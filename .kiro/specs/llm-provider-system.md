---
title: "Multi-Provider LLM System"
description: "LLM provider abstraction with fallback support"
version: "1.0"
---

# Multi-Provider LLM System Spec

## Overview
Abstraction layer supporting multiple LLM providers with unified interface, fallback capabilities, and comprehensive logging.

## Provider Architecture

### Base Provider Interface
**Location**: `src/llm_provider.py`

#### Core Methods
- `generate(prompt, system_prompt)`: Generate LLM response
- `is_available()`: Check provider availability  
- `get_name()`: Return provider identifier

#### Response Object
```python
class LLMResponse:
    text: Optional[str]           # Generated text
    error_code: Optional[int]     # HTTP-like error codes
    error_message: Optional[str]  # Error description
    is_success: bool             # Success indicator
```

### Provider Factory
**Location**: `src/llm_provider.py` - `LLMProviderFactory`

#### Features
- Provider registration system
- Dynamic provider creation with availability filtering
- Default provider selection
- Runtime provider switching

## Supported Providers

### Gemini CLI Provider
**Location**: `src/gemini_provider.py`

#### Implementation
- Uses `gemini` CLI tool
- Command: `gemini --output-format text <prompt>`
- Timeout: 15 minutes
- Rate limit detection via error message parsing

### Claude CLI Provider  
**Location**: `src/claude_provider.py`

#### Implementation
- Uses `claude` CLI tool
- Command: `claude <prompt>`
- System prompt integration
- Comprehensive error handling

### GitHub CLI Provider
**Location**: `src/github_provider.py`

#### Implementation
- Uses `gh copilot suggest` command
- Command: `gh copilot suggest --output text <prompt>`
- GitHub Copilot integration
- Enterprise-friendly option

## Error Handling and Fallback

### Error Codes
- `429`: Rate limit exceeded
- `500`: General provider error
- `503`: Provider unavailable
- `504`: Provider timeout

### Fallback Strategy
1. Try primary provider
2. On 429 error, try next available provider
3. Switch active provider if fallback succeeds
4. Log provider switches and failures
5. Return error if all providers fail

## Logging and Monitoring

### LLM Interaction Logging
**Location**: `src/llm_providers.py` - Dedicated logger

#### Log Format
```
[TIMESTAMP] REQUEST to <Provider> at <ISO-timestamp>
----------------------------------------
System Prompt: <system_prompt>
----------------------------------------
User Prompt: <user_prompt>
----------------------------------------
RESPONSE from <Provider>:
----------------------------------------
Status: SUCCESS/ERROR (Code <code>)
Response Length: <chars> characters
----------------------------------------
<response_text>
========================================
```

#### Features
- Separate log file: `logs/llm_interactions.log`
- Request/response correlation
- Error code tracking and performance metrics
- Provider switching notifications

## Configuration

### Provider Selection
- Default provider via `AI_PROXY_PROVIDER` environment variable
- Runtime provider switching on rate limits
- Availability checking on startup

### System Integration
- Factory pattern for clean provider instantiation
- Unified error handling across all providers
- Automatic fallback without user intervention

## Implementation Files
- `src/llm_provider.py` - Base interface and factory
- `src/llm_providers.py` - Provider registration and logging
- `src/gemini_provider.py` - Gemini CLI implementation
- `src/claude_provider.py` - Claude CLI implementation  
- `src/github_provider.py` - GitHub CLI implementation