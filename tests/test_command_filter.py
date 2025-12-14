"""Tests for command filtering"""
import pytest
from src.command_filter import CommandFilter


def test_filter_allows_all_when_disabled():
    """When filter disabled, all commands allowed"""
    f = CommandFilter(allowed_only=False, allowed_file="")
    assert f.is_allowed("rm -rf /")
    assert f.is_allowed("dangerous-command")
    assert f.is_allowed("")


def test_filter_blocks_unlisted_when_enabled():
    """When filter enabled, only listed commands allowed"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls", "cat", "grep"}  # Manually set for test
    assert f.is_allowed("ls /tmp")
    assert f.is_allowed("cat file.txt")
    assert not f.is_allowed("rm file.txt")
    assert not f.is_allowed("rm -rf /")


def test_filter_extracts_command_name():
    """Extract first word as command name"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"grep"}
    assert f.is_allowed("grep 'pattern' file.txt")
    assert not f.is_allowed("grep-recursive file.txt")  # Different command


def test_filter_handles_whitespace():
    """Handle leading/trailing whitespace"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls"}
    assert f.is_allowed("  ls  /tmp  ")
    assert f.is_allowed("ls")


def test_filter_loads_file():
    """Load allowed commands from file"""
    import tempfile
    import os

    # Create temp file with allowed commands
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("ls\ncat\ngrep\n")
        f.write("# Comments are ignored\n")
        f.write("\n")  # Empty lines
        f.write("  find  \n")  # With whitespace
        temp_file = f.name

    try:
        f = CommandFilter(allowed_only=True, allowed_file=temp_file)
        assert f.is_allowed("ls /tmp")
        assert f.is_allowed("cat file.txt")
        assert f.is_allowed("grep pattern file.txt")
        assert f.is_allowed("find /")
        assert not f.is_allowed("rm -rf /")
    finally:
        os.unlink(temp_file)


def test_filter_empty_command():
    """Handle empty command string"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls"}
    assert not f.is_allowed("")
    assert not f.is_allowed("   ")
