"""The "Show" settings: which parts of the grid are visible.

Mirrors the mockup's Show legend (two sections of toggles). Each entry is
``(key, label, default)``; :data:`DEFAULTS` is the as-shipped state. The layout
(:mod:`rtt.web.spreadsheet`) reads a settings dict to decide what to include, so
toggling a box adds/removes content (which the reconciling renderer animates).

Only the toggles with built content are wired so far (``names``, ``counts``,
``preselects``, ``temperament_boxes``, ``tuning_boxes``, ``math_expressions``); the
rest are shown in the panel at their default state and become live as their content
is built.
"""

from __future__ import annotations

SHOW_GROUPS: tuple[tuple[str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "general",
        (
            ("names", "names", True),
            ("symbols", "symbols", False),
            ("equivalences", "equivalences", False),
            ("gridded_values", "gridded values", True),
            ("plain_text_values", "plain text values", False),
            ("charts", "charts", False),
            ("preselects", "preselects", False),
            ("mnemonics", "mnemonics", False),
            ("quantities", "quantities", True),
            ("units", "units", True),
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
            ("form_controls", "form controls", False),
            ("tuning_boxes", "tuning boxes", True),
            ("generator_detempering", "generator detempering", False),
            ("nonstandard_domain", "nonstandard domain", False),
            ("identity_objects", "identity objects", False),
        ),
    ),
)

DEFAULTS: dict[str, bool] = {
    key: default for _, items in SHOW_GROUPS for key, _, default in items
}

# Toggles whose content the layout actually builds today; the panel disables
# (greys out) the rest until their content exists.
IMPLEMENTED: frozenset[str] = frozenset(
    {"names", "counts", "preselects", "temperament_boxes", "tuning_boxes", "math_expressions"}
)


def defaults() -> dict[str, bool]:
    return dict(DEFAULTS)
