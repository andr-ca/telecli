# TeleCLI Design Document

## Overview

TeleCLI is a web-based terminal interface that provides secure, isolated command-line access through multiple channels: web browsers and Telegram bots. The application supports real-time terminal interactions via WebSockets, session management, and optional AI-powered automation for terminal commands.

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Telegram Bot  │    │   AI Providers  │
│                 │    │                 │    │                 │
│  ┌────────────┐ │    │  ┌────────────┐ │    │  ┌────────────┐ │
│  │ WebSocket  │ │    │  │ Telegram   │ │    │  │ Gemini CLI │ │
│  │ Client     │ │    │  │ API        │ │    │  │ Claude CLI │ │
│  └────────────┘ │    │  └────────────┘ │    │  │ GitHub CLI │ │
└─────────────────┘    └─────────────────┘    └───────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────┐
                    │    FastAPI Server   │
                    │                     │
                    │  ┌────────────────┐ │
                    │  │ SessionManager │ │
                    │  │                │ │
                    │  │  ┌───────────┐ │ │
                    │  │  │Terminal   │ │ │
                    │  │  │Sessions   │ │ │
                    │  │  └───────────┘ │ │
                    │  └────────────────┘ │
                    │                     │
                    │  ┌────────────────┐ │
                    │  │   AI Proxy     │ │
                    │  │                │ │
                    │  │  ┌───────────┐ │ │
                    │  │  │Providers  │ │ │
                    │  │  └───────────┘ │ │
                    │  └────────────────┘ │
                    └─────────────────────┘
```

### Core Components

#### 1. Web Application (`web_app.py`)
- **Framework**: FastAPI with async support
- **Endpoints**:
  - `GET /`: Serves the main web interface
  - `GET /telecli`: Alternative path for web interface
  - `GET /health`: Health check endpoint
  - `GET /debug`: Debug information
  - `GET /api/sessions`: Session statistics
  - `GET /api/ai-proxy/config`: AI proxy configuration
  - `GET /api/llm-monitor`: LLM interaction monitoring
  - `WebSocket /ws/{client_id}`: Real-time terminal communication
- **Middleware**: TrustedHostMiddleware for security
- **Static Files**: Serves HTML, CSS, and JavaScript assets

#### 2. Telegram Bot (`telegram_bot.py`)
- **Framework**: python-telegram-bot
- **Features**:
  - Polling or webhook-based message handling
  - User authentication via allowed user lists
  - Command processing and terminal output formatting
  - Session management integration
- **Integration**: Runs concurrently with web server in main.py

#### 3. Session Manager (`session_manager.py`)
- **Purpose**: Manages terminal session lifecycle
- **Features**:
  - Creates and destroys terminal sessions
  - Tracks session state and statistics
  - Integrates AI proxy functionality
  - Handles session cleanup on disconnect
- **Threading**: Uses asyncio for concurrent session handling

#### 4. Terminal Session (`terminal.py`)
- **Backend**: pexpect for pseudo-terminal management
- **Features**:
  - Isolated bash sessions per user
  - Real-time output streaming
  - Command execution with timeout handling
  - Terminal resize support
  - Session state persistence
- **Security**: Command filtering and user isolation

#### 5. AI Proxy (`ai_proxy.py`)
- **Purpose**: Provides AI-powered terminal automation
- **Features**:
  - Multiple LLM provider support (Gemini, Claude, GitHub)
  - Fallback provider chains for reliability
  - Context-aware command suggestions
  - Rate limiting and error handling
  - Configurable system prompts
- **Integration**: Optional per-session activation

#### 6. LLM Providers (`*_provider.py`)
- **Gemini Provider**: Interfaces with Google Gemini CLI
- **Claude Provider**: Interfaces with Anthropic Claude CLI
- **GitHub Provider**: Interfaces with GitHub Copilot CLI
- **Common Interface**: Standardized response handling and error detection

#### 7. Configuration (`config.py`)
- **Backend**: Pydantic for validation
- **Sources**: Environment variables from .env file
- **Categories**:
  - Telegram settings (bot token, webhook, users)
  - Web server settings (host, port, SSL)
  - Terminal settings (shell, timeout, sessions)
  - Security settings (auth, command filtering)
  - AI proxy settings (providers, prompts, limits)
  - Logging settings (level, output, rotation)

#### 8. Logging (`logger.py`)
- **Backend**: Python logging with custom formatting
- **Features**:
  - Multiple output destinations (console, file, both)
  - Log rotation and size limits
  - Configurable log levels
  - Structured logging for debugging

#### 9. WebSocket Models (`ws_models.py`)
- **Purpose**: Defines message formats for WebSocket communication
- **Message Types**:
  - Terminal input/output
  - Session control (resize, close)
  - AI proxy control (enable/disable)
  - Error messages
- **Validation**: Pydantic models for type safety

## Data Flow

### Web Interface Flow

1. **Connection Establishment**:
   ```
   Browser → WebSocket /ws/{client_id} → Auth Check → Session Creation
   ```

2. **Terminal Interaction**:
   ```
   User Input → WebSocket Message → SessionManager → TerminalSession → pexpect
   pexpect Output → TerminalSession → WebSocket → Browser Display
   ```

3. **AI Proxy Integration**:
   ```
   Terminal Output → AI Proxy → LLM Provider → Command Suggestion → WebSocket
   ```

### Telegram Bot Flow

1. **Message Reception**:
   ```
   Telegram API → Bot Handler → User Auth → Session Lookup/Create
   ```

2. **Command Processing**:
   ```
   User Message → Command Filter → TerminalSession → pexpect
   pexpect Output → Formatted Response → Telegram API
   ```

## Security Design

### Authentication
- **WebSocket**: Token-based authentication via URL parameter
- **Telegram**: User ID whitelist validation
- **Session Isolation**: Each user gets isolated terminal environment

### Authorization
- **Command Filtering**: Whitelist/blacklist based on configuration
- **User Restrictions**: Configurable allowed user lists
- **Session Limits**: Maximum concurrent sessions per user

### Data Protection
- **No Persistent Storage**: Terminal sessions are ephemeral
- **Log Sanitization**: Sensitive data filtering in logs
- **SSL/TLS**: Optional certificate-based encryption

## Session Management

### Session Lifecycle

```
Create Session → Initialize Terminal → Attach AI Proxy → Handle Messages → Cleanup
     ↓              ↓              ↓              ↓              ↓
  User Connect   pexpect spawn   Provider setup   I/O Loop    Close pty
```

### Session State
- **Active**: Terminal running, accepting commands
- **Inactive**: Terminal paused, resources preserved
- **Closed**: Terminal terminated, resources freed

### Resource Management
- **Memory**: Buffer limits for output history
- **CPU**: Timeout limits for command execution
- **Concurrency**: Maximum sessions per user and globally

## AI Proxy Architecture

### Provider Chain
```
Primary Provider → Success: Return Result
                → Rate Limit: Try Fallback
                → Error: Try Next Fallback
                → All Fail: Return Error
```

### Context Management
- **Buffer Size**: Configurable output history length
- **Context Window**: Sliding window of recent terminal activity
- **Prompt Engineering**: System prompts for consistent behavior

### Error Handling
- **Rate Limiting**: Automatic fallback on 429 errors
- **Timeout**: Configurable request timeouts
- **Provider Failure**: Graceful degradation to manual mode

## Deployment Considerations

### Development
- **Local Setup**: Virtual environment with run_web.sh
- **Hot Reload**: Uvicorn development server
- **Debug Tools**: Health endpoints and debug logging

### Production
- **Process Management**: systemd or Docker containers
- **Reverse Proxy**: Nginx/Apache for SSL termination
- **Load Balancing**: Multiple instances behind load balancer
- **Monitoring**: Log aggregation and health checks

### Scaling
- **Horizontal**: Multiple FastAPI instances
- **Session Affinity**: Sticky sessions for WebSocket connections
- **Shared State**: Redis for cross-instance session coordination

## Error Handling

### Categories
- **Configuration Errors**: Startup validation failures
- **Authentication Errors**: Invalid tokens/users
- **Terminal Errors**: pexpect failures, timeouts
- **Network Errors**: WebSocket disconnections
- **AI Provider Errors**: API failures, rate limits

### Recovery Strategies
- **Graceful Degradation**: Continue without failed components
- **Automatic Retry**: Transient error recovery
- **User Notification**: Clear error messages
- **Logging**: Comprehensive error tracking

## Performance Characteristics

### Latency
- **WebSocket**: <10ms for local commands
- **Terminal**: Depends on command complexity
- **AI Proxy**: 1-5 seconds for LLM responses

### Throughput
- **Concurrent Users**: Configurable session limits
- **Message Rate**: WebSocket message processing
- **Memory Usage**: ~50MB per active session

### Bottlenecks
- **Terminal I/O**: pexpect performance
- **AI API Calls**: External provider latency
- **WebSocket Scaling**: Single-threaded message processing

## Future Enhancements

### Planned Features
- **File Upload/Download**: Secure file transfer
- **Session Recording**: Command history and replay
- **Multi-terminal**: Multiple tabs per session
- **Plugin System**: Extensible command processing

### Architecture Improvements
- **Microservices**: Separate services for web, bot, AI
- **Database Integration**: Persistent session storage
- **Real-time Collaboration**: Multi-user sessions
- **Container Orchestration**: Kubernetes deployment</content>
<parameter name="filePath">/home/andrey/projects/telecli/docs/design.md