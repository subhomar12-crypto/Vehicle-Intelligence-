"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Server Tab V2
"""

"""
Server Tab v2.0 - Organized Server Management

Features:
- Sub-tabs for organized access to all server features
- Tier-based API key system (F_/P_/A_ prefixes)
- Encrypted API key storage with reveal functionality
- Admin password protection for generating admin keys
- Auto-integration with subscription system

Sub-tabs:
1. Server Control - Start/Stop server, status monitoring
2. API Keys - Generate, view, manage API keys with tier system
3. Database - Stats, query, export, backup
4. Network - IP addresses and connection info
5. PDF Server - PDF generation server status
6. Cloudflare Tunnel - Remote access management
"""

import os
import json
import secrets
import hashlib
import base64
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog, QHeaderView, QComboBox, QFileDialog,
    QTextEdit, QScrollArea, QFrame, QApplication, QDialog,
    QTabWidget, QSpinBox, QCheckBox, QGridLayout, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QFont, QColor
from ui_common import show_error, show_info, show_warning
from cloudflare_tunnel import CloudflareTunnel


# =============================================================================
# ENCRYPTION UTILITIES
# =============================================================================

class SimpleEncryption:
    """Simple XOR-based encryption for API keys (not military-grade, but better than plaintext)"""

    @staticmethod
    def encrypt(text: str, password: str) -> str:
        """Encrypt text using XOR with password"""
        # Use SHA256 of password as key
        key = hashlib.sha256(password.encode()).digest()
        encrypted = []
        for i, char in enumerate(text):
            key_byte = key[i % len(key)]
            encrypted.append(chr(ord(char) ^ key_byte))
        encrypted_text = ''.join(encrypted)
        # Return as base64 for safe storage
        return base64.b64encode(encrypted_text.encode()).decode()

    @staticmethod
    def decrypt(encrypted_text: str, password: str) -> str:
        """Decrypt text using XOR with password"""
        try:
            key = hashlib.sha256(password.encode()).digest()
            encrypted = base64.b64decode(encrypted_text.encode()).decode()
            decrypted = []
            for i, char in enumerate(encrypted):
                key_byte = key[i % len(key)]
                decrypted.append(chr(ord(char) ^ key_byte))
            return ''.join(decrypted)
        except Exception:
            return ""  # Wrong password or corrupted data


# =============================================================================
# THEME COLORS
# =============================================================================

class ServerTheme:
    PRIMARY = "#C40000"
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"
    DANGER = "#F44336"
    INFO = "#0DCAF0"

    BACKGROUND = "#0D1117"
    CARD_BG = "#21262D"
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"
    BORDER = "#30363D"

    # Tier colors
    FREE_TIER = "#6E7681"      # Gray
    PREMIUM_TIER = "#FFD700"    # Gold
    ADMIN_TIER = "#DC3545"      # Red


# =============================================================================
# STATS UPDATE WORKER
# =============================================================================

class StatsUpdateWorker(QThread):
    """Background worker for updating stats without blocking UI"""
    stats_ready = Signal(dict)
    network_ready = Signal(dict)
    sessions_ready = Signal(list)

    def __init__(self, server):
        super().__init__()
        self.server = server

    def run(self):
        try:
            if hasattr(self.server, 'get_database_stats'):
                stats = self.server.get_database_stats()
                self.stats_ready.emit(stats)

            if hasattr(self.server, 'get_server_info'):
                info = self.server.get_server_info()
                if 'network_info' in info:
                    self.network_ready.emit(info)

            if hasattr(self.server, 'get_active_sessions'):
                sessions = self.server.get_active_sessions()
                self.sessions_ready.emit(sessions)
        except Exception:
            pass


# =============================================================================
# API KEY TIER SYSTEM
# =============================================================================

class ApiKeyTier:
    """API Key Tier Configuration"""

    TIERS = {
        "free": {
            "prefix": "F_",
            "name": "Free",
            "color": ServerTheme.FREE_TIER,
            "permissions": ["vehicle_data"],
            "key_length": 28,  # F_ + 26 chars = 28 total
            "description": "Basic vehicle data access only"
        },
        "premium": {
            "prefix": "P_",
            "name": "Premium",
            "color": ServerTheme.PREMIUM_TIER,
            "permissions": ["vehicle_data", "predict", "diagnostic", "llm_chat"],
            "key_length": 28,  # P_ + 26 chars = 28 total
            "description": "Full access including predictions and AI chat"
        },
        "admin": {
            "prefix": "A_",
            "name": "Admin",
            "color": ServerTheme.ADMIN_TIER,
            "permissions": ["vehicle_data", "predict", "diagnostic", "llm_chat", "admin"],
            "key_length": 30,  # A_ + 28 chars = 30 total (longer for admin)
            "description": "Unlimited access with admin privileges"
        }
    }

    @classmethod
    def get_tier_info(cls, tier: str) -> Dict[str, Any]:
        """Get tier configuration"""
        return cls.TIERS.get(tier, cls.TIERS["free"])

    @classmethod
    def generate_key(cls, tier: str) -> str:
        """Generate API key with tier prefix"""
        tier_info = cls.get_tier_info(tier)
        prefix = tier_info["prefix"]
        key_length = tier_info["key_length"] - len(prefix)

        # Generate random alphanumeric string
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        random_part = ''.join(secrets.choice(chars) for _ in range(key_length))

        return f"{prefix}{random_part}"

    @classmethod
    def validate_tier_from_key(cls, api_key: str) -> str:
        """Determine tier from API key prefix"""
        if api_key.startswith("A_"):
            return "admin"
        elif api_key.startswith("P_"):
            return "premium"
        elif api_key.startswith("F_"):
            return "free"
        return "unknown"


# =============================================================================
# MAIN SERVER TAB
# =============================================================================

class ServerTab(QWidget):
    """
    Server Management Tab v2.0 with organized sub-tabs
    """

    def __init__(self, mobile_wrapper=None, parent=None):
        super().__init__(parent)
        self.mobile_wrapper = mobile_wrapper

        # API keys file path
        if CONFIG:
            self.api_keys_file = str(CONFIG.API_KEYS_FILE)
            self.database_path = str(CONFIG.SERVER_DB_PATH)
        else:
            self.api_keys_file = "config/api_keys.json"
            self.database_path = "data/obd_data.db"

        # Admin password for generating admin keys
        self.admin_password = "YOUR_ADMIN_PASSWORD"  # Admin password

        # Update timer for stats
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)

        # Background worker for stats updates
        self._stats_worker = None

        # Cloudflare tunnel manager
        self.tunnel = CloudflareTunnel(self)
        self.tunnel.status_changed.connect(self._on_tunnel_status_changed)

        self._build_ui()
        self._load_api_keys_from_server()  # Load from server instead of local file
        self._update_stats()

        # Connect table item changed signal for inline editing
        # Only if api_table exists (API Keys tab is enabled)
        if hasattr(self, 'api_table'):
            self.api_table.itemChanged.connect(self._on_table_item_changed)

        # Update stats every 5 seconds
        self.stats_timer.start(5000)

    def _build_ui(self):
        """Build the server tab UI with sub-tabs"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ServerTheme.BACKGROUND};
                color: {ServerTheme.TEXT_PRIMARY};
            }}
            QTabWidget::pane {{
                border: 1px solid {ServerTheme.BORDER};
                background-color: {ServerTheme.BACKGROUND};
            }}
            QTabBar::tab {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_SECONDARY};
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {ServerTheme.PRIMARY};
                color: #FFFFFF;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {ServerTheme.BORDER};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(0)

        # Header
        header = self._build_header()
        main_layout.addLayout(header)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget {
                background-color: transparent;
            }
        """)

        # Add sub-tabs
        self.tab_widget.addTab(self._build_server_control_tab(), "📱 Server")
        # API Keys tab removed - now managed via Profile Tab's Customer Management
        # self.tab_widget.addTab(self._build_api_keys_tab(), "🔑 API Keys")
        self.tab_widget.addTab(self._build_database_tab(), "💾 Database")
        self.tab_widget.addTab(self._build_network_tab(), "🌐 Network")
        self.tab_widget.addTab(self._build_pdf_server_tab(), "📄 PDF Server")
        self.tab_widget.addTab(self._build_cloudflare_tab(), "🌐 Cloudflare")

        main_layout.addWidget(self.tab_widget)

    def _build_header(self) -> QHBoxLayout:
        """Build header with title"""
        header = QHBoxLayout()

        title = QLabel("🖥️ Server Management Center")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY};")
        header.addWidget(title)

        header.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh All")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(refresh_btn)

        return header

    # =============================================================================
    # SERVER CONTROL TAB
    # =============================================================================

    def _build_server_control_tab(self) -> QWidget:
        """Build server control tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Status card
        status_group = self._create_card("📱 Mobile Server Status", ServerTheme.PRIMARY)
        status_layout = QVBoxLayout(status_group)

        # Status row
        status_row = QHBoxLayout()
        self.server_status_label = QLabel("Server: Stopped")
        self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 16px;")
        status_row.addWidget(self.server_status_label)

        status_row.addStretch()

        port_label = QLabel("Port: 8000")
        port_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        status_row.addWidget(port_label)

        status_layout.addLayout(status_row)

        # Stats row
        stats_row = QHBoxLayout()
        self.connection_label = QLabel("Connections: 0")
        self.connection_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_row.addWidget(self.connection_label)

        self.data_count_label = QLabel("Data Points: 0")
        self.data_count_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_row.addWidget(self.data_count_label)

        stats_row.addStretch()

        status_layout.addLayout(stats_row)

        # Control buttons
        btn_row = QHBoxLayout()
        self.server_btn = QPushButton("▶️ Start Server")
        self.server_btn.setStyleSheet(self._get_button_style('success'))
        self.server_btn.clicked.connect(self._toggle_server)
        btn_row.addWidget(self.server_btn)

        btn_row.addStretch()

        status_layout.addLayout(btn_row)
        layout.addWidget(status_group)

        # Quick stats
        quick_stats_group = self._create_card("📊 Quick Statistics", ServerTheme.INFO)
        quick_layout = QGridLayout(quick_stats_group)

        self.stat_records = self._create_stat_box("Total Records", "0")
        quick_layout.addWidget(self.stat_records, 0, 0)

        self.stat_vehicles = self._create_stat_box("Vehicles", "0")
        quick_layout.addWidget(self.stat_vehicles, 0, 1)

        self.stat_uptime = self._create_stat_box("Uptime", "0m")
        quick_layout.addWidget(self.stat_uptime, 1, 0)

        self.stat_requests = self._create_stat_box("Requests", "0")
        quick_layout.addWidget(self.stat_requests, 1, 1)

        layout.addWidget(quick_stats_group)

        layout.addStretch()

        # Server info
        info_group = self._create_card("ℹ️ Server Information", ServerTheme.TEXT_SECONDARY)
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        info_text.setPlainText(
            "Mobile Server (Port 8000)\n"
            "- Receives OBD data from Android app\n"
            "- Validates API keys\n"
            "- Stores vehicle data in database\n\n"
            "PDF Server (Port 8001)\n"
            "- Generates PDF reports\n"
            "- Standalone operation"
        )
        info_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ServerTheme.CARD_BG};
                border: 1px solid {ServerTheme.BORDER};
                color: {ServerTheme.TEXT_PRIMARY};
                padding: 10px;
            }}
        """)
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        return widget

    def _create_stat_box(self, label: str, value: str) -> QFrame:
        """Create a statistic box"""
        box = QFrame()
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {ServerTheme.CARD_BG};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 8px;
                padding: 15px;
            }}
        """)

        layout = QVBoxLayout(box)
        layout.setSpacing(5)

        lbl_value = QLabel(value)
        lbl_value.setFont(QFont("Segoe UI", 24, QFont.Bold))
        lbl_value.setStyleSheet(f"color: {ServerTheme.PRIMARY};")
        lbl_value.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_value)

        lbl_label = QLabel(label)
        lbl_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
        lbl_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_label)

        return box

    # =============================================================================
    # API KEYS TAB
    # =============================================================================

    def _build_api_keys_tab(self) -> QWidget:
        """Build API keys management tab"""
        # Create a scroll area for the entire tab content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {ServerTheme.BACKGROUND};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {ServerTheme.CARD_BG};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ServerTheme.BORDER};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
            QScrollBar:horizontal {{
                background-color: {ServerTheme.CARD_BG};
                height: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {ServerTheme.BORDER};
                border-radius: 5px;
                min-width: 20px;
            }}
        """)

        # Content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Info banner - smaller
        info_banner = QFrame()
        info_banner.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(13, 202, 240, 0.1);
                border: 1px solid {ServerTheme.INFO};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        info_layout = QHBoxLayout(info_banner)

        info_text = QLabel(
            "🔑 API Keys are automatically generated when subscriptions are created. "
            "Admin keys require password protection."
        )
        info_text.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY}; font-size: 11px;")
        info_layout.addWidget(info_text)

        layout.addWidget(info_banner)

        # Search and filter bar - NEW
        search_filter_layout = QHBoxLayout()
        search_filter_layout.setSpacing(10)

        # Search box
        search_label = QLabel("🔍 Search:")
        search_label.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY}; font-size: 12px; font-weight: bold;")
        search_filter_layout.addWidget(search_label)

        self.api_search_box = QLineEdit()
        self.api_search_box.setPlaceholderText("Search by name, email, phone...")
        self.api_search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
        """)
        self.api_search_box.textChanged.connect(self._filter_api_keys)
        search_filter_layout.addWidget(self.api_search_box, 3)

        # Tier filter
        tier_filter_label = QLabel("Tier:")
        tier_filter_label.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY}; font-size: 12px;")
        search_filter_layout.addWidget(tier_filter_label)

        self.tier_filter_combo = QComboBox()
        self.tier_filter_combo.addItems(["All", "Admin", "Premium", "Free"])
        self.tier_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 100px;
            }}
            QComboBox:hover {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                background-color: {ServerTheme.PRIMARY};
                border-radius: 3px;
                width: 20px;
            }}
        """)
        self.tier_filter_combo.currentTextChanged.connect(self._filter_api_keys)
        search_filter_layout.addWidget(self.tier_filter_combo)

        # Status filter
        status_filter_label = QLabel("Status:")
        status_filter_label.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY}; font-size: 12px;")
        search_filter_layout.addWidget(status_filter_label)

        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All", "Active", "Suspended", "Revoked"])
        self.status_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 100px;
            }}
            QComboBox:hover {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                background-color: {ServerTheme.PRIMARY};
                border-radius: 3px;
                width: 20px;
            }}
        """)
        self.status_filter_combo.currentTextChanged.connect(self._filter_api_keys)
        search_filter_layout.addWidget(self.status_filter_combo)

        # Refresh button
        self.btn_refresh_keys = QPushButton("🔄 Refresh")
        self.btn_refresh_keys.setStyleSheet(self._get_button_style('info'))
        self.btn_refresh_keys.clicked.connect(self._load_api_keys_from_server)
        search_filter_layout.addWidget(self.btn_refresh_keys)

        layout.addLayout(search_filter_layout)

        # Tier stats - smaller
        tier_stats_layout = QHBoxLayout()
        tier_stats_layout.setSpacing(8)

        self.tier_free_count = self._create_tier_badge("Free", "0", ServerTheme.FREE_TIER)
        tier_stats_layout.addWidget(self.tier_free_count)

        self.tier_premium_count = self._create_tier_badge("Premium", "0", ServerTheme.PREMIUM_TIER)
        tier_stats_layout.addWidget(self.tier_premium_count)

        self.tier_admin_count = self._create_tier_badge("Admin", "0", ServerTheme.ADMIN_TIER)
        tier_stats_layout.addWidget(self.tier_admin_count)

        tier_stats_layout.addStretch()
        layout.addLayout(tier_stats_layout)

        # Action buttons - smaller
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_generate_customer_key = QPushButton("➕ Generate Customer Key")
        self.btn_generate_customer_key.setStyleSheet(self._get_button_style('success'))
        self.btn_generate_customer_key.clicked.connect(self._generate_customer_api_key)
        action_layout.addWidget(self.btn_generate_customer_key)

        self.btn_generate_admin_key = QPushButton("🔐 Generate Admin Key")
        self.btn_generate_admin_key.setStyleSheet(self._get_button_style('danger'))
        self.btn_generate_admin_key.clicked.connect(self._generate_admin_api_key)
        action_layout.addWidget(self.btn_generate_admin_key)

        self.btn_export_keys = QPushButton("📤 Export Keys")
        self.btn_export_keys.setStyleSheet(self._get_button_style('secondary'))
        self.btn_export_keys.clicked.connect(self._export_keys)
        action_layout.addWidget(self.btn_export_keys)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # API Keys table - compact size
        table_group = self._create_card("🔑 API Keys", ServerTheme.PRIMARY)
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setSpacing(5)

        self.api_table = QTableWidget()
        self.api_table.setColumnCount(12)
        self.api_table.setHorizontalHeaderLabels([
            "☑", "Name", "Email", "Phone", "Tier", "Role", "Vehicle", "Apps", "Status", "Source", "Created", "Actions"
        ])
        self.api_table.horizontalHeader().setStretchLastSection(True)
        self.api_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Set column widths - optimized for new layout
        self.api_table.setColumnWidth(0, 30)    # Checkbox
        self.api_table.setColumnWidth(1, 120)   # Name
        self.api_table.setColumnWidth(2, 160)   # Email
        self.api_table.setColumnWidth(3, 110)   # Phone
        self.api_table.setColumnWidth(4, 80)    # Tier
        self.api_table.setColumnWidth(5, 70)    # Role
        self.api_table.setColumnWidth(6, 140)   # Vehicle
        self.api_table.setColumnWidth(7, 90)    # Apps
        self.api_table.setColumnWidth(8, 70)    # Status
        self.api_table.setColumnWidth(9, 70)    # Source
        self.api_table.setColumnWidth(10, 95)   # Created
        self.api_table.setColumnWidth(11, 100)  # Actions

        # Store original key data for each row (for filtering and sync)
        self.api_table_data = []

        # COMPACT: Smaller row height (35px instead of 52px)
        self.api_table.verticalHeader().setDefaultSectionSize(35)
        self.api_table.verticalHeader().setMinimumSectionSize(32)

        # Set table size to allow scrolling within table
        self.api_table.setMinimumHeight(500)
        self.api_table.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # Enable proper scrolling
        self.api_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.api_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.api_table.setAutoScroll(False)
        self.api_table.setWordWrap(False)
        self.api_table.setSelectionBehavior(QTableWidget.SelectRows)

        self._apply_compact_table_styling(self.api_table)
        table_layout.addWidget(self.api_table)

        layout.addWidget(table_group)

        # Set the scroll area content
        scroll_area.setWidget(content_widget)

        # Return a wrapper widget
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll_area)

        return wrapper

    def _create_tier_badge(self, label: str, count: str, color: str) -> QFrame:
        """Create a tier badge"""
        badge = QFrame()
        badge.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 20px;
                padding: 8px 16px;
            }}
        """)

        layout = QHBoxLayout(badge)
        layout.setSpacing(8)

        lbl_label = QLabel(f"{label}:")
        lbl_label.setStyleSheet("color: rgba(0,0,0,0.7); font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_label)

        lbl_count = QLabel(count)
        lbl_count.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_count)

        return badge

    # =============================================================================
    # DATABASE TAB
    # =============================================================================

    def _build_database_tab(self) -> QWidget:
        """Build database management tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Database info
        db_group = self._create_card("💾 Database Information", ServerTheme.SUCCESS)
        db_layout = QVBoxLayout(db_group)

        self.db_info_label = QLabel("Loading database information...")
        self.db_info_label.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY};")
        db_layout.addWidget(self.db_info_label)

        self.db_path_label = QLabel(f"Path: {self.database_path}")
        self.db_path_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 11px;")
        db_layout.addWidget(self.db_path_label)

        # Database actions
        db_actions = QHBoxLayout()

        btn_open_folder = QPushButton("📁 Open Folder")
        btn_open_folder.setStyleSheet(self._get_button_style('secondary'))
        btn_open_folder.clicked.connect(self._open_db_folder)
        db_actions.addWidget(btn_open_folder)

        btn_backup = QPushButton("💾 Backup")
        btn_backup.setStyleSheet(self._get_button_style('success'))
        btn_backup.clicked.connect(self._backup_database)
        db_actions.addWidget(btn_backup)

        btn_export = QPushButton("📄 Export CSV")
        btn_export.setStyleSheet(self._get_button_style('info'))
        btn_export.clicked.connect(self._export_database_csv)
        db_actions.addWidget(btn_export)

        btn_vacuum = QPushButton("🧹 Vacuum")
        btn_vacuum.setStyleSheet(self._get_button_style('warning'))
        btn_vacuum.clicked.connect(self._vacuum_database)
        db_actions.addWidget(btn_vacuum)

        db_actions.addStretch()
        db_layout.addLayout(db_actions)

        layout.addWidget(db_group)

        return widget

    # =============================================================================
    # NETWORK TAB
    # =============================================================================

    def _build_network_tab(self) -> QWidget:
        """Build network information tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        network_group = self._create_card("🌐 Network Information", ServerTheme.INFO)
        network_layout = QVBoxLayout(network_group)

        self.network_info = QPlainTextEdit()
        self.network_info.setReadOnly(True)
        self.network_info.setMinimumHeight(300)
        self.network_info.setPlaceholderText("Network information will appear here...")
        self.network_info.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                padding: 10px;
                font-family: 'Courier New';
                font-size: 12px;
            }}
        """)
        network_layout.addWidget(self.network_info)

        # Instructions
        instructions = QLabel(
            "📱 Mobile App Setup:\n"
            "• Select one of the IP addresses above\n"
            "• Use port 8000 for Main Server\n"
            "• Use port 8001 for PDF Server\n"
            "• Enter your API key for authentication"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {ServerTheme.INFO}; font-weight: bold; padding: 10px;")
        network_layout.addWidget(instructions)

        layout.addWidget(network_group)

        return widget

    # =============================================================================
    # PDF SERVER TAB
    # =============================================================================

    def _build_pdf_server_tab(self) -> QWidget:
        """Build PDF server tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        pdf_group = self._create_card("📄 PDF API Server (Port 8001)", ServerTheme.WARNING)
        pdf_layout = QVBoxLayout(pdf_group)

        # Status
        status_row = QHBoxLayout()
        self.pdf_status_label = QLabel("PDF Server: Checking...")
        self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.INFO}; font-weight: bold; font-size: 16px;")
        status_row.addWidget(self.pdf_status_label)

        status_row.addStretch()

        self.pdf_port_label = QLabel("Port: 8001")
        self.pdf_port_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        status_row.addWidget(self.pdf_port_label)

        pdf_layout.addLayout(status_row)

        # URL display
        url_row = QHBoxLayout()
        url_label = QLabel("PDF API URL:")
        url_label.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY};")
        url_row.addWidget(url_label)

        self.pdf_url_input = QLineEdit()
        self.pdf_url_input.setReadOnly(True)
        self.pdf_url_input.setText("http://localhost:8001")
        self.pdf_url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                padding: 8px;
                border-radius: 4px;
            }}
        """)
        url_row.addWidget(self.pdf_url_input)

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_btn.clicked.connect(self._copy_pdf_url)
        url_row.addWidget(copy_btn)

        pdf_layout.addLayout(url_row)

        # Test button
        test_btn = QPushButton("🔌 Test Connection")
        test_btn.setStyleSheet(self._get_button_style('info'))
        test_btn.clicked.connect(self._test_pdf_server)
        pdf_layout.addWidget(test_btn)

        # Endpoints info
        endpoints_info = QTextEdit()
        endpoints_info.setReadOnly(True)
        endpoints_info.setMaximumHeight(150)
        endpoints_info.setPlainText(
            "Available Endpoints:\n"
            "  GET  /report   - Generate and download PDF report\n"
            "  GET  /health   - Server health check\n\n"
            "Android app uses:\n"
            "  http://<server-ip>:8001/report"
        )
        endpoints_info.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                padding: 10px;
                font-family: 'Courier New';
                font-size: 11px;
            }}
        """)
        pdf_layout.addWidget(endpoints_info)

        layout.addWidget(pdf_group)

        return widget

    # =============================================================================
    # CLOUDFLARE TUNNEL TAB
    # =============================================================================

    def _build_cloudflare_tab(self) -> QWidget:
        """Build Cloudflare tunnel tab"""
        print("[DEBUG] Building Cloudflare tab with NEW connection indicator UI")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # =====================================================
        # CONNECTION STATUS CARD - Large Visual Indicator
        # =====================================================
        status_card = QFrame()
        status_card.setStyleSheet(f"""
            QFrame {{
                background-color: {ServerTheme.CARD_BG};
                border: 2px solid {ServerTheme.BORDER};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        status_card_layout = QVBoxLayout(status_card)

        # Main status indicator row
        main_status_row = QHBoxLayout()

        # Large status indicator dot
        self.tunnel_indicator = QLabel("●")
        self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 48px;")
        main_status_row.addWidget(self.tunnel_indicator)

        # Status text
        status_text_layout = QVBoxLayout()
        self.tunnel_status_label = QLabel("DISCONNECTED")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 24px;")
        status_text_layout.addWidget(self.tunnel_status_label)

        self.tunnel_detail_label = QLabel("Tunnel not running - Click 'Start Tunnel' to connect")
        self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;")
        status_text_layout.addWidget(self.tunnel_detail_label)

        main_status_row.addLayout(status_text_layout)
        main_status_row.addStretch()

        # Test connection button
        self.test_conn_btn = QPushButton("🔍 Test Connection")
        self.test_conn_btn.setMinimumWidth(160)
        self.test_conn_btn.setMinimumHeight(45)
        self.test_conn_btn.setCursor(Qt.PointingHandCursor)
        self.test_conn_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
            QPushButton:disabled {
                background-color: #30363D;
                color: #8B949E;
            }
        """)
        self.test_conn_btn.clicked.connect(self._test_all_connections)
        main_status_row.addWidget(self.test_conn_btn)

        status_card_layout.addLayout(main_status_row)

        # Services status grid
        services_frame = QFrame()
        services_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #161B22;
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }}
        """)
        services_layout = QHBoxLayout(services_frame)
        services_layout.setSpacing(30)

        # OBD Server status
        self.obd_service_indicator = QLabel("● OBD Server (8000)")
        self.obd_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;")
        services_layout.addWidget(self.obd_service_indicator)

        # AI Server status
        self.ai_service_indicator = QLabel("● AI Server (12580)")
        self.ai_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;")
        services_layout.addWidget(self.ai_service_indicator)

        # PDF Server status
        self.pdf_service_indicator = QLabel("● PDF Server (8001)")
        self.pdf_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;")
        services_layout.addWidget(self.pdf_service_indicator)

        services_layout.addStretch()
        status_card_layout.addWidget(services_frame)

        layout.addWidget(status_card)

        # =====================================================
        # TUNNEL URLs SECTION
        # =====================================================
        url_group = QGroupBox("🔗 Public URLs")
        url_group.setStyleSheet(f"""
            QGroupBox {{
                color: {ServerTheme.TEXT_PRIMARY};
                font-weight: bold;
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 8px;
                margin-top: 15px;
                padding: 15px;
                background-color: {ServerTheme.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        url_layout = QGridLayout(url_group)
        url_layout.setSpacing(10)

        # Main API URL
        url_layout.addWidget(QLabel("Main API:"), 0, 0)
        self.tunnel_main_url = QLineEdit()
        self.tunnel_main_url.setReadOnly(True)
        self.tunnel_main_url.setText(self.tunnel.get_main_url())
        self.tunnel_main_url.setStyleSheet(f"background-color: #161B22; color: {ServerTheme.TEXT_PRIMARY}; padding: 8px; border-radius: 4px;")
        url_layout.addWidget(self.tunnel_main_url, 0, 1)

        copy_main_btn = QPushButton("📋 Copy")
        copy_main_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_main_btn.setFixedWidth(80)
        copy_main_btn.clicked.connect(self._copy_main_tunnel_url)
        url_layout.addWidget(copy_main_btn, 0, 2)

        # AI API URL
        url_layout.addWidget(QLabel("AI API:"), 1, 0)
        self.tunnel_ai_url = QLineEdit()
        self.tunnel_ai_url.setReadOnly(True)
        self.tunnel_ai_url.setText("https://ai.previlium.com")
        self.tunnel_ai_url.setStyleSheet(f"background-color: #161B22; color: {ServerTheme.TEXT_PRIMARY}; padding: 8px; border-radius: 4px;")
        url_layout.addWidget(self.tunnel_ai_url, 1, 1)

        copy_ai_btn = QPushButton("📋 Copy")
        copy_ai_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_ai_btn.setFixedWidth(80)
        copy_ai_btn.clicked.connect(lambda: self._copy_to_clipboard(self.tunnel_ai_url.text(), "AI API URL"))
        url_layout.addWidget(copy_ai_btn, 1, 2)

        # PDF API URL
        url_layout.addWidget(QLabel("PDF API:"), 2, 0)
        self.tunnel_pdf_url = QLineEdit()
        self.tunnel_pdf_url.setReadOnly(True)
        self.tunnel_pdf_url.setText(self.tunnel.get_pdf_url())
        self.tunnel_pdf_url.setStyleSheet(f"background-color: #161B22; color: {ServerTheme.TEXT_PRIMARY}; padding: 8px; border-radius: 4px;")
        url_layout.addWidget(self.tunnel_pdf_url, 2, 1)

        copy_pdf_btn = QPushButton("📋 Copy")
        copy_pdf_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_pdf_btn.setFixedWidth(80)
        copy_pdf_btn.clicked.connect(self._copy_pdf_tunnel_url)
        url_layout.addWidget(copy_pdf_btn, 2, 2)

        layout.addWidget(url_group)

        # =====================================================
        # CONTROL BUTTONS
        # =====================================================
        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)

        self.tunnel_start_btn = QPushButton("▶️ Start Tunnel")
        self.tunnel_start_btn.setMinimumHeight(45)
        self.tunnel_start_btn.setMinimumWidth(150)
        self.tunnel_start_btn.setCursor(Qt.PointingHandCursor)
        self.tunnel_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
            QPushButton:disabled {
                background-color: #30363D;
                color: #8B949E;
            }
        """)
        self.tunnel_start_btn.clicked.connect(self._start_tunnel)
        btn_row.addWidget(self.tunnel_start_btn)

        self.tunnel_stop_btn = QPushButton("⏹️ Stop Tunnel")
        self.tunnel_stop_btn.setMinimumHeight(45)
        self.tunnel_stop_btn.setStyleSheet(self._get_button_style('danger'))
        self.tunnel_stop_btn.clicked.connect(self._stop_tunnel)
        self.tunnel_stop_btn.setEnabled(False)
        btn_row.addWidget(self.tunnel_stop_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

        return widget

    def _copy_to_clipboard(self, text: str, name: str):
        """Copy text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        show_info(self, "Copied", f"{name} copied to clipboard")

    def _test_all_connections(self):
        """Test all service connections"""
        import threading

        self.test_conn_btn.setEnabled(False)
        self.test_conn_btn.setText("Testing...")
        self.tunnel_detail_label.setText("Testing all services...")

        def test_services():
            results = {
                'obd': False,
                'ai': False,
                'pdf': False,
                'public': False
            }

            # Test OBD Server (localhost:8000)
            try:
                import urllib.request
                req = urllib.request.Request('http://localhost:8000/health', method='GET')
                req.add_header('User-Agent', 'Predict-Desktop/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    results['obd'] = response.status == 200
            except:
                results['obd'] = False

            # Test AI Server (localhost:12580)
            try:
                req = urllib.request.Request('http://localhost:12580/health', method='GET')
                req.add_header('User-Agent', 'Predict-Desktop/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    results['ai'] = response.status == 200
            except:
                results['ai'] = False

            # Test PDF Server (localhost:8001)
            try:
                req = urllib.request.Request('http://localhost:8001/health', method='GET')
                req.add_header('User-Agent', 'Predict-Desktop/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    results['pdf'] = response.status == 200
            except:
                results['pdf'] = False

            # Test Public URL
            try:
                req = urllib.request.Request('https://predict.previlium.com/health', method='GET')
                req.add_header('User-Agent', 'Predict-Desktop/1.0')
                with urllib.request.urlopen(req, timeout=10) as response:
                    results['public'] = response.status == 200
            except:
                results['public'] = False

            # Update UI on main thread
            QTimer.singleShot(0, lambda: self._update_service_indicators(results))

        thread = threading.Thread(target=test_services, daemon=True)
        thread.start()

    def _update_service_indicators(self, results: dict):
        """Update service indicators based on test results"""
        green_style = f"color: {ServerTheme.SUCCESS}; font-size: 13px; font-weight: bold;"
        red_style = f"color: {ServerTheme.DANGER}; font-size: 13px; font-weight: bold;"

        # Update OBD indicator
        if results['obd']:
            self.obd_service_indicator.setText("● OBD Server (8000) - OK")
            self.obd_service_indicator.setStyleSheet(green_style)
        else:
            self.obd_service_indicator.setText("● OBD Server (8000) - OFFLINE")
            self.obd_service_indicator.setStyleSheet(red_style)

        # Update AI indicator
        if results['ai']:
            self.ai_service_indicator.setText("● AI Server (12580) - OK")
            self.ai_service_indicator.setStyleSheet(green_style)
        else:
            self.ai_service_indicator.setText("● AI Server (12580) - OFFLINE")
            self.ai_service_indicator.setStyleSheet(red_style)

        # Update PDF indicator
        if results['pdf']:
            self.pdf_service_indicator.setText("● PDF Server (8001) - OK")
            self.pdf_service_indicator.setStyleSheet(green_style)
        else:
            self.pdf_service_indicator.setText("● PDF Server (8001) - OFFLINE")
            self.pdf_service_indicator.setStyleSheet(red_style)

        # Update main status
        all_ok = results['obd'] and results['ai'] and results['public']
        if all_ok:
            self.tunnel_detail_label.setText("All services connected and accessible!")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 13px;")
        elif results['obd'] or results['ai']:
            self.tunnel_detail_label.setText("Some services running - check indicators below")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-size: 13px;")
        else:
            self.tunnel_detail_label.setText("Services offline - run C:\\OBDserver\\start_server.bat")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 13px;")

        # Re-enable test button
        self.test_conn_btn.setEnabled(True)
        self.test_conn_btn.setText("🔍 Test Connection")

    def _reset_service_indicators(self):
        """Reset all service indicators to unknown state"""
        gray_style = f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;"
        self.obd_service_indicator.setStyleSheet(gray_style)
        self.obd_service_indicator.setText("● OBD Server (8000)")
        self.ai_service_indicator.setStyleSheet(gray_style)
        self.ai_service_indicator.setText("● AI Server (12580)")
        self.pdf_service_indicator.setStyleSheet(gray_style)
        self.pdf_service_indicator.setText("● PDF Server (8001)")

    # =============================================================================
    # UI HELPER METHODS
    # =============================================================================

    def _create_card(self, title: str, color: str) -> QGroupBox:
        """Create a styled card"""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                color: {color};
                font-weight: bold;
                font-size: 14px;
                border: 1px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: {ServerTheme.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        return card

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get button stylesheet"""
        styles = {
            'primary': f"""
                QPushButton {{
                    background-color: {ServerTheme.PRIMARY};
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: #E53935; }}
                QPushButton:pressed {{ background-color: #A00000; }}
            """,
            'secondary': f"""
                QPushButton {{
                    background-color: {ServerTheme.CARD_BG};
                    color: {ServerTheme.TEXT_PRIMARY};
                    border: 1px solid {ServerTheme.BORDER};
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: {ServerTheme.BORDER}; }}
            """,
            'success': f"""
                QPushButton {{
                    background-color: {ServerTheme.SUCCESS};
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: #45a049; }}
            """,
            'danger': f"""
                QPushButton {{
                    background-color: {ServerTheme.DANGER};
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: #E53935; }}
            """,
            'warning': f"""
                QPushButton {{
                    background-color: {ServerTheme.WARNING};
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: #FFD54F; }}
            """,
            'info': f"""
                QPushButton {{
                    background-color: {ServerTheme.INFO};
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: #0CB5E5; }}
            """
        }
        return styles.get(style_type, styles['primary'])

    def _apply_table_styling(self, table_widget):
        """Apply table styling with forced text visibility"""
        table_widget.setStyleSheet(f"""
            QTableWidget {{
                background-color: {ServerTheme.CARD_BG};
                color: #FFFFFF;
                border: 1px solid {ServerTheme.BORDER};
                gridline-color: {ServerTheme.BORDER};
                border-radius: 8px;
                selection-background-color: {ServerTheme.PRIMARY};
                alternate-background-color: #262C35;
            }}
            QTableWidget::item {{
                padding: 10px 8px;
                border-bottom: 1px solid {ServerTheme.BORDER};
                color: #FFFFFF;
            }}
            QTableWidget::item:selected {{
                background-color: {ServerTheme.PRIMARY};
                color: #FFFFFF;
            }}
            QTableWidget::item:hover {{
                background-color: #2A3038;
                color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: #161B22;
                color: #F0F6FC;
                padding: 12px 10px;
                border: none;
                border-bottom: 2px solid {ServerTheme.PRIMARY};
                border-right: 1px solid {ServerTheme.BORDER};
                font-weight: 700;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: #161B22;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {ServerTheme.CARD_BG};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ServerTheme.BORDER};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
            QScrollBar:horizontal {{
                background-color: {ServerTheme.CARD_BG};
                height: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {ServerTheme.BORDER};
                border-radius: 6px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: #555;
            }}
        """)

    def _apply_compact_table_styling(self, table_widget):
        """Apply compact table styling with smaller fonts and padding"""
        table_widget.setStyleSheet(f"""
            QTableWidget {{
                background-color: {ServerTheme.CARD_BG};
                color: #FFFFFF;
                border: 1px solid {ServerTheme.BORDER};
                gridline-color: {ServerTheme.BORDER};
                border-radius: 6px;
                selection-background-color: {ServerTheme.PRIMARY};
                alternate-background-color: #262C35;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {ServerTheme.BORDER};
                color: #FFFFFF;
                font-size: 10px;
            }}
            QTableWidget::item:selected {{
                background-color: {ServerTheme.PRIMARY};
                color: #FFFFFF;
            }}
            QTableWidget::item:hover {{
                background-color: #2A3038;
                color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: #161B22;
                color: #F0F6FC;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid {ServerTheme.PRIMARY};
                border-right: 1px solid {ServerTheme.BORDER};
                font-weight: 700;
                font-size: 10px;
                text-transform: uppercase;
            }}
            QTableWidget QTableCornerButton::section {{
                background-color: #161B22;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {ServerTheme.CARD_BG};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ServerTheme.BORDER};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
            QScrollBar:horizontal {{
                background-color: {ServerTheme.CARD_BG};
                height: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {ServerTheme.BORDER};
                border-radius: 5px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: #555;
            }}
        """)

    # =============================================================================
    # API KEY MANAGEMENT
    # =============================================================================

    def _load_api_keys(self):
        """Load and display API keys"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'api_table'):
            return
        
        try:
            if not os.path.exists(self.api_keys_file):
                self.api_table.setRowCount(0)
                self._update_tier_counts()
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Get all available profiles for the dropdowns
            all_profiles = self._get_vehicle_profiles()

            self.api_table.setRowCount(len(api_keys))

            tier_counts = {"free": 0, "premium": 0, "admin": 0}

            for row, (key_id, key_data) in enumerate(api_keys.items()):
                tier = key_data.get('tier', 'free')
                tier_counts[tier] = tier_counts.get(tier, 0) + 1

                # Column 0: Name
                name_item = QTableWidgetItem(key_data.get('name', key_id))
                self.api_table.setItem(row, 0, name_item)

                # Column 1: Role (owner/driver/admin)
                role = key_data.get('role', 'owner')
                role_item = QTableWidgetItem(role.capitalize())
                role_colors = {
                    'owner': '#4CAF50',    # Green
                    'driver': '#2196F3',   # Blue
                    'admin': '#FF5722'     # Orange-red
                }
                role_item.setForeground(QColor(role_colors.get(role, '#FFFFFF')))
                self.api_table.setItem(row, 1, role_item)

                # Column 2: Apps (obd/guardian)
                apps = key_data.get('apps', ['obd', 'guardian'])
                if isinstance(apps, str):
                    apps = [a.strip() for a in apps.split(',')]
                apps_text = ', '.join([a.upper() for a in apps]) if apps else 'OBD'
                apps_item = QTableWidgetItem(apps_text)
                self.api_table.setItem(row, 2, apps_item)

                # Column 3: Owner (from owner_id or inferred)
                owner_name = key_data.get('owner_name', '')
                if not owner_name and key_data.get('owner_id'):
                    owner_name = f"Owner #{key_data.get('owner_id')}"
                owner_item = QTableWidgetItem(owner_name or '-')
                self.api_table.setItem(row, 3, owner_item)

                # Profile - Create dropdown selector with proper sizing
                profile_widget = QWidget()
                profile_layout = QHBoxLayout(profile_widget)
                profile_layout.setContentsMargins(3, 2, 3, 2)  # Compact padding
                profile_layout.setSpacing(2)

                # Profile combo dropdown - compact size
                profile_combo = QComboBox()
                profile_combo.setMinimumHeight(26)  # Compact height
                profile_combo.setMaximumHeight(26)  # Compact height
                profile_combo.setStyleSheet(f"""
                    QComboBox {{
                        padding: 3px 6px;
                        font-size: 9px;
                        font-weight: 500;
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        border-radius: 3px;
                    }}
                    QComboBox:hover {{
                        background-color: #2A3038;
                        border: 1px solid {ServerTheme.PRIMARY};
                    }}
                    QComboBox:focus {{
                        border: 1px solid {ServerTheme.PRIMARY};
                    }}
                    QComboBox::drop-down {{
                        subcontrol-origin: padding;
                        subcontrol-position: right center;
                        width: 16px;
                        border-left: 1px solid {ServerTheme.BORDER};
                        border-top-right-radius: 2px;
                        border-bottom-right-radius: 2px;
                        background-color: {ServerTheme.PRIMARY};
                    }}
                    QComboBox::down-arrow {{
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 4px solid #FFFFFF;
                        width: 0;
                        height: 0;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        selection-background-color: {ServerTheme.PRIMARY};
                        selection-color: #FFFFFF;
                        padding: 2px;
                        outline: none;
                    }}
                    QComboBox QAbstractItemView::item {{
                        height: 22px;
                        padding: 3px 6px;
                        color: #FFFFFF;
                        font-size: 9px;
                        border: none;
                    }}
                    QComboBox QAbstractItemView::item:hover {{
                        background-color: rgba(196, 0, 0, 0.3);
                        color: #FFFFFF;
                    }}
                    QComboBox QAbstractItemView::item:selected {{
                        background-color: {ServerTheme.PRIMARY};
                        color: #FFFFFF;
                    }}
                """)

                # Add "No Profile" option (for admin keys)
                profile_combo.addItem("🔓 No Profile (System Admin)", {'type': 'none', 'id': None})

                # Add all available entities (owners, vehicles, drivers)
                for entity in all_profiles:
                    display_text = entity.get('display_text', entity.get('name', 'Unknown'))
                    # Store entity data with type and IDs
                    entity_data = {
                        'type': entity.get('type', 'vehicle'),
                        'id': entity.get('id'),
                        'profile_id': entity.get('profile_id'),
                        'owner_id': entity.get('owner_id'),
                        'driver_id': entity.get('driver_id'),
                        'name': entity.get('name', 'Unknown')
                    }
                    profile_combo.addItem(display_text, entity_data)

                # Set current selection based on key's linked entity
                current_profile_id = key_data.get('profile_id')
                current_owner_id = key_data.get('owner_id')
                current_driver_id = key_data.get('driver_id')
                current_profile_name = key_data.get('profile_name', 'N/A')

                # Find and select the current entity
                found_index = -1
                for i in range(profile_combo.count()):
                    item_data = profile_combo.itemData(i)
                    if item_data and isinstance(item_data, dict):
                        # Match by driver_id first (most specific)
                        if current_driver_id and item_data.get('driver_id') == current_driver_id:
                            found_index = i
                            break
                        # Match by profile_id (vehicle)
                        if current_profile_id and item_data.get('profile_id') == current_profile_id and item_data.get('type') == 'vehicle':
                            found_index = i
                            break
                        # Match by owner_id
                        if current_owner_id and item_data.get('owner_id') == current_owner_id and item_data.get('type') == 'owner':
                            found_index = i
                            break

                if found_index >= 0:
                    profile_combo.setCurrentIndex(found_index)
                elif tier == 'admin':
                    # Admin keys default to "No Profile"
                    profile_combo.setCurrentIndex(0)

                # Connect change event
                profile_combo.currentIndexChanged.connect(
                    lambda index, k=key_id, c=profile_combo: self._on_api_key_profile_changed(k, c)
                )

                profile_layout.addWidget(profile_combo, 1)
                self.api_table.setCellWidget(row, 4, profile_widget)  # Vehicle column

                # Highlight admin rows with a subtle background
                if tier == 'admin':
                    for col in range(9):  # 9 columns now
                        item = self.api_table.item(row, col)
                        if item is None:
                            item = QTableWidgetItem()
                            self.api_table.setItem(row, col, item)
                        item.setBackground(QColor(ServerTheme.ADMIN_TIER).lighter(230))

                # Column 5: API Key (masked)
                api_key = key_data.get('key_hidden', '••••••••••••••••')
                key_item = QTableWidgetItem(api_key)
                self.api_table.setItem(row, 5, key_item)

                # Column 6: Created
                created = key_data.get('created', 'Unknown')
                if created != 'Unknown':
                    try:
                        dt = datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                date_item = QTableWidgetItem(created)
                self.api_table.setItem(row, 6, date_item)

                # Column 7: Status
                status = key_data.get('status', 'active')
                status_item = QTableWidgetItem(status.upper())
                if status == 'active':
                    status_item.setForeground(QColor(ServerTheme.SUCCESS))
                elif status == 'revoked':
                    status_item.setForeground(QColor(ServerTheme.DANGER))
                self.api_table.setItem(row, 7, status_item)

                # Actions - compact buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(3, 2, 3, 2)
                actions_layout.setSpacing(3)

                # View/Reveal button - compact
                view_btn = QPushButton("👁️")
                view_btn.setFixedSize(24, 24)  # Compact button size
                view_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: {ServerTheme.INFO};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.INFO};
                    }}
                    QPushButton:pressed {{
                        background-color: #0B8FA6;
                    }}
                """)
                view_btn.setToolTip("View/Reveal API Key")
                view_btn.setCursor(Qt.PointingHandCursor)
                view_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._reveal_api_key(k, d))
                actions_layout.addWidget(view_btn)

                # Copy button - compact
                copy_btn = QPushButton("📋")
                copy_btn.setFixedSize(24, 24)
                copy_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: {ServerTheme.SUCCESS};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.SUCCESS};
                    }}
                    QPushButton:pressed {{
                        background-color: #3A8E3A;
                    }}
                """)
                copy_btn.setToolTip("Copy API Key to Clipboard")
                copy_btn.setCursor(Qt.PointingHandCursor)
                copy_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._copy_api_key(k, d))
                actions_layout.addWidget(copy_btn)

                # Edit button - compact
                edit_btn = QPushButton("✏️")
                edit_btn.setFixedSize(24, 24)
                edit_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: {ServerTheme.WARNING};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.WARNING};
                    }}
                    QPushButton:pressed {{
                        background-color: #CC8400;
                    }}
                """)
                edit_btn.setToolTip("Edit API Key (Role, Apps, Permissions)")
                edit_btn.setCursor(Qt.PointingHandCursor)
                edit_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._edit_api_key_dialog(k, d))
                actions_layout.addWidget(edit_btn)

                # Regenerate Key button - compact
                regen_btn = QPushButton("🔄")
                regen_btn.setFixedSize(24, 24)
                regen_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: {ServerTheme.PRIMARY};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.PRIMARY};
                    }}
                    QPushButton:pressed {{
                        background-color: #A00000;
                    }}
                """)
                regen_btn.setToolTip("Regenerate API Key (sends email)")
                regen_btn.setCursor(Qt.PointingHandCursor)
                regen_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._regenerate_api_key(k, d))
                actions_layout.addWidget(regen_btn)

                # Send Email button - compact
                email_btn = QPushButton("📧")
                email_btn.setFixedSize(24, 24)
                email_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.CARD_BG};
                        color: #FFFFFF;
                        border: 1px solid {ServerTheme.BORDER};
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: #2196F3;
                        color: #FFFFFF;
                        border: 1px solid #2196F3;
                    }}
                    QPushButton:pressed {{
                        background-color: #1565C0;
                    }}
                """)
                email_btn.setToolTip("Send API Key via Email")
                email_btn.setCursor(Qt.PointingHandCursor)
                email_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._send_api_key_email(k, d))
                actions_layout.addWidget(email_btn)

                # Delete button - compact
                delete_btn = QPushButton("🗑️")
                delete_btn.setFixedSize(24, 24)
                delete_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ServerTheme.DANGER};
                        color: #FFFFFF;
                        border: none;
                        padding: 0px;
                        font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: #E53935;
                        color: #FFFFFF;
                    }}
                    QPushButton:pressed {{
                        background-color: #A00000;
                    }}
                """)
                delete_btn.setToolTip("Delete API Key")
                delete_btn.setCursor(Qt.PointingHandCursor)
                delete_btn.clicked.connect(lambda checked, k=key_id, d=key_data: self._delete_api_key(k, d))
                actions_layout.addWidget(delete_btn)

                actions_layout.addStretch()  # Push buttons to the left
                self.api_table.setCellWidget(row, 8, actions_widget)  # Column 8: Actions

            self._update_tier_counts(tier_counts)

        except Exception as e:
            show_error(self, "Error", f"Failed to load API keys: {e}")

    def _update_tier_counts(self, counts: Dict[str, int] = None):
        """Update tier count badges"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'tier_free_count'):
            return
        
        if counts is None:
            counts = {"free": 0, "premium": 0, "admin": 0}

        for badge, count in [
            (self.tier_free_count, counts.get("free", 0)),
            (self.tier_premium_count, counts.get("premium", 0)),
            (self.tier_admin_count, counts.get("admin", 0))
        ]:
            for child in badge.findChildren(QLabel):
                if child.text().isdigit():
                    child.setText(str(count))

    def _on_api_key_profile_changed(self, key_id: str, combo: QComboBox):
        """Handle when user changes entity assignment for an API key"""
        try:
            # Get the new entity selection (now a dict with type, id, profile_id, owner_id, driver_id)
            entity_data = combo.currentData()
            selected_text = combo.currentText()

            # Load existing keys
            if not os.path.exists(self.api_keys_file):
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            if key_id not in api_keys:
                return

            # Get the key data
            key_data = api_keys[key_id]
            old_profile_name = key_data.get('profile_name', 'None')

            # Update based on entity type
            if entity_data is None or (isinstance(entity_data, dict) and entity_data.get('type') == 'none'):
                # Admin key - no profile
                api_keys[key_id]['profile_id'] = None
                api_keys[key_id]['owner_id'] = None
                api_keys[key_id]['driver_id'] = None
                api_keys[key_id]['profile_name'] = "System Admin"
            elif isinstance(entity_data, dict):
                entity_type = entity_data.get('type', 'vehicle')
                entity_name = entity_data.get('name', 'Unknown')

                if entity_type == 'owner':
                    # Owner selected
                    api_keys[key_id]['owner_id'] = entity_data.get('owner_id')
                    api_keys[key_id]['profile_id'] = None  # Owner, not specific vehicle
                    api_keys[key_id]['driver_id'] = None
                    api_keys[key_id]['profile_name'] = f"Owner: {entity_name}"
                    api_keys[key_id]['role'] = 'owner'
                    api_keys[key_id]['apps'] = ['obd', 'guardian']  # Owners get both apps

                elif entity_type == 'driver':
                    # Driver selected
                    api_keys[key_id]['driver_id'] = entity_data.get('driver_id')
                    api_keys[key_id]['profile_id'] = entity_data.get('profile_id')  # Vehicle for this driver
                    api_keys[key_id]['owner_id'] = entity_data.get('owner_id')
                    api_keys[key_id]['profile_name'] = f"Driver: {entity_name}"
                    api_keys[key_id]['role'] = 'driver'
                    api_keys[key_id]['apps'] = ['obd']  # Drivers only get OBD

                else:  # vehicle
                    # Vehicle selected
                    api_keys[key_id]['profile_id'] = entity_data.get('profile_id')
                    api_keys[key_id]['owner_id'] = entity_data.get('owner_id')
                    api_keys[key_id]['driver_id'] = None
                    api_keys[key_id]['profile_name'] = entity_name
                    # Keep existing role and apps for vehicle selection
            else:
                # Fallback: old format (just profile_id)
                api_keys[key_id]['profile_id'] = entity_data
                api_keys[key_id]['profile_name'] = selected_text.split('(')[0].strip().replace('🚗', '').strip()

            # Save the updated keys
            with open(self.api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Show success message
            new_profile_name = api_keys[key_id].get('profile_name', 'Unknown')
            show_info(
                self, "Assignment Updated",
                f"API key '{key_data.get('name', key_id)}' assignment changed:\n"
                f"From: {old_profile_name}\n"
                f"To: {new_profile_name}"
            )

            # Refresh table to show update
            self._load_api_keys()

        except Exception as e:
            show_error(self, "Error", f"Failed to update assignment: {e}")

    def _generate_customer_api_key(self):
        """Generate a customer API key (free or premium)"""
        try:
            entities = self._get_vehicle_profiles()

            if not entities:
                show_warning(
                    self, "No Profiles",
                    "No owners, vehicles, or drivers found. Please create a vehicle profile first."
                )
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Generate Customer API Key")
            dialog.setMinimumWidth(550)

            layout = QVBoxLayout(dialog)

            form = QFormLayout()

            # Entity selection with better display
            entity_label = QLabel("Assign to Owner/Vehicle/Driver:")
            entity_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(entity_label)

            # Entity combo with detailed items
            entity_combo = QComboBox()
            entity_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 8px;
                    font-size: 13px;
                    background-color: {ServerTheme.CARD_BG};
                    color: {ServerTheme.TEXT_PRIMARY};
                }}
                QComboBox::drop-down {{
                    border: 1px solid {ServerTheme.PRIMARY};
                }}
            """)

            for entity in entities:
                display_text = entity.get('display_text', entity.get('name', 'Unknown'))
                # Store the full entity data
                entity_combo.addItem(display_text, entity)

            # Add entity details display
            entity_details = QLabel()
            entity_details.setStyleSheet(f"""
                QLabel {{
                    background-color: {ServerTheme.BACKGROUND};
                    border: 1px solid {ServerTheme.BORDER};
                    border-radius: 5px;
                    padding: 10px;
                    color: {ServerTheme.TEXT_PRIMARY};
                }}
            """)
            entity_details.setWordWrap(True)

            # Update entity details when selection changes
            def update_entity_details(index):
                if index >= 0 and index < len(entities):
                    e = entities[index]
                    entity_type = e.get('type', 'vehicle')

                    if entity_type == 'owner':
                        details_text = f"""
👤 Type: Owner
📛 Name: {e.get('name', 'Unknown')}
🚗 Vehicles: {e.get('vehicle_count', 0)}
👥 Drivers: {e.get('driver_count', 0)}
📱 Apps: OBD + Guardian (Full Access)
                        """.strip()
                    elif entity_type == 'driver':
                        details_text = f"""
🚘 Type: Driver
📛 Name: {e.get('name', 'Unknown')}
🚗 Vehicle: {e.get('vehicle_name', 'Unknown')}
⭐ Primary: {'Yes' if e.get('is_primary') else 'No'}
📱 Apps: OBD Only (Limited Access)
                        """.strip()
                    else:  # vehicle
                        details_text = f"""
🚗 Type: Vehicle
📛 Name: {e.get('name', 'Unknown')}
🏭 Make: {e.get('make', 'Unknown')} {e.get('model', '')} {e.get('year', '')}
🆔 Profile ID: {e.get('profile_id', 'N/A')}
📱 Apps: Based on tier selection
                        """.strip()

                    entity_details.setText(details_text)

            entity_combo.currentIndexChanged.connect(update_entity_details)
            layout.addWidget(entity_combo)
            layout.addWidget(entity_details)

            # Initialize with first entity
            if entities:
                update_entity_details(0)

            layout.addSpacing(10)

            # Key name
            name_label = QLabel("API Key Name:")
            name_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(name_label)

            name_input = QLineEdit()
            name_input.setPlaceholderText("e.g., John's iPhone, Company Tablet, etc.")
            name_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 8px;
                    background-color: {ServerTheme.CARD_BG};
                    color: {ServerTheme.TEXT_PRIMARY};
                    border: 1px solid {ServerTheme.BORDER};
                    border-radius: 5px;
                }}
            """)
            layout.addWidget(name_input)

            # Tier selection
            tier_label = QLabel("Access Tier:")
            tier_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(tier_label)

            tier_combo = QComboBox()
            tier_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 8px;
                    font-size: 13px;
                    background-color: {ServerTheme.CARD_BG};
                    color: {ServerTheme.TEXT_PRIMARY};
                }}
            """)
            tier_combo.addItem("🔓 Free Tier - Basic vehicle data only", "free")
            tier_combo.addItem("⭐ Premium Tier - Full access + predictions + AI chat", "premium")
            layout.addWidget(tier_combo)

            layout.addSpacing(15)

            # Info banner
            info_banner = QLabel()
            info_banner.setStyleSheet(f"""
                QLabel {{
                    background-color: rgba(13, 202, 240, 0.15);
                    border: 1px solid {ServerTheme.INFO};
                    border-radius: 5px;
                    padding: 10px;
                    color: {ServerTheme.TEXT_PRIMARY};
                }}
            """)
            info_banner.setWordWrap(True)
            info_banner.setText(
                "ℹ️ Select an Owner (full access to OBD + Guardian apps), "
                "Vehicle (specific vehicle access), or Driver (OBD app only)."
            )
            layout.addWidget(info_banner)

            layout.addSpacing(10)

            # Buttons
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("✅ Generate API Key")
            ok_btn.setStyleSheet(self._get_button_style('success'))
            cancel_btn = QPushButton("❌ Cancel")
            cancel_btn.setStyleSheet(self._get_button_style('secondary'))
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            if dialog.exec() != QDialog.Accepted:
                return

            name = name_input.text().strip()
            if not name:
                show_warning(self, "Invalid Input", "Please enter a name for the API key.")
                return

            selected_entity = entity_combo.currentData()
            tier = tier_combo.currentData()

            # Extract IDs based on entity type
            entity_type = selected_entity.get('type', 'vehicle')
            profile_id = selected_entity.get('profile_id')
            owner_id = selected_entity.get('owner_id')
            driver_id = selected_entity.get('driver_id')
            entity_name = selected_entity.get('name', 'Unknown')

            # Set role and apps based on entity type
            if entity_type == 'owner':
                profile_name = f"Owner: {entity_name}"
                role = 'owner'
                apps = ['obd', 'guardian']
            elif entity_type == 'driver':
                profile_name = f"Driver: {entity_name}"
                role = 'driver'
                apps = ['obd']
            else:
                profile_name = entity_name
                role = 'owner'  # Default for vehicle
                apps = ['obd', 'guardian'] if tier == 'premium' else ['obd']

            # Create and save the API key with extended data
            self._create_and_save_api_key(
                name, profile_id, profile_name, tier,
                owner_id=owner_id, driver_id=driver_id, role=role, apps=apps
            )

        except Exception as e:
            show_error(self, "Error", f"Failed to generate API key: {e}")

    def _generate_admin_api_key(self):
        """Generate an admin API key (requires password)"""
        # Prompt for admin password
        password, ok = QInputDialog.getText(
            self, "Admin Authentication",
            "Enter admin password to generate admin key:",
            QLineEdit.Password
        )

        if not ok or not password:
            return

        # Verify password
        if password != self.admin_password:
            show_error(self, "Authentication Failed", "Invalid admin password!")
            return

        # Get admin key name
        name, ok = QInputDialog.getText(
            self, "Admin API Key",
            "Enter a name for this admin key:",
            QLineEdit.Normal,
            "Admin Master Key"
        )

        if not ok or not name.strip():
            return

        # Ask if should link to existing profile/owner
        profile_id = None
        owner_id = None
        profile_name = "System Admin"

        reply = QMessageBox.question(
            self, "Link to Profile?",
            "Do you want to link this admin key to an existing owner/profile?\n\n"
            "This allows the key to show up in the Profile tab.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # Get available profiles
            profiles = self._get_vehicle_profiles()
            owners = [p for p in profiles if p.get('type') == 'owner']

            if owners:
                # Create selection dialog
                items = [f"{o.get('name', 'Unknown')} (Owner #{o.get('owner_id', 'N/A')})" for o in owners]
                item, ok = QInputDialog.getItem(
                    self, "Select Owner",
                    "Link admin key to owner:",
                    items, 0, False
                )
                if ok and item:
                    idx = items.index(item)
                    selected = owners[idx]
                    owner_id = selected.get('owner_id')
                    profile_id = selected.get('profile_id')
                    profile_name = f"Admin: {selected.get('name', 'Unknown')}"
            else:
                show_warning(self, "No Owners", "No owner profiles found. Creating unlinked admin key.")

        # Create admin key
        self._create_and_save_api_key(
            name.strip(),
            profile_id=profile_id,
            profile_name=profile_name,
            tier="admin",
            owner_id=owner_id,
            role='admin',
            apps=['obd', 'guardian']
        )

    def _create_and_save_api_key(
        self,
        name: str,
        profile_id: Optional[int],
        profile_name: str,
        tier: str,
        owner_id: Optional[int] = None,
        driver_id: Optional[str] = None,
        role: str = 'owner',
        apps: Optional[list] = None
    ):
        """Create and save an API key"""
        try:
            # Generate API key
            api_key = ApiKeyTier.generate_key(tier)
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Encrypt the key for storage
            key_encrypted = SimpleEncryption.encrypt(api_key, self.admin_password)

            # Load existing keys
            api_keys = {}
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r') as f:
                    api_keys = json.load(f)

            # Create unique key identifier
            key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

            # Get tier info
            tier_info = ApiKeyTier.get_tier_info(tier)

            # Default apps based on tier if not specified
            if apps is None:
                if tier == 'admin':
                    apps = ['obd', 'guardian']
                elif role == 'driver':
                    apps = ['obd']
                else:
                    apps = ['obd', 'guardian']

            # Add new key with extended fields
            api_keys[key_id] = {
                "key_hash": key_hash,
                "key_encrypted": key_encrypted,
                "key_hidden": f"{tier_info['prefix']}{'•' * (tier_info['key_length'] - len(tier_info['prefix']))}",
                "name": name,
                "tier": tier,
                "role": role,
                "apps": apps,
                "profile_id": profile_id,
                "owner_id": owner_id,
                "driver_id": driver_id,
                "profile_name": profile_name,
                "permissions": tier_info["permissions"],
                "created": datetime.now().isoformat(),
                "status": "active"
            }

            # Save keys
            os.makedirs(os.path.dirname(self.api_keys_file), exist_ok=True)
            with open(self.api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Auto-sync to server
            try:
                from api_key_sync import sync_single_key_to_server
                sync_single_key_to_server(key_id, api_keys[key_id])
                print(f"✓ API key auto-synced to server")
            except Exception as sync_error:
                print(f"Warning: Failed to auto-sync API key to server: {sync_error}")

            # Save backup file
            self._save_api_key_backup(api_key, name, profile_name, tier)

            # Show success dialog
            self._show_api_key_success(api_key, name, profile_name, tier)

            # Reload table
            self._load_api_keys()

        except Exception as e:
            show_error(self, "Error", f"Failed to generate API key: {e}")

    def _save_api_key_backup(self, api_key: str, name: str, profile_name: str, tier: str):
        """Save API key to backup file"""
        try:
            if CONFIG:
                keys_folder = str(CONFIG.get_customer_api_keys_dir("default"))
            else:
                keys_folder = "API_KEYS"

            os.makedirs(keys_folder, exist_ok=True)

            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            key_filename = os.path.join(keys_folder, f"{safe_name}_{tier}_{timestamp}_apikey.txt")

            with open(key_filename, 'w') as f:
                f.write("╔════════════════════════════════════════════════════════════╗\n")
                f.write("║         PREDICT OBD - API KEY CREDENTIALS                    ║\n")
                f.write("╚════════════════════════════════════════════════════════════╝\n\n")
                f.write(f"Key Name:    {name}\n")
                f.write(f"Tier:         {tier.upper()}\n")
                f.write(f"Profile:      {profile_name}\n")
                f.write(f"Generated:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("─" * 64 + "\n")
                f.write("API KEY (keep this secret!):\n")
                f.write("─" * 64 + "\n")
                f.write(f"{api_key}\n")
                f.write("─" * 64 + "\n\n")
                f.write("SETUP INSTRUCTIONS:\n")
                f.write("1. Open Predict OBD Android app\n")
                f.write("2. Go to Settings → Server Connection\n")
                f.write("3. Enter Server IP and Port 8000\n")
                f.write("4. Paste this API key\n")
                f.write("5. Save and enjoy!\n")

        except Exception as e:
            print(f"Warning: Could not save backup file: {e}")

    def _show_api_key_success(self, api_key: str, name: str, profile_name: str, tier: str):
        """Show API key success dialog"""
        tier_info = ApiKeyTier.get_tier_info(tier)

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(f"{tier_info['name']} API Key Generated")
        msg.setText(f"API key generated successfully!\n\n• Name: {name}\n• Tier: {tier_info['name']}\n• Profile: {profile_name}")

        # Create text edit for key
        key_display = QTextEdit()
        key_display.setPlainText(api_key)
        key_display.setReadOnly(True)
        key_display.setMaximumHeight(80)
        key_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {tier_info['color']};
                border: 2px solid {tier_info['color']};
                padding: 15px;
                font-family: 'Courier New';
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        msg.layout().addWidget(key_display, 1, 1)

        copy_btn = msg.addButton("📋 Copy to Clipboard", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)

        msg.exec()

        if msg.clickedButton() == copy_btn:
            QApplication.clipboard().setText(api_key)
            show_info(self, "Copied", "API key copied to clipboard!")

    def _edit_api_key_dialog(self, key_id: str, key_data: Dict):
        """Open dialog to edit API key role, apps, and permissions"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QComboBox, QCheckBox,
                                       QDialogButtonBox, QLabel, QHBoxLayout,
                                       QGroupBox)

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit API Key")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ServerTheme.BACKGROUND};
                color: #FFFFFF;
            }}
            QLabel {{
                color: #FFFFFF;
                font-size: 12px;
            }}
            QLineEdit, QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: #FFFFFF;
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {ServerTheme.PRIMARY};
            }}
            QCheckBox {{
                color: #FFFFFF;
                spacing: 8px;
            }}
            QGroupBox {{
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"Edit API Key: {key_data.get('name', key_id)}")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ServerTheme.PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        # Name
        name_input = QLineEdit()
        name_input.setText(key_data.get('name', ''))
        form.addRow("Name:", name_input)

        # Email
        email_input = QLineEdit()
        email_input.setText(key_data.get('email', ''))
        email_input.setPlaceholderText("customer@example.com")
        form.addRow("Email:", email_input)

        # Role
        role_combo = QComboBox()
        role_combo.addItems(["owner", "driver", "admin"])
        current_role = key_data.get('role', 'owner')
        if current_role in ["owner", "driver", "admin"]:
            role_combo.setCurrentText(current_role)
        form.addRow("Role:", role_combo)

        # Tier
        tier_combo = QComboBox()
        tier_combo.addItems(["free", "premium", "admin"])
        current_tier = key_data.get('tier', 'free')
        if current_tier in ["free", "premium", "admin"]:
            tier_combo.setCurrentText(current_tier)
        form.addRow("Tier:", tier_combo)

        # Profile linking section
        link_group = QGroupBox("Profile Linking")
        link_layout = QVBoxLayout(link_group)

        # Show current link status
        current_profile = key_data.get('profile_id')
        current_owner = key_data.get('owner_id')
        link_status = "Not linked to any profile"
        if current_owner:
            link_status = f"Linked to Owner #{current_owner}"
            if current_profile:
                link_status += f", Profile #{current_profile}"

        link_status_label = QLabel(link_status)
        link_status_label.setStyleSheet("color: #888; font-style: italic;")
        link_layout.addWidget(link_status_label)

        # Link to profile button
        link_btn = QPushButton("🔗 Link to Profile/Owner")
        link_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ServerTheme.INFO};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #0B8FA6;
            }}
        """)

        # Store selected profile/owner IDs
        selected_ids = {'profile_id': current_profile, 'owner_id': current_owner}

        def select_profile():
            profiles = self._get_vehicle_profiles()
            owners = [p for p in profiles if p.get('type') == 'owner']
            if not owners:
                show_warning(self, "No Owners", "No owner profiles found.")
                return

            items = ["(Unlink - No Profile)"] + [
                f"{o.get('name', 'Unknown')} (Owner #{o.get('owner_id', 'N/A')}, Profile #{o.get('profile_id', 'N/A')})"
                for o in owners
            ]
            item, ok = QInputDialog.getItem(self, "Select Owner", "Link to owner:", items, 0, False)
            if ok:
                if item == "(Unlink - No Profile)":
                    selected_ids['profile_id'] = None
                    selected_ids['owner_id'] = None
                    link_status_label.setText("Will be unlinked")
                else:
                    idx = items.index(item) - 1
                    selected = owners[idx]
                    selected_ids['profile_id'] = selected.get('profile_id')
                    selected_ids['owner_id'] = selected.get('owner_id')
                    link_status_label.setText(f"Will link to: {selected.get('name')}")

        link_btn.clicked.connect(select_profile)
        link_layout.addWidget(link_btn)
        layout.addWidget(link_group)

        layout.addLayout(form)

        # Apps section
        apps_group = QGroupBox("App Access")
        apps_layout = QHBoxLayout(apps_group)
        current_apps = key_data.get('apps', ['obd', 'guardian'])
        if isinstance(current_apps, str):
            current_apps = [a.strip() for a in current_apps.split(',')]

        obd_check = QCheckBox("OBD App")
        obd_check.setChecked('obd' in current_apps)
        guardian_check = QCheckBox("Guardian App")
        guardian_check.setChecked('guardian' in current_apps)
        apps_layout.addWidget(obd_check)
        apps_layout.addWidget(guardian_check)
        layout.addWidget(apps_group)

        # Permissions section
        perm_group = QGroupBox("Permissions")
        perm_layout = QVBoxLayout(perm_group)
        current_perms = key_data.get('permissions', ['vehicle_data', 'predict'])

        perm_checks = {}
        all_perms = ['vehicle_data', 'predict', 'diagnostic', 'llm_chat', 'admin']
        for perm in all_perms:
            cb = QCheckBox(perm.replace('_', ' ').title())
            cb.setChecked(perm in current_perms)
            perm_layout.addWidget(cb)
            perm_checks[perm] = cb

        layout.addWidget(perm_group)

        # Status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_combo = QComboBox()
        status_combo.addItems(["active", "revoked"])
        status_combo.setCurrentText(key_data.get('status', 'active'))
        status_layout.addWidget(status_label)
        status_layout.addWidget(status_combo, 1)
        layout.addLayout(status_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ServerTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E53935;
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            # Build updated data
            new_apps = []
            if obd_check.isChecked():
                new_apps.append('obd')
            if guardian_check.isChecked():
                new_apps.append('guardian')

            new_perms = [perm for perm, cb in perm_checks.items() if cb.isChecked()]

            updated_data = {
                'name': name_input.text().strip() or key_data.get('name', ''),
                'email': email_input.text().strip() or key_data.get('email', ''),
                'role': role_combo.currentText(),
                'tier': tier_combo.currentText(),
                'apps': new_apps,
                'permissions': new_perms,
                'status': status_combo.currentText(),
                'profile_id': selected_ids.get('profile_id'),
                'owner_id': selected_ids.get('owner_id')
            }

            self._save_api_key_changes(key_id, updated_data)

    def _save_api_key_changes(self, key_id: str, updated_data: Dict):
        """Save changes to an API key"""
        try:
            if not os.path.exists(self.api_keys_file):
                show_error(self, "Error", "API keys file not found")
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            if key_id not in api_keys:
                show_error(self, "Error", "API key not found")
                return

            # Update the key data
            for field, value in updated_data.items():
                api_keys[key_id][field] = value

            # Save to desktop file
            with open(self.api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Sync to server via API (preferred) or file sync (fallback)
            sync_success = False
            try:
                from server_api_client import get_server_client
                client = get_server_client()
                response = client.update_api_key(
                    key_id,
                    tier=updated_data.get('tier'),
                    apps=updated_data.get('apps'),
                    permissions=updated_data.get('permissions'),
                    status=updated_data.get('status'),
                    name=updated_data.get('name'),
                    email=updated_data.get('email')
                )
                if response.success:
                    sync_success = True
                    logger.info(f"API key {key_id} synced via server API")
            except Exception as api_err:
                logger.warning(f"Server API sync failed: {api_err}, trying file sync")

            # Fallback to file-based sync
            if not sync_success:
                try:
                    from api_key_sync import sync_api_keys_to_server
                    sync_api_keys_to_server()
                    sync_success = True
                except Exception as e:
                    logger.warning(f"Failed to sync API key changes to server: {e}")

            show_info(self, "Success", f"API key updated successfully{' (synced)' if sync_success else ''}")
            self._load_api_keys()  # Refresh table

        except Exception as e:
            show_error(self, "Error", f"Failed to save API key changes: {e}")

    def _reveal_api_key(self, key_id: str, key_data: Dict):
        """Reveal an API key (requires password for admin keys)"""
        try:
            tier = key_data.get('tier', 'free')

            # Admin keys require password
            if tier == 'admin':
                password, ok = QInputDialog.getText(
                    self, "Security Verification",
                    "Enter admin password to reveal this key:",
                    QLineEdit.Password
                )
                if not ok or not password:
                    return
                if password != self.admin_password:
                    show_error(self, "Authentication Failed", "Invalid admin password!")
                    return

            # Decrypt key
            key_encrypted = key_data.get('key_encrypted')
            if not key_encrypted:
                show_warning(self, "Not Available", "This API key cannot be revealed (old format).")
                return

            api_key = SimpleEncryption.decrypt(key_encrypted, self.admin_password)

            if not api_key:
                show_error(self, "Decryption Failed", "Could not decrypt API key.")
                return

            # Show dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"API Key - {key_data.get('name', key_id)}")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)

            info = QLabel(
                f"Name: {key_data.get('name', key_id)}\n"
                f"Tier: {tier.upper()}\n"
                f"Profile: {key_data.get('profile_name', 'N/A')}"
            )
            layout.addWidget(info)

            key_display = QTextEdit()
            key_display.setPlainText(api_key)
            key_display.setReadOnly(True)
            key_display.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {ApiKeyTier.get_tier_info(tier)['color']};
                    color: #FFFFFF;
                    padding: 20px;
                    font-family: 'Courier New';
                    font-size: 18px;
                    font-weight: bold;
                    border-radius: 8px;
                }}
            """)
            layout.addWidget(key_display)

            btn_layout = QHBoxLayout()
            copy_btn = QPushButton("📋 Copy")
            copy_btn.setStyleSheet(self._get_button_style('success'))
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(api_key))
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(self._get_button_style('secondary'))
            close_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(copy_btn)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

            dialog.exec()

        except Exception as e:
            show_error(self, "Error", f"Failed to reveal API key: {e}")

    def _copy_api_key(self, key_id: str, key_data: Dict):
        """Copy API key to clipboard"""
        try:
            # Decrypt key
            key_encrypted = key_data.get('key_encrypted')
            if not key_encrypted:
                show_warning(self, "Not Available", "This API key uses old format and cannot be copied.")
                return

            api_key = SimpleEncryption.decrypt(key_encrypted, self.admin_password)
            if not api_key:
                show_error(self, "Decryption Failed", "Could not decrypt API key.")
                return

            QApplication.clipboard().setText(api_key)
            show_info(self, "Copied", "API key copied to clipboard!")

        except Exception as e:
            show_error(self, "Error", f"Failed to copy API key: {e}")

    def _delete_api_key(self, key_id: str, key_data: Dict):
        """Delete an API key"""
        try:
            name = key_data.get('name', key_id)
            tier = key_data.get('tier', 'free').upper()
            profile = key_data.get('profile_name', 'N/A')

            reply = QMessageBox.question(
                self, "Delete API Key",
                f"Are you sure you want to delete this API key?\n\n"
                f"• Name: {name}\n"
                f"• Tier: {tier}\n"
                f"• Profile: {profile}\n\n"
                f"⚠️ WARNING: Any device using this key will lose access!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Load keys
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Error", "API keys file not found.")
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Delete key
            if key_id in api_keys:
                del api_keys[key_id]

                # Save
                with open(self.api_keys_file, 'w') as f:
                    json.dump(api_keys, f, indent=2)

                # Reload
                self._load_api_keys()

                show_info(self, "Deleted", f"API key '{name}' has been deleted.")

        except Exception as e:
            show_error(self, "Error", f"Failed to delete API key: {e}")

    def _regenerate_api_key(self, key_id: str, key_data: Dict):
        """Regenerate an API key and optionally send via email"""
        try:
            name = key_data.get('name', key_id)
            email = key_data.get('email', '')
            tier = key_data.get('tier', 'free').upper()

            # Ask for confirmation with email option
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Regenerate API Key")
            msg_box.setText(
                f"Are you sure you want to regenerate the API key?\n\n"
                f"Name: {name}\n"
                f"Email: {email or 'No email'}\n"
                f"Tier: {tier}\n\n"
                f"The old key will be invalidated immediately."
            )
            msg_box.setIcon(QMessageBox.Warning)

            # Add custom buttons
            regen_email_btn = msg_box.addButton("Regenerate & Email", QMessageBox.AcceptRole)
            regen_only_btn = msg_box.addButton("Regenerate Only", QMessageBox.AcceptRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)

            msg_box.exec_()

            clicked = msg_box.clickedButton()
            if clicked == cancel_btn:
                return

            send_email = (clicked == regen_email_btn)

            # Try server API first
            try:
                from server_api_client import get_server_client
                client = get_server_client()
                response = client.regenerate_api_key(key_id, send_email=send_email)

                if response.success:
                    new_key = response.data.get('new_api_key', '')
                    email_sent = response.data.get('email_sent', False)

                    # Show the new key
                    msg = f"API key regenerated successfully!\n\nNew Key: {new_key}"
                    if email_sent:
                        msg += f"\n\nEmail sent to: {email}"
                    else:
                        msg += "\n\n(Email not sent)"

                    # Copy to clipboard
                    QApplication.clipboard().setText(new_key)
                    msg += "\n\n(New key copied to clipboard)"

                    show_info(self, "Regenerated", msg)
                    self._load_api_keys()
                    return

            except Exception as api_error:
                logger.warning(f"Server API not available: {api_error}, falling back to local")

            # Fallback to local file method
            self._regenerate_api_key_local(key_id, key_data, send_email)

        except Exception as e:
            show_error(self, "Error", f"Failed to regenerate API key: {e}")

    def _regenerate_api_key_local(self, key_id: str, key_data: Dict, send_email: bool):
        """Regenerate API key using local file (fallback)"""
        import hashlib
        import secrets
        import string

        try:
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Error", "API keys file not found.")
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            if key_id not in api_keys:
                show_warning(self, "Error", f"API key {key_id} not found.")
                return

            # Generate new key
            chars = string.ascii_letters + string.digits
            new_api_key = ''.join(secrets.choice(chars) for _ in range(32))
            new_key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()

            # Update the key
            api_keys[key_id]['previous_key_hash'] = api_keys[key_id].get('key_hash')
            api_keys[key_id]['key_hash'] = new_key_hash
            api_keys[key_id]['regenerated_at'] = time.time()

            # Save
            with open(self.api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Try to send email if requested
            email_sent = False
            if send_email:
                email = key_data.get('email', '')
                if email:
                    try:
                        from email_service import send_api_key_email
                        send_api_key_email(email, key_data.get('name', 'Customer'), new_api_key, '')
                        email_sent = True
                    except Exception as e:
                        logger.error(f"Failed to send email: {e}")

            # Show result
            msg = f"API key regenerated successfully!\n\nNew Key: {new_api_key}"
            if email_sent:
                msg += f"\n\nEmail sent to: {key_data.get('email', '')}"
            elif send_email:
                msg += "\n\n(Email failed to send)"

            QApplication.clipboard().setText(new_api_key)
            msg += "\n\n(New key copied to clipboard)"

            show_info(self, "Regenerated", msg)

            # Sync to server
            try:
                from api_key_sync import sync_single_key_to_server
                sync_single_key_to_server(key_id)
            except:
                pass

            self._load_api_keys()

        except Exception as e:
            show_error(self, "Error", f"Failed to regenerate API key locally: {e}")

    def _send_api_key_email(self, key_id: str, key_data: Dict):
        """Send API key to customer via email"""
        try:
            name = key_data.get('name', key_id)
            email = key_data.get('email', '')

            if not email:
                # Ask for email address
                email, ok = QInputDialog.getText(
                    self, "Email Address",
                    f"Enter email address for {name}:",
                    QLineEdit.Normal, ""
                )
                if not ok or not email:
                    return

                # Update the key with the email
                try:
                    from server_api_client import get_server_client
                    client = get_server_client()
                    client.update_api_key(key_id, email=email)
                except:
                    # Update locally
                    if os.path.exists(self.api_keys_file):
                        with open(self.api_keys_file, 'r') as f:
                            api_keys = json.load(f)
                        if key_id in api_keys:
                            api_keys[key_id]['email'] = email
                            with open(self.api_keys_file, 'w') as f:
                                json.dump(api_keys, f, indent=2)

            # Since we only store hashes, we need to regenerate to send
            reply = QMessageBox.question(
                self, "Send API Key",
                f"To send the API key to {email}, we need to regenerate it.\n\n"
                f"The current key will be invalidated and a new one generated.\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self._regenerate_api_key(key_id, {**key_data, 'email': email})

        except Exception as e:
            show_error(self, "Error", f"Failed to send API key email: {e}")

    def _export_keys(self):
        """Export API keys list (without actual keys)"""
        try:
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Not Found", "No API keys to export.")
                return

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export API Keys List",
                f"api_keys_list_{datetime.now().strftime('%Y%m%d')}.txt",
                "Text Files (*.txt)"
            )

            if not filename:
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            with open(filename, 'w') as f:
                f.write("╔════════════════════════════════════════════════════════════╗\n")
                f.write("║           PREDICT OBD - API KEYS LIST                         ║\n")
                f.write("╚════════════════════════════════════════════════════════════╝\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 64 + "\n\n")

                for key_id, key_data in api_keys.items():
                    f.write(f"Name:     {key_data.get('name', key_id)}\n")
                    f.write(f"Tier:     {key_data.get('tier', 'unknown').upper()}\n")
                    f.write(f"Profile:  {key_data.get('profile_name', 'N/A')}\n")
                    f.write(f"Created:  {key_data.get('created', 'Unknown')}\n")
                    f.write(f"Status:   {key_data.get('status', 'active')}\n")
                    f.write(f"ID:       {key_id}\n")
                    f.write("-" * 64 + "\n\n")

                f.write("\nNote: Actual API keys are NOT included for security reasons.\n")
                f.write("Keys are encrypted and can only be revealed from the Server tab.\n")

            show_info(self, "Exported", f"API keys list exported to:\n{filename}")

        except Exception as e:
            show_error(self, "Error", f"Failed to export keys: {e}")

    # =============================================================================
    # SERVER CONTROL
    # =============================================================================

    def _toggle_server(self):
        """Toggle mobile server on/off"""
        if not self.mobile_wrapper:
            show_warning(self, "Not Available", "Mobile server not initialized")
            return

        if hasattr(self.mobile_wrapper, 'is_running') and self.mobile_wrapper.is_running:
            success = self.mobile_wrapper.stop_server()
            if success:
                self.server_btn.setText("▶️ Start Server")
                self.server_status_label.setText("Server: Stopped")
                self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 16px;")
        else:
            success = self.mobile_wrapper.start_server()
            if success:
                self.server_btn.setText("⏹️ Stop Server")
                self.server_status_label.setText("Server: Running ✓")
                self.server_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 16px;")

    # =============================================================================
    # STATS UPDATES
    # =============================================================================

    def _update_stats(self):
        """Update all statistics"""
        self._update_server_status()

        if self._stats_worker and self._stats_worker.isRunning():
            return

        if self.mobile_wrapper and hasattr(self.mobile_wrapper, 'server'):
            server = self.mobile_wrapper.server
            if server:
                self._stats_worker = StatsUpdateWorker(server)
                self._stats_worker.stats_ready.connect(self._on_stats_ready)
                self._stats_worker.network_ready.connect(self._on_network_ready)
                self._stats_worker.sessions_ready.connect(self._on_sessions_ready)
                self._stats_worker.start()

    def _update_server_status(self):
        """Update server status display"""
        if not self.mobile_wrapper:
            return

        if hasattr(self.mobile_wrapper, 'is_running') and self.mobile_wrapper.is_running:
            self.server_status_label.setText("Server: Running ✓")
            self.server_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 16px;")
            self.server_btn.setText("⏹️ Stop Server")
        else:
            self.server_status_label.setText("Server: Stopped")
            self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 16px;")
            self.server_btn.setText("▶️ Start Server")

    @Slot(list)
    def _on_sessions_ready(self, sessions):
        """Handle active sessions update"""
        count = len(sessions)
        self.connection_label.setText(f"Connections: {count}")
        if count > 0:
            self.connection_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold;")
        else:
            self.connection_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")

    @Slot(dict)
    def _on_stats_ready(self, stats):
        """Handle stats data"""
        try:
            if 'error' not in stats:
                # Update stat boxes
                for box, value in [
                    (self.stat_records, stats.get('total_records', 0)),
                    (self.stat_vehicles, stats.get('unique_vehicles', 0)),
                    (self.stat_requests, 0),  # Not available yet
                ]:
                    for child in box.findChildren(QLabel):
                        if child.text().isdigit() or child.text() == '0m':
                            child.setText(str(value))

                # Update database info
                if os.path.exists(self.database_path):
                    size_mb = os.path.getsize(self.database_path) / (1024 * 1024)
                    latest = stats.get('latest_record', 'Never')
                    self.db_info_label.setText(
                        f"Total Records: {stats.get('total_records', 0):,} | "
                        f"Vehicles: {stats.get('unique_vehicles', 0)} | "
                        f"Size: {size_mb:.2f} MB | "
                        f"Last Update: {latest}"
                    )
        except Exception:
            pass

    @Slot(dict)
    def _on_network_ready(self, info):
        """Handle network info"""
        try:
            network_info = info.get('network_info', {})

            text = "Network Interfaces:\n"
            text += "=" * 50 + "\n\n"

            for iface_name, iface_info in network_info.items():
                text += f"Interface: {iface_name}\n"
                text += f"  IPv4: {iface_info.get('ipv4', 'N/A')}\n"
                text += f"  IPv6: {iface_info.get('ipv6', 'N/A')}\n"
                text += "\n"

            self.network_info.setPlainText(text)
        except Exception:
            pass

    # =============================================================================
    # DATABASE ACTIONS
    # =============================================================================

    def _open_db_folder(self):
        """Open database folder"""
        try:
            import subprocess
            folder = os.path.dirname(self.database_path)
            if os.name == 'nt':
                os.startfile(folder)
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            show_error(self, "Error", f"Failed to open folder: {e}")

    def _backup_database(self):
        """Backup database"""
        try:
            if not os.path.exists(self.database_path):
                show_warning(self, "Not Found", "Database file not found")
                return

            filename, _ = QFileDialog.getSaveFileName(
                self, "Backup Database",
                f"predictai_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                "Database Files (*.db)"
            )

            if not filename:
                return

            import shutil
            shutil.copy2(self.database_path, filename)

            size_mb = os.path.getsize(filename) / (1024 * 1024)
            show_info(self, "Success", f"Database backed up to:\n{filename}\n\nSize: {size_mb:.2f} MB")

        except Exception as e:
            show_error(self, "Error", f"Backup failed: {e}")

    def _export_database_csv(self):
        """Export database to CSV"""
        show_info(self, "Export", "CSV export feature - Select profile to export")
        # Implementation would go here

    def _vacuum_database(self):
        """Vacuum database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.database_path)
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            conn.close()

            show_info(self, "Success", "Database optimized successfully")
            self._update_stats()

        except Exception as e:
            show_error(self, "Error", f"Optimization failed: {e}")

    # =============================================================================
    # PDF SERVER
    # =============================================================================

    def _copy_pdf_url(self):
        """Copy PDF URL to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.pdf_url_input.text())
        show_info(self, "Copied", "PDF API URL copied to clipboard")

    def _test_pdf_server(self):
        """Test PDF server connection"""
        import urllib.request
        try:
            response = urllib.request.urlopen("http://localhost:8001/health", timeout=3)
            if response.status == 200:
                self.pdf_status_label.setText("PDF Server: Running ✓")
                self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 16px;")
                show_info(self, "Success", "PDF Server is running and responding on port 8001")
            else:
                raise Exception(f"HTTP {response.status}")
        except Exception as e:
            self.pdf_status_label.setText("PDF Server: Not Responding")
            self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 16px;")
            show_warning(self, "Connection Failed", f"Could not connect to PDF server:\n{e}")

    # =============================================================================
    # CLOUDFLARE TUNNEL
    # =============================================================================

    def _start_tunnel(self):
        """Start Cloudflare tunnel"""
        print("[DEBUG] Start Tunnel button clicked")
        self.tunnel_start_btn.setEnabled(False)
        # Update status indicator
        self.tunnel_status_label.setText("STARTING...")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-weight: bold; font-size: 24px;")
        self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.WARNING}; font-size: 48px;")
        self.tunnel_detail_label.setText("Starting Cloudflare tunnel...")
        self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-size: 13px;")

        # Try to start the tunnel
        try:
            print(f"[DEBUG] Cloudflare path: {self.tunnel.cloudflared_path}")
            print(f"[DEBUG] Config path: {self.tunnel.config_path}")
            success = self.tunnel.start_tunnel()
            print(f"[DEBUG] Tunnel start result: {success}")
            if not success:
                self.tunnel_start_btn.setEnabled(True)
                self.tunnel_status_label.setText("FAILED")
                self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 24px;")
                self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 48px;")
                self.tunnel_detail_label.setText("Failed to start tunnel - Check cloudflared path")
                show_warning(self, "Tunnel Error", f"Failed to start Cloudflare tunnel.\n\nPlease check:\n1. cloudflared.exe exists\n2. config.yml is properly configured\n\nPath: {self.tunnel.cloudflared_path}")
        except Exception as e:
            print(f"[DEBUG] Tunnel exception: {e}")
            self.tunnel_start_btn.setEnabled(True)
            self.tunnel_status_label.setText("ERROR")
            self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 24px;")
            self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 48px;")
            self.tunnel_detail_label.setText(f"Error: {str(e)}")
            show_error(self, "Tunnel Error", f"Exception starting tunnel:\n{str(e)}")

    def _stop_tunnel(self):
        """Stop Cloudflare tunnel"""
        self.tunnel_stop_btn.setEnabled(False)
        # Update status indicator
        self.tunnel_status_label.setText("STOPPING...")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-weight: bold; font-size: 24px;")
        self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.WARNING}; font-size: 48px;")
        self.tunnel_detail_label.setText("Stopping Cloudflare tunnel...")

        self.tunnel.stop_tunnel()

    def _on_tunnel_status_changed(self, is_running: bool, message: str):
        """Handle tunnel status changes"""
        if is_running:
            # Update large indicator
            self.tunnel_status_label.setText("CONNECTED")
            self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 24px;")
            self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 48px;")
            self.tunnel_detail_label.setText("Tunnel active - Remote access enabled")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 13px;")
            # Update buttons
            self.tunnel_start_btn.setEnabled(False)
            self.tunnel_stop_btn.setEnabled(True)
            # Auto-test connections after 2 seconds
            QTimer.singleShot(2000, self._test_all_connections)
        else:
            # Update large indicator
            self.tunnel_status_label.setText("DISCONNECTED")
            self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 24px;")
            self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 48px;")
            self.tunnel_detail_label.setText("Tunnel not running - Click 'Start Tunnel' to connect")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 13px;")
            # Update buttons
            self.tunnel_start_btn.setEnabled(True)
            self.tunnel_stop_btn.setEnabled(False)
            # Reset service indicators
            self._reset_service_indicators()

    def _copy_main_tunnel_url(self):
        """Copy main tunnel URL"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.tunnel_main_url.text())
        show_info(self, "Copied", "Main API URL copied to clipboard")

    def _copy_pdf_tunnel_url(self):
        """Copy PDF tunnel URL"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.tunnel_pdf_url.text())
        show_info(self, "Copied", "PDF API URL copied to clipboard")

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    def _get_vehicle_profiles(self) -> List[Dict]:
        """Get all owners, vehicle profiles, and drivers from database for API key assignment"""
        import sqlite3
        from pathlib import Path

        entities = []

        # Use VehicleProfileManager (has correct path and all methods)
        try:
            from vehicle_module import VehicleProfileManager
            vm = VehicleProfileManager()

            # Get all OWNERS first
            try:
                all_owners = vm.get_all_owners()
                if all_owners:
                    for owner in all_owners:
                        entities.append({
                            'type': 'owner',
                            'id': owner.get('owner_id'),
                            'profile_id': None,  # Owners don't have profile_id
                            'owner_id': owner.get('owner_id'),
                            'driver_id': None,
                            'name': owner.get('name', 'Unknown Owner'),
                            'display_text': f"👤 [Owner] {owner.get('name', 'Unknown')}",
                            'vehicle_count': owner.get('vehicle_count', 0),
                            'driver_count': owner.get('driver_count', 0)
                        })
                    print(f"[API Keys] Loaded {len(all_owners)} owners")
            except Exception as e:
                print(f"[API Keys] Error loading owners: {e}")

            # Get all VEHICLES (profiles)
            try:
                all_profiles = vm.get_all_profiles()
                if all_profiles:
                    for p in all_profiles:
                        vehicle_name = p.get('name', 'Unknown')
                        make = p.get('make', '')
                        model = p.get('model', '')
                        year = p.get('year', 0)

                        # Create display text
                        if make or model:
                            display_text = f"🚗 [Vehicle] {vehicle_name} ({make} {model} {year})"
                        else:
                            display_text = f"🚗 [Vehicle] {vehicle_name}"

                        entities.append({
                            'type': 'vehicle',
                            'id': p.get('profile_id'),
                            'profile_id': p.get('profile_id'),
                            'owner_id': p.get('owner_id'),
                            'driver_id': None,
                            'name': vehicle_name,
                            'make': make,
                            'model': model,
                            'year': year,
                            'display_text': display_text
                        })
                    print(f"[API Keys] Loaded {len(all_profiles)} vehicles")
            except Exception as e:
                print(f"[API Keys] Error loading vehicles: {e}")

            # Get all DRIVERS (from all profiles)
            try:
                if all_profiles:
                    for p in all_profiles:
                        profile_id = p.get('profile_id')
                        vehicle_name = p.get('name', 'Unknown Vehicle')
                        drivers = vm.get_drivers_for_profile(profile_id)
                        if drivers:
                            for driver in drivers:
                                driver_name = driver.get('name', 'Unknown Driver')
                                relationship = driver.get('relationship', '')
                                is_primary = driver.get('is_primary', False)

                                # Create display text
                                suffix = " (Primary)" if is_primary else ""
                                display_text = f"🚘 [Driver] {driver_name} - {vehicle_name}{suffix}"

                                entities.append({
                                    'type': 'driver',
                                    'id': driver.get('driver_id'),
                                    'profile_id': profile_id,
                                    'owner_id': p.get('owner_id'),
                                    'driver_id': driver.get('driver_id'),
                                    'name': driver_name,
                                    'relationship': relationship,
                                    'is_primary': is_primary,
                                    'vehicle_name': vehicle_name,
                                    'display_text': display_text
                                })
                    driver_count = sum(1 for e in entities if e['type'] == 'driver')
                    print(f"[API Keys] Loaded {driver_count} drivers")
            except Exception as e:
                print(f"[API Keys] Error loading drivers: {e}")

            if entities:
                print(f"[API Keys] Total: {len(entities)} entities (owners, vehicles, drivers)")
                return entities

        except Exception as e:
            print(f"[API Keys] VehicleProfileManager failed: {e}")
            import traceback
            traceback.print_exc()

        # Fallback: Direct database access
        try:
            db_paths = []
            if CONFIG:
                db_paths.append(str(CONFIG.PROFILES_DB_PATH))
                db_paths.append(str(CONFIG.DATA_DIR / "vehicle_profiles.db"))

            script_dir = Path(__file__).parent
            db_paths.append(str(script_dir / "data" / "vehicle_profiles.db"))
            db_paths.append("./data/vehicle_profiles.db")
            db_paths.append("C:/D Drive/Predict/data/vehicle_profiles.db")

            # Remove duplicates
            seen = set()
            unique_paths = [p for p in db_paths if p and p not in seen and not seen.add(p)]

            for db_path in unique_paths:
                if not os.path.exists(db_path):
                    continue

                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()

                    # Load owners
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='owners'")
                    if cursor.fetchone():
                        cursor.execute("SELECT owner_id, name, email FROM owners WHERE is_active = 1 ORDER BY name")
                        for row in cursor.fetchall():
                            entities.append({
                                'type': 'owner',
                                'id': row[0],
                                'profile_id': None,
                                'owner_id': row[0],
                                'driver_id': None,
                                'name': row[1] or 'Unknown',
                                'display_text': f"👤 [Owner] {row[1] or 'Unknown'}"
                            })

                    # Load vehicles
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vehicle_profiles'")
                    if cursor.fetchone():
                        cursor.execute("SELECT profile_id, name, make, model, year, owner_id FROM vehicle_profiles ORDER BY name")
                        for row in cursor.fetchall():
                            name = row[1] or 'Unknown'
                            make = row[2] or ''
                            model = row[3] or ''
                            year = row[4] or 0
                            display_text = f"🚗 [Vehicle] {name}"
                            if make or model:
                                display_text = f"🚗 [Vehicle] {name} ({make} {model} {year})"
                            entities.append({
                                'type': 'vehicle',
                                'id': row[0],
                                'profile_id': row[0],
                                'owner_id': row[5],
                                'driver_id': None,
                                'name': name,
                                'make': make,
                                'model': model,
                                'year': year,
                                'display_text': display_text
                            })

                    # Load drivers
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drivers'")
                    if cursor.fetchone():
                        cursor.execute("""
                            SELECT d.driver_id, d.name, d.profile_id, d.is_primary, vp.name as vehicle_name
                            FROM drivers d
                            LEFT JOIN vehicle_profiles vp ON d.profile_id = vp.profile_id
                            WHERE d.is_active = 1
                            ORDER BY d.name
                        """)
                        for row in cursor.fetchall():
                            driver_name = row[1] or 'Unknown'
                            vehicle_name = row[4] or 'Unknown Vehicle'
                            is_primary = row[3]
                            suffix = " (Primary)" if is_primary else ""
                            entities.append({
                                'type': 'driver',
                                'id': row[0],
                                'profile_id': row[2],
                                'owner_id': None,
                                'driver_id': row[0],
                                'name': driver_name,
                                'is_primary': is_primary,
                                'display_text': f"🚘 [Driver] {driver_name} - {vehicle_name}{suffix}"
                            })

                    conn.close()
                    if entities:
                        print(f"[API Keys] Loaded {len(entities)} entities from {db_path}")
                        break
                except Exception as e:
                    print(f"[API Keys] Error reading {db_path}: {e}")

        except Exception as e:
            print(f"[API Keys] Fallback error: {e}")

        if not entities:
            print(f"[API Keys] WARNING: No entities found!")

        return entities

    # =============================================================================
    # NEW SERVER-BASED API KEY METHODS
    # =============================================================================

    def _load_api_keys_from_server(self):
        """Load API keys from server (source of truth)"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'api_table'):
            return
        
        try:
            from server_api_client import get_server_client

            client = get_server_client()
            response = client.list_api_keys()

            if not response.success:
                show_error(self, "Server Error", f"Failed to load API keys: {response.error}")
                return

            api_keys = response.data.get('api_keys', [])

            # Store data for filtering
            self.api_table_data = api_keys

            # Populate table
            self._populate_api_keys_table(api_keys)

            # Update tier counts
            tier_counts = {"free": 0, "premium": 0, "admin": 0}
            for key in api_keys:
                tier = key.get('tier', 'free').lower()
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            self._update_tier_counts(tier_counts)

        except Exception as e:
            import traceback
            traceback.print_exc()
            show_error(self, "Connection Error", f"Failed to connect to server: {str(e)}")

    def _populate_api_keys_table(self, api_keys: list):
        """Populate the API keys table with 12-column structure"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'api_table'):
            return
        
        # Block signals to prevent itemChanged from firing during population
        self.api_table.blockSignals(True)

        self.api_table.setRowCount(len(api_keys))

        for row, key_data in enumerate(api_keys):
            try:
                # Column 0: Checkbox
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                checkbox_layout.setAlignment(Qt.AlignCenter)

                checkbox = QCheckBox()
                checkbox.setStyleSheet(f"""
                    QCheckBox::indicator {{
                        width: 16px;
                        height: 16px;
                        background-color: {ServerTheme.CARD_BG};
                        border: 1px solid {ServerTheme.BORDER};
                        border-radius: 3px;
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {ServerTheme.PRIMARY};
                        border: 1px solid {ServerTheme.PRIMARY};
                    }}
                """)
                checkbox_layout.addWidget(checkbox)
                self.api_table.setCellWidget(row, 0, checkbox_widget)

                # Column 1: Name (editable)
                name = key_data.get('name', 'Unknown')
                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
                self.api_table.setItem(row, 1, name_item)

                # Column 2: Email (editable)
                email = key_data.get('email', '')
                email_item = QTableWidgetItem(email)
                email_item.setFlags(email_item.flags() | Qt.ItemIsEditable)
                self.api_table.setItem(row, 2, email_item)

                # Column 3: Phone (editable)
                phone = key_data.get('phone', '')
                phone_item = QTableWidgetItem(phone)
                phone_item.setFlags(phone_item.flags() | Qt.ItemIsEditable)
                self.api_table.setItem(row, 3, phone_item)

                # Column 4: Tier (dropdown)
                tier = key_data.get('tier', 'free')
                tier_widget = self._create_tier_dropdown(tier, key_data.get('key_id'))
                self.api_table.setCellWidget(row, 4, tier_widget)

                # Column 5: Role (dropdown)
                role = key_data.get('role', 'owner')
                role_widget = self._create_role_dropdown(role, key_data.get('key_id'))
                self.api_table.setCellWidget(row, 5, role_widget)

                # Column 6: Vehicle
                vehicle_info = key_data.get('vehicle_info', '-')
                vehicle_item = QTableWidgetItem(vehicle_info)
                self.api_table.setItem(row, 6, vehicle_item)

                # Column 7: Apps
                apps = key_data.get('apps', [])
                apps_text = ', '.join([a.upper() for a in apps]) if apps else '-'
                apps_item = QTableWidgetItem(apps_text)
                self.api_table.setItem(row, 7, apps_item)

                # Column 8: Status (dropdown)
                status = key_data.get('status', 'active')
                status_widget = self._create_status_dropdown(status, key_data.get('key_id'))
                self.api_table.setCellWidget(row, 8, status_widget)

                # Column 9: Source
                source = key_data.get('source', 'desktop')
                source_item = QTableWidgetItem(source.upper())
                source_color = '#4CAF50' if source == 'android' else '#2196F3'
                source_item.setForeground(QColor(source_color))
                self.api_table.setItem(row, 9, source_item)

                # Column 10: Created
                created = key_data.get('created_at', 'Unknown')
                if created != 'Unknown' and created:
                    try:
                        from datetime import datetime
                        if isinstance(created, (int, float)):
                            dt = datetime.fromtimestamp(created)
                        else:
                            dt = datetime.fromisoformat(str(created))
                        created = dt.strftime("%Y-%m-%d")
                    except:
                        pass
                created_item = QTableWidgetItem(str(created))
                self.api_table.setItem(row, 10, created_item)

                # Column 11: Actions
                actions_widget = self._create_actions_widget(key_data)
                self.api_table.setCellWidget(row, 11, actions_widget)

                # Store key_id as hidden data in row
                name_item.setData(Qt.UserRole, key_data.get('key_id'))

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error populating row {row}: {e}")

        # Unblock signals after population is complete
        self.api_table.blockSignals(False)

    def _create_tier_dropdown(self, current_tier: str, key_id: str):
        """Create tier dropdown widget"""
        combo = QComboBox()
        combo.addItems(["free", "premium", "admin"])
        # Block signals while setting initial value to prevent false sync
        combo.blockSignals(True)
        combo.setCurrentText(current_tier.lower())
        combo.blockSignals(False)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }}
            QComboBox:hover {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
        """)
        # Use default argument to capture key_id value
        combo.currentTextChanged.connect(
            lambda tier, k=key_id: self._sync_field_change(k, 'tier', tier)
        )
        return combo

    def _create_role_dropdown(self, current_role: str, key_id: str):
        """Create role dropdown widget"""
        combo = QComboBox()
        combo.addItems(["owner", "driver", "admin"])
        # Block signals while setting initial value to prevent false sync
        combo.blockSignals(True)
        combo.setCurrentText(current_role.lower())
        combo.blockSignals(False)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }}
            QComboBox:hover {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
        """)
        # Use default argument to capture key_id value
        combo.currentTextChanged.connect(
            lambda role, k=key_id: self._sync_field_change(k, 'role', role)
        )
        return combo

    def _create_status_dropdown(self, current_status: str, key_id: str):
        """Create status dropdown widget"""
        combo = QComboBox()
        combo.addItems(["active", "suspended", "revoked"])
        # Block signals while setting initial value to prevent false sync
        combo.blockSignals(True)
        combo.setCurrentText(current_status.lower())
        combo.blockSignals(False)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }}
            QComboBox:hover {{
                border: 1px solid {ServerTheme.PRIMARY};
            }}
        """)
        # Use default argument to capture key_id value
        combo.currentTextChanged.connect(
            lambda status, k=key_id: self._sync_field_change(k, 'status', status)
        )
        return combo

    def _create_actions_widget(self, key_data: dict):
        """Create actions buttons widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(3)

        # Email button
        email_btn = QPushButton("📧")
        email_btn.setFixedSize(24, 24)
        email_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ServerTheme.CARD_BG};
                color: #FFFFFF;
                border: 1px solid {ServerTheme.BORDER};
                padding: 0px;
                font-size: 12px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {ServerTheme.SUCCESS};
                border: 1px solid {ServerTheme.SUCCESS};
            }}
        """)
        email_btn.setToolTip("Send email notification")
        email_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(email_btn)

        # Delete button
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ServerTheme.CARD_BG};
                color: #FFFFFF;
                border: 1px solid {ServerTheme.BORDER};
                padding: 0px;
                font-size: 12px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {ServerTheme.DANGER};
                border: 1px solid {ServerTheme.DANGER};
            }}
        """)
        delete_btn.setToolTip("Delete API key")
        delete_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(delete_btn)

        return widget

    def _sync_field_change(self, key_id: str, field: str, value):
        """Sync field change to server with auto-email"""
        try:
            from server_api_client import get_server_client

            client = get_server_client()
            updates = {field: value}

            response = client.update_api_key(
                key_id,
                **updates,
                send_notification=True  # Auto-email on change
            )

            if response.success:
                print(f"✓ {field} updated and synced to server")
                # Optionally show a brief success message
            else:
                show_error(self, "Sync Failed", f"Failed to sync {field}: {response.error}")
                # Reload table to revert change
                self._load_api_keys_from_server()

        except Exception as e:
            show_error(self, "Connection Error", f"Failed to sync to server: {str(e)}")
            # Reload table to revert change
            self._load_api_keys_from_server()

    def _filter_api_keys(self, search_text=None):
        """Filter table rows based on search text and filter selections"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'api_table'):
            return
        
        if search_text is None:
            search_text = self.api_search_box.text()

        search_lower = search_text.lower()
        tier_filter = self.tier_filter_combo.currentText().lower()
        status_filter = self.status_filter_combo.currentText().lower()

        for row in range(self.api_table.rowCount()):
            # Get row data
            try:
                name = self.api_table.item(row, 1).text().lower() if self.api_table.item(row, 1) else ""
                email = self.api_table.item(row, 2).text().lower() if self.api_table.item(row, 2) else ""
                phone = self.api_table.item(row, 3).text().lower() if self.api_table.item(row, 3) else ""

                # Get tier from dropdown
                tier_widget = self.api_table.cellWidget(row, 4)
                tier = tier_widget.currentText().lower() if tier_widget else "free"

                # Get status from dropdown
                status_widget = self.api_table.cellWidget(row, 8)
                status = status_widget.currentText().lower() if status_widget else "active"

                # Check search match
                search_match = (
                    search_lower in name or
                    search_lower in email or
                    search_lower in phone
                )

                # Check tier filter
                tier_match = tier_filter == "all" or tier == tier_filter

                # Check status filter
                status_match = status_filter == "all" or status == status_filter

                # Show/hide row based on all filters
                should_show = search_match and tier_match and status_match
                self.api_table.setRowHidden(row, not should_show)

            except Exception as e:
                print(f"Error filtering row {row}: {e}")

    def _on_table_item_changed(self, item):
        """Handle inline editing of table cells (Name, Email, Phone)"""
        # Guard: API Keys tab may not be built
        if not hasattr(self, 'api_table'):
            return
        
        if item is None:
            return

        row = item.row()
        column = item.column()

        # Only handle editable columns (Name, Email, Phone)
        if column not in [1, 2, 3]:
            return

        # Get key_id from hidden data in name column
        name_item = self.api_table.item(row, 1)
        if not name_item:
            return

        key_id = name_item.data(Qt.UserRole)
        if not key_id:
            return

        # Map column to field name
        field_map = {
            1: "name",
            2: "email",
            3: "phone"
        }

        field = field_map.get(column)
        new_value = item.text()

        # Sync to server
        self._sync_field_change(key_id, field, new_value)

    def _refresh_all(self):
        """Refresh all data"""
        self._load_api_keys_from_server()  # Changed to use server-based loading
        self._update_stats()
        show_info(self, "Refreshed", "All data refreshed successfully")


# For backward compatibility
CloudSyncTab = ServerTab
