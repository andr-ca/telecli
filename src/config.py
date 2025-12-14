"""
Configuration management - loads from .env with sensible defaults
"""
import logging
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
load_dotenv()


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
    LOG_FILE_MAX_SIZE = int(os.getenv("LOG_FILE_MAX_SIZE", 100))  # MB
    LOG_DIR_MAX_SIZE = int(os.getenv("LOG_DIR_MAX_SIZE", 1000))  # MB
    LOG_ROTATION_INTERVAL = os.getenv("LOG_ROTATION_INTERVAL", "1d").lower()  # 1d, 1w, 1m
    LOG_WRITE_POSITION = os.getenv("LOG_WRITE_POSITION", "bottom").lower()  # top, bottom

    # Terminal Configuration
    TERMINAL_SHELL = os.getenv("TERMINAL_SHELL", "bash")
    TERMINAL_TIMEOUT = int(os.getenv("TERMINAL_TIMEOUT", 300))  # seconds
    TERMINAL_MAX_SESSIONS = int(os.getenv("TERMINAL_MAX_SESSIONS", 100))
    TERMINAL_ENCODING = os.getenv("TERMINAL_ENCODING", "utf-8")

    # Web Server Configuration
    WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
    WEB_PORT = int(os.getenv("WEB_PORT", 8000))
    WEB_SSL_CERT = os.getenv("WEB_SSL_CERT", "")
    WEB_SSL_KEY = os.getenv("WEB_SSL_KEY", "")

    # Security Configuration
    AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
    ALLOWED_COMMANDS_ONLY = os.getenv("ALLOWED_COMMANDS_ONLY", "false").lower() == "true"
    ALLOWED_COMMANDS_FILE = os.getenv("ALLOWED_COMMANDS_FILE", "")

    # AI Proxy Configuration
    AI_PROXY_ENABLED = os.getenv("AI_PROXY_ENABLED", "false").lower() == "true"
    AI_PROXY_PROVIDER = os.getenv("AI_PROXY_PROVIDER", "gemini-cli")  # gemini-cli, claude-cli
    AI_PROXY_SYSTEM_PROMPT = os.getenv("AI_PROXY_SYSTEM_PROMPT", 
        "You are automating terminal input. CRITICAL RULES:\n"
        "1. For numbered menus (e.g. '1. Yes', '2. No'), respond with ONLY the number: 1\n"
        "2. For yes/no prompts, respond with ONLY: y or n\n"
        "3. For text input prompts, provide a brief, relevant answer\n"
        "4. NEVER explain your choice\n"
        "5. NEVER add extra text, punctuation, or formatting\n"
        "6. If you see multiple options, choose the first/default option (usually option 1 or Yes)")
    AI_PROXY_MAX_ITERATIONS = int(os.getenv("AI_PROXY_MAX_ITERATIONS", 10))

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required in .env")

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

    @classmethod
    def get_log_level(cls):
        """Get logging level object"""
        return getattr(logging, cls.LOG_LEVEL)
