"""Tests for logging system"""
import pytest
import logging
from pathlib import Path
import tempfile
from src.logger import setup_logging, get_logger


@pytest.fixture
def temp_log_dir():
    """Create temporary log directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_get_logger():
    """Test getting a logger instance"""
    logger = get_logger(__name__)
    assert isinstance(logger, logging.Logger)
    assert logger.name == __name__


def test_setup_logging_console():
    """Test setting up console logging"""
    logger = setup_logging()
    assert isinstance(logger, logging.Logger)
    # Should have at least one handler
    assert len(logger.handlers) > 0


# TODO: Add tests for all rotation modes:
# - test_setup_logging_append()
# - test_setup_logging_new_each_start()
# - test_setup_logging_timestamp_rotate()
# - test_cleanup_log_directory()
# - test_write_position_top()
# - test_write_position_bottom()
