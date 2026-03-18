"""Tests for Claude Code auto-continue automation."""
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.claude_code_auto_continue import ClaudeCodeAutoContinue


def test_detect_wait_reason_prefers_weekly_limit():
    """Weekly limit screens should use the weekly reset timer."""
    screen_text = """
    Claude Code weekly usage limit reached.
    Please continue once your weekly reset completes.
    """

    assert ClaudeCodeAutoContinue._detect_wait_reason(screen_text) == "weekly_reset"


def test_detect_wait_reason_handles_100_percent_used_block_screen():
    """Claude's 100%-used screen should still arm block-reset auto-continue."""
    screen_text = """
    Claude Code
    100% used
    Resets at 6:00 PM
    """

    assert ClaudeCodeAutoContinue._detect_wait_reason(screen_text) == "block_reset"


def test_detect_wait_reason_handles_100_percent_used_block_screen_without_claude_header():
    """A rendered limit screen can lose the Claude header but should still arm block-reset auto-continue."""
    screen_text = """
    100% used
    Resets at 6:00 PM
    """

    assert ClaudeCodeAutoContinue._detect_wait_reason(screen_text) == "block_reset"


def test_detect_wait_reason_handles_hit_limit_screen_with_named_timezone():
    """Claude's newer rate-limit screen should arm block-reset auto-continue."""
    screen_text = """
    You've hit your limit · resets 11am (America/Toronto)
    """

    assert ClaudeCodeAutoContinue._detect_wait_reason(screen_text) == "block_reset"


def test_parse_screen_reset_at_handles_hit_limit_screen_with_named_timezone():
    """Rendered hit-limit screens should yield a concrete same-day reset timestamp."""
    now = datetime(2026, 3, 18, 10, 42, tzinfo=ZoneInfo("America/Toronto"))
    screen_text = """
    You've hit your limit · resets 11am (America/Toronto)
    """

    reset_at = ClaudeCodeAutoContinue._parse_screen_reset_at(screen_text, now)

    assert reset_at == datetime(2026, 3, 18, 11, 0, tzinfo=ZoneInfo("America/Toronto"))


def test_parse_block_reset_at_uses_active_block_end_time():
    """Block parsing should use the future block end when present."""
    now = datetime(2026, 3, 18, 3, 32, tzinfo=timezone.utc)
    payload = {
        "blocks": [
            {
                "startTime": "2026-03-18T01:00:00.000Z",
                "endTime": "2026-03-18T06:00:00.000Z",
                "projection": {"remainingMinutes": 148},
            }
        ]
    }

    reset_at = ClaudeCodeAutoContinue._parse_block_reset_at(payload, now)

    assert reset_at == datetime(2026, 3, 18, 6, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_enable_probes_ccusage_for_existing_block_limit(monkeypatch):
    """Enabling the feature should arm immediately when ccusage already reports a limit reset time."""
    controller = ClaudeCodeAutoContinue(grace_seconds=7)
    reset_at = datetime.now().astimezone() + timedelta(minutes=10)

    async def run_ccusage_json(*args: str):
        assert args == ("blocks", "--json", "--active", "--offline")
        return {
            "blocks": [
                {
                    "usageLimitResetTime": reset_at.isoformat(),
                }
            ]
        }

    monkeypatch.setattr(controller, "_run_ccusage_json", run_ccusage_json)

    controller.enable()

    deadline = asyncio.get_running_loop().time() + 1
    while not controller.get_status()["waiting"]:
        assert asyncio.get_running_loop().time() < deadline
        await asyncio.sleep(0.01)

    status = controller.get_status()
    assert status["wait_reason"] == "block_reset"
    assert status["reset_at"] == reset_at.isoformat()
    assert status["scheduled_for"] == (reset_at + timedelta(seconds=7)).isoformat()


def test_parse_weekly_reset_at_uses_next_boundary():
    """Weekly parsing should compute the next restart from the current week bucket."""
    now = datetime(2026, 3, 17, 16, 0, tzinfo=timezone.utc)
    payload = {
        "weekly": [
            {"week": "2026-03-16"},
            {"week": "2026-03-09"},
        ]
    }

    reset_at = ClaudeCodeAutoContinue._parse_weekly_reset_at(payload, now)

    assert reset_at == datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_limit_output_schedules_delayed_continue(monkeypatch):
    """Detected limit output should schedule and send a single `continue`."""
    sent_inputs = []
    controller = ClaudeCodeAutoContinue(grace_seconds=0)

    async def send_input(text: str):
        sent_inputs.append(text)

    async def resolve_resume_deadline(wait_reason_hint: str, _screen_text: str | None = None):
        assert wait_reason_hint == "block_reset"
        return datetime.now().astimezone() + timedelta(seconds=0.05), "block_reset"

    controller.set_input_callback(send_input)
    controller.enable()
    monkeypatch.setattr(controller, "_resolve_resume_deadline", resolve_resume_deadline)

    controller.add_output("Claude Code usage limit reached. Please wait for your 5-hour block reset.")
    await asyncio.sleep(0.15)

    assert sent_inputs == ["continue"]
    assert controller.get_status()["waiting"] is False


@pytest.mark.asyncio
async def test_hit_limit_screen_schedules_from_rendered_reset_time_without_ccusage(monkeypatch):
    """Rendered limit screens should schedule from the visible reset time without falling through to weekly."""
    controller = ClaudeCodeAutoContinue(grace_seconds=7)
    reset_at = datetime.now().astimezone() + timedelta(minutes=10)

    async def run_ccusage_json(*_args: str):
        raise AssertionError("screen reset parsing should avoid ccusage fallback for hit-limit screens")

    monkeypatch.setattr(controller, "_run_ccusage_json", run_ccusage_json)
    monkeypatch.setattr(
        controller,
        "_parse_screen_reset_at",
        lambda _screen_text, _now: reset_at,
    )

    controller.enable()
    controller.inspect_screen_text("You've hit your limit · resets 11am (America/Toronto)")
    await asyncio.sleep(0.05)

    status = controller.get_status()

    assert status["waiting"] is True
    assert status["wait_reason"] == "block_reset"
    assert status["reset_at"] == reset_at.isoformat()
    assert status["scheduled_for"] == (reset_at + timedelta(seconds=7)).isoformat()


@pytest.mark.asyncio
async def test_stale_limit_screen_does_not_rearm_weekly_after_continue(monkeypatch):
    """A still-rendered limit screen should not schedule a weekly retry right after sending continue."""
    sent_inputs = []
    controller = ClaudeCodeAutoContinue(grace_seconds=0)
    screen_text = "You've hit your limit · resets 11am (America/Toronto)"
    resolutions = iter(
        [
            (datetime.now().astimezone() + timedelta(seconds=0.05), "block_reset"),
            (datetime.now().astimezone() + timedelta(days=5), "weekly_reset"),
        ]
    )

    async def send_input(text: str):
        sent_inputs.append(text)

    async def resolve_resume_deadline(_wait_reason_hint: str, _screen_text: str | None = None):
        return next(resolutions)

    controller.set_input_callback(send_input)
    controller.enable()
    monkeypatch.setattr(controller, "_resolve_resume_deadline", resolve_resume_deadline)

    controller.inspect_screen_text(screen_text)
    await asyncio.sleep(0.15)
    controller.inspect_screen_text(screen_text)
    await asyncio.sleep(0.05)

    status = controller.get_status()

    assert sent_inputs == ["continue"]
    assert status["waiting"] is False
    assert status["wait_reason"] is None
    assert status["scheduled_for"] is None


@pytest.mark.asyncio
async def test_waiting_status_includes_reset_and_trigger_details(monkeypatch):
    """Waiting status should expose both the ccusage reset and the delayed trigger time."""
    controller = ClaudeCodeAutoContinue(grace_seconds=7)
    reset_at = datetime.now().astimezone() + timedelta(minutes=10)

    async def resolve_resume_deadline(_wait_reason_hint: str, _screen_text: str | None = None):
        return reset_at, "block_reset"

    controller.enable()
    monkeypatch.setattr(controller, "_resolve_resume_deadline", resolve_resume_deadline)

    controller.add_output("Claude Code usage limit reached. Please wait for your 5-hour block reset.")
    await asyncio.sleep(0.05)

    status = controller.get_status()

    assert status["waiting"] is True
    assert status["reset_at"] == reset_at.isoformat()
    assert status["scheduled_for"] == (reset_at + timedelta(seconds=7)).isoformat()


@pytest.mark.asyncio
async def test_disable_cancels_pending_continue(monkeypatch):
    """Disabling the feature should cancel an already scheduled continue."""
    sent_inputs = []
    controller = ClaudeCodeAutoContinue(grace_seconds=0)

    async def send_input(text: str):
        sent_inputs.append(text)

    async def resolve_resume_deadline(_wait_reason_hint: str, _screen_text: str | None = None):
        return datetime.now().astimezone() + timedelta(seconds=0.2), "block_reset"

    controller.set_input_callback(send_input)
    controller.enable()
    monkeypatch.setattr(controller, "_resolve_resume_deadline", resolve_resume_deadline)

    controller.add_output("Claude usage limit reached. Wait for this block reset before continuing.")
    await asyncio.sleep(0.05)
    controller.disable()
    await asyncio.sleep(0.25)

    assert sent_inputs == []
