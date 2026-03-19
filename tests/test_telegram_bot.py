"""Tests for Telegram bot command handling."""

import asyncio
from types import SimpleNamespace

import pytest

from src import telegram_bot


class FakeChat:
    def __init__(self):
        self.actions = []

    async def send_action(self, action: str):
        self.actions.append(action)


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.chat = FakeChat()
        self.replies = []
        self.edits = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))

    async def edit_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))


class FakeUpdate:
    def __init__(self, user_id: int, text: str):
        self.effective_user = SimpleNamespace(id=user_id)
        self.message = FakeMessage(text)
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
    def __init__(self, user_id: int, data: str, message: FakeMessage | None = None):
        self.effective_user = SimpleNamespace(id=user_id)
        self.callback_query = FakeCallbackQuery(user_id, data, message=message)
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

    async def set_my_commands(self, commands):
        self.set_my_commands_calls.append(commands)


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
        self.runtime_sessions = {"777": FakeRuntimeSession(history="prompt$ ")}
        self.stream_chunks = {"777": ["prompt$ ", "pwd\n/home/demo\nprompt$ "]}
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
    assert "/repeat - Repeat the last terminal output" in rendered
