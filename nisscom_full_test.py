"""
Comprehensive Nisscom Device Test
==================================

Tests all discovered protocols and initialization sequences
to find what actually works with the car.
"""

import serial
import time

class NisscomTester:
    """Test different protocol approaches"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None

    def connect(self, baudrate):
        """Connect at specified baudrate"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                self.port,
                baudrate=baudrate,
                timeout=2
            )
            time.sleep(0.5)
            print(f"[OK] Connected at {baudrate} baud")
            return True
        except Exception as e:
            print(f"[ERROR] Failed at {baudrate}: {e}")
            return False

    def send_recv(self, data, label=""):
        """Send data and show response"""
        hex_cmd = ' '.join([f'{b:02X}' for b in data])
        print(f"\n  [{label}]")
        print(f"    SEND: {hex_cmd}")

        self.ser.write(bytes(data))
        self.ser.flush()
        time.sleep(0.3)

        resp = []
        while self.ser.in_waiting > 0:
            resp.append(self.ser.read(1)[0])
            time.sleep(0.01)

        if resp:
            hex_resp = ' '.join([f'{b:02X}' for b in resp])
            print(f"    RECV: {hex_resp}")

            # Check if echo
            if resp == data:
                print(f"    >>> ECHO (device loopback, ECU not responding)")
                return False
            else:
                print(f"    >>> DIFFERENT! (ECU might be responding!)")
                return True
        else:
            print(f"    RECV: (no response)")
            return False

    def test_consult2_init(self):
        """Test standard Consult-II initialization"""
        print("\n" + "=" * 70)
        print("TEST 1: Standard Consult-II Protocol")
        print("=" * 70)

        if not self.connect(9600):
            return

        # Clear buffer
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Try Consult-II init
        result = self.send_recv([0xFF, 0xFF, 0xEF], "Consult-II Init")

        self.ser.close()
        return result

    def test_nisscom_captured_init(self):
        """Test initialization sequence captured from Nisscom software"""
        print("\n" + "=" * 70)
        print("TEST 2: Captured Nisscom Protocol (38400 baud)")
        print("=" * 70)

        if not self.connect(38400):
            return

        # Clear buffer
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Captured initialization sequence
        results = []
        results.append(self.send_recv([0x00], "Sync"))
        time.sleep(0.1)

        results.append(self.send_recv([0x81], "Init cmd"))
        time.sleep(0.1)

        results.append(self.send_recv([0x10, 0xFC, 0x81], "Handshake 1"))
        time.sleep(0.1)

        results.append(self.send_recv([0x0E], "Handshake 2"))
        time.sleep(0.1)

        # Try a read command
        results.append(self.send_recv([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D], "Read Reg 0x11"))

        self.ser.close()
        return any(results)

    def test_hybrid_init(self):
        """Test: Nisscom wrapper at 38400, then Consult-II commands"""
        print("\n" + "=" * 70)
        print("TEST 3: Hybrid - Nisscom init, then Consult-II data")
        print("=" * 70)

        if not self.connect(38400):
            return

        # Nisscom init
        self.send_recv([0x00], "Nisscom Sync")
        time.sleep(0.1)
        self.send_recv([0x81], "Nisscom Init")
        time.sleep(0.1)

        # Now try Consult-II commands embedded
        result = self.send_recv([0xFF, 0xFF, 0xEF], "Consult-II Init (embedded)")

        self.ser.close()
        return result

    def test_simple_probe(self):
        """Send simple probe commands to see if anything responds differently"""
        print("\n" + "=" * 70)
        print("TEST 4: Simple Probe Commands")
        print("=" * 70)

        results = {}

        for baud in [9600, 38400]:
            print(f"\n--- Testing at {baud} baud ---")

            if not self.connect(baud):
                continue

            # Try various single byte commands
            test_bytes = [0x00, 0x01, 0x10, 0x81, 0xFF, 0xF0, 0xD0, 0x5A]

            for b in test_bytes:
                resp_data = []
                self.ser.write(bytes([b]))
                self.ser.flush()
                time.sleep(0.2)

                while self.ser.in_waiting > 0:
                    resp_data.append(self.ser.read(1)[0])

                if resp_data and resp_data != [b]:
                    print(f"  {b:02X} -> {' '.join([f'{r:02X}' for r in resp_data])} *** INTERESTING!")
                    results[f"{baud}_{b:02X}"] = resp_data

            self.ser.close()

        return len(results) > 0


def main():
    print("=" * 70)
    print("NISSCOM COMPREHENSIVE DEVICE TEST")
    print("=" * 70)
    print("\nThis will test multiple protocol approaches to find what works.")
    print("Make sure: Car ignition ON, engine running, device connected.\n")

    tester = NisscomTester(port='COM5')

    # Run all tests
    test1 = tester.test_consult2_init()
    test2 = tester.test_nisscom_captured_init()
    test3 = tester.test_hybrid_init()
    test4 = tester.test_simple_probe()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"  Test 1 (Consult-II @ 9600):      {'PASS' if test1 else 'FAIL'}")
    print(f"  Test 2 (Nisscom @ 38400):        {'PASS' if test2 else 'FAIL'}")
    print(f"  Test 3 (Hybrid):                 {'PASS' if test3 else 'FAIL'}")
    print(f"  Test 4 (Probe):                  {'PASS' if test4 else 'FAIL'}")

    if test1:
        print("\n>>> Standard Consult-II works! Use that protocol.")
    elif test2:
        print("\n>>> Nisscom protocol works! Use captured commands.")
    elif test3:
        print("\n>>> Hybrid approach works! Use combination.")
    else:
        print("\n>>> All tests failed. Device or ECU not responding.")
        print("    Possible issues:")
        print("    - Device not properly connected to car")
        print("    - Wrong OBD pins")
        print("    - ECU not compatible")
        print("    - Need additional initialization")

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
