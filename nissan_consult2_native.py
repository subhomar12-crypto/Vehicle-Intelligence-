"""
Nissan Consult-II Protocol Implementation
Based on open-source reverse engineering and community documentation

Protocol Details:
- Baud Rate: 9600
- Init Sequence: FF FF EF (expects 10 response)
- Commands use inverted acknowledgment
- Register-based sensor reading

References:
- https://github.com/Crim/Arduino-Nissan-Consult-Library
- https://github.com/fridlington/K11Consult
- https://github.com/jonsim/openconsult
"""

import serial
import time
from typing import Optional, Dict, List

class NissanConsult2:
    """Native Nissan Consult-II protocol implementation"""

    # Protocol Commands
    CMD_INIT = [0xFF, 0xFF, 0xEF]
    CMD_READ_REGISTER = 0x5A
    CMD_ECU_INFO = 0xD0
    CMD_SELF_DIAG = 0xD1
    CMD_CLEAR_CODES = 0xC1
    CMD_STOP_STREAM = 0x30
    CMD_TERM = 0xF0

    # Common Register Addresses (MSB, LSB pairs)
    # These vary by ECU model - may need adjustment for Patrol 2003
    REGISTERS = {
        'RPM': (0x00, 0x01),          # Engine RPM (2 bytes)
        'COOLANT_TEMP': (0x08, None),  # Coolant temperature (1 byte)
        'VEHICLE_SPEED': (0x0B, None), # Vehicle speed km/h (1 byte)
        'BATTERY_VOLTAGE': (0x0C, None), # Battery voltage (1 byte)
        'THROTTLE_POS': (0x0D, None),  # Throttle position (1 byte)
        'ENGINE_LOAD': (0x13, None),   # Engine load (1 byte)
        'MAF_VOLTAGE': (0x12, None),   # MAF sensor voltage (1 byte)
        'INTAKE_TEMP': (0x11, None),   # Intake air temp (1 byte)
        'FUEL_TEMP': (0x0F, None),     # Fuel temperature (1 byte)
        'TIMING_ADVANCE': (0x13, None), # Ignition timing (1 byte)
    }

    def __init__(self, port='COM5', baudrate=9600, timeout=1):
        """Initialize Consult-II interface"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.connected = False

    def connect(self):
        """Connect to Consult-II interface"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            print(f"[OK] Port opened: {self.port} @ {self.baudrate} baud")
            time.sleep(0.5)

            # Try to initialize ECU
            if self.initialize_ecu():
                self.connected = True
                print("[OK] ECU initialized successfully")
                return True
            else:
                print("[FAILED] Could not initialize ECU")
                return False

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def initialize_ecu(self):
        """Initialize communication with ECU"""
        print("[INIT] Initializing ECU...")

        # Stop any existing stream
        self.stop_stream()
        time.sleep(0.2)

        # Send init sequence: FF FF EF
        for attempt in range(3):
            print(f"  Attempt {attempt + 1}/3...")

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Send init command
            self.ser.write(bytes(self.CMD_INIT))
            time.sleep(0.5)

            # Read response
            response = self.ser.read(10)

            if response:
                print(f"  Response: {response.hex()}")
                # Looking for 0x10 response
                if 0x10 in response:
                    print("  [OK] ECU acknowledged")
                    return True

        print("  [FAILED] No valid response from ECU")
        return False

    def stop_stream(self):
        """Stop any active data stream"""
        try:
            self.ser.write(bytes([self.CMD_STOP_STREAM]))
            time.sleep(0.1)
            self.ser.reset_input_buffer()
        except:
            pass

    def read_register(self, msb_addr: int, lsb_addr: Optional[int] = None) -> Optional[int]:
        """
        Read a register value from ECU

        Args:
            msb_addr: MSB register address
            lsb_addr: LSB register address (if 2-byte value)

        Returns:
            Register value or None if failed
        """
        try:
            # Build command
            command = [self.CMD_READ_REGISTER, msb_addr]

            if lsb_addr is not None:
                command.append(lsb_addr)

            command.append(self.CMD_TERM)

            # Send command
            self.ser.reset_input_buffer()
            self.ser.write(bytes(command))
            time.sleep(0.1)

            # Read response
            # Expected: inverted command, then 0xFF, then byte count, then data
            response = self.ser.read(20)

            if not response:
                return None

            # Parse response
            # Look for 0xFF frame marker
            try:
                ff_index = response.index(0xFF)
                # Next byte is count, then data
                if ff_index + 2 < len(response):
                    count = response[ff_index + 1]

                    if lsb_addr is not None:
                        # 2-byte value (MSB, LSB)
                        if ff_index + 3 < len(response):
                            msb = response[ff_index + 2]
                            lsb = response[ff_index + 3]
                            return (msb << 8) | lsb
                    else:
                        # 1-byte value
                        return response[ff_index + 2]
            except ValueError:
                # 0xFF not found, try reading raw
                if len(response) >= 1:
                    return response[0]

            return None

        except Exception as e:
            print(f"[ERROR] Read register failed: {e}")
            return None

    def read_rpm(self) -> Optional[int]:
        """Read engine RPM"""
        msb, lsb = self.REGISTERS['RPM']
        raw_value = self.read_register(msb, lsb)

        if raw_value is not None:
            # RPM = raw_value / 4 (typical Nissan scaling)
            return int(raw_value / 4)
        return None

    def read_coolant_temp(self) -> Optional[int]:
        """Read coolant temperature in Celsius"""
        msb, _ = self.REGISTERS['COOLANT_TEMP']
        raw_value = self.read_register(msb)

        if raw_value is not None:
            # Temperature = raw - 50 (typical offset)
            return raw_value - 50
        return None

    def read_vehicle_speed(self) -> Optional[int]:
        """Read vehicle speed in km/h"""
        msb, _ = self.REGISTERS['VEHICLE_SPEED']
        return self.read_register(msb)

    def read_battery_voltage(self) -> Optional[float]:
        """Read battery voltage"""
        msb, _ = self.REGISTERS['BATTERY_VOLTAGE']
        raw_value = self.read_register(msb)

        if raw_value is not None:
            # Voltage = raw * 0.08 (typical scaling)
            return round(raw_value * 0.08, 1)
        return None

    def read_throttle_position(self) -> Optional[float]:
        """Read throttle position as percentage"""
        msb, _ = self.REGISTERS['THROTTLE_POS']
        raw_value = self.read_register(msb)

        if raw_value is not None:
            # Throttle = (raw / 255) * 100
            return round((raw_value / 255.0) * 100, 1)
        return None

    def read_intake_temp(self) -> Optional[int]:
        """Read intake air temperature in Celsius"""
        msb, _ = self.REGISTERS['INTAKE_TEMP']
        raw_value = self.read_register(msb)

        if raw_value is not None:
            return raw_value - 50
        return None

    def read_all_sensors(self) -> Dict[str, any]:
        """Read all available sensors"""
        data = {}

        print("\nReading all sensors...")

        # RPM
        rpm = self.read_rpm()
        if rpm is not None:
            data['rpm'] = rpm
            print(f"  RPM: {rpm}")

        # Coolant Temperature
        coolant_temp = self.read_coolant_temp()
        if coolant_temp is not None:
            data['coolant_temp'] = coolant_temp
            print(f"  Coolant Temp: {coolant_temp}°C")

        # Vehicle Speed
        speed = self.read_vehicle_speed()
        if speed is not None:
            data['speed'] = speed
            print(f"  Speed: {speed} km/h")

        # Battery Voltage
        voltage = self.read_battery_voltage()
        if voltage is not None:
            data['battery_voltage'] = voltage
            print(f"  Battery: {voltage}V")

        # Throttle Position
        throttle = self.read_throttle_position()
        if throttle is not None:
            data['throttle'] = throttle
            print(f"  Throttle: {throttle}%")

        # Intake Temperature
        intake_temp = self.read_intake_temp()
        if intake_temp is not None:
            data['intake_temp'] = intake_temp
            print(f"  Intake Temp: {intake_temp}°C")

        return data

    def continuous_monitor(self, duration=60):
        """Continuously monitor sensors"""
        print(f"\n{'='*70}")
        print(f"CONTINUOUS MONITORING ({duration} seconds)")
        print(f"{'='*70}\n")

        print(f"{'Time':>6} | {'RPM':>6} | {'Speed':>7} | {'Coolant':>8} | {'Throttle':>9} | {'Battery':>8}")
        print(f"{'(s)':>6} | {'':>6} | {'km/h':>7} | {'°C':>8} | {'%':>9} | {'V':>8}")
        print("-" * 70)

        start_time = time.time()

        while time.time() - start_time < duration:
            elapsed = time.time() - start_time

            # Read key sensors
            rpm = self.read_rpm() or "N/A"
            speed = self.read_vehicle_speed() or "N/A"
            temp = self.read_coolant_temp() or "N/A"
            throttle = self.read_throttle_position() or "N/A"
            voltage = self.read_battery_voltage() or "N/A"

            print(f"{elapsed:>5.1f}s | {str(rpm):>6} | {str(speed):>6} | {str(temp):>7} | {str(throttle):>8} | {str(voltage):>7}")

            time.sleep(1)

    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.stop_stream()
            self.ser.close()
            print("\n[OK] Connection closed")


def main():
    print("="*70)
    print("NISSAN CONSULT-II NATIVE PROTOCOL")
    print("Nissan Patrol 2003")
    print("="*70)
    print()
    print("Using native protocol implementation")
    print("Baud Rate: 9600")
    print()
    print("REQUIREMENTS:")
    print("  - Car ignition ON")
    print("  - Device connected to OBD-II port")
    print()

    # Create Consult-II instance
    consult = NissanConsult2(port='COM5', baudrate=9600)

    # Connect
    if not consult.connect():
        print("\n[FAILED] Could not connect to ECU")
        print("\nTroubleshooting:")
        print("  1. Is car ignition ON?")
        print("  2. Is device properly connected?")
        print("  3. Try unplugging and reconnecting device")
        input("\nPress Enter to exit...")
        return

    try:
        # Read all sensors once
        data = consult.read_all_sensors()

        if data:
            print(f"\n[SUCCESS] Read {len(data)} sensors!")

            # Ask for continuous monitoring
            print()
            choice = input("Start continuous monitoring? (y/n): ")

            if choice.lower() == 'y':
                consult.continuous_monitor(duration=60)

        else:
            print("\n[WARNING] No sensor data received")
            print("ECU may not be responding properly")

    except KeyboardInterrupt:
        print("\n\n[STOPPED] Monitoring stopped by user")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        consult.close()

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
