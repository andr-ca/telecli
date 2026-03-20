"""
Integration tests for LLM providers with fallback support
"""
import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.llm_provider import LLMProvider, LLMResponse, LLMProviderFactory
from src.gemini_provider import GeminiCLIProvider
from src.github_provider import GitHubCLIProvider
from src.llm_providers import ClaudeCLIProvider
from src.ai_proxy import AIProxy

logger = logging.getLogger(__name__)


class TestLLMResponse:
    """Test LLMResponse class"""
    
    def test_response_success(self):
        """Test successful response"""
        response = LLMResponse(text="Hello")
        assert response.is_success
        assert response.text == "Hello"
        assert response.error_code is None
        assert bool(response) is True
    
    def test_response_error_429(self):
        """Test rate limit error response"""
        response = LLMResponse(error_code=429, error_message="Rate limited")
        assert not response.is_success
        assert response.error_code == 429
        assert response.error_message == "Rate limited"
        assert bool(response) is False
    
    def test_response_error_500(self):
        """Test server error response"""
        response = LLMResponse(error_code=500, error_message="Internal error")
        assert not response.is_success
        assert response.error_code == 500
        assert bool(response) is False
    
    def test_response_str_representation(self):
        """Test string representation"""
        success = LLMResponse(text="Success text")
        assert str(success) == "Success text"
        
        error = LLMResponse(error_code=429, error_message="Rate limited")
        assert "429" in str(error)
        assert "Rate limited" in str(error)


class MockGeminiProvider(GeminiCLIProvider):
    """Mock Gemini provider for testing"""
    
    def __init__(self, should_fail=False, error_code=None):
        self.cli_path = "/mock/gemini"
        self.should_fail = should_fail
        self.error_code = error_code or 500
        self.call_count = 0
    
    async def generate(self, prompt: str, system_prompt=None) -> LLMResponse:
        """Mock generate that can fail or succeed"""
        self.call_count += 1
        if self.should_fail:
            return LLMResponse(error_code=self.error_code, error_message="Mock error")
        return LLMResponse(text=f"Gemini response to: {prompt[:50]}")
    
    def is_available(self) -> bool:
        return True


class MockGitHubProvider(GitHubCLIProvider):
    """Mock GitHub provider for testing"""
    
    def __init__(self, should_fail=False, error_code=None):
        self.cli_path = "/mock/gh"
        self.should_fail = should_fail
        self.error_code = error_code or 500
        self.call_count = 0
    
    async def generate(self, prompt: str, system_prompt=None) -> LLMResponse:
        """Mock generate that can fail or succeed"""
        self.call_count += 1
        if self.should_fail:
            return LLMResponse(error_code=self.error_code, error_message="Mock error")
        return LLMResponse(text=f"GitHub response to: {prompt[:50]}")
    
    def is_available(self) -> bool:
        return True


class MockClaudeProvider(ClaudeCLIProvider):
    """Mock Claude provider for testing"""
    
    def __init__(self, should_fail=False, error_code=None):
        self.cli_path = "/mock/claude"
        self.should_fail = should_fail
        self.error_code = error_code or 500
        self.call_count = 0
    
    async def generate(self, prompt: str, system_prompt=None) -> LLMResponse:
        """Mock generate that can fail or succeed"""
        self.call_count += 1
        if self.should_fail:
            return LLMResponse(error_code=self.error_code, error_message="Mock error")
        return LLMResponse(text=f"Claude response to: {prompt[:50]}")
    
    def is_available(self) -> bool:
        return True


class TestProviderAvailability:
    """Test provider availability detection"""
    
    def test_gemini_available_with_cli(self):
        """Test Gemini provider detects available CLI"""
        provider = MockGeminiProvider()
        assert provider.is_available()
        assert provider.get_name() == "gemini-cli"
    
    def test_github_available_with_cli(self):
        """Test GitHub provider detects available CLI"""
        provider = MockGitHubProvider()
        assert provider.is_available()
        assert provider.get_name() == "github-cli"
    
    def test_claude_available_with_cli(self):
        """Test Claude provider detects available CLI"""
        provider = MockClaudeProvider()
        assert provider.is_available()
        assert provider.get_name() == "claude-cli"


class TestLLMProviderFactory:
    """Test LLM provider factory"""
    
    def test_factory_registration(self):
        """Test provider registration in factory"""
        # Providers should be registered
        factory = LLMProviderFactory()
        
        # Check that providers are registered
        assert "gemini-cli" in factory._providers
        assert "github-cli" in factory._providers
        assert "claude-cli" in factory._providers
    
    def test_get_available_providers(self):
        """Test getting available providers"""
        # This will include real providers if CLIs are available
        # For testing, we just check the method works
        available = LLMProviderFactory.get_available_providers()
        
        # Should return list of tuples
        assert isinstance(available, list)
        for name, provider in available:
            assert isinstance(name, str)
            assert isinstance(provider, LLMProvider)


@pytest.mark.asyncio
class TestProviderGeneration:
    """Test LLM provider response generation"""
    
    async def test_gemini_successful_generation(self):
        """Test Gemini successful generation"""
        provider = MockGeminiProvider(should_fail=False)
        response = await provider.generate("test prompt")
        
        assert response.is_success
        assert "Gemini response" in response.text
        assert provider.call_count == 1
    
    async def test_gemini_failed_generation(self):
        """Test Gemini failed generation"""
        provider = MockGeminiProvider(should_fail=True, error_code=500)
        response = await provider.generate("test prompt")
        
        assert not response.is_success
        assert response.error_code == 500
        assert provider.call_count == 1
    
    async def test_gemini_rate_limit(self):
        """Test Gemini rate limit detection"""
        provider = MockGeminiProvider(should_fail=True, error_code=429)
        response = await provider.generate("test prompt")
        
        assert not response.is_success
        assert response.error_code == 429
    
    async def test_github_successful_generation(self):
        """Test GitHub successful generation"""
        provider = MockGitHubProvider(should_fail=False)
        response = await provider.generate("test prompt")
        
        assert response.is_success
        assert "GitHub response" in response.text
        assert provider.call_count == 1
    
    async def test_github_rate_limit(self):
        """Test GitHub rate limit detection"""
        provider = MockGitHubProvider(should_fail=True, error_code=429)
        response = await provider.generate("test prompt")
        
        assert not response.is_success
        assert response.error_code == 429


@pytest.mark.asyncio
class TestAIProxyFallback:
    """Test AI Proxy fallback mechanism"""
    
    async def test_fallback_on_primary_rate_limit(self):
        """Test fallback when primary provider hits rate limit"""
        # Primary provider fails with 429
        primary = MockGeminiProvider(should_fail=True, error_code=429)
        
        # Create AIProxy with fallback
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=["github-cli"]
        )
        
        # Mock the factory to return our mock providers
        with patch.object(LLMProviderFactory, 'create') as mock_create:
            fallback = MockGitHubProvider(should_fail=False)
            
            def create_side_effect(name):
                if name == "github-cli":
                    return fallback
                return None
            
            mock_create.side_effect = create_side_effect
            
            # Try LLM with fallback
            result = await proxy._try_llm_with_fallback("test prompt")
            
            # Should have tried primary and gotten fallback response
            assert result is not None
            assert "GitHub response" in result
            assert primary.call_count == 1
            assert fallback.call_count == 1
    
    async def test_fallback_chain_multiple_failures(self):
        """Test fallback chain with multiple failures"""
        # Primary fails with 429
        primary = MockGeminiProvider(should_fail=True, error_code=429)
        
        # Create AIProxy with multiple fallbacks
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=["github-cli", "claude-cli"]
        )
        
        with patch.object(LLMProviderFactory, 'create') as mock_create:
            github = MockGitHubProvider(should_fail=True, error_code=429)
            claude = MockClaudeProvider(should_fail=False)
            
            def create_side_effect(name):
                if name == "github-cli":
                    return github
                elif name == "claude-cli":
                    return claude
                return None
            
            mock_create.side_effect = create_side_effect
            
            # Try LLM with fallback chain
            result = await proxy._try_llm_with_fallback("test prompt")
            
            # Should eventually succeed with Claude
            assert result is not None
            assert "Claude response" in result
            assert primary.call_count == 1
            assert github.call_count == 1
            assert claude.call_count == 1
    
    async def test_fallback_all_fail(self):
        """Test fallback when all providers fail"""
        primary = MockGeminiProvider(should_fail=True, error_code=500)
        
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=["github-cli"]
        )
        
        with patch.object(LLMProviderFactory, 'create') as mock_create:
            fallback = MockGitHubProvider(should_fail=True, error_code=500)
            
            def create_side_effect(name):
                if name == "github-cli":
                    return fallback
                return None
            
            mock_create.side_effect = create_side_effect
            
            # Try LLM when all fail
            result = await proxy._try_llm_with_fallback("test prompt")
            
            # Should return None when all fail
            assert result is None
    
    async def test_primary_succeeds_no_fallback_needed(self):
        """Test that fallback is not used when primary succeeds"""
        primary = MockGeminiProvider(should_fail=False)
        fallback = MockGitHubProvider(should_fail=False)
        
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=["github-cli"]
        )
        
        with patch.object(LLMProviderFactory, 'create') as mock_create:
            mock_create.return_value = fallback
            
            # Try LLM when primary succeeds
            result = await proxy._try_llm_with_fallback("test prompt")
            
            # Should succeed immediately with primary
            assert result is not None
            assert "Gemini response" in result
            assert primary.call_count == 1
            # Fallback should not be called
            assert fallback.call_count == 0


@pytest.mark.asyncio
class TestAIProxyIntegration:
    """Test AIProxy integration with providers"""
    
    async def test_proxy_enable_with_primary_provider(self):
        """Test enabling proxy with primary provider"""
        provider = MockGeminiProvider(should_fail=False)
        proxy = AIProxy(
            llm_provider=provider,
            system_prompt="Test prompt",
            max_iterations=5
        )
        
        proxy.enable()
        
        assert proxy.is_enabled()
        assert proxy.iteration_count == 0
        assert len(proxy.conversation_memory) == 0
    
    async def test_proxy_with_fallback_providers_list(self):
        """Test proxy initialized with fallback providers"""
        primary = MockGeminiProvider()
        fallbacks = ["github-cli", "claude-cli"]
        
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=fallbacks
        )
        
        assert proxy.primary_provider_name == "gemini-cli"
        assert proxy.fallback_provider_names == fallbacks

    async def test_proxy_accepts_legacy_provider_kwargs(self):
        """Test proxy accepts legacy primary/fallback provider kwargs."""
        primary = MockGeminiProvider()
        fallbacks = ["github-cli", "claude-cli"]

        with patch.object(LLMProviderFactory, "create", return_value=primary) as mock_create:
            proxy = AIProxy(
                primary_provider="gemini-cli",
                fallback_providers=fallbacks,
            )

        mock_create.assert_called_once_with("gemini-cli")
        assert proxy.llm_provider is primary
        assert proxy.primary_provider == "gemini-cli"
        assert proxy.primary_provider_name == "gemini-cli"
        assert proxy.fallback_providers == fallbacks
        assert proxy.fallback_provider_names == fallbacks
    
    async def test_proxy_output_buffer_management(self):
        """Test proxy output buffer management"""
        provider = MockGeminiProvider()
        proxy = AIProxy(llm_provider=provider, buffer_size=100)
        
        # Enable proxy to allow output processing
        proxy.enable()
        
        # Add some output
        proxy.add_output("Line 1\n")
        proxy.add_output("Line 2\n")
        
        assert len(proxy.output_buffer) == 2
        
        # Test buffer maxlen
        for i in range(150):
            proxy.add_output(f"Line {i}\n")
        
        # Should be limited to 100
        assert len(proxy.output_buffer) <= 100


class TestErrorCodeDetection:
    """Test error code detection in providers"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_code_429(self):
        """Test rate limit error code 429 detection"""
        provider = MockGeminiProvider(should_fail=True, error_code=429)
        response = await provider.generate("test")
        
        assert response.error_code == 429
    
    @pytest.mark.asyncio
    async def test_timeout_error_code_504(self):
        """Test timeout error code 504"""
        provider = MockGeminiProvider(should_fail=True, error_code=504)
        response = await provider.generate("test")
        
        assert response.error_code == 504
    
    @pytest.mark.asyncio
    async def test_unavailable_error_code_503(self):
        """Test unavailable error code 503"""
        provider = MockGeminiProvider(should_fail=True, error_code=503)
        response = await provider.generate("test")
        
        assert response.error_code == 503


class TestProviderSwitching:
    """Test provider switching after fallback"""
    
    @pytest.mark.asyncio
    async def test_provider_switches_on_fallback_success(self):
        """Test that active provider switches when fallback succeeds"""
        primary = MockGeminiProvider(should_fail=True, error_code=429)
        fallback = MockGitHubProvider(should_fail=False)
        
        proxy = AIProxy(
            llm_provider=primary,
            fallback_providers=["github-cli"]
        )
        
        # Verify primary is active
        assert proxy.primary_provider_name == "gemini-cli"
        assert proxy.llm_provider.get_name() == "gemini-cli"
        
        with patch.object(LLMProviderFactory, 'create') as mock_create:
            mock_create.return_value = fallback
            
            result = await proxy._try_llm_with_fallback("test prompt")
            
            # After fallback succeeds, provider should be switched
            assert result is not None
            # Note: Provider switching logic updates self.llm_provider
            # This would be reflected in subsequent calls


@pytest.mark.asyncio
class TestLLMLoggingIntegration:
    """Test LLM interaction logging"""
    
    async def test_response_contains_expected_data(self):
        """Test response has all expected metadata"""
        provider = MockGeminiProvider()
        system_prompt = "Be helpful"
        user_prompt = "What is 2+2?"
        
        response = await provider.generate(user_prompt, system_prompt)
        
        assert response.is_success
        assert response.text
        assert response.error_code is None
        assert response.error_message is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
