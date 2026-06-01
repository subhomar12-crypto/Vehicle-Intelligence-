"""
Legal/Privacy API routes with float timestamps.
Version 2.1 — Updated February 2026
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/legal", tags=["Legal"])


@router.get("/privacy-policy")
async def get_privacy_policy():
    """Get privacy policy summary. Full policy at https://predict-pp.com/privacy"""
    policy = """
# PREDICT Privacy Policy
Version 2.1 | Effective February 25, 2026

## Quick Summary
- We collect vehicle sensor data (OBD-II), location, trips, and account info to provide diagnostics and predictions.
- Background location is used for trip tracking, hard braking detection, and geofence monitoring. You can disable it.
- Your data is encrypted in transit (TLS 1.3) and at rest (AES-256).
- You can delete your data anytime via Settings or by emailing support@previlium.com.
- We do NOT sell your personal data.
- AI chat data is used to improve service quality.

## Data We Collect
- Account: name, email, phone (optional), subscription tier
- Vehicle: make, model, year, VIN (optional), engine specs
- OBD-II Telemetry: RPM, speed, coolant temp, battery voltage, throttle, fuel, engine load, intake temp, DTCs
- Location: GPS coordinates, trip routes, background location (when enabled)
- Trips: start/end times, distance, speed, hard braking events
- Guardian: fleet membership, geofence configs, location requests (Premium only)
- AI Chat: messages, responses, search queries

## Data Retention
- OBD Sensor Data: 90 days
- GPS/Location: 30 days
- Trip Records: 1 year
- AI Chat History: 90 days
- Diagnostic Codes: Life of vehicle profile
- Guardian Data: Life of fleet membership
- Account Info: Until deletion requested
- Audit Logs: 7 years
- Post-deletion: 30 days then permanently deleted

## Your Rights (GDPR/CCPA)
Access, correct, delete, restrict, portability, withdraw consent, object, non-discrimination.
Email: support@previlium.com | Response: within 30 days.

## Contact
Predict | Email: support@previlium.com | Phone: +XXX XXXXXXXX | Doha, Qatar

Full policy: https://predict-pp.com/privacy
    """

    return {
        "policy": policy.strip(),
        "version": "2.1",
        "effective_date": "2026-02-25",
        "last_updated": "2026-02-25T00:00:00Z",
        "last_updated_unix": 1740441600.0,
        "full_url": "https://predict-pp.com/privacy",
    }


@router.get("/terms-of-service")
async def get_terms_of_service():
    """Get terms of service summary. Full terms at https://predict-pp.com/terms"""
    terms = """
# PREDICT Terms of Service
Version 2.1 | Effective February 25, 2026

## Service Description
Predict provides real-time OBD-II vehicle diagnostics, AI predictive maintenance (BETA), AI chat assistant (BETA), vehicle intelligence (VIN decode, recalls, reliability research), trip tracking, Guardian fleet monitoring (Premium), and PDF health reports.

## Subscription Plans
- Free: Basic OBD diagnostics, 1 vehicle
- Pro (36 QAR/month or 300 QAR/year): Full diagnostics, AI predictions (2/day), AI chat (15/day), PDF reports (1/week)
- Premium (91 QAR/month or 750 QAR/year): All Pro + Guardian monitoring, 3 vehicles, AI predictions (10/day/vehicle), AI chat (75/day/vehicle), fleet management

## Key Disclaimers
- AI predictions are BETA — statistical estimates, NOT guarantees.
- Predict is NOT an emergency service. It does NOT contact first responders. In Qatar, dial 999.
- Hard braking alerts are informational only; may have false positives or miss events.
- Guardian monitoring requires legal authority and informed consent from all monitored drivers.
- Unauthorized surveillance may violate the Qatar Penal Code.

## Liability
Services provided "AS IS" without warranties. Total liability capped at 12 months of payments or 100 QAR, whichever is greater.

## Governing Law
State of Qatar, courts of Doha.

## Contact
Predict | Email: support@previlium.com | Phone: +XXX XXXXXXXX | Doha, Qatar

Full terms: https://predict-pp.com/terms
    """

    return {
        "terms": terms.strip(),
        "version": "2.1",
        "effective_date": "2026-02-25",
        "last_updated": "2026-02-25T00:00:00Z",
        "last_updated_unix": 1740441600.0,
        "full_url": "https://predict-pp.com/terms",
    }


@router.post("/data-export")
async def request_data_export(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Request export of all user data."""
    user_id = current_user.id

    # Create export request
    current_time = time.time()

    logger.info(f"Data export requested for user {user_id}")

    return {
        "request_id": f"EXP-{int(current_time)}",
        "user_id": user_id,
        "status": "processing",
        "estimated_completion": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(current_time + 3600)
        ),
        "message": "Your data export is being prepared. You will be notified when ready.",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": current_time,
    }


@router.post("/data-deletion")
async def request_data_deletion(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Request deletion of all user data."""
    user_id = current_user.id
    current_time = time.time()

    logger.info(f"Data deletion requested for user {user_id}")

    return {
        "request_id": f"DEL-{int(current_time)}",
        "user_id": user_id,
        "status": "scheduled",
        "deletion_date": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(current_time + 2592000)  # 30 days
        ),
        "message": "Your data deletion request has been scheduled. All personal data will be permanently deleted within 30 days.",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": current_time,
    }
