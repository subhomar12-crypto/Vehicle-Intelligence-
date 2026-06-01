#!/usr/bin/env python3
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK = 8, 9
SETDTR = 5

def cs(d):
    return sum(d) & 0xFF

ser = serial.Serial('COM5', 10400, timeout=1)
handle = ser._port_handle

# Init
ser.reset_input_buffer()
kernel32.EscapeCommFunction(handle, SETDTR)
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, SETBREAK)
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, CLRBREAK)
time.sleep(0.025)
if ser.in_waiting:
    ser.read(ser.in_waiting)
ser.write(bytes([0x81, 0x10, 0xFC, 0x81, 0x0E]))
time.sleep(0.3)
ser.read(ser.in_waiting)

# Read RPM
cmd = [0x05, 0x22, 0x12, 0x01, 0x04, 0x01, 0]
cmd[6] = cs(cmd[:6])
ser.reset_input_buffer()
ser.write(bytes(cmd))
time.sleep(0.25)
resp = ser.read(ser.in_waiting)
print(f'RPM Raw: {resp.hex()}')
print(f'Bytes: {" ".join(f"{b:02X}" for b in resp)}')

# Parse
reg_hi, reg_lo = 0x12, 0x01
for i in range(len(resp) - 3):
    if resp[i] == 0x62 and resp[i+1] == reg_hi and resp[i+2] == reg_lo:
        print(f'Found 0x62 at position {i}')
        b1 = resp[i+3] if i + 3 < len(resp) else None
        b2 = resp[i+4] if i + 4 < len(resp) else None
        if b1 is not None and b2 is not None:
            print(f'Data bytes: {b1:02X}, {b2:02X}')
            rpm = ((b1 << 8) | b2) * 12.5
            print(f'RPM = {rpm:.0f}')

ser.close()
