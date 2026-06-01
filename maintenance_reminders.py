"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Maintenance Reminders

Maintenance Reminders System
- Track service schedules (mileage and time-based)
- Generate reminders when service is due
- Push notifications to mobile app
- Integration with service history
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import sqlite3

logger = logging.getLogger(__name__)


class MaintenanceRemindersSystem:
    """
    Intelligent maintenance reminder system

    Features:
    - Mileage-based reminders (e.g., every 5,000 km)
    - Time-based reminders (e.g., every 6 months)
    - Multiple service types (oil, tires, brakes, filters, etc.)
    - Early warnings (configurable lead time)
    - Overdue tracking
    - Service history integration
    - Push notification support
    """

    def __init__(self, vehicle_manager, db_path=None):
        """
        Initialize maintenance reminders system

        Args:
            vehicle_manager: VehicleProfileManager instance
            db_path: Path to database
        """
        from config import get_config
        CONFIG = get_config()
        
        self.vehicle_manager = vehicle_manager
        self.db_path = db_path if db_path else str(CONFIG.DATA_DIR / "vehicle_data.db")

        # Default service schedules (can be customized per vehicle)
        self.default_schedules = {
            'oil_change': {
                'name': 'Oil Change',
                'mileage_interval_km': 5000,
                'time_interval_days': 180,  # 6 months
                'priority': 'high',
                'description': 'Engine oil and filter replacement',
                'warning_threshold_km': 500,
                'warning_threshold_days': 14
            },
            'tire_rotation': {
                'name': 'Tire Rotation',
                'mileage_interval_km': 10000,
                'time_interval_days': 180,  # 6 months
                'priority': 'medium',
                'description': 'Rotate tires for even wear',
                'warning_threshold_km': 1000,
                'warning_threshold_days': 30
            },
            'brake_inspection': {
                'name': 'Brake Inspection',
                'mileage_interval_km': 15000,
                'time_interval_days': 365,  # 1 year
                'priority': 'high',
                'description': 'Check brake pads, rotors, and fluid',
                'warning_threshold_km': 1000,
                'warning_threshold_days': 30
            },
            'air_filter': {
                'name': 'Air Filter Replacement',
                'mileage_interval_km': 20000,
                'time_interval_days': 365,  # 1 year
                'priority': 'low',
                'description': 'Replace engine air filter',
                'warning_threshold_km': 2000,
                'warning_threshold_days': 30
            },
            'cabin_filter': {
                'name': 'Cabin Air Filter',
                'mileage_interval_km': 15000,
                'time_interval_days': 365,
                'priority': 'low',
                'description': 'Replace cabin air filter',
                'warning_threshold_km': 2000,
                'warning_threshold_days': 30
            },
            'coolant_flush': {
                'name': 'Coolant Flush',
                'mileage_interval_km': 50000,
                'time_interval_days': 730,  # 2 years
                'priority': 'medium',
                'description': 'Flush and replace coolant',
                'warning_threshold_km': 5000,
                'warning_threshold_days': 60
            },
            'transmission_fluid': {
                'name': 'Transmission Fluid',
                'mileage_interval_km': 60000,
                'time_interval_days': 730,  # 2 years
                'priority': 'medium',
                'description': 'Check/replace transmission fluid',
                'warning_threshold_km': 5000,
                'warning_threshold_days': 60
            },
            'spark_plugs': {
                'name': 'Spark Plugs',
                'mileage_interval_km': 40000,
                'time_interval_days': 1095,  # 3 years
                'priority': 'medium',
                'description': 'Replace spark plugs',
                'warning_threshold_km': 5000,
                'warning_threshold_days': 90
            },
            'battery_check': {
                'name': 'Battery Check',
                'mileage_interval_km': None,  # Time-based only
                'time_interval_days': 365,  # 1 year
                'priority': 'medium',
                'description': 'Test battery health',
                'warning_threshold_km': None,
                'warning_threshold_days': 30
            },
            'inspection': {
                'name': 'Annual Inspection',
                'mileage_interval_km': None,  # Time-based only
                'time_interval_days': 365,  # 1 year
                'priority': 'high',
                'description': 'Annual vehicle inspection',
                'warning_threshold_km': None,
                'warning_threshold_days': 30
            }
        }

        # Initialize reminder storage
        from config import get_config
        CONFIG = get_config()
        self.storage_path = str(CONFIG.DATA_DIR / "maintenance_schedules")
        os.makedirs(self.storage_path, exist_ok=True)

        logger.info("Maintenance Reminders System initialized")

    def get_active_reminders(self, profile_id: int, current_odometer_km: float) -> List[Dict[str, Any]]:
        """
        Get all active reminders for a profile

        Args:
            profile_id: Vehicle profile ID
            current_odometer_km: Current odometer reading

        Returns:
            List of active reminders with status
        """
        try:
            # Get vehicle profile
            profile = self.vehicle_manager.get_profile(profile_id)
            if not profile:
                return []

            # Load custom schedules or use defaults
            schedules = self._load_schedules(profile_id)
            if not schedules:
                schedules = self.default_schedules

            # Get service history
            service_history = self._get_service_history(profile_id)

            # Calculate reminders
            reminders = []
            current_date = datetime.now()

            for service_type, schedule in schedules.items():
                # Get last service for this type
                last_service = self._get_last_service(service_history, service_type)

                # Calculate next due
                reminder = self._calculate_reminder(
                    service_type,
                    schedule,
                    last_service,
                    current_odometer_km,
                    current_date
                )

                if reminder:
                    reminders.append(reminder)

            # Sort by urgency (overdue first, then by days/km remaining)
            reminders.sort(key=lambda r: (
                not r['is_overdue'],  # Overdue first
                r.get('days_remaining', 999999),
                r.get('km_remaining', 999999)
            ))

            return reminders

        except Exception as e:
            logger.error(f"Error getting active reminders: {e}")
            return []

    def _calculate_reminder(self, service_type: str, schedule: Dict[str, Any],
                          last_service: Optional[Dict[str, Any]],
                          current_odometer_km: float,
                          current_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Calculate reminder status for a service type

        Args:
            service_type: Service type ID
            schedule: Service schedule configuration
            last_service: Last service record (or None)
            current_odometer_km: Current odometer
            current_date: Current date

        Returns:
            Reminder data or None
        """
        try:
            # If no last service, use vehicle purchase/creation date as baseline
            if not last_service:
                last_service_date = current_date - timedelta(days=365)  # Assume 1 year ago
                last_service_odometer = max(0, current_odometer_km - 10000)  # Assume 10k km ago
            else:
                last_service_date = datetime.fromisoformat(last_service['date'])
                last_service_odometer = last_service.get('odometer_km', 0)

            # Calculate time-based due date
            time_due = None
            days_remaining = None
            time_overdue = False

            if schedule.get('time_interval_days'):
                time_interval = timedelta(days=schedule['time_interval_days'])
                time_due = last_service_date + time_interval
                days_remaining = (time_due - current_date).days
                time_overdue = days_remaining < 0

            # Calculate mileage-based due
            mileage_due_km = None
            km_remaining = None
            mileage_overdue = False

            if schedule.get('mileage_interval_km'):
                mileage_due_km = last_service_odometer + schedule['mileage_interval_km']
                km_remaining = mileage_due_km - current_odometer_km
                mileage_overdue = km_remaining < 0

            # Determine overall status
            is_overdue = time_overdue or mileage_overdue

            # Check if reminder should be shown (within warning threshold)
            show_reminder = False
            urgency = 'normal'

            if is_overdue:
                show_reminder = True
                urgency = 'overdue'
            else:
                # Check time-based warning
                if days_remaining is not None and schedule.get('warning_threshold_days'):
                    if days_remaining <= schedule['warning_threshold_days']:
                        show_reminder = True
                        if days_remaining <= 7:
                            urgency = 'urgent'
                        else:
                            urgency = 'warning'

                # Check mileage-based warning
                if km_remaining is not None and schedule.get('warning_threshold_km'):
                    if km_remaining <= schedule['warning_threshold_km']:
                        show_reminder = True
                        if km_remaining <= 500:
                            urgency = 'urgent'
                        elif urgency != 'urgent':
                            urgency = 'warning'

            # Only return if reminder should be shown
            if not show_reminder:
                return None

            # Build reminder object
            reminder = {
                'service_type': service_type,
                'name': schedule['name'],
                'description': schedule['description'],
                'priority': schedule['priority'],
                'is_overdue': is_overdue,
                'urgency': urgency,
                'last_service_date': last_service_date.isoformat() if last_service else None,
                'last_service_odometer_km': last_service_odometer if last_service else None,
                'current_odometer_km': current_odometer_km
            }

            # Add time-based info
            if time_due:
                reminder['due_date'] = time_due.isoformat()
                reminder['days_remaining'] = days_remaining
                reminder['days_overdue'] = abs(days_remaining) if time_overdue else 0

            # Add mileage-based info
            if mileage_due_km:
                reminder['due_odometer_km'] = mileage_due_km
                reminder['km_remaining'] = km_remaining
                reminder['km_overdue'] = abs(km_remaining) if mileage_overdue else 0

            # Generate message
            reminder['message'] = self._generate_reminder_message(reminder)

            return reminder

        except Exception as e:
            logger.error(f"Error calculating reminder for {service_type}: {e}")
            return None

    def _generate_reminder_message(self, reminder: Dict[str, Any]) -> str:
        """Generate human-readable reminder message"""
        try:
            name = reminder['name']

            if reminder['is_overdue']:
                # Overdue message
                if reminder.get('days_overdue', 0) > 0:
                    return f"{name} is OVERDUE by {reminder['days_overdue']} days!"
                elif reminder.get('km_overdue', 0) > 0:
                    return f"{name} is OVERDUE by {reminder['km_overdue']:.0f} km!"
                else:
                    return f"{name} is OVERDUE!"

            else:
                # Upcoming message
                parts = []

                if reminder.get('days_remaining') is not None:
                    days = reminder['days_remaining']
                    parts.append(f"{days} day{'s' if days != 1 else ''}")

                if reminder.get('km_remaining') is not None:
                    km = reminder['km_remaining']
                    parts.append(f"{km:.0f} km")

                if parts:
                    return f"{name} due in {' or '.join(parts)}"
                else:
                    return f"{name} due soon"

        except Exception as e:
            return f"{reminder.get('name', 'Service')} reminder"

    def _get_service_history(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get service history from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM service_history WHERE profile_id = ? ORDER BY date DESC',
                (profile_id,)
            )

            rows = cursor.fetchall()
            conn.close()

            # Convert to dict list
            history = []
            for row in rows:
                history.append({
                    'id': row['id'],
                    'profile_id': row['profile_id'],
                    'date': row['date'],
                    'odometer_km': row.get('odometer_km'),
                    'service_type': row.get('service_type', ''),
                    'description': row.get('description', ''),
                    'cost': row.get('cost')
                })

            return history

        except Exception as e:
            logger.error(f"Error getting service history: {e}")
            return []

    def _get_last_service(self, service_history: List[Dict[str, Any]],
                         service_type: str) -> Optional[Dict[str, Any]]:
        """Get last service of specific type from history"""
        try:
            # Normalize service type for matching
            service_type_lower = service_type.lower().replace('_', ' ')

            for service in service_history:
                service_desc = service.get('service_type', '').lower()
                description = service.get('description', '').lower()

                # Check if service type matches
                if service_type_lower in service_desc or service_type_lower in description:
                    return service

            return None

        except Exception as e:
            logger.error(f"Error getting last service: {e}")
            return None

    def _load_schedules(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Load custom schedules for profile"""
        try:
            schedule_file = os.path.join(self.storage_path, f'profile_{profile_id}_schedule.json')

            if os.path.exists(schedule_file):
                with open(schedule_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            return None

        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
            return None

    def save_custom_schedule(self, profile_id: int, schedules: Dict[str, Any]) -> bool:
        """
        Save custom maintenance schedule for profile

        Args:
            profile_id: Profile ID
            schedules: Custom schedule dictionary

        Returns:
            Success status
        """
        try:
            schedule_file = os.path.join(self.storage_path, f'profile_{profile_id}_schedule.json')

            with open(schedule_file, 'w', encoding='utf-8') as f:
                json.dump(schedules, f, indent=2, ensure_ascii=False)

            logger.info(f"Custom schedule saved for profile {profile_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving custom schedule: {e}")
            return False

    def get_reminder_summary(self, profile_id: int, current_odometer_km: float) -> Dict[str, Any]:
        """
        Get reminder summary for dashboard display

        Args:
            profile_id: Profile ID
            current_odometer_km: Current odometer

        Returns:
            Summary with counts and urgent reminders
        """
        try:
            reminders = self.get_active_reminders(profile_id, current_odometer_km)

            # Count by urgency
            overdue_count = len([r for r in reminders if r['urgency'] == 'overdue'])
            urgent_count = len([r for r in reminders if r['urgency'] == 'urgent'])
            warning_count = len([r for r in reminders if r['urgency'] == 'warning'])

            # Get most urgent reminders (top 3)
            urgent_reminders = reminders[:3] if reminders else []

            return {
                'total_reminders': len(reminders),
                'overdue_count': overdue_count,
                'urgent_count': urgent_count,
                'warning_count': warning_count,
                'has_critical': overdue_count > 0 or urgent_count > 0,
                'urgent_reminders': urgent_reminders,
                'all_reminders': reminders
            }

        except Exception as e:
            logger.error(f"Error getting reminder summary: {e}")
            return {
                'total_reminders': 0,
                'overdue_count': 0,
                'urgent_count': 0,
                'warning_count': 0,
                'has_critical': False,
                'urgent_reminders': [],
                'all_reminders': []
            }

    def get_push_notifications(self, profile_id: int, current_odometer_km: float) -> List[Dict[str, Any]]:
        """
        Get reminders formatted for push notifications

        Args:
            profile_id: Profile ID
            current_odometer_km: Current odometer

        Returns:
            List of push notification objects
        """
        try:
            reminders = self.get_active_reminders(profile_id, current_odometer_km)

            notifications = []

            for reminder in reminders:
                # Only send notifications for overdue and urgent
                if reminder['urgency'] not in ['overdue', 'urgent']:
                    continue

                notification = {
                    'type': 'maintenance_reminder',
                    'urgency': reminder['urgency'],
                    'priority': reminder['priority'],
                    'title': f"{reminder['name']} {'Overdue' if reminder['is_overdue'] else 'Due Soon'}",
                    'message': reminder['message'],
                    'service_type': reminder['service_type'],
                    'timestamp': datetime.now().isoformat()
                }

                # Add action buttons
                notification['actions'] = [
                    {'id': 'view_details', 'label': 'View Details'},
                    {'id': 'schedule_service', 'label': 'Schedule Service'},
                    {'id': 'dismiss', 'label': 'Dismiss'}
                ]

                notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error(f"Error generating push notifications: {e}")
            return []

    def add_custom_service(self, profile_id: int, service_config: Dict[str, Any]) -> bool:
        """
        Add custom service reminder

        Args:
            profile_id: Profile ID
            service_config: Service configuration

        Returns:
            Success status
        """
        try:
            # Load existing schedules
            schedules = self._load_schedules(profile_id)
            if not schedules:
                schedules = self.default_schedules.copy()

            # Add custom service
            service_id = service_config.get('id', f"custom_{len(schedules)}")
            schedules[service_id] = service_config

            # Save
            return self.save_custom_schedule(profile_id, schedules)

        except Exception as e:
            logger.error(f"Error adding custom service: {e}")
            return False

    def reset_to_defaults(self, profile_id: int) -> bool:
        """
        Reset to default maintenance schedule

        Args:
            profile_id: Profile ID

        Returns:
            Success status
        """
        try:
            schedule_file = os.path.join(self.storage_path, f'profile_{profile_id}_schedule.json')

            if os.path.exists(schedule_file):
                os.remove(schedule_file)

            logger.info(f"Reset to default schedule for profile {profile_id}")
            return True

        except Exception as e:
            logger.error(f"Error resetting schedule: {e}")
            return False

    def dismiss_reminder(self, profile_id: int, service_type: str,
                        snooze_days: int = 7) -> bool:
        """
        Dismiss/snooze a reminder

        Args:
            profile_id: Profile ID
            service_type: Service type to dismiss
            snooze_days: Days to snooze (default 7)

        Returns:
            Success status
        """
        try:
            # Load dismissals
            dismissals_file = os.path.join(self.storage_path, f'profile_{profile_id}_dismissals.json')

            dismissals = {}
            if os.path.exists(dismissals_file):
                with open(dismissals_file, 'r', encoding='utf-8') as f:
                    dismissals = json.load(f)

            # Add dismissal
            dismissals[service_type] = {
                'dismissed_at': datetime.now().isoformat(),
                'snooze_until': (datetime.now() + timedelta(days=snooze_days)).isoformat()
            }

            # Save
            with open(dismissals_file, 'w', encoding='utf-8') as f:
                json.dump(dismissals, f, indent=2, ensure_ascii=False)

            logger.info(f"Reminder dismissed for {service_type} (snoozed {snooze_days} days)")
            return True

        except Exception as e:
            logger.error(f"Error dismissing reminder: {e}")
            return False

    def get_next_service_date(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """
        Get next upcoming service (soonest due)

        Args:
            profile_id: Profile ID

        Returns:
            Next service info or None
        """
        try:
            # Get current odometer from latest data
            profile = self.vehicle_manager.get_profile(profile_id)
            if not profile:
                return None

            # Get last known odometer from profile or database
            current_odometer = self._get_current_odometer(profile_id, profile)

            reminders = self.get_active_reminders(profile_id, current_odometer)

            if not reminders:
                return None

            # Return first (soonest) reminder
            return reminders[0]

        except Exception as e:
            logger.error(f"Error getting next service: {e}")
            return None

    def _get_current_odometer(self, profile_id: int, profile: Dict) -> int:
        """
        Get current odometer reading from multiple sources.

        Priority:
        1. Profile's stored last_odometer field
        2. Latest OBD session data
        3. Service history (last service mileage)
        4. Default to 0 if nothing found

        Args:
            profile_id: Vehicle profile ID
            profile: Profile dictionary

        Returns:
            Current odometer reading in km
        """
        try:
            # Source 1: Check profile for stored odometer
            if profile.get('last_odometer'):
                return int(profile.get('last_odometer', 0))

            if profile.get('current_mileage'):
                return int(profile.get('current_mileage', 0))

            # Source 2: Query latest OBD data from database
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()

                # Try to get latest speed/distance reading
                c.execute('''
                    SELECT value FROM obd_readings
                    WHERE profile_id = ? AND pid_name IN ('DISTANCE_SINCE_DTC_CLEAR', 'ODOMETER', 'MILEAGE')
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (profile_id,))
                row = c.fetchone()
                if row and row[0]:
                    conn.close()
                    return int(float(row[0]))

                conn.close()
            except Exception as db_error:
                logger.debug(f"Could not get odometer from OBD data: {db_error}")

            # Source 3: Get last service mileage from service history
            try:
                from config import get_config
                CONFIG = get_config()
                service_db = CONFIG.DATA_DIR / "service_history.db"

                if service_db.exists():
                    conn = sqlite3.connect(str(service_db))
                    c = conn.cursor()

                    c.execute('''
                        SELECT service_km FROM service_records
                        WHERE profile_name = ?
                        ORDER BY service_date DESC, service_km DESC
                        LIMIT 1
                    ''', (profile.get('name', ''),))
                    row = c.fetchone()
                    conn.close()

                    if row and row[0]:
                        return int(row[0])
            except Exception as service_error:
                logger.debug(f"Could not get odometer from service history: {service_error}")

            # Default: no odometer data available
            return 0

        except Exception as e:
            logger.error(f"Error getting current odometer: {e}")
            return 0


# Adapter methods for MaintenanceRemindersTab compatibility
_maintenance_predictor = None

def get_maintenance_predictor():
    """
    Get singleton instance of MaintenancePredictor adapter.
    Adapter function for tab compatibility.
    """
    global _maintenance_predictor
    if _maintenance_predictor is None:
        try:
            # Import VehicleProfileManager to create the reminder system
            from vehicle_profile_manager import VehicleProfileManager
            vehicle_manager = VehicleProfileManager()
            reminder_system = MaintenanceRemindersSystem(vehicle_manager)
            _maintenance_predictor = MaintenancePredictor(reminder_system)
        except Exception as e:
            logger.error(f"Error creating MaintenancePredictor: {e}")
            return None
    return _maintenance_predictor


class MaintenancePredictor:
    """
    Adapter class that wraps MaintenanceRemindersSystem.
    Provides the API expected by MaintenanceRemindersTab.
    """
    
    def __init__(self, reminder_system: MaintenanceRemindersSystem):
        """
        Initialize adapter with reminder system instance.
        
        Args:
            reminder_system: MaintenanceRemindersSystem instance
        """
        self.reminder_system = reminder_system
    
    def get_upcoming_maintenance(self, profile_id: int, current_odometer_km: float = None) -> List[Dict[str, Any]]:
        """
        Get upcoming maintenance reminders.
        
        Args:
            profile_id: Vehicle profile ID
            current_odometer_km: Current odometer reading (optional, will be fetched if not provided)
        
        Returns:
            List of upcoming maintenance reminders
        """
        if current_odometer_km is None:
            # Get current odometer from profile
            profile = self.reminder_system.vehicle_manager.get_profile(profile_id)
            if profile:
                current_odometer_km = self.reminder_system._get_current_odometer(profile_id, profile)
            else:
                current_odometer_km = 0
        
        reminders = self.reminder_system.get_active_reminders(profile_id, current_odometer_km)
        
        # Transform to format expected by tab
        result = []
        for r in reminders:
            result.append({
                'id': r['service_type'],
                'service_type': r['service_type'],
                'name': r['name'],
                'description': r['description'],
                'priority': r['priority'],
                'due_date': r.get('due_date'),
                'due_odometer_km': r.get('due_odometer_km'),
                'days_remaining': r.get('days_remaining'),
                'km_remaining': r.get('km_remaining'),
                'is_overdue': r['is_overdue'],
                'urgency': r['urgency'],
                'message': r['message']
            })
        
        return result
    
    def get_predicted_maintenance(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Get AI-predicted maintenance recommendations.
        For now, returns the same as upcoming maintenance.
        Can be enhanced with actual AI predictions later.
        
        Args:
            profile_id: Vehicle profile ID
        
        Returns:
            List of predicted maintenance items
        """
        # For now, return upcoming maintenance as predictions
        # This can be enhanced with actual AI predictions later
        return self.get_upcoming_maintenance(profile_id)
    
    def add_reminder(self, profile_id: int, reminder_data: Dict[str, Any]) -> bool:
        """
        Add a new maintenance reminder.
        
        Args:
            profile_id: Vehicle profile ID
            reminder_data: Reminder configuration
        
        Returns:
            Success status
        """
        try:
            # Transform to service config format
            service_config = {
                'name': reminder_data.get('name', 'Custom Service'),
                'description': reminder_data.get('description', ''),
                'mileage_interval_km': reminder_data.get('mileage_interval'),
                'time_interval_days': reminder_data.get('time_interval'),
                'priority': reminder_data.get('priority', 'medium'),
                'warning_threshold_km': reminder_data.get('warning_threshold_km', 1000),
                'warning_threshold_days': reminder_data.get('warning_threshold_days', 30)
            }
            
            return self.reminder_system.add_custom_service(profile_id, service_config)
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return False
    
    def get_reminders(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Get all reminders for a profile.
        Alias for get_upcoming_maintenance.
        
        Args:
            profile_id: Vehicle profile ID
        
        Returns:
            List of reminders
        """
        return self.get_upcoming_maintenance(profile_id)
    
    def get_service_history(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Get service history for a profile.
        
        Args:
            profile_id: Vehicle profile ID
        
        Returns:
            List of service history records
        """
        return self.reminder_system._get_service_history(profile_id)
    
    def get_default_schedules(self) -> Dict[str, Any]:
        """
        Get default maintenance schedules.
        
        Returns:
            Dictionary of default schedules
        """
        return self.reminder_system.default_schedules.copy()
    
    def get_custom_schedules(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """
        Get custom schedules for a profile.
        
        Args:
            profile_id: Vehicle profile ID
        
        Returns:
            Custom schedules or None
        """
        return self.reminder_system._load_schedules(profile_id)
    
    def save_custom_schedules(self, profile_id: int, schedules: Dict[str, Any]) -> bool:
        """
        Save custom schedules for a profile.
        
        Args:
            profile_id: Vehicle profile ID
            schedules: Schedule configuration
        
        Returns:
            Success status
        """
        return self.reminder_system.save_custom_schedule(profile_id, schedules)
