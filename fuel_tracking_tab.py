"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Fuel Tracking Tab
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDateEdit, QMessageBox, QFrame, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from fuel_tracking import FuelTrackingSystem, get_fuel_system
    FUEL_SYSTEM_AVAILABLE = True
except ImportError:
    FUEL_SYSTEM_AVAILABLE = False
    FuelTrackingSystem = None
    get_fuel_system = None

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
            date_obj = datetime.fromisoformat(self.entry.get('date', ''))
            self.date_edit.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
            self.gallons_spin.setValue(self.entry.get('gallons', 0))
            self.price_spin.setValue(self.entry.get('price_per_gallon', 0))
            self.odometer_spin.setValue(self.entry.get('odometer', 0))
            self.station_edit.setText(self.entry.get('station', ''))

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

    def __init__(self, fuel_system=None, parent=None):
        super().__init__(parent)

        # Initialize fuel tracker backend
        if fuel_system:
            self.fuel_system = fuel_system
        elif FUEL_SYSTEM_AVAILABLE and get_fuel_system:
            try:
                self.fuel_system = get_fuel_system()
                logger.info("Fuel tracking system initialized")
            except Exception as e:
                logger.warning(f"Could not initialize FuelTrackingSystem: {e}")
                self.fuel_system = None
        else:
            self.fuel_system = None
            logger.warning("Fuel tracking system not available")

        self.fuel_entries = []
        self.profile_id = 1  # Default profile ID

        self._setup_ui()
        self._load_fuel_data()

    def _setup_ui(self):
        """Setup UI"""
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
        """Load real fuel data from backend"""
        try:
            if self.fuel_system:
                # Get current profile ID
                profile_id = self._get_current_profile_id()
                
                # Load from backend
                self.fuel_entries = self.fuel_system.get_fuel_entries(
                    profile_id=profile_id,
                    days=90
                )
                logger.info(f"Loaded {len(self.fuel_entries)} fuel entries")
            else:
                logger.warning("No fuel system available, using empty data")
                self.fuel_entries = []

        except Exception as e:
            logger.error(f"Error loading fuel data: {e}")
            self.fuel_entries = []

        self._update_table()
        self._update_statistics()

    def _get_current_profile_id(self):
        """Get the currently active profile ID"""
        # Try to get from parent window
        parent = self.parent()
        while parent:
            if hasattr(parent, 'active_profile'):
                profile = parent.active_profile
                if profile:
                    profile_id = profile.get('id') or profile.get('profile_id')
                    if profile_id:
                        return profile_id
            parent = parent.parent() if hasattr(parent, 'parent') else None
        return self.profile_id  # Default to 1

    def _refresh_data(self):
        """Refresh fuel data from backend"""
        self._load_fuel_data()

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

            # Add action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(self._get_button_style('secondary'))
            edit_btn.clicked.connect(lambda: self._edit_entry(row))

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #F44336; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            delete_btn.clicked.connect(lambda: self._delete_entry(row))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            self.fuel_table.setCellWidget(row, 6, actions_widget)

        self.fuel_table.resizeColumnsToContents()

    def _update_statistics(self):
        """Update statistics from backend"""
        try:
            if not self.fuel_system:
                return

            profile_id = self._get_current_profile_id()
            stats = self.fuel_system.get_fuel_statistics(profile_id)

            # Update UI labels
            if hasattr(self, 'avg_mpg_label'):
                self.avg_mpg_label.setText(f"{stats.get('average_mpg', 0):.1f}")
            if hasattr(self, 'total_cost_label'):
                self.total_cost_label.setText(f"${stats.get('total_cost', 0):,.2f}")
            if hasattr(self, 'last_fillup_label'):
                if self.fuel_entries:
                    self.last_fillup_label.setText(self.fuel_entries[0].get('date', '-'))
                else:
                    self.last_fillup_label.setText('-')
            if hasattr(self, 'cost_per_mile_label'):
                self.cost_per_mile_label.setText(f"${stats.get('cost_per_mile', 0):.3f}")

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    def _get_profile_name(self):
        """Get the current profile name"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'active_profile'):
                profile = parent.active_profile
                if profile:
                    return profile.get('name', 'Default Vehicle')
            parent = parent.parent() if hasattr(parent, 'parent') else None
        return "Default Vehicle"

    def _add_fuel_entry(self):
        """Add new fuel entry to backend"""
        dialog = FuelEntryDialog(self)

        if dialog.exec() == QDialog.Accepted:
            entry_data = dialog.get_entry_data()

            if not self.fuel_system:
                QMessageBox.warning(self, "Error", "Fuel tracking system not available")
                return

            profile_id = self._get_current_profile_id()
            profile_name = self._get_profile_name()

            # Save to backend
            result = self.fuel_system.add_fuel_entry(
                entry_data=entry_data,
                profile_id=profile_id,
                profile_name=profile_name
            )

            if result.get('success'):
                QMessageBox.information(self, "Success", "Fuel entry added successfully")
                self._load_fuel_data()  # Reload from backend
            else:
                QMessageBox.warning(self, "Error", f"Failed to add fuel entry: {result.get('error', 'Unknown error')}")

    def _edit_entry(self, row: int):
        """Edit existing fuel entry"""
        if row < len(self.fuel_entries):
            entry = self.fuel_entries[row]
            dialog = FuelEntryDialog(self, entry)
            if dialog.exec() == QDialog.Accepted:
                entry_data = dialog.get_entry_data()
                self.fuel_entries[row] = entry_data
                self._update_table()
                self._update_statistics()
                QMessageBox.information(self, "Entry Updated", "Fuel entry updated successfully!")

    def _delete_entry(self, row: int):
        """Delete fuel entry"""
        if row < len(self.fuel_entries):
            entry = self.fuel_entries[row]
            reply = QMessageBox.question(
                self, "Delete Entry",
                f"Are you sure you want to delete the fuel entry from {entry.get('date', '')}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.fuel_entries[row]
                self._update_table()
                self._update_statistics()
                QMessageBox.information(self, "Entry Deleted", "Fuel entry deleted successfully!")
