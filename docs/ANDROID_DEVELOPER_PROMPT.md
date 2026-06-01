# Android OBD App Developer Prompt

## Project Overview

Build an Android application that connects to vehicles via Bluetooth OBD-II adapters, collects real-time diagnostics, sends data to a cloud server, and displays AI-powered failure predictions. The app integrates with a Windows desktop application (Previlium Predict) that serves as the central data hub and AI engine.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    ANDROID APP                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Bluetooth OBD   │  │ Data Collection │  │   UI/Display    │  │ HTTP Client     │ │
│  │ Connection      │  │ & Caching       │  │   Dashboard     │  │ (Retrofit)      │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
└───────────┼─────────────────────┼──────────────────────────────────────────┼─────────┘
            │                     │                                          │
            │                     ▼                                          │
            │            Local SQLite Cache                                  │
            │            (offline support)                                   │
            │                                                                │
            └────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────────┐
                            │     ONLINE SERVER (FastAPI)       │
                            │  https://predict.previlium.com    │
                            │                                   │
                            │  Endpoints:                       │
                            │  - /api/v1/telemetry (OBD data)  │
                            │  - /api/v1/lstm/predict          │
                            │  - /api/v1/feedback              │
                            │  - /api/v1/service-records       │
                            │  - /api/profile/list             │
                            │  - /api/report/generate          │
                            └───────────────┬──────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────────┐
                            │   DESKTOP APP (Windows)           │
                            │   c:/D Drive/Predict              │
                            │                                   │
                            │  - EnhancedPredictionEngine      │
                            │  - LSTM Deep Learning Model      │
                            │  - Vehicle Profile Database      │
                            │  - API Key Management            │
                            │  - PDF Report Generation         │
                            └──────────────────────────────────┘
```

---

## Server Connection Details

**Production Server:**
- Base URL: `https://predict.previlium.com`
- Protocol: HTTPS (via Cloudflare Tunnel)
- Authentication: API Key in `X-API-Key` header

**All requests must include:**
```http
X-API-Key: {api_key_from_profile}
Content-Type: application/json
```

---

## Profile Management

### CRITICAL: Profile Creation Flow

**Profiles are created on the Desktop App, NOT the Android app.**

The workflow is:
1. User creates a vehicle profile on the Desktop app (Previlium Predict)
2. Desktop app generates an API key for that profile
3. User enters the API key in the Android app
4. Android app can then send data and receive predictions for that profile

### Getting Profile Information

**Endpoint:** `GET /api/profile/list`

**Response:**
```json
{
  "status": "ok",
  "profiles": [
    {
      "profile_id": 1,
      "name": "My Car",
      "make": "Toyota",
      "model": "Camry",
      "year": 2020,
      "vin": "1HGBH41JXMN109186",
      "license_plate": "ABC123",
      "category": "personal",
      "fuel_type": "gasoline"
    }
  ],
  "count": 1
}
```

### Updating Profile (Optional)

**Endpoint:** `POST /api/profile/update`

Android can update basic profile fields (make, model, year, VIN), but profile creation must be done on Desktop.

```json
{
  "make": "Toyota",
  "model": "Camry",
  "year": 2021,
  "vin": "1HGBH41JXMN109186"
}
```

---

## Core Data Flow

### 1. Sending OBD Data

**Endpoint:** `POST /api/v1/telemetry`

Send OBD readings to server. This is the primary data ingestion endpoint.

**Request:**
```json
{
  "profile_id": 1,
  "readings": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "rpm": 850,
      "speed": 0,
      "coolant_temp": 85.5,
      "voltage": 14.2,
      "engine_load": 22.5,
      "intake_temp": 28.0,
      "maf": 5.2,
      "throttle_pos": 15.0,
      "fuel_pressure": 35.0,
      "timing_advance": 12.5,
      "short_fuel_trim": 1.2,
      "long_fuel_trim": -0.8
    }
  ]
}
```

**Required OBD PIDs for prediction:**
| PID | Parameter | Unit | Description |
|-----|-----------|------|-------------|
| 0x05 | coolant_temp | Celsius | Engine coolant temperature |
| 0x0C | rpm | RPM | Engine speed |
| 0x0D | speed | km/h | Vehicle speed |
| 0x04 | engine_load | % | Calculated engine load |
| 0x42 | voltage | V | Control module voltage |
| 0x0F | intake_temp | Celsius | Intake air temperature |
| 0x10 | maf | g/s | Mass air flow rate |
| 0x11 | throttle_pos | % | Throttle position |
| 0x0A | fuel_pressure | kPa | Fuel pressure |
| 0x0E | timing_advance | degrees | Timing advance |
| 0x06 | short_fuel_trim | % | Short term fuel trim Bank 1 |
| 0x07 | long_fuel_trim | % | Long term fuel trim Bank 1 |

**Response:**
```json
{
  "status": "ok",
  "records_saved": 1,
  "prediction_available": true
}
```

---

### 2. Getting LSTM Predictions

**Endpoint:** `POST /api/v1/lstm/predict`

Get AI-powered failure predictions. Requires minimum 10 sequential OBD readings.

**Request:**
```json
{
  "profile_id": 1,
  "sequence_data": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "coolant_temp": 85.5,
      "voltage": 14.2,
      "rpm": 850,
      "engine_load": 22.5,
      "short_fuel_trim": 1.2,
      "long_fuel_trim": -0.8
    }
    // ... minimum 10 readings required
  ]
}
```

**Response:**
```json
{
  "success": true,
  "profile_id": 1,
  "prediction": {
    "failure_probability": 0.75,
    "failure_type": "battery",
    "days_to_failure": 12,
    "confidence": 0.82,
    "prediction_id": "pred_abc123xyz",
    "components_at_risk": [
      {"component": "battery", "risk": 0.75, "days": 12},
      {"component": "alternator", "risk": 0.35, "days": 45}
    ]
  },
  "model_version": "1.0.0",
  "timestamp": "2024-01-15T14:35:00Z"
}
```

**Failure Types:**
- `battery` - Battery failure (voltage degradation)
- `alternator` - Alternator failure (charging issues)
- `thermostat` - Thermostat failure (cooling issues)
- `fuel_pump` - Fuel system failure
- `no_failure` - No imminent failure predicted

---

### 3. Submitting Prediction Feedback

**Endpoint:** `POST /api/v1/feedback`

Critical for model improvement. Submit when a prediction proves correct or incorrect.

**Request:**
```json
{
  "profile_id": 1,
  "prediction_id": "pred_abc123xyz",
  "was_correct": true,
  "actual_outcome": "battery_replaced",
  "actual_failure_date": "2024-01-27",
  "notes": "Battery died after 12 days as predicted"
}
```

**Response:**
```json
{
  "success": true,
  "feedback_recorded": true,
  "prediction_id": "pred_abc123xyz",
  "timestamp": "2024-01-27T10:00:00Z"
}
```

---

### 4. Getting Pending Predictions

**Endpoint:** `GET /api/v1/predictions/pending/{profile_id}`

Get predictions awaiting feedback (to prompt user for confirmation).

**Response:**
```json
{
  "success": true,
  "profile_id": 1,
  "pending_predictions": [
    {
      "prediction_id": "pred_abc123xyz",
      "failure_type": "battery",
      "predicted_date": "2024-01-27",
      "days_remaining": 5,
      "failure_probability": 0.75
    }
  ],
  "count": 1
}
```

---

### 5. Service Records

**Add Record - Endpoint:** `POST /api/v1/service-records`

```json
{
  "profile_id": 1,
  "service_date": "2024-01-27",
  "service_type": "repair",
  "component": "battery",
  "mileage": 85000,
  "cost": 150.00,
  "shop_name": "AutoZone",
  "description": "Replaced battery - original battery failed",
  "failure_type": "battery_failure",
  "related_prediction_id": "pred_abc123xyz",
  "parts_replaced": ["battery", "battery_terminals"],
  "dtc_codes": ["P0562"]
}
```

**Service Types:**
- `oil_change` - Oil and filter change
- `repair` - Component repair/replacement
- `maintenance` - Scheduled maintenance
- `inspection` - Vehicle inspection

**Get Records - Endpoint:** `GET /api/v1/service-records/{profile_id}?limit=50`

---

### 6. ESP32 External Sensors (Optional)

**Submit Sensor Data - Endpoint:** `POST /api/v1/sensors/data`

For vehicles with ESP32 external sensor modules.

```json
{
  "profile_id": 1,
  "sensor_type": "oil_temp",
  "value": 95.5,
  "unit": "celsius",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Sensor Types:**
- `oil_temp` - Oil temperature (Celsius)
- `oil_quality` - Oil quality percentage (0-100)
- `vibration` - Vibration level (g-force)
- `external_temp` - External temperature (Celsius)

**Get Sensor Status - Endpoint:** `GET /api/v1/sensors/status/{profile_id}`

---

### 7. PDF Report Generation

**Request Report - Endpoint:** `POST /api/report/generate`

```json
{
  "profile_id": 1,
  "report_type": "full"
}
```

**Check Status - Endpoint:** `GET /api/report/status?request_id={id}`

**Download Report - Endpoint:** `GET /api/report/download?request_id={id}`

---

### 8. System Status

**LSTM Status - Endpoint:** `GET /api/v1/lstm/status`

```json
{
  "available": true,
  "status": {
    "model_loaded": true,
    "model_version": "1.0.0",
    "is_trained": true,
    "accuracy": 0.85
  }
}
```

**Enhanced System Status - Endpoint:** `GET /api/v1/enhanced/status`

```json
{
  "available": true,
  "status": {
    "lstm": {"loaded": true, "version": "1.0.0"},
    "feedback": {"pending_count": 5, "total_collected": 150},
    "esp32": {"connected": true, "sensors": 3},
    "service_records": {"total": 25}
  },
  "timestamp": "2024-01-15T14:35:00Z"
}
```

---

## KNOWN ISSUES - MUST FIX

### 1. Oil Change History - NOT WORKING
The oil change history feature is currently not functional. The UI exists but data is not being saved or displayed correctly. This needs to be investigated and fixed.

**Affected Areas:**
- Service records with `service_type: "oil_change"` may not be saving properly
- Oil change reminder calculations are not working
- Historical oil change display is broken

### 2. Scan DTC (Diagnostic Trouble Codes) - NOT WORKING
The DTC scanning feature is not operational. The OBD connection may work but DTC retrieval and display are broken.

**Affected Areas:**
- DTC read command (Mode 03) not implemented correctly
- DTC clear command (Mode 04) not implemented
- DTC code lookup/description database missing or not integrated
- DTC history not being saved

**Required DTC Implementation:**
```kotlin
// Mode 03: Request stored DTCs
fun readDTCs(): List<DTCCode> {
    val response = sendOBDCommand("03")
    // Parse DTC response (format: 43 XX XX YY YY...)
    // Each DTC is 2 bytes
}

// Mode 04: Clear DTCs
fun clearDTCs(): Boolean {
    val response = sendOBDCommand("04")
    return response == "44"
}

// Mode 07: Pending DTCs
fun readPendingDTCs(): List<DTCCode>
```

---

## Android App UI Requirements

### Main Screens

1. **Setup/Login Screen**
   - API Key input field
   - "Get API Key from Desktop App" instructions
   - Validate key with `/api/profile/list`
   - Store API key securely (EncryptedSharedPreferences)

2. **Dashboard Screen**
   - Current vehicle status (connected/disconnected)
   - Latest OBD readings (live when connected)
   - Prediction summary card (if available)
   - Quick actions: Scan, Service History, Reports

3. **Predictions Screen**
   - Current predictions with risk levels
   - Days to predicted failure
   - Component risk breakdown
   - "Confirm/Deny Prediction" buttons for feedback

4. **Service History Screen**
   - List of past services
   - Add new service record
   - Link service to prediction (if applicable)
   - **FIX NEEDED:** Oil change history display

5. **DTC Scanner Screen**
   - Scan for codes button
   - List of active DTCs with descriptions
   - Clear codes button
   - **FIX NEEDED:** Entire feature non-functional

6. **Settings Screen**
   - OBD adapter selection
   - Data sync preferences
   - Notification settings
   - API key management

---

## Data Synchronization

### Offline Support

The app must work offline with local caching:

```kotlin
// Room Database Schema
@Entity(tableName = "obd_readings")
data class OBDReading(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val profileId: Int,
    val timestamp: Long,
    val rpm: Float?,
    val speed: Float?,
    val coolantTemp: Float?,
    val voltage: Float?,
    // ... other fields
    val synced: Boolean = false
)

@Entity(tableName = "pending_uploads")
data class PendingUpload(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val endpoint: String,
    val payload: String,
    val createdAt: Long,
    val attempts: Int = 0
)
```

### Sync Strategy

1. Collect OBD data locally with `synced = false`
2. When online, batch upload unsynced records
3. Mark as synced on successful upload
4. Queue failed uploads for retry
5. Use WorkManager for background sync

---

## Bluetooth OBD Connection

### Supported Adapters
- ELM327 compatible adapters
- OBDLink MX+
- Vgate iCar Pro

### Connection Flow

```kotlin
class OBDConnection {
    fun connect(deviceAddress: String): Boolean
    fun sendCommand(command: String): String
    fun disconnect()

    // Standard initialization sequence
    fun initialize() {
        sendCommand("ATZ")      // Reset
        sendCommand("ATE0")     // Echo off
        sendCommand("ATL0")     // Linefeeds off
        sendCommand("ATS0")     // Spaces off
        sendCommand("ATH0")     // Headers off
        sendCommand("ATSP0")    // Auto protocol
    }
}
```

---

## Error Handling

### HTTP Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 401 | Invalid/missing API key | Prompt for new API key |
| 402 | Subscription expired | Show upgrade message |
| 403 | Feature not available | Check subscription tier |
| 404 | Resource not found | Handle gracefully |
| 429 | Rate limited | Implement exponential backoff |
| 500 | Server error | Retry with backoff |
| 503 | Service unavailable | Queue for later |

### Retry Strategy

```kotlin
class RetryPolicy {
    val maxRetries = 3
    val baseDelayMs = 1000L

    fun getDelay(attempt: Int): Long {
        return baseDelayMs * (2.0.pow(attempt)).toLong()
    }
}
```

---

## Security Requirements

1. **API Key Storage:** Use EncryptedSharedPreferences
2. **Network:** HTTPS only, certificate pinning recommended
3. **Data at Rest:** Encrypt sensitive local data
4. **Permissions:** Request only necessary permissions
   - BLUETOOTH, BLUETOOTH_ADMIN
   - BLUETOOTH_CONNECT, BLUETOOTH_SCAN (Android 12+)
   - ACCESS_FINE_LOCATION (for BLE scanning)
   - INTERNET

---

## Testing Checklist

- [ ] API key validation works
- [ ] Profile fetch displays correctly
- [ ] OBD connection establishes
- [ ] Live data streams to server
- [ ] Predictions display correctly
- [ ] Feedback submission works
- [ ] Service records save and display
- [ ] Offline mode caches data
- [ ] Background sync works
- [ ] Notifications trigger correctly
- [ ] **Oil change history displays (CURRENTLY BROKEN)**
- [ ] **DTC scanning works (CURRENTLY BROKEN)**

---

## Integration Points with Desktop App

### Profile Linking
- Desktop creates profile with unique `profile_id`
- Desktop generates API key linked to `profile_id`
- Android uses API key to identify which profile
- All data sent from Android tagged with `profile_id`
- Desktop receives and processes all data for that profile

### Data Flow
```
Android App                  Server                    Desktop App
    │                          │                           │
    │──OBD Reading────────────▶│                           │
    │                          │──Store + Forward─────────▶│
    │                          │                           │──Process
    │                          │◀──Prediction Result───────│
    │◀─Prediction──────────────│                           │
    │                          │                           │
    │──Feedback───────────────▶│                           │
    │                          │──Update Model────────────▶│
```

### Shared Data Locations
- **Vehicle Profiles:** `c:/D Drive/Predict/data/vehicle_profiles.db`
- **API Keys:** `c:/D Drive/Predict/config/api_keys.json`
- **OBD History:** `c:/D Drive/Predict/data/obd_history/`
- **Predictions:** `c:/D Drive/Predict/data/predictions/`
- **Service Records:** Managed by EnhancedPredictionEngine

---

## Version Compatibility

- **Minimum Android SDK:** 24 (Android 7.0)
- **Target SDK:** 34 (Android 14)
- **Server API Version:** v1
- **Desktop App Version:** Compatible with Previlium Predict 2.x

---

## Contact for Integration Support

For API documentation updates or integration issues, check:
- Server logs: `C:\OBDserver\logs\`
- Desktop logs: `c:\D Drive\Predict\logs\`
- API health: `GET /status` endpoint
