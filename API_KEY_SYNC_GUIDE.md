# API Key Automatic Sync System

## Overview
The API Key Sync system automatically synchronizes API keys between your Desktop program and Server, ensuring both locations always have the same keys.

---

## Your Admin API Key

**API Key:** `YOUR_ADMIN_API_KEY`
**Key ID:** `key_20260104211327_e9511550`
**Tier:** Admin
**Profile:** Omar (Profile ID: 17)
**Permissions:** vehicle_data, predict, diagnostic, llm_chat, admin

### Status
✅ **SYNCED** to both server locations:
- `C:\OBDserver\config\api_keys.json`
- `C:\OBDserver\Previlium_OBD_Server\config\api_keys.json`

### Plain Text Key Location
- Desktop: `c:\D Drive\Predict\PredictData\customers\default\api_keys\Admin_admin_20260104_211327_apikey.txt`
- Server: `C:\OBDserver\API_KEYS\Admin_apikey.txt`

---

## How Automatic Sync Works

### When Does Sync Happen?

Automatic sync occurs **every time** a new API key is created in the desktop program:

1. **Server Tab** - When you generate a customer or admin API key
2. **Subscription Manager** - When a subscription generates an API key

### What Gets Synced?

The following data is synced to the server:
- Key hash (for authentication)
- Key name
- Profile ID and name
- Permissions
- Tier (free, premium, admin)
- Creation timestamp
- Status

**Note:** Encrypted keys (`key_encrypted`) and hidden keys (`key_hidden`) are NOT synced to the server for security.

### Where Are Keys Synced To?

API keys are automatically synced to:
1. `C:\OBDserver\config\api_keys.json`
2. `C:\OBDserver\Previlium_OBD_Server\config\api_keys.json`

---

## Manual Sync (If Needed)

If you need to manually sync all API keys, run:

```bash
cd "c:\D Drive\Predict"
python api_key_sync.py
```

This will:
- Create backups of existing server keys
- Sync all desktop keys to both server locations
- Display sync status and results

---

## Sync Module Location

**File:** `c:\D Drive\Predict\api_key_sync.py`

### Key Functions

1. **sync_api_keys_to_server()** - Sync all keys from desktop to server
2. **sync_single_key_to_server()** - Sync a single key (used by auto-sync)
3. **get_sync_status()** - Check current sync status

### Integration Points

The sync is integrated into:
- `server_tab_v2.py` (line ~1745-1751)
- `subscription_manager.py` (line ~733-739)

---

## Backup System

Every sync creates automatic backups:
- Format: `api_keys.json.backup_YYYYMMDD_HHMMSS`
- Location: Same folder as the original file
- Retention: Manual cleanup (backups are not auto-deleted)

### Recent Backups
Check these locations for backups:
- `C:\OBDserver\config\api_keys.json.backup_*`
- `C:\OBDserver\Previlium_OBD_Server\config\api_keys.json.backup_*`

---

## Testing Sync

To test the sync system:

```python
from api_key_sync import get_sync_status, sync_api_keys_to_server

# Check sync status
status = get_sync_status()
print(f"Desktop keys: {status['desktop_keys']}")
print(f"In sync: {status['in_sync']}")

# Perform manual sync
result = sync_api_keys_to_server()
print(f"Success: {result['success']}")
print(f"Keys synced: {result['keys_synced']}")
```

---

## Troubleshooting

### Sync Not Working?

1. **Check paths exist:**
   ```bash
   dir "C:\OBDserver\config"
   dir "C:\OBDserver\Previlium_OBD_Server\config"
   ```

2. **Check desktop keys file:**
   ```bash
   dir "c:\D Drive\Predict\PredictData\system\config\api_keys.json"
   ```

3. **Run manual sync with verbose output:**
   ```bash
   cd "c:\D Drive\Predict"
   python api_key_sync.py
   ```

### Keys Out of Sync?

Run this to check status:
```python
from api_key_sync import get_sync_status
status = get_sync_status()
if not status['in_sync']:
    print("Missing keys:", status['missing_on_servers'])
```

Then run manual sync to fix.

---

## Security Notes

1. **Key Storage:**
   - Desktop: Keys are encrypted with password `YOUR_ADMIN_PASSWORD`
   - Server: Only key hashes are stored (not encrypted keys)

2. **Authentication:**
   - Server validates API keys by comparing SHA-256 hashes
   - Original keys are never stored on server

3. **Backups:**
   - All backups contain sensitive data
   - Secure backups appropriately
   - Consider encrypting backup folder

---

## Future Enhancements

Potential improvements to consider:

1. **Real-time sync** - Watch for file changes and sync immediately
2. **Bi-directional sync** - Sync server keys back to desktop
3. **Conflict resolution** - Handle conflicting keys between desktop and server
4. **Sync logging** - Detailed logs of all sync operations
5. **Remote sync** - Sync to remote servers via API

---

## Summary

✅ Admin key is synced and working
✅ Automatic sync is active for new keys
✅ Manual sync available when needed
✅ Backup system protects against data loss
✅ Integration complete in both key generation locations

**Next Steps:**
- Use your admin key: `YOUR_ADMIN_API_KEY`
- Create new API keys - they'll auto-sync
- Start the server and test admin permissions

---

Generated: 2026-01-05
