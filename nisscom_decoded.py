"""
Nisscom Decoded Protocol
========================

Based on USB capture analysis - exact FTDI initialization sequence.

The device has an internal MCU that requires:
1. Specific baudrate sequence (38400 -> 9600 -> 10400)
2. DTR/RTS toggling pattern
3. Then CONSULT-II init bytes

This script replicates the exact sequence from NDS II software.
"""

import serial
import serial.tools.list_ports
import time

def find_nisscom_port():
    """Find Nisscom device COM port"""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if '0403' in p.hwid.lower() or 'ftdi' in p.description.lower():
            return p.device
    return 'COM5'  # Default


def exact_init_sequence(port='COM5'):
    """
    Replicate EXACT sequence from USB capture.

    Captured FTDI command sequence:
    1. Reset device
    2. Set 8N1
    3. DTR=1, RTS=0
    4. DTR=0, RTS=1
    5. Flow control = none
    6. Baudrate = 38400
    7. Baudrate = 9600
    8. DTR toggling
    9. Baudrate = 10400
    10. More DTR/RTS toggling
    11. Send init bytes
    """
    print("=" * 70)
    print("NISSCOM DECODED INITIALIZATION")
    print("Based on USB capture analysis")
    print("=" * 70)
    print()

    # Phase 1: Initial setup at 38400 baud (as seen in capture)
    print("[PHASE 1] Initial setup at 38400 baud")
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 38400
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = 0.5
    ser.open()

    # Toggle DTR/RTS as seen in capture
    print("  DTR=1, RTS=0")
    ser.dtr = True
    ser.rts = False
    time.sleep(0.05)

    print("  DTR=0, RTS=1")
    ser.dtr = False
    ser.rts = True
    time.sleep(0.05)

    ser.close()
    time.sleep(0.02)

    # Phase 2: Switch to 9600 baud
    print("[PHASE 2] Switch to 9600 baud")
    ser = serial.Serial(port, baudrate=9600, timeout=0.5)
    ser.dtr = False
    ser.rts = True
    time.sleep(0.05)
    ser.dtr = True
    ser.rts = False
    time.sleep(0.05)
    ser.close()
    time.sleep(0.02)

    # Phase 3: Switch to 10400 baud (K-line standard)
    print("[PHASE 3] Switch to 10400 baud (K-line)")
    ser = serial.Serial(port, baudrate=10400, timeout=1)

    # DTR/RTS toggle sequence from capture
    print("  DTR/RTS toggle sequence...")
    ser.dtr = False
    ser.rts = False
    time.sleep(0.02)
    ser.dtr = False
    ser.rts = False
    time.sleep(0.02)
    ser.dtr = True
    ser.rts = False
    time.sleep(0.05)

    # Clear any garbage
    if ser.in_waiting > 0:
        garbage = ser.read(ser.in_waiting)
        print(f"  Cleared {len(garbage)} bytes")

    # Phase 4: Send CONSULT-II init bytes
    print("[PHASE 4] Sending CONSULT-II init: 81 10 FC 81 0E")
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]

    for b in init_bytes:
        print(f"  TX: {b:02X}")
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(0.05)  # Inter-byte delay

        # Read any echo/response
        time.sleep(0.05)
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"  RX: {' '.join([f'{x:02X}' for x in resp])}")

    # Wait for ECU init response (83 FC 10 C1 ...)
    print()
    print("[WAIT] Waiting for ECU response...")
    time.sleep(0.5)

    response = []
    for _ in range(5):
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            response.extend(resp)
        time.sleep(0.1)

    if response:
        print(f"  RX: {' '.join([f'{b:02X}' for b in response])}")

        if 0x83 in response:
            print()
            print("*** ECU SESSION ESTABLISHED! ***")
            return ser, True
        else:
            # Check if it's just echo
            if response == init_bytes:
                print("  (Echo only - MCU not activated)")
            else:
                print("  (Unknown response)")
    else:
        print("  No response received")

    return ser, False


def test_with_break_signal(port='COM5'):
    """Try using BREAK signal as seen in capture (0x4008 data config)"""
    print()
    print("=" * 70)
    print("ALTERNATIVE: Using BREAK signal")
    print("=" * 70)
    print()

    ser = serial.Serial(port, baudrate=10400, timeout=1)

    # Send BREAK (might wake MCU)
    print("[BREAK] Sending 300ms break signal...")
    ser.send_break(duration=0.3)
    time.sleep(0.2)

    # Clear buffer
    if ser.in_waiting > 0:
        ser.read(ser.in_waiting)

    # Send init
    print("[INIT] Sending: 81 10 FC 81 0E")
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.05)

    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  RX: {' '.join([f'{b:02X}' for b in resp])}")

        if 0x83 in resp:
            print("*** SUCCESS WITH BREAK! ***")
            return ser, True

    ser.close()
    return None, False


def send_ecu_command(ser, cmd_bytes):
    """Send command and read response"""
    cmd_hex = ' '.join([f'{b:02X}' for b in cmd_bytes])
    print(f"[TX] {cmd_hex}")

    ser.write(bytes(cmd_bytes))
    ser.flush()
    time.sleep(0.3)

    response = []
    for _ in range(3):
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            response.extend(resp)
        time.sleep(0.1)

    if response:
        resp_hex = ' '.join([f'{b:02X}' for b in response])
        print(f"[RX] {resp_hex}")

        # Check if response is different from command (not just echo)
        if response != list(cmd_bytes):
            if len(response) > len(cmd_bytes):
                print("  *** GOT ECU RESPONSE! ***")
            return response

    return None


def main():
    port = find_nisscom_port()
    print(f"Using port: {port}")
    print()

    # Try exact decoded sequence
    ser, success = exact_init_sequence(port)

    if success:
        print()
        print("=" * 70)
        print("TESTING ECU COMMANDS")
        print("=" * 70)
        print()

        # ECU ID request: 02 1A 81 CS
        print("[TEST 1] ECU ID request")
        cmd = [0x02, 0x1A, 0x81]
        cmd.append(sum(cmd) & 0xFF)  # Checksum
        send_ecu_command(ser, cmd)
        print()

        # Sensor read: 05 22 11 00 04 01 CS
        print("[TEST 2] Sensor data request")
        cmd = [0x05, 0x22, 0x11, 0x00, 0x04, 0x01]
        cmd.append(sum(cmd) & 0xFF)
        send_ecu_command(ser, cmd)

        ser.close()
    else:
        if ser:
            ser.close()

        # Try alternative with BREAK
        ser, success = test_with_break_signal(port)
        if ser:
            ser.close()

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
