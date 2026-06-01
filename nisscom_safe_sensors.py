"""
Nisscom SAFE Sensor Reader - AC 81 + 0x21 Method
================================================

⚠️  SAFETY FIRST - READ-ONLY KNOWN SENSORS ONLY  ⚠️

This implementation uses ONLY the 7 verified read-only sensor addresses
from the decompiled NDS II code. These are the SAME addresses NDS II uses
to display sensor data - they are confirmed safe.

Why AC 81 + 0x21 is SAFER than direct 0xA0:
--------------------------------------------
✓ MCU acts as safety buffer - no direct ECU parameter access
✓ Uses known read-only sensor addresses (not mystery parameter IDs)
✓ No risk of triggering actuators (caused engine shutdown with 0xA0)
✓ No P0605 DTC risk (internal control module fault)
✓ Official Nisscom/NDS II communication path

The 7 Safe Sensors (from decompiled frmMain::method_82()):
----------------------------------------------------------
ID  Sensor              ADDR0   ADDR1   Type        Scaling
--- ------------------  ------  ------  ----------  ------------------
0   Engine RPM          0x12    0x01    2-byte      (HI*256+LO)*12.5
1   Air Flow Voltage    0x12    0x04    2-byte      (HI*256+LO)*0.005
2   Coolant Temp        0x11    0x01    1-byte      byte-50 (°C)
3   Short Fuel Trim     0x11    0x5F    1-byte      raw %
4   Long Fuel Trim      0x11    0x61    1-byte      raw %
5   Speed (MPH)         0x11    0x02    1-byte      byte*1.24274
6   Vehicle Speed (KPH) 0x12    0x1A    2-byte      HI*256+LO

⚠️  NEVER use 0xA0 direct with unknown parameter IDs!
    Parameters 0x04-0x20 triggered actuator commands that:
    - Shut down the engine
    - Generated P0605 (Internal Control Module Fault) DTC

Usage:
------
1. Connect Nisscom USB to computer
2. Connect Nisscom to car OBD port
3. Turn ignition ON (engine can be off for safety)
4. Run: python nisscom_safe_sensors.py

Author: PREDICT AI System
Date: 2026-01-30
"""

import serial
import time
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class SensorType(Enum):
    """Sensor data types for proper parsing."""
    RPM = "rpm"
    VOLTAGE = "voltage"
    TEMP_C = "temp_c"
    PERCENT = "percent"
    SPEED_MPH = "speed_mph"
    SPEED_KPH = "speed_kph"


@dataclass
class SafeSensor:
    """
    SAFE sensor definition - ONLY from decompiled NDS II code.
    These addresses are confirmed read-only by NDS II usage.
    """
    id: int
    name: str
    short_name: str
    addr0: int  # 0x11 = 1-byte sensor, 0x12 = 2-byte sensor
    addr1: int  # Parameter address within register
    sensor_type: SensorType
    unit: str
    min_val: float
    max_val: float
    
    def get_ac_entry(self) -> List[int]:
        """Get AC 81 frame entry: [0x02, ADDR0, ADDR1]"""
        return [0x02, self.addr0, self.addr1]
    
    def parse(self, data: bytes) -> Optional[float]:
        """Parse raw bytes to human-readable value."""
        if not data:
            return None
        
        if self.addr0 == 0x11 and len(data) >= 1:
            # 1-byte sensor
            raw = data[0]
            if self.sensor_type == SensorType.TEMP_C:
                return raw - 50.0
            elif self.sensor_type == SensorType.PERCENT:
                # Fuel trim: signed byte
                return raw if raw < 128 else raw - 256
            elif self.sensor_type == SensorType.SPEED_MPH:
                return raw * 1.24274
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
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# THE 7 SAFE SENSORS - From decompiled NDS II (frmMain::method_82)
# These are the ONLY addresses this implementation will use
# ═══════════════════════════════════════════════════════════════════════════════
SAFE_SENSORS: Dict[int, SafeSensor] = {
    0: SafeSensor(0, "Engine RPM", "RPM", 
                  0x12, 0x01, SensorType.RPM, "rpm", 0, 8000),
    1: SafeSensor(1, "Air Flow Meter Voltage", "AFM", 
                  0x12, 0x04, SensorType.VOLTAGE, "V", 0, 5.0),
    2: SafeSensor(2, "Coolant Temperature", "COOLANT", 
                  0x11, 0x01, SensorType.TEMP_C, "°C", -40, 150),
    3: SafeSensor(3, "Short Term Fuel Trim", "STFT", 
                  0x11, 0x5F, SensorType.PERCENT, "%", -25, 25),
    4: SafeSensor(4, "Long Term Fuel Trim", "LTFT", 
                  0x11, 0x61, SensorType.PERCENT, "%", -25, 25),
    5: SafeSensor(5, "Vehicle Speed (MPH)", "SPEED_MPH", 
                  0x11, 0x02, SensorType.SPEED_MPH, "mph", 0, 200),
    6: SafeSensor(6, "Vehicle Speed (KPH)", "SPEED_KPH", 
                  0x12, 0x1A, SensorType.SPEED_KPH, "kph", 0, 255),
}


def hexdump(data: bytes) -> str:
    """Format bytes as hex string."""
    return ' '.join(f'{b:02X}' for b in data)


def calc_checksum(data: List[int]) -> int:
    """Calculate CONSULT-II checksum (sum of all bytes & 0xFF)."""
    return sum(data) & 0xFF


class NisscomSafeReader:
    """
    SAFE Nisscom sensor reader using AC 81 + 0x21 method.
    
    This class ONLY uses the 7 verified safe sensor addresses.
    No other addresses or parameter IDs will be accessed.
    """
    
    def __init__(self, port: str = 'COM5'):
        self.port = port
        self.ser: Optional[serial.Serial] = None
        self.connected = False
        self.ecu_id: Optional[str] = None
    
    def connect(self) -> bool:
        """
        Initialize connection to ECU using safe initialization.
        
        Sequence:
        1. Open serial at 10400 baud (standard K-line)
        2. Send KWP2000 StartCommunication
        3. Verify ECU responds with 0xC1
        """
        print(f"\n[CONNECT] Opening {self.port} at 10400 baud...")
        
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
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.05)
        
        # KWP2000 StartCommunication (safe standard sequence)
        init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        print(f"[INIT] TX: {hexdump(init_bytes)}")
        
        for b in init_bytes:
            self.ser.write(bytes([b]))
            time.sleep(0.010)
        
        # Read response
        time.sleep(0.3)
        response = bytearray()
        for _ in range(10):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        print(f"[INIT] RX: {hexdump(response)}")
        
        # Check for positive response (0xC1)
        if 0xC1 in response:
            self.connected = True
            print("[INIT] ✓ ECU SESSION ACTIVE")
            self._read_ecu_id()
            return True
        else:
            print("[INIT] ✗ FAILED - No ECU response")
            print("\n[TROUBLESHOOTING]")
            print("  1. Is ignition ON? (Engine can be off)")
            print("  2. Is Nisscom connected to OBD port?")
            print("  3. Is COM port correct? (Check Device Manager)")
            self.ser.close()
            self.ser = None
            return False
    
    def _read_ecu_id(self) -> Optional[str]:
        """Read ECU identification using service 0x1A (safe read-only)."""
        cmd = bytes([0x02, 0x1A, 0x81, 0x9D])
        self.ser.reset_input_buffer()
        self.ser.write(cmd)
        time.sleep(0.3)
        
        response = bytearray()
        for _ in range(5):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Parse ECU ID from response
        if len(response) > 4:
            for i, byte in enumerate(response):
                if byte == 0x5A and i > 0:
                    length = response[i-1] - 1 if i > 0 else 6
                    id_bytes = response[i+1:i+1+length]
                    try:
                        self.ecu_id = ''.join(chr(b) if 32 <= b < 127 else '.' for b in id_bytes)
                        print(f"[INFO] ECU ID: {self.ecu_id}")
                        return self.ecu_id
                    except Exception:
                        pass
        return None
    
    def read_safe_sensors(self, sensor_ids: List[int]) -> Dict[int, float]:
        """
        Read sensors using SAFE AC 81 + 0x21 method.
        
        This method:
        1. Sends AC 81 with ONLY known safe sensor addresses
        2. MCU collects data from those addresses
        3. Sends 0x21 to read the buffered data
        4. Parses response using NDS II scaling formulas
        
        Args:
            sensor_ids: List of sensor IDs (0-6) from SAFE_SENSORS
        
        Returns:
            Dict mapping sensor_id to parsed value
        """
        if not self.connected:
            print("[ERROR] Not connected to ECU")
            return {}
        
        # Validate all sensor IDs are safe
        for sid in sensor_ids:
            if sid not in SAFE_SENSORS:
                print(f"[ERROR] Sensor ID {sid} is NOT in safe list!")
                print("[ERROR] This implementation only uses IDs 0-6")
                return {}
        
        # Build AC 81 frame
        ac_frame = [0xAC, 0x81]
        for sid in sensor_ids:
            ac_frame.extend(SAFE_SENSORS[sid].get_ac_entry())
        
        # Add length prefix and checksum
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(calc_checksum(ac_frame))
        
        # Send AC 81 to configure MCU
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.2)
        
        # Read MCU acknowledgment
        ack = bytearray()
        for _ in range(5):
            if self.ser.in_waiting > 0:
                ack.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        if 0xEC not in ack:
            print(f"[WARN] MCU did not acknowledge: {hexdump(ack)}")
            return {}
        
        # Send 0x21 to read buffered data
        read_cmd = bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB])
        self.ser.write(read_cmd)
        time.sleep(0.3)
        
        # Read response
        response = bytearray()
        for _ in range(10):
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
            time.sleep(0.05)
        
        # Parse response (look for 0x61 = positive response to 0x21)
        results = {}
        if 0x61 in response:
            idx = response.index(0x61)
            if idx + 2 < len(response):
                data_start = idx + 2  # Skip 0x61 and record ID
                offset = data_start
                
                for sid in sensor_ids:
                    if sid not in SAFE_SENSORS:
                        continue
                    
                    sensor = SAFE_SENSORS[sid]
                    
                    if sensor.addr0 == 0x11 and offset < len(response) - 1:
                        # 1-byte sensor
                        raw_data = bytes([response[offset]])
                        value = sensor.parse(raw_data)
                        if value is not None:
                            results[sid] = value
                        offset += 1
                    
                    elif sensor.addr0 == 0x12 and offset + 1 < len(response) - 1:
                        # 2-byte sensor
                        raw_data = bytes([response[offset], response[offset + 1]])
                        value = sensor.parse(raw_data)
                        if value is not None:
                            results[sid] = value
                        offset += 2
        
        return results
    
    def monitor_sensors(self, sensor_ids: List[int], interval: float = 1.0):
        """
        Continuously monitor safe sensors.
        
        Args:
            sensor_ids: List of safe sensor IDs to monitor
            interval: Seconds between readings
        """
        print("\n" + "="*70)
        print("SAFE SENSOR MONITOR - AC 81 + 0x21 Method")
        print("="*70)
        print("Reading ONLY these verified safe sensors:")
        for sid in sensor_ids:
            s = SAFE_SENSORS[sid]
            print(f"  [{sid}] {s.name} (0x{s.addr0:02X} 0x{s.addr1:02X})")
        print(f"\nUpdate interval: {interval}s")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                timestamp = time.strftime("%H:%M:%S")
                values = self.read_safe_sensors(sensor_ids)
                
                if values:
                    line = f"[{timestamp}]"
                    for sid in sensor_ids:
                        if sid in values:
                            s = SAFE_SENSORS[sid]
                            line += f" | {s.short_name}:{values[sid]:.1f}{s.unit}"
                    print(line)
                else:
                    print(f"[{timestamp}] (no data)")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[STOP] Monitoring stopped")
    
    def read_all_safe_sensors(self) -> Dict[int, float]:
        """Read all 7 safe sensors at once."""
        return self.read_safe_sensors(list(SAFE_SENSORS.keys()))
    
    def disconnect(self):
        """Close connection."""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.connected = False


def print_safety_info():
    """Print safety information."""
    print("="*70)
    print("NISSCOM SAFE SENSOR READER")
    print("="*70)
    print("\n✓ SAFETY FEATURES:")
    print("  • Uses ONLY 7 verified read-only sensor addresses")
    print("  • AC 81 + 0x21 method (MCU buffered)")
    print("  • No direct 0xA0 parameter access")
    print("  • No risk of triggering actuators")
    print("  • Same addresses used by NDS II software")
    
    print("\n⚠️  WHY THIS IS SAFER THAN 0xA0 DIRECT:")
    print("  ┌─────────────────────┬──────────────────┬──────────────────┐")
    print("  │ Aspect              │ Direct 0xA0      │ AC 81 + 0x21     │")
    print("  ├─────────────────────┼──────────────────┼──────────────────┤")
    print("  │ Known Risk          │ Engine shutdown  │ ✅ No risks     │")
    print("  │ DTC Triggered       │ P0605 (serious)  │ ✅ None         │")
    print("  │ Actuator Risk       │ HIGH (unknown)   │ ✅ LOW (known)  │")
    print("  │ Data Source         │ Raw parameter IDs│ Decompiled addrs│")
    print("  │ Safety Buffer       │ None             │ ✅ MCU buffered │")
    print("  └─────────────────────┴──────────────────┴──────────────────┘")
    
    print("\n📋 THE 7 SAFE SENSORS:")
    print("  ┌────┬──────────────────────┬────────┬────────┬──────────┐")
    print("  │ ID │ Name                 │ ADDR0  │ ADDR1  │ Type     │")
    print("  ├────┼──────────────────────┼────────┼────────┼──────────┤")
    for sid, s in SAFE_SENSORS.items():
        safe_mark = "✓"
        print(f"  │ {sid}  │ {s.name[:20]:<20} │ 0x{s.addr0:02X}   │ 0x{s.addr1:02X}   │ {s.sensor_type.value:<8} │")
    print("  └────┴──────────────────────┴────────┴────────┴──────────┘")
    
    print("\n🚗 BEFORE YOU START:")
    print("  1. Connect Nisscom USB to your computer")
    print("  2. Connect Nisscom to car OBD port")
    print("  3. Turn ignition ON (engine can be OFF for safety)")
    print("  4. Verify COM port in Device Manager")


def main():
    """Main program."""
    print_safety_info()
    
    # Get COM port
    port = input("\n[?] Enter COM port (default: COM5): ").strip()
    if not port:
        port = "COM5"
    
    reader = NisscomSafeReader(port)
    
    try:
        # Connect
        if not reader.connect():
            print("\n[EXIT] Connection failed")
            return 1
        
        # Menu
        while True:
            print("\n" + "="*70)
            print("MENU")
            print("="*70)
            print("  1. Read all 7 safe sensors (one-shot)")
            print("  2. Monitor all sensors continuously")
            print("  3. Read specific sensors")
            print("  4. Exit")
            
            choice = input("\n[?] Select option (1-4): ").strip()
            
            if choice == "1":
                print("\n[READ] Reading all safe sensors...")
                results = reader.read_all_safe_sensors()
                
                if results:
                    print("\n" + "-"*50)
                    print("RESULTS:")
                    print("-"*50)
                    for sid, value in sorted(results.items()):
                        s = SAFE_SENSORS[sid]
                        print(f"  {s.name:25} {value:8.1f} {s.unit}")
                    print("-"*50)
                else:
                    print("[WARN] No data received")
            
            elif choice == "2":
                interval = input("[?] Update interval in seconds (default: 1.0): ").strip()
                try:
                    interval = float(interval) if interval else 1.0
                except ValueError:
                    interval = 1.0
                reader.monitor_sensors(list(SAFE_SENSORS.keys()), interval)
            
            elif choice == "3":
                print("\nAvailable sensors:")
                for sid, s in SAFE_SENSORS.items():
                    print(f"  {sid}: {s.name}")
                ids_input = input("\n[?] Enter sensor IDs to read (comma-separated, e.g., 0,2,3): ").strip()
                try:
                    sensor_ids = [int(x.strip()) for x in ids_input.split(",")]
                    results = reader.read_safe_sensors(sensor_ids)
                    
                    if results:
                        print("\nRESULTS:")
                        for sid, value in sorted(results.items()):
                            s = SAFE_SENSORS[sid]
                            print(f"  {s.name}: {value:.1f} {s.unit}")
                    else:
                        print("[WARN] No data received")
                except ValueError:
                    print("[ERROR] Invalid input")
            
            elif choice == "4":
                break
            else:
                print("[ERROR] Invalid choice")
    
    except KeyboardInterrupt:
        print("\n[EXIT] Interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        reader.disconnect()
        print("[EXIT] Disconnected")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
