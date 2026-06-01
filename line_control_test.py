#!/usr/bin/env python3
"""Test with full line control"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL

SETBREAK = 8
CLRBREAK = 9
SETDTR = 5
CLRDTR = 6
SETRTS = 3
CLRRTS = 4

print('='*50)
print('LINE CONTROL TEST')
print('='*50)

ser = serial.Serial('COM5', 10400, timeout=1)
handle = ser._port_handle

# Clear DTR and RTS first
print('Clearing DTR/RTS...')
kernel32.EscapeCommFunction(handle, CLRDTR)
kernel32.EscapeCommFunction(handle, CLRRTS)
time.sleep(0.1)

# Set DTR
print('Setting DTR...')
kernel32.EscapeCommFunction(handle, SETDTR)
time.sleep(0.05)

# Send BREAK
print('Sending BREAK...')
kernel32.EscapeCommFunction(handle, SETBREAK)
time.sleep(0.07)
kernel32.EscapeCommFunction(handle, CLRBREAK)
time.sleep(0.05)

# Set RTS
print('Setting RTS...')
kernel32.EscapeCommFunction(handle, SETRTS)
time.sleep(0.05)

if ser.in_waiting:
    ser.read(ser.in_waiting)

print('Sending init sequence...')
for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
    ser.write(bytes([b]))
    time.sleep(0.02)

time.sleep(0.5)
resp = ser.read(ser.in_waiting)

if resp:
    print(f'Response: {" ".join(f"{b:02X}" for b in resp)}')
    if len(resp) > 5:
        print('SUCCESS! ECU is responding!')
    else:
        print('Echo only - ECU not responding')
else:
    print('No response at all')

ser.close()
