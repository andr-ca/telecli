"""
Configuration management - loads from .env with sensible defaults
"""
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
from src.command_filter import CommandFilter

# Load .env file
load_dotenv()


def _get_int(key: str, default: int, min_value: int = None, max_value: int = None) -> int:
    """Safe integer conversion from environment variable with validation"""
    try:
        value = int(os.getenv(key, default))
        if min_value is not None and value < min_value:
            raise ValueError(f"Value {value} is less than minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Value {value} is greater than maximum {max_value}")
        return value
    except ValueError as e:
        raise ValueError(f"Invalid {key}: {e}. Expected integer, got '{os.getenv(key)}'")


def _get_float(key: str, default: float, min_value: float = None, max_value: float = None) -> float:
    """Safe float conversion from environment variable with validation"""
    try:
        value = float(os.getenv(key, default))
        if min_value is not None and value < min_value:
            raise ValueError(f"Value {value} is less than minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Value {value} is greater than maximum {max_value}")
        return value
    except ValueError as e:
        raise ValueError(f"Invalid {key}: {e}. Expected float, got '{os.getenv(key)}'")


class Config:
    """Configuration singleton"""

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_OUTPUT = os.getenv("LOG_OUTPUT", "console").lower()  # console, file, both
    LOG_FILE_DIR = os.getenv("LOG_FILE_DIR", "./logs")
    LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "telecli")
    LOG_FILE_MODE = os.getenv("LOG_FILE_MODE", "append").lower()  # append, new_each_start, timestamp_rotate
    LOG_FILE_MAX_SIZE = _get_int("LOG_FILE_MAX_SIZE", 100, min_value=1)  # MB
    LOG_DIR_MAX_SIZE = _get_int("LOG_DIR_MAX_SIZE", 1000, min_value=1)  # MB
    LOG_ROTATION_INTERVAL = os.getenv("LOG_ROTATION_INTERVAL", "1d").lower()  # 1d, 1w, 1m
    LOG_WRITE_POSITION = os.getenv("LOG_WRITE_POSITION", "bottom").lower()  # top, bottom

    # Terminal Configuration
    TERMINAL_SHELL = os.getenv("TERMINAL_SHELL", "bash")
    TERMINAL_TIMEOUT = _get_int("TERMINAL_TIMEOUT", 300, min_value=1)  # seconds
    TERMINAL_MAX_SESSIONS = _get_int("TERMINAL_MAX_SESSIONS", 100, min_value=1)
    TERMINAL_ENCODING = os.getenv("TERMINAL_ENCODING", "utf-8")
    SESSION_REGISTRY_PATH = os.getenv("SESSION_REGISTRY_PATH", "output/session-registry.json")

    # Web Server Configuration
    WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
    WEB_PORT = _get_int("WEB_PORT", 8000, min_value=1, max_value=65535)
    WEB_SSL_CERT = os.getenv("WEB_SSL_CERT", "")
    WEB_SSL_KEY = os.getenv("WEB_SSL_KEY", "")

    # Security Configuration
    AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
    ALLOWED_COMMANDS_ONLY = os.getenv("ALLOWED_COMMANDS_ONLY", "false").lower() == "true"
    ALLOWED_COMMANDS_FILE = os.getenv("ALLOWED_COMMANDS_FILE", "")
    # Telegram user whitelist (comma-separated user IDs)
    ALLOWED_TELEGRAM_USERS = os.getenv("ALLOWED_TELEGRAM_USERS", "").strip()

    # Command filtering (lazily initialized)
    command_filter: Optional[CommandFilter] = None

    # AI Proxy Configuration
    AI_PROXY_ENABLED = os.getenv("AI_PROXY_ENABLED", "false").lower() == "true"
    AI_PROXY_PROVIDER = os.getenv("AI_PROXY_PROVIDER", "gemini-cli")  # gemini-cli, claude-cli
    AI_PROXY_SYSTEM_PROMPT = os.getenv("AI_PROXY_SYSTEM_PROMPT",
        "You are an intelligent terminal automation assistant. Your job is to analyze terminal prompts and provide appropriate responses.\n"
        "\n"
        "CORE PRINCIPLES:\n"
        "- Analyze the terminal screen carefully to understand what input is needed\n"
        "- Provide ONLY the exact text to type (no explanations or formatting)\n"
        "- Choose the most logical and safe option when multiple choices exist\n"
        "- Default to non-destructive actions when uncertain\n"
        "\n"
        "RESPONSE PATTERNS:\n"
        "- Numbered menus: Select the most appropriate option number\n"
        "- Yes/No questions: Choose based on context and safety\n"
        "- Text input: Provide brief, relevant responses\n"
        "- File operations: Use safe, standard paths and names\n"
        "- Confirmations: Generally confirm unless clearly destructive\n"
        "\n"
        "OUTPUT FORMAT: Your entire response becomes terminal input exactly as typed.")
    AI_PROXY_MAX_ITERATIONS = _get_int("AI_PROXY_MAX_ITERATIONS", 50, min_value=1)
    
    # AI Proxy Buffer and Context Configuration
    AI_PROXY_BUFFER_SIZE = _get_int("AI_PROXY_BUFFER_SIZE", 1000, min_value=100)
    AI_PROXY_CONTEXT_LINES = _get_int("AI_PROXY_CONTEXT_LINES", 500, min_value=50)
    AI_PROXY_MAX_CONTEXT_SIZE = _get_int("AI_PROXY_MAX_CONTEXT_SIZE", 5000, min_value=1000)
    
    # LLM Provider Timeouts
    LLM_TIMEOUT_SECONDS = _get_int("LLM_TIMEOUT_SECONDS", 90, min_value=10)

    # Claude Code auto-continue
    CLAUDE_CODE_AUTO_CONTINUE_GRACE_SECONDS = _get_float(
        "CLAUDE_CODE_AUTO_CONTINUE_GRACE_SECONDS",
        15.0,
        min_value=0.0,
    )
    CLAUDE_CODE_CCUSAGE_TIMEOUT_SECONDS = _get_float(
        "CLAUDE_CODE_CCUSAGE_TIMEOUT_SECONDS",
        15.0,
        min_value=1.0,
    )
    TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS = _get_float(
        "TELEGRAM_COMMAND_INITIAL_OUTPUT_TIMEOUT_SECONDS",
        3.0,
        min_value=0.01,
    )
    TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS = _get_float(
        "TELEGRAM_COMMAND_FOLLOW_UP_OUTPUT_TIMEOUT_SECONDS",
        0.25,
        min_value=0.001,
    )

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if cls.TELEGRAM_WEBHOOK_URL and not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required when TELEGRAM_WEBHOOK_URL is set")

        # Create log directory if needed
        if cls.LOG_OUTPUT in ("file", "both"):
            Path(cls.LOG_FILE_DIR).mkdir(parents=True, exist_ok=True)

        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if cls.LOG_LEVEL not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL: {cls.LOG_LEVEL}. Must be one of {valid_levels}")

        # Validate log output
        valid_outputs = {"console", "file", "both"}
        if cls.LOG_OUTPUT not in valid_outputs:
            raise ValueError(f"Invalid LOG_OUTPUT: {cls.LOG_OUTPUT}. Must be one of {valid_outputs}")

        # Validate log file mode
        valid_modes = {"append", "new_each_start", "timestamp_rotate"}
        if cls.LOG_FILE_MODE not in valid_modes:
            raise ValueError(f"Invalid LOG_FILE_MODE: {cls.LOG_FILE_MODE}. Must be one of {valid_modes}")

        # Validate rotation interval
        valid_intervals = {"1d", "1w", "1m"}
        if cls.LOG_ROTATION_INTERVAL not in valid_intervals:
            raise ValueError(f"Invalid LOG_ROTATION_INTERVAL: {cls.LOG_ROTATION_INTERVAL}. Must be one of {valid_intervals}")

        # Validate write position
        valid_positions = {"top", "bottom"}
        if cls.LOG_WRITE_POSITION not in valid_positions:
            raise ValueError(f"Invalid LOG_WRITE_POSITION: {cls.LOG_WRITE_POSITION}. Must be one of {valid_positions}")

        # Validate SSL configuration
        if cls.WEB_SSL_CERT and not cls.WEB_SSL_KEY:
            raise ValueError("WEB_SSL_KEY required if WEB_SSL_CERT is set")
        if cls.WEB_SSL_KEY and not cls.WEB_SSL_CERT:
            raise ValueError("WEB_SSL_CERT required if WEB_SSL_KEY is set")

        # Verify SSL files exist if specified
        if cls.WEB_SSL_CERT:
            if not Path(cls.WEB_SSL_CERT).exists():
                raise ValueError(f"SSL certificate file not found: {cls.WEB_SSL_CERT}")
        if cls.WEB_SSL_KEY:
            if not Path(cls.WEB_SSL_KEY).exists():
                raise ValueError(f"SSL key file not found: {cls.WEB_SSL_KEY}")

        # Initialize command filter
        logger = logging.getLogger(__name__)
        if cls.ALLOWED_COMMANDS_ONLY:
            if not cls.ALLOWED_COMMANDS_FILE:
                raise ValueError("ALLOWED_COMMANDS_FILE required when ALLOWED_COMMANDS_ONLY is true")
            cls.command_filter = CommandFilter(True, cls.ALLOWED_COMMANDS_FILE)
            logger.info(f"Command filtering enabled: {cls.command_filter.get_status()['num_allowed']} allowed commands")
        else:
            cls.command_filter = CommandFilter(False, "")
            logger.info("Command filtering disabled (all commands allowed)")

    @classmethod
    def get_log_level(cls):
        """Get logging level object"""
        return getattr(logging, cls.LOG_LEVEL)
