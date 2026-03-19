"""Tests for the development launcher script."""

from pathlib import Path
import os
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_run_web_script_starts_main_entrypoint(tmp_path):
    """The launcher should delegate to the combined application entrypoint."""
    script_path = tmp_path / "run_web.sh"
    script_path.write_text((REPO_ROOT / "run_web.sh").read_text(encoding="utf-8"), encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | 0o111)

    (tmp_path / ".env").write_text("AUTH_TOKEN=test-token\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")

    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)

    _write_executable(
        venv_bin / "activate",
        f"#!/bin/sh\nexport VIRTUAL_ENV='{tmp_path / 'venv'}'\nexport PATH=\"$VIRTUAL_ENV/bin\"\n",
    )
    _write_executable(
        venv_bin / "pip",
        "#!/bin/sh\nexit 0\n",
    )
    _write_executable(
        venv_bin / "python",
        (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > '{tmp_path / 'python-args.txt'}'\n"
            "exit 0\n"
        ),
    )

    completed = subprocess.run(
        ["/bin/bash", str(script_path)],
        cwd=tmp_path,
        env={**os.environ, "PATH": str(venv_bin)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "python-args.txt").read_text(encoding="utf-8").splitlines() == ["-m", "src.main"]


def test_run_web_script_uses_parent_env_file_for_worktree(tmp_path):
    """A worktree launcher should accept a shared .env from a parent checkout."""
    worktree = tmp_path / "repo" / ".worktrees" / "telegram-session-controls"
    worktree.mkdir(parents=True)

    script_path = worktree / "run_web.sh"
    script_path.write_text((REPO_ROOT / "run_web.sh").read_text(encoding="utf-8"), encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | 0o111)

    (tmp_path / "repo" / ".env").write_text("AUTH_TOKEN=test-token\n", encoding="utf-8")
    (worktree / "requirements.txt").write_text("", encoding="utf-8")

    venv_bin = worktree / "venv" / "bin"
    venv_bin.mkdir(parents=True)

    _write_executable(
        venv_bin / "activate",
        f"#!/bin/sh\nexport VIRTUAL_ENV='{worktree / 'venv'}'\nexport PATH=\"$VIRTUAL_ENV/bin\"\n",
    )
    _write_executable(
        venv_bin / "pip",
        "#!/bin/sh\nexit 0\n",
    )
    _write_executable(
        venv_bin / "python",
        (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > '{worktree / 'python-args.txt'}'\n"
            "exit 0\n"
        ),
    )

    completed = subprocess.run(
        ["/bin/bash", str(script_path)],
        cwd=worktree,
        env={**os.environ, "PATH": str(venv_bin)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (worktree / "python-args.txt").read_text(encoding="utf-8").splitlines() == ["-m", "src.main"]


def test_run_web_script_execs_python_entrypoint(tmp_path):
    """The launcher should replace the shell with the Python process so Ctrl+C stops the service cleanly."""
    script_path = tmp_path / "run_web.sh"
    script_path.write_text((REPO_ROOT / "run_web.sh").read_text(encoding="utf-8"), encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | 0o111)

    (tmp_path / ".env").write_text("AUTH_TOKEN=test-token\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")

    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)

    _write_executable(
        venv_bin / "activate",
        f"#!/bin/sh\nexport VIRTUAL_ENV='{tmp_path / 'venv'}'\nexport PATH=\"$VIRTUAL_ENV/bin:/usr/bin:/bin\"\n",
    )
    _write_executable(venv_bin / "pip", "#!/bin/sh\nexit 0\n")
    _write_executable(
        venv_bin / "python",
        (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > '{tmp_path / 'python-args.txt'}'\n"
            "sleep 30\n"
        ),
    )

    process = subprocess.Popen(
        ["/bin/bash", str(script_path)],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{venv_bin}:/usr/bin:/bin"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        subprocess.run(["/bin/sleep", "0.2"], check=True)
        process_info = subprocess.run(
            ["ps", "-o", "command=", "-p", str(process.pid)],
            capture_output=True,
            text=True,
            check=True,
        )

        assert "run_web.sh" not in process_info.stdout
        assert (tmp_path / "python-args.txt").read_text(encoding="utf-8").splitlines() == ["-m", "src.main"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
