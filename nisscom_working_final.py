"""
Nisscom Working Protocol - FINAL VERSION
=========================================

Successfully decoded from NDS II decompilation.

Key discovery: MCU activation requires BREAK signal via EscapeCommFunction(8/9)

Protocol:
1. Open port at 10400 baud
2. SETBREAK (EscapeCommFunction 8)
3. Wait 25ms
4. CLRBREAK (EscapeCommFunction 9)
5. Wait 25ms
6. Send init: 81 10 FC 81 0E
7. ECU responds: 83 FC 10 C1 xx xx CS

Then send CONSULT-II commands.
"""

import serial
import time
import ctypes
from ctypes import wintypes

# Windows API constants for EscapeCommFunction
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6

# Load kernel32
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL


class NisscomAdapter:
    """Nisscom USB adapter communication class."""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.handle = None
        self.connected = False

    def _escape_comm(self, func):
        """Call Windows EscapeCommFunction."""
        if self.handle:
            return kernel32.EscapeCommFunction(self.handle, func)
        return False

    def connect(self):
        """Initialize connection to ECU via Nisscom adapter."""
        print(f"Connecting to ECU via {self.port}...")

        # Open serial port
        self.ser = serial.Serial(self.port, baudrate=10400, timeout=1)
        self.handle = self.ser._port_handle

        # Clear buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.05)

        # Set DTR
        self._escape_comm(SETDTR)
        time.sleep(0.025)

        # BREAK signal sequence - THIS IS THE KEY!
        self._escape_comm(SETBREAK)
        time.sleep(0.025)
        self._escape_comm(CLRBREAK)
        time.sleep(0.025)

        # Clear any garbage from BREAK
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Send CONSULT-II init: 81 10 FC 81 0E
        init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        for byte in init_bytes:
            self.ser.write(bytes([byte]))
            time.sleep(0.010)

        # Wait for ECU response
        time.sleep(0.3)

        response = []
        for _ in range(5):
            if self.ser.in_waiting > 0:
                response.extend(list(self.ser.read(self.ser.in_waiting)))
            time.sleep(0.05)

        # Check for valid response (should contain 0x83)
        if 0x83 in response:
            self.connected = True
            print(f"ECU connected! Response: {' '.join([f'{b:02X}' for b in response])}")
            return True
        else:
            print(f"Connection failed. Response: {' '.join([f'{b:02X}' for b in response])}")
            return False

    def disconnect(self):
        """Close connection."""
        if self.ser:
            self.ser.close()
            self.ser = None
            self.handle = None
            self.connected = False
            print("Disconnected.")

    def send_command(self, cmd_bytes, wait_time=0.3):
        """Send command and receive response."""
        if not self.connected:
            raise Exception("Not connected to ECU")

        # Clear input buffer
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Send command
        self.ser.write(bytes(cmd_bytes))
        self.ser.flush()

        # Wait for response
        time.sleep(wait_time)

        response = []
        for _ in range(5):
            if self.ser.in_waiting > 0:
                response.extend(list(self.ser.read(self.ser.in_waiting)))
            time.sleep(0.05)

        return response

    def calc_checksum(self, data):
        """Calculate CONSULT-II checksum (sum of bytes & 0xFF)."""
        return sum(data) & 0xFF

    def read_ecu_id(self):
        """Read ECU identification."""
        # Command: 02 1A 81 CS (Request ECU ID)
        cmd = [0x02, 0x1A, 0x81]
        cmd.append(self.calc_checksum(cmd))

        print(f"Reading ECU ID: {' '.join([f'{b:02X}' for b in cmd])}")
        response = self.send_command(cmd)

        if response:
            # Skip echo, find actual response
            resp_hex = ' '.join([f'{b:02X}' for b in response])
            print(f"Response: {resp_hex}")

            # Look for 5A response (positive response to 1A)
            if 0x5A in response:
                idx = response.index(0x5A)
                # Extract ID string
                if idx + 1 < len(response):
                    length = response[idx - 1] if idx > 0 else 0
                    id_bytes = response[idx + 1:idx + length]
                    try:
                        ecu_id = ''.join([chr(b) for b in id_bytes if 32 <= b < 127])
                        print(f"ECU ID: {ecu_id}")
                        return ecu_id
                    except:
                        pass

        return None

    def read_sensor(self, sensor_addr):
        """
        Read sensor data.
        Command format: 05 22 11 XX 04 01 CS
        Where XX is the sensor address.
        """
        cmd = [0x05, 0x22, 0x11, sensor_addr, 0x04, 0x01]
        cmd.append(self.calc_checksum(cmd))

        response = self.send_command(cmd)

        if response:
            # Look for 62 response (positive response to 22)
            if 0x62 in response:
                idx = response.index(0x62)
                # Extract data bytes
                if idx + 4 < len(response):
                    data = response[idx + 3:idx + 7]  # 4 data bytes
                    return data

        return None

    def send_keep_alive(self):
        """Send keep-alive to maintain session."""
        cmd = [0x04, 0x21, 0x81, 0x04, 0x01, 0xAB]
        self.send_command(cmd, wait_time=0.1)


def main():
    """Main test function."""
    print("=" * 60)
    print("NISSCOM WORKING PROTOCOL - FINAL")
    print("=" * 60)
    print()

    adapter = NisscomAdapter('COM5')

    try:
        # Connect to ECU
        if adapter.connect():
            print()

            # Read ECU ID
            print("-" * 40)
            ecu_id = adapter.read_ecu_id()
            print()

            # Read some sensors
            print("-" * 40)
            print("Reading sensors...")

            # Sensor addresses from USB capture
            sensor_addrs = [0x00, 0x20, 0x01, 0x02]

            for addr in sensor_addrs:
                data = adapter.read_sensor(addr)
                if data:
                    hex_data = ' '.join([f'{b:02X}' for b in data])
                    print(f"Sensor 0x{addr:02X}: {hex_data}")
                else:
                    print(f"Sensor 0x{addr:02X}: No data")
                time.sleep(0.2)

            print()
            print("-" * 40)
            print("Connection successful!")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
