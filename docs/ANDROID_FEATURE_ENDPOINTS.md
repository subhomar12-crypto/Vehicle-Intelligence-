# Android App - New Feature Endpoints Implementation Guide

## Session Summary (December 2024)

This document describes **24 new API endpoints** added to the OBDserver that enable the Android app to access all desktop features including:

- **Fuel Tracking** - Log fillups, view history, get statistics (MPG, L/100km)
- **Trip Analytics** - View trip history and statistics
- **Driving Score** - Real-time driving behavior scoring
- **Maintenance Reminders** - Service schedule tracking
- **Custom Alerts** - User-configurable alert rules
- **Geofencing** - GPS zone alerts (desert areas, custom zones)
- **Two-Way Commands** - Desktop ↔ Mobile communication
- **Fleet Management** - Multi-vehicle overview and comparison
- **Data Export** - Export data to CSV/Excel
- **AI Alerts** - AI-generated alert history

---

## Server Connection

**Base URL:** `https://predict.previlium.com`

**Authentication:** All requests require the API key header:
```http
X-API-Key: {your_api_key}
Content-Type: application/json
```

---

## FUEL ECONOMY FEATURE - COMPLETE IMPLEMENTATION

### Overview

The fuel economy feature allows users to:
1. Log fuel fillups with cost, liters, odometer reading
2. View fillup history
3. See calculated statistics (MPG, L/100km, cost per km)
4. Track fuel efficiency trends

### API Endpoints

#### 1. Log Fuel Fillup

**Endpoint:** `POST /api/fuel/fillup`

**Request:**
```json
{
  "liters": 45.5,
  "cost": 180.00,
  "odometer_km": 75230,
  "full_tank": true,
  "fuel_grade": "Regular",
  "station_name": "Qatar Fuel Station"
}
```

**Response:**
```json
{
  "success": true,
  "fillup_data": {
    "fillup_id": "fillup_MyCarProfile_20241227_143052",
    "profile_id": 1,
    "profile_name": "My Car Profile",
    "timestamp": "2024-12-27T14:30:52",
    "liters": 45.5,
    "gallons": 12.02,
    "cost": 180.00,
    "cost_per_liter": 3.956,
    "odometer_km": 75230,
    "odometer_miles": 46738.5,
    "full_tank": true,
    "fuel_grade": "Regular",
    "station_name": "Qatar Fuel Station",
    "calculated_metrics": {
      "distance_since_last_km": 520.0,
      "distance_since_last_miles": 323.1,
      "fuel_consumed_liters": 42.0,
      "fuel_consumed_gallons": 11.09,
      "fuel_efficiency_l_per_100km": 8.08,
      "fuel_efficiency_mpg": 29.1,
      "cost_per_km": 0.346,
      "cost_per_mile": 0.557
    }
  }
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| liters | float | Yes | Liters of fuel added (1-200) |
| cost | float | Yes | Total cost in local currency |
| odometer_km | float | Yes | Current odometer reading in km |
| full_tank | bool | No | Whether tank was filled completely (default: true) |
| fuel_grade | string | No | "Regular", "Premium", "Diesel" (default: "Regular") |
| station_name | string | No | Gas station name for tracking |

---

#### 2. Get Fuel History

**Endpoint:** `GET /api/fuel/history/{profile_id}?days=90`

**Parameters:**
- `profile_id` (path): Vehicle profile ID
- `days` (query): Number of days of history (default: 90)

**Response:**
```json
{
  "success": true,
  "profile_id": 1,
  "days": 90,
  "fillup_count": 12,
  "fillups": [
    {
      "fillup_id": "fillup_MyCarProfile_20241227_143052",
      "timestamp": "2024-12-27T14:30:52",
      "liters": 45.5,
      "gallons": 12.02,
      "cost": 180.00,
      "cost_per_liter": 3.956,
      "odometer_km": 75230,
      "full_tank": true,
      "fuel_grade": "Regular",
      "station_name": "Qatar Fuel Station",
      "calculated_metrics": {
        "fuel_efficiency_mpg": 29.1,
        "fuel_efficiency_l_per_100km": 8.08,
        "cost_per_km": 0.346
      }
    }
    // ... more fillups (most recent first)
  ]
}
```

---

#### 3. Get Fuel Statistics

**Endpoint:** `GET /api/fuel/statistics/{profile_id}?days=90`

**Parameters:**
- `profile_id` (path): Vehicle profile ID
- `days` (query): Analysis period (default: 90)

**Response:**
```json
{
  "success": true,
  "profile_id": 1,
  "statistics": {
    "period_days": 90,
    "fillup_count": 12,
    "total_fuel_liters": 540.5,
    "total_fuel_gallons": 142.8,
    "total_cost": 2150.00,
    "avg_cost_per_liter": 3.978,
    "avg_fuel_efficiency_mpg": 28.5,
    "avg_fuel_efficiency_l_per_100km": 8.25,
    "best_mpg": 32.1,
    "worst_mpg": 24.2,
    "best_l_per_100km": 7.32,
    "worst_l_per_100km": 9.71,
    "avg_cost_per_km": 0.358
  }
}
```

---

### Android UI Implementation for Fuel Economy

#### Suggested Screen Layout

```
┌────────────────────────────────────────────┐
│           FUEL ECONOMY                      │
├────────────────────────────────────────────┤
│  ┌────────────────────────────────────┐    │
│  │  CURRENT EFFICIENCY                 │    │
│  │  ┌─────────┐  ┌─────────┐          │    │
│  │  │  28.5   │  │  8.25   │          │    │
│  │  │   MPG   │  │ L/100km │          │    │
│  │  └─────────┘  └─────────┘          │    │
│  └────────────────────────────────────┘    │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │  MONTHLY SUMMARY                    │    │
│  │  Total Fuel: 540.5 L               │    │
│  │  Total Cost: QAR 2,150             │    │
│  │  Cost per km: QAR 0.36             │    │
│  └────────────────────────────────────┘    │
│                                             │
│  [+ LOG FILLUP]                             │
│                                             │
│  FILLUP HISTORY                             │
│  ┌────────────────────────────────────┐    │
│  │ Dec 27, 2024                        │    │
│  │ 45.5 L @ QAR 180                    │    │
│  │ 29.1 MPG | 8.08 L/100km            │    │
│  │ Qatar Fuel Station                  │    │
│  └────────────────────────────────────┘    │
│  ┌────────────────────────────────────┐    │
│  │ Dec 20, 2024                        │    │
│  │ 42.0 L @ QAR 166                    │    │
│  │ 27.8 MPG | 8.46 L/100km            │    │
│  └────────────────────────────────────┘    │
└────────────────────────────────────────────┘
```

#### Kotlin Data Classes

```kotlin
// Response models
data class FillupResponse(
    val success: Boolean,
    val fillup_data: FillupData?
)

data class FillupData(
    val fillup_id: String,
    val profile_id: Int,
    val profile_name: String,
    val timestamp: String,
    val liters: Double,
    val gallons: Double,
    val cost: Double,
    val cost_per_liter: Double,
    val odometer_km: Double,
    val odometer_miles: Double,
    val full_tank: Boolean,
    val fuel_grade: String,
    val station_name: String?,
    val calculated_metrics: CalculatedMetrics?
)

data class CalculatedMetrics(
    val distance_since_last_km: Double?,
    val fuel_consumed_liters: Double?,
    val fuel_efficiency_mpg: Double?,
    val fuel_efficiency_l_per_100km: Double?,
    val cost_per_km: Double?
)

data class FuelHistoryResponse(
    val success: Boolean,
    val profile_id: Int,
    val days: Int,
    val fillup_count: Int,
    val fillups: List<FillupData>
)

data class FuelStatisticsResponse(
    val success: Boolean,
    val profile_id: Int,
    val statistics: FuelStatistics
)

data class FuelStatistics(
    val period_days: Int,
    val fillup_count: Int,
    val total_fuel_liters: Double,
    val total_cost: Double,
    val avg_fuel_efficiency_mpg: Double?,
    val avg_fuel_efficiency_l_per_100km: Double?,
    val best_mpg: Double?,
    val worst_mpg: Double?,
    val avg_cost_per_km: Double?
)

// Request model
data class FillupRequest(
    val liters: Double,
    val cost: Double,
    val odometer_km: Double,
    val full_tank: Boolean = true,
    val fuel_grade: String = "Regular",
    val station_name: String? = null
)
```

#### Retrofit API Interface

```kotlin
interface FuelApiService {

    @POST("/api/fuel/fillup")
    suspend fun logFillup(
        @Header("X-API-Key") apiKey: String,
        @Body request: FillupRequest
    ): Response<FillupResponse>

    @GET("/api/fuel/history/{profileId}")
    suspend fun getFuelHistory(
        @Header("X-API-Key") apiKey: String,
        @Path("profileId") profileId: Int,
        @Query("days") days: Int = 90
    ): Response<FuelHistoryResponse>

    @GET("/api/fuel/statistics/{profileId}")
    suspend fun getFuelStatistics(
        @Header("X-API-Key") apiKey: String,
        @Path("profileId") profileId: Int,
        @Query("days") days: Int = 90
    ): Response<FuelStatisticsResponse>
}
```

---

## ALL NEW ENDPOINTS REFERENCE

### Fuel Tracking (3 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/fuel/fillup` | Log fuel fillup |
| GET | `/api/fuel/history/{profile_id}` | Get fillup history |
| GET | `/api/fuel/statistics/{profile_id}` | Get fuel statistics |

### Trip Analytics (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trips/history/{profile_id}?limit=20` | Get recent trips |
| GET | `/api/trips/statistics/{profile_id}?days=30` | Get trip statistics |

### Driving Score (1 endpoint)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/driving/score/{profile_id}` | Get driving score (0-100) |

**Driving Score Response:**
```json
{
  "success": true,
  "profile_id": 1,
  "driving_score": 85.5,
  "rating": "Good",
  "emoji": "✅",
  "events": {
    "harsh_brakes": 2,
    "rapid_accels": 1,
    "speeding_events": 0
  },
  "recent_events": [...]
}
```

### Maintenance Reminders (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/maintenance/reminders/{profile_id}?current_odometer_km=75000` | Get due reminders |
| GET | `/api/maintenance/summary/{profile_id}` | Get reminder summary |

### Custom Alerts (4 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/alerts/rules` | Create alert rule |
| GET | `/api/alerts/rules/{profile_id}` | Get all rules |
| PUT | `/api/alerts/rules/{profile_id}/{rule_id}/toggle?enabled=true` | Enable/disable rule |
| DELETE | `/api/alerts/rules/{profile_id}/{rule_id}` | Delete rule |

**Create Alert Rule Request:**
```json
{
  "name": "High Coolant Temperature",
  "parameter": "coolant_temp",
  "condition": "greater_than",
  "threshold": 105,
  "severity": "critical",
  "enabled": true,
  "message_template": "Coolant temperature is {value}°C!"
}
```

**Condition Options:** `greater_than`, `less_than`, `equals`, `between`, `outside`
**Severity Options:** `info`, `warning`, `critical`

### Geofencing (3 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/geofence/check?latitude=25.3&longitude=51.5` | Check location against zones |
| POST | `/api/geofence/create` | Create custom geofence |
| GET | `/api/geofence/active/{profile_id}` | Get zones vehicle is in |

### Commands/Communication (3 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/commands/pending/{profile_id}` | Get pending commands from desktop |
| POST | `/api/commands/response` | Submit command response |
| POST | `/api/commands/request` | Send request to desktop |

### Fleet Management (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fleet/overview` | Get all vehicles |
| GET | `/api/fleet/compare?profile_ids=1,2,3` | Compare vehicles |

### Data Export (1 endpoint)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/export/data` | Export data to CSV/Excel |

**Export Request:**
```json
{
  "export_type": "all",
  "days": 30,
  "format": "csv"
}
```

**Export Types:** `all`, `obd`, `trips`, `fuel`

### AI Alerts (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai-alerts/history/{profile_id}?limit=50` | Get alert history |
| GET | `/api/ai-alerts/active/{profile_id}` | Get active alerts |

### Profile Creation (1 endpoint)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profile/create` | Request profile creation |

---

## IMPORTANT NOTES FOR ANDROID DEVELOPER

1. **All endpoints require API key authentication** via `X-API-Key` header

2. **Fuel Economy is the priority feature** - implement the fillup logging and history display first

3. **Driving Score updates in real-time** - poll every 10-30 seconds when driving

4. **Maintenance reminders need current odometer** - send the latest known odometer reading

5. **Commands endpoint enables two-way communication** - poll `/api/commands/pending` periodically

6. **Geofencing works server-side** - just send GPS coordinates, server handles zone checks

7. **Data export returns file paths** - may need follow-up download endpoint

8. **Error codes:**
   - 401: Invalid API key
   - 402: Subscription expired
   - 429: Rate limited (back off and retry)

---

## TESTING THE NEW ENDPOINTS

You can test these endpoints using curl:

```bash
# Log a fillup
curl -X POST https://predict.previlium.com/api/fuel/fillup \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"liters": 45.5, "cost": 180, "odometer_km": 75230}'

# Get fuel history
curl https://predict.previlium.com/api/fuel/history/1?days=90 \
  -H "X-API-Key: YOUR_API_KEY"

# Get fuel statistics
curl https://predict.previlium.com/api/fuel/statistics/1 \
  -H "X-API-Key: YOUR_API_KEY"

# Get driving score
curl https://predict.previlium.com/api/driving/score/1 \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## VERSION INFO

- **Server Version:** OBDserver with feature_endpoints.py
- **Endpoints Added:** 24 new endpoints
- **Date:** December 27, 2024
- **Compatible with:** Previlium Predict Desktop App v2.x
