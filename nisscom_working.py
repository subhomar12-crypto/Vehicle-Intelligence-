"""
Nisscom Working Protocol
========================

Based on USB capture analysis - send init bytes ONE AT A TIME!
"""

import serial
import time

def nisscom_connect(port='COM5'):
    """Connect to ECU using discovered protocol"""
    print("="*60)
    print("NISSCOM PROTOCOL - FROM USB CAPTURE")
    print("="*60)

    # Open at 10400 baud (K-line standard, seen in capture)
    print(f"\n[OPEN] {port} at 10400 baud")
    ser = serial.Serial(port, baudrate=10400, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.3)

    # Clear buffer
    if ser.in_waiting > 0:
        ser.read(ser.in_waiting)

    # INIT SEQUENCE - send bytes ONE AT A TIME with delays
    print("\n[INIT] Sending initialization sequence...")

    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]

    for b in init_bytes:
        print(f"  TX: {b:02X}")
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(0.1)  # Small delay between bytes

        # Read any response
        time.sleep(0.1)
        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"  RX: {' '.join([f'{x:02X}' for x in resp])}")

    # Wait for ECU init response (83 FC 10 C1 ...)
    print("\n[WAIT] Waiting for ECU init response...")
    time.sleep(0.5)

    if ser.in_waiting > 0:
        init_resp = list(ser.read(ser.in_waiting))
        print(f"  RX: {' '.join([f'{x:02X}' for x in init_resp])}")

        # Check for successful init (83 at start)
        if 0x83 in init_resp:
            print("\n*** ECU INIT SUCCESSFUL! ***")
        else:
            print("  (No 0x83 init response)")
    else:
        print("  No init response received")

    # Now try ECU ID
    print("\n[CMD] ECU ID request: 02 1A 81 9D")
    ser.write(bytes([0x02, 0x1A, 0x81, 0x9D]))
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  RX: {' '.join([f'{x:02X}' for x in resp])}")

        # Check for ECU ID response (5A = positive response to 1A)
        if 0x5A in resp:
            print("\n*** GOT ECU ID! ***")
            # Extract ID string
            try:
                idx = resp.index(0x5A)
                id_bytes = resp[idx+1:idx+7]
                id_str = ''.join([chr(b) for b in id_bytes if 32 <= b < 127])
                print(f"  ECU ID: {id_str}")
            except:
                pass

    # Try sensor read
    print("\n[CMD] Sensor read: 05 22 11 00 04 01 3D")
    ser.write(bytes([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D]))
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  RX: {' '.join([f'{x:02X}' for x in resp])}")

        if 0x62 in resp:
            print("\n*** GOT SENSOR DATA! ***")

    ser.close()
    print("\n[DONE]")


def try_different_baudrates(port='COM5'):
    """Try init at different baudrates"""
    print("\n" + "="*60)
    print("TRYING DIFFERENT BAUDRATES")
    print("="*60)

    for baud in [9600, 10400, 38400]:
        print(f"\n--- Baudrate: {baud} ---")

        ser = serial.Serial(port, baudrate=baud, timeout=1)
        ser.dtr = True
        ser.rts = True
        time.sleep(0.2)

        # Clear
        if ser.in_waiting > 0:
            ser.read(ser.in_waiting)

        # Send init one byte at a time
        for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
            ser.write(bytes([b]))
            time.sleep(0.05)

        time.sleep(0.5)

        if ser.in_waiting > 0:
            resp = list(ser.read(ser.in_waiting))
            print(f"  Response: {' '.join([f'{x:02X}' for x in resp])}")

            if 0x83 in resp:
                print(f"  *** SUCCESS AT {baud} BAUD! ***")
                ser.close()
                return baud

        ser.close()

    return None


if __name__ == "__main__":
    # Try main approach
    nisscom_connect()

    # If that didn't work, try different baudrates
    print("\n")
    try_different_baudrates()
