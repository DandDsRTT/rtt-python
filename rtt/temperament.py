from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Variance(Enum):
    ROW = "row"  # covariant: mappings / covectors, written ⟨...]
    COL = "col"  # contravariant: comma bases / vectors, written [...⟩


@dataclass(frozen=True)
class Temperament:
    matrix: tuple[tuple[int, ...], ...]  # rows are the (co)vectors
    variance: Variance
    domain_basis: tuple[int, ...] | None = None  # None = standard prime-limit basis
