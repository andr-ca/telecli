"""
Gemini CLI LLM provider implementation
"""
import asyncio
import logging
import shutil
from typing import Optional
from datetime import datetime
from src.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Create dedicated LLM interaction logger
llm_logger = logging.getLogger('llm_interactions')


class GeminiCLIProvider(LLMProvider):
    """
    Provider using the Gemini CLI tool
    Requires: gemini CLI installed in PATH
    """
    
    def __init__(self):
        self.cli_path = shutil.which("gemini")
        if self.cli_path:
            logger.info(f"Found gemini CLI at: {self.cli_path}")
        else:
            logger.warning("Gemini CLI not found in PATH")
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate response using gemini CLI"""
        if not self.is_available():
            logger.error("Gemini CLI not available")
            return LLMResponse(error_code=503, error_message="Gemini CLI not available")
        
        try:
            # Build full prompt with system instructions
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Log request
            llm_logger.info("=" * 80)
            llm_logger.info(f"REQUEST to Gemini CLI at {datetime.now().isoformat()}")
            llm_logger.info("-" * 80)
            if system_prompt:
                llm_logger.info(f"System Prompt:\n{system_prompt}")
                llm_logger.info("-" * 80)
            llm_logger.info(f"User Prompt:\n{prompt}")
            llm_logger.info("-" * 80)
            
            # Run gemini CLI with positional prompt (--prompt is deprecated)
            cmd = [self.cli_path, "--output-format", "text", full_prompt]
            
            logger.info(f"Running gemini with prompt: {prompt[:50]}...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent stdin issues
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            from src.config import Config
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=Config.LLM_TIMEOUT_SECONDS)
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Gemini CLI error (code {process.returncode}): {error_msg}")
                
                # Check if it's a rate limit error (429)
                is_rate_limit = "429" in error_msg or "rate" in error_msg.lower() or "quota" in error_msg.lower()
                error_code = 429 if is_rate_limit else 500
                
                llm_logger.info(f"RESPONSE from Gemini CLI:")
                llm_logger.info("-" * 80)
                llm_logger.info(f"Status: ERROR (Code {error_code})")
                llm_logger.info(f"Error Message: {error_msg}")
                llm_logger.info("=" * 80 + "\n")
                
                return LLMResponse(error_code=error_code, error_message=error_msg)
            
            response = stdout.decode().strip()
            logger.info(f"Gemini CLI response: {response[:100]}...")
            
            # Log response
            llm_logger.info(f"RESPONSE from Gemini CLI:")
            llm_logger.info("-" * 80)
            llm_logger.info(f"Status: SUCCESS")
            llm_logger.info(f"Response Length: {len(response)} characters")
            llm_logger.info("-" * 80)
            llm_logger.info(response)
            llm_logger.info("=" * 80 + "\n")
            
            return LLMResponse(text=response)
            
        except asyncio.TimeoutError:
            logger.error("Gemini CLI timeout")
            llm_logger.info(f"RESPONSE from Gemini CLI:")
            llm_logger.info("-" * 80)
            llm_logger.info(f"Status: ERROR (Code 504)")
            llm_logger.info(f"Error Message: Gemini CLI timeout after {Config.LLM_TIMEOUT_SECONDS}s")
            llm_logger.info("=" * 80 + "\n")
            return LLMResponse(error_code=504, error_message="Gemini CLI timeout")
        except Exception as e:
            logger.error(f"Gemini CLI error: {e}")
            llm_logger.info(f"RESPONSE from Gemini CLI:")
            llm_logger.info("-" * 80)
            llm_logger.info(f"Status: ERROR (Code 500)")
            llm_logger.info(f"Error Message: {str(e)}")
            llm_logger.info("=" * 80 + "\n")
            return LLMResponse(error_code=500, error_message=str(e))

    
    def is_available(self) -> bool:
        return self.cli_path is not None
    
    def get_name(self) -> str:
        return "gemini-cli"
