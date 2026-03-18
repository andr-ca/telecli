"""
WebSocket message models for validation and type safety
"""
from typing import Optional
from pydantic import BaseModel, Field


class ResizePayload(BaseModel):
    """Terminal resize command"""
    rows: int = Field(default=24, ge=1, le=500)
    cols: int = Field(default=80, ge=1, le=500)


class ProxyCommand(BaseModel):
    """AI Proxy control command"""
    enable: Optional[bool] = None
    disable: Optional[bool] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None


class ClaudeCodeCommand(BaseModel):
    """Claude Code auto-continue control command"""
    enable: Optional[bool] = None
    disable: Optional[bool] = None
    screen_text: Optional[str] = None


class WebSocketMessage(BaseModel):
    """WebSocket message from client"""
    input: Optional[str] = None
    resize: Optional[ResizePayload] = None
    proxy: Optional[ProxyCommand] = None
    claude_code: Optional[ClaudeCodeCommand] = None

    class Config:
        extra = "allow"  # Allow additional fields for forward compatibility
