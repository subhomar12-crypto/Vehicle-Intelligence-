"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Scheduled Predictions

Scheduled Predictions Module
Automatically runs daily predictions for all active vehicles.

Features:
- Runs predictions at scheduled time (default 02:00 AM)
- Processes all active vehicle profiles
- Generates both short-term (3-7 day) and long-term (30-60 day) predictions
- Saves predictions to database
- Sends alerts for critical predictions
- Can run manually or as a background daemon
"""

import schedule
import time
import threading
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import config
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

from vehicle_profile_manager import VehicleProfileManager
from predictive_failure_engine import PredictiveFailureEngine

# Optional imports for enhanced predictions
try:
    from lstm_predictor import LSTMPredictor
    LSTM_AVAILABLE = True
except ImportError:
    LSTM_AVAILABLE = False

try:
    from alert_notifications import AlertNotificationManager
    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScheduledPredictionRunner:
    """
    Runs automated daily predictions for all vehicles.

    Usage:
        runner = ScheduledPredictionRunner()
        runner.start_daemon()  # Starts background scheduler

        # Or run manually:
        runner.run_predictions_for_all_vehicles()
    """

    def __init__(
        self,
        schedule_time: str = "02:00",
        min_data_days: int = 7,
        lstm_data_days: int = 30
    ):
        """
        Initialize the scheduled prediction runner.

        Args:
            schedule_time: Time to run daily predictions (HH:MM format)
            min_data_days: Minimum days of data required for predictions
            lstm_data_days: Minimum days of data required for LSTM predictions
        """
        self.schedule_time = schedule_time
        self.min_data_days = min_data_days
        self.lstm_data_days = lstm_data_days

        # Initialize components
        self.profile_manager = VehicleProfileManager()
        self.prediction_engine = PredictiveFailureEngine()

        # Initialize LSTM predictor if available
        self.lstm_predictor = None
        if LSTM_AVAILABLE:
            try:
                self.lstm_predictor = LSTMPredictor()
                logger.info("LSTM predictor initialized for long-term predictions")
            except Exception as e:
                logger.warning(f"LSTM predictor not available: {e}")

        # Initialize alert manager if available
        self.alert_manager = None
        if ALERTS_AVAILABLE:
            try:
                self.alert_manager = AlertNotificationManager()
                logger.info("Alert notifications enabled")
            except Exception as e:
                logger.warning(f"Alert notifications not available: {e}")

        # Database path for predictions
        if CONFIG:
            self.predictions_db = str(CONFIG.DATA_DIR / "predictions.db")
        else:
            self.predictions_db = "./data/predictions.db"

        # Ensure database exists
        self._init_database()

        # Scheduler thread
        self._scheduler_thread = None
        self._stop_flag = threading.Event()

        logger.info(f"ScheduledPredictionRunner initialized (daily at {schedule_time})")

    def _init_database(self):
        """Initialize predictions database"""
        try:
            Path(self.predictions_db).parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(self.predictions_db)
            cur = conn.cursor()

            # Create predictions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    vehicle_name TEXT,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prediction_type TEXT,  -- 'short_term' or 'long_term'
                    component TEXT,        -- Engine, Battery, Brakes, etc.
                    risk_level TEXT,       -- normal, warning, critical
                    risk_score REAL,       -- 0-100
                    confidence REAL,       -- 0-1
                    failure_window_min_days INTEGER,
                    failure_window_max_days INTEGER,
                    recommendation TEXT,
                    alert_sent BOOLEAN DEFAULT FALSE,
                    raw_prediction TEXT    -- JSON of full prediction data
                )
            """)

            # Create index for fast lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_vehicle
                ON scheduled_predictions(vehicle_id, generated_at DESC)
            """)

            # Create summary table for quick dashboard access
            cur.execute("""
                CREATE TABLE IF NOT EXISTS prediction_summary (
                    vehicle_id INTEGER PRIMARY KEY,
                    vehicle_name TEXT,
                    last_prediction_at TIMESTAMP,
                    overall_health_score REAL,
                    critical_components INTEGER DEFAULT 0,
                    warning_components INTEGER DEFAULT 0,
                    next_predicted_failure TEXT,
                    next_failure_days INTEGER
                )
            """)

            conn.commit()
            conn.close()
            logger.info("Predictions database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize predictions database: {e}")

    def get_vehicle_telemetry(
        self,
        vehicle_id: int,
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get telemetry data for a vehicle from the OBD database.

        Args:
            vehicle_id: Vehicle profile ID
            days: Number of days of data to retrieve

        Returns:
            List of telemetry records sorted by timestamp
        """
        try:
            # Try to get data from OBD server database
            if CONFIG:
                db_path = str(CONFIG.SERVER_DB_PATH)
            else:
                db_path = "C:/OBDserver/Previlium_OBD_Server/obd_data.db"

            if not Path(db_path).exists():
                logger.warning(f"OBD database not found: {db_path}")
                return []

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=days)

            cur.execute("""
                SELECT * FROM vehicle_data
                WHERE profile_id = ?
                AND timestamp > ?
                ORDER BY timestamp ASC
            """, (vehicle_id, cutoff_date.isoformat()))

            rows = cur.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get telemetry for vehicle {vehicle_id}: {e}")
            return []

    def run_prediction_for_vehicle(
        self,
        vehicle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run predictions for a single vehicle.

        Args:
            vehicle: Vehicle profile dictionary

        Returns:
            Dictionary with prediction results
        """
        vehicle_id = vehicle.get('profile_id') or vehicle.get('id')
        vehicle_name = vehicle.get('name', f'Vehicle {vehicle_id}')

        logger.info(f"Running predictions for {vehicle_name} (ID: {vehicle_id})")

        result = {
            'vehicle_id': vehicle_id,
            'vehicle_name': vehicle_name,
            'success': False,
            'short_term': None,
            'long_term': None,
            'alerts': []
        }

        try:
            # Get telemetry data
            telemetry = self.get_vehicle_telemetry(vehicle_id, days=60)

            if len(telemetry) < self.min_data_days:
                logger.warning(
                    f"Insufficient data for {vehicle_name}: "
                    f"{len(telemetry)} days (need {self.min_data_days})"
                )
                result['error'] = 'Insufficient data'
                return result

            # Run short-term prediction (3-7 days)
            try:
                short_term_pred = self.prediction_engine.analyze_failure_risk(
                    vehicle_profile=vehicle,
                    latest_data=telemetry[-1] if telemetry else {},
                    history=telemetry
                )
                result['short_term'] = short_term_pred

                # Save short-term predictions
                self._save_prediction(
                    vehicle_id=vehicle_id,
                    vehicle_name=vehicle_name,
                    prediction=short_term_pred,
                    prediction_type='short_term'
                )

            except Exception as e:
                logger.error(f"Short-term prediction failed: {e}")
                result['short_term_error'] = str(e)

            # Run long-term prediction if LSTM available and enough data
            if self.lstm_predictor and len(telemetry) >= self.lstm_data_days:
                try:
                    long_term_pred = self.lstm_predictor.predict(telemetry)
                    result['long_term'] = long_term_pred

                    # Save long-term predictions
                    self._save_prediction(
                        vehicle_id=vehicle_id,
                        vehicle_name=vehicle_name,
                        prediction=long_term_pred,
                        prediction_type='long_term'
                    )

                except Exception as e:
                    logger.warning(f"Long-term prediction failed: {e}")
                    result['long_term_error'] = str(e)

            # Check for critical alerts
            alerts = self._check_for_alerts(result)
            result['alerts'] = alerts

            # Send alerts if needed
            if alerts and self.alert_manager:
                for alert in alerts:
                    self._send_alert(vehicle, alert)

            # Update summary
            self._update_summary(vehicle_id, vehicle_name, result)

            result['success'] = True
            logger.info(f"Predictions complete for {vehicle_name}")

        except Exception as e:
            logger.error(f"Prediction failed for {vehicle_name}: {e}")
            result['error'] = str(e)

        return result

    def run_predictions_for_all_vehicles(self) -> Dict[str, Any]:
        """
        Run predictions for all active vehicles.

        Returns:
            Summary of prediction run
        """
        logger.info("=" * 60)
        logger.info("Starting scheduled predictions for all vehicles")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Get all vehicle profiles
        vehicles = self.profile_manager.get_all_profiles()

        if not vehicles:
            logger.warning("No vehicle profiles found")
            return {
                'success': False,
                'error': 'No vehicle profiles found',
                'vehicles_processed': 0
            }

        results = {
            'success': True,
            'start_time': start_time.isoformat(),
            'total_vehicles': len(vehicles),
            'vehicles_processed': 0,
            'vehicles_skipped': 0,
            'vehicles_failed': 0,
            'critical_alerts': 0,
            'warning_alerts': 0,
            'vehicle_results': []
        }

        for vehicle in vehicles:
            try:
                pred_result = self.run_prediction_for_vehicle(vehicle)
                results['vehicle_results'].append(pred_result)

                if pred_result.get('success'):
                    results['vehicles_processed'] += 1

                    # Count alerts
                    for alert in pred_result.get('alerts', []):
                        if alert.get('severity') == 'critical':
                            results['critical_alerts'] += 1
                        elif alert.get('severity') == 'warning':
                            results['warning_alerts'] += 1

                elif 'Insufficient data' in pred_result.get('error', ''):
                    results['vehicles_skipped'] += 1
                else:
                    results['vehicles_failed'] += 1

            except Exception as e:
                logger.error(f"Error processing vehicle: {e}")
                results['vehicles_failed'] += 1

        end_time = datetime.now()
        results['end_time'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"Scheduled predictions complete")
        logger.info(f"  Processed: {results['vehicles_processed']}")
        logger.info(f"  Skipped: {results['vehicles_skipped']}")
        logger.info(f"  Failed: {results['vehicles_failed']}")
        logger.info(f"  Critical alerts: {results['critical_alerts']}")
        logger.info(f"  Warning alerts: {results['warning_alerts']}")
        logger.info(f"  Duration: {results['duration_seconds']:.1f}s")
        logger.info("=" * 60)

        return results

    def _save_prediction(
        self,
        vehicle_id: int,
        vehicle_name: str,
        prediction: Dict[str, Any],
        prediction_type: str
    ):
        """Save prediction to database"""
        try:
            import json
            conn = sqlite3.connect(self.predictions_db)
            cur = conn.cursor()

            # Handle different prediction formats
            components = prediction.get('components', prediction.get('risk_factors', []))

            if isinstance(components, dict):
                # Convert dict to list
                components = [
                    {'component': k, **v}
                    for k, v in components.items()
                ]

            for comp in components:
                component_name = comp.get('component', comp.get('name', 'Unknown'))
                risk_level = comp.get('risk_level', comp.get('severity', 'normal'))
                risk_score = comp.get('risk_score', comp.get('risk', 0))
                confidence = comp.get('confidence', 0.5)

                # Get failure window
                window = comp.get('failure_window', {})
                min_days = window.get('min_days', window.get('days_min', None))
                max_days = window.get('max_days', window.get('days_max', None))

                recommendation = comp.get('recommendation', comp.get('action', ''))

                cur.execute("""
                    INSERT INTO scheduled_predictions (
                        vehicle_id, vehicle_name, prediction_type,
                        component, risk_level, risk_score, confidence,
                        failure_window_min_days, failure_window_max_days,
                        recommendation, raw_prediction
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vehicle_id, vehicle_name, prediction_type,
                    component_name, risk_level, risk_score, confidence,
                    min_days, max_days, recommendation,
                    json.dumps(comp)
                ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to save prediction: {e}")

    def _check_for_alerts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check prediction results for alert conditions"""
        alerts = []

        # Check short-term predictions
        short_term = result.get('short_term', {})
        components = short_term.get('components', short_term.get('risk_factors', {}))

        if isinstance(components, dict):
            for comp_name, comp_data in components.items():
                risk_level = comp_data.get('risk_level', comp_data.get('severity', ''))
                risk_score = comp_data.get('risk_score', comp_data.get('risk', 0))

                if risk_level == 'critical' or risk_score >= 80:
                    alerts.append({
                        'severity': 'critical',
                        'component': comp_name,
                        'message': f"Critical risk detected: {comp_name}",
                        'risk_score': risk_score
                    })
                elif risk_level == 'warning' or risk_score >= 60:
                    alerts.append({
                        'severity': 'warning',
                        'component': comp_name,
                        'message': f"Warning: {comp_name} needs attention",
                        'risk_score': risk_score
                    })

        return alerts

    def _send_alert(self, vehicle: Dict[str, Any], alert: Dict[str, Any]):
        """Send alert notification"""
        try:
            if self.alert_manager:
                self.alert_manager.send_alert(
                    title=f"Vehicle Alert: {vehicle.get('name', 'Unknown')}",
                    message=alert.get('message', 'Prediction alert'),
                    severity=alert.get('severity', 'warning'),
                    vehicle_id=vehicle.get('profile_id')
                )
                logger.info(f"Alert sent for {vehicle.get('name')}: {alert.get('message')}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    def _update_summary(
        self,
        vehicle_id: int,
        vehicle_name: str,
        result: Dict[str, Any]
    ):
        """Update prediction summary for quick dashboard access"""
        try:
            conn = sqlite3.connect(self.predictions_db)
            cur = conn.cursor()

            # Calculate summary metrics
            short_term = result.get('short_term', {})
            components = short_term.get('components', short_term.get('risk_factors', {}))

            critical_count = 0
            warning_count = 0
            next_failure = None
            next_failure_days = None
            health_scores = []

            if isinstance(components, dict):
                for comp_name, comp_data in components.items():
                    risk_level = comp_data.get('risk_level', comp_data.get('severity', ''))
                    health_score = 100 - comp_data.get('risk_score', comp_data.get('risk', 0))
                    health_scores.append(health_score)

                    if risk_level == 'critical':
                        critical_count += 1
                        window = comp_data.get('failure_window', {})
                        days = window.get('min_days', window.get('days_min'))
                        if days and (next_failure_days is None or days < next_failure_days):
                            next_failure = comp_name
                            next_failure_days = days
                    elif risk_level == 'warning':
                        warning_count += 1

            overall_health = sum(health_scores) / len(health_scores) if health_scores else 100

            cur.execute("""
                INSERT OR REPLACE INTO prediction_summary (
                    vehicle_id, vehicle_name, last_prediction_at,
                    overall_health_score, critical_components, warning_components,
                    next_predicted_failure, next_failure_days
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vehicle_id, vehicle_name, datetime.now().isoformat(),
                overall_health, critical_count, warning_count,
                next_failure, next_failure_days
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to update summary: {e}")

    def start_daemon(self):
        """Start the scheduler as a background daemon thread"""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return

        # Schedule daily predictions
        schedule.every().day.at(self.schedule_time).do(
            self.run_predictions_for_all_vehicles
        )

        logger.info(f"Scheduled daily predictions at {self.schedule_time}")

        # Start daemon thread
        self._stop_flag.clear()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=True,
            name="PredictionScheduler"
        )
        self._scheduler_thread.start()
        logger.info("Prediction scheduler daemon started")

    def _run_scheduler(self):
        """Run the scheduler loop"""
        while not self._stop_flag.is_set():
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def stop_daemon(self):
        """Stop the scheduler daemon"""
        self._stop_flag.set()
        schedule.clear()
        logger.info("Prediction scheduler stopped")

    def get_latest_predictions(
        self,
        vehicle_id: int = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get latest predictions from database.

        Args:
            vehicle_id: Optional vehicle ID filter
            days: Number of days to look back

        Returns:
            List of prediction records
        """
        try:
            conn = sqlite3.connect(self.predictions_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cutoff = datetime.now() - timedelta(days=days)

            if vehicle_id:
                cur.execute("""
                    SELECT * FROM scheduled_predictions
                    WHERE vehicle_id = ? AND generated_at > ?
                    ORDER BY generated_at DESC
                """, (vehicle_id, cutoff.isoformat()))
            else:
                cur.execute("""
                    SELECT * FROM scheduled_predictions
                    WHERE generated_at > ?
                    ORDER BY generated_at DESC
                """, (cutoff.isoformat(),))

            rows = cur.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get predictions: {e}")
            return []

    def get_prediction_summary(self) -> List[Dict[str, Any]]:
        """Get prediction summary for all vehicles"""
        try:
            conn = sqlite3.connect(self.predictions_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM prediction_summary
                ORDER BY overall_health_score ASC
            """)

            rows = cur.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return []


# Convenience function for quick access
def run_daily_predictions():
    """Run predictions for all vehicles (convenience function)"""
    runner = ScheduledPredictionRunner()
    return runner.run_predictions_for_all_vehicles()


# Entry point for standalone execution
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scheduled Vehicle Predictions")
    parser.add_argument(
        '--run-now',
        action='store_true',
        help="Run predictions immediately"
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help="Start as background daemon"
    )
    parser.add_argument(
        '--time',
        default="02:00",
        help="Schedule time (HH:MM format, default 02:00)"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scheduled_predictions.log'),
            logging.StreamHandler()
        ]
    )

    runner = ScheduledPredictionRunner(schedule_time=args.time)

    if args.run_now:
        print("Running predictions now...")
        results = runner.run_predictions_for_all_vehicles()
        print(f"Complete! Processed {results['vehicles_processed']} vehicles.")

    elif args.daemon:
        print(f"Starting prediction scheduler daemon (daily at {args.time})...")
        runner.start_daemon()

        # Keep main thread alive
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            runner.stop_daemon()
    else:
        parser.print_help()
