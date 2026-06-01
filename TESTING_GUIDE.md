# PREDICT Platform - Testing & Data Collection Guide

> Quick start guide for testing the system and collecting data
> Last Updated: January 17, 2026

---

## Quick Start

### 1. Start the Server (Recommended Method)

**Option A: Using Server GUI (Recommended)**
```
Double-click: C:\OBDserver\Start Predict Server.vbs
```
This opens the Server Control Panel which starts both:
- OBD Server (port 8000)
- LLM Server (port 12580)

**Option B: Manual Start**
```bash
# Terminal 1: OBD Server
cd C:\OBDserver\Previlium_OBD_Server
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: LLM Server
cd "C:\D Drive\Predict"
python llm_api_server.py
```

### 2. Verify Server is Running

```bash
# Test OBD Server
curl http://localhost:8000/api/health

# Test LLM Server
curl http://localhost:12580/health
```

Expected response: `{"status": "healthy", ...}`

---

## Server Components

| Component | Port | URL | Health Check |
|-----------|------|-----|--------------|
| OBD Server | 8000 | http://localhost:8000 | `/api/health` |
| LLM Server | 12580 | http://localhost:12580 | `/health` |
| Tunnel | 443 | https://api.previlium.com | External access |

---

## Data Collection Endpoints

### 1. Real-time Vehicle Data
Send telemetry from OBD app:

```bash
curl -X POST http://localhost:8000/api/vehicle_data \
  -H "Authorization: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "rpm": 1500,
    "speed": 60,
    "coolant_temp": 85,
    "battery_voltage": 12.6,
    "engine_load": 45,
    "timestamp": "2026-01-17T12:00:00Z"
  }'
```

### 2. Batch Data Upload
Upload multiple records at once:

```bash
curl -X POST http://localhost:8000/api/data/batch \
  -H "Authorization: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "records": [
      {"rpm": 1500, "speed": 60, "timestamp": "2026-01-17T12:00:00Z"},
      {"rpm": 1600, "speed": 65, "timestamp": "2026-01-17T12:01:00Z"},
      {"rpm": 1700, "speed": 70, "timestamp": "2026-01-17T12:02:00Z"}
    ]
  }'
```

### 3. Data Validation
Validate data before submission:

```bash
curl -X POST http://localhost:8000/api/data/validate \
  -H "Authorization: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "data": {"rpm": 1500, "speed": 60}
  }'
```

### 4. Collection Statistics
Get data collection stats:

```bash
curl http://localhost:8000/api/data/stats/1 \
  -H "Authorization: YOUR_API_KEY"
```

---

## Database Location

**Main Database:**
```
C:\D Drive\Predict\PredictData\vehicle_profiles.db
```

**View Tables:**
```bash
sqlite3 "C:\D Drive\Predict\PredictData\vehicle_profiles.db" ".tables"
```

**Sample Query:**
```bash
sqlite3 "C:\D Drive\Predict\PredictData\vehicle_profiles.db" \
  "SELECT COUNT(*) FROM vehicle_data;"
```

---

## Android App Testing

### PredictOBD App
1. Open the app on Android device
2. Go to Settings > Server Configuration
3. Set server URL: `http://YOUR_PC_IP:8000` (local) or `https://api.previlium.com` (tunnel)
4. Enter API key from Server > API Keys tab
5. Connect to OBD adapter
6. Data will stream to server automatically

### Guardian App
1. Open the app
2. Login with API key
3. View dashboard for vehicle status
4. AI Chat connects to LLM server

---

## LLM Testing

### Test Chat Endpoint
```bash
curl -X POST http://localhost:12580/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the status of my vehicle?",
    "api_key": "YOUR_API_KEY"
  }'
```

### Test via Server Proxy
```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Authorization: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze my battery health"
  }'
```

---

## Troubleshooting

### Server Won't Start
1. Check if port 8000/12580 is in use:
   ```bash
   netstat -ano | findstr :8000
   netstat -ano | findstr :12580
   ```
2. Kill existing process or use different port

### Database Not Found
1. Verify path exists: `C:\D Drive\Predict\PredictData\`
2. Check database file: `vehicle_profiles.db`
3. If missing, run desktop app to create it

### LLM Not Responding
1. Check LLM server is running on port 12580
2. Verify Ollama is installed and model is loaded
3. Test: `curl http://localhost:12580/health`

### Android App Can't Connect
1. Ensure phone and PC are on same network
2. Check Windows Firewall allows ports 8000/12580
3. Use PC's local IP (not localhost)
4. Test: `ping YOUR_PC_IP` from phone

---

## API Keys

### Get Your API Key
1. Open Desktop App
2. Go to Server tab
3. View API Keys section
4. Copy your key

### Create New API Key
1. Server tab > API Keys > Add Key
2. Set name, tier, permissions
3. Copy the generated key

---

## Health Monitoring

### Full Health Check
```bash
curl http://localhost:8000/api/monitor/health
```

### Resource Usage
```bash
curl http://localhost:8000/api/monitor/resources
```

### System Status
```bash
curl http://localhost:8000/api/monitor/status
```

---

## Common Test Scenarios

### Scenario 1: Basic Data Collection
1. Start server
2. Connect OBD app
3. Drive for 10 minutes
4. Check desktop app for new data

### Scenario 2: AI Predictions
1. Collect at least 100 data points
2. Open Desktop > AI Training > Train
3. Go to Predictions tab
4. Verify predictions appear

### Scenario 3: LLM Chat
1. Ensure LLM server is running
2. Open Guardian app > AI Chat
3. Ask: "What's the status of my vehicle?"
4. Verify response uses real data

---

## Files Reference

| Purpose | Location |
|---------|----------|
| Server GUI | `C:\OBDserver\Previlium_OBD_Server\server_gui.py` |
| OBD Server | `C:\OBDserver\Previlium_OBD_Server\main.py` |
| LLM Server | `C:\D Drive\Predict\llm_api_server.py` |
| Desktop App | `C:\D Drive\Predict\main_pyside.py` |
| Database | `C:\D Drive\Predict\PredictData\vehicle_profiles.db` |
| API Keys | `C:\OBDserver\config\api_keys.json` |

---

## Ready for Production Testing

The system is now ready for:
- [x] Real-time data collection from OBD app
- [x] LLM chat functionality
- [x] Health monitoring
- [x] Batch data upload
- [x] API key authentication

Focus on Android app finalization - the server infrastructure is complete.
