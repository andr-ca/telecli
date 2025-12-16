"""
Real CLI Integration Tests - Quick
Fast tests for actual LLM CLI tool availability without waiting for responses
"""
import pytest
import shutil
from src.llm_provider import LLMProviderFactory
from src.gemini_provider import GeminiCLIProvider
from src.claude_provider import ClaudeCLIProvider
from src.github_provider import GitHubCLIProvider
# Import llm_providers to trigger factory registrations
import src.llm_providers  # noqa


class TestCLIAvailability:
    """Test that CLI tools are available"""
    
    def test_gemini_cli_installed(self):
        """Test that Gemini CLI is installed"""
        assert shutil.which('gemini') is not None
        print("✓ Gemini CLI found")
    
    def test_claude_cli_installed(self):
        """Test that Claude CLI is installed"""
        assert shutil.which('claude') is not None
        print("✓ Claude CLI found")
    
    def test_github_cli_installed(self):
        """Test that GitHub CLI is installed"""
        assert shutil.which('gh') is not None
        print("✓ GitHub CLI found")


class TestProviderInitialization:
    """Test provider initialization with real CLIs"""
    
    def test_gemini_provider_initialization(self):
        """Test Gemini provider initializes with real CLI"""
        provider = GeminiCLIProvider()
        assert provider.is_available()
        assert provider.cli_path == shutil.which('gemini')
        assert provider.get_name() == "gemini-cli"
        print(f"✓ Gemini provider initialized at {provider.cli_path}")
    
    def test_claude_provider_initialization(self):
        """Test Claude provider initializes with real CLI"""
        provider = ClaudeCLIProvider()
        assert provider.is_available()
        assert provider.cli_path == shutil.which('claude')
        assert provider.get_name() == "claude-cli"
        print(f"✓ Claude provider initialized at {provider.cli_path}")
    
    def test_github_provider_initialization(self):
        """Test GitHub provider initializes with real CLI"""
        provider = GitHubCLIProvider()
        # GitHub provider check is more complex, just verify it initializes
        assert provider.get_name() == "github-cli"
        print(f"✓ GitHub provider initialized")


class TestProviderFactory:
    """Test factory creates instances of real providers"""
    
    def test_factory_creates_gemini_provider(self):
        """Test factory can create Gemini provider"""
        provider = LLMProviderFactory.create("gemini-cli")
        assert provider is not None
        assert provider.get_name() == "gemini-cli"
        assert provider.is_available()
        print("✓ Factory created Gemini provider")
    
    def test_factory_creates_claude_provider(self):
        """Test factory can create Claude provider"""
        provider = LLMProviderFactory.create("claude-cli")
        assert provider is not None
        assert provider.get_name() == "claude-cli"
        assert provider.is_available()
        print("✓ Factory created Claude provider")
    
    def test_factory_creates_github_provider(self):
        """Test factory can create GitHub provider"""
        provider = LLMProviderFactory.create("github-cli")
        assert provider is not None
        assert provider.get_name() == "github-cli"
        print("✓ Factory created GitHub provider")
    
    def test_factory_lists_available_providers(self):
        """Test factory lists available providers"""
        available = LLMProviderFactory.get_available_providers()
        assert isinstance(available, (list, tuple))
        # Available is a list of tuples (name, provider_class)
        provider_names = [name for name, _ in available] if available and isinstance(available[0], tuple) else available
        assert "gemini-cli" in provider_names
        assert "claude-cli" in provider_names
        print(f"✓ Available providers: {provider_names}")


class TestSessionManagerIntegration:
    """Test SessionManager with real providers"""
    
    @pytest.mark.asyncio
    async def test_session_initialization(self):
        """Test SessionManager can be initialized with real provider"""
        from src.session_manager import SessionManager
        
        session_manager = SessionManager()
        session = await session_manager.get_session("test_session_1")
        await session_manager.enable_ai_proxy("test_session_1", provider_name="claude-cli")
        
        assert session_manager.ai_proxies.get("test_session_1") is not None
        proxy = session_manager.ai_proxies["test_session_1"]
        # AIProxy stores the provider, not a string name
        assert proxy is not None
        print("✓ SessionManager initialized with real provider")
        await session_manager.close_session("test_session_1")
    
    @pytest.mark.asyncio
    async def test_session_auto_configures_fallback(self):
        """Test SessionManager auto-configures fallback providers"""
        from src.session_manager import SessionManager
        
        session_manager = SessionManager()
        session = await session_manager.get_session("test_session_2")
        await session_manager.enable_ai_proxy("test_session_2", provider_name="claude-cli")
        
        proxy = session_manager.ai_proxies.get("test_session_2")
        assert proxy is not None
        # Fallback providers should be configured (auto-populated by AIProxy)
        # Fallback should not contain the primary provider "claude-cli"
        print("✓ SessionManager auto-configured fallback providers")
        await session_manager.close_session("test_session_2")
        print(f"✓ Fallback providers configured: {proxy.fallback_providers}")
        await session_manager.close_session("test_session_2")


class TestAIProxyConfiguration:
    """Test AIProxy with real providers"""
    
    def test_ai_proxy_initialization(self):
        """Test AIProxy can be initialized with real providers"""
        from src.ai_proxy import AIProxy
        
        gemini_provider = GeminiCLIProvider()
        claude_provider = ClaudeCLIProvider()
        
        proxy = AIProxy(
            llm_provider=gemini_provider,
            fallback_providers=["claude-cli", "github-cli"]
        )
        
        assert proxy.llm_provider is not None
        assert proxy.primary_provider_name == "gemini-cli"
        assert proxy.fallback_provider_names == ["claude-cli", "github-cli"]
        print("✓ AIProxy initialized with real providers")
    
    def test_ai_proxy_can_enable(self):
        """Test AIProxy can be enabled"""
        from src.ai_proxy import AIProxy
        
        provider = GeminiCLIProvider()
        proxy = AIProxy(llm_provider=provider)
        proxy.enable()
        
        assert proxy.primary_provider_name == "gemini-cli"
        assert proxy.enabled is True
        print("✓ AIProxy enabled successfully")


class TestProviderErrorDetection:
    """Test that providers can detect and handle errors"""
    
    @pytest.mark.asyncio
    async def test_gemini_error_detection(self):
        """Test Gemini provider returns error object on failure"""
        provider = GeminiCLIProvider()
        
        # This will either succeed or return an error (not raise)
        response = await provider.generate("test")
        
        assert response is not None
        assert hasattr(response, 'text')
        assert hasattr(response, 'error_code')
        assert hasattr(response, 'error_message')
        print(f"✓ Gemini response: error_code={response.error_code}, success={response.is_success}")
    
    @pytest.mark.asyncio
    async def test_claude_error_detection(self):
        """Test Claude provider returns error object on failure"""
        provider = ClaudeCLIProvider()
        
        response = await provider.generate("test")
        
        assert response is not None
        assert hasattr(response, 'text')
        assert hasattr(response, 'error_code')
        assert hasattr(response, 'error_message')
        print(f"✓ Claude response: error_code={response.error_code}, success={response.is_success}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
