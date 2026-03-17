"""
Tests for predict.core.ai.weather_service — Open-Meteo weather integration.

Covers:
- Temperature fetch returns a float
- Location rounding for cache key generation
- Cache hit skips API call
- Fallback on API error
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from predict.core.ai.weather_service import WeatherService, get_weather_service


@pytest.mark.asyncio
async def test_get_current_temp_returns_float():
    """get_current_temp should return a float from the API response."""
    svc = WeatherService()

    mock_response = {"current_weather": {"temperature": 42.3}}

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock, return_value=mock_response):
        result = await svc.get_current_temp(25.3, 51.5)

    assert isinstance(result, float)
    assert result == 42.3


@pytest.mark.asyncio
async def test_location_rounding_creates_cache_key():
    """Coordinates should be rounded to 0.5 degrees for cache key.
    (25.31, 51.53) -> (25.5, 51.5)
    """
    svc = WeatherService()

    mock_response = {"current_weather": {"temperature": 38.0}}

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock, return_value=mock_response) as mock_fetch:
        await svc.get_current_temp(25.31, 51.53)

    # The API should have been called with rounded coordinates
    mock_fetch.assert_called_once_with(25.5, 51.5)


@pytest.mark.asyncio
async def test_cache_hit_skips_api_call():
    """A cached temperature should be returned without calling the API."""
    svc = WeatherService()

    # Pre-fill cache: (25.5, 51.5) -> 40.0, not expired
    cache_key = (25.5, 51.5)
    svc._cache[cache_key] = (40.0, time.time())  # fresh entry

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock) as mock_fetch:
        result = await svc.get_current_temp(25.3, 51.4)

    mock_fetch.assert_not_called()
    assert result == 40.0


@pytest.mark.asyncio
async def test_fallback_on_api_error():
    """On API failure, should return the Qatar default (35.0)."""
    svc = WeatherService()

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock, side_effect=Exception("API down")):
        result = await svc.get_current_temp(25.3, 51.5)

    assert result == 35.0


@pytest.mark.asyncio
async def test_expired_cache_calls_api():
    """An expired cache entry should trigger a fresh API call."""
    svc = WeatherService()

    # Pre-fill cache with an expired entry (31 minutes old)
    cache_key = (25.5, 51.5)
    svc._cache[cache_key] = (40.0, time.time() - 1860)

    mock_response = {"current_weather": {"temperature": 44.0}}

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock, return_value=mock_response) as mock_fetch:
        result = await svc.get_current_temp(25.3, 51.4)

    mock_fetch.assert_called_once()
    assert result == 44.0


def test_get_weather_service_returns_singleton():
    """get_weather_service() should return the same instance each call."""
    svc1 = get_weather_service()
    svc2 = get_weather_service()
    assert svc1 is svc2


@pytest.mark.asyncio
async def test_malformed_api_response_returns_fallback():
    """If API response is missing expected fields, return fallback."""
    svc = WeatherService()

    # Response missing 'current_weather' key
    mock_response = {"hourly": {"temperature": [30.0]}}

    with patch.object(svc, "_fetch_from_api", new_callable=AsyncMock, return_value=mock_response):
        result = await svc.get_current_temp(25.3, 51.5)

    assert result == 35.0
