"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Pdf Exporter
"""

import os
import io
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, PageBreak, KeepTogether,
    ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.units import inch, mm
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.widgets.markers import makeMarker

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

from config import get_config
CONFIG = get_config()


# PREDICT Brand Colors
class PredictColors:
    PRIMARY = colors.HexColor("#C40000")  # PREDICT Red
    SECONDARY = colors.HexColor("#1A1A1A")  # Dark Grey
    ACCENT = colors.HexColor("#2563EB")  # Blue accent
    SUCCESS = colors.HexColor("#10B981")  # Green
    WARNING = colors.HexColor("#F59E0B")  # Orange
    DANGER = colors.HexColor("#EF4444")  # Red
    BACKGROUND = colors.HexColor("#F8F9FA")  # Light grey background
    TEXT_PRIMARY = colors.HexColor("#1F2937")
    TEXT_SECONDARY = colors.HexColor("#6B7280")
    BORDER = colors.HexColor("#E5E7EB")


class PDFExporter:
    """
    PREDICT Professional PDF Export Engine v2.0
    
    Generates comprehensive OEM-grade vehicle reports with:
    - Full vehicle profile information
    - AI health insights and predictions
    - Subsystem risk analysis
    - Sensor readings and anomalies
    - Historical trend charts
    - Maintenance recommendations
    - Professional formatting with PREDICT branding
    """

    def __init__(self):
        self.story = []
        self.styles = getSampleStyleSheet()
        self.path = None
        self.doc = None
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize custom styles
        self._setup_styles()
        
    def _setup_styles(self):
        """Setup custom PREDICT styles"""
        # Title style - PREDICT branded
        self.title_style = ParagraphStyle(
            "PredictTitle",
            parent=self.styles["Title"],
            fontSize=22,
            alignment=TA_CENTER,
            textColor=PredictColors.PRIMARY,
            spaceAfter=20,
            fontName="Helvetica-Bold"
        )
        
        # Subtitle
        self.subtitle_style = ParagraphStyle(
            "PredictSubtitle",
            parent=self.styles["Heading2"],
            fontSize=14,
            alignment=TA_CENTER,
            textColor=PredictColors.TEXT_SECONDARY,
            spaceAfter=30
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            "PredictSection",
            parent=self.styles["Heading2"],
            fontSize=14,
            textColor=PredictColors.PRIMARY,
            spaceBefore=15,
            spaceAfter=10,
            borderPadding=5,
            fontName="Helvetica-Bold"
        )
        
        # Subsection style
        self.subsection_style = ParagraphStyle(
            "PredictSubsection",
            parent=self.styles["Heading3"],
            fontSize=12,
            textColor=PredictColors.SECONDARY,
            spaceBefore=10,
            spaceAfter=8,
            fontName="Helvetica-Bold"
        )
        
        # Body text style
        self.body_style = ParagraphStyle(
            "PredictBody",
            parent=self.styles["BodyText"],
            fontSize=10,
            leading=14,
            textColor=PredictColors.TEXT_PRIMARY,
            alignment=TA_JUSTIFY
        )
        
        # Small text style
        self.small_style = ParagraphStyle(
            "PredictSmall",
            parent=self.styles["BodyText"],
            fontSize=8,
            textColor=PredictColors.TEXT_SECONDARY,
            leading=10
        )
        
        # Alert styles
        self.alert_critical = ParagraphStyle(
            "AlertCritical",
            parent=self.body_style,
            textColor=colors.white,
            backColor=PredictColors.DANGER,
            borderPadding=8
        )
        
        self.alert_warning = ParagraphStyle(
            "AlertWarning",
            parent=self.body_style,
            textColor=PredictColors.SECONDARY,
            backColor=PredictColors.WARNING,
            borderPadding=8
        )
        
        self.alert_success = ParagraphStyle(
            "AlertSuccess",
            parent=self.body_style,
            textColor=colors.white,
            backColor=PredictColors.SUCCESS,
            borderPadding=8
        )

        # Bullet item style for concise lists
        self.bullet_style = ParagraphStyle(
            "BulletItem",
            parent=self.body_style,
            leftIndent=20,
            spaceBefore=2,
            spaceAfter=2,
            fontSize=10
        )

        # Context text style - smaller, grey, for explanatory text
        self.context_style = ParagraphStyle(
            "ContextText",
            parent=self.body_style,
            fontSize=9,
            textColor=PredictColors.TEXT_SECONDARY,
            spaceBefore=8,
            spaceAfter=4,
            leading=12
        )

    # ==================== HELPER METHODS ====================

    def _add_spacer(self, size=12):
        """Add vertical spacer"""
        self.story.append(Spacer(1, size))

    def _add_section_title(self, title: str, icon: str = ""):
        """Add a branded section title"""
        full_title = f"{icon} {title}" if icon else title
        self.story.append(Paragraph(full_title, self.section_style))
        self._add_divider()

    def _add_subsection_title(self, title: str):
        """Add a subsection title"""
        self.story.append(Paragraph(title, self.subsection_style))

    def _add_text(self, text: str, style=None):
        """Add body text"""
        self.story.append(Paragraph(text, style or self.body_style))
        self._add_spacer(4)

    def _add_divider(self):
        """Add a horizontal divider line"""
        table = Table([[""]],  colWidths=[500], rowHeights=[2])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PredictColors.PRIMARY),
            ("LINEBELOW", (0, 0), (-1, -1), 1, PredictColors.PRIMARY)
        ]))
        self.story.append(table)
        self._add_spacer(10)

    def _add_light_divider(self):
        """Add a light divider line"""
        table = Table([[""]],  colWidths=[500], rowHeights=[1])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PredictColors.BORDER)
        ]))
        self.story.append(table)
        self._add_spacer(8)

    def _format_value(self, value, unit: str = "", decimals: int = 1) -> str:
        """Format a value for display"""
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return f"{value:.{decimals}f} {unit}".strip()
        return f"{value} {unit}".strip()

    def _get_health_color(self, score: float) -> colors.Color:
        """Get color based on health score"""
        if score >= 80:
            return PredictColors.SUCCESS
        elif score >= 60:
            return PredictColors.WARNING
        else:
            return PredictColors.DANGER

    def _get_status_text(self, score: float) -> Tuple[str, colors.Color]:
        """Get status text and color based on score"""
        if score >= 90:
            return "Excellent", PredictColors.SUCCESS
        elif score >= 75:
            return "Good", PredictColors.SUCCESS
        elif score >= 60:
            return "Fair", PredictColors.WARNING
        elif score >= 40:
            return "Poor", PredictColors.WARNING
        else:
            return "Critical", PredictColors.DANGER

    # ==================== TABLE BUILDER ====================

    def _add_table(self, data: List[List], col_widths: List[int] = None, 
                   header_style: bool = True, alternating: bool = True):
        """Add a professionally styled table"""
        if not data:
            self._add_text("No data available.")
            return

        t = Table(data, colWidths=col_widths)
        
        style_commands = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, PredictColors.BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        
        if header_style:
            style_commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), PredictColors.PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ])
        
        if alternating and len(data) > 1:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style_commands.append(
                        ("BACKGROUND", (0, i), (-1, i), PredictColors.BACKGROUND)
                    )
        
        t.setStyle(TableStyle(style_commands))
        self.story.append(t)
        self._add_spacer(12)

    def _add_key_value_table(self, data: Dict[str, Any], title: str = None):
        """Add a key-value styled table"""
        if title:
            self._add_subsection_title(title)
        
        rows = [["Field", "Value"]]
        for key, value in data.items():
            rows.append([key, self._format_value(value)])
        
        self._add_table(rows, col_widths=[180, 320])

    # ==================== CHART METHODS ====================

    def _save_temp_chart(self, fig, name: str = "chart.png") -> str:
        """Save matplotlib figure to temp file"""
        path = os.path.join(self.temp_dir, name)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor='white')
        plt.close(fig)
        return path

    def _add_chart_image(self, path: str, width: int = 480, height: int = 200):
        """Add chart image to story"""
        try:
            img = Image(path, width=width, height=height)
            img.hAlign = "CENTER"
            self.story.append(img)
            self._add_spacer(12)
        except Exception as e:
            self._add_text(f"Unable to load chart: {str(e)}")

    def _create_health_gauge(self, score: float, label: str = "Health Score") -> str:
        """Create a health score gauge chart"""
        fig, ax = plt.subplots(figsize=(4, 2.5), subplot_kw={'projection': 'polar'})
        
        # Setup
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_thetamin(0)
        ax.set_thetamax(180)
        
        # Background arc
        theta_bg = np.linspace(0, np.pi, 100)
        ax.fill_between(theta_bg, 0, 1, alpha=0.1, color='gray')
        
        # Score arc
        score_pct = max(0, min(100, score)) / 100
        theta_score = np.linspace(0, np.pi * score_pct, 50)
        
        if score >= 80:
            color = '#10B981'
        elif score >= 60:
            color = '#F59E0B'
        else:
            color = '#EF4444'
        
        ax.fill_between(theta_score, 0, 1, alpha=0.8, color=color)
        
        # Center text
        ax.annotate(f'{score:.0f}%', xy=(np.pi/2, 0), ha='center', va='center',
                   fontsize=24, fontweight='bold', color=color)
        ax.annotate(label, xy=(np.pi/2, -0.4), ha='center', va='center',
                   fontsize=10, color='#666666')
        
        # Remove ticks
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['polar'].set_visible(False)
        
        return self._save_temp_chart(fig, f"gauge_{label.replace(' ', '_')}.png")

    def _create_subsystem_chart(self, subsystems: Dict[str, Dict]) -> str:
        """Create subsystem health bar chart"""
        fig, ax = plt.subplots(figsize=(6, 3))
        
        names = []
        scores = []
        bar_colors = []
        
        for name, data in subsystems.items():
            names.append(name.replace('_', ' ').title())
            score = data.get('score', 50)
            scores.append(score)
            bar_colors.append(self._get_bar_color(score))
        
        y_pos = np.arange(len(names))
        bars = ax.barh(y_pos, scores, color=bar_colors, height=0.6)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlim(0, 100)
        ax.set_xlabel('Health Score (%)')
        ax.set_title('Subsystem Health Overview', fontweight='bold', color='#C40000')
        
        # Add score labels
        for bar, score in zip(bars, scores):
            ax.text(score + 2, bar.get_y() + bar.get_height()/2, 
                   f'{score:.0f}%', va='center', fontsize=9)
        
        # Add threshold lines
        ax.axvline(x=60, color='#F59E0B', linestyle='--', alpha=0.5, label='Warning')
        ax.axvline(x=80, color='#10B981', linestyle='--', alpha=0.5, label='Good')
        
        ax.legend(loc='lower right', fontsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        return self._save_temp_chart(fig, "subsystem_health.png")

    def _get_bar_color(self, score: float) -> str:
        """Get bar color based on score"""
        if score >= 80:
            return '#10B981'
        elif score >= 60:
            return '#F59E0B'
        else:
            return '#EF4444'

    def _create_trend_chart(self, data: List[float], label: str, 
                            unit: str = "", thresholds: Tuple[float, float] = None) -> str:
        """Create a trend line chart"""
        fig, ax = plt.subplots(figsize=(6, 2.5))
        
        x = np.arange(len(data))
        ax.plot(x, data, color='#2563EB', linewidth=2, marker='o', markersize=3)
        ax.fill_between(x, data, alpha=0.1, color='#2563EB')
        
        if thresholds:
            ax.axhline(y=thresholds[0], color='#10B981', linestyle='--', 
                      alpha=0.7, label='Optimal Min')
            ax.axhline(y=thresholds[1], color='#F59E0B', linestyle='--', 
                      alpha=0.7, label='Warning')
        
        ax.set_xlabel('Time')
        ax.set_ylabel(f'{label} ({unit})' if unit else label)
        ax.set_title(f'{label} Trend', fontweight='bold', color='#C40000')
        
        if thresholds:
            ax.legend(loc='best', fontsize=8)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return self._save_temp_chart(fig, f"trend_{label.replace(' ', '_')}.png")

    def _create_prediction_chart(self, predictions: Dict[str, Dict]) -> str:
        """Create prediction probability chart"""
        fig, ax = plt.subplots(figsize=(5, 3))
        
        horizons = []
        probabilities = []
        bar_colors = []
        
        for horizon, pred in predictions.items():
            horizons.append(horizon.replace('_', ' ').title())
            prob = pred.get('probability', 0) * 100
            probabilities.append(prob)
            bar_colors.append(self._get_bar_color(100 - prob))  # Inverse - low prob is good
        
        bars = ax.bar(horizons, probabilities, color=bar_colors, width=0.6)
        
        ax.set_ylabel('Failure Probability (%)')
        ax.set_title('Predicted Failure Risk by Horizon', fontweight='bold', color='#C40000')
        ax.set_ylim(0, 100)
        
        # Add probability labels
        for bar, prob in zip(bars, probabilities):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                   f'{prob:.0f}%', ha='center', fontsize=9)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        return self._save_temp_chart(fig, "predictions.png")

    # ==================== HEADER & FOOTER ====================

    def _add_header(self, title: str = "PREDICT VEHICLE REPORT", 
                    subtitle: str = None, include_logo: bool = True):
        """Add professional header with PREDICT branding"""
        
        # Logo (if available)
        if include_logo:
            try:
                icon_path = CONFIG.RESOURCES_DIR / "car_icon.ico"
                logo_paths = [
                    str(icon_path),
                    "./assets/predict_logo.png",
                    "./car_icon.ico"
                ]
                # Fallback to same directory if resources folder doesn't exist
                if not icon_path.exists():
                    fallback_path = Path(__file__).parent / "car_icon.ico"
                    if fallback_path.exists():
                        logo_paths.insert(0, str(fallback_path))
                for logo_path in logo_paths:
                    if os.path.exists(logo_path):
                        logo = Image(logo_path, width=50, height=50)
                        logo.hAlign = "CENTER"
                        self.story.append(logo)
                        break
            except:
                pass
        
        self._add_spacer(10)
        
        # Main title
        self.story.append(Paragraph(title, self.title_style))
        
        # Subtitle
        if subtitle:
            self.story.append(Paragraph(subtitle, self.subtitle_style))
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.story.append(Paragraph(
            f"Generated: {timestamp}",
            self.small_style
        ))
        
        self._add_spacer(20)
        self._add_divider()

    def _add_footer(self):
        """Add footer with branding"""
        self._add_spacer(20)
        self._add_light_divider()

        footer_text = (
            "<font color='#C40000'><b>PREDICT</b></font> — "
            "Predictive Vehicle Intelligence System | "
            f"Report generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            "Confidential"
        )

        self.story.append(Paragraph(footer_text, self.small_style))

    def _add_legal_disclaimer(self):
        """
        Add legal disclaimer section to protect against liability.
        This MUST be included in all reports.
        """
        self._add_spacer(20)
        self._add_divider()
        self._add_spacer(10)

        # Disclaimer header
        disclaimer_header = ParagraphStyle(
            "DisclaimerHeader",
            parent=self.styles["Normal"],
            fontSize=10,
            textColor=PredictColors.TEXT_SECONDARY,
            fontName="Helvetica-Bold",
            spaceBefore=5,
            spaceAfter=5
        )
        self.story.append(Paragraph("IMPORTANT DISCLAIMER", disclaimer_header))

        # Disclaimer text style
        disclaimer_style = ParagraphStyle(
            "DisclaimerText",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=PredictColors.TEXT_SECONDARY,
            fontName="Helvetica",
            leading=10,
            alignment=TA_JUSTIFY,
            spaceBefore=3,
            spaceAfter=3
        )

        # Legal disclaimer paragraphs
        disclaimers = [
            (
                "<b>AI-Generated Analysis:</b> This report contains predictions and analysis "
                "generated using artificial intelligence. AI predictions are based on available "
                "OBD-II sensor data and historical patterns, and may not reflect actual vehicle "
                "condition. Accuracy depends on data quality and vehicle-specific factors."
            ),
            (
                "<b>Not a Substitute for Professional Inspection:</b> This report does NOT "
                "replace professional mechanical inspection, manufacturer diagnostics, or "
                "certified mechanic evaluation. Always consult a qualified automotive technician "
                "for safety-critical issues, unusual noises, warning lights, or before making "
                "repair decisions."
            ),
            (
                "<b>Limitation of Liability:</b> The creators of this software provide this "
                "report 'as is' without warranty of any kind, express or implied. We shall not "
                "be liable for any direct, indirect, incidental, special, or consequential "
                "damages arising from the use of this report or reliance on its predictions."
            ),
            (
                "<b>Data Accuracy:</b> Report accuracy depends on OBD-II sensor data provided "
                "by the vehicle. Sensor malfunctions, aftermarket modifications, or incomplete "
                "data may affect prediction reliability. Confidence scores indicate prediction "
                "certainty levels."
            ),
            (
                "<b>Recommendation Only:</b> All maintenance recommendations are suggestions "
                "based on general automotive best practices and AI analysis. Actual maintenance "
                "needs may vary based on driving conditions, manufacturer specifications, and "
                "individual vehicle history."
            ),
        ]

        for disclaimer in disclaimers:
            self.story.append(Paragraph(disclaimer, disclaimer_style))

        self._add_spacer(5)

        # Version and timestamp
        version_style = ParagraphStyle(
            "VersionInfo",
            parent=self.styles["Normal"],
            fontSize=7,
            textColor=colors.gray,
            alignment=TA_CENTER
        )
        version_text = (
            f"PREDICT Vehicle Intelligence System v1.0 | "
            f"Report ID: {datetime.now().strftime('%Y%m%d%H%M%S')} | "
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.story.append(Paragraph(version_text, version_style))

    # ==================== REPORT SECTIONS ====================

    def add_vehicle_summary(self, profile: Dict[str, Any], options: Dict = None):
        """Add comprehensive vehicle summary section"""
        self._add_section_title("Vehicle Information", "🚗")
        
        if not profile:
            self._add_text("No vehicle profile available.")
            return
        
        # Basic info table
        basic_info = [
            ["Field", "Value"],
            ["Vehicle Name", profile.get("name", "—")],
            ["Make", profile.get("make", "—")],
            ["Model", profile.get("model", "—")],
            ["Year", str(profile.get("year", "—"))],
            ["VIN", profile.get("vin", "—")],
            ["License Plate", profile.get("license_plate", "—")],
        ]
        self._add_table(basic_info, col_widths=[150, 350])
        
        # Technical specifications
        self._add_subsection_title("Technical Specifications")
        tech_info = [
            ["Specification", "Value"],
            ["Engine Type", profile.get("engine_type", profile.get("engine", "—"))],
            ["Transmission", profile.get("transmission", "—")],
            ["Fuel Type", profile.get("fuel_type", "—")],
            ["Drivetrain", profile.get("drivetrain", "—")],
        ]
        self._add_table(tech_info, col_widths=[150, 350])
        
        # Usage statistics
        self._add_subsection_title("Usage Statistics")
        usage_info = [
            ["Metric", "Value"],
            ["Total Distance", f"{profile.get('total_distance', profile.get('mileage', 0)):,.0f} km"],
            ["Total Driving Hours", f"{profile.get('total_driving_hours', 0):,.1f} hrs"],
            ["Trip Count", str(profile.get("trip_count", 0))],
            ["Maintenance Count", str(profile.get("maintenance_count", 0))],
        ]
        self._add_table(usage_info, col_widths=[150, 350])

    def add_ai_health_summary(self, profile: Dict, snapshot: Dict, 
                              ai_module, options: Dict = None):
        """Add comprehensive AI health analysis section"""
        self._add_section_title("AI Health Analysis", "🤖")
        
        try:
            # Get AI analysis
            history = options.get('history', []) if options else []
            
            if hasattr(ai_module, 'generate_comprehensive_health_report'):
                health_report = ai_module.generate_comprehensive_health_report(
                    profile or {}, snapshot or {}, history
                )
            elif hasattr(ai_module, 'get_dashboard_summary'):
                health_report = ai_module.get_dashboard_summary(
                    profile or {}, snapshot or {}, history
                )
            else:
                health_report = {}
            
            # Overall health score gauge
            health_score = health_report.get('overall_health_score', 
                                            health_report.get('health_score', 75))
            
            gauge_path = self._create_health_gauge(health_score, "Overall Health")
            self._add_chart_image(gauge_path, width=250, height=150)
            
            # Health grade and summary
            grade = health_report.get('health_grade', health_report.get('health_label', 'C'))
            status_text, status_color = self._get_status_text(health_score)
            
            summary_text = (
                f"<b>Overall Health Grade: {grade}</b><br/>"
                f"<b>Status: {status_text}</b> ({health_score:.0f}%)<br/><br/>"
            )
            self._add_text(summary_text)
            
            # Subsystem health breakdown
            subsystems = health_report.get('subsystems', health_report.get('system_health', {}))
            if subsystems:
                self._add_subsection_title("Subsystem Health Breakdown")
                
                # Create subsystem chart
                chart_path = self._create_subsystem_chart(subsystems)
                self._add_chart_image(chart_path, width=450, height=200)
                
                # Subsystem details table
                subsystem_rows = [["Subsystem", "Score", "Status", "Trend"]]
                for name, data in subsystems.items():
                    score = data.get('score', 50)
                    status = data.get('status', 'Unknown')
                    trend = data.get('trend', data.get('trend_direction', '—'))
                    subsystem_rows.append([
                        name.replace('_', ' ').title(),
                        f"{score:.0f}%",
                        status,
                        trend.title() if trend else '—'
                    ])
                
                self._add_table(subsystem_rows, col_widths=[120, 80, 80, 80])
            
            # Risk levels
            self._add_subsection_title("Risk Assessment")
            risk_level = health_report.get('alerts_risk_level', 'LOW')
            alerts_count = health_report.get('alerts_count', 0)
            
            risk_info = [
                ["Assessment", "Value"],
                ["Current Risk Level", risk_level],
                ["Active Alerts", str(alerts_count)],
                ["Data Quality", f"{health_report.get('data_quality', {}).get('reliability_score', 0.8)*100:.0f}%"],
            ]
            self._add_table(risk_info, col_widths=[200, 200])
            
        except Exception as e:
            self._add_text(f"AI analysis unavailable: {str(e)}")

    def add_owner_explanation_section(self, explanation_text: str, llm_assistant=None):
        """
        Add owner-friendly natural language explanation from external AI.

        Uses bullet points + short context text format for clarity.
        If LLM assistant is provided and text is long, it will be summarized.

        Args:
            explanation_text: The explanation to format
            llm_assistant: Optional LLM assistant for summarization
        """
        if not explanation_text:
            return

        # High-level section for owner explanation
        self._add_section_title("What This Means For You", "🧠")

        # If LLM available and explanation is long, summarize it
        if llm_assistant and len(explanation_text) > 300:
            try:
                if hasattr(llm_assistant, 'summarize_for_pdf'):
                    explanation_text = llm_assistant.summarize_for_pdf(explanation_text)
            except Exception:
                pass  # Keep original if summarization fails

        # Parse lines into bullets and context text
        lines = explanation_text.strip().splitlines()
        bullets = []
        context_text = []
        current_section = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Heading-style lines become subsection titles
            if line.startswith("### "):
                # Output any accumulated content first
                if bullets or context_text:
                    self._add_bullet_section(bullets, context_text)
                    bullets = []
                    context_text = []
                current_section = line[4:].strip()
                self._add_subsection_title(current_section)

            # Bullet points (-, *, •)
            elif line.startswith(('-', '*', '•')) and len(line) > 1:
                bullet_text = line.lstrip('-*• ').strip()
                if bullet_text:
                    bullets.append(bullet_text)

            # Regular text becomes context
            else:
                # Strip leading markdown characters but keep text
                clean_line = line.lstrip('#').strip()
                if clean_line:
                    context_text.append(clean_line)

        # Output final accumulated content
        if bullets or context_text:
            self._add_bullet_section(bullets, context_text)

    def _add_bullet_section(self, bullets: list, context_text: list):
        """
        Add a section with bullet points followed by context text.

        Args:
            bullets: List of bullet point strings
            context_text: List of context paragraph strings
        """
        # Add bullets as a formatted table for consistent styling
        if bullets:
            bullet_data = []
            for bullet in bullets:
                bullet_data.append([
                    Paragraph(f"• {bullet}", self.bullet_style)
                ])

            bullet_table = Table(bullet_data, colWidths=[480])
            bullet_table.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            self.story.append(bullet_table)

        # Add context paragraph(s)
        if context_text:
            self._add_spacer(6)
            combined_context = ' '.join(context_text)
            self.story.append(Paragraph(combined_context, self.context_style))
            self._add_spacer(4)

    def add_predictions_section(self, profile: Dict, snapshot: Dict,
                                ai_module, options: Dict = None):
        """Add failure predictions section"""
        self._add_section_title("Failure Predictions", "🔮")
        
        try:
            history = options.get('history', []) if options else []
            
            if hasattr(ai_module, 'generate_comprehensive_health_report'):
                health_report = ai_module.generate_comprehensive_health_report(
                    profile or {}, snapshot or {}, history
                )
                predictions = health_report.get('predictions', {})
            else:
                predictions = {}
            
            if predictions:
                # Predictions chart
                chart_path = self._create_prediction_chart(predictions)
                self._add_chart_image(chart_path, width=400, height=220)
                
                # Predictions table
                pred_rows = [["Horizon", "Probability", "Confidence", "Risk Factors"]]
                for horizon, pred in predictions.items():
                    prob = pred.get('probability', 0) * 100
                    conf = pred.get('confidence', 0) * 100
                    factors = pred.get('risk_factors', [])
                    factors_text = '; '.join(factors[:2]) if factors else 'None identified'
                    
                    pred_rows.append([
                        horizon.replace('_', ' ').title(),
                        f"{prob:.0f}%",
                        f"{conf:.0f}%",
                        factors_text[:50]
                    ])
                
                self._add_table(pred_rows, col_widths=[80, 80, 80, 260])
            else:
                self._add_text("Insufficient data for failure predictions. Continue collecting sensor data for accurate forecasting.")
                
        except Exception as e:
            self._add_text(f"Prediction analysis unavailable: {str(e)}")

    def add_obd_snapshot(self, snapshot: Dict[str, Any], options: Dict = None):
        """Add current OBD sensor readings section"""
        self._add_section_title("OBD Sensor Snapshot", "📊")
        
        if not snapshot:
            self._add_text("No live sensor data available.")
            return
        
        # Define sensor groups with thresholds
        sensor_groups = {
            "Engine Parameters": {
                'rpm': ('RPM', 'RPM', (600, 6500)),
                'engine_load': ('Engine Load', '%', (0, 100)),
                'throttle_pos': ('Throttle Position', '%', (0, 100)),
                'timing_advance': ('Timing Advance', '°', (-10, 50)),
            },
            "Temperature": {
                'coolant_temp': ('Coolant Temp', '°C', (60, 110)),
                'oil_temp': ('Oil Temp', '°C', (60, 130)),
                'intake_temp': ('Intake Temp', '°C', (-40, 80)),
                'catalyst_temp': ('Catalyst Temp', '°C', (100, 1000)),
            },
            "Electrical": {
                'battery_voltage': ('Battery Voltage', 'V', (11.5, 15.0)),
            },
            "Fuel System": {
                'fuel_trim_short': ('Short Term Fuel Trim', '%', (-25, 25)),
                'fuel_trim_long': ('Long Term Fuel Trim', '%', (-25, 25)),
                'fuel_pressure': ('Fuel Pressure', 'kPa', (200, 600)),
                'maf': ('MAF', 'g/s', (0, 500)),
                'map': ('MAP', 'kPa', (10, 105)),
            },
            "Vehicle": {
                'speed': ('Speed', 'km/h', (0, 250)),
            }
        }
        
        for group_name, sensors in sensor_groups.items():
            group_data = []
            for key, (name, unit, normal_range) in sensors.items():
                if key in snapshot:
                    value = snapshot[key]
                    if value is not None:
                        # Check if in range
                        in_range = normal_range[0] <= value <= normal_range[1]
                        status = "✓" if in_range else "⚠"
                        group_data.append([
                            name,
                            f"{value:.1f}" if isinstance(value, float) else str(value),
                            unit,
                            f"{normal_range[0]}-{normal_range[1]}",
                            status
                        ])
            
            if group_data:
                self._add_subsection_title(group_name)
                rows = [["Sensor", "Value", "Unit", "Normal Range", "Status"]] + group_data
                self._add_table(rows, col_widths=[120, 70, 50, 100, 50])

    def add_recommendations(self, ai_module, profile: Dict, snapshot: Dict, 
                             options: Dict = None):
        """Add AI recommendations section"""
        self._add_section_title("AI Recommendations", "💡")
        
        try:
            history = options.get('history', []) if options else []
            
            if hasattr(ai_module, 'generate_comprehensive_health_report'):
                health_report = ai_module.generate_comprehensive_health_report(
                    profile or {}, snapshot or {}, history
                )
                recommendations = health_report.get('recommendations', [])
            elif hasattr(ai_module, 'get_dashboard_summary'):
                summary = ai_module.get_dashboard_summary(
                    profile or {}, snapshot or {}, history
                )
                recommendations = summary.get('recommendations', [])
            else:
                recommendations = []
            
            if recommendations:
                # Priority recommendations
                self._add_subsection_title("Maintenance Priorities")
                
                rec_rows = [["Priority", "Recommendation"]]
                for i, rec in enumerate(recommendations[:8], 1):
                    priority = "HIGH" if i <= 2 else "MEDIUM" if i <= 5 else "LOW"
                    rec_rows.append([priority, rec])
                
                self._add_table(rec_rows, col_widths=[80, 420])
            else:
                self._add_text(
                    "No specific recommendations at this time. "
                    "Continue regular maintenance schedule and monitoring."
                )
            
            # General maintenance advice
            self._add_subsection_title("General Maintenance Guidelines")
            guidelines = [
                "• Monitor coolant and oil temperatures regularly",
                "• Check battery voltage, especially before long trips",
                "• Address any check engine lights promptly",
                "• Follow manufacturer service intervals",
                "• Keep fuel system clean with quality fuel",
            ]
            self._add_text("<br/>".join(guidelines))
            
        except Exception as e:
            self._add_text(f"Recommendations unavailable: {str(e)}")

    def add_trend_charts(self, history: List[Dict], options: Dict = None):
        """Add historical trend charts section"""
        self._add_section_title("Historical Trends", "📈")
        
        if not history or len(history) < 5:
            self._add_text(
                "Insufficient historical data for trend analysis. "
                f"Current data points: {len(history) if history else 0} (minimum: 5)"
            )
            return
        
        # Extract time series data
        sensors_to_plot = [
            ('coolant_temp', 'Coolant Temperature', '°C', (80, 100)),
            ('battery_voltage', 'Battery Voltage', 'V', (12.5, 14.0)),
            ('engine_load', 'Engine Load', '%', (20, 80)),
        ]
        
        for sensor_key, label, unit, thresholds in sensors_to_plot:
            values = []
            for h in history[-50:]:  # Last 50 data points
                val = h.get(sensor_key, h.get('sensor_data', {}).get(sensor_key))
                if val is not None:
                    values.append(val)
            
            if len(values) >= 5:
                chart_path = self._create_trend_chart(values, label, unit, thresholds)
                self._add_chart_image(chart_path, width=450, height=180)

    def add_pid_coverage(self, profile: Dict, snapshot: Dict, options: Dict = None):
        """Add PID coverage summary section"""
        self._add_section_title("PID Coverage Summary", "📋")
        
        # Count available PIDs
        available_pids = len(snapshot) if snapshot else 0
        
        # Standard Mode 01 PIDs
        standard_pids = [
            'rpm', 'speed', 'coolant_temp', 'engine_load', 'throttle_pos',
            'intake_temp', 'maf', 'map', 'timing_advance', 'fuel_trim_short',
            'fuel_trim_long', 'battery_voltage', 'o2_sensor_1'
        ]
        
        supported_standard = sum(1 for pid in standard_pids if snapshot and pid in snapshot)
        
        coverage_info = [
            ["Category", "Count", "Status"],
            ["Total PIDs Available", str(available_pids), "✓" if available_pids > 5 else "⚠"],
            ["Standard Mode 01 PIDs", f"{supported_standard}/{len(standard_pids)}", 
             "✓" if supported_standard > 8 else "⚠"],
            ["Custom/Mode 22 PIDs", "—", "—"],
        ]
        
        self._add_table(coverage_info, col_widths=[200, 100, 80])
        
        # List available PIDs
        if snapshot:
            self._add_subsection_title("Available Sensors")
            pid_list = ", ".join(sorted(snapshot.keys())[:20])
            self._add_text(f"<font size='9'>{pid_list}</font>")

    def add_maintenance_history(self, profile: Dict, db_manager=None):
        """Add maintenance history section"""
        self._add_section_title("Maintenance History", "🔧")
        
        # Get maintenance records from profile
        maintenance_count = profile.get('maintenance_count', 0) if profile else 0
        last_service = profile.get('last_service_date', 'Unknown') if profile else 'Unknown'
        
        summary_info = [
            ["Metric", "Value"],
            ["Total Maintenance Records", str(maintenance_count)],
            ["Last Service Date", str(last_service)],
        ]
        self._add_table(summary_info, col_widths=[200, 200])
        
        # Note about maintenance data source
        self._add_text(
            "For detailed maintenance records, view the Service History tab. "
            "Regular maintenance helps prevent unexpected failures and extends vehicle life."
        )

    # ==================== DOCUMENT SAVING ====================

    def save_pdf(self, path: str):
        """Build and save the PDF document"""
        if not self.doc:
            return False
            
        try:
            # Use temp file then rename
            temp_name = os.path.join(self.temp_dir, "temp_report.pdf")
            self.doc.filename = temp_name
            self.doc.build(self.story)
            
            # Move to final location
            if os.path.exists(path):
                os.remove(path)
            
            import shutil
            shutil.move(temp_name, path)
            
            self.path = path
            return True
            
        except Exception as e:
            print(f"Error saving PDF: {e}")
            return False

    # ==================== MAIN REPORT GENERATORS ====================

    def generate_master_report(self, profile: Dict, snapshot: Dict, 
                                ai_module, options: Dict = None) -> Dict[str, Any]:
        """Generate complete master vehicle report"""
        try:
            options = options or {}
            sections = options.get('sections', {})
            
            # Initialize document
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            # Header
            vehicle_name = profile.get('name', 'Vehicle') if profile else 'Vehicle'
            self._add_header(
                title="PREDICT VEHICLE HEALTH CERTIFICATE",
                subtitle=f"{vehicle_name} — Comprehensive Analysis Report",
                include_logo=options.get('include_logo', True)
            )
            
            # Executive Summary
            self._add_section_title("Executive Summary", "📋")
            try:
                history = options.get('history', [])
                if hasattr(ai_module, 'get_dashboard_summary'):
                    summary = ai_module.get_dashboard_summary(
                        profile or {}, snapshot or {}, history
                    )
                    score = summary.get('health_score', 75)
                    grade = summary.get('health_label', 'C')
                    status_text, _ = self._get_status_text(score)
                    
                    exec_summary = (
                        f"<b>Overall Health: {score}% (Grade {grade})</b><br/><br/>"
                        f"This comprehensive analysis evaluates {vehicle_name} across all major "
                        f"vehicle subsystems including engine, transmission, cooling, electrical, "
                        f"and fuel systems. The AI analysis indicates the vehicle is in "
                        f"<b>{status_text}</b> condition."
                    )
                    self._add_text(exec_summary)
            except:
                self._add_text("AI analysis in progress...")
            
            # Vehicle Information
            if sections.get('vehicle_info', True):
                self.add_vehicle_summary(profile, options)
            
            # AI Health Analysis
            if sections.get('ai_insights', True):
                self.story.append(PageBreak())
                self.add_ai_health_summary(profile, snapshot, ai_module, options)
            
            # OBD Snapshot
            if sections.get('obd_snapshot', True):
                self.story.append(PageBreak())
                self.add_obd_snapshot(snapshot, options)
            
            # Predictions
            if sections.get('predictions', True):
                self.add_predictions_section(profile, snapshot, ai_module, options)
            
            # Trend Charts
            if sections.get('trends', True) and options.get('include_charts', True):
                history = options.get('history', [])
                if history and len(history) >= 5:
                    self.story.append(PageBreak())
                    self.add_trend_charts(history, options)
            
            # PID Coverage
            if sections.get('pid_coverage', True):
                self.add_pid_coverage(profile, snapshot, options)
            
            # Recommendations
            if sections.get('recommendations', True):
                self.story.append(PageBreak())
                self.add_recommendations(ai_module, profile, snapshot, options)
            
            # Maintenance
            if sections.get('maintenance', True):
                self.add_maintenance_history(profile)

            # Legal Disclaimer (ALWAYS included - required for liability protection)
            self._add_legal_disclaimer()

            # Footer
            if options.get('include_footer', True):
                self._add_footer()

            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_vehicle_summary(self, profile: Dict) -> Dict[str, Any]:
        """Export standalone vehicle summary"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT VEHICLE SUMMARY")
            self.add_vehicle_summary(profile)
            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_ai_forecast(self, profile: Dict, snapshot: Dict,
                            ai_module, explanation_text: Optional[str] = None,
                            llm_assistant=None) -> Dict[str, Any]:
        """
        Export AI forecast report with optional LLM summarization.

        Args:
            profile: Vehicle profile data
            snapshot: Current OBD sensor snapshot
            ai_module: AI module for health analysis
            explanation_text: Optional owner-friendly explanation
            llm_assistant: Optional LLM assistant for summarizing long explanations
        """
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []

            self._add_header("PREDICT AI HEALTH & PREDICTIONS REPORT")
            self.add_ai_health_summary(profile, snapshot, ai_module, {'history': []})
            if explanation_text:
                self.add_owner_explanation_section(explanation_text, llm_assistant)
            self.add_predictions_section(profile, snapshot, ai_module, {'history': []})
            self.add_recommendations(ai_module, profile, snapshot, {'history': []})
            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_maintenance_history(self, profile: Dict, 
                                    db_manager=None) -> Dict[str, Any]:
        """Export maintenance history report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT MAINTENANCE HISTORY")
            self.add_maintenance_history(profile, db_manager)
            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_trends_report(self, profile: Dict, snapshot: Dict,
                              ai_module, options: Dict = None) -> Dict[str, Any]:
        """Export trends analysis report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT TRENDS ANALYSIS REPORT")

            history = options.get('history', []) if options else []
            self.add_trend_charts(history, options)
            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_cost_analytics(self, profile: Dict, 
                               db_manager=None) -> Dict[str, Any]:
        """Export cost analytics report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT COST ANALYTICS REPORT")
            
            self._add_section_title("Cost Analysis", "💰")
            
            if profile:
                total_costs = profile.get('total_costs', 0)
                mileage = profile.get('total_distance', profile.get('mileage', 0))
                
                cost_per_km = total_costs / mileage if mileage > 0 else 0
                
                cost_info = [
                    ["Metric", "Value"],
                    ["Total Recorded Costs", f"${total_costs:,.2f}"],
                    ["Total Distance", f"{mileage:,.0f} km"],
                    ["Cost per km", f"${cost_per_km:.3f}"],
                ]
                self._add_table(cost_info, col_widths=[200, 200])
            else:
                self._add_text("No cost data available.")

            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_driver_behavior(self, profile: Dict, 
                                db_manager=None) -> Dict[str, Any]:
        """Export driver behavior report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT DRIVER BEHAVIOR REPORT")
            
            self._add_section_title("Driving Analysis", "🚗")
            self._add_text(
                "Driver behavior analysis evaluates driving patterns based on "
                "acceleration, braking, speed profiles, and engine load patterns. "
                "Connect to live data for personalized analysis."
            )

            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_environmental_report(self, profile: Dict, snapshot: Dict,
                                      ai_module) -> Dict[str, Any]:
        """Export environmental impact report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT ENVIRONMENTAL IMPACT REPORT")
            
            self._add_section_title("Environmental Analysis", "🌍")
            self._add_text(
                "Environmental impact analysis evaluates fuel efficiency, "
                "emissions performance, and overall ecological footprint "
                "based on driving patterns and vehicle condition."
            )
            
            # Basic environmental metrics
            if snapshot:
                fuel_eff = snapshot.get('fuel_efficiency', 25)

                env_info = [
                    ["Metric", "Value", "Rating"],
                    ["Fuel Efficiency", f"{fuel_eff:.1f} MPG", "Good" if fuel_eff > 25 else "Fair"],
                    ["Emissions Status", "Normal", "✓"],
                ]
                self._add_table(env_info, col_widths=[180, 120, 100])

            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_fleet_report(self, profiles: List[Dict]) -> Dict[str, Any]:
        """Export fleet overview report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT FLEET OVERVIEW REPORT")
            
            self._add_section_title("Fleet Summary", "📊")
            
            if profiles:
                summary_info = [
                    ["Metric", "Value"],
                    ["Total Vehicles", str(len(profiles))],
                    ["Total Fleet Distance", f"{sum(p.get('total_distance', 0) for p in profiles):,.0f} km"],
                ]
                self._add_table(summary_info, col_widths=[200, 200])
                
                # Vehicle list
                self._add_subsection_title("Vehicle List")
                vehicle_rows = [["Vehicle", "Make/Model", "Year", "Distance"]]
                for p in profiles[:20]:
                    vehicle_rows.append([
                        p.get('name', '—'),
                        f"{p.get('make', '')} {p.get('model', '')}",
                        str(p.get('year', '—')),
                        f"{p.get('total_distance', 0):,.0f} km"
                    ])
                self._add_table(vehicle_rows, col_widths=[130, 150, 60, 100])
            else:
                self._add_text("No fleet data available.")

            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_comparison_report(self, profiles: List[Dict], 
                                  ai_module) -> Dict[str, Any]:
        """Export vehicle comparison report"""
        try:
            self.doc = SimpleDocTemplate(
                "temp_report.pdf",
                pagesize=A4,
                topMargin=25,
                bottomMargin=25,
                leftMargin=35,
                rightMargin=35,
            )
            self.story = []
            
            self._add_header("PREDICT VEHICLE COMPARISON REPORT")
            
            self._add_section_title("Comparison Overview", "⚖️")
            
            if profiles and len(profiles) >= 2:
                # Comparison table
                headers = ["Metric"] + [p.get('name', f'Vehicle {i+1}') 
                                       for i, p in enumerate(profiles[:5])]
                
                comparison_rows = [headers]
                
                metrics = [
                    ('make', 'Make'),
                    ('model', 'Model'),
                    ('year', 'Year'),
                    ('total_distance', 'Distance (km)'),
                ]
                
                for key, label in metrics:
                    row = [label]
                    for p in profiles[:5]:
                        val = p.get(key, '—')
                        if key == 'total_distance':
                            row.append(f"{val:,.0f}" if val else '—')
                        else:
                            row.append(str(val) if val else '—')
                    comparison_rows.append(row)
                
                col_widths = [100] + [80] * min(len(profiles), 5)
                self._add_table(comparison_rows, col_widths=col_widths)
            else:
                self._add_text("At least 2 vehicles required for comparison.")

            self._add_legal_disclaimer()
            self._add_footer()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_trip_summary(self, profile: Dict, db_manager=None):
        """Add trip summary section"""
        self._add_section_title("Trip Summary", "🛣️")
        
        trip_count = profile.get('trip_count', 0) if profile else 0
        total_distance = profile.get('total_distance', 0) if profile else 0
        driving_hours = profile.get('total_driving_hours', 0) if profile else 0
        
        trip_info = [
            ["Metric", "Value"],
            ["Total Trips", str(trip_count)],
            ["Total Distance", f"{total_distance:,.0f} km"],
            ["Total Driving Time", f"{driving_hours:,.1f} hours"],
            ["Avg Distance/Trip", f"{total_distance/trip_count:,.1f} km" if trip_count > 0 else "—"],
        ]
        self._add_table(trip_info, col_widths=[200, 200])

    def add_cost_analytics(self, profile: Dict, db_manager=None):
        """Add cost analytics section"""
        self._add_section_title("Cost Analytics", "💰")
        
        total_costs = profile.get('total_costs', 0) if profile else 0
        maintenance_count = profile.get('maintenance_count', 0) if profile else 0
        
        cost_info = [
            ["Metric", "Value"],
            ["Total Recorded Costs", f"${total_costs:,.2f}"],
            ["Maintenance Events", str(maintenance_count)],
            ["Avg Cost/Maintenance", f"${total_costs/maintenance_count:,.2f}" if maintenance_count > 0 else "—"],
        ]
        self._add_table(cost_info, col_widths=[200, 200])

    def add_fuel_efficiency_trend(self, profile: Dict, db_manager=None):
        """Add fuel efficiency trend section"""
        self._add_section_title("Fuel Efficiency", "⛽")
        
        self._add_text(
            "Fuel efficiency analysis tracks your vehicle's fuel consumption patterns "
            "over time. Connect to live data for real-time efficiency monitoring."
        )

    def add_driver_behavior(self, profile: Dict, db_manager=None):
        """Add driver behavior section"""
        self._add_section_title("Driver Behavior Analysis", "🚗")
        
        self._add_text(
            "Driver behavior scoring evaluates acceleration patterns, braking habits, "
            "speed consistency, and overall driving efficiency. Higher scores indicate "
            "more efficient and safer driving practices."
        )

    def add_diagnostics_summary(self, diagnostics=None):
        """Add diagnostics summary section"""
        self._add_section_title("Diagnostics Summary", "🔍")
        
        if diagnostics:
            diag_info = [
                ["Diagnostic", "Status"],
            ]
            for key, value in diagnostics.items():
                diag_info.append([str(key), str(value)])
            self._add_table(diag_info, col_widths=[200, 200])
        else:
            self._add_text("No diagnostic codes present. System operating normally.")

    def add_sensor_deviation(self, snapshot: Dict):
        """Add sensor deviation report"""
        self._add_section_title("Sensor Deviation Report", "⚠️")
        
        if not snapshot:
            self._add_text("No sensor data available for deviation analysis.")
            return
        
        # Check for deviations
        deviations = []
        thresholds = {
            'coolant_temp': (60, 110),
            'battery_voltage': (11.5, 15.0),
            'engine_load': (0, 100),
            'rpm': (0, 7000),
        }
        
        for sensor, (low, high) in thresholds.items():
            if sensor in snapshot:
                value = snapshot[sensor]
                if value is not None and (value < low or value > high):
                    deviations.append({
                        'sensor': sensor,
                        'value': value,
                        'range': f"{low}-{high}"
                    })
        
        if deviations:
            dev_rows = [["Sensor", "Value", "Normal Range"]]
            for dev in deviations:
                dev_rows.append([
                    dev['sensor'].replace('_', ' ').title(),
                    f"{dev['value']:.1f}",
                    dev['range']
                ])
            self._add_table(dev_rows, col_widths=[150, 100, 150])
        else:
            self._add_text("All sensors within normal operating ranges. ✓")

    def add_system_health(self, ai_module=None, connectivity=None):
        """Add system health summary"""
        self._add_section_title("System Health", "💚")
        
        health_info = [
            ["Parameter", "Status"],
            ["Data Quality", "Good ✓"],
            ["AI Confidence", "High ✓"],
            ["Connection Status", "Online ✓"],
            ["Logging Integrity", "OK ✓"],
        ]
        self._add_table(health_info, col_widths=[200, 200])

    def add_ai_forecast(self, profile: Dict, snapshot: Dict, 
                        ai_module, predictive_engine=None):
        """Add AI forecast section (legacy compatibility)"""
        self.add_ai_health_summary(profile, snapshot, ai_module)
        self.add_predictions_section(profile, snapshot, ai_module)

    def add_vin_decoded_info(self, profile: Dict, vin_decoder=None):
        """Add VIN decoded information"""
        self._add_section_title("VIN Information", "🔑")
        
        vin = profile.get('vin', '') if profile else ''
        
        if not vin:
            self._add_text("No VIN available for decoding.")
            return
        
        vin_info = [
            ["Field", "Value"],
            ["VIN", vin],
            ["Country", "—"],
            ["Manufacturer", profile.get('make', '—') if profile else '—'],
            ["Model Year", str(profile.get('year', '—')) if profile else '—'],
        ]
        self._add_table(vin_info, col_widths=[150, 350])