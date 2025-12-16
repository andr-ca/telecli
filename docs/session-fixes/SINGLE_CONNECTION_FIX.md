# Single Connection Per Session Fix

## Problem
Multiple WebSocket connections were being created for the same session, causing terminal output duplication. Logs showed up to 10 connections for a single session:

```
[WARNING] Multiple connections (10) detected for session web-329a50578b6172522830d6018820c408 - this may cause duplication!
```

## Root Cause
1. **Authentication failures** - Initial WebSocket connections failed auth (code 1008)
2. **Automatic retries** - Frontend retried connections after auth failures
3. **No connection cleanup** - Old failed connections weren't properly closed
4. **No connection limiting** - Backend allowed unlimited connections per session

## Solution
Implemented single connection enforcement with connection time tracking:

### Backend Changes (`src/session_manager.py`)
- Added `latest_connection_time` tracking per session
- Added `mark_latest_connection()` to timestamp new connections
- Added `is_connection_outdated()` to detect superseded connections
- Modified connection cleanup to remove tracking data

### WebSocket Handler Changes (`src/web_app.py`)
- Track connection timestamp for each WebSocket
- Mark latest connection time on new connections
- Add periodic checks in all handlers (input, output, AI proxy) to detect outdated connections
- Gracefully close outdated connections when newer ones arrive

### Connection Lifecycle
1. New WebSocket connects → gets timestamp
2. If multiple connections exist → newer connection supersedes older ones
3. Older connections detect they're outdated → close gracefully
4. Only the latest connection remains active

## Key Features
- **Graceful closure** - Old connections detect they're outdated and close themselves
- **No data loss** - Transition happens smoothly without interrupting terminal session
- **Automatic cleanup** - Connection tracking is cleaned up when sessions end
- **Backward compatible** - Works with existing frontend code

## Testing
Use `test_single_connection.py` to verify the fix:

```bash
python test_single_connection.py
```

Expected result: Only 1 connection remains active out of 3 created.

## Monitoring
The fix includes detailed logging:
- Connection registration/unregistration
- Outdated connection detection
- Connection time tracking
- Cleanup operations

## Files Modified
- `src/session_manager.py` - Connection tracking and management
- `src/web_app.py` - WebSocket handler with outdated connection checks
- `src/ai_proxy.py` - Added debugging for timeout conditions

## Impact
- ✅ Eliminates terminal output duplication
- ✅ Fixes cursor display issues
- ✅ Improves AI proxy reliability
- ✅ Reduces server resource usage
- ✅ Better session management on browser refresh