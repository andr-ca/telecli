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
        self.output_buffer = deque(maxlen=100)  # Keep last 100 lines (increased for menus)
        self.last_output_time = 0
        self.last_response_time = 0  # Track when we last sent a response
        self.response_cooldown = 3.0  # Don't respond again within 3 seconds
        self.stuck_check_timeout = 60.0  # If no output for 60s after response, try again
        self.last_buffer_hash = ""  # Track if buffer content changed
        self.send_input_callback: Optional[Callable] = None
        
        # Memory: track conversation history
        self.conversation_memory = []  # List of {role, content} dicts
        self.max_memory_items = 20  # Keep last 20 exchanges
        self.memory_summary = ""  # Compressed summary of older interactions
        self.summarize_threshold = 12  # Summarize when memory exceeds this
        
    def enable(self):
        """Enable AI proxy"""
        self.enabled = True
        self.iteration_count = 0
        self.conversation_memory = []  # Reset memory on enable
        self.memory_summary = ""  # Reset summary
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
        
        # Log raw chunk preview
        preview = repr(text[:200]) if len(text) < 200 else repr(text[:200]) + f"... ({len(text)} total bytes)"
        logger.debug(f"AI Proxy received chunk: {preview}")
        
        # Split by both \n and \r to handle different line endings
        lines = re.split(r'[\r\n]+', text)
        added_lines = 0
        
        for line in lines:
            # Quick check - skip if completely empty or just whitespace
            if not line or not line.strip():
                continue
            
            # Skip lines that are purely ANSI codes
            stripped = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
            stripped = re.sub(r'\x1b[^\[]*', '', stripped)
            if not stripped.strip():
                continue
            
            self.output_buffer.append(line)
            added_lines += 1
        
        if added_lines > 0:
            logger.debug(f"Added {added_lines} lines to buffer (total: {len(self.output_buffer)})")
        
        self.last_output_time = asyncio.get_event_loop().time()
    
    def _detect_prompt(self) -> bool:
        """
        Detect if terminal is waiting for user input
        
        Returns:
            True if prompt detected
        """
        if len(self.output_buffer) == 0:
            return False
        
        last_line = self.output_buffer[-1]
        
        # Log raw line for debugging
        logger.debug(f"Raw last_line: {repr(last_line[:150])}")
        
        # Remove ANSI escape codes for analysis
        clean_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', last_line)
        clean_line = clean_line.strip()
        
        # Skip empty lines
        if not clean_line:
            # Check inactivity even if line is empty
            current_time = asyncio.get_event_loop().time()
            time_since_output = current_time - self.last_output_time
            if time_since_output > 1.5:
                # Get the last non-empty line
                for line in reversed(list(self.output_buffer)):
                    test_clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line).strip()
                    if test_clean:
                        logger.info(f"✓ Prompt detected by inactivity on last content: {test_clean[:100]}")
                        return True
            return False
        
        logger.debug(f"Checking for prompt in: {clean_line[:100]}")
        
        # Ignore false positives - decorative elements, spinners, etc.
        false_positives = [
            r'^[─┌┐└┘├┤┬┴┼│]+$',  # Box drawing characters
            r'^[∴✶⎿]+.*$',  # Spinner/loading symbols
            r'^>\s*$',  # Just a > with nothing else
            r'^Use skill',  # Skill loading messages
            r'^Loading',  # Loading messages
        ]
        
        for fp_pattern in false_positives:
            if re.match(fp_pattern, clean_line):
                logger.debug(f"Ignoring false positive: {clean_line[:50]}")
                return False
        
        # Real prompt patterns - more specific
        patterns = [
            r'\?\s*$',  # Ends with ?
            r':\s*$',  # Ends with : (like "Enter name:" or "Do you want to proceed:")
            r'^\s*❯\s*\d+\.',  # Numbered menu with cursor (❯ 1.)
            r'^\s*\d+\.\s+\w+',  # Numbered options (1. Yes, 2. No)
            r'\(y/n\)',  # Yes/no prompt
            r'\[y/N\]',  # Bracketed yes/no
        ]
        
        # Check if any of the patterns match
        for pattern in patterns:
            if re.search(pattern, clean_line):
                logger.info(f"✓ Prompt detected by pattern in last line: {clean_line[:100]}")
                return True
        
        # Also check last few lines for multi-line prompts (like numbered menus)
        if len(self.output_buffer) >= 3:
            last_3_lines = '\n'.join([re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line).strip() 
                                     for line in list(self.output_buffer)[-3:]])
            
            # Check for numbered menu patterns across multiple lines
            if re.search(r'❯\s*\d+\.', last_3_lines) or re.search(r'\d+\.\s+(Yes|No|\w+).*\n.*\d+\.', last_3_lines, re.IGNORECASE):
                logger.info(f"✓ Prompt detected: numbered menu in recent lines")
                return True
        
        # Check for inactivity (no output for 1.5 seconds) - reduced from 2s
        current_time = asyncio.get_event_loop().time()
        time_since_output = current_time - self.last_output_time
        if time_since_output > 1.5:
            # Log buffer contents for debugging
            buffer_preview = '\n'.join([repr(line[:80]) for line in list(self.output_buffer)[-5:]])
            logger.info(f"✓ Prompt detected by inactivity ({time_since_output:.1f}s)")
            logger.debug(f"Last 5 lines in buffer:\n{buffer_preview}")
            return True
        
        return False
    
    def _build_context(self) -> str:
        """Build context from recent output with aggressive cleaning"""
        # Get last 30 lines of output (increased for better menu capture)
        recent_lines = list(self.output_buffer)[-30:]
        
        # Aggressively clean each line
        cleaned_lines = []
        for line in recent_lines:
            # Remove all ANSI escape sequences (colors, formatting)
            clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
            # Remove other escape sequences
            clean = re.sub(r'\x1b[^\[]*', '', clean)
            # Remove control characters like \x1b
            clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)
            clean = clean.strip()
            
            # Skip if empty or just decorative
            if not clean:
                continue
            
            # Skip pure decoration lines (box drawing, spinner symbols, separators)
            if re.match(r'^[─┌┐└┘├┤┬┴┼│\-_=]{3,}$', clean):  # Lines of just box chars
                continue
            if re.match(r'^[∴✶✽⎿\*\.]+.*(?:esc to interrupt|ctrl\+[a-z])', clean, re.IGNORECASE):  # Spinner/loading with instructions
                continue
            if re.match(r'^[\*∴✶✽]\s+(Thought|Imagining|Thinking|Loading|Finagling|Processing)', clean, re.IGNORECASE):  # Common loading messages
                continue
            if clean in ['? for shortcuts', '>']:  # Specific noise patterns
                continue
            
            cleaned_lines.append(clean)
        
        context = '\n'.join(cleaned_lines)
        
        # Log cleaned context for debugging
        logger.debug(f"Built context with {len(cleaned_lines)} cleaned lines (from {len(recent_lines)} raw)")
        logger.debug(f"Clean context preview: {context[:300]}...")
        
        return context
    
    async def _summarize_memory(self):
        """Summarize and compress older memory items"""
        if len(self.conversation_memory) <= self.summarize_threshold:
            return
        
        try:
            logger.info(f"📝 Summarizing conversation memory ({len(self.conversation_memory)} items)")
            
            # Take older items (keep last 6 items unsummarized)
            items_to_summarize = self.conversation_memory[:-6]
            
            # Build text representation
            conversation_text = ""
            for item in items_to_summarize:
                if item['role'] == 'prompt':
                    conversation_text += f"Terminal: {item['content']}\n"
                elif item['role'] == 'response':
                    conversation_text += f"AI: {item['content']}\n"
            
            # Ask LLM to summarize
            summarize_prompt = f"""Summarize this terminal interaction history in 2-3 sentences. Focus on the key context and what the user is trying to accomplish:

{conversation_text}

Provide a concise summary:"""
            
            summary = await self.llm_provider.generate(
                summarize_prompt,
                "You are a helpful assistant that summarizes terminal interactions concisely."
            )
            
            if summary:
                # Update summary (append if we already have one)
                if self.memory_summary:
                    self.memory_summary += f" {summary.strip()}"
                else:
                    self.memory_summary = summary.strip()
                
                # Keep only recent items
                self.conversation_memory = self.conversation_memory[-6:]
                
                logger.info(f"✓ Memory summarized: kept {len(self.conversation_memory)} recent items, summary: {len(self.memory_summary)} chars")
            else:
                logger.warning("Failed to generate memory summary")
                
        except Exception as e:
            logger.error(f"Error summarizing memory: {e}")
    
    def _build_memory_context(self) -> str:
        """Build conversation history for context"""
        memory_parts = []
        
        # Add summary of older interactions if available
        if self.memory_summary:
            memory_parts.append(f"\n\nSummary of earlier interactions:\n{self.memory_summary}")
        
        # Add recent interactions
        if self.conversation_memory:
            memory_parts.append("\n\nRecent interactions:")
            for item in self.conversation_memory[-10:]:  # Last 10 items
                if item['role'] == 'prompt':
                    memory_parts.append(f"Terminal asked: {item['content']}")
                elif item['role'] == 'response':
                    memory_parts.append(f"You responded: {item['content']}")
        
        return '\n'.join(memory_parts) if memory_parts else ""
    
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
        
        current_time = asyncio.get_event_loop().time()
        time_since_response = current_time - self.last_response_time
        
        # Check cooldown - don't respond too quickly after last response
        if time_since_response < self.response_cooldown:
            logger.debug(f"In cooldown period ({time_since_response:.1f}s < {self.response_cooldown}s)")
            return
        
        # Check if terminal is stuck (no changes after our response for 60s)
        if self.last_response_time > 0 and time_since_response > self.stuck_check_timeout:
            # Check if buffer content has changed since last response
            current_hash = hash(''.join(list(self.output_buffer)))
            if current_hash == self.last_buffer_hash:
                logger.info(f"⚠️ Terminal stuck for {time_since_response:.0f}s with no changes - re-querying LLM")
                # Force prompt detection to retry
                prompt_detected = True
            else:
                # Buffer changed, reset hash and continue normal detection
                self.last_buffer_hash = current_hash
                prompt_detected = self._detect_prompt()
        else:
            prompt_detected = self._detect_prompt()
        
        if not prompt_detected:
            return
        
        # Build prompt for LLM
        context = self._build_context()
        memory_context = self._build_memory_context()
        
        logger.info(f"🤖 Building LLM prompt with {len(context)} chars of context and {len(self.conversation_memory)} memory items")
        logger.debug(f"Context preview: {context[:200]}...")
        
        prompt = f"""Terminal output:
{context}

The terminal is waiting for input. What should I respond? Provide only the response text, nothing else.
{memory_context}"""
        
        logger.info(f"→ Querying {self.llm_provider.get_name()} (iteration {self.iteration_count + 1}/{self.max_iterations})")
        
        try:
            response = await self.llm_provider.generate(prompt, self.system_prompt)
            
            if response:
                response = response.strip()
                self.iteration_count += 1
                logger.info(f"← Got {len(response)} chars from LLM: {response[:100]}{'...' if len(response) > 100 else ''}")
                
                # Store in memory
                last_line = self.output_buffer[-1] if self.output_buffer else ""
                self.conversation_memory.append({
                    'role': 'prompt',
                    'content': last_line.strip()
                })
                self.conversation_memory.append({
                    'role': 'response',
                    'content': response
                })
                
                # Summarize and compress memory if it's getting large
                if len(self.conversation_memory) > self.summarize_threshold:
                    await self._summarize_memory()
                
                logger.debug(f"💭 Updated conversation memory: {len(self.conversation_memory)} items, has_summary={bool(self.memory_summary)}")
                
                # Send response to terminal
                if self.send_input_callback:
                    logger.info(f"✉ Sending response to terminal")
                    await self.send_input_callback(response)
                    # Set cooldown timestamp and save buffer state
                    self.last_response_time = asyncio.get_event_loop().time()
                    self.last_buffer_hash = hash(''.join(list(self.output_buffer)))
                    logger.debug(f"Response sent, cooldown active for {self.response_cooldown}s, will check for stuck at {self.stuck_check_timeout}s")
                else:
                    logger.error("❌ No input callback set!")
            else:
                logger.error("❌ LLM returned empty response")
                
        except Exception as e:
            logger.error(f"❌ AI Proxy error: {e}", exc_info=True)
    
    def get_status(self) -> dict:
        """Get current proxy status"""
        return {
            "enabled": self.enabled,
            "provider": self.llm_provider.get_name() if self.llm_provider else None,
            "iterations": self.iteration_count,
            "max_iterations": self.max_iterations,
            "buffer_size": len(self.output_buffer),
            "memory_items": len(self.conversation_memory),
            "has_summary": bool(self.memory_summary)
        }
