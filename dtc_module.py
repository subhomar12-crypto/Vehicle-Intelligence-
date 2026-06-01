"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Dtc Module
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

from PySide6.QtCore import QObject, Signal, QThread

logger = logging.getLogger(__name__)

# Global alert manager reference (set by main application)
_alert_manager = None


def set_alert_manager(manager):
    """Set the global alert notification manager for DTC alerts"""
    global _alert_manager
    _alert_manager = manager


def get_alert_manager():
    """Get the global alert notification manager"""
    return _alert_manager


def get_alert_types():
    """Get AlertType enum from alert_notifications module"""
    try:
        from alert_notifications import AlertType
        return AlertType
    except ImportError:
        return None


def get_notification_priority():
    """Get NotificationPriority enum from alert_notifications module"""
    try:
        from alert_notifications import NotificationPriority
        return NotificationPriority
    except ImportError:
        return None


# ================================
# DTC CODE DATABASE
# ================================

DTC_DATABASE = {
    # Powertrain - Fuel and Air Metering
    "P0100": {"description": "Mass Air Flow Circuit Malfunction", "severity": "HIGH", "system": "Fuel/Air"},
    "P0101": {"description": "Mass Air Flow Circuit Range/Performance", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0102": {"description": "Mass Air Flow Circuit Low Input", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0103": {"description": "Mass Air Flow Circuit High Input", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0104": {"description": "Mass Air Flow Circuit Intermittent", "severity": "LOW", "system": "Fuel/Air"},
    "P0105": {"description": "Manifold Absolute Pressure Circuit Malfunction", "severity": "HIGH", "system": "Fuel/Air"},
    "P0106": {"description": "MAP Circuit Range/Performance Problem", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0110": {"description": "Intake Air Temperature Circuit Malfunction", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0115": {"description": "Engine Coolant Temperature Circuit Malfunction", "severity": "HIGH", "system": "Cooling"},
    "P0116": {"description": "Engine Coolant Temperature Circuit Range/Performance", "severity": "MEDIUM", "system": "Cooling"},
    "P0117": {"description": "Engine Coolant Temperature Circuit Low Input", "severity": "MEDIUM", "system": "Cooling"},
    "P0118": {"description": "Engine Coolant Temperature Circuit High Input", "severity": "MEDIUM", "system": "Cooling"},
    "P0120": {"description": "Throttle Position Sensor Circuit Malfunction", "severity": "HIGH", "system": "Fuel/Air"},
    "P0121": {"description": "Throttle Position Sensor Circuit Range/Performance", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0122": {"description": "Throttle Position Sensor Circuit Low Input", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0123": {"description": "Throttle Position Sensor Circuit High Input", "severity": "MEDIUM", "system": "Fuel/Air"},
    "P0125": {"description": "Insufficient Coolant Temperature for Closed Loop Fuel Control", "severity": "MEDIUM", "system": "Cooling"},
    "P0130": {"description": "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0131": {"description": "O2 Sensor Circuit Low Voltage (Bank 1 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0132": {"description": "O2 Sensor Circuit High Voltage (Bank 1 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0133": {"description": "O2 Sensor Circuit Slow Response (Bank 1 Sensor 1)", "severity": "LOW", "system": "Emissions"},
    "P0134": {"description": "O2 Sensor Circuit No Activity Detected (Bank 1 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0135": {"description": "O2 Sensor Heater Circuit Malfunction (Bank 1 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0136": {"description": "O2 Sensor Circuit Malfunction (Bank 1 Sensor 2)", "severity": "MEDIUM", "system": "Emissions"},
    "P0140": {"description": "O2 Sensor Circuit No Activity Detected (Bank 1 Sensor 2)", "severity": "MEDIUM", "system": "Emissions"},
    "P0141": {"description": "O2 Sensor Heater Circuit Malfunction (Bank 1 Sensor 2)", "severity": "MEDIUM", "system": "Emissions"},
    "P0150": {"description": "O2 Sensor Circuit Malfunction (Bank 2 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0155": {"description": "O2 Sensor Heater Circuit Malfunction (Bank 2 Sensor 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0160": {"description": "O2 Sensor Circuit No Activity Detected (Bank 2 Sensor 2)", "severity": "MEDIUM", "system": "Emissions"},
    "P0161": {"description": "O2 Sensor Heater Circuit Malfunction (Bank 2 Sensor 2)", "severity": "MEDIUM", "system": "Emissions"},
    
    # Fuel System
    "P0170": {"description": "Fuel Trim Malfunction (Bank 1)", "severity": "MEDIUM", "system": "Fuel"},
    "P0171": {"description": "System Too Lean (Bank 1)", "severity": "MEDIUM", "system": "Fuel"},
    "P0172": {"description": "System Too Rich (Bank 1)", "severity": "MEDIUM", "system": "Fuel"},
    "P0173": {"description": "Fuel Trim Malfunction (Bank 2)", "severity": "MEDIUM", "system": "Fuel"},
    "P0174": {"description": "System Too Lean (Bank 2)", "severity": "MEDIUM", "system": "Fuel"},
    "P0175": {"description": "System Too Rich (Bank 2)", "severity": "MEDIUM", "system": "Fuel"},
    "P0190": {"description": "Fuel Rail Pressure Sensor Circuit Malfunction", "severity": "HIGH", "system": "Fuel"},
    "P0191": {"description": "Fuel Rail Pressure Sensor Circuit Range/Performance", "severity": "MEDIUM", "system": "Fuel"},
    
    # Ignition System
    "P0300": {"description": "Random/Multiple Cylinder Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0301": {"description": "Cylinder 1 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0302": {"description": "Cylinder 2 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0303": {"description": "Cylinder 3 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0304": {"description": "Cylinder 4 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0305": {"description": "Cylinder 5 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0306": {"description": "Cylinder 6 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0307": {"description": "Cylinder 7 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0308": {"description": "Cylinder 8 Misfire Detected", "severity": "HIGH", "system": "Ignition"},
    "P0325": {"description": "Knock Sensor 1 Circuit Malfunction (Bank 1)", "severity": "MEDIUM", "system": "Ignition"},
    "P0330": {"description": "Knock Sensor 2 Circuit Malfunction (Bank 2)", "severity": "MEDIUM", "system": "Ignition"},
    "P0335": {"description": "Crankshaft Position Sensor A Circuit Malfunction", "severity": "HIGH", "system": "Ignition"},
    "P0340": {"description": "Camshaft Position Sensor A Circuit Malfunction (Bank 1)", "severity": "HIGH", "system": "Ignition"},
    "P0345": {"description": "Camshaft Position Sensor A Circuit Malfunction (Bank 2)", "severity": "HIGH", "system": "Ignition"},
    
    # Emission Controls
    "P0400": {"description": "Exhaust Gas Recirculation Flow Malfunction", "severity": "MEDIUM", "system": "Emissions"},
    "P0401": {"description": "Exhaust Gas Recirculation Flow Insufficient Detected", "severity": "MEDIUM", "system": "Emissions"},
    "P0402": {"description": "Exhaust Gas Recirculation Flow Excessive Detected", "severity": "MEDIUM", "system": "Emissions"},
    "P0420": {"description": "Catalyst System Efficiency Below Threshold (Bank 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0421": {"description": "Warm Up Catalyst Efficiency Below Threshold (Bank 1)", "severity": "MEDIUM", "system": "Emissions"},
    "P0430": {"description": "Catalyst System Efficiency Below Threshold (Bank 2)", "severity": "MEDIUM", "system": "Emissions"},
    "P0440": {"description": "Evaporative Emission Control System Malfunction", "severity": "LOW", "system": "Emissions"},
    "P0441": {"description": "Evaporative Emission Control System Incorrect Purge Flow", "severity": "LOW", "system": "Emissions"},
    "P0442": {"description": "Evaporative Emission Control System Leak Detected (small)", "severity": "LOW", "system": "Emissions"},
    "P0443": {"description": "Evaporative Emission Control System Purge Control Valve Circuit", "severity": "LOW", "system": "Emissions"},
    "P0446": {"description": "Evaporative Emission Control System Vent Control Circuit", "severity": "LOW", "system": "Emissions"},
    "P0455": {"description": "Evaporative Emission Control System Leak Detected (large)", "severity": "MEDIUM", "system": "Emissions"},
    
    # Speed/Idle Control
    "P0500": {"description": "Vehicle Speed Sensor Malfunction", "severity": "MEDIUM", "system": "Speed Control"},
    "P0505": {"description": "Idle Control System Malfunction", "severity": "MEDIUM", "system": "Idle"},
    "P0506": {"description": "Idle Control System RPM Lower Than Expected", "severity": "LOW", "system": "Idle"},
    "P0507": {"description": "Idle Control System RPM Higher Than Expected", "severity": "LOW", "system": "Idle"},
    
    # Transmission
    "P0700": {"description": "Transmission Control System Malfunction", "severity": "HIGH", "system": "Transmission"},
    "P0705": {"description": "Transmission Range Sensor Circuit Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0715": {"description": "Input/Turbine Speed Sensor Circuit Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0720": {"description": "Output Speed Sensor Circuit Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0725": {"description": "Engine Speed Input Circuit Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0730": {"description": "Incorrect Gear Ratio", "severity": "MEDIUM", "system": "Transmission"},
    "P0731": {"description": "Gear 1 Incorrect Ratio", "severity": "MEDIUM", "system": "Transmission"},
    "P0732": {"description": "Gear 2 Incorrect Ratio", "severity": "MEDIUM", "system": "Transmission"},
    "P0733": {"description": "Gear 3 Incorrect Ratio", "severity": "MEDIUM", "system": "Transmission"},
    "P0734": {"description": "Gear 4 Incorrect Ratio", "severity": "MEDIUM", "system": "Transmission"},
    "P0740": {"description": "Torque Converter Clutch Circuit Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0750": {"description": "Shift Solenoid A Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0755": {"description": "Shift Solenoid B Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    "P0760": {"description": "Shift Solenoid C Malfunction", "severity": "MEDIUM", "system": "Transmission"},
    
    # Body Codes
    "B0001": {"description": "Driver Frontal Stage 1 Deployment Control", "severity": "HIGH", "system": "Airbag"},
    "B0002": {"description": "Driver Frontal Stage 2 Deployment Control", "severity": "HIGH", "system": "Airbag"},
    "B0100": {"description": "Electronic Frontal Sensor 1 Circuit", "severity": "HIGH", "system": "Airbag"},
    
    # Chassis Codes
    "C0035": {"description": "Left Front Wheel Speed Circuit Malfunction", "severity": "MEDIUM", "system": "ABS"},
    "C0040": {"description": "Right Front Wheel Speed Circuit Malfunction", "severity": "MEDIUM", "system": "ABS"},
    "C0045": {"description": "Left Rear Wheel Speed Circuit Malfunction", "severity": "MEDIUM", "system": "ABS"},
    "C0050": {"description": "Right Rear Wheel Speed Circuit Malfunction", "severity": "MEDIUM", "system": "ABS"},
    
    # Network Codes
    "U0001": {"description": "High Speed CAN Communication Bus", "severity": "HIGH", "system": "Network"},
    "U0100": {"description": "Lost Communication With ECM/PCM A", "severity": "HIGH", "system": "Network"},
    "U0101": {"description": "Lost Communication With TCM", "severity": "HIGH", "system": "Network"},
    "U0121": {"description": "Lost Communication With ABS", "severity": "MEDIUM", "system": "Network"},
    "U0140": {"description": "Lost Communication With BCM", "severity": "MEDIUM", "system": "Network"},
}


@dataclass
class DTCCode:
    """Data class for a DTC code"""
    code: str
    description: str
    severity: str  # HIGH, MEDIUM, LOW
    system: str
    timestamp: str
    status: str  # ACTIVE, PENDING, HISTORY
    freeze_frame: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DTCCode':
        return cls(**data)


class DTCReadThread(QThread):
    """Thread for reading DTC codes from vehicle"""
    progress = Signal(int, str)
    dtc_found = Signal(dict)  # Single DTC found
    completed = Signal(list)  # All DTCs
    error = Signal(str)
    
    def __init__(self, connectivity_manager, parent=None):
        super().__init__(parent)
        self.connectivity = connectivity_manager
        self.is_running = True
    
    def run(self):
        try:
            self.progress.emit(10, "Initializing DTC scan...")
            all_dtcs = []
            
            # Check connection
            if not getattr(self.connectivity, 'connected', False):
                self.error.emit("Not connected to vehicle")
                return
            
            # Try python-obd method first
            if hasattr(self.connectivity, 'obd_connection') and self.connectivity.obd_connection:
                import obd
                
                # Read stored DTCs (Mode 03)
                self.progress.emit(30, "Reading stored DTCs (Mode 03)...")
                try:
                    response = self.connectivity.obd_connection.query(obd.commands.GET_DTC)
                    if response and not response.is_null():
                        for dtc_tuple in response.value:
                            dtc_code = dtc_tuple[0] if isinstance(dtc_tuple, tuple) else str(dtc_tuple)
                            dtc_info = DTC_DATABASE.get(dtc_code, {
                                "description": "Unknown DTC Code",
                                "severity": "MEDIUM",
                                "system": "Unknown"
                            })
                            
                            dtc = DTCCode(
                                code=dtc_code,
                                description=dtc_info["description"],
                                severity=dtc_info["severity"],
                                system=dtc_info["system"],
                                timestamp=datetime.now().isoformat(),
                                status="ACTIVE"
                            )
                            all_dtcs.append(dtc.to_dict())
                            self.dtc_found.emit(dtc.to_dict())
                except Exception as e:
                    logger.warning(f"Error reading stored DTCs: {e}")
                
                # Read pending DTCs (Mode 07)
                self.progress.emit(60, "Reading pending DTCs (Mode 07)...")
                try:
                    if obd.commands.GET_FREEZE_DTC in self.connectivity.obd_connection.supported_commands:
                        response = self.connectivity.obd_connection.query(obd.commands.GET_FREEZE_DTC)
                        if response and not response.is_null():
                            for dtc_tuple in response.value:
                                dtc_code = dtc_tuple[0] if isinstance(dtc_tuple, tuple) else str(dtc_tuple)
                                
                                # Skip if already in active list
                                if any(d['code'] == dtc_code for d in all_dtcs):
                                    continue
                                
                                dtc_info = DTC_DATABASE.get(dtc_code, {
                                    "description": "Unknown DTC Code",
                                    "severity": "MEDIUM",
                                    "system": "Unknown"
                                })
                                
                                dtc = DTCCode(
                                    code=dtc_code,
                                    description=dtc_info["description"],
                                    severity=dtc_info["severity"],
                                    system=dtc_info["system"],
                                    timestamp=datetime.now().isoformat(),
                                    status="PENDING"
                                )
                                all_dtcs.append(dtc.to_dict())
                                self.dtc_found.emit(dtc.to_dict())
                except Exception as e:
                    logger.warning(f"Error reading pending DTCs: {e}")
            
            # Try direct ELM method
            elif hasattr(self.connectivity, 'direct_elm') and self.connectivity.direct_elm:
                self.progress.emit(30, "Reading DTCs via direct ELM...")
                
                # Mode 03 - Stored DTCs
                try:
                    response = self.connectivity.direct_elm.send_command("03")
                    if response and "43" in response:
                        dtcs = self._parse_dtc_response(response, "ACTIVE")
                        all_dtcs.extend(dtcs)
                        for dtc in dtcs:
                            self.dtc_found.emit(dtc)
                except Exception as e:
                    logger.warning(f"Error reading Mode 03: {e}")
                
                # Mode 07 - Pending DTCs
                self.progress.emit(60, "Reading pending DTCs...")
                try:
                    response = self.connectivity.direct_elm.send_command("07")
                    if response and "47" in response:
                        dtcs = self._parse_dtc_response(response, "PENDING")
                        # Skip duplicates
                        for dtc in dtcs:
                            if not any(d['code'] == dtc['code'] for d in all_dtcs):
                                all_dtcs.append(dtc)
                                self.dtc_found.emit(dtc)
                except Exception as e:
                    logger.warning(f"Error reading Mode 07: {e}")
            
            self.progress.emit(100, f"Scan complete! Found {len(all_dtcs)} DTCs")
            self.completed.emit(all_dtcs)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _parse_dtc_response(self, response: str, status: str) -> List[Dict]:
        """Parse DTC response from ELM327"""
        dtcs = []
        
        # Remove whitespace and split
        data = response.replace(" ", "").replace("\r", "").replace("\n", "")
        
        # Find the data after the mode response (43 for Mode 03, 47 for Mode 07)
        if "43" in data:
            idx = data.find("43") + 2
        elif "47" in data:
            idx = data.find("47") + 2
        else:
            return dtcs
        
        # Parse DTCs (each DTC is 4 hex chars)
        data = data[idx:]
        
        while len(data) >= 4:
            dtc_raw = data[:4]
            data = data[4:]
            
            if dtc_raw == "0000":
                continue
            
            dtc_code = self._decode_dtc(dtc_raw)
            if dtc_code:
                dtc_info = DTC_DATABASE.get(dtc_code, {
                    "description": "Unknown DTC Code",
                    "severity": "MEDIUM",
                    "system": "Unknown"
                })
                
                dtc = DTCCode(
                    code=dtc_code,
                    description=dtc_info["description"],
                    severity=dtc_info["severity"],
                    system=dtc_info["system"],
                    timestamp=datetime.now().isoformat(),
                    status=status
                )
                dtcs.append(dtc.to_dict())
        
        return dtcs
    
    def _decode_dtc(self, raw: str) -> Optional[str]:
        """Decode raw DTC bytes to standard format"""
        try:
            first_byte = int(raw[0], 16)
            
            # Determine type prefix
            type_map = {0: 'P', 1: 'P', 2: 'P', 3: 'P',  # Powertrain
                       4: 'C', 5: 'C', 6: 'C', 7: 'C',  # Chassis
                       8: 'B', 9: 'B', 10: 'B', 11: 'B', # Body
                       12: 'U', 13: 'U', 14: 'U', 15: 'U'} # Network
            
            prefix = type_map.get(first_byte, 'P')
            
            # Second char based on first nibble
            second_char = str(first_byte % 4)
            
            # Rest of code
            rest = raw[1:4].upper()
            
            return f"{prefix}{second_char}{rest}"
        except:
            return None
    
    def stop(self):
        self.is_running = False


class DTCManager(QObject):
    """Manager for DTC codes per vehicle"""
    
    dtc_updated = Signal(str, list)  # profile_id, dtc_list
    
    def __init__(self, storage_dir: str = None, parent=None):
        super().__init__(parent)
        
        if storage_dir is None:
            storage_dir = os.path.join(os.getcwd(), "data", "dtc_codes")
        
        self.storage_dir = storage_dir
        self._ensure_directory()
        
        # Cache of DTCs per profile
        self._dtc_cache: Dict[str, List[Dict]] = {}
    
    def _ensure_directory(self):
        """Ensure storage directory exists"""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def _get_filepath(self, profile_id: str) -> str:
        """Get filepath for profile's DTC storage"""
        safe_id = profile_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"dtc_{safe_id}.json")
    
    def load_dtcs(self, profile_id: str) -> List[Dict]:
        """Load DTCs for a specific profile"""
        filepath = self._get_filepath(profile_id)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._dtc_cache[profile_id] = data.get('dtcs', [])
            except Exception as e:
                logger.error(f"Error loading DTCs for {profile_id}: {e}")
                self._dtc_cache[profile_id] = []
        else:
            self._dtc_cache[profile_id] = []
        
        return self._dtc_cache.get(profile_id, [])
    
    def save_dtcs(self, profile_id: str, dtcs: List[Dict]):
        """Save DTCs for a specific profile"""
        filepath = self._get_filepath(profile_id)
        
        data = {
            'profile_id': profile_id,
            'last_updated': datetime.now().isoformat(),
            'dtcs': dtcs
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self._dtc_cache[profile_id] = dtcs
            self.dtc_updated.emit(profile_id, dtcs)
            
        except Exception as e:
            logger.error(f"Error saving DTCs for {profile_id}: {e}")
    
    def add_dtc(self, profile_id: str, dtc: Dict):
        """Add a single DTC to profile and trigger alert for critical DTCs"""
        dtcs = self.load_dtcs(profile_id)
        
        # Check if DTC already exists
        existing = next((d for d in dtcs if d['code'] == dtc['code']), None)
        is_new = existing is None
        
        if existing:
            # Update timestamp
            existing['timestamp'] = datetime.now().isoformat()
            existing['status'] = dtc.get('status', existing['status'])
        else:
            dtcs.append(dtc)
        
        self.save_dtcs(profile_id, dtcs)
        
        # Send alert for new HIGH severity DTCs
        if is_new and dtc.get('severity') == 'HIGH':
            self._send_dtc_alert(profile_id, dtc)
    
    def _send_dtc_alert(self, profile_id: str, dtc: Dict):
        """Send alert notification for critical DTC detection"""
        alert_manager = get_alert_manager()
        if not alert_manager:
            logger.warning("Alert manager not available for DTC alert")
            return
        
        # Get alert types and priority enums
        AlertType = get_alert_types()
        NotificationPriority = get_notification_priority()
        if not AlertType or not NotificationPriority:
            logger.warning("Alert types or priority not available")
            return
        
        try:
            # Create alert message
            alert_message = f"""
⚠️ CRITICAL DTC DETECTED

DTC Code: {dtc['code']}
Description: {dtc['description']}
Severity: {dtc['severity']}
System: {dtc['system']}
Detected: {dtc['timestamp']}

This is a HIGH severity diagnostic trouble code that requires immediate attention.
Please check your vehicle and schedule service if needed.
"""
            
            # Send alert using send_notification method
            alert_manager.send_notification(
                alert_type=AlertType.DTC_DETECTED,
                priority=NotificationPriority.HIGH,
                title=f"Critical DTC: {dtc['code']}",
                message=alert_message,
                recipient_id=1,  # Default user ID - should be configured
                data={
                    "profile_id": profile_id,
                    "dtc_code": dtc['code'],
                    "dtc_description": dtc['description'],
                    "dtc_severity": dtc['severity'],
                    "dtc_system": dtc['system']
                }
            )
            
            logger.info(f"Alert sent for critical DTC {dtc['code']} for profile {profile_id}")
            
        except Exception as e:
            logger.error(f"Failed to send DTC alert: {e}")
    
    def clear_dtcs(self, profile_id: str):
        """Clear all DTCs for a profile (after clearing on vehicle)"""
        # Move to history instead of deleting
        dtcs = self.load_dtcs(profile_id)
        for dtc in dtcs:
            dtc['status'] = 'HISTORY'
            dtc['cleared_at'] = datetime.now().isoformat()
        
        self.save_dtcs(profile_id, dtcs)
    
    def get_active_dtcs(self, profile_id: str) -> List[Dict]:
        """Get only active DTCs for profile"""
        dtcs = self.load_dtcs(profile_id)
        return [d for d in dtcs if d.get('status') == 'ACTIVE']
    
    def get_pending_dtcs(self, profile_id: str) -> List[Dict]:
        """Get only pending DTCs for profile"""
        dtcs = self.load_dtcs(profile_id)
        return [d for d in dtcs if d.get('status') == 'PENDING']
    
    def get_dtc_summary(self, profile_id: str) -> Dict[str, Any]:
        """Get DTC summary for profile"""
        dtcs = self.load_dtcs(profile_id)
        
        active = [d for d in dtcs if d.get('status') == 'ACTIVE']
        pending = [d for d in dtcs if d.get('status') == 'PENDING']
        history = [d for d in dtcs if d.get('status') == 'HISTORY']
        
        # Count by severity
        high_count = len([d for d in active if d.get('severity') == 'HIGH'])
        medium_count = len([d for d in active if d.get('severity') == 'MEDIUM'])
        low_count = len([d for d in active if d.get('severity') == 'LOW'])
        
        # Count by system
        systems = {}
        for dtc in active:
            system = dtc.get('system', 'Unknown')
            systems[system] = systems.get(system, 0) + 1
        
        return {
            'total_active': len(active),
            'total_pending': len(pending),
            'total_history': len(history),
            'high_severity': high_count,
            'medium_severity': medium_count,
            'low_severity': low_count,
            'systems_affected': systems,
            'last_scan': dtcs[0]['timestamp'] if dtcs else None
        }
    
    def get_dtc_info(self, code: str) -> Dict[str, Any]:
        """Get database info for a DTC code"""
        return DTC_DATABASE.get(code, {
            "description": "Unknown DTC Code",
            "severity": "MEDIUM",
            "system": "Unknown"
        })


# ================================
# DTC CLEAR THREAD
# ================================

class DTCClearThread(QThread):
    """Thread for clearing DTC codes from vehicle"""
    progress = Signal(int, str)
    completed = Signal(bool, str)
    
    def __init__(self, connectivity_manager, parent=None):
        super().__init__(parent)
        self.connectivity = connectivity_manager
    
    def run(self):
        try:
            self.progress.emit(20, "Preparing to clear DTCs...")
            
            if not getattr(self.connectivity, 'connected', False):
                self.completed.emit(False, "Not connected to vehicle")
                return
            
            # Try python-obd method
            if hasattr(self.connectivity, 'obd_connection') and self.connectivity.obd_connection:
                import obd
                
                self.progress.emit(50, "Sending clear command...")
                
                try:
                    response = self.connectivity.obd_connection.query(obd.commands.CLEAR_DTC)
                    self.progress.emit(100, "DTCs cleared successfully")
                    self.completed.emit(True, "DTCs cleared successfully")
                    return
                except Exception as e:
                    logger.warning(f"OBD clear failed: {e}")
            
            # Try direct ELM method (Mode 04)
            if hasattr(self.connectivity, 'direct_elm') and self.connectivity.direct_elm:
                self.progress.emit(50, "Sending clear command via ELM...")
                
                try:
                    response = self.connectivity.direct_elm.send_command("04")
                    if response and "44" in response:
                        self.progress.emit(100, "DTCs cleared successfully")
                        self.completed.emit(True, "DTCs cleared successfully")
                        return
                except Exception as e:
                    logger.warning(f"ELM clear failed: {e}")
            
            self.completed.emit(False, "Failed to clear DTCs")
            
        except Exception as e:
            self.completed.emit(False, str(e))
