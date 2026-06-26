from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from tools._quality_common import (
    Violation,
    line_count,
    module_name,
    parse_files,
    python_files,
    span,
)
from tools.quality_metrics import (
    bag_cross_file,
    class_surface,
    demeter_chains,
    explanatory_comment_blocks,
    is_reexport_facade,
    oversized_classes,
    reach_through_by_handle,
)
from tools.quality_ratchets import (
    BASELINE_PATH,
    bag_violations,
    class_surface_violations,
    comment_violations,
    demeter_violations,
    load_baseline,
    reach_through_violations,
)

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50
MAX_EFFERENT_COUPLING = 15
MAX_LCOM4 = 10
MAX_DIT = 2
MAX_NOC = 3
MAX_SPREADSHEET_SHARED_STATE = 2
COUPLING_BASELINE_FLOOR = 10

FILE_LENGTH_EXEMPT = frozenset(
    {
        "rtt/app/tooltips.py",
        "rtt/app/page_assets.py",
        "rtt/app/grid_tables.py",
    }
)

_DEFAULT_ROOTS = ("rtt", "tools")
_DEFINITION = (ast.FunctionDef, ast.AsyncFunctionDef)
_DOCSTRING_OWNER = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


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


def facade_modules(files: list[Path]) -> set[str]:
    return {
        module_name(path)
        for path in files
        if path.name == "__init__.py" and is_reexport_facade(ast.parse(path.read_text()))
    }


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


def logic_coupling(files: list[Path]) -> dict[str, int]:
    facades = facade_modules(files)
    return {mod: len(deps) for mod, deps in efferent_coupling(files).items() if mod not in facades}


def coupling_violations(files: list[Path]) -> list[Violation]:
    return [
        Violation(mod, 1, f"efferent coupling {fanout} (max {MAX_EFFERENT_COUPLING})")
        for mod, fanout in sorted(logic_coupling(files).items())
        if fanout > MAX_EFFERENT_COUPLING
    ]


def coupling_baseline(files: list[Path]) -> dict[str, int]:
    return {
        mod: fanout
        for mod, fanout in logic_coupling(files).items()
        if fanout >= COUPLING_BASELINE_FLOOR
    }


def coupling_ratchet_violations(files: list[Path], baseline: dict) -> list[Violation]:
    floors = baseline["coupling"]
    found = []
    for mod, fanout in sorted(logic_coupling(files).items()):
        floor = floors.get(mod)
        if floor is not None and fanout > floor:
            found.append(Violation(mod, 1, f"efferent coupling rose to {fanout} (floor {floor})"))
        elif floor is None and fanout >= COUPLING_BASELINE_FLOOR:
            found.append(
                Violation(mod, 1, f"new module at coupling {fanout}; baseline it or cut deps")
            )
    return found


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


def _cross_file_shared_self(paths: list[Path]) -> set[str]:
    writes: dict[str, set[str]] = {}
    reads: dict[str, set[str]] = {}
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
            ):
                bucket = writes if isinstance(node.ctx, ast.Store) else reads
                bucket.setdefault(node.attr, set()).add(path.name)
    return {
        attr
        for attr in set(writes) | set(reads)
        if writes.get(attr) and (reads.get(attr, set()) - writes.get(attr, set()))
    }


def _spreadsheet_cluster(files: list[Path]) -> list[Path]:
    return [p for p in files if p.name.startswith("spreadsheet") and p.suffix == ".py"]


def spreadsheet_shared_state_violations(files: list[Path]) -> list[Violation]:
    count = len(_cross_file_shared_self(_spreadsheet_cluster(files)))
    if count <= MAX_SPREADSHEET_SHARED_STATE:
        return []
    return [
        Violation(
            "rtt/app/spreadsheet*.py",
            1,
            f"cross-file shared mutable self {count} (max {MAX_SPREADSHEET_SHARED_STATE}) — "
            "the builder god-object is regrowing; pass frozen value objects, don't share self",
        )
    ]


def ratchet_violations(
    trees: list[tuple[Path, ast.Module]], files: list[Path], baseline: dict
) -> list[Violation]:
    return [
        *reach_through_violations(trees, baseline),
        *demeter_violations(trees, baseline),
        *bag_violations(trees, baseline),
        *class_surface_violations(trees, baseline),
        *comment_violations(files, baseline),
        *coupling_ratchet_violations(files, baseline),
    ]


def collect(roots: tuple[str, ...]) -> list[Violation]:
    files = python_files(roots)
    trees = parse_files(files)
    baseline = load_baseline()
    return [
        *(v for path in files for v in file_violations(path)),
        *coupling_violations(files),
        *cohesion_violations(files),
        *inheritance_violations(files),
        *spreadsheet_shared_state_violations(files),
        *ratchet_violations(trees, files, baseline),
    ]


def compute_baseline(files: list[Path]) -> dict:
    trees = parse_files(files)
    crossing, accumulators = bag_cross_file(trees)
    return {
        "reach_through_total": sum(reach_through_by_handle(trees).values()),
        "reach_through_by_handle": dict(reach_through_by_handle(trees).most_common()),
        "demeter_chains": sorted(demeter_chains(trees)),
        "bag_cross_file_total": len(crossing),
        "bag_cross_file_attrs": sorted(crossing),
        "bag_cross_file_accumulators": sorted(accumulators),
        "class_surface": dict(sorted(oversized_classes(class_surface(trees)).items())),
        "coupling": dict(sorted(coupling_baseline(files).items())),
        "explanatory_comment_blocks": sum(len(explanatory_comment_blocks(path)) for path in files),
    }


def write_baseline(roots: tuple[str, ...] = _DEFAULT_ROOTS) -> dict:
    data = compute_baseline(python_files(roots))
    BASELINE_PATH.write_text(json.dumps(data, indent=2) + "\n")
    return data


def worklist(roots: tuple[str, ...] = _DEFAULT_ROOTS) -> list[str]:
    live = compute_baseline(python_files(roots))
    base = load_baseline()
    lines = []
    for key in ("reach_through_total", "bag_cross_file_total", "explanatory_comment_blocks"):
        lines.append(f"{key}: {live[key]} (floor {base[key]})")
    lines.append(f"demeter_4hop_chains: {len(live['demeter_chains'])}")
    lines.append(f"oversized_classes: {len(live['class_surface'])}")
    lines.append(f"max_efferent_coupling: {max(live['coupling'].values(), default=0)}")
    return lines


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--update-baseline"]
    if "--update-baseline" in argv:
        write_baseline(tuple(args) or _DEFAULT_ROOTS)
        return 0
    roots = tuple(args) or _DEFAULT_ROOTS
    violations = collect(roots)
    for violation in violations:
        print(violation.render())
    if roots == _DEFAULT_ROOTS:
        print("\n-- ratchet worklist --")
        for line in worklist(roots):
            print(line)
    if violations:
        print(f"\n{len(violations)} structural quality violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
