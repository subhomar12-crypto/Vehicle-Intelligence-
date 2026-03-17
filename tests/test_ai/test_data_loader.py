"""Tests for LSTM data loader."""

import numpy as np
import pytest
from unittest.mock import MagicMock, AsyncMock

from predict.core.ai.data_loader import LSTMDataLoader, FEATURE_COLUMNS


class TestFeatureColumns:
    """Test FEATURE_COLUMNS constant."""

    def test_feature_columns_count(self):
        """Verify FEATURE_COLUMNS has exactly 15 entries."""
        assert len(FEATURE_COLUMNS) == 15

    def test_feature_columns_contents(self):
        """Verify expected columns are present."""
        expected = [
            "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
            "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
            "long_term_fuel_trim", "timing_advance", "injector_ms",
            "fuel_trim_b2", "accel_pedal", "ambient_temp",
        ]
        assert FEATURE_COLUMNS == expected


class TestReadingsToArray:
    """Test readings_to_array method."""

    def test_empty_input(self):
        """Empty input returns empty array."""
        loader = LSTMDataLoader()
        result = loader.readings_to_array([])
        assert result.shape == (0,)
        assert len(result) == 0

    def test_single_row_conversion(self):
        """Single row converts to (1, 15) array."""
        loader = LSTMDataLoader()
        
        # Create mock row with all attributes
        row = MagicMock()
        for col in FEATURE_COLUMNS:
            setattr(row, col, 100.0)
        
        result = loader.readings_to_array([row])
        assert result.shape == (1, 15)
        assert result.dtype == np.float32
        np.testing.assert_array_equal(result[0], np.full(15, 100.0, dtype=np.float32))

    def test_null_imputation_with_mean(self):
        """NaN values replaced with column mean."""
        loader = LSTMDataLoader()
        
        # Create two rows: first has NaN in first column, second has value
        row1 = MagicMock()
        row2 = MagicMock()
        
        for i, col in enumerate(FEATURE_COLUMNS):
            if i == 0:  # First column: row1=None, row2=100
                setattr(row1, col, None)
                setattr(row2, col, 100.0)
            else:
                setattr(row1, col, 50.0)
                setattr(row2, col, 50.0)
        
        result = loader.readings_to_array([row1, row2])
        # First column should be imputed with mean (100.0)
        assert result[0, 0] == 100.0
        assert result[1, 0] == 100.0

    def test_null_imputation_all_nan(self):
        """Column with all NaN becomes 0.0."""
        loader = LSTMDataLoader()
        
        row = MagicMock()
        for col in FEATURE_COLUMNS:
            setattr(row, col, None)
        
        result = loader.readings_to_array([row])
        np.testing.assert_array_equal(result[0], np.zeros(15, dtype=np.float32))


class TestCreateSequences:
    """Test create_sequences method."""

    def test_create_sequences_shape(self):
        """200 readings with window=60 → (141, 60, 15)."""
        loader = LSTMDataLoader()
        data = np.random.rand(200, 15).astype(np.float32)
        
        result = loader.create_sequences(data, window_size=60)
        
        # N - window_size + 1 = 200 - 60 + 1 = 141 sequences
        assert result.shape == (141, 60, 15)
        assert result.dtype == np.float32

    def test_insufficient_data(self):
        """Less data than window size returns empty array."""
        loader = LSTMDataLoader()
        data = np.random.rand(50, 15).astype(np.float32)
        
        result = loader.create_sequences(data, window_size=60)
        
        assert result.shape == (0,)
        assert len(result) == 0

    def test_exact_window_size(self):
        """Exactly window_size data returns (1, window, features)."""
        loader = LSTMDataLoader()
        data = np.random.rand(60, 15).astype(np.float32)
        
        result = loader.create_sequences(data, window_size=60)
        
        assert result.shape == (1, 60, 15)

    def test_sequence_content(self):
        """Sequences are proper sliding windows."""
        loader = LSTMDataLoader()
        data = np.arange(100 * 15).reshape(100, 15).astype(np.float32)
        
        result = loader.create_sequences(data, window_size=10)
        
        # First sequence should be rows 0-9
        np.testing.assert_array_equal(result[0], data[0:10])
        # Second sequence should be rows 1-10
        np.testing.assert_array_equal(result[1], data[1:11])


class TestNormalize:
    """Test normalize method."""

    def test_normalize_range(self):
        """Output values between 0 and 1."""
        loader = LSTMDataLoader()
        data = np.array([
            [0, 10, 100],
            [50, 50, 50],
            [100, 90, 0],
        ], dtype=np.float32)
        
        normalized, mins, maxs = loader.normalize(data)
        
        # Check range
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
        
        # Check specific values
        assert normalized[0, 0] == 0.0  # Min value
        assert normalized[2, 0] == 1.0  # Max value
        assert normalized[1, 0] == 0.5  # Middle value

    def test_normalize_zero_range(self):
        """Column with zero range doesn't cause division by zero."""
        loader = LSTMDataLoader()
        data = np.array([
            [50, 10],
            [50, 20],
            [50, 30],
        ], dtype=np.float32)
        
        normalized, mins, maxs = loader.normalize(data)
        
        # First column should be all zeros (no range)
        np.testing.assert_array_equal(normalized[:, 0], np.zeros(3))
        # Second column should be normalized
        assert normalized[0, 1] == 0.0
        assert normalized[2, 1] == 1.0

    def test_normalize_returns_mins_maxs(self):
        """Returns correct min and max values."""
        loader = LSTMDataLoader()
        data = np.array([
            [0, 100],
            [50, 200],
            [100, 300],
        ], dtype=np.float32)
        
        normalized, mins, maxs = loader.normalize(data)
        
        np.testing.assert_array_equal(mins, np.array([0, 100], dtype=np.float32))
        np.testing.assert_array_equal(maxs, np.array([100, 300], dtype=np.float32))


class TestLoadFromDB:
    """Test load_from_db method."""

    @pytest.mark.asyncio
    async def test_load_from_db_empty_result(self):
        """Empty DB result returns empty array."""
        loader = LSTMDataLoader()
        
        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = await loader.load_from_db(mock_session, profile_id=1)
        
        assert result.shape == (0,)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_load_from_db_with_data(self):
        """DB data converted to array correctly."""
        loader = LSTMDataLoader()
        
        # Create mock rows
        rows = []
        for i in range(5):
            row = MagicMock()
            for col in FEATURE_COLUMNS:
                setattr(row, col, float(i * 10))
            rows.append(row)
        
        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        mock_session.execute.return_value = mock_result
        
        result = await loader.load_from_db(mock_session, profile_id=1)
        
        assert result.shape == (5, 15)
        assert result.dtype == np.float32
