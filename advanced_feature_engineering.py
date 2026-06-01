"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Advanced Feature Engineering

Advanced Feature Engineering Module
===================================
Extracts maximum predictive power from OBD-II data through sophisticated feature engineering.

Features:
- Rate of change calculations (dT/dt)
- Rolling statistics (mean, std, min, max)
- Cross-sensor correlations
- Derived physics-based features
- Anomaly z-scores
- Time-based patterns
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class AdvancedFeatureEngineering:
    """
    Advanced feature engineering for predictive maintenance.
    Extracts derived features that have higher predictive power than raw sensor values.
    """

    def __init__(self, config=None):
        """Initialize feature engineering module."""
        self.config = config

        # Rolling window sizes for different calculations
        self.rolling_windows = {
            'short': 5,      # ~5 seconds for immediate trends
            'medium': 30,    # ~30 seconds for short-term patterns
            'long': 300      # ~5 minutes for medium-term trends
        }

        # Sensor data buffers for rolling calculations
        self.sensor_buffers: Dict[str, Dict[str, deque]] = {}  # vehicle_id -> sensor -> buffer

        # Baseline values per vehicle
        self.vehicle_baselines: Dict[str, Dict[str, Any]] = {}

        # Feature definitions
        self.derived_features = self._define_derived_features()

        # Storage path for baselines
        self.storage_path = CONFIG.AI_DIR / "feature_engineering"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load existing baselines
        self._load_baselines()

        logger.info("Advanced Feature Engineering initialized")

    def _define_derived_features(self) -> Dict[str, Dict[str, Any]]:
        """Define all derived features and their calculations."""
        return {
            # Rate of change features
            'coolant_temp_rate': {
                'source': 'coolant_temp',
                'type': 'rate_of_change',
                'unit': 'C/min',
                'warning_threshold': 5.0,  # More than 5C/min is concerning
                'critical_threshold': 10.0
            },
            'battery_voltage_rate': {
                'source': 'battery_voltage',
                'type': 'rate_of_change',
                'unit': 'V/min',
                'warning_threshold': 0.5,
                'critical_threshold': 1.0
            },
            'rpm_stability': {
                'source': 'rpm',
                'type': 'stability',
                'description': 'Standard deviation of RPM over window'
            },

            # Cross-sensor correlations
            'transmission_slip': {
                'sources': ['speed', 'rpm'],
                'type': 'correlation',
                'description': 'Calculated from speed/RPM ratio changes',
                'warning_threshold': 0.1  # 10% deviation from expected
            },
            'engine_efficiency': {
                'sources': ['engine_load', 'rpm', 'speed'],
                'type': 'derived',
                'description': 'Power output vs RPM efficiency indicator'
            },
            'cooling_efficiency': {
                'sources': ['coolant_temp', 'ambient_temp', 'speed'],
                'type': 'derived',
                'description': 'How well cooling system maintains temperature'
            },

            # Fuel system health indicators
            'fuel_trim_imbalance': {
                'sources': ['fuel_trim_short_b1', 'fuel_trim_short_b2'],
                'type': 'differential',
                'description': 'Bank-to-bank fuel trim difference'
            },
            'fuel_trim_drift': {
                'source': 'fuel_trim_long',
                'type': 'trend',
                'description': 'Long-term fuel trim trend direction'
            },

            # Electrical system indicators
            'voltage_under_load': {
                'sources': ['battery_voltage', 'engine_load'],
                'type': 'conditional',
                'description': 'Voltage drop correlation with load'
            },
            'alternator_ripple_indicator': {
                'source': 'battery_voltage',
                'type': 'frequency',
                'description': 'Voltage variation indicating alternator health'
            },

            # Engine health composite
            'idle_quality_score': {
                'sources': ['rpm', 'engine_load', 'fuel_trim_short'],
                'type': 'composite',
                'description': 'Composite score of idle stability'
            },

            # Thermal management
            'warmup_efficiency': {
                'source': 'coolant_temp',
                'type': 'time_to_threshold',
                'threshold': 80,  # Target operating temp
                'description': 'Time to reach operating temperature'
            },
            'thermal_stability': {
                'source': 'coolant_temp',
                'type': 'stability',
                'description': 'Temperature stability at operating temp'
            }
        }

    def _load_baselines(self):
        """Load saved vehicle baselines from disk."""
        baseline_file = self.storage_path / "vehicle_baselines.json"
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r') as f:
                    self.vehicle_baselines = json.load(f)
                logger.info(f"Loaded baselines for {len(self.vehicle_baselines)} vehicles")
            except Exception as e:
                logger.warning(f"Failed to load baselines: {e}")

    def _save_baselines(self):
        """Save vehicle baselines to disk."""
        baseline_file = self.storage_path / "vehicle_baselines.json"
        try:
            with open(baseline_file, 'w') as f:
                json.dump(self.vehicle_baselines, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save baselines: {e}")

    def _get_vehicle_id(self, profile: Optional[Dict]) -> str:
        """Extract vehicle ID from profile."""
        if not profile:
            return "unknown"
        return str(profile.get('profile_id', profile.get('vin', profile.get('name', 'unknown'))))

    def _ensure_buffer(self, vehicle_id: str, sensor: str, max_size: int = 600):
        """Ensure a sensor buffer exists for a vehicle."""
        if vehicle_id not in self.sensor_buffers:
            self.sensor_buffers[vehicle_id] = {}
        if sensor not in self.sensor_buffers[vehicle_id]:
            self.sensor_buffers[vehicle_id][sensor] = deque(maxlen=max_size)

    def add_reading(self, vehicle_id: str, sensor: str, value: float, timestamp: datetime = None):
        """Add a sensor reading to the buffer."""
        self._ensure_buffer(vehicle_id, sensor)
        if timestamp is None:
            timestamp = datetime.now()
        self.sensor_buffers[vehicle_id][sensor].append({
            'value': value,
            'timestamp': timestamp
        })

    def process_snapshot(self, data: Dict[str, Any], profile: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a data snapshot and add to buffers, returning derived features.

        Args:
            data: Raw OBD-II data snapshot
            profile: Vehicle profile for identification

        Returns:
            Dictionary containing original data plus all derived features
        """
        if not data:
            return {}

        vehicle_id = self._get_vehicle_id(profile)
        timestamp = datetime.now()

        # Add raw readings to buffers
        sensor_map = {
            'coolant_temp': ['coolant_temp', 'engine_coolant_temp'],
            'battery_voltage': ['battery_voltage', 'control_module_voltage'],
            'rpm': ['rpm', 'engine_rpm'],
            'speed': ['speed', 'vehicle_speed'],
            'engine_load': ['engine_load', 'calculated_engine_load'],
            'fuel_trim_short': ['fuel_trim_short', 'short_term_fuel_trim_1'],
            'fuel_trim_long': ['fuel_trim_long', 'long_term_fuel_trim_1'],
            'intake_temp': ['intake_temp', 'intake_air_temp'],
            'maf': ['maf', 'mass_air_flow'],
            'throttle': ['throttle_position', 'throttle_pos']
        }

        # Map data to canonical sensor names and buffer
        for canonical, alternates in sensor_map.items():
            for alt in alternates:
                if alt in data and data[alt] is not None:
                    try:
                        value = float(data[alt])
                        self.add_reading(vehicle_id, canonical, value, timestamp)
                    except (ValueError, TypeError):
                        pass
                    break

        # Calculate derived features
        derived = self._calculate_derived_features(vehicle_id, data)

        # Merge with original data
        result = data.copy()
        result['derived_features'] = derived
        result['feature_timestamp'] = timestamp.isoformat()

        return result

    def _calculate_derived_features(self, vehicle_id: str, data: Dict) -> Dict[str, Any]:
        """Calculate all derived features for a vehicle."""
        derived = {}

        if vehicle_id not in self.sensor_buffers:
            return derived

        buffers = self.sensor_buffers[vehicle_id]

        # Rate of change calculations
        for sensor in ['coolant_temp', 'battery_voltage', 'rpm', 'engine_load']:
            if sensor in buffers and len(buffers[sensor]) >= 2:
                rate = self._calculate_rate_of_change(buffers[sensor])
                derived[f'{sensor}_rate'] = round(rate, 4)

        # Stability calculations (standard deviation)
        for sensor in ['rpm', 'battery_voltage', 'coolant_temp']:
            if sensor in buffers and len(buffers[sensor]) >= 5:
                stability = self._calculate_stability(buffers[sensor])
                derived[f'{sensor}_stability'] = round(stability, 4)

        # Rolling statistics
        for sensor in ['coolant_temp', 'rpm', 'engine_load', 'battery_voltage']:
            if sensor in buffers and len(buffers[sensor]) >= 5:
                stats = self._calculate_rolling_stats(buffers[sensor])
                derived[f'{sensor}_mean'] = round(stats['mean'], 2)
                derived[f'{sensor}_std'] = round(stats['std'], 2)
                derived[f'{sensor}_trend'] = stats['trend']

        # Transmission slip indicator
        if 'speed' in buffers and 'rpm' in buffers:
            if len(buffers['speed']) >= 5 and len(buffers['rpm']) >= 5:
                slip = self._calculate_transmission_slip(buffers['speed'], buffers['rpm'])
                derived['transmission_slip_indicator'] = round(slip, 4)

        # Fuel trim imbalance (if bank 2 data available)
        stft_b1 = data.get('short_term_fuel_trim_1')
        stft_b2 = data.get('short_term_fuel_trim_2')
        if stft_b1 is not None and stft_b2 is not None:
            try:
                imbalance = abs(float(stft_b1) - float(stft_b2))
                derived['fuel_trim_bank_imbalance'] = round(imbalance, 2)
            except (ValueError, TypeError):
                pass

        # Voltage under load correlation
        voltage = data.get('battery_voltage') or data.get('control_module_voltage')
        load = data.get('engine_load') or data.get('calculated_engine_load')
        if voltage is not None and load is not None:
            try:
                # Expected: voltage should drop slightly under high load
                # Excessive drop indicates alternator/electrical issues
                voltage = float(voltage)
                load = float(load)
                if load > 50:  # Only calculate under significant load
                    # Baseline: ~0.5V drop at 100% load is normal
                    expected_voltage = 14.2 - (load * 0.005)
                    voltage_deviation = voltage - expected_voltage
                    derived['voltage_load_deviation'] = round(voltage_deviation, 2)
            except (ValueError, TypeError):
                pass

        # Idle quality score (when vehicle is idling)
        rpm = data.get('rpm') or data.get('engine_rpm')
        speed = data.get('speed') or data.get('vehicle_speed')
        if rpm is not None and speed is not None:
            try:
                rpm = float(rpm)
                speed = float(speed)
                if speed < 5 and rpm > 0:  # Vehicle is idling
                    idle_score = self._calculate_idle_quality(vehicle_id, rpm, data)
                    derived['idle_quality_score'] = round(idle_score, 2)
            except (ValueError, TypeError):
                pass

        # Engine efficiency indicator
        derived['engine_efficiency'] = self._calculate_engine_efficiency(data)

        # Anomaly z-scores
        z_scores = self._calculate_anomaly_scores(vehicle_id, data)
        derived['anomaly_scores'] = z_scores
        derived['max_anomaly_score'] = max(z_scores.values()) if z_scores else 0

        return derived

    def _calculate_rate_of_change(self, buffer: deque, window_seconds: float = 60.0) -> float:
        """Calculate rate of change in units per minute."""
        if len(buffer) < 2:
            return 0.0

        recent = list(buffer)[-30:]  # Last 30 readings

        if len(recent) < 2:
            return 0.0

        first = recent[0]
        last = recent[-1]

        time_diff = (last['timestamp'] - first['timestamp']).total_seconds()
        if time_diff == 0:
            return 0.0

        value_diff = last['value'] - first['value']

        # Convert to per-minute rate
        return (value_diff / time_diff) * 60.0

    def _calculate_stability(self, buffer: deque, window: int = 30) -> float:
        """Calculate stability (inverse of variance) for a sensor."""
        if len(buffer) < 5:
            return 100.0  # Assume stable if insufficient data

        values = [r['value'] for r in list(buffer)[-window:]]
        std = np.std(values)

        return std

    def _calculate_rolling_stats(self, buffer: deque, window: int = 30) -> Dict[str, Any]:
        """Calculate rolling statistics for a sensor buffer."""
        values = [r['value'] for r in list(buffer)[-window:]]

        if len(values) < 2:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'trend': 'stable'}

        mean = np.mean(values)
        std = np.std(values)

        # Calculate trend
        if len(values) >= 5:
            first_half_mean = np.mean(values[:len(values)//2])
            second_half_mean = np.mean(values[len(values)//2:])
            diff = second_half_mean - first_half_mean

            if abs(diff) < std * 0.1:
                trend = 'stable'
            elif diff > 0:
                trend = 'increasing'
            else:
                trend = 'decreasing'
        else:
            trend = 'unknown'

        return {
            'mean': mean,
            'std': std,
            'min': min(values),
            'max': max(values),
            'trend': trend
        }

    def _calculate_transmission_slip(self, speed_buffer: deque, rpm_buffer: deque) -> float:
        """
        Calculate transmission slip indicator.
        Compares actual speed/RPM ratio to expected ratio.
        Returns deviation percentage.
        """
        if len(speed_buffer) < 5 or len(rpm_buffer) < 5:
            return 0.0

        speeds = [r['value'] for r in list(speed_buffer)[-10:]]
        rpms = [r['value'] for r in list(rpm_buffer)[-10:]]

        # Filter out idle/stopped conditions
        valid_pairs = [(s, r) for s, r in zip(speeds, rpms) if s > 10 and r > 1000]

        if len(valid_pairs) < 3:
            return 0.0

        # Calculate speed/RPM ratios
        ratios = [s / r for s, r in valid_pairs]
        mean_ratio = np.mean(ratios)
        std_ratio = np.std(ratios)

        # High variability in ratio indicates slip
        if mean_ratio > 0:
            coefficient_of_variation = std_ratio / mean_ratio
            return coefficient_of_variation

        return 0.0

    def _calculate_idle_quality(self, vehicle_id: str, rpm: float, data: Dict) -> float:
        """
        Calculate idle quality score (0-100, higher is better).
        Based on RPM stability, fuel trim, and engine load at idle.
        """
        score = 100.0

        # RPM stability check
        if vehicle_id in self.sensor_buffers and 'rpm' in self.sensor_buffers[vehicle_id]:
            rpm_buffer = self.sensor_buffers[vehicle_id]['rpm']
            if len(rpm_buffer) >= 10:
                rpm_values = [r['value'] for r in list(rpm_buffer)[-10:]]
                rpm_std = np.std(rpm_values)

                # Deduct points for RPM instability
                if rpm_std > 100:
                    score -= min(30, rpm_std / 10)

        # Fuel trim check
        stft = data.get('short_term_fuel_trim_1') or data.get('fuel_trim_short')
        if stft is not None:
            try:
                stft = abs(float(stft))
                if stft > 10:
                    score -= min(20, (stft - 10) * 2)
            except (ValueError, TypeError):
                pass

        # Engine load at idle should be low
        load = data.get('engine_load') or data.get('calculated_engine_load')
        if load is not None:
            try:
                load = float(load)
                if load > 30:  # Idle load should be <30%
                    score -= min(20, (load - 30))
            except (ValueError, TypeError):
                pass

        return max(0, min(100, score))

    def _calculate_engine_efficiency(self, data: Dict) -> float:
        """
        Calculate engine efficiency indicator.
        Based on load vs RPM relationship.
        """
        rpm = data.get('rpm') or data.get('engine_rpm')
        load = data.get('engine_load') or data.get('calculated_engine_load')
        speed = data.get('speed') or data.get('vehicle_speed')

        if rpm is None or load is None:
            return 0.0

        try:
            rpm = float(rpm)
            load = float(load)
            speed = float(speed) if speed else 0

            if rpm < 500 or load < 5:
                return 0.0

            # Efficiency = work output / energy input proxy
            # Higher speed with lower RPM and load = better efficiency
            if speed > 0:
                efficiency = (speed / (rpm / 1000)) * (100 - load) / 100
                return round(min(100, max(0, efficiency * 10)), 2)

            return 0.0

        except (ValueError, TypeError):
            return 0.0

    def _calculate_anomaly_scores(self, vehicle_id: str, data: Dict) -> Dict[str, float]:
        """
        Calculate z-scores for anomaly detection.
        Compares current values against vehicle's learned baseline.
        """
        z_scores = {}

        baseline = self.vehicle_baselines.get(vehicle_id, {})
        if not baseline:
            return z_scores

        sensor_map = {
            'coolant_temp': ['coolant_temp', 'engine_coolant_temp'],
            'battery_voltage': ['battery_voltage', 'control_module_voltage'],
            'rpm': ['rpm', 'engine_rpm'],
            'engine_load': ['engine_load', 'calculated_engine_load'],
            'fuel_trim_short': ['short_term_fuel_trim_1', 'fuel_trim_short'],
            'fuel_trim_long': ['long_term_fuel_trim_1', 'fuel_trim_long']
        }

        for canonical, alternates in sensor_map.items():
            if canonical not in baseline:
                continue

            base_mean = baseline[canonical].get('mean', 0)
            base_std = baseline[canonical].get('std', 1)

            if base_std == 0:
                base_std = 1  # Prevent division by zero

            for alt in alternates:
                if alt in data and data[alt] is not None:
                    try:
                        value = float(data[alt])
                        z = abs(value - base_mean) / base_std
                        z_scores[canonical] = round(z, 2)
                    except (ValueError, TypeError):
                        pass
                    break

        return z_scores

    def learn_baseline(self, vehicle_id: str, min_samples: int = 100) -> bool:
        """
        Learn baseline statistics for a vehicle from buffered data.
        Should be called after collecting sufficient data.
        """
        if vehicle_id not in self.sensor_buffers:
            return False

        buffers = self.sensor_buffers[vehicle_id]
        baseline = {}

        for sensor, buffer in buffers.items():
            if len(buffer) < min_samples:
                continue

            values = [r['value'] for r in buffer]

            baseline[sensor] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'percentile_5': float(np.percentile(values, 5)),
                'percentile_95': float(np.percentile(values, 95)),
                'sample_count': len(values),
                'learned_at': datetime.now().isoformat()
            }

        if baseline:
            self.vehicle_baselines[vehicle_id] = baseline
            self._save_baselines()
            logger.info(f"Learned baseline for vehicle {vehicle_id} with {len(baseline)} sensors")
            return True

        return False

    def get_baseline(self, vehicle_id: str) -> Dict[str, Any]:
        """Get baseline for a vehicle."""
        return self.vehicle_baselines.get(vehicle_id, {})

    def get_feature_summary(self, vehicle_id: str) -> Dict[str, Any]:
        """Get summary of feature engineering status for a vehicle."""
        buffers = self.sensor_buffers.get(vehicle_id, {})
        baseline = self.vehicle_baselines.get(vehicle_id, {})

        return {
            'vehicle_id': vehicle_id,
            'buffered_sensors': list(buffers.keys()),
            'buffer_sizes': {s: len(b) for s, b in buffers.items()},
            'has_baseline': len(baseline) > 0,
            'baseline_sensors': list(baseline.keys()),
            'available_derived_features': list(self.derived_features.keys())
        }

    def clear_buffers(self, vehicle_id: str = None):
        """Clear sensor buffers for a vehicle or all vehicles."""
        if vehicle_id:
            if vehicle_id in self.sensor_buffers:
                del self.sensor_buffers[vehicle_id]
        else:
            self.sensor_buffers.clear()
