"""Tests for configuration module"""
import pytest
from src.config import Config


def test_config_defaults():
    """Test that config has sensible defaults"""
    assert Config.LOG_LEVEL == "INFO"
    assert Config.LOG_OUTPUT == "console"
    assert Config.TERMINAL_SHELL == "bash"
    assert Config.TERMINAL_TIMEOUT == 300
    assert Config.WEB_PORT == 8000


def test_config_validation():
    """Test config validation"""
    # This should raise if TELEGRAM_BOT_TOKEN is missing
    # (unless it's set in environment)
    if not Config.TELEGRAM_BOT_TOKEN:
        with pytest.raises(ValueError):
            Config.validate()


def test_config_log_level():
    """Test log level conversion"""
    import logging
    level = Config.get_log_level()
    assert level == logging.INFO
