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

from dataclasses import replace
from fractions import Fraction

from rtt.web import service
from rtt.web.layout import Block, CellBox, Layout, Line
from rtt.web.settings import defaults as _default_settings

ROW_H = 30  # px per row / matrix-entry height
COL_W = 30  # px per value column; == ROW_H so matrix cells are squares that tile
# the column (a shared-border grid, per the mockup); cents stack int-over-frac to fit
GAP = 14  # px between row/column groups
PAD = 4  # px a block extends around its cells
WASH_PAD = GAP / 2  # px a colorization wash extends around its cells — wide enough that
# adjacent washed tiles' rects meet across the gap, so the colour reads as one
# continuous band behind the grey tiles (which overhang only by the smaller PAD)
LABEL_W = 96  # row-label gutter width
HEADER_H = 36  # column-header height — two text lines tall, so a multi-word title
# stacks centered onto a second line (via explicit "\n" breaks in col_header, e.g.
# "domain" / "primes"); single-word titles centre as one line
SPINE_W = 64  # quantities spine column width — sized to seat its "quantities"
# header without overflowing onto the generators column; carries only the
# column-axis vertical rule, no data cells in the default view
CTRL_W = 18  # domain expand (+) control gutter, just right of the primes block
BTN = 15  # px side of a domain +/− control — half the COL_W square mapping/prime cell
MINUS_REVEAL_H = 18  # height the removable prime's hover-minus rises above its header
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap
TOGGLE_INSET = 3  # small grey margin hugging a tile's top-left corner toggle (off the edges and content)
CAPTION_FONT = 9  # px font size of the quantity-name caption (matches the mockup —
# ~0.2 of the cell height; the CSS .rtt-caption must use the same size)
CAPTION_LINE = 10  # px per wrapped caption line (font size + leading); == .rtt-caption line-height
PRESELECT_H = 20  # height of a preselect chooser dropdown (when preselects shown)
PRESELECT_W = 124  # its width — fits "<choose temperament>" and caps the wide target tile
TARGET_PRESELECT_W = 132  # wider: the target chooser seats a square limit field + the family select
PTEXT_MAX_FONT = 10  # px cap on the plain-text font; the app shrinks it per box so every value
# always fits on ONE line within its column (a long tuning row just gets smaller text)
PTEXT_H = 13  # px height of a one-line read-only plain-text value
PTEXT_EDIT_H = 16  # px height of an editable plain-text input box (a touch taller than a text line)
SYMBOL_H = 18  # height of the quantity-symbol glyph above the caption (when symbols shown)
CHART_H = 64  # height of a per-tile bar chart's plot area (when charts shown)
CHART_GAP = 5  # gap between a chart and the value cells below it
RANGE_CHART_H = 58  # height of the generator tuning-ranges I-beam chart (title + caps + min/max labels)
RANGE_MODE_H = 13  # height of the monotone/tradeoff range-mode selector (one row of square indicators) below the chart
RANGE_GAP = 2  # gap between the ranges chart and its mode selector (and the values above the chart)
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
GENMAP_BRACKETS = ("{", "]")  # { … ] for the generator tuning map (per the mockup)

# The counts row: each column's set cardinality, as (column key, symbol, name).
# The symbol+value (e.g. "r = 2", the symbol rendered math-italic via _mathit) is
# the cell; the name ("rank") is its caption.
COUNTS = (
    ("gens", "r", "rank"),
    ("primes", "d", "dimensionality"),
    ("commas", "n", "nullity"),
    ("targets", "k", "target interval count"),
)
# The counts row's grey panels + fold toggles, derived from COUNTS so they track
# its columns automatically — every count cell is guaranteed a backing tile, with
# no second list to keep in sync.
COUNTS_TILES = tuple((f"block:counts:{ckey}", "counts", ckey) for ckey, *_ in COUNTS)

# Quantity-name captions shown inside each (row, column) tile when names are on.
CAPTIONS = {
    ("vectors", "commas"): "comma basis",
    ("vectors", "targets"): "target interval list",
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "commas"): "mapped comma list",
    ("mapping", "targets"): "mapped target interval list",
    ("tuning", "gens"): "generator tuning map",
    ("tuning", "primes"): "tuning map",
    ("tuning", "commas"): "tempered comma size list",
    ("tuning", "targets"): "tempered target interval size list",
    ("just", "primes"): "just tuning map",
    ("just", "commas"): "(just) comma size list",
    ("just", "targets"): "(just) target interval size list",
    ("retune", "primes"): "retuning map",
    ("retune", "commas"): "comma error list",
    ("retune", "targets"): "target interval error list",
    ("damage", "targets"): "target interval damage list",
    **{("counts", ckey): name for ckey, _sym, name in COUNTS},
    # other intervals of interest mirror the targets, minus the damage row
    ("vectors", "interest"): "interval of interest list",
    ("mapping", "interest"): "mapped interval list",
    ("tuning", "interest"): "tempered interval size list",
    ("just", "interest"): "(just) interval size list",
    ("retune", "interest"): "interval error list",
}
CAPTIONED_ROWS = frozenset(row for row, _ in CAPTIONS)
# The quantity symbol shown above each name when symbols is on. Styling: the maps
# (covectors) are bold-italic (𝒕 𝒋 𝒓); the vector size-lists are bold-upright (𝐚 𝐨
# 𝐞 𝐝); the mapping 𝑀 is math-italic; the interval lists/bases — mapped target list
# Y, comma basis C, target list T — are upright, non-bold. The comma column has no
# dedicated letters — everything but the basis C (in the interval-vectors row) is a
# product with it: the mapped comma list 𝑀C and the comma sizes 𝒕C, 𝒋C, 𝒓C (damage is
# a target-only row, so the comma column ends there). The "other intervals of
# interest" carry none.
SYMBOLS = {
    ("vectors", "commas"): "C",
    ("vectors", "targets"): "T",
    ("mapping", "primes"): "𝑀",
    ("mapping", "commas"): "𝑀C",
    ("mapping", "targets"): "Y",
    ("tuning", "gens"): "𝒈",
    ("tuning", "primes"): "𝒕",
    ("tuning", "commas"): "𝒕C",
    ("tuning", "targets"): "𝐚",
    ("just", "primes"): "𝒋",
    ("just", "commas"): "𝒋C",
    ("just", "targets"): "𝐨",
    ("retune", "primes"): "𝒓",
    ("retune", "commas"): "𝒓C",
    ("retune", "targets"): "𝐞",
    ("damage", "targets"): "𝐝",
}
SYMBOLED_ROWS = frozenset(row for row, _ in SYMBOLS)  # rows that reserve a symbol slot
# multi-row matrices reserve top/bottom frame bands for their EBK marks: the mapping
# for its spanning bracket+brace, the interval vectors for the per-column ket marks
FRAMED_ROWS = frozenset({"mapping", "vectors"})
CHARTED_ROWS = frozenset({"retune", "damage"})  # rows that grow a bar-chart band above their values when charts shown

# Box-group colorization (the mockup's coloured washes behind the grey tiles): a
# group's "{group}_colorization" setting, when on, paints a colour wash behind that
# group's boxes, showing through the gaps around the grey tiles. A group claims whole
# ROWS (washed full width) and/or whole COLUMNS (washed full height); where a row band
# and a column band cross, the colours blend (see the wash emission / app.py). tuning
# is its quantity rows; temperament is the domain columns (so the tuning maps over the
# domain primes/commas sit at a tuning-row × temperament-column crossing — cyan ⊓
# yellow = green). The renderer maps the group name to its CSS colour.
COLORIZE_GROUP_ROWS: dict[str, frozenset[str]] = {
    "tuning": frozenset({"tuning", "just", "retune", "damage"}),
}
COLORIZE_GROUP_COLS: dict[str, frozenset[str]] = {
    "temperament": frozenset({"gens", "primes", "commas"}),
}

# The three "preselect" chooser dropdowns (settings["preselects"]) as (name, row,
# column): each is a quick menu for one of the things you actually choose, riding
# under its governing tile — the temperament under the mapping matrix, the tuning
# scheme under the tuning map, the target interval set under the target list.
PRESELECTS = (
    ("temperament", "mapping", "primes"),
    ("tuning", "tuning", "primes"),
    ("target", "quantities", "targets"),
)
PRESELECT_ROWS = frozenset(row for _, row, _ in PRESELECTS)

# Mnemonics: underline the caption letter that spells the tile's symbol (see
# SYMBOLS) — a memory aid linking the name to its symbol (e.g. "tuning map" -> t,
# "target interval damage list" -> d). Each entry names the word whose first letter
# is underlined; keep these in step with SYMBOLS. A tile whose symbol letter is not
# a word-initial in its name carries no underline — the mapped list (Y), and the
# tempered (𝐚), just (𝐨) and other size lists.
MNEMONICS = {
    ("mapping", "primes"): "mapping",   # 𝑀
    ("tuning", "gens"): "generator",    # 𝒈
    ("tuning", "primes"): "tuning",     # 𝒕
    ("just", "primes"): "just",         # 𝒋
    ("retune", "primes"): "retuning",   # 𝒓
    ("retune", "targets"): "error",     # 𝐞
    ("damage", "targets"): "damage",    # 𝐝
}

# Each quantity's defining equation continues its symbol (see SYMBOLS): the mockup's
# "symbols section" from the first "=" on, appended to the symbol when equivalences
# is on so the line reads e.g. "𝒕 = 𝒈𝑀". Glyphs match SYMBOLS — bold-italic maps,
# math-italic mapping 𝑀, upright interval lists (T = the target-interval list);
# operators stay upright.
# Only terms buildable from shipped features appear, so the superspace/canonical-
# form tails (the tuning map's "= B_Ls 𝒕_L", "𝑀 = 𝐅𝑀_c", "𝒋 = B_Ls 𝒋_L") are
# dropped — the mapping over primes and the just tuning map thus carry no
# continuation yet; the mapped comma basis instead vanishes to the zero matrix.
EQUIVALENCES = {
    ("mapping", "commas"): " = 𝑂",
    ("mapping", "targets"): " = 𝑀T",
    ("tuning", "primes"): " = 𝒈𝑀",
    ("tuning", "targets"): " = 𝒕T",
    ("just", "targets"): " = 𝒋T",
    ("retune", "primes"): " = 𝒕 − 𝒋",
    ("retune", "targets"): " = 𝒓T",
    ("damage", "targets"): " = |𝐞|diag(𝒘)",
}

# Always-present content tiles (a row×column intersection) as (grey-panel id, row,
# column). Each gets a grey panel and a top-left fold toggle; the panel/toggle ids
# stay stable so the reconciling renderer can animate a single tile folding away.
# The counts row's tiles derive from COUNTS (see COUNTS_TILES) and the "other
# intervals of interest" column adds its own dynamically (only when the user has
# entered intervals) — both are prepended/appended in build().
TILES = (
    ("block:primes", "quantities", "primes"),
    ("block:commas", "quantities", "commas"),
    ("block:targets", "quantities", "targets"),
    ("block:vec:quantities", "vectors", "quantities"),
    ("block:vec:commas", "vectors", "commas"),
    ("block:vec:targets", "vectors", "targets"),
    ("block:gens", "mapping", "quantities"),
    ("block:mapping", "mapping", "primes"),
    ("block:mapped_comma", "mapping", "commas"),
    ("block:mapped", "mapping", "targets"),
    ("block:tuning:gens", "tuning", "gens"),
    ("block:tuning:primes", "tuning", "primes"),
    ("block:tuning:commas", "tuning", "commas"),
    ("block:tuning:targets", "tuning", "targets"),
    ("block:just:primes", "just", "primes"),
    ("block:just:commas", "just", "commas"),
    ("block:just:targets", "just", "targets"),
    ("block:retune:primes", "retune", "primes"),
    ("block:retune:commas", "retune", "commas"),
    ("block:retune:targets", "retune", "targets"),
    ("block:damage:targets", "damage", "targets"),
)

# The plain-text tiles whose string is an editable input that drives the grid —
# the two duals the grid itself lets you type into: the mapping (mapping/primes)
# and the comma basis (vectors/commas). Every other plain-text value is read-only.
EDITABLE_PTEXT = frozenset({("mapping", "primes"), ("vectors", "commas")})
EDITABLE_PTEXT_ROWS = frozenset(r for r, _ in EDITABLE_PTEXT)  # rows whose band holds an input
# Rows that carry a plain-text band (every value row; the counts row has none). The
# quantities row's ratios are placed per column, the rest as one EBK string per tile.
PTEXT_ROWS = frozenset({"quantities", "vectors", "mapping", "tuning", "just", "retune", "damage"})

# Cell kinds the value-display toggles filter out. "gridded values" hides
# everything a tile holds besides its fold toggle, name caption and plain-text
# value box: the value numbers (including the just row's "mathexpr" log₂ form),
# the EBK marks framing them, and the domain/comma ± controls. (Gridded off with
# plain text on leaves just the inline string — the two value views are independent.)
GRIDDED_KINDS = frozenset({
    "prime", "target", "commaratio", "genratio", "mapping", "mapped", "commacell", "static",
    "vec", "tval", "mathexpr", "interestcell",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "vbar",
    "minus", "plus", "comma_minus", "comma_plus", "basis_minus",
    "interest_minus", "interest_plus",
})
# "quantities" (general) is gentler than gridded values: it keeps every cell box
# AND the EBK marks framing them, and only *blanks the numbers* of the body
# quantity values -- the matrix, mapped list, comma basis, generator ratios,
# tuning cents, and the static / plain-text-vector / other-interval value cells --
# so the bare gridded structure remains. (The quantities-row header ratios answer
# to "domain_quantities"; the just row's "mathexpr" log₂ form is not a bare number,
# so math_expressions' own show_value logic trims it.)
BLANKED_NUMBER_KINDS = frozenset({
    "genratio", "mapping", "mapped", "commacell", "static", "vec", "tval", "interestcell",
})


def _mathit(letter: str) -> str:
    """A single lowercase ASCII letter as its Unicode Mathematical Italic glyph
    (e.g. ``d`` -> ``𝑑``), so a count's variable reads as math italic like the
    Show panel's example. ``h`` is the one hole in the block — it maps to the
    Planck-constant glyph ``ℎ`` instead of an undefined code point."""
    return "ℎ" if letter == "h" else chr(0x1D44E + ord(letter) - ord("a"))


def _log_operand(ratio: str) -> str:
    """The operand of a just interval's log₂, e.g. ``3/1`` -> ``3`` (a bare prime,
    matching the mockup's ``log₂3``) and ``3/2`` -> ``(3/2)`` (parenthesised)."""
    num, _, den = ratio.partition("/")
    return num if den == "1" else f"({num}/{den})"


def _math_expr(operand: str, value: float, show_value: bool) -> str:
    """A just value's exact closed form ``1200 · log₂{operand}`` — which *equals* the
    cents value, so the decimal stays in cents and is kept as a true ``= {cents}``.
    The two parts are newline-separated so the renderer stacks them (the ``=`` and
    the decimal on the second line), e.g. ``"1200 · log₂2\\n= 1200.00"``. With the
    value (quantities) off, only the expression shows."""
    expr = f"1200 · log₂{operand}"
    return f"{expr}\n= {service.cents(value)}" if show_value else expr


def _format_power(power: float) -> str:
    """The optimization power as shown beside ``𝑝``: ``∞`` for a minimax scheme, else
    the bare integer (``2``, ``1``) — or the decimal for an unusual fractional power."""
    if power == float("inf"):
        return "∞"
    return str(int(power)) if power == int(power) else str(power)


def _title_w(title: str) -> int:
    """Width of a collapsed column's title strip: wide enough for the widest line of its
    title at 13px bold, with a STRIP floor. A multi-word title carries explicit "\\n"
    breaks (col_header), so it stacks within a strip sized to its longest word-run rather
    than folding to an over-wide one-line ribbon."""
    widest = max(len(line) for line in title.splitlines())
    return max(STRIP, widest * 8 + 10)


def _fold_glyph(is_collapsed: bool) -> str:
    """Material Icons name for the fold toggle: out-chevrons to expand a collapsed
    band, in-chevrons to collapse an expanded one."""
    return "unfold_more" if is_collapsed else "unfold_less"


def _foldable_ids(cells) -> set:
    """The row/column fold-ids present among ``cells`` ("row:tuning", "col:targets")
    — the bands the master expand/collapse-all toggle acts on. Tiles are omitted: a
    folded row or column already subsumes its tiles, so collapsing every band folds
    the whole grid. Derived from the emitted toggles so it can't drift from them."""
    return {c.id.split("toggle:", 1)[1] for c in cells
            if c.kind in ("rowtoggle", "coltoggle")}


def toggle_all_collapsed(layout, collapsed) -> set:
    """The next ``collapsed`` set when the master expand/collapse-all toggle fires:
    expand everything (clear the set) when every foldable band is already collapsed,
    otherwise collapse every row and column. Pure — the app stores the result and
    re-renders. Operates on the just-built ``layout`` so it tracks the visible grid."""
    foldable = _foldable_ids(layout.cells)
    if foldable and foldable <= collapsed:
        return set()
    return set(collapsed) | foldable


def _wrap_lines(text: str, width: float, font: float = CAPTION_FONT) -> int:
    """How many lines ``text`` wraps to in a ``width``-px box at ``font`` px, so the
    tile can grow tall enough to hold it (rather than letting it spill, as a narrow
    column's long name would). A greedy word wrap with a conservative serif char-width
    estimate; an over-long word breaks across lines itself. Shared by the name
    captions and the plain-text value boxes."""
    max_chars = max(1, int((width - 4) / (font * 0.52)))  # -4: a little padding
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
          tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
          pending_comma=None) -> Layout:
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
    show_charts = settings["charts"]  # per-tile bar charts above the value cells
    show_ranges = settings["tuning_ranges"]  # the generator tuning-ranges I-beam chart (in the gens box)
    show_symbols = settings["symbols"]  # the in-tile quantity symbols, stacked above the captions
    show_temp = settings["temperament_boxes"]
    show_tuning = settings["tuning_boxes"]
    # optimization is a sub-control of tuning boxes: it annotates the tuning region with
    # the scheme's optimization power, so it only applies while that region shows
    show_optimization = show_tuning and settings["optimization"]
    # Value-display toggles. "gridded values" is the master switch: with it off
    # (and plain-text values not yet built) every value a tile holds -- the numbers,
    # the EBK marks framing them, the domain/comma ± controls -- is filtered out
    # (see GRIDDED_KINDS at the end of build), leaving the tiles empty but for their
    # fold toggles, name captions and (when on) plain-text value boxes.
    # "quantities" (general) is gentler -- it keeps the boxes and EBK marks and only
    # blanks the body numbers (BLANKED_NUMBER_KINDS); "domain_quantities" (specific)
    # governs the quantities row and its spine column.
    gridded = settings["gridded_values"]
    show_quantities = settings["quantities"]
    show_domain_quantities = settings["domain_quantities"]
    # Math expressions PREFIXES a tuning cell's cents value with its exact closed form
    # where one exists ("1200 · log₂3 = 1901.96", the = cents kept when quantities is
    # on); a cell with no closed form is untouched and keeps its plain cents value.
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
    mapped = service.mapped_intervals(state.mapping, targets)
    target_vectors = service.target_interval_monzos(targets, d)  # k monzos, each d-tall
    tun = service.tuning(state.mapping, tuning_scheme)  # prime maps, shared by every interval set
    target_sizes = service.interval_sizes(tun, targets)
    comma_ratios = service.comma_ratios(state.comma_basis)
    nc = len(comma_ratios)  # the real commas (those that define the temperament)
    mapped_commas = service.mapped_commas(state.mapping, state.comma_basis)  # M·commas = 0 (vanish)
    comma_sizes = service.interval_sizes(tun, comma_ratios)  # comma sizes (tempered ~0)
    # a comma being added is shown as a pending draft column to the right of the real
    # ones: blank red cells and a "?" quantity until it is a valid independent comma
    # (then it commits and the mapping re-ranks). It is not a real comma, so it does
    # not enter the nullity, the mapping, or the sizes — only the displayed column count.
    pending = list(pending_comma) if pending_comma is not None else None
    nc_shown = nc + (1 if pending is not None else 0)
    # other intervals of interest: a user-built set held as monzos and edited like
    # the comma basis (editable vector cells). Normalize each monzo to the current d
    # (pad/trim) so a domain change can't misalign them, then derive the ratios the
    # quantities row shows and the mapping/sizes the lower rows show. It carries no
    # damage row and contributes tiles only when populated, so an empty column adds no
    # panels or fold toggles — just its header and a single straight axis rule.
    interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(d)) for m in interest)
    mi = len(interest)
    interest_ratios = service.comma_ratios(interest)  # monzo -> "num/den" (the shared renderer)
    interest_mapped = service.mapped_intervals(state.mapping, interest_ratios)
    interest_sizes = service.interval_sizes(tun, interest_ratios)
    interest_tiles = () if not interest else (
        ("block:vec:interest", "vectors", "interest"),
        ("block:interest", "quantities", "interest"),
        ("block:imapped", "mapping", "interest"),
        ("block:tuning:interest", "tuning", "interest"),
        ("block:just:interest", "just", "interest"),
        ("block:retune:interest", "retune", "interest"),
    )
    # the optimization power rides one tile over the targets column (guarded by panel()
    # and the toggle loop, so it adds nothing unless the optimization row is present)
    tiles = COUNTS_TILES + TILES + interest_tiles + (("block:optimization", "optimization", "targets"),)
    # The authoritative set of real (row, column) tiles. tile_open() consults it, so a
    # tile's existence lives in ONE place: drop its entry here (via TILES etc.) and it
    # vanishes everywhere — panels, toggles, cells, brackets and marks — with no chance
    # for a stray hardcoded column list to keep drawing a tile that no longer exists.
    declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in tiles}

    # Column bands left-to-right: (key, natural width, present, collapsible).
    # Each set-column belongs to a box toggle: generators, the domain primes and
    # the commas are the temperament's (shown with temperament_boxes), target-
    # intervals are the tuning's (shown with tuning_boxes) -- turning a box off
    # takes its whole column with it, including the other family's cells that ride
    # in it (e.g. the tuning maps over primes, or the mapped target interval list
    # over targets). A collapsed column folds to a strip just wide enough to keep
    # its (horizontal) title readable, so it never overflows onto its neighbours.
    # The domain/comma + controls ride just right of their blocks when open; each −
    # is a hover affordance on the removable highest-prime / last-comma column.
    col_header = {"quantities": "quantities", "gens": "generators",
                  "primes": "domain\nprimes", "commas": "commas", "targets": "target\nintervals",
                  "interest": "other intervals\nof interest"}
    # The leftmost quantities column is the spine: a header + fold toggle + a single
    # vertical rule, the column-axis dual of the quantities spine row.
    # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
    # the value cells are inset by BRACKET_W within the group.
    col_bands = (
        ("quantities", SPINE_W, show_domain_quantities, True),
        ("gens", 2 * BRACKET_W + r * COL_W, show_temp, True),
        ("primes", 2 * BRACKET_W + d * COL_W, show_temp, True),
        ("commas", 2 * BRACKET_W + nc_shown * COL_W, show_temp, True),
        ("targets", 2 * BRACKET_W + k * COL_W, show_tuning, True),
        # The interest column's tiles hug their content (32 + mi·COL_W) — no empty
        # padding. Its long two-line title would not fit that narrow width, so the
        # HEADER alone floats wider (see col_head_w below): since interest is the
        # rightmost column, the header overhangs to the right (into the header band
        # above the + gutter) without crowding any neighbour. The captions wrap within
        # the (content) column width, and the board height is independent of either.
        ("interest", 2 * BRACKET_W + mi * COL_W, show_tuning, True),
    )
    # A fold-toggle node column sits between the row-label gutter and the content
    # (when names show); content starts past it with a clear gap so the tiles
    # never collide with the nodes. Row lines fan from the node's right edge so
    # their gaps match the columns'.
    node_x = label_w + GAP
    node_edge = node_x + TOGGLE  # the node's content-facing (right) edge
    content_x0 = node_x + TOGGLE + GAP

    # the domain, the comma basis and the interest set each ride an expand (+) control
    # in a gutter just right of their (open) block — domain primes add a prime, commas
    # add a comma, interest adds a blank interval to edit
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
        if key in ("primes", "commas", "interest") and f"col:{key}" not in collapsed:
            ctrl_x[key] = x + 6
            x = ctrl_x[key] + CTRL_W
        x += GAP
    total_w = x

    # Header width per column. Normally the header spans its column; the rightmost
    # column (interest) is the exception — its tiles hug a few narrow cells but its
    # long title needs more room, so its header floats out to the title width and
    # overhangs to the right (only the rightmost column may, with no neighbour there).
    col_head_w = dict(col_w)
    if "interest" in col_x:
        col_head_w["interest"] = max(col_w["interest"], _title_w(col_header["interest"]))
        total_w = max(total_w, col_x["interest"] + col_head_w["interest"] + PAD)

    primes_x = col_x.get("primes")  # None when the domain-primes column is hidden
    commas_x = col_x.get("commas")  # None when the commas column is hidden
    targets_x = col_x.get("targets")  # None when the target intervals column is hidden
    interest_x = col_x.get("interest")  # None when the interest column is hidden

    def col_open(key):
        return key in col_x and f"col:{key}" not in collapsed

    # The generator tuning-ranges box (the chart + its mode selector) nests at the bottom
    # of the generator tuning map tile when tuning_ranges is on. Its extra height is
    # reserved in the tuning row (below) so the rows beneath drop clear of it rather than
    # the box spilling across them. Determinable up front: it rides the open, uncollapsed
    # gens tile of the (present, unfolded) tuning row.
    gtm_chart = (show_ranges and show_tuning and "row:tuning" not in collapsed
                 and col_open("gens") and "tile:tuning:gens" not in collapsed)
    gtm_extra = (RANGE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if gtm_chart else 0

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
    # laid out by the same running-cursor rule as the columns. Every row folds to a
    # strip via its toggle; the "quantities" setting additionally hides that row and
    # its column outright.
    row_bands = (
        ("counts", ROW_H, show_counts, True, "counts"),
        ("quantities", ROW_H, show_domain_quantities, True, "quantities"),
        ("vectors", d * ROW_H, True, True, "interval vectors"),
        ("mapping", r * ROW_H, show_temp, True, "mapping"),
        ("tuning", ROW_H, show_tuning, True, "tuning"),
        ("just", ROW_H, show_tuning, True, "just tuning"),
        ("retune", ROW_H, show_tuning, True, "retuning"),
        ("damage", ROW_H, show_tuning, True, "damage"),
        ("optimization", ROW_H, show_optimization, True, "optimization"),
    )
    # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
    # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    tile_h, tile_top, row_frame, row_sym, row_cap, row_ptext, chart_top = {}, {}, {}, {}, {}, {}, {}

    def caption_band(key, folded):
        # the row's caption band is sized to its tallest (wrapped) caption, so the
        # longest name fits within its tile rather than spilling off a narrow column.
        # Captions wrap within the header width (col_head_w), not the content width, so
        # the interest column's caption tracks its (steady) header rather than its
        # content — keeping this band, and the board height, independent of how many
        # intervals of interest are present.
        if not (show_captions and key in CAPTIONED_ROWS and not folded):
            return 0
        lines = [_wrap_lines(CAPTIONS[(key, c)], col_head_w[c]) for c in col_x
                 if (key, c) in CAPTIONS and col_open(c) and f"tile:{key}:{c}" not in collapsed]
        return max(lines, default=1) * CAPTION_LINE

    ptext_strings = service.plain_text_values(state, tuning_scheme, target_spec) if show_ptext else {}

    def ptext_height(rkey, ckey):  # one line; the app shrinks the font to fit the box width
        return PTEXT_EDIT_H if (rkey, ckey) in EDITABLE_PTEXT else PTEXT_H

    def ptext_band(key, folded):
        # a single-line band for every value row's plain text (taller for the rows whose
        # band holds an editable input); the font auto-fits so nothing wraps or spills
        if not (show_ptext and key in PTEXT_ROWS and not folded):
            return 0
        return PTEXT_EDIT_H if key in EDITABLE_PTEXT_ROWS else PTEXT_H
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
        # a charted row grows a chart band (above the values, below the top frame)
        charted = show_charts and key in CHARTED_ROWS and not folded
        chart_band = (CHART_H + CHART_GAP) if charted else 0
        cap = caption_band(key, folded)
        # the symbol line reserves a slot above the caption for every symboled row;
        # equivalences extends that same line (the "= …" continuation) rather than
        # adding a band, so it reserves the slot too even when symbols itself is off
        sym = SYMBOL_H if ((show_symbols or show_equiv) and key in SYMBOLED_ROWS and not folded) else 0
        # below the caption a tile reserves bands for the plain-text value box and
        # the preselect chooser (its row), stacked in that order
        pre = PRESELECT_H if (show_preselects and key in PRESELECT_ROWS and not folded) else 0
        ptext = ptext_band(key, folded)
        row_h[key] = STRIP if folded else natural
        tile_top[key] = y
        if charted:
            chart_top[key] = y + head + top_frame  # the chart sits just below the top frame
        row_y[key] = y + head + top_frame + chart_band  # values sit below toggle head, top frame, chart
        row_frame[key] = bot_frame  # the symbol/caption stack sits below the bottom brace band
        row_sym[key] = sym  # the caption (and bands below it) sit below the symbol slot
        row_cap[key] = cap  # the plain-text box and preselect chooser sit below the caption
        row_ptext[key] = ptext  # the plain-text band, with the preselect chooser below it
        row_label[key] = label
        row_collapsible[key] = collapsible
        tile_h[key] = head + top_frame + chart_band + row_h[key] + bot_frame + sym + cap + pre + ptext
        # the tuning row reserves the nested ranges box below its values: this grows EVERY
        # tile in the row to the same height (so the row is one uniform band) and pushes the
        # rows below clear of it
        if key == "tuning":
            tile_h[key] += gtm_extra
        y += tile_h[key] + GAP
    total_h = y

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def tile_open(rkey, ckey):  # a real tile, whose row + column are open and not folded
        return ((rkey, ckey) in declared_tiles and row_open(rkey) and col_open(ckey)
                and f"tile:{rkey}:{ckey}" not in collapsed)

    def prime_left(p):
        return primes_x + BRACKET_W + p * COL_W

    def comma_left(c):
        return commas_x + BRACKET_W + c * COL_W

    def target_left(j):
        return targets_x + BRACKET_W + j * COL_W

    def interest_left(i):
        return interest_x + BRACKET_W + i * COL_W

    def gen_left(g):  # the g-th generator column in the generators box (its tuning-map cells)
        return col_x["gens"] + BRACKET_W + g * COL_W

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
        cells.append(CellBox(f"header:{key}", col_x[key], header_y, col_head_w[key], HEADER_H, "colheader", text=col_header[key]))
        if col_collapsible[key]:
            glyph = _fold_glyph(f"col:{key}" in collapsed)
            # the fold toggle sits on the column's gridline (its content centre), so it
            # stays aligned with the trunk even when the interest header floats wider
            tx = col_x[key] + (col_w[key] - TOGGLE) / 2
            cells.append(CellBox(f"toggle:col:{key}", tx, col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))

    # row labels (always shown; a collapsed row keeps its label as the strip)
    # plus a fold toggle in the gutter for the collapsible ones
    for key in row_y:
        cells.append(CellBox(f"label:{key}", 0, row_y[key], LABEL_W, row_h[key], "rowlabel", text=row_label[key]))
        if row_collapsible[key]:
            glyph = _fold_glyph(f"row:{key}" in collapsed)
            ty = row_y[key] + (row_h[key] - TOGGLE) / 2
            cells.append(CellBox(f"toggle:row:{key}", node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))

    # the master expand/collapse-all toggle, in the corner where the row-toggle column
    # (node_x) meets the column-toggle row (col_node_y). Its glyph mirrors the whole
    # grid: out-chevrons to expand when every foldable row and column is already
    # collapsed, in-chevrons to collapse otherwise.
    foldable = _foldable_ids(cells)  # the row/col toggles emitted just above
    all_collapsed = bool(foldable) and foldable <= collapsed
    cells.append(CellBox("toggle:all", node_x, col_node_y, TOGGLE, TOGGLE, "alltoggle",
                         text=_fold_glyph(all_collapsed)))

    # counts row: each present column's set cardinality, centred over its values
    if row_open("counts"):
        cardinality = {"gens": r, "primes": d, "commas": state.n, "targets": k}
        for ckey, sym, _name in COUNTS:
            if tile_open("counts", ckey):
                cells.append(CellBox(f"count:{ckey}", col_x[ckey], row_y["counts"], col_w[ckey], ROW_H,
                                     "count", text=f"{_mathit(sym)} = {cardinality[ckey]}"))

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
            if pending is not None:  # the draft has no ratio yet — a "?" in a distinct id so
                # it is removed (not restructured from "?" label to fraction) when it commits
                cells.append(CellBox("comma:pending", comma_left(nc), qy, COL_W, ROW_H, "commaratio", text="?", comma=nc, pending=True))
            # commas mirror the domain controls: + starts a (pending) comma; the − rides
            # the last column — cancelling the draft, or dropping a real comma when >1
            if pending is not None or nc > 1:
                cells.append(CellBox("comma_minus", comma_left(nc_shown - 1), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "comma_minus"))
            cells.append(CellBox("comma_plus", ctrl_x["commas"], qy + (ROW_H - BTN) // 2, BTN, BTN, "comma_plus"))
        if tile_open("quantities", "targets"):
            for j in range(k):
                cells.append(CellBox(f"target:{j}", target_left(j), qy, COL_W, ROW_H, "target", text=targets[j]))
        if tile_open("quantities", "interest"):  # the user's other intervals of interest
            for i in range(mi):
                # the derived ratio (read-only, from the monzo) heads each column, like a comma's
                cells.append(CellBox(f"interest:{i}", interest_left(i), qy, COL_W, ROW_H, "commaratio", text=interest_ratios[i], comma=i))
                # every interval carries its own − (a hover affordance over its header):
                # any one is removable, unlike the domain/comma last-only −
                cells.append(CellBox(f"interest_minus:{i}", interest_left(i), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "interest_minus", comma=i))
        # the + is a column control, not tile content: an empty-but-open interest column
        # has no tile yet, so it rides col_open (not tile_open) so the first interval can
        # be added. It appends a blank 1/1 (a zero monzo) to edit in the vectors row.
        if col_open("interest") and row_open("quantities"):
            cells.append(CellBox("interest_plus", ctrl_x["interest"], qy + (ROW_H - BTN) // 2, BTN, BTN, "interest_plus"))

    # generator ratios (aligned with the mapping rows they label) + the mapping
    # matrix and its mapped target interval list
    if row_open("mapping"):
        # the generators list the mapping's rows: a vertical ratio list in the
        # quantities spine column, labelling the rows as the primes label the columns
        if tile_open("mapping", "quantities"):
            for i in range(r):
                cells.append(CellBox(f"gen:{i}", col_x["quantities"], map_top(i), col_w["quantities"], ROW_H, "genratio", text=gens[i] if i < len(gens) else "", gen=i))
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
    # The comma basis is the editable raw monzos (the mapping's dual); the targets
    # become a d x k matrix of monzo columns.
    if row_open("vectors"):
        # the domain basis lists the interval-vectors' rows: the d primes as boxed
        # COL_W squares (the same the quantities row heads its columns with) stacked
        # down the quantities spine — the dual index, as the generators label the
        # mapping rows. Its domain ± controls ride it vertically: + below the stack to
        # add a prime, − on the highest (bottom) prime to remove one.
        if tile_open("vectors", "quantities"):
            bx = col_x["quantities"] + (col_w["quantities"] - COL_W) / 2  # square, centred in the spine
            for p in range(d):
                cells.append(CellBox(f"basis:{p}", bx, vec_top(p), COL_W, ROW_H, "prime", text=str(primes[p]), prime=p))
            if d > 1:  # the highest prime is the removable one (shrink trims the last)
                cells.append(CellBox("basis_minus", col_x["quantities"], vec_top(d - 1), col_w["quantities"], ROW_H, "basis_minus"))
            cells.append(CellBox("basis_plus", bx + (COL_W - BTN) / 2, vec_top(d) + FRAME_GAP, BTN, BTN, "plus"))
        if tile_open("vectors", "commas"):
            for c in range(nc):
                for p in range(d):
                    cells.append(CellBox(f"cell:comma:{p}:{c}", comma_left(c), vec_top(p), COL_W, ROW_H, "commacell", text=str(state.comma_basis[c][p]), prime=p, comma=c))
            if pending is not None:  # the draft column: blank, red-outlined cells the user fills in
                for p in range(d):
                    v = pending[p]
                    cells.append(CellBox(f"cell:comma:{p}:{nc}", comma_left(nc), vec_top(p), COL_W, ROW_H, "commacell",
                                         text="" if v is None else str(v), prime=p, comma=nc, pending=True))
        if tile_open("vectors", "targets"):
            for j in range(k):
                for p in range(d):
                    cells.append(CellBox(f"cell:vec:targets:{j}:{p}", target_left(j), vec_top(p), COL_W, ROW_H, "vec", text=str(target_vectors[j][p])))
        if tile_open("vectors", "interest"):  # the user's intervals of interest: editable monzos, like the comma basis
            for i in range(mi):
                for p in range(d):
                    cells.append(CellBox(f"cell:interest:{p}:{i}", interest_left(i), vec_top(p), COL_W, ROW_H, "interestcell", text=str(interest[i][p]), prime=p, comma=i))

    # the three value groups share an element name (for cell ids), a left-edge
    # accessor, and the operand of their just log₂ (a bare prime, or a comma/target
    # ratio); primes carry a map, commas and targets carry interval lists
    group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target", "interest": "interest"}
    group_left = {"gens": gen_left, "primes": prime_left, "commas": comma_left, "targets": target_left,
                  "interest": interest_left}
    group_ratio = {  # the just interval ratio each value group is taken over
        "primes": lambda i: f"{primes[i]}/1",
        "commas": lambda i: comma_ratios[i],
        "targets": lambda i: targets[i],
        "interest": lambda i: interest_ratios[i],
    }

    def closed_form_operand(key, group, i):
        """The operand ``R`` of a cell's exact closed form ``1200 · log₂R``, or None
        when the value has no closed form. A just size IS ``1200·log₂`` of its
        interval. A comma vanishes in the temperament, so its retuning is the negated
        just size — the exact log of the inverted comma. The tempered sizes and the
        prime/target errors come from optimization, so they have none."""
        if key == "just":
            return _log_operand(group_ratio[group](i))
        if group == "commas" and key == "retune":
            r = 1 / Fraction(comma_ratios[i])
            return _log_operand(f"{r.numerator}/{r.denominator}")
        return None

    # tuning rows over the primes, commas and targets (cents); each can collapse on
    # its own. Commas sit on the same footing as targets — they are just the dual
    # interval set. Math expressions only ADDS the exact closed form where one exists
    # (a "mathexpr" kind prefixing the cents value); a cell with no closed form is
    # untouched — it keeps its plain cents cell. Math expressions never removes a
    # value, bracket, caption or tile: those are governed by quantities/gridded/names.
    def tval_row(key, group, vals):
        if not tile_open(key, group):
            return
        y = row_y[key]
        for i, v in enumerate(vals):
            cid = f"{key}:{group_elem[group]}:{i}"
            x = group_left[group](i)
            operand = closed_form_operand(key, group, i) if show_math else None
            if operand is not None:
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, show_quantities)))
            else:
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "tval", text=service.cents(v)))

    # a charted tile draws a bar chart in the band reserved above its values; the
    # chart spans the column group so its bars align with the value cells below.
    # chart_top[key] exists only where a chart band was reserved (charts on, row
    # charted, not folded), so it gates emission against the layout with no drift.
    def chart(rkey, ckey, vals):
        if rkey in chart_top and tile_open(rkey, ckey):
            cells.append(CellBox(f"chart:{rkey}:{ckey}", col_x[ckey], chart_top[rkey],
                                 col_w[ckey], CHART_H, "chart", values=tuple(vals)))

    tuning_data = {
        "tuning": (tun.tuning_map, comma_sizes.tempered, target_sizes.tempered, interest_sizes.tempered),
        "just": (tun.just_map, comma_sizes.just, target_sizes.just, interest_sizes.just),
        "retune": (tun.retuning_map, comma_sizes.errors, target_sizes.errors, interest_sizes.errors),
    }
    for key, (prime_vals, comma_vals, target_vals, interest_vals) in tuning_data.items():
        if row_open(key):
            tval_row(key, "primes", prime_vals)
            tval_row(key, "commas", comma_vals)
            tval_row(key, "targets", target_vals)
            tval_row(key, "interest", interest_vals)
            chart(key, "primes", prime_vals)
            chart(key, "targets", target_vals)
    # the generator tuning map: the tuning row's map over the generators (the gens-column
    # counterpart of the tuning map over the primes), so the generators get a tuning tile too
    if row_open("tuning"):
        tval_row("tuning", "gens", tun.generator_map)
    if row_open("damage"):  # damage is over the targets only (the tuning's own column)
        tval_row("damage", "targets", target_sizes.damage)
        chart("damage", "targets", target_sizes.damage)

    # The generator tuning-ranges chart nests at the BOTTOM of the generator tuning map
    # tile (below its values and caption), a per-generator [min, max] I-beam (octave held
    # pure, so the period generator pins to a point) under the selected mode, diamond-
    # monotone or -tradeoff. Gated on the tuning_ranges toggle; the tile's own panel is
    # extended to enclose it (see gtm_extra in the panel loop), so it sits inside the tile
    # rather than floating. The monotone range can be None (no monotone tuning exists),
    # passed as () so the chart draws a placeholder rather than I-beams. gtm_chart/gtm_extra
    # were computed up front (so the tuning row could reserve the box's height).
    gtm_box = None  # (x, y, w, h) of the bordered box framing the chart + selector
    if gtm_chart:
        chosen = tun.monotone_generator_range if range_mode == "monotone" else tun.tradeoff_generator_range
        gx, gw = col_x["gens"], col_w["gens"]
        # the chart nests below the tile's values + caption (tile_h now includes gtm_extra
        # for the box itself, so back it out to find the values' bottom)
        cy = tile_top["tuning"] + tile_h["tuning"] - gtm_extra + RANGE_GAP
        cells.append(CellBox("rangechart:tuning:gens", gx, cy, gw, RANGE_CHART_H, "rangechart",
                             ranges=tuple(chosen) if chosen is not None else (),
                             values=tuple(tun.generator_map)))  # the live tuning, marked within each range
        cells.append(CellBox("rangemode:tuning:gens", gx, cy + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                             "rangemode", text=range_mode))
        gtm_box = (gx, cy, gw, RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)

    # the optimization power 𝑝 of the current tuning, annotating the bottom of the
    # tuning boxes (the scheme's Lp-norm order: ∞ minimax, 2 least-squares, 1 average).
    # It rides the target-intervals column — the tuning's own column, whose damage list
    # the optimization minimizes — and reads like a count: "𝑝 = ∞".
    if tile_open("optimization", "targets"):
        power = _format_power(service.optimization_power(tuning_scheme))
        cells.append(CellBox("optimization:power", col_x["targets"], row_y["optimization"],
                             col_w["targets"], ROW_H, "optimization", text=f"{_mathit('p')} = {power}"))

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
        # the primes mapping is a stack of maps: ⟨ … ] per row
        if tile_open("mapping", "primes"):
            for i in range(r):
                bracket(f"map:{i}", MAP_BRACKETS, "primes", map_top(i), ROW_H)
        if tile_open("mapping", "commas"):  # the mapped (vanishing) comma list: a [ ] over r rows
            bracket("mapped_comma", LIST_BRACKETS, "commas", row_y["mapping"], r * ROW_H, fit=True)
        if tile_open("mapping", "targets"):
            bracket("mapped", LIST_BRACKETS, "targets", row_y["mapping"], r * ROW_H, fit=True)
        if mi and tile_open("mapping", "interest"):  # interest mapped list, like the targets
            bracket("imapped", LIST_BRACKETS, "interest", row_y["mapping"], r * ROW_H, fit=True)
    if row_open("vectors"):  # each group is a list of monzos: a [ ] spanning the d components
        for group in ("commas", "targets"):
            if tile_open("vectors", group):
                bracket(f"vec:{group}", LIST_BRACKETS, group, row_y["vectors"], d * ROW_H, fit=True)
        if mi and tile_open("vectors", "interest"):
            bracket("vec:interest", LIST_BRACKETS, "interest", row_y["vectors"], d * ROW_H, fit=True)
    if tile_open("tuning", "gens"):  # the generator tuning map is framed { … ] (per the mockup)
        bracket("tuning:genmap", GENMAP_BRACKETS, "gens", row_y["tuning"], ROW_H)
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
    column_axis("commas", "comma", nc_shown, lambda c: comma_left(c) + COL_W / 2)
    column_axis("targets", "target", k, lambda j: target_left(j) + COL_W / 2)
    column_axis("interest", "interest", mi, lambda i: interest_left(i) + COL_W / 2)

    # quantities spine column: a single vertical rule the full height of the grid
    # (the column-axis dual of the h:quantities spine row) — one spine rule, no fan
    if "quantities" in col_x:
        q_cx = col_x["quantities"] + col_w["quantities"] / 2
        lines.append(Line("trunk:quantities", "v", q_cx, branch_top_y, total_h - branch_top_y))

    # generators column: a single vertical rule the full height of the grid, like the
    # quantities spine — it indexes the mapping rows and backs the rank count and the
    # tuning-ranges chart when those are shown.
    if "gens" in col_x:
        gen_cx = col_x["gens"] + col_w["gens"] / 2
        lines.append(Line("trunk:gens", "v", gen_cx, branch_top_y, total_h - branch_top_y))

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
    # row-axis counterpart of the quantities spine column) that the data blocks hang off
    if "quantities" in row_y:
        lines.append(Line("h:quantities", "h", row_y["quantities"] + row_h["quantities"] / 2, node_edge, total_w - node_edge))

    # the remaining rows each get one horizontal rule across their band (no sub-row
    # fan), present or collapsed — so a collapsed one still leaves a gridline
    for key in ("counts", "vectors", "tuning", "just", "retune", "damage", "optimization"):
        if key not in row_y:
            continue
        lines.append(Line(f"h:{key}", "h", row_y[key] + row_h[key] / 2, node_edge, total_w - node_edge))

    # #e0e0e0 panels behind each content group. A panel folds to zero size along
    # any collapsed axis (collapsing toward the band centre), so the renderer
    # animates it shrinking away to nothing — leaving only the band's gridline,
    # never a leftover grey strip. Every tile is simply its row band's full height
    # (the d-tall monzo matrices live in the d-tall interval-vectors row).
    def panel_rect(ckey, rkey):
        # a folded tile collapses both ways at once, so it shrinks to a point at its
        # centre — like a row+column collapse confined to this one tile. tile_h already
        # includes the tuning row's ranges-box reservation, so every tile in that row
        # gets the same (extended) height here.
        tile_c = f"tile:{rkey}:{ckey}" in collapsed
        col_c = f"col:{ckey}" in collapsed or tile_c
        row_c = f"row:{rkey}" in collapsed or tile_c
        cw, ch, cx, cy = col_w[ckey], tile_h[rkey], col_x[ckey], tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        return bx - px, by - py, w + 2 * px, h + 2 * py

    def panel(bid, ckey, rkey):
        if ckey not in col_x or rkey not in row_y:
            return
        blocks.append(Block(bid, *panel_rect(ckey, rkey)))

    for bid, rkey, ckey in tiles:
        panel(bid, ckey, rkey)
    # the nested tuning-ranges box: a thin-bordered frame around the chart + selector,
    # appended after the tile panels so it layers on top of the generator tuning map tile
    if gtm_box is not None:
        blocks.append(Block("block:tuning:rangesbox", *gtm_box, boxed=True))

    # Colorization washes. The mockup paints the whole background of a colorized
    # group's boxes (the grey tiles float on top), so a colorized ROW gets a full-width
    # band and a colorized COLUMN a full-height band — not per-tile patches. A band is a
    # white base plus the group's colour drawn at mix-blend-mode:darken (see app.py).
    # ALL bases are emitted before ALL colour layers, so a cyan row band crossing a
    # yellow column band composes the way the mockup's palette does: the opaque white
    # bases paint first, then the darken colour layers min together — cyan ⊓ yellow =
    # green at the tuning-maps-over-primes/commas cells. Bands overhang by WASH_PAD so a
    # group's adjacent rows/columns read as one block; each folds to a strip with its row/column.
    if col_x and row_y:
        row_l = min(col_x.values()) - WASH_PAD
        row_r = max(col_x[c] + col_w[c] for c in col_x) + WASH_PAD
        col_t = min(tile_top.values()) - WASH_PAD
        col_b = max(tile_top[r] + tile_h[r] for r in tile_top) + WASH_PAD
        washes = []  # (id-suffix, x, y, w, h, group)
        for group, rows in COLORIZE_GROUP_ROWS.items():
            if settings.get(f"{group}_colorization"):
                washes += [(rk, row_l, tile_top[rk] - WASH_PAD, row_r - row_l,
                            tile_h[rk] + 2 * WASH_PAD, group) for rk in rows if rk in row_y]
        for group, cols in COLORIZE_GROUP_COLS.items():
            if settings.get(f"{group}_colorization"):
                washes += [(f"col:{ck}", col_x[ck] - WASH_PAD, col_t, col_w[ck] + 2 * WASH_PAD,
                            col_b - col_t, group) for ck in cols if ck in col_x]
        for suffix, x, y, w, h, _ in washes:  # every white base first (painted underneath)
            blocks.append(Block(f"washbase:{suffix}", x, y, w, h, tint="base"))
        for suffix, x, y, w, h, group in washes:  # then the darken colour layers over them
            blocks.append(Block(f"wash:{suffix}", x, y, w, h, tint=group))

    # quantity symbol + name stacked inside each tile, below its values + bottom
    # frame: the symbol line (toggled by symbols) on top, the long-form name
    # (toggled by names) under it. Equivalences extends the symbol line with the
    # quantity's defining equation — the "= …" continuation appended to the glyph,
    # so it reads e.g. "𝒕 = 𝒈𝑀"; turning it on shows the glyph too (the equation's
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
            # wrap within the header width (col_head_w): for interest this is its
            # steady header, not its content, so the caption stays put as intervals
            # are added and overhangs the narrow tiles to the right, like the header
            ch = _wrap_lines(name, col_head_w[ckey]) * CAPTION_LINE  # hug this name's own lines
            cells.append(CellBox(f"caption:{rkey}:{ckey}", col_x[ckey], cy, col_head_w[ckey], ch,
                                 "caption", text=name, underlines=underlines))

    # the plain-text box sits directly below the symbol/caption stack; the preselect
    # chooser rides one plain-text band lower (so preselects appear under plain text).
    def ptext_band_y(rkey):
        return row_y[rkey] + row_h[rkey] + row_frame[rkey] + row_sym[rkey] + row_cap[rkey]

    # preselect chooser dropdowns, in the reserved band below each governing tile's
    # plain-text box. The tuning/target choosers carry the live selection; the
    # temperament chooser is a placeholder (it loads, not mirrors). These are controls,
    # so they ride the tile whether or not math expressions has emptied its values.
    if show_preselects:
        preselect_text = {"temperament": "", "tuning": tuning_scheme, "target": target_spec}
        for name, rkey, ckey in PRESELECTS:
            if not tile_open(rkey, ckey):
                continue
            py = ptext_band_y(rkey) + row_ptext[rkey]  # below the plain-text band
            pw = min(col_w[ckey], TARGET_PRESELECT_W if name == "target" else PRESELECT_W)
            cells.append(CellBox(f"preselect:{name}", col_x[ckey], py, pw, PRESELECT_H, "preselect", text=preselect_text[name]))

    # plain-text value band: each tile's value as its natural EBK string, directly
    # below the symbol/caption stack (above the preselect chooser). The two editable
    # duals (mapping, comma basis) render as inputs that drive the grid; every other
    # value is read-only. The app shrinks each box's font so the value fits one line.
    if show_ptext:
        for (rkey, ckey), text in ptext_strings.items():
            if not tile_open(rkey, ckey):
                continue
            kind = "ptextedit" if (rkey, ckey) in EDITABLE_PTEXT else "ptext"
            # while a comma is pending the comma-basis string reddens to match the grid
            pend = pending is not None and (rkey, ckey) == ("vectors", "commas")
            cells.append(CellBox(f"ptext:{rkey}:{ckey}", col_x[ckey], ptext_band_y(rkey),
                                 col_w[ckey], ptext_height(rkey, ckey), kind, text=text, pending=pend))
        # the quantities-row ratios get their plain text per column, directly below
        # each ratio (the mockup), one inline "n/d" per cell — not packed into a set
        for ckey, left, ratios in (("commas", comma_left, comma_ratios), ("targets", target_left, targets)):
            if tile_open("quantities", ckey):
                qy = ptext_band_y("quantities")
                for i, ratio in enumerate(ratios):
                    cells.append(CellBox(f"ptext:quantities:{ckey}:{i}", left(i), qy, COL_W, PTEXT_H, "ptext", text=ratio))

    # a framed matrix's top bracket + bottom brace stand off the cells by FRAME_GAP:
    # the top bracket just above row 0 (below the toggle head), the brace a matching
    # gap below the last row of that band.
    def frame_top_y(rkey):
        return row_y[rkey] - FRAME_H - FRAME_GAP

    def frame_brace_y(rkey):
        return row_y[rkey] + row_h[rkey] + FRAME_GAP

    # the primes mapping is a stacked-maps matrix, enclosed by a top bracket + bottom
    # brace spanning its whole column
    def map_frame(ckey):
        if not tile_open("mapping", ckey):
            return
        gx, gw = col_x[ckey], col_w[ckey]
        cells.append(CellBox(f"ebktop:{ckey}", gx, frame_top_y("mapping"), gw, FRAME_H, "ebktop"))
        cells.append(CellBox(f"ebkbrace:{ckey}", gx, frame_brace_y("mapping"), gw, BRACE_H, "ebkbrace"))

    map_frame("primes")

    # a matrix of monzo columns: vertical rules separate the columns, and each is
    # marked top + bottom — inset so they stop short of the rules. The foot tells the
    # two apart: a tempered/mapped column (generator coords) closes with a curly brace,
    # a raw (untempered) monzo is a ket and closes with the angle ⟩ (a down-chevron).
    # A bordered grid skips the rules — its own cell borders already divide the columns.
    def monzo_list_marks(rkey, name, ckey, left, n_cols, foot="ebkbrace", bordered=False, pending_col=-1):
        if not tile_open(rkey, ckey):
            return
        mark_w = COL_W - 2 * MARK_INSET
        for c in range(n_cols):
            mx = left(c) + MARK_INSET
            pend = (c == pending_col)  # the draft column's ket marks render red, like its cells
            cells.append(CellBox(f"ebktop:{name}:{c}", mx, frame_top_y(rkey), mark_w, FRAME_H, "ebktop", pending=pend))
            cells.append(CellBox(f"{foot}:{name}:{c}", mx, frame_brace_y(rkey), mark_w, BRACE_H, foot, pending=pend))
        if bordered:  # a bordered grid's own cell borders divide the columns; adding a
            return    # separator rule too would lay a second line over each shared border
        for c in range(1, n_cols):  # a rule on each interior column boundary
            cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, row_y[rkey], SEP_W, row_h[rkey], "vbar"))

    monzo_list_marks("mapping", "mapped_comma", "commas", comma_left, nc)
    monzo_list_marks("mapping", "mapped", "targets", target_left, k)
    monzo_list_marks("mapping", "imapped", "interest", interest_left, mi)
    # the interval-vectors row holds raw (untempered) monzos, so every column is a
    # ket — angle ⟩ feet, not braces. The comma basis is the editable bordered grid
    # (commacell), so it skips the separator rules (its cell borders divide the columns);
    # nc_shown includes the pending draft column so it gets its ket marks too.
    monzo_list_marks("vectors", "vec:commas", "commas", comma_left, nc_shown, foot="ebkangle", bordered=True,
                     pending_col=(nc if pending is not None else -1))
    monzo_list_marks("vectors", "vec:targets", "targets", target_left, k, foot="ebkangle")
    monzo_list_marks("vectors", "vec:interest", "interest", interest_left, mi, foot="ebkangle")

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
    # stand; only a tile's *contents* answer to the value-display toggles, applied
    # here by kind rather than threaded through every emission above. "gridded
    # values" off drops them outright -- numbers, boxes, EBK marks, controls -- so
    # the tiles go empty. "quantities" (general) off is gentler: it keeps the boxes
    # and marks and only blanks the body numbers, baring the gridded structure.
    if not gridded:
        cells = [cb for cb in cells if cb.kind not in GRIDDED_KINDS]
    elif not show_quantities:
        cells = [replace(cb, blank=True, text="") if cb.kind in BLANKED_NUMBER_KINDS else cb
                 for cb in cells]

    return Layout(total_w, total_h, tuple(lines), tuple(blocks), tuple(cells))
