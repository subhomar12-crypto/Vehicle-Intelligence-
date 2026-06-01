"""
Read Real-Time Car Data from Nisscom Device
Make sure: Car ignition is ON, device plugged into OBD-II port
"""

import obd
import time

print("=" * 60)
print("NISSCOM - REAL-TIME CAR DATA READER")
print("=" * 60)
print()
print("Connecting to car on COM5 at 38400 baud...")
print("Please wait...")
print()

try:
    # Connect with the detected settings
    connection = obd.OBD(
        portstr="COM5",
        baudrate=38400,
        fast=False,  # Don't use fast mode for better compatibility
        timeout=30    # Give it time to connect
    )

    if not connection.is_connected():
        print("[FAILED] Could not connect to car")
        print()
        print("Troubleshooting:")
        print("1. Is the car's ignition ON?")
        print("2. Wait 10-15 seconds after turning ignition ON")
        print("3. Make sure device is fully inserted into OBD-II port")
        print("4. Try starting the engine")
        print()
        input("Press Enter to exit...")
        exit()

    print("[SUCCESS] Connected to car!")
    print(f"Protocol: {connection.protocol_name()}")
    print(f"ECU: {connection.ecus}")
    print()
    print("=" * 60)

    # List of available commands
    supported = connection.supported_commands
    print(f"Your car supports {len(supported)} OBD-II commands")
    print()

    # Define commands to read
    commands = {
        'RPM': obd.commands.RPM,
        'Speed': obd.commands.SPEED,
        'Coolant Temp': obd.commands.COOLANT_TEMP,
        'Engine Load': obd.commands.ENGINE_LOAD,
        'Throttle Position': obd.commands.THROTTLE_POS,
        'Intake Air Temp': obd.commands.INTAKE_TEMP,
        'MAF': obd.commands.MAF,
        'Fuel Level': obd.commands.FUEL_LEVEL,
        'Intake Pressure': obd.commands.INTAKE_PRESSURE,
    }

    print("READING CURRENT VALUES:")
    print("-" * 60)

    for name, cmd in commands.items():
        if cmd in supported:
            response = connection.query(cmd)
            if not response.is_null():
                print(f"{name:20} : {response.value}")
            else:
                print(f"{name:20} : No data")
        else:
            print(f"{name:20} : Not supported by vehicle")

    print()
    print("=" * 60)
    print("LIVE MONITORING (Press Ctrl+C to stop)")
    print("=" * 60)
    print()

    # Continuous monitoring
    print(f"{'Time':>8} | {'RPM':>6} | {'Speed':>8} | {'Coolant':>10} | {'Load':>6}")
    print("-" * 60)

    start_time = time.time()

    try:
        while True:
            # Query key parameters
            rpm_response = connection.query(obd.commands.RPM)
            speed_response = connection.query(obd.commands.SPEED)
            temp_response = connection.query(obd.commands.COOLANT_TEMP)
            load_response = connection.query(obd.commands.ENGINE_LOAD)

            # Get values
            rpm = rpm_response.value if not rpm_response.is_null() else "N/A"
            speed = speed_response.value if not speed_response.is_null() else "N/A"
            temp = temp_response.value if not temp_response.is_null() else "N/A"
            load = load_response.value if not load_response.is_null() else "N/A"

            # Display
            elapsed = time.time() - start_time
            print(f"{elapsed:>7.1f}s | {str(rpm):>6} | {str(speed):>8} | {str(temp):>10} | {str(load):>6}")

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Monitoring stopped by user")

    connection.close()
    print()
    print("Connection closed.")
    print("[SUCCESS] Test completed!")

except Exception as e:
    print(f"[ERROR] {e}")
    print()
    import traceback
    traceback.print_exc()

print()
input("Press Enter to exit...")
