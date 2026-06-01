"""
Test script for Phase 12: Server - Guardian System (Teen Monitoring)
Tests Guardian API endpoints as specified in IMPLEMENTATION_TODO_PHASES.md
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("PHASE 12: Server - Guardian System (Teen Monitoring)")
print("=" * 60)

# Test 1: Health check (for Guardian API)
print("\n[TEST 1] Health Check")
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: Register guardian
print("\n[TEST 2] Register Guardian")
try:
    guardian_data = {
        "email": "parent@test.com",
        "password": "password123",
        "name": "Test Parent",
        "phone": "+9741234567"
    }
    response = requests.post(f"{BASE_URL}/api/guardian/auth/register", json=guardian_data)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 3: Login guardian
print("\n[TEST 3] Login Guardian")
try:
    login_data = {
        "email": "parent@test.com",
        "password": "password123",
        "fcm_token": "test_fcm_token_12345"
    }
    response = requests.post(f"{BASE_URL}/api/guardian/auth/login", json=login_data)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    
    # Save token for subsequent tests
    if response.status_code == 200:
        token = response.json().get("token")
        print(f"  Token received: {token[:20]}...")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 4: Get guardian info (me endpoint)
print("\n[TEST 4] Get Guardian Info (Me)")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/auth/me", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 5: Link vehicle to guardian
print("\n[TEST 5] Link Vehicle to Guardian")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    link_data = {
        "profile_id": 1,
        "relationship": "parent"
    }
    response = requests.post(f"{BASE_URL}/api/guardian/vehicles/link", json=link_data, headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 6: Get linked vehicles
print("\n[TEST 6] Get Linked Vehicles")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/vehicles", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 7: Get guardian dashboard
print("\n[TEST 7] Get Guardian Dashboard")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/dashboard", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 8: Get alerts
print("\n[TEST 8] Get Alerts")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/alerts", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 9: Send warning command
print("\n[TEST 9] Send Warning Command")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    command_data = {
        "profile_id": 1,
        "message": "Test warning from parent",
        "command_type": "warning"
    }
    response = requests.post(f"{BASE_URL}/api/guardian/commands/send-warning", json=command_data, headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 10: Request location (emergency)
print("\n[TEST 10] Request Location (Emergency)")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    location_data = {
        "profile_id": 1,
        "reason": "Emergency location check"
    }
    response = requests.post(f"{BASE_URL}/api/guardian/commands/request-location", json=location_data, headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 11: Get live vehicle data
print("\n[TEST 11] Get Live Vehicle Data")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/vehicles/1/live", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 12: Get vehicle health
print("\n[TEST 12] Get Vehicle Health")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/vehicles/1/health", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 13: Get trips
print("\n[TEST 13] Get Trip History")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/trips/1", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 14: Get vehicle settings
print("\n[TEST 14] Get Vehicle Settings")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/settings/1", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 15: Get notification preferences
print("\n[TEST 15] Get Notification Preferences")
try:
    headers = {"Authorization": f"Bearer {token}"} if 'token' in locals() else None
    response = requests.get(f"{BASE_URL}/api/guardian/notification-preferences", headers=headers)
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("PHASE 12: Guardian Endpoint Tests Complete")
print("=" * 60)
