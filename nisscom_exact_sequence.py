"""
Nisscom Exact Sequence Replication
==================================

Replicate the EXACT sequence from USB capture with precise timing.
Based on analysis: baudrates 300->1200->9600->10400->38400
"""

import serial
import time

def exact_sequence(port='COM5'):
    """Replicate exact Nisscom initialization"""
    print("="*60)
    print("EXACT NISSCOM INITIALIZATION SEQUENCE")
    print("="*60)

    # Phase 1: 300 baud - Wake up / slow init
    print("\n[PHASE 1] 300 baud - Wake up")
    ser = serial.Serial(port, baudrate=300, timeout=0.5)
    ser.dtr = False
    ser.rts = False
    time.sleep(0.05)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)

    # Send something at slow speed (might trigger K-line wake)
    ser.write(b'\xFF')
    time.sleep(0.3)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")

    ser.close()
    time.sleep(0.05)

    # Phase 2: 1200 baud
    print("[PHASE 2] 1200 baud")
    ser = serial.Serial(port, baudrate=1200, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.05)
    ser.close()
    time.sleep(0.05)

    # Phase 3: 9600 baud
    print("[PHASE 3] 9600 baud")
    ser = serial.Serial(port, baudrate=9600, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.05)
    ser.close()
    time.sleep(0.05)

    # Phase 4: 10400 baud - K-line standard
    print("[PHASE 4] 10400 baud - K-line init")
    ser = serial.Serial(port, baudrate=10400, timeout=1)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)

    # K-line init commands
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    for b in init_bytes:
        ser.write(bytes([b]))
        time.sleep(0.05)

    time.sleep(0.2)
    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")

    ser.close()
    time.sleep(0.05)

    # Phase 5: 38400 baud - Main communication
    print("[PHASE 5] 38400 baud - Communication")
    ser = serial.Serial(port, baudrate=38400, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.3)

    # Clear buffer
    if ser.in_waiting > 0:
        junk = ser.read(ser.in_waiting)
        print(f"  Cleared {len(junk)} bytes")

    # Try ECU ID request
    print("\n[TEST] ECU ID request: 02 1A 81 9D")
    cmd = bytes([0x02, 0x1A, 0x81, 0x9D])
    ser.write(cmd)
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")

        if len(resp) > len(cmd):
            print("  *** GOT MORE THAN ECHO - ECU RESPONDED! ***")
            return ser

    # Try sensor read
    print("\n[TEST] Sensor read: 05 22 11 00 04 01 3D")
    cmd = bytes([0x05, 0x22, 0x11, 0x00, 0x04, 0x01, 0x3D])
    ser.write(cmd)
    ser.flush()
    time.sleep(0.5)

    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")

        if len(resp) > len(cmd):
            print("  *** GOT MORE THAN ECHO - ECU RESPONDED! ***")

    ser.close()
    return None


def try_different_init_patterns(port='COM5'):
    """Try different initialization patterns"""
    print("\n" + "="*60)
    print("TRYING DIFFERENT INIT PATTERNS")
    print("="*60)

    # Pattern 1: DTR toggle before each baudrate change
    print("\n[PATTERN 1] DTR toggle before baudrate changes")
    for baud in [300, 1200, 9600, 10400, 38400]:
        ser = serial.Serial(port, baudrate=baud, timeout=0.5)
        # Toggle DTR
        ser.dtr = False
        time.sleep(0.02)
        ser.dtr = True
        time.sleep(0.05)
        ser.close()
        time.sleep(0.02)

    # Now test at 38400
    ser = serial.Serial(port, baudrate=38400, timeout=1)
    ser.write(bytes([0x02, 0x1A, 0x81, 0x9D]))
    time.sleep(0.5)
    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")
        if len(resp) > 4:
            print("  *** SUCCESS! ***")
    ser.close()

    time.sleep(0.5)

    # Pattern 2: Send break before init
    print("\n[PATTERN 2] BREAK signal before init")
    ser = serial.Serial(port, baudrate=38400, timeout=1)
    ser.send_break(duration=0.3)
    time.sleep(0.2)

    ser.write(bytes([0x02, 0x1A, 0x81, 0x9D]))
    time.sleep(0.5)
    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")
    ser.close()

    time.sleep(0.5)

    # Pattern 3: RTS toggle
    print("\n[PATTERN 3] RTS toggle")
    ser = serial.Serial(port, baudrate=38400, timeout=1)
    ser.rts = False
    time.sleep(0.1)
    ser.rts = True
    time.sleep(0.1)

    ser.write(bytes([0x02, 0x1A, 0x81, 0x9D]))
    time.sleep(0.5)
    if ser.in_waiting > 0:
        resp = list(ser.read(ser.in_waiting))
        print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")
    ser.close()


if __name__ == "__main__":
    # Run exact sequence
    exact_sequence()

    # Try different patterns
    try_different_init_patterns()

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)
