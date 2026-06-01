"""
Quick Sensor Reader - Just run this to see your live data!
===========================================================

Simplest possible script to read sensors from your Nissan.
Edit the COM_PORT below to match your system.
"""

import sys
import time
from consult2_sensor_reader import Consult2SensorReader, ECM_SENSORS

# EDIT THIS to match your COM port
# Windows: 'COM5', 'COM3', etc.
# Linux: '/dev/ttyUSB0', '/dev/ttyACM0', etc.
COM_PORT = 'COM5'

def main():
    reader = Consult2SensorReader(COM_PORT)
    
    print("=" * 60)
    print("NISSAN SENSOR READER - QUICK START")
    print("=" * 60)
    print(f"Port: {COM_PORT}")
    print()
    
    # Connect
    print("Connecting to ECU...")
    if not reader.connect():
        print("\n❌ Connection failed!")
        print("\nTroubleshooting:")
        print("  1. Is ignition ON? (Engine can be off)")
        print("  2. Is Nisscom USB plugged in firmly?")
        print("  3. Try a different COM port:")
        print("     - Check Device Manager (Windows)")
        print("     - Run: python -c \"import serial; print([p.device for p in serial.tools.list_ports.comports()])\"")
        return 1
    
    print("\n✓ Connected to ECU!")
    if reader.ecu_id:
        print(f"  ECU ID: {reader.ecu_id}")
    print()
    
    try:
        # Quick scan of known-safe parameters
        print("-" * 60)
        print("STEP 1: Discovering available sensors...")
        print("-" * 60)
        
        # Only scan 0x00-0x05 (known safe from your docs)
        params = reader.scan_a0_parameters(0x00, 0x05)
        
        if not params:
            print("\nNo parameters found in safe range.")
            print("Your ECU may use different parameter IDs.")
            return
        
        print()
        
        # Test read each found parameter
        print("-" * 60)
        print("STEP 2: Reading sensor values...")
        print("-" * 60)
        
        print("\nPress Ctrl+C to stop monitoring\n")
        
        # Live display
        while True:
            line_parts = []
            for param in sorted(params.keys()):
                status, data = reader.read_sensor_a0(param, wait=0.2)
                if status == 'ok' and data:
                    if len(data) == 1:
                        val = data[0]
                        line_parts.append(f"0x{param:02X}={val}")
                    elif len(data) >= 2:
                        val16 = (data[0] << 8) | data[1]
                        line_parts.append(f"0x{param:02X}={val16}")
            
            if line_parts:
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] {' | '.join(line_parts)}")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        reader.disconnect()
        print("\nDone!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
