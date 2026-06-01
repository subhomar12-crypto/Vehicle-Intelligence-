"""
Test Nisscom OBD-II Device
Reads basic vehicle data from the diagnostic adapter on COM5
"""

import obd
import time

def test_nisscom_device():
    """Test the Nisscom device and read basic OBD-II data"""

    print("=" * 60)
    print("NISSCOM OBD-II DEVICE TEST")
    print("=" * 60)
    print()

    # Try to connect to COM5 (where the device is detected)
    print("Connecting to Nisscom device on COM5...")
    print("NOTE: Make sure the device is plugged into your car's OBD-II port")
    print("      and the ignition is ON (engine can be off or running)")
    print()

    try:
        # Connect to the OBD-II adapter
        connection = obd.OBD(portstr="COM5", baudrate=38400)

        if not connection.is_connected():
            print("❌ Could not connect to OBD-II adapter")
            print()
            print("Troubleshooting:")
            print("1. Make sure the device is plugged into the car's OBD-II port")
            print("2. Turn the car's ignition to ON position (don't need to start engine)")
            print("3. Wait 5-10 seconds after plugging in")
            print("4. Check if the device has LED lights that are blinking")
            return

        print("✅ Connected to OBD-II adapter successfully!")
        print(f"Protocol: {connection.protocol_name()}")
        print(f"Port: {connection.port_name()}")
        print()

        # List supported commands
        print("Checking supported commands...")
        supported = connection.supported_commands
        print(f"Device supports {len(supported)} OBD-II commands")
        print()

        print("=" * 60)
        print("READING VEHICLE DATA")
        print("=" * 60)
        print()

        # Define the commands to read
        commands_to_read = [
            (obd.commands.RPM, "Engine RPM"),
            (obd.commands.SPEED, "Vehicle Speed"),
            (obd.commands.COOLANT_TEMP, "Coolant Temperature"),
            (obd.commands.ENGINE_LOAD, "Engine Load"),
            (obd.commands.THROTTLE_POS, "Throttle Position"),
            (obd.commands.INTAKE_TEMP, "Intake Air Temperature"),
            (obd.commands.MAF, "Mass Air Flow"),
            (obd.commands.FUEL_LEVEL, "Fuel Level"),
            (obd.commands.INTAKE_PRESSURE, "Intake Manifold Pressure"),
            (obd.commands.TIMING_ADVANCE, "Timing Advance"),
        ]

        # Read each command
        for cmd, name in commands_to_read:
            if cmd in supported:
                response = connection.query(cmd)
                if not response.is_null():
                    print(f"✅ {name:30} : {response.value}")
                else:
                    print(f"⚠️  {name:30} : No data")
            else:
                print(f"❌ {name:30} : Not supported")

        print()
        print("=" * 60)
        print("CONTINUOUS MONITORING (10 seconds)")
        print("=" * 60)
        print()

        # Monitor key parameters for 10 seconds
        print("Monitoring RPM, Speed, and Coolant Temp...")
        print("Time  | RPM    | Speed      | Coolant Temp")
        print("-" * 50)

        start_time = time.time()
        while time.time() - start_time < 10:
            rpm = connection.query(obd.commands.RPM)
            speed = connection.query(obd.commands.SPEED)
            temp = connection.query(obd.commands.COOLANT_TEMP)

            rpm_val = rpm.value if not rpm.is_null() else "N/A"
            speed_val = speed.value if not speed.is_null() else "N/A"
            temp_val = temp.value if not temp.is_null() else "N/A"

            elapsed = time.time() - start_time
            print(f"{elapsed:4.1f}s | {str(rpm_val):6} | {str(speed_val):10} | {str(temp_val)}")

            time.sleep(1)

        print()
        print("✅ Test completed successfully!")

        # Close connection
        connection.close()
        print("Connection closed.")

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Common issues:")
        print("1. Device not connected to car's OBD-II port")
        print("2. Car ignition is not ON")
        print("3. Wrong COM port (try checking Device Manager)")
        print("4. Device might need specific drivers")

if __name__ == "__main__":
    test_nisscom_device()

    print()
    input("Press Enter to exit...")
