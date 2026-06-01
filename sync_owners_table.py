"""
PREDICT Platform - Database Sync Script
Syncs unified_users from server_database.db to owners table in vehicle_profiles.db

This script fixes the critical issue where the Desktop Info dialog shows "Not set"
for all fields because the owners table is empty.
"""

import sqlite3
import time
from pathlib import Path

def sync_owners():
    """Sync unified_users data to owners table"""

    # Database paths
    server_db = Path('C:/OBDserver/Previlium_OBD_Server/server_database.db')
    desktop_db = Path('C:/D Drive/Predict/data/vehicle_profiles.db')

    # Verify both databases exist
    if not server_db.exists():
        print(f"[ERROR] ERROR: Server database not found at {server_db}")
        return False

    if not desktop_db.exists():
        print(f"[ERROR] ERROR: Desktop database not found at {desktop_db}")
        return False

    print("=" * 70)
    print("PREDICT Database Sync - unified_users -> owners table")
    print("=" * 70)

    # Connect to both databases
    server_conn = sqlite3.connect(str(server_db))
    desktop_conn = sqlite3.connect(str(desktop_db))

    server_cur = server_conn.cursor()
    desktop_cur = desktop_conn.cursor()

    try:
        # Fetch all users from unified_users
        server_cur.execute("""
            SELECT id, email, name, phone, api_key, tier, role, created_at, updated_at, status
            FROM unified_users
            WHERE email IS NOT NULL
        """)

        users = server_cur.fetchall()

        print(f"\n[INFO] Found {len(users)} users in server_database.db")

        if len(users) == 0:
            print("[WARNING]  No users found to sync")
            return False

        # Check current state of owners table
        desktop_cur.execute("SELECT COUNT(*) FROM owners")
        initial_count = desktop_cur.fetchone()[0]
        print(f"[INFO] Current owners in vehicle_profiles.db: {initial_count}")

        print("\n[SYNC] Starting sync...")
        print("-" * 70)

        synced_count = 0
        for user in users:
            user_id, email, name, phone, api_key, tier, role, created_at, updated_at, status = user

            # Skip deleted users
            if status == 'deleted':
                print(f"  [SKIP]  Skipping deleted user {user_id}: {name} ({email})")
                continue

            # Insert or replace into owners table
            desktop_cur.execute("""
                INSERT OR REPLACE INTO owners (
                    owner_id, name, email, phone, api_key, api_key_hash,
                    role, apps, is_active, created_at, updated_at, tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,                        # owner_id
                name or "Unknown",               # name
                email,                           # email
                phone or "",                     # phone
                api_key or "",                   # api_key
                "",                              # api_key_hash (empty for now)
                role or "owner",                 # role
                "obd,guardian",                  # apps (comma-separated)
                1,                               # is_active
                created_at or time.time(),       # created_at
                updated_at or time.time(),       # updated_at
                tier or "free"                   # tier
            ))

            synced_count += 1
            api_key_display = f"{api_key[:30]}..." if api_key else "None"
            print(f"  [OK] Synced user {user_id}: {name} ({email}) | API Key: {api_key_display}")

        desktop_conn.commit()

        # Verify sync
        desktop_cur.execute("SELECT COUNT(*) FROM owners")
        final_count = desktop_cur.fetchone()[0]

        print("-" * 70)
        print(f"\n[OK] Sync complete!")
        print(f"   • Users synced: {synced_count}")
        print(f"   • Total owners in vehicle_profiles.db: {final_count}")

        # Show owner 1 data as verification
        desktop_cur.execute("""
            SELECT owner_id, name, email, phone, api_key, tier
            FROM owners
            WHERE owner_id = 1
        """)
        owner = desktop_cur.fetchone()

        if owner:
            print(f"\n[VERIFY] Verification - Owner ID=1 data:")
            print(f"   • ID: {owner[0]}")
            print(f"   • Name: {owner[1]}")
            print(f"   • Email: {owner[2]}")
            print(f"   • Phone: {owner[3]}")
            print(f"   • API Key: {owner[4][:30]}..." if owner[4] else "   • API Key: None")
            print(f"   • Tier: {owner[5]}")
        else:
            print("\n[WARNING]  Warning: Owner ID=1 not found after sync")

        print("\n" + "=" * 70)
        print("[OK] Desktop can now display owner information correctly!")
        print("   Next step: Restart the Desktop application")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n[ERROR] ERROR during sync: {e}")
        import traceback
        traceback.print_exc()
        desktop_conn.rollback()
        return False

    finally:
        server_conn.close()
        desktop_conn.close()

if __name__ == "__main__":
    success = sync_owners()
    if success:
        print("\n[OK] Sync script completed successfully")
    else:
        print("\n[ERROR] Sync script failed")
