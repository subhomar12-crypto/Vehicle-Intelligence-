"""
Setup owners table and migrate existing customers for desktop app compatibility.

This script:
1. Creates the owners table if it doesn't exist
2. Adds owner_id column to vehicle_profiles if missing
3. Migrates existing customers to owners
4. Links vehicle_profiles to their corresponding owners
"""

import sqlite3
import sys
from pathlib import Path

# Database path
DB_PATH = Path(r"C:\OBDserver\Previlium_OBD_Server\data\vehicle_data.db")

def setup_owners_table():
    """Create owners table and migrate data"""

    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return False

    print(f"🔧 Setting up owners table in: {DB_PATH}")

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # STEP 1: Create owners table
        print("\n📋 Step 1: Creating owners table...")
        cur.execute('''
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

        # STEP 2: Add owner_id column to vehicle_profiles if missing
        print("\n📋 Step 2: Adding owner_id column to vehicle_profiles...")
        cur.execute("PRAGMA table_info(vehicle_profiles)")
        columns = {row[1] for row in cur.fetchall()}

        if 'owner_id' not in columns:
            cur.execute("ALTER TABLE vehicle_profiles ADD COLUMN owner_id INTEGER REFERENCES owners(owner_id)")
            print("✅ Added column: owner_id to vehicle_profiles")
        else:
            print("ℹ️  owner_id column already exists")

        # STEP 3: Migrate customers to owners
        print("\n📋 Step 3: Migrating customers to owners...")

        # Get all customers
        cur.execute('''
            SELECT id, name, email, phone, api_key, api_key_hash, created_at
            FROM customers
            WHERE verified = 1
            ORDER BY id
        ''')
        customers = cur.fetchall()

        print(f"Found {len(customers)} verified customers to migrate")

        migrated_count = 0
        for customer in customers:
            customer_id, name, email, phone, api_key, api_key_hash, created_at = customer

            # Check if owner already exists with this email or customer_id as owner_id
            existing_owner = None
            if email:
                cur.execute('SELECT owner_id FROM owners WHERE email = ?', (email,))
                existing_owner = cur.fetchone()

            if not existing_owner:
                # Use customer_id as owner_id for consistency
                cur.execute('SELECT owner_id FROM owners WHERE owner_id = ?', (customer_id,))
                existing_owner = cur.fetchone()

            if existing_owner:
                owner_id = existing_owner[0]
                print(f"  ℹ️  Owner already exists for {name} (owner_id={owner_id})")
            else:
                # Create new owner with customer_id as owner_id
                cur.execute('''
                    INSERT INTO owners (owner_id, name, email, phone, api_key, api_key_hash, role, apps, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'owner', 'obd,guardian', 1, ?)
                ''', (customer_id, name, email, phone, api_key, api_key_hash, created_at))
                owner_id = customer_id
                print(f"  ✅ Created owner: {name} (owner_id={owner_id})")
                migrated_count += 1

            # Link vehicle_profiles to owner via customer_id
            cur.execute('''
                UPDATE vehicle_profiles
                SET owner_id = ?
                WHERE customer_id = ? AND (owner_id IS NULL OR owner_id != ?)
            ''', (owner_id, customer_id, owner_id))

            updated_profiles = cur.rowcount
            if updated_profiles > 0:
                print(f"    → Linked {updated_profiles} vehicle(s) to owner")

        conn.commit()
        print(f"\n✅ Migrated {migrated_count} customers to owners")

        # STEP 4: Verify results
        print("\n📋 Step 4: Verifying migration...")

        cur.execute('SELECT COUNT(*) FROM owners')
        owner_count = cur.fetchone()[0]
        print(f"✅ Total owners: {owner_count}")

        cur.execute('SELECT COUNT(*) FROM vehicle_profiles WHERE owner_id IS NOT NULL')
        linked_profiles = cur.fetchone()[0]
        print(f"✅ Profiles linked to owners: {linked_profiles}")

        cur.execute('''
            SELECT vp.profile_id, vp.name, vp.license_plate, vp.owner_id, o.name as owner_name
            FROM vehicle_profiles vp
            LEFT JOIN owners o ON vp.owner_id = o.owner_id
            ORDER BY vp.profile_id
        ''')
        profiles = cur.fetchall()

        print(f"\n📊 Profile → Owner Linkage:")
        for profile in profiles:
            profile_id, vehicle_name, plate, owner_id, owner_name = profile
            if owner_id:
                print(f"  Profile {profile_id} ({vehicle_name}, Plate: {plate}) → Owner {owner_id} ({owner_name})")
            else:
                print(f"  ⚠️  Profile {profile_id} ({vehicle_name}, Plate: {plate}) → NO OWNER")

        conn.close()

        print("\n✅ Owner table setup complete!")
        return True

    except Exception as e:
        print(f"\n❌ Error setting up owners table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_owners_table()
    sys.exit(0 if success else 1)
