"""Command filtering for security - prevent arbitrary command execution"""
import logging

logger = logging.getLogger(__name__)


class CommandFilter:
    """Validates commands against allowed list"""

    def __init__(self, allowed_only: bool, allowed_file: str):
        """
        Args:
            allowed_only: If True, only allow listed commands
            allowed_file: Path to file with allowed commands (one per line)
        """
        self.allowed_only = allowed_only
        self.allowed_commands = set()

        if allowed_only and allowed_file:
            self._load_allowed_commands(allowed_file)

    def _load_allowed_commands(self, filepath: str) -> None:
        """Load allowed commands from file"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        self.allowed_commands.add(line)

            logger.info(f"Loaded {len(self.allowed_commands)} allowed commands from {filepath}")
        except FileNotFoundError:
            logger.error(f"Allowed commands file not found: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Error loading allowed commands: {e}")
            raise

    def is_allowed(self, command: str) -> bool:
        """
        Check if command is allowed

        Args:
            command: Full command string (e.g., "ls -la /tmp")

        Returns:
            True if command is allowed, False otherwise
        """
        # If filtering disabled, allow everything
        if not self.allowed_only:
            return True

        # Extract command name (first word)
        command = command.strip()
        if not command:
            return False

        parts = command.split()
        if not parts:
            return False
        cmd_name = parts[0]

        # Check if command is in allowed list
        is_allowed = cmd_name in self.allowed_commands

        if not is_allowed:
            logger.warning(f"Command not allowed: {cmd_name} (from: {command[:50]})")

        return is_allowed

    def get_status(self) -> dict:
        """Get filter status for logging/debugging"""
        return {
            "enabled": self.allowed_only,
            "num_allowed": len(self.allowed_commands),
            "allowed_commands": sorted(list(self.allowed_commands))
        }
