"""
NDS II Final Decoded Protocol
==============================

Based on dnSpy decompilation of GClass7:

method_20(bool) uses EscapeCommFunction:
  - true  -> EscapeCommFunction(handle, 8) = SETBREAK
  - false -> EscapeCommFunction(handle, 9) = CLRBREAK

method_12(bool) uses EscapeCommFunction:
  - true  -> EscapeCommFunction(handle, 5) = SETDTR
  - false -> EscapeCommFunction(handle, 6) = CLRDTR

The init sequence from btnConnect_Click:
1. Set baudrate 10400
2. method_20(true)  -> SETBREAK
3. Delay 25ms
4. method_20(false) -> CLRBREAK
5. Delay 25ms
6. Send init bytes: 0x81, 0x10, 0xFC, 0x81, 0x0E
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
SETRTS = 3
CLRRTS = 4

# Load kernel32
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# EscapeCommFunction prototype
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL


def escape_comm_function(handle, func):
    """Call Windows EscapeCommFunction directly."""
    result = kernel32.EscapeCommFunction(handle, func)
    if not result:
        error = ctypes.get_last_error()
        print(f"    EscapeCommFunction({func}) failed: error {error}")
    return result


def nds_init_sequence(port='COM5'):
    """
    Exact NDS II initialization sequence from decompiled code.
    """
    print("=" * 60)
    print("NDS II FINAL - USING BREAK SIGNAL")
    print("=" * 60)
    print()

    # Open port
    print(f"[1] Opening {port} at 10400 baud...")
    ser = serial.Serial(port, baudrate=10400, timeout=1)

    # Get the Windows handle from pyserial
    handle = ser._port_handle
    print(f"    Handle: {handle}")

    # Reset/clear port (method_35 equivalent)
    print("[2] Clearing port...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)

    # method_12(true/false) - DTR control based on GClass5.bool_15 flag
    # Let's try both patterns
    print("[3] Setting DTR...")
    escape_comm_function(handle, SETDTR)
    time.sleep(0.025)

    # THE KEY: method_20(true) then method_20(false) - BREAK signal!
    print("[4] BREAK signal sequence (method_20)...")
    print("    SETBREAK...")
    escape_comm_function(handle, SETBREAK)
    time.sleep(0.025)  # 25ms as per decompiled code

    print("    CLRBREAK...")
    escape_comm_function(handle, CLRBREAK)
    time.sleep(0.025)

    # Clear any garbage from break
    if ser.in_waiting > 0:
        garbage = ser.read(ser.in_waiting)
        print(f"    Cleared {len(garbage)} bytes after BREAK")

    # Send init bytes with 10ms delays
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    print(f"[5] Sending init: {' '.join([f'{b:02X}' for b in init_bytes])}")

    for byte in init_bytes:
        ser.write(bytes([byte]))
        ser.flush()
        time.sleep(0.010)  # 10ms inter-byte delay

        # Check for echo
        time.sleep(0.010)
        if ser.in_waiting > 0:
            rx = list(ser.read(ser.in_waiting))
            print(f"    TX: {byte:02X} -> RX: {' '.join([f'{b:02X}' for b in rx])}")
        else:
            print(f"    TX: {byte:02X}")

    # Wait for ECU response
    print()
    print("[6] Waiting for ECU response...")
    time.sleep(0.5)

    response = []
    for _ in range(5):
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            response.extend(resp)
        time.sleep(0.1)

    if response:
        print(f"    RX: {' '.join([f'{b:02X}' for b in response])}")

        if 0x83 in response:
            print()
            print("*" * 60)
            print("*** ECU SESSION ESTABLISHED! ***")
            print("*" * 60)
            return ser, True
        elif response == init_bytes:
            print("    (Echo only)")
    else:
        print("    No response")

    return ser, False


def test_longer_break(port='COM5'):
    """Try longer BREAK duration."""
    print()
    print("=" * 60)
    print("ALTERNATIVE: LONGER BREAK (200ms)")
    print("=" * 60)
    print()

    ser = serial.Serial(port, baudrate=10400, timeout=1)
    handle = ser._port_handle

    # Longer break
    print("[1] Long BREAK (200ms)...")
    escape_comm_function(handle, SETBREAK)
    time.sleep(0.200)
    escape_comm_function(handle, CLRBREAK)
    time.sleep(0.050)

    ser.reset_input_buffer()

    # Send init
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    print(f"[2] Sending: {' '.join([f'{b:02X}' for b in init_bytes])}")

    for byte in init_bytes:
        ser.write(bytes([byte]))
        time.sleep(0.010)

    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"    RX: {' '.join([f'{b:02X}' for b in resp])}")
        if len(resp) > 5 and 0x83 in resp:
            print("*** SUCCESS! ***")
            return ser, True

    ser.close()
    return None, False


def test_dtr_break_combo(port='COM5'):
    """Try DTR + BREAK combination."""
    print()
    print("=" * 60)
    print("ALTERNATIVE: DTR + BREAK COMBO")
    print("=" * 60)
    print()

    ser = serial.Serial(port, baudrate=10400, timeout=1)
    handle = ser._port_handle

    # Clear DTR first
    print("[1] Clear DTR, then set...")
    escape_comm_function(handle, CLRDTR)
    time.sleep(0.050)
    escape_comm_function(handle, SETDTR)
    time.sleep(0.050)

    # BREAK sequence
    print("[2] BREAK sequence...")
    escape_comm_function(handle, SETBREAK)
    time.sleep(0.025)
    escape_comm_function(handle, CLRBREAK)
    time.sleep(0.025)

    ser.reset_input_buffer()

    # Send init
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    print(f"[3] Sending: {' '.join([f'{b:02X}' for b in init_bytes])}")

    for byte in init_bytes:
        ser.write(bytes([byte]))
        time.sleep(0.010)

    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"    RX: {' '.join([f'{b:02X}' for b in resp])}")
        if len(resp) > 5 and 0x83 in resp:
            print("*** SUCCESS! ***")
            return ser, True

    ser.close()
    return None, False


def main():
    port = 'COM5'

    print(f"Port: {port}")
    print()

    # Try main sequence
    ser, success = nds_init_sequence(port)

    if not success:
        if ser:
            ser.close()

        # Try longer break
        ser, success = test_longer_break(port)

        if not success:
            # Try DTR + BREAK combo
            ser, success = test_dtr_break_combo(port)

    if success and ser:
        print()
        print("=" * 60)
        print("TESTING ECU COMMUNICATION")
        print("=" * 60)
        print()

        # Send sensor read command
        cmd = [0x04, 0x21, 0x81, 0x04, 0x01, 0xAB]
        print(f"Sending: {' '.join([f'{b:02X}' for b in cmd])}")
        ser.write(bytes(cmd))
        time.sleep(0.5)

        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"Response: {' '.join([f'{b:02X}' for b in resp])}")

            if len(resp) > len(cmd):
                print()
                print("*** GOT ECU DATA! ***")

        ser.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
