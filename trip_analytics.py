"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Trip Analytics

Trip Analytics System
- Automatic trip detection
- Start/End location tracking with GPS
- Fuel efficiency calculation
- Trip duration and distance tracking
- Route mapping capability
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import math

logger = logging.getLogger(__name__)


class TripAnalytics:
    """
    Intelligent trip detection and analytics system

    Detects trips based on:
    - Vehicle speed (trip starts when speed > 5 km/h)
    - Engine RPM (engine running)
    - Time gaps (trip ends after 5 minutes of inactivity)
    """

    def __init__(self, historical_data_manager):
        """
        Initialize trip analytics

        Args:
            historical_data_manager: HistoricalDataManager instance
        """
        self.historical_data = historical_data_manager

        # Trip detection thresholds
        self.TRIP_START_SPEED_THRESHOLD = 5  # km/h
        self.TRIP_END_IDLE_TIME = 300  # 5 minutes in seconds
        self.MIN_TRIP_DISTANCE = 0.5  # Minimum 0.5 km to count as trip
        self.MIN_TRIP_DURATION = 60  # Minimum 60 seconds

        # Active trip tracking
        self.active_trips = {}  # profile_id -> active_trip_data

        # Trip statistics cache
        self.trip_stats_cache = {}

        logger.info("Trip Analytics initialized")

    def process_data_point(self, profile_id: int, profile_name: str,
                          data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process incoming data point for trip detection

        Args:
            profile_id: Vehicle profile ID
            profile_name: Vehicle profile name
            data: OBD data with GPS (if available)

        Returns:
            Trip update info or None
        """
        try:
            speed = data.get('speed', data.get('speed_kmh', 0))
            rpm = data.get('rpm', 0)
            timestamp = data.get('timestamp', datetime.now().isoformat())

            # Parse timestamp
            if isinstance(timestamp, str):
                timestamp_dt = datetime.fromisoformat(timestamp)
            else:
                timestamp_dt = timestamp

            # GPS data
            gps = data.get('gps', {})
            latitude = gps.get('latitude')
            longitude = gps.get('longitude')

            # Check if trip should start
            if profile_id not in self.active_trips:
                if speed > self.TRIP_START_SPEED_THRESHOLD and rpm > 0:
                    return self._start_trip(profile_id, profile_name, data, timestamp_dt)

            # Update existing trip
            else:
                return self._update_trip(profile_id, data, timestamp_dt)

        except Exception as e:
            logger.error(f"Error processing trip data: {e}")
            return None

    def _start_trip(self, profile_id: int, profile_name: str,
                   data: Dict[str, Any], timestamp: datetime) -> Dict[str, Any]:
        """Start a new trip"""
        try:
            gps = data.get('gps', {})

            trip_data = {
                'profile_id': profile_id,
                'profile_name': profile_name,
                'trip_id': f"trip_{profile_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                'start_time': timestamp.isoformat(),
                'start_location': {
                    'latitude': gps.get('latitude'),
                    'longitude': gps.get('longitude'),
                    'address': None  # Could be geocoded later
                },
                'current_location': {
                    'latitude': gps.get('latitude'),
                    'longitude': gps.get('longitude')
                },
                'start_odometer': data.get('odometer', 0),
                'start_fuel_level': data.get('fuel_level_pct', 100),
                'total_distance': 0.0,
                'duration_seconds': 0,
                'data_points': [data],
                'fuel_consumed': 0.0,
                'avg_speed': 0.0,
                'max_speed': data.get('speed', data.get('speed_kmh', 0)),
                'route_points': []
            }

            # Add GPS route point
            if gps.get('latitude') and gps.get('longitude'):
                trip_data['route_points'].append({
                    'lat': gps['latitude'],
                    'lon': gps['longitude'],
                    'timestamp': timestamp.isoformat()
                })

            self.active_trips[profile_id] = trip_data

            logger.info(f"🚗 Trip started for {profile_name}")

            return {
                'event': 'trip_started',
                'trip_id': trip_data['trip_id'],
                'start_time': trip_data['start_time']
            }

        except Exception as e:
            logger.error(f"Error starting trip: {e}")
            return None

    def _update_trip(self, profile_id: int, data: Dict[str, Any],
                    timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Update active trip with new data point"""
        try:
            trip = self.active_trips.get(profile_id)
            if not trip:
                return None

            speed = data.get('speed', data.get('speed_kmh', 0))
            rpm = data.get('rpm', 0)
            gps = data.get('gps', {})

            # Add data point
            trip['data_points'].append(data)

            # Update duration
            start_time = datetime.fromisoformat(trip['start_time'])
            trip['duration_seconds'] = (timestamp - start_time).total_seconds()

            # Update location
            if gps.get('latitude') and gps.get('longitude'):
                prev_lat = trip['current_location'].get('latitude')
                prev_lon = trip['current_location'].get('longitude')

                new_lat = gps['latitude']
                new_lon = gps['longitude']

                # Calculate distance increment
                if prev_lat and prev_lon:
                    distance_km = self._calculate_distance(
                        prev_lat, prev_lon, new_lat, new_lon
                    )
                    trip['total_distance'] += distance_km

                # Update current location
                trip['current_location'] = {
                    'latitude': new_lat,
                    'longitude': new_lon
                }

                # Add route point (every 30 seconds to avoid too many points)
                if len(trip['route_points']) == 0 or \
                   (timestamp - datetime.fromisoformat(trip['route_points'][-1]['timestamp'])).total_seconds() > 30:
                    trip['route_points'].append({
                        'lat': new_lat,
                        'lon': new_lon,
                        'timestamp': timestamp.isoformat(),
                        'speed': speed
                    })

            # Update speed stats
            trip['max_speed'] = max(trip['max_speed'], speed)

            # Calculate average speed
            if trip['duration_seconds'] > 0:
                trip['avg_speed'] = (trip['total_distance'] / trip['duration_seconds']) * 3600  # km/h

            # Estimate fuel consumed (rough calculation)
            fuel_level = data.get('fuel_level_pct', trip['start_fuel_level'])
            trip['fuel_consumed'] = trip['start_fuel_level'] - fuel_level

            # Check if trip should end (idle for 5 minutes)
            if speed < 1 and rpm < 800:
                # Check last data point time
                if len(trip['data_points']) > 1:
                    last_active = datetime.fromisoformat(trip['data_points'][-2].get('timestamp', timestamp.isoformat()))
                    idle_time = (timestamp - last_active).total_seconds()

                    if idle_time > self.TRIP_END_IDLE_TIME:
                        return self._end_trip(profile_id, timestamp)

            return {
                'event': 'trip_updated',
                'trip_id': trip['trip_id'],
                'distance': round(trip['total_distance'], 2),
                'duration': trip['duration_seconds']
            }

        except Exception as e:
            logger.error(f"Error updating trip: {e}")
            return None

    def _end_trip(self, profile_id: int, end_time: datetime) -> Dict[str, Any]:
        """End active trip and save it"""
        try:
            trip = self.active_trips.get(profile_id)
            if not trip:
                return None

            # Check minimum trip requirements
            if trip['total_distance'] < self.MIN_TRIP_DISTANCE or \
               trip['duration_seconds'] < self.MIN_TRIP_DURATION:
                # Trip too short, discard
                del self.active_trips[profile_id]
                logger.info(f"Trip discarded (too short): {trip['trip_id']}")
                return {'event': 'trip_discarded', 'reason': 'too_short'}

            # Finalize trip data
            trip['end_time'] = end_time.isoformat()
            trip['end_location'] = trip['current_location'].copy()

            # Calculate fuel efficiency
            if trip['fuel_consumed'] > 0 and trip['total_distance'] > 0:
                # L/100km (rough estimate based on fuel level %)
                # Assuming average tank size of 60L
                tank_size = 60
                liters_consumed = (trip['fuel_consumed'] / 100) * tank_size
                trip['fuel_efficiency_l_per_100km'] = (liters_consumed / trip['total_distance']) * 100
                trip['fuel_efficiency_mpg'] = 235.21 / trip['fuel_efficiency_l_per_100km']  # Convert to MPG
            else:
                trip['fuel_efficiency_l_per_100km'] = None
                trip['fuel_efficiency_mpg'] = None

            # Calculate trip summary
            trip['summary'] = self._generate_trip_summary(trip)

            # Save trip to historical data
            self.historical_data.save_trip_data(
                trip['profile_name'],
                trip['profile_id'],
                trip
            )

            # Remove from active trips
            del self.active_trips[profile_id]

            logger.info(f"🏁 Trip completed: {trip['trip_id']} - {trip['total_distance']:.2f} km in {trip['duration_seconds']/60:.1f} min")

            return {
                'event': 'trip_completed',
                'trip_id': trip['trip_id'],
                'distance': round(trip['total_distance'], 2),
                'duration': trip['duration_seconds'],
                'avg_speed': round(trip['avg_speed'], 1),
                'fuel_efficiency': trip.get('fuel_efficiency_l_per_100km'),
                'summary': trip['summary']
            }

        except Exception as e:
            logger.error(f"Error ending trip: {e}")
            return None

    def _generate_trip_summary(self, trip: Dict[str, Any]) -> str:
        """Generate human-readable trip summary"""
        try:
            distance = trip['total_distance']
            duration_min = trip['duration_seconds'] / 60
            avg_speed = trip['avg_speed']
            max_speed = trip['max_speed']

            summary = f"Trip: {distance:.1f} km in {duration_min:.0f} minutes"
            summary += f" (Avg: {avg_speed:.0f} km/h, Max: {max_speed:.0f} km/h)"

            if trip.get('fuel_efficiency_l_per_100km'):
                summary += f", Fuel: {trip['fuel_efficiency_l_per_100km']:.1f} L/100km"

            return summary

        except Exception as e:
            return "Trip completed"

    def _calculate_distance(self, lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula

        Returns:
            Distance in kilometers
        """
        try:
            # Earth radius in km
            R = 6371.0

            # Convert to radians
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            # Haversine formula
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

            distance = R * c

            return distance

        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return 0.0

    def get_trip_statistics(self, profile_id: int, profile_name: str,
                          days: int = 30) -> Dict[str, Any]:
        """
        Get trip statistics for a profile

        Args:
            profile_id: Profile ID
            profile_name: Profile name
            days: Number of days to analyze

        Returns:
            Trip statistics dictionary
        """
        try:
            # Load trips from historical data
            trips = self._load_trips(profile_name, profile_id, days)

            if not trips:
                return {
                    'total_trips': 0,
                    'message': 'No trips found'
                }

            # Calculate statistics
            total_trips = len(trips)
            total_distance = sum(t.get('total_distance', 0) for t in trips)
            total_duration = sum(t.get('duration_seconds', 0) for t in trips)

            avg_distance = total_distance / total_trips if total_trips > 0 else 0
            avg_duration = total_duration / total_trips if total_trips > 0 else 0

            # Fuel efficiency (average of trips that have data)
            fuel_efficiencies = [t.get('fuel_efficiency_l_per_100km')
                               for t in trips
                               if t.get('fuel_efficiency_l_per_100km')]

            avg_fuel_efficiency = sum(fuel_efficiencies) / len(fuel_efficiencies) if fuel_efficiencies else None

            # Speed statistics
            avg_speeds = [t.get('avg_speed', 0) for t in trips]
            max_speeds = [t.get('max_speed', 0) for t in trips]

            stats = {
                'total_trips': total_trips,
                'total_distance_km': round(total_distance, 2),
                'total_duration_hours': round(total_duration / 3600, 2),
                'avg_trip_distance_km': round(avg_distance, 2),
                'avg_trip_duration_min': round(avg_duration / 60, 1),
                'avg_speed_kmh': round(sum(avg_speeds) / len(avg_speeds), 1) if avg_speeds else 0,
                'max_speed_kmh': max(max_speeds) if max_speeds else 0,
                'avg_fuel_efficiency_l_per_100km': round(avg_fuel_efficiency, 2) if avg_fuel_efficiency else None,
                'period_days': days
            }

            return stats

        except Exception as e:
            logger.error(f"Error calculating trip statistics: {e}")
            return {'error': str(e)}

    def _load_trips(self, profile_name: str, profile_id: int,
                   days: int) -> List[Dict[str, Any]]:
        """Load trips from historical data"""
        try:
            # Get trips folder
            profile_folder = self.historical_data.get_profile_folder_name(profile_name, profile_id)
            trips_folder = os.path.join(
                self.historical_data.base_path,
                profile_folder,
                'trips'
            )

            if not os.path.exists(trips_folder):
                return []

            # Load trip files from last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            trips = []

            for filename in os.listdir(trips_folder):
                if filename.startswith('trip_') and filename.endswith('.json'):
                    file_path = os.path.join(trips_folder, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if file_time >= cutoff_date:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            trip_data = json.load(f)
                            trips.append(trip_data)

            # Sort by start time
            trips.sort(key=lambda t: t.get('start_time', ''), reverse=True)

            return trips

        except Exception as e:
            logger.error(f"Error loading trips: {e}")
            return []

    def get_recent_trips(self, profile_id: int, profile_name: str,
                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent trips for display

        Args:
            profile_id: Profile ID
            profile_name: Profile name
            limit: Maximum number of trips to return

        Returns:
            List of recent trips
        """
        try:
            trips = self._load_trips(profile_name, profile_id, days=30)

            # Return limited, formatted trips
            recent = []
            for trip in trips[:limit]:
                recent.append({
                    'trip_id': trip.get('trip_id'),
                    'start_time': trip.get('start_time'),
                    'end_time': trip.get('end_time'),
                    'distance_km': round(trip.get('total_distance', 0), 2),
                    'duration_min': round(trip.get('duration_seconds', 0) / 60, 1),
                    'avg_speed_kmh': round(trip.get('avg_speed', 0), 1),
                    'fuel_efficiency': trip.get('fuel_efficiency_l_per_100km'),
                    'summary': trip.get('summary', 'No summary')
                })

            return recent

        except Exception as e:
            logger.error(f"Error getting recent trips: {e}")
            return []

    def force_end_all_trips(self):
        """Force end all active trips (e.g., on app shutdown)"""
        try:
            for profile_id in list(self.active_trips.keys()):
                self._end_trip(profile_id, datetime.now())

            logger.info("All active trips ended")

        except Exception as e:
            logger.error(f"Error ending all trips: {e}")
