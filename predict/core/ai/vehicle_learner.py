"""
Per-vehicle AI that learns what 'normal' looks like for THIS specific car.

Uses the DB-backed VehicleBaseline model (not file-based).
Called as a background task after each batch_v2 upload.

Phases:
  - collecting:        < 500 data points, just accumulating stats
  - baseline_ready:    500+ points, mean/std/trends available
  - autoencoder_ready: 2000+ points, autoencoder trained, anomaly detection active

All stats are stored as JSON in the DB, not in-memory or on disk.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.vehicle import VehicleBaseline as VehicleBaselineModel
from predict.core.db.models.vehicle import VehicleData

logger = logging.getLogger(__name__)

# Sensors we track stats for
TRACKED_SENSORS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "fuel_level", "intake_temp", "maf_rate",
    "oil_temp", "short_term_fuel_trim", "long_term_fuel_trim",
    "timing_advance", "ambient_temp", "fuel_rate", "boost_pressure",
    "torque", "fuel_pressure",
]

PHASE_COLLECTING = "collecting"
PHASE_BASELINE_READY = "baseline_ready"
PHASE_AUTOENCODER_READY = "autoencoder_ready"

MIN_BASELINE_POINTS = 500
MIN_AUTOENCODER_POINTS = 2000
Z_SCORE_ANOMALY_THRESHOLD = 2.5


class VehicleLearner:
    """Per-vehicle AI that learns what 'normal' looks like for THIS specific car."""

    async def process_batch(
        self, session: AsyncSession, profile_id: int, readings: List[Dict]
    ) -> None:
        """Called after batch_v2 stores data. Runs in background."""
        if not readings:
            return

        try:
            baseline = await self._get_or_create_baseline(session, profile_id)

            # 1. Update running statistics (mean, std, min, max per sensor)
            self._update_sensor_stats(baseline, readings)

            # 2. Update weekly trend (append this week's averages)
            self._update_weekly_trends(baseline, readings)

            # 3. Increment counters
            baseline.data_points += len(readings)
            baseline.trip_count += 1
            baseline.updated_at = time.time()

            # 4. Check phase transitions
            old_phase = baseline.phase
            if baseline.data_points >= MIN_AUTOENCODER_POINTS and baseline.phase != PHASE_AUTOENCODER_READY:
                # Train autoencoder (future: use actual model weights)
                baseline.phase = PHASE_AUTOENCODER_READY
                baseline.autoencoder_trained_at = time.time()
                logger.info(
                    f"Vehicle {profile_id}: phase → autoencoder_ready "
                    f"({baseline.data_points} data points)"
                )
            elif baseline.data_points >= MIN_BASELINE_POINTS and baseline.phase == PHASE_COLLECTING:
                baseline.phase = PHASE_BASELINE_READY
                logger.info(
                    f"Vehicle {profile_id}: phase → baseline_ready "
                    f"({baseline.data_points} data points)"
                )

            await session.commit()

            if old_phase != baseline.phase:
                logger.info(f"Vehicle {profile_id} baseline phase: {old_phase} → {baseline.phase}")

            # Train per-vehicle LSTM if enough data (runs after baseline update)
            if baseline.data_points >= 100:
                try:
                    from predict.core.ai.vehicle_lstm import get_vehicle_lstm
                    vehicle_lstm = get_vehicle_lstm()
                    await vehicle_lstm.train_and_predict(session, profile_id)
                except Exception as lstm_err:
                    logger.warning(f"Per-vehicle LSTM training failed for {profile_id}: {lstm_err}")

        except Exception as e:
            logger.error(f"VehicleLearner.process_batch error for {profile_id}: {e}")
            await session.rollback()

    async def get_anomaly_scores(
        self, session: AsyncSession, profile_id: int, readings: List[Dict]
    ) -> Dict[str, Any]:
        """Run inference — detect anomalies in new data vs learned baseline."""
        result: Dict[str, Any] = {}

        try:
            baseline = await self._get_baseline(session, profile_id)
            if not baseline or baseline.phase == PHASE_COLLECTING:
                return result

            stats = self._parse_stats(baseline.sensor_stats)
            if not stats:
                return result

            # Statistical anomalies (z-score > threshold = flagged)
            if baseline.phase in (PHASE_BASELINE_READY, PHASE_AUTOENCODER_READY):
                result["statistical"] = self._detect_statistical_anomalies(stats, readings)
                result["trends"] = self._detect_trends(baseline)

            result["phase"] = baseline.phase
            result["data_points"] = baseline.data_points
            result["trip_count"] = baseline.trip_count

        except Exception as e:
            logger.error(f"VehicleLearner.get_anomaly_scores error for {profile_id}: {e}")

        return result

    async def get_baseline_info(
        self, session: AsyncSession, profile_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get baseline summary for a vehicle (used by health-assessment endpoint)."""
        baseline = await self._get_baseline(session, profile_id)
        if not baseline:
            return None

        stats = self._parse_stats(baseline.sensor_stats)
        trends = self._parse_trends(baseline.weekly_trends)

        return {
            "phase": baseline.phase,
            "data_points": baseline.data_points,
            "trip_count": baseline.trip_count,
            "sensor_stats": stats,
            "weekly_trends": trends,
            "updated_at": baseline.updated_at,
        }

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_or_create_baseline(
        self, session: AsyncSession, profile_id: int
    ) -> VehicleBaselineModel:
        """Get existing baseline or create a new one."""
        stmt = select(VehicleBaselineModel).where(
            VehicleBaselineModel.profile_id == profile_id
        )
        result = await session.execute(stmt)
        baseline = result.scalar_one_or_none()

        if baseline is None:
            now = time.time()
            baseline = VehicleBaselineModel(
                profile_id=profile_id,
                trip_count=0,
                data_points=0,
                sensor_stats=None,
                weekly_trends=None,
                phase=PHASE_COLLECTING,
                created_at=now,
                updated_at=now,
            )
            session.add(baseline)
            await session.flush()

            # Try backfill from existing historical data
            await self._try_backfill(session, baseline, profile_id)

        return baseline

    async def _get_baseline(
        self, session: AsyncSession, profile_id: int
    ) -> Optional[VehicleBaselineModel]:
        """Get existing baseline or None."""
        stmt = select(VehicleBaselineModel).where(
            VehicleBaselineModel.profile_id == profile_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _try_backfill(
        self, session: AsyncSession, baseline: VehicleBaselineModel, profile_id: int
    ) -> None:
        """On first baseline creation, backfill from existing VehicleData records."""
        try:
            stmt = (
                select(VehicleData)
                .where(VehicleData.profile_id == profile_id)
                .order_by(VehicleData.timestamp.desc())
                .limit(5000)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            if len(rows) < 50:
                return

            # Convert DB rows to sensor dicts
            readings = []
            for row in rows:
                sensors: Dict[str, float] = {}
                for sensor in TRACKED_SENSORS:
                    val = getattr(row, sensor, None)
                    if val is not None:
                        sensors[sensor] = float(val)
                if sensors:
                    readings.append(sensors)

            if len(readings) < 50:
                return

            self._update_sensor_stats(baseline, readings)
            baseline.data_points = len(readings)
            baseline.trip_count = 0  # unknown

            if baseline.data_points >= MIN_AUTOENCODER_POINTS:
                baseline.phase = PHASE_AUTOENCODER_READY
                baseline.autoencoder_trained_at = time.time()
            elif baseline.data_points >= MIN_BASELINE_POINTS:
                baseline.phase = PHASE_BASELINE_READY

            logger.info(
                f"Backfilled baseline for vehicle {profile_id} "
                f"from {len(readings)} historical records → phase={baseline.phase}"
            )
        except Exception as e:
            logger.warning(f"Backfill failed for {profile_id}: {e}")

    def _update_sensor_stats(
        self, baseline: VehicleBaselineModel, readings: List[Dict]
    ) -> None:
        """Update running statistics from new readings using Welford's algorithm."""
        stats = self._parse_stats(baseline.sensor_stats)

        for reading in readings:
            sensors = reading.get("sensors", reading)  # handle both formats
            for sensor in TRACKED_SENSORS:
                val = sensors.get(sensor)
                if val is None:
                    continue
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    continue

                if sensor not in stats:
                    stats[sensor] = {
                        "count": 0,
                        "mean": 0.0,
                        "m2": 0.0,
                        "min": val,
                        "max": val,
                    }

                s = stats[sensor]
                s["count"] += 1
                delta = val - s["mean"]
                s["mean"] += delta / s["count"]
                delta2 = val - s["mean"]
                s["m2"] += delta * delta2
                s["min"] = min(s["min"], val)
                s["max"] = max(s["max"], val)

        baseline.sensor_stats = json.dumps(stats)

    def _update_weekly_trends(
        self, baseline: VehicleBaselineModel, readings: List[Dict]
    ) -> None:
        """Append this batch's averages to weekly trend data."""
        if not readings:
            return

        trends = self._parse_trends(baseline.weekly_trends)

        # Compute averages for this batch
        sensor_sums: Dict[str, List[float]] = {}
        for reading in readings:
            sensors = reading.get("sensors", reading)
            for sensor in TRACKED_SENSORS:
                val = sensors.get(sensor)
                if val is not None:
                    sensor_sums.setdefault(sensor, []).append(float(val))

        for sensor, values in sensor_sums.items():
            avg = sum(values) / len(values)
            if sensor not in trends:
                trends[sensor] = []
            trends[sensor].append(round(avg, 2))
            # Keep last 52 weeks of trend data
            if len(trends[sensor]) > 52:
                trends[sensor] = trends[sensor][-52:]

        baseline.weekly_trends = json.dumps(trends)

    def _detect_statistical_anomalies(
        self, stats: Dict[str, Dict], readings: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Find sensors where current values deviate significantly from baseline."""
        anomalies = []

        # Aggregate current readings
        sensor_values: Dict[str, List[float]] = {}
        for reading in readings:
            sensors = reading.get("sensors", reading)
            for sensor, val in sensors.items():
                if val is not None and sensor in stats:
                    sensor_values.setdefault(sensor, []).append(float(val))

        for sensor, values in sensor_values.items():
            if sensor not in stats:
                continue
            s = stats[sensor]
            count = s.get("count", 0)
            if count < 30:
                continue

            mean = s["mean"]
            variance = s["m2"] / count if count > 0 else 0
            std = variance ** 0.5 if variance > 0 else 0

            if std == 0:
                continue

            current_mean = sum(values) / len(values)
            z_score = abs(current_mean - mean) / std

            if z_score > Z_SCORE_ANOMALY_THRESHOLD:
                direction = "above" if current_mean > mean else "below"
                anomalies.append({
                    "sensor": sensor,
                    "z_score": round(z_score, 2),
                    "current": round(current_mean, 2),
                    "baseline_mean": round(mean, 2),
                    "baseline_std": round(std, 2),
                    "direction": direction,
                })

        return anomalies

    def _detect_trends(
        self, baseline: VehicleBaselineModel
    ) -> List[Dict[str, Any]]:
        """Detect upward/downward trends in weekly data."""
        trends_data = self._parse_trends(baseline.weekly_trends)
        detected = []

        for sensor, weekly_avgs in trends_data.items():
            if len(weekly_avgs) < 4:
                continue

            recent = weekly_avgs[-4:]
            # Simple linear regression on last 4 data points
            x = np.arange(len(recent), dtype=float)
            y = np.array(recent, dtype=float)
            if np.std(y) == 0:
                continue

            slope = np.polyfit(x, y, 1)[0]
            avg_val = np.mean(y)

            # Only flag if slope is significant relative to value
            if avg_val != 0 and abs(slope / avg_val) > 0.01:  # > 1% per data point
                direction = "trending_up" if slope > 0 else "trending_down"
                detected.append({
                    "sensor": sensor,
                    "direction": direction,
                    "slope_per_week": round(float(slope), 3),
                    "recent_avg": round(float(avg_val), 2),
                    "data_points": len(weekly_avgs),
                })

        return detected

    def _parse_stats(self, json_str: Optional[str]) -> Dict[str, Dict]:
        """Parse sensor_stats JSON, return empty dict on error."""
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _parse_trends(self, json_str: Optional[str]) -> Dict[str, List[float]]:
        """Parse weekly_trends JSON, return empty dict on error."""
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}
