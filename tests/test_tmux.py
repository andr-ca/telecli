"""Tests for tmux helpers."""

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
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return _completed("line 1\nline 2\n")

    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
    monkeypatch.setattr(tmux.subprocess, "run", fake_run)

    assert tmux.capture_tmux_pane("dev-shell", lines=20) == "line 1\nline 2\n"
    assert "-p" in calls[0]
    assert "-e" not in calls[0]
    assert "-S" in calls[0]


def test_capture_tmux_screen_returns_visible_text(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return _completed("visible line 1\nvisible line 2\n")

    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
    monkeypatch.setattr(tmux.subprocess, "run", fake_run)

    assert tmux.capture_tmux_screen("dev-shell") == "visible line 1\nvisible line 2\n"
    assert "-S" not in calls[0]
    assert calls[0][-1] == "-p"


def test_get_tmux_interaction_recommendation_reports_signature_and_interactivity(monkeypatch):
    monkeypatch.setattr(tmux, "get_tmux_pane_state", lambda session_name: {
        "pane_id": "%1",
        "current_command": "vim",
        "alternate_screen": True,
        "interactive": True,
    })

    recommendation = tmux.get_tmux_interaction_recommendation("dev-shell")

    assert recommendation["supports_agent_mode"] is True
    assert recommendation["should_suggest_agent_mode"] is True
    assert recommendation["reason"] == "vim"
    assert recommendation["signature"] == "dev-shell:%1:vim:1"
    assert recommendation["pane"]["interactive"] is True


def test_tmux_interaction_signature_is_stable_and_ignores_snapshot_content():
    pane = {
        "pane_id": "%1",
        "current_command": "vim",
        "alternate_screen": True,
        "interactive": True,
    }

    signature_one = tmux._tmux_interaction_signature("dev-shell", pane)  # noqa: SLF001
    pane["current_command"] = "vim"
    pane["alternate_screen"] = True
    signature_two = tmux._tmux_interaction_signature("dev-shell", pane)  # noqa: SLF001

    assert signature_one == "dev-shell:%1:vim:1"
    assert signature_two == signature_one


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


@pytest.mark.parametrize(
    ("key_name", "expected"),
    [
        ("left", "Left"),
        ("right", "Right"),
        ("backspace", "BSpace"),
        ("ctrl-d", "C-d"),
    ],
)
def test_send_tmux_key_maps_extended_aliases(monkeypatch, key_name, expected):
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

    tmux.send_tmux_key("dev-shell", key_name)

    assert calls[0][-3:] == ["-t", "dev-shell", expected]


def test_send_tmux_key_rejects_unknown_keys():
    with pytest.raises(ValueError, match="Unsupported tmux key"):
        tmux.send_tmux_key("dev-shell", "ctrl-x")


def test_get_tmux_path_requires_tmux_binary(monkeypatch):
    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: None,
    )

    with pytest.raises(ValueError, match="tmux is not installed"):
        tmux.capture_tmux_pane("dev-shell")


def test_run_tmux_command_raises_on_non_zero_exit(monkeypatch):
    monkeypatch.setattr(
        tmux.shutil,
        "which",
        lambda name: "/usr/bin/tmux",
    )
    monkeypatch.setattr(
        tmux.subprocess,
        "run",
        lambda *args, **kwargs: _completed(stdout="", stderr="boom", returncode=1),
    )

    with pytest.raises(ValueError, match="boom"):
        tmux.capture_tmux_pane("dev-shell")
