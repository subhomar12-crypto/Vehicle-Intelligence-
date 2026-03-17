"""
PySide6 Main Window for PREDICT Desktop.

Provides a native desktop interface to the PREDICT platform
with embedded server for local operation.
"""

import logging
import sys
import webbrowser
from typing import Optional

try:
    import requests
    _has_requests = True
except ImportError:
    _has_requests = False

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QStatusBar,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QFont

from predict.core.version import APP_NAME, APP_VERSION
from predict.desktop.server_thread import get_server_manager
from predict.desktop.api_client import PredictAPIClient
from predict.desktop.workers import StatusPoller, WebSocketListener

# Import tab classes
from predict.desktop.tabs.profile_tab import ProfileTab
from predict.desktop.tabs.server_ops_tab import ServerOpsTab
from predict.desktop.tabs.ai_llm_tab import AILLMTab
from predict.desktop.tabs.pdf_tab import PDFTab
from predict.desktop.tabs.dtc_tab import DTCTab
from predict.desktop.tabs.analytics_tab import AnalyticsTab
from predict.desktop.tabs.fleet_requests_tab import FleetRequestsTab
from predict.desktop.tabs.vehicle_photos_tab import VehiclePhotosTab
from predict.desktop.tabs.pricing_tab import PricingTab

logger = logging.getLogger(__name__)


class PredictMainWindow(QMainWindow):
    """
    Main application window for PREDICT Desktop.
    6-tab interface: Profiles, Server & Ops, AI & LLM, PDF Reports, DTC Manager, Analytics
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1400, 900)

        self._status_poller: Optional[StatusPoller] = None
        self._ws_listener: Optional[WebSocketListener] = None
        self._api_client: Optional[PredictAPIClient] = None

        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        # Defer background services until the Qt event loop is running
        QTimer.singleShot(300, self._start_services)

    def _setup_ui(self):
        """Setup the main UI with 6 tabs."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QLabel(f"{APP_NAME} - Vehicle Intelligence Platform")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Server status
        self._status_label = QLabel("Server: Initializing...")
        layout.addWidget(self._status_label)

        # Create API client (server.base_url is http://host:port, add /api prefix)
        server = get_server_manager().server
        self._api_client = PredictAPIClient(base_url=f"{server.base_url}/api")

        # Tab widget
        self._tabs = QTabWidget()

        # Create 6 tabs
        self._profile_tab = ProfileTab(self._api_client, self._ws_listener)
        self._server_ops_tab = ServerOpsTab(self._api_client)
        self._ai_llm_tab = AILLMTab(self._api_client)
        self._pdf_tab = PDFTab(self._api_client)
        self._dtc_tab = DTCTab(self._api_client)
        self._analytics_tab = AnalyticsTab(self._api_client)
        self._fleet_requests_tab = FleetRequestsTab(self._api_client)
        self._vehicle_photos_tab = VehiclePhotosTab(self._api_client)
        self._pricing_tab = PricingTab(self._api_client)

        # Add tabs
        self._tabs.addTab(self._profile_tab, "Profiles")
        self._tabs.addTab(self._server_ops_tab, "Server & Ops")
        self._tabs.addTab(self._ai_llm_tab, "AI & LLM")
        self._tabs.addTab(self._pdf_tab, "PDF Reports")
        self._tabs.addTab(self._dtc_tab, "DTC Manager")
        self._tabs.addTab(self._analytics_tab, "Analytics")
        self._tabs.addTab(self._fleet_requests_tab, "Fleet Requests")
        self._tabs.addTab(self._vehicle_photos_tab, "Vehicle Photos")
        self._tabs.addTab(self._pricing_tab, "Pricing")

        layout.addWidget(self._tabs)

    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        refresh_action = QAction("Refresh Current Tab", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_current_tab)
        view_menu.addAction(refresh_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        health_action = QAction("Health Check", self)
        health_action.triggered.connect(self._check_health)
        tools_menu.addAction(health_action)

        docs_action = QAction("API Documentation", self)
        docs_action.triggered.connect(self._open_docs)
        tools_menu.addAction(docs_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self):
        """Setup the status bar."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(150)
        self._progress.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress)

        # Status message
        self._status_bar.showMessage("Ready")

    def _start_services(self):
        """Start status polling and WebSocket."""
        server = get_server_manager().server
        if not server:
            return

        # Start status poller
        self._status_poller = StatusPoller(server.base_url)
        self._status_poller.status_updated.connect(self._update_status)
        self._status_poller.start()

        # Start WebSocket listener
        ws_url = f"ws://{server.host}:{server.port}/api/ws"
        self._ws_listener = WebSocketListener(ws_url)
        self._ws_listener.connected.connect(self._on_ws_connected)
        self._ws_listener.disconnected.connect(self._on_ws_disconnected)
        self._ws_listener.start()

        # Update profile tab with WebSocket
        self._profile_tab._ws_listener = self._ws_listener
        self._ws_listener.user_change.connect(self._profile_tab._on_user_change)

    def _update_status(self, status: dict):
        """Update UI with server status."""
        if status.get("online"):
            self._status_label.setText("Server: Online ✅")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText("Server: Offline ❌")
            self._status_label.setStyleSheet("color: red;")

    def _on_ws_connected(self):
        """Handle WebSocket connected."""
        logger.info("WebSocket connected")
        self._status_bar.showMessage("Real-time updates connected")

    def _on_ws_disconnected(self):
        """Handle WebSocket disconnected."""
        logger.info("WebSocket disconnected")
        self._status_bar.showMessage("Real-time updates disconnected")

    def _refresh_current_tab(self):
        """Refresh the currently selected tab."""
        current_tab = self._tabs.currentWidget()
        if hasattr(current_tab, '_load_data'):
            current_tab._load_data()
        elif hasattr(current_tab, '_load_users'):
            current_tab._load_users()
        elif hasattr(current_tab, '_on_refresh'):
            current_tab._on_refresh()

    def _check_health(self):
        """Check server health manually."""
        if not _has_requests:
            QMessageBox.warning(self, "Error", "requests library not installed")
            return

        server = get_server_manager().server
        if not server:
            QMessageBox.warning(self, "Error", "Server not running")
            return

        try:
            response = requests.get(f"{server.base_url}/health/ready", timeout=5)
            data = response.json()

            QMessageBox.information(
                self,
                "Health Check",
                f"Status: {data.get('status', 'unknown')}\n"
                f"Checks: {data.get('checks', {})}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Health check failed: {e}")

    def _open_docs(self):
        """Open API documentation in browser."""
        server = get_server_manager().server
        if server:
            webbrowser.open(f"{server.base_url}/docs")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            f"<p>Vehicle Intelligence Platform</p>"
            f"<p>Unified Desktop + Server Architecture</p>"
            f"<p>9-Tab Admin Interface</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop tab PollingWorkers first (Qt doesn't call closeEvent on child widgets)
        for tab in [self._server_ops_tab, self._ai_llm_tab, self._analytics_tab, self._fleet_requests_tab, self._vehicle_photos_tab, self._pricing_tab]:
            if hasattr(tab, 'cleanup'):
                tab.cleanup()

        # Stop status poller
        if self._status_poller:
            self._status_poller.stop()
            self._status_poller.wait(2000)

        # Stop WebSocket listener
        if self._ws_listener:
            self._ws_listener.stop()
            self._ws_listener.wait(2000)

        # Stop embedded server and kill any orphaned server process
        try:
            from predict.desktop.server_thread import get_server_manager
            get_server_manager().stop_server()
        except Exception:
            pass

        # Accept close event
        event.accept()
