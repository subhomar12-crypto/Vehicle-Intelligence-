# PREDICT - Complete Feature Implementation Plan

**Version:** 1.0
**Created:** January 2026
**Target:** GLM4.7 Implementation Tasks
**Reviewer:** Claude Opus 4.5

---

## Overview

This document outlines the complete implementation plan for adding missing features to the PREDICT Vehicle Intelligence Platform. The plan is organized into 6 phases with 32 total tasks.

### Project Structure
```
c:\D Drive\Predict\
├── main_window.py          # Main application window
├── dashboard_tab.py        # Dashboard with widgets
├── analytics_tab.py        # Analytics and charts
├── reports_tab.py          # Report generation
├── settings_tab.py         # Application settings
├── devices_tab.py          # Device management
├── notifications_tab.py    # Notification center
├── user_management_tab.py  # User administration
├── data_management_tab.py  # Data export/import/backup
├── [NEW TABS TO CREATE]    # See Phase 2
└── [BACKEND MODULES]       # Existing backend systems
```

### Color Scheme (Must Match)
- Primary Red: `#C40000`
- Background Dark: `#0D1117`
- Card Background: `#161B22`
- Border Color: `#30363D`
- Text Primary: `#F0F6FC`
- Text Secondary: `#8B949E`
- Success Green: `#4CAF50`
- Warning Orange: `#FF9800`
- Error Red: `#F44336`

---

## Phase 1: Core Infrastructure & Backend Wiring

**Priority:** P0 - Critical
**Estimated Tasks:** 5
**Dependencies:** None

### Task 1.1: Wire Push Notification Manager

**File:** `push_notification_manager.py`

**Current State:** Placeholder implementation with no actual push service

**Required Changes:**
1. Add Firebase Cloud Messaging (FCM) or OneSignal SDK integration
2. Add configuration for API keys in `config/api_keys.json`
3. Implement device token registration
4. Implement actual `send_push_notification()` method

**Implementation Details:**
```python
# Required imports to add
import firebase_admin
from firebase_admin import credentials, messaging

# OR for OneSignal
import onesignal_sdk

# Required methods to implement:
def _initialize_firebase(self):
    """Initialize Firebase Admin SDK"""
    cred = credentials.Certificate(self.firebase_credentials_path)
    firebase_admin.initialize_app(cred)

def send_push_notification(self, device_token: str, title: str, body: str, data: dict = None) -> bool:
    """Send actual push notification via FCM"""
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=device_token
    )
    response = messaging.send(message)
    return response is not None
```

**Config file update (`config/api_keys.json`):**
```json
{
    "firebase": {
        "credentials_path": "config/firebase_credentials.json",
        "project_id": "predict-vehicle-platform"
    }
}
```

---

### Task 1.2: Wire SMS Notification Manager

**File:** `sms_notification_manager.py`

**Current State:** Placeholder with mock SMS sending

**Required Changes:**
1. Integrate Twilio or AWS SNS
2. Add credentials to config
3. Implement actual SMS sending with error handling

**Implementation Details:**
```python
# For Twilio
from twilio.rest import Client

class SMSNotificationManager:
    def __init__(self):
        self.account_sid = CONFIG.get('twilio', {}).get('account_sid')
        self.auth_token = CONFIG.get('twilio', {}).get('auth_token')
        self.from_number = CONFIG.get('twilio', {}).get('from_number')
        self.client = Client(self.account_sid, self.auth_token)

    def send_sms(self, to_number: str, message: str) -> bool:
        """Send actual SMS via Twilio"""
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"SMS sent: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"SMS failed: {e}")
            return False
```

**Config addition:**
```json
{
    "twilio": {
        "account_sid": "YOUR_ACCOUNT_SID",
        "auth_token": "YOUR_AUTH_TOKEN",
        "from_number": "+1234567890"
    }
}
```

---

### Task 1.3: Replace Mock Data in Maintenance History API

**File:** `maintenance_history_api.py`

**Current State:** Returns hardcoded mock data

**Required Changes:**
1. Connect to `service_history.db` database
2. Implement actual SQLite queries
3. Return real maintenance records

**Implementation Details:**
```python
import sqlite3
from config import get_config

CONFIG = get_config()

def get_maintenance_history(self, vehicle_id: str = None, limit: int = 100) -> List[Dict]:
    """Get actual maintenance history from database"""
    db_path = CONFIG.DATA_DIR / 'data' / 'service_history.db'

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if vehicle_id:
        cursor.execute("""
            SELECT * FROM service_records
            WHERE vehicle_id = ?
            ORDER BY service_date DESC
            LIMIT ?
        """, (vehicle_id, limit))
    else:
        cursor.execute("""
            SELECT * FROM service_records
            ORDER BY service_date DESC
            LIMIT ?
        """, (limit,))

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records
```

---

### Task 1.4: Replace Hardcoded DTCs with Real OBD Retrieval

**File:** `obd_manager.py` (or relevant diagnostics file)

**Current State:** Uses hardcoded mock DTC list

**Required Changes:**
1. Use actual OBD-II commands to retrieve DTCs
2. Query `obd.commands.GET_DTC` and `obd.commands.GET_FREEZE_DTC`
3. Parse and return real DTC data

**Implementation Details:**
```python
import obd

def get_current_dtcs(self) -> List[Dict]:
    """Get actual DTCs from vehicle via OBD-II"""
    if not self.connection or not self.connection.is_connected():
        logger.warning("OBD not connected, cannot retrieve DTCs")
        return []

    dtcs = []

    # Get current DTCs
    response = self.connection.query(obd.commands.GET_DTC)
    if response.value:
        for code, description in response.value:
            dtcs.append({
                'code': code,
                'description': description,
                'type': 'current',
                'timestamp': datetime.now().isoformat()
            })

    # Get freeze frame DTCs
    freeze_response = self.connection.query(obd.commands.GET_FREEZE_DTC)
    if freeze_response.value:
        for code, description in freeze_response.value:
            dtcs.append({
                'code': code,
                'description': description,
                'type': 'freeze_frame',
                'timestamp': datetime.now().isoformat()
            })

    return dtcs
```

---

### Task 1.5: Connect DTC Learning to Alert System

**File:** `dtc_learning_manager.py`

**Current State:** Learning system exists but doesn't trigger notifications

**Required Changes:**
1. Import and use `AlertNotificationManager`
2. Add callback when new DTC pattern is learned
3. Send notification on critical DTC detection

**Implementation Details:**
```python
from alert_notification_manager import AlertNotificationManager

class DTCLearningManager:
    def __init__(self):
        self.notification_manager = AlertNotificationManager()

    def on_dtc_learned(self, dtc_code: str, pattern_data: dict):
        """Callback when DTC pattern is learned"""
        # Send notification for critical DTCs
        if self._is_critical_dtc(dtc_code):
            self.notification_manager.send_notification(
                user_id=1,
                title=f"Critical DTC Detected: {dtc_code}",
                message=f"A critical diagnostic trouble code has been detected. {pattern_data.get('description', '')}",
                priority="CRITICAL",
                channels=["in_app", "push", "email"]
            )

        logger.info(f"DTC pattern learned: {dtc_code}")

    def _is_critical_dtc(self, dtc_code: str) -> bool:
        """Check if DTC is critical (P0xxx codes are usually critical)"""
        critical_prefixes = ['P0', 'P1', 'P2']  # Powertrain codes
        return any(dtc_code.startswith(prefix) for prefix in critical_prefixes)
```

---

## Phase 2: New Dashboard Tabs

**Priority:** P1 - High
**Estimated Tasks:** 6
**Dependencies:** Phase 1 completion recommended

### Task 2.1: Create Fuel Tracking Tab

**New File:** `fuel_tracking_tab.py`

**Backend Module:** `fuel_tracking_system.py`

**UI Components Required:**
- Fuel log table (date, gallons, cost, odometer, MPG)
- MPG trend chart (line graph)
- Cost tracking summary cards
- Add fill-up form dialog
- Statistics panel (avg MPG, total cost, best/worst tank)

**Template:**
```python
"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT. All rights reserved.

Module: Fuel Tracking Tab
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDateEdit, QMessageBox, QTabWidget,
    QFrame, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from fuel_tracking_system import FuelTrackingSystem
    FUEL_SYSTEM_AVAILABLE = True
except ImportError:
    FUEL_SYSTEM_AVAILABLE = False

logger = logging.getLogger(__name__)


class FuelEntryDialog(QDialog):
    """Dialog for adding/editing fuel entries"""

    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Add Fuel Entry" if not entry else "Edit Fuel Entry")
        self.setMinimumWidth(400)
        self._setup_ui()

        if entry:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit, QDoubleSpinBox, QDateEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px;
            }
        """)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        form.addRow("Date:", self.date_edit)

        # Gallons
        self.gallons_spin = QDoubleSpinBox()
        self.gallons_spin.setRange(0.1, 100.0)
        self.gallons_spin.setDecimals(3)
        self.gallons_spin.setSuffix(" gal")
        form.addRow("Gallons:", self.gallons_spin)

        # Price per gallon
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.01, 20.0)
        self.price_spin.setDecimals(3)
        self.price_spin.setPrefix("$")
        form.addRow("Price/Gallon:", self.price_spin)

        # Odometer
        self.odometer_spin = QDoubleSpinBox()
        self.odometer_spin.setRange(0, 9999999)
        self.odometer_spin.setDecimals(1)
        self.odometer_spin.setSuffix(" mi")
        form.addRow("Odometer:", self.odometer_spin)

        # Station (optional)
        self.station_edit = QLineEdit()
        self.station_edit.setPlaceholderText("Gas station name (optional)")
        form.addRow("Station:", self.station_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_fields(self):
        """Populate fields with existing entry data"""
        if self.entry:
            # Populate from entry dict
            pass

    def get_entry_data(self) -> Dict[str, Any]:
        """Get entry data from form"""
        return {
            'date': self.date_edit.date().toPyDate().isoformat(),
            'gallons': self.gallons_spin.value(),
            'price_per_gallon': self.price_spin.value(),
            'total_cost': self.gallons_spin.value() * self.price_spin.value(),
            'odometer': self.odometer_spin.value(),
            'station': self.station_edit.text().strip()
        }


class FuelTrackingTab(QWidget):
    """
    Fuel Tracking Tab - Track fuel consumption and costs
    """

    fuel_entry_added = Signal(dict)

    def __init__(self, fuel_system=None):
        super().__init__()
        self.fuel_system = fuel_system
        self.fuel_entries = []

        self._setup_ui()
        self._load_fuel_data()

    def _setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Statistics cards
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(self._create_stat_card("Average MPG", "0.0", "avg_mpg"))
        stats_layout.addWidget(self._create_stat_card("Total Cost", "$0.00", "total_cost"))
        stats_layout.addWidget(self._create_stat_card("Last Fill-up", "-", "last_fillup"))
        stats_layout.addWidget(self._create_stat_card("Cost/Mile", "$0.00", "cost_per_mile"))
        layout.addLayout(stats_layout)

        # Fuel log table
        self.fuel_table = QTableWidget()
        self.fuel_table.setColumnCount(7)
        self.fuel_table.setHorizontalHeaderLabels([
            "Date", "Gallons", "Price/Gal", "Total", "Odometer", "MPG", "Actions"
        ])
        self._apply_table_style(self.fuel_table)
        layout.addWidget(self.fuel_table)

        # TODO: Add MPG trend chart using pyqtgraph or matplotlib

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with title and actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Fuel Tracking")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        layout.addStretch()

        add_btn = QPushButton("+ Add Fill-up")
        add_btn.setStyleSheet(self._get_button_style('primary'))
        add_btn.clicked.connect(self._add_fuel_entry)
        layout.addWidget(add_btn)

        return widget

    def _create_stat_card(self, title: str, value: str, attr_name: str) -> QFrame:
        """Create a statistics card"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        value_label.setObjectName(attr_name)
        setattr(self, f"{attr_name}_label", value_label)
        layout.addWidget(value_label)

        return card

    def _apply_table_style(self, table: QTableWidget):
        """Apply dark theme to table"""
        table.setStyleSheet("""
            QTableWidget {
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 8px;
                gridline-color: #30363D;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #C40000; }
            QHeaderView::section {
                background-color: #21262D;
                color: #F0F6FC;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
            }
        """)

    def _get_button_style(self, style_type: str) -> str:
        """Get button stylesheet"""
        if style_type == 'primary':
            return """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
            """
        return ""

    def _load_fuel_data(self):
        """Load fuel data from system"""
        if self.fuel_system and FUEL_SYSTEM_AVAILABLE:
            try:
                self.fuel_entries = self.fuel_system.get_fuel_entries()
            except Exception as e:
                logger.error(f"Error loading fuel data: {e}")
                self._load_mock_data()
        else:
            self._load_mock_data()

        self._update_table()
        self._update_statistics()

    def _load_mock_data(self):
        """Load mock fuel data for testing"""
        self.fuel_entries = [
            {
                'date': '2026-01-08',
                'gallons': 12.5,
                'price_per_gallon': 3.45,
                'total_cost': 43.13,
                'odometer': 45230,
                'mpg': 28.5
            },
            {
                'date': '2026-01-01',
                'gallons': 11.2,
                'price_per_gallon': 3.52,
                'total_cost': 39.42,
                'odometer': 44875,
                'mpg': 31.7
            }
        ]

    def _update_table(self):
        """Update fuel entries table"""
        self.fuel_table.setRowCount(0)

        for entry in self.fuel_entries:
            row = self.fuel_table.rowCount()
            self.fuel_table.insertRow(row)

            self.fuel_table.setItem(row, 0, QTableWidgetItem(entry.get('date', '')))
            self.fuel_table.setItem(row, 1, QTableWidgetItem(f"{entry.get('gallons', 0):.3f}"))
            self.fuel_table.setItem(row, 2, QTableWidgetItem(f"${entry.get('price_per_gallon', 0):.3f}"))
            self.fuel_table.setItem(row, 3, QTableWidgetItem(f"${entry.get('total_cost', 0):.2f}"))
            self.fuel_table.setItem(row, 4, QTableWidgetItem(f"{entry.get('odometer', 0):,.1f}"))

            mpg = entry.get('mpg', 0)
            mpg_item = QTableWidgetItem(f"{mpg:.1f}")
            if mpg >= 30:
                mpg_item.setForeground(QColor("#4CAF50"))
            elif mpg >= 20:
                mpg_item.setForeground(QColor("#FFC107"))
            else:
                mpg_item.setForeground(QColor("#F44336"))
            self.fuel_table.setItem(row, 5, mpg_item)

        self.fuel_table.resizeColumnsToContents()

    def _update_statistics(self):
        """Update statistics cards"""
        if not self.fuel_entries:
            return

        # Calculate average MPG
        mpg_values = [e.get('mpg', 0) for e in self.fuel_entries if e.get('mpg')]
        avg_mpg = sum(mpg_values) / len(mpg_values) if mpg_values else 0
        self.avg_mpg_label.setText(f"{avg_mpg:.1f}")

        # Calculate total cost
        total_cost = sum(e.get('total_cost', 0) for e in self.fuel_entries)
        self.total_cost_label.setText(f"${total_cost:,.2f}")

        # Last fill-up
        if self.fuel_entries:
            self.last_fillup_label.setText(self.fuel_entries[0].get('date', '-'))

    def _add_fuel_entry(self):
        """Add new fuel entry"""
        dialog = FuelEntryDialog(self)

        if dialog.exec() == QDialog.Accepted:
            entry_data = dialog.get_entry_data()

            # Calculate MPG if we have previous entry
            if self.fuel_entries:
                prev_odometer = self.fuel_entries[0].get('odometer', 0)
                miles_driven = entry_data['odometer'] - prev_odometer
                if miles_driven > 0 and entry_data['gallons'] > 0:
                    entry_data['mpg'] = miles_driven / entry_data['gallons']

            # Add to list
            self.fuel_entries.insert(0, entry_data)

            # Save to system if available
            if self.fuel_system and FUEL_SYSTEM_AVAILABLE:
                try:
                    self.fuel_system.add_fuel_entry(entry_data)
                except Exception as e:
                    logger.error(f"Error saving fuel entry: {e}")

            self._update_table()
            self._update_statistics()
            self.fuel_entry_added.emit(entry_data)

            QMessageBox.information(self, "Entry Added", "Fuel entry added successfully!")
```

---

### Task 2.2: Create Driving Score Tab

**New File:** `driving_score_tab.py`

**Backend Module:** `driving_score_system.py`

**UI Components Required:**
- Score gauge widget (0-100 circular gauge)
- Behavior breakdown cards (acceleration, braking, cornering, speed)
- Trip history table
- Tips for improvement section
- Weekly/Monthly trend chart

**Key Implementation Notes:**
- Use QProgressBar styled as circular gauge or custom paint
- Color code score: Green (80+), Yellow (60-79), Red (<60)
- Connect to `driving_score_system.get_current_score()`

---

### Task 2.3: Create Geofencing Tab

**New File:** `geofencing_tab.py`

**Backend Module:** `geofence_manager.py`

**UI Components Required:**
- Map placeholder (can use QWebEngineView for OpenStreetMap later)
- Zone list table (name, type, coordinates, status)
- Add/Edit zone dialog
- Entry/Exit alerts history
- Zone statistics

**Key Implementation Notes:**
- For MVP, use a placeholder for map view
- Focus on zone CRUD operations
- Connect to `geofence_manager.get_zones()`, `add_zone()`, `delete_zone()`

---

### Task 2.4: Create ESP32 Sensors Tab

**New File:** `esp32_sensors_tab.py`

**Backend Module:** `esp32_sensor_manager.py`

**UI Components Required:**
- Sensor list table (ID, type, status, last reading)
- Live readings dashboard
- Calibration settings panel
- Connection status indicator
- Data logging toggle

**Key Implementation Notes:**
- Support temperature, humidity, pressure, GPS sensors
- Real-time updates using QTimer
- Connect to `esp32_sensor_manager.get_sensors()`, `get_readings()`

---

### Task 2.5: Create Maintenance Reminders Tab

**New File:** `maintenance_reminders_tab.py`

**Backend Module:** `maintenance_reminder_system.py`

**UI Components Required:**
- Upcoming reminders list (due date, type, vehicle, status)
- Add/Edit reminder dialog
- Interval settings (mileage-based, time-based, or both)
- Completed maintenance history
- Snooze/Dismiss actions

**Key Implementation Notes:**
- Reminder types: Oil Change, Tire Rotation, Brake Inspection, etc.
- Show days until due or miles until due
- Connect to `maintenance_reminder_system.get_reminders()`

---

### Task 2.6: Create Recall Alerts Tab

**New File:** `recall_alerts_tab.py`

**Backend Module:** `recall_alert_system.py`

**UI Components Required:**
- Active recalls table (campaign, description, severity, status)
- VIN lookup form
- NHTSA integration status
- Recall details view
- Mark as completed action

**Key Implementation Notes:**
- Query NHTSA API for recall data
- Store checked VINs and results
- Connect to `recall_alert_system.check_recalls()`, `get_active_recalls()`

---

## Phase 3: Dashboard Integration & Multi-Vehicle Support

**Priority:** P1 - High
**Estimated Tasks:** 5
**Dependencies:** Phase 2 tabs created

### Task 3.1: Add Vehicle Switcher to Dashboard

**File:** `main_window.py`, `dashboard_tab.py`

**Required Changes:**
1. Add `QComboBox` in header/toolbar for vehicle selection
2. Populate from `multi_vehicle_manager.get_vehicles()`
3. Emit `vehicle_changed` signal when selection changes
4. Update all tabs to respond to vehicle change

**Implementation:**
```python
# In main_window.py header area
self.vehicle_selector = QComboBox()
self.vehicle_selector.setMinimumWidth(200)
self.vehicle_selector.setStyleSheet("""
    QComboBox {
        background-color: #21262D;
        color: #F0F6FC;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 8px 12px;
    }
""")
self.vehicle_selector.currentIndexChanged.connect(self._on_vehicle_changed)

def _load_vehicles(self):
    """Load vehicles into selector"""
    if self.multi_vehicle_manager:
        vehicles = self.multi_vehicle_manager.get_vehicles()
        for vehicle in vehicles:
            display_name = f"{vehicle['year']} {vehicle['make']} {vehicle['model']}"
            self.vehicle_selector.addItem(display_name, vehicle['id'])

def _on_vehicle_changed(self, index):
    """Handle vehicle selection change"""
    vehicle_id = self.vehicle_selector.currentData()
    self.vehicle_changed.emit(vehicle_id)
```

---

### Task 3.2: Add Sync Status Indicator

**File:** `main_window.py`

**Required Changes:**
1. Add status indicator in status bar or header
2. Connect to `data_sync_manager.get_sync_status()`
3. Show last sync time and sync state (syncing, synced, error)
4. Add manual sync button

**Implementation:**
```python
# Status indicator widget
self.sync_status = QLabel("Synced")
self.sync_status.setStyleSheet("""
    QLabel {
        color: #4CAF50;
        font-size: 11px;
        padding: 4px 8px;
        background-color: #21262D;
        border-radius: 4px;
    }
""")

# Update sync status
def _update_sync_status(self):
    if self.data_sync_manager:
        status = self.data_sync_manager.get_sync_status()
        if status['syncing']:
            self.sync_status.setText("Syncing...")
            self.sync_status.setStyleSheet("color: #FFC107; ...")
        elif status['error']:
            self.sync_status.setText("Sync Error")
            self.sync_status.setStyleSheet("color: #F44336; ...")
        else:
            last_sync = status.get('last_sync', 'Never')
            self.sync_status.setText(f"Synced: {last_sync}")
            self.sync_status.setStyleSheet("color: #4CAF50; ...")
```

---

### Task 3.3: Integrate Voice Command System

**File:** `main_window.py`

**Required Changes:**
1. Add microphone button in toolbar
2. Connect to `voice_command_system.start_listening()`
3. Show listening indicator
4. Handle voice command results

---

### Task 3.4: Add Remote Command Controls

**File:** `devices_tab.py`

**Required Changes:**
1. Add remote command buttons for connected vehicles
2. Commands: Lock, Unlock, Start Engine, Stop Engine, Locate
3. Connect to `remote_command_system.send_command()`
4. Show command status feedback

---

### Task 3.5: Register All New Tabs in Navigation

**File:** `main_window.py`

**Required Changes:**
1. Import all new tab classes
2. Add to navigation menu/tab widget
3. Initialize with appropriate managers

**Implementation:**
```python
# Imports
from fuel_tracking_tab import FuelTrackingTab
from driving_score_tab import DrivingScoreTab
from geofencing_tab import GeofencingTab
from esp32_sensors_tab import ESP32SensorsTab
from maintenance_reminders_tab import MaintenanceRemindersTab
from recall_alerts_tab import RecallAlertsTab

# In _setup_tabs() method
self.fuel_tab = FuelTrackingTab(self.fuel_system)
self.tabs.addTab(self.fuel_tab, "Fuel")

self.driving_score_tab = DrivingScoreTab(self.driving_score_system)
self.tabs.addTab(self.driving_score_tab, "Driving Score")

self.geofencing_tab = GeofencingTab(self.geofence_manager)
self.tabs.addTab(self.geofencing_tab, "Geofencing")

self.esp32_tab = ESP32SensorsTab(self.esp32_manager)
self.tabs.addTab(self.esp32_tab, "Sensors")

self.reminders_tab = MaintenanceRemindersTab(self.reminder_system)
self.tabs.addTab(self.reminders_tab, "Reminders")

self.recalls_tab = RecallAlertsTab(self.recall_system)
self.tabs.addTab(self.recalls_tab, "Recalls")
```

---

## Phase 4: Analytics & Reports Enhancement

**Priority:** P2 - Medium
**Estimated Tasks:** 4
**Dependencies:** Phase 1-3 completion

### Task 4.1: Implement Real Charts in Analytics Tab

**File:** `analytics_tab.py`

**Required Changes:**
1. Install `pyqtgraph` or `matplotlib`
2. Replace `QLabel` placeholders with actual chart widgets
3. Implement: Fuel efficiency trend, Maintenance costs, DTC frequency

**Chart Types:**
- Line chart: MPG over time
- Bar chart: Monthly maintenance costs
- Pie chart: DTC categories
- Area chart: Driving score trend

---

### Task 4.2: Complete Report Generation

**File:** `reports_tab.py`

**Required Changes:**
1. Install `reportlab` or `fpdf`
2. Implement PDF generation for each report type
3. Report templates: Vehicle Summary, Maintenance Report, Diagnostics Report

---

### Task 4.3: Wire Dashboard Widgets to Live Data

**File:** `dashboard_tab.py`

**Required Changes:**
1. Connect stat widgets to actual data sources
2. Use QTimer for periodic updates
3. Pull from `obd_manager`, `historical_data_manager`

---

### Task 4.4: Implement Global Search

**File:** `main_window.py`

**Required Changes:**
1. Add search `QLineEdit` in toolbar
2. Search across: vehicles, DTCs, service records, notifications
3. Show results in dropdown or popup

---

## Phase 5: Settings & Configuration Completion

**Priority:** P2 - Medium
**Estimated Tasks:** 4
**Dependencies:** None

### Task 5.1: Complete Settings Save Functions

**File:** `settings_tab.py`

**Required Changes:**
1. Implement `_save_general_settings()`
2. Implement `_save_obd_settings()`
3. Implement `_save_notification_settings()`
4. Write to config files

---

### Task 5.2: Add Help/About Content

**File:** `help_tab.py` or new `about_dialog.py`

**Required Changes:**
1. Display version from `__version__`
2. Show changelog from `CHANGELOG.md`
3. Display license text
4. Add links to documentation

---

### Task 5.3: Wire Notification Preferences

**File:** `notifications_tab.py`

**Required Changes:**
1. Connect preference toggles to `AlertNotificationManager.update_preferences()`
2. Save preferences to database
3. Load preferences on startup

---

### Task 5.4: Add Theme Switching

**File:** `settings_tab.py`, create `styles.py`

**Required Changes:**
1. Add theme toggle (Dark/Light)
2. Create light theme stylesheet
3. Implement theme switching at runtime

---

## Phase 6: Testing & Final Integration

**Priority:** P0 - Critical
**Estimated Tasks:** 4
**Dependencies:** All previous phases

### Task 6.1: Test Tab Loading

**Checklist:**
- [ ] All new tabs import without errors
- [ ] Tabs initialize correctly
- [ ] No crashes on empty data
- [ ] Mock data displays correctly

### Task 6.2: Verify Backend Integration

**Checklist:**
- [ ] Push notifications send successfully
- [ ] SMS notifications work
- [ ] Database queries return real data
- [ ] OBD DTCs retrieved correctly
- [ ] DTC learning triggers alerts

### Task 6.3: Test Data Flow

**Checklist:**
- [ ] OBD data recorded to database
- [ ] Historical data appears in analytics
- [ ] Export functions work
- [ ] Backup/restore functions work

### Task 6.4: UI/UX Consistency Check

**Checklist:**
- [ ] All colors match scheme (#C40000, #0D1117, etc.)
- [ ] Button styles consistent
- [ ] Spacing and margins uniform
- [ ] Fonts match (Segoe UI)
- [ ] Tables have same styling
- [ ] Cards have same styling

---

## Appendix A: File Summary

### New Files to Create (Phase 2)
| File | Lines (est.) |
|------|--------------|
| `fuel_tracking_tab.py` | 400-500 |
| `driving_score_tab.py` | 350-450 |
| `geofencing_tab.py` | 400-500 |
| `esp32_sensors_tab.py` | 350-400 |
| `maintenance_reminders_tab.py` | 400-500 |
| `recall_alerts_tab.py` | 350-450 |

### Files to Modify
| File | Changes |
|------|---------|
| `main_window.py` | Add tabs, vehicle switcher, sync status, search |
| `push_notification_manager.py` | Firebase/OneSignal integration |
| `sms_notification_manager.py` | Twilio integration |
| `maintenance_history_api.py` | Real database queries |
| `obd_manager.py` | Real DTC retrieval |
| `dtc_learning_manager.py` | Alert integration |
| `analytics_tab.py` | Real charts |
| `reports_tab.py` | PDF generation |
| `dashboard_tab.py` | Live data |
| `settings_tab.py` | Save functions, theme |

---

## Appendix B: Dependencies to Install

```bash
# For push notifications
pip install firebase-admin
# OR
pip install onesignal-sdk

# For SMS
pip install twilio

# For charts
pip install pyqtgraph
# OR
pip install matplotlib

# For PDF reports
pip install reportlab
# OR
pip install fpdf2

# For maps (optional)
pip install folium
pip install PyQtWebEngine
```

---

## Appendix C: Review Process

After each phase completion:

1. **Code Review by Claude Opus 4.5**
   - Check for syntax errors
   - Verify style consistency
   - Ensure error handling
   - Validate integration points

2. **Functional Testing**
   - Run application
   - Test each new feature
   - Verify data flow
   - Check for crashes

3. **Approval Criteria**
   - No import errors
   - No runtime crashes
   - Features work as specified
   - UI matches design system

---

**Document End**

*This plan should be executed phase by phase. Do not proceed to the next phase until the current phase is reviewed and approved.*
