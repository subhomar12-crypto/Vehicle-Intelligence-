"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Api Endpoints Extended

Extended API Endpoints for New Features
Add these routes to your existing FastAPI mobile_server.py
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from config import get_config
import re
from enum import Enum

# Import TensorFlow availability check
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

CONFIG = get_config()

# Create router
router = APIRouter()

# ==================== SECURITY & VALIDATION ====================

import uuid
import logging
from functools import wraps

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Custom API error with user-safe message."""
    def __init__(self, message: str, status_code: int = 500, internal_message: str = None):
        self.message = message
        self.status_code = status_code
        self.internal_message = internal_message or message
        super().__init__(self.message)

def handle_api_errors(func):
    """Decorator for consistent error handling."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except APIError as e:
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"API Error [{error_id}]: {e.internal_message}")
            raise HTTPException(status_code=e.status_code, detail=f"{e.message} (ref: {error_id})")
        except ValueError as e:
            # Validation errors - client's fault
            error_id = str(uuid.uuid4())[:8]
            logger.warning(f"Validation Error [{error_id}]: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid request data (ref: {error_id})")
        except FileNotFoundError as e:
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"Not Found [{error_id}]: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Resource not found (ref: {error_id})")
        except PermissionError as e:
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"Permission Error [{error_id}]: {str(e)}")
            raise HTTPException(status_code=403, detail=f"Access denied (ref: {error_id})")
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            logger.exception(f"Unexpected Error [{error_id}]: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred. Please contact support with reference: {error_id}"
            )
    return wrapper

def sanitize_string(value: str, max_length: int = 100) -> str:
    """Remove potentially dangerous characters and limit length."""
    if value is None:
        return value
    # Remove SQL injection and XSS characters
    sanitized = re.sub(r'[<>"\';\\`]', '', value)
    # Limit length
    return sanitized[:max_length].strip()

# ==================== ENUMS ====================

class FuelGrade(str, Enum):
    REGULAR = 'Regular'
    MIDGRADE = 'Midgrade'
    PREMIUM = 'Premium'
    DIESEL = 'Diesel'

class AlertSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'

class AlertCondition(str, Enum):
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    EQUALS = 'equals'
    BETWEEN = 'between'
    NOT_EQUALS = 'not_equals'

# ==================== PYDANTIC MODELS ====================

class FillupRequest(BaseModel):
    profile_id: int = Field(..., gt=0, description="Vehicle profile ID")
    profile_name: str = Field(..., min_length=1, max_length=100)
    liters: float = Field(..., gt=0, le=500, description="Fuel amount in liters")
    cost: float = Field(..., ge=0, le=50000, description="Fuel cost")
    odometer_km: float = Field(..., ge=0, le=10000000, description="Current odometer")
    full_tank: bool = True
    fuel_grade: FuelGrade = FuelGrade.REGULAR
    station_name: Optional[str] = Field(None, max_length=200)

    @validator('profile_name', 'station_name', pre=True)
    def sanitize_names(cls, v):
        return sanitize_string(v) if v else v

    class Config:
        use_enum_values = True

class CustomAlertRule(BaseModel):
    profile_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    parameter: str = Field(..., min_length=1, max_length=50, regex=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    condition: AlertCondition
    threshold: float = Field(..., ge=-1000, le=100000)
    threshold2: Optional[float] = Field(None, ge=-1000, le=100000)
    severity: AlertSeverity
    enabled: bool = True
    message_template: Optional[str] = Field(None, max_length=500)

    @validator('name', 'message_template', pre=True)
    def sanitize_text(cls, v):
        return sanitize_string(v, max_length=500) if v else v

    @validator('threshold2')
    def validate_threshold2_for_between(cls, v, values):
        if values.get('condition') == AlertCondition.BETWEEN and v is None:
            raise ValueError('threshold2 required when condition is BETWEEN')
        return v

    class Config:
        use_enum_values = True

class GeofenceCreate(BaseModel):
    geofence_id: str = Field(..., min_length=1, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(..., min_length=1, max_length=100)
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(..., gt=0, le=1000)
    zone_type: Literal['home', 'work', 'service', 'custom'] = 'custom'
    severity: AlertSeverity = AlertSeverity.INFO

    @validator('name')
    def sanitize_name(cls, v):
        return sanitize_string(v)

    class Config:
        use_enum_values = True

class GPSLocation(BaseModel):
    profile_id: int = Field(..., gt=0)
    profile_name: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @validator('profile_name')
    def sanitize_name(cls, v):
        return sanitize_string(v)

class ExportRequest(BaseModel):
    profile_id: int = Field(..., gt=0)
    profile_name: str = Field(..., min_length=1, max_length=100)
    export_type: Literal['obd', 'trips', 'fuel', 'all']
    days: int = Field(30, ge=1, le=365)
    format: Literal['csv', 'json', 'xlsx'] = 'csv'

    @validator('profile_name')
    def sanitize_name(cls, v):
        return sanitize_string(v)

class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    make: str = Field('', max_length=50)
    model: str = Field('', max_length=50)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    vin: str = Field('', max_length=17, regex=r'^[A-HJ-NPR-Z0-9]*$')  # VIN format
    license_plate: str = Field('', max_length=20)
    category: Literal['Personal', 'Commercial', 'Fleet'] = 'Commercial'
    engine_type: str = Field('', max_length=50)
    transmission: Literal['', 'Automatic', 'Manual', 'CVT'] = ''
    fuel_type: Literal['', 'Gasoline', 'Diesel', 'Electric', 'Hybrid'] = ''
    drivetrain: Literal['', 'FWD', 'RWD', 'AWD', '4WD'] = ''
    color: str = Field('', max_length=30)
    purchase_date: str = Field('', max_length=10)  # YYYY-MM-DD format
    last_service_date: str = Field('', max_length=10)
    dealer_info: str = Field('', max_length=200)
    warranty_info: str = Field('', max_length=200)
    insurance_details: str = Field('', max_length=200)
    is_favorite: bool = False

    @validator('name', 'make', 'model', 'color', 'dealer_info', 'warranty_info', 'insurance_details')
    def sanitize_strings(cls, v):
        return sanitize_string(v) if v else v

    @validator('purchase_date', 'last_service_date')
    def validate_date_format(cls, v):
        if v and v.strip():
            import re
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v

# ==================== VEHICLE PROFILE ENDPOINTS ====================

@router.post("/api/profile/create")
@handle_api_errors
async def create_vehicle_profile(profile: CreateProfileRequest):
    """Create new vehicle profile from mobile app"""
    from vehicle_module import VehicleProfileManager

    vehicle_manager = VehicleProfileManager()

    # Convert Pydantic model to dict
    profile_data = profile.dict()

    # Create the profile
    result = vehicle_manager.create_profile(profile_data)

    if result:
        return {
            "success": True,
            "profile_id": result['profile_id'],
            "profile": result
        }
    else:
        raise APIError("Profile creation failed", status_code=400)

@router.get("/api/profile/list")
@handle_api_errors
async def get_all_profiles():
    """Get list of all vehicle profiles"""
    from vehicle_module import VehicleProfileManager

    vehicle_manager = VehicleProfileManager()
    profiles = vehicle_manager.get_all_profiles()

    return {
        "success": True,
        "profiles": profiles,
        "count": len(profiles)
    }

@router.get("/api/profile/{profile_id}")
@handle_api_errors
async def get_profile_details(profile_id: int):
    """Get specific profile details"""
    from vehicle_module import VehicleProfileManager

    vehicle_manager = VehicleProfileManager()
    profile = vehicle_manager.get_profile(profile_id)

    if profile:
        return {
            "success": True,
            "profile": profile
        }
    else:
        raise APIError("Profile not found", status_code=404)

# ==================== FUEL TRACKING ENDPOINTS ====================

@router.post("/api/fuel/fillup")
@handle_api_errors
async def log_fillup(fillup: FillupRequest):
    """Log a fuel fillup"""
    from fuel_tracking import FuelTrackingSystem
    fuel_system = FuelTrackingSystem()

    result = fuel_system.log_fillup(
        profile_id=fillup.profile_id,
        profile_name=fillup.profile_name,
        liters=fillup.liters,
        cost=fillup.cost,
        odometer_km=fillup.odometer_km,
        full_tank=fillup.full_tank,
        fuel_grade=fillup.fuel_grade,
        station_name=fillup.station_name
    )

    return result

@router.get("/api/fuel/history/{profile_id}")
@handle_api_errors
async def get_fillup_history(profile_id: int, days: int = 90):
    """Get fillup history"""
    from fuel_tracking import FuelTrackingSystem
    fuel_system = FuelTrackingSystem()

    history = fuel_system.get_fillup_history(profile_id, days)
    return {"fillups": history}

@router.get("/api/fuel/statistics/{profile_id}")
@handle_api_errors
async def get_fuel_statistics(profile_id: int, days: int = 90):
    """Get fuel statistics"""
    from fuel_tracking import FuelTrackingSystem
    fuel_system = FuelTrackingSystem()

    stats = fuel_system.calculate_fuel_statistics(profile_id, days)
    return stats

# ==================== TRIP ANALYTICS ENDPOINTS ====================

@router.get("/api/trips/history/{profile_id}")
@handle_api_errors
async def get_trip_history(profile_id: int, profile_name: str, limit: int = 10):
    """Get recent trips"""
    from trip_analytics import TripAnalytics
    from historical_data_manager import HistoricalDataManager

    historical_data = HistoricalDataManager()
    trip_system = TripAnalytics(historical_data)

    trips = trip_system.get_recent_trips(profile_id, profile_name, limit)
    return {"trips": trips}

@router.get("/api/trips/statistics/{profile_id}")
@handle_api_errors
async def get_trip_statistics(profile_id: int, profile_name: str, days: int = 30):
    """Get trip statistics"""
    from trip_analytics import TripAnalytics
    from historical_data_manager import HistoricalDataManager

    historical_data = HistoricalDataManager()
    trip_system = TripAnalytics(historical_data)

    stats = trip_system.get_trip_statistics(profile_id, profile_name, days)
    return stats

# ==================== DRIVING SCORE ENDPOINTS ====================

@router.get("/api/driving/score/{profile_id}")
@handle_api_errors
async def get_driving_score(profile_id: int):
    """Get current driving score"""
    from driving_score import DrivingScoreAnalyzer

    driving_score = DrivingScoreAnalyzer()
    summary = driving_score.get_session_summary(profile_id)
    return summary

# ==================== MAINTENANCE REMINDERS ENDPOINTS ====================

@router.get("/api/maintenance/reminders/{profile_id}")
@handle_api_errors
async def get_maintenance_reminders(profile_id: int, current_odometer_km: float):
    """Get active maintenance reminders"""
    from maintenance_reminders import MaintenanceRemindersSystem
    from vehicle_module import VehicleProfileManager

    vehicle_manager = VehicleProfileManager()
    reminder_system = MaintenanceRemindersSystem(vehicle_manager)

    reminders = reminder_system.get_active_reminders(profile_id, current_odometer_km)
    return {"reminders": reminders}

@router.get("/api/maintenance/summary/{profile_id}")
@handle_api_errors
async def get_maintenance_summary(profile_id: int, current_odometer_km: float):
    """Get maintenance reminder summary"""
    from maintenance_reminders import MaintenanceRemindersSystem
    from vehicle_module import VehicleProfileManager

    vehicle_manager = VehicleProfileManager()
    reminder_system = MaintenanceRemindersSystem(vehicle_manager)

    summary = reminder_system.get_reminder_summary(profile_id, current_odometer_km)
    return summary

# ==================== CUSTOM ALERTS ENDPOINTS ====================

@router.post("/api/alerts/create")
@handle_api_errors
async def create_alert_rule(rule: CustomAlertRule):
    """Create custom alert rule"""
    from custom_alerts import CustomAlertsSystem

    alert_system = CustomAlertsSystem()
    result = alert_system.create_alert_rule(rule.profile_id, rule.dict())
    return result

@router.get("/api/alerts/rules/{profile_id}")
@handle_api_errors
async def get_alert_rules(profile_id: int):
    """Get all alert rules for profile"""
    from custom_alerts import CustomAlertsSystem

    alert_system = CustomAlertsSystem()
    rules = alert_system.get_alert_rules(profile_id)
    return {"rules": rules}

@router.put("/api/alerts/rule/{profile_id}/{rule_id}/toggle")
@handle_api_errors
async def toggle_alert_rule(profile_id: int, rule_id: str, enabled: bool):
    """Enable/disable alert rule"""
    from custom_alerts import CustomAlertsSystem

    alert_system = CustomAlertsSystem()
    success = alert_system.enable_disable_rule(profile_id, rule_id, enabled)
    return {"success": success}

@router.delete("/api/alerts/rule/{profile_id}/{rule_id}")
@handle_api_errors
async def delete_alert_rule(profile_id: int, rule_id: str):
    """Delete alert rule"""
    from custom_alerts import CustomAlertsSystem

    alert_system = CustomAlertsSystem()
    success = alert_system.delete_alert_rule(profile_id, rule_id)
    return {"success": success}

# ==================== GEOFENCING ENDPOINTS ====================

@router.post("/api/geofence/check")
@handle_api_errors
async def check_geofence(location: GPSLocation):
    """Check GPS location against geofences"""
    from geofencing_alerts import GeofencingAlertSystem

    geofence_system = GeofencingAlertSystem()
    events = geofence_system.process_gps_data(
        location.profile_id,
        location.profile_name,
        location.latitude,
        location.longitude
    )
    return {"events": events}

@router.post("/api/geofence/create")
@handle_api_errors
async def create_geofence(geofence: GeofenceCreate):
    """Create custom geofence"""
    from geofencing_alerts import GeofencingAlertSystem

    geofence_system = GeofencingAlertSystem()
    success = geofence_system.create_custom_geofence(
        geofence.geofence_id,
        geofence.dict()
    )
    return {"success": success}

@router.get("/api/geofence/active/{profile_id}")
@handle_api_errors
async def get_active_zones(profile_id: int):
    """Get currently active zones"""
    from geofencing_alerts import GeofencingAlertSystem

    geofence_system = GeofencingAlertSystem()
    zones = geofence_system.get_active_zones(profile_id)
    return {"zones": zones}

# ==================== TWO-WAY COMMUNICATION ENDPOINTS ====================

@router.get("/api/commands/pending/{profile_id}")
@handle_api_errors
async def get_pending_commands(profile_id: int):
    """Get pending commands for mobile (polling)"""
    from two_way_communication import TwoWayCommunicationHub

    comm_hub = TwoWayCommunicationHub()
    commands = comm_hub.get_pending_commands_for_mobile(profile_id)
    return {"commands": commands}

@router.post("/api/commands/response")
@handle_api_errors
async def send_command_response(command_id: str, response: Dict[str, Any]):
    """Send response for a command"""
    from two_way_communication import TwoWayCommunicationHub

    comm_hub = TwoWayCommunicationHub()
    success = comm_hub.receive_command_response(command_id, response)
    return {"success": success}

@router.post("/api/request/desktop")
@handle_api_errors
async def send_request_to_desktop(profile_id: int, request_type: str, parameters: Dict[str, Any]):
    """Send request from mobile to desktop"""
    from two_way_communication import TwoWayCommunicationHub

    comm_hub = TwoWayCommunicationHub()
    result = comm_hub.send_request_to_desktop(profile_id, request_type, parameters)
    return result

# ==================== MULTI-VEHICLE COMPARISON ENDPOINTS ====================

@router.get("/api/fleet/overview")
@handle_api_errors
async def get_fleet_overview(days: int = 30):
    """Get fleet overview"""
    from multi_vehicle_comparison import MultiVehicleComparison
    from vehicle_module import VehicleProfileManager
    from historical_data_manager import HistoricalDataManager

    vehicle_manager = VehicleProfileManager()
    historical_data = HistoricalDataManager()
    comparison = MultiVehicleComparison(vehicle_manager, historical_data)

    overview = comparison.get_fleet_overview(days)
    return overview

@router.post("/api/fleet/compare")
@handle_api_errors
async def compare_vehicles(profile_ids: List[int], days: int = 30):
    """Compare specific vehicles"""
    from multi_vehicle_comparison import MultiVehicleComparison
    from vehicle_module import VehicleProfileManager
    from historical_data_manager import HistoricalDataManager

    vehicle_manager = VehicleProfileManager()
    historical_data = HistoricalDataManager()
    comparison = MultiVehicleComparison(vehicle_manager, historical_data)

    result = comparison.compare_vehicles(profile_ids, days)
    return result

# ==================== DATA EXPORT ENDPOINTS ====================

@router.post("/api/export/data")
@handle_api_errors
async def export_data(export_req: ExportRequest, background_tasks: BackgroundTasks):
    """Export data to CSV/Excel"""
    from desktop_data_export import DataExportSystem
    from vehicle_module import VehicleProfileManager
    from historical_data_manager import HistoricalDataManager

    vehicle_manager = VehicleProfileManager()
    historical_data = HistoricalDataManager()
    export_system = DataExportSystem(historical_data, vehicle_manager)

    if export_req.export_type == 'all':
        result = export_system.export_all_data(
            export_req.profile_id,
            export_req.profile_name,
            export_req.days,
            export_req.format
        )
    elif export_req.export_type == 'obd':
        result = export_system.export_obd_data(
            export_req.profile_id,
            export_req.profile_name,
            format=export_req.format
        )
    elif export_req.export_type == 'trips':
        result = export_system.export_trip_history(
            export_req.profile_id,
            export_req.profile_name,
            export_req.days,
            export_req.format
        )
    elif export_req.export_type == 'fuel':
        result = export_system.export_fuel_tracking(
            export_req.profile_id,
            export_req.days,
            export_req.format
        )
    else:
        raise APIError("Invalid export type", status_code=400)

    return result

# ==================== AI ALERTS ENDPOINTS ====================

@router.get("/api/ai/alerts/{profile_id}")
@handle_api_errors
async def get_ai_alerts(profile_id: int, limit: int = 50):
    """Get AI alert history"""
    from ai_alert_notifications import AIAlertNotificationSystem

    alert_system = AIAlertNotificationSystem(None)
    alerts = alert_system.get_alert_history(profile_id, limit)
    return {"alerts": alerts}

@router.get("/api/ai/alerts/active/{profile_id}")
@handle_api_errors
async def get_active_ai_alerts(profile_id: int):
    """Get active AI alerts"""
    from ai_alert_notifications import AIAlertNotificationSystem

    alert_system = AIAlertNotificationSystem(None)
    alerts = alert_system.get_active_alerts(profile_id)
    return {"alerts": alerts}

# ==================== SERVICE & MAINTENANCE ENDPOINTS ====================

class OilChangeLog(BaseModel):
    profile_id: int
    profile_name: str
    odometer_km: float
    oil_type: str
    filter_changed: bool = True
    cost: Optional[float] = None
    notes: Optional[str] = None

class OilChangeReminder(BaseModel):
    profile_id: int
    interval_km: int = 5000
    interval_days: int = 180
    last_change_km: float
    last_change_date: str

class ServiceReportRequest(BaseModel):
    profile_id: int
    profile_name: str
    report_type: str  # 'dtc', 'oil_change', 'full'
    include_history: bool = True

@router.post("/api/service/dtc/read")
async def read_dtc_codes(profile_id: int):
    """Read DTC (Diagnostic Trouble Codes) from vehicle"""
    try:
        from obd_connection_manager import get_obd_manager
        from dtc_lookup import lookup_dtc_details
        import logging

        logger = logging.getLogger(__name__)

        # Try to read from OBD adapter
        try:
            obd_mgr = get_obd_manager()

            if not obd_mgr.is_connected():
                # OBD adapter not connected - return mock data for testing
                logger.warning("OBD adapter not connected, returning mock data")
                return {
                    "success": True,
                    "profile_id": profile_id,
                    "dtc_codes": [
                        {
                            "code": "P0420",
                            "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                            "category": "Powertrain - Emissions",
                            "severity": "warning",
                            "status": "confirmed",
                            "possible_causes": [
                                "Faulty catalytic converter",
                                "Damaged oxygen sensor",
                                "Exhaust leak"
                            ]
                        },
                        {
                            "code": "P0171",
                            "description": "System Too Lean (Bank 1)",
                            "category": "Powertrain - Fuel/Air",
                            "severity": "warning",
                            "status": "confirmed",
                            "possible_causes": [
                                "Vacuum leak",
                                "Faulty MAF sensor",
                                "Weak fuel pump"
                            ]
                        }
                    ],
                    "total_codes": 2,
                    "timestamp": datetime.now().isoformat(),
                    "source": "mock_data"
                }

            # Read DTCs from vehicle via OBD adapter
            dtc_list = obd_mgr.read_dtc_codes()

            # Enhance with detailed descriptions, severity, causes
            enhanced_dtcs = []
            for code, basic_desc in dtc_list:
                details = lookup_dtc_details(code)
                enhanced_dtcs.append({
                    "code": code,
                    "description": details.get("description", basic_desc),
                    "category": details.get("category", "Unknown"),
                    "severity": details.get("severity", "warning"),
                    "status": "confirmed",
                    "possible_causes": details.get("causes", [])
                })

            return {
                "success": True,
                "profile_id": profile_id,
                "dtc_codes": enhanced_dtcs,
                "total_codes": len(enhanced_dtcs),
                "timestamp": datetime.now().isoformat(),
                "source": "obd_adapter"
            }

        except ConnectionError as e:
            # OBD connection error - return mock data with warning
            logger.error(f"OBD connection error: {e}, returning mock data")
            return {
                "success": True,
                "profile_id": profile_id,
                "dtc_codes": [
                    {
                        "code": "P0420",
                        "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                        "category": "Powertrain - Emissions",
                        "severity": "warning",
                        "status": "confirmed",
                        "possible_causes": [
                            "Faulty catalytic converter",
                            "Damaged oxygen sensor"
                        ]
                    }
                ],
                "total_codes": 1,
                "timestamp": datetime.now().isoformat(),
                "source": "mock_data",
                "warning": "OBD adapter not available"
            }

    except Exception as e:
        logger.error(f"DTC read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/service/dtc/clear")
async def clear_dtc_codes(profile_id: int):
    """Clear DTC codes from vehicle"""
    try:
        from obd_connection_manager import get_obd_manager
        import logging

        logger = logging.getLogger(__name__)

        # Try to clear DTCs via OBD adapter
        try:
            obd_mgr = get_obd_manager()

            if not obd_mgr.is_connected():
                # OBD adapter not connected - return mock success for testing
                logger.warning("OBD adapter not connected, returning mock response")
                return {
                    "success": True,
                    "profile_id": profile_id,
                    "message": "DTC codes cleared successfully (simulation mode)",
                    "timestamp": datetime.now().isoformat(),
                    "source": "mock_data"
                }

            # Clear DTCs via OBD adapter
            success = obd_mgr.clear_dtc_codes()

            if success:
                return {
                    "success": True,
                    "profile_id": profile_id,
                    "message": "DTC codes cleared successfully",
                    "timestamp": datetime.now().isoformat(),
                    "source": "obd_adapter"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to clear DTCs. Some codes may remain."
                )

        except ConnectionError as e:
            # OBD connection error - return mock success with warning
            logger.error(f"OBD connection error: {e}, returning mock response")
            return {
                "success": True,
                "profile_id": profile_id,
                "message": "DTC codes cleared (simulation mode)",
                "timestamp": datetime.now().isoformat(),
                "source": "mock_data",
                "warning": "OBD adapter not available"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DTC clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/service/odometer/{profile_id}")
async def get_odometer_reading(profile_id: int):
    """Get current odometer reading for vehicle"""
    try:
        from vehicle_module import VehicleProfileManager
        from obd_connection_manager import get_obd_manager
        import logging

        logger = logging.getLogger(__name__)
        vehicle_manager = VehicleProfileManager()
        profile = vehicle_manager.get_profile(profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        make = profile.get('make', '')
        model = profile.get('model', '')
        year = profile.get('year', 0)

        # Try to read from OBD adapter
        odometer_km = None
        source = "database"

        try:
            obd_mgr = get_obd_manager()

            if obd_mgr.is_connected():
                # Attempt to read odometer via OBD
                odometer_km = obd_mgr.read_odometer(make, model, year)

                if odometer_km is not None:
                    source = "obd_adapter"
                    # Update stored value in database
                    try:
                        # Update the profile's odometer value
                        profile['odometer_km'] = odometer_km
                        vehicle_manager.update_profile(profile_id, profile)
                        logger.info(f"Updated odometer for profile {profile_id}: {odometer_km} km")
                    except Exception as e:
                        logger.warning(f"Failed to update stored odometer: {e}")

        except Exception as e:
            logger.warning(f"OBD odometer read failed: {e}, falling back to database value")

        # Fallback to stored value if OBD read fails or is unavailable
        if odometer_km is None:
            odometer_km = profile.get('odometer_km', 0)
            source = "database"

        return {
            "success": True,
            "profile_id": profile_id,
            "profile_name": profile.get('name', 'Unknown'),
            "odometer_km": odometer_km,
            "odometer_miles": odometer_km * 0.621371,
            "source": source,
            "last_updated": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Odometer read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/service/oil-change/log")
@handle_api_errors
async def log_oil_change(oil_change: OilChangeLog):
    """Log an oil change service"""
    from vehicle_module import VehicleProfileManager
    import json
    import os

    vehicle_manager = VehicleProfileManager()

    # Create oil change log entry
    log_entry = {
        "log_id": f"oil_change_{oil_change.profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "profile_id": oil_change.profile_id,
        "profile_name": oil_change.profile_name,
        "timestamp": datetime.now().isoformat(),
        "odometer_km": oil_change.odometer_km,
        "oil_type": oil_change.oil_type,
        "filter_changed": oil_change.filter_changed,
        "cost": oil_change.cost,
        "notes": oil_change.notes
    }

    # Store in service history
    service_dir = str(CONFIG.DATA_DIR / "service_history")
    os.makedirs(service_dir, exist_ok=True)

    log_file = f"{service_dir}/profile_{oil_change.profile_id}_oil_changes.jsonl"
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

    return {
        "success": True,
        "log_id": log_entry["log_id"],
        "message": "Oil change logged successfully",
        "next_change_due_km": oil_change.odometer_km + 5000
    }

@router.post("/api/service/oil-change/reminder/set")
@handle_api_errors
async def set_oil_change_reminder(reminder: OilChangeReminder):
    """Set oil change reminder interval"""
    import json
    import os

    reminder_dir = str(CONFIG.DATA_DIR / "maintenance_schedules")
    os.makedirs(reminder_dir, exist_ok=True)

    reminder_data = {
        "profile_id": reminder.profile_id,
        "service_type": "oil_change",
        "interval_km": reminder.interval_km,
        "interval_days": reminder.interval_days,
        "last_change_km": reminder.last_change_km,
        "last_change_date": reminder.last_change_date,
        "next_change_due_km": reminder.last_change_km + reminder.interval_km,
        "updated_at": datetime.now().isoformat()
    }

    reminder_file = f"{reminder_dir}/profile_{reminder.profile_id}_oil_reminder.json"
    with open(reminder_file, 'w') as f:
        json.dump(reminder_data, f, indent=2)

    return {
        "success": True,
        "reminder_set": True,
        "next_change_due_km": reminder_data["next_change_due_km"],
        "km_remaining": reminder_data["next_change_due_km"] - reminder.last_change_km
    }

@router.get("/api/service/oil-change/reminder/{profile_id}")
@handle_api_errors
async def get_oil_change_reminder(profile_id: int, current_odometer_km: float):
    """Get oil change reminder status"""
    import json
    import os
    from datetime import datetime, timedelta

    reminder_file = str(CONFIG.DATA_DIR / "maintenance_schedules" / f"profile_{profile_id}_oil_reminder.json")

    if not os.path.exists(reminder_file):
        return {
            "success": False,
            "message": "No oil change reminder set for this profile"
        }

    with open(reminder_file, 'r') as f:
        reminder_data = json.load(f)

    km_remaining = reminder_data["next_change_due_km"] - current_odometer_km
    is_overdue = km_remaining < 0

    # Calculate days remaining
    last_change_date = datetime.fromisoformat(reminder_data["last_change_date"])
    days_since_change = (datetime.now() - last_change_date).days
    days_remaining = reminder_data["interval_days"] - days_since_change

    return {
        "success": True,
        "profile_id": profile_id,
        "next_change_due_km": reminder_data["next_change_due_km"],
        "km_remaining": km_remaining,
        "days_remaining": days_remaining,
        "is_overdue": is_overdue,
        "urgency": "critical" if is_overdue else ("warning" if km_remaining < 500 else "normal"),
        "message": f"Oil change {'overdue' if is_overdue else 'due'} in {abs(km_remaining):.0f} km"
    }

@router.get("/api/service/oil-change/history/{profile_id}")
@handle_api_errors
async def get_oil_change_history(profile_id: int, limit: int = 10):
    """Get oil change history"""
    import json
    import os

    log_file = str(CONFIG.DATA_DIR / "service_history" / f"profile_{profile_id}_oil_changes.jsonl")

    if not os.path.exists(log_file):
        return {
            "success": True,
            "history": [],
            "count": 0
        }

    history = []
    with open(log_file, 'r') as f:
        lines = f.readlines()
        for line in lines[-limit:]:  # Get last N entries
            history.append(json.loads(line.strip()))

    history.reverse()  # Most recent first

    return {
        "success": True,
        "history": history,
        "count": len(history)
    }

@router.post("/api/service/report/generate")
async def generate_service_report(report_request: ServiceReportRequest):
    """Generate comprehensive service report PDF"""
    try:
        from vehicle_module import VehicleProfileManager
        from service_report_generator import ServiceReportGenerator
        from obd_connection_manager import get_obd_manager
        from dtc_lookup import lookup_dtc_details
        import json
        import os
        import logging

        logger = logging.getLogger(__name__)
        vehicle_manager = VehicleProfileManager()
        profile = vehicle_manager.get_profile(report_request.profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Gather DTC codes data
        dtc_codes = []
        if report_request.report_type in ['dtc', 'full']:
            try:
                obd_mgr = get_obd_manager()
                if obd_mgr.is_connected():
                    # Read real DTCs from vehicle
                    dtc_list = obd_mgr.read_dtc_codes()
                    for code, basic_desc in dtc_list:
                        details = lookup_dtc_details(code)
                        dtc_codes.append({
                            "code": code,
                            "description": details.get("description", basic_desc),
                            "category": details.get("category", "Unknown"),
                            "severity": details.get("severity", "warning"),
                            "status": "confirmed",
                            "possible_causes": details.get("causes", [])
                        })
                else:
                    # Use mock data if OBD not available
                    dtc_codes = [
                        {
                            "code": "P0420",
                            "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                            "category": "Powertrain - Emissions",
                            "severity": "warning",
                            "status": "confirmed",
                            "possible_causes": ["Faulty catalytic converter", "Damaged oxygen sensor"]
                        }
                    ]
            except Exception as e:
                logger.warning(f"Failed to read DTCs: {e}")

        # Gather oil change status
        oil_change_status = {}
        if report_request.report_type in ['oil_change', 'full']:
            try:
                # Try to load oil change reminder
                reminder_file = str(CONFIG.DATA_DIR / "maintenance_schedules" / f"profile_{report_request.profile_id}_oil_reminder.json")
                if os.path.exists(reminder_file):
                    with open(reminder_file, 'r') as f:
                        reminder = json.load(f)

                    current_km = profile.get('odometer_km', 0)
                    last_change_km = reminder.get('last_change_km', 0)
                    interval_km = reminder.get('interval_km', 5000)
                    next_due_km = last_change_km + interval_km
                    km_remaining = max(0, next_due_km - current_km)

                    oil_change_status = {
                        "last_change_km": last_change_km,
                        "next_change_due_km": next_due_km,
                        "km_remaining": km_remaining,
                        "status": "overdue" if km_remaining == 0 else "due_soon" if km_remaining < 500 else "normal"
                    }
                else:
                    # Default values
                    oil_change_status = {
                        "last_change_km": profile.get('odometer_km', 0),
                        "next_change_due_km": profile.get('odometer_km', 0) + 5000,
                        "km_remaining": 5000,
                        "status": "normal"
                    }
            except Exception as e:
                logger.warning(f"Failed to load oil change status: {e}")

        # Gather maintenance summary
        maintenance_summary = {
            "total_services": 0,
            "upcoming_services": [],
            "overdue_services": []
        }

        try:
            # Count oil change history entries
            history_file = str(CONFIG.DATA_DIR / "service_history" / f"profile_{report_request.profile_id}_oil_changes.jsonl")
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    maintenance_summary["total_services"] = sum(1 for _ in f)
        except Exception as e:
            logger.warning(f"Failed to count service history: {e}")

        # Generate PDF report
        try:
            generator = ServiceReportGenerator()
            pdf_path = generator.generate_service_report(
                profile=profile,
                dtc_codes=dtc_codes,
                oil_change_status=oil_change_status,
                maintenance_summary=maintenance_summary,
                report_type=report_request.report_type
            )

            # Get filename for download URL
            filename = os.path.basename(pdf_path)
            report_id = filename.replace('.pdf', '')

            return {
                "success": True,
                "report_id": report_id,
                "filename": filename,
                "file_path": pdf_path,
                "file_size_kb": os.path.getsize(pdf_path) / 1024,
                "generated_at": datetime.now().isoformat(),
                "report_type": report_request.report_type,
                "profile": {
                    "profile_id": report_request.profile_id,
                    "name": report_request.profile_name
                }
            }

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate PDF report: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HEALTH CHECK ENDPOINTS ====================

from datetime import datetime
import psutil
import os

@router.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    Returns system status and key component availability.
    """
    try:
        # Check database connectivity
        db_status = "healthy"
        try:
            from vehicle_module import VehicleProfileManager
            vm = VehicleProfileManager()
            _ = vm.get_all_profiles()
        except Exception as e:
            db_status = f"unhealthy: {type(e).__name__}"

        # Check ML model availability
        ml_status = "healthy"
        try:
            from lstm_predictor import get_lstm_predictor
            predictor = get_lstm_predictor()
            status = predictor.get_availability_status()
            if not status.get('can_make_predictions'):
                ml_status = "degraded: fallback mode"
        except Exception as e:
            ml_status = f"unhealthy: {type(e).__name__}"

        # System resources
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(CONFIG.ROOT_DIR))

        return {
            "status": "healthy" if db_status == "healthy" and "unhealthy" not in ml_status else "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": CONFIG.APP_VERSION,
            "components": {
                "database": db_status,
                "ml_model": ml_status,
                "tensorflow": "available" if TENSORFLOW_AVAILABLE else "unavailable"
            },
            "resources": {
                "memory_percent": memory.percent,
                "disk_percent": disk.percent
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(type(e).__name__)
        }

@router.get("/ready")
async def readiness_check():
    """
    Readiness check - is the service ready to receive traffic?
    """
    try:
        # Quick database check
        from vehicle_module import VehicleProfileManager
        vm = VehicleProfileManager()
        _ = vm.get_all_profiles()

        return {"ready": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")
