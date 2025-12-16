# Cloudflare Tunnel Troubleshooting

## 🚨 Issue: "Invalid HTTP request received"

This error indicates that the server is receiving malformed HTTP requests, likely due to how Cloudflare tunnel is forwarding requests.

## 🔧 Fixes Applied

### 1. Enhanced Server Configuration

#### Updated main.py (Recommended Entry Point)
```python
config = uvicorn.Config(
    web_app,
    host=Config.WEB_HOST,
    port=Config.WEB_PORT,
    log_level="info",
    access_log=True,
    server_header=False,
    date_header=False,
    forwarded_allow_ips="*",  # Allow forwarded headers from any IP
    proxy_headers=True,       # Trust proxy headers
)
```

#### Updated web_app.py (Direct Run)
```python
uvicorn.run(
    app, 
    host=Config.WEB_HOST, 
    port=Config.WEB_PORT,
    access_log=True,
    server_header=False,
    date_header=False,
    forwarded_allow_ips="*",
    proxy_headers=True,
)
```

### 2. Added Request Logging Middleware
```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            logger.debug(f"Incoming request: {request.method} {request.url}")
            logger.debug(f"Headers: {dict(request.headers)}")
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            raise
```

### 3. Added Debug Endpoint
```python
@app.get("/debug")
async def debug_info(request: Request):
    return {
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers),
        "path": request.url.path,
        "host": request.headers.get("host"),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "x_forwarded_proto": request.headers.get("x-forwarded-proto"),
    }
```

## 🧪 Testing Steps

### 1. Test with Simple Server
Run the test server to isolate the issue:
```bash
python test_server.py
```

Then test:
- Local: `http://localhost:8801/`
- Tunnel: `https://code.andr.ca/telecli/`
- Debug: `https://code.andr.ca/telecli/debug`

### 2. Check Server Logs
Look for detailed request information in the logs:
```bash
python -m src.main
# or
python src/web_app.py
```

### 3. Test Endpoints
- `/debug` - Shows request headers and forwarding info
- `/health` - Basic health check
- `/test` - Simple test endpoint (in test server)

## 🔍 Debugging Information

### Expected Headers from Cloudflare
```json
{
  "host": "code.andr.ca",
  "x-forwarded-for": "your.ip.address",
  "x-forwarded-proto": "https",
  "x-forwarded-host": "code.andr.ca",
  "cf-ray": "cloudflare-ray-id",
  "cf-connecting-ip": "your.ip.address"
}
```

### Common Issues

#### 1. Path Prefix Problems
- **Symptom**: 404 errors on API calls
- **Solution**: Ensure all frontend paths are relative (`./api/...`)

#### 2. WebSocket Connection Issues
- **Symptom**: WebSocket connection fails
- **Solution**: Check WebSocket URL generation in frontend

#### 3. CORS Issues
- **Symptom**: Browser blocks requests
- **Solution**: Add CORS middleware if needed

#### 4. SSL/TLS Issues
- **Symptom**: Mixed content warnings
- **Solution**: Ensure all resources use HTTPS through tunnel

## 🛠️ Alternative Solutions

### Option 1: Use Different Port
Try running on a different port:
```bash
# In .env
WEB_PORT=8802
```

### Option 2: Disable Middleware Temporarily
Comment out middleware to isolate the issue:
```python
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
# app.add_middleware(RequestLoggingMiddleware)
```

### Option 3: Use Different Tunnel Configuration
Try different Cloudflare tunnel settings:
```yaml
ingress:
  - hostname: code.andr.ca
    path: /telecli/*  # Note the wildcard
    service: http://localhost:8801
```

### Option 4: Run Without Path Prefix
Configure tunnel to serve at root:
```yaml
ingress:
  - hostname: telecli.code.andr.ca  # Subdomain instead of path
    service: http://localhost:8801
```

## 📊 Verification Steps

1. **Test Server Response**
   ```bash
   curl -v https://code.andr.ca/telecli/debug
   ```

2. **Check WebSocket**
   ```javascript
   // In browser console
   const ws = new WebSocket('wss://code.andr.ca/telecli/ws/test-123');
   ws.onopen = () => console.log('WebSocket connected');
   ws.onerror = (e) => console.error('WebSocket error:', e);
   ```

3. **Verify Authentication**
   ```bash
   curl -v https://code.andr.ca/telecli/api/auth/required
   ```

## 🚀 Next Steps

1. **Run test server** to isolate the issue
2. **Check debug endpoint** for request information
3. **Review server logs** for detailed error messages
4. **Test different tunnel configurations** if needed
5. **Consider using subdomain** instead of path prefix

If the test server works but the main application doesn't, the issue is likely in the application code rather than the tunnel configuration.