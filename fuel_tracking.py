"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Fuel Tracking

Fuel Tracking System
- Track fuel fillups manually entered by user
- Calculate real MPG from fillups
- Compare with OBD-reported MPG
- Detect fuel consumption anomalies
- Provide fuel cost tracking
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import statistics

logger = logging.getLogger(__name__)


class FuelTrackingSystem:
    """
    Comprehensive fuel tracking and analysis

    Features:
    - Manual fillup logging
    - Real MPG calculation (distance / fuel)
    - OBD MPG estimation (from fuel consumption PID)
    - Comparison and accuracy analysis
    - Cost tracking
    - Fuel efficiency trends
    """

    def __init__(self, storage_path=None):
        """Initialize fuel tracking system"""
        from config import get_config
        CONFIG = get_config()
        
        self.storage_path = storage_path if storage_path else str(CONFIG.DATA_DIR / "fuel_data")
        os.makedirs(self.storage_path, exist_ok=True)

        # Conversion constants
        self.LITERS_PER_GALLON = 3.78541
        self.KM_PER_MILE = 1.60934

        logger.info("Fuel Tracking System initialized")

    def log_fillup(self, profile_id: int, profile_name: str,
                  liters: float, cost: float, odometer_km: float,
                  full_tank: bool = True, fuel_grade: str = 'Regular',
                  station_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Log a fuel fillup

        Args:
            profile_id: Vehicle profile ID
            profile_name: Profile name
            liters: Liters of fuel added
            cost: Total cost
            odometer_km: Current odometer reading in km
            full_tank: Whether tank was filled to full
            fuel_grade: Fuel grade (Regular, Premium, Diesel)
            station_name: Gas station name

        Returns:
            Fillup data with calculated metrics
        """
        try:
            fillup_id = f"fillup_{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            fillup_data = {
                'fillup_id': fillup_id,
                'profile_id': profile_id,
                'profile_name': profile_name,
                'timestamp': datetime.now().isoformat(),
                'liters': round(liters, 2),
                'gallons': round(liters / self.LITERS_PER_GALLON, 2),
                'cost': round(cost, 2),
                'cost_per_liter': round(cost / liters, 3),
                'odometer_km': round(odometer_km, 2),
                'odometer_miles': round(odometer_km / self.KM_PER_MILE, 2),
                'full_tank': full_tank,
                'fuel_grade': fuel_grade,
                'station_name': station_name
            }

            # Calculate MPG/L per 100km if previous fillup exists
            previous_fillup = self._get_last_fillup(profile_id)

            if previous_fillup and full_tank and previous_fillup.get('full_tank'):
                # Calculate real fuel consumption
                distance_km = odometer_km - previous_fillup['odometer_km']
                fuel_used_liters = previous_fillup['liters']  # Fuel used since last fillup

                if distance_km > 0 and fuel_used_liters > 0:
                    # Calculate fuel efficiency
                    l_per_100km = (fuel_used_liters / distance_km) * 100
                    mpg = (distance_km / self.KM_PER_MILE) / (fuel_used_liters / self.LITERS_PER_GALLON)

                    fillup_data['calculated_metrics'] = {
                        'distance_since_last_km': round(distance_km, 2),
                        'distance_since_last_miles': round(distance_km / self.KM_PER_MILE, 2),
                        'fuel_consumed_liters': round(fuel_used_liters, 2),
                        'fuel_consumed_gallons': round(fuel_used_liters / self.LITERS_PER_GALLON, 2),
                        'fuel_efficiency_l_per_100km': round(l_per_100km, 2),
                        'fuel_efficiency_mpg': round(mpg, 2),
                        'cost_per_km': round(previous_fillup['cost'] / distance_km, 3),
                        'cost_per_mile': round(previous_fillup['cost'] / (distance_km / self.KM_PER_MILE), 3)
                    }

                    logger.info(f"Fuel efficiency calculated: {mpg:.2f} MPG ({l_per_100km:.2f} L/100km)")

            # Save fillup
            self._save_fillup(profile_id, fillup_data)

            logger.info(f"Fillup logged: {liters}L at {odometer_km}km for {profile_name}")

            return {
                'success': True,
                'fillup_data': fillup_data
            }

        except Exception as e:
            logger.error(f"Error logging fillup: {e}")
            return {'success': False, 'error': str(e)}

    def _save_fillup(self, profile_id: int, fillup_data: Dict[str, Any]):
        """Save fillup to storage"""
        try:
            fillup_file = os.path.join(self.storage_path, f'profile_{profile_id}_fillups.jsonl')

            # Append to JSONL file
            with open(fillup_file, 'a', encoding='utf-8') as f:
                json.dump(fillup_data, f, ensure_ascii=False)
                f.write('\n')

        except Exception as e:
            logger.error(f"Error saving fillup: {e}")

    def _get_last_fillup(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get last fillup for profile"""
        try:
            fillup_file = os.path.join(self.storage_path, f'profile_{profile_id}_fillups.jsonl')

            if not os.path.exists(fillup_file):
                return None

            # Read last line
            with open(fillup_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                return None

            # Parse last fillup
            last_fillup = json.loads(lines[-1])
            return last_fillup

        except Exception as e:
            logger.error(f"Error getting last fillup: {e}")
            return None

    def get_fillup_history(self, profile_id: int, days: int = 90) -> List[Dict[str, Any]]:
        """Get fillup history for profile"""
        try:
            fillup_file = os.path.join(self.storage_path, f'profile_{profile_id}_fillups.jsonl')

            if not os.path.exists(fillup_file):
                return []

            # Load fillups
            fillups = []
            cutoff_date = datetime.now() - timedelta(days=days)

            with open(fillup_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        fillup = json.loads(line)
                        fillup_time = datetime.fromisoformat(fillup['timestamp'])

                        if fillup_time >= cutoff_date:
                            fillups.append(fillup)

            # Sort by timestamp (most recent first)
            fillups.sort(key=lambda x: x['timestamp'], reverse=True)

            return fillups

        except Exception as e:
            logger.error(f"Error getting fillup history: {e}")
            return []

    def calculate_fuel_statistics(self, profile_id: int, days: int = 90) -> Dict[str, Any]:
        """Calculate fuel statistics over period"""
        try:
            fillups = self.get_fillup_history(profile_id, days)

            if len(fillups) < 2:
                return {
                    'message': 'Insufficient data (need at least 2 fillups)',
                    'fillup_count': len(fillups)
                }

            # Extract calculated metrics
            efficiencies_mpg = []
            efficiencies_l100 = []
            costs_per_km = []
            total_fuel = 0
            total_cost = 0

            for fillup in fillups:
                metrics = fillup.get('calculated_metrics', {})

                if metrics:
                    if 'fuel_efficiency_mpg' in metrics:
                        efficiencies_mpg.append(metrics['fuel_efficiency_mpg'])
                    if 'fuel_efficiency_l_per_100km' in metrics:
                        efficiencies_l100.append(metrics['fuel_efficiency_l_per_100km'])
                    if 'cost_per_km' in metrics:
                        costs_per_km.append(metrics['cost_per_km'])

                total_fuel += fillup['liters']
                total_cost += fillup['cost']

            # Calculate averages
            stats = {
                'period_days': days,
                'fillup_count': len(fillups),
                'total_fuel_liters': round(total_fuel, 2),
                'total_fuel_gallons': round(total_fuel / self.LITERS_PER_GALLON, 2),
                'total_cost': round(total_cost, 2),
                'avg_cost_per_liter': round(total_cost / total_fuel, 3) if total_fuel > 0 else 0
            }

            if efficiencies_mpg:
                stats['avg_fuel_efficiency_mpg'] = round(statistics.mean(efficiencies_mpg), 2)
                stats['best_mpg'] = round(max(efficiencies_mpg), 2)
                stats['worst_mpg'] = round(min(efficiencies_mpg), 2)

            if efficiencies_l100:
                stats['avg_fuel_efficiency_l_per_100km'] = round(statistics.mean(efficiencies_l100), 2)
                stats['best_l_per_100km'] = round(min(efficiencies_l100), 2)  # Lower is better
                stats['worst_l_per_100km'] = round(max(efficiencies_l100), 2)

            if costs_per_km:
                stats['avg_cost_per_km'] = round(statistics.mean(costs_per_km), 3)

            return stats

        except Exception as e:
            logger.error(f"Error calculating fuel statistics: {e}")
            return {'error': str(e)}

    def compare_obd_vs_real(self, profile_id: int, obd_mpg: float) -> Dict[str, Any]:
        """
        Compare OBD-reported MPG with real fillup-based MPG

        Args:
            profile_id: Profile ID
            obd_mpg: MPG reported by OBD system

        Returns:
            Comparison analysis
        """
        try:
            # Get recent fillup-based MPG
            fillups = self.get_fillup_history(profile_id, days=30)

            real_mpgs = []
            for fillup in fillups:
                metrics = fillup.get('calculated_metrics', {})
                if 'fuel_efficiency_mpg' in metrics:
                    real_mpgs.append(metrics['fuel_efficiency_mpg'])

            if not real_mpgs:
                return {
                    'status': 'insufficient_data',
                    'message': 'No real MPG data available for comparison'
                }

            avg_real_mpg = statistics.mean(real_mpgs)
            difference = obd_mpg - avg_real_mpg
            percent_difference = (difference / avg_real_mpg) * 100

            # Determine accuracy
            if abs(percent_difference) < 5:
                accuracy = 'Excellent'
                message = 'OBD readings are very accurate'
            elif abs(percent_difference) < 10:
                accuracy = 'Good'
                message = 'OBD readings are reasonably accurate'
            elif abs(percent_difference) < 20:
                accuracy = 'Fair'
                message = 'OBD readings show some deviation'
            else:
                accuracy = 'Poor'
                message = 'OBD readings significantly differ from real consumption'

            return {
                'obd_mpg': round(obd_mpg, 2),
                'real_mpg_avg': round(avg_real_mpg, 2),
                'difference_mpg': round(difference, 2),
                'percent_difference': round(percent_difference, 1),
                'accuracy': accuracy,
                'message': message,
                'sample_count': len(real_mpgs)
            }

        except Exception as e:
            logger.error(f"Error comparing OBD vs real MPG: {e}")
            return {'error': str(e)}

    def estimate_range(self, profile_id: int, current_fuel_level_pct: float,
                      tank_capacity_liters: float = 60) -> Dict[str, Any]:
        """
        Estimate remaining range based on fuel level and historical consumption

        Args:
            profile_id: Profile ID
            current_fuel_level_pct: Current fuel level (0-100)
            tank_capacity_liters: Tank capacity in liters

        Returns:
            Range estimate
        """
        try:
            stats = self.calculate_fuel_statistics(profile_id, days=30)

            if 'avg_fuel_efficiency_l_per_100km' not in stats:
                return {
                    'status': 'insufficient_data',
                    'message': 'Not enough data to estimate range'
                }

            # Calculate remaining fuel
            remaining_fuel_liters = (current_fuel_level_pct / 100) * tank_capacity_liters

            # Calculate range
            l_per_100km = stats['avg_fuel_efficiency_l_per_100km']
            estimated_range_km = (remaining_fuel_liters / l_per_100km) * 100

            # Reserve range (assuming 10% reserve)
            reserve_range_km = estimated_range_km * 0.9

            return {
                'current_fuel_level_pct': current_fuel_level_pct,
                'remaining_fuel_liters': round(remaining_fuel_liters, 2),
                'remaining_fuel_gallons': round(remaining_fuel_liters / self.LITERS_PER_GALLON, 2),
                'estimated_range_km': round(estimated_range_km, 1),
                'estimated_range_miles': round(estimated_range_km / self.KM_PER_MILE, 1),
                'safe_range_km': round(reserve_range_km, 1),
                'safe_range_miles': round(reserve_range_km / self.KM_PER_MILE, 1),
                'avg_consumption_l_per_100km': l_per_100km
            }

        except Exception as e:
            logger.error(f"Error estimating range: {e}")
            return {'error': str(e)}

    def detect_fuel_anomalies(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Detect unusual fuel consumption patterns

        Returns:
            List of anomalies detected
        """
        try:
            fillups = self.get_fillup_history(profile_id, days=90)
            anomalies = []

            if len(fillups) < 5:
                return anomalies

            # Get MPG values
            mpg_values = []
            for fillup in fillups:
                metrics = fillup.get('calculated_metrics', {})
                if 'fuel_efficiency_mpg' in metrics:
                    mpg_values.append({
                        'mpg': metrics['fuel_efficiency_mpg'],
                        'timestamp': fillup['timestamp'],
                        'fillup_id': fillup['fillup_id']
                    })

            if len(mpg_values) < 5:
                return anomalies

            # Calculate mean and standard deviation
            mpgs = [v['mpg'] for v in mpg_values]
            mean_mpg = statistics.mean(mpgs)
            std_mpg = statistics.stdev(mpgs) if len(mpgs) > 1 else 0

            # Detect outliers (> 2 standard deviations)
            for mpg_data in mpg_values:
                mpg = mpg_data['mpg']
                deviation = abs(mpg - mean_mpg)

                if std_mpg > 0 and deviation > (2 * std_mpg):
                    # Anomaly detected
                    if mpg > mean_mpg:
                        anomaly_type = 'unusually_high_efficiency'
                        severity = 'info'
                    else:
                        anomaly_type = 'unusually_low_efficiency'
                        severity = 'warning'

                    anomalies.append({
                        'type': anomaly_type,
                        'severity': severity,
                        'mpg': round(mpg, 2),
                        'expected_mpg': round(mean_mpg, 2),
                        'deviation': round(deviation, 2),
                        'timestamp': mpg_data['timestamp'],
                        'fillup_id': mpg_data['fillup_id']
                    })

            logger.info(f"Detected {len(anomalies)} fuel consumption anomalies")

            return anomalies

        except Exception as e:
            logger.error(f"Error detecting fuel anomalies: {e}")
            return []

    def get_fuel_cost_report(self, profile_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate fuel cost report"""
        try:
            fillups = self.get_fillup_history(profile_id, days)

            if not fillups:
                return {'message': 'No fillup data available'}

            # Calculate totals
            total_spent = sum(f['cost'] for f in fillups)
            total_fuel = sum(f['liters'] for f in fillups)

            # Group by fuel grade
            by_grade = {}
            for fillup in fillups:
                grade = fillup.get('fuel_grade', 'Unknown')
                if grade not in by_grade:
                    by_grade[grade] = {'count': 0, 'liters': 0, 'cost': 0}

                by_grade[grade]['count'] += 1
                by_grade[grade]['liters'] += fillup['liters']
                by_grade[grade]['cost'] += fillup['cost']

            # Daily average
            daily_avg = total_spent / days if days > 0 else 0

            return {
                'period_days': days,
                'fillup_count': len(fillups),
                'total_spent': round(total_spent, 2),
                'total_fuel_liters': round(total_fuel, 2),
                'avg_cost_per_liter': round(total_spent / total_fuel, 3) if total_fuel > 0 else 0,
                'daily_avg_cost': round(daily_avg, 2),
                'monthly_estimate': round(daily_avg * 30, 2),
                'by_fuel_grade': by_grade
            }

        except Exception as e:
            logger.error(f"Error generating fuel cost report: {e}")
            return {'error': str(e)}


# ============================================================================
# ADAPTER METHODS - For compatibility with fuel_tracking_tab.py
# ============================================================================

    def get_fuel_entries(self, profile_id: int = 1, days: int = 90) -> List[Dict[str, Any]]:
        """
        Get fuel entries in format expected by fuel_tracking_tab.py
        
        Args:
            profile_id: Vehicle profile ID (defaults to 1)
            days: Number of days to look back (defaults to 90)
            
        Returns:
            List of fuel entries with expected keys
        """
        fillups = self.get_fillup_history(profile_id, days)
        
        # Transform to format expected by tab
        entries = []
        for fillup in fillups:
            metrics = fillup.get('calculated_metrics', {})
            entry = {
                'date': fillup.get('timestamp', '')[:10],  # YYYY-MM-DD
                'gallons': fillup.get('gallons', 0),
                'price_per_gallon': round(fillup.get('cost', 0) / fillup.get('gallons', 1), 3) if fillup.get('gallons', 0) > 0 else 0,
                'total_cost': fillup.get('cost', 0),
                'odometer': fillup.get('odometer_miles', 0),
                'mpg': metrics.get('fuel_efficiency_mpg', 0),
                'station': fillup.get('station_name', ''),
                'fuel_type': fillup.get('fuel_grade', 'Regular'),
                'notes': '',
                'fillup_id': fillup.get('fillup_id', '')
            }
            entries.append(entry)
        
        return entries

    def add_fuel_entry(self, entry_data: Dict[str, Any], profile_id: int = 1,
                        profile_name: str = "Default Vehicle") -> Dict[str, Any]:
        """
        Add fuel entry from tab format
        
        Args:
            entry_data: Entry data from tab with keys: date, gallons, price_per_gallon,
                       total_cost, odometer, station
            profile_id: Vehicle profile ID
            profile_name: Vehicle profile name
            
        Returns:
            Result dict with success status
        """
        try:
            # Convert from tab format to backend format
            date_obj = datetime.fromisoformat(entry_data.get('date', ''))
            odometer_km = entry_data.get('odometer', 0) * self.KM_PER_MILE
            gallons = entry_data.get('gallons', 0)
            liters = gallons * self.LITERS_PER_GALLON
            cost = entry_data.get('total_cost', 0)
            
            # Log fillup using existing method
            result = self.log_fillup(
                profile_id=profile_id,
                profile_name=profile_name,
                liters=liters,
                cost=cost,
                odometer_km=odometer_km,
                full_tank=True,  # Assume full tank for manual entries
                fuel_grade=entry_data.get('fuel_type', 'Regular'),
                station_name=entry_data.get('station', None)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding fuel entry: {e}")
            return {'success': False, 'error': str(e)}

    def get_fuel_statistics(self, profile_id: int = 1) -> Dict[str, Any]:
        """
        Get fuel statistics for tab
        
        Args:
            profile_id: Vehicle profile ID
            
        Returns:
            Statistics dict with keys expected by tab
        """
        stats = self.calculate_fuel_statistics(profile_id, days=90)
        
        # Transform to format expected by tab
        return {
            'average_mpg': stats.get('avg_fuel_efficiency_mpg', 0),
            'total_cost': stats.get('total_cost', 0),
            'total_gallons': stats.get('total_fuel_gallons', 0),
            'cost_per_mile': stats.get('avg_cost_per_km', 0) / self.KM_PER_MILE if stats.get('avg_cost_per_km') else 0,
            'fillup_count': stats.get('fillup_count', 0)
        }

    def get_monthly_spending(self, profile_id: int = 1) -> Dict[str, Any]:
        """
        Get monthly fuel spending
        
        Args:
            profile_id: Vehicle profile ID
            
        Returns:
            Monthly spending data
        """
        report = self.get_fuel_cost_report(profile_id, days=30)
        return report


# Singleton instance for easy access
_fuel_system = None

def get_fuel_system() -> FuelTrackingSystem:
    """Get singleton fuel tracking system instance"""
    global _fuel_system
    if _fuel_system is None:
        _fuel_system = FuelTrackingSystem()
    return _fuel_system
