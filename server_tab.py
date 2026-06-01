"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Server Tab
"""

"""
Server Tab - Manages mobile server, API keys, and database

Features:
- Generate/manage API keys for Android app
- Mobile server controls (start/stop)
- View server statistics
- Database management
- Network information
"""

import os
import json
import secrets
import hashlib
from datetime import datetime

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
    QTextEdit, QScrollArea, QFrame, QApplication, QDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QFont
from ui_common import show_error, show_info, show_warning
from cloudflare_tunnel import CloudflareTunnel

# Theme colors
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


class StatsUpdateWorker(QThread):
    """Background worker for updating stats without blocking UI"""
    stats_ready = Signal(dict)  # database stats
    network_ready = Signal(dict)  # network info
    sessions_ready = Signal(list) # active sessions

    def __init__(self, server):
        super().__init__()
        self.server = server

    def run(self):
        """Fetch stats in background"""
        try:
            # Get database stats
            if hasattr(self.server, 'get_database_stats'):
                stats = self.server.get_database_stats()
                self.stats_ready.emit(stats)

            # Get network info (cached, fast)
            if hasattr(self.server, 'get_server_info'):
                info = self.server.get_server_info()
                if 'network_info' in info:
                    self.network_ready.emit(info)
            
            # Get active sessions
            if hasattr(self.server, 'get_active_sessions'):
                sessions = self.server.get_active_sessions()
                self.sessions_ready.emit(sessions)
        except Exception as e:
            # Silently fail - stats update is non-critical
            pass


class ServerTab(QWidget):
    """
    Server management tab for mobile server and API key management
    """

    def __init__(self, mobile_wrapper=None, parent=None):
        super().__init__(parent)
        self.mobile_wrapper = mobile_wrapper
        # API keys now saved in desktop app's config folder for better organization
        if CONFIG:
            self.api_keys_file = str(CONFIG.API_KEYS_FILE)
        else:
            self.api_keys_file = "config/api_keys.json"
        # Database path - for now still uses legacy location
        if CONFIG:
            self.database_path = str(CONFIG.SERVER_DB_PATH)
        else:
            self.database_path = "data/obd_data.db"

        # Update timer for stats
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)

        # Background worker for stats updates
        self._stats_worker = None

        # Cloudflare tunnel manager
        self.tunnel = CloudflareTunnel(self)
        self.tunnel.status_changed.connect(self._on_tunnel_status_changed)

        self._build_ui()
        self._load_api_keys()
        self._update_stats()

        # Update stats every 5 seconds
        self.stats_timer.start(5000)

    def _build_ui(self):
        """Build the server tab UI"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ServerTheme.BACKGROUND};
                color: {ServerTheme.TEXT_PRIMARY};
            }}
            QGroupBox {{
                color: {ServerTheme.PRIMARY};
                font-weight: bold;
                border: 1px solid {ServerTheme.BORDER};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
            }}
            QPushButton {{
                background-color: #C40000;
                color: #FFFFFF;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #E53935;
            }}
            QPushButton:pressed {{
                background-color: #A00000;
            }}
            QPushButton:disabled {{
                background-color: #30363D;
                color: #8B949E;
            }}
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {ServerTheme.CARD_BG};
                color: {ServerTheme.TEXT_PRIMARY};
                border: 1px solid {ServerTheme.BORDER};
                padding: 6px;
                border-radius: 4px;
            }}
            QTableWidget {{
                background-color: {ServerTheme.CARD_BG};
                border: 1px solid {ServerTheme.BORDER};
                gridline-color: {ServerTheme.BORDER};
            }}
            QTableWidget::item {{
                color: {ServerTheme.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {ServerTheme.BACKGROUND};
                color: {ServerTheme.PRIMARY};
                padding: 8px;
                border: 1px solid {ServerTheme.BORDER};
                font-weight: bold;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header
        header = self._build_header()
        main_layout.addLayout(header)

        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # Server status section
        server_group = self._build_server_section()
        content_layout.addWidget(server_group)

        # API Keys section
        api_group = self._build_api_keys_section()
        content_layout.addWidget(api_group)

        # Database section
        db_group = self._build_database_section()
        content_layout.addWidget(db_group)

        # Network info section
        network_group = self._build_network_section()
        content_layout.addWidget(network_group)

        # PDF API section (port 8001)
        pdf_group = self._build_pdf_section()
        content_layout.addWidget(pdf_group)

        # Cloudflare Tunnel section
        tunnel_group = self._build_tunnel_section()
        content_layout.addWidget(tunnel_group)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _build_header(self) -> QHBoxLayout:
        """Build header with title"""
        header = QHBoxLayout()

        title = QLabel("🖥️ Server Management")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color: {ServerTheme.TEXT_PRIMARY};")
        header.addWidget(title)

        header.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(refresh_btn)

        return header

    def _build_server_section(self) -> QGroupBox:
        """Build mobile server control section"""
        group = QGroupBox("📱 Mobile Server Status")
        layout = QVBoxLayout(group)

        # Status row
        status_row = QHBoxLayout()

        self.server_status_label = QLabel("Server: Stopped")
        self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 14px;")
        status_row.addWidget(self.server_status_label)

        status_row.addStretch()

        # Port info
        port_label = QLabel("Port: 8000 (Previlium)")
        port_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        status_row.addWidget(port_label)

        layout.addLayout(status_row)

        # Stats row
        stats_row = QHBoxLayout()

        self.connection_label = QLabel("Connections: 0")
        self.connection_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_row.addWidget(self.connection_label)

        self.data_count_label = QLabel("Data Points Today: 0")
        self.data_count_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_row.addWidget(self.data_count_label)

        stats_row.addStretch()

        layout.addLayout(stats_row)

        # Start/Stop button
        btn_row = QHBoxLayout()

        self.server_btn = QPushButton("Start Server")
        self.server_btn.setStyleSheet(self._get_button_style('primary'))
        self.server_btn.clicked.connect(self._toggle_server)
        btn_row.addWidget(self.server_btn)

        btn_row.addStretch()

        layout.addLayout(btn_row)

        return group

    def _build_api_keys_section(self) -> QGroupBox:
        """Build API keys management section"""
        group = QGroupBox("🔑 API Keys for Mobile App")
        layout = QVBoxLayout(group)

        # Info text
        info = QLabel("Generate API keys for Mobile OBD app (Android/iOS) authentication. Each key is linked to a vehicle profile for secure access.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(info)

        # API Keys table
        self.api_table = QTableWidget()
        self.api_table.setColumnCount(5)
        self.api_table.setHorizontalHeaderLabels(["Name", "Profile", "Key (Hidden)", "Created", "Actions"])
        self.api_table.horizontalHeader().setStretchLastSection(True)
        self.api_table.setMaximumHeight(200)
        self._apply_table_styling(self.api_table)
        layout.addWidget(self.api_table)

        # Buttons row
        btn_row = QHBoxLayout()

        generate_btn = QPushButton("➕ Generate New Key")
        generate_btn.setStyleSheet(self._get_button_style('success'))
        generate_btn.clicked.connect(self._generate_api_key)
        btn_row.addWidget(generate_btn)

        view_btn = QPushButton("👁️ View Keys File")
        view_btn.setStyleSheet(self._get_button_style('secondary'))
        view_btn.clicked.connect(self._view_keys_file)
        btn_row.addWidget(view_btn)

        export_btn = QPushButton("📤 Export Keys")
        export_btn.setStyleSheet(self._get_button_style('secondary'))
        export_btn.clicked.connect(self._export_keys)
        btn_row.addWidget(export_btn)

        btn_row.addStretch()

        layout.addLayout(btn_row)

        return group

    def _build_database_section(self) -> QGroupBox:
        """Build database management section"""
        group = QGroupBox("💾 Mobile Data Database")
        layout = QVBoxLayout(group)

        # Stats grid
        stats_grid = QHBoxLayout()

        self.db_records_label = QLabel("Total Records: -")
        self.db_records_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_grid.addWidget(self.db_records_label)

        self.db_vehicles_label = QLabel("Vehicles: -")
        self.db_vehicles_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_grid.addWidget(self.db_vehicles_label)

        self.db_size_label = QLabel("Size: -")
        self.db_size_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        stats_grid.addWidget(self.db_size_label)

        stats_grid.addStretch()

        layout.addLayout(stats_grid)

        # Last update
        self.db_last_update_label = QLabel("Last Update: -")
        self.db_last_update_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.db_last_update_label)

        # Database path
        path_row = QHBoxLayout()
        path_label = QLabel(f"📁 {self.database_path}")
        path_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 11px;")
        path_row.addWidget(path_label)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setStyleSheet(self._get_button_style('secondary'))
        open_folder_btn.clicked.connect(self._open_db_folder)
        open_folder_btn.setMaximumWidth(120)
        path_row.addWidget(open_folder_btn)

        layout.addLayout(path_row)

        # Action buttons
        btn_row = QHBoxLayout()

        query_btn = QPushButton("📊 Query Data")
        query_btn.setStyleSheet(self._get_button_style('info'))
        query_btn.clicked.connect(self._query_database)
        btn_row.addWidget(query_btn)

        export_csv_btn = QPushButton("📄 Export CSV")
        export_csv_btn.setStyleSheet(self._get_button_style('secondary'))
        export_csv_btn.clicked.connect(self._export_database_csv)
        btn_row.addWidget(export_csv_btn)

        backup_btn = QPushButton("💾 Backup Database")
        backup_btn.setStyleSheet(self._get_button_style('success'))
        backup_btn.clicked.connect(self._backup_database)
        btn_row.addWidget(backup_btn)

        btn_row.addStretch()

        layout.addLayout(btn_row)

        return group

    def _build_network_section(self) -> QGroupBox:
        """Build network information section"""
        group = QGroupBox("🌐 Network Information")
        layout = QVBoxLayout(group)

        # IP addresses
        self.network_info = QPlainTextEdit()
        self.network_info.setReadOnly(True)
        self.network_info.setMaximumHeight(120)
        self.network_info.setPlaceholderText("Network information will appear here...")
        layout.addWidget(self.network_info)

        # Instructions
        instructions = QLabel("📱 Mobile App Setup: Use one of the IP addresses above with port 8000")
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {ServerTheme.INFO}; font-weight: bold; margin-top: 5px;")
        layout.addWidget(instructions)

        return group

    def _build_pdf_section(self) -> QGroupBox:
        """Build PDF API server section (port 8001)"""
        group = QGroupBox("📄 PDF API Server (Port 8001)")
        layout = QVBoxLayout(group)

        # Status row
        status_row = QHBoxLayout()

        self.pdf_status_label = QLabel("PDF Server: Running ✓")
        self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 14px;")
        status_row.addWidget(self.pdf_status_label)

        status_row.addStretch()

        self.pdf_port_label = QLabel("Port: 8001")
        self.pdf_port_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        status_row.addWidget(self.pdf_port_label)

        layout.addLayout(status_row)

        # Info text
        info_text = QPlainTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setPlainText(
            "PDF API Server provides report generation for Android app.\n\n"
            "Endpoints:\n"
            "  GET  /report   - Generate and download PDF report\n"
            "  GET  /health   - Server health check\n\n"
            "Android app uses: http://<server-ip>:8001/report"
        )
        layout.addWidget(info_text)

        # URL display
        url_row = QHBoxLayout()
        url_label = QLabel("PDF API URL:")
        url_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        url_row.addWidget(url_label)

        self.pdf_url_input = QLineEdit()
        self.pdf_url_input.setReadOnly(True)
        self.pdf_url_input.setText("http://localhost:8001")
        url_row.addWidget(self.pdf_url_input)

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(self._copy_pdf_url)
        url_row.addWidget(copy_btn)

        layout.addLayout(url_row)

        # Test button
        test_btn = QPushButton("Test PDF Server Connection")
        test_btn.clicked.connect(self._test_pdf_server)
        layout.addWidget(test_btn)

        return group

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
                self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 14px;")
                show_info(self, "Success", "PDF Server is running and responding on port 8001")
            else:
                raise Exception(f"HTTP {response.status}")
        except Exception as e:
            self.pdf_status_label.setText("PDF Server: Not Responding")
            self.pdf_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 14px;")
            show_warning(self, "Connection Failed", f"Could not connect to PDF server on port 8001.\n\nError: {str(e)}")

    def _build_tunnel_section(self) -> QGroupBox:
        """Build Cloudflare Tunnel section"""
        group = QGroupBox("🌐 Cloudflare Tunnel - Remote Access")
        layout = QVBoxLayout(group)

        # Connection Status Card - Visual Indicator
        status_card = QFrame()
        status_card.setStyleSheet(f"""
            QFrame {{
                background-color: {ServerTheme.CARD_BG};
                border: 2px solid {ServerTheme.BORDER};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        status_card_layout = QVBoxLayout(status_card)

        # Main status indicator row
        main_status_row = QHBoxLayout()

        # Large status indicator dot
        self.tunnel_indicator = QLabel("●")
        self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 32px;")
        main_status_row.addWidget(self.tunnel_indicator)

        # Status text
        status_text_layout = QVBoxLayout()
        self.tunnel_status_label = QLabel("DISCONNECTED")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 18px;")
        status_text_layout.addWidget(self.tunnel_status_label)

        self.tunnel_detail_label = QLabel("Tunnel not running")
        self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
        status_text_layout.addWidget(self.tunnel_detail_label)

        main_status_row.addLayout(status_text_layout)
        main_status_row.addStretch()

        # Test connection button
        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.setMinimumWidth(140)
        self.test_conn_btn.setMinimumHeight(40)
        self.test_conn_btn.setCursor(Qt.PointingHandCursor)
        self.test_conn_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 6px;
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
        services_row = QHBoxLayout()
        services_row.setSpacing(20)

        # OBD Server status
        self.obd_service_indicator = QLabel("● OBD Server (8000)")
        self.obd_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
        services_row.addWidget(self.obd_service_indicator)

        # AI Server status
        self.ai_service_indicator = QLabel("● AI Server (12580)")
        self.ai_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
        services_row.addWidget(self.ai_service_indicator)

        # PDF Server status
        self.pdf_service_indicator = QLabel("● PDF Server (8001)")
        self.pdf_service_indicator.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
        services_row.addWidget(self.pdf_service_indicator)

        services_row.addStretch()
        status_card_layout.addLayout(services_row)

        layout.addWidget(status_card)

        # Main API URL
        main_url_row = QHBoxLayout()
        main_url_label = QLabel("Main API URL:")
        main_url_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        main_url_label.setFixedWidth(120)
        main_url_row.addWidget(main_url_label)

        self.tunnel_main_url = QLineEdit()
        self.tunnel_main_url.setReadOnly(True)
        self.tunnel_main_url.setText(self.tunnel.get_main_url())
        main_url_row.addWidget(self.tunnel_main_url)

        copy_main_btn = QPushButton("Copy")
        copy_main_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_main_btn.setFixedWidth(60)
        copy_main_btn.clicked.connect(self._copy_main_tunnel_url)
        main_url_row.addWidget(copy_main_btn)

        layout.addLayout(main_url_row)

        # PDF API URL
        pdf_url_row = QHBoxLayout()
        pdf_url_label = QLabel("PDF API URL:")
        pdf_url_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY};")
        pdf_url_label.setFixedWidth(120)
        pdf_url_row.addWidget(pdf_url_label)

        self.tunnel_pdf_url = QLineEdit()
        self.tunnel_pdf_url.setReadOnly(True)
        self.tunnel_pdf_url.setText(self.tunnel.get_pdf_url())
        pdf_url_row.addWidget(self.tunnel_pdf_url)

        copy_pdf_btn = QPushButton("Copy")
        copy_pdf_btn.setStyleSheet(self._get_button_style('secondary'))
        copy_pdf_btn.setFixedWidth(60)
        copy_pdf_btn.clicked.connect(self._copy_pdf_tunnel_url)
        pdf_url_row.addWidget(copy_pdf_btn)

        layout.addLayout(pdf_url_row)

        # Control buttons
        btn_row = QHBoxLayout()

        self.tunnel_start_btn = QPushButton("Start Tunnel")
        self.tunnel_start_btn.setStyleSheet(self._get_button_style('success'))
        self.tunnel_start_btn.clicked.connect(self._start_tunnel)
        btn_row.addWidget(self.tunnel_start_btn)

        self.tunnel_stop_btn = QPushButton("Stop Tunnel")
        self.tunnel_stop_btn.setStyleSheet(self._get_button_style('danger'))
        self.tunnel_stop_btn.clicked.connect(self._stop_tunnel)
        self.tunnel_stop_btn.setEnabled(False)
        btn_row.addWidget(self.tunnel_stop_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return group

    def _start_tunnel(self):
        """Start Cloudflare tunnel"""
        self.tunnel_start_btn.setEnabled(False)
        self.tunnel_status_label.setText("Tunnel: Starting...")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-weight: bold; font-size: 14px;")

        success = self.tunnel.start_tunnel()
        if not success:
            self.tunnel_start_btn.setEnabled(True)

    def _stop_tunnel(self):
        """Stop Cloudflare tunnel"""
        self.tunnel_stop_btn.setEnabled(False)
        self.tunnel_status_label.setText("Tunnel: Stopping...")
        self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-weight: bold; font-size: 14px;")

        self.tunnel.stop_tunnel()

    def _on_tunnel_status_changed(self, is_running: bool, message: str):
        """Handle tunnel status changes"""
        if is_running:
            self.tunnel_status_label.setText("CONNECTED")
            self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 18px;")
            self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 32px;")
            self.tunnel_detail_label.setText("Tunnel active - Remote access enabled")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 12px;")
            self.tunnel_start_btn.setEnabled(False)
            self.tunnel_stop_btn.setEnabled(True)
            # Auto-test connections when tunnel starts
            QTimer.singleShot(2000, self._test_all_connections)
        else:
            self.tunnel_status_label.setText("DISCONNECTED")
            self.tunnel_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 18px;")
            self.tunnel_indicator.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 32px;")
            self.tunnel_detail_label.setText("Tunnel not running")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;")
            self.tunnel_start_btn.setEnabled(True)
            self.tunnel_stop_btn.setEnabled(False)
            # Reset service indicators
            self._reset_service_indicators()

    def _reset_service_indicators(self):
        """Reset all service indicators to unknown state"""
        gray_style = f"color: {ServerTheme.TEXT_SECONDARY}; font-size: 12px;"
        self.obd_service_indicator.setStyleSheet(gray_style)
        self.ai_service_indicator.setStyleSheet(gray_style)
        self.pdf_service_indicator.setStyleSheet(gray_style)

    def _test_all_connections(self):
        """Test all service connections"""
        import threading

        self.test_conn_btn.setEnabled(False)
        self.test_conn_btn.setText("Testing...")
        self.tunnel_detail_label.setText("Testing connections...")

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
        green_style = f"color: {ServerTheme.SUCCESS}; font-size: 12px; font-weight: bold;"
        red_style = f"color: {ServerTheme.DANGER}; font-size: 12px; font-weight: bold;"

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
            self.tunnel_detail_label.setText("All services connected and accessible")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-size: 12px;")
        elif results['obd'] or results['ai']:
            self.tunnel_detail_label.setText("Some services running - check indicators below")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.WARNING}; font-size: 12px;")
        else:
            self.tunnel_detail_label.setText("Services offline - run start_server.bat")
            self.tunnel_detail_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-size: 12px;")

        # Re-enable test button
        self.test_conn_btn.setEnabled(True)
        self.test_conn_btn.setText("Test Connection")

    def _copy_main_tunnel_url(self):
        """Copy main tunnel URL to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.tunnel_main_url.text())
        show_info(self, "Copied", "Main API URL copied to clipboard")

    def _copy_pdf_tunnel_url(self):
        """Copy PDF tunnel URL to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.tunnel_pdf_url.text())
        show_info(self, "Copied", "PDF API URL copied to clipboard")

    # ========================================
    # Server Control
    # ========================================

    def _toggle_server(self):
        """Toggle mobile server on/off"""
        if not self.mobile_wrapper:
            show_warning(self, "Not Available", "Mobile server not initialized")
            return

        if hasattr(self.mobile_wrapper, 'is_running') and self.mobile_wrapper.is_running:
            # Stop server
            success = self.mobile_wrapper.stop_server()
            if success:
                self.server_btn.setText("Start Server")
                self.server_status_label.setText("Server: Stopped")
                self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 14px;")
        else:
            # Start server
            success = self.mobile_wrapper.start_server()
            if success:
                self.server_btn.setText("Stop Server")
                self.server_status_label.setText("Server: Running ✓")
                self.server_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 14px;")

    # ========================================
    # API Key Management
    # ========================================

    def _load_api_keys(self):
        """Load and display API keys"""
        try:
            if not os.path.exists(self.api_keys_file):
                self.api_table.setRowCount(0)
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            self.api_table.setRowCount(len(api_keys))

            for row, (key_name, key_data) in enumerate(api_keys.items()):
                # Name
                name_item = QTableWidgetItem(key_data.get('name', key_name))
                self.api_table.setItem(row, 0, name_item)

                # Profile
                profile_name = key_data.get('profile_name', 'N/A')
                if profile_name == 'N/A' and 'profile_id' in key_data:
                    # Try to get profile name from database
                    profiles = self._get_vehicle_profiles()
                    for p in profiles:
                        if p['profile_id'] == key_data['profile_id']:
                            profile_name = p['name']
                            break
                profile_item = QTableWidgetItem(profile_name)
                self.api_table.setItem(row, 1, profile_item)

                # Key (hidden)
                key_item = QTableWidgetItem("••••••••••••••••")
                self.api_table.setItem(row, 2, key_item)

                # Created date
                created = key_data.get('created', 'Unknown')
                if created != 'Unknown':
                    try:
                        dt = datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                date_item = QTableWidgetItem(created)
                self.api_table.setItem(row, 3, date_item)

                # Actions buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(5)

                # Copy button
                copy_btn = QPushButton("Copy")
                copy_btn.setStyleSheet(self._get_button_style('secondary'))
                copy_btn.setMaximumWidth(60)
                copy_btn.clicked.connect(lambda checked, n=key_name: self._copy_api_key(n))
                actions_layout.addWidget(copy_btn)

                # Delete button
                delete_btn = QPushButton("Delete")
                delete_btn.setStyleSheet(self._get_button_style('danger'))
                delete_btn.setMaximumWidth(60)
                delete_btn.clicked.connect(lambda checked, n=key_name, d=key_data: self._delete_api_key(n, d))
                actions_layout.addWidget(delete_btn)

                self.api_table.setCellWidget(row, 4, actions_widget)

        except Exception as e:
            show_error(self, "Error", f"Failed to load API keys: {e}")

    def _generate_api_key(self):
        """Generate a new API key linked to a vehicle profile"""
        try:
            # Get available profiles
            profiles = self._get_vehicle_profiles()

            if not profiles:
                show_warning(
                    self,
                    "No Profiles",
                    "No vehicle profiles found. Please create a vehicle profile first."
                )
                return

            # Create dialog to select profile and enter name
            dialog = QDialog(self)
            dialog.setWindowTitle("Generate API Key")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)

            # Profile selection
            layout.addWidget(QLabel("Select Vehicle Profile:"))
            profile_combo = QComboBox()
            for profile in profiles:
                profile_text = f"{profile['name']} ({profile['make']} {profile['model']} {profile['year']})"
                profile_combo.addItem(profile_text, profile['profile_id'])
            layout.addWidget(profile_combo)

            # Key name
            layout.addWidget(QLabel("\nEnter API Key Name:"))
            layout.addWidget(QLabel("(e.g., 'iPhone 14' or 'Pixel 7')"))
            name_input = QLineEdit()
            name_input.setPlaceholderText("API Key Name")
            layout.addWidget(name_input)

            # Buttons
            button_layout = QHBoxLayout()
            ok_btn = QPushButton("Generate")
            ok_btn.setStyleSheet(self._get_button_style('primary'))
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet(self._get_button_style('secondary'))
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            button_layout.addWidget(ok_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            if dialog.exec() != QDialog.Accepted:
                return

            name = name_input.text().strip()
            if not name:
                show_warning(self, "Invalid Input", "Please enter a name for the API key.")
                return

            profile_id = profile_combo.currentData()
            profile_name = profiles[profile_combo.currentIndex()]['name']

            # Generate new key (9 characters)
            new_key = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') for _ in range(9))
            key_hash = hashlib.sha256(new_key.encode()).hexdigest()

            # Load existing keys
            api_keys = {}
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r') as f:
                    api_keys = json.load(f)

            # Create unique key identifier
            key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Add new key with profile_id
            api_keys[key_id] = {
                "key_hash": key_hash,
                "name": name,
                "profile_id": profile_id,
                "profile_name": profile_name,
                "created": datetime.now().isoformat(),
                "permissions": ["vehicle_data", "predict", "diagnostic"]
            }

            # Save keys
            os.makedirs(os.path.dirname(self.api_keys_file), exist_ok=True)
            with open(self.api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Save backup text file in API_KEYS folder
            try:
                if CONFIG:
                    keys_folder = str(CONFIG.get_customer_api_keys_dir("default"))
                else:
                    keys_folder = str(CONFIG.get_customer_api_keys_dir("default")) if CONFIG else "api_keys"
                os.makedirs(keys_folder, exist_ok=True)
                
                # Sanitize filename
                safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
                key_filename = os.path.join(keys_folder, f"{safe_name}_apikey.txt")
                
                with open(key_filename, 'w') as f:
                    f.write("PREDICT CAR AI - API KEY CREDENTIALS\n")
                    f.write("====================================\n\n")
                    f.write(f"Name:    {name}\n")
                    f.write(f"Profile: {profile_name}\n")
                    f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("API KEY:\n")
                    f.write(f"{new_key}\n\n")
                    f.write("CONFIGURATION:\n")
                    f.write("Server IP: [Your Server IP]\n")
                    f.write("Port:      8000\n")
                
                save_msg = f"\n\nSaved to: {key_filename}"
            except Exception as e:
                save_msg = f"\n\nWarning: Could not save backup file: {e}"

            # Show key to user (only time they can see it!)
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("API Key Generated")
            msg.setText(f"New API key generated for:\n• Profile: {profile_name}\n• Key Name: {name}{save_msg}")
            msg.setInformativeText("⚠️ IMPORTANT: The key has been saved to the file above, but the database only stores a hash.")

            # Create text edit for key
            key_display = QTextEdit()
            key_display.setPlainText(new_key)
            key_display.setReadOnly(True)
            key_display.setMaximumHeight(80)
            key_display.selectAll()
            msg.layout().addWidget(key_display, 1, 1)

            copy_btn = msg.addButton("Copy to Clipboard", QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Ok)

            msg.exec()

            if msg.clickedButton() == copy_btn:
                QApplication.clipboard().setText(new_key)
                show_info(self, "Copied", "API key copied to clipboard!")

            # Reload table
            self._load_api_keys()

        except Exception as e:
            show_error(self, "Error", f"Failed to generate API key: {e}")

    def _copy_api_key(self, key_name: str):
        """Copy API key to clipboard (shows warning)"""
        show_warning(
            self,
            "Security Warning",
            f"The actual API key for '{key_name}' was only shown once during generation.\n\n"
            "If you lost the key, you need to:\n"
            "1. Delete this key\n"
            "2. Generate a new one\n"
            "3. Update your Android app configuration\n\n"
            "For security reasons, keys are stored as hashes and cannot be retrieved."
        )

    def _delete_api_key(self, key_name: str, key_data: dict):
        """Delete an API key"""
        try:
            # Get profile name for confirmation message
            profile_name = key_data.get('profile_name', 'Unknown')
            api_key_name = key_data.get('name', key_name)

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Delete API Key",
                f"Are you sure you want to delete this API key?\n\n"
                f"• Key Name: {api_key_name}\n"
                f"• Profile: {profile_name}\n\n"
                f"⚠️ WARNING: If this key is being used by a Mobile device, "
                f"that device will no longer be able to connect to the server.\n\n"
                f"This action cannot be undone!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Load existing keys
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Error", "API keys file not found.")
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Delete the key
            if key_name in api_keys:
                del api_keys[key_name]

                # Save updated keys
                with open(self.api_keys_file, 'w') as f:
                    json.dump(api_keys, f, indent=2)

                # Reload table
                self._load_api_keys()

                show_info(
                    self,
                    "Deleted",
                    f"API key '{api_key_name}' has been deleted successfully.\n\n"
                    f"If this key was in use, update your Mobile app configuration."
                )
            else:
                show_warning(self, "Error", f"API key '{key_name}' not found.")

        except Exception as e:
            show_error(self, "Error", f"Failed to delete API key: {e}")

    def _view_keys_file(self):
        """View the API keys file"""
        try:
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Not Found", "API keys file does not exist yet.")
                return

            with open(self.api_keys_file, 'r') as f:
                content = f.read()

            dialog = QMessageBox(self)
            dialog.setWindowTitle("API Keys File")
            dialog.setText("API Keys Configuration (keys are hashed for security):")

            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setReadOnly(True)
            text_edit.setMinimumWidth(600)
            text_edit.setMinimumHeight(400)
            dialog.layout().addWidget(text_edit, 1, 1)

            dialog.addButton(QMessageBox.Ok)
            dialog.exec()

        except Exception as e:
            show_error(self, "Error", f"Failed to view keys file: {e}")

    def _export_keys(self):
        """Export API keys list (without actual keys)"""
        try:
            if not os.path.exists(self.api_keys_file):
                show_warning(self, "Not Found", "No API keys to export.")
                return

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export API Keys List",
                f"api_keys_list_{datetime.now().strftime('%Y%m%d')}.txt",
                "Text Files (*.txt)"
            )

            if not filename:
                return

            with open(self.api_keys_file, 'r') as f:
                api_keys = json.load(f)

            with open(filename, 'w') as f:
                f.write("API Keys List - Predict Car AI\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                for key_name, key_data in api_keys.items():
                    f.write(f"Name: {key_data.get('name', key_name)}\n")
                    f.write(f"Created: {key_data.get('created', 'Unknown')}\n")
                    f.write(f"Permissions: {', '.join(key_data.get('permissions', []))}\n")
                    f.write(f"ID: {key_name}\n")
                    f.write("-" * 60 + "\n\n")

                f.write("\nNote: Actual keys are not included for security reasons.\n")
                f.write("Keys were only displayed once during generation.\n")

            show_info(self, "Exported", f"API keys list exported to:\n{filename}")

        except Exception as e:
            show_error(self, "Error", f"Failed to export keys: {e}")

    # ========================================
    # Database Management
    # ========================================

    def _get_vehicle_profiles(self):
        """Get all vehicle profiles from the database"""
        import sqlite3

        profiles = []
        try:
            db_path = str(CONFIG.DATA_DIR / "vehicle_profiles.db") if CONFIG else "data/vehicle_profiles.db"
            if not os.path.exists(db_path):
                return profiles

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT profile_id, name, make, model, year
                FROM vehicle_profiles
                ORDER BY name
            """)

            for row in cursor.fetchall():
                profiles.append({
                    'profile_id': row[0],
                    'name': row[1],
                    'make': row[2] or 'Unknown',
                    'model': row[3] or 'Unknown',
                    'year': row[4] or 0
                })

            conn.close()
        except Exception as e:
            print(f"Error loading profiles: {e}")

        return profiles

    def _update_stats(self):
        """Update all statistics (non-blocking)"""
        # Always update server status (fast, no HTTP)
        self._update_server_status()

        # Don't start new worker if one is already running
        if self._stats_worker and self._stats_worker.isRunning():
            return

        # Start background stats fetch
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
            self.server_status_label.setStyleSheet(f"color: {ServerTheme.SUCCESS}; font-weight: bold; font-size: 14px;")
            self.server_btn.setText("Stop Server")
        else:
            self.server_status_label.setText("Server: Stopped")
            self.server_status_label.setStyleSheet(f"color: {ServerTheme.DANGER}; font-weight: bold; font-size: 14px;")
            self.server_btn.setText("Start Server")

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
        """Handle stats data from background thread"""
        try:
            if 'error' not in stats:
                self.db_records_label.setText(f"Total Records: {stats.get('total_records', 0):,}")
                self.db_vehicles_label.setText(f"Vehicles: {stats.get('unique_vehicles', 0)}")

                # Database size
                if os.path.exists(self.database_path):
                    size_mb = os.path.getsize(self.database_path) / (1024 * 1024)
                    self.db_size_label.setText(f"Size: {size_mb:.2f} MB")

                # Last update
                latest = stats.get('latest_record', 'Never')
                if latest and latest != 'Never':
                    try:
                        dt = datetime.fromisoformat(latest.replace('Z', '+00:00'))
                        latest = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                self.db_last_update_label.setText(f"Last Update: {latest}")
        except Exception as e:
            pass  # Silently fail

    @Slot(dict)
    def _on_network_ready(self, info):
        """Handle network info from background thread"""
        try:
            network_info = info.get('network_info', {})

            text = "Network Interfaces:\n"
            text += "=" * 50 + "\n\n"

            for iface_name, iface_info in network_info.items():
                text += f"Interface: {iface_name}\n"
                text += f"  IPv4: {iface_info.get('ipv4', 'N/A')}\n"
                text += f"  IPv6: {iface_info.get('ipv6', 'N/A')}\n"
                text += f"  MAC: {iface_info.get('mac', 'N/A')}\n"
                text += "\n"

            text += f"\n📱 Mobile App Configuration:\n"
            text += f"   Server IP: <choose from above>\n"
            text += f"   Port: 8000 (Previlium Server)\n"
            text += f"   API Key: <generate above>\n"

            self.network_info.setPlainText(text)
        except Exception as e:
            pass  # Silently fail

    def _update_database_stats(self):
        """Update database statistics"""
        try:
            if not self.mobile_wrapper or not hasattr(self.mobile_wrapper, 'server'):
                return

            server = self.mobile_wrapper.server
            if not server:
                return

            stats = server.get_database_stats()

            if 'error' not in stats:
                self.db_records_label.setText(f"Total Records: {stats.get('total_records', 0):,}")
                self.db_vehicles_label.setText(f"Vehicles: {stats.get('unique_vehicles', 0)}")

                # Database size
                if os.path.exists(self.database_path):
                    size_mb = os.path.getsize(self.database_path) / (1024 * 1024)
                    self.db_size_label.setText(f"Size: {size_mb:.2f} MB")

                # Last update
                latest = stats.get('latest_record', 'Never')
                if latest and latest != 'Never':
                    try:
                        dt = datetime.fromisoformat(latest.replace('Z', '+00:00'))
                        latest = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                self.db_last_update_label.setText(f"Last Update: {latest}")

        except Exception as e:
            pass  # Silently fail on stats update

    def _update_network_info(self):
        """Update network information"""
        try:
            if not self.mobile_wrapper or not hasattr(self.mobile_wrapper, 'server'):
                return

            server = self.mobile_wrapper.server
            if not server:
                return

            info = server.get_server_info()
            network_info = info.get('network_info', {})

            text = "Network Interfaces:\n"
            text += "=" * 50 + "\n\n"

            for iface_name, iface_info in network_info.items():
                text += f"Interface: {iface_name}\n"
                text += f"  IPv4: {iface_info.get('ipv4', 'N/A')}\n"
                text += f"  IPv6: {iface_info.get('ipv6', 'N/A')}\n"
                text += f"  MAC: {iface_info.get('mac', 'N/A')}\n"
                text += "\n"

            text += f"\n📱 Mobile App Configuration:\n"
            text += f"   Server IP: <choose from above>\n"
            text += f"   Port: 8000 (Previlium Server)\n"
            text += f"   API Key: <generate above>\n"

            self.network_info.setPlainText(text)

        except Exception as e:
            self.network_info.setPlainText(f"Error loading network info: {e}")

    def _query_database(self):
        """Query database data"""
        try:
            if not self.mobile_wrapper or not hasattr(self.mobile_wrapper, 'server'):
                show_warning(self, "Not Available", "Mobile server not initialized")
                return

            server = self.mobile_wrapper.server

            # Ask for profile
            profile, ok = QInputDialog.getText(
                self,
                "Query Database",
                "Enter vehicle profile name (or leave empty for all):"
            )

            if not ok:
                return

            # Get data
            if profile:
                data = server.get_mobile_data_by_profile(profile, limit=100)
            else:
                # Get all recent data
                stats = server.get_database_stats()
                show_info(self, "Database Stats",
                         f"Total Records: {stats.get('total_records', 0)}\n"
                         f"Unique Vehicles: {stats.get('unique_vehicles', 0)}\n"
                         f"Latest Record: {stats.get('latest_record', 'N/A')}")
                return

            if data:
                show_info(self, "Query Result",
                         f"Found {len(data)} records for '{profile}'\n\n"
                         f"Latest record:\n"
                         f"  Time: {data[0].get('timestamp', 'N/A')}\n"
                         f"  RPM: {data[0].get('rpm', 'N/A')}\n"
                         f"  Speed: {data[0].get('speed', 'N/A')} km/h")
            else:
                show_info(self, "No Data", f"No data found for '{profile}'")

        except Exception as e:
            show_error(self, "Error", f"Query failed: {e}")

    def _export_database_csv(self):
        """Export database to CSV"""
        try:
            if not self.mobile_wrapper or not hasattr(self.mobile_wrapper, 'server'):
                show_warning(self, "Not Available", "Mobile server not initialized")
                return

            server = self.mobile_wrapper.server

            # Ask for profile
            profile, ok = QInputDialog.getText(
                self,
                "Export to CSV",
                "Enter vehicle profile name to export:"
            )

            if not ok or not profile:
                return

            # Get save location
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save CSV Export",
                f"mobile_data_{profile}_{datetime.now().strftime('%Y%m%d')}.csv",
                "CSV Files (*.csv)"
            )

            if not filename:
                return

            # Export
            success = server.export_mobile_data_to_csv(profile, filename)

            if success:
                show_info(self, "Success", f"Data exported to:\n{filename}")
            else:
                show_warning(self, "No Data", f"No data found for '{profile}'")

        except Exception as e:
            show_error(self, "Error", f"Export failed: {e}")

    def _backup_database(self):
        """Backup database file"""
        try:
            if not os.path.exists(self.database_path):
                show_warning(self, "Not Found", "Database file not found")
                return

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Backup Database",
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

    def _open_db_folder(self):
        """Open database folder in file explorer"""
        try:
            import subprocess
            folder = os.path.dirname(self.database_path)
            if os.name == 'nt':  # Windows
                os.startfile(folder)
            else:  # Linux/Mac
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            show_error(self, "Error", f"Failed to open folder: {e}")

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
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
        return styles.get(style_type, styles['primary'])
    
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
    
    def _refresh_all(self):
        """Refresh all data"""
        self._load_api_keys()
        self._update_stats()
        show_info(self, "Refreshed", "All data refreshed successfully")
    

# For backward compatibility
CloudSyncTab = ServerTab
