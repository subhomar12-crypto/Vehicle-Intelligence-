"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Mobile Data Bridge

Mobile Data Bridge - Integrates Mobile OBD app (Android/iOS) with main desktop application
Converts Mobile JSON data to unified frame format and feeds to AI pipeline
"""

from PySide6.QtCore import QObject, Signal, QThread, QTimer
import json
import logging
import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Import config to get server database path
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None
    logger = logging.getLogger(__name__)
    logger.warning("Could not import config - server polling may not work")

logger = logging.getLogger(__name__)


class MobileDataBridge(QObject):
    """
    Bridge between Mobile OBD app and desktop application
    - Receives data from mobile server
    - Polls server database for live data
    - Converts to unified frame format
    - Emits to main application data pipeline
    """

    # Signals
    mobile_data_ready = Signal(dict)  # Unified frame data
    connection_status = Signal(str, str)  # (device_id, status: connected/disconnected)
    error_occurred = Signal(str)  # Error message
    server_polling_active = Signal(bool)  # Server polling status

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self.current_profile_id = None
        self.last_data_time = None
        self.polling_timer = None
        self.is_polling = False
        logger.info("Mobile Data Bridge initialized")

    def set_active_profile(self, profile_name, profile_id=None):
        """Set the currently active profile for server polling"""
        self.current_profile = profile_name
        self.current_profile_id = profile_id
        logger.info(f"Mobile bridge profile set to: {profile_name} (ID: {profile_id})")

    def start_server_polling(self, profile_id: int, interval_ms: int = 1000):
        """
        Start polling the server database for live vehicle data.

        Args:
            profile_id: Vehicle profile ID to poll data for
            interval_ms: Polling interval in milliseconds (default 1000 = 1 second)
        """
        if self.polling_timer is None:
            self.polling_timer = QTimer()
            self.polling_timer.timeout.connect(self._poll_server_database)

        self.current_profile_id = profile_id
        self.polling_timer.start(interval_ms)
        self.is_polling = True
        self.server_polling_active.emit(True)
        logger.info(f"Started server polling for profile_id={profile_id} every {interval_ms}ms")

    def stop_server_polling(self):
        """Stop polling the server database"""
        if self.polling_timer and self.polling_timer.isActive():
            self.polling_timer.stop()
            self.is_polling = False
            self.server_polling_active.emit(False)
            logger.info("Stopped server polling")

    def _poll_server_database(self):
        """Poll the server database for the latest vehicle data"""
        if not CONFIG:
            logger.warning("Config not available - cannot poll server")
            return

        if self.current_profile_id is None:
            return

        try:
            server_db_path = CONFIG.SERVER_DB_PATH
            if not Path(server_db_path).exists():
                logger.debug(f"Server database not found: {server_db_path}")
                return

            conn = sqlite3.connect(str(server_db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get latest vehicle data for this profile
            c.execute('''
                SELECT
                    vehicle_id,
                    profile_id,
                    timestamp,
                    rpm,
                    speed,
                    coolant_temp,
                    battery_voltage,
                    engine_load,
                    throttle_pos,
                    fuel_level,
                    intake_temp,
                    maf_rate,
                    latitude,
                    longitude,
                    acceleration_x,
                    acceleration_y,
                    acceleration_z
                FROM vehicle_data
                WHERE profile_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (self.current_profile_id,))

            row = c.fetchone()
            conn.close()

            if row:
                # Convert server data to mobile data format
                mobile_data = {
                    'timestamp': datetime.fromtimestamp(row['timestamp']).isoformat(),
                    'vehicle_id': row['vehicle_id'] or f"profile_{self.current_profile_id}",
                    'source': 'server_database',
                    'obd': {
                        'rpm': row['rpm'],
                        'speed_kmh': row['speed'],
                        'coolant_temp_c': row['coolant_temp'],
                        'voltage_batt_v': row['battery_voltage'],
                        'engine_load_pct': row['engine_load'],
                        'throttle_position_pct': row['throttle_pos'],
                        'fuel_level_pct': row['fuel_level'],
                        'intake_air_temp_c': row['intake_temp'],
                        'maf_gps': row['maf_rate']
                    },
                    'gps': {
                        'latitude': row['latitude'],
                        'longitude': row['longitude']
                    } if row['latitude'] and row['longitude'] else None,
                    'accelerometer': {
                        'acceleration_x': row['acceleration_x'],
                        'acceleration_y': row['acceleration_y'],
                        'acceleration_z': row['acceleration_z']
                    } if row['acceleration_x'] else None
                }

                # Process the data (this will emit mobile_data_ready signal)
                self.process_mobile_data(mobile_data)

        except Exception as e:
            logger.error(f"Error polling server database: {e}")
            self.error_occurred.emit(f"Server polling error: {e}")

    def process_mobile_data(self, mobile_data: Dict[str, Any]):
        """
        Process incoming Mobile data and convert to unified frame format

        Mobile data format:
        {
          "timestamp": "2025-12-09T20:15:22Z",
          "vehicle_id": "nissan_patrol_2020",
          "source": "android_predictobd",
          "obd": {
            "rpm": 2500,
            "speed_kmh": 80,
            "coolant_temp_c": 90,
            ...
          },
          "vibration": {...},
          "missing_data_summary": []
        }
        """
        try:
            # Extract OBD data
            # Try to get nested 'obd' object, otherwise use the root data
            obd_data = mobile_data.get('obd')
            if not obd_data:
                obd_data = mobile_data
            
            vehicle_id = mobile_data.get('vehicle_id', self.current_profile)
            timestamp = mobile_data.get('timestamp', datetime.now().isoformat())

            # Convert to unified frame format
            unified_frame = self._convert_to_unified_frame(obd_data, mobile_data)

            # Add metadata
            unified_frame['metadata'] = {
                'source': 'mobile_app',
                'vehicle_id': vehicle_id,
                'timestamp': timestamp,
                'profile_name': self.current_profile
            }

            # Emit signal
            self.mobile_data_ready.emit(unified_frame)
            self.last_data_time = datetime.now()

            # Update connection status
            self.connection_status.emit(vehicle_id, 'connected')

            logger.debug(f"Processed Mobile data for {vehicle_id}")

        except Exception as e:
            error_msg = f"Error processing Mobile data: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _convert_to_unified_frame(self, obd_data: Dict, full_data: Dict) -> Dict:
        """
        Convert Mobile OBD format to unified frame format

        Maps Mobile field names to unified frame structure
        """
        unified = {
            'obd': {
                'core_signals': {},
                'extended_signals': {},
                'diagnostic_signals': {},
                'derived_metrics': {}
            },
            'data_quality': {
                'timestamp': datetime.now().isoformat(),
                'has_missing': False,
                'required_missing': [],
                'optional_missing': []
            }
        }

        # Map Mobile fields to unified core_signals
        field_mapping = {
            # Mobile field -> (unified field, unit, pid)
            'rpm': ('rpm', 'rpm', '0C'),
            'speed_kmh': ('speed', 'km/h', '0D'),
            'coolant_temp_c': ('coolant_temp', '°C', '05'),
            'intake_air_temp_c': ('intake_air_temp', '°C', '0F'),
            'ambient_air_temp_c': ('ambient_air_temp', '°C', '46'),
            'throttle_position_pct': ('throttle_position', '%', '11'),
            'engine_load_pct': ('engine_load', '%', '04'),
            'fuel_pressure_kpa': ('fuel_pressure', 'kPa', '0A'),
            'intake_manifold_pressure_kpa': ('intake_manifold_pressure', 'kPa', '0B'),
            'timing_advance_deg': ('timing_advance', 'degrees', '0E'),
            'maf_gps': ('maf', 'g/s', '10'),
            'voltage_batt_v': ('battery_voltage', 'V', '42'),
            'oil_temp_c': ('oil_temp', '°C', '5C'),
            'fuel_level_pct': ('fuel_level', '%', '2F'),
        }

        # Process core signals
        for mobile_field, (unified_field, unit, pid) in field_mapping.items():
            value = obd_data.get(mobile_field)
            if value is not None:
                unified['obd']['core_signals'][unified_field] = {
                    'value': value,
                    'unit': unit,
                    'pid': pid
                }
                # Flatten for AI compatibility (Critical for UnifiedAIModule)
                unified[unified_field] = value
            else:
                unified['data_quality']['optional_missing'].append(unified_field)

        # Process fuel trims
        if obd_data.get('short_term_fuel_trim_b1') is not None:
            val = obd_data.get('short_term_fuel_trim_b1')
            unified['obd']['extended_signals']['short_fuel_trim'] = {
                'value': val,
                'unit': '%',
                'pid': '06'
            }
            unified['short_fuel_trim'] = val
            unified['short_fuel_trim_1'] = val  # Alias for some AI checks

        if obd_data.get('long_term_fuel_trim_b1') is not None:
            val = obd_data.get('long_term_fuel_trim_b1')
            unified['obd']['extended_signals']['long_fuel_trim'] = {
                'value': val,
                'unit': '%',
                'pid': '07'
            }
            unified['long_fuel_trim'] = val
            unified['long_fuel_trim_1'] = val  # Alias for some AI checks

        # Process DTC data
        dtc_list = obd_data.get('dtc_list', [])
        if dtc_list:
            unified['obd']['diagnostic_signals']['dtc_count'] = {
                'value': len(dtc_list),
                'unit': 'codes',
                'pid': '01'
            }
            unified['obd']['diagnostic_signals']['dtc_codes'] = dtc_list
            # Flatten DTCs for AI
            unified['dtc_count'] = len(dtc_list)
            unified['dtc_codes'] = dtc_list

        # Add vibration data if available
        vibration = full_data.get('vibration', {})
        if vibration.get('rms') is not None:
            unified['obd']['derived_metrics']['vibration_rms'] = {
                'value': vibration.get('rms'),
                'unit': 'g',
                'source': 'accelerometer'
            }

        # Check if any required data is missing
        unified['data_quality']['has_missing'] = len(unified['data_quality']['required_missing']) > 0

        return unified


class MobileDataReceiver(QThread):
    """
    Background thread that monitors mobile server for incoming data
    """
    data_received = Signal(dict)

    def __init__(self, mobile_server, parent=None):
        super().__init__(parent)
        self.mobile_server = mobile_server
        self.running = False

    def run(self):
        """Monitor mobile server and emit data when received"""
        self.running = True
        logger.info("Mobile data receiver thread started")

        # Connect to mobile server's data signal if available
        if hasattr(self.mobile_server, 'mobile_data_received'):
            self.mobile_server.mobile_data_received.connect(self.data_received.emit)

    def stop(self):
        """Stop the receiver thread"""
        self.running = False
        logger.info("Mobile data receiver thread stopped")
