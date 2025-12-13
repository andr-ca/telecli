"""
Pexpect-based terminal wrapper for interactive terminal sessions
"""
import pexpect
import logging
from typing import Optional, Tuple
from src.config import Config

logger = logging.getLogger(__name__)


class TerminalSession:
    """Manages a single interactive terminal session with pexpect"""

    def __init__(self, session_id: str, shell: Optional[str] = None):
        self.session_id = session_id
        self.shell = shell or Config.TERMINAL_SHELL
        self.process: Optional[pexpect.spawn] = None
        self.is_active = False

    async def start(self) -> bool:
        """Start a terminal session"""
        try:
            # Spawn a shell process
            self.process = pexpect.spawn(self.shell, encoding=Config.TERMINAL_ENCODING, timeout=Config.TERMINAL_TIMEOUT)
            
            # Set up terminal size for proper rendering
            self.process.setwinsize(24, 80)
            
            self.is_active = True
            logger.info(f"Started terminal session {self.session_id} with shell: {self.shell}")
            return True
        except Exception as e:
            logger.error(f"Failed to start terminal session {self.session_id}: {e}")
            self.is_active = False
            return False

    async def send_command(self, command: str) -> str:
        """
        Send a command and return output
        """
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        try:
            # Send the command
            self.process.sendline(command)
            
            # Wait for command to complete
            # Try to match command echo or prompt
            try:
                self.process.expect([pexpect.TIMEOUT, pexpect.EOF], timeout=Config.TERMINAL_TIMEOUT)
            except pexpect.TIMEOUT:
                logger.warning(f"Command timed out in session {self.session_id}")
                pass  # Timeout is ok, we'll return what we have
            except pexpect.EOF:
                logger.warning(f"Process ended unexpectedly in session {self.session_id}")

            # Get all output
            output = self.process.before if self.process.before else ""
            
            logger.debug(f"Command output in session {self.session_id}: {output[:100]}...")
            return output
        except Exception as e:
            logger.error(f"Error sending command in session {self.session_id}: {e}")
            raise RuntimeError(f"Failed to execute command: {str(e)}")

    async def read_output(self, timeout: Optional[int] = None) -> str:
        """
        Read available output from terminal without sending command
        """
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        try:
            timeout = timeout or Config.TERMINAL_TIMEOUT
            output = ""
            
            try:
                self.process.expect([pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass  # Expected behavior
            
            if self.process.before:
                output = self.process.before
            
            return output
        except Exception as e:
            logger.error(f"Error reading output in session {self.session_id}: {e}")
            raise RuntimeError(f"Failed to read output: {str(e)}")

    async def send_input(self, text: str, newline: bool = True) -> None:
        """
        Send raw input without waiting for response
        """
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        try:
            if newline:
                self.process.sendline(text)
            else:
                self.process.send(text)
            logger.debug(f"Sent input in session {self.session_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending input in session {self.session_id}: {e}")
            raise RuntimeError(f"Failed to send input: {str(e)}")

    async def is_responsive(self) -> bool:
        """Check if terminal is still responsive"""
        if not self.is_active or not self.process:
            return False

        try:
            # Try to get a simple response
            self.process.sendline("echo 'ALIVE'")
            self.process.expect("ALIVE", timeout=2)
            return True
        except Exception:
            return False

    async def stop(self) -> None:
        """Stop the terminal session"""
        try:
            if self.process:
                try:
                    self.process.terminate()
                except Exception:
                    pass
                
                try:
                    self.process.kill(signal=9)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error stopping session {self.session_id}: {e}")
        finally:
            self.is_active = False
            logger.info(f"Stopped terminal session {self.session_id}")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
