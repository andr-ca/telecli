"""
Claude Code auto-continue automation backed by ccusage timing.
"""
import asyncio
import json
import logging
import re
import shutil
from collections import deque
from datetime import datetime, time, timedelta
from contextlib import suppress
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import Config

logger = logging.getLogger(__name__)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
FULLY_USED_RE = re.compile(r"\b100\s*(?:%|percent)\s*used\b")

WEEKLY_MARKERS = (
    "weekly limit",
    "weekly usage",
    "week restart",
    "week reset",
    "weekly reset",
)
BLOCK_MARKERS = (
    "5-hour",
    "5 hour",
    "block reset",
    "session block",
    "usage block",
)
LIMIT_MARKERS = (
    "usage limit",
    "rate limit",
    "limit reached",
    "hit your limit",
    "blocked until",
    "try again later",
    "please wait",
)
CLAUDE_MARKERS = (
    "claude",
    "anthropic",
    "sonnet",
    "opus",
    "haiku",
)
RESET_HINT_MARKERS = (
    "resets at",
    "resets in",
)
SCREEN_RESET_TIME_RE = re.compile(
    r"\breset(?:s)?\s*(?:at\s*)?(?P<time>\d{1,2}(?::\d{2})?\s*[ap]m)(?:\s*\((?P<timezone>[^)]+)\))?",
    re.IGNORECASE,
)


class ClaudeCodeAutoContinue:
    """Schedules a delayed `continue` input after a Claude usage reset."""

    def __init__(
        self,
        grace_seconds: Optional[float] = None,
        ccusage_timeout_seconds: Optional[float] = None,
        output_buffer_size: int = 200,
    ):
        self.ccusage_path = shutil.which("ccusage")
        self.grace_seconds = grace_seconds if grace_seconds is not None else Config.CLAUDE_CODE_AUTO_CONTINUE_GRACE_SECONDS
        self.ccusage_timeout_seconds = (
            ccusage_timeout_seconds
            if ccusage_timeout_seconds is not None
            else Config.CLAUDE_CODE_CCUSAGE_TIMEOUT_SECONDS
        )
        self.output_buffer = deque(maxlen=output_buffer_size)
        self.enabled = False
        self.send_input_callback: Optional[Callable[[str], Awaitable[None]]] = None
        self.status_callback: Optional[Callable[[dict], Awaitable[None]]] = None
        self.scheduled_for: Optional[datetime] = None
        self.reset_at: Optional[datetime] = None
        self.wait_reason: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_continue_sent_at: Optional[datetime] = None
        self._wait_task: Optional[asyncio.Task] = None
        self._resolve_task: Optional[asyncio.Task] = None
        self._probe_task: Optional[asyncio.Task] = None
        self._last_detection_fingerprint = ""

    def enable(self):
        """Enable the automation."""
        self.enabled = True
        self.last_error = None
        logger.info("Claude Code auto-continue enabled")
        self._schedule_status_update()
        if not self._probe_task or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_existing_limit_state())

    def disable(self):
        """Disable the automation and cancel any pending continue."""
        self.enabled = False
        self._cancel_task(self._probe_task)
        self._probe_task = None
        self._cancel_task(self._resolve_task)
        self._resolve_task = None
        self._cancel_task(self._wait_task)
        self._wait_task = None
        self.scheduled_for = None
        self.reset_at = None
        self.wait_reason = None
        self.last_error = None
        self._last_detection_fingerprint = ""
        logger.info("Claude Code auto-continue disabled")
        self._schedule_status_update()

    def is_enabled(self) -> bool:
        return self.enabled

    def set_input_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Set callback used to send `continue` to the terminal."""
        self.send_input_callback = callback

    def set_status_callback(self, callback: Optional[Callable[[dict], Awaitable[None]]]):
        """Set callback used to push status updates to the UI."""
        self.status_callback = callback

    def prime_with_output(self, text: str):
        """Inspect existing terminal history when the feature is enabled mid-session."""
        if text:
            self.add_output(text)

    def add_output(self, text: str):
        """Inspect terminal output and schedule auto-continue when a limit screen appears."""
        if not self.enabled:
            return

        clean_text = self._clean_output(text)
        if not clean_text.strip():
            return

        self.output_buffer.append(clean_text)
        self._inspect_candidate_screen(self._build_screen_text())

    def inspect_screen_text(self, text: str):
        """Inspect a rendered terminal screen snapshot and schedule auto-continue if it shows a limit."""
        if not self.enabled:
            return

        clean_text = self._clean_output(text)
        if not clean_text.strip():
            return

        self._inspect_candidate_screen(clean_text)

    async def _resolve_and_schedule(self, wait_reason_hint: str, screen_text: Optional[str] = None):
        """Resolve the next reset time from ccusage and schedule one delayed continue."""
        try:
            reset_at, resolved_reason = await self._resolve_resume_deadline(wait_reason_hint, screen_text)
            if not reset_at:
                self.last_error = "Unable to determine the next Claude usage reset from ccusage"
                logger.warning(self.last_error)
                await self._notify_status()
                return

            await self._apply_resolved_deadline(reset_at, resolved_reason)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = f"ccusage scheduling failed: {exc}"
            logger.error(self.last_error)
            await self._notify_status()
        finally:
            self._resolve_task = None

    async def _probe_existing_limit_state(self):
        """Arm auto-continue immediately if ccusage already reports an explicit limit reset time."""
        try:
            reset_at, resolved_reason = await self._detect_current_limit_reset()
            if reset_at and resolved_reason:
                await self._apply_resolved_deadline(reset_at, resolved_reason)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Claude Code auto-continue probe skipped: %s", exc)
        finally:
            self._probe_task = None

    async def _wait_and_continue(self, scheduled_for: datetime):
        """Sleep until the scheduled time and then send `continue`."""
        try:
            delay_seconds = max((scheduled_for - datetime.now().astimezone()).total_seconds(), 0)
            await asyncio.sleep(delay_seconds)

            if not self.enabled:
                return

            if not self.send_input_callback:
                self.last_error = "No terminal input callback configured"
                logger.error(self.last_error)
                await self._notify_status()
                return

            await self.send_input_callback("continue")
            self.last_continue_sent_at = datetime.now().astimezone()
            self.scheduled_for = None
            self.reset_at = None
            self.wait_reason = None
            self.last_error = None
            self.output_buffer.clear()
            logger.info("Sent delayed Claude Code `continue` input")
            await self._notify_status()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = f"Failed to send continue: {exc}"
            logger.error(self.last_error)
            await self._notify_status()
        finally:
            self._wait_task = None

    async def _resolve_resume_deadline(
        self,
        wait_reason_hint: str,
        screen_text: Optional[str] = None,
    ) -> tuple[Optional[datetime], Optional[str]]:
        """Get the next reset timestamp, preferring the timer implied by the detected screen."""
        now = datetime.now().astimezone()
        if wait_reason_hint == "block_reset" and screen_text:
            screen_reset_at = self._parse_screen_reset_at(screen_text, now)
            if screen_reset_at:
                return screen_reset_at, "block_reset"

        checks = [wait_reason_hint] if wait_reason_hint in {"block_reset", "weekly_reset"} else ["block_reset", "weekly_reset"]

        for reason in checks:
            if reason == "block_reset":
                payload = await self._run_ccusage_json("blocks", "--json", "--active", "--offline")
                reset_at = self._parse_block_reset_at(payload, now)
            else:
                payload = await self._run_ccusage_json("weekly", "--json", "--order", "desc", "--offline")
                reset_at = self._parse_weekly_reset_at(payload, now)

            if reset_at:
                return reset_at, reason

        return None, None

    async def _detect_current_limit_reset(self) -> tuple[Optional[datetime], Optional[str]]:
        """Check whether ccusage already knows about an active limit reset without relying on screen detection."""
        now = datetime.now().astimezone()
        payload = await self._run_ccusage_json("blocks", "--json", "--active", "--offline")
        reset_at = self._parse_usage_limit_reset_at(payload, now)
        if reset_at:
            return reset_at, "block_reset"
        return None, None

    async def _run_ccusage_json(self, *args: str) -> dict:
        """Run ccusage and parse JSON output."""
        if not self.ccusage_path:
            raise RuntimeError("ccusage CLI not found in PATH")

        process = await asyncio.create_subprocess_exec(
            self.ccusage_path,
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.ccusage_timeout_seconds,
            )
        except BaseException:
            with suppress(ProcessLookupError):
                if process.returncode is None:
                    process.kill()
            with suppress(Exception):
                await process.communicate()
            raise

        if process.returncode != 0:
            stderr_text = stderr.decode().strip() or "unknown error"
            raise RuntimeError(stderr_text)

        output = stdout.decode().strip()
        if not output:
            raise RuntimeError("ccusage returned empty output")

        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid ccusage JSON: {exc}") from exc

    def get_status(self) -> dict:
        """Current UI-facing status."""
        return {
            "enabled": self.enabled,
            "waiting": bool(self.scheduled_for),
            "wait_reason": self.wait_reason,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "last_error": self.last_error,
            "last_continue_sent_at": (
                self.last_continue_sent_at.isoformat() if self.last_continue_sent_at else None
            ),
            "ccusage_available": bool(self.ccusage_path),
        }

    async def _notify_status(self):
        if self.status_callback:
            await self.status_callback(self.get_status())

    def _schedule_status_update(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._notify_status())

    @staticmethod
    def _cancel_task(task: Optional[asyncio.Task]):
        if task and not task.done():
            task.cancel()

    @staticmethod
    def _clean_output(text: str) -> str:
        text = ANSI_ESCAPE_RE.sub("", text)
        text = text.replace("\r", "\n")
        text = CONTROL_CHAR_RE.sub("", text)
        return text

    def _build_screen_text(self) -> str:
        return "\n".join(self.output_buffer)

    def _inspect_candidate_screen(self, screen_text: str):
        wait_reason = self._detect_wait_reason(screen_text)
        if not wait_reason:
            self._last_detection_fingerprint = ""
            return

        detection_fingerprint = f"{wait_reason}:{screen_text[-500:]}"
        if detection_fingerprint == self._last_detection_fingerprint:
            return

        self._last_detection_fingerprint = detection_fingerprint

        if self._resolve_task and not self._resolve_task.done():
            self._resolve_task.cancel()

        self._resolve_task = asyncio.create_task(self._resolve_and_schedule(wait_reason, screen_text))

    async def _apply_resolved_deadline(self, reset_at: datetime, resolved_reason: str):
        scheduled_for = reset_at + timedelta(seconds=self.grace_seconds)
        now = datetime.now().astimezone()
        if scheduled_for <= now:
            scheduled_for = now + timedelta(seconds=1)

        if (
            self.scheduled_for
            and self.wait_reason == resolved_reason
            and abs((self.scheduled_for - scheduled_for).total_seconds()) < 1
        ):
            await self._notify_status()
            return

        self._cancel_task(self._wait_task)
        self.reset_at = reset_at
        self.scheduled_for = scheduled_for
        self.wait_reason = resolved_reason
        self.last_error = None

        logger.info(
            "Scheduled Claude Code auto-continue for %s (%s)",
            self.scheduled_for.isoformat(),
            self.wait_reason,
        )
        await self._notify_status()

        self._wait_task = asyncio.create_task(self._wait_and_continue(scheduled_for))

    @staticmethod
    def _detect_wait_reason(screen_text: str) -> Optional[str]:
        lower_text = screen_text.lower()
        has_percent_used_reset = bool(FULLY_USED_RE.search(lower_text)) and any(
            marker in lower_text for marker in RESET_HINT_MARKERS
        )
        has_hit_limit_reset = "hit your limit" in lower_text and "reset" in lower_text

        has_limit_marker = has_percent_used_reset or has_hit_limit_reset or any(
            marker in lower_text for marker in LIMIT_MARKERS + BLOCK_MARKERS + WEEKLY_MARKERS
        )
        has_claude_marker = any(marker in lower_text for marker in CLAUDE_MARKERS)
        if not has_limit_marker:
            return None

        if not has_percent_used_reset and not has_hit_limit_reset and not has_claude_marker:
            return None

        if any(marker in lower_text for marker in WEEKLY_MARKERS):
            return "weekly_reset"

        if has_percent_used_reset or has_hit_limit_reset or any(marker in lower_text for marker in BLOCK_MARKERS):
            return "block_reset"

        return "block_reset"

    @staticmethod
    def _parse_block_reset_at(payload: dict, now: datetime) -> Optional[datetime]:
        return ClaudeCodeAutoContinue._parse_usage_limit_reset_at(payload, now)

    @staticmethod
    def _parse_usage_limit_reset_at(payload: dict, now: datetime) -> Optional[datetime]:
        blocks = payload.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            return None

        for block in blocks:
            usage_limit_reset_time = ClaudeCodeAutoContinue._parse_iso_datetime(block.get("usageLimitResetTime"))
            if usage_limit_reset_time and usage_limit_reset_time > now:
                return usage_limit_reset_time

        return None

    @staticmethod
    def _parse_weekly_reset_at(payload: dict, now: datetime) -> Optional[datetime]:
        weeks = payload.get("weekly")
        if not isinstance(weeks, list) or not weeks:
            return None

        timezone = now.tzinfo
        for week in weeks:
            week_start_raw = week.get("week")
            if not isinstance(week_start_raw, str):
                continue
            try:
                week_start_date = datetime.strptime(week_start_raw, "%Y-%m-%d").date()
            except ValueError:
                continue

            week_start = datetime.combine(week_start_date, time.min, tzinfo=timezone)
            next_reset = week_start + timedelta(days=7)
            if next_reset > now:
                return next_reset

        return None

    @staticmethod
    def _parse_screen_reset_at(screen_text: str, now: datetime) -> Optional[datetime]:
        match = SCREEN_RESET_TIME_RE.search(screen_text)
        if not match:
            return None

        timezone_name = (match.group("timezone") or "").strip()
        timezone = now.tzinfo
        if timezone_name:
            try:
                timezone = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                logger.debug("Unknown timezone in Claude limit screen: %s", timezone_name)

        time_text = re.sub(r"\s+", "", match.group("time")).upper()
        parsed_time = None
        for fmt in ("%I%p", "%I:%M%p"):
            try:
                parsed_time = datetime.strptime(time_text, fmt).time()
                break
            except ValueError:
                continue

        if not parsed_time:
            return None

        localized_now = now.astimezone(timezone) if timezone else now
        reset_at = localized_now.replace(
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=0,
            microsecond=0,
        )
        if reset_at <= localized_now:
            reset_at += timedelta(days=1)
        return reset_at

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.astimezone()
        return parsed
