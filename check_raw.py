#!/usr/bin/env python3
"""Check raw sensor responses"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK, SETDTR = 8, 9, 5

def connect():
    ser = serial.Serial('COM5', 10400, timeout=1)
    handle = ser._port_handle
    
    ser.reset_input_buffer()
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    time.sleep(0.3)
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    return ser

def read_raw(ser, reg, addr):
    cmd = [0x05, 0x22, reg, addr, 0x04, 0x01, 0]
    cmd[6] = sum(cmd[:6]) & 0xFF
    
    ser.reset_input_buffer()
    for b in cmd:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    time.sleep(0.3)
    response = []
    for _ in range(5):
        if ser.in_waiting:
            response.extend(list(ser.read(ser.in_waiting)))
        time.sleep(0.05)
    
    return response

ser = connect()

print("RAW SENSOR RESPONSES:")
print("="*50)

# Coolant
resp = read_raw(ser, 0x11, 0x01)
print(f"Coolant (11 01): {' '.join(f'{b:02X}' for b in resp)}")

# RPM
resp = read_raw(ser, 0x12, 0x01)
print(f"RPM     (12 01): {' '.join(f'{b:02X}' for b in resp)}")

# AFM
resp = read_raw(ser, 0x12, 0x04)
print(f"AFM     (12 04): {' '.join(f'{b:02X}' for b in resp)}")

# Speed
resp = read_raw(ser, 0x12, 0x1A)
print(f"Speed   (12 1A): {' '.join(f'{b:02X}' for b in resp)}")

# TPS
resp = read_raw(ser, 0x11, 0x5F)
print(f"TPS     (11 5F): {' '.join(f'{b:02X}' for b in resp)}")

ser.close()
