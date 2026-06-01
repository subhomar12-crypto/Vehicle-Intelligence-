"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Ai Alert Notifications

AI Alert Notification System
Monitors AI predictions and sends push notifications for potential issues
- Engine health warnings
- Transmission alerts
- Critical sensor failures
- Predictive maintenance alerts
- Real-time anomaly detection
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque
import json
import os
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class AIAlertNotificationSystem:
    """
    Monitors AI predictions and generates push notifications for critical issues

    Alert Types:
    - Critical: Immediate attention required (engine failure risk)
    - Warning: Issue detected, service recommended soon
    - Info: Potential issue, monitor situation
    - Maintenance: Predictive maintenance alert

    Alert Categories:
    - Engine Health
    - Transmission
    - Cooling System
    - Electrical System
    - Emissions
    - Sensors
    """

    def __init__(self, communication_hub, enhanced_ai=None, predictive_engine=None):
        """
        Initialize AI alert notification system

        Args:
            communication_hub: TwoWayCommunicationHub instance
            enhanced_ai: EnhancedAILearning instance (optional)
            predictive_engine: PredictiveFailureEngine instance (optional)
        """
        self.communication_hub = communication_hub
        self.enhanced_ai = enhanced_ai
        self.predictive_engine = predictive_engine

        # Alert thresholds
        self.HEALTH_SCORE_CRITICAL = 30  # Below 30% = critical
        self.HEALTH_SCORE_WARNING = 50   # Below 50% = warning
        self.CONFIDENCE_THRESHOLD = 0.7   # Minimum confidence for alerts

        # Failure probability thresholds
        self.FAILURE_CRITICAL = 0.7  # >70% failure risk = critical
        self.FAILURE_WARNING = 0.4   # >40% failure risk = warning

        # Alert cooldown (prevent spam)
        self.alert_cooldown = {}  # alert_key -> last_sent_time
        self.cooldown_minutes = {
            'critical': 5,    # Critical: every 5 min
            'warning': 30,    # Warning: every 30 min
            'info': 120,      # Info: every 2 hours
            'maintenance': 1440  # Maintenance: once per day
        }

        # Alert history per profile
        self.alert_history = {}  # profile_id -> deque of alerts

        # Storage for alert tracking
        self.storage_path = str(CONFIG.DATA_DIR / "ai_alerts")
        os.makedirs(self.storage_path, exist_ok=True)

        logger.info("AI Alert Notification System initialized")

    def process_ai_prediction(self, profile_id: int, profile_name: str,
                              prediction: Dict[str, Any],
                              current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process AI prediction and generate alerts if needed

        Args:
            profile_id: Vehicle profile ID
            profile_name: Profile name
            prediction: AI prediction result
            current_data: Current OBD data

        Returns:
            List of generated alerts
        """
        try:
            alerts = []

            # Extract health score
            health_score = prediction.get('health_score', 100)
            confidence = prediction.get('confidence', 0)

            # Check if confidence is high enough
            if confidence < self.CONFIDENCE_THRESHOLD:
                return alerts

            # 1. Check overall health score
            health_alert = self._check_health_score(
                profile_id, profile_name, health_score, confidence, current_data
            )
            if health_alert:
                alerts.append(health_alert)

            # 2. Check component-specific predictions
            components = prediction.get('component_health', {})
            for component, component_data in components.items():
                component_alert = self._check_component_health(
                    profile_id, profile_name, component, component_data, current_data
                )
                if component_alert:
                    alerts.append(component_alert)

            # 3. Check failure predictions
            if self.predictive_engine:
                failure_predictions = prediction.get('failure_predictions', [])
                for failure_pred in failure_predictions:
                    failure_alert = self._check_failure_prediction(
                        profile_id, profile_name, failure_pred, current_data
                    )
                    if failure_alert:
                        alerts.append(failure_alert)

            # 4. Check anomalies
            anomalies = prediction.get('anomalies', [])
            for anomaly in anomalies:
                anomaly_alert = self._check_anomaly(
                    profile_id, profile_name, anomaly, current_data
                )
                if anomaly_alert:
                    alerts.append(anomaly_alert)

            # Send alerts
            for alert in alerts:
                self._send_alert(profile_id, alert)

            return alerts

        except Exception as e:
            logger.error(f"Error processing AI prediction for alerts: {e}")
            return []

    def _check_health_score(self, profile_id: int, profile_name: str,
                           health_score: float, confidence: float,
                           current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check overall health score and generate alert if needed"""
        try:
            alert_key = f"{profile_id}_overall_health"

            # Determine severity
            if health_score < self.HEALTH_SCORE_CRITICAL:
                severity = 'critical'
                title = "⚠️ CRITICAL: Vehicle Health Alert"
                message = f"{profile_name} health is critically low ({health_score:.0f}%). Immediate inspection recommended!"
                category = 'engine_health'
            elif health_score < self.HEALTH_SCORE_WARNING:
                severity = 'warning'
                title = "⚠️ WARNING: Low Vehicle Health"
                message = f"{profile_name} health score is {health_score:.0f}%. Service recommended soon."
                category = 'engine_health'
            else:
                return None  # No alert needed

            # Check cooldown
            if not self._check_cooldown(alert_key, severity):
                return None

            # Create alert
            alert = {
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{profile_id}",
                'alert_type': 'health_score',
                'severity': severity,
                'category': category,
                'title': title,
                'message': message,
                'health_score': health_score,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'profile_id': profile_id,
                'profile_name': profile_name,
                'current_data': {
                    'rpm': current_data.get('rpm'),
                    'speed': current_data.get('speed'),
                    'engine_temp': current_data.get('coolant_temp')
                },
                'recommended_actions': [
                    'Schedule diagnostic scan',
                    'Check engine codes',
                    'Inspect engine components'
                ]
            }

            return alert

        except Exception as e:
            logger.error(f"Error checking health score: {e}")
            return None

    def _check_component_health(self, profile_id: int, profile_name: str,
                               component: str, component_data: Dict[str, Any],
                               current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check component-specific health"""
        try:
            component_score = component_data.get('health', 100)
            confidence = component_data.get('confidence', 0)

            alert_key = f"{profile_id}_component_{component}"

            # Determine severity
            if component_score < 30:
                severity = 'critical'
                title = f"🔴 CRITICAL: {component.replace('_', ' ').title()} Issue"
                message = f"{component.replace('_', ' ').title()} health critically low ({component_score:.0f}%)!"
            elif component_score < 60:
                severity = 'warning'
                title = f"⚠️ {component.replace('_', ' ').title()} Warning"
                message = f"{component.replace('_', ' ').title()} showing degradation ({component_score:.0f}%)"
            else:
                return None

            # Check cooldown
            if not self._check_cooldown(alert_key, severity):
                return None

            # Map component to category
            category_map = {
                'engine': 'engine_health',
                'transmission': 'transmission',
                'cooling_system': 'cooling_system',
                'electrical': 'electrical_system',
                'emissions': 'emissions',
                'fuel_system': 'engine_health'
            }
            category = category_map.get(component, 'general')

            # Create alert
            alert = {
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{profile_id}",
                'alert_type': 'component_health',
                'severity': severity,
                'category': category,
                'title': title,
                'message': message,
                'component': component,
                'component_score': component_score,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'profile_id': profile_id,
                'profile_name': profile_name,
                'recommended_actions': self._get_component_recommendations(component)
            }

            return alert

        except Exception as e:
            logger.error(f"Error checking component health: {e}")
            return None

    def _check_failure_prediction(self, profile_id: int, profile_name: str,
                                 failure_pred: Dict[str, Any],
                                 current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check failure prediction and generate alert"""
        try:
            component = failure_pred.get('component', 'Unknown')
            probability = failure_pred.get('probability', 0)
            time_to_failure = failure_pred.get('estimated_days', None)

            alert_key = f"{profile_id}_failure_{component}"

            # Determine severity
            if probability > self.FAILURE_CRITICAL:
                severity = 'critical'
                title = f"🔴 CRITICAL: {component} Failure Risk"
                message = f"High probability ({probability*100:.0f}%) of {component} failure!"
                if time_to_failure:
                    message += f" Estimated time: {time_to_failure:.0f} days"
            elif probability > self.FAILURE_WARNING:
                severity = 'warning'
                title = f"⚠️ WARNING: {component} Failure Risk"
                message = f"Moderate probability ({probability*100:.0f}%) of {component} failure"
                if time_to_failure:
                    message += f" within {time_to_failure:.0f} days"
            else:
                return None

            # Check cooldown
            if not self._check_cooldown(alert_key, severity):
                return None

            # Create alert
            alert = {
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{profile_id}",
                'alert_type': 'failure_prediction',
                'severity': severity,
                'category': 'predictive_maintenance',
                'title': title,
                'message': message,
                'component': component,
                'failure_probability': probability,
                'estimated_days': time_to_failure,
                'timestamp': datetime.now().isoformat(),
                'profile_id': profile_id,
                'profile_name': profile_name,
                'recommended_actions': [
                    f'Inspect {component} immediately',
                    'Schedule preventive maintenance',
                    'Monitor {component} closely'
                ]
            }

            return alert

        except Exception as e:
            logger.error(f"Error checking failure prediction: {e}")
            return None

    def _check_anomaly(self, profile_id: int, profile_name: str,
                      anomaly: Dict[str, Any],
                      current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check anomaly and generate alert"""
        try:
            parameter = anomaly.get('parameter', 'Unknown')
            severity_level = anomaly.get('severity', 'info')
            deviation = anomaly.get('deviation', 0)

            alert_key = f"{profile_id}_anomaly_{parameter}"

            # Map severity
            if severity_level in ['severe', 'critical']:
                severity = 'warning'
                title = f"⚠️ Anomaly Detected: {parameter}"
                message = f"Unusual reading for {parameter} (deviation: {deviation:.1f})"
            else:
                severity = 'info'
                title = f"ℹ️ Anomaly: {parameter}"
                message = f"Unusual pattern detected for {parameter}"

            # Check cooldown
            if not self._check_cooldown(alert_key, severity):
                return None

            # Create alert
            alert = {
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{profile_id}",
                'alert_type': 'anomaly',
                'severity': severity,
                'category': 'sensors',
                'title': title,
                'message': message,
                'parameter': parameter,
                'deviation': deviation,
                'timestamp': datetime.now().isoformat(),
                'profile_id': profile_id,
                'profile_name': profile_name,
                'recommended_actions': [
                    f'Check {parameter} sensor',
                    'Monitor for recurring anomalies',
                    'Run diagnostic scan'
                ]
            }

            return alert

        except Exception as e:
            logger.error(f"Error checking anomaly: {e}")
            return None

    def _check_cooldown(self, alert_key: str, severity: str) -> bool:
        """Check if alert can be sent (not in cooldown)"""
        try:
            now = datetime.now()
            cooldown_min = self.cooldown_minutes.get(severity, 60)

            if alert_key in self.alert_cooldown:
                last_sent = self.alert_cooldown[alert_key]
                time_diff = (now - last_sent).total_seconds() / 60  # minutes

                if time_diff < cooldown_min:
                    return False  # Still in cooldown

            # Update cooldown
            self.alert_cooldown[alert_key] = now
            return True

        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return True  # Allow send on error

    def _send_alert(self, profile_id: int, alert: Dict[str, Any]):
        """Send alert via push notification"""
        try:
            # Add to history
            if profile_id not in self.alert_history:
                self.alert_history[profile_id] = deque(maxlen=100)
            self.alert_history[profile_id].append(alert)

            # Save to file
            self._save_alert(profile_id, alert)

            # Send via communication hub
            notification = {
                'type': 'ai_alert',
                'alert_id': alert['alert_id'],
                'severity': alert['severity'],
                'category': alert['category'],
                'title': alert['title'],
                'message': alert['message'],
                'timestamp': alert['timestamp'],
                'actions': [
                    {'id': 'view_details', 'label': 'View Details'},
                    {'id': 'diagnostic_scan', 'label': 'Run Diagnostic'},
                    {'id': 'dismiss', 'label': 'Dismiss'}
                ],
                'data': alert
            }

            result = self.communication_hub.send_notification_to_mobile(
                profile_id,
                notification
            )

            if result.get('success'):
                logger.info(f"Alert sent: {alert['title']} (ID: {alert['alert_id']})")
            else:
                logger.warning(f"Failed to send alert: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    def _save_alert(self, profile_id: int, alert: Dict[str, Any]):
        """Save alert to file"""
        try:
            alert_file = os.path.join(self.storage_path, f'profile_{profile_id}_alerts.jsonl')

            with open(alert_file, 'a', encoding='utf-8') as f:
                json.dump(alert, f, ensure_ascii=False)
                f.write('\n')

        except Exception as e:
            logger.error(f"Error saving alert: {e}")

    def _get_component_recommendations(self, component: str) -> List[str]:
        """Get recommended actions for component"""
        recommendations = {
            'engine': [
                'Check engine oil level and quality',
                'Inspect air filter',
                'Run engine diagnostic',
                'Check for error codes'
            ],
            'transmission': [
                'Check transmission fluid level',
                'Inspect for leaks',
                'Test transmission responsiveness',
                'Schedule transmission service'
            ],
            'cooling_system': [
                'Check coolant level',
                'Inspect radiator and hoses',
                'Test thermostat',
                'Check for leaks'
            ],
            'electrical': [
                'Test battery voltage',
                'Check alternator output',
                'Inspect wiring connections',
                'Test electrical load'
            ],
            'emissions': [
                'Check O2 sensors',
                'Inspect catalytic converter',
                'Test evaporative system',
                'Check for exhaust leaks'
            ]
        }

        return recommendations.get(component, [
            'Run full diagnostic scan',
            'Inspect component',
            'Schedule service appointment'
        ])

    def get_alert_history(self, profile_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alert history for profile"""
        try:
            if profile_id not in self.alert_history:
                return []

            history = list(self.alert_history[profile_id])
            history.reverse()  # Most recent first

            return history[:limit]

        except Exception as e:
            logger.error(f"Error getting alert history: {e}")
            return []

    def get_active_alerts(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get currently active (not dismissed) alerts"""
        try:
            if profile_id not in self.alert_history:
                return []

            # Get alerts from last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            active = []

            for alert in self.alert_history[profile_id]:
                alert_time = datetime.fromisoformat(alert['timestamp'])
                if alert_time >= cutoff:
                    active.append(alert)

            return active

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    def dismiss_alert(self, alert_id: str):
        """Dismiss an alert"""
        try:
            # Find and mark alert as dismissed
            for alerts in self.alert_history.values():
                for alert in alerts:
                    if alert['alert_id'] == alert_id:
                        alert['dismissed'] = True
                        alert['dismissed_at'] = datetime.now().isoformat()
                        logger.info(f"Alert dismissed: {alert_id}")
                        return True

            return False

        except Exception as e:
            logger.error(f"Error dismissing alert: {e}")
            return False
