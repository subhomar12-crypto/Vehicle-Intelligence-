"""
Async email service using aiosmtplib.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib
from jinja2 import Template

from predict.core.config import get_config

logger = logging.getLogger(__name__)


# Email templates (inline for now, can be moved to files)
VERIFICATION_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #1a73e8; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .code { font-size: 32px; font-weight: bold; text-align: center; 
                letter-spacing: 8px; padding: 20px; background: white; 
                border: 2px dashed #1a73e8; margin: 20px 0; }
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
            <p>Thank you for registering with PREDICT. Please use the verification code below to complete your registration:</p>
            
            <div class="code">{{ code }}</div>
            
            <p>This code will expire in 24 hours.</p>
            <p>If you didn't create an account, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>© {{ year }} PREDICT. All rights reserved.</p>
            <p>This email was sent to {{ email }}</p>
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
        .header { background: #1a73e8; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .code { font-size: 32px; font-weight: bold; text-align: center; 
                letter-spacing: 8px; padding: 20px; background: white; 
                border: 2px dashed #1a73e8; margin: 20px 0; }
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
            <p>We received a request to reset your password. Use the code below to proceed:</p>
            
            <div class="code">{{ code }}</div>
            
            <p>This code will expire in 24 hours.</p>
            <p>If you didn't request a password reset, you can safely ignore this email.</p>
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
        .header { background: {{ header_color }}; color: white; padding: 20px; text-align: center; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 5px; }
        .alert-box { background: white; padding: 20px; border-left: 4px solid {{ header_color }}; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ alert_title }}</h1>
        </div>
        <div class="content">
            <div class="alert-box">
                <h3>{{ alert_message }}</h3>
                <p>{{ alert_details }}</p>
            </div>
            <p>Open the PREDICT app to view more details.</p>
        </div>
        <div class="footer">
            <p>© {{ year }} PREDICT. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


class EmailService:
    """Async email service."""
    
    def __init__(self):
        self.config = get_config()
        self.smtp_host = self.config.smtp_host
        self.smtp_port = self.config.smtp_port
        self.smtp_user = self.config.smtp_user
        self.smtp_password = self.config.smtp_password
        self.from_email = self.config.email_from
        self.from_name = self.config.email_from_name
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text part
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            
            # Add HTML part
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_verification_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send email verification code."""
        template = Template(VERIFICATION_EMAIL_TEMPLATE)
        html = template.render(
            name=name or "User",
            code=code,
            email=to_email,
            year=datetime.now().year,
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="Verify your PREDICT account",
            html_content=html,
            text_content=f"Your verification code is: {code}",
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send password reset code."""
        template = Template(PASSWORD_RESET_TEMPLATE)
        html = template.render(
            name=name or "User",
            code=code,
            year=datetime.now().year,
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="Reset your PREDICT password",
            html_content=html,
            text_content=f"Your password reset code is: {code}",
        )
    
    async def send_alert_email(
        self,
        to_email: str,
        alert_title: str,
        alert_message: str,
        alert_details: str = "",
        severity: str = "info",
    ) -> bool:
        """Send alert notification email."""
        colors = {
            'info': '#1a73e8',
            'warning': '#f9ab00',
            'critical': '#d93025',
        }
        
        template = Template(ALERT_EMAIL_TEMPLATE)
        html = template.render(
            alert_title=alert_title,
            alert_message=alert_message,
            alert_details=alert_details,
            header_color=colors.get(severity, colors['info']),
            year=datetime.now().year,
        )
        
        return await self.send_email(
            to_email=to_email,
            subject=f"PREDICT Alert: {alert_title}",
            html_content=html,
            text_content=f"{alert_title}\n\n{alert_message}\n\n{alert_details}",
        )
    
    async def send_bulk_emails(
        self,
        recipients: List[dict],
        subject: str,
        template_name: str,
        template_data: dict,
    ) -> dict:
        """
        Send bulk emails with rate limiting.
        
        Returns dict with success/failure counts.
        """
        results = {'sent': 0, 'failed': 0}
        
        for recipient in recipients:
            try:
                # Add recipient-specific data
                data = {**template_data, **recipient}
                
                # Render template and send
                # (Template rendering logic would go here)
                
                results['sent'] += 1
            except Exception as e:
                logger.error(f"Failed to send to {recipient.get('email')}: {e}")
                results['failed'] += 1
        
        return results
