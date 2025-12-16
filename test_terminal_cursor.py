#!/usr/bin/env python3
"""
Test script to verify terminal cursor appears
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_terminal_cursor():
    """Test that terminal shows cursor/prompt on connection"""
    
    session_id = "test-cursor-display"
    ws_url = f"ws://localhost:8801/ws/{session_id}?token=13241324"
    
    try:
        logger.info("Connecting to terminal...")
        ws = await websockets.connect(ws_url)
        
        # Send terminal size
        await ws.send(json.dumps({
            "resize": {"rows": 24, "cols": 80}
        }))
        
        logger.info("Waiting for initial terminal output...")
        
        # Wait for initial output (should include prompt/cursor)
        output_received = False
        for i in range(10):  # Wait up to 5 seconds
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(response)
                if data.get("output"):
                    logger.info(f"Received output: {repr(data['output'][:100])}")
                    output_received = True
                    
                    # Check if it looks like a prompt
                    output = data["output"]
                    if any(char in output for char in ['$', '#', '>', '~']):
                        logger.info("✅ SUCCESS: Prompt/cursor detected in output")
                        break
                    else:
                        logger.info("Output received but no clear prompt detected")
                        
            except asyncio.TimeoutError:
                logger.info(f"No output in iteration {i+1}")
                continue
        
        if not output_received:
            logger.error("❌ FAILURE: No terminal output received")
        
        await ws.close()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_terminal_cursor())