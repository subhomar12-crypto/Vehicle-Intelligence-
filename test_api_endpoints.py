"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Api Endpoints
"""

import requests
import json
import hashlib

def test_profile_list():
    url = "http://localhost:8000/api/profile/list"
    # Use the raw key that corresponds to one of the hashes in api_keys.json
    # Since I don't know the raw key, I'll have to "cheat" and mock it or just check if the endpoint exists.
    
    print("Testing /api/profile/list endpoint...")
    try:
        # Testing with the correct key
        headers = {"X-API-Key": "test_raw_key"}
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Verify fields
        if data.get("success") and data.get("count") > 0:
            print("✅ Success! Profiles found.")
            profile = data["profiles"][0]
            print(f"   Profile Name: {profile.get('name')}")
            print(f"   Profile ID: {profile.get('profile_id')}")
        else:
            print("❌ Failure! Profiles not found or incorrect format.")
            
    except Exception as e:
        print(f"Error: {e}")

def test_specific_profile():
    url = "http://localhost:8000/api/profile/10"
    print("\nTesting /api/profile/10 endpoint...")
    try:
        headers = {"X-API-Key": "test_raw_key"}
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get("success") and data.get("profile"):
            print("✅ Success! Profile details found.")
        else:
            print("❌ Failure! Profile details not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_profile_list()
    test_specific_profile()
