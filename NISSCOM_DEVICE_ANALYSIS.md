# Nisscom Diagnostic Device Analysis

**Vehicle:** Nissan Patrol 2003
**Device:** Nisscom USB Diagnostic Adapter
**Port:** COM5
**Date:** 2026-01-25

---

## Executive Summary

After extensive testing with multiple protocols, baud rates, and hardware configurations, the Nisscom device has been identified as a **proprietary adapter that requires Nisscom's official software** to function. It is NOT a standard OBD-II, ELM327, or Consult-II compatible device.

---

## What We Tested

### 1. Standard OBD-II/ELM327 Protocol
- **Test File:** `test_nisscom_device.py`
- **Result:** ❌ Failed - Device does not respond to ELM327 commands
- **Error:** "ATE0 did not return 'OK'"

### 2. Basic Serial Communication
- **Test File:** `test_nisscom_basic.py`
- **Result:** ✅ Device responds at 38400 baud
- **Issue:** Device only echoes commands back, no actual data

### 3. Consult-II Protocol (38400 baud)
- **Test Files:**
  - `consult2_reader.py`
  - `consult2_live_monitor.py`
  - `consult2_calibrate.py`
- **Result:** ❌ Failed - All registers returned 0x5A (command echo)
- **Readings:** RPM=1125, Temp=40°C, Speed=90 km/h (all incorrect - just echoed command byte)

### 4. Native Consult-II Protocol (9600 baud)
- **Test File:** `nissan_consult2_native.py`
- **Result:** ❌ Failed - Device echoes "FF FF EF" but doesn't acknowledge with 0x10
- **Based On:** Open-source implementations (Arduino-Nissan-Consult-Library, K11Consult, openconsult)

### 5. Alternative Initialization Methods
- **Test File:** `nissan_consult2_alternative.py`
- **Tests Performed:**
  - Standard Consult-II at 9600 baud
  - Longer delays between bytes
  - Alternative baud rates (9600, 19200, 38400, 57600, 115200)
  - Alternative command sequences (FF FF EE, FF FF 01, etc.)
  - Repeated rapid initialization
  - Wakeup sequences
  - Direct register reading
- **Result:** ❌ All methods failed - device echoes at all baud rates

### 6. Hardware Flow Control
- **Test File:** `nisscom_hardware_test.py`
- **Tests Performed:**
  - RTS/CTS hardware flow control
  - DSR/DTR hardware flow control
  - XON/XOFF software flow control
  - Manual RTS/DTR line control
- **Result:** ❌ Device continues echoing regardless of flow control settings

---

## Key Findings

### Device Behavior
1. **Echoes all commands** at all baud rates (9600, 19200, 38400, 57600, 115200)
2. **No protocol recognition** - does not respond to:
   - OBD-II commands
   - ELM327 AT commands
   - Consult-II initialization (FF FF EF)
   - Alternative initialization sequences
3. **Hardware passthrough** - acts as simple serial echo/loopback adapter
4. **Requires activation** - likely needs proprietary software to initialize

### What This Means
The Nisscom device is:
- ✅ Properly detected by Windows (COM5)
- ✅ Communicating at serial level
- ❌ NOT a standard diagnostic adapter
- ❌ NOT compatible with open-source protocols
- ❌ Requires Nisscom's proprietary software

---

## Free Software Tested (All Failed)

Based on your testing:
1. **NDS II** (Nissan Data Scan) - Did not work
2. **ECU Talk** - Did not work
3. **DDLReader** - Did not work (link was broken)

---

## Next Steps

### Option 1: Get Official Nisscom Software (Recommended)
Contact your device vendor or Nisscom directly to get the official software:
- Request software download link
- Check if device came with installation CD
- Ask vendor for support

### Option 2: Use Protocol Sniffer (When Software Available)
Once you have working Nisscom software:

1. **Run the sniffer FIRST:**
   ```bash
   cd "C:\D Drive\Predict"
   python nisscom_protocol_sniffer.py
   ```

2. **Then open Nisscom software**

3. **Connect to vehicle and read data**

4. **Stop sniffer (Ctrl+C)**

5. **Review captured logs** in `C:\D Drive\Predict\nisscom_logs\`

The sniffer will capture:
- Initialization sequence
- Command structure
- Register addresses
- Response format
- Checksums/validation

### Option 3: Reverse Engineer Protocol
After capturing with the sniffer:
1. Analyze logs to identify command patterns
2. Create Python implementation based on captured protocol
3. Build custom software to replace Nisscom software

---

## Technical Details

### Device Information
- **Port:** COM5 - USB Serial Port
- **Detection:** Properly detected by Windows Device Manager
- **Communication:** Functional serial communication
- **Baud Rates Tested:** 9600, 19200, 38400, 57600, 115200
- **Echo Behavior:** Echoes at ALL baud rates

### Consult-II Protocol Reference
Standard Nissan Consult-II protocol (for reference):
- **Baud Rate:** 9600
- **Init Command:** FF FF EF (expects 0x10 response)
- **Read Register:** 5A [count] [addr] ... F0
- **Stop Stream:** 30

**Note:** Nisscom device does NOT follow this protocol.

### Register Addresses (Standard Consult-II)
For reference when analyzing captured data:
```
0x00/0x01 - RPM (2 bytes, value/4)
0x08      - Coolant temp (1 byte, value-50)
0x0B      - Vehicle speed (1 byte, km/h)
0x0C      - Battery voltage (1 byte, value*0.08)
0x0D      - Throttle position (1 byte, value/255*100)
0x0E      - Engine load
0x11      - Intake air temp (1 byte, value-50)
```

---

## Files Created

### Test Scripts
1. `test_nisscom_device.py` - OBD-II/ELM327 test
2. `test_nisscom_basic.py` - Basic serial test
3. `test_elm327_mode.py` - ELM327 mode test
4. `consult2_reader.py` - Consult-II reader (38400 baud)
5. `consult2_live_monitor.py` - Live monitoring with CSV logging
6. `consult2_calibrate.py` - Register scanner
7. `nissan_consult2_native.py` - Native Consult-II (9600 baud)
8. `nissan_consult2_alternative.py` - Alternative init methods
9. `nisscom_hardware_test.py` - Hardware flow control test

### Tools
10. `nisscom_protocol_sniffer.py` - Protocol capture tool (use with official software)

### Documentation
11. `NISSCOM_DEVICE_ANALYSIS.md` - This file

---

## Conclusion

The Nisscom device is a proprietary adapter that **requires Nisscom's official software** to function. All open-source protocols and free software alternatives have been tested and failed.

**Immediate Action Required:**
1. Contact device vendor/Nisscom for official software
2. Once software is obtained, use the protocol sniffer to capture communication
3. We can then create custom Python implementation based on captured protocol

**Alternative Option:**
Consider purchasing a standard ELM327 or Consult-II compatible adapter that works with open-source software and protocols.

---

## Contact Information

**Vendor Support:**
- Contact your Nisscom device vendor
- Request official software download
- Ask for technical support documentation

**For Future Development:**
- Use `nisscom_protocol_sniffer.py` to capture protocol
- Logs will be saved to `C:\D Drive\Predict\nisscom_logs\`
- Share logs for Python implementation development

---

*Last Updated: 2026-01-25*
