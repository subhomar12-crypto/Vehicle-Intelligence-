"""
Nisscom DLL - Improved Version
===============================

Try different function signatures and parameters.
"""

import ctypes
import time
import os

class NisscomDLL:
    """Improved DLL access"""

    def __init__(self):
        self.dll = None

    def load_dll(self):
        """Load MTS.DLL"""
        dll_path = r"C:\Program Files (x86)\Nissan Data Scan\Nissan DataScan II 2.53\mts.dll"

        try:
            self.dll = ctypes.CDLL(dll_path)
            print(f"[DLL] Loaded: {dll_path}")

            # Set return types for functions
            self.dll.mtsInitialize.restype = ctypes.c_int
            self.dll.mtsCleanup.restype = None
            self.dll.mtsSendSerial.restype = ctypes.c_int
            self.dll.mtsReadSerial.restype = ctypes.c_int

            return True
        except Exception as e:
            print(f"[ERROR] Failed to load DLL: {e}")
            return False

    def try_initialize_with_port(self, port_num=5):
        """Try mtsInitialize with COM port parameter"""
        print(f"\n[TRY] mtsInitialize with port COM{port_num}...")

        try:
            # Try with integer parameter
            result = self.dll.mtsInitialize(port_num)
            print(f"[RESULT] Returned: {result}")
            return result

        except Exception as e:
            print(f"[ERROR] {e}")

        try:
            # Try with string parameter
            port_str = f"COM{port_num}".encode('ascii')
            result = self.dll.mtsInitialize(port_str)
            print(f"[RESULT] Returned: {result}")
            return result

        except Exception as e:
            print(f"[ERROR] {e}")

        return -1

    def try_initialize_no_params(self):
        """Try mtsInitialize with no parameters"""
        print(f"\n[TRY] mtsInitialize with no parameters...")

        try:
            result = self.dll.mtsInitialize()
            print(f"[RESULT] Returned: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] {e}")
            return -1

    def open_com_port_windows(self, port_num=5):
        """Try opening COM port with Windows API first"""
        print(f"\n[TRY] Opening COM{port_num} with Windows CreateFile...")

        try:
            # Use Windows kernel32.dll to open COM port
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            OPEN_EXISTING = 3

            port_name = f"\\\\.\\COM{port_num}".encode('ascii')

            handle = kernel32.CreateFileA(
                port_name,
                GENERIC_READ | GENERIC_WRITE,
                0,  # No sharing
                None,  # No security
                OPEN_EXISTING,
                0,  # No flags
                None  # No template
            )

            if handle == -1:
                print(f"[ERROR] CreateFile failed")
                return None

            print(f"[SUCCESS] Port opened, handle: {handle}")
            return handle

        except Exception as e:
            print(f"[ERROR] {e}")
            return None

    def test_all_approaches(self):
        """Try every possible way to initialize"""
        print("\n" + "="*70)
        print("TRYING ALL INITIALIZATION APPROACHES")
        print("="*70)

        # Approach 1: No params
        result = self.try_initialize_no_params()
        if result == 0:
            print("\n*** SUCCESS with no params! ***")
            return True

        # Approach 2: COM port number
        for port in [5, 4, 3]:
            result = self.try_initialize_with_port(port)
            if result == 0:
                print(f"\n*** SUCCESS with COM{port}! ***")
                return True

        # Approach 3: Open port with Windows API first
        handle = self.open_com_port_windows(5)
        if handle:
            print("\n[TRY] mtsInitialize after Windows open...")
            result = self.try_initialize_no_params()
            if result == 0:
                print("\n*** SUCCESS after Windows open! ***")
                return True

        print("\n[INFO] All initialization attempts returned errors")
        print("[INFO] But DLL might still work - trying communication anyway...")
        return False

    def send_and_read(self, data):
        """Send data and try to read response"""
        print(f"\n[TX] {' '.join([f'{b:02X}' for b in data])}")

        # Send
        data_array = (ctypes.c_ubyte * len(data))(*data)
        send_result = self.dll.mtsSendSerial(data_array, len(data))
        print(f"  Send result: {send_result}")

        time.sleep(0.5)

        # Try to read
        buffer = (ctypes.c_ubyte * 256)()
        bytes_read = ctypes.c_int(0)

        read_result = self.dll.mtsReadSerial(buffer, 256, ctypes.byref(bytes_read))

        if bytes_read.value > 0:
            data = list(buffer[:bytes_read.value])
            print(f"[RX] {' '.join([f'{b:02X}' for b in data])}")
            return data

        print(f"  Read result: {read_result}, bytes: {bytes_read.value}")
        return []

    def test_communication(self):
        """Test sending commands"""
        print("\n" + "="*70)
        print("TESTING COMMUNICATION")
        print("="*70)

        # Init sequence
        print("\n[TEST] Init sequence...")
        self.send_and_read([0x81])
        self.send_and_read([0x10])
        self.send_and_read([0xFC])
        self.send_and_read([0x81])
        self.send_and_read([0x0E])

        # ECU ID
        print("\n[TEST] ECU ID...")
        self.send_and_read([0x02, 0x1A, 0x81, 0x9D])

        # Sensor
        print("\n[TEST] Sensor read...")
        self.send_and_read([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D])


def main():
    print("="*70)
    print("NISSCOM DLL - IMPROVED VERSION")
    print("="*70)

    device = NisscomDLL()

    if not device.load_dll():
        print("[ERROR] Could not load DLL")
        input("Press Enter...")
        return

    # Try all initialization methods
    device.test_all_approaches()

    # Test communication anyway (might work even if init failed)
    device.test_communication()

    # Cleanup
    try:
        device.dll.mtsCleanup()
    except:
        pass

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
