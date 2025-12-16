"""
FastAPI web application with WebSocket support
"""
import logging
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from starlette.websockets import WebSocketDisconnect
from pydantic import ValidationError
from src.session_manager import SessionManager
from src.config import Config
from src.ws_models import WebSocketMessage

logger = logging.getLogger(__name__)

# Global session manager
session_manager: SessionManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    global session_manager
    session_manager = SessionManager()
    logger.info("Web app started")
    yield
    await session_manager.close_all()
    logger.info("Web app stopped")


app = FastAPI(title="TeleCLI", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_root():
    """Serve the web UI"""
    return FileResponse("static/index.html")


@app.get("/style.css")
async def get_style():
    """Serve the CSS file"""
    return FileResponse("static/style.css")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    stats = session_manager.get_stats()
    return {
        "status": "healthy",
        "sessions": stats,
    }


@app.get("/stats")
async def get_stats():
    """Get server statistics"""
    stats = session_manager.get_stats()
    return stats


@app.get("/api/sessions")
async def get_active_sessions():
    """Get list of active sessions"""
    sessions = []
    for session_id, session in session_manager.sessions.items():
        if session.is_active:
            sessions.append({
                "id": session_id,
                "created_at": session_id.split('-')[-1] if '-' in session_id else "unknown",
                "shell": session.shell,
                "is_active": session.is_active
            })
    return {"sessions": sessions}


# Global LLM monitor data
llm_monitor_data = []
MAX_MONITOR_ENTRIES = 100

def add_llm_monitor_entry(entry_type: str, data: dict):
    """Add entry to LLM monitor data"""
    global llm_monitor_data
    entry = {
        "type": entry_type,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    llm_monitor_data.append(entry)
    
    # Keep only recent entries
    if len(llm_monitor_data) > MAX_MONITOR_ENTRIES:
        llm_monitor_data = llm_monitor_data[-MAX_MONITOR_ENTRIES:]

@app.get("/api/llm-monitor")
async def get_llm_monitor_data():
    """Get LLM monitor data"""
    return {"entries": llm_monitor_data}

@app.delete("/api/llm-monitor")
async def clear_llm_monitor_data():
    """Clear LLM monitor data"""
    global llm_monitor_data
    llm_monitor_data = []
    return {"status": "cleared"}


@app.get("/api/auth/required")
async def get_auth_required():
    """Get whether authentication is required"""
    return {
        "auth_required": Config.AUTH_REQUIRED
    }


@app.get("/api/ai-proxy/config")
async def get_ai_proxy_config():
    """Get AI proxy configuration (single source of truth)"""
    return {
        "default_provider": Config.AI_PROXY_PROVIDER,
        "default_system_prompt": Config.AI_PROXY_SYSTEM_PROMPT,
        "max_iterations": Config.AI_PROXY_MAX_ITERATIONS
    }


@app.post("/reset/{client_id}")
async def reset_session(client_id: str):
    """Reset a client's session"""
    try:
        await session_manager.close_session(client_id)
        logger.info(f"Reset session for client {client_id}")
        return {"status": "ok", "message": "Session reset"}
    except Exception as e:
        logger.error(f"Error resetting session {client_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for bidirectional terminal streaming"""

    # Check authentication if required
    if Config.AUTH_REQUIRED:
        token = websocket.query_params.get("token")
        if not token or token != Config.AUTH_TOKEN:
            logger.warning(f"WebSocket auth failed for {client_id}: invalid or missing token")
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()
    logger.info(f"WebSocket connection established for client {client_id}")

    # Track connection state
    connection_active = True
    logger.info(f"WebSocket connection_active initialized to True for {client_id}")
    
    # Set up LLM monitoring callback for this client
    async def llm_monitor_callback(entry_type: str, data: dict):
        """Send LLM monitoring data to WebSocket client"""
        nonlocal connection_active
        
        if not connection_active:
            logger.debug(f"LLM monitor callback skipped - connection_active=False for {client_id}")
            return  # Don't try to send if connection is closed
        
        try:
            await websocket.send_json({
                "llm_monitor": {
                    "type": entry_type,
                    "data": data
                }
            })
        except Exception as e:
            logger.debug(f"Failed to send LLM monitor data: {e}")
            # Mark connection as inactive if send fails
            logger.warning(f"Marking connection_active=False for {client_id} due to LLM monitor send failure")
            connection_active = False
    
    # Set the callback for this specific session's AI proxy (if it exists)
    ai_proxy = session_manager.get_ai_proxy(client_id)
    if ai_proxy:
        ai_proxy.set_monitor_callback(llm_monitor_callback)
    
    # Check if this is a reconnection to an existing session
    # If reconnecting, send multiple refresh attempts to ensure terminal responsiveness
    session_existed = client_id in session_manager.sessions
    if session_existed:
        try:
            session = await session_manager.get_session(client_id)
            logger.info(f"Reconnecting to existing session {client_id} - applying terminal refresh")
            
            # Wait a bit longer to ensure connection is fully established
            await asyncio.sleep(0.2)
            
            # Try multiple refresh strategies for better reliability
            try:
                # Strategy 1: Space + backspace (gentle refresh)
                await session.send_input(" \b", newline=False)
                await asyncio.sleep(0.1)
                
                # Strategy 2: Send a newline to trigger prompt redraw
                await session.send_input("", newline=True)
                await asyncio.sleep(0.1)
                
                # Strategy 3: Send Ctrl+L (clear screen) as last resort if needed
                # This is more aggressive but ensures terminal responsiveness
                await session.send_input("\x0C", newline=False)
                
                logger.info(f"Successfully applied terminal refresh strategies to session {client_id}")
                
            except Exception as refresh_error:
                logger.warning(f"Terminal refresh failed for session {client_id}: {refresh_error}")
                # Even if refresh fails, continue with the connection
                
        except Exception as e:
            logger.warning(f"Could not refresh existing session {client_id}: {e}")
            # Continue anyway - the session might still work
    else:
        logger.debug(f"New session {client_id} - no refresh needed")

    async def handle_input():
        """Handle input from WebSocket -> Terminal"""
        nonlocal connection_active
        try:
            while connection_active:
                data = await websocket.receive_text()
                logger.info(f"Received from client {client_id}: {data[:100]}")
                logger.debug(f"Input handler processing message, connection_active={connection_active}")
                
                try:
                    message = json.loads(data)
                    input_text = message.get("input", "")
                    if input_text:
                        # Send input immediately for best responsiveness (this is user input)
                        try:
                            await session_manager.send_input(client_id, input_text, newline=False, from_ai=False)
                        except Exception as input_error:
                            logger.error(f"Error sending input to session {client_id}: {input_error}")
                            # Don't break the connection, just log the error and continue
                            continue
                        
                        # Notify AI proxy after sending (non-blocking) - only for user input
                        ai_proxy = session_manager.get_ai_proxy(client_id)
                        if ai_proxy and ai_proxy.is_enabled():
                            ai_proxy.notify_user_input(input_text)
                        
                        # Only log in debug mode to reduce overhead
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Sent input to terminal for {client_id}: {repr(input_text[:50])}")
                    
                    # Handle terminal resize
                    if "resize" in message:
                        rows = message["resize"].get("rows", 24)
                        cols = message["resize"].get("cols", 80)
                        await session_manager.resize_session(client_id, rows, cols)
                        logger.info(f"Resized terminal for {client_id} to {rows}x{cols}")
                    
                    # Handle AI proxy control
                    if "proxy" in message:
                        proxy_cmd = message["proxy"]
                        logger.info(f"📡 Received proxy command: {proxy_cmd}")
                        if proxy_cmd.get("enable"):
                            provider = proxy_cmd.get("provider")
                            system_prompt = proxy_cmd.get("system_prompt")  # Get custom prompt
                            logger.info(f"🔧 Enabling AI proxy: provider={provider}, has_custom_prompt={bool(system_prompt)}")
                            success = await session_manager.enable_ai_proxy(
                                client_id, 
                                provider, 
                                system_prompt
                            )
                            if success:
                                logger.info(f"✅ Enabled AI proxy for {client_id}")
                                ai_proxy = session_manager.get_ai_proxy(client_id)
                                if ai_proxy:
                                    # Set the monitor callback for this specific AI proxy
                                    ai_proxy.set_monitor_callback(llm_monitor_callback)
                                    status = ai_proxy.get_status()
                                    logger.info(f"Status: {status}")
                                    try:
                                        await websocket.send_json({"proxy_status": status})
                                    except Exception as ws_error:
                                        logger.debug(f"Failed to send proxy status: {ws_error}")
                            else:
                                logger.error(f"❌ Failed to enable AI proxy for {client_id}")
                                try:
                                    await websocket.send_json({"error": "Failed to enable AI proxy"})
                                except Exception as ws_error:
                                    logger.debug(f"Failed to send error message: {ws_error}")
                        elif proxy_cmd.get("disable"):
                            logger.info(f"🔧 Disabling AI proxy for {client_id}")
                            await session_manager.disable_ai_proxy(client_id)
                            logger.info(f"✅ Disabled AI proxy for {client_id}")
                            try:
                                await websocket.send_json({"proxy_status": {"enabled": False}})
                            except Exception as ws_error:
                                logger.debug(f"Failed to send proxy disable status: {ws_error}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error from client {client_id}: {e}")
                    # Continue processing other messages despite JSON error
                except Exception as e:
                    logger.error(f"Error processing message for {client_id}: {e}")
                    # Log the error but continue processing other messages
                    # Only break if it's a critical connection error
                    if "connection" in str(e).lower() or "websocket" in str(e).lower():
                        logger.error(f"Critical connection error, stopping input handler: {e}")
                        break
        except WebSocketDisconnect as e:
            # Normal disconnect codes: 1000 (normal), 1001 (going away), 1012 (service restart)
            if e.code in [1000, 1001, 1012]:
                logger.info(f"Client {client_id} disconnected normally (code {e.code})")
            else:
                logger.warning(f"Client {client_id} disconnected with code {e.code}: {e.reason}")
            connection_active = False
        except Exception as e:
            logger.error(f"Input handler error for {client_id}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            connection_active = False

    async def handle_output():
        """Handle output from Terminal -> WebSocket"""
        nonlocal connection_active
        try:
            async for chunk in session_manager.get_output_stream(client_id):
                if not connection_active:
                    break  # Stop if connection is closed
                
                if chunk:
                    # Check if AI proxy is enabled for this session
                    ai_proxy = session_manager.get_ai_proxy(client_id)
                    if ai_proxy and ai_proxy.is_enabled():
                        logger.debug(f"🤖 AI proxy active, buffering chunk: {len(chunk)} bytes")
                        ai_proxy.add_output(chunk)
                        # Don't process immediately - let inactivity detection work
                        # process_output will be called by a background task
                    
                    logger.debug(f"Sending {len(chunk)} bytes to client {client_id}")
                    try:
                        await websocket.send_json({
                            "output": chunk
                        })
                    except Exception as send_error:
                        logger.debug(f"Failed to send output to {client_id}: {send_error}")
                        connection_active = False
                        break
        except Exception as e:
            logger.info(f"Output handler ended for {client_id}: {e}")
            connection_active = False
    
    async def ai_proxy_checker():
        """Background task to periodically check for prompts"""
        try:
            while connection_active:
                await asyncio.sleep(0.5)  # Check every 500ms
                if not connection_active:
                    break
                ai_proxy = session_manager.get_ai_proxy(client_id)
                if ai_proxy and ai_proxy.is_enabled():
                    await ai_proxy.process_output()
        except Exception as e:
            logger.debug(f"AI proxy checker ended for {client_id}: {e}")

    try:
        # Run input/output handlers and AI proxy checker concurrently
        await asyncio.gather(
            handle_input(),
            handle_output(),
            ai_proxy_checker(),
            return_exceptions=True
        )
    except WebSocketDisconnect as e:
        # Handle normal disconnections gracefully
        connection_active = False
        if e.code in [1000, 1001, 1012]:
            logger.info(f"Client {client_id} disconnected (code {e.code})")
        else:
            logger.warning(f"Client {client_id} disconnected unexpectedly (code {e.code}): {e.reason}")
    except Exception as e:
        connection_active = False
        logger.error(f"WebSocket error for client {client_id}: {e}")
        logger.error(f"WebSocket exception type: {type(e).__name__}")
        import traceback
        logger.error(f"WebSocket traceback: {traceback.format_exc()}")
    finally:
        connection_active = False
        logger.info(f"WebSocket connection closed for client {client_id}")
        logger.info(f"Connection closed - connection_active set to False")
        
        # Clear the monitor callback for this session's AI proxy
        try:
            ai_proxy = session_manager.get_ai_proxy(client_id)
            if ai_proxy:
                ai_proxy.set_monitor_callback(None)
        except Exception as e:
            logger.debug(f"Error clearing monitor callback for {client_id}: {e}")
        
        # Clean up session when WebSocket closes
        try:
            if session_manager and client_id:
                await session_manager.close_session(client_id)
        except Exception as e:
            logger.error(f"Error closing session {client_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.WEB_HOST, port=Config.WEB_PORT)
