"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Verify Key
"""

import requests
import hashlib
import json

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

def test_api_key(api_key, server_url="http://localhost:8000"):
    print(f"Testing API Key: {api_key}")
    print(f"Target Server: {server_url}")
    
    headers = {
        "X-API-Key": api_key
    }
    
    try:
        # Test profile list endpoint
        url = f"{server_url}/api/profile/list"
        print(f"Calling GET {url}...")
        response = requests.get(url, headers=headers, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success! Server accepted the key.")
            print(f"Response: {json.dumps(data, indent=2)}")
            if data.get('profiles'):
                print(f"Found {len(data['profiles'])} profiles.")
                for p in data['profiles']:
                    print(f" - Profile: {p.get('name')} (ID: {p.get('profile_id')})")
        elif response.status_code == 401:
            print("❌ Unauthorized: The server rejected this API key.")
            print(f"Detail: {response.text}")
        else:
            print(f"❌ Unexpected error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Is the server running? Start it from the Connection tab in the desktop app.")

def _get_a_valid_key():
    try:
        if CONFIG:
            api_keys_path = CONFIG.API_KEYS_FILE
        else:
            # Fallback to relative path
            api_keys_path = Path("config/api_keys.json")
        if api_keys_path.exists():
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                keys = json.load(f)
                if keys:
                    # Just pick one for testing
                    return "sxgQSbMbU" # Default to the one we know should work
    except: pass
    return "sxgQSbMbU"

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Try to use provided key or find one
    target_key = sys.argv[1] if len(sys.argv) > 1 else _get_a_valid_key()
    
    test_api_key(target_key)
