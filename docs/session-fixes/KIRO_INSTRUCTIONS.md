# Kiro Instructions for TeleCLI Project

## Project Context
TeleCLI is a web and Telegram interface for interactive terminal sessions using pexpect for proper terminal emulation and state management.

## Critical Git Workflow Rules
- **NEVER commit directly to main branch**
- **ALWAYS create feature branches BEFORE starting any task**: `feature/description` or `fix/description`
- **Create branch immediately** when user requests work - don't wait until completion
- **Commit frequently** as soon as each logical unit of work is delivered
- **Create PR immediately** once user confirms work is validated and complete
- Check current branch before any commits (`git branch` or `git status`)
- Use descriptive commit messages following conventional commits format
- Push branches early and often to backup work

## Git Workflow Steps
1. **Before Starting Work**: `git checkout -b feature/task-description`
2. **During Work**: Commit logical units frequently with clear messages
3. **After User Validation**: Create comprehensive PR with detailed description
4. **Branch Naming**: Use clear, descriptive names (feature/llm-optimization, fix/websocket-errors)
5. **Commit Messages**: Use conventional format (feat:, fix:, docs:, refactor:, etc.)

## Configuration Management
- All settings must be configurable via `.env` file with sensible defaults
- Use `config.py` for centralized configuration loading
- Never hardcode paths, tokens, or configuration values
- Reference `.env.sample` for configuration structure

## Key Configuration Areas
### Logging System
- Comprehensive logging with multiple output handlers (console, file)
- Multiple rotation strategies: append, new_each_start, timestamp_rotate
- Configurable log levels, formats, and cleanup policies
- Log format: `[TIMESTAMP] [LEVEL] [MODULE] message`

### Terminal Management
- Pexpect-based terminal wrapper for proper session handling
- Configurable shell, timeout, max sessions, encoding
- Isolated sessions per user with proper cleanup

### Security & Access
- Optional authentication with token-based access
- Command whitelisting capability
- Configurable security policies

## Code Structure Guidelines
- Use `src/` directory for all source code
- Modular design: separate concerns into focused modules
- All modules use `logger = logging.getLogger(__name__)`
- Async/await for web endpoints and non-blocking operations
- Proper error handling with logging before raising

## Development Workflow
1. **FIRST**: Create feature branch immediately when user requests work
2. Check current git branch (must not be main)
3. Make changes following project structure
4. **Commit frequently** - each logical unit of work gets its own commit
5. Test configuration loading and logging
6. Verify no hardcoded values
7. Run tests before each commit
8. **Final Step**: Create PR once user validates the work is complete

## Testing Requirements
- Unit tests for core modules (logger, terminal, config, session_manager)
- Integration tests for session management
- Manual testing on both web and Telegram interfaces

## Key Dependencies
- fastapi (web server)
- python-telegram-bot (Telegram integration)
- pexpect (terminal interaction)
- python-dotenv (configuration loading)
- uvicorn (ASGI server)

## Before Any Commits
1. **CRITICAL**: Verify on feature branch (not main) - `git branch`
2. Run `pytest tests/` if tests exist
3. Check `.env` configuration works properly
4. Ensure no hardcoded paths or sensitive data
5. Confirm branch name clearly indicates feature/fix
6. Write clear, descriptive commit message

## PR Creation Requirements
- Create PR only after user confirms work is validated and complete
- Include comprehensive description of changes
- List all files modified and why
- Document any breaking changes or migration steps
- Add testing notes and verification steps
- Reference any related issues or tasks

## Logging Best Practices
- DEBUG: Internal flow and detailed operations
- INFO: User actions and significant events
- WARNING: Recoverable issues or important notices
- ERROR: Failures that affect functionality
- Include context (session_id, user_id) in logs
- Never use print() for logging - always use logger

## Session Management
- Each user gets isolated pexpect session
- Track session states: active, idle, terminated
- Clean up resources on session close
- Handle terminal resize events properly