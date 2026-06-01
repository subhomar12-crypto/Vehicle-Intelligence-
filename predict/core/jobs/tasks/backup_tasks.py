"""
Backup background tasks with float timestamps.
"""

import logging
import time
from typing import Dict, Any
from pathlib import Path

from predict.core.services.backup_service import BackupService
from predict.core.config import get_config

logger = logging.getLogger(__name__)


async def backup_database(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create database backup.
    
    Args:
        ctx: ARQ context
    
    Returns:
        Backup result dict
    """
    logger.info("Starting database backup")
    
    start_time = time.perf_counter()
    
    try:
        service = BackupService()
        result = await service.create_database_backup()
        
        if result.success:
            elapsed_sec = time.perf_counter() - start_time
            
            logger.info(
                f"Database backup completed: {result.backup_path} "
                f"({result.size_bytes:,} bytes)"
            )
            
            return {
                "status": "success",
                "task": "backup_database",
                "filename": Path(result.backup_path).name,
                "filepath": str(result.backup_path),
                "file_size_bytes": result.size_bytes,
                "duration_seconds": elapsed_sec,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timestamp_unix": time.time(),
            }
        else:
            logger.error(f"Database backup failed: {result.error_message}")
            raise Exception(result.error_message or "Backup failed")
    
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        raise


async def cleanup_old_backups(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Delete backups older than retention period."""
    logger.info("Starting backup cleanup")
    
    current_time = time.time()
    
    try:
        service = BackupService()
        result = await service.cleanup_old_backups(
            retention_days=30,
            dry_run=False,
        )
        
        logger.info(
            f"Deleted {result['deleted_count']} old backups, "
            f"freed {result['space_freed_bytes']:,} bytes"
        )
        
        return {
            "status": "success",
            "task": "cleanup_old_backups",
            "deleted_count": result["deleted_count"],
            "freed_bytes": result["space_freed_bytes"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": current_time,
        }
    
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")
        raise


async def verify_backup(ctx: Dict[str, Any], backup_path: str) -> Dict[str, Any]:
    """Verify a backup file is valid."""
    logger.info(f"Verifying backup: {backup_path}")
    
    start_time = time.perf_counter()
    verify_timestamp = time.time()
    
    try:
        path = Path(backup_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        # Check file integrity (size > 0)
        file_size = path.stat().st_size
        is_valid = file_size > 0
        
        # Try to verify gzip integrity if .gz file
        if path.suffix == ".gz":
            import gzip
            try:
                with gzip.open(path, 'rb') as f:
                    # Read first 1KB to verify it's valid gzip
                    f.read(1024)
            except gzip.BadGzipFile:
                is_valid = False
        
        elapsed_sec = time.perf_counter() - start_time
        
        return {
            "status": "success" if is_valid else "failed",
            "task": "verify_backup",
            "backup_path": backup_path,
            "file_size_bytes": file_size,
            "is_valid": is_valid,
            "duration_seconds": elapsed_sec,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": verify_timestamp,
        }
    
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
        raise


async def upload_backup_to_cloud(ctx: Dict[str, Any], backup_path: str, provider: str = "s3") -> Dict[str, Any]:
    """Upload backup to cloud storage."""
    logger.info(f"Uploading backup to {provider}: {backup_path}")
    
    try:
        service = BackupService()
        path = Path(backup_path)
        
        success = await service.upload_to_cloud(path, provider)
        
        return {
            "status": "success" if success else "failed",
            "backup_path": backup_path,
            "provider": provider,
            "timestamp": time.time(),
        }
    
    except Exception as e:
        logger.error(f"Cloud upload failed: {e}")
        raise


async def daily_backup_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Daily backup task - creates backup and cleans old ones."""
    logger.info("Running daily backup task")
    
    # Create backup
    backup_result = await backup_database(ctx)
    
    # Cleanup old backups
    cleanup_result = await cleanup_old_backups(ctx)
    
    return {
        "status": "success",
        "backup": backup_result,
        "cleanup": cleanup_result,
        "timestamp": time.time(),
    }
