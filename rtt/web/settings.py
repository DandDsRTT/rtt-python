"""The "Show" settings: which parts of the grid are visible.

Mirrors the mockup's Show legend (two sections of toggles). Each entry is
``(key, label, default)``; :data:`DEFAULTS` is the as-shipped state. The layout
(:mod:`rtt.web.spreadsheet`) reads a settings dict to decide what to include, so
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
"""

from __future__ import annotations

# NB: every key here also needs a hover-text entry in ``rtt.web.tooltips.SHOW_HELP`` — the
# settings panel reads it for each toggle's tooltip, and ``test_web_tooltips`` enforces the
# match (``SHOW_HELP`` == ``DEFAULTS``), so adding a toggle without its help text fails the suite.
SHOW_GROUPS: tuple[tuple[str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "general",
        (
            ("names", "names", True),
            ("mnemonics", "mnemonics", False),
            ("symbols", "symbols", False),
            ("equivalences", "equivalences", False),
            ("gridded_values", "gridded values", True),
            ("plain_text_values", "plain text values", False),
            ("charts", "charts", False),
            ("presets", "presets", False),
            ("quantities", "quantities", True),
            ("units", "units", False),
            ("math_expressions", "math expressions", False),
        ),
    ),
    (
        "specific boxes & controls",
        (
            ("counts", "counts", False),
            ("audio", "audio", False),
            ("domain_quantities", "quantities", True),
            ("domain_units", "units", False),
            ("temperament_boxes", "temperament boxes", True),
            ("temperament_colorization", "colorization", False),
            ("form_controls", "form controls", False),
            ("form_colorization", "colorization", False),
            ("tuning_boxes", "tuning boxes", True),
            ("optimization", "optimization", False),
            ("tuning_ranges", "tuning ranges", False),
            ("weighting", "weighting", False),
            ("all_interval", "all-interval", False),
            ("alt_complexity", "alt. complexity", False),
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
    "temperament_colorization": "temperament_boxes",
    "form_colorization": "form_controls",  # the magenta wash (deferred; greyed until built)
    "optimization": "tuning_boxes",
    "tuning_ranges": "tuning_boxes",
    "weighting": "tuning_boxes",
    "all_interval": "weighting",  # a control in box 𝐓 (nested under weighting)
    "alt_complexity": "weighting",  # controls in boxes 𝐋 and 𝒄
    "projection": "tuning_boxes",
    "tuning_colorization": "tuning_boxes",
}

# Toggles whose behaviour the layout actually builds today; the panel disables
# (greys out) the rest until their content exists.
IMPLEMENTED: frozenset[str] = frozenset(
    {"names", "symbols", "mnemonics", "equivalences", "gridded_values", "plain_text_values",
     "quantities", "domain_quantities", "units", "domain_units", "counts", "presets",
     "temperament_boxes", "tuning_boxes", "math_expressions", "charts", "tuning_ranges",
     "tuning_colorization", "temperament_colorization", "weighting", "audio",
     "generator_detempering", "optimization", "interest", "all_interval"}
)


def defaults() -> dict[str, bool]:
    return dict(DEFAULTS)


def depth_of(key: str) -> int:
    """How many levels ``key`` is nested under a top-level toggle (see :data:`SUBCONTROLS`):
    0 for a top-level toggle, 1 for a sub-control, 2 for a sub-sub-control. The panel indents
    each row by its depth, so a grandchild (all-interval, under weighting, under tuning boxes)
    sits further right than its parent instead of level with it."""
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
