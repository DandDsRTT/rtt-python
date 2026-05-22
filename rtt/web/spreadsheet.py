"""Spreadsheet layout for the temperament/tuning grid (the mockup's default view).

Rows are quantities the temperament exposes (so far: quantities, mapping) and
columns are the interval/generator sets they're shown over (generators, domain
primes). Cells sit on shared coordinate axes — every prime is a vertical line
shared down a column, every generator a horizontal line shared across a row — so
the matrices stay aligned, and the reconciling renderer can animate rows/columns
in and out. Reuses the entity types in :mod:`rtt.web.layout`.

This is increment 1 (the skeleton + temperament cells); generators-as-ratios,
target intervals and tuning rows are layered on next.
"""

from __future__ import annotations

from rtt.web import service
from rtt.web.layout import Block, CellBox, Layout, Line

CELL = 30  # px per matrix entry / axis pitch
GAP = 16  # px between column/row groups
PAD = 4  # px a block extends around its cells
LABEL_W = 84  # row-label gutter width
HEADER_H = 22  # column-header height
GEN_W = 46  # generators column width


def build(state) -> Layout:
    d = state.d
    r = len(state.mapping)
    primes = service.standard_primes(d)
    gens = service.generators(state.mapping)
    targets = service.DEFAULT_TARGET_INTERVALS
    k = len(targets)
    mapped = service.mapped_target_intervals(state.mapping, targets)

    gen_x = LABEL_W + GAP
    primes_x = gen_x + GEN_W + GAP
    ctrl_x = primes_x + d * CELL + 6  # domain -/+ buttons sit after the primes
    targets_x = ctrl_x + 52 + GAP
    header_y = 0
    quant_y = HEADER_H + GAP
    map_y = quant_y + CELL + GAP
    total_w = targets_x + k * CELL + GAP
    total_h = map_y + r * CELL + GAP

    def prime_left(p):
        return primes_x + p * CELL

    def target_left(j):
        return targets_x + j * CELL

    def map_top(i):
        return map_y + i * CELL

    cells: list[CellBox] = []
    lines: list[Line] = []
    blocks: list[Block] = []

    # column headers
    cells.append(CellBox("header:gens", gen_x, header_y, GEN_W, HEADER_H, "colheader", text="generators"))
    cells.append(CellBox("header:primes", primes_x, header_y, d * CELL, HEADER_H, "colheader", text="domain primes"))
    cells.append(CellBox("header:targets", targets_x, header_y, k * CELL, HEADER_H, "colheader", text="target-intervals"))

    # row labels
    cells.append(CellBox("label:quantities", 0, quant_y, LABEL_W, CELL, "rowlabel", text="quantities"))
    cells.append(CellBox("label:mapping", 0, map_y, LABEL_W, r * CELL, "rowlabel", text="mapping"))

    # quantities row: the domain primes (shown, not yet editable) + domain controls
    for p in range(d):
        cells.append(CellBox(f"prime:{p}", prime_left(p), quant_y, CELL, CELL, "prime", text=str(primes[p]), prime=p))
    cells.append(CellBox("minus", ctrl_x, quant_y + 5, 20, 20, "minus"))
    cells.append(CellBox("plus", ctrl_x + 24, quant_y + 5, 20, 20, "plus"))

    # generators column: each generator's ratio, aligned with the mapping rows
    for i in range(r):
        ratio = gens[i] if i < len(gens) else ""
        cells.append(CellBox(f"gen:{i}", gen_x, map_top(i), GEN_W, CELL, "genratio", text=ratio, gen=i))

    # mapping matrix: r generators (rows) x d primes (columns)
    for i in range(r):
        for p in range(d):
            cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), CELL, CELL, "mapping", gen=i, prime=p))

    # target-intervals column: the targets (quantities row) and the mapped list (mapping rows)
    for j in range(k):
        cells.append(CellBox(f"target:{j}", target_left(j), quant_y, CELL, CELL, "target", text=targets[j]))
    for i in range(r):
        for j in range(k):
            cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), CELL, CELL, "mapped", text=str(mapped[i][j]), gen=i))

    # shared axes: a vertical line per prime and per target, a horizontal line per generator
    for p in range(d):
        lines.append(Line(f"v:prime:{p}", "v", prime_left(p) + CELL / 2, 0, total_h))
    for j in range(k):
        lines.append(Line(f"v:target:{j}", "v", target_left(j) + CELL / 2, 0, total_h))
    for i in range(r):
        lines.append(Line(f"h:gen:{i}", "h", map_top(i) + CELL / 2, 0, total_w))

    # #e0e0e0 panels behind each content group
    blocks.append(Block("block:primes", primes_x - PAD, quant_y - PAD, d * CELL + 2 * PAD, CELL + 2 * PAD))
    blocks.append(Block("block:gens", gen_x - PAD, map_y - PAD, GEN_W + 2 * PAD, r * CELL + 2 * PAD))
    blocks.append(Block("block:mapping", primes_x - PAD, map_y - PAD, d * CELL + 2 * PAD, r * CELL + 2 * PAD))
    blocks.append(Block("block:targets", targets_x - PAD, quant_y - PAD, k * CELL + 2 * PAD, CELL + 2 * PAD))
    blocks.append(Block("block:mapped", targets_x - PAD, map_y - PAD, k * CELL + 2 * PAD, r * CELL + 2 * PAD))

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
