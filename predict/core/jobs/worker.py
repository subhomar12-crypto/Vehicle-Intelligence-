"""
ARQ worker configuration.

Background job processing with:
- Redis as message broker
- Retry with exponential backoff
- Dead letter queue for failed jobs
- Cron schedules for recurring tasks
"""

import logging
from typing import List

from arq import create_pool, ArqRedis
from arq.connections import RedisSettings

from predict.core.config import get_config

logger = logging.getLogger(__name__)

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 60  # seconds


class JobQueues:
    """Job queue names."""
    EMAIL = "email"
    FCM = "fcm"
    PDF = "pdf"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    PARQUET = "parquet"


async def get_arq_pool() -> ArqRedis:
    """Get ARQ Redis pool."""
    config = get_config()
    redis_settings = RedisSettings.from_dsn(config.REDIS_URL)
    return await create_pool(redis_settings)


async def close_arq_pool(pool: ArqRedis) -> None:
    """Close ARQ Redis pool."""
    await pool.close()


# Import all task functions for registration
from predict.core.jobs.tasks.email_tasks import (
    send_email,
    send_verification_email,
    send_password_reset_email,
    send_bulk_emails,
)

from predict.core.jobs.tasks.fcm_tasks import (
    send_push_notification,
    send_bulk_push,
    send_guardian_alert,
    update_fcm_token,
    cleanup_invalid_tokens,
)

from predict.core.jobs.tasks.backup_tasks import (
    backup_database,
    cleanup_old_backups,
    verify_backup,
    upload_backup_to_cloud,
    daily_backup_task,
)

from predict.core.jobs.tasks.cleanup_tasks import (
    gdpr_cleanup_task,
    cleanup_old_sessions,
    cleanup_expired_exports,
    cleanup_old_predictions,
    cleanup_failed_operations,
    cleanup_parquet_temp_files,
)

from predict.core.jobs.tasks.parquet_tasks import (
    flush_parquet_buffer,
    compact_parquet_files,
    archive_old_parquet,
)

from predict.core.jobs.tasks.pdf_tasks import (
    generate_health_report_pdf,
    generate_diagnostic_report_pdf,
    generate_enhanced_report_job,
)

from predict.core.jobs.tasks.training_tasks import (
    check_and_start_training,
)

from predict.core.jobs.tasks.self_validation import (
    self_validation_job,
)

from predict.core.jobs.tasks.fleet_learning import (
    fleet_learning_job,
)


# Worker function registry
WORKER_FUNCTIONS = [
    # Email tasks
    send_email,
    send_verification_email,
    send_password_reset_email,
    send_bulk_emails,
    
    # FCM tasks
    send_push_notification,
    send_bulk_push,
    send_guardian_alert,
    update_fcm_token,
    cleanup_invalid_tokens,
    
    # Backup tasks
    backup_database,
    cleanup_old_backups,
    verify_backup,
    upload_backup_to_cloud,
    daily_backup_task,
    
    # Cleanup tasks
    gdpr_cleanup_task,
    cleanup_old_sessions,
    cleanup_expired_exports,
    cleanup_old_predictions,
    cleanup_failed_operations,
    cleanup_parquet_temp_files,
    
    # Parquet tasks
    flush_parquet_buffer,
    compact_parquet_files,
    archive_old_parquet,
    
    # PDF tasks
    generate_health_report_pdf,
    generate_diagnostic_report_pdf,
    generate_enhanced_report_job,
    
    # Training tasks
    check_and_start_training,

    # Intelligence engine v2 jobs
    self_validation_job,
    fleet_learning_job,
]


class WorkerSettings:
    """
    ARQ worker settings.
    
    Usage:
        arq predict.core.jobs.worker.WorkerSettings
    """
    
    # Redis connection from config
    redis_settings = RedisSettings.from_dsn(get_config().REDIS_URL)
    
    # Job functions
    functions: List = WORKER_FUNCTIONS
    
    # Cron jobs
    cron_jobs = [
        # Run daily backup at 3 AM
        {
            "name": "daily_backup",
            "cron": "0 3 * * *",
            "function": daily_backup_task,
        },
        # Run GDPR cleanup at 4 AM
        {
            "name": "gdpr_cleanup",
            "cron": "0 4 * * *",
            "function": gdpr_cleanup_task,
        },
        # Flush Parquet buffer every 6 hours
        {
            "name": "flush_parquet",
            "cron": "0 */6 * * *",
            "function": flush_parquet_buffer,
        },
        # Cleanup failed operations hourly
        {
            "name": "cleanup_failed_ops",
            "cron": "0 * * * *",
            "function": cleanup_failed_operations,
        },
        # Check AI training schedule every 15 minutes
        {
            "name": "ai_training_check",
            "cron": "*/15 * * * *",
            "function": check_and_start_training,
        },
        # Prediction self-validation (compare snapshots vs feedback) — nightly 2 AM
        {
            "name": "self_validation",
            "cron": "0 2 * * *",
            "function": self_validation_job,
        },
        # Fleet learning (aggregate fleet-wide penalty calibration) — nightly 2:30 AM
        {
            "name": "fleet_learning",
            "cron": "30 2 * * *",
            "function": fleet_learning_job,
        },
    ]
    
    # Retry settings
    max_tries = DEFAULT_MAX_RETRIES
    retry_delay = DEFAULT_RETRY_DELAY
    
    # Worker behavior
    handle_signals = True
    
    # Logging
    log_level = logging.INFO
    
    # Job timeout (5 minutes)
    job_timeout = 300
    
    # Maximum jobs to run concurrently
    max_jobs = 10
    
    # Keep results for 1 hour
    keep_result = 3600
    
    # Health check interval
    health_check_interval = 30


async def startup(ctx):
    """Worker startup handler."""
    logger.info("ARQ worker starting up...")
    ctx["config"] = get_config()


async def shutdown(ctx):
    """Worker shutdown handler."""
    logger.info("ARQ worker shutting down...")


# Update worker settings with lifecycle handlers
WorkerSettings.on_startup = startup
WorkerSettings.on_shutdown = shutdown
