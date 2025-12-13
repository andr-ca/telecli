"""Tests for session manager"""
import pytest
from src.session_manager import SessionManager


@pytest.mark.asyncio
async def test_session_manager_creation():
    """Test creating a session manager"""
    manager = SessionManager()
    assert manager.max_sessions == 100
    assert len(manager.sessions) == 0


@pytest.mark.asyncio
async def test_session_manager_get_session():
    """Test getting a session"""
    manager = SessionManager()
    session = await manager.get_session("test-user")
    assert session is not None
    assert session.is_active
    await manager.close_session("test-user")


@pytest.mark.asyncio
async def test_session_manager_stats():
    """Test getting statistics"""
    manager = SessionManager()
    stats = manager.get_stats()
    assert "active_sessions" in stats
    assert "max_sessions" in stats
    assert "total_created" in stats


# TODO: Add tests for:
# - test_session_manager_max_sessions_limit()
# - test_session_manager_send_command()
# - test_session_manager_close_all()
# - test_session_manager_responsiveness_check()
