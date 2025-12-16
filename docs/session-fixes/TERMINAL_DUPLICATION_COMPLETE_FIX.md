# Terminal Duplication Complete Fix

## Summary
Fixed the terminal output duplication issue that was causing multiple connections per session and preventing cursor display.

## Root Cause Analysis
1. **Multiple WebSocket connections** - Up to 10 connections per session
2. **Authentication retry loops** - Failed auth attempts created new connections without closing old ones
3. **No connection limiting** - Backend allowed unlimited connections per session
4. **Missing initial prompt** - Terminal didn't send initial output to display cursor

## Complete Solution

### 1. Immediate Connection Closure (`src/session_manager.py`)
```python
# Store actual WebSocket objects
self.active_websockets: dict[str, list] = {}

# Close old connections immediately when new one arrives
if self.active_websockets[session_id]:
    for old_ws in self.active_websockets[session_id]:
        close_task = asyncio.create_task(old_ws.close(code=1000, reason="Superseded"))
```

**Benefits:**
- ✅ Prevents multiple connections
- ✅ Eliminates output duplication
- ✅ Immediate effect (no waiting for timeouts)

### 2. Connection Time Tracking (Backup Method)
```python
# Track connection timestamps for graceful detection
self.latest_connection_time: dict[str, datetime] = {}

# Periodic checks in WebSocket handlers
if session_manager.is_connection_outdated(client_id, connection_time):
    connection_active = False
```

**Benefits:**
- ✅ Graceful fallback if immediate closure fails
- ✅ Handles edge cases in connection timing

### 3. Initial Prompt Trigger (`src/terminal.py`)
```python
# Send carriage return to trigger initial prompt
self.process.send('\r')
```

**Benefits:**
- ✅ Ensures cursor/prompt appears immediately
- ✅ Fixes "cursor doesn't show up" issue

### 4. Enhanced Debugging (`src/ai_proxy.py`)
```python
# Detailed timeout logging
logger.info(f"Timeouts: user_idle={time_since_user_input:.1f}s, "
           f"terminal_idle={time_since_output:.1f}s")
```

**Benefits:**
- ✅ Helps diagnose AI proxy issues
- ✅ Shows why AI proxy isn't triggering

## Test Scripts

### Connection Test
```bash
python test_single_connection.py
```
Expected: Only 1 of 3 connections remains active

### Cursor Test  
```bash
python test_terminal_cursor.py
```
Expected: Terminal output with prompt/cursor appears

## Files Modified
- `src/session_manager.py` - Connection tracking and immediate closure
- `src/web_app.py` - WebSocket handler with connection management
- `src/terminal.py` - Initial prompt trigger
- `src/ai_proxy.py` - Enhanced debugging and timeout logging

## Monitoring
Check logs for these indicators:

**Success:**
```
✅ Scheduled close for old connection for session-id
Registered connection for session-id, total connections: 1
```

**Issues:**
```
🚨 MULTIPLE CONNECTIONS (N) for session-id - WILL CAUSE DUPLICATION!
```

## AI Proxy Debugging
The AI proxy requires specific conditions:
- User idle > 3.0s
- Terminal idle > 2.5s  
- Cooldown > 3.0s since last response
- No streaming output < 0.5s

Check logs for timeout details to diagnose why AI proxy isn't triggering.

## Impact
- ✅ Eliminates terminal output duplication
- ✅ Fixes cursor display on new sessions
- ✅ Improves session management reliability
- ✅ Better AI proxy debugging
- ✅ Reduces server resource usage
- ✅ Handles browser refresh gracefully