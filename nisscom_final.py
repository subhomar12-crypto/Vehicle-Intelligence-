"""
Nisscom Device - FINAL VERSION
===============================

Using exact baudrate sequence found in binary analysis:
300 → 1200 → 9600 → 10400 → 38400

This replicates what the DLL does!
"""

import serial
import time

class NisscomFinal:
    """Final implementation with correct baudrate sequence"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.debug = True

    def k_line_init_exact_sequence(self):
        """
        K-line initialization using EXACT baudrate sequence from binary analysis.

        The Nisscom software does:
        1. 300 baud - K-line address byte
        2. 1200 baud - Slow init waveform
        3. 9600 baud - ECU sync
        4. 10400 baud - ECU response
        5. 38400 baud - Data transfer
        """
        print("\n[K-LINE INIT] Multi-baudrate sequence (from binary analysis)...")

        try:
            # Phase 1: 300 baud - Send address byte (K-line 5-baud init simulation)
            print("[K-LINE] Phase 1: 300 baud - Address byte...")
            ser = serial.Serial(self.port, baudrate=300, timeout=1)
            ser.dtr = True
            ser.rts = False

            # Send K-line address (0x33 is common for Nissan)
            ser.write(b'\x33')
            time.sleep(0.3)
            ser.close()
            time.sleep(0.05)

            # Phase 2: 1200 baud - Slow init waveform
            print("[K-LINE] Phase 2: 1200 baud - Slow init...")
            ser = serial.Serial(self.port, baudrate=1200, timeout=1)
            ser.dtr = True
            ser.rts = True

            time.sleep(0.2)
            if ser.in_waiting > 0:
                sync1 = ser.read(ser.in_waiting)
                print(f"  Sync @1200: {' '.join([f'{b:02X}' for b in sync1])}")

            ser.close()
            time.sleep(0.05)

            # Phase 3: 9600 baud - ECU sync
            print("[K-LINE] Phase 3: 9600 baud - ECU sync...")
            ser = serial.Serial(self.port, baudrate=9600, timeout=1)
            ser.dtr = True
            ser.rts = True

            time.sleep(0.2)
            if ser.in_waiting > 0:
                sync2 = ser.read(ser.in_waiting)
                print(f"  Sync @9600: {' '.join([f'{b:02X}' for b in sync2])}")

            ser.close()
            time.sleep(0.05)

            # Phase 4: 10400 baud - ECU response
            print("[K-LINE] Phase 4: 10400 baud - ECU response...")
            ser = serial.Serial(self.port, baudrate=10400, timeout=1)
            ser.dtr = True
            ser.rts = True

            time.sleep(0.2)
            if ser.in_waiting > 0:
                sync3 = ser.read(ser.in_waiting)
                print(f"  Sync @10400: {' '.join([f'{b:02X}' for b in sync3])}")

            ser.close()
            time.sleep(0.05)

            # Phase 5: 38400 baud - Data transfer (final)
            print("[K-LINE] Phase 5: 38400 baud - Data mode...")

            print("[K-LINE INIT] Complete!")
            return True

        except Exception as e:
            print(f"[ERROR] K-line init failed: {e}")
            return False

    def connect(self, baudrate=38400):
        """Connect at final baudrate for data transfer"""
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=baudrate,
                timeout=2
            )

            # DTR/RTS high for data mode
            self.ser.dtr = True
            self.ser.rts = True

            time.sleep(0.5)

            if self.debug:
                print(f"[CONNECT] Port open at {baudrate} baud")

            return True

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def send_command(self, cmd, wait_time=0.5):
        """Send command and get response"""
        if not self.ser:
            return None

        # Clear buffer
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Send
        self.ser.write(bytes(cmd))
        self.ser.flush()

        if self.debug:
            print(f"[TX] {' '.join([f'{b:02X}' for b in cmd])}")

        # Wait for response with longer timeout
        time.sleep(wait_time)

        # Read all available
        response = []
        max_wait = time.time() + 2.0

        while time.time() < max_wait:
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
                time.sleep(0.05)  # Wait for more
            elif len(response) > 0:
                break

        if self.debug and response:
            print(f"[RX] {' '.join([f'{b:02X}' for b in response])}")

            # Check if NOT just echo
            if response != cmd:
                print("  >>> NON-ECHO RESPONSE - ECU IS RESPONDING!")

        return response

    def init_ecu(self):
        """ECU initialization"""
        print("\n[ECU INIT] Sending initialization sequence...")

        self.send_command([0x81], wait_time=0.3)
        self.send_command([0x10], wait_time=0.3)
        self.send_command([0xFC], wait_time=0.3)
        self.send_command([0x81], wait_time=0.3)
        self.send_command([0x0E], wait_time=0.5)

        print("[ECU INIT] Complete")

    def test(self):
        """Test communication"""
        print("\n" + "="*70)
        print("TESTING ECU COMMUNICATION")
        print("="*70)

        # ECU ID
        print("\n[TEST] Reading ECU ID...")
        self.send_command([0x02, 0x1A, 0x81, 0x9D], wait_time=0.6)

        # Sensor reads
        print("\n[TEST] Reading sensor register 0x11...")
        self.send_command([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D], wait_time=0.6)

        print("\n[TEST] Reading sensor register 0x12...")
        self.send_command([0x05, 0x22, 0x12, 0x00, 0x04, 0x01, 0x3E], wait_time=0.6)

        print("\n" + "="*70)


def main():
    print("="*70)
    print("NISSCOM - FINAL IMPLEMENTATION")
    print("Using exact baudrate sequence from binary analysis")
    print("="*70)
    print("\nBaudrate sequence: 300 → 1200 → 9600 → 10400 → 38400")
    print("This is what the Nisscom software does!\n")

    device = NisscomFinal(port='COM5')

    # Multi-baud K-line init
    device.k_line_init_exact_sequence()

    # Connect for data at 38400
    device.connect(baudrate=38400)

    # Init ECU
    device.init_ecu()

    # Test
    device.test()

    print("\n[DONE] Press Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if device.ser:
            device.ser.close()
        print("\n[EXIT] Closed")


if __name__ == "__main__":
    main()
