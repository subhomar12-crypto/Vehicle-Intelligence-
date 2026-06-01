"""
Nisscom COM Port Bridge with Protocol Capture
==============================================

This script creates a bridge between a virtual COM port and the real Nisscom device,
capturing all traffic that passes through.

Architecture:
  Nisscom Software -> Virtual COM10 ↔ This Bridge ↔ Real COM5 -> Device -> Car

Usage:
  1. Install com0com to create virtual COM port pair (COM10 <-> COM11)
  2. Run this script: python nisscom_com_bridge.py
  3. Configure Nisscom software to use COM10
  4. Connect to vehicle in Nisscom software
  5. All traffic will be logged while being forwarded

The bridge is completely transparent - Nisscom software thinks it's talking
directly to COM5, but we capture everything in between.
"""

import serial
import threading
import time
from datetime import datetime
import os
import sys

class COMBridge:
    """Transparent COM port bridge with logging"""

    def __init__(self, virtual_port='COM11', real_port='COM5', baudrate=38400):
        """
        Args:
            virtual_port: The virtual COM port we'll connect to (pair of the one Nisscom uses)
            real_port: The real COM port where device is connected
            baudrate: Initial baudrate (will try to auto-detect if connection fails)
        """
        self.virtual_port = virtual_port
        self.real_port = real_port
        self.baudrate = baudrate

        self.virtual_ser = None
        self.real_ser = None

        self.running = False
        self.log_dir = r"C:\D Drive\Predict\nisscom_logs"
        self.log_file = None
        self.csv_file = None

        # Statistics
        self.bytes_to_device = 0
        self.bytes_from_device = 0
        self.packets_to_device = 0
        self.packets_from_device = 0

        # Threads
        self.virtual_to_real_thread = None
        self.real_to_virtual_thread = None

    def setup_logging(self):
        """Setup log files"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Text log
        log_path = os.path.join(self.log_dir, f"bridge_capture_{timestamp}.txt")
        self.log_file = open(log_path, 'w', encoding='utf-8')

        # CSV log
        csv_path = os.path.join(self.log_dir, f"bridge_capture_{timestamp}.csv")
        self.csv_file = open(csv_path, 'w', encoding='utf-8')
        self.csv_file.write("Timestamp,Direction,Hex,ASCII,Decimal,Length\n")

        print(f"[LOG] Text log: {log_path}")
        print(f"[LOG] CSV log:  {csv_path}")

        # Write header to text log
        self.log_file.write("=" * 80 + "\n")
        self.log_file.write("NISSCOM PROTOCOL CAPTURE VIA COM BRIDGE\n")
        self.log_file.write("=" * 80 + "\n")
        self.log_file.write(f"Capture started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_file.write(f"Virtual port: {self.virtual_port}\n")
        self.log_file.write(f"Real port:    {self.real_port}\n")
        self.log_file.write(f"Baudrate:     {self.baudrate}\n")
        self.log_file.write("=" * 80 + "\n\n")
        self.log_file.flush()

        return log_path, csv_path

    def log_data(self, direction, data):
        """Log captured data"""
        if not data or len(data) == 0:
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Convert to different formats
        hex_str = ' '.join([f'{b:02X}' for b in data])
        ascii_str = ''.join([chr(b) if 32 <= b < 127 else '.' for b in data])
        dec_str = ' '.join([f'{b:03d}' for b in data])

        # Update statistics
        if direction == "TO_DEVICE":
            self.bytes_to_device += len(data)
            self.packets_to_device += 1
            direction_label = "PC->DEV"
            direction_symbol = ">>>"
        else:  # FROM_DEVICE
            self.bytes_from_device += len(data)
            self.packets_from_device += 1
            direction_label = "DEV->PC"
            direction_symbol = "<<<"

        # Write to text log
        self.log_file.write(f"\n[{timestamp}] {direction_label} ({len(data)} bytes)\n")
        self.log_file.write(f"  HEX: {hex_str}\n")
        self.log_file.write(f"  ASC: {ascii_str}\n")
        self.log_file.write(f"  DEC: {dec_str}\n")
        self.log_file.flush()

        # Write to CSV
        self.csv_file.write(f'"{timestamp}","{direction_label}","{hex_str}","{ascii_str}","{dec_str}",{len(data)}\n')
        self.csv_file.flush()

        # Console output with color coding
        print(f"[{timestamp}] {direction_symbol} {hex_str}")

    def forward_virtual_to_real(self):
        """Forward data from virtual port to real device (PC -> Device)"""
        print("[THREAD] Virtual->Real forwarder started")

        try:
            while self.running:
                if self.virtual_ser and self.virtual_ser.is_open and self.virtual_ser.in_waiting > 0:
                    # Read from virtual port (data from Nisscom software)
                    data = self.virtual_ser.read(self.virtual_ser.in_waiting)

                    # Log it
                    self.log_data("TO_DEVICE", data)

                    # Forward to real device
                    if self.real_ser and self.real_ser.is_open:
                        self.real_ser.write(data)
                        self.real_ser.flush()

                time.sleep(0.001)  # Small delay to prevent CPU spinning

        except Exception as e:
            print(f"[ERROR] Virtual->Real thread error: {e}")
            self.running = False

    def forward_real_to_virtual(self):
        """Forward data from real device to virtual port (Device -> PC)"""
        print("[THREAD] Real->Virtual forwarder started")

        try:
            while self.running:
                if self.real_ser and self.real_ser.is_open and self.real_ser.in_waiting > 0:
                    # Read from real device (data from car)
                    data = self.real_ser.read(self.real_ser.in_waiting)

                    # Log it
                    self.log_data("FROM_DEVICE", data)

                    # Forward to virtual port (to Nisscom software)
                    if self.virtual_ser and self.virtual_ser.is_open:
                        self.virtual_ser.write(data)
                        self.virtual_ser.flush()

                time.sleep(0.001)  # Small delay to prevent CPU spinning

        except Exception as e:
            print(f"[ERROR] Real->Virtual thread error: {e}")
            self.running = False

    def try_baudrates(self):
        """Try different baudrates to find the right one"""
        baudrates = [38400, 9600, 19200, 57600, 115200]

        for baud in baudrates:
            try:
                print(f"[DETECT] Trying {baud} baud...")

                # Try to open real port
                test_ser = serial.Serial(
                    self.real_port,
                    baudrate=baud,
                    timeout=1
                )
                test_ser.close()

                self.baudrate = baud
                print(f"[DETECT] Successfully opened port at {baud} baud")
                return True

            except serial.SerialException:
                continue

        return False

    def start(self):
        """Start the bridge"""
        print("=" * 80)
        print("NISSCOM COM PORT BRIDGE")
        print("=" * 80)
        print(f"\nVirtual Port: {self.virtual_port} (connect Nisscom software here)")
        print(f"Real Port:    {self.real_port} (Nisscom device)")
        print(f"Initial Baud: {self.baudrate}")
        print()

        # Setup logging
        txt_log, csv_log = self.setup_logging()

        # Try to open ports
        try:
            print("[CONNECT] Opening real port (Nisscom device)...")
            self.real_ser = serial.Serial(
                self.real_port,
                baudrate=self.baudrate,
                timeout=0.01
            )
            print(f"[CONNECT] OK Real port {self.real_port} opened at {self.baudrate} baud")

        except serial.SerialException as e:
            print(f"[ERROR] Failed to open real port {self.real_port}: {e}")
            print("\nTrying to detect correct baudrate...")
            if self.try_baudrates():
                try:
                    self.real_ser = serial.Serial(
                        self.real_port,
                        baudrate=self.baudrate,
                        timeout=0.01
                    )
                    print(f"[CONNECT] OK Real port opened at {self.baudrate} baud")
                except:
                    print("[ERROR] Still failed. Check if device is connected.")
                    return
            else:
                print("[ERROR] Could not open real port. Is device connected?")
                return

        try:
            print(f"[CONNECT] Opening virtual port {self.virtual_port}...")
            self.virtual_ser = serial.Serial(
                self.virtual_port,
                baudrate=self.baudrate,
                timeout=0.01
            )
            print(f"[CONNECT] OK Virtual port {self.virtual_port} opened")

        except serial.SerialException as e:
            print(f"[ERROR] Failed to open virtual port {self.virtual_port}: {e}")
            print("\nMake sure:")
            print("  1. com0com is installed")
            print("  2. Virtual COM port pair is created (e.g., COM10 <-> COM11)")
            print("  3. You're using the correct port number")
            if self.real_ser:
                self.real_ser.close()
            return

        print("\n" + "=" * 80)
        print("BRIDGE ACTIVE - All traffic will be captured and forwarded")
        print("=" * 80)
        print("\nInstructions:")
        print(f"  1. Open Nisscom software")
        print(f"  2. Configure it to use COM{self.virtual_port.replace('COM', '')}")
        print(f"     (NOT COM5 - use the virtual port!)")
        print("  3. Connect to vehicle")
        print("  4. Read sensors, perform diagnostics")
        print("  5. Press Ctrl+C here when done to stop and analyze")
        print("\nWaiting for Nisscom software to connect...")
        print("-" * 80)

        # Start forwarding
        self.running = True

        self.virtual_to_real_thread = threading.Thread(target=self.forward_virtual_to_real, daemon=True)
        self.real_to_virtual_thread = threading.Thread(target=self.forward_real_to_virtual, daemon=True)

        self.virtual_to_real_thread.start()
        self.real_to_virtual_thread.start()

        try:
            # Keep running until Ctrl+C
            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n[STOPPED] Stopping bridge...")
            self.running = False

        finally:
            # Wait for threads to finish
            if self.virtual_to_real_thread:
                self.virtual_to_real_thread.join(timeout=2)
            if self.real_to_virtual_thread:
                self.real_to_virtual_thread.join(timeout=2)

            # Close ports
            if self.virtual_ser and self.virtual_ser.is_open:
                self.virtual_ser.close()
                print("[DISCONNECT] Virtual port closed")

            if self.real_ser and self.real_ser.is_open:
                self.real_ser.close()
                print("[DISCONNECT] Real port closed")

            # Close logs
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

    def print_statistics(self):
        """Print capture statistics"""
        print("\n" + "=" * 80)
        print("CAPTURE STATISTICS")
        print("=" * 80)
        print(f"  Packets PC->Device:     {self.packets_to_device}")
        print(f"  Packets Device->PC:     {self.packets_from_device}")
        print(f"  Bytes PC->Device:       {self.bytes_to_device}")
        print(f"  Bytes Device->PC:       {self.bytes_from_device}")
        print(f"  Total Packets:         {self.packets_to_device + self.packets_from_device}")
        print(f"  Total Bytes:           {self.bytes_to_device + self.bytes_from_device}")
        print("=" * 80)

    def analyze_capture(self):
        """Basic analysis of captured data"""
        if self.bytes_to_device == 0 and self.bytes_from_device == 0:
            print("\n[WARNING] No data was captured!")
            print("  Make sure:")
            print("    1. Nisscom software was configured to use the virtual port")
            print("    2. You connected to the vehicle in Nisscom software")
            print("    3. You performed some actions (read sensors, etc.)")
            return

        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("  1. Review the log files to understand the protocol")
        print("  2. Look for:")
        print("     - Initialization sequence (first packets)")
        print("     - Command patterns (repeated sequences)")
        print("     - Response format (how device answers)")
        print("     - Data encoding (how sensor values are encoded)")
        print("  3. We'll use this to create a native Python implementation")
        print("=" * 80)


def main():
    """Main entry point"""
    print("\nNisscom COM Bridge Configuration")
    print("-" * 80)

    # Get configuration
    virtual_port = 'COM11'  # Default - the pair of COM10
    real_port = 'COM5'      # Your Nisscom device
    baudrate = 38400        # Common Consult-II baudrate

    # Allow command line override
    if len(sys.argv) > 1:
        virtual_port = sys.argv[1]
    if len(sys.argv) > 2:
        real_port = sys.argv[2]
    if len(sys.argv) > 3:
        baudrate = int(sys.argv[3])

    print(f"\nConfiguration:")
    print(f"  Virtual port (for Nisscom software): {virtual_port}")
    print(f"  Real port (Nisscom device):          {real_port}")
    print(f"  Baudrate:                            {baudrate}")
    print("\nIf this is incorrect, press Ctrl+C and run:")
    print(f"  python nisscom_com_bridge.py <virtual_port> <real_port> <baudrate>")
    print("\nStarting in 3 seconds...")
    time.sleep(3)

    # Create and start bridge
    bridge = COMBridge(virtual_port=virtual_port, real_port=real_port, baudrate=baudrate)

    try:
        bridge.start()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("\n")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
