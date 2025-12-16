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
        self.output_queue: asyncio.Queue = asyncio.Queue()  # Unlimited queue to prevent blocking
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
        chunks_read = 0
        try:
            while self.is_active and self.process:
                try:
                    # Read output in non-blocking mode with very short timeout for responsiveness
                    chunk = self.process.read_nonblocking(size=4096, timeout=0.01)  # Increased buffer, reduced timeout
                    if chunk:
                        chunks_read += 1
                        # Clean the output
                        cleaned_chunk = self._clean_output(chunk)
                        if cleaned_chunk:  # Only queue if there's content after cleaning
                            logger.debug(f"Read chunk #{chunks_read} ({len(cleaned_chunk)} bytes) from session {self.session_id}: {repr(cleaned_chunk[:50])}")
                            await self.output_queue.put(cleaned_chunk)
                        else:
                            logger.debug(f"Chunk #{chunks_read} was empty after cleaning for session {self.session_id}")
                except pexpect.TIMEOUT:
                    # No data available, very small delay to avoid busy loop but maintain responsiveness
                    await asyncio.sleep(0.001)  # Reduced from 0.05 to 0.001 seconds
                except pexpect.EOF:
                    logger.warning(f"EOF reached in session {self.session_id} after {chunks_read} chunks")
                    self.is_active = False
                    await self.output_queue.put(None)  # Signal end of stream
                    break
                except Exception as e:
                    logger.error(f"Error reading from session {self.session_id} after {chunks_read} chunks: {e}")
                    break
        finally:
            logger.info(f"Read loop ended for session {self.session_id} after reading {chunks_read} chunks")
            await self.output_queue.put(None)  # Signal end of stream



    async def start(self) -> bool:
        """Start a terminal session with background output reading"""
        try:
            logger.info(f"Starting terminal session {self.session_id} with shell: {self.shell}")
            
            # Spawn a shell process
            self.process = pexpect.spawn(
                self.shell, 
                encoding=Config.TERMINAL_ENCODING,
                timeout=None  # No timeout for continuous reading
            )
            
            logger.info(f"Process spawned for session {self.session_id}")
            
            # Set up terminal size for proper rendering
            self.process.setwinsize(24, 80)
            logger.info(f"Terminal size set for session {self.session_id}")
            
            self.is_active = True
            
            # Start background read loop
            self.read_task = asyncio.create_task(self._read_loop())
            logger.info(f"Read task started for session {self.session_id}")
            
            # Give the shell a moment to initialize and send initial output
            await asyncio.sleep(0.1)
            
            # Send a simple command to trigger initial prompt display
            try:
                # Send empty command to get prompt
                self.process.send('\r')
                logger.debug(f"Sent initial carriage return to trigger prompt for {self.session_id}")
            except Exception as e:
                logger.warning(f"Failed to send initial prompt trigger for {self.session_id}: {e}")
            
            logger.info(f"Started terminal session {self.session_id} with shell: {self.shell}")
            return True
        except Exception as e:
            logger.error(f"Failed to start terminal session {self.session_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.is_active = False
            return False

    async def get_output_stream(self) -> AsyncIterator[str]:
        """Async generator that yields output as it becomes available"""
        logger.info(f"Starting output stream for session {self.session_id}")
        
        try:
            while self.is_active:
                try:
                    # Use timeout to allow checking is_active periodically
                    chunk = await asyncio.wait_for(self.output_queue.get(), timeout=0.5)
                    if chunk is None:  # End of stream
                        logger.debug(f"End of output stream for session {self.session_id}")
                        break
                    yield chunk
                except asyncio.TimeoutError:
                    # No data available, continue loop to check conditions
                    continue
        except Exception as e:
            logger.error(f"Error in output stream for session {self.session_id}: {e}")
            raise
        finally:
            logger.info(f"Output stream ended for session {self.session_id}")

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

    async def refresh_prompt(self) -> None:
        """Refresh the terminal prompt to ensure cursor is visible"""
        if not self.is_active or not self.process:
            logger.warning(f"Cannot refresh prompt - session {self.session_id} is not active")
            return
        
        try:
            # Send a sequence that will refresh the prompt without executing anything
            # This is more effective than just \r for showing the cursor
            self.process.send('\x15')  # Ctrl+U (clear line)
            await asyncio.sleep(0.05)  # Brief delay
            self.process.send('\r')    # Enter to show fresh prompt
            logger.info(f"Refreshed prompt for session {self.session_id}")
        except Exception as e:
            logger.warning(f"Failed to refresh prompt for session {self.session_id}: {e}")

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
