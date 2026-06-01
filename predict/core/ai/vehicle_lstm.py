"""
Per-vehicle LSTM-like sequential predictor.

Each registered vehicle gets its own model that:
  1. Reads from the last 14 days (2 weeks) of OBD sensor data
  2. Learns that vehicle's personal patterns via rolling statistics + trend extrapolation
  3. Produces per-component health predictions that feed into the main UnifiedAI brain

This is NOT a heavy TensorFlow LSTM — it's a lightweight numpy-based time-series
model that approximates LSTM behavior (memory of sequences, trend detection,
anomaly scoring) without GPU requirements.

Storage: predictions cached in VehicleBaseline.sensor_stats JSON under "_lstm_predictions" key.
Training trigger: called after batch_v2 upload (via VehicleLearner) or on-demand.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.vehicle import VehicleBaseline, VehicleData

logger = logging.getLogger(__name__)

# 2-week training window
TRAINING_WINDOW_DAYS = 14
MIN_TRAINING_POINTS = 100  # Need at least 100 readings in 2 weeks

# Sensors the per-vehicle LSTM tracks
LSTM_SENSORS = [
    "battery_voltage", "coolant_temp", "engine_load", "rpm",
    "intake_temp", "maf_rate", "throttle_pos", "fuel_level",
    "short_term_fuel_trim", "long_term_fuel_trim",
]

# Component-to-sensor mapping (which sensors predict which component health)
COMPONENT_SENSORS = {
    "battery": ["battery_voltage"],
    "alternator": ["battery_voltage", "engine_load"],
    "coolant": ["coolant_temp", "intake_temp"],
    "engine": ["rpm", "engine_load", "maf_rate"],
    "fuel_system": ["fuel_level", "short_term_fuel_trim", "long_term_fuel_trim"],
    "o2_sensor": ["short_term_fuel_trim", "long_term_fuel_trim"],
    "catalytic_converter": ["short_term_fuel_trim", "long_term_fuel_trim"],
    "thermostat": ["coolant_temp"],
    "transmission_fluid": ["rpm", "throttle_pos"],
    "brakes": ["speed"],
}

# Normal operating ranges (Qatar climate adjusted)
NORMAL_RANGES = {
    "battery_voltage": (12.4, 14.8),
    "coolant_temp": (85, 105),   # Qatar hot climate
    "engine_load": (15, 85),
    "rpm": (650, 6500),
    "intake_temp": (20, 65),     # Qatar: higher normal
    "maf_rate": (2, 250),
    "throttle_pos": (10, 90),
    "fuel_level": (10, 100),
    "short_term_fuel_trim": (-15, 15),
    "long_term_fuel_trim": (-15, 15),
}


class VehicleLSTM:
    """
    Per-vehicle sequential predictor.

    Mimics LSTM behavior using:
    - Rolling window statistics (mean, std, trend slope) per sensor
    - Exponential weighted moving average (EWMA) for recent emphasis
    - Linear regression for trend projection
    - Z-score anomaly detection against the vehicle's own baseline
    - Component health scoring based on sensor degradation patterns
    """

    async def train_and_predict(
        self, session: AsyncSession, profile_id: int
    ) -> Dict[str, Any]:
        """
        Train on 2 weeks of data and produce per-component predictions.

        Returns:
            {
                "trained_at": float,
                "data_points": int,
                "training_window_days": 14,
                "component_predictions": {
                    "battery": {"health_pct": 85, "trend": "stable", "days_to_warning": 45, "confidence": 0.7},
                    ...
                },
                "sensor_analysis": {
                    "battery_voltage": {"mean": 13.2, "std": 0.3, "trend_slope": -0.01, "ewma": 13.1, ...},
                    ...
                },
                "anomalies": [{"sensor": "coolant_temp", "severity": "warning", ...}],
            }
        """
        # 1. Fetch 2 weeks of data
        cutoff_ts = time.time() - (TRAINING_WINDOW_DAYS * 86400)
        stmt = (
            select(VehicleData)
            .where(
                VehicleData.profile_id == profile_id,
                VehicleData.timestamp >= cutoff_ts,
            )
            .order_by(VehicleData.timestamp.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()

        if len(rows) < MIN_TRAINING_POINTS:
            logger.info(
                f"Vehicle LSTM {profile_id}: only {len(rows)} points "
                f"(need {MIN_TRAINING_POINTS}), skipping"
            )
            return {"trained": False, "data_points": len(rows), "reason": "insufficient_data"}

        # 2. Convert to numpy arrays per sensor
        sensor_data = self._extract_sensor_series(rows)

        # 3. Per-sensor analysis (LSTM-like sequence learning)
        sensor_analysis = {}
        for sensor, values in sensor_data.items():
            if len(values) < 10:
                continue
            sensor_analysis[sensor] = self._analyze_sensor(sensor, values)

        # 4. Component health predictions
        component_predictions = {}
        for comp_id, comp_sensors in COMPONENT_SENSORS.items():
            comp_analysis = {s: sensor_analysis[s] for s in comp_sensors if s in sensor_analysis}
            if comp_analysis:
                component_predictions[comp_id] = self._predict_component(
                    comp_id, comp_analysis
                )

        # 5. Anomaly detection
        anomalies = self._detect_anomalies(sensor_analysis)

        result = {
            "trained": True,
            "trained_at": time.time(),
            "data_points": len(rows),
            "training_window_days": TRAINING_WINDOW_DAYS,
            "component_predictions": component_predictions,
            "sensor_analysis": {k: self._serialize_analysis(v) for k, v in sensor_analysis.items()},
            "anomalies": anomalies,
        }

        # 6. Cache predictions in VehicleBaseline
        await self._cache_predictions(session, profile_id, result)

        logger.info(
            f"Vehicle LSTM {profile_id}: trained on {len(rows)} points, "
            f"{len(component_predictions)} components predicted, "
            f"{len(anomalies)} anomalies found"
        )
        return result

    async def get_cached_predictions(
        self, session: AsyncSession, profile_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached per-vehicle LSTM predictions from the baseline DB."""
        stmt = select(VehicleBaseline).where(VehicleBaseline.profile_id == profile_id)
        baseline = (await session.execute(stmt)).scalar_one_or_none()
        if not baseline or not baseline.sensor_stats:
            return None

        try:
            stats = json.loads(baseline.sensor_stats)
            preds = stats.get("_lstm_predictions")
            if preds and isinstance(preds, dict) and preds.get("trained"):
                return preds
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    # ── Sensor Analysis (LSTM-like sequence learning) ──

    def _extract_sensor_series(self, rows) -> Dict[str, np.ndarray]:
        """Convert DB rows to per-sensor numpy arrays."""
        series: Dict[str, List[float]] = {}
        for row in rows:
            for sensor in LSTM_SENSORS:
                val = getattr(row, sensor, None)
                if val is not None:
                    series.setdefault(sensor, []).append(float(val))
        return {k: np.array(v) for k, v in series.items()}

    def _analyze_sensor(self, sensor: str, values: np.ndarray) -> Dict[str, Any]:
        """Full time-series analysis for one sensor."""
        n = len(values)

        # Basic stats
        mean = float(np.mean(values))
        std = float(np.std(values))
        median = float(np.median(values))

        # Exponential weighted moving average (recent data matters more)
        alpha = 0.1
        ewma = values[0]
        for v in values[1:]:
            ewma = alpha * v + (1 - alpha) * ewma
        ewma = float(ewma)

        # Linear regression for trend
        x = np.arange(n, dtype=float)
        if std > 0 and n >= 10:
            coeffs = np.polyfit(x, values, 1)
            slope = float(coeffs[0])
            # R² for fit quality
            predicted = np.polyval(coeffs, x)
            ss_res = np.sum((values - predicted) ** 2)
            ss_tot = np.sum((values - mean) ** 2)
            r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0
        else:
            slope = 0.0
            r_squared = 0.0

        # Volatility (coefficient of variation)
        volatility = (std / abs(mean)) if mean != 0 else 0.0

        # Recent vs historical comparison
        recent_window = min(n // 4, 50)
        recent_mean = float(np.mean(values[-recent_window:])) if recent_window > 0 else mean
        historical_mean = float(np.mean(values[:-recent_window])) if n > recent_window else mean

        # Rate of change (slope per day, assuming ~1 reading per minute avg)
        readings_per_day = max(n / TRAINING_WINDOW_DAYS, 1)
        slope_per_day = slope * readings_per_day

        # Normal range check
        normal = NORMAL_RANGES.get(sensor, (float('-inf'), float('inf')))
        in_range = normal[0] <= ewma <= normal[1]
        range_position = 0.0
        if normal[1] != normal[0]:
            range_position = (ewma - normal[0]) / (normal[1] - normal[0])

        return {
            "mean": mean, "std": std, "median": median,
            "ewma": ewma, "slope": slope, "slope_per_day": slope_per_day,
            "r_squared": r_squared, "volatility": volatility,
            "recent_mean": recent_mean, "historical_mean": historical_mean,
            "in_range": in_range, "range_position": range_position,
            "min": float(np.min(values)), "max": float(np.max(values)),
            "count": n, "normal_range": normal,
        }

    # ── Component Health Prediction ──

    def _predict_component(
        self, comp_id: str, sensor_analyses: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Predict component health from its sensor analyses."""
        health_factors = []
        trend_directions = []
        confidence_factors = []

        for sensor, analysis in sensor_analyses.items():
            # Health factor: how well is the sensor in normal range?
            if analysis["in_range"]:
                # In range — score based on how centered
                pos = analysis["range_position"]
                # Best at center (0.5), worse at edges
                health = 100 - abs(pos - 0.5) * 60
            else:
                # Out of range — penalize based on how far out
                pos = analysis["range_position"]
                if pos < 0:
                    health = max(0, 40 + pos * 40)  # below range
                else:
                    health = max(0, 40 - (pos - 1) * 40)  # above range
            health_factors.append(health)

            # Trend: is the sensor getting worse?
            slope = analysis["slope_per_day"]
            normal = analysis["normal_range"]
            mid = (normal[0] + normal[1]) / 2
            ewma = analysis["ewma"]

            if ewma > mid:
                # Above center — rising is bad
                if slope > 0:
                    trend_directions.append("degrading")
                elif slope < -0.001:
                    trend_directions.append("improving")
                else:
                    trend_directions.append("stable")
            else:
                # Below center — dropping is bad
                if slope < 0:
                    trend_directions.append("degrading")
                elif slope > 0.001:
                    trend_directions.append("improving")
                else:
                    trend_directions.append("stable")

            # Confidence: more data + better R² = more confident
            data_conf = min(analysis["count"] / 500, 1.0) * 0.5
            fit_conf = max(analysis["r_squared"], 0) * 0.3
            range_conf = 0.2 if analysis["in_range"] else 0.1
            confidence_factors.append(data_conf + fit_conf + range_conf)

        if not health_factors:
            return {"health_pct": 50, "trend": "unknown", "confidence": 0.0, "days_to_warning": None}

        health_pct = int(np.mean(health_factors))
        confidence = float(np.mean(confidence_factors))

        # Overall trend
        degrading_count = trend_directions.count("degrading")
        improving_count = trend_directions.count("improving")
        if degrading_count > improving_count:
            trend = "declining"
        elif improving_count > degrading_count:
            trend = "improving"
        else:
            trend = "stable"

        # Days to warning estimate (extrapolate from slope)
        days_to_warning = None
        for sensor, analysis in sensor_analyses.items():
            if analysis["slope_per_day"] != 0 and analysis["in_range"]:
                normal = analysis["normal_range"]
                ewma = analysis["ewma"]
                # How many days until out of range?
                if analysis["slope_per_day"] > 0:
                    days = (normal[1] - ewma) / analysis["slope_per_day"]
                else:
                    days = (normal[0] - ewma) / analysis["slope_per_day"]
                if days > 0:
                    if days_to_warning is None or days < days_to_warning:
                        days_to_warning = int(days)

        return {
            "health_pct": max(0, min(100, health_pct)),
            "trend": trend,
            "confidence": round(confidence, 2),
            "days_to_warning": days_to_warning,
        }

    # ── Anomaly Detection ──

    def _detect_anomalies(self, sensor_analysis: Dict[str, Dict]) -> List[Dict]:
        """Detect anomalies based on the vehicle's own learned patterns."""
        anomalies = []
        for sensor, analysis in sensor_analysis.items():
            # Recent mean vs historical mean divergence
            if analysis["std"] > 0:
                z_score = abs(analysis["recent_mean"] - analysis["historical_mean"]) / analysis["std"]
                if z_score > 2.0:
                    severity = "critical" if z_score > 3.5 else "warning" if z_score > 2.5 else "info"
                    direction = "rising" if analysis["recent_mean"] > analysis["historical_mean"] else "falling"
                    anomalies.append({
                        "sensor": sensor,
                        "severity": severity,
                        "z_score": round(z_score, 2),
                        "direction": direction,
                        "recent": round(analysis["recent_mean"], 2),
                        "baseline": round(analysis["historical_mean"], 2),
                    })

            # High volatility
            if analysis["volatility"] > 0.3:
                anomalies.append({
                    "sensor": sensor,
                    "severity": "warning",
                    "type": "high_volatility",
                    "volatility": round(analysis["volatility"], 3),
                })

        return anomalies

    # ── Caching ──

    async def _cache_predictions(
        self, session: AsyncSession, profile_id: int, predictions: Dict
    ) -> None:
        """Store LSTM predictions in VehicleBaseline.sensor_stats under _lstm_predictions key."""
        try:
            stmt = select(VehicleBaseline).where(VehicleBaseline.profile_id == profile_id)
            baseline = (await session.execute(stmt)).scalar_one_or_none()
            if not baseline:
                return

            stats = {}
            if baseline.sensor_stats:
                try:
                    stats = json.loads(baseline.sensor_stats)
                except (json.JSONDecodeError, TypeError):
                    stats = {}

            # Serialize for JSON storage (remove numpy types)
            serializable = json.loads(json.dumps(predictions, default=str))
            stats["_lstm_predictions"] = serializable
            baseline.sensor_stats = json.dumps(stats)
            baseline.updated_at = time.time()
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to cache LSTM predictions for {profile_id}: {e}")
            await session.rollback()

    def _serialize_analysis(self, analysis: Dict) -> Dict:
        """Convert analysis to JSON-serializable format."""
        result = {}
        for k, v in analysis.items():
            if isinstance(v, (np.integer, np.int64)):
                result[k] = int(v)
            elif isinstance(v, (np.floating, np.float64)):
                result[k] = round(float(v), 4)
            elif isinstance(v, tuple):
                result[k] = list(v)
            else:
                result[k] = v
        return result


# Singleton
_vehicle_lstm: Optional[VehicleLSTM] = None

def get_vehicle_lstm() -> VehicleLSTM:
    global _vehicle_lstm
    if _vehicle_lstm is None:
        _vehicle_lstm = VehicleLSTM()
    return _vehicle_lstm
