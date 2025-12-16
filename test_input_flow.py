#!/usr/bin/env python3
"""
Test the complete input flow from WebSocket to terminal
"""
import asyncio
import json
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.session_manager import SessionManager

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_input_flow():
    """Test the complete input flow"""
    print("🧪 Testing complete input flow...")
    
    session_manager = SessionManager()
    client_id = "test-input-flow"
    
    try:
        print("1. Creating session...")
        session = await session_manager.get_session(client_id)
        print(f"   ✅ Session created: active={session.is_active}, process={session.process is not None}")
        
        print("2. Testing direct input (simulating WebSocket message)...")
        # Simulate what the WebSocket handler does
        input_text = "echo 'direct test'"
        
        # Check session state
        session = await session_manager.get_session(client_id)
        if not session.is_active:
            print(f"   ❌ Session not active!")
            return
        
        # Send input
        await session_manager.send_input(client_id, input_text, newline=False, from_ai=False)
        print(f"   ✅ Direct input sent: {input_text}")
        
        # Wait for output
        await asyncio.sleep(1)
        
        print("3. Testing AI proxy enable/disable cycle...")
        
        # Enable AI proxy
        success = await session_manager.enable_ai_proxy(client_id, "gemini-cli")
        print(f"   AI proxy enabled: {success}")
        
        if success:
            # Test input with AI proxy enabled
            input_text = "echo 'with ai proxy'"
            session = await session_manager.get_session(client_id)
            if session.is_active:
                await session_manager.send_input(client_id, input_text, newline=False, from_ai=False)
                print(f"   ✅ Input with AI proxy sent: {input_text}")
                
                # Notify AI proxy (simulating WebSocket handler)
                ai_proxy = session_manager.get_ai_proxy(client_id)
                if ai_proxy and ai_proxy.is_enabled():
                    ai_proxy.notify_user_input(input_text)
                    print(f"   ✅ AI proxy notified")
            else:
                print(f"   ❌ Session not active after AI proxy enable!")
            
            await asyncio.sleep(1)
            
            # Disable AI proxy
            await session_manager.disable_ai_proxy(client_id)
            print(f"   ✅ AI proxy disabled")
        
        print("4. Testing input after AI proxy operations...")
        input_text = "echo 'after ai operations'"
        
        session = await session_manager.get_session(client_id)
        if session.is_active:
            await session_manager.send_input(client_id, input_text, newline=False, from_ai=False)
            print(f"   ✅ Post-AI input sent: {input_text}")
        else:
            print(f"   ❌ Session not active after AI proxy operations!")
        
        await asyncio.sleep(1)
        
        print("5. Final session state check...")
        session = await session_manager.get_session(client_id)
        print(f"   Session active: {session.is_active}")
        print(f"   Process exists: {session.process is not None}")
        if session.process:
            print(f"   Process alive: {session.process.isalive()}")
        
        ai_proxy = session_manager.get_ai_proxy(client_id)
        print(f"   AI proxy exists: {ai_proxy is not None}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleaning up...")
        await session_manager.close_all()

if __name__ == "__main__":
    asyncio.run(test_input_flow())