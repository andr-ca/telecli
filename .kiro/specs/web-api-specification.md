---
title: "Web API and WebSocket Specification"
description: "REST API endpoints and WebSocket protocol"
version: "1.0"
---

# Web API and WebSocket Specification

## REST API Endpoints

### Health Check
```http
GET /health
```
**Response**:
```json
{
  "status": "healthy",
  "sessions": {
    "active_sessions": 3,
    "max_sessions": 100,
    "total_created": 15
  }
}
```

### Statistics
```http
GET /stats
```
**Response**: Session statistics for monitoring

### Authentication Status
```http
GET /api/auth/required
```
**Response**: Client-side authentication requirement detection

### AI Proxy Configuration
```http
GET /api/ai-proxy/config
```
**Response**: Single source of truth for AI proxy configuration

### Session Reset
```http
POST /reset/{client_id}
```
**Response**: Force reset of specific client session

## WebSocket API

### Connection
```
ws://host:port/ws/{client_id}?token={auth_token}
```

#### Parameters
- `client_id`: Unique client identifier (UUID recommended)
- `token`: Authentication token (if `AUTH_REQUIRED=true`)

### Message Protocol

#### Client to Server Messages

##### Terminal Input
```json
{
  "input": "ls -la\n"
}
```
**Purpose**: Send user input to terminal

##### Terminal Resize
```json
{
  "resize": {
    "rows": 30,
    "cols": 120
  }
}
```
**Purpose**: Notify terminal of size changes

##### AI Proxy Control
```json
{
  "proxy": {
    "enable": true,
    "provider": "claude-cli",
    "system_prompt": "Custom system prompt..."
  }
}
```

#### Server to Client Messages

##### Terminal Output
```json
{
  "output": "\u001b[32muser@host\u001b[0m:\u001b[34m~\u001b[0m$ "
}
```
**Purpose**: Stream terminal output with ANSI escape sequences

##### AI Proxy Status
```json
{
  "proxy_status": {
    "enabled": true,
    "provider": "gemini-cli",
    "iterations": 3,
    "max_iterations": 50,
    "buffer_size": 150,
    "memory_items": 6,
    "has_summary": false
  }
}
```

##### Error Messages
```json
{
  "error": "Failed to enable AI proxy"
}
```

## Connection Management

### Authentication
- Optional token-based authentication via query parameter
- Token validation against `AUTH_TOKEN` configuration
- Unauthorized connections closed with code 1008

### Lifecycle
1. **Connection**: WebSocket accept and session creation
2. **Handlers**: Concurrent input/output/AI proxy handlers
3. **Monitoring**: Connection health and error handling
4. **Cleanup**: Session cleanup on disconnect

### Error Handling
- Graceful disconnect handling (codes 1000, 1001, 1012)
- Unexpected disconnect logging
- Automatic session cleanup and resource cleanup on errors

## Implementation Details

### Key Files
- `src/web_app.py` - FastAPI application and WebSocket handlers
- `src/ws_models.py` - Pydantic models for message validation
- `static/index.html` - Web UI with xterm.js integration
- `static/style.css` - Matrix-themed styling

### Dependencies
- FastAPI for REST API and WebSocket support
- xterm.js for terminal emulation in browser
- Session manager for terminal coordination
- AI proxy system for automation controls