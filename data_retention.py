"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Data Retention

Data Retention Policy Manager
Manages automatic cleanup of old data according to configurable retention policies.
"""

import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import schedule

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """Defines retention policy for a data type"""
    name: str
    retention_days: int
    enabled: bool = True
    description: str = ""


class DataRetentionManager:
    """
    Manages data retention policies and automatic cleanup.

    Features:
    - Configurable retention periods per data type
    - Automatic daily cleanup
    - Retention statistics and reporting
    - Safe deletion with logging
    """

    # Default retention policies (days)
    DEFAULT_POLICIES = {
        'obd_records': RetentionPolicy(
            name='obd_records',
            retention_days=90,
            description='OBD sensor readings from vehicles'
        ),
        'telemetry_records': RetentionPolicy(
            name='telemetry_records',
            retention_days=90,
            description='Vehicle telemetry data'
        ),
        'heartbeat_history': RetentionPolicy(
            name='heartbeat_history',
            retention_days=30,
            description='Device connection history'
        ),
        'prediction_logs': RetentionPolicy(
            name='prediction_logs',
            retention_days=180,
            description='AI prediction records'
        ),
        'training_logs': RetentionPolicy(
            name='training_logs',
            retention_days=365,
            description='Model training history'
        ),
        'audit_logs': RetentionPolicy(
            name='audit_logs',
            retention_days=365,
            description='System audit trail'
        ),
        'reports': RetentionPolicy(
            name='reports',
            retention_days=90,
            description='Generated PDF reports'
        ),
    }

    def __init__(self):
        self.policies: Dict[str, RetentionPolicy] = {}
        self.config_file = CONFIG.CONFIG_DIR / "retention_policies.json"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_cleanup: Optional[datetime] = None
        self._cleanup_stats: Dict[str, int] = {}

        self._load_policies()
        logger.info("DataRetentionManager initialized")

    def _load_policies(self):
        """Load retention policies from config file or use defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    saved_policies = json.load(f)
                    for name, data in saved_policies.items():
                        self.policies[name] = RetentionPolicy(
                            name=name,
                            retention_days=data.get('retention_days', 90),
                            enabled=data.get('enabled', True),
                            description=data.get('description', '')
                        )
                logger.info(f"Loaded {len(self.policies)} retention policies from config")
            else:
                self.policies = self.DEFAULT_POLICIES.copy()
                self._save_policies()
                logger.info("Using default retention policies")
        except Exception as e:
            logger.error(f"Error loading retention policies: {e}")
            self.policies = self.DEFAULT_POLICIES.copy()

    def _save_policies(self):
        """Save current policies to config file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                name: {
                    'retention_days': p.retention_days,
                    'enabled': p.enabled,
                    'description': p.description
                }
                for name, p in self.policies.items()
            }
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving retention policies: {e}")

    def set_policy(self, name: str, retention_days: int, enabled: bool = True, description: str = ""):
        """Set or update a retention policy"""
        self.policies[name] = RetentionPolicy(
            name=name,
            retention_days=retention_days,
            enabled=enabled,
            description=description
        )
        self._save_policies()
        logger.info(f"Updated retention policy: {name} = {retention_days} days")

    def get_policy(self, name: str) -> Optional[RetentionPolicy]:
        """Get a retention policy by name"""
        return self.policies.get(name)

    def get_all_policies(self) -> Dict[str, RetentionPolicy]:
        """Get all retention policies"""
        return self.policies.copy()

    def start_scheduler(self, cleanup_time: str = "04:00"):
        """Start automatic cleanup scheduler"""
        if self._running:
            return

        self._running = True

        # Schedule daily cleanup
        schedule.every().day.at(cleanup_time).do(self.run_cleanup)

        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

        logger.info(f"Data retention scheduler started - cleanup at {cleanup_time}")

    def stop_scheduler(self):
        """Stop the scheduler"""
        self._running = False
        schedule.clear('retention')
        logger.info("Data retention scheduler stopped")

    def _scheduler_loop(self):
        """Background scheduler loop"""
        while self._running:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.error(f"Error in retention scheduler: {e}")
            time.sleep(60)

    def run_cleanup(self) -> Dict[str, Any]:
        """
        Run cleanup for all enabled policies.

        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting data retention cleanup...")
        start_time = datetime.now()
        results = {
            'start_time': start_time.isoformat(),
            'policies_processed': 0,
            'total_deleted': 0,
            'details': {}
        }

        for name, policy in self.policies.items():
            if not policy.enabled:
                continue

            try:
                deleted = self._cleanup_data_type(name, policy.retention_days)
                results['details'][name] = {
                    'deleted': deleted,
                    'retention_days': policy.retention_days
                }
                results['total_deleted'] += deleted
                results['policies_processed'] += 1
                self._cleanup_stats[name] = deleted

            except Exception as e:
                logger.error(f"Error cleaning up {name}: {e}")
                results['details'][name] = {'error': str(e)}

        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        self._last_cleanup = datetime.now()

        logger.info(f"Cleanup complete: {results['total_deleted']} records deleted in {results['duration_seconds']:.1f}s")
        return results

    def _cleanup_data_type(self, data_type: str, retention_days: int) -> int:
        """Clean up a specific data type based on retention policy"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted = 0

        # Database cleanup based on data type
        if data_type == 'obd_records':
            deleted = self._cleanup_server_obd_records(cutoff_date)

        elif data_type == 'telemetry_records':
            deleted = self._cleanup_server_telemetry(cutoff_date)

        elif data_type == 'heartbeat_history':
            deleted = self._cleanup_heartbeat_history(cutoff_date)

        elif data_type == 'prediction_logs':
            deleted = self._cleanup_prediction_logs(cutoff_date)

        elif data_type == 'training_logs':
            deleted = self._cleanup_training_logs(cutoff_date)

        elif data_type == 'reports':
            deleted = self._cleanup_old_reports(cutoff_date)

        return deleted

    def _cleanup_server_obd_records(self, cutoff_date: datetime) -> int:
        """Clean up old OBD records from server database"""
        try:
            db_path = CONFIG.SERVER_DIR / "obd_data.db"
            if not db_path.exists():
                return 0

            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()

            cutoff_ts = cutoff_date.timestamp()
            c.execute('DELETE FROM obd_records WHERE ts < ?', (cutoff_ts,))
            deleted = c.rowcount

            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info(f"Deleted {deleted} old OBD records")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning OBD records: {e}")
            return 0

    def _cleanup_server_telemetry(self, cutoff_date: datetime) -> int:
        """Clean up old telemetry records"""
        try:
            db_path = CONFIG.SERVER_DIR / "obd_data.db"
            if not db_path.exists():
                return 0

            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()

            cutoff_ts = cutoff_date.timestamp()
            c.execute('DELETE FROM telemetry_records WHERE ts < ?', (cutoff_ts,))
            deleted = c.rowcount

            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info(f"Deleted {deleted} old telemetry records")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning telemetry records: {e}")
            return 0

    def _cleanup_heartbeat_history(self, cutoff_date: datetime) -> int:
        """Clean up old heartbeat history"""
        try:
            db_path = CONFIG.DATA_DIR / "device_heartbeats.db"
            if not db_path.exists():
                return 0

            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()

            cutoff_str = cutoff_date.isoformat()
            c.execute('DELETE FROM heartbeat_history WHERE timestamp < ?', (cutoff_str,))
            deleted = c.rowcount

            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info(f"Deleted {deleted} old heartbeat records")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning heartbeat history: {e}")
            return 0

    def _cleanup_prediction_logs(self, cutoff_date: datetime) -> int:
        """Clean up old prediction logs"""
        try:
            db_path = CONFIG.AI_DIR / "accuracy_tracking.db"
            if not db_path.exists():
                return 0

            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()

            cutoff_str = cutoff_date.isoformat()
            c.execute('DELETE FROM predictions WHERE created_at < ?', (cutoff_str,))
            deleted = c.rowcount

            conn.commit()
            conn.close()

            if deleted > 0:
                logger.info(f"Deleted {deleted} old prediction records")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning prediction logs: {e}")
            return 0

    def _cleanup_training_logs(self, cutoff_date: datetime) -> int:
        """Clean up old training log files"""
        try:
            log_dir = CONFIG.LOGS_DIR / "training"
            if not log_dir.exists():
                return 0

            deleted = 0
            for log_file in log_dir.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        log_file.unlink()
                        deleted += 1
                except Exception:
                    pass

            if deleted > 0:
                logger.info(f"Deleted {deleted} old training log files")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning training logs: {e}")
            return 0

    def _cleanup_old_reports(self, cutoff_date: datetime) -> int:
        """Clean up old PDF reports"""
        try:
            reports_dir = CONFIG.SERVER_DIR / "reports"
            if not reports_dir.exists():
                return 0

            deleted = 0
            for report_file in reports_dir.glob("*.pdf"):
                try:
                    mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        report_file.unlink()
                        deleted += 1
                except Exception:
                    pass

            if deleted > 0:
                logger.info(f"Deleted {deleted} old report files")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning reports: {e}")
            return 0

    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage statistics for each data type"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'last_cleanup': self._last_cleanup.isoformat() if self._last_cleanup else None,
            'data_types': {}
        }

        # OBD records
        try:
            db_path = CONFIG.SERVER_DIR / "obd_data.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM obd_records')
                count = c.fetchone()[0]
                c.execute('SELECT MIN(ts), MAX(ts) FROM obd_records')
                row = c.fetchone()
                conn.close()
                stats['data_types']['obd_records'] = {
                    'count': count,
                    'oldest': datetime.fromtimestamp(row[0]).isoformat() if row[0] else None,
                    'newest': datetime.fromtimestamp(row[1]).isoformat() if row[1] else None
                }
        except Exception:
            pass

        # Telemetry records
        try:
            db_path = CONFIG.SERVER_DIR / "obd_data.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM telemetry_records')
                count = c.fetchone()[0]
                conn.close()
                stats['data_types']['telemetry_records'] = {'count': count}
        except Exception:
            pass

        # Heartbeat history
        try:
            db_path = CONFIG.DATA_DIR / "device_heartbeats.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM heartbeat_history')
                count = c.fetchone()[0]
                conn.close()
                stats['data_types']['heartbeat_history'] = {'count': count}
        except Exception:
            pass

        # Reports
        try:
            reports_dir = CONFIG.SERVER_DIR / "reports"
            if reports_dir.exists():
                pdf_files = list(reports_dir.glob("*.pdf"))
                total_size = sum(f.stat().st_size for f in pdf_files)
                stats['data_types']['reports'] = {
                    'count': len(pdf_files),
                    'total_size_mb': round(total_size / (1024 * 1024), 2)
                }
        except Exception:
            pass

        return stats


# Singleton instance
_retention_manager: Optional[DataRetentionManager] = None
_manager_lock = threading.Lock()


def get_retention_manager() -> DataRetentionManager:
    """Get the singleton DataRetentionManager instance."""
    global _retention_manager

    with _manager_lock:
        if _retention_manager is None:
            _retention_manager = DataRetentionManager()

        return _retention_manager
