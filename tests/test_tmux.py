"""Tests for tmux helpers."""

from hashlib import sha256
from types import SimpleNamespace

import pytest

from src import tmux


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_get_tmux_pane_state_parses_foreground_command(monkeypatch):
    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
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
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda *args, **kwargs: _completed("line 1\nline 2\n"),
    )

    assert tmux.capture_tmux_pane("dev-shell", lines=20) == "line 1\nline 2\n"


def test_get_tmux_interaction_recommendation_reports_signature_and_interactivity(monkeypatch):
    monkeypatch.setattr(tmux, "get_tmux_pane_state", lambda session_name: {
        "pane_id": "%1",
        "current_command": "vim",
        "alternate_screen": True,
        "interactive": True,
    })
    monkeypatch.setattr(tmux, "capture_tmux_pane", lambda session_name, lines=40: "vim screen\n")

    recommendation = tmux.get_tmux_interaction_recommendation("dev-shell")
    expected_digest = sha256("vim screen\n".encode("utf-8")).hexdigest()[:12]

    assert recommendation["supports_agent_mode"] is True
    assert recommendation["should_suggest_agent_mode"] is True
    assert recommendation["reason"] == "vim"
    assert recommendation["signature"] == f"dev-shell:%1:vim:{expected_digest}"
    assert recommendation["pane"]["interactive"] is True


def test_send_tmux_key_maps_common_aliases(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed()

    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
    monkeypatch.setattr(tmux.subprocess, "run", fake_run)

    tmux.send_tmux_key("dev-shell", "ctrl-c")

    assert calls[0][-3:] == ["-t", "dev-shell", "C-c"]
