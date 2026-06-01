"""
User Detail Dialog - Popup for viewing and editing user details.

Contains 6 sub-tabs: User Info, Vehicles & Drivers, Tier Management,
Service History, Billing, Fleet Info.
"""

import logging
import time
from typing import Dict, List

from PySide6.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QWidget, QGroupBox, QGridLayout, QMessageBox,
    QHeaderView, QTextEdit
)
from PySide6.QtCore import Qt

from predict.desktop.theme import PredictTheme, get_table_stylesheet
from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)

# Tier limits reference
TIER_LIMITS = {
    "free": {"vehicles": 1, "dtc_checks": 2, "predictions_day": 0,
             "llm_chat_day": 0, "pdfs_week": 0, "guardian": False,
             "fleet": False, "history_days": 7},
    "pro": {"vehicles": 1, "dtc_checks": -1, "predictions_day": 2,
            "llm_chat_day": 15, "pdfs_week": 1, "guardian": False,
            "fleet": False, "history_days": 90},
    "premium": {"vehicles": 3, "dtc_checks": -1, "predictions_day": 20,
                "llm_chat_day": 100, "pdfs_week": 8, "guardian": True,
                "fleet": False, "history_days": 365},
    "admin": {"vehicles": -1, "dtc_checks": -1, "predictions_day": -1,
              "llm_chat_day": -1, "pdfs_week": -1, "guardian": True,
              "fleet": True, "history_days": -1},
}


class UserDetailDialog(QDialog):
    """Dialog for viewing and editing user details."""

    def __init__(self, user_id: int, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._user_id = user_id
        self._api = api_client
        self._user_data: Dict = {}
        self._vehicles: List = []

        self.setWindowTitle(f"User Details - ID {user_id}")
        self.setMinimumSize(900, 700)

        self._setup_ui()
        self._load_user_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget()

        # Create sub-tabs
        self._info_tab = self._create_info_tab()
        self._vehicles_tab = self._create_vehicles_tab()
        self._tier_tab = self._create_tier_tab()
        self._service_tab = self._create_service_tab()
        self._billing_tab = self._create_billing_tab()
        self._fleet_tab = self._create_fleet_tab()
        self._api_keys_tab = self._create_api_keys_tab()

        self._tabs.addTab(self._info_tab, "User Info")
        self._tabs.addTab(self._vehicles_tab, "Vehicles & Drivers")
        self._tabs.addTab(self._tier_tab, "Tier Management")
        self._tabs.addTab(self._service_tab, "Service History")
        self._tabs.addTab(self._billing_tab, "Billing")
        self._tabs.addTab(self._fleet_tab, "Fleet Info")
        self._tabs.addTab(self._api_keys_tab, "API Keys")

        layout.addWidget(self._tabs)

        # Bottom buttons: Delete User and Close
        btn_layout = QHBoxLayout()
        
        self._delete_btn = QPushButton("Delete User")
        self._delete_btn.setStyleSheet(f"background-color: {PredictTheme.DANGER}; color: white;")
        self._delete_btn.clicked.connect(self._on_delete_user)
        
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._close_btn)
        layout.addLayout(btn_layout)

    def _create_info_tab(self) -> QWidget:
        """Create User Info sub-tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        self._info_name = QLineEdit()
        self._info_email = QLabel()
        self._info_phone = QLineEdit()
        self._info_role = QLabel()
        self._info_status = QLabel()
        self._info_registered = QLabel()
        self._info_last_login = QLabel()

        layout.addRow("Name:", self._info_name)
        layout.addRow("Email:", self._info_email)
        layout.addRow("Phone:", self._info_phone)
        layout.addRow("Role:", self._info_role)
        layout.addRow("Status:", self._info_status)
        layout.addRow("Registered:", self._info_registered)
        layout.addRow("Last Login:", self._info_last_login)

        # Vehicle info section
        vehicle_group = QGroupBox("Vehicle Info")
        vehicle_layout = QFormLayout(vehicle_group)
        self._info_vehicle_make = QLabel()
        self._info_vehicle_model = QLabel()
        self._info_vehicle_year = QLabel()
        self._info_vehicle_plate = QLabel()

        vehicle_layout.addRow("Make:", self._info_vehicle_make)
        vehicle_layout.addRow("Model:", self._info_vehicle_model)
        vehicle_layout.addRow("Year:", self._info_vehicle_year)
        vehicle_layout.addRow("Plate:", self._info_vehicle_plate)

        layout.addRow(vehicle_group)

        # Edit/Save buttons
        btn_layout = QHBoxLayout()
        self._edit_btn = QPushButton("Edit")
        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit_clicked)
        self._save_btn.clicked.connect(self._on_save_clicked)

        btn_layout.addWidget(self._edit_btn)
        btn_layout.addWidget(self._save_btn)
        btn_layout.addStretch()
        layout.addRow(btn_layout)

        return tab

    def _create_vehicles_tab(self) -> QWidget:
        """Create Vehicles & Drivers sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Vehicles section
        vehicles_group = QGroupBox("Vehicles")
        vehicles_layout = QVBoxLayout(vehicles_group)

        self._vehicles_table = QTableWidget()
        self._vehicles_table.setColumnCount(4)
        self._vehicles_table.setHorizontalHeaderLabels(
            ["Make/Model", "Year", "Plate", "Actions"]
        )
        self._vehicles_table.setStyleSheet(get_table_stylesheet())
        vehicles_layout.addWidget(self._vehicles_table)

        self._add_vehicle_btn = QPushButton("Add Vehicle")
        vehicles_layout.addWidget(self._add_vehicle_btn)

        layout.addWidget(vehicles_group)

        # Drivers section
        drivers_group = QGroupBox("Drivers (Read-Only)")
        drivers_layout = QVBoxLayout(drivers_group)

        self._drivers_table = QTableWidget()
        self._drivers_table.setColumnCount(3)
        self._drivers_table.setHorizontalHeaderLabels(
            ["Name", "Email", "Role"]
        )
        self._drivers_table.setStyleSheet(get_table_stylesheet())
        drivers_layout.addWidget(self._drivers_table)

        layout.addWidget(drivers_group)

        return tab

    def _create_tier_tab(self) -> QWidget:
        """Create Tier Management sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Current tier display
        tier_layout = QHBoxLayout()
        tier_layout.addWidget(QLabel("Current Tier:"))
        self._current_tier_label = QLabel("Free")
        self._current_tier_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {PredictTheme.PRIMARY};"
        )
        tier_layout.addWidget(self._current_tier_label)
        tier_layout.addStretch()
        layout.addLayout(tier_layout)

        # Tier selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Change to:"))
        self._tier_combo = QComboBox()
        self._tier_combo.addItems(["free", "pro", "premium", "admin"])
        self._tier_combo.currentTextChanged.connect(self._on_tier_changed)
        selector_layout.addWidget(self._tier_combo)
        self._apply_tier_btn = QPushButton("Apply Tier Change")
        self._apply_tier_btn.clicked.connect(self._on_apply_tier)
        selector_layout.addWidget(self._apply_tier_btn)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Features table
        features_group = QGroupBox("Features & Limits")
        features_layout = QVBoxLayout(features_group)

        self._features_table = QTableWidget()
        self._features_table.setColumnCount(3)
        self._features_table.setHorizontalHeaderLabels(
            ["Feature", "Current Limit", "After Change"]
        )
        self._features_table.setRowCount(8)
        features = [
            "Vehicles", "DTC Checks", "Predictions/day",
            "LLM Chat/day", "PDFs/week", "Guardian", "Fleet", "History"
        ]
        for i, feat in enumerate(features):
            self._features_table.setItem(i, 0, QTableWidgetItem(feat))
        self._features_table.setStyleSheet(get_table_stylesheet())
        features_layout.addWidget(self._features_table)

        layout.addWidget(features_group)

        # Per-user overrides
        overrides_group = QGroupBox("Per-User Overrides")
        overrides_layout = QVBoxLayout(overrides_group)

        self._overrides_table = QTableWidget()
        self._overrides_table.setColumnCount(4)
        self._overrides_table.setHorizontalHeaderLabels(
            ["Feature", "Tier Default", "Custom Override", "Actions"]
        )
        self._overrides_table.setStyleSheet(get_table_stylesheet())
        overrides_layout.addWidget(self._overrides_table)

        layout.addWidget(overrides_group)
        layout.addStretch()

        return tab

    def _create_service_tab(self) -> QWidget:
        """Create Service History sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Vehicle selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Vehicle:"))
        self._service_vehicle_combo = QComboBox()
        self._service_vehicle_combo.currentIndexChanged.connect(
            self._on_service_vehicle_changed
        )
        selector_layout.addWidget(self._service_vehicle_combo)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Stats cards
        stats_layout = QHBoxLayout()
        self._stat_total = QGroupBox("Total Services")
        self._stat_last = QGroupBox("Last Service")
        self._stat_cost = QGroupBox("Total Cost")
        stats_layout.addWidget(self._stat_total)
        stats_layout.addWidget(self._stat_last)
        stats_layout.addWidget(self._stat_cost)
        layout.addLayout(stats_layout)

        # Service records table
        self._service_table = QTableWidget()
        self._service_table.setColumnCount(5)
        self._service_table.setHorizontalHeaderLabels(
            ["Date", "Type", "Component", "Cost", "Mileage"]
        )
        self._service_table.setStyleSheet(get_table_stylesheet())
        layout.addWidget(self._service_table)

        # OBD snapshot
        obd_group = QGroupBox("Latest OBD Snapshot")
        obd_layout = QGridLayout(obd_group)
        self._obd_labels = {}
        obd_fields = ["RPM", "Speed", "Coolant Temp", "Battery Voltage",
                      "Engine Load", "Throttle"]
        for i, field in enumerate(obd_fields):
            obd_layout.addWidget(QLabel(f"{field}:"), i // 3, (i % 3) * 2)
            self._obd_labels[field] = QLabel("N/A")
            obd_layout.addWidget(self._obd_labels[field], i // 3, (i % 3) * 2 + 1)
        layout.addWidget(obd_group)

        return tab

    def _create_billing_tab(self) -> QWidget:
        """Create Billing sub-tab (read-only)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._billing_table = QTableWidget()
        self._billing_table.setColumnCount(4)
        self._billing_table.setHorizontalHeaderLabels(
            ["Date", "Description", "Amount", "Status"]
        )
        self._billing_table.setStyleSheet(get_table_stylesheet())
        layout.addWidget(self._billing_table)

        self._billing_placeholder = QLabel("No billing data available")
        self._billing_placeholder.setAlignment(Qt.AlignCenter)
        self._billing_placeholder.hide()
        layout.addWidget(self._billing_placeholder)

        return tab

    def _create_fleet_tab(self) -> QWidget:
        """Create Fleet Info sub-tab (read-only)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fleet_info = QFormLayout()
        self._fleet_role_label = QLabel("N/A")
        fleet_info.addRow("Fleet Role:", self._fleet_role_label)
        layout.addLayout(fleet_info)

        self._fleet_table = QTableWidget()
        self._fleet_table.setColumnCount(3)
        self._fleet_table.setHorizontalHeaderLabels(
            ["Vehicle", "Driver", "Status"]
        )
        self._fleet_table.setStyleSheet(get_table_stylesheet())
        layout.addWidget(self._fleet_table)

        self._fleet_placeholder = QLabel("User is not part of a fleet")
        self._fleet_placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._fleet_placeholder)

        layout.addStretch()
        return tab

    def _create_api_keys_tab(self) -> QWidget:
        """Create API Keys sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # API Keys table
        self._api_keys_table = QTableWidget()
        self._api_keys_table.setColumnCount(5)
        self._api_keys_table.setHorizontalHeaderLabels(
            ["Name", "Key ID", "Status", "Expires", "Actions"]
        )
        self._api_keys_table.setStyleSheet(get_table_stylesheet())
        layout.addWidget(self._api_keys_table)

        # Generate new key section
        gen_group = QGroupBox("Generate New API Key")
        gen_layout = QHBoxLayout(gen_group)
        
        gen_layout.addWidget(QLabel("Name:"))
        self._new_key_name = QLineEdit()
        self._new_key_name.setPlaceholderText("e.g., Desktop App")
        gen_layout.addWidget(self._new_key_name)
        
        gen_layout.addWidget(QLabel("Expires (days):"))
        self._new_key_expiry = QComboBox()
        self._new_key_expiry.addItems(["30", "90", "365", "Never"])
        self._new_key_expiry.setCurrentIndex(2)  # Default to 365
        gen_layout.addWidget(self._new_key_expiry)
        
        self._generate_key_btn = QPushButton("Generate Key")
        self._generate_key_btn.clicked.connect(self._on_generate_api_key)
        gen_layout.addWidget(self._generate_key_btn)
        
        layout.addWidget(gen_group)
        
        # Display area for newly generated key (shown once)
        self._new_key_display = QTextEdit()
        self._new_key_display.setReadOnly(True)
        self._new_key_display.setMaximumHeight(80)
        self._new_key_display.setPlaceholderText("New API key will appear here...")
        self._new_key_display.hide()
        layout.addWidget(self._new_key_display)

        return tab

    def _load_user_data(self):
        """Load user data from API."""
        worker = APIWorker(self._api.get_user, self._user_id)
        worker.finished.connect(self._on_user_data_loaded)
        worker.error.connect(self._on_load_error)
        worker.start()

    def _on_user_data_loaded(self, result: dict):
        """Handle user data loaded."""
        self._user_data = result
        user = result.get("user", {})

        # Update info tab
        self._info_name.setText(user.get("name", ""))
        self._info_email.setText(user.get("email", "N/A"))
        self._info_phone.setText(user.get("phone", ""))
        self._info_role.setText(user.get("role", "owner"))
        self._info_status.setText(user.get("status", "active").capitalize())
        self._info_registered.setText(
            self._format_timestamp(user.get("created_at"))
        )
        self._info_last_login.setText(
            self._format_timestamp(user.get("last_login"))
        )

        # Update tier tab
        tier = user.get("tier", "free")
        self._current_tier_label.setText(tier.capitalize())
        self._tier_combo.setCurrentText(tier)
        self._update_features_table(tier)

        # Load vehicles
        self._load_vehicles()

        # Load billing (may fail - that's ok)
        self._load_billing()
        
        # Load API keys
        self._load_api_keys()

    def _load_vehicles(self):
        """Load user vehicles."""
        worker = APIWorker(self._api.get_user_vehicles, self._user_id)
        worker.finished.connect(self._on_vehicles_loaded)
        worker.start()

    def _on_vehicles_loaded(self, result: dict):
        """Handle vehicles loaded."""
        vehicles = result.get("vehicles", [])
        self._vehicles = vehicles

        # Update vehicles table
        self._vehicles_table.setRowCount(len(vehicles))
        for i, v in enumerate(vehicles):
            self._vehicles_table.setItem(
                i, 0, QTableWidgetItem(f"{v.get('make', '')} {v.get('model', '')}")
            )
            self._vehicles_table.setItem(
                i, 1, QTableWidgetItem(str(v.get('year', '')))
            )
            self._vehicles_table.setItem(
                i, 2, QTableWidgetItem(v.get('license_plate', '') or v.get('vin', 'N/A'))
            )
            btn = QPushButton("Delete")
            self._vehicles_table.setCellWidget(i, 3, btn)

        # Update vehicle selector in service tab
        self._service_vehicle_combo.clear()
        for v in vehicles:
            name = f"{v.get('make', '')} {v.get('model', '')} ({v.get('year', '')})"
            self._service_vehicle_combo.addItem(name, v.get('id'))

        # Update info tab vehicle info
        if vehicles:
            v = vehicles[0]
            self._info_vehicle_make.setText(v.get('make', 'N/A'))
            self._info_vehicle_model.setText(v.get('model', 'N/A'))
            self._info_vehicle_year.setText(str(v.get('year', 'N/A')))
            self._info_vehicle_plate.setText(v.get('license_plate', '') or v.get('vin', 'N/A'))

    def _load_billing(self):
        """Load billing data (may fail)."""
        # For now, show placeholder as billing API may not exist
        self._billing_placeholder.show()
        self._billing_table.hide()

    def _on_load_error(self, error_msg: str):
        """Handle load error."""
        logger.error(f"Failed to load user data: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load user data:\n{error_msg}")

    def _on_edit_clicked(self):
        """Enable editing of user info."""
        self._info_name.setEnabled(True)
        self._info_phone.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._edit_btn.setEnabled(False)

    def _on_save_clicked(self):
        """Save user info changes."""
        self._save_btn.setEnabled(False)

        worker = APIWorker(
            self._api.update_user,
            self._user_id,
            name=self._info_name.text(),
            phone=self._info_phone.text()
        )
        worker.finished.connect(self._on_save_complete)
        worker.error.connect(self._on_save_error)
        worker.start()

    def _on_save_complete(self, result: dict):
        """Handle save complete."""
        self._info_name.setEnabled(False)
        self._info_phone.setEnabled(False)
        self._edit_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "User updated successfully")

    def _on_save_error(self, error_msg: str):
        """Handle save error."""
        self._save_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to save:\n{error_msg}")

    def _on_tier_changed(self, tier: str):
        """Handle tier selection change."""
        self._update_features_table(tier)

    def _update_features_table(self, tier: str):
        """Update features table based on selected tier."""
        limits = TIER_LIMITS.get(tier.lower(), TIER_LIMITS["free"])
        current_tier = self._user_data.get("user", {}).get("tier", "free")
        current_limits = TIER_LIMITS.get(current_tier.lower(), TIER_LIMITS["free"])

        mappings = [
            ("Vehicles", "vehicles"),
            ("DTC Checks", "dtc_checks"),
            ("Predictions/day", "predictions_day"),
            ("LLM Chat/day", "llm_chat_day"),
            ("PDFs/week", "pdfs_week"),
            ("Guardian", "guardian"),
            ("Fleet", "fleet"),
            ("History", "history_days"),
        ]

        for i, (label, key) in enumerate(mappings):
            current = current_limits.get(key, 0)
            new = limits.get(key, 0)

            # Format values
            if isinstance(current, bool):
                current_str = "Yes" if current else "No"
            elif current == -1:
                current_str = "Unlimited"
            else:
                current_str = str(current)

            if isinstance(new, bool):
                new_str = "Yes" if new else "No"
            elif new == -1:
                new_str = "Unlimited"
            else:
                new_str = str(new)

            self._features_table.setItem(i, 1, QTableWidgetItem(current_str))
            self._features_table.setItem(i, 2, QTableWidgetItem(new_str))

    def _on_apply_tier(self):
        """Apply tier change."""
        tier = self._tier_combo.currentText()

        reply = QMessageBox.question(
            self, "Confirm",
            f"Change user tier to '{tier}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._apply_tier_btn.setEnabled(False)

        worker = APIWorker(self._api.change_user_tier, self._user_id, tier)
        worker.finished.connect(self._on_tier_applied)
        worker.error.connect(self._on_tier_error)
        worker.start()

    def _on_tier_applied(self, result: dict):
        """Handle tier applied."""
        self._apply_tier_btn.setEnabled(True)
        tier = result.get("new_tier", "free")
        self._current_tier_label.setText(tier.capitalize())
        self._update_features_table(tier)
        QMessageBox.information(self, "Success", f"Tier changed to {tier}")

    def _on_tier_error(self, error_msg: str):
        """Handle tier change error."""
        self._apply_tier_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to change tier:\n{error_msg}")

    def _on_service_vehicle_changed(self, index: int):
        """Handle service vehicle selection change."""
        vehicle_id = self._service_vehicle_combo.itemData(index)
        if not vehicle_id:
            return

        # Load service records
        worker = APIWorker(self._api.get_service_records, vehicle_id)
        worker.finished.connect(self._on_service_records_loaded)
        worker.start()

        # Load OBD data
        worker2 = APIWorker(self._api.get_latest_vehicle_data, vehicle_id)
        worker2.finished.connect(self._on_obd_data_loaded)
        worker2.start()

    def _on_service_records_loaded(self, result: dict):
        """Handle service records loaded."""
        records = result.get("records", [])
        self._service_table.setRowCount(len(records))

        for i, r in enumerate(records):
            self._service_table.setItem(
                i, 0, QTableWidgetItem(self._format_timestamp(r.get("date")))
            )
            self._service_table.setItem(
                i, 1, QTableWidgetItem(r.get("type", "N/A"))
            )
            self._service_table.setItem(
                i, 2, QTableWidgetItem(r.get("component", "N/A"))
            )
            self._service_table.setItem(
                i, 3, QTableWidgetItem(f"${r.get('cost', 0)}")
            )
            self._service_table.setItem(
                i, 4, QTableWidgetItem(str(r.get("mileage", "N/A")))
            )

    def _on_obd_data_loaded(self, result: dict):
        """Handle OBD data loaded."""
        data = result.get("data", {})
        self._obd_labels["RPM"].setText(str(data.get("rpm", "N/A")))
        self._obd_labels["Speed"].setText(str(data.get("speed", "N/A")))
        self._obd_labels["Coolant Temp"].setText(str(data.get("coolant_temp", "N/A")))
        self._obd_labels["Battery Voltage"].setText(str(data.get("battery_voltage", "N/A")))
        self._obd_labels["Engine Load"].setText(str(data.get("engine_load", "N/A")))
        self._obd_labels["Throttle"].setText(str(data.get("throttle", "N/A")))

    def _format_timestamp(self, ts: float) -> str:
        """Format timestamp to readable string."""
        if not ts:
            return "N/A"
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        except Exception:
            return str(ts)

    def _load_api_keys(self):
        """Load user's API keys."""
        worker = APIWorker(self._api.get_user_api_keys, self._user_id)
        worker.finished.connect(self._on_api_keys_loaded)
        worker.error.connect(lambda e: logger.error(f"Failed to load API keys: {e}"))
        worker.start()

    def _on_api_keys_loaded(self, result: dict):
        """Handle API keys loaded."""
        keys = result.get("api_keys", [])
        self._api_keys_table.setRowCount(len(keys))

        for i, k in enumerate(keys):
            self._api_keys_table.setItem(i, 0, QTableWidgetItem(str(k.get("name", "Default"))))
            self._api_keys_table.setItem(i, 1, QTableWidgetItem(str(k.get("id", "N/A"))))
            
            status = k.get("status", "unknown")
            status_item = QTableWidgetItem(status.capitalize())
            if status == "active":
                status_item.setForeground(Qt.green)
            elif status == "revoked":
                status_item.setForeground(Qt.red)
            self._api_keys_table.setItem(i, 2, status_item)
            
            expires = k.get("expires_at")
            expires_str = self._format_timestamp(expires) if expires else "Never"
            self._api_keys_table.setItem(i, 3, QTableWidgetItem(expires_str))
            
            # Actions button
            btn = QPushButton("Revoke")
            btn.setEnabled(status == "active")
            # btn.clicked.connect(lambda checked, kid=k.get("id"): self._on_revoke_key(kid))
            self._api_keys_table.setCellWidget(i, 4, btn)

    def _on_generate_api_key(self):
        """Generate new API key."""
        name = self._new_key_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Please enter a name for the API key")
            return

        expiry_text = self._new_key_expiry.currentText()
        expires_days = 0 if expiry_text == "Never" else int(expiry_text)

        self._generate_key_btn.setEnabled(False)
        
        worker = APIWorker(self._api.generate_api_key, self._user_id, name, expires_days)
        worker.finished.connect(self._on_key_generated)
        worker.error.connect(self._on_key_generate_error)
        worker.start()

    def _on_key_generated(self, result: dict):
        """Handle API key generated."""
        self._generate_key_btn.setEnabled(True)
        api_key = result.get("api_key", "")
        
        if api_key:
            self._new_key_display.setText(
                f"New API Key Generated (copy now - shown only once):\n\n{api_key}"
            )
            self._new_key_display.setStyleSheet(
                f"background-color: #d4edda; color: #155724; padding: 10px;"
            )
            self._new_key_display.show()
            self._new_key_name.clear()
            self._load_api_keys()  # Refresh the list

    def _on_key_generate_error(self, error_msg: str):
        """Handle API key generation error."""
        self._generate_key_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to generate API key:\n{error_msg}")

    def _on_delete_user(self):
        """Delete the user after confirmation."""
        reply = QMessageBox.warning(
            self, "Confirm Delete",
            f"Are you sure you want to delete user '{self._info_name.text()}'?\n\n"
            "This action cannot be undone. All user data including vehicles, "
            "predictions, and API keys will be permanently deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Double-check confirmation
        confirm_reply = QMessageBox.warning(
            self, "Final Confirmation",
            "This will PERMANENTLY DELETE all user data.\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm_reply != QMessageBox.Yes:
            return

        self._delete_btn.setEnabled(False)
        
        worker = APIWorker(self._api.delete_user, self._user_id, hard_delete=True)
        worker.finished.connect(self._on_delete_complete)
        worker.error.connect(self._on_delete_error)
        worker.start()

    def _on_delete_complete(self, result: dict):
        """Handle user deletion complete."""
        deleted = result.get("deleted_records", {})
        total_deleted = sum(deleted.values()) if deleted else 0
        
        QMessageBox.information(
            self, "Success",
            f"User deleted successfully.\n\n"
            f"Deleted {total_deleted} related records."
        )
        self.accept()  # Close dialog

    def _on_delete_error(self, error_msg: str):
        """Handle user deletion error."""
        self._delete_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to delete user:\n{error_msg}")
