"""Tests for terminal module"""
import pytest
import asyncio
from src import terminal
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


@pytest.mark.asyncio
async def test_terminal_session_send_command_uses_running_loop(monkeypatch):
    """send_command should rely on the active loop inside async code."""
    session = TerminalSession("test-session")
    await session.start()
    monkeypatch.setattr("src.terminal.asyncio.get_event_loop", lambda: (_ for _ in ()).throw(AssertionError("deprecated loop lookup")))  # noqa: E731

    try:
        output = await session.send_command("echo hello")
        assert "hello" in output
    finally:
        await session.stop()


def test_append_incremental_output_skips_join_when_no_new_chunks(monkeypatch):
    """Incremental output helper should not rebuild the buffer when nothing new arrived."""
    monkeypatch.setattr(
        terminal,
        "_join_output_chunks",
        lambda chunks: (_ for _ in ()).throw(AssertionError("join should not be called")),  # noqa: E731
    )

    assert terminal._append_incremental_output("existing output", []) == "existing output"


# TODO: Add tests for:
# - test_terminal_session_is_responsive()
# - test_terminal_session_context_manager()
# - test_terminal_session_timeout()
# - test_terminal_encoding()
