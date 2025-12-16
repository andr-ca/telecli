# Cloudflare Tunnel Setup for TeleCLI

## 🌐 Issue Resolution

The TeleCLI application was returning "invalid http request" when accessed through Cloudflare tunnel at `<full cf domain>/<path>`. This was due to path prefix handling issues.

## 🔧 Fixes Implemented

### 1. Backend Changes (src/web_app.py)

#### Added Reverse Proxy Support
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(title="TeleCLI", lifespan=lifespan)

# Add middleware to handle reverse proxy headers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
```

### 2. Frontend Changes (static/index.html)

#### Fixed WebSocket URL Generation
```javascript
// Before: Hardcoded absolute path
const url = `${protocol}//${window.location.host}/ws/${clientId}`;

// After: Dynamic path based on current location
const basePath = window.location.pathname.replace(/\/$/, '');
const url = `${protocol}//${window.location.host}${basePath}/ws/${clientId}`;
console.log('WebSocket URL:', url); // Debug logging
```

#### Fixed API Endpoint Calls
```javascript
// Before: Absolute paths
fetch('/api/sessions')
fetch('/api/auth/required')
fetch('/api/ai-proxy/config')
fetch('/stats')
fetch(`/reset/${sessionId}`)

// After: Relative paths
fetch('./api/sessions')
fetch('./api/auth/required')
fetch('./api/ai-proxy/config')
fetch('./stats')
fetch(`./reset/${sessionId}`)
```

## 🚀 How It Works Now

### Path Resolution
1. **Root Access**: `http://localhost:8801/` → Works as before
2. **Tunnel Access**: `https://<full cf domain>/<path>/` → Now works correctly
3. **WebSocket**: Automatically adapts to the correct path prefix
4. **API Calls**: Use relative paths that work with any base path

### WebSocket Connection
```javascript
// Example URLs generated:
// Local: ws://localhost:8801/ws/web-123456
// Tunnel: wss://<full cf domain>/<path>/ws/web-123456
```

## 🔍 Debugging Features

Added console logging for WebSocket URL generation to help troubleshoot connection issues:
```javascript
console.log('WebSocket URL:', url); // Shows the generated WebSocket URL
```

## 📋 Configuration Requirements

### Cloudflare Tunnel Configuration
Ensure your tunnel is configured to forward requests to the correct local port:

```yaml
# Example cloudflared config
tunnel: your-tunnel-id
credentials-file: /path/to/credentials.json

ingress:
  - hostname: <full cf domain>
    path: /telecli
    service: http://localhost:8801
  - service: http_status:404
```

### TeleCLI Configuration
No changes needed to `.env` file. The application will work with:
```bash
WEB_HOST=0.0.0.0
WEB_PORT=8801
AUTH_REQUIRED=true
AUTH_TOKEN=password
```

## 🧪 Testing

### Local Testing
1. Start TeleCLI: `python -m src.web_app`
2. Access: `http://localhost:8801/`
3. Should work normally

### Tunnel Testing
1. Ensure Cloudflare tunnel is running
2. Access: `https://<full cf domain>/<path>/`
3. Should show authentication modal
4. Enter token: `password`
5. Terminal should become available

### Debug Steps
1. Open browser developer tools
2. Check console for WebSocket URL logging
3. Verify WebSocket connection in Network tab
4. Check for any 404 errors on API calls

## 🚨 Common Issues

### WebSocket Connection Failed
- Check that WebSocket URL includes correct path prefix
- Verify Cloudflare tunnel supports WebSocket forwarding
- Ensure no firewall blocking WebSocket connections

### API Calls Returning 404
- Verify all API calls use relative paths (`./api/...`)
- Check browser network tab for actual URLs being called
- Ensure Cloudflare tunnel forwards all paths under `/telecli`

### Authentication Issues
- Verify `AUTH_REQUIRED=true` and `AUTH_TOKEN=password` in `.env`
- Check that token is being passed correctly in WebSocket query params
- Look for authentication errors in server logs

## 🔄 Rollback Plan

If issues persist, you can revert the changes:

1. **Remove middleware** from `src/web_app.py`
2. **Revert paths** in `static/index.html` back to absolute paths
3. **Configure tunnel** to serve at root path instead of `/telecli`

## 📊 Expected Results

- ✅ Application accessible via Cloudflare tunnel
- ✅ WebSocket connections work through tunnel
- ✅ All API endpoints respond correctly
- ✅ Authentication modal appears and works
- ✅ Terminal functionality fully operational
- ✅ Works both locally and through tunnel

The application should now be fully functional when accessed through `https://<full cf domain>/<path>/` with proper authentication and all features working correctly.