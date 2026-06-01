"""
PREDICT Platform - Complete User Data Reset
Wipes all user/profile data from server and desktop databases for fresh testing

This script removes:
- All users from server_database.db
- All owners from vehicle_profiles.db
- All vehicle profiles from vehicle_profiles.db
- All verification sessions
- All API keys from api_keys.json
"""

import sqlite3
import json
from pathlib import Path

def reset_all_data():
    """Complete reset of all user data"""

    print("=" * 70)
    print("PREDICT Complete User Data Reset")
    print("=" * 70)
    print("\nWARNING: This will delete ALL user data from:")
    print("  - Server database (unified_users)")
    print("  - Desktop database (owners, vehicle_profiles)")
    print("  - API keys configuration")
    print("  - Verification sessions")
    print("\n" + "=" * 70)

    # Database paths
    server_db = Path('C:/OBDserver/Previlium_OBD_Server/server_database.db')
    desktop_db = Path('C:/D Drive/Predict/data/vehicle_profiles.db')
    api_keys_file = Path('C:/OBDserver/Previlium_OBD_Server/config/api_keys.json')

    # Verify databases exist
    if not server_db.exists():
        print(f"[ERROR] Server database not found: {server_db}")
        return False

    if not desktop_db.exists():
        print(f"[ERROR] Desktop database not found: {desktop_db}")
        return False

    try:
        # ===== SERVER DATABASE CLEANUP =====
        print("\n[1/3] Cleaning server database...")
        server_conn = sqlite3.connect(str(server_db))
        server_cur = server_conn.cursor()

        # Count before deletion
        server_cur.execute("SELECT COUNT(*) FROM unified_users")
        user_count = server_cur.fetchone()[0]
        print(f"  Found {user_count} user(s) in unified_users")

        # Delete all users
        server_cur.execute("DELETE FROM unified_users")
        deleted_users = server_cur.rowcount

        # Delete verification sessions if table exists
        server_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_sessions'")
        if server_cur.fetchone():
            server_cur.execute("DELETE FROM verification_sessions")
            deleted_sessions = server_cur.rowcount
            print(f"  Deleted {deleted_sessions} verification session(s)")

        # Delete API keys if table exists
        server_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unified_api_keys'")
        if server_cur.fetchone():
            server_cur.execute("DELETE FROM unified_api_keys")
            deleted_keys = server_cur.rowcount
            print(f"  Deleted {deleted_keys} API key(s) from database")

        server_conn.commit()
        server_conn.close()
        print(f"  [OK] Deleted {deleted_users} user(s) from server database")

        # ===== DESKTOP DATABASE CLEANUP =====
        print("\n[2/3] Cleaning desktop database...")
        desktop_conn = sqlite3.connect(str(desktop_db))
        desktop_cur = desktop_conn.cursor()

        # Count before deletion
        desktop_cur.execute("SELECT COUNT(*) FROM owners")
        owner_count = desktop_cur.fetchone()[0]
        desktop_cur.execute("SELECT COUNT(*) FROM vehicle_profiles")
        profile_count = desktop_cur.fetchone()[0]

        print(f"  Found {owner_count} owner(s) and {profile_count} vehicle profile(s)")

        # Delete all owners
        desktop_cur.execute("DELETE FROM owners")
        deleted_owners = desktop_cur.rowcount

        # Delete all vehicle profiles
        desktop_cur.execute("DELETE FROM vehicle_profiles")
        deleted_profiles = desktop_cur.rowcount

        # Delete drivers if table exists
        desktop_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drivers'")
        if desktop_cur.fetchone():
            desktop_cur.execute("DELETE FROM drivers")
            deleted_drivers = desktop_cur.rowcount
            print(f"  Deleted {deleted_drivers} driver(s)")

        desktop_conn.commit()
        desktop_conn.close()
        print(f"  [OK] Deleted {deleted_owners} owner(s) and {deleted_profiles} profile(s)")

        # ===== API KEYS JSON CLEANUP =====
        print("\n[3/3] Cleaning API keys configuration...")
        if api_keys_file.exists():
            with open(api_keys_file, 'r') as f:
                keys_data = json.load(f)

            original_count = len(keys_data)

            # Keep only system/admin keys (keys without 'owner_' prefix or tier info)
            cleaned_keys = {
                k: v for k, v in keys_data.items()
                if v.get('role') == 'admin' or not v.get('tier')
            }

            deleted_key_count = original_count - len(cleaned_keys)

            with open(api_keys_file, 'w') as f:
                json.dump(cleaned_keys, f, indent=2)

            print(f"  [OK] Removed {deleted_key_count} customer API key(s), kept {len(cleaned_keys)} system key(s)")
        else:
            print(f"  [SKIP] API keys file not found: {api_keys_file}")

        # ===== SUMMARY =====
        print("\n" + "=" * 70)
        print("[OK] Complete reset successful!")
        print("\nSummary:")
        print(f"  Server users deleted: {deleted_users}")
        print(f"  Desktop owners deleted: {deleted_owners}")
        print(f"  Desktop profiles deleted: {deleted_profiles}")
        print(f"  API keys removed: {deleted_key_count if api_keys_file.exists() else 0}")
        print("\n" + "=" * 70)
        print("System is now clean for fresh testing!")
        print("\nNext steps:")
        print("  1. Restart the server")
        print("  2. Restart the Desktop app")
        print("  3. Rebuild Android APK: gradlew.bat clean assembleDebug")
        print("  4. Register a new test user")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n[ERROR] Error during reset: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nStarting complete user data reset...")
    success = reset_all_data()

    if success:
        print("\n[OK] Reset completed successfully")
    else:
        print("\n[ERROR] Reset failed")
