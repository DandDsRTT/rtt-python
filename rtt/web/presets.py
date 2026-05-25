"""Curated preset lists for the three "preselect" dropdowns.

Each is a small, hand-picked menu the UI offers as a quick way to set one of the
three things you actually *choose* (the rest of the grid is derived):

* :data:`TEMPERAMENTS` — named rank-2 temperaments, given by their defining comma
  (a monzo over 2.3.5). Loaded via :func:`rtt.web.service.from_comma_basis`, so
  the mapping is the canonical dual. Sign of the comma is irrelevant (it spans
  the same nullspace either way).
* :data:`TUNING_SCHEMES` — historical tuning-scheme names understood by the
  tuning optimizer (see :data:`rtt.tuning._ORIGINAL_NAME_SCHEMES`).
* :data:`TARGET_SETS` — target interval set specs the service can resolve against
  the current domain (see :func:`rtt.web.service.target_interval_set`).

These are deliberately short starter menus; the design intends a fuller curated
list later.
"""

from __future__ import annotations

# name -> defining comma basis (5-limit monzos). Single comma => rank 2 over 2.3.5.
TEMPERAMENTS: tuple[tuple[str, tuple[tuple[int, ...], ...]], ...] = (
    ("Meantone", ((-4, 4, -1),)),  # 81/80
    ("Porcupine", ((1, -5, 3),)),  # 250/243
    ("Augmented", ((7, 0, -3),)),  # 128/125
    ("Diminished", ((3, 4, -4),)),  # 648/625
    ("Blackwood", ((8, -5, 0),)),  # 256/243
    ("Mavila", ((-7, 3, 1),)),  # 135/128
    ("Magic", ((-10, -1, 5),)),  # 3125/3072
    ("Hanson", ((-6, -5, 6),)),  # 15625/15552
    ("Tetracot", ((5, -9, 4),)),  # 20000/19683
    ("Helmholtz", ((-15, 8, 1),)),  # 32805/32768
    ("Würschmidt", ((17, 1, -8),)),  # 393216/390625
)

TUNING_SCHEMES: tuple[str, ...] = (
    "TOP", "TE", "CTE", "POTE", "POTOP", "Frobenius", "BOP", "Weil",
)

TARGET_SETS: tuple[str, ...] = ("TILT", "OLD")
