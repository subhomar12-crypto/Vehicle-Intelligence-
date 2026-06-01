#!/usr/bin/env python3
"""Verify sensor scaling against dashboard readings"""
import serial
import time
import ctypes
from ctypes import wintypes

# Windows API for BREAK signal
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK = 8
CLRBREAK = 9
SETDTR = 5

def send_break(ser):
    """Send BREAK signal via Windows API"""
    handle = ser._port_handle
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)

def checksum(data):
    return sum(data) & 0xFF

def init_ecu(port='COM5'):
    ser = serial.Serial(port, 10400, timeout=1)
    ser.reset_input_buffer()
    send_break(ser)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    time.sleep(0.3)
    ser.read(ser.in_waiting)
    return ser

def read_sensor(ser, reg, addr):
    cmd = [0x05, 0x22, reg, addr, 0x04, 0x01, 0]
    cmd[6] = checksum(cmd[:6])
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.25)
    return ser.read(ser.in_waiting)

def parse_response(resp, reg, addr):
    """Parse ECU response and extract value"""
    if not resp:
        return None
    
    # Look for positive response 0x62
    if 0x62 not in resp:
        return None
    
    # Find the 0x62 response
    try:
        idx = resp.index(0x62)
        if idx + 3 >= len(resp):
            return None
        
        # Format: [length] [62] [reg] [addr] [data...]
        if resp[idx-1] == 0x04 and resp[idx+1] == reg and resp[idx+2] == addr:
            # Single byte value
            if idx + 3 < len(resp):
                return resp[idx + 3]
    except:
        pass
    
    return None

print('='*60)
print('NISSAN SENSOR SCALING VERIFICATION')
print('='*60)
print()
print('Compare these values with your dashboard:')
print()

ser = init_ecu('COM5')

# Coolant Temp
resp = read_sensor(ser, 0x11, 0x01)
raw = parse_response(resp, 0x11, 0x01)
if raw is not None:
    print(f'COOLANT TEMP:')
    print(f'  Raw hex: 0x{raw:02X} ({raw} decimal)')
    print(f'  Option 1: {raw - 50}C  ({(raw - 50) * 9 // 5 + 32}F)  [Standard OBD]')
    print(f'  Option 2: {raw - 40}C  ({(raw - 40) * 9 // 5 + 32}F)  [Nissan older]')
    print(f'  Option 3: {raw * 0.75 - 48:.1f}C  [Nissan specific]')
    print()

# RPM
resp = read_sensor(ser, 0x12, 0x01)
raw = parse_response(resp, 0x12, 0x01)
if raw is not None:
    print(f'RPM:')
    print(f'  Raw hex: 0x{raw:02X} ({raw} decimal)')
    print(f'  Option 1: {raw * 12.5:.0f} RPM  [Standard OBD]')
    print(f'  Option 2: {raw * 8:.0f} RPM  [Alternative]')
    print(f'  Option 3: {raw * 25:.0f} RPM  [Some Nissan]')
    print()

# AFM Voltage
resp = read_sensor(ser, 0x12, 0x04)
raw = parse_response(resp, 0x12, 0x04)
if raw is not None:
    print(f'AFM VOLTAGE:')
    print(f'  Raw hex: 0x{raw:02X} ({raw} decimal)')
    print(f'  Option 1: {raw * 0.005:.2f} V  [Standard OBD]')
    print(f'  Option 2: {raw * 0.01:.2f} V  [Alternative]')
    print(f'  Option 3: {raw / 50:.2f} V  [Nissan MAF]')
    print()

# Speed
resp = read_sensor(ser, 0x12, 0x1A)
raw = parse_response(resp, 0x12, 0x1A)
if raw is not None:
    print(f'SPEED:')
    print(f'  Raw hex: 0x{raw:02X} ({raw} decimal)')
    print(f'  Option 1: {raw} kph  [Standard OBD]')
    print(f'  Option 2: {raw * 2} kph  [Alternative]')
    print()

ser.close()

print('='*60)
print('Tell me:')
print('1. Which option matches your dashboard coolant temp?')
print('2. Which option matches your tachometer RPM?')
print('3. What does your dashboard actually show?')
print('='*60)
