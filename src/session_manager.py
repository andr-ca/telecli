"""
Session manager for coordinating multiple terminal sessions
"""
import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from src.config import Config
from src.terminal import TerminalSession
from src.ai_proxy import AIProxy
from src.llm_providers import *  # Register all providers
from src.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)

# Grace period before closing disconnected sessions (allows browser refresh)
SESSION_DISCONNECT_GRACE_PERIOD = 60  # seconds


class SessionInfo:
    """Metadata about a session"""
    def __init__(self, session_id: str, client_ip: str):
        self.session_id = session_id
        self.client_ip = client_ip
        self.created_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "client_ip": self.client_ip,
            "created_at": self.created_at.isoformat(),
        }


class SessionManager:
    """Manages multiple terminal sessions"""

    def __init__(self, max_sessions: int = Config.TERMINAL_MAX_SESSIONS):
        self.max_sessions = max_sessions
        self.sessions: dict[str, TerminalSession] = {}
        self.session_info: dict[str, SessionInfo] = {}  # Session metadata (IP, timestamp)
        self.session_count = 0
        self.ai_proxies: dict[str, AIProxy] = {}  # AI proxy per session
        self.monitor_callback = None  # Callback for LLM monitoring
        self.disconnected_sessions: dict[str, datetime] = {}  # Track disconnected sessions
        self.cleanup_tasks: dict[str, asyncio.Task] = {}  # Pending cleanup tasks
        self.active_connections: dict[str, int] = {}  # Track active WebSocket connections per session
        self.latest_connection_time: dict[str, datetime] = {}  # Track latest connection time per session

    async def get_session(self, session_id: str, client_ip: Optional[str] = None) -> TerminalSession:
        """Get or create a session for the given ID"""
        if session_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                logger.warning("Max sessions reached, closing oldest session")
                oldest_id = next(iter(self.sessions))
                await self.close_session(oldest_id)

            logger.info(f"Creating NEW terminal session {session_id} from IP {client_ip}")
            session = TerminalSession(session_id)
            if not await session.start():
                raise RuntimeError(f"Failed to start session {session_id}")
            
            self.sessions[session_id] = session
            self.session_info[session_id] = SessionInfo(session_id, client_ip or "unknown")
            self.session_count += 1
            logger.info(f"Created new session {session_id} from IP {client_ip}, total sessions: {len(self.sessions)}")
        else:
            logger.info(f"Reusing EXISTING terminal session {session_id}")

        return self.sessions[session_id]

    async def send_input(self, session_id: str, text: str, newline: bool = True, from_ai: bool = False) -> None:
        """Send input to a session"""
        session = await self.get_session(session_id)
        logger.debug(f"SessionManager.send_input called with: text={repr(text[:100])}, newline={newline}, from_ai={from_ai}")
        await session.send_input(text, newline)
        logger.debug(f"✓ Sent input to session {session_id} (from_ai={from_ai})")

    async def resize_session(self, session_id: str, rows: int, cols: int) -> None:
        """Resize a terminal session"""
        if session_id in self.sessions:
            await self.sessions[session_id].resize(rows, cols)
            logger.debug(f"Resized session {session_id} to {rows}x{cols}")

    def register_connection(self, session_id: str) -> int:
        """Register a new WebSocket connection for a session"""
        if session_id not in self.active_connections:
            self.active_connections[session_id] = 0
        self.active_connections[session_id] += 1
        connection_count = self.active_connections[session_id]
        logger.info(f"Registered connection for {session_id}, total connections: {connection_count}")
        
        # CRITICAL: Warn about multiple connections - this causes duplication
        if connection_count > 1:
            logger.error(f"🚨 MULTIPLE CONNECTIONS ({connection_count}) for session {session_id} - WILL CAUSE DUPLICATION!")
            logger.error(f"🚨 This is the root cause of terminal output duplication!")
        
        return connection_count

    def should_close_old_connections(self, session_id: str) -> bool:
        """Check if old connections should be closed for this session"""
        connection_count = self.active_connections.get(session_id, 0)
        return connection_count > 1

    def mark_latest_connection(self, session_id: str) -> datetime:
        """Mark the latest connection time for a session"""
        connection_time = datetime.now()
        self.latest_connection_time[session_id] = connection_time
        logger.info(f"Marked latest connection time for {session_id}: {connection_time}")
        return connection_time

    def is_connection_outdated(self, session_id: str, connection_time: datetime) -> bool:
        """Check if a connection is outdated (newer connection exists)"""
        latest_time = self.latest_connection_time.get(session_id)
        if latest_time and connection_time < latest_time:
            logger.info(f"Connection for {session_id} is outdated: {connection_time} < {latest_time}")
            return True
        return False

    def unregister_connection(self, session_id: str):
        """Unregister a WebSocket connection for a session"""
        if session_id in self.active_connections:
            self.active_connections[session_id] -= 1
            connection_count = self.active_connections[session_id]
            logger.info(f"Unregistered connection for {session_id}, remaining connections: {connection_count}")
            if self.active_connections[session_id] <= 0:
                del self.active_connections[session_id]
                # Also clean up connection time tracking when no connections remain
                if session_id in self.latest_connection_time:
                    del self.latest_connection_time[session_id]
                logger.info(f"No more connections for {session_id}, cleaned up tracking")

    async def get_output_stream(self, session_id: str, client_ip: Optional[str] = None):
        """Get output stream from a session"""
        # Check for multiple connections
        connection_count = self.active_connections.get(session_id, 0)
        if connection_count > 1:
            logger.warning(f"Multiple connections ({connection_count}) detected for session {session_id} - this may cause duplication!")
        
        session = await self.get_session(session_id, client_ip)
        logger.debug(f"SessionManager: Starting output stream for {session_id}")
        async for chunk in session.get_output_stream():
            yield chunk
        logger.debug(f"SessionManager: Output stream ended for {session_id}")

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
        
        # Get list of fallback providers (all available except the primary one)
        available_providers = LLMProviderFactory.get_available_providers()
        fallback_names = [name for name, _ in available_providers if name != provider_name]
        
        # Use custom system prompt or config default
        prompt = system_prompt or Config.AI_PROXY_SYSTEM_PROMPT
        
        # Create AI proxy with fallback providers
        ai_proxy = AIProxy(
            llm_provider=llm_provider,
            system_prompt=prompt,
            max_iterations=Config.AI_PROXY_MAX_ITERATIONS,
            fallback_providers=fallback_names
        )
        
        # Set callback to send input to terminal
        async def send_input(text: str):
            logger.info(f"💬 AI Proxy callback invoked to send text to terminal: {repr(text[:100])}")
            # Send character by character like user input, then carriage return
            for char in text:
                logger.debug(f"Sending character: {repr(char)}")
                await self.send_input(session_id, char, newline=False, from_ai=True)
            # Send carriage return to submit
            logger.info(f"📤 Sending carriage return to submit")
            await self.send_input(session_id, "\r", newline=False, from_ai=True)
            logger.info(f"✓ Text '{text}' + CR sent to session {session_id}")
        
        ai_proxy.set_input_callback(send_input)
        
        # Set up monitoring callback if available
        if hasattr(self, 'monitor_callback') and self.monitor_callback:
            ai_proxy.set_monitor_callback(self.monitor_callback)
        
        ai_proxy.enable()
        
        self.ai_proxies[session_id] = ai_proxy
        logger.info(f"Enabled AI proxy for session {session_id} with provider {provider_name}, fallbacks: {fallback_names if fallback_names else 'none'}")
        return True
    
    async def disable_ai_proxy(self, session_id: str):
        """Disable AI proxy for a session"""
        if session_id not in self.ai_proxies:
            logger.debug(f"AI proxy for session {session_id} already disabled or doesn't exist")
            return
            
        try:
            self.ai_proxies[session_id].disable()
        except Exception as e:
            logger.error(f"Error disabling AI proxy for session {session_id}: {e}")
        finally:
            # Always remove from ai_proxies dict
            try:
                if session_id in self.ai_proxies:
                    del self.ai_proxies[session_id]
                    logger.info(f"Disabled AI proxy for session {session_id}")
            except Exception as e:
                logger.error(f"Error removing AI proxy {session_id} from dict: {e}")
    
    def get_ai_proxy(self, session_id: str) -> Optional[AIProxy]:
        """Get AI proxy for a session"""
        return self.ai_proxies.get(session_id)

    async def mark_session_disconnected(self, session_id: str) -> None:
        """Mark a session as disconnected but keep it alive for reconnection"""
        if session_id not in self.sessions:
            logger.debug(f"Session {session_id} not found, nothing to mark as disconnected")
            return
        
        # Cancel any existing cleanup task for this session
        if session_id in self.cleanup_tasks:
            self.cleanup_tasks[session_id].cancel()
            try:
                await self.cleanup_tasks[session_id]
            except asyncio.CancelledError:
                pass
            del self.cleanup_tasks[session_id]
        
        # Mark as disconnected
        self.disconnected_sessions[session_id] = datetime.now()
        logger.info(f"Session {session_id} marked as disconnected, will be kept alive for {SESSION_DISCONNECT_GRACE_PERIOD}s")
        
        # Schedule cleanup after grace period
        async def delayed_cleanup():
            try:
                await asyncio.sleep(SESSION_DISCONNECT_GRACE_PERIOD)
                # Check if session is still disconnected (not reconnected)
                if session_id in self.disconnected_sessions:
                    logger.info(f"Grace period expired for session {session_id}, closing session")
                    await self.close_session(session_id)
                    if session_id in self.disconnected_sessions:
                        del self.disconnected_sessions[session_id]
            except asyncio.CancelledError:
                logger.debug(f"Cleanup task cancelled for session {session_id} (likely reconnected)")
            except Exception as e:
                logger.error(f"Error in delayed cleanup for session {session_id}: {e}")
        
        self.cleanup_tasks[session_id] = asyncio.create_task(delayed_cleanup())

    async def mark_session_reconnected(self, session_id: str) -> bool:
        """Mark a session as reconnected, cancelling any pending cleanup"""
        if session_id in self.disconnected_sessions:
            # Cancel pending cleanup
            if session_id in self.cleanup_tasks:
                self.cleanup_tasks[session_id].cancel()
                try:
                    await self.cleanup_tasks[session_id]
                except asyncio.CancelledError:
                    pass
                del self.cleanup_tasks[session_id]
            
            del self.disconnected_sessions[session_id]
            logger.info(f"Session {session_id} reconnected successfully")
            return True
        return False

    def is_session_available(self, session_id: str) -> bool:
        """Check if a session exists and is available for reconnection"""
        return session_id in self.sessions

    async def close_session(self, session_id: str) -> None:
        """Close a specific session"""
        # Check if session exists before attempting cleanup
        session_exists = session_id in self.sessions
        ai_proxy_exists = session_id in self.ai_proxies
        
        if not session_exists and not ai_proxy_exists:
            logger.debug(f"Session {session_id} already closed or doesn't exist")
            return
            
        logger.info(f"Closing session {session_id} (session_exists={session_exists}, ai_proxy_exists={ai_proxy_exists})")
        
        try:
            # Disable AI proxy if active
            if ai_proxy_exists:
                try:
                    await self.disable_ai_proxy(session_id)
                except Exception as e:
                    logger.error(f"Error disabling AI proxy for session {session_id}: {e}")
            
            # Stop the terminal session if it exists
            if session_exists:
                try:
                    session = self.sessions[session_id]
                    await session.stop()
                    logger.debug(f"Successfully stopped terminal session {session_id}")
                except Exception as e:
                    logger.error(f"Error stopping terminal session {session_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error during session cleanup {session_id}: {e}")
        finally:
            # Always remove from sessions dict if it exists, even if there were errors
            if session_exists:
                try:
                    del self.sessions[session_id]
                    # Also remove session info
                    if session_id in self.session_info:
                        del self.session_info[session_id]
                    logger.info(f"Closed session {session_id}, remaining sessions: {len(self.sessions)}")
                except KeyError:
                    # Session was already removed by another thread/process
                    logger.debug(f"Session {session_id} was already removed from sessions dict")
                except Exception as e:
                    logger.error(f"Unexpected error removing session {session_id} from sessions dict: {e}")
            else:
                logger.debug(f"Session {session_id} was not in sessions dict, cleanup completed")

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
            "sessions": [info.to_dict() for info in self.session_info.values()],
        }
    
    def set_monitor_callback(self, callback):
        """Set monitoring callback for all AI proxies"""
        self.monitor_callback = callback
        # Update existing AI proxies
        for ai_proxy in self.ai_proxies.values():
            ai_proxy.set_monitor_callback(callback)
