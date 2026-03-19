# Telegram Agent Mode Design

## Summary

TeleCLI's current Telegram integration is optimized for line-oriented shell commands. That model works for simple shell usage, but it breaks down for full-screen terminal applications such as Codex, Claude Code, `vim`, `less`, and similar TUIs. The Telegram bot currently sends each non-command message as a complete line followed by Enter, then strips ANSI output and returns plain text. That interaction model is fundamentally incompatible with alternate-screen, cursor-driven, continuously redrawn interfaces.

The recommended fix is a hybrid interaction model:

- Keep the existing Telegram behavior as `shell mode` for normal shell commands.
- Add an explicit `agent mode` for tmux-backed interactive sessions.
- Add auto-suggest, not auto-switch, when TeleCLI detects that the active tmux pane is likely running an interactive TUI.

This makes Telegram usable as a control plane for coding agents without trying to turn Telegram into a terminal emulator.

## Goals

- Keep simple shell usage in Telegram fast and familiar.
- Make tmux-backed coding-agent sessions usable from Telegram.
- Support explicit mode switching with safe auto-suggestions.
- Avoid breaking current web and shell session behavior.
- Keep Telegram policy separate from tmux mechanics.

## Non-Goals

- Emulating a full xterm experience inside Telegram.
- Making raw full-screen TUI interaction feel native in chat.
- Auto-switching modes without user confirmation.
- Supporting agent mode on non-tmux sessions in v1.

## User Experience

Each Telegram alias/session gains an interaction mode:

- `shell mode`
  - Existing behavior.
  - A plain Telegram message is treated as a shell command and submitted with Enter.
  - Output is cleaned and returned as text.

- `agent mode`
  - Intended for tmux-backed interactive tools.
  - Telegram becomes a structured remote control for the pane.
  - A plain Telegram message is treated as `send + Enter`, but only after the user has explicitly enabled agent mode.

### New Telegram commands

- `/mode [shell|agent|status]`
- `/snapshot`
- `/tail [lines]`
- `/send <text>`
- `/key <name>`
- `/status`

`/status` should report the current Telegram mode, active TeleCLI session, backend type, tmux target if present, and whether the session is a candidate for agent mode.

### Auto-Suggest

When the active session is tmux-backed and TeleCLI has a high-confidence signal that the foreground pane is interactive, the bot should send a one-time suggestion:

> This looks like an interactive TUI. Switch this session to agent mode?

With inline buttons:

- `Switch`
- `Not now`
- `Don't suggest again`

The bot must never switch automatically. Suggestions should be suppressed after dismissal until the pane state changes.

## Architecture

The design should keep behavior split across three layers.

### 1. Telegram policy: `src/telegram_bot.py`

This module should own:

- Per-user per-session interaction mode state.
- Routing rules for plain text in each mode.
- Mode commands and agent-mode Telegram commands.
- Auto-suggest presentation and suppression.
- User-facing fallbacks and help text.

`TelegramUserSessions` should be extended with state similar to:

- `session_modes: dict[str, str]`
- `suggestion_dismissals: dict[str, bool]`
- `last_suggested_signature: dict[str, str]`

Mode state should be keyed by TeleCLI session ID so aliases remain cheap views over the same underlying runtime.

### 2. Capability layer: `src/session_manager.py`

This module should expose Telegram-neutral operations such as:

- `get_session_mode_capabilities(session_id)`
- `get_agent_mode_recommendation(session_id)`
- `capture_session_snapshot(session_id, lines=...)`
- `tail_session_output(session_id, lines=...)`
- `send_exact_input(session_id, text)`
- `send_special_key(session_id, key_name)`

`SessionManager` should not know about Telegram prompts or inline keyboards. It should answer capability questions and delegate tmux-specific behavior when appropriate.

### 3. tmux backend adapter: `src/tmux.py`

This module should add helpers for:

- Capturing pane content from a tmux session.
- Inspecting pane metadata, including the foreground command.
- Sending raw keys to the pane.
- Returning a stable "pane signature" used for suggestion suppression.
- Exposing an `interactive` heuristic summary.

This keeps tmux subprocess logic in one place and avoids scattering `tmux` shell-outs across the Telegram bot.

## Agent Mode Heuristics

v1 should keep detection narrow and conservative.

Only tmux-backed sessions are eligible for auto-suggest. The recommendation should be based on a small heuristic set:

- Foreground command names such as `claude`, `codex`, `vim`, `less`, `man`, `htop`.
- Pane metadata or content that strongly suggests alternate-screen or interactive redraw behavior.
- Pane text patterns that indicate the session is waiting for user input in an interactive app.

If detection fails or tmux inspection is unavailable, Telegram should stay in shell mode and degrade gracefully.

To prevent repeated nagging, suggestions should be shown once per pane-state signature. A signature can be derived from stable inputs such as:

- tmux session name
- pane id
- foreground command
- recent capture hash

If the signature changes, the bot may suggest again.

## Input Semantics

### Shell mode

- Plain text -> send line + Enter.
- Existing command output formatting remains unchanged.

### Agent mode

- Plain text -> exact paste + Enter.
- `/send` -> exact paste only.
- `/key enter` -> Enter
- `/key esc` -> Escape
- `/key tab` -> Tab
- `/key up` -> Up arrow
- `/key down` -> Down arrow
- `/key ctrl-c` -> interrupt

The agent-mode default for plain text is intentionally lightweight, because common workflows involve short approvals such as `continue`, `yes`, or short instructions. More complex key-level control stays explicit through `/key`.

## Output Semantics

Agent mode should avoid pretending to stream a full TUI over chat. Instead it should provide stable views:

- `/snapshot` returns a cleaned fixed-width pane capture.
- `/tail` returns the last stable lines from pane history.
- `/status` reports state and recommendation details.

The bot should continue to chunk long replies to respect Telegram limits.

## Error Handling

- If a user tries `/mode agent` on a non-tmux session, return a clear error and suggest `/newtmux` or `/attachtmux`.
- If tmux is unavailable, agent-mode commands should fail cleanly without changing mode.
- If key names are unknown, return a short usage message with supported values.
- If snapshot or tail capture fails, keep the session alive and return an actionable error.
- If a tmux session disappears, report that the backing runtime is no longer available and suggest reattaching.

## Testing

### `tests/test_telegram_bot.py`

Add coverage for:

- `/mode shell|agent|status`
- plain-text routing in shell mode versus agent mode
- auto-suggest display on recommended interactive tmux sessions
- suppression after `Not now` and `Don't suggest again`
- agent-mode commands on non-tmux sessions
- suggestion reset after pane signature changes

### `tests/test_session_manager.py`

Add coverage for:

- capability reporting for shell versus tmux sessions
- recommendation summaries
- snapshot/tail delegation
- special key routing

### tmux helper tests

Add focused unit tests for:

- foreground-command parsing
- pane capture parsing
- key mapping
- signature generation

Tests should prefer mocked tmux subprocess calls rather than requiring a live Telegram runtime.

## Rollout

### Phase 1

- Add tmux helper primitives.
- Add session-manager capability methods.
- Add Telegram mode state and `/mode`, `/snapshot`, `/tail`, `/send`, `/key`, `/status`.

### Phase 2

- Add conservative auto-suggest for tmux-backed interactive sessions.
- Add inline actions and suppression rules.

### Phase 3

- Tune heuristics for real coding-agent sessions.
- Expand convenience shortcuts if usage proves they are needed.

## Recommendation

Implement the hybrid model with explicit opt-in and auto-suggest. Do not attempt to emulate a full terminal in Telegram. For coding agents, the best user experience is to run the real UI in tmux or the web terminal, and use Telegram as a structured remote control and monitoring layer.
