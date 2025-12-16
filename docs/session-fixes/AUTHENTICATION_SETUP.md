# Authentication Setup Documentation

## 🔐 Authentication Configuration

Authentication has been enabled for the TeleCLI application with the following settings:

### Environment Configuration
```bash
# In .env file
AUTH_REQUIRED=true
AUTH_TOKEN=password
```

### How Authentication Works

1. **WebSocket Connection**: All WebSocket connections require authentication when `AUTH_REQUIRED=true`
2. **Token Validation**: The client must provide the correct token via query parameter
3. **Frontend Modal**: A secure modal prompts users for the authentication token
4. **Token Storage**: Valid tokens are stored in browser localStorage for future sessions

## 🚀 User Experience

### First Visit
1. User opens the TeleCLI web interface
2. Application detects authentication is required
3. Secure modal appears asking for authentication token
4. User enters: `password`
5. Token is validated and stored in browser
6. WebSocket connection established
7. Terminal becomes available

### Subsequent Visits
1. Application checks for stored token
2. If valid token exists, connects automatically
3. If no token or invalid, shows authentication modal again

## 🔧 Technical Implementation

### Backend (src/web_app.py)
```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # Check authentication if required
    if Config.AUTH_REQUIRED:
        token = websocket.query_params.get("token")
        if not token or token != Config.AUTH_TOKEN:
            logger.warning(f"WebSocket auth failed for {client_id}: invalid or missing token")
            await websocket.close(code=1008, reason="Unauthorized")
            return
```

### Frontend (static/index.html)
- **Auth Modal**: Secure password input modal
- **Token Storage**: localStorage for persistence
- **Auto-retry**: Automatic reconnection with new token on auth failure
- **Clear Auth**: Button to clear stored token

## 🎯 Security Features

1. **Password Input**: Token input field uses `type="password"`
2. **Secure Storage**: Token stored in browser localStorage (not cookies)
3. **Connection Validation**: Every WebSocket connection validates token
4. **Auth Failure Handling**: Graceful handling of invalid tokens
5. **Clear Auth**: Users can clear stored tokens

## 🔑 Access Credentials

**Authentication Token**: `password`

## 📱 UI Elements

### Auth Button
- Appears in header when token is stored
- Allows users to clear authentication
- Shows/hides based on auth state

### Auth Modal
- Clean, professional design
- Password field for security
- Skip option for testing
- Enter key support
- Escape key to cancel

## 🧪 Testing

To test authentication:

1. **Enable Auth**: Ensure `AUTH_REQUIRED=true` in `.env`
2. **Start Server**: Run the application
3. **Open Browser**: Navigate to the web interface
4. **Enter Token**: Use `password` when prompted
5. **Verify Access**: Terminal should become available

To test auth failure:
1. Enter wrong token
2. Should see "Authentication failed" error
3. Modal should reappear for retry

## 🔄 Managing Authentication

### To Disable Authentication
```bash
# In .env file
AUTH_REQUIRED=false
```

### To Change Token
```bash
# In .env file
AUTH_TOKEN=your_new_token_here
```

### To Clear User's Stored Token
Users can click the "🔓 Auth" button in the header to clear their stored token.

## 🚨 Security Notes

- Token is transmitted via WebSocket query parameter (secure over HTTPS)
- Token is stored in browser localStorage (cleared when browser data is cleared)
- Invalid authentication attempts are logged
- No rate limiting implemented (consider adding for production)
- Token is visible in browser developer tools (consider more secure methods for production)

This authentication system provides a good balance of security and usability for the TeleCLI application.