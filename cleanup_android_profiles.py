"""
PREDICT Platform - Database Cleanup Script
Removes redundant vehicle profiles for Android customers

Android customers are represented by owner entries only.
Vehicle profiles with customer_name are redundant and cause conflicts.
"""

import sqlite3
from pathlib import Path

def cleanup_android_profiles():
    """Remove vehicle profiles that duplicate owner entries"""

    desktop_db = Path('C:/D Drive/Predict/data/vehicle_profiles.db')

    if not desktop_db.exists():
        print(f"[ERROR] Desktop database not found at {desktop_db}")
        return False

    print("=" * 70)
    print("PREDICT Database Cleanup - Redundant Android Profiles")
    print("=" * 70)

    conn = sqlite3.connect(str(desktop_db))
    cur = conn.cursor()

    try:
        # Find vehicle profiles that have customer_name AND match an owner
        cur.execute("""
            SELECT vp.profile_id, vp.name, vp.customer_name, vp.customer_email, vp.owner_id,
                   o.owner_id, o.name, o.email
            FROM vehicle_profiles vp
            INNER JOIN owners o ON vp.owner_id = o.owner_id
            WHERE vp.customer_name IS NOT NULL
              AND vp.customer_email IS NOT NULL
        """)

        duplicates = cur.fetchall()

        if len(duplicates) == 0:
            print("\n[INFO] No redundant profiles found. Database is clean.")
            return True

        print(f"\n[INFO] Found {len(duplicates)} redundant vehicle profile(s)")
        print("\nProfiles to remove:")
        print("-" * 70)

        for dup in duplicates:
            profile_id, vp_name, vp_customer_name, vp_customer_email, vp_owner_id, o_id, o_name, o_email = dup
            print(f"  Profile ID {profile_id}:")
            print(f"    Vehicle Profile: name=\"{vp_name}\", customer=\"{vp_customer_name}\"")
            print(f"    Owner Entry: ID={o_id}, name=\"{o_name}\", email=\"{o_email}\"")
            print(f"    -> Reason: Owner entry already exists, vehicle profile is redundant")
            print()

        # Ask for confirmation
        response = input("\nDelete these redundant profiles? (yes/no): ").lower().strip()

        if response != 'yes':
            print("\n[INFO] Cleanup cancelled by user")
            return False

        print("\n[CLEANUP] Removing redundant profiles...")

        # Delete the redundant profiles
        for dup in duplicates:
            profile_id = dup[0]
            cur.execute("DELETE FROM vehicle_profiles WHERE profile_id = ?", (profile_id,))
            print(f"  [OK] Deleted profile ID {profile_id}")

        conn.commit()

        # Verify cleanup
        cur.execute("SELECT COUNT(*) FROM vehicle_profiles WHERE customer_name IS NOT NULL")
        remaining = cur.fetchone()[0]

        print("-" * 70)
        print(f"\n[OK] Cleanup complete!")
        print(f"   Profiles deleted: {len(duplicates)}")
        print(f"   Remaining profiles with customer_name: {remaining}")

        # Show final state
        cur.execute("SELECT COUNT(*) FROM owners")
        owner_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vehicle_profiles")
        profile_count = cur.fetchone()[0]

        print(f"\n[INFO] Final database state:")
        print(f"   Owners: {owner_count}")
        print(f"   Vehicle Profiles: {profile_count}")

        print("\n" + "=" * 70)
        print("[OK] Desktop will now show Android customers as owners only")
        print("   Next step: Restart the Desktop application")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n[ERROR] ERROR during cleanup: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = cleanup_android_profiles()
    if success:
        print("\n[OK] Cleanup script completed successfully")
    else:
        print("\n[ERROR] Cleanup script failed or was cancelled")
