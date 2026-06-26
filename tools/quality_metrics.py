from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

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


def _param_seeded_attrs(method: ast.AST) -> set[str]:
    params = init_params(method)
    seeded: set[str] = set()
    for stmt in ast.walk(method):
        value = getattr(stmt, "value", None)
        if isinstance(value, ast.Name) and value.id in params:
            seeded |= {tgt.attr for tgt in self_attr_targets(stmt)}
    return seeded


def constructor_injected_names(trees: list[tuple[Path, ast.Module]]) -> set[str]:
    names: set[str] = set()
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for method in _enclosed_methods(node):
                    if method.name == "__init__":
                        names |= _param_seeded_attrs(method)
    return names


class _HandleParts(NamedTuple):
    init_injected: set[str]
    late_injected: set[str]
    aliases: list[tuple[str, str]]
    constructed: set[str]


def _class_handle_parts(cls: ast.ClassDef, injectable: set[str]) -> _HandleParts:
    init_injected: set[str] = set()
    late_injected: set[str] = set()
    constructed: set[str] = set()
    aliases: list[tuple[str, str]] = []
    for method in _enclosed_methods(cls):
        seeded = _param_seeded_attrs(method)
        if method.name == "__init__":
            init_injected |= seeded
        else:
            late_injected |= seeded & injectable
        for node in ast.walk(method):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = getattr(node, "value", None)
            if isinstance(value, (ast.Name, ast.Constant)):
                continue
            source = _self_attr(value)
            for tgt in self_attr_targets(node):
                if source is not None:
                    aliases.append((tgt.attr, source))
                else:
                    constructed.add(tgt.attr)
    return _HandleParts(init_injected, late_injected, aliases, constructed)


def _merge_handle_parts(left: _HandleParts | None, right: _HandleParts) -> _HandleParts:
    if left is None:
        return right
    return _HandleParts(
        left.init_injected | right.init_injected,
        left.late_injected | right.late_injected,
        left.aliases + right.aliases,
        left.constructed | right.constructed,
    )


def _inheritance_components(bases: dict[str, set[str]]) -> dict[str, str]:
    parent = {name: name for name in bases}

    def root(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for name in parent:
        for base in bases[name]:
            if base in parent:
                parent[root(name)] = root(base)
    return {name: root(name) for name in parent}


def handles_by_class(trees: list[tuple[Path, ast.Module]]) -> dict[str, set[str]]:
    injectable = constructor_injected_names(trees)
    parts: dict[str, _HandleParts] = {}
    bases: dict[str, set[str]] = defaultdict(set)
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                parts[node.name] = _merge_handle_parts(
                    parts.get(node.name), _class_handle_parts(node, injectable)
                )
                bases[node.name] |= {b.id for b in node.bases if isinstance(b, ast.Name)}
    component = _inheritance_components(bases)
    init: dict[str, set[str]] = defaultdict(set)
    late: dict[str, set[str]] = defaultdict(set)
    aliases: dict[str, list[tuple[str, str]]] = defaultdict(list)
    constructed: dict[str, set[str]] = defaultdict(set)
    for name, part in parts.items():
        root = component[name]
        init[root] |= part.init_injected
        late[root] |= part.late_injected
        aliases[root] += part.aliases
        constructed[root] |= part.constructed
    resolved: dict[str, set[str]] = {}
    for root in set(component.values()):
        handles = init[root] | late[root]
        _grow_alias_handles(handles, aliases[root])
        handles -= constructed[root] - init[root]
        resolved[root] = handles
    return {name: resolved[component[name]] for name in parts}


def _grow_alias_handles(handles: set[str], aliases: list[tuple[str, str]]) -> None:
    changed = True
    while changed:
        changed = False
        for target, source in aliases:
            if source in handles and target not in handles:
                handles.add(target)
                changed = True


class _ReachVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.handles: set[str] = set()
        self.counts: Counter = Counter()
        self.scopes: list[dict[str, str]] = [{}]

    def visit_FunctionDef(self, node: ast.AST) -> None:
        self.scopes.append(dict(self.scopes[-1]))
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _direct_attr(self, value: ast.AST) -> str | None:
        raise NotImplementedError

    def _base_handle(self, value: ast.AST) -> str | None:
        if isinstance(value, ast.NamedExpr):
            value = value.value
        attr = self._direct_attr(value)
        if attr in self.handles:
            return attr
        if isinstance(value, ast.Name):
            return self.scopes[-1].get(value.id)
        return None

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

    def visit_Attribute(self, node: ast.Attribute) -> None:
        handle = self._base_handle(node.value)
        if handle:
            self.counts[handle] += 1
        self._note_attribute(node)
        self.generic_visit(node)

    def _note_attribute(self, node: ast.Attribute) -> None:
        pass


class _HandleVisitor(_ReachVisitor):
    def __init__(self, class_handles: dict[str, set[str]]) -> None:
        super().__init__()
        self.class_handles = class_handles
        self.chains: list[tuple[int, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        enclosing = self.handles
        self.handles = self.class_handles.get(node.name, set())
        self.generic_visit(node)
        self.handles = enclosing

    def _direct_attr(self, value: ast.AST) -> str | None:
        return _self_attr(value)

    def _note_attribute(self, node: ast.Attribute) -> None:
        chain = self._chain(node)
        if chain and chain[1] >= HANDLE_CHAIN_FLOOR:
            self.chains.append((node.lineno, chain[0]))

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
    visitor = _HandleVisitor(handles_by_class(trees))
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


SHARD_PARAM_CONTROLLER = {
    "rec": "_Reconciler",
    "ec": "EditController",
    "te": "_TuningEdits",
    "gc": "GestureController",
    "pb": "PageBuilder",
    "r": "Renderer",
}


class _ParamReachVisitor(_ReachVisitor):
    def __init__(self, param: str, handles: set[str], counts: Counter) -> None:
        super().__init__()
        self.param = param
        self.handles = handles
        self.counts = counts

    def _direct_attr(self, value: ast.AST) -> str | None:
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == self.param
        ):
            return value.attr
        return None


def _shard_binding(
    node: ast.AST, class_handles: dict[str, set[str]]
) -> tuple[str, set[str]] | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.args.args:
        return None
    param = node.args.args[0].arg
    bound = SHARD_PARAM_CONTROLLER.get(param)
    handles = class_handles.get(bound, set()) if bound else set()
    return (param, handles) if handles else None


def param_reach_by_handle(trees: list[tuple[Path, ast.Module]]) -> Counter:
    class_handles = handles_by_class(trees)
    counts: Counter = Counter()
    for _path, tree in trees:
        for node in tree.body:
            binding = _shard_binding(node, class_handles)
            if binding is not None:
                param, handles = binding
                _ParamReachVisitor(param, handles, counts).visit(node)
    return counts


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
