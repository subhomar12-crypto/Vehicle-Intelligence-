import sqlite3
import time

# Connect to Desktop app's vehicle profiles database
conn = sqlite3.connect('data/vehicle_profiles.db')
cursor = conn.cursor()

current_time = time.time()

# Test vehicle data matching the backend
test_vehicle = {
    'profile_id': 999,
    'name': 'Test Driver - John Smith',
    'make': 'Toyota',
    'model': 'Camry',
    'year': 2020,
    'vin': '1HGBH41JXMN109186',
    'license_plate': 'TEST-123',
    'category': 'Sedan',
    'fuel_type': 'Gasoline',
    'created_at': current_time,
    'last_used': current_time,
    'is_connected': False,
    'is_favorite': False,
    'maintenance_count': 0,
    'trip_count': 0,
    'total_costs': 0.0,
    'total_distance': 0.0,
    'total_driving_hours': 0.0,
    'updated_at': current_time,
    'last_seen': current_time,
    'ever_connected': True,
    'customer_name': 'Test Driver - John Smith',
    'customer_email': 'testdriver@previlium.com',
    'customer_phone': '+971509876543',
    'profile_type': 'customer',
    'owner_id': 3,
    'api_key': 'TESTDRIVER-API-KEY-123'
}

try:
    cursor.execute("""
        INSERT INTO vehicle_profiles (
            profile_id, name, make, model, year, vin, license_plate, category, fuel_type,
            created_at, last_used, is_connected, is_favorite, maintenance_count, trip_count,
            total_costs, total_distance, total_driving_hours, updated_at, last_seen, ever_connected,
            customer_name, customer_email, customer_phone, profile_type, owner_id, api_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        test_vehicle['profile_id'],
        test_vehicle['name'],
        test_vehicle['make'],
        test_vehicle['model'],
        test_vehicle['year'],
        test_vehicle['vin'],
        test_vehicle['license_plate'],
        test_vehicle['category'],
        test_vehicle['fuel_type'],
        test_vehicle['created_at'],
        test_vehicle['last_used'],
        test_vehicle['is_connected'],
        test_vehicle['is_favorite'],
        test_vehicle['maintenance_count'],
        test_vehicle['trip_count'],
        test_vehicle['total_costs'],
        test_vehicle['total_distance'],
        test_vehicle['total_driving_hours'],
        test_vehicle['updated_at'],
        test_vehicle['last_seen'],
        test_vehicle['ever_connected'],
        test_vehicle['customer_name'],
        test_vehicle['customer_email'],
        test_vehicle['customer_phone'],
        test_vehicle['profile_type'],
        test_vehicle['owner_id'],
        test_vehicle['api_key']
    ))

    print(f"[OK] Created test vehicle in Desktop app database")
    print(f"     Profile ID: {test_vehicle['profile_id']}")
    print(f"     Name: {test_vehicle['name']}")
    print(f"     Vehicle: {test_vehicle['year']} {test_vehicle['make']} {test_vehicle['model']}")
    print(f"     VIN: {test_vehicle['vin']}")
    print(f"     License Plate: {test_vehicle['license_plate']}")

    conn.commit()

except sqlite3.IntegrityError as e:
    print(f"[INFO] Vehicle already exists or constraint violation: {e}")

    # Try to update instead
    cursor.execute("""
        UPDATE vehicle_profiles
        SET name=?, make=?, model=?, year=?, vin=?, license_plate=?, updated_at=?, last_seen=?
        WHERE profile_id=?
    """, (
        test_vehicle['name'],
        test_vehicle['make'],
        test_vehicle['model'],
        test_vehicle['year'],
        test_vehicle['vin'],
        test_vehicle['license_plate'],
        current_time,
        current_time,
        test_vehicle['profile_id']
    ))
    print(f"[OK] Updated existing vehicle profile {test_vehicle['profile_id']}")
    conn.commit()

# Verify it was added
cursor.execute("SELECT profile_id, name, make, model, year, vin, license_plate FROM vehicle_profiles WHERE profile_id=999")
result = cursor.fetchone()
if result:
    print(f"\n[VERIFY] Vehicle found in database:")
    print(f"         Profile ID: {result[0]}")
    print(f"         Name: {result[1]}")
    print(f"         Vehicle: {result[4]} {result[2]} {result[3]}")
    print(f"         VIN: {result[5]}")
    print(f"         Plate: {result[6]}")
else:
    print("\n[ERROR] Vehicle not found after insertion!")

conn.close()

print("\n[OK] Test vehicle added to Desktop app!")
print("     Restart the Desktop app to see the new vehicle.")
