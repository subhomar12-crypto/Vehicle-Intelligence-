"""
Nisscom Direct Communication
=============================

Talk directly to Nisscom device using the captured protocol.
This implementation is based on reverse-engineered protocol from bridge capture.

No Nisscom software required!
"""

import serial
import time
from typing import List, Optional

class NisscomDevice:
    """Direct communication with Nisscom USB adapter"""

    def __init__(self, port='COM5', baudrate=38400):
        """
        Initialize Nisscom device

        Args:
            port: COM port where Nisscom device is connected
            baudrate: Communication speed (captured as 38400)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.debug = True

    def connect(self):
        """Open serial connection to device"""
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)  # Let port stabilize

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

    def _calculate_checksum(self, data: List[int]) -> int:
        """
        Calculate checksum (SUM method)
        Discovered from protocol analysis: checksum = sum(bytes) & 0xFF

        Args:
            data: List of bytes to checksum

        Returns:
            Checksum byte (0-255)
        """
        return sum(data) & 0xFF

    def send_command(self, data: List[int], wait_response=True, timeout=0.5) -> Optional[List[int]]:
        """
        Send command to device and optionally wait for response

        Args:
            data: Command bytes to send
            wait_response: Whether to wait for response
            timeout: How long to wait for response

        Returns:
            Response bytes or None
        """
        if not self.ser or not self.ser.is_open:
            print("[ERROR] Not connected")
            return None

        # Send command
        self.ser.write(bytes(data))
        self.ser.flush()

        if self.debug:
            hex_str = ' '.join([f'{b:02X}' for b in data])
            print(f"[SEND] {hex_str}")

        if not wait_response:
            return None

        # Wait for response
        time.sleep(0.1)  # Give device time to respond

        response = []
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self.ser.in_waiting > 0:
                byte = self.ser.read(1)[0]
                response.append(byte)
                time.sleep(0.01)  # Small delay between bytes
            elif len(response) > 0:
                # Got some data and no more coming
                break

        if self.debug and response:
            hex_str = ' '.join([f'{b:02X}' for b in response])
            print(f"[RECV] {hex_str}")

        return response if response else None

    def initialize(self) -> bool:
        """
        Initialize communication with device using captured sequence:
        1. Send 0x00 (sync/wakeup)
        2. Send 0x81 (init command)
        3. Send 0x10 0xFC 0x81 (handshake part 1)
        4. Send 0x0E (handshake part 2)

        Returns:
            True if initialization appears successful
        """
        print("\n" + "=" * 60)
        print("INITIALIZING NISSCOM DEVICE")
        print("=" * 60)

        # Step 1: Sync/wakeup
        print("\n[INIT] Step 1: Sync")
        resp = self.send_command([0x00])
        if resp and resp == [0x00]:
            print("  >>> Sync OK")
        else:
            print(f"  >>> Unexpected response: {resp}")

        time.sleep(0.1)

        # Step 2: Init command
        print("\n[INIT] Step 2: Init Command")
        resp = self.send_command([0x81])
        if resp and resp == [0x81]:
            print("  >>> Init OK")
        else:
            print(f"  >>> Unexpected response: {resp}")

        time.sleep(0.1)

        # Step 3 & 4: Handshake sequence
        print("\n[INIT] Step 3: Handshake Part 1")
        resp = self.send_command([0x10, 0xFC, 0x81])

        print("\n[INIT] Step 4: Handshake Part 2")
        resp = self.send_command([0x0E])

        # Expected response: 81 10 FC 81 0E
        if resp and len(resp) == 5 and resp == [0x81, 0x10, 0xFC, 0x81, 0x0E]:
            print("  >>> Handshake OK - Device initialized!")
            print("\n" + "=" * 60)
            print("INITIALIZATION SUCCESSFUL")
            print("=" * 60)
            return True
        else:
            print(f"  >>> Unexpected response: {resp}")
            print("\n" + "=" * 60)
            print("INITIALIZATION MAY HAVE FAILED")
            print("=" * 60)
            return False

    def send_type2_command(self, param1: int, param2: int) -> Optional[List[int]]:
        """
        Send Type 2 command (4-byte format)
        Format: [02] [param1] [param2] [checksum]

        Args:
            param1: First parameter
            param2: Second parameter

        Returns:
            Response bytes
        """
        cmd = [0x02, param1, param2]
        checksum = self._calculate_checksum(cmd)
        cmd.append(checksum)

        return self.send_command(cmd)

    def read_register(self, reg: int, addr: int = 0x00, length: int = 0x04, flags: int = 0x01) -> Optional[List[int]]:
        """
        Read register/memory using Type 5 command (7-byte format)
        Format: [05] [22] [reg] [addr] [len] [flags] [checksum]

        This appears to be the main command for reading ECU data.

        Args:
            reg: Register number (0x11, 0x12, 0x13 seen in capture)
            addr: Address offset within register
            length: Number of bytes to read
            flags: Operation flags

        Returns:
            Response bytes
        """
        cmd = [0x05, 0x22, reg, addr, length, flags]
        checksum = self._calculate_checksum(cmd)
        cmd.append(checksum)

        return self.send_command(cmd)

    def test_communication(self):
        """
        Test communication with device by sending captured commands
        """
        print("\n" + "=" * 60)
        print("TESTING COMMUNICATION")
        print("=" * 60)

        # Try some of the commands we saw in the capture

        print("\n[TEST] Type 2 command: 02 1A 81...")
        resp = self.send_type2_command(0x1A, 0x81)
        if resp == [0x02, 0x1A, 0x81, 0x9D]:
            print("  >>> Echo response (device working, car may not be connected)")
        elif resp:
            print(f"  >>> Got response: {resp}")
        else:
            print("  >>> No response")

        print("\n[TEST] Reading register 0x11...")
        resp = self.read_register(0x11, 0x00, 0x04, 0x01)
        if resp == [0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D]:
            print("  >>> Echo response (device working, car may not be connected)")
        elif resp:
            print(f"  >>> Got response: {resp}")
        else:
            print("  >>> No response")

        print("\n[TEST] Reading register 0x13...")
        resp = self.read_register(0x13, 0x01, 0x04, 0x01)
        if resp == [0x05, 0x22, 0x13, 0x01, 0x04, 0x01, 0x40]:
            print("  >>> Echo response (device working, car may not be connected)")
        elif resp:
            print(f"  >>> Got response: {resp}")
        else:
            print("  >>> No response")

        print("\n" + "=" * 60)


def main():
    """Main test program"""

    print("=" * 60)
    print("NISSCOM DIRECT COMMUNICATION TEST")
    print("Based on reverse-engineered protocol")
    print("=" * 60)

    # Create device
    device = NisscomDevice(port='COM5', baudrate=38400)

    # Connect
    if not device.connect():
        print("\n[ERROR] Failed to connect to device")
        print("Make sure:")
        print("  1. Nisscom device is connected to COM5")
        print("  2. No other software is using COM5")
        print("  3. Device drivers are installed")
        return

    try:
        # Initialize
        if device.initialize():
            # Test communication
            device.test_communication()

            print("\n" + "=" * 60)
            print("NEXT STEPS")
            print("=" * 60)
            print("1. If you see echo responses: Device works, but car not connected")
            print("   - Make sure car ignition is ON")
            print("   - Make sure device is connected to car OBD port")
            print("2. If you see different responses: Great! We're talking to the ECU")
            print("   - We can now decode the actual sensor data")
            print("3. If no responses: Check connections and try again")

        else:
            print("\n[WARNING] Initialization may have failed")
            print("Trying test commands anyway...")
            device.test_communication()

    finally:
        # Cleanup
        device.disconnect()

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
