"""
Nisscom Device - Multi-Baudrate Initialization
===============================================

From USB capture analysis, Nisscom software changes baudrates:
1. Sets baud to ~1200 (for K-line 5-baud init simulation)
2. Sets baud to ~10400
3. Sets baud to 38400 (for data)

This is KEY to K-line initialization!
"""

import serial
import time

class NisscomDevice:
    """Multi-baudrate approach based on USB capture"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.debug = True

    def k_line_init_multi_baud(self):
        """
        K-line init using baudrate changes + DTR/RTS
        This simulates the 5-baud init waveform
        """
        print("\n[K-LINE INIT] Multi-baudrate approach...")

        try:
            # Phase 1: Very slow baudrate for init waveform (simulates 5-baud)
            print("[K-LINE] Phase 1: Slow baudrate init (300 baud)...")
            ser1 = serial.Serial(self.port, baudrate=300, timeout=1)
            ser1.dtr = True
            ser1.rts = False

            # Send address byte at slow speed (simulates 5-baud)
            ser1.write(b'\x8F')  # Common K-line address byte
            time.sleep(0.2)

            ser1.close()
            time.sleep(0.1)

            # Phase 2: Medium baudrate (10400 baud - ECU response)
            print("[K-LINE] Phase 2: ECU sync (10400 baud)...")
            ser2 = serial.Serial(self.port, baudrate=10400, timeout=1)
            ser2.dtr = True
            ser2.rts = True

            # Wait for ECU sync bytes
            time.sleep(0.2)
            if ser2.in_waiting > 0:
                sync = ser2.read(ser2.in_waiting)
                print(f"[K-LINE] ECU sync: {' '.join([f'{b:02X}' for b in sync])}")

            ser2.close()
            time.sleep(0.1)

            # Phase 3: Final baudrate (38400 for data)
            print("[K-LINE] Phase 3: Data baudrate (38400)...")

            print("[K-LINE INIT] Complete")
            return True

        except Exception as e:
            print(f"[ERROR] K-line init failed: {e}")
            return False

    def connect(self, baudrate=38400):
        """Connect at specified baudrate"""
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=baudrate,
                timeout=2
            )

            # DTR/RTS both high for data mode
            self.ser.dtr = True
            self.ser.rts = True

            time.sleep(0.5)

            if self.debug:
                print(f"[CONNECT] Port open at {baudrate} baud")

            return True

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def send_command(self, cmd, wait_time=0.3):
        """Send command and get response with longer timeout"""
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

        # Wait longer for ECU response
        time.sleep(wait_time)

        # Read everything available
        response = []
        max_wait = time.time() + 1.5  # Longer timeout

        while time.time() < max_wait:
            if self.ser.in_waiting > 0:
                response.extend(self.ser.read(self.ser.in_waiting))
                time.sleep(0.05)  # Wait for more data
            elif len(response) > 0:
                break

        if self.debug and response:
            print(f"[RX] {' '.join([f'{b:02X}' for b in response])}")

        return response

    def init_ecu(self):
        """ECU initialization"""
        print("\n[ECU INIT] Starting...")

        # Try the sequence with longer waits
        self.send_command([0x81], wait_time=0.2)
        self.send_command([0x10], wait_time=0.2)
        self.send_command([0xFC], wait_time=0.2)
        self.send_command([0x81], wait_time=0.2)
        self.send_command([0x0E], wait_time=0.3)

        # Wait for any delayed ECU response
        time.sleep(0.5)
        if self.ser.in_waiting > 0:
            delayed = self.ser.read(self.ser.in_waiting)
            print(f"[ECU INIT] Delayed response: {' '.join([f'{b:02X}' for b in delayed])}")

        print("[ECU INIT] Complete")

    def test(self):
        """Test communication"""
        print("\n[TEST] Reading ECU ID...")
        self.send_command([0x02, 0x1A, 0x81, 0x9D], wait_time=0.5)

        print("\n[TEST] Reading sensor...")
        self.send_command([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D], wait_time=0.5)


def main():
    print("="*70)
    print("NISSCOM - MULTI-BAUDRATE K-LINE INIT")
    print("="*70)

    device = NisscomDevice(port='COM5')

    # K-line init with baudrate changes
    device.k_line_init_multi_baud()

    # Connect for data
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


if __name__ == "__main__":
    main()
