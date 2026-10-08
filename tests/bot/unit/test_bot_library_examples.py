import contextlib
import io
import pkgutil
import re
from dataclasses import dataclass

import pytest

import rtt.library
from rtt.bot.prompt import PROMPTS_DIR

EXAMPLES = (PROMPTS_DIR / "library_examples.md").read_text(encoding="utf-8")
_FLOAT_RE = re.compile(r"-?\d+\.\d+")


@dataclass(frozen=True)
class Example:
    module: str
    description: str
    code: str
    output: str


def _fenced_blocks(lines, start):
    blocks = []
    index = start
    while index < len(lines) and not lines[index].startswith("#"):
        if lines[index].startswith("```"):
            end = lines.index("```", index + 1)
            blocks.append("\n".join(lines[index + 1 : end]))
            index = end
        index += 1
    return blocks, index


def _examples():
    lines = EXAMPLES.splitlines()
    examples, module, index = [], "", 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            module = line[3:]
        if line.startswith("### "):
            blocks, index = _fenced_blocks(lines, index + 1)
            examples.append(Example(module, line[4:], blocks[0], blocks[1]))
            continue
        index += 1
    return examples


def _run(code):
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exec(compile(code, "<library example>", "exec"), {"__name__": "__main__"})
    return captured.getvalue()


def _normalized(text):
    rounded = _FLOAT_RE.sub(lambda m: f"{float(m.group()):.2f}", text)
    return " ".join(rounded.split())


class TestLibraryExamples:
    @pytest.mark.parametrize("example", _examples(), ids=lambda e: f"{e.module}: {e.description[:50]}")
    def test_each_example_still_prints_its_recorded_output(self, example):
        assert _normalized(_run(example.code)) == _normalized(example.output)

    def test_every_library_module_has_at_least_one_example(self):
        covered = {example.module for example in _examples()}
        modules = {f"rtt.library.{info.name}" for info in pkgutil.iter_modules(rtt.library.__path__)}
        assert modules <= covered, sorted(modules - covered)
