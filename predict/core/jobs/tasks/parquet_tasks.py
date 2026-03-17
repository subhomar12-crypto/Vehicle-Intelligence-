"""
ARQ background task for Parquet writes.
"""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List

try:
    import pyarrow.parquet as pq
    import pyarrow as pa
    _has_pyarrow = True
except ImportError:
    _has_pyarrow = False

try:
    import pandas as pd
    _has_pandas = True
except ImportError:
    _has_pandas = False

from predict.core.config import get_config

logger = logging.getLogger(__name__)


async def flush_parquet_buffer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flush buffered data to Parquet files.

    ParquetWriter was removed in the v3 AI cleanup.
    This task is now a no-op stub retained for worker compatibility.
    """
    logger.info("flush_parquet_buffer: ParquetWriter removed — skipping")
    return {"status": "skipped", "reason": "parquet_writer_removed"}


async def compact_parquet_files(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read small Parquet files, merge into larger ones, delete originals.
    
    Args:
        ctx: ARQ context
    
    Returns:
        Compaction statistics
    """
    logger.info("Starting Parquet file compaction")
    
    config = get_config()
    parquet_dir = config.PARQUET_DIR
    
    if not parquet_dir.exists():
        logger.warning(f"Parquet directory does not exist: {parquet_dir}")
        return {"status": "skipped", "reason": "directory_missing"}
    
    if not _has_pyarrow or not _has_pandas:
        logger.warning("PyArrow or Pandas not available, skipping compaction")
        return {"status": "skipped", "reason": "dependencies_missing"}
    
    try:
        # Find small files (< 1MB)
        small_files: List[Path] = []
        for file_path in parquet_dir.glob("*.parquet"):
            if file_path.stat().st_size < 1_000_000:  # 1MB
                small_files.append(file_path)
        
        if len(small_files) < 5:
            logger.info("Not enough small files to compact")
            return {
                "status": "skipped",
                "reason": "insufficient_files",
                "small_files_found": len(small_files),
            }
        
        # Group by prefix (e.g., "training_", "profile_123_")
        file_groups: Dict[str, List[Path]] = {}
        for file_path in small_files:
            # Extract prefix (e.g., "training_" from "training_123456.parquet")
            parts = file_path.stem.split('_')
            if len(parts) >= 2:
                prefix = f"{parts[0]}_{parts[1]}"
            else:
                prefix = parts[0] if parts else "misc"
            
            if prefix not in file_groups:
                file_groups[prefix] = []
            file_groups[prefix].append(file_path)
        
        # Compact each group
        compacted = 0
        removed = 0
        bytes_saved = 0
        
        for prefix, files in file_groups.items():
            if len(files) < 3:
                continue
            
            try:
                # Read and concatenate
                dfs = []
                for f in files:
                    try:
                        df = pd.read_parquet(f)
                        dfs.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to read {f}: {e}")
                
                if not dfs:
                    continue
                
                combined = pd.concat(dfs, ignore_index=True)
                
                # Write compacted file
                timestamp = int(asyncio.get_event_loop().time())
                compacted_path = parquet_dir / f"{prefix}_compact_{timestamp}.parquet"
                
                combined.to_parquet(
                    compacted_path,
                    compression='zstd',
                    index=False,
                )
                
                # Delete original files
                for f in files:
                    try:
                        size = f.stat().st_size
                        f.unlink()
                        removed += 1
                        bytes_saved += size
                    except Exception as e:
                        logger.warning(f"Failed to delete {f}: {e}")
                
                compacted += 1
                logger.info(f"Compacted {len(files)} files into {compacted_path}")
            
            except Exception as e:
                logger.error(f"Failed to compact group {prefix}: {e}")
        
        return {
            "status": "success",
            "groups_compacted": compacted,
            "files_removed": removed,
            "bytes_saved": bytes_saved,
        }
    
    except Exception as e:
        logger.error(f"Parquet compaction failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def archive_old_parquet(ctx: Dict[str, Any], days: int = 30) -> Dict[str, Any]:
    """
    Archive old Parquet files to compressed archives.
    
    Args:
        ctx: ARQ context
        days: Age threshold in days
    
    Returns:
        Archive statistics
    """
    logger.info(f"Starting Parquet archive for files older than {days} days")
    
    config = get_config()
    parquet_dir = config.PARQUET_DIR
    archive_dir = config.DATA_DIR / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    import time
    cutoff_time = time.time() - (days * 86400)
    
    try:
        archived = 0
        bytes_archived = 0
        
        for file_path in parquet_dir.glob("*.parquet"):
            try:
                mtime = file_path.stat().st_mtime
                if mtime < cutoff_time:
                    # Archive by moving to archive directory
                    archive_path = archive_dir / file_path.name
                    
                    # Handle name collision
                    counter = 1
                    while archive_path.exists():
                        archive_path = archive_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                        counter += 1
                    
                    file_path.rename(archive_path)
                    
                    archived += 1
                    bytes_archived += archive_path.stat().st_size
            
            except Exception as e:
                logger.warning(f"Failed to archive {file_path}: {e}")
        
        logger.info(f"Archived {archived} old Parquet files")
        
        return {
            "status": "success",
            "files_archived": archived,
            "bytes_archived": bytes_archived,
            "archive_location": str(archive_dir),
        }
    
    except Exception as e:
        logger.error(f"Parquet archive failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
