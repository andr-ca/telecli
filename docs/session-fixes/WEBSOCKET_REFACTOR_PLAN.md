# WebSocket Connection Refactor Plan

## Current Problems

1. **Too many connection tracking mechanisms**:
   - `active_connections` (count)
   - `active_websockets` (list of WebSocket objects)
   - `latest_connection_time` (datetime)
   - `disconnected_sessions` (datetime)
   - `cleanup_tasks` (asyncio tasks)

2. **Frontend reconnection chaos**:
   - `staleStateCheckInterval` - monitors connection health
   - `forceReconnection()` - forces reconnection
   - `ws.onclose` handler - auto-reconnects
   - Multiple places calling `connectWebSocket()`

3. **Race conditions**:
   - Backend closes old connections while handlers are running
   - Frontend creates new connections before old ones are fully closed

## Simplified Design

### Principle
- **One WebSocket per browser tab**
- **One terminal session per session ID**
- **Simple state: connected or not connected**

### Frontend Changes

```javascript
// Simple state
let ws = null;
let isConnected = false;

// Connect once, reconnect only on actual disconnection
async function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('Already connected');
        return;
    }
    
    // Close any existing connection cleanly
    if (ws) {
        ws.onclose = null; // Prevent reconnection loop
        ws.close();
        ws = null;
    }
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        isConnected = true;
        // Send terminal size once
        sendTerminalSize();
    };
    
    ws.onclose = (event) => {
        isConnected = false;
        // Only reconnect if not intentional close
        if (event.code !== 1000) {
            setTimeout(connectWebSocket, 3000);
        }
    };
}
```

### Backend Changes

```python
# Simple session manager
class SessionManager:
    def __init__(self):
        self.sessions: dict[str, TerminalSession] = {}
        self.session_info: dict[str, SessionInfo] = {}
    
    # No connection tracking needed - WebSocket handles its own lifecycle
    # No cleanup tasks - sessions persist until explicitly closed
```

### WebSocket Handler

```python
async def websocket_handler(websocket, client_id):
    await websocket.accept()
    
    # Get or create session
    session = await session_manager.get_session(client_id)
    
    # Simple input/output handlers
    async def handle_input():
        async for message in websocket.iter_text():
            data = json.loads(message)
            if "input" in data:
                await session.send_input(data["input"])
    
    async def handle_output():
        async for chunk in session.get_output_stream():
            await websocket.send_json({"output": chunk})
    
    await asyncio.gather(handle_input(), handle_output())
```

## Implementation Steps

1. **Remove complex connection tracking** from SessionManager
2. **Simplify frontend** to single connection logic
3. **Remove stale state monitoring** - trust WebSocket state
4. **Remove reconnection loops** - let onclose handle it simply
5. **Test with single browser tab** first
