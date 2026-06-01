"""
NISSCOM Multi-Baudrate Sensor Test
===================================

This uses the same multi-baudrate sequence as the original test,
but with corrected AC 81 handling and proper acknowledgment checking.
"""

import serial
import time
import sys


def hexdump(data):
    return ' '.join(f'{b:02X}' for b in data)


def checksum(data):
    return sum(data) & 0xFF


class MultiBaudReader:
    """Reader using multi-baudrate initialization sequence."""
    
    SAFE_SENSORS = [
        ("RPM", 0x12, 0x01, "rpm", lambda d: d * 12.5),
        ("AFM_V", 0x12, 0x04, "V", lambda d: d * 0.005),
        ("COOLANT", 0x11, 0x01, "C", lambda d: d - 50),
        ("STFT", 0x11, 0x5F, "%", lambda d: d if d < 128 else d - 256),
        ("LTFT", 0x11, 0x61, "%", lambda d: d if d < 128 else d - 256),
        ("SPEED", 0x12, 0x1A, "kph", lambda d: d),
    ]
    
    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
    
    def init_sequence(self):
        """Perform multi-baudrate initialization."""
        print("\n[INIT] Multi-baudrate sequence...")
        
        baud_rates = [300, 1200, 9600, 10400]
        
        for baud in baud_rates:
            print(f"  → {baud} baud")
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                
                self.ser = serial.Serial(
                    self.port, baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5
                )
                
                # Send 0x00 at each baud rate (wake-up pattern)
                self.ser.write(bytes([0x00]))
                time.sleep(0.05)
                
                if self.ser.in_waiting:
                    self.ser.read(self.ser.in_waiting)
                
            except Exception as e:
                print(f"     Error: {e}")
                continue
        
        # Now at 10400 baud, send proper KWP2000 init
        print("  → 10400 baud (K-line init)")
        
        init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        
        for b in init_bytes:
            self.ser.write(bytes([b]))
            time.sleep(0.01)
        
        time.sleep(0.3)
        resp = self.ser.read(self.ser.in_waiting)
        print(f"     RX: {hexdump(resp)}")
        
        # Check if ECU responded properly (0xC1 = positive response)
        ecu_responded = 0xC1 in resp or 0x83 in resp
        
        # Switch to 38400 baud for data mode
        print("  → 38400 baud (data mode)")
        self.ser.close()
        self.ser = serial.Serial(
            self.port, 38400,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
        time.sleep(0.1)
        
        if ecu_responded:
            print("  ✓ ECU session established")
            return True
        else:
            print("  ⚠ No ECU response (trying anyway)")
            return True  # Continue anyway
    
    def test_ac81(self):
        """Test AC 81 command at 38400 baud."""
        print("\n[TEST] Testing AC 81 command...")
        
        # Build AC 81 frame for 4 sensors
        ac_frame = [0xAC, 0x81]
        for name, reg, addr, unit, parser in self.SAFE_SENSORS[:4]:
            ac_frame.extend([0x02, reg, addr])
        
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(checksum(ac_frame))
        
        print(f"[TX] AC 81: {hexdump(ac_frame)}")
        
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.3)
        
        resp = self.ser.read(self.ser.in_waiting)
        print(f"[RX] Data: {hexdump(resp)} ({len(resp)} bytes)")
        
        # Analyze response
        if resp == bytes(ac_frame):
            print("  ⚠ ECHO - MCU did not process command")
            return False
        
        if 0xEC in resp:
            print("  ✓ MCU acknowledged AC 81")
            return True
        
        if len(resp) > 0 and resp != bytes(ac_frame):
            print("  ? Got different response (may need different parsing)")
            return True
        
        print("  ✗ No valid response")
        return False
    
    def read_with_ac81(self):
        """Read sensors using AC 81 + 0x21."""
        # Build AC 81 frame
        ac_frame = [0xAC, 0x81]
        sensors = self.SAFE_SENSORS[:4]
        for name, reg, addr, unit, parser in sensors:
            ac_frame.extend([0x02, reg, addr])
        
        length = len(ac_frame)
        ac_frame.insert(0, length)
        ac_frame.append(checksum(ac_frame))
        
        # Send AC 81
        self.ser.reset_input_buffer()
        self.ser.write(bytes(ac_frame))
        time.sleep(0.2)
        
        ack = self.ser.read(self.ser.in_waiting)
        if 0xEC not in ack:
            return {}
        
        # Send 0x21 to read
        read_cmd = bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB])
        self.ser.write(read_cmd)
        time.sleep(0.3)
        
        resp = self.ser.read(self.ser.in_waiting)
        
        # Parse
        results = {}
        if 0x61 in resp:
            idx = resp.index(0x61)
            if idx + 2 < len(resp):
                offset = idx + 2
                for name, reg, addr, unit, parser in sensors:
                    if reg == 0x11 and offset < len(resp):
                        raw = resp[offset]
                        results[name] = (parser(raw), unit)
                        offset += 1
                    elif reg == 0x12 and offset + 1 < len(resp):
                        raw = (resp[offset] << 8) | resp[offset + 1]
                        results[name] = (parser(raw), unit)
                        offset += 2
        
        return results
    
    def read_with_22(self):
        """Read sensors using direct service 0x22."""
        results = {}
        
        for name, reg, addr, unit, parser in self.SAFE_SENSORS[:4]:
            cmd = [0x05, 0x22, reg, addr, 0x04, 0x01]
            cmd.append(checksum(cmd))
            
            self.ser.reset_input_buffer()
            self.ser.write(bytes(cmd))
            time.sleep(0.25)
            
            resp = self.ser.read(self.ser.in_waiting)
            
            # Look for 0x62 = positive response
            if 0x62 in resp:
                idx = resp.index(0x62)
                if idx + 4 < len(resp):
                    if reg == 0x11:
                        raw = resp[idx + 3]
                    else:
                        raw = (resp[idx + 3] << 8) | resp[idx + 4]
                    results[name] = (parser(raw), unit)
        
        return results
    
    def run(self):
        """Main test."""
        print("=" * 60)
        print("NISSCOM MULTI-BAUDRATE SENSOR TEST")
        print("=" * 60)
        print("\n[!] IMPORTANT: Ignition must be ON")
        
        port = input(f"\nEnter COM port (default {self.port}): ").strip()
        if port:
            self.port = port
        
        # Step 1: Multi-baudrate init
        if not self.init_sequence():
            print("[ERROR] Initialization failed")
            return 1
        
        # Step 2: Test AC 81
        ac81_works = self.test_ac81()
        
        # Step 3: Read sensors
        print("\n" + "=" * 60)
        print("READING SENSORS")
        print("=" * 60)
        
        if ac81_works:
            print("[Using AC 81 + 0x21 method]")
            results = self.read_with_ac81()
        else:
            print("[Using direct service 0x22 method]")
            results = self.read_with_22()
        
        if results:
            print("\n[RESULTS]")
            print("-" * 40)
            for name, (value, unit) in results.items():
                print(f"  {name:12} {value:8.1f} {unit}")
            print("-" * 40)
            print(f"\n✓ Read {len(results)} sensors!")
            
            # Live monitoring
            print("\nMonitor? (y/n): ", end="")
            if input().strip().lower() == 'y':
                print("\n[Ctrl+C to stop]\n")
                try:
                    while True:
                        ts = time.strftime("%H:%M:%S")
                        if ac81_works:
                            results = self.read_with_ac81()
                        else:
                            results = self.read_with_22()
                        line = f"[{ts}]"
                        for name, (value, unit) in list(results.items())[:2]:
                            line += f" {name}:{value:.0f}"
                        print(line)
                        time.sleep(1.0)
                except KeyboardInterrupt:
                    print("\n[STOP]")
        else:
            print("\n[ERROR] No data received")
            print("\nTroubleshooting:")
            print("  1. Start engine and retry")
            print("  2. Check OBD connection")
            print("  3. Some Nisscom devices require vendor software")
        
        self.ser.close()
        print("\n[EXIT] Disconnected")
        return 0


def main():
    reader = MultiBaudReader()
    try:
        return reader.run()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
