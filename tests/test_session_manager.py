"""Tests for session manager"""
import json
import pytest
from src.session_manager import SessionManager


@pytest.mark.asyncio
async def test_session_manager_creation():
    """Test creating a session manager"""
    manager = SessionManager()
    assert manager.max_sessions == 100
    assert len(manager.sessions) == 0


@pytest.mark.asyncio
async def test_session_manager_get_session():
    """Test getting a session"""
    manager = SessionManager()
    session = await manager.get_session("test-user")
    assert session is not None
    assert session.is_active
    await manager.close_session("test-user")


@pytest.mark.asyncio
async def test_session_manager_stats():
    """Test getting statistics"""
    manager = SessionManager()
    stats = manager.get_stats()
    assert "active_sessions" in stats
    assert "max_sessions" in stats
    assert "total_created" in stats


@pytest.mark.asyncio
async def test_session_manager_rename_active_telecli_session():
    """Active TeleCLI sessions should expose a user-defined name in the session list."""
    manager = SessionManager()
    await manager.get_session("test-user")

    manager.rename_session("test-user", "Dev Shell")
    sessions = manager.list_sessions()

    assert any(
        session["id"] == "test-user"
        and session["name"] == "Dev Shell"
        and session["backend"] == "telecli"
        for session in sessions
    )

    await manager.close_session("test-user")


def test_session_manager_import_tmux_session_persists_named_entry(tmp_path, monkeypatch):
    """Imported tmux sessions should persist as named TeleCLI entries."""
    registry_path = tmp_path / "tmux-session-registry.json"
    manager = SessionManager(registry_path=registry_path)
    monkeypatch.setattr(
        manager,
        "list_machine_tmux_sessions",
        lambda: [{"name": "build-shell", "windows": 2, "attached": False}],
    )

    session = manager.import_tmux_session("build-shell", name="Build Shell")

    assert session["name"] == "Build Shell"
    assert session["backend"] == "tmux"
    assert session["tmux_session_name"] == "build-shell"

    saved = json.loads(registry_path.read_text())
    assert saved["sessions"][0]["tmux_session_name"] == "build-shell"
    assert saved["sessions"][0]["name"] == "Build Shell"

    reloaded_manager = SessionManager(registry_path=registry_path)
    monkeypatch.setattr(
        reloaded_manager,
        "list_machine_tmux_sessions",
        lambda: [{"name": "build-shell", "windows": 2, "attached": False}],
    )
    sessions = reloaded_manager.list_sessions()

    assert any(
        session["name"] == "Build Shell"
        and session["backend"] == "tmux"
        and session["tmux_session_name"] == "build-shell"
        for session in sessions
    )


def test_session_manager_create_tmux_session_persists_named_entry(tmp_path, monkeypatch):
    """Creating a tmux session should create the machine session and persist its TeleCLI entry."""
    registry_path = tmp_path / "tmux-session-registry.json"
    manager = SessionManager(registry_path=registry_path)
    created_tmux_sessions = []

    monkeypatch.setattr(
        "src.session_manager.create_tmux_session",
        lambda name: created_tmux_sessions.append(name),
    )

    session = manager.create_tmux_session_entry("pairing-shell")

    assert created_tmux_sessions == ["pairing-shell"]
    assert session["name"] == "pairing-shell"
    assert session["backend"] == "tmux"
    assert session["tmux_session_name"] == "pairing-shell"

    saved = json.loads(registry_path.read_text())
    assert saved["sessions"][0]["tmux_session_name"] == "pairing-shell"


def test_session_manager_uses_configured_registry_path(monkeypatch, tmp_path):
    """Default registry storage should come from Config when no explicit path is passed."""
    configured_path = tmp_path / "custom-registry.json"
    monkeypatch.setattr("src.session_manager.Config.SESSION_REGISTRY_PATH", str(configured_path))

    manager = SessionManager()

    assert manager.registry_path == configured_path


def test_session_manager_lists_inactive_named_telecli_entries():
    """Named TeleCLI entries should appear in the session list before their runtime is started."""
    manager = SessionManager()

    created = manager.create_session_entry("Inbox Shell")
    sessions = manager.list_sessions()

    assert any(
        session["id"] == created["id"]
        and session["name"] == "Inbox Shell"
        and session["backend"] == "telecli"
        and session["is_active"] is False
        for session in sessions
    )


@pytest.mark.asyncio
async def test_session_manager_detach_tmux_session_keeps_imported_entry(tmp_path, monkeypatch):
    """Detaching a tmux session should stop its runtime but keep the imported record."""
    registry_path = tmp_path / "tmux-session-registry.json"
    manager = SessionManager(registry_path=registry_path)
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: name == "ops-shell")
    session = manager._ensure_record(  # noqa: SLF001 - exercising existing manager state path
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    class FakeRuntimeSession:
        def __init__(self):
            self.is_active = True
            self.shell = "tmux:ops-shell"
            self.stop_calls = 0

        async def stop(self):
            self.stop_calls += 1
            self.is_active = False

    runtime = FakeRuntimeSession()
    manager.sessions[session.session_id] = runtime

    detached = await manager.detach_tmux_session(session.session_id)

    assert runtime.stop_calls == 1
    assert detached["id"] == session.session_id
    assert detached["backend"] == "tmux"
    assert detached["is_active"] is False
    assert detached["available"] is True
    assert session.session_id in manager.session_records
    assert session.session_id not in manager.sessions


# TODO: Add tests for:
# - test_session_manager_max_sessions_limit()
# - test_session_manager_send_command()
# - test_session_manager_close_all()
# - test_session_manager_responsiveness_check()
