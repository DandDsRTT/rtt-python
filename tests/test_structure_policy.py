import ast
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_TEST_FILES = sorted(_TESTS.rglob("test_*.py"))
MAX_LINES = 800
MAX_TESTS_PER_CLASS = 30


def _rel(path):
    return path.relative_to(_TESTS).as_posix()


def _module_level_tests(tree):
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]


def _class_test_counts(tree):
    counts = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            counts[node.name] = sum(
                1 for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test_")
            )
    return counts


class TestStructurePolicy:
    @pytest.mark.parametrize("path", _TEST_FILES, ids=_rel)
    def test_every_test_lives_in_a_class(self, path):
        offenders = _module_level_tests(ast.parse(path.read_text(encoding="utf-8")))
        assert not offenders, (
            f"{_rel(path)} has {len(offenders)} module-level test function(s): {offenders[:3]}. "
            "Every test must live in a class Test... so the suite reads as named, navigable groups "
            "of behaviour (CLAUDE.md). Wrap them in a class."
        )

    @pytest.mark.parametrize("path", _TEST_FILES, ids=_rel)
    def test_test_file_stays_under_the_line_cap(self, path):
        n = len(path.read_text(encoding="utf-8").splitlines())
        assert n <= MAX_LINES, (
            f"{_rel(path)} is {n} lines, over the {MAX_LINES}-line cap. Split it into smaller feature "
            "files (one concern each) so a reader can hold a whole file in their head (CLAUDE.md)."
        )

    @pytest.mark.parametrize("path", _TEST_FILES, ids=_rel)
    def test_no_class_exceeds_the_test_cap(self, path):
        oversized = {c: n for c, n in _class_test_counts(ast.parse(path.read_text(encoding="utf-8"))).items()
                     if n > MAX_TESTS_PER_CLASS}
        assert not oversized, (
            f"{_rel(path)} has test class(es) over the {MAX_TESTS_PER_CLASS}-test cap: {oversized}. "
            "Split each into smaller, more specific class groups (CLAUDE.md)."
        )
