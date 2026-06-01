"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Backup Manager

Automatic Backup Manager - Creates scheduled backups of all critical data
Backs up database, historical data, and configuration files to D:\Backup
"""

import os
import shutil
import zipfile
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging
import threading

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages automatic backups of all application data

    Backup Structure:
    D:/Backup/
        ├── daily/
        │   ├── backup_YYYY_MM_DD_HHMMSS.zip
        ├── weekly/
        │   ├── backup_YYYY_WW.zip
        ├── monthly/
        │   ├── backup_YYYY_MM.zip
        └── backup_log.json
    """

    def __init__(self, backup_base_path=None, app_data_path=None):
        """Initialize backup manager"""
        from config import get_config
        CONFIG = get_config()
        
        self.backup_base_path = backup_base_path if backup_base_path else str(CONFIG.BACKUPS_DIR)
        self.app_data_path = app_data_path if app_data_path else str(CONFIG.DATA_DIR)
        self.backup_log_file = os.path.join(self.backup_base_path, 'backup_log.json')

        self.ensure_backup_directories()
        logger.info(f"Backup Manager initialized. Backups will be saved to: {backup_base_path}")

    def ensure_backup_directories(self):
        """Ensure backup directory structure exists"""
        os.makedirs(self.backup_base_path, exist_ok=True)
        os.makedirs(os.path.join(self.backup_base_path, 'daily'), exist_ok=True)
        os.makedirs(os.path.join(self.backup_base_path, 'weekly'), exist_ok=True)
        os.makedirs(os.path.join(self.backup_base_path, 'monthly'), exist_ok=True)

    def create_backup(self, backup_type='daily', description='Automatic backup') -> Optional[str]:
        """
        Create a complete backup of all application data

        Args:
            backup_type: 'daily', 'weekly', or 'monthly'
            description: Description of the backup

        Returns:
            Path to backup file or None if failed
        """
        try:
            logger.info(f"Starting {backup_type} backup...")

            # Generate backup filename
            timestamp = datetime.now()
            if backup_type == 'daily':
                filename = f"backup_{timestamp.strftime('%Y_%m_%d_%H%M%S')}.zip"
            elif backup_type == 'weekly':
                week_num = timestamp.isocalendar()[1]
                filename = f"backup_{timestamp.year}_W{week_num:02d}.zip"
            elif backup_type == 'monthly':
                filename = f"backup_{timestamp.strftime('%Y_%m')}.zip"
            else:
                filename = f"backup_{timestamp.strftime('%Y_%m_%d_%H%M%S')}.zip"

            backup_dir = os.path.join(self.backup_base_path, backup_type)
            backup_path = os.path.join(backup_dir, filename)

            # Create zip backup
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup database
                self._backup_databases(zipf)

                # Backup historical data
                self._backup_historical_data(zipf)

                # Backup configuration files
                self._backup_configurations(zipf)

                # Backup learned PIDs
                self._backup_learned_pids(zipf)

                # Backup AI models
                self._backup_ai_models(zipf)

            # Log the backup
            backup_size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            self._log_backup(backup_type, filename, backup_size_mb, description)

            logger.info(f"✅ Backup completed successfully: {backup_path} ({backup_size_mb:.2f} MB)")
            return backup_path

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return None

    def _backup_databases(self, zipf: zipfile.ZipFile):
        """Backup all database files"""
        try:
            db_files = [
                os.path.join(self.app_data_path, 'data', 'vehicle_profiles.db'),
                os.path.join(self.app_data_path, 'data', 'service_history.db'),
            ]

            for db_file in db_files:
                if os.path.exists(db_file):
                    arcname = os.path.relpath(db_file, self.app_data_path)
                    zipf.write(db_file, arcname)
                    logger.debug(f"Backed up database: {arcname}")

        except Exception as e:
            logger.error(f"Error backing up databases: {e}")

    def _backup_historical_data(self, zipf: zipfile.ZipFile):
        """Backup historical data folder"""
        try:
            historical_data_path = os.path.join(self.app_data_path, 'historical_data')
            if os.path.exists(historical_data_path):
                for root, dirs, files in os.walk(historical_data_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.app_data_path)
                        zipf.write(file_path, arcname)

                logger.debug(f"Backed up historical data")

        except Exception as e:
            logger.error(f"Error backing up historical data: {e}")

    def _backup_configurations(self, zipf: zipfile.ZipFile):
        """Backup configuration files"""
        try:
            config_files = [
                os.path.join(self.app_data_path, 'config', 'api_keys.json'),
                os.path.join(self.app_data_path, 'pids_config.json'),
                os.path.join(self.app_data_path, 'pid_database.json'),
            ]

            for config_file in config_files:
                if os.path.exists(config_file):
                    arcname = os.path.relpath(config_file, self.app_data_path)
                    zipf.write(config_file, arcname)
                    logger.debug(f"Backed up config: {arcname}")

        except Exception as e:
            logger.error(f"Error backing up configurations: {e}")

    def _backup_learned_pids(self, zipf: zipfile.ZipFile):
        """Backup learned PID files"""
        try:
            learned_pids_path = os.path.join(self.app_data_path, 'learned_pids')
            if os.path.exists(learned_pids_path):
                for file in os.listdir(learned_pids_path):
                    if file.endswith('.json'):
                        file_path = os.path.join(learned_pids_path, file)
                        arcname = os.path.relpath(file_path, self.app_data_path)
                        zipf.write(file_path, arcname)

                logger.debug(f"Backed up learned PIDs")

        except Exception as e:
            logger.error(f"Error backing up learned PIDs: {e}")

    def _backup_ai_models(self, zipf: zipfile.ZipFile):
        """Backup AI model files"""
        try:
            ai_models_path = os.path.join(self.app_data_path, 'ai_model_storage')
            if os.path.exists(ai_models_path):
                for root, dirs, files in os.walk(ai_models_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.app_data_path)
                        zipf.write(file_path, arcname)

                logger.debug(f"Backed up AI models")

        except Exception as e:
            logger.error(f"Error backing up AI models: {e}")

    def _log_backup(self, backup_type: str, filename: str, size_mb: float, description: str):
        """Log backup details to backup log"""
        try:
            # Load existing log
            if os.path.exists(self.backup_log_file):
                with open(self.backup_log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = {'backups': []}

            # Add new backup entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': backup_type,
                'filename': filename,
                'size_mb': round(size_mb, 2),
                'description': description
            }
            log_data['backups'].append(log_entry)

            # Keep only last 100 entries
            log_data['backups'] = log_data['backups'][-100:]

            # Save log
            with open(self.backup_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error logging backup: {e}")

    def restore_backup(self, backup_path: str, restore_path: Optional[str] = None) -> bool:
        """
        Restore from a backup file

        Args:
            backup_path: Path to backup zip file
            restore_path: Path to restore to (default: app_data_path)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False

            restore_target = restore_path or self.app_data_path

            logger.info(f"Restoring backup from: {backup_path}")

            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(restore_target)

            logger.info(f"✅ Backup restored successfully to: {restore_target}")
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False

    def cleanup_old_backups(self, keep_daily=7, keep_weekly=4, keep_monthly=12):
        """
        Clean up old backups based on retention policy

        Args:
            keep_daily: Number of daily backups to keep
            keep_weekly: Number of weekly backups to keep
            keep_monthly: Number of monthly backups to keep
        """
        try:
            logger.info("Cleaning up old backups...")

            policies = {
                'daily': keep_daily,
                'weekly': keep_weekly,
                'monthly': keep_monthly
            }

            for backup_type, keep_count in policies.items():
                backup_dir = os.path.join(self.backup_base_path, backup_type)
                if not os.path.exists(backup_dir):
                    continue

                # Get all backup files sorted by modification time
                backups = []
                for file in os.listdir(backup_dir):
                    if file.endswith('.zip'):
                        file_path = os.path.join(backup_dir, file)
                        backups.append((file_path, os.path.getmtime(file_path)))

                # Sort by modification time (newest first)
                backups.sort(key=lambda x: x[1], reverse=True)

                # Delete old backups
                for file_path, _ in backups[keep_count:]:
                    os.remove(file_path)
                    logger.debug(f"Deleted old backup: {file_path}")

            logger.info("✅ Old backups cleaned up")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get statistics about backups"""
        try:
            stats = {
                'total_backups': 0,
                'total_size_mb': 0,
                'daily_count': 0,
                'weekly_count': 0,
                'monthly_count': 0,
                'latest_backup': None,
                'oldest_backup': None
            }

            all_backups = []

            for backup_type in ['daily', 'weekly', 'monthly']:
                backup_dir = os.path.join(self.backup_base_path, backup_type)
                if not os.path.exists(backup_dir):
                    continue

                for file in os.listdir(backup_dir):
                    if file.endswith('.zip'):
                        file_path = os.path.join(backup_dir, file)
                        file_stat = os.stat(file_path)
                        file_size_mb = file_stat.st_size / (1024 * 1024)
                        file_mtime = file_stat.st_mtime

                        all_backups.append({
                            'path': file_path,
                            'size_mb': file_size_mb,
                            'mtime': file_mtime,
                            'type': backup_type
                        })

                        stats[f'{backup_type}_count'] += 1
                        stats['total_size_mb'] += file_size_mb

            stats['total_backups'] = len(all_backups)

            if all_backups:
                latest = max(all_backups, key=lambda x: x['mtime'])
                oldest = min(all_backups, key=lambda x: x['mtime'])
                stats['latest_backup'] = datetime.fromtimestamp(latest['mtime']).isoformat()
                stats['oldest_backup'] = datetime.fromtimestamp(oldest['mtime']).isoformat()

            stats['total_size_mb'] = round(stats['total_size_mb'], 2)

            return stats

        except Exception as e:
            logger.error(f"Error getting backup statistics: {e}")
            return {}

    def schedule_automatic_backups(self, daily_time='02:00'):
        """
        Schedule automatic daily backups at specified time

        Args:
            daily_time: Time to run daily backup (HH:MM format)
        """
        def backup_scheduler():
            while True:
                try:
                    now = datetime.now()
                    target_hour, target_minute = map(int, daily_time.split(':'))
                    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

                    # If target time has passed today, schedule for tomorrow
                    if now > target_time:
                        target_time += timedelta(days=1)

                    # Wait until target time
                    sleep_seconds = (target_time - now).total_seconds()
                    logger.info(f"Next automatic backup scheduled for: {target_time}")

                    import time
                    time.sleep(sleep_seconds)

                    # Perform backup
                    self.create_backup('daily', 'Automatic scheduled backup')

                    # Weekly backup on Sundays
                    if now.weekday() == 6:
                        self.create_backup('weekly', 'Automatic weekly backup')

                    # Monthly backup on 1st of month
                    if now.day == 1:
                        self.create_backup('monthly', 'Automatic monthly backup')

                    # Cleanup old backups
                    self.cleanup_old_backups()

                except Exception as e:
                    logger.error(f"Error in backup scheduler: {e}")

        # Run scheduler in background thread
        scheduler_thread = threading.Thread(target=backup_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info(f"Automatic backup scheduler started (daily at {daily_time})")
