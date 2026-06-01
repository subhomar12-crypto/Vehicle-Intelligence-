"""
Live Data tab for real-time OBD sensor display.

Shows live sensor readings with color-coded value indicators.
"""

import logging
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class SensorGauge(QFrame):
    """Individual sensor gauge widget."""
    
    def __init__(self, name: str, unit: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.name = name
        self.unit = unit
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup gauge UI."""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {PredictTheme.BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        self.setMinimumSize(150, 100)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Sensor name with anomaly dot
        header_layout = QHBoxLayout()
        self.name_label = QLabel(self.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 10)
        self.name_label.setFont(font)
        header_layout.addWidget(self.name_label)
        
        # Anomaly dot
        self._anomaly_dot = QLabel("●")
        self._anomaly_dot.setStyleSheet("color: transparent; font-size: 12px;")
        self._anomaly_dot.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self._anomaly_dot)
        layout.addLayout(header_layout)
        
        # Value
        self.value_label = QLabel("--")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 24, QFont.Weight.Bold)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)
        
        # Unit
        self.unit_label = QLabel(self.unit)
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_label.setStyleSheet(f"color: {PredictTheme.TEXT_MUTED};")
        font = QFont(PredictTheme.FONT_FAMILY, 9)
        self.unit_label.setFont(font)
        layout.addWidget(self.unit_label)
        
        # Baseline label
        self._baseline_label = QLabel("baseline: --")
        self._baseline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._baseline_label.setStyleSheet(f"color: {PredictTheme.TEXT_MUTED}; font-size: 10px;")
        font = QFont(PredictTheme.FONT_FAMILY, 9)
        self._baseline_label.setFont(font)
        layout.addWidget(self._baseline_label)
    
    def update_value(self, value: float, color: Optional[str] = None) -> None:
        """Update displayed value with optional color."""
        if isinstance(value, float):
            display_value = f"{value:.1f}"
        else:
            display_value = str(value)
        
        self.value_label.setText(display_value)
        
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        else:
            self.value_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
    
    def set_baseline(self, baseline_value: float, current_value: float, unit: str = "") -> None:
        """Update baseline comparison label."""
        if baseline_value is not None:
            delta = current_value - baseline_value
            sign = "+" if delta >= 0 else ""
            self._baseline_label.setText(f"baseline: {baseline_value:.1f}{unit}  Δ{sign}{delta:.1f}")
            if baseline_value != 0 and abs(delta) > abs(baseline_value) * 0.15:  # >15% deviation
                self._baseline_label.setStyleSheet(f"color: {PredictTheme.WARNING}; font-size: 10px;")
            else:
                self._baseline_label.setStyleSheet(f"color: {PredictTheme.TEXT_MUTED}; font-size: 10px;")
    
    def set_anomaly(self, is_anomaly: bool, severity: str = "warning") -> None:
        """Set anomaly indicator visibility and color."""
        color = PredictTheme.DANGER if severity == "critical" else PredictTheme.WARNING
        self._anomaly_dot.setStyleSheet(f"color: {color if is_anomaly else 'transparent'}; font-size: 12px;")


class LiveDataTab(QWidget):
    """
    Tab for displaying real-time OBD sensor data.
    
    Shows sensor gauges for RPM, Speed, Coolant Temp, Battery Voltage,
    Engine Load, Intake Temp, MAF, and Throttle Position.
    """
    
    # Sensor thresholds (normal, warning, critical)
    THRESHOLDS = {
        "RPM": {
            "normal": (600, 4000),
            "warning": (4000, 5500),
            "critical": (5500, 8000),
        },
        "Speed": {
            "normal": (0, 120),
            "warning": (120, 150),
            "critical": (150, 300),
        },
        "Coolant Temp": {
            "normal": (80, 100),
            "warning": (100, 110),
            "critical": (110, 150),
        },
        "Battery Voltage": {
            "normal": (13.0, 14.8),
            "warning": (12.0, 13.0),
            "critical": (0, 12.0),
        },
        "Engine Load": {
            "normal": (0, 75),
            "warning": (75, 90),
            "critical": (90, 100),
        },
        "Intake Temp": {
            "normal": (10, 60),
            "warning": (60, 80),
            "critical": (80, 150),
        },
        "MAF": {
            "normal": (2, 30),
            "warning": (30, 50),
            "critical": (50, 100),
        },
        "Throttle Position": {
            "normal": (0, 80),
            "warning": (80, 95),
            "critical": (95, 100),
        },
    }
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_timer()
        self._sensor_data: Dict[str, float] = {}
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Live OBD Data")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Driving context indicator
        context_layout = QHBoxLayout()
        self._driving_mode_label = QLabel("Mode: --")
        self._driving_mode_label.setStyleSheet(f"font-weight: bold; color: {PredictTheme.INFO}; font-size: 13px;")
        context_layout.addWidget(self._driving_mode_label)
        context_layout.addStretch()
        layout.addLayout(context_layout)
        
        # Scroll area for gauges
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Gauges container
        container = QWidget()
        gauges_layout = QGridLayout(container)
        gauges_layout.setSpacing(15)
        
        # Create sensor gauges
        self.gauges: Dict[str, SensorGauge] = {}
        
        sensors = [
            ("RPM", "rpm", 0, 0),
            ("Speed", "km/h", 0, 1),
            ("Coolant Temp", "°C", 0, 2),
            ("Battery Voltage", "V", 0, 3),
            ("Engine Load", "%", 1, 0),
            ("Intake Temp", "°C", 1, 1),
            ("MAF", "g/s", 1, 2),
            ("Throttle Position", "%", 1, 3),
        ]
        
        for name, unit, row, col in sensors:
            gauge = SensorGauge(name, unit)
            self.gauges[name] = gauge
            gauges_layout.addWidget(gauge, row, col)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # Status bar
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet(f"color: {PredictTheme.DANGER};")
        layout.addWidget(self.status_label)
    
    def _setup_timer(self) -> None:
        """Setup refresh timer."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_data)
        self.timer.start(1000)  # 1 second interval
    
    def _update_data(self) -> None:
        """Fetch and update sensor data."""
        # TODO: Connect to actual OBD service
        # For now, use placeholder data
        self._sensor_data = {
            "RPM": 850,
            "Speed": 0,
            "Coolant Temp": 92,
            "Battery Voltage": 14.2,
            "Engine Load": 15,
            "Intake Temp": 35,
            "MAF": 4.5,
            "Throttle Position": 8,
        }
        
        for name, value in self._sensor_data.items():
            if name in self.gauges:
                color = self._get_value_color(name, value)
                self.gauges[name].update_value(value, color)
        
        self.status_label.setText("Connected - Last update: now")
        self.status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS};")
    
    def _get_value_color(self, sensor: str, value: float) -> str:
        """
        Get color for sensor value based on thresholds.
        
        Args:
            sensor: Sensor name
            value: Current value
        
        Returns:
            Hex color code
        """
        if sensor not in self.THRESHOLDS:
            return PredictTheme.TEXT_PRIMARY
        
        thresholds = self.THRESHOLDS[sensor]
        
        # Check critical first
        crit_min, crit_max = thresholds["critical"]
        if value <= crit_min or value >= crit_max:
            return PredictTheme.DANGER
        
        # Check warning
        warn_min, warn_max = thresholds["warning"]
        if value <= warn_min or value >= warn_max:
            return PredictTheme.WARNING
        
        # Normal
        return PredictTheme.SUCCESS
    
    def set_connected(self, connected: bool) -> None:
        """Set connection status."""
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS};")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet(f"color: {PredictTheme.DANGER};")
    
    def set_driving_context(self, mode: str, confidence: Optional[float] = None) -> None:
        """Update driving context indicator."""
        text = f"Mode: {mode.title()}"
        if confidence is not None:
            text += f" ({int(confidence * 100)}%)"
        self._driving_mode_label.setText(text)
    
    def update_sensor_data(self, data: Dict[str, float]) -> None:
        """Update sensor data from external source."""
        self._sensor_data.update(data)
        for name, value in data.items():
            if name in self.gauges:
                color = self._get_value_color(name, value)
                self.gauges[name].update_value(value, color)
