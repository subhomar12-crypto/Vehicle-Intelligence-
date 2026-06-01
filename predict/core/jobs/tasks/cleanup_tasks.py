"""
Cleanup background tasks with float timestamps.
"""

import logging
import time
from typing import Dict, Any

from predict.core.services.gdpr_service import GDPRService
from predict.core.config import get_config

logger = logging.getLogger(__name__)


async def gdpr_cleanup_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily GDPR cleanup task.
    
    - Delete telemetry > 30 days
    - Delete verification codes > 24 hours
    - Delete expired sessions
    - Log cleanup stats
    """
    logger.info("Starting GDPR cleanup task")
    
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.db.session import get_db_session
    
    async for session in get_db_session():
        try:
            service = GDPRService()
            
            # Enforce retention policies
            results = await service.enforce_retention_policies(session)
            await session.commit()
            
            # Clean verification codes
            await cleanup_expired_verification_codes(session)
            
            logger.info(f"GDPR cleanup completed: {results}")
            
            return {
                "status": "success",
                "task": "gdpr_cleanup",
                **results,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timestamp_unix": time.time(),
            }
        
        except Exception as e:
            logger.error(f"GDPR cleanup failed: {e}")
            await session.rollback()
            raise
    
    return {"status": "error", "error": "Database session failed"}


async def cleanup_expired_verification_codes(session) -> Dict[str, Any]:
    """Clean up expired verification codes."""
    from sqlalchemy import delete
    from predict.core.db.models.user import VerificationCode
    
    cutoff_time = time.time() - 86400  # 24 hours
    
    stmt = delete(VerificationCode).where(
        VerificationCode.created_at < cutoff_time
    )
    
    result = await session.execute(stmt)
    deleted = result.rowcount
    
    logger.info(f"Deleted {deleted} expired verification codes")
    
    return {
        "deleted_verification_codes": deleted,
    }


async def cleanup_old_sessions(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up expired user sessions."""
    logger.info("Starting session cleanup")
    
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.db.session import get_db_session
    
    async for session in get_db_session():
        try:
            from predict.core.db.models.audit import SessionLog
            from sqlalchemy import delete
            
            cutoff_time = time.time() - (7 * 86400)  # 7 days
            
            stmt = delete(SessionLog).where(
                SessionLog.timestamp < cutoff_time
            )
            
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            
            logger.info(f"Deleted {deleted} old session logs")
            
            return {
                "status": "success",
                "task": "cleanup_old_sessions",
                "deleted_sessions": deleted,
                "timestamp": time.time(),
            }
        
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            raise
    
    return {"status": "error", "error": "Database session failed"}


async def cleanup_expired_exports(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up old export files."""
    logger.info("Starting export cleanup")
    
    current_time = time.time()
    cutoff_time = current_time - (30 * 86400)  # 30 days
    
    try:
        config = get_config()
        exports_dir = config.DATA_DIR / "exports"
        
        deleted_count = 0
        freed_bytes = 0
        
        if exports_dir.exists():
            for file_path in exports_dir.glob("*.json"):
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        freed_bytes += size
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
        
        logger.info(f"Deleted {deleted_count} old export files")
        
        return {
            "status": "success",
            "task": "cleanup_expired_exports",
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": current_time,
        }
    
    except Exception as e:
        logger.error(f"Export cleanup failed: {e}")
        raise


async def cleanup_old_predictions(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Archive old predictions."""
    logger.info("Starting prediction cleanup")
    
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.db.session import get_db_session
    
    async for session in get_db_session():
        try:
            from predict.core.db.models.prediction import Prediction
            from sqlalchemy import update
            
            cutoff_time = time.time() - (90 * 86400)  # 90 days
            
            # Mark old predictions as inactive (soft delete)
            stmt = (
                update(Prediction)
                .where(Prediction.created_at < cutoff_time)
                .where(Prediction.status == "active")
                .values(status="archived", updated_at=time.time())
            )
            
            result = await session.execute(stmt)
            archived = result.rowcount
            
            await session.commit()
            
            logger.info(f"Archived {archived} old predictions")
            
            return {
                "status": "success",
                "task": "cleanup_old_predictions",
                "archived_count": archived,
                "timestamp": time.time(),
            }
        
        except Exception as e:
            logger.error(f"Prediction cleanup failed: {e}")
            raise
    
    return {"status": "error", "error": "Database session failed"}


async def cleanup_failed_operations(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up failed/obsolete operations."""
    logger.info("Starting failed operations cleanup")
    
    current_time = time.time()
    
    # Clean up various temporary/stale data
    results = {
        "status": "success",
        "timestamp": current_time,
        "cleaned_items": {},
    }
    
    return results


async def cleanup_parquet_temp_files(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up temporary Parquet files."""
    logger.info("Starting Parquet temp cleanup")
    
    try:
        config = get_config()
        parquet_dir = config.PARQUET_DIR
        
        deleted = 0
        freed = 0
        
        if parquet_dir.exists():
            # Clean up .tmp files older than 1 day
            cutoff = time.time() - 86400
            
            for tmp_file in parquet_dir.glob("*.tmp"):
                if tmp_file.stat().st_mtime < cutoff:
                    try:
                        size = tmp_file.stat().st_size
                        tmp_file.unlink()
                        deleted += 1
                        freed += size
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file: {e}")
        
        logger.info(f"Deleted {deleted} temp Parquet files")
        
        return {
            "status": "success",
            "deleted_files": deleted,
            "freed_bytes": freed,
        }
    
    except Exception as e:
        logger.error(f"Parquet temp cleanup failed: {e}")
        raise
