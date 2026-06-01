"""
Backup service for database and data protection.

Handles:
- Automated database backups via pg_dump
- File backups (models, logs, parquet)
- Backup rotation and retention
- Restore operations
- Cloud upload integration
"""

import asyncio
import logging
import os
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import aiofiles
import httpx

from predict.core.config import get_config
from predict.core.monitoring.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class BackupResult:
    """Result of a backup operation."""
    success: bool
    backup_path: Optional[Path] = None
    size_bytes: int = 0
    duration_sec: float = 0.0
    error_message: Optional[str] = None
    uploaded_to_cloud: bool = False


class BackupService:
    """Database and file backup service."""
    
    def __init__(self):
        self.config = get_config()
        self.backup_dir = Path(self.config.BACKUPS_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_url = os.environ.get("DATABASE_URL", self.config.DATABASE_URL)
        self.circuit_breaker = CircuitBreaker("backup", failure_threshold=5)
    
    async def create_database_backup(
        self,
        backup_name: Optional[str] = None,
        compress: bool = True,
    ) -> BackupResult:
        """
        Create a PostgreSQL database backup using pg_dump.
        
        Args:
            backup_name: Optional custom backup filename
            compress: Whether to gzip compress
        
        Returns:
            BackupResult with details
        """
        start_time = time.perf_counter()
        
        if backup_name is None:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_name = f"predict_backup_{timestamp}.sql"
        
        if compress and not backup_name.endswith('.gz'):
            backup_name += '.gz'
        
        backup_path = self.backup_dir / backup_name
        
        try:
            # Parse database URL
            db_config = self._parse_db_url(self.db_url)
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '-h', db_config['host'],
                '-p', str(db_config['port']),
                '-U', db_config['user'],
                '-d', db_config['dbname'],
                '-F', 'p',  # Plain text format
                '-v',  # Verbose
            ]
            
            # Environment with password
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            # Execute pg_dump
            if compress:
                # Pipe through gzip
                proc_dump = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                
                proc_gzip = await asyncio.create_subprocess_exec(
                    'gzip',
                    stdin=proc_dump.stdout,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                # Write output
                async with aiofiles.open(backup_path, 'wb') as f:
                    while True:
                        chunk = await proc_gzip.stdout.read(8192)
                        if not chunk:
                            break
                        await f.write(chunk)
                
                await proc_dump.wait()
                await proc_gzip.wait()
                
                if proc_dump.returncode != 0 or proc_gzip.returncode != 0:
                    stderr_dump = await proc_dump.stderr.read()
                    raise Exception(f"pg_dump failed: {stderr_dump.decode()}")
            else:
                # Direct output
                with open(backup_path, 'w') as f:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    _, stderr = await proc.communicate()
                    
                    if proc.returncode != 0:
                        raise Exception(f"pg_dump failed: {stderr.decode()}")
            
            duration = time.perf_counter() - start_time
            size = backup_path.stat().st_size
            
            logger.info(f"Database backup created: {backup_path} ({size:,} bytes in {duration:.2f}s)")
            
            return BackupResult(
                success=True,
                backup_path=backup_path,
                size_bytes=size,
                duration_sec=duration,
            )
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return BackupResult(
                success=False,
                error_message=str(e),
                duration_sec=time.perf_counter() - start_time,
            )
    
    async def create_file_backup(
        self,
        source_dirs: List[Path],
        backup_name: Optional[str] = None,
    ) -> BackupResult:
        """
        Create a compressed archive of specified directories.
        
        Args:
            source_dirs: Directories to backup
            backup_name: Optional custom backup filename
        
        Returns:
            BackupResult with details
        """
        start_time = time.perf_counter()
        
        if backup_name is None:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_name = f"predict_files_{timestamp}.tar.gz"
        
        backup_path = self.backup_dir / backup_name
        
        try:
            # Create tar.gz archive
            with tarfile.open(backup_path, 'w:gz') as tar:
                for source_dir in source_dirs:
                    if source_dir.exists():
                        tar.add(source_dir, arcname=source_dir.name)
                        logger.debug(f"Added to backup: {source_dir}")
            
            duration = time.perf_counter() - start_time
            size = backup_path.stat().st_size
            
            logger.info(f"File backup created: {backup_path} ({size:,} bytes in {duration:.2f}s)")
            
            return BackupResult(
                success=True,
                backup_path=backup_path,
                size_bytes=size,
                duration_sec=duration,
            )
            
        except Exception as e:
            logger.error(f"File backup failed: {e}")
            return BackupResult(
                success=False,
                error_message=str(e),
                duration_sec=time.perf_counter() - start_time,
            )
    
    async def upload_to_cloud(
        self,
        backup_path: Path,
        provider: str = "s3",
    ) -> bool:
        """
        Upload backup to cloud storage.
        
        Args:
            backup_path: Path to backup file
            provider: Cloud provider (s3, gcs, azure)
        
        Returns:
            True if upload successful
        """
        try:
            if provider == "s3":
                return await self._upload_to_s3(backup_path)
            elif provider == "gcs":
                return await self._upload_to_gcs(backup_path)
            elif provider == "azure":
                return await self._upload_to_azure(backup_path)
            else:
                logger.error(f"Unknown cloud provider: {provider}")
                return False
                
        except Exception as e:
            logger.error(f"Cloud upload failed: {e}")
            return False
    
    async def _upload_to_s3(self, backup_path: Path) -> bool:
        """Upload to AWS S3."""
        import boto3
        
        bucket = os.environ.get("AWS_BACKUP_BUCKET")
        if not bucket:
            logger.warning("AWS_BACKUP_BUCKET not set, skipping S3 upload")
            return False
        
        s3 = boto3.client('s3')
        key = f"backups/{backup_path.name}"
        
        s3.upload_file(str(backup_path), bucket, key)
        logger.info(f"Backup uploaded to S3: s3://{bucket}/{key}")
        
        return True
    
    async def _upload_to_gcs(self, backup_path: Path) -> bool:
        """Upload to Google Cloud Storage."""
        from google.cloud import storage
        
        bucket_name = os.environ.get("GCS_BACKUP_BUCKET")
        if not bucket_name:
            logger.warning("GCS_BACKUP_BUCKET not set, skipping GCS upload")
            return False
        
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"backups/{backup_path.name}")
        
        blob.upload_from_filename(str(backup_path))
        logger.info(f"Backup uploaded to GCS: gs://{bucket_name}/backups/{backup_path.name}")
        
        return True
    
    async def _upload_to_azure(self, backup_path: Path) -> bool:
        """Upload to Azure Blob Storage."""
        from azure.storage.blob import BlobServiceClient
        
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container = os.environ.get("AZURE_BACKUP_CONTAINER", "backups")
        
        if not connection_string:
            logger.warning("AZURE_STORAGE_CONNECTION_STRING not set, skipping Azure upload")
            return False
        
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service.get_blob_client(
            container=container,
            blob=f"backups/{backup_path.name}"
        )
        
        with open(backup_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        
        logger.info(f"Backup uploaded to Azure: {container}/backups/{backup_path.name}")
        
        return True
    
    async def cleanup_old_backups(
        self,
        retention_days: int = 30,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Remove backups older than retention period.
        
        Args:
            retention_days: Number of days to keep backups
            dry_run: If True, only report what would be deleted
        
        Returns:
            Cleanup statistics
        """
        cutoff_time = time.time() - (retention_days * 86400)
        deleted = []
        errors = []
        space_freed = 0
        
        for backup_file in self.backup_dir.iterdir():
            if not backup_file.is_file():
                continue
            
            mtime = backup_file.stat().st_mtime
            
            if mtime < cutoff_time:
                if dry_run:
                    deleted.append({
                        "file": backup_file.name,
                        "age_days": int((time.time() - mtime) / 86400),
                        "size": backup_file.stat().st_size,
                    })
                else:
                    try:
                        size = backup_file.stat().st_size
                        backup_file.unlink()
                        deleted.append({
                            "file": backup_file.name,
                            "size": size,
                        })
                        space_freed += size
                    except Exception as e:
                        errors.append({"file": backup_file.name, "error": str(e)})
        
        if not dry_run and deleted:
            logger.info(f"Cleaned up {len(deleted)} old backups, freed {space_freed:,} bytes")
        
        return {
            "deleted_count": len(deleted),
            "space_freed_bytes": space_freed,
            "deleted": deleted,
            "errors": errors,
        }
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        
        for backup_file in self.backup_dir.iterdir():
            if backup_file.is_file():
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "size_bytes": stat.st_size,
                    "created_at": stat.st_mtime,
                    "type": self._detect_backup_type(backup_file.name),
                })
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        
        return backups
    
    def _detect_backup_type(self, filename: str) -> str:
        """Detect backup type from filename."""
        if "_backup_" in filename and filename.endswith(".sql.gz"):
            return "database"
        elif "_files_" in filename and filename.endswith(".tar.gz"):
            return "files"
        else:
            return "unknown"
    
    def _parse_db_url(self, url: str) -> Dict[str, str]:
        """Parse PostgreSQL connection URL."""
        # Handle asyncpg URLs
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
            "dbname": parsed.path.lstrip('/') or "predict",
        }
    
    async def restore_database_backup(
        self,
        backup_path: Path,
        target_db: Optional[str] = None,
    ) -> bool:
        """
        Restore database from backup (admin only).
        
        WARNING: This will overwrite existing data!
        
        Args:
            backup_path: Path to backup file
            target_db: Optional target database name
        
        Returns:
            True if restore successful
        """
        logger.warning(f"Starting database restore from: {backup_path}")
        
        try:
            db_config = self._parse_db_url(self.db_url)
            target_db = target_db or db_config['dbname']
            
            # Build psql command
            cmd = [
                'psql',
                '-h', db_config['host'],
                '-p', str(db_config['port']),
                '-U', db_config['user'],
                '-d', target_db,
                '-f', str(backup_path),
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error(f"Database restore failed: {stderr.decode()}")
                return False
            
            logger.info(f"Database restored successfully to: {target_db}")
            return True
            
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
