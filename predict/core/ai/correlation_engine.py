"""Sensor correlation engine — rolling Pearson correlation matrix with anomaly detection."""

import numpy as np
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass

# Expected sensor correlations from vehicle physics
EXPECTED_PAIRS = [
    ("rpm", "maf_rate", 0.85),
    ("rpm", "injector_ms", 0.80),
    ("speed", "rpm", 0.70),
    ("throttle_pos", "engine_load", 0.75),
    ("coolant_temp", "ambient_temp", 0.40),
]


@dataclass
class CorrelationAnomaly:
    """Anomaly detected in sensor correlation."""
    pair: Tuple[str, str]
    baseline_r: float
    current_r: float
    delta: float
    severity: str  # "low", "medium", "high"
    interpretation: str


class CorrelationEngine:
    """Rolling correlation analysis for sensor relationships."""

    def __init__(self, window_size: int = 100, break_threshold: float = 0.25):
        """Initialize correlation engine.

        Args:
            window_size: Number of readings for rolling window
            break_threshold: Delta threshold to flag as anomaly (abs difference)
        """
        self.window_size = window_size
        self.break_threshold = break_threshold

    def compute_correlation_matrix(
        self,
        readings: List[Dict[str, Any]],
        sensors: List[str],
    ) -> Dict[Tuple[str, str], float]:
        """Compute Pearson correlation matrix for sensor pairs.

        Args:
            readings: List of telemetry readings
            sensors: List of sensor names to analyze

        Returns:
            Dict mapping (sensor1, sensor2) -> correlation coefficient
        """
        if len(readings) < 10:
            return {}

        # Extract sensor values
        sensor_data = {}
        for sensor in sensors:
            values = []
            for r in readings:
                val = r.get(sensor)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (TypeError, ValueError):
                        values.append(np.nan)
                else:
                    values.append(np.nan)
            sensor_data[sensor] = np.array(values)

        # Compute correlations
        correlations = {}
        for i, s1 in enumerate(sensors):
            for s2 in sensors[i + 1:]:
                data1 = sensor_data[s1]
                data2 = sensor_data[s2]

                # Remove NaN pairs
                mask = ~(np.isnan(data1) | np.isnan(data2))
                if np.sum(mask) < 10:
                    continue

                clean1 = data1[mask]
                clean2 = data2[mask]

                if len(clean1) < 10 or np.std(clean1) == 0 or np.std(clean2) == 0:
                    continue

                # Pearson correlation
                corr = np.corrcoef(clean1, clean2)[0, 1]
                if not np.isnan(corr):
                    correlations[(s1, s2)] = float(corr)

        return correlations

    def detect_anomalies(
        self,
        baseline_corr: Dict[Tuple[str, str], float],
        current_corr: Dict[Tuple[str, str], float],
    ) -> List[CorrelationAnomaly]:
        """Detect correlation breaks between baseline and current.

        Args:
            baseline_corr: Baseline correlation values
            current_corr: Current correlation values

        Returns:
            List of detected anomalies
        """
        anomalies = []

        for pair, baseline_r in baseline_corr.items():
            if pair not in current_corr:
                continue

            current_r = current_corr[pair]
            delta = current_r - baseline_r

            if abs(delta) > self.break_threshold:
                # Determine severity
                if abs(delta) > 0.5:
                    severity = "high"
                elif abs(delta) > 0.35:
                    severity = "medium"
                else:
                    severity = "low"

                # Generate interpretation
                s1, s2 = pair
                if delta < 0:
                    interpretation = f"{s1} ↔ {s2}: correlation dropped from {baseline_r:.2f} to {current_r:.2f}"
                    if pair in [("rpm", "maf_rate"), ("rpm", "injector_ms")]:
                        interpretation += f" — {s2} sensor may be degrading"
                    elif pair == ("speed", "rpm"):
                        interpretation += " — potential clutch/transmission issue"
                    elif pair == ("throttle_pos", "engine_load"):
                        interpretation += " — throttle or load sensor fault"
                else:
                    interpretation = f"{s1} ↔ {s2}: correlation increased from {baseline_r:.2f} to {current_r:.2f}"

                anomalies.append(CorrelationAnomaly(
                    pair=pair,
                    baseline_r=baseline_r,
                    current_r=current_r,
                    delta=delta,
                    severity=severity,
                    interpretation=interpretation,
                ))

        return anomalies

    def analyze_expected_pairs(
        self,
        readings: List[Dict[str, Any]],
    ) -> List[CorrelationAnomaly]:
        """Analyze expected correlation pairs for anomalies.

        Args:
            readings: List of telemetry readings

        Returns:
            List of anomalies for expected pairs
        """
        if len(readings) < 50:
            return []

        # Extract unique sensors from expected pairs
        sensors = set()
        for s1, s2, _ in EXPECTED_PAIRS:
            sensors.add(s1)
            sensors.add(s2)
        sensors = list(sensors)

        # Compute current correlations
        current_corr = self.compute_correlation_matrix(readings, sensors)

        # Build baseline from expected values
        baseline_corr = {(s1, s2): expected for s1, s2, expected in EXPECTED_PAIRS}

        # Detect anomalies
        return self.detect_anomalies(baseline_corr, current_corr)

    def get_correlation_summary(
        self,
        readings: List[Dict[str, Any]],
        sensors: List[str],
    ) -> Dict[str, Any]:
        """Get summary of all correlations for a window.

        Args:
            readings: List of telemetry readings
            sensors: List of sensor names

        Returns:
            Summary dict with correlations and health score
        """
        correlations = self.compute_correlation_matrix(readings, sensors)

        if not correlations:
            return {
                "correlations": {},
                "health_score": 100.0,
                "num_analyzed": 0,
            }

        # Check against expected pairs
        anomalies = self.analyze_expected_pairs(readings)

        # Health score: 100 - penalty for each anomaly
        health_score = 100.0
        for anomaly in anomalies:
            if anomaly.severity == "high":
                health_score -= 20
            elif anomaly.severity == "medium":
                health_score -= 10
            else:
                health_score -= 5

        health_score = max(0.0, health_score)

        return {
            "correlations": {f"{k[0]}_{k[1]}": v for k, v in correlations.items()},
            "health_score": round(health_score, 1),
            "num_analyzed": len(correlations),
            "anomalies": [
                {
                    "pair": list(a.pair),
                    "baseline_r": round(a.baseline_r, 2),
                    "current_r": round(a.current_r, 2),
                    "delta": round(a.delta, 2),
                    "severity": a.severity,
                    "interpretation": a.interpretation,
                }
                for a in anomalies
            ],
        }
