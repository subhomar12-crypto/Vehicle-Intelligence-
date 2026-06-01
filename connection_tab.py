"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Connection Tab
"""

import obd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QLineEdit, QTextEdit, QCheckBox,
    QComboBox, QApplication, QMessageBox, QFrame, QScrollArea, QSpinBox
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import QTimer, Qt, QThread, Signal

from connectivity_module import UniversalConnectivityManager, ConnectionType, ConnectionState, ConnectionStrategy

# Import config for path management
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

# Import theme
try:
    from ui_common import PredictTheme
except ImportError:
    PredictTheme = None


# ================================
# THEME FALLBACK
# ================================

class DefaultTheme:
    """Default theme colors if PredictTheme not available"""
    PRIMARY = "#C40000"
    PRIMARY_DARK = "#A00000"
    SECONDARY = "#1A1A1A"
    SUCCESS = "#4CAF50"
    WARNING = "#FF9800"
    DANGER = "#F44336"
    INFO = "#2196F3"
    BORDER = "#30363D"
    BACKGROUND = "#0D1117"
    CARD_BG = "#21262D"
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"


Theme = PredictTheme if PredictTheme else DefaultTheme


def get_groupbox_style():
    """Get consistent GroupBox styling"""
    return f"""
        QGroupBox {{
            font-weight: bold;
            font-size: 13px;
            color: {Theme.PRIMARY};
            border: 1px solid {Theme.BORDER};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
            background-color: {Theme.CARD_BG};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            background-color: {Theme.CARD_BG};
        }}
    """


def get_combobox_style():
    """Get consistent ComboBox styling"""
    return f"""
        QComboBox {{
            background-color: {Theme.CARD_BG};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 8px 12px;
            min-width: 120px;
            font-size: 13px;
        }}
        QComboBox:hover {{
            border-color: {Theme.INFO};
        }}
        QComboBox:focus {{
            border-color: {Theme.PRIMARY};
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {Theme.TEXT_SECONDARY};
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Theme.CARD_BG};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER};
            selection-background-color: {Theme.PRIMARY};
            outline: none;
        }}
    """


def get_checkbox_style():
    """Get consistent CheckBox styling"""
    return f"""
        QCheckBox {{
            color: {Theme.TEXT_PRIMARY};
            spacing: 8px;
            font-size: 13px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {Theme.BORDER};
            border-radius: 4px;
            background-color: {Theme.CARD_BG};
        }}
        QCheckBox::indicator:hover {{
            border-color: {Theme.INFO};
        }}
        QCheckBox::indicator:checked {{
            background-color: {Theme.PRIMARY};
            border-color: {Theme.PRIMARY};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: #E53935;
        }}
    """


def get_label_style():
    """Get consistent label styling"""
    return f"color: {Theme.TEXT_PRIMARY}; font-size: 13px;"


# ================================
# HELPER FUNCTIONS
# ================================

def show_error(parent, title, message):
    """Show error message box"""
    QMessageBox.critical(parent, title, message)


def show_warning(parent, title, message):
    """Show warning message box"""
    QMessageBox.warning(parent, title, message)


def show_info(parent, title, message):
    """Show info message box"""
    QMessageBox.information(parent, title, message)


# ================================
# STATUS LED WIDGET
# ================================

class StatusLED(QFrame):
    """Visual status LED indicator"""

    def __init__(self, size: int = 12, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = Theme.DANGER
        self._update_style()

    def set_color(self, color: str):
        """Set LED color"""
        self._color = color
        self._update_style()

    def set_status(self, status: str):
        """Set status by name: 'success', 'warning', 'danger', 'info'"""
        colors = {
            'success': Theme.SUCCESS,
            'warning': Theme.WARNING,
            'danger': Theme.DANGER,
            'info': Theme.INFO,
            'connected': Theme.SUCCESS,
            'connecting': Theme.WARNING,
            'disconnected': Theme.DANGER,
        }
        self._color = colors.get(status.lower(), Theme.DANGER)
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self._color};
                border-radius: 6px;
                border: 1px solid {Theme.BORDER};
            }}
        """)


# ================================
# SERVER CONNECTION POLLER
# ================================

class ServerConnectionPoller(QThread):
    """Background thread to test server connection (Desktop - No API Key Required)"""
    test_result = Signal(bool, str)  # success, message

    def __init__(self, server_url: str):
        super().__init__()
        self.server_url = server_url

    def run(self):
        """Test connection to server using /api/health endpoint (no API key needed)"""
        import requests
        try:
            # Use /api/health endpoint which doesn't require API key for desktop connections
            response = requests.get(
                f"{self.server_url}/api/health",
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    self.test_result.emit(True, f"✅ Connected to {self.server_url}")
                else:
                    self.test_result.emit(False, f"❌ Server unhealthy: {result.get('status', 'unknown')}")
            else:
                self.test_result.emit(False, f"❌ Server returned status {response.status_code}")
        except requests.exceptions.Timeout:
            self.test_result.emit(False, f"⏱️ Timeout connecting to {self.server_url}")
        except requests.exceptions.ConnectionError:
            self.test_result.emit(False, f"❌ Cannot reach {self.server_url}")
        except Exception as e:
            self.test_result.emit(False, f"❌ Error: {str(e)}")


# ================================
# CONNECTION TAB
# ================================

class ConnectionTab(QWidget):
    """
    COM Port Connection Management Tab

    Features:
    - OBD-II Connection (COM Port)
    - Mobile OBD Server (Local)
    - Online Server Connection (Manual)
    - Cloud Sync Status
    """

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
                    border-radius: 8px;
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
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
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
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
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
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FF9800;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #FB8C00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def __init__(self, connectivity: UniversalConnectivityManager,
                 get_active_profile=None, parent=None):
        super().__init__(parent)
        self.conn = connectivity
        self.get_active_profile = get_active_profile

        # Online server state
        self.online_server_connected = False
        self.online_server_url = "https://predict.previlium.com"
        self.connection_poller = None

        # Build UI
        self._build_ui()

        # Initialize port list
        self._initialize_port_combo()

        # Start status update timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_all_status)
        self.status_timer.start(1000)

        # Connect to connectivity signals
        if hasattr(self.conn, 'status_changed'):
            self.conn.status_changed.connect(self._on_status_changed)
        if hasattr(self.conn, 'error_occurred'):
            self.conn.error_occurred.connect(self._on_error)
        if hasattr(self.conn, 'connection_lost'):
            self.conn.connection_lost.connect(self._on_connection_lost)
        if hasattr(self.conn, 'connection_strategy_changed'):
            self.conn.connection_strategy_changed.connect(self._on_strategy_changed)

    def _build_ui(self):
        """Build the user interface with scrollable content"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #0D1117; }")

        # Content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # ==================== HEADER ====================
        title = QLabel("🔌 Connection Management")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        subtitle = QLabel("Manage OBD connections, mobile server, and online server access")
        subtitle.setStyleSheet("color: #8B949E; font-size: 13px;")
        layout.addWidget(subtitle)

        # Divider
        self._add_divider(layout)

        # ==================== SECTIONS ====================

        # 1. Vehicle Profile Status
        profile_group = self._create_profile_status_group()
        layout.addWidget(profile_group)

        # 2. OBD-II Connection (COM Port)
        obd_group = self._create_obd_connection_group()
        layout.addWidget(obd_group)

        # 3. Mobile OBD Server (Local)
        mobile_group = self._create_mobile_server_group()
        layout.addWidget(mobile_group)

        # 4. Online Server Connection (NEW - Manual Control)
        online_group = self._create_online_server_group()
        layout.addWidget(online_group)

        # 5. Connection Log
        log_group = self._create_log_group()
        layout.addWidget(log_group)

        layout.addStretch()

        # Set scroll content
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _add_divider(self, layout: QVBoxLayout):
        """Add a visual divider line"""
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #30363D;")
        layout.addWidget(divider)

    def _create_profile_status_group(self) -> QGroupBox:
        """Create vehicle profile status section"""
        group = QGroupBox("Vehicle Profile")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Status row
        status_row = QHBoxLayout()
        self.profile_led = StatusLED()
        self.profile_led.set_status('danger')

        self.profile_status_label = QLabel("⚠️ No vehicle profile selected")
        self.profile_status_label.setStyleSheet(f"color: {Theme.WARNING}; font-weight: bold; font-size: 14px;")

        status_row.addWidget(self.profile_led)
        status_row.addWidget(self.profile_status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        # Info text
        self.profile_info_label = QLabel("Select a vehicle profile from the Profiles tab to enable connections.")
        self.profile_info_label.setWordWrap(True)
        self.profile_info_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self.profile_info_label)

        return group

    def _create_obd_connection_group(self) -> QGroupBox:
        """Create OBD-II connection section"""
        group = QGroupBox("OBD-II Adapter Connection")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Info note
        info_note = QLabel(
            "💡 Connect your OBD-II adapter via Bluetooth in Windows Settings first. "
            "Windows will create a virtual COM port (e.g., COM6)."
        )
        info_note.setWordWrap(True)
        info_note.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
            padding: 10px;
            background-color: rgba(33, 150, 243, 0.1);
            border-radius: 6px;
        """)
        layout.addWidget(info_note)

        # Port selection row
        port_row = QHBoxLayout()
        port_label = QLabel("COM Port:")
        port_label.setStyleSheet(get_label_style())
        port_label.setFixedWidth(90)
        port_row.addWidget(port_label)

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(150)
        self.port_combo.setStyleSheet(get_combobox_style())
        port_row.addWidget(self.port_combo)

        self.btn_refresh_ports = QPushButton("🔄")
        self.btn_refresh_ports.clicked.connect(self._refresh_port_list)
        self.btn_refresh_ports.setStyleSheet(self._get_button_style('secondary'))
        self.btn_refresh_ports.setFixedWidth(40)
        port_row.addWidget(self.btn_refresh_ports)
        port_row.addStretch()

        layout.addLayout(port_row)

        # Connection buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_connect = QPushButton("🔌 Connect OBD")
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_connect.setStyleSheet(self._get_button_style('primary'))
        self.btn_connect.setFixedWidth(160)

        self.btn_disconnect = QPushButton("⏹️ Disconnect")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.setStyleSheet(self._get_button_style('secondary'))
        self.btn_disconnect.setFixedWidth(140)

        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        return group

    def _create_mobile_server_group(self) -> QGroupBox:
        """Create mobile server section"""
        group = QGroupBox("Mobile OBD Server (Local)")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Status row
        status_row = QHBoxLayout()
        self.mobile_led = StatusLED()
        self.mobile_led.set_status('danger')

        self.mobile_status_label = QLabel("Server: Stopped")
        self.mobile_status_label.setStyleSheet(f"color: {Theme.DANGER}; font-weight: bold; font-size: 14px;")

        status_row.addWidget(self.mobile_led)
        status_row.addWidget(self.mobile_status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        # Info
        info = QLabel("Port 8000 • Connect Android OBD app to this PC")
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)

        # Start/Stop button
        self.mobile_server_btn = QPushButton("▶️ Start Mobile Server")
        self.mobile_server_btn.clicked.connect(self._toggle_mobile_server)
        self.mobile_server_btn.setStyleSheet(self._get_button_style('success'))
        layout.addWidget(self.mobile_server_btn)

        return group

    def _create_online_server_group(self) -> QGroupBox:
        """Create online server connection section (NEW)"""
        group = QGroupBox("Online Server Connection")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Status row
        status_row = QHBoxLayout()
        self.online_led = StatusLED()
        self.online_led.set_status('danger')

        self.online_status_label = QLabel("Disconnected")
        self.online_status_label.setStyleSheet(f"color: {Theme.DANGER}; font-weight: bold; font-size: 14px;")

        status_row.addWidget(self.online_led)
        status_row.addWidget(self.online_status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        # Server URL display
        url_row = QHBoxLayout()
        url_label = QLabel("Server:")
        url_label.setStyleSheet(get_label_style())
        url_label.setFixedWidth(90)
        url_row.addWidget(url_label)

        self.online_url_label = QLabel("https://predict.previlium.com")
        self.online_url_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-family: monospace;")
        url_row.addWidget(self.online_url_label)
        url_row.addStretch()

        layout.addLayout(url_row)

        # Connection info
        info_note = QLabel(
            "💡 Manual connection to online server for remote data access. "
            "Server polls every 30 seconds for online profiles."
        )
        info_note.setWordWrap(True)
        info_note.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
            padding: 10px;
            background-color: rgba(76, 175, 80, 0.1);
            border-radius: 6px;
        """)
        layout.addWidget(info_note)

        # Connect/Disconnect buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_online_connect = QPushButton("🌐 Connect to Server")
        self.btn_online_connect.clicked.connect(self._connect_to_online_server)
        self.btn_online_connect.setStyleSheet(self._get_button_style('info'))
        self.btn_online_connect.setFixedWidth(180)

        self.btn_online_disconnect = QPushButton("⏹️ Disconnect")
        self.btn_online_disconnect.clicked.connect(self._disconnect_from_online_server)
        self.btn_online_disconnect.setEnabled(False)
        self.btn_online_disconnect.setStyleSheet(self._get_button_style('secondary'))
        self.btn_online_disconnect.setFixedWidth(140)

        self.btn_test_server = QPushButton("🧪 Test")
        self.btn_test_server.clicked.connect(self._test_online_server)
        self.btn_test_server.setStyleSheet(self._get_button_style('secondary'))
        self.btn_test_server.setFixedWidth(80)

        btn_row.addWidget(self.btn_online_connect)
        btn_row.addWidget(self.btn_online_disconnect)
        btn_row.addWidget(self.btn_test_server)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        # Online server log (smaller)
        self.online_log = QTextEdit()
        self.online_log.setMaximumHeight(80)
        self.online_log.setReadOnly(True)
        self.online_log.setPlaceholderText("Server connection events...")
        self.online_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BACKGROUND};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.online_log)

        return group

    def _create_log_group(self) -> QGroupBox:
        """Create connection log section"""
        group = QGroupBox("Connection Activity Log")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.connection_log = QTextEdit()
        self.connection_log.setMaximumHeight(120)
        self.connection_log.setReadOnly(True)
        self.connection_log.setPlaceholderText("Connection events will appear here...")
        self.connection_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BACKGROUND};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.connection_log)

        # Clear button
        btn_row = QHBoxLayout()
        self.btn_clear_log = QPushButton("🗑️ Clear Log")
        self.btn_clear_log.clicked.connect(lambda: self.connection_log.clear())
        self.btn_clear_log.setStyleSheet(self._get_button_style('secondary'))
        self.btn_clear_log.setFixedWidth(120)
        btn_row.addWidget(self.btn_clear_log)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        return group

    # ================================
    # ONLINE SERVER METHODS (NEW)
    # ================================

    def _connect_to_online_server(self):
        """Manually connect to the online server"""
        self._online_log("🌐 Connecting to online server...")
        self.btn_online_connect.setEnabled(False)
        self.btn_online_connect.setText("Connecting...")
        QApplication.processEvents()

        # Get API key
        api_key = self._get_api_key()
        if not api_key:
            self._online_log("⚠️ No API key found - using public access")
            # Desktop connections don't need API keys
            # Only mobile apps use API keys for authentication

        # Start connection test in background (no API key needed for desktop)
        self.connection_poller = ServerConnectionPoller(self.online_server_url)
        self.connection_poller.test_result.connect(self._on_online_server_test_result)
        self.connection_poller.start()

    def _on_online_server_test_result(self, success: bool, message: str):
        """Handle online server connection test result"""
        self._online_log(message)

        if success:
            self.online_server_connected = True
            self.online_led.set_status('success')
            self.online_status_label.setText("✅ Connected")
            self.online_status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 14px;")

            self.btn_online_connect.setEnabled(False)
            self.btn_online_connect.setText("🌐 Connected")
            self.btn_online_disconnect.setEnabled(True)

            self._log("🌐 Online server connection established")
        else:
            self.online_server_connected = False
            self.online_led.set_status('danger')
            self.online_status_label.setText("❌ Failed")
            self.online_status_label.setStyleSheet(f"color: {Theme.DANGER}; font-weight: bold; font-size: 14px;")

            self.btn_online_connect.setEnabled(True)
            self.btn_online_connect.setText("🌐 Connect to Server")
            self.btn_online_disconnect.setEnabled(False)

    def _disconnect_from_online_server(self):
        """Manually disconnect from online server"""
        self._online_log("⏹️ Disconnected from online server")

        self.online_server_connected = False
        self.online_led.set_status('danger')
        self.online_status_label.setText("Disconnected")
        self.online_status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-weight: bold; font-size: 14px;")

        self.btn_online_connect.setEnabled(True)
        self.btn_online_connect.setText("🌐 Connect to Server")
        self.btn_online_disconnect.setEnabled(False)

        self._log("🌐 Online server disconnected")

    def _test_online_server(self):
        """Test connection to online server without connecting"""
        self._online_log("🧪 Testing server connection...")

        # Desktop connections use /api/health endpoint (no API key needed)
        poller = ServerConnectionPoller(self.online_server_url)
        poller.test_result.connect(lambda success, msg: self._online_log(f"Test: {msg}"))
        poller.start()

    def _get_api_key(self) -> str:
        """Get API key for server authentication"""
        try:
            import os
            # Use CONFIG path with fallback to legacy path
            if CONFIG:
                api_keys_folder = str(CONFIG.get_customer_api_keys_dir("default"))
            else:
                api_keys_folder = "C:/OBDserver/API_KEYS"
            if not os.path.exists(api_keys_folder):
                return None

            for filename in os.listdir(api_keys_folder):
                if filename.endswith("_apikey.txt"):
                    filepath = os.path.join(api_keys_folder, filename)
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                            for line in content.split('\n'):
                                line = line.strip()
                                if line and len(line) == 9 and line.isalnum():
                                    return line
                    except:
                        pass
        except:
            pass
        return None

    def _online_log(self, message: str):
        """Add message to online server log"""
        if hasattr(self, 'online_log'):
            self.online_log.append(message)

    # ================================
    # MOBILE SERVER METHODS
    # ================================

    def _toggle_mobile_server(self):
        """Toggle mobile server on/off"""
        try:
            if not hasattr(self.parent(), 'mobile_wrapper'):
                show_warning(self, "Not Available", "Mobile server not initialized")
                return

            wrapper = self.parent().mobile_wrapper
            if not wrapper:
                show_warning(self, "Not Available", "Mobile server not available")
                return

            if wrapper.is_running:
                # Stop server
                if wrapper.stop_server():
                    self.mobile_server_btn.setText("▶️ Start Mobile Server")
                    self.mobile_server_btn.setStyleSheet(self._get_button_style('success'))
                    self.mobile_status_label.setText("Server: Stopped")
                    self.mobile_status_label.setStyleSheet(f"color: {Theme.DANGER}; font-weight: bold;")
                    self.mobile_led.set_status('danger')
                    self._log("Mobile server stopped")
            else:
                # Start server
                if wrapper.start_server():
                    self.mobile_server_btn.setText("⏹️ Stop Mobile Server")
                    self.mobile_server_btn.setStyleSheet(self._get_button_style('warning'))
                    self.mobile_status_label.setText("Server: Running ✓")
                    self.mobile_status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold;")
                    self.mobile_led.set_status('success')
                    self._log(f"Mobile server started on port 8000")
                else:
                    show_error(self, "Error", "Failed to start mobile server")

        except Exception as e:
            show_error(self, "Error", f"Mobile server error: {e}")
            self._log(f"❌ Mobile server error: {e}")

    # ================================
    # PORT MANAGEMENT
    # ================================

    def _initialize_port_combo(self):
        """Initialize port combo box"""
        common_ports = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'COM10']
        detected_ports = []

        if hasattr(self.conn, 'detect_com_ports'):
            ports = self.conn.detect_com_ports()
            detected_ports = [p['port'] for p in ports]

        all_ports = list(set(detected_ports + common_ports))
        all_ports.sort(key=lambda x: int(x.replace('COM', '')) if x.startswith('COM') and x.replace('COM', '').isdigit() else 999)

        self.port_combo.clear()
        self.port_combo.addItems(all_ports)

        if 'COM6' in all_ports:
            self.port_combo.setCurrentText('COM6')

    def _refresh_port_list(self):
        """Refresh the port list"""
        self._log("🔄 Refreshing port list...")

        detected_ports = []
        if hasattr(self.conn, 'detect_com_ports'):
            ports = self.conn.detect_com_ports()
            detected_ports = [p['port'] for p in ports]

            for p in ports:
                self._log(f"  Found: {p['port']} - {p.get('description', 'N/A')}")

        common_ports = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'COM10']
        all_ports = list(set(detected_ports + common_ports))
        all_ports.sort(key=lambda x: int(x.replace('COM', '')) if x.startswith('COM') and x.replace('COM', '').isdigit() else 999)

        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(all_ports)

        if current in all_ports:
            self.port_combo.setCurrentText(current)

        self._log(f"📝 Found {len(detected_ports)} ports")

    # ================================
    # STATUS UPDATES
    # ================================

    def _update_all_status(self):
        """Update all status displays"""
        self._update_profile_status()
        self._update_connection_status()

    def _update_profile_status(self):
        """Update vehicle profile status display"""
        has_profile = self.conn.has_vehicle_profile()
        profile = self.conn.get_vehicle_profile()

        if has_profile and profile:
            name = profile.get('name', 'Unknown')
            make = profile.get('make', profile.get('brand', 'Unknown'))
            model = profile.get('model', 'Unknown')
            year = profile.get('year', '')

            self.profile_led.set_status('success')
            self.profile_status_label.setText(f"✅ {name}")
            self.profile_status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 14px;")
            self.profile_info_label.setText(f"{year} {make} {model}")
        else:
            self.profile_led.set_status('danger')
            self.profile_status_label.setText("⚠️ No profile selected")
            self.profile_status_label.setStyleSheet(f"color: {Theme.WARNING}; font-weight: bold; font-size: 14px;")
            self.profile_info_label.setText("Select a vehicle profile from the Profiles tab")

    def _update_connection_status(self):
        """Update OBD connection status display"""
        is_connected = getattr(self.conn, 'connected', False)

        if is_connected:
            self.conn_led = getattr(self, 'conn_led', None)
            if self.conn_led:
                self.conn_led.set_status('success')
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            if hasattr(self, 'conn_led') and self.conn_led:
                self.conn_led.set_status('danger')
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    # ================================
    # CONNECTION ACTIONS
    # ================================

    def _on_connect(self):
        """Handle OBD connect button click"""
        if not self.conn.has_vehicle_profile():
            show_warning(
                self,
                "Vehicle Profile Required",
                "Please select a vehicle profile first.\n\nGo to the Profiles tab."
            )
            return

        port = self.port_combo.currentText().strip()
        if not port:
            show_error(self, "Invalid Port", "Please select a COM port")
            return

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Connecting...")

        self._log(f"🔌 Connecting to {port}...")
        QApplication.processEvents()

        try:
            success = self.conn.connect_universal(port, 38400, "auto")

            if success:
                self._log("✅ OBD Connected successfully!")
                self._update_connection_status()
            else:
                self._log("❌ Connection failed")
                self._log("  • Check adapter is plugged in")
                self._log("  • Ensure ignition is ON")
                self._log("  • Try a different COM port")

        except Exception as e:
            self._log(f"❌ Error: {str(e)}")
        finally:
            self.btn_connect.setText("🔌 Connect OBD")
            self._update_connection_status()

    def _on_disconnect(self):
        """Handle OBD disconnect button click"""
        try:
            self.conn.disconnect()
            self._update_connection_status()
            self._log("🔌 Disconnected from OBD adapter")
        except Exception as e:
            show_error(self, "Disconnect Error", f"Error: {str(e)}")

    # ================================
    # SIGNAL HANDLERS
    # ================================

    def _on_status_changed(self, status: str):
        """Handle status changed signal"""
        self._log(f"📡 Status: {status}")

    def _on_error(self, error: str):
        """Handle error signal"""
        self._log(f"❌ Error: {error}")

    def _on_connection_lost(self):
        """Handle connection lost signal"""
        self._log("\n⚠️ CONNECTION LOST!")
        self._update_connection_status()

    def _on_strategy_changed(self, strategy: str):
        """Handle strategy changed signal"""
        self._log(f"🔀 Strategy: {strategy}")

    # ================================
    # LOGGING
    # ================================

    def _log(self, message: str):
        """Add message to connection log"""
        if hasattr(self, 'connection_log'):
            self.connection_log.append(message)


# ================================
# BACKWARD COMPATIBILITY
# ================================

BluetoothTab = ConnectionTab
