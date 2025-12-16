# WebSocket Authentication Fix for Cloudflare Tunnel

## 🎯 Issue Identified

WebSocket authentication was failing through the Cloudflare tunnel with error:
```
[2025-12-15 22:29:22] [WARNING] [src.web_app] WebSocket auth failed for web-b7f435c30feb4ede78f35c4be8e4ebee: invalid or missing token
INFO: 172.97.208.209:0 - "WebSocket /telecli/ws/web-b7f435c30feb4ede78f35c4be8e4ebee" 403
```

## 🔍 Root Cause Analysis

The issue was in the frontend JavaScript where API calls were using relative paths that didn't account for the `/telecli` base path when accessed through the Cloudflare tunnel.

### Problem Areas

1. **Authentication Check**: `./api/auth/required` → Should be `/telecli/api/auth/required`
2. **Session Management**: `./api/sessions` → Should be `/telecli/api/sessions`
3. **Reset Endpoints**: `./reset/{id}` → Should be `/telecli/reset/{id}`
4. **AI Proxy Config**: `./api/ai-proxy/config` → Should be `/telecli/api/ai-proxy/config`
5. **Stats Endpoint**: `./stats` → Should be `/telecli/stats`

### URL Construction Logic

**Before (Broken)**:
```javascript
// This worked locally but failed through tunnel
const response = await fetch('./api/auth/required');
```

**After (Fixed)**:
```javascript
// This works both locally and through tunnel
const basePath = window.location.pathname.replace(/\/$/, '');
const response = await fetch(`${basePath}/api/auth/required`);
```

## 🔧 Solution Implemented

### 1. Fixed WebSocket URL Generation
```javascript
async function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const basePath = window.location.pathname.replace(/\/$/, '');
    const url = `${protocol}//${window.location.host}${basePath}/ws/${clientId}`;
    
    // Fixed: Use basePath for auth API call
    const authApiUrl = `${basePath}/api/auth/required`;
    const response = await fetch(authApiUrl);
    // ... rest of auth logic
}
```

### 2. Fixed All API Calls

Updated all fetch calls to use dynamic base path:

```javascript
// Session management
const basePath = window.location.pathname.replace(/\/$/, '');
const response = await fetch(`${basePath}/api/sessions`);

// Reset session
await fetch(`${basePath}/reset/${sessionId}`, { method: 'POST' });

// AI proxy config
const response = await fetch(`${basePath}/api/ai-proxy/config`);

// Stats
fetch(`${basePath}/stats`)

// Auth check
fetch(`${basePath}/api/auth/required`)
```

## 🧪 Testing Strategy

### 1. Local Testing
```bash
# Start the server locally
python src/main.py

# Test WebSocket connection
python test_websocket_auth.py
```

### 2. Tunnel Testing
```bash
# Test through Cloudflare tunnel
curl -v https://code.andr.ca/telecli/api/auth/required
# Should return: {"auth_required": true}

# Test WebSocket in browser console
const ws = new WebSocket('wss://code.andr.ca/telecli/ws/test-123?token=13241324');
ws.onopen = () => console.log('Connected!');
ws.onerror = (e) => console.error('Error:', e);
```

## 📊 Expected Behavior

### Local Access (localhost:8801)
- `basePath = ""` (empty)
- API calls: `/api/auth/required`, `/api/sessions`, etc.
- WebSocket: `ws://localhost:8801/ws/{clientId}?token=13241324`

### Tunnel Access (code.andr.ca/telecli)
- `basePath = "/telecli"`
- API calls: `/telecli/api/auth/required`, `/telecli/api/sessions`, etc.
- WebSocket: `wss://code.andr.ca/telecli/ws/{clientId}?token=13241324`

## 🔄 Authentication Flow

1. **Page Load**: Check `window.location.pathname` to determine base path
2. **Auth Check**: Fetch `{basePath}/api/auth/required`
3. **Token Retrieval**: Get token from localStorage or show modal
4. **WebSocket Connect**: Connect to `{basePath}/ws/{clientId}?token={token}`
5. **Server Validation**: Server validates token and accepts/rejects connection

## 🎯 Files Modified

- `static/index.html`: Fixed all API calls to use dynamic base path
- `test_websocket_auth.py`: Created test script for validation

## 🚀 Next Steps

1. **Test the fix** through the Cloudflare tunnel
2. **Verify authentication** works with token `13241324`
3. **Test all functionality** (sessions, AI proxy, reset, etc.)
4. **Monitor logs** for any remaining authentication issues
5. **Clean up test files** once confirmed working

The WebSocket authentication should now work correctly through both local access and the Cloudflare tunnel.
</content>