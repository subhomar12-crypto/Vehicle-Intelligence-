"""
PDF service for report generation using ReportLab.

Handles:
- Diagnostic report PDFs
- Maintenance history reports
- Subscription invoices
- Performance summaries
"""

import logging
import os
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, ListFlowable, ListItem
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from predict.core.config import get_config

logger = logging.getLogger(__name__)


class PDFService:
    """PDF generation service for reports."""
    
    def __init__(self):
        self.config = get_config()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Modify existing 'Title' style instead of adding a duplicate
        self.styles['Title'].fontSize = 24
        self.styles['Title'].spaceAfter = 30
        self.styles['Title'].alignment = TA_CENTER

        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1976d2'),
            spaceBefore=20,
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name='RiskHigh',
            parent=self.styles['Normal'],
            textColor=colors.red,
            fontSize=12,
        ))
        self.styles.add(ParagraphStyle(
            name='RiskMedium',
            parent=self.styles['Normal'],
            textColor=colors.orange,
            fontSize=12,
        ))
        self.styles.add(ParagraphStyle(
            name='RiskLow',
            parent=self.styles['Normal'],
            textColor=colors.green,
            fontSize=12,
        ))
    
    async def generate_diagnostic_report(
        self,
        vehicle_info: Dict[str, Any],
        diagnostic_results: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a diagnostic PDF report.
        
        Args:
            vehicle_info: Vehicle details (make, model, year, VIN)
            diagnostic_results: AI diagnostic results
            filename: Optional custom filename
        
        Returns:
            Path to generated PDF file
        """
        if filename is None:
            filename = f"diagnostic_{vehicle_info.get('vin') or 'unknown'}_{int(time.time())}.pdf"
        
        output_path = self.config.DATA_DIR / "reports" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        story = []
        
        # Title
        story.append(Paragraph("Vehicle Diagnostic Report", self.styles['Title']))
        story.append(Paragraph(
            f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
            self.styles['Subtitle']
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Vehicle Information
        story.append(Paragraph("Vehicle Information", self.styles['SectionHeader']))
        vehicle_data = [
            ["Make", vehicle_info.get("make", "N/A")],
            ["Model", vehicle_info.get("model", "N/A")],
            ["Year", str(vehicle_info.get("year", "N/A"))],
            ["VIN", vehicle_info.get("vin", "N/A")],
            ["Mileage", f"{vehicle_info.get('mileage', 'N/A'):,} km"],
        ]
        
        vehicle_table = Table(vehicle_data, colWidths=[2*inch, 4*inch])
        vehicle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(vehicle_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Health Score
        story.append(Paragraph("Overall Health Assessment", self.styles['SectionHeader']))
        health_score = diagnostic_results.get("health_score", 0)
        
        score_color = colors.green if health_score >= 80 else colors.orange if health_score >= 60 else colors.red
        score_data = [[
            f"Health Score: {health_score}/100",
            f"Risk Level: {diagnostic_results.get('risk_level', 'Unknown').upper()}",
        ]]
        
        score_table = Table(score_data, colWidths=[3*inch, 3*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), score_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Component Analysis
        story.append(Paragraph("Component Analysis", self.styles['SectionHeader']))
        components = diagnostic_results.get("subsystem_scores", {})
        
        if components:
            comp_data = [["Component", "Health Score", "Status", "Notes"]]
            for name, data in components.items():
                score = data.get("score", 0)
                status = data.get("status", "Unknown")
                notes = data.get("notes", "")
                comp_data.append([name.title(), f"{score}", status, notes])
            
            comp_table = Table(comp_data, colWidths=[1.5*inch, 1*inch, 1*inch, 2.5*inch])
            comp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ]))
            story.append(comp_table)
        else:
            story.append(Paragraph("No component data available", self.styles['Normal']))
        
        story.append(PageBreak())
        
        # Recommendations
        story.append(Paragraph("Recommendations", self.styles['SectionHeader']))
        recommendations = diagnostic_results.get("recommendations", [])
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                priority = rec.get("priority", "normal")
                style = f"Risk{priority.capitalize()}" if priority in ["high", "medium", "low"] else "Normal"
                story.append(Paragraph(
                    f"{i}. [{priority.upper()}] {rec.get('action', 'No action specified')}",
                    self.styles.get(style, self.styles['Normal'])
                ))
        else:
            story.append(Paragraph("No immediate recommendations", self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        logger.info(f"Diagnostic report generated: {output_path}")
        
        return str(output_path)
    
    async def generate_invoice(
        self,
        invoice_data: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a subscription invoice PDF.
        
        Args:
            invoice_data: Invoice details
            filename: Optional custom filename
        
        Returns:
            Path to generated PDF file
        """
        if filename is None:
            filename = f"invoice_{invoice_data.get('invoice_id', 'unknown')}.pdf"
        
        output_path = self.config.DATA_DIR / "invoices" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        story = []
        
        # Header
        story.append(Paragraph("INVOICE", self.styles['Title']))
        story.append(Spacer(1, 0.2*inch))
        
        # Invoice details
        invoice_info = [
            ["Invoice #:", invoice_data.get("invoice_id", "N/A")],
            ["Date:", time.strftime('%Y-%m-%d', time.localtime(invoice_data.get("date", time.time())))],
            ["Due Date:", time.strftime('%Y-%m-%d', time.localtime(invoice_data.get("due_date", time.time())))],
        ]
        
        info_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Bill To
        story.append(Paragraph("Bill To:", self.styles['SectionHeader']))
        customer = invoice_data.get("customer", {})
        story.append(Paragraph(customer.get("name", "Unknown"), self.styles['Normal']))
        story.append(Paragraph(customer.get("email", ""), self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Items
        story.append(Paragraph("Items", self.styles['SectionHeader']))
        items = invoice_data.get("items", [])
        
        if items:
            item_data = [["Description", "Quantity", "Unit Price", "Amount"]]
            total = 0
            for item in items:
                qty = item.get("quantity", 1)
                price = item.get("price", 0)
                amount = qty * price
                total += amount
                item_data.append([
                    item.get("description", ""),
                    str(qty),
                    f"${price:.2f}",
                    f"${amount:.2f}",
                ])
            
            # Add total row
            item_data.append(["", "", "Total:", f"${total:.2f}"])
            
            item_table = Table(item_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f5f5f5')),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -2), 1, colors.grey),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            ]))
            story.append(item_table)
        
        # Payment Status
        story.append(Spacer(1, 0.3*inch))
        status = invoice_data.get("status", "pending")
        status_color = colors.green if status == "paid" else colors.orange if status == "pending" else colors.red
        story.append(Paragraph(
            f"Payment Status: {status.upper()}",
            ParagraphStyle(
                name='Status',
                parent=self.styles['Normal'],
                fontSize=14,
                textColor=status_color,
                fontName='Helvetica-Bold',
            )
        ))
        
        doc.build(story)
        logger.info(f"Invoice generated: {output_path}")
        
        return str(output_path)
    
    async def generate_enhanced_diagnostic_report(
        self,
        vehicle_info: Dict[str, Any],
        diagnostic_results: Dict[str, Any],
        narrative: Dict[str, str],
        stats_summary: Dict[str, Any],
        health_chart: Optional[bytes] = None,
        trend_charts: Optional[List[bytes]] = None,
        filename: Optional[str] = None,
        ai_predictions: Optional[Dict[str, Any]] = None,
        v3_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate an enhanced diagnostic report with LLM narrative and charts.

        Structure:
        - Page 1: Title + vehicle info + health score + executive summary
        - Page 2: Health bar chart + component analysis narrative
        - Page 3: Sensor trend charts + stats highlights
        - Page 4: Recommendations + maintenance outlook
        - Footer: "Generated by PREDICT AI"
        """
        if filename is None:
            filename = f"enhanced_{vehicle_info.get('vin') or 'report'}_{int(time.time())}.pdf"

        output_path = self.config.DATA_DIR / "reports" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=36,
        )

        story = []

        # ---- Page 1: Title + Vehicle Info + Health Score + Executive Summary ----
        story.append(Paragraph("PREDICT Vehicle Health Report", self.styles["Title"]))
        story.append(Paragraph(
            f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
            self.styles["Subtitle"],
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Vehicle info table
        story.append(Paragraph("Vehicle Information", self.styles["SectionHeader"]))
        vdata = [
            ["Make", vehicle_info.get("make", "N/A")],
            ["Model", vehicle_info.get("model", "N/A")],
            ["Year", str(vehicle_info.get("year", "N/A"))],
            ["VIN", vehicle_info.get("vin", "N/A")],
        ]
        engine = vehicle_info.get("engine_type", "")
        displacement = vehicle_info.get("displacement", "")
        if engine:
            vdata.append(["Engine", f"{engine} {displacement}".strip()])

        vtable = Table(vdata, colWidths=[2 * inch, 4 * inch])
        vtable.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(vtable)
        story.append(Spacer(1, 0.3 * inch))

        # Health score banner
        health_score = diagnostic_results.get("health_score", 0)
        score_color = (
            colors.green if health_score >= 80
            else colors.orange if health_score >= 60
            else colors.red
        )
        score_table = Table(
            [[f"Health Score: {health_score}/100",
              f"Risk Level: {diagnostic_results.get('risk_level', 'unknown').upper()}"]],
            colWidths=[3 * inch, 3 * inch],
        )
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), score_color),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 0.3 * inch))

        # Executive summary narrative
        exec_summary = narrative.get("executive_summary", "")
        if exec_summary:
            story.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))
            for para in exec_summary.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), self.styles["Normal"]))
                    story.append(Spacer(1, 0.1 * inch))

        story.append(PageBreak())

        # ---- Page 2: Health Chart + Component Analysis ----
        if health_chart:
            story.append(Paragraph("Component Health Overview", self.styles["SectionHeader"]))
            story.append(Image(BytesIO(health_chart), width=6 * inch, height=3.5 * inch))
            story.append(Spacer(1, 0.2 * inch))

        # Component analysis table (same as original)
        components = diagnostic_results.get("subsystem_scores", {})
        if components:
            story.append(Paragraph("Component Details", self.styles["SectionHeader"]))
            comp_data = [["Component", "Health", "Status", "Notes"]]
            for name, data in components.items():
                score = data.get("score", 0)
                status = data.get("status", "Unknown")
                notes = data.get("notes", "")
                comp_data.append([name.replace("_", " ").title(), f"{score}%", status, notes[:60]])

            comp_table = Table(comp_data, colWidths=[1.5 * inch, 0.8 * inch, 0.8 * inch, 2.9 * inch])
            comp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C40000")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]))
            story.append(comp_table)
            story.append(Spacer(1, 0.2 * inch))

        # Component analysis narrative
        comp_narrative = narrative.get("component_analysis", "")
        if comp_narrative:
            story.append(Paragraph("Analysis", self.styles["SectionHeader"]))
            for para in comp_narrative.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), self.styles["Normal"]))
                    story.append(Spacer(1, 0.1 * inch))

        story.append(PageBreak())

        # ---- Page 3: Sensor Trends + Stats ----
        if trend_charts:
            story.append(Paragraph("Sensor Trends (Last 7 Days)", self.styles["SectionHeader"]))
            for chart_bytes in trend_charts[:4]:
                story.append(Image(BytesIO(chart_bytes), width=6 * inch, height=2.5 * inch))
                story.append(Spacer(1, 0.15 * inch))

        # Stats highlights
        sensors_data = stats_summary.get("sensors", {})
        anomaly_sensors = {
            k: v for k, v in sensors_data.items()
            if v.get("risk_level", "normal") != "normal"
        }
        if anomaly_sensors:
            story.append(Paragraph("Sensor Anomalies Detected", self.styles["SectionHeader"]))
            anomaly_data = [["Sensor", "Risk", "Mean", "Trend", "Anomalies"]]
            for sname, sdata in anomaly_sensors.items():
                anomaly_data.append([
                    sname.replace("_", " ").title(),
                    sdata.get("risk_level", "").upper(),
                    f"{sdata.get('mean', 0):.1f}",
                    sdata.get("trend", "stable"),
                    str(sdata.get("anomaly_count", 0)),
                ])
            at = Table(anomaly_data, colWidths=[1.5 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch])
            at.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C40000")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(at)

        # ---- AI Prediction Action Plan (optional) ----
        if ai_predictions:
            story.append(PageBreak())
            story.append(Paragraph("AI Prediction Action Plan", self.styles["SectionHeader"]))
            story.append(Spacer(1, 0.1 * inch))

            action_plan = ai_predictions.get("action_plan", {})
            for priority, label_color in [
                ("urgent", colors.red), ("soon", colors.orange), ("routine", colors.green)
            ]:
                items = action_plan.get(priority, [])
                if items:
                    story.append(Paragraph(
                        f"{priority.upper()} Actions",
                        ParagraphStyle(
                            name=f"Priority_{priority}",
                            parent=self.styles["Normal"],
                            fontSize=11, fontName="Helvetica-Bold",
                            textColor=label_color,
                        ),
                    ))
                    for item in items:
                        action_text = item.get("action", "") if isinstance(item, dict) else str(item)
                        reason = item.get("reason", "") if isinstance(item, dict) else ""
                        cost = item.get("cost", "N/A") if isinstance(item, dict) else "N/A"
                        story.append(Paragraph(
                            f"• {action_text} — {reason} (Est: {cost})",
                            self.styles["Normal"],
                        ))
                    story.append(Spacer(1, 0.15 * inch))

            # Per-component AI narratives
            llm_comps = ai_predictions.get("components", {})
            for comp_id, comp_data in llm_comps.items():
                comp_name = comp_id.replace("_", " ").title()
                health_pct = comp_data.get("health_pct", 0)
                headline = comp_data.get("headline", "")
                story.append(Paragraph(
                    f"{comp_name} — {health_pct}%",
                    ParagraphStyle(
                        name=f"Comp_{comp_id}",
                        parent=self.styles["Normal"],
                        fontSize=10, fontName="Helvetica-Bold",
                    ),
                ))
                if headline:
                    story.append(Paragraph(headline, self.styles["Normal"]))
                for field in ["status_text", "trend_text", "prediction_text", "compared_to_others_text"]:
                    text = comp_data.get(field, "")
                    if text:
                        story.append(Paragraph(text, self.styles["Normal"]))
                action_info = comp_data.get("recommended_action", {})
                if isinstance(action_info, dict) and action_info.get("action"):
                    story.append(Paragraph(
                        f"Recommended: {action_info['action']}",
                        ParagraphStyle(
                            name=f"Action_{comp_id}",
                            parent=self.styles["Normal"],
                            fontName="Helvetica-Oblique",
                        ),
                    ))
                story.append(Spacer(1, 0.1 * inch))

        story.append(PageBreak())

        # ---- Page 4: Recommendations + Maintenance Outlook ----
        recs = narrative.get("recommendations", "")
        if recs:
            story.append(Paragraph("Recommendations", self.styles["SectionHeader"]))
            for line in recs.split("\n"):
                line = line.strip()
                if line:
                    story.append(Paragraph(line, self.styles["Normal"]))
                    story.append(Spacer(1, 0.05 * inch))
            story.append(Spacer(1, 0.2 * inch))

        outlook = narrative.get("maintenance_outlook", "")
        if outlook:
            story.append(Paragraph("Maintenance Outlook", self.styles["SectionHeader"]))
            for para in outlook.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), self.styles["Normal"]))
                    story.append(Spacer(1, 0.1 * inch))

        # ---- v3 Sections: Maintenance Forecast + Fleet Comparison + Root Cause ----
        if v3_data:
            self._add_v3_sections(story, v3_data)

        # Footer note
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(
            f"Generated by PREDICT AI • {time.strftime('%Y-%m-%d %H:%M')}",
            ParagraphStyle(
                name="FooterNote",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            ),
        ))

        doc.build(story)
        logger.info(f"Enhanced diagnostic report generated: {output_path}")
        return str(output_path)

    def _add_v3_sections(self, story: list, v3_data: Dict[str, Any]) -> None:
        """Add v3 intelligence sections to PDF report."""
        maintenance_events = v3_data.get("maintenance_events", [])
        fleet_comparison = v3_data.get("fleet_comparison")
        ai_diagnostic = v3_data.get("ai_diagnostic")

        # ---- Maintenance Forecast Table ----
        if maintenance_events:
            story.append(PageBreak())
            story.append(Paragraph("Maintenance Forecast", self.styles["SectionHeader"]))
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph(
                "Predicted service dates based on Weibull survival analysis, component health scores, "
                "and Qatar climate-adjusted service intervals. Costs in QAR.",
                self.styles["Normal"],
            ))
            story.append(Spacer(1, 0.15 * inch))

            maint_data = [["Component", "Priority", "Due Date", "Days", "Health", "Cost (QAR)"]]
            total_min = 0
            total_max = 0
            for ev in maintenance_events:
                cost = ev.get("cost_estimate_qar", {})
                cost_min = cost.get("min", 0)
                cost_max = cost.get("max", 0)
                total_min += cost_min
                total_max += cost_max
                maint_data.append([
                    ev.get("component_name", ""),
                    ev.get("priority", "").upper(),
                    ev.get("due_date", ""),
                    str(ev.get("days_until_due", "")),
                    f"{ev.get('health_pct', 0)}%",
                    f"{cost_min}-{cost_max}",
                ])

            # Add total row
            maint_data.append(["", "", "", "", "TOTAL", f"{total_min}-{total_max}"])

            maint_table = Table(
                maint_data,
                colWidths=[1.6 * inch, 0.8 * inch, 0.9 * inch, 0.5 * inch, 0.7 * inch, 1.1 * inch],
            )

            # Color-code priority cells
            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C40000")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f0f0")),
            ]
            # Color priority column
            priority_colors = {
                "CRITICAL": colors.red, "HIGH": colors.HexColor("#FF6600"),
                "MEDIUM": colors.orange, "LOW": colors.green,
            }
            for row_idx, row in enumerate(maint_data[1:-1], start=1):
                p_color = priority_colors.get(row[1], colors.black)
                style_commands.append(("TEXTCOLOR", (1, row_idx), (1, row_idx), p_color))

            maint_table.setStyle(TableStyle(style_commands))
            story.append(maint_table)
            story.append(Spacer(1, 0.2 * inch))

        # ---- Fleet Comparison ----
        if fleet_comparison:
            story.append(PageBreak())
            story.append(Paragraph("Fleet Comparison", self.styles["SectionHeader"]))
            story.append(Spacer(1, 0.1 * inch))

            cohort_size = fleet_comparison.get("cohort_size", 0)
            percentile = fleet_comparison.get("overall_percentile", 50)
            cohort_avg = fleet_comparison.get("overall_cohort_avg", 0)
            your_score = fleet_comparison.get("your_score", 0)
            year_range = fleet_comparison.get("year_range", "")
            make = fleet_comparison.get("make", "")
            model = fleet_comparison.get("model", "")

            story.append(Paragraph(
                f"Your vehicle compared against <b>{cohort_size}</b> similar "
                f"{make} {model} ({year_range}) vehicles in the PREDICT network.",
                self.styles["Normal"],
            ))
            story.append(Spacer(1, 0.1 * inch))

            # Overall ranking
            rank_color = colors.green if percentile >= 70 else colors.orange if percentile >= 40 else colors.red
            rank_table = Table(
                [[f"Your Score: {your_score}/100",
                  f"Fleet Average: {cohort_avg}/100",
                  f"Percentile: {percentile}th"]],
                colWidths=[2 * inch, 2 * inch, 2 * inch],
            )
            rank_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), rank_color),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
            ]))
            story.append(rank_table)
            story.append(Spacer(1, 0.2 * inch))

            # Per-component comparison
            comp_comparison = fleet_comparison.get("components", {})
            if comp_comparison:
                story.append(Paragraph("Component Comparison", self.styles["SectionHeader"]))
                fc_data = [["Component", "Your Score", "Fleet Avg", "Delta", "Percentile"]]
                for cid, cd in comp_comparison.items():
                    delta = cd.get("delta", 0)
                    delta_str = f"+{delta}" if delta >= 0 else str(delta)
                    fc_data.append([
                        cid.replace("_", " ").title(),
                        f"{cd.get('your_score', 0)}%",
                        f"{cd.get('cohort_avg', 0)}%",
                        delta_str,
                        f"{cd.get('percentile', 50)}th",
                    ])

                fc_table = Table(
                    fc_data,
                    colWidths=[1.6 * inch, 1 * inch, 1 * inch, 0.8 * inch, 1 * inch],
                )
                fc_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ]))
                # Color delta column (green for positive, red for negative)
                for row_idx in range(1, len(fc_data)):
                    delta_val = comp_comparison.get(list(comp_comparison.keys())[row_idx - 1], {}).get("delta", 0)
                    dc = colors.green if delta_val >= 0 else colors.red
                    fc_table.setStyle(TableStyle([
                        ("TEXTCOLOR", (3, row_idx), (3, row_idx), dc),
                    ]))
                story.append(fc_table)
                story.append(Spacer(1, 0.2 * inch))

        # ---- AI Root Cause Analysis ----
        if ai_diagnostic:
            story.append(PageBreak())
            story.append(Paragraph("AI Root Cause Analysis", self.styles["SectionHeader"]))
            story.append(Spacer(1, 0.1 * inch))

            owner_summary = ai_diagnostic.get("owner_summary", "")
            if owner_summary:
                story.append(Paragraph(owner_summary, self.styles["Normal"]))
                story.append(Spacer(1, 0.15 * inch))

            # Cross-component patterns
            patterns = ai_diagnostic.get("cross_patterns", [])
            if patterns:
                story.append(Paragraph("Cross-Component Patterns", self.styles["SectionHeader"]))
                for pat in patterns:
                    if isinstance(pat, dict):
                        story.append(Paragraph(
                            f"• {pat.get('pattern', pat.get('description', str(pat)))}",
                            self.styles["Normal"],
                        ))
                    else:
                        story.append(Paragraph(f"• {pat}", self.styles["Normal"]))
                story.append(Spacer(1, 0.15 * inch))

            # Known issue flags
            known_issues = ai_diagnostic.get("known_issue_flags", [])
            if known_issues:
                story.append(Paragraph("Known Issue Flags", self.styles["SectionHeader"]))
                for issue in known_issues:
                    if isinstance(issue, dict):
                        story.append(Paragraph(
                            f"• {issue.get('issue', issue.get('description', str(issue)))}",
                            self.styles["Normal"],
                        ))
                    else:
                        story.append(Paragraph(f"• {issue}", self.styles["Normal"]))
                story.append(Spacer(1, 0.15 * inch))

            # Disagreements (AI vs cold-start)
            disagreements = ai_diagnostic.get("disagreements", [])
            if disagreements:
                story.append(Paragraph("AI Analysis Notes", self.styles["SectionHeader"]))
                for d in disagreements:
                    if isinstance(d, dict):
                        comp = d.get("component", "")
                        note = d.get("note", d.get("reason", str(d)))
                        story.append(Paragraph(f"• {comp}: {note}", self.styles["Normal"]))
                    else:
                        story.append(Paragraph(f"• {d}", self.styles["Normal"]))
                story.append(Spacer(1, 0.15 * inch))

    async def generate_maintenance_report(
        self,
        vehicle_info: Dict[str, Any],
        maintenance_history: List[Dict[str, Any]],
        upcoming_services: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> str:
        """Generate a maintenance history report."""
        if filename is None:
            filename = f"maintenance_{vehicle_info.get('vin', 'unknown')}_{int(time.time())}.pdf"
        
        output_path = self.config.DATA_DIR / "reports" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
        )
        
        story = []
        story.append(Paragraph("Maintenance History Report", self.styles['Title']))
        story.append(Spacer(1, 0.3*inch))
        
        # Vehicle info
        story.append(Paragraph("Vehicle Information", self.styles['SectionHeader']))
        for key, value in vehicle_info.items():
            story.append(Paragraph(f"<b>{key.title()}:</b> {value}", self.styles['Normal']))
        
        story.append(PageBreak())
        
        # History
        story.append(Paragraph("Service History", self.styles['SectionHeader']))
        if maintenance_history:
            for record in maintenance_history:
                date_str = str(record.get('date', 'N/A'))
                cost = record.get('cost') or 0
                story.append(Paragraph(
                    f"• {date_str} - "
                    f"{record.get('service', 'Unknown Service')} - ${cost:.2f}",
                    self.styles['Normal']
                ))
        else:
            story.append(Paragraph("No service history available", self.styles['Normal']))
        
        # Upcoming
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Upcoming Services", self.styles['SectionHeader']))
        if upcoming_services:
            for service in upcoming_services:
                story.append(Paragraph(
                    f"• Due at {service.get('due_mileage', 'N/A')} km: {service.get('description', 'Unknown')}",
                    self.styles['Normal']
                ))
        else:
            story.append(Paragraph("No upcoming services scheduled", self.styles['Normal']))
        
        doc.build(story)
        logger.info(f"Maintenance report generated: {output_path}")
        
        return str(output_path)
