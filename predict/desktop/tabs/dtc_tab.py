"""
DTC Management Tab - Diagnostic Trouble Code management.

Tab 5 of 6 in the PREDICT Desktop GUI.
"""

import logging
import re
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QGridLayout, QTextEdit, QMessageBox, QHeaderView,
    QProgressBar, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from predict.desktop.theme import PredictTheme, get_table_stylesheet
from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)


class DTCTab(QWidget):
    """Tab for DTC management."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._selected_user_id = None
        self._selected_vehicle_id = None
        self._selected_dtc = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Top: Search & Filter
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("User/Plate:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search user or plate...")
        self._search_input.returnPressed.connect(self._on_search)
        filter_layout.addWidget(self._search_input)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        filter_layout.addWidget(self._search_btn)

        filter_layout.addWidget(QLabel("Vehicle:"))
        self._vehicle_combo = QComboBox()
        self._vehicle_combo.currentIndexChanged.connect(self._on_vehicle_changed)
        filter_layout.addWidget(self._vehicle_combo)

        filter_layout.addWidget(QLabel("Severity:"))
        self._severity_combo = QComboBox()
        self._severity_combo.addItems(["All", "Critical", "Major", "Minor", "Info"])
        filter_layout.addWidget(self._severity_combo)

        self._active_only = QCheckBox("Active Only")
        self._active_only.setChecked(True)
        filter_layout.addWidget(self._active_only)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        filter_layout.addWidget(self._refresh_btn)

        layout.addLayout(filter_layout)

        # Middle: DTC Table
        self._dtc_table = QTableWidget()
        self._dtc_table.setColumnCount(7)
        self._dtc_table.setHorizontalHeaderLabels([
            "Code", "Description", "Severity", "Vehicle", "Status", "First Seen", "Count"
        ])
        self._dtc_table.setStyleSheet(get_table_stylesheet())
        self._dtc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._dtc_table.cellClicked.connect(self._on_dtc_selected)
        layout.addWidget(self._dtc_table)

        # Bottom: Detail Panel
        self._detail_panel = QGroupBox("DTC Details")
        self._detail_panel.setVisible(False)
        detail_layout = QHBoxLayout(self._detail_panel)

        # Left column
        left_col = QVBoxLayout()
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("Code:"), 0, 0)
        self._detail_code = QLabel()
        self._detail_code.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {PredictTheme.PRIMARY}")
        info_layout.addWidget(self._detail_code, 0, 1)

        info_layout.addWidget(QLabel("Description:"), 1, 0)
        self._detail_desc = QLabel()
        info_layout.addWidget(self._detail_desc, 1, 1)

        info_layout.addWidget(QLabel("Category:"), 2, 0)
        self._detail_category = QLabel()
        info_layout.addWidget(self._detail_category, 2, 1)

        info_layout.addWidget(QLabel("Severity:"), 3, 0)
        self._detail_severity = QLabel()
        info_layout.addWidget(self._detail_severity, 3, 1)

        left_col.addLayout(info_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self._explain_btn = QPushButton("Get AI Explanation")
        self._explain_btn.clicked.connect(self._on_get_explanation)
        self._clear_dtc_btn = QPushButton("Clear DTC")
        self._clear_dtc_btn.clicked.connect(self._on_clear_dtc)
        self._resolve_btn = QPushButton("Mark Resolved")
        self._resolve_btn.clicked.connect(self._on_mark_resolved)

        btn_layout.addWidget(self._explain_btn)
        btn_layout.addWidget(self._clear_dtc_btn)
        btn_layout.addWidget(self._resolve_btn)
        left_col.addLayout(btn_layout)

        detail_layout.addLayout(left_col)

        # Right column: AI Explanation
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("AI Explanation:"))
        self._ai_explanation = QTextEdit()
        self._ai_explanation.setReadOnly(True)
        self._ai_explanation.setPlaceholderText("Click 'Get AI Explanation' to see AI analysis")
        right_col.addWidget(self._ai_explanation)
        detail_layout.addLayout(right_col)

        layout.addWidget(self._detail_panel)

        # Forensics Panel
        self._forensics_group = QGroupBox("Root Cause Analysis")
        self._forensics_group.setVisible(False)
        self._forensics_layout = QVBoxLayout(self._forensics_group)
        
        # Scroll area for forensics content
        self._forensics_scroll = QScrollArea()
        self._forensics_scroll.setWidgetResizable(True)
        self._forensics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self._forensics_content = QWidget()
        self._forensics_content_layout = QVBoxLayout(self._forensics_content)
        self._forensics_content_layout.setSpacing(12)
        
        self._forensics_scroll.setWidget(self._forensics_content)
        self._forensics_layout.addWidget(self._forensics_scroll)
        
        layout.addWidget(self._forensics_group)

    def _on_search(self):
        """Search for user."""
        query = self._search_input.text().strip()
        if not query:
            return

        self._search_btn.setEnabled(False)
        worker = APIWorker(self._api.search_users, query, 20)
        worker.finished.connect(self._on_search_results)
        worker.error.connect(self._on_search_error)
        worker.start()

    def _on_search_results(self, result: dict):
        """Handle search results."""
        self._search_btn.setEnabled(True)
        users = result.get("users", [])

        if users:
            # Take first user
            user = users[0]
            self._selected_user_id = user.get("id")
            self._load_user_vehicles()

    def _on_search_error(self, error_msg: str):
        """Handle search error."""
        self._search_btn.setEnabled(True)
        logger.error(f"Search error: {error_msg}")

    def _load_user_vehicles(self):
        """Load vehicles for selected user."""
        if not self._selected_user_id:
            return

        worker = APIWorker(self._api.get_user_vehicles, self._selected_user_id)
        worker.finished.connect(self._on_vehicles_loaded)
        worker.start()

    def _on_vehicles_loaded(self, result: dict):
        """Handle vehicles loaded."""
        vehicles = result.get("vehicles", [])

        self._vehicle_combo.clear()
        for v in vehicles:
            name = f"{v.get('make', '')} {v.get('model', '')} ({v.get('year', '')})"
            self._vehicle_combo.addItem(name, v.get("id"))

    def _on_vehicle_changed(self, index: int):
        """Handle vehicle selection change."""
        vehicle_id = self._vehicle_combo.itemData(index)
        if vehicle_id:
            self._selected_vehicle_id = vehicle_id
            self._load_dtcs(vehicle_id)
            self._load_forensics(vehicle_id)

    def _load_dtcs(self, vehicle_id: int):
        """Load DTCs for vehicle."""
        worker = APIWorker(self._api.get_dtc_history, vehicle_id)
        worker.finished.connect(self._on_dtcs_loaded)
        worker.start()

    def _on_dtcs_loaded(self, result: dict):
        """Handle DTCs loaded."""
        dtcs = result.get("dtcs", [])

        # Filter by severity if needed
        severity_filter = self._severity_combo.currentText()
        if severity_filter != "All":
            dtcs = [d for d in dtcs if d.get("severity") == severity_filter.lower()]

        # Filter by active only
        if self._active_only.isChecked():
            dtcs = [d for d in dtcs if d.get("status") == "active"]

        self._dtc_table.setRowCount(len(dtcs))

        for i, dtc in enumerate(dtcs):
            code = dtc.get("code", "N/A")
            self._dtc_table.setItem(i, 0, QTableWidgetItem(code))
            self._dtc_table.setItem(i, 1, QTableWidgetItem(dtc.get("description", "")))

            severity = dtc.get("severity", "unknown")
            severity_item = QTableWidgetItem(severity.capitalize())
            severity_color = self._get_severity_color(severity)
            if severity_color:
                severity_item.setForeground(QColor(severity_color))
            self._dtc_table.setItem(i, 2, severity_item)

            self._dtc_table.setItem(i, 3, QTableWidgetItem(str(dtc.get("vehicle_id", ""))))
            self._dtc_table.setItem(i, 4, QTableWidgetItem(dtc.get("status", "unknown")))
            self._dtc_table.setItem(i, 5, QTableWidgetItem(
                self._format_timestamp(dtc.get("first_seen"))
            ))
            self._dtc_table.setItem(i, 6, QTableWidgetItem(str(dtc.get("count", 0))))

    def _get_severity_color(self, severity: str) -> str:
        """Get color for severity level."""
        colors = {
            "critical": PredictTheme.DANGER,
            "major": PredictTheme.WARNING,
            "minor": PredictTheme.INFO,
            "info": PredictTheme.TEXT_SECONDARY,
        }
        return colors.get(severity.lower(), PredictTheme.TEXT_PRIMARY)

    def _on_dtc_selected(self, row: int, column: int):
        """Handle DTC row selection."""
        code_item = self._dtc_table.item(row, 0)
        if not code_item:
            return

        code = code_item.text()
        desc = self._dtc_table.item(row, 1).text()
        severity = self._dtc_table.item(row, 2).text()

        self._selected_dtc = {
            "code": code,
            "description": desc,
            "severity": severity.lower(),
        }

        self._detail_code.setText(code)
        self._detail_desc.setText(desc)
        self._detail_severity.setText(severity)
        self._detail_category.setText(self._get_dtc_category(code))

        self._ai_explanation.clear()
        self._detail_panel.setVisible(True)

    def _get_dtc_category(self, code: str) -> str:
        """Get DTC category from code prefix."""
        if not code:
            return "Unknown"

        prefix = code[0].upper() if code else ""
        categories = {
            "P": "Powertrain",
            "B": "Body",
            "C": "Chassis",
            "U": "Network",
        }
        return categories.get(prefix, "Unknown")

    def _on_get_explanation(self):
        """Get AI explanation for DTC."""
        if not self._selected_dtc:
            return

        code = self._selected_dtc["code"]
        self._explain_btn.setEnabled(False)
        self._ai_explanation.setText("Analyzing...")

        worker = APIWorker(self._api.explain_dtc, code)
        worker.finished.connect(self._on_explanation_received)
        worker.error.connect(self._on_explanation_error)
        worker.start()

    def _on_explanation_received(self, result: dict):
        """Handle AI explanation received."""
        self._explain_btn.setEnabled(True)
        explanation = result.get("explanation", "No explanation available")
        self._ai_explanation.setText(explanation)

    def _on_explanation_error(self, error_msg: str):
        """Handle explanation error."""
        self._explain_btn.setEnabled(True)
        self._ai_explanation.setText(f"Error: {error_msg}")

    def _on_clear_dtc(self):
        """Clear selected DTC."""
        if not self._selected_dtc or not self._selected_vehicle_id:
            return

        code = self._selected_dtc["code"]
        reply = QMessageBox.question(
            self, "Confirm", f"Clear DTC {code}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Note: This would need the actual DTC ID
            # For now, just refresh
            self._load_dtcs(self._selected_vehicle_id)

    def _on_mark_resolved(self):
        """Mark DTC as resolved."""
        if not self._selected_dtc or not self._selected_vehicle_id:
            return

        # Refresh DTC list
        self._load_dtcs(self._selected_vehicle_id)

    def _on_refresh(self):
        """Refresh DTC list."""
        if self._selected_vehicle_id:
            self._load_dtcs(self._selected_vehicle_id)
            self._load_forensics(self._selected_vehicle_id)

    def _load_forensics(self, vehicle_id: int):
        """Load DTC forensics for vehicle."""
        worker = APIWorker(self._api.get_health_assessment, vehicle_id)
        worker.finished.connect(self._on_forensics_received)
        worker.error.connect(lambda e: logger.error(f"Forensics error: {e}"))
        worker.start()

    def _on_forensics_received(self, result: dict):
        """Handle forensics data received."""
        forensics = result.get("dtc_forensics")
        if not forensics:
            self._forensics_group.setVisible(False)
            return

        self._forensics_group.setVisible(True)

        # Clear old content
        while self._forensics_content_layout.count():
            item = self._forensics_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Summary
        if forensics.get("summary"):
            summary_label = QLabel(forensics["summary"])
            summary_label.setWordWrap(True)
            summary_label.setStyleSheet(f"font-weight: bold; color: {PredictTheme.TEXT_PRIMARY}; font-size: 14px;")
            self._forensics_content_layout.addWidget(summary_label)

        # Hypothesis cards
        hypotheses = forensics.get("root_cause_hypotheses", [])
        for hypothesis in hypotheses:
            hyp_widget = self._create_hypothesis_widget(hypothesis)
            self._forensics_content_layout.addWidget(hyp_widget)

        # Anomaly evidence table
        if forensics.get("anomaly_evidence"):
            evidence_table = self._create_evidence_table(forensics["anomaly_evidence"])
            self._forensics_content_layout.addWidget(QLabel("Anomaly Evidence:"))
            self._forensics_content_layout.addWidget(evidence_table)

        # Correlation breaks
        if forensics.get("correlation_breaks"):
            corr_widget = self._create_correlation_widget(forensics["correlation_breaks"])
            self._forensics_content_layout.addWidget(QLabel("Correlation Breaks:"))
            self._forensics_content_layout.addWidget(corr_widget)

        self._forensics_content_layout.addStretch()

    def _create_hypothesis_widget(self, hypothesis: dict) -> QGroupBox:
        """Create a hypothesis card widget."""
        group = QGroupBox()
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Component name + confidence bar
        header = QHBoxLayout()
        component = hypothesis.get("component", "Unknown")
        comp_label = QLabel(component.replace("_", " ").title())
        comp_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {PredictTheme.TEXT_PRIMARY};")
        header.addWidget(comp_label)

        confidence = hypothesis.get("confidence", 0)
        conf_bar = QProgressBar()
        conf_bar.setRange(0, 100)
        conf_bar.setValue(int(confidence * 100))
        conf_bar.setFormat(f"{int(confidence * 100)}% confidence")
        conf_bar.setMaximumWidth(200)
        header.addWidget(conf_bar)
        layout.addLayout(header)

        # Reasoning text
        if hypothesis.get("reasoning"):
            reasoning = QLabel(hypothesis["reasoning"])
            reasoning.setWordWrap(True)
            reasoning.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
            layout.addWidget(reasoning)

        # Supporting evidence
        if hypothesis.get("supporting_evidence"):
            evidence_text = "\n".join([f"• {e}" for e in hypothesis["supporting_evidence"]])
            evidence_label = QLabel(f"<b>Evidence:</b><br>{evidence_text}")
            evidence_label.setWordWrap(True)
            evidence_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
            layout.addWidget(evidence_label)

        # Causal chain
        if hypothesis.get("causal_chain"):
            chain_parts = [
                f"{c.get('component', 'Unknown').replace('_', ' ').title()} ({c.get('effect', 'N/A')})"
                for c in hypothesis["causal_chain"]
            ]
            chain_text = " → ".join(chain_parts)
            chain_label = QLabel(f"<b>Causal Chain:</b> {chain_text}")
            chain_label.setWordWrap(True)
            chain_label.setStyleSheet(f"color: {PredictTheme.INFO}; margin-top: 4px;")
            layout.addWidget(chain_label)

        # Recommended inspections
        if hypothesis.get("recommended_inspections"):
            insp_text = "\n".join([f"• {i}" for i in hypothesis["recommended_inspections"]])
            insp_label = QLabel(f"<b>Recommended Inspections:</b><br>{insp_text}")
            insp_label.setWordWrap(True)
            insp_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY}; margin-top: 4px;")
            layout.addWidget(insp_label)

        return group

    def _create_evidence_table(self, evidence_list: list) -> QTableWidget:
        """Create anomaly evidence table."""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Sensor", "Value", "Expected", "Deviation", "Severity"])
        table.setStyleSheet(get_table_stylesheet())
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        table.setRowCount(len(evidence_list))
        for i, ev in enumerate(evidence_list):
            table.setItem(i, 0, QTableWidgetItem(ev.get("sensor", "")))
            table.setItem(i, 1, QTableWidgetItem(str(ev.get("value", ""))))
            table.setItem(i, 2, QTableWidgetItem(str(ev.get("expected", ""))))
            table.setItem(i, 3, QTableWidgetItem(str(ev.get("deviation", ""))))
            
            severity = ev.get("severity", "unknown")
            severity_item = QTableWidgetItem(severity.capitalize())
            severity_color = self._get_severity_color(severity)
            if severity_color:
                severity_item.setForeground(QColor(severity_color))
            table.setItem(i, 4, severity_item)

        table.resizeColumnsToContents()
        return table

    def _create_correlation_widget(self, correlation_breaks: list) -> QGroupBox:
        """Create correlation breaks widget."""
        group = QGroupBox()
        layout = QVBoxLayout(group)

        for corr in correlation_breaks:
            sensor_a = corr.get("sensor_a", "N/A")
            sensor_b = corr.get("sensor_b", "N/A")
            baseline_r = corr.get("baseline_r", 0)
            current_r = corr.get("current_r", 0)
            delta = corr.get("delta", 0)
            severity = corr.get("severity", "unknown")

            text = f"{sensor_a} ↔ {sensor_b}: r={current_r:.2f} (baseline: {baseline_r:.2f}, Δ{delta:+.2f})"
            label = QLabel(text)
            label.setStyleSheet(f"color: {self._get_severity_color(severity)};")
            layout.addWidget(label)

        return group

    def _format_timestamp(self, ts: float) -> str:
        """Format timestamp."""
        if not ts:
            return "N/A"
        try:
            return time.strftime("%Y-%m-%d", time.localtime(ts))
        except Exception:
            return str(ts)
