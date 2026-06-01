"""
PREDICT - Vehicle Intelligence Platform
Copyright (c) 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: February 2026
Module: User Control Dialog

Complete User Control Panel for Desktop Admin
Manages user subscriptions, features, limits, and account status.
Changes reflect IMMEDIATELY on user's Android app.
"""

import logging
import json
import sqlite3
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Import AuditLogViewer for "View All" functionality
try:
    from audit_log_viewer import AuditLogViewer
    AUDIT_VIEWER_AVAILABLE = True
except ImportError:
    AUDIT_VIEWER_AVAILABLE = False

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QMessageBox, QSpinBox, QFrame, QScrollArea, QWidget,
    QRadioButton, QButtonGroup, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QDateEdit, QGridLayout,
    QTabWidget, QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont, QColor, QShortcut, QKeySequence

logger = logging.getLogger(__name__)

# Database path (for local unified_users - Desktop created)
DB_PATH = Path("C:/OBDserver/Previlium_OBD_Server/data/obd_data.db")

# Server database path (for customers - Android registered)
SERVER_DB_PATH = Path("C:/OBDserver/Previlium_OBD_Server/server_database.db")

# Import server API client for HTTP calls
try:
    from server_api_client import ServerAPIClient, ADMIN_KEY
    HAS_SERVER_CLIENT = True
except ImportError:
    HAS_SERVER_CLIENT = False
    ADMIN_KEY = None


@dataclass
class UserControlData:
    """Complete user data for control panel"""
    user_id: int
    email: str
    name: str = ""
    tier: str = "free"
    status: str = "active"
    created_at: str = ""
    last_activity: str = ""
    suspended: bool = False
    suspended_at: str = ""
    suspension_reason: str = ""

    # Custom limits (None = use tier default)
    custom_ai_limit: Optional[int] = None
    custom_trip_days: Optional[int] = None
    custom_max_vehicles: Optional[int] = None
    custom_refresh_seconds: Optional[int] = None
    tier_expires_at: Optional[str] = None

    # Feature overrides (None = use tier default)
    feature_overrides: Dict[str, Optional[bool]] = field(default_factory=dict)

    # Current usage
    usage_today: Dict[str, int] = field(default_factory=dict)

    # Audit log
    audit_log: List[Dict[str, Any]] = field(default_factory=list)


class TierRadioGroup(QGroupBox):
    """Subscription tier selection with radio buttons"""

    tier_changed = Signal(str)

    TIER_INFO = {
        'free': {
            'color': '#6B7280',
            'description': '3-day trial with full access. After trial expires, all features locked.'
        },
        'pro': {
            'color': '#3B82F6',
            'description': 'AI Chat (10/day), Predictions (10/day), 30-day history. NO Guardian access.'
        },
        'premium': {
            'color': '#F59E0B',
            'description': 'AI Chat (50/day), Predictions (50/day), Guardian mode (2 vehicles max), 365-day history.'
        },
        'admin': {
            'color': '#C40000',
            'description': 'Unlimited access to ALL features including admin controls.'
        }
    }

    def __init__(self, current_tier: str = "free", parent=None):
        super().__init__("Subscription Tier", parent)
        self.current_tier = current_tier
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.button_group = QButtonGroup(self)

        for tier_name, info in self.TIER_INFO.items():
            radio = QRadioButton(tier_name.upper())
            radio.setStyleSheet(f"""
                QRadioButton {{
                    color: #F0F6FC;
                    font-size: 13px;
                    font-weight: bold;
                    spacing: 10px;
                }}
                QRadioButton::indicator {{
                    width: 18px;
                    height: 18px;
                }}
                QRadioButton::indicator:checked {{
                    background-color: {info['color']};
                    border: 2px solid {info['color']};
                    border-radius: 9px;
                }}
                QRadioButton::indicator:unchecked {{
                    background-color: #21262D;
                    border: 2px solid #30363D;
                    border-radius: 9px;
                }}
            """)

            if tier_name == self.current_tier:
                radio.setChecked(True)

            radio.toggled.connect(lambda checked, t=tier_name: self._on_tier_selected(t, checked))
            self.button_group.addButton(radio)

            # Description label
            desc = QLabel(info['description'])
            desc.setStyleSheet("color: #8B949E; font-size: 11px; margin-left: 28px; margin-bottom: 8px;")
            desc.setWordWrap(True)

            layout.addWidget(radio)
            layout.addWidget(desc)

    def _on_tier_selected(self, tier: str, checked: bool):
        if checked:
            self.tier_changed.emit(tier)

    def get_selected_tier(self) -> str:
        for button in self.button_group.buttons():
            if button.isChecked():
                return button.text().lower()
        return self.current_tier


class UsageLimitsGroup(QGroupBox):
    """Custom usage limits override group"""

    def __init__(self, user_data: UserControlData, parent=None):
        super().__init__("Usage Limits (Override Defaults)", parent)
        self.user_data = user_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)

        # Define limits with defaults per tier
        # Note: Fleet vehicles default is 2 for Premium tier (Guardian mode)
        # Free/Pro: 0 (no fleet), Premium: 2, Fleet Manager: 10, Enterprise: 50
        self.limits = {}
        limit_configs = [
            ('ai_messages_per_day', 'AI Messages/Day', 10, self.user_data.custom_ai_limit),
            ('trip_history_days', 'Trip History Days', 7, self.user_data.custom_trip_days),
            ('max_vehicles', 'Max Fleet Vehicles', 2, self.user_data.custom_max_vehicles),
            ('data_refresh_seconds', 'Data Refresh (sec)', 5, self.user_data.custom_refresh_seconds),
        ]

        for key, label, default, current_value in limit_configs:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Spin box for value
            spin = QSpinBox()
            spin.setRange(0, 10000)
            spin.setSpecialValueText("0 (Locked)")
            spin.setValue(current_value if current_value is not None else default)
            spin.setEnabled(current_value is not None)
            spin.setStyleSheet("""
                QSpinBox {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    border-radius: 6px;
                    padding: 4px 8px;
                    min-width: 80px;
                }
                QSpinBox:disabled {
                    background-color: #161B22;
                    color: #6B7280;
                }
            """)
            row_layout.addWidget(spin)

            # Override checkbox
            override_cb = QCheckBox("Custom")
            override_cb.setChecked(current_value is not None)
            override_cb.setStyleSheet("color: #8B949E;")
            override_cb.toggled.connect(lambda checked, s=spin: s.setEnabled(checked))
            row_layout.addWidget(override_cb)

            # Default value hint
            hint = QLabel(f"(Default: {default})")
            hint.setStyleSheet("color: #6B7280; font-size: 10px;")
            row_layout.addWidget(hint)

            row_layout.addStretch()

            self.limits[key] = {'spin': spin, 'override': override_cb, 'default': default}
            layout.addRow(label + ":", row_widget)

    def get_overrides(self) -> Dict[str, Optional[int]]:
        """Get only the overridden limits"""
        overrides = {}
        for key, widgets in self.limits.items():
            if widgets['override'].isChecked():
                overrides[key] = widgets['spin'].value()
            else:
                overrides[key] = None
        return overrides


class FeatureAccessGroup(QGroupBox):
    """Feature access toggles"""

    FEATURES = [
        ('obd_dashboard', 'OBD Dashboard'),
        ('dtc_read', 'DTC Reading'),
        ('dtc_clear', 'DTC Clearing'),
        ('ai_chat', 'AI Chat'),
        ('predictions', 'Predictions'),
        ('guardian_mode', 'Guardian Mode'),
        ('desktop_sync', 'Desktop Sync'),
        ('pdf_reports', 'PDF Reports'),
        ('push_alerts', 'Push Alerts'),
    ]

    def __init__(self, feature_overrides: Dict[str, Optional[bool]], parent=None):
        super().__init__("Feature Access", parent)
        self.feature_overrides = feature_overrides
        self._setup_ui()

    def _setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)

        self.checkboxes = {}

        for idx, (feature_key, feature_label) in enumerate(self.FEATURES):
            row = idx // 3
            col = idx % 3

            cb = QCheckBox(feature_label)
            cb.setTristate(True)

            # Get current state
            current = self.feature_overrides.get(feature_key)
            if current is None:
                cb.setCheckState(Qt.PartiallyChecked)  # Use tier default
            elif current:
                cb.setCheckState(Qt.Checked)
            else:
                cb.setCheckState(Qt.Unchecked)

            cb.setStyleSheet("""
                QCheckBox {
                    color: #F0F6FC;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
                QCheckBox::indicator:checked {
                    background-color: #22C55E;
                    border: 1px solid #22C55E;
                    border-radius: 3px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #EF4444;
                    border: 1px solid #EF4444;
                    border-radius: 3px;
                }
                QCheckBox::indicator:indeterminate {
                    background-color: #6B7280;
                    border: 1px solid #6B7280;
                    border-radius: 3px;
                }
            """)

            self.checkboxes[feature_key] = cb
            layout.addWidget(cb, row, col)

        # Legend
        legend = QLabel("Checked=Enabled, Unchecked=Disabled, Gray=Use Tier Default")
        legend.setStyleSheet("color: #6B7280; font-size: 10px; margin-top: 8px;")
        layout.addWidget(legend, (len(self.FEATURES) // 3) + 1, 0, 1, 3)

    def get_overrides(self) -> Dict[str, Optional[bool]]:
        """Get feature overrides"""
        overrides = {}
        for feature_key, cb in self.checkboxes.items():
            state = cb.checkState()
            if state == Qt.PartiallyChecked:
                overrides[feature_key] = None  # Use tier default
            elif state == Qt.Checked:
                overrides[feature_key] = True
            else:
                overrides[feature_key] = False
        return overrides


class CurrentUsageGroup(QGroupBox):
    """Current usage display with reset buttons"""

    usage_reset = Signal(str)  # feature_name

    def __init__(self, usage_today: Dict[str, int], parent=None):
        super().__init__("Current Usage (Today)", parent)
        self.usage_today = usage_today
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(8)

        usage_items = [
            ('ai_messages', 'AI Messages', 10),
            ('dtc_scans', 'DTC Scans', 20),
            ('predictions', 'Predictions', 10),
            ('vehicle_data', 'Data Points', None),  # None = no limit display
        ]

        for key, label, limit in usage_items:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            used = self.usage_today.get(key, 0)

            if limit:
                # Progress bar
                bar = QProgressBar()
                bar.setFixedHeight(20)
                bar.setMaximum(limit)
                bar.setValue(min(used, limit))
                bar.setFormat(f"{used}/{limit}")

                pct = (used / limit) * 100 if limit > 0 else 0
                if pct >= 100:
                    color = "#EF4444"
                elif pct >= 75:
                    color = "#F59E0B"
                else:
                    color = "#22C55E"

                bar.setStyleSheet(f"""
                    QProgressBar {{
                        border: none;
                        border-radius: 4px;
                        background-color: #21262D;
                        text-align: center;
                        color: white;
                        font-size: 11px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {color};
                        border-radius: 4px;
                    }}
                """)
                row_layout.addWidget(bar, stretch=1)
            else:
                # Just text
                value_label = QLabel(f"{used:,}")
                value_label.setStyleSheet("color: #F0F6FC; font-size: 12px;")
                row_layout.addWidget(value_label, stretch=1)

            # Reset button
            reset_btn = QPushButton("Reset")
            reset_btn.setFixedWidth(60)
            reset_btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                }
            """)
            reset_btn.clicked.connect(lambda checked, k=key: self.usage_reset.emit(k))
            row_layout.addWidget(reset_btn)

            layout.addRow(label + ":", row_widget)


class AuditLogTable(QTableWidget):
    """Audit log table widget"""

    def __init__(self, audit_log: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.audit_log = audit_log
        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Date", "Action", "Field", "Old Value", "New Value"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        self.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 4px;
                gridline-color: #21262D;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #21262D;
            }
            QTableWidget::item:alternate {
                background-color: #161B22;
            }
            QHeaderView::section {
                background-color: #21262D;
                color: #8B949E;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #C40000;
            }
        """)

    def _populate(self):
        self.setRowCount(len(self.audit_log))

        for row, entry in enumerate(self.audit_log):
            # Date
            ts = entry.get('timestamp', 0)
            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else "N/A"
            self.setItem(row, 0, QTableWidgetItem(date_str))

            # Action
            action = entry.get('action', 'unknown')
            action_item = QTableWidgetItem(action.replace('_', ' ').title())
            self.setItem(row, 1, action_item)

            # Field
            self.setItem(row, 2, QTableWidgetItem(entry.get('field_name', '-')))

            # Old/New values
            self.setItem(row, 3, QTableWidgetItem(str(entry.get('old_value', '-'))))
            self.setItem(row, 4, QTableWidgetItem(str(entry.get('new_value', '-'))))


class UserControlDialog(QDialog):
    """
    Complete User Control Panel Dialog

    Allows admin to:
    - Change subscription tier (Free/Pro/Premium/Admin)
    - Set custom usage limits
    - Enable/disable specific features
    - Suspend/activate accounts
    - View audit log
    - Reset usage counters

    Changes reflect IMMEDIATELY on user's Android app.
    """

    user_updated = Signal(int)  # user_id

    def __init__(self, user_id: int, source: str = 'unified_users', parent=None):
        """
        Initialize User Control Dialog.

        Args:
            user_id: The user's ID
            source: Which table to query - 'unified_users' (Desktop) or 'customers' (Android)
            parent: Parent widget
        """
        super().__init__(parent)
        self.user_id = user_id
        self.source = source  # 'unified_users' or 'customers'
        self.user_data: Optional[UserControlData] = None
        self.original_data: Optional[UserControlData] = None
        self._server_api_key: Optional[str] = None  # Store API key for display

        self.setWindowTitle("User Control Panel")
        self.setMinimumSize(700, 800)
        self._apply_styling()
        self._setup_ui()
        self._load_user_data()

        # Add Ctrl+S keyboard shortcut for quick save
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._save_changes)

    def _apply_styling(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
            }
            QLabel {
                color: #F0F6FC;
            }
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #30363D;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: #0D1117;
            }
            QPushButton {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
            QPushButton:disabled {
                background-color: #161B22;
                color: #6B7280;
            }
        """)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with user info
        self.header_frame = self._create_header()
        main_layout.addWidget(self.header_frame)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #0D1117;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363D;
                border-radius: 5px;
                min-height: 30px;
            }
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(16)

        # Tier selection
        self.tier_group = TierRadioGroup("free")
        content_layout.addWidget(self.tier_group)

        # Expiration
        self.expiry_group = self._create_expiry_group()
        content_layout.addWidget(self.expiry_group)

        # Usage limits
        self.limits_group = UsageLimitsGroup(UserControlData(user_id=0, email=""))
        content_layout.addWidget(self.limits_group)

        # Feature access
        self.features_group = FeatureAccessGroup({})
        content_layout.addWidget(self.features_group)

        # Current usage
        self.usage_group = CurrentUsageGroup({})
        self.usage_group.usage_reset.connect(self._reset_usage_counter)
        content_layout.addWidget(self.usage_group)

        # Account actions
        self.actions_group = self._create_actions_group()
        content_layout.addWidget(self.actions_group)

        # Audit log
        self.audit_group = self._create_audit_group()
        content_layout.addWidget(self.audit_group)

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #C40000;
                border-color: #C40000;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        save_btn.clicked.connect(self._save_changes)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

    def _create_header(self) -> QFrame:
        """Create header with user info"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1E2329;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QGridLayout(frame)
        layout.setSpacing(12)

        # User icon placeholder
        icon_label = QLabel("👤")
        icon_label.setFont(QFont("Segoe UI", 32))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label, 0, 0, 2, 1)

        # Name and email
        self.name_label = QLabel("Loading...")
        self.name_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.name_label.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(self.name_label, 0, 1)

        self.email_label = QLabel("")
        self.email_label.setStyleSheet("color: #8B949E;")
        layout.addWidget(self.email_label, 1, 1)

        # Status
        self.status_label = QLabel("●  Active")
        self.status_label.setStyleSheet("color: #22C55E; font-weight: bold;")
        layout.addWidget(self.status_label, 0, 2, Qt.AlignRight)

        # Created date
        self.created_label = QLabel("")
        self.created_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(self.created_label, 1, 2, Qt.AlignRight)

        # API Key row
        api_key_label = QLabel("🔑 API Key:")
        api_key_label.setStyleSheet("color: #8B949E; font-size: 11px;")
        layout.addWidget(api_key_label, 2, 0)

        self.api_key_display = QLineEdit()
        self.api_key_display.setReadOnly(True)
        self.api_key_display.setPlaceholderText("Not set")
        self.api_key_display.setStyleSheet("""
            QLineEdit {
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.api_key_display, 2, 1)

        # Copy button for API key
        self.copy_key_btn = QPushButton("📋")
        self.copy_key_btn.setMaximumWidth(32)
        self.copy_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
        """)
        self.copy_key_btn.clicked.connect(self._copy_api_key)
        layout.addWidget(self.copy_key_btn, 2, 2, Qt.AlignRight)

        layout.setColumnStretch(1, 1)

        return frame

    def _copy_api_key(self):
        """Copy API key to clipboard"""
        if hasattr(self, '_server_api_key') and self._server_api_key:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._server_api_key)
            self.copy_key_btn.setText("✓")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.copy_key_btn.setText("📋"))

    def _create_expiry_group(self) -> QGroupBox:
        """Create tier expiration group"""
        group = QGroupBox("Tier Expiration")
        layout = QHBoxLayout(group)

        self.expiry_combo = QComboBox()
        self.expiry_combo.addItems(["Never", "Custom Date"])
        self.expiry_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 120px;
            }
        """)
        self.expiry_combo.currentTextChanged.connect(self._on_expiry_changed)
        layout.addWidget(self.expiry_combo)

        self.expiry_date = QDateEdit()
        self.expiry_date.setCalendarPopup(True)
        self.expiry_date.setDate(QDate.currentDate().addMonths(1))
        self.expiry_date.setEnabled(False)
        self.expiry_date.setStyleSheet("""
            QDateEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QDateEdit:disabled {
                background-color: #161B22;
                color: #6B7280;
            }
        """)
        layout.addWidget(self.expiry_date)

        layout.addStretch()

        return group

    def _on_expiry_changed(self, text: str):
        self.expiry_date.setEnabled(text == "Custom Date")

    def _create_actions_group(self) -> QGroupBox:
        """Create account actions group"""
        group = QGroupBox("Account Actions")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)

        self.suspend_btn = QPushButton("Suspend Account")
        self.suspend_btn.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: #000000;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)
        self.suspend_btn.clicked.connect(self._toggle_suspend)
        layout.addWidget(self.suspend_btn)

        regen_btn = QPushButton("Regenerate API Key")
        regen_btn.clicked.connect(self._regenerate_key)
        layout.addWidget(regen_btn)

        delete_btn = QPushButton("Delete User")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                border-color: #EF4444;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        delete_btn.clicked.connect(self._delete_user)
        layout.addWidget(delete_btn)

        layout.addStretch()

        return group

    def _create_audit_group(self) -> QGroupBox:
        """Create audit log group"""
        group = QGroupBox("Audit Log (Recent Changes)")
        layout = QVBoxLayout(group)

        self.audit_table = AuditLogTable([])
        self.audit_table.setMaximumHeight(150)
        layout.addWidget(self.audit_table)

        view_all_btn = QPushButton("View All")
        view_all_btn.setFixedWidth(100)
        view_all_btn.clicked.connect(self._open_audit_log_viewer)
        layout.addWidget(view_all_btn, alignment=Qt.AlignRight)

        return group

    def _open_audit_log_viewer(self):
        """Open the full audit log viewer for this user."""
        if not AUDIT_VIEWER_AVAILABLE:
            QMessageBox.warning(
                self,
                "Not Available",
                "Audit Log Viewer is not available."
            )
            return

        try:
            dialog = AuditLogViewer(user_id=self.user_id, parent=self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening audit log viewer: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Audit Log Viewer: {e}"
            )

    def _load_user_data(self):
        """Load user data from database based on source table"""
        try:
            if self.source == 'customers':
                # Load from SERVER database (Android registrations)
                if not SERVER_DB_PATH.exists():
                    QMessageBox.warning(self, "Error", f"Server database not found: {SERVER_DB_PATH}")
                    return

                conn = sqlite3.connect(str(SERVER_DB_PATH))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Load from unified_users table in server_database.db
                # Note: server_database.db uses 'id' as primary key (not 'user_id')
                cur.execute("""
                    SELECT u.id, u.email, u.name, u.tier, u.created_at,
                           u.api_key, u.email_verified,
                           u.custom_ai_limit, u.custom_trip_days,
                           u.custom_max_vehicles, u.custom_refresh_seconds,
                           u.tier_expires_at
                    FROM unified_users u
                    WHERE u.id = ?
                """, (self.user_id,))

                row = cur.fetchone()
                if not row:
                    QMessageBox.warning(self, "Error", f"Customer not found: {self.user_id}")
                    conn.close()
                    return

                # Build user data from server database
                self.user_data = UserControlData(
                    user_id=row['id'],
                    email=row['email'] or "",
                    name=row['name'] or row['email'] or f"User {row['id']}",
                    tier=row['tier'] or 'free',
                    suspended=not bool(row['email_verified']),
                    suspended_at="",
                    suspension_reason="Pending verification" if not row['email_verified'] else "",
                    created_at=str(row['created_at']) if row['created_at'] else "",
                    custom_ai_limit=row['custom_ai_limit'],
                    custom_trip_days=row['custom_trip_days'],
                    custom_max_vehicles=row['custom_max_vehicles'],
                    custom_refresh_seconds=row['custom_refresh_seconds'],
                    tier_expires_at=row['tier_expires_at'],
                )
                # Store API key for display
                self._server_api_key = row['api_key'] if row['api_key'] else None

                # Load feature overrides if table exists
                try:
                    cur.execute("""
                        SELECT * FROM user_feature_overrides WHERE user_id = ?
                    """, (self.user_id,))
                    override_row = cur.fetchone()
                    if override_row:
                        self._feature_overrides = dict(override_row)
                except sqlite3.OperationalError:
                    pass  # Table doesn't exist yet

                conn.close()

                # Update UI for server users
                self._update_ui_from_data()
                return

            else:
                # Load from LOCAL database (Desktop created users)
                if not DB_PATH.exists():
                    QMessageBox.warning(self, "Error", f"Database not found: {DB_PATH}")
                    return

                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Load from unified_users table (Desktop created users)
                cur.execute("""
                    SELECT user_id, email, name, tier, created_at,
                           suspended, suspended_at, suspension_reason,
                           custom_ai_limit, custom_trip_days, custom_max_vehicles,
                           custom_refresh_seconds, tier_expires_at
                    FROM unified_users
                    WHERE user_id = ?
                """, (self.user_id,))

                row = cur.fetchone()
                if not row:
                    QMessageBox.warning(self, "Error", f"User not found: {self.user_id}")
                    conn.close()
                    return

                # Build user data from unified_users
                self.user_data = UserControlData(
                    user_id=row['user_id'],
                    email=row['email'] or "",
                    name=row['name'] or row['email'] or f"User {row['user_id']}",
                    tier=row['tier'] or 'free',
                    suspended=bool(row['suspended']) if row['suspended'] is not None else False,
                    suspended_at=row['suspended_at'] or "",
                    suspension_reason=row['suspension_reason'] or "",
                    created_at=row['created_at'] or "",
                    custom_ai_limit=row['custom_ai_limit'],
                    custom_trip_days=row['custom_trip_days'],
                    custom_max_vehicles=row['custom_max_vehicles'],
                    custom_refresh_seconds=row['custom_refresh_seconds'],
                    tier_expires_at=row['tier_expires_at'],
                )

            # Get feature overrides
            cur.execute("""
                SELECT obd_dashboard, dtc_read, dtc_clear, ai_chat,
                       predictions, guardian_mode, desktop_sync, pdf_reports, push_alerts
                FROM user_feature_overrides
                WHERE user_id = ?
            """, (self.user_id,))

            override_row = cur.fetchone()
            if override_row:
                for key in ['obd_dashboard', 'dtc_read', 'dtc_clear', 'ai_chat',
                           'predictions', 'guardian_mode', 'desktop_sync', 'pdf_reports', 'push_alerts']:
                    val = override_row[key]
                    self.user_data.feature_overrides[key] = bool(val) if val is not None else None

            # Get today's usage
            today_start = time.time() - (time.time() % 86400)
            cur.execute("""
                SELECT feature, request_count
                FROM usage_counters
                WHERE user_id = ? AND period_start >= ? AND period_type = 'day'
            """, (self.user_id, today_start))

            for urow in cur.fetchall():
                self.user_data.usage_today[urow['feature']] = urow['request_count']

            # Get audit log (last 10 entries)
            cur.execute("""
                SELECT timestamp, action, field_name, old_value, new_value, reason
                FROM subscription_audit_log
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (self.user_id,))

            self.user_data.audit_log = [dict(r) for r in cur.fetchall()]

            conn.close()

            # Update UI
            self._update_ui_from_data()

        except Exception as e:
            logger.error(f"Error loading user data: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load user data: {e}")

    def _update_ui_from_data(self):
        """Update UI elements from user data"""
        if not self.user_data:
            return

        # Header
        self.name_label.setText(self.user_data.name)
        self.email_label.setText(self.user_data.email)
        self.created_label.setText(f"Created: {self.user_data.created_at[:10] if self.user_data.created_at else 'Unknown'}")

        # API Key
        if hasattr(self, '_server_api_key') and self._server_api_key:
            # Show partial key for security
            key = self._server_api_key
            if len(key) > 20:
                display = f"{key[:8]}...{key[-4:]}"
            else:
                display = key
            self.api_key_display.setText(display)
            self.api_key_display.setPlaceholderText("")
        else:
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("Not set - click Regenerate")

        # Status
        if self.user_data.suspended:
            self.status_label.setText("●  Suspended")
            self.status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
            self.suspend_btn.setText("Activate Account")
            self.suspend_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22C55E;
                    color: #000000;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #16A34A;
                }
            """)
        else:
            self.status_label.setText("●  Active")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: bold;")
            self.suspend_btn.setText("Suspend Account")

        # Recreate tier group with correct tier
        layout = self.tier_group.parent().layout()
        idx = layout.indexOf(self.tier_group)
        layout.removeWidget(self.tier_group)
        self.tier_group.deleteLater()
        self.tier_group = TierRadioGroup(self.user_data.tier)
        layout.insertWidget(idx, self.tier_group)

        # Recreate limits group
        idx = layout.indexOf(self.limits_group)
        layout.removeWidget(self.limits_group)
        self.limits_group.deleteLater()
        self.limits_group = UsageLimitsGroup(self.user_data)
        layout.insertWidget(idx, self.limits_group)

        # Recreate features group
        idx = layout.indexOf(self.features_group)
        layout.removeWidget(self.features_group)
        self.features_group.deleteLater()
        self.features_group = FeatureAccessGroup(self.user_data.feature_overrides)
        layout.insertWidget(idx, self.features_group)

        # Recreate usage group
        idx = layout.indexOf(self.usage_group)
        layout.removeWidget(self.usage_group)
        self.usage_group.deleteLater()
        self.usage_group = CurrentUsageGroup(self.user_data.usage_today)
        self.usage_group.usage_reset.connect(self._reset_usage_counter)
        layout.insertWidget(idx, self.usage_group)

        # Update audit table
        self.audit_table.audit_log = self.user_data.audit_log
        self.audit_table._populate()

        # Expiration
        if self.user_data.tier_expires_at:
            self.expiry_combo.setCurrentText("Custom Date")
            try:
                exp_date = datetime.fromisoformat(self.user_data.tier_expires_at)
                self.expiry_date.setDate(QDate(exp_date.year, exp_date.month, exp_date.day))
            except:
                pass
        else:
            self.expiry_combo.setCurrentText("Never")

    def _save_changes(self):
        """Save all changes to database and server"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            admin_id = 1  # Desktop admin ID

            # Get selected tier
            new_tier = self.tier_group.get_selected_tier()

            # Get limit overrides
            limit_overrides = self.limits_group.get_overrides()

            # Get feature overrides
            feature_overrides = self.features_group.get_overrides()

            # Get expiration
            if self.expiry_combo.currentText() == "Never":
                expires_at = None
                expires_timestamp = None
            else:
                qdate = self.expiry_date.date()
                expires_at = f"{qdate.year()}-{qdate.month():02d}-{qdate.day():02d}"
                # Convert to timestamp for customers table
                from datetime import datetime
                expires_timestamp = datetime(qdate.year(), qdate.month(), qdate.day()).timestamp()

            # Handle differently based on source table
            if self.source == 'customers':
                # === SERVER DATABASE (Android users) ===
                conn.close()  # Close the local DB connection

                # Connect to server database instead
                if not SERVER_DB_PATH.exists():
                    raise Exception(f"Server database not found: {SERVER_DB_PATH}")

                conn = sqlite3.connect(str(SERVER_DB_PATH))
                cur = conn.cursor()

                # Update unified_users table in server database (tier + custom limits)
                # Note: server_database.db uses 'id' as primary key (not 'user_id')
                cur.execute("""
                    UPDATE unified_users SET
                        tier = ?,
                        custom_ai_limit = ?,
                        custom_trip_days = ?,
                        custom_max_vehicles = ?,
                        custom_refresh_seconds = ?,
                        tier_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    new_tier,
                    limit_overrides.get('ai_messages_per_day'),
                    limit_overrides.get('trip_history_days'),
                    limit_overrides.get('max_vehicles'),
                    limit_overrides.get('data_refresh_seconds'),
                    expires_at,
                    time.time(),
                    self.user_id
                ))

                # Update feature overrides for Android users
                cur.execute("""
                    INSERT OR IGNORE INTO user_feature_overrides (user_id) VALUES (?)
                """, (self.user_id,))

                cur.execute("""
                    UPDATE user_feature_overrides SET
                        obd_dashboard = ?,
                        dtc_read = ?,
                        dtc_clear = ?,
                        ai_chat = ?,
                        predictions = ?,
                        guardian_mode = ?,
                        desktop_sync = ?,
                        pdf_reports = ?,
                        push_alerts = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE user_id = ?
                """, (
                    feature_overrides.get('obd_dashboard'),
                    feature_overrides.get('dtc_read'),
                    feature_overrides.get('dtc_clear'),
                    feature_overrides.get('ai_chat'),
                    feature_overrides.get('predictions'),
                    feature_overrides.get('guardian_mode'),
                    feature_overrides.get('desktop_sync'),
                    feature_overrides.get('pdf_reports'),
                    feature_overrides.get('push_alerts'),
                    time.time(),
                    admin_id,
                    self.user_id
                ))

                # Log tier change to audit log
                if new_tier != self.user_data.tier:
                    cur.execute("""
                        INSERT INTO subscription_audit_log
                        (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                        VALUES (?, ?, 'tier_change', 'tier', ?, ?, ?)
                    """, (self.user_id, admin_id, self.user_data.tier, new_tier, time.time()))

            else:
                # === UNIFIED_USERS TABLE (Desktop users) ===
                # Update tier if changed
                if new_tier != self.user_data.tier:
                    # Log the change
                    cur.execute("""
                        INSERT INTO subscription_audit_log
                        (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                        VALUES (?, ?, 'tier_change', 'tier', ?, ?, ?)
                    """, (self.user_id, admin_id, self.user_data.tier, new_tier, time.time()))

                    cur.execute("UPDATE unified_users SET tier = ? WHERE user_id = ?",
                               (new_tier, self.user_id))

                # Update custom limits
                cur.execute("""
                    UPDATE unified_users SET
                        custom_ai_limit = ?,
                        custom_trip_days = ?,
                        custom_max_vehicles = ?,
                        custom_refresh_seconds = ?,
                        tier_expires_at = ?
                    WHERE user_id = ?
                """, (
                    limit_overrides.get('ai_messages_per_day'),
                    limit_overrides.get('trip_history_days'),
                    limit_overrides.get('max_vehicles'),
                    limit_overrides.get('data_refresh_seconds'),
                    expires_at,
                    self.user_id
                ))

                # Update feature overrides
                # First, ensure row exists
                cur.execute("""
                    INSERT OR IGNORE INTO user_feature_overrides (user_id) VALUES (?)
                """, (self.user_id,))

                cur.execute("""
                    UPDATE user_feature_overrides SET
                        obd_dashboard = ?,
                        dtc_read = ?,
                        dtc_clear = ?,
                        ai_chat = ?,
                        predictions = ?,
                        guardian_mode = ?,
                        desktop_sync = ?,
                        pdf_reports = ?,
                        push_alerts = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE user_id = ?
                """, (
                    feature_overrides.get('obd_dashboard'),
                    feature_overrides.get('dtc_read'),
                    feature_overrides.get('dtc_clear'),
                    feature_overrides.get('ai_chat'),
                    feature_overrides.get('predictions'),
                    feature_overrides.get('guardian_mode'),
                    feature_overrides.get('desktop_sync'),
                    feature_overrides.get('pdf_reports'),
                    feature_overrides.get('push_alerts'),
                    time.time(),
                    admin_id,
                    self.user_id
                ))

            conn.commit()
            conn.close()

            QMessageBox.information(
                self,
                "Success",
                f"User {self.user_data.email} updated successfully.\n\n"
                "Changes will reflect immediately on the user's Android app."
            )

            self.user_updated.emit(self.user_id)
            self.accept()

        except Exception as e:
            logger.error(f"Error saving changes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")

    def _toggle_suspend(self):
        """Toggle account suspension"""
        if self.user_data.suspended:
            # Activate
            confirm = QMessageBox.question(
                self,
                "Activate Account",
                f"Are you sure you want to activate {self.user_data.email}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

            try:
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()

                cur.execute("""
                    UPDATE unified_users SET suspended = 0, suspended_at = NULL, suspension_reason = NULL
                    WHERE user_id = ?
                """, (self.user_id,))

                cur.execute("""
                    INSERT INTO subscription_audit_log
                    (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                    VALUES (?, 1, 'activate', 'suspended', '1', '0', ?)
                """, (self.user_id, time.time()))

                conn.commit()
                conn.close()

                self.user_data.suspended = False
                self._update_ui_from_data()

                QMessageBox.information(self, "Success", "Account activated.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to activate account: {e}")
        else:
            # Suspend
            confirm = QMessageBox.question(
                self,
                "Suspend Account",
                f"Are you sure you want to suspend {self.user_data.email}?\n\n"
                "The user will immediately lose access to all features.",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

            try:
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()

                cur.execute("""
                    UPDATE unified_users SET suspended = 1, suspended_at = ?
                    WHERE user_id = ?
                """, (time.time(), self.user_id))

                cur.execute("""
                    INSERT INTO subscription_audit_log
                    (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                    VALUES (?, 1, 'suspend', 'suspended', '0', '1', ?)
                """, (self.user_id, time.time()))

                conn.commit()
                conn.close()

                self.user_data.suspended = True
                self._update_ui_from_data()

                QMessageBox.information(self, "Success", "Account suspended.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to suspend account: {e}")

    def _regenerate_key(self):
        """Regenerate user's API key"""
        confirm = QMessageBox.question(
            self,
            "Regenerate API Key",
            f"Are you sure you want to regenerate the API key for {self.user_data.email}?\n\n"
            "The old key will be immediately invalidated.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            import secrets
            import hashlib

            if self.source == 'customers':
                # Generate key with owner_ prefix (matches server's format)
                new_key = f"owner_{secrets.token_urlsafe(32)}"
                key_hash = hashlib.sha256(new_key.encode()).hexdigest()

                # Update in server database (uses 'id' column, not 'user_id')
                if not SERVER_DB_PATH.exists():
                    raise Exception("Server database not found")

                conn = sqlite3.connect(str(SERVER_DB_PATH))
                cur = conn.cursor()
                cur.execute("""
                    UPDATE unified_users SET
                        api_key = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (new_key, time.time(), self.user_id))
                conn.commit()
                conn.close()

                # Also register key in server's api_keys.json for runtime auth
                api_keys_path = Path("C:/OBDserver/Previlium_OBD_Server/config/api_keys.json")
                if api_keys_path.exists():
                    try:
                        with open(api_keys_path, 'r') as f:
                            keys_data = json.load(f)

                        # Revoke old key if exists
                        for existing_hash, kdata in list(keys_data.items()):
                            if kdata.get('email') == self.user_data.email:
                                kdata['status'] = 'revoked'

                        # Add new key
                        keys_data[key_hash] = {
                            "name": self.user_data.name,
                            "email": self.user_data.email,
                            "tier": self.user_data.tier,
                            "role": "owner",
                            "apps": ["obd", "guardian"],
                            "status": "active",
                            "created_at": time.time()
                        }
                        with open(api_keys_path, 'w') as f:
                            json.dump(keys_data, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Could not update api_keys.json: {e}")
            else:
                # Generate key with PREDICT_ prefix for desktop users
                new_key = f"PREDICT_{secrets.token_urlsafe(32)}"
                key_hash = hashlib.sha256(new_key.encode()).hexdigest()

                # Update in local database
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()
                cur.execute("""
                    UPDATE unified_users SET
                        api_key = ?,
                        api_key_hash = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (new_key, key_hash, time.time(), self.user_id))
                conn.commit()
                conn.close()

            # Store for display
            self._server_api_key = new_key

            # Show the new key
            msg = QMessageBox(self)
            msg.setWindowTitle("API Key Regenerated")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"New API key generated for {self.user_data.email}:")
            msg.setInformativeText(
                f"{new_key}\n\n"
                "IMPORTANT: Copy this key now!\n"
                "It will not be shown again for security reasons."
            )
            msg.setDetailedText(f"Full Key:\n{new_key}")

            # Add copy button
            copy_btn = msg.addButton("Copy to Clipboard", QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Ok)
            msg.exec()

            if msg.clickedButton() == copy_btn:
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setText(new_key)
                QMessageBox.information(self, "Copied", "API key copied to clipboard!")

        except Exception as e:
            logger.error(f"Error regenerating API key: {e}")
            QMessageBox.critical(self, "Error", f"Failed to regenerate API key: {e}")

    def _delete_user(self):
        """Delete user account"""
        confirm = QMessageBox.warning(
            self,
            "Delete User",
            f"Are you sure you want to DELETE {self.user_data.email}?\n\n"
            "This action CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # Double confirm
        confirm2 = QMessageBox.critical(
            self,
            "Confirm Deletion",
            f"Type 'DELETE' to confirm deletion of {self.user_data.email}",
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if confirm2 != QMessageBox.Ok:
            return

        try:
            if self.source == 'customers':
                # Android user - soft delete in server database
                if not SERVER_DB_PATH.exists():
                    raise Exception(f"Server database not found: {SERVER_DB_PATH}")
                conn = sqlite3.connect(str(SERVER_DB_PATH))
                cur = conn.cursor()

                # Soft-delete: set status to deleted, revoke API keys
                cur.execute("""
                    UPDATE unified_users SET status = 'deleted', updated_at = ? WHERE id = ?
                """, (time.time(), self.user_id))

                cur.execute("""
                    UPDATE customers SET status = 'deleted', updated_at = ? WHERE id = ?
                """, (time.time(), self.user_id))

                # Revoke API keys
                cur.execute("""
                    UPDATE api_keys SET status = 'revoked', revoked_at = ? WHERE user_id = ?
                """, (time.time(), self.user_id))

                # Also revoke API key in api_keys.json file
                api_keys_path = Path("C:/OBDserver/Previlium_OBD_Server/config/api_keys.json")
                if api_keys_path.exists() and self.user_data.api_key:
                    import json
                    import hashlib
                    key_hash = hashlib.sha256(self.user_data.api_key.encode()).hexdigest()

                    with open(api_keys_path, 'r') as f:
                        keys_data = json.load(f)

                    if key_hash in keys_data:
                        keys_data[key_hash]['status'] = 'revoked'
                        keys_data[key_hash]['revoked_at'] = time.time()

                        with open(api_keys_path, 'w') as f:
                            json.dump(keys_data, f, indent=2)
                        logger.info(f"Revoked API key {key_hash[:16]}... in api_keys.json")

                conn.commit()
                conn.close()

                # Also soft-delete from Desktop's vehicle_profiles.db
                desktop_db = Path("C:/D Drive/Predict/data/vehicle_profiles.db")
                if desktop_db.exists():
                    desktop_conn = sqlite3.connect(str(desktop_db))
                    desktop_cur = desktop_conn.cursor()

                    # Soft-delete from owners table
                    desktop_cur.execute("""
                        UPDATE owners SET is_active = 0, updated_at = ?
                        WHERE owner_id = ?
                    """, (time.time(), self.user_id))

                    # Soft-delete from vehicle_profiles table
                    desktop_cur.execute("""
                        UPDATE vehicle_profiles SET status = 'deleted', updated_at = ?
                        WHERE owner_id = ?
                    """, (time.time(), self.user_id))

                    desktop_conn.commit()
                    desktop_conn.close()
                    logger.info(f"Soft-deleted user {self.user_id} from Desktop database")
            else:
                # Desktop user - soft delete in local database
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()

                cur.execute("""
                    UPDATE unified_users SET status = 'deleted', updated_at = ? WHERE user_id = ?
                """, (time.time(), self.user_id))

                # Log the deletion
                cur.execute("""
                    INSERT INTO subscription_audit_log
                    (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                    VALUES (?, 1, 'delete_account', 'status', 'active', 'deleted', ?)
                """, (self.user_id, time.time()))

                conn.commit()
                conn.close()

            QMessageBox.information(self, "User Deleted",
                f"User {self.user_data.email} has been deleted.\n"
                "Training data and subscription history preserved.")
            self.user_updated.emit(self.user_id)
            self.reject()

        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete user: {e}")

    def _reset_usage_counter(self, feature: str):
        """Reset a specific usage counter"""
        confirm = QMessageBox.question(
            self,
            "Reset Counter",
            f"Reset {feature.replace('_', ' ')} counter for {self.user_data.email}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()

            today_start = time.time() - (time.time() % 86400)
            cur.execute("""
                UPDATE usage_counters SET request_count = 0
                WHERE user_id = ? AND feature = ? AND period_start >= ?
            """, (self.user_id, feature, today_start))

            cur.execute("""
                INSERT INTO subscription_audit_log
                (user_id, admin_id, action, field_name, old_value, new_value, timestamp)
                VALUES (?, 1, 'usage_reset', ?, ?, '0', ?)
            """, (self.user_id, feature, self.user_data.usage_today.get(feature, 0), time.time()))

            conn.commit()
            conn.close()

            self.user_data.usage_today[feature] = 0
            QMessageBox.information(self, "Success", f"{feature} counter reset.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset counter: {e}")


# For standalone testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(13, 17, 23))
    palette.setColor(QPalette.WindowText, QColor(240, 246, 252))
    palette.setColor(QPalette.Base, QColor(22, 27, 34))
    palette.setColor(QPalette.Text, QColor(240, 246, 252))
    app.setPalette(palette)

    # Test with user_id 1
    dialog = UserControlDialog(user_id=1)
    dialog.exec()

    sys.exit(0)
