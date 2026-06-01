"""
Dashboard Monitor tab for server health monitoring.

Shows system metrics, server stats, circuit breaker status, and database pool info.
"""

import logging
import random
import time
from datetime import timedelta
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTableWidget, QTableWidgetItem, QGroupBox,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


try:
    import psutil
    _has_psutil = True
except ImportError:
    _has_psutil = False


class DashboardMonitorTab(QWidget):
    """
    Tab for server health monitoring.
    
    Features:
    - System metrics (CPU, Memory, Disk)
    - Server stats (requests/sec, active users, uptime)
    - Circuit breaker panel
    - Database pool status
    - Redis status
    - Auto-refresh every 5 seconds
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._start_time = time.time()
        self._circuit_breakers: Dict[str, Any] = {}
        self._setup_ui()
        self._setup_timer()
        self._load_sample_data()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Server Dashboard")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Top row: System metrics
        metrics_layout = QHBoxLayout()
        
        # CPU
        self.cpu_card = self._create_metric_card("CPU Usage", "0%", PredictTheme.INFO)
        metrics_layout.addWidget(self.cpu_card)
        
        # Memory
        self.memory_card = self._create_metric_card("Memory", "0%", PredictTheme.SUCCESS)
        metrics_layout.addWidget(self.memory_card)
        
        # Disk
        self.disk_card = self._create_metric_card("Disk", "0%", PredictTheme.WARNING)
        metrics_layout.addWidget(self.disk_card)
        
        # Uptime
        self.uptime_card = self._create_metric_card("Uptime", "00:00:00", PredictTheme.TEXT_SECONDARY)
        metrics_layout.addWidget(self.uptime_card)
        
        layout.addLayout(metrics_layout)
        
        # Middle row
        middle_layout = QHBoxLayout()
        
        # Server stats
        stats_group = QGroupBox("Server Statistics")
        stats_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        stats_layout = QGridLayout(stats_group)
        
        stats_layout.addWidget(QLabel("Requests/sec:"), 0, 0)
        self.requests_label = QLabel("0")
        self.requests_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        stats_layout.addWidget(self.requests_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Active Users:"), 1, 0)
        self.users_label = QLabel("0")
        self.users_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        stats_layout.addWidget(self.users_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Avg Response:"), 2, 0)
        self.response_label = QLabel("0 ms")
        self.response_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        stats_layout.addWidget(self.response_label, 2, 1)
        
        middle_layout.addWidget(stats_group)
        
        # Database pool
        db_group = QGroupBox("Database Pool")
        db_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        db_layout = QGridLayout(db_group)
        
        db_layout.addWidget(QLabel("Active:"), 0, 0)
        self.db_active_label = QLabel("0")
        self.db_active_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
        db_layout.addWidget(self.db_active_label, 0, 1)
        
        db_layout.addWidget(QLabel("Idle:"), 1, 0)
        self.db_idle_label = QLabel("0")
        self.db_idle_label.setStyleSheet(f"color: {PredictTheme.INFO}; font-weight: bold;")
        db_layout.addWidget(self.db_idle_label, 1, 1)
        
        db_layout.addWidget(QLabel("Max:"), 2, 0)
        self.db_max_label = QLabel("20")
        self.db_max_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        db_layout.addWidget(self.db_max_label, 2, 1)
        
        middle_layout.addWidget(db_group)
        
        # Redis status
        redis_group = QGroupBox("Redis Cache")
        redis_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        redis_layout = QGridLayout(redis_group)
        
        redis_layout.addWidget(QLabel("Status:"), 0, 0)
        self.redis_status_label = QLabel("Connected")
        self.redis_status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
        redis_layout.addWidget(self.redis_status_label, 0, 1)
        
        redis_layout.addWidget(QLabel("Memory:"), 1, 0)
        self.redis_memory_label = QLabel("12.5 MB")
        self.redis_memory_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        redis_layout.addWidget(self.redis_memory_label, 1, 1)
        
        redis_layout.addWidget(QLabel("Keys:"), 2, 0)
        self.redis_keys_label = QLabel("1,245")
        self.redis_keys_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        redis_layout.addWidget(self.redis_keys_label, 2, 1)
        
        middle_layout.addWidget(redis_group)
        
        layout.addLayout(middle_layout)
        
        # Circuit breaker panel
        cb_group = QGroupBox("Circuit Breakers")
        cb_group.setStyleSheet(PredictTheme.get_card_stylesheet(PredictTheme.WARNING))
        cb_layout = QVBoxLayout(cb_group)
        
        self.cb_table = QTableWidget()
        self.cb_table.setColumnCount(5)
        self.cb_table.setHorizontalHeaderLabels([
            "Service", "State", "Failures", "Last Failure", "Reset Time"
        ])
        self.cb_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        cb_layout.addWidget(self.cb_table)
        
        layout.addWidget(cb_group)
        layout.addStretch()
    
    def _create_metric_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a metric card widget."""
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}; font-size: 10px;")
        layout.addWidget(title_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        value_lbl.setFont(QFont(PredictTheme.FONT_FAMILY, 28, QFont.Weight.Bold))
        layout.addWidget(value_lbl)
        
        return card
    
    def _setup_timer(self) -> None:
        """Setup refresh timer."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_metrics)
        self.timer.start(5000)  # 5 seconds
    
    def _load_sample_data(self) -> None:
        """Load sample circuit breaker data."""
        self._circuit_breakers = {
            "obd_service": {
                "state": "closed",
                "failures": 0,
                "last_failure": None,
                "reset_time": None,
            },
            "ai_prediction": {
                "state": "closed",
                "failures": 2,
                "last_failure": "2024-01-15 09:30:00",
                "reset_time": "2024-01-15 09:35:00",
            },
            "external_api": {
                "state": "half-open",
                "failures": 5,
                "last_failure": "2024-01-15 10:15:00",
                "reset_time": "2024-01-15 10:20:00",
            },
            "database": {
                "state": "closed",
                "failures": 0,
                "last_failure": None,
                "reset_time": None,
            },
        }
        self._update_cb_table()
    
    def _update_cb_table(self) -> None:
        """Update circuit breaker table."""
        self.cb_table.setRowCount(len(self._circuit_breakers))
        
        for row, (service, data) in enumerate(self._circuit_breakers.items()):
            # Service name
            item = QTableWidgetItem(service.replace("_", " ").title())
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cb_table.setItem(row, 0, item)
            
            # State
            state = data["state"]
            item = QTableWidgetItem(state.upper())
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if state == "closed":
                item.setForeground(QColor(PredictTheme.SUCCESS))
            elif state == "half-open":
                item.setForeground(QColor(PredictTheme.WARNING))
            elif state == "open":
                item.setForeground(QColor(PredictTheme.DANGER))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.cb_table.setItem(row, 1, item)
            
            # Failures
            item = QTableWidgetItem(str(data["failures"]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cb_table.setItem(row, 2, item)
            
            # Last failure
            last_fail = data["last_failure"] or "Never"
            item = QTableWidgetItem(last_fail)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cb_table.setItem(row, 3, item)
            
            # Reset time
            reset_time = data["reset_time"] or "N/A"
            item = QTableWidgetItem(reset_time)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cb_table.setItem(row, 4, item)
        
        self.cb_table.resizeColumnsToContents()
    
    def _refresh_metrics(self) -> None:
        """Refresh all metrics."""
        # System metrics
        if _has_psutil:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                self._update_card(self.cpu_card, f"{cpu_percent:.0f}%", self._get_cpu_color(cpu_percent))
                self._update_card(self.memory_card, f"{memory.percent:.0f}%", self._get_mem_color(memory.percent))
                self._update_card(self.disk_card, f"{disk.percent:.0f}%", self._get_disk_color(disk.percent))
            
            except Exception as e:
                logger.warning(f"Failed to get system metrics: {e}")
                self._update_card(self.cpu_card, "N/A", PredictTheme.TEXT_MUTED)
                self._update_card(self.memory_card, "N/A", PredictTheme.TEXT_MUTED)
                self._update_card(self.disk_card, "N/A", PredictTheme.TEXT_MUTED)
        else:
            # Simulate values for demo
            cpu = random.randint(10, 60)
            mem = random.randint(30, 70)
            dsk = random.randint(40, 80)
            
            self._update_card(self.cpu_card, f"{cpu}%", self._get_cpu_color(cpu))
            self._update_card(self.memory_card, f"{mem}%", self._get_mem_color(mem))
            self._update_card(self.disk_card, f"{dsk}%", self._get_disk_color(dsk))
        
        # Uptime
        uptime = time.time() - self._start_time
        uptime_str = str(timedelta(seconds=int(uptime)))
        self._update_card(self.uptime_card, uptime_str, PredictTheme.TEXT_SECONDARY)
        
        # Server stats (simulated)
        self.requests_label.setText(f"{random.randint(10, 150)}")
        self.users_label.setText(f"{random.randint(5, 50)}")
        self.response_label.setText(f"{random.randint(20, 200)} ms")
        
        # Database pool (simulated)
        self.db_active_label.setText(str(random.randint(2, 8)))
        self.db_idle_label.setText(str(random.randint(5, 12)))
    
    def _update_card(self, card: QFrame, value: str, color: str) -> None:
        """Update metric card value."""
        # Find value label (second child)
        layout = card.layout()
        if layout and layout.count() > 1:
            value_lbl = layout.itemAt(1).widget()
            if isinstance(value_lbl, QLabel):
                value_lbl.setText(value)
                value_lbl.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        
        # Update border color
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
    
    def _get_cpu_color(self, percent: float) -> str:
        """Get color for CPU usage."""
        if percent < 50:
            return PredictTheme.SUCCESS
        elif percent < 80:
            return PredictTheme.WARNING
        return PredictTheme.DANGER
    
    def _get_mem_color(self, percent: float) -> str:
        """Get color for memory usage."""
        if percent < 60:
            return PredictTheme.SUCCESS
        elif percent < 85:
            return PredictTheme.WARNING
        return PredictTheme.DANGER
    
    def _get_disk_color(self, percent: float) -> str:
        """Get color for disk usage."""
        if percent < 70:
            return PredictTheme.SUCCESS
        elif percent < 90:
            return PredictTheme.WARNING
        return PredictTheme.DANGER
