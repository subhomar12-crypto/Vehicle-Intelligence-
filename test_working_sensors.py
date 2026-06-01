#!/usr/bin/env python3
"""
Working Nisscom Sensor Reader
Uses correct ISO 14230 initialization and register 0x11 for all sensors
"""

import serial
import time
import ctypes
from ctypes import wintypes

# Windows API
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL

SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6
SETRTS = 3
CLRRTS = 4

PORT = 'COM5'
BAUD = 10400


def checksum(data):
    """Calculate Nissan checksum (sum of all bytes) & 0xFF"""
    return sum(data) & 0xFF


def iso_fast_init(ser):
    """ISO 14230-2 Fast Init - this is what works!"""
    handle = ser._port_handle
    
    # W5: Wake-up pattern
    ser.baudrate = 5
    ser.write(bytes([0x00]))
    time.sleep(0.025)
    
    # W4: Low for 25ms
    ser.baudrate = BAUD
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    # W3: High for 25ms
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    
    return True


def init_ecu(ser):
    """Initialize ECU communication using ISO 14230"""
    ser.reset_input_buffer()
    
    # Send W5 pattern
    iso_fast_init(ser)
    
    # Clear any garbage
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Send StartCommunication request
    # Format: [Len] [Tgt] [Src] [Svc] [CS]
    init_frame = [0x81, 0x33, 0xF1, 0x81, 0x66]
    ser.write(bytes(init_frame))
    time.sleep(0.3)
    
    resp = ser.read(ser.in_waiting)
    if len(resp) >= 5 and 0xC1 in resp:
        return True
    return False


def read_sensor(ser, register_hi, register_lo):
    """Read sensor using Service 0x22 (ReadDataByIdentifier)"""
    # Build request: [Len] [Tgt] [Src] [Svc] [RegHi] [RegLo] [CS]
    # For Nissan, Len includes everything except checksum
    frame = [0x05, 0x33, 0xF1, 0x22, register_hi, register_lo]
    frame.append(checksum(frame))
    
    ser.reset_input_buffer()
    ser.write(bytes(frame))
    time.sleep(0.25)
    
    resp = ser.read(ser.in_waiting)
    
    # Parse response - look for positive response 0x62
    if len(resp) >= 7:
        # Find 0x62 in response
        for i in range(len(resp) - 4):
            if resp[i] == 0x62:
                # Next bytes should be register and data
                if i + 3 < len(resp):
                    return resp[i+3], resp[i+4] if i + 4 < len(resp) else None
    
    return None, None


def read_sensor_11(ser, offset):
    """
    Read sensor from register 0x11 with offset.
    This is how the working implementation reads all sensors.
    """
    frame = [0x05, 0x33, 0xF1, 0x22, 0x11, offset]
    frame.append(checksum(frame))
    
    ser.reset_input_buffer()
    ser.write(bytes(frame))
    time.sleep(0.25)
    
    resp = ser.read(ser.in_waiting)
    
    # Debug
    print(f"  [11 {offset:02X}] Raw: {' '.join(f'{b:02X}' for b in resp)}")
    
    # Parse - look for 0x62 followed by 11 offset
    for i in range(len(resp) - 3):
        if resp[i] == 0x62 and resp[i+1] == 0x11 and resp[i+2] == offset:
            if i + 3 < len(resp):
                return resp[i+3]
    
    return None


def main():
    print("=" * 60)
    print("NISSCOM WORKING SENSOR READER")
    print("=" * 60)
    print(f"Port: {PORT}, Baud: {BAUD}")
    print()
    
    print("[INIT] Opening serial port...")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"  Port opened: {ser.is_open}")
    
    print("\n[INIT] Initializing ECU (ISO 14230 Fast Init)...")
    if init_ecu(ser):
        print("  [OK] ECU connected!")
    else:
        print("  [FAIL] No ECU response")
        ser.close()
        return
    
    print("\n" + "=" * 60)
    print("READING SENSORS")
    print("=" * 60)
    
    # Read common sensors using register 0x11 with offsets
    # Based on nisscom_working_final.py
    
    sensors = {
        0x01: ("Coolant Temp", "°C", lambda x: x - 50),
        0x04: ("RPM Low", "raw", lambda x: x),
        0x05: ("RPM High", "raw", lambda x: x),
        0x07: ("Speed", "km/h", lambda x: x),
        0x08: ("Battery", "V", lambda x: x * 0.08),
        0x09: ("MAF/AFM", "V", lambda x: x * 0.005),
        0x0A: ("Throttle", "%", lambda x: x * 100 / 255),
    }
    
    results = {}
    
    for offset, (name, unit, formula) in sensors.items():
        value = read_sensor_11(ser, offset)
        if value is not None:
            scaled = formula(value)
            results[name] = (value, scaled, unit)
            print(f"  {name}: {scaled:.2f} {unit} (raw: 0x{value:02X})")
        else:
            print(f"  {name}: No response")
    
    # Calculate RPM from high/low bytes
    if "RPM Low" in results and "RPM High" in results:
        low = results["RPM Low"][0]
        high = results["RPM High"][0]
        rpm = (high * 256 + low) * 12.5
        print(f"  RPM: {rpm:.0f} (from 0x{high:02X}{low:02X})")
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    
    ser.close()


if __name__ == "__main__":
    main()
