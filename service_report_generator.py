"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Service Report Generator

Service Report PDF Generator
Creates comprehensive service reports in PDF format
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os


class ServiceReportGenerator:
    """Generates PDF service reports"""

    def __init__(self, output_dir: str = None):
        from config import get_config
        CONFIG = get_config()
        
        self.output_dir = output_dir if output_dir else str(CONFIG.DATA_DIR / "reports")
        os.makedirs(self.output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Define custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#C40000'),  # Predict Red
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            spaceBefore=20,
            borderWidth=0,
            borderPadding=0,
            leftIndent=0,
        ))

    def generate_service_report(
        self,
        profile: dict,
        dtc_codes: list,
        oil_change_status: dict,
        maintenance_summary: dict,
        report_type: str = "full"
    ) -> str:
        """
        Generate service report PDF

        Args:
            profile: Vehicle profile dictionary
            dtc_codes: List of DTC codes with details
            oil_change_status: Oil change status information
            maintenance_summary: Maintenance summary data
            report_type: Type of report ('dtc', 'oil_change', 'full')

        Returns:
            Path to generated PDF file
        """
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_name = profile.get('name', 'vehicle').replace(' ', '_')
        filename = f"service_report_{profile_name}_{timestamp}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        # Create PDF document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph(
            "PREDICT - Vehicle Service Report",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.3*inch))

        # Vehicle Information
        story.append(Paragraph("Vehicle Information", self.styles['SectionHeader']))
        vehicle_data = [
            ["Name:", profile.get('name', 'N/A')],
            ["Make/Model:", f"{profile.get('make', '')} {profile.get('model', '')}".strip() or 'N/A'],
            ["Year:", str(profile.get('year', 'N/A'))],
            ["VIN:", profile.get('vin', 'N/A')],
            ["License Plate:", profile.get('license_plate', 'N/A')],
            ["Odometer:", f"{profile.get('odometer_km', 0):.0f} km ({profile.get('odometer_km', 0) * 0.621371:.0f} miles)"],
        ]
        vehicle_table = Table(vehicle_data, colWidths=[2*inch, 4*inch])
        vehicle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(vehicle_table)
        story.append(Spacer(1, 0.3*inch))

        # DTC Codes Section
        if report_type in ['dtc', 'full'] and dtc_codes:
            story.append(Paragraph(
                "Diagnostic Trouble Codes (DTCs)",
                self.styles['SectionHeader']
            ))

            dtc_data = [["Code", "Description", "Severity"]]
            for dtc in dtc_codes:
                description = dtc.get('description', '')
                if len(description) > 50:
                    description = description[:47] + "..."

                dtc_data.append([
                    dtc.get('code', ''),
                    description,
                    dtc.get('severity', 'Unknown').upper()
                ])

            dtc_table = Table(dtc_data, colWidths=[1*inch, 4*inch, 1.5*inch])
            dtc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#C40000')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            story.append(dtc_table)
            story.append(Spacer(1, 0.2*inch))

            # Add possible causes for each DTC
            story.append(Paragraph("Possible Causes & Recommendations:", self.styles['Heading3']))
            for dtc in dtc_codes:
                causes = dtc.get('possible_causes', [])
                if causes:
                    story.append(Paragraph(
                        f"<b>{dtc.get('code', '')}</b>: {', '.join(causes[:3])}",
                        self.styles['Normal']
                    ))

            story.append(Spacer(1, 0.3*inch))

        # Oil Change Status
        if report_type in ['oil_change', 'full'] and oil_change_status:
            story.append(Paragraph(
                "Oil Change Status",
                self.styles['SectionHeader']
            ))

            oil_data = [
                ["Last Change:", f"{oil_change_status.get('last_change_km', 0):.0f} km"],
                ["Next Change Due:", f"{oil_change_status.get('next_change_due_km', 0):.0f} km"],
                ["Remaining:", f"{oil_change_status.get('km_remaining', 0):.0f} km"],
                ["Status:", oil_change_status.get('status', 'Unknown').upper()]
            ]
            oil_table = Table(oil_data, colWidths=[2*inch, 4*inch])
            oil_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(oil_table)
            story.append(Spacer(1, 0.3*inch))

        # Maintenance Summary
        if report_type == 'full':
            story.append(Paragraph(
                "Maintenance Summary",
                self.styles['SectionHeader']
            ))
            story.append(Paragraph(
                f"• Total Services Recorded: {maintenance_summary.get('total_services', 0)}",
                self.styles['Normal']
            ))
            story.append(Paragraph(
                f"• Upcoming Services: {len(maintenance_summary.get('upcoming_services', []))}",
                self.styles['Normal']
            ))
            story.append(Paragraph(
                f"• Overdue Services: {len(maintenance_summary.get('overdue_services', []))}",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 0.2*inch))

            # Recommendations
            story.append(Paragraph("Recommendations:", self.styles['Heading3']))
            recommendations = [
                "• Follow manufacturer's maintenance schedule",
                "• Check tire pressure and tread depth monthly",
                "• Inspect brake pads every 10,000 km",
                "• Replace air filter every 15,000 km",
                "• Flush coolant every 40,000 km or 2 years"
            ]
            for rec in recommendations:
                story.append(Paragraph(rec, self.styles['Normal']))

        # Footer
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(
            "<i>Powered by PREDICT - Professional Car AI</i>",
            self.styles['Normal']
        ))

        # Build PDF
        doc.build(story)

        return filepath


    def generate_oil_change_history_report(
        self,
        profile: dict,
        oil_change_history: list
    ) -> str:
        """
        Generate oil change history report PDF

        Args:
            profile: Vehicle profile dictionary
            oil_change_history: List of oil change records

        Returns:
            Path to generated PDF file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_name = profile.get('name', 'vehicle').replace(' ', '_')
        filename = f"oil_change_history_{profile_name}_{timestamp}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )

        story = []

        # Title
        story.append(Paragraph(
            "PREDICT - Oil Change History",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.3*inch))

        # Vehicle Info
        story.append(Paragraph(
            f"Vehicle: {profile.get('name', 'N/A')} ({profile.get('make', '')} {profile.get('model', '')} {profile.get('year', '')})",
            self.styles['Heading2']
        ))
        story.append(Spacer(1, 0.2*inch))

        # Oil change history table
        if oil_change_history:
            history_data = [["Date", "Odometer (km)", "Oil Type", "Filter", "Cost"]]

            for record in oil_change_history:
                date_str = record.get('timestamp', '')[:10]  # Extract date part
                odometer = f"{record.get('odometer_km', 0):.0f}"
                oil_type = record.get('oil_type', 'N/A')
                filter_changed = "Yes" if record.get('filter_changed', True) else "No"
                cost = f"${record.get('cost', 0):.2f}" if record.get('cost') else "N/A"

                history_data.append([date_str, odometer, oil_type, filter_changed, cost])

            history_table = Table(history_data, colWidths=[1.5*inch, 1.5*inch, 2*inch, 0.75*inch, 1*inch])
            history_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#C40000')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            story.append(history_table)
        else:
            story.append(Paragraph("No oil change records found.", self.styles['Normal']))

        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['Normal']
        ))

        doc.build(story)
        return filepath
