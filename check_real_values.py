"""
Check what the real values should be

Compare these readings to your car's dashboard:
- Coolant temp gauge position
- Is engine idling? (RPM)
- Any other gauges
"""
import serial, time, ctypes
from ctypes import wintypes

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.EscapeCommFunction.restype = wintypes.BOOL

SB, CB, SD = 8, 9, 5

def cs(d): return sum(d) & 0xFF

def init(p):
    ser = serial.Serial(p, 10400, timeout=1)
    h = ser._port_handle
    ser.reset_input_buffer()
    k32.EscapeCommFunction(h, SD); time.sleep(0.025)
    k32.EscapeCommFunction(h, SB); time.sleep(0.025)
    k32.EscapeCommFunction(h, CB); time.sleep(0.025)
    if ser.in_waiting: ser.read(ser.in_waiting)
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]: 
        ser.write(bytes([b])); time.sleep(0.01)
    time.sleep(0.3); ser.read(ser.in_waiting)
    return ser

def read(ser, r, a):
    c = [0x05, 0x22, r, a, 0x04, 0x01, 0]
    c[6] = cs(c[:6])
    ser.reset_input_buffer()
    ser.write(bytes(c))
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    # Parse
    if 0x62 in resp:
        i = resp.index(0x62)
        if r == 0x11 and i + 4 < len(resp):  # 1-byte
            return resp[i + 4]
        elif r == 0x12 and i + 5 < len(resp):  # 2-byte
            return (resp[i + 4] << 8) | resp[i + 5]
    return None

print("="*60)
print("CHECK REAL VALUES AGAINST YOUR DASHBOARD")
print("="*60)
print()
print("What does your car show right now?")
print("- Engine temp gauge: (cold / warm / hot)")
print("- Is engine running? (yes / no)")
print("- If running, what RPM?")
print()
print("\nReading sensors in 3 seconds...")
time.sleep(3)

ser = init('COM5')

print("\n" + "="*60)
print("SENSOR READINGS")
print("="*60)

# Coolant
raw_c = read(ser, 0x11, 0x01)
if raw_c:
    print(f"\n[COOLANT RAW: {raw_c} (0x{raw_c:02X})]")
    print(f"  Option 1: {raw_c - 50}C  ({(raw_c-50)*9/5+32:.1f}F)  <- Standard Nissan")
    print(f"  Option 2: {raw_c - 40}C  ({(raw_c-40)*9/5+32:.1f}F)")
    print(f"  Option 3: {raw_c * 0.75:.1f}C  ({raw_c*0.75*9/5+32:.1f}F)")
    print(f"  Option 4: {raw_c}C  (no offset)")

# AFM Voltage
raw_a = read(ser, 0x12, 0x04)
if raw_a:
    print(f"\n[AFM RAW: {raw_a} (0x{raw_a:04X})]")
    print(f"  Option 1: {raw_a * 0.005:.3f}V  <- Standard Nissan")
    print(f"  Option 2: {raw_a * 0.01:.3f}V")
    print(f"  Option 3: {raw_a / 200:.3f}V")
    print(f"  Option 4: {raw_a * 0.001:.3f}V")

# RPM
raw_r = read(ser, 0x12, 0x01)
if raw_r:
    print(f"\n[RPM RAW: {raw_r} (0x{raw_r:04X})]")
    print(f"  Calculated: {raw_r * 12.5:.0f} RPM")

ser.close()

print("\n" + "="*60)
print("Which option matches your dashboard?")
print("="*60)
