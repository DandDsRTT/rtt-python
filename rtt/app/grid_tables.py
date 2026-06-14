"""Semantic content tables for the temperament grid (extracted from spreadsheet.py).

Pure data -- *which* quantities exist and their symbols, captions, units, mnemonics,
colorization factors and tile sets -- with no layout logic and no imports. spreadsheet.py
re-exports everything here (`from rtt.app.grid_tables import *`) so `spreadsheet.<NAME>`
stays the public surface app.py, tooltips and the tests read.
"""

# Sentinel markers wrapping a subscript range, converted to <sub>…</sub> by the renderers
# (app._math_html for symbols/labels, app._bold_units for units). NORM_SUB forces italic on
# its whole range (suits a bare "q"); plain SUB leaves each glyph its own slant ("dual(𝑞)").
# Private-Use-Area code points so they never collide with content. Defined here (not in
# spreadsheet) so the semantic tables below can embed them; spreadsheet re-exports via import *.
NORM_SUB_OPEN = chr(0xE001)
NORM_SUB_CLOSE = chr(0xE002)
SUB_OPEN = chr(0xE003)
SUB_CLOSE = chr(0xE004)
# The chapter-9 superspace marker: a real subscript CAPITAL L (the guide's "lifted to the
# superspace" subscript). Unicode has no subscript-capital-L, so we render a capital "L" inside
# <sub> rather than the lowercase ₗ (U+2097) the tables used to embed.
SUBSCRIPT_L = SUB_OPEN + "L" + SUB_CLOSE
# The canonical-FORM marker: a subscript CAPITAL C (the form is canonical by default — when the
# form layer is on we acknowledge that with this subscript on every generator-basis object). Like
# SUBSCRIPT_L it renders a capital "C" inside <sub> (Unicode has no subscript-capital-C). NB it is
# distinct from the upright comma-basis C the tables embed as a plain glyph (e.g. 𝑀C, the mapped
# comma basis) — there the form subscript sits between: 𝑀{C-sub}C.
SUBSCRIPT_C = SUB_OPEN + "C" + SUB_CLOSE

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

# The chapter-9 superspace columns carry counts too: rL (the count of superspace
# generators) and dL (the count of superspace primes). The symbol is two characters —
# a letter and a literal "L" — which build()'s _count_sym renders math-italic-letter +
# Unicode subscript-ₗ (so the cell shows "𝑟ₗ = 3", "𝑑ₗ = 4"). Like OPTIMIZATION_COUNTS
# / DETEMPERING_COUNTS, these are conditional (only when the nonstandard_domain Show
# toggle adds the superspace columns), so they live in their own tuple.
SUPERSPACE_COUNTS = (
    ("ssgens", "rL", "superspace rank"),
    ("ssprimes", "dL", "superspace dimensionality"),
)
SUPERSPACE_COUNTS_TILES = tuple(
    (f"block:counts:{ckey}", "counts", ckey) for ckey, *_ in SUPERSPACE_COUNTS
)

# Quantity-name captions shown inside each (row, column) tile when names are on.
# In the comma column, the rows whose quantity the temperament zeroes out — mapped
# (𝑀C), tempered (𝒕C) and retuned (𝒓C) — append "(made to vanish!)"; the just row
# shows the comma's genuine untempered size, so it omits the note.
CAPTIONS = {
    # the chapter-9 superspace tiles — the basis-embedding matrix B_L lives in
    # (ss_vectors, primes), the temperament's superspace mapping M_L lives in
    # (ss_mapping, ssprimes), and the trivial superspace JI mapping M_jL = I lives in
    # (ss_vectors, ssprimes). Phase 4 also adds 𝒈ₗ / 𝒕ₗ / 𝒋ₗ / 𝒓ₗ captions over the
    # superspace tuning rows when their cells are emitted.
    ("ss_vectors", "ssprimes"): "superspace JI mapping",
    ("ss_vectors", "primes"): "basis change matrix",
    ("ss_vectors", "commas"): "comma basis in superspace",
    ("ss_vectors", "held"): "held interval basis in superspace",
    ("ss_vectors", "targets"): "target interval list in superspace",
    ("ss_vectors", "interest"): "intervals in superspace",
    ("ss_vectors", "detempering"): "generator detempering in superspace",
    ("ss_mapping", "ssgens"): "superspace mapping over its generators",
    ("ss_mapping", "ssprimes"): "superspace mapping",
    ("ss_mapping", "primes"): "mapping from domain intervals to superspace generators",
    ("ss_mapping", "commas"): "comma basis in superspace generators",
    ("ss_mapping", "held"): "held interval basis in superspace generators",
    ("ss_mapping", "targets"): "target interval list in superspace generators",
    ("ss_mapping", "interest"): "intervals in superspace generators",
    ("ss_mapping", "detempering"): "generator detempering in superspace generators",
    # the superspace tempering projection P_L = G_L·M_L (the chapter-9 analogue of the on-domain P)
    ("ss_projection", "ssprimes"): "superspace projection",
    # the rest of the superspace projection row — the embedding G_L and P_L applied to each column's
    # lifted vectors (the chapter-9 analogues of the on-domain G / P·D / P·V / P·T / P·H projected tiles)
    ("ss_projection", "ssgens"): "superspace generator embedding",
    ("ss_projection", "primes"): "superspace projected subspace basis elements",
    ("ss_projection", "detempering"): "projected generator detempering in superspace",
    ("ss_projection", "commas"): "projected comma basis in superspace",
    ("ss_projection", "targets"): "projected target interval list in superspace",
    ("ss_projection", "held"): "projected held interval basis in superspace",
    ("ss_projection", "interest"): "projected intervals in superspace",
    ("tuning", "ssgens"): "superspace generator tuning map",
    ("tuning", "ssprimes"): "superspace tuning map",
    ("just", "ssprimes"): "superspace just tuning map",
    ("retune", "ssprimes"): "superspace retuning map",
    ("vectors", "commas"): "comma basis",
    ("vectors", "targets"): "target interval list",
    ("canon", "gens"): "generator form matrix",
    ("canon", "primes"): "canonical mapping",
    ("vectors", "held"): "held interval basis",
    ("vectors", "detempering"): "generator detempering",
    ("vectors", "primes"): "JI mapping",                 # 𝑀ⱼ = 𝐼 (domain primes as vectors over themselves)
    ("mapping", "primes"): "(temperament) mapping",
    # the standard-domain identity objects (gated on identity_objects, like the superspace pair):
    ("mapping", "gens"): "mapped generators",            # 𝑀𝐺 = 𝐼 (M over its own generators)
    ("mapping", "detempering"): "mapped generator detemperings",  # 𝑀D = 𝐼
    ("mapping", "commas"): "mapped comma basis (made to vanish!)",
    ("mapping", "targets"): "mapped target interval list",
    # the rational tempering projection P = GM (a d×d operator over the domain primes),
    # a stack of maps like the mapping itself (toggled with the projection sub-control)
    ("projection", "primes"): "projection",
    # the rational generator embedding G = H(MH)⁻¹ (d×r): its columns are the held tuning's
    # generators as fractional vectors. Rides the projection row band in the gens columns,
    # beside P (which it multiplies the mapping into: P = GM). Same projection sub-control.
    ("projection", "gens"): "generator embedding",
    # the projected unrotated vector list P·V — each unrotated vector scaled by its eigenvalue:
    # the comma columns vanish (P·c = 0), the unchanged columns are held unchanged (P·u = u)
    ("projection", "commas"): "projected unrotated vector list",
    # the projected vector lists riding the projection row band — P applied to each column's interval
    # vectors (P·D / P·T / P·H / P·interest), the projection-row counterparts of the interval-vectors
    # row's tiles. P·D is the embedding G (P·D = GMD = G); P·H = H (the held intervals are unchanged).
    ("projection", "detempering"): "projected generator detempering",
    ("projection", "targets"): "projected target interval list",
    ("projection", "held"): "projected held interval basis",
    ("projection", "interest"): "projected intervals",
    # the chapter-9 superspace projection tiles (between G and P in the row): G_L→s the embedding from
    # the superspace generators to the subspace elements, P_L→s = G_L→s·M_L the projection from the
    # superspace to the subspace (the on-domain P factors through it: P = G_L→s·M_s→L = P_L→s·B_Lᵀ)
    ("projection", "ssgens"): "embedding from superspace generators to subspace elements",
    ("projection", "ssprimes"): "projection from superspace to subspace",
    # the scaling factors λ = diag(λ) — the projection's eigenvalue list over the
    # consolidated V = C|U column (0 per comma, 1 per unchanged interval); toggled with
    # projection, one row above the interval-vectors row
    ("scaling_factors", "commas"): "scaling factor (eigenvalue) list",
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
    # the chapter-9 superspace shift: once the ss-primes column appears (neutral / prime-based),
    # the bare prescaler moves here over the TRUE primes; the domain-primes tile then becomes the
    # prescaled subspace basis elements 𝐿·B_Ls ((prescaling, primes) is overridden to that caption
    # in _resolve_prescaler_labels when show_superspace).
    ("prescaling", "ssprimes"): "(superspace) complexity prescaler",
    ("prescaling", "commas"): "complexity prescaled comma basis",
    ("prescaling", "detempering"): "complexity prescaled generator detempering",
    ("prescaling", "targets"): "complexity prescaled target interval list",
    ("complexity", "primes"): "domain prime complexity map",
    # the prime complexity map ‖𝐿[i]‖q moves here with the bare prescaler; the domain-primes tile
    # then becomes the "subspace basis element complexity map" (overridden when show_superspace)
    ("complexity", "ssprimes"): "domain prime complexity map",
    ("complexity", "commas"): "comma basis interval complexity list",
    ("complexity", "detempering"): "generator detempering complexity list",
    ("complexity", "targets"): "target interval complexity list",
    ("weight", "targets"): "target interval weight list",
    ("damage", "targets"): "target interval damage list",
    **{("counts", ckey): name for ckey, _sym, name in
       COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS},
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
    # the chapter-9 superspace anchors: B_L the basis-embedding matrix (upright capital,
    # parallel to C/T/D — an interval basis), 𝑀ₗ the temperament's superspace mapping
    # (math-italic M, parallel to 𝑀), 𝑀ⱼₗ the trivial superspace JI mapping (parallel to
    # the just tuning map 𝒋). Phase 4F adds the cyan tuning row's superspace symbols.
    ("ss_vectors", "primes"): "BL",      # B (upright) + Unicode subscript L
    ("ss_mapping", "ssprimes"): "𝑀L",   # math-italic M (\U0001D440) + subscript L
    ("tuning", "ssgens"): "𝒈L",
    ("tuning", "ssprimes"): "𝒕L",
    ("just", "ssprimes"): "𝒋L",
    ("retune", "ssprimes"): "𝒓L",
    ("ss_vectors", "ssprimes"): f"𝑀ⱼ{SUBSCRIPT_L}",  # M_jL = I (superspace JI mapping)
    ("ss_vectors", "commas"): f"C{SUBSCRIPT_L}",      # C_L = B_L·C
    ("ss_vectors", "held"): f"H{SUBSCRIPT_L}",        # H_L = B_L·H
    ("ss_vectors", "targets"): f"T{SUBSCRIPT_L}",     # T_L = B_L·T
    ("ss_vectors", "detempering"): f"D{SUBSCRIPT_L}", # D_L = B_L·D
    ("ss_mapping", "ssgens"): f"𝑀{SUBSCRIPT_L}g{SUBSCRIPT_L}",  # M_LgL = I
    ("ss_mapping", "primes"): f"𝑀ₛ→{SUBSCRIPT_L}",   # M_s→L = M_L·B_L
    ("ss_mapping", "commas"): f"𝑀ₛ→{SUBSCRIPT_L}C",  # mapped commas (vanish)
    ("ss_mapping", "held"): f"𝑀ₛ→{SUBSCRIPT_L}H",
    ("ss_mapping", "targets"): f"Y{SUBSCRIPT_L}",     # Y_L = M_s→L·T
    ("ss_mapping", "detempering"): f"𝑀ₛ→{SUBSCRIPT_L}D",
    ("scaling_factors", "commas"): "𝝀",  # the eigenvalue list diag(λ) over V (bold-italic λ)
    ("projection", "commas"): "𝑃V",  # the projected unrotated vector list P·V (italic 𝑃 operator + upright V basis)
    ("projection", "primes"): "𝑃",   # the rational tempering projection P = GM (math-italic P, like 𝑀)
    ("projection", "gens"): "G",     # the rational generator embedding G — an UPRIGHT capital (a basis, like C/T/D/B)
    # the projected vector lists: 𝑃 (italic operator) applied to each column's basis (upright capital,
    # like the vectors row's D/T/H). interest carries no symbol (a loose collection, like the vectors row).
    ("projection", "detempering"): "𝑃D",
    ("projection", "targets"): "𝑃T",
    ("projection", "held"): "𝑃H",
    # the chapter-9 superspace projection tiles. G_L→s upright (a basis, like G); P_L→s math-italic
    # (an operator, like P). L→s mirrors the M_s→L "s→L" subscript pattern (SUBSCRIPT_L + → + ₛ).
    ("projection", "ssgens"): f"G{SUBSCRIPT_L}→ₛ",
    ("projection", "ssprimes"): f"𝑃{SUBSCRIPT_L}→ₛ",
    # the superspace projection P_L = G_L·M_L: math-italic 𝑃 + subscript L, parallel to M_L's 𝑀L
    # and the on-domain P's 𝑃 (an operator; its " = G_L 𝑀_L" form tail is set in EQUIVALENCES)
    ("ss_projection", "ssprimes"): f"𝑃{SUBSCRIPT_L}",
    # the rest of the superspace projection row: the embedding G_L (upright, a basis like the on-domain
    # G) and P_L applied to each lifted basis — 𝑃_L (italic operator) + the upright basis letter with
    # its subscript L (B_L / D_L / C_L / T_L / H_L), parallel to the on-domain 𝑃D / 𝑃T / 𝑃H. Interest
    # carries no symbol (a loose collection, like the on-domain projected interest). (The mockup writes
    # P_L·B_Ls with a trailing ₛ, but no other symbol carries that subscript, so we drop it for parity.)
    ("ss_projection", "ssgens"): f"G{SUBSCRIPT_L}",
    ("ss_projection", "primes"): f"𝑃{SUBSCRIPT_L}B{SUBSCRIPT_L}",
    ("ss_projection", "detempering"): f"𝑃{SUBSCRIPT_L}D{SUBSCRIPT_L}",
    ("ss_projection", "commas"): f"𝑃{SUBSCRIPT_L}C{SUBSCRIPT_L}",
    ("ss_projection", "targets"): f"𝑃{SUBSCRIPT_L}T{SUBSCRIPT_L}",
    ("ss_projection", "held"): f"𝑃{SUBSCRIPT_L}H{SUBSCRIPT_L}",
    ("vectors", "commas"): "C",
    ("vectors", "targets"): "T",
    ("vectors", "detempering"): "D",  # the generator detempering matrix (upright, like C/T)
    ("vectors", "primes"): "𝑀ⱼ",      # 𝑀ⱼ = 𝐼 (the JI mapping; the domain twin of 𝑀ⱼL)
    # the canonical-mapping row: the canonical mapping 𝑀_C over the primes (its subscript is BAKED in
    # — this row IS the canonical form, always, vs the main mapping's dynamic subscript) and the
    # generator form matrix 𝐹 over the (canonical) generators, with 𝐹·𝑀 = 𝑀_C.
    ("canon", "primes"): f"𝑀{SUBSCRIPT_C}",
    ("canon", "gens"): "𝐹",
    ("mapping", "primes"): "𝑀",
    ("mapping", "gens"): "𝑀G",          # 𝑀𝐺 = 𝐼: M (italic) + the generator basis G (upright)
    ("mapping", "detempering"): "𝑀D",   # 𝑀D = 𝐼: M (italic) + the detempering basis D (upright)
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
    # the superspace bare prescaler (when show_superspace it carries 𝑋; the domain-primes tile then
    # takes the product symbol 𝐿B_Ls, set live in _resolve_prescaler_labels)
    ("prescaling", "ssprimes"): "𝑋",
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
    # the canonical-mapping row's stacks: 𝑀_C's covector rows 𝒎_Cᵢ (𝒎 + the baked canonical
    # subscript) and the generator form matrix 𝐹's rows 𝒇ᵢ
    ("canon", "primes"): f"𝒎{SUBSCRIPT_C}",
    ("canon", "gens"): "𝒇",
    # the JI mapping M_j = I rows (vectors × primes): each row a covector 𝒎ⱼᵢ (𝒎 + subscript j),
    # the domain twin of M_jL's 𝒎ⱼL — sits in the same primes-column gutter as the mapping's 𝒎ᵢ
    ("vectors", "primes"): "𝒎ⱼ",
    # the projection P = GM is a stack of maps like 𝑀 (each row a covector 𝒑ᵢ over the primes)
    ("projection", "primes"): "𝒑",
    # P_L→s is a covector stack like P (each row a covector 𝒑_L→sᵢ over the superspace primes)
    ("projection", "ssprimes"): f"𝒑{SUBSCRIPT_L}→ₛ",
    # each row of the bare prescaler matrix is a covector, labelled with the lowercase of the
    # glyph it realises — build() swaps in 𝒍ᵢ when 𝑋 = 𝐿 (the log-prime matrix), else the generic
    # 𝒙ᵢ (see row_labels). The static value is that generic fallback.
    ("prescaling", "primes"): "𝒙",
    # the superspace bare prescaler's rows, when it moves into the ss-primes column (build() swaps
    # 𝒍ᵢ for 𝒙ᵢ when 𝑋 = 𝐿, same as the domain-primes bare prescaler)
    ("prescaling", "ssprimes"): "𝒙",
    # the chapter-9 superspace mapping M_L: each row a covector over the dL ss_primes,
    # labelled 𝒎ₗᵢ (math-italic 𝒎 + subscript ₗ + index), parallel to the existing M's 𝒎ᵢ
    ("ss_mapping", "ssprimes"): "𝒎L",
    ("ss_mapping", "primes"): "𝒎ₛ→L",   # m_s→L subrow headers (mapping from domain intervals)
    # M_jL's identity rows likewise: each row labelled 𝒎ⱼₗᵢ — math-italic 𝒎 + subscript j
    # (U+2C7C) + subscript ₗ
    ("ss_vectors", "ssprimes"): "𝒎ⱼL",
    # the superspace projection P_L: each row a covector over the dL ss_primes, labelled 𝒑ₗᵢ —
    # math-bold-italic 𝒑 + subscript ₗ + index, parallel to the on-domain P's 𝒑ᵢ and M_L's 𝒎ₗᵢ
    ("ss_projection", "ssprimes"): f"𝒑{SUBSCRIPT_L}",
}
COL_LABEL_LETTERS = {
    # MD = I columns (mapping × detempering): each column M·𝐝ᵢ, headed 𝑀𝐝ᵢ (M + bold d + index)
    ("mapping", "detempering"): "𝑀𝐝",
    # the scaling factors λ = diag(λ): one eigenvalue λᵢ per V sub-column (commas then unchanged),
    # the scalar entries in italic (𝜆ᵢ), like the other size lists' italic scalar headers
    ("scaling_factors", "commas"): "𝜆",
    # the projected unrotated vector list: each column is 𝑃·𝐯ᵢ (𝑃v₁ 𝑃v₂ … in the mockup; italic 𝑃)
    ("projection", "commas"): "𝑃𝐯",
    # the generator embedding G is a vector list (each column a held generator 𝐠ᵢ as a prime vector)
    ("projection", "gens"): "𝐠",
    # G_L→s is a vector list too (each column a superspace generator 𝐠_L→sᵢ as a domain prime vector)
    ("projection", "ssgens"): f"𝐠{SUBSCRIPT_L}→ₛ",
    # the projected vector lists' columns: 𝑃 (italic operator) + the bold column letter of the list it
    # projects (𝑃𝐝 / 𝑃𝐭 / 𝑃𝐡 / 𝑃𝐢), like the mapped lists' 𝑀𝐜 / 𝑀𝐡
    ("projection", "detempering"): "𝑃𝐝",
    ("projection", "targets"): "𝑃𝐭",
    ("projection", "held"): "𝑃𝐡",
    ("projection", "interest"): "𝑃𝐢",
    # the SUPERSPACE projection row's column labels: G_L's columns are the superspace generators 𝐠_L;
    # the rest are 𝑃_L (italic operator) + the bold column letter of the lifted list it projects
    # (𝑃_L𝐛 / 𝑃_L𝐝 / 𝑃_L𝐜 / 𝑃_L𝐭 / 𝑃_L𝐡 / 𝑃_L𝐢), parallel to the on-domain 𝑃𝐝 / 𝑃𝐭 / 𝑃𝐡 / 𝑃𝐢
    ("ss_projection", "ssgens"): f"𝐠{SUBSCRIPT_L}",
    ("ss_projection", "primes"): f"𝑃{SUBSCRIPT_L}𝐛",
    ("ss_projection", "detempering"): f"𝑃{SUBSCRIPT_L}𝐝",
    ("ss_projection", "commas"): f"𝑃{SUBSCRIPT_L}𝐜",
    ("ss_projection", "targets"): f"𝑃{SUBSCRIPT_L}𝐭",
    ("ss_projection", "held"): f"𝑃{SUBSCRIPT_L}𝐡",
    ("ss_projection", "interest"): f"𝑃{SUBSCRIPT_L}𝐢",
    # interval vectors row — d-tall column-vector matrices
    ("vectors", "commas"): "𝐜",
    ("vectors", "targets"): "𝐭",
    ("vectors", "held"): "𝐡",
    ("vectors", "detempering"): "𝐝",
    # chapter-9 superspace interval-vectors row — dL-tall column-vector matrices over the
    # superspace primes. B_L's columns are the domain elements (𝐛ᵢ); the lifted lists carry
    # their on-domain letter with a subscript L.
    ("ss_vectors", "primes"): "𝐛",
    ("ss_vectors", "commas"): f"𝐜{SUBSCRIPT_L}",
    ("ss_vectors", "held"): f"𝐡{SUBSCRIPT_L}",
    ("ss_vectors", "targets"): f"𝐭{SUBSCRIPT_L}",
    ("ss_vectors", "detempering"): f"𝐝{SUBSCRIPT_L}",
    # chapter-9 superspace mapping row — mapped lists into the superspace generators (Y_L's
    # columns are 𝐲ₗᵢ; the others mirror the on-domain mapped lists)
    ("ss_mapping", "commas"): f"𝑀{SUBSCRIPT_L}𝐜",
    ("ss_mapping", "targets"): f"𝐲{SUBSCRIPT_L}",
    ("ss_mapping", "held"): f"𝑀{SUBSCRIPT_L}𝐡",
    ("ss_mapping", "detempering"): f"𝑀{SUBSCRIPT_L}𝐝",
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
    # the chapter-9 superspace tuning-family covectors, each entry per superspace generator /
    # prime — 𝒈ʟᵢ over ssgens, 𝒕ʟᵢ / 𝒋ʟᵢ / 𝒓ʟᵢ over ssprimes (parallel to the on-domain
    # 𝒈ᵢ / 𝒕ᵢ / 𝒋ᵢ / 𝒓ᵢ). M_L / M_jL head their ROWS (𝒎ʟᵢ) instead, like the on-domain mapping.
    ("tuning", "ssgens"): f"𝒈{SUBSCRIPT_L}",
    ("tuning", "ssprimes"): f"𝒕{SUBSCRIPT_L}",
    ("just", "ssprimes"): f"𝒋{SUBSCRIPT_L}",
    ("retune", "ssprimes"): f"𝒓{SUBSCRIPT_L}",
    # the complexity row's headers (EVERY column, targets included) track the live prescaler
    # glyph and the equivalences layer, so build() fills them in per-render via
    # _prescaler_col_labels (NOT here): the auxiliary columns spell the bare norm
    # ‖prescaler·basisᵢ‖q, the named targets column the symbol cₙ with that norm as its
    # equivalence tail. So the complexity row carries no static entry — it is registered in
    # COL_LABELED_ROWS explicitly (like the prescaling row, also built per-render).
}
# multi-row matrices reserve top/bottom frame bands for their EBK marks: the mapping,
# the canonical mapping and the complexity-prescaling matrix for their spanning
# bracket+brace, the interval vectors for the per-column ket marks. The chapter-9
# superspace rows (B_L's vector columns, M_L's covector stack) likewise frame their
# tiles when Phase 4 populates them — Phase 3 reserves the frame bands so the
# row_axis fan splits into one rule per cell-row (dL / rL sub-rules).
FRAMED_ROWS = frozenset({"mapping", "canon", "vectors", "prescaling",
                         "ss_vectors", "ss_mapping", "ss_projection",
                         "projection"})
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
# Keys match TILES. NB the generator RATIOS shown in the spine (mapping ×
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
    # the standard-domain identity objects (gated on identity_objects): all 𝑀-family, washed yellow
    # like their mapping-row / primes-column siblings — M_j over the domain primes P, MG over the
    # generator basis B (the generators column carries B in every tile), MD over the neutral D.
    ("vectors", "primes"): frozenset({"M", "P"}),      # 𝑀ⱼ = 𝐼 (the JI mapping over the domain primes P)
    ("mapping", "gens"): frozenset({"M", "B"}),        # 𝑀𝐺 = 𝐼 (over the generator basis B)
    ("mapping", "detempering"): frozenset({"M"}),      # 𝑀D = 𝐼 (D is neutral, like the other detempering tiles)
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
    ("prescaling", "ssprimes"): frozenset({"X", "P"}), # the (superspace) prescaler over the true primes
    ("prescaling", "commas"): frozenset({"X", "C"}),   # 𝑋C (the prescaled comma basis → green)
    ("prescaling", "targets"): frozenset({"X", "T"}),  # 𝑋T
    ("prescaling", "interest"): frozenset({"X"}),      # 𝑋·interest
    ("prescaling", "held"): frozenset({"X", "H"}),     # 𝑋H
    ("prescaling", "detempering"): frozenset({"X"}),   # 𝑋·D (the detempering list is neutral, bare cyan 𝑋)
    # complexity 𝒄 = ‖𝑋·v‖ inherits the prescaler's cyan 𝑋 and the basis's own colour
    ("complexity", "primes"): frozenset({"X", "P"}),   # 𝒄 of the primes (norm of 𝑋 over the yellow P → green)
    ("complexity", "ssprimes"): frozenset({"X", "P"}), # the superspace prime complexity map ‖𝐿[i]‖q
    ("complexity", "commas"): frozenset({"X", "C"}),   # 𝒄 of the comma basis (norm of 𝑋C → green)
    ("complexity", "targets"): frozenset({"X", "T"}),  # 𝒄 of the targets (norm of 𝑋T)
    ("complexity", "interest"): frozenset({"X"}),      # 𝒄 of the other-intervals
    ("complexity", "held"): frozenset({"X", "H"}),     # 𝒄 of the held basis (norm of 𝑋H)
    ("complexity", "detempering"): frozenset({"X"}),   # 𝒄 of the detempering (norm of 𝑋·D, neutral list → cyan)
    # the weight 𝒘 incorporates the target complexity list (𝒘 = 𝒄, 1, or 1∕𝒄 by the damage-
    # weight slope), so it inherits that list's cyan 𝑋 and rides the cyan target column T → cyan
    ("weight", "targets"): frozenset({"X", "T"}),      # 𝒘 (built from the cyan complexity 𝒄)
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
# A family may be a single string OR a set of families: a row/column that genuinely carries
# both the cyan tuning and the yellow temperament family reads green across its whole band
# (e.g. the damage row 𝐝 = |𝐞|𝒘 — the tuning retuning error 𝐞 over the temperament mapping 𝑀).
SPINE_COLUMN_GROUP = {
    "gens": "temperament", "primes": "temperament", "commas": "temperament",
    "held": "tuning", "targets": "tuning",
}
SPINE_ROW_GROUP = {
    "mapping": "temperament",
    "tuning": "tuning", "just": "tuning", "retune": "tuning",
    "prescaling": "tuning", "complexity": "tuning",
    "weight": "tuning",                                  # the cyan weight band 𝒘
    "damage": frozenset({"tuning", "temperament"}),      # both families → the green damage band 𝐝
}
# The spine rows (whose cells colour by their column) and spine columns (by their row).
SPINE_ROWS = frozenset({"counts", "units"})
SPINE_COLUMNS = frozenset({"quantities", "units"})

# Chapter-9 superspace block colorization — a TUNING-family (cyan) REGION by design: the whole
# block exists to compute tuning over the prime superspace, so it reads cyan, turning GREEN only
# where it crosses a yellow temperament COLUMN (the domain-basis elements / commas, carrying P / C).
# This is a deliberate coarse REGION tint, NOT the per-object CELL_FACTORS scheme the rest of the
# grid uses — that scheme would wash the superspace primes yellow (they ARE genuine primes), but
# here the block is cyan. A tile is in the region if it sits in a superspace column OR a superspace
# row; the temperament overlay (→ green) rides the yellow domain columns it crosses, while its own
# ssgens / ssprimes columns, the M_L mapping, the tuning maps (𝒈ₗ/𝒕ₗ/𝒋ₗ/𝒓ₗ) and the JI mapping M_jL
# stay pure cyan. (tile_groups reads these, keying green off SPINE_COLUMN_GROUP's temperament cols.)
SUPERSPACE_REGION_COLUMNS = frozenset({"ssgens", "ssprimes"})
SUPERSPACE_REGION_ROWS = frozenset({"ss_vectors", "ss_mapping", "ss_projection"})

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
    # the established projection chooser rides the projection matrix P; its named rational
    # tuning's held intervals drive P = GM (and the embedding G, which copies it — see below).
    ("projection", "projection", "primes", "established projection"),
)
# Extra copies of a preset chooser in another governing tile (the same control, its own
# id so the renderer keeps both): the tuning scheme also under the generator tuning map, the
# temperament also in the comma basis (which it loads), the established projection also under
# the generator embedding G (relabelled "established embedding" — one tuning, two views, since
# P = GM). The boxes stay within their own tiles, so the labels don't collide.
PRESET_COPIES = (
    ("tuning", "tuning", "gens", "established tuning scheme"),
    ("temperament", "vectors", "commas", "temperament"),
    ("projection", "projection", "gens", "established embedding"),
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
    ("ss_projection", "ssprimes"): "projection",  # 𝑃L → underline the "p" in "superspace projection"
    # superspace anchors — underline the symbol-letter where it sits in the caption
    ("ss_vectors", "primes"): "basis",        # BL → underline the "b" in "basis embedding…"
    ("vectors", "primes"): "mapping",        # 𝑀ⱼ → underline the "m" in "JI mapping"
    ("mapping", "gens"): "mapped",            # 𝑀𝐺 → underline the "m" in "mapped generators"
    ("mapping", "detempering"): "mapped",     # 𝑀D → underline the "m" in "mapped generator detemperings"
    ("ss_mapping", "ssprimes"): "mapping",    # 𝑀L → underline the "m" in "superspace mapping"
    ("ss_vectors", "ssprimes"): "mapping",  # 𝑀ⱼL → "m" in "superspace JI mapping"
    ("tuning", "ssgens"): "generator",        # 𝒈L → "g" in "superspace generator tuning map"
    ("tuning", "ssprimes"): "tuning",         # 𝒕L → "t" in "superspace tuning map"
    ("just", "ssprimes"): "just",             # 𝒋L → "j" in "superspace just tuning map"
    ("retune", "ssprimes"): "retuning",       # 𝒓L → "r" in "superspace retuning map"
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
    ("prescaling", "ssprimes"): "x",    # the superspace bare prescaler — same "compleXity" x
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
    # the superspace projection P_L = G_L·M_L (the b/b operator's form tail), parallel to the
    # on-domain P's " = G𝑀 …" — upright basis G_L composed with the math-italic operand 𝑀_L
    ("ss_projection", "ssprimes"): f" = G{SUBSCRIPT_L}𝑀{SUBSCRIPT_L}",
    # the chapter-9 superspace M_jL is trivially the identity (each superspace prime is
    # its own basis element). 𝒕ₗ products parallel the existing 𝒕 = 𝒈𝑀 / 𝒓 = 𝒕 − 𝒋
    # chains; 𝒈ₗ and 𝒋ₗ are primary (no continuation).
    ("tuning", "ssprimes"): " = 𝒈L𝑀L",
    ("retune", "ssprimes"): " = 𝒕L − 𝒋L",
    # the chapter-9 superspace block defining equations (each tile lifted through B_L / M_s→L,
    # matching the mockup): the two identity objects = 𝐼; lifted lists = B_L·(on-domain list);
    # mapped lists run those through M_s→L (the mapped comma basis vanishing to 𝑂).
    ("ss_vectors", "ssprimes"): " = 𝐼",
    ("ss_vectors", "commas"): " = BLC",
    ("ss_vectors", "held"): " = BLH",
    ("ss_vectors", "targets"): " = BLT",
    ("ss_vectors", "detempering"): " = BLD",
    ("ss_mapping", "ssgens"): " = 𝐼",
    ("ss_mapping", "ssprimes"): " = null⁻¹(BL·null(𝑀))",
    ("ss_mapping", "primes"): " = 𝑀LBL",
    ("ss_mapping", "targets"): " = 𝑀ₛ→LT",
    ("mapping", "commas"): " = 𝑂",
    ("vectors", "primes"): " = 𝐼",       # M_j = I
    ("mapping", "gens"): " = 𝐼",         # MG = I
    ("mapping", "detempering"): " = 𝐼",  # MD = I
    ("mapping", "targets"): " = 𝑀T",
    # the rational tempering projection and generator embedding. G and V are bases (upright), P and M
    # operators (italic). The canonical-form decompositions (𝐺CᴹC / GCF⁻¹) wait for the form feature;
    # the superspace tail on P (" = Gₛ→ₗ𝑀ₛ→ₗ") is appended per-render in build() only when show_superspace.
    ("projection", "primes"): " = G𝑀 = V·diag(𝝀)V⁻¹",
    ("projection", "gens"): " = U(𝑀U)⁻¹",
    # P·H = H: the held intervals are P's eigenvalue-1 directions, returned unchanged by the projection
    ("projection", "held"): " = H",
    # P_L→s = G_L→s·M_L (the superspace projection composes the embedding with the superspace mapping)
    ("projection", "ssprimes"): f" = G{SUBSCRIPT_L}→ₛ𝑀{SUBSCRIPT_L}",
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

# When the form layer is on (the "form" Show toggle), the default form is acknowledged as the
# CANONICAL one with a subscript C (SUBSCRIPT_C) on every generator-basis object, wherever it
# appears as a symbol or inside a defining equation. The objects are the mapping 𝑀, the generator
# tuning map 𝒈 and the projection's generator embedding G — each depends on the choice of generator
# basis (the form), so the subscript marks "this is in canonical form". The form-INVARIANT objects
# (the prime tuning maps 𝒕/𝒋/𝒓, the interval bases C/T/H, the detempering D) carry no form, so they
# stay bare. The symbol side is a cell SET (the subscript is inserted after the leading glyph at
# render time, so it composes with the unchanged-intervals C→V swap on the mapped-comma tile); the
# equivalence side is an explicit overlay, applied OVER EQUIVALENCES in build's caption loop.
# Applied by ROW, not per tile, so EVERY tile of a form-dependent row inherits it — a new mapped
# product (𝑀G mapped generators, 𝑀D mapped generator detemperings, …) needs no registration. The
# whole mapping row is 𝑀-and-its-products; plus the two lone generator-basis cells in other rows
# (the generator tuning map 𝒈, the projection embedding G). The canonical-mapping row is NOT here:
# it is statically the canonical form (its SYMBOLS bake in the subscript), shown only when surfaced.
FORM_SUBSCRIPT_ROWS = frozenset({"mapping"})
FORM_SUBSCRIPT_GENS = frozenset({("tuning", "gens"), ("projection", "gens")})
FORM_EQUIVALENCES = {
    ("mapping", "targets"):    f" = 𝑀{SUBSCRIPT_C}T",
    ("tuning", "detempering"): f" = 𝒈{SUBSCRIPT_C}",          # 𝒕D = the generator tuning map
    ("tuning", "primes"):      f" = 𝒈{SUBSCRIPT_C}𝑀{SUBSCRIPT_C}",
    ("projection", "primes"):  f" = G{SUBSCRIPT_C}𝑀{SUBSCRIPT_C} = V·diag(𝝀)V⁻¹",
    ("projection", "gens"):    f" = U(𝑀{SUBSCRIPT_C}U)⁻¹",
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
    # the projected unrotated vector list P·V — prime-count vectors, like the interval-vectors V it
    # projects (P maps each just prime back to a prime-count vector, hence p, not the mapping's g)
    ("projection", "commas"): "p",
    # P = GM maps prime-count vectors to prime-count vectors (p/p); G embeds the generators as
    # prime-count vectors (p/g, the mapping's reciprocal)
    ("projection", "primes"): "p/p",
    # the superspace projection tiles: G_L→s embeds the superspace generators in domain primes (p/g_L),
    # P_L→s projects superspace basis elements to domain primes (p/b — per the mockup)
    ("projection", "ssgens"): f"p/g{SUBSCRIPT_L}",
    ("projection", "ssprimes"): "p/b",
    ("projection", "gens"): "p/g",
    # the projected vector lists are prime-count vectors (p), like the interval-vectors lists they project
    ("projection", "detempering"): "p",
    ("projection", "targets"): "p",
    ("projection", "held"): "p",
    ("projection", "interest"): "p",
    ("vectors", "targets"): "p",
    ("vectors", "held"): "p",
    ("vectors", "detempering"): "p",
    ("vectors", "interest"): "p",
    # the chapter-9 green superspace tiles run over TRUE primes — the superspace is prime-only
    # by construction — so their coordinate is p, NOT the on-domain basis element b, even when
    # the domain itself is nonstandard (the whole point of the superspace: it re-expresses a
    # nonprime domain b over genuine primes p). Its generators are the superspace generators gL
    # (distinct from the on-domain g). So B_L embeds the d domain elements in dL superspace-prime
    # coordinates (p), M_L is gL/p (one superspace generator per superspace prime), M_jL is p/p
    # (identity). The p → b on-domain swap (see cell_unit) does NOT reach these tiles.
    # B_L (basis change matrix) and M_s→L are the two tiles that bridge the two spaces, so they
    # carry BOTH coordinates: B_L is p/b (each domain element b expressed as superspace-prime p
    # components), M_s→L is gL/b (each domain element b mapped to superspace generators gL) — both
    # in output/input order, the superspace coordinate (p, gL) leading. Every other
    # superspace tile lives wholly in the superspace (p / gL only). The gL token uses the
    # SUBSCRIPT_L markup so cell_unit can subscript it per generator.
    ("ss_vectors", "ssprimes"): "p/p",   # M_jL = I
    ("vectors", "primes"): "p/p",            # 𝑀ⱼ = 𝐼
    ("mapping", "gens"): "g/g",              # 𝑀𝐺 = 𝐼
    ("mapping", "detempering"): "g",         # 𝑀D = 𝐼
    ("ss_vectors", "primes"): "p/b",      # B_L basis change matrix (superspace prime p per domain element b)
    ("ss_vectors", "commas"): "p",        # C_L
    ("ss_vectors", "held"): "p",          # H_L
    ("ss_vectors", "targets"): "p",       # T_L
    ("ss_vectors", "interest"): "p",
    ("ss_vectors", "detempering"): "p",   # D_L
    ("ss_mapping", "ssgens"): f"g{SUBSCRIPT_L}/g{SUBSCRIPT_L}",  # M_LgL = I
    ("ss_mapping", "ssprimes"): f"g{SUBSCRIPT_L}/p",   # M_L
    ("ss_mapping", "primes"): f"g{SUBSCRIPT_L}/b",     # M_s→L
    ("ss_mapping", "commas"): f"g{SUBSCRIPT_L}",
    ("ss_mapping", "held"): f"g{SUBSCRIPT_L}",
    ("ss_mapping", "targets"): f"g{SUBSCRIPT_L}",      # Y_L
    ("ss_mapping", "interest"): f"g{SUBSCRIPT_L}",
    ("ss_mapping", "detempering"): f"g{SUBSCRIPT_L}",
    # P_L is a basis-element → basis-element operator (the projected superspace basis), so b/b — NOT
    # the gL/p or p/p of M_L / M_jL (the mockup labels its rows bᵢ; its spine α, β, γ … are
    # placeholders for the superspace primes the row's quantities spine actually lists)
    ("ss_projection", "ssprimes"): "b/b",
    # the rest of the superspace projection row's tiles (the mockup): the embedding G_L is b/gL, the
    # projected subspace basis P_L·B_Ls is b/p, and every projected lifted list is b (a basis vector)
    ("ss_projection", "ssgens"): f"b/g{SUBSCRIPT_L}",
    ("ss_projection", "primes"): "b/p",
    ("ss_projection", "detempering"): "b",
    ("ss_projection", "commas"): "b",
    ("ss_projection", "targets"): "b",
    ("ss_projection", "held"): "b",
    ("ss_projection", "interest"): "b",
    # the cyan superspace tuning row mirrors the on-domain tuning row over the superspace
    # primes (p, true primes); 𝒈ₗ is ¢ per superspace generator gL.
    ("tuning", "ssgens"): f"¢/g{SUBSCRIPT_L}",
    ("tuning", "ssprimes"): "¢/p",
    ("just", "ssprimes"): "¢/p",
    ("retune", "ssprimes"): "¢/p",
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
    ("prescaling", "ssprimes"): "oct/p",  # the (superspace) prescaler, per true prime
    ("prescaling", "commas"): "oct",
    ("prescaling", "detempering"): "oct",
    ("prescaling", "targets"): "oct",
    ("prescaling", "interest"): "oct",
    ("complexity", "primes"): "(C)/p",
    ("complexity", "ssprimes"): "(C)/p",  # the superspace prime complexity map
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
    # the standard-domain identity objects, gated on identity_objects (dropped from declared_tiles
    # when the toggle is off, like the superspace pair). MD = I rides detempering_tiles instead.
    ("block:vec:primes", "vectors", "primes"),      # 𝑀ⱼ = 𝐼 (JI mapping)
    ("block:selfmap", "mapping", "gens"),           # 𝑀𝐺 = 𝐼 (mapping over its own generators)
    ("block:projection", "projection", "primes"),
    ("block:projection_embedding", "projection", "gens"),  # the generator embedding G, beside P
    ("block:proj_v", "projection", "commas"),  # the projected unrotated vector list P·V over V
    ("block:scaling_factors", "scaling_factors", "commas"),  # the λ list over V (projection on)
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

# The chapter-9 superspace block's content tiles (the mockup's green region). Like
# OPTIMIZATION_COUNTS_TILES / DETEMPERING_COUNTS_TILES these are gated on their rows /
# columns being present (i.e. on the nonstandard_domain Show toggle), so they sit
# unconditionally in the registry; tile_open / panel() early-return whenever the toggle
# is off and the bands are missing. These now render real cells: the superspace generators /
# primes quantities, B_L over the domain primes, M_L over ssprimes, and 𝒈L / 𝒕L / 𝒋L / 𝒓L
# over the superspace columns.
SUPERSPACE_TILES = (
    # the column-header quantities, the dual of the spine basis index: the rL superspace
    # generators as ~ratios (𝒈L's detempering) and the dL superspace primes — the chapter-9
    # counterparts of the (quantities, gens) / (quantities, primes) tiles. Read-only: the
    # superspace basis is derived from the domain, so there are no ± controls (unlike gens/primes).
    ("block:ss_quantities:ssgens", "quantities", "ssgens"),        # the rL superspace generators as ~ratios
    ("block:ss_quantities:ssprimes", "quantities", "ssprimes"),    # the dL superspace primes (2, 3, 5, 13 …)
    ("block:ss_vectors:quantities", "ss_vectors", "quantities"),  # the spine basis index column (the dL superspace primes)
    ("block:ss_vectors:ssprimes", "ss_vectors", "ssprimes"),       # M_jL = I (dL × dL superspace JI mapping)
    ("block:ss_vectors:primes", "ss_vectors", "primes"),           # B_L: each domain element as a dL-tall superspace vector (basis change matrix)
    ("block:ss_vectors:commas", "ss_vectors", "commas"),           # C_L: the commas as superspace vectors
    ("block:ss_vectors:held", "ss_vectors", "held"),               # H_L: the held intervals as superspace vectors
    ("block:ss_vectors:targets", "ss_vectors", "targets"),         # T_L: the target list as superspace vectors
    ("block:ss_vectors:interest", "ss_vectors", "interest"),       # the intervals of interest as superspace vectors
    ("block:ss_vectors:detempering", "ss_vectors", "detempering"), # D_L: the generator detempering as superspace vectors
    ("block:ss_mapping:quantities", "ss_mapping", "quantities"),   # the spine: the rL superspace generators as ~ratios
    ("block:ss_mapping:ssgens", "ss_mapping", "ssgens"),           # M_LgL = I: the superspace mapping over its own generators
    ("block:ss_mapping:ssprimes", "ss_mapping", "ssprimes"),       # M_L itself, the rL × dL mapping
    ("block:ss_mapping:primes", "ss_mapping", "primes"),           # M_s→L: domain intervals mapped straight to superspace generators
    ("block:ss_mapping:commas", "ss_mapping", "commas"),           # mapped commas (vanish to 0)
    ("block:ss_mapping:held", "ss_mapping", "held"),               # held mapped into superspace generators
    ("block:ss_mapping:targets", "ss_mapping", "targets"),         # Y_L: targets mapped into superspace generators
    ("block:ss_mapping:interest", "ss_mapping", "interest"),       # intervals of interest mapped into superspace generators
    ("block:ss_mapping:detempering", "ss_mapping", "detempering"), # detempering mapped into superspace generators
    # the superspace tempering projection P_L = G_L·M_L (gated on the projection toggle via its row band):
    # the dL × dL operator over the superspace primes, plus its quantities spine (the dL superspace primes)
    ("block:ss_projection:ssprimes", "ss_projection", "ssprimes"),     # P_L itself, the dL × dL projection
    ("block:ss_projection:quantities", "ss_projection", "quantities"), # the spine: the dL superspace primes
    ("block:tuning:ssgens", "tuning", "ssgens"),                   # 𝒈L (Phase 4F)
    ("block:tuning:ssprimes", "tuning", "ssprimes"),               # 𝒕L (Phase 4F)
    ("block:just:ssprimes", "just", "ssprimes"),                   # 𝒋L (Phase 4F)
    ("block:retune:ssprimes", "retune", "ssprimes"),               # 𝒓L (Phase 4F)
    # the chapter-9 prescaler shift: the bare 𝐿 and the prime complexity map move into the
    # ss-primes column when the superspace appears (neutral / prime-based). tile_open still gates
    # them on the prescaling/complexity rows being present (complexity weighting on), so a
    # unity-weighted scheme shows neither — just like the domain-primes prescaler tiles.
    ("block:prescaling:ssprimes", "prescaling", "ssprimes"),       # the (superspace) complexity prescaler 𝐿
    ("block:complexity:ssprimes", "complexity", "ssprimes"),       # the domain prime complexity map ‖𝐿[i]‖q
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
    # the chapter-9 superspace units (gated on nonstandard_domain too — both row and column
    # bands must be present): the units COLUMN over the superspace rows (B_L / M_L / M_jL in
    # pᵢ/ and gLᵢ/) and the units ROW over the superspace columns (/gLᵢ over ssgens, /pᵢ over
    # ssprimes — true primes p, not the on-domain b)
    ("block:ucol:ss_vectors", "ss_vectors", "units"),
    ("block:ucol:ss_mapping", "ss_mapping", "units"),
    ("block:ucol:ss_projection", "ss_projection", "units"),   # P_L's rows are bᵢ/ (b/b operator)
    ("block:urow:ssgens", "units", "ssgens"),
    ("block:urow:ssprimes", "units", "ssprimes"),
)

# The plain-text tiles whose string is an editable input that drives the grid —
# the duals the grid itself lets you type into: the mapping (mapping/primes), the comma
# basis (vectors/commas), the generator tuning map (tuning/gens), the target interval list
# (vectors/targets), and the bare prescaler 𝐿's diagonal (prescaling/primes — the matrix
# form parses to a d-tuple via service.parse_prescaler_diagonal). Every other plain-text
# value is a computed read-only display.
EDITABLE_PTEXT = frozenset({("mapping", "primes"), ("vectors", "commas"), ("tuning", "gens"),
                            ("vectors", "targets"), ("prescaling", "primes"),
                            # P and G aren't per-cell editable (a single entry can't keep P
                            # idempotent / 𝑀𝐺 = 𝐼), so the whole-matrix EBK string is the only edit path
                            ("projection", "primes"), ("projection", "gens")})
EDITABLE_PTEXT_ROWS = frozenset(r for r, _ in EDITABLE_PTEXT)  # rows whose band holds an input
# Rows that carry a plain-text band (every value row; the counts row has none). The
# quantities row's band holds only the domain-primes basis string ("2.3.5"); its interval-
# ratio columns show no plain text (the gridded ratio is already the formatted value). Every
# other row shows one EBK string per tile.
PTEXT_ROWS = frozenset({"quantities", "vectors", "mapping", "tuning", "just", "retune", "damage",
                        "prescaling", "complexity", "weight",
                        # the projection row (P·V) and the scaling-factors row (λ) each carry a
                        # plain-text EBK string over the consolidated V column; reserving the bands
                        # keeps the text from spilling into the row below
                        "projection", "scaling_factors",
                        # the chapter-9 superspace matrices carry a plain-text EBK string too
                        # (B_L, M_L, M_jL, and the superspace projection P_L); listing them reserves
                        # the band height so the text doesn't spill past the tile into the row below
                        "ss_vectors", "ss_mapping", "ss_projection"})

# Cell kinds the value-display toggles filter out. "gridded values" hides
# everything a tile holds besides its fold toggle, name caption and plain-text
# value box: the value numbers (including the just row's "mathexpr" log₂ form),
# the EBK marks framing them, and the domain/comma ± controls. (Gridded off with
# plain text on leaves just the inline string — the two value views are independent.)
GRIDDED_KINDS = frozenset({
    "prime", "ratiocell", "commaratio", "genratio", "mapping", "mapped", "commacell",
    "vec", "tuningvalue", "mathexpr", "interestcell", "formcell", "heldcell", "gentuningcell", "targetcell",
    "prescalercell",
    # the nonstandard-domain (box-on) editable twins of the read-only value cells above: the
    # domain basis element cells (quantities row "prime:*" + spine "basis:*", standing in for
    # "prime") and the editable unchanged basis U (standing in for "vec"). Filtered alongside
    # their read-only forms so a typed domain / consolidated-V view collapses with everything else.
    "elementcell", "elementratio", "unchangedcell",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "ebkbot", "transpose", "vbar", "matlabel",
    "minus", "plus", "gen_minus", "gen_plus", "map_minus", "map_plus", "comma_minus", "comma_plus", "basis_minus",
    # the nonstandard-domain (box-on) twins of the domain ± walk controls (minus/plus/basis_minus):
    # a per-element − on every element and the typed-element + on both axes
    "element_minus", "element_plus",
    "interest_minus", "interest_plus", "held_minus", "held_plus", "target_minus", "target_plus",
    "colgrip",  # the drag-and-drop reorder grip on each interval column's fan branch
    "boxtitle", "powerinput", "powerdisplay",  # both power-value faces (editable input / locked value)
})
# "quantities" (general) is gentler than gridded values: it keeps every cell box
# AND the EBK marks framing them, and only *blanks the numbers* of EVERY value cell --
# the matrix, mapped list, comma basis, generator ratios, tuning cents, the static /
# plain-text-vector / other-interval value cells, AND the quantities row + spine column
# (the domain primes / nonstandard elements / interval-ratio headers) and the unrotated
# vector list's editable unchanged cells -- so only the bare gridded structure remains.
# (Superspace mirrors the main block with the same kinds, so its quantities blank too;
# the just row's "mathexpr" log₂ form is not a bare number, so math_expressions' own
# show_value logic trims it.)
BLANKED_NUMBER_KINDS = frozenset({
    "genratio", "mapping", "mapped", "commacell", "vec", "tuningvalue", "interestcell", "formcell", "heldcell",
    "gentuningcell", "targetcell", "prescalercell",
    # the quantities row + spine column and the unrotated vector list: the domain primes
    # ("prime"), the nonstandard-domain element cells ("elementcell"/"elementratio"), the
    # interval-ratio headers ("ratiocell") and the unchanged/detempering ratios
    # ("commaratio"), and the editable unchanged basis ("unchangedcell"). The generator
    # ratios ("genratio") and read-only comma/unchanged vectors ("commacell"/"vec") above
    # already covered the rest of those regions.
    "prime", "elementcell", "elementratio", "ratiocell", "commaratio", "unchangedcell",
})

# The cell kinds the edit-preview ring may flag — the value-bearing cells the user reads a computed
# or edited NUMBER / RATIO off. The preview highlights what an action MOVES, so it skips the
# scaffolding around those values: the EBK marks (brackets/braces) and the column separators (which
# read as subgridline branches), the per-column controls (drag grips, +/- buttons), and the labels
# / charts. None of those carries a value, so a reshape that adds or alters them would only ring as
# noise. (powerdisplay is the locked optimization power's read-only value; charts are excluded — the
# inset ring is built for discrete value cells, not a plot.)
RINGABLE_KINDS = BLANKED_NUMBER_KINDS | frozenset({
    # the value faces quantities-off does NOT blank but the ring still flags: the just row's
    # closed-form "mathexpr" and the locked optimization power "powerdisplay". (prime / ratiocell /
    # commaratio and the editable element / unchanged cells are now in BLANKED_NUMBER_KINDS above.)
    "mathexpr", "powerdisplay",
})

# The editable interval-data cell kinds the user directly OWNS: the temperament's mapping rows and
# the domain elements, plus the target / held / interest interval lists (entered as ratios in the
# quantities row or as vectors in the interval-vectors grid). When a chooser pick would DROP one of
# these, the hover-preview reddens it in place so the user SEES the interval go away (a target-set
# family that drops targets, a projection that makes every target unchanged). A pick that drops only
# DERIVED, read-only display cells (the canonical-form box and its F matrix when the matrix adopts
# canonical form, a prescaling tile a scheme hides) is NOT data loss, so the hover reflows instead —
# the changed cells then show their new values. This is the narrow subset of RINGABLE_KINDS whose
# disappearance gates the redden-vs-reflow fork; the read-only outputs (mapped / tuningvalue / vec /
# genratio / commaratio / formcell / prescalercell / gentuningcell / …) are deliberately excluded.
INTERVAL_DATA_KINDS = frozenset({
    "mapping", "commacell", "unchangedcell", "interestcell", "heldcell", "targetcell",
    "ratiocell", "elementcell", "elementratio",
})
