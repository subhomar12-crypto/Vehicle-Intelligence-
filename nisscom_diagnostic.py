"""
Nisscom Device Diagnostic - Manual ELM327 Communication
"""

import serial
import time

def send_command(ser, command, wait_time=1):
    """Send a command and read response"""
    print(f"  Sending: {command}")
    ser.write((command + '\r').encode())
    time.sleep(wait_time)

    response = b''
    timeout_count = 0
    while timeout_count < 10:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting)
            time.sleep(0.1)
        else:
            timeout_count += 1
            time.sleep(0.1)

    print(f"  Response: {response}")
    return response

print("=" * 60)
print("NISSCOM DEVICE DIAGNOSTIC")
print("=" * 60)
print()

try:
    # Open COM5 at 38400 baud
    print("Opening COM5 at 38400 baud...")
    ser = serial.Serial('COM5', 38400, timeout=2)
    print(f"[OK] Port opened: {ser.name}")
    print()

    # ELM327 initialization sequence
    print("Initializing ELM327 device...")
    print()

    # 1. Reset
    print("1. Resetting device...")
    response = send_command(ser, 'ATZ', 2)

    # 2. Echo OFF
    print("\n2. Turning echo OFF...")
    response = send_command(ser, 'ATE0')

    # 3. Line feeds OFF
    print("\n3. Turning line feeds OFF...")
    response = send_command(ser, 'ATL0')

    # 4. Request device identification
    print("\n4. Requesting device ID...")
    response = send_command(ser, 'ATI')

    # 5. Request voltage
    print("\n5. Requesting battery voltage...")
    response = send_command(ser, 'ATRV')

    # 6. Set protocol to auto
    print("\n6. Setting protocol to AUTO...")
    response = send_command(ser, 'ATSP0')

    # 7. Try to connect to car's ECU
    print("\n7. Attempting to connect to car ECU...")
    print("   (This may take 10-15 seconds)")
    response = send_command(ser, '0100', 5)

    if b'41 00' in response or b'4100' in response:
        print("\n[SUCCESS] Connected to car's ECU!")
        print()

        # Try to read RPM (PID 010C)
        print("8. Reading RPM...")
        response = send_command(ser, '010C', 1)
        print()

        # Try to read Speed (PID 010D)
        print("9. Reading Speed...")
        response = send_command(ser, '010D', 1)
        print()

        # Try to read Coolant Temp (PID 0105)
        print("10. Reading Coolant Temperature...")
        response = send_command(ser, '0105', 1)

    elif b'NO DATA' in response or b'UNABLE TO CONNECT' in response:
        print("\n[FAILED] Cannot connect to car")
        print()
        print("Possible reasons:")
        print("1. Car ignition is not ON")
        print("2. Device is not properly inserted in OBD-II port")
        print("3. Your car might use a different OBD protocol")
        print("4. The device might need to be initialized in the car first")

    else:
        print("\n[UNKNOWN] Unexpected response from device")
        print()
        print("The device might not be ELM327 compatible")
        print("You may need the manufacturer's specific software")

    ser.close()
    print()
    print("Connection closed.")

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
input("Press Enter to exit...")
