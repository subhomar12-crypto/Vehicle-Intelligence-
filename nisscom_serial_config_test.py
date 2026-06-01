"""
Test Different Serial Port Configurations
==========================================

The Nisscom software works, but our Python gets echoes.
The difference is likely in serial port settings like:
- DTR (Data Terminal Ready)
- RTS (Request To Send)
- Flow control settings

This script tests all combinations to find what works.
"""

import serial
import time

def test_config(port, baudrate, rtscts, dsrdtr, xonxoff, rts_state, dtr_state, label):
    """Test a specific serial configuration"""

    print(f"\n{'='*70}")
    print(f"Testing: {label}")
    print(f"{'='*70}")
    print(f"  Baudrate: {baudrate}")
    print(f"  RTS/CTS:  {rtscts}")
    print(f"  DSR/DTR:  {dsrdtr}")
    print(f"  XON/XOFF: {xonxoff}")
    print(f"  RTS:      {rts_state}")
    print(f"  DTR:      {dtr_state}")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=1,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
            xonxoff=xonxoff
        )

        # Set DTR and RTS explicitly
        if rts_state is not None:
            ser.rts = rts_state
        if dtr_state is not None:
            ser.dtr = dtr_state

        time.sleep(0.5)

        # Clear buffer
        if ser.in_waiting > 0:
            ser.read(ser.in_waiting)

        # Try the captured initialization
        print("\n  Sending init sequence...")

        # Sync
        ser.write(bytes([0x00]))
        ser.flush()
        time.sleep(0.1)

        resp = []
        while ser.in_waiting > 0:
            resp.append(ser.read(1)[0])

        print(f"    [0x00] -> {' '.join([f'{b:02X}' for b in resp]) if resp else '(no response)'}")

        # Init command
        ser.write(bytes([0x81]))
        ser.flush()
        time.sleep(0.1)

        resp = []
        while ser.in_waiting > 0:
            resp.append(ser.read(1)[0])

        print(f"    [0x81] -> {' '.join([f'{b:02X}' for b in resp]) if resp else '(no response)'}")

        # Handshake
        ser.write(bytes([0x10, 0xFC, 0x81]))
        ser.flush()
        time.sleep(0.1)

        resp = []
        while ser.in_waiting > 0:
            resp.append(ser.read(1)[0])

        print(f"    [0x10 0xFC 0x81] -> {' '.join([f'{b:02X}' for b in resp]) if resp else '(no response)'}")

        # Final handshake
        ser.write(bytes([0x0E]))
        ser.flush()
        time.sleep(0.2)

        resp = []
        while ser.in_waiting > 0:
            resp.append(ser.read(1)[0])

        print(f"    [0x0E] -> {' '.join([f'{b:02X}' for b in resp]) if resp else '(no response)'}")

        # Check if we got the expected response (not just echo)
        if resp and resp != [0x0E]:
            print(f"\n  >>> NON-ECHO RESPONSE! This config might work!")

            # Try a data read
            print("\n  Trying data read command...")
            ser.write(bytes([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D]))
            ser.flush()
            time.sleep(0.2)

            resp = []
            while ser.in_waiting > 0:
                resp.append(ser.read(1)[0])

            print(f"    [Read cmd] -> {' '.join([f'{b:02X}' for b in resp]) if resp else '(no response)'}")

            if resp and resp != [0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D]:
                print(f"\n  *** SUCCESS! ECU IS RESPONDING! ***")
                print(f"  *** USE THIS CONFIGURATION! ***")
                ser.close()
                return True

        ser.close()
        return False

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print("="*70)
    print("NISSCOM SERIAL PORT CONFIGURATION TEST")
    print("="*70)
    print("\nTesting different serial port settings to find what works...")
    print("This may take a few minutes.\n")

    port = 'COM5'
    baudrate = 38400  # We know Nisscom uses this

    configs = [
        # Format: (rtscts, dsrdtr, xonxoff, rts_state, dtr_state, label)

        # No flow control, different DTR/RTS combinations
        (False, False, False, None, None, "Default (no flow control)"),
        (False, False, False, True, True, "RTS=ON, DTR=ON"),
        (False, False, False, False, False, "RTS=OFF, DTR=OFF"),
        (False, False, False, True, False, "RTS=ON, DTR=OFF"),
        (False, False, False, False, True, "RTS=OFF, DTR=ON"),

        # Hardware flow control
        (True, False, False, None, None, "RTS/CTS flow control"),
        (False, True, False, None, None, "DSR/DTR flow control"),
        (True, True, False, None, None, "RTS/CTS + DSR/DTR"),

        # Software flow control
        (False, False, True, None, None, "XON/XOFF flow control"),

        # Hardware flow with explicit states
        (True, False, False, True, True, "RTS/CTS + RTS=ON, DTR=ON"),
        (False, True, False, True, True, "DSR/DTR + RTS=ON, DTR=ON"),
    ]

    success = False

    for config in configs:
        result = test_config(port, baudrate, *config)
        if result:
            success = True
            print(f"\n\n{'='*70}")
            print(f"FOUND WORKING CONFIGURATION: {config[5]}")
            print(f"{'='*70}")
            break
        time.sleep(0.5)  # Brief pause between tests

    if not success:
        print(f"\n\n{'='*70}")
        print("NO WORKING CONFIGURATION FOUND")
        print("="*70)
        print("\nPossibilities:")
        print("  1. Device needs specific timing we haven't tried")
        print("  2. Software sends a special 'unlock' command first")
        print("  3. Multiple baudrates used in sequence")
        print("  4. Device has internal state/mode that needs switching")
        print("\nNext step: Capture actual working session with hardware sniffer")

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
