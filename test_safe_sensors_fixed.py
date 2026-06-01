#!/usr/bin/env python3
"""
NISSCOM SAFE SENSOR TEST - Fixed Version
=========================================

Uses proper BREAK signal activation and CONSULT-II protocol.
Run this after reconnecting the car with engine ON.
"""
import serial
import time
import ctypes
from ctypes import wintypes

# Windows API for BREAK signal
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5

def checksum(data):
    return sum(data) & 0xFF

class NisscomSafeSensors:
    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.handle = None
        self.connected = False

    def _send_break(self):
        """Send BREAK signal via Windows API"""
        kernel32.EscapeCommFunction(self.handle, SETDTR)
        time.sleep(0.025)
        kernel32.EscapeCommFunction(self.handle, SETBREAK)
        time.sleep(0.025)
        kernel32.EscapeCommFunction(self.handle, CLRBREAK)
        time.sleep(0.025)

    def connect(self):
        """Initialize connection to ECU"""
        print(f"\n[INIT] Connecting to ECU via {self.port}...")
        
        self.ser = serial.Serial(self.port, 10400, timeout=1)
        self.handle = self.ser._port_handle
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.05)
        
        # Send BREAK signal (KEY STEP!)
        self._send_break()
        
        # Clear any garbage
        if self.ser.in_waiting:
            self.ser.read(self.ser.in_waiting)
        
        # Send CONSULT-II init sequence
        init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
        for b in init_bytes:
            self.ser.write(bytes([b]))
            time.sleep(0.01)
        
        # Wait for response (important: longer wait + loop!)
        time.sleep(0.3)
        response = []
        for _ in range(5):
            if self.ser.in_waiting:
                response.extend(list(self.ser.read(self.ser.in_waiting)))
            time.sleep(0.05)
        
        if response:
            print(f"[RX] {' '.join(f'{b:02X}' for b in response)}")
            if 0x83 in response or 0xC1 in response:
                print("[OK] ECU connected!")
                self.connected = True
                return True
            elif response == init_bytes:
                print("[WARN] Echo only - ECU not responding")
                return False
            else:
                print(f"[WARN] Unexpected response")
                return False
        else:
            print("[ERROR] No response from ECU")
            return False

    def read_ecu_id(self):
        """Read ECU identification"""
        print("\n[TEST] Reading ECU ID...")
        
        cmd = [0x02, 0x1A, 0x81, 0x00]  # Will calculate checksum
        cmd[3] = checksum(cmd[:3])
        
        for b in cmd:
            self.ser.write(bytes([b]))
            time.sleep(0.01)
        
        time.sleep(0.3)
        response = []
        for _ in range(5):
            if self.ser.in_waiting:
                response.extend(list(self.ser.read(self.ser.in_waiting)))
            time.sleep(0.05)
        
        if response:
            print(f"[RX] {' '.join(f'{b:02X}' for b in response)}")
            # Look for positive response 0x5A
            if 0x5A in response:
                # ECU ID starts after 5A
                try:
                    idx = response.index(0x5A)
                    if idx + 1 < len(response):
                        ecu_id = ''.join(chr(b) for b in response[idx+1:] if 32 <= b < 127)
                        print(f"[OK] ECU ID: {ecu_id}")
                        return True
                except:
                    pass
        
        print("[WARN] Could not read ECU ID")
        return False

    def read_sensor_22(self, reg, addr):
        """Read sensor using service 0x22"""
        # Build command: length, service, reg, addr, unknown, unknown, checksum
        cmd = [0x05, 0x22, reg, addr, 0x04, 0x01, 0x00]
        cmd[6] = checksum(cmd[:6])
        
        self.ser.reset_input_buffer()
        for b in cmd:
            self.ser.write(bytes([b]))
            time.sleep(0.01)
        
        time.sleep(0.3)
        response = []
        for _ in range(5):
            if self.ser.in_waiting:
                response.extend(list(self.ser.read(self.ser.in_waiting)))
            time.sleep(0.05)
        
        # Parse response looking for 0x62 (positive response)
        if 0x62 in response:
            try:
                idx = response.index(0x62)
                if idx + 3 < len(response):
                    if response[idx+1] == reg and response[idx+2] == addr:
                        return response[idx+3]
            except:
                pass
        return None

    def read_all_sensors(self):
        """Read all available sensors"""
        print("\n" + "="*60)
        print("READING SENSORS")
        print("="*60)
        
        results = {}
        
        # Coolant Temperature
        val = self.read_sensor_22(0x11, 0x01)
        if val is not None:
            temp_c = val - 50
            temp_f = int(temp_c * 9 / 5 + 32)
            results['COOLANT'] = f"{temp_c}C ({temp_f}F)"
            print(f"  COOLANT:    {temp_c}C ({temp_f}F)  [raw=0x{val:02X}]")
        else:
            print("  COOLANT:    No data")
        
        # RPM
        val = self.read_sensor_22(0x12, 0x01)
        if val is not None:
            rpm = int(val * 12.5)
            results['RPM'] = rpm
            print(f"  RPM:        {rpm}  [raw=0x{val:02X}]")
        else:
            print("  RPM:        No data")
        
        # AFM Voltage
        val = self.read_sensor_22(0x12, 0x04)
        if val is not None:
            voltage = val * 0.005
            results['AFM_V'] = f"{voltage:.2f}V"
            print(f"  AFM_V:      {voltage:.2f}V  [raw=0x{val:02X}]")
        else:
            print("  AFM_V:      No data")
        
        # Speed
        val = self.read_sensor_22(0x12, 0x1A)
        if val is not None:
            kph = val
            mph = int(kph * 0.621)
            results['SPEED'] = f"{kph}kph ({mph}mph)"
            print(f"  SPEED:      {kph}kph ({mph}mph)  [raw=0x{val:02X}]")
        else:
            print("  SPEED:      No data")
        
        # Throttle Position
        val = self.read_sensor_22(0x11, 0x5F)
        if val is not None:
            percent = int(val * 100 / 255)
            results['TPS'] = f"{percent}%"
            print(f"  TPS:        {percent}%  [raw=0x{val:02X}]")
        else:
            print("  TPS:        No data")
        
        return results

    def disconnect(self):
        """Close connection"""
        if self.ser:
            self.ser.close()
            print("\n[EXIT] Disconnected")


def main():
    print("="*60)
    print("NISSCOM SAFE SENSOR TEST - Fixed Initialization")
    print("="*60)
    print("\n*** IMPORTANT: Engine must be ON and running!")
    input("\nPress ENTER to start...")
    
    port = input("\nEnter COM port (default COM5): ").strip()
    if not port:
        port = 'COM5'
    
    adapter = NisscomSafeSensors(port)
    
    try:
        # Connect to ECU
        if adapter.connect():
            # Read ECU ID
            adapter.read_ecu_id()
            
            # Read sensors
            results = adapter.read_all_sensors()
            
            print("\n" + "="*60)
            if results:
                print("SUCCESS! Sensors reading:")
                for name, value in results.items():
                    print(f"  {name}: {value}")
            else:
                print("WARNING: No sensor data received")
                print("Try:")
                print("  - Reconnecting the OBD2 cable")
                print("  - Waiting 10 seconds after ignition ON")
                print("  - Checking if the engine is running")
            print("="*60)
        else:
            print("\n[ERROR] Could not connect to ECU")
            print("\nTroubleshooting:")
            print("  1. Is the ignition ON? (not just ACC)")
            print("  2. Is the engine running?")
            print("  3. Is the OBD2 cable firmly connected?")
            print("  4. Try unplugging and reconnecting the USB cable")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        adapter.disconnect()
    
    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
