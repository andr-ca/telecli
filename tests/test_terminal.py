"""Tests for terminal module"""
import pytest
import asyncio
from src.terminal import TerminalSession


@pytest.mark.asyncio
async def test_terminal_session_creation():
    """Test creating a terminal session"""
    session = TerminalSession("test-session")
    assert session.session_id == "test-session"
    assert not session.is_active


@pytest.mark.asyncio
async def test_terminal_session_start():
    """Test starting a terminal session"""
    session = TerminalSession("test-session")
    success = await session.start()
    assert success
    assert session.is_active
    await session.stop()
    assert not session.is_active


@pytest.mark.asyncio
async def test_terminal_session_send_command():
    """Test sending a command"""
    session = TerminalSession("test-session")
    await session.start()
    
    try:
        output = await session.send_command("echo hello")
        assert "hello" in output
    finally:
        await session.stop()


# TODO: Add tests for:
# - test_terminal_session_is_responsive()
# - test_terminal_session_context_manager()
# - test_terminal_session_timeout()
# - test_terminal_encoding()
