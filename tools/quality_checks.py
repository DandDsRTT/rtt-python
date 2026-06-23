from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50
MAX_EFFERENT_COUPLING = 18
MAX_LCOM4 = 10
MAX_DIT = 2
MAX_NOC = 3

FILE_LENGTH_EXEMPT = frozenset(
    {
        "rtt/app/tooltips.py",
        "rtt/app/page_assets.py",
    }
)

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


def is_file_length_exempt(path: str) -> bool:
    posix = Path(path).as_posix()
    return any(posix == name or posix.endswith("/" + name) for name in FILE_LENGTH_EXEMPT)


def file_length_violations(path: str, text: str) -> list[Violation]:
    if is_file_length_exempt(path):
        return []
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


def module_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _from_prefix(mod: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    owner = mod.split(".")
    base = owner[: -node.level] if node.level <= len(owner) else []
    return ".".join(base + ([node.module] if node.module else []))


def _import_targets(mod: str, node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        prefix = _from_prefix(mod, node)
        return {prefix, *(f"{prefix}.{alias.name}" for alias in node.names)}
    return set()


def _resolve_internal(target: str, internal: set[str]) -> str | None:
    best = None
    for candidate in internal:
        matches = target == candidate or target.startswith(candidate + ".")
        if matches and (best is None or len(candidate) > len(best)):
            best = candidate
    return best


def efferent_coupling(files: list[Path]) -> dict[str, set[str]]:
    internal = {module_name(path) for path in files}
    fanout: dict[str, set[str]] = {}
    for path in files:
        mod = module_name(path)
        deps = fanout.setdefault(mod, set())
        for node in ast.walk(ast.parse(path.read_text())):
            for target in _import_targets(mod, node):
                hit = _resolve_internal(target, internal)
                if hit and hit != mod:
                    deps.add(hit)
    return fanout


def coupling_violations(files: list[Path]) -> list[Violation]:
    fanout = efferent_coupling(files)
    return [
        Violation(mod, 1, f"efferent coupling {len(deps)} (max {MAX_EFFERENT_COUPLING})")
        for mod, deps in sorted(fanout.items())
        if len(deps) > MAX_EFFERENT_COUPLING
    ]


def _self_attrs(method: ast.AST) -> set[str]:
    return {
        node.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


def _find(parent: dict[str, str], item: str) -> str:
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


def _cohesive(a: str, b: str, refs: dict[str, set[str]], names: set[str]) -> bool:
    shared = (refs[a] - names) & (refs[b] - names)
    return bool(shared) or b in refs[a] or a in refs[b]


def lcom4(cls: ast.ClassDef) -> int:
    methods = [node.name for node in cls.body if isinstance(node, _DEFINITION)]
    if len(methods) < 2:
        return 1
    names = set(methods)
    refs = {node.name: _self_attrs(node) for node in cls.body if isinstance(node, _DEFINITION)}
    parent = {name: name for name in methods}
    for index, left in enumerate(methods):
        for right in methods[index + 1 :]:
            if _cohesive(left, right, refs, names):
                parent[_find(parent, left)] = _find(parent, right)
    return len({_find(parent, name) for name in methods})


def cohesion_violations(files: list[Path]) -> list[Violation]:
    found = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            score = lcom4(node) if isinstance(node, ast.ClassDef) else 1
            if score > MAX_LCOM4:
                found.append(
                    Violation(
                        str(path), node.lineno, f"{node.name} LCOM4 {score} (max {MAX_LCOM4})"
                    )
                )
    return found


def class_bases(files: list[Path]) -> tuple[dict[str, list[str]], dict[str, tuple[str, int]]]:
    bases: dict[str, list[str]] = {}
    where: dict[str, tuple[str, int]] = {}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, []).extend(
                    base.id for base in node.bases if isinstance(base, ast.Name)
                )
                where.setdefault(node.name, (str(path), node.lineno))
    return bases, where


def depth_of_inheritance(
    name: str, bases: dict[str, list[str]], seen: frozenset[str] = frozenset()
) -> int:
    if name in seen:
        return 0
    deeper = seen | {name}
    return max(
        (
            1 + depth_of_inheritance(base, bases, deeper)
            for base in bases.get(name, [])
            if base in bases
        ),
        default=0,
    )


def number_of_children(bases: dict[str, list[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for parents in bases.values():
        for base in parents:
            if base in bases:
                counts[base] = counts.get(base, 0) + 1
    return counts


def inheritance_violations(files: list[Path]) -> list[Violation]:
    bases, where = class_bases(files)
    children = number_of_children(bases)
    found = []
    for name, (path, line) in where.items():
        depth = depth_of_inheritance(name, bases)
        if depth > MAX_DIT:
            found.append(Violation(path, line, f"{name} DIT {depth} (max {MAX_DIT})"))
        if children.get(name, 0) > MAX_NOC:
            found.append(Violation(path, line, f"{name} NOC {children[name]} (max {MAX_NOC})"))
    return found


def collect(roots: tuple[str, ...]) -> list[Violation]:
    files = python_files(roots)
    return [
        *(v for path in files for v in file_violations(path)),
        *coupling_violations(files),
        *cohesion_violations(files),
        *inheritance_violations(files),
    ]


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
