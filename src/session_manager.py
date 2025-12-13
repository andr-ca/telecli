"""
Session manager for coordinating multiple terminal sessions
"""
import logging
from src.config import Config
from src.terminal import TerminalSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages multiple terminal sessions"""

    def __init__(self, max_sessions: int = Config.TERMINAL_MAX_SESSIONS):
        self.max_sessions = max_sessions
        self.sessions: dict[str, TerminalSession] = {}
        self.session_count = 0

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

    async def send_command(self, session_id: str, command: str) -> str:
        """Send a command to a session"""
        session = await self.get_session(session_id)
        
        # Check if session is responsive
        if not await session.is_responsive():
            logger.warning(f"Session {session_id} is not responsive, closing it")
            await self.close_session(session_id)
            # Create a new session
            session = await self.get_session(session_id)

        try:
            output = await session.send_command(command)
            logger.info(f"Command executed in session {session_id}: {command[:50]}...")
            return output
        except Exception as e:
            logger.error(f"Error executing command in session {session_id}: {e}")
            raise

    async def read_output(self, session_id: str, timeout: int = 5) -> str:
        """Read output from a session"""
        session = await self.get_session(session_id)
        return await session.read_output(timeout)

    async def send_input(self, session_id: str, text: str, newline: bool = True) -> None:
        """Send raw input to a session"""
        session = await self.get_session(session_id)
        await session.send_input(text, newline)

    async def close_session(self, session_id: str) -> None:
        """Close a specific session"""
        if session_id in self.sessions:
            try:
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
