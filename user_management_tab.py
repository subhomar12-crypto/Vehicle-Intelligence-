"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: User Management Tab

User Management Tab v2.0 - Refactored with clean card-based layout
Manages user accounts, roles, permissions, and access control
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QMessageBox, QTabWidget,
    QScrollArea, QFrame, QSpinBox, QDateEdit, QHeaderView,
    QDialog, QDialogButtonBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor

import json
import csv
import os
import uuid
import hashlib

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User data structure"""
    id: str
    username: str
    email: str
    role: str
    status: str
    created_at: str
    last_login: str
    permissions: Dict[str, bool] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = {}


class UserDialog(QDialog):
    """Dialog for creating/editing users"""

    def __init__(self, parent=None, user: User = None, title: str = "Add User"):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
            }
            QLabel {
                color: #F0F6FC;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #C40000;
            }
            QCheckBox {
                color: #F0F6FC;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #30363D;
                background-color: #21262D;
            }
            QCheckBox::indicator:checked {
                background-color: #C40000;
                border-color: #C40000;
            }
        """)

        self._setup_ui()

        if user:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("User Details")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("color: #C40000; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Username
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Enter username...")
        form_layout.addRow("Username:", self.username_edit)

        # Email
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Enter email address...")
        form_layout.addRow("Email:", self.email_edit)

        # Password (only for new users or reset)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Enter password..." if not self.user else "Leave blank to keep current")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_edit)

        # Role
        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "manager", "technician", "viewer"])
        self.role_combo.currentTextChanged.connect(self._update_permissions)
        form_layout.addRow("Role:", self.role_combo)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "inactive", "suspended"])
        form_layout.addRow("Status:", self.status_combo)

        layout.addLayout(form_layout)

        # Permissions section
        perm_group = QGroupBox("Permissions")
        perm_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        perm_layout = QVBoxLayout(perm_group)

        self.perm_users = QCheckBox("User Management")
        self.perm_settings = QCheckBox("Settings")
        self.perm_vehicles = QCheckBox("Vehicles")
        self.perm_obd = QCheckBox("OBD Connection")
        self.perm_diagnostics = QCheckBox("Diagnostics")
        self.perm_reports = QCheckBox("Reports")

        perm_layout.addWidget(self.perm_users)
        perm_layout.addWidget(self.perm_settings)
        perm_layout.addWidget(self.perm_vehicles)
        perm_layout.addWidget(self.perm_obd)
        perm_layout.addWidget(self.perm_diagnostics)
        perm_layout.addWidget(self.perm_reports)

        layout.addWidget(perm_group)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #C40000;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #E53935;
            }
            QPushButton[text="Cancel"] {
                background-color: #21262D;
                border: 1px solid #30363D;
            }
            QPushButton[text="Cancel"]:hover {
                background-color: #30363D;
            }
        """)
        layout.addWidget(button_box)

        # Set initial permissions based on default role
        self._update_permissions(self.role_combo.currentText())

    def _populate_fields(self):
        """Populate fields with existing user data"""
        if self.user:
            self.username_edit.setText(self.user.username)
            self.email_edit.setText(self.user.email)

            # Set role
            index = self.role_combo.findText(self.user.role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)

            # Set status
            index = self.status_combo.findText(self.user.status)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)

            # Set permissions
            perms = self.user.permissions or {}
            self.perm_users.setChecked(perms.get('users', False))
            self.perm_settings.setChecked(perms.get('settings', False))
            self.perm_vehicles.setChecked(perms.get('vehicles', False))
            self.perm_obd.setChecked(perms.get('obd', False))
            self.perm_diagnostics.setChecked(perms.get('diagnostics', False))
            self.perm_reports.setChecked(perms.get('reports', False))

    def _update_permissions(self, role: str):
        """Update default permissions based on role"""
        # Default permissions by role
        defaults = {
            'admin': {'users': True, 'settings': True, 'vehicles': True, 'obd': True, 'diagnostics': True, 'reports': True},
            'manager': {'users': False, 'settings': True, 'vehicles': True, 'obd': False, 'diagnostics': False, 'reports': True},
            'technician': {'users': False, 'settings': False, 'vehicles': True, 'obd': True, 'diagnostics': True, 'reports': False},
            'viewer': {'users': False, 'settings': False, 'vehicles': True, 'obd': False, 'diagnostics': True, 'reports': True}
        }

        perms = defaults.get(role, {})

        # Only update if not editing existing user
        if not self.user:
            self.perm_users.setChecked(perms.get('users', False))
            self.perm_settings.setChecked(perms.get('settings', False))
            self.perm_vehicles.setChecked(perms.get('vehicles', False))
            self.perm_obd.setChecked(perms.get('obd', False))
            self.perm_diagnostics.setChecked(perms.get('diagnostics', False))
            self.perm_reports.setChecked(perms.get('reports', False))

    def _validate_and_accept(self):
        """Validate input before accepting"""
        username = self.username_edit.text().strip()
        email = self.email_edit.text().strip()
        password = self.password_edit.text()

        if not username:
            QMessageBox.warning(self, "Validation Error", "Username is required.")
            return

        if not email or '@' not in email:
            QMessageBox.warning(self, "Validation Error", "Valid email is required.")
            return

        if not self.user and not password:
            QMessageBox.warning(self, "Validation Error", "Password is required for new users.")
            return

        if password and len(password) < 6:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters.")
            return

        self.accept()

    def get_user_data(self) -> Dict[str, Any]:
        """Get user data from form"""
        data = {
            'username': self.username_edit.text().strip(),
            'email': self.email_edit.text().strip(),
            'role': self.role_combo.currentText(),
            'status': self.status_combo.currentText(),
            'permissions': {
                'users': self.perm_users.isChecked(),
                'settings': self.perm_settings.isChecked(),
                'vehicles': self.perm_vehicles.isChecked(),
                'obd': self.perm_obd.isChecked(),
                'diagnostics': self.perm_diagnostics.isChecked(),
                'reports': self.perm_reports.isChecked()
            }
        }

        password = self.password_edit.text()
        if password:
            # Hash the password
            data['password_hash'] = hashlib.sha256(password.encode()).hexdigest()

        return data


class UserManagementTab(QWidget):
    """
    User Management Tab - Refactored v2.0
    Admin interface for managing users with clean card-based layout.
    """

    user_created = Signal(dict)
    user_updated = Signal(dict)
    user_deleted = Signal(str)
    permissions_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.users = []
        self._setup_ui()
        self._load_users()

    def _create_card(self, title: str, color: str) -> QGroupBox:
        """Create a styled card container"""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #1E2329;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: #1E2329;
            }}
        """)
        return card

    def _setup_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0D1117; }")

        # Main content
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(15)

        # ========================================
        # HEADER
        # ========================================
        header_layout = QHBoxLayout()
        title = QLabel("User Management")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('info'))
        self.refresh_btn.clicked.connect(self._refresh_users)
        header_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(header_layout)

        # ========================================
        # STATS ROW
        # ========================================
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.total_users_label = self._create_stat_label("Total Users", "0", "#6F42C1")
        self.active_users_label = self._create_stat_label("Active", "0", "#198754")
        self.inactive_users_label = self._create_stat_label("Inactive", "0", "#FFC107")
        self.sessions_label = self._create_stat_label("Active Sessions", "0", "#0D6EFD")

        stats_layout.addWidget(self.total_users_label)
        stats_layout.addWidget(self.active_users_label)
        stats_layout.addWidget(self.inactive_users_label)
        stats_layout.addWidget(self.sessions_label)

        main_layout.addLayout(stats_layout)

        # ========================================
        # USERS TABLE
        # ========================================
        users_card = self._create_card("User Accounts", "#C40000")
        users_layout = QVBoxLayout(users_card)

        # Filter row
        filter_row = QHBoxLayout()

        self.user_search_edit = QLineEdit()
        self.user_search_edit.setPlaceholderText("Search users...")
        self.user_search_edit.textChanged.connect(self._filter_users)
        filter_row.addWidget(QLabel("Search:"))
        filter_row.addWidget(self.user_search_edit)

        self.role_filter_combo = QComboBox()
        self.role_filter_combo.addItems(["All Roles", "Admin", "Manager", "Technician", "Viewer"])
        self.role_filter_combo.currentTextChanged.connect(self._filter_users)
        filter_row.addWidget(QLabel("Role:"))
        filter_row.addWidget(self.role_filter_combo)

        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All Status", "Active", "Inactive", "Suspended"])
        self.status_filter_combo.currentTextChanged.connect(self._filter_users)
        filter_row.addWidget(QLabel("Status:"))
        filter_row.addWidget(self.status_filter_combo)

        filter_row.addStretch()
        users_layout.addLayout(filter_row)

        # Table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels([
            "Username", "Email", "Role", "Status",
            "Created", "Last Login", "Actions"
        ])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.setMinimumHeight(300)
        self._apply_table_styling(self.users_table)
        users_layout.addWidget(self.users_table)

        # Action buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.add_user_btn = QPushButton("Add User")
        self.add_user_btn.setStyleSheet(self._get_button_style('success'))
        self.add_user_btn.clicked.connect(self._add_user)
        button_row.addWidget(self.add_user_btn)

        self.edit_user_btn = QPushButton("Edit User")
        self.edit_user_btn.setStyleSheet(self._get_button_style('primary'))
        self.edit_user_btn.clicked.connect(lambda: self._edit_user(None))
        self.edit_user_btn.setEnabled(False)
        button_row.addWidget(self.edit_user_btn)

        self.delete_user_btn = QPushButton("Delete User")
        self.delete_user_btn.setStyleSheet(self._get_button_style('danger'))
        self.delete_user_btn.clicked.connect(lambda: self._delete_user(None))
        self.delete_user_btn.setEnabled(False)
        button_row.addWidget(self.delete_user_btn)

        users_layout.addLayout(button_row)
        main_layout.addWidget(users_card)

        # ========================================
        # ROLES & PERMISSIONS
        # ========================================
        roles_layout = QHBoxLayout()
        roles_layout.setSpacing(15)

        # Roles card
        roles_card = self._create_card("User Roles", "#FF9800")
        roles_card_layout = QVBoxLayout(roles_card)

        self.roles_table = QTableWidget()
        self.roles_table.setColumnCount(3)
        self.roles_table.setHorizontalHeaderLabels(["Role", "Description", "Users"])
        self.roles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.roles_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.roles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.roles_table.setMaximumHeight(200)
        self._apply_table_styling(self.roles_table)

        # Add role definitions
        roles = [
            ('Admin', 'Full system access', 'users, settings, data'),
            ('Manager', 'Can manage vehicles and reports', 'vehicles, reports'),
            ('Technician', 'OBD connection and diagnostics', 'obd, diagnostics'),
            ('Viewer', 'Read-only access', 'reports, historical')
        ]

        for role, desc, perms in roles:
            row = self.roles_table.rowCount()
            self.roles_table.insertRow(row)
            self.roles_table.setItem(row, 0, QTableWidgetItem(role))
            self.roles_table.setItem(row, 1, QTableWidgetItem(desc))
            self.roles_table.setItem(row, 2, QTableWidgetItem(perms))

        roles_card_layout.addWidget(self.roles_table)
        roles_layout.addWidget(roles_card)

        # Permissions card
        perm_card = self._create_card("Permission Matrix", "#4CAF50")
        perm_layout = QVBoxLayout(perm_card)

        self.permissions_table = QTableWidget()
        self.permissions_table.setColumnCount(5)
        self.permissions_table.setHorizontalHeaderLabels([
            "Permission", "Admin", "Manager", "Tech", "Viewer"
        ])
        self.permissions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.permissions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._apply_table_styling(self.permissions_table)

        permissions = [
            ('User Management', True, False, False, False),
            ('Settings', True, True, False, False),
            ('Vehicles', True, True, True, True),
            ('OBD Connection', False, False, True, False),
            ('Diagnostics', False, False, True, True),
            ('Live Data', False, False, True, True),
            ('Reports', True, True, False, True),
            ('Notifications', True, True, False, False),
        ]

        for perm, *access in permissions:
            row = self.permissions_table.rowCount()
            self.permissions_table.insertRow(row)
            self.permissions_table.setItem(row, 0, QTableWidgetItem(perm))
            for i, has_access in enumerate(access):
                self.permissions_table.setItem(row, i + 1, QTableWidgetItem("✓" if has_access else ""))

        perm_layout.addWidget(self.permissions_table)
        roles_layout.addWidget(perm_card, 1)
        main_layout.addLayout(roles_layout)

        # ========================================
        # ACTIVITY & SESSIONS
        # ========================================
        activity_layout = QHBoxLayout()
        activity_layout.setSpacing(15)

        # Activity log card
        activity_card = self._create_card("Recent Activity", "#2196F3")
        activity_card_layout = QVBoxLayout(activity_card)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels([
            "Timestamp", "User", "Action", "Details"
        ])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_table.setMinimumHeight(200)
        self.activity_table.setMaximumHeight(200)
        self._apply_table_styling(self.activity_table)
        activity_card_layout.addWidget(self.activity_table)

        export_btn = QPushButton("Export Log")
        export_btn.setStyleSheet(self._get_button_style('secondary'))
        export_btn.clicked.connect(self._export_activity)
        activity_card_layout.addWidget(export_btn)

        activity_layout.addWidget(activity_card)

        # Sessions card
        sessions_card = self._create_card("Active Sessions", "#9C27B0")
        sessions_card_layout = QVBoxLayout(sessions_card)

        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(4)
        self.sessions_table.setHorizontalHeaderLabels([
            "User", "Login Time", "IP Address", "Actions"
        ])
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sessions_table.setMinimumHeight(200)
        self.sessions_table.setMaximumHeight(200)
        self._apply_table_styling(self.sessions_table)
        sessions_card_layout.addWidget(self.sessions_table)

        # Session controls
        session_controls = QHBoxLayout()

        self.session_timeout_spin = QSpinBox()
        self.session_timeout_spin.setRange(15, 480)
        self.session_timeout_spin.setValue(60)
        self.session_timeout_spin.setSuffix(" min")

        session_controls.addWidget(QLabel("Timeout:"))
        session_controls.addWidget(self.session_timeout_spin)
        session_controls.addStretch()

        self.logout_all_btn = QPushButton("Logout All")
        self.logout_all_btn.setStyleSheet(self._get_button_style('danger'))
        self.logout_all_btn.clicked.connect(self._logout_all_users)
        session_controls.addWidget(self.logout_all_btn)

        sessions_card_layout.addLayout(session_controls)
        activity_layout.addWidget(sessions_card, 1)

        main_layout.addLayout(activity_layout)
        main_layout.addStretch()

        scroll.setWidget(content)

        # Container layout
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.addWidget(scroll)

        # Connect selection
        self.users_table.itemSelectionChanged.connect(self._on_selection_changed)

    def _create_stat_label(self, title: str, value: str, color: str) -> QFrame:
        """Create a statistic label widget."""
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2329;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #8B949E; font-size: 11px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        value_lbl = QLabel(value)
        value_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        value_lbl.setStyleSheet(f"color: {color};")
        value_lbl.setAlignment(Qt.AlignCenter)
        value_lbl.setObjectName(f"stat_{title.lower().replace(' ', '_')}")
        layout.addWidget(value_lbl)

        return widget

    def _load_users(self):
        """Load users (mock data for now)"""
        self._load_mock_users()
        self._update_users_table()
        self._update_statistics()
        self._load_mock_sessions()
        self._load_mock_activity()

    def _load_mock_users(self):
        """Load mock user data"""
        now = datetime.now()

        self.users = [
            User(
                id="user-001",
                username="admin",
                email="admin@predictobd.com",
                role="admin",
                status="active",
                created_at=(now - timedelta(days=365)).isoformat(),
                last_login=now.isoformat(),
                permissions={'users': True, 'settings': True, 'data': True}
            ),
            User(
                id="user-002",
                username="manager1",
                email="manager1@company.com",
                role="manager",
                status="active",
                created_at=(now - timedelta(days=180)).isoformat(),
                last_login=(now - timedelta(hours=2)).isoformat(),
                permissions={'vehicles': True, 'reports': True}
            ),
            User(
                id="user-003",
                username="tech1",
                email="tech1@company.com",
                role="technician",
                status="active",
                created_at=(now - timedelta(days=90)).isoformat(),
                last_login=(now - timedelta(days=1)).isoformat(),
                permissions={'obd': True, 'diagnostics': True}
            ),
            User(
                id="user-004",
                username="viewer1",
                email="viewer1@company.com",
                role="viewer",
                status="inactive",
                created_at=(now - timedelta(days=60)).isoformat(),
                last_login=(now - timedelta(days=7)).isoformat(),
                permissions={'reports': True}
            ),
        ]

    def _update_users_table(self):
        """Update users table"""
        self.users_table.setRowCount(0)

        for user in self.users:
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)

            self.users_table.setItem(row, 0, QTableWidgetItem(user.username))
            self.users_table.setItem(row, 1, QTableWidgetItem(user.email))

            role_item = QTableWidgetItem(user.role.upper())
            role_color = {
                "admin": "#F44336",
                "manager": "#FF9800",
                "technician": "#4CAF50",
                "viewer": "#8B949E"
            }.get(user.role, "#8B949E")
            role_item.setForeground(QColor(role_color))
            self.users_table.setItem(row, 2, role_item)

            status_item = QTableWidgetItem(user.status.upper())
            status_color = {
                "active": "#198754",
                "inactive": "#FFC107",
                "suspended": "#DC3545"
            }.get(user.status, "#8B949E")
            status_item.setForeground(QColor(status_color))
            self.users_table.setItem(row, 3, status_item)

            try:
                created_dt = datetime.fromisoformat(user.created_at)
                created_text = created_dt.strftime("%Y-%m-%d")
            except:
                created_text = user.created_at
            self.users_table.setItem(row, 4, QTableWidgetItem(created_text))

            try:
                login_dt = datetime.fromisoformat(user.last_login)
                login_text = login_dt.strftime("%Y-%m-%d %H:%M")
            except:
                login_text = user.last_login
            self.users_table.setItem(row, 5, QTableWidgetItem(login_text))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(self._get_button_style('secondary'))
            edit_btn.clicked.connect(lambda checked, u=user: self._edit_user(u))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet(self._get_button_style('danger'))
            delete_btn.clicked.connect(lambda checked, u=user: self._delete_user(u))
            actions_layout.addWidget(delete_btn)

            self.users_table.setCellWidget(row, 6, actions_widget)

    def _update_statistics(self):
        """Update statistics"""
        total = len(self.users)
        active = sum(1 for u in self.users if u.status == "active")
        inactive = total - active

        for widget in [self.total_users_label, self.active_users_label, self.inactive_users_label, self.sessions_label]:
            # Find child QLabel with objectName starting with "stat_"
            for child in widget.findChildren(QLabel):
                if child.objectName() and child.objectName().startswith("stat_"):
                    obj_name = child.objectName()
                    if "total" in obj_name:
                        child.setText(str(total))
                    elif "active" in obj_name:
                        child.setText(str(active))
                    elif "inactive" in obj_name:
                        child.setText(str(inactive))
                    elif "sessions" in obj_name:
                        child.setText(str(active))

    def _filter_users(self):
        """Filter users"""
        self._update_users_table()

    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.users_table.selectedItems()
        has_selection = len(selected) > 0
        self.edit_user_btn.setEnabled(has_selection)
        self.delete_user_btn.setEnabled(has_selection)

    def _add_user(self):
        """Add new user"""
        dialog = UserDialog(self, title="Add New User")

        if dialog.exec() == QDialog.Accepted:
            user_data = dialog.get_user_data()

            # Check for duplicate username
            if any(u.username == user_data['username'] for u in self.users):
                QMessageBox.warning(self, "Duplicate User", f"Username '{user_data['username']}' already exists.")
                return

            # Check for duplicate email
            if any(u.email == user_data['email'] for u in self.users):
                QMessageBox.warning(self, "Duplicate Email", f"Email '{user_data['email']}' is already in use.")
                return

            # Create new user
            now = datetime.now()
            new_user = User(
                id=f"user-{uuid.uuid4().hex[:8]}",
                username=user_data['username'],
                email=user_data['email'],
                role=user_data['role'],
                status=user_data['status'],
                created_at=now.isoformat(),
                last_login="Never",
                permissions=user_data['permissions']
            )

            self.users.append(new_user)
            self._update_users_table()
            self._update_statistics()
            self._add_activity_log("User Created", f"New user: {new_user.username}", new_user.username)

            # Emit signal
            self.user_created.emit({
                'id': new_user.id,
                'username': new_user.username,
                'email': new_user.email,
                'role': new_user.role
            })

            QMessageBox.information(self, "User Created", f"User '{new_user.username}' created successfully.")
            logger.info(f"New user created: {new_user.username}")

    def _edit_user(self, user: User):
        """Edit user"""
        # Get user from selection if not provided
        if not user:
            selected = self.users_table.selectedItems()
            if selected:
                row = selected[0].row()
                username = self.users_table.item(row, 0).text()
                user = next((u for u in self.users if u.username == username), None)

        if not user:
            QMessageBox.warning(self, "No Selection", "Please select a user to edit.")
            return

        dialog = UserDialog(self, user=user, title=f"Edit User: {user.username}")

        if dialog.exec() == QDialog.Accepted:
            user_data = dialog.get_user_data()

            # Check for duplicate username (excluding current user)
            if any(u.username == user_data['username'] and u.id != user.id for u in self.users):
                QMessageBox.warning(self, "Duplicate User", f"Username '{user_data['username']}' already exists.")
                return

            # Check for duplicate email (excluding current user)
            if any(u.email == user_data['email'] and u.id != user.id for u in self.users):
                QMessageBox.warning(self, "Duplicate Email", f"Email '{user_data['email']}' is already in use.")
                return

            # Update user
            old_username = user.username
            user.username = user_data['username']
            user.email = user_data['email']
            user.role = user_data['role']
            user.status = user_data['status']
            user.permissions = user_data['permissions']

            self._update_users_table()
            self._update_statistics()
            self._add_activity_log("User Updated", f"Updated user: {user.username}", "admin")

            # Emit signal
            self.user_updated.emit({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            })

            QMessageBox.information(self, "User Updated", f"User '{user.username}' updated successfully.")
            logger.info(f"User updated: {old_username} -> {user.username}")

    def _delete_user(self, user: User):
        """Delete user"""
        if not user:
            selected = self.users_table.selectedItems()
            if selected:
                row = selected[0].row()
                username = self.users_table.item(row, 0).text()
                user = next((u for u in self.users if u.username == username), None)

        if not user:
            return

        reply = QMessageBox.question(
            self, "Delete User",
            f"Delete user: {user.username}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.users = [u for u in self.users if u.id != user.id]
            self._update_users_table()
            self._update_statistics()
            self.user_deleted.emit(user.id)
            logger.info(f"User deleted: {user.username}")

    def _refresh_users(self):
        """Refresh users"""
        self._load_users()
        logger.info("Users refreshed")

    def _export_activity(self):
        """Export activity log to file"""
        # Get export file path
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Activity Log",
            f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "CSV Files (*.csv);;JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Gather activity data from table
            activity_data = []
            for row in range(self.activity_table.rowCount()):
                row_data = {
                    'timestamp': self.activity_table.item(row, 0).text() if self.activity_table.item(row, 0) else '',
                    'user': self.activity_table.item(row, 1).text() if self.activity_table.item(row, 1) else '',
                    'action': self.activity_table.item(row, 2).text() if self.activity_table.item(row, 2) else '',
                    'details': self.activity_table.item(row, 3).text() if self.activity_table.item(row, 3) else ''
                }
                activity_data.append(row_data)

            # Export based on file extension
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'export_date': datetime.now().isoformat(),
                        'total_entries': len(activity_data),
                        'activity_log': activity_data
                    }, f, indent=2)
            else:
                # Default to CSV
                if not file_path.endswith('.csv'):
                    file_path += '.csv'

                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['timestamp', 'user', 'action', 'details'])
                    writer.writeheader()
                    writer.writerows(activity_data)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Activity log exported successfully!\n\nFile: {file_path}\nEntries: {len(activity_data)}"
            )
            logger.info(f"Activity log exported: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export activity log:\n{e}")
            logger.error(f"Activity export error: {e}")

    def _logout_all_users(self):
        """Logout all users"""
        # Count active sessions
        active_sessions = self.sessions_table.rowCount()

        if active_sessions == 0:
            QMessageBox.information(self, "No Sessions", "There are no active sessions to logout.")
            return

        reply = QMessageBox.question(
            self, "Logout All Users",
            f"Are you sure you want to logout ALL {active_sessions} active session(s)?\n\n"
            "This will force all users to re-authenticate.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Clear sessions table
            self.sessions_table.setRowCount(0)

            # Update users' last_login (simulating logout)
            for user in self.users:
                if user.status == "active":
                    user.last_login = datetime.now().isoformat()

            # Log the action
            self._add_activity_log("Mass Logout", f"All {active_sessions} sessions terminated", "admin")

            # Update statistics
            self._update_statistics()

            QMessageBox.information(
                self,
                "Logout Complete",
                f"Successfully logged out {active_sessions} session(s).\n\n"
                "All users will need to re-authenticate."
            )
            logger.info(f"Mass logout: {active_sessions} sessions terminated")

    def _add_activity_log(self, action: str, details: str, user: str = "System"):
        """Add entry to activity log"""
        row = self.activity_table.rowCount()
        self.activity_table.insertRow(0)  # Insert at top

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.activity_table.setItem(0, 0, QTableWidgetItem(timestamp))
        self.activity_table.setItem(0, 1, QTableWidgetItem(user))
        self.activity_table.setItem(0, 2, QTableWidgetItem(action))
        self.activity_table.setItem(0, 3, QTableWidgetItem(details))

        # Keep only last 100 entries
        while self.activity_table.rowCount() > 100:
            self.activity_table.removeRow(self.activity_table.rowCount() - 1)

    def _load_mock_sessions(self):
        """Load mock session data"""
        self.sessions_table.setRowCount(0)

        # Add some mock sessions
        sessions = [
            ("admin", datetime.now() - timedelta(hours=2), "192.168.1.100"),
            ("manager1", datetime.now() - timedelta(minutes=30), "192.168.1.105"),
            ("tech1", datetime.now() - timedelta(minutes=10), "192.168.1.110"),
        ]

        for username, login_time, ip in sessions:
            row = self.sessions_table.rowCount()
            self.sessions_table.insertRow(row)

            self.sessions_table.setItem(row, 0, QTableWidgetItem(username))
            self.sessions_table.setItem(row, 1, QTableWidgetItem(login_time.strftime("%Y-%m-%d %H:%M")))
            self.sessions_table.setItem(row, 2, QTableWidgetItem(ip))

            # Action button
            logout_btn = QPushButton("Logout")
            logout_btn.setStyleSheet(self._get_button_style('danger'))
            logout_btn.clicked.connect(lambda checked, u=username: self._logout_user(u))
            self.sessions_table.setCellWidget(row, 3, logout_btn)

    def _logout_user(self, username: str):
        """Logout a specific user"""
        reply = QMessageBox.question(
            self, "Logout User",
            f"Logout user '{username}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Find and remove the session row
            for row in range(self.sessions_table.rowCount()):
                item = self.sessions_table.item(row, 0)
                if item and item.text() == username:
                    self.sessions_table.removeRow(row)
                    break

            self._add_activity_log("User Logout", f"Session terminated for: {username}", "admin")
            self._update_statistics()
            logger.info(f"User logged out: {username}")

    def _load_mock_activity(self):
        """Load mock activity data"""
        self.activity_table.setRowCount(0)

        # Add some mock activity
        activities = [
            (datetime.now() - timedelta(minutes=5), "admin", "Login", "Successful login from 192.168.1.100"),
            (datetime.now() - timedelta(minutes=15), "tech1", "OBD Connection", "Connected to vehicle VIN: ABC123"),
            (datetime.now() - timedelta(minutes=30), "manager1", "Report Export", "Exported monthly maintenance report"),
            (datetime.now() - timedelta(hours=1), "admin", "User Created", "Created user: viewer1"),
            (datetime.now() - timedelta(hours=2), "system", "Backup", "Automatic daily backup completed"),
        ]

        for timestamp, user, action, details in activities:
            row = self.activity_table.rowCount()
            self.activity_table.insertRow(row)

            self.activity_table.setItem(row, 0, QTableWidgetItem(timestamp.strftime("%Y-%m-%d %H:%M:%S")))
            self.activity_table.setItem(row, 1, QTableWidgetItem(user))
            self.activity_table.setItem(row, 2, QTableWidgetItem(action))
            self.activity_table.setItem(row, 3, QTableWidgetItem(details))

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #2C3E50;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #34495E; }
                QPushButton:disabled { background-color: #1A252F; color: #6E7681; }
            """,
            'danger': """
                QPushButton {
                    background-color: #DC3545;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'success': """
                QPushButton {
                    background-color: #198754;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #20C997; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'info': """
                QPushButton {
                    background-color: #0D6EFD;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #1976D2; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _apply_table_styling(self, table_widget):
        """Apply table styling"""
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #1E2329;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #30363D;
            }
            QTableWidget::item:selected {
                background-color: #C40000;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #2C3E50;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #F0F6FC;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
                font-weight: 600;
                font-size: 11px;
            }
        """)
