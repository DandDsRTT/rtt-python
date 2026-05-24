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
COL_W = 30  # px per value column; == ROW_H so matrix cells are squares that tile
# the column (a shared-border grid, per the mockup); cents stack int-over-frac to fit
GAP = 14  # px between row/column groups
PAD = 4  # px a block extends around its cells
LABEL_W = 96  # row-label gutter width
HEADER_H = 22  # column-header height
GEN_W = 50  # generators column width
SPINE_W = 64  # quantities spine column width — sized to seat its "quantities"
# header without overflowing onto the generators column; carries only the
# column-axis vertical rule, no data cells in the default view
CTRL_W = 18  # domain expand (+) control gutter, just right of the primes block
BTN = 15  # px side of a domain +/− control — half the COL_W square mapping/prime cell
MINUS_REVEAL_H = 18  # height the removable prime's hover-minus rises above its header
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap
TOGGLE_INSET = 3  # small grey margin hugging a tile's top-left corner toggle (off the edges and content)
CAPTION_H = 16  # height of the quantity-name caption inside a tile (when names shown)
PRESELECT_H = 20  # height of a preselect chooser dropdown (when preselects shown)
PRESELECT_W = 124  # its width — fits "<choose temperament>" and caps the wide target tile
FRAME_H = 9  # height of a matrix's top-bracket framing band (the bar + down-ticks)
BRACE_H = 7  # depth of the bottom curly-brace band; kept shallow so the brace's
# short bounding dimension matches the value brackets' footprint (one EBK weight)
FRAME_GAP = 5  # gap between a framing band and the matrix cells, so they don't merge
BRACKET_W = 16  # gutter inside a value group for an EBK bracket (one side)
VAL_BRACKET_H = 16  # a single-row value bracket, kept short and centred in its
# ROW_H row so neighbouring rows' brackets keep a clear gap (the enclosing
# mapped-list [ ] is the tall exception and spans the whole matrix)
MARK_INSET = 8  # inset of a mapped column's top/bottom mark, so it clears the rules
SEP_W = 2  # width of a vertical rule between monzo columns (the renderer draws it
# as thick as a square bracket's main bar; this is just the cell it centres in)
MAP_BRACKETS = ("⟨", "]")  # ⟨ … ] for maps (covectors)
LIST_BRACKETS = ("[", "]")  # [ … ] for plain lists/matrices

# The counts row: each column's set cardinality, as (column key, symbol, name).
# The symbol+value (e.g. "r = 2") is the cell; the name ("rank") is its caption.
COUNTS = (
    ("gens", "r", "rank"),
    ("primes", "d", "dimensionality"),
    ("commas", "n", "nullity"),
    ("targets", "k", "target-interval count"),
)

# Quantity-name captions shown inside each (row, column) tile when names are on.
CAPTIONS = {
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "commas"): "comma basis",
    ("mapping", "targets"): "mapped target-interval list",
    ("tuning", "primes"): "tuning map",
    ("tuning", "commas"): "tempered comma size list",
    ("tuning", "targets"): "tempered target-interval size list",
    ("just", "primes"): "just tuning map",
    ("just", "commas"): "(just) comma size list",
    ("just", "targets"): "(just) target-interval size list",
    ("retune", "primes"): "retuning map",
    ("retune", "commas"): "comma error list",
    ("retune", "targets"): "target-interval error list",
    ("damage", "commas"): "comma damage list",
    ("damage", "targets"): "target-interval damage list",
    **{("counts", ckey): name for ckey, _sym, name in COUNTS},
}
CAPTIONED_ROWS = frozenset(row for row, _ in CAPTIONS)
FRAMED_ROWS = frozenset({"mapping"})  # multi-row matrices get a top bracket + bottom brace band

# The three "preselect" chooser dropdowns (settings["preselects"]) as (name, row,
# column): each is a quick menu for one of the things you actually choose, riding
# under its governing tile — the temperament under the mapping matrix, the tuning
# scheme under the tuning map, the target-interval set under the target list.
PRESELECTS = (
    ("temperament", "mapping", "primes"),
    ("tuning", "tuning", "primes"),
    ("target", "quantities", "targets"),
)
PRESELECT_ROWS = frozenset(row for _, row, _ in PRESELECTS)

# Every content tile (a row×column intersection) as (grey-panel id, row, column).
# Each gets a grey panel and a top-left fold toggle; the panel/toggle ids stay
# stable so the reconciling renderer can animate a single tile folding away.
TILES = (
    ("block:counts:gens", "counts", "gens"),
    ("block:counts:primes", "counts", "primes"),
    ("block:counts:targets", "counts", "targets"),
    ("block:primes", "quantities", "primes"),
    ("block:commas", "quantities", "commas"),
    ("block:targets", "quantities", "targets"),
    ("block:gens", "mapping", "gens"),
    ("block:mapping", "mapping", "primes"),
    ("block:comma_basis", "mapping", "commas"),
    ("block:mapped", "mapping", "targets"),
    ("block:tuning:primes", "tuning", "primes"),
    ("block:tuning:commas", "tuning", "commas"),
    ("block:tuning:targets", "tuning", "targets"),
    ("block:just:primes", "just", "primes"),
    ("block:just:commas", "just", "commas"),
    ("block:just:targets", "just", "targets"),
    ("block:retune:primes", "retune", "primes"),
    ("block:retune:commas", "retune", "commas"),
    ("block:retune:targets", "retune", "targets"),
    ("block:damage:commas", "damage", "commas"),
    ("block:damage:targets", "damage", "targets"),
)


def _cents(value) -> str:
    return f"{value:.2f}"


def _log_operand(ratio: str) -> str:
    """The operand of a just interval's log₂, e.g. ``3/1`` -> ``3`` (a bare prime,
    matching the mockup's ``log₂3``) and ``3/2`` -> ``(3/2)`` (parenthesised)."""
    num, _, den = ratio.partition("/")
    return num if den == "1" else f"({num}/{den})"


def _math_expr(operand: str, cents: float, show_value: bool) -> str:
    """A just value's closed form: ``log₂{operand}``, with ``= {octaves}`` appended
    when the value (quantities) is also shown — e.g. ``log₂3 = 1.585``. The decimal
    is in octaves (cents/1200) because that is what log₂ evaluates to."""
    expr = f"log₂{operand}"
    return f"{expr} = {cents / 1200:.3f}" if show_value else expr


def _title_w(title: str) -> int:
    """Approx rendered width of a 13px bold column title, so a collapsed column
    can fold to a strip that still fits its (horizontal) title without overflow."""
    return max(STRIP, len(title) * 8 + 10)


def _fold_glyph(is_collapsed: bool) -> str:
    """Material Icons name for the fold toggle: out-chevrons to expand a collapsed
    band, in-chevrons to collapse an expanded one."""
    return "unfold_more" if is_collapsed else "unfold_less"


def build(state, settings=None, collapsed=None,
          tuning_scheme=None, target_spec=None) -> Layout:
    if settings is None:
        settings = _default_settings()
    if tuning_scheme is None:
        tuning_scheme = service.DEFAULT_TUNING_SCHEME
    if target_spec is None:
        target_spec = service.DEFAULT_TARGET_SPEC
    collapsed = collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
    show_captions = settings["names"]  # the in-tile quantity captions; row/col titles always show
    show_preselects = settings["preselects"]  # the per-quantity chooser dropdowns
    show_counts = settings["counts"]
    show_temp = settings["temperament_boxes"]
    show_tuning = settings["tuning_boxes"]
    # The just tuning row alone has an exact closed form (log₂ of each prime/ratio);
    # with math expressions on it shows that instead of the cents decimal, paired
    # with its octave value when quantities is also on ("log₂3 = 1.585").
    show_math = settings["math_expressions"]
    show_quantities = settings["quantities"]
    # Row labels and column headers (and their gutters) are always present.
    label_w = LABEL_W
    header_h = HEADER_H
    d = state.d
    r = len(state.mapping)
    primes = service.standard_primes(d)
    gens = service.generators(state.mapping)
    targets = service.target_interval_set(target_spec, primes)
    k = len(targets)
    mapped = service.mapped_target_intervals(state.mapping, targets)
    tun = service.tuning(state.mapping, targets, tuning_scheme)
    comma_ratios = service.comma_ratios(state.comma_basis)
    nc = len(comma_ratios)  # comma count shown (>= nullity when a blank comma waits)
    ctun = service.tuning(state.mapping, comma_ratios)  # comma sizes (tempered ~0)

    # Column bands left-to-right: (key, natural width, present, collapsible).
    # Generators belong to the temperament; domain primes and targets are always
    # present. A collapsed column folds to a strip just wide enough to keep its
    # (horizontal) title readable, so it never overflows onto its neighbours. The
    # always-present domain + control rides just right of the primes block when it
    # is open; the − is a hover affordance on the (removable) highest-prime column.
    col_header = {"quantities": "quantities", "gens": "generators",
                  "primes": "domain primes", "commas": "commas", "targets": "target-intervals"}
    # The leftmost quantities column is the spine: a non-collapsible header + a
    # single vertical rule, the column-axis dual of the spine quantities row.
    # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
    # the value cells are inset by BRACKET_W within the group.
    col_bands = (
        ("quantities", SPINE_W, True, False),
        ("gens", GEN_W, show_temp, True),
        ("primes", 2 * BRACKET_W + d * COL_W, show_temp, True),
        ("commas", 2 * BRACKET_W + nc * COL_W, True, True),
        ("targets", 2 * BRACKET_W + k * COL_W, True, True),
    )
    # A fold-toggle node column sits between the row-label gutter and the content
    # (when names show); content starts past it with a clear gap so the tiles
    # never collide with the nodes. Row lines fan from the node's right edge so
    # their gaps match the columns'.
    node_x = label_w + GAP
    node_edge = node_x + TOGGLE  # the node's content-facing (right) edge
    content_x0 = node_x + TOGGLE + GAP

    # the domain and the comma basis each ride an expand (+) control in a gutter just
    # right of their (open) block — domain primes add a prime, commas add a comma
    col_x, col_w, col_collapsible = {}, {}, {}
    ctrl_x = {}
    x = content_x0
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        col_x[key] = x
        col_w[key] = _title_w(col_header[key]) if f"col:{key}" in collapsed else natural
        col_collapsible[key] = collapsible
        x += col_w[key]
        if key in ("primes", "commas") and f"col:{key}" not in collapsed:
            ctrl_x[key] = x + 6
            x = ctrl_x[key] + CTRL_W
        x += GAP
    total_w = x

    gen_x = col_x.get("gens", content_x0)
    primes_x = col_x.get("primes")  # None when the domain-primes column is hidden
    commas_x = col_x.get("commas")  # None when the commas column is hidden
    targets_x = col_x.get("targets")  # None when the target-intervals column is hidden

    def col_open(key):
        return key in col_x and f"col:{key}" not in collapsed

    header_y = 0
    col_node_y = header_h + (GAP - TOGGLE) / 2  # the column toggle sits just under the header text
    # Branching (trunk/bus/verticals) starts just below the column nodes so no
    # line pokes up past them; with names hidden it starts at the very top.
    branch_top_y = col_node_y + TOGGLE
    rows_top_y = branch_top_y + GAP  # top of the first row band (counts when shown, else quantities)
    # The grey tiles overhang their cells by PAD and sit over the gridlines, so the
    # *visible* fan segment runs from the bus only to the tile edge. Put each bus
    # midway between the node/foot edge and the tile edge (PAD inside the cell), so
    # the inner (bus->tile) and outer (node->bus) segments are equal: (GAP-PAD)/2.
    FAN = (GAP - PAD) / 2
    fanout_y = branch_top_y + FAN

    # The comma basis is d primes tall (a column per comma), so when its tile is
    # shown the mapping band grows from r rows (the stacked maps) to d to contain it;
    # the shorter maps and mapped list top-align within the taller band.
    commas_in_map = col_open("commas") and "tile:mapping:commas" not in collapsed
    map_band_rows = d if commas_in_map else r

    # Row bands top-to-bottom: (key, natural height, present, collapsible, label),
    # laid out by the same running-cursor rule as the columns. The spine
    # quantities row is not collapsible; the rest can fold to a strip.
    row_bands = (
        ("counts", ROW_H, show_counts, True, "counts"),
        ("quantities", ROW_H, True, False, "quantities"),
        ("mapping", map_band_rows * ROW_H, show_temp, True, "mapping"),
        ("tuning", ROW_H, show_tuning, True, "tuning"),
        ("just", ROW_H, show_tuning, True, "just tuning"),
        ("retune", ROW_H, show_tuning, True, "retuning"),
        ("damage", ROW_H, show_tuning, True, "damage"),
    )
    # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
    # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    tile_h, tile_top, row_frame = {}, {}, {}
    y = rows_top_y
    for key, natural, present, collapsible, label in row_bands:
        if not present:
            continue
        folded = f"row:{key}" in collapsed
        framed = key in FRAMED_ROWS and not folded
        # an open tile reserves a head strip at the top for its corner fold toggle,
        # so the toggle sits clear of the frame/cells (no strip when folded to a row)
        head = 0 if folded else TOGGLE + 2 * TOGGLE_INSET - PAD
        # framing bands stand off the cells by FRAME_GAP: a top bracket (FRAME_H)
        # and a taller bottom curly brace (BRACE_H, with room for its spike)
        top_frame = (FRAME_H + FRAME_GAP) if framed else 0
        bot_frame = (BRACE_H + FRAME_GAP) if framed else 0
        cap = CAPTION_H if (show_captions and key in CAPTIONED_ROWS and not folded) else 0
        # a preselect chooser reserves a band below the caption for its row
        pre = PRESELECT_H if (show_preselects and key in PRESELECT_ROWS and not folded) else 0
        row_h[key] = STRIP if folded else natural
        tile_top[key] = y
        row_y[key] = y + head + top_frame  # values sit below the toggle head and top frame
        row_frame[key] = bot_frame  # the caption sits below the bottom brace band
        row_label[key] = label
        row_collapsible[key] = collapsible
        tile_h[key] = head + top_frame + row_h[key] + bot_frame + cap + pre
        y += tile_h[key] + GAP
    total_h = y

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def tile_open(rkey, ckey):
        return row_open(rkey) and col_open(ckey) and f"tile:{rkey}:{ckey}" not in collapsed

    def prime_left(p):
        return primes_x + BRACKET_W + p * COL_W

    def comma_left(c):
        return commas_x + BRACKET_W + c * COL_W

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

    # counts row: each present column's set cardinality, centred over its values
    if row_open("counts"):
        cardinality = {"gens": r, "primes": d, "commas": state.n, "targets": k}
        for ckey, sym, _name in COUNTS:
            if tile_open("counts", ckey):
                cells.append(CellBox(f"count:{ckey}", col_x[ckey], row_y["counts"], col_w[ckey], ROW_H,
                                     "count", text=f"{sym} = {cardinality[ckey]}"))

    # quantities row: domain primes (+ controls) and target ratios (below the
    # tile's toggle head, like every other row's values)
    qy = row_y["quantities"]
    if tile_open("quantities", "primes"):
        for p in range(d):
            cells.append(CellBox(f"prime:{p}", prime_left(p), qy, COL_W, ROW_H, "prime", text=str(primes[p]), prime=p))
        # Only the highest prime is removable (shrink_domain trims the last), so its
        # − rides that column as a hover affordance: a zone spanning the header that
        # reveals the button just above it, clear of the editable mapping cell below.
        if d > 1:
            cells.append(CellBox("minus", prime_left(d - 1), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "minus"))
        cells.append(CellBox("plus", ctrl_x["primes"], qy + (ROW_H - BTN) // 2, BTN, BTN, "plus"))
    if tile_open("quantities", "commas"):
        for c in range(nc):
            cells.append(CellBox(f"comma:{c}", comma_left(c), qy, COL_W, ROW_H, "commaratio", text=comma_ratios[c], comma=c))
        # commas mirror the domain controls: + always adds a (blank) comma; the −
        # rides the last comma as a hover affordance, only when one can be removed
        if nc > 1:
            cells.append(CellBox("comma_minus", comma_left(nc - 1), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "comma_minus"))
        cells.append(CellBox("comma_plus", ctrl_x["commas"], qy + (ROW_H - BTN) // 2, BTN, BTN, "comma_plus"))
    if tile_open("quantities", "targets"):
        for j in range(k):
            cells.append(CellBox(f"target:{j}", target_left(j), qy, COL_W, ROW_H, "target", text=targets[j]))

    # generator ratios (aligned with the mapping rows they label) + the mapping
    # matrix and its mapped target-interval list
    if row_open("mapping"):
        if tile_open("mapping", "gens"):
            for i in range(r):
                cells.append(CellBox(f"gen:{i}", gen_x, map_top(i), GEN_W, ROW_H, "genratio", text=gens[i] if i < len(gens) else "", gen=i))
        for i in range(r):
            if tile_open("mapping", "primes"):
                for p in range(d):
                    cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), COL_W, ROW_H, "mapping", gen=i, prime=p))
            if tile_open("mapping", "targets"):
                for j in range(k):
                    cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped[i][j]), gen=i))
        # the comma basis: each comma is a d-tall monzo column (prime coefficients
        # down the rows), editable like the mapping — its dual
        if tile_open("mapping", "commas"):
            for c in range(nc):
                for p in range(d):
                    cells.append(CellBox(f"cell:comma:{p}:{c}", comma_left(c), row_y["mapping"] + p * ROW_H, COL_W, ROW_H, "commacell", text=str(state.comma_basis[c][p]), prime=p, comma=c))

    # the three value groups share an element name (for cell ids), a left-edge
    # accessor, and the operand of their just log₂ (a bare prime, or a comma/target
    # ratio); primes carry a map, commas and targets carry interval lists
    group_elem = {"primes": "prime", "commas": "comma", "targets": "target"}
    group_left = {"primes": prime_left, "commas": comma_left, "targets": target_left}
    group_operand = {
        "primes": lambda i: str(primes[i]),
        "commas": lambda i: _log_operand(comma_ratios[i]),
        "targets": lambda i: _log_operand(targets[i]),
    }

    # tuning rows over the primes, commas and targets (cents); each can collapse on
    # its own. Commas sit on the same footing as targets — they are just the dual
    # interval set — so the comma's tempered size is ~0 (it vanishes), with a real
    # just size and error. The just row alone has an exact closed form (log₂ of each
    # interval), so math expressions swaps its cents cells for that — paired with the
    # octave value when quantities is also on ("log₂3 = 1.585"), the same cell id and
    # box but a "mathexpr" kind the renderer swaps in.
    def tval_row(key, group, vals):
        if not tile_open(key, group):
            return
        y = row_y[key]
        for i, v in enumerate(vals):
            cid = f"{key}:{group_elem[group]}:{i}"
            x = group_left[group](i)
            if show_math and key == "just":
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(group_operand[group](i), v, show_quantities)))
            else:
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "tval", text=_cents(v)))

    tuning_data = {
        "tuning": (tun.tuning_map, ctun.tempered_targets, tun.tempered_targets),
        "just": (tun.just_map, ctun.just_targets, tun.just_targets),
        "retune": (tun.retuning_map, ctun.target_errors, tun.target_errors),
    }
    for key, (prime_vals, comma_vals, target_vals) in tuning_data.items():
        if row_open(key):
            tval_row(key, "primes", prime_vals)
            tval_row(key, "commas", comma_vals)
            tval_row(key, "targets", target_vals)
    if row_open("damage"):  # damage is over the commas and targets only (not the maps)
        tval_row("damage", "commas", ctun.target_damage)
        tval_row("damage", "targets", tun.target_damage)

    # EBK brackets in the value groups' gutters: prime-side rows are maps (⟨…]),
    # target-side rows are lists ([ … ]). Maps stack one per generator row.
    def bracket(bid, glyphs, group_key, y, h, *, fit=False):
        # value brackets are short and centred in their row (so stacked rows keep a
        # gap); the enclosing mapped-list [ ] passes fit=True to span the matrix.
        gx, gw = col_x[group_key], col_w[group_key]
        by, bh = (y, h) if fit else (y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H)
        cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0]))
        cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1]))

    if row_open("mapping"):
        if tile_open("mapping", "primes"):
            for i in range(r):
                bracket(f"map:{i}", MAP_BRACKETS, "primes", map_top(i), ROW_H)
        if tile_open("mapping", "commas"):  # the comma basis is a list of monzos: a [ ] spanning d rows
            bracket("comma_basis", LIST_BRACKETS, "commas", row_y["mapping"], d * ROW_H, fit=True)
        if tile_open("mapping", "targets"):
            bracket("mapped", LIST_BRACKETS, "targets", row_y["mapping"], r * ROW_H, fit=True)
    for key in ("tuning", "just", "retune"):
        if row_open(key):
            if tile_open(key, "primes"):
                bracket(f"{key}:map", MAP_BRACKETS, "primes", row_y[key], ROW_H)
            if tile_open(key, "commas"):
                bracket(f"{key}:commalist", LIST_BRACKETS, "commas", row_y[key], ROW_H)
            if tile_open(key, "targets"):
                bracket(f"{key}:list", LIST_BRACKETS, "targets", row_y[key], ROW_H)
    if tile_open("damage", "commas"):
        bracket("damage:commalist", LIST_BRACKETS, "commas", row_y["damage"], ROW_H)
    if tile_open("damage", "targets"):
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
    column_axis("commas", "comma", nc, lambda c: comma_left(c) + COL_W / 2)
    column_axis("targets", "target", k, lambda j: target_left(j) + COL_W / 2)

    # quantities spine column: a single vertical rule the full height of the grid
    # (the column-axis dual of the h:quantities spine row); no per-element fan
    # since the spine carries no data in the default view
    if "quantities" in col_x:
        q_cx = col_x["quantities"] + col_w["quantities"] / 2
        lines.append(Line("trunk:quantities", "v", q_cx, branch_top_y, total_h - branch_top_y))

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

    # the quantities spine row: a single horizontal rule across the grid (the
    # row-axis counterpart of the quantities spine column) that the data blocks
    # hang off; always present since the spine row never collapses
    if "quantities" in row_y:
        lines.append(Line("h:quantities", "h", row_y["quantities"] + row_h["quantities"] / 2, node_edge, total_w - node_edge))

    # single-value rows (counts + the tuning family) are each one line (no
    # sub-rows), present or collapsed — so a collapsed one still leaves a gridline
    for key in ("counts", "tuning", "just", "retune", "damage"):
        if key not in row_y:
            continue
        lines.append(Line(f"h:{key}", "h", row_y[key] + row_h[key] / 2, node_edge, total_w - node_edge))

    # #e0e0e0 panels behind each content group. A panel folds to zero size along
    # any collapsed axis (collapsing toward the band centre), so the renderer
    # animates it shrinking away to nothing — leaving only the band's gridline,
    # never a leftover grey strip.
    # Value-area height of a (row, col) tile. Almost every tile is its row's height;
    # the comma basis is the exception — d primes tall where the maps are only r —
    # so within the (taller) mapping band each column's panel/caption/frame still
    # hugs its own matrix rather than the band's full height.
    def col_value_h(rkey, ckey):
        if rkey == "mapping" and "row:mapping" not in collapsed:
            return (d if ckey == "commas" else r) * ROW_H
        return row_h[rkey]

    def tile_height(rkey, ckey):  # full tile = head + frames + caption + values
        return tile_h[rkey] - row_h[rkey] + col_value_h(rkey, ckey)

    def panel(bid, ckey, rkey):
        if ckey not in col_x or rkey not in row_y:
            return
        # a folded tile collapses both ways at once, so it shrinks to a point at
        # its centre — like a row+column collapse confined to this one tile
        tile_c = f"tile:{rkey}:{ckey}" in collapsed
        col_c = f"col:{ckey}" in collapsed or tile_c
        row_c = f"row:{rkey}" in collapsed or tile_c
        cw, ch, cx, cy = col_w[ckey], tile_height(rkey, ckey), col_x[ckey], tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        blocks.append(Block(bid, bx - px, by - py, w + 2 * px, h + 2 * py))

    for bid, rkey, ckey in TILES:
        panel(bid, ckey, rkey)

    # quantity-name captions inside each tile (below its values + bottom frame),
    # toggled by names
    if show_captions:
        for (rkey, ckey), text in CAPTIONS.items():
            if tile_open(rkey, ckey):
                cy = row_y[rkey] + col_value_h(rkey, ckey) + row_frame[rkey]
                cells.append(CellBox(f"caption:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], CAPTION_H, "caption", text=text))

    # preselect chooser dropdowns, in the reserved band below each governing tile
    # (and below its caption when names show). The tuning/target choosers carry the
    # live selection; the temperament chooser is a placeholder (it loads, not mirrors).
    if show_preselects:
        preselect_text = {"temperament": "", "tuning": tuning_scheme, "target": target_spec}
        for name, rkey, ckey in PRESELECTS:
            if not tile_open(rkey, ckey):
                continue
            py = row_y[rkey] + row_h[rkey] + row_frame[rkey]
            if show_captions and (rkey, ckey) in CAPTIONS:
                py += CAPTION_H
            pw = min(col_w[ckey], PRESELECT_W)
            cells.append(CellBox(f"preselect:{name}", col_x[ckey], py, pw, PRESELECT_H, "preselect", text=preselect_text[name]))

    # the mapping is a column of stacked maps, so it's enclosed by a top bracket
    # and a bottom curly brace spanning the matrix, drawn in its frame bands. Both
    # stand off the cells by FRAME_GAP — the top bracket just above row 0 (below the
    # toggle head), the brace a matching gap below the last row. Each column's brace
    # hugs its own matrix height (the comma basis runs d rows deep, the maps and
    # mapped list only r), so they stagger within the taller band.
    map_top_y = row_y["mapping"] - FRAME_H - FRAME_GAP if "mapping" in row_y else None

    def map_brace_y(ckey):
        return row_y["mapping"] + col_value_h("mapping", ckey) + FRAME_GAP

    if tile_open("mapping", "primes"):
        gx, gw = col_x["primes"], col_w["primes"]
        cells.append(CellBox("ebktop:primes", gx, map_top_y, gw, FRAME_H, "ebktop"))
        cells.append(CellBox("ebkbrace:primes", gx, map_brace_y("primes"), gw, BRACE_H, "ebkbrace"))

    # the mapped list and comma basis are rows/grids of vectors: vertical rules
    # separate the monzo columns, and each column is marked with its own top bracket
    # and bottom brace — inset so they stop short of the rules rather than touching.
    def monzo_list_marks(name, ckey, left, n_cols, n_rows):
        if not tile_open("mapping", ckey):
            return
        mark_w = COL_W - 2 * MARK_INSET
        for c in range(n_cols):
            mx = left(c) + MARK_INSET
            cells.append(CellBox(f"ebktop:{name}:{c}", mx, map_top_y, mark_w, FRAME_H, "ebktop"))
            cells.append(CellBox(f"ebkbrace:{name}:{c}", mx, map_brace_y(ckey), mark_w, BRACE_H, "ebkbrace"))
        for c in range(1, n_cols):  # a rule on each interior column boundary
            cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, row_y["mapping"], SEP_W, n_rows * ROW_H, "vbar"))

    monzo_list_marks("comma_basis", "commas", comma_left, nc, d)
    monzo_list_marks("mapped", "targets", target_left, k, r)

    # a per-tile fold toggle inset into each content tile's top-left corner: it
    # sits in the head strip reserved above the content, TOGGLE_INSET in from the
    # grey panel's top-left, so it never touches an edge or overlaps the frame.
    # Present whenever the tile's row and column bands are open — it stays put when
    # only the tile is folded, so the tile can be re-expanded.
    for _bid, rkey, ckey in TILES:
        if rkey in row_y and ckey in col_x and row_open(rkey) and col_open(ckey):
            glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in collapsed)
            cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                 col_x[ckey] - PAD + TOGGLE_INSET, tile_top[rkey] - PAD + TOGGLE_INSET,
                                 TOGGLE, TOGGLE, "tiletoggle", text=glyph))

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
