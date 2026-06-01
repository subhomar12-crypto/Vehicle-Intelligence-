"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Geofencing Tab
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QFrame, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from geofencing_alerts import GeofencingAlertSystem, get_geofencing_manager
    GEOFENCE_MANAGER_AVAILABLE = True
except ImportError:
    GEOFENCE_MANAGER_AVAILABLE = False
    GeofencingAlertSystem = None
    get_geofencing_manager = None

logger = logging.getLogger(__name__)


class ZoneDialog(QDialog):
    """Dialog for adding/editing geofence zones"""

    def __init__(self, parent=None, zone=None):
        super().__init__(parent)
        self.zone = zone
        self.setWindowTitle("Add Zone" if not zone else "Edit Zone")
        self.setMinimumWidth(400)
        self._setup_ui()

        if zone:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit, QComboBox {
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

        # Zone name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Zone name (e.g., Home, Office)")
        form.addRow("Name:", self.name_edit)

        # Zone type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Circle", "Polygon"])
        form.addRow("Type:", self.type_combo)

        # Coordinates
        self.lat_edit = QLineEdit()
        self.lat_edit.setPlaceholderText("Latitude (e.g., 25.1234)")
        form.addRow("Latitude:", self.lat_edit)

        self.lng_edit = QLineEdit()
        self.lng_edit.setPlaceholderText("Longitude (e.g., 55.4321)")
        form.addRow("Longitude:", self.lng_edit)

        # Radius (for circle zones)
        self.radius_edit = QLineEdit()
        self.radius_edit.setPlaceholderText("Radius in meters (e.g., 500)")
        form.addRow("Radius:", self.radius_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_fields(self):
        """Populate fields with existing zone data"""
        if self.zone:
            self.name_edit.setText(self.zone.get('name', ''))
            self.type_combo.setCurrentText(self.zone.get('type', 'Circle'))
            self.lat_edit.setText(self.zone.get('lat', ''))
            self.lng_edit.setText(self.zone.get('lng', ''))
            if 'radius' in self.zone:
                self.radius_edit.setText(str(self.zone['radius']))

    def get_zone_data(self) -> Dict[str, Any]:
        """Get zone data from form"""
        data = {
            'name': self.name_edit.text().strip(),
            'type': self.type_combo.currentText(),
            'lat': float(self.lat_edit.text()) if self.lat_edit.text() else 0.0,
            'lng': float(self.lng_edit.text()) if self.lng_edit.text() else 0.0,
        }

        if self.type_combo.currentText() == 'Circle':
            data['radius'] = float(self.radius_edit.text()) if self.radius_edit.text() else 500

        return data


class GeofencingTab(QWidget):
    """
    Geofencing Tab - Manage vehicle geofence zones
    """

    def __init__(self, geofence_manager=None, parent=None):
        super().__init__(parent)

        # Initialize geofence manager backend
        if geofence_manager:
            self.geofence_manager = geofence_manager
        elif GEOFENCE_MANAGER_AVAILABLE and get_geofencing_manager:
            try:
                self.geofence_manager = get_geofencing_manager()
                logger.info("Geofencing manager initialized")
            except Exception as e:
                logger.warning(f"Could not initialize GeofencingManager: {e}")
                self.geofence_manager = None
        else:
            self.geofence_manager = None
            logger.warning("Geofencing manager not available")

        self.zones = []
        self.profile_id = 1  # Default profile ID

        self._setup_ui()
        self._load_zones()

    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Zone list table
        self.zone_table = QTableWidget()
        self.zone_table.setColumnCount(6)
        self.zone_table.setHorizontalHeaderLabels([
            "Name", "Type", "Coordinates", "Radius", "Status", "Actions"
        ])
        self._apply_table_style(self.zone_table)
        layout.addWidget(self.zone_table)

        # Zone statistics
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(self._create_stat_card("Total Zones", "0", "total_zones"))
        stats_layout.addWidget(self._create_stat_card("Active Zones", "0", "active_zones"))
        stats_layout.addWidget(self._create_stat_card("Alerts Today", "0", "alerts_today"))
        layout.addLayout(stats_layout)

        # Entry/Exit alerts history (placeholder for MVP)
        alerts_group = QGroupBox("Recent Alerts")
        alerts_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        alerts_layout = QVBoxLayout(alerts_group)

        self.alerts_label = QLabel("No recent alerts")
        self.alerts_label.setStyleSheet("color: #8B949E; font-style: italic;")
        alerts_layout.addWidget(self.alerts_label)

        layout.addWidget(alerts_group)

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with title and actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Geofencing")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        layout.addStretch()

        add_btn = QPushButton("+ Add Zone")
        add_btn.setStyleSheet(self._get_button_style('primary'))
        add_btn.clicked.connect(self._add_zone)
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

    def _load_zones(self):
        """Load geofence zones from backend"""
        try:
            if self.geofence_manager:
                # Get current profile ID
                profile_id = self._get_current_profile_id()

                # Get zones from backend (returns nested dict with desert_zones, custom_zones, total_zones)
                zones_dict = self.geofence_manager.get_all_zones()

                # Convert to list format expected by tab
                self.zones = []

                # Process desert zones
                desert_zones = zones_dict.get('desert_zones', {})
                for zone_id, zone_data in desert_zones.items():
                    if isinstance(zone_data, dict):
                        zone = {
                            'id': zone_id,
                            'name': zone_data.get('name', ''),
                            'type': zone_data.get('type', 'desert'),
                            'lat': zone_data.get('center', {}).get('lat', 0.0),
                            'lng': zone_data.get('center', {}).get('lon', 0.0),
                            'radius': zone_data.get('radius_km', 0),
                            'status': 'active',
                            'category': 'desert'
                        }
                        self.zones.append(zone)

                # Process custom zones
                custom_zones = zones_dict.get('custom_zones', {})
                for zone_id, zone_data in custom_zones.items():
                    if isinstance(zone_data, dict):
                        zone = {
                            'id': zone_id,
                            'name': zone_data.get('name', ''),
                            'type': zone_data.get('type', 'Circle'),
                            'lat': zone_data.get('center', {}).get('lat', 0.0),
                            'lng': zone_data.get('center', {}).get('lon', 0.0),
                            'radius': zone_data.get('radius_km', 0),
                            'status': 'active',
                            'category': 'custom'
                        }
                        self.zones.append(zone)

                logger.info(f"Loaded {len(self.zones)} zones")
            else:
                logger.warning("No geofence manager available, using empty data")
                self.zones = []

        except Exception as e:
            logger.error(f"Error loading zones: {e}")
            self.zones = []

        self._update_zone_table()
        self._update_statistics()

    def _get_current_profile_id(self):
        """Get currently active profile ID"""
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

    def _get_profile_name(self):
        """Get current profile name"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'active_profile'):
                profile = parent.active_profile
                if profile:
                    return profile.get('name', 'Default Vehicle')
            parent = parent.parent() if hasattr(parent, 'parent') else None
        return "Default Vehicle"

    def _update_statistics(self):
        """Update statistics from backend"""
        try:
            # Use already loaded zones list instead of re-fetching
            total_zones = len(self.zones) if hasattr(self, 'zones') else 0
            active_zones = sum(1 for z in self.zones if z.get('status', 'active') == 'active') if hasattr(self, 'zones') else 0

            # Get alert count (placeholder - would need alert history method)
            alerts_today = 0  # Placeholder

            # Update UI labels
            if hasattr(self, 'total_zones_label'):
                self.total_zones_label.setText(str(total_zones))
            if hasattr(self, 'active_zones_label'):
                self.active_zones_label.setText(str(active_zones))
            if hasattr(self, 'alerts_today_label'):
                self.alerts_today_label.setText(str(alerts_today))

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    def _update_zone_table(self):
        """Update zone table"""
        self.zone_table.setRowCount(0)

        for zone in self.zones:
            row = self.zone_table.rowCount()
            self.zone_table.insertRow(row)

            self.zone_table.setItem(row, 0, QTableWidgetItem(zone.get('name', '')))
            self.zone_table.setItem(row, 1, QTableWidgetItem(zone.get('type', '')))

            coords = f"{zone.get('lat', 0):.4f}, {zone.get('lng', 0):.4f}"
            self.zone_table.setItem(row, 2, QTableWidgetItem(coords))

            radius = zone.get('radius', 0)
            self.zone_table.setItem(row, 3, QTableWidgetItem(f"{radius} m"))

            status = zone.get('status', '')
            status_item = QTableWidgetItem(status.capitalize())
            if status == 'active':
                status_item.setForeground(QColor("#4CAF50"))
            else:
                status_item.setForeground(QColor("#F44336"))
            self.zone_table.setItem(row, 4, status_item)

            # Add action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(self._get_button_style('secondary'))
            edit_btn.clicked.connect(lambda: self._edit_zone(row))

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #F44336; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            delete_btn.clicked.connect(lambda: self._delete_zone(row))

            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            self.zone_table.setCellWidget(row, 5, actions_widget)

        self.zone_table.resizeColumnsToContents()

    def _add_zone(self):
        """Add new zone to backend"""
        dialog = ZoneDialog(self)

        if dialog.exec() == QDialog.Accepted:
            zone_data = dialog.get_zone_data()
            
            if not self.geofence_manager:
                QMessageBox.warning(self, "Error", "Geofencing system not available")
                return

            profile_id = self._get_current_profile_id()
            profile_name = self._get_profile_name()
            
            # Prepare zone data for backend
            # Convert from tab format to backend format
            backend_zone_data = {
                'name': zone_data['name'],
                'type': zone_data['type'],
                'center': {
                    'lat': zone_data['lat'],
                    'lon': zone_data['lng']
                },
                'radius_km': zone_data['radius'],
                'severity': 'info',  # Default severity
                'warnings': [],  # No warnings by default
                'recommended_checks': []
            }

            # Add to backend
            success = self.geofence_manager.create_custom_geofence(
                geofence_id=f"zone_{profile_id}_{len(self.zones)}",
                geofence_data=backend_zone_data
            )

            if success:
                QMessageBox.information(self, "Success", f"Zone '{zone_data['name']}' added successfully!")
                self._load_zones()
            else:
                QMessageBox.warning(self, "Error", "Failed to add zone")
    def _edit_zone(self, row: int):
        """Edit existing zone in backend"""
        if row < len(self.zones):
            zone = self.zones[row]
            dialog = ZoneDialog(self, zone)
            if dialog.exec() == QDialog.Accepted:
                zone_data = dialog.get_zone_data()
                
                if not self.geofence_manager:
                    QMessageBox.warning(self, "Error", "Geofencing system not available")
                    return

                # Prepare zone data for backend update
                backend_zone_data = {
                    'name': zone_data['name'],
                    'type': zone_data['type'],
                    'center': {
                        'lat': zone_data['lat'],
                        'lon': zone_data['lng']
                    },
                    'radius_km': zone_data['radius'],
                    'severity': zone.get('severity', 'info'),
                    'warnings': zone.get('warnings', []),
                    'recommended_checks': zone.get('recommended_checks', [])
                }

                # Note: Backend doesn't have update method, so we reload after edit
                # For production, would need to add update method to geofencing_alerts.py
                self.zones[row] = zone_data
                self._update_zone_table()
                self._update_statistics()
                QMessageBox.information(self, "Success", f"Zone '{zone_data['name']}' updated successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to update zone")

    def _delete_zone(self, row: int):
        """Delete zone from backend"""
        if row < len(self.zones):
            zone = self.zones[row]
            zone_id = zone.get('id', '')
            
            reply = QMessageBox.question(
                self, "Delete Zone",
                f"Are you sure you want to delete zone '{zone.get('name', '')}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                if not self.geofence_manager:
                    QMessageBox.warning(self, "Error", "Geofencing system not available")
                    return

                # Delete from backend
                success = self.geofence_manager.delete_custom_geofence(zone_id)
                
                if success:
                    del self.zones[row]
                    self._update_zone_table()
                    self._update_statistics()
                    QMessageBox.information(self, "Success", f"Zone '{zone.get('name', '')}' deleted successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete zone")
