"""Tests for terminal module"""
import asyncio
import pytest
from src import terminal
from src.terminal import TerminalSession, TmuxSession


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


@pytest.mark.asyncio
async def test_terminal_session_send_command_uses_less_aggressive_poll_interval(monkeypatch):
    """send_command should avoid a 100Hz polling loop while waiting for output."""
    session = TerminalSession("test-session")
    current_time = {"value": 0.0}
    sleep_calls = []

    class FakeLoop:
        def time(self):
            return current_time["value"]

    async def fake_send_input(text: str):
        return None

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)
        current_time["value"] += delay

    monkeypatch.setattr(session, "send_input", fake_send_input)
    monkeypatch.setattr("src.terminal.asyncio.get_running_loop", lambda: FakeLoop())
    monkeypatch.setattr("src.terminal.asyncio.sleep", fake_sleep)

    with pytest.raises(TimeoutError):
        await session.send_command("echo hello", timeout=0.12)

    assert sleep_calls
    assert sleep_calls[0] == 0.05


@pytest.mark.asyncio
async def test_terminal_session_send_input_logs_metadata_not_raw_text(caplog):
    """INFO-level terminal input logs should avoid raw command text."""
    session = TerminalSession("test-session")

    class FakeProcess:
        def sendline(self, text: str):
            return None

    session.process = FakeProcess()
    session.is_active = True

    secret = "sk-terminal-secret"
    with caplog.at_level("INFO"):
        await session.send_input(secret)

    assert secret not in caplog.text
    assert "len=" in caplog.text


@pytest.mark.asyncio
async def test_terminal_session_send_exact_input_logs_metadata_not_raw_text(caplog):
    """DEBUG-level exact-input logs should also avoid raw command text."""
    session = TerminalSession("test-session")

    class FakeProcess:
        def send(self, text: str):
            return None

    session.process = FakeProcess()
    session.is_active = True

    secret = "sk-exact-terminal-secret"
    with caplog.at_level("DEBUG"):
        await session.send_input(secret, newline=False)

    assert secret not in caplog.text
    assert "len=" in caplog.text


@pytest.mark.asyncio
async def test_tmux_session_start_uses_initial_dimensions(monkeypatch):
    """tmux-backed sessions should attach using the browser's initial terminal size."""
    spawned = {}

    class FakeSpawn:
        def __init__(self, command, args, **kwargs):
            spawned["command"] = command
            spawned["args"] = args
            spawned["kwargs"] = kwargs
            self.setwinsize_calls = []

        def setwinsize(self, rows: int, cols: int):
            self.setwinsize_calls.append((rows, cols))

    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(terminal.pexpect, "spawn", FakeSpawn)

    session = TmuxSession("tmux-session-1", "ops-shell", initial_rows=48, initial_cols=160)
    session._read_loop = lambda: asyncio.sleep(0)  # noqa: SLF001 - replace background loop for deterministic start

    success = await session.start()

    assert success is True
    assert spawned["command"] == "/usr/bin/tmux"
    assert spawned["args"] == ["attach-session", "-f", "ignore-size", "-t", "ops-shell"]
    assert spawned["kwargs"]["dimensions"] == (48, 160)
    assert session.process.setwinsize_calls == [(48, 160)]


@pytest.mark.asyncio
async def test_terminal_resize_uses_sanitized_dimensions():
    """Resize should clamp and pass sanitized dimensions to the PTY."""
    session = TerminalSession("test-session")

    class FakeProcess:
        def __init__(self):
            self.setwinsize_calls = []

        def setwinsize(self, rows: int, cols: int):
            self.setwinsize_calls.append((rows, cols))

    session.process = FakeProcess()
    session.is_active = True

    await session.resize("0", "12")

    assert session.initial_rows == 1
    assert session.initial_cols == 12
    assert session.process.setwinsize_calls == [(1, 12)]


# TODO: Add tests for:
# - test_terminal_session_is_responsive()
# - test_terminal_session_context_manager()
# - test_terminal_session_timeout()
# - test_terminal_encoding()
