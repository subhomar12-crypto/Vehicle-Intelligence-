"""
OBD data processor for real-time vehicle data ingestion.

Handles:
- OBD data validation and cleaning
- Sensor unit conversion
- Data normalization
- Stream processing for real-time metrics
- Quality scoring for incoming data
"""

import logging
import math
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

from predict.core.monitoring.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = 5
    GOOD = 4
    FAIR = 3
    POOR = 2
    CRITICAL = 1
    INVALID = 0


@dataclass
class OBDDataPoint:
    """A single OBD data point."""
    timestamp: float
    rpm: Optional[float] = None
    speed: Optional[float] = None
    coolant_temp: Optional[float] = None
    oil_temp: Optional[float] = None
    battery_voltage: Optional[float] = None
    engine_load: Optional[float] = None
    maf_rate: Optional[float] = None
    throttle_pos: Optional[float] = None
    intake_temp: Optional[float] = None
    fuel_level: Optional[float] = None
    odometer: Optional[float] = None
    
    # GPS data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    gps_speed: Optional[float] = None
    heading: Optional[float] = None
    
    # DTCs
    dtc_codes: Optional[List[str]] = None
    
    # Quality metadata
    quality_score: float = 0.0
    quality_level: DataQuality = DataQuality.INVALID
    missing_fields: List[str] = None
    
    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []


class OBDProcessor:
    """Process and validate OBD-II data streams."""
    
    # Sensor valid ranges
    RANGES = {
        "rpm": (0, 16383),
        "speed": (0, 300),  # km/h
        "coolant_temp": (-40, 215),  # Celsius
        "oil_temp": (-40, 215),
        "battery_voltage": (6.0, 18.0),
        "engine_load": (0, 100),  # Percent
        "maf_rate": (0, 655.35),  # g/s
        "throttle_pos": (0, 100),
        "intake_temp": (-40, 215),
        "fuel_level": (0, 100),
    }
    
    # Conversion factors
    CONVERSIONS = {
        # Temperature: Fahrenheit to Celsius
        "temp_f_to_c": lambda x: (x - 32) * 5/9,
        # Speed: mph to km/h
        "mph_to_kmh": lambda x: x * 1.60934,
        # Distance: miles to km
        "miles_to_km": lambda x: x * 1.60934,
        # Pressure: psi to kPa
        "psi_to_kpa": lambda x: x * 6.89476,
    }
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker("obd_processor", CircuitBreakerConfig(failure_threshold=10))
        self._stats = {
            "processed_count": 0,
            "error_count": 0,
            "avg_quality": 0.0,
        }
    
    def process_record(
        self,
        raw_data: Dict[str, Any],
        unit_system: str = "metric",
    ) -> OBDDataPoint:
        """
        Process a raw OBD record into a standardized data point.
        
        Args:
            raw_data: Raw OBD data dictionary
            unit_system: "metric" or "imperial"
        
        Returns:
            Validated and normalized OBDDataPoint
        """
        try:
            # Extract timestamp
            ts = raw_data.get("timestamp") or raw_data.get("ts") or time.time()
            if isinstance(ts, str):
                # Parse ISO format
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
            
            # Create data point
            point = OBDDataPoint(timestamp=ts)
            
            # Process sensor values
            point.rpm = self._extract_value(raw_data, ["rpm", "engine_rpm", "RPM"])
            point.speed = self._extract_value(raw_data, ["speed", "vehicle_speed", "SPEED"])
            point.coolant_temp = self._extract_value(raw_data, ["coolant_temp", "engine_temp", "coolant_temperature"])
            point.oil_temp = self._extract_value(raw_data, ["oil_temp", "oil_temperature"])
            point.battery_voltage = self._extract_value(raw_data, ["battery_voltage", "voltage", "control_module_voltage"])
            point.engine_load = self._extract_value(raw_data, ["engine_load", "calculated_engine_load", "load"])
            point.maf_rate = self._extract_value(raw_data, ["maf_rate", "maf", "mass_air_flow"])
            point.throttle_pos = self._extract_value(raw_data, ["throttle_pos", "throttle_position", "throttle"])
            point.intake_temp = self._extract_value(raw_data, ["intake_temp", "intake_temperature", "iat"])
            point.fuel_level = self._extract_value(raw_data, ["fuel_level", "fuel", "fuel_tank_level"])
            point.odometer = self._extract_value(raw_data, ["odometer", "distance", "mileage"])
            
            # GPS data
            point.latitude = self._extract_value(raw_data, ["latitude", "lat", "gps_lat"])
            point.longitude = self._extract_value(raw_data, ["longitude", "lon", "lng", "gps_lon"])
            point.altitude = self._extract_value(raw_data, ["altitude", "alt", "gps_altitude"])
            point.gps_speed = self._extract_value(raw_data, ["gps_speed", "gps_spd"])
            point.heading = self._extract_value(raw_data, ["heading", "course", "direction"])
            
            # DTC codes
            point.dtc_codes = raw_data.get("dtc_codes") or raw_data.get("dtc") or raw_data.get("trouble_codes", [])
            if isinstance(point.dtc_codes, str):
                point.dtc_codes = [code.strip() for code in point.dtc_codes.split(",") if code.strip()]
            
            # Unit conversions if needed
            if unit_system == "imperial":
                self._convert_to_metric(point)
            
            # Validate ranges
            self._validate_ranges(point)
            
            # Calculate quality
            self._calculate_quality(point)
            
            # Update stats
            self._update_stats(point)
            
            return point
            
        except Exception as e:
            logger.error(f"OBD processing error: {e}")
            self._stats["error_count"] += 1
            return OBDDataPoint(
                timestamp=time.time(),
                quality_level=DataQuality.INVALID,
                quality_score=0.0,
            )
    
    def process_batch(
        self,
        raw_records: List[Dict[str, Any]],
        unit_system: str = "metric",
    ) -> List[OBDDataPoint]:
        """
        Process a batch of OBD records.
        
        Args:
            raw_records: List of raw OBD data dictionaries
            unit_system: "metric" or "imperial"
        
        Returns:
            List of validated data points
        """
        results = []
        for record in raw_records:
            point = self.process_record(record, unit_system)
            if point.quality_level != DataQuality.INVALID:
                results.append(point)
        
        return results
    
    def calculate_derived_metrics(
        self,
        points: List[OBDDataPoint],
    ) -> Dict[str, Any]:
        """
        Calculate derived metrics from a series of data points.
        
        Args:
            points: List of OBD data points (chronologically sorted)
        
        Returns:
            Dictionary of derived metrics
        """
        if len(points) < 2:
            return {"error": "Insufficient data points"}
        
        # Basic statistics
        speeds = [p.speed for p in points if p.speed is not None]
        rpms = [p.rpm for p in points if p.rpm is not None]
        temps = [p.coolant_temp for p in points if p.coolant_temp is not None]
        
        # Calculate trip metrics
        duration = points[-1].timestamp - points[0].timestamp
        
        # Distance calculation from GPS if available
        distance_km = 0.0
        for i in range(1, len(points)):
            if points[i-1].latitude and points[i].latitude:
                distance_km += self._haversine_distance(
                    points[i-1].latitude, points[i-1].longitude,
                    points[i].latitude, points[i].longitude
                )
        
        # Fuel efficiency estimate (if MAF available)
        fuel_efficiency = None
        if points[0].maf_rate:
            # Rough estimate: MAF (g/s) / (14.7 * fuel_density) * 3600 / speed
            avg_maf = sum(p.maf_rate for p in points if p.maf_rate) / len([p for p in points if p.maf_rate])
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            if avg_speed > 0:
                # L/100km approximation
                fuel_efficiency = (avg_maf * 3600) / (14.7 * 750 * avg_speed) * 100
        
        # Aggressive driving detection
        hard_brakes = 0
        hard_accelerations = 0
        for i in range(1, len(points)):
            if points[i].speed and points[i-1].speed:
                delta_speed = points[i].speed - points[i-1].speed
                delta_time = points[i].timestamp - points[i-1].timestamp
                if delta_time > 0:
                    acceleration = delta_speed / delta_time  # km/h/s
                    if acceleration > 10:  # Hard acceleration
                        hard_accelerations += 1
                    elif acceleration < -10:  # Hard braking
                        hard_brakes += 1
        
        return {
            "duration_seconds": duration,
            "distance_km": round(distance_km, 2),
            "avg_speed_kmh": round(sum(speeds) / len(speeds), 1) if speeds else None,
            "max_speed_kmh": max(speeds) if speeds else None,
            "avg_rpm": round(sum(rpms) / len(rpms), 0) if rpms else None,
            "max_coolant_temp": max(temps) if temps else None,
            "fuel_efficiency_l100km": round(fuel_efficiency, 1) if fuel_efficiency else None,
            "hard_brakes": hard_brakes,
            "hard_accelerations": hard_accelerations,
            "data_quality_avg": sum(p.quality_score for p in points) / len(points),
        }
    
    def detect_anomalies(
        self,
        point: OBDDataPoint,
        baseline: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in OBD data.
        
        Args:
            point: Current data point
            baseline: Optional baseline values for comparison
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Critical temperature
        if point.coolant_temp and point.coolant_temp > 110:
            anomalies.append({
                "type": "critical_coolant_temp",
                "value": point.coolant_temp,
                "threshold": 110,
                "severity": "high",
            })
        
        # Low battery voltage
        if point.battery_voltage and point.battery_voltage < 11.5:
            anomalies.append({
                "type": "low_battery",
                "value": point.battery_voltage,
                "threshold": 11.5,
                "severity": "medium",
            })
        
        # High RPM
        if point.rpm and point.rpm > 6000:
            anomalies.append({
                "type": "high_rpm",
                "value": point.rpm,
                "threshold": 6000,
                "severity": "low",
            })
        
        # DTC codes present
        if point.dtc_codes and len(point.dtc_codes) > 0:
            anomalies.append({
                "type": "dtc_present",
                "codes": point.dtc_codes,
                "count": len(point.dtc_codes),
                "severity": "high" if any(c[0] in "PB" for c in point.dtc_codes) else "medium",
            })
        
        return anomalies
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self._stats,
            "success_rate": (
                (self._stats["processed_count"] - self._stats["error_count"]) /
                max(1, self._stats["processed_count"])
            ),
        }
    
    def reset_stats(self):
        """Reset processing statistics."""
        self._stats = {
            "processed_count": 0,
            "error_count": 0,
            "avg_quality": 0.0,
        }
    
    # Private helper methods
    
    def _extract_value(self, data: Dict[str, Any], keys: List[str]) -> Optional[float]:
        """Extract a value from data using multiple possible keys."""
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    val = float(data[key])
                    # Check for NaN or Inf
                    if val == val and val != float('inf') and val != float('-inf'):  # NaN check
                        return val
                except (ValueError, TypeError):
                    continue
        return None
    
    def _convert_to_metric(self, point: OBDDataPoint):
        """Convert imperial units to metric."""
        if point.coolant_temp and point.coolant_temp > 100:
            # Likely Fahrenheit
            point.coolant_temp = self.CONVERSIONS["temp_f_to_c"](point.coolant_temp)
        
        if point.oil_temp and point.oil_temp > 100:
            point.oil_temp = self.CONVERSIONS["temp_f_to_c"](point.oil_temp)
        
        if point.speed and point.speed > 150:
            # Likely mph
            point.speed = self.CONVERSIONS["mph_to_kmh"](point.speed)
        
        if point.gps_speed and point.gps_speed > 150:
            point.gps_speed = self.CONVERSIONS["mph_to_kmh"](point.gps_speed)
        
        if point.odometer and point.odometer > 1000000:
            # Likely miles
            point.odometer = self.CONVERSIONS["miles_to_km"](point.odometer)
    
    def _validate_ranges(self, point: OBDDataPoint):
        """Validate values are within sensor ranges."""
        for field, (min_val, max_val) in self.RANGES.items():
            value = getattr(point, field, None)
            if value is not None:
                if value < min_val or value > max_val:
                    # Clamp to valid range
                    setattr(point, field, max(min_val, min(value, max_val)))
                    point.missing_fields.append(f"{field}_out_of_range")
    
    def _calculate_quality(self, point: OBDDataPoint):
        """Calculate data quality score."""
        # Essential fields
        essential = ["rpm", "speed", "coolant_temp"]
        # Important fields
        important = ["battery_voltage", "engine_load", "maf_rate"]
        # Optional fields
        optional = ["throttle_pos", "intake_temp", "fuel_level"]
        
        essential_count = sum(1 for f in essential if getattr(point, f) is not None)
        important_count = sum(1 for f in important if getattr(point, f) is not None)
        optional_count = sum(1 for f in optional if getattr(point, f) is not None)
        
        # Calculate score (0-100)
        score = (
            (essential_count / len(essential)) * 60 +
            (important_count / len(important)) * 30 +
            (optional_count / len(optional)) * 10
        )
        
        # Deduct for validation errors
        score -= len(point.missing_fields) * 5
        score = max(0, min(100, score))
        
        point.quality_score = score
        
        # Determine level
        if score >= 90:
            point.quality_level = DataQuality.EXCELLENT
        elif score >= 75:
            point.quality_level = DataQuality.GOOD
        elif score >= 50:
            point.quality_level = DataQuality.FAIR
        elif score >= 25:
            point.quality_level = DataQuality.POOR
        else:
            point.quality_level = DataQuality.CRITICAL
    
    def _update_stats(self, point: OBDDataPoint):
        """Update processing statistics."""
        self._stats["processed_count"] += 1
        # Running average of quality
        n = self._stats["processed_count"]
        self._stats["avg_quality"] = (
            (self._stats["avg_quality"] * (n - 1) + point.quality_score) / n
        )
    
    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Calculate distance between two GPS coordinates in km."""
        R = 6371  # Earth radius in km
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
