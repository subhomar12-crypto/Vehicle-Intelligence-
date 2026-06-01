"""
Basic Nisscom OBD-II Device Test
Tests if the device is responding on COM5
"""

import serial
import time

def test_serial_connection():
    """Test basic serial communication with the device"""

    print("=" * 60)
    print("NISSCOM DEVICE - BASIC CONNECTION TEST")
    print("=" * 60)
    print()

    # Common baud rates for OBD-II adapters
    baud_rates = [38400, 9600, 115200, 57600, 19200]

    print("Testing COM5 at different baud rates...")
    print()

    for baudrate in baud_rates:
        print(f"Trying baud rate: {baudrate}...")

        try:
            # Open serial connection
            ser = serial.Serial(
                port='COM5',
                baudrate=baudrate,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            print(f"  [OK] Port opened successfully")
            print(f"  Port: {ser.name}")
            print(f"  Is Open: {ser.is_open}")

            # Try to reset the device (ATZ command for ELM327)
            print(f"  Sending ATZ (reset) command...")
            ser.write(b'ATZ\r')
            time.sleep(1)

            # Read response
            response = ser.read(ser.in_waiting or 100)
            if response:
                print(f"  [RESPONSE] Device responded: {response}")
                print(f"  [SUCCESS] Device is responding at {baudrate} baud!")
                print()

                # Try a few more commands
                print("  Testing additional commands...")

                # ATI - Request device ID
                ser.write(b'ATI\r')
                time.sleep(0.5)
                response = ser.read(ser.in_waiting or 100)
                if response:
                    print(f"  Device ID: {response}")

                # ATE0 - Echo OFF
                ser.write(b'ATE0\r')
                time.sleep(0.5)
                response = ser.read(ser.in_waiting or 100)
                if response:
                    print(f"  Echo OFF: {response}")

                # ATL0 - Linefeeds OFF
                ser.write(b'ATL0\r')
                time.sleep(0.5)
                response = ser.read(ser.in_waiting or 100)
                if response:
                    print(f"  Linefeeds OFF: {response}")

                ser.close()
                print()
                print("=" * 60)
                print("[SUCCESS] Device is working!")
                print(f"Correct baud rate: {baudrate}")
                print()
                print("To read car data:")
                print("1. Plug device into your car's OBD-II port")
                print("2. Turn ignition to ON")
                print("3. Run the full test script")
                print("=" * 60)
                return baudrate

            else:
                print(f"  [NO RESPONSE] Device did not respond")
                ser.close()

        except serial.SerialException as e:
            print(f"  [ERROR] Could not open port: {e}")

        except Exception as e:
            print(f"  [ERROR] {e}")

        print()

    print("=" * 60)
    print("[FAILED] Device did not respond at any baud rate")
    print()
    print("Possible reasons:")
    print("1. Device might need to be connected to a car first")
    print("2. Device might need specific drivers installed")
    print("3. Device might be on a different COM port")
    print("4. Device might be faulty")
    print()
    print("Next steps:")
    print("1. Check Device Manager - is COM5 still there?")
    print("2. Unplug and replug the device")
    print("3. Try plugging into car's OBD-II port with ignition ON")
    print("=" * 60)
    return None


def test_with_obd_library():
    """Test using the OBD library with car connected"""

    print()
    print("=" * 60)
    print("FULL OBD-II TEST (Car must be connected)")
    print("=" * 60)
    print()

    import obd

    print("IMPORTANT: Make sure:")
    print("  1. Device is plugged into car's OBD-II port")
    print("  2. Car ignition is ON (engine can be off)")
    print("  3. Wait 10 seconds after turning ignition ON")
    print()

    input("Press Enter when ready to test with car...")
    print()

    try:
        # Try common baud rates
        for baudrate in [38400, 9600]:
            print(f"Trying to connect at {baudrate} baud...")

            connection = obd.OBD(portstr="COM5", baudrate=baudrate, fast=False)

            if connection.is_connected():
                print(f"[SUCCESS] Connected to car!")
                print(f"Protocol: {connection.protocol_name()}")
                print(f"Port: {connection.port_name()}")
                print()

                # Try to read some basic data
                print("Reading vehicle data...")

                # RPM
                cmd = obd.commands.RPM
                response = connection.query(cmd)
                if not response.is_null():
                    print(f"  Engine RPM: {response.value}")
                else:
                    print(f"  Engine RPM: No data (engine might be off)")

                # Speed
                cmd = obd.commands.SPEED
                response = connection.query(cmd)
                if not response.is_null():
                    print(f"  Speed: {response.value}")
                else:
                    print(f"  Speed: No data")

                # Coolant temp
                cmd = obd.commands.COOLANT_TEMP
                response = connection.query(cmd)
                if not response.is_null():
                    print(f"  Coolant Temperature: {response.value}")
                else:
                    print(f"  Coolant Temperature: No data")

                connection.close()
                print()
                print("[SUCCESS] Device is working with car!")
                return

            else:
                print(f"  Could not connect at {baudrate} baud")

        print()
        print("[FAILED] Could not connect to car")
        print("Make sure ignition is ON and device is properly connected")

    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    # First test basic serial communication
    detected_baudrate = test_serial_connection()

    # If user wants to test with car
    print()
    user_input = input("Do you want to test with car connected? (y/n): ")

    if user_input.lower() == 'y':
        test_with_obd_library()

    print()
    input("Press Enter to exit...")
