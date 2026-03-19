# PR Review Log: PR-8 feat-improve-telegram-session-controls

## PR

- Number: 8
- Title: `feat: improve telegram session controls`
- URL: https://github.com/malandr/telecli/pull/8
- Reviewer: `copilot-pull-request-reviewer[bot]`
- Review ID: `PRR_kwDOQoRQ3s7swyjN`

## Summary

All 8 inline comments were technically valid for this branch.

Actions taken:

- replaced the quadratic per-chunk `_format_command_output("".join(...))` check with a cheap chunk-level meaningful-output detector
- moved Telegram command output timeouts into dedicated `Config` fields instead of hardcoded module constants
- used `ENV_FILE` in `run_web.sh` by reporting which `.env` path was selected
- reduced Telegram bot test runtime by shrinking the artificial sleeps and monkeypatching the new timeout config in tests
- fixed `/start` to report the actual current Telegram alias instead of hardcoding `main`
- rejected whitespace-only `/newsession` names
- made alias allocation auto-suffix on collisions so `/usesession` and the session picker do not fail on name clashes

## Verification

Commands run after the fixes:

```bash
pytest tests/test_telegram_bot.py tests/test_main.py tests/test_run_web.py tests/test_service_wiring.py tests/test_config.py -q
python3 -m py_compile src/telegram_bot.py src/main.py src/web_app.py src/config.py
```

Observed results:

- `34 passed`
- `py_compile` completed without errors

## Comment Responses

### 1. Quadratic formatting in `_execute_session_command`

- Comment ID: `2957343218`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343218
- Evaluation: valid
- Action: added `_chunk_has_meaningful_output(...)` and switched the collector to a cheap chunk-level signal instead of repeatedly joining and formatting the entire buffer on every chunk
- PR response:

```text
Fixed. `_execute_session_command()` now tracks meaningful output with a cheap chunk-level check instead of recomputing `_format_command_output("".join(collected))` on every chunk.
```

### 2. Hardcoded Telegram command-output timeouts

- Comment ID: `2957343249`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343249
- Evaluation: valid
- Action: added `Config.TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS` and `Config.TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS`, and switched the Telegram collector to read those values instead of hardcoded constants
- PR response:

```text
Fixed. I added dedicated Telegram command-output timeout config (`TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS` and `TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS`) and wired `_execute_session_command()` to use them instead of hardcoded values.
```

### 3. Unused `ENV_FILE` in `run_web.sh`

- Comment ID: `2957343273`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343273
- Evaluation: valid
- Action: kept the variable and now print the selected `.env` path during launcher startup; added coverage in `tests/test_run_web.py`
- PR response:

```text
Fixed. `run_web.sh` now reports which `.env` file it selected, so `ENV_FILE` is no longer dead code and worktree launches are easier to debug.
```

### 4. Real `asyncio.sleep(1.2)` in Telegram bot tests

- Comment ID: `2957343290`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343290
- Evaluation: valid
- Action: reduced the artificial sleeps to `0.02s` and monkeypatched the new Telegram timeout config in the test fixture so the same behaviors are covered without multi-second delays
- PR response:

```text
Fixed. The delayed-output Telegram tests now monkeypatch the Telegram timeout config to small values and use `0.02s` sleeps instead of `1.2s`, which keeps the same behavior coverage while cutting test runtime substantially.
```

### 5. `/start` hardcodes alias `main`

- Comment ID: `2957343309`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343309
- Evaluation: valid
- Action: changed `/start` to render the current alias from `TelegramUserSessions` instead of hardcoding `main`; added a regression in `tests/test_telegram_bot.py`
- PR response:

```text
Fixed. `/start` now reports the user's actual current Telegram alias instead of hardcoding `main`, and there’s a regression covering that path.
```

### 6. `/newsession` accepts whitespace-only names

- Comment ID: `2957343320`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343320
- Evaluation: valid
- Action: added an empty-name guard after stripping and return `Session name cannot be empty`; added a regression in `tests/test_telegram_bot.py`
- PR response:

```text
Fixed. `/newsession` now rejects whitespace-only names after stripping and returns `Session name cannot be empty`, with a regression in `tests/test_telegram_bot.py`.
```

### 7. `/usesession` alias collision can raise `ValueError`

- Comment ID: `2957343332`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343332
- Evaluation: valid
- Action: changed alias allocation to auto-suffix on collisions instead of raising, so switching to an existing session named `main` becomes `main-2`; added a regression in `tests/test_telegram_bot.py`
- PR response:

```text
Fixed. Alias allocation now auto-suffixes on collisions instead of raising, so `/usesession` can switch to an existing session even when its name collides with a Telegram alias. Added a regression for that case.
```

### 8. `handle_session_picker` alias collision can raise `ValueError`

- Comment ID: `2957343342`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2957343342
- Evaluation: valid
- Action: covered by the same alias-allocation change as comment 7; added a separate regression for the picker callback path
- PR response:

```text
Fixed. The same collision-safe alias allocation is now used when the session picker targets a session whose name collides with an existing alias, and there’s a dedicated regression for the picker callback path.
```

## Additional Review

- Review ID: `PRR_kwDOQoRQ3s7s3ySa`

All 3 newly added inline comments were technically valid for this branch.

Additional actions taken:

- added a fail-fast guard in `src/telegram_bot.py` so direct Telegram startup rejects a missing `TELEGRAM_BOT_TOKEN` with a clear `ValueError` before building the Telegram `Application`
- changed the combined `src.main` entrypoint to skip Telegram startup in webhook mode and log why, instead of attempting to bind `WEB_PORT` twice
- updated the README prerequisite to Python 3.10+ and documented that webhook deployments must run the Telegram bot separately from the combined entrypoint
- added regressions in `tests/test_telegram_bot.py`, `tests/test_main.py`, and `tests/test_readme.py`

Additional verification:

```bash
pytest tests/test_telegram_bot.py tests/test_main.py tests/test_run_web.py tests/test_service_wiring.py tests/test_config.py tests/test_readme.py -q
python3 -m py_compile src/telegram_bot.py src/main.py src/web_app.py src/config.py
```

Observed results:

- `37 passed`
- `py_compile` completed without errors

### 9. `telegram_bot.main()` crashes with a missing token

- Comment ID: `2959024437`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2959024437
- Evaluation: valid
- Action: added an explicit top-level guard in `telegram_bot.main()` that raises `ValueError("TELEGRAM_BOT_TOKEN is required to start the Telegram bot")` before any `Application.builder()` call; added a regression in `tests/test_telegram_bot.py`
- PR response:

```text
Fixed. `telegram_bot.main()` now fails fast with a clear `ValueError` when `TELEGRAM_BOT_TOKEN` is missing, before building the Telegram `Application`, and there’s a regression covering the direct startup path.
```

### 10. Combined `src.main` startup collides with webhook mode on `WEB_PORT`

- Comment ID: `2959024472`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2959024472
- Evaluation: valid
- Action: taught `src.main` to skip Telegram startup when `TELEGRAM_WEBHOOK_URL` is configured and log a warning that webhook deployments must run the Telegram bot separately, avoiding a second bind on `WEB_PORT`; added a regression in `tests/test_main.py`
- PR response:

```text
Fixed. The combined `src.main` entrypoint now skips Telegram startup in webhook mode and logs why, instead of trying to bind `WEB_PORT` twice. There’s also a regression covering that combined-startup path.
```

### 11. README still claims Python 3.8 support

- Comment ID: `2959024497`
- URL: https://github.com/malandr/telecli/pull/8#discussion_r2959024497
- Evaluation: valid
- Action: updated the README prerequisite to `Python 3.10 or higher` and added a small README regression test in `tests/test_readme.py`
- PR response:

```text
Fixed. The README now documents `Python 3.10 or higher`, which matches the 3.10-only syntax already used in the codebase, and I added a small README regression test for that prerequisite line.
```
