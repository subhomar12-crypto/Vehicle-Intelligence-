"""
Data Quality Filter — OBD Telemetry Cleaning Pipeline.

Cleans raw OBD telemetry BEFORE it reaches the AI prediction engine.
Prevents sensor glitches, stuck values, and connection start-up garbage
from corrupting health assessments.

Filtering layers (applied in order per reading):
  1. Warm-up: first N readings after connection → discarded (start-up noise)
  2. Range validation: values outside physical sensor limits → rejected
  3. Outlier rejection: value > 3σ from rolling average → rejected
  4. Stuck sensor detection: same exact value for 30+ consecutive readings → flagged

Usage:
    f = DataQualityFilter(warmup_readings=10)
    cleaned, quality = f.filter_reading({"rpm": 2500.0, "battery_voltage": 13.8})
    # quality: {"rpm": 1.0, "battery_voltage": 1.0}
"""

import logging
import math
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum number of post-warmup readings needed before outlier rejection is active.
# With fewer readings the rolling std is too unstable to trust.
_MIN_READINGS_FOR_OUTLIER = 5

# Number of standard deviations beyond which a value is considered an outlier.
_OUTLIER_SIGMA = 3.0

# Number of consecutive identical readings before a sensor is considered stuck.
_STUCK_THRESHOLD = 30


class DataQualityFilter:
    """
    Cleans OBD telemetry data before AI processing.

    Thread-safety: not thread-safe. Create one instance per active OBD session.
    Reset between sessions with reset().
    """

    # Physical range limits for known OBD sensors.
    # Tuple: (min_valid, max_valid)  — inclusive boundaries.
    PHYSICAL_RANGES: Dict[str, Tuple[float, float]] = {
        "rpm":                   (0.0,   9000.0),
        "speed":                 (0.0,    300.0),
        "coolant_temp":         (-40.0,   150.0),
        "battery_voltage":       (0.0,     20.0),
        "engine_load":           (0.0,    100.0),
        "throttle_pos":          (0.0,    100.0),
        "fuel_level":            (0.0,    100.0),
        "intake_temp":          (-40.0,    80.0),
        "maf_rate":              (0.0,    700.0),
        "oil_temp":             (-40.0,   180.0),
        "short_term_fuel_trim": (-50.0,    50.0),
        "long_term_fuel_trim":  (-50.0,    50.0),
        "ambient_temp":         (-50.0,    70.0),
        "boost_pressure":        (0.0,    400.0),
        "fuel_rate":             (0.0,    100.0),
    }

    def __init__(self, warmup_readings: int = 10) -> None:
        """
        Args:
            warmup_readings: Number of readings to discard after connection.
                             Set to 0 to skip warm-up (e.g. in tests).
        """
        self.warmup_readings = warmup_readings
        self._reading_count: int = 0

        # Welford's online algorithm accumulators (per sensor)
        self._count:       Dict[str, int]   = {}   # readings included so far
        self._mean:        Dict[str, float] = {}   # running mean
        self._M2:          Dict[str, float] = {}   # sum of squared diffs from mean

        # Stuck sensor tracking
        self._consecutive_same: Dict[str, int]   = {}
        self._last_value:       Dict[str, float] = {}

        # Quality tracking: total and valid reading counts per sensor
        self._total_readings: Dict[str, int] = {}
        self._valid_readings: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_reading(
        self,
        reading: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Filter a single telemetry reading.

        Args:
            reading: Raw sensor dict from OBD (sensor_name → numeric value).

        Returns:
            (cleaned_reading, quality_scores)
            - cleaned_reading: sensors that passed all filters
            - quality_scores:  per-sensor float 0.0-1.0
              * empty dict  → warm-up reading, entire batch discarded
              * 0.0         → sensor rejected (out of range / stuck / outlier)
              * 1.0         → sensor passed all checks
        """
        self._reading_count += 1

        # ── Layer 1: Warm-up ──────────────────────────────────────────
        if self._reading_count <= self.warmup_readings:
            logger.debug(
                "Warm-up reading %d/%d — discarding",
                self._reading_count,
                self.warmup_readings,
            )
            return dict(reading), {}

        cleaned: Dict[str, Any]    = {}
        quality: Dict[str, float]  = {}

        for sensor, raw_value in reading.items():
            # Coerce to float; skip non-numeric sensors
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                logger.warning("Non-numeric value for %s: %r — skipping", sensor, raw_value)
                continue

            # Track total attempts for this sensor
            self._total_readings[sensor] = self._total_readings.get(sensor, 0) + 1

            # ── Layer 2: Physical range check ─────────────────────────
            range_bounds = self.PHYSICAL_RANGES.get(sensor)
            if range_bounds is not None:
                lo, hi = range_bounds
                if value < lo or value > hi:
                    logger.debug(
                        "Range violation: %s=%.2f outside [%.1f, %.1f]",
                        sensor, value, lo, hi,
                    )
                    quality[sensor] = 0.0
                    # Do NOT update rolling stats or stuck counters with bad data
                    continue

            # ── Layer 3: Stuck sensor detection ───────────────────────
            prev_same = self._consecutive_same.get(sensor, 0)
            last = self._last_value.get(sensor)
            if last is not None and last == value:
                self._consecutive_same[sensor] = prev_same + 1
            else:
                self._consecutive_same[sensor] = 0
            self._last_value[sensor] = value

            if self._consecutive_same.get(sensor, 0) >= _STUCK_THRESHOLD:
                logger.warning(
                    "Stuck sensor detected: %s stuck at %.4f for %d readings",
                    sensor, value, self._consecutive_same[sensor],
                )
                quality[sensor] = 0.0
                continue

            # If the sensor was previously stuck and just changed value,
            # skip outlier detection for this one reading — the rolling
            # stats are dominated by the stuck value, making any change
            # look like an outlier.  Range validation still protects us.
            recovering_from_stuck = prev_same >= _STUCK_THRESHOLD and self._consecutive_same[sensor] == 0

            # ── Layer 4: Statistical outlier rejection ─────────────────
            if not recovering_from_stuck and self._is_outlier(sensor, value):
                logger.debug(
                    "Outlier rejected: %s=%.4f (mean=%.4f, std=%.4f)",
                    sensor, value,
                    self._mean.get(sensor, 0),
                    self._std(sensor),
                )
                quality[sensor] = 0.0
                # Don't update rolling stats with the outlier
                continue

            # ── Passed all filters ─────────────────────────────────────
            self._update_rolling_stats(sensor, value)
            self._valid_readings[sensor] = self._valid_readings.get(sensor, 0) + 1
            cleaned[sensor] = value
            quality[sensor] = 1.0

        return cleaned, quality

    def get_sensor_quality_summary(self) -> Dict[str, float]:
        """
        Overall quality score per sensor: fraction of readings that were valid.

        Returns:
            Dict of sensor_name → quality in [0.0, 1.0].
            Empty if no readings have been processed yet.
        """
        summary: Dict[str, float] = {}
        for sensor, total in self._total_readings.items():
            if total > 0:
                valid = self._valid_readings.get(sensor, 0)
                summary[sensor] = valid / total
        return summary

    def reset(self) -> None:
        """Reset all state. Call when OBD connection is dropped/restarted."""
        self._reading_count = 0
        self._count.clear()
        self._mean.clear()
        self._M2.clear()
        self._consecutive_same.clear()
        self._last_value.clear()
        self._total_readings.clear()
        self._valid_readings.clear()
        logger.debug("DataQualityFilter reset")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_outlier(self, sensor: str, value: float) -> bool:
        """
        Returns True if *value* is more than _OUTLIER_SIGMA std-devs from the
        rolling mean.  Returns False if not enough data exists yet.
        """
        n = self._count.get(sensor, 0)
        if n < _MIN_READINGS_FOR_OUTLIER:
            return False

        std = self._std(sensor)
        if std < 1e-9:
            # Near-zero std means all previous values were identical.
            # If the new value differs, flag it unless it's within the warmup
            # tolerance.  We only flag if the absolute difference is meaningful.
            mean = self._mean.get(sensor, value)
            return abs(value - mean) > 1e-6

        mean = self._mean.get(sensor, value)
        z_score = abs(value - mean) / std
        return z_score > _OUTLIER_SIGMA

    def _std(self, sensor: str) -> float:
        """Sample standard deviation using Welford's M2 accumulator."""
        n = self._count.get(sensor, 0)
        if n < 2:
            return 0.0
        m2 = self._M2.get(sensor, 0.0)
        variance = m2 / (n - 1)
        return math.sqrt(max(variance, 0.0))

    def _update_rolling_stats(self, sensor: str, value: float) -> None:
        """Update Welford's online mean/variance for *sensor* with *value*."""
        n = self._count.get(sensor, 0) + 1
        self._count[sensor] = n

        # Welford's algorithm
        delta = value - self._mean.get(sensor, 0.0)
        self._mean[sensor] = self._mean.get(sensor, 0.0) + delta / n
        delta2 = value - self._mean[sensor]
        self._M2[sensor] = self._M2.get(sensor, 0.0) + delta * delta2
