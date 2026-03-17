"""
3-stage data filtration pipeline for OBD sensor readings.

Cleans raw sensor data before it reaches AI modules (LSTM training,
XGBoost features, health scoring). Removes physically impossible values,
rate-of-change spikes from OBD glitches / Bluetooth drops, and
cross-sensor inconsistencies.

Stages:
    1. Physical bounds — reject readings with values outside known limits
    2. Spike detection — remove readings whose rate of change vs the
       previous clean reading exceeds a per-sensor threshold
    3. Consistency check — flag readings where cross-sensor relationships
       are physically impossible (e.g. speed > 20 with RPM == 0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Stage 1 — Physical bounds (min, max) per sensor
# ---------------------------------------------------------------------------

PHYSICAL_BOUNDS: Dict[str, tuple[float, float]] = {
    "rpm": (0, 9000),
    "speed": (0, 300),
    "coolant_temp": (-40, 150),
    "battery_voltage": (0, 20),
    "engine_load": (0, 100),
    "throttle_pos": (0, 100),
    "maf_rate": (0, 700),
    "intake_temp": (-40, 100),
    "short_term_fuel_trim": (-50, 50),
    "long_term_fuel_trim": (-50, 50),
    "timing_advance": (-60, 60),
    "injector_ms": (0, 30),
    "fuel_trim_b2": (0, 255),
    "accel_pedal": (0, 100),
    "ambient_temp": (-50, 65),
    "boost_pressure": (0, 400),
    "oil_temp": (-40, 200),
}

# ---------------------------------------------------------------------------
# Stage 2 — Maximum rate of change between consecutive readings
# ---------------------------------------------------------------------------

MAX_RATE_OF_CHANGE: Dict[str, float] = {
    "rpm": 3000,
    "coolant_temp": 2.0,
    "battery_voltage": 1.0,
    "speed": 30,
    "intake_temp": 3.0,
}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FilterResult:
    """Output of the filtration pipeline."""

    clean_readings: List[dict] = field(default_factory=list)
    rejected_count: int = 0
    spike_count: int = 0
    inconsistent_count: int = 0
    total_input: int = 0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class DataFiltrationPipeline:
    """Three-stage sensor data filter applied per batch."""

    # ----- public API -----

    def filter(self, batch: List[dict]) -> FilterResult:
        """Run all three stages sequentially and return a FilterResult."""
        result = FilterResult(total_input=len(batch))

        if not batch:
            return result

        # Stage 1 — physical bounds
        after_bounds: List[dict] = []
        for reading in batch:
            if self._check_bounds(reading):
                after_bounds.append(reading)
            else:
                result.rejected_count += 1

        # Stage 2 — spike detection (needs sequential context)
        after_spikes: List[dict] = []
        prev: dict | None = None
        for reading in after_bounds:
            if prev is not None and self._is_spike(prev, reading):
                result.spike_count += 1
            else:
                after_spikes.append(reading)
                prev = reading

        # Stage 3 — cross-sensor consistency
        for reading in after_spikes:
            if self._is_inconsistent(reading):
                result.inconsistent_count += 1
            else:
                result.clean_readings.append(reading)

        return result

    # ----- Stage 1 -----

    @staticmethod
    def _check_bounds(reading: dict) -> bool:
        """Return True if every present sensor value is within bounds."""
        for sensor, (lo, hi) in PHYSICAL_BOUNDS.items():
            value = reading.get(sensor)
            if value is None:
                continue
            if value < lo or value > hi:
                return False
        return True

    # ----- Stage 2 -----

    @staticmethod
    def _is_spike(prev: dict, curr: dict) -> bool:
        """Return True if any sensor in *curr* jumps beyond its rate limit."""
        for sensor, max_rate in MAX_RATE_OF_CHANGE.items():
            prev_val = prev.get(sensor)
            curr_val = curr.get(sensor)
            if prev_val is None or curr_val is None:
                continue
            if abs(curr_val - prev_val) > max_rate:
                return True
        return False

    # ----- Stage 3 -----

    @staticmethod
    def _is_inconsistent(reading: dict) -> bool:
        """Return True if cross-sensor relationships are impossible."""
        speed = reading.get("speed")
        rpm = reading.get("rpm")

        # Moving at >20 km/h with engine at 0 RPM is physically impossible
        if speed is not None and rpm is not None:
            if speed > 20 and rpm == 0:
                return True

        return False
