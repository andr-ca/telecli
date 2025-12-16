---
title: "AI Proxy Automation System"
description: "Intelligent terminal automation with LLM providers"
version: "1.0"
---

# AI Proxy Automation System Spec

## Overview
The AI Proxy system provides intelligent automation for terminal interactions by detecting prompts and generating appropriate responses using LLM providers with fallback support.

## Core Components

### Prompt Detection Engine
**Location**: `src/ai_proxy.py` - `_detect_prompt()`

#### Detection Methods
1. **Pattern-Based Detection**:
   - Question marks: `?\s*$`
   - Colons: `:\s*$` (for prompts like "Enter name:")
   - Numbered menus: `^\s*❯\s*\d+\.` or `^\s*\d+\.\s+\w+`
   - Yes/No prompts: `\(y/n\)`, `\[y/N\]`

2. **Inactivity Detection**:
   - Terminal idle timeout: 2.5 seconds (configurable)
   - Streaming detection window: 0.5 seconds
   - Stuck detection: 60 seconds after last AI response

3. **False Positive Filtering**:
   - Box drawing characters and loading spinners
   - Decorative elements and progress indicators

### Context Building System
**Location**: `src/ai_proxy.py` - `_build_context()`

#### Processing Pipeline
1. **ANSI Cleaning**: Remove color codes and formatting
2. **Control Character Removal**: Strip non-printable characters
3. **Decorative Filtering**: Remove box drawing and spinner lines
4. **Context Windowing**: Last 500 lines (configurable)
5. **Memory Integration**: Include conversation history and summary

### Memory Management
**Features**:
- **Conversation History**: Track prompt/response pairs
- **Automatic Summarization**: Compress older interactions when memory exceeds 12 items
- **Context Preservation**: Maintain recent interactions for continuity
- **Memory Summary**: Compressed representation of older conversations

### Provider Fallback System
**Location**: `src/ai_proxy.py` - `_try_llm_with_fallback()`

#### Fallback Strategy
1. Try primary provider (configured in settings)
2. On 429 (rate limit) error, try next available provider
3. Switch active provider if fallback succeeds
4. Log provider switches and failures
5. Return None if all providers fail

## Configuration

### Timing Controls
- `user_idle_timeout`: 3.0 seconds (user typing detection)
- `terminal_idle_timeout`: 2.5 seconds (terminal output detection)
- `response_cooldown`: 3.0 seconds (minimum time between AI responses)
- `stuck_check_timeout`: 60.0 seconds (retry if no changes after response)

### System Prompts
- **Default**: Keyboard simulation with strict response rules
- **Custom**: User-configurable through web UI
- **Context Integration**: Automatic context prepending

### Iteration Limits
- `max_iterations`: 50 (configurable, prevents infinite loops)
- Automatic disable when limit reached
- Reset capability through UI

## Integration Points

### Web Interface Integration
- Modal-based configuration UI with real-time status display
- Provider selection and custom prompt input
- Reset functionality for iteration counter

### Session Manager Integration
- Per-session AI proxy instances
- Input callback setup for terminal automation
- Provider configuration and fallback setup

## Implementation Details

### Key Files
- `src/ai_proxy.py` - Main AI proxy implementation
- `src/session_manager.py` - AI proxy integration
- `src/web_app.py` - Web UI controls
- `static/index.html` - AI proxy configuration modal

### Dependencies
- LLM provider system for multiple backend support
- Terminal session management for input/output
- WebSocket communication for real-time control