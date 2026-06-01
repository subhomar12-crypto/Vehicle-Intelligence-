"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Esp32 Sensor Bridge

ESP32 External Sensor Bridge
============================
Integration layer for ESP32-S3 external sensors (vibration, current, temperature, acoustic).
Receives data via HTTP/MQTT and integrates with the prediction engine.

Features:
- HTTP REST API for ESP32 data submission
- MQTT client for real-time sensor streams
- Sensor data validation and calibration
- Integration with prediction engine
- Sensor health monitoring
- Data buffering and batching
"""

import json
import logging
import threading
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import socket
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)

# MQTT support (optional)
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.info("paho-mqtt not installed - MQTT support disabled")


@dataclass
class SensorReading:
    """A single sensor reading from ESP32."""
    sensor_id: str
    sensor_type: str  # vibration, current, temperature, acoustic
    vehicle_id: str
    timestamp: str
    value: float
    unit: str
    location: str  # engine, alternator, wheel_fl, etc.
    raw_value: Optional[float] = None
    calibration_offset: float = 0.0
    quality: float = 1.0  # 0-1 data quality score


@dataclass
class SensorConfig:
    """Configuration for an external sensor."""
    sensor_id: str
    sensor_type: str
    location: str
    unit: str
    min_value: float
    max_value: float
    calibration_offset: float = 0.0
    calibration_scale: float = 1.0
    sampling_rate_hz: float = 10.0
    alert_threshold_low: Optional[float] = None
    alert_threshold_high: Optional[float] = None
    enabled: bool = True


@dataclass
class SensorHealth:
    """Health status of a sensor."""
    sensor_id: str
    last_reading: Optional[str]
    readings_count: int
    error_count: int
    avg_quality: float
    is_online: bool
    battery_level: Optional[float]


class ESP32SensorBridge:
    """
    Bridge for ESP32-S3 external sensor integration.
    Handles data reception, validation, and integration with prediction engine.
    """

    def __init__(
        self,
        http_port: int = 8085,
        mqtt_broker: str = None,
        mqtt_port: int = 1883,
        storage_path: str = None
    ):
        """Initialize the sensor bridge."""
        self.http_port = http_port
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port

        self.storage_path = Path(storage_path or str(CONFIG.DATA_DIR / "external_sensors"))
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.storage_path / "sensor_data.db"
        self._init_database()

        # Sensor configurations
        self.sensors: Dict[str, SensorConfig] = {}
        self._load_sensor_configs()

        # Data buffers (per vehicle)
        self.data_buffers: Dict[str, deque] = {}
        self.buffer_size = 1000

        # Sensor health tracking
        self.sensor_health: Dict[str, SensorHealth] = {}

        # Callbacks for real-time data
        self.data_callbacks: List[Callable] = []
        self.alert_callbacks: List[Callable] = []

        # Server threads
        self.http_server: Optional[HTTPServer] = None
        self.http_thread: Optional[threading.Thread] = None
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_thread: Optional[threading.Thread] = None

        self.running = False

        logger.info(f"ESP32SensorBridge initialized (HTTP port: {http_port})")

    def _init_database(self):
        """Initialize SQLite database for sensor data."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Sensor readings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                location TEXT,
                raw_value REAL,
                quality REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Aggregated data (hourly summaries)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_aggregates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                hour_timestamp TEXT NOT NULL,
                min_value REAL,
                max_value REAL,
                avg_value REAL,
                std_value REAL,
                sample_count INTEGER,
                UNIQUE(sensor_id, vehicle_id, hour_timestamp)
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_vehicle ON sensor_readings(vehicle_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON sensor_readings(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_sensor ON sensor_readings(sensor_id)")

        conn.commit()
        conn.close()

    def _load_sensor_configs(self):
        """Load sensor configurations."""
        config_file = self.storage_path / "sensor_configs.json"

        # Default sensor configurations
        default_configs = [
            SensorConfig(
                sensor_id="VIB_ENGINE_01",
                sensor_type="vibration",
                location="engine_block",
                unit="g",
                min_value=0,
                max_value=10,
                alert_threshold_high=5.0
            ),
            SensorConfig(
                sensor_id="VIB_ALT_01",
                sensor_type="vibration",
                location="alternator",
                unit="g",
                min_value=0,
                max_value=5,
                alert_threshold_high=3.0
            ),
            SensorConfig(
                sensor_id="CURR_ALT_01",
                sensor_type="current",
                location="alternator",
                unit="A",
                min_value=0,
                max_value=150,
                alert_threshold_low=10,
                alert_threshold_high=120
            ),
            SensorConfig(
                sensor_id="CURR_BATT_01",
                sensor_type="current",
                location="battery",
                unit="A",
                min_value=-100,
                max_value=100
            ),
            SensorConfig(
                sensor_id="TEMP_ENG_01",
                sensor_type="temperature",
                location="engine_block",
                unit="C",
                min_value=-40,
                max_value=150,
                alert_threshold_high=120
            ),
            SensorConfig(
                sensor_id="TEMP_TRANS_01",
                sensor_type="temperature",
                location="transmission",
                unit="C",
                min_value=-40,
                max_value=150,
                alert_threshold_high=110
            ),
            SensorConfig(
                sensor_id="TEMP_BRAKE_FL",
                sensor_type="temperature",
                location="brake_front_left",
                unit="C",
                min_value=-40,
                max_value=400,
                alert_threshold_high=300
            ),
            SensorConfig(
                sensor_id="ACOU_ENGINE_01",
                sensor_type="acoustic",
                location="engine",
                unit="dB",
                min_value=0,
                max_value=120,
                alert_threshold_high=100
            ),
        ]

        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    saved_configs = json.load(f)
                    for cfg in saved_configs:
                        self.sensors[cfg['sensor_id']] = SensorConfig(**cfg)
            except Exception as e:
                logger.warning(f"Failed to load sensor configs: {e}")

        # Add defaults if not present
        for cfg in default_configs:
            if cfg.sensor_id not in self.sensors:
                self.sensors[cfg.sensor_id] = cfg

        self._save_sensor_configs()

    def _save_sensor_configs(self):
        """Save sensor configurations."""
        config_file = self.storage_path / "sensor_configs.json"
        try:
            configs = [asdict(cfg) for cfg in self.sensors.values()]
            with open(config_file, 'w') as f:
                json.dump(configs, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save sensor configs: {e}")

    def add_sensor(self, config: SensorConfig):
        """Add or update a sensor configuration."""
        self.sensors[config.sensor_id] = config
        self._save_sensor_configs()
        logger.info(f"Added sensor: {config.sensor_id}")

    def remove_sensor(self, sensor_id: str):
        """Remove a sensor configuration."""
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            self._save_sensor_configs()

    # =========================================================================
    # Data Reception
    # =========================================================================

    def process_reading(self, reading: SensorReading) -> Dict[str, Any]:
        """
        Process an incoming sensor reading.

        Returns:
            Dict with processing result and any alerts
        """
        result = {'success': True, 'alerts': []}

        # Validate sensor
        if reading.sensor_id not in self.sensors:
            # Auto-register unknown sensor with defaults
            self.sensors[reading.sensor_id] = SensorConfig(
                sensor_id=reading.sensor_id,
                sensor_type=reading.sensor_type,
                location=reading.location or 'unknown',
                unit=reading.unit or '',
                min_value=0,
                max_value=1000
            )

        config = self.sensors[reading.sensor_id]

        # Apply calibration
        calibrated_value = (reading.value * config.calibration_scale) + config.calibration_offset
        reading.raw_value = reading.value
        reading.value = calibrated_value

        # Validate range
        if calibrated_value < config.min_value or calibrated_value > config.max_value:
            reading.quality = 0.5  # Reduced quality for out-of-range

        # Check alerts
        if config.alert_threshold_high and calibrated_value > config.alert_threshold_high:
            alert = {
                'sensor_id': reading.sensor_id,
                'type': 'high_threshold',
                'value': calibrated_value,
                'threshold': config.alert_threshold_high,
                'timestamp': reading.timestamp
            }
            result['alerts'].append(alert)
            self._trigger_alert(alert)

        if config.alert_threshold_low and calibrated_value < config.alert_threshold_low:
            alert = {
                'sensor_id': reading.sensor_id,
                'type': 'low_threshold',
                'value': calibrated_value,
                'threshold': config.alert_threshold_low,
                'timestamp': reading.timestamp
            }
            result['alerts'].append(alert)
            self._trigger_alert(alert)

        # Store reading
        self._store_reading(reading)

        # Add to buffer
        if reading.vehicle_id not in self.data_buffers:
            self.data_buffers[reading.vehicle_id] = deque(maxlen=self.buffer_size)
        self.data_buffers[reading.vehicle_id].append(asdict(reading))

        # Update health
        self._update_sensor_health(reading)

        # Trigger callbacks
        for callback in self.data_callbacks:
            try:
                callback(reading)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return result

    def _store_reading(self, reading: SensorReading):
        """Store reading in database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sensor_readings
                (sensor_id, sensor_type, vehicle_id, timestamp, value, unit,
                 location, raw_value, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reading.sensor_id, reading.sensor_type, reading.vehicle_id,
                reading.timestamp, reading.value, reading.unit,
                reading.location, reading.raw_value, reading.quality
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store reading: {e}")

    def _update_sensor_health(self, reading: SensorReading):
        """Update sensor health status."""
        if reading.sensor_id not in self.sensor_health:
            self.sensor_health[reading.sensor_id] = SensorHealth(
                sensor_id=reading.sensor_id,
                last_reading=None,
                readings_count=0,
                error_count=0,
                avg_quality=1.0,
                is_online=True,
                battery_level=None
            )

        health = self.sensor_health[reading.sensor_id]
        health.last_reading = reading.timestamp
        health.readings_count += 1
        health.is_online = True

        # Rolling average quality
        health.avg_quality = (health.avg_quality * 0.95) + (reading.quality * 0.05)

    def _trigger_alert(self, alert: Dict):
        """Trigger alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    # =========================================================================
    # HTTP Server
    # =========================================================================

    def start_http_server(self):
        """Start HTTP server for ESP32 data submission."""
        bridge = self

        class SensorHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress default logging

            def do_POST(self):
                if self.path == '/sensor/data':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)

                    try:
                        data = json.loads(post_data.decode('utf-8'))

                        # Handle batch or single reading
                        readings = data if isinstance(data, list) else [data]

                        results = []
                        for item in readings:
                            reading = SensorReading(
                                sensor_id=item.get('sensor_id', 'unknown'),
                                sensor_type=item.get('sensor_type', 'unknown'),
                                vehicle_id=item.get('vehicle_id', 'default'),
                                timestamp=item.get('timestamp', datetime.now().isoformat()),
                                value=float(item.get('value', 0)),
                                unit=item.get('unit', ''),
                                location=item.get('location', 'unknown')
                            )
                            result = bridge.process_reading(reading)
                            results.append(result)

                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'success': True,
                            'processed': len(results)
                        }).encode())

                    except Exception as e:
                        self.send_response(400)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'error': str(e)
                        }).encode())

                elif self.path == '/sensor/register':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)

                    try:
                        data = json.loads(post_data.decode('utf-8'))
                        config = SensorConfig(**data)
                        bridge.add_sensor(config)

                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'success': True,
                            'sensor_id': config.sensor_id
                        }).encode())

                    except Exception as e:
                        self.send_response(400)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'error': str(e)
                        }).encode())

                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                if self.path == '/sensor/health':
                    health_data = {
                        sid: asdict(h) for sid, h in bridge.sensor_health.items()
                    }

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(health_data).encode())

                elif self.path == '/sensor/configs':
                    configs = {
                        sid: asdict(cfg) for sid, cfg in bridge.sensors.items()
                    }

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(configs).encode())

                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            self.http_server = HTTPServer(('0.0.0.0', self.http_port), SensorHandler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever)
            self.http_thread.daemon = True
            self.http_thread.start()
            logger.info(f"ESP32 HTTP server started on port {self.http_port}")
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")

    # =========================================================================
    # MQTT Client
    # =========================================================================

    def start_mqtt_client(self):
        """Start MQTT client for real-time sensor streams."""
        if not MQTT_AVAILABLE or not self.mqtt_broker:
            return

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("MQTT connected")
                client.subscribe("sensors/#")
            else:
                logger.error(f"MQTT connection failed: {rc}")

        def on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode())
                reading = SensorReading(
                    sensor_id=data.get('sensor_id', msg.topic.split('/')[-1]),
                    sensor_type=data.get('sensor_type', 'unknown'),
                    vehicle_id=data.get('vehicle_id', 'default'),
                    timestamp=data.get('timestamp', datetime.now().isoformat()),
                    value=float(data.get('value', 0)),
                    unit=data.get('unit', ''),
                    location=data.get('location', 'unknown')
                )
                self.process_reading(reading)
            except Exception as e:
                logger.error(f"MQTT message error: {e}")

        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_message = on_message
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)

            self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever)
            self.mqtt_thread.daemon = True
            self.mqtt_thread.start()
            logger.info(f"MQTT client connected to {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")

    # =========================================================================
    # Data Retrieval
    # =========================================================================

    def get_recent_data(
        self,
        vehicle_id: str,
        sensor_type: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """Get recent sensor data for a vehicle."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        since = (datetime.now() - timedelta(hours=hours)).isoformat()

        query = """
            SELECT * FROM sensor_readings
            WHERE vehicle_id = ? AND timestamp >= ?
        """
        params = [vehicle_id, since]

        if sensor_type:
            query += " AND sensor_type = ?"
            params.append(sensor_type)

        query += " ORDER BY timestamp DESC LIMIT 1000"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        readings = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return readings

    def get_aggregated_data(
        self,
        vehicle_id: str,
        sensor_id: str,
        days: int = 7
    ) -> List[Dict]:
        """Get hourly aggregated data."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT * FROM sensor_aggregates
            WHERE vehicle_id = ? AND sensor_id = ? AND hour_timestamp >= ?
            ORDER BY hour_timestamp
        """, (vehicle_id, sensor_id, since))

        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return data

    def get_sensor_summary(self, vehicle_id: str) -> Dict[str, Any]:
        """Get summary of all sensors for a vehicle."""
        summary = {
            'vehicle_id': vehicle_id,
            'sensors': {},
            'last_update': None,
            'online_count': 0,
            'total_readings_24h': 0
        }

        # Get recent readings per sensor type
        for sensor_type in ['vibration', 'current', 'temperature', 'acoustic']:
            data = self.get_recent_data(vehicle_id, sensor_type, hours=24)
            if data:
                values = [d['value'] for d in data]
                summary['sensors'][sensor_type] = {
                    'count': len(data),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'latest': data[0]['value'],
                    'latest_time': data[0]['timestamp']
                }
                summary['total_readings_24h'] += len(data)

                if not summary['last_update'] or data[0]['timestamp'] > summary['last_update']:
                    summary['last_update'] = data[0]['timestamp']

        # Count online sensors
        for health in self.sensor_health.values():
            if health.is_online:
                summary['online_count'] += 1

        return summary

    def get_features_for_prediction(self, vehicle_id: str) -> Dict[str, float]:
        """
        Get external sensor features formatted for prediction engine integration.

        Returns dict with feature names matching external_sensor_schema.py
        """
        features = {}

        # Get recent data (last hour)
        for sensor_type in ['vibration', 'current', 'temperature', 'acoustic']:
            data = self.get_recent_data(vehicle_id, sensor_type, hours=1)

            if not data:
                continue

            # Group by location
            by_location = {}
            for reading in data:
                loc = reading.get('location', 'unknown')
                if loc not in by_location:
                    by_location[loc] = []
                by_location[loc].append(reading['value'])

            # Calculate features
            for loc, values in by_location.items():
                import numpy as np
                prefix = f"ext_{sensor_type}_{loc}"

                features[f"{prefix}_mean"] = float(np.mean(values))
                features[f"{prefix}_max"] = float(np.max(values))
                features[f"{prefix}_std"] = float(np.std(values))

                if sensor_type == 'vibration':
                    # RMS for vibration
                    features[f"{prefix}_rms"] = float(np.sqrt(np.mean(np.square(values))))

        return features

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self):
        """Start the sensor bridge."""
        self.running = True
        self.start_http_server()
        if self.mqtt_broker:
            self.start_mqtt_client()
        logger.info("ESP32 Sensor Bridge started")

    def stop(self):
        """Stop the sensor bridge."""
        self.running = False
        if self.http_server:
            self.http_server.shutdown()
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        logger.info("ESP32 Sensor Bridge stopped")

    def register_data_callback(self, callback: Callable):
        """Register callback for incoming data."""
        self.data_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable):
        """Register callback for sensor alerts."""
        self.alert_callbacks.append(callback)


# Singleton instance
_sensor_bridge = None

def get_sensor_bridge() -> ESP32SensorBridge:
    """Get the singleton ESP32SensorBridge instance."""
    global _sensor_bridge
    if _sensor_bridge is None:
        _sensor_bridge = ESP32SensorBridge()
    return _sensor_bridge
