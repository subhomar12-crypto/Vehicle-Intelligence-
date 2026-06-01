"""Pi5 edge device registration, status, and token management."""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.pi5_device import Pi5Device

logger = logging.getLogger(__name__)

router = APIRouter()

# Device token validity: 90 days
_TOKEN_TTL = 90 * 24 * 60 * 60


class Pi5RegisterRequest(BaseModel):
    device_id: str
    vehicle_id: int
    firmware_version: Optional[str] = None


class Pi5RegisterResponse(BaseModel):
    success: bool
    device_token: str
    expires_at: float


@router.post("/register")
async def register_pi5(
    req: Pi5RegisterRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Pi5RegisterResponse:
    """Register a Pi5 device and return a device-scoped token.

    Called once during initial setup. The raw API key is used for this
    request only; subsequent uploads use the returned device_token.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    now = time.time()
    token = Pi5Device.generate_token()
    expires = now + _TOKEN_TTL

    # Upsert: update if device_id already exists
    result = await db.execute(
        select(Pi5Device).where(Pi5Device.device_id == req.device_id)
    )
    device = result.scalar_one_or_none()

    if device:
        device.vehicle_id = req.vehicle_id
        device.user_id = user_id
        device.device_token = token
        device.token_expires_at = expires
        device.firmware_version = req.firmware_version
        device.last_seen = now
    else:
        db.add(Pi5Device(
            device_id=req.device_id,
            vehicle_id=req.vehicle_id,
            user_id=user_id,
            device_token=token,
            token_expires_at=expires,
            firmware_version=req.firmware_version,
            last_seen=now,
            created_at=now,
        ))

    await db.commit()

    return Pi5RegisterResponse(
        success=True,
        device_token=token,
        expires_at=expires,
    )


@router.get("/status/{vehicle_id}")
async def get_pi5_status(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Pi5 device status for a vehicle. Used by Android app and website."""
    result = await db.execute(
        select(Pi5Device).where(Pi5Device.vehicle_id == vehicle_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="No Pi5 device linked to this vehicle")

    online = (time.time() - device.last_seen) < 300  # 5 min threshold

    return {
        "success": True,
        "device_id": device.device_id,
        "vehicle_id": device.vehicle_id,
        "online": online,
        "last_seen": device.last_seen,
        "cpu_temp": device.cpu_temp,
        "ram_used_mb": device.ram_used_mb,
        "sd_free_gb": device.sd_free_gb,
        "wifi_signal_dbm": device.wifi_signal_dbm,
        "wifi_ssid": device.wifi_ssid,
        "buffer_remaining": device.buffer_remaining,
        "odometer_km": device.odometer_km,
        "firmware_version": device.firmware_version,
    }


@router.delete("/revoke/{device_id}")
async def revoke_device_token(
    device_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a Pi5 device token. User can re-register via BLE SET_AUTH."""
    user_id = current_user.get("user_id") or current_user.get("id")
    result = await db.execute(
        select(Pi5Device).where(
            Pi5Device.device_id == device_id,
            Pi5Device.user_id == user_id,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.device_token = None
    device.token_expires_at = None
    await db.commit()

    return {"success": True, "message": "Device token revoked"}
