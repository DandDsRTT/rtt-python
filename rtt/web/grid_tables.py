"""Semantic content tables for the temperament grid (extracted from spreadsheet.py).

Pure data -- *which* quantities exist and their symbols, captions, units, mnemonics,
colorization factors and tile sets -- with no layout logic and no imports. spreadsheet.py
re-exports everything here (`from rtt.web.grid_tables import *`) so `spreadsheet.<NAME>`
stays the public surface app.py, tooltips and the tests read.
"""

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
# COUNTS: the held interval count h. Kept separate because these columns are
# conditional (present only with the optimization box), so build() folds them into the
# counts machinery only when shown rather than always, as COUNTS is.
OPTIMIZATION_COUNTS = (
    ("held", "h", "held interval count"),
)
# Their backing tiles, like COUNTS_TILES. Declared unconditionally — each is inert
# (no panel, toggle or cell) until its column exists, since tile_open gates on the
# column being present (which only happens while the optimization box is shown).
OPTIMIZATION_COUNTS_TILES = tuple(
    (f"block:counts:{ckey}", "counts", ckey) for ckey, *_ in OPTIMIZATION_COUNTS
)
# The generator-detempering column carries a count too: the matrix holds one detempering
# interval per generator, so its count IS the rank r — same value AND same name ("rank") as
# the generators column's count. Like OPTIMIZATION_COUNTS, it is gated on its column being
# shown (the generator_detempering box), so it lives in its own conditional tuple.
DETEMPERING_COUNTS = (
    ("detempering", "r", "rank"),  # the count IS the rank r — same name as the generators count
)
DETEMPERING_COUNTS_TILES = tuple(
    (f"block:counts:{ckey}", "counts", ckey) for ckey, *_ in DETEMPERING_COUNTS
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
    ("vectors", "held"): "held interval basis",
    ("vectors", "detempering"): "generator detempering",
    ("mapping", "primes"): "(temperament) mapping",
    ("mapping", "commas"): "mapped comma basis (made to vanish!)",
    ("mapping", "targets"): "mapped target interval list",
    ("tuning", "gens"): "generator tuning map",
    ("tuning", "primes"): "tuning map",
    ("tuning", "commas"): "tempered comma basis interval size list (made to vanish!)",
    ("tuning", "detempering"): "tempered generator detempering tuning map",
    ("tuning", "targets"): "tempered target interval size list",
    ("just", "primes"): "just tuning map",
    ("just", "commas"): "(just) comma basis interval size list",
    ("just", "detempering"): "(just) generator detempering interval size list",
    ("just", "targets"): "(just) target interval size list",
    ("retune", "primes"): "retuning map",
    ("retune", "commas"): "comma basis interval retuning list (made to vanish!)",
    ("retune", "detempering"): "generator detempering interval retuning list",
    ("retune", "targets"): "target interval error list",
    ("prescaling", "primes"): "complexity prescaler",
    ("prescaling", "commas"): "complexity prescaled comma basis",
    ("prescaling", "detempering"): "complexity prescaled generator detempering",
    ("prescaling", "targets"): "complexity prescaled target interval list",
    ("complexity", "primes"): "domain prime complexity map",
    ("complexity", "commas"): "comma basis interval complexity list",
    ("complexity", "detempering"): "generator detempering complexity list",
    ("complexity", "targets"): "target interval complexity list",
    ("weight", "targets"): "target interval weight list",
    ("damage", "targets"): "target interval damage list",
    **{("counts", ckey): name for ckey, _sym, name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS},
    # Other intervals of interest carry the mockup's own descriptive names — distinct from
    # the targets column's "...target interval... list" phrasing. This column is narrow (a
    # few user-curated intervals), so a wrapped caption would grow/shrink the caption band —
    # and the whole board — as intervals are added. To avoid that, the interest captions
    # OVERHANG a single line (like the column title): centred and overflowing the column,
    # and counted as one line by caption_band so the band height stays constant.
    ("vectors", "interest"): "intervals of interest",
    ("mapping", "interest"): "mapped intervals",
    ("tuning", "interest"): "tempered interval sizes",
    ("just", "interest"): "(just) interval sizes",
    ("retune", "interest"): "interval retunings",
    ("prescaling", "interest"): "complexity prescaled intervals",
    ("complexity", "interest"): "interval complexities",
    # the held column is the optimization's held-just constraint set: like the comma basis
    # (special intervals the temperament treats specially), it carries full descriptive names
    # mirroring the comma column ("held interval basis" in place of "comma basis"), but without
    # the comma column's "(made to vanish!)" — held intervals are held just, not vanished
    ("mapping", "held"): "mapped held interval basis",
    ("tuning", "held"): "tempered held interval basis interval size list",
    ("just", "held"): "(just) held interval basis interval size list",
    ("retune", "held"): "held interval basis interval retuning list",
    ("prescaling", "held"): "complexity prescaled held interval basis",
    ("complexity", "held"): "held interval basis interval complexity list",
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
    ("vectors", "detempering"): "D",  # the generator detempering matrix (upright, like C/T)
    ("mapping", "primes"): "𝑀",
    ("mapping", "commas"): "𝑀C",
    ("mapping", "targets"): "Y",
    ("tuning", "gens"): "𝒈",
    ("tuning", "primes"): "𝒕",
    ("tuning", "commas"): "𝒕C",
    ("tuning", "detempering"): "𝒕D",
    ("tuning", "targets"): "𝐚",
    ("just", "primes"): "𝒋",
    ("just", "commas"): "𝒋C",
    ("just", "detempering"): "𝒋D",
    ("just", "targets"): "𝐨",
    ("retune", "primes"): "𝒓",
    ("retune", "commas"): "𝒓C",
    ("retune", "detempering"): "𝒓D",
    ("retune", "targets"): "𝐞",
    # the bare prescaler matrix keeps the abstract symbol 𝑋 (math italic, like 𝑀); its " = …"
    # equivalence is set scheme-aware at build time ("𝑋 = 𝐿" / "𝑋 = diag(𝒑)" / "𝑋 = 𝐼" — see
    # prescaler_equivalence). The product tiles carry an upright-``L`` placeholder that build()
    # resolves to the LIVE glyph (see prescaling_symbols): 𝐿C/𝐿D/… when 𝑋 = 𝐿 (the log-prime
    # matrix), else generic 𝑋C/𝑋D/… — so a product tile and its column headers never mix 𝐿 and 𝑋.
    ("prescaling", "primes"): "𝑋",   # the complexity prescaler matrix (math italic, like 𝑀)
    ("prescaling", "commas"): "LC",   # the product over the comma basis C
    ("prescaling", "detempering"): "LD",   # over the generator detempering D
    ("prescaling", "targets"): "LT",   # over the target interval list T
    ("prescaling", "held"): "LH",   # over the held interval basis H
    # the held interval column mirrors the comma column: the basis H lives in the
    # interval-vectors row, and everything else is a product with it — the mapped held
    # basis 𝑀H and the held sizes 𝒕H, 𝒋H, 𝒓H (the held complexity is a derived auxiliary,
    # so like the comma complexity it carries none)
    ("vectors", "held"): "H",
    ("mapping", "held"): "𝑀H",
    ("tuning", "held"): "𝒕H",
    ("just", "held"): "𝒋H",
    ("retune", "held"): "𝒓H",
    # only the target interval complexity list carries the bare 𝒄 symbol; the domain-prime
    # map, comma list and interest complexity are derived auxiliaries and carry none
    ("complexity", "targets"): "𝒄",
    ("weight", "targets"): "𝒘",  # bold italic, as in the damage row's 𝒘 factor
    ("damage", "targets"): "𝐝",
}
SYMBOLED_ROWS = frozenset(row for row, _ in SYMBOLS)  # rows that reserve a symbol slot
# Matrix labels emitted when symbols is on, alongside the tile's existing big-symbol
# glyph. Each label has a fixed glyph (the matrix's row/column letter) appended with a
# Unicode subscript index:
#   - a covector stack (rows are the meaningful objects) labels its ROWS at the left
#     of each row's ⟨ bracket — 𝒎ᵢ on the mapping 𝑀, 𝒙ᵢ on the prescaler 𝑋.
#   - every other multi-cell tile labels its COLUMNS above each cell — 𝐜ᵢ on the
#     comma basis C, 𝒕ᵢ on the tuning map 𝒕, 𝑀𝐜ᵢ on the mapped comma basis 𝑀C, etc.
# The pattern follows the existing SYMBOLS convention — compound symbols keep the
# prefix and lowercase only the trailing vector capital (𝒕C → 𝒕𝐜, 𝑀H → 𝑀𝐡); renamed
# list symbols (Y, 𝐚, 𝐨, 𝐞, 𝐝) pass through with the subscript appended directly. The
# five target SIZE lists hold scalar cells per column, so their column labels use the
# NON-BOLD italic form (𝐚 → 𝑎, 𝐨 → 𝑜, 𝐞 → 𝑒, 𝒘 → 𝑤, 𝐝 → 𝑑) — the bold form names the
# list itself, the italic form its scalar entries.
ROW_LABEL_LETTERS = {
    ("mapping", "primes"): "𝒎",      # 𝑀 → 𝒎: each row of the mapping is a covector 𝒎ᵢ
    # each row of the bare prescaler matrix is a covector, labelled with the lowercase of the
    # glyph it realises — build() swaps in 𝒍ᵢ when 𝑋 = 𝐿 (the log-prime matrix), else the generic
    # 𝒙ᵢ (see row_labels). The static value is that generic fallback.
    ("prescaling", "primes"): "𝒙",
}
ROW_LABELED_TILES = frozenset(ROW_LABEL_LETTERS)
COL_LABEL_LETTERS = {
    # interval vectors row — d-tall column-vector matrices
    ("vectors", "commas"): "𝐜",
    ("vectors", "targets"): "𝐭",
    ("vectors", "held"): "𝐡",
    ("vectors", "detempering"): "𝐝",
    # mapping row — mapped lists; the mapped target list Y has its own 𝐲 letter
    ("mapping", "commas"): "𝑀𝐜",
    ("mapping", "targets"): "𝐲",
    ("mapping", "held"): "𝑀𝐡",
    # tuning row — single covector applied to each column set; the tempered target
    # list 𝐚 is bold-upright as a list, but each cell is a SCALAR so its index reads
    # as plain "a" (neither bold nor italic) — same for the other scalar lists below
    ("tuning", "gens"): "𝒈",
    ("tuning", "primes"): "𝒕",
    ("tuning", "commas"): "𝒕𝐜",
    ("tuning", "targets"): "a",       # tempered target SIZES (scalars) — plain
    ("tuning", "held"): "𝒕𝐡",
    ("tuning", "detempering"): "𝒕𝐝",
    # just row
    ("just", "primes"): "𝒋",
    ("just", "commas"): "𝒋𝐜",
    ("just", "targets"): "o",         # just target SIZES — plain
    ("just", "held"): "𝒋𝐡",
    ("just", "detempering"): "𝒋𝐝",
    # retune row
    ("retune", "primes"): "𝒓",
    ("retune", "commas"): "𝒓𝐜",
    ("retune", "targets"): "e",       # retuning errors — plain
    ("retune", "held"): "𝒓𝐡",
    ("retune", "detempering"): "𝒓𝐝",
    # damage + weight — scalar lists over the targets only
    ("damage", "targets"): "d",       # damage scalars — plain
    ("weight", "targets"): "w",       # weight scalars — plain
    # the complexity row's headers (EVERY column, targets included) track the live prescaler
    # glyph and the equivalences layer, so build() fills them in per-render via
    # _prescaler_col_labels (NOT here): the auxiliary columns spell the bare norm
    # ‖prescaler·basisᵢ‖q, the named targets column the symbol cₙ with that norm as its
    # equivalence tail. So the complexity row carries no static entry — it is registered in
    # COL_LABELED_ROWS explicitly (like the prescaling row, also built per-render).
}
# multi-row matrices reserve top/bottom frame bands for their EBK marks: the mapping,
# the canonical mapping and the complexity-prescaling matrix for their spanning
# bracket+brace, the interval vectors for the per-column ket marks
FRAMED_ROWS = frozenset({"mapping", "canon", "vectors", "prescaling"})
CHARTED_ROWS = frozenset({"retune", "weight", "damage"})  # rows that grow a bar-chart band above their values when charts shown
# Value rows whose tiles carry per-column matrix labels (𝐜ᵢ, 𝒕ᵢ, 𝐲ᵢ, …) when symbols
# is on — every row with multi-cell tiles in the built layout. The counts/quantities/
# units/canon spine rows hold a single index per column already (a cardinality, a
# ratio, a unit) so they label their cells in-place, not over a separate band.
# the prescaling and complexity rows' per-column labels are built per-render (see
# _prescaler_col_labels), so they carry no static COL_LABEL_LETTERS entry — register both
# explicitly so the layout still reserves their column-label band.
COL_LABELED_ROWS = frozenset(rkey for rkey, _ in COL_LABEL_LETTERS) | {"prescaling", "complexity"}

# Content-derived colorization (the mockup's coloured washes behind the grey tiles): a
# group's "{group}_colorization" setting, when on, paints colour behind the tiles whose
# quantity is built from that group's fundamental object, showing through the gaps around
# the grey tiles. Each quantity is a product of fundamental objects; a tile is washed by
# whichever *colour-bearing* objects are multiplied into it:
#   "G" — the generator embedding / generator tuning map 𝒈 (which tunes G) → tuning (cyan)
#   "J" — the just tuning map 𝒋                                            → tuning (cyan)
#   "X" — the complexity prescaler 𝑋                                       → tuning (cyan)
#   "T" — the target interval list                                         → tuning (cyan)
#   "H" — the held interval basis                                          → tuning (cyan)
#   "P" — the domain basis (the primes)                                    → temperament (yellow)
#   "B" — the generator basis (the generators column's codomain basis)     → temperament (yellow)
#   "M" — the (temperament) mapping                                        → temperament (yellow)
#   "C" — the comma basis                                                  → temperament (yellow)
# Colourless: the other-intervals of interest AND the generator detempering list (both are
# chosen interval lists, carrying no basis colour). (The weight 𝒘 is NOT colourless — it
# incorporates the cyan complexity list; see its entry. The domain basis P and generator
# basis B are yellow, so the primes and generators columns colour like the commas column.)
# A tile carrying both a tuning and a temperament object reads green (the darken blend of
# the two washes) — e.g. the tempered map 𝒕 = 𝒈𝑀 (G·M), the mapped target list 𝑀T (M·T),
# the just-of-commas 𝒋C (J·C), and the whole
# error/damage chain 𝐞 = (𝒈𝑀 − 𝒋)T, which keeps every operand's factors
# (G, M, J, T) across the 𝒓 = 𝒕 − 𝒋 difference. A norm carries its operand's factors, so
# the complexity 𝒄 = ‖𝑋·v‖ inherits 𝑋 and the basis v's own colour. CELL_FACTORS lists
# only the colour-bearing factors of each tile; a (row, col) absent here carries no wash.
# Keys match TILES / AUDIO_TILES. NB the generator RATIOS shown in the spine (mapping ×
# quantities) are a chosen input, neither the embedding G nor the tuning map 𝒈 — so by
# CONTENT they'd be uncoloured; the spine-band rule (see SPINE_*) tints them by the mapping
# row instead. The genmap 𝒈 (tuning × generators) reads green: its cyan G over the yellow
# generator basis B. The embedding G awaits the deferred form box (𝐹).
_FACTOR_GROUP = {"G": "tuning", "J": "tuning", "X": "tuning", "T": "tuning", "H": "tuning",
                 "P": "temperament", "B": "temperament", "M": "temperament", "C": "temperament"}
CELL_FACTORS: dict[tuple[str, str], frozenset[str]] = {
    # interval-vectors / quantities headers: the domain basis is P (yellow) and the comma
    # basis is C (yellow); the target list T and the held basis H are cyan; the other-intervals
    # and the generator detempering list stay colourless (chosen interval lists, no entry)
    ("quantities", "gens"): frozenset({"B"}),          # the generator ratios = the generator basis B (yellow)
    ("quantities", "primes"): frozenset({"P"}),        # the domain prime ratios = P
    ("quantities", "commas"): frozenset({"C"}),        # the comma ratios = C
    ("vectors", "commas"): frozenset({"C"}),           # the comma basis vectors = C
    ("quantities", "targets"): frozenset({"T"}),       # the target ratios = T
    ("vectors", "targets"): frozenset({"T"}),          # the target list vectors = T
    ("quantities", "held"): frozenset({"H"}),          # the held ratios = H
    ("vectors", "held"): frozenset({"H"}),             # the held basis vectors = H
    # the mapping matrix and its mapped lists are 𝑀 (the mapped comma basis 𝑀C also has C).
    # the primes column carries the domain basis P in EVERY tile — just like the comma column
    # carries C — since every primes-column quantity is a map/list over the domain primes
    ("mapping", "primes"): frozenset({"M", "P"}),      # 𝑀 (over the domain primes P)
    ("mapping", "commas"): frozenset({"M", "C"}),      # 𝑀C
    ("mapping", "targets"): frozenset({"M", "T"}),     # 𝑀T (the mapping carries the cyan target list)
    ("mapping", "interest"): frozenset({"M"}),         # 𝑀·interest (other-intervals are colourless)
    ("mapping", "held"): frozenset({"M", "H"}),        # 𝑀H (the mapping carries the cyan held basis)
    ("canon", "primes"): frozenset({"M", "P"}),        # the canonical mapping (𝑀 = 𝐅𝑀_c): 𝑀 family over P
    # the generator tuning map 𝒈 = G; the tempered family 𝒕 = 𝒈𝑀 etc. carry G and M (green).
    # the generators column carries the generator basis B in EVERY tile — like the domain
    # primes column carries P — since every generators-column quantity is over the generators
    ("tuning", "gens"): frozenset({"G", "B"}),         # 𝒈 over the yellow generator basis B → green
    ("tuning", "primes"): frozenset({"G", "M", "P"}),  # 𝒕 = 𝒈𝑀 (over the domain primes P)
    ("tuning", "commas"): frozenset({"G", "M", "C"}),  # 𝒕C
    ("tuning", "detempering"): frozenset({"G", "M"}),  # 𝒕·D (the tempered family's 𝒈𝑀; D is neutral)
    ("tuning", "targets"): frozenset({"G", "M", "T"}),  # 𝐚 = 𝒈𝑀T (carries the cyan target list)
    ("tuning", "interest"): frozenset({"G", "M"}),
    ("tuning", "held"): frozenset({"G", "M", "H"}),    # 𝒕H (carries the cyan held basis)
    # the just tuning map 𝒋 is cyan; the yellow primes (P) and comma (C) columns green it,
    # the cyan T / H lists stay cyan, and the other-intervals ride the bare cyan 𝒋
    ("just", "primes"): frozenset({"J", "P"}),         # 𝒋 over the yellow domain basis P → green
    ("just", "commas"): frozenset({"J", "C"}),         # 𝒋C (cyan 𝒋 over the yellow comma basis → green)
    ("just", "targets"): frozenset({"J", "T"}),        # 𝐨 = 𝒋T
    ("just", "interest"): frozenset({"J"}),            # 𝒋·interest
    ("just", "held"): frozenset({"J", "H"}),           # 𝒋H
    ("just", "detempering"): frozenset({"J"}),         # 𝒋·D (the detempering list is neutral, so bare cyan 𝒋)
    # the retuning/error chain 𝒓 = 𝒕 − 𝒋 keeps 𝒕's G and 𝑀 AND 𝒋's cyan J (a difference carries
    # both operands' factors); the comma column adds C, the target / held columns add T / H
    ("retune", "primes"): frozenset({"G", "M", "J", "P"}),  # 𝒓 = 𝒈𝑀 − 𝒋 (over the domain primes P)
    ("retune", "commas"): frozenset({"G", "M", "C", "J"}),  # 𝒓C
    ("retune", "detempering"): frozenset({"G", "M", "J"}),  # 𝒓·D (the 𝒈𝑀 greens; D is neutral)
    ("retune", "targets"): frozenset({"G", "M", "T", "J"}),  # 𝐞 = 𝒓T
    ("retune", "interest"): frozenset({"G", "M", "J"}),
    ("retune", "held"): frozenset({"G", "M", "H", "J"}),    # 𝒓H (≈ 𝟎 since held just, but keeps the factors)
    ("damage", "targets"): frozenset({"G", "M", "T", "J"}),  # 𝐝 = |𝐞|𝒘, via 𝐞 = 𝒓T
    # the prescaler 𝑋 is cyan; it carries to every column it scales — the primes (P) and comma
    # (C) columns add yellow (→ green), the target / held columns add the cyan T / H, and the
    # other-intervals and (neutral) detempering list ride the bare cyan 𝑋
    ("prescaling", "primes"): frozenset({"X", "P"}),   # 𝑋 over the yellow domain basis P → green
    ("prescaling", "commas"): frozenset({"X", "C"}),   # 𝑋C (the prescaled comma basis → green)
    ("prescaling", "targets"): frozenset({"X", "T"}),  # 𝑋T
    ("prescaling", "interest"): frozenset({"X"}),      # 𝑋·interest
    ("prescaling", "held"): frozenset({"X", "H"}),     # 𝑋H
    ("prescaling", "detempering"): frozenset({"X"}),   # 𝑋·D (the detempering list is neutral, bare cyan 𝑋)
    # complexity 𝒄 = ‖𝑋·v‖ inherits the prescaler's cyan 𝑋 and the basis's own colour
    ("complexity", "primes"): frozenset({"X", "P"}),   # 𝒄 of the primes (norm of 𝑋 over the yellow P → green)
    ("complexity", "commas"): frozenset({"X", "C"}),   # 𝒄 of the comma basis (norm of 𝑋C → green)
    ("complexity", "targets"): frozenset({"X", "T"}),  # 𝒄 of the targets (norm of 𝑋T)
    ("complexity", "interest"): frozenset({"X"}),      # 𝒄 of the other-intervals
    ("complexity", "held"): frozenset({"X", "H"}),     # 𝒄 of the held basis (norm of 𝑋H)
    ("complexity", "detempering"): frozenset({"X"}),   # 𝒄 of the detempering (norm of 𝑋·D, neutral list → cyan)
    # the weight 𝒘 incorporates the target complexity list (𝒘 = 𝒄, 1, or 1∕𝒄 by the damage-
    # weight slope), so it inherits that list's cyan 𝑋 and rides the cyan target column T → cyan
    ("weight", "targets"): frozenset({"X", "T"}),      # 𝒘 (built from the cyan complexity 𝒄)
    # the audio rows mirror the just (cyan 𝒋; comma column greens via C) and tempered (G·M;
    # the target / held columns add the cyan T / H) sizes they sound
    ("just_audio", "primes"): frozenset({"J", "P"}),   # sounds 𝒋 over the yellow domain basis P → green
    ("just_audio", "commas"): frozenset({"J", "C"}),   # sounds 𝒋C (→ green)
    ("just_audio", "targets"): frozenset({"J", "T"}),  # sounds 𝐨 = 𝒋T
    ("just_audio", "interest"): frozenset({"J"}),      # sounds 𝒋·interest
    ("just_audio", "held"): frozenset({"J", "H"}),     # sounds 𝒋H
    ("just_audio", "detempering"): frozenset({"J"}),   # sounds 𝒋·D (neutral detempering list, bare cyan 𝒋)
    ("tempered_audio", "gens"): frozenset({"G", "B"}),   # sounds 𝒈 over the yellow generator basis B → green
    ("tempered_audio", "primes"): frozenset({"G", "M", "P"}),  # sounds 𝒕 = 𝒈𝑀 over the domain primes P
    ("tempered_audio", "commas"): frozenset({"G", "M", "C"}),
    ("tempered_audio", "detempering"): frozenset({"G", "M"}),  # sounds 𝒕·D (the 𝒈𝑀 greens; D is neutral)
    ("tempered_audio", "targets"): frozenset({"G", "M", "T"}),  # sounds 𝐚 = 𝒈𝑀T
    ("tempered_audio", "interest"): frozenset({"G", "M"}),
    ("tempered_audio", "held"): frozenset({"G", "M", "H"}),   # sounds 𝒕H
}

# The spine label cells carry no algebraic quantity — they head a value row or column, so
# they take that BAND's family colour, continuing the colour through the spine so each
# value column / row reads as one unbroken band. This is a BY-BAND rule, distinct from
# CELL_FACTORS' by-content rule: a spine cell is coloured by the band it heads, even where
# that band's value cells are green (e.g. the retuning units cell is cyan, since retuning
# is a tuning-family row, though the retuning 𝒓 value cells are green).
#   - SPINE_COLUMN_GROUP: a value COLUMN → its family. The counts + units ROW cells at that
#     column take this. generators / domain primes / commas are temperament; held / targets
#     are tuning; the detempering spine stays neutral (no entry), like its value tiles.
#   - SPINE_ROW_GROUP: a value ROW → its family. The quantities + units COLUMN cells at that
#     row take this. The mapping is temperament; the tuning-family rows are tuning.
SPINE_COLUMN_GROUP = {
    "gens": "temperament", "primes": "temperament", "commas": "temperament",
    "held": "tuning", "targets": "tuning",
}
SPINE_ROW_GROUP = {
    "mapping": "temperament",
    "tuning": "tuning", "just": "tuning", "retune": "tuning",
    "prescaling": "tuning", "complexity": "tuning",
}
# The spine rows (whose cells colour by their column) and spine columns (by their row).
SPINE_ROWS = frozenset({"counts", "units"})
SPINE_COLUMNS = frozenset({"quantities", "units"})

# The preset chooser dropdowns (settings["presets"]) as (name, row, column,
# title): each is a quick menu for one of the things you actually choose, riding under
# its governing tile in a titled control box — the temperament under the mapping matrix,
# the tuning scheme under the tuning map, the target interval set under the target list,
# the predefined prescaler under the prescaling matrix (box 𝐋, shown only with weighting).
PRESETS = (
    ("temperament", "mapping", "primes", "temperament"),
    ("tuning", "tuning", "primes", "established tuning scheme"),
    ("target", "vectors", "targets", "target interval set scheme"),
    ("prescaler", "prescaling", "primes", "predefined prescalers"),
)
# Extra copies of a preset chooser in another governing tile (the same control, its own
# id so the renderer keeps both): the tuning scheme also under the generator tuning map, the
# temperament also in the comma basis (which it loads). Each carries the same field label as
# its primary; the boxes stay within their own tiles, so the labels don't collide.
PRESET_COPIES = (
    ("tuning", "tuning", "gens", "established tuning scheme"),
    ("temperament", "vectors", "commas", "temperament"),
)
PRESET_ROWS = frozenset(row for _, row, _, _ in PRESETS + PRESET_COPIES)

# The "form" chooser (settings["form_controls"]) as (name, row, column, title): a control
# in the mapping and comma-basis boxes that re-stores that matrix in canonical form (an
# undoable edit). Rides below the tile in its own titled box, like a preset chooser.
FORM_CHOOSERS = (
    ("mapping", "mapping", "primes", "form"),
    ("comma_basis", "vectors", "commas", "form"),
)
FORM_CHOOSER_ROWS = frozenset(row for _, row, _, _ in FORM_CHOOSERS)

# Mnemonics: underline the caption letter that spells the tile's symbol (see
# SYMBOLS) — a memory aid linking the name to its symbol (e.g. "tuning map" -> t,
# "target interval damage list" -> d). Each value is a substring of the caption whose
# first letter — found at the substring's first occurrence — is the one underlined.
# That letter is usually a word-initial (so the value is that word), but it may fall
# mid-word: the complexity prescaler's symbol 𝑋 marks the x in "compleXity", so its
# value is the bare "x". Keep these in step with SYMBOLS. Symbols with no meaningful
# letter in their caption carry no entry — the abstract size-list letters of the
# mapped list (Y), the tempered (𝐚) and just (𝐨) lists.
MNEMONICS = {
    ("vectors", "commas"): "comma",     # C
    ("vectors", "targets"): "target",   # T
    ("vectors", "held"): "held",        # H
    ("vectors", "detempering"): "detempering",  # D
    ("mapping", "primes"): "mapping",   # 𝑀
    ("tuning", "gens"): "generator",    # 𝒈
    ("tuning", "primes"): "tuning",     # 𝒕
    ("just", "primes"): "just",         # 𝒋
    ("retune", "primes"): "retuning",   # 𝒓
    ("retune", "targets"): "error",     # 𝐞
    ("prescaling", "primes"): "x",      # 𝑋 — the x mid-word in "compleXity"
    ("complexity", "targets"): "complexity",  # 𝒄 — only the target list carries the symbol
    ("weight", "targets"): "weight",    # 𝒘
    ("damage", "targets"): "damage",    # 𝐝
}

# Each quantity's defining equation continues its symbol (see SYMBOLS): the mockup's
# "symbols section" from the first "=" on, appended to the symbol when equivalences
# is on so the line reads e.g. "𝒕 = 𝒈𝑀". Glyphs match SYMBOLS — bold-italic maps,
# math-italic mapping 𝑀, upright interval lists (T = the target interval list);
# operators stay upright.
# Only terms buildable from shipped features appear, so the superspace/canonical-
# form tails (the tuning map's "= B_Ls 𝒕_L", "𝑀 = 𝐅𝑀_c", "𝒋 = B_Ls 𝒋_L") are
# dropped — the mapping over primes and the just tuning map thus carry no
# continuation yet; the mapped comma basis instead vanishes to the zero matrix.
EQUIVALENCES = {
    ("mapping", "commas"): " = 𝑂",
    ("mapping", "targets"): " = 𝑀T",
    ("tuning", "detempering"): " = 𝒈",  # 𝒕D = the generator tuning map (tempering D gives the generators)
    ("tuning", "primes"): " = 𝒈𝑀",
    ("tuning", "targets"): " = 𝒕T",
    ("just", "targets"): " = 𝒋T",
    ("retune", "primes"): " = 𝒕 − 𝒋",
    ("retune", "targets"): " = 𝒓T",
    ("damage", "targets"): " = |𝐞|𝒘",  # 𝒘 is the weight LIST, not a matrix; build() drops it when the weight row is hidden (→ 𝐝 = |𝐞|)
    # the held intervals are tuned exactly just: the tempered size equals the just size (and
    # vice versa — the just row carries the inverse identity), so the retuning error vanishes
    ("tuning", "held"): " = 𝒋H",
    ("just", "held"): " = 𝒕H",
    ("retune", "held"): " = 𝟎",
}

# When all-interval (the checkbox is checked → Tₚ = I), the KEPT target-column tiles relabel to
# their prime-proxy forms, per D&D's Guide. Keyed (row, col) → the all-interval symbol / caption /
# equivalence, applied OVER SYMBOLS / CAPTIONS / EQUIVALENCES in build's caption loop. The target
# list becomes the prime-proxy list Tₚ = I. (Extended as more tiles are specified; the redundant
# tiles that get removed need no entry here.)
ALL_INTERVAL_SYMBOLS = {("vectors", "targets"): "Tₚ"}
ALL_INTERVAL_CAPTIONS = {("vectors", "targets"): "prime proxy target interval list"}
ALL_INTERVAL_EQUIVALENCES = {("vectors", "targets"): " = 𝐼"}
# all-interval mnemonics: the Tₚ subscript's "p" underlines BOTH p's it stands for — "prime"
# and "proxy" — on top of the base symbol-letter underline (the T's "target"). See the caption loop.
ALL_INTERVAL_MNEMONICS = {("vectors", "targets"): ("prime", "proxy")}

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
    ("tuning", "detempering"): "¢",
    ("tuning", "targets"): "¢",
    ("tuning", "interest"): "¢",
    ("just", "primes"): "¢/p",
    ("just", "commas"): "¢",
    ("just", "detempering"): "¢",
    ("just", "targets"): "¢",
    ("just", "interest"): "¢",
    ("retune", "primes"): "¢/p",
    ("retune", "commas"): "¢",
    ("retune", "detempering"): "¢",
    ("retune", "targets"): "¢",
    ("retune", "interest"): "¢",
    ("damage", "targets"): "¢",
    # the weighting region (per the mockup): the prescaler matrix L is octaves per prime
    # (oct/p — the prescaler has one diagonal entry per prime, like the mapping's g/p), L
    # applied to a vector set is plain octaves (oct); complexity is in complexity units (C)
    # — a map over the primes (C)/p, a list elsewhere (C); weight too.
    ("prescaling", "primes"): "oct/p",
    ("prescaling", "commas"): "oct",
    ("prescaling", "detempering"): "oct",
    ("prescaling", "targets"): "oct",
    ("prescaling", "interest"): "oct",
    ("complexity", "primes"): "(C)/p",
    ("complexity", "commas"): "(C)",
    ("complexity", "detempering"): "(C)",
    ("complexity", "targets"): "(C)",
    ("complexity", "interest"): "(C)",
    ("weight", "targets"): "(C)",
    # the held column mirrors the interest column's per-row units
    ("mapping", "held"): "g",
    ("tuning", "held"): "¢",
    ("just", "held"): "¢",
    ("retune", "held"): "¢",
    ("prescaling", "held"): "oct",
    ("complexity", "held"): "(C)",
}
UNITED_ROWS = frozenset(row for row, _ in UNITS)  # rows that reserve a units-line slot

# The weight row's equivalence is scheme-dependent: the weight is the complexity, unity,
# or its reciprocal by the scheme's damage-weight slope (see service.damage_weight_slope),
# so build() picks the right-hand side from this map rather than a fixed headline.
WEIGHT_EQUIVALENCE_BY_SLOPE = {
    "complexityWeight": " = 𝒄",
    "unityWeight": " = 𝟏",  # bold one — the all-ones weight vector (not a scalar)
    "simplicityWeight": " = 𝒄⁻¹",  # the complexity inverted (a list, so 𝒄⁻¹, not 1/𝒄)
}

# The concrete form the prescaler takes, by scheme — named in the bare tile's SYMBOL
# equivalence: the log-prime matrix 𝐿 for the default prescaler, the prime diagonal diag(𝒑) for
# sopfr, the identity 𝐼 for the unweighted count (copfr). 𝐿 and 𝐼 are math-italic capitals (like
# 𝑀 / 𝑋); the prime diagonal is written diag(𝒑) per the guide — a bare 𝑃 would clash with the
# guide's projection matrix (P = GM). So the bare tile reads 𝑋 = 𝐿 / 𝑋 = diag(𝒑) / 𝑋 = 𝐼. The
# 𝐿 here is also the glyph the products and column headers use when 𝑋 = 𝐿 (see prescaler_symbol).
PRESCALER_LETTER = {"log-prime": "𝐿", "prime": "diag(𝒑)", "identity": "𝐼"}

# Always-present content tiles (a row×column intersection) as (grey-panel id, row,
# column). Each gets a grey panel and a top-left fold toggle; the panel/toggle ids
# stay stable so the reconciling renderer can animate a single tile folding away.
# The counts row's tiles derive from COUNTS (see COUNTS_TILES) and the "other
# intervals of interest" column adds its own dynamically (only when the user has
# entered intervals) — both are prepended/appended in build().
TILES = (
    ("block:qgens", "quantities", "gens"),
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
# sizes) over primes/commas/targets, tempered_audio (the tempered sizes) over those plus
# the generators (whose tuned size the tuning row also carries; a generator has no just
# size, so just_audio has no generators tile). The interest column's audio tiles are
# appended dynamically in build() like its other tiles.
AUDIO_TILES = (
    ("block:just_audio:primes", "just_audio", "primes"),
    ("block:just_audio:commas", "just_audio", "commas"),
    ("block:just_audio:targets", "just_audio", "targets"),
    ("block:tempered_audio:gens", "tempered_audio", "gens"),
    ("block:tempered_audio:primes", "tempered_audio", "primes"),
    ("block:tempered_audio:commas", "tempered_audio", "commas"),
    ("block:tempered_audio:targets", "tempered_audio", "targets"),
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
# the duals the grid itself lets you type into: the mapping (mapping/primes), the comma
# basis (vectors/commas), the generator tuning map (tuning/gens), the target interval list
# (vectors/targets), and the bare prescaler 𝐿's diagonal (prescaling/primes — the matrix
# form parses to a d-tuple via service.parse_prescaler_diagonal). Every other plain-text
# value is a computed read-only display.
EDITABLE_PTEXT = frozenset({("mapping", "primes"), ("vectors", "commas"), ("tuning", "gens"),
                            ("vectors", "targets"), ("prescaling", "primes")})
EDITABLE_PTEXT_ROWS = frozenset(r for r, _ in EDITABLE_PTEXT)  # rows whose band holds an input
# Rows that carry a plain-text band (every value row; the counts row has none). The
# quantities row's band holds only the domain-primes basis string ("2.3.5"); its interval-
# ratio columns show no plain text (the gridded ratio is already the formatted value). Every
# other row shows one EBK string per tile.
PTEXT_ROWS = frozenset({"quantities", "vectors", "mapping", "tuning", "just", "retune", "damage",
                        "prescaling", "complexity", "weight"})

# Cell kinds the value-display toggles filter out. "gridded values" hides
# everything a tile holds besides its fold toggle, name caption and plain-text
# value box: the value numbers (including the just row's "mathexpr" log₂ form),
# the EBK marks framing them, and the domain/comma ± controls. (Gridded off with
# plain text on leaves just the inline string — the two value views are independent.)
GRIDDED_KINDS = frozenset({
    "prime", "ratiocell", "commaratio", "genratio", "mapping", "mapped", "commacell",
    "vec", "tval", "mathexpr", "interestcell", "formcell", "heldcell", "gentuningcell", "targetcell",
    "prescalercell",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "matlabel",
    "minus", "plus", "gen_minus", "gen_plus", "map_minus", "map_plus", "comma_minus", "comma_plus", "basis_minus",
    "interest_minus", "interest_plus", "held_minus", "held_plus", "target_minus", "target_plus", "optimize",
    "colgrip", "dropslot",  # the drag-and-drop fan controls (a column grip + per-gap drop slot)
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
    "gentuningcell", "targetcell", "prescalercell",
})
