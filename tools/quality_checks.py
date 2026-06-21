from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50

_DEFAULT_ROOTS = ("rtt", "tools")
_DEFINITION = (ast.FunctionDef, ast.AsyncFunctionDef)
_DOCSTRING_OWNER = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def line_count(text: str) -> int:
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def span(node: ast.AST) -> int:
    return node.end_lineno - node.lineno + 1


def file_length_violations(path: str, text: str) -> list[Violation]:
    lines = line_count(text)
    if lines <= MAX_FILE_LINES:
        return []
    return [Violation(path, 1, f"file is {lines} lines (max {MAX_FILE_LINES})")]


def function_length_violations(path: str, tree: ast.AST) -> list[Violation]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, _DEFINITION) and span(node) > MAX_FUNCTION_LINES:
            found.append(
                Violation(
                    path,
                    node.lineno,
                    f"{node.name} is {span(node)} lines (max {MAX_FUNCTION_LINES})",
                )
            )
    return found


def docstring_violations(path: str, tree: ast.AST) -> list[Violation]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_OWNER) and ast.get_docstring(node) is not None:
            found.append(Violation(path, getattr(node, "lineno", 1), "docstring is banned"))
    return found


def file_violations(path: Path) -> list[Violation]:
    text = path.read_text()
    name = str(path)
    tree = ast.parse(text, filename=name)
    return [
        *file_length_violations(name, text),
        *function_length_violations(name, tree),
        *docstring_violations(name, tree),
    ]


def python_files(roots: tuple[str, ...]) -> list[Path]:
    return sorted(path for root in roots for path in Path(root).rglob("*.py"))


def collect(roots: tuple[str, ...]) -> list[Violation]:
    return [v for path in python_files(roots) for v in file_violations(path)]


def main(argv: list[str]) -> int:
    roots = tuple(argv[1:]) or _DEFAULT_ROOTS
    violations = collect(roots)
    for violation in violations:
        print(violation.render())
    if violations:
        print(f"\n{len(violations)} structural quality violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
