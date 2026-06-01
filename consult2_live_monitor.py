"""
Nissan Consult-II Live Monitor
Real-time monitoring with data logging for Nissan Patrol 2003
"""

import serial
import time
from datetime import datetime
import csv
import os

class Consult2Monitor:
    """Enhanced Consult-II monitor with logging"""

    # Register addresses (may need calibration for specific models)
    REGISTERS = {
        'RPM': 0x00,
        'COOLANT_TEMP': 0x08,
        'VEHICLE_SPEED': 0x0B,
        'BATTERY_VOLTAGE': 0x0C,
        'THROTTLE_POSITION': 0x0D,
        'ENGINE_LOAD': 0x0E,
        'FUEL_TEMP': 0x0F,
        'INTAKE_TEMP': 0x11,
        'AIR_FLOW': 0x12,
        'TIMING': 0x13,
    }

    def __init__(self, port='COM5', baudrate=38400):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.log_file = None

    def connect(self):
        """Connect to the device"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def send_command(self, command):
        """Send command to ECU"""
        if isinstance(command, list):
            command = bytes(command)
        self.ser.write(command)
        time.sleep(0.05)

    def read_response(self, num_bytes=3):
        """Read response from ECU"""
        time.sleep(0.05)
        available = self.ser.in_waiting
        if available > 0:
            return self.ser.read(min(available, num_bytes))
        return b''

    def initialize_ecu(self):
        """Initialize ECU communication"""
        self.send_command([0xFF, 0xFF, 0xEF])
        response = self.read_response()
        return len(response) > 0 if response else False

    def read_register(self, register_addr):
        """Read a register value"""
        command = [0x5A, 0x01, register_addr]
        self.ser.reset_input_buffer()
        self.send_command(command)
        response = self.read_response(3)

        if response and len(response) >= 1:
            return response[0]
        return None

    def decode_rpm(self, value):
        """Decode RPM"""
        return int(value * 12.5) if value is not None else None

    def decode_temperature(self, value):
        """Decode temperature"""
        return value - 50 if value is not None else None

    def decode_speed(self, value):
        """Decode speed (km/h)"""
        return value if value is not None else None

    def decode_throttle(self, value):
        """Decode throttle position (%)"""
        return round((value / 255.0) * 100, 1) if value is not None else None

    def decode_voltage(self, value):
        """Decode battery voltage"""
        return round(value * 0.08, 1) if value is not None else None

    def create_log_file(self):
        """Create CSV log file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = "C:\\D Drive\\Predict\\consult2_logs"

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        filename = os.path.join(log_dir, f"nissan_patrol_{timestamp}.csv")
        self.log_file = open(filename, 'w', newline='')

        writer = csv.writer(self.log_file)
        writer.writerow([
            'Timestamp', 'RPM', 'Speed (km/h)', 'Coolant Temp (C)',
            'Throttle (%)', 'Battery (V)', 'Intake Temp (C)'
        ])

        print(f"[LOG] Logging to: {filename}")
        return writer

    def log_data(self, writer, data):
        """Log data to CSV file"""
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get('RPM', 'N/A'),
            data.get('Speed', 'N/A'),
            data.get('Coolant Temp', 'N/A'),
            data.get('Throttle', 'N/A'),
            data.get('Battery Voltage', 'N/A'),
            data.get('Intake Temp', 'N/A')
        ])
        self.log_file.flush()

    def read_all_parameters(self):
        """Read all available parameters"""
        data = {}

        # Read RPM
        rpm_raw = self.read_register(self.REGISTERS['RPM'])
        if rpm_raw is not None:
            data['RPM'] = self.decode_rpm(rpm_raw)

        # Read Coolant Temperature
        temp_raw = self.read_register(self.REGISTERS['COOLANT_TEMP'])
        if temp_raw is not None:
            data['Coolant Temp'] = self.decode_temperature(temp_raw)

        # Read Vehicle Speed
        speed_raw = self.read_register(self.REGISTERS['VEHICLE_SPEED'])
        if speed_raw is not None:
            data['Speed'] = self.decode_speed(speed_raw)

        # Read Throttle Position
        throttle_raw = self.read_register(self.REGISTERS['THROTTLE_POSITION'])
        if throttle_raw is not None:
            data['Throttle'] = self.decode_throttle(throttle_raw)

        # Read Battery Voltage
        battery_raw = self.read_register(self.REGISTERS['BATTERY_VOLTAGE'])
        if battery_raw is not None:
            data['Battery Voltage'] = self.decode_voltage(battery_raw)

        # Read Intake Air Temperature
        intake_raw = self.read_register(self.REGISTERS['INTAKE_TEMP'])
        if intake_raw is not None:
            data['Intake Temp'] = self.decode_temperature(intake_raw)

        return data

    def display_data(self, data, elapsed):
        """Display data in console"""
        rpm = data.get('RPM', 'N/A')
        speed = data.get('Speed', 'N/A')
        temp = data.get('Coolant Temp', 'N/A')
        throttle = data.get('Throttle', 'N/A')
        voltage = data.get('Battery Voltage', 'N/A')
        intake = data.get('Intake Temp', 'N/A')

        print(f"{elapsed:>6.1f}s | {str(rpm):>6} | {str(speed):>6} | {str(temp):>7} | {str(throttle):>7} | {str(voltage):>6} | {str(intake):>7}")

    def continuous_monitor(self, duration=60):
        """Continuously monitor and log data"""
        print("\n" + "=" * 80)
        print(f"LIVE MONITORING ({duration} seconds)")
        print("=" * 80)
        print()
        print(f"{'Time':>6} | {'RPM':>6} | {'Speed':>6} | {'Coolant':>7} | {'Throttle':>7} | {'Battery':>6} | {'Intake':>7}")
        print(f"{'(s)':>6} | {'':>6} | {'km/h':>6} | {'C':>7} | {'%':>7} | {'V':>6} | {'C':>7}")
        print("-" * 80)

        csv_writer = self.create_log_file()
        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time

                # Read all parameters
                data = self.read_all_parameters()

                # Display
                self.display_data(data, elapsed)

                # Log to CSV
                self.log_data(csv_writer, data)

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[STOPPED] Monitoring stopped by user")

        finally:
            if self.log_file:
                self.log_file.close()
                print("\n[LOG] Data saved to file")

    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    print("=" * 80)
    print("NISSAN CONSULT-II LIVE MONITOR")
    print("Nissan Patrol 2003")
    print("=" * 80)
    print()
    print("This will monitor your car for 60 seconds and save data to CSV file")
    print()
    print("REQUIREMENTS:")
    print("  - Car ignition ON (engine can be off or running)")
    print("  - Device connected to OBD-II port")
    print()
    print("Press Ctrl+C anytime to stop monitoring")
    print()

    # Create monitor
    monitor = Consult2Monitor(port='COM5', baudrate=38400)

    # Connect
    print("Connecting to device...")
    if not monitor.connect():
        print("[FAILED] Could not connect")
        input("Press Enter to exit...")
        return

    print("[OK] Connected to COM5")

    # Initialize ECU
    print("Initializing ECU...")
    if monitor.initialize_ecu():
        print("[OK] ECU initialized")
    else:
        print("[WARNING] ECU init unclear, continuing anyway...")

    print()

    # Read initial values
    print("Reading initial values...")
    data = monitor.read_all_parameters()

    if data:
        print("\nCurrent readings:")
        for key, value in data.items():
            print(f"  {key:20} : {value}")

    print()

    try:
        # Start monitoring
        monitor.continuous_monitor(duration=60)

        print("\n[SUCCESS] Monitoring completed!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        monitor.close()
        print("[OK] Connection closed")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
