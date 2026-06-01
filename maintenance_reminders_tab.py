"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Maintenance Reminders Tab
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QFrame, QDialog,
    QDialogButtonBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from maintenance_reminders import MaintenanceRemindersSystem, MaintenancePredictor, get_maintenance_predictor
    REMINDER_SYSTEM_AVAILABLE = True
except ImportError:
    REMINDER_SYSTEM_AVAILABLE = False

logger = logging.getLogger(__name__)


class ReminderDialog(QDialog):
    """Dialog for adding/editing maintenance reminders"""

    def __init__(self, parent=None, reminder=None):
        super().__init__(parent)
        self.reminder = reminder
        self.setWindowTitle("Add Reminder" if not reminder else "Edit Reminder")
        self.setMinimumWidth(450)
        self._setup_ui()

        if reminder:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit, QComboBox, QSpinBox {
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

        # Reminder type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Oil Change",
            "Tire Rotation",
            "Brake Inspection",
            "Battery Replacement",
            "Air Filter",
            "Coolant Flush",
            "Transmission Service",
            "Spark Plugs"
        ])
        form.addRow("Type:", self.type_combo)

        # Due type (mileage-based or time-based)
        self.due_type_combo = QComboBox()
        self.due_type_combo.addItems(["Mileage-based", "Time-based"])
        form.addRow("Due Type:", self.due_type_combo)

        # Interval value
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 100000)
        self.interval_spin.setSuffix(" miles")
        self.interval_spin.setValue(5000)
        form.addRow("Interval:", self.interval_spin)

        # Time interval (for time-based)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setSuffix(" days")
        self.days_spin.setValue(90)
        form.addRow("Days:", self.days_spin)

        # Notes
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Additional notes (optional)")
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_fields(self):
        """Populate fields with existing reminder data"""
        if self.reminder:
            self.type_combo.setCurrentText(self.reminder.get('type', 'Oil Change'))
            self.due_type_combo.setCurrentText(self.reminder.get('due_type', 'Mileage-based'))
            self.interval_spin.setValue(self.reminder.get('interval', 5000))
            self.days_spin.setValue(self.reminder.get('days', 90))
            self.notes_edit.setText(self.reminder.get('notes', ''))

    def get_reminder_data(self) -> Dict[str, Any]:
        """Get reminder data from form"""
        data = {
            'type': self.type_combo.currentText(),
            'due_type': self.due_type_combo.currentText(),
            'interval': self.interval_spin.value(),
            'days': self.days_spin.value(),
            'notes': self.notes_edit.text().strip()
        }

        if self.due_type_combo.currentText() == 'Time-based':
            data['interval'] = None
        else:
            data['days'] = None

        return data


class MaintenanceRemindersTab(QWidget):
    """
    Maintenance Reminders Tab - Track upcoming maintenance reminders
    """

    def __init__(self, reminder_system=None):
        super().__init__()
        self.reminder_system = reminder_system
        self.maintenance_predictor = None
        self.reminders = []
        self.completed_history = []

        # Initialize backend predictor
        if REMINDER_SYSTEM_AVAILABLE:
            try:
                if self.reminder_system:
                    # Wrap the existing reminder system in the adapter
                    self.maintenance_predictor = MaintenancePredictor(self.reminder_system)
                else:
                    # Try to get singleton
                    self.maintenance_predictor = get_maintenance_predictor()
            except Exception as e:
                logger.warning(f"Failed to initialize maintenance predictor: {e}")
                self.maintenance_predictor = None

        self._setup_ui()
        self._load_reminders()

    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Upcoming reminders list
        reminders_group = QGroupBox("Upcoming Reminders")
        reminders_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        reminders_layout = QVBoxLayout(reminders_group)

        self.reminders_table = QTableWidget()
        self.reminders_table.setColumnCount(6)
        self.reminders_table.setHorizontalHeaderLabels([
            "Type", "Due", "Interval", "Status", "Actions"
        ])
        self._apply_table_style(self.reminders_table)
        reminders_layout.addWidget(self.reminders_table)

        layout.addWidget(reminders_group)

        # Completed maintenance history
        history_group = QGroupBox("Completed Maintenance")
        history_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels([
            "Type", "Completed Date", "Notes", "Actions"
        ])
        self._apply_table_style(self.history_table)
        history_layout.addWidget(self.history_table)

        layout.addWidget(history_group)

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with title and actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Maintenance Reminders")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        layout.addStretch()

        add_btn = QPushButton("+ Add Reminder")
        add_btn.setStyleSheet(self._get_button_style('primary'))
        add_btn.clicked.connect(self._add_reminder)
        layout.addWidget(add_btn)

        return widget

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

    def _load_reminders(self):
        """Load reminders from backend"""
        try:
            if self.maintenance_predictor:
                # Get current profile ID
                profile_id = self._get_current_profile_id()
                if profile_id:
                    # Get current odometer from profile
                    current_odometer = self._get_current_odometer(profile_id)
                    
                    # Load reminders from backend
                    self.reminders = self.maintenance_predictor.get_upcoming_maintenance(
                        profile_id=profile_id,
                        current_odometer_km=current_odometer
                    )
                    
                    # Load service history
                    self.completed_history = self.maintenance_predictor.get_service_history(profile_id)
                else:
                    logger.warning("No active profile, showing empty data")
                    self.reminders = []
                    self.completed_history = []
            else:
                logger.warning("Maintenance predictor not available, showing empty data")
                self.reminders = []
                self.completed_history = []
        except Exception as e:
            logger.error(f"Error loading reminders: {e}")
            self.reminders = []
            self.completed_history = []

        self._update_reminders_table()
        self._update_history_table()
    
    def _get_current_profile_id(self):
        """Get the current vehicle profile ID from parent window"""
        try:
            # Try to get from parent window
            parent = self.parent()
            while parent:
                if hasattr(parent, 'current_profile') and parent.current_profile:
                    return parent.current_profile.get('profile_id')
                if hasattr(parent, 'vehicle_manager') and parent.vehicle_manager:
                    # Get active profile from manager
                    active_profile = parent.vehicle_manager.get_active_profile()
                    if active_profile:
                        return active_profile.get('profile_id')
                parent = parent.parent()
        except Exception as e:
            logger.debug(f"Could not get current profile ID: {e}")
        return None
    
    def _get_current_odometer(self, profile_id):
        """Get current odometer reading for profile"""
        try:
            # Try to get from parent window's vehicle manager
            parent = self.parent()
            while parent:
                if hasattr(parent, 'vehicle_manager') and parent.vehicle_manager:
                    profile = parent.vehicle_manager.get_profile(profile_id)
                    if profile:
                        # Check for odometer in various fields
                        if profile.get('last_odometer'):
                            return int(profile.get('last_odometer', 0))
                        if profile.get('current_mileage'):
                            return int(profile.get('current_mileage', 0))
                        if profile.get('total_distance'):
                            return int(profile.get('total_distance', 0))
                parent = parent.parent()
        except Exception as e:
            logger.debug(f"Could not get current odometer: {e}")
        return 0

    def _update_reminders_table(self):
        """Update upcoming reminders table"""
        self.reminders_table.setRowCount(0)

        for reminder in self.reminders:
            row = self.reminders_table.rowCount()
            self.reminders_table.insertRow(row)

            self.reminders_table.setItem(row, 0, QTableWidgetItem(reminder.get('type', '')))

            # Calculate due date/days until due
            if reminder.get('due_type') == 'Time-based':
                due_info = f"{reminder.get('due_date', '')} ({reminder.get('days', 0)} days)"
            else:
                due_mileage = reminder.get('due_mileage', 0)
                current_mileage = reminder.get('current_mileage', 0)
                miles_until = max(0, due_mileage - current_mileage)
                due_info = f"{miles_until} miles"

            self.reminders_table.setItem(row, 1, QTableWidgetItem(due_info))

            interval = f"{reminder.get('interval', 0)} miles" if reminder.get('due_type') == 'Mileage-based' else f"{reminder.get('days', 0)} days"
            self.reminders_table.setItem(row, 2, QTableWidgetItem(interval))

            status = reminder.get('status', '')
            status_item = QTableWidgetItem(status.replace('_', ' ').title())
            if status == 'due_soon':
                status_item.setForeground(QColor("#FFC107"))
            elif status == 'due':
                status_item.setForeground(QColor("#FF9800"))
            else:
                status_item.setForeground(QColor("#4CAF50"))
            self.reminders_table.setItem(row, 3, status_item)

            # Add action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            snooze_btn = QPushButton("Snooze")
            snooze_btn.setStyleSheet(self._get_button_style('secondary'))
            snooze_btn.clicked.connect(lambda: self._snooze_reminder(row))

            dismiss_btn = QPushButton("Dismiss")
            dismiss_btn.setStyleSheet("background-color: #F44336; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            dismiss_btn.clicked.connect(lambda: self._dismiss_reminder(row))

            actions_layout.addWidget(snooze_btn)
            actions_layout.addWidget(dismiss_btn)
            self.reminders_table.setCellWidget(row, 4, actions_widget)

        self.reminders_table.resizeColumnsToContents()

    def _update_history_table(self):
        """Update completed maintenance history table"""
        self.history_table.setRowCount(0)

        for item in self.completed_history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            self.history_table.setItem(row, 0, QTableWidgetItem(item.get('type', '')))
            self.history_table.setItem(row, 1, QTableWidgetItem(item.get('completed_date', '')))
            self.history_table.setItem(row, 2, QTableWidgetItem(item.get('notes', '')))

            # Add view button
            view_btn = QPushButton("View")
            view_btn.setStyleSheet("background-color: #C40000; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            self.history_table.setCellWidget(row, 3, view_btn)

        self.history_table.resizeColumnsToContents()

    def _add_reminder(self):
        """Add new reminder"""
        dialog = ReminderDialog(self)

        if dialog.exec() == QDialog.Accepted:
            reminder_data = dialog.get_reminder_data()
            reminder_data['status'] = 'upcoming'

            # Get current profile ID
            profile_id = self._get_current_profile_id()
            
            if not profile_id:
                QMessageBox.warning(self, "Error", "No active vehicle profile. Please select a vehicle first.")
                return

            # Transform dialog data to backend format
            backend_data = {
                'name': reminder_data.get('type', 'Custom Service'),
                'description': reminder_data.get('notes', ''),
                'mileage_interval_km': reminder_data.get('interval'),
                'time_interval_days': reminder_data.get('days'),
                'priority': 'medium',
                'warning_threshold_km': 1000,
                'warning_threshold_days': 30
            }

            # Save to backend if available
            if self.maintenance_predictor:
                try:
                    success = self.maintenance_predictor.add_reminder(
                        profile_id=profile_id,
                        reminder_data=backend_data
                    )
                    if success:
                        # Reload reminders from backend
                        self._load_reminders()
                        QMessageBox.information(self, "Reminder Added", f"Reminder '{reminder_data['type']}' added successfully!")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to save reminder to backend.")
                except Exception as e:
                    logger.error(f"Error saving reminder: {e}")
                    QMessageBox.warning(self, "Error", f"Failed to save reminder: {e}")
            else:
                # Fallback to local list
                self.reminders.append(reminder_data)
                self._update_reminders_table()
                QMessageBox.information(self, "Reminder Added", f"Reminder '{reminder_data['type']}' added locally!")

    def _snooze_reminder(self, row: int):
        """Snooze a reminder"""
        if row < len(self.reminders):
            reminder = self.reminders[row]
            
            # Try to snooze in backend
            if self.maintenance_predictor:
                try:
                    profile_id = self._get_current_profile_id()
                    if profile_id:
                        service_type = reminder.get('service_type', reminder.get('type', ''))
                        self.reminder_system.dismiss_reminder(profile_id, service_type, snooze_days=7)
                except Exception as e:
                    logger.error(f"Error snoozing reminder: {e}")
            
            reminder['status'] = 'snoozed'
            self._update_reminders_table()
            QMessageBox.information(self, "Reminder Snoozed", f"Reminder snoozed for 7 days!")

    def _dismiss_reminder(self, row: int):
        """Dismiss a reminder"""
        if row < len(self.reminders):
            reminder = self.reminders[row]
            
            # Try to dismiss in backend
            if self.maintenance_predictor:
                try:
                    profile_id = self._get_current_profile_id()
                    if profile_id:
                        service_type = reminder.get('service_type', reminder.get('type', ''))
                        self.reminder_system.dismiss_reminder(profile_id, service_type, snooze_days=365)
                except Exception as e:
                    logger.error(f"Error dismissing reminder: {e}")
            
            reminder['status'] = 'dismissed'
            self._update_reminders_table()
            QMessageBox.information(self, "Reminder Dismissed", f"Reminder '{reminder.get('type', '')}' dismissed!")
