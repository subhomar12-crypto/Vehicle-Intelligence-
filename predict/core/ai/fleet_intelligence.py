"""
Fleet-Level Intelligence Engine.

Analyzes fleet-wide patterns:
1. Cross-vehicle sensor trends (e.g., 3+ vehicles battery declining)
2. Model-specific risk propagation (known issues for same make/model)
3. Fleet efficiency metrics (idle time, fuel waste)
4. Relative health comparison (vs fleet average)
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class FleetIntelligence:
    """Fleet-wide pattern analysis engine."""

    async def analyze_fleet(
        self,
        fleet_vehicles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze fleet-wide patterns from individual vehicle health data.

        Args:
            fleet_vehicles: List of dicts with keys:
                id, make, model, year, health_score, components, trends, urgency

        Returns:
            Dict with insights, fleet_health_avg, at_risk_count, etc.
        """
        if not fleet_vehicles:
            return {
                "insights": [],
                "fleet_health_avg": 0,
                "at_risk_count": 0,
                "vehicle_count": 0,
            }

        insights: List[Dict[str, Any]] = []
        health_scores = [v.get("health_score", 75) for v in fleet_vehicles]
        fleet_avg = sum(health_scores) / len(health_scores) if health_scores else 75

        # 1. Fleet-wide sensor trends
        insights.extend(self._detect_fleet_sensor_trends(fleet_vehicles))

        # 2. Model-specific risk propagation
        insights.extend(self._detect_model_risks(fleet_vehicles))

        # 3. Relative health comparison
        insights.extend(self._relative_health(fleet_vehicles, fleet_avg))

        # 4. Fleet efficiency
        insights.extend(self._fleet_efficiency(fleet_vehicles))

        at_risk = [v for v in fleet_vehicles if v.get("health_score", 75) < 50]

        return {
            "insights": insights,
            "fleet_health_avg": round(fleet_avg, 1),
            "at_risk_count": len(at_risk),
            "vehicle_count": len(fleet_vehicles),
            "at_risk_vehicles": [v.get("id") for v in at_risk],
        }

    def _detect_fleet_sensor_trends(
        self, vehicles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect when multiple vehicles show the same sensor trend."""
        insights = []

        # Track per-component declining trends
        component_declining: Dict[str, List[int]] = {}
        for v in vehicles:
            components = v.get("components", {})
            for comp_name, comp_data in components.items():
                health = comp_data.get("health_pct", 100)
                if health < 60:
                    component_declining.setdefault(comp_name, []).append(v.get("id", 0))

        # Alert if 3+ vehicles have same component declining
        for comp, vehicle_ids in component_declining.items():
            if len(vehicle_ids) >= 3:
                insights.append({
                    "type": "fleet_wide_decline",
                    "severity": "warning",
                    "component": comp,
                    "message": f"{len(vehicle_ids)} vehicles showing {comp} decline",
                    "recommendation": f"Schedule fleet-wide {comp} inspection",
                    "affected_vehicles": vehicle_ids,
                })

        # Battery-specific (common fleet issue in hot climates)
        battery_low = [
            v.get("id")
            for v in vehicles
            if v.get("components", {}).get("battery", {}).get("health_pct", 100) < 50
        ]
        if len(battery_low) >= 2:
            insights.append({
                "type": "fleet_battery_alert",
                "severity": "warning",
                "component": "battery",
                "message": f"{len(battery_low)} vehicles with low battery health",
                "recommendation": "Qatar heat degrades batteries — schedule fleet battery test",
                "affected_vehicles": battery_low,
            })

        return insights

    def _detect_model_risks(
        self, vehicles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """If same make/model has an issue, warn other same-model vehicles."""
        insights = []

        # Group by make+model
        by_model: Dict[str, List[Dict]] = {}
        for v in vehicles:
            key = f"{v.get('make', '')} {v.get('model', '')}".strip()
            if key:
                by_model.setdefault(key, []).append(v)

        for model_key, model_vehicles in by_model.items():
            if len(model_vehicles) < 2:
                continue

            # Find common failing components across same model
            comp_issues: Dict[str, int] = {}
            for v in model_vehicles:
                for comp, data in v.get("components", {}).items():
                    if data.get("health_pct", 100) < 50:
                        comp_issues[comp] = comp_issues.get(comp, 0) + 1

            for comp, count in comp_issues.items():
                ratio = count / len(model_vehicles)
                if ratio >= 0.5 and count >= 2:
                    insights.append({
                        "type": "model_specific_risk",
                        "severity": "info",
                        "component": comp,
                        "message": f"{count}/{len(model_vehicles)} {model_key} vehicles have {comp} issues",
                        "recommendation": f"This may be a known {model_key} issue — check service bulletins",
                        "affected_vehicles": [
                            v.get("id") for v in model_vehicles
                            if v.get("components", {}).get(comp, {}).get("health_pct", 100) < 50
                        ],
                    })

        return insights

    def _relative_health(
        self, vehicles: List[Dict[str, Any]], fleet_avg: float
    ) -> List[Dict[str, Any]]:
        """Flag vehicles significantly below fleet average."""
        insights = []
        for v in vehicles:
            score = v.get("health_score", 75)
            if score < fleet_avg - 20:
                insights.append({
                    "type": "below_fleet_average",
                    "severity": "advisory",
                    "message": f"Vehicle #{v.get('id')} health ({score:.0f}%) is {fleet_avg - score:.0f}% below fleet average",
                    "recommendation": "Prioritize this vehicle for inspection",
                    "affected_vehicles": [v.get("id")],
                })
        return insights

    def _fleet_efficiency(
        self, vehicles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fleet-level efficiency insights."""
        insights = []

        # Count vehicles with high engine load at idle (wasted fuel)
        idle_high_load = []
        for v in vehicles:
            components = v.get("components", {})
            engine = components.get("engine", {})
            if engine.get("health_pct", 100) < 70:
                idle_high_load.append(v.get("id"))

        if len(idle_high_load) >= 3:
            insights.append({
                "type": "fleet_efficiency",
                "severity": "info",
                "message": f"{len(idle_high_load)} vehicles with engine efficiency concerns",
                "recommendation": "Review engine maintenance schedule for these vehicles",
                "affected_vehicles": idle_high_load,
            })

        return insights


# Singleton
_fleet_intelligence: Optional[FleetIntelligence] = None


def get_fleet_intelligence() -> FleetIntelligence:
    global _fleet_intelligence
    if _fleet_intelligence is None:
        _fleet_intelligence = FleetIntelligence()
    return _fleet_intelligence
