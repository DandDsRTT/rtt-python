from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

DEFINITION = (ast.FunctionDef, ast.AsyncFunctionDef)


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


def python_files(roots: tuple[str, ...]) -> list[Path]:
    return sorted(path for root in roots for path in Path(root).rglob("*.py"))


def module_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_files(files: list[Path]) -> list[tuple[Path, ast.Module]]:
    return [(path, ast.parse(path.read_text(), filename=str(path))) for path in files]


def init_params(func: ast.AST) -> set[str]:
    args = func.args
    named = args.posonlyargs + args.args[1:] + args.kwonlyargs
    params = {arg.arg for arg in named}
    if args.vararg:
        params.add(args.vararg.arg)
    if args.kwarg:
        params.add(args.kwarg.arg)
    return params


def self_attr_targets(stmt: ast.AST) -> list[ast.Attribute]:
    targets = (
        stmt.targets
        if isinstance(stmt, ast.Assign)
        else ([stmt.target] if isinstance(stmt, ast.AnnAssign) else [])
    )
    return [
        tgt
        for tgt in targets
        if isinstance(tgt, ast.Attribute)
        and isinstance(tgt.value, ast.Name)
        and tgt.value.id == "self"
    ]
