# CONSULT-II Protocol - NDS II Reverse Engineering

Reverse engineered from **NDS II 2_53.exe** using dnSpy + ildasm decompilation.

Target: **2003 Nissan Patrol** with **RB25DET** engine via **Nisscom USB adapter**.

---

## 1. Hardware Architecture

```
ECU <-- K-line --> MCU (inside Nisscom) <-- FTDI FT232R --> USB --> PC
                   ^
                   |
            Requires BREAK signal
            to activate forwarding
```

- **K-line**: Single-wire half-duplex, 10400 baud
- **FTDI Chip**: FT232R USB-to-serial
- **MCU**: Internal microcontroller that gates K-line access
- **Protocol**: ISO 14230 (KWP2000) framing, CONSULT-II commands

---

## 2. MCU Activation (BREAK Signal)

The Nisscom adapter has an internal MCU that will NOT forward data to the ECU
until it receives a BREAK signal sequence. This was the root cause of all
"echo-only" responses.

### Discovered in: `GClass7::method_20(bool)`

```csharp
// Decompiled from NDS II
public void method_20(bool bool_3)
{
    if (this.int_0 != -1)
    {
        if (bool_3)
            GClass7.EscapeCommFunction(this.int_0, 8L);  // SETBREAK
        else
            GClass7.EscapeCommFunction(this.int_0, 9L);  // CLRBREAK
    }
}
```

### Activation Sequence

```python
# Windows
kernel32.EscapeCommFunction(handle, SETDTR)    # 5 = Set DTR
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, SETBREAK)  # 8 = Set BREAK
time.sleep(0.025)
kernel32.EscapeCommFunction(handle, CLRBREAK)  # 9 = Clear BREAK
time.sleep(0.025)
```

```python
# Linux (Raspberry Pi 5)
import fcntl, termios
TIOCSBRK = 0x5427
TIOCCBRK = 0x5428
fd = ser.fileno()

# Set DTR via pyserial
ser.dtr = True
time.sleep(0.025)

fcntl.ioctl(fd, TIOCSBRK)   # Set BREAK
time.sleep(0.025)
fcntl.ioctl(fd, TIOCCBRK)   # Clear BREAK
time.sleep(0.025)
```

### EscapeCommFunction Constants

| Value | Constant   | Purpose           |
|-------|------------|-------------------|
| 5     | SETDTR     | Assert DTR line   |
| 6     | CLRDTR     | Deassert DTR line |
| 8     | SETBREAK   | Set BREAK state   |
| 9     | CLRBREAK   | Clear BREAK state |

---

## 3. ECU Session Initialization

After MCU activation, send the ISO 14230 StartCommunication request.

### Init Frame

```
TX: 81 10 FC 81 0E
    |  |  |  |  └── Checksum (0x81+0x10+0xFC+0x81 = 0x20E & 0xFF = 0x0E)
    |  |  |  └───── Service ID: StartCommunication (0x81)
    |  |  └──────── Source: Tester (0xFC)
    |  └─────────── Target: ECM (0x10)
    └────────────── Format: 1 data byte, addressing present
```

### Expected Response

```
RX: 83 FC 10 C1 5D 8F 3C
    |  |  |  |  |  |  └── Checksum
    |  |  |  |  └──┴───── Key bytes (0x5D, 0x8F)
    |  |  |  └──────────── Positive response: StartComm (0xC1 = 0x81 + 0x40)
    |  |  └─────────────── Source: ECM (0x10)
    |  └──────────────────  Target: Tester (0xFC)
    └─────────────────────  Format: 3 data bytes
```

### Byte-by-byte TX with inter-byte delay

```python
init_bytes = bytes([0x81, 0x10, 0xFC, 0x81, 0x0E])
for byte in init_bytes:
    ser.write(bytes([byte]))
    time.sleep(0.010)  # 10ms inter-byte delay
```

---

## 4. Live Data Polling - Complete Architecture

### Three Protocol Layers

Deep IL analysis revealed the NDS II data polling uses a **3-stage handshake**
between NDS II software, the Nisscom MCU, and the ECU:

```
NDS II Software          Nisscom MCU           ECU (KWP2000)
     |                        |                      |
     |-- AC 81 frame -------->|                      |
     |   (sensor list)        |                      |
     |                        |-- 0xA0 param N ----->|
     |                        |<-- E0 data ----------|
     |                        |-- 0xA0 param N+1 --->|
     |                        |<-- E0 data ----------|
     |                        |   (repeats per sensor)|
     |<-- EC 81 response -----|                      |
     |   (MCU acknowledges)   |                      |
     |                        |                      |
     |-- 21 81 04 01 -------->|                      |
     |   (read collected data)|                      |
     |<-- 61 81 [data...] ----|                      |
     |   (all sensor data     |                      |
     |    concatenated)       |                      |
```

### Stage 1: method_3() - Configure Sensor List

NDS II builds an AC 81 frame listing which sensors it wants and sends it to
the Nisscom MCU. **This is an MCU command, NOT an ECU command.**

```
TX to MCU: [LEN] AC 81 [02 ADDR0 ADDR1]... [CS]
```

### Stage 2: method_4() - MCU Acknowledgment

The MCU responds with EC 81 (positive response to AC = AC + 0x40). This
confirms the MCU received the sensor configuration. The MCU then internally
queries the ECU using 0xA0 service calls for each requested sensor.

```
RX from MCU: [...] EC 81 [...]
```

### Stage 3: method_5() → method_6() - Read Collected Data

NDS II sends `ReadDataByLocalIdentifier` (service 0x21) with record 0x81
to retrieve the collected sensor data from the MCU's buffer:

```
TX to MCU: 04 21 81 04 01 AB
           |  |  |  |  |  └── Checksum (04+21+81+04+01 = AB)
           |  |  |  └──┴───── Sub-parameters (constant)
           |  |  └──────────── Record ID: 0x81
           |  └─────────────── Service: ReadDataByLocalIdentifier
           └────────────────── Length: 4 data bytes

RX from MCU: [LEN] 61 81 [sensor_data...] [CS]
                   |  |   └── All sensor values concatenated in request order
                   |  └────── Record ID echo
                   └───────── Positive response (0x21 + 0x40)
```

method_6() calls `GClass5::smethod_0()` which parses the concatenated data
using a 56-case switch statement, advancing through the buffer by 1 or 2
bytes per sensor depending on the sensor type.

### Data Polling Loop

After method_6 processes data, it spawns a new Write thread that calls
method_5() again, creating a continuous poll loop:

```
method_3() → method_4() → method_5() → method_6() → method_5() → method_6() ...
  (once)      (once)       (repeat)      (repeat)     (repeat)     (repeat)
```

### Service 0xA0 - Nissan Proprietary Data Read (ECU Direct)

When bypassing the MCU (direct serial to ECU), this is the service to use.

**Request Format:**
```
02 A0 [PARAM] [CHECKSUM]
|  |  |       └── Sum of all bytes & 0xFF
|  |  └────────── Parameter ID (ECU-native, NOT same as NDS II sensor index)
|  └───────────── Service ID: Nissan data read
└──────────────── Format byte: 2 data bytes, no addressing
```

**Positive Response:**
```
[LEN] E0 [PARAM_ECHO] [DATA...] [CHECKSUM]
      |  |             └────────── Sensor data bytes
      |  └─────────────────────── Echo of requested parameter
      └────────────────────────── Positive response (0xA0 + 0x40)
```

**Negative Response:**
```
03 7F A0 [ERROR_CODE] [CHECKSUM]
```

### Error Code 0x78 - Response Pending

The ECU returns NRC 0x78 when it needs more time to process. When this is
received, wait 500-800ms and keep reading for the final positive response.

### CRITICAL SAFETY WARNING

**DO NOT blind-scan 0xA0 parameters.** During testing, scanning unknown
parameter ranges (0x04-0x20) triggered actuator commands that shut down
the engine and produced a P0605 DTC. Only test parameters that are:
1. Confirmed safe from previous testing (0x01, 0x02, 0x03, 0x06)
2. Mapped from decompiled sensor definitions (known read-only addresses)
3. Tested one-at-a-time with the engine OFF first

### Supported vs Rejected Services (tested on ECU ID: 1VC816)

| Service | Name                     | Result    |
|---------|--------------------------|-----------|
| 0x10    | StartDiagnosticSession   | NRC 0x11 (not supported) |
| 0x1A    | ReadECUIdentification    | WORKS     |
| 0x21    | ReadDataByLocalId        | NRC 0x12 (when sent directly to ECU) |
| 0x22    | ReadDataByCommonId       | NRC 0x12 (when sent directly to ECU) |
| 0xA0    | Nissan Data Read         | WORKS (ECU native) |
| 0xAC    | (MCU internal command)   | Echo only (not forwarded to ECU) |

**Note:** Service 0x21 works when sent through the MCU (method_5 uses it
successfully). When sent directly to the ECU bypassing the MCU, it returns
NRC 0x12. This confirms the MCU intercepts 0x21 and returns its buffered data.

### NDS II Internal Frame (AC 81) - MCU Command Reference

```
[LEN] AC 81 [ENTRY_1] [ENTRY_2] ... [ENTRY_N] [CHECKSUM]
```

Where each entry is `02 [ADDR0] [ADDR1]`:

| ADDR0 | Meaning                | Response Data |
|-------|------------------------|---------------|
| 0x11  | 1-byte sensor value    | 1 byte        |
| 0x12  | 2-byte sensor value    | 2 bytes (HI, LO) |

### GClass7::method_41 - Write Function Analysis

The serial write function does **NOT transform data**. It sends the byte
array as-is to the serial port via Windows WriteFile API. A 0x53 ('S')
prefix byte is written only to the debug log (BinaryWriter), not to the
serial port. This confirms the MCU firmware handles all protocol translation.

---

## 5. Sensor Definitions

Extracted from `frmMain::method_82()` in the NDS II decompilation.

### ECM Sensors (gclass2_0)

| Index | Name             | ADDR0 | ADDR1 | Bytes | Scaling Formula                 | Unit |
|-------|------------------|-------|-------|-------|---------------------------------|------|
| 0     | Engine RPM       | 0x12  | 0x01  | 2     | `(HI*256 + LO) * 12.5`         | RPM  |
| 1     | Air Flow Volts   | 0x12  | 0x04  | 2     | `(HI*256 + LO) * 0.005`        | V    |
| 2     | Water Temp       | 0x11  | 0x01  | 1     | `byte - 50`                    | C    |
| 3     | Short Fuel Trim  | 0x11  | 0x5F  | 1     | raw                             | %    |
| 4     | Long Fuel Trim   | 0x11  | 0x61  | 1     | raw                             | %    |
| 5     | Speed Sensor     | 0x11  | 0x02  | 1     | `byte * 1.24274`                | mph  |
| 6     | Vehicle Speed    | 0x12  | 0x1A  | 2     | `HI*256 + LO`                  | kph  |

### Temperature Notes (from decompilation)

- Celsius mode: `value = byte - 50`
- Fahrenheit mode: `value = (byte - 50) * 1.8 + 32`
- Selection controlled by `GClass5::bool_10`

### Speed Notes

- mph mode: `value = byte * 1.24274`
- kph mode: `value = byte` (direct)
- Selection controlled by `GClass5::bool_9`

---

## 6. Frame Examples

### Service 0xA0: Single Parameter Read

```
TX: 02 A0 01 A3
    |  |  |  └── Checksum: (02+A0+01) & FF = A3
    |  |  └───── Parameter 0x01
    |  └──────── Service 0xA0
    └─────────── Format: 2 data bytes

RX: [echo] 03 E0 01 55 39
           |  |  |  |  └── Checksum
           |  |  |  └───── Data byte (0x55 = 85 decimal)
           |  |  └──────── Echo of param
           |  └─────────── Positive response (0xA0 + 0x40)
           └────────────── Format: 3 data bytes
```

### Service 0xA0: Confirmed Working Parameters

```
Param 0x01:  TX: 02 A0 01 A3  ->  RX: 03 E0 01 55 39   (data=0x55)
Param 0x03:  TX: 02 A0 03 A5  ->  RX: 02 E0 03 E5      (data=0x03)
```

### ECU Identification (0x1A 0x81)

```
TX: 02 1A 81 9D
RX: 07 5A 31 56 43 38 31 36 CA
         "1  V  C  8  1  6"       -> ECU ID: 1VC816
```

### NDS II Internal Frames (AC 81) - Reference Only

These are sent to the Nisscom MCU, not the ECU:

```
RPM only:       05 AC 81 02 12 01 E3
RPM + Coolant:  08 AC 81 02 12 01 02 11 01 49
All 7 sensors:  14 AC 81 02 12 01 02 12 04 02 11 01 02 11 5F 02 11 61 02 11 02 02 12 1A [CS]
```

---

## 7. Response Parsing

### Response Structure

On K-line half-duplex, the response includes:
1. **Echo** of the transmitted frame (loopback on K-line)
2. **ECU response** data

### Parsing Steps

```
Full RX buffer:
[echo of TX frame] [ECU response bytes]
                    ^
                    data starts here
```

### ECU Response Data Order

Response data bytes arrive in the same order as the sensors were requested.
Each sensor returns the number of bytes indicated by ADDR0:

- ADDR0 = 0x11 -> 1 response byte
- ADDR0 = 0x12 -> 2 response bytes (HI, LO)

### Example: RPM + Coolant Response

```
TX: 08 AC 81 02 12 01 02 11 01 49
RX: [echo: 08 AC 81 02 12 01 02 11 01 49] [RPM_HI] [RPM_LO] [TEMP]

RPM  = (RPM_HI * 256 + RPM_LO) * 12.5
TEMP = TEMP_BYTE - 50  (Celsius)
```

---

## 8. Write Path (Code Flow)

Extracted from IL disassembly of `frmDataDisplay`.

### Data Poll Sequence

```
frmDataDisplay_Load()
  └── method_3()                    // Build and send poll frame
        ├── Build 71-byte buffer
        │     ├── byte[0] = length
        │     ├── byte[1] = 0xAC
        │     ├── byte[2] = 0x81
        │     ├── For each sensor in GClass5::byte_0:
        │     │     ├── byte[n*3+3] = 0x02
        │     │     ├── byte[n*3+4] = GClass2::method_6(0)  // ADDR0
        │     │     └── byte[n*3+5] = GClass2::method_6(1)  // ADDR1
        │     ├── Trim array to actual size
        │     └── Append checksum via getCheckSum()
        │
        ├── GClass7::method_24(0)   // Set TX mode (GEnum4)
        ├── GClass7::method_41()    // WriteFile() to serial
        ├── GClass7::method_24(1)   // Set RX mode
        └── GClass7::method_40()    // ReadFile() from serial
              └── Fires DataReceived delegate
                    └── myCommPort_DataReceived()
                          └── Switch on GClass5::byte_18 (state machine)
                                └── Case 5: Parse sensor data
                                      └── Scaling per sensor type
```

### GClass7::method_41(byte[]) - The Write Function

```
PurgeComm(handle, 12)          // Clear TX+RX buffers
WriteFile(handle, data, len, &written, &overlapped)
```

### GClass7::method_40(int) - The Read Function

```
ReadFile(handle, buffer, count, &read, &overlapped)
  └── If async: WaitForSingleObject() then GetOverlappedResult()
  └── Fires DataReceived callback with buffer
```

---

## 9. GClass2 - Sensor Data Object

```csharp
class GClass2
{
    uint8  byte_0;     // method_0() / method_1() - data byte count (1 or 2)
    string string_0;   // method_2() / method_3() - short name ("RPM")
    string string_1;   // method_4() / method_5() - long name ("Engine RPM")
    uint8  byte_1;     // method_6(0) / method_7(0,x) - address byte 0
    uint8  byte_2;     // method_6(1) / method_7(1,x) - address byte 1
    // method_6(uint8 index) returns address byte at index
    // method_7(uint8 index, uint8 value) sets address byte

    int16  short_0;    // method_8() / method_9()   - min value
    int16  short_1;    // method_10() / method_11()  - max value
    int16  short_2;    // method_12() / method_13()  - current raw value
    uint8  byte_3;     // method_14() / method_15()  - ?
    uint8  byte_4;     // method_16() / method_17()  - ?
    uint8  byte_5;     // method_18() / method_19()  - ?
    float  float_0;    // method_20() / method_21()  - scaled display value

    bool   bool_0;     // method_22() / method_23()  - enabled flag?
    bool   bool_1;     // method_24() / method_25()  - visible flag?
}
```

---

## 10. Checksum Calculation

Extracted from `frmDataDisplay::getCheckSum(uint8[] Sdata)`:

```python
def checksum(data):
    """Sum all bytes, return lowest 8 bits."""
    return sum(data) & 0xFF
```

The checksum covers all bytes in the frame **before** the checksum byte itself.

---

## 11. Communication Parameters

| Parameter       | Value        |
|-----------------|--------------|
| Baud rate       | 10400        |
| Data bits       | 8            |
| Stop bits       | 1            |
| Parity          | None         |
| Flow control    | None         |
| ECM address     | 0x10         |
| Tester address  | 0xFC         |

---

## 12. Complete Startup Procedure

```
1.  Open serial port at 10400 baud, 8N1
2.  Set DTR (EscapeCommFunction 5 / ioctl TIOCMBIS)
3.  Wait 25ms
4.  Set BREAK (EscapeCommFunction 8 / ioctl TIOCSBRK)
5.  Wait 25ms
6.  Clear BREAK (EscapeCommFunction 9 / ioctl TIOCCBRK)
7.  Wait 25ms
8.  Flush RX buffer
9.  Send init: 81 10 FC 81 0E (with 10ms inter-byte delay)
10. Wait 500ms
11. Read response, expect: 83 FC 10 C1 5D 8F 3C
12. Session is active -> start polling
13. Send data requests: 02 A0 [PARAM] [CHECKSUM]
14. Read response, handle NRC 0x78 (wait longer)
15. Parse positive response (E0 prefix): extract data bytes
16. Apply scaling formulas from sensor table
```

### Timing Notes

- After device replug: wait 1 second before opening port
- After rapid scanning: device may need replug to recover
- NRC 0x78: wait 500-800ms for final response
- Inter-command delay: 100ms minimum between 0xA0 requests

---

## 13. Raspberry Pi 5 Notes

### BREAK Signal on Linux

```python
import fcntl

TIOCSBRK = 0x5427  # Set break
TIOCCBRK = 0x5428  # Clear break

fd = serial_port.fileno()
fcntl.ioctl(fd, TIOCSBRK)  # Start BREAK
time.sleep(0.025)
fcntl.ioctl(fd, TIOCCBRK)  # Stop BREAK
```

### DTR on Linux

```python
import termios

TIOCMBIS = 0x5416  # Set modem bits
TIOCM_DTR = 0x002

buf = struct.pack('I', TIOCM_DTR)
fcntl.ioctl(fd, TIOCMBIS, buf)
```

Or simpler with pyserial:
```python
ser.dtr = True
```

### USB Device Path

The Nisscom FTDI adapter will appear as `/dev/ttyUSB0` (or similar).
Verify with:
```bash
ls -la /dev/ttyUSB*
dmesg | grep FTDI
```

---

## 14. File References

| File | Purpose |
|------|---------|
| `consult2_data_poll.py` | Python test script for Windows data polling |
| `nisscom_working_final.py` | Working ECU connection script |
| `nds_final.py` | BREAK signal test script |
| `nds_il.txt` | Full IL disassembly of NDS II 2_53.exe |

---

## 15. Key Decompilation Locations

| Line (nds_il.txt) | Content |
|--------------------|---------|
| 100977 | `GClass7::method_41(uint8[])` - WriteFile wrapper |
| 100870 | `GClass7::method_40(int)` - ReadFile wrapper |
| 151640 | `frmDataDisplay::method_3()` - Poll frame builder |
| 152100 | `frmDataDisplay::getCheckSum()` - Checksum function |
| 152146 | `frmDataDisplay::myCommPort_DataReceived()` - Response parser |
| 370900 | Sensor initialization (RPM at index 0) |
| 81855  | Response scaling (RPM at case 0: `*12.5`) |
| 142265 | `frmDataDisplay` class definition |
