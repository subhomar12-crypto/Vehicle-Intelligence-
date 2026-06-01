#!/usr/bin/env python3
"""Quick diagnostic test for Nisscom ECU communication"""
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

print('=' * 50)
print('NISSCOM ECU DIAGNOSTIC TEST')
print('=' * 50)

print('Opening COM5 at 10400 baud...')
ser = serial.Serial('COM5', 10400, timeout=1)
print(f'Port opened: {ser.is_open}')

print('Sending BREAK signal...')
handle = ser._port_handle
kernel32.EscapeCommFunction(handle, SETDTR)
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, SETBREAK)
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, CLRBREAK)
time.sleep(0.025)

if ser.in_waiting:
    ser.read(ser.in_waiting)

print('Sending init sequence 81 10 FC 81 0E...')
for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
    ser.write(bytes([b]))
    time.sleep(0.01)
time.sleep(0.5)
resp = ser.read(ser.in_waiting)
print(f'Response length: {len(resp)} bytes')
if resp:
    print(f'Raw hex: {" ".join(f"{b:02X}" for b in resp)}')
else:
    print('No response!')

if resp and (0xC1 in resp or 0x83 in resp):
    print('SUCCESS: ECU is responding!')
elif resp == bytes([0x81, 0x10, 0xFC, 0x81, 0x0E]):
    print('WARNING: ECHO ONLY - ECU not responding')
else:
    print('Checking response content...')

ser.close()
print('=' * 50)
print('Test complete')
