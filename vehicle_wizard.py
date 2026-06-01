"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Wizard

Vehicle Wizard
==============

Multi-step wizard for adding new vehicle profiles to PredictOBD.
Provides guided creation of vehicle profiles with validation and
integration with the vehicle catalog.

Steps:
1. Basic Info - Vehicle identification (VIN, make, model, year)
2. OBD Settings - OBD-II adapter configuration
3. Advanced Options - Mileage tracking, custom settings
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox, QGroupBox,
    QTextEdit, QDateEdit, QDoubleSpinBox, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QIntValidator, QDoubleValidator, QFont

from config import get_config
import json

CONFIG = get_config()
logger = logging.getLogger(__name__)


class BasicInfoPage(QWizardPage):
    """Wizard page for basic vehicle information."""

    def __init__(self, vehicle_catalog=None):
        super().__init__()
        self.vehicle_catalog = vehicle_catalog
        self.setTitle("Vehicle Information")
        self.setSubTitle("Enter the basic details of your vehicle")

        layout = QFormLayout()

        # VIN (Vehicle Identification Number)
        self.vin_edit = QLineEdit()
        self.vin_edit.setPlaceholderText("17-character VIN")
        self.vin_edit.setMaxLength(17)
        self.vin_edit.textChanged.connect(self._validate_vin)
        layout.addRow("VIN:", self.vin_edit)

        # Vehicle Name (user-friendly name)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., My Toyota Camry")
        layout.addRow("Vehicle Name:", self.name_edit)

        # Make
        self.make_combo = QComboBox()
        self.make_combo.setEditable(True)
        self._populate_makes()
        self.make_combo.currentTextChanged.connect(self._on_make_changed)
        layout.addRow("Make:", self.make_combo)

        # Model
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self._populate_models("")
        layout.addRow("Model:", self.model_combo)

        # Year
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1990, QDate.currentDate().year() + 1)
        self.year_spin.setValue(QDate.currentDate().year())
        layout.addRow("Year:", self.year_spin)

        # Engine Type
        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "Gasoline",
            "Diesel",
            "Hybrid",
            "Electric",
            "Plug-in Hybrid",
            "Natural Gas"
        ])
        layout.addRow("Engine Type:", self.engine_combo)

        # Transmission
        self.trans_combo = QComboBox()
        self.trans_combo.addItems([
            "Automatic",
            "Manual",
            "CVT",
            "Dual-Clutch",
            "Semi-Automatic"
        ])
        layout.addRow("Transmission:", self.trans_combo)

        # Fuel Type
        self.fuel_combo = QComboBox()
        self.fuel_combo.addItems([
            "Regular Unleaded (87)",
            "Mid-Grade (89)",
            "Premium (91-93)",
            "Diesel",
            "Electric",
            "Hybrid"
        ])
        layout.addRow("Fuel Type:", self.fuel_combo)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Optional notes about this vehicle...")
        layout.addRow("Notes:", self.notes_edit)

        self.setLayout(layout)

        # Register fields for validation
        self.registerField("vin*", self.vin_edit)
        self.registerField("name*", self.name_edit)
        self.registerField("make*", self.make_combo, "currentText")
        self.registerField("model*", self.model_combo, "currentText")
        self.registerField("year*", self.year_spin)
        self.registerField("engine", self.engine_combo, "currentText")
        self.registerField("transmission", self.trans_combo, "currentText")
        self.registerField("fuel", self.fuel_combo, "currentText")
        self.registerField("notes", self.notes_edit, "plainText")

    def _populate_makes(self):
        """Populate makes from vehicle catalog or defaults."""
        default_makes = [
            "Toyota", "Honda", "Ford", "Chevrolet", "Nissan",
            "Hyundai", "Kia", "Volkswagen", "BMW", "Mercedes-Benz",
            "Audi", "Mazda", "Subaru", "Mitsubishi", "Jeep",
            "Dodge", "Chrysler", "Volvo", "Lexus", "Acura"
        ]
        self.make_combo.addItems(default_makes)

        # Try to load from vehicle catalog
        if self.vehicle_catalog:
            try:
                catalog_path = CONFIG.CONFIGS_DIR / "vehicle_catalog.json"
                if catalog_path.exists():
                    with open(catalog_path, 'r') as f:
                        catalog = json.load(f)
                        makes = list(catalog.keys())
                        if makes:
                            self.make_combo.clear()
                            self.make_combo.addItems(sorted(makes))
            except Exception as e:
                logger.warning(f"Could not load vehicle catalog: {e}")

    def _populate_models(self, make: str):
        """Populate models based on selected make."""
        self.model_combo.clear()
        default_models = [
            "Sedan", "SUV", "Truck", "Coupe", "Hatchback",
            "Wagon", "Van", "Convertible", "Crossover"
        ]

        # Try to load models from vehicle catalog
        if self.vehicle_catalog and make:
            try:
                catalog_path = CONFIG.CONFIGS_DIR / "vehicle_catalog.json"
                if catalog_path.exists():
                    with open(catalog_path, 'r') as f:
                        catalog = json.load(f)
                        if make in catalog:
                            models = catalog[make].get('models', [])
                            if models:
                                self.model_combo.addItems(sorted(models))
                                return
            except Exception as e:
                logger.warning(f"Could not load models from catalog: {e}")

        # Fall back to defaults
        self.model_combo.addItems(default_models)

    def _on_make_changed(self, make: str):
        """Handle make selection change."""
        self._populate_models(make)

    def _validate_vin(self, text: str):
        """Validate VIN format."""
        if text and len(text) != 17:
            self.vin_edit.setStyleSheet("QLineEdit { background-color: #ffeeee; }")
        else:
            self.vin_edit.setStyleSheet("")

    def validatePage(self):
        """Validate page before proceeding."""
        vin = self.vin_edit.text().strip()
        name = self.name_edit.text().strip()

        if not vin:
            QMessageBox.warning(self, "Validation Error", "VIN is required.")
            return False

        if len(vin) != 17:
            QMessageBox.warning(self, "Validation Error", "VIN must be exactly 17 characters.")
            return False

        if not name:
            QMessageBox.warning(self, "Validation Error", "Vehicle name is required.")
            return False

        return True


class OBDSettingsPage(QWizardPage):
    """Wizard page for OBD-II adapter settings."""

    def __init__(self):
        super().__init__()
        self.setTitle("OBD-II Adapter Settings")
        self.setSubTitle("Configure your OBD-II adapter connection")

        layout = QFormLayout()

        # Adapter Type
        self.adapter_combo = QComboBox()
        self.adapter_combo.addItems([
            "ELM327 (USB)",
            "ELM327 (Bluetooth)",
            "ELM327 (WiFi)",
            "STN11xx",
            "J2534 Pass-Thru",
            "Custom"
        ])
        layout.addRow("Adapter Type:", self.adapter_combo)

        # Connection Method
        conn_group = QGroupBox("Connection Method")
        conn_layout = QVBoxLayout()

        self.conn_radio_group = QButtonGroup()

        self.auto_radio = QRadioButton("Auto-Detect (Recommended)")
        self.auto_radio.setChecked(True)
        self.conn_radio_group.addButton(self.auto_radio, 0)

        self.bluetooth_radio = QRadioButton("Bluetooth")
        self.conn_radio_group.addButton(self.bluetooth_radio, 1)

        self.usb_radio = QRadioButton("USB")
        self.conn_radio_group.addButton(self.usb_radio, 2)

        self.wifi_radio = QRadioButton("WiFi")
        self.conn_radio_group.addButton(self.wifi_radio, 3)

        self.serial_radio = QRadioButton("Serial Port")
        self.conn_radio_group.addButton(self.serial_radio, 4)

        conn_layout.addWidget(self.auto_radio)
        conn_layout.addWidget(self.bluetooth_radio)
        conn_layout.addWidget(self.usb_radio)
        conn_layout.addWidget(self.wifi_radio)
        conn_layout.addWidget(self.serial_radio)
        conn_group.setLayout(conn_layout)
        layout.addRow(conn_group)

        # Bluetooth Address (if selected)
        self.bluetooth_edit = QLineEdit()
        self.bluetooth_edit.setPlaceholderText("e.g., 00:11:22:33:44:55")
        self.bluetooth_edit.setEnabled(False)
        layout.addRow("Bluetooth Address:", self.bluetooth_edit)

        # WiFi IP Address (if selected)
        self.wifi_ip_edit = QLineEdit()
        self.wifi_ip_edit.setPlaceholderText("e.g., 192.168.0.10")
        self.wifi_ip_edit.setEnabled(False)
        layout.addRow("WiFi IP Address:", self.wifi_ip_edit)

        # WiFi Port
        self.wifi_port_spin = QSpinBox()
        self.wifi_port_spin.setRange(1, 65535)
        self.wifi_port_spin.setValue(35000)
        self.wifi_port_spin.setEnabled(False)
        layout.addRow("WiFi Port:", self.wifi_port_spin)

        # Serial Port (if selected)
        self.serial_combo = QComboBox()
        self.serial_combo.setEditable(True)
        self.serial_combo.addItems([
            "COM1", "COM3", "COM4", "COM5", "COM6",
            "COM7", "COM8", "COM9", "COM10",
            "/dev/ttyUSB0", "/dev/ttyUSB1",
            "/dev/rfcomm0", "/dev/rfcomm1"
        ])
        self.serial_combo.setEnabled(False)
        layout.addRow("Serial Port:", self.serial_combo)

        # Baud Rate
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([
            "9600", "19200", "38400", "57600", "115200", "230400", "460800"
        ])
        self.baud_combo.setCurrentText("38400")
        layout.addRow("Baud Rate:", self.baud_combo)

        # Protocol
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems([
            "Auto-Detect",
            "SAE J1850 PWM",
            "SAE J1850 VPW",
            "ISO 9141-2",
            "ISO 14230-4 KWP",
            "ISO 15765-4 CAN (11 bit)",
            "ISO 15765-4 CAN (29 bit)"
        ])
        self.protocol_combo.setCurrentText("Auto-Detect")
        layout.addRow("Protocol:", self.protocol_combo)

        # Connection Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSuffix(" seconds")
        layout.addRow("Connection Timeout:", self.timeout_spin)

        # Auto-connect on startup
        self.auto_connect_check = QCheckBox("Auto-connect to this adapter on startup")
        self.auto_connect_check.setChecked(True)
        layout.addRow(self.auto_connect_check)

        self.setLayout(layout)

        # Connect radio buttons to enable/disable fields
        self.conn_radio_group.buttonClicked.connect(self._update_field_states)

        # Register fields
        self.registerField("adapter_type", self.adapter_combo, "currentText")
        self.registerField("connection_method", self.conn_radio_group, "checkedId")
        self.registerField("bluetooth_address", self.bluetooth_edit)
        self.registerField("wifi_ip", self.wifi_ip_edit)
        self.registerField("wifi_port", self.wifi_port_spin)
        self.registerField("serial_port", self.serial_combo, "currentText")
        self.registerField("baud_rate", self.baud_combo, "currentText")
        self.registerField("protocol", self.protocol_combo, "currentText")
        self.registerField("connection_timeout", self.timeout_spin)
        self.registerField("auto_connect", self.auto_connect_check)

    def _update_field_states(self):
        """Enable/disable fields based on connection method."""
        method = self.conn_radio_group.checkedId()

        # Reset all
        self.bluetooth_edit.setEnabled(False)
        self.wifi_ip_edit.setEnabled(False)
        self.wifi_port_spin.setEnabled(False)
        self.serial_combo.setEnabled(False)

        # Enable based on selection
        if method == 1:  # Bluetooth
            self.bluetooth_edit.setEnabled(True)
        elif method == 3:  # WiFi
            self.wifi_ip_edit.setEnabled(True)
            self.wifi_port_spin.setEnabled(True)
        elif method == 4:  # Serial
            self.serial_combo.setEnabled(True)


class AdvancedOptionsPage(QWizardPage):
    """Wizard page for advanced vehicle options."""

    def __init__(self):
        super().__init__()
        self.setTitle("Advanced Options")
        self.setSubTitle("Configure additional vehicle settings")

        layout = QFormLayout()

        # Initial Mileage
        self.mileage_spin = QSpinBox()
        self.mileage_spin.setRange(0, 5000000)
        self.mileage_spin.setSingleStep(1000)
        self.mileage_spin.setSuffix(" miles")
        self.mileage_spin.setValue(0)
        layout.addRow("Current Mileage:", self.mileage_spin)

        # Mileage Unit
        self.mileage_unit_combo = QComboBox()
        self.mileage_unit_combo.addItems(["Miles", "Kilometers"])
        layout.addRow("Mileage Unit:", self.mileage_unit_combo)

        # Oil Change Interval
        self.oil_interval_spin = QSpinBox()
        self.oil_interval_spin.setRange(1000, 20000)
        self.oil_interval_spin.setSingleStep(500)
        self.oil_interval_spin.setSuffix(" miles")
        self.oil_interval_spin.setValue(5000)
        layout.addRow("Oil Change Interval:", self.oil_interval_spin)

        # Tire Rotation Interval
        self.tire_interval_spin = QSpinBox()
        self.tire_interval_spin.setRange(1000, 15000)
        self.tire_interval_spin.setSingleStep(500)
        self.tire_interval_spin.setSuffix(" miles")
        self.tire_interval_spin.setValue(7500)
        layout.addRow("Tire Rotation Interval:", self.tire_interval_spin)

        # Service Reminders
        reminders_group = QGroupBox("Service Reminders")
        reminders_layout = QVBoxLayout()

        self.oil_reminder_check = QCheckBox("Oil Change Reminder")
        self.oil_reminder_check.setChecked(True)
        reminders_layout.addWidget(self.oil_reminder_check)

        self.tire_reminder_check = QCheckBox("Tire Rotation Reminder")
        self.tire_reminder_check.setChecked(True)
        reminders_layout.addWidget(self.tire_reminder_check)

        self.inspection_reminder_check = QCheckBox("Annual Inspection Reminder")
        self.inspection_reminder_check.setChecked(True)
        reminders_layout.addWidget(self.inspection_reminder_check)

        self.registration_reminder_check = QCheckBox("Registration Renewal Reminder")
        self.registration_reminder_check.setChecked(True)
        reminders_layout.addWidget(self.registration_reminder_check)

        reminders_group.setLayout(reminders_layout)
        layout.addRow(reminders_group)

        # AI Learning Settings
        ai_group = QGroupBox("AI Learning Settings")
        ai_layout = QVBoxLayout()

        self.enable_learning_check = QCheckBox("Enable AI Learning for this vehicle")
        self.enable_learning_check.setChecked(True)
        self.enable_learning_check.setToolTip("Allow AI to learn from this vehicle's data")
        ai_layout.addWidget(self.enable_learning_check)

        self.share_anonymous_check = QCheckBox("Share anonymous data for model improvement")
        self.share_anonymous_check.setChecked(False)
        self.share_anonymous_check.setToolTip("Help improve AI models by sharing anonymous data")
        ai_layout.addWidget(self.share_anonymous_check)

        ai_group.setLayout(ai_layout)
        layout.addRow(ai_group)

        # Data Retention
        retention_group = QGroupBox("Data Retention")
        retention_layout = QVBoxLayout()

        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(30, 3650)
        self.retention_spin.setSingleStep(30)
        self.retention_spin.setSuffix(" days")
        self.retention_spin.setValue(365)
        retention_layout.addWidget(QLabel("Keep OBD data for:"))
        retention_layout.addWidget(self.retention_spin)

        self.auto_archive_check = QCheckBox("Auto-archive old data")
        self.auto_archive_check.setChecked(True)
        retention_layout.addWidget(self.auto_archive_check)

        retention_group.setLayout(retention_layout)
        layout.addRow(retention_group)

        # Custom PIDs
        custom_group = QGroupBox("Custom PIDs (Optional)")
        custom_layout = QVBoxLayout()

        self.custom_pids_edit = QTextEdit()
        self.custom_pids_edit.setMaximumHeight(100)
        self.custom_pids_edit.setPlaceholderText(
            "Enter custom PIDs, one per line:\n"
            "Example:\n"
            "010C - RPM\n"
            "010D - Vehicle Speed"
        )
        custom_layout.addWidget(self.custom_pids_edit)

        custom_group.setLayout(custom_layout)
        layout.addRow(custom_group)

        self.setLayout(layout)

        # Register fields
        self.registerField("initial_mileage", self.mileage_spin)
        self.registerField("mileage_unit", self.mileage_unit_combo, "currentText")
        self.registerField("oil_interval", self.oil_interval_spin)
        self.registerField("tire_interval", self.tire_interval_spin)
        self.registerField("oil_reminder", self.oil_reminder_check)
        self.registerField("tire_reminder", self.tire_reminder_check)
        self.registerField("inspection_reminder", self.inspection_reminder_check)
        self.registerField("registration_reminder", self.registration_reminder_check)
        self.registerField("enable_learning", self.enable_learning_check)
        self.registerField("share_anonymous", self.share_anonymous_check)
        self.registerField("data_retention", self.retention_spin)
        self.registerField("auto_archive", self.auto_archive_check)
        self.registerField("custom_pids", self.custom_pids_edit, "plainText")


class SummaryPage(QWizardPage):
    """Wizard page showing summary before saving."""

    def __init__(self):
        super().__init__()
        self.setTitle("Summary")
        self.setSubTitle("Review your vehicle profile before saving")

        layout = QVBoxLayout()

        # Summary text
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.PlainText)
        self.summary_label.setStyleSheet("QLabel { font-size: 12px; padding: 10px; background-color: #f5f5f5; border-radius: 5px; }")
        layout.addWidget(self.summary_label)

        # Checkbox to confirm
        self.confirm_check = QCheckBox("I confirm the information above is correct")
        self.confirm_check.stateChanged.connect(self.completeChanged)
        layout.addWidget(self.confirm_check)

        self.setLayout(layout)

    def initializePage(self):
        """Initialize page with summary from previous pages."""
        wizard = self.wizard()

        # Gather all field values
        summary = "=== Vehicle Profile Summary ===\n\n"
        summary += f"VIN: {wizard.field('vin')}\n"
        summary += f"Name: {wizard.field('name')}\n"
        summary += f"Vehicle: {wizard.field('year')} {wizard.field('make')} {wizard.field('model')}\n"
        summary += f"Engine: {wizard.field('engine')}\n"
        summary += f"Transmission: {wizard.field('transmission')}\n"
        summary += f"Fuel: {wizard.field('fuel')}\n\n"

        summary += "=== OBD Settings ===\n"
        summary += f"Adapter: {wizard.field('adapter_type')}\n"
        summary += f"Protocol: {wizard.field('protocol')}\n"
        summary += f"Baud Rate: {wizard.field('baud_rate')}\n"
        summary += f"Timeout: {wizard.field('connection_timeout')}s\n\n"

        summary += "=== Advanced Options ===\n"
        summary += f"Initial Mileage: {wizard.field('initial_mileage')} {wizard.field('mileage_unit')}\n"
        summary += f"Oil Change Interval: {wizard.field('oil_interval')} miles\n"
        summary += f"Tire Rotation Interval: {wizard.field('tire_interval')} miles\n"
        summary += f"AI Learning: {'Enabled' if wizard.field('enable_learning') else 'Disabled'}\n"
        summary += f"Data Retention: {wizard.field('data_retention')} days\n"

        notes = wizard.field('notes')
        if notes:
            summary += f"\nNotes: {notes}\n"

        self.summary_label.setText(summary)

    def isComplete(self):
        """Check if page is complete."""
        return self.confirm_check.isChecked()


class VehicleWizard(QWizard):
    """
    Multi-step wizard for creating new vehicle profiles.
    """

    # Signal emitted when vehicle is successfully created
    vehicleCreated = Signal(dict)

    def __init__(self, parent=None, vehicle_catalog=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Vehicle")
        self.setMinimumSize(600, 500)
        self.setWizardStyle(QWizard.ModernStyle)

        # Set wizard options
        self.setOption(QWizard.HaveHelpButton, False)
        self.setOption(QWizard.HaveCustomButton1, True)
        self.setButtonText(QWizard.CustomButton1, "Load from Catalog")
        self.customButtonClicked.connect(self._load_from_catalog)

        self.vehicle_catalog = vehicle_catalog

        # Add pages
        self.addPage(BasicInfoPage(vehicle_catalog))
        self.addPage(OBDSettingsPage())
        self.addPage(AdvancedOptionsPage())
        self.addPage(SummaryPage())

    def _load_from_catalog(self):
        """Load vehicle data from catalog (placeholder)."""
        QMessageBox.information(
            self,
            "Load from Catalog",
            "This feature will allow you to select a vehicle from the catalog.\n\n"
            "For now, please enter the vehicle details manually."
        )

    def get_vehicle_data(self) -> Dict[str, Any]:
        """
        Get all collected vehicle data from the wizard.

        Returns:
            Dictionary with all vehicle profile fields
        """
        return {
            'vin': self.field('vin'),
            'name': self.field('name'),
            'make': self.field('make'),
            'model': self.field('model'),
            'year': self.field('year'),
            'engine': self.field('engine'),
            'transmission': self.field('transmission'),
            'fuel': self.field('fuel'),
            'notes': self.field('notes'),
            'adapter_type': self.field('adapter_type'),
            'connection_method': self.field('connection_method'),
            'bluetooth_address': self.field('bluetooth_address'),
            'wifi_ip': self.field('wifi_ip'),
            'wifi_port': self.field('wifi_port'),
            'serial_port': self.field('serial_port'),
            'baud_rate': self.field('baud_rate'),
            'protocol': self.field('protocol'),
            'connection_timeout': self.field('connection_timeout'),
            'auto_connect': self.field('auto_connect'),
            'initial_mileage': self.field('initial_mileage'),
            'mileage_unit': self.field('mileage_unit'),
            'oil_interval': self.field('oil_interval'),
            'tire_interval': self.field('tire_interval'),
            'oil_reminder': self.field('oil_reminder'),
            'tire_reminder': self.field('tire_reminder'),
            'inspection_reminder': self.field('inspection_reminder'),
            'registration_reminder': self.field('registration_reminder'),
            'enable_learning': self.field('enable_learning'),
            'share_anonymous': self.field('share_anonymous'),
            'data_retention': self.field('data_retention'),
            'auto_archive': self.field('auto_archive'),
            'custom_pids': self.field('custom_pids'),
            'created_at': __import__('datetime').datetime.now().isoformat(),
            'active': True
        }

    def accept(self):
        """Handle wizard acceptance."""
        try:
            vehicle_data = self.get_vehicle_data()

            # Save to database
            from db_utils import DatabaseManager

            db = DatabaseManager(CONFIG.PROFILES_DB_PATH)

            # Check if VIN already exists
            existing = db.get_profile_by_vin(vehicle_data['vin'])
            if existing:
                reply = QMessageBox.question(
                    self,
                    "VIN Already Exists",
                    f"A vehicle with VIN {vehicle_data['vin']} already exists.\n\n"
                    "Do you want to update it?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

                # Update existing profile
                db.update_profile(existing['profile_id'], vehicle_data)
                logger.info(f"Updated vehicle profile: {vehicle_data['name']}")
            else:
                # Create new profile
                profile_id = db.create_profile(vehicle_data)
                vehicle_data['profile_id'] = profile_id
                logger.info(f"Created vehicle profile: {vehicle_data['name']}")

            # Emit signal
            self.vehicleCreated.emit(vehicle_data)

            # Show success message
            QMessageBox.information(
                self,
                "Vehicle Added Successfully",
                f"Vehicle '{vehicle_data['name']}' has been added to your profiles."
            )

            super().accept()

        except Exception as e:
            logger.error(f"Error saving vehicle profile: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save vehicle profile:\n{str(e)}"
            )


def show_vehicle_wizard(parent=None, vehicle_catalog=None):
    """
    Convenience function to show the vehicle wizard.

    Args:
        parent: Parent widget
        vehicle_catalog: Optional vehicle catalog data

    Returns:
        The created vehicle data if successful, None otherwise
    """
    wizard = VehicleWizard(parent, vehicle_catalog)
    result = wizard.exec()

    if result == QWizard.Accepted:
        return wizard.get_vehicle_data()
    return None


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    wizard = VehicleWizard()
    wizard.show()
    sys.exit(app.exec())
