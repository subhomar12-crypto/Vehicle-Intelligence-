import serial, time, ctypes
from ctypes import wintypes
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.EscapeCommFunction.restype = wintypes.BOOL
SB, CB, SD = 8, 9, 5

def cs(d): return sum(d)&0xFF

def read(ser,r,a):
    c=[5,0x22,r,a,4,1,0];c[6]=cs(c[:6])
    ser.reset_input_buffer()
    ser.write(bytes(c))
    time.sleep(0.3)
    resp=ser.read(ser.in_waiting)
    hx=' '.join(f'{b:02X}' for b in resp)
    if 0x62 in resp:
        i=resp.index(0x62)
        if i+4<len(resp): 
            return resp[i+3],resp[i+4],hx
    return None,None,hx

print("[INIT] COM5...")
ser=serial.Serial('COM5',10400,timeout=1)
h=ser._port_handle
ser.reset_input_buffer()
k32.EscapeCommFunction(h,SD);time.sleep(0.025)
k32.EscapeCommFunction(h,SB);time.sleep(0.025)
k32.EscapeCommFunction(h,CB);time.sleep(0.025)
if ser.in_waiting: ser.read(ser.in_waiting)
for b in [0x81,0x10,0xFC,0x81,0x0E]: ser.write(bytes([b]));time.sleep(0.01)
time.sleep(0.3); ser.read(ser.in_waiting)
print("[OK] Connected\n")

print("Raw responses:")
b1,b2,hx=read(ser,0x11,0x01)
print(f"  Coolant (11 01): {hx}")
if b1: print(f"    -> {b1} - 50 = {b1-50}C")

b1,b2,hx=read(ser,0x12,0x01)
print(f"  RPM (12 01): {hx}")
if b1: 
    raw=(b1<<8)|b2
    print(f"    -> Raw: {raw} = {raw*12.5:.0f} RPM")
else:
    print("    -> No data (engine not running?)")

b1,b2,hx=read(ser,0x12,0x04)
print(f"  AFM (12 04): {hx}")
if b1:
    raw=(b1<<8)|b2
    print(f"    -> Raw: {raw} = {raw*0.005:.2f}V")

ser.close()
print("\nDone!")
