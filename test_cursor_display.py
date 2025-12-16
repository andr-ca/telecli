#!/usr/bin/env python3
"""
Test script to verify cursor display on terminal reconnection
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_cursor_display():
    """Test that cursor appears when reconnecting to existing session"""
    uri = "ws://localhost:8801/ws"
    headers = {"Authorization": "Bearer 13241324"}
    
    try:
        # First connection - create a session
        logger.info("Creating initial connection...")
        ws1 = await websockets.connect(uri, extra_headers=headers)
        
        # Wait for initial terminal output
        await asyncio.sleep(1)
        
        # Try to receive initial output
        try:
            response = await asyncio.wait_for(ws1.recv(), timeout=2.0)
            logger.info(f"Initial output received: {len(response)} bytes")
        except asyncio.TimeoutError:
            logger.info("No initial output (expected)")
        
        # Close first connection
        await ws1.close()
        logger.info("Closed first connection")
        
        # Wait a moment
        await asyncio.sleep(0.5)
        
        # Second connection - reconnect to same session
        logger.info("Reconnecting to existing session...")
        ws2 = await websockets.connect(uri, extra_headers=headers)
        
        # Wait for reconnection output (should include cursor refresh)
        await asyncio.sleep(1)
        
        # Try to receive reconnection output
        try:
            response = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            logger.info(f"Reconnection output received: {len(response)} bytes")
            # Check if it contains cursor/prompt indicators
            if '\x1b[' in response:  # ANSI escape sequences (cursor positioning)
                logger.info("✅ ANSI sequences detected - cursor likely visible")
            else:
                logger.warning("⚠️ No ANSI sequences - cursor might not be visible")
        except asyncio.TimeoutError:
            logger.warning("⚠️ No reconnection output received")
        
        # Send a test command to see if cursor responds
        logger.info("Sending test input...")
        await ws2.send(json.dumps({"input": "echo 'cursor test'"}))
        
        # Wait for command output
        try:
            response = await asyncio.wait_for(ws2.recv(), timeout=3.0)
            logger.info(f"Command output received: {len(response)} bytes")
            if 'cursor test' in response:
                logger.info("✅ Command executed successfully - terminal is responsive")
            else:
                logger.info("Command output doesn't contain expected text")
        except asyncio.TimeoutError:
            logger.warning("⚠️ No command output received")
        
        await ws2.close()
        logger.info("Test completed")
        
    except Exception as e:
        logger.error(f"Test error: {e}")

if __name__ == "__main__":
    print("Testing cursor display on reconnection...")
    print("This will create a session, disconnect, then reconnect to test cursor visibility")
    print("Check the server logs for 'Refreshed terminal prompt' messages")
    
    asyncio.run(test_cursor_display())