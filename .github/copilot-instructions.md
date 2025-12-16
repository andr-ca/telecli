# Copilot Instructions for TeleCLI (Aligned with WARP.md)

## 1. Git Workflow
- Only suggest or apply changes to feature branches (never `main`).
- Enforce branch naming: `feature/description` or `fix/description`.
- Never generate direct commits to `main`.

## 2. Configuration
- All configuration must be loaded from `.env` (use `python-dotenv`).
- Use sensible defaults for all config values.
- Never hardcode secrets, tokens, or paths.

## 3. Logging
- Use `logger = logging.getLogger(__name__)` in all modules.
- Log at appropriate levels: DEBUG (internal), INFO (user actions), WARNING/ERROR (issues).
- Never use `print()` for logging.
- Log format: `[TIMESTAMP] [LEVEL] [MODULE] message`.
- Support all log rotation and output strategies described in WARP.md.
- Always log errors before raising.

## 4. Terminal Sessions
- Each user/session must have an isolated pexpect session.
- Track session state and clean up on close.
- Handle terminal resize events.

## 5. Async/Await
- All FastAPI endpoints must be async.
- Terminal operations should be non-blocking (use asyncio).

## 6. Testing
- Ensure unit tests for logger, terminal, config, and session management.
- Run `pytest tests/` before any commit.

## 7. Security
- Never expose secrets or tokens in code or logs.
- Support all security-related `.env` options (auth, allowed commands, etc).

## 8. Code Structure
- Place new code in the correct module as per the project structure in WARP.md.
- Use utility functions in `utils.py` if needed.

## 9. Pre-commit Checklist
- All code must be on a feature branch.
- All tests must pass.
- No hardcoded paths/tokens.
- Branch name must indicate feature/fix.
