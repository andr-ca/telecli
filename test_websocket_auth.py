#!/usr/bin/env python3
"""
Test WebSocket authentication for Cloudflare tunnel
"""
import asyncio
import websockets
import json
import sys

async def test_websocket_auth():
    """Test WebSocket connection with authentication"""
    
    # Test URLs
    local_url = "ws://localhost:8801/ws/test-session-123?token=13241324"
    tunnel_url = "wss://code.andr.ca/telecli/ws/test-session-123?token=13241324"
    
    print("Testing WebSocket authentication...")
    print(f"Local URL: {local_url}")
    print(f"Tunnel URL: {tunnel_url}")
    print()
    
    # Test local connection first
    print("1. Testing local connection...")
    try:
        async with websockets.connect(local_url) as websocket:
            print("✅ Local connection successful!")
            
            # Send a test message
            await websocket.send(json.dumps({"input": "echo 'test'\n"}))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✅ Received response: {response[:100]}...")
            
    except Exception as e:
        print(f"❌ Local connection failed: {e}")
    
    print()
    
    # Test tunnel connection
    print("2. Testing tunnel connection...")
    try:
        async with websockets.connect(tunnel_url) as websocket:
            print("✅ Tunnel connection successful!")
            
            # Send a test message
            await websocket.send(json.dumps({"input": "echo 'tunnel test'\n"}))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✅ Received response: {response[:100]}...")
            
    except Exception as e:
        print(f"❌ Tunnel connection failed: {e}")
        print(f"Error type: {type(e).__name__}")
        if hasattr(e, 'status_code'):
            print(f"Status code: {e.status_code}")

if __name__ == "__main__":
    asyncio.run(test_websocket_auth())