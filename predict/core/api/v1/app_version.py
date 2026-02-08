"""
Mobile app version endpoints.

Handles:
- Force update checks
- Version compatibility
- App store links
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# ========================
# Version Configuration
# ========================

# Minimum required versions by platform
MIN_VERSIONS = {
    "android": "2.5.0",
    "ios": "2.5.0",
}

# Latest available versions
LATEST_VERSIONS = {
    "android": {
        "version": "3.0.0",
        "build": 300,
        "url": "https://play.google.com/store/apps/details?id=com.previlium.predict",
        "force_update": False,
        "update_message": "A new version is available with improved AI predictions.",
    },
    "ios": {
        "version": "3.0.0",
        "build": 300,
        "url": "https://apps.apple.com/app/predict/id1234567890",
        "force_update": False,
        "update_message": "A new version is available with improved AI predictions.",
    },
}


# ========================
# Response Models
# ========================

class VersionCheckResponse(BaseModel):
    current_version: str
    latest_version: str
    update_required: bool
    force_update: bool
    update_url: str
    update_message: str
    maintenance_mode: bool
    maintenance_message: Optional[str]


# ========================
# Endpoints
# ========================

@router.get("/version")
async def check_version(
    platform: str,
    version: str,
    build: Optional[int] = None,
):
    """
    Check if the app version is current.
    
    Args:
        platform: 'android' or 'ios'
        version: Current app version (e.g., '2.5.0')
        build: Build number
    """
    platform = platform.lower()
    
    if platform not in LATEST_VERSIONS:
        return {
            "error": "Invalid platform",
            "supported_platforms": list(LATEST_VERSIONS.keys()),
        }
    
    latest = LATEST_VERSIONS[platform]
    min_version = MIN_VERSIONS[platform]
    
    # Compare versions (simple string comparison works for semver)
    update_required = version < latest["version"]
    force_update = version < min_version
    
    return VersionCheckResponse(
        current_version=version,
        latest_version=latest["version"],
        update_required=update_required,
        force_update=force_update,
        update_url=latest["url"],
        update_message=latest["update_message"] if update_required else "",
        maintenance_mode=False,
        maintenance_message=None,
    )


@router.get("/version/all")
async def get_all_versions():
    """Get version information for all platforms."""
    return {
        "minimum_versions": MIN_VERSIONS,
        "latest_versions": LATEST_VERSIONS,
    }
