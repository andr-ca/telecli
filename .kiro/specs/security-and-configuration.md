---
title: "Security and Configuration"
description: "Security model and configuration management"
version: "1.0"
---

# Security and Configuration Spec

## Security Model

### Multi-Layer Security
1. **Authentication**: Token-based for web, user whitelist for Telegram
2. **Command Filtering**: Whitelist-based command restriction
3. **Process Isolation**: Isolated terminal sessions per user
4. **SSL/TLS**: Encrypted connections for production

## Command Filtering System

### Command Filter Class
**Location**: `src/command_filter.py` - `CommandFilter`

#### Features
- Whitelist-based command validation
- File-based configuration with comments support
- Command name extraction from full command strings
- Security event logging for blocked commands

### Configuration Format
**Location**: `examples/allowed_commands.txt`

#### Format Example
```
# Comments start with #
# Empty lines ignored
ls
cat
grep
python3
git
# More commands...
```

#### Integration Points
- Terminal session input validation
- Real-time command checking during execution
- Security logging for audit trails
- Configuration reload capability

## Authentication System

### Web Interface Authentication
- **Token-based**: Authentication via `AUTH_TOKEN` configuration
- **WebSocket**: Query parameter validation (`?token=...`)
- **Storage**: LocalStorage token persistence in browser
- **Security**: Unauthorized connection rejection with code 1008

### Telegram User Whitelist
- **User ID-based**: Access control via `ALLOWED_TELEGRAM_USERS`
- **Format**: Comma-separated user ID list
- **Behavior**: Empty list allows all users
- **Enforcement**: Runtime validation with user blocking

## SSL/TLS Support

### Configuration
- `WEB_SSL_CERT`: SSL certificate file path
- `WEB_SSL_KEY`: SSL private key file path
- **Validation**: File existence checking during startup
- **Integration**: Secure WebSocket (WSS) support

### Production Deployment
- Certificate and key file validation
- Automatic HTTPS/WSS protocol selection
- Secure cookie and token handling

## Configuration Management

### Environment-Based Configuration
**Location**: `src/config.py`

#### Configuration Categories

##### Telegram Configuration
```python
TELEGRAM_BOT_TOKEN: str          # Required bot token
TELEGRAM_WEBHOOK_URL: str        # Optional webhook URL
ALLOWED_TELEGRAM_USERS: str      # Comma-separated user IDs
```

##### Security Configuration
```python
AUTH_REQUIRED: bool              # Require web authentication
AUTH_TOKEN: str                  # Authentication token
ALLOWED_COMMANDS_ONLY: bool      # Enable command filtering
ALLOWED_COMMANDS_FILE: str       # Command whitelist file path
```

##### Web Server Configuration
```python
WEB_HOST: str                    # Server bind address
WEB_PORT: int                    # Server port (1-65535)
WEB_SSL_CERT: str               # SSL certificate path
WEB_SSL_KEY: str                # SSL key path
```

### Validation System

#### Type Validation
- Integer bounds checking with min/max values
- Boolean parsing from string values
- String validation with allowed value sets
- File path validation with existence checks

#### Security Validation
- SSL certificate and key file pairing
- Command whitelist file accessibility
- Authentication token presence when required
- Network configuration validation

### Runtime Security

#### Process Isolation
- Each session runs in isolated pexpect process
- Proper resource cleanup and process termination
- Timeout-based session management
- Memory and connection limits enforcement

#### Resource Limits
- Maximum concurrent sessions (`TERMINAL_MAX_SESSIONS`)
- Session timeout controls (`TERMINAL_TIMEOUT`)
- Log directory size limits (`LOG_DIR_MAX_SIZE`)
- AI proxy iteration limits (`AI_PROXY_MAX_ITERATIONS`)

## Implementation Files

### Core Security Files
- `src/config.py` - Configuration management and validation
- `src/command_filter.py` - Command filtering implementation
- `src/web_app.py` - Web authentication and SSL
- `src/telegram_bot.py` - Telegram user authorization

### Configuration Files
- `.env` - Environment configuration (not in repo)
- `.env.sample` - Configuration template
- `examples/allowed_commands.txt` - Command whitelist example

### Security Best Practices
- No hardcoded secrets or tokens
- Environment-based configuration
- Comprehensive input validation
- Audit logging for security events
- Graceful error handling without information leakage