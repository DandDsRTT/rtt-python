from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Variance(Enum):
    ROW = "row"  # covariant: mappings / covectors, written ⟨...]
    COL = "col"  # contravariant: comma bases / vectors, written [...⟩

    @classmethod
    def from_string(cls, text: str) -> "Variance":
        """Map any of the library's variance synonyms to ROW or COL."""
        if text in _COL_SYNONYMS:
            return cls.COL
        if text in _ROW_SYNONYMS:
            return cls.ROW
        raise ValueError(f"Unrecognized variance: {text!r}")


# Accepted INPUT synonyms for the column (vector) variance. Beside D&D's preferred terms
# this keeps a few legacy/jargon ones SOLELY as a translation layer — so a user who types
# the old word is still understood, not because we endorse it: "monzo"/"monzos" (the
# abandoned eponym for a vector) and the abbreviations pcv/gcv. (The parallel _ROW_SYNONYMS
# likewise keeps "val"/"vals".) These are the only place "monzo" survives in the codebase;
# everywhere else uses "vector". Don't remove them unless dropping that input compatibility.
_COL_SYNONYMS = frozenset(
    {
        "vector", "vectors", "contra", "contravector", "contravectors",
        "contravariant", "v", "c", "comma", "commas", "comma basis",
        "comma-basis", "commaBasis", "comma_basis", "i", "interval", "intervals",
        "g", "generator", "generators", "pcv", "gcv", "monzo", "monzos",
        "against", "col", "cols", "column-major order", "column-major",
        "column order", "col-major order", "col-major", "col order",
    }
)

_ROW_SYNONYMS = frozenset(
    {
        "map", "maps", "co", "covector", "covectors", "covariant", "m",
        "mapping", "et", "ets", "edo", "edos", "edomapping", "edomappings",
        "val", "vals", "with", "row", "rows", "row-major order", "row-major",
        "row order",
    }
)


@dataclass(frozen=True)
class Temperament:
    matrix: tuple[tuple[int, ...], ...]  # rows are the (co)vectors
    variance: Variance
    domain_basis: tuple[int, ...] | None = None  # None = standard prime-limit basis
