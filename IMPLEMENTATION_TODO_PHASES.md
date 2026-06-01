# PREDICT Complete Implementation TODO - Phased Approach

> **Instructions for GLM4.7**: Complete each phase in order. After each phase, notify the user so they can verify the implementation works correctly with tests before proceeding to the next phase.

---

## PRIORITY ORDER

```
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 1: DESKTOP APPLICATION (Phases 1-10)              │
│  Location: c:\D Drive\Predict                               │
│  Status: Complete this FIRST before anything else           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 2: PREVILIUM SERVER (Phases 11-13)                │
│  Location: C:\OBDserver\Previlium_OBD_Server                │
│  Status: Only after Desktop is 100% working                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 3: ANDROID DRIVER APP - PredictOBD (Phases 14-15) │
│  Location: C:\Predict\PredictOBD                            │
│  Status: Only after Server is verified                      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 4: ANDROID GUARDIAN APP (Phases 16-18)            │
│  Location: C:\Predict guradian                              │
│  Status: Parent/Fleet Manager monitoring app                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 5: FULL INTEGRATION TESTING (Phases 19-20)        │
│  All apps connected and working together                    │
└─────────────────────────────────────────────────────────────┘
```

---

## PROJECT OVERVIEW

**Current State**: 62% complete
**Goal**: 100% fully functional application with all features wired and tested

**Complete Ecosystem Architecture**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PREDICT VEHICLE INTELLIGENCE PLATFORM                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐         ┌─────────────────────────────┐    │
│  │  PREDICT Desktop App       │         │  Previlium Server           │    │
│  │  (c:\D Drive\Predict)      │◀───────▶│  (C:\OBDserver\...)         │    │
│  │                            │   API    │                             │    │
│  │  - AI Predictions          │         │  - Vehicle Data Storage     │    │
│  │  - PDF Reports             │         │  - Guardian API             │    │
│  │  - OBD Diagnostics         │         │  - WebSocket Streaming      │    │
│  │  - Fuel Tracking           │         │  - Driver/Geofence APIs     │    │
│  │  - Maintenance             │         │  - Push Notifications       │    │
│  │  Priority: 1 (Phases 1-10) │         │  Priority: 2 (Phases 11-13) │    │
│  └─────────────────────────────┘         └──────────────┬──────────────┘    │
│                                                         │                    │
│         ┌───────────────────────────────────────────────┴────────────────┐  │
│         │                        Cloud/API Layer                          │  │
│         └───────────────────────────────────────────────┬────────────────┘  │
│                                                         │                    │
│  ┌─────────────────────────────┐         ┌─────────────────────────────┐    │
│  │  PredictOBD (Driver App)   │         │  Predict Guardian App       │    │
│  │  (C:\Predict\PredictOBD)   │         │  (C:\Predict guradian)      │    │
│  │                            │         │                             │    │
│  │  - OBD Bluetooth Connect   │   ───▶  │  - Multi-Vehicle Dashboard  │    │
│  │  - Driver Profile Select   │  Sends  │  - Teen Driver Monitoring   │    │
│  │  - Real-time Telemetry     │  Data   │  - AI Predictions View      │    │
│  │  - Session Management      │         │  - Geofencing Management    │    │
│  │  - Location Tracking       │         │  - Emergency Commands       │    │
│  │  Priority: 3 (Phases 14-15)│         │  Priority: 4 (Phases 16-18) │    │
│  └─────────────────────────────┘         └─────────────────────────────┘    │
│                                                                              │
│  Target Users:                                                               │
│  • Desktop: Mechanics, Fleet Managers, Power Users                          │
│  • PredictOBD: Drivers (installs in vehicle, connects to OBD)               │
│  • Guardian: Parents, Fleet Managers (monitors drivers remotely)            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Desktop App Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│                    PREDICT Desktop App                       │
│                  (c:\D Drive\Predict)                        │
├─────────────────────────────────────────────────────────────┤
│  UI Layer (PySide6 Tabs)                                    │
│  ├── fuel_tracking_tab.py ──────┐                           │
│  ├── driving_score_tab.py ──────┤                           │
│  ├── geofencing_tab.py ─────────┼──> Need Backend Wiring    │
│  ├── notifications_tab.py ──────┤                           │
│  ├── maintenance_reminders_tab.py ┤                         │
│  └── recall_alerts_tab.py ──────┘                           │
├─────────────────────────────────────────────────────────────┤
│  Backend Layer (Already Implemented)                         │
│  ├── fuel_tracking.py           (FuelTracker class)         │
│  ├── driving_score.py           (DrivingScoreAnalyzer)      │
│  ├── geofencing_alerts.py       (GeofencingManager)         │
│  ├── alert_notifications.py     (AlertNotificationManager)  │
│  ├── maintenance_predictor.py   (MaintenancePredictor)      │
│  └── nhtsa_recall_api.py        (RecallChecker)             │
├─────────────────────────────────────────────────────────────┤
│  AI Layer (Mostly Complete)                                  │
│  ├── lstm_predictor.py          ✅ Trained                  │
│  ├── enhanced_prediction_engine.py ✅ Working               │
│  ├── ai_auto_retraining.py      ⚠️ Has mock returns         │
│  └── ai_prediction_integrity.py ⚠️ Has placeholder          │
└─────────────────────────────────────────────────────────────┘
```

---

# PHASE 1: Fuel Tracking Tab - Backend Wiring

**Priority**: HIGH
**Estimated Complexity**: Medium
**Files to Modify**:
- `c:\D Drive\Predict\fuel_tracking_tab.py`
- `c:\D Drive\Predict\fuel_tracking.py` (backend - verify exists)

## Task 1.1: Verify Backend Exists

**Action**: Check that `fuel_tracking.py` has the `FuelTracker` class with these methods:
- `add_fuel_entry(date, odometer, gallons, price_per_gallon, fuel_type, station, notes)`
- `get_fuel_history(profile_id, limit=None)`
- `get_fuel_statistics(profile_id)`
- `calculate_mpg(entries)`
- `get_monthly_spending(profile_id)`

**If backend missing**: Create the backend class first.

## Task 1.2: Import Backend in Tab

**File**: `c:\D Drive\Predict\fuel_tracking_tab.py`

**Find** (around line 1-50):
```python
# Look for existing imports
```

**Add Import**:
```python
# Import fuel tracking backend
try:
    from fuel_tracking import FuelTracker, get_fuel_tracker
    FUEL_TRACKER_AVAILABLE = True
except ImportError:
    FUEL_TRACKER_AVAILABLE = False
    FuelTracker = None
```

## Task 1.3: Initialize Backend in __init__

**File**: `c:\D Drive\Predict\fuel_tracking_tab.py`

**Find** the `__init__` method and add:
```python
def __init__(self, fuel_system=None, parent=None):
    super().__init__(parent)

    # Initialize fuel tracker backend
    if fuel_system:
        self.fuel_tracker = fuel_system
    elif FUEL_TRACKER_AVAILABLE:
        try:
            self.fuel_tracker = get_fuel_tracker()
        except Exception as e:
            logger.warning(f"Could not initialize FuelTracker: {e}")
            self.fuel_tracker = None
    else:
        self.fuel_tracker = None

    # Rest of init...
```

## Task 1.4: Replace Mock Data Loading

**File**: `c:\D Drive\Predict\fuel_tracking_tab.py`

**Find** the `_load_mock_data` method (search for `def _load_mock_data`).

**Replace the entire method with**:
```python
def _load_fuel_data(self):
    """Load real fuel data from backend"""
    try:
        if not self.fuel_tracker:
            logger.warning("No fuel tracker available, using empty data")
            self.fuel_entries = []
            return

        # Get current profile ID
        profile_id = self._get_current_profile_id()
        if not profile_id:
            self.fuel_entries = []
            return

        # Load from backend
        self.fuel_entries = self.fuel_tracker.get_fuel_history(profile_id)
        logger.info(f"Loaded {len(self.fuel_entries)} fuel entries")

    except Exception as e:
        logger.error(f"Error loading fuel data: {e}")
        self.fuel_entries = []

def _get_current_profile_id(self):
    """Get the currently active profile ID"""
    # Try to get from parent window
    if hasattr(self, 'parent') and self.parent():
        parent = self.parent()
        while parent:
            if hasattr(parent, 'active_profile'):
                profile = parent.active_profile
                if profile:
                    return profile.get('id') or profile.get('profile_id')
            parent = parent.parent() if hasattr(parent, 'parent') else None
    return None
```

## Task 1.5: Update Refresh Method

**Find** any method that calls `_load_mock_data` and replace with `_load_fuel_data`.

**Find** the refresh button click handler and update:
```python
def _refresh_data(self):
    """Refresh fuel data from backend"""
    self._load_fuel_data()
    self._update_table()
    self._update_statistics()
```

## Task 1.6: Wire Add Entry to Backend

**Find** the method that handles adding new fuel entries (likely `_add_fuel_entry` or `_save_entry`).

**Update to save to backend**:
```python
def _add_fuel_entry(self):
    """Add new fuel entry to backend"""
    try:
        # Gather form data
        date = self.date_edit.date().toPython()
        odometer = self.odometer_spin.value()
        gallons = self.gallons_spin.value()
        price = self.price_spin.value()
        fuel_type = self.fuel_type_combo.currentText()
        station = self.station_edit.text()
        notes = self.notes_edit.text()

        if not self.fuel_tracker:
            QMessageBox.warning(self, "Error", "Fuel tracking system not available")
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            QMessageBox.warning(self, "Error", "No active profile selected")
            return

        # Save to backend
        success = self.fuel_tracker.add_fuel_entry(
            profile_id=profile_id,
            date=date,
            odometer=odometer,
            gallons=gallons,
            price_per_gallon=price,
            fuel_type=fuel_type,
            station=station,
            notes=notes
        )

        if success:
            QMessageBox.information(self, "Success", "Fuel entry added successfully")
            self._load_fuel_data()
            self._update_table()
            self._update_statistics()
            self._clear_form()
        else:
            QMessageBox.warning(self, "Error", "Failed to add fuel entry")

    except Exception as e:
        logger.error(f"Error adding fuel entry: {e}")
        QMessageBox.critical(self, "Error", f"Failed to add entry: {e}")
```

## Task 1.7: Wire Statistics to Backend

**Find** the `_update_statistics` or `_load_statistics` method.

**Update**:
```python
def _update_statistics(self):
    """Update statistics from backend"""
    try:
        if not self.fuel_tracker:
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            return

        stats = self.fuel_tracker.get_fuel_statistics(profile_id)

        # Update UI labels
        if hasattr(self, 'avg_mpg_label'):
            self.avg_mpg_label.setText(f"{stats.get('average_mpg', 0):.1f}")
        if hasattr(self, 'total_cost_label'):
            self.total_cost_label.setText(f"${stats.get('total_cost', 0):.2f}")
        if hasattr(self, 'total_gallons_label'):
            self.total_gallons_label.setText(f"{stats.get('total_gallons', 0):.1f}")
        if hasattr(self, 'cost_per_mile_label'):
            self.cost_per_mile_label.setText(f"${stats.get('cost_per_mile', 0):.3f}")

    except Exception as e:
        logger.error(f"Error updating statistics: {e}")
```

## Phase 1 Verification Checklist

After completing Phase 1, verify:
- [ ] Application launches without errors
- [ ] Fuel Tracking tab opens without crash
- [ ] No `_load_mock_data` calls remain in fuel_tracking_tab.py
- [ ] Adding a fuel entry saves to database
- [ ] Refreshing shows real data from database
- [ ] Statistics update with real calculations

**Test Command**:
```bash
cd "c:\D Drive\Predict"
python -c "from fuel_tracking_tab import FuelTrackingTab; print('Import OK')"
python main_pyside.py
```

---

# PHASE 2: Driving Score Tab - Backend Wiring

**Priority**: HIGH
**Files to Modify**:
- `c:\D Drive\Predict\driving_score_tab.py`
- `c:\D Drive\Predict\driving_score.py` (backend)

## Task 2.1: Verify Backend Exists

**Check** `driving_score.py` has:
- `DrivingScoreAnalyzer` class
- `calculate_score(obd_data)` method
- `get_score_history(profile_id)` method
- `get_behavior_breakdown(profile_id)` method
- `analyze_trip(trip_data)` method

## Task 2.2: Import Backend

**File**: `c:\D Drive\Predict\driving_score_tab.py`

**Add**:
```python
try:
    from driving_score import DrivingScoreAnalyzer, get_driving_analyzer
    DRIVING_ANALYZER_AVAILABLE = True
except ImportError:
    DRIVING_ANALYZER_AVAILABLE = False
    DrivingScoreAnalyzer = None
```

## Task 2.3: Initialize in __init__

```python
def __init__(self, parent=None):
    super().__init__(parent)

    if DRIVING_ANALYZER_AVAILABLE:
        try:
            self.driving_analyzer = get_driving_analyzer()
        except Exception as e:
            logger.warning(f"Could not initialize DrivingScoreAnalyzer: {e}")
            self.driving_analyzer = None
    else:
        self.driving_analyzer = None
```

## Task 2.4: Replace Mock Data

**Find** `_load_mock_data` and replace with:
```python
def _load_driving_data(self):
    """Load real driving score data from backend"""
    try:
        if not self.driving_analyzer:
            self.score_history = []
            self.current_score = 0
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            return

        # Get score history
        self.score_history = self.driving_analyzer.get_score_history(profile_id)

        # Get current score
        if self.score_history:
            self.current_score = self.score_history[-1].get('score', 0)

        # Get behavior breakdown
        self.behavior_breakdown = self.driving_analyzer.get_behavior_breakdown(profile_id)

    except Exception as e:
        logger.error(f"Error loading driving data: {e}")
```

## Task 2.5: Wire Score Calculation

**Find** where the score gauge is updated and connect to real-time OBD data:
```python
def update_with_obd_data(self, obd_data: dict):
    """Update driving score with real-time OBD data"""
    if not self.driving_analyzer:
        return

    try:
        # Calculate real-time score
        score_result = self.driving_analyzer.calculate_score(obd_data)

        # Update gauge
        self.current_score = score_result.get('score', 0)
        self._update_score_gauge(self.current_score)

        # Update behavior indicators
        behaviors = score_result.get('behaviors', {})
        self._update_behavior_indicators(behaviors)

    except Exception as e:
        logger.error(f"Error calculating driving score: {e}")
```

## Task 2.6: Wire Behavior Breakdown Display

```python
def _update_behavior_indicators(self, behaviors: dict):
    """Update behavior breakdown display"""
    # Hard braking indicator
    if hasattr(self, 'hard_braking_label'):
        count = behaviors.get('hard_braking_count', 0)
        self.hard_braking_label.setText(str(count))
        color = '#4CAF50' if count < 3 else '#FFC107' if count < 6 else '#F44336'
        self.hard_braking_label.setStyleSheet(f"color: {color};")

    # Rapid acceleration indicator
    if hasattr(self, 'rapid_accel_label'):
        count = behaviors.get('rapid_acceleration_count', 0)
        self.rapid_accel_label.setText(str(count))

    # Speeding indicator
    if hasattr(self, 'speeding_label'):
        percent = behaviors.get('speeding_percentage', 0)
        self.speeding_label.setText(f"{percent:.1f}%")

    # Idle time indicator
    if hasattr(self, 'idle_time_label'):
        minutes = behaviors.get('idle_time_minutes', 0)
        self.idle_time_label.setText(f"{minutes:.0f} min")
```

## Phase 2 Verification Checklist

- [ ] Application launches without errors
- [ ] Driving Score tab opens without crash
- [ ] Score gauge displays (even if 0)
- [ ] Behavior breakdown shows real categories
- [ ] Score updates when connected to OBD

**Test**:
```bash
python -c "from driving_score_tab import DrivingScoreTab; print('Import OK')"
```

---

# PHASE 3: Geofencing Tab - Backend Wiring

**Priority**: MEDIUM
**Files to Modify**:
- `c:\D Drive\Predict\geofencing_tab.py`
- `c:\D Drive\Predict\geofencing_alerts.py` (backend)

## Task 3.1: Verify Backend

**Check** `geofencing_alerts.py` has:
- `GeofencingManager` class
- `add_zone(name, lat, lon, radius, alert_on_entry, alert_on_exit)` method
- `get_zones(profile_id)` method
- `delete_zone(zone_id)` method
- `check_location(lat, lon)` method
- `get_alert_history(profile_id)` method

## Task 3.2: Import and Initialize

```python
try:
    from geofencing_alerts import GeofencingManager, get_geofencing_manager
    GEOFENCING_AVAILABLE = True
except ImportError:
    GEOFENCING_AVAILABLE = False
    GeofencingManager = None

class GeofencingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        if GEOFENCING_AVAILABLE:
            try:
                self.geofence_manager = get_geofencing_manager()
            except Exception as e:
                logger.warning(f"Could not initialize GeofencingManager: {e}")
                self.geofence_manager = None
        else:
            self.geofence_manager = None
```

## Task 3.3: Replace Mock Data Loading

```python
def _load_zones(self):
    """Load geofence zones from backend"""
    try:
        if not self.geofence_manager:
            self.zones = []
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            self.zones = []
            return

        self.zones = self.geofence_manager.get_zones(profile_id)
        self._update_zones_table()

    except Exception as e:
        logger.error(f"Error loading zones: {e}")
        self.zones = []
```

## Task 3.4: Wire Add Zone

```python
def _add_zone(self):
    """Add new geofence zone"""
    try:
        name = self.zone_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Zone name is required")
            return

        lat = self.latitude_spin.value()
        lon = self.longitude_spin.value()
        radius = self.radius_spin.value()
        alert_entry = self.alert_entry_check.isChecked()
        alert_exit = self.alert_exit_check.isChecked()

        if not self.geofence_manager:
            QMessageBox.warning(self, "Error", "Geofencing system not available")
            return

        profile_id = self._get_current_profile_id()

        success = self.geofence_manager.add_zone(
            profile_id=profile_id,
            name=name,
            latitude=lat,
            longitude=lon,
            radius_meters=radius,
            alert_on_entry=alert_entry,
            alert_on_exit=alert_exit
        )

        if success:
            QMessageBox.information(self, "Success", f"Zone '{name}' added")
            self._load_zones()
            self._clear_form()
        else:
            QMessageBox.warning(self, "Error", "Failed to add zone")

    except Exception as e:
        logger.error(f"Error adding zone: {e}")
        QMessageBox.critical(self, "Error", str(e))
```

## Task 3.5: Wire Delete Zone

```python
def _delete_zone(self):
    """Delete selected zone"""
    selected = self.zones_table.currentRow()
    if selected < 0:
        QMessageBox.warning(self, "Error", "Please select a zone to delete")
        return

    zone = self.zones[selected]
    zone_id = zone.get('id')
    zone_name = zone.get('name', 'Unknown')

    reply = QMessageBox.question(
        self, "Confirm Delete",
        f"Delete zone '{zone_name}'?",
        QMessageBox.Yes | QMessageBox.No
    )

    if reply == QMessageBox.Yes:
        if self.geofence_manager.delete_zone(zone_id):
            self._load_zones()
        else:
            QMessageBox.warning(self, "Error", "Failed to delete zone")
```

## Task 3.6: Wire Alert History

```python
def _load_alert_history(self):
    """Load geofence alert history"""
    try:
        if not self.geofence_manager:
            return

        profile_id = self._get_current_profile_id()
        history = self.geofence_manager.get_alert_history(profile_id, limit=50)

        self.history_table.setRowCount(len(history))
        for row, alert in enumerate(history):
            self.history_table.setItem(row, 0, QTableWidgetItem(alert.get('timestamp', '')))
            self.history_table.setItem(row, 1, QTableWidgetItem(alert.get('zone_name', '')))
            self.history_table.setItem(row, 2, QTableWidgetItem(alert.get('event_type', '')))

    except Exception as e:
        logger.error(f"Error loading alert history: {e}")
```

## Phase 3 Verification Checklist

- [ ] Geofencing tab opens without crash
- [ ] Can add new zones
- [ ] Zones appear in table
- [ ] Can delete zones
- [ ] Alert history loads (may be empty initially)

---

# PHASE 4: Notifications Tab - Backend Wiring

**Priority**: HIGH
**Files to Modify**:
- `c:\D Drive\Predict\notifications_tab.py`
- `c:\D Drive\Predict\alert_notifications.py` (backend)

## Task 4.1: Verify Backend

**Check** `alert_notifications.py` has:
- `AlertNotificationManager` class
- `get_notifications(profile_id, limit, unread_only)` method
- `mark_as_read(notification_id)` method
- `mark_all_read(profile_id)` method
- `delete_notification(notification_id)` method
- `get_notification_preferences(profile_id)` method
- `save_notification_preferences(profile_id, prefs)` method

## Task 4.2: Import and Initialize

```python
try:
    from alert_notifications import AlertNotificationManager, get_notification_manager
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    AlertNotificationManager = None

class NotificationsTab(QWidget):
    def __init__(self, notification_manager=None, parent=None):
        super().__init__(parent)

        if notification_manager:
            self.notification_manager = notification_manager
        elif NOTIFICATIONS_AVAILABLE:
            try:
                self.notification_manager = get_notification_manager()
            except Exception as e:
                logger.warning(f"Could not initialize NotificationManager: {e}")
                self.notification_manager = None
        else:
            self.notification_manager = None
```

## Task 4.3: Replace Mock Notifications

**Find** `_load_mock_notifications` and replace:
```python
def _load_notifications(self):
    """Load real notifications from backend"""
    try:
        if not self.notification_manager:
            self.notifications = []
            self._update_notifications_display()
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            self.notifications = []
            return

        # Get filter settings
        unread_only = self.unread_filter_check.isChecked() if hasattr(self, 'unread_filter_check') else False
        category = self.category_filter_combo.currentText() if hasattr(self, 'category_filter_combo') else 'All'

        # Load from backend
        self.notifications = self.notification_manager.get_notifications(
            profile_id=profile_id,
            limit=100,
            unread_only=unread_only,
            category=None if category == 'All' else category
        )

        self._update_notifications_display()
        self._update_unread_count()

    except Exception as e:
        logger.error(f"Error loading notifications: {e}")
        self.notifications = []
```

## Task 4.4: Wire Mark as Read

```python
def _mark_notification_read(self, notification_id: int):
    """Mark a notification as read"""
    try:
        if not self.notification_manager:
            return

        success = self.notification_manager.mark_as_read(notification_id)
        if success:
            self._load_notifications()
    except Exception as e:
        logger.error(f"Error marking notification read: {e}")

def _mark_all_read(self):
    """Mark all notifications as read"""
    try:
        if not self.notification_manager:
            return

        profile_id = self._get_current_profile_id()
        success = self.notification_manager.mark_all_read(profile_id)
        if success:
            self._load_notifications()
            QMessageBox.information(self, "Success", "All notifications marked as read")
    except Exception as e:
        logger.error(f"Error marking all read: {e}")
```

## Task 4.5: Wire Preferences

```python
def _load_preferences(self):
    """Load notification preferences"""
    try:
        if not self.notification_manager:
            return

        profile_id = self._get_current_profile_id()
        prefs = self.notification_manager.get_notification_preferences(profile_id)

        # Update UI checkboxes
        if hasattr(self, 'email_check'):
            self.email_check.setChecked(prefs.get('email_enabled', False))
        if hasattr(self, 'push_check'):
            self.push_check.setChecked(prefs.get('push_enabled', True))
        if hasattr(self, 'sms_check'):
            self.sms_check.setChecked(prefs.get('sms_enabled', False))
        if hasattr(self, 'in_app_check'):
            self.in_app_check.setChecked(prefs.get('in_app_enabled', True))

    except Exception as e:
        logger.error(f"Error loading preferences: {e}")

def _save_preferences(self):
    """Save notification preferences"""
    try:
        if not self.notification_manager:
            QMessageBox.warning(self, "Error", "Notification system not available")
            return

        profile_id = self._get_current_profile_id()

        prefs = {
            'email_enabled': self.email_check.isChecked() if hasattr(self, 'email_check') else False,
            'push_enabled': self.push_check.isChecked() if hasattr(self, 'push_check') else True,
            'sms_enabled': self.sms_check.isChecked() if hasattr(self, 'sms_check') else False,
            'in_app_enabled': self.in_app_check.isChecked() if hasattr(self, 'in_app_check') else True,
        }

        success = self.notification_manager.save_notification_preferences(profile_id, prefs)

        if success:
            QMessageBox.information(self, "Success", "Preferences saved")
        else:
            QMessageBox.warning(self, "Error", "Failed to save preferences")

    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        QMessageBox.critical(self, "Error", str(e))
```

## Phase 4 Verification Checklist

- [ ] Notifications tab opens
- [ ] Real notifications load (may be empty)
- [ ] Mark as read works
- [ ] Mark all read works
- [ ] Preferences save/load works
- [ ] Filter by category works
- [ ] Filter by unread works

---

# PHASE 5: Maintenance Reminders Tab - Backend Wiring

**Priority**: MEDIUM
**Files to Modify**:
- `c:\D Drive\Predict\maintenance_reminders_tab.py`
- `c:\D Drive\Predict\maintenance_predictor.py` (backend)

## Task 5.1: Import and Initialize

```python
try:
    from maintenance_predictor import MaintenancePredictor, get_maintenance_predictor
    MAINTENANCE_AVAILABLE = True
except ImportError:
    MAINTENANCE_AVAILABLE = False

class MaintenanceRemindersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        if MAINTENANCE_AVAILABLE:
            try:
                self.maintenance_predictor = get_maintenance_predictor()
            except:
                self.maintenance_predictor = None
        else:
            self.maintenance_predictor = None
```

## Task 5.2: Wire Reminder Loading

```python
def _load_reminders(self):
    """Load maintenance reminders from backend"""
    try:
        if not self.maintenance_predictor:
            self.reminders = []
            return

        profile_id = self._get_current_profile_id()
        if not profile_id:
            return

        # Get upcoming maintenance
        self.reminders = self.maintenance_predictor.get_upcoming_maintenance(
            profile_id=profile_id,
            days_ahead=90
        )

        # Get AI predictions
        self.predictions = self.maintenance_predictor.get_predicted_maintenance(
            profile_id=profile_id
        )

        self._update_reminders_display()

    except Exception as e:
        logger.error(f"Error loading reminders: {e}")
```

## Task 5.3: Wire Add Reminder

```python
def _add_reminder(self):
    """Add new maintenance reminder"""
    try:
        if not self.maintenance_predictor:
            QMessageBox.warning(self, "Error", "Maintenance system not available")
            return

        service_type = self.service_type_combo.currentText()
        due_date = self.due_date_edit.date().toPython()
        due_mileage = self.due_mileage_spin.value()
        notes = self.notes_edit.text()

        profile_id = self._get_current_profile_id()

        success = self.maintenance_predictor.add_reminder(
            profile_id=profile_id,
            service_type=service_type,
            due_date=due_date,
            due_mileage=due_mileage,
            notes=notes
        )

        if success:
            QMessageBox.information(self, "Success", "Reminder added")
            self._load_reminders()
            self._clear_form()

    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
```

## Phase 5 Verification Checklist

- [ ] Maintenance tab opens
- [ ] Reminders load from database
- [ ] Can add new reminder
- [ ] Can mark reminder complete
- [ ] AI predictions display (if available)

---

# PHASE 6: Recall Alerts Tab - Backend Wiring

**Priority**: MEDIUM
**Files to Modify**:
- `c:\D Drive\Predict\recall_alerts_tab.py`
- `c:\D Drive\Predict\nhtsa_recall_api.py` (backend)

## Task 6.1: Import and Initialize

```python
try:
    from nhtsa_recall_api import RecallChecker, get_recall_checker
    RECALL_CHECKER_AVAILABLE = True
except ImportError:
    RECALL_CHECKER_AVAILABLE = False

class RecallAlertsTab(QWidget):
    def __init__(self, recall_system=None, parent=None):
        super().__init__(parent)

        if recall_system:
            self.recall_checker = recall_system
        elif RECALL_CHECKER_AVAILABLE:
            try:
                self.recall_checker = get_recall_checker()
            except:
                self.recall_checker = None
        else:
            self.recall_checker = None
```

## Task 6.2: Wire Recall Check

```python
def _check_recalls(self):
    """Check for recalls for current vehicle"""
    try:
        if not self.recall_checker:
            QMessageBox.warning(self, "Error", "Recall system not available")
            return

        profile = self._get_current_profile()
        if not profile:
            QMessageBox.warning(self, "Error", "No vehicle profile selected")
            return

        make = profile.get('make', '')
        model = profile.get('model', '')
        year = profile.get('year', 0)

        if not all([make, model, year]):
            QMessageBox.warning(self, "Error", "Vehicle make, model, and year required")
            return

        # Show loading indicator
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking...")

        # Call NHTSA API
        recalls = self.recall_checker.check_recalls(
            make=make,
            model=model,
            year=year
        )

        self.recalls = recalls
        self._update_recalls_display()

        if recalls:
            QMessageBox.information(
                self, "Recalls Found",
                f"Found {len(recalls)} recall(s) for your vehicle"
            )
        else:
            QMessageBox.information(
                self, "No Recalls",
                "No active recalls found for your vehicle"
            )

    except Exception as e:
        logger.error(f"Error checking recalls: {e}")
        QMessageBox.critical(self, "Error", f"Failed to check recalls: {e}")
    finally:
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for Recalls")
```

## Phase 6 Verification Checklist

- [ ] Recall Alerts tab opens
- [ ] Check button triggers NHTSA API call
- [ ] Results display in table
- [ ] Error handling for API failures

---

# PHASE 7: AI Module Fixes - Remove Mock Returns

**Priority**: HIGH
**Files to Modify**:
- `c:\D Drive\Predict\ai_auto_retraining.py`
- `c:\D Drive\Predict\ai_prediction_integrity.py`

## Task 7.1: Fix ai_auto_retraining.py

**Find** line ~972 where it says "For now, return mock data structure"

**Replace mock return with actual implementation** or proper error handling:
```python
# Instead of returning mock data, either:
# Option A: Return actual computed results
# Option B: Raise an exception if data unavailable
# Option C: Return None and handle in caller

def _compute_retraining_metrics(self, ...):
    """Compute actual retraining metrics"""
    try:
        # Actual implementation
        metrics = {
            'accuracy': self._calculate_accuracy(),
            'loss': self._calculate_loss(),
            'samples_used': len(self.training_data),
            'timestamp': datetime.now().isoformat()
        }
        return metrics
    except Exception as e:
        logger.error(f"Failed to compute metrics: {e}")
        return None  # Caller should handle None
```

**Find** line ~1010 with another mock return and fix similarly.

## Task 7.2: Fix ai_prediction_integrity.py

**Find** line ~123 with "placeholder - replace with actual AI model call"

**Replace with actual model call**:
```python
def _validate_prediction(self, prediction_data: dict) -> dict:
    """Validate prediction using actual AI model"""
    try:
        # Get the prediction engine
        if not hasattr(self, 'prediction_engine') or not self.prediction_engine:
            from enhanced_prediction_engine import get_prediction_engine
            self.prediction_engine = get_prediction_engine()

        # Run actual validation
        validation_result = self.prediction_engine.validate_prediction(
            prediction=prediction_data.get('prediction'),
            confidence=prediction_data.get('confidence'),
            features=prediction_data.get('features')
        )

        return {
            'valid': validation_result.get('is_valid', False),
            'confidence_score': validation_result.get('confidence', 0),
            'issues': validation_result.get('issues', [])
        }

    except Exception as e:
        logger.error(f"Prediction validation failed: {e}")
        return {
            'valid': False,
            'confidence_score': 0,
            'issues': [str(e)]
        }
```

## Phase 7 Verification Checklist

- [ ] No "mock" or "placeholder" comments remain in modified functions
- [ ] AI retraining returns real metrics
- [ ] Prediction validation uses actual model
- [ ] Application still launches without errors

---

# PHASE 8: Devices Tab - Backend Wiring

**Priority**: MEDIUM
**Files to Modify**:
- `c:\D Drive\Predict\devices_tab.py`

## Task 8.1: Wire to HeartbeatManager

The `devices_tab.py` should connect to the heartbeat manager for real device status.

**Find** `_load_mock_data` (around line 840) and replace:
```python
def _load_devices(self):
    """Load real device data from heartbeat manager"""
    try:
        self.devices = []

        if self.heartbeat_manager:
            # Get connected devices from heartbeat manager
            connected = self.heartbeat_manager.get_connected_devices()
            for device_id, device_info in connected.items():
                self.devices.append({
                    'id': device_id,
                    'type': device_info.get('type', 'Unknown'),
                    'profile': device_info.get('profile_name', '-'),
                    'status': 'Online' if device_info.get('is_alive', False) else 'Offline',
                    'last_seen': device_info.get('last_heartbeat', '-'),
                    'signal': device_info.get('signal_strength', 0),
                    'battery': device_info.get('battery_level', 100),
                })

        self._update_devices_table()
        self._update_statistics()

    except Exception as e:
        logger.error(f"Error loading devices: {e}")
        self.devices = []
```

## Phase 8 Verification Checklist

- [ ] Devices tab shows real connected devices
- [ ] Device status updates correctly
- [ ] Statistics reflect actual device count

---

# PHASE 9: ESP32 Sensors Tab - Graceful Degradation

**Priority**: LOW
**Files to Modify**:
- `c:\D Drive\Predict\esp32_sensors_tab.py`

## Task 9.1: Improve ESP32 Connection Handling

**Update** the tab to clearly show when ESP32 is not connected:
```python
def _check_esp32_connection(self):
    """Check ESP32 sensor connection status"""
    try:
        if hasattr(self, 'sensor_manager') and self.sensor_manager:
            connected = self.sensor_manager.is_connected()
            if connected:
                self.status_label.setText("ESP32 Connected")
                self.status_label.setStyleSheet("color: #4CAF50;")
                return True

        self.status_label.setText("ESP32 Not Connected - Optional Enhancement")
        self.status_label.setStyleSheet("color: #FFC107;")
        return False

    except Exception as e:
        self.status_label.setText(f"ESP32 Error: {e}")
        self.status_label.setStyleSheet("color: #F44336;")
        return False
```

## Phase 9 Verification Checklist

- [ ] ESP32 tab opens without crash
- [ ] Shows clear message when ESP32 not connected
- [ ] Does not show fake/mock sensor readings

---

# PHASE 10: Integration Testing & Final Verification

**Priority**: CRITICAL
**This phase is for the human reviewer (you) after GLM4.7 completes Phases 1-9**

## Task 10.1: Full Application Test

```bash
cd "c:\D Drive\Predict"

# Test syntax of all modified files
python -m py_compile fuel_tracking_tab.py
python -m py_compile driving_score_tab.py
python -m py_compile geofencing_tab.py
python -m py_compile notifications_tab.py
python -m py_compile maintenance_reminders_tab.py
python -m py_compile recall_alerts_tab.py
python -m py_compile devices_tab.py
python -m py_compile esp32_sensors_tab.py
python -m py_compile ai_auto_retraining.py
python -m py_compile ai_prediction_integrity.py

# If all pass, run the application
python main_pyside.py
```

## Task 10.2: Tab-by-Tab Verification

1. **Fuel Tracking Tab**
   - Open tab
   - Add a fuel entry
   - Verify it appears in table
   - Check statistics update

2. **Driving Score Tab**
   - Open tab
   - Verify score gauge displays
   - If OBD connected, verify real-time updates

3. **Geofencing Tab**
   - Open tab
   - Add a zone
   - Verify it appears in table
   - Delete the zone

4. **Notifications Tab**
   - Open tab
   - Check if any notifications load
   - Test mark as read
   - Save preferences

5. **Maintenance Reminders Tab**
   - Open tab
   - Add a reminder
   - Verify it appears

6. **Recall Alerts Tab**
   - Open tab
   - Click check for recalls (needs vehicle profile)

7. **Devices Tab**
   - Open tab
   - Verify real device list (or empty if none connected)

8. **ESP32 Tab**
   - Open tab
   - Verify shows "not connected" message (unless ESP32 hardware present)

## Task 10.3: Search for Remaining Mock Data

```bash
# Search for remaining mock data calls
grep -r "_load_mock" "c:\D Drive\Predict\*.py"
grep -r "mock_data" "c:\D Drive\Predict\*.py"
grep -r "placeholder" "c:\D Drive\Predict\*.py"
```

**Expected Result**: No results in the modified tabs.

---

# SUMMARY CHECKLIST

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Fuel Tracking Tab Wiring | ⬜ Pending |
| 2 | Driving Score Tab Wiring | ⬜ Pending |
| 3 | Geofencing Tab Wiring | ⬜ Pending |
| 4 | Notifications Tab Wiring | ⬜ Pending |
| 5 | Maintenance Reminders Tab Wiring | ⬜ Pending |
| 6 | Recall Alerts Tab Wiring | ⬜ Pending |
| 7 | AI Module Mock Fixes | ⬜ Pending |
| 8 | Devices Tab Wiring | ⬜ Pending |
| 9 | ESP32 Graceful Degradation | ⬜ Pending |
| 10 | Final Integration Testing | ⬜ Pending |

---

# NOTES FOR GLM4.7

1. **Always check if the backend file exists before wiring** - Some backends may need to be created first.

2. **Preserve existing UI code** - Only modify the data loading and action methods, not the UI layout code.

3. **Add proper error handling** - Every database/API call should be wrapped in try/except.

4. **Use logging** - Add `logger.info()` and `logger.error()` calls for debugging.

5. **Test after each phase** - Don't proceed to next phase until current phase works.

6. **Profile ID handling** - Most tabs need to get the current profile ID. Use the `_get_current_profile_id()` pattern shown above.

7. **Signal the user** - After completing each phase, tell the user so they can verify before proceeding.

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 2: PREVILIUM SERVER (Phases 11-13)
# Location: C:\OBDserver\Previlium_OBD_Server
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 11: Server - Verify Core Endpoints

**Priority**: HIGH (after Desktop complete)
**Location**: `C:\OBDserver\Previlium_OBD_Server`

## Task 11.1: Verify Server Starts

```bash
cd "C:\OBDserver\Previlium_OBD_Server"
python main.py
```

**Expected**: Server starts on port 8000 without errors.

## Task 11.2: Test Profile Endpoints

Using curl, Postman, or Python:

```python
import requests

BASE_URL = "http://localhost:8000"

# Test profile list
response = requests.get(f"{BASE_URL}/api/profile/list")
print(f"Profile list: {response.status_code}")

# Test profile creation
profile_data = {
    "name": "Test Vehicle",
    "make": "Toyota",
    "model": "Camry",
    "year": 2022,
    "vin": "TEST123456789"
}
response = requests.post(f"{BASE_URL}/api/profile/create", json=profile_data)
print(f"Profile create: {response.status_code}")
```

## Task 11.3: Test OBD Data Endpoints

```python
# Submit vehicle data
vehicle_data = {
    "profile_id": 1,
    "rpm": 2500,
    "speed": 65,
    "coolant_temp": 195,
    "engine_load": 45,
    "voltage": 14.2,
    "timestamp": "2026-01-11T12:00:00"
}
response = requests.post(
    f"{BASE_URL}/api/vehicle_data",
    json=vehicle_data,
    headers={"X-API-Key": "your-api-key"}
)
print(f"Vehicle data submit: {response.status_code}")

# Get latest data
response = requests.get(f"{BASE_URL}/api/vehicle_data/latest/1")
print(f"Latest data: {response.status_code}")
```

## Task 11.4: Test DTC Endpoints

```python
# Submit DTC
dtc_data = {
    "profile_id": 1,
    "codes": ["P0301", "P0420"],
    "timestamp": "2026-01-11T12:00:00"
}
response = requests.post(f"{BASE_URL}/api/dtc/submit/1", json=dtc_data)
print(f"DTC submit: {response.status_code}")

# Get active DTCs
response = requests.get(f"{BASE_URL}/api/dtc/active/1")
print(f"Active DTCs: {response.status_code}")
```

## Phase 11 Verification Checklist

- [ ] Server starts on port 8000
- [ ] GET /api/profile/list returns 200
- [ ] POST /api/profile/create works
- [ ] POST /api/vehicle_data works with API key
- [ ] GET /api/vehicle_data/latest/{id} works
- [ ] POST /api/dtc/submit works
- [ ] GET /api/dtc/active works

---

# PHASE 12: Server - Guardian System (Teen Monitoring)

**Priority**: MEDIUM
**Files**:
- `C:\OBDserver\Previlium_OBD_Server\guardian_api.py`
- `C:\OBDserver\Previlium_OBD_Server\driver_geofence_api.py`

## Task 12.1: Verify Guardian Endpoints Exist

**Check** `guardian_api.py` for these endpoints:
- `POST /api/guardian/register` - Register guardian relationship
- `GET /api/guardian/status/{teen_id}` - Get teen's current status
- `POST /api/guardian/alert` - Send alert to guardian
- `GET /api/guardian/history/{teen_id}` - Get driving history
- `POST /api/guardian/geofence` - Create geofence zone
- `POST /api/guardian/sos` - Emergency SOS handling

## Task 12.2: Test Guardian Registration

```python
# Register guardian relationship
guardian_data = {
    "guardian_profile_id": 1,  # Parent profile
    "teen_profile_id": 2,      # Teen's profile
    "relationship": "parent",
    "notifications_enabled": True,
    "speed_limit": 70,
    "curfew_start": "22:00",
    "curfew_end": "06:00"
}
response = requests.post(f"{BASE_URL}/api/guardian/register", json=guardian_data)
print(f"Guardian register: {response.status_code}")
```

## Task 12.3: Test Geofencing for Guardians

```python
# Create geofence for teen
geofence_data = {
    "teen_profile_id": 2,
    "name": "School Zone",
    "latitude": 25.2854,
    "longitude": 51.5310,
    "radius_meters": 500,
    "alert_on_exit": True,
    "alert_on_entry": False,
    "active_hours": {
        "start": "07:00",
        "end": "15:00"
    }
}
response = requests.post(f"{BASE_URL}/api/guardian/geofence", json=geofence_data)
print(f"Geofence create: {response.status_code}")
```

## Task 12.4: Test Alert Generation

```python
# Simulate speeding alert
alert_data = {
    "teen_profile_id": 2,
    "alert_type": "speeding",
    "details": {
        "current_speed": 85,
        "speed_limit": 70,
        "location": {"lat": 25.2854, "lon": 51.5310}
    }
}
response = requests.post(f"{BASE_URL}/api/guardian/alert", json=alert_data)
print(f"Alert sent: {response.status_code}")
```

## Task 12.5: Verify Emergency SOS

```python
# Test SOS endpoint
sos_data = {
    "teen_profile_id": 2,
    "location": {"lat": 25.2854, "lon": 51.5310},
    "timestamp": "2026-01-11T12:00:00"
}
response = requests.post(f"{BASE_URL}/api/guardian/sos", json=sos_data)
print(f"SOS: {response.status_code}")
```

## Phase 12 Verification Checklist

- [ ] Guardian registration works
- [ ] Geofence creation works
- [ ] Speeding alerts generate correctly
- [ ] Hard braking alerts work
- [ ] SOS endpoint responds
- [ ] Alert history retrieval works

---

# PHASE 13: Server - WebSocket Real-Time Streaming

**Priority**: HIGH
**File**: `C:\OBDserver\Previlium_OBD_Server\main.py`

## Task 13.1: Verify WebSocket Endpoint Exists

**Check** `main.py` for WebSocket implementation:
```python
# Look for something like:
@app.websocket("/ws/live/{profile_id}")
async def websocket_endpoint(websocket: WebSocket, profile_id: int):
    await websocket.accept()
    # ...
```

## Task 13.2: Test WebSocket Connection

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/live/1"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")

        # Listen for data
        for i in range(10):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received: {data}")

asyncio.run(test_websocket())
```

## Task 13.3: If WebSocket Missing, Add It

**Add to** `main.py`:
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List

# Active WebSocket connections
active_connections: Dict[int, List[WebSocket]] = {}

@app.websocket("/ws/live/{profile_id}")
async def websocket_live_data(websocket: WebSocket, profile_id: int):
    """WebSocket endpoint for real-time vehicle data"""
    await websocket.accept()

    # Add to active connections
    if profile_id not in active_connections:
        active_connections[profile_id] = []
    active_connections[profile_id].append(websocket)

    try:
        while True:
            # Get latest data for this profile
            data = get_latest_vehicle_data(profile_id)
            if data:
                await websocket.send_json(data)
            await asyncio.sleep(1)  # Send every 1 second
    except WebSocketDisconnect:
        active_connections[profile_id].remove(websocket)
```

## Phase 13 Verification Checklist

- [ ] WebSocket endpoint exists at /ws/live/{profile_id}
- [ ] Can connect to WebSocket
- [ ] Receives real-time data
- [ ] Connection handles disconnects gracefully

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 3: ANDROID APP - PredictOBD (Phases 14-15)
# Location: C:\Predict\PredictOBD
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 14: Android App - Server Connection Verification

**Priority**: HIGH (after Server verified)
**Location**: `C:\Predict\PredictOBD`

## Task 14.1: Verify API Configuration

**File**: `app/src/main/java/com/omar/predictobd/data/api/ApiService.kt` (or similar)

**Check**:
```kotlin
// Should point to Previlium server
const val BASE_URL = "http://YOUR_SERVER_IP:8000/"

// API Key header
const val API_KEY_HEADER = "X-API-Key"
```

## Task 14.2: Update Server URL

If using local network:
```kotlin
const val BASE_URL = "http://192.168.1.XXX:8000/"  // Your PC's local IP
```

If using Cloudflare tunnel:
```kotlin
const val BASE_URL = "https://your-tunnel.trycloudflare.com/"
```

## Task 14.3: Verify Retrofit/HTTP Client Setup

**Check** for proper HTTP client configuration:
```kotlin
// OkHttpClient with API key interceptor
val client = OkHttpClient.Builder()
    .addInterceptor { chain ->
        val request = chain.request().newBuilder()
            .addHeader("X-API-Key", apiKey)
            .build()
        chain.proceed(request)
    }
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(30, TimeUnit.SECONDS)
    .build()
```

## Task 14.4: Test Connection from App

1. Build and install app on device:
```bash
cd "C:\Predict\PredictOBD"
.\gradlew assembleDebug
```

2. Install APK on phone
3. Open app and check if it can:
   - Fetch profile list
   - Display connection status

## Phase 14 Verification Checklist

- [ ] App builds without errors
- [ ] APK installs on device
- [ ] App connects to Previlium server
- [ ] Profile list loads
- [ ] API key authentication works

---

# PHASE 15: Android App - OBD Data Flow

**Priority**: HIGH
**Goal**: Verify OBD data flows from app to server to desktop

## Task 15.1: Bluetooth OBD Connection

**Verify** the app can:
1. Discover Bluetooth OBD adapters
2. Connect to adapter
3. Read OBD data (RPM, Speed, etc.)

## Task 15.2: Data Upload to Server

**Check** that data is being posted:
```kotlin
// Should be sending data like:
data class VehicleDataRequest(
    val profile_id: Int,
    val rpm: Int,
    val speed: Int,
    val coolant_temp: Int,
    val engine_load: Int,
    val voltage: Double,
    val timestamp: String
)

suspend fun submitVehicleData(data: VehicleDataRequest): Response<Unit>
```

## Task 15.3: Verify Data Appears on Server

1. Connect OBD adapter to phone
2. Start data collection in app
3. Check server logs for incoming data
4. Check database for stored records

```bash
# On server, check database
cd "C:\OBDserver\Previlium_OBD_Server"
sqlite3 obd_data.db "SELECT * FROM vehicle_data ORDER BY id DESC LIMIT 5;"
```

## Task 15.4: Verify Desktop Receives Data

1. Open Desktop PREDICT app
2. Go to Live Data tab
3. Check if data from mobile appears

## Phase 15 Verification Checklist

- [ ] App connects to OBD adapter
- [ ] App reads OBD data correctly
- [ ] Data is sent to server
- [ ] Server stores data in database
- [ ] Desktop app can view mobile data

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 4: PREDICT GUARDIAN ANDROID APP (Phases 16-18)
# Location: C:\Predict guradian
# Parent/Fleet Manager Monitoring Application
# ═══════════════════════════════════════════════════════════════════════

---

## Predict Guardian App Overview

**What It Is**: A standalone Android application for parents and fleet managers to remotely monitor drivers (teens, employees) in real-time.

**Tech Stack**:
- Kotlin with Jetpack Compose (UI)
- MVVM + Clean Architecture
- Retrofit + OkHttp (Networking)
- Room Database (Local Cache)
- WebSocket (Real-time Updates)
- Firebase Cloud Messaging (Push Notifications)
- Hilt (Dependency Injection)

**Current State**: ~90% Complete

**What's Complete**:
- ✅ Authentication (Login/Register with Qatar phone validation)
- ✅ Multi-vehicle Dashboard with real-time updates
- ✅ Vehicle Health Monitoring (DTC codes, battery, maintenance)
- ✅ Trip History and Analysis
- ✅ Driving Analytics with trends
- ✅ Speed Records tracking
- ✅ AI Predictions display (bilingual: English/Arabic)
- ✅ Emergency Location Requests
- ✅ Guardian Commands (warnings/messages to driver)
- ✅ PDF Report Generation
- ✅ Advanced Settings
- ✅ Real-time WebSocket integration
- ✅ Push Notification system (6 channels)
- ✅ Bilingual UI (English/Arabic with RTL support)
- ✅ Security (encryption, HTTPS, ProGuard)
- ✅ FREE Speed Limit Detection (saves $360k/year vs Google Maps)

**What's Missing** (Phases 16-18):

```
┌─────────────────────────────────────────────────────────────┐
│  PREDICT GUARDIAN - MISSING FEATURES                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 16: Geofencing Map UI                                │
│  ├── Backend API: ✅ Ready (Geofence.kt model complete)     │
│  ├── Map Integration: ❌ Need Google Maps Compose           │
│  └── UI Screen: ❌ Missing geofence creation/editing        │
│                                                             │
│  Phase 17: AI Chat Screen                                   │
│  ├── Backend API: ✅ Ready                                  │
│  └── Chat UI: ❌ Missing Compose chat interface             │
│                                                             │
│  Phase 18: Driver Analytics & Polish                        │
│  ├── Driver Photo: ⚠️ Placeholder (needs AsyncImage)        │
│  ├── Driver Analytics: ⚠️ Basic (needs comparison UI)       │
│  ├── Dark Mode: ⚠️ Infrastructure ready, not wired          │
│  └── Biometric Auth: ❌ Not implemented                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

# PHASE 16: Geofencing Map UI Implementation

**Priority**: HIGH
**Location**: `C:\Predict guradian\app\src\main\java\com\predict\guardian\`
**Goal**: Create interactive map-based geofence management screen

## Task 16.1: Add Google Maps Compose Dependency

**File**: `C:\Predict guradian\app\build.gradle.kts`

**Add to dependencies**:
```kotlin
// Google Maps for Compose
implementation("com.google.maps.android:maps-compose:4.3.0")
implementation("com.google.android.gms:play-services-maps:18.2.0")
implementation("com.google.android.gms:play-services-location:21.1.0")
```

**Add to AndroidManifest.xml**:
```xml
<meta-data
    android:name="com.google.android.geo.API_KEY"
    android:value="${MAPS_API_KEY}" />
```

**Add to local.properties** (don't commit to git):
```properties
MAPS_API_KEY=your_google_maps_api_key_here
```

## Task 16.2: Create GeofencingScreen Composable

**Create file**: `ui/screen/geofencing/GeofencingScreen.kt`

```kotlin
package com.predict.guardian.ui.screen.geofencing

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.*
import com.predict.guardian.data.model.Geofence

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GeofencingScreen(
    profileId: Int,
    onNavigateBack: () -> Unit,
    viewModel: GeofencingViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val geofences by viewModel.geofences.collectAsState()

    // Default to Qatar location
    val defaultLocation = LatLng(25.2854, 51.5310)
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(defaultLocation, 12f)
    }

    var showAddDialog by remember { mutableStateOf(false) }
    var selectedLocation by remember { mutableStateOf<LatLng?>(null) }

    LaunchedEffect(profileId) {
        viewModel.loadGeofences(profileId)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Geofence Zones") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { showAddDialog = true }) {
                        Icon(Icons.Default.Add, "Add Zone")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            GoogleMap(
                modifier = Modifier.fillMaxSize(),
                cameraPositionState = cameraPositionState,
                onMapLongClick = { latLng ->
                    selectedLocation = latLng
                    showAddDialog = true
                }
            ) {
                // Draw existing geofences as circles
                geofences.forEach { geofence ->
                    Circle(
                        center = LatLng(geofence.latitude, geofence.longitude),
                        radius = geofence.radiusMeters.toDouble(),
                        fillColor = when {
                            geofence.alertOnExit -> Color(0x4400FF00) // Green for exit alerts
                            geofence.alertOnEntry -> Color(0x44FF0000) // Red for entry alerts
                            else -> Color(0x440000FF) // Blue default
                        },
                        strokeColor = Color.DarkGray,
                        strokeWidth = 2f
                    )
                    Marker(
                        state = MarkerState(position = LatLng(geofence.latitude, geofence.longitude)),
                        title = geofence.name,
                        snippet = "Radius: ${geofence.radiusMeters}m"
                    )
                }
            }

            // Loading indicator
            if (uiState is UiState.Loading) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }
    }

    // Add Geofence Dialog
    if (showAddDialog) {
        AddGeofenceDialog(
            initialLocation = selectedLocation,
            onDismiss = {
                showAddDialog = false
                selectedLocation = null
            },
            onConfirm = { name, lat, lon, radius, alertEntry, alertExit ->
                viewModel.addGeofence(
                    profileId = profileId,
                    name = name,
                    latitude = lat,
                    longitude = lon,
                    radiusMeters = radius,
                    alertOnEntry = alertEntry,
                    alertOnExit = alertExit
                )
                showAddDialog = false
                selectedLocation = null
            }
        )
    }
}

@Composable
fun AddGeofenceDialog(
    initialLocation: LatLng?,
    onDismiss: () -> Unit,
    onConfirm: (String, Double, Double, Int, Boolean, Boolean) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var latitude by remember { mutableStateOf(initialLocation?.latitude?.toString() ?: "") }
    var longitude by remember { mutableStateOf(initialLocation?.longitude?.toString() ?: "") }
    var radius by remember { mutableStateOf("500") }
    var alertOnEntry by remember { mutableStateOf(false) }
    var alertOnExit by remember { mutableStateOf(true) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Geofence Zone") },
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Zone Name") },
                    placeholder = { Text("e.g., Home, School, Work") }
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = latitude,
                        onValueChange = { latitude = it },
                        label = { Text("Latitude") },
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = longitude,
                        onValueChange = { longitude = it },
                        label = { Text("Longitude") },
                        modifier = Modifier.weight(1f)
                    )
                }
                OutlinedTextField(
                    value = radius,
                    onValueChange = { radius = it },
                    label = { Text("Radius (meters)") },
                    placeholder = { Text("500") }
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = alertOnEntry, onCheckedChange = { alertOnEntry = it })
                    Text("Alert on Entry")
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = alertOnExit, onCheckedChange = { alertOnExit = it })
                    Text("Alert on Exit")
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onConfirm(
                        name,
                        latitude.toDoubleOrNull() ?: 0.0,
                        longitude.toDoubleOrNull() ?: 0.0,
                        radius.toIntOrNull() ?: 500,
                        alertOnEntry,
                        alertOnExit
                    )
                },
                enabled = name.isNotBlank() && latitude.isNotBlank() && longitude.isNotBlank()
            ) {
                Text("Add")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
```

## Task 16.3: Create GeofencingViewModel

**Create file**: `ui/screen/geofencing/GeofencingViewModel.kt`

```kotlin
package com.predict.guardian.ui.screen.geofencing

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.predict.guardian.data.model.Geofence
import com.predict.guardian.data.repository.GeofenceRepository
import com.predict.guardian.utils.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class GeofencingViewModel @Inject constructor(
    private val repository: GeofenceRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<UiState<Unit>>(UiState.Idle)
    val uiState: StateFlow<UiState<Unit>> = _uiState.asStateFlow()

    private val _geofences = MutableStateFlow<List<Geofence>>(emptyList())
    val geofences: StateFlow<List<Geofence>> = _geofences.asStateFlow()

    fun loadGeofences(profileId: Int) {
        viewModelScope.launch {
            _uiState.value = UiState.Loading
            repository.getGeofences(profileId)
                .onSuccess { _geofences.value = it }
                .onFailure { _uiState.value = UiState.Error(it.message ?: "Failed to load geofences") }
            _uiState.value = UiState.Idle
        }
    }

    fun addGeofence(
        profileId: Int,
        name: String,
        latitude: Double,
        longitude: Double,
        radiusMeters: Int,
        alertOnEntry: Boolean,
        alertOnExit: Boolean
    ) {
        viewModelScope.launch {
            _uiState.value = UiState.Loading
            repository.createGeofence(
                profileId = profileId,
                name = name,
                latitude = latitude,
                longitude = longitude,
                radiusMeters = radiusMeters,
                alertOnEntry = alertOnEntry,
                alertOnExit = alertOnExit
            ).onSuccess {
                loadGeofences(profileId) // Refresh list
            }.onFailure {
                _uiState.value = UiState.Error(it.message ?: "Failed to create geofence")
            }
        }
    }

    fun deleteGeofence(geofenceId: Int, profileId: Int) {
        viewModelScope.launch {
            repository.deleteGeofence(geofenceId)
                .onSuccess { loadGeofences(profileId) }
                .onFailure { _uiState.value = UiState.Error(it.message ?: "Failed to delete") }
        }
    }
}
```

## Task 16.4: Create GeofenceRepository

**Create file**: `data/repository/GeofenceRepository.kt`

```kotlin
package com.predict.guardian.data.repository

import com.predict.guardian.data.api.ApiService
import com.predict.guardian.data.model.Geofence
import com.predict.guardian.data.model.CreateGeofenceRequest
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GeofenceRepository @Inject constructor(
    private val apiService: ApiService
) {
    suspend fun getGeofences(profileId: Int): Result<List<Geofence>> {
        return try {
            val response = apiService.getGeofences(profileId)
            if (response.isSuccessful) {
                Result.success(response.body() ?: emptyList())
            } else {
                Result.failure(Exception("Failed to fetch geofences"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createGeofence(
        profileId: Int,
        name: String,
        latitude: Double,
        longitude: Double,
        radiusMeters: Int,
        alertOnEntry: Boolean,
        alertOnExit: Boolean
    ): Result<Geofence> {
        return try {
            val request = CreateGeofenceRequest(
                profileId = profileId,
                name = name,
                latitude = latitude,
                longitude = longitude,
                radiusMeters = radiusMeters,
                alertOnEntry = alertOnEntry,
                alertOnExit = alertOnExit
            )
            val response = apiService.createGeofence(request)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to create geofence"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteGeofence(geofenceId: Int): Result<Unit> {
        return try {
            val response = apiService.deleteGeofence(geofenceId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to delete geofence"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
```

## Task 16.5: Add API Endpoints to ApiService

**File**: `data/api/ApiService.kt`

**Add these endpoints**:
```kotlin
// Geofencing endpoints
@GET("api/geofences/{profile_id}")
suspend fun getGeofences(@Path("profile_id") profileId: Int): Response<List<Geofence>>

@POST("api/geofences")
suspend fun createGeofence(@Body request: CreateGeofenceRequest): Response<Geofence>

@DELETE("api/geofences/{geofence_id}")
suspend fun deleteGeofence(@Path("geofence_id") geofenceId: Int): Response<Unit>

@POST("api/geofences/check")
suspend fun checkGeofence(@Body request: CheckGeofenceRequest): Response<GeofenceCheckResult>
```

## Task 16.6: Add Navigation to Geofencing Screen

**File**: `navigation/NavGraph.kt`

**Add**:
```kotlin
composable(
    route = "geofencing/{profileId}",
    arguments = listOf(navArgument("profileId") { type = NavType.IntType })
) { backStackEntry ->
    val profileId = backStackEntry.arguments?.getInt("profileId") ?: return@composable
    GeofencingScreen(
        profileId = profileId,
        onNavigateBack = { navController.popBackStack() }
    )
}
```

**Add navigation button** to VehicleDetailScreen or Dashboard:
```kotlin
Button(onClick = { navController.navigate("geofencing/$profileId") }) {
    Icon(Icons.Default.LocationOn, null)
    Text("Manage Geofences")
}
```

## Phase 16 Verification Checklist

- [ ] Google Maps dependency added and compiles
- [ ] Geofencing screen displays map
- [ ] Existing geofences show as circles on map
- [ ] Long-press on map opens add dialog
- [ ] Can create new geofence with name, location, radius
- [ ] Alert type checkboxes (entry/exit) work
- [ ] Geofences sync with server
- [ ] Can delete geofence
- [ ] Navigation from dashboard/vehicle detail works

---

# PHASE 17: AI Chat Screen Implementation

**Priority**: MEDIUM
**Location**: `C:\Predict guradian\app\src\main\java\com\predict\guardian\`
**Goal**: Create AI assistant chat interface for vehicle queries

## Task 17.1: Create Chat Data Models

**Create file**: `data/model/ChatModels.kt`

```kotlin
package com.predict.guardian.data.model

import java.time.Instant

data class ChatMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val content: String,
    val isFromUser: Boolean,
    val timestamp: Instant = Instant.now(),
    val isLoading: Boolean = false
)

data class ChatRequest(
    val message: String,
    val profileId: Int,
    val context: String? = null  // Optional vehicle context
)

data class ChatResponse(
    val response: String,
    val suggestions: List<String>? = null
)
```

## Task 17.2: Create ChatScreen Composable

**Create file**: `ui/screen/chat/ChatScreen.kt`

```kotlin
package com.predict.guardian.ui.screen.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.predict.guardian.data.model.ChatMessage
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    profileId: Int,
    vehicleName: String,
    onNavigateBack: () -> Unit,
    viewModel: ChatViewModel = hiltViewModel()
) {
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(profileId) {
        viewModel.initialize(profileId, vehicleName)
    }

    // Auto-scroll to bottom when new message arrives
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("AI Assistant")
                        Text(
                            text = vehicleName,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                }
            )
        },
        bottomBar = {
            ChatInputBar(
                value = inputText,
                onValueChange = { inputText = it },
                onSend = {
                    if (inputText.isNotBlank()) {
                        viewModel.sendMessage(inputText)
                        inputText = ""
                    }
                },
                isLoading = isLoading
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages) { message ->
                ChatBubble(message = message)
            }

            // Loading indicator
            if (isLoading) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.CenterStart
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ChatBubble(message: ChatMessage) {
    val bubbleColor = if (message.isFromUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.secondaryContainer
    }

    val textColor = if (message.isFromUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSecondaryContainer
    }

    val alignment = if (message.isFromUser) Alignment.End else Alignment.Start

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = alignment
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(bubbleColor)
                .padding(12.dp)
        ) {
            Text(
                text = message.content,
                color = textColor
            )
        }
        Text(
            text = message.timestamp.atZone(java.time.ZoneId.systemDefault())
                .format(DateTimeFormatter.ofPattern("HH:mm")),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun ChatInputBar(
    value: String,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    isLoading: Boolean
) {
    Surface(
        tonalElevation = 3.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask about your vehicle...") },
                maxLines = 4,
                enabled = !isLoading
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = onSend,
                enabled = value.isNotBlank() && !isLoading
            ) {
                Icon(
                    Icons.Default.Send,
                    contentDescription = "Send",
                    tint = if (value.isNotBlank() && !isLoading) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    }
                )
            }
        }
    }
}
```

## Task 17.3: Create ChatViewModel

**Create file**: `ui/screen/chat/ChatViewModel.kt`

```kotlin
package com.predict.guardian.ui.screen.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.predict.guardian.data.model.ChatMessage
import com.predict.guardian.data.model.ChatRequest
import com.predict.guardian.data.repository.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository
) : ViewModel() {

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private var profileId: Int = 0
    private var vehicleName: String = ""

    fun initialize(profileId: Int, vehicleName: String) {
        this.profileId = profileId
        this.vehicleName = vehicleName

        // Add welcome message
        _messages.value = listOf(
            ChatMessage(
                content = "Hello! I'm your AI vehicle assistant. I can help you with:\n\n" +
                    "• Understanding diagnostic codes\n" +
                    "• Maintenance recommendations\n" +
                    "• Fuel efficiency tips\n" +
                    "• Driving behavior analysis\n\n" +
                    "What would you like to know about your $vehicleName?",
                isFromUser = false
            )
        )
    }

    fun sendMessage(text: String) {
        // Add user message
        val userMessage = ChatMessage(content = text, isFromUser = true)
        _messages.value = _messages.value + userMessage

        viewModelScope.launch {
            _isLoading.value = true

            val request = ChatRequest(
                message = text,
                profileId = profileId,
                context = "Vehicle: $vehicleName"
            )

            repository.sendChatMessage(request)
                .onSuccess { response ->
                    val aiMessage = ChatMessage(
                        content = response.response,
                        isFromUser = false
                    )
                    _messages.value = _messages.value + aiMessage
                }
                .onFailure { error ->
                    val errorMessage = ChatMessage(
                        content = "Sorry, I couldn't process your request. Please try again.",
                        isFromUser = false
                    )
                    _messages.value = _messages.value + errorMessage
                }

            _isLoading.value = false
        }
    }
}
```

## Task 17.4: Create ChatRepository

**Create file**: `data/repository/ChatRepository.kt`

```kotlin
package com.predict.guardian.data.repository

import com.predict.guardian.data.api.ApiService
import com.predict.guardian.data.model.ChatRequest
import com.predict.guardian.data.model.ChatResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ChatRepository @Inject constructor(
    private val apiService: ApiService
) {
    suspend fun sendChatMessage(request: ChatRequest): Result<ChatResponse> {
        return try {
            val response = apiService.sendChatMessage(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Chat request failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
```

## Task 17.5: Add Chat Endpoint to ApiService

**File**: `data/api/ApiService.kt`

**Add**:
```kotlin
@POST("api/chat")
suspend fun sendChatMessage(@Body request: ChatRequest): Response<ChatResponse>
```

## Task 17.6: Add Navigation to Chat Screen

**File**: `navigation/NavGraph.kt`

**Add**:
```kotlin
composable(
    route = "chat/{profileId}/{vehicleName}",
    arguments = listOf(
        navArgument("profileId") { type = NavType.IntType },
        navArgument("vehicleName") { type = NavType.StringType }
    )
) { backStackEntry ->
    val profileId = backStackEntry.arguments?.getInt("profileId") ?: return@composable
    val vehicleName = backStackEntry.arguments?.getString("vehicleName") ?: "Vehicle"
    ChatScreen(
        profileId = profileId,
        vehicleName = vehicleName,
        onNavigateBack = { navController.popBackStack() }
    )
}
```

## Phase 17 Verification Checklist

- [ ] Chat screen displays welcome message
- [ ] User can type and send messages
- [ ] Messages appear in chat bubbles (user on right, AI on left)
- [ ] Loading indicator shows while waiting for response
- [ ] AI responses display correctly
- [ ] Auto-scroll to newest message works
- [ ] Timestamps display correctly
- [ ] Error handling shows user-friendly message
- [ ] Navigation from vehicle detail works

---

# PHASE 18: Driver Analytics & Polish Features

**Priority**: LOW
**Location**: `C:\Predict guradian\app\src\main\java\com\predict\guardian\`
**Goal**: Complete remaining UI polish and driver analytics visualization

## Task 18.1: Implement Driver Photo with AsyncImage

**File**: `ui/components/VehicleCard.kt`

**Find** the placeholder comment around line 171 and implement:

```kotlin
// Replace placeholder with actual implementation
import coil.compose.AsyncImage
import coil.request.ImageRequest

// In VehicleCard composable, replace placeholder with:
if (driver.photoUrl != null) {
    AsyncImage(
        model = ImageRequest.Builder(LocalContext.current)
            .data(driver.photoUrl)
            .crossfade(true)
            .placeholder(R.drawable.ic_driver_placeholder)
            .error(R.drawable.ic_driver_placeholder)
            .build(),
        contentDescription = "Driver photo",
        modifier = Modifier
            .size(40.dp)
            .clip(CircleShape),
        contentScale = ContentScale.Crop
    )
} else {
    // Default icon if no photo
    Icon(
        Icons.Default.Person,
        contentDescription = null,
        modifier = Modifier
            .size(40.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant, CircleShape)
            .padding(8.dp)
    )
}
```

## Task 18.2: Create Driver Comparison Analytics Screen

**Create file**: `ui/screen/analytics/DriverComparisonScreen.kt`

```kotlin
package com.predict.guardian.ui.screen.analytics

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DriverComparisonScreen(
    profileId: Int,
    onNavigateBack: () -> Unit,
    viewModel: DriverComparisonViewModel = hiltViewModel()
) {
    val drivers by viewModel.drivers.collectAsState()
    val selectedDrivers by viewModel.selectedDrivers.collectAsState()
    val comparisonData by viewModel.comparisonData.collectAsState()

    LaunchedEffect(profileId) {
        viewModel.loadDrivers(profileId)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Driver Comparison") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Driver selection chips
            Text("Select drivers to compare:", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                drivers.forEach { driver ->
                    FilterChip(
                        selected = selectedDrivers.contains(driver.id),
                        onClick = { viewModel.toggleDriver(driver.id) },
                        label = { Text(driver.name) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Comparison metrics
            if (comparisonData.isNotEmpty()) {
                ComparisonCard(
                    title = "Safety Score",
                    data = comparisonData.map { it.driverName to it.safetyScore }
                )

                Spacer(modifier = Modifier.height(16.dp))

                ComparisonCard(
                    title = "Average Speed (km/h)",
                    data = comparisonData.map { it.driverName to it.avgSpeed }
                )

                Spacer(modifier = Modifier.height(16.dp))

                ComparisonCard(
                    title = "Hard Braking Events",
                    data = comparisonData.map { it.driverName to it.hardBrakingCount.toFloat() }
                )

                Spacer(modifier = Modifier.height(16.dp))

                ComparisonCard(
                    title = "Total Distance (km)",
                    data = comparisonData.map { it.driverName to it.totalDistance }
                )
            } else if (selectedDrivers.size < 2) {
                Text(
                    "Select at least 2 drivers to compare",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun ComparisonCard(
    title: String,
    data: List<Pair<String, Float>>
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Spacer(modifier = Modifier.height(8.dp))

            data.forEach { (name, value) ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(name)
                    Text(
                        "%.1f".format(value),
                        style = MaterialTheme.typography.bodyLarge
                    )
                }
            }
        }
    }
}
```

## Task 18.3: Wire Dark Mode Toggle

**File**: `ui/screen/settings/AdvancedSettingsActivity.kt`

**Find** the dark mode section and wire it:

```kotlin
// In the settings composable, add:
var darkModeEnabled by remember {
    mutableStateOf(viewModel.isDarkModeEnabled())
}

Row(
    modifier = Modifier.fillMaxWidth(),
    horizontalArrangement = Arrangement.SpaceBetween,
    verticalAlignment = Alignment.CenterVertically
) {
    Text("Dark Mode")
    Switch(
        checked = darkModeEnabled,
        onCheckedChange = { enabled ->
            darkModeEnabled = enabled
            viewModel.setDarkMode(enabled)
        }
    )
}
```

**Update AdvancedSettingsViewModel**:
```kotlin
private val dataStore: DataStore<Preferences>

fun isDarkModeEnabled(): Boolean {
    return runBlocking {
        dataStore.data.first()[PreferencesKeys.DARK_MODE] ?: false
    }
}

suspend fun setDarkMode(enabled: Boolean) {
    dataStore.edit { preferences ->
        preferences[PreferencesKeys.DARK_MODE] = enabled
    }
}

object PreferencesKeys {
    val DARK_MODE = booleanPreferencesKey("dark_mode")
}
```

**Update PredictGuardianApp.kt** to observe dark mode:
```kotlin
@Composable
fun PredictGuardianTheme(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val dataStore = context.settingsDataStore
    val darkMode by dataStore.data
        .map { it[PreferencesKeys.DARK_MODE] ?: false }
        .collectAsState(initial = false)

    MaterialTheme(
        colorScheme = if (darkMode) darkColorScheme() else lightColorScheme(),
        typography = Typography,
        content = content
    )
}
```

## Task 18.4: Add Biometric Authentication (Optional Enhancement)

**File**: `ui/screen/auth/LoginScreen.kt`

```kotlin
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

// Add biometric login option
private fun showBiometricPrompt(activity: FragmentActivity, onSuccess: () -> Unit) {
    val executor = ContextCompat.getMainExecutor(activity)

    val biometricPrompt = BiometricPrompt(
        activity,
        executor,
        object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                onSuccess()
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                // Show error toast
            }
        }
    )

    val promptInfo = BiometricPrompt.PromptInfo.Builder()
        .setTitle("Biometric Login")
        .setSubtitle("Log in using your biometric credential")
        .setNegativeButtonText("Use password instead")
        .build()

    biometricPrompt.authenticate(promptInfo)
}

// Add to UI:
if (BiometricManager.from(context).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK)
    == BiometricManager.BIOMETRIC_SUCCESS) {
    Button(
        onClick = { showBiometricPrompt(activity) { viewModel.biometricLogin() } }
    ) {
        Icon(Icons.Default.Fingerprint, null)
        Text("Login with Biometrics")
    }
}
```

## Task 18.5: Final Polish Checklist

**Review and fix**:
1. Remove any "Skip Login" debug buttons from production
2. Ensure all error messages are user-friendly
3. Add loading states to all network operations
4. Verify Arabic translations are complete
5. Test RTL layout in Arabic mode
6. Verify ProGuard rules for release build
7. Test offline mode functionality
8. Update app version in build.gradle

## Phase 18 Verification Checklist

- [ ] Driver photos display correctly with AsyncImage
- [ ] Driver comparison analytics screen works
- [ ] Dark mode toggle functions correctly
- [ ] Theme persists across app restarts
- [ ] Biometric auth works (if implemented)
- [ ] No debug code in release build
- [ ] All strings translated to Arabic
- [ ] RTL layout works correctly
- [ ] App builds in release mode without errors
- [ ] ProGuard doesn't break functionality

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 5: FULL INTEGRATION TESTING (Phases 19-20)
# All Applications Working Together
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 19: Complete System Integration Test

**Priority**: CRITICAL
**Goal**: Verify all 4 applications work together seamlessly

## Task 19.1: Full Data Flow Test

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPLETE DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Vehicle with OBD                                                    │
│       ↓                                                              │
│  PredictOBD App (Driver's Phone)                                     │
│       ↓ [Bluetooth]                                                  │
│  Reads OBD-II data (RPM, Speed, Temps, DTCs)                         │
│       ↓ [HTTPS API]                                                  │
│  Previlium Server                                                    │
│       ↓ [Stores in SQLite]                                           │
│  ┌────┴─────────────────────────────┐                                │
│  ↓                                  ↓                                │
│  PREDICT Desktop                    Predict Guardian App             │
│  (Mechanic/Admin)                   (Parent/Fleet Manager)           │
│  - AI Predictions                   - Real-time Dashboard            │
│  - PDF Reports                      - Driving Analytics              │
│  - Full Diagnostics                 - Geofence Alerts                │
│                                     - Emergency Commands             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Test Steps**:
1. Start Previlium Server on your PC
2. Connect OBD adapter to vehicle
3. Open PredictOBD app, connect to adapter and server
4. Start driving session with driver profile
5. Verify data appears on server (check logs)
6. Open PREDICT Desktop, verify live data tab shows data
7. Open Predict Guardian app, verify dashboard updates
8. Generate AI prediction on Desktop
9. View prediction in Guardian app
10. Create PDF report from Desktop

## Task 19.2: Multi-Vehicle Fleet Test

1. Create 3 different vehicle profiles
2. Simulate/collect data for each
3. Verify data stays isolated per profile
4. Test switching between vehicles on Guardian dashboard
5. Verify correct vehicle data displays

## Task 19.3: Guardian-Driver Communication Test

1. **Setup**:
   - Fleet Manager on Predict Guardian app
   - Driver on PredictOBD app

2. **Test Emergency Location**:
   - Guardian requests location
   - Driver app receives request
   - Location sent back to Guardian

3. **Test Guardian Commands**:
   - Guardian sends warning message
   - Driver receives notification

4. **Test Geofence Alerts**:
   - Create geofence on Guardian app
   - Have driver enter/exit zone
   - Verify Guardian receives alert

## Task 19.4: Real-Time Updates Test

1. Connect PredictOBD to vehicle
2. Open Guardian app dashboard
3. Start driving session
4. Verify:
   - Dashboard shows "DRIVING" status
   - Speed updates in real-time
   - Session duration increments
   - Safety score adjusts based on behavior

## Task 19.5: Offline/Online Sync Test

**PredictOBD Offline Test**:
1. Disconnect phone from internet
2. Continue collecting OBD data
3. Reconnect to internet
4. Verify queued data uploads to server

**Guardian Offline Test**:
1. Open Guardian app with vehicles loaded
2. Disconnect from internet
3. Verify cached data still displays
4. Reconnect and verify data refreshes

## Phase 19 Verification Checklist

- [ ] All 4 apps start without errors
- [ ] PredictOBD sends data to server
- [ ] Server stores data correctly
- [ ] Desktop receives and displays data
- [ ] Guardian shows real-time dashboard
- [ ] Multi-vehicle isolation works
- [ ] Guardian commands reach driver
- [ ] Geofence alerts generate correctly
- [ ] Real-time WebSocket updates work
- [ ] Offline mode functions on all apps
- [ ] Sync works when reconnected

---

# PHASE 20: Production Readiness & Deployment

**Priority**: CRITICAL
**Goal**: Prepare all applications for production deployment

## Task 20.1: Security Audit

**Desktop App**:
- [ ] No hardcoded credentials
- [ ] API keys in environment variables
- [ ] HTTPS enforced for all API calls
- [ ] Input validation on all forms

**Server**:
- [ ] API key authentication working
- [ ] Rate limiting implemented
- [ ] SQL injection protection (parameterized queries)
- [ ] CORS properly configured
- [ ] Secrets not in git repository

**Android Apps**:
- [ ] ProGuard enabled for release builds
- [ ] Network security config uses HTTPS only
- [ ] No debug logs in release build
- [ ] EncryptedSharedPreferences for tokens

## Task 20.2: Performance Verification

- [ ] Desktop: App loads in < 5 seconds
- [ ] Server: API responses < 500ms
- [ ] Guardian: Dashboard refresh < 2 seconds
- [ ] PredictOBD: OBD read cycle < 1 second

## Task 20.3: Build Release Versions

**Desktop**:
```bash
cd "c:\D Drive\Predict"
# Create release executable
pyinstaller --onefile --windowed main_pyside.py
```

**Server**:
```bash
cd "C:\OBDserver\Previlium_OBD_Server"
# Test production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Android Apps**:
```bash
# PredictOBD
cd "C:\Predict\PredictOBD"
./gradlew assembleRelease

# Guardian
cd "C:\Predict guradian"
./gradlew assembleRelease
```

## Task 20.4: Final Documentation

- [ ] Update README files with current instructions
- [ ] Document API endpoints for each app
- [ ] Create user guide for fleet managers
- [ ] Document deployment steps
- [ ] Create troubleshooting guide

## Task 20.5: Final Verification

Run through complete user journey:

1. **Setup Phase**:
   - Deploy server to production
   - Install Desktop app on admin PC
   - Install PredictOBD on driver phone
   - Install Guardian on fleet manager phone

2. **Registration Phase**:
   - Create admin account
   - Create vehicle profiles
   - Create driver profiles
   - Link guardian to drivers

3. **Daily Operations**:
   - Driver starts shift, selects profile
   - Connects to OBD adapter
   - Drives routes
   - Guardian monitors in real-time
   - Receives any alerts (speeding, geofence)

4. **Reporting Phase**:
   - Admin generates AI predictions
   - Creates PDF reports
   - Reviews driver analytics
   - Exports fleet summary

## Phase 20 Final Checklist

- [ ] All security checks pass
- [ ] Performance metrics acceptable
- [ ] Release builds created for all apps
- [ ] Documentation complete
- [ ] Full user journey works end-to-end
- [ ] No mock data anywhere
- [ ] All error handling graceful
- [ ] Ready for production deployment

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 6: NEW FEATURES (Phases 21-23)
# Additional features identified during gap analysis
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 21: Guardian App - LLM Chat Feature

**Priority**: HIGH
**Location**: `C:\Predict guradian\app\src\main\java\com\predict\guardian\`
**Purpose**: Allow parents/fleet managers to ask AI questions about their drivers' vehicles

> **NOTE**: PredictOBD already has full LLM chat implemented in `ChatScreen.kt`.
> This phase adds the same capability to the Guardian app.

> **PARTIAL PROGRESS**: The following files have been STARTED and need to be completed/verified:
> - `data/model/GuardianChatModels.kt` - Created with basic models (review and complete)
> - `data/repository/GuardianChatRepository.kt` - Created with basic repository (review and complete)
> - `data/api/ApiService.kt` - Chat endpoints ADDED (lines 241-253) - verify and complete
>
> Continue from Task 21.3 (ViewModel) and complete Tasks 21.4-21.6 (Screen, Navigation, DI).

## Task 21.1: Create Guardian Chat Models

**Create file**: `data/model/GuardianChatModels.kt`

```kotlin
package com.predict.guardian.data.model

import com.google.gson.annotations.SerializedName

/**
 * Chat message for Guardian app
 */
data class GuardianChatMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val text: String,
    val isFromUser: Boolean,
    val timestamp: Long = System.currentTimeMillis(),
    val vehicleId: Int? = null,
    val vehicleName: String? = null,
    val confidence: Float = 0f,
    val sources: List<String> = emptyList(),
    val alerts: List<String> = emptyList(),
    val isError: Boolean = false
)

/**
 * Chat request to server
 */
data class GuardianChatRequest(
    val message: String,
    @SerializedName("profile_id") val profileId: Int?,
    @SerializedName("vehicle_context") val vehicleContext: GuardianVehicleContext?,
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("is_guardian") val isGuardian: Boolean = true
)

/**
 * Vehicle context for Guardian (from server, not direct OBD)
 */
data class GuardianVehicleContext(
    @SerializedName("profile_id") val profileId: Int,
    @SerializedName("vehicle_name") val vehicleName: String,
    val make: String?,
    val model: String?,
    val year: Int?,
    @SerializedName("last_known_dtcs") val lastKnownDtcs: List<String> = emptyList(),
    @SerializedName("active_predictions") val activePredictions: List<String> = emptyList(),
    @SerializedName("last_update") val lastUpdate: Long?
)

/**
 * Chat response from server
 */
data class GuardianChatResponse(
    val response: String,
    val confidence: Float = 0f,
    val sources: List<String> = emptyList(),
    val alerts: List<String> = emptyList(),
    @SerializedName("conversation_id") val conversationId: String?,
    @SerializedName("vehicle_summary") val vehicleSummary: String? = null
)
```

## Task 21.2: Create Guardian Chat Repository

**Create file**: `data/repository/GuardianChatRepository.kt`

```kotlin
package com.predict.guardian.data.repository

import com.predict.guardian.data.api.GuardianApiService
import com.predict.guardian.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GuardianChatRepository @Inject constructor(
    private val apiService: GuardianApiService
) {
    suspend fun sendMessage(
        apiKey: String,
        message: String,
        profileId: Int?,
        vehicleContext: GuardianVehicleContext?,
        conversationId: String?
    ): Result<GuardianChatResponse> {
        return try {
            val request = GuardianChatRequest(
                message = message,
                profileId = profileId,
                vehicleContext = vehicleContext,
                conversationId = conversationId,
                isGuardian = true
            )
            val response = apiService.sendGuardianChatMessage(apiKey, request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errorMsg = when (response.code()) {
                    403 -> "Premium access required for AI chat"
                    401 -> "Invalid API key"
                    else -> "Failed to get AI response"
                }
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getVehicleContext(apiKey: String, profileId: Int): Result<GuardianVehicleContext> {
        return try {
            val response = apiService.getVehicleContextForChat(apiKey, profileId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to get vehicle context"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
```

## Task 21.3: Create Guardian Chat ViewModel

**Create file**: `ui/screen/chat/GuardianChatViewModel.kt`

```kotlin
package com.predict.guardian.ui.screen.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.predict.guardian.data.model.*
import com.predict.guardian.data.repository.GuardianChatRepository
import com.predict.guardian.data.repository.VehicleRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class GuardianChatViewModel @Inject constructor(
    private val chatRepository: GuardianChatRepository,
    private val vehicleRepository: VehicleRepository
) : ViewModel() {

    private val _messages = MutableStateFlow<List<GuardianChatMessage>>(emptyList())
    val messages: StateFlow<List<GuardianChatMessage>> = _messages.asStateFlow()

    private val _isSending = MutableStateFlow(false)
    val isSending: StateFlow<Boolean> = _isSending.asStateFlow()

    private val _linkedVehicles = MutableStateFlow<List<Vehicle>>(emptyList())
    val linkedVehicles: StateFlow<List<Vehicle>> = _linkedVehicles.asStateFlow()

    private val _selectedVehicle = MutableStateFlow<Vehicle?>(null)
    val selectedVehicle: StateFlow<Vehicle?> = _selectedVehicle.asStateFlow()

    private var conversationId: String? = null
    private var currentVehicleContext: GuardianVehicleContext? = null

    fun loadLinkedVehicles(apiKey: String) {
        viewModelScope.launch {
            vehicleRepository.getLinkedVehicles(apiKey)
                .onSuccess { vehicles ->
                    _linkedVehicles.value = vehicles
                    // Auto-select first vehicle if none selected
                    if (_selectedVehicle.value == null && vehicles.isNotEmpty()) {
                        selectVehicle(apiKey, vehicles.first())
                    }
                }
        }
    }

    fun selectVehicle(apiKey: String, vehicle: Vehicle) {
        _selectedVehicle.value = vehicle
        // Load vehicle context for chat
        viewModelScope.launch {
            chatRepository.getVehicleContext(apiKey, vehicle.profileId)
                .onSuccess { context ->
                    currentVehicleContext = context
                }
        }
    }

    fun sendMessage(apiKey: String, message: String) {
        if (message.isBlank()) return

        // Add user message to chat
        val userMessage = GuardianChatMessage(
            text = message,
            isFromUser = true,
            vehicleId = _selectedVehicle.value?.profileId,
            vehicleName = _selectedVehicle.value?.name
        )
        _messages.value = _messages.value + userMessage

        // Send to server
        viewModelScope.launch {
            _isSending.value = true
            chatRepository.sendMessage(
                apiKey = apiKey,
                message = message,
                profileId = _selectedVehicle.value?.profileId,
                vehicleContext = currentVehicleContext,
                conversationId = conversationId
            ).onSuccess { response ->
                conversationId = response.conversationId
                val aiMessage = GuardianChatMessage(
                    text = response.response,
                    isFromUser = false,
                    confidence = response.confidence,
                    sources = response.sources,
                    alerts = response.alerts,
                    vehicleId = _selectedVehicle.value?.profileId,
                    vehicleName = _selectedVehicle.value?.name
                )
                _messages.value = _messages.value + aiMessage
            }.onFailure { error ->
                val errorMessage = GuardianChatMessage(
                    text = "⚠️ ${error.message ?: "Failed to get response"}",
                    isFromUser = false,
                    isError = true
                )
                _messages.value = _messages.value + errorMessage
            }
            _isSending.value = false
        }
    }

    fun clearChat() {
        _messages.value = emptyList()
        conversationId = null
    }
}
```

## Task 21.4: Create Guardian Chat Screen UI

**Create file**: `ui/screen/chat/GuardianChatScreen.kt`

```kotlin
package com.predict.guardian.ui.screen.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.predict.guardian.data.model.GuardianChatMessage
import com.predict.guardian.data.model.Vehicle
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GuardianChatScreen(
    apiKey: String,
    onNavigateBack: () -> Unit,
    viewModel: GuardianChatViewModel = hiltViewModel()
) {
    val messages by viewModel.messages.collectAsState()
    val isSending by viewModel.isSending.collectAsState()
    val linkedVehicles by viewModel.linkedVehicles.collectAsState()
    val selectedVehicle by viewModel.selectedVehicle.collectAsState()

    var messageInput by remember { mutableStateOf("") }
    var showVehicleSelector by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    LaunchedEffect(apiKey) {
        viewModel.loadLinkedVehicles(apiKey)
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI Assistant") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                },
                actions = {
                    // Vehicle selector chip
                    Surface(
                        onClick = { showVehicleSelector = true },
                        shape = RoundedCornerShape(16.dp),
                        color = MaterialTheme.colorScheme.primaryContainer
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.DirectionsCar, null, Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text(
                                text = selectedVehicle?.name ?: "Select Vehicle",
                                fontSize = 12.sp
                            )
                            Icon(Icons.Default.ArrowDropDown, null, Modifier.size(16.dp))
                        }
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF1A1A1A))
        ) {
            // Messages list
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(16.dp),
                contentPadding = PaddingValues(vertical = 16.dp)
            ) {
                if (messages.isEmpty()) {
                    item {
                        GuardianWelcomeMessage(
                            selectedVehicle = selectedVehicle,
                            onSuggestionClick = { messageInput = it }
                        )
                    }
                }

                items(messages) { message ->
                    GuardianChatBubble(message = message)
                }

                if (isSending) {
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Start
                        ) {
                            Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = Color(0xFF2A2A2A)
                            ) {
                                Row(
                                    modifier = Modifier.padding(16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(16.dp),
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(Modifier.width(12.dp))
                                    Text("AI is thinking...", color = Color.Gray)
                                }
                            }
                        }
                    }
                }
            }

            // Input area
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = Color(0xFF2A2A2A)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalAlignment = Alignment.Bottom
                ) {
                    OutlinedTextField(
                        value = messageInput,
                        onValueChange = { messageInput = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Ask about ${selectedVehicle?.name ?: "your vehicle"}...") },
                        enabled = !isSending && selectedVehicle != null,
                        maxLines = 5,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color.Transparent,
                            unfocusedBorderColor = Color.Transparent
                        )
                    )
                    Spacer(Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            viewModel.sendMessage(apiKey, messageInput)
                            messageInput = ""
                        },
                        enabled = messageInput.isNotBlank() && !isSending && selectedVehicle != null
                    ) {
                        Icon(
                            Icons.Default.Send,
                            "Send",
                            tint = if (messageInput.isNotBlank()) Color.White else Color.Gray
                        )
                    }
                }
            }
        }
    }

    // Vehicle selector dialog
    if (showVehicleSelector) {
        AlertDialog(
            onDismissRequest = { showVehicleSelector = false },
            title = { Text("Select Vehicle") },
            text = {
                Column {
                    linkedVehicles.forEach { vehicle ->
                        Surface(
                            onClick = {
                                viewModel.selectVehicle(apiKey, vehicle)
                                showVehicleSelector = false
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.DirectionsCar, null)
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text(vehicle.name, fontWeight = FontWeight.Bold)
                                    Text(
                                        "${vehicle.make} ${vehicle.model} ${vehicle.year}",
                                        fontSize = 12.sp,
                                        color = Color.Gray
                                    )
                                }
                                Spacer(Modifier.weight(1f))
                                if (selectedVehicle?.profileId == vehicle.profileId) {
                                    Icon(Icons.Default.Check, null, tint = Color.Green)
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showVehicleSelector = false }) {
                    Text("Close")
                }
            }
        )
    }
}

@Composable
private fun GuardianWelcomeMessage(
    selectedVehicle: Vehicle?,
    onSuggestionClick: (String) -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Guardian AI",
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = if (selectedVehicle != null)
                "Ask about ${selectedVehicle.name}'s vehicle"
            else
                "Select a vehicle to ask questions",
            color = Color.Gray
        )
        Spacer(Modifier.height(24.dp))

        if (selectedVehicle != null) {
            val suggestions = listOf(
                "How is ${selectedVehicle.name}'s car doing?",
                "Are there any predicted failures?",
                "What maintenance is due?",
                "Show me the driving behavior summary"
            )
            suggestions.forEach { suggestion ->
                Surface(
                    onClick = { onSuggestionClick(suggestion) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF2A2A2A)
                ) {
                    Row(modifier = Modifier.padding(12.dp)) {
                        Icon(Icons.Default.KeyboardArrowRight, null, tint = Color.Gray)
                        Text(suggestion, color = Color.White.copy(alpha = 0.8f))
                    }
                }
            }
        }
    }
}

@Composable
private fun GuardianChatBubble(message: GuardianChatMessage) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = if (message.isFromUser) "You" else "Guardian AI",
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            color = Color.White.copy(alpha = 0.6f)
        )
        Spacer(Modifier.height(4.dp))
        Surface(
            shape = RoundedCornerShape(8.dp),
            color = when {
                message.isError -> Color(0xFF3A1A1A)
                message.isFromUser -> Color(0xFF2A2A2A)
                else -> Color.Transparent
            }
        ) {
            Column(modifier = Modifier.padding(if (message.isFromUser) 16.dp else 0.dp)) {
                Text(
                    text = message.text,
                    fontSize = 15.sp,
                    lineHeight = 24.sp,
                    color = Color.White.copy(alpha = 0.9f)
                )
                if (message.vehicleName != null && !message.isFromUser) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = "Vehicle: ${message.vehicleName}",
                        fontSize = 10.sp,
                        color = Color.Gray
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    text = SimpleDateFormat("HH:mm", Locale.getDefault())
                        .format(Date(message.timestamp)),
                    fontSize = 10.sp,
                    color = Color.Gray
                )
            }
        }
    }
}
```

## Task 21.5: Add Chat API Endpoint

**File**: `data/api/GuardianApiService.kt`

**Add**:
```kotlin
// AI Chat endpoints
@POST("api/chat/message")
suspend fun sendGuardianChatMessage(
    @Header("X-API-Key") apiKey: String,
    @Body request: GuardianChatRequest
): Response<GuardianChatResponse>

@GET("api/guardian/vehicle-context/{profile_id}")
suspend fun getVehicleContextForChat(
    @Header("X-API-Key") apiKey: String,
    @Path("profile_id") profileId: Int
): Response<GuardianVehicleContext>
```

## Task 21.6: Add Navigation to Chat Screen

**File**: `navigation/NavGraph.kt`

**Add**:
```kotlin
composable("guardian_chat") {
    GuardianChatScreen(
        apiKey = apiKey,
        onNavigateBack = { navController.popBackStack() }
    )
}
```

**Add chat button to Dashboard** - in `DashboardScreen.kt`:
```kotlin
FloatingActionButton(
    onClick = { navController.navigate("guardian_chat") }
) {
    Icon(Icons.Default.Chat, "AI Chat")
}
```

## Phase 21 Verification Checklist

- [ ] Chat screen displays with vehicle selector
- [ ] Can select different linked vehicles
- [ ] Welcome message shows vehicle-specific suggestions
- [ ] Can send messages to AI
- [ ] Responses include vehicle context
- [ ] Error messages display properly
- [ ] Arabic RTL support works
- [ ] Navigation from dashboard works

---

# PHASE 22: Desktop - Parent-Child Profile + Invite Links

**Priority**: HIGH
**Location**: `c:\D Drive\Predict\`
**Purpose**: Allow fleet owners/parents to register and manage drivers under their account

## Task 22.1: Create Profile Hierarchy Manager

**Create file**: `c:\D Drive\Predict\profile_hierarchy_manager.py`

```python
"""
Profile Hierarchy Manager
Manages parent-child relationships between fleet owners and drivers
"""

import sqlite3
import secrets
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ProfileHierarchyManager:
    """Manages fleet owner -> driver relationships"""

    def __init__(self, db_path: str = "vehicle_profiles.db"):
        self.db_path = db_path
        self._init_hierarchy_tables()

    def _init_hierarchy_tables(self):
        """Create hierarchy tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Fleet owners table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fleet_owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    phone TEXT,
                    api_key_hash TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')

            # Drivers linked to fleet owners
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fleet_drivers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fleet_owner_id INTEGER NOT NULL,
                    driver_name TEXT NOT NULL,
                    driver_email TEXT,
                    driver_phone TEXT,
                    profile_id INTEGER,
                    api_key TEXT NOT NULL,
                    api_key_hash TEXT NOT NULL,
                    relationship TEXT DEFAULT 'driver',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (fleet_owner_id) REFERENCES fleet_owners(id)
                )
            ''')

            # Invite codes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invite_codes (
                    code TEXT PRIMARY KEY,
                    fleet_owner_id INTEGER NOT NULL,
                    driver_name TEXT,
                    expires_at TIMESTAMP NOT NULL,
                    redeemed_by INTEGER,
                    redeemed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fleet_owner_id) REFERENCES fleet_owners(id)
                )
            ''')

            conn.commit()

    def generate_api_key(self) -> str:
        """Generate a new API key"""
        chars = string.ascii_letters + string.digits
        key = ''.join(secrets.choice(chars) for _ in range(32))
        return f"PRED_{key}"

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def add_driver(
        self,
        fleet_owner_id: int,
        driver_name: str,
        driver_email: Optional[str] = None,
        driver_phone: Optional[str] = None,
        relationship: str = "driver"
    ) -> Dict[str, Any]:
        """
        Add a driver under a fleet owner
        Returns the driver info including the API key (only shown once)
        """
        api_key = self.generate_api_key()
        api_key_hash = self.hash_api_key(api_key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO fleet_drivers
                (fleet_owner_id, driver_name, driver_email, driver_phone,
                 api_key, api_key_hash, relationship)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (fleet_owner_id, driver_name, driver_email, driver_phone,
                  api_key, api_key_hash, relationship))
            driver_id = cursor.lastrowid
            conn.commit()

        return {
            "driver_id": driver_id,
            "driver_name": driver_name,
            "api_key": api_key,  # Show only once!
            "relationship": relationship,
            "message": "API key generated. Share this with the driver securely."
        }

    def get_fleet_drivers(self, fleet_owner_id: int) -> List[Dict[str, Any]]:
        """Get all drivers under a fleet owner"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, driver_name, driver_email, driver_phone,
                       profile_id, relationship, created_at, is_active
                FROM fleet_drivers
                WHERE fleet_owner_id = ? AND is_active = 1
                ORDER BY driver_name
            ''', (fleet_owner_id,))
            return [dict(row) for row in cursor.fetchall()]

    def generate_invite_code(
        self,
        fleet_owner_id: int,
        driver_name: Optional[str] = None,
        expires_hours: int = 48
    ) -> str:
        """Generate an invite code for a new driver"""
        # Generate code: PRED-YYYY-XXXX-XXXX
        year = datetime.now().year
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits)
                              for _ in range(8))
        code = f"PRED-{year}-{random_part[:4]}-{random_part[4:]}"

        expires_at = datetime.now() + timedelta(hours=expires_hours)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO invite_codes (code, fleet_owner_id, driver_name, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (code, fleet_owner_id, driver_name, expires_at))
            conn.commit()

        return code

    def redeem_invite_code(self, code: str, driver_id: int) -> Dict[str, Any]:
        """Redeem an invite code to link a driver to a fleet owner"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if code exists and is valid
            cursor.execute('''
                SELECT * FROM invite_codes
                WHERE code = ? AND redeemed_by IS NULL AND expires_at > ?
            ''', (code, datetime.now()))

            invite = cursor.fetchone()
            if not invite:
                return {"success": False, "error": "Invalid or expired invite code"}

            # Mark as redeemed
            cursor.execute('''
                UPDATE invite_codes
                SET redeemed_by = ?, redeemed_at = ?
                WHERE code = ?
            ''', (driver_id, datetime.now(), code))

            conn.commit()

            return {
                "success": True,
                "fleet_owner_id": invite["fleet_owner_id"],
                "message": "Successfully linked to fleet owner"
            }

    def remove_driver(self, driver_id: int, fleet_owner_id: int) -> bool:
        """Remove a driver from fleet (soft delete)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE fleet_drivers
                SET is_active = 0
                WHERE id = ? AND fleet_owner_id = ?
            ''', (driver_id, fleet_owner_id))
            conn.commit()
            return cursor.rowcount > 0


# Singleton instance
_hierarchy_manager = None

def get_hierarchy_manager() -> ProfileHierarchyManager:
    global _hierarchy_manager
    if _hierarchy_manager is None:
        _hierarchy_manager = ProfileHierarchyManager()
    return _hierarchy_manager
```

## Task 22.2: Create Driver Registration Dialog

**Create file**: `c:\D Drive\Predict\driver_registration_dialog.py`

```python
"""
Driver Registration Dialog
UI for fleet owners to add drivers
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QLabel, QMessageBox,
    QTabWidget, QWidget, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class DriverRegistrationDialog(QDialog):
    """Dialog for adding/managing drivers under a fleet owner"""

    driver_added = Signal(dict)  # Emits driver info when added

    def __init__(self, fleet_owner_id: int, parent=None):
        super().__init__(parent)
        self.fleet_owner_id = fleet_owner_id
        self.setWindowTitle("Add Driver")
        self.setMinimumWidth(450)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget for Manual vs Invite
        tabs = QTabWidget()

        # Manual Entry Tab
        manual_tab = QWidget()
        manual_layout = QFormLayout(manual_tab)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Ahmed's Car")
        manual_layout.addRow("Driver Name*:", self.name_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("driver@email.com")
        manual_layout.addRow("Email:", self.email_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("+974 XXXX XXXX")
        manual_layout.addRow("Phone:", self.phone_edit)

        self.relationship_combo = QComboBox()
        self.relationship_combo.addItems(["driver", "child", "employee", "family"])
        manual_layout.addRow("Relationship:", self.relationship_combo)

        add_btn = QPushButton("Add Driver & Generate API Key")
        add_btn.clicked.connect(self.add_driver_manual)
        manual_layout.addRow(add_btn)

        # Result area for showing API key
        self.api_key_result = QTextEdit()
        self.api_key_result.setReadOnly(True)
        self.api_key_result.setMaximumHeight(100)
        self.api_key_result.hide()
        manual_layout.addRow("Generated API Key:", self.api_key_result)

        tabs.addTab(manual_tab, "Manual Entry")

        # Invite Code Tab
        invite_tab = QWidget()
        invite_layout = QVBoxLayout(invite_tab)

        invite_label = QLabel(
            "Generate an invite code that the driver can enter in their\n"
            "PredictOBD app to automatically link to your account."
        )
        invite_layout.addWidget(invite_label)

        self.invite_name_edit = QLineEdit()
        self.invite_name_edit.setPlaceholderText("Driver name (optional)")
        invite_layout.addWidget(self.invite_name_edit)

        generate_btn = QPushButton("Generate Invite Code")
        generate_btn.clicked.connect(self.generate_invite)
        invite_layout.addWidget(generate_btn)

        self.invite_code_result = QLabel()
        self.invite_code_result.setFont(QFont("Consolas", 16, QFont.Bold))
        self.invite_code_result.setAlignment(Qt.AlignCenter)
        self.invite_code_result.setStyleSheet(
            "background: #2a2a2a; color: #4CAF50; padding: 20px; border-radius: 8px;"
        )
        self.invite_code_result.hide()
        invite_layout.addWidget(self.invite_code_result)

        self.invite_info = QLabel()
        self.invite_info.setWordWrap(True)
        self.invite_info.hide()
        invite_layout.addWidget(self.invite_info)

        invite_layout.addStretch()
        tabs.addTab(invite_tab, "Invite Link")

        layout.addWidget(tabs)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def add_driver_manual(self):
        """Add driver via manual entry"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Driver name is required")
            return

        try:
            from profile_hierarchy_manager import get_hierarchy_manager
            manager = get_hierarchy_manager()

            result = manager.add_driver(
                fleet_owner_id=self.fleet_owner_id,
                driver_name=name,
                driver_email=self.email_edit.text().strip() or None,
                driver_phone=self.phone_edit.text().strip() or None,
                relationship=self.relationship_combo.currentText()
            )

            # Show API key (only time it's visible)
            self.api_key_result.setText(
                f"API Key: {result['api_key']}\n\n"
                f"⚠️ IMPORTANT: Copy this key now!\n"
                f"Share it with the driver to enter in their PredictOBD app.\n"
                f"This key will not be shown again."
            )
            self.api_key_result.show()

            self.driver_added.emit(result)

            # Clear form
            self.name_edit.clear()
            self.email_edit.clear()
            self.phone_edit.clear()

        except Exception as e:
            logger.error(f"Error adding driver: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add driver: {e}")

    def generate_invite(self):
        """Generate an invite code"""
        try:
            from profile_hierarchy_manager import get_hierarchy_manager
            manager = get_hierarchy_manager()

            code = manager.generate_invite_code(
                fleet_owner_id=self.fleet_owner_id,
                driver_name=self.invite_name_edit.text().strip() or None
            )

            self.invite_code_result.setText(code)
            self.invite_code_result.show()

            self.invite_info.setText(
                f"Share this code with the driver.\n"
                f"They enter it in PredictOBD app: Settings → Join Fleet\n"
                f"Code expires in 48 hours."
            )
            self.invite_info.show()

        except Exception as e:
            logger.error(f"Error generating invite: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate invite: {e}")
```

## Task 22.3: Add Server Endpoints for Fleet Management

**File**: `C:\OBDserver\Previlium_OBD_Server\main.py`

**Add these endpoints**:

```python
# ============================================================================
# FLEET MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/invite/create")
async def create_invite_code(
    request: Request,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Create an invite code for a new driver"""
    # Verify API key is a fleet owner
    profile = get_profile_by_api_key(api_key)
    if not profile:
        raise HTTPException(401, "Invalid API key")

    data = await request.json()
    driver_name = data.get("driver_name")

    # Generate code
    code = generate_invite_code(profile["id"], driver_name)

    return {"code": code, "expires_in_hours": 48}


@app.post("/api/invite/redeem")
async def redeem_invite_code(request: Request):
    """Redeem an invite code to link driver to fleet owner"""
    data = await request.json()
    code = data.get("code")
    driver_api_key = data.get("api_key")

    if not code or not driver_api_key:
        raise HTTPException(400, "Code and API key required")

    result = redeem_invite(code, driver_api_key)
    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result


@app.get("/api/fleet/drivers")
async def get_fleet_drivers(api_key: str = Header(..., alias="X-API-Key")):
    """Get all drivers under a fleet owner"""
    profile = get_profile_by_api_key(api_key)
    if not profile:
        raise HTTPException(401, "Invalid API key")

    drivers = get_drivers_for_fleet(profile["id"])
    return {"drivers": drivers}


@app.post("/api/fleet/add-driver")
async def add_fleet_driver(
    request: Request,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Manually add a driver to fleet"""
    profile = get_profile_by_api_key(api_key)
    if not profile:
        raise HTTPException(401, "Invalid API key")

    data = await request.json()

    result = create_fleet_driver(
        fleet_owner_id=profile["id"],
        driver_name=data.get("driver_name"),
        driver_email=data.get("email"),
        driver_phone=data.get("phone"),
        relationship=data.get("relationship", "driver")
    )

    return result
```

## Phase 22 Verification Checklist

- [ ] Can add driver via manual entry in Desktop
- [ ] API key is generated and displayed
- [ ] Can generate invite codes
- [ ] PredictOBD app can redeem invite codes
- [ ] Fleet owner can see list of drivers
- [ ] Server endpoints work correctly
- [ ] Database tables created properly

---

# PHASE 23: Desktop - LLM Training Data Editor (Review Mode)

**Priority**: MEDIUM
**Location**: `c:\D Drive\Predict\`
**Purpose**: Allow users to improve AI predictions by describing missed failures

## Task 23.1: Create Training Data Editor Backend

**Create file**: `c:\D Drive\Predict\training_data_editor.py`

```python
"""
Training Data Editor
Allows LLM to suggest training data improvements based on user feedback
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class TrainingDataEditor:
    """Manages training data suggestions and modifications"""

    def __init__(self, data_dir: str = "PredictData/ai/datasets"):
        self.data_dir = data_dir
        self.suggestions_file = os.path.join(data_dir, "pending_suggestions.json")
        self.applied_file = os.path.join(data_dir, "applied_suggestions.json")
        os.makedirs(data_dir, exist_ok=True)

    def get_llm_suggestion(
        self,
        llm_assistant,
        failure_description: str,
        vehicle_info: Dict[str, Any],
        sensor_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ask LLM to suggest training data based on a missed prediction

        Args:
            llm_assistant: The LLM assistant instance
            failure_description: User's description of what failed
            vehicle_info: Make, model, year, mileage
            sensor_data: Optional sensor readings at time of failure

        Returns:
            Suggested training data entry with confidence
        """
        prompt = f"""You are PREDICT's AI training assistant. A prediction was missed and we need to improve the model.

FAILURE CASE:
{failure_description}

VEHICLE:
- Make: {vehicle_info.get('make', 'Unknown')}
- Model: {vehicle_info.get('model', 'Unknown')}
- Year: {vehicle_info.get('year', 'Unknown')}
- Mileage: {vehicle_info.get('mileage', 'Unknown')} km

{f"SENSOR DATA AT FAILURE: {json.dumps(sensor_data, indent=2)}" if sensor_data else ""}

Based on this case, suggest a training data entry to help catch similar patterns in the future.

Respond in this exact JSON format:
{{
    "suggested_label": "component_failure_type",
    "features": {{
        "feature_name": value,
        ...
    }},
    "confidence": 0.0-1.0,
    "reasoning": "Why this pattern matters",
    "related_patterns": ["similar patterns to watch for"],
    "data_collection_tips": "What additional data would help"
}}
"""

        try:
            response = llm_assistant.query(prompt)

            # Parse JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                suggestion = json.loads(json_match.group())
                suggestion["id"] = f"sugg_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                suggestion["failure_description"] = failure_description
                suggestion["vehicle_info"] = vehicle_info
                suggestion["created_at"] = datetime.now().isoformat()
                suggestion["status"] = "pending"

                # Save to pending suggestions
                self._save_suggestion(suggestion)

                return suggestion
            else:
                return {
                    "error": "Could not parse LLM response",
                    "raw_response": response
                }

        except Exception as e:
            logger.error(f"Error getting LLM suggestion: {e}")
            return {"error": str(e)}

    def _save_suggestion(self, suggestion: Dict[str, Any]):
        """Save a pending suggestion"""
        suggestions = self._load_suggestions()
        suggestions.append(suggestion)

        with open(self.suggestions_file, 'w') as f:
            json.dump(suggestions, f, indent=2)

    def _load_suggestions(self) -> List[Dict[str, Any]]:
        """Load pending suggestions"""
        if os.path.exists(self.suggestions_file):
            with open(self.suggestions_file, 'r') as f:
                return json.load(f)
        return []

    def get_pending_suggestions(self) -> List[Dict[str, Any]]:
        """Get all pending suggestions for review"""
        suggestions = self._load_suggestions()
        return [s for s in suggestions if s.get("status") == "pending"]

    def apply_suggestion(self, suggestion_id: str, modified_features: Optional[Dict] = None) -> bool:
        """
        Apply a suggestion to the training dataset

        Args:
            suggestion_id: ID of the suggestion
            modified_features: Optional modifications to features before applying

        Returns:
            True if successfully applied
        """
        suggestions = self._load_suggestions()

        for suggestion in suggestions:
            if suggestion.get("id") == suggestion_id:
                # Apply modifications if provided
                if modified_features:
                    suggestion["features"].update(modified_features)

                # Mark as applied
                suggestion["status"] = "applied"
                suggestion["applied_at"] = datetime.now().isoformat()

                # Add to training dataset
                self._add_to_training_data(suggestion)

                # Save updated suggestions
                with open(self.suggestions_file, 'w') as f:
                    json.dump(suggestions, f, indent=2)

                # Log to applied file
                self._log_applied(suggestion)

                logger.info(f"Applied suggestion {suggestion_id}")
                return True

        return False

    def reject_suggestion(self, suggestion_id: str, reason: str = "") -> bool:
        """Reject a suggestion"""
        suggestions = self._load_suggestions()

        for suggestion in suggestions:
            if suggestion.get("id") == suggestion_id:
                suggestion["status"] = "rejected"
                suggestion["rejected_at"] = datetime.now().isoformat()
                suggestion["rejection_reason"] = reason

                with open(self.suggestions_file, 'w') as f:
                    json.dump(suggestions, f, indent=2)

                return True

        return False

    def _add_to_training_data(self, suggestion: Dict[str, Any]):
        """Add suggestion to actual training dataset"""
        training_file = os.path.join(self.data_dir, "user_feedback_training.jsonl")

        entry = {
            "features": suggestion["features"],
            "label": suggestion["suggested_label"],
            "source": "user_feedback",
            "suggestion_id": suggestion["id"],
            "vehicle": suggestion.get("vehicle_info", {}),
            "timestamp": datetime.now().isoformat()
        }

        with open(training_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def _log_applied(self, suggestion: Dict[str, Any]):
        """Log applied suggestion for audit"""
        applied = []
        if os.path.exists(self.applied_file):
            with open(self.applied_file, 'r') as f:
                applied = json.load(f)

        applied.append(suggestion)

        with open(self.applied_file, 'w') as f:
            json.dump(applied, f, indent=2)


# Singleton
_editor = None

def get_training_editor() -> TrainingDataEditor:
    global _editor
    if _editor is None:
        _editor = TrainingDataEditor()
    return _editor
```

## Task 23.2: Create Training Data Editor Tab UI

**Create file**: `c:\D Drive\Predict\training_data_editor_tab.py`

```python
"""
Training Data Editor Tab
UI for reviewing and applying LLM suggestions
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QLineEdit, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt
import json
import logging

logger = logging.getLogger(__name__)


class TrainingDataEditorTab(QWidget):
    """Tab for reviewing and applying training data suggestions"""

    def __init__(self, llm_assistant=None, parent=None):
        super().__init__(parent)
        self.llm_assistant = llm_assistant
        self.editor = None
        self.current_suggestion = None
        self.setup_ui()
        self._init_editor()

    def _init_editor(self):
        """Initialize the training data editor"""
        try:
            from training_data_editor import get_training_editor
            self.editor = get_training_editor()
            self._refresh_suggestions()
        except Exception as e:
            logger.error(f"Failed to initialize editor: {e}")

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("LLM Training Data Editor")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        description = QLabel(
            "Describe failures the AI missed, and the LLM will suggest training data improvements.\n"
            "Review suggestions carefully before applying them to the training dataset."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # Splitter for input and suggestions
        splitter = QSplitter(Qt.Vertical)

        # Input section
        input_group = QGroupBox("Describe Missed Prediction")
        input_layout = QVBoxLayout(input_group)

        self.failure_input = QTextEdit()
        self.failure_input.setPlaceholderText(
            "Describe what failed and when...\n\n"
            "Example: The battery failed suddenly after 3 years. The car had been showing "
            "slow cranking for 2 weeks but no warning was given. Voltage readings were "
            "around 12.1V during this period."
        )
        self.failure_input.setMaximumHeight(150)
        input_layout.addWidget(self.failure_input)

        # Vehicle info
        vehicle_layout = QHBoxLayout()
        self.make_edit = QLineEdit()
        self.make_edit.setPlaceholderText("Make")
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Model")
        self.year_edit = QLineEdit()
        self.year_edit.setPlaceholderText("Year")
        self.mileage_edit = QLineEdit()
        self.mileage_edit.setPlaceholderText("Mileage (km)")
        vehicle_layout.addWidget(self.make_edit)
        vehicle_layout.addWidget(self.model_edit)
        vehicle_layout.addWidget(self.year_edit)
        vehicle_layout.addWidget(self.mileage_edit)
        input_layout.addLayout(vehicle_layout)

        get_suggestion_btn = QPushButton("Get LLM Suggestion")
        get_suggestion_btn.clicked.connect(self._get_suggestion)
        input_layout.addWidget(get_suggestion_btn)

        splitter.addWidget(input_group)

        # Suggestions table
        suggestions_group = QGroupBox("Pending Suggestions")
        suggestions_layout = QVBoxLayout(suggestions_group)

        self.suggestions_table = QTableWidget()
        self.suggestions_table.setColumnCount(5)
        self.suggestions_table.setHorizontalHeaderLabels([
            "ID", "Label", "Confidence", "Created", "Status"
        ])
        self.suggestions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.suggestions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.suggestions_table.itemSelectionChanged.connect(self._on_selection_changed)
        suggestions_layout.addWidget(self.suggestions_table)

        splitter.addWidget(suggestions_group)

        # Suggestion detail
        detail_group = QGroupBox("Suggestion Details")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.apply_btn = QPushButton("✓ Apply Suggestion")
        self.apply_btn.clicked.connect(self._apply_suggestion)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("background: #4CAF50; color: white;")
        btn_layout.addWidget(self.apply_btn)

        self.reject_btn = QPushButton("✗ Reject")
        self.reject_btn.clicked.connect(self._reject_suggestion)
        self.reject_btn.setEnabled(False)
        self.reject_btn.setStyleSheet("background: #F44336; color: white;")
        btn_layout.addWidget(self.reject_btn)

        detail_layout.addLayout(btn_layout)

        splitter.addWidget(detail_group)

        layout.addWidget(splitter)

    def _get_suggestion(self):
        """Get LLM suggestion for the described failure"""
        if not self.editor or not self.llm_assistant:
            QMessageBox.warning(self, "Error", "LLM assistant not available")
            return

        description = self.failure_input.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "Error", "Please describe the failure")
            return

        vehicle_info = {
            "make": self.make_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "year": self.year_edit.text().strip(),
            "mileage": self.mileage_edit.text().strip()
        }

        try:
            suggestion = self.editor.get_llm_suggestion(
                llm_assistant=self.llm_assistant,
                failure_description=description,
                vehicle_info=vehicle_info
            )

            if "error" in suggestion:
                QMessageBox.warning(self, "Error", suggestion["error"])
            else:
                QMessageBox.information(
                    self, "Suggestion Generated",
                    f"New suggestion created: {suggestion.get('suggested_label', 'Unknown')}\n\n"
                    f"Confidence: {suggestion.get('confidence', 0):.0%}\n\n"
                    f"Please review in the table below."
                )
                self._refresh_suggestions()

        except Exception as e:
            logger.error(f"Error getting suggestion: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _refresh_suggestions(self):
        """Refresh the suggestions table"""
        if not self.editor:
            return

        suggestions = self.editor.get_pending_suggestions()
        self.suggestions_table.setRowCount(len(suggestions))

        for row, sugg in enumerate(suggestions):
            self.suggestions_table.setItem(row, 0, QTableWidgetItem(sugg.get("id", "")))
            self.suggestions_table.setItem(row, 1, QTableWidgetItem(sugg.get("suggested_label", "")))
            self.suggestions_table.setItem(row, 2, QTableWidgetItem(f"{sugg.get('confidence', 0):.0%}"))
            self.suggestions_table.setItem(row, 3, QTableWidgetItem(sugg.get("created_at", "")[:10]))
            self.suggestions_table.setItem(row, 4, QTableWidgetItem(sugg.get("status", "")))

    def _on_selection_changed(self):
        """Handle selection change in suggestions table"""
        selected = self.suggestions_table.selectedItems()
        if not selected:
            self.current_suggestion = None
            self.detail_text.clear()
            self.apply_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            return

        row = selected[0].row()
        suggestion_id = self.suggestions_table.item(row, 0).text()

        # Find full suggestion
        suggestions = self.editor.get_pending_suggestions()
        for sugg in suggestions:
            if sugg.get("id") == suggestion_id:
                self.current_suggestion = sugg
                self._show_suggestion_detail(sugg)
                self.apply_btn.setEnabled(True)
                self.reject_btn.setEnabled(True)
                break

    def _show_suggestion_detail(self, suggestion: dict):
        """Display suggestion details"""
        detail = f"""
SUGGESTED LABEL: {suggestion.get('suggested_label', 'Unknown')}

CONFIDENCE: {suggestion.get('confidence', 0):.0%}

FEATURES:
{json.dumps(suggestion.get('features', {}), indent=2)}

REASONING:
{suggestion.get('reasoning', 'No reasoning provided')}

RELATED PATTERNS:
{chr(10).join('• ' + p for p in suggestion.get('related_patterns', []))}

DATA COLLECTION TIPS:
{suggestion.get('data_collection_tips', 'None')}

ORIGINAL FAILURE DESCRIPTION:
{suggestion.get('failure_description', 'N/A')}

VEHICLE: {suggestion.get('vehicle_info', {})}
"""
        self.detail_text.setText(detail)

    def _apply_suggestion(self):
        """Apply the selected suggestion"""
        if not self.current_suggestion:
            return

        reply = QMessageBox.question(
            self, "Confirm Apply",
            f"Apply this suggestion to the training dataset?\n\n"
            f"Label: {self.current_suggestion.get('suggested_label')}\n"
            f"Confidence: {self.current_suggestion.get('confidence', 0):.0%}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.editor.apply_suggestion(self.current_suggestion["id"])
            if success:
                QMessageBox.information(self, "Success", "Suggestion applied to training data")
                self._refresh_suggestions()
                self.detail_text.clear()
                self.current_suggestion = None
            else:
                QMessageBox.warning(self, "Error", "Failed to apply suggestion")

    def _reject_suggestion(self):
        """Reject the selected suggestion"""
        if not self.current_suggestion:
            return

        success = self.editor.reject_suggestion(
            self.current_suggestion["id"],
            reason="User rejected"
        )
        if success:
            self._refresh_suggestions()
            self.detail_text.clear()
            self.current_suggestion = None
```

## Phase 23 Verification Checklist

- [ ] Training Data Editor tab appears in Desktop app
- [ ] Can describe a missed failure
- [ ] LLM generates suggestion with features
- [ ] Suggestions appear in table
- [ ] Can view suggestion details
- [ ] Can apply suggestion (adds to training data)
- [ ] Can reject suggestion
- [ ] Applied suggestions saved to user_feedback_training.jsonl

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 7: COMMERCIAL LAUNCH PREPARATION (Phases 24-31)
# Required for accepting real payments and public launch
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 24: User Authentication System

**Priority**: HIGH - REQUIRED BEFORE LAUNCH
**Affects**: All 4 applications
**Goal**: Implement secure user registration, login, and session management

## Task 24.1: Server Authentication Backend

**File**: `C:\OBDserver\Previlium_OBD_Server\auth.py` (NEW)

```python
"""
User Authentication System
Handles registration, login, password reset, and session management
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer
import sqlite3
import smtplib
from email.mime.text import MIMEText
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = secrets.token_hex(32)  # Generate once and store securely
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

security = HTTPBearer()


class AuthManager:
    """Manages user authentication"""

    def __init__(self, db_path: str = "predict_users.db"):
        self.db_path = db_path
        self._init_auth_tables()

    def _init_auth_tables(self):
        """Create authentication tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    role TEXT DEFAULT 'user',
                    subscription_tier TEXT DEFAULT 'free',
                    subscription_expires TIMESTAMP,
                    email_verified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')

            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    device_info TEXT,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_valid INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Password reset tokens
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Email verification tokens
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    verified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            conn.commit()

    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        hash_value = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000
        )
        return f"{salt}:{hash_value.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        try:
            salt, hash_value = stored_hash.split(':')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256', password.encode(), salt.encode(), 100000
            )
            return new_hash.hex() == hash_value
        except:
            return False

    def register_user(
        self,
        email: str,
        password: str,
        name: str,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a new user"""
        # Validate email format
        if '@' not in email or '.' not in email:
            return {"success": False, "error": "Invalid email format"}

        # Validate password strength
        if len(password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        password_hash = self.hash_password(password)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (email, password_hash, name, phone)
                    VALUES (?, ?, ?, ?)
                ''', (email.lower(), password_hash, name, phone))
                user_id = cursor.lastrowid
                conn.commit()

            # Send verification email
            self._send_verification_email(user_id, email)

            return {
                "success": True,
                "user_id": user_id,
                "message": "Registration successful. Please verify your email."
            }

        except sqlite3.IntegrityError:
            return {"success": False, "error": "Email already registered"}
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {"success": False, "error": str(e)}

    def login(
        self,
        email: str,
        password: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Authenticate user and return JWT token"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM users WHERE email = ? AND is_active = 1
            ''', (email.lower(),))
            user = cursor.fetchone()

            if not user:
                return {"success": False, "error": "Invalid email or password"}

            if not self.verify_password(password, user["password_hash"]):
                return {"success": False, "error": "Invalid email or password"}

            # Generate JWT token
            token_data = {
                "user_id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "tier": user["subscription_tier"],
                "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
            }
            token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

            # Store session
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.now() + timedelta(hours=JWT_EXPIRY_HOURS)

            cursor.execute('''
                INSERT INTO sessions (user_id, token_hash, device_info, ip_address, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user["id"], token_hash, device_info, ip_address, expires_at))

            # Update last login
            cursor.execute('''
                UPDATE users SET last_login = ? WHERE id = ?
            ''', (datetime.now(), user["id"]))

            conn.commit()

            return {
                "success": True,
                "token": token,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                    "subscription_tier": user["subscription_tier"],
                    "email_verified": bool(user["email_verified"])
                }
            }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return user data"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            # Check if session is still valid
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT is_valid FROM sessions
                    WHERE token_hash = ? AND is_valid = 1 AND expires_at > ?
                ''', (token_hash, datetime.now()))

                if not cursor.fetchone():
                    return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def logout(self, token: str) -> bool:
        """Invalidate session"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sessions SET is_valid = 0 WHERE token_hash = ?
            ''', (token_hash,))
            conn.commit()
            return cursor.rowcount > 0

    def request_password_reset(self, email: str) -> Dict[str, Any]:
        """Generate password reset token and send email"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM users WHERE email = ?', (email.lower(),))
            user = cursor.fetchone()

            if not user:
                # Don't reveal if email exists
                return {"success": True, "message": "If email exists, reset link sent"}

            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            expires_at = datetime.now() + timedelta(hours=1)

            cursor.execute('''
                INSERT INTO password_resets (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
            ''', (user["id"], token_hash, expires_at))
            conn.commit()

            # Send reset email
            self._send_reset_email(email, reset_token)

            return {"success": True, "message": "If email exists, reset link sent"}

    def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """Reset password using token"""
        if len(new_password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT user_id FROM password_resets
                WHERE token_hash = ? AND used = 0 AND expires_at > ?
            ''', (token_hash, datetime.now()))
            reset = cursor.fetchone()

            if not reset:
                return {"success": False, "error": "Invalid or expired reset token"}

            # Update password
            new_hash = self.hash_password(new_password)
            cursor.execute('''
                UPDATE users SET password_hash = ? WHERE id = ?
            ''', (new_hash, reset["user_id"]))

            # Mark token as used
            cursor.execute('''
                UPDATE password_resets SET used = 1 WHERE token_hash = ?
            ''', (token_hash,))

            # Invalidate all sessions
            cursor.execute('''
                UPDATE sessions SET is_valid = 0 WHERE user_id = ?
            ''', (reset["user_id"],))

            conn.commit()

            return {"success": True, "message": "Password reset successful"}

    def _send_verification_email(self, user_id: int, email: str):
        """Send email verification link"""
        # Implementation depends on your email service (SendGrid, SES, etc.)
        pass

    def _send_reset_email(self, email: str, token: str):
        """Send password reset email"""
        # Implementation depends on your email service
        pass


# Singleton
_auth_manager = None

def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


# FastAPI dependency
async def get_current_user(authorization: str = Header(...)) -> Dict[str, Any]:
    """Dependency to get current authenticated user"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")

    token = authorization.split(" ")[1]
    user = get_auth_manager().verify_token(token)

    if not user:
        raise HTTPException(401, "Invalid or expired token")

    return user
```

## Task 24.2: Add Auth Endpoints to Server

**File**: `C:\OBDserver\Previlium_OBD_Server\main.py`

**Add these endpoints**:

```python
from auth import get_auth_manager, get_current_user

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/auth/register")
async def register(request: Request):
    """Register new user"""
    data = await request.json()
    auth = get_auth_manager()

    result = auth.register_user(
        email=data.get("email"),
        password=data.get("password"),
        name=data.get("name"),
        phone=data.get("phone")
    )

    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result


@app.post("/api/auth/login")
async def login(request: Request):
    """User login"""
    data = await request.json()
    auth = get_auth_manager()

    result = auth.login(
        email=data.get("email"),
        password=data.get("password"),
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host
    )

    if not result["success"]:
        raise HTTPException(401, result["error"])

    return result


@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """User logout"""
    # Token invalidation handled by dependency
    return {"success": True, "message": "Logged out"}


@app.post("/api/auth/forgot-password")
async def forgot_password(request: Request):
    """Request password reset"""
    data = await request.json()
    auth = get_auth_manager()
    return auth.request_password_reset(data.get("email"))


@app.post("/api/auth/reset-password")
async def reset_password(request: Request):
    """Reset password with token"""
    data = await request.json()
    auth = get_auth_manager()

    result = auth.reset_password(
        token=data.get("token"),
        new_password=data.get("new_password")
    )

    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return current_user
```

## Task 24.3: Android App Login Screen (PredictOBD)

**Create file**: `C:\Predict\PredictOBD\app\src\main\java\com\omar\predictobd\ui\screens\auth\LoginScreen.kt`

```kotlin
package com.omar.predictobd.ui.screens.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    onRegisterClick: () -> Unit,
    viewModel: AuthViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }

    LaunchedEffect(uiState) {
        if (uiState is AuthUiState.Success) {
            onLoginSuccess()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Logo
        Text(
            text = "PREDICT",
            style = MaterialTheme.typography.headlineLarge
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Email field
        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            leadingIcon = { Icon(Icons.Default.Email, null) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Password field
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            leadingIcon = { Icon(Icons.Default.Lock, null) },
            trailingIcon = {
                IconButton(onClick = { showPassword = !showPassword }) {
                    Icon(
                        if (showPassword) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                        null
                    )
                }
            },
            visualTransformation = if (showPassword) VisualTransformation.None
                else PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Forgot password
        TextButton(
            onClick = { /* Navigate to forgot password */ },
            modifier = Modifier.align(Alignment.End)
        ) {
            Text("Forgot Password?")
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Login button
        Button(
            onClick = { viewModel.login(email, password) },
            enabled = email.isNotBlank() && password.isNotBlank() &&
                    uiState !is AuthUiState.Loading,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (uiState is AuthUiState.Loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text("Login")
            }
        }

        // Error message
        if (uiState is AuthUiState.Error) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = (uiState as AuthUiState.Error).message,
                color = MaterialTheme.colorScheme.error
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Register link
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Don't have an account?")
            TextButton(onClick = onRegisterClick) {
                Text("Register")
            }
        }
    }
}
```

## Phase 24 Verification Checklist

- [ ] User can register with email/password
- [ ] Email verification sent
- [ ] User can login and receive JWT token
- [ ] Token stored securely on device
- [ ] Protected endpoints require valid token
- [ ] Password reset flow works
- [ ] Logout invalidates session
- [ ] Login screen works on Android apps

---

# PHASE 25: Payment Integration (Stripe)

**Priority**: HIGH - REQUIRED BEFORE LAUNCH
**Affects**: Server, Desktop, Android apps
**Goal**: Accept payments and manage subscriptions

## Task 25.1: Stripe Backend Integration

**File**: `C:\OBDserver\Previlium_OBD_Server\payments.py` (NEW)

```python
"""
Payment System with Stripe
Handles subscriptions, one-time payments, and billing
"""

import stripe
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = "sk_test_YOUR_STRIPE_SECRET_KEY"  # Use env variable in production

# Subscription tiers
SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "features": ["1 vehicle", "Basic predictions", "DTC reading"],
        "vehicle_limit": 1,
        "stripe_price_id": None
    },
    "basic": {
        "name": "Basic",
        "price_monthly": 9.99,
        "price_yearly": 99.99,
        "features": ["3 vehicles", "AI predictions", "Maintenance reminders", "Email support"],
        "vehicle_limit": 3,
        "stripe_price_id_monthly": "price_basic_monthly",
        "stripe_price_id_yearly": "price_basic_yearly"
    },
    "premium": {
        "name": "Premium",
        "price_monthly": 19.99,
        "price_yearly": 199.99,
        "features": ["10 vehicles", "AI chat", "Priority support", "API access", "Fleet management"],
        "vehicle_limit": 10,
        "stripe_price_id_monthly": "price_premium_monthly",
        "stripe_price_id_yearly": "price_premium_yearly"
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 49.99,
        "price_yearly": 499.99,
        "features": ["Unlimited vehicles", "Custom integrations", "Dedicated support", "SLA"],
        "vehicle_limit": 999,
        "stripe_price_id_monthly": "price_enterprise_monthly",
        "stripe_price_id_yearly": "price_enterprise_yearly"
    }
}


class PaymentManager:
    """Manages payments and subscriptions"""

    def __init__(self, db_path: str = "predict_users.db"):
        self.db_path = db_path
        self._init_payment_tables()

    def _init_payment_tables(self):
        """Create payment tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Subscriptions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    tier TEXT NOT NULL DEFAULT 'free',
                    billing_cycle TEXT DEFAULT 'monthly',
                    status TEXT DEFAULT 'active',
                    current_period_start TIMESTAMP,
                    current_period_end TIMESTAMP,
                    cancel_at_period_end INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Payment history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stripe_payment_id TEXT,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'usd',
                    status TEXT NOT NULL,
                    description TEXT,
                    invoice_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            conn.commit()

    def create_checkout_session(
        self,
        user_id: int,
        tier: str,
        billing_cycle: str = "monthly",
        success_url: str = "https://predict.app/success",
        cancel_url: str = "https://predict.app/cancel"
    ) -> Dict[str, Any]:
        """Create Stripe checkout session"""
        if tier not in SUBSCRIPTION_TIERS or tier == "free":
            return {"success": False, "error": "Invalid subscription tier"}

        tier_info = SUBSCRIPTION_TIERS[tier]
        price_id = tier_info.get(f"stripe_price_id_{billing_cycle}")

        if not price_id:
            return {"success": False, "error": "Invalid billing cycle"}

        try:
            # Get or create Stripe customer
            customer_id = self._get_or_create_customer(user_id)

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata={
                    'user_id': user_id,
                    'tier': tier,
                    'billing_cycle': billing_cycle
                }
            )

            return {
                "success": True,
                "checkout_url": session.url,
                "session_id": session.id
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return {"success": False, "error": str(e)}

    def _get_or_create_customer(self, user_id: int) -> str:
        """Get existing or create new Stripe customer"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if customer exists
            cursor.execute('''
                SELECT stripe_customer_id FROM subscriptions WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()

            if result and result["stripe_customer_id"]:
                return result["stripe_customer_id"]

            # Get user info
            cursor.execute('SELECT email, name FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()

            # Create Stripe customer
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["name"],
                metadata={"user_id": user_id}
            )

            # Store customer ID
            cursor.execute('''
                INSERT OR REPLACE INTO subscriptions (user_id, stripe_customer_id, tier)
                VALUES (?, ?, 'free')
            ''', (user_id, customer.id))
            conn.commit()

            return customer.id

    def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        webhook_secret = "whsec_YOUR_WEBHOOK_SECRET"

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError:
            return {"success": False, "error": "Invalid signature"}

        # Handle events
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            self._handle_successful_checkout(session)

        elif event['type'] == 'invoice.paid':
            invoice = event['data']['object']
            self._handle_invoice_paid(invoice)

        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            self._handle_subscription_updated(subscription)

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            self._handle_subscription_cancelled(subscription)

        return {"success": True, "event": event['type']}

    def _handle_successful_checkout(self, session):
        """Handle successful checkout"""
        user_id = session['metadata']['user_id']
        tier = session['metadata']['tier']
        billing_cycle = session['metadata']['billing_cycle']

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Update subscription
            cursor.execute('''
                UPDATE subscriptions
                SET tier = ?, billing_cycle = ?, status = 'active',
                    stripe_subscription_id = ?, updated_at = ?
                WHERE user_id = ?
            ''', (tier, billing_cycle, session.get('subscription'),
                  datetime.now(), user_id))

            # Update user tier
            cursor.execute('''
                UPDATE users SET subscription_tier = ? WHERE id = ?
            ''', (tier, user_id))

            conn.commit()

    def get_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """Get user's subscription status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM subscriptions WHERE user_id = ?
            ''', (user_id,))
            sub = cursor.fetchone()

            if not sub:
                return {
                    "tier": "free",
                    "status": "active",
                    "features": SUBSCRIPTION_TIERS["free"]["features"],
                    "vehicle_limit": 1
                }

            tier_info = SUBSCRIPTION_TIERS.get(sub["tier"], SUBSCRIPTION_TIERS["free"])

            return {
                "tier": sub["tier"],
                "tier_name": tier_info["name"],
                "status": sub["status"],
                "billing_cycle": sub["billing_cycle"],
                "features": tier_info["features"],
                "vehicle_limit": tier_info["vehicle_limit"],
                "current_period_end": sub["current_period_end"],
                "cancel_at_period_end": bool(sub["cancel_at_period_end"])
            }

    def cancel_subscription(self, user_id: int) -> Dict[str, Any]:
        """Cancel subscription at period end"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT stripe_subscription_id FROM subscriptions WHERE user_id = ?
            ''', (user_id,))
            sub = cursor.fetchone()

            if not sub or not sub["stripe_subscription_id"]:
                return {"success": False, "error": "No active subscription"}

            try:
                # Cancel at period end (not immediately)
                stripe.Subscription.modify(
                    sub["stripe_subscription_id"],
                    cancel_at_period_end=True
                )

                cursor.execute('''
                    UPDATE subscriptions SET cancel_at_period_end = 1, updated_at = ?
                    WHERE user_id = ?
                ''', (datetime.now(), user_id))
                conn.commit()

                return {"success": True, "message": "Subscription will cancel at period end"}

            except stripe.error.StripeError as e:
                return {"success": False, "error": str(e)}


# Singleton
_payment_manager = None

def get_payment_manager() -> PaymentManager:
    global _payment_manager
    if _payment_manager is None:
        _payment_manager = PaymentManager()
    return _payment_manager
```

## Task 25.2: Add Payment Endpoints

**File**: `C:\OBDserver\Previlium_OBD_Server\main.py`

**Add**:
```python
from payments import get_payment_manager, SUBSCRIPTION_TIERS

@app.get("/api/subscriptions/tiers")
async def get_subscription_tiers():
    """Get available subscription tiers"""
    return {"tiers": SUBSCRIPTION_TIERS}


@app.post("/api/subscriptions/checkout")
async def create_checkout(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Create Stripe checkout session"""
    data = await request.json()
    payments = get_payment_manager()

    result = payments.create_checkout_session(
        user_id=current_user["user_id"],
        tier=data.get("tier"),
        billing_cycle=data.get("billing_cycle", "monthly")
    )

    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result


@app.get("/api/subscriptions/status")
async def get_subscription_status(current_user: dict = Depends(get_current_user)):
    """Get current subscription status"""
    payments = get_payment_manager()
    return payments.get_subscription_status(current_user["user_id"])


@app.post("/api/subscriptions/cancel")
async def cancel_subscription(current_user: dict = Depends(get_current_user)):
    """Cancel subscription"""
    payments = get_payment_manager()
    result = payments.cancel_subscription(current_user["user_id"])

    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    payments = get_payment_manager()
    result = payments.handle_webhook(payload, sig_header)

    if not result["success"]:
        raise HTTPException(400, result["error"])

    return result
```

## Phase 25 Verification Checklist

- [ ] Stripe account created and API keys configured
- [ ] Subscription tiers defined in Stripe dashboard
- [ ] Checkout session creates successfully
- [ ] Webhook receives payment events
- [ ] Subscription status updates after payment
- [ ] User tier updates in database
- [ ] Cancel subscription works
- [ ] Payment history recorded

---

# PHASE 26: Production Server Setup

**Priority**: HIGH - REQUIRED BEFORE LAUNCH
**Goal**: Deploy server to cloud with PostgreSQL

## Task 26.1: PostgreSQL Migration

**File**: `C:\OBDserver\Previlium_OBD_Server\database_postgres.py` (NEW)

```python
"""
PostgreSQL Database Configuration
Production-ready database setup
"""

import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from databases import Database
import asyncpg

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/predict_db"
)

# Async database connection
database = Database(DATABASE_URL)

# SQLAlchemy engine for migrations
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()


async def connect_db():
    """Connect to database on startup"""
    await database.connect()


async def disconnect_db():
    """Disconnect from database on shutdown"""
    await database.disconnect()


def get_db():
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Task 26.2: Docker Configuration

**File**: `C:\OBDserver\Previlium_OBD_Server\Dockerfile` (NEW)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with gunicorn
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

**File**: `C:\OBDserver\Previlium_OBD_Server\docker-compose.yml` (NEW)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: predict_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: predict_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  server:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://predict_user:${DB_PASSWORD}@db:5432/predict_db
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
    depends_on:
      - db
      - redis
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - server

volumes:
  postgres_data:
```

## Phase 26 Verification Checklist

- [ ] PostgreSQL database created
- [ ] Data migrated from SQLite
- [ ] Docker containers build successfully
- [ ] Server runs on cloud (AWS/Azure/DigitalOcean)
- [ ] Database accessible from server
- [ ] Environment variables configured
- [ ] Health check endpoint works

---

# PHASE 27: Security Hardening

**Priority**: HIGH
**Goal**: Implement SSL, encryption, rate limiting

## Task 27.1: Rate Limiting Enhancement

**File**: `C:\OBDserver\Previlium_OBD_Server\security.py` (NEW)

```python
"""
Security Enhancements
Rate limiting, IP blocking, request validation
"""

from fastapi import Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import time
from collections import defaultdict
import asyncio
import hashlib
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self):
        self.requests = defaultdict(list)
        self.blocked_ips = set()

    def is_allowed(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> bool:
        """Check if request is allowed"""
        if key in self.blocked_ips:
            return False

        now = time.time()
        window_start = now - window_seconds

        # Clean old requests
        self.requests[key] = [
            t for t in self.requests[key] if t > window_start
        ]

        if len(self.requests[key]) >= max_requests:
            # Temporarily block if too many requests
            if len(self.requests[key]) >= max_requests * 2:
                self.blocked_ips.add(key)
                logger.warning(f"Blocked IP: {key}")
            return False

        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_ip = request.client.host

    # Different limits for different endpoints
    if "/api/auth" in request.url.path:
        allowed = rate_limiter.is_allowed(client_ip, max_requests=10, window_seconds=60)
    elif "/api/obd" in request.url.path:
        allowed = rate_limiter.is_allowed(client_ip, max_requests=300, window_seconds=60)
    else:
        allowed = rate_limiter.is_allowed(client_ip, max_requests=60, window_seconds=60)

    if not allowed:
        raise HTTPException(429, "Too many requests")

    response = await call_next(request)
    return response


def setup_cors(app):
    """Configure CORS"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://predict.app",
            "https://www.predict.app",
            "http://localhost:3000",  # Dev only
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def encrypt_sensitive_data(data: str, key: str) -> str:
    """Encrypt sensitive data"""
    from cryptography.fernet import Fernet
    f = Fernet(key.encode())
    return f.encrypt(data.encode()).decode()


def decrypt_sensitive_data(encrypted: str, key: str) -> str:
    """Decrypt sensitive data"""
    from cryptography.fernet import Fernet
    f = Fernet(key.encode())
    return f.decrypt(encrypted.encode()).decode()
```

## Phase 27 Verification Checklist

- [ ] SSL certificate installed (Let's Encrypt)
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] Rate limiting blocks excessive requests
- [ ] CORS configured for production domains only
- [ ] Sensitive data encrypted in database
- [ ] SQL injection protection verified
- [ ] XSS protection headers set

---

# PHASE 28: Monitoring & Error Tracking

**Priority**: MEDIUM
**Goal**: Set up Sentry and logging

## Task 28.1: Sentry Integration

**File**: `C:\OBDserver\Previlium_OBD_Server\monitoring.py` (NEW)

```python
"""
Monitoring and Error Tracking
Sentry integration, metrics, health checks
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
import os
import psutil
import time
from datetime import datetime

# Initialize Sentry
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions
    environment=os.getenv("ENVIRONMENT", "development")
)


def get_system_health() -> dict:
    """Get system health metrics"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "uptime_seconds": time.time() - psutil.boot_time()
    }


def log_metric(name: str, value: float, tags: dict = None):
    """Log custom metric"""
    # Can integrate with DataDog, CloudWatch, etc.
    pass
```

**Add to main.py**:
```python
from monitoring import get_system_health

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    return get_system_health()
```

## Phase 28 Verification Checklist

- [ ] Sentry account created
- [ ] Errors appear in Sentry dashboard
- [ ] Health endpoint returns system metrics
- [ ] Alerts configured for critical errors
- [ ] Performance monitoring enabled

---

# PHASE 29: Legal Compliance

**Priority**: MEDIUM
**Goal**: Privacy policy, terms of service, GDPR compliance

## Task 29.1: Privacy Policy Endpoint

**Add to server**:
```python
@app.get("/api/legal/privacy-policy")
async def get_privacy_policy():
    """Get privacy policy"""
    return {
        "version": "1.0",
        "effective_date": "2026-01-01",
        "content": """
        PREDICT Privacy Policy

        1. DATA WE COLLECT
        - Vehicle diagnostic data (OBD-II readings)
        - Location data (for geofencing features)
        - Account information (email, name)

        2. HOW WE USE YOUR DATA
        - Predict vehicle failures
        - Provide maintenance recommendations
        - Fleet monitoring (if enabled)

        3. DATA SHARING
        - We do not sell your personal data
        - Fleet managers can see driver data (with consent)

        4. DATA RETENTION
        - Vehicle data: 2 years
        - Account data: Until account deletion

        5. YOUR RIGHTS
        - Access your data
        - Delete your account
        - Export your data

        6. CONTACT
        - privacy@predict.app
        """
    }


@app.get("/api/legal/terms-of-service")
async def get_terms():
    """Get terms of service"""
    return {
        "version": "1.0",
        "effective_date": "2026-01-01",
        "content": "..."  # Full ToS
    }


@app.post("/api/user/export-data")
async def export_user_data(current_user: dict = Depends(get_current_user)):
    """Export all user data (GDPR compliance)"""
    # Gather all user data
    # Return as JSON or generate download link
    pass


@app.delete("/api/user/delete-account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """Delete user account and all data"""
    # Soft delete first, hard delete after 30 days
    pass
```

## Phase 29 Verification Checklist

- [ ] Privacy policy written and reviewed
- [ ] Terms of service written and reviewed
- [ ] Users must accept ToS on registration
- [ ] Data export feature works
- [ ] Account deletion feature works
- [ ] Cookie consent banner (if web app)

---

# PHASE 30: Testing Suite

**Priority**: MEDIUM
**Goal**: Unit and integration tests

## Task 30.1: Server Tests

**File**: `C:\OBDserver\Previlium_OBD_Server\tests\test_auth.py` (NEW)

```python
"""
Authentication Tests
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_register_user():
    """Test user registration"""
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "securepassword123",
        "name": "Test User"
    })
    assert response.status_code == 200
    assert response.json()["success"] == True


def test_login():
    """Test user login"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword123"
    })
    assert response.status_code == 200
    assert "token" in response.json()


def test_invalid_login():
    """Test invalid login"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_protected_endpoint_without_token():
    """Test accessing protected endpoint without token"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_with_token():
    """Test accessing protected endpoint with valid token"""
    # Login first
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "securepassword123"
    })
    token = login_response.json()["token"]

    # Access protected endpoint
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

## Phase 30 Verification Checklist

- [ ] Unit tests for auth module
- [ ] Unit tests for payment module
- [ ] Integration tests for API endpoints
- [ ] Test coverage > 70%
- [ ] CI pipeline runs tests on push
- [ ] All tests pass

---

# PHASE 31: User Documentation & Onboarding

**Priority**: LOW
**Goal**: Help users get started

## Task 31.1: In-App Onboarding

**Android onboarding screen**:
```kotlin
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit
) {
    val pages = listOf(
        OnboardingPage(
            title = "Welcome to PREDICT",
            description = "AI-powered vehicle health monitoring",
            image = R.drawable.onboarding_1
        ),
        OnboardingPage(
            title = "Connect Your OBD Device",
            description = "Plug in any ELM327 compatible adapter",
            image = R.drawable.onboarding_2
        ),
        OnboardingPage(
            title = "Get Predictions",
            description = "Know about failures 7-30 days in advance",
            image = R.drawable.onboarding_3
        )
    )

    // HorizontalPager with pages
    // "Get Started" button on last page
}
```

## Phase 31 Verification Checklist

- [ ] Onboarding screens in Android apps
- [ ] FAQ section in app
- [ ] Help/Support button links to documentation
- [ ] Video tutorials created (optional)

---

# ═══════════════════════════════════════════════════════════════════════
# PRIORITY 8: POST-LAUNCH & SCALE (Phases 32-38)
# For after initial launch with real users
# ═══════════════════════════════════════════════════════════════════════

---

# PHASE 32: Hardware Sensor Integration (ESP32/RPi)

**Priority**: FUTURE (After software complete)
**Goal**: Custom sensor hardware for advanced predictions

## Recommended Hardware

### Main Controller Options:
| Option | Pros | Cons | Cost |
|--------|------|------|------|
| **ESP32-S3** | WiFi/BLE, low power, small | Limited processing | ~$8 |
| **Raspberry Pi 5 4GB** | Full Linux, high power | Higher power draw, larger | ~$60 |
| **Arduino Nano 33 IoT** | Simple, reliable | Limited connectivity | ~$25 |

**Recommendation**: ESP32-S3 for most use cases, RPi 5 only if complex local AI needed.

### Sensors Needed:
| Sensor | Purpose | Model | Cost |
|--------|---------|-------|------|
| Brake Temp (x2) | Brake wear prediction | MLX90614 IR | ~$15 ea |
| Fuel Pump Current | Pump health | ACS712 20A | ~$5 |
| Engine Vibration (x2) | Bearing/mount wear | MPU6050 + piezo | ~$8 ea |
| Transmission Vibration | Gearbox health | ADXL345 | ~$10 |
| Ambient Temp | Calibration | DHT22 | ~$5 |
| GPS Module | Location accuracy | NEO-6M | ~$12 |

### Total BOM Cost: ~$85-150

## Task 32.1: ESP32 Firmware

```cpp
// esp32_sensor_firmware.ino
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <MPU6050.h>

// Sensors
Adafruit_MLX90614 brakeTempLeft;
Adafruit_MLX90614 brakeTempRight;
MPU6050 engineVibration;

// Server config
const char* serverUrl = "https://api.predict.app/api/sensors/data";
String apiKey = "";

void setup() {
    Serial.begin(115200);
    Wire.begin();

    // Init sensors
    brakeTempLeft.begin(0x5A);
    brakeTempRight.begin(0x5B);
    engineVibration.initialize();

    // Connect WiFi
    WiFi.begin(ssid, password);
}

void loop() {
    // Read sensors
    float brakeLeftTemp = brakeTempLeft.readObjectTempC();
    float brakeRightTemp = brakeTempRight.readObjectTempC();

    int16_t ax, ay, az;
    engineVibration.getAcceleration(&ax, &ay, &az);
    float vibrationRMS = sqrt(ax*ax + ay*ay + az*az) / 16384.0;

    // Send to server
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("X-API-Key", apiKey);

    String payload = "{";
    payload += "\"brake_temp_left\":" + String(brakeLeftTemp) + ",";
    payload += "\"brake_temp_right\":" + String(brakeRightTemp) + ",";
    payload += "\"vibration_rms\":" + String(vibrationRMS);
    payload += "}";

    http.POST(payload);
    http.end();

    delay(1000);  // 1 second interval
}
```

## Phase 32 Verification Checklist

- [ ] ESP32 firmware compiles
- [ ] Sensors read correctly
- [ ] Data uploads to server
- [ ] Desktop app displays sensor data
- [ ] Prediction algorithms use sensor data

---

# PHASE 33: App Store Requirements

**Priority**: BEFORE PUBLIC LAUNCH
**Goal**: Publish to Google Play Store

## Task 33.1: Google Play Preparation

**Required**:
- [ ] Developer account ($25 one-time)
- [ ] App icon (512x512 PNG)
- [ ] Feature graphic (1024x500)
- [ ] Screenshots (min 2, phone + tablet)
- [ ] Privacy policy URL
- [ ] App description (short + full)
- [ ] Content rating questionnaire
- [ ] Target audience declaration

**build.gradle updates**:
```gradle
android {
    defaultConfig {
        applicationId "app.predict.obd"
        versionCode 1
        versionName "1.0.0"
    }

    signingConfigs {
        release {
            storeFile file("predict-release-key.jks")
            storePassword System.getenv("KEYSTORE_PASSWORD")
            keyAlias "predict"
            keyPassword System.getenv("KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt')
        }
    }
}
```

## Phase 33 Verification Checklist

- [ ] Release APK/AAB built and signed
- [ ] All store assets prepared
- [ ] Privacy policy published online
- [ ] App submitted to Google Play
- [ ] App approved and published

---

# PHASE 34: Customer Support System

**Priority**: AFTER LAUNCH
**Goal**: Handle user inquiries

## Task 34.1: In-App Support

```kotlin
@Composable
fun SupportScreen() {
    Column(modifier = Modifier.padding(16.dp)) {
        // FAQ Section
        Text("Frequently Asked Questions", style = MaterialTheme.typography.headlineSmall)

        FAQItem("How do I connect my OBD device?", "...")
        FAQItem("Why is my prediction accuracy low?", "...")
        FAQItem("How do I add a second vehicle?", "...")

        Spacer(modifier = Modifier.height(24.dp))

        // Contact Support
        Button(onClick = { /* Open email */ }) {
            Text("Email Support")
        }

        // Or integrate with Zendesk/Intercom widget
    }
}
```

## Phase 34 Verification Checklist

- [ ] FAQ section in app
- [ ] Email support configured
- [ ] Response time < 24 hours
- [ ] Ticketing system (optional: Zendesk)

---

# PHASE 35: Business Admin Dashboard

**Priority**: AFTER 100+ USERS
**Goal**: Manage customers and view metrics

## Task 35.1: Admin Web Panel

**Tech**: React + FastAPI backend

**Features**:
- User management (view, suspend, delete)
- Subscription overview
- Revenue dashboard
- Error logs viewer
- System health metrics

## Phase 35 Verification Checklist

- [ ] Admin login works
- [ ] Can view all users
- [ ] Can manage subscriptions
- [ ] Revenue reports accurate

---

# PHASE 36: Real-World Validation

**Priority**: ONGOING
**Goal**: Verify system works in real conditions

## Testing Matrix

| Test | Cars | Conditions | Duration |
|------|------|------------|----------|
| Heat test | 3 | Qatar summer (45°C+) | 2 weeks |
| OBD adapters | 10 | Various brands | 1 week |
| Car models | 20 | Toyota, Nissan, Ford, etc. | 1 month |
| Prediction accuracy | 50 | Track actual vs predicted | 3 months |

## Phase 36 Verification Checklist

- [ ] Heat test passed (no thermal issues)
- [ ] 10+ OBD adapters tested
- [ ] 20+ car models work
- [ ] Prediction accuracy > 70%

---

# PHASE 37: Disaster Recovery

**Priority**: AFTER LAUNCH
**Goal**: Prepare for failures

## Task 37.1: Backup Configuration

```yaml
# backup-config.yml
database:
  type: postgresql
  backup_schedule: "0 2 * * *"  # Daily at 2 AM
  retention_days: 30
  destination: s3://predict-backups/db/

files:
  paths:
    - /app/uploads
    - /app/logs
  backup_schedule: "0 3 * * *"
  retention_days: 14
```

## Phase 37 Verification Checklist

- [ ] Daily database backups
- [ ] Backup restoration tested
- [ ] Incident response plan documented
- [ ] On-call rotation (if team)

---

# PHASE 38: Scale Testing

**Priority**: BEFORE 1000+ USERS
**Goal**: Ensure system handles load

## Task 38.1: Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between

class PredictUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_dashboard(self):
        self.client.get("/api/dashboard")

    @task(2)
    def send_obd_data(self):
        self.client.post("/api/obd", json={
            "rpm": 2500,
            "speed": 60,
            "coolant_temp": 90
        })

    @task(1)
    def get_predictions(self):
        self.client.get("/api/predictions")
```

**Run**: `locust -f locustfile.py --host=https://api.predict.app`

## Phase 38 Verification Checklist

- [ ] 1000 concurrent users tested
- [ ] Response time < 500ms at load
- [ ] No errors under load
- [ ] Database queries optimized
- [ ] Caching implemented (Redis)

---

# MASTER SUMMARY CHECKLIST

## Desktop Application (Phases 1-10)
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Fuel Tracking Tab Wiring | ⬜ Pending |
| 2 | Driving Score Tab Wiring | ⬜ Pending |
| 3 | Geofencing Tab Wiring | ⬜ Pending |
| 4 | Notifications Tab Wiring | ⬜ Pending |
| 5 | Maintenance Reminders Tab Wiring | ⬜ Pending |
| 6 | Recall Alerts Tab Wiring | ⬜ Pending |
| 7 | AI Module Mock Fixes | ⬜ Pending |
| 8 | Devices Tab Wiring | ⬜ Pending |
| 9 | ESP32 Graceful Degradation | ⬜ Pending |
| 10 | Desktop Integration Testing | ⬜ Pending |

## Previlium Server (Phases 11-13)
| Phase | Description | Status |
|-------|-------------|--------|
| 11 | Server Core Endpoints Verification | ⬜ Pending |
| 12 | Guardian System (Teen Monitoring) APIs | ⬜ Pending |
| 13 | WebSocket Real-Time Streaming | ⬜ Pending |

## PredictOBD Driver App (Phases 14-15)
| Phase | Description | Status |
|-------|-------------|--------|
| 14 | Server Connection Verification | ⬜ Pending |
| 15 | OBD Data Flow Testing | ⬜ Pending |

## Predict Guardian App (Phases 16-18)
| Phase | Description | Status |
|-------|-------------|--------|
| 16 | Geofencing Map UI Implementation | ⬜ Pending |
| 17 | AI Chat Screen Implementation | ⬜ Pending |
| 18 | Driver Analytics & Polish Features | ⬜ Pending |

## Full Integration Testing (Phases 19-20)
| Phase | Description | Status |
|-------|-------------|--------|
| 19 | Complete System Integration Test | ⬜ Pending |
| 20 | Production Readiness & Deployment | ⬜ Pending |

## New Features (Phases 21-23)
| Phase | Description | Status |
|-------|-------------|--------|
| 21 | Guardian App LLM Chat Feature | ⬜ Pending |
| 22 | Desktop Parent-Child Profile + Invite Links | ⬜ Pending |
| 23 | Desktop LLM Training Data Editor | ⬜ Pending |

## Commercial Launch Preparation (Phases 24-31)
| Phase | Description | Status |
|-------|-------------|--------|
| 24 | User Authentication System (OAuth + Email) | ⬜ Pending |
| 25 | Payment Integration (Stripe) | ⬜ Pending |
| 26 | Production Server Setup (PostgreSQL + Cloud) | ⬜ Pending |
| 27 | Security Hardening (SSL, Encryption, Rate Limiting) | ⬜ Pending |
| 28 | Monitoring & Error Tracking (Sentry) | ⬜ Pending |
| 29 | Legal Compliance (Privacy Policy, ToS, GDPR) | ⬜ Pending |
| 30 | Testing Suite (Unit + Integration Tests) | ⬜ Pending |
| 31 | User Documentation & Onboarding | ⬜ Pending |

## Post-Launch & Scale (Phases 32-38)
| Phase | Description | Status |
|-------|-------------|--------|
| 32 | Hardware Sensor Integration (ESP32/RPi) | ⬜ Pending |
| 33 | App Store Requirements (Google Play) | ⬜ Pending |
| 34 | Customer Support System | ⬜ Pending |
| 35 | Business Admin Dashboard | ⬜ Pending |
| 36 | Real-World Validation & Testing | ⬜ Pending |
| 37 | Disaster Recovery & Backup | ⬜ Pending |
| 38 | Scale Testing & Optimization | ⬜ Pending |

---

# CRITICAL REMINDERS FOR GLM4.7

1. **COMPLETE DESKTOP FIRST (Phases 1-10)** before touching server or Android apps.

2. **Test after EVERY phase** - Do not proceed until current phase verified working.

3. **No mock data in final code** - All `_load_mock_data()` must be replaced with real data calls.

4. **Error handling everywhere** - Every external API/database call needs try/except or try/catch.

5. **Preserve UI code** - Only modify data/action methods, not the UI layout code.

6. **Check backend exists** - Before wiring UI, verify the backend class/methods actually exist.

7. **Use profile ID pattern** - All tabs need `_get_current_profile_id()` or equivalent helper.

8. **Signal completion** - Tell user after each phase so they can verify before proceeding.

9. **Server port is 8000** - The Previlium server runs on port 8000, not 8080.

10. **4 Applications Total**:
    - Desktop App: `c:\D Drive\Predict` (PySide6/Python)
    - Previlium Server: `C:\OBDserver\Previlium_OBD_Server` (FastAPI/Python)
    - PredictOBD: `C:\Predict\PredictOBD` (Kotlin/Android - Driver app)
    - Predict Guardian: `C:\Predict guradian` (Kotlin/Android - Parent/Fleet app)

11. **Guardian App is Kotlin/Android** - It's a separate Android app at `C:\Predict guradian`, not part of the server.

12. **Use Google Maps Compose** for geofencing map UI in Guardian app (Phase 16).

13. **Test on real Android device** for Guardian and PredictOBD apps (not just emulator).

14. **Arabic RTL support** - Guardian app has Arabic translations, test RTL layout.

15. **Check dependencies** - Ensure all Gradle dependencies are compatible versions.
