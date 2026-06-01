"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Training Data Pipeline

Training Data Pipeline
Transforms user feedback into LSTM training sequences
"""

import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from config import get_config
from feedback_collector import FeedbackCollector
from historical_data_manager import HistoricalDataManager

CONFIG = get_config()
logger = logging.getLogger(__name__)


class TrainingDataPipeline:
    """
    Converts confirmed predictions and service records into
    training sequences for LSTM model.
    """

    def __init__(self):
        self.feedback = FeedbackCollector()
        self.historical = HistoricalDataManager()
        self.sequence_length = 50  # 50 readings per sequence

    def generate_training_data(self) -> Tuple[List[List[Dict]], List[Dict]]:
        """
        Generate training sequences from confirmed feedback.

        Returns:
            (sequences, labels) - List of OBD sequences and their failure labels
        """
        sequences = []
        labels = []

        try:
            # Get all confirmed predictions
            confirmed = self.feedback.get_confirmed_predictions()

            for prediction in confirmed:
                profile_name = prediction.get('profile_name')
                profile_id = prediction.get('profile_id')
                failure_date = prediction.get('confirmed_date')
                failure_type = prediction.get('failure_type')

                if not all([profile_name, failure_date]):
                    continue

                # Get OBD data BEFORE the failure (7-30 days before)
                failure_dt = datetime.fromisoformat(failure_date)
                start_date = failure_dt - timedelta(days=30)
                end_date = failure_dt - timedelta(days=1)

                obd_data = self.historical.read_profile_data(
                    profile_name, profile_id,
                    start_date=start_date,
                    end_date=end_date
                )

                if len(obd_data) < self.sequence_length:
                    continue

                # Create sequence from OBD data
                sequence = self._extract_features(obd_data[-self.sequence_length:])
                sequences.append(sequence)

                # Create label
                label = {
                    'failure_occurred': 1,
                    'failure_type': failure_type,
                    'days_to_failure': (failure_dt - datetime.fromisoformat(obd_data[-1].get('timestamp', failure_date))).days
                }
                labels.append(label)

            # Also add negative samples (no failure)
            negative_sequences, negative_labels = self._generate_negative_samples()
            sequences.extend(negative_sequences)
            labels.extend(negative_labels)

            logger.info(f"Generated {len(sequences)} training sequences ({len(confirmed)} positive, {len(negative_sequences)} negative)")
            return sequences, labels

        except Exception as e:
            logger.error(f"Error generating training data: {e}")
            return [], []

    def _extract_features(self, obd_readings: List[Dict]) -> List[Dict]:
        """Extract relevant features from OBD readings"""
        features = []
        for reading in obd_readings:
            feature = {
                'rpm': reading.get('rpm', 0),
                'coolant_temp': reading.get('coolant_temp', 0),
                'engine_load': reading.get('engine_load', 0),
                'throttle_pos': reading.get('throttle_position', 0),
                'speed': reading.get('speed', 0),
                'intake_temp': reading.get('intake_temp', 0),
                'maf': reading.get('maf', 0),
                'fuel_pressure': reading.get('fuel_pressure', 0),
                'battery_voltage': reading.get('battery_voltage', 0),
                'fuel_trim_short': reading.get('short_fuel_trim', 0),
                'fuel_trim_long': reading.get('long_fuel_trim', 0),
            }
            features.append(feature)
        return features

    def _generate_negative_samples(self) -> Tuple[List, List]:
        """
        Generate negative samples (vehicles with no failures).

        These are OBD sequences from vehicles that have been running
        normally without any confirmed failures, providing the model
        with examples of healthy vehicle behavior.

        Returns:
            (sequences, labels) - Negative training samples
        """
        sequences = []
        labels = []

        try:
            # Get all confirmed failures to know which vehicles/dates to exclude
            confirmed_failures = self.feedback.get_confirmed_predictions()

            # Build set of (profile_name, date) pairs that had failures
            failure_dates = set()
            for pred in confirmed_failures:
                profile_name = pred.get('profile_name', '')
                failure_date = pred.get('confirmed_date', '')
                if profile_name and failure_date:
                    # Exclude 30 days before and after the failure
                    try:
                        fd = datetime.fromisoformat(failure_date)
                        for delta in range(-30, 31):
                            date_key = (profile_name, (fd + timedelta(days=delta)).strftime('%Y-%m-%d'))
                            failure_dates.add(date_key)
                    except ValueError as e:
                        logger.debug(f"Invalid date format for failure_date '{failure_date}': {e}")

            # Get list of all profiles from vehicle manager
            try:
                from vehicle_profile_manager import VehicleProfileManager
                vehicle_manager = VehicleProfileManager()
                all_profiles = vehicle_manager.get_all_profiles()
            except Exception as e:
                logger.warning(f"Could not get vehicle profiles: {e}")
                all_profiles = []

            # For each profile, get OBD data from periods with no failures
            negative_count = 0
            max_negative_samples = 100  # Limit to balance dataset

            for profile in all_profiles:
                if negative_count >= max_negative_samples:
                    break

                profile_name = profile.get('name', '')
                profile_id = profile.get('profile_id', 0)

                if not profile_name:
                    continue

                # Get historical data from last 90 days
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)

                try:
                    obd_data = self.historical.read_profile_data(
                        profile_name, profile_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                except Exception as e:
                    logger.debug(f"Could not read data for {profile_name}: {e}")
                    continue

                if len(obd_data) < self.sequence_length:
                    continue

                # Group data by date and filter out failure periods
                data_by_date = {}
                for reading in obd_data:
                    ts = reading.get('timestamp', '')
                    if ts:
                        try:
                            date_str = datetime.fromisoformat(ts).strftime('%Y-%m-%d')
                            date_key = (profile_name, date_str)

                            # Skip dates near failures
                            if date_key in failure_dates:
                                continue

                            if date_str not in data_by_date:
                                data_by_date[date_str] = []
                            data_by_date[date_str].append(reading)
                        except ValueError as e:
                            logger.debug(f"Invalid timestamp format: {e}")

                # Create sequences from clean data
                for date_str, readings in data_by_date.items():
                    if negative_count >= max_negative_samples:
                        break

                    if len(readings) >= self.sequence_length:
                        # Extract sequence
                        sequence = self._extract_features(readings[:self.sequence_length])
                        sequences.append(sequence)

                        # Create negative label (no failure)
                        label = {
                            'failure_occurred': 0,
                            'failure_type': 'no_failure',
                            'days_to_failure': -1  # -1 indicates no failure
                        }
                        labels.append(label)
                        negative_count += 1

            logger.info(f"Generated {len(sequences)} negative samples from healthy vehicle data")

        except Exception as e:
            logger.error(f"Error generating negative samples: {e}")

        return sequences, labels

    def export_training_dataset(self, output_path: str = None) -> str:
        """
        Export training dataset to JSON file for LSTM training.
        
        Args:
            output_path: Path to save training data (optional)
            
        Returns:
            Path to saved file
        """
        sequences, labels = self.generate_training_data()
        
        if not sequences:
            logger.warning("No training data to export")
            return ""
        
        # Prepare dataset
        dataset = {
            'metadata': {
                'total_sequences': len(sequences),
                'positive_samples': sum(1 for l in labels if l.get('failure_occurred') == 1),
                'negative_samples': sum(1 for l in labels if l.get('failure_occurred') == 0),
                'sequence_length': self.sequence_length,
                'exported_at': datetime.now().isoformat()
            },
            'sequences': sequences,
            'labels': labels
        }
        
        # Determine output path
        if output_path is None:
            output_path = str(CONFIG.AI_TRAINING_SETS_DIR / f"training_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file
        import json
        with open(output_path, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        logger.info(f"Training dataset exported to {output_path}")
        return output_path

    def get_training_statistics(self) -> Dict[str, Any]:
        """Get statistics about available training data"""
        confirmed = self.feedback.get_confirmed_predictions()
        
        total_samples = len(confirmed)
        positive_samples = len([p for p in confirmed if p.get('was_correct', False)])
        
        # Count by failure type
        failure_types = {}
        for pred in confirmed:
            ftype = pred.get('failure_type', 'unknown')
            failure_types[ftype] = failure_types.get(ftype, 0) + 1
        
        return {
            'total_confirmed_predictions': total_samples,
            'positive_samples': positive_samples,
            'negative_samples': total_samples - positive_samples,
            'failure_type_distribution': failure_types,
            'ready_for_training': total_samples >= 10  # Minimum threshold
        }


# Singleton instance
_training_pipeline = None

def get_training_pipeline() -> TrainingDataPipeline:
    """Get the singleton TrainingDataPipeline instance."""
    global _training_pipeline
    if _training_pipeline is None:
        _training_pipeline = TrainingDataPipeline()
    return _training_pipeline
