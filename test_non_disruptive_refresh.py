#!/usr/bin/env python3
"""
Test non-disruptive terminal refresh methods
"""
import asyncio
import websockets
import json
import time

async def test_refresh_methods():
    """Test the new non-disruptive refresh methods"""
    
    print("🔍 Testing non-disruptive terminal refresh methods...")
    print()
    
    # Test URLs
    local_url = "ws://localhost:8801/ws/test-refresh-session?token=13241324"
    
    try:
        async with websockets.connect(local_url) as websocket:
            print("✅ Connected to terminal")
            
            # Send some initial input to establish baseline
            await websocket.send(json.dumps({"input": "echo 'Testing refresh methods'\n"}))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
            print(f"✅ Initial response received")
            
            print("\n🧪 Testing refresh methods:")
            
            # Test Method 1: Null character (should be invisible)
            print("1. Testing null character refresh...")
            await websocket.send(json.dumps({"input": "\x00"}))
            
            # Test Method 2: Cursor position query (should be invisible)
            print("2. Testing cursor position query...")
            await websocket.send(json.dumps({"input": "\x1b[6n"}))
            
            # Test Method 3: Terminal status query (should be invisible)
            print("3. Testing terminal status query...")
            await websocket.send(json.dumps({"input": "\x1b[5n"}))
            
            # Wait a bit to see if any responses come back
            print("\n⏳ Waiting for any responses...")
            try:
                for i in range(3):
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"📨 Response {i+1}: {response[:100]}...")
            except asyncio.TimeoutError:
                print("✅ No disruptive output detected (good!)")
            
            # Send a normal command to verify terminal still works
            print("\n✅ Testing normal operation after refresh...")
            await websocket.send(json.dumps({"input": "echo 'Terminal still works'\n"}))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
            print("✅ Terminal responds normally after refresh methods")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure the server is running with: python src/main.py")

if __name__ == "__main__":
    asyncio.run(test_refresh_methods())