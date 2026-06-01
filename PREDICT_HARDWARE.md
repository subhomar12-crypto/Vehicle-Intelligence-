# PREDICT Hardware Recommendations

## Document Purpose
This document provides detailed hardware specifications for a custom sensor node that works alongside the PredictOBD phone app to provide enhanced vehicle diagnostics and predictive maintenance capabilities.

---

## SYSTEM ARCHITECTURE

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        PREDICT SENSOR NODE                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     RASPBERRY PI 5 (4GB)                             │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │  │
│  │  │  WiFi AP  │  │ Bluetooth │  │   GPS     │  │  4G/LTE   │        │  │
│  │  │  Mode     │  │           │  │  Module   │  │ (Optional)│        │  │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │  │
│  │                                                                      │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │                    SENSOR INPUT HUB                           │   │  │
│  │  │  ADC (MCP3008)  │  I2C Bus  │  GPIO  │  CAN Bus Interface    │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                   │                                        │
│  ┌────────────────────────────────┼────────────────────────────────────┐  │
│  │                         SENSORS                                      │  │
│  │                                                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│  │  │ BRAKE TEMP  │  │ BRAKE TEMP  │  │ VIBRATION   │                  │  │
│  │  │ FRONT (x2)  │  │ REAR (x2)   │  │ ENGINE (x2) │                  │  │
│  │  │ K-Type TC   │  │ K-Type TC   │  │ MPU6050     │                  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │  │
│  │                                                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│  │  │ VIBRATION   │  │ FUEL PUMP   │  │ AMBIENT     │                  │  │
│  │  │ TRANS (x1)  │  │ CURRENT     │  │ TEMP        │                  │  │
│  │  │ ADXL345     │  │ ACS712      │  │ DS18B20     │                  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │  │
│  │                                                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│  │  │ OBD-II      │  │ GPS         │  │ BATTERY     │                  │  │
│  │  │ CAN BUS     │  │ NEO-6M      │  │ VOLTAGE     │                  │  │
│  │  │ MCP2515     │  │             │  │ Divider     │                  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │  │
│  │                                                                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         POWER SYSTEM                                 │  │
│  │  12V Car → Buck Converter (5V 5A) → Pi 5 + Sensors                  │  │
│  │  UPS HAT (Optional) for graceful shutdown                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WiFi/Bluetooth
                                    ▼
                        ┌─────────────────────┐
                        │   PHONE APP         │
                        │   (PredictOBD)      │
                        │   Display + Upload  │
                        └─────────────────────┘
```

---

## MAIN CONTROLLER

### Raspberry Pi 5 - 4GB RAM

**Recommendation: SUITABLE with considerations**

| Specification | Value | Assessment |
|--------------|-------|------------|
| CPU | Quad-core Cortex-A76 @ 2.4GHz | Excellent for data processing |
| RAM | 4GB LPDDR4X | Sufficient for sensor fusion |
| GPIO | 40 pins | Adequate for all sensors |
| I2C | 2 buses | Good for multiple sensors |
| SPI | 2 buses | Needed for ADC and CAN |
| WiFi | 802.11ac dual-band | Good for phone communication |
| Bluetooth | BT 5.0/BLE | Good for OBD adapter |
| Power | 5V 5A recommended | Requires stable supply |
| Operating Temp | 0-50°C | May need cooling in hot climates |

**Pros:**
- Powerful enough for real-time data processing
- Built-in WiFi for phone communication
- Good community support
- Python-friendly for integration with desktop software
- Can run local ML inference if needed

**Cons:**
- Draws more power than ESP32 (but acceptable for car use)
- Needs proper enclosure for automotive environment
- Boot time ~30 seconds (mitigated with auto-start scripts)
- May need active cooling in hot climates (Qatar: consider heatsink + fan)

**Alternative: ESP32 (Lower power, simpler)**
- Better for battery-only operation
- Faster boot (~1 second)
- Lower cost
- But: Limited processing power for complex algorithms

**Recommendation:** Stick with **Raspberry Pi 5 4GB** for its processing power and Python compatibility. The power draw is acceptable when connected to car power.

---

## COMPLETE HARDWARE LIST

### Essential Components

| Component | Model | Qty | Purpose | Est. Price (USD) |
|-----------|-------|-----|---------|------------------|
| Raspberry Pi 5 4GB | Official | 1 | Main controller | $60 |
| MicroSD Card 64GB | SanDisk Extreme | 1 | Storage | $12 |
| Pi 5 Active Cooler | Official | 1 | Cooling | $5 |
| Weatherproof Enclosure | IP65 rated | 1 | Protection | $25 |

### Temperature Sensors (Brakes)

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| K-Type Thermocouple | High temp -200°C to 1250°C | 4 | Brake rotor temp | $8 x 4 = $32 |
| MAX31855 Breakout | Adafruit | 4 | Thermocouple to digital | $15 x 4 = $60 |

**Note:** You mentioned 2 temp sensors for brakes - I recommend **4** (one per wheel) for comprehensive monitoring. The front brakes wear faster, so at minimum use 2 for front wheels.

### Vibration Sensors

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| MPU6050 | 6-axis IMU | 2 | Engine vibration | $5 x 2 = $10 |
| ADXL345 | 3-axis accelerometer | 1 | Transmission | $8 |

**Your proposal (2 engine + 1 transmission):** Good choice. The MPU6050 provides both accelerometer and gyroscope data.

**Placement:**
- Engine block: Mount near cylinder head
- Transmission: Mount on transmission housing
- Provides: Misfire detection, bearing wear, unusual vibrations

### Current Sensor (Fuel Pump)

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| ACS712 30A | Hall effect current | 1 | Fuel pump current | $6 |

**Your proposal:** Correct. The ACS712 30A module can handle the fuel pump's current draw (typically 5-8A).

**Purpose:**
- Detect fuel pump degradation (current increase = wear)
- Identify failing fuel pump before complete failure
- Monitor startup current spikes

### Additional Recommended Sensors

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| DS18B20 | Waterproof temp | 2 | Ambient + coolant external | $5 x 2 = $10 |
| NEO-6M GPS | GPS module | 1 | Location + speed verification | $12 |
| Voltage Divider Circuit | Custom | 1 | Battery voltage monitoring | $3 |
| MCP3008 | 8-channel ADC | 1 | Analog sensor inputs | $8 |

### Communication Interfaces

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| MCP2515 CAN Module | SPI CAN bus | 1 | Direct OBD-II CAN | $8 |
| OBD-II to DB9 Cable | J1962 to DB9 | 1 | OBD port connection | $10 |
| 4G LTE HAT | SIM7600 (optional) | 1 | Independent connectivity | $45 |

### Power System

| Component | Model | Qty | Purpose | Est. Price |
|-----------|-------|-----|---------|------------|
| DC-DC Buck Converter | LM2596 12V→5V 5A | 1 | Power regulation | $8 |
| Fuse Holder + 5A Fuse | Automotive | 1 | Circuit protection | $5 |
| Power Cable | OBD-II power tap | 1 | 12V from OBD port | $8 |
| UPS HAT (Optional) | PiSugar 3 | 1 | Graceful shutdown | $40 |

---

## SENSOR SPECIFICATIONS

### K-Type Thermocouple (Brake Temperature)

```
Temperature Range: -200°C to +1250°C
Accuracy: ±0.75% or ±2.2°C
Response Time: ~0.5 seconds
Wire Length: 1m recommended
Mounting: Bracket near rotor (not touching)

MAX31855 Converter:
- 14-bit resolution
- Cold junction compensation
- SPI interface
- 3.3V or 5V compatible
```

**Installation Notes:**
- Mount sensor tip 5-10mm from brake rotor
- Use high-temp wiring insulation
- Shield wires from electrical interference
- Front brakes reach 300-400°C during hard braking
- Rear brakes typically 100-200°C lower

### MPU6050 (Engine Vibration)

```
Accelerometer Range: ±2g, ±4g, ±8g, ±16g (configurable)
Gyroscope Range: ±250, ±500, ±1000, ±2000 °/s
Resolution: 16-bit ADC
Sample Rate: Up to 1kHz
Interface: I2C (address 0x68 or 0x69)
Operating Temp: -40°C to +85°C
```

**Installation Notes:**
- Mount rigidly on engine block (epoxy or bracket)
- Orient consistently (note axis directions)
- Use ±8g range for automotive vibration
- Sample at 100Hz minimum for vibration analysis
- Cover with conformal coating for moisture protection

### ADXL345 (Transmission Vibration)

```
Range: ±2g, ±4g, ±8g, ±16g
Resolution: 13-bit (4mg/LSB at ±2g)
Sample Rate: Up to 3200Hz
Interface: I2C or SPI
Operating Temp: -40°C to +85°C
Power: 23µA at 100Hz
```

**Installation Notes:**
- Mount on transmission bell housing
- High sample rate useful for bearing analysis
- Can detect gear mesh frequencies
- Different I2C address from MPU6050 if on same bus

### ACS712-30A (Fuel Pump Current)

```
Current Range: ±30A
Sensitivity: 66mV/A
Output: Analog voltage (centered at VCC/2)
Response Time: 5µs
Operating Temp: -40°C to +85°C
```

**Installation Notes:**
- Wire in series with fuel pump positive lead
- Keep wires short to minimize noise
- Add 100nF bypass capacitor
- Analog output requires ADC (MCP3008)
- Baseline reading when pump is healthy for comparison

### DS18B20 (Ambient Temperature)

```
Temperature Range: -55°C to +125°C
Accuracy: ±0.5°C (-10°C to +85°C)
Resolution: 9-12 bits configurable
Interface: 1-Wire (multiple sensors on one wire)
Power: 3.0V to 5.5V
```

**Use Cases:**
- Ambient air temperature (outside vehicle)
- Engine bay temperature (heat soak detection)
- Compare to OBD coolant temp for radiator efficiency

### NEO-6M GPS Module

```
Channels: 50 (22 tracking, 66 acquisition)
Update Rate: Up to 5Hz
Position Accuracy: 2.5m CEP
Velocity Accuracy: 0.1 m/s
Interface: UART (9600 baud default)
Antenna: Ceramic patch (external recommended)
```

**Purpose:**
- Verify speed accuracy vs OBD
- Track trip routes
- Geofencing
- Timestamp synchronization

---

## WIRING DIAGRAM

```
                         RASPBERRY PI 5 GPIO
                    ┌─────────────────────────────────┐
                    │  3.3V ●──────────●  5V          │
        DS18B20 ────│  GPIO2/SDA ●────● 5V           │──── Power
                    │  GPIO3/SCL ●────● GND          │
        MPU6050 ────│  GPIO4 ●────────● GPIO14/TX    │──── GPS TX
         (I2C)      │  GND ●──────────● GPIO15/RX    │──── GPS RX
                    │  GPIO17 ●───────● GPIO18       │
        ADXL345 ────│  GPIO27 ●───────● GND          │
         (I2C)      │  GPIO22 ●───────● GPIO23       │
                    │  3.3V ●─────────● GPIO24       │
                    │  GPIO10/MOSI ●──● GND          │
     MAX31855 ──────│  GPIO9/MISO ●───● GPIO25       │
       (SPI0)       │  GPIO11/SCLK ●──● GPIO8/CE0    │──── MAX31855 #1 CS
                    │  GND ●──────────● GPIO7/CE1    │──── MAX31855 #2 CS
                    │  GPIO0 ●────────● GPIO1        │
     MCP3008 ───────│  GPIO5 ●────────● GND          │
       (SPI1)       │  GPIO6 ●────────● GPIO12       │──── MAX31855 #3 CS
     MCP2515 ───────│  GPIO13 ●───────● GND          │
       (SPI1)       │  GPIO19 ●───────● GPIO16       │──── MAX31855 #4 CS
                    │  GPIO26 ●───────● GPIO20       │──── MCP3008 CS
                    │  GND ●──────────● GPIO21       │──── MCP2515 CS
                    └─────────────────────────────────┘

POWER CONNECTIONS:
┌────────────┐     ┌─────────────────┐     ┌──────────────┐
│ 12V from   │────►│ Buck Converter  │────►│ 5V to Pi &   │
│ OBD Port   │     │ (12V to 5V 5A)  │     │ All Sensors  │
└────────────┘     └─────────────────┘     └──────────────┘

SENSOR CONNECTIONS DETAIL:

1. Brake Temp (MAX31855 x4):
   - VCC → 3.3V
   - GND → GND
   - SCK → GPIO11 (shared SPI clock)
   - SO  → GPIO9 (shared SPI MISO)
   - CS  → GPIO8, 7, 12, 16 (individual chip select)

2. Vibration (MPU6050 x2):
   - VCC → 3.3V
   - GND → GND
   - SDA → GPIO2
   - SCL → GPIO3
   - AD0 → GND (addr 0x68) or VCC (addr 0x69)

3. Vibration (ADXL345):
   - VCC → 3.3V
   - GND → GND
   - SDA → GPIO2 (shared I2C)
   - SCL → GPIO3 (shared I2C)
   - Address: 0x53

4. Current Sensor (ACS712):
   - VCC → 5V
   - GND → GND
   - OUT → MCP3008 CH0

5. Ambient Temp (DS18B20):
   - VCC → 3.3V
   - GND → GND
   - DATA → GPIO4 (with 4.7K pullup)

6. GPS (NEO-6M):
   - VCC → 3.3V
   - GND → GND
   - TX → GPIO15 (Pi RX)
   - RX → GPIO14 (Pi TX)

7. ADC (MCP3008):
   - VCC → 3.3V
   - VREF → 3.3V
   - GND → GND
   - CLK → SPI1_SCLK
   - DOUT → SPI1_MISO
   - DIN → SPI1_MOSI
   - CS → GPIO20

8. CAN Bus (MCP2515):
   - VCC → 5V
   - GND → GND
   - SCK → SPI1_SCLK
   - MOSI → SPI1_MOSI
   - MISO → SPI1_MISO
   - CS → GPIO21
   - INT → GPIO25
```

---

## SOFTWARE COMPONENTS

### Required Python Libraries

```python
# requirements.txt for Pi sensor node

# GPIO and hardware
RPi.GPIO==0.7.1
gpiozero==2.0
spidev==3.6
smbus2==0.4.3

# Sensors
adafruit-circuitpython-max31855==3.2.21
adafruit-circuitpython-mpu6050==1.2.5
adafruit-circuitpython-adxl345==1.14.4
adafruit-circuitpython-ads1x15==2.2.23  # Alternative ADC
w1thermsensor==2.3.0  # DS18B20

# CAN bus
python-can==4.3.1

# GPS
pyserial==3.5
pynmea2==1.19.0

# Communication
flask==3.0.0  # REST API
flask-socketio==5.3.6  # WebSocket
requests==2.31.0

# Data processing
numpy==1.26.3
scipy==1.12.0  # FFT for vibration analysis
```

### Main Sensor Daemon

```python
#!/usr/bin/env python3
"""
PREDICT Sensor Node - Main Data Collection Daemon
Runs on Raspberry Pi 5
"""

import time
import json
import threading
from datetime import datetime
from collections import deque
import numpy as np

# Sensor libraries
import board
import busio
import digitalio
import adafruit_max31855
import adafruit_mpu6050
import adafruit_adxl345
from w1thermsensor import W1ThermSensor
import serial
import pynmea2
from gpiozero import MCP3008

# Communication
from flask import Flask, jsonify
from flask_socketio import SocketIO
import requests


class PredictSensorNode:
    """Main sensor data collection and transmission system."""

    def __init__(self, config_file='config.json'):
        self.config = self._load_config(config_file)
        self.running = False

        # Data buffers
        self.brake_temps = {'fl': 0, 'fr': 0, 'rl': 0, 'rr': 0}
        self.vibration_data = {
            'engine_1': {'accel': [0, 0, 0], 'gyro': [0, 0, 0]},
            'engine_2': {'accel': [0, 0, 0], 'gyro': [0, 0, 0]},
            'trans': {'accel': [0, 0, 0]}
        }
        self.fuel_pump_current = 0.0
        self.ambient_temp = 0.0
        self.gps_data = {'lat': 0, 'lon': 0, 'speed': 0, 'satellites': 0}
        self.battery_voltage = 0.0

        # Vibration analysis buffers
        self.vibration_buffer = deque(maxlen=1000)  # 10 seconds at 100Hz

        # Initialize sensors
        self._init_sensors()

        # Setup API server
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self._setup_routes()

    def _load_config(self, config_file):
        try:
            with open(config_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'sample_rate_hz': 100,
                'upload_interval_sec': 1,
                'phone_ip': '192.168.4.2',
                'server_url': 'https://predict.previlium.com'
            }

    def _init_sensors(self):
        """Initialize all sensor connections."""

        # SPI for thermocouples
        self.spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

        # Thermocouple chip selects
        cs_pins = [board.D8, board.D7, board.D12, board.D16]
        self.thermocouples = {}
        positions = ['fl', 'fr', 'rl', 'rr']

        for pos, cs_pin in zip(positions, cs_pins):
            try:
                cs = digitalio.DigitalInOut(cs_pin)
                self.thermocouples[pos] = adafruit_max31855.MAX31855(self.spi, cs)
            except Exception as e:
                print(f"Thermocouple {pos} init failed: {e}")

        # I2C for IMU sensors
        self.i2c = busio.I2C(board.SCL, board.SDA)

        try:
            self.mpu6050_1 = adafruit_mpu6050.MPU6050(self.i2c, address=0x68)
            self.mpu6050_1.accelerometer_range = adafruit_mpu6050.Range.RANGE_8_G
        except Exception as e:
            print(f"MPU6050 #1 init failed: {e}")
            self.mpu6050_1 = None

        try:
            self.mpu6050_2 = adafruit_mpu6050.MPU6050(self.i2c, address=0x69)
            self.mpu6050_2.accelerometer_range = adafruit_mpu6050.Range.RANGE_8_G
        except Exception as e:
            print(f"MPU6050 #2 init failed: {e}")
            self.mpu6050_2 = None

        try:
            self.adxl345 = adafruit_adxl345.ADXL345(self.i2c)
            self.adxl345.range = adafruit_adxl345.Range.RANGE_8_G
        except Exception as e:
            print(f"ADXL345 init failed: {e}")
            self.adxl345 = None

        # ADC for current sensor
        try:
            self.adc_current = MCP3008(channel=0)
        except Exception as e:
            print(f"MCP3008 init failed: {e}")
            self.adc_current = None

        # DS18B20 temperature
        try:
            self.temp_sensors = W1ThermSensor.get_available_sensors()
        except Exception as e:
            print(f"DS18B20 init failed: {e}")
            self.temp_sensors = []

        # GPS
        try:
            self.gps_serial = serial.Serial('/dev/ttyS0', 9600, timeout=1)
        except Exception as e:
            print(f"GPS init failed: {e}")
            self.gps_serial = None

    def read_brake_temps(self):
        """Read all brake rotor temperatures."""
        for pos, tc in self.thermocouples.items():
            try:
                self.brake_temps[pos] = tc.temperature
            except Exception:
                pass  # Sensor read failed, keep last value

    def read_vibration(self):
        """Read all vibration sensors."""
        if self.mpu6050_1:
            try:
                self.vibration_data['engine_1']['accel'] = list(self.mpu6050_1.acceleration)
                self.vibration_data['engine_1']['gyro'] = list(self.mpu6050_1.gyro)
            except Exception:
                pass

        if self.mpu6050_2:
            try:
                self.vibration_data['engine_2']['accel'] = list(self.mpu6050_2.acceleration)
                self.vibration_data['engine_2']['gyro'] = list(self.mpu6050_2.gyro)
            except Exception:
                pass

        if self.adxl345:
            try:
                self.vibration_data['trans']['accel'] = list(self.adxl345.acceleration)
            except Exception:
                pass

        # Add to vibration analysis buffer
        combined = (
            self.vibration_data['engine_1']['accel'] +
            self.vibration_data['engine_2']['accel'] +
            self.vibration_data['trans']['accel']
        )
        self.vibration_buffer.append(combined)

    def read_fuel_pump_current(self):
        """Read fuel pump current from ACS712."""
        if self.adc_current:
            try:
                # ACS712 30A: 66mV/A, centered at VCC/2
                raw = self.adc_current.value  # 0-1
                voltage = raw * 3.3  # Convert to voltage
                # Centered at 1.65V (VCC/2), sensitivity 0.066V/A
                self.fuel_pump_current = (voltage - 1.65) / 0.066
            except Exception:
                pass

    def read_ambient_temp(self):
        """Read ambient temperature from DS18B20."""
        if self.temp_sensors:
            try:
                self.ambient_temp = self.temp_sensors[0].get_temperature()
            except Exception:
                pass

    def read_gps(self):
        """Read GPS position and speed."""
        if self.gps_serial:
            try:
                line = self.gps_serial.readline().decode('ascii', errors='replace')
                if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                    msg = pynmea2.parse(line)
                    if hasattr(msg, 'latitude'):
                        self.gps_data['lat'] = msg.latitude
                        self.gps_data['lon'] = msg.longitude
                    if hasattr(msg, 'spd_over_grnd'):
                        self.gps_data['speed'] = msg.spd_over_grnd * 1.852  # knots to km/h
                    if hasattr(msg, 'num_sats'):
                        self.gps_data['satellites'] = int(msg.num_sats)
            except Exception:
                pass

    def calculate_vibration_metrics(self):
        """Analyze vibration data for anomalies."""
        if len(self.vibration_buffer) < 100:
            return None

        data = np.array(list(self.vibration_buffer))

        # RMS vibration level
        rms = np.sqrt(np.mean(data ** 2, axis=0))

        # Peak values
        peak = np.max(np.abs(data), axis=0)

        # Crest factor (peak/RMS) - higher = more impulsive (bearing damage)
        crest_factor = peak / (rms + 0.0001)

        # FFT for frequency analysis (detect specific frequencies)
        # Engine: Expect peaks at RPM/60 Hz and harmonics
        # Transmission: Gear mesh frequencies

        return {
            'rms': rms.tolist(),
            'peak': peak.tolist(),
            'crest_factor': crest_factor.tolist()
        }

    def get_sensor_packet(self):
        """Build complete sensor data packet."""
        vib_metrics = self.calculate_vibration_metrics()

        return {
            'timestamp': datetime.now().isoformat(),
            'brake_temps': self.brake_temps,
            'vibration': self.vibration_data,
            'vibration_metrics': vib_metrics,
            'fuel_pump_current': self.fuel_pump_current,
            'ambient_temp': self.ambient_temp,
            'gps': self.gps_data,
            'battery_voltage': self.battery_voltage
        }

    def _setup_routes(self):
        """Setup Flask API routes."""

        @self.app.route('/data')
        def get_data():
            return jsonify(self.get_sensor_packet())

        @self.app.route('/health')
        def health():
            return jsonify({
                'status': 'ok',
                'sensors': {
                    'thermocouples': len(self.thermocouples),
                    'mpu6050_1': self.mpu6050_1 is not None,
                    'mpu6050_2': self.mpu6050_2 is not None,
                    'adxl345': self.adxl345 is not None,
                    'gps': self.gps_serial is not None,
                    'temp_sensors': len(self.temp_sensors)
                }
            })

        @self.socketio.on('connect')
        def handle_connect():
            print("Client connected")

    def sensor_loop(self):
        """Main sensor reading loop."""
        interval = 1.0 / self.config['sample_rate_hz']

        while self.running:
            start = time.time()

            self.read_brake_temps()
            self.read_vibration()
            self.read_fuel_pump_current()
            self.read_ambient_temp()
            self.read_gps()

            # Emit via WebSocket
            self.socketio.emit('sensor_data', self.get_sensor_packet())

            # Sleep for remaining time
            elapsed = time.time() - start
            if elapsed < interval:
                time.sleep(interval - elapsed)

    def start(self):
        """Start the sensor node."""
        self.running = True

        # Start sensor thread
        self.sensor_thread = threading.Thread(target=self.sensor_loop, daemon=True)
        self.sensor_thread.start()

        # Start Flask server
        self.socketio.run(self.app, host='0.0.0.0', port=5000)

    def stop(self):
        """Stop the sensor node."""
        self.running = False


if __name__ == '__main__':
    node = PredictSensorNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
```

---

## ENCLOSURE & MOUNTING

### Enclosure Requirements

```
Material: ABS plastic or aluminum (heat dissipation)
Rating: IP65 minimum (dust/water resistant)
Size: ~200x150x80mm (fit Pi + HATs + connections)
Features:
- Cable glands for sensor wires
- Ventilation with dust filter
- Mounting brackets for under-hood or under-dash
- Removable cover for maintenance
```

### Mounting Locations

| Component | Location | Notes |
|-----------|----------|-------|
| Main unit (Pi) | Under dash or firewall | Protected from heat |
| Brake temp sensors | Near brake calipers | Use heat-resistant wire |
| Engine vibration | Engine block | Rigid mount required |
| Trans vibration | Transmission housing | Accessible location |
| GPS antenna | Roof or dash | Clear sky view |
| Current sensor | Near fuel pump relay | In-line with positive wire |

---

## TOTAL COST ESTIMATE

| Category | Items | Cost (USD) |
|----------|-------|------------|
| Controller | Pi 5 + SD + Cooler + Case | $102 |
| Brake Temp | 4x TC + 4x MAX31855 | $92 |
| Vibration | 2x MPU6050 + ADXL345 | $18 |
| Current | ACS712 30A | $6 |
| Ambient Temp | 2x DS18B20 | $10 |
| GPS | NEO-6M | $12 |
| Power | Buck converter + fuse | $13 |
| ADC | MCP3008 | $8 |
| CAN Bus | MCP2515 (optional) | $8 |
| Wiring | Cables, connectors, heat shrink | $30 |
| Enclosure | IP65 box + cable glands | $35 |
| **TOTAL** | | **$334** |

**Optional additions:**
- 4G LTE HAT: +$45
- UPS HAT: +$40
- Professional enclosure: +$50

---

## RECOMMENDED IMPROVEMENTS TO YOUR PROPOSAL

### What You Proposed vs Recommended

| Your Proposal | My Recommendation | Reason |
|--------------|-------------------|--------|
| 2 brake temp sensors | 4 brake temp sensors | Front/rear wear differently; complete picture |
| 2 engine + 1 trans vibration | ✓ Same | Good balance of coverage and cost |
| 1 fuel pump current sensor | ✓ Same | Sufficient for monitoring |
| Raspberry Pi 5 4GB | ✓ Same | Good choice for processing |

### Additional Sensors to Consider

1. **Exhaust Gas Temperature (EGT)**
   - Detect catalytic converter issues
   - Monitor turbo health (if applicable)
   - K-type thermocouple ($15)

2. **Intake Manifold Pressure (if not available via OBD)**
   - MPX5700 pressure sensor ($20)
   - Detect vacuum leaks

3. **Oil Pressure (external)**
   - Verify OBD reading
   - Earlier warning of oil pump issues
   - Requires tapping into oil system

4. **Transmission Temperature (external)**
   - Many cars don't report via OBD
   - Critical for transmission health
   - DS18B20 on transmission pan

5. **Wheel Speed (for ABS-equipped)**
   - Detect wheel bearing issues
   - Usually available via OBD CAN

---

## NEXT STEPS

1. **Order Components** - Start with essential sensors
2. **Prototype on Breadboard** - Test sensor readings
3. **Develop Software** - Implement data collection daemon
4. **Integrate with Phone App** - Add sensor data to telemetry
5. **Test in Vehicle** - Validate readings and reliability
6. **Design PCB** - Custom board for production
7. **Finalize Enclosure** - Weatherproof housing

---

*Document generated: 2026-01-07*
*Version: 1.0*
