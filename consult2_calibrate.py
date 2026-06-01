"""
Consult-II Register Scanner
Scans all registers to help identify correct mappings for your specific ECU
"""

import serial
import time

class Consult2Scanner:
    """Scan Consult-II registers to find correct mappings"""

    def __init__(self, port='COM5', baudrate=38400):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        """Connect to device"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            return True
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

    def initialize_ecu(self):
        """Initialize ECU"""
        self.ser.write(bytes([0xFF, 0xFF, 0xEF]))
        time.sleep(0.5)
        response = self.ser.read(self.ser.in_waiting)
        return len(response) > 0

    def read_register(self, addr):
        """Read single register"""
        command = bytes([0x5A, 0x01, addr])
        self.ser.reset_input_buffer()
        self.ser.write(command)
        time.sleep(0.05)

        if self.ser.in_waiting > 0:
            response = self.ser.read(self.ser.in_waiting)
            if len(response) >= 1:
                return response[0]
        return None

    def scan_registers(self, start=0x00, end=0x50):
        """Scan a range of registers"""
        print(f"\nScanning registers 0x{start:02X} to 0x{end:02X}...")
        print("-" * 60)
        print(f"{'Register':>10} | {'Hex':>6} | {'Dec':>6} | {'Possible Meaning'}")
        print("-" * 60)

        results = {}

        for addr in range(start, end + 1):
            value = self.read_register(addr)

            if value is not None:
                results[addr] = value

                # Try to guess what the value might represent
                interpretation = self.interpret_value(value, addr)

                print(f"0x{addr:02X} ({addr:>3}) | 0x{value:02X}  | {value:>5}  | {interpretation}")

            time.sleep(0.02)

        return results

    def interpret_value(self, value, addr):
        """Try to interpret what a value might represent"""
        interpretations = []

        # RPM (typically 0-255, multiply by 12.5 = 0-3187 RPM)
        rpm = value * 12.5
        if 500 <= rpm <= 3000:
            interpretations.append(f"RPM={int(rpm)}")

        # Temperature (typically value - 50 = -50 to 205°C)
        temp = value - 50
        if -20 <= temp <= 150:
            interpretations.append(f"Temp={temp}°C")

        # Speed (direct km/h, 0-255)
        if 0 <= value <= 200:
            interpretations.append(f"Speed={value}km/h")

        # Throttle (0-255 = 0-100%)
        throttle = (value / 255.0) * 100
        if 0 <= throttle <= 100:
            interpretations.append(f"Throttle={throttle:.1f}%")

        # Voltage (value * 0.08 = 0-20V)
        voltage = value * 0.08
        if 10 <= voltage <= 15:
            interpretations.append(f"Battery={voltage:.1f}V")

        return " | ".join(interpretations) if interpretations else "Unknown"

    def monitor_registers(self, registers, duration=10):
        """Monitor specific registers over time to see changes"""
        print(f"\nMonitoring registers for {duration} seconds...")
        print("This helps identify which registers change when you rev engine, etc.")
        print()

        # Print header
        header = f"{'Time':>6} |"
        for reg in registers:
            header += f" 0x{reg:02X} |"
        print(header)
        print("-" * len(header))

        start_time = time.time()
        previous_values = {}

        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            line = f"{elapsed:>5.1f}s |"

            for reg in registers:
                value = self.read_register(reg)
                if value is not None:
                    # Highlight if value changed
                    if reg in previous_values and previous_values[reg] != value:
                        line += f" *{value:>3} |"
                    else:
                        line += f"  {value:>3} |"
                    previous_values[reg] = value
                else:
                    line += "  N/A |"

            print(line)
            time.sleep(0.5)

    def close(self):
        """Close connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    print("=" * 60)
    print("CONSULT-II REGISTER SCANNER")
    print("Helps identify correct register mappings for your ECU")
    print("=" * 60)
    print()

    scanner = Consult2Scanner()

    print("Connecting...")
    if not scanner.connect():
        print("[FAILED] Could not connect")
        input("Press Enter to exit...")
        return

    print("[OK] Connected")

    print("Initializing ECU...")
    if scanner.initialize_ecu():
        print("[OK] ECU initialized")
    else:
        print("[WARNING] Init unclear, continuing...")

    # Scan first 80 registers
    results = scanner.scan_registers(start=0x00, end=0x50)

    print()
    print("=" * 60)
    print(f"Found {len(results)} responding registers")
    print()

    # Ask user which registers to monitor
    print("Based on the scan above, likely important registers are:")
    print("  0x00 - Might be RPM")
    print("  0x08 - Might be Coolant Temperature")
    print("  0x0B - Might be Vehicle Speed")
    print("  0x0C - Might be Battery Voltage")
    print("  0x0D - Might be Throttle Position")
    print()
    print("Now monitoring these registers...")
    print("Try revving the engine to see which values change!")
    print()

    # Monitor key registers
    key_registers = [0x00, 0x01, 0x08, 0x0B, 0x0C, 0x0D, 0x0E, 0x11]
    scanner.monitor_registers(key_registers, duration=15)

    scanner.close()
    print()
    print("[OK] Scan complete")
    print()
    print("Analysis:")
    print("  - Registers marked with * changed during monitoring")
    print("  - RPM should change if you rev the engine")
    print("  - Throttle should change when you press gas pedal")
    print("  - Speed should be 0 if car is stationary")
    print()

    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
