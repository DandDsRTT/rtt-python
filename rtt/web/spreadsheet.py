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
HEADER_H = 36  # column-header height — two text lines tall, so a long collapsed
# title (e.g. "other intervals of interest") wraps centered onto a second line
# instead of forcing an over-wide one-line strip; short titles centre as one line
SPINE_W = 64  # quantities spine column width — sized to seat its "quantities"
# header without overflowing onto the generators column; carries only the
# column-axis vertical rule, no data cells in the default view
CTRL_W = 18  # domain expand (+) control gutter, just right of the primes block
BTN = 15  # px side of a domain +/− control — half the COL_W square mapping/prime cell
MINUS_REVEAL_H = 18  # height the removable prime's hover-minus rises above its header
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TITLE_WRAP_W = 140  # cap on a collapsed column's title strip: a title wider than this
# wraps onto the header band's second line (HEADER_H is two lines) instead of folding
# to an over-wide one-line ribbon — e.g. "other intervals of interest"
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap
TOGGLE_INSET = 3  # small grey margin hugging a tile's top-left corner toggle (off the edges and content)
CAPTION_FONT = 9  # px font size of the quantity-name caption (matches the mockup —
# ~0.2 of the cell height; the CSS .rtt-caption must use the same size)
CAPTION_LINE = 11  # px per wrapped caption line (font size + leading)
PRESELECT_H = 20  # height of a preselect chooser dropdown (when preselects shown)
PRESELECT_W = 124  # its width — fits "<choose temperament>" and caps the wide target tile
PTEXT_H = 18  # height of the plain-text value band (the boxed EBK string) below a tile
SYMBOL_H = 18  # height of the quantity-symbol glyph above the caption (when symbols shown)
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
    ("vectors", "primes"): "domain basis",
    ("vectors", "commas"): "comma basis",
    ("vectors", "targets"): "target-interval list",
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "commas"): "mapped comma list",
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
    # other intervals of interest mirror the targets, minus the damage row
    ("mapping", "interest"): "mapped interval list",
    ("tuning", "interest"): "tempered interval size list",
    ("just", "interest"): "(just) interval size list",
    ("retune", "interest"): "interval error list",
}
CAPTIONED_ROWS = frozenset(row for row, _ in CAPTIONS)
# The bold quantity symbol shown above each name when symbols is on: bold-italic
# for the maps (covectors), bold-upright for the vectors and matrices. The comma
# column has no dedicated letters — everything but the basis 𝐂 (in the interval-
# vectors row) is a product with it: the mapped comma list 𝐌𝐂 and the comma sizes
# 𝒕𝐂, 𝒋𝐂, 𝒓𝐂. The comma damage list (|error|, no product form) and the "other
# intervals of interest" column carry no symbol.
SYMBOLS = {
    ("vectors", "commas"): "𝐂",
    ("mapping", "primes"): "𝐌",
    ("mapping", "commas"): "𝐌𝐂",
    ("mapping", "targets"): "𝐘",
    ("tuning", "primes"): "𝒕",
    ("tuning", "commas"): "𝒕𝐂",
    ("tuning", "targets"): "𝐚",
    ("just", "primes"): "𝒋",
    ("just", "commas"): "𝒋𝐂",
    ("just", "targets"): "𝐨",
    ("retune", "primes"): "𝒓",
    ("retune", "commas"): "𝒓𝐂",
    ("retune", "targets"): "𝐞",
    ("damage", "targets"): "𝐝",
}
SYMBOLED_ROWS = frozenset(row for row, _ in SYMBOLS)  # rows that reserve a symbol slot
# multi-row matrices reserve top/bottom frame bands for their EBK marks: the mapping
# for its spanning bracket+brace, the interval vectors for the per-column ket marks
FRAMED_ROWS = frozenset({"mapping", "vectors"})

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

# Mnemonics: the letter of a caption that spells the quantity's symbol, shown
# underlined when mnemonics is on — a memory aid linking the name to its symbol
# (e.g. "tuning map" -> t, "target-interval damage list" -> d). Each entry names
# the word whose first letter is underlined. The mapped list (Y) and tempered
# size list (a) use symbols absent from their names, so they carry no underline.
MNEMONICS = {
    ("mapping", "primes"): "mapping",   # M
    ("tuning", "primes"): "tuning",     # t
    ("just", "primes"): "just",         # j
    ("just", "targets"): "just",        # j̄ (just target-interval sizes)
    ("retune", "primes"): "retuning",   # r
    ("retune", "targets"): "error",     # e
    ("damage", "targets"): "damage",    # d
}

# Each quantity's defining equation continues its symbol (see SYMBOLS): the mockup's
# "symbols section" from the first "=" on, appended to the symbol when equivalences
# is on so the line reads e.g. "𝒕 = 𝒈𝐌". Glyphs match SYMBOLS — bold-italic maps,
# bold-upright matrices (𝐓 = the target-interval matrix); operators stay upright.
# Only terms buildable from shipped features appear, so the superspace/canonical-
# form tails (the tuning map's "= B_Ls 𝒕_L", "𝐌 = 𝐅𝐌_c", "𝒋 = B_Ls 𝒋_L") are
# dropped — the mapping and just tuning maps thus carry no continuation yet.
EQUIVALENCES = {
    ("mapping", "targets"): " = 𝐌𝐓",
    ("tuning", "primes"): " = 𝒈𝐌",
    ("tuning", "targets"): " = 𝒕𝐓",
    ("just", "targets"): " = 𝒋𝐓",
    ("retune", "primes"): " = 𝒕 − 𝒋",
    ("retune", "targets"): " = 𝒓𝐓",
    ("damage", "targets"): " = |𝐞|diag(𝐰)",
}

# Always-present content tiles (a row×column intersection) as (grey-panel id, row,
# column). Each gets a grey panel and a top-left fold toggle; the panel/toggle ids
# stay stable so the reconciling renderer can animate a single tile folding away.
# The "other intervals of interest" column adds its own tiles dynamically (only
# when the user has entered intervals) — see build().
TILES = (
    ("block:counts:gens", "counts", "gens"),
    ("block:counts:primes", "counts", "primes"),
    ("block:counts:targets", "counts", "targets"),
    ("block:primes", "quantities", "primes"),
    ("block:commas", "quantities", "commas"),
    ("block:targets", "quantities", "targets"),
    ("block:vec:quantities", "vectors", "quantities"),
    ("block:vec:primes", "vectors", "primes"),
    ("block:vec:commas", "vectors", "commas"),
    ("block:vec:targets", "vectors", "targets"),
    ("block:gens", "mapping", "quantities"),
    ("block:selfmap", "mapping", "gens"),
    ("block:mapping", "mapping", "primes"),
    ("block:mapped_comma", "mapping", "commas"),
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

# Cell kinds the value-display toggles filter out. "gridded values" hides
# everything a tile holds besides its fold toggle, name caption and plain-text
# value box: the value numbers (including the just row's "mathexpr" log₂ form),
# the EBK marks framing them, and the domain/comma ± controls. (Gridded off with
# plain text on leaves just the inline string — the two value views are independent.)
GRIDDED_KINDS = frozenset({
    "prime", "target", "commaratio", "genratio", "mapping", "mapped", "commacell", "static",
    "vec", "tval", "mathexpr",
    "bracket", "ebktop", "ebkbrace", "vbar", "minus", "plus", "comma_minus", "comma_plus",
})
# "quantities" (general) narrows that to the body quantity values and the EBK
# marks framing them -- the matrix, mapped list, comma basis, generator ratios
# and tuning cents -- leaving the quantities-row headers (the prime / comma /
# target ratios) and the domain/comma controls in place. It does NOT drop the
# just row's "mathexpr" cells: a log₂ expression is not a bare number, so it
# stays (math_expressions' own show_value logic trims its "= value" tail instead).
BODY_VALUE_KINDS = frozenset({
    "genratio", "mapping", "mapped", "commacell", "static", "vec", "tval",
    "bracket", "ebktop", "ebkbrace", "vbar",
})


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
    """Width of a collapsed column's title strip. A short title gets a strip just wide
    enough for its single 13px bold line; a long one is capped at TITLE_WRAP_W so it
    wraps to ~2 lines (matching the mockup) rather than folding to an over-wide ribbon."""
    return max(STRIP, min(len(title) * 8 + 10, TITLE_WRAP_W))


def _fold_glyph(is_collapsed: bool) -> str:
    """Material Icons name for the fold toggle: out-chevrons to expand a collapsed
    band, in-chevrons to collapse an expanded one."""
    return "unfold_more" if is_collapsed else "unfold_less"


def _caption_lines(text: str, width: float) -> int:
    """How many lines ``text`` wraps to in a ``width``-px caption at CAPTION_FONT,
    so the tile can grow tall enough to hold it (rather than letting it spill, as a
    narrow column's long name would). A greedy word wrap with a conservative serif
    char-width estimate; an over-long word breaks across lines itself."""
    max_chars = max(1, int((width - 4) / (CAPTION_FONT * 0.52)))  # -4: a little padding
    lines, cur = 1, 0
    for word in text.split():
        wlen = len(word)
        if cur and cur + 1 + wlen > max_chars:  # word won't fit on the current line
            lines, cur = lines + 1, 0
        if cur == 0 and wlen > max_chars:  # the word itself overflows one line
            lines += (wlen - 1) // max_chars
            cur = (wlen - 1) % max_chars + 1
        else:
            cur += (1 if cur else 0) + wlen
    return lines


def build(state, settings=None, collapsed=None,
          tuning_scheme=None, target_spec=None, interest=()) -> Layout:
    if settings is None:
        settings = _default_settings()
    if tuning_scheme is None:
        tuning_scheme = service.DEFAULT_TUNING_SCHEME
    if target_spec is None:
        target_spec = service.DEFAULT_TARGET_SPEC
    collapsed = collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
    show_captions = settings["names"]  # the in-tile quantity captions; row/col titles always show
    show_mnemonics = show_captions and settings["mnemonics"]  # underline a caption's symbol letter
    show_equiv = settings["equivalences"]  # extend the symbol line with the defining equation
    show_preselects = settings["preselects"]  # the per-quantity chooser dropdowns
    show_counts = settings["counts"]
    show_ptext = settings["plain_text_values"]  # the boxed EBK string under each tile
    show_symbols = settings["symbols"]  # the in-tile quantity symbols, stacked above the captions
    show_temp = settings["temperament_boxes"]
    show_tuning = settings["tuning_boxes"]
    # Value-display toggles. "gridded values" is the master switch: with it off
    # (and plain-text values not yet built) every value a tile holds -- the numbers,
    # the EBK marks framing them, the domain/comma ± controls -- is filtered out
    # (see GRIDDED_KINDS at the end of build), leaving the tiles empty but for their
    # fold toggles, name captions and (when on) plain-text value boxes. "quantities"
    # (general) narrows that to the
    # body values (BODY_VALUE_KINDS); "domain_quantities" (specific) governs the
    # quantities row and its spine column. The just row alone has an exact closed
    # form, so "math_expressions" renders log₂ of each interval there instead of
    # cents -- paired with its octave value when "quantities" is also on
    # ("log₂3 = 1.585").
    gridded = settings["gridded_values"]
    show_quantities = settings["quantities"]
    show_domain_quantities = settings["domain_quantities"]
    show_math = settings["math_expressions"]
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
    target_vectors = service.target_interval_monzos(targets, d)  # k monzos, each d-tall
    tun = service.tuning(state.mapping, targets, tuning_scheme)
    comma_ratios = service.comma_ratios(state.comma_basis)
    nc = len(comma_ratios)  # comma count shown (>= nullity when a blank comma waits)
    mapped_commas = service.mapped_commas(state.mapping, state.comma_basis)  # M·commas = 0 (vanish)
    ctun = service.tuning(state.mapping, comma_ratios)  # comma sizes (tempered ~0)
    # other intervals of interest: a user-supplied set (empty until they enter some),
    # sized under the same scheme; it carries no damage row and contributes tiles only
    # when populated, so an empty column adds no panels or fold toggles — just its
    # header and a single straight axis rule.
    interest = tuple(interest)
    mi = len(interest)
    interest_mapped = service.mapped_target_intervals(state.mapping, interest)
    itun = service.tuning(state.mapping, interest, tuning_scheme)  # interest sizes
    interest_tiles = () if not interest else (
        ("block:interest", "quantities", "interest"),
        ("block:imapped", "mapping", "interest"),
        ("block:tuning:interest", "tuning", "interest"),
        ("block:just:interest", "just", "interest"),
        ("block:retune:interest", "retune", "interest"),
    )
    tiles = TILES + interest_tiles

    # Column bands left-to-right: (key, natural width, present, collapsible).
    # Each set-column belongs to a box toggle: generators, the domain primes and
    # the commas are the temperament's (shown with temperament_boxes), target-
    # intervals are the tuning's (shown with tuning_boxes) -- turning a box off
    # takes its whole column with it, including the other family's cells that ride
    # in it (e.g. the tuning maps over primes, or the mapped target-interval list
    # over targets). A collapsed column folds to a strip just wide enough to keep
    # its (horizontal) title readable, so it never overflows onto its neighbours.
    # The domain/comma + controls ride just right of their blocks when open; each −
    # is a hover affordance on the removable highest-prime / last-comma column.
    col_header = {"quantities": "quantities", "gens": "generators",
                  "primes": "domain primes", "commas": "commas", "targets": "target-intervals",
                  "interest": "other intervals of interest"}
    # The leftmost quantities column is the spine: a non-collapsible header + a
    # single vertical rule, the column-axis dual of the spine quantities row.
    # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
    # the value cells are inset by BRACKET_W within the group.
    col_bands = (
        ("quantities", SPINE_W, show_domain_quantities, False),
        ("gens", 2 * BRACKET_W + r * COL_W, show_temp, True),
        ("primes", 2 * BRACKET_W + d * COL_W, show_temp, True),
        ("commas", 2 * BRACKET_W + nc * COL_W, show_temp, True),
        ("targets", 2 * BRACKET_W + k * COL_W, show_tuning, True),
        # an empty interest column has no cells to size it, so it takes its title's
        # (wrapped, two-line) strip width — the narrow header the mockup shows — rather
        # than a bare bracket-gutter stub the long title would overflow
        ("interest", 2 * BRACKET_W + mi * COL_W if mi else _title_w(col_header["interest"]),
         show_tuning, True),
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
    interest_x = col_x.get("interest")  # None when the interest column is hidden

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

    # Row bands top-to-bottom: (key, natural height, present, collapsible, label),
    # laid out by the same running-cursor rule as the columns. The spine
    # quantities row is not collapsible, but the specific "quantities" toggle hides
    # it (and its column, built elsewhere); the rest can fold to a strip.
    row_bands = (
        ("counts", ROW_H, show_counts, True, "counts"),
        ("quantities", ROW_H, show_domain_quantities, False, "quantities"),
        ("vectors", d * ROW_H, True, True, "interval vectors"),
        ("mapping", r * ROW_H, show_temp, True, "mapping"),
        ("tuning", ROW_H, show_tuning, True, "tuning"),
        ("just", ROW_H, show_tuning, True, "just tuning"),
        ("retune", ROW_H, show_tuning, True, "retuning"),
        ("damage", ROW_H, show_tuning, True, "damage"),
    )
    # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
    # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    tile_h, tile_top, row_frame, row_sym, row_cap, row_pre = {}, {}, {}, {}, {}, {}

    def caption_band(key, folded):
        # the row's caption band is sized to its tallest (wrapped) caption, so the
        # longest name fits within its tile rather than spilling off a narrow column
        if not (show_captions and key in CAPTIONED_ROWS and not folded):
            return 0
        lines = [_caption_lines(CAPTIONS[(key, c)], col_w[c]) for c in col_x
                 if (key, c) in CAPTIONS and col_open(c) and f"tile:{key}:{c}" not in collapsed]
        return max(lines, default=1) * CAPTION_LINE
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
        cap = caption_band(key, folded)
        # the symbol line reserves a slot above the caption for every symboled row;
        # equivalences extends that same line (the "= …" continuation) rather than
        # adding a band, so it reserves the slot too even when symbols itself is off
        sym = SYMBOL_H if ((show_symbols or show_equiv) and key in SYMBOLED_ROWS and not folded) else 0
        # below the caption a tile reserves bands for the preselect chooser (its
        # row) and the plain-text value box, stacked in that order
        pre = PRESELECT_H if (show_preselects and key in PRESELECT_ROWS and not folded) else 0
        ptext = PTEXT_H if (show_ptext and not folded) else 0
        row_h[key] = STRIP if folded else natural
        tile_top[key] = y
        row_y[key] = y + head + top_frame  # values sit below the toggle head and top frame
        row_frame[key] = bot_frame  # the symbol/caption stack sits below the bottom brace band
        row_sym[key] = sym  # the caption (and bands below it) sit below the symbol slot
        row_cap[key] = cap  # the preselect/plain-text bands sit below the caption
        row_pre[key] = pre  # ...and the plain-text band sits below the preselect band
        row_label[key] = label
        row_collapsible[key] = collapsible
        tile_h[key] = head + top_frame + row_h[key] + bot_frame + sym + cap + pre + ptext
        y += tile_h[key] + GAP
    total_h = y

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def tile_open(rkey, ckey):
        return row_open(rkey) and col_open(ckey) and f"tile:{rkey}:{ckey}" not in collapsed

    def prime_left(p):
        return primes_x + BRACKET_W + p * COL_W

    def gen_left(g):
        return gen_x + BRACKET_W + g * COL_W

    def comma_left(c):
        return commas_x + BRACKET_W + c * COL_W

    def target_left(j):
        return targets_x + BRACKET_W + j * COL_W

    def interest_left(i):
        return interest_x + BRACKET_W + i * COL_W

    def map_top(i):
        return row_y["mapping"] + i * ROW_H

    def vec_top(p):  # the y of monzo component p in the d-tall interval-vectors row
        return row_y["vectors"] + p * ROW_H

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
    # tile's toggle head, like every other row's values). The whole row -- its
    # headers and the domain/comma ± controls riding it -- answers to the specific
    # "quantities" toggle, which drops it from row_y via its present flag.
    if "quantities" in row_y:
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
        if tile_open("quantities", "interest"):  # the user's other intervals of interest (ratios)
            for i in range(mi):
                cells.append(CellBox(f"interest:{i}", interest_left(i), qy, COL_W, ROW_H, "target", text=interest[i]))

    # generator ratios (aligned with the mapping rows they label) + the mapping
    # matrix and its mapped target-interval list
    if row_open("mapping"):
        # the generators list the mapping's rows: a vertical ratio list in the
        # quantities spine column (the dual of the mapping-over-generators identity)
        if tile_open("mapping", "quantities"):
            for i in range(r):
                cells.append(CellBox(f"gen:{i}", col_x["quantities"], map_top(i), col_w["quantities"], ROW_H, "genratio", text=gens[i] if i < len(gens) else "", gen=i))
        # M over the generators is the identity (each generator maps to itself): a
        # read-only stack of maps in the generators column, dual to the list above
        if tile_open("mapping", "gens"):
            for i in range(r):
                for j in range(r):
                    cells.append(CellBox(f"cell:selfmap:{i}:{j}", gen_left(j), map_top(i), COL_W, ROW_H, "static", text="1" if i == j else "0"))
        for i in range(r):
            if tile_open("mapping", "primes"):
                for p in range(d):
                    cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), COL_W, ROW_H, "mapping", gen=i, prime=p))
            if tile_open("mapping", "targets"):
                for j in range(k):
                    cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped[i][j]), gen=i))
            if tile_open("mapping", "interest"):  # interest mapped through M, like the targets
                for ii in range(mi):
                    cells.append(CellBox(f"cell:imapped:{i}:{ii}", interest_left(ii), map_top(i), COL_W, ROW_H, "mapped", text=str(interest_mapped[i][ii]), gen=i))
            # the comma basis mapped through M — it vanishes to 0 (parallel to the
            # mapped target list); the raw basis lives in the interval-vectors row
            if tile_open("mapping", "commas"):
                for c in range(nc):
                    cells.append(CellBox(f"cell:mapped_comma:{i}:{c}", comma_left(c), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped_commas[i][c]), gen=i))

    # interval-vectors row: each column's intervals as monzos (d-tall columns over
    # the domain primes), on the same prime/comma/target axes as the quantities row.
    # The domain primes are their own basis, so they read as the d x d identity; the
    # comma basis is the editable raw monzos (the mapping's dual); the targets become
    # a d x k matrix of monzo columns.
    if row_open("vectors"):
        # the domain basis lists the interval-vectors' rows: the d primes in a vertical
        # column in the quantities spine (the dual index, as the generators label the
        # mapping rows). The same boxed primes the quantities row heads its columns with.
        if tile_open("vectors", "quantities"):
            for p in range(d):
                cells.append(CellBox(f"basis:{p}", col_x["quantities"], vec_top(p), col_w["quantities"], ROW_H, "prime", text=str(primes[p]), prime=p))
        if tile_open("vectors", "primes"):
            for e in range(d):
                for p in range(d):
                    cells.append(CellBox(f"cell:vec:primes:{e}:{p}", prime_left(e), vec_top(p), COL_W, ROW_H, "vec", text=("1" if e == p else "0")))
        if tile_open("vectors", "commas"):
            for c in range(nc):
                for p in range(d):
                    cells.append(CellBox(f"cell:comma:{p}:{c}", comma_left(c), vec_top(p), COL_W, ROW_H, "commacell", text=str(state.comma_basis[c][p]), prime=p, comma=c))
        if tile_open("vectors", "targets"):
            for j in range(k):
                for p in range(d):
                    cells.append(CellBox(f"cell:vec:targets:{j}:{p}", target_left(j), vec_top(p), COL_W, ROW_H, "vec", text=str(target_vectors[j][p])))

    # the three value groups share an element name (for cell ids), a left-edge
    # accessor, and the operand of their just log₂ (a bare prime, or a comma/target
    # ratio); primes carry a map, commas and targets carry interval lists
    group_elem = {"primes": "prime", "commas": "comma", "targets": "target", "interest": "interest"}
    group_left = {"primes": prime_left, "commas": comma_left, "targets": target_left,
                  "interest": interest_left}
    group_operand = {
        "primes": lambda i: str(primes[i]),
        "commas": lambda i: _log_operand(comma_ratios[i]),
        "targets": lambda i: _log_operand(targets[i]),
        "interest": lambda i: _log_operand(interest[i]),
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
        "tuning": (tun.tuning_map, ctun.tempered_targets, tun.tempered_targets, itun.tempered_targets),
        "just": (tun.just_map, ctun.just_targets, tun.just_targets, itun.just_targets),
        "retune": (tun.retuning_map, ctun.target_errors, tun.target_errors, itun.target_errors),
    }
    for key, (prime_vals, comma_vals, target_vals, interest_vals) in tuning_data.items():
        if row_open(key):
            tval_row(key, "primes", prime_vals)
            tval_row(key, "commas", comma_vals)
            tval_row(key, "targets", target_vals)
            tval_row(key, "interest", interest_vals)
    if row_open("damage"):  # damage is over the commas and targets only (not the maps or interest)
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
        # the gens identity and the primes mapping are stacks of maps: ⟨ … ] per row
        for bid, ckey in (("selfmap", "gens"), ("map", "primes")):
            if tile_open("mapping", ckey):
                for i in range(r):
                    bracket(f"{bid}:{i}", MAP_BRACKETS, ckey, map_top(i), ROW_H)
        if tile_open("mapping", "commas"):  # the mapped (vanishing) comma list: a [ ] over r rows
            bracket("mapped_comma", LIST_BRACKETS, "commas", row_y["mapping"], r * ROW_H, fit=True)
        if tile_open("mapping", "targets"):
            bracket("mapped", LIST_BRACKETS, "targets", row_y["mapping"], r * ROW_H, fit=True)
        if mi and tile_open("mapping", "interest"):  # interest mapped list, like the targets
            bracket("imapped", LIST_BRACKETS, "interest", row_y["mapping"], r * ROW_H, fit=True)
    if row_open("vectors"):  # each group is a list of monzos: a [ ] spanning the d components
        for group in ("primes", "commas", "targets"):
            if tile_open("vectors", group):
                bracket(f"vec:{group}", LIST_BRACKETS, group, row_y["vectors"], d * ROW_H, fit=True)
    for key in ("tuning", "just", "retune"):
        if row_open(key):
            if tile_open(key, "primes"):
                bracket(f"{key}:map", MAP_BRACKETS, "primes", row_y[key], ROW_H)
            if tile_open(key, "commas"):
                bracket(f"{key}:commalist", LIST_BRACKETS, "commas", row_y[key], ROW_H)
            if tile_open(key, "targets"):
                bracket(f"{key}:list", LIST_BRACKETS, "targets", row_y[key], ROW_H)
            if mi and tile_open(key, "interest"):
                bracket(f"{key}:ilist", LIST_BRACKETS, "interest", row_y[key], ROW_H)
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
        if n == 0:  # an empty interval set (interest, before any are entered) is one straight axis
            lines.append(Line(f"trunk:{key}", "v", cx, branch_top_y, fanout_y - branch_top_y))
            lines.append(Line(f"foot:{key}", "v", cx, fanout_y, total_h - fanout_y))
            return
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
    column_axis("interest", "interest", mi, lambda i: interest_left(i) + COL_W / 2)

    # quantities spine column: a single vertical rule the full height of the grid
    # (the column-axis dual of the h:quantities spine row); no per-element fan
    # since the spine carries no data in the default view
    if "quantities" in col_x:
        q_cx = col_x["quantities"] + col_w["quantities"] / 2
        lines.append(Line("trunk:quantities", "v", q_cx, branch_top_y, total_h - branch_top_y))

    # generators column: a single vertical axis from its node down to the mapping
    # band, connecting the toggle to the identity matrix (drawn over it).
    if "mapping" in row_y:
        gen_cx = gen_x + col_w["gens"] / 2
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
    # never a leftover grey strip. Every tile is simply its row band's full height
    # (the d-tall monzo matrices live in the d-tall interval-vectors row).
    def panel(bid, ckey, rkey):
        if ckey not in col_x or rkey not in row_y:
            return
        # a folded tile collapses both ways at once, so it shrinks to a point at
        # its centre — like a row+column collapse confined to this one tile
        tile_c = f"tile:{rkey}:{ckey}" in collapsed
        col_c = f"col:{ckey}" in collapsed or tile_c
        row_c = f"row:{rkey}" in collapsed or tile_c
        cw, ch, cx, cy = col_w[ckey], tile_h[rkey], col_x[ckey], tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        blocks.append(Block(bid, bx - px, by - py, w + 2 * px, h + 2 * py))

    for bid, rkey, ckey in tiles:
        panel(bid, ckey, rkey)

    # quantity symbol + name stacked inside each tile, below its values + bottom
    # frame: the symbol line (toggled by symbols) on top, the long-form name
    # (toggled by names) under it. Equivalences extends the symbol line with the
    # quantity's defining equation — the "= …" continuation appended to the glyph,
    # so it reads e.g. "𝒕 = 𝒈𝐌"; turning it on shows the glyph too (the equation's
    # left side) even when symbols itself is off. Within a symboled row the slot is
    # reserved for every captioned column so the names stay aligned; the glyph and
    # equation are drawn only where defined (the comma columns have none yet). An
    # empty interest column has no tiles. Mnemonics underlines the symbol letter.
    for (rkey, ckey), name in CAPTIONS.items():
        if ckey == "interest" and not interest:
            continue
        if not tile_open(rkey, ckey):
            continue
        cy = row_y[rkey] + row_h[rkey] + row_frame[rkey]
        if (show_symbols or show_equiv) and rkey in SYMBOLED_ROWS:
            equiv = EQUIVALENCES.get((rkey, ckey), "") if show_equiv else ""
            glyph = SYMBOLS.get((rkey, ckey), "") if (show_symbols or equiv) else ""
            if glyph or equiv:
                cells.append(CellBox(f"symbol:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
            cy += SYMBOL_H
        if show_captions:
            kw = MNEMONICS.get((rkey, ckey)) if show_mnemonics else None
            underlines = ((name.index(kw), 1),) if kw else ()
            ch = _caption_lines(name, col_w[ckey]) * CAPTION_LINE  # hug this name's own lines
            cells.append(CellBox(f"caption:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], ch,
                                 "caption", text=name, underlines=underlines))

    # preselect chooser dropdowns, in the reserved band below each governing tile
    # (and below its caption when names show). The tuning/target choosers carry the
    # live selection; the temperament chooser is a placeholder (it loads, not mirrors).
    if show_preselects:
        preselect_text = {"temperament": "", "tuning": tuning_scheme, "target": target_spec}
        for name, rkey, ckey in PRESELECTS:
            if not tile_open(rkey, ckey):
                continue
            py = row_y[rkey] + row_h[rkey] + row_frame[rkey]
            if (show_symbols or show_equiv) and rkey in SYMBOLED_ROWS and (rkey, ckey) in CAPTIONS:
                py += SYMBOL_H
            if show_captions and (rkey, ckey) in CAPTIONS:
                py += row_cap[rkey]
            pw = min(col_w[ckey], PRESELECT_W)
            cells.append(CellBox(f"preselect:{name}", col_x[ckey], py, pw, PRESELECT_H, "preselect", text=preselect_text[name]))

    # plain-text value band: each tile's value as its natural EBK string, in a box
    # at the foot of the tile, below the caption and preselect bands (the same
    # numbers the grid shows, written inline so the two views agree)
    if show_ptext:
        strings = service.plain_text_values(state, tuning_scheme, target_spec)
        for (rkey, ckey), text in strings.items():
            if tile_open(rkey, ckey):
                py = row_y[rkey] + row_h[rkey] + row_frame[rkey] + row_sym[rkey] + row_cap[rkey] + row_pre[rkey]
                cells.append(CellBox(f"ptext:{rkey}:{ckey}", col_x[ckey], py, col_w[ckey], PTEXT_H, "ptext", text=text))

    # a framed matrix's top bracket + bottom brace stand off the cells by FRAME_GAP:
    # the top bracket just above row 0 (below the toggle head), the brace a matching
    # gap below the last row of that band.
    def frame_top_y(rkey):
        return row_y[rkey] - FRAME_H - FRAME_GAP

    def frame_brace_y(rkey):
        return row_y[rkey] + row_h[rkey] + FRAME_GAP

    # the gens identity and the primes mapping are both stacked-maps matrices, each
    # enclosed by a top bracket + bottom brace spanning its whole column
    def map_frame(ckey):
        if not tile_open("mapping", ckey):
            return
        gx, gw = col_x[ckey], col_w[ckey]
        cells.append(CellBox(f"ebktop:{ckey}", gx, frame_top_y("mapping"), gw, FRAME_H, "ebktop"))
        cells.append(CellBox(f"ebkbrace:{ckey}", gx, frame_brace_y("mapping"), gw, BRACE_H, "ebkbrace"))

    map_frame("gens")
    map_frame("primes")

    # a matrix of monzo columns (the mapped lists, the interval-vector groups):
    # vertical rules separate the columns, and each column is marked as a ket with
    # its own top bracket + bottom brace — inset so they stop short of the rules.
    def monzo_list_marks(rkey, name, ckey, left, n_cols):
        if not tile_open(rkey, ckey):
            return
        mark_w = COL_W - 2 * MARK_INSET
        for c in range(n_cols):
            mx = left(c) + MARK_INSET
            cells.append(CellBox(f"ebktop:{name}:{c}", mx, frame_top_y(rkey), mark_w, FRAME_H, "ebktop"))
            cells.append(CellBox(f"ebkbrace:{name}:{c}", mx, frame_brace_y(rkey), mark_w, BRACE_H, "ebkbrace"))
        for c in range(1, n_cols):  # a rule on each interior column boundary
            cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, row_y[rkey], SEP_W, row_h[rkey], "vbar"))

    monzo_list_marks("mapping", "mapped_comma", "commas", comma_left, nc)
    monzo_list_marks("mapping", "mapped", "targets", target_left, k)
    monzo_list_marks("mapping", "imapped", "interest", interest_left, mi)
    monzo_list_marks("vectors", "vec:primes", "primes", prime_left, d)
    monzo_list_marks("vectors", "vec:commas", "commas", comma_left, nc)
    monzo_list_marks("vectors", "vec:targets", "targets", target_left, k)

    # a per-tile fold toggle inset into each content tile's top-left corner: it
    # sits in the head strip reserved above the content, TOGGLE_INSET in from the
    # grey panel's top-left, so it never touches an edge or overlaps the frame.
    # Present whenever the tile's row and column bands are open — it stays put when
    # only the tile is folded, so the tile can be re-expanded.
    for _bid, rkey, ckey in tiles:
        if rkey in row_y and ckey in col_x and row_open(rkey) and col_open(ckey):
            glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in collapsed)
            cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                 col_x[ckey] - PAD + TOGGLE_INSET, tile_top[rkey] - PAD + TOGGLE_INSET,
                                 TOGGLE, TOGGLE, "tiletoggle", text=glyph))

    # Value-display filtering. The tiles (blocks) and gridlines (lines) always
    # stand; only a tile's *contents* answer to the value-display toggles, so we
    # drop cells by kind here rather than threading the gates through every
    # emission above. "gridded values" off empties the tiles entirely; "quantities"
    # (general) off drops just the body values and their marks.
    if not gridded:
        cells = [cb for cb in cells if cb.kind not in GRIDDED_KINDS]
    elif not show_quantities:
        cells = [cb for cb in cells if cb.kind not in BODY_VALUE_KINDS]

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
