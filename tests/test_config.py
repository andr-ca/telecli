"""Tests for configuration module"""
import pytest
from src.config import Config


def test_config_defaults():
    """Test that config fields are present with valid values."""
    assert Config.LOG_LEVEL in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    assert Config.LOG_OUTPUT in {"console", "file", "both"}
    assert isinstance(Config.TERMINAL_SHELL, str) and Config.TERMINAL_SHELL
    assert Config.TERMINAL_TIMEOUT >= 1
    assert 1 <= Config.WEB_PORT <= 65535
    assert isinstance(Config.SESSION_REGISTRY_PATH, str) and Config.SESSION_REGISTRY_PATH
    assert Config.CLAUDE_CODE_AUTO_CONTINUE_GRACE_SECONDS >= 0
    assert Config.CLAUDE_CODE_CCUSAGE_TIMEOUT_SECONDS >= 1


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
