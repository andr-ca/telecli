# Browser Refresh Fix - Session Reconnection

## Problem
When the browser is refreshed, the terminal stops working and doesn't show the carriage symbol (prompt). This happens because:

1. **Session Persistence**: The browser tries to reconnect to the same session ID (stored in localStorage)
2. **Stale Connection**: The old WebSocket connection is closed, but the terminal session remains active on the server
3. **No Output**: The terminal is sitting at a shell prompt with no new output to send to the new WebSocket connection
4. **Missing Prompt**: The client doesn't see the current terminal state (prompt) because the output stream only sends new data

## Root Cause
The WebSocket output stream only forwards new terminal output. When reconnecting to an existing session, there's no mechanism to show the current terminal state (like the shell prompt) to the new connection.

## Solution Implemented

### 1. Session State Detection
Added logic to detect if the WebSocket is connecting to an existing session:
```python
session_existed = client_id in session_manager.sessions
```

### 2. Non-Intrusive Prompt Refresh
For existing sessions, send a subtle command to refresh the display:
```python
if session_existed:
    # Send space + backspace to refresh prompt without changing anything
    await session.send_input(" \b", newline=False)
```

### 3. Timing Coordination
Added a small delay to ensure the WebSocket connection is fully established before sending the refresh:
```python
await asyncio.sleep(0.1)  # Small delay to ensure connection is ready
```

## How It Works

1. **New Sessions**: No refresh needed - the shell will naturally output its initial prompt
2. **Existing Sessions**: 
   - Detect that the session already exists
   - Send a space character followed by a backspace
   - This causes the shell to redraw the current line (showing the prompt)
   - The output is captured and sent to the new WebSocket connection
   - The user sees the current terminal state immediately

## Benefits

✅ **Seamless Reconnection**: Browser refresh now properly shows the terminal state
✅ **Non-Intrusive**: The refresh command doesn't change the terminal state or history
✅ **Immediate Feedback**: Users see the prompt right away after refresh
✅ **Backward Compatible**: New sessions work exactly as before

## Technical Details

- **Command Used**: `" \b"` (space + backspace)
- **Why This Works**: Most shells will echo the space and then remove it with backspace, causing a redraw of the current line
- **Timing**: 100ms delay ensures WebSocket is ready to receive output
- **Logging**: Debug logs track when refresh is sent vs. new sessions

This fix ensures that browser refresh maintains a smooth user experience while preserving all existing functionality.