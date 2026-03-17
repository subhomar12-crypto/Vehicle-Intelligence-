"""
Open-Meteo weather service for ambient temperature lookup.

Provides live ambient temperature for the AI scoring engine.
Qatar has extreme seasonal variation (23-50 C), so a static default
is insufficient for accurate coolant/battery health thresholds.

Features:
- Open-Meteo API (free, unlimited, no API key)
- 0.5-degree location rounding (~55 km resolution, fine for Qatar)
- 30-minute in-memory cache TTL
- Falls back to 35.0 C (Qatar annual average) on any error
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_SECONDS = 1800  # 30 minutes
QATAR_DEFAULT_TEMP = 35.0  # Fallback when API is unreachable
HTTP_TIMEOUT_SECONDS = 5.0


class WeatherService:
    """Async weather service backed by Open-Meteo with location-rounded caching."""

    def __init__(self) -> None:
        # Cache: {(rounded_lat, rounded_lon): (temperature, fetch_time)}
        self._cache: Dict[Tuple[float, float], Tuple[float, float]] = {}

    async def get_current_temp(self, latitude: float, longitude: float) -> float:
        """Return current ambient temperature in Celsius.

        Rounds coordinates to the nearest 0.5 degree for caching.
        Returns QATAR_DEFAULT_TEMP (35.0) on any failure.
        """
        rounded_lat = round(latitude * 2) / 2
        rounded_lon = round(longitude * 2) / 2
        cache_key = (rounded_lat, rounded_lon)

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            temp, fetched_at = cached
            if time.time() - fetched_at < CACHE_TTL_SECONDS:
                return temp

        # Fetch from API
        try:
            data = await self._fetch_from_api(rounded_lat, rounded_lon)
            temp = float(data["current_weather"]["temperature"])
            self._cache[cache_key] = (temp, time.time())
            return temp
        except Exception:
            logger.warning(
                "Weather API failed for (%.2f, %.2f), using default %.1f C",
                latitude,
                longitude,
                QATAR_DEFAULT_TEMP,
            )
            return QATAR_DEFAULT_TEMP

    async def _fetch_from_api(self, lat: float, lon: float) -> Dict[str, Any]:
        """Call Open-Meteo and return the parsed JSON response."""
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(
                OPEN_METEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": "true",
                },
            )
            response.raise_for_status()
            return response.json()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Return the module-level WeatherService singleton."""
    global _instance
    if _instance is None:
        _instance = WeatherService()
    return _instance
