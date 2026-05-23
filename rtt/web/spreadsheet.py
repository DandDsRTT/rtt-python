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
CAPTION_H = 16  # height of the quantity-name caption inside a tile (when names shown)
FRAME_H = 9  # height of a matrix's top-bracket framing band (the bar + down-ticks)
BRACE_H = 14  # height of a matrix's bottom curly-brace band (taller, room for the spike)
FRAME_GAP = 5  # gap between a framing band and the matrix cells, so they don't merge
BRACKET_W = 16  # gutter inside a value group for an EBK bracket (one side)
MARK_INSET = 8  # inset of a mapped column's top/bottom mark, so it clears the rules
SEP_W = 2  # width of a vertical rule between monzo columns (the renderer draws it
# as thick as a square bracket's main bar; this is just the cell it centres in)
MAP_BRACKETS = ("⟨", "]")  # ⟨ … ] for maps (covectors)
LIST_BRACKETS = ("[", "]")  # [ … ] for plain lists/matrices

# Quantity-name captions shown inside each (row, column) tile when names are on.
CAPTIONS = {
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "targets"): "mapped target-interval list",
    ("tuning", "primes"): "tuning map",
    ("tuning", "targets"): "tempered target-interval size list",
    ("just", "primes"): "just tuning map",
    ("just", "targets"): "(just) target-interval size list",
    ("retune", "primes"): "retuning map",
    ("retune", "targets"): "target-interval error list",
    ("damage", "targets"): "target-interval damage list",
}
CAPTIONED_ROWS = frozenset(row for row, _ in CAPTIONS)
FRAMED_ROWS = frozenset({"mapping"})  # multi-row matrices get a top bracket + bottom brace band


def _cents(value) -> str:
    return f"{value:.2f}"


def _title_w(title: str) -> int:
    """Approx rendered width of a 13px bold column title, so a collapsed column
    can fold to a strip that still fits its (horizontal) title without overflow."""
    return max(STRIP, len(title) * 8 + 10)


def _fold_glyph(is_collapsed: bool) -> str:
    """Material Icons name for the fold toggle: out-chevrons to expand a collapsed
    band, in-chevrons to collapse an expanded one."""
    return "unfold_more" if is_collapsed else "unfold_less"


def build(state, settings=None, collapsed=None) -> Layout:
    if settings is None:
        settings = _default_settings()
    collapsed = collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
    show_captions = settings["names"]  # the in-tile quantity captions; row/col titles always show
    show_temp = settings["temperament_boxes"]
    show_tuning = settings["tuning_boxes"]
    # Row labels and column headers (and their gutters) are always present.
    label_w = LABEL_W
    header_h = HEADER_H
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
    # present. A collapsed column folds to a strip just wide enough to keep its
    # (horizontal) title readable, so it never overflows onto its neighbours. The
    # domain -/+ controls ride just right of the primes block when it is open.
    col_header = {"gens": "generators", "primes": "domain primes", "targets": "target-intervals"}
    # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
    # the value cells are inset by BRACKET_W within the group.
    col_bands = (
        ("gens", GEN_W, show_temp, True),
        ("primes", 2 * BRACKET_W + d * COL_W, True, True),
        ("targets", 2 * BRACKET_W + k * COL_W, True, True),
    )
    # A fold-toggle node column sits between the row-label gutter and the content
    # (when names show); content starts past it with a clear gap so the tiles
    # never collide with the nodes. Row lines fan from the node's right edge so
    # their gaps match the columns'.
    node_x = label_w + GAP
    node_edge = node_x + TOGGLE  # the node's content-facing (right) edge
    content_x0 = node_x + TOGGLE + GAP

    col_x, col_w, col_collapsible = {}, {}, {}
    ctrl_x = None
    x = content_x0
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        col_x[key] = x
        col_w[key] = _title_w(col_header[key]) if f"col:{key}" in collapsed else natural
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
    branch_top_y = col_node_y + TOGGLE
    quant_y = branch_top_y + GAP
    # The grey tiles overhang their cells by PAD and sit over the gridlines, so the
    # *visible* fan segment runs from the bus only to the tile edge. Put each bus
    # midway between the node/foot edge and the tile edge (PAD inside the cell), so
    # the inner (bus->tile) and outer (node->bus) segments are equal: (GAP-PAD)/2.
    FAN = (GAP - PAD) / 2
    fanout_y = branch_top_y + FAN

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
    # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
    # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    tile_h, tile_top, row_frame = {}, {}, {}
    y = quant_y
    for key, natural, present, collapsible, label in row_bands:
        if not present:
            continue
        folded = f"row:{key}" in collapsed
        framed = key in FRAMED_ROWS and not folded
        # framing bands stand off the cells by FRAME_GAP: a top bracket (FRAME_H)
        # and a taller bottom curly brace (BRACE_H, with room for its spike)
        top_frame = (FRAME_H + FRAME_GAP) if framed else 0
        bot_frame = (BRACE_H + FRAME_GAP) if framed else 0
        cap = CAPTION_H if (show_captions and key in CAPTIONED_ROWS and not folded) else 0
        row_h[key] = STRIP if folded else natural
        tile_top[key] = y
        row_y[key] = y + top_frame  # values sit below the top framing band
        row_frame[key] = bot_frame  # the caption sits below the bottom brace band
        row_label[key] = label
        row_collapsible[key] = collapsible
        tile_h[key] = top_frame + row_h[key] + bot_frame + cap
        y += tile_h[key] + GAP
    total_h = y

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def prime_left(p):
        return primes_x + BRACKET_W + p * COL_W

    def target_left(j):
        return targets_x + BRACKET_W + j * COL_W

    def map_top(i):
        return row_y["mapping"] + i * ROW_H

    cells: list[CellBox] = []
    lines: list[Line] = []
    blocks: list[Block] = []

    # column headers (always shown; a collapsed column keeps its title) plus a
    # fold toggle in the header band for collapsible ones
    for key in col_x:
        cells.append(CellBox(f"header:{key}", col_x[key], header_y, col_w[key], HEADER_H, "colheader", text=col_header[key]))
        if col_collapsible[key]:
            glyph = _fold_glyph(f"col:{key}" in collapsed)
            tx = col_x[key] + (col_w[key] - TOGGLE) / 2  # centered under the header text
            cells.append(CellBox(f"toggle:col:{key}", tx, col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))

    # row labels (always shown; a collapsed row keeps its label as the strip)
    # plus a fold toggle in the gutter for the collapsible ones
    for key in row_y:
        cells.append(CellBox(f"label:{key}", 0, row_y[key], LABEL_W, row_h[key], "rowlabel", text=row_label[key]))
        if row_collapsible[key]:
            glyph = _fold_glyph(f"row:{key}" in collapsed)
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

    # EBK brackets in the value groups' gutters: prime-side rows are maps (⟨…]),
    # target-side rows are lists ([ … ]). Maps stack one per generator row.
    def bracket(bid, glyphs, group_key, y, h):
        gx, gw = col_x[group_key], col_w[group_key]
        cells.append(CellBox(f"bracket:{bid}:l", gx, y, BRACKET_W, h, "bracket", text=glyphs[0]))
        cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, y, BRACKET_W, h, "bracket", text=glyphs[1]))

    if row_open("mapping"):
        if col_open("primes"):
            for i in range(r):
                bracket(f"map:{i}", MAP_BRACKETS, "primes", map_top(i), ROW_H)
        if col_open("targets"):
            bracket("mapped", LIST_BRACKETS, "targets", row_y["mapping"], r * ROW_H)
    for key in ("tuning", "just", "retune"):
        if row_open(key):
            if col_open("primes"):
                bracket(f"{key}:map", MAP_BRACKETS, "primes", row_y[key], ROW_H)
            if col_open("targets"):
                bracket(f"{key}:list", LIST_BRACKETS, "targets", row_y[key], ROW_H)
    if row_open("damage") and col_open("targets"):
        bracket("damage", LIST_BRACKETS, "targets", row_y["damage"], ROW_H)

    # Shared axes. A multi-element group is one line that fans out at the near end
    # (from its node) into one line per element, runs through the data, then fans
    # back in at the far end to a foot extending a touch past the data — pinched at
    # both ends, bulging through the middle. Collapsing converges the per-element
    # lines onto the centre and shrinks both buses to nothing, so the renderer
    # animates the merge into a single straight gridline.
    bot_bus_y = total_h - FAN

    def column_axis(key, prefix, n, center_open):
        if key not in col_x:
            return
        cx = col_x[key] + col_w[key] / 2
        xs = [cx] * n if f"col:{key}" in collapsed else [center_open(i) for i in range(n)]
        for i in range(n):
            lines.append(Line(f"v:{prefix}:{i}", "v", xs[i], fanout_y, bot_bus_y - fanout_y))
        lines.append(Line(f"bus:{key}:top", "h", fanout_y, xs[0], xs[-1] - xs[0]))
        lines.append(Line(f"bus:{key}:bot", "h", bot_bus_y, xs[0], xs[-1] - xs[0]))
        lines.append(Line(f"trunk:{key}", "v", cx, branch_top_y, fanout_y - branch_top_y))
        lines.append(Line(f"foot:{key}", "v", cx, bot_bus_y, total_h - bot_bus_y))

    column_axis("primes", "prime", d, lambda p: prime_left(p) + COL_W / 2)
    column_axis("targets", "target", k, lambda j: target_left(j) + COL_W / 2)

    # generators column: a single vertical axis from its node down through the
    # mapping rows (it has no per-element fan — the generators are one column).
    gen_cx = gen_x + col_w.get("gens", GEN_W) / 2
    if "mapping" in row_y:
        gen_bot = map_top(r - 1) + ROW_H / 2 if row_open("mapping") else row_y["mapping"] + row_h["mapping"] / 2
        lines.append(Line("trunk:gens", "v", gen_cx, branch_top_y, gen_bot - branch_top_y))

    # mapping rows: the horizontal mirror of a column axis — fan out at the node
    # into one line per generator, fan back in on the right to a foot past the data.
    right_bus_x = total_w - FAN
    if "mapping" in row_y:
        folded = "row:mapping" in collapsed
        cy = row_y["mapping"] + row_h["mapping"] / 2
        ys = [cy] * r if folded else [map_top(i) + ROW_H / 2 for i in range(r)]
        left_bus_x = node_edge + FAN if (r > 1 and not folded) else node_edge
        for i in range(r):
            lines.append(Line(f"h:gen:{i}", "h", ys[i], left_bus_x, right_bus_x - left_bus_x))
        lines.append(Line("vbar:mapping:left", "v", left_bus_x, ys[0], ys[-1] - ys[0]))
        lines.append(Line("vbar:mapping:right", "v", right_bus_x, ys[0], ys[-1] - ys[0]))
        lines.append(Line("trunk:mapping", "h", cy, node_edge, left_bus_x - node_edge))
        lines.append(Line("foot:mapping", "h", cy, right_bus_x, total_w - right_bus_x))

    # tuning-family rows are each a single line (no sub-rows), present or collapsed
    for key in ("tuning", "just", "retune", "damage"):
        if key not in row_y:
            continue
        lines.append(Line(f"h:{key}", "h", row_y[key] + row_h[key] / 2, node_edge, total_w - node_edge))

    # #e0e0e0 panels behind each content group. A panel folds to zero size along
    # any collapsed axis (collapsing toward the band centre), so the renderer
    # animates it shrinking away to nothing — leaving only the band's gridline,
    # never a leftover grey strip.
    def panel(bid, ckey, rkey):
        if ckey not in col_x or rkey not in row_y:
            return
        col_c, row_c = f"col:{ckey}" in collapsed, f"row:{rkey}" in collapsed
        cw, ch, cx, cy = col_w[ckey], tile_h[rkey], col_x[ckey], tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        blocks.append(Block(bid, bx - px, by - py, w + 2 * px, h + 2 * py))

    panel("block:primes", "primes", "quantities")
    panel("block:targets", "targets", "quantities")
    panel("block:gens", "gens", "mapping")
    panel("block:mapping", "primes", "mapping")
    panel("block:mapped", "targets", "mapping")
    for key in ("tuning", "just", "retune"):
        panel(f"block:{key}:primes", "primes", key)
        panel(f"block:{key}:targets", "targets", key)
    panel("block:damage:targets", "targets", "damage")

    # quantity-name captions inside each tile (below its values + bottom frame),
    # toggled by names
    if show_captions:
        for (rkey, ckey), text in CAPTIONS.items():
            if row_open(rkey) and col_open(ckey):
                cy = row_y[rkey] + row_h[rkey] + row_frame[rkey]
                cells.append(CellBox(f"caption:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], CAPTION_H, "caption", text=text))

    # the mapping is a column of stacked maps, so it's enclosed by a top bracket
    # and a bottom curly brace spanning the matrix, drawn in its frame bands. The
    # top bracket sits at the tile top (a FRAME_GAP above the cells, since row_y is
    # inset by the frame); the brace sits a matching FRAME_GAP below the cells.
    map_top_y, brace_y = tile_top.get("mapping"), None
    if "mapping" in row_y:
        brace_y = row_y["mapping"] + row_h["mapping"] + FRAME_GAP
    if row_open("mapping") and col_open("primes"):
        gx, gw = col_x["primes"], col_w["primes"]
        cells.append(CellBox("ebktop:primes", gx, map_top_y, gw, FRAME_H, "ebktop"))
        cells.append(CellBox("ebkbrace:primes", gx, brace_y, gw, BRACE_H, "ebkbrace"))
    # the mapped list is a row of vectors: vertical rules separate the monzo
    # columns, and each column is marked with its own top bracket and bottom
    # brace — inset so they stop short of the rules rather than touching them
    if row_open("mapping") and col_open("targets"):
        mark_w = COL_W - 2 * MARK_INSET
        for j in range(k):
            mx = target_left(j) + MARK_INSET
            cells.append(CellBox(f"ebktop:mapped:{j}", mx, map_top_y, mark_w, FRAME_H, "ebktop"))
            cells.append(CellBox(f"ebkbrace:mapped:{j}", mx, brace_y, mark_w, BRACE_H, "ebkbrace"))
        for j in range(1, k):  # a rule on each interior column boundary
            cells.append(CellBox(f"sep:mapped:{j}", target_left(j) - SEP_W / 2, row_y["mapping"], SEP_W, r * ROW_H, "vbar"))

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
