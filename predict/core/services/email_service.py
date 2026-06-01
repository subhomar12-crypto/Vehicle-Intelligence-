"""
Async email service using aiosmtplib.

Handles:
- SMTP email delivery with TLS
- HTML and plain text emails
- Verification and password reset emails
- Circuit breaker for SMTP failures
"""

import logging
import time
from typing import Optional, List, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from jinja2 import Template

from predict.core.config import get_config
from predict.core.monitoring.circuit_breaker import circuit_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


# Email templates (inline for now, can be moved to files)
VERIFICATION_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #C40000; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .code { font-size: 32px; font-weight: bold; text-align: center; 
                letter-spacing: 8px; padding: 20px; background: white; 
                border: 2px dashed #C40000; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PREDICT</h1>
            <p>Vehicle Intelligence Platform</p>
        </div>
        <div class="content">
            <h2>Verify Your Email</h2>
            <p>Hi {{ name }},</p>
            <p>Thank you for registering with PREDICT. Please use the verification code below:</p>
            
            <div class="code">{{ code }}</div>
            
            <p>This code will expire in 24 hours.</p>
        </div>
        <div class="footer">
            <p>© {{ year }} PREDICT. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

PASSWORD_RESET_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #C40000; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .code { font-size: 32px; font-weight: bold; text-align: center; 
                letter-spacing: 8px; padding: 20px; background: white; 
                border: 2px dashed #C40000; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PREDICT</h1>
            <p>Vehicle Intelligence Platform</p>
        </div>
        <div class="content">
            <h2>Password Reset</h2>
            <p>Hi {{ name }},</p>
            <p>Use this code to reset your password:</p>
            
            <div class="code">{{ code }}</div>
            
            <p>This code will expire in 1 hour.</p>
        </div>
        <div class="footer">
            <p>© {{ year }} PREDICT. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

ALERT_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #C40000; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .alert-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }
        .severity-high { background: #f8d7da; border-left-color: #dc3545; }
        .severity-medium { background: #fff3cd; border-left-color: #ffc107; }
        .severity-low { background: #d1ecf1; border-left-color: #17a2b8; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PREDICT Alert</h1>
            <p>Vehicle Intelligence Platform</p>
        </div>
        <div class="content">
            <h2>{{ alert_title }}</h2>
            <div class="alert-box severity-{{ severity }}">
                <p><strong>Vehicle:</strong> {{ vehicle_name }}</p>
                <p><strong>Alert Type:</strong> {{ alert_type }}</p>
                <p><strong>Time:</strong> {{ timestamp }}</p>
                <p>{{ alert_message }}</p>
            </div>
            <p>Please check your PREDICT app for more details.</p>
        </div>
        <div class="footer">
            <p>© {{ year }} PREDICT. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


REPORT_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #C40000; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .highlights { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; }
        .score { font-size: 36px; font-weight: bold; color: #C40000; text-align: center; }
        .score-label { text-align: center; color: #666; font-size: 14px; }
        .stat { display: inline-block; text-align: center; margin: 0 15px; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PREDICT</h1>
            <p>Vehicle Intelligence Platform</p>
        </div>
        <div class="content">
            <h2>Your Report is Ready</h2>
            <p>Hi {{ name }},</p>
            <p>Your <strong>{{ report_type }}</strong> report for <strong>{{ vehicle_name }}</strong> is ready.</p>

            <div class="highlights">
                <div class="score">{{ health_score }}/100</div>
                <div class="score-label">Health Score</div>
                <p style="text-align: center; color: #666; margin-top: 10px;">
                    {{ components_analyzed }} components analyzed
                </p>
            </div>

            <p>The full PDF report is attached to this email.</p>
            <p>You can also download it from the PREDICT app: <strong>Reports → History</strong></p>
        </div>
        <div class="footer">
            <p>&copy; {{ year }} PREDICT. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


class EmailService:
    """Async email service with circuit breaker protection."""
    
    def __init__(self):
        self.config = get_config()
        self.smtp_host = getattr(self.config, 'SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(getattr(self.config, 'SMTP_PORT', 587))
        self.smtp_user = getattr(self.config, 'SMTP_USER', None) or getattr(self.config, 'smtp_user', None)
        self.smtp_password = getattr(self.config, 'SMTP_PASSWORD', None) or getattr(self.config, 'smtp_password', None)
        self.from_email = getattr(self.config, 'FROM_EMAIL', 'noreply@previlium.com') or getattr(self.config, 'from_email', 'noreply@previlium.com')
        self.from_name = getattr(self.config, 'FROM_NAME', 'PREDICT') or "PREDICT"
        
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured - emails will be logged only")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
        
        Returns:
            True if sent successfully
        """
        if not self.smtp_user or not self.smtp_password:
            logger.info(f"[EMAIL LOGGED - NO SMTP] To: {to_email}, Subject: {subject}")
            return True
        
        try:
            # Import here to avoid dependency if not used
            import aiosmtplib
            
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # Attach plain text
            msg.attach(MIMEText(body, "plain"))
            
            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Send via SMTP with circuit breaker
            # Port 587 uses STARTTLS, port 465 uses TLS
            use_tls = self.smtp_port == 465
            start_tls = self.smtp_port == 587
            
            @circuit_breaker("smtp", failure_threshold=3, recovery_timeout=60.0)
            async def _send():
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    use_tls=use_tls,
                    start_tls=start_tls,
                )
            
            await _send()
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except CircuitBreakerOpen:
            logger.error(f"SMTP circuit breaker open - cannot send email to {to_email}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Tuple[str, bytes, str]]] = None,
    ) -> bool:
        """
        Send an email with optional file attachments.

        Args:
            attachments: list of (filename, data_bytes, mime_type) tuples
        """
        if not self.smtp_user or not self.smtp_password:
            logger.info(f"[EMAIL LOGGED - NO SMTP] To: {to_email}, Subject: {subject}, attachments={len(attachments or [])}")
            return True

        try:
            import aiosmtplib

            msg = MIMEMultipart("mixed")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            # Text/HTML body as alternative sub-part
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(body, "plain"))
            if html_body:
                body_part.attach(MIMEText(html_body, "html"))
            msg.attach(body_part)

            # Attachments
            for filename, data, mime_type in (attachments or []):
                maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
                part = MIMEBase(maintype, subtype)
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)

            use_tls = self.smtp_port == 465
            start_tls = self.smtp_port == 587

            @circuit_breaker("smtp", failure_threshold=3, recovery_timeout=60.0)
            async def _send():
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    use_tls=use_tls,
                    start_tls=start_tls,
                )

            await _send()
            logger.info(f"Email with attachment sent to {to_email}: {subject}")
            return True

        except CircuitBreakerOpen:
            logger.error(f"SMTP circuit breaker open - cannot send email to {to_email}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email with attachment to {to_email}: {e}")
            return False

    async def send_report_email(
        self,
        to_email: str,
        name: str,
        vehicle_name: str,
        report_type: str,
        health_score: int = 0,
        components_analyzed: int = 0,
        pdf_bytes: Optional[bytes] = None,
    ) -> bool:
        """Send report-ready email with PDF attachment."""
        template = Template(REPORT_EMAIL_TEMPLATE)
        html_body = template.render(
            name=name,
            report_type=report_type.replace("_", " ").title(),
            vehicle_name=vehicle_name,
            health_score=health_score,
            components_analyzed=components_analyzed,
            year=time.strftime("%Y"),
        )

        plain_body = (
            f"Hi {name},\n\n"
            f"Your {report_type} report for {vehicle_name} is ready.\n"
            f"Health Score: {health_score}/100 — {components_analyzed} components analyzed.\n\n"
            f"The full PDF report is attached.\n"
            f"You can also download it from the PREDICT app: Reports → History\n\n"
            f"© {time.strftime('%Y')} PREDICT"
        )

        attachments = []
        if pdf_bytes:
            filename = f"PREDICT_{report_type}_{vehicle_name.replace(' ', '_')}.pdf"
            attachments.append((filename, pdf_bytes, "application/pdf"))

        return await self.send_email_with_attachment(
            to_email=to_email,
            subject=f"Your PREDICT {report_type.title()} Report is Ready",
            body=plain_body,
            html_body=html_body,
            attachments=attachments,
        )

    async def send_verification_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send email verification code."""
        template = Template(VERIFICATION_EMAIL_TEMPLATE)
        html_body = template.render(name=name, code=code, year=time.strftime("%Y"))
        
        plain_body = f"""
Hi {name},

Your PREDICT verification code is: {code}

This code will expire in 24 hours.

© {time.strftime("%Y")} PREDICT
"""
        
        return await self.send_email(
            to_email=to_email,
            subject="Verify Your Email - PREDICT",
            body=plain_body,
            html_body=html_body,
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send password reset code."""
        template = Template(PASSWORD_RESET_TEMPLATE)
        html_body = template.render(name=name, code=code, year=time.strftime("%Y"))
        
        plain_body = f"""
Hi {name},

Your PREDICT password reset code is: {code}

This code will expire in 1 hour.

© {time.strftime("%Y")} PREDICT
"""
        
        return await self.send_email(
            to_email=to_email,
            subject="Password Reset - PREDICT",
            body=plain_body,
            html_body=html_body,
        )
    
    async def send_alert_email(
        self,
        to_email: str,
        alert_data: dict,
    ) -> bool:
        """Send guardian alert email."""
        template = Template(ALERT_EMAIL_TEMPLATE)
        html_body = template.render(
            alert_title=alert_data.get('title', 'Vehicle Alert'),
            vehicle_name=alert_data.get('vehicle_name', 'Unknown Vehicle'),
            alert_type=alert_data.get('type', 'General'),
            severity=alert_data.get('severity', 'medium'),
            alert_message=alert_data.get('message', ''),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            year=time.strftime("%Y"),
        )
        
        plain_body = f"""
PREDICT Alert

Vehicle: {alert_data.get('vehicle_name', 'Unknown')}
Alert Type: {alert_data.get('type', 'General')}
Severity: {alert_data.get('severity', 'medium')}

{alert_data.get('message', '')}

Please check your PREDICT app for more details.
"""
        
        return await self.send_email(
            to_email=to_email,
            subject=f"PREDICT Alert: {alert_data.get('title', 'Vehicle Alert')}",
            body=plain_body,
            html_body=html_body,
        )
    
    async def send_api_key_email(
        self,
        to_email: str,
        name: str,
        api_key: str,
        car_plate: str = "",
    ) -> bool:
        """Send API key email to verified customer."""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-size: 28px; font-weight: bold; color: #C40000; }}
        .success {{ background-color: #d4edda; color: #155724; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0; }}
        .key-box {{ background-color: #1a1a2e; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
        .api-key {{ font-size: 18px; font-family: 'Courier New', monospace; color: #00ff88; word-break: break-all; }}
        .info-box {{ background-color: #f8f9fa; border-left: 4px solid #C40000; padding: 15px; margin: 20px 0; }}
        .message {{ color: #333; line-height: 1.6; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; color: #666; font-size: 12px; }}
        .warning {{ color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 20px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">PREDICT AI</div>
            <p>Vehicle Diagnostics & Predictions</p>
        </div>

        <div class="success">
            Email Verified Successfully!
        </div>

        <div class="message">
            <p>Hello {name},</p>
            <p>Your email has been verified. Here is your API key to connect your vehicle apps:</p>
        </div>

        <div class="key-box">
            <p style="color: #888; margin-bottom: 10px;">Your API Key</p>
            <div class="api-key">{api_key}</div>
        </div>

        <div class="info-box">
            {f"<strong>Vehicle:</strong> {car_plate}<br>" if car_plate else ""}
            <strong>Account Status:</strong> Free Tier
        </div>

        <div class="message">
            <p><strong>How to use your API key:</strong></p>
            <ol>
                <li>Open the PREDICT OBD app</li>
                <li>Go to Settings - API Connection</li>
                <li>Paste your API key</li>
                <li>Start monitoring your vehicle!</li>
            </ol>
        </div>

        <div class="warning">
            Keep your API key secure! Do not share it with anyone. If compromised, contact support for a new key.
        </div>

        <div class="footer">
            <p>© {time.strftime("%Y")} PREDICT AI - Professional Vehicle Diagnostics</p>
            <p>This is an automated message, please do not reply.</p>
        </div>
    </div>
</body>
</html>
"""

        plain_body = f"""
Hi {name},

Your email has been verified successfully!

Your API Key: {api_key}

{f'Vehicle: {car_plate}' if car_plate else ''}
Account Status: Free Tier

How to use your API key:
1. Open the PREDICT OBD app
2. Go to Settings - API Connection  
3. Paste your API key
4. Start monitoring your vehicle!

Keep your API key secure! Do not share it with anyone.

© {time.strftime("%Y")} PREDICT AI
"""

        return await self.send_email(
            to_email=to_email,
            subject="Your PREDICT API Key",
            body=plain_body,
            html_body=html_body,
        )

    async def send_welcome_email(
        self,
        to_email: str,
        name: str,
    ) -> bool:
        """Send welcome email after registration."""
        plain_body = f"""
Hi {name},

Welcome to PREDICT - your vehicle intelligence platform!

With PREDICT, you can:
- Monitor your vehicle's health in real-time
- Receive predictive maintenance alerts
- Track driving behavior and trip history
- Access AI-powered diagnostics

Get started by connecting your OBD-II device.

© {time.strftime("%Y")} PREDICT
"""
        
        return await self.send_email(
            to_email=to_email,
            subject="Welcome to PREDICT",
            body=plain_body,
        )
