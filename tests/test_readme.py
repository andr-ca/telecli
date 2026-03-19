"""Tests for README accuracy."""

from pathlib import Path


def test_readme_lists_python_3_10_as_minimum_version():
    """The documented Python floor should match the 3.10+ syntax used in the codebase."""
    readme = Path(__file__).resolve().parents[1] / "README.md"

    assert "- Python 3.10 or higher" in readme.read_text(encoding="utf-8")
