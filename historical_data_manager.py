"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Historical Data Manager

Historical Data Manager - Stores all OBD data forever for AI learning
Organizes data by profile_name/car_number in structured folders
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """
    Manages permanent storage of OBD data for AI training and analysis

    Storage Structure:
    D:/Predict/historical_data/
        ├── ProfileName_CarNumber/
        │   ├── profile_info.json
        │   ├── obd_data_YYYY_MM.jsonl (JSON Lines format)
        │   ├── trips/
        │   │   ├── trip_YYYYMMDD_HHMMSS.json
        │   └── summary/
        │       ├── monthly_summary_YYYY_MM.json
        └── ai_training/
            ├── combined_dataset.csv
            └── training_metadata.json
    """

    def __init__(self, base_path=None):
        """Initialize historical data manager"""
        from config import get_config
        CONFIG = get_config()
        
        self.base_path = base_path if base_path else str(CONFIG.DATA_DIR / "historical_data")
        self.ensure_base_directory()
        logger.info(f"Historical Data Manager initialized at: {self.base_path}")

    def ensure_base_directory(self):
        """Ensure base directory and subdirectories exist"""
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(os.path.join(self.base_path, 'ai_training'), exist_ok=True)

    def get_profile_folder_name(self, profile_name: str, profile_id: int) -> str:
        """Generate folder name: ProfileName_ID"""
        # Sanitize profile name for filesystem
        safe_name = "".join(c for c in profile_name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(' ', '_')
        return f"{safe_name}_{profile_id}"

    def ensure_profile_directory(self, profile_name: str, profile_id: int) -> str:
        """Ensure profile-specific directory exists and return path"""
        folder_name = self.get_profile_folder_name(profile_name, profile_id)
        profile_path = os.path.join(self.base_path, folder_name)

        # Create directory structure
        os.makedirs(profile_path, exist_ok=True)
        os.makedirs(os.path.join(profile_path, 'trips'), exist_ok=True)
        os.makedirs(os.path.join(profile_path, 'summary'), exist_ok=True)

        return profile_path

    def save_profile_info(self, profile_data: Dict[str, Any]):
        """Save profile metadata"""
        try:
            profile_path = self.ensure_profile_directory(
                profile_data.get('name', 'Unknown'),
                profile_data.get('profile_id', 0)
            )

            info_file = os.path.join(profile_path, 'profile_info.json')

            # Update with timestamp
            profile_data['last_updated'] = datetime.now().isoformat()

            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved profile info for {profile_data.get('name')}")
            return True

        except Exception as e:
            logger.error(f"Error saving profile info: {e}")
            return False

    def append_obd_data(self, profile_name: str, profile_id: int, obd_data: Dict[str, Any]):
        """
        Append OBD data to monthly JSONL file
        Uses JSON Lines format for efficient append and reading
        """
        try:
            profile_path = self.ensure_profile_directory(profile_name, profile_id)

            # Generate monthly file name
            now = datetime.now()
            data_file = os.path.join(profile_path, f"obd_data_{now.year}_{now.month:02d}.jsonl")

            # Add timestamp if not present
            if 'timestamp' not in obd_data:
                obd_data['timestamp'] = datetime.now().isoformat()

            # Append to JSON Lines file (one JSON object per line)
            with open(data_file, 'a', encoding='utf-8') as f:
                json.dump(obd_data, f, ensure_ascii=False)
                f.write('\n')

            return True

        except Exception as e:
            logger.error(f"Error appending OBD data: {e}")
            return False

    def read_profile_data(self, profile_name: str, profile_id: int,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Read historical data for a profile with optional date range
        Returns list of OBD data entries
        """
        try:
            folder_name = self.get_profile_folder_name(profile_name, profile_id)
            profile_path = os.path.join(self.base_path, folder_name)

            if not os.path.exists(profile_path):
                logger.warning(f"No historical data found for {profile_name}")
                return []

            all_data = []

            # Find all JSONL files
            for filename in sorted(os.listdir(profile_path)):
                if filename.startswith('obd_data_') and filename.endswith('.jsonl'):
                    file_path = os.path.join(profile_path, filename)

                    # Read JSONL file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    data = json.loads(line)

                                    # Apply date filters if specified
                                    if start_date or end_date:
                                        timestamp_str = data.get('timestamp')
                                        if timestamp_str:
                                            data_time = datetime.fromisoformat(timestamp_str)
                                            if start_date and data_time < start_date:
                                                continue
                                            if end_date and data_time > end_date:
                                                continue

                                    all_data.append(data)

                                    # Apply limit if specified
                                    if limit and len(all_data) >= limit:
                                        return all_data

                                except json.JSONDecodeError:
                                    logger.warning(f"Invalid JSON in {filename}")
                                    continue

            logger.info(f"Read {len(all_data)} records for {profile_name}")
            return all_data

        except Exception as e:
            logger.error(f"Error reading profile data: {e}")
            return []

    def save_trip_data(self, profile_name: str, profile_id: int, trip_data: Dict[str, Any]):
        """Save individual trip data"""
        try:
            profile_path = self.ensure_profile_directory(profile_name, profile_id)
            trips_path = os.path.join(profile_path, 'trips')

            # Generate trip filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            trip_file = os.path.join(trips_path, f"trip_{timestamp}.json")

            trip_data['saved_at'] = datetime.now().isoformat()

            with open(trip_file, 'w', encoding='utf-8') as f:
                json.dump(trip_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved trip data: {trip_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving trip data: {e}")
            return False

    def generate_monthly_summary(self, profile_name: str, profile_id: int,
                                year: int, month: int) -> Dict[str, Any]:
        """Generate monthly summary statistics"""
        try:
            # Read data for the month
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            data = self.read_profile_data(profile_name, profile_id, start_date, end_date)

            if not data:
                return {}

            summary = {
                'year': year,
                'month': month,
                'total_records': len(data),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'statistics': self._calculate_statistics(data)
            }

            # Save summary
            profile_path = self.ensure_profile_directory(profile_name, profile_id)
            summary_path = os.path.join(profile_path, 'summary')
            summary_file = os.path.join(summary_path, f"monthly_summary_{year}_{month:02d}.json")

            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            return summary

        except Exception as e:
            logger.error(f"Error generating monthly summary: {e}")
            return {}

    def _calculate_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical summary from OBD data"""
        stats = {
            'rpm': {'min': None, 'max': None, 'avg': None},
            'speed': {'min': None, 'max': None, 'avg': None},
            'coolant_temp': {'min': None, 'max': None, 'avg': None},
            'engine_load': {'min': None, 'max': None, 'avg': None},
        }

        try:
            # Extract values for common parameters
            for param in ['rpm', 'speed', 'coolant_temp', 'engine_load']:
                values = [d.get(param) for d in data if d.get(param) is not None]
                if values:
                    stats[param] = {
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values)
                    }
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")

        return stats

    def export_for_ai_training(self, output_format='csv') -> str:
        """
        Export all historical data for AI training
        Combines data from all profiles into a unified training dataset
        """
        try:
            ai_training_path = os.path.join(self.base_path, 'ai_training')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if output_format == 'csv':
                output_file = os.path.join(ai_training_path, f'combined_dataset_{timestamp}.csv')
                return self._export_to_csv(output_file)
            elif output_format == 'json':
                output_file = os.path.join(ai_training_path, f'combined_dataset_{timestamp}.json')
                return self._export_to_json(output_file)
            else:
                raise ValueError(f"Unsupported format: {output_format}")

        except Exception as e:
            logger.error(f"Error exporting for AI training: {e}")
            return ""

    def _export_to_csv(self, output_file: str) -> str:
        """Export all data to CSV format"""
        try:
            all_data = []

            # Iterate through all profile folders
            for folder_name in os.listdir(self.base_path):
                folder_path = os.path.join(self.base_path, folder_name)
                if not os.path.isdir(folder_path) or folder_name == 'ai_training':
                    continue

                # Read all JSONL files in this profile
                for filename in os.listdir(folder_path):
                    if filename.startswith('obd_data_') and filename.endswith('.jsonl'):
                        file_path = os.path.join(folder_path, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.strip():
                                    try:
                                        data = json.loads(line)
                                        data['profile_folder'] = folder_name
                                        all_data.append(data)
                                    except json.JSONDecodeError:
                                        continue

            if not all_data:
                logger.warning("No data to export")
                return ""

            # Get all unique keys
            all_keys = set()
            for data in all_data:
                all_keys.update(data.keys())

            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(all_data)

            logger.info(f"Exported {len(all_data)} records to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return ""

    def _export_to_json(self, output_file: str) -> str:
        """Export all data to JSON format"""
        try:
            all_data = []

            # Same logic as CSV export
            for folder_name in os.listdir(self.base_path):
                folder_path = os.path.join(self.base_path, folder_name)
                if not os.path.isdir(folder_path) or folder_name == 'ai_training':
                    continue

                for filename in os.listdir(folder_path):
                    if filename.startswith('obd_data_') and filename.endswith('.jsonl'):
                        file_path = os.path.join(folder_path, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.strip():
                                    try:
                                        data = json.loads(line)
                                        data['profile_folder'] = folder_name
                                        all_data.append(data)
                                    except json.JSONDecodeError:
                                        continue

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(all_data)} records to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return ""

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                'total_profiles': 0,
                'total_size_mb': 0,
                'total_records': 0,
                'profiles': []
            }

            for folder_name in os.listdir(self.base_path):
                folder_path = os.path.join(self.base_path, folder_name)
                if not os.path.isdir(folder_path) or folder_name == 'ai_training':
                    continue

                profile_stats = {
                    'name': folder_name,
                    'records': 0,
                    'size_mb': 0
                }

                # Count records and size
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        profile_stats['size_mb'] += os.path.getsize(file_path) / (1024 * 1024)

                        if filename.endswith('.jsonl'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                profile_stats['records'] += sum(1 for line in f if line.strip())

                stats['profiles'].append(profile_stats)
                stats['total_profiles'] += 1
                stats['total_size_mb'] += profile_stats['size_mb']
                stats['total_records'] += profile_stats['records']

            return stats

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}
