"""
Nisscom Device - Complete Implementation
=========================================

Based on USB capture analysis, this uses:
1. FTDI commands to control DTR/RTS for K-line initialization
2. Serial commands for ECU communication

Requirements:
  pip install pyftdi pyserial
"""

import time
from pyftdi.ftdi import Ftdi
import serial

class NisscomDevice:
    """Complete Nisscom device control with FTDI + Serial"""

    def __init__(self, port='COM5'):
        self.port = port
        self.ftdi = None
        self.ser = None
        self.debug = True

    def connect_ftdi(self):
        """Connect using FTDI library for low-level control"""
        try:
            self.ftdi = Ftdi()

            # Open the device (you may need to adjust URL)
            # Common FTDI URLs: 'ftdi://ftdi:232/1' or 'ftdi://ftdi:ft232/1'
            self.ftdi.open_from_url('ftdi://ftdi:232/1')

            if self.debug:
                print("[FTDI] Connected to device")

            return True

        except Exception as e:
            print(f"[ERROR] FTDI connection failed: {e}")
            print("[INFO] Trying serial-only approach...")
            return False

    def kline_init_via_dtr_rts(self):
        """
        Perform K-line initialization using DTR/RTS toggling
        Based on captured sequence
        """
        print("\n[K-LINE] Performing K-line initialization via DTR/RTS...")

        if not self.ftdi:
            print("[WARNING] FTDI not available, trying serial DTR/RTS")
            return self.kline_init_serial_dtr_rts()

        try:
            # Sequence from capture:
            # Multiple resets, then DTR/RTS toggling

            # Reset FTDI
            self.ftdi.reset()
            time.sleep(0.05)

            # Set latency timer
            self.ftdi.set_latency_timer(16)

            # DTR ON, RTS OFF (wValue=0x0101)
            self.ftdi.set_dtr_rts(dtr=True, rts=False)
            time.sleep(0.01)

            # DTR OFF, RTS ON (wValue=0x0202)
            self.ftdi.set_dtr_rts(dtr=False, rts=True)
            time.sleep(0.01)

            # DTR OFF, RTS ON again
            self.ftdi.set_dtr_rts(dtr=False, rts=True)
            time.sleep(0.01)

            # DTR ON, RTS OFF
            self.ftdi.set_dtr_rts(dtr=True, rts=False)
            time.sleep(0.01)

            print("[K-LINE] DTR/RTS initialization complete")
            return True

        except Exception as e:
            print(f"[ERROR] K-line init failed: {e}")
            return False

    def kline_init_serial_dtr_rts(self):
        """Fallback: K-line init using pyserial DTR/RTS"""
        try:
            # Open serial port temporarily for DTR/RTS control
            temp_ser = serial.Serial(self.port, baudrate=38400, timeout=1)

            # Toggle DTR/RTS
            temp_ser.dtr = True
            temp_ser.rts = False
            time.sleep(0.01)

            temp_ser.dtr = False
            temp_ser.rts = True
            time.sleep(0.01)

            temp_ser.dtr = False
            temp_ser.rts = True
            time.sleep(0.01)

            temp_ser.dtr = True
            temp_ser.rts = False
            time.sleep(0.01)

            temp_ser.close()

            print("[K-LINE] Serial DTR/RTS initialization complete")
            return True

        except Exception as e:
            print(f"[ERROR] Serial DTR/RTS init failed: {e}")
            return False

    def connect_serial(self):
        """Connect via serial port for data communication"""
        try:
            # Close FTDI if open (we'll use serial for data)
            if self.ftdi:
                self.ftdi.close()
                self.ftdi = None

            # Open serial port at 38400 baud
            self.ser = serial.Serial(
                self.port,
                baudrate=38400,
                timeout=2,
                rtscts=False,
                dsrdtr=False
            )
            time.sleep(0.5)

            if self.debug:
                print(f"[SERIAL] Connected to {self.port} at 38400 baud")

            return True

        except Exception as e:
            print(f"[ERROR] Serial connection failed: {e}")
            return False

    def send_command(self, cmd):
        """Send command and return response"""
        if not self.ser or not self.ser.is_open:
            print("[ERROR] Serial port not open")
            return None

        # Send command
        self.ser.write(bytes(cmd))
        self.ser.flush()

        if self.debug:
            hex_cmd = ' '.join([f'{b:02X}' for b in cmd])
            print(f"[SEND] {hex_cmd}")

        # Wait for response
        time.sleep(0.2)

        # Read response
        response = []
        while self.ser.in_waiting > 0:
            response.append(self.ser.read(1)[0])
            time.sleep(0.01)

        if self.debug and response:
            hex_resp = ' '.join([f'{b:02X}' for b in response])
            print(f"[RECV] {hex_resp}")

        return response

    def initialize_ecu(self):
        """
        Initialize ECU communication
        From capture: 81, 10, FC, 81, 0E sequence
        """
        print("\n[INIT] Initializing ECU communication...")

        # Send init sequence
        cmds = [
            [0x81],
            [0x10],
            [0xFC],
            [0x81],
            [0x0E]
        ]

        for cmd in cmds:
            resp = self.send_command(cmd)
            time.sleep(0.05)

        print("[INIT] ECU initialization complete")
        return True

    def read_ecu_info(self):
        """Read ECU identification"""
        print("\n[ECU INFO] Reading ECU identification...")

        # From capture: 02 1A 81 9D gets ECU ID
        resp = self.send_command([0x02, 0x1A, 0x81, 0x9D])

        if resp and len(resp) > 4:
            # Look for ASCII data in response
            ecu_id = ''
            for b in resp[4:]:  # Skip echo
                if 32 <= b < 127:
                    ecu_id += chr(b)

            if ecu_id:
                print(f"[ECU INFO] ECU ID: {ecu_id}")
                return ecu_id

        return None

    def read_sensor(self, reg, addr=0x00):
        """Read sensor data"""
        # Format: 05 22 [reg] [addr] 04 01 [checksum]
        cmd = [0x05, 0x22, reg, addr, 0x04, 0x01]
        checksum = sum(cmd) & 0xFF
        cmd.append(checksum)

        resp = self.send_command(cmd)

        if resp and len(resp) > 7:
            # Real data comes after echo
            # Format: 07 62 [reg] [addr] [data...]
            return resp[7:]  # Return actual sensor data

        return None

    def read_rpm(self):
        """Read engine RPM"""
        data = self.read_sensor(0x12, 0x00)
        if data and len(data) >= 2:
            # RPM calculation (example - may need adjustment)
            rpm = (data[0] * 256 + data[1]) // 4
            return rpm
        return None

    def test_connection(self):
        """Test complete connection"""
        print("\n" + "="*70)
        print("TESTING COMPLETE NISSCOM CONNECTION")
        print("="*70)

        # Read ECU info
        ecu_id = self.read_ecu_info()

        # Try reading a sensor
        print("\n[TEST] Reading sensor register 0x11...")
        data = self.read_sensor(0x11, 0x00)
        if data:
            print(f"[TEST] Sensor data: {' '.join([f'{b:02X}' for b in data])}")

        # Try RPM
        print("\n[TEST] Reading RPM...")
        rpm = self.read_rpm()
        if rpm:
            print(f"[TEST] RPM: {rpm}")


def main():
    """Main test"""

    print("="*70)
    print("NISSCOM DEVICE - COMPLETE IMPLEMENTATION")
    print("Based on USB capture reverse engineering")
    print("="*70)

    device = NisscomDevice(port='COM5')

    # Step 1: Try FTDI approach first
    print("\n[STEP 1] Attempting FTDI connection for K-line init...")
    if device.connect_ftdi():
        device.kline_init_via_dtr_rts()
    else:
        # Fallback: Use serial DTR/RTS
        print("\n[FALLBACK] Using serial DTR/RTS for K-line init...")
        device.kline_init_serial_dtr_rts()

    # Step 2: Connect via serial for data
    print("\n[STEP 2] Connecting via serial for data communication...")
    if not device.connect_serial():
        print("[ERROR] Failed to connect")
        return

    # Step 3: Initialize ECU
    print("\n[STEP 3] Initializing ECU...")
    device.initialize_ecu()

    # Step 4: Test
    device.test_connection()

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
