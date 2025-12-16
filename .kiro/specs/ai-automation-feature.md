# AI Terminal Automation Feature

## Feature Overview
Implement intelligent terminal automation that detects when commands are waiting for user input and automatically provides appropriate responses using LLM providers.

## User Stories

### Primary User Story
**As a developer**, I want the terminal to automatically respond to prompts so that I can run interactive commands without manual intervention.

**Acceptance Criteria:**
- [ ] System detects when terminal is waiting for input
- [ ] AI generates contextually appropriate responses
- [ ] Multiple LLM providers supported with fallback
- [ ] User can configure custom system prompts
- [ ] Automation can be enabled/disabled per session
- [ ] Iteration limits prevent infinite loops

### Secondary User Stories
- **As a user**, I want to customize the AI's behavior through system prompts
- **As an admin**, I want rate limit handling with automatic provider switching
- **As a developer**, I want comprehensive logging of AI interactions

## Technical Requirements

### Prompt Detection
```python
# Location: src/ai_proxy.py - _detect_prompt()
def _detect_prompt(self) -> bool:
    """Detect if terminal is waiting for user input"""
    # Pattern-based detection
    patterns = [
        r'\?\s*$',           # Questions ending with ?
        r':\s*$',            # Prompts ending with :
        r'\(y/n\)',          # Yes/no prompts
        r'^\s*\d+\.\s+\w+',  # Numbered menus
    ]
    
    # Inactivity detection
    if time_since_output > self.terminal_idle_timeout:
        return True
        
    return False
```

### Context Building
```python
# Location: src/ai_proxy.py - _build_context()
def _build_context(self) -> str:
    """Build clean context from terminal output"""
    # 1. Remove ANSI escape sequences
    # 2. Filter decorative elements
    # 3. Extract meaningful content
    # 4. Include conversation history
    return cleaned_context
```

### LLM Integration
```python
# Location: src/ai_proxy.py - _try_llm_with_fallback()
async def _try_llm_with_fallback(self, prompt: str) -> Optional[str]:
    """Try LLM providers with fallback on rate limits"""
    for provider_name, provider in providers_to_try:
        response = await provider.generate(prompt, self.system_prompt)
        if response.is_success:
            return response.text
        if response.error_code == 429:  # Rate limit
            continue  # Try next provider
    return None
```

## Implementation Plan

### Phase 1: Core Detection ✅
- [x] Implement prompt detection patterns
- [x] Add inactivity-based detection
- [x] Create false positive filtering
- [x] Test with common interactive commands

### Phase 2: LLM Integration ✅
- [x] Create provider abstraction layer
- [x] Implement Gemini CLI provider
- [x] Implement Claude CLI provider
- [x] Implement GitHub CLI provider
- [x] Add fallback mechanism for rate limits

### Phase 3: Memory System ✅
- [x] Track conversation history
- [x] Implement automatic summarization
- [x] Preserve context across interactions
- [x] Memory cleanup and optimization

### Phase 4: Web UI Controls ✅
- [x] AI proxy toggle button
- [x] Configuration modal with custom prompts
- [x] Real-time status display
- [x] Provider selection interface

### Phase 5: Advanced Features ✅
- [x] Smart timing controls (user input detection)
- [x] Streaming detection to avoid interruption
- [x] Stuck detection and retry logic
- [x] Comprehensive error handling

## Configuration Options

### Environment Variables
```bash
AI_PROXY_ENABLED=false
AI_PROXY_PROVIDER=gemini-cli
AI_PROXY_SYSTEM_PROMPT="You are helping automate terminal interactions..."
AI_PROXY_MAX_ITERATIONS=50
```

### Runtime Configuration
```javascript
// Web UI configuration
{
  "proxy": {
    "enable": true,
    "provider": "claude-cli",
    "system_prompt": "Custom behavior instructions..."
  }
}
```

## Testing Strategy

### Unit Tests
```python
# Test prompt detection
def test_prompt_detection():
    assert ai_proxy._detect_prompt_in_text("Enter password:")
    assert ai_proxy._detect_prompt_in_text("Continue? (y/n)")
    assert not ai_proxy._detect_prompt_in_text("Loading...")

# Test provider fallback
async def test_provider_fallback():
    # Mock rate limit from primary provider
    # Verify fallback to secondary provider
    pass
```

### Integration Tests
```python
# Test end-to-end automation
async def test_ai_automation_flow():
    # 1. Send command that requires input
    # 2. Verify prompt detection
    # 3. Verify AI response generation
    # 4. Verify response injection
    # 5. Verify command completion
    pass
```

## Performance Considerations

### Memory Management
- Rolling buffer with configurable size (default: 1000 lines)
- Automatic conversation summarization
- Context window optimization (500 lines to LLM)

### Timing Optimization
- User input detection: 3.0s timeout
- Terminal idle detection: 2.5s timeout
- Response cooldown: 3.0s minimum
- Stuck detection: 60s retry timeout

### Rate Limit Handling
- Automatic provider switching on 429 errors
- Exponential backoff for retries
- Provider availability caching

## Monitoring and Observability

### Metrics
- AI proxy iterations per session
- Provider success/failure rates
- Average response time per provider
- Memory usage and cleanup frequency

### Logging
```
[TIMESTAMP] REQUEST to Gemini CLI
----------------------------------------
System Prompt: You are helping automate...
User Prompt: Terminal context...
----------------------------------------
RESPONSE from Gemini CLI:
Status: SUCCESS
Response: y
========================================
```

### Status Tracking
```json
{
  "enabled": true,
  "provider": "gemini-cli",
  "iterations": 3,
  "max_iterations": 50,
  "buffer_size": 150,
  "memory_items": 6,
  "has_summary": false
}
```

## Error Handling

### Provider Errors
- Rate limits (429): Switch to fallback provider
- Timeouts (504): Log and continue with next iteration
- Unavailable (503): Skip provider in fallback chain

### Detection Errors
- False positives: Comprehensive filtering patterns
- Missed prompts: Inactivity-based backup detection
- Context issues: Aggressive output cleaning

### Memory Errors
- Buffer overflow: Rolling buffer with size limits
- Summarization failures: Graceful degradation
- Context corruption: Reset and rebuild

## Future Enhancements

### Planned Features
- [ ] Custom detection patterns per session
- [ ] Response caching for common prompts
- [ ] Multi-language prompt detection
- [ ] Streaming response support
- [ ] Provider-specific tuning parameters

### Performance Improvements
- [ ] Async context building
- [ ] Parallel provider queries
- [ ] Response quality scoring
- [ ] Adaptive timeout adjustment