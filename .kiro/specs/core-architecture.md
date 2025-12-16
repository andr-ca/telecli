---
title: "TeleCLI - Core Architecture"
description: "System architecture and core components overview"
version: "1.0"
---

# TeleCLI - Core Architecture Spec

## Overview
TeleCLI is a comprehensive terminal access system that provides both web and Telegram interfaces for interactive terminal sessions. It features advanced logging, AI-powered automation, security controls, and proper terminal emulation using pexpect.

## System Components

### 1. Configuration Management (`src/config.py`)
- Centralized configuration loading from `.env` files with validation
- Environment variable loading with type validation and bounds checking
- Support for SSL configuration with file existence checks
- Command filtering initialization and security controls

### 2. Advanced Logging System (`src/logger.py`)
- Multi-strategy logging with rotation and cleanup
- Three rotation modes: append, new_each_start, timestamp_rotate
- Top/bottom write positioning (configurable)
- Automatic directory cleanup based on size limits

### 3. Terminal Session Management (`src/terminal.py`)
- Pexpect-based terminal wrapper with bidirectional streaming
- Asynchronous terminal interaction with background output reading
- Terminal resize support and control character handling
- Command filtering integration and proper cleanup

### 4. Session Coordination (`src/session_manager.py`)
- Manages multiple terminal sessions with AI proxy integration
- Session creation and lifecycle management with limits
- AI proxy integration per session with provider selection
- Session statistics and monitoring

### 5. Web Interface (`src/web_app.py`)
- FastAPI-based web server with WebSocket terminal streaming
- Real-time bidirectional WebSocket communication
- xterm.js integration for full terminal emulation
- Authentication support and AI proxy control

### 6. Telegram Bot Integration (`src/telegram_bot.py`)
- Telegram bot interface for terminal access
- User whitelist support and command handling
- Message chunking for Telegram limits
- Webhook and polling mode support

### 7. AI Proxy System (`src/ai_proxy.py`)
- Intelligent terminal automation using LLM providers
- Prompt detection with pattern matching and inactivity detection
- Context building with aggressive output cleaning
- Memory management with conversation history and summarization

### 8. LLM Provider System (`src/llm_provider.py`, providers)
- Abstraction layer for multiple LLM providers
- Support for Gemini CLI, Claude CLI, and GitHub CLI
- Provider fallback on rate limits with unified response interface
- Comprehensive logging of all LLM interactions

## Data Flow

### Terminal Session Flow
1. Connection established (WebSocket/Telegram)
2. Terminal session spawned with pexpect
3. Background output capture in async loop
4. User input processed with command filtering
5. Terminal output streamed to client
6. Optional AI intervention based on prompt detection
7. Session cleanup on disconnect

### AI Proxy Flow
1. Terminal output buffered in rolling buffer
2. Prompt detection via patterns and inactivity
3. Context building with cleaned output
4. LLM query with fallback providers
5. Response processing and validation
6. Input injection to terminal as user input
7. Memory update with conversation history

## Security Model
- Optional token-based authentication for web interface
- Telegram user whitelist support
- Whitelist-based command restriction with file configuration
- SSL/TLS support for encrypted connections
- Process isolation with proper resource cleanup

## Deployment
- Python 3.8+ with asyncio support
- External CLI tools for LLM providers
- Environment-based configuration
- Configurable resource limits and SSL support