"""
WebSocket Connection Test Script
Tests the WebSocket real-time streaming functionality.
"""

import asyncio
import websockets
import json
import time

# Server configuration
SERVER_URL = "ws://localhost:8000/ws?profile_id=1"
TEST_PROFILE_ID = 1


async def test_websocket_connection():
    """Test WebSocket connection and data streaming"""
    print("=" * 60)
    print("PHASE 13: WebSocket Real-Time Streaming Test")
    print("=" * 60)
    
    try:
        # Connect to WebSocket
        print(f"\n[TEST 1] Connecting to WebSocket...")
        async with websockets.connect(SERVER_URL) as websocket:
            print(f"[TEST 1] Connected successfully")
            
            # Send initial message
            print(f"\n[TEST 2] Sending initial message...")
            await websocket.send(json.dumps({
                "type": "test",
                "message": "Hello from WebSocket test client"
            }))
            
            # Receive messages
            print(f"\n[TEST 3] Listening for messages (10 seconds)...")
            
            received_count = 0
            start_time = time.time()
            
            while time.time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    received_count += 1
                    print(f"[TEST 3.{received_count}] Received: {data}")
                except asyncio.TimeoutError:
                    print("[TEST 3] Timeout waiting for message")
                    break
            
            print(f"\n[TEST 4] Received {received_count} messages in 10 seconds")
            
            # Test closing
            print(f"\n[TEST 5] Closing connection...")
            await websocket.close()
            print("[TEST 5] Connection closed")
            
    except Exception as e:
        print(f"\n[ERROR] WebSocket test failed: {e}")
        return False
    
    print("\n" + "=" * 60)


async def test_websocket_stats():
    """Test WebSocket stats endpoint"""
    import aiohttp
    
    print("\n[TEST 6] Testing WebSocket stats endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test stats endpoint
            async with session.get("http://localhost:8000/api/websocket/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"[TEST 6] Stats: {json.dumps(data, indent=2)}")
                    print(f"[TEST 6] Total connections: {data.get('stats', {}).get('total_connections', 0)}")
                    print(f"[TEST 6] Profiles connected: {data.get('stats', {}).get('profiles_connected', 0)}")
                else:
                    print(f"[TEST 6] Error: {response.status}")
                    return False
    except Exception as e:
        print(f"[ERROR] Stats test failed: {e}")
        return False
    
    print("\n" + "=" * 60)


def main():
    """Run all WebSocket tests"""
    print("\n" + "=" * 80)
    print("PHASE 13: WebSocket Real-Time Streaming Tests")
    print("=" * 80)
    
    # Test 1: Basic connection
    asyncio.run(test_websocket_connection())
    
    # Test 2: Stats endpoint
    asyncio.run(test_websocket_stats())
    
    print("\n" + "=" * 80)
    print("\nPHASE 13 COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
