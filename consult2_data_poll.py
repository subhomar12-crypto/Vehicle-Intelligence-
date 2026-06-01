"""
CONSULT-II Live Data Polling via Service 0xA0
==============================================

Reverse engineered from NDS II 2_53.exe.

Discovery:
- Service 0xA0 is the Nissan-proprietary data read service
- Format: [02] [A0] [PARAM] [CHECKSUM]
- Positive response: [LEN] [E0] [DATA...] [CHECKSUM]
- NRC 0x78 = response pending (wait longer)
- AC 81 format from decompilation is internal to NDS II, NOT sent to ECU

Requires BREAK signal init (EscapeCommFunction 8/9) to activate Nisscom MCU.
"""

import serial
import time
import ctypes
from ctypes import wintypes

# Windows API constants
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL


def hexdump(data):
    if isinstance(data, (bytes, list)):
        return ' '.join(f'{b:02X}' for b in data)
    return ''


class Consult2Adapter:
    """CONSULT-II adapter for Nisscom USB device."""

    def __init__(self, port='COM5'):
        self.port = port
        self.ser = None
        self.handle = None
        self.connected = False

    def _escape_comm(self, func):
        if self.handle:
            return kernel32.EscapeCommFunction(self.handle, func)
        return False

    def _safe_read(self):
        """Read available bytes with error handling."""
        try:
            if self.ser and self.ser.in_waiting > 0:
                return list(self.ser.read(self.ser.in_waiting))
        except Exception:
            pass
        return []

    def _read_response(self, wait=0.3, loops=10):
        """Read response with configurable timing."""
        time.sleep(wait)
        data = []
        for _ in range(loops):
            data.extend(self._safe_read())
            time.sleep(0.05)
        return data

    def connect(self):
        """Initialize connection to ECU via BREAK signal."""
        print(f"[INIT] Opening {self.port} at 10400 baud...")

        self.ser = serial.Serial(self.port, baudrate=10400, timeout=1)
        self.handle = self.ser._port_handle

        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception:
            pass
        time.sleep(0.05)

        # BREAK activation sequence
        print("[INIT] Activating MCU (BREAK signal)...")
        self._escape_comm(SETDTR)
        time.sleep(0.025)
        self._escape_comm(SETBREAK)
        time.sleep(0.025)
        self._escape_comm(CLRBREAK)
        time.sleep(0.025)

        # Clear junk from BREAK
        self._safe_read()

        # Send KWP2000 StartCommunication
        init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
        print(f"[INIT] TX: {hexdump(init_bytes)}")
        for b in init_bytes:
            self.ser.write(bytes([b]))
            time.sleep(0.010)

        resp = self._read_response(0.5, 12)
        print(f"[INIT] RX: {hexdump(resp)}")

        if 0xC1 in resp:
            self.connected = True
            print("[INIT] *** ECU SESSION ACTIVE ***")
            return True
        else:
            print("[INIT] FAILED - no ECU response")
            return False

    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.handle = None
            self.connected = False
            print("[DONE] Disconnected.")

    def send_a0(self, param, wait=0.3):
        """
        Send service 0xA0 request with a single parameter byte.

        Frame: [02] [A0] [PARAM] [CHECKSUM]
        Returns: (status, data_bytes)
            status: 'positive', 'pending', 'negative', 'echo_only'
            data_bytes: list of data bytes (empty if not positive)
        """
        frame = [0x02, 0xA0, param]
        frame.append(sum(frame) & 0xFF)

        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

        self.ser.write(bytes(frame))
        self.ser.flush()

        resp = self._read_response(wait, 8)
        extra = resp[len(frame):]  # Strip echo

        # Handle NRC 0x78 (response pending) - wait for final answer
        if extra and len(extra) >= 4 and extra[1] == 0x7F and extra[3] == 0x78:
            more = self._read_response(0.8, 15)
            extra = extra + more

        if not extra:
            return 'echo_only', []

        # Look for positive response (0xE0 = 0xA0 + 0x40)
        for i in range(len(extra)):
            if extra[i] == 0xE0:
                after = extra[i + 1:]
                data = after[:-1] if len(after) > 1 else after
                return 'positive', data

        # Check for negative response
        if len(extra) >= 4 and extra[1] == 0x7F:
            err = extra[3]
            if err == 0x78:
                return 'pending', []
            return 'negative', [err]

        return 'unknown', extra

    def scan_service_a0(self, start=0x00, end=0x20, verbose=True):
        """
        Scan service 0xA0 parameters to find valid sensor addresses.

        Returns dict: {param: data_bytes}
        """
        if not self.connected:
            raise Exception("Not connected to ECU")

        results = {}
        print(f"Scanning 0xA0 params 0x{start:02X}-0x{end:02X}...")
        print("-" * 55)

        for param in range(start, end + 1):
            status, data = self.send_a0(param, wait=0.25)

            if status == 'positive':
                results[param] = data
                if verbose:
                    print(f"  0x{param:02X} ({param:3d}): OK   data={hexdump(data)}  dec={list(data)}")
            elif status == 'pending':
                if verbose:
                    print(f"  0x{param:02X} ({param:3d}): PENDING (ECU busy)")
            elif verbose and status == 'negative':
                err = data[0] if data else 0
                # Only show non-standard errors
                if err not in (0x12, 0x31):
                    print(f"  0x{param:02X} ({param:3d}): NRC 0x{err:02X}")

            time.sleep(0.1)

        print("-" * 55)
        print(f"Found {len(results)} valid parameters")
        return results

    def read_param_repeated(self, param, count=5, interval=0.3):
        """Read a parameter multiple times to detect changing values."""
        readings = []
        for _ in range(count):
            status, data = self.send_a0(param, wait=0.25)
            if status == 'positive':
                readings.append(list(data))
            time.sleep(interval)
        return readings

    def identify_sensors(self, valid_params):
        """
        Read valid parameters multiple times to identify sensor types.
        Changing values = live sensor data.
        Static values = configuration/ID data.
        """
        if not valid_params:
            print("No valid parameters to test")
            return

        print()
        print("=" * 55)
        print("IDENTIFYING SENSORS (5 reads each)")
        print("=" * 55)

        for param in sorted(valid_params.keys()):
            readings = self.read_param_repeated(param, 5, 0.3)
            if not readings:
                print(f"  0x{param:02X}: no data")
                continue

            unique = len(set(str(r) for r in readings))
            changing = unique > 1

            # Calculate values assuming different scaling
            sample = readings[-1]
            interpretations = []
            if len(sample) == 1:
                v = sample[0]
                interpretations.append(f"raw={v}")
                interpretations.append(f"temp={v-50}C")
                interpretations.append(f"volt={v*0.08:.1f}V")
            elif len(sample) >= 2:
                raw16 = sample[0] * 256 + sample[1]
                interpretations.append(f"raw16={raw16}")
                interpretations.append(f"rpm={raw16*12.5:.0f}")
                interpretations.append(f"volt={raw16*0.005:.3f}V")

            tag = "*** LIVE ***" if changing else "static"
            print(f"  0x{param:02X}: [{tag}] readings={readings}  ({', '.join(interpretations)})")

        print()


def main():
    print()
    print("=" * 60)
    print("CONSULT-II DATA POLL - SERVICE 0xA0")
    print("Nisscom USB -> ECU (KWP2000)")
    print("=" * 60)
    print()

    adapter = Consult2Adapter('COM5')

    try:
        if not adapter.connect():
            print()
            print("Could not connect. Check:")
            print("  1. Ignition is ON")
            print("  2. Nisscom USB is plugged in")
            print("  3. COM5 is the correct port")
            return

        print()

        # Phase 1: Scan for valid parameters
        valid = adapter.scan_service_a0(0x00, 0x20)

        # Phase 2: If we found params, extend scan
        if valid:
            valid2 = adapter.scan_service_a0(0x21, 0x40, verbose=True)
            valid.update(valid2)

        # Phase 3: Identify live vs static sensors
        if valid:
            adapter.identify_sensors(valid)
        else:
            print()
            print("No valid 0xA0 parameters found.")
            print("Trying broader scan 0x00-0xFF...")
            valid = adapter.scan_service_a0(0x00, 0xFF)
            if valid:
                adapter.identify_sensors(valid)

        # Phase 4: Quick ECU ID confirmation
        print("=" * 55)
        print("ECU IDENTIFICATION (service 0x1A)")
        print("=" * 55)
        try:
            adapter.ser.reset_input_buffer()
        except Exception:
            pass
        frame = bytes([0x02, 0x1A, 0x81, 0x9D])
        adapter.ser.write(frame)
        adapter.ser.flush()
        resp = adapter._read_response(0.5, 10)
        extra = resp[4:]
        if extra and len(extra) > 2 and extra[1] == 0x5A:
            ecu_id = ''.join(chr(b) if 32 <= b < 127 else '.' for b in extra[2:-1])
            print(f"  ECU ID: {ecu_id}")
            print(f"  Raw: {hexdump(extra)}")
        print()

    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
