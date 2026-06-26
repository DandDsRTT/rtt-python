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


def _self_attr(value: ast.AST) -> str | None:
    if (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "self"
    ):
        return value.attr
    return None


def injected_handle_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    handles: set[str] = set()
    aliases: list[tuple[str, str]] = []
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, DEFINITION) and node.name == "__init__":
                _seed_param_handles(node, handles)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                source = _self_attr(getattr(node, "value", None))
                if source is not None:
                    aliases += [(tgt.attr, source) for tgt in self_attr_targets(node)]
    _grow_alias_handles(handles, aliases)
    return handles


def _seed_param_handles(init: ast.AST, handles: set[str]) -> None:
    params = init_params(init)
    for stmt in ast.walk(init):
        value = getattr(stmt, "value", None)
        if isinstance(value, ast.Name) and value.id in params:
            handles |= {tgt.attr for tgt in self_attr_targets(stmt)}


def _grow_alias_handles(handles: set[str], aliases: list[tuple[str, str]]) -> None:
    changed = True
    while changed:
        changed = False
        for target, source in aliases:
            if source in handles and target not in handles:
                handles.add(target)
                changed = True


class _HandleVisitor(ast.NodeVisitor):
    def __init__(self, handles: set[str]) -> None:
        self.handles = handles
        self.counts: Counter = Counter()
        self.chains: list[tuple[int, str]] = []
        self.scopes: list[dict[str, str]] = [{}]

    def visit_FunctionDef(self, node: ast.AST) -> None:
        self.scopes.append(dict(self.scopes[-1]))
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _register(self, target: ast.AST, value: ast.AST) -> None:
        if isinstance(target, ast.Name):
            handle = self._base_handle(value)
            if handle:
                self.scopes[-1][target.id] = handle

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._register(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._register(node.target, node.value)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._register(node.target, node.value)
        self.generic_visit(node)

    def _base_handle(self, value: ast.AST) -> str | None:
        if isinstance(value, ast.NamedExpr):
            value = value.value
        attr = _self_attr(value)
        if attr in self.handles:
            return attr
        if isinstance(value, ast.Name):
            return self.scopes[-1].get(value.id)
        return None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        handle = self._base_handle(node.value)
        if handle:
            self.counts[handle] += 1
        chain = self._chain(node)
        if chain and chain[1] >= HANDLE_CHAIN_FLOOR:
            self.chains.append((node.lineno, chain[0]))
        self.generic_visit(node)

    def _chain(self, node: ast.Attribute) -> tuple[str, int] | None:
        hops: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, (ast.Attribute, ast.NamedExpr)):
            if isinstance(cur, ast.NamedExpr):
                cur = cur.value
            else:
                hops.append(cur.attr)
                cur = cur.value
        hops.reverse()
        if isinstance(cur, ast.Name) and cur.id == "self" and hops and hops[0] in self.handles:
            return "self." + ".".join(hops), len(hops)
        if isinstance(cur, ast.Name) and (handle := self.scopes[-1].get(cur.id)):
            return "self." + ".".join([handle, *hops]), len(hops) + 1
        return None


def _walk_handles(trees: list[tuple[Path, ast.Module]]) -> tuple[Counter, set[str]]:
    visitor = _HandleVisitor(injected_handle_names(trees))
    rows: list[tuple[str, int, str]] = []
    for path, tree in trees:
        visitor.scopes = [{}]
        start = len(visitor.chains)
        visitor.visit(tree)
        rows += [(path.as_posix(), line, text) for line, text in visitor.chains[start:]]
    return visitor.counts, _maximal_chains(rows)


def reach_through_by_handle(trees: list[tuple[Path, ast.Module]]) -> Counter:
    return _walk_handles(trees)[0]


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
    return _walk_handles(trees)[1]


def namespace_ctor_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    names = {"SimpleNamespace"}
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "types":
                for alias in node.names:
                    if alias.name == "SimpleNamespace":
                        names.add(alias.asname or alias.name)
    return names


def _constructs_namespace(node: ast.AST, ctor_names: set[str]) -> bool:
    if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
        return False
    func = node.value.func
    return (isinstance(func, ast.Name) and func.id in ctor_names) or (
        isinstance(func, ast.Attribute) and func.attr == "SimpleNamespace"
    )


def bag_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    ctor_names = namespace_ctor_names(trees)
    names: set[str] = set()
    for _path, tree in trees:
        for node in ast.walk(tree):
            if _constructs_namespace(node, ctor_names):
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
        if writes.get(key) and len(writes.get(key, set()) | reads.get(key, set())) > 1
    }
    return {f"{bag}.{attr}" for bag, attr in crossing}, {bag for bag, _attr in crossing}


def _enclosed_methods(cls: ast.ClassDef) -> list[ast.AST]:
    methods: list[ast.AST] = []
    stack = list(cls.body)
    while stack:
        node = stack.pop()
        if isinstance(node, DEFINITION):
            methods.append(node)
        elif isinstance(node, ast.ClassDef):
            continue
        else:
            for field in ("body", "orelse", "finalbody"):
                stack.extend(getattr(node, field, []))
            for handler in getattr(node, "handlers", []):
                stack.extend(handler.body)
    return methods


def _instance_attrs(cls: ast.ClassDef) -> set[str]:
    attrs: set[str] = set()
    for method in _enclosed_methods(cls):
        for node in ast.walk(method):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and isinstance(node.ctx, ast.Store)
            ):
                attrs.add(node.attr)
    return attrs


def _collect_classes(
    node: ast.AST, path: Path, prefix: list[str], surface: dict[str, dict[str, int]]
) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            qualified = ".".join([*prefix, child.name])
            surface[f"{path.as_posix()}::{qualified}"] = {
                "methods": len(_enclosed_methods(child)),
                "attrs": len(_instance_attrs(child)),
            }
            _collect_classes(child, path, [*prefix, child.name], surface)
        else:
            _collect_classes(child, path, prefix, surface)


def class_surface(trees: list[tuple[Path, ast.Module]]) -> dict[str, dict[str, int]]:
    surface: dict[str, dict[str, int]] = {}
    for path, tree in trees:
        _collect_classes(tree, path, [], surface)
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
