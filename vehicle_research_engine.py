"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Vehicle Research Engine - LLM-powered web research for vehicle registration.
Searches for common problems, failure rates, costs, and owner experiences.

This module runs during vehicle registration to gather vehicle-specific
knowledge that feeds into AI prediction models.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json
import re
import time

logger = logging.getLogger(__name__)


@dataclass
class CommonProblem:
    """A known problem for a vehicle"""
    problem: str
    severity: str  # high, medium, low
    frequency: str  # common, occasional, rare
    affected_components: List[str] = field(default_factory=list)
    typical_mileage: Optional[int] = None
    repair_cost_qar: Optional[int] = None


@dataclass
class FailurePronePart:
    """A part known to fail frequently"""
    part: str
    failure_rate: float  # 0.0-1.0
    avg_cost_qar: int
    typical_failure_mileage: Optional[int] = None
    symptoms: List[str] = field(default_factory=list)


@dataclass
class Recall:
    """Vehicle recall information"""
    recall_id: str
    description: str
    affected_years: str
    remedy: str = ""
    date_issued: str = ""


@dataclass
class TSB:
    """Technical Service Bulletin"""
    tsb_id: str
    description: str
    fix: str
    components: List[str] = field(default_factory=list)


@dataclass
class AIFeatures:
    """Numerical features extracted for AI prediction integration"""
    known_issue_multiplier: float = 1.0  # 0.8-1.5 risk factor
    reliability_factor: float = 1.0  # 0.8-1.2
    failure_probability_boost: Dict[str, float] = field(default_factory=dict)
    avg_part_costs: Dict[str, int] = field(default_factory=dict)
    common_failure_parts: List[str] = field(default_factory=list)
    dtc_severity_adjustments: Dict[str, float] = field(default_factory=dict)


@dataclass
class VehicleResearchResult:
    """Complete research results for a vehicle make/model/year"""
    make: str
    model: str
    year: int

    # Common problems
    common_problems: List[CommonProblem] = field(default_factory=list)

    # Part failure data
    failure_prone_parts: List[FailurePronePart] = field(default_factory=list)

    # Recalls and TSBs
    recalls: List[Recall] = field(default_factory=list)
    tsbs: List[TSB] = field(default_factory=list)

    # Owner experiences
    owner_reviews_summary: str = ""
    reliability_score: float = 5.0  # 0-10

    # Extracted numerical features for AI
    ai_features: AIFeatures = field(default_factory=AIFeatures)

    # Metadata
    research_date: str = ""
    sources: List[str] = field(default_factory=list)
    confidence_score: float = 0.5
    research_status: str = "completed"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'make': self.make,
            'model': self.model,
            'year': self.year,
            'common_problems': [asdict(p) for p in self.common_problems],
            'failure_prone_parts': [asdict(p) for p in self.failure_prone_parts],
            'recalls': [asdict(r) for r in self.recalls],
            'tsbs': [asdict(t) for t in self.tsbs],
            'owner_reviews_summary': self.owner_reviews_summary,
            'reliability_score': self.reliability_score,
            'ai_features': asdict(self.ai_features),
            'research_date': self.research_date,
            'sources': self.sources,
            'confidence_score': self.confidence_score,
            'research_status': self.research_status
        }


class VehicleResearchEngine:
    """
    Orchestrates web search and LLM analysis for vehicle research.

    Process:
    1. Perform multiple targeted web searches
    2. Aggregate search results
    3. Use LLM to extract structured data
    4. Generate numerical features for AI predictions
    """

    SEARCH_QUERIES = [
        "{year} {make} {model} common problems issues",
        "{year} {make} {model} reliability consumer reports",
        "{year} {make} {model} parts failure breakdown",
        "{year} {make} {model} recall NHTSA safety",
        "{year} {make} {model} owner complaints forum",
        "{year} {make} {model} maintenance repair costs",
        "{year} {make} {model} TSB technical service bulletin"
    ]

    def __init__(self):
        self.search_engine = None
        self.llm = None
        self._init_dependencies()

    def _init_dependencies(self):
        """Initialize search engine and LLM dependencies"""
        # Try to import web search
        try:
            from web_search import get_search_engine
            self.search_engine = get_search_engine()
            logger.info("Web search engine initialized")
        except ImportError as e:
            logger.warning(f"Web search not available: {e}")
            self.search_engine = None

        # Try to import LLM
        try:
            from llm_assistant import get_llm_assistant
            self.llm = get_llm_assistant()
            logger.info("LLM assistant initialized")
        except ImportError as e:
            logger.warning(f"LLM assistant not available: {e}")
            self.llm = None

        # Try Anthropic Haiku for research extraction (preferred over local LLM)
        self.haiku_client = None
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                self.haiku_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Anthropic Haiku initialized for research extraction")
            else:
                logger.info("No ANTHROPIC_API_KEY set — will use local LLM for research")
        except ImportError:
            logger.warning("anthropic package not installed — falling back to local LLM")

        logger.info(
            f"Research engine ready: haiku={'yes' if self.haiku_client else 'no'}, "
            f"local_llm={'yes' if self.llm else 'no'}, "
            f"web_search={'yes' if self.search_engine else 'no'}"
        )

    def research_vehicle(
        self,
        make: str,
        model: str,
        year: int,
        progress_callback: Callable[[int, str], None] = None,
        force_refresh: bool = False,
        engine_type: str = None,
        fuel_type: str = None,
    ) -> VehicleResearchResult:
        """
        Perform comprehensive research on a vehicle.

        Args:
            make: Vehicle make (e.g., "Toyota")
            model: Vehicle model (e.g., "Camry")
            year: Model year (e.g., 2012)
            progress_callback: Optional callback(percent, message)
            force_refresh: If True, bypass any cached data and perform fresh research

        Returns:
            VehicleResearchResult with all research data
        """
        def report_progress(percent: int, message: str):
            if progress_callback:
                try:
                    progress_callback(percent, message)
                except Exception:
                    pass
            logger.debug(f"Research progress: {percent}% - {message}")

        # Build engine suffix for more specific searches
        engine_suffix = ""
        if engine_type:
            engine_suffix += f" {engine_type}"
        if fuel_type and fuel_type.lower() not in (engine_type or "").lower():
            engine_suffix += f" {fuel_type}"

        report_progress(0, f"Starting research for {year} {make} {model}{engine_suffix}...")

        all_results = []
        sources = []

        # Step 1: Execute web searches (40% of progress)
        if self.search_engine:
            total_queries = len(self.SEARCH_QUERIES)
            for i, query_template in enumerate(self.SEARCH_QUERIES):
                progress = int((i / total_queries) * 40)
                query = query_template.format(year=year, make=make, model=model)
                if engine_suffix:
                    query += engine_suffix
                report_progress(progress, f"Searching: {query[:50]}...")

                try:
                    results = self.search_engine.search(query, max_results=3)
                    all_results.extend(results)
                    sources.extend([r.get('url', '') for r in results if r.get('url')])
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")

                # Small delay between searches to be respectful
                time.sleep(0.5)
        else:
            report_progress(40, "Web search not available, using fallback data...")

        # Step 2: Aggregate and format for LLM (10% of progress)
        report_progress(50, "Processing search results...")
        aggregated_text = self._aggregate_results(all_results)

        # Step 3: LLM extraction — prefer Haiku, fall back to local LLM
        parsed_data = {}
        if aggregated_text:
            extraction_prompt = self._build_extraction_prompt(make, model, year, aggregated_text,
                                                               engine_type=engine_type, fuel_type=fuel_type)

            if self.haiku_client:
                report_progress(60, "AI analyzing vehicle data (Haiku)...")
                try:
                    response = self.haiku_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=1500,
                        messages=[{"role": "user", "content": extraction_prompt}]
                    )
                    llm_response = response.content[0].text
                    report_progress(80, "Extracting structured data...")
                    parsed_data = self._parse_llm_response(llm_response)
                    logger.info(f"Haiku extraction succeeded for {year} {make} {model}")
                except Exception as e:
                    logger.error(f"Haiku extraction failed: {e}")
                    parsed_data = self._get_fallback_data(make, model, year)
            elif self.llm:
                report_progress(60, "AI analyzing vehicle data (local)...")
                try:
                    llm_response = self.llm.chat(extraction_prompt, max_tokens=1500, temperature=0.2)
                    report_progress(80, "Extracting structured data...")
                    parsed_data = self._parse_llm_response(llm_response)
                except Exception as e:
                    logger.error(f"Local LLM extraction failed: {e}")
                    parsed_data = self._get_fallback_data(make, model, year)
            else:
                report_progress(80, "No LLM available — using fallback...")
                parsed_data = self._get_fallback_data(make, model, year)
        else:
            report_progress(80, "No search results — using fallback...")
            parsed_data = self._get_fallback_data(make, model, year)

        # Step 4: Generate AI features (10% of progress)
        report_progress(90, "Generating AI features...")
        ai_features = self._generate_ai_features(parsed_data)

        report_progress(100, "Research complete!")

        # Build result
        result = VehicleResearchResult(
            make=make,
            model=model,
            year=year,
            common_problems=self._parse_problems(parsed_data.get('common_problems', [])),
            failure_prone_parts=self._parse_parts(parsed_data.get('failure_prone_parts', [])),
            recalls=self._parse_recalls(parsed_data.get('recalls', [])),
            tsbs=self._parse_tsbs(parsed_data.get('tsbs', [])),
            owner_reviews_summary=parsed_data.get('owner_summary', ''),
            reliability_score=parsed_data.get('reliability_score', 5.0),
            ai_features=ai_features,
            research_date=datetime.now().isoformat(),
            sources=list(set(sources))[:15],
            confidence_score=self._calculate_confidence(all_results),
            research_status="completed"
        )

        logger.info(f"Research completed for {year} {make} {model}: "
                    f"{len(result.common_problems)} problems, "
                    f"{len(result.failure_prone_parts)} failure-prone parts")

        return result

    def _aggregate_results(self, results: List[Dict]) -> str:
        """Combine search results into single text for LLM"""
        if not results:
            return ""

        text_parts = []
        seen_snippets = set()

        for r in results[:20]:  # Limit to top 20 results
            snippet = r.get('snippet', '')
            if snippet and snippet not in seen_snippets:
                text_parts.append(f"- {snippet}")
                seen_snippets.add(snippet)

        return "\n".join(text_parts)

    def _build_extraction_prompt(self, make: str, model: str, year: int, search_text: str,
                                   engine_type: str = None, fuel_type: str = None) -> str:
        """Build prompt for LLM to extract structured data"""
        engine_note = ""
        if engine_type or fuel_type:
            engine_note = f"\nIMPORTANT: This vehicle has a {engine_type or ''} {fuel_type or ''} engine. Only include problems, recalls, and information specific to this engine variant. Do NOT include information about other engine variants (e.g., if this is a petrol/gasoline engine, exclude diesel-specific issues and vice versa).\n"
        return f"""Analyze the following search results about the {year} {make} {model} and extract structured information.
{engine_note}

SEARCH RESULTS:
{search_text}

Extract the following information in JSON format. Be specific and practical.
Estimate costs in QAR (Qatari Riyals) for the Qatar market (multiply USD by ~3.6).

{{
  "common_problems": [
    {{"problem": "description of issue", "severity": "high/medium/low", "frequency": "common/occasional/rare", "affected_components": ["component1"], "repair_cost_qar": estimated_cost}}
  ],
  "failure_prone_parts": [
    {{"part": "part name", "failure_rate": 0.0-1.0, "avg_cost_qar": cost_in_qar, "symptoms": ["symptom1"]}}
  ],
  "recalls": [
    {{"recall_id": "NHTSA_ID_if_known", "description": "brief description", "affected_years": "year range", "remedy": "fix"}}
  ],
  "tsbs": [
    {{"tsb_id": "ID_if_known", "description": "issue", "fix": "solution", "components": ["component"]}}
  ],
  "owner_summary": "2-3 sentence summary of typical owner experiences and reliability",
  "reliability_score": 0-10 rating based on available information
}}

Focus on actionable maintenance and repair information.
If information is not available for a section, use empty arrays or reasonable defaults.
Respond ONLY with the JSON, no additional text or explanation."""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")

        return self._get_fallback_data("", "", 0)

    def _get_fallback_data(self, make: str, model: str, year: int) -> Dict[str, Any]:
        """Return fallback data when research fails"""
        return {
            'common_problems': [],
            'failure_prone_parts': [
                {'part': 'battery', 'failure_rate': 0.15, 'avg_cost_qar': 300, 'symptoms': ['slow start', 'dim lights']},
                {'part': 'alternator', 'failure_rate': 0.10, 'avg_cost_qar': 500, 'symptoms': ['battery warning', 'dim lights']},
                {'part': 'brake_pads', 'failure_rate': 0.20, 'avg_cost_qar': 250, 'symptoms': ['squeaking', 'longer stopping']},
            ],
            'recalls': [],
            'tsbs': [],
            'owner_summary': f'General maintenance recommended for {year} {make} {model}. Specific data not available.',
            'reliability_score': 5.0
        }

    def _parse_problems(self, problems_data: List[Dict]) -> List[CommonProblem]:
        """Parse problem data into CommonProblem objects"""
        problems = []
        for p in problems_data:
            try:
                problems.append(CommonProblem(
                    problem=p.get('problem', 'Unknown issue'),
                    severity=p.get('severity', 'medium'),
                    frequency=p.get('frequency', 'occasional'),
                    affected_components=p.get('affected_components', []),
                    typical_mileage=p.get('typical_mileage'),
                    repair_cost_qar=p.get('repair_cost_qar')
                ))
            except Exception as e:
                logger.warning(f"Failed to parse problem: {e}")
        return problems

    def _parse_parts(self, parts_data: List[Dict]) -> List[FailurePronePart]:
        """Parse part data into FailurePronePart objects"""
        parts = []
        for p in parts_data:
            try:
                parts.append(FailurePronePart(
                    part=p.get('part', 'Unknown'),
                    failure_rate=float(p.get('failure_rate', 0.1)),
                    avg_cost_qar=int(p.get('avg_cost_qar', 200)),
                    typical_failure_mileage=p.get('typical_failure_mileage'),
                    symptoms=p.get('symptoms', [])
                ))
            except Exception as e:
                logger.warning(f"Failed to parse part: {e}")
        return parts

    def _parse_recalls(self, recalls_data: List[Dict]) -> List[Recall]:
        """Parse recall data into Recall objects"""
        recalls = []
        for r in recalls_data:
            try:
                recalls.append(Recall(
                    recall_id=r.get('recall_id', 'Unknown'),
                    description=r.get('description', ''),
                    affected_years=r.get('affected_years', ''),
                    remedy=r.get('remedy', ''),
                    date_issued=r.get('date_issued', '')
                ))
            except Exception as e:
                logger.warning(f"Failed to parse recall: {e}")
        return recalls

    def _parse_tsbs(self, tsbs_data: List[Dict]) -> List[TSB]:
        """Parse TSB data into TSB objects"""
        tsbs = []
        for t in tsbs_data:
            try:
                tsbs.append(TSB(
                    tsb_id=t.get('tsb_id', 'Unknown'),
                    description=t.get('description', ''),
                    fix=t.get('fix', ''),
                    components=t.get('components', [])
                ))
            except Exception as e:
                logger.warning(f"Failed to parse TSB: {e}")
        return tsbs

    def _generate_ai_features(self, parsed_data: Dict) -> AIFeatures:
        """Generate numerical features for AI prediction integration"""
        features = AIFeatures()

        # Calculate issue multiplier based on problem count and severity
        problems = parsed_data.get('common_problems', [])
        if problems:
            severity_weights = {'high': 0.15, 'medium': 0.08, 'low': 0.03}
            multiplier = 1.0
            for p in problems:
                severity = p.get('severity', 'low') if isinstance(p, dict) else 'low'
                multiplier += severity_weights.get(severity, 0.03)
            features.known_issue_multiplier = min(1.5, multiplier)

        # Extract failure-prone parts
        parts = parsed_data.get('failure_prone_parts', [])
        for part in parts:
            if isinstance(part, dict):
                part_name = part.get('part', '').lower().replace(' ', '_')
                if part_name:
                    features.common_failure_parts.append(part_name)
                    features.avg_part_costs[part_name] = int(part.get('avg_cost_qar', 200))
                    features.failure_probability_boost[part_name] = float(part.get('failure_rate', 0.1))

        # Reliability factor (inverse of reliability score)
        reliability = float(parsed_data.get('reliability_score', 5.0))
        features.reliability_factor = max(0.8, min(1.2, 2 - (reliability / 10)))

        # Generate DTC severity adjustments based on common problems
        problem_to_dtc = {
            'engine': 'P0',
            'transmission': 'P07',
            'fuel': 'P02',
            'emission': 'P04',
            'ignition': 'P03',
            'evap': 'P04',
            'catalyst': 'P04',
        }

        for problem in problems:
            if isinstance(problem, dict):
                problem_text = problem.get('problem', '').lower()
                severity = problem.get('severity', 'low')
                severity_mult = {'high': 1.3, 'medium': 1.15, 'low': 1.05}

                for keyword, dtc_prefix in problem_to_dtc.items():
                    if keyword in problem_text:
                        features.dtc_severity_adjustments[dtc_prefix] = severity_mult.get(severity, 1.0)

        return features

    def _calculate_confidence(self, results: List[Dict]) -> float:
        """Calculate confidence score based on result quality"""
        if not results:
            return 0.3

        # More results = higher confidence
        result_score = min(1.0, len(results) / 20)

        # Results with URLs are more trustworthy
        url_count = sum(1 for r in results if r.get('url'))
        url_score = min(1.0, url_count / 10)

        return round((result_score * 0.6 + url_score * 0.4), 2)

    def should_refresh_research(self, research_data: Dict[str, Any], max_age_days: int = 30) -> bool:
        """Check if research data should be refreshed"""
        if not research_data:
            return True

        research_date = research_data.get('research_date')
        if not research_date:
            return True

        try:
            last_research = datetime.fromisoformat(research_date)
            days_since = (datetime.now() - last_research).days
            return days_since >= max_age_days
        except Exception:
            return True


# Singleton instance
_research_engine: Optional[VehicleResearchEngine] = None


def get_research_engine() -> VehicleResearchEngine:
    """Get global research engine instance"""
    global _research_engine
    if _research_engine is None:
        _research_engine = VehicleResearchEngine()
    return _research_engine


def research_vehicle_sync(
    make: str,
    model: str,
    year: int,
    progress_callback: Callable[[int, str], None] = None
) -> Dict[str, Any]:
    """
    Convenience function to research a vehicle and return dict.

    Args:
        make: Vehicle make
        model: Vehicle model
        year: Model year
        progress_callback: Optional progress callback

    Returns:
        Research results as dictionary
    """
    engine = get_research_engine()
    result = engine.research_vehicle(make, model, year, progress_callback)
    return result.to_dict()
