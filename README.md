# TeleCLI

TeleCLI is a web-based terminal interface that allows users to interact with command-line sessions through a web browser or Telegram bot. It provides isolated terminal sessions, supports multiple users, and includes optional AI proxy features for automated terminal interactions.

## Features

- **Web Interface**: Access terminal sessions via a modern web UI with WebSocket support
- **Telegram Bot Integration**: Control terminals through Telegram messages
- **Session Management**: Isolated terminal sessions per user with configurable timeouts
- **Security**: Authentication tokens, command whitelisting, and user restrictions
- **AI Proxy**: Optional AI-powered automation for terminal interactions (supports Gemini, Claude, GitHub models)
- **Logging**: Comprehensive logging with rotation and multiple output options
- **Async Architecture**: Built with FastAPI for high performance and scalability

## Prerequisites

- Python 3.8 or higher
- Linux/macOS/Windows (Linux recommended for full terminal compatibility)
- Telegram Bot Token (optional, for Telegram integration)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd telecli
   ```

2. **Set up configuration**:
   ```bash
   cp .env.sample .env
   # Edit .env with your settings (see Configuration section below)
   ```

3. **Run the setup script** (recommended):
   ```bash
   ./run_web.sh
   ```
   This will:
   - Create a Python virtual environment
   - Install all dependencies
   - Start the web server
   - Start the Telegram bot when `TELEGRAM_BOT_TOKEN` is configured

   Or install manually:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Configuration

TeleCLI uses environment variables for configuration. Copy `.env.sample` to `.env` and configure the following key settings:

### Required Settings

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (get from @BotFather)
- `AUTH_TOKEN`: Authentication token for WebSocket connections

### Optional Settings

- `WEB_HOST`: Host to bind the web server (default: 127.0.0.1)
- `WEB_PORT`: Port for the web server (default: 8000)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `TERMINAL_SHELL`: Default shell (default: bash)
- `ALLOWED_COMMANDS_ONLY`: Enable command whitelisting (true/false)
- `AI_PROXY_ENABLED`: Enable AI proxy features (true/false)

See `.env.sample` for all available configuration options.

## Running the Application

### Development Mode

Use the provided script:
```bash
./run_web.sh
```

Or run directly:
```bash
source venv/bin/activate
python -m src.main
```

The application will start both the web server and Telegram bot (if configured).
When running from a git worktree, `run_web.sh` will also accept a shared `.env` from a parent checkout directory.

### Production Deployment

For production, consider using a process manager like systemd or Docker. The application supports SSL certificates via `WEB_SSL_CERT` and `WEB_SSL_KEY`.

### Accessing the Application

- **Web Interface**: Open `http://localhost:8000` (or your configured host/port)
- **Telegram Bot**: Send messages to your bot (if configured)

## Testing

### Unit Tests

Run the test suite with pytest:
```bash
source venv/bin/activate
pytest tests/
```

### Playwright Integration Tests

Run browser-based tests:
```bash
python run_playwright_tests.py
```

This will install Playwright browsers if needed and run the full test suite.

### Coverage

Generate coverage reports:
```bash
pytest --cov=src --cov-report=html tests/
```

## Development

### Git Workflow

- Always work on feature branches: `feature/description` or `fix/description`
- Never commit directly to `main`
- Follow the pre-commit checklist:
  - All tests pass (`pytest tests/`)
  - Code is on a feature branch
  - No hardcoded secrets/tokens/paths
  - Branch name indicates feature/fix

### Code Structure

- `src/`: Main application code
- `tests/`: Test files
- `static/`: Web assets (HTML, CSS)
- `examples/`: Sample configuration files
- `docs/`: Documentation and plans

### Key Components

- `web_app.py`: FastAPI application with WebSocket endpoints
- `telegram_bot.py`: Telegram bot handler
- `terminal.py`: Terminal session management with pexpect
- `session_manager.py`: User session lifecycle management
- `ai_proxy.py`: AI-powered terminal automation
- `config.py`: Configuration management with Pydantic

## Security

- Use strong authentication tokens
- Enable command whitelisting for production
- Configure user restrictions via `ALLOWED_TELEGRAM_USERS`
- Keep dependencies updated
- Monitor logs for suspicious activity

## Troubleshooting

### Common Issues

1. **Permission denied on terminal commands**: Ensure the application has proper permissions or use `sudo` carefully
2. **WebSocket connection fails**: Check `AUTH_TOKEN` and firewall settings
3. **Telegram bot not responding**: Verify `TELEGRAM_BOT_TOKEN` and webhook configuration
4. **AI proxy errors**: Check API keys and provider configuration

### Logs

Check logs in `./logs/` directory. Log level can be adjusted in `.env`.

## Contributing

1. Follow the Git workflow guidelines
2. Write tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting PRs

## License

[Add license information here]
