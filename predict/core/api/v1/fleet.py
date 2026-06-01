"""
Fleet management API routes.

Handles fleet creation, driver invites, fleet-wide monitoring.
"""

import asyncio
import json
import logging
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user
from predict.core.security.hashing import generate_api_key, hash_api_key, hash_password
from predict.core.middleware.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiting
_rl = get_rate_limiter()

async def _rate_limit_accept_invite(request: Request):
    allowed, meta = await _rl.is_allowed(
        f"{_rl._get_client_ip(request)}:/fleet/accept-invite", limit=5, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many invite attempts. Try again later.")


# Pydantic models
class CreateFleetRequest(BaseModel):
    name: str
    description: Optional[str] = None


class InviteDriverRequest(BaseModel):
    fleet_id: Optional[int] = None
    driver_email: Optional[str] = None
    vehicle_ids: list = []
    vehicle_label: Optional[str] = None


class AcceptInviteRequest(BaseModel):
    invite_code: str


class JoinFleetPublicRequest(BaseModel):
    """Public fleet join — no auth required. Creates user + vehicle + accepts invite."""
    invite_code: str
    name: str
    email: str
    phone: str
    car_make: str
    car_model: str
    car_year: int
    car_plate: str
    vin: Optional[str] = None
    engine_type: Optional[str] = None
    fuel_type: Optional[str] = None
    displacement: Optional[str] = None
    transmission: Optional[str] = None
    drivetrain: Optional[str] = None
    category: Optional[str] = None


class FleetAccessRequest(BaseModel):
    company_name: str
    fleet_size: str
    message: Optional[str] = None


@router.post("/create")
async def create_fleet(
    request: CreateFleetRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Create a new fleet."""
    user_id = current_user.get("user_id")
    
    from predict.core.db.models.subscription import Fleet
    
    current_time = time.time()
    
    fleet = Fleet(
        owner_id=user_id,
        name=request.name,
        description=request.description,
        is_active=True,
        created_at=current_time,
        updated_at=current_time,
    )
    
    session.add(fleet)
    await session.flush()
    
    logger.info(f"Fleet created: {fleet.id} by user {user_id}")
    
    return {
        "status": "success",
        "fleet": {
            "id": fleet.id,
            "name": fleet.name,
            "description": fleet.description,
            "owner_id": fleet.owner_id,
            "created_at": fleet.created_at,
        },
        "timestamp": time.time(),
    }


@router.get("/my-fleets")
async def get_my_fleets(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get fleet dashboard with vehicles for the current user.

    Returns format matching Android FleetDashboardResponse:
    success, fleet_name, total_vehicles, active_now, alerts_today, vehicles[]
    """
    user_id = current_user.get("user_id")

    from predict.core.db.models.subscription import FleetInvite
    from predict.core.db.models.user import User
    from predict.core.db.models.vehicle import VehicleProfile

    # Get user info
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    owner_name = user.name if user else "Driver"

    fleet_vehicles = []

    # 1. Get user's own vehicle profiles
    vehicles_result = await session.execute(
        select(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
    )
    for v in vehicles_result.scalars().all():
        fleet_vehicles.append({
            "profile_id": v.profile_id,
            "customer_id": v.owner_user_id or 0,
            "driver_name": owner_name,
            "car_make": v.make or "",
            "car_model": v.model or "",
            "car_year": v.year,
            "car_plate": v.license_plate or "",
            "status": "idle",
            "last_speed": None,
            "location": None,
            "health_score": None,
            "last_seen": None,
            "role": "owner",
        })

    # 2. Get vehicles from fleet drivers (users who accepted this user's invites)
    invites_result = await session.execute(
        select(FleetInvite).where(
            FleetInvite.fleet_manager_id == user_id,
            FleetInvite.used_by.isnot(None),
        )
    )
    driver_ids = set()
    for invite in invites_result.scalars().all():
        if invite.used_by and invite.used_by not in driver_ids:
            driver_ids.add(invite.used_by)

    for driver_id in driver_ids:
        # Get driver info
        driver_result = await session.execute(select(User).where(User.id == driver_id))
        driver = driver_result.scalar_one_or_none()
        driver_name = driver.name if driver else "Driver"

        # Get driver's vehicles
        driver_vehicles_result = await session.execute(
            select(VehicleProfile).where(VehicleProfile.owner_user_id == driver_id)
        )
        for v in driver_vehicles_result.scalars().all():
            fleet_vehicles.append({
                "profile_id": v.profile_id,
                "customer_id": v.owner_user_id or 0,
                "driver_name": driver_name,
                "car_make": v.make or "",
                "car_model": v.model or "",
                "car_year": v.year,
                "car_plate": v.license_plate or "",
                "status": "idle",
                "last_speed": None,
                "location": None,
                "health_score": None,
                "last_seen": None,
                "role": "driver",
            })

    return {
        "success": True,
        "fleet_name": f"{owner_name}'s Fleet",
        "total_vehicles": len(fleet_vehicles),
        "active_now": 0,
        "alerts_today": 0,
        "vehicles": fleet_vehicles,
        "timestamp": time.time(),
    }


@router.post("/invite-driver")
async def invite_driver(
    request: InviteDriverRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Invite a driver to join a fleet.

    Tier restrictions:
      - Admin/Enterprise: unlimited invite codes, all grant Pro access
      - Premium: max 3 redeemed invites that grant Pro access
      - Pro/Free: cannot create invite codes
    """
    user_id = current_user.get("user_id")

    from predict.core.db.models.subscription import FleetInvite
    from predict.core.db.models.user import User

    # Check inviter's tier
    user_stmt = select(User).where(User.id == user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.tier not in ("premium", "admin", "enterprise"):
        raise HTTPException(
            status_code=403,
            detail="Only Premium and Admin users can create invite codes. Upgrade your plan to invite drivers."
        )

    # Premium users: enforce 3 redeemed-invite limit
    if user.tier == "premium":
        redeemed_count_stmt = select(func.count()).select_from(FleetInvite).where(
            FleetInvite.fleet_manager_id == user_id,
            FleetInvite.used_by.isnot(None),
        )
        redeemed_result = await session.execute(redeemed_count_stmt)
        redeemed_count = redeemed_result.scalar() or 0

        if redeemed_count >= 3:
            raise HTTPException(
                status_code=403,
                detail="You've reached the maximum of 3 invited drivers for Premium. Contact support or upgrade for more."
            )

    # Generate invite code with 192 bits of entropy
    invite_code = secrets.token_urlsafe(32)
    current_time = time.time()

    invite = FleetInvite(
        fleet_manager_id=user_id,
        invite_code=invite_code,
        created_at=current_time,
        expires_at=current_time + (24 * 3600),  # 24 hours
        is_active=True,
    )

    session.add(invite)
    await session.flush()

    # Build response with remaining count for Premium
    response = {
        "success": True,
        "invite_code": invite_code,
        "expires_at": str(invite.expires_at),
        "message": "Invite code created successfully",
        "timestamp": time.time(),
    }

    if user.tier == "premium":
        redeemed_count_stmt = select(func.count()).select_from(FleetInvite).where(
            FleetInvite.fleet_manager_id == user_id,
            FleetInvite.used_by.isnot(None),
        )
        redeemed_result = await session.execute(redeemed_count_stmt)
        redeemed_count = redeemed_result.scalar() or 0
        response["remaining_invites"] = 3 - redeemed_count

    logger.info(f"Fleet invite created: {invite.id} by user {user_id} (tier: {user.tier})")

    return response


@router.post("/accept-invite")
async def accept_invite(
    request: AcceptInviteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    _rl_guard: None = Depends(_rate_limit_accept_invite),
):
    """Accept a fleet invitation."""
    user_id = current_user.get("user_id")

    from predict.core.db.models.subscription import FleetInvite

    # Find the invite
    invite_stmt = select(FleetInvite).where(
        FleetInvite.invite_code == request.invite_code,
        FleetInvite.is_active == True,
    )
    invite_result = await session.execute(invite_stmt)
    invite = invite_result.scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=404, detail="Invite not found or already used"
        )

    # Check if expired
    if invite.expires_at and invite.expires_at < time.time():
        invite.is_active = False
        await session.flush()
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Mark invite as used
    invite.is_active = False
    invite.used_by = user_id
    invite.used_at = time.time()

    await session.flush()

    # Auto-upgrade driver to Pro if inviter is Premium/Admin
    # Premium users get 3 invite codes that auto-grant Pro to drivers
    from predict.core.db.models.user import User
    inviter_stmt = select(User).where(User.id == invite.fleet_manager_id)
    inviter_result = await session.execute(inviter_stmt)
    inviter = inviter_result.scalar_one_or_none()

    tier_upgraded = False
    if inviter and inviter.tier in ("premium", "admin", "enterprise"):
        # Upgrade the accepting driver to Pro (if they're currently free)
        driver_stmt = select(User).where(User.id == user_id)
        driver_result = await session.execute(driver_stmt)
        driver = driver_result.scalar_one_or_none()

        if driver and driver.tier == "free":
            driver.tier = "pro"
            tier_upgraded = True
            logger.info(f"Auto-upgraded user {user_id} to Pro tier via Premium invite from user {invite.fleet_manager_id}")

    await session.commit()

    logger.info(f"User {user_id} accepted fleet invite {invite.id}")

    message = "Invite accepted successfully"
    if tier_upgraded:
        message = "Invite accepted! You've been upgraded to Pro subscription."

    return {
        "success": True,
        "message": message,
        "tier_upgraded": tier_upgraded,
        "new_tier": "pro" if tier_upgraded else None,
        "timestamp": time.time(),
    }


@router.post("/join-public")
async def join_fleet_public(
    request: JoinFleetPublicRequest,
    session: AsyncSession = Depends(get_db_session),
    _rl_guard: None = Depends(_rate_limit_accept_invite),
):
    """Public fleet join endpoint — NO auth required.

    Combines: validate invite → create user → create vehicle → generate API key → mark invite used.
    Used by new drivers/family members who scan a QR code from the Guardian app.
    """
    from predict.core.db.models.subscription import FleetInvite
    from predict.core.db.models.user import User, ApiKey
    from predict.core.db.models.vehicle import VehicleProfile

    # 1. Validate invite code
    invite_stmt = select(FleetInvite).where(
        FleetInvite.invite_code == request.invite_code,
        FleetInvite.is_active == True,
    )
    invite_result = await session.execute(invite_stmt)
    invite = invite_result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite code not found or already used.")

    if invite.expires_at and invite.expires_at < time.time():
        invite.is_active = False
        await session.flush()
        raise HTTPException(status_code=400, detail="Invite code has expired.")

    # 2. Check if email already has an account
    email_lower = request.email.lower().strip()
    existing_user_stmt = select(User).where(User.email == email_lower)
    existing_result = await session.execute(existing_user_stmt)
    existing_user = existing_result.scalar_one_or_none()

    now = time.time()

    if existing_user:
        user = existing_user
        logger.info(f"join-public: existing user {user.id} ({email_lower}) joining fleet")
    else:
        # 3. Create new user (placeholder password — they'll set it later or use Google)
        placeholder_password = secrets.token_urlsafe(32)
        user = User(
            email=email_lower,
            name=request.name.strip(),
            phone=request.phone.strip(),
            password_hash=hash_password(placeholder_password),
            car_plate=request.car_plate.upper().strip(),
            tier="free",
            verified=False,
            status="active",
            registered_via="fleet_invite",
        )
        session.add(user)
        await session.flush()  # Get user.id
        logger.info(f"join-public: created new user {user.id} ({email_lower})")

    # 4. Create vehicle profile
    vehicle = VehicleProfile(
        owner_user_id=user.id,
        name=f"{request.car_make} {request.car_model}".strip() or request.car_plate,
        make=request.car_make or None,
        model=request.car_model or None,
        year=request.car_year or None,
        license_plate=request.car_plate.upper().strip(),
        engine_type=request.engine_type or None,
        fuel_type=request.fuel_type or None,
        displacement=request.displacement or None,
        transmission=request.transmission or None,
        vin=request.vin or None,
        drivetrain=request.drivetrain or None,
        category=request.category or None,
        created_at=now,
    )
    session.add(vehicle)
    await session.flush()  # Get vehicle.profile_id

    # 5. Generate API key
    plain_key = generate_api_key("pred")
    api_key = ApiKey(
        key_prefix=plain_key[:8],
        user_id=user.id,
        key_hash=hash_api_key(plain_key),
        name="Fleet Join Key",
        status="active",
        created_at=now,
        tier=user.tier,
        permissions=["vehicle_data", "diagnostic", "predict"],
        apps=["obd", "guardian"],
        profile_id=vehicle.profile_id,
    )
    session.add(api_key)

    # 5b. Create VehicleGuardian link so inviter can view this vehicle via guardian endpoints
    from predict.core.db.models.guardian import VehicleGuardian
    guardian_link = VehicleGuardian(
        profile_id=vehicle.profile_id,
        user_id=invite.fleet_manager_id,
        role="owner",
        is_active=True,
    )
    session.add(guardian_link)

    # 6. Mark invite as used
    invite.is_active = False
    invite.used_by = user.id
    invite.used_at = now

    # 7. Auto-upgrade to Pro if inviter is Premium/Admin
    tier_upgraded = False
    inviter_stmt = select(User).where(User.id == invite.fleet_manager_id)
    inviter_result = await session.execute(inviter_stmt)
    inviter = inviter_result.scalar_one_or_none()

    if inviter and inviter.tier in ("premium", "admin", "enterprise"):
        if user.tier == "free":
            user.tier = "pro"
            api_key.tier = "pro"
            tier_upgraded = True
            logger.info(
                f"join-public: auto-upgraded user {user.id} to Pro "
                f"(invited by {inviter.id}, tier={inviter.tier})"
            )

    await session.commit()

    # 8. Trigger background vehicle research if we have enough info
    if vehicle.make and vehicle.model and vehicle.year:
        try:
            from predict.core.services.vehicle_research_service import get_research_service
            service = get_research_service()
            asyncio.create_task(service.research_vehicle(vehicle.profile_id))
            logger.info(f"join-public: triggered research for vehicle {vehicle.profile_id}")
        except Exception as e:
            logger.debug(f"Research trigger failed (non-critical): {e}")

    message = "Welcome to the fleet! Your account has been created."
    if tier_upgraded:
        message = "Welcome to the fleet! Your account has been created and upgraded to Pro."

    logger.info(
        f"join-public: user {user.id} joined fleet via invite {invite.id}, "
        f"vehicle {vehicle.profile_id}, tier_upgraded={tier_upgraded}"
    )

    return {
        "success": True,
        "api_key": plain_key,
        "message": message,
        "tier": user.tier,
        "tier_upgraded": tier_upgraded,
        "user_id": user.id,
        "vehicle_id": vehicle.profile_id,
        "name": user.name,
    }


@router.get("/{fleet_id}/drivers")
async def get_fleet_drivers(
    fleet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get all drivers in a fleet."""
    user_id = current_user.get("user_id")
    
    # Verify fleet access
    from predict.core.db.models.subscription import Fleet, FleetMember
    
    fleet_stmt = select(Fleet).where(
        Fleet.id == fleet_id,
        Fleet.is_active == True,
    )
    fleet_result = await session.execute(fleet_stmt)
    fleet = fleet_result.scalar_one_or_none()
    
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")
    
    # Check if user is owner or member
    if fleet.owner_id != user_id:
        member_check = select(FleetMember).where(
            FleetMember.fleet_id == fleet_id,
            FleetMember.user_id == user_id,
            FleetMember.is_active == True,
        )
        member_result = await session.execute(member_check)
        if not member_result.scalar_one_or_none():
            raise HTTPException(
                status_code=403, detail="Not authorized to view this fleet"
            )
    
    # Get all members
    stmt = (
        select(FleetMember)
        .where(FleetMember.fleet_id == fleet_id)
        .where(FleetMember.is_active == True)
    )
    
    result = await session.execute(stmt)
    members = result.scalars().all()
    
    drivers = []
    for member in members:
        # Get user details
        from predict.core.db.models.user import User
        user_stmt = select(User).where(User.id == member.user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        drivers.append({
            "member_id": member.id,
            "user_id": member.user_id,
            "email": user.email if user else None,
            "role": member.role,
            "joined_at": member.joined_at,
        })
    
    return {
        "fleet_id": fleet_id,
        "drivers": drivers,
        "count": len(drivers),
        "timestamp": time.time(),
    }


@router.delete("/{fleet_id}/driver/{driver_id}")
async def remove_fleet_driver(
    fleet_id: int,
    driver_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Remove a driver from a fleet."""
    user_id = current_user.get("user_id")
    
    # Verify fleet ownership
    from predict.core.db.models.subscription import Fleet, FleetMember
    
    fleet_stmt = select(Fleet).where(
        Fleet.id == fleet_id,
        Fleet.owner_id == user_id,
        Fleet.is_active == True,
    )
    fleet_result = await session.execute(fleet_stmt)
    fleet = fleet_result.scalar_one_or_none()
    
    if not fleet:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this fleet"
        )
    
    # Find and deactivate member
    member_stmt = select(FleetMember).where(
        FleetMember.fleet_id == fleet_id,
        FleetMember.user_id == driver_id,
        FleetMember.is_active == True,
    )
    member_result = await session.execute(member_stmt)
    member = member_result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(status_code=404, detail="Driver not found in fleet")
    
    member.is_active = False
    member.updated_at = time.time()
    
    await session.flush()
    
    logger.info(f"Driver {driver_id} removed from fleet {fleet_id}")
    
    return {
        "status": "success",
        "fleet_id": fleet_id,
        "driver_id": driver_id,
        "timestamp": time.time(),
    }


@router.get("/{fleet_id}/stats")
async def get_fleet_stats(
    fleet_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get fleet-wide statistics."""
    user_id = current_user.get("user_id")
    
    # Verify fleet access
    from predict.core.db.models.subscription import Fleet, FleetMember
    
    fleet_stmt = select(Fleet).where(
        Fleet.id == fleet_id,
        Fleet.is_active == True,
    )
    fleet_result = await session.execute(fleet_stmt)
    fleet = fleet_result.scalar_one_or_none()
    
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")
    
    # Check access
    if fleet.owner_id != user_id:
        member_check = select(FleetMember).where(
            FleetMember.fleet_id == fleet_id,
            FleetMember.user_id == user_id,
            FleetMember.is_active == True,
        )
        member_result = await session.execute(member_check)
        if not member_result.scalar_one_or_none():
            raise HTTPException(
                status_code=403, detail="Not authorized to view this fleet"
            )
    
    # Count drivers
    driver_count_stmt = select(FleetMember).where(
        FleetMember.fleet_id == fleet_id,
        FleetMember.is_active == True,
    )
    driver_result = await session.execute(driver_count_stmt)
    members = driver_result.scalars().all()
    driver_count = len(members)

    return {
        "fleet_id": fleet_id,
        "fleet_name": fleet.name,
        "driver_count": driver_count,
        "vehicle_count": 0,
        "timestamp": time.time(),
    }


@router.post("/request-access")
async def request_fleet_access(
    request: FleetAccessRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Submit a fleet access request. Admin reviews and approves in desktop app."""
    user_id = current_user.get("user_id")

    from predict.core.db.models.subscription import TierUpgradeRequest
    from predict.core.db.models.user import User

    # Get user
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Already premium/admin — no need to request
    if user.tier in ("premium", "admin", "enterprise"):
        raise HTTPException(
            status_code=400,
            detail="You already have fleet management access.",
        )

    # Check for existing pending request
    pending_stmt = select(TierUpgradeRequest).where(
        TierUpgradeRequest.owner_id == user_id,
        TierUpgradeRequest.status == "pending",
        TierUpgradeRequest.requested_tier == "premium",
    )
    pending_result = await session.execute(pending_stmt)
    if pending_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You already have a pending fleet access request.",
        )

    current_time = time.time()
    upgrade_request = TierUpgradeRequest(
        owner_id=user_id,
        owner_name=user.name,
        owner_email=user.email,
        current_tier=user.tier,
        requested_tier="premium",
        status="pending",
        requested_at=current_time,
        company_name=request.company_name,
        fleet_size=request.fleet_size,
        notes=request.message,
    )
    session.add(upgrade_request)
    await session.flush()

    # Broadcast via WebSocket for desktop notification
    try:
        from predict.core.services.websocket_service import ws_manager
        await ws_manager.broadcast({
            "type": "FLEET_REQUEST",
            "event": "new_request",
            "request_id": upgrade_request.request_id,
            "company_name": request.company_name,
            "timestamp": time.time(),
        })
    except Exception:
        pass  # WebSocket broadcast is best-effort

    logger.info(
        f"Fleet access request {upgrade_request.request_id} created by user {user_id} "
        f"(company: {request.company_name}, fleet_size: {request.fleet_size})"
    )

    return {
        "success": True,
        "request_id": upgrade_request.request_id,
        "message": "Fleet access request submitted. We'll contact you within 24 hours.",
        "timestamp": time.time(),
    }


@router.get("/request-access/status")
async def get_fleet_request_status(
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Check the status of a user's fleet access request."""
    user_id = current_user.get("user_id")

    from predict.core.db.models.subscription import TierUpgradeRequest

    # Get the most recent fleet request
    stmt = (
        select(TierUpgradeRequest)
        .where(
            TierUpgradeRequest.owner_id == user_id,
            TierUpgradeRequest.requested_tier == "premium",
        )
        .order_by(desc(TierUpgradeRequest.requested_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    req = result.scalar_one_or_none()

    if not req:
        return {"status": "none", "request": None}

    return {
        "status": req.status,
        "request": {
            "request_id": req.request_id,
            "company_name": req.company_name,
            "fleet_size": req.fleet_size,
            "requested_at": req.requested_at,
            "processed_at": req.processed_at,
            "notes": req.notes,
        },
    }
