"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Recall Alerts Tab
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QMessageBox, QFrame, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from nhtsa_recall_api import RecallChecker, get_recall_checker
    RECALL_CHECKER_AVAILABLE = True
except ImportError:
    RECALL_CHECKER_AVAILABLE = False

logger = logging.getLogger(__name__)


class VINLookupDialog(QDialog):
    """Dialog for VIN lookup"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VIN Lookup")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog { background-color: #0D1117; }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px;
            }
        """)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        # VIN input
        self.vin_edit = QLineEdit()
        self.vin_edit.setPlaceholderText("Enter 17-character VIN")
        self.vin_edit.setMaxLength(17)
        self.vin_edit.textChanged.connect(self._validate_vin)
        form.addRow("VIN:", self.vin_edit)

        layout.addLayout(form)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8B949E; font-size: 11px; padding: 8px;")
        layout.addWidget(self.status_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Lookup | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_vin(self, text: str):
        """Validate VIN format"""
        vin = text.strip().upper()
        if len(vin) == 17 and vin.isalnum():
            self.status_label.setText("✓ Valid VIN format")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 8px;")
        elif len(vin) == 17:
            self.status_label.setText("✗ VIN must be alphanumeric")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px; padding: 8px;")
        else:
            self.status_label.setText("✗ VIN must be 17 characters")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px; padding: 8px;")

    def get_vin(self) -> str:
        """Get VIN from input"""
        return self.vin_edit.text().strip().upper()


class RecallAlertsTab(QWidget):
    """
    Recall Alerts Tab - Monitor NHTSA vehicle recalls
    """

    def __init__(self, recall_checker=None, parent=None):
        super().__init__(parent)
        
        # Initialize recall checker backend
        if recall_checker:
            self.recall_checker = recall_checker
        elif RECALL_CHECKER_AVAILABLE:
            try:
                self.recall_checker = get_recall_checker()
            except Exception as e:
                logger.warning(f"Could not initialize RecallChecker: {e}")
                self.recall_checker = None
        else:
            self.recall_checker = None
        
        self.recalls = []
        self.checked_vins = []

        self._setup_ui()
        self._load_recalls()

    def _setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # VIN lookup form
        vin_group = QGroupBox("Check Vehicle for Recalls")
        vin_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        vin_layout = QVBoxLayout(vin_group)

        vin_form = QFormLayout()
        vin_form.setSpacing(12)

        self.vin_edit = QLineEdit()
        self.vin_edit.setPlaceholderText("Enter 17-character VIN")
        self.vin_edit.setMaxLength(17)
        vin_form.addRow("VIN:", self.vin_edit)

        lookup_btn = QPushButton("Check Recalls")
        lookup_btn.setStyleSheet(self._get_button_style('primary'))
        lookup_btn.clicked.connect(self._lookup_recalls)
        vin_layout.addLayout(vin_form)
        vin_layout.addWidget(lookup_btn)
        layout.addWidget(vin_group)

        # Active recalls table
        recalls_group = QGroupBox("Active Recalls")
        recalls_group.setStyleSheet("""
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
            }
        """)
        recalls_layout = QVBoxLayout(recalls_group)

        self.recalls_table = QTableWidget()
        self.recalls_table.setColumnCount(6)
        self.recalls_table.setHorizontalHeaderLabels([
            "Campaign", "Description", "Severity", "Status", "Actions"
        ])
        self._apply_table_style(self.recalls_table)
        recalls_layout.addWidget(self.recalls_table)

        layout.addWidget(recalls_group)

        # NHTSA integration status
        status_layout = QHBoxLayout()
        status_layout.addWidget(self._create_status_card("NHTSA Status", "Connected", "nhtsa_status"))
        status_layout.addWidget(self._create_status_card("Checked VINs", "0", "checked_vins"))
        layout.addLayout(status_layout)

        self.setStyleSheet("background-color: #0D1117;")

    def _create_header(self) -> QWidget:
        """Create header with title and actions"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Recall Alerts")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(title)

        layout.addStretch()

        return widget

    def _create_status_card(self, title: str, value: str, attr_name: str) -> QFrame:
        """Create a status card"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("color: #F0F6FC; font-size: 24px; font-weight: bold;")
        value_label.setObjectName(attr_name)
        setattr(self, f"{attr_name}_label", value_label)
        layout.addWidget(value_label)

        return card

    def _apply_table_style(self, table: QTableWidget):
        """Apply dark theme to table"""
        table.setStyleSheet("""
            QTableWidget {
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 8px;
                gridline-color: #30363D;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #C40000; }
            QHeaderView::section {
                background-color: #21262D;
                color: #F0F6FC;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
            }
        """)

    def _get_button_style(self, style_type: str) -> str:
        """Get button stylesheet"""
        if style_type == 'primary':
            return """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
            """
        return ""

    def _load_recalls(self):
        """Load recalls from backend"""
        if self.recall_checker:
            try:
                # Get current vehicle profile to get VIN
                profile = self._get_current_profile()
                if profile:
                    vin = profile.get('vin', '')
                    make = profile.get('make', None)
                    model = profile.get('model', None)
                    year = profile.get('year', None)
                else:
                    logger.warning("No active vehicle profile found")
                    vin = ''
                    make = None
                    model = None
                    year = None
                
                # Get recalls from backend
                self.recalls = self.recall_checker.get_active_recalls(
                    vin=vin,
                    make=make,
                    model=model,
                    year=year
                )
                
                # Get checked VINs
                self.checked_vins = self.recall_checker.get_checked_vins()
                
                logger.info(f"Loaded {len(self.recalls)} recalls from backend")
            except Exception as e:
                logger.error(f"Error loading recalls: {e}")
                self.recalls = []
                self.checked_vins = []
        else:
            # No backend available - show empty data
            self.recalls = []
            self.checked_vins = []

        self._update_recalls_table()
        self._update_status_cards()
    
    def _get_current_profile(self):
        """Get current vehicle profile from parent window"""
        try:
            # Try to get from parent window
            parent = self.parent()
            while parent:
                if hasattr(parent, 'current_profile') and parent.current_profile:
                    return parent.current_profile
                if hasattr(parent, 'vehicle_manager') and parent.vehicle_manager:
                    # Get active profile from manager
                    active_profile = parent.vehicle_manager.get_active_profile()
                    if active_profile:
                        return active_profile
                parent = parent.parent() if hasattr(parent, 'parent') else None
        except Exception as e:
            logger.debug(f"Could not get current profile: {e}")
        return None

    def _update_recalls_table(self):
        """Update recalls table"""
        self.recalls_table.setRowCount(0)

        for recall in self.recalls:
            row = self.recalls_table.rowCount()
            self.recalls_table.insertRow(row)

            self.recalls_table.setItem(row, 0, QTableWidgetItem(recall.get('campaign', '')))
            self.recalls_table.setItem(row, 1, QTableWidgetItem(recall.get('description', '')))

            severity = recall.get('severity', '')
            severity_item = QTableWidgetItem(severity.title())
            if severity == 'HIGH':
                severity_item.setForeground(QColor("#F44336"))
            elif severity == 'MEDIUM':
                severity_item.setForeground(QColor("#FF9800"))
            else:
                severity_item.setForeground(QColor("#4CAF50"))
            self.recalls_table.setItem(row, 2, severity_item)

            status = recall.get('status', '')
            status_item = QTableWidgetItem(status.capitalize())
            if status == 'active':
                status_item.setForeground(QColor("#F44336"))
            else:
                status_item.setForeground(QColor("#4CAF50"))
            self.recalls_table.setItem(row, 3, status_item)

            # Add action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            view_btn = QPushButton("View")
            view_btn.setStyleSheet(self._get_button_style('secondary'))
            view_btn.clicked.connect(lambda: self._view_recall(row))

            complete_btn = QPushButton("Mark Complete")
            complete_btn.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 4px;")
            complete_btn.clicked.connect(lambda: self._mark_complete(row))

            actions_layout.addWidget(view_btn)
            actions_layout.addWidget(complete_btn)
            self.recalls_table.setCellWidget(row, 4, actions_widget)

        self.recalls_table.resizeColumnsToContents()

    def _update_status_cards(self):
        """Update status cards"""
        nhtsa_status = "Connected" if self.recall_checker and RECALL_CHECKER_AVAILABLE else "Not Available"
        self.nhtsa_status_label.setText(nhtsa_status)

        checked_count = len(self.checked_vins)
        self.checked_vins_label.setText(str(checked_count))

    def _lookup_recalls(self):
        """Lookup recalls for VIN"""
        vin = self.vin_edit.text().strip().upper()

        if len(vin) != 17:
            QMessageBox.warning(self, "Invalid VIN", "VIN must be 17 characters")
            return

        # Check if backend available
        if not self.recall_checker:
            QMessageBox.warning(self, "Error", "Recall checker not available")
            return

        # Check if already looked up
        if vin in self.checked_vins:
            QMessageBox.information(self, "Already Checked", f"VIN {vin} has already been checked")
            return

        # Add to checked list
        self.checked_vins.append(vin)

        # Query NHTSA API
        self._query_nhtsa_api(vin)

    def _query_nhtsa_api(self, vin: str):
        """Query NHTSA API for recalls"""
        try:
            # Show loading indicator
            QMessageBox.information(self, "NHTSA Lookup", f"Querying NHTSA database for VIN {vin}...")

            # Get current vehicle profile for additional context
            profile = self._get_current_profile()
            make = profile.get('make', None) if profile else None
            model = profile.get('model', None) if profile else None
            year = profile.get('year', None) if profile else None

            # Query NHTSA API
            recalls = self.recall_checker.check_recalls(
                vin=vin,
                make=make,
                model=model,
                year=year
            )

            # Add new recalls to list
            self.recalls.extend(recalls)

            # Update display
            self._update_recalls_table()
            self._update_status_cards()

            # Show results
            if recalls:
                QMessageBox.information(
                    self, "Recalls Found",
                    f"Found {len(recalls)} recall(s) for VIN {vin}"
                )
            else:
                QMessageBox.information(
                    self, "No Recalls",
                    f"No active recalls found for your vehicle"
                )

        except Exception as e:
            logger.error(f"Error querying NHTSA API: {e}")
            QMessageBox.critical(
                self, "Error",
                f"Failed to query NHTSA API: {e}"
            )

    def _view_recall(self, row: int):
        """View recall details"""
        if row < len(self.recalls):
            recall = self.recalls[row]
            QMessageBox.information(
                self,
                f"Recall Details: {recall.get('campaign', '')}",
                f"Campaign: {recall.get('campaign', '')}\n"
                f"Description: {recall.get('description', '')}\n"
                f"Severity: {recall.get('severity', '')}\n"
                f"Status: {recall.get('status', '')}"
            )

    def _mark_complete(self, row: int):
        """Mark recall as completed"""
        if row < len(self.recalls):
            recall = self.recalls[row]
            campaign = recall.get('campaign', '')
            
            reply = QMessageBox.question(
                self,
                "Mark as Complete",
                f"Are you sure you want to mark recall '{campaign}' as complete?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes and self.recall_checker:
                # Mark recall as complete in backend
                success = self.recall_checker.mark_recall_complete(
                    vin=recall.get('vin', ''),
                    campaign=campaign
                )
                
                if success:
                    recall['status'] = 'completed'
                    self._update_recalls_table()
                    QMessageBox.information(self, "Recall Updated", f"Recall '{campaign}' marked as complete!")
                else:
                    QMessageBox.warning(self, "Error", "Failed to mark recall as complete")
            elif reply == QMessageBox.Yes:
                # Fallback: update local state only
                recall['status'] = 'completed'
                self._update_recalls_table()
                QMessageBox.information(self, "Recall Updated", f"Recall '{campaign}' marked as complete!")
