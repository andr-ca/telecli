# Telegram Agent Mode Implementation Plan

**Goal:** Build a hybrid Telegram experience where normal shell sessions keep the current line-oriented behavior, while tmux-backed interactive sessions can opt into `agent mode` with auto-suggest for coding-agent TUIs.

**Architecture:** Keep Telegram policy in `src/telegram_bot.py`, add a tmux capability layer in `src/session_manager.py`, and centralize tmux inspection/control helpers in `src/tmux.py`. The implementation should stay conservative: agent mode only works on tmux-backed sessions in v1, and auto-suggest is opt-in with per-session suppression.

**Tech Stack:** Python 3.12, `python-telegram-bot`, tmux subprocess helpers, pytest, pytest-asyncio

## Prerequisites

1. Work from a clean branch or worktree for the Telegram TUI usability changes.
2. Read the approved design in `docs/plans/2026-03-19-telegram-agent-mode-design.md`.
3. Add or update tests alongside each behavior change.
4. Run focused verification before committing.

### Task 1: Add tmux inspection and key helpers

**Files:**
- Create: `tests/test_tmux.py`
- Modify: `src/tmux.py:1-73`

**Step 1: Write the failing tmux helper tests**

Add focused tests for pane metadata parsing, snapshot capture, interactive recommendation, and special-key mapping.

```python
from types import SimpleNamespace

import pytest

from src import tmux


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_get_tmux_pane_state_parses_foreground_command(monkeypatch):
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda *args, **kwargs: _completed("%1\tcodex\t1\n"),
    )

    state = tmux.get_tmux_pane_state("dev-shell")

    assert state["pane_id"] == "%1"
    assert state["current_command"] == "codex"
    assert state["alternate_screen"] is True
    assert state["interactive"] is True


def test_capture_tmux_pane_returns_text(monkeypatch):
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda *args, **kwargs: _completed("line 1\nline 2\n"),
    )

    assert tmux.capture_tmux_pane("dev-shell", lines=20) == "line 1\nline 2\n"


def test_send_tmux_key_maps_common_aliases(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed()

    monkeypatch.setattr(tmux.subprocess, "run", fake_run)

    tmux.send_tmux_key("dev-shell", "ctrl-c")

    assert calls[0][-2:] == ["C-c"]
```

**Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_tmux.py -v`

Expected: FAIL with missing helper functions such as `get_tmux_pane_state`, `capture_tmux_pane`, and `send_tmux_key`.

**Step 3: Add the minimal tmux helpers**

Extend `src/tmux.py` with a small helper surface and shared command runner.

```python
_PANE_FORMAT = "#{pane_id}\t#{pane_current_command}\t#{alternate_on}"
_INTERACTIVE_COMMANDS = {"claude", "codex", "vim", "less", "man", "htop"}
_SPECIAL_KEYS = {
    "enter": "Enter",
    "esc": "Escape",
    "tab": "Tab",
    "up": "Up",
    "down": "Down",
    "ctrl-c": "C-c",
}


def get_tmux_pane_state(session_name: str) -> dict:
    result = _run_tmux_command(["display-message", "-pt", session_name, _PANE_FORMAT])
    pane_id, current_command, alternate_on = (result.stdout.strip().split("\t") + ["", "", "0"])[:3]
    interactive = current_command.lower() in _INTERACTIVE_COMMANDS or alternate_on == "1"
    return {
        "pane_id": pane_id,
        "current_command": current_command,
        "alternate_screen": alternate_on == "1",
        "interactive": interactive,
    }


def capture_tmux_pane(session_name: str, *, lines: int = 80) -> str:
    result = _run_tmux_command(["capture-pane", "-pt", session_name, "-S", f"-{lines}", "-e"])
    return result.stdout


def send_tmux_key(session_name: str, key_name: str) -> None:
    mapped = _SPECIAL_KEYS[key_name.lower()]
    _run_tmux_command(["send-keys", "-t", session_name, mapped])
```

Also add a recommendation helper:

```python
def get_tmux_interaction_recommendation(session_name: str) -> dict:
    pane = get_tmux_pane_state(session_name)
    snapshot = capture_tmux_pane(session_name, lines=40)
    signature = f"{session_name}:{pane['pane_id']}:{pane['current_command']}:{hash(snapshot)}"
    return {
        "supports_agent_mode": True,
        "should_suggest_agent_mode": pane["interactive"],
        "reason": pane["current_command"] or "unknown",
        "signature": signature,
        "pane": pane,
    }
```

Keep errors narrow: raise `ValueError` for unsupported keys and missing tmux.

**Step 4: Run the tmux tests again**

Run: `pytest tests/test_tmux.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/tmux.py tests/test_tmux.py
git commit -m "feat: add tmux agent-mode helpers"
```

### Task 2: Add session-manager capability methods

**Files:**
- Modify: `src/session_manager.py:14-20`
- Modify: `src/session_manager.py:147-365`
- Modify: `tests/test_session_manager.py:54-205`

**Step 1: Write the failing session-manager tests**

Add tests that prove the manager can report agent-mode capabilities, delegate snapshot/tail capture, and reject non-tmux agent-mode actions.

```python
def test_session_manager_reports_agent_mode_recommendation_for_tmux(tmp_path, monkeypatch):
    manager = SessionManager(registry_path=tmp_path / "registry.json")
    manager._ensure_record("tmux-1", backend="tmux", name="Ops", tmux_session_name="ops-shell")  # noqa: SLF001
    monkeypatch.setattr(
        "src.session_manager.get_tmux_interaction_recommendation",
        lambda name: {
            "supports_agent_mode": True,
            "should_suggest_agent_mode": True,
            "reason": "codex",
            "signature": "sig-1",
        },
    )

    recommendation = manager.get_agent_mode_recommendation("tmux-1")

    assert recommendation["should_suggest_agent_mode"] is True
    assert recommendation["reason"] == "codex"


def test_session_manager_rejects_snapshot_for_non_tmux_session():
    manager = SessionManager()
    manager.create_session_entry("build")

    with pytest.raises(ValueError, match="tmux-backed"):
        manager.capture_session_snapshot("web-does-not-matter")
```

**Step 2: Run the session-manager tests to verify they fail**

Run: `pytest tests/test_session_manager.py -v`

Expected: FAIL with missing capability methods.

**Step 3: Add the minimal capability layer**

Import the new helpers and add a small API surface.

```python
from src.tmux import (
    capture_tmux_pane,
    create_tmux_session,
    get_tmux_interaction_recommendation,
    send_tmux_key,
    tmux_session_exists,
    list_tmux_sessions,
)


def get_session_mode_capabilities(self, session_id: str) -> dict:
    record = self._resolve_record(session_id)
    return {
        "backend": record.backend,
        "supports_agent_mode": record.backend == "tmux" and bool(record.tmux_session_name),
        "tmux_session_name": record.tmux_session_name,
    }


def get_agent_mode_recommendation(self, session_id: str) -> dict:
    record = self._resolve_record(session_id)
    if record.backend != "tmux" or not record.tmux_session_name:
        return {
            "supports_agent_mode": False,
            "should_suggest_agent_mode": False,
            "reason": "Session is not tmux-backed",
            "signature": None,
        }
    return get_tmux_interaction_recommendation(record.tmux_session_name)


def capture_session_snapshot(self, session_id: str, *, lines: int = 80) -> str:
    record = self._resolve_record(session_id)
    if record.backend != "tmux" or not record.tmux_session_name:
        raise ValueError("Agent mode requires a tmux-backed session")
    return capture_tmux_pane(record.tmux_session_name, lines=lines)


def tail_session_output(self, session_id: str, *, lines: int = 20) -> str:
    snapshot = self.capture_session_snapshot(session_id, lines=max(lines, 80))
    return "\n".join(snapshot.splitlines()[-lines:])


async def send_exact_input(self, session_id: str, text: str) -> None:
    await self.send_input(session_id, text, newline=False, from_ai=False)


def send_special_key(self, session_id: str, key_name: str) -> None:
    record = self._resolve_record(session_id)
    if record.backend != "tmux" or not record.tmux_session_name:
        raise ValueError("Agent mode requires a tmux-backed session")
    send_tmux_key(record.tmux_session_name, key_name)
```

**Step 4: Run the focused session-manager tests**

Run: `pytest tests/test_session_manager.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/session_manager.py tests/test_session_manager.py
git commit -m "feat: add session manager agent-mode capabilities"
```

### Task 3: Add Telegram mode state and `/mode` plus `/status`

**Files:**
- Modify: `src/telegram_bot.py:35-129`
- Modify: `src/telegram_bot.py:403-426`
- Modify: `src/telegram_bot.py:520-571`
- Modify: `src/telegram_bot.py:696-838`
- Modify: `src/telegram_bot.py:849-926`
- Modify: `tests/test_telegram_bot.py:109-746`

**Step 1: Write the failing Telegram mode tests**

Add tests for default shell mode, switching to agent mode on tmux-backed sessions, and rejecting agent mode on normal sessions.

```python
@pytest.mark.asyncio
async def test_mode_status_defaults_to_shell(monkeypatch):
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/mode status")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["status"]))

    assert "Mode: shell" in update.message.replies[0][0]


@pytest.mark.asyncio
async def test_mode_agent_requires_tmux_support(monkeypatch):
    manager = FakeSessionManager()
    monkeypatch.setattr(telegram_bot, "session_manager", manager)

    update = FakeUpdate(777, "/mode agent")
    await telegram_bot.mode_command(update, SimpleNamespace(args=["agent"]))

    assert "requires a tmux-backed session" in update.message.replies[0][0]
```

Update `FakeSessionManager` with:

```python
def get_session_mode_capabilities(self, session_id: str):
    session = self.get_session_summary(session_id)
    return {
        "backend": session["backend"],
        "supports_agent_mode": session["backend"] == "tmux",
        "tmux_session_name": session["tmux_session_name"],
    }
```

**Step 2: Run the Telegram tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -v`

Expected: FAIL because `/mode` and `/status` do not exist yet.

**Step 3: Add Telegram mode state and command handlers**

Extend the bot state model and command specs.

```python
@dataclass
class TelegramUserSessions:
    current_alias: str = "main"
    sessions: dict[str, str] = field(default_factory=dict)
    last_outputs: dict[str, str] = field(default_factory=dict)
    session_modes: dict[str, str] = field(default_factory=dict)
    suggestion_dismissals: dict[str, bool] = field(default_factory=dict)
    last_suggested_signature: dict[str, str | None] = field(default_factory=dict)


def _get_session_mode(user_id: int, session_id: str) -> str:
    state = _get_user_sessions(user_id)
    return state.session_modes.get(session_id, "shell")


def _set_session_mode(user_id: int, session_id: str, mode: str) -> None:
    _get_user_sessions(user_id).session_modes[session_id] = mode
```

Add new command specs for `/mode` and `/status`, then implement:

```python
async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _get_current_session_id(update.effective_user.id)
    capabilities = _require_session_manager().get_session_mode_capabilities(session_id)
    action = context.args[0].lower() if context.args else "status"

    if action == "status":
        await update.message.reply_text(_render_mode_status(...))
        return

    if action == "agent" and not capabilities["supports_agent_mode"]:
        await update.message.reply_text("❌ Agent mode requires a tmux-backed session. Use /newtmux or /attachtmux.")
        return

    _set_session_mode(update.effective_user.id, session_id, action)
    await update.message.reply_text(f"Mode set to {action} for {session_id}")
```

Use `/status` as a Telegram session status view distinct from `/features`.

**Step 4: Run the focused Telegram tests**

Run: `pytest tests/test_telegram_bot.py -k "mode or status" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram mode and status commands"
```

### Task 4: Add `/snapshot`, `/tail`, `/send`, `/key`, and mode-aware message routing

**Files:**
- Modify: `src/telegram_bot.py:35-129`
- Modify: `src/telegram_bot.py:308-400`
- Modify: `src/telegram_bot.py:674-887`
- Modify: `tests/test_telegram_bot.py:334-746`

**Step 1: Write the failing routing and command tests**

Add tests that prove shell-mode messages still run as line commands, while agent-mode messages use exact paste plus Enter and expose agent commands.

```python
@pytest.mark.asyncio
async def test_handle_message_uses_exact_send_in_agent_mode(monkeypatch):
    manager = FakeSessionManager()
    manager.import_tmux_session("ops-shell", name="Ops Shell")
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    state = telegram_bot._get_user_sessions(777)
    state.current_alias = "Ops Shell"
    state.session_modes["tmux-1"] = "agent"

    update = FakeUpdate(777, "continue")
    await telegram_bot.handle_message(update, SimpleNamespace())

    assert manager.exact_inputs == [("tmux-1", "continue")]
    assert manager.special_keys == [("tmux-1", "enter")]


@pytest.mark.asyncio
async def test_snapshot_command_returns_tmux_capture(monkeypatch):
    manager = FakeSessionManager()
    manager.import_tmux_session("ops-shell", name="Ops Shell")
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    telegram_bot._get_user_sessions(777).current_alias = "Ops Shell"

    update = FakeUpdate(777, "/snapshot")
    await telegram_bot.snapshot_command(update, SimpleNamespace(args=[]))

    assert "Claude is waiting" in update.message.replies[0][0]
```

Update `FakeSessionManager` with:

```python
self.exact_inputs = []
self.special_keys = []
self.snapshots = {"tmux-1": "Claude is waiting\n> "}
self.tails = {"tmux-1": "Claude is waiting"}

async def send_exact_input(self, session_id: str, text: str):
    self.exact_inputs.append((session_id, text))

def send_special_key(self, session_id: str, key_name: str):
    self.special_keys.append((session_id, key_name))

def capture_session_snapshot(self, session_id: str, *, lines: int = 80):
    return self.snapshots[session_id]

def tail_session_output(self, session_id: str, *, lines: int = 20):
    return self.tails[session_id]
```

**Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -k "agent_mode or snapshot or tail or key or send" -v`

Expected: FAIL with missing commands and fake-manager methods.

**Step 3: Add the agent commands and route plain text by mode**

Implement commands:

```python
async def snapshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _get_current_session_id(update.effective_user.id)
    snapshot = _require_session_manager().capture_session_snapshot(session_id, lines=80)
    await _reply_in_chunks(update, f"```text\n{_strip_ansi(snapshot).strip()}\n```")


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _get_current_session_id(update.effective_user.id)
    text = " ".join(context.args)
    await _require_session_manager().send_exact_input(session_id, text)
    await update.message.reply_text("Sent text to session")


async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _get_current_session_id(update.effective_user.id)
    key_name = context.args[0].lower()
    _require_session_manager().send_special_key(session_id, key_name)
    await update.message.reply_text(f"Sent key {key_name}")
```

Update `handle_message()`:

```python
mode = _get_session_mode(user_id, session_id)
if mode == "agent":
    await manager.send_exact_input(session_id, command)
    manager.send_special_key(session_id, "enter")
    await update.message.reply_text("Sent to agent session")
    return
```

Do not remove shell-mode behavior.

**Step 4: Run the focused Telegram tests**

Run: `pytest tests/test_telegram_bot.py -k "agent_mode or snapshot or tail or key or send" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram agent-mode controls"
```

### Task 5: Add auto-suggest with inline actions and suppression

**Files:**
- Modify: `src/telegram_bot.py:127-130`
- Modify: `src/telegram_bot.py:265-305`
- Modify: `src/telegram_bot.py:809-838`
- Modify: `src/telegram_bot.py:841-887`
- Modify: `tests/test_telegram_bot.py:334-746`

**Step 1: Write the failing auto-suggest tests**

Add tests for suggestion display, `Switch`, `Not now`, `Don't suggest again`, and signature-change reset.

```python
@pytest.mark.asyncio
async def test_handle_message_suggests_agent_mode_once_for_interactive_tmux(monkeypatch):
    manager = FakeSessionManager()
    manager.import_tmux_session("ops-shell", name="Ops Shell")
    manager.recommendations["tmux-1"] = {
        "supports_agent_mode": True,
        "should_suggest_agent_mode": True,
        "reason": "codex",
        "signature": "sig-1",
    }
    monkeypatch.setattr(telegram_bot, "session_manager", manager)
    telegram_bot._get_user_sessions(777).current_alias = "Ops Shell"

    update = FakeUpdate(777, "pwd")
    await telegram_bot.handle_message(update, SimpleNamespace())
    await telegram_bot.handle_message(FakeUpdate(777, "pwd"), SimpleNamespace())

    replies = [text for text, _ in update.message.replies]
    assert any("Switch this session to agent mode?" in text for text in replies)
```

**Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -k "suggest" -v`

Expected: FAIL because no suggestion state or callback path exists yet.

**Step 3: Add the suggestion callback flow**

Add a dedicated callback prefix and a helper:

```python
AGENT_MODE_CALLBACK_PREFIX = "agent-mode:"


def _should_offer_agent_mode(user_id: int, session_id: str) -> dict | None:
    state = _get_user_sessions(user_id)
    recommendation = _require_session_manager().get_agent_mode_recommendation(session_id)
    if not recommendation["supports_agent_mode"] or not recommendation["should_suggest_agent_mode"]:
        return None
    if state.suggestion_dismissals.get(session_id):
        return None
    if state.last_suggested_signature.get(session_id) == recommendation["signature"]:
        return None
    state.last_suggested_signature[session_id] = recommendation["signature"]
    return recommendation
```

In `handle_message()`, after shell-mode command completion, call `_should_offer_agent_mode(...)` for tmux-backed sessions and send an inline keyboard with `Switch`, `Not now`, and `Don't suggest again`.

Handle callbacks in `handle_agent_mode_picker()`:

```python
if action == "switch":
    _set_session_mode(user_id, session_id, "agent")
elif action == "dismiss":
    state.last_suggested_signature[session_id] = signature
elif action == "mute":
    state.suggestion_dismissals[session_id] = True
```

Register the callback handler in `main()`.

**Step 4: Run the focused Telegram tests**

Run: `pytest tests/test_telegram_bot.py -k "suggest" -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add telegram agent-mode suggestions"
```

### Task 6: Run end-to-end verification and update help text

**Files:**
- Modify: `src/telegram_bot.py:35-114`
- Modify: `src/telegram_bot.py:403-426`
- Modify: `tests/test_telegram_bot.py:703-746`

**Step 1: Add the final help/autocomplete assertions**

Extend help and slash-command tests to cover the new commands.

```python
assert any(command.command == "mode" for command in commands)
assert any(command.command == "snapshot" for command in commands)
assert any(command.command == "tail" for command in commands)
assert "/mode [shell|agent|status]" in rendered
assert "/snapshot - Show the current tmux pane snapshot" in rendered
```

**Step 2: Run the Telegram tests to verify the docs fail first if needed**

Run: `pytest tests/test_telegram_bot.py -k "help or register_bot_commands" -v`

Expected: FAIL until help text and command registration are updated.

**Step 3: Finish help text and command registration**

Update `COMMAND_SPECS`, `_render_help()`, and handler registration in `main()` so every new command is documented and registered in the slash menu.

**Step 4: Run focused verification**

Run: `pytest tests/test_tmux.py tests/test_session_manager.py tests/test_telegram_bot.py -v`

Expected: PASS

**Step 5: Run broader verification**

Run: `pytest tests/test_telegram_bot.py tests/test_session_manager.py tests/test_tmux.py tests/test_main.py -v`

Expected: PASS

**Step 6: Check formatting and staged diff**

Run: `git diff --check`

Expected: no output

**Step 7: Commit**

```bash
git add src/tmux.py src/session_manager.py src/telegram_bot.py tests/test_tmux.py tests/test_session_manager.py tests/test_telegram_bot.py
git commit -m "feat: add telegram agent mode for tmux sessions"
```

## Notes for the Implementer

- Do not broaden agent mode beyond tmux in v1.
- Do not silently auto-switch into agent mode.
- Keep shell-mode routing unchanged unless a failing test proves a necessary adjustment.
- Prefer small helpers in `telegram_bot.py` over growing `handle_message()` into a monolith.
- Keep tmux subprocess calls isolated in `src/tmux.py`.
- Use explicit error strings in tests so user-facing behavior stays stable.
