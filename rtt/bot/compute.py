from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rtt.bot.tools import ToolError

_OUTPUT_CHARS = 20_000


def _capped(text: str) -> str:
    if len(text) <= _OUTPUT_CHARS:
        return text
    return text[:_OUTPUT_CHARS] + f"\n… output truncated at {_OUTPUT_CHARS} characters"


def _child_environment(repo_root: Path) -> dict[str, str]:
    kept = {key: value for key, value in os.environ.items() if not key.startswith("ANTHROPIC_")}
    return {**kept, "PYTHONPATH": str(repo_root)}


def _head(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace") as handle:
        return handle.read(_OUTPUT_CHARS + 1).strip()


def _run_capturing(code: str, repo_root: Path, timeout: float) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as scratch:
        out_path, err_path = Path(scratch, "stdout"), Path(scratch, "stderr")
        with out_path.open("wb") as out, err_path.open("wb") as err:
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=scratch,
                    env=_child_environment(repo_root),
                    stdout=out,
                    stderr=err,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ToolError(f"The snippet did not finish within {timeout:g} seconds.") from None
            except (ValueError, OSError) as error:
                raise ToolError(f"The snippet could not be started: {error}") from None
        return completed.returncode, _head(out_path), _head(err_path)


def run_rtt_python(code: str, repo_root: Path, timeout: float = 60.0) -> str:
    status, stdout, stderr = _run_capturing(code, repo_root, timeout)
    if status != 0:
        printed = _capped(stdout) + "\n" if stdout else ""
        raise ToolError(f"{printed}[the snippet exited with status {status}]\n{_capped(stderr)}")
    output = stdout + ("\n[stderr]\n" + stderr if stderr else "")
    return _capped(output) if output else "(the snippet printed nothing)"
