# PREDICT API Endpoints Reference

**For UX/UI Developer Use**
**Version**: 1.0
**Date**: February 2026

This document provides a complete reference of all API endpoints available for the PREDICT Android app and Desktop application.

---

## Table of Contents

1. [Authentication & Device Management](#1-authentication--device-management)
2. [Subscription & Permissions](#2-subscription--permissions)
3. [OBD Data (Driver Mode)](#3-obd-data-driver-mode)
4. [Predictions (Driver Mode)](#4-predictions-driver-mode)
5. [AI Chat](#5-ai-chat)
6. [Guardian Mode - Fleet Management](#6-guardian-mode---fleet-management)
7. [Emergency & Accident Detection](#7-emergency--accident-detection)
8. [Admin Endpoints (Desktop Only)](#8-admin-endpoints-desktop-only)
9. [FCM Notifications](#9-fcm-notifications)
10. [UI-to-Endpoint Mapping](#10-ui-to-endpoint-mapping)
11. [Error Codes](#11-error-codes)
12. [Headers Required](#12-headers-required)

---

## 1. AUTHENTICATION & DEVICE MANAGEMENT

### POST /api/auth/request-code
**Purpose**: Request email verification code for login/registration
**UI Element**: Login screen, Registration screen
**Auth Required**: No

**Request**:
```json
{
    "email": "user@example.com"
}
```

**Response**:
```json
{
    "success": true,
    "message": "Verification code sent to email"
}
```

---

### POST /api/auth/verify-code
**Purpose**: Verify code and complete login/registration
**UI Element**: Code entry screen
**Auth Required**: No

**Request**:
```json
{
    "email": "user@example.com",
    "code": "123456"
}
```

**Response**:
```json
{
    "success": true,
    "user_id": 123,
    "is_new_user": false,
    "message": "Code verified successfully"
}
```

---

### POST /api/auth/device-login
**Purpose**: Login from device, get/create API key bound to device
**UI Element**: Login screen (after code verification)
**Auth Required**: No (email+code verified)

**Request**:
```json
{
    "email": "user@example.com",
    "device_id": "abc123-unique-device-id",
    "device_name": "John's Phone",
    "device_model": "Samsung Galaxy S24",
    "device_type": "phone"
}
```

**Response**:
```json
{
    "success": true,
    "api_key": "pk_live_xxxxxxxxxxxxxxxx",
    "user_id": 123,
    "tier": "pro",
    "features": ["obd_dashboard", "ai_chat", "predictions"],
    "device_registered": true
}
```

**Notes**:
- `device_id` should be Android's ANDROID_ID (persists across reinstalls)
- If device already registered, returns existing API key for that device
- New devices get new API keys

---

### GET /api/user/devices
**Purpose**: List all devices registered for current user
**UI Element**: Settings screen → Manage Devices
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "devices": [
        {
            "device_id": "abc123",
            "device_name": "John's Phone",
            "device_model": "Samsung Galaxy S24",
            "device_type": "phone",
            "created_at": "2026-01-15T10:30:00Z",
            "last_used_at": "2026-02-01T14:22:00Z",
            "is_current": true
        },
        {
            "device_id": "def456",
            "device_name": "John's Tablet",
            "device_model": "iPad Pro",
            "device_type": "tablet",
            "created_at": "2026-01-20T09:00:00Z",
            "last_used_at": "2026-01-25T16:45:00Z",
            "is_current": false
        }
    ]
}
```

---

### DELETE /api/user/devices/{device_id}
**Purpose**: Revoke a specific device's access
**UI Element**: Settings → Manage Devices → Remove button
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "message": "Device revoked successfully"
}
```

---

### POST /api/user/devices/revoke-all
**Purpose**: Revoke all devices except current
**UI Element**: Settings → Security → "Sign out all devices"
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "devices_revoked": 2,
    "message": "All other devices signed out"
}
```

---

## 2. SUBSCRIPTION & PERMISSIONS

### GET /api/key/permissions
**Purpose**: Get current user's tier, limits, features, and usage
**UI Element**: Called on app startup, before every gated feature
**Auth Required**: Yes
**Cache**: 60 seconds recommended

**Response**:
```json
{
    "success": true,
    "user_id": 123,
    "status": "active",
    "suspended": false,
    "tier": "pro",
    "tier_expires_at": null,

    "limits": {
        "ai_messages_per_day": 20,
        "trip_history_days": 7,
        "max_vehicles": 1,
        "data_refresh_seconds": 5
    },
    "limits_custom": {
        "ai_messages_per_day": true
    },

    "features": {
        "obd_dashboard": true,
        "dtc_read": true,
        "dtc_clear": false,
        "ai_chat": true,
        "predictions": true,
        "guardian_mode": false,
        "desktop_sync": false,
        "pdf_reports": false,
        "push_alerts": true
    },
    "features_overridden": ["ai_chat"],

    "usage": {
        "ai_messages_today": 3,
        "ai_messages_remaining": 17,
        "dtc_scans_today": 1,
        "vehicles_count": 1
    },

    "last_modified": "2026-01-30T14:22:00Z",
    "modified_by": "admin"
}
```

**UI Usage**:
- Check `suspended` before any feature access
- Check `features[feature_name]` before showing feature
- Show usage bars based on `usage` and `limits`
- Display paywall if feature is `false`

---

### GET /api/pricing/public
**Purpose**: Get subscription pricing for paywall display
**UI Element**: Paywall screen, Subscription screen
**Auth Required**: No

**Response**:
```json
{
    "success": true,
    "tiers": {
        "free": {
            "price_monthly": 0,
            "price_annual": 0,
            "currency": "USD",
            "currency_symbol": "$",
            "description": "Basic OBD reading",
            "features": ["Basic diagnostics"]
        },
        "pro": {
            "price_monthly": 4.99,
            "price_annual": 47.88,
            "currency": "USD",
            "currency_symbol": "$",
            "description": "AI predictions & chat assistant",
            "features": [
                "AI failure predictions",
                "Chat assistant",
                "7-day trip history",
                "DTC reading"
            ]
        },
        "premium": {
            "price_monthly": 9.99,
            "price_annual": 95.88,
            "currency": "USD",
            "currency_symbol": "$",
            "description": "Full fleet management",
            "features": [
                "All Pro features",
                "Guardian mode",
                "365-day history",
                "DTC clearing",
                "PDF reports"
            ]
        }
    },
    "annual_discount_percent": 20
}
```

---

## 3. OBD DATA (Driver Mode)

### POST /api/obd/data
**Purpose**: Send OBD telemetry data to server
**UI Element**: Background service (no direct UI)
**Auth Required**: Yes
**Frequency**: Every 5 seconds while connected

**Request**:
```json
{
    "profile_id": 1,
    "timestamp": 1706745600,
    "data": {
        "rpm": 2500,
        "speed": 65,
        "coolant_temp": 85,
        "battery_voltage": 14.2,
        "engine_load": 45,
        "throttle_position": 30,
        "intake_air_temp": 25,
        "maf_rate": 15.5,
        "fuel_pressure": 350,
        "o2_sensor_voltage": 0.45
    },
    "gps": {
        "latitude": 33.4484,
        "longitude": -112.0740,
        "speed": 65,
        "heading": 180,
        "accuracy": 5
    }
}
```

**Response**:
```json
{
    "success": true,
    "data_id": 12345
}
```

---

### POST /api/obd/dtc
**Purpose**: Send DTC codes found during scan
**UI Element**: DTC screen after scan completes
**Auth Required**: Yes

**Request**:
```json
{
    "profile_id": 1,
    "dtcs": [
        {
            "code": "P0301",
            "description": "Cylinder 1 Misfire Detected",
            "status": "active",
            "freeze_frame": {
                "rpm": 2500,
                "speed": 45,
                "coolant_temp": 92
            }
        },
        {
            "code": "P0420",
            "description": "Catalyst System Efficiency Below Threshold",
            "status": "pending"
        }
    ]
}
```

**Response**:
```json
{
    "success": true,
    "dtcs_stored": 2,
    "ai_analysis": {
        "P0301": {
            "severity": "medium",
            "likely_causes": ["Spark plug failure", "Ignition coil issue"],
            "recommended_action": "Check spark plugs and ignition coils"
        }
    }
}
```

---

### POST /api/obd/dtc/clear
**Purpose**: Clear DTCs from vehicle (Premium only)
**UI Element**: DTC screen → "Clear Codes" button
**Auth Required**: Yes (Premium tier)

**Request**:
```json
{
    "profile_id": 1,
    "codes_to_clear": ["P0301", "P0420"]
}
```

**Response**:
```json
{
    "success": true,
    "codes_cleared": 2,
    "message": "Codes cleared successfully"
}
```

---

## 4. PREDICTIONS (Driver Mode)

### POST /api/predict
**Purpose**: Get AI predictions for vehicle health
**UI Element**: Predictions screen → "Get AI Summary" button
**Auth Required**: Yes (Pro+ tier)

**Request**:
```json
{
    "vin": "1HGCM82633A123456",
    "mileage_km": 45000,
    "sensors": {
        "rpm": 2500,
        "speed": 65,
        "coolant_temp": 85,
        "battery_voltage": 14.2,
        "engine_load": 45
    }
}
```

**Response**:
```json
{
    "success": true,
    "risk_score": 0.35,
    "risk_level": "LOW",
    "top_risks": [
        {
            "component": "Battery",
            "probability": 0.25,
            "time_horizon_km": 5000,
            "reason": "Slight voltage instability on previous trips"
        },
        {
            "component": "Engine cooling",
            "probability": 0.15,
            "time_horizon_km": 8000,
            "reason": "Coolant temperature above normal in hot conditions"
        }
    ],
    "recommendations": [
        "Check battery health at next service",
        "Inspect coolant level and radiator fan"
    ],
    "model_version": "v2_2026-02-01",
    "confidence": 0.85
}
```

---

### GET /api/v1/report/{profile_name}
**Purpose**: Get PDF health report for vehicle
**UI Element**: Predictions screen → "Open PDF Health Report" button
**Auth Required**: Yes (Pro+ tier)
**Response Type**: PDF file

**Example URL**: `https://predict.previlium.com/api/v1/report/John's%20Honda`

**Response**: PDF file download (opens in browser/PDF viewer)

---

## 5. AI CHAT

### POST /api/chat/message
**Purpose**: Send message to AI chat assistant
**UI Element**: Chat screen
**Auth Required**: Yes (Pro+ tier)
**Rate Limit**: Based on tier (e.g., 10/day for Pro)

**Request**:
```json
{
    "message": "Why is my check engine light on?",
    "context": {
        "active_dtcs": ["P0301", "P0420"],
        "vehicle_data": {
            "rpm": 2500,
            "coolant_temp": 85,
            "battery_voltage": 14.2
        },
        "vehicle_info": {
            "make": "Honda",
            "model": "Accord",
            "year": 2020
        }
    },
    "conversation_id": "conv_abc123"
}
```

**Response**:
```json
{
    "success": true,
    "response": "Based on the active DTCs, your check engine light is on due to two issues:\n\n1. **P0301 - Cylinder 1 Misfire**: This indicates...",
    "conversation_id": "conv_abc123",
    "usage": {
        "messages_today": 4,
        "messages_remaining": 6
    }
}
```

---

## 6. GUARDIAN MODE - FLEET MANAGEMENT

### GET /api/guardian/dashboard
**Purpose**: Get fleet overview data
**UI Element**: Guardian dashboard screen
**Auth Required**: Yes (Premium tier + Guardian role)

**Response**:
```json
{
    "success": true,
    "fleet_summary": {
        "total_vehicles": 5,
        "online": 3,
        "offline": 2,
        "alerts_active": 2
    },
    "vehicles": [
        {
            "profile_id": 1,
            "name": "Delivery Van 1",
            "driver_name": "John Smith",
            "status": "driving",
            "last_location": {
                "latitude": 33.4484,
                "longitude": -112.0740,
                "speed": 45,
                "heading": 180,
                "updated_at": "2026-02-01T14:22:00Z"
            },
            "health_score": 85,
            "alerts": []
        }
    ],
    "recent_events": [
        {
            "type": "hard_brake",
            "vehicle_id": 1,
            "timestamp": "2026-02-01T14:15:00Z",
            "severity": "medium"
        }
    ]
}
```

---

### GET /api/guardian/profiles
**Purpose**: List all vehicles under guardian management
**UI Element**: Fleet list in dashboard
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "profiles": [
        {
            "profile_id": 1,
            "name": "Delivery Van 1",
            "vin": "1HGCM82633A123456",
            "driver_id": 5,
            "driver_name": "John Smith",
            "driver_email": "john@example.com",
            "created_at": "2026-01-15T10:00:00Z",
            "monitoring_enabled": true
        }
    ]
}
```

---

### GET /api/guardian/fleet/slots
**Purpose**: Get guardian's fleet slot usage (how many vehicles can be added)
**UI Element**: Fleet Management screen - slot usage card
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "max_slots": 2,
    "used_slots": 1,
    "available_slots": 1,
    "can_add_more": true,
    "tier": "premium",
    "is_custom_limit": false,
    "upgrade_options": {
        "fleet_manager": {"slots": 10, "message": "Upgrade to Fleet Manager for 10 vehicles"},
        "enterprise": {"slots": 50, "message": "Contact sales for Enterprise (50+ vehicles)"}
    }
}
```

**Tier Defaults**:
| Tier | Max Vehicles |
|------|--------------|
| Free/Pro | 0 (no fleet access) |
| Premium | 2 |
| Fleet Manager | 10 |
| Enterprise | 50 |
| Admin | Unlimited |

**Note**: Admin can set custom limits per user via Desktop app.

---

### POST /api/guardian/invite
**Purpose**: Create invitation link for a new driver
**UI Element**: Fleet Management → "Invite Driver" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "driver_email": "newdriver@example.com",
    "driver_name": "Jane Doe",
    "vehicle_name": "Delivery Van 3",
    "permissions": ["location", "telemetry", "alerts"]
}
```

**Response (Success)**:
```json
{
    "success": true,
    "invite_code": "INV-ABC123",
    "invite_url": "https://predict.previlium.com/join/INV-ABC123",
    "expires_at": "2026-02-08T14:22:00Z"
}
```

**Response (Slot Limit Reached - HTTP 429)**:
```json
{
    "success": false,
    "error": "fleet_slot_limit_reached",
    "message": "You've reached your limit of 2 vehicles",
    "max_slots": 2,
    "used_slots": 2,
    "upgrade_required": true
}
```

**Important**: Check `/api/guardian/fleet/slots` before showing "Add Driver" button to proactively show upgrade prompt.

---

### GET /api/guardian/profiles/{profile_id}/location
**Purpose**: Get vehicle's last known location
**UI Element**: Map marker in Live Monitoring
**Auth Required**: Yes (Premium + Guardian)
**Poll Frequency**: Every 10 seconds for live view

**Response**:
```json
{
    "success": true,
    "location": {
        "latitude": 33.4484,
        "longitude": -112.0740,
        "speed": 45,
        "heading": 180,
        "accuracy": 5,
        "updated_at": "2026-02-01T14:22:00Z"
    },
    "is_driving": true,
    "trip_id": "trip_123"
}
```

---

### GET /api/guardian/profiles/{profile_id}/trips
**Purpose**: Get vehicle's trip history
**UI Element**: Trip list in Guardian History
**Auth Required**: Yes (Premium + Guardian)

**Query Parameters**:
- `limit`: Number of trips (default 20)
- `offset`: Pagination offset
- `start_date`: Filter start date
- `end_date`: Filter end date

**Response**:
```json
{
    "success": true,
    "trips": [
        {
            "trip_id": "trip_123",
            "start_time": "2026-02-01T08:00:00Z",
            "end_time": "2026-02-01T09:30:00Z",
            "distance_km": 45.5,
            "duration_minutes": 90,
            "avg_speed": 30.3,
            "max_speed": 65,
            "score": 85,
            "events_count": 2,
            "start_location": "123 Main St",
            "end_location": "456 Oak Ave"
        }
    ],
    "total_count": 150
}
```

---

### GET /api/guardian/profiles/{profile_id}/events
**Purpose**: Get driving events (hard braking, speeding, etc.)
**UI Element**: Events list, alert badges
**Auth Required**: Yes (Premium + Guardian)

**Query Parameters**:
- `limit`: Number of events (default 50)
- `event_type`: Filter by type (hard_brake, speeding, etc.)
- `severity`: Filter by severity (low, medium, high)

**Response**:
```json
{
    "success": true,
    "events": [
        {
            "event_id": 1,
            "event_type": "hard_brake",
            "timestamp": "2026-02-01T14:15:00Z",
            "latitude": 33.4484,
            "longitude": -112.0740,
            "value": 0.8,
            "threshold": 0.5,
            "severity": "medium",
            "description": "Hard braking detected (0.8g)"
        },
        {
            "event_id": 2,
            "event_type": "speeding",
            "timestamp": "2026-02-01T14:10:00Z",
            "latitude": 33.4500,
            "longitude": -112.0750,
            "value": 75,
            "threshold": 65,
            "severity": "low",
            "description": "Speed 75 km/h in 65 km/h zone"
        }
    ]
}
```

---

### POST /api/guardian/profiles/{profile_id}/command
**Purpose**: Send command to vehicle (request location, message, etc.)
**UI Element**: Vehicle action menu
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "command_type": "request_location",
    "payload": {
        "message": "Please share your location"
    }
}
```

**Command Types**:
- `request_location` - Ask driver to share location
- `message` - Send text message to driver
- `obd_reconnect` - Request OBD reconnection

**Response**:
```json
{
    "success": true,
    "command_id": 456,
    "status": "pending",
    "message": "Command sent to vehicle"
}
```

---

### GET /api/guardian/telemetry/{profile_id}/latest
**Purpose**: Get latest telemetry for a vehicle
**UI Element**: Vehicle detail screen
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "telemetry": {
        "timestamp": "2026-02-01T14:22:00Z",
        "latitude": 33.4484,
        "longitude": -112.0740,
        "speed": 45,
        "heading": 180,
        "accuracy": 5,
        "is_driving": true,
        "obd_data": {
            "rpm": 2500,
            "coolant_temp": 85,
            "battery_voltage": 14.2
        }
    }
}
```

---

## 7. EMERGENCY & ACCIDENT DETECTION

These endpoints handle emergency situations, accident detection (including airbag deployment), and location request management. **Location tracking is NOT continuous** - it only occurs during accidents or on-demand guardian requests (limited to 3/month).

### POST /api/events/accident
**Purpose**: Report an accident or emergency (CRITICAL - triggers immediate guardian notification)
**UI Element**: Background service detects airbag deployment, crash, or emergency button press
**Auth Required**: Yes

**When Triggered**:
- Airbag deployment detected via OBD
- Severe impact detected (high G-force from phone sensors)
- Emergency button pressed by driver
- Vehicle rollover detected

**Request**:
```json
{
    "profile_id": 1,
    "accident_type": "airbag_deployed",
    "latitude": 33.4484,
    "longitude": -112.0740,
    "speed_at_impact": 45.5,
    "g_force": 2.5,
    "airbag_status": "deployed",
    "vehicle_orientation": "upright",
    "timestamp": 1706745600,
    "details": {
        "seatbelt_status": "engaged",
        "doors_locked": false
    }
}
```

**Accident Types**:
- `airbag_deployed` - Airbag deployment detected (HIGHEST PRIORITY)
- `crash_detected` - Impact detected via sensors
- `emergency_button` - Driver pressed emergency button
- `rollover` - Vehicle rollover detected

**Response**:
```json
{
    "success": true,
    "event_id": "evt_abc123",
    "alert_id": "alt_def456",
    "notifications_sent": 2,
    "guardians_count": 2,
    "message": "EMERGENCY: All guardians have been notified immediately"
}
```

**Important**:
- This triggers IMMEDIATE FCM push notifications to ALL guardians
- Notifications are sent with highest priority (wake device)
- Alert is stored in database for guardian dashboard
- No rate limiting on this endpoint (emergencies are emergencies)
- **ACCIDENT LOCATION IS ALWAYS SENT** - does NOT count against the 3/month quota
- The 3/month limit ONLY applies to manual "Request Location" requests

---

### GET /api/guardian/location-requests/remaining
**Purpose**: Check remaining location requests for this month
**UI Element**: Live Monitoring screen - before "Request Location" button
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "limit_per_month": 3,
    "used_this_month": 1,
    "remaining": 2,
    "resets_on": "2026-03-01"
}
```

**Important**:
- Guardians are LIMITED to 3 **manual** location requests per month (privacy protection)
- Quota resets on the 1st of each month
- **CRITICAL: Emergency/accident alerts ALWAYS include location** - never blocked by quota
- The quota ONLY applies to guardian-initiated "Request Location" actions

---

### POST /api/guardian/request-location/{profile_id}
**Purpose**: Request a driver's location (LIMITED TO 3/MONTH)
**UI Element**: Live Monitoring → Vehicle card → "Request Location" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "reason": "Checking on driver - no response to calls"
}
```

**Response (Success)**:
```json
{
    "success": true,
    "command_id": 789,
    "message": "Location request sent to driver",
    "requests_remaining_this_month": 2
}
```

**Response (Quota Exceeded - HTTP 429)**:
```json
{
    "error": "location_request_limit_reached",
    "message": "You have used all 3 location requests this month",
    "used": 3,
    "limit": 3,
    "resets_on": "2026-03-01"
}
```

**Important**:
- Driver receives push notification and can CHOOSE to share location
- Request expires after 1 hour if driver doesn't respond
- Use sparingly - this is for genuine concern situations

---

### POST /api/commands/location-response
**Purpose**: Driver responds to location request with their current location
**UI Element**: Driver app - notification action "Share Location"
**Auth Required**: Yes

**Request**:
```json
{
    "command_id": 789,
    "latitude": 33.4484,
    "longitude": -112.0740,
    "speed": 0,
    "heading": 180,
    "accuracy": 5,
    "address": "123 Main St, Phoenix, AZ",
    "battery_level": 75
}
```

**Response**:
```json
{
    "success": true,
    "message": "Location shared with guardian"
}
```

---

### GET /api/guardian/alerts/recent
**Purpose**: Get recent alerts for all vehicles under guardian
**UI Element**: Live Monitoring screen - alerts list
**Auth Required**: Yes (Premium + Guardian)

**Query Parameters**:
- `limit`: Number of alerts (default 50)
- `include_acknowledged`: Include acknowledged alerts (default false)

**Response**:
```json
{
    "success": true,
    "alerts": [
        {
            "alert_id": "alt_abc123",
            "profile_id": 1,
            "vehicle_name": "Delivery Van 1",
            "alert_type": "accident_airbag_deployed",
            "severity": "critical",
            "title": "🚨 AIRBAG DEPLOYED - EMERGENCY",
            "message": "Emergency alert detected for vehicle. Location: 33.448400, -112.074000. Speed at impact: 45.5 km/h. Airbag was deployed.",
            "timestamp": "2026-02-01T14:22:00Z",
            "is_acknowledged": false,
            "data": {
                "accident_type": "airbag_deployed",
                "latitude": 33.4484,
                "longitude": -112.0740,
                "speed_at_impact": 45.5,
                "airbag_status": "deployed",
                "requires_immediate_action": true
            }
        },
        {
            "alert_id": "alt_def456",
            "profile_id": 2,
            "vehicle_name": "Delivery Van 2",
            "alert_type": "driving_event",
            "severity": "high",
            "title": "Hard Braking Detected",
            "message": "Hard braking event detected at 0.8g",
            "timestamp": "2026-02-01T14:15:00Z",
            "is_acknowledged": true
        }
    ],
    "summary": {
        "critical_count": 1,
        "high_count": 1,
        "total_count": 2
    }
}
```

**Alert Severity Levels**:
- `critical` - Accidents, airbag deployment, rollover (RED badge)
- `high` - Hard braking, rapid acceleration (ORANGE badge)
- `medium` - Speeding, OBD disconnect (YELLOW badge)
- `low` - Informational (GRAY badge)

---

### POST /api/guardian/alerts/{alert_id}/acknowledge
**Purpose**: Acknowledge an alert (mark as seen/handled)
**UI Element**: Alert card → "Acknowledge" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "notes": "Driver confirmed OK, minor fender bender"
}
```

**Response**:
```json
{
    "success": true,
    "message": "Alert acknowledged"
}
```

---

### POST /api/guardian/invite
**Purpose**: Create invitation link for a new driver
**UI Element**: Fleet Management → "Invite Driver" button / FAB
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "driver_email": "newdriver@example.com",
    "driver_name": "Jane Doe",
    "vehicle_name": "Delivery Van 3",
    "permissions": ["location", "telemetry", "alerts"]
}
```

**Response**:
```json
{
    "success": true,
    "invite_code": "INV-ABC123",
    "invite_url": "https://predict.previlium.com/join/INV-ABC123",
    "expires_at": "2026-02-08T14:22:00Z"
}
```

---

### GET /api/guardian/fleet/drivers
**Purpose**: Get all drivers/vehicles in the fleet
**UI Element**: Fleet Management - Drivers tab
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "drivers": [
        {
            "driver_id": "drv_123",
            "name": "John Smith",
            "email": "john@example.com",
            "vehicle_name": "Delivery Van 1",
            "license_plate": "ABC-1234",
            "profile_id": 1,
            "is_active": true,
            "consent_location": true,
            "consent_telemetry": true,
            "consent_alerts": true,
            "joined_at": "2026-01-15T10:00:00Z"
        }
    ]
}
```

---

### POST /api/guardian/vehicles/link
**Purpose**: Link a vehicle to guardian (after invite accepted)
**UI Element**: Backend - called when driver joins
**Auth Required**: Yes

---

### POST /api/guardian/vehicles/unlink/{profile_id}
**Purpose**: Remove driver/vehicle from fleet
**UI Element**: Fleet Management → Driver card → "Remove" button
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "message": "Vehicle unlinked from fleet"
}
```

---

### GET /api/guardian/vehicles/{profile_id}/live
**Purpose**: Get real-time data for a specific vehicle
**UI Element**: Vehicle Detail screen
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "data": {
        "is_online": true,
        "is_driving": true,
        "last_update": "2026-02-01T14:22:00Z",
        "location": {
            "latitude": 33.4484,
            "longitude": -112.0740,
            "speed": 45,
            "heading": 180
        },
        "obd": {
            "rpm": 2500,
            "coolant_temp": 85,
            "battery_voltage": 14.2
        }
    }
}
```

---

### GET /api/guardian/vehicles/{profile_id}/health
**Purpose**: Get vehicle health summary
**UI Element**: Vehicle Detail - Health tab
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "health_score": 85,
    "components": [
        {
            "name": "Battery",
            "status": "good",
            "score": 90,
            "last_checked": "2026-02-01T14:22:00Z"
        },
        {
            "name": "Engine",
            "status": "fair",
            "score": 75,
            "warning": "Minor coolant temp variations"
        }
    ],
    "active_dtcs": 0,
    "pending_dtcs": 1
}
```

---

### GET /api/guardian/settings/{profile_id}
**Purpose**: Get monitoring settings for a vehicle
**UI Element**: Guardian Settings screen
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "settings": {
        "speed_limit": 120,
        "geofence_enabled": true,
        "notifications_enabled": true,
        "harsh_braking_alerts": true,
        "rapid_acceleration_alerts": true,
        "idle_alerts": true,
        "idle_threshold_minutes": 10
    }
}
```

---

### PUT /api/guardian/settings/{profile_id}
**Purpose**: Update monitoring settings for a vehicle
**UI Element**: Guardian Settings - Save button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "speed_limit": 100,
    "harsh_braking_alerts": false
}
```

---

### GET /api/guardian/predictions/{profile_id}
**Purpose**: Get AI predictions for a vehicle
**UI Element**: Vehicle Detail - Predictions tab
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "predictions": [
        {
            "prediction_id": "pred_123",
            "component": "Battery",
            "probability": 0.25,
            "severity": "medium",
            "estimated_days": 30,
            "created_at": "2026-02-01T10:00:00Z"
        }
    ]
}
```

---

### POST /api/guardian/predictions/{prediction_id}/acknowledge
**Purpose**: Acknowledge a prediction
**UI Element**: Prediction card → "Acknowledge" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "action": "scheduled_maintenance"
}
```

---

### POST /api/guardian/predictions/{prediction_id}/false-alarm
**Purpose**: Mark prediction as false alarm
**UI Element**: Prediction card → "False Alarm" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "reason": "Component was recently replaced"
}
```

---

### GET /api/guardian/geofences/{profile_id}
**Purpose**: Get geofences for a vehicle
**UI Element**: Geofencing screen
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "geofences": [
        {
            "geofence_id": "geo_123",
            "name": "Office",
            "type": "circle",
            "latitude": 33.4484,
            "longitude": -112.0740,
            "radius_meters": 500,
            "alert_on_entry": true,
            "alert_on_exit": true
        }
    ]
}
```

---

### POST /api/guardian/geofences
**Purpose**: Create a new geofence
**UI Element**: Geofencing → "Add Geofence" button
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "profile_id": 1,
    "name": "Home",
    "type": "circle",
    "latitude": 33.4484,
    "longitude": -112.0740,
    "radius_meters": 200,
    "alert_on_entry": true,
    "alert_on_exit": true
}
```

---

### DELETE /api/guardian/geofences/{geofence_id}
**Purpose**: Delete a geofence
**UI Element**: Geofence card → "Delete" button
**Auth Required**: Yes (Premium + Guardian)

---

### GET /api/guardian/chat/vehicle-context/{profile_id}
**Purpose**: Get vehicle context for AI chat
**UI Element**: Chat screen (background)
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "context": {
        "vehicle_name": "Delivery Van 1",
        "make": "Ford",
        "model": "Transit",
        "year": 2022,
        "current_dtcs": ["P0420"],
        "recent_events": ["hard_brake at 14:15"],
        "health_score": 85
    }
}
```

---

### POST /api/guardian/chat/message
**Purpose**: Send message to AI chat (Guardian context)
**UI Element**: Guardian AI Chat
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "message": "Why did my driver's van have hard braking events today?",
    "profile_id": 1
}
```

---

### GET /api/guardian/notification-preferences
**Purpose**: Get guardian's notification preferences
**UI Element**: Settings → Notifications
**Auth Required**: Yes (Premium + Guardian)

**Response**:
```json
{
    "success": true,
    "preferences": {
        "emergency_alerts": true,
        "speeding_alerts": true,
        "hard_braking_alerts": true,
        "geofence_alerts": true,
        "maintenance_alerts": true,
        "quiet_hours_enabled": false,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00"
    }
}
```

---

### PUT /api/guardian/notification-preferences
**Purpose**: Update notification preferences
**UI Element**: Settings → Notifications → Save
**Auth Required**: Yes (Premium + Guardian)

---

### GET /api/guardian/action-log
**Purpose**: Get guardian's action log
**UI Element**: Settings → Activity Log
**Auth Required**: Yes (Premium + Guardian)

**Query Parameters**:
- `limit`: Number of entries (default 50)
- `offset`: Pagination offset

**Response**:
```json
{
    "success": true,
    "entries": [
        {
            "action": "location_request",
            "profile_id": 1,
            "timestamp": "2026-02-01T14:22:00Z",
            "details": "Requested location for Delivery Van 1"
        }
    ]
}
```

---

### GET /api/guardian/reports/history
**Purpose**: Get generated reports history
**UI Element**: Reports screen
**Auth Required**: Yes (Premium + Guardian)

---

### POST /api/guardian/analytics/compare
**Purpose**: Compare driver/vehicle analytics
**UI Element**: Driver Comparison screen
**Auth Required**: Yes (Premium + Guardian)

**Request**:
```json
{
    "profile_ids": [1, 2, 3],
    "metrics": ["avg_speed", "hard_braking_count", "fuel_efficiency"],
    "period": "last_30_days"
}
```

---

## Driver-Side Consent Endpoints

### POST /api/driver/consent
**Purpose**: Driver grants monitoring consent to guardian
**UI Element**: Consent screen (Driver app)
**Auth Required**: Yes

**Request**:
```json
{
    "guardian_id": "guard_123",
    "consent_types": ["location", "telemetry", "alerts"]
}
```

---

### POST /api/driver/revoke-consent
**Purpose**: Driver revokes monitoring consent
**UI Element**: Privacy Settings → Revoke Consent
**Auth Required**: Yes

**Request**:
```json
{
    "guardian_id": "guard_123",
    "consent_types": ["location"]
}
```

---

### GET /api/driver/monitoring-status
**Purpose**: Get what data is being monitored
**UI Element**: Privacy Settings screen (Driver)
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "monitoring": {
        "location": true,
        "telemetry": true,
        "alerts": true
    },
    "guardian": {
        "name": "Fleet Manager",
        "email": "manager@company.com"
    }
}
```

---

### GET /api/driver/guardians
**Purpose**: Get list of guardians monitoring the driver
**UI Element**: Privacy Settings screen (Driver)
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "guardians": [
        {
            "guardian_id": "guard_123",
            "name": "Fleet Manager",
            "email": "manager@company.com",
            "active_consents": ["location", "telemetry", "alerts"]
        }
    ]
}
```

---

## Telemetry Endpoints (Driver → Server)

### POST /api/telemetry
**Purpose**: Send enhanced telemetry from driver app
**UI Element**: Background service
**Auth Required**: Yes
**Frequency**: When location changes or every 30 seconds while driving

**Request**:
```json
{
    "profile_id": 1,
    "timestamp": 1706745600,
    "latitude": 33.4484,
    "longitude": -112.0740,
    "speed": 45,
    "heading": 180,
    "accuracy": 5,
    "is_driving": true,
    "obd_connected": true
}
```

---

### POST /api/trips/start
**Purpose**: Signal trip start
**UI Element**: Background service (auto-detected)
**Auth Required**: Yes

**Request**:
```json
{
    "profile_id": 1,
    "start_latitude": 33.4484,
    "start_longitude": -112.0740
}
```

---

### POST /api/trips/end
**Purpose**: Signal trip end
**UI Element**: Background service (auto-detected)
**Auth Required**: Yes

**Request**:
```json
{
    "trip_id": "trip_123",
    "end_latitude": 33.5000,
    "end_longitude": -112.1000,
    "distance_km": 15.5,
    "duration_minutes": 25,
    "max_speed": 75,
    "events_count": 1
}
```

---

### POST /api/events/report
**Purpose**: Report driving event (hard brake, speeding, etc.)
**UI Element**: Background service (sensor detection)
**Auth Required**: Yes

**Request**:
```json
{
    "profile_id": 1,
    "event_type": "hard_brake",
    "severity": "medium",
    "latitude": 33.4484,
    "longitude": -112.0740,
    "value": 0.8,
    "speed": 45
}
```

---

### POST /api/events/obd-disconnect
**Purpose**: Report OBD adapter disconnection
**UI Element**: Background service
**Auth Required**: Yes

---

### POST /api/events/obd-reconnect
**Purpose**: Report OBD adapter reconnection
**UI Element**: Background service
**Auth Required**: Yes

---

### GET /api/commands/pending/{profile_id}
**Purpose**: Get pending commands for driver
**UI Element**: Background service (polling)
**Auth Required**: Yes

**Response**:
```json
{
    "success": true,
    "commands": [
        {
            "command_id": 123,
            "command_type": "request_location",
            "guardian_name": "Fleet Manager",
            "reason": "Checking on driver",
            "created_at": "2026-02-01T14:20:00Z",
            "expires_at": "2026-02-01T15:20:00Z"
        }
    ]
}
```

---

### POST /api/commands/acknowledge
**Purpose**: Acknowledge receipt of command
**UI Element**: Notification action
**Auth Required**: Yes

---

### POST /api/commands/complete
**Purpose**: Complete a command with response
**UI Element**: Notification action / Dialog
**Auth Required**: Yes

**Request**:
```json
{
    "command_id": 123,
    "response": {
        "latitude": 33.4484,
        "longitude": -112.0740,
        "address": "123 Main St"
    }
}
```

---

## 8. ADMIN ENDPOINTS (Desktop Only)

These endpoints require `X-Admin-Key` header and are used by the Desktop application only.

### GET /api/admin/users/{user_id}/subscription
**Purpose**: Get user's subscription details
**UI Element**: User Control Dialog (Desktop)

**Response**:
```json
{
    "success": true,
    "user_id": 123,
    "email": "user@example.com",
    "name": "John Smith",
    "tier": "pro",
    "status": "active",
    "suspended": false,
    "created_at": "2026-01-15T10:00:00Z",
    "custom_limits": {
        "ai_messages_per_day": 50
    },
    "feature_overrides": {
        "guardian_mode": true
    },
    "tier_expires_at": null
}
```

---

### PUT /api/admin/users/{user_id}/subscription
**Purpose**: Update user tier, limits, expiration
**UI Element**: User Control Dialog tier selection, limit inputs

**Request**:
```json
{
    "tier": "premium",
    "custom_limits": {
        "ai_messages_per_day": 100
    },
    "tier_expires_at": "2027-01-15T00:00:00Z"
}
```

---

### PUT /api/admin/users/{user_id}/features
**Purpose**: Enable/disable specific features for user
**UI Element**: User Control Dialog feature checkboxes

**Request**:
```json
{
    "features": {
        "guardian_mode": true,
        "desktop_sync": true,
        "pdf_reports": false
    }
}
```

---

### POST /api/admin/users/{user_id}/suspend
**Purpose**: Suspend user account
**UI Element**: User Control Dialog → "Suspend Account" button

**Request**:
```json
{
    "reason": "Payment failed"
}
```

---

### POST /api/admin/users/{user_id}/activate
**Purpose**: Reactivate suspended account
**UI Element**: User Control Dialog → "Activate Account" button

---

### GET /api/admin/users/{user_id}/audit-log
**Purpose**: Get all admin changes made to user
**UI Element**: User Control Dialog → Audit log table

**Response**:
```json
{
    "success": true,
    "entries": [
        {
            "timestamp": "2026-01-30T14:22:00Z",
            "action": "tier_change",
            "field_name": "tier",
            "old_value": "free",
            "new_value": "pro",
            "admin_id": 1,
            "reason": null
        }
    ]
}
```

---

### GET /api/admin/pricing
**Purpose**: Get current pricing configuration
**UI Element**: Pricing Config Dialog (Desktop)

---

### PUT /api/admin/pricing/{tier}
**Purpose**: Update pricing for a tier
**UI Element**: Pricing Config Dialog save

**Request**:
```json
{
    "price_monthly": 4.99,
    "price_annual": 47.88,
    "currency": "USD",
    "currency_symbol": "$",
    "description": "AI predictions & chat",
    "features_summary": "AI predictions\nChat assistant\n7-day history"
}
```

---

## 9. FCM NOTIFICATIONS

### POST /api/fcm/register
**Purpose**: Register FCM token for push notifications
**UI Element**: Background (no direct UI)
**When Called**: On app startup, on token refresh

**Request**:
```json
{
    "fcm_token": "dGhpcyBpcyBhIHRlc3QgdG9rZW4...",
    "device_type": "android"
}
```

**Response**:
```json
{
    "success": true,
    "message": "FCM token registered"
}
```

---

## 10. UI-TO-ENDPOINT MAPPING

| UI Screen | Endpoints Used |
|-----------|----------------|
| **DRIVER MODE** | |
| Login/Registration | `/api/auth/request-code`, `/api/auth/verify-code`, `/api/auth/device-login` |
| Dashboard (Driver) | `/api/obd/data`, `/api/key/permissions` |
| Predictions | `/api/predict`, `/api/v1/report/{name}` |
| DTC Screen | `/api/obd/dtc`, `/api/obd/dtc/clear` |
| AI Chat | `/api/chat/message` |
| History | `/api/obd/data` (historical query) |
| Driver Settings | `/api/user/devices`, `/api/key/permissions` |
| Paywall | `/api/pricing/public` |
| **GUARDIAN MODE** | |
| Guardian Dashboard | `/api/guardian/dashboard`, `/api/guardian/profiles` |
| Live Monitoring | `/api/guardian/alerts/recent`, `/api/guardian/location-requests/remaining`, `/api/guardian/request-location/{id}` |
| Fleet Management | `/api/guardian/invite`, `/api/guardian/fleet/drivers`, `/api/guardian/vehicles/unlink/{id}` |
| Guardian History | `/api/guardian/profiles/{id}/trips`, `/api/guardian/profiles/{id}/events` |
| Vehicle Detail | `/api/guardian/vehicles/{id}/live`, `/api/guardian/vehicles/{id}/health`, `/api/guardian/telemetry/{id}/latest` |
| Predictions (Guardian) | `/api/guardian/predictions/{id}`, `/api/guardian/predictions/{id}/acknowledge` |
| Geofencing | `/api/guardian/geofences/{id}`, POST `/api/guardian/geofences`, DELETE `/api/guardian/geofences/{id}` |
| Guardian AI Chat | `/api/guardian/chat/message`, `/api/guardian/chat/vehicle-context/{id}` |
| Guardian Settings | `/api/guardian/settings/{id}`, `/api/guardian/notification-preferences` |
| Driver Comparison | `/api/guardian/analytics/compare` |
| **DRIVER CONSENT** | |
| Consent Screen | `/api/driver/consent`, `/api/driver/revoke-consent` |
| Privacy Settings | `/api/driver/monitoring-status`, `/api/driver/guardians` |
| **BACKGROUND SERVICES** | |
| Telemetry (Driver) | `/api/telemetry`, `/api/obd/data` |
| Trip Tracking | `/api/trips/start`, `/api/trips/end` |
| Event Reporting | `/api/events/report`, `/api/events/obd-disconnect`, `/api/events/obd-reconnect` |
| Command Handling | `/api/commands/pending/{id}`, `/api/commands/acknowledge`, `/api/commands/complete` |
| Emergency/Accident | `/api/events/accident`, `/api/commands/location-response` |
| Alert Acknowledgement | `/api/guardian/alerts/{id}/acknowledge` |
| FCM Registration | `/api/fcm/register` |

---

## 11. ERROR CODES

| HTTP Code | Error | UI Action |
|-----------|-------|-----------|
| 401 | `invalid_api_key` | Show login screen |
| 401 | `expired_api_key` | Show login screen |
| 403 | `account_suspended` | Show "Account Suspended" dialog with reason |
| 403 | `device_mismatch` | Show "Re-authenticate on this device" prompt |
| 403 | `feature_locked` | Show paywall for feature |
| 403 | `tier_required` | Show upgrade prompt for required tier |
| 429 | `rate_limited` | Show "Try again later" with retry time |
| 429 | `daily_limit_reached` | Show usage limit dialog |
| 429 | `location_request_limit_reached` | Show "You've used all 3 location requests this month" |
| 429 | `fleet_slot_limit_reached` | Show "You've reached your vehicle limit" with upgrade prompt |
| 500 | `server_error` | Show generic error, retry button |
| 503 | `maintenance` | Show maintenance screen |

**Error Response Format**:
```json
{
    "success": false,
    "error": {
        "code": "feature_locked",
        "message": "This feature requires Pro subscription",
        "required_tier": "pro",
        "upgrade_url": "https://predict.previlium.com/upgrade"
    }
}
```

---

## 12. HEADERS REQUIRED

### All Authenticated Requests

```http
X-API-Key: pk_live_xxxxxxxxxxxxxxxx
X-Device-Id: abc123-unique-device-id
Content-Type: application/json
Accept: application/json
```

### Admin Requests (Desktop Only)

```http
X-Admin-Key: PREDICT-DESKTOP-ADMIN-KEY-2026
Content-Type: application/json
Accept: application/json
```

---

## Appendix: Data Types

### Tier Values
- `free` - Basic access
- `pro` - AI features
- `premium` - Full access + Guardian
- `admin` - Unlimited

### Status Values
- `active` - Normal operation
- `suspended` - Account suspended
- `expired` - Tier expired

### Event Types
- `hard_brake` - Sudden deceleration (>0.5g)
- `rapid_accel` - Sudden acceleration (>0.4g)
- `speeding` - Over speed limit
- `obd_disconnect` - OBD adapter disconnected
- `obd_reconnect` - OBD adapter reconnected
- `trip_start` - Trip started
- `trip_end` - Trip ended

### Accident Types (EMERGENCY)
- `airbag_deployed` - Airbag deployment detected via OBD (HIGHEST PRIORITY)
- `crash_detected` - Severe impact detected via phone sensors
- `emergency_button` - Driver pressed emergency button in app
- `rollover` - Vehicle rollover detected

### Alert Severities
- `critical` - Accidents, airbag deployment (RED - immediate attention)
- `high` - Hard braking, rapid acceleration (ORANGE - attention needed)
- `medium` - Speeding, disconnections (YELLOW - informational)
- `low` - Minor events (GRAY - for records)

### Command Types
- `request_location` - Request driver's location (3/month limit)
- `message` - Send text message to driver
- `obd_reconnect` - Request OBD reconnection

---

---

## Important Notes for UI/UX Developer

### Location Privacy Model
PREDICT does **NOT** continuously track driver location. Location is only shared:
1. **During accidents** - Automatically sent with emergency alert (**NO QUOTA LIMIT**)
2. **On-demand requests** - Guardian requests, driver approves (LIMITED TO 3/MONTH)

**CRITICAL DISTINCTION:**
- Accident/emergency location: **ALWAYS SENT** - never blocked by quota
- Manual "Request Location": **LIMITED TO 3/MONTH** per guardian
- Even if guardian has 0 requests remaining, they WILL receive accident location

This design protects driver privacy while ensuring guardians can ALWAYS respond to emergencies.

### Emergency Alert Flow
1. App detects airbag deployment or crash
2. Alert sent to server immediately
3. Server notifies ALL guardians via FCM push (highest priority)
4. Guardians see alert on Live Monitoring screen
5. Guardian can acknowledge alert with notes

### Location Request Flow
1. Guardian checks remaining quota (`/api/guardian/location-requests/remaining`)
2. If quota available, sends request (`/api/guardian/request-location/{id}`)
3. Driver receives push notification
4. Driver can CHOOSE to share location (`/api/commands/location-response`)
5. Guardian sees location on map

---

---

## Quick Reference for UX/UI Developer

### Screen → Endpoint Checklist

**Driver Mode Screens:**
- [ ] Login → `/api/auth/request-code`, `/api/auth/verify-code`, `/api/auth/device-login`
- [ ] Dashboard → `/api/key/permissions`, `/api/obd/data`
- [ ] Predictions → `/api/predict`
- [ ] AI Chat → `/api/chat/message`
- [ ] DTC Screen → `/api/obd/dtc`, `/api/obd/dtc/clear`
- [ ] Settings → `/api/user/devices`
- [ ] Paywall → `/api/pricing/public`

**Guardian Mode Screens:**
- [ ] Fleet Dashboard → `/api/guardian/dashboard`
- [ ] Live Monitoring → `/api/guardian/alerts/recent`, `/api/guardian/location-requests/remaining`
- [ ] Fleet Management → `/api/guardian/fleet/drivers`, `/api/guardian/invite`
- [ ] Vehicle Detail → `/api/guardian/vehicles/{id}/live`, `/api/guardian/vehicles/{id}/health`
- [ ] Geofencing → `/api/guardian/geofences/{id}`
- [ ] Guardian Settings → `/api/guardian/settings/{id}`, `/api/guardian/notification-preferences`

**Key Flows:**

1. **Emergency Alert Flow** (Automatic):
   - Driver app detects accident → `POST /api/events/accident`
   - Server sends FCM to all guardians (immediate)
   - Guardian sees alert in Live Monitoring → `GET /api/guardian/alerts/recent`
   - Guardian acknowledges → `POST /api/guardian/alerts/{id}/acknowledge`

2. **Location Request Flow** (Manual, 3/month limit):
   - Guardian checks quota → `GET /api/guardian/location-requests/remaining`
   - Guardian requests location → `POST /api/guardian/request-location/{id}`
   - Driver receives FCM notification
   - Driver shares location → `POST /api/commands/location-response`

3. **Driver Invite Flow**:
   - Guardian creates invite → `POST /api/guardian/invite`
   - Driver receives code via email/SMS
   - Driver enters code in app → joins fleet
   - Driver grants consent → `POST /api/driver/consent`

---

*Complete API Reference for UX/UI Developer. Last updated February 2026. Version 2.0*
*Total endpoints documented: 60+*
