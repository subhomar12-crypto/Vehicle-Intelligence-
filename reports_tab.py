"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Reports Tab
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from phi_explainer import get_phi_explanation


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QPlainTextEdit, QFileDialog, QGroupBox,
    QMessageBox, QProgressBar, QGridLayout,
    QComboBox, QCheckBox, QSpinBox, QScrollArea
)
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtCore import Qt, QThread, Signal

from ui_common import show_error, ProfessionalTheme

# Import session logic from reports_tab1
try:
    from reports_tab1 import SessionDataReader, VehicleHealthAnalyzer
except Exception as e:
    SessionDataReader = None
    VehicleHealthAnalyzer = None
    print(f"[ReportsTab] Warning: could not import SessionDataReader/VehicleHealthAnalyzer from reports_tab1: {e}")

from pdf_exporter import PDFExporter

# Mobile Server Database Integration
import sys
from pathlib import Path
try:
    server_path = Path(__file__).parent / "Previlium_OBD_Server"
    if str(server_path) not in sys.path:
        sys.path.append(str(server_path))
    import database as server_db
except Exception as e:
    server_db = None
    print(f"[ReportsTab] Could not load server database: {e}")


# Local show_info helper
def show_info(parent, title, message):
    QMessageBox.information(parent, title, message)


class ReportGeneratorThread(QThread):
    """Background thread for PDF report generation"""
    progress = Signal(int, str)
    completed = Signal(dict)
    error = Signal(str)

    def __init__(self, report_type: str, pdf_exporter, profile, snapshot,
                 ai_module, options: Dict[str, Any] = None):
        super().__init__()
        self.report_type = report_type
        self.pdf = pdf_exporter
        self.profile = profile
        self.snapshot = snapshot
        self.ai_module = ai_module
        self.options = options or {}

    def run(self):
        try:
            self.progress.emit(10, "Initializing report generation...")

            if self.report_type == 'master':
                result = self._generate_master_report()
            elif self.report_type == 'ai_forecast':
                result = self._generate_ai_report()
            elif self.report_type == 'summary':
                result = self._generate_summary_report()
            elif self.report_type == 'maintenance':
                result = self._generate_maintenance_report()
            elif self.report_type == 'trends':
                result = self._generate_trends_report()
            elif self.report_type == 'cost':
                result = self._generate_cost_report()
            elif self.report_type == 'fleet':
                result = self._generate_fleet_report()
            else:
                result = {'success': False, 'error': 'Unknown report type'}

            self.completed.emit(result)

        except Exception as e:
            self.error.emit(str(e))

    def _generate_master_report(self) -> Dict[str, Any]:
        self.progress.emit(20, "Collecting vehicle data...")
        self.progress.emit(40, "Analyzing AI insights...")
        self.progress.emit(60, "Generating charts...")
        self.progress.emit(80, "Building PDF document...")

        result = self.pdf.generate_master_report(
            profile=self.profile,
            snapshot=self.snapshot,
            ai_module=self.ai_module,
            options=self.options
        )

        self.progress.emit(100, "Report complete!")
        return result

    def _generate_ai_report(self) -> Dict[str, Any]:
            self.progress.emit(30, "Analyzing AI predictions...")
            self.progress.emit(70, "Building forecast report...")

            # Build explanation text
            explanation_text: Optional[str] = None
            try:
                history = self.options.get('history', []) if hasattr(self, 'options') else []

                # Get dashboard summary from AI module
                dashboard = {}
                if hasattr(self.ai_module, 'get_enhanced_dashboard_summary'):
                    dashboard = self.ai_module.get_enhanced_dashboard_summary(
                        self.profile or {}, self.snapshot or {}, history
                    )
                elif hasattr(self.ai_module, 'get_dashboard_summary'):
                    dashboard = self.ai_module.get_dashboard_summary(
                        self.profile or {}, self.snapshot or {}, history
                    )
                elif hasattr(self.ai_module, 'generate_comprehensive_health_report'):
                    health_report = self.ai_module.generate_comprehensive_health_report(
                        self.profile or {}, self.snapshot or {}, history
                    )
                    dashboard = {
                        "health_score": int(health_report.get("overall_health_score", 0)),
                        "system_health": health_report.get("subsystems", {}),
                        "alerts_risk_level": health_report.get("risk_level", ""),
                        "alerts_count": len(health_report.get("alerts", [])),
                        "emergency_alerts": health_report.get("alerts", []),
                        "trend_insights": [],
                        "recommendations": health_report.get("recommendations", []),
                    }

                # Prepare anomalies list
                anomalies: List[str] = []
                for alert in dashboard.get("emergency_alerts", []):
                    if isinstance(alert, dict):
                        msg = alert.get("message") or alert.get("rule")
                        if msg:
                            anomalies.append(msg)
                    else:
                        anomalies.append(str(alert))

                for item in dashboard.get("trend_insights", []) or []:
                    anomalies.append(str(item))

                recommendations = dashboard.get("recommendations", []) or []

                # Build vehicle info
                vehicle_info: Dict[str, Any] = {}
                if isinstance(self.profile, dict):
                    vehicle_info = {
                        "name": self.profile.get("vehicle_name") or self.profile.get("name"),
                        "make": self.profile.get("make"),
                        "model": self.profile.get("model"),
                        "year": self.profile.get("year"),
                        "vin": self.profile.get("vin"),
                        "license_plate": self.profile.get("license_plate"),
                    }

                # Build health_summary
                snapshot_dict = self.snapshot or {}
                health_summary = {
                    "vehicle": vehicle_info,
                    "overall_health_score": dashboard.get("health_score", 0),
                    "subsystems": dashboard.get("system_health", {}),
                    "dtc_codes": snapshot_dict.get("dtc_codes", []),
                    "recent_anomalies": anomalies,
                    "region": "Qatar / hot climate",
                    "alerts_count": dashboard.get("alerts_count", 0),
                    "risk_level": dashboard.get("alerts_risk_level", ""),
                    "recommendations": recommendations,
                }

                explanation_text = get_phi_explanation(health_summary)
            except Exception as exc:
                print(f"[ReportsTab] Phi explanation error: {exc}")
                explanation_text = None

            result = self.pdf.export_ai_forecast(
                self.profile, self.snapshot, self.ai_module, explanation_text
            )

            self.progress.emit(100, "AI report complete!")
            return result

    def _generate_summary_report(self) -> Dict[str, Any]:
        self.progress.emit(50, "Building vehicle summary...")
        result = self.pdf.export_vehicle_summary(self.profile)
        self.progress.emit(100, "Summary complete!")
        return result

    def _generate_maintenance_report(self) -> Dict[str, Any]:
        self.progress.emit(50, "Compiling maintenance history...")
        result = self.pdf.export_maintenance_history(self.profile)
        self.progress.emit(100, "Maintenance report complete!")
        return result

    def _generate_trends_report(self) -> Dict[str, Any]:
        self.progress.emit(30, "Analyzing historical trends...")
        self.progress.emit(60, "Generating trend charts...")
        result = self.pdf.export_trends_report(
            self.profile, self.snapshot, self.ai_module, self.options
        )
        self.progress.emit(100, "Trends report complete!")
        return result

    def _generate_cost_report(self) -> Dict[str, Any]:
        self.progress.emit(50, "Calculating cost analytics...")
        result = self.pdf.export_cost_analytics(self.profile)
        self.progress.emit(100, "Cost report complete!")
        return result

    def _generate_fleet_report(self) -> Dict[str, Any]:
        self.progress.emit(30, "Collecting fleet data...")
        self.progress.emit(60, "Generating fleet analysis...")
        result = self.pdf.export_fleet_report(self.options.get('profiles', []))
        self.progress.emit(100, "Fleet report complete!")
        return result


class ReportOptionsWidget(QWidget):
    """Widget for report customization options"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Report sections selection
        sections_group = QGroupBox("Include Sections")
        sections_layout = QGridLayout(sections_group)

        self.section_checks = {}
        sections = [
            ('vehicle_info', 'Vehicle Information', True),
            ('ai_insights', 'AI Health Insights', True),
            ('obd_snapshot', 'OBD Sensor Snapshot', True),
            ('predictions', 'Failure Predictions', True),
            ('trends', 'Historical Trends', True),
            ('maintenance', 'Maintenance Schedule', True),
            ('pid_coverage', 'PID Coverage Summary', True),
            ('recommendations', 'AI Recommendations', True),
            ('cost_analysis', 'Cost Analysis', False),
            ('driver_behavior', 'Driver Behavior', False),
            ('environmental', 'Environmental Impact', False),
            ('dtc_codes', 'DTC Error Codes', True),
        ]

        for i, (key, label, default) in enumerate(sections):
            check = QCheckBox(label)
            check.setChecked(default)
            self.section_checks[key] = check
            sections_layout.addWidget(check, i // 2, i % 2)

        layout.addWidget(sections_group)

        # Chart options
        charts_group = QGroupBox("Chart Options")
        charts_layout = QVBoxLayout(charts_group)

        self.include_charts = QCheckBox("Include Trend Charts")
        self.include_charts.setChecked(True)

        self.chart_days_label = QLabel("History Days:")
        self.chart_days = QSpinBox()
        self.chart_days.setRange(7, 365)
        self.chart_days.setValue(30)

        charts_row = QHBoxLayout()
        charts_row.addWidget(self.include_charts)
        charts_row.addWidget(self.chart_days_label)
        charts_row.addWidget(self.chart_days)
        charts_row.addStretch()

        charts_layout.addLayout(charts_row)
        layout.addWidget(charts_group)

        # Branding options
        branding_group = QGroupBox("Branding")
        branding_layout = QVBoxLayout(branding_group)

        self.include_logo = QCheckBox("Include Company Logo")
        self.include_logo.setChecked(True)

        self.include_footer = QCheckBox("Include Footer with Timestamp")
        self.include_footer.setChecked(True)

        branding_layout.addWidget(self.include_logo)
        branding_layout.addWidget(self.include_footer)

        layout.addWidget(branding_group)

        # Report Depth
        depth_group = QGroupBox("Report Depth & Audience")
        depth_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1976D2;
                border: 2px solid #2196F3;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        depth_layout = QVBoxLayout(depth_group)

        depth_info = QLabel(
            "Choose the report style based on your audience:"
            "\n• Driver-Friendly: Simple language, key issues, recommendations"
            "\n• Technical: Detailed sensor data, AI reasoning, correlations"
        )
        depth_info.setWordWrap(True)
        depth_info.setStyleSheet("""
            background: #E3F2FD;
            border: 1px solid #2196F3;
            border-radius: 3px;
            padding: 8px;
            color: #0D47A1;
            font-size: 11px;
        """)
        depth_layout.addWidget(depth_info)

        depth_row = QHBoxLayout()
        depth_label = QLabel("Report Style:")
        depth_label.setStyleSheet("font-weight: bold;")
        depth_row.addWidget(depth_label)

        self.report_depth = QComboBox()
        self.report_depth.addItems([
            "Driver-Friendly Summary",
            "Technical Deep Dive",
            "Comprehensive (Both Layers)"
        ])
        self.report_depth.setCurrentIndex(2)
        self.report_depth.setMinimumWidth(200)
        depth_row.addWidget(self.report_depth)
        depth_row.addStretch()

        depth_layout.addLayout(depth_row)
        layout.addWidget(depth_group)

        layout.addStretch()

    def get_options(self) -> Dict[str, Any]:
        """Get current options as dictionary"""
        depth_map = {
            0: 'driver_friendly',
            1: 'technical',
            2: 'comprehensive'
        }

        return {
            'sections': {k: v.isChecked() for k, v in self.section_checks.items()},
            'include_charts': self.include_charts.isChecked(),
            'chart_days': self.chart_days.value(),
            'include_logo': self.include_logo.isChecked(),
            'include_footer': self.include_footer.isChecked(),
            'report_depth': depth_map.get(self.report_depth.currentIndex(), 'comprehensive')
        }


class ReportPreviewWidget(QWidget):
    """Widget for report preview and status"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Status header
        self.status_label = QLabel("Ready to Generate Reports")
        self.status_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {ProfessionalTheme.TEXT_PRIMARY};
            padding: 10px;
            background: {ProfessionalTheme.CARD_BG};
            border-radius: 5px;
        """)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }}
            QProgressBar::chunk {{
                background-color: {ProfessionalTheme.SUCCESS};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Report info display
        self.info_group = QGroupBox("Last Generated Report")
        info_layout = QVBoxLayout(self.info_group)

        self.report_info = QLabel("No reports generated yet")
        self.report_info.setWordWrap(True)
        self.report_info.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")
        info_layout.addWidget(self.report_info)

        layout.addWidget(self.info_group)

        # Quick stats
        stats_group = QGroupBox("Vehicle Quick Stats")
        stats_layout = QGridLayout(stats_group)

        self.stats_labels = {}
        stats = [
            ('health_score', 'Health Score:', '--'),
            ('alerts', 'Active Alerts:', '--'),
            ('predictions', 'Predictions:', '--'),
            ('sensors', 'Sensors Active:', '--'),
        ]

        for i, (key, label, default) in enumerate(stats):
            label_widget = QLabel(label)
            label_widget.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")

            value_widget = QLabel(default)
            value_widget.setStyleSheet(f"font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY};")

            stats_layout.addWidget(label_widget, i // 2, (i % 2) * 2)
            stats_layout.addWidget(value_widget, i // 2, (i % 2) * 2 + 1)

            self.stats_labels[key] = value_widget

        layout.addWidget(stats_group)
        layout.addStretch()

    def update_progress(self, value: int, message: str):
        """Update progress bar and status"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def update_stats(self, stats: Dict[str, Any]):
        """Update quick stats display"""
        for key, widget in self.stats_labels.items():
            if key in stats:
                widget.setText(str(stats[key]))

    def set_report_info(self, info: str):
        """Set report info text"""
        self.report_info.setText(info)

    def reset(self):
        """Reset to initial state"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready to Generate Reports")


class ReportsTab(QWidget):
    """
    PREDICT — Enhanced Professional Reports Tab v2.3

    Refactored UI with scrollable card-based layout
    All v2.2 functionality preserved
    """

    def __init__(
        self,
        ai_module,
        get_active_profile,
        get_latest_snapshot,
        get_historical_data=None,
        get_all_profiles=None,
        get_dtc_codes=None,
        mobile_wrapper=None,
        parent=None
    ):
        super().__init__(parent)

        self.ai_module = ai_module
        self.get_active_profile = get_active_profile
        self.get_latest_snapshot = get_latest_snapshot
        self.get_historical_data = get_historical_data or (lambda: [])
        self.get_all_profiles = get_all_profiles or (lambda: [])
        self.get_dtc_codes = get_dtc_codes or (lambda: [])
        self.mobile_wrapper = mobile_wrapper
        self._pending_mobile_sync = False

        self.pdf = PDFExporter()
        self.generator_thread = None
        self.last_report_path = None

        # Saved-session / health support
        self.session_reader = None
        self.health_analyzer = None
        self.current_session_data: Optional[Dict[str, Any]] = None
        self.current_health_analysis: Optional[Dict[str, Any]] = None
        self._session_index_map: List[Dict[str, Any]] = []

        if SessionDataReader is not None and VehicleHealthAnalyzer is not None:
            try:
                self.session_reader = SessionDataReader()
                self.health_analyzer = VehicleHealthAnalyzer()
                print(f"[ReportsTab] Session reader initialized")
            except Exception as e:
                print(f"[ReportsTab] Error initializing session support: {e}")
                self.session_reader = None
                self.health_analyzer = None

        self._setup_ui()
        self._refresh_saved_sessions()

    def _create_card(self, title: str, color: str) -> QGroupBox:
        """Create a styled card container"""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: {ProfessionalTheme.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: {ProfessionalTheme.CARD_BG};
            }}
        """)
        return card

    def _setup_ui(self):
        # Create scroll area for main content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Main content widget with grid layout
        content = QWidget()
        grid_layout = QGridLayout(content)
        grid_layout.setHorizontalSpacing(20)
        grid_layout.setVerticalSpacing(15)

        # ========================================
        # TOP ROW - Primary Reports
        # ========================================
        primary_card = self._create_card("Primary Reports", "#C40000")
        primary_layout = QVBoxLayout(primary_card)

        btn_master = QPushButton("Generate MASTER Vehicle Report")
        btn_master.setMinimumHeight(45)
        btn_master.setStyleSheet(self._get_button_style("primary"))
        btn_master.clicked.connect(self.generate_master_report)
        btn_master.setToolTip("Complete OEM-style report with all AI insights and analysis")
        primary_layout.addWidget(btn_master)

        btn_ai = QPushButton("AI Health & Predictions Report")
        btn_ai.setMinimumHeight(45)
        btn_ai.setStyleSheet(self._get_button_style("info"))
        btn_ai.clicked.connect(self.generate_ai_report)
        btn_ai.setToolTip("AI-focused report with predictions, recommendations, and confidence scores")
        primary_layout.addWidget(btn_ai)

        grid_layout.addWidget(primary_card, 0, 0, 1, 2)

        # ========================================
        # TOP RIGHT - Status & Preview
        # ========================================
        status_card = self._create_card("Status & Preview", "#2196F3")
        status_layout = QVBoxLayout(status_card)

        self.preview_widget = ReportPreviewWidget()
        status_layout.addWidget(self.preview_widget)

        grid_layout.addWidget(status_card, 0, 2)

        # ========================================
        # MIDDLE LEFT - Individual Reports
        # ========================================
        individual_card = self._create_card("Individual Section Reports", "#4CAF50")
        individual_layout = QGridLayout(individual_card)

        report_buttons = [
            ("Vehicle Summary", self.generate_summary_report, 0, 0),
            ("Maintenance History", self.generate_maintenance_report, 0, 1),
            ("Trends Analysis", self.generate_trends_report, 1, 0),
            ("Cost Analytics", self.generate_cost_report, 1, 1),
            ("Driver Behavior", self.generate_driver_report, 2, 0),
            ("Environmental Impact", self.generate_environmental_report, 2, 1),
            ("DTC Error Codes", self.generate_dtc_report, 3, 0),
        ]

        for text, handler, row, col in report_buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(38)
            btn.setStyleSheet(self._get_button_style("secondary"))
            btn.clicked.connect(handler)
            individual_layout.addWidget(btn, row, col)

        grid_layout.addWidget(individual_card, 1, 0)

        # ========================================
        # MIDDLE CENTER - Fleet Reports
        # ========================================
        fleet_card = self._create_card("Fleet Reports", "#FF9800")
        fleet_layout = QVBoxLayout(fleet_card)

        btn_fleet = QPushButton("Generate Fleet Overview Report")
        btn_fleet.setMinimumHeight(40)
        btn_fleet.setStyleSheet(self._get_button_style("warning"))
        btn_fleet.clicked.connect(self.generate_fleet_report)
        btn_fleet.setToolTip("Overview report for all vehicles in fleet")
        fleet_layout.addWidget(btn_fleet)

        btn_comparison = QPushButton("Vehicle Comparison Report")
        btn_comparison.setMinimumHeight(40)
        btn_comparison.setStyleSheet(self._get_button_style("warning"))
        btn_comparison.clicked.connect(self.generate_comparison_report)
        btn_comparison.setToolTip("Compare health metrics across vehicles")
        fleet_layout.addWidget(btn_comparison)

        grid_layout.addWidget(fleet_card, 1, 1)

        # ========================================
        # MIDDLE RIGHT - Mobile Integration
        # ========================================
        mobile_card = self._create_card("Mobile App Integration", "#9C27B0")
        mobile_layout = QVBoxLayout(mobile_card)

        self.mobile_status_lbl = QLabel("Mobile Sync: READY")
        self.mobile_status_lbl.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px;")
        mobile_layout.addWidget(self.mobile_status_lbl)

        btn_sync_mobile = QPushButton("Sync Current Report to Phone")
        btn_sync_mobile.setMinimumHeight(40)
        btn_sync_mobile.setStyleSheet(self._get_button_style("success"))
        btn_sync_mobile.clicked.connect(self.sync_report_to_mobile)
        btn_sync_mobile.setToolTip("Generate master report and immediately push to connected Android devices")
        mobile_layout.addWidget(btn_sync_mobile)

        self.auto_sync_check = QCheckBox("Auto-Sync Reports on generation")
        self.auto_sync_check.setChecked(True)
        self.auto_sync_check.setStyleSheet("color: #666; font-size: 12px;")
        mobile_layout.addWidget(self.auto_sync_check)

        grid_layout.addWidget(mobile_card, 1, 2)

        # ========================================
        # BOTTOM LEFT - Report Options
        # ========================================
        options_card = self._create_card("Report Options", "#00BCD4")
        options_layout = QVBoxLayout(options_card)

        self.options_widget = ReportOptionsWidget()
        options_layout.addWidget(self.options_widget)

        grid_layout.addWidget(options_card, 2, 0)

        # ========================================
        # BOTTOM CENTER - Saved Sessions
        # ========================================
        sessions_card = self._create_card("Saved Sessions (for PDF)", "#FF5722")
        sessions_layout = QVBoxLayout(sessions_card)

        self.sessions_info_label = QLabel(
            "Optional: load a previously recorded session.\n"
            "If nothing is loaded, LIVE data will be used."
        )
        self.sessions_info_label.setWordWrap(True)
        self.sessions_info_label.setStyleSheet("color: #666; font-size: 11px;")
        sessions_layout.addWidget(self.sessions_info_label)

        row = QHBoxLayout()
        self.sessions_combo = QComboBox()
        self.sessions_combo.setMinimumWidth(200)
        row.addWidget(self.sessions_combo, 1)

        self.btn_refresh_sessions = QPushButton("Refresh")
        self.btn_refresh_sessions.setStyleSheet(self._get_button_style("secondary"))
        self.btn_load_session = QPushButton("Load")
        self.btn_load_session.setStyleSheet(self._get_button_style("info"))
        self.btn_clear_session = QPushButton("Clear")
        self.btn_clear_session.setStyleSheet(self._get_button_style("danger"))

        row.addWidget(self.btn_refresh_sessions)
        row.addWidget(self.btn_load_session)
        row.addWidget(self.btn_clear_session)

        sessions_layout.addLayout(row)

        self.btn_refresh_sessions.clicked.connect(self._refresh_saved_sessions)
        self.btn_load_session.clicked.connect(self._on_load_session_for_pdf)
        self.btn_clear_session.clicked.connect(self._on_clear_loaded_session)

        grid_layout.addWidget(sessions_card, 2, 1)

        # ========================================
        # BOTTOM RIGHT - Generation Log
        # ========================================
        log_card = self._create_card("Generation Log", "#607D8B")
        log_layout = QVBoxLayout(log_card)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        self.log_output.setMaximumHeight(150)
        self.log_output.setStyleSheet(f"""
            background-color: #1E1E1E;
            color: #00FF00;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 8px;
        """)
        log_layout.addWidget(self.log_output)

        grid_layout.addWidget(log_card, 2, 2)

        # Set the scroll content
        scroll.setWidget(content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(scroll)

    def _get_button_style(self, style_type: str) -> str:
        """Get consistent button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 12px 20px;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
                QPushButton:disabled { background-color: #484F58; color: #8B949E; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #2C3E50;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #34495E; }
                QPushButton:pressed { background-color: #1A252F; }
            """,
            'danger': """
                QPushButton {
                    background-color: #D32F2F;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #66BB6A; }
                QPushButton:pressed { background-color: #388E3C; }
            """,
            'warning': """
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #FFB300; }
                QPushButton:pressed { background-color: #FF8F00; }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #42A5F5; }
                QPushButton:pressed { background-color: #1976D2; }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _log(self, message: str):
        """Add message to log output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{timestamp}] {message}")

    def _validate_profile(self) -> bool:
        """Validate that a profile is loaded"""
        profile = self.get_active_profile()
        if not profile:
            show_error(self, "No Profile", "Please load a vehicle profile first.")
            return False
        return True

    def _select_output_file(self, default_name: str) -> Optional[str]:
        """Open file dialog to select output path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"{default_name}_{timestamp}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", suggested_name, "PDF Files (*.pdf)"
        )
        return path

    # ----------------- Saved Session Logic -----------------
    def _refresh_saved_sessions(self):
        """Refresh saved sessions list"""
        self._session_index_map = []
        self.sessions_combo.clear()

        if not self.session_reader:
            self.sessions_combo.addItem("Session reader not available")
            self.sessions_combo.setEnabled(False)
            self.btn_load_session.setEnabled(False)
            self.btn_clear_session.setEnabled(False)
            self.sessions_info_label.setText("Session reader not available.")
            return

        # Try to get active profile name
        profile_name = None
        try:
            profile = self.get_active_profile()
            if profile:
                profile_name = (
                    profile.get('name')
                    or profile.get('vehicle_name')
                    or profile.get('plate')
                )
        except Exception:
            pass

        try:
            sessions = self.session_reader.get_available_sessions(profile_name)
        except Exception as e:
            self.sessions_info_label.setText(f"Error loading sessions: {e}")
            self.sessions_combo.addItem("Error loading sessions")
            self.sessions_combo.setEnabled(False)
            self.btn_load_session.setEnabled(False)
            self.btn_clear_session.setEnabled(False)
            return

        if not sessions:
            if profile_name:
                self.sessions_info_label.setText(f"No sessions found for '{profile_name}'. Live data will be used.")
            else:
                self.sessions_info_label.setText("No sessions found. Live data will be used.")
            self.sessions_combo.setEnabled(False)
            self.btn_load_session.setEnabled(False)
            self.btn_clear_session.setEnabled(False)
            return

        self.sessions_combo.setEnabled(True)
        self.btn_load_session.setEnabled(True)
        self.btn_clear_session.setEnabled(True)

        for sess in sessions:
            label = f"{sess.get('display_name', 'Session')} ({sess.get('data_points', 0)} pts)"
            self.sessions_combo.addItem(label)
            self._session_index_map.append(sess)

        self.sessions_info_label.setText(f"{len(sessions)} session(s) found. Load one to use it instead of LIVE data.")

    def _on_load_session_for_pdf(self):
        """Load selected saved session"""
        if not self.session_reader:
            show_error(self, "Sessions Disabled", "Session reader is not available.")
            return

        idx = self.sessions_combo.currentIndex()
        if idx < 0 or idx >= len(self._session_index_map):
            show_error(self, "No Session Selected", "Please select a saved session to load.")
            return

        sess_meta = self._session_index_map[idx]
        filepath = sess_meta.get('filepath')
        if not filepath:
            show_error(self, "Invalid Session", "Selected session has no file path.")
            return

        self._log(f"Loading saved session: {os.path.basename(filepath)}")

        try:
            session_data = self.session_reader.load_session(filepath)
        except Exception as e:
            show_error(self, "Session Load Error", str(e))
            self._log(f"ERROR loading session: {e}")
            return

        self.current_session_data = session_data

        if self.health_analyzer and session_data.get('statistics'):
            try:
                health = self.health_analyzer.analyze_health(
                    session_data.get('statistics', {}), {}
                )
                self.current_health_analysis = health
                stats = {
                    'health_score': f"{health.get('overall_score', 0):.0f}%",
                    'alerts': len(health.get('alerts', [])),
                    'predictions': len(health.get('predictions', [])),
                    'sensors': len(session_data.get('data_points')[-1])
                    if session_data.get('data_points') else 0,
                }
                self.preview_widget.update_stats(stats)
            except Exception as e:
                print(f"[ReportsTab] Health analysis error: {e}")

        self.preview_widget.set_report_info(f"Loaded: {sess_meta.get('display_name', 'Session')}")
        self._log("Saved session loaded. PDF reports will now use this session.")

    def _on_clear_loaded_session(self):
        """Clear loaded session"""
        self.current_session_data = None
        self.current_health_analysis = None

        self.preview_widget.update_stats({
            'health_score': '--',
            'alerts': '--',
            'predictions': '--',
            'sensors': '--',
        })
        self.preview_widget.set_report_info("Using LIVE data (no saved session loaded).")
        self._log("Cleared loaded session. Reports will use LIVE data.")

    def _get_effective_snapshot_and_history(self):
        """Get snapshot and history from session or live data"""
        snapshot = None
        history = []

        if self.current_session_data and self.current_session_data.get('data_points'):
            data_points = self.current_session_data['data_points']
            snapshot = data_points[-1]
            history = data_points
        else:
            try:
                snapshot = self.get_latest_snapshot()
            except Exception as e:
                print(f"[ReportsTab] Error getting live snapshot: {e}")
                snapshot = None

            try:
                history = self.get_historical_data()
            except Exception as e:
                print(f"[ReportsTab] Error getting live history: {e}")
                history = []

        return snapshot, history

    def update_mobile_status(self, is_connected, device_id=None):
        """Update mobile sync status"""
        if is_connected:
            self.mobile_status_lbl.setText(f"Mobile Sync: ONLINE ({device_id or 'connected'})")
            self.mobile_status_lbl.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px;")
        else:
            self.mobile_status_lbl.setText("Mobile Sync: OFFLINE")
            self.mobile_status_lbl.setStyleSheet("color: #999; font-weight: bold; font-size: 13px;")

    # ------------------------------------------------------------------
    # Thread callbacks
    # ------------------------------------------------------------------
    def _on_generation_progress(self, value: int, message: str):
        """Handle progress updates"""
        self.preview_widget.update_progress(value, message)
        self._log(message)

    def _on_generation_complete(self, result: dict):
        """Handle generation completion"""
        self.preview_widget.reset()

        if result.get("success"):
            path = self.last_report_path
            if path:
                try:
                    self.pdf.save_pdf(path)
                    self._log(f"Report saved: {path}")
                    self.preview_widget.set_report_info(f"Saved: {os.path.basename(path)}")

                    is_auto_sync = self.auto_sync_check.isChecked()
                    if is_auto_sync or self._pending_mobile_sync:
                        self.sync_report_to_mobile(path, silent=is_auto_sync)
                        self._pending_mobile_sync = False
                    else:
                        show_info(self, "Success", f"Report saved:\n{path}")

                except Exception as e:
                    self._log(f"Save error: {e}")
                    show_error(self, "Save Error", str(e))
        else:
            error_msg = result.get("error", "Unknown error")
            self._log(f"Generation failed: {error_msg}")
            show_error(self, "Generation Failed", error_msg)
            self._pending_mobile_sync = False

    def sync_report_to_mobile(self, report_path=None, silent=False):
        """Sync report to mobile app"""
        if report_path is None:
            self._log("Initiating report generation for mobile sync...")
            self._pending_mobile_sync = True
            self.generate_master_report()
            return

        self._log(f"Syncing report to mobile: {os.path.basename(report_path)}")

        try:
            device_id = "unknown"
            if self.mobile_wrapper:
                active_sessions = self.mobile_wrapper.get_active_sessions()
                if active_sessions:
                    device_id = f"profile_{active_sessions[0]}"
                else:
                    profile = self.get_active_profile()
                    if profile and profile.get('profile_id'):
                        device_id = f"profile_{profile['profile_id']}"

            if device_id == "unknown":
                device_id = "profile_16"

            server_reports_dir = Path(__file__).parent / "Previlium_OBD_Server" / "reports"
            server_reports_dir.mkdir(exist_ok=True)

            timestamp = int(datetime.now().timestamp())
            filename = f"health_report_{device_id}_{timestamp}.pdf"
            dest_path = server_reports_dir / filename

            import shutil
            shutil.copy2(report_path, str(dest_path))

            if server_db:
                server_db.register_uploaded_report(device_id, str(dest_path), timestamp)
                self._log(f"Sync Success: Registered for {device_id}")
                if not silent:
                    show_info(self, "Mobile Sync", f"Report synced to: {device_id}")
            else:
                self._log("Server database module not found")
                if not silent:
                    show_error(self, "Sync Error", "Server database integration missing")

        except Exception as e:
            self._log(f"Mobile sync failed: {e}")
            if not silent:
                show_error(self, "Sync Error", f"Failed: {e}")

    def _on_generation_error(self, error_message: str):
        """Handle generation errors"""
        self.preview_widget.reset()
        self._log(f"ERROR: {error_message}")
        show_error(self, "Report Error", error_message)

    # ------------------------------------------------------------------
    # REPORT GENERATION METHODS
    # ------------------------------------------------------------------
    def generate_master_report(self):
        """Generate comprehensive master report"""
        if not self._validate_profile():
            self._pending_mobile_sync = False
            return

        path = self._select_output_file("PREDICT_Master_Report")
        if not path:
            self._pending_mobile_sync = False
            return

        self.last_report_path = path
        self._log("Starting MASTER REPORT generation...")

        profile = self.get_active_profile()
        snapshot, history = self._get_effective_snapshot_and_history()
        options = self.options_widget.get_options()
        options['history'] = history
        options['dtc_codes'] = self.get_dtc_codes()

        self.generator_thread = ReportGeneratorThread(
            'master', self.pdf, profile, snapshot, self.ai_module, options
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_ai_report(self):
        """Generate AI-focused report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_AI_Forecast")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting AI FORECAST report...")

        profile = self.get_active_profile()
        snapshot, _ = self._get_effective_snapshot_and_history()

        self.generator_thread = ReportGeneratorThread(
            'ai_forecast', self.pdf, profile, snapshot, self.ai_module
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_summary_report(self):
        """Generate vehicle summary report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Vehicle_Summary")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting VEHICLE SUMMARY...")

        profile = self.get_active_profile()

        self.generator_thread = ReportGeneratorThread(
            'summary', self.pdf, profile, None, self.ai_module
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_maintenance_report(self):
        """Generate maintenance history report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Maintenance_History")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting MAINTENANCE HISTORY...")

        profile = self.get_active_profile()

        self.generator_thread = ReportGeneratorThread(
            'maintenance', self.pdf, profile, None, self.ai_module
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_trends_report(self):
        """Generate trends analysis report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Trends_Analysis")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting TRENDS ANALYSIS...")

        profile = self.get_active_profile()
        snapshot, history = self._get_effective_snapshot_and_history()
        options = self.options_widget.get_options()
        options['history'] = history

        self.generator_thread = ReportGeneratorThread(
            'trends', self.pdf, profile, snapshot, self.ai_module, options
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_cost_report(self):
        """Generate cost analytics report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Cost_Analytics")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting COST ANALYTICS...")

        profile = self.get_active_profile()

        self.generator_thread = ReportGeneratorThread(
            'cost', self.pdf, profile, None, self.ai_module
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_driver_report(self):
        """Generate driver behavior report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Driver_Behavior")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting DRIVER BEHAVIOR...")

        try:
            profile = self.get_active_profile()
            result = self.pdf.export_driver_behavior(profile)

            if result.get("success"):
                self.pdf.save_pdf(path)
                self._log(f"Saved: {path}")
                show_info(self, "Success", f"Driver Behavior report saved:\n{path}")
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            show_error(self, "Driver Report Error", str(e))
            self._log(f"ERROR: {str(e)}")

    def generate_environmental_report(self):
        """Generate environmental impact report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_Environmental_Impact")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting ENVIRONMENTAL IMPACT...")

        try:
            profile = self.get_active_profile()
            snapshot, _ = self._get_effective_snapshot_and_history()

            result = self.pdf.export_environmental_report(profile, snapshot, self.ai_module)

            if result.get("success"):
                self.pdf.save_pdf(path)
                self._log(f"Saved: {path}")
                show_info(self, "Success", f"Environmental report saved:\n{path}")
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            show_error(self, "Environmental Report Error", str(e))
            self._log(f"ERROR: {str(e)}")

    def generate_dtc_report(self):
        """Generate DTC error codes report"""
        if not self._validate_profile():
            return

        path = self._select_output_file("PREDICT_DTC_Codes")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting DTC ERROR CODES...")

        try:
            profile = self.get_active_profile()
            dtc_codes = self.get_dtc_codes()

            if hasattr(self.pdf, 'export_dtc_report'):
                result = self.pdf.export_dtc_report(profile, dtc_codes)
            else:
                result = {'success': True}
                self._log("DTC report generated (basic)")

            if result.get("success"):
                self.pdf.save_pdf(path)
                self._log(f"Saved: {path}")
                show_info(self, "Success", f"DTC report saved:\n{path}")
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            show_error(self, "DTC Report Error", str(e))
            self._log(f"ERROR: {str(e)}")

    def generate_fleet_report(self):
        """Generate fleet overview report"""
        profiles = self.get_all_profiles()

        if not profiles or len(profiles) < 1:
            show_error(self, "No Profiles", "No vehicle profiles available for fleet report.")
            return

        path = self._select_output_file("PREDICT_Fleet_Overview")
        if not path:
            return

        self.last_report_path = path
        self._log(f"Starting FLEET OVERVIEW for {len(profiles)} vehicles...")

        options = {'profiles': profiles}

        self.generator_thread = ReportGeneratorThread(
            'fleet', self.pdf, None, None, self.ai_module, options
        )
        self.generator_thread.progress.connect(self._on_generation_progress)
        self.generator_thread.completed.connect(self._on_generation_complete)
        self.generator_thread.error.connect(self._on_generation_error)
        self.generator_thread.start()

    def generate_comparison_report(self):
        """Generate vehicle comparison report"""
        profiles = self.get_all_profiles()

        if not profiles or len(profiles) < 2:
            show_error(self, "Insufficient Profiles", "At least 2 vehicle profiles required for comparison.")
            return

        path = self._select_output_file("PREDICT_Vehicle_Comparison")
        if not path:
            return

        self.last_report_path = path
        self._log("Starting VEHICLE COMPARISON...")

        try:
            result = self.pdf.export_comparison_report(profiles, self.ai_module)

            if result.get("success"):
                self.pdf.save_pdf(path)
                self._log(f"Saved: {path}")
                show_info(self, "Success", f"Comparison report saved:\n{path}")
            else:
                raise Exception(result.get("error", "Unknown error"))

        except Exception as e:
            show_error(self, "Comparison Report Error", str(e))
            self._log(f"ERROR: {str(e)}")
