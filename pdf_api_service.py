"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Pdf Api Service

PDF API Service
Handles PDF generation requests from mobile app
Supports week/lifetime data options
Includes push notification and email delivery
"""

import os
import json
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import uuid

from config import get_config
CONFIG = get_config()

logger = logging.getLogger(__name__)


class PDFAPIService:
    """
    PDF generation service for mobile app requests
    - Week data reports (last 7 days)
    - Lifetime data reports (all historical data)
    - Push to mobile app
    - Email delivery
    """

    def __init__(self, pdf_exporter, historical_data_manager, vehicle_manager):
        """
        Initialize PDF API service

        Args:
            pdf_exporter: PDFExporter instance
            historical_data_manager: HistoricalDataManager instance
            vehicle_manager: VehicleProfileManager instance
        """
        self.pdf_exporter = pdf_exporter
        self.historical_data = historical_data_manager
        self.vehicle_manager = vehicle_manager

        # PDF request tracking
        self.active_requests = {}  # request_id -> request_info
        self.completed_pdfs = {}   # request_id -> pdf_path

        # Output directory for PDFs
        self.pdf_output_dir = str(CONFIG.DATA_DIR / "reports")
        os.makedirs(self.pdf_output_dir, exist_ok=True)

        # Email configuration (user should configure this)
        self.email_config = self._load_email_config()

        logger.info("PDF API Service initialized")

    def _load_email_config(self) -> Dict[str, str]:
        """Load email configuration from file"""
        try:
            config_file = str(CONFIG.CONFIG_DIR / "email_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load email config: {e}")

        # Default empty config
        return {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'enabled': False
        }

    def request_pdf_generation(self, profile_name: str, profile_id: int,
                               report_type: str, delivery_method: str,
                               email: Optional[str] = None) -> Dict[str, Any]:
        """
        Request PDF generation

        Args:
            profile_name: Vehicle profile name
            profile_id: Profile ID
            report_type: 'week' or 'lifetime'
            delivery_method: 'push' or 'email'
            email: Email address (required if delivery_method is 'email')

        Returns:
            Request info with request_id
        """
        try:
            # Generate unique request ID
            request_id = f"pdf_req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

            # Validate inputs
            if report_type not in ['week', 'lifetime']:
                return {'success': False, 'error': 'Invalid report_type. Must be "week" or "lifetime"'}

            if delivery_method not in ['push', 'email']:
                return {'success': False, 'error': 'Invalid delivery_method. Must be "push" or "email"'}

            if delivery_method == 'email' and not email:
                return {'success': False, 'error': 'Email address required for email delivery'}

            # Create request info
            request_info = {
                'request_id': request_id,
                'profile_name': profile_name,
                'profile_id': profile_id,
                'report_type': report_type,
                'delivery_method': delivery_method,
                'email': email,
                'status': 'queued',
                'progress': 0,
                'created_at': datetime.now().isoformat(),
                'estimated_time_seconds': 30
            }

            # Track request
            self.active_requests[request_id] = request_info

            # Start generation in background thread
            generation_thread = threading.Thread(
                target=self._generate_pdf_background,
                args=(request_id,)
            )
            generation_thread.start()

            logger.info(f"PDF generation requested: {request_id} ({report_type} for {profile_name})")

            return {
                'success': True,
                'request_id': request_id,
                'estimated_time_seconds': 30,
                'status': 'queued'
            }

        except Exception as e:
            logger.error(f"Error requesting PDF: {e}")
            return {'success': False, 'error': str(e)}

    def _generate_pdf_background(self, request_id: str):
        """
        Generate PDF in background thread

        Args:
            request_id: PDF request ID
        """
        try:
            request_info = self.active_requests.get(request_id)
            if not request_info:
                logger.error(f"Request not found: {request_id}")
                return

            # Update status
            request_info['status'] = 'processing'
            request_info['progress'] = 10

            profile_name = request_info['profile_name']
            profile_id = request_info['profile_id']
            report_type = request_info['report_type']

            logger.info(f"Generating {report_type} PDF for {profile_name}...")

            # Get profile data
            profile = self.vehicle_manager.get_profile(profile_id)
            if not profile:
                request_info['status'] = 'failed'
                request_info['error'] = 'Profile not found'
                return

            request_info['progress'] = 20

            # Get historical data based on report type
            if report_type == 'week':
                # Last 7 days
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                historical_data = self.historical_data.read_profile_data(
                    profile_name, profile_id,
                    start_date=start_date,
                    end_date=end_date
                )
                data_range = f"Last 7 Days ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"

            else:  # lifetime
                # All data
                historical_data = self.historical_data.read_profile_data(
                    profile_name, profile_id
                )
                data_range = "Lifetime Data (All Records)"

            request_info['progress'] = 40

            if not historical_data:
                request_info['status'] = 'failed'
                request_info['error'] = 'No data available'
                logger.warning(f"No data for {profile_name}")
                return

            # Prepare snapshot (use latest data point)
            snapshot = historical_data[-1] if historical_data else {}

            request_info['progress'] = 50

            # Generate PDF filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_filename = f"predict_report_{profile_name}_{report_type}_{timestamp}.pdf"
            pdf_path = os.path.join(self.pdf_output_dir, pdf_filename)

            # Generate PDF using pdf_exporter
            # (Note: You'll need to enhance PDFExporter to accept historical_data parameter)
            result = self._generate_report_pdf(
                profile, snapshot, historical_data, pdf_path, data_range
            )

            request_info['progress'] = 80

            if not result.get('success'):
                request_info['status'] = 'failed'
                request_info['error'] = 'PDF generation failed'
                return

            # PDF generated successfully
            request_info['progress'] = 90
            request_info['pdf_path'] = pdf_path
            request_info['pdf_filename'] = pdf_filename
            request_info['file_size_mb'] = os.path.getsize(pdf_path) / (1024 * 1024)

            # Handle delivery
            delivery_method = request_info['delivery_method']

            if delivery_method == 'push':
                # Make PDF available for download
                request_info['download_url'] = f"http://localhost:8001/reports/{pdf_filename}"
                request_info['expires_at'] = (datetime.now() + timedelta(hours=24)).isoformat()

            elif delivery_method == 'email':
                # Send via email
                email_result = self._send_pdf_email(
                    request_info['email'],
                    pdf_path,
                    profile_name,
                    report_type
                )

                if not email_result.get('success'):
                    request_info['status'] = 'failed'
                    request_info['error'] = f"Email delivery failed: {email_result.get('error')}"
                    return

            # Mark as completed
            request_info['status'] = 'completed'
            request_info['progress'] = 100
            request_info['completed_at'] = datetime.now().isoformat()

            # Move to completed
            self.completed_pdfs[request_id] = pdf_path

            logger.info(f"✅ PDF generation completed: {pdf_filename}")

        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            if request_id in self.active_requests:
                self.active_requests[request_id]['status'] = 'failed'
                self.active_requests[request_id]['error'] = str(e)

    def _generate_report_pdf(self, profile: Dict, snapshot: Dict,
                            historical_data: list, output_path: str,
                            data_range: str) -> Dict[str, Any]:
        """
        Generate PDF report using pdf_exporter

        Args:
            profile: Vehicle profile data
            snapshot: Latest data snapshot
            historical_data: Historical data list
            output_path: Output PDF path
            data_range: Description of data range

        Returns:
            Generation result
        """
        try:
            # Prepare options for PDF exporter
            options = {
                'include_charts': True,
                'history': historical_data[-100:] if len(historical_data) > 100 else historical_data,
                'data_range': data_range,
                'total_records': len(historical_data)
            }

            # Generate master report
            # Note: This assumes PDFExporter has been enhanced to handle these options
            result = self.pdf_exporter.generate_master_report(
                profile=profile,
                snapshot=snapshot,
                ai_module=None,  # Will use internal AI if available
                options=options
            )

            if result.get('success'):
                # Save PDF
                save_result = self.pdf_exporter.save_pdf(output_path)
                if save_result:
                    return {'success': True, 'path': output_path}

            return {'success': False, 'error': 'PDF generation failed'}

        except Exception as e:
            logger.error(f"Error in _generate_report_pdf: {e}")
            return {'success': False, 'error': str(e)}

    def _send_pdf_email(self, recipient_email: str, pdf_path: str,
                       profile_name: str, report_type: str) -> Dict[str, Any]:
        """
        Send PDF via email

        Args:
            recipient_email: Recipient email address
            pdf_path: Path to PDF file
            profile_name: Vehicle profile name
            report_type: 'week' or 'lifetime'

        Returns:
            Send result
        """
        try:
            if not self.email_config.get('enabled'):
                return {'success': False, 'error': 'Email delivery not configured'}

            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            smtp_server = self.email_config['smtp_server']
            smtp_port = self.email_config['smtp_port']

            if not sender_email or not sender_password:
                return {'success': False, 'error': 'Email credentials not configured'}

            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"PREDICT Report - {profile_name} ({report_type.title()} Data)"

            # Email body
            body = f"""
Hello,

Your PREDICT vehicle report is ready!

Vehicle: {profile_name}
Report Type: {report_type.title()} Data
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please find the PDF report attached.

Best regards,
PREDICT Team
            """

            msg.attach(MIMEText(body, 'plain'))

            # Attach PDF
            with open(pdf_path, 'rb') as f:
                pdf_attachment = MIMEBase('application', 'pdf')
                pdf_attachment.set_payload(f.read())

            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(pdf_path)}'
            )
            msg.attach(pdf_attachment)

            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)

            logger.info(f"✅ PDF emailed to {recipient_email}")
            return {'success': True}

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {'success': False, 'error': str(e)}

    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get PDF generation request status

        Args:
            request_id: PDF request ID

        Returns:
            Request status
        """
        if request_id in self.active_requests:
            return self.active_requests[request_id]

        return {'status': 'not_found', 'error': 'Request ID not found'}

    def get_pdf_download_path(self, request_id: str) -> Optional[str]:
        """
        Get PDF file path for download

        Args:
            request_id: PDF request ID

        Returns:
            PDF file path or None
        """
        request_info = self.active_requests.get(request_id)

        if request_info and request_info.get('status') == 'completed':
            return request_info.get('pdf_path')

        return None

    def cleanup_old_pdfs(self, max_age_hours=24):
        """
        Clean up old PDF files

        Args:
            max_age_hours: Maximum age of PDFs to keep (in hours)
        """
        try:
            now = datetime.now()
            cutoff_time = now - timedelta(hours=max_age_hours)

            for filename in os.listdir(self.pdf_output_dir):
                file_path = os.path.join(self.pdf_output_dir, filename)

                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if file_time < cutoff_time:
                        os.remove(file_path)
                        logger.debug(f"Deleted old PDF: {filename}")

            logger.info(f"PDF cleanup completed (older than {max_age_hours}h deleted)")

        except Exception as e:
            logger.error(f"Error cleaning up PDFs: {e}")
