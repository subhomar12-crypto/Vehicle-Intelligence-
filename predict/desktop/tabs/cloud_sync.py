"""
Cloud Sync tab for server synchronization status.

Shows sync status, pending items, and manual sync controls.
"""

import logging
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QCheckBox, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class CloudSyncTab(QWidget):
    """
    Tab for managing cloud synchronization.
    
    Features:
    - Connection status indicator
    - Last sync timestamp
    - Manual sync button
    - Sync queue display
    - Auto-sync toggle
    """
    
    # Sync intervals (minutes)
    SYNC_INTERVALS = ["1 minute", "5 minutes", "15 minutes", "30 minutes", "1 hour"]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._connected = False
        self._last_sync: Optional[float] = None
        self._pending_items: List[Dict[str, Any]] = []
        self._auto_sync = True
        self._setup_ui()
        self._setup_timer()
        self._load_sample_data()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Cloud Sync")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Status row
        status_layout = QHBoxLayout()
        
        # Connection status
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {PredictTheme.BORDER};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        status_frame_layout = QHBoxLayout(self.status_frame)
        
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet(f"color: {PredictTheme.DANGER}; font-size: 24px;")
        status_frame_layout.addWidget(self.status_indicator)
        
        self.status_text = QLabel("Disconnected")
        self.status_text.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        status_frame_layout.addWidget(self.status_text)
        
        status_layout.addWidget(self.status_frame)
        
        # Last sync
        last_sync_frame = QFrame()
        last_sync_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PredictTheme.CARD_BG};
                border: 2px solid {PredictTheme.BORDER};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        last_sync_layout = QVBoxLayout(last_sync_frame)
        
        last_sync_title = QLabel("Last Sync")
        last_sync_title.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}; font-size: 10px;")
        last_sync_layout.addWidget(last_sync_title)
        
        self.last_sync_label = QLabel("Never")
        self.last_sync_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
        last_sync_layout.addWidget(self.last_sync_label)
        
        status_layout.addWidget(last_sync_frame)
        
        # Sync now button
        self.sync_btn = QPushButton("Sync Now")
        self.sync_btn.setObjectName("primary")
        self.sync_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #E00000;
            }}
        """)
        self.sync_btn.clicked.connect(self._sync_now)
        status_layout.addWidget(self.sync_btn)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Auto-sync settings
        auto_sync_group = QGroupBox("Auto-Sync Settings")
        auto_sync_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        auto_sync_layout = QHBoxLayout(auto_sync_group)
        
        self.auto_sync_check = QCheckBox("Enable Auto-Sync")
        self.auto_sync_check.setChecked(self._auto_sync)
        self.auto_sync_check.stateChanged.connect(self._on_auto_sync_changed)
        auto_sync_layout.addWidget(self.auto_sync_check)
        
        auto_sync_layout.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(self.SYNC_INTERVALS)
        self.interval_combo.setCurrentIndex(2)  # 15 minutes
        auto_sync_layout.addWidget(self.interval_combo)
        
        auto_sync_layout.addStretch()
        layout.addWidget(auto_sync_group)
        
        # Sync queue
        queue_group = QGroupBox("Sync Queue")
        queue_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        queue_layout = QVBoxLayout(queue_group)
        
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["Type", "Count", "Status", "Progress"])
        self.queue_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        queue_layout.addWidget(self.queue_table)
        
        layout.addWidget(queue_group)
        
        # Server info
        info_group = QGroupBox("Server Information")
        info_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        info_layout = QGridLayout(info_group)
        
        info_layout.addWidget(QLabel("Server URL:"), 0, 0)
        self.server_url_label = QLabel("https://api.predict-vehicle.com")
        self.server_url_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        info_layout.addWidget(self.server_url_label, 0, 1)
        
        info_layout.addWidget(QLabel("API Version:"), 1, 0)
        self.api_version_label = QLabel("v3.0.0")
        self.api_version_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        info_layout.addWidget(self.api_version_label, 1, 1)
        
        info_layout.addWidget(QLabel("Data Synced:"), 2, 0)
        self.data_synced_label = QLabel("2,450 records")
        self.data_synced_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        info_layout.addWidget(self.data_synced_label, 2, 1)
        
        layout.addWidget(info_group)
        layout.addStretch()
    
    def _setup_timer(self) -> None:
        """Setup refresh timer."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(5000)  # 5 seconds
    
    def _load_sample_data(self) -> None:
        """Load sample sync queue data."""
        self._pending_items = [
            {"type": "OBD Records", "count": 45, "status": "Pending", "progress": 0},
            {"type": "Trip Data", "count": 3, "status": "Pending", "progress": 0},
            {"type": "DTC History", "count": 2, "status": "Pending", "progress": 0},
            {"type": "Settings", "count": 1, "status": "Synced", "progress": 100},
        ]
        self._update_queue_table()
    
    def _update_queue_table(self) -> None:
        """Update sync queue table."""
        self.queue_table.setRowCount(len(self._pending_items))
        
        for row, item in enumerate(self._pending_items):
            # Type
            table_item = QTableWidgetItem(item["type"])
            table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.queue_table.setItem(row, 0, table_item)
            
            # Count
            table_item = QTableWidgetItem(str(item["count"]))
            table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.queue_table.setItem(row, 1, table_item)
            
            # Status
            table_item = QTableWidgetItem(item["status"])
            table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if item["status"] == "Synced":
                table_item.setForeground(QColor(PredictTheme.SUCCESS))
            elif item["status"] == "Syncing":
                table_item.setForeground(QColor(PredictTheme.WARNING))
            elif item["status"] == "Failed":
                table_item.setForeground(QColor(PredictTheme.DANGER))
            self.queue_table.setItem(row, 2, table_item)
            
            # Progress
            progress_text = f"{item['progress']}%"
            table_item = QTableWidgetItem(progress_text)
            table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.queue_table.setItem(row, 3, table_item)
        
        self.queue_table.resizeColumnsToContents()
    
    def _update_status(self) -> None:
        """Update connection status."""
        # Simulate connection check
        # In real implementation, this would check server connectivity
        pass
    
    def _sync_now(self) -> None:
        """Trigger manual sync."""
        logger.info("Manual sync triggered")
        
        # Simulate sync process
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing...")
        
        # Update queue status
        for item in self._pending_items:
            if item["status"] == "Pending":
                item["status"] = "Syncing"
        self._update_queue_table()
        
        # Simulate completion after 2 seconds
        QTimer.singleShot(2000, self._on_sync_complete)
    
    def _on_sync_complete(self) -> None:
        """Handle sync completion."""
        self._connected = True
        self._last_sync = time.time()
        
        # Update queue
        for item in self._pending_items:
            if item["status"] == "Syncing":
                item["status"] = "Synced"
                item["progress"] = 100
        
        # Update UI
        self._update_connection_status()
        self._update_queue_table()
        
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("Sync Now")
        
        logger.info("Sync completed")
    
    def _update_connection_status(self) -> None:
        """Update connection status display."""
        if self._connected:
            self.status_indicator.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-size: 24px;")
            self.status_text.setText("Connected")
            self.status_text.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
            
            if self._last_sync:
                sync_time = datetime.fromtimestamp(self._last_sync).strftime("%Y-%m-%d %H:%M:%S")
                self.last_sync_label.setText(sync_time)
        else:
            self.status_indicator.setStyleSheet(f"color: {PredictTheme.DANGER}; font-size: 24px;")
            self.status_text.setText("Disconnected")
            self.status_text.setStyleSheet(f"color: {PredictTheme.DANGER}; font-weight: bold;")
    
    def _on_auto_sync_changed(self, state: int) -> None:
        """Handle auto-sync toggle."""
        self._auto_sync = bool(state)
        logger.info(f"Auto-sync {'enabled' if self._auto_sync else 'disabled'}")
    
    def set_connected(self, connected: bool) -> None:
        """Set connection status externally."""
        self._connected = connected
        self._update_connection_status()
