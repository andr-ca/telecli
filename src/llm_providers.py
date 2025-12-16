"""
LLM provider implementations and factory registration
"""
import asyncio
import logging
import shutil
from typing import Optional
from pathlib import Path
from src.llm_provider import LLMProvider, LLMProviderFactory, LLMResponse
from datetime import datetime

logger = logging.getLogger(__name__)

# Create dedicated LLM interaction logger
llm_logger = logging.getLogger('llm_interactions')
llm_logger.setLevel(logging.INFO)

# Add file handler for LLM interactions if not already added
if not llm_logger.handlers:
    # Ensure logs directory exists
    Path('logs').mkdir(parents=True, exist_ok=True)
    
    llm_handler = logging.FileHandler('logs/llm_interactions.log')
    llm_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    llm_logger.addHandler(llm_handler)
    llm_logger.propagate = False  # Don't propagate to root logger


# Import providers from separate modules
from src.gemini_provider import GeminiCLIProvider
from src.github_provider import GitHubCLIProvider
from src.claude_provider import ClaudeCLIProvider


# Register all providers
LLMProviderFactory.register("gemini-cli", GeminiCLIProvider)
LLMProviderFactory.register("claude-cli", ClaudeCLIProvider)
LLMProviderFactory.register("github-cli", GitHubCLIProvider)

# Register providers
LLMProviderFactory.register("gemini-cli", GeminiCLIProvider)
LLMProviderFactory.register("claude-cli", ClaudeCLIProvider)
LLMProviderFactory.register("github-cli", GitHubCLIProvider)
