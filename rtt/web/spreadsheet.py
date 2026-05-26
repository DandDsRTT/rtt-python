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
GAP = 20  # px between row/column groups (the visible gap between two grey tiles is GAP - 2*PAD)
PAD = 4  # px a block extends around its cells
WASH_PAD = GAP / 2  # px a colorization wash extends around its cells — wide enough that
# adjacent washed tiles' rects meet across the gap, so the colour reads as one
# continuous band behind the grey tiles (which overhang only by the smaller PAD)
LABEL_W = 96  # row-label gutter width
HEADER_H = 36  # column-header height — two text lines tall, so a multi-word title
# stacks centered onto a second line (via explicit "\n" breaks in col_header, e.g.
# "domain" / "primes"); single-word titles centre as one line
BTN = 15  # px side of a domain +/− control — half the COL_W square mapping/prime cell
MINUS_REVEAL_H = 18  # height the removable prime's hover-minus rises above its header
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap
TOGGLE_INSET = 3  # small grey margin hugging a tile's top-left corner toggle (off the edges and content)
CAPTION_FONT = 9  # px font size of the quantity-name caption (matches the mockup —
# ~0.2 of the cell height; the CSS .rtt-caption must use the same size)
CAPTION_LINE = 10  # px per wrapped caption line (font size + leading); == .rtt-caption line-height
CAPTION_CHAR_W = 0.52  # serif glyph width as a fraction of the font size: a conservative
# (slightly wide) estimate for the greedy caption wrap, so the reservation never falls
# short of the browser's render. Its inverse floors a column wide enough to keep its
# captions within MAX_CAPTION_LINES rather than scaling the font or spilling.
MAX_CAPTION_LINES = 2  # a name wraps to at most this many lines; a longer one widens its tile
PRESELECT_H = 20  # height of a preselect chooser dropdown (when preselects shown)
PRESELECT_W = 124  # its width — fits "<choose temperament>" and caps the wide target tile
TARGET_PRESELECT_W = 132  # wider: the target chooser seats a square limit field + the family select
PTEXT_MAX_FONT = 10  # px cap on the plain-text font; the app shrinks it per box so every value
# always fits on ONE line within its column (a long tuning row just gets smaller text)
PTEXT_H = 13  # px height of a one-line read-only plain-text value
PTEXT_EDIT_H = 16  # px height of an editable plain-text input box (a touch taller than a text line)
SYMBOL_H = 18  # height of the quantity-symbol glyph above the caption (when symbols shown)
UNIT_H = 12  # height of the per-box "units: …" line (below the caption, when units shown)
CHART_H = 64  # height of a per-tile bar chart's plot area (when charts shown)
CHART_GAP = 5  # gap between a chart and the value cells below it
RANGE_CHART_H = 58  # height of the generator tuning-ranges I-beam chart (title + caps + min/max labels)
RANGE_MODE_H = 13  # height of the monotone/tradeoff range-mode selector (one row of square indicators) below the chart
RANGE_GAP = 2  # gap between the ranges chart and its mode selector (and the values above the chart)
OPT_TITLE_H = 14  # height of the optimization box's title strip ("optimization")
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
LINE_W = 2  # px thickness of the shared-axis gridlines: the renderer's .rtt-line border
# weight, and here the overlap by which a convergence bus reaches past its outer sub-lines
# so the rejoin corners stay solid (the cells sit centred on these rules)
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

# The optimization sub-control's interval-list columns carry counts too, just like
# COUNTS: the held-interval count h. Kept separate because these columns are
# conditional (present only with the optimization box), so build() folds them into the
# counts machinery only when shown rather than always, as COUNTS is.
OPTIMIZATION_COUNTS = (
    ("held", "h", "held-interval count"),
)
# Their backing tiles, like COUNTS_TILES. Declared unconditionally — each is inert
# (no panel, toggle or cell) until its column exists, since tile_open gates on the
# column being present (which only happens while the optimization box is shown).
OPTIMIZATION_COUNTS_TILES = tuple(
    (f"block:counts:{ckey}", "counts", ckey) for ckey, *_ in OPTIMIZATION_COUNTS
)

# Quantity-name captions shown inside each (row, column) tile when names are on.
# In the comma column, the rows whose quantity the temperament zeroes out — mapped
# (𝑀C), tempered (𝒕C) and retuned (𝒓C) — append "(made to vanish!)"; the just row
# shows the comma's genuine untempered size, so it omits the note.
CAPTIONS = {
    ("vectors", "commas"): "comma basis",
    ("vectors", "targets"): "target interval list",
    ("canon", "gens"): "generator form matrix",
    ("canon", "primes"): "canonical mapping",
    ("vectors", "held"): "held-interval basis",
    ("vectors", "detempering"): "generator detempering",
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "commas"): "mapped comma basis (made to vanish!)",
    ("mapping", "targets"): "mapped target interval list",
    ("tuning", "gens"): "generator tuning map",
    ("tuning", "primes"): "tuning map",
    ("tuning", "commas"): "tempered comma basis interval size list (made to vanish!)",
    ("tuning", "targets"): "tempered target interval size list",
    ("just", "primes"): "just tuning map",
    ("just", "commas"): "(just) comma basis interval size list",
    ("just", "targets"): "(just) target interval size list",
    ("retune", "primes"): "retuning map",
    ("retune", "commas"): "comma basis interval retuning list (made to vanish!)",
    ("retune", "targets"): "target interval error list",
    ("prescaling", "primes"): "complexity prescaler",
    ("prescaling", "commas"): "complexity prescaled comma basis",
    ("prescaling", "targets"): "complexity prescaled target interval list",
    ("complexity", "primes"): "domain prime complexity map",
    ("complexity", "commas"): "comma basis interval complexity list",
    ("complexity", "targets"): "target interval complexity list",
    ("weight", "targets"): "target interval weight list",
    ("damage", "targets"): "target interval damage list",
    **{("counts", ckey): name for ckey, _sym, name in COUNTS + OPTIMIZATION_COUNTS},
    # Other intervals of interest mirror the targets' rows (minus damage), but with terse
    # one-word captions, not the verbose "...target interval... list" names. This column
    # is narrow (a few user-curated intervals) and grows/shrinks as intervals are added; a
    # long caption would wrap to more lines in the narrow state and fewer in the wide one,
    # reflowing the whole board. A single word stays one line at any width, so the caption
    # band — and the board height — is constant. The left row label and column title carry
    # the full context ("tuning" / "just tuning" rows under "other intervals of interest").
    ("vectors", "interest"): "intervals",
    ("mapping", "interest"): "mapped",
    ("tuning", "interest"): "tempered",
    ("just", "interest"): "just",
    ("retune", "interest"): "errors",
    ("prescaling", "interest"): "prescaled",
    ("complexity", "interest"): "complexity",
    # the held column mirrors the intervals-of-interest rows with the same terse captions
    ("mapping", "held"): "mapped",
    ("tuning", "held"): "tempered",
    ("just", "held"): "just",
    ("retune", "held"): "errors",
    ("complexity", "held"): "complexity",
}
CAPTIONED_ROWS = frozenset(row for row, _ in CAPTIONS)
# The quantity symbol shown above each name when symbols is on. Styling: the maps
# (covectors) are bold-italic (𝒕 𝒋 𝒓); the vector size-lists are bold-upright (𝐚 𝐨
# 𝐞 𝐝); the mapping 𝑀 is math-italic; the interval lists/bases — mapped target list
# Y, comma basis C, target list T — are upright, non-bold. The comma column has no
# dedicated letters — everything but the basis C (in the interval-vectors row) is a
# product with it: the mapped comma basis 𝑀C and the comma sizes 𝒕C, 𝒋C, 𝒓C (damage is
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
    ("prescaling", "primes"): "𝑋",  # the complexity prescaler matrix (math italic, like 𝑀)
    # only the target-interval complexity list carries the bare 𝒄 symbol; the domain-prime
    # map, comma list and interest complexity are derived auxiliaries and carry none
    ("complexity", "targets"): "𝒄",
    ("weight", "targets"): "𝒘",  # bold italic, as in the damage row's diag(𝒘)
    ("damage", "targets"): "𝐝",
}
SYMBOLED_ROWS = frozenset(row for row, _ in SYMBOLS)  # rows that reserve a symbol slot
# multi-row matrices reserve top/bottom frame bands for their EBK marks: the mapping,
# the canonical mapping and the complexity-prescaling matrix for their spanning
# bracket+brace, the interval vectors for the per-column ket marks
FRAMED_ROWS = frozenset({"mapping", "canon", "vectors", "prescaling"})
CHARTED_ROWS = frozenset({"retune", "weight", "damage"})  # rows that grow a bar-chart band above their values when charts shown

# Content-derived colorization (the mockup's coloured washes behind the grey tiles): a
# group's "{group}_colorization" setting, when on, paints colour behind the tiles whose
# quantity is built from that group's fundamental object, showing through the gaps around
# the grey tiles. Each quantity is a product of fundamental objects; a tile is washed by
# whichever *colour-bearing* objects are multiplied into it:
#   "G" — the generator embedding (and the generator tuning map 𝒈, which tunes G) → tuning (cyan)
#   "M" — the (temperament) mapping                                                → temperament (yellow)
#   "C" — the comma basis                                                           → temperament (yellow)
# Everything else is colourless: the domain basis (the primes), the target list T, the
# just tuning map 𝒋, the complexity prescaler 𝑋 and the weight 𝒘. A tile carrying both a
# tuning and a temperament object reads green (the darken blend of the two washes) — e.g.
# the tempered map 𝒕 = 𝒈𝑀 (G·M), and the whole error/damage chain 𝐞 = (𝒈𝑀 − 𝒋)T, whose
# 𝒈𝑀 term keeps its G and M even though 𝒓 is a difference. CELL_FACTORS lists only the
# colour-bearing factors of each tile; a (row, col) absent here carries no wash. Keys
# match TILES / AUDIO_TILES. NB the generators shown in the spine (mapping × quantities)
# are the generator *basis* — a chosen input, neither the embedding G nor the tuning map 𝒈
# — so they're uncoloured, like the domain primes; among built tiles only 𝒈 (the genmap,
# and the 𝒈𝑀 it feeds) is cyan, while the embedding G awaits the deferred form box (𝐹).
_FACTOR_GROUP = {"G": "tuning", "M": "temperament", "C": "temperament"}
CELL_FACTORS: dict[tuple[str, str], frozenset[str]] = {
    # interval-vectors / quantities headers: the comma basis IS C; primes/targets/interest are colourless
    ("quantities", "commas"): frozenset({"C"}),        # the comma ratios = C
    ("vectors", "commas"): frozenset({"C"}),           # the comma basis vectors = C
    # the mapping matrix and its mapped lists are 𝑀 (the mapped comma basis 𝑀C also has C)
    ("mapping", "primes"): frozenset({"M"}),           # 𝑀
    ("mapping", "commas"): frozenset({"M", "C"}),      # 𝑀C
    ("mapping", "targets"): frozenset({"M"}),          # Y = 𝑀T
    ("mapping", "interest"): frozenset({"M"}),         # 𝑀·interest
    ("canon", "primes"): frozenset({"M"}),             # the canonical mapping (𝑀 = 𝐅𝑀_c): still the 𝑀 family
    # the generator tuning map 𝒈 = G; the tempered family 𝒕 = 𝒈𝑀 etc. carry G and M (green)
    ("tuning", "gens"): frozenset({"G"}),              # 𝒈 (the generator tuning map)
    ("tuning", "primes"): frozenset({"G", "M"}),       # 𝒕 = 𝒈𝑀
    ("tuning", "commas"): frozenset({"G", "M", "C"}),  # 𝒕C
    ("tuning", "targets"): frozenset({"G", "M"}),      # 𝐚 = 𝒈𝑀T
    ("tuning", "interest"): frozenset({"G", "M"}),
    # the just sizes carry no G/𝑀; only the comma column has C (the just size of the commas)
    ("just", "commas"): frozenset({"C"}),              # 𝒋C
    # the retuning/error chain 𝒓 = 𝒕 − 𝒋 keeps 𝒕's G and M; the comma column adds C
    ("retune", "primes"): frozenset({"G", "M"}),       # 𝒓 = 𝒈𝑀 − 𝒋
    ("retune", "commas"): frozenset({"G", "M", "C"}),  # 𝒓C
    ("retune", "targets"): frozenset({"G", "M"}),      # 𝐞 = 𝒓T
    ("retune", "interest"): frozenset({"G", "M"}),
    ("damage", "targets"): frozenset({"G", "M"}),      # 𝐝 = |𝐞|diag(𝒘), via 𝐞
    # complexity over the comma basis norms C → temperament; over primes/targets it's colourless
    ("complexity", "commas"): frozenset({"C"}),        # 𝒄 of the comma basis (norm of 𝑋C)
    # the audio rows mirror the just (colourless; comma column C) and tempered (G·M) sizes they sound
    ("just_audio", "commas"): frozenset({"C"}),
    ("mapped_audio", "gens"): frozenset({"G"}),        # the genmap, as the tuning row carries
    ("mapped_audio", "primes"): frozenset({"G", "M"}),
    ("mapped_audio", "commas"): frozenset({"G", "M", "C"}),
    ("mapped_audio", "targets"): frozenset({"G", "M"}),
    ("mapped_audio", "interest"): frozenset({"G", "M"}),
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

# The "<choose form>" chooser (settings["form_controls"]) as (name, row, column): a
# control in the mapping and comma-basis boxes that re-stores that matrix in canonical
# form (an undoable edit). Rides below the tile, like a preselect chooser.
FORM_CHOOSERS = (
    ("mapping", "mapping", "primes"),
    ("comma_basis", "vectors", "commas"),
)
FORM_CHOOSER_ROWS = frozenset(row for _, row, _ in FORM_CHOOSERS)

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
    ("complexity", "targets"): "complexity",  # 𝒄 — only the target list carries the symbol
    ("weight", "targets"): "weight",    # 𝒘
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

# Each box's "units:" annotation (the mockup's per-box unit line, shown below the name
# caption when the general `units` toggle is on). The value is plain ASCII — a fraction
# of base units (generators g, primes p, cents ¢) — which the view (app._units_html and
# the .rtt-units CSS) sets bold in a single-story-g sans face, the mockup's distinct unit
# style. The units follow from the quantity's row and column: the interval-vector lists
# are in primes (p); the mapping matrix is generators-per-prime (g/p) and its mapped
# lists generators (g); the tuning-family maps are cents-per-coordinate (¢/g over
# generators, ¢/p over primes) and their applied size lists plain cents (¢). Keys mirror
# CAPTIONS, so every box with a name also carries a unit (the emission rides the caption loop).
UNITS = {
    ("vectors", "commas"): "p",
    ("vectors", "targets"): "p",
    ("vectors", "held"): "p",
    ("vectors", "detempering"): "p",
    ("vectors", "interest"): "p",
    ("mapping", "primes"): "g/p",
    ("mapping", "commas"): "g",
    ("mapping", "targets"): "g",
    ("mapping", "interest"): "g",
    ("tuning", "gens"): "¢/g",
    ("tuning", "primes"): "¢/p",
    ("tuning", "commas"): "¢",
    ("tuning", "targets"): "¢",
    ("tuning", "interest"): "¢",
    ("just", "primes"): "¢/p",
    ("just", "commas"): "¢",
    ("just", "targets"): "¢",
    ("just", "interest"): "¢",
    ("retune", "primes"): "¢/p",
    ("retune", "commas"): "¢",
    ("retune", "targets"): "¢",
    ("retune", "interest"): "¢",
    ("damage", "targets"): "¢",
    # the weighting region (per the mockup): the prescaler matrix L is octaves per basis
    # element (oct/b), L applied to a vector set is plain octaves (oct); complexity is in
    # complexity units (C) — a map over the primes (C)/b, a list elsewhere (C); weight too.
    ("prescaling", "primes"): "oct/b",
    ("prescaling", "commas"): "oct",
    ("prescaling", "targets"): "oct",
    ("prescaling", "interest"): "oct",
    ("complexity", "primes"): "(C)/b",
    ("complexity", "commas"): "(C)",
    ("complexity", "targets"): "(C)",
    ("complexity", "interest"): "(C)",
    ("weight", "targets"): "(C)",
    # the held column mirrors the interest column's per-row units
    ("mapping", "held"): "g",
    ("tuning", "held"): "¢",
    ("just", "held"): "¢",
    ("retune", "held"): "¢",
    ("complexity", "held"): "(C)",
}
UNITED_ROWS = frozenset(row for row, _ in UNITS)  # rows that reserve a units-line slot

# The weight row's equivalence is scheme-dependent: the weight is the complexity, unity,
# or its reciprocal by the scheme's damage-weight slope (see service.damage_weight_slope),
# so build() picks the right-hand side from this map rather than a fixed headline.
WEIGHT_EQUIVALENCE_BY_SLOPE = {
    "complexityWeight": " = 𝒄",
    "unityWeight": " = 1",
    "simplicityWeight": " = 1/𝒄",
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
    ("block:form", "canon", "gens"),
    ("block:canon", "canon", "primes"),
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
    ("block:prescaling:primes", "prescaling", "primes"),
    ("block:prescaling:commas", "prescaling", "commas"),
    ("block:prescaling:targets", "prescaling", "targets"),
    ("block:complexity:primes", "complexity", "primes"),
    ("block:complexity:commas", "complexity", "commas"),
    ("block:complexity:targets", "complexity", "targets"),
    ("block:weight:targets", "weight", "targets"),
    ("block:damage:targets", "damage", "targets"),
)

# The audio rows' tiles mirror the just / tuning rows they sound: just_audio (the JI
# sizes) over primes/commas/targets, mapped_audio (the tempered sizes) over those plus
# the generators (whose tuned size the tuning row also carries; a generator has no just
# size, so just_audio has no generators tile). The interest column's audio tiles are
# appended dynamically in build() like its other tiles.
AUDIO_TILES = (
    ("block:just_audio:primes", "just_audio", "primes"),
    ("block:just_audio:commas", "just_audio", "commas"),
    ("block:just_audio:targets", "just_audio", "targets"),
    ("block:mapped_audio:gens", "mapped_audio", "gens"),
    ("block:mapped_audio:primes", "mapped_audio", "primes"),
    ("block:mapped_audio:commas", "mapped_audio", "commas"),
    ("block:mapped_audio:targets", "mapped_audio", "targets"),
)

# The domain-units tiles (shown with the specific `domain_units` toggle): the units
# COLUMN holds each row's coordinate-unit labels (the basis primes pᵢ/, the mapping
# generators gᵢ/, the cents tuning rows ¢/); the units ROW holds each column's labels
# (/gᵢ, /pᵢ, /1). They ride the same grey-panel + fold-toggle machinery as TILES, and
# only render when both their row and column bands are present (i.e. the toggle is on).
# The interest column's units-row tile is appended dynamically (like its other tiles).
UNITS_TILES = (
    ("block:ucol:vectors", "vectors", "units"),
    ("block:ucol:mapping", "mapping", "units"),
    ("block:ucol:tuning", "tuning", "units"),
    ("block:ucol:just", "just", "units"),
    ("block:ucol:retune", "retune", "units"),
    ("block:ucol:prescaling", "prescaling", "units"),
    ("block:ucol:complexity", "complexity", "units"),
    ("block:ucol:weight", "weight", "units"),
    ("block:ucol:damage", "damage", "units"),
    ("block:urow:gens", "units", "gens"),
    ("block:urow:primes", "units", "primes"),
    ("block:urow:commas", "units", "commas"),
    ("block:urow:targets", "units", "targets"),
)

# The plain-text tiles whose string is an editable input that drives the grid —
# the two duals the grid itself lets you type into: the mapping (mapping/primes)
# and the comma basis (vectors/commas). Every other plain-text value is read-only.
EDITABLE_PTEXT = frozenset({("mapping", "primes"), ("vectors", "commas")})
EDITABLE_PTEXT_ROWS = frozenset(r for r, _ in EDITABLE_PTEXT)  # rows whose band holds an input
# Rows that carry a plain-text band (every value row; the counts row has none). The
# quantities row's ratios are placed per column, the rest as one EBK string per tile.
PTEXT_ROWS = frozenset({"quantities", "vectors", "mapping", "tuning", "just", "retune", "damage",
                        "prescaling", "complexity", "weight"})

# Cell kinds the value-display toggles filter out. "gridded values" hides
# everything a tile holds besides its fold toggle, name caption and plain-text
# value box: the value numbers (including the just row's "mathexpr" log₂ form),
# the EBK marks framing them, and the domain/comma ± controls. (Gridded off with
# plain text on leaves just the inline string — the two value views are independent.)
GRIDDED_KINDS = frozenset({
    "prime", "target", "commaratio", "genratio", "mapping", "mapped", "commacell",
    "vec", "tval", "mathexpr", "interestcell", "formcell", "heldcell",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "vbar",
    "minus", "plus", "comma_minus", "comma_plus", "basis_minus",
    "interest_minus", "interest_plus", "held_minus", "held_plus", "optimize",
    "boxtitle", "powerinput",
})
# "quantities" (general) is gentler than gridded values: it keeps every cell box
# AND the EBK marks framing them, and only *blanks the numbers* of the body
# quantity values -- the matrix, mapped list, comma basis, generator ratios,
# tuning cents, and the static / plain-text-vector / other-interval value cells --
# so the bare gridded structure remains. (The quantities-row header ratios answer
# to "domain_quantities"; the just row's "mathexpr" log₂ form is not a bare number,
# so math_expressions' own show_value logic trims it.)
BLANKED_NUMBER_KINDS = frozenset({
    "genratio", "mapping", "mapped", "commacell", "vec", "tval", "interestcell", "formcell", "heldcell",
})


def _mathit(letter: str) -> str:
    """A single lowercase ASCII letter as its Unicode Mathematical Italic glyph
    (e.g. ``d`` -> ``𝑑``), so a count's variable reads as math italic like the
    Show panel's example. ``h`` is the one hole in the block — it maps to the
    Planck-constant glyph ``ℎ`` instead of an undefined code point."""
    return "ℎ" if letter == "h" else chr(0x1D44E + ord(letter) - ord("a"))


_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _sub(n: int) -> str:
    """``n`` as Unicode subscript digits (e.g. ``1`` -> ``₁``), for the domain-units
    coordinate labels (p₁/, /g₂) that index each prime/generator."""
    return str(n).translate(_SUBSCRIPTS)


def _ratio_str(element) -> str:
    """A domain element as a ``"num/den"`` ratio: a prime ``p`` -> ``"p/1"``, a nonprime
    element (a Fraction like ``13/5``) -> ``"13/5"`` — the operand its just log₂ is taken over."""
    fraction = Fraction(element)
    return f"{fraction.numerator}/{fraction.denominator}"


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


def _prescale_text(value: float) -> str:
    """A complexity-prescaler matrix entry: a whole number bare (the 0 off-diagonal, and
    log₂2 = 1), else the 3-dp value (log₂3 = 1.585) — keeping the mostly-zero matrix clean."""
    return str(int(value)) if value == int(value) else service.cents(value)


def _format_power(power: float) -> str:
    """The optimization power as shown beside ``𝑝``: ``∞`` for a minimax scheme, else
    the bare integer (``2``, ``1``) — or the decimal for an unusual fractional power."""
    if power == float("inf"):
        return "∞"
    return str(int(power)) if power == int(power) else str(power)


def _lp_objective(damages, power: float) -> float:
    """The optimization objective ⟨𝐝⟩ₚ — the Lp power-mean of the damage list the scheme
    minimizes: ``max`` for a minimax (∞) scheme, the RMS for miniRMS (2), the mean for
    miniaverage (1). The damage chart's horizontal indicator sits at this level."""
    ds = [abs(d) for d in damages]
    if not ds:
        return 0.0
    if power == float("inf"):
        return max(ds)
    return (sum(d ** power for d in ds) / len(ds)) ** (1 / power)


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


def _wrap_chars(words: list[str], max_chars: int) -> int:
    """Greedy line count packing ``words`` into lines of at most ``max_chars`` chars
    (an over-long word breaks across lines itself). The character-budget core shared
    by :func:`_wrap_lines` and its inverse :func:`_min_width_for_lines`."""
    lines, cur = 1, 0
    for word in words:
        wlen = len(word)
        if cur and cur + 1 + wlen > max_chars:  # word won't fit on the current line
            lines, cur = lines + 1, 0
        if cur == 0 and wlen > max_chars:  # the word itself overflows one line
            lines += (wlen - 1) // max_chars
            cur = (wlen - 1) % max_chars + 1
        else:
            cur += (1 if cur else 0) + wlen
    return lines


def _chars_per_line(width: float, font: float = CAPTION_FONT) -> int:
    return max(1, int((width - 4) / (font * CAPTION_CHAR_W)))  # -4: a little padding


def _wrap_lines(text: str, width: float, font: float = CAPTION_FONT) -> int:
    """How many lines ``text`` wraps to in a ``width``-px box at ``font`` px, so the
    tile can reserve the height to hold it. A greedy word wrap with a conservative
    serif char-width estimate. Shared by the name captions and the plain-text boxes."""
    return _wrap_chars(text.split(), _chars_per_line(width, font))


def _min_width_for_lines(text: str, max_lines: int, font: float = CAPTION_FONT) -> int:
    """Smallest box width (px) at which ``text`` wraps to at most ``max_lines`` lines —
    the inverse of :func:`_wrap_lines` in the same char-width model. Floors a column
    wide enough that its captions stay within two lines, widening the tile rather than
    scaling the font or letting a long name spill."""
    words = text.split()
    for chars in range(1, len(text) + 1):  # smallest per-line char budget that fits
        if _wrap_chars(words, chars) <= max_lines:
            return int(chars * font * CAPTION_CHAR_W + 4) + 1  # invert _chars_per_line (round up)
    return int(len(text) * font * CAPTION_CHAR_W + 4) + 1


def _bus_span(positions):
    """The (start, length) of a convergence bus across fanned sub-lines at ``positions``.
    It reaches half a line-width past the outer sub-lines so the rejoin corners stay solid
    at LINE_W; when the sub-lines coincide (a collapsed column or a single element) it
    degenerates to a zero-length point so the merged axis reads as one straight rule."""
    ext = LINE_W if positions[-1] != positions[0] else 0
    return positions[0] - ext / 2, (positions[-1] - positions[0]) + ext


def build(state, settings=None, collapsed=None,
          tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
          pending_comma=None, held_monzos=(), generator_tuning=None) -> Layout:
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
    show_units = settings["units"]  # the in-tile "units: …" line, below each box's caption
    show_domain_units = settings["domain_units"]  # the units row (spine) + units column
    show_temp = settings["temperament_boxes"]
    show_form = settings["form"]  # the canonical-mapping form box (its own row)
    show_form_controls = settings["form_controls"]  # the <choose form> choosers in the mapping/comma-basis boxes
    show_tuning = settings["tuning_boxes"]
    # optimization is a sub-control of tuning boxes: it annotates the tuning region with
    # the scheme's optimization power, so it only applies while that region shows
    show_optimization = show_tuning and settings["optimization"]
    # weighting is likewise a sub-control of tuning boxes: it opens the complexity-
    # prescaling -> complexity -> weight rows that feed the damage row, so it too only
    # applies while the tuning region (and its target column) shows
    show_weighting = show_tuning and settings["weighting"]
    # alt. complexity is a sub-control of weighting: it adds the prescaler dropdown to box 𝐋
    # (the prescaling matrix), so it only applies while that region shows
    show_alt_complexity = show_weighting and settings["alt_complexity"]
    # audio is a top-level toggle (not nested under the tuning boxes): it adds the just /
    # mapped audio rows between counts and quantities. Their per-column tiles still ride the
    # column boxes (targets/interest need tuning boxes; primes/commas/gens need temperament).
    show_audio = settings["audio"]
    # the generator-detempering column (the matrix D) is an independent box toggle
    show_detempering = settings["generator_detempering"]
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
    # the d domain elements: the standard primes, or a nonstandard subgroup's (possibly
    # nonprime) basis. Every interval set is read over this basis (so 13/5 keeps its 13).
    elements = state.domain_basis
    # trait 7: the nonstandard-domain box, when shown, reads the temperament in its prime
    # superspace ("prime-based"); this coincides with the neutral mode on a standard domain,
    # so it is harmless until that box is enabled.
    approach = "prime-based" if settings.get("nonstandard_domain") else ""
    gens = service.generators(state.mapping, elements)
    targets = service.target_interval_set(target_spec, elements)
    k = len(targets)
    mapped = service.mapped_intervals(state.mapping, targets, elements)
    canon_mapping = service.canonical_mapping(state.mapping)  # M defactored + HNF (the form box)
    rc = len(canon_mapping)  # canonical rank (== r for a valid temperament)
    form_M = service.form_matrix(state.mapping)  # F: the generator form matrix (r×r), F·M = canonical
    target_vectors = service.target_interval_monzos(targets, d, elements)  # k monzos, each d-tall
    # held intervals: the optimization box's held-just constraints — user-edited monzos in the
    # held column (like the intervals of interest). The tuning holds each exactly just, so
    # they are folded into service.tuning below. Present only with the optimization sub-control.
    held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(d)) for m in held_monzos) if show_optimization else ()
    nh = len(held)
    held_ratios = service.comma_ratios(held, elements)  # monzo -> "num/den" (the shared renderer)
    # a frozen manual generator tuning (optimize lock off) drives the maps directly; otherwise
    # the scheme's optimum (holding the held intervals just). A stale tuning whose generator
    # count no longer matches the mapping (a rank change) falls back to the optimum.
    if generator_tuning is not None and len(generator_tuning) == len(state.mapping):
        tun = service.tuning_from_generators(state.mapping, generator_tuning, elements)
    else:
        tun = service.tuning(state.mapping, tuning_scheme, elements, approach, held=held_ratios)
    target_sizes = service.interval_sizes(tun, targets, elements)
    held_mapped = service.mapped_intervals(state.mapping, held_ratios, elements)  # M·held (gen coords)
    held_sizes = service.interval_sizes(tun, held_ratios, elements)  # tempered/just/error sizes
    target_weights = service.interval_weights(state.mapping, tuning_scheme, targets)  # the damage row's diag(𝒘)
    comma_ratios = service.comma_ratios(state.comma_basis, elements)
    nc = len(comma_ratios)  # the real commas (those that define the temperament)
    mapped_commas = service.mapped_commas(state.mapping, state.comma_basis)  # M·commas = 0 (vanish)
    comma_sizes = service.interval_sizes(tun, comma_ratios, elements)  # comma sizes (tempered ~0)
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
    interest_ratios = service.comma_ratios(interest, elements)  # monzo -> "num/den" (shared renderer)
    interest_mapped = service.mapped_intervals(state.mapping, interest_ratios, elements)
    interest_sizes = service.interval_sizes(tun, interest_ratios, elements)
    # the complexity row norms each interval's prescaled monzo (𝒄): a covector over the
    # domain elements (each element's complexity, log₂ of it for the default log-prime
    # norm), a list over the comma / target / interest interval sets.
    complexities = {
        "primes": service.interval_complexities(state.mapping, tuning_scheme, tuple(_ratio_str(e) for e in elements)),
        "commas": service.interval_complexities(state.mapping, tuning_scheme, comma_ratios),
        "targets": service.interval_complexities(state.mapping, tuning_scheme, targets),
        "interest": service.interval_complexities(state.mapping, tuning_scheme, interest_ratios),
        "held": service.interval_complexities(state.mapping, tuning_scheme, held_ratios),
    }
    # the prescaler 𝑋: a d×d diagonal matrix over the primes (diag = each prime's pre-norm
    # weight, the values the complexity map norms). log-prime by default: diag(log₂ prime).
    prescaler = service.complexity_prescaler(state.mapping, tuning_scheme)
    interest_tiles = () if not interest else (
        ("block:vec:interest", "vectors", "interest"),
        ("block:interest", "quantities", "interest"),
        ("block:imapped", "mapping", "interest"),
        ("block:tuning:interest", "tuning", "interest"),
        ("block:just:interest", "just", "interest"),
        ("block:retune:interest", "retune", "interest"),
        ("block:urow:interest", "units", "interest"),  # the units row's /1 over the interest column
        ("block:prescaling:interest", "prescaling", "interest"),
        ("block:complexity:interest", "complexity", "interest"),
        ("block:just_audio:interest", "just_audio", "interest"),
        ("block:mapped_audio:interest", "mapped_audio", "interest"),
    )
    # the held-interval column's tiles (computed above): a user-editable interval list, like
    # the intervals of interest. Empty by default, so — like an empty interest column — it
    # then declares no tiles, only its header, axis and the + control to add the first one.
    held_tiles = () if not held else (
        ("block:held", "quantities", "held"),
        ("block:vec:held", "vectors", "held"),
        ("block:hmapped", "mapping", "held"),       # M·held in generator coords
        ("block:tuning:held", "tuning", "held"),    # tempered sizes (= just, since held)
        ("block:just:held", "just", "held"),        # just sizes
        ("block:retune:held", "retune", "held"),    # errors (≈ 0, since held just)
        ("block:complexity:held", "complexity", "held"),
    )
    # The optimization box's other mockup column — unchanged-intervals (count u) — is
    # deferred to the projection feature: the unchanged-interval basis is U = nullspace(P − I),
    # the projection P's eigenvalue-1 eigenvectors (en.xen.wiki/w/Projection#The_unchanged-interval_basis),
    # so it can't be built until projection lands. Until then the box ships with the held
    # column above plus the power line below (held intervals are a subset of the unchanged ones).
    # the generator-detempering column holds the matrix D — one JI interval (a vector) per
    # generator that tempers to it (the mapping's right-inverse), framed like the comma
    # basis / target list. An independent box toggle, riding between domain primes and commas.
    detempering_vectors = service.generator_detempering(state.mapping) if show_detempering else ()
    detempering_tiles = (("block:vec:detempering", "vectors", "detempering"),) if show_detempering else ()
    # the optimization controls (power 𝑝 etc.) nest at the bottom of the damage×targets
    # tile (see opt_box below), not in a tile/row of their own
    tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + TILES + AUDIO_TILES + UNITS_TILES
             + interest_tiles + held_tiles + detempering_tiles)
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
    # over targets). A collapsed column folds to a strip sized to read its title, but never
    # wider than it was open — so collapsing a column only ever narrows it (see col_w below).
    # The domain/comma + controls ride just right of their blocks when open; each −
    # is a hover affordance on the removable highest-prime / last-comma column.
    # the domain column reads "domain elements" over a nonstandard subgroup (whose basis
    # may be nonprime) and "domain primes" over a standard prime limit (per the mockup note)
    domain_title = "domain\nprimes" if service.is_standard_domain(elements) else "domain\nelements"
    col_header = {"quantities": "quantities", "units": "units", "gens": "generators",
                  "primes": domain_title, "detempering": "generator\ndetempering",
                  "commas": "commas",
                  "held": "held\nintervals", "targets": "target\nintervals",
                  "interest": "other intervals\nof interest"}
    # The leftmost quantities column is the spine: a header + fold toggle + a single
    # vertical rule, the column-axis dual of the quantities spine row. The units column
    # (the specific `domain_units` toggle) is a second spine column right after it,
    # carrying each row's coordinate-unit labels (pᵢ/, gᵢ/, ¢/). Each spine holds a single
    # COL_W-wide index per row (a basis square / generator ratio; a unit label) and so is
    # one COL_W wide — its longer header overhangs it (see the col_w hug-content rule above).
    # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
    # the value cells are inset by BRACKET_W within the group.
    col_bands = (
        ("quantities", COL_W, show_domain_quantities, True),
        ("units", COL_W, show_domain_units, True),
        ("gens", 2 * BRACKET_W + r * COL_W, show_temp, True),
        ("primes", 2 * BRACKET_W + d * COL_W, show_temp, True),
        ("detempering", 2 * BRACKET_W + r * COL_W, show_detempering, True),
        ("commas", 2 * BRACKET_W + nc_shown * COL_W, show_temp, True),
        ("held", 2 * BRACKET_W + nh * COL_W, show_optimization, True),
        ("targets", 2 * BRACKET_W + k * COL_W, show_tuning, True),
        # The interest column's tiles hug this content width (32 + mi·COL_W) — no empty
        # padding. Its long two-line title needs more room, so the column's *footprint*
        # is floored at the title width (see the loop below) and the narrow content is
        # centred within it: the title centres over the whole column on its gridline, and
        # the tiles centre on that same gridline. The board height is independent of mi.
        ("interest", 2 * BRACKET_W + mi * COL_W, show_tuning, True),
    )
    # A fold-toggle node column sits between the row-label gutter and the content
    # (when names show); content starts past it with a clear gap so the tiles
    # never collide with the nodes. Row lines fan from the node's right edge so
    # their gaps match the columns'.
    node_x = label_w + GAP
    node_edge = node_x + TOGGLE  # the node's content-facing (right) edge
    content_x0 = node_x + TOGGLE + GAP

    # Row bands top-to-bottom: (key, natural height, present, collapsible, label), laid
    # out below by the same running-cursor rule as the columns. Defined here, ahead of
    # that layout, so each column's width can reserve room for its present rows' captions.
    row_bands = (
        ("counts", ROW_H, show_counts, True, "counts"),
        ("just_audio", ROW_H, show_audio, True, "just audio"),
        ("mapped_audio", ROW_H, show_audio, True, "mapped audio"),
        ("quantities", ROW_H, show_domain_quantities, True, "quantities"),
        ("units", ROW_H, show_domain_units, True, "units"),
        ("vectors", d * ROW_H, show_temp, True, "interval vectors"),
        ("canon", rc * ROW_H, show_form, True, "canonical mapping"),
        ("mapping", r * ROW_H, show_temp, True, "mapping"),
        ("tuning", ROW_H, show_tuning, True, "tuning"),
        ("just", ROW_H, show_tuning, True, "just tuning"),
        ("retune", ROW_H, show_tuning, True, "retuning"),
        ("prescaling", d * ROW_H, show_weighting, True, "complexity prescaling"),
        ("complexity", ROW_H, show_weighting, True, "complexity"),
        ("weight", ROW_H, show_weighting, True, "weight"),
        ("damage", ROW_H, show_tuning, True, "damage"),
    )
    # the present rows that carry an in-tile caption; a column is floored wide enough to
    # keep each of these within MAX_CAPTION_LINES (see _caption_floor in the loop)
    present_caption_rows = frozenset(
        key for key, _h, present, _c, _l in row_bands if present and key in CAPTIONED_ROWS)

    def _caption_floor(key):
        # the width an open column needs so its captions stay within MAX_CAPTION_LINES,
        # widening the tile rather than scaling the font or letting a long name spill;
        # zero when names are hidden (no caption renders) so the column keeps its content size
        if not show_captions:
            return 0
        return max((_min_width_for_lines(CAPTIONS[(rk, key)], MAX_CAPTION_LINES)
                    for rk in present_caption_rows
                    if (rk, key) in CAPTIONS and (rk, key) in declared_tiles), default=0)

    # the domain, the comma basis and the interest set each ride an expand (+) control
    # just inside the right of their (open) tile — domain primes add a prime, commas
    # add a comma, interest adds a blank interval to edit
    col_x, col_w, content_w, col_collapsible = {}, {}, {}, {}
    ctrl_x = {}
    plus_cols = set()  # columns whose + rides inside the tile (the tile overhangs it a margin)
    x = content_x0
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        collapsed_col = f"col:{key}" in collapsed
        hug_w = max(natural, _caption_floor(key))  # the open footprint: hugs content (+ caption room)
        # The content (value cells + their bracket gutters) is the natural width. The column
        # footprint (col_w) hugs that content, or widens where a long caption needs the room;
        # it does NOT reserve room for a wider title. A title wider than its column (the
        # "quantities"/"units" spines, the long interest header) overhangs it instead, rendered
        # without wrapping and centred on the column gridline. The grey tile fills the footprint,
        # with content centred within it (see content_x).
        if collapsed_col:
            # Folded to a title strip — sized to read the (widest line of the) title, but capped
            # at the open footprint so collapsing never WIDENS a column: one already narrower than
            # its title (a spine) keeps its width, the title overhanging, instead of ballooning out.
            col_w[key] = content_w[key] = min(hug_w, _title_w(col_header[key]))
        else:
            content_w[key] = natural
            col_w[key] = hug_w  # the footprint widens for a long caption
        col_collapsible[key] = collapsible
        # a +-bearing column (an open domain/comma/interest set with cells) carries an in-tile
        # + on the panel's right edge (seated below). Reserve an extra FRAME_GAP of tile
        # overhang on EACH side, so the + clears the edge and the tile stays centred on the
        # gridline (panel_rect draws the overhang).
        in_tile_plus = (key in ("primes", "commas", "interest", "held") and not collapsed_col
                        and content_w[key] > 2 * BRACKET_W)
        if in_tile_plus:
            x += FRAME_GAP  # the left overhang
        col_x[key] = x
        x += col_w[key]
        if in_tile_plus:
            plus_cols.add(key)
            x += FRAME_GAP  # the right overhang, so the next column still clears the tile
        x += GAP
    total_w = x

    # Content is centred within each footprint: the margin is (footprint − content) / 2,
    # zero for the common case (content fills the column) and positive only where a long
    # caption widened the footprint, reserving even margins around the narrower content.
    content_x = {key: col_x[key] + (col_w[key] - content_w[key]) / 2 for key in col_x}

    def content_box(key):
        # the (x, width) of a column's actual content — the value cells and the brackets/
        # axes that hug them, centred within the (possibly wider) tile and footprint
        return content_x[key], content_w[key]

    def tile_box(key):
        # the (x, width) of a column's grey tile/panel: the full footprint (the panel fills it
        # and overhangs by tile_pad). The caption stack rides this width; content centres within.
        return col_x[key], col_w[key]

    def tile_pad(key):
        # how far a tile's grey panel overhangs its content on each side: PAD normally, plus
        # an extra FRAME_GAP for a +-bearing column so its + clears the panel's right edge
        # (kept equal both sides → the tile stays centred on the gridline)
        return PAD + (FRAME_GAP if key in plus_cols else 0)

    primes_x = content_x.get("primes")  # centred content-left; None when the column is hidden
    commas_x = content_x.get("commas")  # None when the commas column is hidden
    targets_x = content_x.get("targets")  # None when the target intervals column is hidden
    interest_x = content_x.get("interest")  # None when the interest column is hidden
    held_x = content_x.get("held")  # None when the held-intervals column is hidden
    detempering_x = content_x.get("detempering")  # None when the generator-detempering column is hidden

    def col_open(key):
        return key in col_x and f"col:{key}" not in collapsed

    # the in-tile + (add a prime / comma / interest interval) rides the right edge of its grey
    # panel — FRAME_GAP in, panel-relative like the fold toggle and audio bank — so a caption-
    # widened column (commas) keeps it on the edge rather than drifting it inward with the
    # re-centred content. Equals the old content-relative seat wherever tile == content (every
    # un-widened column). An empty interest set has no cells, so its lone + centres on the gridline.
    for key in ("primes", "commas", "interest", "held"):
        if not col_open(key):
            continue
        if key in plus_cols:
            tx, tw = tile_box(key)
            ctrl_x[key] = tx + tw + tile_pad(key) - FRAME_GAP - BTN
        else:
            ctrl_x[key] = col_x[key] + col_w[key] / 2 - BTN / 2

    # The generator tuning-ranges box (the chart + its mode selector) nests at the bottom
    # of the generator tuning map tile when tuning_ranges is on. Its extra height is
    # reserved in the tuning row (below) so the rows beneath drop clear of it rather than
    # the box spilling across them. Determinable up front: it rides the open, uncollapsed
    # gens tile of the (present, unfolded) tuning row.
    gtm_chart = (show_ranges and show_tuning and "row:tuning" not in collapsed
                 and col_open("gens") and "tile:tuning:gens" not in collapsed)
    gtm_extra = (RANGE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if gtm_chart else 0
    # the alt.-complexity controls nest at the bottom of their matrix/list tiles (like the
    # ranges box in the gens tile): the prescaler chooser under the prescaling matrix (box 𝐋,
    # over the primes) and the complexity-norm chooser under the complexity list (box 𝒄, over
    # the targets). Each tile's height is reserved up front so the rows below drop clear.
    presc_ctrl = (show_alt_complexity and "row:prescaling" not in collapsed
                  and col_open("primes") and "tile:prescaling:primes" not in collapsed)
    presc_extra = (RANGE_GAP + PRESELECT_H) if presc_ctrl else 0
    norm_ctrl = (show_alt_complexity and "row:complexity" not in collapsed
                 and col_open("targets") and "tile:complexity:targets" not in collapsed)
    norm_extra = (RANGE_GAP + PRESELECT_H) if norm_ctrl else 0
    # the optimization controls (the power 𝑝 etc.) nest at the bottom of the target-interval
    # damage list tile (like the ranges box in the gens tile), gated on the optimization
    # sub-control. Reserve their height up front so the board stays clear below the tile.
    opt_ctrl = (show_optimization and "row:damage" not in collapsed
                and col_open("targets") and "tile:damage:targets" not in collapsed)
    # the optimization box: a title strip over two rows (objective ⟨d⟩ₚ + power 𝑝 on the
    # left, the optimize button spanning them on the right)
    opt_extra = (RANGE_GAP + OPT_TITLE_H + 2 * ROW_H) if opt_ctrl else 0
    # Each of these nested controls lives at the bottom of ONE tile of its row (keyed here by
    # row -> (owning column, reserved height)). Its height is reserved across the whole row's
    # tile_h so the rows below clear it, but only the OWNING tile actually grows to enclose it
    # — sibling tiles hug their own content height (see tile_height, used by the panels/washes).
    tile_extra = {
        "tuning": ("gens", gtm_extra),       # the generator tuning-ranges chart (box in the genmap)
        "prescaling": ("primes", presc_extra),  # the alt-complexity prescaler chooser (box 𝐋)
        "complexity": ("targets", norm_extra),  # the alt-complexity norm chooser (box 𝒄)
        "damage": ("targets", opt_extra),    # the optimization controls under the damage list
    }

    header_y = 0
    col_node_y = header_h + (GAP - TOGGLE) / 2  # the column toggle sits just under the header text
    # Branching (trunk/bus/verticals) starts just below the column nodes so no
    # line pokes up past them; with names hidden it starts at the very top.
    branch_top_y = col_node_y + TOGGLE
    rows_top_y = branch_top_y + GAP  # top of the first row band (counts when shown, else quantities)
    # The grey tiles overhang their cells by PAD and sit over the gridlines, so the
    # *visible* fan segment runs from a bus only to the tile edge. FAN places each bus
    # midway between the node/foot edge and the tile edge (PAD inside the cell), so
    # the inner (bus->tile) and outer (node->bus) segments are equal: (GAP-PAD)/2.
    FAN = (GAP - PAD) / 2

    # row_bands (the top-to-bottom band list) is defined above, ahead of the column
    # widths so they can reserve room for each present row's caption. Every row folds to
    # a strip via its toggle; "quantities" additionally hides that row and its column.
    # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
    # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
    row_y, row_h, row_label, row_collapsible = {}, {}, {}, {}
    tile_h, tile_top, row_frame, row_sym, row_cap, row_units, row_ptext, chart_top = {}, {}, {}, {}, {}, {}, {}, {}
    row_pre = {}  # the preselect band height, so the <choose form> chooser can stack below it

    def caption_band(key, folded):
        # the row's caption band is sized to its tallest (wrapped) caption, so the longest
        # name fits within its tile rather than spilling off a narrow column. Only columns
        # that actually render a tile here count: an empty interest column declares no
        # tile, so it reserves no caption height (its captions would otherwise wrap tall in
        # the bare bracket-gutter stub and inflate the empty board). Each caption wraps
        # within its own tile's content width.
        if not (show_captions and key in CAPTIONED_ROWS and not folded):
            return 0
        lines = [_wrap_lines(CAPTIONS[(key, c)], col_w[c]) for c in col_x
                 if (key, c) in CAPTIONS and (key, c) in declared_tiles
                 and col_open(c) and f"tile:{key}:{c}" not in collapsed]
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
        # the units line reserves a slot below the caption (above the plain-text box)
        # for every united row, like the symbol slot above the caption
        uni = UNIT_H if (show_units and key in UNITED_ROWS and not folded) else 0
        # below the caption/units a tile reserves bands for the plain-text value box and
        # the preselect chooser (its row), stacked in that order
        pre = PRESELECT_H if (show_preselects and key in PRESELECT_ROWS and not folded) else 0
        # the <choose form> chooser rides one band below the preselect chooser, in the
        # mapping and comma-basis boxes, when form controls are shown
        formctrl = PRESELECT_H if (show_form_controls and key in FORM_CHOOSER_ROWS and not folded) else 0
        ptext = ptext_band(key, folded)
        row_h[key] = STRIP if folded else natural
        tile_top[key] = y
        if charted:
            chart_top[key] = y + head + top_frame  # the chart sits just below the top frame
        row_y[key] = y + head + top_frame + chart_band  # values sit below toggle head, top frame, chart
        row_frame[key] = bot_frame  # the symbol/caption stack sits below the bottom brace band
        row_sym[key] = sym  # the caption (and bands below it) sit below the symbol slot
        row_cap[key] = cap  # the units line and plain-text box sit below the caption
        row_units[key] = uni  # the plain-text box and preselect chooser sit below the units line
        row_ptext[key] = ptext  # the plain-text band, with the preselect chooser below it
        row_pre[key] = pre  # the preselect band, with the <choose form> chooser below it
        row_label[key] = label
        row_collapsible[key] = collapsible
        tile_h[key] = head + top_frame + chart_band + row_h[key] + bot_frame + sym + cap + uni + pre + ptext + formctrl
        # a row with a nested tile-control (ranges chart, alt-complexity chooser, optimization
        # block) reserves its height here so the rows below drop clear of it; the control's
        # owning tile grows to enclose it while its siblings stay at base height (see tile_height)
        tile_h[key] += tile_extra.get(key, (None, 0))[1]
        y += tile_h[key] + GAP
    total_h = y

    # Each multi-element column runs a single trunk down to the fan-out bus, where it
    # splits into one line per element. The bus sits centred in the whitespace of a GAP
    # between row bands -- by default the gap above the first row band (FAN below the
    # branch top). But the counts row shows one value per column (a cardinality), so when
    # it's present the trunk stays single through it and the split drops to the gap below
    # the counts tile, centred between that tile and the row beneath it.
    fanout_y = branch_top_y + FAN
    if "counts" in row_y:
        fanout_y = tile_top["counts"] + tile_h["counts"] + GAP / 2

    def row_open(key):
        return key in row_y and f"row:{key}" not in collapsed

    def tile_open(rkey, ckey):  # a real tile, whose row + column are open and not folded
        return ((rkey, ckey) in declared_tiles and row_open(rkey) and col_open(ckey)
                and f"tile:{rkey}:{ckey}" not in collapsed)

    def cell_unit(rkey, ckey, *, gen=None, prime=None):
        # the per-value unit shown beneath a gridded cell when units is on: the tile's
        # unit (UNITS) with its g/p variables subscripted by this cell's generator/prime
        # index — so the g/p mapping reads g₁/p₁, the tuning map ¢/p₁, a mapped list g₁.
        if not show_units:
            return ""
        u = UNITS.get((rkey, ckey), "")
        if gen is not None:
            u = u.replace("g", f"g{_sub(gen + 1)}")
        if prime is not None:
            u = u.replace("p", f"p{_sub(prime + 1)}")
        return u

    def prime_left(p):
        return primes_x + BRACKET_W + p * COL_W

    def comma_left(c):
        return commas_x + BRACKET_W + c * COL_W

    def target_left(j):
        return targets_x + BRACKET_W + j * COL_W

    def interest_left(i):
        return interest_x + BRACKET_W + i * COL_W

    def held_left(i):
        return held_x + BRACKET_W + i * COL_W

    def detempering_left(i):  # the i-th generator detempering column
        return detempering_x + BRACKET_W + i * COL_W

    def gen_left(g):  # the g-th generator column in the generators box (its tuning-map cells)
        return content_x["gens"] + BRACKET_W + g * COL_W

    def map_top(i):
        return row_y["mapping"] + i * ROW_H

    def canon_top(i):  # the y of canonical-mapping row i (the r stacked canonical maps)
        return row_y["canon"] + i * ROW_H

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
        cardinality = {"gens": r, "primes": d, "commas": state.n, "targets": k, "held": nh}
        for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS:
            if tile_open("counts", ckey):
                cells.append(CellBox(f"count:{ckey}", col_x[ckey], row_y["counts"], col_w[ckey], ROW_H,
                                     "count", text=f"{_mathit(sym)} = {cardinality[ckey]}"))

    # units row + column (the specific `domain_units` toggle): coordinate-unit labels.
    # The units COLUMN labels each row's coordinate — the interval-vectors basis in
    # primes (pᵢ/), the mapping in generators (gᵢ/), the cents tuning rows as ¢/. The
    # units ROW labels each column's coordinate — /gᵢ over generators, /pᵢ over the
    # domain primes, /1 over the ratio columns. Each rides its own grey tile
    # (UNITS_TILES), so tile_open gates emission against the live layout.
    if tile_open("vectors", "units"):
        for p in range(d):
            cells.append(CellBox(f"ucol:vectors:{p}", col_x["units"], vec_top(p), col_w["units"], ROW_H,
                                 "units", text=f"p{_sub(p + 1)}/"))
    if tile_open("mapping", "units"):
        for i in range(r):
            cells.append(CellBox(f"ucol:mapping:{i}", col_x["units"], map_top(i), col_w["units"], ROW_H,
                                 "units", text=f"g{_sub(i + 1)}/"))
    for key in ("tuning", "just", "retune", "damage"):
        if tile_open(key, "units"):
            cells.append(CellBox(f"ucol:{key}", col_x["units"], row_y[key], col_w["units"], ROW_H,
                                 "units", text="¢/"))
    # the weighting rows' units-column labels: the prescaler is octaves (one per matrix row,
    # like the d-tall interval vectors), complexity and weight are complexity units (C)/
    if tile_open("prescaling", "units"):
        for i in range(d):
            cells.append(CellBox(f"ucol:prescaling:{i}", col_x["units"], row_y["prescaling"] + i * ROW_H,
                                 col_w["units"], ROW_H, "units", text="oct/"))
    for key in ("complexity", "weight"):
        if tile_open(key, "units"):
            cells.append(CellBox(f"ucol:{key}", col_x["units"], row_y[key], col_w["units"], ROW_H,
                                 "units", text="(C)/"))
    if "units" in row_y:
        uy = row_y["units"]
        if tile_open("units", "gens"):
            for g in range(r):
                cells.append(CellBox(f"urow:gens:{g}", gen_left(g), uy, COL_W, ROW_H, "units", text=f"/g{_sub(g + 1)}"))
        if tile_open("units", "primes"):
            for p in range(d):
                cells.append(CellBox(f"urow:primes:{p}", prime_left(p), uy, COL_W, ROW_H, "units", text=f"/p{_sub(p + 1)}"))
        if tile_open("units", "commas"):
            for c in range(nc):
                cells.append(CellBox(f"urow:commas:{c}", comma_left(c), uy, COL_W, ROW_H, "units", text="/1"))
        if tile_open("units", "targets"):
            for j in range(k):
                cells.append(CellBox(f"urow:targets:{j}", target_left(j), uy, COL_W, ROW_H, "units", text="/1"))
        if tile_open("units", "interest"):
            for ii in range(mi):
                cells.append(CellBox(f"urow:interest:{ii}", interest_left(ii), uy, COL_W, ROW_H, "units", text="/1"))

    # quantities row: domain primes (+ controls) and target ratios (below the
    # tile's toggle head, like every other row's values). The whole row -- its
    # headers and the domain/comma ± controls riding it -- answers to the specific
    # "quantities" toggle, which drops it from row_y via its present flag.
    if "quantities" in row_y:
        qy = row_y["quantities"]
        if tile_open("quantities", "primes"):
            for p in range(d):
                cells.append(CellBox(f"prime:{p}", prime_left(p), qy, COL_W, ROW_H, "prime", text=str(elements[p]), prime=p))
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
        if tile_open("quantities", "held"):  # the held intervals, edited like the intervals of interest
            for i in range(nh):
                # the derived ratio (read-only, from the editable monzo) heads each column
                cells.append(CellBox(f"held:{i}", held_left(i), qy, COL_W, ROW_H, "commaratio", text=held_ratios[i], comma=i))
                # each held interval carries its own − (a hover affordance over its header)
                cells.append(CellBox(f"held_minus:{i}", held_left(i), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "held_minus", comma=i))
        # the held + rides col_open (like interest's): an empty-but-open held column shows its
        # + so the first held interval can be added, even with no tile yet
        if col_open("held") and row_open("quantities"):
            cells.append(CellBox("held_plus", ctrl_x["held"], qy + (ROW_H - BTN) // 2, BTN, BTN, "held_plus"))
        if tile_open("quantities", "interest"):  # the user's other intervals of interest
            for i in range(mi):
                # the derived ratio (read-only, from the monzo) heads each column, like a comma's
                cells.append(CellBox(f"interest:{i}", interest_left(i), qy, COL_W, ROW_H, "commaratio", text=interest_ratios[i], comma=i))
                # every interval carries its own − (a hover affordance over its header):
                # any one is removable, unlike the domain/comma last-only −
                cells.append(CellBox(f"interest_minus:{i}", interest_left(i), qy - MINUS_REVEAL_H, COL_W, MINUS_REVEAL_H + ROW_H, "interest_minus", comma=i))
        # the + rides col_open, not tile_open: an empty-but-open interest column declares
        # no tile yet, but must still show its + so the first interval can be added (a blank
        # 1/1 — a zero monzo — to edit in the vectors row). With intervals present ctrl_x
        # seats it inside the tile like the domain/comma +; empty, it centres on the gridline.
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
                    cells.append(CellBox(f"cell:mapping:{i}:{p}", prime_left(p), map_top(i), COL_W, ROW_H, "mapping", gen=i, prime=p, unit=cell_unit("mapping", "primes", gen=i, prime=p)))
            if tile_open("mapping", "targets"):
                for j in range(k):
                    cells.append(CellBox(f"cell:mapped:{i}:{j}", target_left(j), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped[i][j]), gen=i, unit=cell_unit("mapping", "targets", gen=i)))
            if tile_open("mapping", "interest"):  # interest mapped through M, like the targets
                for ii in range(mi):
                    cells.append(CellBox(f"cell:imapped:{i}:{ii}", interest_left(ii), map_top(i), COL_W, ROW_H, "mapped", text=str(interest_mapped[i][ii]), gen=i, unit=cell_unit("mapping", "interest", gen=i)))
            if tile_open("mapping", "held"):  # held mapped through M, like the targets / interest
                for hi in range(nh):
                    cells.append(CellBox(f"cell:hmapped:{i}:{hi}", held_left(hi), map_top(i), COL_W, ROW_H, "mapped", text=str(held_mapped[i][hi]), gen=i, unit=cell_unit("mapping", "held", gen=i)))
            # the comma basis mapped through M — it vanishes to 0 (parallel to the
            # mapped target list); the raw basis lives in the interval-vectors row
            if tile_open("mapping", "commas"):
                for c in range(nc):
                    cells.append(CellBox(f"cell:mapped_comma:{i}:{c}", comma_left(c), map_top(i), COL_W, ROW_H, "mapped", text=str(mapped_commas[i][c]), gen=i, unit=cell_unit("mapping", "commas", gen=i)))

    # the canonical-mapping form box: M in canonical form (defactored + HNF), a stack of
    # read-only maps over the primes, framed like the mapping matrix one row above it; the
    # generator form matrix F (units 𝒈/𝒈) rides its gens column as a bordered r×r grid
    if row_open("canon"):
        if tile_open("canon", "primes"):
            for i in range(rc):
                for p in range(d):
                    cells.append(CellBox(f"cell:canon:{i}:{p}", prime_left(p), canon_top(i), COL_W, ROW_H, "mapped", text=str(canon_mapping[i][p])))
        if tile_open("canon", "gens"):
            for i in range(len(form_M)):
                for j in range(len(form_M)):
                    cells.append(CellBox(f"cell:form:{i}:{j}", gen_left(j), canon_top(i), COL_W, ROW_H, "formcell", text=str(form_M[i][j])))

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
                cells.append(CellBox(f"basis:{p}", bx, vec_top(p), COL_W, ROW_H, "prime", text=str(elements[p]), prime=p))
            if d > 1:  # the highest prime is the removable one (shrink trims the last)
                cells.append(CellBox("basis_minus", col_x["quantities"], vec_top(d - 1), col_w["quantities"], ROW_H, "basis_minus"))
            cells.append(CellBox("basis_plus", bx + (COL_W - BTN) / 2, vec_top(d) + FRAME_GAP, BTN, BTN, "plus"))
        if tile_open("vectors", "commas"):
            for c in range(nc):
                for p in range(d):
                    cells.append(CellBox(f"cell:comma:{p}:{c}", comma_left(c), vec_top(p), COL_W, ROW_H, "commacell", text=str(state.comma_basis[c][p]), prime=p, comma=c, unit=cell_unit("vectors", "commas", prime=p)))
            if pending is not None:  # the draft column: blank, red-outlined cells the user fills in
                for p in range(d):
                    v = pending[p]
                    cells.append(CellBox(f"cell:comma:{p}:{nc}", comma_left(nc), vec_top(p), COL_W, ROW_H, "commacell",
                                         text="" if v is None else str(v), prime=p, comma=nc, pending=True, unit=cell_unit("vectors", "commas", prime=p)))
        if tile_open("vectors", "targets"):
            for j in range(k):
                for p in range(d):
                    cells.append(CellBox(f"cell:vec:targets:{j}:{p}", target_left(j), vec_top(p), COL_W, ROW_H, "vec", text=str(target_vectors[j][p]), unit=cell_unit("vectors", "targets", prime=p)))
        if tile_open("vectors", "held"):  # the held intervals as editable monzos, like the intervals of interest
            for i in range(nh):
                for p in range(d):
                    cells.append(CellBox(f"cell:held:{p}:{i}", held_left(i), vec_top(p), COL_W, ROW_H, "heldcell", text=str(held[i][p]), prime=p, comma=i, unit=cell_unit("vectors", "held", prime=p)))
        if tile_open("vectors", "detempering"):  # the matrix D, one vector column per generator
            for i in range(r):
                for p in range(d):
                    cells.append(CellBox(f"cell:vec:detempering:{i}:{p}", detempering_left(i), vec_top(p), COL_W, ROW_H, "vec", text=str(detempering_vectors[i][p]), unit=cell_unit("vectors", "detempering", prime=p)))
        if tile_open("vectors", "interest"):  # the user's intervals of interest: editable monzos, like the comma basis
            for i in range(mi):
                for p in range(d):
                    cells.append(CellBox(f"cell:interest:{p}:{i}", interest_left(i), vec_top(p), COL_W, ROW_H, "interestcell", text=str(interest[i][p]), prime=p, comma=i, unit=cell_unit("vectors", "interest", prime=p)))

    # the three value groups share an element name (for cell ids), a left-edge
    # accessor, and the operand of their just log₂ (a bare prime, or a comma/target
    # ratio); primes carry a map, commas and targets carry interval lists
    group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                  "interest": "interest", "held": "held"}
    group_left = {"gens": gen_left, "primes": prime_left, "commas": comma_left, "targets": target_left,
                  "interest": interest_left, "held": held_left}
    group_ratio = {  # the just interval ratio each value group is taken over
        "primes": lambda i: _ratio_str(elements[i]),  # a prime "p/1", or a nonprime element "n/d"
        "commas": lambda i: comma_ratios[i],
        "targets": lambda i: targets[i],
        "interest": lambda i: interest_ratios[i],
        "held": lambda i: held_ratios[i],
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
            recip = 1 / Fraction(comma_ratios[i])
            return _log_operand(f"{recip.numerator}/{recip.denominator}")
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
        # the tuning-family unit is cents per the column's coordinate: over the generators
        # it's ¢/gᵢ, over the primes ¢/pᵢ, over the (dimensionless) interval columns plain ¢
        for i, v in enumerate(vals):
            cid = f"{key}:{group_elem[group]}:{i}"
            x = group_left[group](i)
            u = cell_unit(key, group, gen=i if group == "gens" else None, prime=i if group == "primes" else None)
            operand = closed_form_operand(key, group, i) if show_math else None
            if operand is not None:
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, show_quantities), unit=u))
            else:
                cells.append(CellBox(cid, x, y, COL_W, ROW_H, "tval", text=service.cents(v), unit=u))

    # a charted tile draws a bar chart in the band reserved above its values; the
    # chart spans the column group so its bars align with the value cells below.
    # chart_top[key] exists only where a chart band was reserved (charts on, row
    # charted, not folded), so it gates emission against the layout with no drift.
    def chart(rkey, ckey, vals, indicator=None):
        if rkey in chart_top and tile_open(rkey, ckey):
            cells.append(CellBox(f"chart:{rkey}:{ckey}", col_x[ckey], chart_top[rkey],
                                 col_w[ckey], CHART_H, "chart", values=tuple(vals), indicator=indicator))

    tuning_data = {
        "tuning": (tun.tuning_map, comma_sizes.tempered, target_sizes.tempered, interest_sizes.tempered, held_sizes.tempered),
        "just": (tun.just_map, comma_sizes.just, target_sizes.just, interest_sizes.just, held_sizes.just),
        "retune": (tun.retuning_map, comma_sizes.errors, target_sizes.errors, interest_sizes.errors, held_sizes.errors),
    }
    for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
        if row_open(key):
            tval_row(key, "primes", prime_vals)
            tval_row(key, "commas", comma_vals)
            tval_row(key, "targets", target_vals)
            tval_row(key, "interest", interest_vals)
            tval_row(key, "held", held_vals)
            chart(key, "primes", prime_vals)
            chart(key, "targets", target_vals)
    # the generator tuning map: the tuning row's map over the generators (the gens-column
    # counterpart of the tuning map over the primes), so the generators get a tuning tile too
    if row_open("tuning"):
        tval_row("tuning", "gens", tun.generator_map)

    # the audio rows: a speaker button per pitch, sounding the just (just_audio) or
    # tempered (mapped_audio) cents of each interval — the same data the just / tuning
    # rows display, so the ear and the eye agree. mapped_audio also sounds the generators
    # (their tuned size, as the tuning row's genmap does); a generator has no just size.
    def audio_tile(key, group, vals):
        if not tile_open(key, group):
            return
        vals = tuple(vals)
        # one speaker per pitch, aligned under the value columns. Each carries the WHOLE
        # tile's cents list (not just its own) so the play-mode can arp/chord the tile, and
        # text = the tile key it shares with the bank controls (so the engine can pair them).
        for i in range(len(vals)):
            cells.append(CellBox(f"speaker:{key}:{group_elem[group]}:{i}", group_left[group](i),
                                 row_y[key], COL_W, ROW_H, "speaker", text=f"{key}:{group}", values=vals))
        # the per-tile control bank in the head strip's top-right (mirroring the fold toggle
        # top-left): waveform / play-mode / hold-loop / include-1/1, each a TOGGLE square.
        # Anchored to the grey panel's right edge (tile_box), not the centred content — so a
        # caption-widened tile keeps the bank on its edge rather than drifting it inward.
        cx, cw = tile_box(group)
        right = cx + cw + tile_pad(group) - TOGGLE_INSET
        by, step = tile_top[key] - PAD + TOGGLE_INSET, TOGGLE + TOGGLE_INSET
        left0 = right - (4 * TOGGLE + 3 * TOGGLE_INSET)
        for j, ctrl in enumerate(("wave", "mode", "hold", "root")):
            cells.append(CellBox(f"{ctrl}:{key}:{group}", left0 + j * step, by, TOGGLE, TOGGLE, f"audio_{ctrl}"))

    # Source the pitches from tuning_data so the audio rows stay in lockstep with the just /
    # tuning rows they sound (one source of truth for "what those rows contain").
    list_groups = ("primes", "commas", "targets", "interest")  # tuning_data's tuple order
    if row_open("just_audio"):
        for group, vals in zip(list_groups, tuning_data["just"]):
            audio_tile("just_audio", group, vals)
    if row_open("mapped_audio"):
        audio_tile("mapped_audio", "gens", tun.generator_map)  # the genmap, as the tuning row carries
        for group, vals in zip(list_groups, tuning_data["tuning"]):
            audio_tile("mapped_audio", group, vals)
    # the prescaling row applies the prescaler L to each column group's vectors: over the
    # primes it is the d×d diagonal (L·eₚ — the prescaler matrix itself), over the comma /
    # target / interest sets it is L·vector (each component scaled by the diagonal), a d-tall
    # matrix per group like the interval-vectors row. Rendered as int/frac gridded cells.
    prescale_vectors = {
        "primes": tuple(tuple(1 if i == p else 0 for i in range(d)) for p in range(d)),
        "commas": state.comma_basis,
        "targets": target_vectors,
        "interest": interest,
    }
    for group in ("primes", "commas", "targets", "interest"):
        if not tile_open("prescaling", group):
            continue
        left = group_left[group]
        u = cell_unit("prescaling", group)
        for c, vec in enumerate(prescale_vectors[group]):
            for i in range(d):
                cells.append(CellBox(f"cell:prescaling:{group}:{i}:{c}", left(c), row_y["prescaling"] + i * ROW_H,
                                     COL_W, ROW_H, "tval", text=_prescale_text(prescaler[i] * vec[i]), unit=u))
    if presc_ctrl:  # the alt.-complexity prescaler chooser, nested at the bottom of box 𝐋
        py = tile_top["prescaling"] + tile_h["prescaling"] - presc_extra + RANGE_GAP
        cells.append(CellBox("control:prescaler", col_x["primes"], py, col_w["primes"], PRESELECT_H,
                             "control_select", text=service.prescaler_of(tuning_scheme),
                             values=tuple(service.PRESCALERS)))
    if norm_ctrl:  # the alt.-complexity complexity-norm chooser, nested at the bottom of box 𝒄
        py = tile_top["complexity"] + tile_h["complexity"] - norm_extra + RANGE_GAP
        cells.append(CellBox("control:norm", col_x["targets"], py, col_w["targets"], PRESELECT_H,
                             "control_select", text="Euclidean" if service.is_euclidean(tuning_scheme) else "taxicab",
                             values=("taxicab", "Euclidean")))
    if row_open("complexity"):  # 𝒄 over every interval set: a map over primes, lists elsewhere
        for group in ("primes", "commas", "targets", "interest", "held"):
            tval_row("complexity", group, complexities[group])
    if row_open("weight"):  # weight is over the targets only, like damage (it scales them)
        tval_row("weight", "targets", target_weights)
        chart("weight", "targets", target_weights)
    if row_open("damage"):  # damage is over the targets only (the tuning's own column)
        tval_row("damage", "targets", target_sizes.damage)
        # optimization adds the horizontal minimized-damage indicator (the objective ⟨d⟩ₚ
        # the tuning minimizes) across the damage chart; off, the chart is plain bars
        objective = _lp_objective(target_sizes.damage, service.optimization_power(tuning_scheme))
        chart("damage", "targets", target_sizes.damage, indicator=objective if show_optimization else None)

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

    # the optimization box, nested at the BOTTOM of the target-interval damage list tile (the
    # tuning's own column, whose damages it minimizes): a bordered box titled "optimization"
    # holding the minimized-damage objective ⟨𝐝⟩ₚ and the editable power 𝑝 stacked on the left,
    # with the optimize button spanning them on the right. The damage tile's panel grows by
    # opt_extra (above) to enclose it; the box's own border is the opt_box block (panel loop).
    opt_box = None  # (x, y, w, h) of the bordered frame around the optimization controls
    if opt_ctrl:
        ox, ow = col_x["targets"], col_w["targets"]
        box_top = tile_top["damage"] + tile_h["damage"] - opt_extra + RANGE_GAP
        half, content_top = ow / 2, box_top + OPT_TITLE_H
        objective = _lp_objective(target_sizes.damage, service.optimization_power(tuning_scheme))
        power = _format_power(service.optimization_power(tuning_scheme))
        cells.append(CellBox("optimization:title", ox, box_top, ow, OPT_TITLE_H, "boxtitle",
                             text="optimization"))
        cells.append(CellBox("optimization:objective", ox, content_top, half, ROW_H, "optimization",
                             text=f"⟨𝐝⟩ₚ = {service.cents(objective)}"))
        # the power is an editable field (∞ minimax, 2 miniRMS, 1 miniaverage); app.py renders
        # the input with a 𝑝 label and routes edits to editor.set_optimization_power
        cells.append(CellBox("optimization:power", ox, content_top + ROW_H, half, ROW_H, "powerinput",
                             text=power))
        # the button single-clicks to optimize once, double-clicks to lock auto-optimize;
        # app.py owns that behaviour and the lock visual, reading the editor
        cells.append(CellBox("optimization:button", ox + half, content_top, half, 2 * ROW_H, "optimize",
                             text="optimize"))
        opt_box = (ox, box_top, ow, OPT_TITLE_H + 2 * ROW_H)

    # EBK brackets in the value groups' gutters: prime-side rows are maps (⟨…]),
    # target-side rows are lists ([ … ]). Maps stack one per generator row.
    def bracket(bid, glyphs, group_key, y, h, *, fit=False):
        # value brackets are short and centred in their row (so stacked rows keep a
        # gap); the enclosing mapped-list [ ] passes fit=True to span the matrix.
        gx, gw = content_box(group_key)  # hug the cells (interest's content, not its footprint)
        by, bh = (y, h) if fit else (y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H)
        cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0]))
        cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1]))

    if row_open("canon") and tile_open("canon", "primes"):  # canonical maps: ⟨ … ] per row
        for i in range(rc):
            bracket(f"canon:map:{i}", MAP_BRACKETS, "primes", canon_top(i), ROW_H)
    if row_open("canon") and tile_open("canon", "gens"):  # the generator form matrix: { … ] per row
        for i in range(len(form_M)):
            bracket(f"form:map:{i}", GENMAP_BRACKETS, "gens", canon_top(i), ROW_H)
    if row_open("mapping"):
        # the primes mapping is a stack of maps: ⟨ … ] per row
        if tile_open("mapping", "primes"):
            for i in range(r):
                bracket(f"map:{i}", MAP_BRACKETS, "primes", map_top(i), ROW_H)
        if tile_open("mapping", "commas"):  # the mapped (vanishing) comma basis: a [ ] over r rows
            bracket("mapped_comma", LIST_BRACKETS, "commas", row_y["mapping"], r * ROW_H, fit=True)
        if tile_open("mapping", "targets"):
            bracket("mapped", LIST_BRACKETS, "targets", row_y["mapping"], r * ROW_H, fit=True)
        if mi and tile_open("mapping", "interest"):  # interest mapped list, like the targets
            bracket("imapped", LIST_BRACKETS, "interest", row_y["mapping"], r * ROW_H, fit=True)
        if nh and tile_open("mapping", "held"):  # held mapped list, like the targets / interest
            bracket("hmapped", LIST_BRACKETS, "held", row_y["mapping"], r * ROW_H, fit=True)
    if row_open("vectors"):  # each group is a list of monzos: a [ ] spanning the d components
        for group in ("commas", "targets"):
            if tile_open("vectors", group):
                bracket(f"vec:{group}", LIST_BRACKETS, group, row_y["vectors"], d * ROW_H, fit=True)
        if mi and tile_open("vectors", "interest"):
            bracket("vec:interest", LIST_BRACKETS, "interest", row_y["vectors"], d * ROW_H, fit=True)
        if nh and tile_open("vectors", "held"):
            bracket("vec:held", LIST_BRACKETS, "held", row_y["vectors"], d * ROW_H, fit=True)
        if tile_open("vectors", "detempering"):
            bracket("vec:detempering", LIST_BRACKETS, "detempering", row_y["vectors"], d * ROW_H, fit=True)
    if tile_open("tuning", "gens"):  # the generator tuning map is framed { … ] (per the mockup)
        bracket("tuning:genmap", GENMAP_BRACKETS, "gens", row_y["tuning"], ROW_H)
    for key in ("tuning", "just", "retune", "complexity"):
        if row_open(key):
            if tile_open(key, "primes"):
                bracket(f"{key}:map", MAP_BRACKETS, "primes", row_y[key], ROW_H)
            if tile_open(key, "commas"):
                bracket(f"{key}:commalist", LIST_BRACKETS, "commas", row_y[key], ROW_H)
            if tile_open(key, "targets"):
                bracket(f"{key}:list", LIST_BRACKETS, "targets", row_y[key], ROW_H)
            if mi and tile_open(key, "interest"):
                bracket(f"{key}:ilist", LIST_BRACKETS, "interest", row_y[key], ROW_H)
            if nh and tile_open(key, "held"):
                bracket(f"{key}:hlist", LIST_BRACKETS, "held", row_y[key], ROW_H)
    if tile_open("weight", "targets"):
        bracket("weight", LIST_BRACKETS, "targets", row_y["weight"], ROW_H)
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
        bx, bw = _bus_span(xs)
        lines.append(Line(f"bus:{key}:top", "h", fanout_y, bx, bw))
        lines.append(Line(f"bus:{key}:bot", "h", bot_bus_y, bx, bw))
        lines.append(Line(f"trunk:{key}", "v", cx, branch_top_y, fanout_y - branch_top_y))
        lines.append(Line(f"foot:{key}", "v", cx, bot_bus_y, total_h - bot_bus_y))

    FAN_COLUMNS = ("primes", "commas", "targets", "interest")  # the data columns that fan
    column_axis("primes", "prime", d, lambda p: prime_left(p) + COL_W / 2)
    column_axis("commas", "comma", nc_shown, lambda c: comma_left(c) + COL_W / 2)
    column_axis("targets", "target", k, lambda j: target_left(j) + COL_W / 2)
    column_axis("interest", "interest", mi, lambda i: interest_left(i) + COL_W / 2)
    column_axis("held", "held", nh, lambda i: held_left(i) + COL_W / 2)
    column_axis("detempering", "detempering", r, lambda i: detempering_left(i) + COL_W / 2)

    # every other present column is a spine: a single full-height trunk rule. Derived from
    # col_x (not a hand-kept list) so a column can never lack its gridline — the quantities
    # and units spines (carrying the row labels / coordinate units, no value fan) and the
    # generators column (it indexes the mapping rows and backs the rank count + ranges chart).
    # The fanned data columns above already emitted their own trunk inside column_axis.
    for key in col_x:
        if key in FAN_COLUMNS:
            continue
        cx = col_x[key] + col_w[key] / 2
        lines.append(Line(f"trunk:{key}", "v", cx, branch_top_y, total_h - branch_top_y))

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
        bus_y, bus_h = _bus_span(ys)
        lines.append(Line("vbar:mapping:left", "v", left_bus_x, bus_y, bus_h))
        lines.append(Line("vbar:mapping:right", "v", right_bus_x, bus_y, bus_h))
        lines.append(Line("trunk:mapping", "h", cy, node_edge, left_bus_x - node_edge))
        lines.append(Line("foot:mapping", "h", cy, right_bus_x, total_w - right_bus_x))

    # every present row except the mapping (which fans into per-generator rules above) gets
    # ONE horizontal rule across its band. Derived from row_y (not a hand-kept list) so a row
    # can never lack its gridline — present or collapsed (a folded row still leaves its rule).
    # Covers the quantities/units spine rows and the d-tall vectors/prescaling matrices alike.
    for key in row_y:
        if key == "mapping":
            continue
        lines.append(Line(f"h:{key}", "h", row_y[key] + row_h[key] / 2, node_edge, total_w - node_edge))

    # #e0e0e0 panels behind each content group. A panel folds to zero size along
    # any collapsed axis (collapsing toward the band centre), so the renderer
    # animates it shrinking away to nothing — leaving only the band's gridline,
    # never a leftover grey strip. Every tile is simply its row band's full height
    # (the d-tall monzo matrices live in the d-tall interval-vectors row).
    def tile_height(rkey, ckey):
        # the grey panel's height: the row's tile_h, minus any nested-control reservation that
        # belongs to a DIFFERENT tile. tile_h reserves that control's height across the whole row
        # (so the rows below clear it), but only its owning tile encloses it — siblings hug their
        # own content height, so one tile's chart/chooser never stretches the rest of the row.
        owner_col, extra = tile_extra.get(rkey, (None, 0))
        return tile_h[rkey] if ckey == owner_col else tile_h[rkey] - extra

    def panel_rect(ckey, rkey):
        # a folded tile collapses both ways at once, so it shrinks to a point at its
        # centre — like a row+column collapse confined to this one tile.
        tile_c = f"tile:{rkey}:{ckey}" in collapsed
        col_c = f"col:{ckey}" in collapsed or tile_c
        row_c = f"row:{rkey}" in collapsed or tile_c
        cx, cw = tile_box(ckey)  # the tile widens for a long caption; content centres within it
        ch, cy = tile_height(rkey, ckey), tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, tile_pad(ckey))
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
    # the optimization box's thin border, around its title + objective/power/button
    if opt_box is not None:
        blocks.append(Block("block:optimization:box", *opt_box, boxed=True))

    # Colorization washes. Each colour-bearing tile (CELL_FACTORS) renders one band per
    # group — a white base plus the group's colour at mix-blend-mode:darken (see app.py).
    # The base sits a layer BELOW the colour (z-index), so where a tile carries both groups
    # the two colour bands darken-compose regardless of paint order: cyan over yellow gives
    # the mockup's green. Each band hugs its (open) tile's extent and overhangs by WASH_PAD
    # — plus, on a +-bearing column, the extra FRAME_GAP its tile claims (tile_pad over PAD)
    # — so a run of same-coloured tiles meets across the inter-tile gaps and reads as one
    # continuous band rather than leaving grey strips between them. A folded tile (by its own
    # toggle, its row or its column) is not open, so its colour goes away with its content.
    if col_x and row_y:
        bands = []  # (id, x, y, w, h, group)
        for (rkey, ckey), factors in CELL_FACTORS.items():
            if not tile_open(rkey, ckey):
                continue
            pad = tile_pad(ckey) - PAD
            x, w = col_x[ckey] - WASH_PAD - pad, col_w[ckey] + 2 * (WASH_PAD + pad)
            y, h = tile_top[rkey] - WASH_PAD, tile_height(rkey, ckey) + 2 * WASH_PAD
            for group in {_FACTOR_GROUP[f] for f in factors}:
                if settings.get(f"{group}_colorization"):
                    bands.append((f"{group}:{rkey}:{ckey}", x, y, w, h, group))
        for bid, x, y, w, h, _ in bands:  # white bases (a layer below the colour bands)
            blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
        for bid, x, y, w, h, group in bands:  # the darken colour bands over them
            blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))

    # quantity symbol + name stacked inside each tile, below its values + bottom
    # frame: the symbol line (toggled by symbols) on top, the long-form name
    # (toggled by names) under it. Equivalences extends the symbol line with the
    # quantity's defining equation — the "= …" continuation appended to the glyph,
    # so it reads e.g. "𝒕 = 𝒈𝑀"; turning it on shows the glyph too (the equation's
    # left side) even when symbols itself is off. Within a symboled row the slot is
    # reserved for every captioned column so the names stay aligned; the glyph and
    # equation are drawn only where defined (the comma columns have none yet). An
    # empty interest column has no tiles. Mnemonics underlines the symbol letter.
    # The weight row's equivalence is the one scheme-dependent equation (𝒘 = 𝒄 / 1 / 1/𝒄),
    # so it is resolved per build from the live scheme's slope rather than baked in.
    equivalences = {**EQUIVALENCES,
                    ("weight", "targets"): WEIGHT_EQUIVALENCE_BY_SLOPE[service.damage_weight_slope(tuning_scheme)]}
    for (rkey, ckey), name in CAPTIONS.items():
        if ckey == "interest" and not interest:
            continue
        if not tile_open(rkey, ckey):
            continue
        cy = row_y[rkey] + row_h[rkey] + row_frame[rkey]
        if (show_symbols or show_equiv) and rkey in SYMBOLED_ROWS:
            equiv = equivalences.get((rkey, ckey), "") if show_equiv else ""
            glyph = SYMBOLS.get((rkey, ckey), "") if (show_symbols or equiv) else ""
            if glyph or equiv:
                cells.append(CellBox(f"symbol:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
            cy += SYMBOL_H
        if show_captions:
            kw = MNEMONICS.get((rkey, ckey)) if show_mnemonics else None
            underlines = ((name.index(kw), 1),) if kw else ()
            # the caption spans the row's whole caption band (row_cap — the tallest wrapped
            # name in the row), and the CSS centres the text within it. So a one-line name
            # sits centred (half a blank line above and below) against a two-line sibling,
            # rather than hugging the cells with all the slack below.
            cells.append(CellBox(f"caption:{rkey}:{ckey}", col_x[ckey], cy, col_w[ckey], row_cap[rkey],
                                 "caption", text=name, underlines=underlines))
        # the "units: …" line sits below the caption band (independent of names/symbols),
        # reading the box's entry from UNITS — bold-upright unit glyphs via _math_html
        if show_units and (rkey, ckey) in UNITS:
            uy = row_y[rkey] + row_h[rkey] + row_frame[rkey] + row_sym[rkey] + row_cap[rkey]
            cells.append(CellBox(f"units:{rkey}:{ckey}", col_x[ckey], uy, col_w[ckey], UNIT_H,
                                 "units", text=f"units: {UNITS[(rkey, ckey)]}"))

    # the plain-text box sits directly below the symbol/caption/units stack; the preselect
    # chooser rides one plain-text band lower (so preselects appear under plain text).
    def ptext_band_y(rkey):
        return row_y[rkey] + row_h[rkey] + row_frame[rkey] + row_sym[rkey] + row_cap[rkey] + row_units[rkey]

    # preselect chooser dropdowns, in the reserved band below each governing tile's
    # plain-text box. The tuning/target choosers carry the live selection; the
    # temperament chooser is a placeholder (it loads, not mirrors). These are controls,
    # so they ride the tile whether or not math expressions has emptied its values.
    if show_preselects:
        # the tuning chooser shows the scheme name; a scheme refined by the alt.-complexity
        # control is a resolved spec (no preset name), so it shows blank rather than a repr
        preselect_text = {"temperament": "", "target": target_spec,
                          "tuning": tuning_scheme if isinstance(tuning_scheme, str) else ""}
        for name, rkey, ckey in PRESELECTS:
            if not tile_open(rkey, ckey):
                continue
            py = ptext_band_y(rkey) + row_ptext[rkey]  # below the plain-text band
            pw = min(col_w[ckey], TARGET_PRESELECT_W if name == "target" else PRESELECT_W)
            cells.append(CellBox(f"preselect:{name}", col_x[ckey], py, pw, PRESELECT_H, "preselect", text=preselect_text[name]))

    # the <choose form> chooser, one band below the preselect chooser: it canonicalizes
    # the mapping / comma basis it rides (an undoable edit). A control, so it ignores the
    # value-display toggles, like the preselect choosers.
    if show_form_controls:
        for name, rkey, ckey in FORM_CHOOSERS:
            if not tile_open(rkey, ckey):
                continue
            fy = ptext_band_y(rkey) + row_ptext[rkey] + row_pre[rkey]  # below the preselect band
            cells.append(CellBox(f"formchooser:{name}", col_x[ckey],
                                 fy, min(col_w[ckey], PRESELECT_W), PRESELECT_H, "formchooser"))

    # plain-text value band: each tile's value as its natural EBK string, directly
    # below the symbol/caption stack (above the preselect chooser). The two editable
    # duals (mapping, comma basis) render as inputs that drive the grid; every other
    # value is read-only. The app shrinks each box's font so the value fits one line.
    if show_ptext:
        for (rkey, ckey), text in ptext_strings.items():
            if not tile_open(rkey, ckey):
                continue
            # the comma basis flips to a static two-tone box while a comma is pending (the
            # committed commas black, the draft vector red — a single-colour input can't do
            # that); the mapping and read-only values keep their normal kinds.
            if pending is not None and (rkey, ckey) == ("vectors", "commas"):
                kind = "ptextpending"
            elif (rkey, ckey) in EDITABLE_PTEXT:
                kind = "ptextedit"
            else:
                kind = "ptext"
            cells.append(CellBox(f"ptext:{rkey}:{ckey}", col_x[ckey], ptext_band_y(rkey),
                                 col_w[ckey], ptext_height(rkey, ckey), kind, text=text))
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

    # a matrix tile (the primes mapping, the canonical mapping, the complexity prescaler)
    # is enclosed by a top bracket + bottom brace spanning its whole column. ``bid`` keeps
    # each frame's ids stable so two framed rows over the same column never collide.
    def matrix_frame(rkey, ckey, bid):
        if not tile_open(rkey, ckey):
            return
        gx, gw = col_x[ckey], col_w[ckey]
        cells.append(CellBox(f"ebktop:{bid}", gx, frame_top_y(rkey), gw, FRAME_H, "ebktop"))
        cells.append(CellBox(f"ebkbrace:{bid}", gx, frame_brace_y(rkey), gw, BRACE_H, "ebkbrace"))

    matrix_frame("mapping", "primes", "primes")
    matrix_frame("canon", "primes", "canon")
    matrix_frame("canon", "gens", "form")
    matrix_frame("prescaling", "primes", "prescaling")
    matrix_frame("prescaling", "commas", "prescaling:commas")
    matrix_frame("prescaling", "targets", "prescaling:targets")
    matrix_frame("prescaling", "interest", "prescaling:interest")

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
    monzo_list_marks("mapping", "hmapped", "held", held_left, nh)
    # the interval-vectors row holds raw (untempered) monzos, so every column is a
    # ket — angle ⟩ feet, not braces. The comma basis is the editable bordered grid
    # (commacell), so it skips the separator rules (its cell borders divide the columns);
    # nc_shown includes the pending draft column so it gets its ket marks too.
    monzo_list_marks("vectors", "vec:commas", "commas", comma_left, nc_shown, foot="ebkangle", bordered=True,
                     pending_col=(nc if pending is not None else -1))
    monzo_list_marks("vectors", "vec:targets", "targets", target_left, k, foot="ebkangle")
    monzo_list_marks("vectors", "vec:interest", "interest", interest_left, mi, foot="ebkangle")
    monzo_list_marks("vectors", "vec:held", "held", held_left, nh, foot="ebkangle")
    monzo_list_marks("vectors", "vec:detempering", "detempering", detempering_left, r, foot="ebkangle")

    # a per-tile fold toggle inset into each content tile's top-left corner: it
    # sits in the head strip reserved above the content, TOGGLE_INSET in from the
    # grey panel's top-left, so it never touches an edge or overlaps the frame.
    # Anchored to the grey panel's left edge (col_x), not the centred content — so a
    # caption-widened tile keeps the toggle on its edge rather than drifting it inward.
    # Present whenever the tile's row and column bands are open — it stays put when
    # only the tile is folded, so the tile can be re-expanded.
    for _bid, rkey, ckey in tiles:
        if rkey in row_y and ckey in col_x and row_open(rkey) and col_open(ckey):
            glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in collapsed)
            cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                 col_x[ckey] - tile_pad(ckey) + TOGGLE_INSET, tile_top[rkey] - PAD + TOGGLE_INSET,
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
