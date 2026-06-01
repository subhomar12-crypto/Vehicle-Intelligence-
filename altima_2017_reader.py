"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Altima 2017 Reader
"""

"""
================================================================================
NISSAN ALTIMA 2017 - OBD-II READER
================================================================================
Your 2017 Altima uses CAN protocol - fast and reliable!

Just run this script:
    python altima_2017_reader.py

================================================================================
"""

import serial
import serial.tools.list_ports
import time
import os

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

# Standard OBD-II PIDs (work on ALL OBD-II vehicles)
PIDS = {
    0x04: ("Engine Load", "%", 1, lambda d: d[0] * 100 / 255),
    0x05: ("Coolant Temp", "°C", 1, lambda d: d[0] - 40),
    0x06: ("Short Fuel Trim 1", "%", 1, lambda d: (d[0] - 128) * 100 / 128),
    0x07: ("Long Fuel Trim 1", "%", 1, lambda d: (d[0] - 128) * 100 / 128),
    0x0B: ("Intake Pressure", "kPa", 1, lambda d: d[0]),
    0x0C: ("RPM", "rpm", 2, lambda d: (d[0] * 256 + d[1]) / 4),
    0x0D: ("Speed", "km/h", 1, lambda d: d[0]),
    0x0E: ("Timing Advance", "°", 1, lambda d: (d[0] - 128) / 2),
    0x0F: ("Intake Temp", "°C", 1, lambda d: d[0] - 40),
    0x10: ("MAF", "g/s", 2, lambda d: (d[0] * 256 + d[1]) / 100),
    0x11: ("Throttle", "%", 1, lambda d: d[0] * 100 / 255),
    0x14: ("O2 Sensor 1", "V", 2, lambda d: d[0] / 200),
    0x1F: ("Runtime", "sec", 2, lambda d: d[0] * 256 + d[1]),
    0x2F: ("Fuel Level", "%", 1, lambda d: d[0] * 100 / 255),
    0x33: ("Barometric", "kPa", 1, lambda d: d[0]),
    0x42: ("ECU Voltage", "V", 2, lambda d: (d[0] * 256 + d[1]) / 1000),
    0x46: ("Ambient Temp", "°C", 1, lambda d: d[0] - 40),
    0x5C: ("Oil Temp", "°C", 1, lambda d: d[0] - 40),
    0x5E: ("Fuel Rate", "L/h", 2, lambda d: (d[0] * 256 + d[1]) / 20),
}


class AltimaOBDReader:
    """Simple OBD reader for 2017 Nissan Altima"""
    
    def __init__(self, port: str, baudrate: int = 38400):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.supported_pids = []
    
    def connect(self) -> bool:
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=3)
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"{RED}Connection failed: {e}{RESET}")
            return False
    
    def disconnect(self):
        if self.serial:
            self.serial.close()
            self.serial = None
    
    def send(self, cmd: str, timeout: float = 3.0) -> str:
        if not self.serial:
            return ""
        try:
            self.serial.reset_input_buffer()
            self.serial.write((cmd + '\r').encode())
            self.serial.flush()
            
            response = b''
            start = time.time()
            while (time.time() - start) < timeout:
                if self.serial.in_waiting:
                    response += self.serial.read(self.serial.in_waiting)
                    if b'>' in response:
                        break
                time.sleep(0.02)
            
            text = response.decode('ascii', errors='ignore')
            return ' '.join(text.split()).strip()
        except:
            return ""
    
    def initialize(self) -> bool:
        print(f"{CYAN}Initializing ELM327...{RESET}")
        
        # Reset
        resp = self.send('ATZ', 2)
        if 'ELM' in resp.upper():
            print(f"{GREEN}✓ {resp}{RESET}")
        
        time.sleep(0.5)
        
        # Configure for CAN (auto-detect will find it)
        self.send('ATE0')  # Echo off
        self.send('ATL0')  # Linefeeds off
        self.send('ATS0')  # Spaces off
        self.send('ATH0')  # Headers off
        self.send('ATSP0') # Auto protocol
        
        # Get voltage
        v = self.send('ATRV')
        print(f"{GREEN}✓ Voltage: {v}{RESET}")
        
        # Test connection
        resp = self.send('0100', 5)
        if '4100' in resp.replace(' ', ''):
            print(f"{GREEN}✓ ECU responding!{RESET}")
            
            # Get protocol
            proto = self.send('ATDPN')
            print(f"{GREEN}✓ Protocol: {proto}{RESET}")
            return True
        
        print(f"{YELLOW}Response: {resp}{RESET}")
        return False
    
    def discover_pids(self) -> list:
        """Discover which PIDs the car supports"""
        print(f"\n{CYAN}Discovering supported PIDs...{RESET}")
        
        supported = []
        
        for pid, (name, unit, bytes_needed, formula) in PIDS.items():
            cmd = f"01{pid:02X}"
            resp = self.send(cmd, 2)
            
            expected = f"41{pid:02X}"
            if expected in resp.replace(' ', '').upper():
                supported.append(pid)
                
                # Decode value
                try:
                    clean = resp.replace(' ', '').upper()
                    idx = clean.find(expected) + 4
                    hex_data = clean[idx:idx + bytes_needed * 2]
                    data = [int(hex_data[i:i+2], 16) for i in range(0, len(hex_data), 2)]
                    value = formula(data)
                    print(f"  {GREEN}✓ {name}: {value:.1f} {unit}{RESET}")
                except:
                    print(f"  {GREEN}✓ {name}: (supported){RESET}")
            else:
                print(f"  {RED}✗ {name}{RESET}")
        
        self.supported_pids = supported
        return supported
    
    def read_all(self) -> dict:
        """Read all supported PIDs"""
        data = {}
        
        for pid in self.supported_pids:
            if pid not in PIDS:
                continue
                
            name, unit, bytes_needed, formula = PIDS[pid]
            cmd = f"01{pid:02X}"
            resp = self.send(cmd, 1.5)
            
            expected = f"41{pid:02X}"
            if expected in resp.replace(' ', '').upper():
                try:
                    clean = resp.replace(' ', '').upper()
                    idx = clean.find(expected) + 4
                    hex_data = clean[idx:idx + bytes_needed * 2]
                    raw = [int(hex_data[i:i+2], 16) for i in range(0, len(hex_data), 2)]
                    value = formula(raw)
                    data[name] = (value, unit)
                except:
                    pass
        
        return data
    
    def live_monitor(self, duration: int = 60):
        """Live data monitoring"""
        print(f"\n{BOLD}{'=' * 50}{RESET}")
        print(f"{BOLD}LIVE MONITORING - Press Ctrl+C to stop{RESET}")
        print(f"{'=' * 50}\n")
        
        start = time.time()
        samples = 0
        
        try:
            while (time.time() - start) < duration:
                os.system('cls' if os.name == 'nt' else 'clear')
                
                elapsed = int(time.time() - start)
                samples += 1
                
                print(f"{BOLD}{'=' * 50}{RESET}")
                print(f"{BOLD}{CYAN}NISSAN ALTIMA 2017 - LIVE DATA{RESET}")
                print(f"{BOLD}{'=' * 50}{RESET}")
                print(f"Time: {elapsed}s | Samples: {samples}")
                print(f"{'-' * 50}")
                
                data = self.read_all()
                
                for name, (value, unit) in sorted(data.items()):
                    print(f"  {name:<20}: {value:>10.1f} {unit}")
                
                print(f"{'-' * 50}")
                print("Press Ctrl+C to stop")
                
                time.sleep(0.3)  # CAN is fast!
                
        except KeyboardInterrupt:
            pass
        
        print(f"\n{GREEN}Monitoring stopped. Total samples: {samples}{RESET}")


def main():
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}NISSAN ALTIMA 2017 - OBD-II READER{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{GREEN}Your Altima uses CAN protocol - fast and reliable!{RESET}")
    
    # Detect ports
    print(f"\n{CYAN}Detecting COM ports...{RESET}")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print(f"{RED}No COM ports found!{RESET}")
        return
    
    print(f"\nAvailable ports:")
    for i, p in enumerate(ports):
        bt = " (Bluetooth)" if 'bluetooth' in p.description.lower() else ""
        print(f"  {i+1}. {p.device} - {p.description}{bt}")
    
    # Select port
    print(f"\n{CYAN}Select port number:{RESET}")
    try:
        choice = input().strip()
        if choice:
            port = ports[int(choice) - 1].device
        else:
            port = ports[0].device
    except:
        port = ports[0].device
    
    print(f"\nUsing: {port}")
    
    # Create reader
    reader = AltimaOBDReader(port)
    
    # Connect
    if not reader.connect():
        return
    print(f"{GREEN}✓ Connected{RESET}")
    
    # Initialize
    if not reader.initialize():
        print(f"{RED}Initialization failed{RESET}")
        reader.disconnect()
        return
    
    # Discover PIDs
    supported = reader.discover_pids()
    print(f"\n{GREEN}Found {len(supported)} supported PIDs!{RESET}")
    
    # Monitor?
    print(f"\n{CYAN}Start live monitoring? (y/n):{RESET}")
    if input().lower().strip() == 'y':
        print(f"{CYAN}Duration in seconds (Enter for 60):{RESET}")
        try:
            duration = int(input().strip() or "60")
        except:
            duration = 60
        
        reader.live_monitor(duration)
    
    reader.disconnect()
    print(f"\n{GREEN}Done!{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Cancelled{RESET}")
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
