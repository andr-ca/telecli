"""Tests for Telegram bot command handling."""

import asyncio
from types import SimpleNamespace

import pytest

from src import telegram_bot


class FakeChat:
    def __init__(self, chat_id: int = 0):
        self.id = chat_id
        self.actions = []

    async def send_action(self, action: str):
        self.actions.append(action)


class FakeMessage:
    def __init__(self, text: str, chat_id: int = 0):
        self.text = text
        self.chat = FakeChat(chat_id)
        self.chat_id = chat_id
        self.replies = []
        self.edits = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))

    async def edit_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))


class FakeUpdate:
    def __init__(self, user_id: int, text: str, chat_id: int | None = None):
        resolved_chat_id = user_id if chat_id is None else chat_id
        self.effective_user = SimpleNamespace(id=user_id)
        self.effective_chat = SimpleNamespace(id=resolved_chat_id)
        self.message = FakeMessage(text, chat_id=resolved_chat_id)
        self.callback_query = None


class FakeCallbackQuery:
    def __init__(self, user_id: int, data: str, message: FakeMessage | None = None):
        self.from_user = SimpleNamespace(id=user_id)
        self.data = data
        self.message = message or FakeMessage("")
        self.answers = []
        self.edits = []

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))


class FakeCallbackUpdate:
    def __init__(self, user_id: int, data: str, message: FakeMessage | None = None, chat_id: int | None = None):
        resolved_chat_id = chat_id
        if resolved_chat_id is None and message is not None:
            resolved_chat_id = message.chat.id
        if resolved_chat_id is None:
            resolved_chat_id = user_id
        self.effective_user = SimpleNamespace(id=user_id)
        self.effective_chat = SimpleNamespace(id=resolved_chat_id)
        self.callback_query = FakeCallbackQuery(
            user_id,
            data,
            message=message or FakeMessage("", chat_id=resolved_chat_id),
        )
        self.message = None


class FakeRuntimeSession:
    def __init__(self, history: str = ""):
        self._history = history

    def get_recent_output(self) -> str:
        return self._history


class FakeClaudeAuto:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def get_status(self):
        return {"enabled": self.enabled, "waiting": False}


class FakeAiProxy:
    def __init__(self, enabled: bool, provider: str = "gemini-cli"):
        self.enabled = enabled
        self.provider = provider

    def get_status(self):
        return {"enabled": self.enabled, "provider": self.provider}


class FakeBot:
    def __init__(self):
        self.set_my_commands_calls = []
        self.send_message_calls = []

    async def set_my_commands(self, commands):
        self.set_my_commands_calls.append(commands)

    async def send_message(self, chat_id, text, **kwargs):
        self.send_message_calls.append((chat_id, text, kwargs))


class FakeApplicationBuilder:
    def __init__(self):
        self.token_value = None
        self.build_calls = 0

    def token(self, value):
        self.token_value = value
        return self

    def build(self):
        self.build_calls += 1
        return object()


class FakeSessionManager:
    def __init__(self):
        self.sent_inputs = []
        self.exact_inputs = []
        self.special_keys = []
        self.async_special_keys = []
        self.created_sessions = []
        self.deleted_sessions = []
        self.renamed_sessions = []
        self.imported_tmux = []
        self.created_tmux = []
        self.detached_tmux = []
        self.ai_enabled = []
        self.ai_disabled = []
        self.cc_enabled = []
        self.cc_disabled = []
        self.ai_proxies = {}
        self.claude_auto = {}
        self.agent_recommendations = {}
        self.runtime_sessions = {"777": FakeRuntimeSession(history="prompt$ ")}
        self.stream_chunks = {"777": ["prompt$ ", "pwd\n/home/demo\nprompt$ "]}
        self.snapshots = {}
        self.screens = {}
        self.tails = {}
        self.machine_tmux_sessions = [
            {
                "name": "ops-shell",
                "windows": 2,
                "attached": False,
                "imported": False,
                "imported_session_id": None,
                "imported_name": None,
            },
            {
                "name": "dev-shell",
                "windows": 1,
                "attached": True,
                "imported": False,
                "imported_session_id": None,
                "imported_name": None,
            },
        ]
        self._created_index = 0

    async def get_session(self, session_id: str):
        return self.runtime_sessions.setdefault(session_id, FakeRuntimeSession())

    async def send_input(self, session_id: str, text: str, newline: bool = True, from_ai: bool = False):
        self.sent_inputs.append((session_id, text, newline, from_ai))

    async def send_exact_input(self, session_id: str, text: str):
        self.exact_inputs.append((session_id, text))

    def send_special_key(self, session_id: str, key_name: str):
        self.special_keys.append((session_id, key_name))

    async def send_special_key_async(self, session_id: str, key_name: str):
        self.async_special_keys.append((session_id, key_name))
        self.send_special_key(session_id, key_name)

    async def get_output_stream(self, session_id: str):
        for chunk in self.stream_chunks.get(session_id, []):
            yield chunk

    def create_session_entry(self, name: str | None = None):
        self._created_index += 1
        session_id = f"web-{self._created_index}"
        session = {
            "id": session_id,
            "name": name or session_id,
            "backend": "telecli",
            "created_at": "2026-03-18T00:00:00+00:00",
            "shell": "bash",
            "is_active": False,
            "available": True,
            "tmux_session_name": None,
        }
        self.created_sessions.append(session)
        self.runtime_sessions.setdefault(session_id, FakeRuntimeSession(history="prompt$ "))
        self.stream_chunks.setdefault(session_id, ["prompt$ ", "echo hi\nhi\nprompt$ "])
        return session

    def rename_session(self, session_id: str, name: str):
        self.renamed_sessions.append((session_id, name))
        return {
            "id": session_id,
            "name": name,
            "backend": "telecli",
            "created_at": "2026-03-18T00:00:00+00:00",
            "shell": "bash",
            "is_active": False,
            "available": True,
            "tmux_session_name": None,
        }

    async def delete_session_entry(self, session_id: str):
        self.deleted_sessions.append(session_id)

    async def close_session(self, session_id: str):
        self.deleted_sessions.append(session_id)

    def list_sessions(self):
        return [
            {
                "id": "777",
                "name": "main",
                "backend": "telecli",
                "created_at": "2026-03-18T00:00:00+00:00",
                "shell": "bash",
                "is_active": True,
                "available": True,
                "tmux_session_name": None,
            },
            *self.created_sessions,
            *self.imported_tmux,
        ]

    def list_machine_tmux_sessions(self):
        return list(self.machine_tmux_sessions)

    def _register_tmux_session(self, tmux_session_name: str, name: str | None = None):
        self._created_index += 1
        session_id = f"tmux-{self._created_index}"
        session = {
            "id": session_id,
            "name": name or tmux_session_name,
            "backend": "tmux",
            "created_at": "2026-03-18T00:00:00+00:00",
            "shell": f"tmux:{tmux_session_name}",
            "is_active": False,
            "available": True,
            "tmux_session_name": tmux_session_name,
        }
        self.imported_tmux.append(session)
        self.runtime_sessions.setdefault(session_id, FakeRuntimeSession(history="tmux$ "))
        self.stream_chunks.setdefault(session_id, ["tmux$ ", "echo hi from tmux\nhi from tmux\ntmux$ "])
        self.snapshots.setdefault(session_id, "Claude is waiting\n> ")
        self.screens.setdefault(session_id, "Claude is waiting\n> ")
        self.tails.setdefault(session_id, "Claude is waiting")

        for tmux_session in self.machine_tmux_sessions:
            if tmux_session["name"] == tmux_session_name:
                tmux_session["imported"] = True
                tmux_session["imported_session_id"] = session_id
                tmux_session["imported_name"] = session["name"]
                break

        return session

    def import_tmux_session(self, tmux_session_name: str, name: str | None = None):
        self.created_tmux.append((tmux_session_name, name, "import"))
        return self._register_tmux_session(tmux_session_name, name)

    def create_tmux_session_entry(self, tmux_session_name: str, name: str | None = None):
        self.created_tmux.append((tmux_session_name, name, "create"))
        if not any(session["name"] == tmux_session_name for session in self.machine_tmux_sessions):
            self.machine_tmux_sessions.append(
                {
                    "name": tmux_session_name,
                    "windows": 1,
                    "attached": False,
                    "imported": False,
                    "imported_session_id": None,
                    "imported_name": None,
                }
            )
        return self._register_tmux_session(tmux_session_name, name)

    async def detach_tmux_session(self, session_id: str):
        self.detached_tmux.append(session_id)
        session = self.get_session_summary(session_id)
        session["is_active"] = False
        return session

    def get_session_summary(self, session_id: str):
        for session in self.list_sessions():
            if session["id"] == session_id:
                return dict(session)
        raise KeyError(session_id)

    def get_session_mode_capabilities(self, session_id: str):
        session = self.get_session_summary(session_id)
        return {
            "backend": session["backend"],
            "supports_agent_mode": session["backend"] == "tmux",
            "tmux_session_name": session["tmux_session_name"],
        }

    def get_agent_mode_recommendation(self, session_id: str):
        return self.agent_recommendations.get(
            session_id,
            {
                "supports_agent_mode": self.get_session_mode_capabilities(session_id)["supports_agent_mode"],
                "should_suggest_agent_mode": False,
                "reason": "not interactive",
                "signature": None,
            },
        )

    def capture_session_snapshot(self, session_id: str, *, lines: int = 80):
        return self.snapshots[session_id]

    def capture_session_screen(self, session_id: str):
        return self.screens[session_id]

    def tail_session_output(self, session_id: str, *, lines: int = 20):
        return self.tails[session_id]

    async def enable_ai_proxy(self, session_id: str, provider_name: str | None = None, system_prompt: str | None = None):
        self.ai_enabled.append((session_id, provider_name, system_prompt))
        self.ai_proxies[session_id] = FakeAiProxy(True, provider=provider_name or "gemini-cli")
        return True

    async def disable_ai_proxy(self, session_id: str):
        self.ai_disabled.append(session_id)
        self.ai_proxies.pop(session_id, None)

    def get_ai_proxy(self, session_id: str):
        return self.ai_proxies.get(session_id)

    async def enable_claude_code_auto_continue(self, session_id: str):
        self.cc_enabled.append(session_id)
        self.claude_auto[session_id] = FakeClaudeAuto(True)
        return True

    async def disable_claude_code_auto_continue(self, session_id: str):
        self.cc_disabled.append(session_id)
        self.claude_auto.pop(session_id, None)

    def get_claude_code_auto_continue(self, session_id: str):
        return self.claude_auto.get(session_id)


class DelayedFirstChunkSessionManager(FakeSessionManager):
    async def get_output_stream(self, session_id: str):
        await asyncio.sleep(0.02)
        for chunk in self.stream_chunks.get(session_id, []):
            yield chunk


class EchoThenDelayedOutputSessionManager(FakeSessionManager):
    async def get_output_stream(self, session_id: str):
        chunks = list(self.stream_chunks.get(session_id, []))
        if not chunks:
            return
        yield chunks[0]
        if len(chunks) > 1:
            yield chunks[1]
        if len(chunks) > 2:
            await asyncio.sleep(0.02)
            for chunk in chunks[2:]:
                yield chunk


@pytest.fixture(autouse=True)
def reset_telegram_bot_state(monkeypatch):
    monkeypatch.setattr(telegram_bot, "session_manager", None)
    monkeypatch.setattr(telegram_bot, "_telegram_user_sessions", {}, raising=False)
    monkeypatch.setattr(telegram_bot.Config, "ALLOWED_TELEGRAM_USERS", "")
    monkeypatch.setattr(
        telegram_bot.Config,
        "TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS",
        0.05,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_bot.Config,
        "TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )


@pytest.mark.asyncio
async def test_handle_message_executes_command_and_replies_with_new_output(monkeypatch):
    """Telegram command messages should execute via the live session APIs."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "pwd")

    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.sent_inputs == [("777", "pwd", True, False)]
    assert update.message.chat.actions == ["typing"]
    assert update.message.replies == [("/home/demo", {})]


@pytest.mark.asyncio
async def test_handle_message_falls_back_to_repeat_command_for_known_slash_text(monkeypatch):
    """Known bot slash commands should not be forwarded into the terminal if they hit the text handler."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    telegram_bot._get_user_sessions(777).last_outputs["777"] = "/home/demo"

    update = FakeUpdate(777, "/repeat")

    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.sent_inputs == []
    assert update.message.replies == [("/home/demo", {})]


@pytest.mark.asyncio
async def test_handle_message_falls_back_to_ai_command_for_known_slash_text(monkeypatch):
    """Known slash commands with arguments should be handled as bot commands, not shell input."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/ai on claude-cli")

    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.sent_inputs == []
    assert manager.ai_enabled == [("777", "claude-cli", None)]
    assert update.message.replies == [("AI proxy enabled for 777", {})]


@pytest.mark.asyncio
async def test_handle_message_waits_for_delayed_first_output(monkeypatch):
    """Telegram command execution should wait long enough for commands like ccusage to emit first output."""
    manager = DelayedFirstChunkSessionManager()
    manager.stream_chunks["777"] = ["prompt$ ", "ccusage blocks\n/home/demo\nprompt$ "]
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "ccusage blocks")

    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.sent_inputs == [("777", "ccusage blocks", True, False)]
    assert update.message.replies == [("/home/demo", {})]


@pytest.mark.asyncio
async def test_handle_message_waits_for_delayed_output_after_command_echo(monkeypatch):
    """Telegram command execution should not treat the echoed command as completed output."""
    manager = EchoThenDelayedOutputSessionManager()
    manager.stream_chunks["777"] = [
        "prompt$ ",
        "ccusage blocks\r\n",
        "Claude Code Token Usage Report\nprompt$ ",
    ]
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "ccusage blocks")

    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.sent_inputs == [("777", "ccusage blocks", True, False)]
    assert update.message.replies == [("Claude Code Token Usage Report", {})]


@pytest.mark.asyncio
async def test_newsession_then_use_session_routes_commands_to_selected_session(monkeypatch):
    """Telegram should support creating and switching named sessions."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    create_update = FakeUpdate(777, "/newsession build")
    await telegram_bot.newsession_command(create_update, SimpleNamespace(args=["build"]))

    sessions_update = FakeUpdate(777, "/sessions")
    await telegram_bot.sessions_command(sessions_update, SimpleNamespace(args=[]))

    command_update = FakeUpdate(777, "echo hi")
    await telegram_bot.handle_message(command_update, SimpleNamespace())

    assert manager.created_sessions[0]["name"] == "build"
    assert "build" in sessions_update.message.replies[0][0]
    assert manager.sent_inputs[-1][0] == "web-1"
    assert command_update.message.replies == [("hi", {})]


@pytest.mark.asyncio
async def test_start_reports_current_alias(monkeypatch):
    """Start should report the user's actual current Telegram alias."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    await telegram_bot.newsession_command(FakeUpdate(777, "/newsession build"), SimpleNamespace(args=["build"]))

    update = FakeUpdate(777, "/start")
    await telegram_bot.start(update, SimpleNamespace(args=[]))

    assert "current Telegram session is `build` (web-1)" in update.message.replies[0][0]


@pytest.mark.asyncio
async def test_newsession_rejects_whitespace_only_names(monkeypatch):
    """Telegram should reject whitespace-only session names."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/newsession    ")
    await telegram_bot.newsession_command(update, SimpleNamespace(args=["   "]))

    assert manager.created_sessions == []
    assert update.message.replies == [("Session name cannot be empty", {})]


@pytest.mark.asyncio
async def test_usesession_without_args_shows_session_picker(monkeypatch):
    """Telegram should offer a picker when /usesession is invoked without an argument."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    await telegram_bot.newsession_command(FakeUpdate(777, "/newsession build"), SimpleNamespace(args=["build"]))

    update = FakeUpdate(777, "/usesession")
    await telegram_bot.usesession_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Pick a session" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "main" in labels
    assert "build" in labels
    assert "use-session:web-1" in callback_data


@pytest.mark.asyncio
async def test_session_picker_callback_switches_current_session(monkeypatch):
    """Tapping a session picker button should switch the Telegram current session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    await telegram_bot.newsession_command(FakeUpdate(777, "/newsession build"), SimpleNamespace(args=["build"]))

    picker_message = FakeMessage("Pick a session")
    update = FakeCallbackUpdate(777, "use-session:web-1", message=picker_message)

    await telegram_bot.handle_session_picker(update, SimpleNamespace())

    state = telegram_bot._get_user_sessions(777)
    assert state.current_alias == "build"
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert update.callback_query.edits[0][0] == "Switched to session 'build'"


@pytest.mark.asyncio
async def test_usesession_allocates_unique_alias_when_session_name_collides(monkeypatch):
    """Switching to a known session should not fail if its name collides with an existing alias."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    manager.create_session_entry("main")
    update = FakeUpdate(777, "/usesession web-1")

    await telegram_bot.usesession_command(update, SimpleNamespace(args=["web-1"]))

    state = telegram_bot._get_user_sessions(777)
    assert state.current_alias == "main-2"
    assert state.sessions["main-2"] == "web-1"
    assert update.message.replies == [("Switched to session 'main-2'", {})]


@pytest.mark.asyncio
async def test_session_picker_allocates_unique_alias_when_session_name_collides(monkeypatch):
    """Session picker should not fail if the target session name collides with an existing alias."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    manager.create_session_entry("main")
    update = FakeCallbackUpdate(777, "use-session:web-1", message=FakeMessage("Pick a session"))

    await telegram_bot.handle_session_picker(update, SimpleNamespace())

    state = telegram_bot._get_user_sessions(777)
    assert state.current_alias == "main-2"
    assert state.sessions["main-2"] == "web-1"
    assert update.callback_query.edits[0][0] == "Switched to session 'main-2'"


@pytest.mark.asyncio
async def test_ai_and_ccauto_commands_toggle_features_for_current_session(monkeypatch):
    """Feature commands should target the user's currently selected session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    create_update = FakeUpdate(777, "/newsession build")
    await telegram_bot.newsession_command(create_update, SimpleNamespace(args=["build"]))

    ai_update = FakeUpdate(777, "/ai on claude-cli")
    await telegram_bot.ai_command(ai_update, SimpleNamespace(args=["on", "claude-cli"]))

    cc_update = FakeUpdate(777, "/ccauto on")
    await telegram_bot.ccauto_command(cc_update, SimpleNamespace(args=["on"]))

    features_update = FakeUpdate(777, "/features")
    await telegram_bot.features_command(features_update, SimpleNamespace(args=[]))

    assert manager.ai_enabled == [("web-1", "claude-cli", None)]
    assert manager.cc_enabled == ["web-1"]
    assert "AI Proxy: on (claude-cli)" in features_update.message.replies[0][0]
    assert "Claude Auto-Continue: on" in features_update.message.replies[0][0]


@pytest.mark.asyncio
async def test_mode_status_defaults_to_shell_for_regular_session(monkeypatch):
    """Mode status should default to shell for sessions without explicit mode state."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/mode status")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["status"]))

    rendered = update.message.replies[0][0]
    assert "Mode: shell" in rendered
    assert "Backend: telecli" in rendered


@pytest.mark.asyncio
async def test_mode_agent_requires_tmux_backed_session(monkeypatch):
    """Agent mode should be rejected for regular TeleCLI sessions."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/mode agent")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["agent"]))

    assert "requires a tmux-backed session" in update.message.replies[0][0]


@pytest.mark.asyncio
async def test_mode_without_args_shows_action_picker(monkeypatch):
    """Telegram should offer mode actions when /mode is invoked without arguments."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/mode")
    await telegram_bot.mode_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Choose Telegram mode action" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "Status" in labels
    assert "Shell" in labels
    assert "Agent" not in labels
    assert "command:mode:777:status" in callback_data
    assert "command:mode:777:shell" in callback_data


@pytest.mark.asyncio
async def test_mode_agent_switches_tmux_backed_session(monkeypatch):
    """Agent mode should be accepted for tmux-backed sessions and stored per session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/mode agent")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["agent"]))

    state = telegram_bot._get_user_sessions(777)
    assert state.session_modes["tmux-1"] == "agent"
    assert update.message.replies == [("Mode set to agent for tmux-1", {})]


@pytest.mark.asyncio
async def test_mode_picker_callback_switches_tmux_session_to_agent(monkeypatch):
    """Tapping a mode picker button should apply that mode to the targeted session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeCallbackUpdate(777, "command:mode:tmux-1:agent")
    await telegram_bot.handle_command_picker(update, SimpleNamespace())

    state = telegram_bot._get_user_sessions(777)
    assert state.session_modes["tmux-1"] == "agent"
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert update.callback_query.edits[0][0] == "Mode set to agent for tmux-1"


@pytest.mark.asyncio
async def test_mode_agent_rejects_unavailable_tmux_backed_session(monkeypatch):
    """Agent mode should be rejected when the tmux backing session is gone."""
    manager = telegram_bot.SessionManager()
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: False)
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    manager._ensure_record(  # noqa: SLF001 - exercising existing manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    state = telegram_bot._get_user_sessions(777)
    state.sessions["ops"] = "tmux-session-1"
    state.current_alias = "ops"

    update = FakeUpdate(777, "/mode agent")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["agent"]))

    assert "requires a tmux-backed session" in update.message.replies[0][0]
    assert state.session_modes.get("tmux-session-1") != "agent"


@pytest.mark.asyncio
async def test_status_command_reports_mode_and_backend(monkeypatch):
    """Status should report the active mode, backend, and tmux target details."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    telegram_bot._get_user_sessions(777).session_modes["tmux-1"] = "agent"

    update = FakeUpdate(777, "/status")
    await telegram_bot.status_command(update, SimpleNamespace(args=[]))

    rendered = update.message.replies[0][0]
    assert "Mode: agent" in rendered
    assert "Backend: tmux" in rendered
    assert "tmux target: ops-shell" in rendered


@pytest.mark.asyncio
async def test_agent_mode_picker_rejects_unavailable_tmux_backed_session(monkeypatch):
    """The inline agent-mode switch should refuse sessions whose tmux backend disappeared."""
    manager = telegram_bot.SessionManager()
    monkeypatch.setattr("src.session_manager.tmux_session_exists", lambda name: False)
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    manager._ensure_record(  # noqa: SLF001 - exercising existing manager state directly
        "tmux-session-1",
        backend="tmux",
        name="Ops Shell",
        tmux_session_name="ops-shell",
    )

    state = telegram_bot._get_user_sessions(777)
    state.sessions["ops"] = "tmux-session-1"
    state.current_alias = "ops"

    update = FakeCallbackUpdate(777, "agent-mode:switch:tmux-session-1")
    await telegram_bot.handle_agent_mode_picker(update, SimpleNamespace())

    assert state.session_modes.get("tmux-session-1") != "agent"
    assert "requires a tmux-backed session" in update.callback_query.edits[0][0]


@pytest.mark.asyncio
async def test_handle_message_uses_exact_send_in_agent_mode(monkeypatch):
    """Agent mode should send raw text plus Enter and then return the cleaned current screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    telegram_bot._get_user_sessions(777).session_modes["tmux-1"] = "agent"

    update = FakeUpdate(777, "continue")
    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.exact_inputs == [("tmux-1", "continue")]
    assert manager.special_keys == [("tmux-1", "enter")]
    assert manager.async_special_keys == [("tmux-1", "enter")]
    assert manager.sent_inputs == []
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_handle_message_agent_mode_logs_metadata_not_raw_text(monkeypatch, caplog):
    """Agent mode logs should avoid raw message content at INFO level."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    telegram_bot._get_user_sessions(777).session_modes["tmux-1"] = "agent"

    secret = "sk-test-agent-secret"
    update = FakeUpdate(777, secret)
    with caplog.at_level("INFO"):
        await telegram_bot.handle_message(update, SimpleNamespace())

    assert secret not in caplog.text
    assert "len=" in caplog.text


@pytest.mark.asyncio
async def test_handle_message_shell_mode_logs_metadata_not_raw_command(monkeypatch, caplog):
    """Shell-mode logs should avoid raw command content at INFO level."""
    manager = FakeSessionManager()
    manager.stream_chunks["777"] = ["prompt$ ", "result\nprompt$ "]
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    secret = "sk-shell-secret"
    update = FakeUpdate(777, secret)
    with caplog.at_level("INFO"):
        await telegram_bot.handle_message(update, SimpleNamespace())

    assert secret not in caplog.text
    assert "len=" in caplog.text


@pytest.mark.asyncio
async def test_snapshot_command_reports_backend_errors(monkeypatch):
    """Snapshot should surface backend failures as a Telegram error message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    manager.capture_session_snapshot = lambda session_id, *, lines=80: (_ for _ in ()).throw(ValueError("tmux unavailable"))  # noqa: E731

    update = FakeUpdate(777, "/snapshot")
    await telegram_bot.snapshot_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [("❌ Error: tmux unavailable", {})]


@pytest.mark.asyncio
async def test_snapshot_command_rejects_non_tmux_sessions_with_actionable_message(monkeypatch):
    """Snapshot should guide users toward tmux-backed sessions before backend capture."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/snapshot")
    await telegram_bot.snapshot_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [
        ("❌ /snapshot requires a tmux-backed session. Use /newtmux or /attachtmux.", {})
    ]


@pytest.mark.asyncio
async def test_tail_command_reports_backend_errors(monkeypatch):
    """Tail should surface backend failures as a Telegram error message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    manager.tail_session_output = lambda session_id, *, lines=20: (_ for _ in ()).throw(RuntimeError("tmux unavailable"))  # noqa: E731

    update = FakeUpdate(777, "/tail")
    await telegram_bot.tail_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [("❌ Error: tmux unavailable", {})]


@pytest.mark.asyncio
async def test_screen_command_rejects_non_tmux_sessions_with_actionable_message(monkeypatch):
    """Screen should reject non-tmux sessions with a consistent tmux guidance message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/screen")
    await telegram_bot.screen_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [
        ("❌ /screen requires a tmux-backed session. Use /newtmux or /attachtmux.", {})
    ]


@pytest.mark.asyncio
async def test_tail_command_rejects_non_tmux_sessions_with_actionable_message(monkeypatch):
    """Tail should reject non-tmux sessions with a consistent tmux guidance message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/tail")
    await telegram_bot.tail_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [
        ("❌ /tail requires a tmux-backed session. Use /newtmux or /attachtmux.", {})
    ]


@pytest.mark.asyncio
async def test_key_command_reports_backend_errors(monkeypatch):
    """Key should surface backend failures as a Telegram error message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    manager.send_special_key = lambda session_id, key_name: (_ for _ in ()).throw(ValueError("unsupported key"))  # noqa: E731

    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/key enter")
    await telegram_bot.key_command(update, SimpleNamespace(args=["enter"]))

    assert update.message.replies == [("❌ Error: unsupported key", {})]


@pytest.mark.asyncio
async def test_key_without_args_shows_action_picker_for_tmux_session(monkeypatch):
    """Telegram should offer key actions when /key is invoked without arguments."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/key")
    await telegram_bot.key_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Choose key to send" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "Enter" in labels
    assert "Esc" in labels
    assert "Ctrl+D" in labels
    assert "command:key:tmux-1:enter" in callback_data
    assert "command:key:tmux-1:ctrl-d" in callback_data


@pytest.mark.asyncio
async def test_watch_without_args_shows_action_picker_for_tmux_session(monkeypatch):
    """Telegram should offer watch actions when /watch is invoked without arguments."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/watch")
    await telegram_bot.watch_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Choose screen watch action" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "Status" in labels
    assert "Enable" in labels
    assert "Disable" in labels
    assert "command:watch:tmux-1:on" in callback_data
    assert "command:watch:tmux-1:off" in callback_data


@pytest.mark.asyncio
async def test_watch_on_enables_screen_monitoring_for_tmux_session(monkeypatch):
    """Watch on should enable background screen monitoring for the active tmux session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/watch on")
    await telegram_bot.watch_command(update, SimpleNamespace(args=["on"]))

    assert update.message.replies == [("Screen watch enabled for tmux-1", {})]


@pytest.mark.asyncio
async def test_watch_on_stores_group_chat_for_push_updates(monkeypatch):
    """Enabling watch from a group should remember the group chat ID."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    await telegram_bot.watch_command(
        FakeUpdate(777, "/watch on", chat_id=-100123),
        SimpleNamespace(args=["on"]),
    )

    watch_state = telegram_bot._get_screen_watch_state(777, "tmux-1")
    assert watch_state.chat_id == -100123


@pytest.mark.asyncio
async def test_watch_picker_callback_stores_group_chat_for_push_updates(monkeypatch):
    """Enabling watch from the picker should remember the callback message chat ID."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeCallbackUpdate(
        777,
        "command:watch:tmux-1:on",
        message=FakeMessage("Pick action", chat_id=-100456),
    )
    await telegram_bot.handle_command_picker(update, SimpleNamespace())

    watch_state = telegram_bot._get_screen_watch_state(777, "tmux-1")
    assert watch_state.chat_id == -100456


@pytest.mark.asyncio
async def test_screen_watch_tick_pushes_stable_changed_screen_once(monkeypatch):
    """Enabled watches should push a screen only after the changed pane stays stable."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    await telegram_bot.watch_command(FakeUpdate(777, "/watch on"), SimpleNamespace(args=["on"]))

    bot = FakeBot()
    manager.screens["tmux-1"] = "Change incoming\n> "
    await telegram_bot._run_screen_watch_tick(bot)
    assert bot.send_message_calls == []

    await telegram_bot._run_screen_watch_tick(bot)
    assert bot.send_message_calls == [
        (777, "<pre>Change incoming\n&gt; </pre>", {"parse_mode": "HTML"})
    ]

    await telegram_bot._run_screen_watch_tick(bot)
    assert len(bot.send_message_calls) == 1


@pytest.mark.asyncio
async def test_screen_watch_tick_uses_stored_group_chat_id(monkeypatch):
    """Screen watch pushes should target the stored chat ID instead of the Telegram user ID."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    await telegram_bot.watch_command(
        FakeUpdate(777, "/watch on", chat_id=-100789),
        SimpleNamespace(args=["on"]),
    )

    bot = FakeBot()
    manager.screens["tmux-1"] = "Change incoming\n> "
    await telegram_bot._run_screen_watch_tick(bot)
    await telegram_bot._run_screen_watch_tick(bot)

    assert bot.send_message_calls == [
        (-100789, "<pre>Change incoming\n&gt; </pre>", {"parse_mode": "HTML"})
    ]


@pytest.mark.asyncio
async def test_screen_watch_tick_offloads_capability_probe(monkeypatch):
    """Watch ticks should offload capability checks before evaluating tmux state."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    await telegram_bot.watch_command(FakeUpdate(777, "/watch on"), SimpleNamespace(args=["on"]))

    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(telegram_bot.asyncio, "to_thread", fake_to_thread)
    bot = FakeBot()
    manager.screens["tmux-1"] = "Change incoming\n> "
    await telegram_bot._run_screen_watch_tick(bot)

    assert calls[0] == ("get_session_mode_capabilities", ("tmux-1",), {})


@pytest.mark.asyncio
async def test_reply_with_current_screen_offloads_capture_to_worker_thread(monkeypatch):
    """Current-screen replies should offload tmux capture work away from the event loop."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(telegram_bot.asyncio, "to_thread", fake_to_thread)
    update = FakeUpdate(777, "/screen")
    await telegram_bot._reply_with_current_screen(update, "tmux-1", delay_seconds=0)

    assert calls == [("capture_session_screen", ("tmux-1",), {})]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_snapshot_command_returns_tmux_capture(monkeypatch):
    """Snapshot should return the current tmux pane text for agent sessions."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/snapshot")
    await telegram_bot.snapshot_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_key_picker_callback_sends_key_and_returns_current_screen(monkeypatch):
    """Tapping a key picker button should send that key and show the refreshed screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeCallbackUpdate(777, "command:key:tmux-1:ctrl-d")
    await telegram_bot.handle_command_picker(update, SimpleNamespace())

    assert manager.special_keys == [("tmux-1", "ctrl-d")]
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert update.callback_query.edits == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_screen_command_returns_visible_tmux_screen(monkeypatch):
    """Screen should show the visible tmux pane in preformatted form."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )
    manager.screens["tmux-1"] = "top line\nbottom line\n\n\n"

    update = FakeUpdate(777, "/screen")
    await telegram_bot.screen_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [("<pre>top line\nbottom line</pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_tail_command_returns_recent_tmux_output(monkeypatch):
    """Tail should return recent pane output for the current tmux-backed session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/tail")
    await telegram_bot.tail_command(update, SimpleNamespace(args=[]))

    assert update.message.replies == [("Claude is waiting", {})]


@pytest.mark.asyncio
async def test_send_command_forwards_exact_text(monkeypatch):
    """The explicit send command should paste text and then return the current screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/send continue")
    await telegram_bot.send_command(update, SimpleNamespace(args=["continue"]))

    assert manager.exact_inputs == [("tmux-1", "continue")]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_send_command_reports_backend_errors(monkeypatch):
    """Send should surface backend failures as a Telegram error message."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    manager.send_exact_input = lambda session_id, text: (_ for _ in ()).throw(RuntimeError("tmux unavailable"))  # noqa: E731

    state = telegram_bot._get_user_sessions(777)
    state.sessions["ops"] = "tmux-1"
    state.current_alias = "ops"

    update = FakeUpdate(777, "/send continue")
    await telegram_bot.send_command(update, SimpleNamespace(args=["continue"]))

    assert update.message.replies == [("❌ Error: tmux unavailable", {})]


@pytest.mark.asyncio
async def test_key_command_sends_named_special_key(monkeypatch):
    """The key command should route a normalized special key and then return the screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/key enter")
    await telegram_bot.key_command(update, SimpleNamespace(args=["enter"]))

    assert manager.async_special_keys == [("tmux-1", "enter")]
    assert manager.special_keys == [("tmux-1", "enter")]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_key_command_supports_navigation_and_control_keys(monkeypatch):
    """The key command should support the broader Telegram key set and refresh the screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/key left")
    await telegram_bot.key_command(update, SimpleNamespace(args=["left"]))

    assert manager.async_special_keys == [("tmux-1", "left")]
    assert manager.special_keys == [("tmux-1", "left")]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_continue_command_sends_continue_and_enter(monkeypatch):
    """Continue should send the literal continue text, submit it, and return the screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/continue")
    await telegram_bot.continue_command(update, SimpleNamespace(args=[]))

    assert manager.exact_inputs == [("tmux-1", "continue")]
    assert manager.async_special_keys == [("tmux-1", "enter")]
    assert manager.special_keys == [("tmux-1", "enter")]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_interrupt_command_sends_ctrl_c(monkeypatch):
    """Interrupt should send Ctrl+C and then return the current screen."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeUpdate(777, "/interrupt")
    await telegram_bot.interrupt_command(update, SimpleNamespace(args=[]))

    assert manager.async_special_keys == [("tmux-1", "ctrl-c")]
    assert manager.special_keys == [("tmux-1", "ctrl-c")]
    assert update.message.replies == [("<pre>Claude is waiting\n&gt; </pre>", {"parse_mode": "HTML"})]


@pytest.mark.asyncio
async def test_handle_message_suggests_agent_mode_once_for_interactive_tmux(monkeypatch):
    """Interactive tmux sessions should get one agent-mode suggestion per recommendation signature."""
    manager = FakeSessionManager()
    manager.agent_recommendations["tmux-1"] = {
        "supports_agent_mode": True,
        "should_suggest_agent_mode": True,
        "reason": "codex",
        "signature": "sig-1",
    }
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    first_update = FakeUpdate(777, "pwd")
    await telegram_bot.handle_message(first_update, SimpleNamespace())

    second_update = FakeUpdate(777, "pwd")
    await telegram_bot.handle_message(second_update, SimpleNamespace())

    assert any("Switch this session to agent mode?" in text for text, _ in first_update.message.replies)
    assert all("Switch this session to agent mode?" not in text for text, _ in second_update.message.replies)


@pytest.mark.asyncio
async def test_agent_mode_picker_switches_session_to_agent(monkeypatch):
    """The inline switch action should flip the active session into agent mode."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    update = FakeCallbackUpdate(777, "agent-mode:switch:tmux-1")
    await telegram_bot.handle_agent_mode_picker(update, SimpleNamespace())

    state = telegram_bot._get_user_sessions(777)
    assert state.session_modes["tmux-1"] == "agent"
    assert update.callback_query.edits[0][0] == "Mode set to agent for tmux-1"


@pytest.mark.asyncio
async def test_agent_mode_picker_mute_suppresses_future_suggestions(monkeypatch):
    """Muting agent-mode suggestions should suppress later prompts for that session."""
    manager = FakeSessionManager()
    manager.agent_recommendations["tmux-1"] = {
        "supports_agent_mode": True,
        "should_suggest_agent_mode": True,
        "reason": "codex",
        "signature": "sig-1",
    }
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    mute_update = FakeCallbackUpdate(777, "agent-mode:mute:tmux-1")
    await telegram_bot.handle_agent_mode_picker(mute_update, SimpleNamespace())

    follow_up = FakeUpdate(777, "pwd")
    await telegram_bot.handle_message(follow_up, SimpleNamespace())

    assert all("Switch this session to agent mode?" not in text for text, _ in follow_up.message.replies)


@pytest.mark.asyncio
async def test_ai_without_args_shows_action_picker(monkeypatch):
    """Telegram should offer AI actions when /ai is invoked without arguments."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/ai")
    await telegram_bot.ai_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Choose AI proxy action" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "Status" in labels
    assert "Enable Gemini" in labels
    assert "Enable Claude" in labels
    assert "feature:ai:on:claude-cli" in callback_data


@pytest.mark.asyncio
async def test_ai_picker_callback_enables_provider(monkeypatch):
    """Tapping an AI action button should apply that change to the active session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeCallbackUpdate(777, "feature:ai:on:claude-cli")
    await telegram_bot.handle_feature_picker(update, SimpleNamespace())

    assert manager.ai_enabled == [("777", "claude-cli", None)]
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert update.callback_query.edits[0][0] == "AI proxy enabled for 777"


@pytest.mark.asyncio
async def test_ccauto_without_args_shows_action_picker(monkeypatch):
    """Telegram should offer Claude auto-continue actions when /ccauto is invoked without arguments."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/ccauto")
    await telegram_bot.ccauto_command(update, SimpleNamespace(args=[]))

    assert len(update.message.replies) == 1
    text, kwargs = update.message.replies[0]
    assert "Choose Claude auto-continue action" in text
    reply_markup = kwargs["reply_markup"]
    labels = [button.text for row in reply_markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert "Status" in labels
    assert "Enable" in labels
    assert "Disable" in labels
    assert "feature:ccauto:on" in callback_data


@pytest.mark.asyncio
async def test_ccauto_picker_callback_enables_feature(monkeypatch):
    """Tapping a Claude auto-continue action button should apply that change to the active session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeCallbackUpdate(777, "feature:ccauto:on")
    await telegram_bot.handle_feature_picker(update, SimpleNamespace())

    assert manager.cc_enabled == ["777"]
    assert update.callback_query.answers == [{"text": None, "show_alert": False}]
    assert update.callback_query.edits[0][0] == "Claude auto-continue enabled for 777"


@pytest.mark.asyncio
async def test_sessions_command_lists_aliases_known_sessions_and_machine_tmux(monkeypatch):
    """The sessions command should show Telegram aliases, imported sessions, and machine tmux inventory."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    await telegram_bot.newsession_command(FakeUpdate(777, "/newsession build"), SimpleNamespace(args=["build"]))
    await telegram_bot.attachtmux_command(
        FakeUpdate(777, "/attachtmux ops-shell Ops Shell"),
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    sessions_update = FakeUpdate(777, "/sessions")
    await telegram_bot.sessions_command(sessions_update, SimpleNamespace(args=[]))

    rendered = sessions_update.message.replies[0][0]
    assert "Telegram aliases:" in rendered
    assert "build -> web-1" in rendered
    assert "Ops Shell -> tmux-2" in rendered
    assert "Known TeleCLI sessions:" in rendered
    assert "Ops Shell [tmux]" in rendered
    assert "tmux=ops-shell" in rendered
    assert "Machine tmux sessions:" in rendered
    assert "dev-shell" in rendered


@pytest.mark.asyncio
async def test_tmux_commands_attach_create_and_detach_current_session(monkeypatch):
    """Telegram should support importing, creating, and detaching tmux-backed sessions."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    attach_update = FakeUpdate(777, "/attachtmux ops-shell Ops Shell")
    await telegram_bot.attachtmux_command(
        attach_update,
        SimpleNamespace(args=["ops-shell", "Ops", "Shell"]),
    )

    create_update = FakeUpdate(777, "/newtmux pairing-shell Pairing Shell")
    await telegram_bot.newtmux_command(
        create_update,
        SimpleNamespace(args=["pairing-shell", "Pairing", "Shell"]),
    )

    detach_update = FakeUpdate(777, "/detach")
    await telegram_bot.detach_command(detach_update, SimpleNamespace(args=[]))

    assert manager.created_tmux == [
        ("ops-shell", "Ops Shell", "import"),
        ("pairing-shell", "Pairing Shell", "create"),
    ]
    assert manager.detached_tmux == ["tmux-2"]
    assert "Attached tmux session 'ops-shell'" in attach_update.message.replies[0][0]
    assert "Created tmux session 'pairing-shell'" in create_update.message.replies[0][0]
    assert "Detached tmux session 'pairing-shell'" in detach_update.message.replies[0][0]


@pytest.mark.asyncio
async def test_repeat_command_replies_with_previous_terminal_output(monkeypatch):
    """Repeat should resend the last rendered terminal output for the active session."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    command_update = FakeUpdate(777, "pwd")
    await telegram_bot.handle_message(command_update, SimpleNamespace())

    repeat_update = FakeUpdate(777, "/repeat")
    await telegram_bot.repeat_command(repeat_update, SimpleNamespace(args=[]))

    assert command_update.message.replies == [("/home/demo", {})]
    assert repeat_update.message.replies == [("/home/demo", {})]


@pytest.mark.asyncio
async def test_register_bot_commands_sets_slash_menu_for_autocomplete():
    """Telegram startup should publish slash commands so clients can autocomplete them."""
    bot = FakeBot()

    await telegram_bot._register_bot_commands(bot)

    assert len(bot.set_my_commands_calls) == 1
    commands = bot.set_my_commands_calls[0]
    assert any(command.command == "help" for command in commands)
    assert any(command.command == "attachtmux" for command in commands)
    assert any(command.command == "mode" for command in commands)
    assert any(command.command == "continue" for command in commands)
    assert any(command.command == "interrupt" for command in commands)
    assert any(command.command == "screen" for command in commands)
    assert any(command.command == "watch" for command in commands)
    assert any(command.command == "snapshot" for command in commands)
    assert any(command.command == "tail" for command in commands)
    assert any(command.command == "repeat" for command in commands)


@pytest.mark.asyncio
async def test_telegram_main_rejects_missing_bot_token(monkeypatch):
    """Direct Telegram startup should fail fast with a clear error if the bot token is absent."""
    builder = FakeApplicationBuilder()

    monkeypatch.setattr(telegram_bot.Config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(telegram_bot.Config, "TELEGRAM_WEBHOOK_URL", "")
    monkeypatch.setattr(telegram_bot.Application, "builder", lambda: builder)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        await telegram_bot.main()

    assert builder.token_value is None
    assert builder.build_calls == 0


@pytest.mark.asyncio
async def test_help_command_lists_commands_and_autocomplete_hint(monkeypatch):
    """Help should document the available commands and point users to the slash-command menu."""
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/help")
    await telegram_bot.help_command(update, SimpleNamespace(args=[]))

    rendered = update.message.replies[0][0]
    assert "Use Telegram's / menu to autocomplete commands." in rendered
    assert "/attachtmux <tmux-name> [alias]" in rendered
    assert "/newtmux <tmux-name> [alias]" in rendered
    assert "/mode <shell|agent|status>" in rendered
    assert "shell mode" in rendered.lower()
    assert "agent mode" in rendered.lower()
    assert "/screen" in rendered
    assert "/snapshot" in rendered
    assert "/tail [lines]" in rendered
    assert "/key <enter|esc|tab|up|down|left|right|backspace|ctrl-c|ctrl-d>" in rendered
    assert "/continue" in rendered
    assert "/interrupt" in rendered
    assert "/repeat - Repeat the last terminal output" in rendered
