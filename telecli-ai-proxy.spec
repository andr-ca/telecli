---
title: "AI Proxy System"
description: "Intelligent terminal automation with LLM providers"
version: "1.0"
---

# AI Proxy System Specification

## Overview
The AI Proxy system provides intelligent automation for terminal interactions by detecting prompts and generating appropriate responses using multiple LLM providers.

## Key Features

### Prompt Detection
- Pattern-based detection (?, :, numbered menus)
- Inactivity-based detection with configurable timeouts
- False positive filtering for loading messages

### LLM Integration
- Multi-provider support (Gemini, Claude, GitHub CLI)
- Automatic fallback on rate limits (429 errors)
- Comprehensive error handling and logging

### Memory Management
- Conversation history tracking
- Automatic summarization when memory exceeds limits
- Context preservation across interactions

### Smart Timing
- User input detection to pause automation
- Streaming detection to avoid interrupting output
- Cooldown periods between responses

## Configuration
- `AI_PROXY_PROVIDER`: Default LLM provider
- `AI_PROXY_MAX_ITERATIONS`: Maximum automation cycles
- `AI_PROXY_SYSTEM_PROMPT`: Default behavior instructions

## Implementation
- Location: `src/ai_proxy.py`
- Integration: `src/session_manager.py`
- UI Controls: `static/index.html`