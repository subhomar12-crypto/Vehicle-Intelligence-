"""
Subscription tab for tier and subscription management.

Combines customer subscription view with admin tier management.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QGroupBox, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class SubscriptionTab(QWidget):
    """
    Tab for subscription and tier management.
    
    Features:
    - Customer subscription view
    - Admin tier management
    - Stat cards for overview
    - Filter and search capabilities
    """
    
    # Tier change signal
    tier_changed = Signal(int, str)  # user_id, new_tier
    
    # Subscription tiers
    TIERS = ["free", "pro", "premium", "admin"]
    
    # Status options
    STATUSES = ["All", "Active", "Expired", "Pending", "Cancelled"]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._subscriptions: List[Dict[str, Any]] = []
        self._users: List[Dict[str, Any]] = []
        self._is_admin = True  # Assume admin for now
        self._setup_ui()
        self._load_sample_data()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Subscription Management")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Sub-tabs for My Subscription vs Admin Management
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{
                padding: 10px 20px;
                font-weight: bold;
            }}
        """)
        
        # My Subscription tab
        my_sub_widget = self._create_my_subscription_tab()
        self.tabs.addTab(my_sub_widget, "My Subscription")
        
        # Admin Management tab
        if self._is_admin:
            admin_widget = self._create_admin_tab()
            self.tabs.addTab(admin_widget, "Admin: Manage Tiers")
        
        layout.addWidget(self.tabs)
    
    def _create_my_subscription_tab(self) -> QWidget:
        """Create 'My Subscription' tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 15, 0, 0)
        
        # Current plan card
        plan_group = QGroupBox("Current Plan")
        plan_group.setStyleSheet(PredictTheme.get_card_stylesheet(PredictTheme.PRIMARY))
        plan_layout = QGridLayout(plan_group)
        
        self.my_plan_label = QLabel("Premium")
        self.my_plan_label.setStyleSheet(f"color: {PredictTheme.PRIMARY}; font-size: 24px; font-weight: bold;")
        plan_layout.addWidget(QLabel("Plan:"), 0, 0)
        plan_layout.addWidget(self.my_plan_label, 0, 1)
        
        self.my_status_label = QLabel("Active")
        self.my_status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
        plan_layout.addWidget(QLabel("Status:"), 1, 0)
        plan_layout.addWidget(self.my_status_label, 1, 1)
        
        self.my_expiry_label = QLabel("2024-12-31")
        plan_layout.addWidget(QLabel("Expires:"), 2, 0)
        plan_layout.addWidget(self.my_expiry_label, 2, 1)
        
        self.my_payment_label = QLabel("Paid")
        plan_layout.addWidget(QLabel("Payment:"), 3, 0)
        plan_layout.addWidget(self.my_payment_label, 3, 1)
        
        # Days remaining
        days_remaining = 285
        days_widget = QFrame()
        days_widget.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {PredictTheme.SUCCESS};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        days_layout = QVBoxLayout(days_widget)
        
        days_value = QLabel(str(days_remaining))
        days_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        days_value.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-size: 32px; font-weight: bold;")
        days_layout.addWidget(days_value)
        
        days_text = QLabel("Days Remaining")
        days_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        days_text.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
        days_layout.addWidget(days_text)
        
        plan_layout.addWidget(days_widget, 0, 2, 4, 1)
        
        layout.addWidget(plan_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        upgrade_btn = QPushButton("Upgrade Plan")
        upgrade_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
        """)
        upgrade_btn.clicked.connect(self._upgrade_plan)
        actions_layout.addWidget(upgrade_btn)
        
        renew_btn = QPushButton("Renew Subscription")
        renew_btn.clicked.connect(self._renew_subscription)
        actions_layout.addWidget(renew_btn)
        
        cancel_btn = QPushButton("Cancel Subscription")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.DANGER};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }}
        """)
        cancel_btn.clicked.connect(self._cancel_subscription)
        actions_layout.addWidget(cancel_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Features list
        features_group = QGroupBox("Plan Features")
        features_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        features_layout = QVBoxLayout(features_group)
        
        features = [
            "✓ Unlimited OBD readings",
            "✓ AI-powered diagnostics",
            "✓ Predictive maintenance alerts",
            "✓ Up to 5 vehicles",
            "✓ Mobile app access",
            "✓ Cloud data sync",
            "✓ Priority support",
        ]
        
        for feature in features:
            lbl = QLabel(feature)
            lbl.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; padding: 5px;")
            features_layout.addWidget(lbl)
        
        layout.addWidget(features_group)
        layout.addStretch()
        
        return widget
    
    def _create_admin_tab(self) -> QWidget:
        """Create admin tier management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 15, 0, 0)
        
        # Stats row
        stats_layout = QHBoxLayout()
        
        stat_configs = [
            ("Total Users", "156", "#6F42C1"),  # Purple
            ("Active", "134", "#198754"),       # Green
            ("Trial", "12", "#0D6EFD"),         # Blue
            ("Expired", "8", "#DC3545"),        # Red
            ("MRR", "$2,450", "#FF9800"),       # Orange
        ]
        
        self.stat_cards = []
        for title, value, color in stat_configs:
            card = self._create_stat_card(title, value, color)
            stats_layout.addWidget(card)
            self.stat_cards.append(card)
        
        layout.addLayout(stats_layout)
        
        # Filter bar
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(self.STATUSES)
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addWidget(QLabel("Tier:"))
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All Tiers"] + self.TIERS)
        self.tier_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.tier_filter)
        
        filter_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_users)
        filter_layout.addWidget(refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels([
            "User ID", "Email", "Tier", "Created", "Last Activity", "Usage Today", "Actions"
        ])
        self.users_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        layout.addWidget(self.users_table)
        
        return widget
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a stat card widget."""
        card = QFrame()
        card.setFixedHeight(80)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}; font-size: 9px;")
        title_lbl.setFont(QFont(PredictTheme.FONT_FAMILY, 9))
        layout.addWidget(title_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
        value_lbl.setFont(QFont(PredictTheme.FONT_FAMILY, 20, QFont.Weight.Bold))
        layout.addWidget(value_lbl)
        
        return card
    
    def _load_sample_data(self) -> None:
        """Load sample subscription and user data."""
        self._subscriptions = [
            {
                "id": 1,
                "customer": "John Doe",
                "plan": "Premium",
                "status": "Active",
                "expires": "2024-12-31",
                "payment": "Paid",
            },
            {
                "id": 2,
                "customer": "Jane Smith",
                "plan": "Pro",
                "status": "Active",
                "expires": "2024-10-15",
                "payment": "Paid",
            },
        ]
        
        self._users = [
            {
                "id": 1,
                "email": "john.doe@example.com",
                "tier": "premium",
                "created": "2023-06-15",
                "last_activity": "2024-01-15 10:30",
                "usage_today": 145,
            },
            {
                "id": 2,
                "email": "jane.smith@example.com",
                "tier": "pro",
                "created": "2023-08-20",
                "last_activity": "2024-01-15 09:15",
                "usage_today": 89,
            },
            {
                "id": 3,
                "email": "bob.wilson@example.com",
                "tier": "free",
                "created": "2024-01-10",
                "last_activity": "2024-01-14 16:45",
                "usage_today": 23,
            },
        ]
        
        self._update_users_table()
    
    def _update_users_table(self) -> None:
        """Update users table with current data."""
        self.users_table.setRowCount(len(self._users))
        
        for row, user in enumerate(self._users):
            # User ID
            item = QTableWidgetItem(str(user["id"]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.users_table.setItem(row, 0, item)
            
            # Email
            item = QTableWidgetItem(user["email"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.users_table.setItem(row, 1, item)
            
            # Tier
            tier = user["tier"]
            item = QTableWidgetItem(tier.upper())
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if tier == "premium":
                item.setForeground(QColor(PredictTheme.ACCENT_AMBER))
            elif tier == "pro":
                item.setForeground(QColor(PredictTheme.ACCENT_CYAN))
            elif tier == "admin":
                item.setForeground(QColor(PredictTheme.DANGER))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.users_table.setItem(row, 2, item)
            
            # Created
            item = QTableWidgetItem(user["created"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.users_table.setItem(row, 3, item)
            
            # Last Activity
            item = QTableWidgetItem(user["last_activity"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.users_table.setItem(row, 4, item)
            
            # Usage
            item = QTableWidgetItem(str(user["usage_today"]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.users_table.setItem(row, 5, item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 2, 5, 2)
            
            change_tier_btn = QPushButton("Change Tier")
            change_tier_btn.setFixedWidth(90)
            change_tier_btn.clicked.connect(lambda checked, uid=user["id"]: self._change_user_tier(uid))
            actions_layout.addWidget(change_tier_btn)
            
            actions_layout.addStretch()
            self.users_table.setCellWidget(row, 6, actions_widget)
        
        self.users_table.resizeColumnsToContents()
    
    def _apply_filters(self) -> None:
        """Apply status and tier filters."""
        # In a real implementation, this would filter the table
        logger.debug(f"Filters: status={self.status_filter.currentText()}, tier={self.tier_filter.currentText()}")
    
    def _refresh_users(self) -> None:
        """Refresh user list."""
        logger.info("Refreshing user list")
        self._update_users_table()
    
    def _change_user_tier(self, user_id: int) -> None:
        """Open dialog to change user tier."""
        tiers = self.TIERS
        current_tier = next((u["tier"] for u in self._users if u["id"] == user_id), "free")
        
        tier, ok = QInputDialog.getItem(
            self, "Change Tier", "Select new tier:",
            tiers, tiers.index(current_tier), False
        )
        
        if ok and tier:
            # Update user
            for user in self._users:
                if user["id"] == user_id:
                    user["tier"] = tier
                    break
            
            self._update_users_table()
            self.tier_changed.emit(user_id, tier)
            logger.info(f"Changed user {user_id} tier to {tier}")
    
    def _upgrade_plan(self) -> None:
        """Handle upgrade plan button."""
        QMessageBox.information(self, "Upgrade", "Contact sales to upgrade your plan.")
    
    def _renew_subscription(self) -> None:
        """Handle renew subscription button."""
        reply = QMessageBox.question(
            self, "Renew Subscription",
            "Renew your Premium subscription for $29.99/month?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Renewed", "Your subscription has been renewed!")
    
    def _cancel_subscription(self) -> None:
        """Handle cancel subscription button."""
        reply = QMessageBox.warning(
            self, "Cancel Subscription",
            "Are you sure you want to cancel? Your access will continue until the end of the billing period.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Cancelled", "Your subscription has been cancelled.")
