"""Spreadsheet layout for the temperament/tuning grid (the mockup's default view).

Rows are the quantities the temperament exposes (quantities, mapping, tuning,
just tuning, retuning, damage); columns are the interval/generator sets they're
shown over (generators, domain primes, target intervals). Cells sit on shared
coordinate axes — every prime/target is a vertical line shared down its column,
every generator a horizontal line shared across the mapping rows — so the
matrices stay aligned and the reconciling renderer can animate rows/columns in
and out. Reuses the entity types in :mod:`rtt.web.layout`.
"""

from __future__ import annotations

from rtt.web import service
from rtt.web.layout import Block, CellBox, Layout, Line
from rtt.web.settings import defaults as _default_settings

ROW_H = 30  # px per row / matrix-entry height
COL_W = 56  # px per value column (wide enough for cents like 1899.26)
GAP = 14  # px between row/column groups
PAD = 4  # px a block extends around its cells
LABEL_W = 96  # row-label gutter width
HEADER_H = 22  # column-header height
GEN_W = 50  # generators column width


def _cents(value) -> str:
    return f"{value:.2f}"


def build(state, settings=None) -> Layout:
    if settings is None:
        settings = _default_settings()
    show_names = settings["names"]
    show_temp = settings["temperament_boxes"]
    show_tuning = settings["tuning_boxes"]
    # The row-label gutter and column-header band collapse to nothing when names
    # are hidden, so the values slide into the freed margin instead of leaving one.
    label_w = LABEL_W if show_names else 0
    header_h = HEADER_H if show_names else 0
    d = state.d
    r = len(state.mapping)
    primes = service.standard_primes(d)
    gens = service.generators(state.mapping)
    targets = service.DEFAULT_TARGET_INTERVALS
    k = len(targets)
    mapped = service.mapped_target_intervals(state.mapping, targets)
    tun = service.tuning(state.mapping, targets)

    gen_x = label_w + GAP
    primes_x = gen_x + GEN_W + GAP
    ctrl_x = primes_x + d * COL_W + 6
    targets_x = ctrl_x + 52 + GAP
    total_w = targets_x + k * COL_W + GAP

    header_y = 0
    fanout_y = header_h + GAP  # columns fan out into per-element lines here, above quantities
    quant_y = header_h + 2 * GAP
    # Rows are laid out top-down with a running cursor, so hiding a group closes
    # its gap and shrinks total height rather than leaving a hole.
    y = quant_y + ROW_H + GAP
    map_y = y
    if show_temp:
        y += r * ROW_H + GAP
    tuning_y = y
    just_y = tuning_y + ROW_H + GAP
    retune_y = just_y + ROW_H + GAP
    damage_y = retune_y + ROW_H + GAP
    if show_tuning:
        y = damage_y + ROW_H + GAP
    total_h = y

    def prime_left(p):
        return primes_x + p * COL_W

    def target_left(j):
        return targets_x + j * COL_W

    def map_top(i):
        return map_y + i * ROW_H

    cells: list[CellBox] = []
    lines: list[Line] = []
    blocks: list[Block] = []

    # column headers
    if show_names:
        cells.append(CellBox("header:gens", gen_x, header_y, GEN_W, HEADER_H, "colheader", text="generators"))
        cells.append(CellBox("header:primes", primes_x, header_y, d * COL_W, HEADER_H, "colheader", text="domain primes"))
        cells.append(CellBox("header:targets", targets_x, header_y, k * COL_W, HEADER_H, "colheader", text="target-intervals"))

    # row labels (only for the rows actually present)
    if show_names:
        rows = [("quantities", quant_y, ROW_H, "quantities")]
        if show_temp:
            rows.append(("mapping", map_y, r * ROW_H, "mapping"))
        if show_tuning:
            rows += [("tuning", tuning_y, ROW_H, "tuning"), ("just", just_y, ROW_H, "just tuning"),
                     ("retune", retune_y, ROW_H, "retuning"), ("damage", damage_y, ROW_H, "damage")]
        for key, ly, h, text in rows:
            cells.append(CellBox(f"label:{key}", 0, ly, LABEL_W, h, "rowlabel", text=text))

    # quantities row: domain primes (+ controls) and target ratios
    for p in range(d):
        cells.append(CellBox(f"prime:{p}", prime_left(p), quant_y, COL_W, ROW_H, "prime", text=str(primes[p]), prime=p))
    cells.append(CellBox("minus", ctrl_x, quant_y + 5, 20, 20, "minus"))
    cells.append(CellBox("plus", ctrl_x + 24, quant_y + 5, 20, 20, "plus"))
    for j in range(k):
        cells.append(CellBox(f"target:{j}", target_left(j), quant_y, COL_W, ROW_H, "target", text=targets[j]))

    # generator ratios (aligned with the mapping rows they label) + the mapping
    # matrix and its mapped target-interval list
    if show_temp:
        for i in range(r):
            cells.append(CellBox(f"gen:{i}", gen_x, map_top(i), GEN_W, ROW_H, "genratio", text=gens[i] if i < len(gens) else "", gen=i))
        for i in range(r):
            for p in range(d):
                cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), COL_W, ROW_H, "mapping", gen=i, prime=p))
            for j in range(k):
                cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped[i][j]), gen=i))

    # tuning rows over the primes and targets (cents)
    def tuning_row(key, y, prime_vals, target_vals):
        for p, v in enumerate(prime_vals):
            cells.append(CellBox(f"{key}:prime:{p}", prime_left(p), y, COL_W, ROW_H, "tval", text=_cents(v)))
        for j, v in enumerate(target_vals):
            cells.append(CellBox(f"{key}:target:{j}", target_left(j), y, COL_W, ROW_H, "tval", text=_cents(v)))

    if show_tuning:
        tuning_row("tuning", tuning_y, tun.tuning_map, tun.tempered_targets)
        tuning_row("just", just_y, tun.just_map, tun.just_targets)
        tuning_row("retune", retune_y, tun.retuning_map, tun.target_errors)
        for j, v in enumerate(tun.target_damage):  # damage is over the targets only
            cells.append(CellBox(f"damage:target:{j}", target_left(j), damage_y, COL_W, ROW_H, "tval", text=_cents(v)))

    # shared axes, with each column header branching (above quantities) into one
    # vertical line per element: a trunk from the node down to a bus, which fans
    # into the per-element verticals that run down through the rows.
    def fan(group_id, n, pitch_left):
        centers = [pitch_left(i) for i in range(n)]
        trunk_x = (centers[0] + centers[-1]) / 2
        lines.append(Line(f"trunk:{group_id}", "v", trunk_x, header_h, fanout_y - header_h))
        if n > 1:
            lines.append(Line(f"bus:{group_id}", "h", fanout_y, centers[0], centers[-1] - centers[0]))

    fan("primes", d, lambda p: prime_left(p) + COL_W / 2)
    for p in range(d):
        lines.append(Line(f"v:prime:{p}", "v", prime_left(p) + COL_W / 2, fanout_y, total_h - fanout_y))
    fan("targets", k, lambda j: target_left(j) + COL_W / 2)
    for j in range(k):
        lines.append(Line(f"v:target:{j}", "v", target_left(j) + COL_W / 2, fanout_y, total_h - fanout_y))

    # generators column: a trunk from its node down through the mapping rows, which
    # branch off it as the horizontal generator lines.
    gen_cx = gen_x + GEN_W / 2
    if show_temp:
        lines.append(Line("trunk:gens", "v", gen_cx, header_h, map_top(r - 1) + ROW_H / 2 - header_h))
        for i in range(r):
            lines.append(Line(f"h:gen:{i}", "h", map_top(i) + ROW_H / 2, gen_cx, total_w - gen_cx))
    if show_tuning:
        for key, ly in (("tuning", tuning_y), ("just", just_y), ("retune", retune_y), ("damage", damage_y)):
            lines.append(Line(f"h:{key}", "h", ly + ROW_H / 2, primes_x, total_w - primes_x))

    # #e0e0e0 panels behind each content group
    def block(bid, x, y, w, h):
        blocks.append(Block(bid, x - PAD, y - PAD, w + 2 * PAD, h + 2 * PAD))

    block("block:primes", primes_x, quant_y, d * COL_W, ROW_H)
    block("block:targets", targets_x, quant_y, k * COL_W, ROW_H)
    if show_temp:
        block("block:gens", gen_x, map_y, GEN_W, r * ROW_H)
        block("block:mapping", primes_x, map_y, d * COL_W, r * ROW_H)
        block("block:mapped", targets_x, map_y, k * COL_W, r * ROW_H)
    if show_tuning:
        for key, ly in (("tuning", tuning_y), ("just", just_y), ("retune", retune_y)):
            block(f"block:{key}:primes", primes_x, ly, d * COL_W, ROW_H)
            block(f"block:{key}:targets", targets_x, ly, k * COL_W, ROW_H)
        block("block:damage:targets", targets_x, damage_y, k * COL_W, ROW_H)

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
