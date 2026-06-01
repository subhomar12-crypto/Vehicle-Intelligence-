"""LSTM training data loader — reads VehicleData rows into sliding windows."""

import numpy as np
from sqlalchemy import select, asc
from sqlalchemy.ext.asyncio import AsyncSession

FEATURE_COLUMNS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
    "long_term_fuel_trim", "timing_advance", "injector_ms",
    "fuel_trim_b2", "accel_pedal", "ambient_temp",
]


class LSTMDataLoader:
    """Load and prepare telemetry data for LSTM training."""

    async def load_from_db(self, session: AsyncSession, profile_id: int,
                           limit: int = 50000) -> np.ndarray:
        """Load VehicleData rows → (N, 15) numpy array.

        Returns raw sensor values ordered by timestamp ASC.
        NULL values are imputed with column mean (or 0.0 if all NULL).
        """
        from predict.core.db.models.vehicle import VehicleData

        result = await session.execute(
            select(VehicleData)
            .where(VehicleData.profile_id == profile_id)
            .order_by(asc(VehicleData.timestamp))
            .limit(limit)
        )
        rows = result.scalars().all()

        if not rows:
            return np.array([])

        return self.readings_to_array(rows)

    def readings_to_array(self, rows) -> np.ndarray:
        """Convert DB rows to (N, 15) array with NULL imputation."""
        data = []
        for row in rows:
            values = []
            for col in FEATURE_COLUMNS:
                val = getattr(row, col, None)
                values.append(float(val) if val is not None else np.nan)
            data.append(values)

        arr = np.array(data, dtype=np.float32)

        # Handle empty array
        if arr.size == 0:
            return arr

        # Impute NaN with column mean (or 0.0 if entire column is NaN)
        for col_idx in range(arr.shape[1]):
            col = arr[:, col_idx]
            mask = np.isnan(col)
            if mask.all():
                arr[:, col_idx] = 0.0
            elif mask.any():
                arr[mask, col_idx] = np.nanmean(col)

        return arr

    def create_sequences(self, data: np.ndarray, window_size: int = 60) -> np.ndarray:
        """Create sliding windows: (N, 15) → (N-window_size+1, window_size, 15)."""
        if len(data) < window_size:
            return np.array([])

        windows = np.lib.stride_tricks.sliding_window_view(data, (window_size, data.shape[1]))
        return windows.squeeze(axis=1).astype(np.float32, copy=False)

    def normalize(self, data: np.ndarray) -> tuple:
        """Per-column min-max normalization. Returns (normalized_data, min_vals, max_vals)."""
        mins = np.min(data, axis=0)
        maxs = np.max(data, axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1.0  # avoid division by zero

        normalized = (data - mins) / ranges
        return normalized, mins, maxs
