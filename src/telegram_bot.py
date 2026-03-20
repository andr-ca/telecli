"""
Telegram bot integration
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import shlex
from dataclasses import dataclass, field
from types import SimpleNamespace

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from src.session_manager import SessionManager
from src.config import Config

logger = logging.getLogger(__name__)

# Global session manager
session_manager: SessionManager = None

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
PROMPT_LINE_RE = re.compile(r"^.*[$#>] ?$")


COMMAND_SPECS = [
    {
        "command": "start",
        "description": "Show welcome message",
        "usage": "/start",
        "help": "Show the current Telegram session and a quick TeleCLI intro.",
    },
    {
        "command": "help",
        "description": "Show command help",
        "usage": "/help",
        "help": "Show command descriptions, examples, and autocomplete guidance.",
    },
    {
        "command": "reset",
        "description": "Reset current session",
        "usage": "/reset",
        "help": "Close the active runtime for the current session.",
    },
    {
        "command": "sessions",
        "description": "List sessions and tmux",
        "usage": "/sessions",
        "help": "Show Telegram aliases, known TeleCLI sessions, and machine tmux sessions.",
    },
    {
        "command": "newsession",
        "description": "Create named session",
        "usage": "/newsession <name>",
        "help": "Create a new regular TeleCLI session and switch to it.",
    },
    {
        "command": "usesession",
        "description": "Switch session",
        "usage": "/usesession [name|session-id]",
        "help": "Switch to a Telegram alias or an existing TeleCLI session, or omit the argument to pick one.",
    },
    {
        "command": "attachtmux",
        "description": "Import tmux session",
        "usage": "/attachtmux <tmux-name> [alias]",
        "help": "Attach a machine tmux session into TeleCLI and switch to it.",
    },
    {
        "command": "newtmux",
        "description": "Create tmux session",
        "usage": "/newtmux <tmux-name> [alias]",
        "help": "Create a new tmux session, import it, and switch to it.",
    },
    {
        "command": "detach",
        "description": "Detach tmux session",
        "usage": "/detach",
        "help": "Detach the current tmux-backed TeleCLI session without forgetting it.",
    },
    {
        "command": "repeat",
        "description": "Repeat last output",
        "usage": "/repeat",
        "help": "Repeat the last terminal output shown in Telegram for the current session.",
    },
    {
        "command": "screen",
        "description": "Show current screen",
        "usage": "/screen",
        "help": "Show what is currently visible in the active tmux pane.",
    },
    {
        "command": "watch",
        "description": "Monitor screen changes",
        "usage": "/watch <on|off|status>",
        "help": "Enable or disable Telegram push updates when the active tmux screen changes significantly.",
    },
    {
        "command": "snapshot",
        "description": "Show tmux snapshot",
        "usage": "/snapshot",
        "help": "Show the current tmux pane snapshot for the active session.",
    },
    {
        "command": "tail",
        "description": "Show recent output",
        "usage": "/tail [lines]",
        "help": "Show recent tmux pane output for the active session.",
    },
    {
        "command": "send",
        "description": "Send exact text",
        "usage": "/send <text>",
        "help": "Paste exact text into the active session without shell parsing.",
    },
    {
        "command": "key",
        "description": "Send a special key",
        "usage": "/key <enter|esc|tab|up|down|left|right|backspace|ctrl-c|ctrl-d>",
        "help": "Send a named special key to the active session.",
    },
    {
        "command": "continue",
        "description": "Send continue",
        "usage": "/continue",
        "help": "Send `continue` and press Enter in the active session.",
    },
    {
        "command": "interrupt",
        "description": "Send Ctrl+C",
        "usage": "/interrupt",
        "help": "Send Ctrl+C to interrupt the active session.",
    },
    {
        "command": "features",
        "description": "Show feature status",
        "usage": "/features",
        "help": "Show AI proxy and Claude auto-continue status for the current session.",
    },
    {
        "command": "mode",
        "description": "Set Telegram mode",
        "usage": "/mode <shell|agent|status>",
        "help": "Switch Telegram interaction mode or show the current mode status.",
    },
    {
        "command": "status",
        "description": "Show session status",
        "usage": "/status",
        "help": "Show the current Telegram mode and active session backend details.",
    },
    {
        "command": "ai",
        "description": "Manage AI proxy",
        "usage": "/ai <on|off|status> [provider]",
        "help": "Enable, disable, or inspect the AI proxy for the current session.",
    },
    {
        "command": "ccauto",
        "description": "Manage Claude auto-continue",
        "usage": "/ccauto <on|off|status>",
        "help": "Enable, disable, or inspect Claude Code auto-continue for the current session.",
    },
]
KNOWN_BOT_COMMANDS = {spec["command"] for spec in COMMAND_SPECS}


@dataclass
class TelegramUserSessions:
    """Telegram-specific session aliases for a single user."""

    current_alias: str = "main"
    sessions: dict[str, str] = field(default_factory=dict)
    last_outputs: dict[str, str] = field(default_factory=dict)
    session_modes: dict[str, str] = field(default_factory=dict)
    screen_watches: dict[str, "ScreenWatchState"] = field(default_factory=dict)
    suggestion_dismissals: dict[str, bool] = field(default_factory=dict)
    last_suggested_signature: dict[str, str] = field(default_factory=dict)


@dataclass
class ScreenWatchState:
    enabled: bool = False
    chat_id: int | None = None
    last_delivered_screen: str | None = None
    pending_screen: str | None = None
    pending_count: int = 0


_telegram_user_sessions: dict[int, TelegramUserSessions] = {}
SESSION_PICKER_CALLBACK_PREFIX = "use-session:"
FEATURE_PICKER_CALLBACK_PREFIX = "feature:"
AGENT_MODE_CALLBACK_PREFIX = "agent-mode:"
COMMAND_PICKER_CALLBACK_PREFIX = "command:"
SCREEN_WATCH_POLL_INTERVAL_SECONDS = 2.0
SCREEN_WATCH_STABLE_POLLS = 2
KEY_PICKER_LAYOUT = [
    [("Enter", "enter"), ("Esc", "esc"), ("Tab", "tab")],
    [("Up", "up"), ("Down", "down"), ("Left", "left"), ("Right", "right")],
    [("Backspace", "backspace"), ("Ctrl+C", "ctrl-c"), ("Ctrl+D", "ctrl-d")],
]


def set_session_manager(manager: SessionManager | None) -> None:
    """Inject a session manager instance for the Telegram bot runtime."""
    global session_manager
    session_manager = manager


def _require_session_manager() -> SessionManager:
    if session_manager is None:
        raise RuntimeError("Telegram session manager is not initialized")
    return session_manager


def _get_user_sessions(user_id: int) -> TelegramUserSessions:
    state = _telegram_user_sessions.get(user_id)
    if state:
        return state

    state = TelegramUserSessions(sessions={"main": str(user_id)})
    _telegram_user_sessions[user_id] = state
    return state


def _get_current_session_id(user_id: int) -> str:
    state = _get_user_sessions(user_id)
    return state.sessions[state.current_alias]


def _get_session_mode(user_id: int, session_id: str) -> str:
    state = _get_user_sessions(user_id)
    return state.session_modes.get(session_id, "shell")


def _set_session_mode(user_id: int, session_id: str, mode: str) -> None:
    state = _get_user_sessions(user_id)
    state.session_modes[session_id] = mode


def _find_alias_for_session(state: TelegramUserSessions, session_id: str) -> str | None:
    for alias, existing_session_id in state.sessions.items():
        if existing_session_id == session_id:
            return alias
    return None


def _allocate_alias(state: TelegramUserSessions, session_id: str, preferred_alias: str | None = None) -> str:
    existing_alias = _find_alias_for_session(state, session_id)
    if existing_alias:
        return existing_alias

    alias = (preferred_alias or session_id).strip()
    if not alias:
        alias = session_id

    if alias in state.sessions and state.sessions[alias] != session_id:
        suffix = 2
        candidate = f"{alias}-{suffix}"
        while candidate in state.sessions and state.sessions[candidate] != session_id:
            suffix += 1
            candidate = f"{alias}-{suffix}"
        alias = candidate

    state.sessions[alias] = session_id
    return alias


def _resolve_known_session(manager: SessionManager, selector: str) -> dict | None:
    clean_selector = selector.strip()
    if not clean_selector:
        return None

    sessions = manager.list_sessions()
    for session in sessions:
        if session["id"] == clean_selector:
            return session

    selector_lower = clean_selector.lower()
    for session in sessions:
        if session["name"].lower() == selector_lower:
            return session

    return None


def _render_session_inventory(user_id: int) -> str:
    state = _get_user_sessions(user_id)
    manager = _require_session_manager()

    lines = [f"Current session: {state.current_alias} ({state.sessions[state.current_alias]})", "", "Telegram aliases:"]
    for alias, session_id in sorted(state.sessions.items()):
        marker = "*" if alias == state.current_alias else "-"
        lines.append(f"{marker} {alias} -> {session_id}")

    lines.extend(["", "Known TeleCLI sessions:"])
    for session in manager.list_sessions():
        details = [
            f"- {session['name']} [{session['backend']}]",
            f"id={session['id']}",
            f"active={'yes' if session['is_active'] else 'no'}",
            f"available={'yes' if session['available'] else 'no'}",
        ]
        if session.get("tmux_session_name"):
            details.append(f"tmux={session['tmux_session_name']}")
        lines.append(" ".join(details))

    if hasattr(manager, "list_machine_tmux_sessions"):
        machine_tmux_sessions = manager.list_machine_tmux_sessions()
        if machine_tmux_sessions:
            lines.extend(["", "Machine tmux sessions:"])
            for session in machine_tmux_sessions:
                line = (
                    f"- {session['name']} "
                    f"(windows={session['windows']}, "
                    f"attached={'yes' if session['attached'] else 'no'}, "
                    f"imported={'yes' if session.get('imported') else 'no'}"
                )
                if session.get("imported") and session.get("imported_name"):
                    line += f", imported as {session['imported_name']}"
                line += ")"
                lines.append(line)

    return "\n".join(lines)


def _get_session_picker_entries(user_id: int) -> list[tuple[str, str]]:
    state = _get_user_sessions(user_id)
    manager = _require_session_manager()
    entries: list[tuple[str, str]] = []
    seen_session_ids: set[str] = set()

    for alias, session_id in sorted(state.sessions.items()):
        entries.append((alias, session_id))
        seen_session_ids.add(session_id)

    for session in manager.list_sessions():
        session_id = session["id"]
        if session_id in seen_session_ids:
            continue
        entries.append((session["name"], session_id))
        seen_session_ids.add(session_id)

    return entries


def _build_session_picker_markup(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                label,
                callback_data=f"{SESSION_PICKER_CALLBACK_PREFIX}{session_id}",
            )
        ]
        for label, session_id in _get_session_picker_entries(user_id)
    ]
    keyboard.append(
        [InlineKeyboardButton("Cancel", callback_data=f"{SESSION_PICKER_CALLBACK_PREFIX}cancel")]
    )
    return InlineKeyboardMarkup(keyboard)


def _build_ai_picker_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Status", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ai:status")],
            [
                InlineKeyboardButton("Enable Gemini", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ai:on:gemini-cli"),
                InlineKeyboardButton("Enable Claude", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ai:on:claude-cli"),
            ],
            [InlineKeyboardButton("Disable", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ai:off")],
            [InlineKeyboardButton("Cancel", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}cancel")],
        ]
    )


def _build_ccauto_picker_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Status", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ccauto:status")],
            [
                InlineKeyboardButton("Enable", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ccauto:on"),
                InlineKeyboardButton("Disable", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}ccauto:off"),
            ],
            [InlineKeyboardButton("Cancel", callback_data=f"{FEATURE_PICKER_CALLBACK_PREFIX}cancel")],
        ]
    )


def _build_agent_mode_picker_markup(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Switch", callback_data=f"{AGENT_MODE_CALLBACK_PREFIX}switch:{session_id}")],
            [InlineKeyboardButton("Not now", callback_data=f"{AGENT_MODE_CALLBACK_PREFIX}dismiss:{session_id}")],
            [InlineKeyboardButton("Don't suggest again", callback_data=f"{AGENT_MODE_CALLBACK_PREFIX}mute:{session_id}")],
        ]
    )


def _build_mode_picker_markup(session_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Status", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}mode:{session_id}:status"),
            InlineKeyboardButton("Shell", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}mode:{session_id}:shell"),
        ]
    ]
    capabilities = _require_session_manager().get_session_mode_capabilities(session_id)
    if capabilities.get("supports_agent_mode"):
        keyboard.append(
            [InlineKeyboardButton("Agent", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}mode:{session_id}:agent")]
        )
    keyboard.append([InlineKeyboardButton("Cancel", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}mode:{session_id}:cancel")])
    return InlineKeyboardMarkup(keyboard)


def _build_key_picker_markup(session_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(label, callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}key:{session_id}:{key_name}")
            for label, key_name in row
        ]
        for row in KEY_PICKER_LAYOUT
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}key:{session_id}:cancel")])
    return InlineKeyboardMarkup(keyboard)


def _build_watch_picker_markup(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Status", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}watch:{session_id}:status"),
                InlineKeyboardButton("Enable", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}watch:{session_id}:on"),
                InlineKeyboardButton("Disable", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}watch:{session_id}:off"),
            ],
            [InlineKeyboardButton("Cancel", callback_data=f"{COMMAND_PICKER_CALLBACK_PREFIX}watch:{session_id}:cancel")],
        ]
    )


def _strip_ansi(text: str) -> str:
    text = ANSI_ESCAPE_RE.sub("", text)
    text = text.replace("\r", "\n")
    return CONTROL_CHAR_RE.sub("", text)


def _clean_screen_text(text: str) -> str:
    """Normalize a terminal screen capture for Telegram display."""
    clean = _strip_ansi(text)
    lines = clean.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    rendered = "\n".join(lines)
    return rendered or "(screen is empty)"


def _format_command_output(command: str, output: str) -> str:
    clean = _strip_ansi(output)
    lines = [line.rstrip() for line in clean.splitlines()]
    lines = [line for line in lines if line.strip()]

    if lines and lines[0].strip() == command.strip():
        lines = lines[1:]
    if lines and PROMPT_LINE_RE.match(lines[-1]):
        lines = lines[:-1]

    rendered = "\n".join(lines).strip()
    return rendered or "(no new output)"


def _chunk_has_meaningful_output(command: str, chunk: str) -> bool:
    """Return True when a chunk contains output beyond prompt and command echo."""
    clean = _strip_ansi(chunk)
    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == command.strip():
            continue
        if PROMPT_LINE_RE.match(line):
            continue
        return True
    return False


async def _reply_in_chunks(update: Update, text: str) -> None:
    for start in range(0, len(text), 4000):
        await update.message.reply_text(text[start:start + 4000])


async def _reply_screen(update: Update, screen_text: str) -> None:
    clean = _clean_screen_text(screen_text)
    for start in range(0, len(clean), 3500):
        chunk = clean[start:start + 3500]
        await update.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode="HTML")


async def _send_screen_via_bot(bot, chat_id: int, screen_text: str) -> None:
    clean = _clean_screen_text(screen_text)
    for start in range(0, len(clean), 3500):
        chunk = clean[start:start + 3500]
        await bot.send_message(chat_id=chat_id, text=f"<pre>{html.escape(chunk)}</pre>", parse_mode="HTML")


async def _edit_query_with_screen(query, screen_text: str) -> None:
    clean = _clean_screen_text(screen_text)
    chunks = [clean[start:start + 3500] for start in range(0, len(clean), 3500)] or ["(screen is empty)"]
    await query.edit_message_text(f"<pre>{html.escape(chunks[0])}</pre>", parse_mode="HTML")
    for chunk in chunks[1:]:
        await query.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode="HTML")


async def _call_blocking_manager_method(method, *args, **kwargs):
    return await asyncio.to_thread(method, *args, **kwargs)


async def _reply_with_current_screen(
    update: Update,
    session_id: str,
    *,
    fallback_text: str | None = None,
    delay_seconds: float = 0.05,
) -> None:
    manager = _require_session_manager()
    capabilities = manager.get_session_mode_capabilities(session_id)
    if not capabilities.get("supports_agent_mode"):
        if fallback_text is not None:
            await update.message.reply_text(fallback_text)
        return

    if delay_seconds:
        await asyncio.sleep(delay_seconds)

    try:
        screen = await _call_blocking_manager_method(manager.capture_session_screen, session_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    _mark_screen_delivered(update.effective_user.id, session_id, screen)
    await _reply_screen(update, screen)


async def _edit_query_with_current_screen(
    query,
    session_id: str,
    *,
    fallback_text: str | None = None,
    delay_seconds: float = 0.05,
) -> None:
    manager = _require_session_manager()
    capabilities = manager.get_session_mode_capabilities(session_id)
    if not capabilities.get("supports_agent_mode"):
        if fallback_text is not None:
            await query.edit_message_text(fallback_text)
        return

    if delay_seconds:
        await asyncio.sleep(delay_seconds)

    try:
        screen = await _call_blocking_manager_method(manager.capture_session_screen, session_id)
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")
        return

    _mark_screen_delivered(query.from_user.id, session_id, screen)
    await _edit_query_with_screen(query, screen)


def _get_screen_watch_state(user_id: int, session_id: str) -> ScreenWatchState:
    state = _get_user_sessions(user_id)
    return state.screen_watches.setdefault(session_id, ScreenWatchState())


def _mark_screen_delivered(user_id: int, session_id: str, screen_text: str) -> None:
    watch_state = _get_screen_watch_state(user_id, session_id)
    clean = _clean_screen_text(screen_text)
    watch_state.last_delivered_screen = clean
    watch_state.pending_screen = None
    watch_state.pending_count = 0


def _get_watch_status_text(user_id: int, session_id: str) -> str:
    watch_state = _get_screen_watch_state(user_id, session_id)
    return f"Screen watch: {'on' if watch_state.enabled else 'off'} for {session_id}"


async def _run_watch_action(user_id: int, session_id: str, action: str, *, chat_id: int | None = None) -> str:
    manager = _require_session_manager()
    capabilities = manager.get_session_mode_capabilities(session_id)
    if not capabilities.get("supports_agent_mode"):
        return "❌ Screen watch requires a tmux-backed session. Use /newtmux or /attachtmux."

    watch_state = _get_screen_watch_state(user_id, session_id)
    if action == "status":
        return _get_watch_status_text(user_id, session_id)

    if action == "on":
        screen = await _call_blocking_manager_method(manager.capture_session_screen, session_id)
        watch_state.enabled = True
        watch_state.chat_id = chat_id
        _mark_screen_delivered(user_id, session_id, screen)
        return f"Screen watch enabled for {session_id}"

    if action == "off":
        watch_state.enabled = False
        watch_state.pending_screen = None
        watch_state.pending_count = 0
        return f"Screen watch disabled for {session_id}"

    return "Usage: /watch <on|off|status>"


async def _run_screen_watch_tick(bot) -> None:
    manager = _require_session_manager()
    for user_id, state in list(_telegram_user_sessions.items()):
        for session_id, watch_state in list(state.screen_watches.items()):
            if not watch_state.enabled:
                continue

            capabilities = manager.get_session_mode_capabilities(session_id)
            if not capabilities.get("supports_agent_mode"):
                continue

            try:
                screen = await _call_blocking_manager_method(manager.capture_session_screen, session_id)
            except Exception as e:
                logger.debug("Skipping screen watch tick for %s/%s: %s", user_id, session_id, e)
                continue

            clean = _clean_screen_text(screen)
            if clean == watch_state.last_delivered_screen:
                watch_state.pending_screen = None
                watch_state.pending_count = 0
                continue

            if clean == watch_state.pending_screen:
                watch_state.pending_count += 1
            else:
                watch_state.pending_screen = clean
                watch_state.pending_count = 1

            if watch_state.pending_count < SCREEN_WATCH_STABLE_POLLS:
                continue

            target_chat_id = watch_state.chat_id if watch_state.chat_id is not None else user_id
            await _send_screen_via_bot(bot, target_chat_id, clean)
            _mark_screen_delivered(user_id, session_id, clean)


async def _screen_watch_loop(bot) -> None:
    try:
        while True:
            await _run_screen_watch_tick(bot)
            await asyncio.sleep(SCREEN_WATCH_POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        raise


def _build_bot_commands() -> list[BotCommand]:
    return [BotCommand(spec["command"], spec["description"]) for spec in COMMAND_SPECS]


async def _register_bot_commands(bot) -> None:
    await bot.set_my_commands(_build_bot_commands())


async def _execute_session_command(session_id: str, command: str) -> str:
    manager = _require_session_manager()
    session = await manager.get_session(session_id)
    baseline = session.get_recent_output()
    baseline_remaining = len(baseline)
    stream = manager.get_output_stream(session_id)
    stream_iter = stream.__aiter__()
    collected: list[str] = []
    saw_meaningful_output = False

    try:
        await manager.send_input(session_id, command, newline=True, from_ai=False)

        while True:
            # Some CLI tools, including ccusage, echo the command immediately but only render
            # useful output later. Keep the longer startup timeout until we see post-echo content.
            timeout = (
                Config.TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS
                if not saw_meaningful_output
                else Config.TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS
            )
            try:
                chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=timeout)
            except asyncio.TimeoutError:
                break
            except StopAsyncIteration:
                break

            if baseline_remaining:
                if len(chunk) <= baseline_remaining:
                    baseline_remaining -= len(chunk)
                    continue
                chunk = chunk[baseline_remaining:]
                baseline_remaining = 0

            if not chunk:
                continue

            collected.append(chunk)
            if not saw_meaningful_output and _chunk_has_meaningful_output(command, chunk):
                saw_meaningful_output = True
    finally:
        await stream.aclose()

    return _format_command_output(command, "".join(collected))


def _render_help() -> str:
    lines = [
        "TeleCLI - Terminal access via Telegram",
        "",
        "Use Telegram's / menu to autocomplete commands.",
        "In shell mode, non-command messages run as shell commands.",
        "In agent mode, non-command messages are pasted into interactive tmux sessions.",
        "",
        "Commands:",
    ]
    for spec in COMMAND_SPECS:
        lines.append(f"{spec['usage']} - {spec['help']}")

    lines.extend(
        [
            "",
            "Examples:",
            "/newsession build",
            "/attachtmux ops-shell Ops Shell",
            "/newtmux pairing-shell Pairing Shell",
            "/usesession build",
            "/repeat",
        ]
    )
    return "\n".join(lines)


def _parse_known_bot_command(text: str) -> tuple[str, list[str]] | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped[1:].split(maxsplit=1)
    if not parts:
        return None

    command_name = parts[0].split("@", 1)[0].lower()
    if command_name not in KNOWN_BOT_COMMANDS:
        return None

    args_text = parts[1] if len(parts) > 1 else ""
    if not args_text:
        return command_name, []

    try:
        args = shlex.split(args_text)
    except ValueError:
        args = args_text.split()
    return command_name, args


def is_telegram_user_allowed(user_id: int) -> bool:
    """Check if Telegram user is in whitelist"""
    if not Config.ALLOWED_TELEGRAM_USERS:
        return True  # Whitelist disabled

    allowed_ids = set(
        int(uid.strip()) for uid in Config.ALLOWED_TELEGRAM_USERS.split(',')
        if uid.strip()
    )

    return user_id in allowed_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user_id = update.effective_user.id

    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot")
        logger.warning(f"Unauthorized Telegram user: {user_id}")
        return

    state = _get_user_sessions(user_id)
    session_id = state.sessions[state.current_alias]
    await update.message.reply_text(
        f"Welcome to TeleCLI! Your current Telegram session is `{state.current_alias}` ({session_id}).\n\n"
        f"{_render_help()}"
    )
    logger.info(f"User {user_id} started bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text(_render_help())


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    user_id_str = _get_current_session_id(user_id)
    try:
        await _require_session_manager().close_session(user_id_str)
        await update.message.reply_text("Session reset successfully")
        logger.info(f"User {user_id} reset session {user_id_str}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error resetting session: {str(e)}")
        logger.error(f"Error resetting session for {user_id_str}: {e}")


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List Telegram aliases, known TeleCLI sessions, and machine tmux sessions."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await _reply_in_chunks(update, _render_session_inventory(user_id))


async def newsession_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create and switch to a new named Telegram session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text("Usage: /newsession <name>")
        return

    alias = " ".join(context.args).strip()
    if not alias:
        await update.message.reply_text("Session name cannot be empty")
        return

    state = _get_user_sessions(user_id)
    if alias in state.sessions:
        await update.message.reply_text(f"Session '{alias}' already exists")
        return

    session = _require_session_manager().create_session_entry(alias)
    state.sessions[alias] = session["id"]
    state.current_alias = alias
    await update.message.reply_text(f"Created and switched to session '{alias}'")


async def usesession_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to an existing Telegram session alias."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(
            "Pick a session to switch to:",
            reply_markup=_build_session_picker_markup(user_id),
        )
        return

    selector = " ".join(context.args).strip()
    state = _get_user_sessions(user_id)
    if selector in state.sessions:
        alias = selector
    else:
        session = _resolve_known_session(_require_session_manager(), selector)
        if not session:
            await update.message.reply_text(f"Unknown session '{selector}'")
            return
        alias = _allocate_alias(state, session["id"], preferred_alias=session["name"])

    state.current_alias = alias
    await update.message.reply_text(f"Switched to session '{alias}'")


async def handle_session_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button picks for /usesession."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_telegram_user_allowed(user_id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    await query.answer()

    payload = query.data.removeprefix(SESSION_PICKER_CALLBACK_PREFIX)
    if payload == "cancel":
        await query.edit_message_text("Session switch cancelled")
        return

    state = _get_user_sessions(user_id)
    alias = _find_alias_for_session(state, payload)
    if alias is None:
        session = _resolve_known_session(_require_session_manager(), payload)
        if not session:
            await query.edit_message_text(f"Unknown session '{payload}'")
            return
        alias = _allocate_alias(state, session["id"], preferred_alias=session["name"])

    state.current_alias = alias
    await query.edit_message_text(f"Switched to session '{alias}'")


async def attachtmux_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Import an existing tmux session and switch to it."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text("Usage: /attachtmux <tmux-name> [alias]")
        return

    tmux_name = context.args[0].strip()
    alias_hint = " ".join(context.args[1:]).strip() or None
    state = _get_user_sessions(user_id)

    try:
        session = _require_session_manager().import_tmux_session(tmux_name, name=alias_hint)
        alias = _allocate_alias(state, session["id"], preferred_alias=alias_hint or session["name"])
        state.current_alias = alias
        await update.message.reply_text(
            f"Attached tmux session '{tmux_name}' as '{alias}' ({session['id']})"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error attaching tmux session: {str(e)}")


async def newtmux_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a tmux session and switch to it."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text("Usage: /newtmux <tmux-name> [alias]")
        return

    tmux_name = context.args[0].strip()
    alias_hint = " ".join(context.args[1:]).strip() or None
    state = _get_user_sessions(user_id)

    try:
        session = _require_session_manager().create_tmux_session_entry(tmux_name, name=alias_hint)
        alias = _allocate_alias(state, session["id"], preferred_alias=alias_hint or session["name"])
        state.current_alias = alias
        await update.message.reply_text(
            f"Created tmux session '{tmux_name}' as '{alias}' ({session['id']})"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error creating tmux session: {str(e)}")


async def detach_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detach the current tmux-backed session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    manager = _require_session_manager()
    session = manager.get_session_summary(session_id)
    if session["backend"] != "tmux":
        await update.message.reply_text("❌ Only tmux-backed sessions can be detached")
        return

    try:
        await manager.detach_tmux_session(session_id)
        await update.message.reply_text(f"Detached tmux session '{session['tmux_session_name']}'")
    except Exception as e:
        await update.message.reply_text(f"❌ Error detaching tmux session: {str(e)}")


async def repeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Repeat the last rendered terminal output for the current session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    state = _get_user_sessions(user_id)
    session_id = _get_current_session_id(user_id)
    last_output = state.last_outputs.get(session_id, "")

    if not last_output:
        session = await _require_session_manager().get_session(session_id)
        last_output = _format_command_output("", session.get_recent_output())

    if not last_output or last_output == "(no new output)":
        await update.message.reply_text("No previous terminal output recorded for this session")
        return

    await _reply_in_chunks(update, last_output)


async def snapshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current tmux pane snapshot for the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    try:
        snapshot = await _call_blocking_manager_method(
            _require_session_manager().capture_session_snapshot,
            session_id,
            lines=80,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_screen(update, snapshot)


async def screen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the currently visible tmux pane."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    try:
        screen = await _call_blocking_manager_method(_require_session_manager().capture_session_screen, session_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    _mark_screen_delivered(user_id, session_id, screen)
    await _reply_screen(update, screen)


async def tail_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the most recent tmux output lines for the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    lines = 20
    if context.args:
        try:
            lines = max(1, int(context.args[0]))
        except ValueError:
            await update.message.reply_text("Usage: /tail [lines]")
            return

    try:
        tail_output = await _call_blocking_manager_method(
            _require_session_manager().tail_session_output,
            session_id,
            lines=lines,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_in_chunks(update, _strip_ansi(tail_output))


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable or disable background screen monitoring for the active tmux session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    capabilities = _require_session_manager().get_session_mode_capabilities(session_id)
    if not capabilities.get("supports_agent_mode"):
        await update.message.reply_text("❌ Screen watch requires a tmux-backed session. Use /newtmux or /attachtmux.")
        return

    if not context.args:
        await update.message.reply_text(
            f"Choose screen watch action for {session_id}.\n{_get_watch_status_text(user_id, session_id)}",
            reply_markup=_build_watch_picker_markup(session_id),
        )
        return

    try:
        response = await _run_watch_action(
            user_id,
            session_id,
            context.args[0].lower(),
            chat_id=update.effective_chat.id,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await update.message.reply_text(response)


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send exact text into the active session without newline semantics."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text("Usage: /send <text>")
        return

    session_id = _get_current_session_id(user_id)
    text = " ".join(context.args)
    try:
        await _require_session_manager().send_exact_input(session_id, text)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_with_current_screen(update, session_id, fallback_text="Sent text to session")


async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a named special key to the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    capabilities = _require_session_manager().get_session_mode_capabilities(session_id)
    if not capabilities.get("supports_agent_mode"):
        await update.message.reply_text("❌ Agent mode requires a tmux-backed session. Use /newtmux or /attachtmux.")
        return

    if not context.args:
        await update.message.reply_text(
            f"Choose key to send to {session_id}.",
            reply_markup=_build_key_picker_markup(session_id),
        )
        return

    key_name = context.args[0].lower()
    try:
        _require_session_manager().send_special_key(session_id, key_name)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_with_current_screen(update, session_id, fallback_text=f"Sent key {key_name}")


async def continue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send `continue` followed by Enter to the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    try:
        manager = _require_session_manager()
        await manager.send_exact_input(session_id, "continue")
        manager.send_special_key(session_id, "enter")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_with_current_screen(update, session_id, fallback_text="Sent continue to session")


async def interrupt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Ctrl+C to the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    try:
        _require_session_manager().send_special_key(session_id, "ctrl-c")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await _reply_with_current_screen(update, session_id, fallback_text="Sent interrupt to session")


def _render_mode_status_text(user_id: int, session_id: str | None = None) -> str:
    state = _get_user_sessions(user_id)
    session_id = session_id or _get_current_session_id(user_id)
    manager = _require_session_manager()
    session = manager.get_session_summary(session_id)
    capabilities = manager.get_session_mode_capabilities(session_id)
    current_alias = next((alias for alias, known_id in state.sessions.items() if known_id == session_id), session_id)
    lines = [
        f"Current session: {current_alias} ({session_id})",
        f"Mode: {_get_session_mode(user_id, session_id)}",
        f"Backend: {session['backend']}",
        f"Agent mode supported: {'yes' if capabilities['supports_agent_mode'] else 'no'}",
    ]
    if session.get("tmux_session_name"):
        lines.append(f"tmux target: {session['tmux_session_name']}")
    return "\n".join(lines)


def _run_mode_action(user_id: int, session_id: str, action: str) -> str:
    manager = _require_session_manager()
    if action == "status":
        return _render_mode_status_text(user_id, session_id)

    if action not in {"shell", "agent"}:
        return "Usage: /mode <shell|agent|status>"

    capabilities = manager.get_session_mode_capabilities(session_id)
    if action == "agent" and not capabilities["supports_agent_mode"]:
        return "❌ Agent mode requires a tmux-backed session. Use /newtmux or /attachtmux."

    _set_session_mode(user_id, session_id, action)
    return f"Mode set to {action} for {session_id}"


def _get_agent_mode_suggestion(user_id: int, session_id: str) -> dict | None:
    state = _get_user_sessions(user_id)
    if state.suggestion_dismissals.get(session_id):
        return None

    recommendation = _require_session_manager().get_agent_mode_recommendation(session_id)
    if not recommendation.get("supports_agent_mode") or not recommendation.get("should_suggest_agent_mode"):
        return None

    signature = recommendation.get("signature")
    if not signature or state.last_suggested_signature.get(session_id) == signature:
        return None

    state.last_suggested_signature[session_id] = signature
    return recommendation


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage Telegram shell vs agent mode for the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    if not context.args:
        await update.message.reply_text(
            f"Choose Telegram mode action for {session_id}.\n{_render_mode_status_text(user_id, session_id)}",
            reply_markup=_build_mode_picker_markup(session_id),
        )
        return

    await update.message.reply_text(_run_mode_action(user_id, session_id, context.args[0].lower()))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current Telegram session mode and backend details."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text(_render_mode_status_text(user_id))


async def handle_agent_mode_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline picks for agent-mode suggestions."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_telegram_user_allowed(user_id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    await query.answer()

    payload = query.data.removeprefix(AGENT_MODE_CALLBACK_PREFIX)
    parts = payload.split(":", 1)
    action = parts[0] if parts else ""
    session_id = parts[1] if len(parts) > 1 else _get_current_session_id(user_id)
    state = _get_user_sessions(user_id)

    if action == "switch":
        capabilities = _require_session_manager().get_session_mode_capabilities(session_id)
        if not capabilities["supports_agent_mode"]:
            await query.edit_message_text("❌ Agent mode requires a tmux-backed session. Use /newtmux or /attachtmux.")
            return
        _set_session_mode(user_id, session_id, "agent")
        await query.edit_message_text(f"Mode set to agent for {session_id}")
        return

    if action == "dismiss":
        await query.edit_message_text("Agent mode suggestion dismissed")
        return

    if action == "mute":
        state.suggestion_dismissals[session_id] = True
        await query.edit_message_text("Agent mode suggestions muted for this session")
        return

    await query.edit_message_text("Unknown agent mode action")


async def features_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Telegram-manageable feature status for the active session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    state = _get_user_sessions(user_id)
    session_id = state.sessions[state.current_alias]
    manager = _require_session_manager()
    ai_proxy = manager.get_ai_proxy(session_id)
    ai_status = ai_proxy.get_status() if ai_proxy else {"enabled": False, "provider": None}
    ccauto = manager.get_claude_code_auto_continue(session_id)
    ccauto_status = ccauto.get_status() if ccauto else {"enabled": False, "waiting": False}

    lines = [
        f"Current session: {state.current_alias} ({session_id})",
        f"AI Proxy: {'on' if ai_status.get('enabled') else 'off'}"
        + (
            f" ({ai_status.get('provider')})" if ai_status.get("enabled") and ai_status.get("provider") else ""
        ),
        f"Claude Auto-Continue: {'on' if ccauto_status.get('enabled') else 'off'}",
    ]
    await update.message.reply_text("\n".join(lines))


def _get_ai_status_text(session_id: str) -> str:
    ai_proxy = _require_session_manager().get_ai_proxy(session_id)
    if ai_proxy and ai_proxy.get_status().get("enabled"):
        status = ai_proxy.get_status()
        return f"AI proxy is on for {session_id} ({status.get('provider')})"
    return f"AI proxy is off for {session_id}"


async def _run_ai_action(session_id: str, action: str, provider: str | None = None) -> str:
    manager = _require_session_manager()

    if action in {"status", "show"}:
        return _get_ai_status_text(session_id)

    if action in {"on", "enable"}:
        success = await manager.enable_ai_proxy(session_id, provider_name=provider)
        return f"AI proxy {'enabled' if success else 'failed'} for {session_id}"

    if action in {"off", "disable"}:
        await manager.disable_ai_proxy(session_id)
        return f"AI proxy disabled for {session_id}"

    return "Usage: /ai <on|off|status> [provider]"


def _get_ccauto_status_text(session_id: str) -> str:
    controller = _require_session_manager().get_claude_code_auto_continue(session_id)
    status = controller.get_status() if controller else {"enabled": False, "waiting": False}
    return f"Claude auto-continue is {'on' if status.get('enabled') else 'off'} for {session_id}"


async def _run_ccauto_action(session_id: str, action: str) -> str:
    manager = _require_session_manager()

    if action in {"status", "show"}:
        return _get_ccauto_status_text(session_id)

    if action in {"on", "enable"}:
        success = await manager.enable_claude_code_auto_continue(session_id)
        return f"Claude auto-continue {'enabled' if success else 'failed'} for {session_id}"

    if action in {"off", "disable"}:
        await manager.disable_claude_code_auto_continue(session_id)
        return f"Claude auto-continue disabled for {session_id}"

    return "Usage: /ccauto <on|off|status>"


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage AI proxy for the active Telegram session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    if not context.args:
        await update.message.reply_text(
            f"Choose AI proxy action for {session_id}.\n{_get_ai_status_text(session_id)}",
            reply_markup=_build_ai_picker_markup(),
        )
        return

    action = context.args[0].lower()
    provider = context.args[1] if len(context.args) > 1 else None
    await update.message.reply_text(await _run_ai_action(session_id, action, provider=provider))


async def ccauto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage Claude Code auto-continue for the active Telegram session."""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return

    session_id = _get_current_session_id(user_id)
    if not context.args:
        await update.message.reply_text(
            f"Choose Claude auto-continue action for {session_id}.\n{_get_ccauto_status_text(session_id)}",
            reply_markup=_build_ccauto_picker_markup(),
        )
        return

    action = context.args[0].lower()
    await update.message.reply_text(await _run_ccauto_action(session_id, action))


async def handle_feature_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button picks for /ai and /ccauto."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_telegram_user_allowed(user_id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    await query.answer()

    payload = query.data.removeprefix(FEATURE_PICKER_CALLBACK_PREFIX)
    if payload == "cancel":
        await query.edit_message_text("Feature action cancelled")
        return

    parts = payload.split(":")
    feature = parts[0] if parts else ""
    action = parts[1] if len(parts) > 1 else ""
    session_id = _get_current_session_id(user_id)

    if feature == "ai":
        provider = parts[2] if len(parts) > 2 else None
        response = await _run_ai_action(session_id, action, provider=provider)
    elif feature == "ccauto":
        response = await _run_ccauto_action(session_id, action)
    else:
        response = "Unknown feature action"

    await query.edit_message_text(response)


async def handle_command_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button picks for command argument shortcuts."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_telegram_user_allowed(user_id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    await query.answer()

    payload = query.data.removeprefix(COMMAND_PICKER_CALLBACK_PREFIX)
    parts = payload.split(":", 2)
    command_name = parts[0] if parts else ""
    session_id = parts[1] if len(parts) > 1 else _get_current_session_id(user_id)
    action = parts[2] if len(parts) > 2 else ""

    if action == "cancel":
        await query.edit_message_text("Command action cancelled")
        return

    if command_name == "mode":
        await query.edit_message_text(_run_mode_action(user_id, session_id, action))
        return

    if command_name == "key":
        try:
            _require_session_manager().send_special_key(session_id, action)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
            return

        await _edit_query_with_current_screen(query, session_id, fallback_text=f"Sent key {action}")
        return

    if command_name == "watch":
        try:
            callback_chat_id = query.message.chat.id if query.message else query.from_user.id
            response = await _run_watch_action(user_id, session_id, action, chat_id=callback_chat_id)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
            return

        await query.edit_message_text(response)
        return

    await query.edit_message_text("Unknown command action")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular messages (commands)"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        logger.warning(f"Unauthorized Telegram user: {user_id}")
        return

    parsed_command = _parse_known_bot_command(update.message.text)
    if parsed_command:
        command_name, args = parsed_command
        command_handlers = {
            "start": start,
            "help": help_command,
            "reset": reset_command,
            "sessions": sessions_command,
            "newsession": newsession_command,
            "usesession": usesession_command,
            "attachtmux": attachtmux_command,
            "newtmux": newtmux_command,
            "detach": detach_command,
            "repeat": repeat_command,
            "screen": screen_command,
            "watch": watch_command,
            "snapshot": snapshot_command,
            "tail": tail_command,
            "send": send_command,
            "key": key_command,
            "continue": continue_command,
            "interrupt": interrupt_command,
            "features": features_command,
            "mode": mode_command,
            "status": status_command,
            "ai": ai_command,
            "ccauto": ccauto_command,
        }
        await command_handlers[command_name](
            update,
            SimpleNamespace(args=args, bot=getattr(context, "bot", None)),
        )
        return

    session_id = _get_current_session_id(user_id)
    command = update.message.text

    try:
        await update.message.chat.send_action("typing")

        if _get_session_mode(user_id, session_id) == "agent":
            manager = _require_session_manager()
            await manager.send_exact_input(session_id, command)
            manager.send_special_key(session_id, "enter")
            await _reply_with_current_screen(update, session_id, fallback_text="Sent to agent session")
            logger.info(f"User {user_id} sent agent-mode text to session {session_id}: {command[:50]}...")
            return

        output = await _execute_session_command(session_id, command)
        _get_user_sessions(user_id).last_outputs[session_id] = output
        await _reply_in_chunks(update, output)

        suggestion = _get_agent_mode_suggestion(user_id, session_id)
        if suggestion:
            reason = suggestion.get("reason") or "interactive"
            await update.message.reply_text(
                f"This looks like an interactive TUI ({reason}). Switch this session to agent mode?",
                reply_markup=_build_agent_mode_picker_markup(session_id),
            )

        logger.info(f"User {user_id} executed command in session {session_id}: {command[:50]}...")
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Error executing command for {user_id} in session {session_id}: {e}")


async def main(shared_session_manager: SessionManager | None = None):
    """Main entry point for Telegram bot"""
    if not Config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is required to start the Telegram bot")

    owns_session_manager = shared_session_manager is None

    logger.info("Initializing Telegram bot...")
    logger.info(f"Configuration: Webhook URL = {Config.TELEGRAM_WEBHOOK_URL or 'Not set (using polling)'}")
    logger.info(f"Configuration: Web Port = {Config.WEB_PORT}")

    # Initialize session manager
    logger.info("Creating session manager...")
    set_session_manager(shared_session_manager or SessionManager())
    watch_task = None

    # Create bot application
    logger.info("Building Telegram application...")
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    logger.info("Registering command handlers...")
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("sessions", sessions_command))
    app.add_handler(CommandHandler("newsession", newsession_command))
    app.add_handler(CommandHandler("usesession", usesession_command))
    app.add_handler(CommandHandler("attachtmux", attachtmux_command))
    app.add_handler(CommandHandler("newtmux", newtmux_command))
    app.add_handler(CommandHandler("detach", detach_command))
    app.add_handler(CommandHandler("repeat", repeat_command))
    app.add_handler(CommandHandler("screen", screen_command))
    app.add_handler(CommandHandler("watch", watch_command))
    app.add_handler(CommandHandler("snapshot", snapshot_command))
    app.add_handler(CommandHandler("tail", tail_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("key", key_command))
    app.add_handler(CommandHandler("continue", continue_command))
    app.add_handler(CommandHandler("interrupt", interrupt_command))
    app.add_handler(CommandHandler("features", features_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("ccauto", ccauto_command))
    app.add_handler(CallbackQueryHandler(handle_session_picker, pattern=rf"^{SESSION_PICKER_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(handle_feature_picker, pattern=rf"^{FEATURE_PICKER_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(handle_agent_mode_picker, pattern=rf"^{AGENT_MODE_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(handle_command_picker, pattern=rf"^{COMMAND_PICKER_CALLBACK_PREFIX}"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting Telegram bot application...")

    # Start bot
    logger.info("Initializing bot...")
    await app.initialize()
    try:
        await _register_bot_commands(app.bot)
    except Exception as e:
        logger.warning("Failed to register Telegram slash commands: %s", e)
    logger.info("Starting bot...")
    await app.start()
    watch_task = asyncio.create_task(_screen_watch_loop(app.bot), name="telegram-screen-watch")
    
    if Config.TELEGRAM_WEBHOOK_URL:
        # Webhook mode
        logger.info("="*60)
        logger.info("WEBHOOK MODE DETECTED")
        logger.info(f"  - Webhook URL: {Config.TELEGRAM_WEBHOOK_URL}")
        logger.info(f"  - Listen address: 0.0.0.0")
        logger.info(f"  - Port: {Config.WEB_PORT}")
        logger.info(f"  - URL path: /{Config.TELEGRAM_BOT_TOKEN}")
        logger.info("="*60)
        logger.info(f"Attempting to bind to port {Config.WEB_PORT}...")
        await app.start_webhook(
            listen="0.0.0.0",
            port=Config.WEB_PORT,
            url_path=Config.TELEGRAM_BOT_TOKEN,
            webhook_url=f"{Config.TELEGRAM_WEBHOOK_URL}/{Config.TELEGRAM_BOT_TOKEN}",
        )
        logger.info(f"Webhook server started successfully on port {Config.WEB_PORT}")
    else:
        # Polling mode
        logger.info("="*60)
        logger.info("POLLING MODE (no webhook configured)")
        logger.info("="*60)
        logger.info("Starting polling...")
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Polling started successfully")
    
    logger.info("Bot is now running. Press Ctrl+C to stop.")
    
    try:
        # Keep bot running indefinitely
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot interrupted, shutting down...")
    finally:
        if watch_task:
            watch_task.cancel()
            await asyncio.gather(watch_task, return_exceptions=True)
        if app.updater:
            await app.updater.stop()
        if owns_session_manager and session_manager:
            await session_manager.close_all()
        await app.stop()
        logger.info("Bot stopped successfully")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
