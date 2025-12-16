#!/usr/bin/env python3
"""
Test script to verify single connection per session fix
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_single_connection():
    """Test that only one connection per session is allowed"""
    
    # Test session ID
    session_id = "test-single-connection"
    ws_url = f"ws://localhost:8801/ws/{session_id}?token=13241324"
    
    connections = []
    
    try:
        # Create multiple connections to the same session
        logger.info("Creating 3 connections to the same session...")
        
        for i in range(3):
            logger.info(f"Creating connection {i+1}...")
            ws = await websockets.connect(ws_url)
            connections.append(ws)
            
            # Send a test message
            await ws.send(json.dumps({"input": f"echo 'Connection {i+1}'\n"}))
            
            # Wait a bit between connections
            await asyncio.sleep(0.5)
        
        logger.info("All connections created. Waiting for responses...")
        
        # Wait for responses and check which connections are still active
        active_connections = 0
        for i, ws in enumerate(connections):
            try:
                # Try to receive a message with timeout
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                logger.info(f"Connection {i+1} received: {response[:100]}")
                active_connections += 1
            except asyncio.TimeoutError:
                logger.info(f"Connection {i+1} timed out (likely closed)")
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Connection {i+1} was closed")
        
        logger.info(f"Active connections: {active_connections}")
        
        if active_connections == 1:
            logger.info("✅ SUCCESS: Only one connection remained active")
        else:
            logger.error(f"❌ FAILURE: {active_connections} connections are active (should be 1)")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        # Clean up connections
        for ws in connections:
            try:
                await ws.close()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(test_single_connection())