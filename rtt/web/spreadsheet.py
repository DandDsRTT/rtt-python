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
CTRL_W = 52  # domain shrink/expand (-/+) control gutter, right of the primes block
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap


def _cents(value) -> str:
    return f"{value:.2f}"


def build(state, settings=None, collapsed=None) -> Layout:
    if settings is None:
        settings = _default_settings()
    collapsed = collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
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

    # Column bands left-to-right: (key, natural width, present, collapsible).
    # Generators belong to the temperament; domain primes and targets are always
    # present. A present band whose id is in `collapsed` folds to a strip. The
    # domain -/+ controls ride just right of the primes block when it is open.
    col_bands = (
        ("gens", GEN_W, show_temp, True),
        ("primes", d * COL_W, True, True),
        ("targets", k * COL_W, True, True),
    )
    # A fold-toggle node column sits between the row-label gutter and the content
    # (when names show); content starts past it with a clear gap so the tiles
    # never collide with the nodes. The horizontal row lines anchor at node_cx.
    node_x = label_w + GAP
    node_cx = node_x + TOGGLE / 2
    content_x0 = node_x + TOGGLE + GAP if show_names else label_w + GAP

    col_x, col_w, col_collapsible = {}, {}, {}
    ctrl_x = None
    x = content_x0
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        col_x[key] = x
        col_w[key] = STRIP if f"col:{key}" in collapsed else natural
        col_collapsible[key] = collapsible
        x += col_w[key]
        if key == "primes" and f"col:{key}" not in collapsed:
            ctrl_x = x + 6
            x = ctrl_x + CTRL_W
        x += GAP
    total_w = x

    gen_x = col_x.get("gens", content_x0)
    primes_x = col_x["primes"]
    targets_x = col_x["targets"]

    def col_open(key):
        return key in col_x and f"col:{key}" not in collapsed

    header_y = 0
    col_node_y = header_h + (GAP - TOGGLE) / 2  # the column toggle sits just under the header text
    # Branching (trunk/bus/verticals) starts just below the column nodes so no
    # line pokes up past them; with names hidden it starts at the very top.
    branch_top_y = col_node_y + TOGGLE if show_names else header_y
    fanout_y = header_h + GAP  # columns fan out into per-element lines here, above quantities
    quant_y = header_h + 2 * GAP

    # Row bands top-to-bottom: (key, natural height, present, collapsible, label),
    # laid out by the same running-cursor rule as the columns. The spine
    # quantities row is not collapsible; the rest can fold to a strip.
    row_bands = (
        ("quantities", ROW_H, True, False, "quantities"),
        ("mapping", r * ROW_H, show_temp, True, "mapping"),
        ("tuning", ROW_H, show_tuning, True, "tuning"),
        ("just", ROW_H, show_tuning, True, "just tuning"),
        ("retune", ROW_H, show_tuning, True, "retuning"),
        ("damage", ROW_H, show_tuning, True, "damage"),
    )
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    y = quant_y
    for key, natural, present, collapsible, label in row_bands:
        if not present:
            continue
        row_y[key] = y
        row_h[key] = STRIP if f"row:{key}" in collapsed else natural
        row_label[key] = label
        row_collapsible[key] = collapsible
        y += row_h[key] + GAP
    total_h = y

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def prime_left(p):
        return primes_x + p * COL_W

    def target_left(j):
        return targets_x + j * COL_W

    def map_top(i):
        return row_y["mapping"] + i * ROW_H

    cells: list[CellBox] = []
    lines: list[Line] = []
    blocks: list[Block] = []

    # column headers (every present column; a collapsed column keeps its header
    # as the strip) plus a fold toggle in the header band for collapsible ones
    col_header = {"gens": "generators", "primes": "domain primes", "targets": "target-intervals"}
    if show_names:
        for key in col_x:
            # blank the title on a collapsed (strip-width) column so it can't overflow
            # and overlap its neighbours; the chevron toggle stays as the affordance
            htext = "" if f"col:{key}" in collapsed else col_header[key]
            cells.append(CellBox(f"header:{key}", col_x[key], header_y, col_w[key], HEADER_H, "colheader", text=htext))
            if col_collapsible[key]:
                glyph = "chevron_right" if f"col:{key}" in collapsed else "chevron_left"
                tx = col_x[key] + (col_w[key] - TOGGLE) / 2  # centered under the header text
                cells.append(CellBox(f"toggle:col:{key}", tx, col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))

    # row labels (every present row; a collapsed row keeps its label as the
    # strip) plus a fold toggle in the gutter for the collapsible ones
    if show_names:
        for key in row_y:
            cells.append(CellBox(f"label:{key}", 0, row_y[key], LABEL_W, row_h[key], "rowlabel", text=row_label[key]))
            if row_collapsible[key]:
                glyph = "expand_more" if f"row:{key}" in collapsed else "expand_less"
                ty = row_y[key] + (row_h[key] - TOGGLE) / 2
                cells.append(CellBox(f"toggle:row:{key}", node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))

    # quantities row: domain primes (+ controls) and target ratios
    if col_open("primes"):
        for p in range(d):
            cells.append(CellBox(f"prime:{p}", prime_left(p), quant_y, COL_W, ROW_H, "prime", text=str(primes[p]), prime=p))
        cells.append(CellBox("minus", ctrl_x, quant_y + 5, 20, 20, "minus"))
        cells.append(CellBox("plus", ctrl_x + 24, quant_y + 5, 20, 20, "plus"))
    if col_open("targets"):
        for j in range(k):
            cells.append(CellBox(f"target:{j}", target_left(j), quant_y, COL_W, ROW_H, "target", text=targets[j]))

    # generator ratios (aligned with the mapping rows they label) + the mapping
    # matrix and its mapped target-interval list
    if row_open("mapping"):
        if col_open("gens"):
            for i in range(r):
                cells.append(CellBox(f"gen:{i}", gen_x, map_top(i), GEN_W, ROW_H, "genratio", text=gens[i] if i < len(gens) else "", gen=i))
        for i in range(r):
            if col_open("primes"):
                for p in range(d):
                    cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), COL_W, ROW_H, "mapping", gen=i, prime=p))
            if col_open("targets"):
                for j in range(k):
                    cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped[i][j]), gen=i))

    # tuning rows over the primes and targets (cents); each can collapse on its own
    def tuning_row(key, prime_vals, target_vals):
        y = row_y[key]
        if col_open("primes"):
            for p, v in enumerate(prime_vals):
                cells.append(CellBox(f"{key}:prime:{p}", prime_left(p), y, COL_W, ROW_H, "tval", text=_cents(v)))
        if col_open("targets"):
            for j, v in enumerate(target_vals):
                cells.append(CellBox(f"{key}:target:{j}", target_left(j), y, COL_W, ROW_H, "tval", text=_cents(v)))

    tuning_data = {
        "tuning": (tun.tuning_map, tun.tempered_targets),
        "just": (tun.just_map, tun.just_targets),
        "retune": (tun.retuning_map, tun.target_errors),
    }
    for key, (prime_vals, target_vals) in tuning_data.items():
        if row_open(key):
            tuning_row(key, prime_vals, target_vals)
    if row_open("damage") and col_open("targets"):  # damage is over the targets only
        for j, v in enumerate(tun.target_damage):
            cells.append(CellBox(f"damage:target:{j}", target_left(j), row_y["damage"], COL_W, ROW_H, "tval", text=_cents(v)))

    # shared axes, with each column header branching (above quantities) into one
    # vertical line per element: a trunk from the node down to a bus, which fans
    # into the per-element verticals that run down through the rows.
    def fan(group_id, n, pitch_left):
        centers = [pitch_left(i) for i in range(n)]
        trunk_x = (centers[0] + centers[-1]) / 2
        lines.append(Line(f"trunk:{group_id}", "v", trunk_x, branch_top_y, fanout_y - branch_top_y))
        if n > 1:
            lines.append(Line(f"bus:{group_id}", "h", fanout_y, centers[0], centers[-1] - centers[0]))

    if col_open("primes"):
        fan("primes", d, lambda p: prime_left(p) + COL_W / 2)
        for p in range(d):
            lines.append(Line(f"v:prime:{p}", "v", prime_left(p) + COL_W / 2, fanout_y, total_h - fanout_y))
    if col_open("targets"):
        fan("targets", k, lambda j: target_left(j) + COL_W / 2)
        for j in range(k):
            lines.append(Line(f"v:target:{j}", "v", target_left(j) + COL_W / 2, fanout_y, total_h - fanout_y))

    # generators column: a trunk from its node down through the mapping rows, which
    # branch off it as the horizontal generator lines.
    gen_cx = gen_x + col_w.get("gens", GEN_W) / 2
    if row_open("mapping"):
        lines.append(Line("trunk:gens", "v", gen_cx, branch_top_y, map_top(r - 1) + ROW_H / 2 - branch_top_y))
        for i in range(r):
            x0 = node_cx if show_names else gen_cx
            lines.append(Line(f"h:gen:{i}", "h", map_top(i) + ROW_H / 2, x0, total_w - x0))
    for key in ("tuning", "just", "retune", "damage"):
        if row_open(key):
            x0 = node_cx if show_names else primes_x
            lines.append(Line(f"h:{key}", "h", row_y[key] + ROW_H / 2, x0, total_w - x0))

    # #e0e0e0 panels behind each content group
    def block(bid, x, y, w, h):
        blocks.append(Block(bid, x - PAD, y - PAD, w + 2 * PAD, h + 2 * PAD))

    # Panels are emitted for every *present* band (not just open ones) and sized
    # from row_h/col_w, so collapsing folds the panel to a strip that the renderer
    # animates shrinking — rather than the panel popping out of existence.
    def panel(bid, key_x, x, w, y, h):
        if key_x in col_x:
            block(bid, x, y, w, h)

    if "quantities" in row_y:
        qh = row_h["quantities"]
        panel("block:primes", "primes", primes_x, col_w.get("primes", 0), quant_y, qh)
        panel("block:targets", "targets", targets_x, col_w.get("targets", 0), quant_y, qh)
    if "mapping" in row_y:
        my, mh = row_y["mapping"], row_h["mapping"]
        panel("block:gens", "gens", gen_x, col_w.get("gens", 0), my, mh)
        panel("block:mapping", "primes", primes_x, col_w.get("primes", 0), my, mh)
        panel("block:mapped", "targets", targets_x, col_w.get("targets", 0), my, mh)
    for key in ("tuning", "just", "retune"):
        if key in row_y:
            panel(f"block:{key}:primes", "primes", primes_x, col_w.get("primes", 0), row_y[key], row_h[key])
            panel(f"block:{key}:targets", "targets", targets_x, col_w.get("targets", 0), row_y[key], row_h[key])
    if "damage" in row_y:
        panel("block:damage:targets", "targets", targets_x, col_w.get("targets", 0), row_y["damage"], row_h["damage"])

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
