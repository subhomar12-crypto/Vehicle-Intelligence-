"""
Test what protocol Nissan Patrol 2003 actually supports
Tests with the Nisscom device to see if car responds to anything
"""

import serial
import time

def test_protocol_detection():
    """Try to detect what protocol the car uses"""

    print("=" * 70)
    print("NISSAN PATROL 2003 - PROTOCOL DETECTION")
    print("=" * 70)
    print()
    print("This will test if car responds to any protocol")
    print("through the Nisscom device")
    print()
    print("REQUIREMENTS:")
    print("  - Car ignition ON")
    print("  - Engine can be OFF or ON")
    print("  - Nisscom device plugged into car's diagnostic port")
    print("  - USB connected to computer (COM5)")
    print()
    print("Starting tests in 2 seconds...")
    time.sleep(2)
    print()

    protocols_to_test = [
        # (baud, name, init_sequence, expected_response)
        (10400, "ISO 9141-2 (OBD-II)", [0x33], "0x55 or 0xCC"),
        (10400, "ISO 9141-2 Fast Init", [0xC1, 0x33, 0xF1, 0x01, 0x81], "KWP response"),
        (9600, "Nissan Consult-II", [0xFF, 0xFF, 0xEF], "0x10"),
        (38400, "Nissan Consult (older)", [0xFF, 0xFF, 0xEF], "0x10"),
        (4800, "ISO 9141 Slow", [0x33], "0x55"),
        (1200, "Nissan Consult (very old)", [0xFF, 0xFF, 0xEF], "0x10"),
    ]

    print("=" * 70)
    print("TESTING PROTOCOLS")
    print("=" * 70)
    print()

    working_protocols = []

    for baud, name, init_seq, expected in protocols_to_test:
        print(f"Testing: {name} at {baud} baud")
        print(f"  Init: {' '.join([f'{b:02X}' for b in init_seq])}")
        print(f"  Expect: {expected}")

        try:
            ser = serial.Serial(
                'COM5',
                baudrate=baud,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Send init
            ser.write(bytes(init_seq))
            time.sleep(1)

            # Read response
            response = ser.read(ser.in_waiting or 20)

            if response:
                hex_resp = ' '.join([f'{b:02X}' for b in response])
                print(f"  Recv: {hex_resp}")

                # Check if it's not just an echo
                if response != bytes(init_seq):
                    print(f"  [DIFFERENT] Not an echo!")

                    # Check for expected response
                    if any(exp_byte in response for exp_byte in [0x55, 0xCC, 0x10, 0x7F]):
                        print(f"  [POSSIBLE] Got meaningful response!")
                        working_protocols.append((name, baud, hex_resp))
                    else:
                        print(f"  [UNCLEAR] Response doesn't match expected")
                else:
                    print(f"  [ECHO] Device echoed command back")
            else:
                print(f"  [NONE] No response")

            ser.close()

        except Exception as e:
            print(f"  [ERROR] {e}")

        print()
        time.sleep(0.3)

    # Summary
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    if working_protocols:
        print("[FOUND] Car responded to these protocols:")
        print()
        for name, baud, response in working_protocols:
            print(f"  ✓ {name} at {baud} baud")
            print(f"    Response: {response}")
            print()

        print("This means you need an adapter that supports:")
        print(f"  → {working_protocols[0][0]}")
        print()
    else:
        print("[NO RESPONSE] Car did not respond to any protocol")
        print()
        print("This means:")
        print("  1. Nisscom device is blocking communication")
        print("  2. Car's diagnostic port may not be powered")
        print("  3. Device needs Nisscom software to bridge protocols")
        print()
        print("Without responses, we cannot determine car's protocol.")
        print()

    print()
    print("CONCLUSION:")
    print()

    if not working_protocols:
        print("  Your car likely supports Nissan Consult-II protocol,")
        print("  but the Nisscom device cannot test it without software.")
        print()
        print("  RECOMMENDED SOLUTION:")
        print("    Buy a proper Nissan Consult-II USB adapter ($50-100)")
        print()
        print("    This will:")
        print("      ✓ Work immediately (no software needed)")
        print("      ✓ Work with our Python scripts")
        print("      ✓ Give you full Nissan diagnostics")
        print()
        print("    Where to buy:")
        print("      - eBay: Search 'Nissan Consult USB Cable'")
        print("      - AliExpress: Search 'Nissan Consult-II Interface'")
        print("      - Amazon: Search 'Nissan OBD Consult'")
        print()
        print("    What to look for:")
        print("      - Must say 'Consult-II' or 'Consult 2'")
        print("      - USB interface")
        print("      - Compatible with 1996-2007 Nissans")
        print("      - Check reviews mention 'works without software'")
        print()

    print("=" * 70)
    print()


def main():
    test_protocol_detection()
    print("\nTest complete.")


if __name__ == "__main__":
    main()
