# Claude Code Auto-Continue Defect Log

## Summary

- Defect area: Claude Code auto-continue in the TeleCLI web terminal.
- Primary symptom history:
  - CC Auto stayed idle with `No auto-trigger scheduled yet` while Claude was visibly blocked.
  - After detection started working, some sessions scheduled a weekly reset even when weekly usage was low.
  - In the same state, it looked like the scheduled `continue` keystroke did not fire.
- Current status as of 2026-03-18:
  - Blocked Claude screens with visible reset times are parsed directly from the rendered screen.
  - The same stale blocked screen no longer immediately re-arms a new wait after a successful send.
  - Focused controller, websocket, and browser regressions are passing.
- Follow-up status as of 2026-03-19:
  - A send-path regression was confirmed after the earlier fix: CC Auto could type `continue` into the session but add a newline instead of submitting the command.
  - Claude auto-continue now submits `continue` as a complete terminal line instead of replaying it as per-character keystrokes plus a raw carriage return.
  - A `ccusage` parsing regression was also confirmed: CC Auto could treat an active block window or projection as a real reset deadline even when `ccusage` did not provide an explicit usage-limit reset.
  - For block-reset scheduling, CC Auto now accepts only explicit block-reset signals: rendered-screen reset times or `usageLimitResetTime` from `ccusage`.
  - A stale-history regression was also confirmed: after a successful send, old limit text in the raw PTY buffer could be re-read as if it were the current screen.
  - After a successful `continue`, the raw-output history buffer is now cleared so stale limit text cannot immediately rearm the feature.
  - Session-manager, controller, and websocket regression coverage is passing after the follow-up fixes.

## User-Facing Symptom Timeline

1. Claude auto-continue was enabled, but status stayed at:
   - `⏱ Claude Code auto-continue is armed | No auto-trigger scheduled yet | Waiting for Claude to show a usage limit screen`
2. The user confirmed:
   - server restarted
   - hard refresh performed
   - toggle retried
3. Detection later started showing a countdown, but behavior was still wrong:
   - weekly reset was scheduled even though weekly usage was low
   - user reported that `continue` did not appear to be sent
4. Follow-up regression after the scheduling fixes:
   - on 2026-03-19 the user reported that the fix mostly worked
   - but instead of submitting `continue`, the session showed a new line as if Enter had not executed the command
5. Additional follow-up regression on 2026-03-19:
   - after the module tried to submit `continue`, it could still show a future reset even when the session was not actually fully used
   - example symptom: CC Auto showed a next reset many hours away because it treated `ccusage` active-block metadata as a hard reset deadline
6. Additional follow-up regression on 2026-03-19:
   - after a successful `continue`, a new normal PTY output chunk could still rearm CC Auto
   - the controller was still inspecting stale historical limit text from its raw-output buffer

## Live Evidence Collected

### Actual Claude Limit Text on This Machine

The real blocked-screen phrase found in the local Claude transcript was:

- `You've hit your limit · resets 11am (America/Toronto)`

Relevant transcript source inspected during debugging:

- `/home/andrey/.claude/projects/-home-andrey-projects-breqy/1d87f856-5c80-4cb6-8caa-862ffe4df289.jsonl`

Relevant observed timestamps in that transcript:

- `2026-03-18T12:42:56.710Z`
- `2026-03-18T14:42:01.513Z`

This mattered because earlier matchers were tuned to older forms such as:

- `100% used`
- `usage limit reached`
- `block reset`

### `ccusage` Behavior on This Machine

Command inspected:

```bash
ccusage blocks --json --active --offline
```

Observed characteristics from the payload during investigation:

- it returned an active block with fields like `startTime`, `endTime`, `actualEndTime`
- it exposed `projection.remainingMinutes`
- it did not expose a reliable `usageLimitResetTime` for the newer `You've hit your limit` event on this machine
- live inspection on 2026-03-19 also showed the parser mismatch directly:
  - `_parse_block_reset_at(...)` resolved `2026-03-19T15:00:00+00:00`
  - `_parse_usage_limit_reset_at(...)` resolved `None`

Important conclusion:

- `projection.remainingMinutes` is not a trustworthy "currently blocked until" signal for this issue
- absence of `usageLimitResetTime` means `ccusage` alone cannot always resolve the current reset for newer Claude limit messaging
- `ccusage blocks --active` means the 5-hour session window is still active, not that Claude is definitely hard-blocked right now

### `ccusage` Source Inspection

Installed source inspected under:

- `/home/andrey/.nvm/versions/node/v24.11.0/lib/node_modules/ccusage/dist/`

What mattered:

- the weekly/block projection logic was not enough to prove a real hard block
- parsing for `usageLimitResetTime` appeared tied to older Claude limit message formats

## Root Causes That Actually Mattered

### Root Cause 1: Screen Detection Was Initially Looking for the Wrong Phrases

The first wave of failures came from narrow detection logic that only recognized older Claude limit wording.

What eventually had to be supported:

- `100% used`
- `You've hit your limit · resets 11am (America/Toronto)`

Related code:

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L387)
- [static/index.html](/home/andrey/projects/telecli/static/index.html#L349)

### Root Cause 2: The Browser Was Showing a Rendered Limit Screen That the Server Could Miss

The web UI displays xterm's rendered screen, not just raw PTY chunks. A blocked screen could be visible in the browser while the server-side chunk matcher had not seen a matching raw output sequence.

Fix path:

- browser reports visible terminal screen text
- server accepts `claude_code.screen_text`
- controller inspects that rendered screen text

Related code:

- [static/index.html](/home/andrey/projects/telecli/static/index.html#L332)
- [src/web_app.py](/home/andrey/projects/telecli/src/web_app.py#L328)
- [src/ws_models.py](/home/andrey/projects/telecli/src/ws_models.py)

### Root Cause 3: Block Screens Could Fall Through to Weekly Scheduling

This was the key defect behind the later "weekly reset even though weekly usage is low" report.

Before the latest fix:

- a screen detected as `block_reset` still relied on `ccusage blocks`
- if `ccusage blocks` did not yield a future reset
- controller could fall through to `ccusage weekly`
- result: wrong weekly schedule for a block-only situation

Fix:

- parse the visible reset time directly from the blocked Claude screen first
- only fall back to `ccusage` when screen parsing cannot resolve a time

Implemented in:

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L223)
- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L470)

### Root Cause 4: A Successful Send Could Be Masked by Immediate Re-Arming From the Same Stale Screen

This explained why it looked like `continue` had not been sent.

What was happening:

- controller scheduled a send
- `_wait_and_continue()` called the input callback
- the browser was still rendering the same blocked screen immediately afterward
- the controller cleared its detection fingerprint after send
- the same old screen was treated as a fresh new limit event
- if `ccusage blocks` no longer resolved cleanly, it could re-arm as weekly

Result:

- the send may have succeeded
- but the status line immediately went back into a waiting state
- user perception: auto-continue did not work

Fix:

- do not clear the detection fingerprint immediately after a successful send
- only clear it when the screen no longer looks like a limit screen, or the feature is disabled

Implemented in:

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L206)
- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L340)

### Root Cause 5: Claude Auto-Continue Used a Typing-Oriented Send Path Instead of a Submitted-Line Path

This was the follow-up regression confirmed on 2026-03-19.

What was happening:

- Claude auto-continue reused the session-manager helper that simulates a user typing text character-by-character
- that helper sent `c`, `o`, `n`, `t`, `i`, `n`, `u`, `e`, then a raw `\r` with `newline=False`
- normal command submission elsewhere in TeleCLI uses `send_input(..., newline=True)`
- Claude auto-continue therefore used a different terminal-input path from normal submitted commands

Result:

- `continue` could appear in the session
- but the final submit behavior could differ from a normal entered command
- in the reported case, the session showed a new line instead of submitting `continue`

Fix:

- keep the typing-oriented helper for AI proxy flows
- add a dedicated submitted-line helper for Claude auto-continue
- wire the Claude auto-continue callback to `send_input(session_id, text, newline=True, from_ai=True)`

Implemented in:

- [src/session_manager.py](../../src/session_manager.py#L355)
- [src/session_manager.py](../../src/session_manager.py#L437)

### Root Cause 6: Active `ccusage` Block Windows Were Treated As Real Block Reset Deadlines

This was the follow-up regression confirmed on 2026-03-19.

What was happening:

- for `block_reset` handling, `_resolve_resume_deadline()` still accepted `_parse_block_reset_at()` results from `ccusage blocks`
- `_parse_block_reset_at()` treated these fields as reset deadlines:
  - `endTime`
  - `projection.remainingMinutes`
- live `ccusage` source inspection showed that an "active" block only means recent activity still falls inside the current 5-hour block window
- therefore `endTime` and `projection.remainingMinutes` describe the active session window or its projection, not proof of a current hard Claude block

Result:

- CC Auto could show a reset many hours away even though `ccusage` had no explicit `usageLimitResetTime`
- a detected `block_reset` could also fall through to a non-block schedule path when no trustworthy block-reset time existed

Fix:

- for block-reset handling, accept only:
  - rendered-screen reset times parsed from the visible Claude limit screen
  - `usageLimitResetTime` from `ccusage`
- stop treating `endTime` and `projection.remainingMinutes` as hard block reset deadlines
- stop falling from `block_reset` into `weekly_reset` resolution when the block-reset lookup has no explicit answer

Implemented in:

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L223)
- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L413)

### Root Cause 7: Raw PTY History Could Re-Trigger Limit Detection After A Successful Send

This was the follow-up regression confirmed on 2026-03-19.

What was happening:

- `add_output()` appends cleaned PTY chunks into `output_buffer`
- `_build_screen_text()` inspects the combined history, not just the newest chunk
- after a successful `continue`, old limit text could still remain in `output_buffer`
- when the next normal PTY output arrived, the combined history still looked like a limit screen

Result:

- CC Auto could rearm from stale historical limit text even though Claude had resumed normally
- if the stale text contained `resets 11am ...` and that time was already past, the parser could roll it forward to the next day and show a bogus many-hours-away reset

Fix:

- after a successful delayed `continue`, clear the raw-output history buffer
- keep the fingerprint-based stale-screen protection for browser-reported rendered screens

Implemented in:

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L206)

## Hypotheses Tried

### Hypotheses That Were Useful or Correct

1. The matcher only understood older Claude limit wording.
   - Correct.
   - This explained why visible blocked sessions stayed idle.

2. The browser-visible xterm screen could differ from what the server-side PTY matcher had seen.
   - Correct.
   - This justified reporting `screen_text` from the browser.

3. The live phrase on this machine was not `100% used` but `You've hit your limit · resets 11am (America/Toronto)`.
   - Correct.
   - Confirmed from the local Claude transcript.

4. `ccusage` was not a reliable single source of truth for newer block states on this machine.
   - Correct.
   - Confirmed by inspecting both command output and installed `ccusage` code.

5. Weekly scheduling was a fallback artifact, not the real blocked state.
   - Correct.
   - Fixed by parsing reset time directly from screen text.

6. The missing keystroke could be a state illusion caused by immediate re-arming from the same stale limit screen.
   - Correct.
   - This was the working explanation for the "didn't send keystrokes" symptom in the reported case.

7. Claude auto-continue might be using the wrong session-manager input mode for submitted commands.
   - Correct.
   - The callback was wired to a typing helper instead of the standard submitted-line path.

8. `ccusage blocks --active` might only be describing the current 5-hour session window, not a real hard block reset.
   - Correct.
   - The controller was misreading active block-window metadata as a reset deadline.

9. The controller might still be reading stale raw PTY history after a successful `continue`.
   - Correct.
   - Historical limit text in `output_buffer` could re-trigger scheduling on later normal output.

### Hypotheses That Did Not Resolve the Defect

1. The user had not restarted the backend.
   - Not sufficient.
   - A restart was necessary after some iterations, but the user did restart and the issue still reproduced.

2. Accepting `100% used` screens without a Claude header would solve the real-world case.
   - Only partially useful.
   - The live phrase on this machine was different.

3. Probing `ccusage blocks --json --active --offline` at enable-time would fully solve already-blocked sessions.
   - Not sufficient on this machine.
   - `usageLimitResetTime` was not reliably present for the newer Claude event.

4. The send callback path itself was definitely broken.
   - Not established as the main cause.
   - The callback path remained plausible; the stronger explanation for the observed symptom was stale-screen re-arming immediately after send.

## Code Paths Involved

### Core Controller

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py)
  - detection and scheduling state
  - `ccusage` resolution
  - delayed send of `continue`
  - screen-text parsing

Important sections:

- enable / probe: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L93)
- delayed send: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L191)
- deadline resolution: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L223)
- limit-screen inspection: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L340)
- wait-reason detection: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L387)
- screen reset parsing: [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py#L470)

### WebSocket Integration

- [src/web_app.py](/home/andrey/projects/telecli/src/web_app.py#L328)
  - handles enable/disable
  - accepts browser-reported `screen_text`
  - forwards raw PTY output into the controller

### Session/Terminal Send Path

- [src/session_manager.py](/home/andrey/projects/telecli/src/session_manager.py#L337)
- [src/session_manager.py](/home/andrey/projects/telecli/src/session_manager.py#L349)
- [src/session_manager.py](/home/andrey/projects/telecli/src/session_manager.py#L355)
- [src/session_manager.py](/home/andrey/projects/telecli/src/session_manager.py#L437)
- [src/terminal.py](/home/andrey/projects/telecli/src/terminal.py#L155)

Notes:

- AI proxy still uses `_send_text_like_user()` for typing-oriented automation
- Claude auto-continue now calls `_submit_automation_line()`
- that sends `continue` through `send_input(..., newline=True, from_ai=True)`

### Browser-Side Detection and Status Rendering

- [static/index.html](/home/andrey/projects/telecli/static/index.html#L324)
  - rendered-screen detection lifecycle
- [static/index.html](/home/andrey/projects/telecli/static/index.html#L349)
  - browser heuristic for whether a visible screen should be reported
- [static/index.html](/home/andrey/projects/telecli/static/index.html#L1973)
  - CC Auto status-line rendering

## Tests Added or Updated

### Unit / Controller Tests

- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L42)
  - detects newer `hit your limit` wording
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L51)
  - parses `resets 11am (America/Toronto)` into a concrete datetime
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L151)
  - schedules directly from rendered screen reset time instead of weekly fallback
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L179)
  - proves stale limit screen does not re-arm weekly after successful send
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L63)
  - uses `usageLimitResetTime` as the only trusted `ccusage` block-reset field
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L80)
  - ignores active block windows that have no explicit `usageLimitResetTime`
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L197)
  - proves a detected limit screen does not arm from `endTime` or `projection.remainingMinutes` alone
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py#L271)
  - proves new normal PTY output does not rearm from stale historical limit text after a successful send

### Session Manager Coverage

- [tests/test_session_manager.py](/home/andrey/projects/telecli/tests/test_session_manager.py#L202)
  - proves Claude auto-continue submits `continue` as a single line with `newline=True`
  - prevents regression back to per-character typing plus raw `\r`

### WebSocket Coverage

- [tests/test_websocket.py](/home/andrey/projects/telecli/tests/test_websocket.py#L255)
  - browser-reported visible limit screen arms waiting state

### Browser / Playwright Coverage

- [tests/test_playwright_integration.py](/home/andrey/projects/telecli/tests/test_playwright_integration.py#L427)
- [tests/test_playwright_integration.py](/home/andrey/projects/telecli/tests/test_playwright_integration.py#L503)

These cover:

- visible screen report for `100% used`
- visible screen report for `You've hit your limit ...`
- status rendering path

## Verification Commands Run

Focused verification used during the latest fix:

```bash
pytest tests/test_claude_code_auto_continue.py tests/test_websocket.py -q
```

Observed result:

- `31 passed`

Browser-focused verification:

```bash
pytest tests/test_playwright_integration.py -k 'claude_code_auto_continue or reports_visible_limit_screen_on_enable or reports_hit_limit_screen_on_enable' -q
```

Observed result:

- `4 passed`

Combined verification for the final fix state:

```bash
pytest tests/test_claude_code_auto_continue.py tests/test_websocket.py tests/test_playwright_integration.py -k 'claude_code_auto_continue or reports_visible_limit_screen_on_enable or reports_hit_limit_screen_on_enable or visible_screen_report_arms_waiting_state' -q
```

Observed result:

- `20 passed`

Follow-up verification for the 2026-03-19 send-path regression:

```bash
pytest tests/test_session_manager.py tests/test_claude_code_auto_continue.py tests/test_websocket.py -q
```

Observed result:

- `43 passed`

Follow-up verification for the 2026-03-19 `ccusage` parsing fix:

```bash
pytest tests/test_claude_code_auto_continue.py tests/test_session_manager.py tests/test_websocket.py -q
```

Observed result:

- `45 passed`

Follow-up verification after the stale-history fix:

```bash
pytest tests/test_claude_code_auto_continue.py tests/test_session_manager.py tests/test_websocket.py -q
```

Observed result:

- `46 passed`

Warnings seen during verification:

- existing Pydantic deprecation warning in `src/ws_models.py`
- existing `forkpty()` deprecation warning from pytest websocket tests

Neither warning was the cause of this defect.

## Practical Reproduction Notes

Best reproduction shape for this issue:

1. Open a Claude Code session in the TeleCLI web UI.
2. Wait until Claude is blocked and the terminal visibly shows a limit screen.
3. Enable `CC Auto`.
4. Watch whether the status line:
   - remains idle
   - arms a block reset
   - wrongly arms a weekly reset
   - shows `Sent "continue"` and then immediately re-arms

Known relevant blocked-screen strings:

- `100% used`
- `Resets at ...`
- `You've hit your limit · resets 11am (America/Toronto)`

## If This Breaks Again

Collect these first:

1. Exact visible terminal text from the blocked screen.
2. Current CC Auto status line before and after trigger time.
3. Output of:

```bash
ccusage blocks --json --active --offline
```

4. Server log lines around:
   - scheduling
   - `Sent delayed Claude Code 'continue' input`
   - any `Failed to send continue`
   - `Sending automation line to session ...`
   - `Submitted automation line for session ...`
   - any `ccusage scheduling failed`

Most useful next checks:

1. Confirm whether the controller logged a successful send.
2. Confirm whether the browser immediately re-reported the same stale screen.
3. Confirm whether the visible screen string changed again.
4. Confirm whether `ccusage` output shape changed again.
5. Confirm whether `usageLimitResetTime` is actually present before trusting any `ccusage` block-reset deadline.
6. Confirm whether the current reset time came from the visible rendered screen, `usageLimitResetTime`, or stale raw PTY history.

## Current Working Theory to Resume From Later

If a new regression appears, start from these questions in order:

1. Is the visible blocked screen still one of the known patterns?
2. Is the browser sending `screen_text` at the moment CC Auto is enabled?
3. Is `_parse_screen_reset_at()` extracting the correct reset time?
4. After send, is the UI showing `Sent "continue"` or re-entering a waiting state?
5. If re-entering waiting, is it because the screen is still stale or because a new genuine block occurred?
6. If send is logged but Claude does not continue, inspect the terminal/tmux input path next.
7. Confirm whether Claude auto-continue is using the submitted-line helper instead of the typing helper.
8. If CC Auto shows a future reset while Claude is clearly not blocked, inspect whether the value came from `usageLimitResetTime` or from an untrusted active-block field.
9. If a future reset appears right after a successful send, inspect whether stale raw PTY history was cleared.

## Related Files

- [src/claude_code_auto_continue.py](/home/andrey/projects/telecli/src/claude_code_auto_continue.py)
- [src/session_manager.py](/home/andrey/projects/telecli/src/session_manager.py)
- [src/web_app.py](/home/andrey/projects/telecli/src/web_app.py)
- [src/ws_models.py](/home/andrey/projects/telecli/src/ws_models.py)
- [src/terminal.py](/home/andrey/projects/telecli/src/terminal.py)
- [static/index.html](/home/andrey/projects/telecli/static/index.html)
- [tests/test_claude_code_auto_continue.py](/home/andrey/projects/telecli/tests/test_claude_code_auto_continue.py)
- [tests/test_websocket.py](/home/andrey/projects/telecli/tests/test_websocket.py)
- [tests/test_playwright_integration.py](/home/andrey/projects/telecli/tests/test_playwright_integration.py)
