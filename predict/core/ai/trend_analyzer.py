"""
Temporal Trend Analyzer (Layer C)

Analyzes historical telemetry to detect:
1. Rate of Change (slope): Battery dropping 0.15V/day → gradual failure
2. Oscillation: RPM swinging ±100 at idle → vacuum leak / IAC issue
3. Gradual degradation: Weekly average declining
4. Correlation shifts: Speed-RPM ratio changing → transmission wear
5. Baseline deviation: Current values vs vehicle's own historical average

Uses only the last N readings (default 100) for efficiency.
No ML model needed — pure statistical analysis.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import statistics
import logging

logger = logging.getLogger(__name__)

# Sensors we actively trend
TRENDING_SENSORS = {
    "battery_voltage", "coolant_temp", "oil_temp",
    "engine_load", "rpm", "short_term_fuel_trim", "long_term_fuel_trim",
    "maf_rate", "intake_temp",
}

# Thresholds for slope-based alerts (units per 100 readings)
SLOPE_THRESHOLDS = {
    "battery_voltage":     {"warning": -0.05,  "critical": -0.15},   # V per reading
    "coolant_temp":        {"warning":  0.10,  "critical":  0.25},   # °C per reading
    "oil_temp":            {"warning":  0.10,  "critical":  0.20},   # °C per reading
    "long_term_fuel_trim": {"warning":  0.05,  "critical":  0.10},   # % per reading
    "engine_load":         {"warning":  0.08,  "critical":  0.15},   # % per reading
}

# Oscillation thresholds (amplitude as fraction of mean)
OSCILLATION_THRESHOLDS = {
    "rpm": {"amplitude_pct": 0.10, "min_mean": 400},   # ±10% at idle
}


@dataclass
class TrendAlert:
    sensor: str
    direction: str          # "rising", "falling", "stable", "oscillating"
    rate: str               # Human-readable rate
    period: str             # "last N readings"
    data_points: List[float] = field(default_factory=list)
    severity: str = "info"  # "info", "warning", "critical"
    message: str = ""
    affects: Dict[str, int] = field(default_factory=dict)


# Sensor → component for health impact
SENSOR_TO_COMPONENT = {
    "battery_voltage": "battery",
    "coolant_temp": "coolant",
    "oil_temp": "engine",
    "engine_load": "engine",
    "long_term_fuel_trim": "fuel_pump",
    "short_term_fuel_trim": "fuel_pump",
    "rpm": "engine",
}

# Health penalties per trend severity
TREND_PENALTIES = {
    "critical": -20,
    "warning": -10,
    "info": 0,
}


class TrendAnalyzer:
    """
    Analyzes a series of historical telemetry readings to detect trends.

    Usage:
        analyzer = TrendAnalyzer()
        alerts = analyzer.analyze(history)  # history: List[Dict[str, float]]
        for alert in alerts:
            print(alert.sensor, alert.direction, alert.message)
    """

    def analyze(
        self,
        history: List[Dict[str, float]],
        min_readings: int = 10,
    ) -> List[TrendAlert]:
        """
        Analyze history for trends.

        Args:
            history:      List of telemetry dicts, oldest first.
            min_readings: Minimum readings required to attempt analysis.

        Returns:
            List of TrendAlert for detected trends. Empty if insufficient data.
        """
        if len(history) < min_readings:
            return []

        alerts = []

        # Extract per-sensor value series
        for sensor in TRENDING_SENSORS:
            values = self._extract_values(history, sensor)
            if len(values) < min_readings:
                continue

            # Check oscillation (before slope — oscillation changes slope interpretation)
            osc_alert = self._detect_oscillation(sensor, values)
            if osc_alert:
                alerts.append(osc_alert)
                continue  # Don't also report a slope alert for oscillating sensors

            # Check slope / trend
            slope_alert = self._detect_slope(sensor, values)
            if slope_alert:
                alerts.append(slope_alert)

        # Check speed-RPM correlation shift
        corr_alert = self._detect_speed_rpm_correlation(history)
        if corr_alert:
            alerts.append(corr_alert)

        return alerts

    # -----------------------------------------------------------------------
    # Per-sensor analysis
    # -----------------------------------------------------------------------

    def _extract_values(self, history: List[Dict], sensor: str) -> List[float]:
        """Extract non-None values for a sensor from history."""
        return [
            r[sensor] for r in history
            if r.get(sensor) is not None and isinstance(r[sensor], (int, float))
        ]

    def _detect_slope(self, sensor: str, values: List[float]) -> Optional[TrendAlert]:
        """
        Detect monotonic trends using linear regression slope.
        Returns a TrendAlert if the slope exceeds configured thresholds.
        """
        if sensor not in SLOPE_THRESHOLDS:
            return None

        slope = self._calculate_slope(values)
        thresholds = SLOPE_THRESHOLDS[sensor]

        # Determine direction and severity
        severity = "info"
        direction = "stable"
        message = ""
        affects = {}
        rate_str = ""

        if slope <= thresholds.get("critical", float("-inf")):
            severity = "critical"
            direction = "falling"
            rate_str = f"{slope:.3f}/reading"
            message = (
                f"{_sensor_label(sensor)} declining critically "
                f"({rate_str}): {values[-1]:.1f} now vs {values[0]:.1f} at start"
            )
            component = SENSOR_TO_COMPONENT.get(sensor)
            if component:
                affects[component] = TREND_PENALTIES["critical"]

        elif slope <= thresholds.get("warning", float("-inf")):
            severity = "warning"
            direction = "falling"
            rate_str = f"{slope:.3f}/reading"
            message = (
                f"{_sensor_label(sensor)} declining steadily "
                f"({rate_str}): {values[-1]:.1f} now vs {values[0]:.1f} at start"
            )
            component = SENSOR_TO_COMPONENT.get(sensor)
            if component:
                affects[component] = TREND_PENALTIES["warning"]

        elif slope >= abs(thresholds.get("critical", 0)) * 1.5:
            severity = "warning"
            direction = "rising"
            rate_str = f"+{slope:.3f}/reading"
            message = (
                f"{_sensor_label(sensor)} rising rapidly "
                f"({rate_str}): {values[0]:.1f} → {values[-1]:.1f}"
            )
            component = SENSOR_TO_COMPONENT.get(sensor)
            if component:
                affects[component] = TREND_PENALTIES["warning"]

        if severity == "info":
            return None

        return TrendAlert(
            sensor=sensor,
            direction=direction,
            rate=rate_str,
            period=f"last {len(values)} readings",
            data_points=_downsample(values, 6),
            severity=severity,
            message=message,
            affects=affects,
        )

    def _detect_oscillation(self, sensor: str, values: List[float]) -> Optional[TrendAlert]:
        """
        Detect values oscillating above amplitude threshold.
        Used for RPM idle oscillation detection.
        """
        if sensor not in OSCILLATION_THRESHOLDS:
            return None

        config = OSCILLATION_THRESHOLDS[sensor]
        mean_val = statistics.mean(values)
        if mean_val < config.get("min_mean", 0):
            return None

        stdev = statistics.stdev(values) if len(values) > 1 else 0
        amplitude_pct = stdev / mean_val if mean_val > 0 else 0

        if amplitude_pct > config["amplitude_pct"]:
            component = SENSOR_TO_COMPONENT.get(sensor)
            affects = {component: TREND_PENALTIES["warning"]} if component else {}
            return TrendAlert(
                sensor=sensor,
                direction="oscillating",
                rate=f"±{stdev:.0f} (±{amplitude_pct*100:.0f}%)",
                period=f"last {len(values)} readings",
                data_points=_downsample(values, 6),
                severity="warning",
                message=(
                    f"{_sensor_label(sensor)} oscillating at idle "
                    f"(±{stdev:.0f} around {mean_val:.0f}) — possible vacuum leak or IAC issue"
                ),
                affects=affects,
            )
        return None

    def _detect_speed_rpm_correlation(
        self, history: List[Dict[str, float]]
    ) -> Optional[TrendAlert]:
        """
        Detect breakdown in speed-RPM correlation — indicator of transmission slip.
        Pearson correlation close to 1.0 = healthy, below 0.7 = slipping.
        Only evaluated on readings where both speed > 20 and RPM > 1000 (driving, not idle).
        """
        driving = [
            r for r in history
            if r.get("speed", 0) > 20 and r.get("rpm", 0) > 1000
        ]
        if len(driving) < 10:
            return None

        speeds = [r["speed"] for r in driving]
        rpms = [r["rpm"] for r in driving]

        corr = self._check_correlation(speeds, rpms)
        if corr is None:
            return None

        if corr < 0.5:
            return TrendAlert(
                sensor="speed_rpm_correlation",
                direction="falling",
                rate=f"correlation={corr:.2f}",
                period=f"last {len(driving)} driving readings",
                data_points=[],
                severity="critical",
                message=(
                    f"Speed-RPM correlation is {corr:.2f} (healthy: >0.7) — "
                    "transmission may be slipping"
                ),
                affects={"transmission_fluid": -35},
            )
        elif corr < 0.7:
            return TrendAlert(
                sensor="speed_rpm_correlation",
                direction="falling",
                rate=f"correlation={corr:.2f}",
                period=f"last {len(driving)} driving readings",
                data_points=[],
                severity="warning",
                message=(
                    f"Speed-RPM correlation degraded to {corr:.2f} — "
                    "monitor transmission"
                ),
                affects={"transmission_fluid": -15},
            )

        return None

    # -----------------------------------------------------------------------
    # Math helpers
    # -----------------------------------------------------------------------

    def _calculate_slope(self, values: List[float]) -> float:
        """Linear regression slope using least-squares formula."""
        n = len(values)
        if n < 2:
            return 0.0
        x = list(range(n))
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        return numerator / denominator if denominator != 0 else 0.0

    def _check_correlation(
        self, series_a: List[float], series_b: List[float]
    ) -> Optional[float]:
        """Pearson correlation coefficient. Returns None if insufficient variance."""
        if len(series_a) != len(series_b) or len(series_a) < 3:
            return None
        n = len(series_a)
        mean_a = statistics.mean(series_a)
        mean_b = statistics.mean(series_b)
        num = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
        den_a = sum((a - mean_a) ** 2 for a in series_a)
        den_b = sum((b - mean_b) ** 2 for b in series_b)
        denom = (den_a * den_b) ** 0.5
        if denom == 0:
            return None
        return max(-1.0, min(1.0, num / denom))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sensor_label(sensor: str) -> str:
    """Human-readable sensor name."""
    labels = {
        "battery_voltage": "Battery voltage",
        "coolant_temp": "Coolant temperature",
        "oil_temp": "Oil temperature",
        "engine_load": "Engine load",
        "long_term_fuel_trim": "Long-term fuel trim",
        "short_term_fuel_trim": "Short-term fuel trim",
        "rpm": "RPM",
    }
    return labels.get(sensor, sensor.replace("_", " ").title())


def _downsample(values: List[float], n: int) -> List[float]:
    """Return n evenly-spaced samples from values."""
    if len(values) <= n:
        return values
    step = len(values) / n
    return [round(values[int(i * step)], 2) for i in range(n)]
