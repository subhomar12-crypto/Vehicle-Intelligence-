"""
Quick Test: Safe Sensor Reading - AC 81 + 0x21 Method
======================================================

This is a simplified test script that reads the 7 safe sensors.
Uses ONLY verified read-only addresses from decompiled NDS II code.

⚠️  SAFETY VERIFIED - These addresses are KNOWN READ-ONLY:
    • Engine RPM:          0x12 0x01
    • Air Flow Voltage:    0x12 0x04
    • Coolant Temp:        0x11 0x01
    • Short Fuel Trim:     0x11 0x5F
    • Long Fuel Trim:      0x11 0x61
    • Speed (MPH):         0x11 0x02
    • Vehicle Speed (KPH): 0x12 0x1A

SETUP BEFORE RUNNING:
    1. Connect Nisscom USB to your computer
    2. Connect Nisscom to car's OBD port (under dashboard)
    3. Turn ignition ON (engine can be OFF for safety)
    4. Check COM port in Device Manager (usually COM5)
    5. Run: python test_safe_sensors.py

WHAT TO EXPECT:
    ✓ If working: You'll see live sensor values
    ✓ If no data: Check connections and ignition
    ✓ If errors: Verify COM port is correct
"""

import serial
import time


# ═══════════════════════════════════════════════════════════════════════════════
# THE 7 SAFE SENSORS - Verified read-only from NDS II decompilation
# ═══════════════════════════════════════════════════════════════════════════════
SAFE_SENSORS = [
    ("RPM", 0x12, 0x01, "rpm", 2, lambda d: ((d[0]<<8)|d[1]) * 12.5),
    ("AFM_V", 0x12, 0x04, "V", 2, lambda d: ((d[0]<<8)|d[1]) * 0.005),
    ("COOLANT", 0x11, 0x01, "°C", 1, lambda d: d[0] - 50),
    ("STFT", 0x11, 0x5F, "%", 1, lambda d: d[0] if d[0] < 128 else d[0]-256),
    ("LTFT", 0x11, 0x61, "%", 1, lambda d: d[0] if d[0] < 128 else d[0]-256),
    ("SPEED_MPH", 0x11, 0x02, "mph", 1, lambda d: d[0] * 1.24274),
    ("SPEED_KPH", 0x12, 0x1A, "kph", 2, lambda d: (d[0]<<8)|d[1]),
]


def checksum(data):
    return sum(data) & 0xFF


def hexdump(data):
    return ' '.join(f'{b:02X}' for b in data)


def connect_ecu(port):
    """Connect to ECU with KWP2000 initialization."""
    print(f"\n[1] Opening {port} at 10400 baud...")
    ser = serial.Serial(port, 10400, timeout=1.0)
    
    print("[2] Sending KWP2000 init sequence...")
    ser.reset_input_buffer()
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    print(f"[3] Response: {hexdump(resp)}")
    
    if 0xC1 not in resp:
        ser.close()
        return None
    
    print("[4] ✓ ECU connected!\n")
    return ser


def read_ecu_id(ser):
    """Read ECU identification."""
    ser.reset_input_buffer()
    ser.write(bytes([0x02, 0x1A, 0x81, 0x9D]))
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    
    # Parse ECU ID
    if len(resp) > 4:
        for i, b in enumerate(resp):
            if b == 0x5A and i > 0:
                id_bytes = resp[i+1:i+7]
                ecu_id = ''.join(chr(b) if 32 <= b < 127 else '.' for b in id_bytes)
                return ecu_id
    return None


def read_sensors_ac81(ser):
    """
    Read sensors using SAFE AC 81 + 0x21 method.
    
    This sends the 7 safe sensor addresses to the MCU,
    which then collects the data. Then we read it with 0x21.
    """
    # Build AC 81 frame with ALL 7 safe sensors
    frame = [0xAC, 0x81]
    for name, addr0, addr1, unit, size, parser in SAFE_SENSORS:
        frame.extend([0x02, addr0, addr1])
    
    # Add length and checksum
    frame.insert(0, len(frame))
    frame.append(checksum(frame))
    
    # Send AC 81
    ser.reset_input_buffer()
    ser.write(bytes(frame))
    time.sleep(0.2)
    ack = ser.read(ser.in_waiting)
    
    if 0xEC not in ack:
        print(f"  MCU ack: {hexdump(ack)} (expected EC)")
        return {}
    
    # Send 0x21 read command
    ser.write(bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB]))
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    
    # Parse response
    results = {}
    if 0x61 in resp:
        idx = resp.index(0x61)
        if idx + 2 < len(resp):
            data_start = idx + 2
            offset = data_start
            
            for i, (name, addr0, addr1, unit, size, parser) in enumerate(SAFE_SENSORS):
                if offset + size < len(resp):
                    data = resp[offset:offset+size]
                    try:
                        value = parser(data)
                        results[name] = (value, unit)
                    except:
                        pass
                    offset += size
    
    return results


def main():
    print("="*70)
    print("NISSCOM SAFE SENSOR TEST - AC 81 + 0x21 Method")
    print("="*70)
    print("\n⚠️  IMPORTANT: Connect car BEFORE running!")
    print("   1. Nisscom USB → Computer")
    print("   2. Nisscom → Car OBD port")
    print("   3. Ignition ON (engine OFF is OK)")
    
    port = input("\nEnter COM port (default COM5): ").strip() or "COM5"
    
    # Connect
    ser = connect_ecu(port)
    if not ser:
        print("\n❌ Connection failed!")
        print("   • Check ignition is ON")
        print("   • Check Nisscom is connected to car")
        print("   • Check COM port in Device Manager")
        return 1
    
    # Read ECU ID
    ecu_id = read_ecu_id(ser)
    if ecu_id:
        print(f"[INFO] ECU ID: {ecu_id}\n")
    
    # Read sensors
    print("Reading sensors using AC 81 + 0x21 (safe method)...")
    print("-"*50)
    
    results = read_sensors_ac81(ser)
    
    if results:
        print("\n✅ SUCCESS! Sensor data:")
        print("-"*50)
        for name, (value, unit) in results.items():
            print(f"  {name:12} {value:8.1f} {unit}")
        print("-"*50)
        
        # Live monitoring option
        print("\n[OPTION] Press Enter for live monitoring (Ctrl+C to stop)")
        print("         Or type 'q' to quit")
        choice = input("> ").strip().lower()
        
        if choice != 'q':
            print("\n📊 LIVE MONITOR (updating every 1 second)...")
            print("-"*50)
            try:
                while True:
                    results = read_sensors_ac81(ser)
                    ts = time.strftime("%H:%M:%S")
                    line = f"[{ts}]"
                    for name in ["RPM", "COOLANT", "SPEED_KPH", "AFM_V"]:
                        if name in results:
                            val, unit = results[name]
                            line += f" {name}:{val:.0f}"
                    print(line)
                    time.sleep(1.0)
            except KeyboardInterrupt:
                print("\n[STOP] Monitoring stopped")
    else:
        print("\n⚠️  No sensor data received.")
        print("   This could mean:")
        print("   • Engine is off (some sensors need engine running)")
        print("   • ECU doesn't support AC 81 method")
        print("   • Try starting the engine and run again")
    
    ser.close()
    print("\n[EXIT] Disconnected")
    return 0


if __name__ == "__main__":
    exit(main())
