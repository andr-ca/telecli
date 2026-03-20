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


@pytest.mark.asyncio
async def test_enable_ai_proxy_creates_missing_session_record(monkeypatch):
    """AI proxy enable should succeed before the runtime session has been created."""
    manager = SessionManager()

    class FakeProvider:
        def get_name(self):
            return "fake-provider"

    monkeypatch.setattr(
        "src.session_manager.LLMProviderFactory.create",
        lambda provider_name: FakeProvider(),
    )
    monkeypatch.setattr(
        "src.session_manager.LLMProviderFactory.get_available_providers",
        lambda: [("fake-provider", FakeProvider()), ("fallback-provider", FakeProvider())],
    )

    enabled = await manager.enable_ai_proxy("fresh-session", provider_name="fake-provider")

    assert enabled is True
    assert "fresh-session" in manager.session_records
    assert "fresh-session" in manager.ai_proxies
    assert manager.sessions == {}


def test_session_manager_reports_agent_mode_capabilities_for_tmux_record(tmp_path, monkeypatch):
    """tmux-backed records should advertise agent-mode support."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: True)
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    capabilities = manager.get_session_mode_capabilities("tmux-session-1")

    assert capabilities == {
        "backend": "tmux",
        "supports_agent_mode": True,
        "tmux_session_name": "ops-shell",
    }


def test_session_manager_caches_tmux_capability_checks(tmp_path, monkeypatch):
    """Repeated capability checks should avoid re-probing tmux within the cache window."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )
    calls = []
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: calls.append(name) or True)

    first = manager.get_session_mode_capabilities("tmux-session-1")
    second = manager.get_session_mode_capabilities("tmux-session-1")

    assert first["supports_agent_mode"] is True
    assert second["supports_agent_mode"] is True
    assert calls == ["ops-shell"]


def test_session_manager_reports_no_agent_mode_support_for_unavailable_tmux_session(tmp_path, monkeypatch):
    """tmux-backed records should stop advertising agent mode when the backing tmux session is gone."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: False)
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    capabilities = manager.get_session_mode_capabilities("tmux-session-1")

    assert capabilities == {
        "backend": "tmux",
        "supports_agent_mode": False,
        "tmux_session_name": "ops-shell",
    }


def test_session_manager_reports_no_agent_mode_support_for_telecli_session():
    """Regular TeleCLI sessions should not advertise tmux-only agent mode support."""
    manager = SessionManager()
    created = manager.create_session_entry("build")

    capabilities = manager.get_session_mode_capabilities(created["id"])

    assert capabilities == {
        "backend": "telecli",
        "supports_agent_mode": False,
        "tmux_session_name": None,
    }


def test_session_manager_delegates_agent_mode_recommendation_for_tmux(tmp_path, monkeypatch):
    """tmux-backed sessions should delegate recommendation details to tmux helpers."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: True)
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )
    monkeypatch.setattr(
        "src.session_manager.get_tmux_interaction_recommendation",
        lambda name: {
            "supports_agent_mode": True,
            "should_suggest_agent_mode": True,
            "reason": "codex",
            "signature": "ops-shell:%1:codex:1",
            "pane": {"pane_id": "%1"},
        },
    )

    recommendation = manager.get_agent_mode_recommendation("tmux-session-1")

    assert recommendation["should_suggest_agent_mode"] is True
    assert recommendation["reason"] == "codex"
    assert recommendation["signature"] == "ops-shell:%1:codex:1"


def test_session_manager_does_not_recommend_agent_mode_for_unavailable_tmux(tmp_path, monkeypatch):
    """Unavailable tmux-backed sessions should not produce agent-mode suggestions."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: False)
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    recommendation = manager.get_agent_mode_recommendation("tmux-session-1")

    assert recommendation == {
        "supports_agent_mode": False,
        "should_suggest_agent_mode": False,
        "reason": "Session is not tmux-backed or backing tmux session is unavailable",
        "signature": None,
    }


def test_session_manager_rejects_snapshot_for_non_tmux_session():
    """Snapshot capture should reject sessions that are not tmux-backed."""
    manager = SessionManager()
    created = manager.create_session_entry("build")

    with pytest.raises(ValueError, match="tmux-backed"):
        manager.capture_session_snapshot(created["id"])


def test_session_manager_captures_and_tails_tmux_session_output(tmp_path, monkeypatch):
    """Snapshot and tail helpers should delegate to the tmux capture helper."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )
    monkeypatch.setattr(
        "src.session_manager.capture_tmux_pane",
        lambda name, lines=80: "line 1\nline 2\nline 3\nline 4\n",
    )

    snapshot = manager.capture_session_snapshot("tmux-session-1", lines=80)
    tail = manager.tail_session_output("tmux-session-1", lines=2)

    assert snapshot == "line 1\nline 2\nline 3\nline 4\n"
    assert tail == "line 3\nline 4"


def test_session_manager_captures_visible_tmux_screen(tmp_path, monkeypatch):
    """Screen capture should delegate to the tmux visible-pane helper."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )
    monkeypatch.setattr(
        "src.session_manager.capture_tmux_screen",
        lambda name: "screen line 1\nscreen line 2\n",
    )

    screen = manager.capture_session_screen("tmux-session-1")

    assert screen == "screen line 1\nscreen line 2\n"


@pytest.mark.asyncio
async def test_session_manager_send_exact_input_uses_non_newline_send(monkeypatch):
    """Exact input should preserve raw text by disabling newline insertion."""
    manager = SessionManager()
    calls = []

    async def fake_send_input(session_id: str, text: str, newline: bool = True, from_ai: bool = False):
        calls.append((session_id, text, newline, from_ai))

    monkeypatch.setattr(manager, "send_input", fake_send_input)

    await manager.send_exact_input("web-1", "continue")

    assert calls == [("web-1", "continue", False, False)]


@pytest.mark.asyncio
async def test_session_manager_send_special_key_async_uses_worker_thread(monkeypatch):
    """Async key sending should offload the blocking tmux call to a worker thread."""
    manager = SessionManager()
    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return None

    monkeypatch.setattr("src.session_manager.asyncio.to_thread", fake_to_thread)

    await manager.send_special_key_async("tmux-session-1", "enter")

    assert calls == [("send_special_key", ("tmux-session-1", "enter"), {})]


def test_session_manager_send_special_key_delegates_for_tmux(tmp_path, monkeypatch):
    """Special keys should delegate to tmux for tmux-backed sessions."""
    manager = SessionManager(registry_path=tmp_path / "tmux-session-registry.json")
    manager._ensure_record(  # noqa: SLF001 - exercising manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )
    sent = []
    monkeypatch.setattr("src.session_manager.send_tmux_key", lambda name, key: sent.append((name, key)))

    manager.send_special_key("tmux-session-1", "enter")

    assert sent == [("ops-shell", "enter")]


def test_session_manager_send_special_key_rejects_non_tmux_sessions():
    """Special keys should only be available for tmux-backed sessions."""
    manager = SessionManager()
    created = manager.create_session_entry("build")

    with pytest.raises(ValueError, match="tmux-backed"):
        manager.send_special_key(created["id"], "enter")


# TODO: Add tests for:
# - test_session_manager_max_sessions_limit()
# - test_session_manager_send_command()
# - test_session_manager_close_all()
# - test_session_manager_responsiveness_check()
