"""
AI Proxy Manager - Automates terminal interactions using LLMs
"""
import asyncio
import logging
import re
from typing import Optional, Callable
from collections import deque
from src.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class AIProxy:
    """
    Manages AI-automated responses to terminal prompts
    Detects when a command is waiting for input and responds automatically
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10
    ):
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt or "You are helping automate terminal interactions. Provide brief, direct responses."
        self.max_iterations = max_iterations
        self.enabled = False
        self.iteration_count = 0
        self.output_buffer = deque(maxlen=50)  # Keep last 50 lines
        self.last_output_time = 0
        self.send_input_callback: Optional[Callable] = None
        
    def enable(self):
        """Enable AI proxy"""
        self.enabled = True
        self.iteration_count = 0
        logger.info(f"AI Proxy enabled with provider: {self.llm_provider.get_name()}")
    
    def disable(self):
        """Disable AI proxy"""
        self.enabled = False
        logger.info("AI Proxy disabled")
    
    def is_enabled(self) -> bool:
        return self.enabled
    
    def set_input_callback(self, callback: Callable):
        """Set callback function to send input to terminal"""
        self.send_input_callback = callback
    
    def add_output(self, text: str):
        """Add terminal output to buffer"""
        if not self.enabled:
            return
        
        # Split into lines and add to buffer
        lines = text.split('\n')
        for line in lines:
            if line.strip():
                self.output_buffer.append(line)
        
        self.last_output_time = asyncio.get_event_loop().time()
    
    def _detect_prompt(self) -> bool:
        """
        Detect if terminal is waiting for user input
        
        Returns:
            True if prompt detected
        """
        if len(self.output_buffer) == 0:
            return False
        
        last_line = self.output_buffer[-1].strip()
        
        # Remove ANSI escape codes for analysis
        clean_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', last_line)
        
        # Prompt patterns
        patterns = [
            r'>$',  # Ends with >
            r'\?$',  # Ends with ?
            r':\s*$',  # Ends with : (like "Enter name:")
            r'\$ $',  # Shell prompt
        ]
        
        for pattern in patterns:
            if re.search(pattern, clean_line):
                logger.debug(f"Prompt detected: {clean_line}")
                return True
        
        # Check for inactivity (no output for 2 seconds)
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_output_time > 2.0:
            logger.debug("Inactivity detected, assuming prompt")
            return True
        
        return False
    
    def _build_context(self) -> str:
        """Build context from recent output"""
        # Get last 10 lines of output
        recent_lines = list(self.output_buffer)[-10:]
        context = '\n'.join(recent_lines)
        return context
    
    async def process_output(self):
        """
        Process output and respond if prompt detected
        Should be called periodically
        """
        if not self.enabled:
            return
        
        if self.iteration_count >= self.max_iterations:
            logger.warning(f"AI Proxy max iterations ({self.max_iterations}) reached, disabling")
            self.disable()
            return
        
        if not self._detect_prompt():
            return
        
        # Build prompt for LLM
        context = self._build_context()
        prompt = f"Terminal output:\n{context}\n\nThe terminal is waiting for input. What should I respond? Provide only the response text, nothing else."
        
        logger.info(f"Detected prompt, querying {self.llm_provider.get_name()}...")
        
        try:
            response = await self.llm_provider.generate(prompt, self.system_prompt)
            
            if response:
                self.iteration_count += 1
                logger.info(f"AI response ({self.iteration_count}/{self.max_iterations}): {response[:100]}")
                
                # Send response to terminal
                if self.send_input_callback:
                    await self.send_input_callback(response)
                else:
                    logger.error("No input callback set")
            else:
                logger.error("Failed to get LLM response")
                
        except Exception as e:
            logger.error(f"AI Proxy error: {e}")
    
    def get_status(self) -> dict:
        """Get current proxy status"""
        return {
            "enabled": self.enabled,
            "provider": self.llm_provider.get_name() if self.llm_provider else None,
            "iterations": self.iteration_count,
            "max_iterations": self.max_iterations,
            "buffer_size": len(self.output_buffer)
        }
