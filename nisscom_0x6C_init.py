"""
Nisscom 0x6C Init Test
======================

Use the 0x6C address that showed a response in experiment 1.
Implement proper K-line 5-baud initialization.
"""

import serial
import time

def five_baud_init(port, address=0x6C):
    """Proper 5-baud K-line init with address 0x6C"""
    print(f"\n[5-BAUD INIT] Using address 0x{address:02X}")

    # 5-baud init: Each bit is 200ms
    # But we'll use 360 baud as approximation
    ser = serial.Serial(port, baudrate=360, timeout=2)
    ser.dtr = True
    ser.rts = False

    print(f"[TX] Address byte: 0x{address:02X}")
    ser.write(bytes([address]))
    time.sleep(0.4)

    # ECU should respond with:
    # - 0x55 (sync byte)
    # - Key bytes (varies by ECU)
    response = []
    if ser.in_waiting > 0:
        response = list(ser.read(ser.in_waiting))
        print(f"[RX] {' '.join([f'{b:02X}' for b in response])}")

    ser.close()
    time.sleep(0.2)

    return response


def try_communication_after_init(port):
    """Try commands after successful init"""
    print("\n[COMM] Switching to 38400 baud for communication...")

    ser = serial.Serial(port, baudrate=38400, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.3)

    # Clear any garbage
    if ser.in_waiting > 0:
        garbage = ser.read(ser.in_waiting)
        print(f"[INFO] Cleared {len(garbage)} bytes")

    # Try the init sequence from captures
    init_cmds = [
        [0x81],
        [0x10],
        [0xFC],
        [0x81],
        [0x0E],
    ]

    print("\n[INIT] Sending initialization sequence...")
    for cmd in init_cmds:
        print(f"[TX] {' '.join([f'{b:02X}' for b in cmd])}")
        ser.write(bytes(cmd))
        ser.flush()
        time.sleep(0.2)

        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"[RX] {' '.join([f'{b:02X}' for b in resp])}")

            # Check if it's NOT just an echo
            if resp != cmd:
                print("  *** NON-ECHO RESPONSE! ***")

    # Try ECU ID
    print("\n[TEST] ECU ID request...")
    cmd = [0x02, 0x1A, 0x81, 0x9D]
    print(f"[TX] {' '.join([f'{b:02X}' for b in cmd])}")
    ser.write(bytes(cmd))
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"[RX] {' '.join([f'{b:02X}' for b in resp])}")

        if len(resp) > len(cmd):
            print("  *** GOT MORE DATA THAN ECHO! ***")
        elif resp != cmd:
            print("  *** NON-ECHO RESPONSE! ***")

    # Try sensor read
    print("\n[TEST] Sensor data request...")
    cmd = [0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D]
    print(f"[TX] {' '.join([f'{b:02X}' for b in cmd])}")
    ser.write(bytes(cmd))
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"[RX] {' '.join([f'{b:02X}' for b in resp])}")

        if len(resp) > len(cmd):
            print("  *** GOT MORE DATA THAN ECHO! ***")
        elif resp != cmd:
            print("  *** NON-ECHO RESPONSE! ***")

    ser.close()


def try_alternative_baudrates(port):
    """Try different baudrates after 0x6C init"""
    print("\n" + "="*70)
    print("TRYING DIFFERENT BAUDRATES AFTER 0x6C INIT")
    print("="*70)

    # Do 5-baud init first
    five_baud_init(port, 0x6C)

    # Try different baudrates
    for baud in [9600, 10400, 38400]:
        print(f"\n[TRY] Baudrate: {baud}")

        try:
            ser = serial.Serial(port, baudrate=baud, timeout=1)
            ser.dtr = True
            ser.rts = True
            time.sleep(0.2)

            # Try ECU ID
            cmd = [0x02, 0x1A, 0x81, 0x9D]
            print(f"  [TX] {' '.join([f'{b:02X}' for b in cmd])}")
            ser.write(bytes(cmd))
            ser.flush()
            time.sleep(0.3)

            if ser.in_waiting > 0:
                resp = list(ser.read(ser.in_waiting))
                print(f"  [RX] {' '.join([f'{b:02X}' for b in resp])}")

                if resp != cmd:
                    print(f"  *** NON-ECHO AT {baud} BAUD! ***")

            ser.close()
            time.sleep(0.3)

        except Exception as e:
            print(f"  Error: {e}")


def main():
    print("="*70)
    print("NISSCOM 0x6C INITIALIZATION TEST")
    print("="*70)

    port = 'COM5'

    # Test 1: Basic 5-baud init with 0x6C
    print("\n" + "="*70)
    print("TEST 1: 5-BAUD INIT WITH 0x6C")
    print("="*70)

    response = five_baud_init(port, 0x6C)

    if response and response != [0x6C]:
        print("\n*** GOT NON-ECHO RESPONSE! ***")
        print("This might be the sync pattern from the ECU!")

    # Test 2: Try communication after init
    print("\n" + "="*70)
    print("TEST 2: COMMUNICATION AFTER INIT")
    print("="*70)

    try_communication_after_init(port)

    # Test 3: Try different baudrates
    try_alternative_baudrates(port)

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
