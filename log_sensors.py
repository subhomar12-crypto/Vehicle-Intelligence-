"""
Sensor Data Logger
==================

Logs sensor data to CSV file for later analysis.

Features:
- Logs to timestamped CSV file
- Configurable logging rate
- Logs all discovered parameters
- Can run for specified duration or indefinitely
"""

import csv
import time
import os
from datetime import datetime
from consult2_sensor_reader import Consult2SensorReader

COM_PORT = 'COM5'
LOG_INTERVAL = 1.0  # Seconds between readings
LOG_DURATION = None  # None = run until Ctrl+C, or set seconds (e.g., 300 for 5 minutes)


def create_log_filename():
    """Generate timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"nissan_sensor_log_{timestamp}.csv"


def log_sensors():
    reader = Consult2SensorReader(COM_PORT)
    
    print("=" * 60)
    print("NISSAN SENSOR DATA LOGGER")
    print("=" * 60)
    print()
    
    # Connect
    print(f"Connecting to ECU on {COM_PORT}...")
    if not reader.connect():
        print("Connection failed!")
        return
    
    print(f"✓ Connected (ECU: {reader.ecu_id or 'Unknown'})")
    print()
    
    # Discover parameters
    print("Discovering available parameters...")
    params_to_log = []
    for param in range(0x00, 0x10):  # Scan first 16
        status, data = reader.read_sensor_a0(param, wait=0.2)
        if status == 'ok':
            params_to_log.append((param, len(data)))
            print(f"  Found: 0x{param:02X} ({len(data)} bytes)")
        time.sleep(0.05)
    
    if not params_to_log:
        print("No parameters found to log!")
        reader.disconnect()
        return
    
    # Setup CSV file
    filename = create_log_filename()
    print(f"\nLogging to: {filename}")
    print(f"Interval: {LOG_INTERVAL}s")
    if LOG_DURATION:
        print(f"Duration: {LOG_DURATION}s")
    else:
        print("Duration: Until stopped (Ctrl+C)")
    print()
    
    # Write CSV header
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        header = ['Timestamp', 'Elapsed_Seconds']
        for param, length in params_to_log:
            header.append(f"Param_0x{param:02X}_hex")
            if length == 1:
                header.append(f"Param_0x{param:02X}_raw")
                header.append(f"Param_0x{param:02X}_temp_c")
                header.append(f"Param_0x{param:02X}_volts")
            elif length == 2:
                header.append(f"Param_0x{param:02X}_raw16")
                header.append(f"Param_0x{param:02X}_rpm")
                header.append(f"Param_0x{param:02X}_volts")
        writer.writerow(header)
    
    # Start logging
    print("Logging started...")
    print("-" * 60)
    
    start_time = time.time()
    sample_count = 0
    
    try:
        while True:
            row = []
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elapsed = time.time() - start_time
            row.extend([timestamp, f"{elapsed:.3f}"])
            
            # Read all parameters
            for param, length in params_to_log:
                status, data = reader.read_sensor_a0(param, wait=0.15)
                if status == 'ok' and data:
                    row.append(data.hex())
                    
                    if length == 1 and len(data) >= 1:
                        v = data[0]
                        row.extend([
                            str(v),
                            f"{v-50}",
                            f"{v*0.08:.2f}"
                        ])
                    elif length == 2 and len(data) >= 2:
                        v16 = (data[0] << 8) | data[1]
                        row.extend([
                            str(v16),
                            f"{v16*12.5:.0f}",
                            f"{v16*0.005:.3f}"
                        ])
                    else:
                        row.extend([''] * 3)
                else:
                    row.extend([''] * 4)
            
            # Write to CSV
            with open(filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            sample_count += 1
            
            # Status update
            if sample_count % 10 == 0:
                print(f"  Samples: {sample_count} | Elapsed: {elapsed:.0f}s")
            
            # Check duration
            if LOG_DURATION and elapsed >= LOG_DURATION:
                print(f"\nReached duration limit ({LOG_DURATION}s)")
                break
            
            # Wait for next interval
            time.sleep(LOG_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nLogging stopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        reader.disconnect()
        
        # Final summary
        print()
        print("=" * 60)
        print("LOGGING COMPLETE")
        print("=" * 60)
        print(f"File: {filename}")
        print(f"Samples: {sample_count}")
        print(f"Duration: {time.time() - start_time:.0f}s")
        print()
        print(f"Full path: {os.path.abspath(filename)}")


if __name__ == "__main__":
    log_sensors()
