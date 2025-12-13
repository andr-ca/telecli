"""
Concrete LLM provider implementations
"""
import asyncio
import logging
import shutil
from typing import Optional
from src.llm_provider import LLMProvider, LLMProviderFactory

logger = logging.getLogger(__name__)


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
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Generate response using gemini CLI"""
        if not self.is_available():
            logger.error("Gemini CLI not available")
            return None
        
        try:
            # Build full prompt with system instructions
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Run gemini CLI with --prompt flag for non-interactive mode
            cmd = [self.cli_path, "--prompt", full_prompt]
            
            logger.info(f"Running gemini with prompt: {prompt[:50]}...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Gemini CLI error: {error_msg}")
                return None
            
            response = stdout.decode().strip()
            logger.info(f"Gemini CLI response: {response[:100]}...")
            return response
            
        except asyncio.TimeoutError:
            logger.error("Gemini CLI timeout")
            return None
        except Exception as e:
            logger.error(f"Gemini CLI error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.cli_path is not None
    
    def get_name(self) -> str:
        return "gemini-cli"


class ClaudeCLIProvider(LLMProvider):
    """
    Provider using the Claude CLI tool
    Requires: claude CLI installed in PATH
    """
    
    def __init__(self):
        self.cli_path = shutil.which("claude")
        if self.cli_path:
            logger.info(f"Found claude CLI at: {self.cli_path}")
        else:
            logger.warning("Claude CLI not found in PATH")
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Generate response using claude CLI"""
        if not self.is_available():
            logger.error("Claude CLI not available")
            return None
        
        try:
            # Build command
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            cmd = [self.cli_path, full_prompt]
            
            logger.info(f"Running: {' '.join(cmd[:2])}...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Claude CLI error: {error_msg}")
                return None
            
            response = stdout.decode().strip()
            logger.info(f"Claude CLI response: {response[:100]}...")
            return response
            
        except asyncio.TimeoutError:
            logger.error("Claude CLI timeout")
            return None
        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.cli_path is not None
    
    def get_name(self) -> str:
        return "claude-cli"


# Register providers
LLMProviderFactory.register("gemini-cli", GeminiCLIProvider)
LLMProviderFactory.register("claude-cli", ClaudeCLIProvider)
