#!/usr/bin/env python3
"""
Simple debug script to check session state
"""
import asyncio
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.session_manager import SessionManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')

async def debug_session():
    """Debug session state"""
    session_manager = SessionManager()
    session_id = "test-debug"
    
    try:
        print("1. Creating session...")
        session = await session_manager.get_session(session_id)
        print(f"   Session active: {session.is_active}")
        print(f"   Session process: {session.process is not None}")
        
        print("2. Testing basic input...")
        await session_manager.send_input(session_id, "echo test", newline=True)
        print("   Input sent successfully")
        
        print("3. Enabling AI proxy...")
        success = await session_manager.enable_ai_proxy(session_id)
        print(f"   AI proxy enabled: {success}")
        
        if success:
            ai_proxy = session_manager.get_ai_proxy(session_id)
            print(f"   AI proxy exists: {ai_proxy is not None}")
            if ai_proxy:
                print(f"   AI proxy enabled: {ai_proxy.is_enabled()}")
        
        print("4. Testing input with AI proxy enabled...")
        await session_manager.send_input(session_id, "echo with ai", newline=True)
        print("   Input sent successfully")
        
        print("5. Disabling AI proxy...")
        await session_manager.disable_ai_proxy(session_id)
        ai_proxy = session_manager.get_ai_proxy(session_id)
        print(f"   AI proxy after disable: {ai_proxy is not None}")
        
        print("6. Testing input after AI proxy disabled...")
        await session_manager.send_input(session_id, "echo after disable", newline=True)
        print("   Input sent successfully")
        
        print("7. Session state after all operations:")
        session = await session_manager.get_session(session_id)
        print(f"   Session active: {session.is_active}")
        print(f"   Session process: {session.process is not None}")
        if session.process:
            print(f"   Process alive: {session.process.isalive()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await session_manager.close_all()

if __name__ == "__main__":
    asyncio.run(debug_session())