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
        config = get_config()
        _pool = await create_pool(RedisSettings.from_dsn(config.REDIS_URL))
    return _pool


async def close_pool():
    """Close the ARQ pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


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
    channel_id: Optional[str] = None,
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
        channel_id=channel_id,
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


async def enqueue_pdf_report(
    vehicle_id: int,
    report_type: str = "health",
    report_data: Optional[dict] = None,
) -> str:
    """
    Enqueue PDF report generation.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    
    if report_type == "diagnostic":
        job = await pool.enqueue_job(
            "generate_diagnostic_report_pdf",
            vehicle_id=vehicle_id,
            dtc_data=report_data or {},
            _queue_name=JobQueues.PDF,
        )
    else:
        job = await pool.enqueue_job(
            "generate_health_report_pdf",
            vehicle_id=vehicle_id,
            report_data=report_data or {},
            _queue_name=JobQueues.PDF,
        )
    
    logger.info(f"Enqueued PDF generation, job_id={job.job_id}")
    return job.job_id


async def enqueue_enhanced_report(
    report_id: int,
    vehicle_id: int,
    report_type: str,
    user_id: int,
    trip_id: Optional[int] = None,
    include_ai_predictions: bool = False,
) -> str:
    """
    Enqueue enhanced LLM-powered PDF report generation.

    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "generate_enhanced_report_job",
        report_id=report_id,
        vehicle_id=vehicle_id,
        report_type=report_type,
        user_id=user_id,
        trip_id=trip_id,
        include_ai_predictions=include_ai_predictions,
        _queue_name=JobQueues.PDF,
    )
    logger.info(f"Enqueued enhanced report {report_id}, job_id={job.job_id}")
    return job.job_id


async def enqueue_backup() -> str:
    """
    Enqueue database backup.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "daily_backup_task",
        _queue_name=JobQueues.BACKUP,
    )
    logger.info(f"Enqueued database backup, job_id={job.job_id}")
    return job.job_id


async def enqueue_parquet_flush() -> str:
    """
    Enqueue Parquet buffer flush.
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    job = await pool.enqueue_job(
        "flush_parquet_buffer",
        _queue_name=JobQueues.PARQUET,
    )
    logger.info(f"Enqueued Parquet flush, job_id={job.job_id}")
    return job.job_id


async def enqueue_cleanup(cleanup_type: str = "gdpr") -> str:
    """
    Enqueue cleanup task.
    
    Args:
        cleanup_type: Type of cleanup (gdpr, sessions, exports, predictions)
    
    Returns:
        Job ID for tracking
    """
    pool = await _get_pool()
    
    task_map = {
        "gdpr": "gdpr_cleanup_task",
        "sessions": "cleanup_old_sessions",
        "exports": "cleanup_expired_exports",
        "predictions": "cleanup_old_predictions",
        "failed_ops": "cleanup_failed_operations",
        "parquet_temp": "cleanup_parquet_temp_files",
    }
    
    task_name = task_map.get(cleanup_type, "gdpr_cleanup_task")
    
    job = await pool.enqueue_job(
        task_name,
        _queue_name=JobQueues.CLEANUP,
    )
    logger.info(f"Enqueued {cleanup_type} cleanup, job_id={job.job_id}")
    return job.job_id
