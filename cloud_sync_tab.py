"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Cloud Sync Tab
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QPlainTextEdit, QHBoxLayout
from PySide6.QtGui import QFont

from ui_common import show_error
from cloud_sync import CloudSyncManager


class CloudSyncTab(QWidget):
    """
    Cloud Sync tab.
    
    Uses CloudSyncManager for synchronization functionality.
    """

    def __init__(self, cloud_sync: CloudSyncManager, parent=None):
        super().__init__(parent)
        self.cloud_sync = cloud_sync
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Cloud Sync")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        btn_row = QHBoxLayout()
        self.btn_sync = QPushButton("Sync Now")
        self.btn_sync.setStyleSheet(self._get_button_style('primary'))
        self.btn_sync.clicked.connect(self.sync_now)
        self.btn_status = QPushButton("Check Status")
        self.btn_status.setStyleSheet(self._get_button_style('secondary'))
        self.btn_status.clicked.connect(self.check_status)
        btn_row.addWidget(self.btn_sync)
        btn_row.addWidget(self.btn_status)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addStretch(1)

    def sync_now(self):
        try:
            # Replace with your real sync logic
            result = self.cloud_sync.sync_now() if hasattr(self.cloud_sync, "sync_now") else "sync_now() not implemented"
            self.log.appendPlainText(f"Sync result: {result}")
        except Exception as e:
            show_error(self, "Cloud Sync Error", str(e))

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

    def check_status(self):
        try:
            status = self.cloud_sync.get_status() if hasattr(self.cloud_sync, "get_status") else "get_status() not implemented"
            self.log.appendPlainText(f"Status: {status}")
        except Exception as e:
            show_error(self, "Cloud Status Error", str(e))
