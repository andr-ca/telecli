"""
Pexpect-based terminal wrapper for interactive terminal sessions
"""
import pexpect
import logging
import asyncio
import re
from typing import Optional, AsyncIterator
from src.config import Config

logger = logging.getLogger(__name__)

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
        self.output_subscribers: list[asyncio.Queue] = []  # Multiple subscribers for output
        self.read_task: Optional[asyncio.Task] = None

    def _clean_output(self, text: str) -> str:
        """Clean terminal output - minimal cleaning to preserve interactive tools"""
        # Only remove bell character
        text = CONTROL_CHARS_TO_REMOVE.sub('', text)
        # Keep \r for interactive tools (they use it for in-place updates)
        # Just ensure we don't have \r\n followed by extra \n
        return text

    async def _read_loop(self):
        """Background task that continuously reads from terminal and broadcasts output"""
        logger.info(f"Starting read loop for session {self.session_id}")
        try:
            while self.is_active and self.process:
                try:
                    # Read output in non-blocking mode with very short timeout for responsiveness
                    chunk = self.process.read_nonblocking(size=4096, timeout=0.01)  # Increased buffer, reduced timeout
                    if chunk:
                        # Clean the output
                        cleaned_chunk = self._clean_output(chunk)
                        if cleaned_chunk:  # Only broadcast if there's content after cleaning
                            logger.debug(f"Read {len(cleaned_chunk)} bytes from session {self.session_id}: {repr(cleaned_chunk[:50])}")
                            # Broadcast to all subscribers
                            await self._broadcast_output(cleaned_chunk)
                except pexpect.TIMEOUT:
                    # No data available, very small delay to avoid busy loop but maintain responsiveness
                    await asyncio.sleep(0.001)  # Reduced from 0.05 to 0.001 seconds
                except pexpect.EOF:
                    logger.warning(f"EOF reached in session {self.session_id}")
                    self.is_active = False
                    await self._broadcast_output(None)  # Signal end of stream
                    break
                except Exception as e:
                    logger.error(f"Error reading from session {self.session_id}: {e}")
                    break
        finally:
            logger.info(f"Read loop ended for session {self.session_id}")
            await self._broadcast_output(None)  # Signal end of stream

    async def _broadcast_output(self, chunk: Optional[str]):
        """Broadcast output to all subscribers"""
        if not self.output_subscribers:
            return
        
        # Remove closed/full queues and broadcast to active ones
        active_subscribers = []
        for queue in self.output_subscribers:
            try:
                if chunk is not None:
                    queue.put_nowait(chunk)
                else:
                    queue.put_nowait(None)  # End of stream signal
                active_subscribers.append(queue)
            except asyncio.QueueFull:
                logger.warning(f"Subscriber queue full for session {self.session_id}, dropping")
            except Exception as e:
                logger.debug(f"Error broadcasting to subscriber: {e}")
        
        self.output_subscribers = active_subscribers

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
        # Create a new queue for this subscriber
        subscriber_queue = asyncio.Queue(maxsize=100)  # Limit queue size to prevent memory issues
        self.output_subscribers.append(subscriber_queue)
        
        subscriber_id = len(self.output_subscribers)
        logger.info(f"Starting output stream for session {self.session_id} (subscriber {subscriber_id})")
        
        try:
            while self.is_active:
                try:
                    # Use timeout to allow checking is_active periodically
                    chunk = await asyncio.wait_for(subscriber_queue.get(), timeout=0.5)
                    if chunk is None:  # End of stream
                        logger.debug(f"End of output stream for session {self.session_id} (subscriber {subscriber_id})")
                        break
                    yield chunk
                except asyncio.TimeoutError:
                    # No data available, continue loop to check conditions
                    continue
        except Exception as e:
            logger.error(f"Error in output stream for session {self.session_id} (subscriber {subscriber_id}): {e}")
            raise
        finally:
            # Remove this subscriber from the list
            try:
                self.output_subscribers.remove(subscriber_queue)
                logger.info(f"Output stream ended for session {self.session_id} (subscriber {subscriber_id})")
            except ValueError:
                # Already removed
                pass

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
                    logger.info(f"Sent line to session {self.session_id}: {repr(text[:50])}")
                else:
                    self.process.send(text)
                    logger.debug(f"Sent input to session {self.session_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending input to session {self.session_id}: {e}")
            raise RuntimeError(f"Failed to send input: {str(e)}")

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
