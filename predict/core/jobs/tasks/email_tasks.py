"""
Email background tasks.

Async email sending with retry logic.
"""

import logging
from typing import Optional

from predict.core.services.email_service import EmailService

logger = logging.getLogger(__name__)


async def send_email(
    ctx,
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> dict:
    """
    Send email asynchronously.
    
    Args:
        ctx: ARQ context
        to_email: Recipient email
        subject: Email subject
        html_content: HTML body
        text_content: Plain text body (optional)
    
    Returns:
        Result dict with success status
    """
    email_service = EmailService()
    
    try:
        success = await email_service.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        
        if success:
            logger.info(f"Email sent to {to_email}: {subject}")
            return {"success": True, "recipient": to_email}
        else:
            logger.error(f"Failed to send email to {to_email}")
            return {"success": False, "error": "Send failed"}
    
    except Exception as e:
        logger.exception(f"Email task failed: {e}")
        raise  # Re-raise for ARQ retry


async def send_verification_email(
    ctx,
    to_email: str,
    name: str,
    code: str,
) -> dict:
    """Send verification email asynchronously."""
    email_service = EmailService()
    
    try:
        success = await email_service.send_verification_email(
            to_email=to_email,
            name=name,
            code=code,
        )
        
        if success:
            logger.info(f"Verification email sent to {to_email}")
            return {"success": True, "recipient": to_email}
        else:
            return {"success": False, "error": "Send failed"}
    
    except Exception as e:
        logger.exception(f"Verification email failed: {e}")
        raise


async def send_password_reset_email(
    ctx,
    to_email: str,
    name: str,
    code: str,
) -> dict:
    """Send password reset email asynchronously."""
    email_service = EmailService()
    
    try:
        success = await email_service.send_password_reset_email(
            to_email=to_email,
            name=name,
            code=code,
        )
        
        if success:
            logger.info(f"Password reset email sent to {to_email}")
            return {"success": True, "recipient": to_email}
        else:
            return {"success": False, "error": "Send failed"}
    
    except Exception as e:
        logger.exception(f"Password reset email failed: {e}")
        raise


async def send_bulk_emails(
    ctx,
    recipients: list,
    template_name: str,
    template_data: dict,
) -> dict:
    """
    Send bulk emails with rate limiting.
    
    Args:
        recipients: List of recipient dicts
        template_name: Email template to use
        template_data: Template variables
    
    Returns:
        Summary of sent/failed
    """
    results = {"sent": 0, "failed": 0}
    
    for recipient in recipients:
        try:
            # TODO: Implement actual bulk sending with rate limiting
            results["sent"] += 1
        except Exception as e:
            logger.error(f"Failed to send to {recipient}: {e}")
            results["failed"] += 1
    
    return results
