# Android OBD App - Quick Start Guide

## What I've Implemented

✅ **Mobile Data Bridge** (`mobile_data_bridge.py`)
- Converts Android JSON → Unified Frame format
- Maps your exact Android field names
- Ready to use

✅ **Mobile Server Wrapper** (`mobile_server_wrapper.py`)
- Clean PyQt5 integration
- Start/Stop functionality
- Data polling mechanism
- Profile sync support

✅ **Server Data Collection** (modified `server_module.py`)
- Collects incoming Android data
- Makes it available to desktop app in real-time

---

## Next Steps for Full Integration

### Quick Implementation (Add to main_pyside.py):

```python
# 1. Add imports at top of file
from mobile_server_wrapper import MobileServerWrapper
from mobile_data_bridge import MobileDataBridge

# 2. In _init_managers() method, add:
try:
    # Mobile server
    self.mobile_wrapper = MobileServerWrapper(port=8080)
    self.mobile_bridge = MobileDataBridge()

    # Connect signals
    self.mobile_wrapper.data_received.connect(self._on_android_data)
    self.mobile_bridge.mobile_data_ready.connect(self._on_mobile_unified_data)

    logger.info("Mobile server components initialized")
except Exception as e:
    logger.error(f"Mobile server init error: {e}")
    self.mobile_wrapper = None
    self.mobile_bridge = None

# 3. Add handler methods:
def _on_android_data(self, android_data):
    """Receive raw Android data and convert it"""
    if self.mobile_bridge:
        self.mobile_bridge.process_android_data(android_data)

def _on_mobile_unified_data(self, unified_frame):
    """Receive converted data in unified format"""
    # Feed to same pipeline as USB OBD
    self._on_live_data(unified_frame)

# 4. Update _on_profile_loaded() to sync profile:
def _on_profile_loaded(self, profile):
    # ... existing code ...

    # Sync to mobile server
    if hasattr(self, 'mobile_wrapper') and self.mobile_wrapper:
        self.mobile_wrapper.set_active_profile(profile.get('name'))
    if hasattr(self, 'mobile_bridge') and self.mobile_bridge:
        self.mobile_bridge.set_active_profile(profile.get('name'))
```

### Add UI Controls (In ConnectionTab or create new section):

```python
# In connection_tab.py or add to main window:

# Mobile Server Section
mobile_group = QGroupBox("📱 Android OBD Server")
mobile_layout = QVBoxLayout()

# Status
self.mobile_status_label = QLabel("Server: Stopped")
self.mobile_status_label.setStyleSheet("color: red; font-weight: bold;")

# Port info
port_label = QLabel("Port: 8080")

# Start/Stop button
self.mobile_btn = QPushButton("Start Mobile Server")
self.mobile_btn.clicked.connect(self._toggle_mobile_server)

# Android connection status
self.android_status_label = QLabel("Android: Not connected")

mobile_layout.addWidget(self.mobile_status_label)
mobile_layout.addWidget(port_label)
mobile_layout.addWidget(self.mobile_btn)
mobile_layout.addWidget(self.android_status_label)
mobile_group.setLayout(mobile_layout)

# Add to your layout
layout.addWidget(mobile_group)

# Handler:
def _toggle_mobile_server(self):
    if not hasattr(self.parent(), 'mobile_wrapper'):
        QMessageBox.warning(self, "Error", "Mobile server not available")
        return

    wrapper = self.parent().mobile_wrapper

    if wrapper.is_running:
        wrapper.stop_server()
        self.mobile_btn.setText("Start Mobile Server")
        self.mobile_status_label.setText("Server: Stopped")
        self.mobile_status_label.setStyleSheet("color: red;")
    else:
        if wrapper.start_server():
            self.mobile_btn.setText("Stop Mobile Server")
            self.mobile_status_label.setText("Server: Running ✓")
            self.mobile_status_label.setStyleSheet("color: green;")
        else:
            QMessageBox.critical(self, "Error", "Failed to start server")
```

---

## Android App Configuration

### 1. Find Your PC's IP Address:
```
Windows: Open CMD → type "ipconfig"
Look for: IPv4 Address (e.g., 192.168.1.100)
```

### 2. Configure Firewall:
```
Windows Defender Firewall → Advanced Settings
→ Inbound Rules → New Rule
→ Port → TCP → 8080 → Allow
```

### 3. Get API Key:
```
After first run, check:
D:\car_ai_server\config\api_keys.json

Copy the key value
```

### 4. Update Android App:
```java
// In your Android app settings/config:
public static final String SERVER_IP = "192.168.1.100";  // Your PC IP
public static final int SERVER_PORT = 8080;
public static final String API_KEY = "your-key-from-json-file";
```

---

## Testing Checklist

### Desktop Side:
- [ ] Start desktop app
- [ ] Load a vehicle profile
- [ ] Click "Start Mobile Server"
- [ ] Verify status shows "Server: Running ✓"
- [ ] Check firewall allows port 8080

### Network:
- [ ] PC and phone on same WiFi
- [ ] Can ping PC from phone
- [ ] Firewall rule added

### Android App:
- [ ] Server IP configured
- [ ] API key configured
- [ ] OBD adapter connected to car
- [ ] App shows "Connected to server"

### Data Flow:
- [ ] Android sends data
- [ ] Desktop receives data
- [ ] "Android: Connected" status shows
- [ ] Live Data tab updates
- [ ] AI processes the data

---

## Troubleshooting

**Server won't start:**
- Check if port 8080 already in use
- Try different port (change in both desktop and Android app)

**Android can't connect:**
- Verify IP address is correct
- Check firewall settings
- Ensure same WiFi network
- Test with: `telnet YOUR_PC_IP 8080` from phone terminal app

**No data showing:**
- Check Android app is sending data
- Verify API key is correct
- Check desktop app logs: `./logs/connectivity.log`

**Data not reaching AI:**
- Ensure profile is loaded
- Check mobile_bridge is processing data
- Verify _on_mobile_unified_data() is called

---

## File Summary

**Created Files:**
1. `mobile_server_wrapper.py` - Server integration wrapper
2. `mobile_data_bridge.py` - Data format converter
3. `ANDROID_INTEGRATION_PLAN.md` - Detailed implementation plan
4. `ANDROID_QUICK_START.md` - This file

**Modified Files:**
1. `server_module.py` - Added data collection (3 lines added)

**Files to Modify (By You):**
1. `main_pyside.py` - Add mobile server initialization and handlers
2. `connection_tab.py` - Add UI controls (or add to main window)

---

## Expected Behavior After Integration

1. **User starts desktop app**
2. **User loads vehicle profile** (e.g., "Nissan Patrol 2020")
3. **User clicks "Start Mobile Server"**
   - Button changes to "Stop Mobile Server"
   - Status shows "Server: Running ✓"
4. **User opens Android app on phone**
   - Android app connects to desktop
   - Desktop shows "Android: nissan_patrol_2020 connected"
5. **User connects OBD adapter to car**
   - Android reads OBD data
   - Sends to desktop every 1-2 seconds
6. **Desktop receives and processes data:**
   - Mobile Data Bridge converts format
   - Feeds to AI pipeline
   - Updates Live Data tab
   - AI models make predictions
   - Service history can be logged
7. **User drives car:**
   - Real-time monitoring
   - AI learns patterns
   - Predictions improve

---

## Benefits

✅ **No USB OBD adapter needed** - Use phone's Bluetooth
✅ **More portable** - Just phone + OBD adapter
✅ **Extra data** - Phone accelerometer for vibration detection
✅ **Same AI models** - Everything works identically to USB mode
✅ **Service history** - Can log services triggered by Android data
✅ **Profile sync** - Android automatically uses loaded profile

---

**Status**: Framework complete, needs UI integration in main app

**Time to complete**: 30-60 minutes to add UI controls and test

**Difficulty**: Easy - just copy/paste the code snippets above

Would you like me to create the exact code patches for main_pyside.py and connection_tab.py?
