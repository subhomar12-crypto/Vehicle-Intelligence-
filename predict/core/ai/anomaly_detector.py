"""
Multi-method anomaly detection with context-awareness.

Combines Isolation Forest, Z-score detection, and context-aware thresholds
to identify anomalous sensor readings.
"""

import logging
from typing import Dict, Any, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Context-aware anomaly detection for vehicle OBD data.
    
    Uses multiple detection methods:
    - Isolation Forest for multivariate anomalies
    - Z-score for statistical outliers
    - Context-aware thresholds (idle/city/highway/cold_start/hot_weather)
    """
    
    def __init__(self):
        self._has_sklearn = False
        self._isolation_forest = None
        self._check_sklearn()
        
        # Context definitions with adjusted thresholds
        self.context_thresholds = self._define_context_thresholds()
    
    def _check_sklearn(self) -> None:
        """Check if scikit-learn is available."""
        try:
            from sklearn.ensemble import IsolationForest
            self._has_sklearn = True
            self._isolation_forest = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100,
            )
            logger.info("scikit-learn IsolationForest available")
        except ImportError:
            logger.warning("scikit-learn not available, using Z-score only")
            self._has_sklearn = False
    
    def _define_context_thresholds(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Define normal ranges for different vehicle contexts."""
        return {
            'idle': {
                'rpm': {'min': 600, 'max': 900, 'warning_min': 500, 'warning_max': 1000},
                'speed_kmh': {'min': 0, 'max': 5, 'warning_min': 0, 'warning_max': 10},
                'coolant_temp_c': {'min': 80, 'max': 100, 'warning_min': 70, 'warning_max': 110},
                'battery_voltage': {'min': 13.5, 'max': 14.5, 'warning_min': 12.5, 'warning_max': 15.0},
                'engine_load': {'min': 0, 'max': 20, 'warning_min': 0, 'warning_max': 30},
            },
            'city': {
                'rpm': {'min': 800, 'max': 3000, 'warning_min': 600, 'warning_max': 4000},
                'speed_kmh': {'min': 10, 'max': 60, 'warning_min': 0, 'warning_max': 80},
                'coolant_temp_c': {'min': 85, 'max': 105, 'warning_min': 75, 'warning_max': 115},
                'battery_voltage': {'min': 13.5, 'max': 14.7, 'warning_min': 12.5, 'warning_max': 15.2},
                'engine_load': {'min': 10, 'max': 60, 'warning_min': 0, 'warning_max': 80},
            },
            'highway': {
                'rpm': {'min': 1500, 'max': 3500, 'warning_min': 1200, 'warning_max': 4500},
                'speed_kmh': {'min': 60, 'max': 140, 'warning_min': 40, 'warning_max': 160},
                'coolant_temp_c': {'min': 90, 'max': 110, 'warning_min': 80, 'warning_max': 120},
                'battery_voltage': {'min': 14.0, 'max': 14.8, 'warning_min': 13.0, 'warning_max': 15.5},
                'engine_load': {'min': 30, 'max': 70, 'warning_min': 10, 'warning_max': 85},
            },
            'cold_start': {
                'rpm': {'min': 900, 'max': 1500, 'warning_min': 700, 'warning_max': 2000},
                'speed_kmh': {'min': 0, 'max': 0, 'warning_min': 0, 'warning_max': 5},
                'coolant_temp_c': {'min': 10, 'max': 60, 'warning_min': 5, 'warning_max': 80},
                'battery_voltage': {'min': 12.0, 'max': 14.5, 'warning_min': 11.0, 'warning_max': 15.0},
                'engine_load': {'min': 15, 'max': 40, 'warning_min': 10, 'warning_max': 60},
            },
            'hot_weather': {
                'rpm': {'min': 600, 'max': 6000, 'warning_min': 400, 'warning_max': 7000},
                'speed_kmh': {'min': 0, 'max': 200, 'warning_min': 0, 'warning_max': 250},
                'coolant_temp_c': {'min': 90, 'max': 120, 'warning_min': 80, 'warning_max': 130},
                'battery_voltage': {'min': 13.2, 'max': 14.5, 'warning_min': 12.0, 'warning_max': 15.0},
                'engine_load': {'min': 0, 'max': 100, 'warning_min': 0, 'warning_max': 100},
            },
        }
    
    def detect_anomalies(
        self,
        obd_data: Dict[str, float],
        profile_id: int,
        vehicle_state: str = 'city',
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect anomalies in OBD data using multiple methods.
        
        Args:
            obd_data: Current sensor readings
            profile_id: Vehicle profile ID
            vehicle_state: One of 'idle', 'city', 'highway', 'cold_start', 'hot_weather'
        
        Returns:
            Per-sensor anomaly reports
        """
        results = {}
        
        for sensor, value in obd_data.items():
            if value is None:
                continue
            
            anomaly_report = {
                'value': value,
                'is_anomalous': False,
                'score': 0.0,
                'methods_triggered': [],
            }
            
            # Method 1: Context-aware thresholds
            context_result = self._check_context_threshold(sensor, value, vehicle_state)
            if context_result['is_anomalous']:
                anomaly_report['is_anomalous'] = True
                anomaly_report['methods_triggered'].append('context_threshold')
                anomaly_report['context_severity'] = context_result['severity']
            
            # Method 2: Z-score (if we have baseline)
            # This would need vehicle baseline data
            # For now, use simple bounds
            z_result = self._simple_bounds_check(sensor, value)
            if z_result['is_anomalous']:
                anomaly_report['is_anomalous'] = True
                anomaly_report['methods_triggered'].append('bounds_check')
            
            # Calculate overall anomaly score
            anomaly_report['score'] = self._calculate_anomaly_score(
                value, sensor, vehicle_state, obd_data
            )
            
            results[sensor] = anomaly_report
        
        # Method 3: Isolation Forest for multivariate detection
        if self._has_sklearn:
            multivariate_score = self._isolation_forest_score(obd_data)
            results['_multivariate'] = {
                'is_anomalous': multivariate_score > 0.6,
                'score': multivariate_score,
                'methods_triggered': ['isolation_forest'],
            }
        
        return results
    
    def _check_context_threshold(
        self,
        sensor: str,
        value: float,
        vehicle_state: str,
    ) -> Dict[str, Any]:
        """Check value against context-specific thresholds."""
        thresholds = self.context_thresholds.get(vehicle_state, {}).get(sensor)
        
        if not thresholds:
            return {'is_anomalous': False, 'severity': 'unknown'}
        
        # Check critical thresholds
        if value < thresholds.get('warning_min', thresholds['min']):
            return {'is_anomalous': True, 'severity': 'critical_low'}
        if value > thresholds.get('warning_max', thresholds['max']):
            return {'is_anomalous': True, 'severity': 'critical_high'}
        
        # Check warning thresholds
        if value < thresholds['min']:
            return {'is_anomalous': True, 'severity': 'warning_low'}
        if value > thresholds['max']:
            return {'is_anomalous': True, 'severity': 'warning_high'}
        
        return {'is_anomalous': False, 'severity': 'normal'}
    
    def _simple_bounds_check(self, sensor: str, value: float) -> Dict[str, Any]:
        """Simple bounds check for sensors."""
        # Universal bounds for common sensors
        bounds = {
            'rpm': (0, 8000),
            'speed_kmh': (0, 300),
            'coolant_temp_c': (0, 150),
            'oil_temp_c': (0, 180),
            'battery_voltage': (8, 16),
            'engine_load': (0, 100),
            'intake_temp_c': (-40, 80),
            'maf_rate': (0, 500),
            'throttle_pos': (0, 100),
            'fuel_level': (0, 100),
        }
        
        if sensor in bounds:
            min_val, max_val = bounds[sensor]
            if value < min_val or value > max_val:
                return {'is_anomalous': True, 'bounds': bounds[sensor]}
        
        return {'is_anomalous': False}
    
    def _calculate_anomaly_score(
        self,
        value: float,
        sensor: str,
        vehicle_state: str,
        all_data: Dict[str, float],
    ) -> float:
        """Calculate overall anomaly score (0-1)."""
        scores = []
        
        # Context deviation score
        thresholds = self.context_thresholds.get(vehicle_state, {}).get(sensor)
        if thresholds:
            mid = (thresholds['min'] + thresholds['max']) / 2
            range_val = thresholds['max'] - thresholds['min']
            if range_val > 0:
                deviation = abs(value - mid) / (range_val / 2)
                scores.append(min(1.0, deviation))
        
        # Cross-sensor consistency score
        if sensor == 'rpm' and 'speed_kmh' in all_data:
            speed = all_data['speed_kmh']
            if speed > 10:  # Moving
                expected_rpm = speed * 30  # Rough estimate
                rpm_deviation = abs(value - expected_rpm) / expected_rpm if expected_rpm > 0 else 0
                scores.append(min(1.0, rpm_deviation))
        
        return np.mean(scores) if scores else 0.0
    
    def _isolation_forest_score(self, data: Dict[str, float]) -> float:
        """
        Get multivariate anomaly score from Isolation Forest.
        
        Returns:
            Anomaly score (higher = more anomalous)
        """
        if not self._has_sklearn or self._isolation_forest is None:
            return 0.0
        
        # Extract feature vector
        features = [
            data.get('rpm', 0),
            data.get('speed_kmh', 0),
            data.get('coolant_temp_c', 90),
            data.get('battery_voltage', 13.5),
            data.get('engine_load', 20),
            data.get('intake_temp_c', 30),
        ]
        
        try:
            # Reshape for single sample
            X = np.array([features])
            score = self._isolation_forest.score_samples(X)[0]
            # Convert to 0-1 range (higher = more anomalous)
            normalized_score = 0.5 - score / 2
            return float(np.clip(normalized_score, 0, 1))
        except Exception as e:
            logger.error(f"Isolation Forest error: {e}")
            return 0.0
    
    def _zscore_detection(
        self,
        value: float,
        baseline_mean: float,
        baseline_std: float,
    ) -> bool:
        """Z-score based anomaly detection."""
        if baseline_std == 0:
            return abs(value - baseline_mean) > 0.1
        
        z_score = abs(value - baseline_mean) / baseline_std
        return z_score > 3.0
    
    def get_context_aware_thresholds(
        self,
        vehicle_state: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        Get thresholds for a specific vehicle state.
        
        Args:
            vehicle_state: One of the defined states
        
        Returns:
            Dict of sensor thresholds
        """
        return self.context_thresholds.get(vehicle_state, {})
    
    def fit_isolation_forest(self, historical_data: List[Dict[str, float]]) -> None:
        """
        Fit Isolation Forest on historical normal data.
        
        Args:
            historical_data: List of OBD readings from normal operation
        """
        if not self._has_sklearn or not historical_data:
            return
        
        try:
            # Extract features
            features = []
            for record in historical_data:
                feat = [
                    record.get('rpm', 0),
                    record.get('speed_kmh', 0),
                    record.get('coolant_temp_c', 90),
                    record.get('battery_voltage', 13.5),
                    record.get('engine_load', 20),
                ]
                features.append(feat)
            
            X = np.array(features)
            self._isolation_forest.fit(X)
            logger.info(f"Isolation Forest fitted on {len(features)} samples")
        except Exception as e:
            logger.error(f"Failed to fit Isolation Forest: {e}")
