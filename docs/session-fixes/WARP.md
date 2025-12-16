# TeleCLI - Project Rules

## Core Requirements

### Git Workflow
- **CRITICAL**: Always work on feature branches, NEVER commit to main
- Branch naming: `feature/description` or `fix/description`
- All changes must be on a branch before being considered complete
- No direct commits to `main` under any circumstances

### Application Overview
TeleCLI is a web and Telegram interface for interactive terminal sessions wrapped with pexpect for proper terminal emulation and state management.

## Configuration (.env)

All configuration must be externalizable to `.env` with sensible defaults:

### Telegram Configuration
- `TELEGRAM_BOT_TOKEN` - Required for Telegram bot functionality
- `TELEGRAM_WEBHOOK_URL` - Optional webhook URL (default: polling mode)

### Logging Configuration
- `LOG_LEVEL` - Global log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `LOG_OUTPUT` - Where to log: "console", "file", "both" (default: console)
- `LOG_FILE_DIR` - Directory for log files (default: ./logs)
- `LOG_FILE_NAME` - Base name for log files, without extension (default: telecli)
- `LOG_FILE_MODE` - Log file strategy:
  - `append` - Append to existing file (default)
  - `new_each_start` - Create new file each time app starts
  - `timestamp_rotate` - Save current as logname-YYYYMMDD-HHMMSS.log, start fresh
- `LOG_FILE_MAX_SIZE` - Max size per log file in MB before rotation (default: 100)
- `LOG_DIR_MAX_SIZE` - Max total size of logs directory in MB (default: 1000)
- `LOG_ROTATION_INTERVAL` - Rotation interval: 1d, 1w, 1m (default: 1d)
- `LOG_WRITE_POSITION` - Where to write new entries: "top" or "bottom" (default: bottom)

### Terminal Configuration
- `TERMINAL_SHELL` - Shell to use: bash, sh, zsh, etc. (default: bash)
- `TERMINAL_TIMEOUT` - Command timeout in seconds (default: 300)
- `TERMINAL_MAX_SESSIONS` - Max concurrent terminal sessions (default: 100)
- `TERMINAL_ENCODING` - Character encoding (default: utf-8)

### Web Server Configuration
- `WEB_HOST` - Web server host (default: 127.0.0.1)
- `WEB_PORT` - Web server port (default: 8000)
- `WEB_SSL_CERT` - Path to SSL certificate (optional)
- `WEB_SSL_KEY` - Path to SSL key (optional)

### Security Configuration
- `AUTH_REQUIRED` - Require authentication: true/false (default: false)
- `AUTH_TOKEN` - Static auth token for API access (optional)
- `ALLOWED_COMMANDS_ONLY` - Restrict to whitelist: true/false (default: false)
- `ALLOWED_COMMANDS_FILE` - Path to allowed commands file (optional)

## Logging System Requirements

### Output Handlers
1. **Console Handler** - Output to stdout/stderr with proper formatting
2. **File Handler** - Output to rotating log files with full control

### Log Levels
All messages must include level: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Log Format
```
[TIMESTAMP] [LEVEL] [MODULE] message
```
Example: `[2025-12-13 21:14:18] [INFO] [telegram_bot] User session started: user_id=123`

### File Rotation Strategies

**Append Mode** (`append`)
- Keep appending to the same file
- Use `LOG_FILE_MAX_SIZE` to track when to warn about size
- No automatic rotation, user responsibility

**New Each Start** (`new_each_start`)
- On app start, rename current log file to `logname-YYYYMMDD-HHMMSS.log`
- Start writing to fresh `logname.log`
- Old files remain in directory (subject to `LOG_DIR_MAX_SIZE`)

**Timestamp Rotate** (`timestamp_rotate`)
- Write to `logname-YYYYMMDD-HHMMSS.log` with configurable rotation interval
- When interval passes (1d, 1w, 1m), start new file
- Old files cleaned up when `LOG_DIR_MAX_SIZE` exceeded

### Write Position Strategy
- **top** - Write new entries at top of file (requires full file rewrite for rotation mode)
- **bottom** - Write new entries at bottom of file (standard, efficient)

### Cleanup Strategy
When `LOG_DIR_MAX_SIZE` is exceeded:
1. Sort log files by creation time
2. Delete oldest files until total size < threshold

## Code Structure

```
telecli/
├── WARP.md                      # This file
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── .env.sample                  # Example configuration
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── config.py                # Configuration management (loads from .env)
│   ├── logger.py                # Logging system with all rotation strategies
│   ├── terminal.py              # Pexpect-based terminal wrapper
│   ├── session_manager.py       # Session lifecycle management
│   ├── web_app.py               # FastAPI web server
│   ├── telegram_bot.py          # Telegram bot integration
│   └── utils.py                 # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_logger.py
│   ├── test_terminal.py
│   ├── test_config.py
│   └── test_session_manager.py
└── static/
    ├── index.html               # Web UI
    └── style.css
```

## Development Guidelines

### Logging in Code
- All modules must use: `logger = logging.getLogger(__name__)`
- Log at appropriate levels: DEBUG for internal flow, INFO for user actions, WARNING/ERROR for issues
- Never print to stdout directly (except for CLI output)

### Error Handling
- All errors must be logged before raising
- User-facing errors should have helpful messages
- Include relevant context (session_id, user_id, etc.) in error logs

### Terminal Session Management
- Each user gets isolated pexpect session
- Track session state: active, idle, terminated
- Clean up resources on session close
- Handle terminal resize events

### Async/Await
- Web API endpoints must be async
- Terminal operations should be non-blocking
- Use asyncio for concurrent operations

## Testing Requirements
- Unit tests for logger (all rotation modes)
- Unit tests for terminal wrapper
- Unit tests for config loading
- Integration tests for session management
- Manual testing on web and Telegram interfaces

## Dependencies
- fastapi - Web server
- python-telegram-bot - Telegram integration
- pexpect - Terminal interaction
- python-dotenv - .env file loading
- uvicorn - ASGI server

## Before Committing
1. All code on feature branch (never main)
2. Run tests: `pytest tests/`
3. Check logs configured properly with .env
4. Verify no hardcoded paths or tokens
5. Git branch name clearly indicates feature/fix
