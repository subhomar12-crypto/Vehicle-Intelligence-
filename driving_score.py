"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Driving Score

Driving Score System
Analyzes driving behavior and provides safety scores
- Harsh braking detection
- Rapid acceleration detection
- Speeding detection
- Smooth driving rewards
- Overall driving score (0-100)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class DrivingScoreAnalyzer:
    """
    Real-time driving behavior analysis system

    Scoring Components:
    - Smooth Acceleration (25 points)
    - Gentle Braking (25 points)
    - Speed Compliance (25 points)
    - Consistent Speed (25 points)

    Total Score: 0-100
    """

    def __init__(self):
        """Initialize driving score analyzer"""

        # Scoring thresholds
        self.HARSH_BRAKE_THRESHOLD = -3.0  # m/s² (deceleration)
        self.RAPID_ACCEL_THRESHOLD = 3.0   # m/s² (acceleration)
        self.SPEED_LIMIT_TOLERANCE = 10    # km/h over limit
        self.CITY_SPEED_LIMIT = 60         # km/h (default city limit)
        self.HIGHWAY_SPEED_LIMIT = 120     # km/h (default highway limit)

        # Scoring weights
        self.WEIGHTS = {
            'acceleration': 0.25,
            'braking': 0.25,
            'speed_compliance': 0.25,
            'consistency': 0.25
        }

        # Active session tracking per profile
        self.active_sessions = {}  # profile_id -> session_data

        # Event history buffer (last 100 events per profile)
        self.event_history = {}  # profile_id -> deque of events

        logger.info("Driving Score Analyzer initialized")

    def process_data_point(self, profile_id: int, profile_name: str,
                          data: Dict[str, Any], previous_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process data point and update driving score

        Args:
            profile_id: Vehicle profile ID
            profile_name: Profile name
            data: Current OBD data
            previous_data: Previous data point for comparison

        Returns:
            Driving score update with events
        """
        try:
            # Initialize session if needed
            if profile_id not in self.active_sessions:
                self._init_session(profile_id, profile_name)

            session = self.active_sessions[profile_id]
            session['data_points'] += 1

            # Extract current values
            current_speed = data.get('speed', data.get('speed_kmh', 0))
            current_rpm = data.get('rpm', 0)
            current_throttle = data.get('throttle_position', data.get('throttle_position_pct', 0))
            timestamp = data.get('timestamp', datetime.now().isoformat())

            if isinstance(timestamp, str):
                timestamp_dt = datetime.fromisoformat(timestamp)
            else:
                timestamp_dt = timestamp

            # If we have previous data, calculate acceleration/deceleration
            events = []
            if previous_data:
                events = self._analyze_behavior(
                    current_speed,
                    previous_data.get('speed', previous_data.get('speed_kmh', 0)),
                    current_throttle,
                    previous_data.get('throttle_position', previous_data.get('throttle_position_pct', 0)),
                    timestamp_dt,
                    datetime.fromisoformat(previous_data.get('timestamp', timestamp)) if isinstance(previous_data.get('timestamp'), str) else previous_data.get('timestamp', timestamp_dt)
                )

                # Record events
                for event in events:
                    self._record_event(profile_id, event)

            # Check speeding
            speed_events = self._check_speeding(current_speed)
            events.extend(speed_events)
            for event in speed_events:
                self._record_event(profile_id, event)

            # Update speed tracking for consistency
            session['speed_samples'].append(current_speed)
            if len(session['speed_samples']) > 100:
                session['speed_samples'].popleft()

            # Calculate current driving score
            score = self._calculate_driving_score(profile_id)

            return {
                'driving_score': score,
                'events': events,
                'session_data': {
                    'data_points': session['data_points'],
                    'harsh_brakes': session['harsh_brakes'],
                    'rapid_accels': session['rapid_accels'],
                    'speeding_events': session['speeding_events'],
                    'smooth_driving_time': session['smooth_driving_time']
                }
            }

        except Exception as e:
            logger.error(f"Error processing driving score data: {e}")
            return {'driving_score': 50, 'events': [], 'error': str(e)}

    def _init_session(self, profile_id: int, profile_name: str):
        """Initialize driving session"""
        self.active_sessions[profile_id] = {
            'profile_id': profile_id,
            'profile_name': profile_name,
            'start_time': datetime.now().isoformat(),
            'data_points': 0,
            'harsh_brakes': 0,
            'rapid_accels': 0,
            'speeding_events': 0,
            'smooth_driving_time': 0,
            'speed_samples': deque(maxlen=100),
            'last_update': datetime.now()
        }

        self.event_history[profile_id] = deque(maxlen=100)

        logger.info(f"Driving session started for {profile_name}")

    def _analyze_behavior(self, current_speed: float, previous_speed: float,
                         current_throttle: float, previous_throttle: float,
                         current_time: datetime, previous_time: datetime) -> List[Dict[str, Any]]:
        """Analyze driving behavior between two data points"""
        events = []

        try:
            # Calculate time delta
            time_delta = (current_time - previous_time).total_seconds()
            if time_delta == 0 or time_delta > 10:  # Skip if too large gap
                return events

            # Calculate acceleration (m/s²)
            # Convert speed from km/h to m/s
            current_speed_ms = current_speed / 3.6
            previous_speed_ms = previous_speed / 3.6

            acceleration = (current_speed_ms - previous_speed_ms) / time_delta

            # Check for harsh braking
            if acceleration < self.HARSH_BRAKE_THRESHOLD:
                severity = 'severe' if acceleration < -5.0 else 'moderate'
                events.append({
                    'type': 'harsh_brake',
                    'severity': severity,
                    'deceleration_ms2': round(acceleration, 2),
                    'timestamp': current_time.isoformat(),
                    'speed_before': round(previous_speed, 1),
                    'speed_after': round(current_speed, 1)
                })
                logger.debug(f"Harsh braking detected: {acceleration:.2f} m/s²")

            # Check for rapid acceleration
            elif acceleration > self.RAPID_ACCEL_THRESHOLD:
                severity = 'severe' if acceleration > 5.0 else 'moderate'
                events.append({
                    'type': 'rapid_acceleration',
                    'severity': severity,
                    'acceleration_ms2': round(acceleration, 2),
                    'timestamp': current_time.isoformat(),
                    'speed_before': round(previous_speed, 1),
                    'speed_after': round(current_speed, 1),
                    'throttle': round(current_throttle, 1)
                })
                logger.debug(f"Rapid acceleration detected: {acceleration:.2f} m/s²")

            # Check throttle abuse (sudden full throttle)
            throttle_change = current_throttle - previous_throttle
            if throttle_change > 50 and time_delta < 1:  # >50% throttle increase in <1 sec
                events.append({
                    'type': 'throttle_abuse',
                    'severity': 'moderate',
                    'throttle_change': round(throttle_change, 1),
                    'timestamp': current_time.isoformat()
                })

        except Exception as e:
            logger.error(f"Error analyzing behavior: {e}")

        return events

    def _check_speeding(self, current_speed: float) -> List[Dict[str, Any]]:
        """Check if current speed exceeds limits"""
        events = []

        try:
            # Determine speed limit (heuristic: < 80 km/h = city, >= 80 = highway)
            if current_speed < 80:
                speed_limit = self.CITY_SPEED_LIMIT
                context = 'city'
            else:
                speed_limit = self.HIGHWAY_SPEED_LIMIT
                context = 'highway'

            # Check if speeding
            if current_speed > (speed_limit + self.SPEED_LIMIT_TOLERANCE):
                over_limit = current_speed - speed_limit

                severity = 'severe' if over_limit > 30 else 'moderate'

                events.append({
                    'type': 'speeding',
                    'severity': severity,
                    'current_speed': round(current_speed, 1),
                    'speed_limit': speed_limit,
                    'over_limit_kmh': round(over_limit, 1),
                    'context': context,
                    'timestamp': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error checking speeding: {e}")

        return events

    def _record_event(self, profile_id: int, event: Dict[str, Any]):
        """Record driving event"""
        try:
            session = self.active_sessions.get(profile_id)
            if not session:
                return

            # Update counters
            event_type = event.get('type')

            if event_type == 'harsh_brake':
                session['harsh_brakes'] += 1
            elif event_type == 'rapid_acceleration':
                session['rapid_accels'] += 1
            elif event_type == 'speeding':
                session['speeding_events'] += 1

            # Add to history
            if profile_id in self.event_history:
                self.event_history[profile_id].append(event)

        except Exception as e:
            logger.error(f"Error recording event: {e}")

    def _calculate_driving_score(self, profile_id: int) -> float:
        """
        Calculate overall driving score (0-100)

        Components:
        - Acceleration Score (25 points)
        - Braking Score (25 points)
        - Speed Compliance Score (25 points)
        - Consistency Score (25 points)
        """
        try:
            session = self.active_sessions.get(profile_id)
            if not session or session['data_points'] < 10:
                return 100.0  # Default perfect score for new sessions

            data_points = session['data_points']

            # 1. Acceleration Score (fewer rapid accels = higher score)
            rapid_accel_rate = session['rapid_accels'] / data_points
            accel_score = max(0, 25 - (rapid_accel_rate * 1000))

            # 2. Braking Score (fewer harsh brakes = higher score)
            harsh_brake_rate = session['harsh_brakes'] / data_points
            brake_score = max(0, 25 - (harsh_brake_rate * 1000))

            # 3. Speed Compliance Score (fewer speeding events = higher score)
            speeding_rate = session['speeding_events'] / data_points
            speed_score = max(0, 25 - (speeding_rate * 500))

            # 4. Consistency Score (less speed variation = higher score)
            if len(session['speed_samples']) > 10:
                # Filter out stopped periods (speed < 5)
                moving_speeds = [s for s in session['speed_samples'] if s > 5]

                if moving_speeds:
                    speed_std = statistics.stdev(moving_speeds) if len(moving_speeds) > 1 else 0
                    # Lower standard deviation = more consistent = higher score
                    consistency_score = max(0, 25 - (speed_std / 2))
                else:
                    consistency_score = 25
            else:
                consistency_score = 25

            # Total score
            total_score = accel_score + brake_score + speed_score + consistency_score

            # Clamp to 0-100
            total_score = max(0, min(100, total_score))

            return round(total_score, 1)

        except Exception as e:
            logger.error(f"Error calculating driving score: {e}")
            return 50.0

    def get_session_summary(self, profile_id: int) -> Dict[str, Any]:
        """Get driving session summary"""
        try:
            session = self.active_sessions.get(profile_id)
            if not session:
                return {'error': 'No active session'}

            score = self._calculate_driving_score(profile_id)

            # Determine rating
            if score >= 90:
                rating = 'Excellent'
                emoji = '🌟'
            elif score >= 75:
                rating = 'Good'
                emoji = '✅'
            elif score >= 60:
                rating = 'Fair'
                emoji = '⚠️'
            else:
                rating = 'Needs Improvement'
                emoji = '❌'

            return {
                'profile_id': profile_id,
                'profile_name': session['profile_name'],
                'driving_score': score,
                'rating': rating,
                'emoji': emoji,
                'start_time': session['start_time'],
                'data_points': session['data_points'],
                'events': {
                    'harsh_brakes': session['harsh_brakes'],
                    'rapid_accels': session['rapid_accels'],
                    'speeding_events': session['speeding_events']
                },
                'recent_events': list(self.event_history.get(profile_id, []))[-10:]
            }

        except Exception as e:
            logger.error(f"Error getting session summary: {e}")
            return {'error': str(e)}

    def end_session(self, profile_id: int) -> Dict[str, Any]:
        """End driving session and return final summary"""
        try:
            summary = self.get_session_summary(profile_id)

            # Clean up
            if profile_id in self.active_sessions:
                del self.active_sessions[profile_id]
            if profile_id in self.event_history:
                del self.event_history[profile_id]

            logger.info(f"Driving session ended for profile {profile_id}: Score {summary.get('driving_score')}")

            return summary

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return {'error': str(e)}

    def get_all_active_scores(self) -> Dict[int, float]:
        """Get current scores for all active sessions"""
        scores = {}

        for profile_id in self.active_sessions.keys():
            scores[profile_id] = self._calculate_driving_score(profile_id)

        return scores


# ============================================================================
# ADAPTER METHODS - For compatibility with driving_score_tab.py
# ============================================================================

    def get_current_score(self, profile_id: int = 1) -> Dict[str, Any]:
        """
        Get current driving score for tab
        
        Args:
            profile_id: Vehicle profile ID (defaults to 1)
            
        Returns:
            Current score data
        """
        session = self.active_sessions.get(profile_id)
        if not session:
            return {
                'overall_score': 100.0,
                'rating': 'Excellent',
                'session_data': {
                    'data_points': 0,
                    'harsh_brakes': 0,
                    'rapid_accels': 0,
                    'speeding_events': 0,
                    'smooth_driving_time': 0
                }
            }
        
        score = self._calculate_driving_score(profile_id)
        
        # Determine rating
        if score >= 90:
            rating = 'Excellent'
        elif score >= 75:
            rating = 'Good'
        elif score >= 60:
            rating = 'Fair'
        else:
            rating = 'Needs Improvement'
        
        return {
            'overall_score': score,
            'rating': rating,
            'session_data': {
                'data_points': session.get('data_points', 0),
                'harsh_brakes': session.get('harsh_brakes', 0),
                'rapid_accels': session.get('rapid_accels', 0),
                'speeding_events': session.get('speeding_events', 0),
                'smooth_driving_time': session.get('smooth_driving_time', 0)
            }
        }

    def get_trip_history(self, profile_id: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get trip history for tab
        
        Args:
            profile_id: Vehicle profile ID
            limit: Maximum number of trips to return
            
        Returns:
            List of trip summaries
        """
        # For now, return empty list since sessions are in-memory
        # In production, this would query a database
        return []

    def get_behavior_breakdown(self, profile_id: int = 1) -> Dict[str, Any]:
        """
        Get behavior breakdown for tab display
        
        Args:
            profile_id: Vehicle profile ID
            
        Returns:
            Behavior breakdown data
        """
        session = self.active_sessions.get(profile_id)
        if not session:
            return {
                'hard_braking_count': 0,
                'rapid_acceleration_count': 0,
                'speeding_percentage': 0.0,
                'idle_time_minutes': 0.0
            }
        
        data_points = session.get('data_points', 0)
        
        # Calculate percentages
        hard_braking_pct = (session.get('harsh_brakes', 0) / data_points * 100) if data_points > 0 else 0
        rapid_accel_pct = (session.get('rapid_accels', 0) / data_points * 100) if data_points > 0 else 0
        speeding_pct = (session.get('speeding_events', 0) / data_points * 100) if data_points > 0 else 0
        
        return {
            'hard_braking_count': session.get('harsh_brakes', 0),
            'rapid_acceleration_count': session.get('rapid_accels', 0),
            'speeding_percentage': round(speeding_pct, 1),
            'idle_time_minutes': 0.0  # Would need idle detection logic
        }


# Singleton instance for easy access
_score_system = None

def get_driving_analyzer() -> DrivingScoreAnalyzer:
    """Get singleton driving score analyzer instance"""
    global _score_system
    if _score_system is None:
        _score_system = DrivingScoreAnalyzer()
    return _score_system
