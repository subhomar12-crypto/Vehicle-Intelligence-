"""
Experiment 1: Different K-line Address Bytes
=============================================

Try different address bytes during K-line init.
Common addresses: 0x33, 0x68, 0x6C, 0x8F, 0xFE
"""

import serial
import time

def try_address_byte(port, address):
    """Try K-line init with specific address byte"""
    print(f"\n[TRY] Address byte: 0x{address:02X}")

    try:
        # Very slow baudrate for 5-baud init
        ser = serial.Serial(port, baudrate=360, timeout=1)
        ser.dtr = True
        ser.rts = False

        # Send address
        ser.write(bytes([address]))
        time.sleep(0.3)

        # Check for sync response
        if ser.in_waiting > 0:
            resp = ser.read(ser.in_waiting)
            print(f"  Response: {' '.join([f'{b:02X}' for b in resp])}")
            ser.close()
            return True

        ser.close()
        return False

    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    print("="*70)
    print("EXPERIMENT 1: K-LINE ADDRESS BYTES")
    print("="*70)

    port = 'COM5'

    # Try common K-line addresses
    addresses = [
        0x33,  # Generic
        0x68,  # Some Nissan ECUs
        0x6C,  # Alternative
        0x8F,  # ISO 9141
        0xFE,  # Broadcast
        0x10,  # ECU address
        0xF1,  # Tester
    ]

    for addr in addresses:
        success = try_address_byte(port, addr)
        if success:
            print(f"\n*** ADDRESS 0x{addr:02X} GOT RESPONSE! ***")

            # Now try connecting at 38400
            print("\n[TEST] Connecting at 38400 baud...")
            ser = serial.Serial(port, baudrate=38400, timeout=2)
            ser.dtr = True
            ser.rts = True
            time.sleep(0.5)

            # Try sending command
            ser.write(b'\x02\x1A\x81\x9D')
            time.sleep(0.5)

            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"[RX] {' '.join([f'{b:02X}' for b in data])}")

            ser.close()
            break

        time.sleep(0.5)

    print("\n[DONE]")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
