"""
Export service for generating downloadable files.

Supports CSV, JSON, and Parquet exports with async generation.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

from predict.core.config import get_config

logger = logging.getLogger(__name__)


class ExportService:
    """Service for generating data exports."""
    
    def __init__(self):
        self.config = get_config()
        self.exports_dir = self.config.EXPORTS_DIR
    
    async def export_to_csv(
        self,
        data: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Export data to CSV file.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename (auto-generated if None)
        
        Returns:
            Path to generated CSV file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"
        
        file_path = self.exports_dir / filename
        
        if not data:
            # Create empty CSV with headers
            file_path.touch()
            return file_path
        
        # Write CSV
        fieldnames = data[0].keys()
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"CSV export created: {file_path}")
        return file_path
    
    async def export_to_json(
        self,
        data: List[Dict[str, Any]],
        filename: Optional[str] = None,
        indent: int = 2,
    ) -> Path:
        """
        Export data to JSON file.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename
            indent: JSON indentation level
        
        Returns:
            Path to generated JSON file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.json"
        
        file_path = self.exports_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, default=str)
        
        logger.info(f"JSON export created: {file_path}")
        return file_path
    
    async def export_to_parquet(
        self,
        data: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Export data to Parquet file.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename
        
        Returns:
            Path to generated Parquet file
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.parquet"
        
        file_path = self.exports_dir / filename
        
        # Convert to DataFrame and save
        df = pd.DataFrame(data)
        df.to_parquet(file_path, index=False)
        
        logger.info(f"Parquet export created: {file_path}")
        return file_path
    
    async def export_vehicle_data(
        self,
        vehicle_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "csv",
    ) -> Path:
        """
        Export vehicle telemetry data.
        
        Args:
            vehicle_id: Vehicle ID
            start_date: Filter start date
            end_date: Filter end date
            format: Export format (csv, json, parquet)
        
        Returns:
            Path to generated export file
        """
        # TODO: Fetch actual vehicle data from database
        # Placeholder implementation
        
        data = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "vehicle_id": vehicle_id,
                "speed_kmh": 65.0,
                "rpm": 2500,
                "engine_temp_c": 90,
            }
        ]
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"vehicle_{vehicle_id}_{timestamp}.{format}"
        
        if format == "csv":
            return await self.export_to_csv(data, filename)
        elif format == "json":
            return await self.export_to_json(data, filename)
        elif format == "parquet":
            return await self.export_to_parquet(data, filename)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_export_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an export file.
        
        Args:
            filename: Export filename
        
        Returns:
            File info dict or None if not found
        """
        file_path = self.exports_dir / filename
        
        if not file_path.exists():
            return None
        
        stat = file_path.stat()
        
        return {
            "filename": filename,
            "path": str(file_path),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    
    def list_exports(
        self,
        prefix: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List available export files.
        
        Args:
            prefix: Filter by filename prefix
            extension: Filter by file extension
        
        Returns:
            List of export file info dicts
        """
        exports = []
        
        for file_path in self.exports_dir.iterdir():
            if not file_path.is_file():
                continue
            
            # Apply filters
            if prefix and not file_path.name.startswith(prefix):
                continue
            if extension and file_path.suffix.lower() != extension.lower():
                continue
            
            info = self.get_export_info(file_path.name)
            if info:
                exports.append(info)
        
        # Sort by creation time (newest first)
        exports.sort(key=lambda x: x["created_at"], reverse=True)
        
        return exports
    
    async def delete_export(self, filename: str) -> bool:
        """
        Delete an export file.
        
        Args:
            filename: Export filename
        
        Returns:
            True if deleted, False if not found
        """
        file_path = self.exports_dir / filename
        
        if not file_path.exists():
            return False
        
        file_path.unlink()
        logger.info(f"Export deleted: {file_path}")
        return True
    
    async def cleanup_old_exports(self, max_age_days: int = 7) -> Dict[str, int]:
        """
        Delete exports older than specified days.
        
        Args:
            max_age_days: Delete files older than this
        
        Returns:
            Summary of cleanup operation
        """
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 24 * 3600)
        deleted = 0
        failed = 0
        
        for file_path in self.exports_dir.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    deleted += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                failed += 1
        
        logger.info(f"Export cleanup: {deleted} deleted, {failed} failed")
        
        return {
            "deleted": deleted,
            "failed": failed,
        }
