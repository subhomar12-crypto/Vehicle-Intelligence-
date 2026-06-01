"""
Nissan Consult-II Protocol Reader
Experimental reader for Nissan vehicles using Consult-II protocol
Tested on: Nissan Patrol 2003
"""

import serial
import time
import struct

class Consult2Reader:
    """Consult-II protocol reader for Nissan vehicles"""

    # Consult-II commands (reverse-engineered)
    CMD_ECU_INIT = [0xFF, 0xFF, 0xEF]  # Initialize ECU communication
    CMD_START_STREAM = [0x5A, 0x00]     # Start data stream
    CMD_STOP_STREAM = [0x30]            # Stop data stream

    # Register addresses for common parameters
    REGISTERS = {
        'RPM': 0x00,           # Engine RPM (0x00, 0x01)
        'COOLANT_TEMP': 0x08,  # Coolant temperature
        'VEHICLE_SPEED': 0x0B, # Vehicle speed
        'BATTERY_VOLTAGE': 0x0C, # Battery voltage
        'THROTTLE_POSITION': 0x0D, # Throttle position
        'ENGINE_LOAD': 0x0E,   # Engine load
        'AIR_FLOW': 0x12,      # Air flow meter
        'FUEL_TEMP': 0x0F,     # Fuel temperature
        'INTAKE_TEMP': 0x11,   # Intake air temperature
        'TIMING': 0x13,        # Ignition timing
    }

    def __init__(self, port='COM5', baudrate=38400):
        """Initialize Consult-II connection"""
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        """Connect to the Consult-II device"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            print(f"[OK] Connected to {self.port} at {self.baudrate} baud")
            time.sleep(0.5)

            # Clear any existing data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            return True

        except Exception as e:
            print(f"[ERROR] Could not connect: {e}")
            return False

    def send_command(self, command):
        """Send a command to the ECU"""
        if isinstance(command, list):
            command = bytes(command)

        self.ser.write(command)
        time.sleep(0.1)

    def read_response(self, num_bytes=None):
        """Read response from ECU"""
        if num_bytes:
            return self.ser.read(num_bytes)
        else:
            # Read all available data
            time.sleep(0.1)
            available = self.ser.in_waiting
            if available > 0:
                return self.ser.read(available)
            return b''

    def initialize_ecu(self):
        """Initialize communication with ECU"""
        print("\nInitializing ECU communication...")

        # Try Consult-II initialization sequence
        self.send_command(self.CMD_ECU_INIT)
        response = self.read_response()

        print(f"  ECU Init Response: {response.hex() if response else 'No response'}")

        if response and len(response) > 0:
            print("  [OK] ECU responded")
            return True

        # Alternative initialization
        print("  Trying alternative init...")
        self.send_command([0x5A, 0x00, 0x00])
        response = self.read_response()
        print(f"  Alt Response: {response.hex() if response else 'No response'}")

        return len(response) > 0 if response else False

    def read_register(self, register_addr):
        """Read a single register value"""
        # Consult-II read command format
        command = [0x5A, 0x01, register_addr]

        self.ser.reset_input_buffer()
        self.send_command(command)

        # Read response
        response = self.read_response(3)  # Usually 3 bytes response

        if response and len(response) >= 1:
            return response[0]  # Return first data byte

        return None

    def decode_rpm(self, value):
        """Decode RPM from register value"""
        if value is None:
            return None
        # RPM = value * 12.5 (typical for Nissan Consult-II)
        return int(value * 12.5)

    def decode_temperature(self, value):
        """Decode temperature from register value"""
        if value is None:
            return None
        # Temperature = value - 50 (typical offset)
        return value - 50

    def decode_speed(self, value):
        """Decode vehicle speed"""
        if value is None:
            return None
        # Speed in km/h
        return value

    def read_all_parameters(self):
        """Read all available parameters"""
        print("\n" + "=" * 60)
        print("READING VEHICLE PARAMETERS")
        print("=" * 60)

        results = {}

        # Read RPM
        rpm_raw = self.read_register(self.REGISTERS['RPM'])
        if rpm_raw is not None:
            rpm = self.decode_rpm(rpm_raw)
            results['RPM'] = rpm
            print(f"Engine RPM:           {rpm} RPM")
        else:
            print(f"Engine RPM:           No data")

        # Read Coolant Temperature
        temp_raw = self.read_register(self.REGISTERS['COOLANT_TEMP'])
        if temp_raw is not None:
            temp = self.decode_temperature(temp_raw)
            results['Coolant Temp'] = temp
            print(f"Coolant Temperature:  {temp} C")
        else:
            print(f"Coolant Temperature:  No data")

        # Read Vehicle Speed
        speed_raw = self.read_register(self.REGISTERS['VEHICLE_SPEED'])
        if speed_raw is not None:
            speed = self.decode_speed(speed_raw)
            results['Speed'] = speed
            print(f"Vehicle Speed:        {speed} km/h")
        else:
            print(f"Vehicle Speed:        No data")

        # Read Throttle Position
        throttle_raw = self.read_register(self.REGISTERS['THROTTLE_POSITION'])
        if throttle_raw is not None:
            throttle = (throttle_raw / 255.0) * 100  # Convert to percentage
            results['Throttle'] = throttle
            print(f"Throttle Position:    {throttle:.1f} %")
        else:
            print(f"Throttle Position:    No data")

        # Read Battery Voltage
        battery_raw = self.read_register(self.REGISTERS['BATTERY_VOLTAGE'])
        if battery_raw is not None:
            voltage = battery_raw * 0.08  # Typical scaling
            results['Battery Voltage'] = voltage
            print(f"Battery Voltage:      {voltage:.1f} V")
        else:
            print(f"Battery Voltage:      No data")

        # Read Intake Air Temperature
        intake_raw = self.read_register(self.REGISTERS['INTAKE_TEMP'])
        if intake_raw is not None:
            intake_temp = self.decode_temperature(intake_raw)
            results['Intake Temp'] = intake_temp
            print(f"Intake Air Temp:      {intake_temp} C")
        else:
            print(f"Intake Air Temp:      No data")

        return results

    def continuous_read(self, duration=10):
        """Continuously read parameters for specified duration"""
        print("\n" + "=" * 60)
        print(f"CONTINUOUS MONITORING ({duration} seconds)")
        print("=" * 60)
        print()
        print(f"{'Time':>6} | {'RPM':>6} | {'Speed':>7} | {'Coolant':>8} | {'Throttle':>8}")
        print("-" * 60)

        start_time = time.time()

        while time.time() - start_time < duration:
            elapsed = time.time() - start_time

            # Read key parameters
            rpm_raw = self.read_register(self.REGISTERS['RPM'])
            speed_raw = self.read_register(self.REGISTERS['VEHICLE_SPEED'])
            temp_raw = self.read_register(self.REGISTERS['COOLANT_TEMP'])
            throttle_raw = self.read_register(self.REGISTERS['THROTTLE_POSITION'])

            # Decode values
            rpm = self.decode_rpm(rpm_raw) if rpm_raw is not None else "N/A"
            speed = self.decode_speed(speed_raw) if speed_raw is not None else "N/A"
            temp = self.decode_temperature(temp_raw) if temp_raw is not None else "N/A"
            throttle = f"{(throttle_raw / 255.0) * 100:.1f}" if throttle_raw is not None else "N/A"

            print(f"{elapsed:5.1f}s | {str(rpm):>6} | {str(speed):>6} | {str(temp):>7}C | {str(throttle):>7}%")

            time.sleep(1)

    def close(self):
        """Close the serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("\n[OK] Connection closed")


def main():
    """Main function to test Consult-II reader"""

    print("=" * 60)
    print("NISSAN CONSULT-II READER")
    print("For: Nissan Patrol 2003 with Nisscom Device")
    print("=" * 60)
    print()
    print("IMPORTANT:")
    print("  - Car ignition must be ON")
    print("  - Device plugged into OBD-II port")
    print("  - Engine can be off or running")
    print()

    # Create reader instance
    reader = Consult2Reader(port='COM5', baudrate=38400)

    # Connect
    if not reader.connect():
        print("\n[FAILED] Could not connect to device")
        input("Press Enter to exit...")
        return

    try:
        # Initialize ECU communication
        if not reader.initialize_ecu():
            print("\n[WARNING] ECU initialization unclear, trying to read anyway...")

        # Read all parameters once
        reader.read_all_parameters()

        # Ask if user wants continuous monitoring
        print()
        choice = input("Start continuous monitoring? (y/n): ")

        if choice.lower() == 'y':
            reader.continuous_read(duration=15)

        print("\n[SUCCESS] Test completed!")

    except KeyboardInterrupt:
        print("\n\n[STOPPED] User interrupted")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        reader.close()

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
