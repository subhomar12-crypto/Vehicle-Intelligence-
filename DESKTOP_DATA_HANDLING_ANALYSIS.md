# Desktop Application - Data Handling Analysis & Upgrade Recommendations

## Current State Analysis

### ✅ What's Already Working

#### 1. **Automatic Data Reception** ✅
- **Mobile Server Polling**: Checks for incoming Android data every 1 second
- **Location**: `mobile_server_wrapper.py:57` - `self._check_timer.start(1000)`
- **Status**: **FULLY AUTOMATIC** - No user action needed

#### 2. **Automatic Data Flow** ✅
- **Signal Chain**:
  ```
  Android App → HTTP Server → Mobile Wrapper → Mobile Bridge → Main App → All Tabs
  ```
- **Locations**:
  - `main_pyside.py:2787-2789` - Signal connections
  - `main_pyside.py:3160-3178` - Data handlers
  - `main_pyside.py:3195-3224` - Live data processing
- **Status**: **FULLY AUTOMATIC** - Data flows through entire pipeline automatically

#### 3. **Automatic Data Logging (JSON Files)** ✅
- **What Gets Logged**: All live OBD data from both USB and Android sources
- **Location**: `main_pyside.py:3224` - `self.data_logger.log_data(data)`
- **File Format**: JSON lines (one data point per line)
- **Save Path**: `./data/logs/session_YYYYMMDD_HHMMSS.json`
- **Status**: **FULLY AUTOMATIC** - Logs every data point received

#### 4. **Automatic Database Storage (SQLite)** ✅
- **What Gets Saved**: Android OBD data in flat format
- **Location**: `server_module.py:875-927` - `save_to_database()`
- **Database Path**: `D:/car_ai_server/data/predictai.db`
- **Table**: `mobile_vehicle_data`
- **Backup**: Also saves JSON backup to `D:/car_ai_server/data/mobile_data/`
- **Status**: **FULLY AUTOMATIC** - Saves every Android data upload

#### 5. **Real-Time Updates** ✅
- **Live Data Tab**: Updates gauges automatically
- **AI Insights Tab**: Processes data in real-time
- **Forecast Tab**: Updates predictions
- **Service History**: Logs anomalies
- **Status**: **FULLY AUTOMATIC** - All tabs update without user action

---

## ❌ What's Missing - Critical Gaps

### 1. **No Query/Retrieval Functions for Mobile Database** ❌

**Problem**: Data is saved to SQLite but there's no way to retrieve it!

**Current State**:
- ✅ Saves to database: `save_to_database()`
- ❌ No function to query by profile
- ❌ No function to get historical data
- ❌ No function to load past sessions from mobile DB
- ❌ Can only see stats, not actual data

**Impact**:
- Users can't view historical Android OBD data
- Can't compare past sessions
- Can't load previous trips
- Data is trapped in database

**What's Needed**:
```python
# Missing functions:
- get_mobile_data_by_profile(profile_id, start_date, end_date)
- get_mobile_data_by_date(date)
- get_latest_mobile_session(profile_id)
- export_mobile_data_to_csv(profile_id)
```

---

### 2. **No Automatic Loading of Historical Data on Profile Load** ❌

**Problem**: When user loads a vehicle profile, past mobile data doesn't load

**Current State**:
- When profile loads: Only sets active profile
- Historical mobile data: Ignored
- Past sessions: Must manually browse in Reports tab
- No integration between profile and mobile database

**What Should Happen**:
```
User loads "Nissan Patrol 2020" profile
↓
App automatically queries mobile_vehicle_data table
↓
Loads last 100 data points for this profile
↓
Shows in dashboard: "Last Android session: 2 days ago, 156 data points"
↓
User can click to view full history
```

**What's Needed**:
- Auto-query mobile DB when profile loads
- Display summary of available mobile data
- Quick access to past sessions
- Merge USB and Android history view

---

### 3. **No Integration Between JSON Logs and SQLite Database** ❌

**Problem**: Data is saved in TWO separate places with no unification

**Current State**:
- **USB OBD Data**: Saved to `./data/logs/session_*.json` (JSON)
- **Android OBD Data**: Saved to `D:/car_ai_server/data/predictai.db` (SQLite)
- No unified view
- No way to compare USB vs Android sessions
- Reports tab only reads JSON logs, not SQLite

**Impact**:
- Fragmented data storage
- Can't see full vehicle history
- Android data isolated from desktop analytics
- Users confused about where data is

**What's Needed**:
- Unified data viewer showing both sources
- Option to export mobile DB data to JSON format
- Reports tab should read from both JSON and SQLite
- Single "Session History" with all trips (USB + Android)

---

### 4. **No Automatic Data Cleanup/Archiving** ❌

**Problem**: Data accumulates indefinitely, no cleanup strategy

**Current State**:
- SQLite database grows forever
- JSON log files never deleted
- JSON backups in mobile_data folder accumulate
- No automatic archiving

**Potential Issues**:
- Database size grows to GBs
- Slow queries after months of data
- Disk space issues
- Performance degradation

**What's Needed**:
- Auto-archive data older than X months
- Compress old JSON logs
- Database vacuum on startup
- Configurable retention policy

---

### 5. **No Data Export from Mobile Database** ❌

**Problem**: Can't export Android data for external analysis

**Current State**:
- Can export JSON logs (already in JSON)
- Can't export SQLite mobile data
- No CSV export option
- No way to share Android trip data

**What's Needed**:
- Export mobile data to CSV
- Export to PDF report
- Export to Excel format
- Share trip data feature

---

## 🔧 Recommended Upgrades

### Priority 1: Critical (Implement First)

#### **1.1 Add Mobile Data Query Functions**

Add to `server_module.py`:

```python
def get_mobile_data_by_profile(self, profile_id: str, limit: int = 100) -> List[Dict]:
    """
    Get latest mobile data for a specific profile

    Args:
        profile_id: Vehicle profile identifier
        limit: Maximum number of records to return

    Returns:
        List of data records, newest first
    """
    try:
        conn = sqlite3.connect(self.config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM mobile_vehicle_data
            WHERE profile_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (profile_id, limit))

        rows = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error querying mobile data: {e}")
        return []

def get_mobile_sessions_by_profile(self, profile_id: str) -> List[Dict]:
    """
    Get summary of all mobile sessions for a profile

    Returns:
        List of session summaries with date, duration, record count
    """
    try:
        conn = sqlite3.connect(self.config.DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                DATE(timestamp) as session_date,
                COUNT(*) as record_count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time,
                AVG(rpm) as avg_rpm,
                AVG(speed) as avg_speed
            FROM mobile_vehicle_data
            WHERE profile_id = ?
            GROUP BY DATE(timestamp)
            ORDER BY session_date DESC
        ''', (profile_id,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'date': row[0],
                'records': row[1],
                'start': row[2],
                'end': row[3],
                'avg_rpm': row[4],
                'avg_speed': row[5]
            })

        conn.close()
        return sessions

    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return []

def get_mobile_data_by_date_range(self, profile_id: str, start_date: str, end_date: str) -> List[Dict]:
    """
    Get mobile data for a specific date range

    Args:
        profile_id: Vehicle profile identifier
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    try:
        conn = sqlite3.connect(self.config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM mobile_vehicle_data
            WHERE profile_id = ?
            AND DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
        ''', (profile_id, start_date, end_date))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error querying date range: {e}")
        return []

def export_mobile_data_to_csv(self, profile_id: str, output_file: str) -> bool:
    """
    Export mobile data to CSV file

    Args:
        profile_id: Vehicle profile identifier
        output_file: Path to output CSV file

    Returns:
        True if successful, False otherwise
    """
    try:
        import csv

        data = self.get_mobile_data_by_profile(profile_id, limit=10000)

        if not data:
            return False

        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for row in data:
                writer.writerow(row)

        logger.info(f"Exported {len(data)} records to {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False
```

---

#### **1.2 Add Auto-Load on Profile Selection**

Modify `main_pyside.py` - `_on_profile_loaded()`:

```python
def _on_profile_loaded(self, profile):
    """Handle profile loaded event"""
    # Call _set_active_profile to update connectivity manager
    self._set_active_profile(profile)

    # Notify tabs
    self.ai_insights_tab.on_profile_changed(profile)

    # Notify service history tab about loaded profile
    if hasattr(self, 'service_history_tab') and hasattr(self.service_history_tab, 'set_profile'):
        self.service_history_tab.set_profile(profile.get('name'))

    # Sync profile to mobile server
    if self.mobile_wrapper:
        self.mobile_wrapper.set_active_profile(profile.get('name'))
    if self.mobile_bridge:
        self.mobile_bridge.set_active_profile(profile.get('name'))

    # ✨ NEW: Auto-load mobile data history
    self._load_mobile_history_for_profile(profile.get('name'))

    # Start logging session
    self.data_logger.start_session(profile)

def _load_mobile_history_for_profile(self, profile_name: str):
    """
    Automatically load mobile data history when profile is selected

    Args:
        profile_name: Name of the vehicle profile
    """
    try:
        if not self.mobile_wrapper or not hasattr(self.mobile_wrapper, 'server'):
            return

        server = self.mobile_wrapper.server
        if not server:
            return

        # Get mobile session summary
        sessions = server.get_mobile_sessions_by_profile(profile_name)

        if sessions:
            total_records = sum(s['records'] for s in sessions)
            latest_session = sessions[0]['date'] if sessions else None

            # Update status bar
            msg = f"Mobile History: {len(sessions)} sessions, {total_records} data points. Latest: {latest_session}"
            self.statusBar().showMessage(msg, 10000)

            logger.info(f"Loaded mobile history for {profile_name}: {len(sessions)} sessions")

            # Optional: Auto-load latest session data
            if latest_session:
                latest_data = server.get_mobile_data_by_date_range(
                    profile_name,
                    latest_session,
                    latest_session
                )

                # Store for viewing
                self.latest_mobile_session = latest_data

        else:
            logger.info(f"No mobile data history found for {profile_name}")
            self.statusBar().showMessage(f"No Android OBD history for {profile_name}", 5000)

    except Exception as e:
        logger.error(f"Error loading mobile history: {e}")
```

---

#### **1.3 Add Unified Session Viewer**

Create new tab or section in Reports Tab:

**Features**:
- Shows both USB (JSON) and Android (SQLite) sessions
- Unified timeline view
- Click to load any past session
- Compare USB vs Android data
- Export any session to CSV/PDF

**UI Structure**:
```
┌─────────────────────────────────────────────┐
│  All Sessions (USB + Android)               │
├─────────────────────────────────────────────┤
│  Date          Source    Duration  Records  │
│  2025-12-09    Android   45 min    890      │ ← From SQLite
│  2025-12-08    USB       1.2 hrs   1200     │ ← From JSON
│  2025-12-07    Android   30 min    600      │ ← From SQLite
│  2025-12-06    USB       2 hrs     2400     │ ← From JSON
└─────────────────────────────────────────────┘
         [Load Session] [Export CSV] [Compare]
```

---

### Priority 2: Important (Implement Soon)

#### **2.1 Add Database Maintenance Functions**

```python
def cleanup_old_data(self, days_to_keep: int = 90):
    """
    Archive or delete data older than specified days

    Args:
        days_to_keep: Number of days of data to keep
    """
    try:
        conn = sqlite3.connect(self.config.DATABASE_PATH)
        cursor = conn.cursor()

        # Archive to CSV before deleting
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

        cursor.execute('''
            SELECT COUNT(*) FROM mobile_vehicle_data
            WHERE timestamp < ?
        ''', (cutoff_date,))

        old_records = cursor.fetchone()[0]

        if old_records > 0:
            logger.info(f"Archiving {old_records} old records...")

            # Export to archive CSV
            # ... (export code)

            # Delete old records
            cursor.execute('''
                DELETE FROM mobile_vehicle_data
                WHERE timestamp < ?
            ''', (cutoff_date,))

            conn.commit()

        # Vacuum database to reclaim space
        cursor.execute('VACUUM')

        conn.close()
        logger.info(f"Database cleanup complete. Removed {old_records} old records.")

    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")

def get_database_size_mb(self) -> float:
    """Get database file size in MB"""
    try:
        size_bytes = os.path.getsize(self.config.DATABASE_PATH)
        return size_bytes / (1024 * 1024)  # Convert to MB
    except:
        return 0.0
```

---

#### **2.2 Add Data Validation on Load**

When loading historical data, validate integrity:

```python
def validate_session_data(self, data: List[Dict]) -> Dict:
    """
    Validate loaded session data

    Returns:
        Dictionary with validation results
    """
    if not data:
        return {'valid': False, 'error': 'No data'}

    issues = []

    # Check for gaps in timestamps
    timestamps = sorted([d.get('timestamp') for d in data if d.get('timestamp')])
    for i in range(1, len(timestamps)):
        prev = datetime.fromisoformat(timestamps[i-1])
        curr = datetime.fromisoformat(timestamps[i])
        gap = (curr - prev).total_seconds()
        if gap > 60:  # More than 60 seconds gap
            issues.append(f"Data gap at {curr}: {gap}s")

    # Check for anomalies
    rpms = [d.get('rpm') for d in data if d.get('rpm')]
    if rpms:
        avg_rpm = sum(rpms) / len(rpms)
        if avg_rpm == 0:
            issues.append("Average RPM is 0 (engine not running?)")

    return {
        'valid': len(issues) == 0,
        'record_count': len(data),
        'issues': issues,
        'time_span': f"{timestamps[0]} to {timestamps[-1]}" if timestamps else None
    }
```

---

### Priority 3: Nice to Have

#### **3.1 Add Real-Time Database Stats Widget**

Show in Connection Tab or Dashboard:
```
┌──────────────────────────────────────┐
│  Mobile Data Statistics              │
├──────────────────────────────────────┤
│  Total Records: 12,456               │
│  Vehicles: 3                         │
│  Database Size: 45.2 MB              │
│  Latest Upload: 2 min ago            │
│  Today's Records: 890                │
└──────────────────────────────────────┘
```

#### **3.2 Add Automatic Backup**

Daily backup of SQLite database:
```python
def auto_backup_database(self):
    """Create daily backup of mobile database"""
    backup_dir = os.path.join(self.config.BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    backup_file = os.path.join(backup_dir, f"mobile_db_backup_{today}.db")

    # Only backup once per day
    if os.path.exists(backup_file):
        return

    try:
        import shutil
        shutil.copy2(self.config.DATABASE_PATH, backup_file)
        logger.info(f"Database backed up to {backup_file}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
```

---

## Summary - Action Items

### Must Implement (Critical):
1. ✅ Add query functions to retrieve mobile data from SQLite
2. ✅ Auto-load mobile history when profile is selected
3. ✅ Create unified session viewer (USB + Android)
4. ✅ Add CSV export for mobile data

### Should Implement (Important):
5. Add database cleanup/archiving
6. Add data validation on load
7. Implement database size monitoring

### Nice to Have:
8. Add real-time stats widget
9. Automatic daily backups
10. Data compression for old records

---

## Current Answer to Your Questions

### Q1: "Does the program need upgrades for data and saving?"
**Answer**:
- ❌ **Saving works perfectly** - Auto-saves both JSON and SQLite
- ❌ **Loading has gaps** - No way to query/load mobile database data
- ❌ **Need to add** - Query functions and auto-load on profile selection

### Q2: "Does the program automatically read OBD data when it receives it?"
**Answer**:
- ✅ **YES, 100% automatic!**
- Polls every 1 second for new data
- Automatically processes through entire pipeline
- Updates all tabs in real-time
- Logs to JSON automatically
- Saves to SQLite automatically
- **No user action needed!**

### Q3: "Does it automatically load when loading a file?"
**Answer**:
- ✅ **JSON logs**: Yes, Reports tab loads them
- ❌ **Mobile SQLite data**: No automatic loading - **needs to be added**
- ❌ **Profile history**: No auto-load - **needs to be added**

---

## What to Do Next

**Immediate Action**: Implement the Priority 1 items:
1. Copy the query functions to `server_module.py`
2. Update `_on_profile_loaded()` in `main_pyside.py`
3. Test auto-loading with a vehicle profile
4. Verify mobile history displays correctly

This will make the mobile data fully accessible and useful!
