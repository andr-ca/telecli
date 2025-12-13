"""
FastAPI web application with WebSocket support
"""
import logging
import json
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
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


@app.get("/")
async def get_root():
    """Serve the web UI"""
    return FileResponse("static/index.html")


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
    """WebSocket endpoint for real-time terminal access"""
    await websocket.accept()
    logger.info(f"WebSocket connection established for client {client_id}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                })
                continue

            command = message_data.get("message", "")
            if not command:
                await websocket.send_json({
                    "type": "error",
                    "message": "No message provided",
                })
                continue

            try:
                # Execute command
                output = await session_manager.send_command(client_id, command)
                
                # Send response
                await websocket.send_json({
                    "type": "assistant",
                    "message": output,
                })
            except Exception as e:
                logger.error(f"Error executing command for {client_id}: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Command failed: {str(e)}",
                })

    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        logger.info(f"WebSocket connection closed for client {client_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.WEB_HOST, port=Config.WEB_PORT)
