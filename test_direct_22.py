"""
Test: Direct Sensor Reading with Service 0x22
=============================================

The AC 81 method is getting rejected. Let's try service 0x22 which is
used by the working implementation:
  Command: 05 22 11 XX 04 01 CS
  Response: 06 62 11 XX 04 01 DD DD CS (DD DD = data)

Register 0x11 = 1-byte sensors
Register 0x12 = 2-byte sensors
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

def hexdump(data):
    return ' '.join(f'{b:02X}' for b in data)

def checksum(data):
    return sum(data) & 0xFF

def init_ecu(port):
    print(f"[INIT] Opening {port}...")
    ser = serial.Serial(port, 10400, timeout=1)
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
    resp = ser.read(ser.in_waiting)
    print(f"[INIT] RX: {hexdump(resp)}")
    
    if 0xC1 in resp:
        print("[INIT] ECU connected!")
    return ser

def read_register_22(ser, reg_addr, param_addr):
    """Read using service 0x22: 05 22 REG PARAM 04 01 CS"""
    cmd = [0x05, 0x22, reg_addr, param_addr, 0x04, 0x01]
    cmd.append(checksum(cmd))
    
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.3)
    
    resp = ser.read(ser.in_waiting)
    return resp

def main():
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    
    print("="*60)
    print("DIRECT SENSOR READ - Service 0x22")
    print("="*60)
    print(f"Port: {port}")
    print()
    
    try:
        ser = init_ecu(port)
        print()
        
        # Test reading register 0x11 (1-byte sensors)
        print("Reading register 0x11 (1-byte sensors)...")
        for addr in [0x00, 0x01, 0x02, 0x20, 0x5F, 0x61]:
            resp = read_register_22(ser, 0x11, addr)
            print(f"  11 {addr:02X}: {hexdump(resp)}")
            
            # Check for positive response (0x62)
            if 0x62 in resp:
                idx = resp.index(0x62)
                if idx + 4 < len(resp):
                    data_bytes = resp[idx+3:idx+5]
                    val = data_bytes[0] if len(data_bytes) > 0 else 0
                    print(f"        -> Data: {val} (0x{val:02X})")
            time.sleep(0.1)
        
        print()
        
        # Test reading register 0x12 (2-byte sensors)
        print("Reading register 0x12 (2-byte sensors)...")
        for addr in [0x00, 0x01, 0x04, 0x1A]:
            resp = read_register_22(ser, 0x12, addr)
            print(f"  12 {addr:02X}: {hexdump(resp)}")
            
            if 0x62 in resp:
                idx = resp.index(0x62)
                if idx + 4 < len(resp):
                    data_bytes = resp[idx+3:idx+7]
                    if len(data_bytes) >= 2:
                        val = (data_bytes[0] << 8) | data_bytes[1]
                        print(f"        -> Data: {val} (0x{val:04X})")
            time.sleep(0.1)
        
        print()
        print("Test complete!")
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
