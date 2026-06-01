"""
Serial Port Protocol Sniffer
Captures all communication between Nissan diagnostic software and device
This will help us reverse engineer the Consult-II protocol
"""

import serial
import time
import threading
from datetime import datetime
import os

class SerialSniffer:
    """Sniff serial port communication for protocol analysis"""

    def __init__(self, port='COM5', baudrate=38400, log_dir='C:\\D Drive\\Predict\\protocol_logs'):
        self.port = port
        self.baudrate = baudrate
        self.log_dir = log_dir
        self.running = False
        self.log_file = None
        self.hex_log_file = None

        # Create log directory
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def create_log_files(self):
        """Create timestamped log files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Text log
        text_log_path = os.path.join(self.log_dir, f"consult2_protocol_{timestamp}.txt")
        self.log_file = open(text_log_path, 'w')

        # Hex log
        hex_log_path = os.path.join(self.log_dir, f"consult2_hex_{timestamp}.txt")
        self.hex_log_file = open(hex_log_path, 'w')

        print(f"[LOG] Text log: {text_log_path}")
        print(f"[LOG] Hex log: {hex_log_path}")

        # Write header
        self.log_file.write("="*80 + "\n")
        self.log_file.write("NISSAN CONSULT-II PROTOCOL CAPTURE\n")
        self.log_file.write(f"Date: {datetime.now()}\n")
        self.log_file.write(f"Port: {self.port} @ {self.baudrate} baud\n")
        self.log_file.write("="*80 + "\n\n")

        self.hex_log_file.write("Timestamp,Direction,Hex,ASCII,Decimal\n")

    def log_data(self, direction, data):
        """Log captured data"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Convert to different formats
        hex_str = ' '.join([f'{b:02X}' for b in data])
        ascii_str = ''.join([chr(b) if 32 <= b < 127 else '.' for b in data])
        dec_str = ' '.join([f'{b:3d}' for b in data])

        # Log to text file
        self.log_file.write(f"[{timestamp}] {direction}:\n")
        self.log_file.write(f"  HEX:   {hex_str}\n")
        self.log_file.write(f"  ASCII: {ascii_str}\n")
        self.log_file.write(f"  DEC:   {dec_str}\n")
        self.log_file.write(f"  LEN:   {len(data)} bytes\n\n")
        self.log_file.flush()

        # Log to hex file (CSV format)
        self.hex_log_file.write(f'{timestamp},{direction},{hex_str},{ascii_str},{dec_str}\n')
        self.hex_log_file.flush()

        # Print to console
        print(f"\n[{timestamp}] {direction}:")
        print(f"  HEX:   {hex_str}")
        print(f"  ASCII: {ascii_str}")
        print(f"  DEC:   {dec_str}")

    def start_sniffing(self):
        """Start capturing serial communication"""
        print("="*80)
        print("NISSAN CONSULT-II PROTOCOL SNIFFER")
        print("="*80)
        print()
        print("This tool captures all communication between the diagnostic software")
        print("and your Nisscom device to reverse engineer the protocol.")
        print()
        print("INSTRUCTIONS:")
        print("  1. Keep this window open")
        print("  2. Start your Nissan diagnostic software (NDS, DDLReader, etc.)")
        print("  3. Connect to the car and read some data")
        print("  4. Press Ctrl+C here when done capturing")
        print()
        print(f"Monitoring: {self.port} @ {self.baudrate} baud")
        print()

        try:
            # Open serial port
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            print("[OK] Serial port opened successfully")
            print("[LISTENING] Waiting for data...")
            print()

            self.create_log_files()
            self.running = True

            packet_count = 0
            last_activity = time.time()

            while self.running:
                # Check for incoming data
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    if data:
                        packet_count += 1
                        self.log_data("RECEIVED", data)
                        last_activity = time.time()

                # Show activity indicator
                if time.time() - last_activity > 5:
                    print(f"[IDLE] No data for 5 seconds... (Total packets: {packet_count})", end='\r')

                time.sleep(0.01)

        except serial.SerialException as e:
            print(f"\n[ERROR] Serial port error: {e}")
            print("Make sure the diagnostic software is not running yet!")

        except KeyboardInterrupt:
            print("\n\n[STOPPED] Capture stopped by user")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.log_file:
                self.log_file.close()
            if self.hex_log_file:
                self.hex_log_file.close()

            if ser and ser.is_open:
                ser.close()

            print(f"\n[DONE] Captured {packet_count} packets")
            print("[OK] Logs saved")

    def analyze_logs(self, log_file_path):
        """Analyze captured logs to identify patterns"""
        print("\n" + "="*80)
        print("PROTOCOL ANALYSIS")
        print("="*80)
        print()

        # Read hex log
        with open(log_file_path, 'r') as f:
            lines = f.readlines()[1:]  # Skip header

        if not lines:
            print("No data captured yet.")
            return

        print(f"Total packets captured: {len(lines)}")
        print()

        # Find common patterns
        commands = {}
        responses = {}

        for line in lines:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                direction = parts[1]
                hex_data = parts[2]

                if direction == "SENT":
                    commands[hex_data] = commands.get(hex_data, 0) + 1
                elif direction == "RECEIVED":
                    responses[hex_data] = responses.get(hex_data, 0) + 1

        print("Most common commands sent:")
        for cmd, count in sorted(commands.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {cmd:40} : {count} times")

        print("\nMost common responses received:")
        for resp, count in sorted(responses.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {resp:40} : {count} times")


def main():
    sniffer = SerialSniffer(port='COM5', baudrate=38400)

    print("="*80)
    print("SERIAL PORT PROTOCOL SNIFFER")
    print("="*80)
    print()
    print("Choose mode:")
    print("  1. Start capturing (monitor serial port)")
    print("  2. Analyze existing log")
    print()

    choice = input("Enter choice (1 or 2): ")

    if choice == '1':
        sniffer.start_sniffing()
    elif choice == '2':
        log_file = input("Enter path to hex log file: ")
        if os.path.exists(log_file):
            sniffer.analyze_logs(log_file)
        else:
            print(f"[ERROR] File not found: {log_file}")
    else:
        print("[ERROR] Invalid choice")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
