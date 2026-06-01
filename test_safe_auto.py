"""
Safe Sensor Test - Auto-run version (no prompts)
"""
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

SAFE_SENSORS = [
    ("RPM", 0x12, 0x01, "rpm", 2, lambda d: ((d[0]<<8)|d[1]) * 12.5),
    ("AFM_V", 0x12, 0x04, "V", 2, lambda d: ((d[0]<<8)|d[1]) * 0.005),
    ("COOLANT", 0x11, 0x01, "C", 1, lambda d: d[0] - 50),
    ("STFT", 0x11, 0x5F, "%", 1, lambda d: d[0] if d[0] < 128 else d[0]-256),
    ("LTFT", 0x11, 0x61, "%", 1, lambda d: d[0] if d[0] < 128 else d[0]-256),
    ("SPEED_MPH", 0x11, 0x02, "mph", 1, lambda d: d[0] * 1.24274),
    ("SPEED_KPH", 0x12, 0x1A, "kph", 2, lambda d: (d[0]<<8)|d[1]),
]

def hexdump(data):
    return ' '.join(f'{b:02X}' for b in data)

def checksum(data):
    return sum(data) & 0xFF

def init_nisscom(port):
    print(f"[INIT] Opening {port} at 10400 baud...")
    ser = serial.Serial(port, 10400, timeout=1)
    handle = ser._port_handle
    
    ser.reset_input_buffer()
    time.sleep(0.05)
    
    print("[INIT] Sending BREAK signal...")
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    print("[INIT] Sending init bytes...")
    for b in [0x81, 0x10, 0xFC, 0x81, 0x0E]:
        ser.write(bytes([b]))
        time.sleep(0.01)
    
    time.sleep(0.3)
    resp = ser.read(ser.in_waiting)
    print(f"[INIT] RX: {hexdump(resp)}")
    
    if 0xC1 in resp:
        print("[INIT] ECU connected!")
    return ser

def read_sensors(ser):
    # Build AC 81 frame
    frame = [0xAC, 0x81]
    for name, addr0, addr1, unit, size, parser in SAFE_SENSORS:
        frame.extend([0x02, addr0, addr1])
    frame.insert(0, len(frame))
    frame.append(checksum(frame))
    
    print(f"[TX] AC 81: {hexdump(bytes(frame))}")
    ser.reset_input_buffer()
    ser.write(bytes(frame))
    time.sleep(0.3)
    
    ack = ser.read(ser.in_waiting)
    print(f"[RX] {hexdump(ack)}")
    
    # Send 0x21 to read
    read_cmd = bytes([0x04, 0x21, 0x81, 0x04, 0x01, 0xAB])
    print(f"[TX] 0x21: {hexdump(read_cmd)}")
    ser.write(read_cmd)
    time.sleep(0.4)
    
    resp = ser.read(ser.in_waiting)
    print(f"[RX] {hexdump(resp)}")
    
    # Parse
    results = {}
    if 0x61 in resp:
        idx = resp.index(0x61)
        if idx + 2 < len(resp):
            offset = idx + 2
            for name, addr0, addr1, unit, size, parser in SAFE_SENSORS:
                if offset + size <= len(resp):
                    data = resp[offset:offset+size]
                    try:
                        results[name] = (parser(data), unit)
                    except:
                        pass
                    offset += size
    return results

def main():
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    
    print("="*60)
    print("NISSCOM SAFE SENSOR TEST (Auto)")
    print("="*60)
    print(f"Port: {port}")
    print("Make sure ignition is ON!")
    print()
    
    try:
        ser = init_nisscom(port)
        print()
        
        results = read_sensors(ser)
        
        if results:
            print("\n--- SENSOR READINGS ---")
            for name, (val, unit) in results.items():
                print(f"  {name:12} {val:8.1f} {unit}")
            print("-----------------------")
            print("\nSuccess! Try live mode:")
            print("  python test_safe_auto.py COM5 -live")
        else:
            print("\nNo sensor data. Try:")
            print("  1. Start engine")
            print("  2. Check OBD connection")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
