# Android OBD App - Desktop Server Integration Guide

## Overview

This guide explains how to integrate your Android OBD app with the desktop Predict application's mobile server. The desktop server is now fully configured and running on port 8080, ready to receive OBD data from your Android app.

---

## Desktop Server - What's Already Implemented

### Server Architecture

The desktop application now includes a complete mobile server infrastructure:

1. **HTTP Server** (`server_module.py`):
   - Runs on port 8080
   - Handles POST requests to `/api/vehicle_data`
   - API key authentication
   - Rate limiting and security features
   - Stores data in SQLite database
   - Emits PyQt5 signals for real-time data processing

2. **Mobile Server Wrapper** (`mobile_server_wrapper.py`):
   - PyQt5 integration layer
   - Start/Stop functionality
   - Polling mechanism to check for incoming data
   - Profile synchronization

3. **Mobile Data Bridge** (`mobile_data_bridge.py`):
   - Converts Android JSON format → Unified Frame format
   - Maps your OBD field names to standard PIDs
   - Emits signals to main application pipeline

4. **UI Controls** (Connection Tab):
   - "📱 Android OBD Server" section
   - Start/Stop button
   - Server status indicator (running/stopped)
   - Android connection status (connected/disconnected)
   - Visual feedback with color-coded labels

5. **Live Data Integration**:
   - Data source indicator shows "📱 Android OBD" or "📡 USB OBD"
   - Seamless AI processing (same as USB OBD)
   - Real-time gauge updates
   - Service history logging

---

## Expected Android App Data Format

The desktop server expects HTTP POST requests with this JSON structure:

### Endpoint
```
POST http://<PC_IP_ADDRESS>:8080/api/vehicle_data
```

### Headers
```http
Content-Type: application/json
Authorization: Bearer <API_KEY>
```

### JSON Payload Structure

**IMPORTANT**: The server expects data in BOTH flat and nested formats to support database storage AND real-time AI processing.

```json
{
  "timestamp": "2025-12-09T20:15:22Z",
  "vehicle_id": "nissan_patrol_2020",
  "profile_id": "nissan_patrol_2020",
  "source": "android_predictobd",

  "rpm": 2500,
  "speed": 80,
  "coolant_temp": 90,
  "battery_voltage": 14.2,
  "engine_load": 60,
  "intake_pressure": 45,
  "air_temp": 35,
  "maf_flow": 8.5,
  "throttle_pos": 45,
  "fuel_pressure": 350,
  "latitude": 25.276987,
  "longitude": 55.296249,
  "acceleration_x": 0.25,
  "acceleration_y": 0.1,
  "acceleration_z": 9.8,

  "obd": {
    "rpm": 2500,
    "speed_kmh": 80,
    "coolant_temp_c": 90,
    "intake_air_temp_c": 35,
    "ambient_air_temp_c": 25,
    "throttle_position_pct": 45,
    "engine_load_pct": 60,
    "short_term_fuel_trim_b1": 2.5,
    "long_term_fuel_trim_b1": -1.2,
    "fuel_pressure_kpa": 350,
    "intake_manifold_pressure_kpa": 45,
    "timing_advance_deg": 15.5,
    "maf_gps": 8.5,
    "voltage_batt_v": 14.2,
    "oil_temp_c": 95,
    "fuel_level_pct": 65,
    "dtc_list": ["P0171", "P0174"]
  },

  "vibration": {
    "rms": 0.25,
    "peak": 0.8,
    "crest_factor": 3.2
  },

  "missing_data_summary": []
}
```

**Why Two Formats?**
- **Flat fields** (top-level): Used for database storage (`mobile_vehicle_data` table)
- **Nested `obd` object**: Used for real-time AI processing and gauge updates

**Note**: Some field names differ between formats:
- `speed_kmh` (nested) vs `speed` (flat)
- `coolant_temp_c` (nested) vs `coolant_temp` (flat)
- `voltage_batt_v` (nested) vs `battery_voltage` (flat)
```

### Field Mapping Reference

The desktop server requires data in TWO formats for different purposes:

#### **Format 1: Flat Fields (Database Storage)**

These fields are saved directly to the `mobile_vehicle_data` SQLite table:

| Flat Field Name | Type | Description | Example |
|-----------------|------|-------------|---------|
| `profile_id` | string | Vehicle profile identifier | "nissan_patrol_2020" |
| `timestamp` | string | ISO 8601 timestamp | "2025-12-09T20:15:22Z" |
| `source` | string | Data source identifier | "android_predictobd" |
| `rpm` | float | Engine RPM | 2500 |
| `speed` | float | Vehicle Speed (km/h) | 80 |
| `coolant_temp` | float | Coolant Temperature (°C) | 90 |
| `battery_voltage` | float | Battery Voltage (V) | 14.2 |
| `engine_load` | float | Engine Load (%) | 60 |
| `intake_pressure` | float | Intake Manifold Pressure (kPa) | 45 |
| `air_temp` | float | Intake Air Temperature (°C) | 35 |
| `maf_flow` | float | MAF Air Flow Rate (g/s) | 8.5 |
| `throttle_pos` | float | Throttle Position (%) | 45 |
| `fuel_pressure` | float | Fuel Pressure (kPa) | 350 |
| `latitude` | float | GPS Latitude | 25.276987 |
| `longitude` | float | GPS Longitude | 55.296249 |
| `acceleration_x` | float | Accelerometer X-axis (g) | 0.25 |
| `acceleration_y` | float | Accelerometer Y-axis (g) | 0.1 |
| `acceleration_z` | float | Accelerometer Z-axis (g) | 9.8 |

#### **Format 2: Nested `obd` Object (Real-Time AI Processing)**

These fields are used for real-time AI analysis and gauge updates:

| Nested Field (inside `obd`) | PID | Description | Unit | Example |
|------------------------------|-----|-------------|------|---------|
| `rpm` | 0C | Engine RPM | rpm | 2500 |
| `speed_kmh` | 0D | Vehicle Speed | km/h | 80 |
| `coolant_temp_c` | 05 | Coolant Temperature | °C | 90 |
| `intake_air_temp_c` | 0F | Intake Air Temperature | °C | 35 |
| `ambient_air_temp_c` | 46 | Ambient Air Temperature | °C | 25 |
| `throttle_position_pct` | 11 | Throttle Position | % | 45 |
| `engine_load_pct` | 04 | Calculated Engine Load | % | 60 |
| `short_term_fuel_trim_b1` | 06 | Short Term Fuel Trim Bank 1 | % | 2.5 |
| `long_term_fuel_trim_b1` | 07 | Long Term Fuel Trim Bank 1 | % | -1.2 |
| `fuel_pressure_kpa` | 0A | Fuel Pressure | kPa | 350 |
| `intake_manifold_pressure_kpa` | 0B | Intake Manifold Pressure | kPa | 45 |
| `timing_advance_deg` | 0E | Timing Advance | degrees | 15.5 |
| `maf_gps` | 10 | MAF Air Flow Rate | g/s | 8.5 |
| `voltage_batt_v` | 42 | Control Module Voltage | V | 14.2 |
| `oil_temp_c` | 5C | Engine Oil Temperature | °C | 95 |
| `fuel_level_pct` | 2F | Fuel Level | % | 65 |
| `dtc_list` | 01 | Diagnostic Trouble Codes | array | ["P0171", "P0174"] |

#### **Vibration Data (Nested Object)**

| Field (inside `vibration`) | Type | Description | Example |
|-----------------------------|------|-------------|---------|
| `rms` | float | RMS vibration (g) | 0.25 |
| `peak` | float | Peak vibration (g) | 0.8 |
| `crest_factor` | float | Crest factor | 3.2 |

**Critical Notes**:
- **BOTH formats must be included** in the same JSON payload
- Flat fields go at the root level (same level as `timestamp`)
- Nested fields go inside the `obd` object
- Some field names differ between formats (see table above)
- `vehicle_id` and `profile_id` should have the same value
- All numeric values should be numbers, not strings
- `timestamp` must be ISO 8601 format in UTC: `YYYY-MM-DDTHH:MM:SSZ`
- `dtc_list` is an array of strings (e.g., `["P0171", "P0420"]`)
- `missing_data_summary` is an array of field names that couldn't be read

---

## Android App Implementation Requirements

### 1. Network Configuration

#### A. Server Connection Settings

Create a configuration class or settings screen:

```java
public class ServerConfig {
    // User-configurable settings
    public static String SERVER_IP = "192.168.1.100";  // PC IP address
    public static int SERVER_PORT = 8080;
    public static String API_KEY = "";  // Set by user from desktop

    // Derived values
    public static String getServerUrl() {
        return "http://" + SERVER_IP + ":" + SERVER_PORT;
    }

    public static String getVehicleDataEndpoint() {
        return getServerUrl() + "/api/vehicle_data";
    }

    public static String getProfileEndpoint() {
        return getServerUrl() + "/api/get_active_profile";
    }
}
```

#### B. Settings UI

Add settings screen for user input:
- **Server IP Address**: Text input (e.g., "192.168.1.100")
- **Server Port**: Number input (default: 8080)
- **API Key**: Text input (long alphanumeric string)
- **Test Connection**: Button to verify connectivity
- **Current Profile**: Display synced profile name

**How Users Get Their Settings**:

1. **PC IP Address**:
   ```
   Windows PC → Open Command Prompt → Type: ipconfig
   Look for "IPv4 Address" under active network adapter
   Example: 192.168.1.100
   ```

2. **API Key**:
   ```
   Desktop app generates it on first run
   Location: D:\car_ai_server\config\api_keys.json
   Copy the "key" value
   ```

3. **Firewall**:
   ```
   Windows Defender Firewall → Advanced Settings → Inbound Rules
   → New Rule → Port → TCP → 8080 → Allow
   ```

---

### 2. HTTP Client Implementation

#### A. Dependencies

Add to `build.gradle`:

```gradle
dependencies {
    // HTTP client
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'

    // JSON parsing
    implementation 'com.google.code.gson:gson:2.10.1'

    // Or use Volley
    implementation 'com.android.volley:volley:1.2.1'
}
```

#### B. Data Model Classes

```java
public class VehicleData {
    // Top-level fields (for database storage)
    @SerializedName("timestamp")
    private String timestamp;

    @SerializedName("vehicle_id")
    private String vehicleId;

    @SerializedName("profile_id")
    private String profileId;

    @SerializedName("source")
    private String source = "android_predictobd";

    // Flat OBD fields (database format)
    @SerializedName("rpm")
    private Double rpm;

    @SerializedName("speed")
    private Double speed;

    @SerializedName("coolant_temp")
    private Double coolantTemp;

    @SerializedName("battery_voltage")
    private Double batteryVoltage;

    @SerializedName("engine_load")
    private Double engineLoad;

    @SerializedName("intake_pressure")
    private Double intakePressure;

    @SerializedName("air_temp")
    private Double airTemp;

    @SerializedName("maf_flow")
    private Double mafFlow;

    @SerializedName("throttle_pos")
    private Double throttlePos;

    @SerializedName("fuel_pressure")
    private Double fuelPressure;

    // GPS data
    @SerializedName("latitude")
    private Double latitude;

    @SerializedName("longitude")
    private Double longitude;

    // Accelerometer data (flat)
    @SerializedName("acceleration_x")
    private Double accelerationX;

    @SerializedName("acceleration_y")
    private Double accelerationY;

    @SerializedName("acceleration_z")
    private Double accelerationZ;

    // Nested objects (for real-time AI processing)
    @SerializedName("obd")
    private OBDData obd;

    @SerializedName("vibration")
    private VibrationData vibration;

    @SerializedName("missing_data_summary")
    private List<String> missingDataSummary = new ArrayList<>();

    // Constructor
    public VehicleData(String vehicleId) {
        this.vehicleId = vehicleId;
        this.profileId = vehicleId; // Same as vehicle_id
        this.timestamp = getCurrentTimestamp();
        this.obd = new OBDData();
        this.vibration = new VibrationData();
    }

    private String getCurrentTimestamp() {
        // ISO 8601 format in UTC
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
        return sdf.format(new Date());
    }

    /**
     * Sync flat fields with nested OBD data
     * Call this before sending to ensure both formats are populated
     */
    public void syncFields() {
        if (obd != null) {
            this.rpm = obd.getRpm();
            this.speed = obd.getSpeedKmh();
            this.coolantTemp = obd.getCoolantTempC();
            this.batteryVoltage = obd.getVoltageBattV();
            this.engineLoad = obd.getEngineLoadPct();
            this.intakePressure = obd.getIntakeManifoldPressureKpa();
            this.airTemp = obd.getIntakeAirTempC();
            this.mafFlow = obd.getMafGps();
            this.throttlePos = obd.getThrottlePositionPct();
            this.fuelPressure = obd.getFuelPressureKpa();
        }

        if (vibration != null) {
            this.accelerationX = vibration.getRms(); // Or use actual accelerometer
            this.accelerationY = 0.0; // Set from your accelerometer
            this.accelerationZ = 0.0; // Set from your accelerometer
        }
    }

    // Getters and setters for all fields
    // ... (add getters/setters for rpm, speed, coolantTemp, etc.)
}

public class OBDData {
    @SerializedName("rpm")
    private Double rpm;

    @SerializedName("speed_kmh")
    private Double speedKmh;

    @SerializedName("coolant_temp_c")
    private Double coolantTempC;

    @SerializedName("intake_air_temp_c")
    private Double intakeAirTempC;

    @SerializedName("ambient_air_temp_c")
    private Double ambientAirTempC;

    @SerializedName("throttle_position_pct")
    private Double throttlePositionPct;

    @SerializedName("engine_load_pct")
    private Double engineLoadPct;

    @SerializedName("short_term_fuel_trim_b1")
    private Double shortTermFuelTrimB1;

    @SerializedName("long_term_fuel_trim_b1")
    private Double longTermFuelTrimB1;

    @SerializedName("fuel_pressure_kpa")
    private Double fuelPressureKpa;

    @SerializedName("intake_manifold_pressure_kpa")
    private Double intakeManifoldPressureKpa;

    @SerializedName("timing_advance_deg")
    private Double timingAdvanceDeg;

    @SerializedName("maf_gps")
    private Double mafGps;

    @SerializedName("voltage_batt_v")
    private Double voltageBattV;

    @SerializedName("oil_temp_c")
    private Double oilTempC;

    @SerializedName("fuel_level_pct")
    private Double fuelLevelPct;

    @SerializedName("dtc_list")
    private List<String> dtcList = new ArrayList<>();

    // Getters and setters for all fields
}

public class VibrationData {
    @SerializedName("rms")
    private Double rms;

    @SerializedName("peak")
    private Double peak;

    @SerializedName("crest_factor")
    private Double crestFactor;

    // Getters and setters
}
```

#### C. HTTP Client Service

```java
public class DesktopServerClient {
    private static final String TAG = "DesktopServerClient";
    private OkHttpClient httpClient;
    private Gson gson;
    private String currentProfile = null;

    public DesktopServerClient() {
        httpClient = new OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build();

        gson = new Gson();
    }

    /**
     * Test connection to desktop server
     */
    public boolean testConnection() {
        try {
            Request request = new Request.Builder()
                .url(ServerConfig.getServerUrl() + "/api/health")
                .get()
                .build();

            Response response = httpClient.newCall(request).execute();
            return response.isSuccessful();
        } catch (IOException e) {
            Log.e(TAG, "Connection test failed", e);
            return false;
        }
    }

    /**
     * Sync active profile from desktop
     * Call this when app connects to server
     */
    public void syncActiveProfile(ProfileSyncCallback callback) {
        Request request = new Request.Builder()
            .url(ServerConfig.getProfileEndpoint())
            .addHeader("Authorization", "Bearer " + ServerConfig.API_KEY)
            .get()
            .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    String json = response.body().string();
                    try {
                        JsonObject obj = JsonParser.parseString(json).getAsJsonObject();
                        currentProfile = obj.get("profile_name").getAsString();
                        Log.i(TAG, "Synced profile: " + currentProfile);
                        callback.onProfileSynced(currentProfile);
                    } catch (Exception e) {
                        Log.e(TAG, "Failed to parse profile response", e);
                        callback.onSyncFailed(e.getMessage());
                    }
                } else {
                    callback.onSyncFailed("HTTP " + response.code());
                }
            }

            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "Profile sync failed", e);
                callback.onSyncFailed(e.getMessage());
            }
        });
    }

    /**
     * Send vehicle data to desktop server
     * Call this every 1-2 seconds with latest OBD data
     */
    public void sendVehicleData(VehicleData data, DataUploadCallback callback) {
        // Use synced profile if available
        if (currentProfile != null && !currentProfile.equals("no_profile_loaded")) {
            data.setVehicleId(currentProfile);
        }

        String json = gson.toJson(data);

        RequestBody body = RequestBody.create(
            json,
            MediaType.parse("application/json; charset=utf-8")
        );

        Request request = new Request.Builder()
            .url(ServerConfig.getVehicleDataEndpoint())
            .addHeader("Content-Type", "application/json")
            .addHeader("Authorization", "Bearer " + ServerConfig.API_KEY)
            .post(body)
            .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    String responseJson = response.body().string();
                    Log.d(TAG, "Data uploaded successfully: " + responseJson);
                    callback.onSuccess(responseJson);
                } else {
                    String error = "HTTP " + response.code() + ": " + response.message();
                    Log.e(TAG, "Upload failed: " + error);
                    callback.onError(error);
                }
            }

            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "Upload failed", e);
                callback.onError(e.getMessage());
            }
        });
    }

    // Callbacks
    public interface ProfileSyncCallback {
        void onProfileSynced(String profileName);
        void onSyncFailed(String error);
    }

    public interface DataUploadCallback {
        void onSuccess(String response);
        void onError(String error);
    }
}
```

---

### 3. OBD Data Collection Integration

#### A. Main Data Flow

```java
public class OBDDataManager {
    private DesktopServerClient serverClient;
    private Handler uploadHandler;
    private Runnable uploadTask;
    private boolean isUploading = false;
    private VehicleData currentData;

    // Your existing OBD connection
    private BluetoothSocket obdSocket;
    private ELM327 elm327;

    public OBDDataManager() {
        serverClient = new DesktopServerClient();
        uploadHandler = new Handler(Looper.getMainLooper());
        currentData = new VehicleData("default_vehicle");
    }

    /**
     * Start uploading data to desktop server
     * Call this after OBD connection is established
     */
    public void startServerUpload() {
        if (isUploading) return;

        // First, sync profile
        serverClient.syncActiveProfile(new DesktopServerClient.ProfileSyncCallback() {
            @Override
            public void onProfileSynced(String profileName) {
                Log.i("OBDDataManager", "Using profile: " + profileName);
                currentData.setVehicleId(profileName);

                // Start periodic upload
                isUploading = true;
                uploadTask = new Runnable() {
                    @Override
                    public void run() {
                        if (isUploading) {
                            uploadCurrentData();
                            uploadHandler.postDelayed(this, 1500); // Every 1.5 seconds
                        }
                    }
                };
                uploadHandler.post(uploadTask);
            }

            @Override
            public void onSyncFailed(String error) {
                Log.w("OBDDataManager", "Profile sync failed, using default: " + error);
                // Continue with default vehicle_id
                isUploading = true;
                uploadHandler.post(uploadTask);
            }
        });
    }

    /**
     * Stop uploading data
     */
    public void stopServerUpload() {
        isUploading = false;
        if (uploadTask != null) {
            uploadHandler.removeCallbacks(uploadTask);
        }
    }

    /**
     * Update OBD data from your existing reader
     * Call this whenever you read new OBD data
     */
    public void updateOBDData(String pid, Object value) {
        OBDData obd = currentData.getObd();

        switch (pid) {
            case "010C": // RPM
                obd.setRpm(convertToDouble(value));
                break;
            case "010D": // Speed
                obd.setSpeedKmh(convertToDouble(value));
                break;
            case "0105": // Coolant temp
                obd.setCoolantTempC(convertToDouble(value));
                break;
            case "010F": // Intake air temp
                obd.setIntakeAirTempC(convertToDouble(value));
                break;
            case "0111": // Throttle position
                obd.setThrottlePositionPct(convertToDouble(value));
                break;
            case "0104": // Engine load
                obd.setEngineLoadPct(convertToDouble(value));
                break;
            case "010A": // Fuel pressure
                obd.setFuelPressureKpa(convertToDouble(value));
                break;
            case "0110": // MAF
                obd.setMafGps(convertToDouble(value));
                break;
            case "0142": // Battery voltage
                obd.setVoltageBattV(convertToDouble(value));
                break;
            case "015C": // Oil temp
                obd.setOilTempC(convertToDouble(value));
                break;
            case "012F": // Fuel level
                obd.setFuelLevelPct(convertToDouble(value));
                break;
            // Add more PIDs as needed
        }
    }

    /**
     * Update vibration data from accelerometer
     */
    public void updateVibrationData(double rms, double peak, double crestFactor) {
        VibrationData vibration = currentData.getVibration();
        vibration.setRms(rms);
        vibration.setPeak(peak);
        vibration.setCrestFactor(crestFactor);
    }

    /**
     * Upload current data snapshot to desktop
     */
    private void uploadCurrentData() {
        // CRITICAL: Sync flat and nested fields before sending
        currentData.syncFields();

        // Create a copy to avoid concurrent modification
        VehicleData dataToSend = currentData.copy();

        serverClient.sendVehicleData(dataToSend, new DesktopServerClient.DataUploadCallback() {
            @Override
            public void onSuccess(String response) {
                Log.d("OBDDataManager", "Data uploaded successfully");
                // Update UI if needed
            }

            @Override
            public void onError(String error) {
                Log.e("OBDDataManager", "Upload error: " + error);
                // Handle error (show notification, retry, etc.)
            }
        });
    }

    private Double convertToDouble(Object value) {
        if (value == null) return null;
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        try {
            return Double.parseDouble(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
```

---

### 4. Accelerometer Integration (Optional but Recommended)

```java
public class VibrationMonitor implements SensorEventListener {
    private SensorManager sensorManager;
    private Sensor accelerometer;
    private float[] gravity = new float[3];
    private float[] acceleration = new float[3];
    private List<Float> recentAcceleration = new ArrayList<>();
    private static final int SAMPLE_SIZE = 50;

    public VibrationMonitor(Context context) {
        sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
    }

    public void start() {
        sensorManager.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_NORMAL);
    }

    public void stop() {
        sensorManager.unregisterListener(this);
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        // Apply low-pass filter
        final float alpha = 0.8f;
        gravity[0] = alpha * gravity[0] + (1 - alpha) * event.values[0];
        gravity[1] = alpha * gravity[1] + (1 - alpha) * event.values[1];
        gravity[2] = alpha * gravity[2] + (1 - alpha) * event.values[2];

        // Remove gravity
        acceleration[0] = event.values[0] - gravity[0];
        acceleration[1] = event.values[1] - gravity[1];
        acceleration[2] = event.values[2] - gravity[2];

        // Calculate magnitude
        float magnitude = (float) Math.sqrt(
            acceleration[0] * acceleration[0] +
            acceleration[1] * acceleration[1] +
            acceleration[2] * acceleration[2]
        );

        recentAcceleration.add(magnitude);
        if (recentAcceleration.size() > SAMPLE_SIZE) {
            recentAcceleration.remove(0);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // Not needed
    }

    /**
     * Calculate vibration metrics
     */
    public VibrationData getVibrationData() {
        if (recentAcceleration.isEmpty()) {
            return new VibrationData();
        }

        // Calculate RMS
        double sumSquares = 0;
        float peak = 0;
        for (float acc : recentAcceleration) {
            sumSquares += acc * acc;
            if (acc > peak) peak = acc;
        }
        double rms = Math.sqrt(sumSquares / recentAcceleration.size());

        // Calculate crest factor
        double crestFactor = peak / rms;

        VibrationData data = new VibrationData();
        data.setRms(rms);
        data.setPeak((double) peak);
        data.setCrestFactor(crestFactor);

        return data;
    }
}
```

---

### 5. UI Components

#### A. Connection Status Indicator

Add to your main activity layout:

```xml
<LinearLayout
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="horizontal"
    android:padding="8dp"
    android:background="@color/status_background">

    <!-- Desktop Server Status -->
    <TextView
        android:id="@+id/server_status_label"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_weight="1"
        android:text="Desktop: Disconnected"
        android:textColor="@color/error"
        android:textStyle="bold"/>

    <!-- Upload indicator -->
    <ProgressBar
        android:id="@+id/upload_progress"
        android:layout_width="24dp"
        android:layout_height="24dp"
        android:visibility="gone"/>

</LinearLayout>
```

#### B. Activity Code

```java
public class MainActivity extends AppCompatActivity {
    private TextView serverStatusLabel;
    private ProgressBar uploadProgress;
    private OBDDataManager obdManager;
    private VibrationMonitor vibrationMonitor;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        serverStatusLabel = findViewById(R.id.server_status_label);
        uploadProgress = findViewById(R.id.upload_progress);

        obdManager = new OBDDataManager();
        vibrationMonitor = new VibrationMonitor(this);

        // Settings button
        findViewById(R.id.settings_button).setOnClickListener(v -> {
            startActivity(new Intent(this, SettingsActivity.class));
        });
    }

    /**
     * Call this after OBD connection is established
     */
    private void onOBDConnected() {
        // Start desktop server upload
        obdManager.startServerUpload();
        vibrationMonitor.start();

        // Update UI
        serverStatusLabel.setText("Desktop: Connected");
        serverStatusLabel.setTextColor(getColor(R.color.success));
        uploadProgress.setVisibility(View.VISIBLE);
    }

    /**
     * Call this when OBD disconnects
     */
    private void onOBDDisconnected() {
        obdManager.stopServerUpload();
        vibrationMonitor.stop();

        // Update UI
        serverStatusLabel.setText("Desktop: Disconnected");
        serverStatusLabel.setTextColor(getColor(R.color.error));
        uploadProgress.setVisibility(View.GONE);
    }

    /**
     * Update vibration data periodically
     */
    private void updateVibrationData() {
        VibrationData vibData = vibrationMonitor.getVibrationData();
        obdManager.updateVibrationData(
            vibData.getRms(),
            vibData.getPeak(),
            vibData.getCrestFactor()
        );
    }
}
```

---

## Testing & Troubleshooting

### Testing Checklist

1. **Desktop Setup**:
   - [ ] Desktop app running
   - [ ] Navigate to Connection Tab
   - [ ] Click "Start Mobile Server"
   - [ ] Status shows "Server: Running ✓"
   - [ ] Note the PC's IP address (use `ipconfig` in CMD)

2. **Network Setup**:
   - [ ] PC and phone on same WiFi network
   - [ ] Firewall allows port 8080
   - [ ] Can ping PC from phone (use network tools app)

3. **Android App Setup**:
   - [ ] Server IP configured in settings
   - [ ] API key entered (from `api_keys.json` file)
   - [ ] OBD adapter connected to car
   - [ ] App has internet permission in manifest

4. **Connection Test**:
   - [ ] Android app connects to OBD
   - [ ] Desktop shows "Android: <profile> connected"
   - [ ] Live Data tab shows "📱 Android OBD" badge
   - [ ] Gauges update in real-time

### Common Issues & Solutions

#### Issue: "Connection refused" or timeout

**Causes**:
- PC firewall blocking port 8080
- Wrong IP address
- Different WiFi networks

**Solutions**:
```
1. Verify IP address: Run 'ipconfig' on PC
2. Test from phone browser: http://<PC_IP>:8080/api/health
3. Add firewall rule for port 8080
4. Ensure both devices on same network
```

#### Issue: "401 Unauthorized"

**Cause**: Invalid or missing API key

**Solution**:
```
1. Check desktop file: D:\car_ai_server\config\api_keys.json
2. Copy exact API key (it's a long string)
3. Paste into Android app settings
4. Ensure "Bearer " prefix is added in Authorization header
```

#### Issue: "No data showing on desktop"

**Causes**:
- Wrong JSON field names
- Missing required fields
- Data not being sent

**Solutions**:
```
1. Check Android logcat for upload errors
2. Verify JSON matches expected format exactly
3. Ensure upload interval is 1-2 seconds
4. Check desktop logs: ./logs/connectivity.log
```

#### Issue: Data uploads but not processed

**Cause**: Field name mismatch

**Solution**:
```
Use exact field names from the mapping table above:
✅ "rpm" not "RPM" or "engineRpm"
✅ "speed_kmh" not "speed" or "speedKph"
✅ "coolant_temp_c" not "coolantTemp" or "temperature"
```

---

## Required Permissions

Add to `AndroidManifest.xml`:

```xml
<manifest>
    <!-- Network permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />

    <!-- Bluetooth for OBD -->
    <uses-permission android:name="android.permission.BLUETOOTH" />
    <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
    <uses-permission android:name="android.permission.BLUETOOTH_SCAN" />

    <!-- Location (required for Bluetooth on Android 12+) -->
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />

    <!-- Sensors -->
    <uses-permission android:name="android.permission.BODY_SENSORS" />

    <application>
        <!-- Cleartext traffic for local network -->
        <application
            android:usesCleartextTraffic="true">
        </application>
    </application>
</manifest>
```

---

## Security Considerations

1. **API Key Storage**:
   - Store API key in SharedPreferences with encryption
   - Use Android Keystore for production apps
   - Don't hardcode in source code

2. **Network Security**:
   - Use HTTPS for production (current setup uses HTTP for local network)
   - Validate SSL certificates if using HTTPS
   - Implement retry logic with exponential backoff

3. **Data Privacy**:
   - Inform users data is sent to their PC
   - Only send data when user explicitly enables it
   - Provide clear connection status indicators

---

## Performance Optimization

1. **Upload Frequency**:
   - Recommended: 1-2 seconds between uploads
   - Don't upload faster than 500ms (network overhead)
   - Batch multiple PID reads into single upload

2. **Battery Usage**:
   - Use background service with foreground notification
   - Stop uploads when screen off (configurable)
   - Implement wake lock if needed for continuous monitoring

3. **Data Efficiency**:
   - Only send PIDs that have values (omit nulls)
   - Compress data for slow networks (gzip)
   - Implement local queue for failed uploads

---

## Example Complete Flow

```java
// In your MainActivity or Service

// 1. Initialize managers
OBDDataManager obdManager = new OBDDataManager();
VibrationMonitor vibrationMonitor = new VibrationMonitor(context);

// 2. Connect to OBD
connectToOBD(); // Your existing method

// 3. Start desktop server upload
obdManager.startServerUpload();
vibrationMonitor.start();

// 4. In your OBD reading loop
while (connected) {
    // Read OBD data (your existing code)
    String rpm = readPID("010C");
    String speed = readPID("010D");
    String coolantTemp = readPID("0105");
    // ... etc

    // Update manager
    obdManager.updateOBDData("010C", rpm);
    obdManager.updateOBDData("010D", speed);
    obdManager.updateOBDData("0105", coolantTemp);

    // Update vibration
    VibrationData vib = vibrationMonitor.getVibrationData();
    obdManager.updateVibrationData(vib.getRms(), vib.getPeak(), vib.getCrestFactor());

    // Manager automatically uploads every 1.5 seconds

    Thread.sleep(100); // Your poll interval
}

// 5. On disconnect
obdManager.stopServerUpload();
vibrationMonitor.stop();
```

---

## Desktop Server API Reference

### Endpoints

#### 1. Health Check
```http
GET /api/health
Response: 200 OK
```

#### 2. Get Active Profile
```http
GET /api/get_active_profile
Headers:
  Authorization: Bearer <API_KEY>

Response:
{
  "status": "success",
  "profile_name": "nissan_patrol_2020",
  "timestamp": "2025-12-09T10:30:00Z"
}
```

#### 3. Upload Vehicle Data
```http
POST /api/vehicle_data
Headers:
  Content-Type: application/json
  Authorization: Bearer <API_KEY>

Body: (see JSON structure above)

Response:
{
  "status": "success",
  "message": "Data received",
  "timestamp": "2025-12-09T10:30:00Z"
}
```

---

## Support & Debugging

### Desktop Logs

Check these log files on PC:
```
./logs/connectivity.log       - Connection events
./logs/server.log             - Server requests
./data/logs/session_*.json    - Data sessions
```

### Android Logs

Enable verbose logging:
```java
public class ServerConfig {
    public static final boolean DEBUG = true;

    public static void log(String message) {
        if (DEBUG) {
            Log.d("DesktopServer", message);
        }
    }
}
```

### Network Debugging

Use a network inspector app on Android:
- **HTTP Toolkit** - Monitor all HTTP traffic
- **Packet Capture** - See raw network packets
- **Network Monitor** - Check connectivity

---

## Summary - What You Need to Implement

### ✅ Must Have
1. Server configuration settings (IP, port, API key)
2. HTTP client to POST JSON data
3. Data model matching the expected format
4. Integration with your OBD reading code
5. Periodic upload (1-2 seconds)
6. Connection status indicator

### ⭐ Should Have
7. Profile sync on connect
8. Error handling and retry logic
9. Visual feedback (upload indicator)
10. Settings screen for user configuration

### 💡 Nice to Have
11. Accelerometer vibration monitoring
12. Local data queue for offline mode
13. Battery optimization options
14. Connection quality indicator

---

## Need Help?

If you encounter issues:
1. Check desktop logs first
2. Enable Android debug logging
3. Test with simple HTTP client (Postman, curl)
4. Verify JSON format exactly matches spec
5. Ensure API key is correct

---

**Desktop Server Status**: ✅ Fully implemented and tested
**Ready for Android Integration**: ✅ Yes
**Next Step**: Implement Android HTTP client as described above

Good luck with your Android implementation! 🚗📱
