#!/usr/bin/env python3
"""
Debug script to test terminal input handling
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

async def test_terminal_input():
    """Test terminal input handling"""
    print("🔍 Testing terminal input handling...")
    
    # Create session manager
    session_manager = SessionManager()
    test_session_id = "debug-test-session"
    
    try:
        # Create a session
        print(f"📝 Creating session: {test_session_id}")
        await session_manager.get_session(test_session_id)
        print(f"✅ Session created successfully")
        
        # Test basic input
        print("📤 Testing basic input: 'echo hello'")
        await session_manager.send_input(test_session_id, "echo hello", newline=True)
        print("✅ Input sent successfully")
        
        # Wait a bit for output
        print("⏳ Waiting for output...")
        await asyncio.sleep(2)
        
        # Test character-by-character input (like AI proxy does)
        print("📤 Testing character-by-character input: 'ls'")
        for char in "ls":
            await session_manager.send_input(test_session_id, char, newline=False)
            await asyncio.sleep(0.1)
        await session_manager.send_input(test_session_id, "\r", newline=False)
        print("✅ Character-by-character input sent successfully")
        
        # Wait for output
        await asyncio.sleep(2)
        
        # Test AI proxy functionality
        print("🤖 Testing AI proxy creation...")
        success = await session_manager.enable_ai_proxy(test_session_id, "gemini-cli")
        if success:
            print("✅ AI proxy enabled successfully")
            
            # Get AI proxy and test it
            ai_proxy = session_manager.get_ai_proxy(test_session_id)
            if ai_proxy:
                print(f"📊 AI proxy status: {ai_proxy.get_status()}")
                
                # Test notify_user_input
                print("📤 Testing notify_user_input...")
                ai_proxy.notify_user_input("test input")
                print("✅ notify_user_input completed")
                
                # Disable AI proxy
                print("🔄 Disabling AI proxy...")
                await session_manager.disable_ai_proxy(test_session_id)
                print("✅ AI proxy disabled")
            else:
                print("❌ Failed to get AI proxy instance")
        else:
            print("❌ Failed to enable AI proxy")
        
        # Test input after AI proxy operations
        print("📤 Testing input after AI proxy operations: 'pwd'")
        await session_manager.send_input(test_session_id, "pwd", newline=True)
        print("✅ Post-AI-proxy input sent successfully")
        
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        logger.exception("Test failed")
    finally:
        # Clean up
        print("🧹 Cleaning up...")
        await session_manager.close_session(test_session_id)
        await session_manager.close_all()
        print("✅ Cleanup completed")

if __name__ == "__main__":
    print("🚀 Starting terminal input debug test...")
    asyncio.run(test_terminal_input())
    print("🏁 Debug test completed")