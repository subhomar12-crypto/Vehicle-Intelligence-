"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Dashboard Widget

Dashboard Widget - Simple Home Screen for Predict OBD
Version: 5.0 - Live Data Connected
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from collections import deque

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush

from ui_common import show_info, ProfessionalTheme

logger = logging.getLogger(__name__)


class HealthScoreWidget(QWidget):
    """Circular health score with live data updates"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 50
        self.last_update = None
        self.setFixedSize(180, 180)

    def set_score(self, score: int):
        self.score = max(0, min(100, score))
        self.last_update = datetime.now()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Colors based on score
        if self.score >= 80:
            color = QColor("#4CAF50")
        elif self.score >= 60:
            color = QColor("#0DCAF0")
        elif self.score >= 40:
            color = QColor("#FFC107")
        else:
            color = QColor("#C40000")

        size = 160
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2

        # Background circle
        painter.setPen(QPen(QColor("#30363D"), 8))
        painter.setBrush(QBrush(QColor("#0D1117")))
        painter.drawEllipse(x, y, size, size)

        # Score arc
        painter.setPen(QPen(color, 8, Qt.SolidLine, Qt.RoundCap))
        span = int((self.score / 100) * 360 * 16)
        painter.drawArc(x + 4, y + 4, size - 8, size - 8, 90 * 16, -span)

        # Score text
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 36, QFont.Bold))
        painter.drawText(x, y, size, size, Qt.AlignCenter, str(self.score))

        # Last update indicator
        if self.last_update:
            time_str = self.last_update.strftime("%H:%M")
            painter.setPen(QColor("#8B949E"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(x, y + size + 5, 50, 20, Qt.AlignLeft, f"Updated: {time_str}")


class StatCard(QFrame):
    """Stat card with live data updates"""

    def __init__(self, title: str, value: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.unit = unit
        self.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
        """)
        self.setFixedHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10))
        title_label.setStyleSheet("color: #8B949E;")
        layout.addWidget(title_label)

        value_layout = QHBoxLayout()
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.value_label.setStyleSheet("color: #F0F6FC;")
        value_layout.addWidget(self.value_label)

        if unit:
            unit_label = QLabel(unit)
            unit_label.setFont(QFont("Segoe UI", 10))
            unit_label.setStyleSheet("color: #8B949E;")
            value_layout.addWidget(unit_label)

        layout.addLayout(value_layout)

    def update_value(self, value: str):
        self.value_label.setText(value)

    def set_color(self, color: str):
        """Set value color based on status"""
        self.value_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")


class LiveDataWidget(QWidget):
    """Live data display widget with real-time updates"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setStyleSheet("color: #8B949E; padding: 5px;")
        layout.addWidget(title_label)

        # Data display
        self.data_label = QLabel("--")
        self.data_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.data_label.setStyleSheet("color: #F0F6FC; padding: 10px;")
        self.data_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.data_label)

        # Progress bar for values with ranges
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 4px;
                text-align: center;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {ProfessionalTheme.PRIMARY};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)

    def update_data(self, value: Any, max_value: Optional[float] = None):
        """Update displayed data"""
        if value is None:
            self.data_label.setText("--")
            self.progress_bar.setValue(0)
            return

        # Format value
        if isinstance(value, float):
            self.data_label.setText(f"{value:.1f}")
            if max_value and max_value > 0:
                progress = min(100, (value / max_value) * 100)
                self.progress_bar.setValue(int(progress))
        else:
            self.data_label.setText(str(value))
            self.progress_bar.setValue(0)


class DashboardWidget(QWidget):
    """
    Enhanced Dashboard Widget with Live Data Integration
    
    Features:
    - Real-time health score updates
    - Live vehicle data display
    - Connection status tracking
    - Quick action buttons
    - Data quality indicator
    """

    connect_clicked = Signal()
    reports_clicked = Signal()
    training_clicked = Signal()
    settings_clicked = Signal()
    data_updated = Signal(str, object)  # category, data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.live_data = {}
        self.data_sources = {}
        self._setup_ui()
        self._start_update_timer()
        logger.info("DashboardWidget: Initialized with live data support")

    def _setup_ui(self):
        self.setStyleSheet("background-color: #0D1117;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; }
            QScrollBar:vertical { width: 8px; background: #0D1117; }
            QScrollBar::handle:vertical { background: #30363D; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # Header
        header = QLabel("Dashboard")
        header.setFont(QFont("Segoe UI", 24, QFont.Bold))
        header.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(header)

        # Health score card
        health_card = QFrame()
        health_card.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
        """)
        health_card.setFixedWidth(260)

        health_layout = QVBoxLayout(health_card)
        health_layout.setContentsMargins(20, 16, 20, 16)
        health_layout.setSpacing(8)

        health_title = QLabel("Vehicle Health")
        health_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        health_title.setStyleSheet("color: #F0F6FC;")
        health_title.setAlignment(Qt.AlignCenter)
        health_layout.addWidget(health_title)

        self.health_score = HealthScoreWidget()
        health_layout.addWidget(self.health_score, 0, Qt.AlignCenter)

        layout.addWidget(health_card)

        # Stats grid
        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)

        # Connection status
        self.stat_connection = StatCard("Connection", "Disconnected")
        stats_grid.addWidget(self.stat_connection, 0, 0)

        # Data quality
        self.stat_quality = StatCard("Data Quality", "--%")
        stats_grid.addWidget(self.stat_quality, 1, 0)

        # Alerts count
        self.stat_alerts = StatCard("Active Alerts", "0")
        stats_grid.addWidget(self.stat_alerts, 0, 1)

        # Distance driven
        self.stat_distance = StatCard("Distance", "0 km")
        stats_grid.addWidget(self.stat_distance, 1, 1)

        # Session duration
        self.stat_duration = StatCard("Session Time", "0:00")
        stats_grid.addWidget(self.stat_duration, 0, 2)

        # AI predictions
        self.stat_predictions = StatCard("AI Predictions", "0")
        stats_grid.addWidget(self.stat_predictions, 1, 2)

        layout.addLayout(stats_grid)

        # Live data section
        live_data_label = QLabel("Live Vehicle Data")
        live_data_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        live_data_label.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(live_data_label)

        # Live data grid
        live_grid = QGridLayout()
        live_grid.setSpacing(12)

        # RPM
        self.live_rpm = LiveDataWidget("RPM")
        live_grid.addWidget(self.live_rpm, 0, 0)

        # Speed
        self.live_speed = LiveDataWidget("Speed")
        live_grid.addWidget(self.live_speed, 1, 0)

        # Coolant Temp
        self.live_coolant = LiveDataWidget("Coolant Temp")
        live_grid.addWidget(self.live_coolant, 2, 0)

        # Battery Voltage
        self.live_battery = LiveDataWidget("Battery")
        live_grid.addWidget(self.live_battery, 0, 1)

        # Engine Load
        self.live_load = LiveDataWidget("Engine Load")
        live_grid.addWidget(self.live_load, 1, 1)

        # Throttle
        self.live_throttle = LiveDataWidget("Throttle")
        live_grid.addWidget(self.live_throttle, 2, 1)

        layout.addLayout(live_grid)

        # Quick actions
        actions_label = QLabel("Quick Actions")
        actions_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        actions_label.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(actions_label)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        # Button styles
        self.btn_primary_style = """
            QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #A00000; }
                QPushButton:disabled { background-color: #30363D; color: #8B949E; }
        """

        self.btn_secondary_style = """
            QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #30363D; }
                QPushButton:pressed { background-color: #161B22; }
                QPushButton:disabled { background-color: #161B22; color: #484F58; }
        """

        self.btn_success_style = """
            QPushButton {
                    background-color: #4CAF50;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #66BB6A; }
                QPushButton:pressed { background-color: #388E3C; }
            """

        btn_connect = QPushButton("🔌 Connect Vehicle")
        btn_connect.setStyleSheet(self.btn_success_style)
        btn_connect.clicked.connect(self.connect_clicked.emit)
        actions_row.addWidget(btn_connect)

        btn_reports = QPushButton("📊 Reports")
        btn_reports.setStyleSheet(self.btn_secondary_style)
        btn_reports.clicked.connect(self.reports_clicked.emit)
        actions_row.addWidget(btn_reports)

        btn_training = QPushButton("🧠 AI Training")
        btn_training.setStyleSheet(self.btn_secondary_style)
        btn_training.clicked.connect(self.training_clicked.emit)
        actions_row.addWidget(btn_training)

        btn_analytics = QPushButton("📈 Analytics")
        btn_analytics.setStyleSheet(self.btn_secondary_style)
        btn_analytics.clicked.connect(lambda: self.data_updated.emit("navigate", "analytics"))
        actions_row.addWidget(btn_analytics)

        btn_settings = QPushButton("⚙️ Settings")
        btn_settings.setStyleSheet(self.btn_secondary_style)
        btn_settings.clicked.connect(self.settings_clicked.emit)
        actions_row.addWidget(btn_settings)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _start_update_timer(self):
        """Start timer for periodic data refresh"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_live_data)
        self.update_timer.start(1000)  # Update every second

    def register_data_source(self, category: str, get_data_func):
        """Register a data source for live updates"""
        self.data_sources[category] = get_data_func
        logger.info(f"DashboardWidget: Registered data source for category '{category}'")

    def _refresh_live_data(self):
        """Refresh live data from all registered sources"""
        for category, get_data_func in self.data_sources.items():
            try:
                data = get_data_func()
                if data:
                    self.live_data[category] = data
                    self._update_display(category, data)
            except Exception as e:
                logger.error(f"Error refreshing data for '{category}': {e}")

    def _update_display(self, category: str, data: Dict[str, Any]):
        """Update display based on data category"""
        if category == 'connection':
            connected = data.get('connected', False)
            self.stat_connection.update_value("Connected" if connected else "Disconnected")
            if connected:
                self.stat_connection.set_color("#4CAF50")
            else:
                self.stat_connection.set_color("#F44336")

        elif category == 'data_quality':
            quality = data.get('quality', 0)
            self.stat_quality.update_value(f"{quality:.0f}%")
            if quality >= 90:
                self.stat_quality.set_color("#4CAF50")
            elif quality >= 70:
                self.stat_quality.set_color("#FFC107")
            else:
                self.stat_quality.set_color("#F44336")

        elif category == 'alerts':
            count = data.get('count', 0)
            self.stat_alerts.update_value(str(count))

        elif category == 'distance':
            distance = data.get('distance', 0)
            self.stat_distance.update_value(f"{distance:.1f} km")

        elif category == 'session_duration':
            duration = data.get('duration', 0)
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            self.stat_duration.update_value(f"{minutes:02d}:{seconds:02d}")

        elif category == 'predictions':
            predictions = data.get('predictions', 0)
            self.stat_predictions.update_value(str(predictions))

        elif category == 'obd_data':
            # Update live OBD displays
            rpm = data.get('rpm')
            speed = data.get('speed')
            coolant = data.get('coolant_temp')
            battery = data.get('battery_voltage')
            load = data.get('engine_load')
            throttle = data.get('throttle_pos')

            self.live_rpm.update_data(rpm, max_value=7000)
            self.live_speed.update_data(speed, max_value=250)
            self.live_coolant.update_data(coolant, max_value=120)
            self.live_battery.update_data(battery, max_value=15)
            self.live_load.update_data(load, max_value=100)
            self.live_throttle.update_data(throttle, max_value=100)

        elif category == 'health_score':
            score = data.get('score', 50)
            self.health_score.set_score(int(score))

    def update_health_score(self, score: int):
        """Update health score display"""
        self.health_score.set_score(score)

    def update_connection_status(self, connected: bool):
        """Update connection status display"""
        self.stat_connection.update_value("Connected" if connected else "Disconnected")
        if connected:
            self.stat_connection.set_color("#4CAF50")
        else:
            self.stat_connection.set_color("#F44336")

    def update_alerts_count(self, count: int):
        """Update alerts count display"""
        self.stat_alerts.update_value(str(count))

    def update_distance(self, km: float):
        """Update distance display"""
        self.stat_distance.update_value(f"{km:.1f} km")

    def update_live_snapshot(self, snapshot: Dict[str, Any]):
        """Update all live data displays from OBD snapshot"""
        if not snapshot:
            return

        self.live_data['obd_data'] = snapshot
        self._update_display('obd_data', snapshot)

    def set_data_quality(self, quality: float):
        """Set data quality indicator"""
        self.stat_quality.update_value(f"{quality:.0f}%")
        if quality >= 90:
            self.stat_quality.set_color("#4CAF50")
        elif quality >= 70:
            self.stat_quality.set_color("#FFC107")
        else:
            self.stat_quality.set_color("#F44336")

    def update_predictions_count(self, count: int):
        """Update AI predictions count"""
        self.stat_predictions.update_value(str(count))

    def update_session_time(self, seconds: int):
        """Update session duration display"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        self.stat_duration.update_value(f"{minutes:02d}:{secs:02d}")

    def refresh_all_data(self):
        """Force refresh all data sources"""
        self._refresh_live_data()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = DashboardWidget()
    widget.setWindowTitle("PREDICT - Dashboard Widget (Test)")
    widget.resize(1200, 900)
    widget.show()

    sys.exit(app.exec())
