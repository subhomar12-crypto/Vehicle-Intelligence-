"""
Lightweight statistical preprocessing for telemetry data.

Computes structured summaries (slopes, anomalies, risk levels) from raw sensor
readings before passing to the LLM for narrative generation.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Reuse thresholds from cold_start_predictor.py
SENSOR_THRESHOLDS = {
    "rpm": {"min": 600, "max": 6500, "optimal_min": 700, "optimal_max": 3500, "critical_high": 6000},
    "coolant_temp": {"min": 60, "max": 120, "optimal_min": 82, "optimal_max": 100, "critical_high": 110},
    "oil_temp": {"min": 60, "max": 130, "optimal_min": 90, "optimal_max": 110, "critical_high": 120},
    "battery_voltage": {"min": 11.5, "max": 15.0, "optimal_min": 12.4, "optimal_max": 14.4, "critical_low": 11.8},
    "engine_load": {"min": 0, "max": 100, "optimal_min": 10, "optimal_max": 80, "critical_high": 95},
    "throttle_pos": {"min": 0, "max": 100, "optimal_min": 0, "optimal_max": 85},
    "intake_temp": {"min": -40, "max": 80, "optimal_min": 10, "optimal_max": 50, "critical_high": 70},
    "maf_rate": {"min": 0, "max": 500, "optimal_min": 2, "optimal_max": 300},
    "fuel_level": {"min": 0, "max": 100, "optimal_min": 20, "optimal_max": 100, "critical_low": 10},
    "short_term_fuel_trim": {"min": -25, "max": 25, "optimal_min": -10, "optimal_max": 10},
    "long_term_fuel_trim": {"min": -25, "max": 25, "optimal_min": -10, "optimal_max": 10},
    "boost_pressure": {"min": 0, "max": 300, "optimal_min": 50, "optimal_max": 200, "critical_high": 260},
}


class TelemetryStats:
    """Computes statistical summaries from raw sensor telemetry."""

    def compute_sensor_summary(self, readings: List[float], sensor: str) -> Dict[str, Any]:
        """
        Compute stats for a single sensor's readings.

        Returns: {mean, min, max, slope, std_dev, anomaly_count, risk_level, trend}
        """
        if not readings or len(readings) < 2:
            return {"status": "insufficient_data"}

        arr = np.array(readings, dtype=float)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 2:
            return {"status": "insufficient_data"}

        mean_val = float(np.mean(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        std_val = float(np.std(arr))

        # Linear regression for slope (trend over time)
        x = np.arange(len(arr))
        slope = float(np.polyfit(x, arr, 1)[0])

        # Trend classification based on slope relative to mean
        if mean_val != 0:
            relative_slope = abs(slope) / abs(mean_val)
        else:
            relative_slope = abs(slope)

        if relative_slope < 0.001:
            trend = "stable"
        elif slope > 0:
            trend = "rising"
        else:
            trend = "falling"

        # Anomaly detection: count readings outside optimal range
        anomaly_count = 0
        thresholds = SENSOR_THRESHOLDS.get(sensor)
        risk_level = "normal"

        if thresholds:
            opt_min = thresholds.get("optimal_min", thresholds["min"])
            opt_max = thresholds.get("optimal_max", thresholds["max"])
            anomaly_count = int(np.sum((arr < opt_min) | (arr > opt_max)))

            # Risk classification
            crit_high = thresholds.get("critical_high")
            crit_low = thresholds.get("critical_low")

            if crit_high and max_val >= crit_high:
                risk_level = "critical"
            elif crit_low and min_val <= crit_low:
                risk_level = "critical"
            elif anomaly_count > len(arr) * 0.3:
                risk_level = "warning"
            elif anomaly_count > len(arr) * 0.1:
                risk_level = "elevated"

        return {
            "mean": round(mean_val, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "std_dev": round(std_val, 2),
            "slope": round(slope, 4),
            "trend": trend,
            "anomaly_count": anomaly_count,
            "total_readings": len(arr),
            "risk_level": risk_level,
        }

    def compute_vehicle_summary(self, all_sensor_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Compute stats for all sensors. Returns structured JSON for LLM prompt.

        Args:
            all_sensor_data: {sensor_name: [reading1, reading2, ...]}

        Returns:
            {status, sensors: {sensor_name: {mean, min, max, slope, ...}}, overall_risk}
        """
        if not all_sensor_data:
            return {"status": "no_data", "message": "No driving sessions recorded yet"}

        sensors = {}
        risk_counts = {"critical": 0, "warning": 0, "elevated": 0, "normal": 0}

        for sensor_name, readings in all_sensor_data.items():
            summary = self.compute_sensor_summary(readings, sensor_name)
            if summary.get("status") == "insufficient_data":
                continue
            sensors[sensor_name] = summary
            risk = summary.get("risk_level", "normal")
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        if not sensors:
            return {"status": "no_data", "message": "Insufficient sensor readings for analysis"}

        # Overall risk based on worst sensor risks
        if risk_counts["critical"] > 0:
            overall_risk = "critical"
        elif risk_counts["warning"] > 0:
            overall_risk = "warning"
        elif risk_counts["elevated"] > 0:
            overall_risk = "elevated"
        else:
            overall_risk = "normal"

        return {
            "status": "ok",
            "sensors": sensors,
            "overall_risk": overall_risk,
            "sensors_analyzed": len(sensors),
        }
