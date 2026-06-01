#!/usr/bin/env python3
"""Aggressive Nisscom test - engine running"""
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK = 8, 9
SETDTR, CLRDTR = 5, 6

print('='*60)
print('AGGRESSIVE NISSCOM TEST - ENGINE RUNNING')
print('='*60)
print()

def try_init(description, baud, init_bytes, break_time=0.07, delay_after=0.5):
    print(f'{description}...')
    try:
        ser = serial.Serial('COM5', baud, timeout=1)
        handle = ser._port_handle
        
        # Clear and set lines
        kernel32.EscapeCommFunction(handle, CLRDTR)
        time.sleep(0.05)
        kernel32.EscapeCommFunction(handle, SETDTR)
        time.sleep(0.05)
        
        # BREAK
        kernel32.EscapeCommFunction(handle, SETBREAK)
        time.sleep(break_time)
        kernel32.EscapeCommFunction(handle, CLRBREAK)
        time.sleep(0.05)
        
        if ser.in_waiting:
            ser.read(ser.in_waiting)
        
        # Send init
        for b in init_bytes:
            ser.write(bytes([b]))
            time.sleep(0.02)
        
        time.sleep(delay_after)
        resp = ser.read(ser.in_waiting)
        ser.close()
        
        if resp:
            hex_str = ' '.join(f'{b:02X}' for b in resp)
            print(f'  RX: {hex_str}')
            if 0xC1 in resp or 0x83 in resp or 0x7F not in resp:
                # Check if it's more than just echo
                if len(resp) > len(init_bytes):
                    print(f'  >>> SUCCESS! ECU responding!')
                    return True, resp
                else:
                    print(f'  Echo only')
            else:
                print(f'  Negative response')
        else:
            print(f'  No response')
        return False, resp
    except Exception as e:
        print(f'  Error: {e}')
        return False, b''

# Test 1: Standard init at 10400
success, resp = try_init('Test 1: Standard 10400 baud', 10400, [0x81, 0x10, 0xFC, 0x81, 0x0E])

# Test 2: Longer BREAK
if not success:
    success, resp = try_init('Test 2: Longer BREAK (150ms)', 10400, [0x81, 0x10, 0xFC, 0x81, 0x0E], break_time=0.15)

# Test 3: Shorter BREAK
if not success:
    success, resp = try_init('Test 3: Shorter BREAK (25ms)', 10400, [0x81, 0x10, 0xFC, 0x81, 0x0E], break_time=0.025)

# Test 4: 9600 baud init
if not success:
    success, resp = try_init('Test 4: 9600 baud', 9600, [0x81, 0x10, 0xFC, 0x81, 0x0E])

# Test 5: Different init bytes (target address 0x01 = ECM)
if not success:
    success, resp = try_init('Test 5: Init to ECM (01)', 10400, [0x81, 0x01, 0xF1, 0x81, 0x0E])

# Test 6: Fast init (ISO 14230)
if not success:
    print('Test 6: ISO 14230 Fast Init...')
    ser = serial.Serial('COM5', 10400, timeout=1)
    handle = ser._port_handle
    
    # Toggle DTR for wake-up
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
    
    # StartCommunication request
    for b in [0xC1, 0x33, 0xF1, 0x81, 0x66]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting)
    ser.close()
    
    if resp:
        hex_str = ' '.join(f'{b:02X}' for b in resp)
        print(f'  RX: {hex_str}')
        if 0xC1 in resp or len(resp) > 5:
            print(f'  >>> SUCCESS!')
            success = True
    else:
        print(f'  No response')

# If we got success, try reading sensors
if success:
    print('\n' + '='*60)
    print('ATTEMPTING SENSOR READ...')
    print('='*60)
    
    time.sleep(0.5)
    ser = serial.Serial('COM5', 10400, timeout=1)
    
    # Read coolant
    cmd = [0x05, 0x22, 0x11, 0x01, 0x04, 0x01, 0x00]
    cmd[6] = sum(cmd[:6]) & 0xFF
    ser.write(bytes(cmd))
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    if resp and 0x62 in resp:
        print(f'Coolant response: {" ".join(f"{b:02X}" for b in resp)}')
    
    ser.close()

print('\n' + '='*60)
print('DONE')
print('='*60)
