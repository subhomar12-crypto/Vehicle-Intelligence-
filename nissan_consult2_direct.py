"""
Nissan Consult-II Protocol Implementation
==========================================

Based on official Consult-II protocol specification.
Works with Nisscom device or any Consult-II compatible adapter.

References:
- Consult Protocol & Commands Issue 7
- http://www.tocpcs.com/nissan-consult-ii-protocol-details/
- https://www.plmsdevelopments.com/images_ms/Consult_Protocol_&_Commands_Issue_6.pdf
"""

import serial
import time
from typing import List, Optional

class ConsultII:
    """Nissan Consult-II protocol implementation"""

    # Protocol constants
    BAUD_RATE = 9600  # Standard Consult-II baudrate (NOT 38400!)

    # Initialization
    INIT_SEQUENCE = [0xFF, 0xFF, 0xEF]  # Consult-II init
    INIT_RESPONSE = 0x10  # Expected ECU response

    # Commands
    CMD_SELF_DIAG = 0xD0  # Self-diagnostic results
    CMD_REALTIME = 0x5A   # Real-time data
    CMD_TERMINATE = 0xF0  # Terminate/go-ahead
    CMD_ECU_PART = 0xD1   # ECU part number

    def __init__(self, port='COM5', baudrate=None):
        """
        Initialize Consult-II interface

        Args:
            port: Serial port where adapter is connected
            baudrate: Override baudrate (default: 9600 for Consult-II)
        """
        self.port = port
        self.baudrate = baudrate if baudrate else self.BAUD_RATE
        self.ser = None
        self.debug = True
        self.ecu_connected = False

    def connect(self) -> bool:
        """Open serial connection"""
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)

            if self.debug:
                print(f"[CONNECT] Opened {self.port} at {self.baudrate} baud")

            return True

        except serial.SerialException as e:
            print(f"[ERROR] Failed to open {self.port}: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            if self.debug:
                print(f"[DISCONNECT] Closed {self.port}")

    def _send_bytes(self, data: List[int]):
        """Send bytes to device"""
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Not connected")

        self.ser.write(bytes(data))
        self.ser.flush()

        if self.debug:
            hex_str = ' '.join([f'{b:02X}' for b in data])
            print(f"[SEND] {hex_str}")

    def _read_bytes(self, count: int = None, timeout: float = 1.0) -> List[int]:
        """
        Read bytes from device

        Args:
            count: Number of bytes to read (None = read all available)
            timeout: Timeout in seconds

        Returns:
            List of bytes received
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Not connected")

        response = []
        start_time = time.time()

        if count:
            # Read specific number of bytes
            while len(response) < count and (time.time() - start_time) < timeout:
                if self.ser.in_waiting > 0:
                    response.append(self.ser.read(1)[0])
                else:
                    time.sleep(0.01)
        else:
            # Read all available
            time.sleep(0.2)  # Wait for data
            while self.ser.in_waiting > 0:
                response.append(self.ser.read(1)[0])
                time.sleep(0.01)

        if self.debug and response:
            hex_str = ' '.join([f'{b:02X}' for b in response])
            print(f"[RECV] {hex_str}")

        return response

    def initialize_ecu(self) -> bool:
        """
        Initialize ECU communication using Consult-II protocol

        Sends: FF FF EF
        Expects: 10 (ECU ready)

        Returns:
            True if ECU responds correctly
        """
        print("\n" + "=" * 60)
        print("INITIALIZING ECU (Consult-II Protocol)")
        print("=" * 60)

        # Clear any pending data
        if self.ser.in_waiting > 0:
            self.ser.read(self.ser.in_waiting)

        # Send initialization sequence
        print("\n[INIT] Sending Consult-II init sequence: FF FF EF")
        self._send_bytes(self.INIT_SEQUENCE)

        # Wait for response
        time.sleep(0.3)
        response = self._read_bytes()

        # Check for expected response (0x10)
        if response and self.INIT_RESPONSE in response:
            print(f"[INIT] OK ECU responded with 0x10 - READY!")
            print("=" * 60)
            print("ECU INITIALIZATION SUCCESSFUL")
            print("=" * 60)
            self.ecu_connected = True
            return True
        else:
            print(f"[INIT] X Unexpected response: {response}")
            print("=" * 60)
            print("ECU INITIALIZATION FAILED")
            print("=" * 60)
            self.ecu_connected = False
            return False

    def read_ecu_part_number(self) -> Optional[str]:
        """
        Read ECU part number

        Returns:
            Part number string or None
        """
        if not self.ecu_connected:
            print("[ERROR] ECU not initialized")
            return None

        print("\n[CMD] Reading ECU part number...")

        # Send command D1 (ECU part number)
        self._send_bytes([self.CMD_ECU_PART])

        # Send terminate/go-ahead
        self._send_bytes([self.CMD_TERMINATE])

        # Read response
        response = self._read_bytes()

        if response and len(response) > 2:
            # Response format: [FF] [length] [data...]
            if response[0] == 0xFF:
                length = response[1]
                data = response[2:2+length]

                # Try to decode as ASCII
                try:
                    part_str = ''.join([chr(b) for b in data if 32 <= b < 127])
                    print(f"[PART] ECU Part Number: {part_str}")
                    return part_str
                except:
                    print(f"[PART] Raw data: {data}")
                    return None

        return None

    def read_realtime_data(self, register: int) -> Optional[int]:
        """
        Read real-time sensor data

        Args:
            register: Register address to read

        Returns:
            Data value or None
        """
        if not self.ecu_connected:
            print("[ERROR] ECU not initialized")
            return None

        # Send real-time data command with register
        self._send_bytes([self.CMD_REALTIME, register, 0x00])

        # Send terminate
        self._send_bytes([self.CMD_TERMINATE])

        # Read response
        response = self._read_bytes()

        if response and len(response) > 0:
            return response

        return None

    def test_communication(self):
        """Test basic ECU communication"""
        print("\n" + "=" * 60)
        print("TESTING ECU COMMUNICATION")
        print("=" * 60)

        # Try to read ECU part number
        part = self.read_ecu_part_number()

        # Try reading some registers
        print("\n[TEST] Attempting to read sensor registers...")
        for reg in [0x00, 0x01, 0x02, 0x08, 0x0B]:
            print(f"\n[TEST] Register 0x{reg:02X}...")
            data = self.read_realtime_data(reg)
            if data:
                print(f"  Data: {' '.join([f'{b:02X}' for b in data])}")


def main():
    """Test program"""

    print("=" * 60)
    print("NISSAN CONSULT-II DIRECT COMMUNICATION")
    print("Using Official Consult-II Protocol")
    print("=" * 60)

    # Try both baudrates
    for baudrate in [9600, 38400]:
        print(f"\n\n{'=' * 60}")
        print(f"ATTEMPTING CONNECTION AT {baudrate} BAUD")
        print("=" * 60)

        consult = ConsultII(port='COM5', baudrate=baudrate)

        if not consult.connect():
            continue

        try:
            # Try to initialize ECU
            if consult.initialize_ecu():
                # Success! Test communication
                consult.test_communication()

                print("\n" + "=" * 60)
                print("SUCCESS! ECU IS RESPONDING")
                print("=" * 60)
                break  # Don't try other baudrate
            else:
                print(f"\n[INFO] ECU did not respond at {baudrate} baud")
                print("[INFO] Trying next baudrate...")

        finally:
            consult.disconnect()
    else:
        print("\n" + "=" * 60)
        print("FAILED TO INITIALIZE ECU AT ANY BAUDRATE")
        print("=" * 60)
        print("\nPossible issues:")
        print("  1. Car ignition not ON")
        print("  2. Adapter not connected to car OBD port")
        print("  3. Incorrect pins/wiring")
        print("  4. ECU not compatible with Consult-II")

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
