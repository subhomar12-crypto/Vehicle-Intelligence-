#!/usr/bin/env python3
"""Auto-run sensor test (no prompts)"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK, SETDTR = 8, 9, 5

def checksum(data):
    return sum(data) & 0xFF

def connect(port):
    print(f"Connecting to {port}...")
    ser = serial.Serial(port, 10400, timeout=1)
    handle = ser._port_handle
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)
    
    # BREAK
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Init
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    # Wait
    time.sleep(0.3)
    response = []
    for _ in range(5):
        if ser.in_waiting:
            response.extend(list(ser.read(ser.in_waiting)))
        time.sleep(0.05)
    
    if response:
        print(f"Response: {' '.join(f'{b:02X}' for b in response)}")
        if 0x83 in response or 0xC1 in response:
            print("ECU CONNECTED!")
            return ser
    
    print("FAILED to connect")
    ser.close()
    return None

def read_sensor(ser, reg, addr):
    cmd = [0x05, 0x22, reg, addr, 0x04, 0x01, 0]
    cmd[6] = checksum(cmd[:6])
    
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
    
    if 0x62 in response:
        try:
            idx = response.index(0x62)
            if idx + 3 < len(response):
                if response[idx+1] == reg and response[idx+2] == addr:
                    return response[idx+3]
        except:
            pass
    return None

# Main
print("="*50)
print("AUTO SENSOR TEST")
print("="*50)

ser = connect('COM5')
if ser:
    print("\nReading sensors...")
    
    val = read_sensor(ser, 0x11, 0x01)
    if val:
        print(f"COOLANT: {val - 50}C (raw=0x{val:02X})")
    
    val = read_sensor(ser, 0x12, 0x01)
    if val:
        print(f"RPM: {int(val * 12.5)} (raw=0x{val:02X})")
    
    val = read_sensor(ser, 0x12, 0x04)
    if val:
        print(f"AFM: {val * 0.005:.2f}V (raw=0x{val:02X})")
    
    val = read_sensor(ser, 0x12, 0x1A)
    if val:
        print(f"SPEED: {val}kph (raw=0x{val:02X})")
    
    ser.close()
    print("\nDone!")
else:
    print("\nCould not connect to ECU")
