"""
Experiment 2: Direct Consult-II After Simple Init
==================================================

Skip the Nisscom protocol entirely.
Just do K-line init, then send Consult-II commands directly.
"""

import serial
import time

def simple_k_line_init(port):
    """Simplest possible K-line init"""
    print("\n[INIT] Simple K-line initialization...")

    # Method 1: Slow baudrate toggle
    for baud in [300, 1200, 9600, 38400]:
        print(f"  Baudrate: {baud}")
        ser = serial.Serial(port, baudrate=baud, timeout=0.5)
        ser.dtr = True
        ser.rts = True

        if baud == 300:
            # Send wake-up at slow speed
            ser.write(b'\xFF\xFF\xFF')

        time.sleep(0.1)

        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"    Got: {' '.join([f'{b:02X}' for b in data])}")

        ser.close()
        time.sleep(0.05)

    print("[INIT] Complete")


def send_consult2_command(ser, cmd_bytes):
    """Send Consult-II command"""
    print(f"\n[TX] {' '.join([f'{b:02X}' for b in cmd_bytes])}")

    ser.write(bytes(cmd_bytes))
    ser.flush()
    time.sleep(0.4)

    response = []
    timeout = time.time() + 2.0

    while time.time() < timeout:
        if ser.in_waiting > 0:
            response.extend(ser.read(ser.in_waiting))
            time.sleep(0.05)
        elif len(response) > 0:
            break

    if response:
        print(f"[RX] {' '.join([f'{b:02X}' for b in response])}")
        if response != cmd_bytes:
            print("  >>> NON-ECHO!")
            return response

    return response


def main():
    print("="*70)
    print("EXPERIMENT 2: DIRECT CONSULT-II")
    print("="*70)

    port = 'COM5'

    # Simple K-line init
    simple_k_line_init(port)

    # Connect at standard Consult-II baudrate (9600)
    print("\n[CONNECT] Opening at 9600 baud (Consult-II standard)...")
    ser = serial.Serial(port, baudrate=9600, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.5)

    # Try Consult-II initialization
    print("\n[TEST] Consult-II init: FF FF EF")
    send_consult2_command(ser, [0xFF, 0xFF, 0xEF])

    # Try reading ECU part number
    print("\n[TEST] Consult-II ECU part number: D1")
    send_consult2_command(ser, [0xD1])
    send_consult2_command(ser, [0xF0])  # Terminate

    # Try self-diagnostic
    print("\n[TEST] Consult-II self-diag: D0")
    send_consult2_command(ser, [0xD0])
    send_consult2_command(ser, [0xF0])

    # Now try at 38400
    ser.close()
    print("\n[CONNECT] Trying 38400 baud...")
    ser = serial.Serial(port, baudrate=38400, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.5)

    # Try our protocol
    print("\n[TEST] Our protocol at 38400...")
    send_consult2_command(ser, [0x02, 0x1A, 0x81, 0x9D])

    ser.close()

    print("\n[DONE]")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
