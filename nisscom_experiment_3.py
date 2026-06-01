"""
Experiment 3: Long Delays and Delayed Responses
================================================

Maybe the ECU takes longer to respond than we're waiting.
Try sending commands with VERY long waits.
"""

import serial
import time

def wait_and_read(ser, wait_seconds=3):
    """Wait a long time and read everything"""
    print(f"  [WAIT] Waiting {wait_seconds} seconds for response...")

    all_data = []
    start = time.time()

    while (time.time() - start) < wait_seconds:
        if ser.in_waiting > 0:
            chunk = ser.read(ser.in_waiting)
            all_data.extend(chunk)
            print(f"    [{time.time()-start:.1f}s] Got {len(chunk)} bytes: {' '.join([f'{b:02X}' for b in chunk])}")
            time.sleep(0.1)
        else:
            time.sleep(0.1)

    return all_data


def main():
    print("="*70)
    print("EXPERIMENT 3: LONG DELAYS")
    print("="*70)

    port = 'COM5'

    # Open at 38400
    print("\n[CONNECT] Opening at 38400 baud...")
    ser = serial.Serial(port, baudrate=38400, timeout=5)
    ser.dtr = True
    ser.rts = True

    print("\n[INIT] Sending init sequence with LONG delays...")

    # Clear buffer
    if ser.in_waiting > 0:
        ser.read(ser.in_waiting)

    # Send init with long waits
    commands = [
        [0x81],
        [0x10],
        [0xFC],
        [0x81],
        [0x0E],
    ]

    for cmd in commands:
        print(f"\n[TX] {' '.join([f'{b:02X}' for b in cmd])}")
        ser.write(bytes(cmd))
        ser.flush()

        # Wait a LONG time
        wait_and_read(ser, wait_seconds=2)

    # Now try ECU ID with very long wait
    print("\n\n[TEST] ECU ID command with 5-second wait...")
    print("[TX] 02 1A 81 9D")
    ser.write(b'\x02\x1A\x81\x9D')
    ser.flush()

    wait_and_read(ser, wait_seconds=5)

    # Try sensor read with long wait
    print("\n\n[TEST] Sensor read with 5-second wait...")
    print("[TX] 05 22 11 00 04 01 3D")
    ser.write(b'\x05\x22\x11\x00\x04\x01\x3D')
    ser.flush()

    wait_and_read(ser, wait_seconds=5)

    # Check one more time after everything
    print("\n\n[CHECK] Final check for any delayed data...")
    time.sleep(2)
    if ser.in_waiting > 0:
        final = ser.read(ser.in_waiting)
        print(f"[RX] Delayed data: {' '.join([f'{b:02X}' for b in final])}")
    else:
        print("[INFO] No additional data")

    ser.close()

    print("\n[DONE]")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
