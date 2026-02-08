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
    reports,
    admin,
    ai_chat,
    legal,
    dashboard,
    driving,
    tiers,
    app_version,
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
api_router.include_router(tiers.router, prefix="/tiers", tags=["tiers"])

# Reports and exports
api_router.include_router(reports.router, prefix="/report", tags=["reports"])

# Admin and monitoring
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# Legal and app
api_router.include_router(legal.router, prefix="/legal", tags=["legal"])
api_router.include_router(app_version.router, prefix="/app", tags=["app-version"])

# Legacy routes for Android compatibility
api_router.include_router(auth.legacy_router, tags=["legacy"])
api_router.include_router(vehicle_data.legacy_router, tags=["legacy"])
