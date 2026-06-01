"""
Nisscom Protocol Analyzer
Analyzes captured protocol logs to understand the communication structure
"""

import re
from datetime import datetime

class ProtocolAnalyzer:
    """Analyze Nisscom protocol captures"""

    def __init__(self, log_file):
        self.log_file = log_file
        self.packets = []

    def parse_log(self):
        """Parse the bridge log file"""
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_packet = None

        for line in lines:
            # Match timestamp and direction
            match = re.match(r'\[(\d+:\d+:\d+\.\d+)\] (PC->DEV|DEV->PC) \((\d+) bytes\)', line)
            if match:
                if current_packet:
                    self.packets.append(current_packet)

                current_packet = {
                    'timestamp': match.group(1),
                    'direction': match.group(2),
                    'length': int(match.group(3)),
                    'hex': None,
                    'dec': None
                }

            # Match HEX line
            elif line.strip().startswith('HEX:') and current_packet:
                hex_data = line.strip().replace('HEX:', '').strip()
                current_packet['hex'] = hex_data
                current_packet['bytes'] = [int(b, 16) for b in hex_data.split()]

            # Match DEC line
            elif line.strip().startswith('DEC:') and current_packet:
                dec_data = line.strip().replace('DEC:', '').strip()
                current_packet['dec'] = dec_data

        if current_packet:
            self.packets.append(current_packet)

        print(f"[PARSED] {len(self.packets)} packets")

    def analyze_initialization(self):
        """Analyze initialization sequence"""
        print("\n" + "=" * 80)
        print("INITIALIZATION SEQUENCE")
        print("=" * 80)

        # Look at first 10 packets
        init_packets = self.packets[:10]

        for i, pkt in enumerate(init_packets):
            print(f"\n{i+1}. [{pkt['timestamp']}] {pkt['direction']}")
            print(f"   HEX: {pkt['hex']}")

            # Interpret
            if pkt['bytes'] == [0x00]:
                print("   >>> SYNC/WAKEUP byte")
            elif pkt['bytes'] == [0x81]:
                print("   >>> Possible INIT command")
            elif 0x10 in pkt['bytes'] and 0xFC in pkt['bytes']:
                print("   >>> Handshake sequence")

    def find_command_patterns(self):
        """Find repeated command patterns"""
        print("\n" + "=" * 80)
        print("COMMAND PATTERNS")
        print("=" * 80)

        # Group by command structure
        patterns = {}

        for pkt in self.packets:
            if pkt['direction'] == 'PC->DEV':
                # Look at first byte as command
                if pkt['bytes']:
                    cmd = pkt['bytes'][0]
                    if cmd not in patterns:
                        patterns[cmd] = []
                    patterns[cmd].append(pkt)

        for cmd, pkts in sorted(patterns.items()):
            print(f"\nCommand 0x{cmd:02X} (appears {len(pkts)} times)")

            # Show first few examples
            for i, pkt in enumerate(pkts[:3]):
                print(f"  Example {i+1}: {pkt['hex']}")

            # Analyze structure
            if len(pkts) > 0:
                lengths = set(p['length'] for p in pkts)
                print(f"  Packet lengths: {lengths}")

                # Check if last byte could be checksum
                if len(pkts[0]['bytes']) > 1:
                    print(f"  Format analysis:")
                    self._analyze_format(pkts[0]['bytes'])

    def _analyze_format(self, bytes_data):
        """Analyze packet format"""
        if len(bytes_data) == 1:
            print(f"    Single byte command")
        elif len(bytes_data) == 4:
            print(f"    [0]=Cmd, [1]=Param1, [2]=Param2, [3]=Checksum?")
            # Check if last byte is XOR checksum
            calc_xor = 0
            for b in bytes_data[:-1]:
                calc_xor ^= b
            if calc_xor == bytes_data[-1]:
                print(f"    >>> CHECKSUM VERIFIED (XOR)")
            else:
                calc_sum = sum(bytes_data[:-1]) & 0xFF
                if calc_sum == bytes_data[-1]:
                    print(f"    >>> CHECKSUM VERIFIED (SUM)")

        elif len(bytes_data) == 7:
            print(f"    7-byte format: [Cmd][Subcmd][Reg][Addr][Len][Flags][Checksum?]")
            # Check checksum
            calc_xor = 0
            for b in bytes_data[:-1]:
                calc_xor ^= b
            if calc_xor == bytes_data[-1]:
                print(f"    >>> CHECKSUM VERIFIED (XOR)")
            else:
                calc_sum = sum(bytes_data[:-1]) & 0xFF
                if calc_sum == bytes_data[-1]:
                    print(f"    >>> CHECKSUM VERIFIED (SUM)")

    def compare_request_response(self):
        """Compare requests and responses"""
        print("\n" + "=" * 80)
        print("REQUEST/RESPONSE ANALYSIS")
        print("=" * 80)

        echo_count = 0
        modified_count = 0

        for i in range(len(self.packets) - 1):
            pkt = self.packets[i]
            next_pkt = self.packets[i + 1]

            if pkt['direction'] == 'PC->DEV' and next_pkt['direction'] == 'DEV->PC':
                if pkt['bytes'] == next_pkt['bytes']:
                    echo_count += 1
                else:
                    modified_count += 1
                    print(f"\n[{pkt['timestamp']}] NON-ECHO RESPONSE:")
                    print(f"  Request:  {pkt['hex']}")
                    print(f"  Response: {next_pkt['hex']}")

        print(f"\n\nSummary:")
        print(f"  Echo responses: {echo_count}")
        print(f"  Modified responses: {modified_count}")

        if echo_count > modified_count * 2:
            print("\n  >>> WARNING: Most responses are echoes")
            print("      This suggests the device is in loopback mode")
            print("      or the car ECU is not responding")

    def extract_unique_commands(self):
        """Extract unique command sequences"""
        print("\n" + "=" * 80)
        print("UNIQUE COMMANDS SENT BY NISSCOM SOFTWARE")
        print("=" * 80)

        unique_cmds = {}

        for pkt in self.packets:
            if pkt['direction'] == 'PC->DEV':
                hex_str = pkt['hex']
                if hex_str not in unique_cmds:
                    unique_cmds[hex_str] = {
                        'count': 0,
                        'first_time': pkt['timestamp'],
                        'bytes': pkt['bytes']
                    }
                unique_cmds[hex_str]['count'] += 1

        print(f"\nTotal unique commands: {len(unique_cmds)}\n")

        for hex_str, info in sorted(unique_cmds.items(), key=lambda x: x[1]['first_time']):
            print(f"[{info['first_time']}] {hex_str} (sent {info['count']} times)")

    def generate_python_implementation(self):
        """Generate Python code template based on captured protocol"""
        print("\n" + "=" * 80)
        print("PYTHON IMPLEMENTATION TEMPLATE")
        print("=" * 80)

        print("""
Based on the captured protocol, here's a template for talking to the Nisscom device:

```python
import serial
import time

class NisscomDevice:
    def __init__(self, port='COM5', baudrate=38400):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(0.5)

    def send_command(self, data):
        '''Send command and wait for response'''
        self.ser.write(bytes(data))
        self.ser.flush()
        time.sleep(0.1)

        response = []
        while self.ser.in_waiting > 0:
            response.append(self.ser.read(1)[0])
            time.sleep(0.01)

        return response

    def initialize(self):
        '''Initialize communication'''
        # Sync
        self.send_command([0x00])

        # Handshake
        self.send_command([0x81])
        self.send_command([0x10, 0xFC, 0x81])
        self.send_command([0x0E])

        print("Initialization complete")

    def read_register(self, reg, addr=0x00, length=0x04, flags=0x01):
        '''Read a register/memory location'''
        # Format: 05 22 [reg] [addr] [len] [flags] [checksum]
        cmd = [0x05, 0x22, reg, addr, length, flags]

        # Calculate XOR checksum
        checksum = 0
        for b in cmd:
            checksum ^= b
        cmd.append(checksum)

        response = self.send_command(cmd)
        return response

# Usage:
device = NisscomDevice('COM5')
device.initialize()
response = device.read_register(0x11, 0x00)
print(f"Response: {' '.join([f'{b:02X}' for b in response])}")
```
""")

def main():
    import sys

    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        # Find most recent log
        import glob
        import os

        log_dir = r"C:\D Drive\Predict\nisscom_logs"
        log_files = glob.glob(os.path.join(log_dir, "bridge_capture_*.txt"))

        if not log_files:
            print("No log files found!")
            return

        log_file = max(log_files, key=os.path.getmtime)
        print(f"Analyzing most recent log: {log_file}\n")

    analyzer = ProtocolAnalyzer(log_file)
    analyzer.parse_log()
    analyzer.analyze_initialization()
    analyzer.find_command_patterns()
    analyzer.compare_request_response()
    analyzer.extract_unique_commands()
    analyzer.generate_python_implementation()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
