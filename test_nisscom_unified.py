"""
NISSCOM Unified Sensor Test
============================

Combines:
- Multi-baudrate initialization (if needed)
- Standard KWP2000 initialization at 10400 baud
- AC 81 + 0x21 sensor reading method

This script tries multiple initialization approaches to find what works.
"""

import serial
import time
import sys


def hexdump(data):
    return ' '.join(f'{b:02X}' for b in data)


def checksum(data):
    return sum(data) & 0xFF


class NisscomUnifiedReader:
    """Unified reader that tries multiple init methods."""
    
    SAFE_SENSORS = [
        ("RPM", 0x12, 0x01, "rpm", lambda d: d * 12.5),
        ("AFM_V", 0x12, 0x04, "V", lambda d: d * 0.005),
        ("COOLANT", 0x11, 0x01, "C", lambda d: d - 50),
        ("STFT", 0x11, 0x5F, "%", lambda d: d if d < 128 else d - 256),
        ("LTFT", 0x11, 0x61, "%", lambda d: d if d < 128 else d - 256),
        ("SPEED_MPH", 0x11, 0x02, "mph", lambda d: d * 1.24274),
        ("SPEED_KPH", 0x12, 0x1A, "kph", lambda d: d),
    ]
    
    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.mcu_mode = None  # 'ac81' or 'direct'
    
    def connect_standard(self):
        """Try standard KWP2000 initialization at 10400 baud."""
        print("\n[INIT] Trying standard KWP2000 at 10400 baud...")
        
        try:
            self.ser = serial.Serial(
                self.port, 10400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
        except Exception as e:
            print(f"[ERROR] Could not open port: {e}")
            return False
        
        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.1)
        
        # Send KWP2000 StartCommunication
        init = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        print(f"[INIT] TX: {hexdump(init)}")
        
        for b in init:
            self.ser.write(bytes([b]))
            time.sleep(0.01)
        
        time.sleep(0.3)
        resp = self.ser.read(self.ser.in_waiting)
        print(f"[INIT] RX: {hexdump(resp)}")
        
        if 0xC1 in resp or 0x83 in resp:
            print("[INIT] ✓ ECU responded!")
            return True
        
        print("[INIT] No ECU response")
        return False
    
    def try_ac81_mode(self):
        """Test if MCU responds to AC 81 command."""
        print("\n[TEST] Checking if MCU accepts AC 81 commands...")
        
        # Build AC 81 frame for first 4 sensors
        ac_frame = [0xAC, 0x81]
        for name, reg, addr, unit, parser in self.SAFE_SENSORS[:4]:
            ac_frame.extend([0x02, reg, addr])
        
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(checksum(ac_frame))
        
        print(f"[TEST] TX AC 81: {hexdump(ac_frame)}")
        
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.3)
        
        resp = self.ser.read(self.ser.in_waiting)
        print(f"[TEST] RX: {hexdump(resp)} ({len(resp)} bytes)")
        
        # Check if response is echo or actual MCU response
        if resp == bytes(ac_frame):
            print("[TEST] ⚠ MCU is echoing (transparent mode)")
            return False
        
        if 0xEC in resp:
            print("[TEST] ✓ MCU acknowledged AC 81!")
            self.mcu_mode = 'ac81'
            return True
        
        if len(resp) > len(ac_frame):
            print("[TEST] ✓ Got different response (might be working)")
            return True
        
        print("[TEST] ✗ No MCU acknowledgment")
        return False
    
    def read_sensors_ac81(self, count=4):
        """Read sensors using AC 81 + 0x21 method."""
        # Build AC 81 frame
        ac_frame = [0xAC, 0x81]
        sensors = self.SAFE_SENSORS[:count]
        for name, reg, addr, unit, parser in sensors:
            ac_frame.extend([0x02, reg, addr])
        
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(checksum(ac_frame))
        
        # Send AC 81
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.2)
        
        # Check for MCU ack (0xEC)
        ack = self.ser.read(self.ser.in_waiting)
        if 0xEC not in ack:
            return {}
        
        # Send 0x21 to read data
        read_cmd = bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB])
        self.ser.write(read_cmd)
        time.sleep(0.3)
        
        # Read response
        resp = self.ser.read(self.ser.in_waiting)
        
        # Parse response (look for 0x61 = positive response)
        results = {}
        if 0x61 in resp:
            idx = resp.index(0x61)
            if idx + 2 < len(resp):
                data_start = idx + 2
                offset = data_start
                
                for name, reg, addr, unit, parser in sensors:
                    if reg == 0x11 and offset < len(resp):
                        raw = resp[offset]
                        value = parser(raw)
                        results[name] = (value, unit)
                        offset += 1
                    elif reg == 0x12 and offset + 1 < len(resp):
                        raw = (resp[offset] << 8) | resp[offset + 1]
                        value = parser(raw)
                        results[name] = (value, unit)
                        offset += 2
        
        return results
    
    def read_sensors_direct_22(self):
        """Read sensors using direct service 0x22 requests."""
        results = {}
        
        for name, reg, addr, unit, parser in self.SAFE_SENSORS[:4]:
            cmd = [0x05, 0x22, reg, addr, 0x04, 0x01]
            cmd.append(checksum(cmd))
            
            self.ser.reset_input_buffer()
            self.ser.write(bytes(cmd))
            time.sleep(0.25)
            
            resp = self.ser.read(self.ser.in_waiting)
            
            # Look for 0x62 = positive response to 0x22
            if 0x62 in resp:
                idx = resp.index(0x62)
                if idx + 4 < len(resp):
                    if reg == 0x11:
                        raw = resp[idx + 3]
                        value = parser(raw)
                    else:
                        raw = (resp[idx + 3] << 8) | resp[idx + 4]
                        value = parser(raw)
                    results[name] = (value, unit)
        
        return results
    
    def run(self):
        """Main test sequence."""
        print("=" * 60)
        print("NISSCOM UNIFIED SENSOR TEST")
        print("=" * 60)
        print("\n[!] IMPORTANT: Ignition must be ON")
        print("[!] Engine can be OFF for safety")
        
        port = input(f"\nEnter COM port (default {self.port}): ").strip()
        if port:
            self.port = port
        
        # Step 1: Connect with standard KWP2000
        if not self.connect_standard():
            print("\n[ERROR] Could not connect to ECU")
            print("Check:")
            print("  - Ignition is ON")
            print("  - Nisscom is connected")
            print("  - COM port is correct")
            return 1
        
        # Step 2: Try AC 81 mode
        if self.try_ac81_mode():
            print("\n[MODE] Using AC 81 + 0x21 method")
            read_func = self.read_sensors_ac81
        else:
            print("\n[MODE] Using direct service 0x22 method")
            read_func = self.read_sensors_direct_22
        
        # Step 3: Read sensors
        print("\n" + "=" * 60)
        print("READING SENSORS")
        print("=" * 60)
        
        results = read_func()
        
        if results:
            print("\n[RESULTS]")
            print("-" * 40)
            for name, (value, unit) in results.items():
                print(f"  {name:12} {value:8.1f} {unit}")
            print("-" * 40)
            print(f"\n✓ Successfully read {len(results)} sensors!")
            
            # Live monitoring option
            print("\nLive monitor? (y/n): ", end="")
            if input().strip().lower() == 'y':
                print("\n[Press Ctrl+C to stop]\n")
                try:
                    while True:
                        ts = time.strftime("%H:%M:%S")
                        results = read_func()
                        line = f"[{ts}]"
                        for name, (value, unit) in list(results.items())[:3]:
                            line += f" {name}:{value:.0f}"
                        print(line)
                        time.sleep(1.0)
                except KeyboardInterrupt:
                    print("\n[STOP]")
        else:
            print("\n[ERROR] No sensor data received")
            print("\nTroubleshooting:")
            print("  1. Try starting the engine")
            print("  2. Check OBD connection is secure")
            print("  3. Verify COM port in Device Manager")
            print("  4. Some Nisscom devices need vendor software first")
        
        if self.ser:
            self.ser.close()
        print("\n[EXIT] Disconnected")
        return 0


def main():
    reader = NisscomUnifiedReader()
    try:
        return reader.run()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
