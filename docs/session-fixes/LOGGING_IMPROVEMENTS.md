# LLM Logging Improvements

## Summary
Enhanced LLM interaction logging to show error codes, response status, and response lengths. This enables better debugging and monitoring of LLM provider behavior.

## Changes Made

### Modified Files
1. **src/gemini_provider.py** - Enhanced logging for success and error responses
2. **src/claude_provider.py** - Enhanced logging for success and error responses
3. **src/github_provider.py** - Enhanced logging for success and error responses

### Key Improvements

#### 1. Success Response Logging
- Added `Status: SUCCESS` indicator
- Added response length tracking
- Better visual separation of request/response

**Example:**
```
[2025-12-14 00:31:31] [INFO] [llm_interactions] RESPONSE from Claude CLI:
[2025-12-14 00:31:31] [INFO] [llm_interactions] ------------------------------------------
[2025-12-14 00:31:31] [INFO] [llm_interactions] Status: SUCCESS
[2025-12-14 00:31:31] [INFO] [llm_interactions] Response Length: 5 characters
[2025-12-14 00:31:31] [INFO] [llm_interactions] ------------------------------------------
[2025-12-14 00:31:31] [INFO] [llm_interactions] Hello
```

#### 2. Error Response Logging
- Shows HTTP-like error codes (429, 500, 504, etc.)
- Includes full error message for diagnostics
- Consistent format for all error types

**Example - Rate Limit (429):**
```
[2025-12-14 00:31:13] [INFO] [llm_interactions] RESPONSE from Gemini CLI:
[2025-12-14 00:31:13] [INFO] [llm_interactions] ------------------------------------------
[2025-12-14 00:31:13] [INFO] [llm_interactions] Status: ERROR (Code 429)
[2025-12-14 00:31:13] [INFO] [llm_interactions] Error Message: Quota exceeded for quota metric 'Chat API requests'
```

**Example - Timeout (504):**
```
[2025-12-14 00:31:13] [INFO] [llm_interactions] Status: ERROR (Code 504)
[2025-12-14 00:31:13] [INFO] [llm_interactions] Error Message: Claude CLI timeout after 900s
```

**Example - General Error (500):**
```
[2025-12-14 00:31:13] [INFO] [llm_interactions] Status: ERROR (Code 500)
[2025-12-14 00:31:13] [INFO] [llm_interactions] Error Message: [error details]
```

#### 3. Error Code Detection
Automatic error code assignment:
- **429**: Rate limit / Quota exceeded
- **500**: General server error
- **503**: Service unavailable
- **504**: Gateway timeout / CLI timeout

### Implementation Details

All three providers (`GeminiCLIProvider`, `ClaudeCLIProvider`, `GitHubCLIProvider`) now:

1. **On Success:**
   - Log status as "SUCCESS"
   - Include response length in characters
   - Display actual response content

2. **On Error:**
   - Log status as "ERROR (Code XXX)"
   - Parse error messages to detect rate limits
   - Include full error message text
   - Maintain consistent format across providers

3. **On Timeout:**
   - Log as "ERROR (Code 504)" 
   - Include timeout duration (900s)

4. **On Exception:**
   - Log as "ERROR (Code 500)"
   - Include exception message for debugging

## Testing

### Quick Tests
All 12 quick infrastructure tests pass:
```bash
$ pytest tests/test_real_cli_quick.py::TestCLIAvailability \
  tests/test_real_cli_quick.py::TestProviderInitialization \
  tests/test_real_cli_quick.py::TestProviderFactory \
  tests/test_real_cli_quick.py::TestAIProxyConfiguration -q
# ✅ 12 passed in 0.06s
```

### Real CLI Integration Test
Verified with actual Claude CLI:
```
✓ SUCCESS response with "Hello" (5 characters)
✓ Status indicator shown clearly
✓ Response length tracked
✓ Log format consistent
```

## Benefits

1. **Better Debugging** - Error codes and full messages aid troubleshooting
2. **Monitoring** - Easy to track success vs error rates
3. **Quota Management** - Rate limit (429) errors clearly identified
4. **Performance Tracking** - Response length indicates response volume
5. **Consistency** - Uniform format across all providers and error types

## Log Format Reference

### Request Section
```
================================================================================
REQUEST to [Provider] CLI at [ISO timestamp]
--------------------------------------------------------------------------------
User Prompt:
[User input text]
--------------------------------------------------------------------------------
```

### Success Response Section
```
RESPONSE from [Provider] CLI:
--------------------------------------------------------------------------------
Status: SUCCESS
Response Length: [N] characters
--------------------------------------------------------------------------------
[Response text]
================================================================================
```

### Error Response Section
```
RESPONSE from [Provider] CLI:
--------------------------------------------------------------------------------
Status: ERROR (Code [XXX])
Error Message: [Error text]
================================================================================
```

## Notes

- All changes are backward compatible
- No changes to provider interfaces or behavior
- Logging only affects output format, not functionality
- Error detection logic unchanged (rate limit detection preserved)
