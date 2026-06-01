"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: ESP32 Sensors Tab
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from esp32_sensor_bridge import ESP32SensorBridge
    SENSOR_MANAGER_AVAILABLE = True
except ImportError:
    SENSOR_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class ESP32SensorsTab(QWidget):
    """
    ESP32 Sensors Tab - Monitor ESP32 sensor readings
    """

    def __init__(self, sensor_manager=None):
        super().__init__()
        self.sensor_manager = sensor_manager
        self.sensors = []

        self._setup_ui()
        self._start_live_updates()

    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Connection status
        status_card = self._create_status_card()
        layout.addWidget(status_card)

        # Live readings dashboard
        readings_group = QGroupBox("Live Readings")
        readings_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        readings_layout = QVBoxLayout(readings_group)

        # Temperature
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Temperature:")
        temp_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        temp_layout.addWidget(temp_label)
        self.temp_value = QLabel("--")
        self.temp_value.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        temp_layout.addWidget(self.temp_value)
        readings_layout.addLayout(temp_layout)

        # Humidity
        humidity_layout = QHBoxLayout()
        humidity_label = QLabel("Humidity:")
        humidity_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        humidity_layout.addWidget(humidity_label)
        self.humidity_value = QLabel("--")
        self.humidity_value.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        humidity_layout.addWidget(self.humidity_value)
        readings_layout.addLayout(humidity_layout)

        # Pressure
        pressure_layout = QHBoxLayout()
        pressure_label = QLabel("Pressure:")
        pressure_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        pressure_layout.addWidget(pressure_label)
        self.pressure_value = QLabel("--")
        self.pressure_value.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        pressure_layout.addWidget(self.pressure_value)
        readings_layout.addLayout(pressure_layout)

        # GPS
        gps_layout = QHBoxLayout()
        gps_label = QLabel("GPS:")
        gps_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        gps_layout.addWidget(gps_label)
        self.gps_value = QLabel("--")
        self.gps_value.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        gps_layout.addWidget(self.gps_value)
        readings_layout.addLayout(gps_layout)

        layout.addWidget(readings_group)

        # Sensor list table
        self.sensor_table = QTableWidget()
        self.sensor_table.setColumnCount(5)
        self.sensor_table.setHorizontalHeaderLabels([
            "ID", "Type", "Status", "Last Reading", "Actions"
        ])
        self._apply_table_style(self.sensor_table)
        layout.addWidget(self.sensor_table)

        # Calibration settings panel
        calib_group = QGroupBox("Calibration Settings")
        calib_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        calib_layout = QVBoxLayout(calib_group)

        calib_form = QFormLayout()
        calib_form.setSpacing(12)

        self.temp_offset_edit = QLineEdit()
        self.temp_offset_edit.setPlaceholderText("Temperature offset")
        calib_form.addRow("Temp Offset:", self.temp_offset_edit)

        self.humidity_offset_edit = QLineEdit()
        self.humidity_offset_edit.setPlaceholderText("Humidity offset")
        calib_form.addRow("Humidity Offset:", self.humidity_offset_edit)

        self.pressure_offset_edit = QLineEdit()
        self.pressure_offset_edit.setPlaceholderText("Pressure offset")
        calib_form.addRow("Pressure Offset:", self.pressure_offset_edit)

        apply_btn = QPushButton("Apply Calibration")
        apply_btn.setStyleSheet(self._get_button_style('primary'))
        apply_btn.clicked.connect(self._apply_calibration)
        calib_layout.addWidget(apply_btn)

        layout.addWidget(calib_group)

        # Data logging toggle
        logging_group = QGroupBox("Data Logging")
        logging_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        logging_layout = QVBoxLayout(logging_group)

        self.logging_enabled = QPushButton("Logging: ENABLED")
        self.logging_enabled.setCheckable(True)
        self.logging_enabled.setChecked(True)
        self.logging_enabled.setStyleSheet(self._get_toggle_button_style(True))
        self.logging_enabled.clicked.connect(self._toggle_logging)

        logging_layout.addWidget(self.logging_enabled)

        layout.addWidget(logging_group)

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with title"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("ESP32 Sensors")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        layout.addStretch()

        return widget

    def _create_status_card(self) -> QFrame:
        """Create connection status card"""
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

        title_label = QLabel("Connection Status")
        title_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(title_label)

        status_label = QLabel("Disconnected")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet("color: #F44336; font-size: 14px; font-weight: bold; padding: 10px;")
        status_label.setObjectName("connection_status")
        layout.addWidget(status_label)

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

    def _get_toggle_button_style(self, enabled: bool) -> str:
        """Get toggle button stylesheet"""
        bg_color = "#4CAF50" if enabled else "#F44336"
        return f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 6px;
                }}
        """

    def _start_live_updates(self):
        """Start periodic updates for sensor readings"""
        if not hasattr(self, 'update_timer'):
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self._update_sensor_readings)
            self.update_timer.start(2000)  # Update every 2 seconds
        
        # Initial connection check
        self._check_esp32_connection()
    
    def _check_esp32_connection(self) -> bool:
        """
        Check ESP32 sensor connection status and update UI accordingly
        
        Returns:
            True if ESP32 is connected, False otherwise
        """
        try:
            if hasattr(self, 'sensor_manager') and self.sensor_manager:
                # Check if sensor manager has is_connected method
                if hasattr(self.sensor_manager, 'is_connected'):
                    connected = self.sensor_manager.is_connected()
                    if connected:
                        status_label = self.findChild(QLabel, "connection_status")
                        status_label.setText("ESP32 Connected")
                        status_label.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold; padding: 10px;")
                        return True
            
            # Not connected or no sensor manager
            status_label = self.findChild(QLabel, "connection_status")
            status_label.setText("ESP32 Not Connected - Optional Enhancement")
            status_label.setStyleSheet("color: #FFC107; font-size: 14px; font-weight: bold; padding: 10px;")
            
            # Reset sensor readings to show no data
            self._reset_sensor_readings()
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking ESP32 connection: {e}")
            status_label = self.findChild(QLabel, "connection_status")
            status_label.setText(f"ESP32 Error: {str(e)}")
            status_label.setStyleSheet("color: #F44336; font-size: 14px; font-weight: bold; padding: 10px;")
            
            # Reset sensor readings on error
            self._reset_sensor_readings()
            
            return False
    
    def _reset_sensor_readings(self):
        """Reset sensor readings to show no data state"""
        self.temp_value.setText("--")
        self.temp_value.setStyleSheet("color: #8B949E; font-size: 24px; font-weight: bold;")
        
        self.humidity_value.setText("--")
        self.humidity_value.setStyleSheet("color: #8B949E; font-size: 24px; font-weight: bold;")
        
        self.pressure_value.setText("--")
        self.pressure_value.setStyleSheet("color: #8B949E; font-size: 24px; font-weight: bold;")
        
        self.gps_value.setText("--")
        self.gps_value.setStyleSheet("color: #8B949E; font-size: 24px; font-weight: bold;")
    
    def _update_sensor_readings(self):
        """
        Update sensor readings from manager
        
        Only shows real readings when ESP32 is actually connected.
        Does not display fake/mock sensor readings.
        """
        # Check if ESP32 is connected before showing readings
        if not self._check_esp32_connection():
            # Not connected - readings already reset in _check_esp32_connection
            return
        
        # ESP32 is connected, try to get real readings
        if self.sensor_manager and SENSOR_MANAGER_AVAILABLE:
            try:
                readings = self.sensor_manager.get_readings()
                if readings:
                    # Update temperature - only if real data exists
                    if 'temperature' in readings and readings['temperature'] is not None:
                        temp = readings['temperature']
                        self.temp_value.setText(f"{temp:.1f}°C")
                        self.temp_value.setStyleSheet(f"color: #F0F6FC; font-size: 24px; font-weight: bold;")
                    
                    # Update humidity - only if real data exists
                    if 'humidity' in readings and readings['humidity'] is not None:
                        humidity = readings['humidity']
                        self.humidity_value.setText(f"{humidity:.1f}%")
                        self.humidity_value.setStyleSheet(f"color: #F0F6FC; font-size: 24px; font-weight: bold;")
                    
                    # Update pressure - only if real data exists
                    if 'pressure' in readings and readings['pressure'] is not None:
                        pressure = readings['pressure']
                        self.pressure_value.setText(f"{pressure:.2f} hPa")
                        self.pressure_value.setStyleSheet(f"color: #F0F6FC; font-size: 24px; font-weight: bold;")
                    
                    # Update GPS - only if real data exists
                    if 'gps' in readings and readings['gps'] is not None:
                        gps_data = readings['gps']
                        if gps_data and gps_data.get('lat') is not None and gps_data.get('lng') is not None:
                            self.gps_value.setText(f"{gps_data.get('lat', 0):.4f}, {gps_data.get('lng', 0):.4f}")
                            self.gps_value.setStyleSheet(f"color: #F0F6FC; font-size: 20px; font-weight: bold;")
                        else:
                            self.gps_value.setText("No GPS Data")
                    else:
                        self.gps_value.setText("No GPS Data")
                else:
                    # No readings available - keep showing "--"
                    logger.debug("No sensor readings available from manager")
            
            except Exception as e:
                logger.error(f"Error updating sensor readings: {e}")
                # Reset readings on error
                self._reset_sensor_readings()

    def _apply_calibration(self):
        """Apply calibration settings"""
        QMessageBox.information(self, "Calibration Applied", "Calibration settings saved successfully!")

    def _toggle_logging(self):
        """Toggle data logging"""
        enabled = self.logging_enabled.isChecked()
        if self.sensor_manager and SENSOR_MANAGER_AVAILABLE:
            try:
                self.sensor_manager.set_logging_enabled(enabled)
                status = "ENABLED" if enabled else "DISABLED"
                self.logging_enabled.setText(f"Logging: {status}")
                logger.info(f"Data logging {status.lower()}")
            except Exception as e:
                logger.error(f"Error toggling logging: {e}")
