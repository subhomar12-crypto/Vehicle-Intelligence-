"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Lstm Bootstrap Trainer

LSTM Bootstrap Trainer
======================
Trains the LSTM model using synthetic training data.
Integrates with the existing LSTMPredictor and SyntheticTrainingDataManager.
"""

import os
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class LSTMBootstrapTrainer:
    """
    Bootstrap trainer for LSTM model using synthetic data.
    Handles data generation, training, and model evaluation.
    """

    def __init__(self, model_save_dir: str = "models"):
        self.model_save_dir = model_save_dir
        os.makedirs(model_save_dir, exist_ok=True)

        self.lstm_predictor = None
        self.training_history = None
        self.evaluation_metrics = None

    def initialize_lstm(self):
        """Initialize the LSTM predictor."""
        try:
            from lstm_predictor import LSTMPredictor
            self.lstm_predictor = LSTMPredictor(model_path=self.model_save_dir)
            logger.info("LSTM predictor initialized")
            return True
        except ImportError as e:
            logger.error(f"Failed to import LSTMPredictor: {e}")
            return False

    def generate_synthetic_data(self, samples_per_failure: int = 50,
                                  healthy_samples: int = 100) -> Tuple[np.ndarray, Dict]:
        """Generate synthetic training data."""
        from synthetic_training_data import SyntheticTrainingDataManager

        manager = SyntheticTrainingDataManager()

        # Generate dataset
        stats = manager.generate_training_dataset(
            samples_per_failure=samples_per_failure,
            healthy_samples=healthy_samples
        )

        # Prepare for LSTM
        X, y = manager.prepare_lstm_training_data(sequence_length=30)

        logger.info(f"Generated synthetic data: {stats}")
        return X, y

    def train_model(self,
                     samples_per_failure: int = 100,
                     healthy_samples: int = 200,
                     epochs: int = 50,
                     batch_size: int = 32,
                     validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train the LSTM model with synthetic data.

        Args:
            samples_per_failure: Failure sequences per type
            healthy_samples: Number of healthy sequences
            epochs: Training epochs
            batch_size: Training batch size
            validation_split: Fraction for validation

        Returns:
            Training results dictionary
        """
        if not self.lstm_predictor:
            if not self.initialize_lstm():
                return {'success': False, 'error': 'Failed to initialize LSTM'}

        # Generate training data
        logger.info("Generating synthetic training data...")

        from synthetic_training_data import SyntheticTrainingDataManager
        manager = SyntheticTrainingDataManager()

        # Generate dataset
        stats = manager.generate_training_dataset(
            samples_per_failure=samples_per_failure,
            healthy_samples=healthy_samples
        )

        if len(manager.generated_sequences) < 50:
            return {'success': False, 'error': 'Insufficient training data'}

        # Convert to LSTMPredictor's expected format
        # Each item needs 'sequence' (list of OBD readings) and 'label' (failure info)
        training_data = []

        for seq in manager.generated_sequences:
            # Convert synthetic sequence to OBD reading format
            obd_readings = []
            n_samples = len(seq.timestamps)

            for i in range(n_samples):
                reading = {'timestamp': seq.timestamps[i].isoformat()}

                # Map synthetic sensor data to OBD feature names
                if 'battery_voltage' in seq.sensor_data:
                    reading['voltage'] = seq.sensor_data['battery_voltage'][i]

                if 'charging_voltage' in seq.sensor_data:
                    # Map charging voltage to voltage when battery voltage not present
                    if 'voltage' not in reading:
                        reading['voltage'] = seq.sensor_data['charging_voltage'][i]

                if 'coolant_temp' in seq.sensor_data:
                    reading['coolant_temp'] = seq.sensor_data['coolant_temp'][i]

                if 'long_term_fuel_trim_bank1' in seq.sensor_data:
                    reading['long_fuel_trim'] = seq.sensor_data['long_term_fuel_trim_bank1'][i]

                if 'short_term_fuel_trim_bank1' in seq.sensor_data:
                    reading['short_fuel_trim'] = seq.sensor_data['short_term_fuel_trim_bank1'][i]

                # Add some derived/simulated values for other features
                reading['rpm'] = 800 + np.random.normal(0, 50)
                reading['speed'] = 0
                reading['engine_load'] = 20 + np.random.normal(0, 5)
                reading['intake_temp'] = 25 + np.random.normal(0, 3)
                reading['maf'] = 5 + np.random.normal(0, 0.5)
                reading['throttle_pos'] = 15 + np.random.normal(0, 2)
                reading['fuel_pressure'] = 35 + np.random.normal(0, 1)
                reading['timing_advance'] = 10 + np.random.normal(0, 2)

                obd_readings.append(reading)

            # Map failure types to LSTM predictor's expected types
            failure_type_map = {
                'none': 'no_failure',
                'battery_failure': 'battery',
                'alternator_failure': 'alternator',
                'thermostat_failure': 'thermostat',
                'fuel_system_failure': 'fuel_pump'  # Closest match
            }

            label = {
                'failure_occurred': seq.failure_occurred,
                'failure_type': failure_type_map.get(seq.failure_type, 'no_failure'),
                'days_to_failure': seq.days_to_failure if seq.days_to_failure else 60
            }

            training_data.append({
                'sequence': obd_readings,
                'label': label
            })

        logger.info(f"Training LSTM with {len(training_data)} sequences...")

        try:
            # Update LSTM config for training
            self.lstm_predictor.config.epochs = epochs
            self.lstm_predictor.config.batch_size = batch_size

            # Train using the predictor's method
            metrics = self.lstm_predictor.train(
                training_data=training_data,
                validation_split=validation_split,
                verbose=1
            )

            self.training_history = metrics

            # Save the model
            if not metrics.get('error'):
                self.lstm_predictor.save_model()

            return {
                'success': not metrics.get('error'),
                'training_samples': len(training_data),
                'epochs': epochs,
                'metrics': metrics,
                'model_saved': not metrics.get('error')
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _get_failure_type_name(self, type_id: int) -> str:
        """Convert failure type ID to name."""
        types = {
            0: 'none',
            1: 'battery_failure',
            2: 'alternator_failure',
            3: 'thermostat_failure',
            4: 'fuel_system_failure'
        }
        return types.get(type_id, 'unknown')

    def evaluate_model(self, test_samples: int = 50) -> Dict[str, Any]:
        """
        Evaluate the trained model on new synthetic data.

        Returns:
            Evaluation metrics
        """
        if not self.lstm_predictor or not self.lstm_predictor.is_trained:
            return {'error': 'Model not trained'}

        # Generate test data
        X_test, y_test = self.generate_synthetic_data(
            samples_per_failure=test_samples // 4,
            healthy_samples=test_samples // 4
        )

        # Make predictions
        correct_failure = 0
        correct_type = 0
        days_error = []

        for i in range(min(len(X_test), 100)):
            pred = self.lstm_predictor.predict(X_test[i])

            if pred:
                # Failure detection accuracy
                actual_failure = y_test['failure_probability'][i] > 0.5
                pred_failure = pred['failure_probability'] > 0.5
                if actual_failure == pred_failure:
                    correct_failure += 1

                # Type accuracy (only for failures)
                if actual_failure:
                    actual_type = self._get_failure_type_name(int(y_test['failure_type'][i]))
                    if pred.get('failure_type') == actual_type:
                        correct_type += 1

                    # Days prediction error
                    if y_test['days_to_failure'][i] >= 0 and pred.get('days_to_failure'):
                        error = abs(y_test['days_to_failure'][i] - pred['days_to_failure'])
                        days_error.append(error)

        n_tested = min(len(X_test), 100)
        n_failures = sum(1 for p in y_test['failure_probability'][:n_tested] if p > 0.5)

        self.evaluation_metrics = {
            'failure_detection_accuracy': correct_failure / n_tested if n_tested > 0 else 0,
            'failure_type_accuracy': correct_type / n_failures if n_failures > 0 else 0,
            'mean_days_error': float(np.mean(days_error)) if days_error else None,
            'samples_tested': n_tested,
            'failure_samples': n_failures
        }

        return self.evaluation_metrics

    def get_training_report(self) -> Dict[str, Any]:
        """Get a comprehensive training report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'model_initialized': self.lstm_predictor is not None,
            'model_trained': self.lstm_predictor.is_trained if self.lstm_predictor else False,
        }

        if self.training_history:
            report['training'] = self.training_history

        if self.evaluation_metrics:
            report['evaluation'] = self.evaluation_metrics

        if self.lstm_predictor and self.lstm_predictor.is_trained:
            report['model_version'] = self.lstm_predictor.model_version
            report['model_path'] = self.model_save_dir

        return report


def bootstrap_train(epochs: int = 50,
                     samples_per_failure: int = 100,
                     evaluate: bool = True) -> Dict[str, Any]:
    """
    Main function to bootstrap train the LSTM model.

    Args:
        epochs: Number of training epochs
        samples_per_failure: Number of failure samples per type
        evaluate: Whether to evaluate after training

    Returns:
        Training results
    """
    trainer = LSTMBootstrapTrainer()

    print("=" * 60)
    print("LSTM BOOTSTRAP TRAINING")
    print("=" * 60)

    # Train
    print("\n[1/3] Training model...")
    train_result = trainer.train_model(
        samples_per_failure=samples_per_failure,
        healthy_samples=samples_per_failure * 2,
        epochs=epochs
    )

    if not train_result.get('success'):
        print(f"Training failed: {train_result.get('error')}")
        return train_result

    print(f"Training complete: {train_result['training_samples']} samples, {epochs} epochs")

    # Evaluate
    if evaluate:
        print("\n[2/3] Evaluating model...")
        eval_result = trainer.evaluate_model(test_samples=100)
        print(f"Failure detection accuracy: {eval_result['failure_detection_accuracy']:.1%}")
        print(f"Failure type accuracy: {eval_result['failure_type_accuracy']:.1%}")
        if eval_result['mean_days_error']:
            print(f"Mean days prediction error: {eval_result['mean_days_error']:.1f} days")

    # Report
    print("\n[3/3] Generating report...")
    report = trainer.get_training_report()

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = bootstrap_train(epochs=30, samples_per_failure=50)
    print(f"\nFinal result: {result}")
