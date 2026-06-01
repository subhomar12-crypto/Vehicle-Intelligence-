"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Fleet Learning Aggregator - Cross-user intelligence for same make/model/year vehicles.

When multiple users register the same make/model/year, this module aggregates
ALL their data to improve predictions for everyone.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import logging
import json
import os
import statistics

logger = logging.getLogger(__name__)


@dataclass
class FleetStatistics:
    """Aggregated statistics for a vehicle make/model/year."""

    make: str
    model: str
    year: int

    # Vehicle count
    total_vehicles: int = 0
    active_vehicles: int = 0  # Seen in last 30 days

    # Health statistics
    avg_health_score: float = 0.0
    health_percentiles: Dict[int, float] = field(default_factory=dict)  # {25: 65.0, 50: 72.0, 75: 85.0}

    # Component statistics
    component_health_avgs: Dict[str, float] = field(default_factory=dict)  # {battery: 82.5, alternator: 75.0}
    component_failure_rates: Dict[str, float] = field(default_factory=dict)  # {battery: 0.15, alternator: 0.25}

    # Failure events
    failure_events: List[Dict[str, Any]] = field(default_factory=list)
    common_failure_components: List[str] = field(default_factory=list)

    # Mileage statistics
    avg_mileage: float = 0.0
    mileage_at_failures: Dict[str, float] = field(default_factory=dict)  # {battery: 85000, alternator: 120000}

    # Time-based
    avg_age_years: float = 0.0
    typical_failure_ages: Dict[str, float] = field(default_factory=dict)  # Years from purchase

    # DTC patterns
    common_dtcs: List[Dict[str, Any]] = field(default_factory=list)  # [{code: P0301, frequency: 0.35}]

    # Prediction accuracy (for model improvement)
    prediction_accuracy: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0

    # Metadata
    last_updated: str = ""
    data_quality_score: float = 0.0  # 0-1, based on sample size and completeness

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FleetStatistics':
        return cls(
            make=data.get('make', ''),
            model=data.get('model', ''),
            year=data.get('year', 0),
            total_vehicles=data.get('total_vehicles', 0),
            active_vehicles=data.get('active_vehicles', 0),
            avg_health_score=data.get('avg_health_score', 0.0),
            health_percentiles=data.get('health_percentiles', {}),
            component_health_avgs=data.get('component_health_avgs', {}),
            component_failure_rates=data.get('component_failure_rates', {}),
            failure_events=data.get('failure_events', []),
            common_failure_components=data.get('common_failure_components', []),
            avg_mileage=data.get('avg_mileage', 0.0),
            mileage_at_failures=data.get('mileage_at_failures', {}),
            avg_age_years=data.get('avg_age_years', 0.0),
            typical_failure_ages=data.get('typical_failure_ages', {}),
            common_dtcs=data.get('common_dtcs', []),
            prediction_accuracy=data.get('prediction_accuracy', 0.0),
            false_positive_rate=data.get('false_positive_rate', 0.0),
            false_negative_rate=data.get('false_negative_rate', 0.0),
            last_updated=data.get('last_updated', ''),
            data_quality_score=data.get('data_quality_score', 0.0)
        )


@dataclass
class VehicleComparison:
    """Comparison of a vehicle against fleet statistics."""

    vehicle_id: str
    make: str
    model: str
    year: int

    # Overall comparison
    health_percentile: float = 50.0  # "Better than X% of owners"
    fleet_size: int = 0

    # Component comparisons
    component_percentiles: Dict[str, float] = field(default_factory=dict)  # {battery: 75.0}

    # Risk comparison
    risk_vs_fleet: str = "average"  # "lower", "average", "higher"
    risk_factors: List[str] = field(default_factory=list)  # Components worse than fleet avg

    # Positive factors
    better_than_fleet: List[str] = field(default_factory=list)  # Components better than fleet avg

    # Common issues affecting similar vehicles
    fleet_common_issues: List[str] = field(default_factory=list)

    # Recommendations based on fleet data
    fleet_based_recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FleetLearningAggregator:
    """
    Aggregates data from all vehicles of same make/model/year for
    improved predictions and comparative analysis.
    """

    def __init__(self, base_path: str = "./PredictData"):
        self.base_path = base_path
        self.vehicles_path = os.path.join(base_path, "vehicles")
        self._cache: Dict[str, FleetStatistics] = {}
        self._cache_ttl = 3600  # 1 hour cache
        self._cache_timestamps: Dict[str, datetime] = {}

    def get_fleet_key(self, make: str, model: str, year: int) -> str:
        """Generate unique key for make/model/year combination."""
        return f"{make.lower()}_{model.lower()}_{year}"

    def get_fleet_data_path(self, make: str, model: str, year: int) -> str:
        """Get path to fleet data file."""
        return os.path.join(
            self.vehicles_path,
            make,
            model,
            str(year),
            "_fleet_data.json"
        )

    def load_fleet_statistics(self, make: str, model: str, year: int) -> Optional[FleetStatistics]:
        """Load fleet statistics from file or cache."""
        fleet_key = self.get_fleet_key(make, model, year)

        # Check cache
        if fleet_key in self._cache:
            cache_time = self._cache_timestamps.get(fleet_key)
            if cache_time and (datetime.now() - cache_time).seconds < self._cache_ttl:
                return self._cache[fleet_key]

        # Load from file
        fleet_path = self.get_fleet_data_path(make, model, year)
        if os.path.exists(fleet_path):
            try:
                with open(fleet_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats = FleetStatistics.from_dict(data)
                self._cache[fleet_key] = stats
                self._cache_timestamps[fleet_key] = datetime.now()
                return stats
            except Exception as e:
                logger.error(f"Error loading fleet statistics: {e}")

        return None

    def save_fleet_statistics(self, stats: FleetStatistics) -> bool:
        """Save fleet statistics to file."""
        fleet_path = self.get_fleet_data_path(stats.make, stats.model, stats.year)

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(fleet_path), exist_ok=True)

            stats.last_updated = datetime.now().isoformat()

            with open(fleet_path, 'w', encoding='utf-8') as f:
                json.dump(stats.to_dict(), f, indent=2)

            # Update cache
            fleet_key = self.get_fleet_key(stats.make, stats.model, stats.year)
            self._cache[fleet_key] = stats
            self._cache_timestamps[fleet_key] = datetime.now()

            logger.info(f"Saved fleet statistics for {stats.make} {stats.model} {stats.year}")
            return True

        except Exception as e:
            logger.error(f"Error saving fleet statistics: {e}")
            return False

    def aggregate_fleet_data(self, make: str, model: str, year: int) -> FleetStatistics:
        """
        Aggregate data from all vehicles of same make/model/year.

        This method scans all vehicles matching the criteria and computes
        fleet-wide statistics.
        """
        stats = FleetStatistics(make=make, model=model, year=year)

        # Find all vehicles matching make/model/year
        year_path = os.path.join(self.vehicles_path, make, model, str(year))

        if not os.path.exists(year_path):
            logger.warning(f"No vehicles found for {make} {model} {year}")
            return stats

        # Collect vehicle data
        vehicle_data = []
        health_scores = []
        component_healths: Dict[str, List[float]] = {}
        failure_events = []
        mileages = []
        dtc_counts: Dict[str, int] = {}

        # Scan vehicle directories
        for item in os.listdir(year_path):
            if item.startswith('_') or item.startswith('.'):
                continue

            vehicle_path = os.path.join(year_path, item)
            if not os.path.isdir(vehicle_path):
                continue

            # Load vehicle profile
            profile_path = os.path.join(vehicle_path, "profile.json")
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                    vehicle_data.append(profile)

                    # Extract health score
                    health = profile.get('last_health_score', 0)
                    if health > 0:
                        health_scores.append(health)

                    # Extract mileage
                    mileage = profile.get('odometer', 0)
                    if mileage > 0:
                        mileages.append(mileage)

                except Exception as e:
                    logger.error(f"Error loading profile {profile_path}: {e}")

            # Load latest prediction data
            predictions_path = os.path.join(vehicle_path, "predictions")
            if os.path.exists(predictions_path):
                self._aggregate_predictions(predictions_path, component_healths, failure_events)

            # Load OBD readings for DTC patterns
            obd_path = os.path.join(vehicle_path, "obd_readings")
            if os.path.exists(obd_path):
                self._aggregate_dtcs(obd_path, dtc_counts)

        # Calculate statistics
        stats.total_vehicles = len(vehicle_data)
        stats.active_vehicles = self._count_active_vehicles(vehicle_data)

        # Health statistics
        if health_scores:
            stats.avg_health_score = statistics.mean(health_scores)
            sorted_scores = sorted(health_scores)
            n = len(sorted_scores)
            stats.health_percentiles = {
                25: sorted_scores[int(n * 0.25)] if n > 3 else sorted_scores[0],
                50: sorted_scores[int(n * 0.50)] if n > 1 else sorted_scores[0],
                75: sorted_scores[int(n * 0.75)] if n > 3 else sorted_scores[-1],
                90: sorted_scores[int(n * 0.90)] if n > 9 else sorted_scores[-1]
            }

        # Component statistics
        for component, healths in component_healths.items():
            if healths:
                stats.component_health_avgs[component] = statistics.mean(healths)
                # Calculate failure rate (health < 50%)
                failures = sum(1 for h in healths if h < 50)
                stats.component_failure_rates[component] = failures / len(healths)

        # Common failure components (by failure rate)
        sorted_components = sorted(
            stats.component_failure_rates.items(),
            key=lambda x: x[1],
            reverse=True
        )
        stats.common_failure_components = [c[0] for c in sorted_components[:10]]

        # Mileage statistics
        if mileages:
            stats.avg_mileage = statistics.mean(mileages)

        # DTC patterns
        if dtc_counts:
            total_dtc_occurrences = sum(dtc_counts.values())
            stats.common_dtcs = [
                {"code": code, "frequency": count / stats.total_vehicles}
                for code, count in sorted(dtc_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            ]

        # Data quality score
        stats.data_quality_score = self._calculate_data_quality(stats)

        # Save aggregated statistics
        self.save_fleet_statistics(stats)

        return stats

    def _aggregate_predictions(
        self,
        predictions_path: str,
        component_healths: Dict[str, List[float]],
        failure_events: List[Dict]
    ):
        """Aggregate prediction data from a vehicle's predictions folder."""
        try:
            # Get most recent prediction file
            pred_files = sorted([
                f for f in os.listdir(predictions_path)
                if f.endswith('.json')
            ], reverse=True)

            if pred_files:
                latest_path = os.path.join(predictions_path, pred_files[0])
                with open(latest_path, 'r', encoding='utf-8') as f:
                    prediction = json.load(f)

                # Extract component health
                component_risks = prediction.get('component_risks', {})
                for component, risk in component_risks.items():
                    if component not in component_healths:
                        component_healths[component] = []
                    # Convert risk to health (1 - risk) * 100
                    health = (1 - risk) * 100
                    component_healths[component].append(health)

                # Track failure events
                failures = prediction.get('failure_detections', [])
                for failure in failures:
                    if isinstance(failure, dict):
                        failure_events.append({
                            'component': failure.get('component', ''),
                            'probability': failure.get('probability', 0),
                            'timestamp': prediction.get('timestamp', '')
                        })

        except Exception as e:
            logger.error(f"Error aggregating predictions: {e}")

    def _aggregate_dtcs(self, obd_path: str, dtc_counts: Dict[str, int]):
        """Aggregate DTC codes from OBD readings."""
        try:
            for month_dir in os.listdir(obd_path):
                month_path = os.path.join(obd_path, month_dir)
                if not os.path.isdir(month_path):
                    continue

                for reading_file in os.listdir(month_path):
                    if not reading_file.endswith('.json'):
                        continue

                    reading_path = os.path.join(month_path, reading_file)
                    try:
                        with open(reading_path, 'r', encoding='utf-8') as f:
                            reading = json.load(f)

                        dtcs = reading.get('dtcs', [])
                        for dtc in dtcs:
                            code = dtc.get('code', '') if isinstance(dtc, dict) else str(dtc)
                            if code:
                                dtc_counts[code] = dtc_counts.get(code, 0) + 1

                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Error aggregating DTCs: {e}")

    def _count_active_vehicles(self, vehicle_data: List[Dict]) -> int:
        """Count vehicles active in the last 30 days."""
        thirty_days_ago = (datetime.now() - timedelta(days=30)).timestamp()

        active = 0
        for vehicle in vehicle_data:
            last_seen = vehicle.get('last_seen_timestamp', 0)
            if last_seen > thirty_days_ago:
                active += 1

        return active

    def _calculate_data_quality(self, stats: FleetStatistics) -> float:
        """Calculate data quality score based on sample size and completeness."""
        score = 0.0

        # Sample size contribution (0-0.4)
        if stats.total_vehicles >= 100:
            score += 0.4
        elif stats.total_vehicles >= 50:
            score += 0.3
        elif stats.total_vehicles >= 20:
            score += 0.2
        elif stats.total_vehicles >= 5:
            score += 0.1

        # Active vehicles contribution (0-0.2)
        if stats.total_vehicles > 0:
            active_ratio = stats.active_vehicles / stats.total_vehicles
            score += active_ratio * 0.2

        # Health data completeness (0-0.2)
        if stats.avg_health_score > 0:
            score += 0.1
        if len(stats.health_percentiles) >= 4:
            score += 0.1

        # Component data completeness (0-0.2)
        if len(stats.component_health_avgs) >= 5:
            score += 0.2
        elif len(stats.component_health_avgs) >= 2:
            score += 0.1

        return min(1.0, score)

    def compare_vehicle_to_fleet(
        self,
        vehicle_data: Dict[str, Any],
        fleet_stats: Optional[FleetStatistics] = None
    ) -> VehicleComparison:
        """
        Compare a vehicle's health/metrics against fleet statistics.

        Returns comparison data like "Better than 73% of Patrol owners".
        """
        make = vehicle_data.get('make', '')
        model = vehicle_data.get('model', '')
        year = vehicle_data.get('year', 0)
        vehicle_id = vehicle_data.get('vehicle_id', '')

        comparison = VehicleComparison(
            vehicle_id=vehicle_id,
            make=make,
            model=model,
            year=year
        )

        # Load fleet stats if not provided
        if fleet_stats is None:
            fleet_stats = self.load_fleet_statistics(make, model, year)

        if fleet_stats is None or fleet_stats.total_vehicles < 2:
            # Not enough fleet data for comparison
            comparison.fleet_size = 0
            return comparison

        comparison.fleet_size = fleet_stats.total_vehicles

        # Calculate health percentile
        vehicle_health = vehicle_data.get('health_score', 0)
        if vehicle_health > 0 and fleet_stats.health_percentiles:
            comparison.health_percentile = self._calculate_percentile(
                vehicle_health,
                fleet_stats.health_percentiles
            )

        # Compare component health
        vehicle_components = vehicle_data.get('component_health', {})
        for component, health in vehicle_components.items():
            fleet_avg = fleet_stats.component_health_avgs.get(component)
            if fleet_avg is not None:
                if health > fleet_avg + 10:
                    comparison.better_than_fleet.append(component)
                elif health < fleet_avg - 10:
                    comparison.risk_factors.append(component)

        # Determine overall risk vs fleet
        if len(comparison.risk_factors) > len(comparison.better_than_fleet) + 1:
            comparison.risk_vs_fleet = "higher"
        elif len(comparison.better_than_fleet) > len(comparison.risk_factors) + 1:
            comparison.risk_vs_fleet = "lower"
        else:
            comparison.risk_vs_fleet = "average"

        # Add fleet common issues
        comparison.fleet_common_issues = fleet_stats.common_failure_components[:5]

        # Generate fleet-based recommendations
        comparison.fleet_based_recommendations = self._generate_fleet_recommendations(
            vehicle_data, fleet_stats, comparison
        )

        return comparison

    def _calculate_percentile(
        self,
        value: float,
        percentiles: Dict[int, float]
    ) -> float:
        """Calculate approximate percentile for a value given known percentiles."""
        # Get percentile values sorted
        known = sorted(percentiles.items())  # [(25, val), (50, val), ...]

        if not known:
            return 50.0

        # Check if below lowest or above highest
        if value <= known[0][1]:
            return float(known[0][0]) * value / known[0][1] if known[0][1] > 0 else 0
        if value >= known[-1][1]:
            return min(99.0, float(known[-1][0]) + (100 - known[-1][0]) * 0.5)

        # Interpolate between known percentiles
        for i in range(len(known) - 1):
            p1, v1 = known[i]
            p2, v2 = known[i + 1]

            if v1 <= value <= v2:
                # Linear interpolation
                ratio = (value - v1) / (v2 - v1) if v2 != v1 else 0.5
                return p1 + ratio * (p2 - p1)

        return 50.0

    def _generate_fleet_recommendations(
        self,
        vehicle_data: Dict[str, Any],
        fleet_stats: FleetStatistics,
        comparison: VehicleComparison
    ) -> List[str]:
        """Generate recommendations based on fleet learning."""
        recommendations = []

        # Warn about common fleet issues
        for component in fleet_stats.common_failure_components[:3]:
            failure_rate = fleet_stats.component_failure_rates.get(component, 0)
            if failure_rate > 0.2:
                recommendations.append(
                    f"{component.replace('_', ' ').title()} has a {int(failure_rate*100)}% "
                    f"failure rate in similar vehicles - consider preventive maintenance"
                )

        # Specific component warnings
        for component in comparison.risk_factors:
            fleet_avg = fleet_stats.component_health_avgs.get(component, 0)
            recommendations.append(
                f"Your {component.replace('_', ' ')} health is below fleet average "
                f"({int(fleet_avg)}%) - monitor closely"
            )

        # Positive reinforcement
        if comparison.health_percentile > 75:
            recommendations.append(
                f"Your vehicle is healthier than {int(comparison.health_percentile)}% "
                f"of similar vehicles - keep up the good maintenance!"
            )

        return recommendations

    def get_fleet_summary_for_display(
        self,
        make: str,
        model: str,
        year: int
    ) -> Dict[str, Any]:
        """
        Get fleet summary formatted for UI display.
        """
        stats = self.load_fleet_statistics(make, model, year)

        if stats is None:
            return {
                "available": False,
                "message": f"No fleet data available for {make} {model} {year}"
            }

        return {
            "available": True,
            "fleet_size": stats.total_vehicles,
            "active_vehicles": stats.active_vehicles,
            "avg_health": round(stats.avg_health_score, 1),
            "health_distribution": {
                "excellent": stats.health_percentiles.get(90, 0),
                "good": stats.health_percentiles.get(75, 0),
                "average": stats.health_percentiles.get(50, 0),
                "below_average": stats.health_percentiles.get(25, 0)
            },
            "common_issues": [
                {
                    "component": comp,
                    "failure_rate": round(stats.component_failure_rates.get(comp, 0) * 100, 1)
                }
                for comp in stats.common_failure_components[:5]
            ],
            "common_dtcs": stats.common_dtcs[:5],
            "data_quality": round(stats.data_quality_score * 100, 1),
            "last_updated": stats.last_updated
        }


# Singleton instance
_aggregator: Optional[FleetLearningAggregator] = None


def get_fleet_aggregator(base_path: str = "./PredictData") -> FleetLearningAggregator:
    """Get global fleet aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = FleetLearningAggregator(base_path)
    return _aggregator


def compare_to_fleet(
    vehicle_data: Dict[str, Any],
    base_path: str = "./PredictData"
) -> VehicleComparison:
    """
    Convenience function to compare a vehicle to its fleet.

    Args:
        vehicle_data: Vehicle data including make, model, year, health scores
        base_path: Base data path

    Returns:
        VehicleComparison with percentile rankings
    """
    aggregator = get_fleet_aggregator(base_path)
    return aggregator.compare_vehicle_to_fleet(vehicle_data)


def aggregate_fleet(
    make: str,
    model: str,
    year: int,
    base_path: str = "./PredictData"
) -> FleetStatistics:
    """
    Convenience function to aggregate fleet data.

    Args:
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
        base_path: Base data path

    Returns:
        Aggregated FleetStatistics
    """
    aggregator = get_fleet_aggregator(base_path)
    return aggregator.aggregate_fleet_data(make, model, year)
