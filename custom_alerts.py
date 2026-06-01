"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Custom Alerts

Custom Alerts System
User-defined alert rules with customizable thresholds
- Temperature alerts (Celsius)
- RPM alerts
- Speed alerts
- Fuel level alerts
- Custom parameter alerts
- Per-profile configuration
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque

from config import get_config
CONFIG = get_config()

logger = logging.getLogger(__name__)


class CustomAlertsSystem:
    """
    User-configurable alert system with custom thresholds

    Alert Parameters:
    - Coolant Temperature (°C)
    - Oil Temperature (°C)
    - Engine RPM
    - Vehicle Speed (km/h)
    - Fuel Level (%)
    - Throttle Position (%)
    - Engine Load (%)
    - Battery Voltage (V)
    - Any custom OBD parameter

    Alert Conditions:
    - Greater than (>)
    - Less than (<)
    - Equals (=)
    - Between range
    - Outside range
    """

    def __init__(self, communication_hub=None):
        """
        Initialize custom alerts system

        Args:
            communication_hub: TwoWayCommunicationHub instance (optional)
        """
        self.communication_hub = communication_hub

        # Alert rules per profile
        self.alert_rules = {}  # profile_id -> list of rules

        # Alert history per profile
        self.alert_history = {}  # profile_id -> deque of alerts

        # Alert state tracking (for debouncing)
        self.alert_states = {}  # rule_id -> {triggered, last_trigger_time, count}

        # Alert cooldown (prevent spam)
        self.cooldown_seconds = {
            'info': 300,      # 5 minutes
            'warning': 120,   # 2 minutes
            'critical': 60    # 1 minute
        }

        # Storage
        self.storage_path = str(CONFIG.DATA_DIR / "custom_alerts")
        os.makedirs(self.storage_path, exist_ok=True)

        # Load alert rules
        self._load_all_rules()

        # Default alert templates
        self.alert_templates = self._get_default_templates()

        logger.info("Custom Alerts System initialized")

    def _get_default_templates(self) -> Dict[str, Dict]:
        """Get default alert templates (user can customize)"""
        return {
            'high_coolant_temp': {
                'name': 'High Coolant Temperature',
                'description': 'Alert when coolant temperature exceeds threshold',
                'parameter': 'coolant_temp',
                'condition': 'greater_than',
                'threshold': 105,  # °C
                'severity': 'critical',
                'enabled': True,
                'message_template': 'Coolant temperature is {value}°C (threshold: {threshold}°C)!'
            },
            'very_high_coolant_temp': {
                'name': 'EXTREME Coolant Temperature',
                'description': 'Critical overheating alert',
                'parameter': 'coolant_temp',
                'condition': 'greater_than',
                'threshold': 115,  # °C
                'severity': 'critical',
                'enabled': True,
                'message_template': '⚠️ CRITICAL: Coolant at {value}°C! Stop engine immediately!'
            },
            'low_fuel': {
                'name': 'Low Fuel Warning',
                'description': 'Alert when fuel level is low',
                'parameter': 'fuel_level_pct',
                'condition': 'less_than',
                'threshold': 15,  # %
                'severity': 'warning',
                'enabled': True,
                'message_template': 'Fuel level low: {value}% remaining'
            },
            'critical_fuel': {
                'name': 'Critical Fuel Level',
                'description': 'Critical low fuel alert',
                'parameter': 'fuel_level_pct',
                'condition': 'less_than',
                'threshold': 5,  # %
                'severity': 'critical',
                'enabled': True,
                'message_template': '⛽ CRITICAL: Only {value}% fuel remaining!'
            },
            'high_rpm': {
                'name': 'High RPM Warning',
                'description': 'Alert when RPM is excessive',
                'parameter': 'rpm',
                'condition': 'greater_than',
                'threshold': 6000,
                'severity': 'warning',
                'enabled': True,
                'message_template': 'High RPM: {value} (threshold: {threshold})'
            },
            'overspeed': {
                'name': 'Speed Limit Alert',
                'description': 'Alert when speed exceeds limit',
                'parameter': 'speed_kmh',
                'condition': 'greater_than',
                'threshold': 140,  # km/h
                'severity': 'warning',
                'enabled': True,
                'message_template': 'Speed: {value} km/h (limit: {threshold} km/h)'
            },
            'low_battery': {
                'name': 'Low Battery Voltage',
                'description': 'Battery voltage too low',
                'parameter': 'battery_voltage',
                'condition': 'less_than',
                'threshold': 12.0,  # V
                'severity': 'warning',
                'enabled': True,
                'message_template': 'Battery voltage low: {value}V'
            },
            'high_engine_load': {
                'name': 'High Engine Load',
                'description': 'Sustained high engine load',
                'parameter': 'engine_load',
                'condition': 'greater_than',
                'threshold': 85,  # %
                'severity': 'info',
                'enabled': True,
                'message_template': 'High engine load: {value}%'
            }
        }

    def create_alert_rule(self, profile_id: int, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom alert rule

        Args:
            profile_id: Profile ID
            rule_data: Rule configuration

        Returns:
            Result with rule_id
        """
        try:
            # Validate rule data
            required = ['name', 'parameter', 'condition', 'threshold', 'severity']
            if not all(field in rule_data for field in required):
                return {'success': False, 'error': 'Missing required fields'}

            # Generate rule ID
            rule_id = f"rule_{profile_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            rule = {
                'rule_id': rule_id,
                'profile_id': profile_id,
                'name': rule_data['name'],
                'description': rule_data.get('description', ''),
                'parameter': rule_data['parameter'],
                'condition': rule_data['condition'],
                'threshold': rule_data['threshold'],
                'threshold2': rule_data.get('threshold2'),  # For 'between' condition
                'severity': rule_data['severity'],
                'enabled': rule_data.get('enabled', True),
                'message_template': rule_data.get('message_template', '{parameter} is {value}'),
                'created_at': datetime.now().isoformat(),
                'trigger_count': 0
            }

            # Add to profile rules
            if profile_id not in self.alert_rules:
                self.alert_rules[profile_id] = []

            self.alert_rules[profile_id].append(rule)

            # Save
            self._save_rules(profile_id)

            logger.info(f"Alert rule created: {rule['name']} (ID: {rule_id})")

            return {
                'success': True,
                'rule_id': rule_id,
                'rule': rule
            }

        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            return {'success': False, 'error': str(e)}

    def process_data(self, profile_id: int, profile_name: str,
                    data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process OBD data and check for alert conditions

        Args:
            profile_id: Profile ID
            profile_name: Profile name
            data: Current OBD data

        Returns:
            List of triggered alerts
        """
        try:
            if profile_id not in self.alert_rules:
                return []

            triggered_alerts = []

            for rule in self.alert_rules[profile_id]:
                if not rule.get('enabled', True):
                    continue

                alert = self._check_rule(profile_id, profile_name, rule, data)
                if alert:
                    triggered_alerts.append(alert)

            return triggered_alerts

        except Exception as e:
            logger.error(f"Error processing alerts: {e}")
            return []

    def _check_rule(self, profile_id: int, profile_name: str,
                   rule: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if rule condition is met"""
        try:
            parameter = rule['parameter']
            condition = rule['condition']
            threshold = rule['threshold']
            threshold2 = rule.get('threshold2')

            # Get parameter value from data
            value = data.get(parameter)

            if value is None:
                return None

            # Check condition
            is_triggered = False

            if condition == 'greater_than':
                is_triggered = value > threshold
            elif condition == 'less_than':
                is_triggered = value < threshold
            elif condition == 'equals':
                is_triggered = value == threshold
            elif condition == 'between':
                if threshold2 is not None:
                    is_triggered = threshold <= value <= threshold2
            elif condition == 'outside':
                if threshold2 is not None:
                    is_triggered = value < threshold or value > threshold2

            if not is_triggered:
                # Reset state if not triggered
                rule_id = rule['rule_id']
                if rule_id in self.alert_states:
                    self.alert_states[rule_id]['triggered'] = False
                return None

            # Check cooldown
            if not self._check_cooldown(rule):
                return None

            # Create alert
            alert = self._create_alert(profile_id, profile_name, rule, value, data)

            # Update rule state
            rule['trigger_count'] = rule.get('trigger_count', 0) + 1
            self._save_rules(profile_id)

            # Send notification
            self._send_alert_notification(profile_id, alert)

            # Add to history
            if profile_id not in self.alert_history:
                self.alert_history[profile_id] = deque(maxlen=200)
            self.alert_history[profile_id].append(alert)

            return alert

        except Exception as e:
            logger.error(f"Error checking rule: {e}")
            return None

    def _check_cooldown(self, rule: Dict[str, Any]) -> bool:
        """Check if alert can be sent (not in cooldown)"""
        try:
            rule_id = rule['rule_id']
            severity = rule['severity']
            cooldown_sec = self.cooldown_seconds.get(severity, 120)

            if rule_id not in self.alert_states:
                self.alert_states[rule_id] = {
                    'triggered': False,
                    'last_trigger_time': None,
                    'count': 0
                }

            state = self.alert_states[rule_id]

            # First trigger
            if state['last_trigger_time'] is None:
                state['triggered'] = True
                state['last_trigger_time'] = datetime.now()
                state['count'] = 1
                return True

            # Check cooldown
            time_diff = (datetime.now() - state['last_trigger_time']).total_seconds()

            if time_diff >= cooldown_sec:
                state['last_trigger_time'] = datetime.now()
                state['count'] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return True

    def _create_alert(self, profile_id: int, profile_name: str,
                     rule: Dict[str, Any], value: Any,
                     data: Dict[str, Any]) -> Dict[str, Any]:
        """Create alert object"""
        try:
            # Format message
            message_template = rule.get('message_template', '{parameter} is {value}')

            message = message_template.format(
                parameter=rule['parameter'],
                value=value,
                threshold=rule['threshold'],
                threshold2=rule.get('threshold2', '')
            )

            alert = {
                'alert_id': f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{profile_id}",
                'rule_id': rule['rule_id'],
                'rule_name': rule['name'],
                'profile_id': profile_id,
                'profile_name': profile_name,
                'severity': rule['severity'],
                'parameter': rule['parameter'],
                'value': value,
                'threshold': rule['threshold'],
                'condition': rule['condition'],
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'current_data': {
                    'rpm': data.get('rpm'),
                    'speed': data.get('speed_kmh'),
                    'coolant_temp': data.get('coolant_temp'),
                    'fuel_level': data.get('fuel_level_pct')
                }
            }

            return alert

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return {}

    def _send_alert_notification(self, profile_id: int, alert: Dict[str, Any]):
        """Send alert via communication hub"""
        try:
            if not self.communication_hub:
                return

            severity_icons = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'critical': '🔴'
            }

            icon = severity_icons.get(alert['severity'], '⚠️')

            notification = {
                'type': 'custom_alert',
                'alert_id': alert['alert_id'],
                'severity': alert['severity'],
                'title': f"{icon} {alert['rule_name']}",
                'message': alert['message'],
                'timestamp': alert['timestamp'],
                'parameter': alert['parameter'],
                'value': alert['value'],
                'threshold': alert['threshold'],
                'actions': [
                    {'id': 'view_details', 'label': 'View Details'},
                    {'id': 'disable_rule', 'label': 'Disable Alert'},
                    {'id': 'dismiss', 'label': 'Dismiss'}
                ]
            }

            result = self.communication_hub.send_notification_to_mobile(
                profile_id,
                notification
            )

            if result.get('success'):
                logger.info(f"Custom alert sent: {alert['rule_name']}")

        except Exception as e:
            logger.error(f"Error sending alert notification: {e}")

    def get_alert_rules(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get all alert rules for profile"""
        return self.alert_rules.get(profile_id, [])

    def update_alert_rule(self, profile_id: int, rule_id: str,
                         updates: Dict[str, Any]) -> bool:
        """Update alert rule"""
        try:
            if profile_id not in self.alert_rules:
                return False

            for rule in self.alert_rules[profile_id]:
                if rule['rule_id'] == rule_id:
                    rule.update(updates)
                    rule['updated_at'] = datetime.now().isoformat()
                    self._save_rules(profile_id)
                    logger.info(f"Alert rule updated: {rule_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return False

    def delete_alert_rule(self, profile_id: int, rule_id: str) -> bool:
        """Delete alert rule"""
        try:
            if profile_id not in self.alert_rules:
                return False

            self.alert_rules[profile_id] = [
                rule for rule in self.alert_rules[profile_id]
                if rule['rule_id'] != rule_id
            ]

            self._save_rules(profile_id)
            logger.info(f"Alert rule deleted: {rule_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting alert rule: {e}")
            return False

    def enable_disable_rule(self, profile_id: int, rule_id: str, enabled: bool) -> bool:
        """Enable or disable alert rule"""
        return self.update_alert_rule(profile_id, rule_id, {'enabled': enabled})

    def load_template(self, profile_id: int, template_name: str) -> Dict[str, Any]:
        """Load alert template and create rule from it"""
        try:
            if template_name not in self.alert_templates:
                return {'success': False, 'error': 'Template not found'}

            template = self.alert_templates[template_name].copy()
            template['name'] = template_name

            result = self.create_alert_rule(profile_id, template)

            return result

        except Exception as e:
            logger.error(f"Error loading template: {e}")
            return {'success': False, 'error': str(e)}

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

    def get_alert_statistics(self, profile_id: int) -> Dict[str, Any]:
        """Get alert statistics"""
        try:
            rules = self.get_alert_rules(profile_id)
            history = self.alert_history.get(profile_id, [])

            # Count by severity
            critical_count = len([a for a in history if a.get('severity') == 'critical'])
            warning_count = len([a for a in history if a.get('severity') == 'warning'])
            info_count = len([a for a in history if a.get('severity') == 'info'])

            # Most triggered rule
            rule_counts = {}
            for alert in history:
                rule_id = alert.get('rule_id')
                rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

            most_triggered = max(rule_counts.items(), key=lambda x: x[1]) if rule_counts else None

            return {
                'total_rules': len(rules),
                'enabled_rules': len([r for r in rules if r.get('enabled')]),
                'total_alerts_triggered': len(history),
                'critical_alerts': critical_count,
                'warning_alerts': warning_count,
                'info_alerts': info_count,
                'most_triggered_rule_id': most_triggered[0] if most_triggered else None,
                'most_triggered_count': most_triggered[1] if most_triggered else 0
            }

        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {}

    def _save_rules(self, profile_id: int):
        """Save alert rules to storage"""
        try:
            rules_file = os.path.join(self.storage_path, f'profile_{profile_id}_rules.json')

            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(self.alert_rules[profile_id], f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error saving rules: {e}")

    def _load_all_rules(self):
        """Load all alert rules from storage"""
        try:
            for filename in os.listdir(self.storage_path):
                if filename.startswith('profile_') and filename.endswith('_rules.json'):
                    # Extract profile ID
                    profile_id = int(filename.split('_')[1])

                    rules_file = os.path.join(self.storage_path, filename)

                    with open(rules_file, 'r', encoding='utf-8') as f:
                        self.alert_rules[profile_id] = json.load(f)

            logger.info(f"Loaded alert rules for {len(self.alert_rules)} profiles")

        except Exception as e:
            logger.error(f"Error loading alert rules: {e}")
