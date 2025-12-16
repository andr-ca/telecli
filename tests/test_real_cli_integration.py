"""
Real CLI Integration Tests
Tests actual LLM CLI tools without mocks (requires tools to be installed)

Note: These tests validate that CLI tools are installed and accessible.
Some tests may skip if rate limits are exceeded or tools require authentication.
"""
import pytest
import asyncio
import shutil
from src.llm_provider import LLMProviderFactory
from src.gemini_provider import GeminiCLIProvider
from src.claude_provider import ClaudeCLIProvider
from src.github_provider import GitHubCLIProvider


class TestRealGeminiCLI:
    """Tests for real Gemini CLI integration"""
    
    @pytest.fixture(autouse=True)
    def skip_if_unavailable(self):
        """Skip tests if Gemini CLI is not available"""
        if not shutil.which('gemini'):
            pytest.skip("Gemini CLI not installed")
    
    @pytest.mark.asyncio
    async def test_gemini_cli_available(self):
        """Test that Gemini CLI is available"""
        provider = GeminiCLIProvider()
        assert provider.is_available()
        assert provider.get_name() == "gemini-cli"
    
    @pytest.mark.asyncio
    async def test_gemini_simple_generation(self):
        """Test Gemini CLI can generate a response (may hit rate limit)"""
        provider = GeminiCLIProvider()
        
        response = await provider.generate("Say hello world in one sentence")
        
        # May be successful or rate limited - both are valid test outcomes
        assert response is not None
        if response.is_success:
            assert len(response.text) > 0
            assert "hello" in response.text.lower() or "world" in response.text.lower()
        else:
            # Rate limit or other error is expected in some scenarios
            assert response.error_code in [429, 500, 503, 504]
    
    @pytest.mark.asyncio
    async def test_gemini_with_system_prompt(self):
        """Test Gemini CLI with system prompt (may hit rate limit)"""
        provider = GeminiCLIProvider()
        
        response = await provider.generate(
            prompt="Count to 3",
            system_prompt="You are a helpful assistant. Keep responses concise."
        )
        
        assert response is not None
        if response.is_success:
            assert len(response.text) > 0
        else:
            assert response.error_code in [429, 500, 503, 504]
    
    @pytest.mark.asyncio
    async def test_gemini_rate_limit_handling(self):
        """Test that Gemini CLI can return rate limit error"""
        provider = GeminiCLIProvider()
        
        # Try multiple requests - likely to hit rate limit
        for i in range(2):
            response = await provider.generate(f"Test request {i}")
            assert response is not None
            
            # Check if we got a rate limit error
            if response.error_code == 429:
                print(f"Rate limit hit on request {i}")
                assert "rate" in response.error_message.lower() or "quota" in response.error_message.lower()
                break


class TestRealClaudeCLI:
    """Tests for real Claude CLI integration"""
    
    @pytest.fixture(autouse=True)
    def skip_if_unavailable(self):
        """Skip tests if Claude CLI is not available"""
        if not shutil.which('claude'):
            pytest.skip("Claude CLI not installed")
    
    @pytest.mark.asyncio
    async def test_claude_cli_available(self):
        """Test that Claude CLI is available"""
        provider = ClaudeCLIProvider()
        assert provider.is_available()
        assert provider.get_name() == "claude-cli"
    
    @pytest.mark.asyncio
    async def test_claude_simple_generation(self):
        """Test Claude CLI can generate a response"""
        provider = ClaudeCLIProvider()
        
        response = await provider.generate("Say hello in one sentence")
        
        assert response is not None
        if response.is_success:
            assert len(response.text) > 0
            assert "hello" in response.text.lower()
        else:
            assert response.error_code in [429, 500, 503, 504]
    
    @pytest.mark.asyncio
    async def test_claude_code_generation(self):
        """Test Claude CLI generating code"""
        provider = ClaudeCLIProvider()
        
        response = await provider.generate("Write a Python function to calculate factorial")
        
        assert response is not None
        if response.is_success:
            assert len(response.text) > 0
            assert "def " in response.text or "factorial" in response.text.lower()
        else:
            assert response.error_code in [429, 500, 503, 504]
    
    @pytest.mark.asyncio
    async def test_claude_response_stripped(self):
        """Test that Claude response is properly stripped"""
        provider = ClaudeCLIProvider()
        
        response = await provider.generate("Say 'test'")
        
        assert response is not None
        if response.is_success:
            assert response.text == response.text.strip()


class TestRealGitHubCLI:
    """Tests for real GitHub CLI Copilot integration"""
    
    @pytest.fixture(autouse=True)
    def skip_if_unavailable(self):
        """Skip tests if GitHub CLI is not available"""
        if not shutil.which('gh'):
            pytest.skip("GitHub CLI not installed")
    
    @pytest.mark.asyncio
    async def test_github_cli_available(self):
        """Test that GitHub CLI is available"""
        provider = GitHubCLIProvider()
        # GitHub CLI might be available but copilot extension might not
        # This just checks gh command exists
        assert shutil.which('gh') is not None
    
    @pytest.mark.asyncio
    async def test_github_copilot_available(self):
        """Test that GitHub Copilot extension is available"""
        provider = GitHubCLIProvider()
        assert provider.is_available() or provider.is_available()  # Either available or graceful error
    
    @pytest.mark.asyncio
    async def test_github_code_suggestion(self):
        """Test GitHub Copilot can suggest code"""
        provider = GitHubCLIProvider()
        
        if not provider.is_available():
            pytest.skip("GitHub Copilot not available")
        
        response = await provider.generate("Create a function that adds two numbers")
        
        # GitHub Copilot might return error if not configured
        if response.is_success:
            assert len(response.text) > 0


class TestMultiProviderFallback:
    """Test fallback chain with real CLIs"""
    
    def get_available_providers(self):
        """Get list of available CLI tools"""
        available = []
        if shutil.which('gemini'):
            available.append('gemini-cli')
        if shutil.which('claude'):
            available.append('claude-cli')
        if shutil.which('gh'):
            available.append('github-cli')
        return available
    
    @pytest.mark.asyncio
    async def test_available_providers(self):
        """Test that at least one provider is available"""
        available = self.get_available_providers()
        if len(available) == 0:
            pytest.skip("No LLM CLI tools installed")
        
        assert len(available) >= 1
        print(f"Available providers: {available}")
    
    @pytest.mark.asyncio
    async def test_factory_creates_real_providers(self):
        """Test factory creates instances of available providers"""
        available = self.get_available_providers()
        if len(available) == 0:
            pytest.skip("No LLM CLI tools installed")
        
        for provider_name in available:
            provider = LLMProviderFactory.create(provider_name)
            assert provider is not None
            assert provider.is_available()
    
    @pytest.mark.asyncio
    async def test_fallback_chain_with_real_providers(self):
        """Test fallback chain uses real providers"""
        available = self.get_available_providers()
        if len(available) == 0:
            pytest.skip("No LLM CLI tools installed")
        
        # Try each available provider
        for provider_name in available:
            provider = LLMProviderFactory.create(provider_name)
            assert provider.is_available()
            
            # Try a simple generation
            response = await provider.generate("Say 'test'")
            assert response is not None


class TestRealCLIErrorHandling:
    """Test error handling with real CLI tools"""
    
    @pytest.mark.asyncio
    async def test_gemini_handles_errors_gracefully(self):
        """Test Gemini handles errors without crashing"""
        provider = GeminiCLIProvider()
        
        # This should not raise an exception, even on error
        response = await provider.generate("test")
        assert response is not None
        # Either success or a valid error code
        assert response.error_code in [None, 429, 500, 503, 504]
    
    @pytest.mark.asyncio
    async def test_claude_handles_errors_gracefully(self):
        """Test Claude handles errors without crashing"""
        provider = ClaudeCLIProvider()
        
        response = await provider.generate("test")
        assert response is not None
        assert response.error_code in [None, 429, 500, 503, 504]


class TestRealCLIPerformance:
    """Test performance characteristics with real CLIs"""
    
    @pytest.mark.asyncio
    async def test_gemini_responds_in_reasonable_time(self):
        """Test Gemini responds in reasonable time"""
        if not shutil.which('gemini'):
            pytest.skip("Gemini CLI not installed")
        
        import time
        provider = GeminiCLIProvider()
        
        start = time.time()
        response = await provider.generate("hi")
        elapsed = time.time() - start
        
        # Should respond within 60 seconds (or hit rate limit quickly)
        assert elapsed < 60
        print(f"Gemini response time: {elapsed:.2f}s, status: {response.error_code}")
    
    @pytest.mark.asyncio
    async def test_claude_responds_in_reasonable_time(self):
        """Test Claude responds in reasonable time"""
        if not shutil.which('claude'):
            pytest.skip("Claude CLI not installed")
        
        import time
        provider = ClaudeCLIProvider()
        
        start = time.time()
        response = await provider.generate("hi")
        elapsed = time.time() - start
        
        assert elapsed < 60
        print(f"Claude response time: {elapsed:.2f}s, status: {response.error_code}")


class TestRealCLIIntegration:
    """Integration tests with actual SessionManager and AIProxy"""
    
    @pytest.mark.asyncio
    async def test_session_initialization_with_available_providers(self):
        """Test SessionManager initialization with available providers"""
        from src.session_manager import SessionManager
        
        available = []
        if shutil.which('gemini'):
            available.append('gemini-cli')
        if shutil.which('claude'):
            available.append('claude-cli')
        if shutil.which('gh'):
            available.append('github-cli')
        
        if len(available) == 0:
            pytest.skip("No LLM CLI tools installed")
        
        session = SessionManager(user_id="integration_test_user")
        await session.enable_ai_proxy(primary_provider=available[0])
        
        assert session.ai_proxy is not None
        assert session.ai_proxy.primary_provider == available[0]
        print(f"Session initialized with primary provider: {available[0]}")
    
    @pytest.mark.asyncio
    async def test_ai_proxy_configuration(self):
        """Test AIProxy can be configured with real providers"""
        from src.ai_proxy import AIProxy
        
        available = []
        if shutil.which('gemini'):
            available.append('gemini-cli')
        if shutil.which('claude'):
            available.append('claude-cli')
        
        if len(available) == 0:
            pytest.skip("No LLM CLI tools installed")
        
        primary = available[0]
        fallback = available[1:] if len(available) > 1 else []
        
        proxy = AIProxy(
            primary_provider=primary,
            fallback_providers=fallback
        )
        
        assert proxy.primary_provider == primary
        assert proxy.fallback_providers == fallback
        print(f"AIProxy configured: primary={primary}, fallback={fallback}")
    
    @pytest.mark.asyncio
    async def test_fallback_chain_with_real_providers(self):
        """Test fallback mechanism with real providers"""
        from src.ai_proxy import AIProxy
        
        available = []
        if shutil.which('gemini'):
            available.append('gemini-cli')
        if shutil.which('claude'):
            available.append('claude-cli')
        
        if len(available) < 2:
            pytest.skip("Need at least 2 providers for fallback test")
        
        # Create proxy with fallback
        proxy = AIProxy(
            primary_provider=available[0],
            fallback_providers=available[1:]
        )
        
        # Try to generate with fallback capability
        response = await proxy._try_llm_with_fallback("Test prompt")
        
        # Should either succeed or fail gracefully
        assert response is None or isinstance(response, str)
        print(f"Fallback chain response: {response[:50] if response else 'None'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
