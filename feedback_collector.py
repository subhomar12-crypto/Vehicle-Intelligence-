"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Feedback Collector

Feedback Collector - Labeled Training Data Collection System
=============================================================
Collects confirmed failure outcomes to build labeled datasets for LSTM training.

Features:
- Service history import and manual entry
- Prediction confirmation workflow
- DTC-based automatic labeling
- Labeled sequence export for training
- Statistics and data quality metrics
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import csv
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of component failures."""
    BATTERY = "battery"
    ALTERNATOR = "alternator"
    STARTER = "starter"
    FUEL_PUMP = "fuel_pump"
    FUEL_INJECTOR = "fuel_injector"
    IGNITION_COIL = "ignition_coil"
    SPARK_PLUG = "spark_plug"
    OXYGEN_SENSOR = "oxygen_sensor"
    CATALYTIC_CONVERTER = "catalytic_converter"
    MAF_SENSOR = "maf_sensor"
    MAP_SENSOR = "map_sensor"
    COOLANT_TEMP_SENSOR = "coolant_temp_sensor"
    THERMOSTAT = "thermostat"
    WATER_PUMP = "water_pump"
    RADIATOR = "radiator"
    TRANSMISSION = "transmission"
    BRAKE_PADS = "brake_pads"
    BRAKE_ROTORS = "brake_rotors"
    SUSPENSION = "suspension"
    TIMING_BELT = "timing_belt"
    SERPENTINE_BELT = "serpentine_belt"
    AC_COMPRESSOR = "ac_compressor"
    POWER_STEERING = "power_steering"
    OTHER = "other"


class ConfirmationSource(Enum):
    """Source of failure confirmation."""
    MANUAL_USER = "manual_user"           # User confirmed in UI
    SERVICE_RECORD = "service_record"      # From service history import
    DTC_CONFIRMED = "dtc_confirmed"        # DTC code appeared after prediction
    MECHANIC_REPORT = "mechanic_report"    # Professional diagnosis
    PREDICTION_EXPIRED = "prediction_expired"  # No failure occurred (negative sample)


@dataclass
class ServiceRecord:
    """A service/repair record."""
    record_id: str
    vehicle_id: str
    service_date: str
    mileage: int
    service_type: str  # "repair", "maintenance", "inspection"
    component: str     # Component serviced/replaced
    failure_type: Optional[str]  # FailureType value if failure
    description: str
    cost: float
    shop_name: Optional[str]
    technician_notes: Optional[str]
    parts_replaced: List[str]
    dtc_codes: List[str]  # Related DTCs
    created_at: str


@dataclass
class PredictionFeedback:
    """Feedback on a specific prediction."""
    feedback_id: str
    prediction_id: str
    vehicle_id: str
    prediction_type: str      # What was predicted
    predicted_component: str
    predicted_date: str       # When prediction was made
    predicted_failure_date: str  # When failure was predicted to occur
    confidence_score: float

    # Feedback data
    feedback_date: str
    was_correct: bool
    actual_outcome: str       # "failed", "no_failure", "partial", "unknown"
    actual_failure_date: Optional[str]
    confirmation_source: str  # ConfirmationSource value
    service_record_id: Optional[str]  # Link to service record if available
    user_notes: Optional[str]

    # Training data linkage
    sequence_start_date: str  # Start of OBD data sequence before prediction
    sequence_end_date: str    # End of sequence (failure or prediction date)
    days_before_failure: Optional[int]  # Actual days warning given


@dataclass
class LabeledSequence:
    """A labeled training sequence for LSTM."""
    sequence_id: str
    vehicle_id: str
    failure_type: str
    failure_occurred: bool
    failure_date: Optional[str]
    sequence_start: str
    sequence_end: str
    sequence_length_days: int
    data_points: int
    feature_columns: List[str]
    label: int  # 1 = failure, 0 = no failure
    days_to_failure: Optional[int]


class FeedbackCollector:
    """
    Collects and manages labeled training data for predictive maintenance.
    """

    def __init__(self, storage_path: str = None):
        """Initialize the feedback collector."""
        self.storage_path = Path(storage_path or str(CONFIG.DATA_DIR / "feedback"))
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.storage_path / "feedback.db"
        self._init_database()

        # Cache for pending predictions awaiting feedback
        self.pending_predictions: Dict[str, Dict] = {}
        self._load_pending()

        logger.info(f"FeedbackCollector initialized at {self.storage_path}")

    def _init_database(self):
        """Initialize SQLite database for feedback storage."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Service records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_records (
                record_id TEXT PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                service_date TEXT NOT NULL,
                mileage INTEGER,
                service_type TEXT,
                component TEXT,
                failure_type TEXT,
                description TEXT,
                cost REAL,
                shop_name TEXT,
                technician_notes TEXT,
                parts_replaced TEXT,
                dtc_codes TEXT,
                created_at TEXT
            )
        """)

        # Prediction feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prediction_feedback (
                feedback_id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                prediction_type TEXT,
                predicted_component TEXT,
                predicted_date TEXT,
                predicted_failure_date TEXT,
                confidence_score REAL,
                feedback_date TEXT,
                was_correct INTEGER,
                actual_outcome TEXT,
                actual_failure_date TEXT,
                confirmation_source TEXT,
                service_record_id TEXT,
                user_notes TEXT,
                sequence_start_date TEXT,
                sequence_end_date TEXT,
                days_before_failure INTEGER,
                FOREIGN KEY (service_record_id) REFERENCES service_records(record_id)
            )
        """)

        # Labeled sequences table (for LSTM training export)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS labeled_sequences (
                sequence_id TEXT PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                failure_type TEXT,
                failure_occurred INTEGER,
                failure_date TEXT,
                sequence_start TEXT,
                sequence_end TEXT,
                sequence_length_days INTEGER,
                data_points INTEGER,
                feature_columns TEXT,
                label INTEGER,
                days_to_failure INTEGER,
                exported INTEGER DEFAULT 0
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_vehicle ON service_records(vehicle_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_date ON service_records(service_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_vehicle ON prediction_feedback(vehicle_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_correct ON prediction_feedback(was_correct)")

        conn.commit()
        conn.close()

    def _load_pending(self):
        """Load pending predictions awaiting feedback."""
        pending_file = self.storage_path / "pending_predictions.json"
        if pending_file.exists():
            try:
                with open(pending_file, 'r') as f:
                    self.pending_predictions = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load pending predictions: {e}")
                self.pending_predictions = {}

    def _save_pending(self):
        """Save pending predictions."""
        pending_file = self.storage_path / "pending_predictions.json"
        try:
            with open(pending_file, 'w') as f:
                json.dump(self.pending_predictions, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save pending predictions: {e}")

    # =========================================================================
    # Service Record Management
    # =========================================================================

    def add_service_record(
        self,
        vehicle_id: str,
        service_date: str,
        mileage: int,
        service_type: str,
        component: str,
        description: str,
        failure_type: Optional[str] = None,
        cost: float = 0.0,
        shop_name: Optional[str] = None,
        technician_notes: Optional[str] = None,
        parts_replaced: Optional[List[str]] = None,
        dtc_codes: Optional[List[str]] = None
    ) -> str:
        """
        Add a service record.

        Returns:
            record_id: The ID of the created record
        """
        record_id = f"SR_{vehicle_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        record = ServiceRecord(
            record_id=record_id,
            vehicle_id=vehicle_id,
            service_date=service_date,
            mileage=mileage,
            service_type=service_type,
            component=component,
            failure_type=failure_type,
            description=description,
            cost=cost,
            shop_name=shop_name,
            technician_notes=technician_notes,
            parts_replaced=parts_replaced or [],
            dtc_codes=dtc_codes or [],
            created_at=datetime.now().isoformat()
        )

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO service_records
            (record_id, vehicle_id, service_date, mileage, service_type, component,
             failure_type, description, cost, shop_name, technician_notes,
             parts_replaced, dtc_codes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.record_id, record.vehicle_id, record.service_date,
            record.mileage, record.service_type, record.component,
            record.failure_type, record.description, record.cost,
            record.shop_name, record.technician_notes,
            json.dumps(record.parts_replaced), json.dumps(record.dtc_codes),
            record.created_at
        ))

        conn.commit()
        conn.close()

        # Auto-link to pending predictions if this is a failure
        if failure_type:
            self._auto_link_prediction(vehicle_id, component, failure_type, service_date, record_id)

        logger.info(f"Added service record {record_id} for vehicle {vehicle_id}")
        return record_id

    def import_service_history_csv(self, csv_path: str, vehicle_id: str) -> Dict[str, Any]:
        """
        Import service history from CSV file.

        Expected columns: date, mileage, type, component, description, cost, failure_type
        """
        imported = 0
        errors = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        self.add_service_record(
                            vehicle_id=vehicle_id,
                            service_date=row.get('date', ''),
                            mileage=int(row.get('mileage', 0)),
                            service_type=row.get('type', 'repair'),
                            component=row.get('component', 'unknown'),
                            description=row.get('description', ''),
                            failure_type=row.get('failure_type'),
                            cost=float(row.get('cost', 0))
                        )
                        imported += 1
                    except Exception as e:
                        errors.append(f"Row error: {e}")

        except Exception as e:
            return {'success': False, 'error': str(e), 'imported': 0}

        return {
            'success': True,
            'imported': imported,
            'errors': errors
        }

    def get_service_records(
        self,
        vehicle_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        failure_only: bool = False
    ) -> List[Dict]:
        """Get service records for a vehicle."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM service_records WHERE vehicle_id = ?"
        params = [vehicle_id]

        if start_date:
            query += " AND service_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND service_date <= ?"
            params.append(end_date)
        if failure_only:
            query += " AND failure_type IS NOT NULL"

        query += " ORDER BY service_date DESC"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        records = []

        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            record['parts_replaced'] = json.loads(record['parts_replaced'] or '[]')
            record['dtc_codes'] = json.loads(record['dtc_codes'] or '[]')
            records.append(record)

        conn.close()
        return records

    # =========================================================================
    # Prediction Tracking & Feedback
    # =========================================================================

    def register_prediction(
        self,
        prediction_id: str,
        vehicle_id: str,
        prediction_type: str,
        predicted_component: str,
        predicted_failure_date: str,
        confidence_score: float,
        sequence_start_date: str
    ):
        """
        Register a prediction for future feedback tracking.
        Call this when a prediction is made.
        """
        self.pending_predictions[prediction_id] = {
            'prediction_id': prediction_id,
            'vehicle_id': vehicle_id,
            'prediction_type': prediction_type,
            'predicted_component': predicted_component,
            'predicted_date': datetime.now().isoformat(),
            'predicted_failure_date': predicted_failure_date,
            'confidence_score': confidence_score,
            'sequence_start_date': sequence_start_date,
            'status': 'pending'
        }
        self._save_pending()
        logger.debug(f"Registered prediction {prediction_id} for tracking")

    def confirm_prediction(
        self,
        prediction_id: str,
        was_correct: bool,
        actual_outcome: str,
        confirmation_source: str,
        actual_failure_date: Optional[str] = None,
        service_record_id: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm whether a prediction was correct.

        Args:
            prediction_id: The prediction to confirm
            was_correct: True if prediction was accurate
            actual_outcome: "failed", "no_failure", "partial", "unknown"
            confirmation_source: ConfirmationSource value
            actual_failure_date: When failure actually occurred (if applicable)
            service_record_id: Link to service record
            user_notes: Additional notes
        """
        if prediction_id not in self.pending_predictions:
            return {'success': False, 'error': 'Prediction not found'}

        pred = self.pending_predictions[prediction_id]

        # Calculate days warning if failure occurred
        days_before_failure = None
        if actual_failure_date and was_correct:
            try:
                pred_date = datetime.fromisoformat(pred['predicted_date'])
                fail_date = datetime.fromisoformat(actual_failure_date)
                days_before_failure = (fail_date - pred_date).days
            except:
                pass

        feedback_id = f"FB_{prediction_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        feedback = PredictionFeedback(
            feedback_id=feedback_id,
            prediction_id=prediction_id,
            vehicle_id=pred['vehicle_id'],
            prediction_type=pred['prediction_type'],
            predicted_component=pred['predicted_component'],
            predicted_date=pred['predicted_date'],
            predicted_failure_date=pred['predicted_failure_date'],
            confidence_score=pred['confidence_score'],
            feedback_date=datetime.now().isoformat(),
            was_correct=was_correct,
            actual_outcome=actual_outcome,
            actual_failure_date=actual_failure_date,
            confirmation_source=confirmation_source,
            service_record_id=service_record_id,
            user_notes=user_notes,
            sequence_start_date=pred['sequence_start_date'],
            sequence_end_date=actual_failure_date or datetime.now().isoformat(),
            days_before_failure=days_before_failure
        )

        # Store in database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO prediction_feedback
            (feedback_id, prediction_id, vehicle_id, prediction_type, predicted_component,
             predicted_date, predicted_failure_date, confidence_score, feedback_date,
             was_correct, actual_outcome, actual_failure_date, confirmation_source,
             service_record_id, user_notes, sequence_start_date, sequence_end_date,
             days_before_failure)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.feedback_id, feedback.prediction_id, feedback.vehicle_id,
            feedback.prediction_type, feedback.predicted_component,
            feedback.predicted_date, feedback.predicted_failure_date,
            feedback.confidence_score, feedback.feedback_date,
            1 if feedback.was_correct else 0, feedback.actual_outcome,
            feedback.actual_failure_date, feedback.confirmation_source,
            feedback.service_record_id, feedback.user_notes,
            feedback.sequence_start_date, feedback.sequence_end_date,
            feedback.days_before_failure
        ))

        conn.commit()
        conn.close()

        # Remove from pending
        del self.pending_predictions[prediction_id]
        self._save_pending()

        # Create labeled sequence for training
        self._create_labeled_sequence(feedback)

        logger.info(f"Recorded feedback {feedback_id}: correct={was_correct}")

        # Check if we should trigger training
        self._check_training_trigger()

        return {
            'success': True,
            'feedback_id': feedback_id,
            'was_correct': was_correct,
            'days_warning': days_before_failure
        }

    def _auto_link_prediction(
        self,
        vehicle_id: str,
        component: str,
        failure_type: str,
        failure_date: str,
        service_record_id: str
    ):
        """Automatically link a service record to matching pending predictions."""
        component_lower = component.lower()
        failure_lower = failure_type.lower()

        for pred_id, pred in list(self.pending_predictions.items()):
            if pred['vehicle_id'] != vehicle_id:
                continue

            pred_component = pred['predicted_component'].lower()

            # Check for match
            if pred_component in component_lower or component_lower in pred_component:
                # Auto-confirm this prediction
                self.confirm_prediction(
                    prediction_id=pred_id,
                    was_correct=True,
                    actual_outcome='failed',
                    confirmation_source=ConfirmationSource.SERVICE_RECORD.value,
                    actual_failure_date=failure_date,
                    service_record_id=service_record_id,
                    user_notes=f"Auto-linked from service record: {failure_type}"
                )
                logger.info(f"Auto-linked prediction {pred_id} to service record {service_record_id}")

    def check_dtc_confirmations(self, vehicle_id: str, dtc_codes: List[str]):
        """
        Check if any DTCs confirm pending predictions.
        Call this when new DTCs are detected.
        """
        # DTC to component mapping
        dtc_component_map = {
            'P0562': 'battery', 'P0563': 'battery',
            'P0620': 'alternator', 'P0621': 'alternator', 'P0622': 'alternator',
            'P0230': 'fuel_pump', 'P0231': 'fuel_pump', 'P0232': 'fuel_pump',
            'P0300': 'spark_plug', 'P0301': 'ignition_coil', 'P0302': 'ignition_coil',
            'P0130': 'oxygen_sensor', 'P0131': 'oxygen_sensor', 'P0132': 'oxygen_sensor',
            'P0420': 'catalytic_converter', 'P0430': 'catalytic_converter',
            'P0100': 'maf_sensor', 'P0101': 'maf_sensor', 'P0102': 'maf_sensor',
            'P0115': 'coolant_temp_sensor', 'P0116': 'coolant_temp_sensor',
            'P0125': 'thermostat', 'P0128': 'thermostat',
        }

        confirmed = []
        for dtc in dtc_codes:
            dtc_upper = dtc.upper()
            component = dtc_component_map.get(dtc_upper)

            if not component:
                continue

            # Check pending predictions
            for pred_id, pred in list(self.pending_predictions.items()):
                if pred['vehicle_id'] != vehicle_id:
                    continue

                if component in pred['predicted_component'].lower():
                    result = self.confirm_prediction(
                        prediction_id=pred_id,
                        was_correct=True,
                        actual_outcome='failed',
                        confirmation_source=ConfirmationSource.DTC_CONFIRMED.value,
                        actual_failure_date=datetime.now().isoformat(),
                        user_notes=f"Confirmed by DTC: {dtc}"
                    )
                    confirmed.append({
                        'prediction_id': pred_id,
                        'dtc': dtc,
                        'component': component
                    })

        return confirmed

    def expire_old_predictions(self, days_past_due: int = 30):
        """
        Mark old predictions as negative samples (no failure occurred).
        Run this periodically to clean up pending predictions.
        """
        expired = []
        now = datetime.now()

        for pred_id, pred in list(self.pending_predictions.items()):
            try:
                predicted_date = datetime.fromisoformat(pred['predicted_failure_date'])
                if (now - predicted_date).days > days_past_due:
                    # No failure occurred - negative sample
                    self.confirm_prediction(
                        prediction_id=pred_id,
                        was_correct=False,
                        actual_outcome='no_failure',
                        confirmation_source=ConfirmationSource.PREDICTION_EXPIRED.value,
                        user_notes=f"Expired {days_past_due} days past predicted failure date"
                    )
                    expired.append(pred_id)
            except:
                continue

        logger.info(f"Expired {len(expired)} old predictions as negative samples")
        return expired

    # =========================================================================
    # Labeled Sequence Generation
    # =========================================================================

    def _create_labeled_sequence(self, feedback: PredictionFeedback):
        """Create a labeled sequence record for LSTM training."""
        try:
            start = datetime.fromisoformat(feedback.sequence_start_date)
            end = datetime.fromisoformat(feedback.sequence_end_date)
            sequence_days = (end - start).days
        except:
            sequence_days = 0

        sequence = LabeledSequence(
            sequence_id=f"SEQ_{feedback.feedback_id}",
            vehicle_id=feedback.vehicle_id,
            failure_type=feedback.predicted_component,
            failure_occurred=feedback.was_correct and feedback.actual_outcome == 'failed',
            failure_date=feedback.actual_failure_date,
            sequence_start=feedback.sequence_start_date,
            sequence_end=feedback.sequence_end_date,
            sequence_length_days=sequence_days,
            data_points=0,  # Will be calculated during export
            feature_columns=[],  # Will be filled during export
            label=1 if (feedback.was_correct and feedback.actual_outcome == 'failed') else 0,
            days_to_failure=feedback.days_before_failure
        )

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO labeled_sequences
            (sequence_id, vehicle_id, failure_type, failure_occurred, failure_date,
             sequence_start, sequence_end, sequence_length_days, data_points,
             feature_columns, label, days_to_failure)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sequence.sequence_id, sequence.vehicle_id, sequence.failure_type,
            1 if sequence.failure_occurred else 0, sequence.failure_date,
            sequence.sequence_start, sequence.sequence_end, sequence.sequence_length_days,
            sequence.data_points, json.dumps(sequence.feature_columns),
            sequence.label, sequence.days_to_failure
        ))

        conn.commit()
        conn.close()

    def get_labeled_sequences(
        self,
        failure_type: Optional[str] = None,
        min_length_days: int = 7,
        unexported_only: bool = False
    ) -> List[Dict]:
        """Get labeled sequences for training export."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM labeled_sequences WHERE sequence_length_days >= ?"
        params = [min_length_days]

        if failure_type:
            query += " AND failure_type = ?"
            params.append(failure_type)

        if unexported_only:
            query += " AND exported = 0"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        sequences = []

        for row in cursor.fetchall():
            seq = dict(zip(columns, row))
            seq['feature_columns'] = json.loads(seq['feature_columns'] or '[]')
            sequences.append(seq)

        conn.close()
        return sequences

    def mark_sequences_exported(self, sequence_ids: List[str]):
        """Mark sequences as exported for training."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        for seq_id in sequence_ids:
            cursor.execute(
                "UPDATE labeled_sequences SET exported = 1 WHERE sequence_id = ?",
                (seq_id,)
            )

        conn.commit()
        conn.close()

    # =========================================================================
    # Statistics & Reporting
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback collection statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Count service records
        cursor.execute("SELECT COUNT(*) FROM service_records")
        total_services = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM service_records WHERE failure_type IS NOT NULL")
        failure_records = cursor.fetchone()[0]

        # Count feedback
        cursor.execute("SELECT COUNT(*) FROM prediction_feedback")
        total_feedback = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM prediction_feedback WHERE was_correct = 1")
        correct_predictions = cursor.fetchone()[0]

        # Count labeled sequences
        cursor.execute("SELECT COUNT(*) FROM labeled_sequences")
        total_sequences = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM labeled_sequences WHERE label = 1")
        positive_sequences = cursor.fetchone()[0]

        # Accuracy by component
        cursor.execute("""
            SELECT predicted_component,
                   COUNT(*) as total,
                   SUM(was_correct) as correct
            FROM prediction_feedback
            GROUP BY predicted_component
        """)
        component_accuracy = {}
        for row in cursor.fetchall():
            component, total, correct = row
            component_accuracy[component] = {
                'total': total,
                'correct': correct or 0,
                'accuracy': (correct or 0) / total if total > 0 else 0
            }

        conn.close()

        return {
            'service_records': {
                'total': total_services,
                'failures': failure_records
            },
            'predictions': {
                'total_feedback': total_feedback,
                'correct': correct_predictions,
                'accuracy': correct_predictions / total_feedback if total_feedback > 0 else 0,
                'pending': len(self.pending_predictions)
            },
            'training_data': {
                'total_sequences': total_sequences,
                'positive_samples': positive_sequences,
                'negative_samples': total_sequences - positive_sequences,
                'balance_ratio': positive_sequences / total_sequences if total_sequences > 0 else 0
            },
            'component_accuracy': component_accuracy,
            'lstm_ready': total_sequences >= 100  # Minimum for basic training
        }

    def get_pending_predictions(self, vehicle_id: Optional[str] = None) -> List[Dict]:
        """Get predictions awaiting feedback."""
        if vehicle_id:
            return [p for p in self.pending_predictions.values()
                    if p['vehicle_id'] == vehicle_id]
        return list(self.pending_predictions.values())

    def _count_unprocessed_confirmations(self) -> int:
        """Count confirmations that haven't been processed for training."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Count confirmations that haven't been marked as processed
            cursor.execute("""
                SELECT COUNT(*) FROM prediction_feedback
                WHERE feedback_id NOT IN (
                    SELECT feedback_id FROM labeled_sequences
                    WHERE exported = 0
                )
            """)
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Error counting unprocessed confirmations: {e}")
            return 0

    def _mark_confirmations_processed(self, sequence_ids: List[str]):
        """Mark confirmations as processed for training."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            for seq_id in sequence_ids:
                cursor.execute(
                    "UPDATE labeled_sequences SET exported = 1 WHERE sequence_id = ?",
                    (seq_id,)
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Marked {len(sequence_ids)} confirmations as processed")
        except Exception as e:
            logger.error(f"Error marking confirmations as processed: {e}")

    def _check_training_trigger(self):
        """Check if we have enough new confirmations to trigger training."""
        try:
            # Count unprocessed confirmations
            unprocessed = self._count_unprocessed_confirmations()

            # Trigger training if we have 5+ new confirmations
            if unprocessed >= 5:
                logger.info(f"Triggering LSTM training with {unprocessed} new confirmations")
                
                try:
                    from ai_auto_retraining import AutoRetrainingScheduler
                    scheduler = AutoRetrainingScheduler()
                    scheduler._train_lstm_models()
                    
                    # Mark confirmations as processed
                    sequences = self.get_labeled_sequences(unexported_only=True)
                    sequence_ids = [seq['sequence_id'] for seq in sequences]
                    self._mark_confirmations_processed(sequence_ids)
                    
                    logger.info(f"LSTM training triggered successfully")
                except ImportError:
                    logger.warning("AutoRetrainingScheduler not available - cannot trigger training")
                except Exception as e:
                    logger.error(f"Error triggering LSTM training: {e}")

        except Exception as e:
            logger.error(f"Error checking training trigger: {e}")

    def get_confirmed_predictions(self, days: int = 365) -> List[Dict]:
        """
        Get all confirmed predictions for training data generation.

        Args:
            days: Number of days to look back (default 365)

        Returns:
            List of confirmed prediction dictionaries with:
            - profile_name: Vehicle profile name
            - profile_id: Vehicle profile ID
            - confirmed_date: When the prediction was confirmed
            - failure_type: Type of failure that occurred
            - was_correct: Whether prediction was accurate
            - confidence_score: Original prediction confidence
            - days_warning: How many days before failure it was predicted
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute("""
                SELECT
                    vehicle_id as profile_name,
                    vehicle_id as profile_id,
                    feedback_date as confirmed_date,
                    predicted_component as failure_type,
                    was_correct,
                    confidence_score,
                    days_before_failure as days_warning,
                    actual_outcome,
                    actual_failure_date
                FROM prediction_feedback
                WHERE feedback_date >= ?
                ORDER BY feedback_date DESC
            """, (cutoff_date,))

            rows = cursor.fetchall()
            conn.close()

            confirmed = []
            for row in rows:
                confirmed.append({
                    'profile_name': row['profile_name'],
                    'profile_id': row['profile_id'],
                    'confirmed_date': row['confirmed_date'],
                    'failure_type': row['failure_type'],
                    'was_correct': bool(row['was_correct']),
                    'confidence_score': row['confidence_score'],
                    'days_warning': row['days_warning'],
                    'actual_outcome': row['actual_outcome'],
                    'actual_failure_date': row['actual_failure_date']
                })

            logger.debug(f"Retrieved {len(confirmed)} confirmed predictions from last {days} days")
            return confirmed

        except Exception as e:
            logger.error(f"Error getting confirmed predictions: {e}")
            return []

    def get_service_records_for_training(self, days: int = 365) -> List[Dict]:
        """
        Get service records that indicate failures for training.

        Args:
            days: Number of days to look back

        Returns:
            List of service records with failure information
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute("""
                SELECT
                    vehicle_id as profile_name,
                    vehicle_id as profile_id,
                    service_date as confirmed_date,
                    failure_type,
                    component,
                    description,
                    mileage
                FROM service_records
                WHERE service_date >= ? AND failure_type IS NOT NULL
                ORDER BY service_date DESC
            """, (cutoff_date,))

            rows = cursor.fetchall()
            conn.close()

            records = []
            for row in rows:
                records.append({
                    'profile_name': row['profile_name'],
                    'profile_id': row['profile_id'],
                    'confirmed_date': row['confirmed_date'],
                    'failure_type': row['failure_type'] or row['component'],
                    'was_correct': True,  # Service records are ground truth
                    'component': row['component'],
                    'description': row['description'],
                    'mileage': row['mileage']
                })

            logger.debug(f"Retrieved {len(records)} service records with failures from last {days} days")
            return records

        except Exception as e:
            logger.error(f"Error getting service records for training: {e}")
            return []


# Singleton instance
_feedback_collector = None

def get_feedback_collector() -> FeedbackCollector:
    """Get the singleton FeedbackCollector instance."""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector
