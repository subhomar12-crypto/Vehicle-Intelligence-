"""
DTC (Diagnostic Trouble Code) tab.

Reads and clears diagnostic trouble codes with detail view.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QTextEdit, QMessageBox, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class DTCTab(QWidget):
    """
    Tab for reading and clearing Diagnostic Trouble Codes.
    
    Features:
    - Read DTCs from vehicle
    - Clear DTCs with confirmation
    - Color-coded severity levels
    - Freeze frame data view
    """
    
    # Severity levels with colors
    SEVERITY_COLORS = {
        "Critical": PredictTheme.DANGER,
        "High": PredictTheme.WARNING,
        "Medium": PredictTheme.ACCENT_AMBER,
        "Low": PredictTheme.INFO,
        "Info": PredictTheme.TEXT_SECONDARY,
    }
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._dtcs: List[Dict[str, Any]] = []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Diagnostic Trouble Codes")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.read_btn = QPushButton("Read DTCs")
        self.read_btn.setObjectName("primary")
        self.read_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E00000;
            }}
        """)
        self.read_btn.clicked.connect(self._read_dtcs)
        btn_layout.addWidget(self.read_btn)
        
        self.clear_btn = QPushButton("Clear DTCs")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.DANGER};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #bb2d3b;
            }}
        """)
        self.clear_btn.clicked.connect(self._clear_dtcs)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # DTC table
        self.dtc_table = QTableWidget()
        self.dtc_table.setColumnCount(5)
        self.dtc_table.setHorizontalHeaderLabels(["Code", "Description", "Severity", "System", "Status"])
        self.dtc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dtc_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dtc_table.itemSelectionChanged.connect(self._on_dtc_selected)
        self.dtc_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        splitter.addWidget(self.dtc_table)
        
        # Detail panel
        detail_group = QGroupBox("DTC Details")
        detail_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        detail_layout = QVBoxLayout(detail_group)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {PredictTheme.BG_SECONDARY};
                color: {PredictTheme.TEXT_PRIMARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        detail_layout.addWidget(self.detail_text)
        
        splitter.addWidget(detail_group)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        # Load sample data
        self._load_sample_dtcs()
    
    def _load_sample_dtcs(self) -> None:
        """Load sample DTCs for testing."""
        self._dtcs = [
            {
                "code": "P0171",
                "description": "System Too Lean (Bank 1)",
                "severity": "High",
                "system": "Fuel System",
                "status": "Confirmed",
                "freeze_frame": {
                    "Engine RPM": "2450",
                    "Vehicle Speed": "55 km/h",
                    "Coolant Temp": "92°C",
                    "Fuel Trim Bank 1": "+22%",
                    "MAF Rate": "12.5 g/s",
                },
            },
            {
                "code": "P0420",
                "description": "Catalyst System Efficiency Below Threshold",
                "severity": "Medium",
                "system": "Emissions",
                "status": "Pending",
                "freeze_frame": {
                    "Engine RPM": "1800",
                    "Vehicle Speed": "80 km/h",
                    "Coolant Temp": "95°C",
                    "O2 Sensor B1S2": "0.75V",
                },
            },
            {
                "code": "P0301",
                "description": "Cylinder 1 Misfire Detected",
                "severity": "Critical",
                "system": "Ignition",
                "status": "Confirmed",
                "freeze_frame": {
                    "Engine RPM": "1200",
                    "Vehicle Speed": "0 km/h",
                    "Coolant Temp": "88°C",
                    "Misfire Count": "45",
                },
            },
        ]
        self._update_table()
    
    def _update_table(self) -> None:
        """Update DTC table with current data."""
        self.dtc_table.setRowCount(len(self._dtcs))
        
        for row, dtc in enumerate(self._dtcs):
            # Code
            item = QTableWidgetItem(dtc["code"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.dtc_table.setItem(row, 0, item)
            
            # Description
            item = QTableWidgetItem(dtc["description"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.dtc_table.setItem(row, 1, item)
            
            # Severity with color
            severity = dtc["severity"]
            item = QTableWidgetItem(severity)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            color = self.SEVERITY_COLORS.get(severity, PredictTheme.TEXT_PRIMARY)
            item.setForeground(QColor(color))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.dtc_table.setItem(row, 2, item)
            
            # System
            item = QTableWidgetItem(dtc["system"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.dtc_table.setItem(row, 3, item)
            
            # Status
            item = QTableWidgetItem(dtc["status"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if dtc["status"] == "Confirmed":
                item.setForeground(QColor(PredictTheme.DANGER))
            elif dtc["status"] == "Pending":
                item.setForeground(QColor(PredictTheme.WARNING))
            self.dtc_table.setItem(row, 4, item)
        
        self.dtc_table.resizeColumnsToContents()
    
    def _on_dtc_selected(self) -> None:
        """Handle DTC selection."""
        selected = self.dtc_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        if row < len(self._dtcs):
            dtc = self._dtcs[row]
            self._show_dtc_details(dtc)
    
    def _show_dtc_details(self, dtc: Dict[str, Any]) -> None:
        """Show DTC details in the detail panel."""
        details = f"""
<h2>{dtc['code']}</h2>
<p><b>Description:</b> {dtc['description']}</p>
<p><b>Severity:</b> <span style='color: {self.SEVERITY_COLORS.get(dtc['severity'], PredictTheme.TEXT_PRIMARY)}'>{dtc['severity']}</span></p>
<p><b>System:</b> {dtc['system']}</p>
<p><b>Status:</b> {dtc['status']}</p>

<h3>Freeze Frame Data</h3>
<table border='0' cellpadding='5'>
"""
        
        freeze_frame = dtc.get("freeze_frame", {})
        for key, value in freeze_frame.items():
            details += f"<tr><td><b>{key}:</b></td><td>{value}</td></tr>"
        
        details += "</table>"
        
        self.detail_text.setHtml(details)
    
    def _read_dtcs(self) -> None:
        """Read DTCs from vehicle."""
        logger.info("Reading DTCs from vehicle")
        # Simulate reading
        self._load_sample_dtcs()
        QMessageBox.information(self, "DTC Read Complete", f"Found {len(self._dtcs)} trouble codes.")
    
    def _clear_dtcs(self) -> None:
        """Clear DTCs with confirmation."""
        if not self._dtcs:
            QMessageBox.information(self, "No DTCs", "No trouble codes to clear.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Clear DTCs",
            "Are you sure you want to clear all Diagnostic Trouble Codes?\n\n"
            "This will also clear the Check Engine Light.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Clearing DTCs")
            self._dtcs = []
            self._update_table()
            self.detail_text.clear()
            QMessageBox.information(self, "DTCs Cleared", "All trouble codes have been cleared.")
