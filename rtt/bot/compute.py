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


def run_rtt_python(code: str, repo_root: Path, timeout: float = 60.0) -> str:
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    try:
        with tempfile.TemporaryDirectory() as scratch:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=scratch,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired:
        raise ToolError(f"The snippet did not finish within {timeout:g} seconds.") from None
    if completed.returncode != 0:
        raise ToolError(
            f"The snippet exited with status {completed.returncode}.\n"
            f"{_capped(completed.stderr.strip())}"
        )
    output = completed.stdout.rstrip("\n")
    if completed.stderr.strip():
        output += "\n[stderr]\n" + completed.stderr.strip()
    return _capped(output) if output else "(the snippet printed nothing)"
