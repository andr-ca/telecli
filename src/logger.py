"""
Advanced logging system with multiple rotation strategies
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from src.config import Config


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom rotating file handler with top/bottom write support"""

    def emit(self, record):
        """Emit a record, supporting top/bottom write positions"""
        try:
            msg = self.format(record)
            if Config.LOG_WRITE_POSITION == "bottom":
                # Standard behavior - append
                with self._lock:
                    if self.stream is None:
                        self.stream = self._open()
                    self.stream.write(msg + self.terminator)
                    self.flush()
            else:
                # Top - insert at beginning (requires full rewrite)
                with self._lock:
                    # Read existing content
                    if self.stream is not None:
                        self.stream.close()
                    
                    file_path = self.baseFilename
                    existing_content = ""
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            existing_content = f.read()
                    
                    # Write new content at top
                    with open(file_path, "w") as f:
                        f.write(msg + self.terminator + existing_content)
                    
                    self.stream = self._open()
        except Exception:
            self.handleError(record)


class TimestampRotatingHandler(logging.Handler):
    """Handler that rotates logs based on timestamp intervals (1d, 1w, 1m)"""

    def __init__(self, log_dir: str, log_name: str, interval: str):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_name = log_name
        self.interval = interval
        self.current_file = None
        self.last_rotation = None
        self._setup_next_file()

    def _get_interval_seconds(self) -> int:
        """Convert interval string to seconds"""
        if self.interval == "1d":
            return 86400  # 24 hours
        elif self.interval == "1w":
            return 604800  # 7 days
        elif self.interval == "1m":
            return 2592000  # 30 days
        return 86400

    def _should_rotate(self) -> bool:
        """Check if rotation is needed"""
        if self.last_rotation is None:
            return False
        return datetime.now() >= self.last_rotation + timedelta(seconds=self._get_interval_seconds())

    def _setup_next_file(self):
        """Setup next log file with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.current_file = self.log_dir / f"{self.log_name}-{timestamp}.log"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.last_rotation = datetime.now()

    def emit(self, record):
        """Emit a record"""
        if self._should_rotate():
            self._setup_next_file()

        try:
            msg = self.format(record)
            position = Config.LOG_WRITE_POSITION

            if position == "bottom":
                with open(self.current_file, "a") as f:
                    f.write(msg + "\n")
            else:
                # Top - insert at beginning
                existing_content = ""
                if self.current_file.exists():
                    with open(self.current_file, "r") as f:
                        existing_content = f.read()

                with open(self.current_file, "w") as f:
                    f.write(msg + "\n" + existing_content)
        except Exception:
            self.handleError(record)


class AppendFileHandler(logging.FileHandler):
    """Simple append-only file handler with optional top write"""

    def emit(self, record):
        """Emit a record"""
        try:
            msg = self.format(record)
            if Config.LOG_WRITE_POSITION == "bottom":
                with self._lock:
                    if self.stream is None:
                        self.stream = self._open()
                    self.stream.write(msg + self.terminator)
                    self.flush()
            else:
                # Top - insert at beginning
                with self._lock:
                    file_path = self.baseFilename
                    existing_content = ""
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            existing_content = f.read()

                    with open(file_path, "w") as f:
                        f.write(msg + self.terminator + existing_content)
        except Exception:
            self.handleError(record)


class NewEachStartHandler(logging.FileHandler):
    """Handler that creates new file on app start"""

    def __init__(self, log_dir: str, log_name: str):
        self.log_dir = Path(log_dir)
        self.log_name = log_name
        self._rotate_on_start()
        
        log_file = self.log_dir / f"{log_name}.log"
        super().__init__(log_file)

    def _rotate_on_start(self):
        """Rotate existing log file on app start"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        current_file = self.log_dir / f"{self.log_name}.log"

        if current_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            rotated_file = self.log_dir / f"{self.log_name}-{timestamp}.log"
            current_file.rename(rotated_file)

    def emit(self, record):
        """Emit a record"""
        try:
            msg = self.format(record)
            if Config.LOG_WRITE_POSITION == "bottom":
                with self._lock:
                    if self.stream is None:
                        self.stream = self._open()
                    self.stream.write(msg + self.terminator)
                    self.flush()
            else:
                # Top - insert at beginning
                with self._lock:
                    file_path = self.baseFilename
                    existing_content = ""
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            existing_content = f.read()

                    with open(file_path, "w") as f:
                        f.write(msg + self.terminator + existing_content)
        except Exception:
            self.handleError(record)


def cleanup_log_directory():
    """Clean up log directory when it exceeds max size"""
    log_dir = Path(Config.LOG_FILE_DIR)
    if not log_dir.exists():
        return

    max_size_bytes = Config.LOG_DIR_MAX_SIZE * 1024 * 1024
    total_size = sum(f.stat().st_size for f in log_dir.glob("*") if f.is_file())

    if total_size > max_size_bytes:
        # Get all log files sorted by creation time (oldest first)
        log_files = sorted(
            log_dir.glob("*.log"),
            key=lambda x: x.stat().st_ctime,
        )

        # Delete oldest files until under limit
        for log_file in log_files:
            if total_size <= max_size_bytes:
                break
            file_size = log_file.stat().st_size
            log_file.unlink()
            total_size -= file_size


def setup_logging():
    """Setup logging based on configuration"""
    # Create formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(Config.get_log_level())

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    if Config.LOG_OUTPUT in ("console", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(Config.get_log_level())
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if Config.LOG_OUTPUT in ("file", "both"):
        cleanup_log_directory()

        if Config.LOG_FILE_MODE == "append":
            file_handler = AppendFileHandler(
                os.path.join(Config.LOG_FILE_DIR, f"{Config.LOG_FILE_NAME}.log")
            )
        elif Config.LOG_FILE_MODE == "new_each_start":
            file_handler = NewEachStartHandler(Config.LOG_FILE_DIR, Config.LOG_FILE_NAME)
        elif Config.LOG_FILE_MODE == "timestamp_rotate":
            file_handler = TimestampRotatingHandler(
                Config.LOG_FILE_DIR,
                Config.LOG_FILE_NAME,
                Config.LOG_ROTATION_INTERVAL
            )
        else:
            raise ValueError(f"Unknown log file mode: {Config.LOG_FILE_MODE}")

        file_handler.setLevel(Config.get_log_level())
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)
