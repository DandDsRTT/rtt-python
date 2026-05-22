"""Coordinate-space model for the temperament grid.

Turns the logical grid (:mod:`rtt.web.grid`) into positioned entities with
*stable, semantic ids* so the renderer can keep them across state changes and
animate add/remove/move:

* :class:`Line` — one entity per coordinate axis (``v:prime:2``, ``h:gen:0``,
  ``v:comma:0``), a continuous line spanning the content, not per-cell segments.
* :class:`Block` — the #e0e0e0 panels (``block:mapping`` ...), one rect each.
* :class:`CellBox` — inputs / prime labels / buttons / captions
  (``cell:mapping:0:1``, ``prime:2`` ...).

Geometry comes from grid.track_sizes, so positions match the rendered grid; only
the representation changes (entities + ids instead of a flat per-cell list).
"""

from __future__ import annotations

from dataclasses import dataclass

from rtt.web import grid

_BLOCK_PAD = 6  # px the #e0e0e0 panels extend around their cells

_GROUPS = (  # block id -> the cell kinds it bounds
    ("controls", ("minus", "plus")),
    ("header", ("prime",)),
    ("mapping", ("mapping",)),
    ("comma", ("comma",)),
)


@dataclass(frozen=True)
class Line:
    id: str
    orientation: str  # "v" | "h"
    pos: float  # cross-axis position (x for v, y for h)
    start: float  # along-axis start (y for v, x for h)
    length: float


@dataclass(frozen=True)
class Block:
    id: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class CellBox:
    id: str
    x: float
    y: float
    w: float
    h: float
    kind: str
    text: str = ""
    gen: int = -1
    prime: int = -1
    comma: int = -1


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    cells: tuple[CellBox, ...]


def _cell_id(cell) -> str:
    if cell.kind == "mapping":
        return f"cell:mapping:{cell.gen}:{cell.prime}"
    if cell.kind == "comma":
        return f"cell:comma:{cell.comma}:{cell.prime}"
    if cell.kind == "prime":
        return f"cell:prime:{cell.prime}"
    if cell.kind == "name":
        return f"label:{cell.text}"
    return cell.kind  # minus / plus


def build_layout(d: int, rank: int, n: int, primes: tuple[int, ...]) -> Layout:
    cells_g = grid.build(d, rank, n, primes)
    cols, rows = grid.track_sizes(cells_g)

    edge_x, edge_y = [0], [0]
    for w in cols:
        edge_x.append(edge_x[-1] + w)
    for h in rows:
        edge_y.append(edge_y[-1] + h)
    total_w, total_h = edge_x[-1], edge_y[-1]

    def col_x(c):
        return edge_x[c - 1]

    def col_w(c, span=1):
        return edge_x[c - 1 + span] - edge_x[c - 1]

    def row_y(r):
        return edge_y[r - 1]

    def row_h(r):
        return edge_y[r] - edge_y[r - 1]

    # interactive cells -> positioned, identified boxes
    cells: list[CellBox] = []
    for c in cells_g:
        if c.kind in ("prime", "mapping", "comma", "minus", "plus", "name"):
            cells.append(
                CellBox(
                    _cell_id(c), col_x(c.col), row_y(c.row),
                    col_w(c.col, c.colspan), row_h(c.row),
                    c.kind, c.text, c.gen, c.prime, c.comma,
                )
            )

    # first-class lines: one per gridded column / row, spanning the whole content
    col_to_prime = {c.col: c.prime for c in cells_g if c.kind == "prime"}
    col_to_comma = {c.col: c.comma for c in cells_g if c.kind == "comma"}
    row_to_gen = {c.row: c.gen for c in cells_g if c.kind == "mapping"}
    row_to_comma_prime = {c.row: c.prime for c in cells_g if c.kind == "comma"}
    header_rows = {c.row for c in cells_g if c.kind == "prime"}

    lines: list[Line] = []
    for col in sorted({c.col for c in cells_g if c.vline}):
        if col in col_to_prime:
            lid = f"v:prime:{col_to_prime[col]}"
        elif col in col_to_comma:
            lid = f"v:comma:{col_to_comma[col]}"
        else:
            lid = f"v:col:{col}"
        lines.append(Line(lid, "v", col_x(col) + col_w(col) / 2, 0, total_h))
    for row in sorted({c.row for c in cells_g if c.hline}):
        if row in row_to_gen:
            lid = f"h:gen:{row_to_gen[row]}"
        elif row in row_to_comma_prime:
            lid = f"h:prime:{row_to_comma_prime[row]}"
        elif row in header_rows:
            lid = "h:header"
        else:
            lid = f"h:row:{row}"
        lines.append(Line(lid, "h", row_y(row) + row_h(row) / 2, 0, total_w))

    # #e0e0e0 panels: one padded rect bounding each content group
    blocks: list[Block] = []
    by_kind: dict[str, list[CellBox]] = {}
    for cb in cells:
        by_kind.setdefault(cb.kind, []).append(cb)
    for bid, kinds in _GROUPS:
        members = [cb for k in kinds for cb in by_kind.get(k, [])]
        if kinds == ("mapping",):
            members += [cb for cb in by_kind.get("name", []) if cb.text == "mapping"]
        if kinds == ("comma",):
            members += [cb for cb in by_kind.get("name", []) if cb.text == "comma basis"]
        if not members:
            continue
        x0 = min(cb.x for cb in members) - _BLOCK_PAD
        y0 = min(cb.y for cb in members) - _BLOCK_PAD
        x1 = max(cb.x + cb.w for cb in members) + _BLOCK_PAD
        y1 = max(cb.y + cb.h for cb in members) + _BLOCK_PAD
        blocks.append(Block(f"block:{bid}", x0, y0, x1 - x0, y1 - y0))

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
