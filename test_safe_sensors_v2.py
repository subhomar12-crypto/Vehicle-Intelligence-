#!/usr/bin/env python3
"""
Nisscom Sensor Test - Using working BREAK + 0x81 initialization
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
    """Initialize using BREAK signal - this worked before"""
    handle = ser._port_handle
    
    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    # DTR on
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    
    # BREAK signal
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    # Clear any garbage
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Send init
    init = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    ser.write(bytes(init))
    time.sleep(0.3)
    
    resp = ser.read(ser.in_waiting)
    return resp


def read_sensor_22(ser, reg_hi, reg_lo):
    """Read sensor using Service 0x22"""
    cmd = [0x05, 0x22, reg_hi, reg_lo, 0x04, 0x01, 0x00]
    cmd[6] = checksum(cmd[:6])
    
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.25)
    
    resp = ser.read(ser.in_waiting)
    
    # Look for positive response 0x62 followed by register address
    for i in range(len(resp) - 3):
        if resp[i] == 0x62 and resp[i+1] == reg_hi and resp[i+2] == reg_lo:
            # Data bytes follow immediately after register address
            b1 = resp[i+3] if i + 3 < len(resp) else None
            b2 = resp[i+4] if i + 4 < len(resp) else None
            return b1, b2
    return None, None


def main():
    print("=" * 60)
    print("NISSCOM SENSOR TEST - BREAK + 0x81 INIT")
    print("=" * 60)
    print()
    
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Port: {PORT} @ {BAUD} baud")
    print()
    
    print("[INIT] Sending BREAK + init sequence...")
    resp = init_ecu(ser)
    
    if resp:
        hex_str = ' '.join(f'{b:02X}' for b in resp)
        print(f"  RX: {hex_str}")
        
        # Check for ECU response (0xC1 or 0x83 or response longer than 5 bytes)
        if 0xC1 in resp or 0x83 in resp or len(resp) > 5:
            print("  [OK] ECU is responding!")
        else:
            print("  [WARN] Only seeing echo, but trying sensors anyway...")
    else:
        print("  [WARN] No response, trying sensors anyway...")
    
    print()
    print("=" * 60)
    print("READING SENSORS")
    print("=" * 60)
    
    # Sensor addresses that worked before
    sensors = [
        ((0x11, 0x01), "Coolant Temp", lambda b1, b2: f"{b1 - 50}C" if b1 else "N/A"),
        ((0x12, 0x01), "RPM", lambda b1, b2: f"{((b1 << 8) | (b2 or 0)) * 12.5:.0f}" if b1 is not None else "N/A"),
        ((0x12, 0x04), "AFM Voltage", lambda b1, b2: f"{((b1 << 8) | (b2 or 0)) * 0.005:.2f}V" if b1 else "N/A"),
        ((0x12, 0x1A), "Speed", lambda b1, b2: f"{b1} km/h" if b1 is not None else "N/A"),
    ]
    
    for (hi, lo), name, fmt in sensors:
        b1, b2 = read_sensor_22(ser, hi, lo)
        if b1 is not None:
            print(f"  {name}: {fmt(b1, b2)}")
        else:
            print(f"  {name}: No response")
    
    print()
    print("=" * 60)
    print("DONE - Disconnecting")
    print("=" * 60)
    
    ser.close()


if __name__ == "__main__":
    main()
