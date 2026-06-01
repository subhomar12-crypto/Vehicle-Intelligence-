"""
PREDICT - Vehicle Intelligence Platform
Copyright (c) 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Subscription Management Tab

Subscription Management Tab v1.0
Manages user subscription tiers, feature limits, and usage tracking
Controls FREE, PRO, and PREMIUM tier assignments
"""

import logging
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QMessageBox, QTabWidget,
    QScrollArea, QFrame, QSpinBox, QHeaderView, QDialog,
    QDialogButtonBox, QProgressBar, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QBrush

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("C:/OBDserver/Previlium_OBD_Server/data/predict.db")


@dataclass
class SubscriptionUser:
    """User subscription data structure"""
    user_id: int
    email: str
    tier: str
    created_at: str
    last_activity: str = ""
    usage_today: Dict[str, int] = None

    def __post_init__(self):
        if self.usage_today is None:
            self.usage_today = {}


class TierBadge(QLabel):
    """Colored badge for subscription tier display"""

    TIER_COLORS = {
        'free': '#6B7280',      # Gray
        'pro': '#3B82F6',       # Blue
        'premium': '#F59E0B',   # Gold
        'admin': '#C40000'      # Red
    }

    def __init__(self, tier: str, parent=None):
        super().__init__(tier.upper(), parent)
        self.tier = tier
        color = self.TIER_COLORS.get(tier.lower(), '#6B7280')
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedWidth(70)


class UsageBar(QProgressBar):
    """Progress bar showing usage vs limit"""

    def __init__(self, used: int, limit: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self.setTextVisible(True)

        if limit is None or limit == 0:
            # Unlimited or locked
            self.setMaximum(100)
            self.setValue(0)
            self.setFormat("Unlimited" if limit is None else "Locked")
            color = "#22C55E" if limit is None else "#6B7280"
        else:
            self.setMaximum(limit)
            self.setValue(min(used, limit))
            percentage = (used / limit) * 100
            self.setFormat(f"{used}/{limit}")

            if percentage >= 100:
                color = "#EF4444"  # Red
            elif percentage >= 75:
                color = "#F59E0B"  # Yellow
            else:
                color = "#22C55E"  # Green

        self.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: #21262D;
                text-align: center;
                color: white;
                font-size: 10px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)


class TierChangeDialog(QDialog):
    """Dialog for changing user subscription tier"""

    def __init__(self, user: SubscriptionUser, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"Change Tier - {user.email}")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
            }
            QLabel {
                color: #F0F6FC;
                font-size: 12px;
            }
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                min-width: 150px;
            }
            QComboBox:focus {
                border-color: #C40000;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #21262D;
                color: #F0F6FC;
                selection-background-color: #C40000;
            }
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Current tier info
        current_group = QGroupBox("Current Subscription")
        current_layout = QFormLayout(current_group)

        current_layout.addRow("Email:", QLabel(self.user.email))
        current_layout.addRow("Current Tier:", TierBadge(self.user.tier))
        current_layout.addRow("Member Since:", QLabel(self.user.created_at[:10] if self.user.created_at else "Unknown"))

        layout.addWidget(current_group)

        # New tier selection
        change_group = QGroupBox("Change Tier")
        change_layout = QFormLayout(change_group)

        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["free", "pro", "premium", "admin"])
        self.tier_combo.setCurrentText(self.user.tier)
        change_layout.addRow("New Tier:", self.tier_combo)

        # Tier features preview
        self.features_label = QLabel()
        self.features_label.setWordWrap(True)
        self.features_label.setStyleSheet("color: #8B949E; font-size: 11px;")
        self._update_features_preview()
        self.tier_combo.currentTextChanged.connect(self._update_features_preview)
        change_layout.addRow("Features:", self.features_label)

        layout.addWidget(change_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
            QPushButton[text="Save"] {
                background-color: #C40000;
                border-color: #C40000;
            }
            QPushButton[text="Save"]:hover {
                background-color: #A00000;
            }
        """)
        layout.addWidget(button_box)

    def _update_features_preview(self):
        tier = self.tier_combo.currentText()
        features = {
            'free': "All features locked. User cannot access any premium functionality.",
            'pro': "Vehicle Data (100/day), DTC Reading (20/day), AI Chat (10/day), Predictions (10/day), 7-day trip history. NO Guardian access.",
            'premium': "Unlimited Vehicle Data, Unlimited DTC, AI Chat (500/day), Predictions (50/day), 365-day history, FULL Guardian access.",
            'admin': "Unlimited access to all features including admin controls."
        }
        self.features_label.setText(features.get(tier, "Unknown tier"))

    def get_selected_tier(self) -> str:
        return self.tier_combo.currentText()


class LimitOverrideDialog(QDialog):
    """Dialog for overriding specific feature limits"""

    def __init__(self, user: SubscriptionUser, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"Override Limits - {user.email}")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QSpinBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QSpinBox:focus { border-color: #C40000; }
            QCheckBox { color: #F0F6FC; spacing: 8px; }
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Info label
        info = QLabel(f"Override daily limits for {self.user.email}")
        info.setStyleSheet("color: #8B949E; font-size: 11px;")
        layout.addWidget(info)

        # Limits group
        limits_group = QGroupBox("Feature Limits (per day)")
        limits_layout = QFormLayout(limits_group)

        self.limit_inputs = {}
        features = ['vehicle_data', 'llm_chat', 'predict', 'dtc_read']

        for feature in features:
            row_layout = QHBoxLayout()

            spin = QSpinBox()
            spin.setRange(-1, 10000)
            spin.setSpecialValueText("Unlimited")
            spin.setValue(-1)  # -1 means unlimited
            self.limit_inputs[feature] = spin

            row_layout.addWidget(spin)

            # Enable checkbox
            enable_cb = QCheckBox("Override")
            enable_cb.setChecked(False)
            spin.setEnabled(False)
            enable_cb.toggled.connect(lambda checked, s=spin: s.setEnabled(checked))
            row_layout.addWidget(enable_cb)

            self.limit_inputs[f"{feature}_enabled"] = enable_cb

            container = QWidget()
            container.setLayout(row_layout)
            limits_layout.addRow(feature.replace('_', ' ').title() + ":", container)

        layout.addWidget(limits_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_overrides(self) -> Dict[str, Optional[int]]:
        """Get the limit overrides that are enabled"""
        overrides = {}
        for feature in ['vehicle_data', 'llm_chat', 'predict', 'dtc_read']:
            if self.limit_inputs[f"{feature}_enabled"].isChecked():
                value = self.limit_inputs[feature].value()
                overrides[feature] = None if value == -1 else value
        return overrides


class SubscriptionManagementTab(QWidget):
    """Subscription Management Tab - Control user tiers and limits"""

    tier_changed = Signal(int, str)  # user_id, new_tier

    def __init__(self, parent=None):
        super().__init__(parent)
        self.users: List[SubscriptionUser] = []
        self._setup_ui()
        self._load_users()

        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_users)
        self.refresh_timer.start(60000)  # Refresh every 60 seconds

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Subscription Management")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Tier filter
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All Tiers", "free", "pro", "premium", "admin"])
        self.tier_filter.setStyleSheet("""
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 120px;
            }
        """)
        self.tier_filter.currentTextChanged.connect(self._filter_users)
        header_layout.addWidget(QLabel("Filter:"))
        header_layout.addWidget(self.tier_filter)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
        """)
        refresh_btn.clicked.connect(self._load_users)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Stats cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.total_card = self._create_stat_card("Total Users", "0", "#3B82F6")
        self.free_card = self._create_stat_card("Free", "0", "#6B7280")
        self.pro_card = self._create_stat_card("Pro", "0", "#3B82F6")
        self.premium_card = self._create_stat_card("Premium", "0", "#F59E0B")

        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.free_card)
        stats_layout.addWidget(self.pro_card)
        stats_layout.addWidget(self.premium_card)

        layout.addLayout(stats_layout)

        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels([
            "User ID", "Email", "Tier", "Created", "Last Activity", "Usage Today", "Actions"
        ])
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                gridline-color: #21262D;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #21262D;
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
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
            }
        """)

        layout.addWidget(self.users_table)

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a statistics card"""
        card = QFrame()
        card.setFixedHeight(80)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2329;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 9))
        title_label.setStyleSheet("color: #8B949E; border: none;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        value_label.setStyleSheet(f"color: {color}; border: none;")
        value_label.setObjectName("value")
        layout.addWidget(value_label)

        return card

    def _update_stat_card(self, card: QFrame, value: str):
        """Update stat card value"""
        value_label = card.findChild(QLabel, "value")
        if value_label:
            value_label.setText(value)

    def _load_users(self):
        """Load users from database"""
        self.users.clear()

        try:
            if not DB_PATH.exists():
                logger.warning(f"Database not found: {DB_PATH}")
                return

            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Get users with their tiers
            cur.execute("""
                SELECT user_id, email, tier, created_at
                FROM unified_users
                ORDER BY created_at DESC
            """)

            for row in cur.fetchall():
                user = SubscriptionUser(
                    user_id=row['user_id'],
                    email=row['email'] or f"user_{row['user_id']}",
                    tier=row['tier'] or 'free',
                    created_at=row['created_at'] or ""
                )

                # Get today's usage
                import time
                today_start = time.time() - (time.time() % 86400)
                cur.execute("""
                    SELECT feature, request_count
                    FROM usage_counters
                    WHERE user_id = ? AND period_start >= ? AND period_type = 'day'
                """, (user.user_id, today_start))

                user.usage_today = {r['feature']: r['request_count'] for r in cur.fetchall()}
                self.users.append(user)

            conn.close()

            # Update stats
            tier_counts = {'free': 0, 'pro': 0, 'premium': 0, 'admin': 0}
            for user in self.users:
                tier_counts[user.tier] = tier_counts.get(user.tier, 0) + 1

            self._update_stat_card(self.total_card, str(len(self.users)))
            self._update_stat_card(self.free_card, str(tier_counts['free']))
            self._update_stat_card(self.pro_card, str(tier_counts['pro']))
            self._update_stat_card(self.premium_card, str(tier_counts['premium']))

            self._populate_table()

        except Exception as e:
            logger.error(f"Error loading users: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load users: {e}")

    def _populate_table(self):
        """Populate the users table"""
        filter_tier = self.tier_filter.currentText()
        filtered_users = [u for u in self.users if filter_tier == "All Tiers" or u.tier == filter_tier]

        self.users_table.setRowCount(len(filtered_users))

        for row, user in enumerate(filtered_users):
            # User ID
            id_item = QTableWidgetItem(str(user.user_id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.users_table.setItem(row, 0, id_item)

            # Email
            self.users_table.setItem(row, 1, QTableWidgetItem(user.email))

            # Tier badge
            tier_widget = QWidget()
            tier_layout = QHBoxLayout(tier_widget)
            tier_layout.setContentsMargins(4, 4, 4, 4)
            tier_layout.addWidget(TierBadge(user.tier))
            tier_layout.addStretch()
            self.users_table.setCellWidget(row, 2, tier_widget)

            # Created
            created = user.created_at[:10] if user.created_at else "Unknown"
            self.users_table.setItem(row, 3, QTableWidgetItem(created))

            # Last activity
            self.users_table.setItem(row, 4, QTableWidgetItem(user.last_activity or "N/A"))

            # Usage summary
            usage_text = ", ".join([f"{k}: {v}" for k, v in user.usage_today.items()]) or "No usage today"
            self.users_table.setItem(row, 5, QTableWidgetItem(usage_text))

            # Action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(4)

            change_tier_btn = QPushButton("Change Tier")
            change_tier_btn.setStyleSheet("""
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #A00000;
                }
            """)
            change_tier_btn.clicked.connect(lambda checked, u=user: self._change_tier(u))
            actions_layout.addWidget(change_tier_btn)

            override_btn = QPushButton("Limits")
            override_btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                }
            """)
            override_btn.clicked.connect(lambda checked, u=user: self._override_limits(u))
            actions_layout.addWidget(override_btn)

            actions_layout.addStretch()
            self.users_table.setCellWidget(row, 6, actions_widget)

        self.users_table.resizeRowsToContents()

    def _filter_users(self):
        """Filter users by tier"""
        self._populate_table()

    def _change_tier(self, user: SubscriptionUser):
        """Open dialog to change user tier"""
        dialog = TierChangeDialog(user, self)
        if dialog.exec() == QDialog.Accepted:
            new_tier = dialog.get_selected_tier()
            if new_tier != user.tier:
                self._update_user_tier(user, new_tier)

    def _update_user_tier(self, user: SubscriptionUser, new_tier: str):
        """Update user tier in database"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()

            # Update tier
            cur.execute("UPDATE unified_users SET tier = ? WHERE user_id = ?", (new_tier, user.user_id))

            # Get new entitlements and limits
            cur.execute("SELECT features, default_limits FROM tier_presets WHERE tier_name = ?", (new_tier,))
            row = cur.fetchone()

            if row:
                features = json.loads(row[0]) if row[0] else []
                limits = json.loads(row[1]) if row[1] else {}

                # Update entitlements
                for feature in ['vehicle_data', 'llm_chat', 'predict', 'dtc_read', 'guardian', 'admin']:
                    enabled = feature in features
                    cur.execute("""
                        INSERT INTO entitlements (user_id, feature, enabled)
                        VALUES (?, ?, ?)
                        ON CONFLICT(user_id, feature) DO UPDATE SET enabled = ?
                    """, (user.user_id, feature, enabled, enabled))

                # Update rate limits
                for feature, limit_info in limits.items():
                    max_val = limit_info.get('max')
                    period = limit_info.get('period', 'day')
                    cur.execute("""
                        INSERT INTO rate_limits (user_id, feature, max_requests, period)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id, feature) DO UPDATE SET max_requests = ?, period = ?
                    """, (user.user_id, feature, max_val, period, max_val, period))

            conn.commit()
            conn.close()

            QMessageBox.information(
                self,
                "Success",
                f"User {user.email} tier changed from {user.tier.upper()} to {new_tier.upper()}"
            )

            self.tier_changed.emit(user.user_id, new_tier)
            self._load_users()

        except Exception as e:
            logger.error(f"Error updating tier: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update tier: {e}")

    def _override_limits(self, user: SubscriptionUser):
        """Open dialog to override specific limits"""
        dialog = LimitOverrideDialog(user, self)
        if dialog.exec() == QDialog.Accepted:
            overrides = dialog.get_overrides()
            if overrides:
                self._apply_limit_overrides(user, overrides)

    def _apply_limit_overrides(self, user: SubscriptionUser, overrides: Dict[str, Optional[int]]):
        """Apply limit overrides to database"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()

            for feature, limit in overrides.items():
                cur.execute("""
                    INSERT INTO rate_limits (user_id, feature, max_requests, period)
                    VALUES (?, ?, ?, 'day')
                    ON CONFLICT(user_id, feature) DO UPDATE SET max_requests = ?
                """, (user.user_id, feature, limit, limit))

            conn.commit()
            conn.close()

            QMessageBox.information(
                self,
                "Success",
                f"Limit overrides applied for {user.email}"
            )

        except Exception as e:
            logger.error(f"Error applying overrides: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply overrides: {e}")


# For testing standalone
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(13, 17, 23))
    palette.setColor(QPalette.WindowText, QColor(240, 246, 252))
    palette.setColor(QPalette.Base, QColor(22, 27, 34))
    palette.setColor(QPalette.Text, QColor(240, 246, 252))
    app.setPalette(palette)

    window = SubscriptionManagementTab()
    window.setWindowTitle("Subscription Management")
    window.resize(1200, 700)
    window.show()

    sys.exit(app.exec())
