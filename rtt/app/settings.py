from __future__ import annotations

SHOW_GROUPS: tuple[tuple[str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "general",
        (
            ("names", "names", True),
            ("mnemonics", "mnemonics", False),
            ("symbols", "symbols", False),
            ("header_symbols", "row/col header symbols", False),
            ("equivalences", "equivalences", False),
            ("gridded_values", "gridded values", True),
            ("plain_text_values", "plain text values", False),
            ("charts", "charts", False),
            ("presets", "presets", False),
            ("quantities", "quantities", True),
            ("decimals", "decimals", True),
            ("units", "units", False),
            ("cell_units", "per-cell units", False),
            ("math_expressions", "math expressions", False),
            ("drag_to_combine", "drag to combine", False),
        ),
    ),
    (
        "specific tiles & controls",
        (
            ("animations", "animations", True),
            ("preview_highlighting", "preview highlighting", True),
            ("tooltips", "tooltips", True),
            ("counts", "counts", True),
            ("interval_ratios", "interval ratios", True),
            ("interval_vectors", "interval vectors", True),
            ("ebk", "EBK", True),
            ("domain_units", "units", False),
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

SUBCONTROLS: dict[str, str] = {
    "mnemonics": "names",
    "equivalences": "symbols",
    "decimals": "quantities",
    "temperament_tiles": "temperament",
    "temperament_colorization": "temperament",
    "form_controls": "form",
    "form_tiles": "form",
    "form_colorization": "form",
    "tuning_tiles": "tuning",
    "optimization": "tuning",
    "tuning_ranges": "optimization",
    "weighting": "optimization",
    "all_interval": "weighting",
    "alt_complexity": "weighting",
    "custom_weights": "weighting",
    "projection": "tuning",
    "tuning_colorization": "tuning",
}

IMPLEMENTED: frozenset[str] = frozenset(
    {"animations", "preview_highlighting", "tooltips",
     "drag_to_combine",
     "names", "symbols", "header_symbols", "mnemonics", "equivalences", "gridded_values",
     "plain_text_values",
     "quantities", "decimals", "ebk", "interval_ratios", "interval_vectors", "units", "cell_units", "domain_units", "counts", "presets",
     "temperament", "temperament_tiles", "tuning", "tuning_tiles",
     "math_expressions", "charts", "tuning_ranges",
     "tuning_colorization", "temperament_colorization", "weighting",
     "generator_detempering", "optimization", "interest", "all_interval", "alt_complexity",
     "custom_weights", "nonstandard_domain", "projection", "identity_objects",
     "form", "form_controls", "form_tiles", "form_colorization"}
)

GROUPING_PARENTS: frozenset[str] = frozenset({"temperament", "tuning"})




CHAPTER_MIN = 2
CHAPTER_STAR = 10
CHAPTER_DEFAULT = 4

CHAPTER: dict[str, int] = {
    "animations": 2, "preview_highlighting": 2, "tooltips": 2,
    "gridded_values": 2, "quantities": 2, "names": 2, "symbols": 2, "plain_text_values": 2,
    "decimals": 2,
    "math_expressions": 2, "presets": 2, "equivalences": 2,
    "header_symbols": 2,
    "mnemonics": 2,
    "charts": 3,
    "drag_to_combine": 4,
    "units": 5, "cell_units": 5,
    "counts": 2, "temperament": 2, "temperament_tiles": 2, "temperament_colorization": 2,
    "interest": 2, "interval_ratios": 2, "interval_vectors": 2, "domain_units": 2,
    "ebk": 2,
    "tuning": 3, "tuning_tiles": 3, "tuning_colorization": 3,
    "optimization": 3, "tuning_ranges": 3, "weighting": 3,
    "all_interval": 7,
    "alt_complexity": 8,
    "nonstandard_domain": 9,
    "custom_weights": CHAPTER_STAR,
    "form": CHAPTER_STAR, "form_controls": CHAPTER_STAR, "form_tiles": CHAPTER_STAR,
    "form_colorization": CHAPTER_STAR,
    "projection": CHAPTER_STAR, "generator_detempering": CHAPTER_STAR,
    "identity_objects": CHAPTER_STAR,
}

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
    return max([CHAPTER[key]] + [CHAPTER[a] for a in ancestors_of(key)])


def revealed(chapter: int) -> set[str]:
    return {key for key in DEFAULTS if reveal_chapter(key) <= chapter}


def defaults() -> dict[str, bool]:
    return dict(DEFAULTS)


def depth_of(key: str) -> int:
    depth = 0
    parent = SUBCONTROLS.get(key)
    while parent is not None:
        depth += 1
        parent = SUBCONTROLS.get(parent)
    return depth


def subcontrols_of(key: str) -> set[str]:
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
    chain: set[str] = set()
    parent = SUBCONTROLS.get(key)
    while parent is not None and parent not in chain:
        chain.add(parent)
        parent = SUBCONTROLS.get(parent)
    return chain


def from_persisted(stored: dict) -> dict[str, bool]:
    return {key: (stored.get(key, default) if key in IMPLEMENTED else default)
            for key, default in DEFAULTS.items()}
