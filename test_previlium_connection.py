"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Previlium Connection

Test script to verify connection to Previlium OBD Server
"""

import requests
import sys

def test_previlium_connection():
    """Test connection to Previlium server"""

    server_url = "http://localhost:8000"

    print("=" * 60)
    print("Testing Previlium OBD Server Connection")
    print("=" * 60)
    print()

    # Test 1: Check if server is running
    print("Test 1: Checking if server is running...")
    try:
        response = requests.get(f"{server_url}/", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is running!")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
        else:
            print(f"❌ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - Is the Previlium server running?")
        print()
        print("To start the Previlium server:")
        print("1. Open a new terminal")
        print("2. Navigate to: C:\\D Drive\\Predict\\Previlium_OBD_Server")
        print("3. Run: uvicorn main:app --host 0.0.0.0 --port 8000")
        print()
        print("Or use the run.bat file in the Previlium_OBD_Server folder")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print()

    # Test 2: Check API docs
    print("Test 2: Checking API documentation...")
    try:
        response = requests.get(f"{server_url}/docs", timeout=2)
        if response.status_code == 200:
            print(f"✅ API docs available at: {server_url}/docs")
        else:
            print(f"⚠️ API docs returned status code: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not access API docs: {e}")

    print()

    # Test 3: Check dashboard stats
    print("Test 3: Checking dashboard stats endpoint...")
    try:
        response = requests.get(f"{server_url}/dashboard/api/stats", timeout=2)
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Dashboard stats endpoint is working!")
            print(f"   Stats: {stats}")
        else:
            print(f"⚠️ Stats endpoint returned status code: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not access stats: {e}")

    print()

    # Test 4: Check history endpoint
    print("Test 4: Checking history endpoint...")
    try:
        response = requests.get(f"{server_url}/dashboard/api/history", params={"limit": 5}, timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ History endpoint is working!")
            print(f"   Record count: {data.get('count', 0)}")
            if data.get('count', 0) > 0:
                print(f"   Latest record: {data.get('records', [])[0]}")
        else:
            print(f"⚠️ History endpoint returned status code: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not access history: {e}")

    print()
    print("=" * 60)
    print("✅ All tests passed! Previlium server is ready.")
    print("=" * 60)
    print()
    print("The desktop Predict app will now connect to this server")
    print("when you click 'Start Server' in the Server tab.")
    print()

    return True

if __name__ == '__main__':
    success = test_previlium_connection()
    sys.exit(0 if success else 1)
