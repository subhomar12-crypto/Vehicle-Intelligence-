# Guardian Mode Implementation Documentation

**Project**: PREDICT Vehicle Intelligence Platform
**Date**: January 25, 2026
**Version**: 1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Backend Server Changes](#backend-server-changes)
4. [Android App Implementation](#android-app-implementation)
5. [Desktop App Integration](#desktop-app-integration)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Guardian Mode is a premium feature that allows fleet managers and parents to monitor vehicles and drivers in real-time through the Android app. The implementation includes:

- **Premium dark UI** with glass morphism and gold/blue accents
- **Real-time vehicle monitoring** with search and filtering
- **Detailed vehicle dashboards** showing health, stats, DTCs, and predictions
- **Fleet management** with invite code system
- **Unified database** across Android app, server, and desktop app

---

## Architecture

### Database Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    SERVER DATABASE                          │
│   C:\OBDserver\Previlium_OBD_Server\data\vehicle_data.db   │
│                                                             │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ vehicle_profiles│  │  customers   │  │ fleet_invites │ │
│  │                 │  │              │  │               │ │
│  │ - profile_id    │  │ - id         │  │ - invite_code │ │
│  │ - name          │  │ - name       │  │ - created_by  │ │
│  │ - make/model    │  │ - email      │  │ - expires_at  │ │
│  │ - license_plate │  │ - api_key    │  │ - used_by     │ │
│  │ - customer_id   │  │ - profile_id │  │               │ │
│  └─────────────────┘  └──────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Android App  │    │ Desktop App  │    │   Server     │
│              │    │              │    │              │
│ Registration │    │ Monitoring   │    │ API Backend  │
│ Guardian UI  │    │ Management   │    │ Fleet Mgmt   │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Component Communication

```
Android App ──HTTPS──> Cloudflare Tunnel ──> Server (port 8000)
                         predict.previlium.com

Desktop App ──Direct SQLite Connection──> Server Database
```

---

## Backend Server Changes

### Location
`C:\OBDserver\Previlium_OBD_Server\`

### Database Updates

**File**: `data/vehicle_data.db`

**New/Modified Tables**:
- `vehicle_profiles` - Stores all vehicle profiles
- `customers` - User accounts with API keys
- `fleet_invites` - Invite codes for adding drivers
- `guardians` - Guardian/driver relationships
- `vehicle_guardians` - Links vehicles to guardians

### API Keys Configuration

**File**: `config/api_keys.json`

```json
{
  "key_20260125110017_customer_0": {
    "key_hash": "5a2f84ac22b060563a0ee500b1d67a5eb31c2162c7415bc2bb80488a60144417",
    "name": "omar sobeh",
    "tier": "free",
    "role": "owner",
    "apps": ["obd", "guardian"],
    "profile_id": 2,
    "profile_name": "omar sobeh's nissan patrol",
    "permissions": ["vehicle_data", "predict", "diagnostic"],
    "created": "2026-01-25T11:00:17.127838",
    "status": "active"
  }
}
```

### Guardian API Endpoints

**Base URL**: `https://predict.previlium.com/api`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/key/permissions` | GET | Get user permissions and access levels |
| `/fleet/vehicles` | GET | List all fleet vehicles |
| `/fleet/dashboard` | GET | Fleet overview stats |
| `/fleet/invite` | POST | Create fleet invite code |
| `/fleet/join/{code}` | POST | Join fleet with invite code |
| `/vehicle_data/stats/{profile_id}` | GET | Vehicle statistics |
| `/dtc/active/{profile_id}` | GET | Active diagnostic trouble codes |
| `/predictions/{profile_id}` | GET | AI failure predictions |
| `/vehicle_data/recent_trips/{profile_id}` | GET | Recent trip history |

### Cloudflare Tunnel Configuration

**File**: `C:\cloudflared\config.yml`

```yaml
tunnel: f8b3330f-20e8-4584-b08e-a646b01a78f1
credentials-file: C:\Users\Omars\.cloudflared\f8b3330f-20e8-4584-b08e-a646b01a78f1.json

ingress:
  - hostname: predict.previlium.com
    service: http://localhost:8000
  - hostname: pdf.previlium.com
    service: http://localhost:8001
  - hostname: ai.previlium.com
    service: http://localhost:12580
  - service: http_status:404
```

**Port Change**: Updated from port 3000 → **8000** to match server

---

## Android App Implementation

### Location
`c:\New APK\`

### New Files Created

#### 1. Theme
- `app/src/main/java/com/predict/app/ui/theme/GuardianTheme.kt`
  - Premium dark theme with gold (#D4AF37) and blue accents
  - Glass morphism styling
  - Status colors (driving/idle/offline)

#### 2. Data Models
- `app/src/main/java/com/predict/app/data/models/guardian/GuardianVehicleDetail.kt`
  - Vehicle detail data structures
  - Health breakdown
  - Trip statistics
  - Telemetry data

- `app/src/main/java/com/predict/app/data/models/guardian/GuardianApiModels.kt`
  - API request/response models
  - Fleet dashboard response
  - Vehicle stats response

#### 3. Repository
- `app/src/main/java/com/predict/app/data/repository/GuardianRepository.kt`
  - Data access layer for Guardian APIs
  - Methods: `getFleetVehicles()`, `getVehicleStats()`, `getActiveDTCs()`, etc.

#### 4. ViewModel
- `app/src/main/java/com/predict/app/ui/viewmodels/GuardianViewModel.kt`
  - State management with StateFlow
  - Real-time polling (dashboard: 30s, detail: 5s)
  - Search/filter functionality
  - Implements `InviteCapable` interface

- `app/src/main/java/com/predict/app/ui/viewmodels/InviteCapable.kt`
  - Shared interface for invite functionality
  - Used by both FleetViewModel and GuardianViewModel

#### 5. UI Components
- `app/src/main/java/com/predict/app/ui/components/guardian/GuardianVehicleCard.kt`
  - Premium vehicle cards with glass morphism
  - Status badges (colored by state)
  - Real-time speed and health indicators

- `app/src/main/java/com/predict/app/ui/components/guardian/GuardianSearchBar.kt`
  - Search by driver name or license plate

- `app/src/main/java/com/predict/app/ui/components/guardian/HealthScoreIndicator.kt`
  - Circular health score visualization

- `app/src/main/java/com/predict/app/ui/components/guardian/GuardianMetricCard.kt`
  - Reusable metric display cards

#### 6. Screens
- `app/src/main/java/com/predict/app/ui/screens/guardian/VehicleDetailScreen.kt`
  - Full vehicle dashboard
  - Sections: header, speed/trip, health, fuel, predictions, DTCs, trips, location

- `app/src/main/java/com/predict/app/ui/screens/guardian/CreateInviteDialog.kt`
  - Dialog for creating fleet invite codes
  - Supports both FleetViewModel and GuardianViewModel

### Modified Files

#### 1. Navigation
- `app/src/main/java/com/predict/app/navigation/MainNavigationApp.kt`
  - Added `selectedVehicle` state
  - Added `showCreateInviteDialog` state
  - Navigation between dashboard and detail screens
  - Integrated CreateInviteDialog

#### 2. API Service
- `app/src/main/java/com/predict/app/data/predict/CloudApiService.kt`
  - Added Guardian API endpoint definitions

#### 3. Fleet Dashboard
- `app/src/main/java/com/predict/app/ui/screens/guardian/FleetDashboardScreen.kt`
  - Added search bar
  - Replaced basic cards with GuardianVehicleCard
  - Added pull-to-refresh
  - Connected to GuardianViewModel

#### 4. Server Configuration
- `app/src/main/java/com/predict/app/network/CloudServerConfig.kt`
  - **URL**: `https://predict.previlium.com` (production)
  - Changed from local testing URL

---

## Desktop App Integration

### Location
`C:\D Drive\Predict\`

### Database Configuration Change

**File**: `config.py`

**Before**:
```python
@property
def PROFILES_DB_PATH(self) -> Path:
    """Vehicle profiles database file path"""
    return self.DATA_DIR / "vehicle_profiles.db"
```

**After**:
```python
@property
def PROFILES_DB_PATH(self) -> Path:
    """
    Vehicle profiles database file path.
    Now points to server database for automatic sync with Android app.
    """
    # Use server database for unified profile storage
    server_db = self.SERVER_DIR / "data" / "vehicle_data.db"
    if server_db.exists():
        return server_db

    # Fallback to local database if server database doesn't exist
    return self.DATA_DIR / "vehicle_profiles.db"
```

### Impact

✅ **Automatic Sync**: Any profile registered via Android app now appears in desktop app immediately
✅ **Single Source of Truth**: All apps read from same database
✅ **No Manual Sync Required**: Profiles stay in sync automatically

---

## Database Schema

### vehicle_profiles Table (Server)

| Column | Type | Description |
|--------|------|-------------|
| profile_id | INTEGER | Primary key |
| customer_id | INTEGER | Foreign key to customers table |
| name | TEXT | Vehicle profile name |
| make | TEXT | Vehicle manufacturer |
| model | TEXT | Vehicle model |
| year | INTEGER | Vehicle year |
| vin | TEXT | Vehicle identification number |
| license_plate | TEXT | License plate number |
| category | TEXT | Vehicle category (Personal/Commercial) |
| created_at | REAL | Creation timestamp |
| updated_at | REAL | Last update timestamp |

### customers Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Customer full name |
| email | TEXT | Email address |
| phone | TEXT | Phone number |
| car_plate | TEXT | License plate |
| api_key | TEXT | Plain API key (sent via email) |
| api_key_hash | TEXT | Hashed API key for validation |
| tier | TEXT | Subscription tier (free/premium) |
| profile_id | INTEGER | Linked vehicle profile |
| verified | INTEGER | Email verification status |
| created_at | REAL | Registration timestamp |

### fleet_invites Table

| Column | Type | Description |
|--------|------|-------------|
| invite_code | TEXT | Primary key, unique invite code |
| created_by | INTEGER | Customer ID who created invite |
| vehicle_label | TEXT | Optional label for invited vehicle |
| expires_at | REAL | Expiration timestamp (24 hours) |
| used_by | INTEGER | Customer ID who used invite |
| used_at | REAL | Timestamp when used |
| status | TEXT | active/used/expired |

---

## Configuration

### Environment Setup

#### 1. Server Startup

**Automatic (Recommended)**:
```
Double-click: C:\OBDserver\Start Predict Server with Tunnel.vbs
```

**Manual**:
```bash
cd C:\OBDserver\Previlium_OBD_Server
python run_server.py
```

**With Tunnel**:
```bash
cd C:\cloudflared
cloudflared.exe tunnel --config config.yml run
```

#### 2. Desktop App

**Database Path**: Automatically points to `C:\OBDserver\Previlium_OBD_Server\data\vehicle_data.db`

No configuration needed - will automatically sync with server.

#### 3. Android App

**Server URL**: `https://predict.previlium.com`
**API Key**: Sent via email upon registration

---

## API Key System

### Registration Flow

1. User registers via Android app
2. Server generates API key: `PREDICT-XXXX-XXXX-XXXX-XXXX`
3. API key sent to user's email
4. User enters API key in app
5. App validates key via `/api/key/permissions`
6. User granted Driver/Guardian access based on permissions

### Example API Key
```
PREDICT-7ZL1-VZEG-PRP0-USDI
```

### Permissions Response
```json
{
  "success": true,
  "permissions": {
    "has_driver_access": true,
    "has_guardian_access": true,
    "max_vehicles": 1,
    "subscription_tier": "free",
    "role": "owner",
    "features": ["vehicle_data", "predictions", "diagnostics"]
  },
  "key_info": {
    "key_id": "key_20260125110017_customer_0",
    "name": "omar sobeh",
    "profile_id": 2,
    "profile_name": "omar sobeh's nissan patrol"
  },
  "fleet_info": null
}
```

---

## Troubleshooting

### Issue: Android app shows "connection timeout"

**Cause**: Cloudflare tunnel not connected

**Fix**:
```bash
# Kill existing tunnel processes
taskkill /F /IM cloudflared.exe

# Restart tunnel
cd C:\cloudflared
cloudflared.exe tunnel --config config.yml run
```

**Verify**:
```bash
curl https://predict.previlium.com/health
# Should return: {"status":"healthy"}
```

---

### Issue: Profile not showing in desktop app

**Cause**: Desktop app was using old local database

**Fix**: Already implemented - desktop app now reads from server database

**Verify**:
```python
# Check desktop app database path
from config import get_config
cfg = get_config()
print(cfg.PROFILES_DB_PATH)
# Should print: C:\OBDserver\Previlium_OBD_Server\data\vehicle_data.db
```

---

### Issue: API authentication error

**Causes**:
1. Server not running
2. Tunnel not connected
3. Invalid API key

**Fix**:
1. Check server status: `curl http://localhost:8000/health`
2. Check tunnel status: `curl https://predict.previlium.com/health`
3. Verify API key in `C:\OBDserver\Previlium_OBD_Server\config\api_keys.json`

---

### Issue: Tunnel keeps disconnecting

**Cause**: Multiple cloudflared processes running

**Fix**:
```bash
# Kill all cloudflared processes
taskkill /F /IM cloudflared.exe

# Start single instance
cd C:\cloudflared
cloudflared.exe tunnel --config config.yml run
```

---

## Testing Checklist

### Backend
- [ ] Server starts successfully on port 8000
- [ ] Cloudflare tunnel connects (4 connections)
- [ ] `/health` endpoint returns 200
- [ ] `/api/key/permissions` validates API key
- [ ] `/api/fleet/vehicles` returns vehicle list

### Android App
- [ ] Registration creates customer and sends API key email
- [ ] API key authentication works
- [ ] Fleet dashboard loads vehicles
- [ ] Search filters by name/plate
- [ ] Vehicle detail screen shows all data
- [ ] Pull-to-refresh updates data
- [ ] Create invite generates code

### Desktop App
- [ ] Profile appears immediately after registration
- [ ] No manual sync needed
- [ ] Vehicle data matches Android app
- [ ] Profile selection works

---

## File Locations Reference

### Server
```
C:\OBDserver\Previlium_OBD_Server\
├── data/
│   └── vehicle_data.db          # Main database
├── config/
│   └── api_keys.json            # API key storage
├── main.py                       # FastAPI server
└── run_server.py                # Server startup script
```

### Desktop App
```
C:\D Drive\Predict\
├── config.py                    # Modified for server DB
├── data/
│   └── vehicle_profiles.db      # Legacy (no longer used)
└── main_pyside.py               # Desktop app entry point
```

### Android App
```
c:\New APK\app\src\main\java\com\predict\app\
├── ui/
│   ├── theme/GuardianTheme.kt
│   ├── viewmodels/
│   │   ├── GuardianViewModel.kt
│   │   └── InviteCapable.kt
│   ├── components/guardian/
│   │   ├── GuardianVehicleCard.kt
│   │   ├── GuardianSearchBar.kt
│   │   ├── HealthScoreIndicator.kt
│   │   └── GuardianMetricCard.kt
│   └── screens/guardian/
│       ├── FleetDashboardScreen.kt
│       ├── VehicleDetailScreen.kt
│       └── CreateInviteDialog.kt
├── data/
│   ├── models/guardian/
│   │   ├── GuardianVehicleDetail.kt
│   │   └── GuardianApiModels.kt
│   └── repository/
│       └── GuardianRepository.kt
└── network/
    └── CloudServerConfig.kt        # Server URL config
```

### Cloudflare
```
C:\cloudflared\
├── cloudflared.exe
├── config.yml                   # Tunnel configuration
└── credentials-file: C:\Users\Omars\.cloudflared\
    └── f8b3330f-20e8-4584-b08e-a646b01a78f1.json
```

---

## Summary of Changes

### Phase 1: Backend Infrastructure ✅
- Updated Cloudflare tunnel port (3000 → 8000)
- Configured API key system
- Synced customer and profile databases

### Phase 2: Android Guardian Mode ✅
- Created 10 new files (theme, models, repository, viewmodel, components, screens)
- Modified 4 files (navigation, API service, dashboard, dialog)
- Implemented premium dark UI with glass morphism
- Added real-time polling and search functionality

### Phase 3: Desktop Integration ✅
- Modified `config.py` to use server database
- Eliminated need for manual sync
- Single source of truth for all platforms

---

## Next Steps (Future Enhancements)

### Phase 4: Advanced Features (Future)
- [ ] Emergency location request
- [ ] Remote OBD reconnect command
- [ ] LLM chat for vehicle-specific questions
- [ ] Push notifications for alerts
- [ ] Geofence breach alerts
- [ ] Speed limit warnings

---

## Support

For issues or questions:
1. Check this documentation first
2. Verify server and tunnel are running
3. Check database sync status
4. Review API key permissions

---

**End of Documentation**
