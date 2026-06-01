"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Multi Vehicle Comparison

Multi-Vehicle Comparison System
Compare metrics across multiple vehicles in fleet
- Health score comparisons
- Fuel efficiency analysis
- Driving score rankings
- Maintenance cost tracking
- Trip statistics comparison
- AI prediction comparisons
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import statistics

logger = logging.getLogger(__name__)


class MultiVehicleComparison:
    """
    Fleet-wide vehicle comparison and analytics

    Comparison Categories:
    - Overall Health Rankings
    - Fuel Efficiency Leaders/Laggards
    - Driving Score Rankings
    - Maintenance Cost Analysis
    - Trip Statistics
    - AI Predictions Comparison
    """

    def __init__(self, vehicle_manager, historical_data_manager,
                 enhanced_ai=None, fuel_tracking=None,
                 driving_score_analyzer=None, trip_analytics=None):
        """
        Initialize multi-vehicle comparison system

        Args:
            vehicle_manager: VehicleProfileManager instance
            historical_data_manager: HistoricalDataManager instance
            enhanced_ai: EnhancedAILearning instance (optional)
            fuel_tracking: FuelTrackingSystem instance (optional)
            driving_score_analyzer: DrivingScoreAnalyzer instance (optional)
            trip_analytics: TripAnalytics instance (optional)
        """
        self.vehicle_manager = vehicle_manager
        self.historical_data = historical_data_manager
        self.enhanced_ai = enhanced_ai
        self.fuel_tracking = fuel_tracking
        self.driving_score = driving_score_analyzer
        self.trip_analytics = trip_analytics

        logger.info("Multi-Vehicle Comparison System initialized")

    def get_fleet_overview(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive fleet overview

        Args:
            days: Days to analyze

        Returns:
            Fleet overview with all metrics
        """
        try:
            profiles = self.vehicle_manager.get_all_profiles()

            if not profiles:
                return {'message': 'No vehicles in fleet'}

            overview = {
                'total_vehicles': len(profiles),
                'analysis_period_days': days,
                'timestamp': datetime.now().isoformat(),
                'health_overview': self._get_health_overview(profiles),
                'fuel_overview': self._get_fuel_overview(profiles, days),
                'driving_overview': self._get_driving_overview(profiles),
                'trip_overview': self._get_trip_overview(profiles, days),
                'maintenance_overview': self._get_maintenance_overview(profiles),
                'rankings': self._get_fleet_rankings(profiles, days)
            }

            return overview

        except Exception as e:
            logger.error(f"Error getting fleet overview: {e}")
            return {'error': str(e)}

    def _get_health_overview(self, profiles: List[Dict]) -> Dict[str, Any]:
        """Get fleet health overview"""
        try:
            health_scores = []
            critical_count = 0
            warning_count = 0
            healthy_count = 0

            for profile in profiles:
                profile_id = profile.get('profile_id')

                # Get latest AI health prediction
                if self.enhanced_ai:
                    # Get recent historical data
                    profile_name = profile.get('name')
                    recent_data = self.historical_data.read_profile_data(
                        profile_name, profile_id,
                        start_date=datetime.now() - timedelta(days=1)
                    )

                    if recent_data:
                        latest = recent_data[-1]
                        prediction = self.enhanced_ai.predict_health(
                            profile_name, profile_id, latest
                        )
                        health_score = prediction.get('health_score', 100)
                    else:
                        health_score = 100  # Default if no data
                else:
                    health_score = 100

                health_scores.append(health_score)

                # Categorize
                if health_score < 50:
                    critical_count += 1
                elif health_score < 75:
                    warning_count += 1
                else:
                    healthy_count += 1

            return {
                'average_health': round(statistics.mean(health_scores), 1) if health_scores else 0,
                'best_health': round(max(health_scores), 1) if health_scores else 0,
                'worst_health': round(min(health_scores), 1) if health_scores else 0,
                'critical_vehicles': critical_count,
                'warning_vehicles': warning_count,
                'healthy_vehicles': healthy_count,
                'fleet_status': self._determine_fleet_status(health_scores)
            }

        except Exception as e:
            logger.error(f"Error getting health overview: {e}")
            return {}

    def _get_fuel_overview(self, profiles: List[Dict], days: int) -> Dict[str, Any]:
        """Get fleet fuel efficiency overview"""
        try:
            if not self.fuel_tracking:
                return {'message': 'Fuel tracking not available'}

            mpg_values = []
            total_fuel_cost = 0
            total_fuel_liters = 0

            for profile in profiles:
                profile_id = profile.get('profile_id')

                # Get fuel statistics
                stats = self.fuel_tracking.calculate_fuel_statistics(profile_id, days)

                if 'avg_fuel_efficiency_mpg' in stats:
                    mpg_values.append(stats['avg_fuel_efficiency_mpg'])

                total_fuel_cost += stats.get('total_cost', 0)
                total_fuel_liters += stats.get('total_fuel_liters', 0)

            return {
                'fleet_avg_mpg': round(statistics.mean(mpg_values), 1) if mpg_values else 0,
                'best_mpg': round(max(mpg_values), 1) if mpg_values else 0,
                'worst_mpg': round(min(mpg_values), 1) if mpg_values else 0,
                'total_fuel_cost': round(total_fuel_cost, 2),
                'total_fuel_liters': round(total_fuel_liters, 2),
                'avg_cost_per_vehicle': round(total_fuel_cost / len(profiles), 2) if profiles else 0
            }

        except Exception as e:
            logger.error(f"Error getting fuel overview: {e}")
            return {}

    def _get_driving_overview(self, profiles: List[Dict]) -> Dict[str, Any]:
        """Get fleet driving score overview"""
        try:
            if not self.driving_score:
                return {'message': 'Driving score not available'}

            scores = self.driving_score.get_all_active_scores()

            if not scores:
                return {'message': 'No active driving sessions'}

            score_values = list(scores.values())

            # Count by rating
            excellent = len([s for s in score_values if s >= 90])
            good = len([s for s in score_values if 75 <= s < 90])
            fair = len([s for s in score_values if 60 <= s < 75])
            poor = len([s for s in score_values if s < 60])

            return {
                'fleet_avg_score': round(statistics.mean(score_values), 1),
                'best_score': round(max(score_values), 1),
                'worst_score': round(min(score_values), 1),
                'excellent_drivers': excellent,
                'good_drivers': good,
                'fair_drivers': fair,
                'poor_drivers': poor,
                'active_sessions': len(scores)
            }

        except Exception as e:
            logger.error(f"Error getting driving overview: {e}")
            return {}

    def _get_trip_overview(self, profiles: List[Dict], days: int) -> Dict[str, Any]:
        """Get fleet trip statistics overview"""
        try:
            if not self.trip_analytics:
                return {'message': 'Trip analytics not available'}

            total_trips = 0
            total_distance = 0
            total_duration = 0

            for profile in profiles:
                profile_id = profile.get('profile_id')
                profile_name = profile.get('name')

                stats = self.trip_analytics.get_trip_statistics(
                    profile_id, profile_name, days
                )

                total_trips += stats.get('total_trips', 0)
                total_distance += stats.get('total_distance_km', 0)
                total_duration += stats.get('total_duration_hours', 0)

            return {
                'total_trips': total_trips,
                'total_distance_km': round(total_distance, 2),
                'total_duration_hours': round(total_duration, 2),
                'avg_trips_per_vehicle': round(total_trips / len(profiles), 1) if profiles else 0,
                'avg_distance_per_vehicle': round(total_distance / len(profiles), 1) if profiles else 0
            }

        except Exception as e:
            logger.error(f"Error getting trip overview: {e}")
            return {}

    def _get_maintenance_overview(self, profiles: List[Dict]) -> Dict[str, Any]:
        """Get fleet maintenance overview from service_history database"""
        try:
            import sqlite3
            from config import get_config
            CONFIG = get_config()

            service_db = CONFIG.DATA_DIR / "service_history.db"
            if not service_db.exists():
                return {
                    'total_services': 0,
                    'total_cost': 0,
                    'avg_cost_per_vehicle': 0,
                    'vehicles_needing_service': 0
                }

            conn = sqlite3.connect(str(service_db))
            c = conn.cursor()

            # Get profile names for query
            profile_names = [p.get('name', '') for p in profiles if p.get('name')]

            if not profile_names:
                conn.close()
                return {
                    'total_services': 0,
                    'total_cost': 0,
                    'avg_cost_per_vehicle': 0,
                    'vehicles_needing_service': 0
                }

            # Build placeholders for IN clause
            placeholders = ','.join(['?' for _ in profile_names])

            # Get total services and cost
            c.execute(f'''
                SELECT COUNT(*), COALESCE(SUM(cost), 0)
                FROM service_records
                WHERE profile_name IN ({placeholders})
            ''', profile_names)
            row = c.fetchone()
            total_services = row[0] if row else 0
            total_cost = float(row[1]) if row and row[1] else 0

            # Get vehicles needing service (overdue based on expected lifespan)
            vehicles_needing_service = 0
            for profile in profiles:
                profile_name = profile.get('name', '')
                if not profile_name:
                    continue

                # Get last service for each component type
                c.execute('''
                    SELECT component_type, service_date, service_km, expected_lifespan_km
                    FROM service_records
                    WHERE profile_name = ?
                    ORDER BY service_date DESC
                ''', (profile_name,))
                services = c.fetchall()

                # Check if any service is overdue (simplified check)
                # This would ideally check against current odometer
                if services:
                    last_service = services[0]
                    service_date = datetime.fromisoformat(last_service[1]) if last_service[1] else None
                    if service_date:
                        # Check if more than expected interval has passed (time-based)
                        days_since_service = (datetime.now() - service_date).days
                        if days_since_service > 180:  # 6 months default
                            vehicles_needing_service += 1

            conn.close()

            # Calculate average cost per vehicle
            avg_cost = total_cost / len(profiles) if profiles else 0

            return {
                'total_services': total_services,
                'total_cost': round(total_cost, 2),
                'avg_cost_per_vehicle': round(avg_cost, 2),
                'vehicles_needing_service': vehicles_needing_service
            }

        except Exception as e:
            logger.error(f"Error getting maintenance overview: {e}")
            return {
                'total_services': 0,
                'total_cost': 0,
                'avg_cost_per_vehicle': 0,
                'vehicles_needing_service': 0
            }

    def _get_fleet_rankings(self, profiles: List[Dict], days: int) -> Dict[str, List]:
        """Get vehicle rankings across various metrics"""
        try:
            rankings = {
                'health_score': [],
                'fuel_efficiency': [],
                'driving_score': [],
                'most_driven': [],
                'least_issues': []
            }

            for profile in profiles:
                profile_id = profile.get('profile_id')
                profile_name = profile.get('name')

                vehicle_data = {
                    'profile_id': profile_id,
                    'name': profile_name,
                    'make': profile.get('make'),
                    'model': profile.get('model'),
                    'year': profile.get('year')
                }

                # Health score
                if self.enhanced_ai:
                    recent_data = self.historical_data.read_profile_data(
                        profile_name, profile_id,
                        start_date=datetime.now() - timedelta(days=1)
                    )
                    if recent_data:
                        latest = recent_data[-1]
                        prediction = self.enhanced_ai.predict_health(
                            profile_name, profile_id, latest
                        )
                        vehicle_data['health_score'] = prediction.get('health_score', 100)
                    else:
                        vehicle_data['health_score'] = 100
                else:
                    vehicle_data['health_score'] = 100

                rankings['health_score'].append(vehicle_data.copy())

                # Fuel efficiency
                if self.fuel_tracking:
                    stats = self.fuel_tracking.calculate_fuel_statistics(profile_id, days)
                    if 'avg_fuel_efficiency_mpg' in stats:
                        vehicle_data['mpg'] = stats['avg_fuel_efficiency_mpg']
                        rankings['fuel_efficiency'].append(vehicle_data.copy())

                # Driving score
                if self.driving_score:
                    scores = self.driving_score.get_all_active_scores()
                    if profile_id in scores:
                        vehicle_data['driving_score'] = scores[profile_id]
                        rankings['driving_score'].append(vehicle_data.copy())

                # Most driven
                if self.trip_analytics:
                    stats = self.trip_analytics.get_trip_statistics(
                        profile_id, profile_name, days
                    )
                    vehicle_data['total_distance'] = stats.get('total_distance_km', 0)
                    vehicle_data['total_trips'] = stats.get('total_trips', 0)
                    rankings['most_driven'].append(vehicle_data.copy())

            # Sort rankings
            rankings['health_score'].sort(key=lambda x: x.get('health_score', 0), reverse=True)
            rankings['fuel_efficiency'].sort(key=lambda x: x.get('mpg', 0), reverse=True)
            rankings['driving_score'].sort(key=lambda x: x.get('driving_score', 0), reverse=True)
            rankings['most_driven'].sort(key=lambda x: x.get('total_distance', 0), reverse=True)

            # Limit to top 10
            for key in rankings:
                rankings[key] = rankings[key][:10]

            return rankings

        except Exception as e:
            logger.error(f"Error getting fleet rankings: {e}")
            return {}

    def _determine_fleet_status(self, health_scores: List[float]) -> str:
        """Determine overall fleet status"""
        if not health_scores:
            return 'unknown'

        avg_health = statistics.mean(health_scores)

        if avg_health >= 85:
            return 'excellent'
        elif avg_health >= 70:
            return 'good'
        elif avg_health >= 50:
            return 'fair'
        else:
            return 'poor'

    def compare_vehicles(self, profile_ids: List[int], days: int = 30) -> Dict[str, Any]:
        """
        Compare specific vehicles head-to-head

        Args:
            profile_ids: List of profile IDs to compare
            days: Days to analyze

        Returns:
            Detailed comparison
        """
        try:
            comparisons = {
                'vehicles': [],
                'comparison_period_days': days,
                'timestamp': datetime.now().isoformat()
            }

            for profile_id in profile_ids:
                profile = self.vehicle_manager.get_profile(profile_id)
                if not profile:
                    continue

                profile_name = profile.get('name')

                vehicle_metrics = {
                    'profile_id': profile_id,
                    'name': profile_name,
                    'make': profile.get('make'),
                    'model': profile.get('model'),
                    'year': profile.get('year')
                }

                # Get all metrics
                # Health
                if self.enhanced_ai:
                    recent_data = self.historical_data.read_profile_data(
                        profile_name, profile_id,
                        start_date=datetime.now() - timedelta(days=1)
                    )
                    if recent_data:
                        latest = recent_data[-1]
                        prediction = self.enhanced_ai.predict_health(
                            profile_name, profile_id, latest
                        )
                        vehicle_metrics['health_score'] = prediction.get('health_score', 100)
                        vehicle_metrics['ai_confidence'] = prediction.get('confidence', 0)

                # Fuel
                if self.fuel_tracking:
                    fuel_stats = self.fuel_tracking.calculate_fuel_statistics(profile_id, days)
                    vehicle_metrics['fuel_efficiency_mpg'] = fuel_stats.get('avg_fuel_efficiency_mpg')
                    vehicle_metrics['fuel_cost'] = fuel_stats.get('total_cost', 0)

                # Driving
                if self.driving_score:
                    scores = self.driving_score.get_all_active_scores()
                    if profile_id in scores:
                        vehicle_metrics['driving_score'] = scores[profile_id]

                # Trips
                if self.trip_analytics:
                    trip_stats = self.trip_analytics.get_trip_statistics(
                        profile_id, profile_name, days
                    )
                    vehicle_metrics['total_trips'] = trip_stats.get('total_trips', 0)
                    vehicle_metrics['total_distance_km'] = trip_stats.get('total_distance_km', 0)
                    vehicle_metrics['avg_speed_kmh'] = trip_stats.get('avg_speed_kmh', 0)

                comparisons['vehicles'].append(vehicle_metrics)

            # Add comparative insights
            comparisons['insights'] = self._generate_comparison_insights(comparisons['vehicles'])

            return comparisons

        except Exception as e:
            logger.error(f"Error comparing vehicles: {e}")
            return {'error': str(e)}

    def _generate_comparison_insights(self, vehicles: List[Dict]) -> List[str]:
        """Generate insights from vehicle comparison"""
        insights = []

        try:
            if len(vehicles) < 2:
                return insights

            # Health comparison
            health_scores = [v.get('health_score', 0) for v in vehicles if 'health_score' in v]
            if health_scores:
                best_idx = health_scores.index(max(health_scores))
                worst_idx = health_scores.index(min(health_scores))
                insights.append(
                    f"{vehicles[best_idx]['name']} has the best health score ({health_scores[best_idx]:.1f}%), "
                    f"while {vehicles[worst_idx]['name']} has the lowest ({health_scores[worst_idx]:.1f}%)"
                )

            # Fuel efficiency
            mpg_values = [v.get('fuel_efficiency_mpg', 0) for v in vehicles if 'fuel_efficiency_mpg' in v]
            if mpg_values:
                best_idx = mpg_values.index(max(mpg_values))
                worst_idx = mpg_values.index(min(mpg_values))
                diff = mpg_values[best_idx] - mpg_values[worst_idx]
                insights.append(
                    f"{vehicles[best_idx]['name']} is most fuel efficient ({mpg_values[best_idx]:.1f} MPG), "
                    f"{diff:.1f} MPG better than {vehicles[worst_idx]['name']}"
                )

            # Driving score
            driving_scores = [v.get('driving_score', 0) for v in vehicles if 'driving_score' in v]
            if driving_scores:
                best_idx = driving_scores.index(max(driving_scores))
                insights.append(
                    f"{vehicles[best_idx]['name']} has the best driving score ({driving_scores[best_idx]:.1f}/100)"
                )

            # Most driven
            distances = [v.get('total_distance_km', 0) for v in vehicles if 'total_distance_km' in v]
            if distances:
                most_idx = distances.index(max(distances))
                insights.append(
                    f"{vehicles[most_idx]['name']} has been driven the most ({distances[most_idx]:.1f} km)"
                )

        except Exception as e:
            logger.error(f"Error generating insights: {e}")

        return insights

    def get_brand_comparison(self, days: int = 30) -> Dict[str, Any]:
        """
        Compare vehicles grouped by brand

        Args:
            days: Days to analyze

        Returns:
            Brand-level comparison
        """
        try:
            profiles = self.vehicle_manager.get_all_profiles()

            # Group by brand
            brands = {}
            for profile in profiles:
                brand = profile.get('make', 'Unknown')
                if brand not in brands:
                    brands[brand] = []
                brands[brand].append(profile)

            # Compare brands
            brand_comparison = {}

            for brand, brand_profiles in brands.items():
                brand_data = {
                    'vehicle_count': len(brand_profiles),
                    'health_scores': [],
                    'fuel_mpg': [],
                    'driving_scores': []
                }

                for profile in brand_profiles:
                    profile_id = profile.get('profile_id')
                    profile_name = profile.get('name')

                    # Health
                    if self.enhanced_ai:
                        recent_data = self.historical_data.read_profile_data(
                            profile_name, profile_id,
                            start_date=datetime.now() - timedelta(days=1)
                        )
                        if recent_data:
                            latest = recent_data[-1]
                            prediction = self.enhanced_ai.predict_health(
                                profile_name, profile_id, latest
                            )
                            brand_data['health_scores'].append(prediction.get('health_score', 100))

                    # Fuel
                    if self.fuel_tracking:
                        fuel_stats = self.fuel_tracking.calculate_fuel_statistics(profile_id, days)
                        if 'avg_fuel_efficiency_mpg' in fuel_stats:
                            brand_data['fuel_mpg'].append(fuel_stats['avg_fuel_efficiency_mpg'])

                    # Driving
                    if self.driving_score:
                        scores = self.driving_score.get_all_active_scores()
                        if profile_id in scores:
                            brand_data['driving_scores'].append(scores[profile_id])

                # Calculate averages
                brand_comparison[brand] = {
                    'vehicle_count': brand_data['vehicle_count'],
                    'avg_health': round(statistics.mean(brand_data['health_scores']), 1) if brand_data['health_scores'] else 0,
                    'avg_mpg': round(statistics.mean(brand_data['fuel_mpg']), 1) if brand_data['fuel_mpg'] else 0,
                    'avg_driving_score': round(statistics.mean(brand_data['driving_scores']), 1) if brand_data['driving_scores'] else 0
                }

            return {
                'brands': brand_comparison,
                'total_brands': len(brands),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting brand comparison: {e}")
            return {'error': str(e)}
