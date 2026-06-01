"""
Reports tab for report generation and viewing.

Generates health reports, trip summaries, diagnostic reports, and maintenance schedules.
"""

import logging
import time
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class ReportGenerator(QThread):
    """Background thread for report generation."""
    
    progress = Signal(int)
    finished_report = Signal(dict)
    error = Signal(str)
    
    def __init__(self, report_type: str, vehicle_id: Optional[int] = None):
        super().__init__()
        self.report_type = report_type
        self.vehicle_id = vehicle_id
    
    def run(self) -> None:
        """Generate report in background."""
        try:
            # Simulate progress
            for i in range(0, 101, 10):
                time.sleep(0.2)
                self.progress.emit(i)

            # Generate report data
            current_time = time.time()
            report = {
                "id": int(current_time),
                "type": self.report_type,
                "vehicle_id": self.vehicle_id,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
                "date_unix": current_time,
                "status": "Completed",
                "file_path": f"/reports/report_{int(current_time)}.pdf",
            }
            
            self.finished_report.emit(report)
        
        except Exception as e:
            self.error.emit(str(e))


class ReportsTab(QWidget):
    """
    Tab for report generation and management.
    
    Features:
    - Report type selection (Health, Trip, Diagnostic, Maintenance)
    - Report generation with progress bar
    - List of past reports
    - View and delete report actions
    """
    
    # Report types
    REPORT_TYPES = [
        "Health Report",
        "Trip Summary",
        "Diagnostic Report",
        "Maintenance Schedule",
    ]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._reports: List[Dict[str, Any]] = []
        self._generator: Optional[ReportGenerator] = None
        self._setup_ui()
        self._load_sample_reports()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Reports")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Generation group
        gen_group = QGroupBox("Generate New Report")
        gen_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        gen_layout = QHBoxLayout(gen_group)
        
        # Report type selector
        gen_layout.addWidget(QLabel("Report Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.REPORT_TYPES)
        self.type_combo.setMinimumWidth(200)
        gen_layout.addWidget(self.type_combo)
        
        # Generate button
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.setStyleSheet(f"""
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
        self.generate_btn.clicked.connect(self._generate_report)
        gen_layout.addWidget(self.generate_btn)
        
        gen_layout.addStretch()
        layout.addWidget(gen_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PredictTheme.BG_SECONDARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 4px;
                text-align: center;
                color: {PredictTheme.TEXT_PRIMARY};
            }}
            QProgressBar::chunk {{
                background-color: {PredictTheme.PRIMARY};
                border-radius: 4px;
            }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Reports list
        reports_group = QGroupBox("Generated Reports")
        reports_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        reports_layout = QVBoxLayout(reports_group)
        
        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(5)
        self.reports_table.setHorizontalHeaderLabels(["Date", "Type", "Vehicle", "Status", "Actions"])
        self.reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reports_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        reports_layout.addWidget(self.reports_table)
        
        layout.addWidget(reports_group)
    
    def _load_sample_reports(self) -> None:
        """Load sample reports for testing."""
        current_time = time.time()
        
        self._reports = [
            {
                "id": 1,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 86400)),
                "date_unix": current_time - 86400,
                "type": "Health Report",
                "vehicle": "Toyota Camry 2020",
                "status": "Completed",
                "file_path": "/reports/health_001.pdf",
            },
            {
                "id": 2,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 172800)),
                "date_unix": current_time - 172800,
                "type": "Trip Summary",
                "vehicle": "Honda Accord 2019",
                "status": "Completed",
                "file_path": "/reports/trip_002.pdf",
            },
            {
                "id": 3,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 259200)),
                "date_unix": current_time - 259200,
                "type": "Diagnostic Report",
                "vehicle": "Toyota Camry 2020",
                "status": "Completed",
                "file_path": "/reports/diag_003.pdf",
            },
        ]
        self._update_table()
    
    def _update_table(self) -> None:
        """Update reports table."""
        self.reports_table.setRowCount(len(self._reports))
        
        for row, report in enumerate(self._reports):
            # Date
            item = QTableWidgetItem(report["date"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.reports_table.setItem(row, 0, item)
            
            # Type
            item = QTableWidgetItem(report["type"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.reports_table.setItem(row, 1, item)
            
            # Vehicle
            item = QTableWidgetItem(report["vehicle"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.reports_table.setItem(row, 2, item)
            
            # Status
            item = QTableWidgetItem(report["status"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if report["status"] == "Completed":
                item.setForeground(QColor(PredictTheme.SUCCESS))
            elif report["status"] == "Failed":
                item.setForeground(QColor(PredictTheme.DANGER))
            elif report["status"] == "Generating":
                item.setForeground(QColor(PredictTheme.WARNING))
            self.reports_table.setItem(row, 3, item)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 2, 5, 2)
            
            view_btn = QPushButton("View")
            view_btn.setFixedWidth(60)
            view_btn.clicked.connect(lambda checked, r=report: self._view_report(r))
            actions_layout.addWidget(view_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setFixedWidth(60)
            delete_btn.clicked.connect(lambda checked, rid=report["id"]: self._delete_report(rid))
            actions_layout.addWidget(delete_btn)
            
            actions_layout.addStretch()
            self.reports_table.setCellWidget(row, 4, actions_widget)
        
        self.reports_table.resizeColumnsToContents()
    
    def _generate_report(self) -> None:
        """Start report generation."""
        report_type = self.type_combo.currentText()
        logger.info(f"Generating {report_type}")
        
        # Show progress
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.generate_btn.setEnabled(False)
        
        # Start generator thread
        self._generator = ReportGenerator(report_type)
        self._generator.progress.connect(self._on_progress)
        self._generator.finished_report.connect(self._on_report_finished)
        self._generator.error.connect(self._on_report_error)
        self._generator.start()
    
    def _on_progress(self, value: int) -> None:
        """Update progress bar."""
        self.progress_bar.setValue(value)
    
    def _on_report_finished(self, report: Dict[str, Any]) -> None:
        """Handle report completion."""
        self._reports.insert(0, report)
        self._update_table()
        
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        
        QMessageBox.information(self, "Report Generated", f"Report '{report['type']}' has been generated successfully.")
    
    def _on_report_error(self, error: str) -> None:
        """Handle report error."""
        logger.error(f"Report generation failed: {error}")
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        
        QMessageBox.critical(self, "Report Failed", f"Failed to generate report:\n{error}")
    
    def _view_report(self, report: Dict[str, Any]) -> None:
        """View a generated report."""
        logger.info(f"Viewing report: {report['file_path']}")
        QMessageBox.information(self, "View Report", f"Opening report:\n{report['file_path']}")
    
    def _delete_report(self, report_id: int) -> None:
        """Delete a report."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this report?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._reports = [r for r in self._reports if r["id"] != report_id]
            self._update_table()
            logger.info(f"Deleted report {report_id}")
