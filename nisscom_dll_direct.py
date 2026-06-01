"""
Nisscom Device - Direct DLL Access
===================================

Call the mts.dll functions directly using ctypes.
This uses the SAME library that Nisscom software uses!

This is the breakthrough - we use their code, not reverse engineer it!
"""

import ctypes
import time
import os

class NisscomDLL:
    """Direct access to MTS.DLL functions"""

    def __init__(self):
        self.dll = None
        self.port_handle = None

    def load_dll(self):
        """Load the MTS.DLL"""
        dll_path = r"C:\Program Files (x86)\Nissan Data Scan\Nissan DataScan II 2.53\mts.dll"

        if not os.path.exists(dll_path):
            print(f"[ERROR] DLL not found: {dll_path}")
            return False

        try:
            self.dll = ctypes.CDLL(dll_path)
            print(f"[DLL] Loaded: {dll_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load DLL: {e}")
            return False

    def mts_initialize(self):
        """Call mtsInitialize() function"""
        print("\n[CALL] mtsInitialize()...")

        try:
            # mtsInitialize() likely returns int (0=success)
            result = self.dll.mtsInitialize()
            print(f"[RESULT] mtsInitialize returned: {result}")
            return result == 0

        except Exception as e:
            print(f"[ERROR] mtsInitialize failed: {e}")
            return False

    def mts_get_port_list(self):
        """Call mtsGetPortList() to get available ports"""
        print("\n[CALL] mtsGetPortList()...")

        try:
            # This might return a string or fill a buffer
            # Try different approaches

            # Approach 1: Return string pointer
            self.dll.mtsGetPortList.restype = ctypes.c_char_p
            result = self.dll.mtsGetPortList()

            if result:
                ports = result.decode('ascii')
                print(f"[RESULT] Ports: {ports}")
                return ports
            else:
                print("[RESULT] No ports or need buffer")

        except Exception as e:
            print(f"[ERROR] mtsGetPortList failed: {e}")

        return None

    def mts_send_serial(self, data):
        """Send data via mtsSendSerial()"""
        print(f"\n[CALL] mtsSendSerial({' '.join([f'{b:02X}' for b in data])})...")

        try:
            # Convert to ctypes array
            data_array = (ctypes.c_ubyte * len(data))(*data)

            # Call function
            result = self.dll.mtsSendSerial(data_array, len(data))
            print(f"[RESULT] mtsSendSerial returned: {result}")

            return result

        except Exception as e:
            print(f"[ERROR] mtsSendSerial failed: {e}")
            return -1

    def mts_read_serial(self, max_bytes=256):
        """Read data via mtsReadSerial()"""
        print(f"\n[CALL] mtsReadSerial (max {max_bytes} bytes)...")

        try:
            # Create buffer
            buffer = (ctypes.c_ubyte * max_bytes)()
            bytes_read = ctypes.c_int(0)

            # Call function (guessing signature)
            result = self.dll.mtsReadSerial(buffer, max_bytes, ctypes.byref(bytes_read))

            if result == 0 and bytes_read.value > 0:
                data = list(buffer[:bytes_read.value])
                print(f"[RESULT] Read {bytes_read.value} bytes: {' '.join([f'{b:02X}' for b in data])}")
                return data

            print(f"[RESULT] mtsReadSerial returned: {result}, bytes: {bytes_read.value}")

        except Exception as e:
            print(f"[ERROR] mtsReadSerial failed: {e}")

        return []

    def mts_cleanup(self):
        """Call mtsCleanup()"""
        print("\n[CALL] mtsCleanup()...")

        try:
            self.dll.mtsCleanup()
            print("[RESULT] Cleanup complete")
        except Exception as e:
            print(f"[ERROR] mtsCleanup failed: {e}")

    def test_communication(self):
        """Test basic communication"""
        print("\n" + "="*70)
        print("TESTING COMMUNICATION VIA DLL")
        print("="*70)

        # Try sending init sequence
        print("\n[TEST] Sending init sequence...")
        self.mts_send_serial([0x81])
        time.sleep(0.1)

        self.mts_send_serial([0x10])
        time.sleep(0.1)

        self.mts_send_serial([0xFC])
        time.sleep(0.1)

        self.mts_send_serial([0x81])
        time.sleep(0.1)

        self.mts_send_serial([0x0E])
        time.sleep(0.2)

        # Try reading response
        response = self.mts_read_serial()

        # Try ECU ID command
        print("\n[TEST] Sending ECU ID command...")
        self.mts_send_serial([0x02, 0x1A, 0x81, 0x9D])
        time.sleep(0.3)

        response = self.mts_read_serial()

        # Try sensor read
        print("\n[TEST] Sending sensor read...")
        self.mts_send_serial([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D])
        time.sleep(0.3)

        response = self.mts_read_serial()


def main():
    print("="*70)
    print("NISSCOM - DIRECT DLL ACCESS")
    print("Using the actual Nisscom library!")
    print("="*70)

    device = NisscomDLL()

    # Load DLL
    if not device.load_dll():
        print("\n[ERROR] Could not load DLL")
        input("Press Enter to exit...")
        return

    # Initialize
    if not device.mts_initialize():
        print("\n[WARNING] mtsInitialize returned error, but continuing...")

    # Get port list
    ports = device.mts_get_port_list()

    # Test communication
    device.test_communication()

    # Cleanup
    device.mts_cleanup()

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
