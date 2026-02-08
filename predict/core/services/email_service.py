"""
Async email service using aiosmtplib.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from jinja2 import Template

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
            <p>Use this code to reset your password:</p>
            
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


class EmailService:
    """Async email service."""
    
    def __init__(self):
        self.smtp_host = None  # Will be loaded from config
        self.smtp_port = 587
        self.smtp_user = None
        self.smtp_password = None
        self.from_email = "noreply@previlium.com"
        self.from_name = "PREDICT"
    
    async def send_verification_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send email verification code."""
        try:
            # TODO: Implement actual email sending in Phase 5 with ARQ
            logger.info(f"[EMAIL] Verification code to {to_email}: {code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        to_email: str,
        name: str,
        code: str,
    ) -> bool:
        """Send password reset code."""
        try:
            # TODO: Implement actual email sending in Phase 5 with ARQ
            logger.info(f"[EMAIL] Password reset code to {to_email}: {code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
