"""
Pexpect-based terminal wrapper for interactive terminal sessions
"""
import pexpect
import logging
import asyncio
import re
import secrets
import shutil
from typing import Optional, AsyncIterator
from src.config import Config

logger = logging.getLogger(__name__)
SEND_COMMAND_POLL_INTERVAL_SECONDS = 0.05


def _join_output_chunks(chunks: list[str]) -> str:
    return ''.join(chunks)


def _append_incremental_output(output: str, new_chunks: list[str]) -> str:
    if not new_chunks:
        return output
    return output + _join_output_chunks(new_chunks)

# Only remove bell character and a few problematic control codes
# Keep ANSI codes for colors/formatting (needed for interactive tools like claude)
CONTROL_CHARS_TO_REMOVE = re.compile(r'[\x07]')  # Only bell (0x07)


class TerminalSession:
    """Manages a single interactive terminal session with bidirectional streaming"""

    def __init__(self, session_id: str, shell: Optional[str] = None):
        self.session_id = session_id
        self.shell = shell or Config.TERMINAL_SHELL
        self.process: Optional[pexpect.spawn] = None
        self.is_active = False
        self._listeners: set[asyncio.Queue] = set()
        self._history: list[str] = []
        self._max_history = 50  # Keep last 50 chunks for context
        self.read_task: Optional[asyncio.Task] = None

    def _clean_output(self, text: str) -> str:
        """Clean terminal output - minimal cleaning to preserve interactive tools"""
        # Only remove bell character
        text = CONTROL_CHARS_TO_REMOVE.sub('', text)
        # Keep \r for interactive tools (they use it for in-place updates)
        # Just ensure we don't have \r\n followed by extra \n
        return text

    async def _read_loop(self):
        """Background task that continuously reads from terminal and queues output"""
        logger.info(f"Starting read loop for session {self.session_id}")
        try:
            while self.is_active and self.process:
                try:
                    # Read output in non-blocking mode with very short timeout for responsiveness
                    chunk = self.process.read_nonblocking(size=4096, timeout=0.01)  # Increased buffer, reduced timeout
                    if chunk:
                        # Clean the output
                        cleaned_chunk = self._clean_output(chunk)
                        if cleaned_chunk:  # Only queue if there's content after cleaning
                            # Only log in debug mode to reduce overhead
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(f"Read {len(cleaned_chunk)} bytes from session {self.session_id}")

                            # Update history
                            self._history.append(cleaned_chunk)
                            if len(self._history) > self._max_history:
                                self._history.pop(0)

                            # Broadcast to all listeners
                            for queue in list(self._listeners):
                                try:
                                    queue.put_nowait(cleaned_chunk)
                                except asyncio.QueueFull:
                                    pass  # Skip if client is too slow
                except pexpect.TIMEOUT:
                    # No data available, very small delay to avoid busy loop but maintain responsiveness
                    await asyncio.sleep(0.001)  # Reduced from 0.05 to 0.001 seconds
                except pexpect.EOF:
                    logger.warning(f"EOF reached in session {self.session_id}")
                    self.is_active = False
                    # Signal end to all listeners
                    for queue in list(self._listeners):
                        try:
                            queue.put_nowait(None)
                        except asyncio.QueueFull:
                            pass
                    break
                except Exception as e:
                    logger.error(f"Error reading from session {self.session_id}: {e}")
                    break
        finally:
            logger.info(f"Read loop ended for session {self.session_id}")
            # Signal end of stream
            for queue in list(self._listeners):
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    async def start(self) -> bool:
        """Start a terminal session with background output reading"""
        try:
            # Spawn a shell process
            self.process = pexpect.spawn(
                self.shell,
                encoding=Config.TERMINAL_ENCODING,
                timeout=None  # No timeout for continuous reading
            )

            # Set up terminal size for proper rendering
            self.process.setwinsize(24, 80)

            self.is_active = True

            # Start background read loop
            self.read_task = asyncio.create_task(self._read_loop())

            logger.info(f"Started terminal session {self.session_id} with shell: {self.shell}")
            return True
        except Exception as e:
            logger.error(f"Failed to start terminal session {self.session_id}: {e}")
            self.is_active = False
            return False

    async def get_output_stream(self) -> AsyncIterator[str]:
        """Async generator that yields output as it becomes available"""
        logger.debug(f"Starting output stream for session {self.session_id}")
        queue = asyncio.Queue(maxsize=1000)  # Larger buffer for listeners
        self._listeners.add(queue)

        # Replay history first
        for chunk in self._history:
            yield chunk

        try:
            while True:
                chunk = await queue.get()
                if chunk is None:  # End of stream
                    logger.debug(f"End of output stream for session {self.session_id}")
                    break
                yield chunk
        except Exception as e:
            logger.error(f"Error in output stream for session {self.session_id}: {e}")
            raise
        finally:
            self._listeners.discard(queue)

    def get_recent_output(self) -> str:
        """Return retained output history as a single string."""
        return ''.join(self._history)

    async def resize(self, rows: int, cols: int) -> None:
        """Resize the terminal window"""
        if not self.is_active or not self.process:
            return
        
        try:
            self.process.setwinsize(rows, cols)
            logger.debug(f"Resized terminal {self.session_id} to {rows}x{cols}")
        except Exception as e:
            logger.error(f"Error resizing terminal {self.session_id}: {e}")

    async def send_input(self, text: str, newline: bool = True) -> None:
        """
        Send input to the terminal immediately
        Supports special control characters like Ctrl+C
        """
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        # Check command filter (unless it's a special control character)
        if text not in ('\x03', '\x04', '\r', '\n') and Config.command_filter:
            if not Config.command_filter.is_allowed(text):
                raise RuntimeError(f"Command not allowed: {text[:50]}")

        try:
            # Handle special control sequences synchronously for speed
            if text == "\x03":  # Ctrl+C
                self.process.sendintr()
                logger.info(f"Sent Ctrl+C to session {self.session_id}")
            elif text == "\x04":  # Ctrl+D
                self.process.sendeof()
                logger.info(f"Sent Ctrl+D to session {self.session_id}")
            else:
                # Send input directly without executor for better responsiveness
                if newline:
                    self.process.sendline(text)
                    logger.info("Sent line to session %s (len=%s)", self.session_id, len(text))
                else:
                    self.process.send(text)
                    logger.debug(f"Sent input to session {self.session_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending input to session {self.session_id}: {e}")
            raise RuntimeError(f"Failed to send input: {str(e)}")

    async def send_command(self, command: str, timeout: float = 5.0) -> str:
        """Run a shell command and return the incremental output."""
        marker = f"__telecli_done_{secrets.token_hex(8)}__"
        history_start = len(self._history)
        await self.send_input(f"{command}; printf '\\n{marker}\\n'")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        history_index = history_start
        output = ""
        while loop.time() < deadline:
            if history_index < len(self._history):
                new_chunks = self._history[history_index:]
                history_index = len(self._history)
                output = _append_incremental_output(output, new_chunks)
            if marker in output:
                return output.split(marker, 1)[0]
            await asyncio.sleep(SEND_COMMAND_POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"Command did not complete within {timeout} seconds")

    async def stop(self) -> None:
        """Stop the terminal session and cleanup"""
        logger.info(f"Stopping terminal session {self.session_id}")
        self.is_active = False
        
        # Cancel read task
        if self.read_task and not self.read_task.done():
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
        
        # Terminate process
        try:
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
                
                try:
                    self.process.kill(9)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error stopping session {self.session_id}: {e}")
        finally:
            logger.info(f"Stopped terminal session {self.session_id}")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class TmuxSession(TerminalSession):
    """Interactive session backed by an existing tmux session."""

    def __init__(self, session_id: str, tmux_session_name: str):
        super().__init__(session_id=session_id, shell="tmux")
        self.tmux_session_name = tmux_session_name
        self.shell = f"tmux:{tmux_session_name}"

    async def start(self) -> bool:
        """Attach a tmux client process to an existing tmux session."""
        tmux_path = shutil.which("tmux")
        if not tmux_path:
            logger.error("tmux is not installed; cannot start tmux-backed session %s", self.session_id)
            self.is_active = False
            return False

        try:
            self.process = pexpect.spawn(
                tmux_path,
                ["attach-session", "-t", self.tmux_session_name],
                encoding=Config.TERMINAL_ENCODING,
                timeout=None,
            )
            self.process.setwinsize(24, 80)
            self.is_active = True
            self.read_task = asyncio.create_task(self._read_loop())
            logger.info(
                "Attached tmux-backed session %s to tmux target %s",
                self.session_id,
                self.tmux_session_name,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to attach tmux-backed session %s to %s: %s",
                self.session_id,
                self.tmux_session_name,
                e,
            )
            self.is_active = False
            return False
