"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Web Search Module for PREDICT AI
Provides web search with fallback chain:
  1. Serper.dev (Google SERP data) - Primary
  2. Brave Search API - Secondary (when API key available)
  3. DuckDuckGo Instant Answer API - Last resort
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class WebSearchEngine:
    """Web search with Serper.dev (primary) + Brave (fallback) + DuckDuckGo (last resort)."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PREDICT-AI/2.0'
        })
        self.serper_api_key = os.getenv("SERPER_API_KEY", "").strip()
        self.brave_api_key = os.getenv("BRAVE_API_KEY", "").strip()
        self._last_source = "none"

    @property
    def last_source(self) -> str:
        """Which search engine was used for the last query."""
        return self._last_source

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search using fallback chain: Serper.dev -> Brave -> DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of dicts with 'title', 'url', 'snippet'
        """
        # Try Serper.dev first (Google results)
        if self.serper_api_key:
            results = self._search_serper(query, max_results)
            if results:
                self._last_source = "serper"
                return results
            logger.warning("Serper.dev returned no results, trying fallback")

        # Fallback to Brave Search
        if self.brave_api_key:
            results = self._search_brave(query, max_results)
            if results:
                self._last_source = "brave"
                return results
            logger.warning("Brave Search returned no results, trying DuckDuckGo")

        # Last resort: DuckDuckGo Instant Answer
        results = self._search_duckduckgo(query, max_results)
        if results:
            self._last_source = "duckduckgo"
        else:
            self._last_source = "none"

        # If still no results and it's a DTC code, try OBD-Codes.com
        if not results and re.search(r'[PCBU][0-9]{4}', query.upper()):
            results = self._search_dtc_database(query)
            if results:
                self._last_source = "obd-codes"

        return results

    def _search_serper(self, query: str, max_results: int) -> List[Dict]:
        """Search using Serper.dev (Google SERP data)."""
        results = []
        try:
            response = self.session.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.serper_api_key},
                json={"q": query, "num": max_results},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            # Parse organic results
            for item in data.get("organic", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

            # Include answer box if available
            answer_box = data.get("answerBox")
            if answer_box and not results:
                results.append({
                    "title": answer_box.get("title", "Answer"),
                    "url": answer_box.get("link", ""),
                    "snippet": answer_box.get("snippet", answer_box.get("answer", "")),
                })

            # Include knowledge graph if available
            kg = data.get("knowledgeGraph")
            if kg:
                desc = kg.get("description", "")
                if desc and len(results) < max_results:
                    results.append({
                        "title": kg.get("title", ""),
                        "url": kg.get("website", kg.get("descriptionLink", "")),
                        "snippet": desc,
                    })

            logger.info(f"Serper.dev search for '{query}' returned {len(results)} results")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.error("Serper.dev API key invalid or quota exceeded")
            else:
                logger.error(f"Serper.dev HTTP error: {e}")
        except Exception as e:
            logger.error(f"Serper.dev search error: {e}")

        return results

    def _search_brave(self, query: str, max_results: int) -> List[Dict]:
        """Search using Brave Search API."""
        results = []
        try:
            response = self.session.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.brave_api_key,
                },
                params={"q": query, "count": max_results},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                })

            logger.info(f"Brave search for '{query}' returned {len(results)} results")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                logger.error("Brave API key invalid or missing")
            else:
                logger.error(f"Brave Search HTTP error: {e}")
        except Exception as e:
            logger.error(f"Brave Search error: {e}")

        return results

    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Search using DuckDuckGo Instant Answer API (last resort)."""
        results = []
        try:
            api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('Abstract'):
                results.append({
                    'title': data.get('Heading', 'DuckDuckGo Result'),
                    'url': data.get('AbstractURL', ''),
                    'snippet': data.get('Abstract', '')
                })

            for topic in data.get('RelatedTopics', [])[:max_results - 1]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '')[:60] + '...',
                        'url': topic.get('FirstURL', ''),
                        'snippet': topic.get('Text', '')
                    })

            logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results")

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")

        return results

    def _search_dtc_database(self, query: str) -> List[Dict]:
        """Fallback search specifically for DTC codes via obd-codes.com."""
        results = []
        try:
            match = re.search(r'([PCBU][0-9]{4})', query.upper())
            if match:
                dtc_code = match.group(1)
                url = f"https://www.obd-codes.com/{dtc_code.lower()}"
                response = self.session.get(url, timeout=10)

                if response.status_code == 200:
                    html = response.text
                    title_match = re.search(r'<title>([^<]+)</title>', html)
                    desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)

                    if title_match or desc_match:
                        results.append({
                            'title': title_match.group(1) if title_match else f"DTC {dtc_code}",
                            'url': url,
                            'snippet': desc_match.group(1) if desc_match else f"Information about diagnostic trouble code {dtc_code}"
                        })

        except Exception as e:
            logger.debug(f"DTC database search failed: {e}")

        return results

    def search_automotive(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search for automotive-related information.
        For Serper/Brave, adds automotive context only if the query is generic.

        Args:
            query: Search query (can be DTC code, car issue, etc.)
            max_results: Maximum number of results

        Returns:
            List of search results
        """
        # DTC codes don't need extra context
        if re.search(r'[PCBU][0-9]{4}', query.upper()):
            enhanced_query = f"{query} diagnostic trouble code meaning causes fix"
        else:
            enhanced_query = f"{query} car automotive repair diagnosis"
        return self.search(enhanced_query, max_results)

    def format_results_for_llm(self, results: List[Dict]) -> str:
        """
        Format search results as context for the LLM.

        Args:
            results: List of search result dicts

        Returns:
            Formatted string for LLM context
        """
        if not results:
            return "No web search results found."

        formatted = f"Web Search Results (via {self._last_source}):\n\n"

        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result['title']}\n"
            formatted += f"   {result['snippet']}\n"
            formatted += f"   Source: {result['url']}\n\n"

        return formatted


def should_search_web(message: str) -> bool:
    """
    Determine if a message should trigger a web search.

    Args:
        message: User message

    Returns:
        True if web search would be helpful
    """
    search_triggers = [
        'search', 'look up', 'find', 'google', 'web',
        'latest', 'current', 'recent', 'news',
        'how to', 'what is', 'why does', 'when should',
        'price', 'cost', 'buy', 'shop',
        'recall', 'tsb', 'bulletin',
        'specifications', 'specs',
        'common problem', 'known issue',
        'part number', 'compatible', 'fits',
        'oil filter', 'brake pad', 'spark plug',
        # Symptoms and conditions
        'leaking', 'grinding', 'squealing', 'smell', 'smoke', 'vibration',
        'overheating', 'stalling', 'misfiring', 'rough idle', 'check engine',
        'knocking', 'rattling', 'shaking', 'pulling',
        # Maintenance and parts
        'replace', 'change', 'service', 'maintenance', 'interval',
        'reliable', 'problems with', 'issues with',
        'torque spec', 'capacity', 'fluid type',
    ]

    message_lower = message.lower()

    for trigger in search_triggers:
        if trigger in message_lower:
            return True

    # Check for DTC codes
    dtc_pattern = r'\b[PCBU][0-9]{4}\b'
    if re.search(dtc_pattern, message.upper()):
        return True

    return False


# Global instance
_search_engine = None


def get_search_engine() -> WebSearchEngine:
    """Get or create the global search engine instance."""
    global _search_engine
    if _search_engine is None:
        _search_engine = WebSearchEngine()
    return _search_engine


def web_search(query: str, max_results: int = 5) -> str:
    """
    Convenience function to perform a web search and return formatted results.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        Formatted string with search results
    """
    engine = get_search_engine()
    results = engine.search_automotive(query, max_results)
    return engine.format_results_for_llm(results)
