---
title: "TeleCLI Architecture"
description: "Core system architecture and components"
version: "1.0"
type: "specification"
---

# TeleCLI Architecture Specification

## Overview
TeleCLI is a comprehensive terminal access system providing web and Telegram interfaces for interactive terminal sessions with AI automation.

## Core Components

### 1. Configuration Management (`src/config.py`)
- Environment-based configuration with validation
- SSL support and security controls
- Command filtering initialization

### 2. Terminal Sessions (`src/terminal.py`)
- Pexpect-based terminal emulation
- Bidirectional streaming with async queues
- Command filtering and control character support

### 3. AI Proxy (`src/ai_proxy.py`)
- Intelligent prompt detection
- Multi-provider LLM integration with fallback
- Memory management and conversation history

### 4. Web Interface (`src/web_app.py`)
- FastAPI with WebSocket streaming
- xterm.js terminal emulation
- Real-time AI proxy controls

### 5. Telegram Bot (`src/telegram_bot.py`)
- User authorization and session management
- Command execution with output chunking
- Webhook and polling support

## Security Model
- Token-based authentication for web
- User whitelist for Telegram
- Command filtering with whitelist
- SSL/TLS encryption support

## Implementation Status
✅ All core components implemented and tested
✅ Multi-provider LLM system with fallback
✅ Comprehensive logging and monitoring
✅ Security controls and configuration management