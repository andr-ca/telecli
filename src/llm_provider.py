"""
LLM Provider abstraction layer
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class LLMResponse:
    """Response object from LLM provider"""
    def __init__(self, text: Optional[str] = None, error_code: Optional[int] = None, error_message: Optional[str] = None):
        self.text = text
        self.error_code = error_code  # HTTP-like error codes (e.g., 429 for rate limit)
        self.error_message = error_message
        self.is_success = text is not None and error_code is None
    
    def __bool__(self):
        return self.is_success
    
    def __str__(self):
        if self.is_success:
            return self.text
        return f"Error {self.error_code}: {self.error_message}"


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate a response from the LLM
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            
        Returns:
            LLMResponse object containing text, error_code, and error_message
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available/configured"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the provider name"""
        pass


class LLMProviderFactory:
    """Factory to create and manage LLM providers"""
    
    _providers = {}
    
    @classmethod
    def register(cls, name: str, provider_class):
        """Register a provider class"""
        cls._providers[name] = provider_class
        logger.debug(f"Registered LLM provider: {name}")
    
    @classmethod
    def create(cls, provider_name: str) -> Optional[LLMProvider]:
        """
        Create an LLM provider by name
        
        Args:
            provider_name: Name of the provider (e.g., "gemini-cli")
            
        Returns:
            LLMProvider instance or None if not found
        """
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            logger.error(f"Unknown provider: {provider_name}")
            return None
        
        provider = provider_class()
        if not provider.is_available():
            logger.warning(f"Provider {provider_name} is not available")
            return None
        
        return provider
    
    @classmethod
    def get_available_providers(cls) -> list[tuple[str, LLMProvider]]:
        """
        Get all available providers as (name, instance) tuples
        Filters for providers that are actually available
        
        Returns:
            List of (provider_name, provider_instance) tuples sorted by name
        """
        available = []
        for name in sorted(cls._providers.keys()):
            provider = cls.create(name)
            if provider and provider.is_available():
                available.append((name, provider))
        return available
    
    @classmethod
    def get_default_provider(cls) -> Optional[LLMProvider]:
        """Get the first available provider"""
        available = cls.get_available_providers()
        if not available:
            logger.error("No LLM providers available")
            return None
        
        provider_name = available[0]
        logger.info(f"Using default provider: {provider_name}")
        return cls.create(provider_name)
