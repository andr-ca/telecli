"""
Provider-specific unit tests for Gemini and GitHub CLI providers
"""
import pytest
from unittest.mock import patch, AsyncMock
from src.gemini_provider import GeminiCLIProvider
from src.github_provider import GitHubCLIProvider
from src.llm_provider import LLMResponse


class TestGeminiProviderUnit:
    """Unit tests for Gemini CLI provider"""
    
    def test_gemini_init_with_available_cli(self):
        """Test Gemini initialization when CLI is available"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            provider = GeminiCLIProvider()
            assert provider.cli_path == '/usr/bin/gemini'
            assert provider.is_available()
    
    def test_gemini_init_without_cli(self):
        """Test Gemini initialization when CLI is not available"""
        with patch('shutil.which', return_value=None):
            provider = GeminiCLIProvider()
            assert provider.cli_path is None
            assert not provider.is_available()
    
    def test_gemini_get_name(self):
        """Test Gemini provider name"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            provider = GeminiCLIProvider()
            assert provider.get_name() == "gemini-cli"
    
    @pytest.mark.asyncio
    async def test_gemini_unavailable_provider_error(self):
        """Test Gemini generate when provider unavailable"""
        with patch('shutil.which', return_value=None):
            provider = GeminiCLIProvider()
            response = await provider.generate("test")
            
            assert not response.is_success
            assert response.error_code == 503
            assert "not available" in response.error_message.lower()


class TestGitHubProviderUnit:
    """Unit tests for GitHub CLI provider"""
    
    def test_github_init_with_available_cli(self):
        """Test GitHub initialization when CLI is available"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            provider = GitHubCLIProvider()
            assert provider.cli_path == '/usr/bin/gh'
            assert provider.is_available()
    
    def test_github_init_without_cli(self):
        """Test GitHub initialization when CLI is not available"""
        with patch('shutil.which', return_value=None):
            provider = GitHubCLIProvider()
            assert provider.cli_path is None
            assert not provider.is_available()
    
    def test_github_get_name(self):
        """Test GitHub provider name"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            provider = GitHubCLIProvider()
            assert provider.get_name() == "github-cli"
    
    @pytest.mark.asyncio
    async def test_github_unavailable_provider_error(self):
        """Test GitHub generate when provider unavailable"""
        with patch('shutil.which', return_value=None):
            provider = GitHubCLIProvider()
            response = await provider.generate("test")
            
            assert not response.is_success
            assert response.error_code == 503
            assert "not available" in response.error_message.lower()


class TestProviderErrorHandling:
    """Test error handling in providers"""
    
    @pytest.mark.asyncio
    async def test_gemini_rate_limit_detection(self):
        """Test Gemini detects rate limit errors"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock subprocess that fails with rate limit
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'429 Too Many Requests')
                mock_proc.returncode = 1
                mock_exec.return_value = mock_proc
                
                provider = GeminiCLIProvider()
                response = await provider.generate("test prompt")
                
                assert response.error_code == 429
    
    @pytest.mark.asyncio
    async def test_github_rate_limit_detection(self):
        """Test GitHub detects rate limit errors"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock subprocess that fails with rate limit
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'rate limit exceeded')
                mock_proc.returncode = 1
                mock_exec.return_value = mock_proc
                
                provider = GitHubCLIProvider()
                response = await provider.generate("test prompt")
                
                assert response.error_code == 429
    
    @pytest.mark.asyncio
    async def test_gemini_timeout_error(self):
        """Test Gemini handles timeout errors"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock subprocess that times out
                mock_proc = AsyncMock()
                mock_proc.communicate.side_effect = TimeoutError()
                mock_exec.return_value = mock_proc
                
                provider = GeminiCLIProvider()
                response = await provider.generate("test prompt")
                
                assert response.error_code == 504
                assert "timeout" in response.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_github_exception_handling(self):
        """Test GitHub handles general exceptions"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock subprocess that raises exception
                mock_exec.side_effect = RuntimeError("Command failed")
                
                provider = GitHubCLIProvider()
                response = await provider.generate("test prompt")
                
                assert response.error_code == 500
                assert "Command failed" in response.error_message


class TestProviderCommandConstruction:
    """Test command construction for providers"""
    
    @pytest.mark.asyncio
    async def test_gemini_command_with_system_prompt(self):
        """Test Gemini constructs correct command"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'response text', b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                provider = GeminiCLIProvider()
                await provider.generate("user prompt", "system prompt")
                
                # Verify command was called with correct arguments
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args
                # In create_subprocess_exec, arguments are passed as separate parameters
                args = call_args[0]  # Tuple of positional arguments
                
                # First arg is the command
                assert '/usr/bin/gemini' == args[0]
                # Check that --output-format and text are in the arguments
                args_str = ' '.join(args)
                assert '--output-format' in args_str
                assert 'text' in args_str
    
    @pytest.mark.asyncio
    async def test_github_command_structure(self):
        """Test GitHub constructs correct command"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'response text', b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                provider = GitHubCLIProvider()
                await provider.generate("test prompt")
                
                # Verify command was called
                mock_exec.assert_called_once()
                call_args = mock_exec.call_args
                # In create_subprocess_exec, arguments are passed as separate parameters
                args = call_args[0]  # Tuple of positional arguments
                
                # First arg is the command
                assert '/usr/bin/gh' == args[0]
                # Check that copilot and suggest are in the arguments
                args_str = ' '.join(args)
                assert 'copilot' in args_str
                assert 'suggest' in args_str


class TestProviderResponseProcessing:
    """Test response processing in providers"""
    
    @pytest.mark.asyncio
    async def test_gemini_response_stripping(self):
        """Test Gemini strips whitespace from response"""
        with patch('shutil.which', return_value='/usr/bin/gemini'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock response with extra whitespace
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'  response text  \n', b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                provider = GeminiCLIProvider()
                response = await provider.generate("test")
                
                assert response.text == "response text"
                assert not response.text.startswith(' ')
                assert not response.text.endswith(' ')
    
    @pytest.mark.asyncio
    async def test_github_response_decoding(self):
        """Test GitHub properly decodes response bytes"""
        with patch('shutil.which', return_value='/usr/bin/gh'):
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                # Mock response as bytes
                response_text = "Suggested command: ls -la"
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (response_text.encode('utf-8'), b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                provider = GitHubCLIProvider()
                response = await provider.generate("list files")
                
                assert response.text == response_text
                assert isinstance(response.text, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
