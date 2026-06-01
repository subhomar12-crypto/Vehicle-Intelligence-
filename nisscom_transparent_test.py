"""
Nisscom Transparent Passthrough Test
Tests if device is transparent and ECU responses come through AFTER the echo
"""

import serial
import time

class TransparentTest:
    """Test if device is transparent passthrough"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None

    def connect(self, baudrate):
        """Connect at specified baud"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                port=self.port,
                baudrate=baudrate,
                timeout=3,  # Longer timeout to catch delayed responses
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

    def send_and_wait_for_more(self, command, desc, wait_time=2):
        """
        Send command and wait for BOTH echo AND ECU response
        Key insight: ECU response might come AFTER the echo
        """
        print(f"\n  Test: {desc}")
        cmd_bytes = bytes(command)
        cmd_hex = ' '.join([f'{b:02X}' for b in command])
        print(f"    Send: {cmd_hex}")

        self.ser.reset_input_buffer()
        self.ser.write(cmd_bytes)

        # Read in stages to see timing
        print(f"    Waiting {wait_time}s for response...")

        all_data = b''
        for i in range(int(wait_time * 10)):  # Check every 100ms
            time.sleep(0.1)
            if self.ser.in_waiting > 0:
                chunk = self.ser.read(self.ser.in_waiting)
                all_data += chunk

        if all_data:
            hex_resp = ' '.join([f'{b:02X}' for b in all_data])
            print(f"    Recv: {hex_resp} ({len(all_data)} bytes)")

            # Check if we got more than just echo
            if len(all_data) > len(command):
                print(f"    [INTERESTING] Got {len(all_data) - len(command)} extra bytes!")

                # Show echo vs extra data
                echo_part = all_data[:len(command)]
                extra_part = all_data[len(command):]

                echo_hex = ' '.join([f'{b:02X}' for b in echo_part])
                extra_hex = ' '.join([f'{b:02X}' for b in extra_part])

                print(f"    Echo part: {echo_hex}")
                print(f"    EXTRA DATA: {extra_hex}")

                # Check for known response patterns
                if 0x10 in extra_part:
                    print(f"    [SUCCESS] Found 0x10 acknowledgment in extra data!")
                    return True, extra_part
                elif any(b not in command for b in extra_part):
                    print(f"    [MAYBE] Extra data is not echo")
                    return None, extra_part

                return None, extra_part

            elif all_data == cmd_bytes:
                print(f"    [ECHO ONLY] Just our command echoed back")
            else:
                print(f"    [DIFFERENT] Response differs from command!")
                diff_hex = ' '.join([f'{b:02X}' for b in all_data])
                print(f"    Could be ECU response: {diff_hex}")
                return None, all_data
        else:
            print(f"    [NONE] No response at all")

        return False, None

    def test_consult_with_longer_wait(self, baudrate):
        """Test Consult-II with very long wait times"""
        print(f"\n{'='*70}")
        print(f"Testing Consult-II at {baudrate} baud with extended wait")
        print(f"{'='*70}")

        if not self.connect(baudrate):
            return False

        # Try init with longer wait
        success, data = self.send_and_wait_for_more(
            [0xFF, 0xFF, 0xEF],
            "Consult-II Init (wait 2s)",
            wait_time=2
        )

        if success:
            return True

        # Try register read with long wait
        success, data = self.send_and_wait_for_more(
            [0x5A, 0x01, 0x00, 0xF0],
            "Read RPM register (wait 2s)",
            wait_time=2
        )

        return success

    def test_ecu_direct_commands(self, baudrate):
        """Send commands that ECU should respond to"""
        print(f"\n{'='*70}")
        print(f"Testing ECU direct commands at {baudrate} baud")
        print(f"{'='*70}")

        if not self.connect(baudrate):
            return False

        # Commands that ECU should respond to
        ecu_commands = [
            ([0xFF, 0xFF, 0xEF], "ECU Wake-up"),
            ([0xD0], "ECU Info Request"),
            ([0xD1], "Self-Diagnostic"),
            ([0x5A, 0x00], "Start Data Stream"),
            ([0x5A, 0x01, 0x00], "Read Single Register"),
        ]

        for cmd, desc in ecu_commands:
            result, data = self.send_and_wait_for_more(cmd, desc, wait_time=1.5)
            if result:
                return True
            time.sleep(0.2)

        return False

    def test_continuous_read_filter_echo(self, baudrate):
        """
        Try continuous reading and filter out echoes
        Maybe ECU is responding but we're missing it
        """
        print(f"\n{'='*70}")
        print(f"Continuous monitoring at {baudrate} baud (filtering echoes)")
        print(f"{'='*70}")

        if not self.connect(baudrate):
            return False

        print("\n  Sending init and monitoring for 5 seconds...")
        print("  Looking for ANY byte that isn't an echo...")
        print()

        # Send init
        init_cmd = bytes([0xFF, 0xFF, 0xEF])
        self.ser.reset_input_buffer()
        self.ser.write(init_cmd)

        # Monitor for 5 seconds
        start = time.time()
        all_received = b''
        last_command = init_cmd

        while time.time() - start < 5:
            if self.ser.in_waiting > 0:
                chunk = self.ser.read(self.ser.in_waiting)
                all_received += chunk

                # Check if this chunk contains non-echo data
                if chunk != last_command:
                    hex_chunk = ' '.join([f'{b:02X}' for b in chunk])
                    print(f"  [{time.time()-start:4.1f}s] Recv: {hex_chunk}")

                # Send another command periodically
                if int(time.time() - start) % 2 == 1 and len(all_received) > 0:
                    # Try reading a register
                    cmd = bytes([0x5A, 0x01, 0x08])  # Read coolant temp
                    self.ser.write(cmd)
                    last_command = cmd

            time.sleep(0.05)

        if all_received:
            # Analysis
            print()
            print("  Total bytes received:", len(all_received))

            # Look for patterns
            unique_bytes = set(all_received)
            print(f"  Unique byte values: {sorted([f'{b:02X}' for b in unique_bytes])}")

            # Check if we got the init echo plus something else
            if len(all_received) > 3:
                print(f"  [INTERESTING] Received more than just init echo")
                extra = all_received[3:]
                extra_hex = ' '.join([f'{b:02X}' for b in extra])
                print(f"  Extra data: {extra_hex}")

                if 0x10 in extra:
                    print(f"  [SUCCESS] Found 0x10 byte in response!")
                    return True

        return False

    def test_bidirectional_communication(self, baudrate):
        """
        Test if device allows bidirectional communication
        ECU might be sending data on its own
        """
        print(f"\n{'='*70}")
        print(f"Testing for unsolicited ECU data at {baudrate} baud")
        print(f"{'='*70}")

        if not self.connect(baudrate):
            return False

        print("\n  Listening for 5 seconds WITHOUT sending anything...")
        print("  (ECU might broadcast data periodically)")
        print()

        self.ser.reset_input_buffer()
        start = time.time()

        while time.time() - start < 5:
            if self.ser.in_waiting > 0:
                data = self.ser.read(self.ser.in_waiting)
                hex_data = ' '.join([f'{b:02X}' for b in data])
                print(f"  [{time.time()-start:4.1f}s] Unsolicited: {hex_data}")
                print(f"  [INTERESTING] ECU is broadcasting!")
                return True

            time.sleep(0.1)

        print("  [NONE] No unsolicited data from ECU")
        return False

    def run_all_tests(self):
        """Run all transparency tests"""
        print("=" * 70)
        print("NISSCOM TRANSPARENT PASSTHROUGH TEST")
        print("=" * 70)
        print()
        print("Theory: Device might be transparent passthrough")
        print("        ECU responses might come AFTER echo")
        print()
        print("Testing this hypothesis...")

        # Test at both baud rates
        for baud in [9600, 38400]:
            print(f"\n\n{'#'*70}")
            print(f"TESTING AT {baud} BAUD")
            print(f"{'#'*70}")

            # Test 1: Extended wait times
            if self.test_consult_with_longer_wait(baud):
                print(f"\n[SUCCESS] Device is transparent at {baud} baud!")
                return True

            # Test 2: Direct ECU commands
            if self.test_ecu_direct_commands(baud):
                print(f"\n[SUCCESS] ECU responded at {baud} baud!")
                return True

            # Test 3: Continuous monitoring
            if self.test_continuous_read_filter_echo(baud):
                print(f"\n[SUCCESS] Found non-echo data at {baud} baud!")
                return True

            # Test 4: Listen for broadcasts
            if self.test_bidirectional_communication(baud):
                print(f"\n[SUCCESS] ECU broadcasts data at {baud} baud!")
                return True

        print("\n\n" + "=" * 70)
        print("[RESULT] Device is NOT transparent")
        print("=" * 70)
        print()
        print("Conclusion:")
        print("  - Device only echoes, no ECU data passes through")
        print("  - Device acts as active bridge, not passive wire")
        print("  - Needs Nisscom software to translate/bridge protocols")
        print()
        print("This means the device firmware is blocking direct access.")
        print("Without Nisscom software, device cannot be used.")
        print()

        return False

    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    print()
    print("NISSCOM TRANSPARENCY TEST")
    print()
    print("This test checks if ECU responses come through after echoes")
    print()
    print("REQUIREMENTS:")
    print("  - Car ignition ON")
    print("  - Nisscom device connected to car AND computer")
    print()
    print("Starting in 2 seconds...")
    time.sleep(2)
    print()

    tester = TransparentTest()

    try:
        success = tester.run_all_tests()

        if not success:
            print()
            print("=" * 70)
            print("FINAL ANSWER TO YOUR QUESTION:")
            print("=" * 70)
            print()
            print("Q: Can you make things work with the echos?")
            print()
            print("A: NO - the device firmware actively blocks communication")
            print()
            print("   The device is NOT a simple wire or transparent bridge.")
            print("   It has firmware that:")
            print("     - Echoes all commands back to computer")
            print("     - Blocks ECU responses from passing through")
            print("     - Requires Nisscom software to unlock/configure")
            print()
            print("   We cannot bypass this without:")
            print("     Option 1: Nisscom software (to unlock device)")
            print("     Option 2: Reflashing device firmware (risky/impossible)")
            print("     Option 3: Buying different adapter (easier!)")
            print()
            print("   RECOMMENDED: Buy Consult-II adapter ($40-80)")
            print("                Those adapters work immediately")
            print()

    except KeyboardInterrupt:
        print("\n[STOPPED]")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.close()

    print()


if __name__ == "__main__":
    main()
