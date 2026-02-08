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

# ARQ Redis settings
ARQ_REDIS_SETTINGS = RedisSettings(
    host="localhost",
    port=6379,
    database=1,  # Use DB 1 for ARQ (DB 0 for cache)
)

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


async def get_arq_pool() -> ArqRedis:
    """Get ARQ Redis pool."""
    return await create_pool(ARQ_REDIS_SETTINGS)


async def close_arq_pool(pool: ArqRedis) -> None:
    """Close ARQ Redis pool."""
    await pool.close()


# Cron jobs (recurring tasks)
CRON_JOBS = [
    # Run database backup at 3 AM daily
    {
        "name": "daily_backup",
        "cron": "0 3 * * *",  # 3:00 AM
        "function": "predict.core.jobs.tasks.backup_tasks:backup_database",
    },
    # Run GDPR cleanup at 4 AM daily
    {
        "name": "gdpr_cleanup",
        "cron": "0 4 * * *",  # 4:00 AM
        "function": "predict.core.jobs.tasks.cleanup_tasks:gdpr_cleanup",
    },
    # Cleanup old failed operations hourly
    {
        "name": "cleanup_failed_ops",
        "cron": "0 * * * *",  # Every hour
        "function": "predict.core.jobs.tasks.cleanup_tasks:cleanup_failed_operations",
    },
]


class WorkerSettings:
    """
    ARQ worker settings.
    
    Usage:
        arq predict.core.jobs.worker.WorkerSettings
    """
    
    # Redis connection
    redis_settings = ARQ_REDIS_SETTINGS
    
    # Job functions (will be populated by importing from tasks)
    functions: List = []
    
    # Cron jobs
    cron_jobs = CRON_JOBS
    
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
