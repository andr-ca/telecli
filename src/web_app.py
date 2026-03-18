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
from pydantic import BaseModel, ValidationError
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

    # Pass monitor entry function to session manager
    session_manager.set_monitor_callback(add_llm_monitor_entry)

    logger.info("Web app started")
    yield
    await session_manager.close_all()
    session_manager = None
    logger.info("Web app stopped")


app = FastAPI(
    title="TeleCLI",
    lifespan=lifespan,
)

# Add middleware to handle reverse proxy headers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Router for all endpoints to support multiple prefixes
router = APIRouter()


class CreateSessionRequest(BaseModel):
    name: str | None = None


class RenameSessionRequest(BaseModel):
    name: str


class ImportTmuxSessionRequest(BaseModel):
    tmux_session_name: str
    name: str | None = None


class CreateTmuxSessionRequest(BaseModel):
    name: str

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
    return {"sessions": session_manager.list_sessions()}


@router.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a named TeleCLI-only session entry."""
    return {"session": session_manager.create_session_entry(request.name)}


@router.patch("/api/sessions/{session_id}")
async def rename_session(session_id: str, request: RenameSessionRequest):
    """Rename a TeleCLI session entry."""
    try:
        return {"session": session_manager.rename_session(session_id, request.name)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/sessions/{session_id}")
async def delete_session_entry(session_id: str):
    """Delete a session entry from TeleCLI."""
    await session_manager.delete_session_entry(session_id)
    return {"status": "ok"}


@router.get("/api/tmux/sessions")
async def get_machine_tmux_sessions():
    """List tmux sessions currently available on the machine."""
    return {"sessions": session_manager.list_machine_tmux_sessions()}


@router.post("/api/tmux/sessions")
async def create_tmux_session(request: CreateTmuxSessionRequest):
    """Create a new machine tmux session and import it into TeleCLI."""
    try:
        return {"session": session_manager.create_tmux_session_entry(request.name)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/sessions/import-tmux")
async def import_tmux_session(request: ImportTmuxSessionRequest):
    """Import an existing machine tmux session into TeleCLI."""
    try:
        return {"session": session_manager.import_tmux_session(request.tmux_session_name, request.name)}
    except KeyError:
        raise HTTPException(status_code=404, detail="tmux session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/sessions/{session_id}/detach")
async def detach_tmux_session(session_id: str):
    """Detach TeleCLI from a tmux-backed session while keeping the imported entry."""
    try:
        return {"session": await session_manager.detach_tmux_session(session_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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

    async def safe_send_json(payload: dict) -> bool:
        nonlocal connection_active
        if not connection_active:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            connection_active = False
            return False

    # Monitoring callback to send LLM info live to the UI
    async def llm_monitor_callback(entry_type: str, data: dict):
        await safe_send_json({
            "llm_monitor": {
                "type": entry_type,
                "data": data
            }
        })

    async def claude_code_status_callback(status: dict):
        await safe_send_json({"claude_code_status": status})

    # Hook into AI proxy if it exists
    ai_proxy = session_manager.get_ai_proxy(client_id)
    if ai_proxy:
        ai_proxy.set_monitor_callback(llm_monitor_callback)
        if not await safe_send_json({"proxy_status": ai_proxy.get_status()}):
            return
    else:
        if not await safe_send_json({"proxy_status": {"enabled": False}}):
            return

    claude_code_auto = session_manager.get_claude_code_auto_continue(client_id)
    if claude_code_auto:
        claude_code_auto.set_status_callback(claude_code_status_callback)
        if not await safe_send_json({"claude_code_status": claude_code_auto.get_status()}):
            return
    else:
        if not await safe_send_json({"claude_code_status": {"enabled": False}}):
            return

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
                        # Notify proxy of user interaction
                        ai_proxy = session_manager.get_ai_proxy(client_id)
                        if ai_proxy and ai_proxy.is_enabled():
                            ai_proxy.notify_user_input(input_text)

                    if "resize" in message:
                        await session_manager.resize_session(
                            client_id,
                            message["resize"].get("rows", 24),
                            message["resize"].get("cols", 80)
                        )

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
                                    await safe_send_json({"proxy_status": ai_proxy.get_status()})
                        elif proxy_cmd.get("disable"):
                            await session_manager.disable_ai_proxy(client_id)
                            await safe_send_json({"proxy_status": {"enabled": False}})

                    if "claude_code" in message:
                        claude_code_cmd = message["claude_code"]
                        if claude_code_cmd.get("enable"):
                            success = await session_manager.enable_claude_code_auto_continue(client_id)
                            if success:
                                claude_code_auto = session_manager.get_claude_code_auto_continue(client_id)
                                if claude_code_auto:
                                    claude_code_auto.set_status_callback(claude_code_status_callback)
                                    await safe_send_json({"claude_code_status": claude_code_auto.get_status()})
                        elif claude_code_cmd.get("disable"):
                            await session_manager.disable_claude_code_auto_continue(client_id)
                            await safe_send_json({"claude_code_status": {"enabled": False}})
                        elif claude_code_cmd.get("screen_text"):
                            claude_code_auto = session_manager.get_claude_code_auto_continue(client_id)
                            if claude_code_auto and claude_code_auto.is_enabled():
                                claude_code_auto.inspect_screen_text(claude_code_cmd["screen_text"])
                except json.JSONDecodeError:
                    pass
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
                    # Feed chunk to AI proxy for pattern detection
                    ai_proxy = session_manager.get_ai_proxy(client_id)
                    if ai_proxy and ai_proxy.is_enabled():
                        ai_proxy.add_output(chunk)

                    claude_code_auto = session_manager.get_claude_code_auto_continue(client_id)
                    if claude_code_auto and claude_code_auto.is_enabled():
                        claude_code_auto.add_output(chunk)

                    # Forward to browser
                    await safe_send_json({"output": chunk})
        except Exception:
            connection_active = False

    async def ai_proxy_checker():
        """Periodic check for prompt detection while AI proxy is enabled"""
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
        claude_code_auto = session_manager.get_claude_code_auto_continue(client_id)
        if claude_code_auto:
            claude_code_auto.set_status_callback(None)
        # Session is NOT closed here to allow persistence & reconnection
        # sessions are managed by max_sessions policy in SessionManager
        logger.info(f"WebSocket disconnected for {client_id}, session kept alive")


# Explicit route for /telecli without trailing slash to satisfy browsers/proxies
@app.get("/telecli")
async def get_telecli_root_no_slash():
    """Serve the web UI for /telecli without trailing slash"""
    return FileResponse("static/index.html")

# Include router at both root and /telecli prefix for flexible access
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
