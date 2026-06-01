"""
Nisscom Hardware Flow Control Test
Tests different serial port configurations to disable echo mode
"""

import serial
import time

class NisscomHardwareTest:
    """Test different hardware configurations"""

    def __init__(self, port='COM5'):
        self.port = port

    def test_configuration(self, config_name, **serial_params):
        """Test a specific serial configuration"""
        print(f"\n[Test] {config_name}")
        print(f"  Config: {serial_params}")

        try:
            ser = serial.Serial(self.port, **serial_params)
            time.sleep(0.5)

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Try init command
            test_cmd = bytes([0xFF, 0xFF, 0xEF])
            print(f"  Send: FF FF EF")

            ser.write(test_cmd)
            time.sleep(0.5)

            response = ser.read(ser.in_waiting or 20)

            if response:
                hex_resp = ' '.join([f'{b:02X}' for b in response])
                print(f"  Recv: {hex_resp}")

                if response != test_cmd:
                    print(f"  [DIFFERENT] Not an echo!")
                    if 0x10 in response:
                        print(f"  [SUCCESS] Got 0x10 acknowledgment!")
                        ser.close()
                        return True
                else:
                    print(f"  [ECHO] Still echoing")
            else:
                print(f"  [NONE] No response")

            ser.close()
            return False

        except Exception as e:
            print(f"  [ERROR] {e}")
            return False

    def run_tests(self):
        """Run all hardware configuration tests"""
        print("=" * 70)
        print("NISSCOM HARDWARE FLOW CONTROL TEST")
        print("=" * 70)
        print("\nTrying different serial port configurations...")

        # Test 1: Standard settings with RTS/CTS disabled
        if self.test_configuration(
            "Standard (no flow control)",
            baudrate=9600,
            timeout=2,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False
        ):
            return True

        # Test 2: RTS/CTS hardware flow control
        if self.test_configuration(
            "RTS/CTS hardware flow control",
            baudrate=9600,
            timeout=2,
            rtscts=True,
            dsrdtr=False,
            xonxoff=False
        ):
            return True

        # Test 3: DSR/DTR hardware flow control
        if self.test_configuration(
            "DSR/DTR hardware flow control",
            baudrate=9600,
            timeout=2,
            rtscts=False,
            dsrdtr=True,
            xonxoff=False
        ):
            return True

        # Test 4: Software flow control (XON/XOFF)
        if self.test_configuration(
            "Software flow control (XON/XOFF)",
            baudrate=9600,
            timeout=2,
            rtscts=False,
            dsrdtr=False,
            xonxoff=True
        ):
            return True

        # Test 5: All flow control enabled
        if self.test_configuration(
            "All flow control enabled",
            baudrate=9600,
            timeout=2,
            rtscts=True,
            dsrdtr=True,
            xonxoff=True
        ):
            return True

        # Test 6-10: Same tests at 38400 baud
        for baud in [38400]:
            if self.test_configuration(
                f"Standard at {baud} baud",
                baudrate=baud,
                timeout=2,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False
            ):
                return True

            if self.test_configuration(
                f"RTS/CTS at {baud} baud",
                baudrate=baud,
                timeout=2,
                rtscts=True,
                dsrdtr=False,
                xonxoff=False
            ):
                return True

        # Test with RTS/DTR line states
        print("\n[Test] Manual RTS/DTR control at 9600 baud")
        try:
            ser = serial.Serial(
                self.port,
                baudrate=9600,
                timeout=2,
                rtscts=False,
                dsrdtr=False
            )
            time.sleep(0.3)

            # Try different RTS/DTR combinations
            combinations = [
                (False, False, "RTS=Low, DTR=Low"),
                (True, False, "RTS=High, DTR=Low"),
                (False, True, "RTS=Low, DTR=High"),
                (True, True, "RTS=High, DTR=High"),
            ]

            for rts, dtr, desc in combinations:
                print(f"  Trying: {desc}")
                ser.rts = rts
                ser.dtr = dtr
                time.sleep(0.2)

                ser.reset_input_buffer()
                ser.write(bytes([0xFF, 0xFF, 0xEF]))
                time.sleep(0.3)

                response = ser.read(ser.in_waiting or 20)
                if response:
                    hex_resp = ' '.join([f'{b:02X}' for b in response])
                    print(f"    Recv: {hex_resp}")

                    if response != bytes([0xFF, 0xFF, 0xEF]) and len(response) > 0:
                        print(f"    [DIFFERENT] Not an echo!")
                        if 0x10 in response:
                            print(f"    [SUCCESS] Got acknowledgment!")
                            ser.close()
                            return True

            ser.close()

        except Exception as e:
            print(f"  [ERROR] {e}")

        return False


def main():
    print("\nTesting hardware flow control configurations...")
    print("This checks if the device is in echo/loopback mode\n")

    tester = NisscomHardwareTest(port='COM5')

    try:
        success = tester.run_tests()

        if success:
            print("\n" + "=" * 70)
            print("[SUCCESS] Found working configuration!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("[RESULT] No configuration worked")
            print("\nConclusion:")
            print("  The device is a simple serial passthrough/echo adapter")
            print("  It requires Nisscom's proprietary software to function")
            print("  The software likely sends special initialization commands")
            print("  or the device needs driver-level configuration")
            print("\nRecommendations:")
            print("  1. Contact Nisscom for official software download")
            print("  2. Check if device needs driver installation")
            print("  3. Use protocol sniffer when software is available")
            print("=" * 70)

    except KeyboardInterrupt:
        print("\n[STOPPED] User interrupted")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("\n")


if __name__ == "__main__":
    main()
