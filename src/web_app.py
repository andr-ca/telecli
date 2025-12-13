"""
FastAPI web application with WebSocket support
"""
import logging
import json
import asyncio
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from starlette.websockets import WebSocketDisconnect
from src.session_manager import SessionManager
from src.config import Config

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
    await websocket.accept()
    logger.info(f"WebSocket connection established for client {client_id}")

    async def handle_input():
        """Handle input from WebSocket -> Terminal"""
        try:
            while True:
                data = await websocket.receive_text()
                logger.info(f"Received from client {client_id}: {data[:100]}")
                
                try:
                    message = json.loads(data)
                    input_text = message.get("input", "")
                    if input_text:
                        # xterm.js sends input character by character, don't add newline
                        await session_manager.send_input(client_id, input_text, newline=False)
                        logger.info(f"Sent input to terminal for {client_id}: {repr(input_text[:50])}")
                    
                    # Handle terminal resize
                    if "resize" in message:
                        rows = message["resize"].get("rows", 24)
                        cols = message["resize"].get("cols", 80)
                        await session_manager.resize_session(client_id, rows, cols)
                        logger.info(f"Resized terminal for {client_id} to {rows}x{cols}")
                    
                    # Handle AI proxy control
                    if "proxy" in message:
                        proxy_cmd = message["proxy"]
                        if proxy_cmd.get("enable"):
                            provider = proxy_cmd.get("provider")
                            system_prompt = proxy_cmd.get("system_prompt")  # Get custom prompt
                            success = await session_manager.enable_ai_proxy(
                                client_id, 
                                provider, 
                                system_prompt
                            )
                            if success:
                                logger.info(f"Enabled AI proxy for {client_id} with custom prompt")
                                ai_proxy = session_manager.get_ai_proxy(client_id)
                                if ai_proxy:
                                    await websocket.send_json({"proxy_status": ai_proxy.get_status()})
                            else:
                                await websocket.send_json({"error": "Failed to enable AI proxy"})
                        elif proxy_cmd.get("disable"):
                            await session_manager.disable_ai_proxy(client_id)
                            logger.info(f"Disabled AI proxy for {client_id}")
                            await websocket.send_json({"proxy_status": {"enabled": False}})
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error from client {client_id}: {e}")
                except Exception as e:
                    logger.error(f"Error sending input for {client_id}: {e}")
                    break
        except WebSocketDisconnect as e:
            # Normal disconnect codes: 1000 (normal), 1001 (going away), 1012 (service restart)
            if e.code in [1000, 1001, 1012]:
                logger.info(f"Client {client_id} disconnected normally (code {e.code})")
            else:
                logger.warning(f"Client {client_id} disconnected with code {e.code}: {e.reason}")
        except Exception as e:
            logger.error(f"Input handler error for {client_id}: {e}")

    async def handle_output():
        """Handle output from Terminal -> WebSocket"""
        try:
            async for chunk in session_manager.get_output_stream(client_id):
                if chunk:
                    # Check if AI proxy is enabled for this session
                    ai_proxy = session_manager.get_ai_proxy(client_id)
                    if ai_proxy:
                        ai_proxy.add_output(chunk)
                        # Process output for prompt detection
                        await ai_proxy.process_output()
                    
                    logger.info(f"Sending {len(chunk)} bytes to client {client_id}")
                    await websocket.send_json({
                        "output": chunk
                    })
        except Exception as e:
            logger.info(f"Output handler ended for {client_id}: {e}")

    try:
        # Run both input and output handlers concurrently
        await asyncio.gather(
            handle_input(),
            handle_output(),
            return_exceptions=True
        )
    except WebSocketDisconnect as e:
        # Handle normal disconnections gracefully
        if e.code in [1000, 1001, 1012]:
            logger.info(f"Client {client_id} disconnected (code {e.code})")
        else:
            logger.warning(f"Client {client_id} disconnected unexpectedly (code {e.code}): {e.reason}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        logger.info(f"WebSocket connection closed for client {client_id}")
        # Clean up session when WebSocket closes
        try:
            await session_manager.close_session(client_id)
        except Exception as e:
            logger.error(f"Error closing session {client_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.WEB_HOST, port=Config.WEB_PORT)
