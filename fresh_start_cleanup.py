"""
PREDICT - Fresh Start Cleanup Script
=====================================
This script cleans both Desktop and Server databases to start fresh with the
new unified customer management system.

WARNING: This will DELETE ALL existing data:
- All owners, vehicles, and drivers from Desktop
- All unified users, API keys, and entitlements from Server
- All usage counters and rate limits

Run this script when you want to start fresh with a clean slate.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration
DESKTOP_DB_PATH = Path(r"C:\D Drive\Predict\data\vehicle_profiles.db")
SERVER_DB_PATH = Path(r"C:\OBDserver\Previlium_OBD_Server\data\vehicle_database.db")
SERVER_API_KEYS_PATH = Path(r"C:\OBDserver\Previlium_OBD_Server\config\api_keys.json")


def confirm_action(message: str) -> bool:
    """Ask for user confirmation"""
    print(f"\n[!]  WARNING: {message}")
    response = input("\nType 'YES' to confirm: ").strip()
    return response == 'YES'


def clean_desktop_database():
    """Clean all profiles, owners, vehicles, and drivers from Desktop database"""
    print("\n" + "="*60)
    print("[PC]  DESKTOP DATABASE CLEANUP")
    print("="*60)

    if not DESKTOP_DB_PATH.exists():
        print(f"[X] Desktop database not found at: {DESKTOP_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(DESKTOP_DB_PATH))
        cursor = conn.cursor()

        # Get current counts
        tables_to_clean = ['drivers', 'profiles', 'owners', 'service_history',
                          'driving_style_baselines', 'component_health']

        print("\n[#] Current data in Desktop database:")
        for table in tables_to_clean:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   • {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"   • {table}: table doesn't exist")

        if not confirm_action("This will DELETE ALL data from the Desktop database!"):
            print("[X] Cancelled")
            return False

        print("\n[DEL]  Deleting data...")

        for table in tables_to_clean:
            try:
                cursor.execute(f"DELETE FROM {table}")
                print(f"   [OK] Cleared {table}")
            except sqlite3.OperationalError as e:
                print(f"   [!]  Could not clear {table}: {e}")

        conn.commit()
        conn.close()

        print("\n[OK] Desktop database cleaned successfully!")
        return True

    except Exception as e:
        print(f"\n[X] Error cleaning Desktop database: {e}")
        return False


def clean_server_database():
    """Clean all unified users, API keys, and related data from Server database"""
    print("\n" + "="*60)
    print("[PC]  SERVER DATABASE CLEANUP")
    print("="*60)

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found at: {SERVER_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(SERVER_DB_PATH))
        cursor = conn.cursor()

        # Tables to clean (unified user system tables)
        tables_to_clean = [
            'usage_counters',
            'rate_limits',
            'entitlements',
            'driver_assignments',
            'unified_api_keys',
            'unified_users',
            'tier_presets'
        ]

        print("\n[#] Current data in Server database:")
        for table in tables_to_clean:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   • {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"   • {table}: table doesn't exist")

        if not confirm_action("This will DELETE ALL unified user data from the Server database!"):
            print("[X] Cancelled")
            return False

        print("\n[DEL]  Deleting data...")

        for table in tables_to_clean:
            try:
                cursor.execute(f"DELETE FROM {table}")
                print(f"   [OK] Cleared {table}")
            except sqlite3.OperationalError as e:
                print(f"   [!]  Could not clear {table}: {e}")

        conn.commit()
        conn.close()

        print("\n[OK] Server database cleaned successfully!")
        return True

    except Exception as e:
        print(f"\n[X] Error cleaning Server database: {e}")
        return False


def clean_api_keys_file():
    """Clean the legacy api_keys.json file"""
    print("\n" + "="*60)
    print("[FILE]  API KEYS FILE CLEANUP")
    print("="*60)

    if not SERVER_API_KEYS_PATH.exists():
        print(f"[i]  API keys file not found (already clean): {SERVER_API_KEYS_PATH}")
        return True

    try:
        with open(SERVER_API_KEYS_PATH, 'r') as f:
            keys = json.load(f)
        print(f"\n[#] Current API keys in file: {len(keys)}")

        if len(keys) == 0:
            print("[i]  File is already empty")
            return True

        if not confirm_action("This will DELETE ALL legacy API keys from api_keys.json!"):
            print("[X] Cancelled")
            return False

        # Backup first
        backup_path = SERVER_API_KEYS_PATH.with_suffix('.json.backup')
        with open(backup_path, 'w') as f:
            json.dump(keys, f, indent=2)
        print(f"   [BACKUP] Backup saved to: {backup_path}")

        # Clear the file
        with open(SERVER_API_KEYS_PATH, 'w') as f:
            json.dump({}, f, indent=2)

        print("\n[OK] API keys file cleaned successfully!")
        return True

    except Exception as e:
        print(f"\n[X] Error cleaning API keys file: {e}")
        return False


def initialize_tier_presets():
    """Initialize the tier presets in the server database"""
    print("\n" + "="*60)
    print("[TIER]  INITIALIZING TIER PRESETS")
    print("="*60)

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found at: {SERVER_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(SERVER_DB_PATH))
        cursor = conn.cursor()

        # Create tier_presets table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tier_presets (
                tier_name TEXT PRIMARY KEY,
                features TEXT NOT NULL,
                default_limits TEXT NOT NULL
            )
        ''')

        # Define tier presets
        presets = {
            'free': {
                'features': ['vehicle_data'],
                'limits': {
                    'vehicle_data': {'max': 1000, 'period': 'day'},
                    'llm_chat': {'max': 0, 'period': 'day'},
                    'predict': {'max': 0, 'period': 'day'},
                    'guardian': {'max': 0, 'period': 'day'}
                }
            },
            'premium': {
                'features': ['vehicle_data', 'llm_chat', 'predict', 'guardian'],
                'limits': {
                    'vehicle_data': {'max': None, 'period': 'day'},
                    'llm_chat': {'max': 500, 'period': 'day'},
                    'predict': {'max': 50, 'period': 'day'},
                    'guardian': {'max': None, 'period': 'day'}
                }
            },
            'admin': {
                'features': ['vehicle_data', 'llm_chat', 'predict', 'guardian', 'admin'],
                'limits': {
                    'vehicle_data': {'max': None, 'period': 'day'},
                    'llm_chat': {'max': None, 'period': 'day'},
                    'predict': {'max': None, 'period': 'day'},
                    'guardian': {'max': None, 'period': 'day'},
                    'admin': {'max': None, 'period': 'day'}
                }
            }
        }

        for tier_name, config in presets.items():
            cursor.execute('''
                INSERT OR REPLACE INTO tier_presets (tier_name, features, default_limits)
                VALUES (?, ?, ?)
            ''', (tier_name, json.dumps(config['features']), json.dumps(config['limits'])))
            print(f"   [OK] {tier_name.title()} tier preset initialized")

        conn.commit()
        conn.close()

        print("\n[OK] Tier presets initialized successfully!")
        return True

    except Exception as e:
        print(f"\n[X] Error initializing tier presets: {e}")
        return False


def create_admin_account():
    """Create the initial admin account"""
    print("\n" + "="*60)
    print("[USER]  CREATE ADMIN ACCOUNT")
    print("="*60)

    print("\nWould you like to create an admin account now?")
    response = input("Enter 'YES' to create admin account, or press Enter to skip: ").strip()

    if response != 'YES':
        print("[SKIP]  Skipped admin account creation")
        return True

    # Get admin details
    print("\nEnter admin account details:")
    name = input("   Name: ").strip()
    email = input("   Email: ").strip()
    phone = input("   Phone (optional): ").strip() or None

    if not name or not email:
        print("[X] Name and email are required")
        return False

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found at: {SERVER_DB_PATH}")
        return False

    try:
        import secrets
        import hashlib
        from time import time

        conn = sqlite3.connect(str(SERVER_DB_PATH))
        cursor = conn.cursor()

        # Generate API key
        random_part = secrets.token_hex(16)
        api_key = f"PRED-ADMIN-{random_part[:8].upper()}-{random_part[8:12].upper()}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_id = f"key_{int(time())}_{secrets.token_hex(4)}"

        now = time()

        # Create user
        cursor.execute('''
            INSERT INTO unified_users (email, name, phone, created_at, status, role, tier)
            VALUES (?, ?, ?, ?, 'active', 'admin', 'admin')
        ''', (email, name, phone, now))

        user_id = cursor.lastrowid

        # Create API key
        cursor.execute('''
            INSERT INTO unified_api_keys (key_id, user_id, key_hash, name, created_at, status)
            VALUES (?, ?, ?, 'Admin Key', ?, 'active')
        ''', (key_id, user_id, key_hash, now))

        # Get admin tier features
        cursor.execute("SELECT features, default_limits FROM tier_presets WHERE tier_name = 'admin'")
        tier_row = cursor.fetchone()

        if tier_row:
            features = json.loads(tier_row[0])
            limits = json.loads(tier_row[1])

            # Create entitlements
            for feature in features:
                cursor.execute('''
                    INSERT INTO entitlements (user_id, feature, enabled, granted_at)
                    VALUES (?, ?, 1, ?)
                ''', (user_id, feature, now))

            # Create rate limits
            for feature, limit_config in limits.items():
                cursor.execute('''
                    INSERT INTO rate_limits (user_id, feature, max_requests, period)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, feature, limit_config.get('max'), limit_config.get('period', 'day')))

        conn.commit()
        conn.close()

        print(f"\n[OK] Admin account created successfully!")
        print(f"\n[INFO] Admin Account Details:")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Tier: Admin (unlimited access)")
        print(f"\n[KEY] API Key (SAVE THIS - shown only once):")
        print(f"   {api_key}")
        print(f"\n[!]  Store this API key securely!")

        return True

    except Exception as e:
        print(f"\n[X] Error creating admin account: {e}")
        return False


def main():
    """Main cleanup routine"""
    print("\n" + "="*70)
    print("   PREDICT - Fresh Start Cleanup Script")
    print("   Unified Customer Management System")
    print("="*70)

    print("""
This script will:
1. Clean all profiles from Desktop database (owners, vehicles, drivers)
2. Clean all unified users from Server database (users, API keys, entitlements)
3. Clear the legacy api_keys.json file
4. Initialize tier presets (Free, Premium, Admin)
5. Optionally create an admin account

After running this script, you can start fresh with the new
unified customer management system in the Profile tab.
""")

    if not confirm_action("Proceed with complete database cleanup?"):
        print("\n[X] Cleanup cancelled.")
        return

    success = True

    # Step 1: Clean Desktop database
    if not clean_desktop_database():
        success = False

    # Step 2: Clean Server database
    if not clean_server_database():
        success = False

    # Step 3: Clean API keys file
    if not clean_api_keys_file():
        success = False

    # Step 4: Initialize tier presets
    if not initialize_tier_presets():
        success = False

    # Step 5: Create admin account
    create_admin_account()

    print("\n" + "="*70)
    if success:
        print("[OK] CLEANUP COMPLETE!")
        print("""
Next steps:
1. Start the OBD Server
2. Start the PREDICT Desktop app
3. Go to the Profile tab
4. Click [i] on any customer to manage:
   - Tier (Free/Premium/Admin)
   - Features (toggle on/off)
   - Rate Limits (per feature)
   - API Keys (regenerate, copy, email)

All customer management is now done through the Profile tab!
""")
    else:
        print("[!]  CLEANUP COMPLETED WITH ERRORS")
        print("   Please check the error messages above and fix any issues.")
    print("="*70)


if __name__ == "__main__":
    main()
