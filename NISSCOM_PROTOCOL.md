# Nisscom Protocol Documentation

## Overview

This document describes the working Nisscom OBD2 communication protocol for Nissan vehicles. Based on extensive testing with a live Nissan vehicle (engine running).

**Tested Configuration:**
- Port: COM5
- Baud Rate: 10400
- Vehicle: Nissan (engine running, warm)

---

## Initialization Sequence

### The Working Method: BREAK Signal + 0x81 Init

The Nisscom MCU requires a **BREAK signal** via Windows `EscapeCommFunction` to activate its bridge mode. Without this, you'll only get echo responses.

```python
import serial
import time
import ctypes
from ctypes import wintypes

# Windows API setup
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL

SETBREAK = 8
CLRBREAK = 9
SETDTR = 5

def init_ecu(ser):
    """Initialize ECU communication"""
    handle = ser._port_handle
    
    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    # Set DTR line
    kernel32.EscapeCommFunction(handle, SETDTR)
    time.sleep(0.025)
    
    # Send BREAK signal (critical!)
    kernel32.EscapeCommFunction(handle, SETBREAK)
    time.sleep(0.025)
    kernel32.EscapeCommFunction(handle, CLRBREAK)
    time.sleep(0.025)
    
    # Clear any garbage
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Send initialization frame
    init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
    ser.write(bytes(init_bytes))
    time.sleep(0.3)
    
    resp = ser.read(ser.in_waiting)
    return resp

# Usage
ser = serial.Serial('COM5', 10400, timeout=1)
resp = init_ecu(ser)

# Check response - should contain 0xC1 or 0x83 or be longer than 5 bytes
if 0xC1 in resp or 0x83 in resp or len(resp) > 5:
    print("ECU connected!")
else:
    print("Only echo - ECU not responding")
```

### Expected Response

**Good Response (ECU responding):**
```
RX: 81 10 FC 81 0E 83 FC 10 C1 5D 8F 3C
     ^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^
        Echo           ECU Response
```

**Bad Response (Echo only):**
```
RX: 81 10 FC 81 0E
     ^^^^^^^^^^^
        Echo only (no ECU)
```

---

## Sensor Reading

### Service 0x22 (Read Data By Identifier)

Once initialized, use **Service 0x22** to read sensors. The AC 81 command used by some implementations does NOT work.

### Request Format

```
[Length] [Service] [RegHi] [RegLo] [Padding] [Padding] [Checksum]
```

Example for Coolant Temp (register 0x11 0x01):
```
05 22 11 01 04 01 3F
```

- `05` = Length (5 bytes before checksum)
- `22` = Service (ReadDataByIdentifier)
- `11 01` = Register address
- `04 01` = Padding bytes
- `3F` = Checksum (sum of first 6 bytes & 0xFF)

### Checksum Calculation

```python
def checksum(data):
    """Calculate Nissan checksum"""
    return sum(data) & 0xFF

# Example
cmd = [0x05, 0x22, 0x11, 0x01, 0x04, 0x01]
cmd.append(checksum(cmd))  # 0x3F
```

### Response Format

```
[Echo...] [Length] [0x62] [RegHi] [RegLo] [Data...]
```

Example:
```
05 22 11 01 04 01 3F  05 62 11 01 87
^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^
       Echo              ECU Response
```

The positive response is `0x62` (0x22 + 0x40).

### Working Sensor Addresses

| Sensor | Register | Data Bytes | Formula | Example |
|--------|----------|------------|---------|---------|
| **Coolant Temp** | 0x11 0x01 | 1 byte | `°C = value - 50` | 0x87 → 135 - 50 = **85°C** |
| **RPM** | 0x12 0x01 | 2 bytes | `RPM = ((hi << 8) \| lo) × 12.5` | 0x00 0x47 → 71 × 12.5 = **888 RPM** |
| **AFM Voltage** | 0x12 0x04 | 2 bytes | `Volts = ((hi << 8) \| lo) × 0.005` | 0x01 0x40 → 320 × 0.005 = **1.60V** |
| **Speed** | 0x12 0x1A | 1 byte | `KPH = value` | 0x00 → **0 km/h** |

**CRITICAL BUG FIX:** When checking for valid data, use `if b1 is not None` NOT `if b1`. The RPM low byte can be `0x00` which is falsy in Python!

---

## Complete Reading Example

```python
import serial
import time
import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.EscapeCommFunction.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.EscapeCommFunction.restype = wintypes.BOOL
SETBREAK, CLRBREAK = 8, 9
SETDTR = 5

def checksum(data):
    return sum(data) & 0xFF

def init_ecu(ser):
    """Initialize ECU"""
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
    
    ser.write(bytes([0x81, 0x10, 0xFC, 0x81, 0x0E]))
    time.sleep(0.3)
    return ser.read(ser.in_waiting)

def read_sensor(ser, reg_hi, reg_lo):
    """Read sensor using Service 0x22"""
    cmd = [0x05, 0x22, reg_hi, reg_lo, 0x04, 0x01, 0]
    cmd[6] = checksum(cmd[:6])
    
    ser.reset_input_buffer()
    ser.write(bytes(cmd))
    time.sleep(0.25)
    
    resp = ser.read(ser.in_waiting)
    
    # Parse: look for 0x62 followed by register address
    for i in range(len(resp) - 3):
        if resp[i] == 0x62 and resp[i+1] == reg_hi and resp[i+2] == reg_lo:
            b1 = resp[i+3] if i + 3 < len(resp) else None
            b2 = resp[i+4] if i + 4 < len(resp) else None
            return b1, b2
    return None, None

# Main
def main():
    ser = serial.Serial('COM5', 10400, timeout=1)
    
    # Initialize
    resp = init_ecu(ser)
    if not (0xC1 in resp or 0x83 in resp or len(resp) > 5):
        print("ECU not responding")
        ser.close()
        return
    
    print("Connected! Reading sensors...")
    
    # Read Coolant
    b1, _ = read_sensor(ser, 0x11, 0x01)
    if b1 is not None:
        print(f"Coolant: {b1 - 50}°C")
    
    # Read RPM
    b1, b2 = read_sensor(ser, 0x12, 0x01)
    if b1 is not None and b2 is not None:
        rpm = ((b1 << 8) | b2) * 12.5
        print(f"RPM: {rpm:.0f}")
    
    # Read AFM
    b1, b2 = read_sensor(ser, 0x12, 0x04)
    if b1 is not None and b2 is not None:
        volts = ((b1 << 8) | b2) * 0.005
        print(f"AFM: {volts:.2f}V")
    
    # Read Speed
    b1, _ = read_sensor(ser, 0x12, 0x1A)
    if b1 is not None:
        print(f"Speed: {b1} km/h")
    
    ser.close()

if __name__ == "__main__":
    main()
```

---

## Live Data Implementation Tips

### 1. Keep Connection Open

Don't open/close the serial port for each read. Keep it open and just send read commands:

```python
ser = serial.Serial('COM5', 10400, timeout=1)
init_ecu(ser)

while running:
    coolant = read_sensor(ser, 0x11, 0x01)
    rpm = read_sensor(ser, 0x12, 0x01)
    # ... update UI
    time.sleep(0.1)  # 10 Hz update rate

ser.close()
```

### 2. Handle Timeouts Gracefully

```python
def safe_read_sensor(ser, reg_hi, reg_lo, max_retries=3):
    for _ in range(max_retries):
        result = read_sensor(ser, reg_hi, reg_lo)
        if result[0] is not None:
            return result
        time.sleep(0.05)
    return None, None
```

### 3. Re-initialize on Connection Loss

```python
last_good_read = time.time()

while running:
    data = read_sensor(ser, ...)
    if data[0] is None:
        if time.time() - last_good_read > 5:  # 5 seconds no data
            print("Reconnecting...")
            init_ecu(ser)
            last_good_read = time.time()
    else:
        last_good_read = time.time()
```

### 4. Batch Reads for Better Performance

Instead of reading one sensor at a time, you can read multiple sensors in quick succession:

```python
def read_all_sensors(ser):
    results = {}
    
    # Coolant
    b1, _ = read_sensor(ser, 0x11, 0x01)
    results['coolant'] = b1 - 50 if b1 is not None else None
    
    # RPM
    b1, b2 = read_sensor(ser, 0x12, 0x01)
    results['rpm'] = ((b1 << 8) | b2) * 12.5 if b1 is not None and b2 is not None else None
    
    # AFM
    b1, b2 = read_sensor(ser, 0x12, 0x04)
    results['afm'] = ((b1 << 8) | b2) * 0.005 if b1 is not None and b2 is not None else None
    
    # Speed
    b1, _ = read_sensor(ser, 0x12, 0x1A)
    results['speed'] = b1 if b1 is not None else None
    
    return results
```

---

## Timing Requirements

| Operation | Delay | Notes |
|-----------|-------|-------|
| BREAK signal | 25ms | Minimum 25ms BREAK |
| Between BREAK and data | 25ms | Let line settle |
| After init command | 300ms | Wait for ECU response |
| Between sensor reads | 250ms | ECU needs time to respond |
| Inter-byte delay | 10-20ms | When sending multi-byte frames |

**For live data:** You can reduce the between-read delay to ~100ms once the connection is stable, but 250ms is safer for initial reads.

---

## Common Issues & Solutions

### Issue: Echo Only (No ECU Response)

**Symptoms:** Response is exactly 5 bytes matching what was sent (e.g., `81 10 FC 81 0E`)

**Solutions:**
1. Check ignition is ON or engine is running
2. Verify OBD2 cable is firmly connected
3. Ensure BREAK signal is being sent via `EscapeCommFunction`
4. Try re-initializing after 5-10 seconds

### Issue: No Response at All

**Symptoms:** Empty response buffer

**Solutions:**
1. Check COM port is correct
2. Verify baud rate is 10400
3. Ensure no other program is using the port
4. Try physically reconnecting the adapter

### Issue: RPM Shows N/A or Wrong Value

**Symptoms:** RPM is missing or incorrect

**Cause:** Python falsy value bug - RPM low byte is `0x00` at low RPM

**Fix:** Use `if b1 is not None` instead of `if b1`

### Issue: Intermittent Connection

**Symptoms:** Works sometimes, fails other times

**Solutions:**
1. Add retry logic (3 attempts per read)
2. Re-initialize ECU after 5 seconds of no data
3. Check for loose connections
4. Verify engine is running (not just ignition ON)

---

## Raw Response Examples

### Coolant Temp (0x11 0x01)
```
TX: 05 22 11 01 04 01 3F
RX: 05 22 11 01 04 01 3F  05 62 11 01 87
                              ^^^^^^^^
                              Data: 0x87 = 135 → 135 - 50 = 85°C
```

### RPM (0x12 0x01)
```
TX: 05 22 12 01 04 01 3C
RX: 05 22 12 01 04 01 3C  05 62 12 01 00 47
                              ^^^^^^^^^^^^
                              Data: 0x00 0x47 = 71 → 71 × 12.5 = 888 RPM
```

### AFM Voltage (0x12 0x04)
```
TX: 05 22 12 04 04 01 39
RX: 05 22 12 04 04 01 39  05 62 12 04 01 40
                              ^^^^^^^^^^^^
                              Data: 0x01 0x40 = 320 → 320 × 0.005 = 1.60V
```

### Speed (0x12 0x1A)
```
TX: 05 22 12 1A 04 01 57
RX: 05 22 12 1A 04 01 57  05 62 12 1A 00
                              ^^^^^^^^^^
                              Data: 0x00 = 0 km/h
```

---

## Additional Sensor Addresses (Untested)

Based on the protocol pattern, these may work but were not tested:

| Sensor | Register | Expected Data Type |
|--------|----------|-------------------|
| Throttle Position | 0x11 0x04? | 1 byte (0-255) |
| Battery Voltage | 0x11 0x08? | 1 byte (× 0.08) |
| Intake Air Temp | 0x11 0x02? | 1 byte (value - 50) |
| O2 Sensor | 0x12 0x?? | 2 bytes |

To find more sensors, use a brute-force approach:
```python
# Scan all register combinations
for hi in [0x11, 0x12]:
    for lo in range(0x00, 0xFF):
        b1, b2 = read_sensor(ser, hi, lo)
        if b1 is not None:
            print(f"Register {hi:02X} {lo:02X}: {b1:02X} {b2:02X if b2 else '--'}")
```

---

## Reference Files

- `test_safe_sensors_v2.py` - Working sensor reader (BREAK + 0x22)
- `nisscom_working_final.py` - DLL-based implementation (alternative)
- `aggressive_test.py` - Multiple initialization attempts
- `diagnostic_test.py` - Basic ECU communication test

---

## Test Results Summary

**Working Configuration:**
- Port: COM5
- Baud: 10400
- Init: BREAK signal + 0x81 sequence
- Service: 0x22 for sensor reading

**Verified Sensors:**
- Coolant: 82°C (engine warm)
- RPM: 875 (at idle)
- AFM: 1.59V (at idle)
- Speed: 0 km/h (stationary)

**Document Version:** 1.0  
**Last Updated:** Based on live testing session  
**Status:** Working and tested with live vehicle
