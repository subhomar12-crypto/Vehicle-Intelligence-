"""
Nisscom Protocol Sniffer (Enhanced)
Captures communication between Nisscom software and device
Run this BEFORE launching the Nisscom software

Usage:
1. Run this script
2. Launch Nisscom software
3. Connect to vehicle in Nisscom software
4. Let it read some data
5. Press Ctrl+C to stop
6. Check the log files for captured protocol
"""

import serial
import time
import threading
from datetime import datetime
import os
import sys

class ProtocolSniffer:
    """Sniff serial port communication"""

    def __init__(self, port='COM5', baudrate=None):
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.log_dir = r"C:\D Drive\Predict\nisscom_logs"
        self.log_file = None
        self.csv_file = None
        self.ser = None

        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0

    def setup_logging(self):
        """Setup log files"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Text log
        log_path = os.path.join(self.log_dir, f"nisscom_capture_{timestamp}.txt")
        self.log_file = open(log_path, 'w', encoding='utf-8')

        # CSV log
        csv_path = os.path.join(self.log_dir, f"nisscom_capture_{timestamp}.csv")
        self.csv_file = open(csv_path, 'w', encoding='utf-8')
        self.csv_file.write("Timestamp,Direction,Hex,ASCII,Decimal,Length\n")

        print(f"[LOG] Text log: {log_path}")
        print(f"[LOG] CSV log: {csv_path}")

        return log_path, csv_path

    def detect_baudrate(self):
        """Try to detect baudrate by monitoring activity"""
        print("\n[DETECT] Trying to detect baudrate...")
        print("  Please perform an action in Nisscom software now...")

        baud_rates = [9600, 19200, 38400, 57600, 115200]

        for baud in baud_rates:
            print(f"  Testing {baud} baud...")
            try:
                ser = serial.Serial(
                    self.port,
                    baudrate=baud,
                    timeout=0.5
                )
                time.sleep(1)

                # Check for activity
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    print(f"    [ACTIVITY] Detected {len(data)} bytes!")
                    ser.close()
                    return baud

                ser.close()
            except:
                pass

        print("  [INFO] No activity detected, defaulting to 38400")
        return 38400

    def log_data(self, direction, data):
        """Log captured data"""
        if not data:
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Convert to different formats
        hex_str = ' '.join([f'{b:02X}' for b in data])
        ascii_str = ''.join([chr(b) if 32 <= b < 127 else '.' for b in data])
        dec_str = ' '.join([f'{b:03d}' for b in data])

        # Update statistics
        if direction == "SEND":
            self.bytes_sent += len(data)
            self.packets_sent += 1
        else:
            self.bytes_received += len(data)
            self.packets_received += 1

        # Write to text log
        self.log_file.write(f"\n[{timestamp}] {direction} ({len(data)} bytes)\n")
        self.log_file.write(f"  HEX: {hex_str}\n")
        self.log_file.write(f"  ASC: {ascii_str}\n")
        self.log_file.write(f"  DEC: {dec_str}\n")
        self.log_file.flush()

        # Write to CSV
        self.csv_file.write(f'"{timestamp}","{direction}","{hex_str}","{ascii_str}","{dec_str}",{len(data)}\n')
        self.csv_file.flush()

        # Console output
        direction_symbol = ">>>" if direction == "SEND" else "<<<"
        print(f"[{timestamp}] {direction_symbol} {hex_str}")

    def monitor(self):
        """Monitor serial port"""
        print("\n" + "=" * 70)
        print("[MONITORING] Capturing protocol...")
        print("Perform actions in Nisscom software now")
        print("Press Ctrl+C to stop")
        print("=" * 70 + "\n")

        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=0.01  # Very short timeout for responsive monitoring
            )

            last_activity = time.time()
            idle_reported = False

            while self.running:
                # Check for incoming data
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.log_data("RECV", data)
                    last_activity = time.time()
                    idle_reported = False

                # Check for outgoing data (this won't capture data sent by other software,
                # but will show if we send anything)

                # Check for idle
                idle_time = time.time() - last_activity
                if idle_time > 5 and not idle_reported:
                    print(f"\n[INFO] Idle for {int(idle_time)}s - waiting for activity...\n")
                    idle_reported = True

                time.sleep(0.001)  # Small delay to prevent CPU spinning

        except serial.SerialException as e:
            print(f"\n[ERROR] Serial port error: {e}")
            print("  Make sure Nisscom software is NOT open yet")
            print("  Run this sniffer FIRST, then open Nisscom software")
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def print_statistics(self):
        """Print capture statistics"""
        print("\n" + "=" * 70)
        print("CAPTURE STATISTICS")
        print("=" * 70)
        print(f"  Packets Sent:     {self.packets_sent}")
        print(f"  Packets Received: {self.packets_received}")
        print(f"  Bytes Sent:       {self.bytes_sent}")
        print(f"  Bytes Received:   {self.bytes_received}")
        print(f"  Total Packets:    {self.packets_sent + self.packets_received}")
        print(f"  Total Bytes:      {self.bytes_sent + self.bytes_received}")
        print("=" * 70)

    def analyze_capture(self):
        """Basic analysis of captured data"""
        if self.bytes_received == 0:
            print("\n[WARNING] No data was captured!")
            print("  Make sure:")
            print("    1. This sniffer was running BEFORE opening Nisscom software")
            print("    2. You performed actions in Nisscom software (connect, read data)")
            print("    3. The correct COM port was selected")
            return

        print("\n" + "=" * 70)
        print("BASIC PROTOCOL ANALYSIS")
        print("=" * 70)
        print("  Review the log files for:")
        print("    - Initialization sequence (first packets)")
        print("    - Repeated patterns (register read commands)")
        print("    - Response format (how ECU responds)")
        print("    - Command structure (command bytes, data bytes, checksums)")
        print("=" * 70)

    def start(self):
        """Start sniffing"""
        print("=" * 70)
        print("NISSCOM PROTOCOL SNIFFER")
        print("=" * 70)
        print(f"\nPort: {self.port}")

        # Setup logging
        txt_log, csv_log = self.setup_logging()

        # Detect or use baudrate
        if self.baudrate is None:
            self.baudrate = self.detect_baudrate()

        print(f"Baudrate: {self.baudrate}")

        print("\nIMPORTANT INSTRUCTIONS:")
        print("  1. This sniffer must be running BEFORE you open Nisscom software")
        print("  2. After starting capture, open Nisscom software")
        print("  3. Connect to your vehicle in Nisscom software")
        print("  4. Perform some actions (read sensors, etc.)")
        print("  5. Return here and press Ctrl+C to stop capture")
        print("\nWaiting 3 seconds before starting capture...")
        time.sleep(3)

        self.running = True

        try:
            self.monitor()
        except KeyboardInterrupt:
            print("\n\n[STOPPED] Stopping capture...")
            self.running = False
        finally:
            # Cleanup
            if self.log_file:
                self.log_file.close()
            if self.csv_file:
                self.csv_file.close()

            # Print statistics
            self.print_statistics()
            self.analyze_capture()

            print(f"\n[DONE] Logs saved to:")
            print(f"  Text: {txt_log}")
            print(f"  CSV:  {csv_log}")


def main():
    # Check arguments
    port = 'COM5'
    baudrate = None  # Auto-detect

    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baudrate = int(sys.argv[2])

    # Create sniffer
    sniffer = ProtocolSniffer(port=port, baudrate=baudrate)

    try:
        sniffer.start()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
