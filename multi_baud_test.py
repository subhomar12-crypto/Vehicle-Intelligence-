#!/usr/bin/env python3
"""Multi-baudrate wake-up test"""
import serial
import time

print('='*50)
print('MULTI-BAUDRATE WAKE-UP TEST')
print('='*50)

# Try 300 baud wake-up
print('1. Trying 300 baud...')
ser = serial.Serial('COM5', 300, timeout=1)
ser.write(bytes([0x00]))
time.sleep(0.1)
ser.close()

# 1200 baud
print('2. Trying 1200 baud...')
ser = serial.Serial('COM5', 1200, timeout=1)
time.sleep(0.1)
ser.close()

# 9600 baud
print('3. Trying 9600 baud...')
ser = serial.Serial('COM5', 9600, timeout=1)
time.sleep(0.1)
ser.close()

# 10400 baud - K-line init
print('4. Trying 10400 baud...')
ser = serial.Serial('COM5', 10400, timeout=1)
for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
    ser.write(bytes([b]))
    time.sleep(0.01)
time.sleep(0.5)
resp = ser.read(ser.in_waiting)
if resp:
    print(f'   Response: {resp.hex()}')
    print(f'   Bytes: {" ".join(f"{b:02X}" for b in resp)}')
else:
    print('   No response')
ser.close()

print('\nDone')
