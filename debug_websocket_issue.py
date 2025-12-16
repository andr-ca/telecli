#!/usr/bin/env python3
"""
Debug WebSocket connection closing issue
"""
import asyncio
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.session_manager import SessionManager

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def debug_websocket_issue():
    """Debug the WebSocket connection closing issue"""
    print("🔍 Debugging WebSocket connection closing issue...")
    
    session_manager = SessionManager()
    client_id = "debug-websocket-test"
    
    try:
        print("1. Creating session...")
        session = await session_manager.get_session(client_id)
        print(f"   ✅ Session created: active={session.is_active}, process={session.process is not None}")
        
        if session.process:
            print(f"   Process alive: {session.process.isalive()}")
            print(f"   Process PID: {session.process.pid}")
        
        print("2. Testing simple input...")
        test_input = "e"  # Single character like user typing
        
        try:
            await session_manager.send_input(client_id, test_input, newline=False, from_ai=False)
            print(f"   ✅ Input '{test_input}' sent successfully")
        except Exception as e:
            print(f"   ❌ Error sending input: {e}")
            import traceback
            traceback.print_exc()
        
        # Check session state after input
        await asyncio.sleep(0.5)
        session = await session_manager.get_session(client_id)
        print(f"   Session after input: active={session.is_active}")
        if session.process:
            print(f"   Process after input: alive={session.process.isalive()}")
        
        print("3. Testing multiple character input...")
        for char in "cho test":
            try:
                await session_manager.send_input(client_id, char, newline=False, from_ai=False)
                print(f"   ✅ Character '{char}' sent")
                await asyncio.sleep(0.1)
                
                # Check if session is still alive
                session = await session_manager.get_session(client_id)
                if not session.is_active:
                    print(f"   ❌ Session became inactive after character '{char}'!")
                    break
                    
            except Exception as e:
                print(f"   ❌ Error sending character '{char}': {e}")
                break
        
        print("4. Testing newline...")
        try:
            await session_manager.send_input(client_id, "\r", newline=False, from_ai=False)
            print("   ✅ Newline sent")
        except Exception as e:
            print(f"   ❌ Error sending newline: {e}")
        
        await asyncio.sleep(1)
        
        print("5. Final session state...")
        try:
            session = await session_manager.get_session(client_id)
            print(f"   Session active: {session.is_active}")
            if session.process:
                print(f"   Process alive: {session.process.isalive()}")
                print(f"   Process PID: {session.process.pid}")
        except Exception as e:
            print(f"   ❌ Error getting final session state: {e}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleaning up...")
        await session_manager.close_all()

if __name__ == "__main__":
    asyncio.run(debug_websocket_issue())