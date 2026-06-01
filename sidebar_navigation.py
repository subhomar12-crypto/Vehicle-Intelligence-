"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Sidebar Navigation

Sidebar Navigation - Simple clean sidebar for Predict OBD
Version: 4.0 - Simple Edition
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor

logger = logging.getLogger(__name__)


class NavItem(QPushButton):
    """Simple navigation item"""

    def __init__(self, icon: str, text: str, item_id: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.is_active = False

        self.setFixedHeight(40)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setText(f"  {icon}    {text}")
        self.setFont(QFont("Segoe UI", 10))

        self._update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()

    def _update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #21262D;
                    color: #FFFFFF;
                    border: none;
                    border-left: 3px solid #C40000;
                    text-align: left;
                    padding-left: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #8B949E;
                    border: none;
                    text-align: left;
                    padding-left: 15px;
                }
                QPushButton:hover {
                    background-color: #1C2128;
                    color: #C9D1D9;
                }
            """)


class NavHeader(QLabel):
    """Simple section header"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.setStyleSheet("""
            color: #6E7681;
            padding: 16px 15px 6px 15px;
        """)


class SidebarNavigation(QFrame):
    """Simple sidebar navigation"""

    navigation_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("SidebarNavigation: Initializing")
        self.items = {}
        self.current_page = "dashboard"
        self._setup_ui()
        logger.info("SidebarNavigation: UI setup complete")

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border-right: 1px solid #30363D;
            }
        """)
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #0D1117; border-bottom: 1px solid #30363D;")
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)

        logo = QLabel("PREDICT")
        logo.setFont(QFont("Segoe UI", 14, QFont.Bold))
        logo.setStyleSheet("color: #C40000;")
        header_layout.addWidget(logo)
        header_layout.addStretch()

        layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; background: #161B22; }
            QScrollBar::handle:vertical { background: #30363D; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 0, 8)
        content_layout.setSpacing(0)

        # Navigation items - Streamlined to 12 tabs
        # MAIN (2)
        content_layout.addWidget(NavHeader("MAIN"))
        self._add_item(content_layout, "🏠", "Dashboard", "dashboard")
        self._add_item(content_layout, "👤", "Profiles", "profiles")

        # MONITORING (3)
        content_layout.addWidget(NavHeader("MONITORING"))
        self._add_item(content_layout, "📊", "Live Data", "live_data")
        self._add_item(content_layout, "🔍", "DTC Codes", "dtc")
        self._add_item(content_layout, "📈", "Historical", "historical")

        # BUSINESS (2)
        content_layout.addWidget(NavHeader("BUSINESS"))
        self._add_item(content_layout, "📄", "Reports", "reports")
        self._add_item(content_layout, "🖥️", "Server", "server")

        # AI (1)
        content_layout.addWidget(NavHeader("AI"))
        self._add_item(content_layout, "🤖", "AI Chat", "ai_chat")

        # ADMIN (4) - for admin users
        content_layout.addWidget(NavHeader("ADMIN"))
        self._add_item(content_layout, "📊", "Admin Dashboard", "admin_dashboard")
        self._add_item(content_layout, "💳", "Subscriptions", "subscriptions")
        self._add_item(content_layout, "🎫", "Tier Management", "tier_management")
        self._add_item(content_layout, "👑", "Users", "users")
        self._add_item(content_layout, "🔧", "PID Atlas", "pid_atlas")

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Set default active
        self.set_active_page("dashboard")

    def _add_item(self, layout, icon: str, text: str, item_id: str):
        item = NavItem(icon, text, item_id)
        item.clicked.connect(lambda: self._on_click(item_id))
        self.items[item_id] = item
        layout.addWidget(item)

    def _on_click(self, item_id: str):
        logger.info(f"Navigation: Switching to {item_id}")
        self.set_active_page(item_id)
        self.navigation_changed.emit(item_id)

    def set_active_page(self, page_id: str):
        self.current_page = page_id
        for item_id, item in self.items.items():
            item.set_active(item_id == page_id)

    def get_current_page(self) -> str:
        return self.current_page
