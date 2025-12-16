---
title: "Telegram Bot Integration"
description: "Telegram interface with user authorization"
version: "1.0"
---

# Telegram Bot Integration Spec

## Overview
Telegram bot interface providing terminal access through chat with user authorization and session management.

## Bot Commands

### Start Command
```
/start
```
**Response**:
```
Welcome to TeleCLI! Your session ID is 123456789.
Send any command and I'll execute it for you.

Commands:
/help - Show this help message
/reset - Reset your terminal session
```

### Help Command
```
/help
```
**Response**: Command reference and usage instructions

### Reset Command
```
/reset
```
**Response**: Force reset user's terminal session

## Message Handling

### Command Execution
**Input**: Any text message (non-command)

#### Processing Flow
1. User authorization check against whitelist
2. Typing indicator display
3. Command execution in user's isolated session
4. Output capture and formatting
5. Response chunking for Telegram limits (4000 chars)

#### Response Format
```
```
<command_output>
```
```

### Message Chunking
- Telegram limit: 4096 characters
- TeleCLI safety limit: 4000 characters
- Automatic chunking for long outputs
- Markdown code block formatting

## User Authorization

### Whitelist System
**Configuration**: `ALLOWED_TELEGRAM_USERS` (comma-separated user IDs)

#### Behavior
- Empty list: Allow all users
- Populated list: Only allow listed user IDs
- Unauthorized users receive "❌ You are not authorized" message

### Session Management
- User ID as unique session identifier
- Isolated sessions per user
- Session persistence across bot restarts
- Automatic cleanup on inactivity

## Deployment Modes

### Polling Mode (Default)
**Configuration**: `TELEGRAM_WEBHOOK_URL` not set

#### Characteristics
- Bot polls Telegram servers for updates
- Suitable for development and small deployments
- No external network requirements
- Higher latency but simpler setup

### Webhook Mode
**Configuration**: `TELEGRAM_WEBHOOK_URL` set

#### Characteristics
- Telegram sends updates to webhook URL
- Suitable for production deployments
- Requires public HTTPS endpoint
- Webhook path: `/{TELEGRAM_BOT_TOKEN}`
- Lower latency, more efficient

## Error Handling

### Command Execution Errors
```
❌ Error: <error_message>
```

### Authorization Errors
```
❌ You are not authorized to use this bot
```

### Session Management Errors
- Session creation failures
- Command filtering violations
- Resource limit exceeded

## Implementation Details

### Key Files
- `src/telegram_bot.py` - Main bot implementation
- `src/session_manager.py` - Session coordination
- `src/config.py` - Bot token and webhook configuration

### Dependencies
- `python-telegram-bot` library for Telegram API
- Session manager for terminal coordination
- Command filter for security
- Configuration system for bot settings

### Integration Points
- Session manager for terminal access
- Command filter for security validation
- Configuration system for bot settings
- Logging system for bot activity tracking