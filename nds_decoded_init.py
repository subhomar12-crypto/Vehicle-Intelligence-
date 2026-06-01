"""
NDS II Decoded Initialization Sequence
=======================================

Based on IL disassembly of NDS II 2_53.exe btnConnect_Click method.

The sequence from the decompiled code:
1. Set baudrate to 10400
2. Call method_35() - port init
3. Toggle control signal (method_20)
4. Send init bytes with 10ms delays
5. Send checksum

Init bytes: 0x81, 0x10, 0xFC, 0x81, checksum
ECMid = 0x10 (16 decimal)
TesterId = 0xFC (252 decimal)
Checksum = (0x81 + 0x10 + 0xFC + 0x81) & 0xFF = 0x0E
"""

import serial
import time
import sys


def nds_init_sequence(port='COM5'):
    """Replicate exact NDS II initialization sequence."""

    print("=" * 60)
    print("NDS II DECODED INITIALIZATION")
    print("=" * 60)
    print()

    # Constants from decompiled code
    ECM_ID = 0x10      # "16" in decimal
    TESTER_ID = 0xFC   # "252" in decimal
    BAUDRATE = 10400   # 0x28A0

    # Calculate checksum: (0x81 + ECM_ID + TESTER_ID + 0x81) & 0xFF
    checksum = (0x81 + ECM_ID + TESTER_ID + 0x81) & 0xFF
    print(f"ECM ID: 0x{ECM_ID:02X}")
    print(f"Tester ID: 0x{TESTER_ID:02X}")
    print(f"Checksum: 0x{checksum:02X}")
    print()

    # Init sequence bytes
    init_bytes = [0x81, ECM_ID, TESTER_ID, 0x81, checksum]
    print(f"Init sequence: {' '.join([f'{b:02X}' for b in init_bytes])}")
    print()

    # Open serial port
    print(f"[1] Opening {port} at {BAUDRATE} baud...")
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = BAUDRATE
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = 1
    ser.open()

    # Method 35 equivalent - reset/clear
    print("[2] Resetting port (method_35)...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)

    # Method 20 toggle - likely DTR control for K-line wake
    # The IL shows: method_20(true), delay 25ms, method_20(false), delay 25ms
    print("[3] Toggle control signal (method_20)...")

    # Try DTR toggle (common K-line wake method)
    ser.dtr = True
    time.sleep(0.025)  # 25ms as per IL code
    ser.dtr = False
    time.sleep(0.025)

    # Clear any garbage
    if ser.in_waiting > 0:
        garbage = ser.read(ser.in_waiting)
        print(f"    Cleared {len(garbage)} bytes")

    # Send init bytes with 10ms delays (as per IL: ldc.r4 10. call smethod_6)
    print("[4] Sending init sequence...")

    for i, byte in enumerate(init_bytes):
        print(f"    TX: 0x{byte:02X}", end="")
        ser.write(bytes([byte]))
        ser.flush()
        time.sleep(0.010)  # 10ms inter-byte delay

        # Check for immediate echo
        time.sleep(0.010)
        if ser.in_waiting > 0:
            rx = list(ser.read(ser.in_waiting))
            print(f" -> RX: {' '.join([f'{b:02X}' for b in rx])}")
        else:
            print()

    # Wait for ECU response
    print()
    print("[5] Waiting for ECU response (500ms)...")
    time.sleep(0.5)

    response = []
    for _ in range(5):
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            response.extend(resp)
        time.sleep(0.1)

    if response:
        print(f"    RX: {' '.join([f'{b:02X}' for b in response])}")

        # Check for valid ECU response (should start with 0x83 for positive response)
        if 0x83 in response:
            print()
            print("*" * 60)
            print("*** ECU SESSION ESTABLISHED! ***")
            print("*" * 60)
            return ser, True
        elif response == init_bytes:
            print("    (Echo only - MCU not forwarding)")
    else:
        print("    No response")

    return ser, False


def test_alternative_toggle(port='COM5'):
    """Try alternative control signal patterns."""

    print()
    print("=" * 60)
    print("ALTERNATIVE: RTS TOGGLE")
    print("=" * 60)
    print()

    ser = serial.Serial(port, baudrate=10400, timeout=1)

    # Try RTS instead of DTR
    print("[1] RTS toggle sequence...")
    ser.rts = False
    time.sleep(0.025)
    ser.rts = True
    time.sleep(0.025)
    ser.rts = False
    time.sleep(0.025)

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


def test_break_signal(port='COM5'):
    """Try BREAK signal for K-line wake."""

    print()
    print("=" * 60)
    print("ALTERNATIVE: BREAK SIGNAL")
    print("=" * 60)
    print()

    ser = serial.Serial(port, baudrate=10400, timeout=1)

    # Send break for 25ms
    print("[1] Sending 25ms BREAK...")
    ser.break_condition = True
    time.sleep(0.025)
    ser.break_condition = False
    time.sleep(0.025)

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


def main():
    port = 'COM5'
    if len(sys.argv) > 1:
        port = sys.argv[1]

    print(f"Using port: {port}")
    print()

    # Try main sequence
    ser, success = nds_init_sequence(port)

    if not success:
        if ser:
            ser.close()

        # Try RTS toggle
        ser, success = test_alternative_toggle(port)

        if not success:
            # Try BREAK signal
            ser, success = test_break_signal(port)

    if success and ser:
        print()
        print("Testing ECU command...")

        # Try sensor read command
        cmd = [0x04, 0x21, 0x81, 0x04, 0x01, 0xAB]
        print(f"TX: {' '.join([f'{b:02X}' for b in cmd])}")
        ser.write(bytes(cmd))
        time.sleep(0.5)

        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"RX: {' '.join([f'{b:02X}' for b in resp])}")

        ser.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
