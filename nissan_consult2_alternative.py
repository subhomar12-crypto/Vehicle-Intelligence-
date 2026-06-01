"""
Nissan Consult-II Alternative Initialization Attempts
Tries multiple initialization sequences and timing variations
"""

import serial
import time
from typing import Optional, List

class Consult2Alternative:
    """Try alternative Consult-II initialization methods"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.successful_method = None

    def connect(self, baudrate):
        """Connect at specified baud rate"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(
                port=self.port,
                baudrate=baudrate,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def send_and_read(self, command: List[int], description: str, wait_time=0.5):
        """Send command and read response"""
        print(f"  Trying: {description}")
        print(f"    Send: {' '.join([f'{b:02X}' for b in command])}")

        self.ser.reset_input_buffer()
        self.ser.write(bytes(command))
        time.sleep(wait_time)

        response = self.ser.read(self.ser.in_waiting or 20)

        if response:
            hex_resp = ' '.join([f'{b:02X}' for b in response])
            print(f"    Recv: {hex_resp}")

            # Check for success indicators
            if 0x10 in response:
                print(f"    [SUCCESS] Got 0x10 acknowledgment!")
                return True, response
            elif len(response) > 0 and response != bytes(command):
                print(f"    [MAYBE] Got non-echo response")
                return None, response
            else:
                print(f"    [ECHO] Device just echoed back")
                return False, response
        else:
            print(f"    [NONE] No response")
            return False, None

    def method_1_standard_9600(self):
        """Standard Consult-II init at 9600 baud"""
        print("\n[Method 1] Standard Consult-II (9600 baud)")
        if not self.connect(9600):
            return False

        # FF FF EF with 500ms delay
        success, resp = self.send_and_read([0xFF, 0xFF, 0xEF], "FF FF EF (standard)", 0.5)
        return success

    def method_2_longer_delay(self):
        """Try with longer delays between bytes"""
        print("\n[Method 2] Longer delays between init bytes (9600 baud)")
        if not self.connect(9600):
            return False

        print("  Sending FF FF EF with 100ms between bytes...")
        self.ser.reset_input_buffer()

        for byte in [0xFF, 0xFF, 0xEF]:
            self.ser.write(bytes([byte]))
            print(f"    Sent: {byte:02X}")
            time.sleep(0.1)

        time.sleep(0.5)
        response = self.ser.read(self.ser.in_waiting or 20)

        if response:
            hex_resp = ' '.join([f'{b:02X}' for b in response])
            print(f"    Recv: {hex_resp}")
            if 0x10 in response:
                print(f"    [SUCCESS]")
                return True

        return False

    def method_3_38400_standard(self):
        """Try standard init at 38400 baud (where device responds)"""
        print("\n[Method 3] Standard init at 38400 baud")
        if not self.connect(38400):
            return False

        success, resp = self.send_and_read([0xFF, 0xFF, 0xEF], "FF FF EF at 38400", 0.5)
        return success

    def method_4_alternative_init_sequences(self):
        """Try alternative initialization commands at 38400"""
        print("\n[Method 4] Alternative init sequences at 38400 baud")
        if not self.connect(38400):
            return False

        # Try different initialization sequences found in docs
        sequences = [
            ([0xFF, 0xFF, 0xEF], "Standard FF FF EF"),
            ([0xFF, 0xFF, 0xEE], "Variant FF FF EE"),
            ([0xFF, 0xFF, 0x01], "Variant FF FF 01"),
            ([0x00, 0x00, 0x00], "Null sequence"),
            ([0xD0], "ECU Info Request"),
            ([0x5A, 0x00], "Start stream variant"),
        ]

        for seq, desc in sequences:
            success, resp = self.send_and_read(seq, desc, 0.3)
            if success:
                return True

        return False

    def method_5_repeated_init(self):
        """Try sending init multiple times rapidly"""
        print("\n[Method 5] Repeated rapid init (9600 baud)")
        if not self.connect(9600):
            return False

        print("  Sending FF FF EF 5 times rapidly...")
        self.ser.reset_input_buffer()

        for i in range(5):
            self.ser.write(bytes([0xFF, 0xFF, 0xEF]))
            time.sleep(0.05)

        time.sleep(0.5)
        response = self.ser.read(self.ser.in_waiting or 50)

        if response:
            hex_resp = ' '.join([f'{b:02X}' for b in response])
            print(f"    Recv: {hex_resp}")
            if 0x10 in response:
                print(f"    [SUCCESS]")
                return True

        return False

    def method_6_wakeup_then_init(self):
        """Try wakeup sequence before init"""
        print("\n[Method 6] Wakeup + Init sequence (9600 baud)")
        if not self.connect(9600):
            return False

        # Send wakeup nulls
        print("  Sending wakeup sequence (0x00 x 10)...")
        self.ser.write(bytes([0x00] * 10))
        time.sleep(0.3)

        success, resp = self.send_and_read([0xFF, 0xFF, 0xEF], "Then FF FF EF", 0.5)
        return success

    def method_7_check_register_direct(self):
        """Skip init, try reading register directly at 38400"""
        print("\n[Method 7] Skip init, read register directly (38400 baud)")
        if not self.connect(38400):
            return False

        # Try reading RPM register without init
        success, resp = self.send_and_read([0x5A, 0x01, 0x00], "Read register 0x00", 0.2)

        if resp and len(resp) > 0:
            # Check if we got actual data (not just echo)
            if resp != bytes([0x5A, 0x01, 0x00]) and len(resp) >= 1:
                print(f"    [INTERESTING] Got: {resp[0]:02X} ({resp[0]})")
                # Try reading multiple registers
                print("\n  Trying multiple registers...")
                for addr in [0x00, 0x08, 0x0B, 0x0C, 0x0D]:
                    self.ser.reset_input_buffer()
                    self.ser.write(bytes([0x5A, 0x01, addr]))
                    time.sleep(0.1)
                    r = self.ser.read(10)
                    if r and len(r) > 0:
                        print(f"    Reg 0x{addr:02X}: {' '.join([f'{b:02X}' for b in r])}")
                return True

        return False

    def method_8_baud_rate_scan(self):
        """Try init at various baud rates"""
        print("\n[Method 8] Baud rate scan")

        baud_rates = [9600, 19200, 38400, 57600, 115200]

        for baud in baud_rates:
            print(f"\n  Testing at {baud} baud...")
            if not self.connect(baud):
                continue

            success, resp = self.send_and_read([0xFF, 0xFF, 0xEF], f"Init at {baud}", 0.5)
            if success:
                print(f"    [SUCCESS] Working baud rate: {baud}")
                return True

        return False

    def run_all_methods(self):
        """Try all initialization methods"""
        print("=" * 70)
        print("NISSAN CONSULT-II ALTERNATIVE INITIALIZATION TEST")
        print("=" * 70)
        print("\nTrying multiple initialization methods to find one that works...")

        methods = [
            self.method_1_standard_9600,
            self.method_2_longer_delay,
            self.method_3_38400_standard,
            self.method_4_alternative_init_sequences,
            self.method_5_repeated_init,
            self.method_6_wakeup_then_init,
            self.method_7_check_register_direct,
            self.method_8_baud_rate_scan,
        ]

        for i, method in enumerate(methods, 1):
            try:
                result = method()
                if result:
                    self.successful_method = method.__name__
                    print(f"\n{'='*70}")
                    print(f"[SUCCESS] Method {i} ({method.__name__}) worked!")
                    print(f"{'='*70}")
                    return True
            except Exception as e:
                print(f"    [ERROR] {e}")

        print(f"\n{'='*70}")
        print("[RESULT] No initialization method successful")
        print("This device may require proprietary Nisscom software")
        print(f"{'='*70}")
        return False

    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    print("\nIMPORTANT: Make sure car ignition is ON\n")

    tester = Consult2Alternative(port='COM5')

    try:
        tester.run_all_methods()
    except KeyboardInterrupt:
        print("\n\n[STOPPED] User interrupted")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.close()

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
