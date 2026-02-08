"""
Job queue helper functions.

Enqueue background jobs with simple async functions.
"""

import logging
from typing import Optional

from arq import create_pool
from arq.connections import RedisSettings

from predict.core.config import get_config
from predict.core.jobs.worker import JobQueues

logger = logging.getLogger(__name__)

_pool = None


async def _get_pool():
    """Get or create ARQ pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_config().REDIS_URL))
    return _pool


async def enqueue_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> str:
    """
    Enqueue email for background sending.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "send_email",
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        _queue_name=JobQueues.EMAIL,
    )
    logger.info(f"Enqueued email to {to_email}, job_id={job.job_id}")
    return job.job_id


async def enqueue_verification_email(to_email: str, name: str, code: str) -> str:
    """Enqueue verification email."""
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "send_verification_email",
        to_email=to_email,
        name=name,
        code=code,
        _queue_name=JobQueues.EMAIL,
    )
    return job.job_id


async def enqueue_password_reset_email(to_email: str, name: str, code: str) -> str:
    """Enqueue password reset email."""
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "send_password_reset_email",
        to_email=to_email,
        name=name,
        code=code,
        _queue_name=JobQueues.EMAIL,
    )
    return job.job_id


async def enqueue_fcm(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> str:
    """
    Enqueue FCM push notification.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "send_push_notification",
        fcm_token=fcm_token,
        title=title,
        body=body,
        data=data,
        _queue_name=JobQueues.FCM,
    )
    logger.info(f"Enqueued FCM notification, job_id={job.job_id}")
    return job.job_id


async def enqueue_guardian_alert(
    guardian_fcm_token: str,
    alert_type: str,
    vehicle_name: str,
    details: str,
) -> str:
    """Enqueue guardian alert notification."""
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "send_guardian_alert",
        guardian_fcm_token=guardian_fcm_token,
        alert_type=alert_type,
        vehicle_name=vehicle_name,
        details=details,
        _queue_name=JobQueues.FCM,
    )
    return job.job_id


async def enqueue_pdf(
    user_id: int,
    vehicle_profile_id: int,
    report_type: str,
    output_path: str,
) -> str:
    """
    Enqueue PDF report generation.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "generate_vehicle_report",
        user_id=user_id,
        vehicle_profile_id=vehicle_profile_id,
        report_type=report_type,
        output_path=output_path,
        _queue_name=JobQueues.PDF,
    )
    logger.info(f"Enqueued PDF generation, job_id={job.job_id}")
    return job.job_id


async def enqueue_backup() -> str:
    """
    Enqueue database backup.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "backup_database",
        _queue_name=JobQueues.BACKUP,
    )
    logger.info(f"Enqueued database backup, job_id={job.job_id}")
    return job.job_id
