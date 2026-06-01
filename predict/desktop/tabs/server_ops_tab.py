"""
Server & Operations Tab - Server monitoring and controls.

Tab 2 of 6 in the PREDICT Desktop GUI.
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTableWidget, QTableWidgetItem, QPlainTextEdit,
    QComboBox, QScrollArea, QFrame
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme, get_card_stylesheet
from predict.desktop.workers import APIWorker, PollingWorker
from predict.desktop.api_client import PredictAPIClient
from predict.desktop.server_thread import get_server_manager
from predict.core.config import get_config

logger = logging.getLogger(__name__)


class MetricCard(QGroupBox):
    """Metric display card."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(get_card_stylesheet())
        layout = QVBoxLayout(self)

        self._value = QLabel("--")
        self._value.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self._value.setAlignment(Qt.AlignCenter)

        self._desc = QLabel(title)
        self._desc.setFont(QFont("Segoe UI", 10))
        self._desc.setAlignment(Qt.AlignCenter)
        self._desc.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}")

        layout.addWidget(self._value)
        layout.addWidget(self._desc)

    def set_value(self, value: str, color: str = None):
        """Set the metric value."""
        self._value.setText(value)
        if color:
            self._value.setStyleSheet(f"color: {color}")


class ServerOpsTab(QWidget):
    """Tab for server operations and monitoring."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._server_manager = get_server_manager()
        self._health_worker = None
        self._log_file = None
        self._last_pos = 0

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Section 1: Server Controls
        controls_group = QGroupBox("Server Controls")
        controls_main = QVBoxLayout(controls_group)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Server")
        self._stop_btn = QPushButton("Stop Server")
        self._restart_btn = QPushButton("Restart")
        self._status_label = QLabel("Unknown")
        self._uptime_label = QLabel("Uptime: --")

        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._restart_btn.clicked.connect(self._on_restart)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._restart_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._status_label)
        btn_row.addWidget(self._uptime_label)
        controls_main.addLayout(btn_row)

        # Live status row
        live_row = QHBoxLayout()
        self._live_dot = QLabel("\u25CF")
        self._live_dot.setFont(QFont("Segoe UI", 14))
        self._live_dot.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}")
        self._live_label = QLabel("Offline")
        self._live_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._live_url = QLabel("")
        self._live_url.setFont(QFont("Segoe UI", 9))
        self._live_url.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}")
        self._live_url.setTextInteractionFlags(Qt.TextSelectableByMouse)

        live_row.addWidget(self._live_dot)
        live_row.addWidget(self._live_label)
        live_row.addWidget(self._live_url)
        live_row.addStretch()
        controls_main.addLayout(live_row)

        layout.addWidget(controls_group)

        # Section 2: Health Metrics
        health_group = QGroupBox("Health Metrics")
        health_layout = QHBoxLayout(health_group)

        self._cpu_card = MetricCard("CPU")
        self._mem_card = MetricCard("Memory")
        self._req_card = MetricCard("Requests")
        self._conn_card = MetricCard("Connections")

        health_layout.addWidget(self._cpu_card)
        health_layout.addWidget(self._mem_card)
        health_layout.addWidget(self._req_card)
        health_layout.addWidget(self._conn_card)

        layout.addWidget(health_group)

        # Section 3: Services Status
        services_group = QGroupBox("Services")
        services_layout = QVBoxLayout(services_group)

        self._services_table = QTableWidget()
        self._services_table.setColumnCount(3)
        self._services_table.setHorizontalHeaderLabels(
            ["Service", "Status", "Details"]
        )
        self._services_table.setFont(QFont("Segoe UI", 11))
        self._services_table.setMinimumHeight(200)
        self._services_table.horizontalHeader().setStretchLastSection(True)
        self._services_table.setRowCount(3)
        services = ["PostgreSQL", "Redis", "AI Models"]
        for i, svc in enumerate(services):
            self._services_table.setItem(i, 0, QTableWidgetItem(svc))
            self._services_table.setItem(i, 1, QTableWidgetItem("Unknown"))
            self._services_table.setItem(i, 2, QTableWidgetItem("--"))

        services_layout.addWidget(self._services_table)
        layout.addWidget(services_group)

        # Section 4: Server Logs
        logs_group = QGroupBox("Logs")
        logs_layout = QVBoxLayout(logs_group)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self._log_filter = QComboBox()
        self._log_filter.addItems(["ALL", "ERROR", "WARNING", "INFO", "DEBUG"])
        self._log_filter.currentTextChanged.connect(self._on_filter_changed)
        self._clear_log_btn = QPushButton("Clear")
        self._clear_log_btn.clicked.connect(self._on_clear_logs)

        filter_layout.addWidget(self._log_filter)
        filter_layout.addWidget(self._clear_log_btn)
        filter_layout.addStretch()
        logs_layout.addLayout(filter_layout)

        self._log_display = QPlainTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setFont(QFont("Consolas", 11))
        self._log_display.setStyleSheet(
            f"background-color: {PredictTheme.BG_PRIMARY}; "
            f"color: {PredictTheme.TEXT_PRIMARY};"
        )
        self._log_display.setMinimumHeight(300)
        logs_layout.addWidget(self._log_display)

        layout.addWidget(logs_group)

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        # Setup log file
        config = get_config()
        self._log_file = Path(config.LOGS_DIR) / "desktop.log"

    def _start_monitors(self):
        """Start monitoring timers and workers."""
        # Status update timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(2000)
        self._update_status()

        # Health polling worker
        self._health_worker = PollingWorker(self._api.detailed_health, 5000)
        self._health_worker.data_received.connect(self._on_health_data)
        self._health_worker.start()

        # Log tail timer
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._read_new_logs)
        self._log_timer.start(2000)

    def _update_status(self):
        """Update server and tunnel status display."""
        is_running = self._server_manager.is_running
        is_live = self._server_manager.is_live

        if is_running:
            self._status_label.setText("Running")
            self._status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}")
        else:
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet(f"color: {PredictTheme.DANGER}")

        self._start_btn.setEnabled(not is_running)
        self._stop_btn.setEnabled(is_running)

        # Update live/tunnel indicator
        if is_live:
            self._live_dot.setStyleSheet(f"color: {PredictTheme.SUCCESS}")
            self._live_label.setText("LIVE")
            self._live_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}")
            config = get_config()
            self._live_url.setText(config.PUBLIC_API_URL)
        elif is_running:
            self._live_dot.setStyleSheet(f"color: {PredictTheme.WARNING}")
            self._live_label.setText("Local Only")
            self._live_label.setStyleSheet(f"color: {PredictTheme.WARNING}")
            self._live_url.setText("http://127.0.0.1:8000")
        else:
            self._live_dot.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}")
            self._live_label.setText("Offline")
            self._live_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}")
            self._live_url.setText("")

    def _on_start(self):
        """Start the server and Cloudflare tunnel."""
        config = get_config()
        self._server_manager.start_server(config.SERVER_HOST, config.SERVER_PORT)

    def _on_stop(self):
        """Stop the server and Cloudflare tunnel."""
        self._server_manager.stop_server()

    def _on_restart(self):
        """Restart the server and Cloudflare tunnel."""
        self._server_manager.stop_server()
        config = get_config()
        self._server_manager.start_server(config.SERVER_HOST, config.SERVER_PORT)

    def _on_health_data(self, data: dict):
        """Handle health data received."""
        # Handle both direct health data and nested health data
        health = data.get("health", data)

        # Update uptime label from health data
        uptime_formatted = health.get("uptime_formatted", "--")
        self._uptime_label.setText(f"Uptime: {uptime_formatted}")

        # Update metric cards from system metrics
        system = health.get("system", {})
        cpu_data = system.get("cpu", {})
        mem_data = system.get("memory", {})
        
        cpu = cpu_data.get("percent", 0) if cpu_data else 0
        mem = mem_data.get("percent", 0) if mem_data else 0

        cpu_color = self._get_metric_color(cpu)
        mem_color = self._get_metric_color(mem)

        self._cpu_card.set_value(f"{cpu:.1f}%" if cpu else "--", cpu_color)
        self._mem_card.set_value(f"{mem:.1f}%" if mem else "--", mem_color)
        
        # Requests and connections not in new format, show response time
        response_ms = health.get("response_time_ms", 0)
        self._req_card.set_value(f"{response_ms:.0f}ms")
        
        # Show memory usage in MB
        mem_used = mem_data.get("used_mb", 0) if mem_data else 0
        self._conn_card.set_value(f"{mem_used:.0f}MB" if mem_used else "--")

        # Update services table from new health format
        services = health.get("services", {})
        service_names = ["PostgreSQL", "Redis", "AI Models"]
        service_keys = ["database", "redis", "ai_models"]

        self._services_table.setRowCount(len(service_names))
        for i, (name, key) in enumerate(zip(service_names, service_keys)):
            svc_data = services.get(key, {})
            status = svc_data.get("status", "Unknown")
            response_time = svc_data.get("response_time_ms", 0)
            
            detail = f"{response_time:.1f}ms" if response_time else "--"

            self._services_table.setItem(i, 0, QTableWidgetItem(name))
            if status == "unavailable":
                status_item = QTableWidgetItem("Not Installed")
                status_item.setForeground(QColor(PredictTheme.WARNING))
            elif status == "healthy":
                status_item = QTableWidgetItem("Healthy")
                status_item.setForeground(QColor(PredictTheme.SUCCESS))
            elif status == "unhealthy":
                status_item = QTableWidgetItem("Unhealthy")
                status_item.setForeground(QColor(PredictTheme.DANGER))
            else:
                status_item = QTableWidgetItem(status.capitalize())
                status_item.setForeground(QColor(PredictTheme.WARNING))

            self._services_table.setItem(i, 1, status_item)
            self._services_table.setItem(i, 2, QTableWidgetItem(detail))

    def _get_metric_color(self, value: float) -> str:
        """Get color based on metric value."""
        if value < 70:
            return PredictTheme.SUCCESS
        elif value < 90:
            return PredictTheme.WARNING
        else:
            return PredictTheme.DANGER

    def _read_new_logs(self):
        """Read new log lines."""
        if not self._log_file or not self._log_file.exists():
            return

        try:
            with open(self._log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._last_pos)
                new_lines = f.readlines()
                self._last_pos = f.tell()

            filter_text = self._log_filter.currentText()
            for line in new_lines:
                if filter_text != "ALL" and filter_text not in line:
                    continue
                self._log_display.appendPlainText(line.rstrip())

            # Trim if too many lines
            if self._log_display.blockCount() > 1000:
                cursor = self._log_display.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                for _ in range(self._log_display.blockCount() - 1000):
                    cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

        except Exception as e:
            logger.debug(f"Error reading logs: {e}")

    def _on_filter_changed(self, text: str):
        """Handle log filter change."""
        self._log_display.clear()
        self._last_pos = 0

    def _on_clear_logs(self):
        """Clear log display."""
        self._log_display.clear()

    def cleanup(self):
        """Stop all background workers and timers."""
        if hasattr(self, '_status_timer') and self._status_timer:
            self._status_timer.stop()
        if hasattr(self, '_log_timer') and self._log_timer:
            self._log_timer.stop()
        if self._health_worker:
            self._health_worker.stop()
            self._health_worker.wait(2000)

    def closeEvent(self, event):
        """Clean up on close."""
        self.cleanup()
        event.accept()
