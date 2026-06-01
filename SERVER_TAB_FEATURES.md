# Server Tab - Complete Feature List

## Overview
The **Server Tab** (formerly "Cloud Sync" tab) is now a comprehensive mobile server management interface. It provides all tools needed to manage the Android OBD app connection, API keys, and database.

---

## ✅ What's Been Implemented

### 1. **API Key Management** 🔑

#### Generate Custom API Keys
- ➕ **Generate New Key** button
- Prompts for customer name (e.g., "Customer - John Doe" or "Device #1")
- Generates secure 32-character API key
- Only shown once (security best practice)
- Copy to clipboard functionality
- Keys stored as hashes for security

#### View API Keys Table
- Table showing all generated keys
- Columns: Name, Key (hidden), Created date, Actions
- **Copy Key** button (shows security warning)
- Keys are hashed - original keys cannot be retrieved

#### Export/View Keys
- 👁️ **View Keys File** - Shows JSON configuration
- 📤 **Export Keys** - Export list to text file (without actual keys)
- Full audit trail of all generated keys

### 2. **Mobile Server Control** 📱

#### Server Status Display
- Real-time status: "Running ✓" or "Stopped"
- Color-coded (green = running, red = stopped)
- Port information (8080)
- Connection count (if available)
- Data points received today

#### Start/Stop Server
- **Start Server** / **Stop Server** button
- One-click server control
- Automatic status updates
- Integrates with mobile_server_wrapper

### 3. **Database Management** 💾

#### Database Statistics
- **Total Records**: Number of mobile OBD data points stored
- **Vehicles**: Number of unique vehicles/profiles
- **Size**: Database file size in MB
- **Last Update**: Timestamp of most recent data
- **Database Path**: Full path with "Open Folder" button

#### Database Operations
- 📊 **Query Data**: Query mobile data by vehicle profile
- 📄 **Export CSV**: Export vehicle data to CSV file
- 💾 **Backup Database**: Create backup of SQLite database
- 📁 **Open Folder**: Open database directory in file explorer

### 4. **Network Information** 🌐

#### Network Interfaces Display
- Shows all network adapters
- IPv4 addresses for each interface
- IPv6 addresses (if available)
- MAC addresses
- Clear instructions for Android app setup

#### Android App Setup Instructions
- Shows IP addresses to use
- Port number (8080)
- Where to enter API key
- Complete configuration guide

### 5. **Auto-Refresh System** 🔄

#### Automatic Updates
- Stats refresh every 5 seconds
- Server status monitoring
- Database statistics updates
- Network info updates
- **Refresh** button for manual updates

---

## 🔧 Backend Functions Added

### New Server Module Functions

#### 1. `get_mobile_data_by_profile(profile_id, limit=100)`
```python
# Get latest mobile data for a specific vehicle
data = server.get_mobile_data_by_profile("nissan_patrol_2020", limit=100)
# Returns: List of dictionaries with all OBD data
```

#### 2. `get_mobile_sessions_by_profile(profile_id)`
```python
# Get summary of all mobile sessions
sessions = server.get_mobile_sessions_by_profile("nissan_patrol_2020")
# Returns: List with date, record count, avg rpm, avg speed per session
```

#### 3. `get_mobile_data_by_date_range(profile_id, start_date, end_date)`
```python
# Query data for specific date range
data = server.get_mobile_data_by_date_range(
    "nissan_patrol_2020",
    "2025-12-01",
    "2025-12-09"
)
# Returns: All records in date range
```

#### 4. `export_mobile_data_to_csv(profile_id, output_file)`
```python
# Export to CSV
success = server.export_mobile_data_to_csv(
    "nissan_patrol_2020",
    "export.csv"
)
# Returns: True if successful
```

---

## 📊 UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  🖥️ Server Management                          🔄 Refresh   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📱 Mobile Server Status                              │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Server: Running ✓              Port: 8080            │   │
│  │ Connections: 0     Data Points Today: 0             │   │
│  │                                                       │   │
│  │ [Stop Server]                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔑 API Keys for Android App                          │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Generate API keys for authentication                 │   │
│  │                                                       │   │
│  │ ┌──────────────────────────────────────────────┐   │   │
│  │ │ Name         │ Key      │ Created   │Actions │   │   │
│  │ │ Customer A   │ ••••••••│ 2025-12-09│[Copy]  │   │   │
│  │ │ Customer B   │ ••••••••│ 2025-12-08│[Copy]  │   │   │
│  │ └──────────────────────────────────────────────┘   │   │
│  │                                                       │   │
│  │ [➕ Generate New Key] [👁️ View Keys] [📤 Export]    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💾 Mobile Data Database                              │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Total Records: 1,234  Vehicles: 3  Size: 12.5 MB    │   │
│  │ Last Update: 2025-12-09 14:20:00                    │   │
│  │ 📁 D:/car_ai_server/data/predictai.db [Open Folder]│   │
│  │                                                       │   │
│  │ [📊 Query Data] [📄 Export CSV] [💾 Backup Database]│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🌐 Network Information                               │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Interface: Wi-Fi                                     │   │
│  │   IPv4: 192.168.1.100                               │   │
│  │   IPv6: fe80::xxxx                                  │   │
│  │   MAC: XX:XX:XX:XX:XX:XX                            │   │
│  │                                                       │   │
│  │ 📱 Android App Setup: Use IP above with port 8080    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 How To Use

### For Desktop Users:

#### 1. **Generate API Key for Customer**
1. Go to **Server** tab
2. Click **➕ Generate New Key**
3. Enter customer name (e.g., "Customer - John Smith")
4. Copy the generated key (shown only once!)
5. Give key to customer for their Android app

#### 2. **Start Mobile Server**
1. Go to **Server** tab
2. Click **Start Server**
3. Note your PC's IP address from "Network Information" section
4. Configure firewall to allow port 8080

#### 3. **Monitor Incoming Data**
1. Server tab shows real-time connection status
2. Database stats update every 5 seconds
3. See total records and latest update time

#### 4. **Export Customer Data**
1. Click **📄 Export CSV**
2. Enter vehicle profile name
3. Choose save location
4. CSV file contains all mobile OBD data

#### 5. **Query Historical Data**
1. Click **📊 Query Data**
2. Enter vehicle profile name
3. View summary of available data

### For Android App Users:

#### Configuration:
1. Get API key from desktop user
2. Get PC IP address (shown in Network Information)
3. Configure Android app:
   - Server IP: `192.168.x.x` (from desktop)
   - Port: `8080`
   - API Key: (provided by desktop user)

---

## 🔒 Security Features

### API Key Security
- Keys generated using `secrets.token_urlsafe(32)` (cryptographically secure)
- Keys stored as SHA-256 hashes, not plain text
- Original keys shown only once during generation
- Cannot retrieve original key from storage

### Database Security
- SQLite with parameterized queries (prevents SQL injection)
- Input sanitization on all received data
- Rate limiting on HTTP requests
- IP-based lockout after failed authentication

### Network Security
- API key authentication required for all requests
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Request size limits (prevents DoS)
- Audit logging of all access attempts

---

## 📝 Usage Examples

### Example 1: New Customer Setup
```
1. Customer buys your service
2. Desktop user goes to Server tab
3. Clicks "Generate New Key"
4. Enters "Customer - [Name]"
5. Copies generated key
6. Emails key + IP address to customer
7. Customer configures Android app
8. Customer starts driving - data flows automatically
9. Desktop user can export CSV anytime
```

### Example 2: Multiple Vehicles
```
Customer has 3 vehicles:
1. Generate 3 separate API keys
   - "Customer A - Vehicle 1"
   - "Customer A - Vehicle 2"
   - "Customer A - Vehicle 3"
2. Each phone gets unique key
3. All data stored in same database
4. Export by vehicle profile name
```

### Example 3: Data Analysis
```
1. Customer drives for 1 month
2. Desktop user clicks "Query Data"
3. Enters vehicle profile name
4. Sees summary: 1,234 records, avg RPM, avg speed
5. Clicks "Export CSV"
6. Opens in Excel for analysis
7. Creates custom reports for customer
```

---

## 🚀 What's Next

### Possible Future Enhancements:
1. **Auto-Load Mobile Data on Profile Selection** (documented in DESKTOP_DATA_HANDLING_ANALYSIS.md)
2. **Unified Session Viewer** (USB + Android data together)
3. **Database Cleanup/Archiving** (auto-delete old data)
4. **Automatic Daily Backups**
5. **Real-time Dashboard Stats Widget**
6. **Multiple API Key Permissions** (read-only vs full access)
7. **API Key Expiration Dates**
8. **Customer Portal** (web interface for customers to view their own data)

---

## 📂 Files Modified/Created

### New Files:
- `server_tab.py` - Complete server management UI
- `SERVER_TAB_FEATURES.md` - This documentation

### Modified Files:
- `main_pyside.py` - Imports ServerTab instead of CloudSyncTab
- `server_module.py` - Added 4 query functions for data retrieval

### Files Renamed/Replaced:
- `cloud_sync_tab.py` → Kept for backward compatibility, but replaced by `server_tab.py`

---

## ✅ Testing Checklist

- [x] Server tab loads without errors
- [x] Can generate API keys
- [x] Keys are stored as hashes
- [x] Can start/stop mobile server
- [x] Server status updates correctly
- [x] Database stats display properly
- [x] Network information shows correctly
- [x] Can query database by profile
- [x] Can export to CSV
- [x] Can backup database
- [x] Auto-refresh works (5 second interval)
- [x] Manual refresh button works

---

## 🎉 Summary

The Server tab is now a **complete mobile server management solution**:
- ✅ Generate secure API keys for each customer
- ✅ Control mobile server (start/stop)
- ✅ Monitor database in real-time
- ✅ Query and export customer data
- ✅ View network configuration for Android app setup
- ✅ All statistics auto-refresh every 5 seconds

**Desktop app is now production-ready for customer deployments!** 🚗📱
