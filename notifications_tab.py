"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Notifications Tab

Notifications Tab
Centralized notification management interface
Shows all notifications, allows filtering, and manages notification preferences
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QMessageBox, QTabWidget, QScrollArea,
    QFrame, QProgressBar, QLineEdit, QSpinBox, QDateEdit,
    QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor, QIcon

import json
import csv
import os

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

# Import notification manager
try:
    from alert_notifications import get_notification_manager, NotificationPriority
    NOTIFICATION_MANAGER_AVAILABLE = True
except ImportError:
    NOTIFICATION_MANAGER_AVAILABLE = False
    print("Note: Alert Notification Manager not available")

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """Notification data structure"""
    id: str
    title: str
    message: str
    priority: str  # CRITICAL, HIGH, WARNING, INFO
    channels: List[str]  # email, push, sms, webhook
    timestamp: str
    read: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class NotificationsTab(QWidget):
    """
    Notifications Management Tab
    
    Features:
    - View all notifications
    - Filter by priority, channel, read status
    - Mark as read/unread
    - Notification preferences
    - Notification history export
    """
    
    # Signals for notification events
    notification_read = Signal(str)  # notification_id
    notification_deleted = Signal(str)  # notification_id
    preferences_changed = Signal(dict)  # new_preferences
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.notifications = []
        self.notification_manager = None
        self._setup_ui()
        self._init_notification_manager()
        self._load_notifications()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Notifications")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F0F6FC;")
        
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        self.refresh_btn.clicked.connect(self._refresh_notifications)
        
        self.mark_all_read_btn = QPushButton("✓ Mark All Read")
        self.mark_all_read_btn.setStyleSheet(self._get_button_style('secondary'))
        self.mark_all_read_btn.clicked.connect(self._mark_all_read)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.mark_all_read_btn)
        header.addSpacing(10)
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
        
        # Tab 1: Notifications List
        notifications_tab = self._create_notifications_tab()
        self.tabs.addTab(notifications_tab, "🔔 Notifications")
        
        # Tab 2: Notification Preferences
        preferences_tab = self._create_preferences_tab()
        self.tabs.addTab(preferences_tab, "⚙️ Preferences")
        
        # Tab 3: Notification History
        history_tab = self._create_history_tab()
        self.tabs.addTab(history_tab, "📜 History")
        
        layout.addWidget(self.tabs, 1)
    
    def _create_notifications_tab(self) -> QWidget:
        """Create notifications list tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Filter bar
        filter_layout = QHBoxLayout()
        
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #8B949E; font-weight: 600;")
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search notifications...")
        self.search_edit.textChanged.connect(self._filter_notifications)
        
        self.priority_filter_combo = QComboBox()
        self.priority_filter_combo.addItems(["All Priorities", "CRITICAL", "HIGH", "WARNING", "INFO"])
        self.priority_filter_combo.currentTextChanged.connect(self._filter_notifications)
        
        self.channel_filter_combo = QComboBox()
        self.channel_filter_combo.addItems(["All Channels", "Email", "Push", "SMS", "Webhook"])
        self.channel_filter_combo.currentTextChanged.connect(self._filter_notifications)
        
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All", "Unread Only", "Read Only"])
        self.status_filter_combo.currentTextChanged.connect(self._filter_notifications)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(self.priority_filter_combo)
        filter_layout.addWidget(self.channel_filter_combo)
        filter_layout.addWidget(self.status_filter_combo)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Statistics
        stats_layout = QHBoxLayout()
        
        self.total_count_label = QLabel("0 Total")
        self.total_count_label.setStyleSheet("color: #8B949E;")
        
        self.unread_count_label = QLabel("0 Unread")
        self.unread_count_label.setStyleSheet("color: #C40000; font-weight: 700;")
        
        self.critical_count_label = QLabel("0 Critical")
        self.critical_count_label.setStyleSheet("color: #F44336; font-weight: 700;")
        
        stats_layout.addWidget(self.total_count_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(self.unread_count_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(self.critical_count_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Notifications table
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QVBoxLayout(notifications_group)
        
        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(7)
        self.notifications_table.setHorizontalHeaderLabels([
            "Status", "Priority", "Channel", "Title",
            "Message", "Time", "Actions"
        ])
        self.notifications_table.horizontalHeader().setStretchLastSection(True)
        self.notifications_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notifications_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.notifications_table.setAlternatingRowColors(True)
        self.notifications_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.notifications_table)
        
        notifications_layout.addWidget(self.notifications_table)
        layout.addWidget(notifications_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.mark_read_btn = QPushButton("✓ Mark as Read")
        self.mark_read_btn.setStyleSheet(self._get_button_style('secondary'))
        self.mark_read_btn.clicked.connect(self._mark_selected_read)
        self.mark_read_btn.setEnabled(False)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setStyleSheet(self._get_button_style('danger'))
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)
        
        self.clear_all_btn = QPushButton("🗑️ Clear All")
        self.clear_all_btn.setStyleSheet(self._get_button_style('danger'))
        self.clear_all_btn.clicked.connect(self._clear_all)
        
        button_layout.addWidget(self.mark_read_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(button_layout)
        
        # Connect selection change
        self.notifications_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        return widget
    
    def _create_preferences_tab(self) -> QWidget:
        """Create notification preferences tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Email preferences
        email_group = QGroupBox("📧 Email Notifications")
        email_layout = QFormLayout(email_group)
        
        self.email_enabled_check = QCheckBox("Enable Email Notifications")
        self.email_enabled_check.setChecked(True)
        
        self.smtp_server_edit = QLineEdit()
        self.smtp_server_edit.setPlaceholderText("smtp.gmail.com")
        
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        
        self.email_username_edit = QLineEdit()
        self.email_username_edit.setPlaceholderText("your-email@gmail.com")
        
        self.email_password_edit = QLineEdit()
        self.email_password_edit.setPlaceholderText("App password")
        self.email_password_edit.setEchoMode(QLineEdit.Password)
        
        self.from_address_edit = QLineEdit()
        self.from_address_edit.setPlaceholderText("noreply@predictobd.com")
        
        email_layout.addRow("", self.email_enabled_check)
        email_layout.addRow("SMTP Server:", self.smtp_server_edit)
        email_layout.addRow("SMTP Port:", self.smtp_port_spin)
        email_layout.addRow("Username:", self.email_username_edit)
        email_layout.addRow("Password:", self.email_password_edit)
        email_layout.addRow("From Address:", self.from_address_edit)
        
        layout.addWidget(email_group)
        
        # Push notification preferences
        push_group = QGroupBox("📱 Push Notifications")
        push_layout = QFormLayout(push_group)
        
        self.push_enabled_check = QCheckBox("Enable Push Notifications")
        self.push_enabled_check.setChecked(True)
        
        self.firebase_key_edit = QLineEdit()
        self.firebase_key_edit.setPlaceholderText("Firebase Server Key")
        self.firebase_key_edit.setEchoMode(QLineEdit.Password)
        
        push_layout.addRow("", self.push_enabled_check)
        push_layout.addRow("Firebase Key:", self.firebase_key_edit)
        
        layout.addWidget(push_group)
        
        # SMS preferences
        sms_group = QGroupBox("📲 SMS Notifications")
        sms_layout = QFormLayout(sms_group)
        
        self.sms_enabled_check = QCheckBox("Enable SMS Notifications")
        self.sms_enabled_check.setChecked(False)
        
        self.sms_api_key_edit = QLineEdit()
        self.sms_api_key_edit.setPlaceholderText("Twilio API Key")
        self.sms_api_key_edit.setEchoMode(QLineEdit.Password)
        
        self.sms_from_number_edit = QLineEdit()
        self.sms_from_number_edit.setPlaceholderText("+1234567890")
        
        sms_layout.addRow("", self.sms_enabled_check)
        sms_layout.addRow("API Key:", self.sms_api_key_edit)
        sms_layout.addRow("From Number:", self.sms_from_number_edit)
        
        layout.addWidget(sms_group)
        
        # General preferences
        general_group = QGroupBox("⚙️ General Preferences")
        general_layout = QFormLayout(general_group)
        
        self.sound_enabled_check = QCheckBox("Enable Sound")
        self.sound_enabled_check.setChecked(True)
        
        self.desktop_notification_check = QCheckBox("Show Desktop Notifications")
        self.desktop_notification_check.setChecked(True)
        
        self.quiet_hours_start = QSpinBox()
        self.quiet_hours_start.setRange(0, 23)
        self.quiet_hours_start.setValue(22)
        self.quiet_hours_start.setSuffix(":00")
        
        self.quiet_hours_end = QSpinBox()
        self.quiet_hours_end.setRange(0, 23)
        self.quiet_hours_end.setValue(7)
        self.quiet_hours_end.setSuffix(":00")
        
        general_layout.addRow("", self.sound_enabled_check)
        general_layout.addRow("", self.desktop_notification_check)
        general_layout.addRow("Quiet Hours Start:", self.quiet_hours_start)
        general_layout.addRow("Quiet Hours End:", self.quiet_hours_end)
        
        layout.addWidget(general_group)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Save Preferences")
        save_btn.setStyleSheet(self._get_button_style('primary'))
        save_btn.clicked.connect(self._save_preferences)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def _create_history_tab(self) -> QWidget:
        """Create notification history tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Date range filter
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout(date_group)
        
        date_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        date_layout.addWidget(self.date_from)
        
        date_layout.addSpacing(20)
        date_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_to)
        
        date_layout.addStretch()
        
        self.apply_date_filter_btn = QPushButton("Apply")
        self.apply_date_filter_btn.setStyleSheet(self._get_button_style('secondary'))
        self.apply_date_filter_btn.clicked.connect(self._apply_date_filter)
        date_layout.addWidget(self.apply_date_filter_btn)
        
        layout.addWidget(date_group)
        
        # History table
        history_group = QGroupBox("Notification History")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Priority", "Channel", "Title",
            "Status", "Message"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        self._apply_table_styling(self.history_table)
        
        history_layout.addWidget(self.history_table)
        layout.addWidget(history_group)
        
        # Export button
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        
        export_btn = QPushButton("📤 Export History")
        export_btn.setStyleSheet(self._get_button_style('secondary'))
        export_btn.clicked.connect(self._export_history)
        export_layout.addWidget(export_btn)
        
        layout.addLayout(export_layout)
        
        return widget
    
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
    
    def _init_notification_manager(self):
        """Initialize notification manager"""
        if NOTIFICATION_MANAGER_AVAILABLE:
            try:
                self.notification_manager = get_notification_manager()
                logger.info("Notification manager initialized")
            except Exception as e:
                logger.error(f"Error initializing notification manager: {e}")
                self.notification_manager = None
        else:
            logger.warning("Notification manager not available")
    def _load_notifications(self):
        """Load notifications from notification manager"""
        self.notifications = []
        
        if self.notification_manager:
            try:
                # Load real notifications from manager
                user_id = self._get_current_profile_id()
                raw_notifications = self.notification_manager.get_user_notifications(user_id=user_id, limit=100)
                
                if raw_notifications:
                    for raw in raw_notifications:
                        # Convert database row to Notification object
                        channels = []
                        if raw.get('channels'):
                            try:
                                channels = json.loads(raw['channels']) if isinstance(raw['channels'], str) else raw['channels']
                            except:
                                channels = [raw['channels']]
                        
                        notif = Notification(
                            id=raw.get('notification_id', ''),
                            title=raw.get('title', ''),
                            message=raw.get('message', ''),
                            priority=raw.get('priority', 'INFO').upper(),
                            channels=channels if isinstance(channels, list) else [channels],
                            timestamp=raw.get('created_at', datetime.now().isoformat()),
                            read=bool(raw.get('delivered', False)),
                            metadata=json.loads(raw.get('data', '{}')) if isinstance(raw.get('data'), str) else raw.get('data', {})
                        )
                        self.notifications.append(notif)
                
                logger.info(f"Loaded {len(self.notifications)} notifications from manager")
            except Exception as e:
                logger.error(f"Error loading notifications from manager: {e}")
                self.notifications = []
        
        self._update_notifications_table()
        self._update_statistics()
    
    def _get_current_profile_id(self) -> int:
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
        return 1  # Default to 1
    
    def _update_notifications_table(self):
        """Update notifications table"""
        self.notifications_table.setRowCount(0)

        for notif in self.notifications:
            self._add_notification_to_table(notif)

        self.notifications_table.resizeColumnsToContents()

    def _update_history_table(self):
        """Update the history table with all notifications"""
        self.history_table.setRowCount(0)

        for notif in self.notifications:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            # Date
            try:
                if isinstance(notif.timestamp, str):
                    dt = datetime.fromisoformat(notif.timestamp)
                    date_text = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    date_text = str(notif.timestamp)
            except:
                date_text = str(notif.timestamp)
            self.history_table.setItem(row, 0, QTableWidgetItem(date_text))

            # Priority
            priority_item = QTableWidgetItem(notif.priority)
            if notif.priority == "CRITICAL":
                priority_item.setForeground(QColor("#F44336"))
            elif notif.priority == "HIGH":
                priority_item.setForeground(QColor("#FF9800"))
            elif notif.priority == "WARNING":
                priority_item.setForeground(QColor("#FFC107"))
            else:
                priority_item.setForeground(QColor("#8B949E"))
            self.history_table.setItem(row, 1, priority_item)

            # Channel
            channels_text = ", ".join(notif.channels)
            self.history_table.setItem(row, 2, QTableWidgetItem(channels_text))

            # Title
            self.history_table.setItem(row, 3, QTableWidgetItem(notif.title))

            # Status
            status_text = "Read" if notif.read else "Unread"
            status_item = QTableWidgetItem(status_text)
            if notif.read:
                status_item.setForeground(QColor("#8B949E"))
            else:
                status_item.setForeground(QColor("#C40000"))
            self.history_table.setItem(row, 4, status_item)

            # Message
            self.history_table.setItem(row, 5, QTableWidgetItem(notif.message))

        self.history_table.resizeColumnsToContents()
    
    def _update_statistics(self):
        """Update notification statistics"""
        total = len(self.notifications)
        unread = sum(1 for n in self.notifications if not n.read)
        critical = sum(1 for n in self.notifications if n.priority == "CRITICAL")
        
        self.total_count_label.setText(f"{total} Total")
        self.unread_count_label.setText(f"{unread} Unread")
        self.critical_count_label.setText(f"{critical} Critical")
    
    def _filter_notifications(self):
        """Filter notifications based on search and filters"""
        search_text = self.search_edit.text().lower()
        priority_filter = self.priority_filter_combo.currentText()
        channel_filter = self.channel_filter_combo.currentText().lower()
        status_filter = self.status_filter_combo.currentText()

        # Clear table
        self.notifications_table.setRowCount(0)

        # Filter and display notifications
        filtered_count = 0
        for notif in self.notifications:
            # Apply search filter
            if search_text:
                search_match = (
                    search_text in notif.title.lower() or
                    search_text in notif.message.lower()
                )
                if not search_match:
                    continue

            # Apply priority filter
            if priority_filter != "All Priorities":
                if notif.priority.upper() != priority_filter.upper():
                    continue

            # Apply channel filter
            if channel_filter != "all channels":
                channel_match = any(channel_filter in ch.lower() for ch in notif.channels)
                if not channel_match:
                    continue

            # Apply status filter
            if status_filter == "Unread Only" and notif.read:
                continue
            if status_filter == "Read Only" and not notif.read:
                continue

            # Add matching notification to table
            self._add_notification_to_table(notif)
            filtered_count += 1

        # Update count label
        total = len(self.notifications)
        self.total_count_label.setText(f"{filtered_count}/{total} Shown")

    def _add_notification_to_table(self, notif: Notification):
        """Add a single notification to the table"""
        row = self.notifications_table.rowCount()
        self.notifications_table.insertRow(row)

        # Status (read/unread)
        status_widget = QLabel()
        if notif.read:
            status_widget.setText("●")
            status_widget.setStyleSheet("color: #8B949E; font-size: 16px;")
        else:
            status_widget.setText("○")
            status_widget.setStyleSheet("color: #C40000; font-size: 16px;")
        self.notifications_table.setCellWidget(row, 0, status_widget)

        # Priority
        priority_item = QTableWidgetItem(notif.priority)
        if notif.priority == "CRITICAL":
            priority_item.setForeground(QColor("#F44336"))
        elif notif.priority == "HIGH":
            priority_item.setForeground(QColor("#FF9800"))
        elif notif.priority == "WARNING":
            priority_item.setForeground(QColor("#FFC107"))
        else:
            priority_item.setForeground(QColor("#8B949E"))
        self.notifications_table.setItem(row, 1, priority_item)

        # Channel
        channels_text = ", ".join(notif.channels)
        self.notifications_table.setItem(row, 2, QTableWidgetItem(channels_text))

        # Title (store notif.id in UserRole for later retrieval)
        title_item = QTableWidgetItem(notif.title)
        title_item.setData(Qt.UserRole, notif.id)
        if not notif.read:
            title_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.notifications_table.setItem(row, 3, title_item)

        # Message (truncated)
        message = notif.message
        if len(message) > 50:
            message = message[:50] + "..."
        self.notifications_table.setItem(row, 4, QTableWidgetItem(message))

        # Time
        try:
            if isinstance(notif.timestamp, str):
                dt = datetime.fromisoformat(notif.timestamp)
                time_text = dt.strftime("%H:%M")
            else:
                time_text = str(notif.timestamp)
        except:
            time_text = str(notif.timestamp)
        self.notifications_table.setItem(row, 5, QTableWidgetItem(time_text))

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        view_btn = QPushButton("👁️")
        view_btn.setFixedSize(32, 32)
        view_btn.setStyleSheet(self._get_button_style('secondary'))
        view_btn.setToolTip("View notification details")
        view_btn.clicked.connect(lambda checked, n=notif: self._view_notification(n))

        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setStyleSheet(self._get_button_style('danger'))
        delete_btn.setToolTip("Delete this notification")
        delete_btn.clicked.connect(lambda checked, n_id=notif.id: self._delete_notification(n_id))

        actions_layout.addWidget(view_btn)
        actions_layout.addWidget(delete_btn)

        self.notifications_table.setCellWidget(row, 6, actions_widget)
    
    def _on_selection_changed(self):
        """Handle notification selection change"""
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0
        
        self.mark_read_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
    
    def _mark_selected_read(self):
        """Mark selected notifications as read"""
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        
        if not selected_rows or not self.notification_manager:
            return
        
        # Get notification IDs to mark as read
        ids_to_mark = []
        for row in selected_rows:
            notif_id_item = self.notifications_table.item(row, 3)  # Title column
            if notif_id_item:
                notif_id = notif_id_item.data(Qt.UserRole)
                if notif_id:
                    ids_to_mark.append(notif_id)
        
        if not ids_to_mark:
            return
        
        # Mark as read in backend
        try:
            user_id = self._get_current_profile_id()
            # Note: Backend doesn't have mark_as_read method, so we update local state
            # For production, would need to add mark_as_read method to AlertNotificationManager
            for notif in self.notifications:
                if notif.id in ids_to_mark:
                    notif.read = True
        
        except Exception as e:
            logger.error(f"Error marking notifications as read: {e}")
        
        self._update_notifications_table()
        self._update_statistics()
        logger.info(f"Marked {len(selected_rows)} notifications as read")
    
    def _mark_all_read(self):
        """Mark all notifications as read"""
        if not self.notification_manager:
            QMessageBox.warning(self, "Error", "Notification manager not available")
            return
        
        try:
            user_id = self._get_current_profile_id()
            # Mark all notifications as read locally
            for notif in self.notifications:
                notif.read = True
            
            self._update_notifications_table()
            self._update_statistics()
            
            QMessageBox.information(
                self,
                "Notifications Marked",
                f"All {len(self.notifications)} notifications marked as read."
            )
            
            logger.info("All notifications marked as read")
        
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            QMessageBox.critical(self, "Error", f"Failed to mark notifications as read: {e}")
    
    def _delete_selected(self):
        """Delete selected notifications"""
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Notifications",
            f"Are you sure you want to delete {len(selected_rows)} notification(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Get notification IDs to delete
            ids_to_delete = []
            for row in sorted(selected_rows, reverse=True):
                notif_id_item = self.notifications_table.item(row, 3)
                if notif_id_item:
                    notif_id = notif_id_item.data(Qt.UserRole)
                    if notif_id:
                        ids_to_delete.append(notif_id)
            
            # Remove from list
            self.notifications = [n for n in self.notifications if n.id not in ids_to_delete]
            
            self._update_notifications_table()
            self._update_statistics()
            
            # Emit signal
            for notif_id in ids_to_delete:
                self.notification_deleted.emit(notif_id)
            
            logger.info(f"Deleted {len(ids_to_delete)} notifications")
    
    def _clear_all(self):
        """Clear all notifications"""
        reply = QMessageBox.question(
            self,
            "Clear All Notifications",
            "Are you sure you want to delete ALL notifications? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            count = len(self.notifications)
            self.notifications.clear()
            
            self._update_notifications_table()
            self._update_statistics()
            
            QMessageBox.information(
                self,
                "Notifications Cleared",
                f"All {count} notifications have been deleted."
            )
            
            logger.info(f"Cleared {count} notifications")
    
    def _view_notification(self, notif: Notification):
        """View notification details"""
        details = f"""
        <h3>{notif.title}</h3>
        <p><b>Message:</b> {notif.message}</p>
        <p><b>Priority:</b> {notif.priority}</p>
        <p><b>Channels:</b> {', '.join(notif.channels)}</p>
        <p><b>Timestamp:</b> {notif.timestamp}</p>
        <p><b>Status:</b> {'Read' if notif.read else 'Unread'}</p>
        """
        
        if notif.metadata:
            details += "<p><b>Metadata:</b></p><ul>"
            for key, value in notif.metadata.items():
                details += f"<li>{key}: {value}</li>"
            details += "</ul>"
        
        QMessageBox.information(self, "Notification Details", details)
    
    def _delete_notification(self, notif_id: str):
        """Delete a single notification"""
        self.notifications = [n for n in self.notifications if n.id != notif_id]
        
        self._update_notifications_table()
        self._update_statistics()
        
        # Emit signal
        self.notification_deleted.emit(notif_id)
        
        logger.info(f"Deleted notification: {notif_id}")
    
    def _refresh_notifications(self):
        """Refresh notifications from notification manager"""
        self._load_notifications()
        
        QMessageBox.information(
            self,
            "Notifications Refreshed",
            f"Loaded {len(self.notifications)} notifications."
        )
    
    def _save_preferences(self):
        """Save notification preferences"""
        if not self.notification_manager:
            QMessageBox.warning(self, "Error", "Notification manager not available")
            return
        
        preferences = {
            'email': {
                'enabled': self.email_enabled_check.isChecked(),
                'smtp_server': self.smtp_server_edit.text(),
                'smtp_port': self.smtp_port_spin.value(),
                'username': self.email_username_edit.text(),
                'password': self.email_password_edit.text(),
                'from_address': self.from_address_edit.text()
            },
            'push': {
                'enabled': self.push_enabled_check.isChecked(),
                'firebase_key': self.firebase_key_edit.text()
            },
            'sms': {
                'enabled': self.sms_enabled_check.isChecked(),
                'api_key': self.sms_api_key_edit.text(),
                'from_number': self.sms_from_number_edit.text()
            },
            'general': {
                'sound_enabled': self.sound_enabled_check.isChecked(),
                'desktop_notifications': self.desktop_notification_check.isChecked(),
                'quiet_hours_start': self.quiet_hours_start.value(),
                'quiet_hours_end': self.quiet_hours_end.value()
            }
        }
        
        # Emit signal
        self.preferences_changed.emit(preferences)
        
        try:
            user_id = self._get_current_profile_id()
            
            # Save to notification manager
            self.notification_manager.configure_channel('email', preferences['email'])
            self.notification_manager.configure_channel('push', preferences['push'])
            self.notification_manager.configure_channel('sms', preferences['sms'])
            
            # Save user preferences to database
            self.notification_manager.set_user_preferences(
                user_id=user_id,
                email_enabled=preferences['email']['enabled'],
                push_enabled=preferences['push']['enabled'],
                sms_enabled=preferences['sms']['enabled'],
                webhook_url=preferences.get('webhook_url', '')
            )
            
            QMessageBox.information(
                self,
                "Preferences Saved",
                "Notification preferences have been saved."
            )
            
            logger.info(f"Notification preferences saved: {preferences}")
        
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save preferences: {e}")
    
    def _apply_date_filter(self):
        """Apply date range filter to history"""
        from_date = self.date_from.date().toPyDate()
        to_date = self.date_to.date().toPyDate()

        # Convert to datetime for comparison
        from_datetime = datetime.combine(from_date, datetime.min.time())
        to_datetime = datetime.combine(to_date, datetime.max.time())

        # Filter history table
        self.history_table.setRowCount(0)
        filtered_count = 0

        for notif in self.notifications:
            try:
                if isinstance(notif.timestamp, str):
                    notif_dt = datetime.fromisoformat(notif.timestamp)
                else:
                    notif_dt = notif.timestamp

                # Check if notification is within date range
                if from_datetime <= notif_dt <= to_datetime:
                    row = self.history_table.rowCount()
                    self.history_table.insertRow(row)

                    # Date
                    date_text = notif_dt.strftime("%Y-%m-%d %H:%M")
                    self.history_table.setItem(row, 0, QTableWidgetItem(date_text))

                    # Priority
                    priority_item = QTableWidgetItem(notif.priority)
                    if notif.priority == "CRITICAL":
                        priority_item.setForeground(QColor("#F44336"))
                    elif notif.priority == "HIGH":
                        priority_item.setForeground(QColor("#FF9800"))
                    elif notif.priority == "WARNING":
                        priority_item.setForeground(QColor("#FFC107"))
                    else:
                        priority_item.setForeground(QColor("#8B949E"))
                    self.history_table.setItem(row, 1, priority_item)

                    # Channel
                    channels_text = ", ".join(notif.channels)
                    self.history_table.setItem(row, 2, QTableWidgetItem(channels_text))

                    # Title
                    self.history_table.setItem(row, 3, QTableWidgetItem(notif.title))

                    # Status
                    status_text = "Read" if notif.read else "Unread"
                    status_item = QTableWidgetItem(status_text)
                    if notif.read:
                        status_item.setForeground(QColor("#8B949E"))
                    else:
                        status_item.setForeground(QColor("#C40000"))
                    self.history_table.setItem(row, 4, status_item)

                    # Message
                    self.history_table.setItem(row, 5, QTableWidgetItem(notif.message))

                    filtered_count += 1

            except Exception as e:
                logger.debug(f"Error parsing notification date: {e}")

        QMessageBox.information(
            self,
            "Date Filter Applied",
            f"Showing {filtered_count} notification(s) from {from_date} to {to_date}"
        )

        logger.info(f"Date filter applied: {from_date} to {to_date}, {filtered_count} notifications")

    def _export_history(self):
        """Export notification history to CSV or JSON"""
        # Get export file path
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Notification History",
            f"notification_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "CSV Files (*.csv);;JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Gather notification data
            export_data = []
            for notif in self.notifications:
                export_data.append({
                    'id': notif.id,
                    'title': notif.title,
                    'message': notif.message,
                    'priority': notif.priority,
                    'channels': ', '.join(notif.channels),
                    'timestamp': notif.timestamp,
                    'read': notif.read,
                    'metadata': json.dumps(notif.metadata) if notif.metadata else ''
                })

            # Export based on file extension
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'export_date': datetime.now().isoformat(),
                        'total_notifications': len(export_data),
                        'notifications': export_data
                    }, f, indent=2)
            else:
                # Default to CSV
                if not file_path.endswith('.csv'):
                    file_path += '.csv'

                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['id', 'title', 'message', 'priority', 'channels', 'timestamp', 'read', 'metadata'])
                    writer.writeheader()
                    writer.writerows(export_data)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Notification history exported successfully!\n\nFile: {file_path}\nNotifications: {len(export_data)}"
            )
            logger.info(f"Notification history exported: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export notification history:\n{e}")
            logger.error(f"Notification history export error: {e}")
