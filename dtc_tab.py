"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Dtc Tab
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QMessageBox, QProgressBar, QFrame,
    QHeaderView, QTabWidget, QSplitter, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QBrush

from ui_common import ProfessionalTheme, show_error, show_info, show_question
from dtc_module import DTCManager, DTCReadThread, DTCClearThread, DTC_DATABASE

import logging

logger = logging.getLogger(__name__)


class DTCTab(QWidget):
    """
    DTC (Diagnostic Trouble Codes) Tab
    
    Shows DTC codes for the currently loaded vehicle profile only.
    Allows reading and clearing DTCs from the vehicle.
    """
    
    def __init__(self, connectivity_manager, get_active_profile: Callable,
                 ai_module=None, parent=None):
        super().__init__(parent)
        
        self.connectivity = connectivity_manager
        self.get_active_profile = get_active_profile
        self.ai_module = ai_module
        
        # DTC Manager
        self.dtc_manager = DTCManager()
        
        # Current profile
        self.current_profile_id = None
        self.current_dtcs = []
        
        # Threads
        self.read_thread = None
        self.clear_thread = None
        
        self._build_ui()
        self._update_display()
    
    def _build_ui(self):
        """Build the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = self._create_header()
        layout.addLayout(header)
        
        # Main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: DTC List
        left_widget = self._create_dtc_list_panel()
        splitter.addWidget(left_widget)
        
        # Right: Details and AI Analysis
        right_widget = self._create_details_panel()
        splitter.addWidget(right_widget)
        
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)
    
    def _create_header(self) -> QHBoxLayout:
        """Create header with title and controls"""
        header = QHBoxLayout()
        
        # Title
        title = QLabel("DTC Error Codes")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {ProfessionalTheme.TEXT_PRIMARY};
        """)
        header.addWidget(title)
        
        # Profile indicator
        self.profile_label = QLabel("No Profile Loaded")
        self.profile_label.setStyleSheet(f"""
            color: {ProfessionalTheme.TEXT_SECONDARY};
            padding: 5px 10px;
            background: {ProfessionalTheme.CARD_BG};
            border-radius: 4px;
        """)
        header.addWidget(self.profile_label)
        
        header.addStretch()
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        header.addWidget(self.progress_bar)
        
        # Buttons
        self.read_btn = QPushButton("🔍 Read DTCs")
        self.read_btn.setStyleSheet(self._get_button_style('primary'))
        self.read_btn.clicked.connect(self._read_dtcs)
        header.addWidget(self.read_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear DTCs")
        self.clear_btn.setStyleSheet(self._get_button_style('danger'))
        self.clear_btn.clicked.connect(self._clear_dtcs)
        header.addWidget(self.clear_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        self.refresh_btn.clicked.connect(self._update_display)
        header.addWidget(self.refresh_btn)
        
        return header
    
    def _create_dtc_list_panel(self) -> QWidget:
        """Create the DTC list panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Summary cards
        summary_layout = QHBoxLayout()
        
        self.active_card = self._create_summary_card("Active", "0", ProfessionalTheme.DANGER)
        self.pending_card = self._create_summary_card("Pending", "0", ProfessionalTheme.WARNING)
        self.history_card = self._create_summary_card("History", "0", ProfessionalTheme.TEXT_MUTED)
        
        summary_layout.addWidget(self.active_card)
        summary_layout.addWidget(self.pending_card)
        summary_layout.addWidget(self.history_card)
        
        layout.addLayout(summary_layout)
        
        # DTC Table
        table_group = QGroupBox("DTC Codes")
        table_layout = QVBoxLayout(table_group)
        
        self.dtc_table = QTableWidget()
        self.dtc_table.setColumnCount(5)
        self.dtc_table.setHorizontalHeaderLabels(["Code", "Description", "Severity", "System", "Status"])
        self.dtc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.dtc_table.setAlternatingRowColors(True)
        self.dtc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dtc_table.itemSelectionChanged.connect(self._on_dtc_selected)
        self._apply_table_styling(self.dtc_table)
        
        table_layout.addWidget(self.dtc_table)
        layout.addWidget(table_group, 1)
        
        # Log
        log_group = QGroupBox("Scan Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet(f"""
            font-family: 'Consolas', monospace;
            font-size: 11px;
            background-color: {ProfessionalTheme.BACKGROUND};
            color: {ProfessionalTheme.TEXT_SECONDARY};
        """)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a summary card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 12px;")
        title_label.setAlignment(Qt.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setObjectName(f"{title.lower()}_value")
        value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 700;")
        value_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card
    
    def _create_details_panel(self) -> QWidget:
        """Create the details and AI analysis panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # DTC Details
        details_group = QGroupBox("DTC Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a DTC code to view details...")
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(details_group)
        
        # AI Analysis
        ai_group = QGroupBox("AI Analysis & Recommendations")
        ai_layout = QVBoxLayout(ai_group)
        
        self.ai_analysis_text = QPlainTextEdit()
        self.ai_analysis_text.setReadOnly(True)
        self.ai_analysis_text.setPlaceholderText("AI analysis will appear here after reading DTCs...")
        ai_layout.addWidget(self.ai_analysis_text)
        
        self.analyze_btn = QPushButton("🤖 Analyze with AI")
        self.analyze_btn.setStyleSheet(self._get_button_style('info'))
        self.analyze_btn.clicked.connect(self._analyze_with_ai)
        ai_layout.addWidget(self.analyze_btn)
        
        layout.addWidget(ai_group)
        
        return widget
    
    def _log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def _update_display(self):
        """Update the display based on current profile"""
        profile = self.get_active_profile()
        
        if not profile:
            self.profile_label.setText("No Profile Loaded")
            self.profile_label.setStyleSheet(f"""
                color: {ProfessionalTheme.WARNING};
                padding: 5px 10px;
                background: {ProfessionalTheme.CARD_BG};
                border-radius: 4px;
            """)
            self.current_profile_id = None
            self.current_dtcs = []
            self._update_table([])
            return
        
        # Get profile ID
        profile_id = profile.get('profile_id') or profile.get('vin') or profile.get('name', 'unknown')
        profile_name = profile.get('name', 'Unknown Vehicle')
        
        self.profile_label.setText(f"Vehicle: {profile_name}")
        self.profile_label.setStyleSheet(f"""
            color: {ProfessionalTheme.SUCCESS};
            padding: 5px 10px;
            background: {ProfessionalTheme.CARD_BG};
            border-radius: 4px;
        """)
        
        # Load DTCs for this profile
        if profile_id != self.current_profile_id:
            self.current_profile_id = profile_id
            self.current_dtcs = self.dtc_manager.load_dtcs(profile_id)
            self._log(f"Loaded {len(self.current_dtcs)} DTCs for {profile_name}")
        
        self._update_table(self.current_dtcs)
        self._update_summary()
    
    def _update_table(self, dtcs: List[Dict]):
        """Update the DTC table"""
        self.dtc_table.setRowCount(len(dtcs))
        
        for row, dtc in enumerate(dtcs):
            # Code
            code_item = QTableWidgetItem(dtc.get('code', ''))
            code_item.setFont(QFont("Consolas", 10, QFont.Bold))
            self.dtc_table.setItem(row, 0, code_item)
            
            # Description
            desc_item = QTableWidgetItem(dtc.get('description', ''))
            self.dtc_table.setItem(row, 1, desc_item)
            
            # Severity
            severity = dtc.get('severity', 'MEDIUM')
            severity_item = QTableWidgetItem(severity)
            if severity == 'HIGH':
                severity_item.setForeground(QBrush(QColor(ProfessionalTheme.DANGER)))
            elif severity == 'MEDIUM':
                severity_item.setForeground(QBrush(QColor(ProfessionalTheme.WARNING)))
            else:
                severity_item.setForeground(QBrush(QColor(ProfessionalTheme.SUCCESS)))
            self.dtc_table.setItem(row, 2, severity_item)
            
            # System
            system_item = QTableWidgetItem(dtc.get('system', ''))
            self.dtc_table.setItem(row, 3, system_item)
            
            # Status
            status = dtc.get('status', 'ACTIVE')
            status_item = QTableWidgetItem(status)
            if status == 'ACTIVE':
                status_item.setForeground(QBrush(QColor(ProfessionalTheme.DANGER)))
            elif status == 'PENDING':
                status_item.setForeground(QBrush(QColor(ProfessionalTheme.WARNING)))
            else:
                status_item.setForeground(QBrush(QColor(ProfessionalTheme.TEXT_MUTED)))
            self.dtc_table.setItem(row, 4, status_item)
    
    def _update_summary(self):
        """Update summary cards"""
        active = len([d for d in self.current_dtcs if d.get('status') == 'ACTIVE'])
        pending = len([d for d in self.current_dtcs if d.get('status') == 'PENDING'])
        history = len([d for d in self.current_dtcs if d.get('status') == 'HISTORY'])
        
        # Update labels
        self.active_card.findChild(QLabel, "active_value").setText(str(active))
        self.pending_card.findChild(QLabel, "pending_value").setText(str(pending))
        self.history_card.findChild(QLabel, "history_value").setText(str(history))
    
    def _on_dtc_selected(self):
        """Handle DTC selection"""
        selected = self.dtc_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        if row < len(self.current_dtcs):
            dtc = self.current_dtcs[row]
            
            details = f"""
DTC Code: {dtc.get('code', 'Unknown')}
========================================

Description: {dtc.get('description', 'No description available')}

Severity: {dtc.get('severity', 'Unknown')}
System: {dtc.get('system', 'Unknown')}
Status: {dtc.get('status', 'Unknown')}

First Detected: {dtc.get('timestamp', 'Unknown')}

Possible Causes:
- Sensor malfunction
- Wiring issues
- Component failure
- Software/calibration issues

Recommended Actions:
1. Verify the DTC with a professional scan tool
2. Check related sensors and wiring
3. Inspect related components
4. Clear code and monitor for recurrence
"""
            self.details_text.setPlainText(details.strip())
    
    def _read_dtcs(self):
        """Read DTCs from vehicle"""
        profile = self.get_active_profile()
        if not profile:
            show_error(self, "No Profile", "Please load a vehicle profile first.")
            return
        
        if not getattr(self.connectivity, 'connected', False):
            show_error(self, "Not Connected", "Please connect to the vehicle first.")
            return
        
        self._log("Starting DTC scan...")
        self.read_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.read_thread = DTCReadThread(self.connectivity)
        self.read_thread.progress.connect(self._on_read_progress)
        self.read_thread.dtc_found.connect(self._on_dtc_found)
        self.read_thread.completed.connect(self._on_read_completed)
        self.read_thread.error.connect(self._on_read_error)
        self.read_thread.start()
    
    def _on_read_progress(self, value: int, message: str):
        """Handle read progress"""
        self.progress_bar.setValue(value)
        self._log(message)
    
    def _on_dtc_found(self, dtc: Dict):
        """Handle single DTC found"""
        self._log(f"Found: {dtc['code']} - {dtc['description']}")
        
        # Add to manager
        if self.current_profile_id:
            self.dtc_manager.add_dtc(self.current_profile_id, dtc)
    
    def _on_read_completed(self, dtcs: List[Dict]):
        """Handle read completion"""
        self.progress_bar.setVisible(False)
        self.read_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        self._log(f"Scan complete! Found {len(dtcs)} DTC codes.")
        
        # Update display
        if self.current_profile_id:
            self.current_dtcs = self.dtc_manager.load_dtcs(self.current_profile_id)
        else:
            self.current_dtcs = dtcs
        
        self._update_table(self.current_dtcs)
        self._update_summary()
        
        if dtcs:
            show_info(self, "Scan Complete", f"Found {len(dtcs)} DTC codes.")
        else:
            show_info(self, "Scan Complete", "No DTC codes found. Vehicle is healthy!")
    
    def _on_read_error(self, error: str):
        """Handle read error"""
        self.progress_bar.setVisible(False)
        self.read_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        self._log(f"Error: {error}")
        show_error(self, "Scan Error", error)
    
    def _clear_dtcs(self):
        """Clear DTCs from vehicle"""
        profile = self.get_active_profile()
        if not profile:
            show_error(self, "No Profile", "Please load a vehicle profile first.")
            return
        
        if not getattr(self.connectivity, 'connected', False):
            show_error(self, "Not Connected", "Please connect to the vehicle first.")
            return
        
        # Confirm
        result = show_question(
            self, "Clear DTCs",
            "Are you sure you want to clear all DTC codes from the vehicle?\n\n"
            "Note: This will turn off the Check Engine Light. The codes may return "
            "if the underlying issue is not resolved."
        )
        
        if result != QMessageBox.Yes:
            return
        
        self._log("Clearing DTCs...")
        self.read_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        self.clear_thread = DTCClearThread(self.connectivity)
        self.clear_thread.progress.connect(self._on_clear_progress)
        self.clear_thread.completed.connect(self._on_clear_completed)
        self.clear_thread.start()
    
    def _on_clear_progress(self, value: int, message: str):
        """Handle clear progress"""
        self.progress_bar.setValue(value)
        self._log(message)
    
    def _on_clear_completed(self, success: bool, message: str):
        """Handle clear completion"""
        self.progress_bar.setVisible(False)
        self.read_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        self._log(message)
        
        if success:
            # Mark DTCs as cleared in storage
            if self.current_profile_id:
                self.dtc_manager.clear_dtcs(self.current_profile_id)
                self.current_dtcs = self.dtc_manager.load_dtcs(self.current_profile_id)
            
            self._update_table(self.current_dtcs)
            self._update_summary()
            
            show_info(self, "DTCs Cleared", "DTC codes have been cleared from the vehicle.")
        else:
            show_error(self, "Clear Failed", message)
    
    def _analyze_with_ai(self):
        """Analyze DTCs with AI"""
        if not self.current_dtcs:
            show_info(self, "No DTCs", "No DTC codes to analyze. Read DTCs from vehicle first.")
            return
        
        active_dtcs = [d for d in self.current_dtcs if d.get('status') in ['ACTIVE', 'PENDING']]
        
        if not active_dtcs:
            show_info(self, "No Active DTCs", "No active DTC codes to analyze.")
            return
        
        self._log("Analyzing DTCs with AI...")
        
        # Build analysis
        analysis_lines = ["🤖 AI ANALYSIS OF DTC CODES", "=" * 40, ""]
        
        # Summary
        high_count = len([d for d in active_dtcs if d.get('severity') == 'HIGH'])
        medium_count = len([d for d in active_dtcs if d.get('severity') == 'MEDIUM'])
        
        analysis_lines.append(f"📊 SUMMARY")
        analysis_lines.append(f"• Total Active Codes: {len(active_dtcs)}")
        analysis_lines.append(f"• High Severity: {high_count}")
        analysis_lines.append(f"• Medium Severity: {medium_count}")
        analysis_lines.append("")
        
        # Priority actions
        analysis_lines.append("🚨 PRIORITY ACTIONS")
        
        if high_count > 0:
            analysis_lines.append("• URGENT: High severity codes detected!")
            analysis_lines.append("• Recommend immediate professional inspection")
        
        # Analyze by system
        systems = {}
        for dtc in active_dtcs:
            system = dtc.get('system', 'Unknown')
            if system not in systems:
                systems[system] = []
            systems[system].append(dtc)
        
        analysis_lines.append("")
        analysis_lines.append("🔧 SYSTEM ANALYSIS")
        
        for system, dtcs in systems.items():
            analysis_lines.append(f"\n{system} System ({len(dtcs)} codes):")
            for dtc in dtcs[:3]:  # Show first 3
                analysis_lines.append(f"  • {dtc['code']}: {dtc['description']}")
            if len(dtcs) > 3:
                analysis_lines.append(f"  ... and {len(dtcs) - 3} more")
        
        # Recommendations
        analysis_lines.append("")
        analysis_lines.append("💡 RECOMMENDATIONS")
        
        if 'Emissions' in systems:
            analysis_lines.append("• Check O2 sensors and catalytic converter")
        if 'Ignition' in systems:
            analysis_lines.append("• Inspect spark plugs and ignition coils")
        if 'Fuel' in systems:
            analysis_lines.append("• Check fuel system pressure and injectors")
        if 'Cooling' in systems:
            analysis_lines.append("• Inspect coolant level and thermostat")
        
        analysis_lines.append("")
        analysis_lines.append("• Clear codes after repairs and monitor for recurrence")
        analysis_lines.append("• Consider professional diagnostic if issues persist")
        
        self.ai_analysis_text.setPlainText("\n".join(analysis_lines))
        self._log("AI analysis complete")
    
    def on_profile_changed(self, profile: Dict):
        """Handle profile change notification"""
        self._update_display()
    
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
    
    def get_dtc_codes_for_ai(self) -> List[Dict]:
        """Get current DTCs for AI module integration"""
        return [d for d in self.current_dtcs if d.get('status') in ['ACTIVE', 'PENDING']]
