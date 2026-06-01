"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Baseline Learning System

Vehicle Baseline Learning System
================================
Learns normal operating characteristics for each individual vehicle.

Features:
- Per-vehicle baseline establishment
- Operating state-aware baselines (idle, cruising, acceleration, etc.)
- Seasonal/temperature adjustments
- Anomaly detection against learned baselines
- Fleet-wide comparison
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json
import logging
from pathlib import Path
from enum import Enum
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class VehicleState(Enum):
    """Operating states of a vehicle."""
    OFF = "off"
    STARTING = "starting"
    WARMING_UP = "warming_up"
    IDLE = "idle"
    CRUISING = "cruising"
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"
    HIGH_LOAD = "high_load"
    UNKNOWN = "unknown"


@dataclass
class SensorBaseline:
    """Baseline statistics for a sensor."""
    mean: float
    std: float
    min_val: float
    max_val: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    sample_count: int
    last_updated: str


@dataclass
class StateBaseline:
    """Baseline for a specific operating state."""
    state: VehicleState
    sensors: Dict[str, SensorBaseline]
    sample_count: int
    last_updated: str


@dataclass
class VehicleBaseline:
    """Complete baseline for a vehicle."""
    vehicle_id: str
    vin: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    overall: Dict[str, SensorBaseline]  # Global baselines
    by_state: Dict[str, StateBaseline]  # State-specific baselines
    by_temperature: Dict[str, Dict[str, SensorBaseline]]  # Temperature-adjusted
    warmup_profile: Dict[str, Any]  # Warmup characteristics
    learning_started: str
    last_updated: str
    total_samples: int
    quality_score: float  # 0-100, based on data coverage


class VehicleBaselineLearning:
    """
    Learns and maintains baselines for individual vehicles.
    Enables accurate anomaly detection tailored to each vehicle.
    """

    def __init__(self, config=None):
        """Initialize baseline learning system."""
        self.config = config

        # Storage path
        self.storage_path = CONFIG.DATA_DIR / "vehicle_baselines"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Loaded baselines
        self.baselines: Dict[str, VehicleBaseline] = {}

        # Active learning buffers
        self.learning_buffers: Dict[str, Dict[str, deque]] = {}

        # Sensors to track
        self.tracked_sensors = [
            'rpm', 'coolant_temp', 'battery_voltage', 'engine_load',
            'throttle_position', 'speed', 'intake_temp', 'maf',
            'fuel_trim_short', 'fuel_trim_long', 'timing_advance',
            'catalyst_temp', 'ambient_temp'
        ]

        # Temperature buckets for temperature-based baselines
        self.temperature_buckets = {
            'cold': (-float('inf'), 0),      # < 0°C
            'cool': (0, 15),                  # 0-15°C
            'normal': (15, 30),               # 15-30°C
            'warm': (30, 40),                 # 30-40°C
            'hot': (40, float('inf'))         # > 40°C
        }

        # Minimum samples for reliable baseline
        self.min_samples_per_state = 100
        self.min_total_samples = 500

        # Load existing baselines
        self._load_baselines()

        logger.info(f"Vehicle Baseline Learning initialized with {len(self.baselines)} vehicles")

    def _load_baselines(self):
        """Load saved baselines from disk."""
        for file in self.storage_path.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    baseline = self._dict_to_baseline(data)
                    self.baselines[baseline.vehicle_id] = baseline
            except Exception as e:
                logger.warning(f"Failed to load baseline {file}: {e}")

    def _save_baseline(self, vehicle_id: str):
        """Save a vehicle baseline to disk."""
        if vehicle_id not in self.baselines:
            return

        baseline = self.baselines[vehicle_id]
        file_path = self.storage_path / f"{vehicle_id}.json"

        try:
            data = self._baseline_to_dict(baseline)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save baseline for {vehicle_id}: {e}")

    def _baseline_to_dict(self, baseline: VehicleBaseline) -> Dict:
        """Convert VehicleBaseline to dictionary for JSON serialization."""
        return {
            'vehicle_id': baseline.vehicle_id,
            'vin': baseline.vin,
            'make': baseline.make,
            'model': baseline.model,
            'year': baseline.year,
            'overall': {
                k: vars(v) for k, v in baseline.overall.items()
            },
            'by_state': {
                k: {
                    'state': v.state.value,
                    'sensors': {sk: vars(sv) for sk, sv in v.sensors.items()},
                    'sample_count': v.sample_count,
                    'last_updated': v.last_updated
                }
                for k, v in baseline.by_state.items()
            },
            'by_temperature': baseline.by_temperature,
            'warmup_profile': baseline.warmup_profile,
            'learning_started': baseline.learning_started,
            'last_updated': baseline.last_updated,
            'total_samples': baseline.total_samples,
            'quality_score': baseline.quality_score
        }

    def _dict_to_baseline(self, data: Dict) -> VehicleBaseline:
        """Convert dictionary to VehicleBaseline."""
        overall = {}
        for k, v in data.get('overall', {}).items():
            overall[k] = SensorBaseline(**v)

        by_state = {}
        for k, v in data.get('by_state', {}).items():
            sensors = {sk: SensorBaseline(**sv) for sk, sv in v.get('sensors', {}).items()}
            by_state[k] = StateBaseline(
                state=VehicleState(v['state']),
                sensors=sensors,
                sample_count=v.get('sample_count', 0),
                last_updated=v.get('last_updated', '')
            )

        return VehicleBaseline(
            vehicle_id=data['vehicle_id'],
            vin=data.get('vin'),
            make=data.get('make'),
            model=data.get('model'),
            year=data.get('year'),
            overall=overall,
            by_state=by_state,
            by_temperature=data.get('by_temperature', {}),
            warmup_profile=data.get('warmup_profile', {}),
            learning_started=data.get('learning_started', ''),
            last_updated=data.get('last_updated', ''),
            total_samples=data.get('total_samples', 0),
            quality_score=data.get('quality_score', 0)
        )

    def _get_vehicle_id(self, profile: Optional[Dict]) -> str:
        """Extract vehicle ID from profile."""
        if not profile:
            return "unknown"
        return str(profile.get('profile_id', profile.get('vin', profile.get('name', 'unknown'))))

    def _determine_state(self, data: Dict) -> VehicleState:
        """Determine current vehicle operating state from sensor data."""
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        speed = self._get_value(data, ['speed', 'vehicle_speed'])
        load = self._get_value(data, ['engine_load', 'calculated_engine_load'])
        coolant = self._get_value(data, ['coolant_temp', 'engine_coolant_temp'])
        throttle = self._get_value(data, ['throttle_position', 'throttle_pos'])

        # Engine off
        if rpm is None or rpm < 100:
            return VehicleState.OFF

        # Starting (high RPM, no speed, low coolant)
        if speed is not None and speed < 5:
            if coolant is not None and coolant < 60:
                return VehicleState.WARMING_UP
            if rpm is not None and 600 < rpm < 1200 and (load is None or load < 30):
                return VehicleState.IDLE

        # High load operation
        if load is not None and load > 80:
            return VehicleState.HIGH_LOAD

        # Acceleration detection (high throttle, increasing speed)
        if throttle is not None and throttle > 40:
            return VehicleState.ACCELERATING

        # Deceleration (low throttle while moving)
        if speed is not None and speed > 20 and (throttle is None or throttle < 10):
            return VehicleState.DECELERATING

        # Cruising (moderate speed, low throttle variation)
        if speed is not None and speed > 30 and (throttle is None or throttle < 30):
            return VehicleState.CRUISING

        return VehicleState.UNKNOWN

    def _get_value(self, data: Dict, keys: List[str]) -> Optional[float]:
        """Get a value from data trying multiple possible keys."""
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    pass
        return None

    def _ensure_buffer(self, vehicle_id: str, state: str, sensor: str, temp_bucket: str = None):
        """Ensure learning buffer exists."""
        if vehicle_id not in self.learning_buffers:
            self.learning_buffers[vehicle_id] = {}
        if state not in self.learning_buffers[vehicle_id]:
            self.learning_buffers[vehicle_id][state] = {}
        if temp_bucket and 'by_temperature' not in self.learning_buffers[vehicle_id]:
            self.learning_buffers[vehicle_id]['by_temperature'] = {}
            for bucket in self.temperature_buckets:
                self.learning_buffers[vehicle_id]['by_temperature'][bucket] = {}
        if sensor not in self.learning_buffers[vehicle_id][state]:
            self.learning_buffers[vehicle_id][state][sensor] = deque(maxlen=5000)
        if temp_bucket and sensor not in self.learning_buffers[vehicle_id]['by_temperature'][temp_bucket]:
            self.learning_buffers[vehicle_id]['by_temperature'][temp_bucket][sensor] = deque(maxlen=2000)

    def _get_temperature_bucket(self, ambient_temp: Optional[float]) -> str:
        """Determine temperature bucket based on ambient temperature."""
        if ambient_temp is None:
            return 'normal'  # Default to normal if no temp data
        
        for bucket_name, (min_temp, max_temp) in self.temperature_buckets.items():
            if min_temp <= ambient_temp < max_temp:
                return bucket_name
        return 'normal'

    def add_sample(self, data: Dict, profile: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Add a data sample for learning.

        Args:
            data: Current OBD-II sensor data
            profile: Vehicle profile

        Returns:
            Learning status dictionary
        """
        vehicle_id = self._get_vehicle_id(profile)
        state = self._determine_state(data)
        timestamp = datetime.now()

        # Extract vehicle info from profile
        vin = profile.get('vin') if profile else None
        make = profile.get('make') if profile else None
        model = profile.get('model') if profile else None
        year = profile.get('year') if profile else None

        # Get ambient temperature for temperature-based baselines
        ambient_temp = self._get_value(data, ['ambient_temp', 'intake_temp'])
        temp_bucket = self._get_temperature_bucket(ambient_temp)

        # Add to buffers
        for sensor in self.tracked_sensors:
            value = self._get_value(data, [sensor])
            if value is not None:
                # Add to state-specific buffer
                self._ensure_buffer(vehicle_id, state.value, sensor)
                self.learning_buffers[vehicle_id][state.value][sensor].append(value)

                # Add to overall buffer
                self._ensure_buffer(vehicle_id, 'overall', sensor)
                self.learning_buffers[vehicle_id]['overall'][sensor].append(value)

                # Add to temperature-specific buffer
                if temp_bucket:
                    self._ensure_buffer(vehicle_id, state.value, sensor, temp_bucket)
                    self.learning_buffers[vehicle_id]['by_temperature'][temp_bucket][sensor].append(value)

        # Check if we have enough data to update baseline
        status = self._update_baseline_if_ready(
            vehicle_id, vin, make, model, year
        )

        return status

    def _update_baseline_if_ready(self, vehicle_id: str, vin: str = None,
                                   make: str = None, model: str = None,
                                   year: int = None) -> Dict[str, Any]:
        """Update baseline if sufficient data has been collected."""
        if vehicle_id not in self.learning_buffers:
            return {'status': 'collecting', 'samples': 0}

        buffers = self.learning_buffers[vehicle_id]
        overall_buffer = buffers.get('overall', {})

        # Count total samples (use RPM as proxy)
        total_samples = len(overall_buffer.get('rpm', []))

        if total_samples < self.min_total_samples:
            return {
                'status': 'collecting',
                'samples': total_samples,
                'needed': self.min_total_samples
            }

        # Create or update baseline
        baseline = self._create_baseline(vehicle_id, vin, make, model, year, buffers)
        self.baselines[vehicle_id] = baseline
        self._save_baseline(vehicle_id)

        return {
            'status': 'updated',
            'samples': total_samples,
            'quality_score': baseline.quality_score
        }

    def _create_baseline(self, vehicle_id: str, vin: str, make: str,
                          model: str, year: int, buffers: Dict) -> VehicleBaseline:
        """Create or update vehicle baseline from collected data."""
        now = datetime.now().isoformat()

        # Create overall baseline
        overall = {}
        overall_buffer = buffers.get('overall', {})
        for sensor, values in overall_buffer.items():
            if len(values) >= 30:
                overall[sensor] = self._calculate_sensor_baseline(list(values))

        # Create state-specific baselines
        by_state = {}
        for state_name, state_buffers in buffers.items():
            if state_name == 'overall':
                continue

            sensors = {}
            sample_count = 0
            for sensor, values in state_buffers.items():
                if len(values) >= 10:
                    sensors[sensor] = self._calculate_sensor_baseline(list(values))
                    sample_count = max(sample_count, len(values))

            if sensors:
                by_state[state_name] = StateBaseline(
                    state=VehicleState(state_name),
                    sensors=sensors,
                    sample_count=sample_count,
                    last_updated=now
                )

        # Calculate warmup profile
        warmup_profile = self._calculate_warmup_profile(buffers)

        # Calculate temperature-based baselines
        by_temperature = self._calculate_temperature_baselines(buffers)

        # Calculate quality score
        quality_score = self._calculate_quality_score(overall, by_state)

        # Total samples
        total_samples = sum(len(v) for v in overall_buffer.values())

        # Check for existing baseline
        existing = self.baselines.get(vehicle_id)

        return VehicleBaseline(
            vehicle_id=vehicle_id,
            vin=vin or (existing.vin if existing else None),
            make=make or (existing.make if existing else None),
            model=model or (existing.model if existing else None),
            year=year or (existing.year if existing else None),
            overall=overall,
            by_state=by_state,
            by_temperature=by_temperature,
            warmup_profile=warmup_profile,
            learning_started=existing.learning_started if existing else now,
            last_updated=now,
            total_samples=total_samples,
            quality_score=quality_score
        )

    def _calculate_sensor_baseline(self, values: List[float]) -> SensorBaseline:
        """Calculate baseline statistics for a sensor."""
        arr = np.array(values)
        return SensorBaseline(
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_val=float(np.min(arr)),
            max_val=float(np.max(arr)),
            percentile_5=float(np.percentile(arr, 5)),
            percentile_25=float(np.percentile(arr, 25)),
            percentile_75=float(np.percentile(arr, 75)),
            percentile_95=float(np.percentile(arr, 95)),
            sample_count=len(values),
            last_updated=datetime.now().isoformat()
        )

    def _calculate_warmup_profile(self, buffers: Dict) -> Dict[str, Any]:
        """Calculate vehicle warmup characteristics."""
        warmup_data = buffers.get(VehicleState.WARMING_UP.value, {})
        coolant_values = list(warmup_data.get('coolant_temp', []))

        if len(coolant_values) < 10:
            return {}

        return {
            'starting_temp': float(np.min(coolant_values)),
            'target_temp': 90.0,  # Assumed operating temp
            'samples_during_warmup': len(coolant_values)
        }

    def _calculate_quality_score(self, overall: Dict[str, SensorBaseline],
                                  by_state: Dict[str, StateBaseline]) -> float:
        """Calculate baseline quality score (0-100)."""
        score = 0

        # Points for overall sensors (max 40)
        sensor_coverage = len(overall) / len(self.tracked_sensors)
        score += sensor_coverage * 40

        # Points for state coverage (max 30)
        possible_states = [s for s in VehicleState if s != VehicleState.OFF and s != VehicleState.UNKNOWN]
        state_coverage = len(by_state) / len(possible_states)
        score += state_coverage * 30

        # Points for sample count (max 30)
        total_samples = sum(s.sample_count for s in overall.values())
        sample_score = min(1.0, total_samples / 5000)  # Max score at 5000 samples
        score += sample_score * 30

        return round(score, 1)

    def _calculate_temperature_baselines(self, buffers: Dict) -> Dict[str, Dict[str, SensorBaseline]]:
        """
        Calculate temperature-specific baselines for sensors.
        
        Returns:
            Dictionary mapping temperature bucket names to sensor baselines
        """
        by_temperature = {}
        temp_buffers = buffers.get('by_temperature', {})
        
        for bucket_name, bucket_sensors in temp_buffers.items():
            sensor_baselines = {}
            
            for sensor, values in bucket_sensors.items():
                if len(values) >= 20:  # Minimum samples for temperature baseline
                    sensor_baselines[sensor] = self._calculate_sensor_baseline(list(values))
            
            if sensor_baselines:
                by_temperature[bucket_name] = sensor_baselines
        
        return by_temperature

    def get_baseline(self, vehicle_id: str) -> Optional[VehicleBaseline]:
        """Get baseline for a vehicle."""
        return self.baselines.get(vehicle_id)

    def get_anomaly_score(self, data: Dict, profile: Optional[Dict] = None,
                          use_state: bool = True) -> Dict[str, float]:
        """
        Calculate anomaly scores for current readings against baseline.

        Args:
            data: Current sensor data
            profile: Vehicle profile
            use_state: Whether to use state-specific baselines

        Returns:
            Dictionary of sensor -> z-score
        """
        vehicle_id = self._get_vehicle_id(profile)
        baseline = self.baselines.get(vehicle_id)

        if not baseline:
            return {}

        scores = {}
        state = self._determine_state(data)

        for sensor in self.tracked_sensors:
            value = self._get_value(data, [sensor])
            if value is None:
                continue

            # Get appropriate baseline
            sensor_baseline = None

            if use_state and state.value in baseline.by_state:
                state_baseline = baseline.by_state[state.value]
                sensor_baseline = state_baseline.sensors.get(sensor)

            if sensor_baseline is None:
                sensor_baseline = baseline.overall.get(sensor)

            if sensor_baseline is None:
                continue

            # Calculate z-score
            if sensor_baseline.std > 0:
                z_score = abs(value - sensor_baseline.mean) / sensor_baseline.std
                scores[sensor] = round(z_score, 2)

        return scores

    def compare_to_fleet(self, vehicle_id: str, data: Dict) -> Dict[str, Any]:
        """
        Compare vehicle readings to fleet average.
        Useful for detecting vehicle-specific issues vs normal variation.
        """
        if len(self.baselines) < 2:
            return {'status': 'insufficient_fleet_data'}

        vehicle_baseline = self.baselines.get(vehicle_id)
        if not vehicle_baseline:
            return {'status': 'no_vehicle_baseline'}

        # Calculate fleet averages
        fleet_stats = {}
        for sensor in self.tracked_sensors:
            values = []
            for bid, baseline in self.baselines.items():
                if bid == vehicle_id:
                    continue
                sensor_baseline = baseline.overall.get(sensor)
                if sensor_baseline:
                    values.append(sensor_baseline.mean)

            if values:
                fleet_stats[sensor] = {
                    'fleet_mean': float(np.mean(values)),
                    'fleet_std': float(np.std(values))
                }

        # Compare vehicle to fleet
        comparisons = {}
        for sensor, stats in fleet_stats.items():
            vehicle_sensor = vehicle_baseline.overall.get(sensor)
            if vehicle_sensor:
                fleet_mean = stats['fleet_mean']
                fleet_std = stats['fleet_std'] or 1

                deviation = (vehicle_sensor.mean - fleet_mean) / fleet_std
                comparisons[sensor] = {
                    'vehicle_mean': vehicle_sensor.mean,
                    'fleet_mean': fleet_mean,
                    'deviation_sigma': round(deviation, 2),
                    'status': 'normal' if abs(deviation) < 2 else 'abnormal'
                }

        return {
            'status': 'success',
            'fleet_size': len(self.baselines) - 1,
            'comparisons': comparisons
        }

    def get_learning_status(self, vehicle_id: str) -> Dict[str, Any]:
        """Get learning status for a vehicle."""
        baseline = self.baselines.get(vehicle_id)
        buffers = self.learning_buffers.get(vehicle_id, {})

        buffer_samples = sum(
            len(v) for state_buffers in buffers.values()
            for v in state_buffers.values()
        ) // len(self.tracked_sensors) if buffers else 0

        return {
            'vehicle_id': vehicle_id,
            'has_baseline': baseline is not None,
            'quality_score': baseline.quality_score if baseline else 0,
            'total_samples': baseline.total_samples if baseline else 0,
            'buffer_samples': buffer_samples,
            'states_learned': list(baseline.by_state.keys()) if baseline else [],
            'sensors_covered': list(baseline.overall.keys()) if baseline else [],
            'last_updated': baseline.last_updated if baseline else None
        }

    def clear_vehicle_data(self, vehicle_id: str):
        """Clear all data for a vehicle."""
        if vehicle_id in self.baselines:
            del self.baselines[vehicle_id]
        if vehicle_id in self.learning_buffers:
            del self.learning_buffers[vehicle_id]

        # Remove saved file
        file_path = self.storage_path / f"{vehicle_id}.json"
        if file_path.exists():
            file_path.unlink()
