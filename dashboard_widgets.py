"""
Dashboard Widgets
Custom widgets for the enhanced Dashboard showing AI status, predictions, notifications, and export.

Part of the PREDICT Vehicle Intelligence Platform.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QScrollArea, QGridLayout, QFileDialog,
    QGroupBox, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CardWidget(QFrame):
    """Base card widget with shadow and rounded corners"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("CardWidget")
        self.setStyleSheet("""
            #CardWidget {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title_label.setStyleSheet("color: #333;")
            self.main_layout.addWidget(title_label)

    def add_widget(self, widget: QWidget):
        """Add a widget to the card"""
        self.main_layout.addWidget(widget)


class AIStatusWidget(CardWidget):
    """
    Widget showing AI model training status.

    Displays:
    - Last training time
    - Model accuracy
    - Training data statistics
    - Next scheduled training
    """

    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("AI Model Status", parent)

        # Status indicators
        self.status_grid = QGridLayout()
        self.status_grid.setSpacing(15)

        # Last training time
        self.last_training_label = QLabel("Last Training:")
        self.last_training_label.setStyleSheet("color: #666;")
        self.last_training_value = QLabel("Loading...")
        self.last_training_value.setStyleSheet("color: #333; font-weight: bold;")
        self.status_grid.addWidget(self.last_training_label, 0, 0)
        self.status_grid.addWidget(self.last_training_value, 0, 1)

        # Model accuracy
        self.accuracy_label = QLabel("Model Accuracy:")
        self.accuracy_label.setStyleSheet("color: #666;")
        self.accuracy_value = QLabel("--")
        self.accuracy_value.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 16px;")
        self.status_grid.addWidget(self.accuracy_label, 1, 0)
        self.status_grid.addWidget(self.accuracy_value, 1, 1)

        # Data points
        self.data_points_label = QLabel("Training Data Points:")
        self.data_points_label.setStyleSheet("color: #666;")
        self.data_points_value = QLabel("--")
        self.data_points_value.setStyleSheet("color: #333; font-weight: bold;")
        self.status_grid.addWidget(self.data_points_label, 2, 0)
        self.status_grid.addWidget(self.data_points_value, 2, 1)

        # Active models
        self.models_label = QLabel("Active Models:")
        self.models_label.setStyleSheet("color: #666;")
        self.models_value = QLabel("--")
        self.models_value.setStyleSheet("color: #333; font-weight: bold;")
        self.status_grid.addWidget(self.models_label, 3, 0)
        self.status_grid.addWidget(self.models_value, 3, 1)

        # Next training
        self.next_training_label = QLabel("Next Training:")
        self.next_training_label.setStyleSheet("color: #666;")
        self.next_training_value = QLabel("--")
        self.next_training_value.setStyleSheet("color: #1a73e8; font-weight: bold;")
        self.status_grid.addWidget(self.next_training_label, 4, 0)
        self.status_grid.addWidget(self.next_training_value, 4, 1)

        self.main_layout.addLayout(self.status_grid)

        # Progress bar for learning progress
        self.progress_label = QLabel("Learning Progress")
        self.progress_label.setStyleSheet("color: #666; margin-top: 10px;")
        self.main_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: #e0e0e0;
                height: 10px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: linear-gradient(90deg, #1a73e8, #4caf50);
                border-radius: 5px;
            }
        """)
        self.main_layout.addWidget(self.progress_bar)

        # Refresh button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        button_layout.addWidget(self.refresh_btn)

        self.main_layout.addLayout(button_layout)

        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_requested.emit)
        self.refresh_timer.start(60000)  # Refresh every minute

    def update_status(self, status: Dict[str, Any]):
        """Update the display with new status data"""
        # Last training
        last_training = status.get("last_training_time")
        if last_training:
            try:
                dt = datetime.fromisoformat(last_training)
                time_ago = self._format_time_ago(dt)
                self.last_training_value.setText(time_ago)
            except:
                self.last_training_value.setText(str(last_training))
        else:
            self.last_training_value.setText("Never")

        # Accuracy
        accuracy = status.get("accuracy")
        if accuracy is not None:
            self.accuracy_value.setText(f"{accuracy:.1%}")
            if accuracy >= 0.9:
                self.accuracy_value.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 16px;")
            elif accuracy >= 0.7:
                self.accuracy_value.setStyleSheet("color: #ff9800; font-weight: bold; font-size: 16px;")
            else:
                self.accuracy_value.setStyleSheet("color: #f44336; font-weight: bold; font-size: 16px;")
        else:
            self.accuracy_value.setText("N/A")

        # Data points
        data_points = status.get("total_data_points", 0)
        self.data_points_value.setText(f"{data_points:,}")

        # Models
        models_count = status.get("models_count", 0)
        self.models_value.setText(str(models_count))

        # Next training
        next_training = status.get("next_training")
        if next_training:
            try:
                dt = datetime.fromisoformat(next_training)
                self.next_training_value.setText(dt.strftime("%Y-%m-%d %H:%M"))
            except:
                self.next_training_value.setText(str(next_training))
        else:
            self.next_training_value.setText("Not scheduled")

        # Progress (based on data accumulation toward next training threshold)
        progress = status.get("training_progress", 0)
        self.progress_bar.setValue(int(progress * 100))

    def _format_time_ago(self, dt: datetime) -> str:
        """Format a datetime as 'X hours/days ago'"""
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"


class PredictionsSummaryWidget(CardWidget):
    """
    Widget showing recent predictions summary.

    Displays:
    - Critical predictions count
    - Recent high-risk items
    - Trend indicators
    """

    view_all_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Predictions Summary", parent)

        # Summary stats in a row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        # Critical count
        self.critical_box = self._create_stat_box("Critical", "0", "#f44336")
        stats_layout.addWidget(self.critical_box)

        # High count
        self.high_box = self._create_stat_box("High Risk", "0", "#ff9800")
        stats_layout.addWidget(self.high_box)

        # Medium count
        self.medium_box = self._create_stat_box("Medium", "0", "#2196f3")
        stats_layout.addWidget(self.medium_box)

        # Low count
        self.low_box = self._create_stat_box("Low", "0", "#4caf50")
        stats_layout.addWidget(self.low_box)

        self.main_layout.addLayout(stats_layout)

        # Recent predictions list
        self.predictions_label = QLabel("Recent High-Risk Predictions")
        self.predictions_label.setStyleSheet("color: #666; font-weight: bold; margin-top: 10px;")
        self.main_layout.addWidget(self.predictions_label)

        self.predictions_list = QVBoxLayout()
        self.predictions_list.setSpacing(8)
        self.main_layout.addLayout(self.predictions_list)

        # View all button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.view_all_btn = QPushButton("View All Predictions")
        self.view_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1a73e8;
                border: 1px solid #1a73e8;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.view_all_btn.clicked.connect(self.view_all_clicked.emit)
        button_layout.addWidget(self.view_all_btn)

        self.main_layout.addLayout(button_layout)

    def _create_stat_box(self, label: str, value: str, color: str) -> QFrame:
        """Create a stat display box"""
        box = QFrame()
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {color}15;
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        value_label = QLabel(value)
        value_label.setObjectName(f"value_{label}")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)

        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(text_label)

        return box

    def update_predictions(self, data: Dict[str, Any]):
        """Update predictions display"""
        # Update counts
        counts = data.get("counts", {})

        critical_label = self.critical_box.findChild(QLabel, "value_Critical")
        if critical_label:
            critical_label.setText(str(counts.get("critical", 0)))

        high_label = self.high_box.findChild(QLabel, "value_High Risk")
        if high_label:
            high_label.setText(str(counts.get("high", 0)))

        medium_label = self.medium_box.findChild(QLabel, "value_Medium")
        if medium_label:
            medium_label.setText(str(counts.get("medium", 0)))

        low_label = self.low_box.findChild(QLabel, "value_Low")
        if low_label:
            low_label.setText(str(counts.get("low", 0)))

        # Update predictions list
        self._clear_predictions_list()

        recent = data.get("recent_high_risk", [])
        for pred in recent[:5]:
            self._add_prediction_item(pred)

        if not recent:
            no_data = QLabel("No high-risk predictions")
            no_data.setStyleSheet("color: #999; font-style: italic;")
            self.predictions_list.addWidget(no_data)

    def _clear_predictions_list(self):
        """Clear the predictions list"""
        while self.predictions_list.count():
            item = self.predictions_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_prediction_item(self, pred: Dict[str, Any]):
        """Add a prediction item to the list"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background-color: #fff3e0;
                border-left: 3px solid #ff9800;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        layout = QHBoxLayout(item)
        layout.setContentsMargins(10, 8, 10, 8)

        # Vehicle and component
        text = QLabel(f"{pred.get('vehicle_name', 'Unknown')} - {pred.get('component', 'Unknown')}")
        text.setStyleSheet("color: #333; font-weight: bold;")
        layout.addWidget(text)

        layout.addStretch()

        # Risk level
        risk = pred.get('risk_level', 0)
        risk_label = QLabel(f"{risk:.0%}")
        risk_label.setStyleSheet("color: #ff9800; font-weight: bold; font-size: 14px;")
        layout.addWidget(risk_label)

        self.predictions_list.addWidget(item)


class NotificationsCenterWidget(CardWidget):
    """
    Widget showing recent notifications center.

    Displays:
    - Unread notifications count
    - Recent notifications list
    - Quick actions
    """

    view_all_clicked = Signal()
    notification_clicked = Signal(str)  # notification_id

    def __init__(self, parent=None):
        super().__init__("Notifications Center", parent)

        # Unread badge
        header_layout = QHBoxLayout()

        self.unread_badge = QLabel("0 unread")
        self.unread_badge.setStyleSheet("""
            background-color: #f44336;
            color: white;
            border-radius: 10px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.unread_badge)
        header_layout.addStretch()

        self.mark_all_read_btn = QPushButton("Mark All Read")
        self.mark_all_read_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1a73e8;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        header_layout.addWidget(self.mark_all_read_btn)

        self.main_layout.addLayout(header_layout)

        # Notifications list
        self.notifications_scroll = QScrollArea()
        self.notifications_scroll.setWidgetResizable(True)
        self.notifications_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        self.notifications_scroll.setMaximumHeight(300)

        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setContentsMargins(0, 0, 0, 0)
        self.notifications_layout.setSpacing(8)

        self.notifications_scroll.setWidget(self.notifications_container)
        self.main_layout.addWidget(self.notifications_scroll)

        # View all button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.view_all_btn = QPushButton("View All Notifications")
        self.view_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1a73e8;
                border: 1px solid #1a73e8;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.view_all_btn.clicked.connect(self.view_all_clicked.emit)
        button_layout.addWidget(self.view_all_btn)

        self.main_layout.addLayout(button_layout)

    def update_notifications(self, notifications: List[Dict[str, Any]], unread_count: int = 0):
        """Update notifications display"""
        # Update badge
        if unread_count > 0:
            self.unread_badge.setText(f"{unread_count} unread")
            self.unread_badge.setStyleSheet("""
                background-color: #f44336;
                color: white;
                border-radius: 10px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            """)
        else:
            self.unread_badge.setText("All read")
            self.unread_badge.setStyleSheet("""
                background-color: #4caf50;
                color: white;
                border-radius: 10px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            """)

        # Clear existing
        while self.notifications_layout.count():
            item = self.notifications_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add notifications
        for notif in notifications[:10]:
            self._add_notification_item(notif)

        if not notifications:
            no_data = QLabel("No notifications")
            no_data.setStyleSheet("color: #999; font-style: italic; padding: 20px;")
            no_data.setAlignment(Qt.AlignCenter)
            self.notifications_layout.addWidget(no_data)

        self.notifications_layout.addStretch()

    def _add_notification_item(self, notif: Dict[str, Any]):
        """Add a notification item"""
        item = QFrame()
        is_read = notif.get("read", False)

        item.setStyleSheet(f"""
            QFrame {{
                background-color: {'#fff' if is_read else '#e3f2fd'};
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
            }}
            QFrame:hover {{
                background-color: #f5f5f5;
            }}
        """)
        item.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(item)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Title row
        title_layout = QHBoxLayout()

        priority = notif.get("priority", "medium")
        priority_colors = {
            "critical": "#f44336",
            "high": "#ff9800",
            "medium": "#2196f3",
            "low": "#4caf50"
        }
        priority_dot = QLabel("●")
        priority_dot.setStyleSheet(f"color: {priority_colors.get(priority, '#999')};")
        title_layout.addWidget(priority_dot)

        title = QLabel(notif.get("title", "Notification"))
        title.setStyleSheet("color: #333; font-weight: bold;")
        title_layout.addWidget(title)

        title_layout.addStretch()

        # Time
        sent_at = notif.get("sent_at")
        if sent_at:
            try:
                dt = datetime.fromisoformat(sent_at)
                time_str = dt.strftime("%H:%M")
            except:
                time_str = ""
            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: #999; font-size: 11px;")
            title_layout.addWidget(time_label)

        layout.addLayout(title_layout)

        # Message preview
        message = notif.get("message", "")
        if len(message) > 80:
            message = message[:80] + "..."
        message_label = QLabel(message)
        message_label.setStyleSheet("color: #666; font-size: 12px;")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Make clickable
        notif_id = notif.get("notification_id")
        if notif_id:
            item.mousePressEvent = lambda e, nid=notif_id: self.notification_clicked.emit(nid)

        self.notifications_layout.addWidget(item)


class DataExportWidget(CardWidget):
    """
    Widget for exporting collected data.

    Provides:
    - Export options (CSV, JSON, PDF)
    - Date range selection
    - Data type selection
    """

    export_requested = Signal(dict)  # Export options

    def __init__(self, parent=None):
        super().__init__("Export Data", parent)

        # Export info
        info_label = QLabel(
            "Export your vehicle data, predictions, and reports for analysis or backup."
        )
        info_label.setStyleSheet("color: #666;")
        info_label.setWordWrap(True)
        self.main_layout.addWidget(info_label)

        # Export buttons
        buttons_layout = QGridLayout()
        buttons_layout.setSpacing(10)

        # CSV Export
        self.csv_btn = self._create_export_button(
            "Export CSV",
            "Vehicle data and predictions",
            "#4caf50"
        )
        self.csv_btn.clicked.connect(lambda: self._request_export("csv"))
        buttons_layout.addWidget(self.csv_btn, 0, 0)

        # JSON Export
        self.json_btn = self._create_export_button(
            "Export JSON",
            "Full data with metadata",
            "#2196f3"
        )
        self.json_btn.clicked.connect(lambda: self._request_export("json"))
        buttons_layout.addWidget(self.json_btn, 0, 1)

        # PDF Report
        self.pdf_btn = self._create_export_button(
            "Generate Report",
            "PDF summary report",
            "#9c27b0"
        )
        self.pdf_btn.clicked.connect(lambda: self._request_export("pdf"))
        buttons_layout.addWidget(self.pdf_btn, 1, 0)

        # Excel Export
        self.excel_btn = self._create_export_button(
            "Export Excel",
            "Spreadsheet format",
            "#ff9800"
        )
        self.excel_btn.clicked.connect(lambda: self._request_export("excel"))
        buttons_layout.addWidget(self.excel_btn, 1, 1)

        self.main_layout.addLayout(buttons_layout)

        # Last export info
        self.last_export_label = QLabel("Last export: Never")
        self.last_export_label.setStyleSheet("color: #999; font-size: 11px; margin-top: 10px;")
        self.main_layout.addWidget(self.last_export_label)

    def _create_export_button(self, text: str, subtitle: str, color: str) -> QPushButton:
        """Create an export button with subtitle"""
        btn = QPushButton()
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """)
        btn.setMinimumHeight(70)

        # Custom layout for button content
        layout = QVBoxLayout(btn)
        layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel(text)
        title.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        sub = QLabel(subtitle)
        sub.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
        layout.addWidget(sub)

        return btn

    def _request_export(self, format_type: str):
        """Request an export"""
        self.export_requested.emit({
            "format": format_type,
            "timestamp": datetime.now().isoformat()
        })

    def update_last_export(self, timestamp: str):
        """Update last export timestamp"""
        try:
            dt = datetime.fromisoformat(timestamp)
            self.last_export_label.setText(f"Last export: {dt.strftime('%Y-%m-%d %H:%M')}")
        except:
            self.last_export_label.setText(f"Last export: {timestamp}")


class EnhancedDashboard(QWidget):
    """
    Enhanced Dashboard widget combining all dashboard components.

    Layout:
    - Top: AI Status + Predictions Summary
    - Middle: Notifications Center
    - Bottom: Data Export
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Setup the dashboard UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Welcome header
        header = QLabel("Dashboard")
        header.setFont(QFont("Segoe UI", 24, QFont.Bold))
        header.setStyleSheet("color: #333;")
        main_layout.addWidget(header)

        # Top row: AI Status + Predictions
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        self.ai_status = AIStatusWidget()
        self.ai_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_row.addWidget(self.ai_status, 1)

        self.predictions = PredictionsSummaryWidget()
        self.predictions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_row.addWidget(self.predictions, 1)

        main_layout.addLayout(top_row)

        # Middle: Notifications
        self.notifications = NotificationsCenterWidget()
        main_layout.addWidget(self.notifications)

        # Bottom: Export
        self.export = DataExportWidget()
        main_layout.addWidget(self.export)

        main_layout.addStretch()

    def connect_signals(self):
        """Connect widget signals"""
        self.ai_status.refresh_requested.connect(self.refresh_ai_status)
        self.predictions.view_all_clicked.connect(self.open_predictions_page)
        self.notifications.view_all_clicked.connect(self.open_notifications_page)
        self.notifications.notification_clicked.connect(self.show_notification_details)
        self.export.export_requested.connect(self.handle_export)

    def refresh_ai_status(self):
        """Refresh AI status data"""
        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()
            status = engine.get_training_status()
            self.ai_status.update_status(status)
        except ImportError:
            # Use mock data for testing
            self.ai_status.update_status({
                "last_training_time": datetime.now().isoformat(),
                "accuracy": 0.92,
                "total_data_points": 15432,
                "models_count": 5,
                "training_progress": 0.75
            })

    def refresh_predictions(self):
        """Refresh predictions data"""
        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()
            data = engine.get_predictions_summary()
            self.predictions.update_predictions(data)
        except ImportError:
            # Mock data
            self.predictions.update_predictions({
                "counts": {"critical": 2, "high": 5, "medium": 12, "low": 8},
                "recent_high_risk": []
            })

    def refresh_notifications(self):
        """Refresh notifications data"""
        try:
            from notification_audit import NotificationAuditLog
            audit = NotificationAuditLog()
            recent = audit.get_recent(limit=10)
            notifications = [
                {
                    "notification_id": n.notification_id,
                    "title": n.title,
                    "message": n.message,
                    "priority": n.priority,
                    "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                    "read": n.read_at is not None
                }
                for n in recent
            ]
            unread = sum(1 for n in notifications if not n["read"])
            self.notifications.update_notifications(notifications, unread)
        except ImportError:
            self.notifications.update_notifications([], 0)

    def refresh_all(self):
        """Refresh all dashboard data"""
        self.refresh_ai_status()
        self.refresh_predictions()
        self.refresh_notifications()

    def open_predictions_page(self):
        """Navigate to predictions page"""
        logger.info("Navigate to predictions page")
        # This would emit a signal to the main window to switch tabs

    def open_notifications_page(self):
        """Navigate to notifications page"""
        logger.info("Navigate to notifications page")

    def show_notification_details(self, notification_id: str):
        """Show notification details"""
        logger.info(f"Show notification details: {notification_id}")

    def handle_export(self, options: dict):
        """Handle data export request"""
        format_type = options.get("format", "csv")
        logger.info(f"Export requested: {format_type}")

        # Show file dialog
        file_filter = {
            "csv": "CSV Files (*.csv)",
            "json": "JSON Files (*.json)",
            "pdf": "PDF Files (*.pdf)",
            "excel": "Excel Files (*.xlsx)"
        }.get(format_type, "All Files (*.*)")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            f"predict_export_{datetime.now().strftime('%Y%m%d')}.{format_type}",
            file_filter
        )

        if file_path:
            self._perform_export(file_path, format_type)

    def _perform_export(self, file_path: str, format_type: str):
        """Perform the actual export"""
        try:
            # This would call the actual export functions
            logger.info(f"Exporting to {file_path}")
            self.export.update_last_export(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Export error: {e}")
