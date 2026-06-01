#!/usr/bin/env python3
"""Comprehensive Nisscom test after reconnect"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK = 8, 9
SETDTR, CLRDTR = 5, 6
SETRTS, CLRRTS = 3, 4

print('='*60)
print('COMPREHENSIVE NISSCOM TEST')
print('='*60)
print()

# Method 1: Multi-baudrate with BREAK
print('METHOD 1: Multi-baudrate + BREAK')
for baud in [300, 1200, 9600]:
    try:
        ser = serial.Serial('COM5', baud, timeout=0.5)
        if baud == 300:
            ser.write(bytes([0x00]))
        time.sleep(0.1)
        ser.close()
    except:
        pass

ser = serial.Serial('COM5', 10400, timeout=1)
handle = ser._port_handle

# Send BREAK
kernel32.EscapeCommFunction(handle, SETDTR)
time.sleep(0.05)
kernel32.EscapeCommFunction(handle, SETBREAK)
time.sleep(0.05)
kernel32.EscapeCommFunction(handle, CLRBREAK)
time.sleep(0.1)

if ser.in_waiting:
    ser.read(ser.in_waiting)

# Send init
for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
    ser.write(bytes([b]))
    time.sleep(0.02)
time.sleep(0.5)
resp1 = ser.read(ser.in_waiting)
ser.close()

if resp1:
    print(f'  Response: {" ".join(f"{b:02X}" for b in resp1)}')
    if 0xC1 in resp1 or 0x83 in resp1:
        print('  SUCCESS!')
    else:
        print('  Echo only')
else:
    print('  No response')

# Wait a bit and retry
time.sleep(1)

# Method 2: Just BREAK at 10400
print('\nMETHOD 2: Direct BREAK at 10400')
ser = serial.Serial('COM5', 10400, timeout=1)
handle = ser._port_handle

# Reset lines
kernel32.EscapeCommFunction(handle, CLRDTR)
kernel32.EscapeCommFunction(handle, CLRRTS)
time.sleep(0.1)
kernel32.EscapeCommFunction(handle, SETDTR)
time.sleep(0.05)

# BREAK for 70ms
kernel32.EscapeCommFunction(handle, SETBREAK)
time.sleep(0.07)
kernel32.EscapeCommFunction(handle, CLRBREAK)
time.sleep(0.1)

kernel32.EscapeCommFunction(handle, SETRTS)

if ser.in_waiting:
    ser.read(ser.in_waiting)

for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
    ser.write(bytes([b]))
    time.sleep(0.02)
time.sleep(0.5)
resp2 = ser.read(ser.in_waiting)
ser.close()

if resp2:
    print(f'  Response: {" ".join(f"{b:02X}" for b in resp2)}')
    if 0xC1 in resp2 or 0x83 in resp2:
        print('  SUCCESS!')
    else:
        print('  Echo only')
else:
    print('  No response')

# Method 3: Try 5-baud init
print('\nMETHOD 3: 5-baud init (ISO 9141)')
ser = serial.Serial('COM5', 5, timeout=1)  # 5 baud for address
ser.write(bytes([0x33]))  # Address 0x33 for engine
time.sleep(0.2)
ser.close()

time.sleep(0.3)

ser = serial.Serial('COM5', 10400, timeout=1)
for b in [0x55, 0x01, 0x8A]:  # Sync + key bytes
    ser.write(bytes([b]))
    time.sleep(0.01)
time.sleep(0.5)
resp3 = ser.read(ser.in_waiting)
ser.close()

if resp3:
    print(f'  Response: {" ".join(f"{b:02X}" for b in resp3)}')
else:
    print('  No response')

print('\n' + '='*60)
print('RESULT:')
print('If all methods show "Echo only" or "No response", check:')
print('  1. Ignition is ON (not just ACC)')
print('  2. OBD2 cable is firmly connected')
print('  3. Nisscom device LED is on/blinking')
print('='*60)
