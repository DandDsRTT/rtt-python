from __future__ import annotations

# No browser measures text width in-process; these per-glyph em-widths over-estimate the STIX Two Text face so a value never spills.
DEFAULT_EM = 0.59
CAPTION_EM = 0.52
CHART_LABEL_EM = 0.62
EXPR_EM = 0.5

GLYPH_EM = {
    **dict.fromkeys("0123456789", DEFAULT_EM),
    ".": 0.25,
    "-": 0.35,
    "/": 0.52,
    " ": 0.24,
    "[": 0.37,
    "]": 0.37,
    "{": 0.41,
    "}": 0.41,
    "⟨": 0.38,
    "⟩": 0.38,
    "⟪": 0.58,
    "⟫": 0.58,
    "—": 1.0,
}

EMITTABLE = frozenset(GLYPH_EM)


def em_units(text: str) -> float:
    return sum(GLYPH_EM.get(character, DEFAULT_EM) for character in text)
