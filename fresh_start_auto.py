"""
PREDICT - Fresh Start Cleanup Script (Auto Mode)
=================================================
Non-interactive version that automatically cleans all databases.

WARNING: This will DELETE ALL existing data without confirmation!
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration - Multiple possible paths
DESKTOP_DB_PATHS = [
    Path(r"C:\D Drive\Predict\PredictData\vehicle_profiles.db"),
    Path(r"C:\D Drive\Predict\data\vehicle_profiles.db"),
    Path(r"C:\D Drive\Predict\vehicle_profiles.db"),
]
SERVER_DB_PATHS = [
    Path(r"C:\OBDserver\Previlium_OBD_Server\data\obd_data.db"),
    Path(r"C:\OBDserver\Previlium_OBD_Server\obd_data.db"),
    Path(r"C:\OBDserver\Previlium_OBD_Server\previlium_obd.db"),
]
SERVER_API_KEYS_PATH = Path(r"C:\OBDserver\Previlium_OBD_Server\config\api_keys.json")

def find_existing_path(paths):
    """Find the first path that exists"""
    for p in paths:
        if p.exists():
            return p
    return paths[0]  # Return first as default


def clean_desktop_database():
    """Clean all profiles from Desktop database"""
    print("\n" + "="*60)
    print("[PC]  DESKTOP DATABASE CLEANUP")
    print("="*60)

    DESKTOP_DB_PATH = find_existing_path(DESKTOP_DB_PATHS)
    print(f"   Using database: {DESKTOP_DB_PATH}")

    if not DESKTOP_DB_PATH.exists():
        print(f"[X] Desktop database not found at any expected location")
        return False

    try:
        conn = sqlite3.connect(str(DESKTOP_DB_PATH))
        cursor = conn.cursor()

        tables_to_clean = ['drivers', 'profiles', 'owners', 'service_history',
                          'driving_style_baselines', 'component_health']

        print("\n[#] Current data in Desktop database:")
        for table in tables_to_clean:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   - {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"   - {table}: table doesn't exist")

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
    """Clean all unified users from Server database"""
    print("\n" + "="*60)
    print("[PC]  SERVER DATABASE CLEANUP")
    print("="*60)

    SERVER_DB_PATH = find_existing_path(SERVER_DB_PATHS)
    print(f"   Using database: {SERVER_DB_PATH}")

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found at any expected location")
        print(f"   Tried: {[str(p) for p in SERVER_DB_PATHS]}")
        return False

    try:
        conn = sqlite3.connect(str(SERVER_DB_PATH))
        cursor = conn.cursor()

        tables_to_clean = [
            'usage_counters',
            'rate_limits',
            'entitlements',
            'driver_assignments',
            'unified_api_keys',
            'unified_users',
            'tier_presets',
            'login_verification_codes'
        ]

        print("\n[#] Current data in Server database:")
        for table in tables_to_clean:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   - {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"   - {table}: table doesn't exist")

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
        print(f"[i]  API keys file not found (already clean)")
        return True

    try:
        with open(SERVER_API_KEYS_PATH, 'r') as f:
            keys = json.load(f)
        print(f"\n[#] Current API keys in file: {len(keys)}")

        if len(keys) == 0:
            print("[i]  File is already empty")
            return True

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
    """Initialize the tier presets and create all unified user tables"""
    print("\n" + "="*60)
    print("[TIER]  INITIALIZING UNIFIED USER TABLES & TIER PRESETS")
    print("="*60)

    SERVER_DB_PATH = find_existing_path(SERVER_DB_PATHS)

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found")
        return False

    try:
        conn = sqlite3.connect(str(SERVER_DB_PATH))
        cursor = conn.cursor()

        # Create ALL unified user tables
        print("   Creating unified user tables...")

        # unified_users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                created_at REAL NOT NULL,
                updated_at REAL,
                status TEXT DEFAULT 'active',
                role TEXT DEFAULT 'owner',
                tier TEXT DEFAULT 'free'
            )
        ''')
        print("   [OK] unified_users table created")

        # unified_api_keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_api_keys (
                key_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at REAL NOT NULL,
                last_used_at REAL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES unified_users(user_id)
            )
        ''')
        print("   [OK] unified_api_keys table created")

        # entitlements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entitlements (
                entitlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                granted_at REAL NOT NULL,
                granted_by INTEGER,
                UNIQUE(user_id, feature),
                FOREIGN KEY (user_id) REFERENCES unified_users(user_id)
            )
        ''')
        print("   [OK] entitlements table created")

        # rate_limits table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                limit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                max_requests INTEGER,
                period TEXT NOT NULL DEFAULT 'day',
                UNIQUE(user_id, feature),
                FOREIGN KEY (user_id) REFERENCES unified_users(user_id)
            )
        ''')
        print("   [OK] rate_limits table created")

        # usage_counters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_counters (
                counter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                period_start REAL NOT NULL,
                period_type TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                UNIQUE(user_id, feature, period_start, period_type),
                FOREIGN KEY (user_id) REFERENCES unified_users(user_id)
            )
        ''')
        print("   [OK] usage_counters table created")

        # driver_assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS driver_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_user_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL,
                assigned_at REAL NOT NULL,
                FOREIGN KEY (driver_user_id) REFERENCES unified_users(user_id),
                FOREIGN KEY (owner_user_id) REFERENCES unified_users(user_id)
            )
        ''')
        print("   [OK] driver_assignments table created")

        # tier_presets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tier_presets (
                tier_name TEXT PRIMARY KEY,
                features TEXT NOT NULL,
                default_limits TEXT NOT NULL
            )
        ''')
        print("   [OK] tier_presets table created")

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


def create_admin_account(name: str, email: str, phone: str = None):
    """Create the initial admin account"""
    print("\n" + "="*60)
    print("[USER]  CREATING ADMIN ACCOUNT")
    print("="*60)

    SERVER_DB_PATH = find_existing_path(SERVER_DB_PATHS)

    if not SERVER_DB_PATH.exists():
        print(f"[X] Server database not found")
        return None

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
        print(f"\n[KEY] API Key (SAVE THIS!):")
        print(f"   {api_key}")

        return api_key

    except Exception as e:
        print(f"\n[X] Error creating admin account: {e}")
        return None


def main():
    """Main cleanup routine"""
    print("\n" + "="*70)
    print("   PREDICT - Fresh Start Cleanup Script (AUTO MODE)")
    print("   Unified Customer Management System")
    print("="*70)

    print("\nProceeding with automatic cleanup...")

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
    print("\n" + "="*60)
    print("[USER]  ADMIN ACCOUNT")
    print("="*60)
    api_key = create_admin_account(
        name="Omar Sobeh",
        email="omar.sobeh@outlook.com",
        phone=None
    )

    print("\n" + "="*70)
    if success:
        print("[OK] CLEANUP COMPLETE!")
        print("""
Next steps:
1. Start the OBD Server
2. Start the PREDICT Desktop app
3. Go to the Profile tab
4. Click the info button on any customer to manage:
   - Tier (Free/Premium/Admin)
   - Features (toggle on/off)
   - Rate Limits (per feature)
   - API Keys (regenerate, copy, email)

All customer management is now done through the Profile tab!
""")
        if api_key:
            print(f"Your Admin API Key: {api_key}")
            print("\nSave this key - you'll need it for admin access!")
    else:
        print("[!]  CLEANUP COMPLETED WITH ERRORS")
        print("   Please check the error messages above.")
    print("="*70)


if __name__ == "__main__":
    main()
