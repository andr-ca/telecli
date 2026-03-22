"""Regression tests for the code-quality workflow security grep checks."""

from pathlib import Path
import re
import subprocess


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "code-quality.yml"
SQL_INJECTION_PATTERN = r"(^|[^[:alnum:]_])(execute|query)[[:space:]]*\([^#]*['\"][^'\"]*['\"][[:space:]]*%"
# Adapt the workflow's POSIX-style pattern for Python's `re` engine.
SQL_INJECTION_PATTERN_PYTHON = (
    SQL_INJECTION_PATTERN.replace("[:alnum:]", "A-Za-z0-9").replace("[:space:]", r"\s")
)


def _read_workflow() -> str:
    """Read the workflow file using the repository's declared UTF-8 encoding."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _run_sql_injection_check(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Pure-Python equivalent of the workflow's recursive grep for SQL injection patterns."""
    regex = re.compile(SQL_INJECTION_PATTERN_PYTHON, re.MULTILINE)
    matched_files: list[str] = []

    for path in sorted(tmp_path.rglob("*.py")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        if regex.search(content):
            matched_files.append(str(path))

    stdout = ""
    if matched_files:
        stdout = "\n".join(matched_files) + "\n"

    return subprocess.CompletedProcess(
        args=["python-sql-injection-check", str(tmp_path)],
        returncode=0 if matched_files else 1,
        stdout=stdout,
        stderr="",
    )


def test_workflow_sql_injection_pattern_stays_in_sync():
    """The tested regex should match the workflow's SQL-injection grep."""
    workflow = _read_workflow()

    assert SQL_INJECTION_PATTERN in workflow


def test_read_workflow_uses_utf8_encoding(monkeypatch):
    """Workflow reads should pin UTF-8 because the file contains non-ASCII text."""
    observed = {}

    class FakeWorkflowPath:
        def read_text(self, *, encoding=None):
            observed["encoding"] = encoding
            return SQL_INJECTION_PATTERN

    monkeypatch.setattr("tests.test_code_quality_workflow.WORKFLOW_PATH", FakeWorkflowPath())

    workflow = _read_workflow()

    assert workflow == SQL_INJECTION_PATTERN
    assert observed["encoding"] == "utf-8"


def test_workflow_sql_injection_pattern_avoids_newline_escape_in_grep_character_class():
    """The grep regex should stay line-based and avoid `\\n` inside bracket expressions."""
    assert r"[^#\n]*" not in SQL_INJECTION_PATTERN
    assert r"[^#]*" in SQL_INJECTION_PATTERN


def test_sql_injection_check_ignores_percent_style_logging(tmp_path: Path):
    """Percent-style logging should not be mistaken for a database execute/query call."""
    (tmp_path / "logging_sample.py").write_text(
        'logger.info("User %s executed command in session %s (len=%s)", user_id, session_id, len(text))\n'
    )

    result = _run_sql_injection_check(tmp_path)

    assert result.returncode == 1


def test_sql_injection_check_ignores_parameterized_queries(tmp_path: Path):
    """DB-API parameter placeholders should not look like Python string interpolation."""
    (tmp_path / "safe_query.py").write_text(
        'cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))\n'
    )

    result = _run_sql_injection_check(tmp_path)

    assert result.returncode == 1


def test_sql_injection_check_detects_string_interpolation_in_execute(tmp_path: Path):
    """String interpolation inside execute(...) should still fail the workflow."""
    (tmp_path / "unsafe_query.py").write_text(
        'cursor.execute("SELECT * FROM users WHERE name = \'%s\'" % user_input)\n'
    )

    result = _run_sql_injection_check(tmp_path)

    assert result.returncode == 0
    assert "unsafe_query.py" in result.stdout


def test_sql_injection_check_does_not_require_system_grep(tmp_path: Path, monkeypatch):
    """The helper should stay portable and not depend on an external grep binary."""
    (tmp_path / "unsafe_query.py").write_text(
        'cursor.execute("SELECT * FROM users WHERE name = \'%s\'" % user_input)\n'
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run should not be used")

    monkeypatch.setattr(subprocess, "run", fail_if_called)

    result = _run_sql_injection_check(tmp_path)

    assert result.returncode == 0
    assert "unsafe_query.py" in result.stdout
