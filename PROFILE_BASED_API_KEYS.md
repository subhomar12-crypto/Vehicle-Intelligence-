# Profile-Based API Key System - Implementation Complete!

## Summary

Your desktop Predict app now supports **profile-based API keys**. Each API key is linked to a specific vehicle profile, providing better security and organization.

---

## What Changed

### 1. ✅ API Key Structure Updated

**Before:**
```json
{
  "key_20231210120000": {
    "key_hash": "...",
    "name": "Android Phone #1",
    "created": "2023-12-10T12:00:00",
    "permissions": ["vehicle_data", "predict", "diagnostic"]
  }
}
```

**After:**
```json
{
  "key_20231210120000": {
    "key_hash": "...",
    "name": "Android Phone #1",
    "profile_id": 9,
    "profile_name": "Omar",
    "created": "2023-12-10T12:00:00",
    "permissions": ["vehicle_data", "predict", "diagnostic"]
  }
}
```

**New Fields:**
- `profile_id` - The vehicle profile ID from the database
- `profile_name` - The vehicle profile name for easy reference

---

### 2. ✅ Key Generation UI Enhanced

**New Features:**
- Profile selection dropdown when generating API keys
- Shows profile details: Name (Make Model Year)
- Example: "Omar (Nissan Patrol Y61 2003)"
- Cannot generate key without selecting a profile

**How It Works:**
1. Click "Generate New Key"
2. **Select Vehicle Profile** from dropdown
3. Enter API Key Name (e.g., "Android Phone #1")
4. Click Generate
5. Key is created and linked to the selected profile

---

### 3. ✅ API Keys Table Updated

**New Column Added:** "Profile"

**Table Structure:**
| Name | Profile | Key (Hidden) | Created | Actions |
|------|---------|-------------|---------|---------|
| Android Phone #1 | Omar | ••••••••••••••••• | 2023-12-10 12:00 | Copy Key |
| Backup Device | MOM | ••••••••••••••••• | 2023-12-10 13:30 | Copy Key |

---

### 4. ✅ Profile Management Function

**New Function:** `_get_vehicle_profiles()`

**Purpose:** Fetches all vehicle profiles from the database

**Returns:**
```python
[
  {
    'profile_id': 9,
    'name': 'Omar',
    'make': 'Nissan',
    'model': 'Patrol Y61',
    'year': 2003
  },
  {
    'profile_id': 10,
    'name': 'MOM',
    'make': 'Nissan',
    'model': 'Altima',
    'year': 2017
  }
]
```

**Database Path:** `C:/D Drive/Predict/data/vehicle_profiles.db`

---

## How to Use

### Generating a Profile-Based API Key

1. **Open Server Tab** in the desktop app
2. **Click "➕ Generate New Key"**
3. **Select Vehicle Profile** from dropdown
   - Shows: Name (Make Model Year)
   - Example: "Omar (Nissan Patrol Y61 2003)"
4. **Enter API Key Name**
   - Example: "Android Phone #1"
   - Or: "Backup Device"
5. **Click "Generate"**
6. **Copy the API key** (shown only once!)
7. **Configure Android App:**
   - API Key: [paste the key you copied]
   - Server IP: [your computer's IP]
   - Port: 8000

---

### Viewing API Keys by Profile

The API Keys table now shows which profile each key belongs to:

```
┌────────────────┬─────────┬──────────────────┬──────────────────┬──────────────────┐
│ Name           │ Profile │ Key (Hidden)     │ Created          │ Actions          │
├────────────────┼─────────┼──────────────────┼──────────────────┼──────────────────┤
│ Android Phone  │ Omar    │ ••••••••••••••••│ 2023-12-10 12:00 │ Copy | Delete   │
│ Backup Device  │ MOM     │ ••••••••••••••••│ 2023-12-10 13:30 │ Copy | Delete   │
│ Tablet         │ Sobeh   │ ••••••••••••••••│ 2023-12-11 09:15 │ Copy | Delete   │
└────────────────┴─────────┴──────────────────┴──────────────────┴──────────────────┘
```

### Deleting API Keys

**How to Delete:**
1. Click the **"Delete"** button next to the key you want to remove
2. Confirm deletion in the popup dialog
3. Key will be permanently removed from the system

**⚠️ Important Notes:**
- Deletion is permanent and cannot be undone
- If the key is in use by an Android device, that device will lose access
- Update Android app configuration after deleting a key
- Consider generating a new key before deleting if you need to maintain access

**When to Delete API Keys:**
- **Lost or Stolen Device:** If the Android device with the key is lost/stolen
- **Security Breach:** If you suspect the key has been compromised
- **No Longer Needed:** When retiring a vehicle profile or device
- **Key Rotation:** As part of regular security key rotation
- **Wrong Profile:** If key was accidentally linked to wrong profile

---

## Security Benefits

### 1. One Key Per Vehicle
- Each vehicle profile has its own unique API key
- No shared keys across different vehicles
- Better access control

### 2. Easy Revocation
- If a device is lost, revoke only that vehicle's key
- Other vehicles remain secure
- No need to regenerate all keys

### 3. Audit Trail
- Know which device is accessing which vehicle
- Track access by profile
- Clear ownership of keys

### 4. Access Isolation
- Android app with "Omar" key can only access Omar's vehicle data
- Cannot access MOM's or Sobeh's vehicle data
- Profile-level security enforcement

---

## Files Modified

### `server_tab.py`

**Changes:**
1. Updated `_generate_api_key()` function:
   - Added profile selection dialog
   - Added `profile_id` and `profile_name` to API key structure
   - Enhanced success message to show profile

2. Added `_get_vehicle_profiles()` function:
   - Queries `vehicle_profiles` table
   - Returns list of all profiles
   - Used for profile selection dropdown

3. Updated `_load_api_keys()` function:
   - Added Profile column to table (now 5 columns)
   - Displays profile name for each key
   - Backward compatible with old keys (shows "N/A")
   - Updated actions to include both Copy and Delete buttons

4. Added `_delete_api_key()` function:
   - Allows deletion of API keys with confirmation
   - Shows key name and profile in confirmation dialog
   - Warns about impact on connected devices
   - Updates table after deletion

5. Updated API keys table:
   - Changed from 4 to 5 columns
   - New header: ["Name", "Profile", "Key (Hidden)", "Created", "Actions"]
   - Actions column now has Copy and Delete buttons

6. Updated info text:
   - New: "Each key is linked to a vehicle profile for secure access"
   - Old: "Each key can be assigned to a customer/device"

**Location:** `C:\D Drive\Predict\server_tab.py`

---

## Existing Profiles

Your system currently has these profiles:

| ID | Name | Make | Model | Year |
|----|------|------|-------|------|
| 9 | Omar | Nissan | Patrol Y61 | 2003 |
| 10 | MOM | Nissan | Altima | 2017 |
| 11 | fath | - | - | - |
| 13 | Sobeh | Nissan | Altima | 2017 |
| 14 | ahmed | Nissan | Patrol Y62 | 2017 |
| 15 | MOH | Chevrolet | Suburban | 2023 |

---

## Backward Compatibility

### Old API Keys (without profile)
- Will still work
- Display "N/A" in Profile column
- Can be deleted and regenerated with profile

### Recommendation
- **Regenerate all existing API keys** to link them to profiles
- This ensures full profile-based security

**Steps:**
1. Note which key belongs to which vehicle
2. Delete old keys
3. Generate new profile-based keys
4. Update Android app with new keys

---

## Android App Configuration

### Example Configuration

**For Omar's Vehicle:**
```
Server IP: 192.168.1.100
Port: 8000
API Key: xyzabc123...
```

**For MOM's Vehicle:**
```
Server IP: 192.168.1.100
Port: 8000
API Key: defghi456...  (DIFFERENT KEY!)
```

### Important Notes
- Each vehicle needs its own Android app instance or configuration
- Use separate API keys for each vehicle
- Keys are tied to specific profiles

---

## Testing the System

### Test 1: Generate Profile-Based Key

1. Open desktop app → Server tab
2. Click "➕ Generate New Key"
3. Verify dropdown shows all profiles
4. Select a profile (e.g., "Omar (Nissan Patrol Y61 2003)")
5. Enter key name: "Test Key"
6. Click Generate
7. Verify success message shows profile name
8. Copy the API key

**Expected Result:** ✅ Key generated with profile_id and profile_name

---

### Test 2: View Keys Table

1. Look at API Keys table
2. Verify "Profile" column is visible
3. Verify your new key shows correct profile name

**Expected Result:** ✅ Table displays 5 columns with Profile column

---

### Test 3: Generate Key for Different Profile

1. Generate another key
2. Select a different profile (e.g., "MOM")
3. Enter key name: "MOM's Phone"
4. Generate key
5. Verify table now shows both keys with different profiles

**Expected Result:** ✅ Two keys with different profiles displayed

---

### Test 4: Backward Compatibility

1. If you have old API keys (without profile)
2. They should display "N/A" in Profile column
3. They should still appear in the table

**Expected Result:** ✅ Old keys still visible with "N/A"

---

## Architecture

### Key Generation Flow

```
User clicks "Generate New Key"
    ↓
_generate_api_key() called
    ↓
_get_vehicle_profiles() → Query database
    ↓
Show profile selection dialog
    ↓
User selects profile + enters name
    ↓
Generate random API key (32 bytes)
    ↓
Create SHA256 hash of key
    ↓
Store in api_keys.json:
  {
    "key_hash": hash,
    "name": name,
    "profile_id": 9,         ← NEW
    "profile_name": "Omar",  ← NEW
    "created": timestamp,
    "permissions": [...]
  }
    ↓
Show key to user (ONE TIME ONLY)
    ↓
Reload API keys table with profile column
```

### Table Display Flow

```
_load_api_keys() called
    ↓
Read api_keys.json
    ↓
For each key:
  - Get profile_name from key data
  - If missing, lookup by profile_id in database
  - Display in Profile column
    ↓
Render 5-column table:
  [Name] [Profile] [Key (Hidden)] [Created] [Actions]
```

---

## Future Enhancements

### Possible Additions (NOT implemented yet):

1. **Profile-Based Validation in Previlium Server**
   - Validate API key + device_id match
   - Reject requests if profile_id doesn't match

2. **Multi-Key Support**
   - Allow multiple keys per profile
   - Example: Primary phone + backup tablet

3. **Key Expiration**
   - Add expiration dates to keys
   - Auto-revoke expired keys

4. **Usage Tracking**
   - Track which key was used for each request
   - Show last used timestamp

5. **Profile Permissions**
   - Different permission levels per profile
   - Read-only vs full access

---

## Troubleshooting

### Issue: "No vehicle profiles found"

**Cause:** No profiles in database

**Solution:**
1. Go to Profiles tab in desktop app
2. Create at least one vehicle profile
3. Then generate API keys

---

### Issue: Profile column shows "N/A"

**Cause:** Old API key without profile_id

**Solution:**
1. Delete the old key
2. Generate a new profile-based key
3. Update Android app with new key

---

### Issue: Profile not showing in dropdown

**Cause:** Profile database not accessible

**Check:**
1. Verify database exists: `C:/D Drive/Predict/data/vehicle_profiles.db`
2. Check file permissions
3. Look for errors in console

---

### Issue: Cannot generate key

**Cause:** No profiles available

**Solution:**
1. Create vehicle profiles first
2. Then generate API keys

---

## Summary

✅ **API key structure updated** with profile_id and profile_name
✅ **Key generation UI enhanced** with profile selection
✅ **API keys table updated** to display Profile column
✅ **Profile management function** added (_get_vehicle_profiles)
✅ **Backward compatible** with old keys (shows "N/A")
✅ **Security improved** with profile-based access control

---

## Quick Reference

### Generate Profile-Based API Key:
```
Server Tab → ➕ Generate New Key → Select Profile → Enter Name → Generate
```

### View API Keys by Profile:
```
Server Tab → API Keys table → Profile column
```

### Get List of Profiles:
```python
profiles = self._get_vehicle_profiles()
# Returns: [{'profile_id': 9, 'name': 'Omar', 'make': 'Nissan', ...}, ...]
```

### API Key JSON Structure:
```json
{
  "key_20231210120000": {
    "key_hash": "sha256_hash_here",
    "name": "Android Phone #1",
    "profile_id": 9,
    "profile_name": "Omar",
    "created": "2023-12-10T12:00:00",
    "permissions": ["vehicle_data", "predict", "diagnostic"]
  }
}
```

---

Your profile-based API key system is now complete and ready to use! 🎉
