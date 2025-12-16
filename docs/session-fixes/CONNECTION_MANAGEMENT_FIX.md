# Connection Management and Cursor Display Fix

## Problem
Multiple WebSocket connections to the same session were causing:
1. **Terminal output duplication** - each connection received the same output
2. **Missing cursor on reconnection** - terminals appeared "dead" when reconnecting to existing sessions
3. **Inconsistent terminal state** - some connections showed cursor, others didn't

## Root Cause Analysis
From logs analysis:
```
[ERROR] 🚨 MULTIPLE CONNECTIONS (2-3) for session web-xxx - WILL CAUSE DUPLICATION!
[INFO] Reconnecting to existing session web-xxx
```

The issues were:
1. **Race condition in connection management** - old connections weren't closed before new ones were registered
2. **Insufficient connection cleanup** - connections were only closed when >= 2 existed, allowing duplication
3. **Stale terminal state** - reconnected sessions didn't refresh the terminal prompt

## Solution

### 1. Improved Connection Management
**File: `src/session_manager.py`**

- Made `register_connection()` async to properly wait for old connections to close
- Changed threshold from `>= 2` to `>= 1` - close ANY existing connection immediately
- Added timeout for connection closure to prevent hanging
- Proper cleanup of WebSocket tracking lists

```python
async def register_connection(self, session_id: str, websocket=None) -> int:
    # Close old connections immediately when ANY exist
    if len(self.active_websockets[session_id]) >= 1:
        # Close all existing connections and wait for completion
        close_tasks = []
        for old_ws in self.active_websockets[session_id]:
            task = asyncio.create_task(old_ws.close(code=1000, reason="Superseded"))
            close_tasks.append(task)
        
        # Wait for all close operations (with timeout)
        await asyncio.wait_for(asyncio.gather(*close_tasks, return_exceptions=True), timeout=1.0)
```

### 2. Terminal Cursor Refresh
**Files: `src/terminal.py`, `src/session_manager.py`, `src/web_app.py`**

Added dedicated prompt refresh functionality to ensure cursor visibility on reconnection:

```python
# In TerminalSession
async def refresh_prompt(self) -> None:
    """Refresh the terminal prompt to ensure cursor is visible"""
    self.process.send('\x15')  # Ctrl+U (clear line)
    await asyncio.sleep(0.05)  # Brief delay
    self.process.send('\r')    # Enter to show fresh prompt

# In SessionManager
async def refresh_session_prompt(self, session_id: str) -> None:
    """Refresh the terminal prompt for a session"""
    await self.sessions[session_id].refresh_prompt()

# In WebSocket handler
if session_existed:
    await session_manager.refresh_session_prompt(client_id)
```

### 3. Synchronous Connection Registration
**File: `src/web_app.py`**

Updated WebSocket handler to await connection registration:

```python
# Register this connection and automatically close old ones
connection_count = await session_manager.register_connection(client_id, websocket)
```

## Expected Results

1. **No more duplication** - only one active connection per session
2. **Consistent cursor display** - cursor appears on both new and reconnected sessions
3. **Faster connection handoff** - old connections close immediately
4. **Better user experience** - terminals feel responsive and consistent

## Testing

Use the test scripts to verify:

**Connection Management:**
```bash
python test_connection_management.py
```

**Cursor Display:**
```bash
python test_cursor_display.py
```
```bash
python test_connection_management.py
```

Check server logs for:
- `🔧 CLOSING X old connections` messages
- `✅ All old connections closed` confirmations
- No more `🚨 MULTIPLE CONNECTIONS` errors
- `Refreshed terminal prompt for session` on reconnections

## Monitoring

Watch for these log patterns:
- **Good**: `Registered connection for session-id, total connections: 1`
- **Bad**: `🚨 MULTIPLE CONNECTIONS (2+) for session-id - WILL CAUSE DUPLICATION!`

The fix ensures only one active connection per session at any time.