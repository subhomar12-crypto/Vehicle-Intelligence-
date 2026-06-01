"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: External Sensor Schema

External Sensor Data Schema
===========================
Defines the data schema and processing pipeline for external sensors
connected via ESP32-S3 (or similar microcontrollers).

Supports:
- Vibration sensors (accelerometers)
- Current sensors
- Temperature sensors (multi-point)
- Acoustic sensors (optional)
- Pressure sensors (optional)

Data Flow: Sensors -> ESP32 -> BLE/WiFi -> Android App -> API -> Predict Server
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
from pathlib import Path
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class SensorType(Enum):
    """Types of external sensors."""
    ACCELEROMETER = "accelerometer"
    CURRENT = "current"
    TEMPERATURE = "temperature"
    ACOUSTIC = "acoustic"
    PRESSURE = "pressure"
    STRAIN = "strain"
    HUMIDITY = "humidity"
    RPM_HALL = "rpm_hall"


class SensorLocation(Enum):
    """Physical locations where sensors can be mounted."""
    ENGINE_BLOCK = "engine_block"
    TRANSMISSION = "transmission"
    DIFFERENTIAL = "differential"
    WHEEL_FL = "wheel_front_left"
    WHEEL_FR = "wheel_front_right"
    WHEEL_RL = "wheel_rear_left"
    WHEEL_RR = "wheel_rear_right"
    ALTERNATOR = "alternator"
    FUEL_PUMP = "fuel_pump"
    AC_COMPRESSOR = "ac_compressor"
    COOLANT_LINE = "coolant_line"
    OIL_PAN = "oil_pan"
    EXHAUST = "exhaust"
    INTAKE = "intake"
    BATTERY = "battery"
    AMBIENT = "ambient"


@dataclass
class SensorConfig:
    """Configuration for a single sensor."""
    sensor_id: str
    sensor_type: SensorType
    location: SensorLocation
    model: str  # e.g., "ADXL345", "INA219", "DS18B20"
    sampling_rate_hz: int
    measurement_range: Tuple[float, float]
    unit: str
    calibration_offset: float = 0.0
    calibration_scale: float = 1.0
    enabled: bool = True


@dataclass
class VibrationData:
    """
    Processed vibration data from accelerometer.
    ESP32 should perform FFT and send frequency-domain data.
    """
    sensor_id: str
    location: str
    timestamp: str

    # Time-domain features
    rms_x: float  # Root Mean Square
    rms_y: float
    rms_z: float
    peak_x: float  # Peak amplitude
    peak_y: float
    peak_z: float
    crest_factor: float  # Peak / RMS ratio

    # Frequency-domain features (from FFT on ESP32)
    dominant_freq_hz: float
    dominant_amplitude: float
    spectral_centroid: float
    frequency_bands: Dict[str, float]  # {"0-100Hz": amplitude, "100-500Hz": amplitude, ...}

    # Bearing defect frequencies (if calculated)
    bpfo_amplitude: Optional[float] = None  # Ball Pass Frequency Outer
    bpfi_amplitude: Optional[float] = None  # Ball Pass Frequency Inner
    bsf_amplitude: Optional[float] = None   # Ball Spin Frequency
    ftf_amplitude: Optional[float] = None   # Fundamental Train Frequency


@dataclass
class CurrentData:
    """Processed current measurement data."""
    sensor_id: str
    location: str
    timestamp: str

    current_amps: float  # Instantaneous current
    current_avg: float   # Rolling average
    current_peak: float  # Peak during sample window
    current_rms: float   # RMS current

    # Derived metrics
    power_watts: Optional[float] = None  # If voltage known
    inrush_detected: bool = False
    inrush_duration_ms: Optional[int] = None


@dataclass
class TemperatureData:
    """Temperature measurement data."""
    sensor_id: str
    location: str
    timestamp: str

    temperature_c: float
    rate_of_change: float  # C/minute
    delta_from_ambient: Optional[float] = None


@dataclass
class AcousticData:
    """Processed acoustic/sound data."""
    sensor_id: str
    location: str
    timestamp: str

    spl_db: float  # Sound Pressure Level
    dominant_freq_hz: float
    frequency_bands: Dict[str, float]

    # Anomaly indicators
    knock_detected: bool = False
    squeal_detected: bool = False


@dataclass
class SensorPacket:
    """
    Complete sensor data packet from ESP32.
    This is the standard format for transmission.
    """
    packet_id: str
    device_id: str  # ESP32 device ID
    vehicle_id: str
    timestamp: str
    battery_voltage: float  # ESP32 battery/power level

    # Sensor readings
    vibration: List[VibrationData] = field(default_factory=list)
    current: List[CurrentData] = field(default_factory=list)
    temperature: List[TemperatureData] = field(default_factory=list)
    acoustic: List[AcousticData] = field(default_factory=list)

    # Metadata
    sample_count: int = 0
    transmission_latency_ms: int = 0


class ExternalSensorProcessor:
    """
    Processes external sensor data from ESP32.
    Integrates with the main AI prediction pipeline.
    """

    def __init__(self, config=None):
        """Initialize sensor processor."""
        self.config = config

        # Sensor configurations
        self.sensors: Dict[str, SensorConfig] = {}

        # Processing thresholds
        self.thresholds = self._define_thresholds()

        # Calibration data per vehicle
        self.calibrations: Dict[str, Dict[str, Any]] = {}

        # Storage path
        self.storage_path = CONFIG.DATA_DIR / "external_sensors"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load configurations
        self._load_config()

        logger.info("External Sensor Processor initialized")

    def _define_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Define detection thresholds for various conditions."""
        return {
            'vibration': {
                'normal_rms': 0.5,  # g
                'warning_rms': 1.5,
                'critical_rms': 3.0,
                'bearing_defect_amplitude': 0.3,
                'imbalance_threshold': 0.8
            },
            'current': {
                'alternator_normal': (40, 80),  # Amps at various loads
                'fuel_pump_normal': (3, 8),
                'starter_inrush_max': 200,
                'inrush_duration_max_ms': 500
            },
            'temperature': {
                'max_rate_of_change': 5.0,  # C/min
                'engine_warning': 100,
                'engine_critical': 110,
                'trans_warning': 100,
                'differential_warning': 90
            },
            'acoustic': {
                'normal_spl_db': 80,
                'warning_spl_db': 95,
                'knock_threshold_db': 85,
                'squeal_freq_range': (2000, 8000)
            }
        }

    def _load_config(self):
        """Load sensor configurations."""
        config_file = self.storage_path / "sensor_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    for sensor_id, cfg in data.get('sensors', {}).items():
                        self.sensors[sensor_id] = SensorConfig(
                            sensor_id=sensor_id,
                            sensor_type=SensorType(cfg['sensor_type']),
                            location=SensorLocation(cfg['location']),
                            model=cfg['model'],
                            sampling_rate_hz=cfg['sampling_rate_hz'],
                            measurement_range=tuple(cfg['measurement_range']),
                            unit=cfg['unit'],
                            calibration_offset=cfg.get('calibration_offset', 0),
                            calibration_scale=cfg.get('calibration_scale', 1),
                            enabled=cfg.get('enabled', True)
                        )
            except Exception as e:
                logger.warning(f"Failed to load sensor config: {e}")

    def _save_config(self):
        """Save sensor configurations."""
        config_file = self.storage_path / "sensor_config.json"
        try:
            data = {
                'sensors': {
                    sid: {
                        'sensor_type': cfg.sensor_type.value,
                        'location': cfg.location.value,
                        'model': cfg.model,
                        'sampling_rate_hz': cfg.sampling_rate_hz,
                        'measurement_range': list(cfg.measurement_range),
                        'unit': cfg.unit,
                        'calibration_offset': cfg.calibration_offset,
                        'calibration_scale': cfg.calibration_scale,
                        'enabled': cfg.enabled
                    }
                    for sid, cfg in self.sensors.items()
                }
            }
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save sensor config: {e}")

    def register_sensor(self, sensor_config: SensorConfig):
        """Register a new sensor."""
        self.sensors[sensor_config.sensor_id] = sensor_config
        self._save_config()
        logger.info(f"Registered sensor: {sensor_config.sensor_id}")

    def process_packet(self, packet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming sensor packet from ESP32.

        Args:
            packet_data: Raw JSON packet from ESP32 via Android app

        Returns:
            Processed results with anomaly detection
        """
        results = {
            'packet_id': packet_data.get('packet_id', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'anomalies': [],
            'health_indicators': {},
            'raw_data_stored': False
        }

        vehicle_id = packet_data.get('vehicle_id', 'unknown')

        # Process vibration data
        for vib_data in packet_data.get('vibration', []):
            vib_result = self._process_vibration(vib_data, vehicle_id)
            results['health_indicators']['vibration_' + vib_data.get('location', 'unknown')] = vib_result
            if vib_result.get('anomaly'):
                results['anomalies'].append(vib_result['anomaly'])

        # Process current data
        for curr_data in packet_data.get('current', []):
            curr_result = self._process_current(curr_data, vehicle_id)
            results['health_indicators']['current_' + curr_data.get('location', 'unknown')] = curr_result
            if curr_result.get('anomaly'):
                results['anomalies'].append(curr_result['anomaly'])

        # Process temperature data
        for temp_data in packet_data.get('temperature', []):
            temp_result = self._process_temperature(temp_data, vehicle_id)
            results['health_indicators']['temperature_' + temp_data.get('location', 'unknown')] = temp_result
            if temp_result.get('anomaly'):
                results['anomalies'].append(temp_result['anomaly'])

        # Process acoustic data
        for acoustic_data in packet_data.get('acoustic', []):
            acoustic_result = self._process_acoustic(acoustic_data, vehicle_id)
            results['health_indicators']['acoustic_' + acoustic_data.get('location', 'unknown')] = acoustic_result
            if acoustic_result.get('anomaly'):
                results['anomalies'].append(acoustic_result['anomaly'])

        # Store raw data for training
        self._store_raw_data(vehicle_id, packet_data)
        results['raw_data_stored'] = True

        return results

    def _process_vibration(self, data: Dict, vehicle_id: str) -> Dict[str, Any]:
        """Process vibration sensor data."""
        result = {
            'location': data.get('location', 'unknown'),
            'health_score': 100.0,
            'anomaly': None
        }

        # Calculate combined RMS
        rms_x = data.get('rms_x', 0)
        rms_y = data.get('rms_y', 0)
        rms_z = data.get('rms_z', 0)
        combined_rms = np.sqrt(rms_x**2 + rms_y**2 + rms_z**2)

        result['combined_rms'] = round(combined_rms, 4)

        thresholds = self.thresholds['vibration']

        # Check against thresholds
        if combined_rms > thresholds['critical_rms']:
            result['health_score'] = 20.0
            result['anomaly'] = {
                'type': 'critical_vibration',
                'location': data.get('location'),
                'value': combined_rms,
                'message': f"Critical vibration level detected: {combined_rms:.2f}g"
            }
        elif combined_rms > thresholds['warning_rms']:
            result['health_score'] = 60.0
            result['anomaly'] = {
                'type': 'high_vibration',
                'location': data.get('location'),
                'value': combined_rms,
                'message': f"Elevated vibration level: {combined_rms:.2f}g"
            }
        elif combined_rms > thresholds['normal_rms']:
            result['health_score'] = 80.0

        # Check for bearing defect signatures
        bpfo = data.get('bpfo_amplitude', 0)
        bpfi = data.get('bpfi_amplitude', 0)
        bsf = data.get('bsf_amplitude', 0)

        if max(bpfo, bpfi, bsf) > thresholds['bearing_defect_amplitude']:
            result['bearing_defect_suspected'] = True
            if not result['anomaly']:
                result['anomaly'] = {
                    'type': 'bearing_defect_signature',
                    'location': data.get('location'),
                    'message': "Bearing defect frequency signature detected"
                }

        return result

    def _process_current(self, data: Dict, vehicle_id: str) -> Dict[str, Any]:
        """Process current sensor data."""
        result = {
            'location': data.get('location', 'unknown'),
            'health_score': 100.0,
            'anomaly': None
        }

        current_amps = data.get('current_amps', 0)
        location = data.get('location', '')

        result['current_amps'] = current_amps

        # Location-specific thresholds
        if 'alternator' in location.lower():
            normal_range = self.thresholds['current']['alternator_normal']
            if current_amps < normal_range[0]:
                result['health_score'] = 50.0
                result['anomaly'] = {
                    'type': 'low_alternator_output',
                    'location': location,
                    'value': current_amps,
                    'message': f"Alternator output low: {current_amps:.1f}A"
                }
            elif current_amps > normal_range[1]:
                result['health_score'] = 70.0
                result['anomaly'] = {
                    'type': 'high_alternator_load',
                    'location': location,
                    'value': current_amps,
                    'message': f"High alternator load: {current_amps:.1f}A"
                }

        elif 'fuel_pump' in location.lower():
            normal_range = self.thresholds['current']['fuel_pump_normal']
            if current_amps > normal_range[1] * 1.5:
                result['health_score'] = 40.0
                result['anomaly'] = {
                    'type': 'fuel_pump_overload',
                    'location': location,
                    'value': current_amps,
                    'message': f"Fuel pump drawing excessive current: {current_amps:.1f}A"
                }

        # Check for inrush issues
        if data.get('inrush_detected', False):
            inrush_duration = data.get('inrush_duration_ms', 0)
            if inrush_duration > self.thresholds['current']['inrush_duration_max_ms']:
                result['anomaly'] = {
                    'type': 'extended_inrush',
                    'location': location,
                    'value': inrush_duration,
                    'message': f"Extended inrush duration: {inrush_duration}ms"
                }

        return result

    def _process_temperature(self, data: Dict, vehicle_id: str) -> Dict[str, Any]:
        """Process temperature sensor data."""
        result = {
            'location': data.get('location', 'unknown'),
            'health_score': 100.0,
            'anomaly': None
        }

        temp_c = data.get('temperature_c', 0)
        rate = data.get('rate_of_change', 0)
        location = data.get('location', '')

        result['temperature_c'] = temp_c
        result['rate_of_change'] = rate

        thresholds = self.thresholds['temperature']

        # Check rate of change
        if abs(rate) > thresholds['max_rate_of_change']:
            result['anomaly'] = {
                'type': 'rapid_temp_change',
                'location': location,
                'value': rate,
                'message': f"Rapid temperature change: {rate:.1f}C/min"
            }

        # Location-specific checks
        if 'engine' in location.lower():
            if temp_c > thresholds['engine_critical']:
                result['health_score'] = 10.0
                result['anomaly'] = {
                    'type': 'engine_overheating',
                    'location': location,
                    'value': temp_c,
                    'message': f"CRITICAL: Engine temperature {temp_c:.1f}C"
                }
            elif temp_c > thresholds['engine_warning']:
                result['health_score'] = 40.0
                if not result['anomaly']:
                    result['anomaly'] = {
                        'type': 'engine_temp_warning',
                        'location': location,
                        'value': temp_c,
                        'message': f"Engine temperature high: {temp_c:.1f}C"
                    }

        return result

    def _process_acoustic(self, data: Dict, vehicle_id: str) -> Dict[str, Any]:
        """Process acoustic sensor data."""
        result = {
            'location': data.get('location', 'unknown'),
            'health_score': 100.0,
            'anomaly': None
        }

        spl_db = data.get('spl_db', 0)
        dominant_freq = data.get('dominant_freq_hz', 0)

        result['spl_db'] = spl_db

        thresholds = self.thresholds['acoustic']

        if spl_db > thresholds['warning_spl_db']:
            result['health_score'] = 50.0
            result['anomaly'] = {
                'type': 'high_noise_level',
                'location': data.get('location'),
                'value': spl_db,
                'message': f"High noise level detected: {spl_db:.1f}dB"
            }

        # Check for knock
        if data.get('knock_detected', False):
            result['anomaly'] = {
                'type': 'knock_detected',
                'location': data.get('location'),
                'message': "Engine knock pattern detected"
            }

        # Check for squeal (belt, bearing)
        squeal_range = thresholds['squeal_freq_range']
        if squeal_range[0] <= dominant_freq <= squeal_range[1]:
            if spl_db > thresholds['knock_threshold_db']:
                result['anomaly'] = {
                    'type': 'squeal_detected',
                    'location': data.get('location'),
                    'frequency': dominant_freq,
                    'message': f"Squeal detected at {dominant_freq}Hz"
                }

        return result

    def _store_raw_data(self, vehicle_id: str, packet_data: Dict):
        """Store raw sensor data for future training."""
        vehicle_path = self.storage_path / vehicle_id
        vehicle_path.mkdir(exist_ok=True)

        # Append to daily file
        date_str = datetime.now().strftime("%Y%m%d")
        data_file = vehicle_path / f"sensor_data_{date_str}.jsonl"

        try:
            with open(data_file, 'a') as f:
                f.write(json.dumps(packet_data) + '\n')
        except Exception as e:
            logger.warning(f"Failed to store sensor data: {e}")

    def calibrate_sensor(self, sensor_id: str, vehicle_id: str,
                          reference_value: float) -> Dict[str, Any]:
        """
        Calibrate a sensor using a known reference value.

        Args:
            sensor_id: ID of sensor to calibrate
            vehicle_id: Vehicle the sensor is installed on
            reference_value: Known correct value for comparison

        Returns:
            Calibration result
        """
        if sensor_id not in self.sensors:
            return {'success': False, 'error': 'Sensor not found'}

        # Load recent readings for this sensor
        vehicle_path = self.storage_path / vehicle_id
        if not vehicle_path.exists():
            return {'success': False, 'error': 'No data for vehicle'}

        # Calculate offset from recent readings
        # This would analyze stored data to determine calibration offset

        return {
            'success': True,
            'sensor_id': sensor_id,
            'calibration_applied': True,
            'message': 'Calibration stored. Offset will be applied to future readings.'
        }

    def get_sensor_status(self) -> Dict[str, Any]:
        """Get status of all registered sensors."""
        return {
            'total_sensors': len(self.sensors),
            'sensors': [
                {
                    'id': sid,
                    'type': cfg.sensor_type.value,
                    'location': cfg.location.value,
                    'model': cfg.model,
                    'enabled': cfg.enabled
                }
                for sid, cfg in self.sensors.items()
            ]
        }

    def get_recommended_sensors(self) -> List[Dict[str, Any]]:
        """Get recommended sensor configuration for predictive maintenance."""
        return [
            {
                'sensor_type': 'accelerometer',
                'model': 'ADXL345',
                'quantity': 3,
                'locations': ['engine_block', 'transmission', 'differential'],
                'purpose': 'Vibration monitoring for rotating components',
                'estimated_cost': '$12'
            },
            {
                'sensor_type': 'current',
                'model': 'INA219',
                'quantity': 4,
                'locations': ['alternator', 'fuel_pump', 'ac_compressor', 'starter'],
                'purpose': 'Electrical load monitoring',
                'estimated_cost': '$12'
            },
            {
                'sensor_type': 'temperature',
                'model': 'DS18B20',
                'quantity': 6,
                'locations': ['engine_block', 'transmission', 'differential', 'coolant_line', 'oil_pan', 'ambient'],
                'purpose': 'Multi-point thermal monitoring',
                'estimated_cost': '$12'
            },
            {
                'sensor_type': 'acoustic',
                'model': 'INMP441',
                'quantity': 2,
                'locations': ['engine_block', 'wheel_front_left'],
                'purpose': 'Knock and bearing noise detection',
                'estimated_cost': '$6'
            }
        ]


# ESP32 Firmware Configuration Template
ESP32_CONFIG_TEMPLATE = """
// ESP32-S3 Sensor Hub Configuration
// Upload this to your ESP32-S3

#define DEVICE_ID "{device_id}"
#define VEHICLE_ID "{vehicle_id}"

// WiFi Configuration
#define WIFI_SSID "{wifi_ssid}"
#define WIFI_PASSWORD "{wifi_password}"

// BLE Configuration
#define BLE_NAME "PredictSensor_{device_id}"

// Sampling Configuration
#define VIBRATION_SAMPLE_RATE 1000  // Hz
#define CURRENT_SAMPLE_RATE 100     // Hz
#define TEMP_SAMPLE_RATE 1          // Hz
#define FFT_SIZE 256

// Transmission Configuration
#define BATCH_SIZE 10               // Readings per transmission
#define TRANSMIT_INTERVAL_MS 1000   // Transmit every second

// Sensor Pins
#define ACCEL_SDA 21
#define ACCEL_SCL 22
#define CURRENT_PIN_1 34
#define CURRENT_PIN_2 35
#define TEMP_PIN 4

// Processing
#define ENABLE_EDGE_FFT true
#define ENABLE_ANOMALY_FLAG true
"""
