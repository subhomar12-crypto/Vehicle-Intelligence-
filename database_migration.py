"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Database Migration
"""

import sqlite3
import os
import sys
from datetime import datetime

class DatabaseMigration:
    """Handle database schema migrations for vehicle profiles"""
    
    def __init__(self, db_path='./data/vehicle_profiles.db'):
        self.db_path = db_path
        self.ensure_data_directory()
    
    def ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs('./data', exist_ok=True)
    
    def get_current_version(self):
        """Get current database version"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='database_version'
            """)
            
            if cursor.fetchone():
                cursor.execute("SELECT version FROM database_version")
                row = cursor.fetchone()
                if row:
                    version = row[0]
                else:
                    version = 0
            else:
                version = 0
            
            conn.close()
            return version
        
        except Exception as e:
            print(f"⚠️ Could not read database version: {e}")
            return 0
    
    def set_version(self, version: int):
        """Set database version"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_version (
                version INTEGER PRIMARY KEY,
                updated_at DATETIME
            )
        """)
        
        cursor.execute("DELETE FROM database_version")
        cursor.execute(
            "INSERT INTO database_version (version, updated_at) VALUES (?, ?)",
            (version, datetime.now())
        )
        
        conn.commit()
        conn.close()
    
    def migrate_database(self):
        """Run all necessary migrations"""
        current_version = self.get_current_version()
        print(f"🔧 Current database version: {current_version}")
        
        # Use < instead of == so we can recover from partial migrations
        if current_version < 1:
            self.migrate_to_v1()
            current_version = 1
        
        if current_version < 2:
            self.migrate_to_v2()
            current_version = 2
        
        if current_version < 3:
            self.migrate_to_v3()
            current_version = 3

        # NEW: v4 – ensure all required columns exist (including license_plate)
        if current_version < 4:
            self.migrate_to_v4()
            current_version = 4

        # v5 – Add last_seen and ever_connected for online status tracking
        if current_version < 5:
            self.migrate_to_v5()
            current_version = 5

        # v6 – Create tables for new features (fillups, custom_alerts, geofences)
        if current_version < 6:
            self.migrate_to_v6()
            current_version = 6

        # v7 – Service management tables
        if current_version < 7:
            self.migrate_to_v7()
            current_version = 7

        # v8 – Add customer contact fields to vehicle_profiles
        if current_version < 8:
            self.migrate_to_v8()
            current_version = 8

        # v9 – Add parent-child profile hierarchy support
        if current_version < 9:
            self.migrate_to_v9()
            current_version = 9

        # v10 – Add drivers table for profile hierarchy (one-to-many: driver belongs to one vehicle)
        if current_version < 10:
            self.migrate_to_v10()
            current_version = 10

        # v11 – Add owners table for Owner → Vehicles → Drivers hierarchy
        if current_version < 11:
            self.migrate_to_v11()
            current_version = 11

        # v12 – Add API key fields to vehicle_profiles for mobile app integration
        if current_version < 12:
            self.migrate_to_v12()
            current_version = 12

        # v13 – Add owner_id field to vehicle_profiles for owner-vehicle relationships
        if current_version < 13:
            self.migrate_to_v13()
            current_version = 13

        # v14 – Add tier and customer relationship fields to owners table
        if current_version < 14:
            self.migrate_to_v14()
            current_version = 14

        print(f"✅ Database migrated to version: {current_version}")
        return current_version
    
    # -------------------------
    #   Individual migrations
    # -------------------------
    
    def migrate_to_v1(self):
        """Initial database schema"""
        print("🔄 Creating initial database schema (v1)...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                make TEXT,
                model TEXT,
                year INTEGER,
                vin TEXT,
                license_plate TEXT,
                category TEXT DEFAULT 'Personal',
                engine_type TEXT,
                transmission TEXT,
                fuel_type TEXT,
                drivetrain TEXT,
                color TEXT,
                purchase_date TEXT,
                last_service_date TEXT,
                dealer_info TEXT,
                warranty_info TEXT,
                insurance_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_categories (
                category_name TEXT PRIMARY KEY,
                color TEXT DEFAULT '#3498db',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT OR IGNORE INTO vehicle_categories (category_name, color)
            VALUES ('Personal', '#3498db')
        ''')
        
        conn.commit()
        conn.close()
        
        self.set_version(1)
        print("✅ Database version 1 created")
    
    def migrate_to_v2(self):
        """Add connection and favorite fields"""
        print("🔄 Adding connection & favorite fields (v2)...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN is_connected BOOLEAN DEFAULT 0")
            print("✅ Added column: is_connected")
        except sqlite3.OperationalError:
            print("ℹ️ Column already exists: is_connected")
        
        try:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN is_favorite BOOLEAN DEFAULT 0")
            print("✅ Added column: is_favorite")
        except sqlite3.OperationalError:
            print("ℹ️ Column already exists: is_favorite")
        
        conn.commit()
        conn.close()
        
        self.set_version(2)
        print("✅ Database version 2 migrated")
    
    def migrate_to_v3(self):
        """Add statistics fields"""
        print("🔄 Adding statistics fields (v3)...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        columns_to_add = [
            'total_distance REAL DEFAULT 0',
            'total_driving_hours REAL DEFAULT 0', 
            'maintenance_count INTEGER DEFAULT 0',
            'trip_count INTEGER DEFAULT 0',
            'total_costs REAL DEFAULT 0'
        ]
        
        for column_def in columns_to_add:
            col_name = column_def.split(' ')[0]
            try:
                cursor.execute(f"ALTER TABLE vehicle_profiles ADD COLUMN {column_def}")
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError:
                print(f"ℹ️ Column already exists: {col_name}")
        
        conn.commit()
        conn.close()
        
        self.set_version(3)
        print("✅ Database version 3 migrated")

    def migrate_to_v4(self):
        """
        v4: Ensure full schema on existing databases.
        Fixes errors like: 'table vehicle_profiles has no column named license_plate'
        by adding any missing columns safely.
        """
        print("🔄 Normalizing vehicle_profiles schema (v4)...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        required_columns = [
            "license_plate TEXT",
            "category TEXT DEFAULT 'Personal'",
            "engine_type TEXT",
            "transmission TEXT",
            "fuel_type TEXT",
            "drivetrain TEXT",
            "color TEXT",
            "purchase_date TEXT",
            "last_service_date TEXT",
            "dealer_info TEXT",
            "warranty_info TEXT",
            "insurance_details TEXT",
            "is_connected BOOLEAN DEFAULT 0",
            "is_favorite BOOLEAN DEFAULT 0",
            "total_distance REAL DEFAULT 0",
            "total_driving_hours REAL DEFAULT 0",
            "maintenance_count INTEGER DEFAULT 0",
            "trip_count INTEGER DEFAULT 0",
            "total_costs REAL DEFAULT 0",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ]

        for column_def in required_columns:
            col_name = column_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE vehicle_profiles ADD COLUMN {column_def}")
                print(f"✅ v4 added column: {col_name}")
            except sqlite3.OperationalError:
                print(f"ℹ️ Column already exists (v4): {col_name}")
        
        conn.commit()
        conn.close()

        self.set_version(4)
        print("✅ Database version 4 migrated (schema normalized)")

    def migrate_to_v5(self):
        """Add online status tracking fields"""
        print("🔄 Adding online status tracking fields (v5)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN last_seen DATETIME")
            print("✅ Added column: last_seen")
        except sqlite3.OperationalError:
            print("ℹ️ Column already exists: last_seen")

        try:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN ever_connected BOOLEAN DEFAULT 0")
            print("✅ Added column: ever_connected")
        except sqlite3.OperationalError:
            print("ℹ️ Column already exists: ever_connected")

        conn.commit()
        conn.close()

        self.set_version(5)
        print("✅ Database version 5 migrated")

    def migrate_to_v6(self):
        """Create tables for new features"""
        print("🔄 Creating tables for new features (v6)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fillups table (fuel tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fillups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                fillup_id TEXT UNIQUE,
                timestamp DATETIME,
                liters REAL,
                gallons REAL,
                cost REAL,
                cost_per_liter REAL,
                odometer_km REAL,
                odometer_miles REAL,
                full_tank BOOLEAN,
                fuel_grade TEXT,
                station_name TEXT,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')
        print("✅ Created table: fillups")

        # Custom alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                rule_id TEXT UNIQUE,
                name TEXT NOT NULL,
                parameter TEXT NOT NULL,
                condition TEXT NOT NULL,
                threshold REAL NOT NULL,
                threshold2 REAL,
                severity TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')
        print("✅ Created table: custom_alerts")

        # Geofences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geofences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geofence_id TEXT UNIQUE,
                name TEXT NOT NULL,
                center_lat REAL NOT NULL,
                center_lon REAL NOT NULL,
                radius_km REAL NOT NULL,
                zone_type TEXT DEFAULT 'custom',
                severity TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Created table: geofences")

        conn.commit()
        conn.close()

        self.set_version(6)
        print("✅ Database version 6 migrated")

    def migrate_to_v7(self):
        """Add service management tables"""
        print("🔄 Creating service management tables (v7)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Oil changes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oil_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                change_date DATETIME NOT NULL,
                odometer_km REAL NOT NULL,
                oil_type TEXT,
                filter_changed BOOLEAN DEFAULT 1,
                cost REAL,
                service_location TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')
        print("✅ Created table: oil_changes")

        # DTC scans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dtc_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                scan_timestamp DATETIME NOT NULL,
                codes_found INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')
        print("✅ Created table: dtc_scans")

        # DTC codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dtc_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                description TEXT,
                severity TEXT,
                detected_at DATETIME NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES dtc_scans(id)
            )
        ''')
        print("✅ Created table: dtc_codes")

        # Service reminders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                service_type TEXT NOT NULL,
                interval_km INTEGER,
                interval_days INTEGER,
                last_service_km REAL,
                last_service_date DATETIME,
                next_due_km REAL,
                next_due_date DATETIME,
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')
        print("✅ Created table: service_reminders")

        conn.commit()
        conn.close()

        self.set_version(7)
        print("✅ Database version 7 migrated")

    def migrate_to_v8(self):
        """Add customer contact fields to vehicle_profiles"""
        print("🔄 Adding customer contact fields to vehicle_profiles (v8)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current columns
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add customer_phone if not exists
        if 'customer_phone' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN customer_phone TEXT")
            print("✅ Added column: customer_phone")

        # Add customer_email if not exists
        if 'customer_email' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN customer_email TEXT")
            print("✅ Added column: customer_email")

        # Add customer_name if not exists (may already exist in some schemas)
        if 'customer_name' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN customer_name TEXT")
            print("✅ Added column: customer_name")

        conn.commit()
        conn.close()

        self.set_version(8)
        print("✅ Database version 8 migrated")

    def migrate_to_v9(self):
        """Add parent-child profile hierarchy support"""
        print("🔄 Adding parent-child profile hierarchy support (v9)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current columns
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add parent_profile_id for hierarchy
        if 'parent_profile_id' not in columns:
            cursor.execute("""
                ALTER TABLE vehicle_profiles
                ADD COLUMN parent_profile_id INTEGER DEFAULT NULL
                REFERENCES vehicle_profiles(profile_id) ON DELETE SET NULL
            """)
            print("✅ Added column: parent_profile_id")

        # Add profile_type (guardian, child, standalone)
        if 'profile_type' not in columns:
            cursor.execute("""
                ALTER TABLE vehicle_profiles
                ADD COLUMN profile_type TEXT DEFAULT 'standalone'
            """)
            print("✅ Added column: profile_type")

        conn.commit()
        conn.close()

        self.set_version(9)
        print("✅ Database version 9 migrated - Parent-child hierarchy enabled")

    def migrate_to_v10(self):
        """Add drivers table for profile hierarchy (one-to-many model)"""
        print("🔄 Creating drivers table for profile hierarchy (v10)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create drivers table - each driver belongs to exactly one vehicle profile
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                driver_id TEXT PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER,
                license_number TEXT,
                phone TEXT,
                email TEXT,
                photo_url TEXT,
                is_primary INTEGER DEFAULT 0,
                relationship TEXT DEFAULT 'driver',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                synced_at DATETIME,
                server_updated_at DATETIME,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id) ON DELETE CASCADE
            )
        ''')
        print("✅ Created table: drivers")

        # Create index on profile_id for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drivers_profile_id
            ON drivers(profile_id)
        ''')
        print("✅ Created index: idx_drivers_profile_id")

        # Create index on is_active for filtering
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_drivers_active
            ON drivers(profile_id, is_active)
        ''')
        print("✅ Created index: idx_drivers_active")

        # Create driver_sessions table for tracking active driving sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS driver_sessions (
                session_id TEXT PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                driver_id TEXT NOT NULL,
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                distance_km REAL DEFAULT 0,
                duration_minutes REAL DEFAULT 0,
                safety_score INTEGER,
                violations_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                synced_at DATETIME,
                FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id) ON DELETE CASCADE,
                FOREIGN KEY (driver_id) REFERENCES drivers(driver_id) ON DELETE CASCADE
            )
        ''')
        print("✅ Created table: driver_sessions")

        # Create index for active sessions lookup
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_driver_sessions_active
            ON driver_sessions(profile_id, status)
        ''')
        print("✅ Created index: idx_driver_sessions_active")

        # Add api_key column to vehicle_profiles for per-profile authentication
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'api_key' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN api_key TEXT")
            print("✅ Added column: api_key to vehicle_profiles")

        if 'api_key_created_at' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN api_key_created_at DATETIME")
            print("✅ Added column: api_key_created_at to vehicle_profiles")

        conn.commit()
        conn.close()

        self.set_version(10)
        print("✅ Database version 10 migrated - Drivers table and sessions enabled")

    def migrate_to_v11(self):
        """Add owners table for Owner → Vehicles → Drivers hierarchy"""
        print("🔄 Creating owners table and migrating data (v11)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create owners table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS owners (
                owner_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                api_key TEXT,
                api_key_hash TEXT,
                role TEXT DEFAULT 'owner',
                apps TEXT DEFAULT 'obd,guardian',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Created table: owners")

        # Create index on owner name for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_owners_name
            ON owners(name)
        ''')
        print("✅ Created index: idx_owners_name")

        # Add owner_id column to vehicle_profiles
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'owner_id' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN owner_id INTEGER REFERENCES owners(owner_id)")
            print("✅ Added column: owner_id to vehicle_profiles")

        # Auto-migrate existing profiles: profile name → owner name
        cursor.execute('''
            SELECT profile_id, name, make, model, year, customer_email, customer_phone, api_key
            FROM vehicle_profiles
            WHERE owner_id IS NULL
        ''')
        profiles_to_migrate = cursor.fetchall()

        migrated_count = 0
        for profile in profiles_to_migrate:
            profile_id, name, make, model, year, email, phone, api_key = profile

            # Skip if no name or if name looks like a vehicle (contains make/model)
            if not name:
                continue

            # Check if owner already exists with this name
            cursor.execute('SELECT owner_id FROM owners WHERE name = ?', (name,))
            existing_owner = cursor.fetchone()

            if existing_owner:
                owner_id = existing_owner[0]
            else:
                # Create new owner from profile name
                cursor.execute('''
                    INSERT INTO owners (name, email, phone, api_key, role, apps)
                    VALUES (?, ?, ?, ?, 'owner', 'obd,guardian')
                ''', (name, email, phone, api_key))
                owner_id = cursor.lastrowid
                print(f"  → Created owner: {name} (ID: {owner_id})")

            # Update profile with owner_id and new vehicle-based name
            vehicle_name = f"{make} {model} {year}".strip() if make and model else name
            if vehicle_name != name:
                cursor.execute('''
                    UPDATE vehicle_profiles
                    SET owner_id = ?, name = ?
                    WHERE profile_id = ?
                ''', (owner_id, vehicle_name, profile_id))
                print(f"  → Profile {profile_id}: '{name}' → Owner, vehicle renamed to '{vehicle_name}'")
            else:
                cursor.execute('''
                    UPDATE vehicle_profiles
                    SET owner_id = ?
                    WHERE profile_id = ?
                ''', (owner_id, profile_id))

            migrated_count += 1

        conn.commit()
        conn.close()

        self.set_version(11)
        print(f"✅ Database version 11 migrated - Owners table created, {migrated_count} profiles migrated")

    def migrate_to_v12(self):
        """Add API key fields to vehicle_profiles for mobile app integration"""
        print("🔄 Adding API key fields to vehicle_profiles (v12)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check current columns
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add api_key column if it doesn't exist
        if 'api_key' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN api_key TEXT")
            print("✅ Added column: api_key to vehicle_profiles")
        else:
            print("ℹ️ Column already exists: api_key")

        # Add api_key_hash column if it doesn't exist
        if 'api_key_hash' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN api_key_hash TEXT")
            print("✅ Added column: api_key_hash to vehicle_profiles")
        else:
            print("ℹ️ Column already exists: api_key_hash")

        # Create index on api_key_hash for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_vehicle_profiles_api_key_hash
            ON vehicle_profiles(api_key_hash)
        ''')
        print("✅ Created index: idx_vehicle_profiles_api_key_hash")

        conn.commit()
        conn.close()

        self.set_version(12)
        print("✅ Database version 12 migrated - API key fields added to vehicle_profiles")

    def migrate_to_v13(self):
        """Add owner_id field to vehicle_profiles for owner-vehicle relationships"""
        print("🔄 Adding owner_id field to vehicle_profiles (v13)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check current columns
        cursor.execute("PRAGMA table_info(vehicle_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add owner_id column if it doesn't exist
        if 'owner_id' not in columns:
            cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN owner_id INTEGER")
            print("✅ Added column: owner_id to vehicle_profiles")
        else:
            print("ℹ️ Column already exists: owner_id")

        # Create index on owner_id for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_vehicle_profiles_owner_id
            ON vehicle_profiles(owner_id)
        ''')
        print("✅ Created index: idx_vehicle_profiles_owner_id")

        conn.commit()
        conn.close()

        self.set_version(13)
        print("✅ Database version 13 migrated - owner_id field added to vehicle_profiles")

    def migrate_to_v14(self):
        """Add tier and customer relationship fields to owners table"""
        print("🔄 Adding tier and customer fields to owners table (v14)...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if owners table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='owners'
        """)

        if not cursor.fetchone():
            print("ℹ️ Owners table doesn't exist yet, will be created by setup script")
            self.set_version(14)
            conn.close()
            return

        # Check current columns
        cursor.execute("PRAGMA table_info(owners)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add tier column if it doesn't exist
        if 'tier' not in columns:
            cursor.execute("ALTER TABLE owners ADD COLUMN tier TEXT DEFAULT 'free'")
            print("✅ Added column: tier to owners")
        else:
            print("ℹ️ Column already exists: tier")

        # Add tier_upgraded_at column if it doesn't exist
        if 'tier_upgraded_at' not in columns:
            cursor.execute("ALTER TABLE owners ADD COLUMN tier_upgraded_at REAL")
            print("✅ Added column: tier_upgraded_at to owners")
        else:
            print("ℹ️ Column already exists: tier_upgraded_at")

        # Add customer_id column if it doesn't exist
        if 'customer_id' not in columns:
            cursor.execute("ALTER TABLE owners ADD COLUMN customer_id INTEGER")
            print("✅ Added column: customer_id to owners")
        else:
            print("ℹ️ Column already exists: customer_id")

        # Create index on tier for filtering
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_owners_tier
            ON owners(tier)
        ''')
        print("✅ Created index: idx_owners_tier")

        # Create index on customer_id for joins
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_owners_customer_id
            ON owners(customer_id)
        ''')
        print("✅ Created index: idx_owners_customer_id")

        conn.commit()
        conn.close()

        self.set_version(14)
        print("✅ Database version 14 migrated - tier and customer fields added to owners")

    # -------------------------
    #   Backup & entry point
    # -------------------------
    
    def create_backup(self):
        """Create database backup"""
        backup_path = f"{self.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if os.path.exists(self.db_path):
            import shutil
            shutil.copy2(self.db_path, backup_path)
            print(f"✅ Database backed up to: {backup_path}")
            return backup_path
        return None

def run_migrations():
    """Run database migrations"""
    print("🔧 Starting database migration...")
    
    try:
        migrator = DatabaseMigration()
        
        backup_path = migrator.create_backup()
        if backup_path:
            print(f"📦 Backup created: {backup_path}")
        
        final_version = migrator.migrate_database()
        print(f"🎉 Database migration completed successfully! Version: {final_version}")
        return True
    
    except Exception as e:
        print(f"❌ Database migration failed: {e}")
        return False

if __name__ == "__main__":
    run_migrations()
