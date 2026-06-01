"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: OBD Connection Manager

OBD Connection Manager
Handles connection to ELM327/STN OBD-II adapter
"""

import obd
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class OBDConnectionManager:
    """Manages OBD-II adapter connection and commands"""

    def __init__(self, port: Optional[str] = None, baudrate: int = 38400):
        """
        Initialize OBD connection

        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Communication speed (38400 is standard for ELM327)
        """
        self.port = port
        self.baudrate = baudrate
        self.connection: Optional[obd.OBD] = None
        self._connect()

    def _connect(self):
        """Establish connection to OBD adapter"""
        try:
            if self.port:
                self.connection = obd.OBD(portstr=self.port, baudrate=self.baudrate)
            else:
                # Auto-detect adapter
                self.connection = obd.OBD()

            if self.connection.is_connected():
                logger.info(f"✅ OBD adapter connected on {self.connection.port_name()}")
                logger.info(f"   Protocol: {self.connection.protocol_name()}")
            else:
                logger.error("❌ Failed to connect to OBD adapter")
                self.connection = None

        except Exception as e:
            logger.error(f"OBD connection error: {e}")
            self.connection = None

    def is_connected(self) -> bool:
        """Check if adapter is connected"""
        return self.connection is not None and self.connection.is_connected()

    def reconnect(self):
        """Attempt to reconnect to adapter"""
        if self.connection:
            self.connection.close()
        self._connect()

    def read_dtc_codes(self) -> List[Tuple[str, str]]:
        """
        Read Diagnostic Trouble Codes from vehicle

        Returns:
            List of tuples: [(code, description), ...]
            Example: [("P0420", "Catalyst System Efficiency Below Threshold"), ...]
        """
        if not self.is_connected():
            raise ConnectionError("OBD adapter not connected")

        try:
            # Query DTCs using Mode 03 command
            response = self.connection.query(obd.commands.GET_DTC)

            if response.is_null():
                logger.warning("No DTC response from vehicle")
                return []

            # response.value is a list of tuples: [("P0420", "Catalyst..."), ...]
            dtc_list = response.value if response.value else []

            logger.info(f"Read {len(dtc_list)} DTC codes from vehicle")
            return dtc_list

        except Exception as e:
            logger.error(f"Error reading DTCs: {e}")
            raise

    def clear_dtc_codes(self) -> bool:
        """
        Clear all DTCs and turn off Check Engine Light (MIL)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            raise ConnectionError("OBD adapter not connected")

        try:
            # Send Mode 04 command to clear DTCs
            response = self.connection.query(obd.commands.CLEAR_DTC)

            # Verify DTCs were cleared
            dtc_check = self.connection.query(obd.commands.GET_DTC)
            cleared = len(dtc_check.value) == 0 if dtc_check.value else True

            if cleared:
                logger.info("✅ DTCs cleared successfully")
            else:
                logger.warning("⚠️ Some DTCs may remain")

            return cleared

        except Exception as e:
            logger.error(f"Error clearing DTCs: {e}")
            raise

    def read_odometer(self, make: str, model: str, year: int) -> Optional[float]:
        """
        Read odometer from vehicle using make/model-specific PID

        Args:
            make: Vehicle manufacturer (e.g., "Nissan")
            model: Vehicle model (e.g., "Patrol")
            year: Vehicle year

        Returns:
            Odometer reading in kilometers, or None if unavailable
        """
        if not self.is_connected():
            raise ConnectionError("OBD adapter not connected")

        try:
            # Get vehicle-specific PID
            pid = self._get_odometer_pid(make, model, year)

            if not pid:
                logger.warning(f"No odometer PID defined for {year} {make} {model}")
                return None

            # Query custom PID
            cmd = obd.OBDCommand(
                "ODOMETER",
                "Get odometer reading",
                pid,
                7,  # Response bytes
                self._parse_odometer_response
            )

            response = self.connection.query(cmd)

            if response.is_null():
                logger.warning("No odometer response from vehicle")
                return None

            odometer_km = response.value
            logger.info(f"Odometer reading: {odometer_km:.1f} km")
            return odometer_km

        except Exception as e:
            logger.error(f"Error reading odometer: {e}")
            return None

    def _get_odometer_pid(self, make: str, model: str, year: int) -> Optional[str]:
        """
        Get manufacturer-specific PID for odometer reading

        Returns:
            PID command string (e.g., "22 20 01" for Nissan)
        """
        # Vehicle-specific PID mapping
        pid_map = {
            "Nissan": "22 20 01",
            "Infiniti": "22 20 01",
            "Honda": "22 A6",
            "Acura": "22 A6",
            "Toyota": "22 0D",
            "Lexus": "22 0D",
            "Jeep": "22 22 F4",
            "Dodge": "22 22 F4",
            "Chrysler": "22 22 F4",
        }

        return pid_map.get(make)

    def _parse_odometer_response(self, messages):
        """Parse odometer response bytes"""
        # Implementation depends on manufacturer
        # Example for Nissan: bytes 3-5 contain odometer in km
        if not messages or len(messages[0].data) < 5:
            return None

        data = messages[0].data
        odometer_km = (data[3] << 16) + (data[4] << 8) + data[5]
        return float(odometer_km)

    def close(self):
        """Close OBD connection"""
        if self.connection:
            self.connection.close()
            logger.info("OBD connection closed")


# Global connection instance
_obd_manager: Optional[OBDConnectionManager] = None


def get_obd_manager() -> OBDConnectionManager:
    """Get singleton OBD connection manager"""
    global _obd_manager

    if _obd_manager is None or not _obd_manager.is_connected():
        _obd_manager = OBDConnectionManager()

    return _obd_manager
