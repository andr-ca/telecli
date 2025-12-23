"""
FastAPI web application with WebSocket support
"""
import logging
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from starlette.websockets import WebSocketDisconnect
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError
from src.session_manager import SessionManager
from src.config import Config
from src.ws_models import WebSocketMessage

logger = logging.getLogger(__name__)

# Global session manager
session_manager: SessionManager = None

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    global session_manager
    session_manager = SessionManager()
    logger.info("Web app started")
    yield
    await session_manager.close_all()
    logger.info("Web app stopped")


app = FastAPI(
    title="TeleCLI", 
    lifespan=lifespan,
)

# Add middleware to handle reverse proxy headers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Router for all endpoints to support multiple prefixes
router = APIRouter()

@router.get("/")
async def get_root():
    """Serve the web UI"""
    return FileResponse("static/index.html")

@router.get("/style.css")
async def get_style():
    """Serve the CSS file"""
    return FileResponse("static/style.css")

@router.get("/debug")
async def debug_info(request: Request):
    """Debug endpoint to check request information"""
    return {
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers),
        "path": request.url.path,
        "query": request.url.query,
        "host": request.headers.get("host"),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "x_forwarded_proto": request.headers.get("x-forwarded-proto"),
    }

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    stats = session_manager.get_stats()
    return {
        "status": "healthy",
        "sessions": stats,
    }

@router.get("/stats")
async def get_stats():
    """Get server statistics"""
    stats = session_manager.get_stats()
    return stats

@router.get("/api/sessions")
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

@router.get("/api/llm-monitor")
async def get_llm_monitor_data():
    """Get LLM monitor data"""
    return {"entries": llm_monitor_data}

@router.delete("/api/llm-monitor")
async def clear_llm_monitor_data():
    """Clear LLM monitor data"""
    global llm_monitor_data
    llm_monitor_data = []
    return {"status": "cleared"}

@router.get("/api/auth/required")
async def get_auth_required():
    """Get whether authentication is required"""
    return {
        "auth_required": Config.AUTH_REQUIRED
    }

@router.get("/api/ai-proxy/config")
async def get_ai_proxy_config():
    """Get AI proxy configuration (single source of truth)"""
    return {
        "default_provider": Config.AI_PROXY_PROVIDER,
        "default_system_prompt": Config.AI_PROXY_SYSTEM_PROMPT,
        "max_iterations": Config.AI_PROXY_MAX_ITERATIONS
    }

@router.post("/reset/{client_id}")
async def reset_session(client_id: str):
    """Reset a client's session"""
    try:
        await session_manager.close_session(client_id)
        logger.info(f"Reset session for client {client_id}")
        return {"status": "ok", "message": "Session reset"}
    except Exception as e:
        logger.error(f"Error resetting session {client_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/{client_id}")
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

    connection_active = True
    
    async def llm_monitor_callback(entry_type: str, data: dict):
        nonlocal connection_active
        if not connection_active:
            return
        try:
            await websocket.send_json({
                "llm_monitor": {
                    "type": entry_type,
                    "data": data
                }
            })
        except Exception:
            connection_active = False
    
    ai_proxy = session_manager.get_ai_proxy(client_id)
    if ai_proxy:
        ai_proxy.set_monitor_callback(llm_monitor_callback)
    
    # Session reconnection logic
    if client_id in session_manager.sessions:
        try:
            session = await session_manager.get_session(client_id)
            await asyncio.sleep(0.2)
            await session.send_input(" \b", newline=False)
            await asyncio.sleep(0.1)
            await session.send_input("", newline=True)
            await asyncio.sleep(0.1)
            await session.send_input("\x0C", newline=False)
        except Exception as e:
            logger.warning(f"Could not refresh existing session {client_id}: {e}")

    async def handle_input():
        nonlocal connection_active
        try:
            while connection_active:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    input_text = message.get("input", "")
                    if input_text:
                        await session_manager.send_input(client_id, input_text, newline=False, from_ai=False)
                        ai_proxy = session_manager.get_ai_proxy(client_id)
                        if ai_proxy and ai_proxy.is_enabled():
                            ai_proxy.notify_user_input(input_text)
                    
                    if "resize" in message:
                        rows = message["resize"].get("rows", 24)
                        cols = message["resize"].get("cols", 80)
                        await session_manager.resize_session(client_id, rows, cols)
                    
                    if "proxy" in message:
                        proxy_cmd = message["proxy"]
                        if proxy_cmd.get("enable"):
                            success = await session_manager.enable_ai_proxy(
                                client_id, 
                                proxy_cmd.get("provider"), 
                                proxy_cmd.get("system_prompt")
                            )
                            if success:
                                ai_proxy = session_manager.get_ai_proxy(client_id)
                                if ai_proxy:
                                    ai_proxy.set_monitor_callback(llm_monitor_callback)
                                    await websocket.send_json({"proxy_status": ai_proxy.get_status()})
                        elif proxy_cmd.get("disable"):
                            await session_manager.disable_ai_proxy(client_id)
                            await websocket.send_json({"proxy_status": {"enabled": False}})
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error processing message for {client_id}: {e}")
        except WebSocketDisconnect:
            connection_active = False
        except Exception as e:
            logger.error(f"Input handler error for {client_id}: {e}")
            connection_active = False

    async def handle_output():
        nonlocal connection_active
        try:
            async for chunk in session_manager.get_output_stream(client_id):
                if not connection_active:
                    break
                if chunk:
                    ai_proxy = session_manager.get_ai_proxy(client_id)
                    if ai_proxy and ai_proxy.is_enabled():
                        ai_proxy.add_output(chunk)
                    await websocket.send_json({"output": chunk})
        except Exception:
            connection_active = False
    
    async def ai_proxy_checker():
        try:
            while connection_active:
                await asyncio.sleep(0.5)
                ai_proxy = session_manager.get_ai_proxy(client_id)
                if ai_proxy and ai_proxy.is_enabled():
                    await ai_proxy.process_output()
        except Exception:
            pass

    try:
        await asyncio.gather(
            handle_input(),
            handle_output(),
            ai_proxy_checker(),
            return_exceptions=True
        )
    finally:
        connection_active = False
        ai_proxy = session_manager.get_ai_proxy(client_id)
        if ai_proxy:
            ai_proxy.set_monitor_callback(None)
        await session_manager.close_session(client_id)


@app.get("/telecli")
async def get_telecli_root_no_slash():
    """Serve the web UI for /telecli without trailing slash"""
    return FileResponse("static/index.html")

# Include router at both root and /telecli prefix
app.include_router(router)

app.include_router(router, prefix="/telecli")

# Mount static files (at both locations to be safe)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/telecli/static", StaticFiles(directory="static"), name="static_telecli")

if __name__ == "__main__":
    import uvicorn
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
