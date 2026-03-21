"""Regression tests for the code-quality workflow security grep checks."""

from pathlib import Path
import subprocess


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "code-quality.yml"
SQL_INJECTION_PATTERN = r"(^|[^[:alnum:]_])(execute|query)[[:space:]]*\([^#\n]*['\"][^'\"]*['\"][[:space:]]*%"


def _run_sql_injection_check(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "grep",
            "-rE",
            SQL_INJECTION_PATTERN,
            str(tmp_path),
            "--include=*.py",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_workflow_sql_injection_pattern_stays_in_sync():
    """The tested regex should match the workflow's SQL-injection grep."""
    workflow = WORKFLOW_PATH.read_text()

    assert SQL_INJECTION_PATTERN in workflow


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
