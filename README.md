# TeleCLI - Terminal Access via Web and Telegram

A modern, feature-rich terminal interface accessible through web and Telegram using pexpect for proper terminal emulation.

## Features

- 🌐 **Web Interface** - Beautiful, responsive terminal UI with WebSocket support
- 📱 **Telegram Bot** - Full access via Telegram with command handlers
- 🖥️ **Pexpect Terminal** - Real interactive terminal emulation
- 📝 **Advanced Logging** - Multiple rotation strategies, configurable output
- ⚙️ **Fully Configurable** - All settings via .env file
- 🔄 **Session Management** - Isolated sessions per user
- 📊 **Multi-user Support** - Concurrent sessions with proper resource limits

## Quick Start

### Web Interface

```bash
# 1. Setup
cp .env.sample .env
# Edit .env with your settings

# 2. Run
chmod +x run_web.sh
./run_web.sh

# 3. Access
# Open http://localhost:8000 in your browser
```

### Telegram Bot

```bash
# 1. Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.sample .env
# Edit .env with your Telegram bot token

# 2. Run
python3 src/main.py
```

## Configuration

All settings are configured via `.env` file. See `.env.sample` for all available options.

### Key Settings

- `TELEGRAM_BOT_TOKEN` - Required for Telegram bot
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR (default: INFO)
- `LOG_OUTPUT` - console, file, both (default: console)
- `LOG_FILE_MODE` - append, new_each_start, timestamp_rotate (default: append)
- `TERMINAL_SHELL` - bash, sh, zsh, etc. (default: bash)
- `WEB_PORT` - Web server port (default: 8000)

## Logging System

The logging system supports multiple strategies:

### 1. Append Mode
- Keeps appending to the same file
- Simple, efficient, file grows indefinitely

### 2. New Each Start
- Creates new file on app start
- Rotates old file to `logname-YYYYMMDD-HHMMSS.log`
- Useful for tracking app restarts

### 3. Timestamp Rotate
- Automatically rotates based on interval (1d, 1w, 1m)
- Keeps timestamped files
- Automatic cleanup when directory exceeds size limit

### Write Position
- `top` - New entries at top (requires full file rewrite)
- `bottom` - New entries at bottom (efficient, recommended)

### Cleanup
- Automatically deletes oldest files when `LOG_DIR_MAX_SIZE` exceeded
- Respects max file size with warnings

## File Structure

```
telecli/
├── WARP.md                      # Project rules and specifications
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.sample                  # Configuration template
├── .gitignore
├── run_web.sh                   # Web server launcher
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── config.py                # Configuration management
│   ├── logger.py                # Logging system
│   ├── terminal.py              # Pexpect terminal wrapper
│   ├── session_manager.py       # Session lifecycle
│   ├── web_app.py               # FastAPI web server
│   └── telegram_bot.py          # Telegram bot
├── static/
│   ├── index.html               # Web UI
│   └── style.css                # Styling
└── tests/
    ├── __init__.py
    ├── test_logger.py
    ├── test_terminal.py
    ├── test_config.py
    └── test_session_manager.py
```

## Usage

### Web Chat
1. Start: `./run_web.sh`
2. Open: http://localhost:8000
3. Type commands and press Enter
4. Click Reset to clear session

### Telegram Bot
1. Start: `python3 src/main.py`
2. Find your bot on Telegram
3. Send `/start`
4. Send any shell command

### Commands (Telegram)
- `/start` - Welcome message
- `/help` - Show help
- `/reset` - Reset session

## API Endpoints

### WebSocket
```
WS /ws/{client_id}
```
Real-time terminal interface. Send JSON: `{"message": "command"}`

### REST
- `GET /` - Web UI
- `GET /health` - Health check
- `GET /stats` - Session statistics
- `POST /reset/{client_id}` - Reset session

## Development

### Branch Workflow
- Always work on feature branches: `feature/description` or `fix/description`
- Never commit to main
- Follow project rules in WARP.md

### Testing
```bash
pytest tests/
```

### Code Style
- Use logging for all output: `logger = logging.getLogger(__name__)`
- No hardcoded paths or tokens
- Proper error handling with logging

## Deployment

### Local Development
```bash
./run_web.sh  # Web server
# or
python3 src/main.py  # Telegram bot
```

### Production Web
```bash
uvicorn src.web_app:app --host 0.0.0.0 --port 8000
```

### Production Telegram
Use systemd service or Docker for reliability.

## Troubleshooting

### Web Connection Issues
- Check `.env` exists and is valid
- Verify port 8000 is available
- Check logs: `tail -f logs/telecli.log`

### Terminal Commands Not Working
- Verify shell is installed: `which bash`
- Check terminal timeout setting
- Review error logs

### Telegram Bot Not Responding
- Verify bot token in `.env`
- Check internet connection
- Review logs for errors

## Performance

- Each session uses ~50MB memory
- Adjust `TERMINAL_MAX_SESSIONS` based on available memory
- Log cleanup is automatic, respects size limits
- WebSocket handles many concurrent connections efficiently

## Security Features

### Command Filtering

Enable command whitelisting to prevent arbitrary command execution:

```ini
ALLOWED_COMMANDS_ONLY=true
ALLOWED_COMMANDS_FILE=./examples/allowed_commands.txt
```

When enabled, only commands in the whitelist can be executed.
See `examples/allowed_commands.txt` for the default list.

### Authentication

Require authentication tokens for terminal access:

```ini
AUTH_REQUIRED=true
AUTH_TOKEN=your-strong-random-token
```

### SSL/TLS

Enable HTTPS by providing certificate and key paths:

```ini
WEB_SSL_CERT=/path/to/cert.pem
WEB_SSL_KEY=/path/to/key.pem
```

### General Security Notes

- Session isolation per user
- Logs may contain sensitive data
- Use HTTPS in production
- Enable authentication for production deployments

## Future Enhancements

- [ ] File upload/download support
- [ ] User authentication
- [ ] Message history persistence
- [ ] Rate limiting
- [ ] Admin dashboard
- [ ] Webhook support for Telegram
- [ ] Custom command hooks

## License

MIT

## Support

For issues and features:
1. Check troubleshooting section
2. Review WARP.md for project rules
3. Check logs for error details
4. Verify configuration

---

**Happy terminal access!** 🚀
