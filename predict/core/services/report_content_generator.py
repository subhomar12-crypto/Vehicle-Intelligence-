"""
LLM-powered report content generator.

Uses Anthropic Haiku (primary) → local Qwen (fallback) → template strings (last resort)
to generate narrative report sections from structured vehicle health data.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ReportContentGenerator:
    """Generates narrative report sections using LLM."""

    def __init__(self):
        self.haiku_client = None
        self.local_llm = None
        self._init_clients()

    def _init_clients(self):
        # Anthropic Haiku — same pattern as vehicle_research_engine.py
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                self.haiku_client = anthropic.Anthropic(api_key=api_key)
                logger.info("ReportContentGenerator: Haiku client ready")
            else:
                logger.info("ReportContentGenerator: No ANTHROPIC_API_KEY — will use local LLM")
        except ImportError:
            logger.warning("ReportContentGenerator: anthropic package not installed")

        # Local Qwen fallback
        try:
            from predict.core.ai.llm.assistant import get_llm_assistant
            self.local_llm = get_llm_assistant()
            logger.info("ReportContentGenerator: Local LLM fallback ready")
        except Exception as e:
            logger.warning(f"ReportContentGenerator: Local LLM not available: {e}")

    async def generate_diagnostic_narrative(
        self,
        vehicle_info: Dict[str, Any],
        health_data: Dict[str, Any],
        research_data: Optional[Dict[str, Any]] = None,
        stats_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Generate narrative sections for a diagnostic report.

        Returns dict with keys:
            executive_summary, component_analysis, recommendations, maintenance_outlook
        """
        prompt = self._build_prompt(vehicle_info, health_data, research_data, stats_summary)

        # Try Haiku first
        if self.haiku_client:
            try:
                narrative = await self._call_haiku(prompt)
                if narrative:
                    return narrative
            except Exception as e:
                logger.warning(f"Haiku narrative generation failed: {e}")

        # Fallback to local Qwen
        if self.local_llm:
            try:
                narrative = await self._call_local_llm(prompt)
                if narrative:
                    return narrative
            except Exception as e:
                logger.warning(f"Local LLM narrative generation failed: {e}")

        # Last resort: template-based text
        logger.info("Using template-based narrative (both LLMs unavailable)")
        return self._template_narrative(vehicle_info, health_data, research_data)

    def _build_prompt(
        self,
        vehicle_info: Dict[str, Any],
        health_data: Dict[str, Any],
        research_data: Optional[Dict[str, Any]],
        stats_summary: Optional[Dict[str, Any]],
    ) -> str:
        make = vehicle_info.get("make", "Unknown")
        model = vehicle_info.get("model", "Unknown")
        year = vehicle_info.get("year", "Unknown")
        engine = vehicle_info.get("engine_type", "")
        displacement = vehicle_info.get("displacement", "")

        health_score = health_data.get("health_score", "N/A")
        components = health_data.get("components", [])
        is_cold_start = health_data.get("is_cold_start", True)

        # Build component summary
        comp_lines = []
        for c in components[:10]:
            name = c.get("name", c.get("component_id", "Unknown"))
            pct = c.get("health_percent", "?")
            trend = c.get("trend", "stable")
            rec = c.get("recommendation", "")
            comp_lines.append(f"- {name}: {pct}% health, trend: {trend}. {rec}")
        comp_text = "\n".join(comp_lines) if comp_lines else "No component data available."

        # Research context
        research_text = ""
        if research_data:
            problems = research_data.get("common_problems", [])[:5]
            recalls = research_data.get("recalls", [])[:3]
            reliability = research_data.get("reliability_score", "N/A")
            research_text = f"""
Known Issues for this Vehicle:
- Reliability score: {reliability}/10
- Common problems: {'; '.join(str(p) for p in problems) if problems else 'None documented'}
- Active recalls: {len(recalls)} {'— ' + '; '.join(str(r) for r in recalls) if recalls else ''}
"""

        # Stats summary
        stats_text = ""
        if stats_summary and stats_summary.get("status") != "no_data":
            sensors = stats_summary.get("sensors", {})
            stat_lines = []
            for sensor_name, data in sensors.items():
                risk = data.get("risk_level", "normal")
                trend = data.get("trend", "stable")
                if risk != "normal" or trend != "stable":
                    stat_lines.append(
                        f"- {sensor_name}: risk={risk}, trend={trend}, "
                        f"mean={data.get('mean', 'N/A'):.1f}, anomalies={data.get('anomaly_count', 0)}"
                    )
            if stat_lines:
                stats_text = "\nSensor Anomalies:\n" + "\n".join(stat_lines)

        data_note = ""
        if is_cold_start:
            data_note = "\nNote: Limited telemetry data. Analysis relies on vehicle research and statistical baselines."

        return f"""You are PREDICT, an AI vehicle diagnostic assistant operating in Qatar (extreme heat 45°C+, desert dust, heavy AC load). Generate a professional vehicle health report.

Vehicle: {year} {make} {model} {engine} {displacement}
Overall Health Score: {health_score}/100{data_note}

Component Health:
{comp_text}
{research_text}{stats_text}

Write exactly 4 sections separated by "---". Each section starts with the section name on its own line:

EXECUTIVE SUMMARY
A 2-3 sentence overview of vehicle health status, highlighting critical concerns.

COMPONENT ANALYSIS
Brief analysis of each component's condition, focusing on items needing attention. Reference Qatar climate impact where relevant.

RECOMMENDATIONS
Numbered list of 3-5 actionable maintenance recommendations, prioritized by urgency.

MAINTENANCE OUTLOOK
2-3 sentences on expected maintenance needs over the next 3-6 months, considering Qatar driving conditions.

Keep language professional, concise, and actionable. Use QAR for cost estimates."""

    async def _call_haiku(self, prompt: str) -> Optional[Dict[str, str]]:
        import asyncio

        def _sync_call():
            response = self.haiku_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        text = await asyncio.to_thread(_sync_call)
        return self._parse_sections(text)

    async def _call_local_llm(self, prompt: str) -> Optional[Dict[str, str]]:
        # local_llm.chat() is sync
        import asyncio

        def _sync_call():
            return self.local_llm.chat(prompt)

        response_text = await asyncio.to_thread(_sync_call)
        if response_text:
            return self._parse_sections(response_text)
        return None

    def _parse_sections(self, text: str) -> Optional[Dict[str, str]]:
        """Parse LLM output into section dict."""
        sections = {
            "executive_summary": "",
            "component_analysis": "",
            "recommendations": "",
            "maintenance_outlook": "",
        }

        section_keys = {
            "EXECUTIVE SUMMARY": "executive_summary",
            "COMPONENT ANALYSIS": "component_analysis",
            "RECOMMENDATIONS": "recommendations",
            "MAINTENANCE OUTLOOK": "maintenance_outlook",
        }

        current_key = None
        current_lines = []

        for line in text.split("\n"):
            stripped = line.strip().upper()
            if stripped in section_keys:
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = section_keys[stripped]
                current_lines = []
            elif line.strip() == "---":
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()
                    current_key = None
                    current_lines = []
            elif current_key:
                current_lines.append(line)

        if current_key and current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

        # Validate we got at least the executive summary
        if sections["executive_summary"]:
            return sections
        # If parsing failed, put everything in executive_summary
        if text.strip():
            sections["executive_summary"] = text.strip()[:500]
            return sections
        return None

    def _template_narrative(
        self,
        vehicle_info: Dict[str, Any],
        health_data: Dict[str, Any],
        research_data: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Template-based fallback when both LLMs are unavailable."""
        make = vehicle_info.get("make", "Unknown")
        model = vehicle_info.get("model", "Unknown")
        year = vehicle_info.get("year", "Unknown")
        score = health_data.get("health_score", "N/A")

        components = health_data.get("components", [])
        critical = [c for c in components if c.get("health_percent", 100) < 50]
        warning = [c for c in components if 50 <= c.get("health_percent", 100) < 75]

        critical_text = ""
        if critical:
            names = ", ".join(c.get("name", c.get("component_id", "?")) for c in critical)
            critical_text = f" Critical attention needed for: {names}."

        warning_text = ""
        if warning:
            names = ", ".join(c.get("name", c.get("component_id", "?")) for c in warning)
            warning_text = f" Monitor closely: {names}."

        recs = []
        for c in (critical + warning)[:5]:
            rec = c.get("recommendation", "")
            if rec:
                recs.append(f"- {rec}")
        rec_text = "\n".join(recs) if recs else "- Continue regular maintenance schedule."

        return {
            "executive_summary": (
                f"Your {year} {make} {model} has an overall health score of {score}/100."
                f"{critical_text}{warning_text}"
                " Operating in Qatar's extreme heat conditions places additional stress on cooling and electrical systems."
            ),
            "component_analysis": "\n".join(
                f"- {c.get('name', c.get('component_id', '?'))}: "
                f"{c.get('health_percent', '?')}% — {c.get('recommendation', 'No issues detected.')}"
                for c in components[:10]
            ) or "No component data available for analysis.",
            "recommendations": rec_text,
            "maintenance_outlook": (
                f"Based on current health scores, your {make} {model} requires "
                f"{'immediate attention' if critical else 'routine maintenance'} "
                "over the next 3-6 months. Qatar's summer temperatures will increase stress on "
                "battery, coolant system, and AC components."
            ),
        }


_generator = None


def get_report_content_generator() -> ReportContentGenerator:
    global _generator
    if _generator is None:
        _generator = ReportContentGenerator()
    return _generator
