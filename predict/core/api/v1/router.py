"""
Master API router for v1.

Includes all sub-routers:
- health: Health checks
- auth: Authentication (register, login, verify)
- profiles: User profiles
- vehicle_data: OBD and telemetry
- predictions: AI predictions
- dtc: Diagnostic trouble codes
- guardian: Parental monitoring
- fleet: Fleet management
- billing: Payments and subscriptions
- reports: PDF reports and analytics
- admin: Admin operations
- ai_chat: LLM chat
- websockets: Real-time connections
- legal: GDPR and privacy
- dashboard: Desktop metrics
- driving: Driver behavior
- tiers: Subscription tiers
- app_version: Mobile app updates
"""

from fastapi import APIRouter

from predict.core.api.v1 import (
    health,
    auth,
    profiles,
    vehicle_data,
    predictions,
    dtc,
    guardian,
    fleet,
    billing,
    paypal,
    reports,
    admin,
    ai_chat,
    legal,
    dashboard,
    driving,
    tiers,
    app_version,
    websockets,
    usage,
    fcm,
    failure_events,
    pid_atlas,
    feedback,
    pricing,
)

api_router = APIRouter()

# Core routes
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profiles.router, prefix="/profile", tags=["profiles"])

# Vehicle data
api_router.include_router(vehicle_data.router, prefix="/obd", tags=["vehicle-data"])
api_router.include_router(vehicle_data.telemetry_router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(dtc.router, prefix="/dtc", tags=["dtc"])

# AI and predictions
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(ai_chat.router, prefix="/ai", tags=["ai"])

# Guardian and fleet
api_router.include_router(guardian.router, prefix="/guardian", tags=["guardian"])
api_router.include_router(fleet.router, prefix="/fleet", tags=["fleet"])
api_router.include_router(driving.router, prefix="/driver", tags=["driving"])

# Billing and subscriptions
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(paypal.router, prefix="/paypal", tags=["paypal"])
api_router.include_router(tiers.router, prefix="/tiers", tags=["tiers"])

# Reports and exports
api_router.include_router(reports.router, prefix="/report", tags=["reports"])

# Admin and monitoring
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# Legal and app
api_router.include_router(legal.router, prefix="/legal", tags=["legal"])
api_router.include_router(app_version.router, prefix="/app", tags=["app-version"])

# WebSocket routes
api_router.include_router(websockets.router, tags=["websockets"])

# Usage tracking and permissions
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(usage.key_router, prefix="/key", tags=["permissions"])

# FCM push notifications
api_router.include_router(fcm.router, prefix="/fcm", tags=["fcm"])

# PID Atlas (community manufacturer PID database)
api_router.include_router(pid_atlas.router, prefix="/pids", tags=["pid-atlas"])

# Failure events and training data
api_router.include_router(failure_events.router, prefix="/profile", tags=["failure-events"])
api_router.include_router(failure_events.training_router, prefix="/training", tags=["training"])

# Prediction feedback (mechanic validation)
api_router.include_router(feedback.router, prefix="/predictions", tags=["predictions"])

# Pricing (parts + service costs, Qatar market)
api_router.include_router(pricing.router, prefix="/pricing", tags=["pricing"])

# Legacy routes for Android compatibility
api_router.include_router(auth.legacy_router, tags=["legacy"])
# NOTE: vehicle_data.legacy_router is mounted on app directly (routes already have /api/ prefix)
api_router.include_router(predictions.legacy_router, tags=["legacy"])

# Android calls /api/v1/ai/* instead of /api/ai/*  — mount ai_chat under both prefixes
api_router.include_router(ai_chat.router, prefix="/v1/ai", tags=["legacy-ai"])

# ========================
# Maintenance stub endpoints (Android expects these)
# ========================
_maintenance_router = APIRouter()


@_maintenance_router.get("/reminders/{user_id}")
async def get_maintenance_reminders(user_id: int):
    """Stub: maintenance reminders for Android compatibility."""
    return {
        "success": True,
        "reminders": [],
        "count": 0,
    }


@_maintenance_router.get("/summary/{user_id}")
async def get_maintenance_summary(user_id: int):
    """Stub: maintenance summary for Android compatibility."""
    return {
        "success": True,
        "summary": {
            "total_services": 0,
            "upcoming": 0,
            "overdue": 0,
            "last_service": None,
            "next_service": None,
        },
    }


def _setup_odometer_endpoint():
    """Deferred setup to avoid circular imports."""
    from fastapi import Body, Depends
    from sqlalchemy import select, update as sql_update
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.api.deps import get_db, get_current_user
    from predict.core.db.models.vehicle import VehicleProfile

    @_maintenance_router.post("/odometer")
    async def update_odometer(
        request: dict = Body(...),
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        """Update odometer (mileage_km) on the user's active vehicle profile."""
        odometer_km = request.get("odometer_km", 0)
        user_id = current_user.get("user_id") or current_user.get("id")

        result = await db.execute(
            select(VehicleProfile.profile_id).where(
                VehicleProfile.owner_user_id == user_id
            ).limit(1)
        )
        profile_id = result.scalar_one_or_none()
        if not profile_id:
            return {"success": False, "error": "No vehicle profile found"}

        await db.execute(
            sql_update(VehicleProfile)
            .where(VehicleProfile.profile_id == profile_id)
            .values(mileage_km=odometer_km)
        )
        await db.commit()
        return {"success": True, "odometer_km": odometer_km, "profile_id": profile_id}

_setup_odometer_endpoint()


api_router.include_router(_maintenance_router, prefix="/maintenance", tags=["maintenance"])

# ========================
# Vehicle stub endpoints (Android expects these)
# ========================
_vehicle_router = APIRouter()


@_vehicle_router.get("/engine-types")
async def get_engine_types(make: str = "", model: str = "", year: int = 0):
    """Stub: Return common engine types for vehicle selection dropdowns."""
    return {
        "success": True,
        "engine_types": ["Gasoline", "Diesel", "Hybrid", "Electric", "Plug-in Hybrid"],
    }


@_vehicle_router.get("/{vehicle_id}/fuel-specs")
async def get_vehicle_fuel_specs(vehicle_id: int):
    """Stub: Return fuel specs for a vehicle."""
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "fuel_type": "gasoline",
        "tank_capacity_liters": None,
        "fuel_grade": None,
    }


api_router.include_router(_vehicle_router, prefix="/vehicle", tags=["vehicle-stubs"])

# ========================
# Fuel tracking stub endpoints (Android expects these)
# ========================
_fuel_router = APIRouter()


@_fuel_router.post("/fillups")
async def log_fillup():
    """Stub: Log a fuel fillup (not yet implemented)."""
    return {"success": True, "message": "Fuel tracking coming soon"}


@_fuel_router.get("/fillups/{vehicle_id}")
async def get_fillup_history(vehicle_id: int):
    """Stub: Get fillup history for a vehicle."""
    return {"success": True, "fillups": [], "count": 0}


@_fuel_router.get("/statistics/{vehicle_id}")
async def get_fuel_statistics(vehicle_id: int):
    """Stub: Get fuel statistics for a vehicle."""
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "avg_mpg": None,
        "avg_cost_per_liter": None,
        "total_fillups": 0,
    }


api_router.include_router(_fuel_router, prefix="/fuel", tags=["fuel-stubs"])
