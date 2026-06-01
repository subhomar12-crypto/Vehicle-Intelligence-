"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Connectivity Module
"""

import time
import threading
import json
import os
import re
from datetime import datetime
from typing import Dict, Optional, List, Any, Tuple, Set
from collections import deque, defaultdict
from enum import Enum
from dataclasses import dataclass
import logging
import serial
import serial.tools.list_ports

# OBD library (optional)
try:
    import obd
    from obd import OBDStatus
    HAS_PYTHON_OBD = True
except ImportError:
    HAS_PYTHON_OBD = False
    print("Note: python-OBD not installed. Using Direct ELM327 mode only.")

from PySide6.QtCore import QObject, Signal

# Import config
try:
    from config import get_config
    _config = get_config()
except ImportError:
    _config = None

# Import PID Profile system
try:
    from pid_profiles import PIDProfileResolver, VehicleProfile
except ImportError:
    PIDProfileResolver = None
    VehicleProfile = None


# ================================
# LOGGING SETUP
# ================================

def setup_connectivity_logger():
    """Setup dedicated connectivity logger"""
    logger = logging.getLogger('UniversalConnectivityManager')
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory
    os.makedirs('./logs', exist_ok=True)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File handler with detailed logging
    file_handler = logging.FileHandler('./logs/connectivity.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


# ================================
# PROTOCOL DEFINITIONS
# ================================

class OBDProtocol(Enum):
    """ELM327 OBD Protocols"""
    AUTO = ("0", "Auto Detect", False)
    SAE_J1850_PWM = ("1", "SAE J1850 PWM (Ford)", False)
    SAE_J1850_VPW = ("2", "SAE J1850 VPW (GM)", False)
    ISO_9141_2 = ("3", "ISO 9141-2 (Asian/European)", True)  # K-Line
    ISO_14230_4_KWP_SLOW = ("4", "ISO 14230-4 KWP 5-baud", True)  # K-Line
    ISO_14230_4_KWP_FAST = ("5", "ISO 14230-4 KWP Fast", True)  # K-Line
    ISO_15765_4_CAN_11_500 = ("6", "CAN 11-bit 500k", False)  # Most 2008+
    ISO_15765_4_CAN_29_500 = ("7", "CAN 29-bit 500k", False)  # Trucks
    ISO_15765_4_CAN_11_250 = ("8", "CAN 11-bit 250k", False)
    ISO_15765_4_CAN_29_250 = ("9", "CAN 29-bit 250k", False)
    
    def __init__(self, code: str, description: str, is_kline: bool):
        self._code = code
        self._description = description
        self._is_kline = is_kline
    
    @property
    def code(self) -> str:
        return self._code
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def is_kline(self) -> bool:
        return self._is_kline
    
    @property
    def is_can(self) -> bool:
        return self._code in ('6', '7', '8', '9')
    
    @property
    def is_j1850(self) -> bool:
        return self._code in ('1', '2')


class ConnectionType(Enum):
    """Connection type enumeration"""
    DISCONNECTED = "Disconnected"
    SERIAL = "Serial"
    USB = "USB"
    BLUETOOTH = "Bluetooth"


class ConnectionState(Enum):
    """Connection state machine states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    PROTOCOL_DETECTION = "protocol_detection"
    PROTOCOL_TESTING = "protocol_testing"
    VERIFYING = "verifying"
    CONNECTED = "connected"
    POLLING = "polling"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    LOST = "lost"


# ================================
# CONNECTION STRATEGY
# ================================

class ConnectionStrategy(Enum):
    """Connection strategy for different vehicle types"""
    AUTO = "auto"                    # Let system decide
    SMART_FALLBACK = "smart"        # Try python-OBD, fallback to direct
    DIRECT_ONLY = "direct"          # Use DirectELM327 only
    PYTHON_OBD_ONLY = "python_obd"  # Use python-OBD only
    
    @classmethod
    def for_vehicle(cls, year: int, make: str = "") -> 'ConnectionStrategy':
        """Determine best strategy for a vehicle"""
        make_lower = make.lower() if make else ""
        
        # Manufacturer-specific strategies
        if "nissan" in make_lower and year >= 2010:
            # Many Nissan vehicles work better with direct mode
            return cls.SMART_FALLBACK
        
        if year >= 2008:
            # Modern CAN vehicles: try python-OBD first
            return cls.SMART_FALLBACK
        else:
            # Older K-Line vehicles: direct mode more reliable
            return cls.DIRECT_ONLY


# ================================
# PID DEFINITION
# ================================

@dataclass
class PIDDefinition:
    """PID definition with decoding formula"""
    pid: int
    name: str
    unit: str = ""
    bytes_count: int = 1
    formula: str = "A"  # Formula using A, B, C, D
    min_val: float = 0
    max_val: float = 255
    tier: int = 1  # 1=critical, 2=important, 3=secondary
    mode: int = 0x01
    can_id: Optional[str] = None  # CAN ID for manufacturer-specific PIDs
    
    def decode(self, data: bytes) -> Optional[float]:
        """Decode raw bytes using formula"""
        if not data or len(data) < self.bytes_count:
            return None
        try:
            variables = {
                'A': data[0] if len(data) > 0 else 0,
                'B': data[1] if len(data) > 1 else 0,
                'C': data[2] if len(data) > 2 else 0,
                'D': data[3] if len(data) > 3 else 0,
            }
            result = eval(self.formula, {"__builtins__": {}}, variables)
            return float(result)
        except:
            return None


# Standard OBD-II PIDs (Mode 01) - Universal
STANDARD_PIDS: Dict[str, PIDDefinition] = {
    # TIER 1 - Critical (poll every cycle)
    "rpm": PIDDefinition(0x0C, "Engine RPM", "rpm", 2, "(A*256+B)/4", 0, 16383.75, 1),
    "speed": PIDDefinition(0x0D, "Vehicle Speed", "km/h", 1, "A", 0, 255, 1),
    "coolant_temp": PIDDefinition(0x05, "Coolant Temperature", "°C", 1, "A-40", -40, 215, 1),
    "engine_load": PIDDefinition(0x04, "Engine Load", "%", 1, "A*100/255", 0, 100, 1),
    "throttle_position": PIDDefinition(0x11, "Throttle Position", "%", 1, "A*100/255", 0, 100, 1),
    
    # TIER 2 - Important (poll every 1-2s)
    "intake_temp": PIDDefinition(0x0F, "Intake Air Temp", "°C", 1, "A-40", -40, 215, 2),
    "maf": PIDDefinition(0x10, "MAF Air Flow", "g/s", 2, "(A*256+B)/100", 0, 655.35, 2),
    "map": PIDDefinition(0x0B, "Intake Manifold Pressure", "kPa", 1, "A", 0, 255, 2),
    "timing_advance": PIDDefinition(0x0E, "Timing Advance", "°", 1, "(A-128)/2", -64, 63.5, 2),
    "short_fuel_trim_1": PIDDefinition(0x06, "Short Fuel Trim Bank 1", "%", 1, "(A-128)*100/128", -100, 99.2, 2),
    "long_fuel_trim_1": PIDDefinition(0x07, "Long Fuel Trim Bank 1", "%", 1, "(A-128)*100/128", -100, 99.2, 2),
    "fuel_pressure": PIDDefinition(0x0A, "Fuel Pressure", "kPa", 1, "A*3", 0, 765, 2),
    
    # TIER 3 - Secondary (poll every 5-10s)
    "fuel_level": PIDDefinition(0x2F, "Fuel Tank Level", "%", 1, "A*100/255", 0, 100, 3),
    "runtime": PIDDefinition(0x1F, "Engine Runtime", "sec", 2, "A*256+B", 0, 65535, 3),
    "barometric_pressure": PIDDefinition(0x33, "Barometric Pressure", "kPa", 1, "A", 0, 255, 3),
    "ambient_temp": PIDDefinition(0x46, "Ambient Air Temp", "°C", 1, "A-40", -40, 215, 3),
    "oil_temp": PIDDefinition(0x5C, "Engine Oil Temp", "°C", 1, "A-40", -40, 210, 3),
    "control_module_voltage": PIDDefinition(0x42, "Control Module Voltage", "V", 2, "(A*256+B)/1000", 0, 65.535, 3),
}

# Map for python-OBD commands (if available)
OBD_COMMAND_MAP = {}
if HAS_PYTHON_OBD:
    OBD_COMMAND_MAP = {
        "rpm": obd.commands.RPM,
        "speed": obd.commands.SPEED,
        "coolant_temp": obd.commands.COOLANT_TEMP,
        "engine_load": obd.commands.ENGINE_LOAD,
        "throttle_position": obd.commands.THROTTLE_POS,
        "intake_temp": obd.commands.INTAKE_TEMP,
        "maf": obd.commands.MAF,
        "map": obd.commands.INTAKE_PRESSURE,
        "timing_advance": obd.commands.TIMING_ADVANCE,
    }


# ================================
# DIRECT ELM327 INTERFACE (UNIVERSAL)
# ================================

class UniversalELM327:
    """
    Universal ELM327 interface for ALL vehicles.
    Handles CAN, K-Line, J1850 protocols intelligently.
    """
    
    ERROR_PATTERNS = [b'NO DATA', b'ERROR', b'UNABLE', b'CAN ERROR', b'BUS INIT', b'?', b'STOPPED']
    
    # Manufacturer-specific CAN IDs (if needed)
    MANUFACTURER_CAN_IDS = {
        'nissan': ['7E0', '7E1', '7E2'],
        'toyota': ['7E0', '7E1'],
        'ford': ['7E0', '7E1'],
        'honda': ['7E0', '7E1'],
        'bmw': ['7E0', '7E1'],
        'mercedes': ['7E0', '7E1'],
        'vw': ['7E0', '7E1'],
        'audi': ['7E0', '7E1'],
    }
    
    def __init__(self, port: str, baudrate: int = 38400, logger=None):
        self.port = port
        self.baudrate = baudrate
        self.logger = logger or logging.getLogger('UniversalELM327')
        self.serial: Optional[serial.Serial] = None
        self.protocol: Optional[OBDProtocol] = None
        self.elm_version: str = ""
        self.voltage: float = 0.0
        self.manufacturer: str = ""
        self._lock = threading.Lock()
        self._connection_history = deque(maxlen=10)  # Store successful protocols
        
    def connect(self) -> bool:
        """Establish serial connection"""
        if not self._validate_port(self.port):
            self.logger.error(f"Invalid port: {self.port}")
            return False
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=5,
                write_timeout=5,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            time.sleep(0.5)
            self._flush()
            self.logger.info(f"Connected to {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def _validate_port(self, port: str) -> bool:
        """Validate port name (security)"""
        if not port:
            return False
        if re.match(r'^COM\d{1,3}$', port, re.IGNORECASE):
            return True
        if re.match(r'^/dev/(tty(USB|ACM|S)|cu\.)\w*\d*$', port):
            return True
        if re.match(r'^/dev/rfcomm\d+$', port):
            return True
        return False
    
    def disconnect(self):
        """Close connection"""
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
            self.logger.info("Disconnected")
    
    def _flush(self):
        """Flush serial buffers"""
        if self.serial:
            try:
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
            except:
                pass
    
    def send_command(self, cmd: str, timeout: float = 3.0) -> str:
        """Send AT command and get response"""
        if not self.serial or not self.serial.is_open:
            return ""
        
        with self._lock:
            try:
                self._flush()
                self.serial.write((cmd.strip() + '\r').encode('ascii'))
                self.serial.flush()
                
                response = b''
                start = time.time()
                
                while (time.time() - start) < timeout:
                    if self.serial.in_waiting:
                        response += self.serial.read(self.serial.in_waiting)
                        if b'>' in response:
                            break
                    time.sleep(0.01)
                
                text = response.decode('ascii', errors='ignore')
                text = text.replace(cmd, '').replace('>', '')
                return ' '.join(text.split()).strip()
                
            except Exception as e:
                self.logger.debug(f"Command error: {e}")
                return ""
    
    def is_error(self, response: str) -> bool:
        """Check for error response"""
        resp = response.upper().encode()
        return any(err in resp for err in self.ERROR_PATTERNS)
    
    def initialize(self, protocol: OBDProtocol) -> bool:
        """Initialize ELM327 with specific protocol"""
        self.logger.info(f"Initializing with protocol: {protocol.description}")
        
        # Reset
        resp = self.send_command('ATZ', 2)
        if 'ELM' in resp.upper():
            self.elm_version = resp
            self.logger.info(f"Adapter: {resp}")
        
        time.sleep(0.5)
        
        # Configure adapter
        self.send_command('ATE0')  # Echo off
        self.send_command('ATL0')  # Linefeeds off
        self.send_command('ATS0')  # Spaces off
        self.send_command('ATH0')  # Headers off
        
        # Set protocol
        self.send_command('ATSP' + protocol.code)
        
        # Additional settings based on protocol
        if protocol.is_can:
            # CAN-specific settings
            self.send_command('ATCAF0')  # CAN auto formatting off
            self.send_command('ATFC SH 7E0')  # Set CAN filter (optional)
            time.sleep(0.5)
        elif protocol.is_kline:
            # K-Line needs more time
            time.sleep(2)
        
        # Get voltage
        v_resp = self.send_command('ATRV')
        match = re.search(r'(\d+\.?\d*)', v_resp)
        if match:
            self.voltage = float(match.group(1))
            self.logger.info(f"Voltage: {self.voltage}V")
        
        self.protocol = protocol
        return True
    
    def smart_protocol_detection(self, vehicle_year: int = 0, manufacturer: str = "") -> Optional[OBDProtocol]:
        """
        Intelligent protocol detection based on vehicle info.
        Returns: Best protocol for this vehicle
        """
        self.manufacturer = manufacturer.lower() if manufacturer else ""
        
        self.logger.info(f"Smart protocol detection - Year: {vehicle_year}, Make: {manufacturer}")
        
        # Try protocols in optimal order
        protocol_order = []
        
        if vehicle_year >= 2008:
            # Modern vehicle - try CAN protocols first
            protocol_order = [
                OBDProtocol.ISO_15765_4_CAN_11_500,  # Most common CAN
                OBDProtocol.ISO_15765_4_CAN_29_500,  # Trucks/SUVs
                OBDProtocol.ISO_15765_4_CAN_11_250,
                OBDProtocol.AUTO,  # Auto-detect as fallback
                OBDProtocol.ISO_9141_2,  # K-Line fallback
                OBDProtocol.SAE_J1850_PWM,  # Ford fallback
            ]
        elif vehicle_year >= 1996 and vehicle_year <= 2007:
            # OBD-II era but pre-CAN
            protocol_order = [
                OBDProtocol.ISO_9141_2,  # Asian/European
                OBDProtocol.ISO_14230_4_KWP_FAST,
                OBDProtocol.ISO_14230_4_KWP_SLOW,
                OBDProtocol.SAE_J1850_PWM,  # Ford
                OBDProtocol.SAE_J1850_VPW,  # GM
                OBDProtocol.AUTO,
            ]
        else:
            # Unknown year, try all
            protocol_order = [
                OBDProtocol.AUTO,
                OBDProtocol.ISO_15765_4_CAN_11_500,
                OBDProtocol.ISO_9141_2,
                OBDProtocol.ISO_14230_4_KWP_FAST,
                OBDProtocol.SAE_J1850_PWM,
                OBDProtocol.SAE_J1850_VPW,
            ]
        
        # Try each protocol
        for protocol in protocol_order:
            self.logger.info(f"Trying protocol: {protocol.description}")
            
            if self.initialize(protocol):
                # Test if protocol works
                time.sleep(1 if protocol.is_kline else 0.5)
                
                test_cmd = '0100'  # PID 00 - Supported PIDs
                response = self.send_command(test_cmd, timeout=10 if protocol.is_kline else 5)
                
                if not self.is_error(response) and '4100' in response.replace(' ', ''):
                    self.protocol = protocol
                    self._connection_history.append(protocol)
                    self.logger.info(f"✓ Protocol successful: {protocol.description}")
                    return protocol
                else:
                    self.logger.debug(f"Protocol {protocol.description} failed: {response}")
            
            time.sleep(0.5)
        
        self.logger.error("All protocols failed")
        return None
    
    def query_pid(self, mode: int, pid: int, can_id: Optional[str] = None) -> Optional[bytes]:
        """Query a PID and return raw bytes"""
        cmd = f"{mode:02X}{pid:02X}"
        
        # Set CAN ID if specified
        if can_id and self.protocol and self.protocol.is_can:
            self.send_command(f'ATSH {can_id}')
        
        # Adjust timeout based on protocol
        timeout = 8.0 if (self.protocol and self.protocol.is_kline) else 3.0
        
        response = self.send_command(cmd, timeout)
        
        if self.is_error(response):
            return None
        
        try:
            clean = response.replace(' ', '').upper()
            expected = f"{mode + 0x40:02X}{pid:02X}"
            
            if expected not in clean:
                return None
            
            idx = clean.find(expected) + 4
            data_hex = clean[idx:]
            data_hex = ''.join(c for c in data_hex if c in '0123456789ABCDEF')
            
            if len(data_hex) >= 2:
                return bytes.fromhex(data_hex)
        except:
            pass
        
        return None
    
    def read_pid(self, pid_key: str) -> Optional[float]:
        """Read a PID by key and decode value"""
        if pid_key not in STANDARD_PIDS:
            return None
        
        pid_def = STANDARD_PIDS[pid_key]
        data = self.query_pid(pid_def.mode, pid_def.pid, pid_def.can_id)
        
        if data:
            return pid_def.decode(data)
        return None
    
    def quick_test(self) -> bool:
        """Quick test to see if connection is alive"""
        if not self.serial:
            return False
        
        try:
            # Simple AT command test
            resp = self.send_command('ATI', timeout=2)
            return 'ELM' in resp.upper()
        except:
            return False


# ================================
# ENHANCED PID MANAGER
# ================================

class EnhancedPIDManager:
    """Enhanced PID manager with profile and learning integration"""
    
    def __init__(self, pid_learning_manager=None):
        self.pid_learning_manager = pid_learning_manager
        self.standard_pids = STANDARD_PIDS.copy()
        self.learned_pids = {}
        self.profile_pids = {}
        self.logger = logging.getLogger('EnhancedPIDManager')
        
        if self.pid_learning_manager:
            self._load_learned_pids()
    
    def _load_learned_pids(self):
        """Load learned PIDs from PID learning manager"""
        try:
            if hasattr(self.pid_learning_manager, 'get_all_pids'):
                self.learned_pids = self.pid_learning_manager.get_all_pids() or {}
            elif hasattr(self.pid_learning_manager, 'learned_pids'):
                self.learned_pids = self.pid_learning_manager.learned_pids or {}
            self.logger.info(f"Loaded {len(self.learned_pids)} learned PIDs")
        except Exception as e:
            self.logger.error(f"Failed to load learned PIDs: {e}")
    
    def set_profile_pids(self, profile_pids: Dict[str, Dict]):
        """Set PIDs from vehicle profile"""
        self.profile_pids = profile_pids or {}
        self.logger.info(f"Set {len(self.profile_pids)} profile PIDs")
    
    def get_all_pids(self) -> Dict[str, PIDDefinition]:
        """Get all PIDs from all sources"""
        all_pids = {}
        all_pids.update(self.standard_pids)
        
        # Add profile PIDs
        for key, info in self.profile_pids.items():
            if isinstance(info, dict) and 'pid' in info:
                all_pids[key] = PIDDefinition(
                    pid=int(info['pid'], 16) if isinstance(info['pid'], str) else info['pid'],
                    name=info.get('name', key),
                    unit=info.get('unit', ''),
                    formula=info.get('equation', 'A'),
                    tier=3
                )
        
        # Add learned PIDs
        all_pids.update(self.learned_pids)
        
        return all_pids
    
    def get_tier_pids(self, tier: int) -> List[str]:
        """Get all PIDs of a specific tier"""
        return [key for key, pid in self.get_all_pids().items() if pid.tier == tier]


# ================================
# MAIN UNIVERSAL CONNECTIVITY MANAGER
# ================================

class UniversalConnectivityManager(QObject):
    """
    UNIVERSAL OBD connectivity manager.
    Works with ANY OBD-II compliant vehicle (1996+).
    
    Features:
    - Intelligent protocol detection
    - Auto-fallback between python-OBD and Direct ELM327
    - Vehicle-year-aware connection strategy
    - Tiered polling optimization
    - Connection persistence and learning
    """
    
    # Signals
    live_data = Signal(dict)
    status_changed = Signal(str)
    connection_changed = Signal(dict)
    error_occurred = Signal(str)
    connection_lost = Signal()
    protocol_detected = Signal(str)
    connection_strategy_changed = Signal(str)
    
    def __init__(self, pid_manager=None, auto_reconnect: bool = False, parent=None):
        super().__init__(parent)
        
        # Setup logging
        self.logger = setup_connectivity_logger()
        self.logger.info("=" * 60)
        self.logger.info("UniversalConnectivityManager v6 Initializing")
        self.logger.info("=" * 60)
        
        self.auto_reconnect = auto_reconnect
        self.pid_manager = EnhancedPIDManager(pid_manager)
        
        # Vehicle Profile
        self.vehicle_profile: Optional[Dict] = None
        self.pid_profile: Optional[Dict] = None
        
        # PID Profile Resolver
        self.pid_resolver: Optional[PIDProfileResolver] = None
        self._init_pid_resolver()
        
        # Full PID Registry
        self.full_pid_registry: Dict[str, PIDDefinition] = STANDARD_PIDS.copy()
        
        # Connection state
        self.connection_state = ConnectionState.DISCONNECTED
        self.connection_type = ConnectionType.DISCONNECTED
        self.obd_connection: Optional[obd.OBD] = None
        self.direct_elm: Optional[UniversalELM327] = None
        self.use_direct_mode: bool = False
        self.connection_lock = threading.RLock()
        
        # Connection info
        self.serial_port: Optional[str] = None
        self.baud_rate: int = 38400
        self.detected_protocol: Optional[OBDProtocol] = None
        self.connection_strategy: ConnectionStrategy = ConnectionStrategy.AUTO
        
        # Connected flag
        self._connected: bool = False
        
        # Data snapshot
        self.latest_merged: Dict[str, Any] = {}
        self._last_successful_read: Optional[datetime] = None
        
        # Error tracking
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 10
        self.error_count: int = 0
        self.error_history: deque = deque(maxlen=100)
        
        # Polling control
        self._polling_active: bool = False
        self._stop_flag: bool = False
        self._poll_thread: Optional[threading.Thread] = None
        
        # Tiered polling intervals (adjust based on protocol)
        self.tier1_interval: float = 0.2   # 200ms for CAN
        self.tier2_interval: float = 1.0   # 1s
        self.tier3_interval: float = 5.0   # 5s
        self._last_tier2_read: float = 0
        self._last_tier3_read: float = 0
        
        # Supported commands cache
        self._supported_commands: set = set()
        self._supported_pids: List[str] = []
        
        # Performance metrics
        self.performance_metrics = {
            'total_reads': 0,
            'successful_reads': 0,
            'failed_reads': 0,
            'read_success_rate': 1.0,
            'avg_read_time_ms': 0,
            'last_read_time_ms': 0,
            'protocol': 'Unknown',
            'strategy': 'Auto'
        }
        
        # Connection history (learn from past connections)
        self.connection_history = defaultdict(list)
        
        self.logger.info("UniversalConnectivityManager v6 initialized")
    
    # ================================
    # CONNECTED PROPERTY
    # ================================
    
    @property
    def connected(self) -> bool:
        """Returns True only if connection is verified"""
        if self.use_direct_mode:
            return self._connected and self.direct_elm is not None and self.direct_elm.serial is not None
        return self._connected and self.obd_connection is not None
    
    @connected.setter
    def connected(self, value: bool):
        old_value = self._connected
        self._connected = value
        if old_value != value:
            self.logger.info(f"Connection state: {old_value} -> {value}")
            if not value:
                self.latest_merged = {}
    
    # ================================
    # VEHICLE PROFILE MANAGEMENT
    # ================================
    
    def set_vehicle_profile(self, profile: Dict):
        """Set the active vehicle profile"""
        if not profile:
            self.vehicle_profile = None
            self.pid_profile = None
            self.full_pid_registry = STANDARD_PIDS.copy()
            self.logger.info("Vehicle profile cleared")
            return
        
        self.vehicle_profile = profile
        vehicle_name = profile.get('name', 'Unknown')
        vehicle_make = profile.get('make', profile.get('brand', 'Unknown'))
        vehicle_model = profile.get('model', 'Unknown')
        vehicle_year = profile.get('year', 0)
        
        self.logger.info(f"Vehicle profile set: {vehicle_name}")
        self.logger.info(f"  Make: {vehicle_make}")
        self.logger.info(f"  Model: {vehicle_model}")
        self.logger.info(f"  Year: {vehicle_year}")
        
        # Determine connection strategy based on vehicle
        self.connection_strategy = ConnectionStrategy.for_vehicle(vehicle_year, vehicle_make)
        self.performance_metrics['strategy'] = self.connection_strategy.value
        self.connection_strategy_changed.emit(self.connection_strategy.value)
        
        # Resolve PID profile
        self._resolve_pid_profile()
        
        # Build PID registry
        self._build_full_pid_registry()
    
    def _resolve_pid_profile(self):
        """Resolve the best PID profile for the vehicle"""
        if not self.pid_resolver or not self.vehicle_profile:
            self.pid_profile = None
            return
        
        try:
            if VehicleProfile:
                vp = VehicleProfile(
                    brand=self.vehicle_profile.get('make', self.vehicle_profile.get('brand', '')),
                    model=self.vehicle_profile.get('model', ''),
                    submodel=self.vehicle_profile.get('submodel', ''),
                    year=self.vehicle_profile.get('year', 0),
                    name=self.vehicle_profile.get('name', '')
                )
                self.pid_profile = self.pid_resolver.resolve(vp)
                if self.pid_profile:
                    self.logger.info(f"Resolved PID profile: {self.pid_profile.get('id')}")
        except Exception as e:
            self.logger.error(f"Error resolving PID profile: {e}")
            self.pid_profile = None
    
    def _build_full_pid_registry(self):
        """Build the complete PID registry"""
        self.full_pid_registry = STANDARD_PIDS.copy()
        
        # Add PIDs from JSON profile
        if self.pid_resolver and self.pid_profile:
            try:
                profile_pids = self.pid_resolver.merge_with_defaults(self.pid_profile)
                for key, info in profile_pids.items():
                    if key not in self.full_pid_registry and isinstance(info, dict):
                        pid_def = PIDDefinition(
                            pid=int(info.get('pid', '0'), 16) if 'pid' in info else 0,
                            name=info.get('name', key),
                            unit=info.get('unit', ''),
                            formula=info.get('equation', 'A'),
                            tier=3
                        )
                        self.full_pid_registry[key] = pid_def
                self.pid_manager.set_profile_pids(profile_pids)
            except Exception as e:
                self.logger.error(f"Error adding profile PIDs: {e}")
        
        self.logger.info(f"Full PID registry: {len(self.full_pid_registry)} PIDs")
    
    # ================================
    # UNIVERSAL CONNECTION METHODS
    # ================================
    
    def detect_com_ports(self) -> List[Dict[str, Any]]:
        """Detect available COM ports"""
        ports = []
        try:
            for port in serial.tools.list_ports.comports():
                port_info = {
                    'port': port.device,
                    'description': port.description,
                    'hwid': port.hwid,
                    'is_bluetooth': 'bluetooth' in port.description.lower(),
                    'is_usb': 'usb' in port.description.lower()
                }
                ports.append(port_info)
            self.logger.info(f"Detected {len(ports)} COM ports")
        except Exception as e:
            self.logger.error(f"Error detecting ports: {e}")
        return ports
    
    def connect_universal(self, port: str, baud_rate: int = 38400, 
                         strategy: Optional[ConnectionStrategy] = None) -> bool:
        """
        UNIVERSAL connection method for ANY vehicle.
        
        Strategy:
        1. Use specified strategy if provided
        2. Otherwise use auto-determined strategy
        3. Smart fallback between python-OBD and DirectELM327
        4. Protocol auto-detection based on vehicle year
        """
        # Require vehicle profile
        if not self.has_vehicle_profile():
            self.logger.error("Cannot connect: No vehicle profile selected")
            self.error_occurred.emit("No vehicle profile selected")
            return False
        
        # Determine connection strategy
        if strategy:
            self.connection_strategy = strategy
        else:
            # Auto-determine based on vehicle
            vehicle_year = self.vehicle_profile.get('year', 0) if self.vehicle_profile else 0
            vehicle_make = self.vehicle_profile.get('make', '') if self.vehicle_profile else ''
            self.connection_strategy = ConnectionStrategy.for_vehicle(vehicle_year, vehicle_make)
        
        self.logger.info(f"Using connection strategy: {self.connection_strategy.value}")
        
        with self.connection_lock:
            # Cleanup existing connection
            self._cleanup_connection()
            
            self.connection_state = ConnectionState.CONNECTING
            self.status_changed.emit(f"Connecting ({self.connection_strategy.value})...")
            self.logger.info(f"Connecting to {port} with strategy: {self.connection_strategy.value}")
            
            try:
                # Execute connection based on strategy
                if self.connection_strategy == ConnectionStrategy.DIRECT_ONLY:
                    success = self._connect_direct_universal(port, baud_rate)
                elif self.connection_strategy == ConnectionStrategy.PYTHON_OBD_ONLY:
                    success = self._connect_python_obd(port, baud_rate)
                elif self.connection_strategy == ConnectionStrategy.SMART_FALLBACK:
                    success = self._connect_smart_fallback(port, baud_rate)
                else:  # AUTO
                    success = self._connect_auto(port, baud_rate)
                
                if success:
                    self.performance_metrics['strategy'] = self.connection_strategy.value
                    self.connection_strategy_changed.emit(self.connection_strategy.value)
                    return True
                else:
                    raise Exception("All connection strategies failed")
                    
            except Exception as e:
                self.logger.error(f"Universal connection failed: {e}")
                self._cleanup_connection()
                self.connection_state = ConnectionState.ERROR
                self.status_changed.emit(f"Failed: {str(e)[:50]}")
                self.error_occurred.emit(str(e))
                return False
    
    def _connect_smart_fallback(self, port: str, baud_rate: int) -> bool:
        """
        Smart fallback: try python-OBD first, fallback to DirectELM327 if needed.
        Best for modern CAN vehicles.
        """
        self.logger.info("Starting smart fallback connection...")
        
        # Step 1: Try python-OBD if available
        if HAS_PYTHON_OBD:
            self.logger.info("Trying python-OBD...")
            try:
                if self._connect_python_obd(port, baud_rate):
                    self.use_direct_mode = False
                    self.logger.info("Smart: python-OBD successful")
                    return True
            except Exception as e:
                self.logger.warning(f"python-OBD failed: {e}")
        
        # Step 2: Fallback to DirectELM327
        self.logger.info("Falling back to DirectELM327...")
        self.use_direct_mode = True
        return self._connect_direct_universal(port, baud_rate)
    
    def _connect_auto(self, port: str, baud_rate: int) -> bool:
        """
        Auto strategy: choose best method based on vehicle info.
        """
        vehicle_year = self.vehicle_profile.get('year', 0) if self.vehicle_profile else 0
        vehicle_make = self.vehicle_profile.get('make', '').lower() if self.vehicle_profile else ''
        
        self.logger.info(f"Auto strategy - Year: {vehicle_year}, Make: {vehicle_make}")
        
        # For modern CAN vehicles, try python-OBD first
        if vehicle_year >= 2008 and HAS_PYTHON_OBD:
            self.logger.info("Modern vehicle, trying python-OBD first...")
            try:
                if self._connect_python_obd(port, baud_rate):
                    self.use_direct_mode = False
                    return True
            except Exception as e:
                self.logger.warning(f"python-OBD failed: {e}")
        
        # For all others, use DirectELM327
        self.logger.info("Using DirectELM327...")
        self.use_direct_mode = True
        return self._connect_direct_universal(port, baud_rate)
    
    def _connect_python_obd(self, port: str, baud_rate: int) -> bool:
        """Connect using python-OBD library"""
        if not HAS_PYTHON_OBD:
            raise Exception("python-OBD not installed")
        
        # Wake adapter
        self._wake_adapter(port, baud_rate)
        
        # Create connection
        self.logger.info("Creating python-OBD connection...")
        self.obd_connection = obd.OBD(
            portstr=port,
            baudrate=baud_rate,
            protocol=None,  # Auto-detect
            fast=True,
            timeout=10,
            check_voltage=False
        )
        
        time.sleep(1.5)
        
        # Check status
        obd_status = self.obd_connection.status()
        self.logger.info(f"OBD status: {obd_status}")
        
        if obd_status != obd.OBDStatus.CAR_CONNECTED:
            raise Exception(f"OBD not connected: {obd_status}")
        
        # Verify with simpler test
        self.connection_state = ConnectionState.VERIFYING
        self.status_changed.emit("Verifying...")
        
        if not self._verify_connection_simple():
            raise Exception("Connection verification failed")
        
        # Success
        self.serial_port = port
        self.baud_rate = baud_rate
        self.connected = True
        self.connection_state = ConnectionState.CONNECTED
        self.connection_type = ConnectionType.BLUETOOTH if 'bluetooth' in port.lower() else ConnectionType.SERIAL
        self.consecutive_failures = 0
        
        self._cache_supported_commands()
        self._start_polling()
        
        self.logger.info("=" * 40)
        self.logger.info("CONNECTION SUCCESSFUL (python-OBD)")
        self.logger.info(f"Supported commands: {len(self._supported_commands)}")
        self.logger.info("=" * 40)
        
        self.status_changed.emit("Connected (python-OBD)")
        self.connection_changed.emit(self.get_connection_status())
        return True
    
    def _connect_direct_universal(self, port: str, baud_rate: int) -> bool:
        """Connect using UniversalELM327"""
        self.use_direct_mode = True
        self.direct_elm = UniversalELM327(port, baud_rate, self.logger)
        
        if not self.direct_elm.connect():
            raise Exception("Serial connection failed")
        
        # Smart protocol detection
        self.connection_state = ConnectionState.PROTOCOL_DETECTION
        self.status_changed.emit("Detecting protocol...")
        
        vehicle_year = self.vehicle_profile.get('year', 0) if self.vehicle_profile else 0
        vehicle_make = self.vehicle_profile.get('make', '') if self.vehicle_profile else ''
        
        protocol = self.direct_elm.smart_protocol_detection(vehicle_year, vehicle_make)
        if not protocol:
            raise Exception("Protocol detection failed")
        
        self.detected_protocol = protocol
        self.performance_metrics['protocol'] = protocol.description
        self.protocol_detected.emit(protocol.description)
        
        # Discover supported PIDs
        self.connection_state = ConnectionState.VERIFYING
        self.status_changed.emit("Discovering PIDs...")
        
        self._discover_supported_pids_direct()
        
        if not self._supported_pids:
            self.logger.warning("No standard PIDs found, trying basic tests...")
            # Try at least RPM and Speed
            rpm = self.direct_elm.read_pid('rpm')
            speed = self.direct_elm.read_pid('speed')
            
            if rpm is not None:
                self._supported_pids.append('rpm')
            if speed is not None:
                self._supported_pids.append('speed')
            
            if not self._supported_pids:
                raise Exception("No supported PIDs found")
        
        # Success
        self.serial_port = port
        self.baud_rate = baud_rate
        self.connected = True
        self.connection_state = ConnectionState.CONNECTED
        self.connection_type = ConnectionType.BLUETOOTH if 'bluetooth' in port.lower() else ConnectionType.SERIAL
        self.consecutive_failures = 0
        
        self._start_polling()
        
        self.logger.info("=" * 40)
        self.logger.info("CONNECTION SUCCESSFUL (Direct ELM327)")
        self.logger.info(f"Protocol: {protocol.description}")
        self.logger.info(f"Supported PIDs: {len(self._supported_pids)}")
        self.logger.info("=" * 40)
        
        self.status_changed.emit(f"Connected ({protocol.description})")
        self.connection_changed.emit(self.get_connection_status())
        return True
    
    def _wake_adapter(self, port: str, baud_rate: int):
        """Wake up ELM327 adapter"""
        try:
            self.logger.debug(f"Waking adapter on {port}...")
            ser = serial.Serial(port=port, baudrate=baud_rate, timeout=3)
            
            wake_commands = [
                (b'\r\r', 0.3),
                (b'ATZ\r', 2.0),
                (b'ATE0\r', 0.3),
                (b'ATL0\r', 0.3),
                (b'ATS0\r', 0.3),
                (b'ATH0\r', 0.3),
            ]
            
            for cmd, delay in wake_commands:
                try:
                    ser.write(cmd)
                    ser.flush()
                    time.sleep(delay)
                    if ser.in_waiting:
                        ser.read(ser.in_waiting)
                except:
                    pass
            
            ser.close()
            time.sleep(1.0)
            self.logger.debug("Adapter wake complete")
            
        except Exception as e:
            self.logger.warning(f"Adapter wake warning: {e}")
    
    def _verify_connection_simple(self) -> bool:
        """Simple connection verification"""
        if not self.obd_connection:
            return False
        
        self.logger.info("Simple verification...")
        
        # Try just one or two basic PIDs
        test_commands = [
            (obd.commands.RPM, "RPM"),
            (obd.commands.SPEED, "SPEED"),
        ]
        
        time.sleep(0.5)
        
        for cmd, name in test_commands:
            try:
                response = self.obd_connection.query(cmd)
                
                if response and not response.is_null():
                    value = response.value
                    if hasattr(value, 'magnitude'):
                        value = value.magnitude
                    self.logger.info(f"✓ {name}: {value}")
                    return True
                    
            except Exception as e:
                self.logger.debug(f"  {name} error: {e}")
        
        self.logger.warning("Simple verification failed")
        return False
    
    def _discover_supported_pids_direct(self):
        """Discover supported PIDs using direct mode"""
        self._supported_pids = []
        
        if not self.direct_elm:
            return
        
        self.logger.info("Discovering supported PIDs...")
        
        # Test critical PIDs first
        test_pids = ['rpm', 'speed', 'coolant_temp', 'engine_load', 'throttle_position',
                     'intake_temp', 'fuel_level']
        
        for pid_key in test_pids:
            value = self.direct_elm.read_pid(pid_key)
            if value is not None:
                self._supported_pids.append(pid_key)
                self.logger.info(f"  ✓ {pid_key}: {value}")
        
        self.logger.info(f"Found {len(self._supported_pids)} supported PIDs")
    
    def _cache_supported_commands(self):
        """Cache supported OBD commands"""
        self._supported_commands.clear()
        self._supported_pids = []
        
        if self.obd_connection:
            try:
                for cmd in self.obd_connection.supported_commands:
                    self._supported_commands.add(cmd)
                
                # Map to PID keys
                for key, cmd in OBD_COMMAND_MAP.items():
                    if cmd in self._supported_commands:
                        self._supported_pids.append(key)
                
                self.logger.info(f"Cached {len(self._supported_commands)} commands, {len(self._supported_pids)} PIDs")
            except Exception as e:
                self.logger.warning(f"Error caching commands: {e}")
    
    # ================================
    # POLLING SYSTEM
    # ================================
    
    def _start_polling(self):
        """Start polling thread"""
        if self._polling_active:
            return
        
        self._stop_flag = False
        self._polling_active = True
        self._poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._poll_thread.start()
        self.logger.info("Polling started")
    
    def _stop_polling(self):
        """Stop polling thread safely"""
        if not self._polling_active:
            return
        
        self._stop_flag = True
        
        current_thread = threading.current_thread()
        if self._poll_thread and self._poll_thread.is_alive():
            if current_thread != self._poll_thread:
                self._poll_thread.join(timeout=3)
        
        self._polling_active = False
        self._poll_thread = None
        self.logger.info("Polling stopped")
    
    def _polling_loop(self):
        """Main polling loop"""
        self.logger.info("Polling loop started")
        self.connection_state = ConnectionState.POLLING
        
        while not self._stop_flag and self.connected:
            try:
                cycle_start = time.time()
                
                # Read data
                if self.use_direct_mode:
                    data = self._read_data_direct()
                else:
                    data = self._read_data_obd()
                
                if data:
                    self.latest_merged.update(data)
                    self.latest_merged['timestamp'] = datetime.now().isoformat()
                    self._last_successful_read = datetime.now()
                    self.consecutive_failures = 0
                    self.performance_metrics['successful_reads'] += 1
                    
                    self.live_data.emit(dict(self.latest_merged))
                else:
                    self.consecutive_failures += 1
                    self.performance_metrics['failed_reads'] += 1
                    
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        self._handle_connection_lost()
                        break
                
                self.performance_metrics['total_reads'] += 1
                
                elapsed = time.time() - cycle_start
                sleep_time = max(0.1, self.tier1_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                self.consecutive_failures += 1
                time.sleep(1)
        
        self.logger.info("Polling loop ended")
    
    def _read_data_obd(self) -> Dict[str, Any]:
        """Read data using python-OBD"""
        if not self.obd_connection:
            return {}
        
        data = {}
        current_time = time.time()
        
        # Tier 1 - Critical
        for pid_key in self._supported_pids:
            if pid_key in OBD_COMMAND_MAP:
                try:
                    resp = self.obd_connection.query(OBD_COMMAND_MAP[pid_key])
                    if resp and not resp.is_null():
                        value = resp.value
                        if hasattr(value, 'magnitude'):
                            value = value.magnitude
                        data[pid_key] = value
                except:
                    pass
        
        return data
    
    def _read_data_direct(self) -> Dict[str, Any]:
        """Read data using DirectELM327"""
        if not self.direct_elm:
            return {}
        
        data = {}
        current_time = time.time()
        
        # Tier 1 - Always read
        for pid_key in self._supported_pids:
            if pid_key in STANDARD_PIDS and STANDARD_PIDS[pid_key].tier == 1:
                value = self.direct_elm.read_pid(pid_key)
                if value is not None:
                    data[pid_key] = value
        
        # Tier 2 - Less frequent
        if current_time - self._last_tier2_read >= self.tier2_interval:
            for pid_key in self._supported_pids:
                if pid_key in STANDARD_PIDS and STANDARD_PIDS[pid_key].tier == 2:
                    value = self.direct_elm.read_pid(pid_key)
                    if value is not None:
                        data[pid_key] = value
            self._last_tier2_read = current_time
        
        # Tier 3 - Least frequent
        if current_time - self._last_tier3_read >= self.tier3_interval:
            for pid_key in self._supported_pids:
                if pid_key in STANDARD_PIDS and STANDARD_PIDS[pid_key].tier == 3:
                    value = self.direct_elm.read_pid(pid_key)
                    if value is not None:
                        data[pid_key] = value
            self._last_tier3_read = current_time
        
        return data
    
    # ================================
    # UTILITY METHODS
    # ================================
    
    def _cleanup_connection(self):
        """Clean up connection resources"""
        self._stop_polling()
        
        if self.obd_connection:
            try:
                self.obd_connection.close()
            except:
                pass
            self.obd_connection = None
        
        if self.direct_elm:
            self.direct_elm.disconnect()
            self.direct_elm = None
        
        self.connected = False
        self.connection_state = ConnectionState.DISCONNECTED
        self.connection_type = ConnectionType.DISCONNECTED
        self.serial_port = None
        self._supported_commands.clear()
        self._supported_pids = []
        self.latest_merged = {}
    
    def disconnect(self):
        """Disconnect from OBD adapter"""
        self.logger.info("Disconnect requested")
        with self.connection_lock:
            self._cleanup_connection()
        
        self.status_changed.emit("Disconnected")
        self.connection_changed.emit(self.get_connection_status())
    
    def _handle_connection_lost(self):
        """Handle connection lost"""
        self.logger.error("CONNECTION LOST")
        
        self._connected = False
        self.connection_state = ConnectionState.LOST
        self._stop_flag = True
        
        self.status_changed.emit("Connection Lost")
        self.connection_lost.emit()
        self.error_occurred.emit("Connection to vehicle lost")
        
        if self.obd_connection:
            try:
                self.obd_connection.close()
            except:
                pass
            self.obd_connection = None
        
        if self.direct_elm:
            self.direct_elm.disconnect()
            self.direct_elm = None
    
    # ================================
    # PUBLIC API
    # ================================
    
    def connect_to_port(self, port: str, baud_rate: int = 38400,
                       strategy: Optional[str] = None) -> bool:
        """Public method with backward compatibility"""
        if strategy:
            strategy_enum = ConnectionStrategy(strategy)
        else:
            strategy_enum = None
        
        return self.connect_universal(port, baud_rate, strategy_enum)
    
    def has_vehicle_profile(self) -> bool:
        return self.vehicle_profile is not None
    
    def get_vehicle_profile(self) -> Optional[Dict]:
        return self.vehicle_profile
    
    def is_connected(self) -> bool:
        return self.connected
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status"""
        return {
            "connected": self.connected,
            "connection_type": self.connection_type.value,
            "connection_state": self.connection_state.value,
            "strategy": self.connection_strategy.value,
            "port": self.serial_port,
            "baud_rate": self.baud_rate,
            "use_direct_mode": self.use_direct_mode,
            "protocol": self.detected_protocol.description if self.detected_protocol else "Auto",
            "supported_pids": len(self._supported_pids),
            "vehicle_profile": self.vehicle_profile.get('name') if self.vehicle_profile else None,
            "latest_data_keys": list(self.latest_merged.keys()),
            "performance_metrics": self.performance_metrics.copy()
        }
    
    def get_supported_pids(self) -> List[str]:
        """Get list of supported PID keys"""
        return list(self._supported_pids)
    
    def stop(self):
        """Stop the connectivity manager"""
        self.logger.info("Stopping connectivity manager")
        self._stop_polling()
        self.disconnect()
    
    def _init_pid_resolver(self):
        """Initialize PID profile resolver"""
        try:
            if PIDProfileResolver:
                possible_paths = []
                # Use CONFIG if available
                if _config:
                    possible_paths.append(str(_config.CONFIG_DIR / "pid_profiles"))
                # Fallback paths
                possible_paths.extend([
                    os.path.join(os.getcwd(), "configs", "pid_profiles"),
                    "./configs/pid_profiles",
                ])
                for path in possible_paths:
                    if os.path.exists(path):
                        self.pid_resolver = PIDProfileResolver(path)
                        self.logger.info(f"PID resolver initialized: {path}")
                        return
                self.pid_resolver = PIDProfileResolver()
                self.logger.info("PID resolver initialized with default path")
        except Exception as e:
            self.logger.warning(f"Could not initialize PID resolver: {e}")
            self.pid_resolver = None


# ================================
# BACKWARD COMPATIBILITY
# ================================

ConnectivityManager = UniversalConnectivityManager
ProfessionalConnectivityManager = UniversalConnectivityManager
OBDConnectivityManager = UniversalConnectivityManager


# ================================
# TEST FUNCTION
# ================================

def test_universal_connection():
    """Test the universal connectivity"""
    print("Testing Universal Connectivity...")
    
    manager = UniversalConnectivityManager()
    
    # Test with a simulated vehicle profile
    profile = {
        'name': 'Test Vehicle',
        'make': 'Nissan',
        'model': 'Altima',
        'year': 2017
    }
    
    manager.set_vehicle_profile(profile)
    
    # Detect ports
    ports = manager.detect_com_ports()
    print(f"Available ports: {[p['port'] for p in ports]}")
    
    if ports:
        port = ports[0]['port']
        print(f"\nTrying connection to {port}...")
        
        # Try different strategies
        strategies = [
            ConnectionStrategy.AUTO,
            ConnectionStrategy.SMART_FALLBACK,
            ConnectionStrategy.DIRECT_ONLY,
        ]
        
        for strategy in strategies:
            print(f"\nTrying strategy: {strategy.value}")
            success = manager.connect_universal(port, 38400, strategy)
            if success:
                print(f"✓ Success with {strategy.value}")
                print(f"Supported PIDs: {manager.get_supported_pids()}")
                manager.disconnect()
                break
            else:
                print(f"✗ Failed with {strategy.value}")
    
    print("\nTest complete.")


if __name__ == "__main__":
    test_universal_connection()