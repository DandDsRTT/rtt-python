"""The "Show" settings: which parts of the grid are visible.

Mirrors the mockup's Show legend (two sections of toggles). Each entry is
``(key, label, default)``; :data:`DEFAULTS` is the as-shipped state. The layout
(:mod:`rtt.web.spreadsheet`) reads a settings dict to decide what to include, so
toggling a box adds/removes content (which the reconciling renderer animates).

Toggles whose behaviour is built are listed in :data:`IMPLEMENTED` and render as
interactive checkboxes; the rest are shown at their default state and greyed out
until their content exists.

A few toggles are *sub-controls* of another (see :data:`SUBCONTROLS`): the panel
indents them under their parent and only shows them while the parent is on.
``mnemonics`` refines ``names`` — it underlines each name caption's symbol letter
— so it only makes sense when names are shown. ``equivalences`` refines
``symbols`` — it shows each symbol's defining equation (𝒕 = 𝒈M) rather than the
bare glyph — so it only makes sense when symbols are shown.
"""

from __future__ import annotations

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
            ("preselects", "preselects", False),
            ("quantities", "quantities", True),
            ("units", "units", False),
            ("math_expressions", "math expressions", False),
        ),
    ),
    (
        "specific boxes & controls",
        (
            ("counts", "counts", False),
            ("domain_quantities", "quantities", True),
            ("domain_units", "units", False),
            ("temperament_boxes", "temperament boxes", True),
            ("temperament_colorization", "colorization", False),
            ("form_controls", "form controls", False),
            ("tuning_boxes", "tuning boxes", True),
            ("optimization", "optimization", False),
            ("tuning_ranges", "tuning ranges", False),
            ("weighting", "weighting", False),
            ("projection", "projection", False),
            ("tuning_colorization", "colorization", False),
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
    "optimization": "tuning_boxes",
    "tuning_ranges": "tuning_boxes",
    "weighting": "tuning_boxes",
    "projection": "tuning_boxes",
    "tuning_colorization": "tuning_boxes",
}

# Toggles whose behaviour the layout actually builds today; the panel disables
# (greys out) the rest until their content exists.
IMPLEMENTED: frozenset[str] = frozenset(
    {"names", "symbols", "mnemonics", "equivalences", "gridded_values", "plain_text_values",
     "quantities", "domain_quantities", "counts", "preselects", "temperament_boxes",
     "tuning_boxes", "math_expressions", "charts"}
)


def defaults() -> dict[str, bool]:
    return dict(DEFAULTS)
