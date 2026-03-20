"""
tmux discovery helpers used by session management.
"""
from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

_TMUX_FORMAT = "#{session_name}\t#{session_windows}\t#{session_attached}"
_PANE_FORMAT = "#{pane_id}\t#{pane_current_command}\t#{alternate_on}"
_INTERACTIVE_COMMANDS = {"claude", "codex", "vim", "less", "man", "htop"}
_SPECIAL_KEYS = {
    "enter": "Enter",
    "esc": "Escape",
    "tab": "Tab",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "backspace": "BSpace",
    "ctrl-c": "C-c",
    "ctrl-d": "C-d",
}


def _get_tmux_path() -> str:
    tmux_path = shutil.which("tmux")
    if not tmux_path:
        raise ValueError("tmux is not installed")
    return tmux_path


def _run_tmux_command(args: list[str]) -> subprocess.CompletedProcess:
    tmux_path = _get_tmux_path()
    result = subprocess.run(
        [tmux_path, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_text = result.stderr.strip() or result.stdout.strip() or "tmux command failed"
        raise ValueError(error_text)
    return result


def list_tmux_sessions() -> list[dict]:
    """Return tmux sessions visible on the current machine."""
    try:
        tmux_path = _get_tmux_path()
    except ValueError:
        return []

    result = subprocess.run(
        [tmux_path, "list-sessions", "-F", _TMUX_FORMAT],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_text = f"{result.stdout}\n{result.stderr}".lower()
        if "no server running" in error_text or "failed to connect to server" in error_text:
            return []

        logger.warning("Failed to list tmux sessions: %s", result.stderr.strip() or result.stdout.strip())
        return []

    sessions = []
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue

        name, windows, attached = (raw_line.split("\t") + ["0", "0"])[:3]
        sessions.append(
            {
                "name": name,
                "windows": int(windows) if windows.isdigit() else 0,
                "attached": attached not in {"0", "", "false", "False"},
            }
        )

    return sessions


def tmux_session_exists(session_name: str) -> bool:
    """Check whether the named tmux session currently exists."""
    return any(session["name"] == session_name for session in list_tmux_sessions())


def get_tmux_pane_state(session_name: str) -> dict:
    """Return lightweight metadata for the active tmux pane."""
    result = _run_tmux_command(["display-message", "-pt", session_name, _PANE_FORMAT])
    pane_id, current_command, alternate_on = (result.stdout.strip().split("\t") + ["", "", "0"])[:3]
    alternate_screen = alternate_on == "1"
    interactive = alternate_screen or current_command.lower() in _INTERACTIVE_COMMANDS
    return {
        "pane_id": pane_id,
        "current_command": current_command,
        "alternate_screen": alternate_screen,
        "interactive": interactive,
    }


def capture_tmux_pane(session_name: str, *, lines: int = 80) -> str:
    """Capture pane contents from a tmux session."""
    result = _run_tmux_command(["capture-pane", "-pt", session_name, "-S", f"-{lines}", "-p"])
    return result.stdout


def capture_tmux_screen(session_name: str) -> str:
    """Capture only the currently visible tmux pane contents."""
    result = _run_tmux_command(["capture-pane", "-pt", session_name, "-p"])
    return result.stdout


def send_tmux_key(session_name: str, key_name: str) -> None:
    """Send a normalized tmux key sequence to the target session."""
    mapped_key = _SPECIAL_KEYS.get(key_name.lower())
    if not mapped_key:
        raise ValueError(f"Unsupported tmux key: {key_name}")

    _run_tmux_command(["send-keys", "-t", session_name, mapped_key])


def _tmux_interaction_signature(session_name: str, pane: dict) -> str:
    """Build a stable signature for agent-mode suggestion suppression."""
    alternate_screen = int(bool(pane.get("alternate_screen")))
    return f"{session_name}:{pane.get('pane_id', '')}:{pane.get('current_command', '')}:{alternate_screen}"


def get_tmux_interaction_recommendation(session_name: str) -> dict:
    """Summarize whether tmux suggests an interactive agent-mode session."""
    pane = get_tmux_pane_state(session_name)
    return {
        "supports_agent_mode": True,
        "should_suggest_agent_mode": pane["interactive"],
        "reason": pane["current_command"] or "unknown",
        "signature": _tmux_interaction_signature(session_name, pane),
        "pane": pane,
    }


def create_tmux_session(session_name: str) -> None:
    """Create a detached tmux session on the current machine."""
    _run_tmux_command(["new-session", "-d", "-s", session_name])
