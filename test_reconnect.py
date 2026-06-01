#!/usr/bin/env python3
"""Test after reconnecting the car"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK, SETDTR = 8, 9, 5

print('='*50)
print('TEST AFTER RECONNECT')
print('='*50)

ser = serial.Serial('COM5', 10400, timeout=2)
handle = ser._port_handle

for attempt in range(3):
    print(f'\nAttempt {attempt + 1}...')
    ser.reset_input_buffer()
    
    # Send BREAK
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.05)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.05)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.1)
    
    # Clear buffer
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Send init
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.02)
    
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting)
    
    if resp:
        print(f'  Response: {" ".join(f"{b:02X}" for b in resp)}')
        if 0xC1 in resp or 0x83 in resp:
            print('  SUCCESS! ECU responding!')
            break
        elif resp == bytes([0x81, 0x10, 0xFC, 0x81, 0x0E]):
            print('  Echo only - waiting longer...')
            time.sleep(1)
    else:
        print('  No response')

# Now try reading sensors
print('\n' + '='*50)
print('READING SENSORS')
print('='*50)

def read22(ser, reg, addr):
    cmd = [0x05, 0x22, reg, addr, 0x04, 0x01, 0]
    cmd[6] = sum(cmd[:6]) & 0xFF
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.3)
    return ser.read(ser.in_waiting)

def parse_val(resp, reg, addr):
    if not resp or 0x62 not in resp:
        return None
    try:
        idx = resp.index(0x62)
        if idx + 3 < len(resp) and resp[idx+1] == reg and resp[idx+2] == addr:
            return resp[idx+3]
    except:
        pass
    return None

# Coolant
resp = read22(ser, 0x11, 0x01)
val = parse_val(resp, 0x11, 0x01)
if val:
    print(f'COOLANT: Raw={val} (0x{val:02X})')
    print(f'  Option 1: {val - 50}C')
    print(f'  Option 2: {val - 40}C')
else:
    print('COOLANT: No data')

# RPM
resp = read22(ser, 0x12, 0x01)
val = parse_val(resp, 0x12, 0x01)
if val:
    rpm = int(val * 12.5)
    print(f'RPM: {rpm}')
else:
    print('RPM: No data')

# AFM
resp = read22(ser, 0x12, 0x04)
val = parse_val(resp, 0x12, 0x04)
if val:
    print(f'AFM: Raw={val} (0x{val:02X})')
    print(f'  Option 1: {val * 0.005:.2f}V')
    print(f'  Option 2: {val * 0.01:.2f}V')
else:
    print('AFM: No data')

ser.close()
print('\nDone!')
