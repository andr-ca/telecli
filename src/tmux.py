"""
tmux discovery helpers used by session management.
"""
from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

_TMUX_FORMAT = "#{session_name}\t#{session_windows}\t#{session_attached}"


def list_tmux_sessions() -> list[dict]:
    """Return tmux sessions visible on the current machine."""
    tmux_path = shutil.which("tmux")
    if not tmux_path:
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


def create_tmux_session(session_name: str) -> None:
    """Create a detached tmux session on the current machine."""
    tmux_path = shutil.which("tmux")
    if not tmux_path:
        raise ValueError("tmux is not installed")

    result = subprocess.run(
        [tmux_path, "new-session", "-d", "-s", session_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_text = result.stderr.strip() or result.stdout.strip() or "tmux session creation failed"
        raise ValueError(error_text)
