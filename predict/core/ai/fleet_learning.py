"""
Fleet learning - cross-vehicle comparison and aggregation.

Compares individual vehicle performance against fleet averages
to identify outliers and predict failures based on fleet data.
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from sqlalchemy import select, func

from predict.core.db.session import get_db_session
from predict.core.db.models.vehicle import VehicleProfile
from predict.core.db.models.prediction import Prediction, FleetBaseline
from predict.core.config import get_config

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
    last_updated: float = 0.0
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
            last_updated=data.get('last_updated', 0.0),
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


@dataclass
class FleetHealthTrend:
    """Trend data for fleet health over time."""

    make: str
    model: str
    year: int

    # Time series data
    timestamps: List[float] = field(default_factory=list)
    health_scores: List[float] = field(default_factory=list)
    active_vehicle_counts: List[int] = field(default_factory=list)

    # Trend analysis
    health_trend_direction: str = "stable"  # "improving", "stable", "declining"
    health_trend_slope: float = 0.0  # Change per month
    predicted_health_next_month: float = 0.0

    # Component trends
    component_trends: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Issue trends
    emerging_issues: List[str] = field(default_factory=list)  # Components with increasing failure rates
    improving_areas: List[str] = field(default_factory=list)  # Components with decreasing failure rates

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FleetLearningAggregator:
    """
    Aggregates and analyzes data across vehicle fleets.
    
    Enables comparison of individual vehicles against fleet averages
    for the same make/model/year to identify outliers.
    """
    
    def __init__(self):
        self.config = get_config()
    
    async def get_fleet_comparison(
        self,
        profile_id: int,
        component: str,
        value: float,
    ) -> Dict[str, Any]:
        """
        Compare a vehicle's component value against fleet average.
        
        Args:
            profile_id: Vehicle profile ID
            component: Component/sensor name
            value: Current value to compare
        
        Returns:
            Comparison metrics including percentile rank
        """
        async with get_db_session() as session:
            # Get vehicle info
            stmt = select(VehicleProfile).where(VehicleProfile.profile_id == profile_id)
            result = await session.execute(stmt)
            vehicle = result.scalar_one_or_none()
            
            if not vehicle:
                return {'error': 'Vehicle not found'}
            
            # Get fleet stats
            fleet_stats = await self.aggregate_fleet_stats(
                vehicle.make, vehicle.model, vehicle.year
            )
            
            if component not in fleet_stats:
                return {
                    'component': component,
                    'value': value,
                    'fleet_comparison': 'no_data',
                }
            
            stats = fleet_stats[component]
            
            # Calculate percentile
            if stats['std'] > 0:
                z_score = (value - stats['mean']) / stats['std']
                # Approximate percentile from Z-score
                percentile = 50 + 34 * z_score  # Rough approximation
                percentile = max(0, min(100, percentile))
            else:
                percentile = 50
            
            # Determine status
            if percentile < 10:
                status = 'excellent'
            elif percentile < 25:
                status = 'good'
            elif percentile < 75:
                status = 'average'
            elif percentile < 90:
                status = 'below_average'
            else:
                status = 'poor'
            
            return {
                'component': component,
                'value': value,
                'fleet_mean': stats['mean'],
                'fleet_std': stats['std'],
                'percentile': float(percentile),
                'status': status,
                'sample_size': stats['count'],
                'comparison': f"Your {component} is {status.replace('_', ' ')} compared to similar vehicles",
            }
    
    async def aggregate_fleet_stats(
        self,
        make: str,
        model: str,
        year: int,
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate fleet statistics for a vehicle type.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
        
        Returns:
            Dict mapping components to statistics
        """
        async with get_db_session() as session:
            # Get all predictions for this vehicle type
            stmt = (
                select(Prediction)
                .join(VehicleProfile)
                .where(
                    VehicleProfile.make == make,
                    VehicleProfile.model == model,
                    VehicleProfile.year == year,
                )
            )
            result = await session.execute(stmt)
            predictions = result.scalars().all()
            
            if not predictions:
                return {}
            
            # Aggregate by component
            component_values = {}
            for pred in predictions:
                comp = pred.component
                if comp not in component_values:
                    component_values[comp] = []
                component_values[comp].append(pred.health_score)
            
            # Calculate stats
            stats = {}
            for comp, values in component_values.items():
                arr = np.array(values)
                stats[comp] = {
                    'mean': float(np.mean(arr)),
                    'std': float(np.std(arr)),
                    'min': float(np.min(arr)),
                    'max': float(np.max(arr)),
                    'median': float(np.median(arr)),
                    'count': len(values),
                }
            
            return stats
    
    async def get_fleet_statistics(
        self,
        make: str,
        model: str,
        year: int,
    ) -> FleetStatistics:
        """
        Get comprehensive fleet statistics for a make/model/year.
        
        This aggregates cross-vehicle patterns including health scores,
        failure rates, DTC patterns, and more.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
        
        Returns:
            FleetStatistics with aggregated data
        """
        stats = FleetStatistics(make=make, model=model, year=year)
        
        async with get_db_session() as session:
            # Get all vehicles of this type
            stmt = select(VehicleProfile).where(
                VehicleProfile.make == make,
                VehicleProfile.model == model,
                VehicleProfile.year == year,
            )
            result = await session.execute(stmt)
            vehicles = result.scalars().all()
            
            stats.total_vehicles = len(vehicles)
            
            if not vehicles:
                return stats
            
            # Count active vehicles (seen in last 30 days)
            thirty_days_ago = time.time() - (30 * 24 * 3600)
            stats.active_vehicles = sum(
                1 for v in vehicles 
                if v.last_seen and v.last_seen > thirty_days_ago
            )
            
            # Get all predictions for these vehicles
            vehicle_ids = [v.profile_id for v in vehicles]
            stmt = select(Prediction).where(
                Prediction.profile_id.in_(vehicle_ids),
                Prediction.status == "active",
            )
            result = await session.execute(stmt)
            predictions = result.scalars().all()

            # Derive health scores from failure_probability (1.0 = perfect health)
            health_scores = [(1.0 - p.failure_probability) for p in predictions if p.failure_probability < 1.0]
            if health_scores:
                stats.avg_health_score = float(np.mean(health_scores))
                sorted_scores = sorted(health_scores)
                n = len(sorted_scores)
                stats.health_percentiles = {
                    25: sorted_scores[int(n * 0.25)] if n > 3 else sorted_scores[0],
                    50: sorted_scores[int(n * 0.50)] if n > 1 else sorted_scores[0],
                    75: sorted_scores[int(n * 0.75)] if n > 3 else sorted_scores[-1],
                    90: sorted_scores[int(n * 0.90)] if n > 9 else sorted_scores[-1]
                }
            
            # Aggregate by component
            component_healths = {}
            component_failures = {}
            
            for pred in predictions:
                comp = pred.component
                if comp not in component_healths:
                    component_healths[comp] = []
                    component_failures[comp] = {'total': 0, 'failures': 0}
                
                component_healths[comp].append(pred.health_score)
                component_failures[comp]['total'] += 1
                if pred.failure_probability > 0.7:
                    component_failures[comp]['failures'] += 1
            
            # Calculate component averages and failure rates
            for comp, healths in component_healths.items():
                if healths:
                    stats.component_health_avgs[comp] = float(np.mean(healths))
                    
                    # Calculate failure rate
                    failure_data = component_failures.get(comp, {'total': 0, 'failures': 0})
                    if failure_data['total'] > 0:
                        stats.component_failure_rates[comp] = (
                            failure_data['failures'] / failure_data['total']
                        )
            
            # Sort components by failure rate for common failures
            sorted_components = sorted(
                stats.component_failure_rates.items(),
                key=lambda x: x[1],
                reverse=True
            )
            stats.common_failure_components = [c[0] for c in sorted_components[:10]]
            
            # Calculate average mileage
            mileages = [v.current_mileage for v in vehicles if v.current_mileage and v.current_mileage > 0]
            if mileages:
                stats.avg_mileage = float(np.mean(mileages))
            
            # Calculate average age
            current_time = time.time()
            ages = []
            for v in vehicles:
                if v.created_at and v.created_at > 0:
                    age_years = (current_time - v.created_at) / (365 * 24 * 3600)
                    ages.append(age_years)
            if ages:
                stats.avg_age_years = float(np.mean(ages))
            
            # Calculate data quality score
            stats.data_quality_score = self._calculate_data_quality(stats)
            stats.last_updated = time.time()
            
            logger.info(f"Aggregated fleet statistics for {make} {model} {year}: "
                       f"{stats.total_vehicles} vehicles, "
                       f"avg health {stats.avg_health_score:.1f}")
            
            return stats
    
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
    
    async def compare_vehicle_to_fleet(
        self,
        profile_id: int,
    ) -> VehicleComparison:
        """
        Compare a vehicle's health/metrics against fleet statistics.
        
        Returns comparison data like "Better than 73% of Patrol owners".
        """
        comparison = VehicleComparison(
            vehicle_id=str(profile_id),
            make="",
            model="",
            year=0
        )
        
        async with get_db_session() as session:
            # Get vehicle info
            stmt = select(VehicleProfile).where(VehicleProfile.profile_id == profile_id)
            result = await session.execute(stmt)
            vehicle = result.scalar_one_or_none()
            
            if not vehicle:
                return comparison
            
            comparison.make = vehicle.make
            comparison.model = vehicle.model
            comparison.year = vehicle.year
            comparison.vehicle_id = str(vehicle.profile_id)
            
            # Get fleet statistics
            fleet_stats = await self.get_fleet_statistics(
                vehicle.make, vehicle.model, vehicle.year
            )
            
            if fleet_stats.total_vehicles < 2:
                comparison.fleet_size = 0
                return comparison
            
            comparison.fleet_size = fleet_stats.total_vehicles
            
            # Get vehicle's latest predictions
            stmt = select(Prediction).where(
                Prediction.profile_id == profile_id,
                Prediction.status == "active",
            )
            result = await session.execute(stmt)
            predictions = result.scalars().all()

            # Derive health scores from failure_probability (1.0 = perfect health)
            vehicle_healths = [(1.0 - p.failure_probability) for p in predictions if p.failure_probability < 1.0]
            if vehicle_healths:
                avg_vehicle_health = np.mean(vehicle_healths)
                if fleet_stats.health_percentiles:
                    comparison.health_percentile = self._calculate_percentile(
                        avg_vehicle_health,
                        fleet_stats.health_percentiles
                    )
            
            # Compare component health
            for pred in predictions:
                fleet_avg = fleet_stats.component_health_avgs.get(pred.component)
                if fleet_avg is not None:
                    if pred.health_score > fleet_avg + 10:
                        comparison.better_than_fleet.append(pred.component)
                    elif pred.health_score < fleet_avg - 10:
                        comparison.risk_factors.append(pred.component)
                    
                    # Calculate component percentile
                    comparison.component_percentiles[pred.component] = self._calculate_component_percentile(
                        pred.health_score,
                        fleet_stats.health_percentiles
                    )
            
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
            comparison.fleet_based_recommendations = await self._generate_fleet_recommendations(
                vehicle, fleet_stats, comparison
            )
            
            return comparison
    
    def _calculate_percentile(
        self,
        value: float,
        percentiles: Dict[int, float]
    ) -> float:
        """Calculate approximate percentile for a value given known percentiles."""
        if not percentiles:
            return 50.0
        
        # Get percentile values sorted
        known = sorted(percentiles.items())  # [(25, val), (50, val), ...]
        
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
    
    def _calculate_component_percentile(
        self,
        health_score: float,
        fleet_percentiles: Dict[int, float]
    ) -> float:
        """Calculate component percentile based on fleet health distribution."""
        if not fleet_percentiles:
            return 50.0
        
        median = fleet_percentiles.get(50, 75)
        p25 = fleet_percentiles.get(25, median - 10)
        p75 = fleet_percentiles.get(75, median + 10)
        
        if health_score >= p75:
            return 75 + (health_score - p75) / (100 - p75) * 25 if p75 < 100 else 90
        elif health_score >= median:
            return 50 + (health_score - median) / (p75 - median) * 25 if p75 != median else 62.5
        elif health_score >= p25:
            return 25 + (health_score - p25) / (median - p25) * 25 if median != p25 else 37.5
        else:
            return health_score / p25 * 25 if p25 > 0 else 0
    
    async def _generate_fleet_recommendations(
        self,
        vehicle: VehicleProfile,
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
    
    async def get_fleet_failure_rates(
        self,
        make: str,
        model: str,
        year: int,
    ) -> Dict[str, float]:
        """
        Calculate failure rates by component for a vehicle type.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
        
        Returns:
            Dict mapping components to failure rates (0-1)
        """
        async with get_db_session() as session:
            # Get predictions and count failures
            stmt = (
                select(
                    Prediction.component,
                    func.count(Prediction.id).label('total'),
                    func.sum(func.case((Prediction.failure_probability > 0.7, 1), else_=0)).label('failures'),
                )
                .join(VehicleProfile)
                .where(
                    VehicleProfile.make == make,
                    VehicleProfile.model == model,
                    VehicleProfile.year == year,
                )
                .group_by(Prediction.component)
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            failure_rates = {}
            for row in rows:
                component = row.component
                total = row.total or 0
                failures = row.failures or 0
                
                if total > 0:
                    failure_rates[component] = float(failures / total)
                else:
                    failure_rates[component] = 0.0
            
            return failure_rates
    
    async def identify_fleet_outliers(
        self,
        profile_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Identify components where this vehicle is an outlier compared to fleet.
        
        Args:
            profile_id: Vehicle profile ID
        
        Returns:
            List of outlier components with details
        """
        async with get_db_session() as session:
            # Get vehicle info
            stmt = select(VehicleProfile).where(VehicleProfile.profile_id == profile_id)
            result = await session.execute(stmt)
            vehicle = result.scalar_one_or_none()
            
            if not vehicle:
                return []
            
            # Get latest predictions for this vehicle
            stmt = (
                select(Prediction)
                .where(Prediction.profile_id == profile_id)
                .where(Prediction.status == "active")
            )
            result = await session.execute(stmt)
            predictions = result.scalars().all()
            
            if not predictions:
                return []
            
            outliers = []
            
            for pred in predictions:
                comparison = await self.get_fleet_comparison(
                    profile_id,
                    pred.component,
                    pred.health_score,
                )
                
                # Flag as outlier if in bottom 25%
                if comparison.get('percentile', 50) < 25:
                    outliers.append({
                        'component': pred.component,
                        'health_score': pred.health_score,
                        'percentile': comparison['percentile'],
                        'fleet_average': comparison['fleet_mean'],
                        'status': comparison['status'],
                    })
            
            return sorted(outliers, key=lambda x: x['percentile'])
    
    async def get_fleet_health_trends(
        self,
        make: str,
        model: str,
        year: int,
        months: int = 6,
    ) -> FleetHealthTrend:
        """
        Get fleet health trends over time.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
            months: Number of months to analyze
        
        Returns:
            FleetHealthTrend with trend analysis
        """
        trend = FleetHealthTrend(make=make, model=model, year=year)
        
        async with get_db_session() as session:
            # Calculate time boundaries
            end_time = time.time()
            start_time = end_time - (months * 30 * 24 * 3600)
            
            # Get predictions over time
            stmt = (
                select(
                    Prediction.component,
                    Prediction.failure_probability,
                    Prediction.created_at,
                )
                .join(VehicleProfile)
                .where(
                    VehicleProfile.make == make,
                    VehicleProfile.model == model,
                    VehicleProfile.year == year,
                    Prediction.created_at >= start_time,
                )
            )
            result = await session.execute(stmt)
            raw_predictions = result.all()
            
            if not raw_predictions:
                return trend

            # Group by month (derive health_score from failure_probability)
            monthly_data = {}
            for pred in raw_predictions:
                health = round((1.0 - pred.failure_probability) * 100, 1)
                month_key = int((pred.created_at - start_time) / (30 * 24 * 3600))
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'healths': [],
                        'components': {},
                    }
                monthly_data[month_key]['healths'].append(health)

                if pred.component not in monthly_data[month_key]['components']:
                    monthly_data[month_key]['components'][pred.component] = []
                monthly_data[month_key]['components'][pred.component].append(health)
            
            # Build time series
            for month_idx in sorted(monthly_data.keys()):
                data = monthly_data[month_idx]
                trend.timestamps.append(start_time + month_idx * 30 * 24 * 3600)
                trend.health_scores.append(float(np.mean(data['healths'])))
            
            # Calculate trend direction
            if len(trend.health_scores) >= 2:
                x = np.arange(len(trend.health_scores))
                y = np.array(trend.health_scores)
                
                # Simple linear regression
                n = len(x)
                slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
                trend.health_trend_slope = float(slope)
                
                if slope > 1:
                    trend.health_trend_direction = "improving"
                elif slope < -1:
                    trend.health_trend_direction = "declining"
                else:
                    trend.health_trend_direction = "stable"
                
                # Predict next month
                next_idx = len(trend.health_scores)
                trend.predicted_health_next_month = float(
                    trend.health_scores[-1] + slope if trend.health_scores else 0
                )
            
            # Analyze component trends
            component_monthly = {}
            for pred in raw_predictions:
                health = round((1.0 - pred.failure_probability) * 100, 1)
                month_key = int((pred.created_at - start_time) / (30 * 24 * 3600))
                if pred.component not in component_monthly:
                    component_monthly[pred.component] = {}
                if month_key not in component_monthly[pred.component]:
                    component_monthly[pred.component][month_key] = []
                component_monthly[pred.component][month_key].append(health)
            
            for comp, monthly in component_monthly.items():
                if len(monthly) >= 2:
                    sorted_months = sorted(monthly.keys())
                    first_avg = np.mean(monthly[sorted_months[0]])
                    last_avg = np.mean(monthly[sorted_months[-1]])
                    
                    change = last_avg - first_avg
                    trend.component_trends[comp] = {
                        'change': float(change),
                        'direction': 'improving' if change > 1 else ('declining' if change < -1 else 'stable'),
                    }
                    
                    if change < -2:
                        trend.emerging_issues.append(comp)
                    elif change > 2:
                        trend.improving_areas.append(comp)
            
            return trend
    
    async def update_fleet_baseline(
        self,
        make: str,
        model: str,
        year: int,
    ) -> bool:
        """
        Update stored fleet baseline for a vehicle type.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
        
        Returns:
            True if updated successfully
        """
        try:
            stats = await self.aggregate_fleet_stats(make, model, year)
            
            async with get_db_session() as session:
                # Check if baseline exists
                stmt = select(FleetBaseline).where(
                    FleetBaseline.make == make,
                    FleetBaseline.model == model,
                    FleetBaseline.year == year,
                )
                result = await session.execute(stmt)
                baseline = result.scalar_one_or_none()
                
                if baseline:
                    # Update existing
                    baseline.baseline_data = stats
                    baseline.updated_at = time.time()
                else:
                    # Create new
                    baseline = FleetBaseline(
                        make=make,
                        model=model,
                        year=year,
                        baseline_data=stats,
                        created_at=time.time(),
                        updated_at=time.time(),
                    )
                    session.add(baseline)
                
                await session.commit()
                logger.info(f"Updated fleet baseline for {make} {model} {year}")
                return True
        except Exception as e:
            logger.error(f"Failed to update fleet baseline: {e}")
            return False
    
    async def get_fleet_baseline(
        self,
        make: str,
        model: str,
        year: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get stored fleet baseline for a vehicle type.
        
        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year
        
        Returns:
            Baseline data or None
        """
        async with get_db_session() as session:
            stmt = select(FleetBaseline).where(
                FleetBaseline.make == make,
                FleetBaseline.model == model,
                FleetBaseline.year == year,
            )
            result = await session.execute(stmt)
            baseline = result.scalar_one_or_none()
            
            if baseline:
                return {
                    'make': baseline.make,
                    'model': baseline.model,
                    'year': baseline.year,
                    'data': baseline.baseline_data,
                    'updated_at': baseline.updated_at,
                }
            
            return None
    
    async def get_similar_vehicles(
        self,
        profile_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find similar vehicles in the fleet.
        
        Args:
            profile_id: Reference vehicle
            limit: Max results
        
        Returns:
            List of similar vehicles
        """
        async with get_db_session() as session:
            # Get reference vehicle
            stmt = select(VehicleProfile).where(VehicleProfile.profile_id == profile_id)
            result = await session.execute(stmt)
            vehicle = result.scalar_one_or_none()
            
            if not vehicle:
                return []
            
            # Find similar
            stmt = (
                select(VehicleProfile)
                .where(
                    VehicleProfile.make == vehicle.make,
                    VehicleProfile.model == vehicle.model,
                    VehicleProfile.year == vehicle.year,
                    VehicleProfile.profile_id != profile_id,
                )
                .limit(limit)
            )
            result = await session.execute(stmt)
            similar = result.scalars().all()
            
            return [
                {
                    'id': v.profile_id,
                    'vin': v.vin,
                    'mileage': v.current_mileage,
                    'created_at': v.created_at,
                }
                for v in similar
            ]
    
    async def get_fleet_summary_for_display(
        self,
        make: str,
        model: str,
        year: int
    ) -> Dict[str, Any]:
        """
        Get fleet summary formatted for UI display.
        """
        stats = await self.get_fleet_statistics(make, model, year)
        
        if stats.total_vehicles == 0:
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


def get_fleet_aggregator() -> FleetLearningAggregator:
    """Get global fleet aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = FleetLearningAggregator()
    return _aggregator


async def compare_to_fleet(profile_id: int) -> VehicleComparison:
    """
    Convenience function to compare a vehicle to its fleet.
    
    Args:
        profile_id: Vehicle profile ID
    
    Returns:
        VehicleComparison with percentile rankings
    """
    aggregator = get_fleet_aggregator()
    return await aggregator.compare_vehicle_to_fleet(profile_id)


async def aggregate_fleet(
    make: str,
    model: str,
    year: int,
) -> FleetStatistics:
    """
    Convenience function to aggregate fleet data.
    
    Args:
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
    
    Returns:
        Aggregated FleetStatistics
    """
    aggregator = get_fleet_aggregator()
    return await aggregator.get_fleet_statistics(make, model, year)
