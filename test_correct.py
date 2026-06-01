#!/usr/bin/env python3
"""
Working Nisscom Sensor Reader - Uses the exact approach that worked
"""

import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL

SETBREAK, CLRBREAK = 8, 9
SETDTR, CLRDTR = 5, 6

PORT = 'COM5'
BAUD = 10400


def checksum(data):
    return sum(data) & 0xFF


def init_ecu(ser):
    """ISO 14230 Fast Init - exact approach that worked"""
    handle = ser._port_handle
    
    # Toggle DTR for wake-up (3 times)
    for _ in range(3):
        kernel32.EscapeCommFunction(handle, CLRDTR)
        time.sleep(0.025)
        kernel32.EscapeCommFunction(handle, SETDTR)
        time.sleep(0.025)
    
    # BREAK
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.07)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.03)
    
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # StartCommunication request [C1 33 F1 81 66]
    init_bytes = [0xC1, 0x33, 0xF1, 0x81, 0x66]
    ser.write(bytes(init_bytes))
    time.sleep(0.5)
    
    resp = ser.read(ser.in_waiting)
    return resp


def read_sensor_11(ser, offset):
    """Read sensor using register 0x11 with offset"""
    cmd = [0x05, 0x33, 0xF1, 0x22, 0x11, offset]
    cmd.append(checksum(cmd))
    
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.3)
    
    resp = ser.read(ser.in_waiting)
    
    # Parse response - look for 0x62 0x11 offset
    for i in range(len(resp) - 3):
        if resp[i] == 0x62 and resp[i+1] == 0x11 and resp[i+2] == offset:
            if i + 3 < len(resp):
                return resp[i+3]
    return None


def main():
    print("=" * 60)
    print("NISSCOM SENSOR READER - CORRECTED")
    print("=" * 60)
    print()
    
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print("[INIT] Initializing ECU...")
    
    resp = init_ecu(ser)
    if resp:
        print(f"  Response: {' '.join(f'{b:02X}' for b in resp)}")
        if len(resp) >= 5:
            print("  [OK] ECU connected!")
        else:
            print("  [FAIL] No ECU response")
            ser.close()
            return
    else:
        print("  [FAIL] No response")
        ser.close()
        return
    
    print("\n" + "=" * 60)
    print("READING SENSORS")
    print("=" * 60)
    
    # Read sensors using register 0x11
    sensors = [
        (0x01, "Coolant Temp", lambda x: f"{x - 50}C"),
        (0x04, "RPM Low", lambda x: f"0x{x:02X}"),
        (0x05, "RPM High", lambda x: f"0x{x:02X}"),
        (0x07, "Speed", lambda x: f"{x} km/h"),
        (0x08, "Battery", lambda x: f"{x * 0.08:.1f}V"),
        (0x09, "AFM/MAF", lambda x: f"{x * 0.005:.2f}V"),
        (0x0A, "Throttle", lambda x: f"{x * 100 // 255}%"),
    ]
    
    rpm_low = None
    rpm_high = None
    
    for offset, name, fmt in sensors:
        value = read_sensor_11(ser, offset)
        if value is not None:
            print(f"  {name}: {fmt(value)} (raw: 0x{value:02X})")
            if offset == 0x04:
                rpm_low = value
            elif offset == 0x05:
                rpm_high = value
        else:
            print(f"  {name}: No response")
    
    # Calculate RPM
    if rpm_low is not None and rpm_high is not None:
        rpm_raw = (rpm_high << 8) | rpm_low
        rpm = rpm_raw * 12.5
        print(f"  RPM: {rpm:.0f}")
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    
    ser.close()


if __name__ == "__main__":
    main()
