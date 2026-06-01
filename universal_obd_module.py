"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Universal Obd Module
"""

"""
================================================================================
UNIVERSAL OBD-II CONNECTIVITY MODULE v5.0
================================================================================
Professional architecture that works with ANY OBD-II compliant vehicle.

DESIGN PATTERN:
- ONE module handles ALL vehicles
- Vehicle-specific data is in JSON profiles (not code)
- Auto-detects protocol (CAN for modern, K-Line for older)
- Extensible PID database

SUPPORTED VEHICLES:
- 2008+ vehicles: CAN protocol (ISO 15765-4) - FAST
- 1996-2007 vehicles: K-Line (ISO 9141-2, ISO 14230-4) - SLOWER
- Your 2017 Nissan Altima: CAN protocol - WILL WORK GREAT!

Author: Professional OBD Module
Version: 5.0
================================================================================
"""

import time
import threading
import json
import os
import re
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from pathlib import Path

# Serial communication
import serial
import serial.tools.list_ports

# python-OBD (optional but recommended for CAN vehicles)
try:
    import obd
    from obd import OBDStatus, OBDCommand
    HAS_PYTHON_OBD = True
except ImportError:
    HAS_PYTHON_OBD = False
    print("Note: python-OBD not installed. Install with: pip install obd")

# PySide6 signals (optional)
try:
    from PySide6.QtCore import QObject, Signal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # Create dummy classes
    class QObject:
        def __init__(self, parent=None): pass
    def Signal(*args):
        return None


# ================================================================================
# LOGGING CONFIGURATION
# ================================================================================

def setup_logger(name: str = 'OBD', level: int = logging.INFO) -> logging.Logger:
    """Setup a logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # Create logs directory
    Path('./logs').mkdir(exist_ok=True)
    
    # File handler (detailed)
    fh = logging.FileHandler(f'./logs/{name.lower()}.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(fh)
    
    # Console handler (info only)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(ch)
    
    return logger


# ================================================================================
# ENUMS AND DATA CLASSES
# ================================================================================

class Protocol(Enum):
    """OBD-II Communication Protocols"""
    AUTO = ("0", "Auto Detect")
    SAE_J1850_PWM = ("1", "SAE J1850 PWM (Ford)")
    SAE_J1850_VPW = ("2", "SAE J1850 VPW (GM)")
    ISO_9141_2 = ("3", "ISO 9141-2 (Older Asian/European)")
    ISO_14230_4_KWP_SLOW = ("4", "ISO 14230-4 KWP 5-baud")
    ISO_14230_4_KWP_FAST = ("5", "ISO 14230-4 KWP Fast")
    ISO_15765_4_CAN_11_500 = ("6", "CAN 11-bit 500kbaud")  # Most 2008+ cars
    ISO_15765_4_CAN_29_500 = ("7", "CAN 29-bit 500kbaud")  # Trucks
    ISO_15765_4_CAN_11_250 = ("8", "CAN 11-bit 250kbaud")
    ISO_15765_4_CAN_29_250 = ("9", "CAN 29-bit 250kbaud")
    
    def __init__(self, code: str, description: str):
        self._code = code
        self._description = description
    
    @property
    def code(self) -> str:
        return self._code
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def is_can(self) -> bool:
        return self._code in ('6', '7', '8', '9')
    
    @property
    def is_kline(self) -> bool:
        return self._code in ('3', '4', '5')


class ConnectionState(Enum):
    """Connection state machine"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    POLLING = "polling"
    ERROR = "error"
    LOST = "lost"


@dataclass
class PIDDefinition:
    """Definition of a single PID"""
    pid: int
    name: str
    description: str = ""
    unit: str = ""
    mode: int = 0x01
    bytes_returned: int = 1
    min_value: float = 0
    max_value: float = 255
    formula: str = "A"  # Formula string like "A", "(A*256+B)/4", "A-40"
    tier: int = 1  # 1=critical, 2=important, 3=secondary
    
    def decode(self, data: bytes) -> Optional[float]:
        """Decode raw bytes using the formula"""
        if not data or len(data) < self.bytes_returned:
            return None
        
        try:
            # Create variable mapping
            variables = {
                'A': data[0] if len(data) > 0 else 0,
                'B': data[1] if len(data) > 1 else 0,
                'C': data[2] if len(data) > 2 else 0,
                'D': data[3] if len(data) > 3 else 0,
            }
            
            # Evaluate formula safely
            result = eval(self.formula, {"__builtins__": {}}, variables)
            return float(result)
        except Exception:
            return None


@dataclass
class VehicleProfile:
    """Vehicle profile for manufacturer-specific settings"""
    make: str
    model: str = ""
    year: int = 0
    protocol: Optional[Protocol] = None
    extra_pids: Dict[str, PIDDefinition] = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        parts = [self.make]
        if self.model:
            parts.append(self.model)
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts)


# ================================================================================
# STANDARD OBD-II PID DATABASE
# ================================================================================

STANDARD_PIDS: Dict[str, PIDDefinition] = {
    # === TIER 1: Critical - Poll every cycle ===
    "rpm": PIDDefinition(
        pid=0x0C, name="Engine RPM", unit="rpm",
        bytes_returned=2, formula="(A*256+B)/4",
        min_value=0, max_value=16383.75, tier=1
    ),
    "speed": PIDDefinition(
        pid=0x0D, name="Vehicle Speed", unit="km/h",
        bytes_returned=1, formula="A",
        min_value=0, max_value=255, tier=1
    ),
    "coolant_temp": PIDDefinition(
        pid=0x05, name="Coolant Temperature", unit="°C",
        bytes_returned=1, formula="A-40",
        min_value=-40, max_value=215, tier=1
    ),
    "engine_load": PIDDefinition(
        pid=0x04, name="Engine Load", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=1
    ),
    "throttle_position": PIDDefinition(
        pid=0x11, name="Throttle Position", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=1
    ),
    
    # === TIER 2: Important - Poll every 1-2 seconds ===
    "intake_temp": PIDDefinition(
        pid=0x0F, name="Intake Air Temperature", unit="°C",
        bytes_returned=1, formula="A-40",
        min_value=-40, max_value=215, tier=2
    ),
    "maf": PIDDefinition(
        pid=0x10, name="MAF Air Flow", unit="g/s",
        bytes_returned=2, formula="(A*256+B)/100",
        min_value=0, max_value=655.35, tier=2
    ),
    "map": PIDDefinition(
        pid=0x0B, name="Intake Manifold Pressure", unit="kPa",
        bytes_returned=1, formula="A",
        min_value=0, max_value=255, tier=2
    ),
    "timing_advance": PIDDefinition(
        pid=0x0E, name="Timing Advance", unit="°",
        bytes_returned=1, formula="(A-128)/2",
        min_value=-64, max_value=63.5, tier=2
    ),
    "short_fuel_trim_1": PIDDefinition(
        pid=0x06, name="Short Term Fuel Trim Bank 1", unit="%",
        bytes_returned=1, formula="(A-128)*100/128",
        min_value=-100, max_value=99.2, tier=2
    ),
    "long_fuel_trim_1": PIDDefinition(
        pid=0x07, name="Long Term Fuel Trim Bank 1", unit="%",
        bytes_returned=1, formula="(A-128)*100/128",
        min_value=-100, max_value=99.2, tier=2
    ),
    "short_fuel_trim_2": PIDDefinition(
        pid=0x08, name="Short Term Fuel Trim Bank 2", unit="%",
        bytes_returned=1, formula="(A-128)*100/128",
        min_value=-100, max_value=99.2, tier=2
    ),
    "long_fuel_trim_2": PIDDefinition(
        pid=0x09, name="Long Term Fuel Trim Bank 2", unit="%",
        bytes_returned=1, formula="(A-128)*100/128",
        min_value=-100, max_value=99.2, tier=2
    ),
    "fuel_pressure": PIDDefinition(
        pid=0x0A, name="Fuel Pressure", unit="kPa",
        bytes_returned=1, formula="A*3",
        min_value=0, max_value=765, tier=2
    ),
    "o2_voltage_1": PIDDefinition(
        pid=0x14, name="O2 Sensor 1 Voltage", unit="V",
        bytes_returned=2, formula="A/200",
        min_value=0, max_value=1.275, tier=2
    ),
    "o2_voltage_2": PIDDefinition(
        pid=0x15, name="O2 Sensor 2 Voltage", unit="V",
        bytes_returned=2, formula="A/200",
        min_value=0, max_value=1.275, tier=2
    ),
    
    # === TIER 3: Secondary - Poll every 5-10 seconds ===
    "fuel_level": PIDDefinition(
        pid=0x2F, name="Fuel Tank Level", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=3
    ),
    "runtime": PIDDefinition(
        pid=0x1F, name="Engine Runtime", unit="sec",
        bytes_returned=2, formula="A*256+B",
        min_value=0, max_value=65535, tier=3
    ),
    "distance_mil": PIDDefinition(
        pid=0x21, name="Distance with MIL On", unit="km",
        bytes_returned=2, formula="A*256+B",
        min_value=0, max_value=65535, tier=3
    ),
    "distance_cleared": PIDDefinition(
        pid=0x31, name="Distance Since Codes Cleared", unit="km",
        bytes_returned=2, formula="A*256+B",
        min_value=0, max_value=65535, tier=3
    ),
    "barometric_pressure": PIDDefinition(
        pid=0x33, name="Barometric Pressure", unit="kPa",
        bytes_returned=1, formula="A",
        min_value=0, max_value=255, tier=3
    ),
    "ambient_temp": PIDDefinition(
        pid=0x46, name="Ambient Air Temperature", unit="°C",
        bytes_returned=1, formula="A-40",
        min_value=-40, max_value=215, tier=3
    ),
    "oil_temp": PIDDefinition(
        pid=0x5C, name="Engine Oil Temperature", unit="°C",
        bytes_returned=1, formula="A-40",
        min_value=-40, max_value=210, tier=3
    ),
    "fuel_rate": PIDDefinition(
        pid=0x5E, name="Engine Fuel Rate", unit="L/h",
        bytes_returned=2, formula="(A*256+B)/20",
        min_value=0, max_value=3276.75, tier=3
    ),
    "control_module_voltage": PIDDefinition(
        pid=0x42, name="Control Module Voltage", unit="V",
        bytes_returned=2, formula="(A*256+B)/1000",
        min_value=0, max_value=65.535, tier=3
    ),
    "absolute_load": PIDDefinition(
        pid=0x43, name="Absolute Load Value", unit="%",
        bytes_returned=2, formula="(A*256+B)*100/255",
        min_value=0, max_value=25700, tier=3
    ),
    "commanded_throttle": PIDDefinition(
        pid=0x4C, name="Commanded Throttle Actuator", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=3
    ),
    "ethanol_percent": PIDDefinition(
        pid=0x52, name="Ethanol Fuel %", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=3
    ),
    "catalyst_temp_b1s1": PIDDefinition(
        pid=0x3C, name="Catalyst Temp B1S1", unit="°C",
        bytes_returned=2, formula="(A*256+B)/10-40",
        min_value=-40, max_value=6513.5, tier=3
    ),
    "evap_purge": PIDDefinition(
        pid=0x2E, name="Evaporative Purge", unit="%",
        bytes_returned=1, formula="A*100/255",
        min_value=0, max_value=100, tier=3
    ),
    "warmups_since_clear": PIDDefinition(
        pid=0x30, name="Warm-ups Since Clear", unit="",
        bytes_returned=1, formula="A",
        min_value=0, max_value=255, tier=3
    ),
}


# ================================================================================
# MANUFACTURER-SPECIFIC PID DATABASES
# ================================================================================

NISSAN_PIDS: Dict[str, PIDDefinition] = {
    "nissan_battery_current": PIDDefinition(
        pid=0x1E, mode=0x21, name="Battery Current (Nissan)", unit="A",
        bytes_returned=2, formula="(A*256+B)/100-327.68",
        tier=2
    ),
    "nissan_battery_voltage": PIDDefinition(
        pid=0x01, mode=0x21, name="Battery Voltage (Nissan)", unit="V",
        bytes_returned=1, formula="A*0.08",
        tier=2
    ),
}

TOYOTA_PIDS: Dict[str, PIDDefinition] = {
    # Toyota-specific PIDs would go here
}

FORD_PIDS: Dict[str, PIDDefinition] = {
    # Ford-specific PIDs would go here
}

# Manufacturer PID registry
MANUFACTURER_PIDS: Dict[str, Dict[str, PIDDefinition]] = {
    "nissan": NISSAN_PIDS,
    "toyota": TOYOTA_PIDS,
    "ford": FORD_PIDS,
}


# ================================================================================
# DIRECT ELM327 INTERFACE (For both CAN and K-Line)
# ================================================================================

class ELM327Interface:
    """
    Direct ELM327 communication interface.
    
    Handles both CAN (fast) and K-Line (slow) protocols.
    """
    
    ERROR_PATTERNS = [b'NO DATA', b'ERROR', b'UNABLE', b'BUS INIT', b'CAN ERROR', b'?']
    
    def __init__(self, port: str, baudrate: int = 38400, logger: logging.Logger = None):
        self.port = port
        self.baudrate = baudrate
        self.logger = logger or setup_logger('ELM327')
        self.serial: Optional[serial.Serial] = None
        self.protocol: Optional[Protocol] = None
        self.elm_version: str = ""
        self.voltage: float = 0.0
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """Establish serial connection"""
        # Validate port name (security)
        if not self._is_valid_port(self.port):
            self.logger.error(f"Invalid port name: {self.port}")
            return False
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=5,
                write_timeout=5
            )
            time.sleep(0.3)
            self._flush()
            self.logger.info(f"Connected to {self.port}")
            return True
        except serial.SerialException as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def _is_valid_port(self, port: str) -> bool:
        """Validate port name to prevent injection attacks"""
        if not port:
            return False
        # Windows: COM1-COM256
        if re.match(r'^COM\d{1,3}$', port, re.IGNORECASE):
            return True
        # Linux/Mac: /dev/tty*
        if re.match(r'^/dev/(tty(USB|ACM|S)|cu\.)\w*\d*$', port):
            return True
        return False
    
    def disconnect(self):
        """Close serial connection"""
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
        """Send command and get response"""
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
                    time.sleep(0.02)
                
                # Clean response
                text = response.decode('ascii', errors='ignore')
                text = text.replace(cmd, '').replace('>', '')
                text = ' '.join(text.split())
                return text.strip()
                
            except Exception as e:
                self.logger.debug(f"Command error: {e}")
                return ""
    
    def is_error_response(self, response: str) -> bool:
        """Check if response indicates an error"""
        resp_bytes = response.upper().encode()
        return any(err in resp_bytes for err in self.ERROR_PATTERNS)
    
    def initialize(self, protocol: Protocol = Protocol.AUTO) -> bool:
        """
        Initialize ELM327 adapter.
        
        For 2017 Altima (and most 2008+ cars), Protocol 6 (CAN) will be auto-detected.
        """
        self.logger.info("Initializing ELM327...")
        
        # Reset adapter
        response = self.send_command('ATZ', timeout=3)
        if 'ELM' in response.upper():
            self.elm_version = response
            self.logger.info(f"Adapter: {response}")
        else:
            # Try again
            time.sleep(1)
            response = self.send_command('ATZ', timeout=3)
            self.elm_version = response
        
        time.sleep(0.5)
        
        # Configure adapter
        self.send_command('ATE0')  # Echo off
        self.send_command('ATL0')  # Linefeeds off
        self.send_command('ATS0')  # Spaces off (easier parsing)
        self.send_command('ATH0')  # Headers off
        self.send_command('ATSP' + protocol.code)  # Set protocol
        
        # Get voltage
        voltage_resp = self.send_command('ATRV')
        match = re.search(r'(\d+\.?\d*)', voltage_resp)
        if match:
            self.voltage = float(match.group(1))
            self.logger.info(f"Voltage: {self.voltage}V")
        
        # For K-Line protocols, need extra init time
        if protocol.is_kline:
            self.logger.info("K-Line protocol - waiting for bus init...")
            time.sleep(2)
        
        self.protocol = protocol
        return True
    
    def detect_protocol(self) -> Optional[Protocol]:
        """Auto-detect the vehicle's OBD protocol"""
        self.logger.info("Auto-detecting protocol...")
        
        # Initialize with auto-detect
        self.initialize(Protocol.AUTO)
        
        # Try to query supported PIDs
        response = self.send_command('0100', timeout=10)
        
        if '4100' in response.replace(' ', ''):
            # Get detected protocol
            proto_resp = self.send_command('ATDPN')
            self.logger.info(f"Detected protocol: {proto_resp}")
            
            # Map response to Protocol enum
            proto_code = proto_resp.strip()[-1] if proto_resp else '6'
            
            for p in Protocol:
                if p.code == proto_code:
                    self.protocol = p
                    self.logger.info(f"Protocol: {p.description}")
                    return p
            
            # Default to CAN for modern vehicles
            self.protocol = Protocol.ISO_15765_4_CAN_11_500
            return self.protocol
        
        self.logger.warning("Protocol auto-detect failed")
        return None
    
    def query_pid(self, mode: int, pid: int) -> Optional[bytes]:
        """Query a PID and return raw response bytes"""
        cmd = f"{mode:02X}{pid:02X}"
        
        # Longer timeout for K-Line
        timeout = 8.0 if (self.protocol and self.protocol.is_kline) else 3.0
        
        response = self.send_command(cmd, timeout=timeout)
        
        if self.is_error_response(response):
            return None
        
        try:
            # Parse response: expect "4X YY ZZ..." where X=mode+0x40, YY=pid
            clean = response.replace(' ', '').upper()
            expected_prefix = f"{mode + 0x40:02X}{pid:02X}"
            
            if expected_prefix not in clean:
                return None
            
            idx = clean.find(expected_prefix)
            data_hex = clean[idx + 4:]  # Skip mode+pid bytes
            
            # Extract valid hex characters
            data_hex = ''.join(c for c in data_hex if c in '0123456789ABCDEF')
            
            if len(data_hex) >= 2:
                return bytes.fromhex(data_hex)
                
        except Exception as e:
            self.logger.debug(f"Parse error for {cmd}: {e}")
        
        return None
    
    def read_pid(self, pid_def: PIDDefinition) -> Optional[float]:
        """Read a PID using its definition and decode the value"""
        data = self.query_pid(pid_def.mode, pid_def.pid)
        if data:
            return pid_def.decode(data)
        return None


# ================================================================================
# MAIN CONNECTIVITY MANAGER
# ================================================================================

class UniversalOBDManager:
    """
    Universal OBD-II Connectivity Manager
    
    Works with ANY OBD-II compliant vehicle (1996+ US, 2001+ EU, 2008+ most others).
    
    Features:
    - Auto protocol detection
    - Tiered polling (critical PIDs polled faster)
    - Vehicle profile support
    - Manufacturer-specific PIDs
    - Thread-safe operation
    """
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or setup_logger('OBDManager')
        
        # Connection
        self.elm: Optional[ELM327Interface] = None
        self.state = ConnectionState.DISCONNECTED
        self.port: Optional[str] = None
        
        # Vehicle
        self.vehicle_profile: Optional[VehicleProfile] = None
        
        # PIDs
        self.pid_database: Dict[str, PIDDefinition] = dict(STANDARD_PIDS)
        self.supported_pids: List[str] = []
        
        # Data
        self.current_data: Dict[str, float] = {}
        self._data_lock = threading.Lock()
        
        # Polling
        self._polling = False
        self._stop_flag = False
        self._poll_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_data: Optional[Callable[[Dict[str, float]], None]] = None
        self.on_state_change: Optional[Callable[[ConnectionState], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Timing (adjustable)
        self.poll_interval_tier1 = 0.2  # 200ms for critical PIDs
        self.poll_interval_tier2 = 1.0  # 1s for important PIDs
        self.poll_interval_tier3 = 5.0  # 5s for secondary PIDs
        
        self.logger.info("UniversalOBDManager initialized")
    
    def _set_state(self, state: ConnectionState):
        """Update connection state and notify"""
        old_state = self.state
        self.state = state
        if old_state != state:
            self.logger.info(f"State: {old_state.value} -> {state.value}")
            if self.on_state_change:
                self.on_state_change(state)
    
    def set_vehicle_profile(self, profile: VehicleProfile):
        """
        Set the vehicle profile.
        
        This adds manufacturer-specific PIDs to the database.
        """
        self.vehicle_profile = profile
        self.logger.info(f"Vehicle profile set: {profile.display_name}")
        
        # Add manufacturer PIDs
        make_lower = profile.make.lower()
        if make_lower in MANUFACTURER_PIDS:
            self.pid_database.update(MANUFACTURER_PIDS[make_lower])
            self.logger.info(f"Added {len(MANUFACTURER_PIDS[make_lower])} {profile.make} PIDs")
        
        # Add any extra PIDs from profile
        if profile.extra_pids:
            self.pid_database.update(profile.extra_pids)
    
    def detect_ports(self) -> List[Dict[str, str]]:
        """Detect available serial ports"""
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                'port': p.device,
                'description': p.description,
                'hwid': p.hwid,
                'is_bluetooth': 'bluetooth' in p.description.lower()
            })
        return ports
    
    def connect(self, port: str, baudrate: int = 38400, 
                protocol: Protocol = Protocol.AUTO) -> bool:
        """
        Connect to the OBD adapter.
        
        Args:
            port: Serial port (e.g., "COM6" on Windows)
            baudrate: Baud rate (usually 38400)
            protocol: Protocol to use (AUTO recommended for most cars)
        
        Returns:
            True if connection successful
        """
        self._set_state(ConnectionState.CONNECTING)
        self.logger.info(f"Connecting to {port}...")
        
        try:
            # Create interface
            self.elm = ELM327Interface(port, baudrate, self.logger)
            
            if not self.elm.connect():
                raise Exception("Serial connection failed")
            
            # Detect or set protocol
            if protocol == Protocol.AUTO:
                detected = self.elm.detect_protocol()
                if not detected:
                    raise Exception("Protocol detection failed")
            else:
                self.elm.initialize(protocol)
            
            # Discover supported PIDs
            self._discover_supported_pids()
            
            if not self.supported_pids:
                raise Exception("No supported PIDs found")
            
            # Success
            self.port = port
            self._set_state(ConnectionState.CONNECTED)
            self.logger.info(f"Connected! {len(self.supported_pids)} PIDs supported")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_state(ConnectionState.ERROR)
            if self.elm:
                self.elm.disconnect()
                self.elm = None
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def disconnect(self):
        """Disconnect from the OBD adapter"""
        self.stop_polling()
        
        if self.elm:
            self.elm.disconnect()
            self.elm = None
        
        self.port = None
        self.supported_pids = []
        self.current_data = {}
        self._set_state(ConnectionState.DISCONNECTED)
    
    def _discover_supported_pids(self):
        """
        Discover which PIDs are supported by the vehicle.
        
        For most modern vehicles, we can query the support bitmaps.
        For older vehicles, we may need to try each PID.
        """
        self.supported_pids = []
        
        if not self.elm:
            return
        
        self.logger.info("Discovering supported PIDs...")
        
        # Try to get supported PIDs bitmap
        bitmap_pids = [0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0]
        supported_pid_numbers = set()
        
        for bitmap_pid in bitmap_pids:
            data = self.elm.query_pid(0x01, bitmap_pid)
            if data and len(data) >= 4:
                # Parse bitmap
                bitmap = int.from_bytes(data[:4], 'big')
                base_pid = bitmap_pid + 1
                
                for i in range(32):
                    if bitmap & (1 << (31 - i)):
                        supported_pid_numbers.add(base_pid + i)
                
                self.logger.debug(f"Bitmap 0x{bitmap_pid:02X}: found {bin(bitmap).count('1')} PIDs")
        
        # Match to our PID database
        for pid_key, pid_def in self.pid_database.items():
            if pid_def.mode == 0x01 and pid_def.pid in supported_pid_numbers:
                self.supported_pids.append(pid_key)
        
        # If bitmap query failed, try common PIDs directly
        if not self.supported_pids:
            self.logger.info("Bitmap query failed, trying PIDs directly...")
            critical_pids = ['rpm', 'speed', 'coolant_temp', 'engine_load', 'throttle_position']
            
            for pid_key in critical_pids:
                if pid_key in self.pid_database:
                    value = self.elm.read_pid(self.pid_database[pid_key])
                    if value is not None:
                        self.supported_pids.append(pid_key)
                        self.logger.info(f"  {pid_key}: {value}")
        
        self.logger.info(f"Found {len(self.supported_pids)} supported PIDs")
    
    def read_pid(self, pid_key: str) -> Optional[float]:
        """Read a single PID value"""
        if not self.elm or pid_key not in self.pid_database:
            return None
        
        return self.elm.read_pid(self.pid_database[pid_key])
    
    def read_all(self) -> Dict[str, float]:
        """Read all supported PIDs"""
        data = {}
        
        for pid_key in self.supported_pids:
            value = self.read_pid(pid_key)
            if value is not None:
                data[pid_key] = value
        
        with self._data_lock:
            self.current_data.update(data)
        
        return data
    
    def start_polling(self):
        """Start background polling thread"""
        if self._polling:
            return
        
        self._stop_flag = False
        self._polling = True
        self._set_state(ConnectionState.POLLING)
        
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        self.logger.info("Polling started")
    
    def stop_polling(self):
        """Stop background polling"""
        self._stop_flag = True
        self._polling = False
        
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2)
        
        self._poll_thread = None
        self.logger.info("Polling stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        last_tier2 = 0
        last_tier3 = 0
        
        while not self._stop_flag and self.elm:
            try:
                current_time = time.time()
                data = {}
                
                # Tier 1: Critical PIDs (every cycle)
                for pid_key in self.supported_pids:
                    pid_def = self.pid_database.get(pid_key)
                    if pid_def and pid_def.tier == 1:
                        value = self.elm.read_pid(pid_def)
                        if value is not None:
                            data[pid_key] = value
                
                # Tier 2: Important PIDs
                if current_time - last_tier2 >= self.poll_interval_tier2:
                    for pid_key in self.supported_pids:
                        pid_def = self.pid_database.get(pid_key)
                        if pid_def and pid_def.tier == 2:
                            value = self.elm.read_pid(pid_def)
                            if value is not None:
                                data[pid_key] = value
                    last_tier2 = current_time
                
                # Tier 3: Secondary PIDs
                if current_time - last_tier3 >= self.poll_interval_tier3:
                    for pid_key in self.supported_pids:
                        pid_def = self.pid_database.get(pid_key)
                        if pid_def and pid_def.tier == 3:
                            value = self.elm.read_pid(pid_def)
                            if value is not None:
                                data[pid_key] = value
                    last_tier3 = current_time
                
                # Update current data
                if data:
                    with self._data_lock:
                        self.current_data.update(data)
                    
                    if self.on_data:
                        self.on_data(data)
                
                time.sleep(self.poll_interval_tier1)
                
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                time.sleep(1)
        
        self.logger.info("Poll loop ended")
    
    def get_current_data(self) -> Dict[str, float]:
        """Get the latest data snapshot"""
        with self._data_lock:
            return dict(self.current_data)
    
    def get_pid_info(self, pid_key: str) -> Optional[Dict[str, Any]]:
        """Get information about a PID"""
        if pid_key not in self.pid_database:
            return None
        
        pid_def = self.pid_database[pid_key]
        return {
            'key': pid_key,
            'name': pid_def.name,
            'unit': pid_def.unit,
            'min': pid_def.min_value,
            'max': pid_def.max_value,
            'supported': pid_key in self.supported_pids
        }
    
    def get_all_pid_info(self) -> List[Dict[str, Any]]:
        """Get information about all PIDs"""
        result = []
        for pid_key in self.pid_database:
            info = self.get_pid_info(pid_key)
            if info:
                result.append(info)
        return result


# ================================================================================
# PYQT5 WRAPPER (Optional)
# ================================================================================

if HAS_PYQT:
    class OBDManagerQt(QObject, UniversalOBDManager):
        """
        Qt wrapper for UniversalOBDManager with signals.
        
        Use this if you're building a PyQt5/PySide application.
        """
        
        # Qt signals
        data_received = Signal(dict)
        state_changed = Signal(str)
        error_occurred = Signal(str)
        
        def __init__(self, parent=None):
            QObject.__init__(self, parent)
            UniversalOBDManager.__init__(self)
            
            # Connect callbacks to signals
            self.on_data = lambda d: self.data_received.emit(d)
            self.on_state_change = lambda s: self.state_changed.emit(s.value)
            self.on_error = lambda e: self.error_occurred.emit(e)


# ================================================================================
# CONVENIENCE ALIASES
# ================================================================================

# For backward compatibility
ConnectivityManager = UniversalOBDManager
ProfessionalConnectivityManager = UniversalOBDManager
OBDConnectivityManager = UniversalOBDManager


# ================================================================================
# EXAMPLE USAGE
# ================================================================================

def example_usage():
    """Example of how to use the module"""
    
    print("=" * 60)
    print("UNIVERSAL OBD-II MODULE - EXAMPLE")
    print("=" * 60)
    
    # Create manager
    manager = UniversalOBDManager()
    
    # Set vehicle profile (optional but recommended)
    profile = VehicleProfile(make="Nissan", model="Altima", year=2017)
    manager.set_vehicle_profile(profile)
    
    # Detect ports
    ports = manager.detect_ports()
    print(f"\nAvailable ports: {[p['port'] for p in ports]}")
    
    if not ports:
        print("No ports found!")
        return
    
    # Connect (use first port for demo)
    port = ports[0]['port']
    print(f"\nConnecting to {port}...")
    
    if manager.connect(port):
        print(f"Connected! Supported PIDs: {manager.supported_pids}")
        
        # Read all data once
        data = manager.read_all()
        print(f"\nCurrent data:")
        for key, value in data.items():
            pid_def = manager.pid_database.get(key)
            unit = pid_def.unit if pid_def else ""
            print(f"  {key}: {value:.2f} {unit}")
        
        # Start polling
        def on_data(data):
            rpm = data.get('rpm', 0)
            speed = data.get('speed', 0)
            print(f"  RPM: {rpm:.0f} | Speed: {speed:.0f} km/h", end='\r')
        
        manager.on_data = on_data
        manager.start_polling()
        
        print("\nPolling for 10 seconds...")
        time.sleep(10)
        
        manager.stop_polling()
        manager.disconnect()
        print("\nDone!")
    else:
        print("Connection failed!")


if __name__ == "__main__":
    example_usage()
