# PREDICT Mobile App - Complete Integration Guide
**For Android & iOS Developers**

Version: 1.0
Last Updated: December 2025
Desktop App Version: PREDICT Professional v2.0

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [API Endpoints](#api-endpoints)
5. [Data Format Specifications](#data-format-specifications)
6. [Connection Flow](#connection-flow)
7. [PDF Report Requests](#pdf-report-requests)
8. [Online Status Tracking](#online-status-tracking)
9. [Error Handling](#error-handling)
10. [Testing](#testing)
11. [Code Examples](#code-examples)

---

## 1. Overview

The PREDICT mobile app connects to the desktop application via HTTP API to:
- Send real-time OBD-II data from the vehicle
- Display AI predictions and health scores
- Request and receive PDF reports
- Show live connection status on desktop

### Key Features
- **Profile-Based Authentication**: Each API key is linked to a specific car profile
- **Real-Time Data Streaming**: Send OBD data every 2 seconds via HTTP POST
- **Bidirectional Communication**: Desktop can send commands, mobile can request PDFs
- **Offline Mode**: Cache data when desktop is unreachable, sync later
- **Push Notifications**: Receive AI-detected issue alerts

---

## 2. Architecture

```
┌─────────────────────────────────────────┐
│     PREDICT MOBILE APP                   │
│  (Android/iOS - Your Development)        │
│                                          │
│  ┌────────────┐      ┌──────────────┐   │
│  │ OBD Reader │─────▶│ Data Manager │   │
│  └────────────┘      └──────┬───────┘   │
│                             │            │
│  ┌────────────┐             │            │
│  │  UI Layer  │◀────────────┘            │
│  └────────────┘                          │
│         │                                │
│         │ HTTP API (Port 8000)           │
│         ▼                                │
└─────────┼────────────────────────────────┘
          │
          │ Network (WiFi/Mobile Data)
          │
┌─────────▼────────────────────────────────┐
│   PREDICT DESKTOP APPLICATION            │
│   (Windows - Running on User's PC)       │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Previlium OBD Server            │   │
│  │  (FastAPI - Port 8000)           │   │
│  └─────────────┬────────────────────┘   │
│                │                         │
│  ┌─────────────▼────────────────────┐   │
│  │  Mobile Data Bridge              │   │
│  │  - Converts mobile JSON          │   │
│  │  - Validates & processes data    │   │
│  └─────────────┬────────────────────┘   │
│                │                         │
│  ┌─────────────▼────────────────────┐   │
│  │  AI Processing Engine            │   │
│  │  - Health scoring                │   │
│  │  - Predictive failure analysis   │   │
│  │  - Recommendations               │   │
│  └─────────────┬────────────────────┘   │
│                │                         │
│  ┌─────────────▼────────────────────┐   │
│  │  Historical Data Manager         │   │
│  │  - Permanent storage             │   │
│  │  - AI training data              │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  PDF Generation (Port 8001)      │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

---

## 3. Authentication

### 3.1 API Key Generation (Desktop Side)

Users generate API keys in the PREDICT desktop app's **Server Tab**:

1. User selects a car profile (e.g., "Omar - Nissan Patrol")
2. Clicks "Generate API Key"
3. Desktop generates a secure 32-byte token
4. Desktop stores SHA256 hash (NOT the plain key)
5. User copies the API key **ONCE** (it's never shown again)

### 3.2 API Key Structure

```json
{
  "key_20231210120000": {
    "key_hash": "a3d5f8b2c1e9...",
    "name": "Android Phone #1",
    "profile_id": 9,
    "profile_name": "Omar",
    "created": "2023-12-10T12:00:00",
    "permissions": ["vehicle_data", "predict", "diagnostic"]
  }
}
```

### 3.3 Mobile App - API Key Input

**First-Time Setup Flow:**

```
1. App Launch
   ↓
2. Check if API key exists locally
   ↓
3. If NO → Show API Key Input Screen
   │   - Input field for API key
   │   - "Scan QR Code" button (optional)
   │   - "Connect" button
   ↓
4. When user enters key:
   - Store in secure storage (Android: EncryptedSharedPreferences, iOS: Keychain)
   - Attempt connection to desktop
   ↓
5. If connection successful:
   - Retrieve profile info
   - Show main dashboard
   ↓
6. If connection failed:
   - Show error message
   - Allow retry or re-enter key
```

**Storage Implementation:**

```kotlin
// Android - Secure Storage
val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val sharedPreferences = EncryptedSharedPreferences.create(
    context,
    "predict_secure_prefs",
    masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
)

sharedPreferences.edit().putString("api_key", apiKey).apply()
```

```swift
// iOS - Keychain Storage
import Security

func saveAPIKey(_ apiKey: String) {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: "predict_api_key",
        kSecValueData as String: apiKey.data(using: .utf8)!,
        kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlocked
    ]
    SecItemAdd(query as CFDictionary, nil)
}
```

---

## 4. API Endpoints

### Base URL
```
http://<desktop_ip>:8000
```

**How to find desktop IP:**
- Desktop app displays local IP in Server Tab (e.g., `192.168.1.100`)
- User enters this in mobile app settings

---

### 4.1 POST `/mobile/data`
**Send OBD-II Data to Desktop**

**Headers:**
```
Content-Type: application/json
X-API-Key: <your_api_key>
```

**Request Body:**
```json
{
  "timestamp": "2025-12-15T14:30:22Z",
  "vehicle_id": "Omar_Nissan_Patrol",
  "source": "android_predictobd",
  "obd": {
    "rpm": 2500,
    "speed_kmh": 80,
    "coolant_temp_c": 90,
    "intake_air_temp_c": 35,
    "ambient_air_temp_c": 28,
    "throttle_position_pct": 45,
    "engine_load_pct": 60,
    "fuel_pressure_kpa": 350,
    "intake_manifold_pressure_kpa": 100,
    "timing_advance_deg": 15,
    "maf_gps": 12.5,
    "voltage_batt_v": 14.2,
    "oil_temp_c": 95,
    "fuel_level_pct": 75,
    "short_term_fuel_trim_b1": 2.5,
    "long_term_fuel_trim_b1": -1.2,
    "dtc_list": []
  },
  "gps": {
    "latitude": 25.276987,
    "longitude": 55.296249,
    "altitude": 5.0,
    "speed_kmh": 80,
    "accuracy_m": 10
  },
  "vibration": {
    "x": 0.05,
    "y": 0.03,
    "z": 0.98,
    "rms": 0.15
  },
  "missing_data_summary": []
}
```

**Response (Success - 200 OK):**
```json
{
  "status": "success",
  "message": "Data received and processed",
  "profile_name": "Omar",
  "health_score": 92,
  "warnings": []
}
```

**Response (Error - 401 Unauthorized):**
```json
{
  "status": "error",
  "error": "Invalid API key"
}
```

**Response (Error - 429 Too Many Requests):**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Max 100 requests per minute."
}
```

---

### 4.2 POST `/mobile/pdf_request`
**Request PDF Report Generation**

**Headers:**
```
Content-Type: application/json
X-API-Key: <your_api_key>
```

**Request Body:**
```json
{
  "report_type": "week",  // "week" or "lifetime"
  "delivery_method": "push",  // "push" or "email"
  "email": "user@example.com"  // Required if delivery_method is "email"
}
```

**Response (Success - 202 Accepted):**
```json
{
  "status": "accepted",
  "message": "PDF generation started",
  "request_id": "pdf_req_20231210_143022",
  "estimated_time_seconds": 30
}
```

---

### 4.3 GET `/mobile/pdf_status/<request_id>`
**Check PDF Generation Status**

**Headers:**
```
X-API-Key: <your_api_key>
```

**Response (In Progress - 202 Accepted):**
```json
{
  "status": "processing",
  "progress_percent": 45,
  "message": "Generating charts..."
}
```

**Response (Completed - 200 OK):**
```json
{
  "status": "completed",
  "download_url": "http://192.168.1.100:8001/reports/predict_report_20231210.pdf",
  "file_size_mb": 2.5,
  "expires_at": "2023-12-10T15:30:22Z"
}
```

---

### 4.4 GET `/mobile/pdf_download/<filename>`
**Download Generated PDF** (Port 8001)

```
http://<desktop_ip>:8001/reports/<filename>
```

**Headers:**
```
X-API-Key: <your_api_key>
```

**Response:**
- Binary PDF file
- Content-Type: application/pdf
- Content-Disposition: attachment; filename="predict_report.pdf"

---

### 4.5 GET `/mobile/health`
**Health Check / Ping**

**Headers:**
```
X-API-Key: <your_api_key>
```

**Response (200 OK):**
```json
{
  "status": "online",
  "server_time": "2023-12-10T14:30:22Z",
  "profile_name": "Omar",
  "desktop_version": "2.0.1"
}
```

---

### 4.6 GET `/mobile/commands`
**Receive Commands from Desktop** (Future Feature)

**Headers:**
```
X-API-Key: <your_api_key>
```

**Response (200 OK):**
```json
{
  "commands": [
    {
      "command_id": "cmd_001",
      "type": "clear_dtc",
      "parameters": {},
      "issued_at": "2023-12-10T14:28:00Z"
    },
    {
      "command_id": "cmd_002",
      "type": "read_pid",
      "parameters": {
        "pid": "0x0C"
      },
      "issued_at": "2023-12-10T14:29:00Z"
    }
  ]
}
```

---

## 5. Data Format Specifications

### 5.1 OBD Parameters

| Parameter | JSON Key | Unit | Type | Range | Required |
|-----------|----------|------|------|-------|----------|
| Engine RPM | `rpm` | rpm | integer | 0-8000 | ✅ Yes |
| Vehicle Speed | `speed_kmh` | km/h | integer | 0-300 | ✅ Yes |
| Coolant Temperature | `coolant_temp_c` | °C | float | -40 to 215 | ✅ Yes |
| Intake Air Temp | `intake_air_temp_c` | °C | float | -40 to 215 | ⚪ No |
| Ambient Air Temp | `ambient_air_temp_c` | °C | float | -40 to 60 | ⚪ No |
| Throttle Position | `throttle_position_pct` | % | float | 0-100 | ✅ Yes |
| Engine Load | `engine_load_pct` | % | float | 0-100 | ✅ Yes |
| Fuel Pressure | `fuel_pressure_kpa` | kPa | float | 0-765 | ⚪ No |
| Intake Manifold Pressure | `intake_manifold_pressure_kpa` | kPa | float | 0-255 | ⚪ No |
| Timing Advance | `timing_advance_deg` | degrees | float | -64 to 63.5 | ⚪ No |
| MAF (Mass Air Flow) | `maf_gps` | g/s | float | 0-655 | ⚪ No |
| Battery Voltage | `voltage_batt_v` | V | float | 0-16 | ✅ Yes |
| Oil Temperature | `oil_temp_c` | °C | float | -40 to 210 | ⚪ No |
| Fuel Level | `fuel_level_pct` | % | float | 0-100 | ⚪ No |
| Short Term Fuel Trim | `short_term_fuel_trim_b1` | % | float | -100 to 99.2 | ⚪ No |
| Long Term Fuel Trim | `long_term_fuel_trim_b1` | % | float | -100 to 99.2 | ⚪ No |
| DTC Codes | `dtc_list` | - | array | - | ✅ Yes (can be empty) |

### 5.2 GPS Data (Optional but Recommended)

```json
"gps": {
  "latitude": 25.276987,    // Decimal degrees
  "longitude": 55.296249,   // Decimal degrees
  "altitude": 5.0,          // Meters above sea level
  "speed_kmh": 80,          // Speed from GPS (for validation)
  "accuracy_m": 10          // Accuracy in meters
}
```

### 5.3 Accelerometer Data (Optional)

```json
"vibration": {
  "x": 0.05,    // G-force on X axis
  "y": 0.03,    // G-force on Y axis
  "z": 0.98,    // G-force on Z axis (gravity)
  "rms": 0.15   // Root Mean Square vibration
}
```

---

## 6. Connection Flow

### 6.1 Initial Connection

```
Mobile App Startup
   │
   ├─ Load API key from secure storage
   │
   ├─ Attempt connection to desktop IP
   │  (Send GET /mobile/health)
   │
   ├─ If SUCCESS (200 OK):
   │  │
   │  ├─ Retrieve profile info
   │  ├─ Display profile name in UI
   │  ├─ Show "Connected" status (green indicator)
   │  ├─ Start OBD data streaming
   │  └─ Update desktop last_seen timestamp
   │
   └─ If FAIL (timeout, 401, network error):
      │
      ├─ Show "Disconnected" status (red indicator)
      ├─ Enable offline mode
      ├─ Cache OBD data locally
      └─ Retry connection every 30 seconds
```

### 6.2 Data Streaming Loop

```kotlin
// Android Example
class OBDDataStreamer(private val apiKey: String, private val desktopIP: String) {
    private val coroutineScope = CoroutineScope(Dispatchers.IO)
    private var isStreaming = false

    fun startStreaming() {
        isStreaming = true
        coroutineScope.launch {
            while (isStreaming) {
                try {
                    // Read OBD data
                    val obdData = readOBDData()

                    // Send to desktop
                    sendData(obdData)

                    // Wait 2 seconds
                    delay(2000)

                } catch (e: Exception) {
                    Log.e("OBD", "Streaming error", e)
                    handleConnectionError(e)
                }
            }
        }
    }

    private suspend fun sendData(data: OBDData) {
        val client = OkHttpClient()
        val json = gson.toJson(data)

        val request = Request.Builder()
            .url("http://$desktopIP:8000/mobile/data")
            .addHeader("Content-Type", "application/json")
            .addHeader("X-API-Key", apiKey)
            .post(json.toRequestBody("application/json".toMediaType()))
            .build()

        val response = client.newCall(request).execute()

        if (response.isSuccessful) {
            // Update UI with success status
            val responseData = gson.fromJson(response.body?.string(), ServerResponse::class.java)
            updateHealthScore(responseData.health_score)
        } else {
            // Handle error
            handleErrorResponse(response.code)
        }
    }
}
```

### 6.3 Offline Mode & Caching

```kotlin
// Cache data when offline
class OfflineDataCache(private val context: Context) {
    private val cacheFile = File(context.filesDir, "offline_cache.json")

    fun cacheData(data: OBDData) {
        val cachedData = loadCache().toMutableList()
        cachedData.add(data)

        // Keep only last 1000 entries
        if (cachedData.size > 1000) {
            cachedData.removeAt(0)
        }

        cacheFile.writeText(gson.toJson(cachedData))
    }

    fun syncCachedData(apiKey: String, desktopIP: String) {
        val cachedData = loadCache()

        cachedData.forEach { data ->
            try {
                sendData(data, apiKey, desktopIP)
            } catch (e: Exception) {
                // Stop syncing if connection fails
                return
            }
        }

        // Clear cache after successful sync
        clearCache()
    }

    private fun loadCache(): List<OBDData> {
        if (!cacheFile.exists()) return emptyList()
        return gson.fromJson(cacheFile.readText(), Array<OBDData>::class.java).toList()
    }

    private fun clearCache() {
        cacheFile.delete()
    }
}
```

---

## 7. PDF Report Requests

### 7.1 Request Flow

```
User clicks "Generate Report" in mobile app
   │
   ├─ Show selection dialog:
   │  • Week Data (last 7 days)
   │  • Lifetime Data (all historical data)
   │
   ├─ User selects option
   │
   ├─ Show delivery method:
   │  • Push to phone
   │  • Email to address
   │
   ├─ Send POST /mobile/pdf_request
   │
   ├─ Receive request_id
   │
   ├─ Start polling GET /mobile/pdf_status/<request_id>
   │  (every 2 seconds)
   │
   ├─ Show progress bar with status
   │
   ├─ When status = "completed":
   │  │
   │  ├─ If delivery = "push":
   │  │  │
   │  │  ├─ Download PDF from download_url
   │  │  ├─ Save to Downloads folder
   │  │  ├─ Show notification "Report Ready"
   │  │  └─ Open PDF viewer
   │  │
   │  └─ If delivery = "email":
   │     └─ Show success message "Report sent to email"
   │
   └─ Handle errors gracefully
```

### 7.2 PDF Download Implementation

```kotlin
// Android - Download PDF
suspend fun downloadPDF(downloadUrl: String, apiKey: String): File {
    val client = OkHttpClient()
    val request = Request.Builder()
        .url(downloadUrl)
        .addHeader("X-API-Key", apiKey)
        .build()

    val response = client.newCall(request).execute()

    if (!response.isSuccessful) {
        throw IOException("Failed to download PDF: ${response.code}")
    }

    // Save to Downloads folder
    val downloadsDir = Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_DOWNLOADS
    )
    val fileName = "predict_report_${System.currentTimeMillis()}.pdf"
    val pdfFile = File(downloadsDir, fileName)

    response.body?.byteStream()?.use { input ->
        pdfFile.outputStream().use { output ->
            input.copyTo(output)
        }
    }

    // Notify media scanner
    MediaScannerConnection.scanFile(
        context,
        arrayOf(pdfFile.absolutePath),
        null,
        null
    )

    return pdfFile
}
```

---

## 8. Online Status Tracking

### 8.1 Desktop Side

The desktop tracks online status based on `last_seen` timestamp:

- **🟢 Green (Online)**: Last data received < 30 seconds ago
- **🔴 Red (Offline)**: Last data received >= 30 seconds ago (but was connected before)
- **⚪ Grey (Never Connected)**: Profile has never received data

### 8.2 Mobile Side

Show connection status in the app UI:

```kotlin
class ConnectionStatusManager {
    private val statusFlow = MutableStateFlow(ConnectionStatus.DISCONNECTED)

    enum class ConnectionStatus {
        CONNECTED,      // Successfully sending data
        CONNECTING,     // Attempting connection
        DISCONNECTED,   // No connection
        ERROR          // Connection error
    }

    fun updateStatus(newStatus: ConnectionStatus) {
        statusFlow.value = newStatus

        when (newStatus) {
            CONNECTED -> showGreenIndicator()
            CONNECTING -> showYellowIndicator()
            DISCONNECTED, ERROR -> showRedIndicator()
        }
    }
}
```

---

## 9. Error Handling

### 9.1 HTTP Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Continue normally |
| 202 | Accepted | Request queued (PDF generation) |
| 400 | Bad Request | Check request format |
| 401 | Unauthorized | Invalid API key - prompt user to re-enter |
| 403 | Forbidden | API key valid but lacks permissions |
| 429 | Too Many Requests | Slow down data sending rate |
| 500 | Server Error | Retry after delay |
| 503 | Service Unavailable | Desktop app may be restarting |

### 9.2 Network Errors

```kotlin
fun handleNetworkError(error: Exception) {
    when (error) {
        is UnknownHostException -> {
            // Desktop IP unreachable
            showError("Cannot reach desktop. Check IP address and network connection.")
            enableOfflineMode()
        }
        is SocketTimeoutException -> {
            // Request timeout
            showError("Connection timeout. Desktop may be busy.")
            retryWithBackoff()
        }
        is SSLException -> {
            // SSL/TLS error (shouldn't happen with HTTP)
            showError("Secure connection error.")
        }
        else -> {
            showError("Network error: ${error.message}")
        }
    }
}
```

---

## 10. Testing

### 10.1 Desktop Setup for Testing

1. Launch PREDICT desktop application
2. Go to Server Tab
3. Generate API key for test profile
4. Note the local IP address displayed (e.g., `192.168.1.100`)
5. Ensure Windows Firewall allows port 8000 and 8001

### 10.2 Mobile App Testing Checklist

- [ ] Initial connection with valid API key
- [ ] Connection rejection with invalid API key
- [ ] Sending OBD data successfully
- [ ] Receiving health score updates
- [ ] Green status indicator appears on desktop profile list
- [ ] Red status appears after 30 seconds of no data
- [ ] Offline mode: cache data when disconnected
- [ ] Offline mode: sync cached data when reconnected
- [ ] PDF request (week data)
- [ ] PDF request (lifetime data)
- [ ] PDF download and open
- [ ] Handle network errors gracefully
- [ ] Handle rate limiting (429 errors)
- [ ] App continues to function if desktop disconnects mid-session

### 10.3 Test Data Generator

```kotlin
// Generate test OBD data for development
fun generateTestOBDData(): OBDData {
    return OBDData(
        timestamp = Instant.now().toString(),
        vehicle_id = "Test_Vehicle",
        source = "test_generator",
        obd = OBDReadings(
            rpm = Random.nextInt(800, 3000),
            speed_kmh = Random.nextInt(0, 120),
            coolant_temp_c = Random.nextFloat() * 20 + 80,  // 80-100°C
            throttle_position_pct = Random.nextFloat() * 100,
            engine_load_pct = Random.nextFloat() * 80,
            voltage_batt_v = Random.nextFloat() * 1 + 13.5f,  // 13.5-14.5V
            dtc_list = emptyList()
        )
    )
}
```

---

## 11. Code Examples

### 11.1 Complete Android Integration Example

```kotlin
// NetworkManager.kt
class PredictNetworkManager(
    private val context: Context,
    private val apiKey: String,
    private val desktopIP: String
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val baseUrl = "http://$desktopIP:8000"

    // Send OBD data
    suspend fun sendOBDData(data: OBDData): Result<ServerResponse> = withContext(Dispatchers.IO) {
        try {
            val json = gson.toJson(data)
            val request = Request.Builder()
                .url("$baseUrl/mobile/data")
                .addHeader("Content-Type", "application/json")
                .addHeader("X-API-Key", apiKey)
                .post(json.toRequestBody("application/json".toMediaType()))
                .build()

            val response = client.newCall(request).execute()
            val responseBody = response.body?.string()

            if (response.isSuccessful && responseBody != null) {
                val serverResponse = gson.fromJson(responseBody, ServerResponse::class.java)
                Result.success(serverResponse)
            } else {
                Result.failure(IOException("HTTP ${response.code}: ${response.message}"))
            }

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // Request PDF
    suspend fun requestPDF(reportType: String, deliveryMethod: String, email: String? = null): Result<PDFRequestResponse> =
        withContext(Dispatchers.IO) {
            try {
                val requestBody = mapOf(
                    "report_type" to reportType,
                    "delivery_method" to deliveryMethod,
                    "email" to email
                )

                val json = gson.toJson(requestBody)
                val request = Request.Builder()
                    .url("$baseUrl/mobile/pdf_request")
                    .addHeader("Content-Type", "application/json")
                    .addHeader("X-API-Key", apiKey)
                    .post(json.toRequestBody("application/json".toMediaType()))
                    .build()

                val response = client.newCall(request).execute()
                val responseBody = response.body?.string()

                if (response.isSuccessful && responseBody != null) {
                    val pdfResponse = gson.fromJson(responseBody, PDFRequestResponse::class.java)
                    Result.success(pdfResponse)
                } else {
                    Result.failure(IOException("HTTP ${response.code}"))
                }

            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    // Health check
    suspend fun healthCheck(): Result<HealthResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/mobile/health")
                .addHeader("X-API-Key", apiKey)
                .get()
                .build()

            val response = client.newCall(request).execute()
            val responseBody = response.body?.string()

            if (response.isSuccessful && responseBody != null) {
                val healthResponse = gson.fromJson(responseBody, HealthResponse::class.java)
                Result.success(healthResponse)
            } else {
                Result.failure(IOException("HTTP ${response.code}"))
            }

        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

// Data classes
data class OBDData(
    val timestamp: String,
    val vehicle_id: String,
    val source: String,
    val obd: OBDReadings,
    val gps: GPSData? = null,
    val vibration: VibrationData? = null,
    val missing_data_summary: List<String> = emptyList()
)

data class OBDReadings(
    val rpm: Int,
    val speed_kmh: Int,
    val coolant_temp_c: Float,
    val intake_air_temp_c: Float? = null,
    val ambient_air_temp_c: Float? = null,
    val throttle_position_pct: Float,
    val engine_load_pct: Float,
    val fuel_pressure_kpa: Float? = null,
    val intake_manifold_pressure_kpa: Float? = null,
    val timing_advance_deg: Float? = null,
    val maf_gps: Float? = null,
    val voltage_batt_v: Float,
    val oil_temp_c: Float? = null,
    val fuel_level_pct: Float? = null,
    val short_term_fuel_trim_b1: Float? = null,
    val long_term_fuel_trim_b1: Float? = null,
    val dtc_list: List<String>
)

data class GPSData(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double,
    val speed_kmh: Int,
    val accuracy_m: Float
)

data class VibrationData(
    val x: Float,
    val y: Float,
    val z: Float,
    val rms: Float
)

data class ServerResponse(
    val status: String,
    val message: String,
    val profile_name: String,
    val health_score: Int,
    val warnings: List<String>
)

data class PDFRequestResponse(
    val status: String,
    val message: String,
    val request_id: String,
    val estimated_time_seconds: Int
)

data class HealthResponse(
    val status: String,
    val server_time: String,
    val profile_name: String,
    val desktop_version: String
)
```

### 11.2 iOS Swift Integration Example

```swift
// PredictNetworkManager.swift
import Foundation

class PredictNetworkManager {
    private let apiKey: String
    private let desktopIP: String
    private let baseURL: String

    init(apiKey: String, desktopIP: String) {
        self.apiKey = apiKey
        self.desktopIP = desktopIP
        self.baseURL = "http://\(desktopIP):8000"
    }

    // Send OBD Data
    func sendOBDData(data: OBDData, completion: @escaping (Result<ServerResponse, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/mobile/data") else {
            completion(.failure(NetworkError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")

        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            request.httpBody = try encoder.encode(data)
        } catch {
            completion(.failure(error))
            return
        }

        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let data = data else {
                completion(.failure(NetworkError.invalidResponse))
                return
            }

            do {
                let decoder = JSONDecoder()
                let serverResponse = try decoder.decode(ServerResponse.self, from: data)
                completion(.success(serverResponse))
            } catch {
                completion(.failure(error))
            }
        }

        task.resume()
    }

    // Health Check
    func healthCheck(completion: @escaping (Result<HealthResponse, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/mobile/health") else {
            completion(.failure(NetworkError.invalidURL))
            return
        }

        var request = URLRequest(url: url)
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")

        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let data = data else {
                completion(.failure(NetworkError.invalidResponse))
                return
            }

            do {
                let decoder = JSONDecoder()
                let healthResponse = try decoder.decode(HealthResponse.self, from: data)
                completion(.success(healthResponse))
            } catch {
                completion(.failure(error))
            }
        }

        task.resume()
    }
}

// Data Models
struct OBDData: Codable {
    let timestamp: String
    let vehicle_id: String
    let source: String
    let obd: OBDReadings
    let gps: GPSData?
    let vibration: VibrationData?
    let missing_data_summary: [String]
}

struct OBDReadings: Codable {
    let rpm: Int
    let speed_kmh: Int
    let coolant_temp_c: Float
    let throttle_position_pct: Float
    let engine_load_pct: Float
    let voltage_batt_v: Float
    let dtc_list: [String]
    // ... other optional fields
}

struct ServerResponse: Codable {
    let status: String
    let message: String
    let profile_name: String
    let health_score: Int
    let warnings: [String]
}

struct HealthResponse: Codable {
    let status: String
    let server_time: String
    let profile_name: String
    let desktop_version: String
}

enum NetworkError: Error {
    case invalidURL
    case invalidResponse
    case unauthorized
}
```

---

## 12. Best Practices

### 12.1 Performance

- **Send data every 2 seconds** - No faster (avoid rate limiting)
- **Compress large payloads** if needed (though JSON is already small)
- **Cache API responses** to reduce network calls
- **Use connection pooling** (OkHttp does this automatically)

### 12.2 Security

- **Never log API keys** in plain text
- **Use HTTPS** if possible (requires SSL setup on desktop)
- **Store API keys securely** (Keychain/EncryptedSharedPreferences)
- **Validate server responses** before processing
- **Handle authentication failures** gracefully

### 12.3 User Experience

- **Show clear connection status** (green/yellow/red indicator)
- **Display health score prominently** (large number, color-coded)
- **Provide meaningful error messages** (not just "Error")
- **Allow manual retry** for failed operations
- **Support offline mode** seamlessly

---

## 13. Troubleshooting

### Common Issues

**Problem**: "Connection refused" error
- **Solution**: Check desktop IP address, ensure desktop app is running, verify port 8000 is not blocked

**Problem**: "Unauthorized" (401 error)
- **Solution**: API key invalid or expired, regenerate key on desktop

**Problem**: Data sending but no green indicator on desktop
- **Solution**: Check that profile name matches, verify data format is correct

**Problem**: PDF generation fails
- **Solution**: Ensure profile has enough data, check desktop logs for errors

**Problem**: Offline cache not syncing
- **Solution**: Verify connection is restored, check cache file exists and is not corrupted

---

## Contact & Support

For questions or issues, please contact:
- Email: support@predict-obd.com
- GitHub: https://github.com/predict-obd/mobile-app

---

**END OF DOCUMENT**
