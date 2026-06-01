"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Driving Score Tab
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPolygon

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from driving_score import DrivingScoreAnalyzer, get_driving_analyzer
    SCORE_SYSTEM_AVAILABLE = True
except ImportError:
    SCORE_SYSTEM_AVAILABLE = False
    DrivingScoreAnalyzer = None
    get_driving_analyzer = None

logger = logging.getLogger(__name__)


class ScoreGaugeWidget(QWidget):
    """Circular score gauge widget"""

    def __init__(self, score: int = 0, parent=None):
        super().__init__(parent)
        self.score = score
        self.setMinimumSize(200, 200)
        self._setup_ui()

    def _setup_ui(self):
        """Setup gauge UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        # Score label in center
        self.score_label = QLabel(str(self.score))
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setFont(QFont("Segoe UI", 36, QFont.Bold))
        self._update_score_color()
        layout.addWidget(self.score_label)

        # Score text below
        self.label = QLabel("Driving Score")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(self.label)

    def _update_score_color(self):
        """Update score color based on value"""
        if self.score >= 80:
            color = "#4CAF50"  # Green
        elif self.score >= 60:
            color = "#FFC107"  # Yellow
        else:
            color = "#F44336"  # Red

        self.score_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 36px;
                font-weight: bold;
            }}
        """)

    def set_score(self, score: int):
        """Update score value"""
        self.score = score
        self.score_label.setText(str(score))
        self._update_score_color()
        self.update()

    def paintEvent(self, event):
        """Custom paint for circular gauge"""
        from PySide6.QtGui import QPainter, QRadialGradient, QPen, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw outer circle
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(self.width(), self.height()) // 2 - 10

        # Background circle
        painter.setPen(QPen(QColor("#30363D"), 2))
        painter.setBrush(QColor("#161B22"))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Score arc
        start_angle = 135 * 16  # Start from top-left
        if self.score >= 80:
            arc_color = QColor("#4CAF50")
        elif self.score >= 60:
            arc_color = QColor("#FFC107")
        else:
            arc_color = QColor("#F44336")

        span_angle = int((self.score / 100) * 270)

        painter.setPen(QPen(arc_color, 15))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(center_x - radius, center_y - radius, radius * 2, radius * 2, start_angle, span_angle)

        painter.end()


class DrivingScoreTab(QWidget):
    """
    Driving Score Tab - Display driving behavior score and analysis
    """

    def __init__(self, score_system=None, parent=None):
        super().__init__(parent)

        # Initialize driving score analyzer backend
        if score_system:
            self.score_system = score_system
        elif SCORE_SYSTEM_AVAILABLE and get_driving_analyzer:
            try:
                self.score_system = get_driving_analyzer()
                logger.info("Driving score analyzer initialized")
            except Exception as e:
                logger.warning(f"Could not initialize DrivingScoreAnalyzer: {e}")
                self.score_system = None
        else:
            self.score_system = None
            logger.warning("Driving score system not available")

        self.trips = []
        self.profile_id = 1  # Default profile ID

        self._setup_ui()
        self._load_score_data()

    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with score gauge
        header = self._create_header()
        layout.addWidget(header)

        # Behavior breakdown cards
        behavior_layout = QHBoxLayout()
        behavior_layout.addWidget(self._create_behavior_card("Acceleration", 85, "acceleration"))
        behavior_layout.addWidget(self._create_behavior_card("Braking", 78, "braking"))
        behavior_layout.addWidget(self._create_behavior_card("Cornering", 72, "cornering"))
        behavior_layout.addWidget(self._create_behavior_card("Speeding", 65, "speeding"))
        layout.addLayout(behavior_layout)

        # Trip history table
        self.trip_table = QTableWidget()
        self.trip_table.setColumnCount(5)
        self.trip_table.setHorizontalHeaderLabels([
            "Date", "Distance", "Duration", "Score", "Actions"
        ])
        self._apply_table_style(self.trip_table)
        layout.addWidget(self.trip_table)

        # Tips for improvement
        tips_group = QGroupBox("Tips for Improvement")
        tips_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        tips_layout = QVBoxLayout(tips_group)

        tips = [
            "Accelerate smoothly to improve your acceleration score",
            "Maintain safe following distance to improve cornering",
            "Brake early and gradually to improve braking score",
            "Observe speed limits to reduce speeding incidents"
        ]

        for tip in tips:
            tip_label = QLabel(f"• {tip}")
            tip_label.setStyleSheet("color: #8B949E; font-size: 12px; padding: 4px;")
            tips_layout.addWidget(tip_label)

        layout.addWidget(tips_group)

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with score gauge"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Score gauge
        self.score_gauge = ScoreGaugeWidget()
        layout.addWidget(self.score_gauge)

        layout.addStretch()

        return widget

    def _create_behavior_card(self, title: str, score: int, attr_name: str) -> QFrame:
        """Create a behavior score card"""
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

        score_label = QLabel(str(score))
        score_label.setStyleSheet("color: #F0F6FC; font-size: 32px; font-weight: bold;")
        score_label.setObjectName(attr_name)
        setattr(self, f"{attr_name}_label", score_label)
        layout.addWidget(score_label)

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

    def _load_score_data(self):
        """Load real driving score data from backend"""
        try:
            if self.score_system:
                # Get current profile ID
                profile_id = self._get_current_profile_id()
                
                # Get current score
                current_score = self.score_system.get_current_score(profile_id)
                self.score_gauge.set_score(current_score.get('overall_score', 0))

                # Load trip history
                self.trips = self.score_system.get_trip_history(profile_id=profile_id, limit=20)
                logger.info(f"Loaded {len(self.trips)} trips")
            else:
                logger.warning("No score system available, using empty data")
                self.trips = []

        except Exception as e:
            logger.error(f"Error loading score data: {e}")
            self.trips = []

        self._update_trip_table()

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

    def update_with_obd_data(self, obd_data: dict):
        """Update driving score with real-time OBD data"""
        if not self.score_system:
            return

        try:
            profile_id = self._get_current_profile_id()
            profile_name = self._get_profile_name()
            
            # Process OBD data
            result = self.score_system.process_data_point(
                profile_id=profile_id,
                profile_name=profile_name,
                data=obd_data
            )
            
            # Update score gauge
            if 'driving_score' in result:
                self.score_gauge.set_score(result['driving_score'])
            
            # Update behavior breakdown
            if 'session_data' in result:
                session = result['session_data']
                self._update_behavior_indicators(session)

        except Exception as e:
            logger.error(f"Error updating with OBD data: {e}")

    def _update_behavior_indicators(self, session: dict):
        """Update behavior breakdown display"""
        behaviors = session.get('events', [])
        hard_brakes = sum(1 for e in behaviors if e.get('type') == 'harsh_brake')
        rapid_accels = sum(1 for e in behaviors if e.get('type') == 'rapid_acceleration')
        speeding_events = sum(1 for e in behaviors if e.get('type') == 'speeding')
        
        data_points = session.get('data_points', 1)
        
        if hasattr(self, 'acceleration_label'):
            self.acceleration_label.setText(str(85 - min(100, (rapid_accels / data_points * 100) if data_points > 0 else 0)))
        if hasattr(self, 'braking_label'):
            self.braking_label.setText(str(hard_brakes))
        if hasattr(self, 'cornering_label'):
            self.cornering_label.setText(str(72))  # Placeholder for cornering
        if hasattr(self, 'speeding_label'):
            speeding_pct = (speeding_events / data_points * 100) if data_points > 0 else 0
            self.speeding_label.setText(str(speeding_pct))

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

    def _update_trip_table(self):
        """Update trip history table"""
        self.trip_table.setRowCount(0)

        for trip in self.trips:
            row = self.trip_table.rowCount()
            self.trip_table.insertRow(row)

            self.trip_table.setItem(row, 0, QTableWidgetItem(trip.get('date', '')))
            self.trip_table.setItem(row, 1, QTableWidgetItem(f"{trip.get('distance', 0):.1f} mi"))
            self.trip_table.setItem(row, 2, QTableWidgetItem(trip.get('duration', '')))

            score = trip.get('score', 0)
            score_item = QTableWidgetItem(str(score))
            if score >= 80:
                score_item.setForeground(QColor("#4CAF50"))
            elif score >= 60:
                score_item.setForeground(QColor("#FFC107"))
            else:
                score_item.setForeground(QColor("#F44336"))
            self.trip_table.setItem(row, 3, score_item)

            # Add view button
            view_btn = QPushButton("View")
            view_btn.setStyleSheet("background-color: #C40000; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            self.trip_table.setCellWidget(row, 4, view_btn)

        self.trip_table.resizeColumnsToContents()
