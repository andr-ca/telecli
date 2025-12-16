#!/usr/bin/env python3
"""
Test script to verify connection management fixes
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_multiple_connections():
    """Test that multiple connections to same session are handled properly"""
    uri = "ws://localhost:8801/ws"
    headers = {"Authorization": "Bearer 13241324"}
    
    connections = []
    
    try:
        # Create multiple connections rapidly
        for i in range(3):
            logger.info(f"Creating connection {i+1}")
            ws = await websockets.connect(uri, extra_headers=headers)
            connections.append(ws)
            
            # Send a test message
            await ws.send(json.dumps({"input": f"echo 'Connection {i+1}'\n"}))
            
            # Brief delay between connections
            await asyncio.sleep(0.1)
        
        # Wait a bit to see responses
        await asyncio.sleep(2)
        
        # Try to receive from all connections
        for i, ws in enumerate(connections):
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                logger.info(f"Connection {i+1} received: {response[:100]}")
            except asyncio.TimeoutError:
                logger.info(f"Connection {i+1} timed out (expected if closed)")
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Connection {i+1} was closed (expected)")
    
    except Exception as e:
        logger.error(f"Test error: {e}")
    
    finally:
        # Clean up connections
        for i, ws in enumerate(connections):
            try:
                await ws.close()
                logger.info(f"Closed connection {i+1}")
            except:
                pass

if __name__ == "__main__":
    print("Testing connection management...")
    print("This will create multiple WebSocket connections to test duplication fixes")
    print("Check the server logs for connection management messages")
    
    asyncio.run(test_multiple_connections())