"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Prediction Accuracy Tracker

Prediction Accuracy Tracker
Tracks prediction vs actual outcomes to measure AI performance
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import sqlite3

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a time period"""
    total_predictions: int = 0
    confirmed_correct: int = 0
    confirmed_incorrect: int = 0
    unconfirmed: int = 0
    accuracy_rate: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0


class PredictionAccuracyTracker:
    """
    Tracks and analyzes prediction accuracy over time.
    """

    def __init__(self):
        self.db_path = CONFIG.AI_DIR / "accuracy_tracking.db"
        self._init_database()

    def _init_database(self):
        """Initialize accuracy tracking database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                profile_id INTEGER,
                profile_name TEXT,
                prediction_type TEXT,
                predicted_failure TEXT,
                predicted_days INTEGER,
                confidence REAL,
                created_at TEXT,
                confirmed_at TEXT,
                actual_outcome TEXT,
                was_correct INTEGER,
                notes TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                total_predictions INTEGER,
                confirmed_correct INTEGER,
                confirmed_incorrect INTEGER,
                accuracy_rate REAL,
                avg_confidence REAL
            )
        ''')

        conn.commit()
        conn.close()

    def record_prediction(self, prediction_id: str, profile_id: int,
                      profile_name: str, prediction_type: str,
                      predicted_failure: str, predicted_days: int,
                      confidence: float):
        """Record a new prediction for tracking"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO predictions
                (prediction_id, profile_id, profile_name, prediction_type,
                 predicted_failure, predicted_days, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (prediction_id, profile_id, profile_name, prediction_type,
                  predicted_failure, predicted_days, confidence,
                  datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error recording prediction: {e}")

    def confirm_prediction(self, prediction_id: str, actual_outcome: str,
                       was_correct: bool, notes: str = None):
        """Confirm prediction with actual outcome"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                UPDATE predictions
                SET confirmed_at = ?, actual_outcome = ?, was_correct = ?, notes = ?
                WHERE prediction_id = ?
            ''', (datetime.now().isoformat(), actual_outcome,
                  1 if was_correct else 0, notes, prediction_id))

            conn.commit()
            conn.close()

            # Update daily metrics
            self._update_daily_metrics()

        except Exception as e:
            logger.error(f"Error confirming prediction: {e}")

    def get_accuracy_metrics(self, days: int = 30) -> AccuracyMetrics:
        """Get accuracy metrics for the last N days"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Total predictions
            c.execute('''
                SELECT COUNT(*) FROM predictions
                WHERE created_at >= ?
            ''', (start_date,))
            total = c.fetchone()[0]

            # Confirmed correct
            c.execute('''
                SELECT COUNT(*) FROM predictions
                WHERE created_at >= ? AND was_correct = 1
            ''', (start_date,))
            correct = c.fetchone()[0]

            # Confirmed incorrect
            c.execute('''
                SELECT COUNT(*) FROM predictions
                WHERE created_at >= ? AND was_correct = 0 AND confirmed_at IS NOT NULL
            ''', (start_date,))
            incorrect = c.fetchone()[0]

            conn.close()

            confirmed_total = correct + incorrect
            accuracy = (correct / confirmed_total * 100) if confirmed_total > 0 else 0

            return AccuracyMetrics(
                total_predictions=total,
                confirmed_correct=correct,
                confirmed_incorrect=incorrect,
                unconfirmed=total - confirmed_total,
                accuracy_rate=round(accuracy, 2),
                false_positive_rate=round((incorrect / confirmed_total * 100) if confirmed_total > 0 else 0, 2),
                false_negative_rate=0.0  # Not directly trackable
            )

        except Exception as e:
            logger.error(f"Error getting accuracy metrics: {e}")
            return AccuracyMetrics()

    def get_accuracy_trend(self, days: int = 30) -> List[Dict]:
        """Get daily accuracy trend"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            c.execute('''
                SELECT date, accuracy_rate, total_predictions
                FROM daily_metrics
                WHERE date >= ?
                ORDER BY date ASC
            ''', (start_date,))

            rows = c.fetchall()
            conn.close()

            return [
                {'date': row[0], 'accuracy': row[1], 'predictions': row[2]}
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error getting accuracy trend: {e}")
            return []

    def get_component_accuracy(self, days: int = 30) -> Dict[str, Dict]:
        """Get accuracy by component type"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            c.execute('''
                SELECT predicted_failure, COUNT(*) as total, SUM(was_correct) as correct
                FROM predictions
                WHERE created_at >= ? AND confirmed_at IS NOT NULL
                GROUP BY predicted_failure
            ''', (start_date,))

            rows = c.fetchall()
            conn.close()

            component_accuracy = {}
            for row in rows:
                component = row[0]
                total = row[1]
                correct = row[2] or 0
                component_accuracy[component] = {
                    'total': total,
                    'correct': correct,
                    'accuracy': (correct / total * 100) if total > 0 else 0
                }

            return component_accuracy

        except Exception as e:
            logger.error(f"Error getting component accuracy: {e}")
            return {}

    def get_confidence_accuracy_correlation(self, days: int = 30) -> Dict:
        """Analyze correlation between confidence and actual accuracy"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            c.execute('''
                SELECT confidence, was_correct
                FROM predictions
                WHERE created_at >= ? AND confirmed_at IS NOT NULL
            ''', (start_date,))

            rows = c.fetchall()
            conn.close()

            if not rows:
                return {}

            # Group by confidence ranges
            high_conf_correct = sum(1 for r in rows if r[0] >= 0.8 and r[1] == 1)
            high_conf_total = sum(1 for r in rows if r[0] >= 0.8)

            med_conf_correct = sum(1 for r in rows if 0.5 <= r[0] < 0.8 and r[1] == 1)
            med_conf_total = sum(1 for r in rows if 0.5 <= r[0] < 0.8)

            low_conf_correct = sum(1 for r in rows if r[0] < 0.5 and r[1] == 1)
            low_conf_total = sum(1 for r in rows if r[0] < 0.5)

            return {
                'high_confidence': {
                    'accuracy': (high_conf_correct / high_conf_total * 100) if high_conf_total > 0 else 0,
                    'count': high_conf_total
                },
                'medium_confidence': {
                    'accuracy': (med_conf_correct / med_conf_total * 100) if med_conf_total > 0 else 0,
                    'count': med_conf_total
                },
                'low_confidence': {
                    'accuracy': (low_conf_correct / low_conf_total * 100) if low_conf_total > 0 else 0,
                    'count': low_conf_total
                }
            }

        except Exception as e:
            logger.error(f"Error getting confidence correlation: {e}")
            return {}

    def _update_daily_metrics(self):
        """Update daily metrics summary"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            # Calculate today's metrics
            c.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(was_correct) as correct,
                    AVG(confidence) as avg_conf
                FROM predictions
                WHERE DATE(created_at) = ? AND confirmed_at IS NOT NULL
            ''', (today,))

            row = c.fetchone()
            if row:
                total = row[0] or 0
                correct = row[1] or 0
                avg_conf = row[2] or 0.0

                incorrect = total - correct
                accuracy = (correct / total * 100) if total > 0 else 0

                c.execute('''
                    INSERT OR REPLACE INTO daily_metrics
                    (date, total_predictions, confirmed_correct, confirmed_incorrect, accuracy_rate, avg_confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (today, total, correct, incorrect, accuracy, avg_conf))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating daily metrics: {e}")


# Singleton instance
_accuracy_tracker = None

def get_accuracy_tracker() -> PredictionAccuracyTracker:
    """Get the singleton PredictionAccuracyTracker instance."""
    global _accuracy_tracker
    if _accuracy_tracker is None:
        _accuracy_tracker = PredictionAccuracyTracker()
    return _accuracy_tracker
