"""
Session manager for coordinating multiple terminal sessions
"""
import logging
from typing import Optional
from src.config import Config
from src.terminal import TerminalSession
from src.ai_proxy import AIProxy
from src.llm_providers import *  # Register all providers
from src.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages multiple terminal sessions"""

    def __init__(self, max_sessions: int = Config.TERMINAL_MAX_SESSIONS):
        self.max_sessions = max_sessions
        self.sessions: dict[str, TerminalSession] = {}
        self.session_count = 0
        self.ai_proxies: dict[str, AIProxy] = {}  # AI proxy per session

    async def get_session(self, session_id: str) -> TerminalSession:
        """Get or create a session for the given ID"""
        if session_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                logger.warning("Max sessions reached, closing oldest session")
                oldest_id = next(iter(self.sessions))
                await self.close_session(oldest_id)

            session = TerminalSession(session_id)
            if not await session.start():
                raise RuntimeError(f"Failed to start session {session_id}")
            
            self.sessions[session_id] = session
            self.session_count += 1
            logger.info(f"Created new session {session_id}, total sessions: {len(self.sessions)}")

        return self.sessions[session_id]

    async def send_input(self, session_id: str, text: str, newline: bool = True) -> None:
        """Send input to a session"""
        session = await self.get_session(session_id)
        logger.debug(f"SessionManager.send_input called with: text={repr(text[:100])}, newline={newline}")
        await session.send_input(text, newline)
        logger.debug(f"✓ Sent input to session {session_id}")

    async def resize_session(self, session_id: str, rows: int, cols: int) -> None:
        """Resize a terminal session"""
        if session_id in self.sessions:
            await self.sessions[session_id].resize(rows, cols)
            logger.debug(f"Resized session {session_id} to {rows}x{cols}")

    async def get_output_stream(self, session_id: str):
        """Get output stream from a session"""
        session = await self.get_session(session_id)
        async for chunk in session.get_output_stream():
            yield chunk

    async def enable_ai_proxy(
        self, 
        session_id: str, 
        provider_name: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> bool:
        """Enable AI proxy for a session"""
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        # Use config provider or specified provider
        provider_name = provider_name or Config.AI_PROXY_PROVIDER
        
        # Create LLM provider
        llm_provider = LLMProviderFactory.create(provider_name)
        if not llm_provider:
            logger.error(f"Failed to create LLM provider: {provider_name}")
            return False
        
        # Use custom system prompt or config default
        prompt = system_prompt or Config.AI_PROXY_SYSTEM_PROMPT
        
        # Create AI proxy
        ai_proxy = AIProxy(
            llm_provider=llm_provider,
            system_prompt=prompt,
            max_iterations=Config.AI_PROXY_MAX_ITERATIONS
        )
        
        # Set callback to send input to terminal
        async def send_input(text: str):
            logger.info(f"💬 AI Proxy callback invoked to send text to terminal: {repr(text[:100])}")
            # Use sendline (newline=True) to properly submit the input
            await self.send_input(session_id, text, newline=True)
            logger.info(f"✓ Text sent to session {session_id}")
        
        ai_proxy.set_input_callback(send_input)
        ai_proxy.enable()
        
        self.ai_proxies[session_id] = ai_proxy
        logger.info(f"Enabled AI proxy for session {session_id} with provider {provider_name}")
        return True
    
    async def disable_ai_proxy(self, session_id: str):
        """Disable AI proxy for a session"""
        if session_id in self.ai_proxies:
            self.ai_proxies[session_id].disable()
            del self.ai_proxies[session_id]
            logger.info(f"Disabled AI proxy for session {session_id}")
    
    def get_ai_proxy(self, session_id: str) -> Optional[AIProxy]:
        """Get AI proxy for a session"""
        return self.ai_proxies.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close a specific session"""
        if session_id in self.sessions:
            try:
                # Disable AI proxy if active
                if session_id in self.ai_proxies:
                    await self.disable_ai_proxy(session_id)
                
                await self.sessions[session_id].stop()
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
            del self.sessions[session_id]
            logger.info(f"Closed session {session_id}, remaining sessions: {len(self.sessions)}")

    async def close_all(self) -> None:
        """Close all sessions"""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        logger.info("All sessions closed")

    def get_stats(self) -> dict:
        """Get session statistics"""
        return {
            "active_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
            "total_created": self.session_count,
        }
