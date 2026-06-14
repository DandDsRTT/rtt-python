"""The "Show" settings: which parts of the grid are visible.

Mirrors the mockup's Show legend (two sections of toggles). Each entry is
``(key, label, default)``; :data:`DEFAULTS` is the as-shipped state. The layout
(:mod:`rtt.app.spreadsheet`) reads a settings dict to decide what to include, so
toggling a box adds/removes content (which the reconciling renderer animates).

Toggles offered as live, interactive checkboxes are listed in :data:`IMPLEMENTED`;
the rest render greyed out at their default state — usually because their content
isn't built yet, but a built feature can also be *shelved* there (held out of
:data:`IMPLEMENTED`) when it isn't ready to expose. :func:`from_persisted` pins
every greyed toggle to its default on load, so a stale saved value can't re-expose
a shelved feature.

A few toggles are *sub-controls* of another (see :data:`SUBCONTROLS`), which keeps the
two in step (applied by ``Editor.set_show``): selecting a sub-control selects the layer it
refines (:func:`ancestors_of`), and deselecting a parent deselects its sub-controls
(:func:`subcontrols_of`). In the specific-controls panel the child rows also indent under
their parent and hide while it is off. ``mnemonics`` refines ``names`` — it underlines each
name caption's symbol letter — so it only makes sense when names are shown. ``equivalences``
refines ``symbols`` — it shows each symbol's defining equation (𝒕 = 𝒈M) rather than the bare
glyph — so it only makes sense when symbols are shown.

Two top-level toggles — ``temperament`` and ``tuning`` — are *pure grouping parents*: they carry
no grid layer of their own (the layout never reads them; see :data:`GROUPING_PARENTS`), existing
only to expand/collapse the toggles grouped directly beneath them. Each group holds its tiles toggle
plus everything that used to nest under that tiles toggle, now flattened up to be its direct
children: ``temperament`` holds ``temperament_tiles`` and ``temperament_colorization``;
``tuning`` holds ``tuning_tiles``, ``optimization``, ``projection`` and ``tuning_colorization``
(``optimization`` in turn parents the optimize sub-axes — ``tuning_ranges`` and ``weighting``,
the latter parenting ``all_interval`` / ``alt_complexity`` / ``custom_weights`` — so ``projection``
reads as the peer-alternative to the whole optimization branch). They use the same sub-control
machinery as any other parent — so collapsing one turns its whole group off — they just have
nothing of their own to show.

``form`` is the third group header but NOT a pure grouping parent: like the other two it expands
its sub-controls (``form_controls``, ``form_tiles``, ``form_colorization``), but it ALSO carries a
real layer — checking it marks the default (canonical) form with a subscript C on the mapping 𝑀,
the generator tuning map 𝒈 and the generator embedding G (across their symbols and equivalences).
So ``form`` is live (in :data:`IMPLEMENTED`) and has an example sample; its three sub-controls stay
greyed until their content ships.
"""

from __future__ import annotations

# NB: every key here also needs a hover-text entry in ``rtt.app.tooltips.SHOW_HELP`` — the
# settings panel reads it for each toggle's tooltip, and ``test_web_tooltips`` enforces the
# match (``SHOW_HELP`` == ``DEFAULTS``), so adding a toggle without its help text fails the suite.
SHOW_GROUPS: tuple[tuple[str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "general",
        (
            ("names", "names", True),
            ("mnemonics", "mnemonics", False),
            ("symbols", "symbols", False),
            # the matrix row/column header labels (matlabels 𝒎₁, 𝐜₁, …) are their OWN toggle,
            # independent of the in-tile big symbol above — NOT a sub-control (no SUBCONTROLS
            # entry): either can show without the other. Both render parts of the same dummy
            # tile, so this adds no panel row; it just unbinds the two appearances.
            ("header_symbols", "row/col header symbols", False),
            ("equivalences", "equivalences", False),
            ("gridded_values", "gridded values", True),
            ("plain_text_values", "plain text values", False),
            ("charts", "charts", False),
            ("presets", "presets", False),
            ("quantities", "quantities", True),
            # the decimal fraction of every value (the ".955" beneath the "701"). A sub-control of
            # quantities: its own clickable part in the dummy tile is the .fraction under the value.
            # Off rounds every displayed value to the nearest integer, app-wide (a display setting —
            # the underlying values keep full precision, so turning it back on restores the decimals).
            ("decimals", "decimals", True),
            # EBK (Extended Bra-Ket) notation. On (default) frames every matrix/vector in its EBK
            # brackets — the angle ⟨…] of a map, the ket […⟩, the curly { of a genmap. Off replaces
            # all of it (the rendered grid marks AND the plain-text strings) with a plain matrix
            # notation: every angle/curly brace becomes a square brace, and a superscript ᵀ marks the
            # vector-based (column-vector-list) kind apart from the map-based (covector-stack) kind.
            # A DISPLAY setting, like decimals — the underlying objects are untouched.
            ("ebk", "EBK", True),
            ("units", "units", False),
            # the per-value unit beneath each gridded cell is its OWN toggle, independent of the
            # per-box "units: …" line above (the `units` key) — NOT a sub-control. Like
            # header_symbols, it just unbinds a second appearance already drawn in the dummy tile.
            ("cell_units", "per-cell units", False),
            ("math_expressions", "math expressions", False),
            # a grid affordance rather than a value-display layer, but it rides the general tile as
            # one more clickable part (its sample is a drag-handle grip); off by default.
            ("drag_to_combine", "drag to combine", False),
        ),
    ),
    (
        "specific tiles & controls",
        (
            ("counts", "counts", True),
            # the interval set rows: each interval as a ratio (the interval-ratios row + its spine
            # column) and as a column vector (the interval-vectors row). Two independent toggles —
            # the interval-vectors row used to ride ``temperament_tiles`` but now owns its own.
            ("interval_ratios", "interval ratios", True),
            ("interval_vectors", "interval vectors", True),
            ("domain_units", "units", False),
            # ``temperament`` / ``tuning`` are pure grouping parents (see the module docstring): each
            # only expands the toggles grouped directly beneath it (its tiles toggle and that tile
            # group's former children, now flattened to siblings); the layout reads the tiles, never
            # the parent. ``form`` is the exception — also a group header, but a LIVE layer (the
            # canonical-form subscript C), so default-off (opt-in) and in IMPLEMENTED.
            ("temperament", "temperament", True),
            ("temperament_tiles", "temperament tiles", True),
            ("temperament_colorization", "colorization", False),
            ("form", "form", False),
            ("form_controls", "form controls", False),
            ("form_tiles", "form tiles", False),
            ("form_colorization", "colorization", False),
            ("tuning", "tuning", True),
            ("tuning_tiles", "tuning tiles", True),
            ("optimization", "optimization", False),
            ("tuning_ranges", "tuning ranges", False),
            ("weighting", "weighting", False),
            ("all_interval", "all-interval", False),
            ("alt_complexity", "alternative complexity", False),
            ("custom_weights", "custom weights", False),
            ("projection", "projection", False),
            ("tuning_colorization", "colorization", False),
            ("interest", "other intervals\nof interest", True),
            ("generator_detempering", "generator detempering", False),
            ("nonstandard_domain", "nonstandard domain", False),
            ("identity_objects", "identity objects", False),
        ),
    ),
)

DEFAULTS: dict[str, bool] = {
    key: default for _, items in SHOW_GROUPS for key, _, default in items
}

# Sub-control -> parent: the panel indents the child under its parent and only
# shows it while the parent is on. (Each parent must precede its child in a group.)
SUBCONTROLS: dict[str, str] = {
    "mnemonics": "names",
    "equivalences": "symbols",
    # the decimal fraction refines the value: with quantities off there is no value to carry a
    # fraction, and clicking the ".955" part (decimals) pulls quantities on, like mnemonics ↔ names.
    "decimals": "quantities",
    # Each grouping parent (temperament / form / tuning) directly holds everything that used to
    # nest under its tiles toggle: the tiles toggle itself AND its former direct children are now
    # direct children of the group (siblings of the tiles toggle). So "temperament tiles" and its
    # "colorization" both sit under "temperament".
    #
    # The tuning group mirrors the guide's two ways to SPECIFY a tuning: (A) by OPTIMIZATION and
    # (B) by direct construction (a PROJECTION). So "optimization" is a content+parent — it reveals
    # its own power/damage/held region AND parents the optimize sub-axes (weighting and its
    # refinements, tuning ranges) — while "projection" sits as its peer directly under "tuning",
    # reading as the alternative to the whole optimization branch. "tuning tiles" (the resulting
    # 𝒕/𝒈 maps, shared by both modes) and "colorization" stay direct children of "tuning".
    # Weighting's three refinements are siblings: all-interval, alt. complexity, and custom weights.
    "temperament_tiles": "temperament",
    "temperament_colorization": "temperament",
    # "form" is the odd group out: not a PURE grouping parent but a live layer (it adds the
    # canonical-form subscript C — see GROUPING_PARENTS), which also holds its three sub-controls:
    # the <choose form> dropdowns, the canonical-mapping / 𝐹 tiles, and the magenta wash.
    "form_controls": "form",
    "form_tiles": "form",
    "form_colorization": "form",
    "tuning_tiles": "tuning",
    "optimization": "tuning",
    "tuning_ranges": "optimization",  # a refinement of the optimized generators (box 𝒈 ranges)
    "weighting": "optimization",      # how the optimization weights its target damage
    "all_interval": "weighting",   # the all-interval target-set mode (forces simplicity weight)
    "alt_complexity": "weighting",  # controls in boxes 𝐋 and 𝒄
    "custom_weights": "weighting",  # typed per-target weights override the slope (editable 𝒘 row)
    "projection": "tuning",
    "tuning_colorization": "tuning",
}

# Toggles whose behaviour the layout actually builds today; the panel disables
# (greys out) the rest until their content exists.
IMPLEMENTED: frozenset[str] = frozenset(
    {"drag_to_combine",
     "names", "symbols", "header_symbols", "mnemonics", "equivalences", "gridded_values",
     "plain_text_values",
     "quantities", "decimals", "ebk", "interval_ratios", "interval_vectors", "units", "cell_units", "domain_units", "counts", "presets",
     "temperament", "temperament_tiles", "tuning", "tuning_tiles",
     "math_expressions", "charts", "tuning_ranges",
     "tuning_colorization", "temperament_colorization", "weighting",
     "generator_detempering", "optimization", "interest", "all_interval", "alt_complexity",
     "custom_weights", "nonstandard_domain", "projection", "identity_objects",
     # "form" IS live: unlike the pure grouping parents it carries a real layer (the canonical-
     # form subscript C). "form_controls" is live too — the <choose form> dropdowns (canonical only,
     # for now). Its other two sub-controls (form_tiles, form_colorization) stay greyed until built.
     "form", "form_controls"}
)

# The pure grouping parents: top-level toggles that only expand the tiles toggle(s) nested under them
# and carry no grid layer of their own — the layout never reads them. So they have no example-column
# sample, and flipping one changes the grid only by cascading its children off (Editor.set_show),
# never through spreadsheet.build directly. "form" is deliberately NOT here: it groups its three
# sub-controls like temperament/tuning, but it ALSO carries a real layer (the canonical-form
# subscript C), so it gets an example and the layout reads it — see the module docstring.
GROUPING_PARENTS: frozenset[str] = frozenset({"temperament", "tuning"})


# (No mutually-exclusive Show toggles. all-interval mode and custom weights ARE mutually exclusive
# tunings — both define the weighting — but that's enforced at the BEHAVIOR level: the in-grid
# box-𝐓 all-interval checkbox (Editor.set_all_interval) drops any custom weights, and entering
# custom-weight mode is a no-op while all-interval. Keeping it OFF the Show toggles is deliberate —
# a Show toggle that disabled a sibling made 'select all' impossible, so all-interval is a two-step
# visibility toggle + in-grid checkbox, and custom weights is the lone mode toggle. Neither disables
# the other in the panel.)


# ── The guide-chapter reveal ────────────────────────────────────────────────────────────────
# The settings panel's chapter slider (see :mod:`rtt.app.app`) progressively reveals the Show
# controls as a reader advances through *Dave Keenan & Douglas Blumeyer's guide to RTT*: each
# control stays hidden until the slider reaches the chapter that control is introduced in. It is a
# pure VIEWING preference — it shows/hides the panel's controls, never the grid (the toggle values,
# and so the rendered grid, are untouched).
#
# :data:`CHAPTER` gives every toggle its home chapter (the same keys as :data:`DEFAULTS`). The
# guide runs chapters 2–9 (chapter 1, "Introductions", has no app content); :data:`CHAPTER_STAR`
# is the final "★" notch PAST the guide, which reveals the chapter-10 "Conventions…" controls and
# every control whose subject lives outside the guide (form, projection, generator detempering,
# identity objects). These numbers are a design call sourced from the mockup's blue-text chapter
# transcription — edit one to move when its control appears; nothing else needs touching.
CHAPTER_MIN = 2       # first notch — chapter 1 (Introductions) has no app content to reveal
CHAPTER_STAR = 10     # the "★" notch: chapter-10 Conventions + every outside-the-guide control
CHAPTER_DEFAULT = 4   # the slider's as-shipped position — the default-state design mockup

CHAPTER: dict[str, int] = {
    # general — the dummy tile's display layers
    "gridded_values": 2, "quantities": 2, "names": 2, "symbols": 2, "plain_text_values": 2,
    # decimals rides its parent quantities' chapter (2) so it reveals — and so stays ON — by the
    # default slider position; a later reveal would let disable_hidden_settings turn it off on load,
    # silently rounding the whole app to integers before the user ever sees the toggle.
    "decimals": 2,
    # EBK notation is introduced in chapter 2 (the first mappings are written in it), so the toggle
    # reveals — and stays ON — by the default slider position, like decimals.
    "ebk": 2,
    "math_expressions": 2, "presets": 2, "equivalences": 2,
    "header_symbols": 2,  # the matrix row/col header labels (𝒎₁, 𝐜₁, …) — a sibling of symbols
    # mnemonics is the underlinable LETTER of the name word, so it must reveal WITH names (its
    # ancestor, ch2) — a later chapter would blank a letter mid-word ("tile name" -> "tile  ame").
    "mnemonics": 2,
    "charts": 3,
    "drag_to_combine": 4,
    "units": 5, "cell_units": 5,  # the per-cell unit beneath each value — a sibling of units
    # specific tiles & controls. The pure grouping parents (temperament / tuning / form) reveal with
    # their EARLIEST child, so the group header never appears before anything it would expand to.
    "counts": 2, "temperament": 2, "temperament_tiles": 2, "temperament_colorization": 2,
    "interest": 2, "interval_ratios": 2, "interval_vectors": 2, "domain_units": 2,
    "tuning": 3, "tuning_tiles": 3, "tuning_colorization": 3,
    "optimization": 3, "tuning_ranges": 3, "weighting": 3,
    "all_interval": 7,
    "alt_complexity": 8,
    "nonstandard_domain": 9,
    # custom (manual) weights aren't covered by the guide ("there's no reason you couldn't just
    # provide manual weights per target-interval"), so they reveal at the ★ notch like the other
    # outside-the-guide controls (its weighting/optimization/tuning ancestors are all ch3).
    "custom_weights": CHAPTER_STAR,
    "form": CHAPTER_STAR, "form_controls": CHAPTER_STAR, "form_tiles": CHAPTER_STAR,
    "form_colorization": CHAPTER_STAR,
    "projection": CHAPTER_STAR, "generator_detempering": CHAPTER_STAR,
    "identity_objects": CHAPTER_STAR,
}

# The guide-article titles shown in the slider's live readout (keyed by chapter; CHAPTER_STAR is
# the ★ notch). The reveal slider runs CHAPTER_MIN..CHAPTER_STAR, so only these need names.
CHAPTER_TITLES: dict[int, str] = {
    2: "Mappings",
    3: "Tuning fundamentals",
    4: "Exploring temperaments",
    5: "Units analysis",
    6: "Tuning computation",
    7: "All-interval tuning schemes",
    8: "Alternative complexities",
    9: "Tuning in nonstandard domains",
    CHAPTER_STAR: "beyond the guide",
}


def reveal_chapter(key: str) -> int:
    """The slider chapter at which ``key``'s control first appears: the LATEST of its own
    :data:`CHAPTER` and those of all its ancestors (:func:`ancestors_of`). Taking the max keeps a
    sub-control from appearing before the layer it refines — whose row would still be hidden — so a
    revealed child never strands above a hidden parent (e.g. all-interval, ch7, waits for its parent
    weighting, ch8)."""
    return max([CHAPTER[key]] + [CHAPTER[a] for a in ancestors_of(key)])


def revealed(chapter: int) -> set[str]:
    """The set of toggle keys visible at slider position ``chapter`` — those whose
    :func:`reveal_chapter` is at or before it."""
    return {key for key in DEFAULTS if reveal_chapter(key) <= chapter}


def defaults() -> dict[str, bool]:
    return dict(DEFAULTS)


def depth_of(key: str) -> int:
    """How many levels ``key`` is nested under a top-level toggle (see :data:`SUBCONTROLS`):
    0 for a top-level toggle, rising by one per nesting level. The panel indents each row by its
    depth, so a grandchild (all-interval, under weighting, under the tuning grouping parent) sits
    further right than its parent instead of level with it."""
    depth = 0
    parent = SUBCONTROLS.get(key)
    while parent is not None:
        depth += 1
        parent = SUBCONTROLS.get(parent)
    return depth


def subcontrols_of(key: str) -> set[str]:
    """Every sub-control nested under ``key`` — its direct sub-controls and theirs,
    transitively (see :data:`SUBCONTROLS`). Deselecting a toggle deselects all of
    these so a hidden parent never strands its sub-controls' content or panel rows."""
    nested: set[str] = set()
    queue = [key]
    while queue:
        parent = queue.pop()
        for child, child_parent in SUBCONTROLS.items():
            if child_parent == parent and child not in nested:
                nested.add(child)
                queue.append(child)
    return nested


def ancestors_of(key: str) -> set[str]:
    """Every toggle ``key`` is nested under — its parent and theirs, transitively (see
    :data:`SUBCONTROLS`); the mirror of :func:`subcontrols_of`. Selecting a sub-control
    selects all of these, so a shown refinement is never stranded without the layer it
    refines (equivalences needs symbols, mnemonics needs names)."""
    chain: set[str] = set()
    parent = SUBCONTROLS.get(key)
    while parent is not None and parent not in chain:
        chain.add(parent)
        parent = SUBCONTROLS.get(parent)
    return chain


def from_persisted(stored: dict) -> dict[str, bool]:
    """A persisted Show-settings dict merged onto the defaults — but a saved value is kept
    only for a live (:data:`IMPLEMENTED`) toggle; for a greyed one its default is kept. The
    panel can't change a greyed toggle (its checkbox is disabled), so a stale ``True`` for
    one would otherwise resurrect a shelved feature on load. Pinning every greyed toggle to
    its default keeps :data:`IMPLEMENTED` the single source of truth for what the grid can
    show. Unknown keys (from a newer or older build) are dropped."""
    return {key: (stored.get(key, default) if key in IMPLEMENTED else default)
            for key, default in DEFAULTS.items()}
