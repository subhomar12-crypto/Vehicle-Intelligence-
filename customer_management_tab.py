"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Customer Management Tab

Predict OBD - Customer Management Tab
Comprehensive UI for managing customer profiles, vehicles, and API keys.

Features:
- View and manage customer profiles
- View customer vehicles
- Manage API keys per customer
- View customer data usage
- GDPR data export/deletion
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QGridLayout, QComboBox, QLineEdit, QMessageBox,
    QDialog, QFormLayout, QTextEdit, QTabWidget, QFrame,
    QSplitter, QListWidget, QListWidgetItem, QCheckBox,
    QInputDialog, QFileDialog, QProgressBar
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt, QTimer, Signal

from ui_common import ProfessionalTheme
from config import get_config
from directory_manager import DirectoryManager
from customer_isolation import get_isolation_enforcer
from audit_logger import log_audit_event, AuditEventType
from user_control_dialog import UserControlDialog


class CustomerManagementTab(QWidget):
    """
    Customer Management Tab for administering customer profiles.
    """

    customer_updated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.dir_manager = DirectoryManager()
        self.isolator = get_isolation_enforcer()
        self._selected_customer = None

        self._build_ui()
        self._load_customers()

        # Auto-refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_customers)
        self.refresh_timer.start(60000)

    def _build_ui(self):
        """Build the customer management UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left - Customer list
        left_panel = self._create_customer_list_panel()
        splitter.addWidget(left_panel)

        # Right - Customer details with tabs
        right_panel = self._create_details_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([350, 650])
        layout.addWidget(splitter, 1)

    def _create_header(self) -> QWidget:
        """Create header with title and actions."""
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {ProfessionalTheme.CARD_BG};
                border-radius: 10px;
                padding: 15px;
            }}
        """)

        layout = QHBoxLayout(header)

        title = QLabel("Customer Management")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {ProfessionalTheme.TEXT_PRIMARY};")
        layout.addWidget(title)

        layout.addStretch()

        # Search
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search customers...")
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ProfessionalTheme.BACKGROUND};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.CARD_BG};
                border-radius: 5px;
                padding: 8px;
                min-width: 200px;
            }}
        """)
        self.txt_search.textChanged.connect(self._filter_customers)
        layout.addWidget(self.txt_search)

        self.btn_manage_user = QPushButton("Manage User")
        self.btn_manage_user.setStyleSheet(self._get_button_style('warning'))
        self.btn_manage_user.clicked.connect(self._open_user_control_dialog)
        self.btn_manage_user.setEnabled(False)  # Enable when customer selected
        layout.addWidget(self.btn_manage_user)

        self.btn_add = QPushButton("+ Add Customer")
        self.btn_add.setStyleSheet(self._get_button_style('success'))
        self.btn_add.clicked.connect(self._add_customer)
        layout.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(self._get_button_style('info'))
        self.btn_refresh.clicked.connect(self._load_customers)
        layout.addWidget(self.btn_refresh)

        return header

    def _create_customer_list_panel(self) -> QWidget:
        """Create customer list panel."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {ProfessionalTheme.CARD_BG};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        # Customer table - shows ALL users from server (Android + Desktop)
        self.customer_table = QTableWidget()
        self.customer_table.setColumnCount(6)
        self.customer_table.setHorizontalHeaderLabels([
            "ID", "Name", "Status", "Tier", "Source", "Email"
        ])
        self.customer_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.customer_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.customer_table.setSelectionMode(QTableWidget.SingleSelection)
        self.customer_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.customer_table.doubleClicked.connect(self._on_customer_double_click)
        self.customer_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customer_table.customContextMenuRequested.connect(self._show_customer_context_menu)
        self.customer_table.setStyleSheet(self._get_table_style())
        layout.addWidget(self.customer_table)

        return panel

    def _create_details_panel(self) -> QWidget:
        """Create customer details panel with tabs."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {ProfessionalTheme.CARD_BG};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        # Tab widget for different sections
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {ProfessionalTheme.CARD_BG};
                background-color: {ProfessionalTheme.BACKGROUND};
            }}
            QTabBar::tab {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                padding: 10px 20px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }}
            QTabBar::tab:selected {{
                background-color: {ProfessionalTheme.PRIMARY};
            }}
        """)

        # Profile tab
        self.profile_tab = self._create_profile_tab()
        self.tabs.addTab(self.profile_tab, "Profile")

        # Subscription tab (tier management)
        self.subscription_tab = self._create_subscription_tab()
        self.tabs.addTab(self.subscription_tab, "Subscription")

        # Vehicles tab
        self.vehicles_tab = self._create_vehicles_tab()
        self.tabs.addTab(self.vehicles_tab, "Vehicles")

        # API Keys tab
        self.api_keys_tab = self._create_api_keys_tab()
        self.tabs.addTab(self.api_keys_tab, "API Keys")

        # Data & GDPR tab
        self.data_tab = self._create_data_tab()
        self.tabs.addTab(self.data_tab, "Data & GDPR")

        layout.addWidget(self.tabs)

        return panel

    def _create_profile_tab(self) -> QWidget:
        """Create profile details tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Profile info
        info_group = QGroupBox("Customer Information")
        info_group.setStyleSheet(self._get_group_style())
        form = QFormLayout(info_group)

        self.lbl_customer_id = QLabel("-")
        form.addRow("Customer ID:", self.lbl_customer_id)

        self.txt_name = QLineEdit()
        form.addRow("Name:", self.txt_name)

        self.txt_email = QLineEdit()
        form.addRow("Email:", self.txt_email)

        self.txt_phone = QLineEdit()
        form.addRow("Phone:", self.txt_phone)

        self.lbl_created = QLabel("-")
        form.addRow("Created:", self.lbl_created)

        self.lbl_status = QLabel("-")
        form.addRow("Status:", self.lbl_status)

        layout.addWidget(info_group)

        # Save button
        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet(self._get_button_style('success'))
        btn_save.clicked.connect(self._save_profile)
        layout.addWidget(btn_save)

        layout.addStretch()

        return widget

    def _create_vehicles_tab(self) -> QWidget:
        """Create vehicles tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Vehicles table
        self.vehicles_table = QTableWidget()
        self.vehicles_table.setColumnCount(4)
        self.vehicles_table.setHorizontalHeaderLabels([
            "Vehicle ID", "VIN", "Make/Model", "Created"
        ])
        self.vehicles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vehicles_table.setStyleSheet(self._get_table_style())
        layout.addWidget(self.vehicles_table)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_add_vehicle = QPushButton("Add Vehicle")
        btn_add_vehicle.setStyleSheet(self._get_button_style('success'))
        btn_add_vehicle.clicked.connect(self._add_vehicle)
        btn_layout.addWidget(btn_add_vehicle)

        btn_remove_vehicle = QPushButton("Remove Vehicle")
        btn_remove_vehicle.setStyleSheet(self._get_button_style('danger'))
        btn_remove_vehicle.clicked.connect(self._remove_vehicle)
        btn_layout.addWidget(btn_remove_vehicle)

        layout.addLayout(btn_layout)

        return widget

    def _create_api_keys_tab(self) -> QWidget:
        """Create API keys management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # API keys table
        self.api_keys_table = QTableWidget()
        self.api_keys_table.setColumnCount(4)
        self.api_keys_table.setHorizontalHeaderLabels([
            "Key ID", "Name", "Created", "Status"
        ])
        self.api_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.api_keys_table.setStyleSheet(self._get_table_style())
        layout.addWidget(self.api_keys_table)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_generate = QPushButton("Generate New Key")
        btn_generate.setStyleSheet(self._get_button_style('success'))
        btn_generate.clicked.connect(self._generate_api_key)
        btn_layout.addWidget(btn_generate)

        btn_revoke = QPushButton("Revoke Selected")
        btn_revoke.setStyleSheet(self._get_button_style('danger'))
        btn_revoke.clicked.connect(self._revoke_api_key)
        btn_layout.addWidget(btn_revoke)

        layout.addLayout(btn_layout)

        return widget

    def _create_subscription_tab(self) -> QWidget:
        """Create subscription/tier management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Current Tier section
        tier_group = QGroupBox("Current Subscription")
        tier_group.setStyleSheet(self._get_group_style())
        tier_layout = QFormLayout(tier_group)

        self.lbl_current_tier = QLabel("-")
        self.lbl_current_tier.setStyleSheet("font-size: 18px; font-weight: bold;")
        tier_layout.addRow("Current Tier:", self.lbl_current_tier)

        self.lbl_tier_expiry = QLabel("-")
        tier_layout.addRow("Expires:", self.lbl_tier_expiry)

        self.lbl_predictions_used = QLabel("-")
        tier_layout.addRow("Predictions Used:", self.lbl_predictions_used)

        layout.addWidget(tier_group)

        # Upgrade section
        upgrade_group = QGroupBox("Change Subscription")
        upgrade_group.setStyleSheet(self._get_group_style())
        upgrade_layout = QVBoxLayout(upgrade_group)

        # Tier selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("New Tier:"))

        self.combo_tier = QComboBox()
        self.combo_tier.addItem("Free (0 QR)", "free")
        self.combo_tier.addItem("Basic - 100 QR/year", "basic")
        self.combo_tier.addItem("Premium - 500 QR/year", "premium")
        self.combo_tier.setStyleSheet(f"""
            QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.TEXT_SECONDARY};
                border-radius: 5px;
                padding: 8px;
                min-width: 200px;
            }}
        """)
        selector_layout.addWidget(self.combo_tier)
        selector_layout.addStretch()
        upgrade_layout.addLayout(selector_layout)

        # Tier features display
        self.lbl_tier_features = QLabel("")
        self.lbl_tier_features.setWordWrap(True)
        self.lbl_tier_features.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; padding: 10px;")
        upgrade_layout.addWidget(self.lbl_tier_features)
        self.combo_tier.currentIndexChanged.connect(self._update_tier_features_display)
        self._update_tier_features_display()

        # Upgrade button
        btn_upgrade = QPushButton("Apply Tier Change")
        btn_upgrade.setStyleSheet(self._get_button_style('success'))
        btn_upgrade.clicked.connect(self._apply_tier_change)
        upgrade_layout.addWidget(btn_upgrade)

        layout.addWidget(upgrade_group)

        # Tier pricing info
        info_group = QGroupBox("Tier Information")
        info_group.setStyleSheet(self._get_group_style())
        info_layout = QVBoxLayout(info_group)

        info_text = """
        <b>Free Tier (0 QR)</b><br>
        - OBD Connection<br>
        - View Diagnostic Codes (DTCs)<br><br>

        <b>Basic Tier (100 QR/year)</b><br>
        - All Free features<br>
        - AI Chat Assistant<br>
        - 3 Predictions per month<br><br>

        <b>Premium Tier (500 QR/year)</b><br>
        - All Basic features<br>
        - Unlimited Predictions<br>
        - Priority Support<br>
        - Advanced Analytics
        """
        info_label = QLabel(info_text)
        info_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_PRIMARY}; padding: 10px;")
        info_layout.addWidget(info_label)

        layout.addWidget(info_group)

        layout.addStretch()
        return widget

    def _update_tier_features_display(self):
        """Update the tier features display based on selection."""
        tier_features = {
            "free": "Features: OBD Connection, View DTCs",
            "basic": "Features: OBD Connection, View DTCs, AI Chat, 3 Predictions/month",
            "premium": "Features: OBD Connection, View DTCs, AI Chat, Unlimited Predictions, Priority Support"
        }
        tier = self.combo_tier.currentData()
        self.lbl_tier_features.setText(tier_features.get(tier, ""))

    def _apply_tier_change(self):
        """Apply the selected tier change to the customer."""
        if not self._selected_customer:
            QMessageBox.warning(self, "No Customer", "Please select a customer first.")
            return

        new_tier = self.combo_tier.currentData()
        customer_id = self._selected_customer.get('id')

        if not customer_id:
            QMessageBox.warning(self, "Error", "Invalid customer ID")
            return

        # Confirm change
        reply = QMessageBox.question(
            self, "Confirm Tier Change",
            f"Change tier to {new_tier.upper()} for customer:\n"
            f"{self._selected_customer.get('name', '')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            import sys
            sys.path.insert(0, str(self.config.SERVER_PATH))
            from database import update_customer_tier
            import time

            # Calculate expiry (1 year for paid tiers)
            if new_tier in ['basic', 'premium']:
                expiry = time.time() + (365 * 24 * 60 * 60)
            else:
                expiry = 0

            if update_customer_tier(customer_id, new_tier, expiry):
                # Try to send email notification
                if new_tier in ['basic', 'premium']:
                    try:
                        from email_service import send_tier_upgrade_email
                        expiry_date = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')
                        send_tier_upgrade_email(
                            self._selected_customer.get('email', ''),
                            self._selected_customer.get('name', ''),
                            new_tier,
                            expiry_date
                        )
                    except Exception as e:
                        pass  # Email sending is optional

                QMessageBox.information(
                    self, "Success",
                    f"Customer tier updated to {new_tier.upper()}!"
                )
                # Refresh customer data
                self._selected_customer['tier'] = new_tier
                self._selected_customer['tier_expiry'] = expiry
                self._update_subscription_display()
            else:
                QMessageBox.warning(self, "Error", "Failed to update tier")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update tier: {str(e)}")

    def _update_subscription_display(self):
        """Update the subscription tab display for selected customer."""
        if not self._selected_customer:
            self.lbl_current_tier.setText("-")
            self.lbl_tier_expiry.setText("-")
            self.lbl_predictions_used.setText("-")
            return

        tier = self._selected_customer.get('tier', 'free')
        tier_colors = {
            'free': ProfessionalTheme.TEXT_SECONDARY,
            'basic': '#D29922',  # Yellow
            'premium': '#A371F7'  # Purple
        }
        color = tier_colors.get(tier, ProfessionalTheme.TEXT_PRIMARY)
        self.lbl_current_tier.setText(f"<span style='color: {color};'>{tier.upper()}</span>")

        # Expiry
        expiry = self._selected_customer.get('tier_expiry')
        if expiry and tier in ['basic', 'premium']:
            expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')
            self.lbl_tier_expiry.setText(expiry_str)
        else:
            self.lbl_tier_expiry.setText("N/A" if tier == 'free' else "-")

        # Predictions used
        predictions_used = self._selected_customer.get('predictions_used', 0)
        if tier == 'basic':
            self.lbl_predictions_used.setText(f"{predictions_used} / 3 (monthly)")
        elif tier == 'premium':
            self.lbl_predictions_used.setText("Unlimited")
        else:
            self.lbl_predictions_used.setText("N/A (upgrade to use)")

        # Set combo to current tier
        for i in range(self.combo_tier.count()):
            if self.combo_tier.itemData(i) == tier:
                self.combo_tier.setCurrentIndex(i)
                break

    def _create_data_tab(self) -> QWidget:
        """Create data management and GDPR tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Data summary
        summary_group = QGroupBox("Data Summary")
        summary_group.setStyleSheet(self._get_group_style())
        summary_layout = QGridLayout(summary_group)

        self.lbl_data_size = QLabel("-")
        summary_layout.addWidget(QLabel("Total Data Size:"), 0, 0)
        summary_layout.addWidget(self.lbl_data_size, 0, 1)

        self.lbl_vehicle_count = QLabel("-")
        summary_layout.addWidget(QLabel("Vehicles:"), 1, 0)
        summary_layout.addWidget(self.lbl_vehicle_count, 1, 1)

        self.lbl_trip_count = QLabel("-")
        summary_layout.addWidget(QLabel("Trips Recorded:"), 2, 0)
        summary_layout.addWidget(self.lbl_trip_count, 2, 1)

        layout.addWidget(summary_group)

        # GDPR Actions
        gdpr_group = QGroupBox("GDPR Compliance Actions")
        gdpr_group.setStyleSheet(self._get_group_style())
        gdpr_layout = QVBoxLayout(gdpr_group)

        btn_export = QPushButton("Export All Customer Data (GDPR)")
        btn_export.setStyleSheet(self._get_button_style('info'))
        btn_export.clicked.connect(self._export_customer_data)
        gdpr_layout.addWidget(btn_export)

        btn_anonymize = QPushButton("Anonymize Personal Data")
        btn_anonymize.setStyleSheet(self._get_button_style('warning'))
        btn_anonymize.clicked.connect(self._anonymize_data)
        gdpr_layout.addWidget(btn_anonymize)

        btn_delete = QPushButton("Delete Customer (Soft Delete - 30 day recovery)")
        btn_delete.setStyleSheet(self._get_button_style('danger'))
        btn_delete.clicked.connect(self._soft_delete_customer)
        gdpr_layout.addWidget(btn_delete)

        btn_permanent = QPushButton("PERMANENT DELETE (No Recovery)")
        btn_permanent.setStyleSheet(f"""
            QPushButton {{
                background-color: #8B0000;
                color: white;
                border: 2px solid {ProfessionalTheme.DANGER};
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }}
        """)
        btn_permanent.clicked.connect(self._permanent_delete_customer)
        gdpr_layout.addWidget(btn_permanent)

        layout.addWidget(gdpr_group)
        layout.addStretch()

        return widget

    def _load_customers(self):
        """Load all customers from SERVER (Android + Desktop users)."""
        self.customer_table.setRowCount(0)

        # Fetch from server instead of local filesystem
        try:
            from server_api_client import ServerAPIClient
            client = ServerAPIClient()

            # Call the new combined endpoint that returns all users
            response = client._make_request("GET", "/api/admin/all-users")

            if response.success and response.data:
                users = response.data.get('users', [])
                for user in users:
                    row = self.customer_table.rowCount()
                    self.customer_table.insertRow(row)

                    # Column 0: ID
                    self.customer_table.setItem(row, 0, QTableWidgetItem(str(user.get('user_id', ''))))

                    # Column 1: Name
                    self.customer_table.setItem(row, 1, QTableWidgetItem(user.get('name', '-')))

                    # Column 2: Status (with color)
                    status = user.get('status', 'active')
                    status_item = QTableWidgetItem(status.upper())
                    if status == "active":
                        status_item.setForeground(QColor(ProfessionalTheme.SUCCESS))
                    elif status == "pending":
                        status_item.setForeground(QColor(ProfessionalTheme.WARNING))
                    else:
                        status_item.setForeground(QColor(ProfessionalTheme.DANGER))
                    self.customer_table.setItem(row, 2, status_item)

                    # Column 3: Tier (with color)
                    tier = user.get('tier', 'free')
                    tier_item = QTableWidgetItem(tier.upper())
                    if tier == 'admin':
                        tier_item.setForeground(QColor("#9C27B0"))  # Purple for admin
                    elif tier == 'premium':
                        tier_item.setForeground(QColor("#FFD700"))  # Gold for premium
                    elif tier == 'pro':
                        tier_item.setForeground(QColor("#2196F3"))  # Blue for pro
                    self.customer_table.setItem(row, 3, tier_item)

                    # Column 4: Source (android/desktop)
                    source = user.get('source', 'unknown')
                    source_item = QTableWidgetItem(source)
                    if source == 'android':
                        source_item.setForeground(QColor("#4CAF50"))  # Green for Android
                    else:
                        source_item.setForeground(QColor("#2196F3"))  # Blue for Desktop
                    self.customer_table.setItem(row, 4, source_item)

                    # Column 5: Email
                    self.customer_table.setItem(row, 5, QTableWidgetItem(user.get('email', '')))

                logger.info(f"Loaded {len(users)} users from server")
            else:
                logger.warning(f"Failed to fetch users from server: {response.message if hasattr(response, 'message') else 'Unknown error'}")
                # Fallback to local if server unreachable
                self._load_customers_local()

        except Exception as e:
            logger.error(f"Error fetching users from server: {e}")
            # Fallback to local when server is offline
            self._load_customers_local()

    def _load_customers_local(self):
        """Fallback: Load customers from local filesystem when server offline."""
        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return

        for customer_dir in sorted(customers_dir.iterdir()):
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name

            # Load profile
            profile_file = self.config.get_customer_profile(customer_id)
            name = "-"
            status = "active"

            if profile_file.exists():
                try:
                    with open(profile_file, 'r') as f:
                        profile = json.load(f)
                    name = profile.get("name", "-")
                    status = profile.get("status", "active")
                except:
                    pass

            # Add row
            row = self.customer_table.rowCount()
            self.customer_table.insertRow(row)

            self.customer_table.setItem(row, 0, QTableWidgetItem(customer_id))
            self.customer_table.setItem(row, 1, QTableWidgetItem(name))

            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(
                QColor(ProfessionalTheme.SUCCESS) if status == "active"
                else QColor(ProfessionalTheme.DANGER)
            )
            self.customer_table.setItem(row, 2, status_item)

            # Tier - unknown for local
            self.customer_table.setItem(row, 3, QTableWidgetItem("LOCAL"))

            # Source - local
            self.customer_table.setItem(row, 4, QTableWidgetItem("local"))

            # Email - unknown
            self.customer_table.setItem(row, 5, QTableWidgetItem("-"))

    def _filter_customers(self):
        """Filter customers based on search text."""
        search = self.txt_search.text().lower()

        for row in range(self.customer_table.rowCount()):
            show = False
            for col in range(self.customer_table.columnCount()):
                item = self.customer_table.item(row, col)
                if item and search in item.text().lower():
                    show = True
                    break
            self.customer_table.setRowHidden(row, not show)

    def _on_selection_changed(self):
        """Handle customer selection change."""
        selected = self.customer_table.selectedItems()
        if not selected:
            self._selected_customer = None
            self.btn_manage_user.setEnabled(False)
            return

        row = selected[0].row()
        customer_id = self.customer_table.item(row, 0).text()
        self._selected_customer = customer_id
        self.btn_manage_user.setEnabled(True)

        self._load_customer_details(customer_id)

    def _on_customer_double_click(self, index):
        """Handle double-click on customer row - opens User Control dialog."""
        row = index.row()
        customer_id_item = self.customer_table.item(row, 0)
        if customer_id_item:
            customer_id = customer_id_item.text()
            self._open_user_control_for_customer(customer_id)

    def _show_customer_context_menu(self, position):
        """Show context menu for customer row."""
        item = self.customer_table.itemAt(position)
        if not item:
            return

        row = item.row()
        customer_id_item = self.customer_table.item(row, 0)
        if not customer_id_item:
            return

        customer_id = customer_id_item.text()
        name_item = self.customer_table.item(row, 1)
        customer_name = name_item.text() if name_item else customer_id

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.PRIMARY};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {ProfessionalTheme.PRIMARY};
            }}
        """)

        action_user_control = menu.addAction(f"Manage User: {customer_name}")
        action_user_control.triggered.connect(lambda: self._open_user_control_for_customer(customer_id))

        menu.addSeparator()

        action_view_details = menu.addAction("View Details")
        action_view_details.triggered.connect(lambda: self._load_customer_details(customer_id))

        action_copy_id = menu.addAction("Copy Customer ID")
        action_copy_id.triggered.connect(lambda: self._copy_to_clipboard(customer_id))

        menu.exec_(self.customer_table.viewport().mapToGlobal(position))

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _open_user_control_dialog(self):
        """Open User Control dialog for selected customer."""
        if self._selected_customer:
            self._open_user_control_for_customer(self._selected_customer)

    def _open_user_control_for_customer(self, customer_id: str):
        """Open User Control dialog for a specific customer.

        Handles different ID formats:
        - "u123" -> unified_users table (Desktop-created user)
        - "123" -> customers table (Android-registered user)
        - "customer_123" -> legacy format
        """
        try:
            # Determine source table based on ID format
            source = 'customers'  # Default to customers (Android users)

            if customer_id.startswith("u"):
                # Desktop user from unified_users table
                user_id = int(customer_id[1:])
                source = 'unified_users'
            elif customer_id.startswith("customer_"):
                # Legacy format
                user_id = int(customer_id.split("_")[1])
            else:
                # Plain number - Android user from customers table
                user_id = int(customer_id)

            dialog = UserControlDialog(user_id=user_id, source=source, parent=self)
            dialog.user_updated.connect(self._on_user_updated)
            dialog.exec()

        except (ValueError, IndexError) as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open User Control for customer: {customer_id}\n{str(e)}"
            )

    def _on_user_updated(self, user_id: int):
        """Handle user update from UserControlDialog."""
        # Refresh the customer list and details
        self._load_customers()
        if self._selected_customer:
            self._load_customer_details(self._selected_customer)
        self.customer_updated.emit(str(user_id))

    def _load_customer_details(self, customer_id: str):
        """Load details for selected customer."""
        # Load profile
        profile_file = self.config.get_customer_profile(customer_id)
        if profile_file.exists():
            try:
                with open(profile_file, 'r') as f:
                    profile = json.load(f)

                self.lbl_customer_id.setText(customer_id)
                self.txt_name.setText(profile.get("name", ""))
                self.txt_email.setText(profile.get("email", ""))
                self.txt_phone.setText(profile.get("phone", ""))
                self.lbl_created.setText(profile.get("created_at", "-"))
                self.lbl_status.setText(profile.get("status", "active").upper())
            except:
                pass

        # Load vehicles
        self._load_vehicles(customer_id)

        # Load API keys
        self._load_api_keys(customer_id)

        # Load data summary
        self._load_data_summary(customer_id)

    def _load_vehicles(self, customer_id: str):
        """Load vehicles for customer."""
        self.vehicles_table.setRowCount(0)

        vehicles = self.isolator.list_customer_vehicles(customer_id)

        for vehicle in vehicles:
            row = self.vehicles_table.rowCount()
            self.vehicles_table.insertRow(row)

            self.vehicles_table.setItem(row, 0, QTableWidgetItem(vehicle.get("vehicle_id", "")))
            self.vehicles_table.setItem(row, 1, QTableWidgetItem(vehicle.get("vin", "-")))

            make_model = f"{vehicle.get('make', '')} {vehicle.get('model', '')}".strip() or "-"
            self.vehicles_table.setItem(row, 2, QTableWidgetItem(make_model))
            self.vehicles_table.setItem(row, 3, QTableWidgetItem(vehicle.get("created_at", "-")))

    def _load_api_keys(self, customer_id: str):
        """Load API keys for customer."""
        self.api_keys_table.setRowCount(0)

        api_keys_file = self.config.API_KEYS_FILE
        if not api_keys_file.exists():
            return

        try:
            with open(api_keys_file, 'r') as f:
                all_keys = json.load(f)

            for key_id, key_data in all_keys.items():
                key_customer = key_data.get("customer_id")
                if not key_customer and key_data.get("profile_id") is not None:
                    key_customer = f"customer_{key_data['profile_id']}"

                if key_customer == customer_id:
                    row = self.api_keys_table.rowCount()
                    self.api_keys_table.insertRow(row)

                    self.api_keys_table.setItem(row, 0, QTableWidgetItem(key_id))
                    self.api_keys_table.setItem(row, 1, QTableWidgetItem(key_data.get("name", "-")))
                    self.api_keys_table.setItem(row, 2, QTableWidgetItem(key_data.get("created", "-")))

                    status = "REVOKED" if key_data.get("revoked") else "ACTIVE"
                    status_item = QTableWidgetItem(status)
                    status_item.setForeground(
                        QColor(ProfessionalTheme.DANGER) if status == "REVOKED"
                        else QColor(ProfessionalTheme.SUCCESS)
                    )
                    self.api_keys_table.setItem(row, 3, status_item)
        except:
            pass

    def _load_data_summary(self, customer_id: str):
        """Load data summary for customer."""
        customer_dir = self.config.get_customer_dir(customer_id)

        # Calculate total size
        total_size = 0
        if customer_dir.exists():
            for path in customer_dir.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size

        # Format size
        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        else:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"

        self.lbl_data_size.setText(size_str)

        # Vehicle count
        vehicles_dir = self.config.get_customer_vehicles_dir(customer_id)
        vehicle_count = 0
        if vehicles_dir.exists():
            vehicle_count = sum(1 for d in vehicles_dir.iterdir() if d.is_dir())
        self.lbl_vehicle_count.setText(str(vehicle_count))

        # Trip count - query from historical data / OBD sessions
        trip_count = self._count_customer_trips(customer_id)
        self.lbl_trip_count.setText(str(trip_count) if trip_count > 0 else "0")

    # ==================== ACTION HANDLERS ====================

    def _add_customer(self):
        """Add a new customer."""
        customer_id, ok = QInputDialog.getText(
            self, "Add Customer",
            "Enter customer ID (e.g., customer_001):"
        )

        if ok and customer_id:
            customer_id = customer_id.strip().replace(" ", "_")

            # Check if exists
            if self.config.get_customer_dir(customer_id).exists():
                QMessageBox.warning(self, "Error", "Customer ID already exists.")
                return

            # Create customer
            self.dir_manager.create_customer(customer_id)

            log_audit_event(
                AuditEventType.PROFILE_CREATED,
                customer_id=customer_id,
                details={"created_by": "admin"}
            )

            self._load_customers()
            QMessageBox.information(self, "Success", f"Customer {customer_id} created.")

    def _save_profile(self):
        """Save profile changes."""
        if not self._selected_customer:
            return

        profile_file = self.config.get_customer_profile(self._selected_customer)
        if profile_file.exists():
            with open(profile_file, 'r') as f:
                profile = json.load(f)
        else:
            profile = {"customer_id": self._selected_customer}

        profile["name"] = self.txt_name.text()
        profile["email"] = self.txt_email.text()
        profile["phone"] = self.txt_phone.text()
        profile["updated_at"] = datetime.now().isoformat()

        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)

        log_audit_event(
            AuditEventType.PROFILE_UPDATED,
            customer_id=self._selected_customer,
            details={"updated_by": "admin"}
        )

        self._load_customers()
        QMessageBox.information(self, "Success", "Profile saved.")

    def _add_vehicle(self):
        """Add a vehicle to customer."""
        if not self._selected_customer:
            return

        vin, ok = QInputDialog.getText(
            self, "Add Vehicle",
            "Enter VIN (17 characters):"
        )

        if ok and vin:
            vin = vin.strip().upper()

            try:
                success, path, error = self.isolator.get_vehicle_directory(
                    self._selected_customer, vin, create=True
                )

                if success:
                    self._load_vehicles(self._selected_customer)
                    QMessageBox.information(self, "Success", "Vehicle added.")
                else:
                    QMessageBox.warning(self, "Error", error)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _remove_vehicle(self):
        """Remove selected vehicle."""
        selected = self.vehicles_table.selectedItems()
        if not selected or not self._selected_customer:
            return

        vehicle_id = self.vehicles_table.item(selected[0].row(), 0).text()

        reply = QMessageBox.warning(
            self, "Confirm Removal",
            f"Remove vehicle {vehicle_id}?\n\nThis will delete all vehicle data.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            vehicle_dir = self.config.get_vehicle_dir(self._selected_customer, vehicle_id)
            if vehicle_dir.exists():
                import shutil
                shutil.rmtree(vehicle_dir)

            self._load_vehicles(self._selected_customer)
            QMessageBox.information(self, "Success", "Vehicle removed.")

    def _generate_api_key(self):
        """Generate new API key for customer."""
        if not self._selected_customer:
            return

        import secrets
        import hashlib

        # Generate key
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

        # Load existing keys
        api_keys_file = self.config.API_KEYS_FILE
        if api_keys_file.exists():
            with open(api_keys_file, 'r') as f:
                all_keys = json.load(f)
        else:
            all_keys = {}

        # Add new key
        all_keys[key_id] = {
            "key_hash": key_hash,
            "customer_id": self._selected_customer,
            "name": f"Key for {self._selected_customer}",
            "created": datetime.now().isoformat(),
            "permissions": ["vehicle_data", "predict", "diagnostic"]
        }

        with open(api_keys_file, 'w') as f:
            json.dump(all_keys, f, indent=2)

        self._load_api_keys(self._selected_customer)

        QMessageBox.information(
            self, "API Key Generated",
            f"New API Key (save this - it won't be shown again):\n\n{api_key}"
        )

    def _revoke_api_key(self):
        """Revoke selected API key."""
        selected = self.api_keys_table.selectedItems()
        if not selected:
            return

        key_id = self.api_keys_table.item(selected[0].row(), 0).text()

        reply = QMessageBox.question(
            self, "Confirm Revocation",
            f"Revoke API key {key_id}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            api_keys_file = self.config.API_KEYS_FILE
            with open(api_keys_file, 'r') as f:
                all_keys = json.load(f)

            if key_id in all_keys:
                all_keys[key_id]["revoked"] = True
                all_keys[key_id]["revoked_at"] = datetime.now().isoformat()

                with open(api_keys_file, 'w') as f:
                    json.dump(all_keys, f, indent=2)

            self._load_api_keys(self._selected_customer)
            QMessageBox.information(self, "Success", "API key revoked.")

    def _export_customer_data(self):
        """Export all customer data (GDPR compliance)."""
        if not self._selected_customer:
            return

        save_path = QFileDialog.getSaveFileName(
            self, "Export Customer Data",
            f"{self._selected_customer}_data_export.zip",
            "ZIP Files (*.zip)"
        )[0]

        if save_path:
            import zipfile

            customer_dir = self.config.get_customer_dir(self._selected_customer)

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for path in customer_dir.rglob("*"):
                    if path.is_file():
                        arcname = path.relative_to(customer_dir)
                        zipf.write(path, arcname)

            log_audit_event(
                AuditEventType.DATA_EXPORTED,
                customer_id=self._selected_customer,
                details={"export_path": save_path, "exported_by": "admin"}
            )

            QMessageBox.information(self, "Success", f"Data exported to:\n{save_path}")

    def _anonymize_data(self):
        """Anonymize personal data in customer profile."""
        if not self._selected_customer:
            return

        reply = QMessageBox.warning(
            self, "Confirm Anonymization",
            "This will replace personal information with anonymized data.\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            profile_file = self.config.get_customer_profile(self._selected_customer)
            if profile_file.exists():
                with open(profile_file, 'r') as f:
                    profile = json.load(f)

                # Anonymize fields
                profile["name"] = "ANONYMIZED"
                profile["email"] = "anonymized@example.com"
                profile["phone"] = "000-000-0000"
                profile["anonymized_at"] = datetime.now().isoformat()

                with open(profile_file, 'w') as f:
                    json.dump(profile, f, indent=2)

            self._load_customer_details(self._selected_customer)
            QMessageBox.information(self, "Success", "Personal data anonymized.")

    def _soft_delete_customer(self):
        """Soft delete customer (30-day recovery)."""
        if not self._selected_customer:
            return

        reply = QMessageBox.warning(
            self, "Confirm Deletion",
            f"Delete customer {self._selected_customer}?\n\n"
            "Data will be recoverable for 30 days.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, msg = self.isolator.delete_customer_data(
                self._selected_customer,
                soft_delete=True,
                deleted_by="admin"
            )

            if success:
                self._selected_customer = None
                self._load_customers()
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Error", msg)

    def _permanent_delete_customer(self):
        """Permanently delete customer (no recovery)."""
        if not self._selected_customer:
            return

        # Double confirmation
        reply1 = QMessageBox.critical(
            self, "PERMANENT DELETION",
            f"PERMANENTLY delete {self._selected_customer}?\n\n"
            "This CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply1 != QMessageBox.Yes:
            return

        confirm, ok = QInputDialog.getText(
            self, "Confirm",
            f"Type '{self._selected_customer}' to confirm permanent deletion:"
        )

        if ok and confirm == self._selected_customer:
            success, msg = self.isolator.delete_customer_data(
                self._selected_customer,
                soft_delete=False,
                deleted_by="admin"
            )

            if success:
                self._selected_customer = None
                self._load_customers()
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Error", msg)

    # ==================== DATA HELPERS ====================

    def _count_customer_trips(self, customer_id: str) -> int:
        """
        Count total trips/sessions for a customer by scanning their OBD data files.

        A trip is counted as:
        1. Each OBD session file in the vehicle directories
        2. Each entry in the historical data manager (if available)

        Returns:
            Total trip count across all customer vehicles
        """
        trip_count = 0

        try:
            vehicles_dir = self.config.get_customer_vehicles_dir(customer_id)
            if not vehicles_dir.exists():
                return 0

            # Count OBD session files for each vehicle
            for vehicle_dir in vehicles_dir.iterdir():
                if not vehicle_dir.is_dir():
                    continue

                # Check OBD data directory for session files
                obd_dir = vehicle_dir / "obd_data"
                if obd_dir.exists():
                    # Count JSON session files
                    trip_count += sum(1 for f in obd_dir.glob("*.json") if f.is_file())
                    # Count CSV session files
                    trip_count += sum(1 for f in obd_dir.glob("*.csv") if f.is_file())

                # Check trips directory
                trips_dir = vehicle_dir / "trips"
                if trips_dir.exists():
                    trip_count += sum(1 for f in trips_dir.glob("*.json") if f.is_file())

            # Also check historical data in the logs directory
            logs_dir = self.config.LOGS_DIR
            if logs_dir.exists():
                # Count session files that belong to this customer
                for log_file in logs_dir.glob(f"*{customer_id}*.json"):
                    if log_file.is_file():
                        trip_count += 1

        except Exception as e:
            print(f"Error counting trips for {customer_id}: {e}")
            return 0

        return trip_count

    # ==================== STYLE HELPERS ====================

    def _get_button_style(self, color: str) -> str:
        """Get consistent button style based on button type"""
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
        return styles.get(color.lower(), styles['secondary'])

    def _get_table_style(self) -> str:
        return """
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
        """

    def _get_group_style(self) -> str:
        return f"""
            QGroupBox {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-weight: bold;
                border: 1px solid {ProfessionalTheme.CARD_BG};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }}
        """
