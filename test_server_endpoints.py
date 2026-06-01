"""
Test script for Phase 11: Server - Verify Core Endpoints
Tests the core API endpoints as specified in IMPLEMENTATION_TODO_PHASES.md
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("PHASE 11: Server - Verify Core Endpoints")
print("=" * 60)

# Test 1: Health check
print("\n[TEST 1] Health Check")
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: Profile list (will fail without API key - that's expected)
print("\n[TEST 2] Profile List (without API key)")
try:
    response = requests.get(f"{BASE_URL}/api/profile/list")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 3: Profile list with X-API-Key header
print("\n[TEST 3] Profile List (with X-API-Key header)")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/profile/list", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 4: Get active profile
print("\n[TEST 4] Get Active Profile (with X-API-Key)")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/get_active_profile", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 5: Get active profile with Authorization Bearer header
print("\n[TEST 5] Get Active Profile (with Authorization Bearer)")
try:
    headers = {"Authorization": "Bearer test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/get_active_profile", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 6: Vehicle data submission (requires valid API key)
print("\n[TEST 6] Submit Vehicle Data (with Authorization)")
try:
    headers = {"Authorization": "Bearer test-key-12345"}
    vehicle_data = {
        "profile_id": 1,
        "rpm": 2500,
        "speed": 65,
        "coolant_temp": 195,
        "engine_load": 45,
        "voltage": 14.2,
        "timestamp": time.time()
    }
    response = requests.post(f"{BASE_URL}/api/vehicle_data", json=vehicle_data, headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 7: Get latest vehicle data
print("\n[TEST 7] Get Latest Vehicle Data")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/vehicle_data/latest/1", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 8: Get vehicle data history
print("\n[TEST 8] Get Vehicle Data History")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/vehicle_data/history/1?limit=10", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 9: Submit DTC codes
print("\n[TEST 9] Submit DTC Codes")
try:
    headers = {"X-API-Key": "test-key-12345"}
    dtc_data = {
        "codes": ["P0301", "P0420"],
        "is_pending": False
    }
    response = requests.post(f"{BASE_URL}/api/dtc/submit/1", json=dtc_data, headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 10: Get active DTCs
print("\n[TEST 10] Get Active DTCs")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/dtc/active/1", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 11: Get DTC history
print("\n[TEST 11] Get DTC History")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/dtc/history/1?limit=10", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 12: Get DTC summary
print("\n[TEST 12] Get DTC Summary")
try:
    headers = {"X-API-Key": "test-key-12345"}
    response = requests.get(f"{BASE_URL}/api/dtc/summary/1", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 13: Server status
print("\n[TEST 13] Server Status")
try:
    response = requests.get(f"{BASE_URL}/api/v1/status")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 14: Health dashboard
print("\n[TEST 14] Health Dashboard")
try:
    response = requests.get(f"{BASE_URL}/api/v1/health/dashboard")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 15: Model health
print("\n[TEST 15] Model Health")
try:
    response = requests.get(f"{BASE_URL}/api/v1/health/models")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("PHASE 11: Core Endpoint Tests Complete")
print("=" * 60)
