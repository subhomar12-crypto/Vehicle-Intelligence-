"""
CONSULT-II Sensor Reader v2 - Using Working 0x22 Protocol
===========================================================

Based on nisscom_working_final.py which successfully reads sensors.
Uses Service 0x22 (ReadDataByIdentifier) instead of 0xA0.

Frame format from working code: 05 22 11 [ADDR] 04 01 [CS]
"""

import serial
import time
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

# Windows API constants
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6

try:
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.EscapeCommFunction.restype = wintypes.BOOL
    IS_WINDOWS = True
except Exception:
    IS_WINDOWS = False
    import fcntl


class SensorType(Enum):
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
    """Sensor definition."""
    name: str
    short_name: str
    sensor_addr: int  # The address for 0x22 command
    sensor_type: SensorType
    unit: str
    bytes_expected: int = 1  # 1 or 2 bytes
    scale: float = 1.0
    offset: float = 0.0
    
    def parse(self, data: bytes) -> Optional[float]:
        """Parse raw bytes to value."""
        if len(data) < self.bytes_expected:
            return None
        
        if self.bytes_expected == 1:
            raw = data[0]
        else:
            raw = (data[0] << 8) | data[1]
        
        # Apply scaling
        value = raw * self.scale + self.offset
        return value


# Sensor database from your decompilation
# Address = the XX in: 05 22 11 XX 04 01 CS
SENSOR_DB = {
    # RPM - 2 bytes, scale 12.5
    0x00: SensorDef("Engine RPM", "RPM", 0x00, SensorType.RPM, "rpm", 2, 12.5),
    
    # Coolant temp - 1 byte, offset -50
    0x01: SensorDef("Coolant Temperature", "Coolant", 0x01, SensorType.TEMP_C, "°C", 1, 1.0, -50.0),
    
    # Air Flow Meter - 2 bytes, scale 0.005
    0x04: SensorDef("Air Flow Meter", "AFM", 0x04, SensorType.VOLTAGE, "V", 2, 0.005),
    
    # Vehicle speed - 1 byte, scale 1.24274
    0x02: SensorDef("Vehicle Speed", "Speed", 0x02, SensorType.SPEED_MPH, "mph", 1, 1.24274),
}


def hexdump(data: bytes) -> str:
    return ' '.join(f'{b:02X}' for b in data)


def calc_checksum(data: List[int]) -> int:
    return sum(data) & 0xFF


class Consult2Reader:
    """Working CONSULT-II reader using 0x22 protocol."""
    
    def __init__(self, port: str = 'COM5'):
        self.port = port
        self.ser: Optional[serial.Serial] = None
        self.handle = None
        self.connected = False
        self._linux_fd: Optional[int] = None
    
    def _escape_comm(self, func: int) -> bool:
        if IS_WINDOWS and self.handle:
            return kernel32.EscapeCommFunction(self.handle, func)
        return False
    
    def _set_break_linux(self, on: bool):
        if not IS_WINDOWS and self._linux_fd:
            TIOCSBRK = 0x5427
            TIOCCBRK = 0x5428
            fcntl.ioctl(self._linux_fd, TIOCSBRK if on else TIOCCBRK)
    
    def connect(self) -> bool:
        """Initialize connection with BREAK signal."""
        print(f"[INIT] Opening {self.port}...")
        
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
            print(f"[ERROR] {e}")
            return False
        
        if IS_WINDOWS:
            self.handle = self.ser._port_handle
        else:
            self._linux_fd = self.ser.fileno()
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.05)
        
        # BREAK sequence
        print("[INIT] Sending BREAK signal...")
        if IS_WINDOWS:
            self._escape_comm(SETDTR)
            time.sleep(0.025)
            self._escape_comm(SETBREAK)
            time.sleep(0.025)
            self._escape_comm(CLRBREAK)
            time.sleep(0.025)
        else:
            self.ser.dtr = True
            time.sleep(0.025)
            self._set_break_linux(True)
            time.sleep(0.025)
            self._set_break_linux(False)
            time.sleep(0.025)
        
        # Clear BREAK garbage
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)
        
        # KWP2000 StartCommunication
        init = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        print(f"[INIT] TX: {hexdump(init)}")
        
        for b in init:
            self.ser.write(bytes([b]))
            time.sleep(0.010)
        
        # Read response
        time.sleep(0.3)
        resp = bytearray()
        for _ in range(10):
            if self.ser.in_waiting > 0:
                resp.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        print(f"[INIT] RX: {hexdump(resp)}")
        
        if 0xC1 in resp:
            self.connected = True
            print("[INIT] ✓ Connected to ECU")
            return True
        else:
            print("[INIT] ✗ No response")
            self.ser.close()
            self.ser = None
            return False
    
    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
            self.connected = False
            print("[DONE] Disconnected")
    
    def read_sensor(self, addr: int, wait: float = 0.3) -> Tuple[str, Optional[bytes]]:
        """
        Read sensor using Service 0x22.
        Format: 05 22 11 [ADDR] 04 01 [CS]
        
        Positive response: 62 11 [ADDR] [DATA...] [CS]
        """
        if not self.connected:
            return 'not_connected', None
        
        # Build command
        cmd = [0x05, 0x22, 0x11, addr, 0x04, 0x01]
        cmd.append(calc_checksum(cmd))
        frame = bytes(cmd)
        
        # Clear and send
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()
        
        # Read response
        time.sleep(wait)
        resp = bytearray()
        for _ in range(8):
            if self.ser.in_waiting > 0:
                resp.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Strip echo
        if len(resp) > len(frame):
            data = resp[len(frame):]
        else:
            return 'no_response', None
        
        # Check for positive response (0x62 = 0x22 + 0x40)
        if 0x62 in data:
            idx = data.index(0x62)
            # 62 11 [ADDR] [DATA...]
            if idx + 3 < len(data):
                resp_addr = data[idx + 2]
                if resp_addr == addr:
                    # Data follows address
                    remaining = data[idx + 3:]
                    if remaining:
                        return 'ok', bytes(remaining[:-1])  # Exclude checksum
        
        # Check for negative response
        if 0x7F in data:
            return 'negative', bytes(data)
        
        return 'unknown', bytes(data)
    
    def read_ecu_id(self) -> Optional[str]:
        """Read ECU ID using 0x1A."""
        cmd = bytes([0x02, 0x1A, 0x81, 0x9D])
        self.ser.reset_input_buffer()
        self.ser.write(cmd)
        time.sleep(0.3)
        
        resp = bytearray()
        for _ in range(5):
            if self.ser.in_waiting > 0:
                resp.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        if 0x5A in resp:
            idx = resp.index(0x5A)
            if idx > 0 and idx + 1 < len(resp):
                length = resp[idx - 1] - 1
                id_bytes = resp[idx + 1:idx + 1 + length]
                try:
                    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in id_bytes)
                except:
                    pass
        return None
    
    def scan_sensors(self, start: int = 0x00, end: int = 0x20) -> Dict[int, bytes]:
        """Scan sensor addresses to find what's available."""
        print(f"[SCAN] Scanning addresses 0x{start:02X}-0x{end:02X}...")
        print("-" * 50)
        
        found = {}
        for addr in range(start, end + 1):
            status, data = self.read_sensor(addr, wait=0.25)
            if status == 'ok' and data:
                found[addr] = data
                print(f"  0x{addr:02X}: {len(data)} bytes - {hexdump(data)}")
            time.sleep(0.1)
        
        print("-" * 50)
        print(f"[SCAN] Found {len(found)} sensors")
        return found
    
    def read_known_sensors(self) -> Dict[str, float]:
        """Read all known sensors from database."""
        results = {}
        print("[READ] Reading known sensors...")
        
        for addr, sensor in SENSOR_DB.items():
            status, data = self.read_sensor(addr)
            if status == 'ok' and data:
                value = sensor.parse(data)
                if value is not None:
                    results[sensor.short_name] = value
                    print(f"  {sensor.name}: {value:.1f} {sensor.unit}")
            time.sleep(0.1)
        
        return results
    
    def monitor(self, sensor_addrs: List[int], interval: float = 1.0):
        """Continuously monitor sensors."""
        print("\n" + "=" * 60)
        print("LIVE MONITOR")
        print("=" * 60)
        print(f"Addresses: {[f'0x{a:02X}' for a in sensor_addrs]}")
        print(f"Interval: {interval}s")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                timestamp = time.strftime("%H:%M:%S")
                line = f"[{timestamp}]"
                
                for addr in sensor_addrs:
                    status, data = self.read_sensor(addr, wait=0.2)
                    if status == 'ok' and data:
                        if len(data) == 1:
                            line += f" 0x{addr:02X}={data[0]}"
                        elif len(data) >= 2:
                            val16 = (data[0] << 8) | data[1]
                            line += f" 0x{addr:02X}={val16}"
                
                print(line)
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[STOP] Monitoring stopped")


def quick_test():
    """Quick test function."""
    print("=" * 60)
    print("CONSULT-II READER v2 - QUICK TEST")
    print("=" * 60)
    print()
    
    reader = Consult2Reader('COM5')
    
    try:
        if not reader.connect():
            print("\nConnection failed!")
            return
        
        print()
        
        # Read ECU ID
        ecu_id = reader.read_ecu_id()
        if ecu_id:
            print(f"[INFO] ECU ID: {ecu_id}")
        print()
        
        # Scan for sensors
        sensors = reader.scan_sensors(0x00, 0x10)
        
        if sensors:
            # Monitor found sensors
            print()
            reader.monitor(list(sensors.keys())[:4], interval=0.5)
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reader.disconnect()


if __name__ == "__main__":
    quick_test()
