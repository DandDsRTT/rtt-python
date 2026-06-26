from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import Counter
from pathlib import Path

from tools._quality_common import (
    DEFINITION,
    init_params,
    self_attr_targets,
)

PLATFORM_LIMITATION = re.compile(
    r"nicegui|quasar|\bvue\b|uvicorn|fastapi|browser|html5|\bcss\b|cpython|dnd",
    re.IGNORECASE,
)

CLASS_METHOD_FLOOR = 15
CLASS_ATTR_FLOOR = 10
HANDLE_CHAIN_FLOOR = 4


def _is_dunder_assign(node: ast.AST) -> bool:
    targets = (
        node.targets
        if isinstance(node, ast.Assign)
        else [node.target]
        if isinstance(node, ast.AnnAssign)
        else []
    )
    return bool(targets) and all(
        isinstance(t, ast.Name) and t.id.startswith("__") and t.id.endswith("__") for t in targets
    )


def is_reexport_facade(tree: ast.Module) -> bool:
    return all(
        isinstance(node, (ast.Import, ast.ImportFrom)) or _is_dunder_assign(node)
        for node in tree.body
    )


def injected_handle_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    names: set[str] = set()
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, DEFINITION) and node.name == "__init__":
                params = init_params(node)
                for stmt in ast.walk(node):
                    value = getattr(stmt, "value", None)
                    if isinstance(value, ast.Name) and value.id in params:
                        names |= {tgt.attr for tgt in self_attr_targets(stmt)}
    return names


def _self_chain(node: ast.Attribute) -> list[str] | None:
    hops: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        hops.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name) and cur.id == "self":
        return list(reversed(hops))
    return None


def _direct_handle(value: ast.AST, handles: set[str]) -> str | None:
    if (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "self"
        and value.attr in handles
    ):
        return value.attr
    return None


class _ReachCounter(ast.NodeVisitor):
    def __init__(self, handles: set[str]) -> None:
        self.handles = handles
        self.counts: Counter = Counter()
        self.scopes: list[dict[str, str]] = [{}]

    def visit_FunctionDef(self, node: ast.AST) -> None:
        self.scopes.append(dict(self.scopes[-1]))
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        handle = _direct_handle(node.value, self.handles)
        if handle and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self.scopes[-1][node.targets[0].id] = handle
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        handle = _direct_handle(node.value, self.handles)
        if handle is None and isinstance(node.value, ast.Name):
            handle = self.scopes[-1].get(node.value.id)
        if handle:
            self.counts[handle] += 1
        self.generic_visit(node)


def reach_through_by_handle(trees: list[tuple[Path, ast.Module]]) -> Counter:
    counter = _ReachCounter(injected_handle_names(trees))
    for _path, tree in trees:
        counter.visit(tree)
    return counter.counts


def _maximal_chains(rows: list[tuple[str, int, str]]) -> set[str]:
    by_spot: dict[tuple[str, int], list[str]] = {}
    for path, line, text in rows:
        by_spot.setdefault((path, line), []).append(text)
    out: set[str] = set()
    for (path, _line), texts in by_spot.items():
        for text in texts:
            if not any(other != text and other.startswith(text + ".") for other in texts):
                out.add(f"{path}::{text}")
    return out


def demeter_chains(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    handles = injected_handle_names(trees)
    rows: list[tuple[str, int, str]] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            chain = _self_chain(node)
            if chain and len(chain) >= HANDLE_CHAIN_FLOOR and chain[0] in handles:
                rows.append((path.as_posix(), node.lineno, "self." + ".".join(chain)))
    return _maximal_chains(rows)


def _constructs_namespace(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
        return False
    func = node.value.func
    return (isinstance(func, ast.Name) and func.id == "SimpleNamespace") or (
        isinstance(func, ast.Attribute) and func.attr == "SimpleNamespace"
    )


def bag_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    names: set[str] = set()
    for _path, tree in trees:
        for node in ast.walk(tree):
            if _constructs_namespace(node):
                names |= {tgt.id for tgt in node.targets if isinstance(tgt, ast.Name)}
    return names


def _bag_attr_io(
    trees: list[tuple[Path, ast.Module]], bags: set[str]
) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    writes: dict[tuple[str, str], set[str]] = {}
    reads: dict[tuple[str, str], set[str]] = {}
    for path, tree in trees:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in bags
            ):
                bucket = writes if isinstance(node.ctx, ast.Store) else reads
                bucket.setdefault((node.value.id, node.attr), set()).add(path.name)
    return writes, reads


def bag_cross_file(trees: list[tuple[Path, ast.Module]]) -> tuple[set[str], set[str]]:
    writes, reads = _bag_attr_io(trees, bag_names(trees))
    crossing = {
        key
        for key in set(writes) | set(reads)
        if writes.get(key) and (reads.get(key, set()) - writes.get(key, set()))
    }
    return {f"{bag}.{attr}" for bag, attr in crossing}, {bag for bag, _attr in crossing}


def _instance_attrs(cls: ast.ClassDef) -> set[str]:
    return {
        node.attr
        for node in ast.walk(cls)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and isinstance(node.ctx, ast.Store)
    }


def class_surface(trees: list[tuple[Path, ast.Module]]) -> dict[str, dict[str, int]]:
    surface: dict[str, dict[str, int]] = {}
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = sum(isinstance(m, DEFINITION) for m in node.body)
                surface[node.name] = {"methods": methods, "attrs": len(_instance_attrs(node))}
    return surface


def oversized_classes(surface: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {
        name: counts
        for name, counts in surface.items()
        if counts["methods"] > CLASS_METHOD_FLOOR or counts["attrs"] > CLASS_ATTR_FLOOR
    }


def _comment_blocks(src: str) -> list[list[tokenize.TokenInfo]]:
    blocks: list[list[tokenize.TokenInfo]] = []
    prev_full = False
    prev_row = -2
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        full = tok.line.lstrip().startswith("#")
        if blocks and full and prev_full and tok.start[0] == prev_row + 1:
            blocks[-1].append(tok)
        else:
            blocks.append([tok])
        prev_full, prev_row = full, tok.start[0]
    return blocks


def explanatory_comment_blocks(path: Path) -> list[int]:
    blocks = _comment_blocks(path.read_text(encoding="utf-8"))
    return [
        block[0].start[0]
        for block in blocks
        if not PLATFORM_LIMITATION.search(" ".join(tok.string for tok in block))
    ]
