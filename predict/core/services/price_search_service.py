"""
Price Search Service — LLM-powered web search for Qatar auto parts pricing.

Searches the web for parts/service prices targeting Qatar retailers,
then uses the local LLM (Ollama/Qwen) to extract structured price data
from the search results.

Results are NOT auto-saved. The admin reviews them in the desktop UI
and manually saves verified prices to the database.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Optional

from web_search import get_search_engine

logger = logging.getLogger(__name__)

# ========================
# Qatar supplier names used to build targeted search queries
# ========================

QATAR_SUPPLIERS = [
    "Taiseer Auto Parts Qatar",
    "Woqood Qatar",
    "Al Muftah Auto Parts",
    "Petromin Express Qatar",
    "Toyota Qatar genuine parts",
    "Nissan Qatar genuine parts",
    "AutoZone Qatar",
]

# ========================
# Component → part categories mapping
# ========================

COMPONENT_TO_CATEGORIES: dict[str, list[str]] = {
    "engine_oil": ["oil", "oil_filter"],
    "coolant_system": ["coolant", "thermostat", "radiator"],
    "battery": ["battery", "alternator"],
    "brakes": ["brake_pad", "brake_disc", "brake_fluid"],
    "transmission_fluid": ["transmission_fluid"],
    "spark_plugs": ["spark_plug", "ignition_coil"],
    "catalytic_converter": ["catalytic_converter"],
    "o2_sensors": ["o2_sensor"],
    "air_filter": ["air_filter", "cabin_filter"],
    "fuel_system": ["fuel_filter", "fuel_pump"],
}

# Human-readable labels for display in search queries
_CATEGORY_LABELS: dict[str, str] = {
    "oil": "engine oil",
    "oil_filter": "oil filter",
    "coolant": "coolant fluid",
    "thermostat": "thermostat",
    "radiator": "radiator",
    "battery": "car battery",
    "alternator": "alternator",
    "brake_pad": "brake pads",
    "brake_disc": "brake disc rotor",
    "brake_fluid": "brake fluid",
    "transmission_fluid": "transmission fluid",
    "spark_plug": "spark plugs",
    "ignition_coil": "ignition coil",
    "catalytic_converter": "catalytic converter",
    "o2_sensor": "oxygen sensor O2 sensor",
    "air_filter": "air filter",
    "cabin_filter": "cabin air filter",
    "fuel_filter": "fuel filter",
    "fuel_pump": "fuel pump",
}


@dataclass
class PriceSearchResult:
    """A single price result extracted by the LLM from web search data."""
    product_name: str
    brand: str
    price_qar: float
    supplier: str
    source_url: str
    confidence: float


class PriceSearchService:
    """Search the web for Qatar auto parts prices and extract structured data via LLM."""

    # Ollama config (same as assistant.py)
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen3.5:2b"
    MAX_QUERIES = 3
    RESULTS_PER_QUERY = 5

    def __init__(self):
        self._search_engine = get_search_engine()

    async def search_prices(
        self,
        component: str,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        vehicle_year: Optional[int] = None,
    ) -> List[PriceSearchResult]:
        """Search for parts prices and return LLM-extracted results.

        Args:
            component: Component ID (e.g. 'engine_oil', 'battery').
            vehicle_make: Optional vehicle make for targeted queries.
            vehicle_model: Optional vehicle model for targeted queries.
            vehicle_year: Optional vehicle year for targeted queries.

        Returns:
            List of PriceSearchResult with extracted price data.
        """
        queries = self._build_queries(component, vehicle_make, vehicle_model, vehicle_year)

        # Run web searches (synchronous engine, run in thread pool)
        all_results: list[dict] = []
        for query in queries[:self.MAX_QUERIES]:
            try:
                results = await asyncio.to_thread(
                    self._search_engine.search, query, self.RESULTS_PER_QUERY
                )
                all_results.extend(results)
            except Exception as e:
                logger.warning("Web search failed for query '%s': %s", query, e)

        if not all_results:
            logger.info("No web search results for component=%s", component)
            return []

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)
            elif not url:
                unique_results.append(r)

        # Format results for LLM extraction
        formatted = self._format_for_extraction(unique_results, component, vehicle_make, vehicle_model)

        # Call LLM to extract structured price data
        llm_response = await self._call_llm(formatted)
        if not llm_response:
            logger.warning("LLM returned empty response for component=%s", component)
            return []

        # Parse LLM output into PriceSearchResult list
        return self._parse_results(llm_response, confidence=0.7)

    def _build_queries(
        self,
        component: str,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[int] = None,
    ) -> List[str]:
        """Build targeted search queries for Qatar auto parts retailers.

        Generates up to MAX_QUERIES queries combining:
        - Component category labels
        - Vehicle make/model/year when available
        - Qatar market targeting (QAR, supplier names)
        """
        categories = COMPONENT_TO_CATEGORIES.get(component, [component])
        vehicle_str = ""
        if make:
            parts = [make]
            if model:
                parts.append(model)
            if year:
                parts.append(str(year))
            vehicle_str = " ".join(parts)

        queries: list[str] = []

        # Query 1: Primary category + vehicle + Qatar pricing
        primary_label = _CATEGORY_LABELS.get(categories[0], categories[0].replace("_", " "))
        if vehicle_str:
            queries.append(f"{vehicle_str} {primary_label} price Qatar QAR")
        else:
            queries.append(f"{primary_label} car price Qatar QAR")

        # Query 2: Add a supplier name for more targeted results
        if len(queries) < self.MAX_QUERIES:
            supplier = QATAR_SUPPLIERS[0]  # Taiseer is the largest
            if vehicle_str:
                queries.append(f"{vehicle_str} {primary_label} {supplier}")
            else:
                queries.append(f"{primary_label} {supplier}")

        # Query 3: Secondary category if available, or genuine parts
        if len(queries) < self.MAX_QUERIES and len(categories) > 1:
            secondary_label = _CATEGORY_LABELS.get(categories[1], categories[1].replace("_", " "))
            if vehicle_str:
                queries.append(f"{vehicle_str} {secondary_label} price Qatar QAR")
            else:
                queries.append(f"{secondary_label} price Qatar QAR")
        elif len(queries) < self.MAX_QUERIES:
            # Try genuine parts variant
            if make:
                queries.append(f"{make} genuine {primary_label} Qatar price")
            else:
                queries.append(f"genuine OEM {primary_label} Qatar price QAR")

        return queries[:self.MAX_QUERIES]

    def _format_for_extraction(
        self,
        results: list[dict],
        component: str,
        make: Optional[str],
        model: Optional[str],
    ) -> str:
        """Format web search results into an LLM prompt for price extraction."""
        vehicle_desc = ""
        if make:
            vehicle_desc = f" for {make}"
            if model:
                vehicle_desc += f" {model}"

        results_text = ""
        for i, r in enumerate(results, 1):
            results_text += f"\n--- Result {i} ---\n"
            results_text += f"Title: {r.get('title', 'N/A')}\n"
            results_text += f"URL: {r.get('url', 'N/A')}\n"
            results_text += f"Snippet: {r.get('snippet', 'N/A')}\n"

        prompt = f"""Extract auto parts prices from these web search results.
I am looking for {component.replace('_', ' ')}{vehicle_desc} prices in Qatar (QAR currency).

{results_text}

Extract EVERY product/service with a price mentioned. Return a JSON array where each item has:
- "product_name": the part or service name
- "brand": the brand name (or "Unknown" if not stated)
- "price_qar": the price as a number in QAR (convert from USD/SAR if needed: 1 USD ≈ 3.65 QAR, 1 SAR ≈ 0.97 QAR)
- "supplier": the store/supplier name (or "Unknown")
- "source_url": the URL where this price was found

Return ONLY the JSON array, no other text. If no prices are found, return [].
Example: [{{"product_name": "Mobil 1 5W-30 4L", "brand": "Mobil", "price_qar": 85.0, "supplier": "Taiseer Auto Parts", "source_url": "https://example.com"}}]"""

        return prompt

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call Ollama/Qwen via HTTP for price extraction.

        Uses asyncio.to_thread since httpx sync client matches the
        assistant.py pattern (which also uses sync httpx).
        """
        import httpx

        def _sync_call() -> Optional[str]:
            try:
                client = httpx.Client(
                    base_url=self.OLLAMA_BASE_URL,
                    timeout=60.0,
                )
                resp = client.post("/api/chat", json={
                    "model": self.OLLAMA_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a price extraction assistant. "
                                "Extract product prices from web search results "
                                "and return them as a JSON array. "
                                "Return ONLY valid JSON, no markdown or explanation."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "options": {
                        "num_predict": 1024,
                        "temperature": 0.1,
                    },
                    "stream": False,
                    "think": False,
                })
                client.close()

                if resp.status_code != 200:
                    logger.error("Ollama price extraction error: %d %s", resp.status_code, resp.text[:200])
                    return None

                data = resp.json()
                content = data.get("message", {}).get("content", "")

                # Clean Qwen thinking blocks
                content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)
                if "<think>" in content and "</think>" not in content:
                    content = content[:content.index("<think>")]

                return content.strip()

            except Exception as e:
                logger.error("LLM call for price extraction failed: %s", e)
                return None

        return await asyncio.to_thread(_sync_call)

    def _parse_results(self, llm_response: str, confidence: float) -> List[PriceSearchResult]:
        """Parse the LLM JSON response into PriceSearchResult objects.

        Handles common LLM output issues like markdown code fences,
        trailing text after the JSON array, etc.
        """
        text = llm_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (with optional language tag)
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Find the JSON array in the response
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")

        if bracket_start == -1 or bracket_end == -1 or bracket_end <= bracket_start:
            logger.warning("No JSON array found in LLM response: %s", text[:200])
            return []

        json_str = text[bracket_start:bracket_end + 1]

        try:
            items = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM JSON response: %s — raw: %s", e, json_str[:300])
            return []

        if not isinstance(items, list):
            logger.warning("LLM response is not a JSON array")
            return []

        results: list[PriceSearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            price_raw = item.get("price_qar")
            if price_raw is None:
                continue

            try:
                price_qar = float(price_raw)
            except (ValueError, TypeError):
                continue

            if price_qar <= 0:
                continue

            results.append(PriceSearchResult(
                product_name=str(item.get("product_name", "Unknown")).strip(),
                brand=str(item.get("brand", "Unknown")).strip(),
                price_qar=round(price_qar, 2),
                supplier=str(item.get("supplier", "Unknown")).strip(),
                source_url=str(item.get("source_url", "")).strip(),
                confidence=confidence,
            ))

        logger.info("Extracted %d price results from LLM response", len(results))
        return results
