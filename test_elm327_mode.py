"""
ELM327 Protocol Test for Nisscom Device
Tests if the device can work in standard ELM327 mode
"""

import serial
import time

def send_at_command(ser, command, wait_time=1):
    """Send AT command and read response"""
    print(f"  → {command}")
    ser.write((command + '\r').encode())
    time.sleep(wait_time)

    response = b''
    timeout_count = 0
    while timeout_count < 20:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting)
            time.sleep(0.05)
        else:
            timeout_count += 1
            time.sleep(0.05)

    response_str = response.decode('utf-8', errors='ignore').strip()
    print(f"  ← {response_str}")
    return response_str

def test_elm327_mode():
    """Test if device works in ELM327 mode"""

    print("=" * 70)
    print("ELM327 MODE TEST FOR NISSCOM DEVICE")
    print("=" * 70)
    print()
    print("This will try to initialize the device as ELM327")
    print()

    # Try different baud rates
    baud_rates = [38400, 9600, 115200, 57600, 19200]

    for baudrate in baud_rates:
        print(f"\n{'='*70}")
        print(f"Testing at {baudrate} baud...")
        print('='*70)

        try:
            ser = serial.Serial('COM5', baudrate, timeout=2)
            print(f"[OK] Port opened at {baudrate} baud")
            time.sleep(1)

            # ELM327 Initialization Sequence
            print("\n1. Resetting device...")
            response = send_at_command(ser, 'ATZ', 2)

            if 'ELM327' in response.upper() or 'ELM' in response.upper():
                print("  [SUCCESS] Device identified as ELM327!")

                # Continue with initialization
                print("\n2. Turning echo OFF...")
                send_at_command(ser, 'ATE0')

                print("\n3. Turning line feeds OFF...")
                send_at_command(ser, 'ATL0')

                print("\n4. Getting device info...")
                send_at_command(ser, 'ATI')

                print("\n5. Getting voltage...")
                send_at_command(ser, 'ATRV')

                print("\n6. Setting protocol to AUTO...")
                send_at_command(ser, 'ATSP0')

                print("\n7. Trying to read supported PIDs...")
                response = send_at_command(ser, '0100', 3)

                if '41 00' in response or '4100' in response:
                    print("\n  [SUCCESS] Connected to car's ECU!")
                    print("\n8. Reading RPM (PID 010C)...")
                    send_at_command(ser, '010C', 1)

                    print("\n9. Reading Speed (PID 010D)...")
                    send_at_command(ser, '010D', 1)

                    print("\n10. Reading Coolant Temp (PID 0105)...")
                    send_at_command(ser, '0105', 1)

                    print("\n" + "="*70)
                    print("[SUCCESS] Device works in ELM327 mode!")
                    print(f"Correct baud rate: {baudrate}")
                    print("="*70)

                    ser.close()
                    return baudrate
                else:
                    print("\n  [INFO] Device responded as ELM327 but can't connect to car")
                    print("  Make sure car ignition is ON")

            elif 'OK' in response.upper():
                print("  [INFO] Device responded with OK (might be ELM327)")
                # Try to get device info
                print("\n  Requesting device ID...")
                response = send_at_command(ser, 'ATI')

                if 'ELM' in response.upper():
                    print("  [SUCCESS] Confirmed ELM327 device!")

            else:
                print(f"  [SKIP] Not ELM327 at {baudrate} baud")

            ser.close()

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "="*70)
    print("[RESULT] Device does not appear to support ELM327 mode")
    print("You will need Nisscom's proprietary software")
    print("="*70)
    return None

def main():
    print()
    print("IMPORTANT: Make sure device is connected to COM5")
    print("Car ignition should be ON for full testing")
    print()

    result = test_elm327_mode()

    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
