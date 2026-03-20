"""
AI Proxy Manager - Automates terminal interactions using LLMs
"""
import asyncio
import json
import logging
import re
from typing import Optional, Callable
from collections import deque
from src.llm_provider import LLMProvider, LLMProviderFactory, LLMResponse

logger = logging.getLogger(__name__)


class AIProxy:
    """
    Manages AI-automated responses to terminal prompts
    Detects when a command is waiting for input and responds automatically
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        system_prompt: Optional[str] = None,
        max_iterations: Optional[int] = None,
        buffer_size: Optional[int] = None,
        context_lines: Optional[int] = None,
        fallback_provider_names: Optional[list[str]] = None,
        primary_provider: Optional[str] = None,
        fallback_providers: Optional[list[str]] = None,
    ):
        from src.config import Config

        if llm_provider is None:
            if primary_provider is None:
                raise TypeError("AIProxy requires llm_provider or primary_provider")

            llm_provider = LLMProviderFactory.create(primary_provider)
            if not llm_provider:
                raise ValueError(f"Unknown or unavailable LLM provider: {primary_provider}")

        fallback_names = fallback_provider_names
        if fallback_names is None:
            fallback_names = fallback_providers or []

        self.llm_provider = llm_provider
        self.primary_provider_name = llm_provider.get_name()
        self.fallback_provider_names = list(fallback_names)  # List of fallback provider names to try on 429
        self.system_prompt = system_prompt or "You are helping automate terminal interactions. Provide brief, direct responses."
        self.max_iterations = max_iterations or Config.AI_PROXY_MAX_ITERATIONS
        self.enabled = False
        self.iteration_count = 0
        self.output_buffer = deque(maxlen=buffer_size or Config.AI_PROXY_BUFFER_SIZE)  # Keep output lines for full screen capture
        self.context_lines = context_lines or Config.AI_PROXY_CONTEXT_LINES  # Number of lines to send to LLM for context
        self.last_output_time = 0
        self.last_output_chunk_time = 0  # Track when last output chunk arrived (for streaming detection)
        self.last_user_input_time = 0  # Track when user last typed
        self.last_response_time = 0  # Track when we last sent a response
        self.response_cooldown = 3.0  # Don't respond again within 3 seconds
        self.user_idle_timeout = 3.0  # Consider user idle after 3s of no typing (increased)
        self.terminal_idle_timeout = 2.5  # Terminal idle after 2.5s of no output (increased)
        self.streaming_detection_window = 0.5  # If output within 0.5s, consider it streaming
        self.stuck_check_timeout = 60.0  # If no output for 60s after response, try again
        self.last_buffer_hash = ""  # Track if buffer content changed
        self.send_input_callback: Optional[Callable] = None
        self.user_input_buffer = []  # Track recent user inputs for context
        self.user_command = ""  # Track the user's command that triggered output
        
        # Memory: track conversation history
        self.conversation_memory = []  # List of {role, content} dicts
        self.max_memory_items = 20  # Keep last 20 exchanges
        self.memory_summary = ""  # Compressed summary of older interactions
        self.summarize_threshold = 12  # Summarize when memory exceeds this

    @property
    def primary_provider(self) -> str:
        """Backward-compatible alias for the active provider name."""
        return self.primary_provider_name

    @property
    def fallback_providers(self) -> list[str]:
        """Backward-compatible alias for fallback provider names."""
        return self.fallback_provider_names
        
    def enable(self):
        """Enable AI proxy"""
        self.enabled = True
        self.iteration_count = 0
        self.conversation_memory = []  # Reset memory on enable
        self.memory_summary = ""  # Reset summary
        self.user_input_buffer = []  # Reset user input tracking
        self.last_user_input_time = 0
        logger.info(f"AI Proxy enabled with provider: {self.llm_provider.get_name()}")
        if self.fallback_provider_names:
            logger.info(f"Fallback providers available: {', '.join(self.fallback_provider_names)}")
    
    async def _try_llm_with_fallback(self, prompt: str) -> Optional[str]:
        """
        Try to generate LLM response with fallback on rate limit (429)
        
        Args:
            prompt: The prompt to send to LLM
            
        Returns:
            Generated text or None if all providers fail
        """
        # Try primary provider first
        providers_to_try = [(self.primary_provider_name, self.llm_provider)]
        
        # Add fallback providers
        for fallback_name in self.fallback_provider_names:
            fallback_provider = LLMProviderFactory.create(fallback_name)
            if fallback_provider:
                providers_to_try.append((fallback_name, fallback_provider))
        
        for provider_name, provider in providers_to_try:
            logger.info(f"→ Trying LLM provider: {provider_name}")
            response = await provider.generate(prompt, self.system_prompt)
            
            if response.is_success:
                logger.info(f"← Got response from {provider_name}: {len(response.text)} chars")
                # Update the active provider if we switched
                if provider_name != self.primary_provider_name:
                    logger.warning(f"⚠️ Switched from {self.primary_provider_name} to {provider_name} due to error")
                    self.llm_provider = provider
                    self.primary_provider_name = provider_name
                return response.text
            
            # Check for rate limit error
            if response.error_code == 429:
                logger.warning(f"⚠️ Rate limit (429) from {provider_name}, trying next provider...")
                continue
            
            # For other errors, log and try next
            if response.error_code:
                logger.warning(f"⚠️ Error {response.error_code} from {provider_name}: {response.error_message}")
                continue
        
        logger.error("❌ All LLM providers failed")
        return None
    
    def disable(self):
        """Disable AI proxy"""
        self.enabled = False
        logger.info("AI Proxy disabled")
    
    def is_enabled(self) -> bool:
        return self.enabled
    
    def set_input_callback(self, callback: Callable):
        """Set callback function to send input to terminal"""
        self.send_input_callback = callback
    
    def set_monitor_callback(self, callback: Callable):
        """Set callback function for monitoring LLM interactions"""
        self.monitor_callback = callback
    
    def notify_user_input(self, text: str):
        """Notify proxy that user typed something (pause AI intervention)"""
        if not self.enabled:
            return
        
        self.last_user_input_time = asyncio.get_event_loop().time()
        self.user_input_buffer.append(text)
        
        # Track user command (accumulate until Enter)
        self.user_command += text
        if text in ('\r', '\n'):
            # Command submitted, save it
            logger.debug(f"👤 User submitted command: {repr(self.user_command)}")
            self.user_command = ""  # Reset for next command
        
        # Keep only last 500 chars of user input for context
        if len(self.user_input_buffer) > 500:
            self.user_input_buffer = self.user_input_buffer[-500:]
        
        logger.debug(f"👤 User input detected: {repr(text[:50])}, AI proxy paused")
    
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
        
        current_time = asyncio.get_event_loop().time()
        self.last_output_chunk_time = current_time  # Track chunk arrival for streaming detection
        self.last_output_time = current_time
    
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
        
        # Check for inactivity (terminal idle after self.terminal_idle_timeout)
        current_time = asyncio.get_event_loop().time()
        time_since_output = current_time - self.last_output_time
        if time_since_output > self.terminal_idle_timeout:
            # Log buffer contents for debugging
            buffer_preview = '\n'.join([repr(line[:80]) for line in list(self.output_buffer)[-5:]])
            logger.info(f"✓ Prompt detected by terminal inactivity ({time_since_output:.1f}s)")
            logger.debug(f"Last 5 lines in buffer:\n{buffer_preview}")
            return True
        
        return False
    
    def _build_context(self) -> str:
        """Build context from recent output with aggressive cleaning and deduplication"""
        # Get last N lines of output (configurable for different terminal sizes)
        recent_lines = list(self.output_buffer)[-self.context_lines:]
        
        # Aggressively clean each line
        cleaned_lines = []
        seen_lines = set()  # Track duplicates
        consecutive_duplicates = 0
        last_clean_line = ""
        
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
            
            # Enhanced noise filtering
            if self._is_noise_line(clean):
                continue
            
            # Deduplication: skip consecutive identical lines (common in Claude output)
            if clean == last_clean_line:
                consecutive_duplicates += 1
                if consecutive_duplicates > 2:  # Allow max 2 consecutive duplicates
                    continue
            else:
                consecutive_duplicates = 0
                last_clean_line = clean
            
            # Skip if we've seen this exact line too many times
            if clean in seen_lines and len([l for l in cleaned_lines if l == clean]) >= 3:
                continue
            
            seen_lines.add(clean)
            cleaned_lines.append(clean)
        
        # Further optimize: keep only the most relevant lines
        optimized_lines = self._optimize_context_lines(cleaned_lines)
        
        context = '\n'.join(optimized_lines)
        
        # Log cleaned context for debugging
        logger.debug(f"Built context with {len(optimized_lines)} optimized lines (from {len(recent_lines)} raw)")
        logger.debug(f"Clean context preview: {context[:300]}...")
        
        return context
    
    def _is_noise_line(self, line: str) -> bool:
        """Enhanced noise detection for terminal output"""
        # Skip pure decoration lines (box drawing, spinner symbols, separators)
        if re.match(r'^[─┌┐└┘├┤┬┴┼│\-_=]{3,}$', line):
            return True
        
        # Skip spinner/loading lines
        if re.match(r'^[∴✶✽⎿\*\.]+.*(?:esc to interrupt|ctrl\+[a-z])', line, re.IGNORECASE):
            return True
        
        # Skip common loading/status messages
        if re.match(r'^[\*∴✶✽]\s+(Thought|Imagining|Thinking|Loading|Finagling|Processing)', line, re.IGNORECASE):
            return True
        
        # Skip Claude-specific UI elements
        if re.match(r'^\* ▐▛███▜▌ \*', line):  # Claude header
            return True
        if re.match(r'^═+.*═+$', line):  # Separator lines
            return True
        if re.match(r'^⎿\s+(Read \d+ lines|Interrupted)', line):  # Claude status
            return True
        if re.match(r'^ctrl\+[a-z]', line, re.IGNORECASE):  # Control instructions
            return True
        
        # Skip repetitive prompts and status
        if line in ['? for shortcuts', '>', 'Waiting…', '✢', '●']:
            return True
        
        # Skip very long repetitive lines (likely formatting artifacts)
        if len(line) > 200 and len(set(line)) < 10:  # Very repetitive content
            return True
        
        return False
    
    def _optimize_context_lines(self, lines: list[str]) -> list[str]:
        """Keep only the most relevant lines for LLM context"""
        if len(lines) <= 20:  # If already short, keep all
            return lines
        
        optimized = []
        
        # Always keep the last 10 lines (most recent context)
        recent_lines = lines[-10:]
        
        # From the rest, keep lines that look like prompts or important content
        earlier_lines = lines[:-10]
        important_lines = []
        
        for line in earlier_lines:
            # Keep lines that look like prompts or questions
            if any(pattern in line.lower() for pattern in ['?', ':', 'enter', 'select', 'choose', 'continue']):
                important_lines.append(line)
            # Keep lines with numbered options
            elif re.search(r'^\s*\d+[\.\)]\s+', line):
                important_lines.append(line)
            # Keep lines with menu indicators
            elif re.search(r'[❯▶►]\s*', line):
                important_lines.append(line)
        
        # Combine: important earlier lines + recent lines, max 30 total
        optimized = (important_lines[-10:] + recent_lines)[-30:]
        
        return optimized
    
    def _build_optimized_prompt(self, context: str, user_context: str, memory_context: str) -> str:
        """Build an optimized prompt with better structure and reduced noise"""
        
        # Analyze context to determine prompt type
        prompt_type = self._analyze_prompt_type(context)
        
        # Build context-aware instructions
        if prompt_type == "menu":
            instructions = """MENU DETECTED: Select an option by typing the number or letter."""
            example_response = '{"action": "select_option", "input": "1", "confidence": 0.9, "reasoning": "First option seems most appropriate"}'
        elif prompt_type == "yes_no":
            instructions = """YES/NO QUESTION: Respond with "y" for yes or "n" for no."""
            example_response = '{"action": "yes_no", "input": "y", "confidence": 0.8, "reasoning": "Confirming the action"}'
        elif prompt_type == "text_input":
            instructions = """TEXT INPUT: Provide a brief, appropriate response."""
            example_response = '{"action": "text_input", "input": "example", "confidence": 0.7, "reasoning": "Providing requested text"}'
        elif prompt_type == "continuation":
            instructions = """CONTINUATION: Press Enter to continue or provide appropriate input."""
            example_response = '{"action": "continue", "input": "", "confidence": 0.9, "reasoning": "Continuing as requested"}'
        else:
            instructions = """GENERAL PROMPT: Analyze the screen and provide the most appropriate response."""
            example_response = '{"action": "general", "input": "1", "confidence": 0.6, "reasoning": "Default safe choice"}'
        
        # Build the optimized prompt with JSON response format
        prompt = f"""TERMINAL AUTOMATION TASK

{instructions}

CURRENT SCREEN:
{context}

RESPONSE FORMAT:
Respond with JSON containing:
- "action": type of action ("{prompt_type}")
- "input": exact text to type
- "confidence": 0.0-1.0 confidence score
- "reasoning": brief explanation of choice

RESPONSE RULES:
- For menus: select the most logical option number/letter
- For yes/no: choose based on context and safety
- For text input: provide brief, relevant responses
- When uncertain: choose safe/default options
- Confidence < 0.5: choose conservative options

{memory_context}{user_context}

Example response: {example_response}

Your JSON response:"""
        
        return prompt
    
    def _analyze_prompt_type(self, context: str) -> str:
        """Analyze context to determine the type of prompt"""
        context_lower = context.lower()
        
        # Check for numbered menus
        if re.search(r'^\s*\d+[\.\)]\s+', context, re.MULTILINE) or '❯' in context:
            return "menu"
        
        # Check for yes/no questions
        if re.search(r'\(y/n\)|\[y/n\]|yes.*no|continue\?', context_lower):
            return "yes_no"
        
        # Check for text input prompts
        if re.search(r'enter.*:|name.*:|path.*:|file.*:', context_lower):
            return "text_input"
        
        # Check for continuation prompts
        if re.search(r'press.*enter|continue|more|next', context_lower):
            return "continuation"
        
        return "general"
    
    def _parse_llm_response(self, response: str) -> dict:
        """
        Parse LLM response, trying JSON first, then falling back to plain text
        
        Returns:
            dict with keys: action, input, confidence, reasoning, format
        """
        
        # Try to parse as JSON first
        try:
            # Look for JSON in the response (might be wrapped in text)
            json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                
                # Validate required fields
                if all(key in parsed for key in ['action', 'input', 'confidence', 'reasoning']):
                    logger.info(f"✓ Parsed JSON response: {parsed['action']} (confidence: {parsed['confidence']:.2f})")
                    return {
                        'action': parsed['action'],
                        'input': str(parsed['input']),
                        'confidence': float(parsed['confidence']),
                        'reasoning': str(parsed['reasoning']),
                        'format': 'json'
                    }
                else:
                    logger.warning(f"⚠️ JSON missing required fields: {list(parsed.keys())}")
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"JSON parsing failed: {e}")
        
        # Fallback to plain text parsing
        logger.info("📝 Falling back to plain text parsing")
        
        # Clean the response
        clean_response = response.strip()
        
        # Remove common JSON artifacts if present
        clean_response = re.sub(r'^```json\s*', '', clean_response)
        clean_response = re.sub(r'\s*```$', '', clean_response)
        clean_response = re.sub(r'^[{"].*[}"]$', lambda m: self._extract_input_from_malformed_json(m.group(0)), clean_response)
        
        # Determine action type based on content
        action_type = "general"
        confidence = 0.6  # Default confidence for plain text
        
        # Analyze the response to guess action type and confidence
        if re.match(r'^\d+$', clean_response):
            action_type = "menu"
            confidence = 0.8
        elif clean_response.lower() in ['y', 'yes', 'n', 'no']:
            action_type = "yes_no"
            confidence = 0.9
        elif clean_response == "":
            action_type = "continue"
            confidence = 0.7
        elif len(clean_response) > 20:
            action_type = "text_input"
            confidence = 0.5
        
        return {
            'action': action_type,
            'input': clean_response,
            'confidence': confidence,
            'reasoning': f"Plain text fallback: detected {action_type} response",
            'format': 'plain_text'
        }
    
    def _extract_input_from_malformed_json(self, json_str: str) -> str:
        """Extract input value from malformed JSON string"""
        try:
            # Try to find "input": "value" pattern
            input_match = re.search(r'"input"\s*:\s*"([^"]*)"', json_str)
            if input_match:
                return input_match.group(1)
            
            # Try to find "input": value pattern (unquoted)
            input_match = re.search(r'"input"\s*:\s*([^,}]+)', json_str)
            if input_match:
                return input_match.group(1).strip().strip('"')
                
        except Exception:
            pass
        
        # Last resort: return the whole string
        return json_str
    
    def _extract_relevant_context_for_memory(self, full_context: str) -> str:
        """Extract only the most relevant parts for memory storage"""
        lines = full_context.split('\n')
        
        # Keep only the last few lines that contain actual prompts or questions
        relevant_lines = []
        for line in lines[-5:]:  # Last 5 lines max
            if line.strip() and any(char in line for char in ['?', ':', '❯', '▶']):
                relevant_lines.append(line.strip())
        
        # If no clear prompts found, keep the last non-empty line
        if not relevant_lines:
            for line in reversed(lines):
                if line.strip():
                    relevant_lines = [line.strip()]
                    break
        
        return ' | '.join(relevant_lines) if relevant_lines else "terminal prompt"
    
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
        
        Only triggers LLM when:
        1. User is idle (hasn't typed in user_idle_timeout seconds)
        2. Terminal is idle (no output in terminal_idle_timeout seconds)
        3. Cooldown period has passed since last AI response
        """
        if not self.enabled:
            return
        
        if self.iteration_count >= self.max_iterations:
            logger.warning(f"AI Proxy max iterations ({self.max_iterations}) reached, disabling")
            self.disable()
            return
        
        current_time = asyncio.get_event_loop().time()
        
        # Check if terminal is actively streaming output - if so, don't intervene
        time_since_last_chunk = current_time - self.last_output_chunk_time
        if time_since_last_chunk < self.streaming_detection_window:
            logger.debug(f"📡 Terminal actively streaming (last chunk {time_since_last_chunk:.2f}s ago), AI proxy waiting")
            return
        
        # Check if user is actively typing - if so, don't intervene
        time_since_user_input = current_time - self.last_user_input_time
        if self.last_user_input_time > 0 and time_since_user_input < self.user_idle_timeout:
            logger.debug(f"👤 User is typing (last input {time_since_user_input:.1f}s ago), AI proxy paused")
            return
        
        time_since_response = current_time - self.last_response_time
        
        # Check cooldown - don't respond too quickly after last response
        if time_since_response < self.response_cooldown:
            logger.debug(f"In cooldown period ({time_since_response:.1f}s < {self.response_cooldown}s)")
            return
        
        # Normal prompt detection
        prompt_detected = self._detect_prompt()
        
        # OVERRIDE: Check if terminal is stuck (no changes after our response for 60s)
        # This overrides normal prompt detection if screen has been stale too long
        if self.last_response_time > 0 and time_since_response > self.stuck_check_timeout:
            # Check if buffer content has changed since last response
            current_hash = hash(''.join(list(self.output_buffer)))
            if current_hash == self.last_buffer_hash:
                logger.info(f"⚠️ Terminal stuck for {time_since_response:.0f}s with no changes - forcing re-query")
                logger.debug(f"Buffer hash unchanged: {current_hash}")
                # Force LLM query even if no prompt detected
                prompt_detected = True
            else:
                # Buffer changed, update hash for next check
                logger.debug(f"Buffer changed since last response: {self.last_buffer_hash} -> {current_hash}")
                self.last_buffer_hash = current_hash
                # Continue with normal prompt detection result (already computed above)
        
        if not prompt_detected:
            return
        
        # Build prompt for LLM
        context = self._build_context()
        memory_context = self._build_memory_context()
        
        # Add user input context if available - clearly separate from terminal output
        user_context = ""
        if self.user_input_buffer:
            recent_input = ''.join(self.user_input_buffer[-500:])  # Last 500 chars
            user_context = f"\n\n--- USER COMMANDS (what the user typed, DO NOT repeat this) ---\n{recent_input}\n--- END USER COMMANDS ---"
        
        # Monitor and limit context size
        max_context_size = Config.AI_PROXY_MAX_CONTEXT_SIZE
        if len(context) > max_context_size:
            logger.warning(f"Context too large ({len(context)} chars), truncating to {max_context_size}...")
            context = context[-max_context_size:]  # Keep the end (most recent)
        
        logger.info(f"🤖 Building LLM prompt with {len(context)} chars of context, {len(self.conversation_memory)} memory items, user_input={bool(self.user_input_buffer)}")
        logger.debug(f"Context preview: {context[:200]}...")
        
        # Build optimized prompt with better structure
        prompt = self._build_optimized_prompt(context, user_context, memory_context)
        
        # Calculate prompt efficiency metrics
        prompt_length = len(prompt)
        context_ratio = len(context) / prompt_length if prompt_length > 0 else 0
        
        logger.info(f"→ Querying {self.llm_provider.get_name()} (iteration {self.iteration_count + 1}/{self.max_iterations})")
        logger.info(f"📊 Prompt stats: {prompt_length} chars total, {len(context)} chars context ({context_ratio:.1%} ratio)")
        
        # Send monitoring data for request
        if hasattr(self, 'monitor_callback') and self.monitor_callback:
            await self.monitor_callback('request', {
                'provider': self.llm_provider.get_name(),
                'prompt': prompt,
                'iteration': self.iteration_count + 1,
                'context_length': len(context),
                'prompt_length': prompt_length
            })
        
        try:
            start_time = asyncio.get_event_loop().time()
            response = await self._try_llm_with_fallback(prompt)
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)
            
            if response:
                response = response.strip()
                self.iteration_count += 1
                logger.info(f"← Got {len(response)} chars from LLM: {response[:100]}{'...' if len(response) > 100 else ''}")
                
                # Send monitoring data for response
                if hasattr(self, 'monitor_callback') and self.monitor_callback:
                    await self.monitor_callback('response', {
                        'provider': self.llm_provider.get_name(),
                        'response': response,
                        'duration': duration_ms,
                        'iteration': self.iteration_count
                    })
                
                # Parse JSON response with fallback to plain text
                parsed_response = self._parse_llm_response(response)
                
                # Store in memory with better context
                relevant_context = self._extract_relevant_context_for_memory(context)
                self.conversation_memory.append({
                    'role': 'prompt',
                    'content': relevant_context
                })
                self.conversation_memory.append({
                    'role': 'response',
                    'content': parsed_response['input']  # Store the actual input we'll send
                })
                
                # Summarize and compress memory if it's getting large
                if len(self.conversation_memory) > self.summarize_threshold:
                    await self._summarize_memory()
                
                logger.debug(f"💭 Updated conversation memory: {len(self.conversation_memory)} items, has_summary={bool(self.memory_summary)}")
                
                # Send monitoring data for parsed response
                if hasattr(self, 'monitor_callback') and self.monitor_callback:
                    await self.monitor_callback('parsed_response', {
                        'provider': self.llm_provider.get_name(),
                        'action': parsed_response['action'],
                        'input': parsed_response['input'],
                        'confidence': parsed_response['confidence'],
                        'reasoning': parsed_response['reasoning'],
                        'format': parsed_response['format']
                    })
                
                # Check confidence and decide whether to proceed
                if parsed_response['confidence'] < 0.3:
                    logger.warning(f"⚠️ Low confidence response ({parsed_response['confidence']:.2f}), skipping action")
                    logger.info(f"Reasoning: {parsed_response['reasoning']}")
                    return
                
                # Send response to terminal
                if self.send_input_callback:
                    input_to_send = parsed_response['input']
                    logger.info(f"✉ Sending {parsed_response['action']} response (confidence: {parsed_response['confidence']:.2f}): {repr(input_to_send)}")
                    logger.info(f"💭 Reasoning: {parsed_response['reasoning']}")
                    
                    await self.send_input_callback(input_to_send)
                    # Set cooldown timestamp and save buffer state IMMEDIATELY for stuck detection
                    self.last_response_time = asyncio.get_event_loop().time()
                    # Wait a bit for output to settle, then capture baseline hash
                    await asyncio.sleep(0.5)
                    self.last_buffer_hash = hash(''.join(list(self.output_buffer)))
                    logger.info(f"✓ Response sent, baseline hash={self.last_buffer_hash}, cooldown={self.response_cooldown}s, stuck_check={self.stuck_check_timeout}s")
                else:
                    logger.error("❌ No input callback set!")
            else:
                logger.error("❌ LLM returned empty response")
                
                # Send monitoring data for empty response
                if hasattr(self, 'monitor_callback') and self.monitor_callback:
                    await self.monitor_callback('error', {
                        'provider': self.llm_provider.get_name(),
                        'error': 'Empty response from LLM',
                        'code': 'EMPTY_RESPONSE'
                    })
                
        except Exception as e:
            logger.error(f"❌ AI Proxy error: {e}", exc_info=True)
            
            # Send monitoring data for error
            if hasattr(self, 'monitor_callback') and self.monitor_callback:
                await self.monitor_callback('error', {
                    'provider': self.llm_provider.get_name() if self.llm_provider else 'Unknown',
                    'error': str(e),
                    'code': 'EXCEPTION'
                })
    
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
