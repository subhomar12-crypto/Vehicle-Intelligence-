# CONSULT-II Sensor Reading - Quick Start Guide

## What You Now Have

| File | Purpose |
|------|---------|
| `consult2_sensor_reader.py` | **Main library** - Complete protocol implementation |
| `read_sensors_now.py` | **Quick test** - Just run to see live data |
| `identify_sensors.py` | **Discovery tool** - Figure out what parameters mean |
| `log_sensors.py` | **Data logger** - Record to CSV for analysis |

## Quick Start

### 1. Simple Test (Read sensors immediately)

```bash
# Edit COM_PORT in the file first, then:
python read_sensors_now.py
```

### 2. Identify What Sensors Are What

```bash
python identify_sensors.py
```

This will:
- Connect to your ECU
- Read all parameters 0x00-0x20
- Show you which ones change (live sensors)
- Try to interpret values (temp, RPM, voltage, etc.)

**Use this to figure out which 0xA0 parameter = which sensor**

### 3. Log Data to CSV

```bash
python log_sensors.py
```

Creates a timestamped CSV file with all sensor readings.

## How It Works

### Service 0xA0 (Direct ECU Reads)

```python
from consult2_sensor_reader import Consult2SensorReader

reader = Consult2SensorReader('COM5')
reader.connect()

# Read a single parameter
status, data = reader.read_sensor_a0(0x01)  # Parameter 0x01
if status == 'ok':
    print(f"Got {len(data)} bytes: {data.hex()}")
```

### AC 81 + 0x21 (MCU Buffered - Faster)

```python
# Read multiple sensors in one request
results = reader.read_sensors_ac81([0, 2])  # RPM and Coolant
# Returns: {0: 1250.0, 2: 82.5}  (sensor_id: value)
```

### Live Monitoring

```python
# Monitor sensors continuously
reader.monitor_sensors([0, 2], interval=0.5, duration=60.0)
```

## Sensor Database

Edit `consult2_sensor_reader.py` to add your discovered sensors:

```python
ECM_SENSORS = {
    0: SensorDef("Engine RPM", "RPM", 0x12, 0x01, SensorType.RPM, "rpm", 0, 8000),
    2: SensorDef("Coolant Temperature", "Coolant", 0x11, 0x01, SensorType.TEMP_C, "°C", -40, 150),
    # Add yours here...
}
```

## Finding COM Port

### Windows
```bash
# In Command Prompt
mode

# Or in Python
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

### Linux (Raspberry Pi)
```bash
ls /dev/ttyUSB*
# or
ls /dev/ttyACM*
```

## Next Steps

1. **Run `identify_sensors.py`** to map 0xA0 parameters
2. **Update `ECM_SENSORS`** with your findings
3. **Use `consult2_sensor_reader.py`** as a library in your own code

## Safety Notes

⚠️ **DO NOT scan random parameter ranges** - Some can trigger actuators!

✅ **Safe ranges** (from your testing):
- 0x00-0x05: Known safe
- 0x01, 0x03: Confirmed working

❌ **Avoid** (unless you know what you're doing):
- 0x04-0x20: Triggered engine shutdown in testing
- Actuator commands (unknown parameters)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Connection failed" | Check ignition is ON, try different COM port |
| "No parameters found" | ECU may need different parameter IDs |
| "Timeout" | Increase wait time in read_sensor_a0() |
| "Echo only" | BREAK signal not working - check adapter |

## Advanced: Using in Your Code

```python
from consult2_sensor_reader import Consult2SensorReader, ECM_SENSORS

reader = Consult2SensorReader('COM5')
if reader.connect():
    # Your custom logic here
    while True:
        values = reader.read_sensors_ac81([0, 1, 2, 5])
        rpm = values.get(0, 0)
        coolant = values.get(2, 0)
        
        if coolant > 100:
            print("WARNING: Engine overheating!")
        
        time.sleep(1)
    
    reader.disconnect()
```
