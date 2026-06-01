# Android OBD App Integration - Implementation Plan

## Status: IN PROGRESS

Based on your requirements, here's the complete integration plan for connecting your Android OBD app to the desktop application.

---

## What You Have

✅ **Android App** (`PredictOBD`):
- Reads OBD PIDs from car via Bluetooth adapter
- Parses data to JSON format
- Sends HTTP POST to desktop server
- Includes vibration/accelerometer data

✅ **Desktop Server** (`server_module.py`):
- HTTP server on port 8080
- API key authentication
- Database storage (`mobile_vehicle_data` table)
- Security features (rate limiting, IP lockout)

✅ **Desktop Application** (`main_pyside.py`):
- USB OBD connectivity
- AI prediction models
- Service history tracking
- Profile management

---

## What's Missing (To Be Implemented)

### 1. Server Integration ❌
**Issue**: Mobile server is NOT started when desktop app runs

**Solution**: Need to add to `main_pyside.py`:
```python
from server_module import DDriveMobileDataServer
from mobile_data_bridge import MobileDataBridge

# In __init__managers():
self.mobile_server = DDriveMobileDataServer(port=8080)
self.mobile_bridge = MobileDataBridge()
```

### 2. Data Bridge ❌
**Issue**: Android data goes to database only, not to AI pipeline

**Solution**: Created `mobile_data_bridge.py` (DONE ✅)
- Converts Android JSON → Unified Frame format
- Emits signals for real-time data flow
- Maps Android field names to standard PIDs

### 3. UI Controls ❌
**Issue**: No way to start/stop mobile server from UI

**Solution**: Add to Connection Tab:
```python
# In ConnectionTab:
self.mobile_server_btn = QPushButton("Start Mobile Server")
self.mobile_server_status = QLabel("❌ Mobile Server: Stopped")
self.mobile_server_btn.clicked.connect(self._toggle_mobile_server)
```

### 4. Data Merging ❌
**Issue**: USB OBD and Android data not merged

**Solution**: Modify `_on_live_data()` in `main_pyside.py`:
```python
def _on_live_data(self, data: dict = None, source='usb'):
    # Check if data is from USB or Android
    if source == 'android':
        # Process Android data
        pass
    elif source == 'usb':
        # Process USB data
        pass

    # Merge both sources if both active
    merged_data = self._merge_data_sources()

    # Feed to AI models
    self.unified_ai.process_frame(merged_data)
```

### 5. Profile Sync ❌
**Issue**: Android doesn't know which profile is loaded

**Solution**: Add to server `/api/get_active_profile` endpoint:
```python
# Android app calls this on connect
GET /api/get_active_profile
Response: {
  "profile_id": "nissan_patrol_2020",
  "profile_name": "My Nissan Patrol",
  "make": "Nissan",
  "model": "Patrol",
  "year": 2020
}
```

### 6. Connection Indicator ❌
**Issue**: No visual indication of Android app connection

**Solution**: Add to UI:
```python
self.android_status_label = QLabel("📱 Android: Disconnected")
# Update when data received:
# "📱 Android: Connected (Last: 2s ago)"
```

---

## Android App Data Format

Your Android app sends this JSON structure:

```json
{
  "timestamp": "2025-12-09T20:15:22Z",
  "vehicle_id": "nissan_patrol_2020",
  "source": "android_predictobd",

  "obd": {
    "rpm": 2500,
    "speed_kmh": 80,
    "coolant_temp_c": 90,
    "intake_air_temp_c": 35,
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

---

## Field Mapping (Android → Unified Frame)

| Android Field | Unified Field | PID | Unit |
|---------------|---------------|-----|------|
| rpm | rpm | 0C | rpm |
| speed_kmh | speed | 0D | km/h |
| coolant_temp_c | coolant_temp | 05 | °C |
| intake_air_temp_c | intake_air_temp | 0F | °C |
| throttle_position_pct | throttle_position | 11 | % |
| engine_load_pct | engine_load | 04 | % |
| fuel_pressure_kpa | fuel_pressure | 0A | kPa |
| maf_gps | maf | 10 | g/s |
| voltage_batt_v | battery_voltage | 42 | V |
| oil_temp_c | oil_temp | 5C | °C |
| fuel_level_pct | fuel_level | 2F | % |

**Note**: The `mobile_data_bridge.py` already handles this mapping ✅

---

## Implementation Steps

### Step 1: Fix server_module.py Indentation Issues
**Status**: ⚠️ IN PROGRESS

The server module has indentation errors after adding PyQt5 signals. Need to:
1. Properly indent all methods under the `DDriveMobileDataServer` class
2. Ensure both HAS_PYQT and non-PyQt versions work
3. Add `mobile_data_received` signal emission in `save_to_database()`

### Step 2: Integrate Mobile Server with MainWindow
**File**: `main_pyside.py`

Add to `_init_managers()`:
```python
# Mobile server
try:
    from server_module import DDriveMobileDataServer
    from mobile_data_bridge import MobileDataBridge

    self.mobile_server = DDriveMobileDataServer(port=8080)
    self.mobile_bridge = MobileDataBridge()

    # Connect signals
    self.mobile_bridge.mobile_data_ready.connect(self._on_mobile_data)
    self.mobile_bridge.connection_status.connect(self._on_mobile_connection)

    logger.info("Mobile server initialized")
except Exception as e:
    logger.error(f"Mobile server init error: {e}")
    self.mobile_server = None
    self.mobile_bridge = None
```

### Step 3: Add Mobile Server Controls to UI
**File**: `connection_tab.py` or create new section in ConnectionTab

```python
# Mobile Server Section
mobile_group = QGroupBox("Mobile Data Server")
mobile_layout = QVBoxLayout()

# Status
self.mobile_status_label = QLabel("❌ Server: Stopped")
mobile_layout.addWidget(self.mobile_status_label)

# Port info
self.mobile_port_label = QLabel("Port: 8080")
mobile_layout.addWidget(self.mobile_port_label)

# Start/Stop button
self.mobile_server_btn = QPushButton("Start Mobile Server")
self.mobile_server_btn.clicked.connect(self._toggle_mobile_server)
mobile_layout.addWidget(self.mobile_server_btn)

# Connection status
self.android_connection_label = QLabel("📱 Android: Not connected")
mobile_layout.addWidget(self.android_connection_label)

mobile_group.setLayout(mobile_layout)
```

### Step 4: Add Mobile Data Handler
**File**: `main_pyside.py`

```python
def _toggle_mobile_server(self):
    """Start or stop the mobile data server"""
    if not self.mobile_server:
        QMessageBox.warning(self, "Error", "Mobile server not available")
        return

    if self.mobile_server.is_running:
        # Stop server
        self.mobile_server.stop_server()
        self.mobile_server_btn.setText("Start Mobile Server")
        self.mobile_status_label.setText("❌ Server: Stopped")
        logger.info("Mobile server stopped")
    else:
        # Start server
        try:
            self.mobile_server.start_server()
            self.mobile_server_btn.setText("Stop Mobile Server")
            self.mobile_status_label.setText("✅ Server: Running on port 8080")
            logger.info("Mobile server started on port 8080")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server: {e}")

def _on_mobile_data(self, unified_frame: dict):
    """Handle incoming mobile data (already in unified format)"""
    # Feed to same pipeline as USB OBD data
    self._on_live_data(unified_frame, source='android')

    # Update Android connection status
    self.android_connection_label.setText("📱 Android: Connected (Just now)")

def _on_mobile_connection(self, device_id: str, status: str):
    """Handle Android app connection status changes"""
    if status == 'connected':
        self.android_connection_label.setText(f"📱 Android: {device_id} connected")
        self.android_connection_label.setStyleSheet("color: green;")
    else:
        self.android_connection_label.setText(f"📱 Android: {device_id} disconnected")
        self.android_connection_label.setStyleSheet("color: red;")
```

### Step 5: Modify _on_live_data() for Multi-Source Support
**File**: `main_pyside.py`

```python
def _on_live_data(self, data: dict = None, source: str = 'usb'):
    """
    Handle live data update from any source

    Args:
        data: Unified frame data
        source: 'usb' or 'android'
    """
    if data is None:
        data = getattr(self.connectivity, 'latest_merged', {})

    if not data:
        return

    # Add source metadata
    if 'metadata' not in data:
        data['metadata'] = {}
    data['metadata']['source'] = source

    self.latest_snapshot = data

    # Update tabs
    self.profiles_tab.update_live_snapshot(data)
    self.ai_insights_tab.update_live_snapshot(data)
    self.forecast_tab.update_live_data(data)

    # Add source indicator to live data tab
    if hasattr(self.live_data_tab, 'set_data_source'):
        self.live_data_tab.set_data_source(source)

    # Add to history
    if data and isinstance(data, dict):
        self.history_buffer.append(data)
        if len(self.history_buffer) > 100:
            self.history_buffer.pop(0)

        # Log data
        self.data_logger.log_data(data)
```

### Step 6: Profile Sync
**File**: `main_pyside.py`

Update `_on_profile_loaded()`:
```python
def _on_profile_loaded(self, profile):
    """Handle profile loaded event"""
    # ... existing code ...

    # Sync profile to mobile server
    if self.mobile_server and self.mobile_server.is_running:
        self.mobile_server.set_active_profile(profile.get('name'))

    if self.mobile_bridge:
        self.mobile_bridge.set_active_profile(profile.get('name'))
```

### Step 7: Add Active Profile Endpoint to Server
**File**: `server_module.py`

In the request handler, add:
```python
elif self.path == '/api/get_active_profile':
    self._handle_get_active_profile()

def _handle_get_active_profile(self):
    """Return currently active profile for Android app sync"""
    try:
        if not self._authenticate('read'):
            return

        active_profile = self.server_instance.active_profile or "no_profile_loaded"

        response = {
            'status': 'success',
            'profile_name': active_profile,
            'timestamp': datetime.now().isoformat()
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    except Exception as e:
        self.send_error(500, f"Error: {str(e)}")
```

### Step 8: Update Android App to Sync Profile
**File**: Android app - `OBDDataUploader.java` (or similar)

```java
// On connect, get active profile
private void syncActiveProfile() {
    String url = serverUrl + "/api/get_active_profile";

    JsonObjectRequest request = new JsonObjectRequest(
        Request.Method.GET, url, null,
        response -> {
            try {
                String profileName = response.getString("profile_name");
                // Use this profile_name in data uploads
                this.currentProfile = profileName;
                Log.i(TAG, "Synced profile: " + profileName);
            } catch (JSONException e) {
                Log.e(TAG, "Profile sync error", e);
            }
        },
        error -> Log.e(TAG, "Profile sync failed", error)
    );

    // Add auth header
    request.setHeaders(Map.of("Authorization", "Bearer " + apiKey));
    queue.add(request);
}
```

---

## Android App Configuration

Your Android app needs these server settings:

```java
// In settings or config
public class ServerConfig {
    // Desktop PC IP address (find with ipconfig on Windows)
    public static final String SERVER_IP = "192.168.1.100";  // Change this!
    public static final int SERVER_PORT = 8080;
    public static final String SERVER_URL = "http://" + SERVER_IP + ":" + SERVER_PORT;

    // API Key (from D:/car_ai_server/config/api_keys.json)
    public static final String API_KEY = "your_api_key_here";

    // Endpoints
    public static final String ENDPOINT_VEHICLE_DATA = "/api/vehicle_data";
    public static final String ENDPOINT_ACTIVE_PROFILE = "/api/get_active_profile";
}
```

### Finding Your API Key:
1. Start the desktop app once to generate the server
2. Check file: `D:\car_ai_server\config\api_keys.json`
3. Copy the API key
4. Put it in your Android app

---

## Testing Procedure

### 1. Desktop Setup:
```bash
1. Ensure Python packages installed:
   pip install pyqt5

2. Start desktop app:
   cd "C:\D Drive\Predict"
   python main_pyside.py

3. Load a vehicle profile
4. Go to Connection tab
5. Click "Start Mobile Server"
6. Check status shows "✅ Server: Running on port 8080"
```

### 2. Network Setup:
```bash
1. Find your PC's IP address:
   - Windows: Open CMD, run "ipconfig"
   - Look for IPv4 Address (e.g., 192.168.1.100)

2. Ensure firewall allows port 8080:
   - Windows Firewall → Allow an app
   - Add inbound rule for port 8080

3. Ensure PC and phone on same WiFi network
```

### 3. Android App Setup:
```java
1. Update SERVER_IP in app to your PC's IP
2. Update API_KEY from the generated file
3. Build and install app
4. Connect OBD adapter to car
5. Launch app
6. App should:
   - Connect to OBD adapter
   - Sync active profile from desktop
   - Start sending data
```

### 4. Verification:
```bash
Desktop app should show:
- "📱 Android: nissan_patrol_2020 connected"
- Live Data tab updates with Android data
- Source indicator shows "📱 Mobile"
- AI models process the data
```

---

## File Summary

### Files Created ✅
1. `mobile_data_bridge.py` - Converts Android data to unified format
2. `ANDROID_INTEGRATION_PLAN.md` - This file

### Files to Modify ⚠️
1. `server_module.py` - Fix indentation, add signal emission
2. `main_pyside.py` - Add mobile server controls, handlers
3. `connection_tab.py` - Add mobile server UI section

### Android App Files to Modify 📱
1. `ServerConfig.java` - Add desktop IP and API key
2. `OBDDataUploader.java` - Add profile sync
3. `MainActivity.java` - Add connection status display

---

## Next Steps

1. **Fix server_module.py indentation** (in progress)
2. **Integrate mobile server into main_pyside.py**
3. **Add UI controls for mobile server**
4. **Test with Android app**
5. **Document for end users**

---

## Benefits After Integration

✅ **For Users**:
- Use phone as OBD reader (more portable)
- Get vibration data from phone's accelerometer
- No need for separate USB OBD adapter
- Can monitor car while driving

✅ **For AI**:
- More data sources = better predictions
- Vibration data helps detect engine issues
- Real-time mobile monitoring
- Can correlate phone GPS with driving patterns

---

**Current Status**: Framework created, needs final integration in main app

**Estimated Time to Complete**: 2-3 hours of focused work

**Blocking Issues**:
1. server_module.py indentation needs fixing
2. Need to add UI controls to connection tab
3. Need to test with actual Android app

Would you like me to continue with the implementation, or do you want to review this plan first?
