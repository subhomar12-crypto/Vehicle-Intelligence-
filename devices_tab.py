"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Devices Tab

Devices Tab
Manages connected devices (OBD adapters, mobile devices, ESP32 sensors)
Shows device status, heartbeat monitoring, and device management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QMessageBox, QTabWidget, QScrollArea,
    QFrame, QProgressBar, QLineEdit, QSpinBox, QFileDialog,
    QDialog, QTextEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QColor, QIcon

import json
import csv
import os
import time

# Import remote command system
try:
    from remote_command_system import get_remote_command_system
except ImportError:
    get_remote_command_system = None

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

logger = logging.getLogger(__name__)


class DeviceStatusWidget(QWidget):
    """Widget showing device status with visual indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Status indicator circle
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(16, 16)
        self.status_circle.setStyleSheet("""
            QLabel {
                background-color: #9E9E9E;
                border-radius: 8px;
                border: 2px solid #6E7681;
            }
        """)
        layout.addWidget(self.status_circle)
        
        # Status text
        self.status_label = QLabel("Unknown")
        self.status_label.setStyleSheet("color: #8B949E; font-weight: 600;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def set_status(self, status: str):
        """Set device status: online, offline, connecting, unknown"""
        colors = {
            'online': '#4CAF50',
            'connected': '#4CAF50',
            'active': '#4CAF50',
            'offline': '#F44336',
            'disconnected': '#F44336',
            'inactive': '#F44336',
            'connecting': '#FFC107',
            'unknown': '#9E9E9E'
        }
        
        bg_color = colors.get(status.lower(), '#9E9E9E')
        
        self.status_circle.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 2px solid #6E7681;
            }}
        """)
        
        # Capitalize first letter
        status_text = status.capitalize() if status else "Unknown"
        self.status_label.setText(status_text)
        
        # Update text color
        if status.lower() in ['online', 'connected', 'active']:
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: 600;")
        elif status.lower() in ['offline', 'disconnected', 'inactive']:
            self.status_label.setStyleSheet("color: #F44336; font-weight: 600;")
        elif status.lower() == 'connecting':
            self.status_label.setStyleSheet("color: #FFC107; font-weight: 600;")
        else:
            self.status_label.setStyleSheet("color: #8B949E; font-weight: 600;")


class CommandStatusMonitor(QThread):
    """Thread to monitor command status and update UI"""
    
    status_update = Signal(str, dict)  # command_id, status_info
    
    def __init__(self, command_system, parent=None):
        super().__init__(parent)
        self.command_system = command_system
        self.pending_commands = {}
        self.running = True
    
    def add_command(self, command_id: str):
        """Add command to monitor"""
        self.pending_commands[command_id] = {
            'command_id': command_id,
            'started_at': datetime.now()
        }
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.wait()
    
    def run(self):
        """Monitor command status"""
        while self.running:
            try:
                time.sleep(0.5)  # Check every 0.5 seconds
                
                # Check status of pending commands
                completed_commands = []
                for command_id, info in self.pending_commands.items():
                    status_info = self.command_system.get_command_status(command_id)
                    
                    # Emit update
                    self.status_update.emit(command_id, status_info)
                    
                    # Remove completed/failed commands
                    if status_info.get('status') in ['completed', 'failed', 'cancelled']:
                        completed_commands.append(command_id)
                
                # Remove completed commands from monitoring
                for command_id in completed_commands:
                    del self.pending_commands[command_id]
                    
            except Exception as e:
                logger.error(f"Error in command status monitor: {e}")
                time.sleep(1)


class DevicesTab(QWidget):
    """
    Devices Management Tab
    
    Features:
    - View all connected devices (OBD adapters, mobile devices, ESP32 sensors)
    - Device status monitoring (online/offline, heartbeat)
    - Device management (add, remove, configure)
    - Device health metrics (signal strength, battery level, uptime)
    - Device grouping and filtering
    """
    
    # Signals for device events
    device_connected = Signal(dict)  # device_info
    device_disconnected = Signal(str)  # device_id
    device_configured = Signal(dict)  # device_config
    
    def __init__(self, heartbeat_manager=None, parent=None):
        super().__init__(parent)
        self.heartbeat_manager = heartbeat_manager
        self.devices = []
        
        # Initialize remote command system
        self.remote_command_system = None
        if get_remote_command_system:
            try:
                self.remote_command_system = get_remote_command_system()
                self.command_status_monitor = CommandStatusMonitor(self.remote_command_system)
                self.command_status_monitor.status_update.connect(self._on_command_status_update)
                self.command_status_monitor.start()
            except Exception as e:
                logger.error(f"Failed to initialize remote command system: {e}")
        
        self._setup_ui()
        self._start_monitoring()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Devices")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F0F6FC;")
        
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        self.refresh_btn.clicked.connect(self._refresh_devices)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        # Main tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #30363D;
                border-radius: 8px;
                background-color: #161B22;
                padding: 5px;
            }
            QTabBar::tab {
                background-color: #21262D;
                color: #8B949E;
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #30363D;
                border-bottom: none;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #C40000;
                color: #F0F6FC;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #30363D;
                color: #F0F6FC;
            }
        """)
        
        # Tab 1: Connected Devices
        connected_tab = self._create_connected_devices_tab()
        self.tabs.addTab(connected_tab, "📱 Connected")
        
        # Tab 2: Device History
        history_tab = self._create_device_history_tab()
        self.tabs.addTab(history_tab, "📜 History")
        
        # Tab 3: Device Configuration
        config_tab = self._create_device_config_tab()
        self.tabs.addTab(config_tab, "⚙️ Configuration")
        
        # Tab 4: Remote Commands
        remote_tab = self._create_remote_commands_tab()
        self.tabs.addTab(remote_tab, "🎮 Remote Commands")
        
        layout.addWidget(self.tabs, 1)
    
    def _create_connected_devices_tab(self) -> QWidget:
        """Create connected devices tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Device filter
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #8B949E; font-weight: 600;")
        
        self.device_filter_combo = QComboBox()
        self.device_filter_combo.addItems([
            "All Devices",
            "OBD Adapters Only",
            "Mobile Devices Only",
            "ESP32 Sensors Only",
            "Online Only",
            "Offline Only"
        ])
        self.device_filter_combo.currentTextChanged.connect(self._filter_devices)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.device_filter_combo)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Device statistics
        stats_layout = QHBoxLayout()
        
        self.total_devices_label = QLabel("0")
        self.total_devices_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #F0F6FC;")
        
        self.online_devices_label = QLabel("0 Online")
        self.online_devices_label.setStyleSheet("color: #4CAF50; font-weight: 600;")
        
        self.offline_devices_label = QLabel("0 Offline")
        self.offline_devices_label.setStyleSheet("color: #F44336; font-weight: 600;")
        
        stats_layout.addWidget(QLabel("Total:"))
        stats_layout.addWidget(self.total_devices_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(self.online_devices_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(self.offline_devices_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Devices table
        devices_group = QGroupBox("Connected Devices")
        devices_layout = QVBoxLayout(devices_group)
        
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(8)
        self.devices_table.setHorizontalHeaderLabels([
            "Status", "Device ID", "Type", "Profile",
            "Last Seen", "Signal", "Battery", "Actions"
        ])
        self.devices_table.horizontalHeader().setStretchLastSection(True)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.devices_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.devices_table.setAlternatingRowColors(True)
        self.devices_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.devices_table)
        
        # Set Status column width to prevent truncation
        self.devices_table.setColumnWidth(0, 80)  # Status column minimum 80px
        
        devices_layout.addWidget(self.devices_table)
        layout.addWidget(devices_group)
        
        # Device details panel
        details_group = QGroupBox("Device Details")
        details_layout = QVBoxLayout(details_group)
        
        # Placeholder text when no device selected
        self.details_placeholder = QLabel("📱 Select a device from the table above to view details")
        self.details_placeholder.setAlignment(Qt.AlignCenter)
        self.details_placeholder.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-style: italic;
                padding: 40px 20px;
                background-color: #161B22;
                border-radius: 6px;
                border: 1px dashed #30363D;
            }
        """)
        details_layout.addWidget(self.details_placeholder)
        
        # Form layout for actual details (initially hidden)
        self.details_form = QWidget()
        details_form_layout = QFormLayout(self.details_form)
        
        self.device_id_label = QLabel("-")
        self.device_type_label = QLabel("-")
        self.device_profile_label = QLabel("-")
        self.device_last_seen_label = QLabel("-")
        self.device_uptime_label = QLabel("-")
        self.device_signal_label = QLabel("-")
        self.device_battery_label = QLabel("-")
        
        details_form_layout.addRow("Device ID:", self.device_id_label)
        details_form_layout.addRow("Type:", self.device_type_label)
        details_form_layout.addRow("Profile:", self.device_profile_label)
        details_form_layout.addRow("Last Seen:", self.device_last_seen_label)
        details_form_layout.addRow("Uptime:", self.device_uptime_label)
        details_form_layout.addRow("Signal:", self.device_signal_label)
        details_form_layout.addRow("Battery:", self.device_battery_label)
        
        self.details_form.setVisible(False)
        details_layout.addWidget(self.details_form)
        
        layout.addWidget(details_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ping_btn = QPushButton("📡 Ping Device")
        self.ping_btn.setStyleSheet(self._get_button_style('secondary'))
        self.ping_btn.clicked.connect(self._ping_device)
        self.ping_btn.setEnabled(False)
        
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.setStyleSheet(self._get_button_style('danger'))
        self.disconnect_btn.clicked.connect(self._disconnect_device)
        self.disconnect_btn.setEnabled(False)
        
        self.configure_btn = QPushButton("⚙️ Configure")
        self.configure_btn.setStyleSheet(self._get_button_style('secondary'))
        self.configure_btn.clicked.connect(self._configure_device)
        self.configure_btn.setEnabled(False)
        
        button_layout.addWidget(self.ping_btn)
        button_layout.addWidget(self.disconnect_btn)
        button_layout.addWidget(self.configure_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def _create_device_history_tab(self) -> QWidget:
        """Create device history tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # History table
        history_group = QGroupBox("Device Connection History")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Timestamp", "Device ID", "Event", "Duration",
            "Signal Quality", "Notes"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.history_table)
        
        history_layout.addWidget(self.history_table)
        layout.addWidget(history_group)
        
        # History filter
        filter_group = QGroupBox("Filter History")
        filter_layout = QFormLayout(filter_group)
        
        self.history_device_combo = QComboBox()
        self.history_device_combo.addItem("All Devices")
        
        self.history_event_combo = QComboBox()
        self.history_event_combo.addItems([
            "All Events",
            "Connection Only",
            "Disconnection Only",
            "Heartbeat Lost",
            "Signal Degraded"
        ])
        
        self.history_date_combo = QComboBox()
        self.history_date_combo.addItems([
            "All Time",
            "Last Hour",
            "Last 24 Hours",
            "Last 7 Days",
            "Last 30 Days"
        ])
        
        filter_layout.addRow("Device:", self.history_device_combo)
        filter_layout.addRow("Event:", self.history_event_combo)
        filter_layout.addRow("Date Range:", self.history_date_combo)
        
        layout.addWidget(filter_group)
        
        # Export button
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        
        export_btn = QPushButton("📤 Export History")
        export_btn.setStyleSheet(self._get_button_style('secondary'))
        export_btn.clicked.connect(self._export_history)
        export_layout.addWidget(export_btn)
        
        layout.addLayout(export_layout)
        
        return widget
    
    def _create_device_config_tab(self) -> QWidget:
        """Create device configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Configuration form
        config_group = QGroupBox("Device Configuration")
        config_layout = QFormLayout(config_group)
        
        self.config_device_combo = QComboBox()
        self.config_device_combo.addItem("Select Device...")
        
        self.device_name_edit = QLineEdit()
        self.device_name_edit.setPlaceholderText("Device name")
        
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItems([
            "OBD Adapter (USB/Bluetooth)",
            "Mobile Device (Android App)",
            "ESP32 Sensor",
            "Custom Device"
        ])
        
        self.heartbeat_interval_spin = QSpinBox()
        self.heartbeat_interval_spin.setRange(5, 300)
        self.heartbeat_interval_spin.setValue(30)
        self.heartbeat_interval_spin.setSuffix(" seconds")
        
        self.auto_reconnect_check = QCheckBox()
        self.auto_reconnect_check.setChecked(True)
        
        self.notification_check = QCheckBox()
        self.notification_check.setChecked(True)
        
        config_layout.addRow("Device:", self.config_device_combo)
        config_layout.addRow("Name:", self.device_name_edit)
        config_layout.addRow("Type:", self.device_type_combo)
        config_layout.addRow("Heartbeat Interval:", self.heartbeat_interval_spin)
        config_layout.addRow("Auto-Reconnect:", self.auto_reconnect_check)
        config_layout.addRow("Notifications:", self.notification_check)
        
        layout.addWidget(config_group)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Save Configuration")
        save_btn.setStyleSheet(self._get_button_style('success'))
        save_btn.clicked.connect(self._save_device_config)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def _create_remote_commands_tab(self) -> QWidget:
        """Create remote commands tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Instructions
        instructions = QLabel(
            "Send remote commands to connected vehicles. "
            "Commands are queued and processed asynchronously."
        )
        instructions.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-style: italic;
                padding: 10px;
                background-color: #161B22;
                border-radius: 6px;
                border: 1px dashed #30363D;
            }
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Devices table for remote commands
        devices_group = QGroupBox("Connected Devices")
        devices_layout = QVBoxLayout(devices_group)
        
        self.remote_devices_table = QTableWidget()
        self.remote_devices_table.setColumnCount(6)
        self.remote_devices_table.setHorizontalHeaderLabels([
            "Status", "Device ID", "Type", "Profile", "Remote Commands", "Command Status"
        ])
        self.remote_devices_table.horizontalHeader().setStretchLastSection(True)
        self.remote_devices_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.remote_devices_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.remote_devices_table.setAlternatingRowColors(True)
        self.remote_devices_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.remote_devices_table)
        
        # Set Status column width
        self.remote_devices_table.setColumnWidth(0, 80)
        
        devices_layout.addWidget(self.remote_devices_table)
        layout.addWidget(devices_group)
        
        # Command history panel
        history_group = QGroupBox("Recent Command History")
        history_layout = QVBoxLayout(history_group)
        
        self.command_history_table = QTableWidget()
        self.command_history_table.setColumnCount(5)
        self.command_history_table.setHorizontalHeaderLabels([
            "Time", "Device", "Command", "Status", "Result"
        ])
        self.command_history_table.horizontalHeader().setStretchLastSection(True)
        self.command_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.command_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.command_history_table.setAlternatingRowColors(True)
        self.command_history_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.command_history_table)
        
        history_layout.addWidget(self.command_history_table)
        layout.addWidget(history_group)
        
        # Clear history button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        clear_history_btn = QPushButton("🗑️ Clear History")
        clear_history_btn.setStyleSheet(self._get_button_style('secondary'))
        clear_history_btn.clicked.connect(self._clear_command_history)
        button_layout.addWidget(clear_history_btn)
        
        layout.addLayout(button_layout)
        
        return widget
    
    def _start_monitoring(self):
        """Start device monitoring timer"""
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._refresh_devices)
        self.monitor_timer.start(5000)  # Update every 5 seconds
        
        # Initial refresh
        self._refresh_devices()
        
        # Also refresh remote devices table
        self._refresh_remote_devices()
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #A00000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #8B949E;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #A00000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFD54F;
                }
                QPushButton:pressed {
                    background-color: #FFA000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _apply_table_styling(self, table_widget):
        """Apply consistent table styling to a QTableWidget"""
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 8px;
                gridline-color: #30363D;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #30363D;
            }
            QTableWidget::item:selected {
                background-color: #C40000;
                color: #FFFFFF;
            }
            QTableWidget::item:hover {
                background-color: #30363D;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #F0F6FC;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #C40000;
                font-weight: 600;
            }
            QScrollBar:vertical {
                background-color: #161B22;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #484F58;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #6E7681;
            }
        """)
    
    def _refresh_devices(self):
        """Refresh device list from heartbeat manager"""
        try:
            if self.heartbeat_manager:
                # Get connected devices from heartbeat manager
                self.devices = self._get_connected_devices()
                
                # Update devices table
                self._update_devices_table()
                
                # Update statistics
                self._update_statistics()
                
                logger.debug(f"Refreshed {len(self.devices)} devices")
            else:
                # No heartbeat manager available - show empty data
                self.devices = []
                self._update_devices_table()
                self._update_statistics()
            
            # Also refresh remote devices table
            self._refresh_remote_devices()
                
        except Exception as e:
            logger.error(f"Error refreshing devices: {e}")
            self.devices = []
    
    def _get_connected_devices(self) -> List[Dict[str, Any]]:
        """
        Get connected devices from heartbeat manager with full device information
        
        Returns:
            List of device dictionaries with device info
        """
        try:
            devices = []
            
            # Get all device statuses from heartbeat manager
            all_devices = self.heartbeat_manager.get_all_devices()
            
            if not all_devices:
                logger.warning("No devices returned from heartbeat manager")
                return []
            
            for device_id, device_info in all_devices.items():
                # Extract device information
                device_type = device_info.get('type', 'unknown')
                profile_name = device_info.get('profile_name', '-')
                is_alive = device_info.get('is_alive', False)
                last_heartbeat = device_info.get('last_heartbeat', None)
                signal_strength = device_info.get('signal_strength', 0)
                battery_level = device_info.get('battery_level', 100)
                
                # Determine status
                status = 'online' if is_alive else 'offline'
                
                # Calculate uptime if available
                uptime = '-'
                if last_heartbeat and isinstance(last_heartbeat, str):
                    try:
                        last_seen = datetime.fromisoformat(last_heartbeat)
                        uptime = datetime.now() - last_seen
                        if uptime.total_seconds() < 3600:
                            uptime = f"{uptime.total_seconds() // 60}m"
                        elif uptime.total_seconds() < 86400:
                            uptime = f"{uptime.total_seconds() // 3600}h"
                        else:
                            uptime = f"{uptime.total_seconds() // 86400}d"
                    except:
                        pass
                
                # Create device dictionary
                device = {
                    'device_id': device_id,
                    'type': device_type,
                    'profile': profile_name,
                    'status': status,
                    'last_seen': last_heartbeat,
                    'signal_strength': signal_strength,
                    'battery_level': battery_level,
                    'uptime': uptime
                }
                
                devices.append(device)
            
            logger.debug(f"Retrieved {len(devices)} connected devices from heartbeat manager")
            return devices
            
        except Exception as e:
            logger.error(f"Error getting connected devices: {e}")
            return []
    
    def _update_devices_table(self):
        """Update devices table with current data"""
        self.devices_table.setRowCount(0)
        
        for device in self.devices:
            row = self.devices_table.rowCount()
            self.devices_table.insertRow(row)
            
            # Status
            status = device.get('status', 'unknown')
            status_widget = DeviceStatusWidget()
            status_widget.set_status(status)
            self.devices_table.setCellWidget(row, 0, status_widget)
            
            # Device ID
            self.devices_table.setItem(row, 1, QTableWidgetItem(device.get('device_id', '')))
            
            # Type
            type_map = {
                'obd_adapter': 'OBD Adapter',
                'mobile_device': 'Mobile',
                'esp32_sensor': 'ESP32',
                'custom': 'Custom'
            }
            device_type = type_map.get(device.get('type', ''), 'Unknown')
            self.devices_table.setItem(row, 2, QTableWidgetItem(device_type))
            
            # Profile
            self.devices_table.setItem(row, 3, QTableWidgetItem(device.get('profile', '-')))
            
            # Last Seen
            last_seen = device.get('last_seen')
            if last_seen:
                if isinstance(last_seen, str):
                    try:
                        last_seen = datetime.fromisoformat(last_seen)
                    except:
                        pass
                
                if isinstance(last_seen, datetime):
                    time_diff = datetime.now() - last_seen
                    if time_diff.total_seconds() < 60:
                        last_seen_text = f"{int(time_diff.total_seconds())}s ago"
                    elif time_diff.total_seconds() < 3600:
                        last_seen_text = f"{int(time_diff.total_seconds() / 60)}m ago"
                    else:
                        last_seen_text = f"{int(time_diff.total_seconds() / 3600)}h ago"
                else:
                    last_seen_text = str(last_seen)
            else:
                last_seen_text = '-'
            
            self.devices_table.setItem(row, 4, QTableWidgetItem(last_seen_text))
            
            # Signal
            signal = device.get('signal_strength', 0)
            if signal >= 80:
                signal_color = '#4CAF50'
                signal_text = 'Excellent'
            elif signal >= 60:
                signal_color = '#FFC107'
                signal_text = 'Good'
            elif signal > 0:
                signal_color = '#FF9800'
                signal_text = 'Weak'
            else:
                signal_color = '#9E9E9E'
                signal_text = '-'
            
            signal_item = QTableWidgetItem(f"{signal}% ({signal_text})")
            signal_item.setForeground(QColor(signal_color))
            self.devices_table.setItem(row, 5, signal_item)
            
            # Battery
            battery = device.get('battery_level', 0)
            if battery >= 80:
                battery_color = '#4CAF50'
            elif battery >= 50:
                battery_color = '#FFC107'
            elif battery > 0:
                battery_color = '#FF9800'
            else:
                battery_color = '#9E9E9E'
            
            battery_item = QTableWidgetItem(f"{battery}%")
            battery_item.setForeground(QColor(battery_color))
            self.devices_table.setItem(row, 6, battery_item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            ping_btn = QPushButton("📡")
            ping_btn.setStyleSheet(self._get_button_style('secondary'))
            ping_btn.setFixedSize(28, 28)
            ping_btn.setToolTip("Ping device")
            ping_btn.clicked.connect(lambda: self._ping_device(device))
            
            config_btn = QPushButton("⚙️")
            config_btn.setStyleSheet(self._get_button_style('secondary'))
            config_btn.setFixedSize(28, 28)
            config_btn.setToolTip("Configure device")
            config_btn.clicked.connect(lambda: self._configure_device(device))
            
            disconnect_btn = QPushButton("🔌")
            disconnect_btn.setStyleSheet(self._get_button_style('danger'))
            disconnect_btn.setFixedSize(28, 28)
            disconnect_btn.setToolTip("Disconnect device")
            disconnect_btn.clicked.connect(lambda: self._disconnect_device(device))
            
            actions_layout.addWidget(ping_btn)
            actions_layout.addWidget(config_btn)
            actions_layout.addWidget(disconnect_btn)
            
            self.devices_table.setCellWidget(row, 7, actions_widget)
        
        self.devices_table.resizeColumnsToContents()
    
    def _update_statistics(self):
        """Update device statistics"""
        total = len(self.devices)
        online = sum(1 for d in self.devices if d.get('status') == 'online')
        offline = total - online
        
        self.total_devices_label.setText(str(total))
        self.online_devices_label.setText(f"{online} Online")
        self.offline_devices_label.setText(f"{offline} Offline")
    
    def _filter_devices(self, filter_text: str):
        """Filter devices based on selected filter"""
        self.devices_table.setRowCount(0)

        filtered_count = 0
        for device in self.devices:
            # Check filter criteria
            device_type = device.get('type', '').lower()
            device_status = device.get('status', '').lower()

            # Apply filter
            show_device = True

            if filter_text == "OBD Adapters Only":
                show_device = device_type == 'obd_adapter'
            elif filter_text == "Mobile Devices Only":
                show_device = device_type == 'mobile_device'
            elif filter_text == "ESP32 Sensors Only":
                show_device = device_type == 'esp32_sensor'
            elif filter_text == "Online Only":
                show_device = device_status in ['online', 'connected', 'active']
            elif filter_text == "Offline Only":
                show_device = device_status in ['offline', 'disconnected', 'inactive']
            # "All Devices" shows everything

            if show_device:
                self._add_device_to_table(device)
                filtered_count += 1

        # Update statistics for filtered view
        total_filtered = filtered_count
        online_filtered = sum(1 for d in self.devices if d.get('status', '').lower() in ['online', 'connected', 'active'] and self._device_matches_filter(d, filter_text))
        offline_filtered = total_filtered - online_filtered

        self.total_devices_label.setText(str(total_filtered))
        self.online_devices_label.setText(f"{online_filtered} Online")
        self.offline_devices_label.setText(f"{offline_filtered} Offline")

        logger.debug(f"Filter '{filter_text}' applied: {filtered_count} devices shown")

    def _device_matches_filter(self, device: dict, filter_text: str) -> bool:
        """Check if device matches current filter"""
        device_type = device.get('type', '').lower()
        device_status = device.get('status', '').lower()

        if filter_text == "All Devices":
            return True
        elif filter_text == "OBD Adapters Only":
            return device_type == 'obd_adapter'
        elif filter_text == "Mobile Devices Only":
            return device_type == 'mobile_device'
        elif filter_text == "ESP32 Sensors Only":
            return device_type == 'esp32_sensor'
        elif filter_text == "Online Only":
            return device_status in ['online', 'connected', 'active']
        elif filter_text == "Offline Only":
            return device_status in ['offline', 'disconnected', 'inactive']
        return True

    def _add_device_to_table(self, device: dict):
        """Add a single device to the table"""
        row = self.devices_table.rowCount()
        self.devices_table.insertRow(row)

        # Status
        status = device.get('status', 'unknown')
        status_widget = DeviceStatusWidget()
        status_widget.set_status(status)
        self.devices_table.setCellWidget(row, 0, status_widget)

        # Device ID
        self.devices_table.setItem(row, 1, QTableWidgetItem(device.get('device_id', '')))

        # Type
        type_map = {
            'obd_adapter': 'OBD Adapter',
            'mobile_device': 'Mobile',
            'esp32_sensor': 'ESP32',
            'custom': 'Custom'
        }
        device_type = type_map.get(device.get('type', ''), 'Unknown')
        self.devices_table.setItem(row, 2, QTableWidgetItem(device_type))

        # Profile
        self.devices_table.setItem(row, 3, QTableWidgetItem(device.get('profile', '-')))

        # Last Seen
        last_seen = device.get('last_seen')
        if last_seen:
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen)
                except:
                    pass

            if isinstance(last_seen, datetime):
                time_diff = datetime.now() - last_seen
                if time_diff.total_seconds() < 60:
                    last_seen_text = f"{int(time_diff.total_seconds())}s ago"
                elif time_diff.total_seconds() < 3600:
                    last_seen_text = f"{int(time_diff.total_seconds() / 60)}m ago"
                else:
                    last_seen_text = f"{int(time_diff.total_seconds() / 3600)}h ago"
            else:
                last_seen_text = str(last_seen)
        else:
            last_seen_text = '-'

        self.devices_table.setItem(row, 4, QTableWidgetItem(last_seen_text))

        # Signal
        signal = device.get('signal_strength', 0)
        if signal >= 80:
            signal_color = '#4CAF50'
            signal_text = 'Excellent'
        elif signal >= 60:
            signal_color = '#FFC107'
            signal_text = 'Good'
        elif signal > 0:
            signal_color = '#FF9800'
            signal_text = 'Weak'
        else:
            signal_color = '#9E9E9E'
            signal_text = '-'

        signal_item = QTableWidgetItem(f"{signal}% ({signal_text})")
        signal_item.setForeground(QColor(signal_color))
        self.devices_table.setItem(row, 5, signal_item)

        # Battery
        battery = device.get('battery_level', 0)
        if battery >= 80:
            battery_color = '#4CAF50'
        elif battery >= 50:
            battery_color = '#FFC107'
        elif battery > 0:
            battery_color = '#FF9800'
        else:
            battery_color = '#9E9E9E'

        battery_item = QTableWidgetItem(f"{battery}%")
        battery_item.setForeground(QColor(battery_color))
        self.devices_table.setItem(row, 6, battery_item)

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        ping_btn = QPushButton("📡")
        ping_btn.setStyleSheet(self._get_button_style('secondary'))
        ping_btn.setFixedSize(28, 28)
        ping_btn.setToolTip("Ping device")
        ping_btn.clicked.connect(lambda checked, d=device: self._ping_device(d))

        config_btn = QPushButton("⚙️")
        config_btn.setStyleSheet(self._get_button_style('secondary'))
        config_btn.setFixedSize(28, 28)
        config_btn.setToolTip("Configure device")
        config_btn.clicked.connect(lambda checked, d=device: self._configure_device(d))

        disconnect_btn = QPushButton("🔌")
        disconnect_btn.setStyleSheet(self._get_button_style('danger'))
        disconnect_btn.setFixedSize(28, 28)
        disconnect_btn.setToolTip("Disconnect device")
        disconnect_btn.clicked.connect(lambda checked, d=device: self._disconnect_device(d))

        actions_layout.addWidget(ping_btn)
        actions_layout.addWidget(config_btn)
        actions_layout.addWidget(disconnect_btn)

        self.devices_table.setCellWidget(row, 7, actions_widget)
    
    def _ping_device(self, device: dict = None):
        """Ping selected device"""
        device_id = device.get('device_id', 'Unknown') if device else 'Unknown'
        QMessageBox.information(
            self,
            "Ping Device",
            f"Pinging device: {device_id}\n\n"
            "This will send a test signal to the device and measure response time."
        )
        logger.info(f"Pinging device: {device_id}")
    
    def _disconnect_device(self, device: dict = None):
        """Disconnect selected device"""
        device_id = device.get('device_id', 'Unknown') if device else 'Unknown'
        
        reply = QMessageBox.question(
            self,
            "Disconnect Device",
            f"Are you sure you want to disconnect device:\n{device_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Device Disconnected", f"Device {device_id} has been disconnected.")
            logger.info(f"Disconnected device: {device_id}")
            
            # Emit signal
            self.device_disconnected.emit(device_id)
    
    def _configure_device(self, device: dict = None):
        """Configure selected device"""
        device_id = device.get('device_id', 'Unknown') if device else 'Unknown'
        
        # Switch to configuration tab
        self.tabs.setCurrentIndex(2)
        
        # Populate config fields
        if device:
            self.config_device_combo.addItem(device_id)
            self.config_device_combo.setCurrentText(device_id)
            self.device_name_edit.setText(device.get('name', ''))
            
            type_map = {
                'obd_adapter': 'OBD Adapter (USB/Bluetooth)',
                'mobile_device': 'Mobile Device (Android App)',
                'esp32_sensor': 'ESP32 Sensor',
                'custom': 'Custom Device'
            }
            self.device_type_combo.setCurrentText(type_map.get(device.get('type', ''), ''))
        
        # Also show details in the details panel
        if device:
            self.details_placeholder.setVisible(False)
            self.details_form.setVisible(True)
            
            self.device_id_label.setText(device.get('device_id', '-'))
            self.device_type_label.setText(device.get('type', '-'))
            self.device_profile_label.setText(device.get('profile', '-'))
            
            last_seen = device.get('last_seen')
            if last_seen:
                if isinstance(last_seen, datetime):
                    self.device_last_seen_label.setText(last_seen.strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    self.device_last_seen_label.setText(str(last_seen))
            else:
                self.device_last_seen_label.setText('-')
            
            self.device_uptime_label.setText(device.get('uptime', '-'))
            
            signal = device.get('signal_strength', 0)
            self.device_signal_label.setText(f"{signal}%")
            
            battery = device.get('battery_level', 0)
            self.device_battery_label.setText(f"{battery}%")
        
        logger.info(f"Configuring device: {device_id}")
    
    def _save_device_config(self):
        """Save device configuration"""
        device_id = self.config_device_combo.currentText()
        
        if device_id == "Select Device...":
            QMessageBox.warning(self, "No Device Selected", "Please select a device to configure.")
            return
        
        config = {
            'device_id': device_id,
            'name': self.device_name_edit.text(),
            'type': self.device_type_combo.currentText(),
            'heartbeat_interval': self.heartbeat_interval_spin.value(),
            'auto_reconnect': self.auto_reconnect_check.isChecked(),
            'notifications': self.notification_check.isChecked()
        }
        
        # Emit signal
        self.device_configured.emit(config)
        
        QMessageBox.information(
            self,
            "Configuration Saved",
            f"Device configuration saved for:\n{device_id}"
        )
        
        logger.info(f"Device configuration saved: {device_id}")
    
    def _export_history(self):
        """Export device history to CSV or JSON"""
        # Get export file path
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Device History",
            f"device_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "CSV Files (*.csv);;JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Gather device history data from table
            history_data = []
            for row in range(self.history_table.rowCount()):
                row_data = {
                    'timestamp': self.history_table.item(row, 0).text() if self.history_table.item(row, 0) else '',
                    'device_id': self.history_table.item(row, 1).text() if self.history_table.item(row, 1) else '',
                    'event': self.history_table.item(row, 2).text() if self.history_table.item(row, 2) else '',
                    'duration': self.history_table.item(row, 3).text() if self.history_table.item(row, 3) else '',
                    'signal_quality': self.history_table.item(row, 4).text() if self.history_table.item(row, 4) else '',
                    'notes': self.history_table.item(row, 5).text() if self.history_table.item(row, 5) else ''
                }
                history_data.append(row_data)

            # Also add current device status
            device_status_data = []
            for device in self.devices:
                last_seen = device.get('last_seen', '')
                if isinstance(last_seen, datetime):
                    last_seen = last_seen.isoformat()

                device_status_data.append({
                    'device_id': device.get('device_id', ''),
                    'type': device.get('type', ''),
                    'status': device.get('status', ''),
                    'profile': device.get('profile', ''),
                    'last_seen': last_seen,
                    'signal_strength': device.get('signal_strength', 0),
                    'battery_level': device.get('battery_level', 0),
                    'uptime': device.get('uptime', '')
                })

            # Export based on file extension
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'export_date': datetime.now().isoformat(),
                        'total_devices': len(device_status_data),
                        'history_entries': len(history_data),
                        'devices': device_status_data,
                        'history': history_data
                    }, f, indent=2)
            else:
                # Default to CSV
                if not file_path.endswith('.csv'):
                    file_path += '.csv'

                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    # Write device status section
                    f.write("# Device Status\n")
                    if device_status_data:
                        writer = csv.DictWriter(f, fieldnames=['device_id', 'type', 'status', 'profile', 'last_seen', 'signal_strength', 'battery_level', 'uptime'])
                        writer.writeheader()
                        writer.writerows(device_status_data)

                    f.write("\n# Connection History\n")
                    if history_data:
                        writer = csv.DictWriter(f, fieldnames=['timestamp', 'device_id', 'event', 'duration', 'signal_quality', 'notes'])
                        writer.writeheader()
                        writer.writerows(history_data)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Device history exported successfully!\n\nFile: {file_path}\nDevices: {len(device_status_data)}\nHistory Entries: {len(history_data)}"
            )
            logger.info(f"Device history exported: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export device history:\n{e}")
            logger.error(f"Device history export error: {e}")
    
    # ==================== REMOTE COMMAND METHODS ====================
    
    def _refresh_remote_devices(self):
        """Refresh remote devices table"""
        try:
            self.remote_devices_table.setRowCount(0)
            
            for device in self.devices:
                # Only show online devices for remote commands
                if device.get('status') != 'online':
                    continue
                
                row = self.remote_devices_table.rowCount()
                self.remote_devices_table.insertRow(row)
                
                # Status
                status = device.get('status', 'unknown')
                status_widget = DeviceStatusWidget()
                status_widget.set_status(status)
                self.remote_devices_table.setCellWidget(row, 0, status_widget)
                
                # Device ID
                self.remote_devices_table.setItem(row, 1, QTableWidgetItem(device.get('device_id', '')))
                
                # Type
                type_map = {
                    'obd_adapter': 'OBD Adapter',
                    'mobile_device': 'Mobile',
                    'esp32_sensor': 'ESP32',
                    'custom': 'Custom'
                }
                device_type = type_map.get(device.get('type', ''), 'Unknown')
                self.remote_devices_table.setItem(row, 2, QTableWidgetItem(device_type))
                
                # Profile
                self.remote_devices_table.setItem(row, 3, QTableWidgetItem(device.get('profile', '-')))
                
                # Remote Commands buttons
                commands_widget = QWidget()
                commands_layout = QHBoxLayout(commands_widget)
                commands_layout.setContentsMargins(2, 2, 2, 2)
                commands_layout.setSpacing(4)
                
                # Lock button
                lock_btn = QPushButton("🔒")
                lock_btn.setFixedSize(32, 32)
                lock_btn.setToolTip("Lock Vehicle")
                lock_btn.setStyleSheet(self._get_button_style('secondary'))
                lock_btn.clicked.connect(lambda checked, d=device: self._send_remote_command(d, 'lock'))
                commands_layout.addWidget(lock_btn)
                
                # Unlock button
                unlock_btn = QPushButton("🔓")
                unlock_btn.setFixedSize(32, 32)
                unlock_btn.setToolTip("Unlock Vehicle")
                unlock_btn.setStyleSheet(self._get_button_style('secondary'))
                unlock_btn.clicked.connect(lambda checked, d=device: self._send_remote_command(d, 'unlock'))
                commands_layout.addWidget(unlock_btn)
                
                # Start Engine button
                start_btn = QPushButton("🚀")
                start_btn.setFixedSize(32, 32)
                start_btn.setToolTip("Start Engine")
                start_btn.setStyleSheet(self._get_button_style('success'))
                start_btn.clicked.connect(lambda checked, d=device: self._send_remote_command(d, 'start_engine'))
                commands_layout.addWidget(start_btn)
                
                # Stop Engine button
                stop_btn = QPushButton("🛑")
                stop_btn.setFixedSize(32, 32)
                stop_btn.setToolTip("Stop Engine")
                stop_btn.setStyleSheet(self._get_button_style('danger'))
                stop_btn.clicked.connect(lambda checked, d=device: self._send_remote_command(d, 'stop_engine'))
                commands_layout.addWidget(stop_btn)
                
                # Locate button
                locate_btn = QPushButton("📍")
                locate_btn.setFixedSize(32, 32)
                locate_btn.setToolTip("Locate Vehicle")
                locate_btn.setStyleSheet(self._get_button_style('info'))
                locate_btn.clicked.connect(lambda checked, d=device: self._send_remote_command(d, 'locate'))
                commands_layout.addWidget(locate_btn)
                
                commands_layout.addStretch()
                self.remote_devices_table.setCellWidget(row, 4, commands_widget)
                
                # Command status label
                status_label = QLabel("Ready")
                status_label.setStyleSheet("color: #8B949E; font-style: italic;")
                self.remote_devices_table.setCellWidget(row, 5, status_label)
            
            self.remote_devices_table.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Error refreshing remote devices: {e}")
    
    def _send_remote_command(self, device: dict, command_type: str):
        """Send remote command to device"""
        if not self.remote_command_system:
            QMessageBox.warning(
                self,
                "Remote Command System Not Available",
                "The remote command system is not available. Please check your configuration."
            )
            return
        
        device_id = device.get('device_id', 'Unknown')
        
        # Confirm for certain commands
        if command_type in ['start_engine', 'stop_engine']:
            reply = QMessageBox.question(
                self,
                f"Confirm {command_type.replace('_', ' ').title()}",
                f"Are you sure you want to {command_type.replace('_', ' ')} the vehicle:\n{device.get('profile', device_id)}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        try:
            # Send command
            result = self.remote_command_system.send_command(
                device_id=device_id,
                command_type=command_type,
                priority='high'
            )
            
            if result.get('success'):
                command_id = result.get('command_id')
                
                # Add to status monitor
                if hasattr(self, 'command_status_monitor'):
                    self.command_status_monitor.add_command(command_id)
                
                # Update command status in table
                self._update_device_command_status(device_id, command_id, 'queued')
                
                # Add to history
                self._add_command_to_history(device, command_type, command_id, 'queued')
                
                logger.info(f"Remote command sent: {command_type} to {device_id}")
                
            else:
                error = result.get('error', 'Unknown error')
                QMessageBox.critical(
                    self,
                    "Command Failed",
                    f"Failed to send command:\n{error}"
                )
                self._update_device_command_status(device_id, None, 'failed')
                
        except Exception as e:
            logger.error(f"Error sending remote command: {e}")
            QMessageBox.critical(
                self,
                "Command Error",
                f"Error sending command:\n{e}"
            )
            self._update_device_command_status(device_id, None, 'error')
    
    def _update_device_command_status(self, device_id: str, command_id: str, status: str):
        """Update command status in the remote devices table"""
        try:
            for row in range(self.remote_devices_table.rowCount()):
                item = self.remote_devices_table.item(row, 1)
                if item and item.text() == device_id:
                    status_label = self.remote_devices_table.cellWidget(row, 5)
                    if status_label:
                        if status == 'queued':
                            status_label.setText("Queued...")
                            status_label.setStyleSheet("color: #FFC107; font-style: italic;")
                        elif status == 'processing':
                            status_label.setText("Processing...")
                            status_label.setStyleSheet("color: #2196F3; font-style: italic;")
                        elif status == 'completed':
                            status_label.setText("✓ Completed")
                            status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                        elif status == 'failed':
                            status_label.setText("✗ Failed")
                            status_label.setStyleSheet("color: #F44336; font-weight: bold;")
                        elif status == 'error':
                            status_label.setText("✗ Error")
                            status_label.setStyleSheet("color: #F44336; font-weight: bold;")
                        else:
                            status_label.setText(status)
                            status_label.setStyleSheet("color: #8B949E; font-style: italic;")
                    break
        except Exception as e:
            logger.error(f"Error updating device command status: {e}")
    
    def _on_command_status_update(self, command_id: str, status_info: dict):
        """Handle command status update from monitor"""
        try:
            status = status_info.get('status')
            device_id = status_info.get('device_id')
            
            # Update device command status
            self._update_device_command_status(device_id, command_id, status)
            
            # Update command history
            self._update_command_history(command_id, status_info)
            
        except Exception as e:
            logger.error(f"Error handling command status update: {e}")
    
    def _add_command_to_history(self, device: dict, command_type: str,
                                 command_id: str, status: str):
        """Add command to history table"""
        try:
            row = self.command_history_table.rowCount()
            self.command_history_table.insertRow(0)  # Insert at top
            
            # Time
            time_item = QTableWidgetItem(datetime.now().strftime('%H:%M:%S'))
            self.command_history_table.setItem(row, 0, time_item)
            
            # Device
            device_item = QTableWidgetItem(device.get('profile', device.get('device_id', 'Unknown')))
            self.command_history_table.setItem(row, 1, device_item)
            
            # Command
            command_names = {
                'lock': '🔒 Lock',
                'unlock': '🔓 Unlock',
                'start_engine': '🚀 Start Engine',
                'stop_engine': '🛑 Stop Engine',
                'locate': '📍 Locate'
            }
            command_item = QTableWidgetItem(command_names.get(command_type, command_type))
            self.command_history_table.setItem(row, 2, command_item)
            
            # Status
            status_item = QTableWidgetItem(status.capitalize())
            if status == 'completed':
                status_item.setForeground(QColor('#4CAF50'))
            elif status in ['failed', 'error']:
                status_item.setForeground(QColor('#F44336'))
            elif status in ['queued', 'processing']:
                status_item.setForeground(QColor('#FFC107'))
            self.command_history_table.setItem(row, 3, status_item)
            
            # Result
            result_item = QTableWidgetItem(command_id)
            result_item.setForeground(QColor('#8B949E'))
            self.command_history_table.setItem(row, 4, result_item)
            
            # Limit history to 50 entries
            if self.command_history_table.rowCount() > 50:
                self.command_history_table.removeRow(50)
                
        except Exception as e:
            logger.error(f"Error adding command to history: {e}")
    
    def _update_command_history(self, command_id: str, status_info: dict):
        """Update command in history"""
        try:
            for row in range(self.command_history_table.rowCount()):
                result_item = self.command_history_table.item(row, 4)
                if result_item and result_item.text() == command_id:
                    status = status_info.get('status')
                    
                    # Update status column
                    status_item = self.command_history_table.item(row, 3)
                    if status_item:
                        status_item.setText(status.capitalize())
                        if status == 'completed':
                            status_item.setForeground(QColor('#4CAF50'))
                        elif status in ['failed', 'error']:
                            status_item.setForeground(QColor('#F44336'))
                        elif status in ['queued', 'processing']:
                            status_item.setForeground(QColor('#FFC107'))
                    
                    # Update result column with response
                    response = status_info.get('response')
                    if response:
                        result_text = response.get('message', 'No details')
                        if 'details' in response and response['details']:
                            details = response['details']
                            if 'confirmation_code' in details:
                                result_text += f" [{details['confirmation_code']}]"
                        result_item.setText(result_text)
                        result_item.setForeground(QColor('#F0F6FC'))
                    
                    break
        except Exception as e:
            logger.error(f"Error updating command history: {e}")
    
    def _clear_command_history(self):
        """Clear command history"""
        reply = QMessageBox.question(
            self,
            "Clear Command History",
            "Are you sure you want to clear the command history?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.command_history_table.setRowCount(0)
            logger.info("Command history cleared")
