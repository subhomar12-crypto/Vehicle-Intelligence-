"""Tests for critical anomaly push notification logic.

Tests the pure-logic helpers in predictions.py:
- Hash computation determinism
- Deduplication (same hash skips)
- Rate limiting (count >= 3 blocks)
- Date reset logic
- Graceful handling when firebase-admin is missing

No DB, no Firebase, no network calls.
"""

import hashlib
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import the functions under test
# ---------------------------------------------------------------------------

from predict.core.api.v1.predictions import (
    _compute_anomaly_hash,
    _extract_critical_findings,
    _maybe_send_anomaly_notification,
)


# ===== _compute_anomaly_hash =====


class TestComputeAnomalyHash:
    def test_deterministic_same_input(self):
        """Same input produces the same hash every time."""
        items = [
            {"component": "battery", "severity": "critical", "anomaly_score": 0.9},
            {"component": "coolant", "severity": "critical", "anomaly_score": 0.8},
        ]
        h1 = _compute_anomaly_hash(items)
        h2 = _compute_anomaly_hash(items)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_deterministic_different_order(self):
        """Order of items does not affect the hash (sorted internally)."""
        items_a = [
            {"component": "coolant", "severity": "critical"},
            {"component": "battery", "severity": "critical"},
        ]
        items_b = [
            {"component": "battery", "severity": "critical"},
            {"component": "coolant", "severity": "critical"},
        ]
        assert _compute_anomaly_hash(items_a) == _compute_anomaly_hash(items_b)

    def test_different_components_different_hash(self):
        """Different component sets produce different hashes."""
        items_a = [{"component": "battery", "severity": "critical"}]
        items_b = [{"component": "oil_temp", "severity": "critical"}]
        assert _compute_anomaly_hash(items_a) != _compute_anomaly_hash(items_b)

    def test_empty_list(self):
        """Empty input produces a valid (but specific) hash."""
        h = _compute_anomaly_hash([])
        assert isinstance(h, str)
        assert len(h) == 64

    def test_uses_sensor_fallback_key(self):
        """Items with 'sensor' key instead of 'component' still work."""
        items = [{"sensor": "intake_temp", "severity": "critical"}]
        h = _compute_anomaly_hash(items)
        assert len(h) == 64

    def test_uses_pattern_fallback_key(self):
        """Items with 'pattern' key instead of 'component' still work."""
        items = [{"pattern": "rapid_coolant_rise", "severity": "critical"}]
        h = _compute_anomaly_hash(items)
        assert len(h) == 64


# ===== _extract_critical_findings =====


class TestExtractCriticalFindings:
    def test_extracts_critical_anomaly_alerts(self):
        """Critical anomaly alerts with score > 0.7 are extracted."""
        result = {
            "anomaly_alerts": [
                {"component": "battery", "severity": "critical", "anomaly_score": 0.9},
                {"component": "coolant", "severity": "warning", "anomaly_score": 0.8},
                {"component": "oil", "severity": "critical", "anomaly_score": 0.5},  # score too low
            ],
            "detected_patterns": [],
        }
        findings = _extract_critical_findings(result)
        assert len(findings) == 1
        assert findings[0]["component"] == "battery"

    def test_extracts_critical_patterns(self):
        """Critical detected_patterns are extracted."""
        result = {
            "anomaly_alerts": [],
            "detected_patterns": [
                {"pattern": "rapid_coolant_rise", "severity": "critical"},
                {"pattern": "minor_vibration", "severity": "info"},
            ],
        }
        findings = _extract_critical_findings(result)
        assert len(findings) == 1
        assert findings[0]["pattern"] == "rapid_coolant_rise"

    def test_combines_alerts_and_patterns(self):
        """Both anomaly_alerts and detected_patterns are combined."""
        result = {
            "anomaly_alerts": [
                {"component": "battery", "severity": "critical", "anomaly_score": 0.95},
            ],
            "detected_patterns": [
                {"pattern": "overheating", "severity": "critical"},
            ],
        }
        findings = _extract_critical_findings(result)
        assert len(findings) == 2

    def test_empty_result(self):
        """No alerts and no patterns returns empty list."""
        assert _extract_critical_findings({}) == []
        assert _extract_critical_findings({"anomaly_alerts": None, "detected_patterns": None}) == []

    def test_non_dict_items_skipped(self):
        """Non-dict items in lists are ignored."""
        result = {
            "anomaly_alerts": ["not_a_dict", 42, None],
            "detected_patterns": [None],
        }
        assert _extract_critical_findings(result) == []


# ===== _maybe_send_anomaly_notification =====


def _make_profile(
    *,
    last_hash=None,
    count=0,
    reset_date=None,
):
    """Create a mock VehicleProfile with notification fields."""
    p = MagicMock()
    p.last_notification_hash = last_hash
    p.notification_count_today = count
    p.notification_reset_date = reset_date
    return p


def _make_session(profile):
    """Create a mock AsyncSession that returns the given profile."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = profile
    session.execute.return_value = result_mock
    session.flush = AsyncMock()
    return session


@pytest.fixture
def critical_result():
    """A pipeline result dict with one critical anomaly alert."""
    return {
        "anomaly_alerts": [
            {"component": "battery", "severity": "critical", "anomaly_score": 0.95},
        ],
        "detected_patterns": [],
    }


@pytest.fixture
def no_critical_result():
    """A pipeline result dict with no critical findings."""
    return {
        "anomaly_alerts": [
            {"component": "battery", "severity": "warning", "anomaly_score": 0.3},
        ],
        "detected_patterns": [],
    }


class TestMaybeSendAnomalyNotification:
    @pytest.mark.asyncio
    async def test_no_critical_findings_skips(self, no_critical_result):
        """When there are no critical findings, nothing happens."""
        session = AsyncMock()
        await _maybe_send_anomaly_notification(session, 1, no_critical_result, None)
        # execute should never be called (early return before DB query)
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_hash_skips(self, critical_result):
        """When the hash matches last_notification_hash, notification is skipped."""
        critical_items = _extract_critical_findings(critical_result)
        current_hash = _compute_anomaly_hash(critical_items)
        profile = _make_profile(last_hash=current_hash, count=0, reset_date=date.today().isoformat())
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        # flush should NOT be called — we skipped
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_blocks(self, critical_result):
        """When count >= 3 today, notification is blocked."""
        profile = _make_profile(last_hash="old_hash", count=3, reset_date=date.today().isoformat())
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        # flush should NOT be called — rate limited
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_date_reset_resets_count(self, critical_result):
        """When reset_date is yesterday, count resets to 0 and notification proceeds."""
        profile = _make_profile(last_hash="old_hash", count=5, reset_date="2020-01-01")
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        # Should have updated the profile and flushed
        assert profile.notification_count_today == 1
        assert profile.notification_reset_date == date.today().isoformat()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_hash_and_count(self, critical_result):
        """After sending, hash, count, and date are updated."""
        profile = _make_profile(last_hash=None, count=0, reset_date=date.today().isoformat())
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        critical_items = _extract_critical_findings(critical_result)
        expected_hash = _compute_anomaly_hash(critical_items)

        assert profile.last_notification_hash == expected_hash
        assert profile.notification_count_today == 1
        assert profile.notification_reset_date == date.today().isoformat()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_firebase_admin_no_crash(self, critical_result):
        """If firebase_admin is not installed, notification is skipped gracefully."""
        profile = _make_profile(last_hash=None, count=0, reset_date=date.today().isoformat())
        session = _make_session(profile)

        # Ensure firebase_admin.messaging import fails
        with patch.dict(sys.modules, {"firebase_admin": None, "firebase_admin.messaging": None}):
            await _maybe_send_anomaly_notification(session, 1, critical_result, "fake_token_123")

        # Should still update hash/count even when Firebase send is skipped
        assert profile.last_notification_hash is not None
        assert profile.notification_count_today == 1
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_firebase_send_error_no_crash(self, critical_result):
        """If Firebase send() raises, the error is caught and state is still updated."""
        profile = _make_profile(last_hash=None, count=0, reset_date=date.today().isoformat())
        session = _make_session(profile)

        mock_messaging = MagicMock()
        mock_messaging.send.side_effect = RuntimeError("FCM unavailable")
        mock_messaging.Message = MagicMock()
        mock_messaging.Notification = MagicMock()

        with patch.dict(sys.modules, {"firebase_admin.messaging": mock_messaging}):
            await _maybe_send_anomaly_notification(session, 1, critical_result, "fake_token_123")

        # State still updated despite send failure
        assert profile.last_notification_hash is not None
        assert profile.notification_count_today == 1
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_fcm_token_still_updates_state(self, critical_result):
        """When fcm_token is None, no send attempt but state is still updated."""
        profile = _make_profile(last_hash=None, count=0, reset_date=date.today().isoformat())
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        assert profile.last_notification_hash is not None
        assert profile.notification_count_today == 1
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_profile_not_found_skips(self, critical_result):
        """If vehicle profile doesn't exist, notification is silently skipped."""
        session = _make_session(None)  # No profile found

        # Should not raise
        await _maybe_send_anomaly_notification(session, 999, critical_result, None)
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_increments_from_existing(self, critical_result):
        """Count increments from existing value when same day."""
        today = date.today().isoformat()
        profile = _make_profile(last_hash="different_hash", count=2, reset_date=today)
        session = _make_session(profile)

        await _maybe_send_anomaly_notification(session, 1, critical_result, None)

        assert profile.notification_count_today == 3
        session.flush.assert_awaited_once()
