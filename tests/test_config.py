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
    assert Config.TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS >= 0.01
    assert Config.TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS >= 0.001


def test_config_validation_does_not_require_telegram_token_without_webhook(monkeypatch):
    """Telegram config should remain optional for web-only startup."""
    monkeypatch.setattr(Config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(Config, "TELEGRAM_WEBHOOK_URL", "")

    Config.validate()


def test_config_validation_requires_telegram_token_for_webhook(monkeypatch):
    """Webhook mode should still require a Telegram bot token."""
    monkeypatch.setattr(Config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(Config, "TELEGRAM_WEBHOOK_URL", "https://example.com/webhook")

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Config.validate()


def test_config_log_level():
    """Test log level conversion"""
    import logging
    level = Config.get_log_level()
    assert level == logging.INFO
