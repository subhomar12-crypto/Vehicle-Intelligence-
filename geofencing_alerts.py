"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Geofencing Alerts

Geofencing Alert System
Monitor GPS location and trigger alerts for specific zones
- Desert area alerts
- Custom geofences
- Entry/exit notifications
- Safety recommendations
- Time tracking in zones
"""

import os
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import deque

from config import get_config
CONFIG = get_config()

logger = logging.getLogger(__name__)


class GeofencingAlertSystem:
    """
    GPS-based geofencing with focus on desert area safety

    Features:
    - Pre-defined desert zones
    - Custom geofence creation
    - Entry/exit alerts
    - Distance from zone center
    - Time spent in zone
    - Safety recommendations
    """

    def __init__(self, communication_hub=None):
        """
        Initialize geofencing system

        Args:
            communication_hub: TwoWayCommunicationHub instance (optional)
        """
        self.communication_hub = communication_hub

        # Pre-defined desert zones (example coordinates - customize for your region)
        self.desert_zones = self._load_desert_zones()

        # Custom geofences
        self.custom_geofences = {}

        # Active zone tracking per profile
        self.active_zones = {}  # profile_id -> {zone_id, entry_time, etc.}

        # Zone history
        self.zone_history = {}  # profile_id -> deque of zone events

        # Alert cooldown
        self.alert_cooldown = {}  # alert_key -> last_sent_time

        # Storage
        self.storage_path = str(CONFIG.DATA_DIR / "geofences")
        os.makedirs(self.storage_path, exist_ok=True)

        # Load custom geofences
        self._load_custom_geofences()

        logger.info("Geofencing Alert System initialized")

    def _load_desert_zones(self) -> Dict[str, Dict]:
        """Load pre-defined desert zones"""
        # Example desert zones (customize for your region)
        # These are sample coordinates - replace with actual desert areas
        return {
            'sahara_egypt': {
                'name': 'Sahara Desert - Egypt',
                'type': 'desert',
                'center': {'lat': 27.0, 'lon': 30.0},  # Example coordinates
                'radius_km': 100,
                'severity': 'high',
                'warnings': [
                    'Extreme heat - check coolant levels',
                    'Sand storms possible',
                    'Limited mobile coverage',
                    'Ensure sufficient fuel and water'
                ],
                'recommended_checks': [
                    'Engine coolant level',
                    'Tire pressure',
                    'Fuel level > 50%',
                    'Emergency supplies'
                ]
            },
            'arabian_desert': {
                'name': 'Arabian Desert',
                'type': 'desert',
                'center': {'lat': 23.0, 'lon': 45.0},  # Example coordinates
                'radius_km': 150,
                'severity': 'high',
                'warnings': [
                    'Extreme temperatures',
                    'Remote area - limited services',
                    'Check vehicle before proceeding'
                ],
                'recommended_checks': [
                    'Full fuel tank recommended',
                    'Check all fluid levels',
                    'Test air conditioning',
                    'Verify tire condition'
                ]
            },
            'gobi_desert': {
                'name': 'Gobi Desert',
                'type': 'desert',
                'center': {'lat': 42.5, 'lon': 103.0},  # Example coordinates
                'radius_km': 200,
                'severity': 'extreme',
                'warnings': [
                    'Extreme temperature variations',
                    'Very remote area',
                    'Limited infrastructure'
                ],
                'recommended_checks': [
                    'Full vehicle inspection',
                    'Emergency supplies mandatory',
                    'Communication equipment',
                    'Spare fuel recommended'
                ]
            }
        }

    def _load_custom_geofences(self):
        """Load custom geofences from storage"""
        try:
            geofence_file = os.path.join(self.storage_path, 'custom_geofences.json')

            if os.path.exists(geofence_file):
                with open(geofence_file, 'r', encoding='utf-8') as f:
                    self.custom_geofences = json.load(f)

                logger.info(f"Loaded {len(self.custom_geofences)} custom geofences")

        except Exception as e:
            logger.error(f"Error loading custom geofences: {e}")

    def save_custom_geofences(self):
        """Save custom geofences to storage"""
        try:
            geofence_file = os.path.join(self.storage_path, 'custom_geofences.json')

            with open(geofence_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_geofences, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.custom_geofences)} custom geofences")

        except Exception as e:
            logger.error(f"Error saving custom geofences: {e}")

    def process_gps_data(self, profile_id: int, profile_name: str,
                        latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """
        Process GPS coordinates and check for geofence events

        Args:
            profile_id: Vehicle profile ID
            profile_name: Profile name
            latitude: Current latitude
            longitude: Current longitude

        Returns:
            List of geofence events/alerts
        """
        try:
            events = []

            # Combine all zones (desert + custom)
            all_zones = {**self.desert_zones, **self.custom_geofences}

            # Check each zone
            for zone_id, zone_data in all_zones.items():
                event = self._check_zone(
                    profile_id, profile_name, zone_id, zone_data,
                    latitude, longitude
                )
                if event:
                    events.append(event)

            return events

        except Exception as e:
            logger.error(f"Error processing GPS data: {e}")
            return []

    def _check_zone(self, profile_id: int, profile_name: str,
                   zone_id: str, zone_data: Dict[str, Any],
                   current_lat: float, current_lon: float) -> Optional[Dict[str, Any]]:
        """Check if vehicle is in zone and generate events"""
        try:
            zone_center = zone_data['center']
            zone_radius_km = zone_data['radius_km']

            # Calculate distance from zone center
            distance_km = self._calculate_distance(
                current_lat, current_lon,
                zone_center['lat'], zone_center['lon']
            )

            # Check if inside zone
            is_inside = distance_km <= zone_radius_km

            # Get current zone state
            zone_key = f"{profile_id}_{zone_id}"
            was_inside = zone_key in self.active_zones

            # Entry event
            if is_inside and not was_inside:
                return self._handle_zone_entry(
                    profile_id, profile_name, zone_id, zone_data,
                    current_lat, current_lon, distance_km
                )

            # Exit event
            elif not is_inside and was_inside:
                return self._handle_zone_exit(
                    profile_id, profile_name, zone_id, zone_data,
                    current_lat, current_lon
                )

            # Inside zone - update tracking
            elif is_inside and was_inside:
                self._update_zone_tracking(
                    profile_id, zone_id, current_lat, current_lon, distance_km
                )

            return None

        except Exception as e:
            logger.error(f"Error checking zone: {e}")
            return None

    def _handle_zone_entry(self, profile_id: int, profile_name: str,
                          zone_id: str, zone_data: Dict[str, Any],
                          lat: float, lon: float, distance_km: float) -> Dict[str, Any]:
        """Handle zone entry event"""
        try:
            zone_key = f"{profile_id}_{zone_id}"

            # Record entry
            entry_time = datetime.now()
            self.active_zones[zone_key] = {
                'profile_id': profile_id,
                'profile_name': profile_name,
                'zone_id': zone_id,
                'zone_name': zone_data['name'],
                'zone_type': zone_data.get('type', 'custom'),
                'entry_time': entry_time.isoformat(),
                'entry_location': {'lat': lat, 'lon': lon},
                'distance_from_center_km': distance_km
            }

            # Add to history
            if profile_id not in self.zone_history:
                self.zone_history[profile_id] = deque(maxlen=100)

            event = {
                'event_type': 'zone_entry',
                'zone_id': zone_id,
                'zone_name': zone_data['name'],
                'zone_type': zone_data.get('type', 'custom'),
                'severity': zone_data.get('severity', 'info'),
                'timestamp': entry_time.isoformat(),
                'location': {'lat': lat, 'lon': lon},
                'distance_from_center_km': round(distance_km, 2)
            }

            self.zone_history[profile_id].append(event)

            # Send alert
            self._send_zone_alert(
                profile_id, profile_name, 'entry', zone_id, zone_data,
                lat, lon, distance_km
            )

            logger.info(f"{profile_name} entered zone: {zone_data['name']}")

            return event

        except Exception as e:
            logger.error(f"Error handling zone entry: {e}")
            return None

    def _handle_zone_exit(self, profile_id: int, profile_name: str,
                         zone_id: str, zone_data: Dict[str, Any],
                         lat: float, lon: float) -> Dict[str, Any]:
        """Handle zone exit event"""
        try:
            zone_key = f"{profile_id}_{zone_id}"

            # Get entry info
            zone_info = self.active_zones.get(zone_key, {})
            entry_time = datetime.fromisoformat(zone_info.get('entry_time', datetime.now().isoformat()))

            # Calculate time spent
            exit_time = datetime.now()
            duration_seconds = (exit_time - entry_time).total_seconds()
            duration_minutes = duration_seconds / 60

            # Remove from active zones
            if zone_key in self.active_zones:
                del self.active_zones[zone_key]

            # Add to history
            if profile_id not in self.zone_history:
                self.zone_history[profile_id] = deque(maxlen=100)

            event = {
                'event_type': 'zone_exit',
                'zone_id': zone_id,
                'zone_name': zone_data['name'],
                'zone_type': zone_data.get('type', 'custom'),
                'timestamp': exit_time.isoformat(),
                'location': {'lat': lat, 'lon': lon},
                'time_spent_minutes': round(duration_minutes, 1),
                'entry_time': zone_info.get('entry_time')
            }

            self.zone_history[profile_id].append(event)

            # Send exit alert
            self._send_zone_alert(
                profile_id, profile_name, 'exit', zone_id, zone_data,
                lat, lon, duration_minutes=duration_minutes
            )

            logger.info(f"{profile_name} exited zone: {zone_data['name']} (duration: {duration_minutes:.1f} min)")

            return event

        except Exception as e:
            logger.error(f"Error handling zone exit: {e}")
            return None

    def _update_zone_tracking(self, profile_id: int, zone_id: str,
                             lat: float, lon: float, distance_km: float):
        """Update tracking for vehicle inside zone"""
        try:
            zone_key = f"{profile_id}_{zone_id}"

            if zone_key in self.active_zones:
                self.active_zones[zone_key]['current_location'] = {'lat': lat, 'lon': lon}
                self.active_zones[zone_key]['distance_from_center_km'] = distance_km
                self.active_zones[zone_key]['last_update'] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Error updating zone tracking: {e}")

    def _send_zone_alert(self, profile_id: int, profile_name: str,
                        event_type: str, zone_id: str, zone_data: Dict[str, Any],
                        lat: float, lon: float, duration_minutes: float = None):
        """Send geofence alert via communication hub"""
        try:
            if not self.communication_hub:
                return

            # Check cooldown
            alert_key = f"{profile_id}_{zone_id}_{event_type}"
            if not self._check_alert_cooldown(alert_key, event_type):
                return

            # Build alert
            if event_type == 'entry':
                title = f"🏜️ Entered {zone_data['name']}"
                message = f"{profile_name} entered {zone_data.get('type', 'zone')}: {zone_data['name']}"

                # Add warnings for desert zones
                warnings = zone_data.get('warnings', [])
                if warnings:
                    message += f"\n\nWarnings:\n" + "\n".join([f"• {w}" for w in warnings[:3]])

                actions = [
                    {'id': 'view_recommendations', 'label': 'View Safety Checks'},
                    {'id': 'acknowledge', 'label': 'Acknowledge'},
                    {'id': 'dismiss', 'label': 'Dismiss'}
                ]

            else:  # exit
                title = f"✅ Exited {zone_data['name']}"
                message = f"{profile_name} exited {zone_data['name']}"
                if duration_minutes:
                    message += f"\nTime spent: {duration_minutes:.0f} minutes"

                actions = [
                    {'id': 'dismiss', 'label': 'OK'}
                ]

            notification = {
                'type': 'geofence_alert',
                'event_type': event_type,
                'zone_id': zone_id,
                'zone_name': zone_data['name'],
                'zone_type': zone_data.get('type', 'custom'),
                'severity': zone_data.get('severity', 'info'),
                'title': title,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'location': {'lat': lat, 'lon': lon},
                'actions': actions,
                'recommended_checks': zone_data.get('recommended_checks', [])
            }

            # Send via communication hub
            result = self.communication_hub.send_notification_to_mobile(
                profile_id,
                notification
            )

            if result.get('success'):
                logger.info(f"Geofence alert sent: {title}")

        except Exception as e:
            logger.error(f"Error sending zone alert: {e}")

    def _check_alert_cooldown(self, alert_key: str, event_type: str) -> bool:
        """Check if alert can be sent (not in cooldown)"""
        try:
            cooldown_minutes = 30 if event_type == 'entry' else 60  # Entry: 30min, Exit: 60min

            if alert_key in self.alert_cooldown:
                last_sent = self.alert_cooldown[alert_key]
                time_diff = (datetime.now() - last_sent).total_seconds() / 60

                if time_diff < cooldown_minutes:
                    return False

            # Update cooldown
            self.alert_cooldown[alert_key] = datetime.now()
            return True

        except Exception as e:
            logger.error(f"Error checking alert cooldown: {e}")
            return True

    def _calculate_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS coordinates (Haversine formula)

        Returns:
            Distance in kilometers
        """
        try:
            R = 6371.0  # Earth radius in km

            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

            distance = R * c

            return distance

        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return 0.0

    def create_custom_geofence(self, geofence_id: str, geofence_data: Dict[str, Any]) -> bool:
        """
        Create custom geofence

        Args:
            geofence_id: Unique geofence ID
            geofence_data: Geofence configuration

        Returns:
            Success status
        """
        try:
            # Validate required fields
            required = ['name', 'center', 'radius_km']
            if not all(field in geofence_data for field in required):
                logger.error(f"Missing required fields for geofence")
                return False

            # Add to custom geofences
            self.custom_geofences[geofence_id] = geofence_data
            self.save_custom_geofences()

            logger.info(f"Custom geofence created: {geofence_data['name']}")
            return True

        except Exception as e:
            logger.error(f"Error creating custom geofence: {e}")
            return False

    def delete_custom_geofence(self, geofence_id: str) -> bool:
        """Delete custom geofence"""
        try:
            if geofence_id in self.custom_geofences:
                del self.custom_geofences[geofence_id]
                self.save_custom_geofences()
                logger.info(f"Custom geofence deleted: {geofence_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting custom geofence: {e}")
            return False

    def get_active_zones(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get zones that vehicle is currently in"""
        try:
            active = []

            for zone_key, zone_info in self.active_zones.items():
                if zone_info['profile_id'] == profile_id:
                    # Calculate time spent
                    entry_time = datetime.fromisoformat(zone_info['entry_time'])
                    time_spent = (datetime.now() - entry_time).total_seconds() / 60

                    zone_info['time_spent_minutes'] = round(time_spent, 1)
                    active.append(zone_info)

            return active

        except Exception as e:
            logger.error(f"Error getting active zones: {e}")
            return []

    def get_zone_history(self, profile_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get zone entry/exit history"""
        try:
            if profile_id not in self.zone_history:
                return []

            history = list(self.zone_history[profile_id])
            history.reverse()  # Most recent first

            return history[:limit]

        except Exception as e:
            logger.error(f"Error getting zone history: {e}")
            return []

    def get_all_zones(self) -> Dict[str, Any]:
        """Get all available zones (desert + custom)"""
        return {
            'desert_zones': self.desert_zones,
            'custom_zones': self.custom_geofences,
            'total_zones': len(self.desert_zones) + len(self.custom_geofences)
        }


# Singleton instance
_geofencing_manager: Optional[GeofencingAlertSystem] = None


def get_geofencing_manager() -> GeofencingAlertSystem:
    """
    Get singleton instance of geofencing alert system

    Returns:
        GeofencingAlertSystem instance
    """
    global _geofencing_manager
    if _geofencing_manager is None:
        _geofencing_manager = GeofencingAlertSystem()
    return _geofencing_manager
