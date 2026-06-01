"""
Sensor Identification Tool
==========================

Helps identify what each 0xA0 parameter represents by:
1. Reading values multiple times
2. Detecting which ones change (live sensors vs constants)
3. Trying different scaling formulas
4. Comparing to expected ranges

Usage: Run this with engine OFF but ignition ON, then turn engine ON
       to see which values change.
"""

import time
from consult2_sensor_reader import Consult2SensorReader
from collections import defaultdict

COM_PORT = 'COM5'

# Expected ranges for different sensor types
RANGES = {
    'rpm': {'min': 0, 'max': 8000, 'scale_16': 12.5, 'unit': 'rpm'},
    'coolant': {'min': -40, 'max': 150, 'offset_8': -50, 'unit': '°C'},
    'battery': {'min': 8, 'max': 16, 'scale_8': 0.08, 'unit': 'V'},
    'maf_voltage': {'min': 0, 'max': 5, 'scale_16': 0.005, 'unit': 'V'},
    'tps': {'min': 0, 'max': 100, 'unit': '%'},
    'speed': {'min': 0, 'max': 200, 'scale_8': 1.24274, 'unit': 'mph'},
}


def identify_sensors():
    reader = Consult2SensorReader(COM_PORT)
    
    print("=" * 70)
    print("SENSOR IDENTIFICATION TOOL")
    print("=" * 70)
    print()
    print("This will help figure out what each 0xA0 parameter represents.")
    print()
    print("Instructions:")
    print("  1. Connect with ignition ON (engine OFF)")
    print("  2. Watch the 'CHANGING' column when you start the engine")
    print("  3. Values that change are live sensors")
    print("  4. Static values are configuration data")
    print()
    input("Press ENTER to start...")
    print()
    
    if not reader.connect():
        print("Failed to connect!")
        return
    
    print()
    
    # First, find which parameters work
    print("Phase 1: Finding valid parameters (0x00-0x20)...")
    print("-" * 70)
    
    valid_params = []
    for param in range(0x00, 0x21):
        status, data = reader.read_sensor_a0(param, wait=0.2)
        if status == 'ok':
            valid_params.append(param)
            print(f"  0x{param:02X}: {len(data)} bytes")
        time.sleep(0.05)
    
    if not valid_params:
        print("No valid parameters found!")
        reader.disconnect()
        return
    
    print(f"\nFound {len(valid_params)} valid parameters")
    print()
    
    # Collect multiple readings
    print("Phase 2: Collecting readings (5 samples per parameter)...")
    print("-" * 70)
    print("Start your engine now! (or rev it if already running)")
    print()
    
    readings = defaultdict(list)
    
    for cycle in range(5):
        print(f"  Sample {cycle + 1}/5...")
        for param in valid_params:
            status, data = reader.read_sensor_a0(param, wait=0.15)
            if status == 'ok':
                readings[param].append(bytes(data))
            else:
                readings[param].append(None)
            time.sleep(0.05)
        time.sleep(0.5)  # Wait between cycles
    
    print()
    print("Phase 3: Analysis")
    print("=" * 70)
    print()
    
    for param in valid_params:
        samples = readings[param]
        valid_samples = [s for s in samples if s is not None]
        
        if not valid_samples:
            continue
        
        # Check if value changes
        unique_values = set(s.hex() for s in valid_samples)
        is_changing = len(unique_values) > 1
        
        # Get latest sample
        latest = valid_samples[-1]
        
        print(f"Parameter 0x{param:02X}:")
        print(f"  Raw bytes: {latest.hex()}")
        print(f"  Length: {len(latest)} bytes")
        print(f"  CHANGING: {'YES ***' if is_changing else 'No (static)'}")
        
        # Try different interpretations
        interpretations = []
        
        if len(latest) == 1:
            v = latest[0]
            interpretations.append(f"Raw={v}")
            
            # Temperature
            temp_c = v - 50
            if -40 <= temp_c <= 150:
                interpretations.append(f"Temp={temp_c}°C")
            
            # Battery voltage (scale 0.08)
            volt = v * 0.08
            if 8 <= volt <= 16:
                interpretations.append(f"Battery={volt:.1f}V")
            
            # Speed MPH
            mph = v * 1.24274
            if 0 <= mph <= 200:
                interpretations.append(f"Speed={mph:.1f}mph")
            
            # Percentage
            if v <= 100:
                interpretations.append(f"Percent={v}%")
                
        elif len(latest) >= 2:
            v16 = (latest[0] << 8) | latest[1]
            interpretations.append(f"Raw16={v16}")
            
            # RPM (scale 12.5)
            rpm = v16 * 12.5
            if 0 <= rpm <= 10000:
                interpretations.append(f"*** RPM={rpm:.0f} ***")
            
            # Voltage (scale 0.005)
            volt = v16 * 0.005
            if 0 <= volt <= 5:
                interpretations.append(f"Voltage={volt:.3f}V")
            
            # Speed KPH
            if 0 <= v16 <= 300:
                interpretations.append(f"Speed={v16}kph")
        
        print(f"  Interpretations: {' | '.join(interpretations)}")
        print()
    
    reader.disconnect()
    print("=" * 70)
    print("Analysis complete!")
    print()
    print("Next steps:")
    print("  1. Look for parameters marked 'CHANGING: YES ***'")
    print("  2. RPM will be a 2-byte value that jumps when engine starts")
    print("  3. Coolant temp will be 1-byte, around 20-80°C when warm")
    print("  4. Update ECM_SENSORS in consult2_sensor_reader.py with your findings")


if __name__ == "__main__":
    identify_sensors()
