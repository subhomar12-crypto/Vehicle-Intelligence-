"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Telemetry Optimizer

Telemetry Storage Optimizer
Optimizes storage of OBD and telemetry data through compression, aggregation, and archival.
"""

import logging
import sqlite3
import threading
import time
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """Storage statistics"""
    total_records: int
    total_size_mb: float
    oldest_record: Optional[datetime]
    newest_record: Optional[datetime]
    records_per_device: Dict[str, int]


class TelemetryOptimizer:
    """
    Optimizes telemetry data storage.

    Features:
    - Data aggregation (hourly/daily summaries)
    - Compression for archived data
    - Smart downsampling for historical data
    - Vacuum and optimize database
    """

    # Aggregation thresholds
    HOURLY_AGGREGATE_AGE = 24  # Start hourly aggregation after 24 hours
    DAILY_AGGREGATE_AGE = 7    # Start daily aggregation after 7 days
    ARCHIVE_AGE = 30           # Archive data older than 30 days

    def __init__(self):
        self.server_db = CONFIG.SERVER_DIR / "obd_data.db"
        self.archive_dir = CONFIG.DATA_DIR / "archives"
        self._lock = threading.Lock()

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._init_aggregation_tables()

        logger.info("TelemetryOptimizer initialized")

    def _init_aggregation_tables(self):
        """Initialize aggregation tables"""
        if not self.server_db.exists():
            return

        try:
            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            # Hourly aggregates table
            c.execute('''
                CREATE TABLE IF NOT EXISTS obd_hourly_aggregates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    profile_id INTEGER,
                    hour_start TEXT,
                    name TEXT,
                    avg_value REAL,
                    min_value REAL,
                    max_value REAL,
                    sample_count INTEGER,
                    unit TEXT,
                    UNIQUE(device_id, hour_start, name)
                )
            ''')

            # Daily aggregates table
            c.execute('''
                CREATE TABLE IF NOT EXISTS obd_daily_aggregates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    profile_id INTEGER,
                    date TEXT,
                    name TEXT,
                    avg_value REAL,
                    min_value REAL,
                    max_value REAL,
                    sample_count INTEGER,
                    unit TEXT,
                    UNIQUE(device_id, date, name)
                )
            ''')

            # Create indexes
            c.execute('CREATE INDEX IF NOT EXISTS idx_hourly_device ON obd_hourly_aggregates(device_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_hourly_time ON obd_hourly_aggregates(hour_start)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_daily_device ON obd_daily_aggregates(device_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON obd_daily_aggregates(date)')

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing aggregation tables: {e}")

    def get_storage_stats(self) -> StorageStats:
        """Get current storage statistics"""
        try:
            if not self.server_db.exists():
                return StorageStats(
                    total_records=0,
                    total_size_mb=0,
                    oldest_record=None,
                    newest_record=None,
                    records_per_device={}
                )

            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            # Total records
            c.execute('SELECT COUNT(*) FROM obd_records')
            total = c.fetchone()[0]

            # Date range
            c.execute('SELECT MIN(ts), MAX(ts) FROM obd_records')
            row = c.fetchone()
            oldest = datetime.fromtimestamp(row[0]) if row[0] else None
            newest = datetime.fromtimestamp(row[1]) if row[1] else None

            # Per-device counts
            c.execute('SELECT device_id, COUNT(*) FROM obd_records GROUP BY device_id')
            per_device = {row[0]: row[1] for row in c.fetchall()}

            conn.close()

            # File size
            size_mb = self.server_db.stat().st_size / (1024 * 1024)

            return StorageStats(
                total_records=total,
                total_size_mb=round(size_mb, 2),
                oldest_record=oldest,
                newest_record=newest,
                records_per_device=per_device
            )

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return StorageStats(0, 0, None, None, {})

    def run_optimization(self) -> Dict[str, Any]:
        """
        Run full optimization cycle.

        Returns:
            Dictionary with optimization results
        """
        logger.info("Starting telemetry optimization...")
        start_time = datetime.now()

        results = {
            'start_time': start_time.isoformat(),
            'hourly_aggregation': {},
            'daily_aggregation': {},
            'archived_records': 0,
            'deleted_records': 0,
            'space_saved_mb': 0
        }

        with self._lock:
            initial_stats = self.get_storage_stats()

            # Step 1: Create hourly aggregates
            results['hourly_aggregation'] = self._create_hourly_aggregates()

            # Step 2: Create daily aggregates
            results['daily_aggregation'] = self._create_daily_aggregates()

            # Step 3: Archive old data
            results['archived_records'] = self._archive_old_data()

            # Step 4: Delete aggregated raw data
            results['deleted_records'] = self._cleanup_aggregated_data()

            # Step 5: Vacuum database
            self._vacuum_database()

            final_stats = self.get_storage_stats()
            results['space_saved_mb'] = round(initial_stats.total_size_mb - final_stats.total_size_mb, 2)

        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        logger.info(f"Optimization complete: {results['space_saved_mb']}MB saved")

        return results

    def _create_hourly_aggregates(self) -> Dict[str, int]:
        """Create hourly aggregates for data older than threshold"""
        try:
            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            cutoff = datetime.now() - timedelta(hours=self.HOURLY_AGGREGATE_AGE)
            cutoff_ts = cutoff.timestamp()

            # Get data to aggregate
            c.execute('''
                SELECT device_id, profile_id, name, unit,
                       strftime('%Y-%m-%d %H:00:00', datetime(ts, 'unixepoch')) as hour,
                       AVG(value), MIN(value), MAX(value), COUNT(*)
                FROM obd_records
                WHERE ts < ? AND value IS NOT NULL
                GROUP BY device_id, name, hour
            ''', (cutoff_ts,))

            rows = c.fetchall()
            aggregated = 0

            for row in rows:
                try:
                    c.execute('''
                        INSERT OR REPLACE INTO obd_hourly_aggregates
                        (device_id, profile_id, hour_start, name, avg_value, min_value, max_value, sample_count, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (row[0], row[1], row[4], row[2], row[5], row[6], row[7], row[8], row[3]))
                    aggregated += 1
                except Exception as e:
                    logger.debug(f"Aggregate insert error: {e}")

            conn.commit()
            conn.close()

            logger.info(f"Created {aggregated} hourly aggregates")
            return {'aggregates_created': aggregated, 'cutoff': cutoff.isoformat()}

        except Exception as e:
            logger.error(f"Error creating hourly aggregates: {e}")
            return {'error': str(e)}

    def _create_daily_aggregates(self) -> Dict[str, int]:
        """Create daily aggregates from hourly data"""
        try:
            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            cutoff = datetime.now() - timedelta(days=self.DAILY_AGGREGATE_AGE)

            # Aggregate from hourly data
            c.execute('''
                SELECT device_id, profile_id, name, unit,
                       date(hour_start) as day,
                       AVG(avg_value), MIN(min_value), MAX(max_value), SUM(sample_count)
                FROM obd_hourly_aggregates
                WHERE hour_start < ?
                GROUP BY device_id, name, day
            ''', (cutoff.isoformat(),))

            rows = c.fetchall()
            aggregated = 0

            for row in rows:
                try:
                    c.execute('''
                        INSERT OR REPLACE INTO obd_daily_aggregates
                        (device_id, profile_id, date, name, avg_value, min_value, max_value, sample_count, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (row[0], row[1], row[4], row[2], row[5], row[6], row[7], row[8], row[3]))
                    aggregated += 1
                except Exception as e:
                    logger.debug(f"Daily aggregate error: {e}")

            conn.commit()
            conn.close()

            logger.info(f"Created {aggregated} daily aggregates")
            return {'aggregates_created': aggregated, 'cutoff': cutoff.isoformat()}

        except Exception as e:
            logger.error(f"Error creating daily aggregates: {e}")
            return {'error': str(e)}

    def _archive_old_data(self) -> int:
        """Archive old raw data to compressed files"""
        try:
            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            cutoff = datetime.now() - timedelta(days=self.ARCHIVE_AGE)
            cutoff_ts = cutoff.timestamp()

            # Get old records by date
            c.execute('''
                SELECT date(datetime(ts, 'unixepoch')) as day, COUNT(*)
                FROM obd_records
                WHERE ts < ?
                GROUP BY day
                ORDER BY day
            ''', (cutoff_ts,))

            days_to_archive = c.fetchall()
            total_archived = 0

            for day_str, count in days_to_archive:
                # Export day's data to compressed JSON
                archived = self._archive_day(conn, day_str)
                total_archived += archived

            conn.close()
            return total_archived

        except Exception as e:
            logger.error(f"Error archiving data: {e}")
            return 0

    def _archive_day(self, conn: sqlite3.Connection, day_str: str) -> int:
        """Archive a single day's data"""
        try:
            c = conn.cursor()

            # Get records for the day
            c.execute('''
                SELECT device_id, profile_id, ts, pid, name, value, unit
                FROM obd_records
                WHERE date(datetime(ts, 'unixepoch')) = ?
            ''', (day_str,))

            rows = c.fetchall()
            if not rows:
                return 0

            # Prepare archive data
            archive_data = {
                'date': day_str,
                'record_count': len(rows),
                'archived_at': datetime.now().isoformat(),
                'records': [
                    {
                        'device_id': r[0],
                        'profile_id': r[1],
                        'ts': r[2],
                        'pid': r[3],
                        'name': r[4],
                        'value': r[5],
                        'unit': r[6]
                    }
                    for r in rows
                ]
            }

            # Save to compressed file
            archive_file = self.archive_dir / f"obd_archive_{day_str}.json.gz"
            with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
                json.dump(archive_data, f)

            logger.debug(f"Archived {len(rows)} records for {day_str}")
            return len(rows)

        except Exception as e:
            logger.error(f"Error archiving day {day_str}: {e}")
            return 0

    def _cleanup_aggregated_data(self) -> int:
        """Delete raw data that has been aggregated"""
        try:
            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            # Delete data older than daily aggregate threshold
            cutoff = datetime.now() - timedelta(days=self.DAILY_AGGREGATE_AGE)
            cutoff_ts = cutoff.timestamp()

            # Only delete if we have the aggregates
            c.execute('''
                DELETE FROM obd_records
                WHERE ts < ? AND EXISTS (
                    SELECT 1 FROM obd_daily_aggregates
                    WHERE obd_daily_aggregates.device_id = obd_records.device_id
                    AND obd_daily_aggregates.name = obd_records.name
                )
            ''', (cutoff_ts,))

            deleted = c.rowcount
            conn.commit()

            # Also clean up old hourly aggregates
            hourly_cutoff = datetime.now() - timedelta(days=self.DAILY_AGGREGATE_AGE)
            c.execute('DELETE FROM obd_hourly_aggregates WHERE hour_start < ?',
                      (hourly_cutoff.isoformat(),))

            conn.commit()
            conn.close()

            logger.info(f"Deleted {deleted} aggregated raw records")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up aggregated data: {e}")
            return 0

    def _vacuum_database(self):
        """Vacuum and optimize database"""
        try:
            conn = sqlite3.connect(str(self.server_db))
            conn.execute('VACUUM')
            conn.execute('ANALYZE')
            conn.close()
            logger.info("Database vacuumed and analyzed")
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")

    def get_aggregated_data(self, device_id: str, start_date: datetime,
                            end_date: datetime, resolution: str = 'hourly') -> List[Dict[str, Any]]:
        """
        Get aggregated data for a device.

        Args:
            device_id: Device identifier
            start_date: Start of date range
            end_date: End of date range
            resolution: 'hourly' or 'daily'

        Returns:
            List of aggregated data points
        """
        try:
            conn = sqlite3.connect(str(self.server_db))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if resolution == 'daily':
                c.execute('''
                    SELECT * FROM obd_daily_aggregates
                    WHERE device_id = ? AND date BETWEEN ? AND ?
                    ORDER BY date, name
                ''', (device_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            else:
                c.execute('''
                    SELECT * FROM obd_hourly_aggregates
                    WHERE device_id = ? AND hour_start BETWEEN ? AND ?
                    ORDER BY hour_start, name
                ''', (device_id, start_date.isoformat(), end_date.isoformat()))

            rows = c.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting aggregated data: {e}")
            return []

    def restore_from_archive(self, date: str) -> int:
        """Restore archived data for a specific date"""
        try:
            archive_file = self.archive_dir / f"obd_archive_{date}.json.gz"
            if not archive_file.exists():
                logger.warning(f"Archive not found for {date}")
                return 0

            with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                archive_data = json.load(f)

            conn = sqlite3.connect(str(self.server_db))
            c = conn.cursor()

            restored = 0
            for record in archive_data.get('records', []):
                try:
                    c.execute('''
                        INSERT OR IGNORE INTO obd_records
                        (device_id, profile_id, ts, pid, name, value, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        record['device_id'],
                        record['profile_id'],
                        record['ts'],
                        record['pid'],
                        record['name'],
                        record['value'],
                        record['unit']
                    ))
                    restored += c.rowcount
                except Exception as e:
                    logger.debug(f"Restore error: {e}")

            conn.commit()
            conn.close()

            logger.info(f"Restored {restored} records from {date}")
            return restored

        except Exception as e:
            logger.error(f"Error restoring from archive: {e}")
            return 0


# Singleton instance
_optimizer: Optional[TelemetryOptimizer] = None


def get_telemetry_optimizer() -> TelemetryOptimizer:
    """Get the singleton TelemetryOptimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = TelemetryOptimizer()
    return _optimizer
