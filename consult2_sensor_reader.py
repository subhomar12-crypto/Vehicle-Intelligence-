"""
CONSULT-II Sensor Reader - Complete Implementation
==================================================

Reads live sensor data from Nissan ECU via Nisscom USB adapter.
Supports both Service 0xA0 (direct) and AC 81 + 0x21 (MCU buffered) methods.

Target: 2003 Nissan Patrol with RB25DET (ECU ID: 1VC816)
"""

import serial
import time
import ctypes
import struct
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from enum import Enum

# Windows API constants
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6

# Load kernel32 on Windows
try:
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.EscapeCommFunction.restype = wintypes.BOOL
    IS_WINDOWS = True
except Exception:
    IS_WINDOWS = False
    import fcntl  # For Linux/Raspberry Pi


class SensorType(Enum):
    """Sensor data types for proper parsing."""
    UINT8 = "uint8"
    UINT16 = "uint16"
    TEMP_C = "temp_c"
    TEMP_F = "temp_f"
    RPM = "rpm"
    VOLTAGE = "voltage"
    SPEED_KPH = "speed_kph"
    SPEED_MPH = "speed_mph"
    PERCENT = "percent"
    RAW = "raw"


@dataclass
class SensorDef:
    """Sensor definition from NDS II decompilation."""
    name: str
    short_name: str
    addr0: int  # 0x11 = 1 byte, 0x12 = 2 bytes
    addr1: int  # Parameter address
    sensor_type: SensorType
    unit: str
    min_val: float = 0.0
    max_val: float = 0.0
    scale_formula: Optional[Callable] = None
    
    def get_ac_entry(self) -> List[int]:
        """Get AC 81 frame entry for this sensor."""
        return [0x02, self.addr0, self.addr1]
    
    def parse_data(self, data: bytes) -> float:
        """Parse raw bytes to human-readable value."""
        if not data:
            return 0.0
            
        if self.addr0 == 0x11 and len(data) >= 1:
            # 1-byte sensor
            raw = data[0]
            if self.sensor_type == SensorType.TEMP_C:
                return raw - 50.0
            elif self.sensor_type == SensorType.TEMP_F:
                return (raw - 50.0) * 1.8 + 32.0
            elif self.sensor_type == SensorType.SPEED_MPH:
                return raw * 1.24274
            elif self.sensor_type == SensorType.SPEED_KPH:
                return float(raw)
            else:
                return float(raw)
                
        elif self.addr0 == 0x12 and len(data) >= 2:
            # 2-byte sensor (big endian)
            raw16 = (data[0] << 8) | data[1]
            if self.sensor_type == SensorType.RPM:
                return raw16 * 12.5
            elif self.sensor_type == SensorType.VOLTAGE:
                return raw16 * 0.005
            elif self.sensor_type == SensorType.SPEED_KPH:
                return float(raw16)
            else:
                return float(raw16)
        
        return 0.0


# ECM Sensor Database - Extracted from frmMain::method_82()
ECM_SENSORS = {
    0: SensorDef("Engine RPM", "RPM", 0x12, 0x01, SensorType.RPM, "rpm", 0, 8000),
    1: SensorDef("Air Flow Meter Voltage", "AFM V", 0x12, 0x04, SensorType.VOLTAGE, "V", 0, 5.0),
    2: SensorDef("Coolant Temperature", "Coolant", 0x11, 0x01, SensorType.TEMP_C, "°C", -40, 150),
    3: SensorDef("Short Term Fuel Trim", "STFT", 0x11, 0x5F, SensorType.PERCENT, "%", -25, 25),
    4: SensorDef("Long Term Fuel Trim", "LTFT", 0x11, 0x61, SensorType.PERCENT, "%", -25, 25),
    5: SensorDef("Vehicle Speed (mph)", "Speed MPH", 0x11, 0x02, SensorType.SPEED_MPH, "mph", 0, 200),
    6: SensorDef("Vehicle Speed (kph)", "Speed KPH", 0x12, 0x1A, SensorType.SPEED_KPH, "kph", 0, 255),
}

# Additional sensors discovered from 0xA0 scanning (to be mapped)
# These are placeholder entries for parameters you find through scanning
A0_SENSORS = {
    0x01: SensorDef("Unknown Param 0x01", "P01", 0x11, 0x01, SensorType.RAW, "raw"),
    0x03: SensorDef("Unknown Param 0x03", "P03", 0x11, 0x01, SensorType.RAW, "raw"),
}


def hexdump(data: bytes) -> str:
    """Format bytes as hex string."""
    return ' '.join(f'{b:02X}' for b in data)


def calc_checksum(data: List[int]) -> int:
    """Calculate CONSULT-II checksum."""
    return sum(data) & 0xFF


class Consult2SensorReader:
    """
    Complete CONSULT-II sensor reader.
    
    Supports:
    - Service 0xA0: Direct parameter reads (single sensor)
    - AC 81 + 0x21: MCU buffered multi-sensor reads (efficient)
    """
    
    def __init__(self, port: str = 'COM5'):
        self.port = port
        self.ser: Optional[serial.Serial] = None
        self.handle = None
        self.connected = False
        self.ecu_id: Optional[str] = None
        self._linux_fd: Optional[int] = None
        
    def _escape_comm(self, func: int) -> bool:
        """Send escape command (Windows only)."""
        if IS_WINDOWS and self.handle:
            return kernel32.EscapeCommFunction(self.handle, func)
        return False
    
    def _set_break_linux(self, on: bool):
        """Set/clear BREAK signal on Linux."""
        if not IS_WINDOWS and self._linux_fd:
            TIOCSBRK = 0x5427
            TIOCCBRK = 0x5428
            fcntl.ioctl(self._linux_fd, TIOCSBRK if on else TIOCCBRK)
    
    def connect(self) -> bool:
        """
        Initialize connection to ECU.
        
        Sequence:
        1. Open serial port at 10400 baud
        2. Send BREAK signal to activate Nisscom MCU
        3. Send KWP2000 StartCommunication
        4. Verify ECU responds with 0xC1
        """
        print(f"[INIT] Opening {self.port} at 10400 baud...")
        
        try:
            self.ser = serial.Serial(
                self.port, 
                baudrate=10400, 
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
        except serial.SerialException as e:
            print(f"[ERROR] Could not open port: {e}")
            return False
        
        if IS_WINDOWS:
            self.handle = self.ser._port_handle
        else:
            self._linux_fd = self.ser.fileno()
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.05)
        
        # BREAK activation sequence
        print("[INIT] Activating Nisscom MCU (BREAK signal)...")
        if IS_WINDOWS:
            self._escape_comm(SETDTR)
            time.sleep(0.025)
            self._escape_comm(SETBREAK)
            time.sleep(0.025)
            self._escape_comm(CLRBREAK)
            time.sleep(0.025)
        else:
            # Linux/Raspberry Pi
            self.ser.dtr = True
            time.sleep(0.025)
            self._set_break_linux(True)
            time.sleep(0.025)
            self._set_break_linux(False)
            time.sleep(0.025)
        
        # Clear any garbage from BREAK
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)
        
        # Send KWP2000 StartCommunication
        init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        print(f"[INIT] TX: {hexdump(init_bytes)}")
        
        for b in init_bytes:
            self.ser.write(bytes([b]))
            time.sleep(0.010)  # 10ms inter-byte delay
        
        # Read response
        time.sleep(0.3)
        response = bytearray()
        for _ in range(10):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        print(f"[INIT] RX: {hexdump(response)}")
        
        # Check for positive response (0xC1 = StartCommunication + 0x40)
        if 0xC1 in response:
            self.connected = True
            print("[INIT] ✓ ECU SESSION ACTIVE")
            # Try to read ECU ID
            self._read_ecu_id()
            return True
        else:
            print("[INIT] ✗ FAILED - No ECU response")
            self.ser.close()
            self.ser = None
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.handle = None
            self._linux_fd = None
            self.connected = False
            print("[DONE] Disconnected")
    
    def _read_ecu_id(self) -> Optional[str]:
        """Read ECU identification using service 0x1A."""
        cmd = bytes([0x02, 0x1A, 0x81, 0x9D])  # Read ECU ID
        self.ser.reset_input_buffer()
        self.ser.write(cmd)
        time.sleep(0.3)
        
        response = bytearray()
        for _ in range(5):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Parse response - look for 0x5A (positive response to 0x1A)
        if len(response) > 4:
            for i, byte in enumerate(response):
                if byte == 0x5A and i > 0:
                    # ID starts after 0x5A, length is in previous byte
                    length = response[i-1] - 1 if i > 0 else 6
                    id_bytes = response[i+1:i+1+length]
                    try:
                        self.ecu_id = ''.join(chr(b) if 32 <= b < 127 else '.' for b in id_bytes)
                        print(f"[INFO] ECU ID: {self.ecu_id}")
                        return self.ecu_id
                    except Exception:
                        pass
        return None
    
    def read_sensor_a0(self, param: int, wait: float = 0.3) -> tuple:
        """
        Read sensor using Service 0xA0 (direct ECU read).
        
        Args:
            param: Parameter ID (0x00-0xFF)
            wait: Response timeout
            
        Returns:
            (status, data_bytes) where status is 'ok', 'pending', 'error', or 'timeout'
        """
        if not self.connected:
            return 'error', b''
        
        # Build frame: [02] [A0] [PARAM] [CHECKSUM]
        frame = bytes([0x02, 0xA0, param, (0x02 + 0xA0 + param) & 0xFF])
        
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()
        
        time.sleep(wait)
        response = bytearray()
        for _ in range(8):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Strip echo
        echo_len = len(frame)
        if len(response) > echo_len:
            data = response[echo_len:]
        else:
            return 'timeout', b''
        
        # Check for NRC 0x78 (response pending)
        if len(data) >= 4 and data[1] == 0x7F and data[3] == 0x78:
            time.sleep(0.8)
            more = bytearray()
            for _ in range(15):
                if self.ser.in_waiting > 0:
                    more.extend(self.ser.read(self.ser.in_waiting))
                time.sleep(0.05)
            data = data + more
        
        # Check for negative response
        if len(data) >= 4 and data[1] == 0x7F:
            err_code = data[3] if len(data) > 3 else 0
            return f'error_0x{err_code:02X}', b''
        
        # Look for positive response (0xE0 = A0 + 0x40)
        for i, byte in enumerate(data):
            if byte == 0xE0:
                # Data follows the 0xE0 byte
                remaining = data[i+1:]
                if remaining:
                    # Last byte is checksum, rest is data
                    return 'ok', bytes(remaining[:-1]) if len(remaining) > 1 else remaining
        
        return 'unknown', bytes(data)
    
    def read_sensors_ac81(self, sensor_ids: List[int]) -> Dict[int, float]:
        """
        Read multiple sensors using AC 81 MCU buffering method.
        
        This is the method NDS II uses for efficient multi-sensor polling.
        
        Args:
            sensor_ids: List of sensor indices from ECM_SENSORS
            
        Returns:
            Dict mapping sensor_id to parsed value
        """
        if not self.connected:
            return {}
        
        # Build AC 81 frame
        ac_frame = [0xAC, 0x81]
        for sid in sensor_ids:
            if sid in ECM_SENSORS:
                ac_frame.extend(ECM_SENSORS[sid].get_ac_entry())
        
        # Add length prefix and checksum
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(calc_checksum(ac_frame))
        
        # Send AC 81 to configure MCU
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.2)
        
        # Read MCU acknowledgment (should contain EC 81)
        ack = bytearray()
        for _ in range(5):
            if self.ser.in_waiting > 0:
                ack.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        if 0xEC not in ack:
            print(f"[WARN] MCU did not acknowledge AC 81: {hexdump(ack)}")
            return {}
        
        # Send 0x21 to read collected data
        read_cmd = bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB])
        self.ser.write(read_cmd)
        time.sleep(0.3)
        
        response = bytearray()
        for _ in range(10):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Parse response - look for 0x61 (positive response to 0x21)
        results = {}
        if 0x61 in response:
            idx = response.index(0x61)
            if idx + 2 < len(response):
                data_start = idx + 2  # Skip 0x61 and record ID
                # Parse data according to sensor order
                offset = data_start
                for sid in sensor_ids:
                    if sid not in ECM_SENSORS:
                        continue
                    sensor = ECM_SENSORS[sid]
                    if sensor.addr0 == 0x11 and offset < len(response) - 1:
                        # 1 byte
                        raw_data = bytes([response[offset]])
                        results[sid] = sensor.parse_data(raw_data)
                        offset += 1
                    elif sensor.addr0 == 0x12 and offset + 1 < len(response) - 1:
                        # 2 bytes
                        raw_data = bytes([response[offset], response[offset + 1]])
                        results[sid] = sensor.parse_data(raw_data)
                        offset += 2
        
        return results
    
    def scan_a0_parameters(self, start: int = 0x00, end: int = 0x40) -> Dict[int, bytes]:
        """
        Scan Service 0xA0 parameters to discover sensors.
        
        WARNING: Be careful! Unknown parameters may trigger actuators.
        Only scan ranges you know are safe.
        """
        print(f"[SCAN] Scanning 0xA0 parameters 0x{start:02X}-0x{end:02X}...")
        print("-" * 55)
        
        found = {}
        for param in range(start, end + 1):
            status, data = self.read_sensor_a0(param, wait=0.25)
            
            if status == 'ok':
                found[param] = data
                print(f"  0x{param:02X}: OK  data={hexdump(data)}  len={len(data)}")
            elif status == 'pending':
                print(f"  0x{param:02X}: PENDING (ECU busy)")
            elif 'error' in status:
                err = status.split('_')[1] if '_' in status else '??'
                # Suppress common errors
                if err not in ('0x12', '0x31'):
                    print(f"  0x{param:02X}: {status}")
            
            time.sleep(0.1)  # Don't flood the ECU
        
        print("-" * 55)
        print(f"[SCAN] Found {len(found)} valid parameters")
        return found
    
    def read_known_sensors_a0(self) -> Dict[int, float]:
        """
        Read all known ECM sensors using Service 0xA0.
        
        This is slower (one request per sensor) but works reliably.
        """
        results = {}
        print("[READ] Reading known sensors via 0xA0...")
        
        # Map sensor index to 0xA0 parameter (you need to determine these)
        # Based on your docs: param 0x01 and 0x03 work
        sensor_param_map = {
            0: 0x01,   # RPM (guessed)
            2: 0x03,   # Coolant temp (guessed)
        }
        
        for sid, param in sensor_param_map.items():
            status, data = self.read_sensor_a0(param)
            if status == 'ok' and sid in ECM_SENSORS:
                value = ECM_SENSORS[sid].parse_data(data)
                results[sid] = value
                sensor = ECM_SENSORS[sid]
                print(f"  {sensor.short_name}: {value:.1f} {sensor.unit}")
            time.sleep(0.1)
        
        return results
    
    def monitor_sensors(self, sensor_ids: List[int], interval: float = 1.0, duration: Optional[float] = None):
        """
        Continuously monitor sensors and print values.
        
        Args:
            sensor_ids: List of sensor indices to monitor
            interval: Seconds between readings
            duration: Total monitoring time (None = infinite)
        """
        print("\n" + "=" * 60)
        print("LIVE SENSOR MONITOR")
        print("=" * 60)
        print(f"Monitoring: {[ECM_SENSORS[sid].short_name for sid in sensor_ids if sid in ECM_SENSORS]}")
        print(f"Interval: {interval}s")
        print("Press Ctrl+C to stop\n")
        
        start_time = time.time()
        try:
            while True:
                # Read sensors using AC 81 method
                values = self.read_sensors_ac81(sensor_ids)
                
                # Format output
                timestamp = time.strftime("%H:%M:%S")
                line = f"[{timestamp}]"
                for sid in sensor_ids:
                    if sid in values:
                        sensor = ECM_SENSORS[sid]
                        line += f" {sensor.short_name}={values[sid]:.1f}{sensor.unit}"
                print(line)
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[STOP] Monitoring stopped by user")


def demo():
    """Demonstration of sensor reading capabilities."""
    print("=" * 60)
    print("CONSULT-II SENSOR READER DEMO")
    print("=" * 60)
    print()
    
    reader = Consult2SensorReader('COM5')
    
    try:
        # Connect to ECU
        if not reader.connect():
            print("\nConnection failed. Check:")
            print("  1. Ignition is ON (engine can be off)")
            print("  2. Nisscom USB is connected")
            print("  3. COM port is correct")
            return
        
        print()
        
        # Option 1: Safe parameter discovery
        print("Option 1: Scan known-safe parameters")
        print("-" * 40)
        known_safe = reader.scan_a0_parameters(0x00, 0x05)
        
        # Try to identify what each parameter is
        print("\n[ANALYSIS] Testing discovered parameters...")
        for param, data in known_safe.items():
            print(f"\n  Param 0x{param:02X}:")
            print(f"    Raw data: {hexdump(data)}")
            print(f"    Length: {len(data)} bytes")
            if len(data) == 1:
                v = data[0]
                print(f"    Interpretations:")
                print(f"      Raw: {v}")
                print(f"      Temp: {v-50}°C")
                print(f"      Voltage: {v*0.08:.2f}V")
            elif len(data) >= 2:
                v16 = (data[0] << 8) | data[1]
                print(f"    Interpretations:")
                print(f"      Raw16: {v16}")
                print(f"      RPM: {v16*12.5:.0f}")
                print(f"      Voltage: {v16*0.005:.3f}V")
        
        print()
        
        # Option 2: Try AC 81 multi-sensor read
        print("Option 2: Multi-sensor read (AC 81 method)")
        print("-" * 40)
        
        # Try reading RPM and Coolant together
        test_sensors = [0, 2]  # RPM and Coolant
        results = reader.read_sensors_ac81(test_sensors)
        
        if results:
            print("AC 81 Results:")
            for sid, value in results.items():
                sensor = ECM_SENSORS[sid]
                print(f"  {sensor.name}: {value:.1f} {sensor.unit}")
        else:
            print("AC 81 method returned no data (may not be supported by your ECU)")
        
        print()
        
        # Option 3: Live monitoring
        print("Option 3: Live monitoring (10 seconds)")
        print("-" * 40)
        monitor_sensors = [0, 2] if results else list(known_safe.keys())[:2]
        if monitor_sensors:
            reader.monitor_sensors(monitor_sensors, interval=0.5, duration=10.0)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reader.disconnect()


if __name__ == "__main__":
    demo()
