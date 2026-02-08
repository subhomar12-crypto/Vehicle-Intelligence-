"""
PySide6 Main Window for PREDICT Desktop.

Provides a native desktop interface to the PREDICT platform
with embedded server for local operation.
"""

import logging
import sys
from typing import Optional

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

logger = logging.getLogger(__name__)


class StatusPoller(QThread):
    """Background thread for polling server status."""
    
    status_updated = Signal(dict)
    
    def __init__(self, server_url: str, interval_ms: int = 5000):
        super().__init__()
        self.server_url = server_url
        self.interval_ms = interval_ms
        self._running = True
    
    def run(self):
        """Poll server status periodically."""
        import requests
        
        while self._running:
            try:
                response = requests.get(
                    f"{self.server_url}/health",
                    timeout=5
                )
                status = {
                    "online": response.status_code == 200,
                    "status_code": response.status_code,
                }
            except Exception as e:
                status = {
                    "online": False,
                    "error": str(e),
                }
            
            self.status_updated.emit(status)
            
            # Sleep interval
            for _ in range(self.interval_ms // 100):
                if not self._running:
                    break
                self.msleep(100)
    
    def stop(self):
        """Stop the poller."""
        self._running = False


class PredictMainWindow(QMainWindow):
    """
    Main application window for PREDICT Desktop.
    """
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 800)
        
        self._status_poller: Optional[StatusPoller] = None
        
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._start_status_polling()
    
    def _setup_ui(self):
        """Setup the main UI."""
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
        
        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        
        # Dashboard tab
        self._dashboard_tab = self._create_dashboard_tab()
        self._tabs.addTab(self._dashboard_tab, "Dashboard")
        
        # Logs tab
        self._logs_tab = self._create_logs_tab()
        self._tabs.addTab(self._logs_tab, "Logs")
        
        # Settings tab
        self._settings_tab = self._create_settings_tab()
        self._tabs.addTab(self._settings_tab, "Settings")
    
    def _create_dashboard_tab(self) -> QWidget:
        """Create the dashboard tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Welcome message
        welcome = QLabel(
            "Welcome to PREDICT Desktop!\n\n"
            "The embedded server is running locally.\n"
            "Use the API endpoints for vehicle diagnostics and predictions."
        )
        welcome.setAlignment(Qt.AlignCenter)
        layout.addWidget(welcome)
        
        # API info
        server = get_server_manager().server
        if server:
            api_info = QLabel(f"API Base URL: {server.base_url}")
            api_info.setAlignment(Qt.AlignCenter)
            layout.addWidget(api_info)
        
        # Quick actions
        actions_layout = QHBoxLayout()
        
        self._health_btn = QPushButton("Check Health")
        self._health_btn.clicked.connect(self._check_health)
        actions_layout.addWidget(self._health_btn)
        
        self._docs_btn = QPushButton("Open API Docs")
        self._docs_btn.clicked.connect(self._open_docs)
        actions_layout.addWidget(self._docs_btn)
        
        layout.addLayout(actions_layout)
        
        # Spacer
        layout.addStretch()
        
        return widget
    
    def _create_logs_tab(self) -> QWidget:
        """Create the logs tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Log display
        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self._log_display)
        
        # Log controls
        controls = QHBoxLayout()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._log_display.clear)
        controls.addWidget(clear_btn)
        
        controls.addStretch()
        
        layout.addLayout(controls)
        
        return widget
    
    def _create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Settings placeholder
        info = QLabel("Settings configuration coming soon...")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        layout.addStretch()
        
        return widget
    
    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
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
    
    def _start_status_polling(self):
        """Start polling server status."""
        server = get_server_manager().server
        if not server:
            return
        
        self._status_poller = StatusPoller(server.base_url)
        self._status_poller.status_updated.connect(self._update_status)
        self._status_poller.start()
    
    def _update_status(self, status: dict):
        """Update UI with server status."""
        if status.get("online"):
            self._status_label.setText("Server: Online ✅")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText("Server: Offline ❌")
            self._status_label.setStyleSheet("color: red;")
    
    def _check_health(self):
        """Check server health manually."""
        import requests
        
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
        import webbrowser
        
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
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop status poller
        if self._status_poller:
            self._status_poller.stop()
            self._status_poller.wait(1000)
        
        # Accept close event
        event.accept()
