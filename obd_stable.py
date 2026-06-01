"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Obd Stable
"""

import obd
import serial.tools.list_ports
import time
from datetime import datetime

class OBDAnalyzer:
    def __init__(self):
        self.connection = None
        self.supported_commands = []
        self.discovered_pids = []
        
    def smart_connect(self):
        """Smart connection that finds the right port and settings"""
        print("🧠 SMART OBD CONNECTION INITIATED...")
        
        # Priority ports based on common OBD adapters
        priority_ports = ['COM6', 'COM7', 'COM3', 'COM4', 'COM5']
        baud_rates = [38400, 9600, 115200, 57600]
        
        for port in priority_ports:
            for baud in baud_rates:
                try:
                    print(f"🔧 Testing {port} at {baud} baud...")
                    self.connection = obd.OBD(portstr=port, baudrate=baud, timeout=15)
                    
                    # Wait for initialization
                    time.sleep(3)
                    
                    if self.connection.status() != obd.OBDStatus.NOT_CONNECTED:
                        print(f"✅ SMART CONNECTION ESTABLISHED!")
                        print(f"📍 Port: {port} | Baud: {baud}")
                        print(f"📊 Status: {self.connection.status()}")
                        return True
                    else:
                        self.connection.close()
                        self.connection = None
                        
                except Exception as e:
                    print(f"❌ {port} at {baud} failed: {str(e)[:50]}...")
                    continue
        
        print("❌ No successful connections found")
        return False
    
    def analyze_connection(self):
        """Analyze what data we can read from the connection"""
        if not self.connection:
            return
        
        print(f"\n🔍 ANALYZING OBD CONNECTION...")
        print(f"Connection Status: {self.connection.status()}")
        print(f"Protocol: {self.connection.protocol_name()}")
        
        # Get supported commands
        try:
            self.supported_commands = list(self.connection.supported_commands)  # Convert set to list
            
            # Convert commands to hex PID list for the connectivity module
            self.discovered_pids = []
            
            for cmd in self.supported_commands:
                try:
                    hex_pid = cmd.command
                    if isinstance(hex_pid, str) and len(hex_pid) == 4:
                        self.discovered_pids.append(hex_pid.upper())
                except:
                    pass
            
            print(f"📋 Supported Commands: {len(self.supported_commands)}")
            print(f"🔢 Discovered PIDs: {len(self.discovered_pids)}")
            
            # Show the actual supported commands
            print("\n📝 ACTUALLY SUPPORTED COMMANDS:")
            for i, cmd in enumerate(self.supported_commands[:15]):  # Show first 15
                print(f"  {i+1}. {cmd.name}")
            if len(self.supported_commands) > 15:
                print(f"  ... and {len(self.supported_commands) - 15} more")
                
            # Show discovered PIDs
            if self.discovered_pids:
                print(f"\n🎯 DISCOVERED PIDs:")
                for i, pid in enumerate(self.discovered_pids[:20]):  # Show first 20
                    print(f"  {i+1}. {pid}")
                if len(self.discovered_pids) > 20:
                    print(f"  ... and {len(self.discovered_pids) - 20} more")
                
        except Exception as e:
            print(f"❌ Could not get supported commands: {e}")
            return
        
        # Test communication with basic commands
        self.test_basic_communication()
        
        # Test available commands
        self.test_available_commands()
    
    def test_basic_communication(self):
        """Test if basic communication works"""
        print(f"\n📡 TESTING BASIC COMMUNICATION...")
        
        # Only use valid, safe commands
        test_commands = [
            ("ELM Version", obd.commands.ELM_VERSION),
            ("ELM Voltage", obd.commands.ELM_VOLTAGE),
            ("VIN", obd.commands.VIN),
        ]
        
        for name, cmd in test_commands:
            try:
                response = self.connection.query(cmd)
                if not response.is_null():
                    print(f"✅ {name}: {response.value}")
                else:
                    print(f"❌ {name}: No response")
            except Exception as e:
                print(f"⚠️ {name}: Error - {e}")
    
    def test_available_commands(self):
        """Test only the commands that are actually supported"""
        print(f"\n🎯 TESTING SUPPORTED OBD COMMANDS...")
        
        if not self.supported_commands:
            print("❌ No supported commands to test")
            return
        
        working_commands = []
        total_tested = 0
        
        # Test a reasonable number of commands (not all to avoid timeout)
        commands_to_test = self.supported_commands[:20]  # Test first 20
        
        for cmd in commands_to_test:
            try:
                total_tested += 1
                response = self.connection.query(cmd)
                if not response.is_null():
                    print(f"✅ {cmd.name}: {response.value}")
                    working_commands.append((cmd.name, response.value))
                else:
                    print(f"❌ {cmd.name}: No data")
            except Exception as e:
                print(f"⚠️ {cmd.name}: Error - {e}")
        
        print(f"\n📊 TEST SUMMARY:")
        print(f"Tested: {total_tested} commands")
        print(f"Working: {len(working_commands)} commands")
        if total_tested > 0:
            print(f"Success rate: {len(working_commands)/total_tested*100:.1f}%")
        
        return working_commands
    
    def smart_monitor(self, duration=60):
        """Smart monitoring that focuses on working commands"""
        if not self.connection:
            print("❌ No connection available for monitoring")
            return
        
        print(f"\n📈 SMART LIVE MONITORING (for {duration} seconds)...")
        print("Press Ctrl+C to stop early")
        
        start_time = time.time()
        sample_count = 0
        
        # Find which commands actually work
        working_commands = self.find_working_commands()
        
        if not working_commands:
            print("❌ No working commands found for monitoring")
            return
        
        print(f"🎯 Monitoring {len(working_commands)} working parameters:")
        for name, cmd in working_commands:
            print(f"  - {name}")
        
        try:
            while time.time() - start_time < duration:
                print("\033[H\033[J", end="")  # Clear screen
                print(f"=== SMART OBD MONITOR ===")
                print(f"Sample: {sample_count} | Time: {int(time.time() - start_time)}s/{duration}s")
                print(f"Status: {self.connection.status()}\n")
                
                # Read all working commands
                for name, cmd in working_commands:
                    try:
                        response = self.connection.query(cmd)
                        if not response.is_null():
                            print(f"🔹 {name}: {response.value}")
                        else:
                            print(f"🔸 {name}: ---")
                    except Exception as e:
                        print(f"🔸 {name}: Error")
                
                print(f"\n⏱️  Next update in 2 seconds... (Ctrl+C to stop)")
                sample_count += 1
                time.sleep(2)
                
        except KeyboardInterrupt:
            print(f"\n⏹️ Monitoring stopped after {sample_count} samples")
        
        print(f"\n📊 Monitoring Summary:")
        print(f"Total samples: {sample_count}")
        print(f"Duration: {int(time.time() - start_time)} seconds")
        print(f"Parameters monitored: {len(working_commands)}")
    
    def find_working_commands(self):
        """Find which commands actually return data"""
        working = []
        
        if not self.supported_commands:
            return working
        
        # Test common commands first
        common_commands = [
            ("RPM", obd.commands.RPM),
            ("Speed", obd.commands.SPEED),
            ("Engine Load", obd.commands.ENGINE_LOAD),
            ("Coolant Temp", obd.commands.COOLANT_TEMP),
            ("Throttle Position", obd.commands.THROTTLE_POS),
            ("Fuel Level", obd.commands.FUEL_LEVEL),
        ]
        
        # Test common commands
        for name, cmd in common_commands:
            try:
                if cmd in self.connection.supported_commands:  # Check against the original set
                    response = self.connection.query(cmd)
                    if not response.is_null():
                        working.append((name, cmd))
            except:
                pass
        
        # If no common commands work, try some from supported list
        if not working and self.supported_commands:
            for cmd in self.supported_commands[:10]:  # Try first 10 supported
                try:
                    response = self.connection.query(cmd)
                    if not response.is_null():
                        working.append((cmd.name, cmd))
                except:
                    pass
        
        return working
    
    def generate_report(self):
        """Generate a comprehensive connection report"""
        if not self.connection:
            return
        
        print(f"\n📄 OBD CONNECTION REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Connection Status: {self.connection.status()}")
        print(f"Protocol: {self.connection.protocol_name()}")
        print(f"Port: {self.connection.port_name()}")
        print(f"Supported Commands: {len(self.supported_commands)}")
        print(f"Discovered PIDs: {len(self.discovered_pids)}")
        
        # Show sample of working data
        working = self.find_working_commands()
        print(f"Working Parameters: {len(working)}")
        for name, cmd in working[:10]:  # Show first 10
            try:
                response = self.connection.query(cmd)
                print(f"  - {name}: {response.value}")
            except:
                print(f"  - {name}: Error reading")

def main():
    print("=" * 60)
    print("🧠 SMART OBD-II DATA READER")
    print("=" * 60)
    
    analyzer = OBDAnalyzer()
    
    # Smart connection
    if analyzer.smart_connect():
        # Analyze what we can read
        analyzer.analyze_connection()
        
        # Generate report
        analyzer.generate_report()
        
        # Ask for monitoring
        try:
            choice = input("\n🎯 Start smart monitoring? (y/n): ").lower()
            if choice == 'y':
                duration = input("Enter monitoring duration in seconds (default 60): ")
                try:
                    duration = int(duration) if duration.strip() else 60
                except:
                    duration = 60
                analyzer.smart_monitor(duration)
        except KeyboardInterrupt:
            pass
        
        # Close connection
        analyzer.connection.close()
        print("\n🔌 Connection closed")
    else:
        print("\n❌ Failed to establish connection")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Check OBD adapter is properly plugged in")
        print("2. Ensure ignition is ON")
        print("3. Verify Bluetooth connection in Windows settings")
        print("4. Try restarting the adapter")

if __name__ == "__main__":
    main()