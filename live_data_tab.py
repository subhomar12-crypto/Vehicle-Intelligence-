"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Live Data Tab
"""

from datetime import datetime
from typing import Dict, Any, Optional, Callable
from collections import deque
import math

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QSlider, QSplitter, QMessageBox, QFrame,
    QDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath

import logging

logger = logging.getLogger(__name__)


# ================================
# THEME COLORS
# ================================

class LiveDataTheme:
    """Color theme for Live Data tab"""
    PRIMARY = "#C40000"
    PRIMARY_DARK = "#A00000"
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"
    DANGER = "#F44336"
    INFO = "#0DCAF0"
    
    BACKGROUND = "#0D1117"
    BACKGROUND_SECONDARY = "#161B22"
    CARD_BG = "#21262D"
    
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"
    TEXT_MUTED = "#6E7681"
    
    BORDER = "#30363D"
    
    GAUGE_BG = "#1A1F25"
    GAUGE_NORMAL = "#4CAF50"
    GAUGE_WARNING = "#FFC107"
    GAUGE_CRITICAL = "#C40000"


# ================================
# CIRCULAR GAUGE WIDGET - FIXED ORIENTATION
# ================================

class CircularGauge(QWidget):
    """Modern circular gauge with correct 7 o'clock to 4 o'clock orientation"""
    
    def __init__(self, title: str, min_val: float, max_val: float, 
                 unit: str, warn_thresh: float = 70, crit_thresh: float = 85, 
                 size: int = 180, parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.warn_thresh = warn_thresh
        self.crit_thresh = crit_thresh
        self._size = size
        
        self._value = min_val
        self._target_value = min_val
        self._is_valid = False
        
        self.setMinimumSize(size, size)
        self.setMaximumSize(size + 20, size + 20)
        
        # Animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.setInterval(16)  # ~60fps
    
    def set_value(self, value: float, is_valid: bool = True):
        """Set gauge value with animation"""
        self._is_valid = is_valid
        self._target_value = max(self.min_val, min(self.max_val, value))
        
        if not self._anim_timer.isActive():
            self._anim_timer.start()
    
    def _animate(self):
        """Smooth animation towards target"""
        diff = self._target_value - self._value
        if abs(diff) < 0.5:
            self._value = self._target_value
            self._anim_timer.stop()
        else:
            self._value += diff * 0.15
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w // 2, h // 2
        radius = min(w, h) // 2 - 15
        
        # Background circle
        painter.setPen(QPen(QColor(LiveDataTheme.BORDER), 2))
        painter.setBrush(QBrush(QColor(LiveDataTheme.GAUGE_BG)))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Draw background arc (shows full range in dark)
        arc_width = 12
        arc_rect = QRectF(
            center_x - radius + arc_width // 2,
            center_y - radius + arc_width // 2,
            (radius - arc_width // 2) * 2,
            (radius - arc_width // 2) * 2
        )
        
        # Background arc (full sweep in dark color)
        painter.setPen(QPen(QColor("#2a2a2a"), arc_width, Qt.SolidLine, Qt.RoundCap))
        # Start at 225° (7 o'clock), sweep 270° clockwise (negative)
        painter.drawArc(arc_rect, 225 * 16, -270 * 16)
        
        # Value arc
        if self._is_valid:
            value_pct = (self._value - self.min_val) / (self.max_val - self.min_val)
            value_pct = max(0, min(1, value_pct))
            
            # Choose color based on value percentage
            if value_pct * 100 >= self.crit_thresh:
                color = QColor(LiveDataTheme.GAUGE_CRITICAL)
            elif value_pct * 100 >= self.warn_thresh:
                color = QColor(LiveDataTheme.WARNING)
            else:
                color = QColor(LiveDataTheme.GAUGE_NORMAL)
            
            painter.setPen(QPen(color, arc_width, Qt.SolidLine, Qt.RoundCap))
            
            # FIXED: Start at 225° (7 o'clock), sweep clockwise (negative angle)
            # Full sweep is 270° from 7 o'clock to 4 o'clock
            start_angle = 225 * 16  # 7 o'clock position
            span_angle = -int(value_pct * 270 * 16)  # Clockwise sweep (negative)
            painter.drawArc(arc_rect, start_angle, span_angle)
        
        # Draw tick marks
        painter.setPen(QPen(QColor(LiveDataTheme.TEXT_MUTED), 1))
        tick_radius = radius - 5
        for i in range(11):  # 11 ticks for 0%, 10%, 20%, ... 100%
            angle_deg = 225 - (i * 27)  # 270° / 10 = 27° per tick
            angle_rad = math.radians(angle_deg)
            
            inner_r = tick_radius - 8
            outer_r = tick_radius - 3
            
            x1 = center_x + inner_r * math.cos(angle_rad)
            y1 = center_y - inner_r * math.sin(angle_rad)
            x2 = center_x + outer_r * math.cos(angle_rad)
            y2 = center_y - outer_r * math.sin(angle_rad)
            
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Min label (at 7 o'clock)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(LiveDataTheme.TEXT_MUTED))
        min_angle = math.radians(225)
        label_r = radius - 25
        min_x = center_x + label_r * math.cos(min_angle) - 10
        min_y = center_y - label_r * math.sin(min_angle) + 5
        painter.drawText(int(min_x), int(min_y), str(int(self.min_val)))
        
        # Max label (at 4 o'clock, which is -45°)
        max_angle = math.radians(-45)
        max_x = center_x + label_r * math.cos(max_angle) - 5
        max_y = center_y - label_r * math.sin(max_angle) + 5
        painter.drawText(int(max_x), int(max_y), str(int(self.max_val)))
        
        # Title
        painter.setPen(QColor(LiveDataTheme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(0, center_y - radius + 25, w, 20, Qt.AlignCenter, self.title)
        
        # Value text
        if self._is_valid:
            painter.setPen(QColor(LiveDataTheme.TEXT_PRIMARY))
            painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
            value_text = f"{self._value:.0f}"
        else:
            painter.setPen(QColor(LiveDataTheme.TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
            value_text = "—"
        
        painter.drawText(0, center_y - 15, w, 40, Qt.AlignCenter, value_text)
        
        # Unit
        painter.setPen(QColor(LiveDataTheme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(0, center_y + 20, w, 20, Qt.AlignCenter, self.unit)


# ================================
# DATA QUALITY BADGE WIDGET
# ================================

class DataQualityBadge(QWidget):
    """
    Displays data quality status, sampling rate, and missing signals
    Purpose: Shows AI awareness and data quality for predictions
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.quality_score = 0.0
        self.sampling_rate = 0.0
        self.missing_signals = []
        self.total_signals = 0
        self.available_signals = 0

        self.setMinimumHeight(80)
        self.setMaximumHeight(100)

    def update_quality(self, quality_score: float, sampling_rate: float,
                      available: int, total: int, missing: list):
        """Update quality badge data"""
        self.quality_score = quality_score
        self.sampling_rate = sampling_rate
        self.available_signals = available
        self.total_signals = total
        self.missing_signals = missing[:3]  # Show max 3 missing
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        margin = 10

        # Background card
        painter.setPen(QPen(QColor(LiveDataTheme.BORDER), 1))
        painter.setBrush(QBrush(QColor(LiveDataTheme.CARD_BG)))
        painter.drawRoundedRect(margin, margin, w - 2*margin, h - 2*margin, 8, 8)

        # Quality indicator circle
        circle_x = margin + 20
        circle_y = h // 2
        circle_radius = 15

        # Determine color based on quality score
        if self.quality_score >= 0.8:
            status_color = QColor(LiveDataTheme.SUCCESS)
            status_text = "Good"
        elif self.quality_score >= 0.6:
            status_color = QColor(LiveDataTheme.WARNING)
            status_text = "Partial"
        else:
            status_color = QColor(LiveDataTheme.DANGER)
            status_text = "Poor"

        painter.setPen(QPen(status_color, 2))
        painter.setBrush(QBrush(status_color.lighter(150)))
        painter.drawEllipse(circle_x - circle_radius, circle_y - circle_radius,
                          circle_radius * 2, circle_radius * 2)

        # Text content
        text_x = circle_x + circle_radius + 15

        # Title
        painter.setPen(QColor(LiveDataTheme.TEXT_PRIMARY))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(text_x, margin + 20, "Data Quality: " + status_text)

        # Details
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(LiveDataTheme.TEXT_SECONDARY))

        details_y = margin + 38
        painter.drawText(text_x, details_y,
                        f"Sampling: ~{self.sampling_rate:.1f} Hz")

        painter.drawText(text_x, details_y + 15,
                        f"Signals: {self.available_signals}/{self.total_signals}")

        # Missing signals warning
        if self.missing_signals:
            painter.setPen(QColor(LiveDataTheme.WARNING))
            missing_text = ", ".join(self.missing_signals)
            if len(self.missing_signals) < len(missing_text.split(", ")):
                missing_text += "..."
            painter.drawText(text_x, details_y + 30,
                           f"Missing: {missing_text}")


# ================================
# LINEAR GAUGE WIDGET
# ================================

class LinearGauge(QWidget):
    """Modern linear/bar gauge"""
    
    def __init__(self, title: str, min_val: float, max_val: float,
                 unit: str, warn_thresh: float = 75, crit_thresh: float = 90, parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.warn_thresh = warn_thresh
        self.crit_thresh = crit_thresh
        
        self._value = min_val
        self._is_valid = False
        
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
    
    def set_value(self, value: float, is_valid: bool = True):
        """Set gauge value"""
        self._is_valid = is_valid
        self._value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        margin = 10
        bar_height = 12
        bar_y = h // 2 + 5
        bar_width = w - 2 * margin
        
        # Title and value
        painter.setPen(QColor(LiveDataTheme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(margin, 5, bar_width // 2, 20, Qt.AlignLeft, self.title)
        
        if self._is_valid:
            value_text = f"{self._value:.1f} {self.unit}"
            painter.setPen(QColor(LiveDataTheme.TEXT_PRIMARY))
        else:
            value_text = f"— {self.unit}"
            painter.setPen(QColor(LiveDataTheme.TEXT_MUTED))
        
        painter.drawText(margin, 5, bar_width, 20, Qt.AlignRight, value_text)
        
        # Background bar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(LiveDataTheme.BORDER)))
        painter.drawRoundedRect(margin, bar_y, bar_width, bar_height, 6, 6)
        
        # Value bar
        if self._is_valid:
            value_pct = (self._value - self.min_val) / (self.max_val - self.min_val)
            value_pct = max(0, min(1, value_pct))
            fill_width = int(bar_width * value_pct)
            
            if value_pct * 100 >= self.crit_thresh:
                color = QColor(LiveDataTheme.GAUGE_CRITICAL)
            elif value_pct * 100 >= self.warn_thresh:
                color = QColor(LiveDataTheme.WARNING)
            else:
                color = QColor(LiveDataTheme.GAUGE_NORMAL)
            
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(margin, bar_y, fill_width, bar_height, 6, 6)


# ================================
# GAUGE POPUP WINDOW
# ================================

class GaugePopupWindow(QDialog):
    """Popup window with large gauges and all readings"""
    
    def __init__(self, connectivity_manager, parent=None):
        super().__init__(parent)
        self.connectivity = connectivity_manager
        
        self.setWindowTitle("🚗 Live Vehicle Gauges")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {LiveDataTheme.BACKGROUND};
            }}
            QLabel {{
                color: {LiveDataTheme.TEXT_PRIMARY};
            }}
            QGroupBox {{
                color: {LiveDataTheme.PRIMARY};
                font-weight: bold;
                font-size: 14px;
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
            }}
            QTableWidget {{
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 5px;
                gridline-color: {LiveDataTheme.BORDER};
            }}
            QTableWidget::item {{
                color: {LiveDataTheme.TEXT_PRIMARY};
                padding: 5px;
            }}
            QHeaderView::section {{
                background-color: {LiveDataTheme.BACKGROUND_SECONDARY};
                color: {LiveDataTheme.PRIMARY};
                padding: 8px;
                border: none;
                font-weight: bold;
            }}
        """)
        
        self._build_ui()
        self._start_updates()
    
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title bar
        title_bar = QHBoxLayout()
        title = QLabel("🚗 LIVE VEHICLE GAUGES")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color: {LiveDataTheme.PRIMARY};")
        title_bar.addWidget(title)
        title_bar.addStretch()
        
        # Close button
        close_btn = QPushButton("✕ Close")
        close_btn.setStyleSheet(self._get_button_style('primary'))
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        
        main_layout.addLayout(title_bar)
        
        # Content area with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # Main Gauges Section
        gauges_group = QGroupBox("🎛️ Main Gauges")
        gauges_layout = QHBoxLayout(gauges_group)
        gauges_layout.setSpacing(30)
        gauges_layout.setContentsMargins(20, 30, 20, 20)
        
        # Create large gauges
        self.popup_rpm_gauge = CircularGauge("ENGINE RPM", 0, 8000, "RPM", 
                                              warn_thresh=75, crit_thresh=90, size=220)
        self.popup_speed_gauge = CircularGauge("SPEED", 0, 220, "km/h",
                                                warn_thresh=80, crit_thresh=95, size=220)
        self.popup_coolant_gauge = CircularGauge("COOLANT", 0, 130, "°C",
                                                  warn_thresh=70, crit_thresh=85, size=220)
        self.popup_battery_gauge = CircularGauge("BATTERY", 10, 16, "V",
                                                  warn_thresh=85, crit_thresh=95, size=220)
        
        gauges_layout.addStretch()
        gauges_layout.addWidget(self.popup_rpm_gauge)
        gauges_layout.addWidget(self.popup_speed_gauge)
        gauges_layout.addWidget(self.popup_coolant_gauge)
        gauges_layout.addWidget(self.popup_battery_gauge)
        gauges_layout.addStretch()
        
        content_layout.addWidget(gauges_group)
        
        # Secondary Gauges
        secondary_group = QGroupBox("📊 Engine Parameters")
        secondary_layout = QGridLayout(secondary_group)
        secondary_layout.setSpacing(15)
        secondary_layout.setContentsMargins(20, 30, 20, 20)
        
        self.popup_load_gauge = LinearGauge("Engine Load", 0, 100, "%", 75, 90)
        self.popup_throttle_gauge = LinearGauge("Throttle Position", 0, 100, "%", 80, 95)
        self.popup_fuel_gauge = LinearGauge("Fuel Level", 0, 100, "%", 20, 10)
        self.popup_intake_gauge = LinearGauge("Intake Temp", -40, 80, "°C", 70, 85)
        self.popup_map_gauge = LinearGauge("MAP", 0, 255, "kPa", 80, 95)
        self.popup_maf_gauge = LinearGauge("MAF", 0, 500, "g/s", 80, 95)
        
        secondary_layout.addWidget(self.popup_load_gauge, 0, 0)
        secondary_layout.addWidget(self.popup_throttle_gauge, 0, 1)
        secondary_layout.addWidget(self.popup_fuel_gauge, 1, 0)
        secondary_layout.addWidget(self.popup_intake_gauge, 1, 1)
        secondary_layout.addWidget(self.popup_map_gauge, 2, 0)
        secondary_layout.addWidget(self.popup_maf_gauge, 2, 1)
        
        content_layout.addWidget(secondary_group)
        
        # All PID Values Table
        table_group = QGroupBox("📋 All Available Readings")
        table_layout = QVBoxLayout(table_group)
        
        self.popup_table = QTableWidget()
        self.popup_table.setColumnCount(3)
        self.popup_table.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
        self.popup_table.horizontalHeader().setStretchLastSection(True)
        self.popup_table.setMinimumHeight(250)
        self._apply_table_styling(self.popup_table)
        table_layout.addWidget(self.popup_table)
        
        content_layout.addWidget(table_group)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
    
    def _start_updates(self):
        """Start update timer"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_gauges)
        self.update_timer.start(250)  # 250ms updates
    
    def _update_gauges(self):
        """Update all gauges with latest data"""
        if not self.connectivity:
            return
        
        data = getattr(self.connectivity, 'latest_merged', None) or {}
        
        # Update main gauges
        rpm = data.get('rpm') or data.get('RPM')
        self.popup_rpm_gauge.set_value(float(rpm) if rpm else 0, rpm is not None)
        
        speed = data.get('speed') or data.get('SPEED')
        self.popup_speed_gauge.set_value(float(speed) if speed else 0, speed is not None)
        
        coolant = data.get('coolant_temp') or data.get('COOLANT_TEMP')
        self.popup_coolant_gauge.set_value(float(coolant) if coolant else 0, coolant is not None)
        
        voltage = data.get('battery_voltage') or data.get('CONTROL_MODULE_VOLTAGE')
        self.popup_battery_gauge.set_value(float(voltage) if voltage else 12.0, voltage is not None)
        
        # Update secondary gauges
        load = data.get('engine_load') or data.get('ENGINE_LOAD')
        self.popup_load_gauge.set_value(float(load) if load else 0, load is not None)
        
        throttle = data.get('throttle_pos') or data.get('THROTTLE_POS')
        self.popup_throttle_gauge.set_value(float(throttle) if throttle else 0, throttle is not None)
        
        fuel = data.get('fuel_level') or data.get('FUEL_LEVEL')
        self.popup_fuel_gauge.set_value(float(fuel) if fuel else 0, fuel is not None)
        
        intake = data.get('intake_temp') or data.get('INTAKE_TEMP')
        self.popup_intake_gauge.set_value(float(intake) if intake else 0, intake is not None)
        
        map_val = data.get('intake_pressure') or data.get('INTAKE_PRESSURE')
        self.popup_map_gauge.set_value(float(map_val) if map_val else 0, map_val is not None)
        
        maf = data.get('maf') or data.get('MAF')
        self.popup_maf_gauge.set_value(float(maf) if maf else 0, maf is not None)
        
        # Update table with all values
        self._update_table(data)
    
    def _update_table(self, data: dict):
        """Update the all-values table"""
        # Filter and prepare data
        items = []
        for key, value in data.items():
            if value is not None and not key.startswith('_'):
                if isinstance(value, (int, float)):
                    items.append((key, f"{value:.2f}" if isinstance(value, float) else str(value), self._get_unit(key)))
                elif isinstance(value, str):
                    items.append((key, value, ""))
        
        self.popup_table.setRowCount(len(items))
        for row, (param, val, unit) in enumerate(items):
            self.popup_table.setItem(row, 0, QTableWidgetItem(param))
            self.popup_table.setItem(row, 1, QTableWidgetItem(val))
            self.popup_table.setItem(row, 2, QTableWidgetItem(unit))
    
    def _get_unit(self, key: str) -> str:
        """Get unit for a parameter"""
        units = {
            'rpm': 'RPM', 'RPM': 'RPM',
            'speed': 'km/h', 'SPEED': 'km/h',
            'coolant_temp': '°C', 'COOLANT_TEMP': '°C',
            'intake_temp': '°C', 'INTAKE_TEMP': '°C',
            'oil_temp': '°C',
            'battery_voltage': 'V', 'CONTROL_MODULE_VOLTAGE': 'V',
            'engine_load': '%', 'ENGINE_LOAD': '%',
            'throttle_pos': '%', 'THROTTLE_POS': '%',
            'fuel_level': '%', 'FUEL_LEVEL': '%',
            'maf': 'g/s', 'MAF': 'g/s',
            'intake_pressure': 'kPa', 'INTAKE_PRESSURE': 'kPa',
        }
        return units.get(key, '')
    
    def closeEvent(self, event):
        """Stop timer when closing"""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        event.accept()


# ================================
# MINI SPARK LINE
# ================================

class SparkLine(QWidget):
    """Mini trend line widget"""
    
    def __init__(self, color: str = LiveDataTheme.PRIMARY, parent=None):
        super().__init__(parent)
        self.color = color
        self.data = deque(maxlen=50)
        self.setMinimumHeight(30)
        self.setMaximumHeight(40)
    
    def add_value(self, value: float):
        """Add a value to the sparkline"""
        self.data.append(value)
        self.update()
    
    def paintEvent(self, event):
        if len(self.data) < 2:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        margin = 5
        
        data_list = list(self.data)
        min_val = min(data_list)
        max_val = max(data_list)
        value_range = max_val - min_val if max_val != min_val else 1
        
        painter.setPen(QPen(QColor(self.color), 2))
        
        points = []
        for i, val in enumerate(data_list):
            x = margin + (i / (len(data_list) - 1)) * (w - 2 * margin)
            y = h - margin - ((val - min_val) / value_range) * (h - 2 * margin)
            points.append((x, y))
        
        for i in range(len(points) - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]),
                           int(points[i+1][0]), int(points[i+1][1]))


# ================================
# LIVE DATA TAB - MAIN WIDGET
# ================================

class LiveDataTab(QWidget):
    """Live Data Dashboard with gauge popup functionality"""
    
    connection_status_changed = Signal(bool)
    
    def __init__(self, connectivity_manager=None, on_snapshot=None, parent=None):
        super().__init__(parent)
        self.connectivity = connectivity_manager
        self.on_snapshot_callback = on_snapshot  # Callback for when data updates
        self.popup_window = None

        # Data history for trends
        self.rpm_history = deque(maxlen=50)
        self.speed_history = deque(maxlen=50)
        self.temp_history = deque(maxlen=50)

        # Data source tracking
        self.current_data_source = 'usb'  # Default to USB

        # AI attention tracking (signals currently influencing predictions)
        self.ai_attention_signals = set()  # Set of signal names AI is watching
        self.ai_deviation_reasons = {}  # signal_name -> reason string

        # Data quality tracking
        self.last_update_time = None
        self.update_count = 0

        self._build_ui()
        self._start_updates()
    
    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {LiveDataTheme.BACKGROUND};
                color: {LiveDataTheme.TEXT_PRIMARY};
            }}
            QGroupBox {{
                color: {LiveDataTheme.PRIMARY};
                font-weight: bold;
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Header
        header = self._build_header()
        main_layout.addLayout(header)
        
        # Main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - gauges and parameters
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)
        
        # Live gauges section with Open button
        gauges_section = self._build_gauges_section()
        left_layout.addWidget(gauges_section)
        
        # Engine parameters
        params_section = self._build_params_section()
        left_layout.addWidget(params_section)
        
        # Trends
        trends_section = self._build_trends_section()
        left_layout.addWidget(trends_section)
        
        left_layout.addStretch()
        splitter.addWidget(left_panel)
        
        # Right panel - table and log
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # PID values table
        table_group = QGroupBox("All PID Values")
        table_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {LiveDataTheme.PRIMARY};
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 10px;
                background-color: {LiveDataTheme.CARD_BG};
            }}
        """)
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(14, 20, 14, 14)

        self.pid_table = QTableWidget()
        self.pid_table.setColumnCount(3)
        self.pid_table.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
        self.pid_table.horizontalHeader().setStretchLastSection(True)
        self.pid_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {LiveDataTheme.BACKGROUND};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
                gridline-color: {LiveDataTheme.BORDER};
            }}
            QTableWidget::item {{
                color: {LiveDataTheme.TEXT_PRIMARY};
                padding: 6px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {LiveDataTheme.PRIMARY};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {LiveDataTheme.BACKGROUND_SECONDARY};
                color: {LiveDataTheme.PRIMARY};
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid {LiveDataTheme.PRIMARY};
                font-weight: 600;
                font-size: 12px;
            }}
            QScrollBar:vertical {{
                background-color: {LiveDataTheme.BACKGROUND};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {LiveDataTheme.BORDER};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {LiveDataTheme.TEXT_MUTED};
            }}
        """)
        table_layout.addWidget(self.pid_table)
        right_layout.addWidget(table_group, 1)  # Give table more stretch

        # Data log
        log_group = QGroupBox("Data Log")
        log_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {LiveDataTheme.PRIMARY};
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 10px;
                background-color: {LiveDataTheme.CARD_BG};
            }}
        """)
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(14, 20, 14, 14)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(140)
        self.log_output.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {LiveDataTheme.BACKGROUND};
                color: {LiveDataTheme.TEXT_SECONDARY};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 10px;
                line-height: 1.4;
            }}
            QScrollBar:vertical {{
                background-color: {LiveDataTheme.BACKGROUND};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {LiveDataTheme.BORDER};
                border-radius: 5px;
                min-height: 20px;
            }}
        """)
        log_layout.addWidget(self.log_output)
        right_layout.addWidget(log_group)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
    
    def _build_header(self) -> QVBoxLayout:
        """Build organized header with title bar and control toolbar"""
        header_container = QVBoxLayout()
        header_container.setSpacing(10)

        # ===== ROW 1: Title Bar =====
        title_bar = QFrame()
        title_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
            }}
        """)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(16, 12, 16, 12)
        title_bar_layout.setSpacing(16)

        # Title
        title = QLabel("Live Data Dashboard")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {LiveDataTheme.TEXT_PRIMARY}; background: transparent; border: none;")
        title_bar_layout.addWidget(title)

        title_bar_layout.addStretch()

        # Status indicators group
        status_frame = QFrame()
        status_frame.setStyleSheet("background: transparent; border: none;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(12)

        # Data source indicator
        self.source_label = QLabel("USB OBD")
        self.source_label.setStyleSheet(f"""
            background-color: {LiveDataTheme.INFO};
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
        """)
        status_layout.addWidget(self.source_label)

        # Status
        self.status_label = QLabel("● Disconnected")
        self.status_label.setStyleSheet(f"""
            color: {LiveDataTheme.DANGER};
            font-weight: 600;
            padding: 0 8px;
            background: transparent;
            border: none;
        """)
        status_layout.addWidget(self.status_label)

        title_bar_layout.addWidget(status_frame)
        header_container.addWidget(title_bar)

        # ===== ROW 2: Controls Toolbar =====
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.BACKGROUND_SECONDARY};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
            }}
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(16)

        # Data Quality Badge
        self.quality_badge = DataQualityBadge()
        self.quality_badge.setFixedWidth(320)
        self.quality_badge.setStyleSheet("border: none; background: transparent;")
        toolbar_layout.addWidget(self.quality_badge)

        # Separator
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet(f"background-color: {LiveDataTheme.BORDER};")
        toolbar_layout.addWidget(sep1)

        # Update rate control
        rate_label_text = QLabel("Update Rate:")
        rate_label_text.setStyleSheet(f"color: {LiveDataTheme.TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
        toolbar_layout.addWidget(rate_label_text)

        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setMinimum(100)
        self.rate_slider.setMaximum(2000)
        self.rate_slider.setValue(500)
        self.rate_slider.setFixedWidth(100)
        self.rate_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {LiveDataTheme.BACKGROUND};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {LiveDataTheme.PRIMARY};
                border: 2px solid {LiveDataTheme.BORDER};
                width: 14px;
                height: 14px;
                margin: -6px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #E53935;
            }}
            QSlider::sub-page:horizontal {{
                background: {LiveDataTheme.PRIMARY};
                border-radius: 2px;
            }}
        """)
        self.rate_slider.valueChanged.connect(self._update_rate_changed)
        toolbar_layout.addWidget(self.rate_slider)

        self.rate_label = QLabel("500ms")
        self.rate_label.setStyleSheet(f"color: {LiveDataTheme.TEXT_PRIMARY}; font-weight: 600; font-size: 12px; min-width: 45px; border: none; background: transparent;")
        toolbar_layout.addWidget(self.rate_label)

        toolbar_layout.addStretch()

        # Separator
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet(f"background-color: {LiveDataTheme.BORDER};")
        toolbar_layout.addWidget(sep2)

        # Action buttons
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._get_small_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_data)
        toolbar_layout.addWidget(refresh_btn)

        debug_btn = QPushButton("Debug")
        debug_btn.setStyleSheet(self._get_small_button_style('secondary'))
        debug_btn.clicked.connect(self._show_debug)
        toolbar_layout.addWidget(debug_btn)

        clear_btn = QPushButton("Clear Log")
        clear_btn.setStyleSheet(self._get_small_button_style('secondary'))
        clear_btn.clicked.connect(lambda: self.log_output.clear())
        toolbar_layout.addWidget(clear_btn)

        header_container.addWidget(toolbar)

        return header_container

    def _get_small_button_style(self, style_type: str = 'secondary') -> str:
        """Get compact button style for toolbar"""
        if style_type == 'primary':
            return f"""
                QPushButton {{
                    background-color: {LiveDataTheme.PRIMARY};
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: #E53935;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background-color: {LiveDataTheme.CARD_BG};
                    color: {LiveDataTheme.TEXT_PRIMARY};
                    border: 1px solid {LiveDataTheme.BORDER};
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {LiveDataTheme.BORDER};
                }}
            """
    
    def _build_gauges_section(self) -> QGroupBox:
        """Build gauges section with open popup button"""
        group = QGroupBox("Live Vehicle Data")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {LiveDataTheme.PRIMARY};
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 10px;
                background-color: {LiveDataTheme.CARD_BG};
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(16)

        # Mini gauges - centered in a container
        gauges_container = QFrame()
        gauges_container.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.BACKGROUND};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
            }}
        """)
        gauges_frame_layout = QHBoxLayout(gauges_container)
        gauges_frame_layout.setContentsMargins(16, 12, 16, 12)
        gauges_frame_layout.setSpacing(20)

        self.rpm_gauge = CircularGauge("ENGINE RPM", 0, 8000, "RPM", size=120)
        self.speed_gauge = CircularGauge("SPEED", 0, 220, "km/h", size=120)
        self.coolant_gauge = CircularGauge("COOLANT", 0, 130, "°C", size=120)
        self.battery_gauge = CircularGauge("BATTERY", 10, 16, "V", size=120)

        gauges_frame_layout.addStretch()
        gauges_frame_layout.addWidget(self.rpm_gauge)
        gauges_frame_layout.addWidget(self.speed_gauge)
        gauges_frame_layout.addWidget(self.coolant_gauge)
        gauges_frame_layout.addWidget(self.battery_gauge)
        gauges_frame_layout.addStretch()

        layout.addWidget(gauges_container)

        # Button row - compact toolbar style
        btn_container = QFrame()
        btn_container.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.BACKGROUND_SECONDARY};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 6px;
            }}
        """)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(10, 8, 10, 8)
        btn_layout.setSpacing(10)

        # Open full gauge panel button
        open_gauges_btn = QPushButton("Open Full Gauge Panel")
        open_gauges_btn.setStyleSheet(self._get_small_button_style('primary'))
        open_gauges_btn.clicked.connect(self._open_gauge_popup)
        btn_layout.addWidget(open_gauges_btn)

        btn_layout.addStretch()

        # Fetch from Mobile button
        self.fetch_mobile_btn = QPushButton("Fetch from Mobile")
        self.fetch_mobile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LiveDataTheme.SUCCESS};
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
        """)
        self.fetch_mobile_btn.clicked.connect(self._fetch_from_mobile)
        btn_layout.addWidget(self.fetch_mobile_btn)

        # Auto-fetch toggle
        self.auto_fetch_enabled = False
        self.auto_fetch_btn = QPushButton("Auto-Fetch: OFF")
        self.auto_fetch_btn.setStyleSheet(self._get_small_button_style('secondary'))
        self.auto_fetch_btn.clicked.connect(self._toggle_auto_fetch)
        btn_layout.addWidget(self.auto_fetch_btn)

        layout.addWidget(btn_container)

        return group
    
    def _build_params_section(self) -> QGroupBox:
        """Build engine parameters section"""
        group = QGroupBox("Engine Parameters")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {LiveDataTheme.PRIMARY};
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 10px;
                background-color: {LiveDataTheme.CARD_BG};
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(8)

        # Wrap linear gauges in a styled container
        params_container = QFrame()
        params_container.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.BACKGROUND};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
            }}
        """)
        params_layout = QVBoxLayout(params_container)
        params_layout.setContentsMargins(14, 10, 14, 10)
        params_layout.setSpacing(4)

        self.load_gauge = LinearGauge("Engine Load", 0, 100, "%")
        self.throttle_gauge = LinearGauge("Throttle Position", 0, 100, "%")
        self.fuel_gauge = LinearGauge("Fuel Level", 0, 100, "%", 20, 10)

        params_layout.addWidget(self.load_gauge)
        params_layout.addWidget(self.throttle_gauge)
        params_layout.addWidget(self.fuel_gauge)

        layout.addWidget(params_container)

        return group
    
    def _build_trends_section(self) -> QGroupBox:
        """Build trends section with sparklines"""
        group = QGroupBox("Trends (Last 50 Readings)")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                color: {LiveDataTheme.PRIMARY};
                background-color: {LiveDataTheme.CARD_BG};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 2px 10px;
                background-color: {LiveDataTheme.CARD_BG};
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(8)

        # Wrap trends in a styled container
        trends_container = QFrame()
        trends_container.setStyleSheet(f"""
            QFrame {{
                background-color: {LiveDataTheme.BACKGROUND};
                border: 1px solid {LiveDataTheme.BORDER};
                border-radius: 8px;
            }}
        """)
        trends_layout = QGridLayout(trends_container)
        trends_layout.setContentsMargins(14, 10, 14, 10)
        trends_layout.setHorizontalSpacing(12)
        trends_layout.setVerticalSpacing(6)

        # RPM trend
        rpm_label = QLabel("RPM:")
        rpm_label.setStyleSheet(f"color: {LiveDataTheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; min-width: 45px;")
        trends_layout.addWidget(rpm_label, 0, 0)
        self.rpm_spark = SparkLine(LiveDataTheme.PRIMARY)
        trends_layout.addWidget(self.rpm_spark, 0, 1)

        # Speed trend
        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet(f"color: {LiveDataTheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; min-width: 45px;")
        trends_layout.addWidget(speed_label, 1, 0)
        self.speed_spark = SparkLine(LiveDataTheme.INFO)
        trends_layout.addWidget(self.speed_spark, 1, 1)

        # Temp trend
        temp_label = QLabel("Temp:")
        temp_label.setStyleSheet(f"color: {LiveDataTheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; min-width: 45px;")
        trends_layout.addWidget(temp_label, 2, 0)
        self.temp_spark = SparkLine(LiveDataTheme.WARNING)
        trends_layout.addWidget(self.temp_spark, 2, 1)

        layout.addWidget(trends_container)

        return group
    
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
    
    def _open_gauge_popup(self):
        """Open the gauge popup window"""
        if self.popup_window is None or not self.popup_window.isVisible():
            self.popup_window = GaugePopupWindow(self.connectivity, self)
            self.popup_window.show()
        else:
            self.popup_window.raise_()
            self.popup_window.activateWindow()
    
    def _start_updates(self):
        """Start update timer"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(500)
    
    def _update_rate_changed(self, value: int):
        """Handle rate slider change"""
        self.rate_label.setText(f"{value}ms")
        self.update_timer.setInterval(value)
    
    def _update_display(self):
        """Update all displays with latest data"""
        if not self.connectivity:
            return

        # Get latest data
        data = getattr(self.connectivity, 'latest_merged', None) or {}

        # Update data quality badge
        if data:
            self.update_data_quality(data)

        # Call the snapshot callback if provided
        if self.on_snapshot_callback and data:
            try:
                self.on_snapshot_callback(data)
            except Exception as e:
                logger.error(f"Error in snapshot callback: {e}")

        # Update data source indicator from metadata
        if data and 'metadata' in data:
            source = data['metadata'].get('source', 'usb')
            self.set_data_source(source)

        # Update connection status
        is_connected = getattr(self.connectivity, 'connected', False)
        if is_connected:
            self.status_label.setText("● Connected")
            self.status_label.setStyleSheet(f"color: {LiveDataTheme.SUCCESS};")
        else:
            self.status_label.setText("● Disconnected")
            self.status_label.setStyleSheet(f"color: {LiveDataTheme.DANGER};")
        
        # Update gauges
        rpm = data.get('rpm') or data.get('RPM')
        self.rpm_gauge.set_value(float(rpm) if rpm else 0, rpm is not None)
        if rpm:
            self.rpm_history.append(float(rpm))
            self.rpm_spark.add_value(float(rpm))
        
        speed = data.get('speed') or data.get('SPEED')
        self.speed_gauge.set_value(float(speed) if speed else 0, speed is not None)
        if speed:
            self.speed_history.append(float(speed))
            self.speed_spark.add_value(float(speed))
        
        coolant = data.get('coolant_temp') or data.get('COOLANT_TEMP')
        self.coolant_gauge.set_value(float(coolant) if coolant else 0, coolant is not None)
        if coolant:
            self.temp_history.append(float(coolant))
            self.temp_spark.add_value(float(coolant))
        
        voltage = data.get('battery_voltage') or data.get('CONTROL_MODULE_VOLTAGE')
        self.battery_gauge.set_value(float(voltage) if voltage else 12.0, voltage is not None)
        
        # Update linear gauges
        load = data.get('engine_load') or data.get('ENGINE_LOAD')
        self.load_gauge.set_value(float(load) if load else 0, load is not None)
        
        throttle = data.get('throttle_pos') or data.get('THROTTLE_POS')
        self.throttle_gauge.set_value(float(throttle) if throttle else 0, throttle is not None)
        
        fuel = data.get('fuel_level') or data.get('FUEL_LEVEL')
        self.fuel_gauge.set_value(float(fuel) if fuel else 0, fuel is not None)
        
        # Update table
        self._update_table(data)
    
    def _update_table(self, data: dict):
        """Update the PID values table with AI attention highlighting"""
        items = []
        for key, value in data.items():
            if value is not None and not key.startswith('_'):
                if isinstance(value, (int, float)):
                    items.append((key, f"{value:.2f}" if isinstance(value, float) else str(value), ""))
                elif isinstance(value, str):
                    items.append((key, value, ""))

        self.pid_table.setRowCount(len(items))
        for row, (param, val, unit) in enumerate(items):
            param_item = QTableWidgetItem(param)
            val_item = QTableWidgetItem(val)
            unit_item = QTableWidgetItem(unit)

            # Highlight if AI is paying attention to this signal
            if param.lower() in self.ai_attention_signals:
                # Subtle visual emphasis for AI-watched signals
                highlight_color = QColor(LiveDataTheme.INFO)
                highlight_color.setAlpha(40)  # Semi-transparent
                param_item.setBackground(highlight_color)
                val_item.setBackground(highlight_color)

                # Add tooltip explaining why AI is watching
                reason = self.ai_deviation_reasons.get(param.lower(), "AI detected deviation from baseline")
                param_item.setToolTip(f"🤖 {reason}")
                val_item.setToolTip(f"🤖 {reason}")

            self.pid_table.setItem(row, 0, param_item)
            self.pid_table.setItem(row, 1, val_item)
            self.pid_table.setItem(row, 2, unit_item)

    def set_data_source(self, source: str):
        """Update data source indicator

        Args:
            source: Either 'usb' or 'android'
        """
        if source == self.current_data_source:
            return

        self.current_data_source = source

        if source == 'mobile_app' or source == 'android_mobile' or source == 'ios_mobile':
            self.source_label.setText("📱 Mobile OBD")
            self.source_label.setStyleSheet(f"""
                background-color: {LiveDataTheme.SUCCESS};
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-weight: bold;
            """)
            logger.info("Data source switched to Mobile")
        else:
            self.source_label.setText("📡 USB OBD")
            self.source_label.setStyleSheet(f"""
                background-color: {LiveDataTheme.INFO};
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
                font-weight: bold;
            """)
            logger.info("Data source switched to USB")

    def _refresh_data(self):
        """Manual refresh"""
        self._update_display()
        self.log_output.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] Manual refresh triggered")
    
    def _show_debug(self):
        """Show debug information"""
        if not self.connectivity:
            QMessageBox.information(self, "Debug", "No connectivity manager")
            return
        
        info = []
        info.append(f"Connected: {getattr(self.connectivity, 'connected', False)}")
        info.append(f"Latest data keys: {list((getattr(self.connectivity, 'latest_merged', {}) or {}).keys())}")
        
        QMessageBox.information(self, "Debug Info", "\n".join(info))
    
    def _log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_output.appendPlainText(f"[{timestamp}] {message}")

    # ================================
    # PUBLIC API FOR AI INTEGRATION
    # ================================

    def set_ai_attention_signals(self, signal_names: list, reasons: dict = None):
        """
        Set which signals the AI is currently paying attention to

        Args:
            signal_names: List of signal names (e.g., ['coolant_temp', 'rpm', 'voltage'])
            reasons: Optional dict mapping signal_name -> reason string

        Purpose: Highlights these signals in the PID table with tooltips
        """
        self.ai_attention_signals = set(s.lower() for s in signal_names)
        if reasons:
            self.ai_deviation_reasons = {k.lower(): v for k, v in reasons.items()}
        else:
            self.ai_deviation_reasons = {}

        logger.info(f"AI attention set to {len(signal_names)} signals: {signal_names}")

    def update_data_quality(self, data: dict):
        """
        Update data quality badge based on current data

        Args:
            data: Current OBD data dict

        Purpose: Shows data quality status to users
        """
        if not data:
            self.quality_badge.update_quality(0.0, 0.0, 0, 0, [])
            return

        # Compute sampling rate
        import time
        current_time = time.time()
        if self.last_update_time:
            time_diff = current_time - self.last_update_time
            if time_diff > 0:
                sampling_rate = 1.0 / time_diff
            else:
                sampling_rate = 0.0
        else:
            sampling_rate = 0.0

        self.last_update_time = current_time
        self.update_count += 1

        # Count available vs total expected signals
        expected_signals = ['rpm', 'speed', 'coolant_temp', 'intake_temp',
                           'battery_voltage', 'engine_load', 'throttle_pos',
                           'maf', 'fuel_level', 'fuel_pressure']

        available = 0
        missing = []
        for sig in expected_signals:
            if sig in data and data[sig] is not None:
                available += 1
            else:
                missing.append(sig.replace('_', ' ').title())

        total = len(expected_signals)
        quality_score = available / total if total > 0 else 0.0

        # Update badge
        self.quality_badge.update_quality(
            quality_score=quality_score,
            sampling_rate=sampling_rate,
            available=available,
            total=total,
            missing=missing
        )

    # ================================
    # MOBILE DATA FETCHING
    # ================================

    def _fetch_from_mobile(self):
        """Fetch live data from mobile app via server"""
        import requests
        import json

        self._log("Fetching live data from mobile...")

        # Get API key and profile ID from config
        try:
            api_keys_file = str(CONFIG.API_KEYS_FILE) if CONFIG else "./config/api_keys.json"
            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            if not api_keys:
                self._log("ERROR: No API keys configured")
                QMessageBox.warning(self, "No API Keys",
                    "No API keys configured. Generate an API key in the Server tab first.")
                return

            # Get the first (or currently selected) API key
            # In production, this should be configurable
            first_key_id = list(api_keys.keys())[0]
            key_data = api_keys[first_key_id]
            profile_id = key_data.get("profile_id")

            # We need to get the raw API key - check backup files
            api_key = self._get_raw_api_key(key_data.get("name", ""))
            if not api_key:
                self._log("ERROR: Could not find raw API key")
                QMessageBox.warning(self, "API Key Error",
                    "Could not find raw API key. The key backup file may be missing.")
                return

            # Fetch from server
            server_url = "https://predict.previlium.com"  # Or local: http://localhost:8000
            response = requests.get(
                f"{server_url}/api/live/latest/{profile_id}",
                headers={"X-API-Key": api_key},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    data = result.get("data", {})
                    age = result.get("age_seconds", 0)
                    self._log(f"SUCCESS: Got live data ({age:.1f}s old)")

                    # Update displays with fetched data
                    self._apply_mobile_data(data)
                    self.set_data_source('mobile_app')
                elif result.get("status") == "no_data":
                    self._log("No live data available - mobile app may not be streaming")
                    QMessageBox.information(self, "No Data",
                        "No live data available from mobile app.\n\n"
                        "Make sure the mobile app is:\n"
                        "1. Connected to OBD adapter\n"
                        "2. Streaming data to the server")
                elif result.get("status") == "stale":
                    self._log(f"WARNING: Data is stale - {result.get('message')}")
                    data = result.get("data", {})
                    self._apply_mobile_data(data)
            else:
                self._log(f"ERROR: Server returned {response.status_code}")

        except requests.exceptions.ConnectionError:
            self._log("ERROR: Could not connect to server")
            QMessageBox.warning(self, "Connection Error",
                "Could not connect to server.\n\n"
                "Make sure the server is running and accessible.")
        except Exception as e:
            self._log(f"ERROR: {str(e)}")
            logger.error(f"Error fetching mobile data: {e}")

    def _get_raw_api_key(self, key_name: str) -> Optional[str]:
        """Get raw API key from backup file"""
        import os

        # Use config path or fallback to legacy path
        if CONFIG:
            keys_folder = str(CONFIG.get_customer_api_keys_dir("default"))
        else:
            keys_folder = "C:/OBDserver/API_KEYS"

        # Also check legacy path if primary doesn't exist
        if not os.path.exists(keys_folder):
            keys_folder = str(CONFIG.get_customer_api_keys_dir("default")) if CONFIG else "api_keys"

        if not os.path.exists(keys_folder):
            return None

        # Try to find matching key file by name first
        target_filename = f"{key_name}_apikey.txt" if key_name else None

        for filename in os.listdir(keys_folder):
            if not filename.endswith("_apikey.txt"):
                continue

            # Prioritize exact match if key_name provided
            if target_filename and filename != target_filename:
                continue

            filepath = os.path.join(keys_folder, filename)
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Extract API key from file
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and len(line) == 9 and line.isalnum():
                            # Found a 9-char alphanumeric key
                            return line
            except:
                pass

        # If no match found with key_name, try any file
        if target_filename:
            for filename in os.listdir(keys_folder):
                if filename.endswith("_apikey.txt"):
                    filepath = os.path.join(keys_folder, filename)
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                            for line in content.split('\n'):
                                line = line.strip()
                                if line and len(line) == 9 and line.isalnum():
                                    return line
                    except:
                        pass

        return None

    def _apply_mobile_data(self, data: dict):
        """Apply fetched mobile data to displays"""
        if not data:
            return

        # Update gauges
        if data.get('rpm') is not None:
            self.rpm_gauge.set_value(float(data['rpm']), True)
            self.rpm_history.append(float(data['rpm']))
            self.rpm_spark.add_value(float(data['rpm']))

        if data.get('speed') is not None:
            self.speed_gauge.set_value(float(data['speed']), True)
            self.speed_history.append(float(data['speed']))
            self.speed_spark.add_value(float(data['speed']))

        if data.get('coolant_temp') is not None:
            self.coolant_gauge.set_value(float(data['coolant_temp']), True)
            self.temp_history.append(float(data['coolant_temp']))
            self.temp_spark.add_value(float(data['coolant_temp']))

        if data.get('battery_voltage') is not None:
            self.battery_gauge.set_value(float(data['battery_voltage']), True)

        # Update linear gauges
        if data.get('engine_load') is not None:
            self.load_gauge.set_value(float(data['engine_load']), True)

        if data.get('throttle_pos') is not None:
            self.throttle_gauge.set_value(float(data['throttle_pos']), True)

        if data.get('fuel_level') is not None:
            self.fuel_gauge.set_value(float(data['fuel_level']), True)

        # Update table
        self._update_table(data)

        # Update connectivity's latest_merged if available
        if self.connectivity:
            self.connectivity.latest_merged = data

    def _toggle_auto_fetch(self):
        """Toggle automatic fetching from mobile"""
        self.auto_fetch_enabled = not self.auto_fetch_enabled

        if self.auto_fetch_enabled:
            self.auto_fetch_btn.setText("🔄 Auto-Fetch: ON")
            self.auto_fetch_btn.setStyleSheet(self._get_button_style('success'))
            self._log("Auto-fetch enabled - fetching every 2 seconds")

            # Start auto-fetch timer
            if not hasattr(self, 'auto_fetch_timer'):
                self.auto_fetch_timer = QTimer(self)
                self.auto_fetch_timer.timeout.connect(self._fetch_from_mobile)
            self.auto_fetch_timer.start(2000)  # Fetch every 2 seconds
        else:
            self.auto_fetch_btn.setText("🔄 Auto-Fetch: OFF")
            self.auto_fetch_btn.setStyleSheet(self._get_button_style('secondary'))
            self._log("Auto-fetch disabled")

            # Stop auto-fetch timer
            if hasattr(self, 'auto_fetch_timer'):
                self.auto_fetch_timer.stop()
    
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
