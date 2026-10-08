from pathlib import Path

import pytest

from rtt.bot.compute import run_rtt_python
from rtt.bot.tools import ToolError

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestRunRttPython:
    def test_runs_the_snippet_with_the_library_importable_and_returns_stdout(self):
        code = (
            "from rtt.library.parsing import parse_temperament_data\n"
            "from rtt.library.dual import dual\n"
            "print(dual(parse_temperament_data('[⟨1 1 0] ⟨0 1 4]⧽')).matrix)"
        )
        assert run_rtt_python(code, REPO_ROOT) == "((4, -4, 1),)"

    def test_a_failing_snippet_raises_a_tool_error_carrying_the_traceback(self):
        with pytest.raises(ToolError, match="ZeroDivisionError"):
            run_rtt_python("1/0", REPO_ROOT)

    def test_a_snippet_that_overruns_the_timeout_raises_a_tool_error(self):
        with pytest.raises(ToolError, match="did not finish within 0.5 seconds"):
            run_rtt_python("import time; time.sleep(5)", REPO_ROOT, timeout=0.5)

    def test_a_silent_snippet_says_so_instead_of_returning_empty_text(self):
        assert run_rtt_python("x = 1", REPO_ROOT) == "(the snippet printed nothing)"

    def test_snippets_run_outside_the_repository_so_stray_writes_do_not_land_in_it(self):
        cwd = run_rtt_python("import os; print(os.getcwd())", REPO_ROOT)
        assert Path(cwd).resolve() != REPO_ROOT
        assert not Path(cwd).exists()
