"""Alternate mapping *generator forms* — re-expressions of a temperament's mapping with
differently-sized generators (the same temperament, a different generating set).

The canonical form (:func:`rtt.library.canonicalization.canonical_ma`, defactored Hermite) is
the unique identifier; these are the other named forms the guide's "Generator form manipulation"
page describes, each defined by a constraint on the generator SIZES:

  - **minimal-generator (mingen):** every non-period generator within ``(-p/2, +p/2]`` of zero
    (the smallest absolute size). The guide gives the exact algorithm (reproduced in
    :func:`_fix_mingen_pair`): walk the rows two at a time, fixing each generator against the
    period above it.
  - **equave-reduced:** every non-period generator within ``[0, p)`` (positive, below one period).
  - **positive-generator:** every non-period generator positive (negate the negatives), not
    necessarily reduced below a period.

Sizes are measured with the log-prime-simplicity-weighted least-squares generator tuning (the
weighted pseudoinverse — a quick, reasonable tuning, the guide's choice for "computational
frugality and reasonableness"), so a form is a pure function of the mapping and its domain. The
period ``p`` of each pair is the size of the earlier generator in it (the octave, for the usual
octave-period temperaments), matching the guide's algorithm.
"""

from __future__ import annotations

import math

import numpy as np
import sympy as sp

from rtt.library.canonicalization import canonical_ma
from rtt.library.matrix_utils import Matrix


def standard_jip_octaves(dimensionality: int) -> tuple[float, ...]:
    """The just tuning map in OCTAVES (log2) of the first ``dimensionality`` primes — the domain
    basis sizes a standard prime-limit mapping is read against."""
    return tuple(math.log2(int(sp.prime(i + 1))) for i in range(dimensionality))


def _generator_sizes_cents(matrix: Matrix, jip_octaves) -> list[float]:
    """Each generator's size in cents under the log-prime-simplicity-weighted least-squares
    generator tuning — the guide's ``gens[m] = cents[weightedG[m]]`` with ``weightedG = W·pinv(m·W)``,
    ``W = diag(1/jip)`` (each prime weighted by its reciprocal log size, the log-prime simplicity)."""
    m = np.array(matrix, dtype=float)
    jip = np.array(jip_octaves, dtype=float)
    weights = np.diag(1.0 / jip)                        # log-prime simplicity weights diag(1/log2 pₙ)
    weighted_g = weights @ np.linalg.pinv(m @ weights)  # d×r generator embedding
    return list(1200.0 * (jip @ weighted_g))            # r generator sizes, cents


def _fix_mingen_pair(rows: list[list[int]], i: int, jip_octaves) -> None:
    """Fix the generator in row ``i+1`` against the period in row ``i`` to within ``(-p/2, p/2]``,
    in place — the guide's ``fixM``: pick the row change for the generator's current size band,
    apply it, and repeat while the generator is still beyond ``±p`` (a far generator needs more
    than one step)."""
    while True:
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        p, g = sizes[i], sizes[i + 1]
        rp, rg = rows[i], rows[i + 1]
        if g < -p:                       # below −p: subtract two generators from the period, retry
            rows[i] = [a - 2 * b for a, b in zip(rp, rg)]
        elif g < -p / 2:                 # [−p, −p/2): subtract one, done
            rows[i] = [a - b for a, b in zip(rp, rg)]
            return
        elif g < 0:                      # [−p/2, 0): negate the generator, done
            rows[i + 1] = [-b for b in rg]
            return
        elif g <= p / 2:                 # [0, p/2]: already minimal, done
            return
        elif g <= p:                     # (p/2, p]: add one generator to the period + negate it, done
            rows[i] = [a + b for a, b in zip(rp, rg)]
            rows[i + 1] = [-b for b in rg]
            return
        else:                            # above p: add two, negate, retry
            rows[i] = [a + 2 * b for a, b in zip(rp, rg)]
            rows[i + 1] = [-b for b in rg]


def _equave_reduce_pair(rows: list[list[int]], i: int, jip_octaves) -> None:
    """Reduce the generator in row ``i+1`` into ``[0, p)`` by whole periods, in place. A period is
    moved by adjusting the PERIOD row (``rp ± rg``) — like the guide's mingen, which adjusts ``rp``
    to re-size the generator (the generators are the dual basis, so changing the period row's map
    rebalances the generator's tuning by exactly one period)."""
    for _ in range(1000):  # bounded: each step moves the generator one period toward the band
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        p, g = sizes[i], sizes[i + 1]
        rp, rg = rows[i], rows[i + 1]
        if g >= p:
            rows[i] = [a + b for a, b in zip(rp, rg)]   # period += generator (drops the generator by p)
        elif g < 0:
            rows[i] = [a - b for a, b in zip(rp, rg)]   # period -= generator (raises it by p)
        else:
            return                                       # 0 ≤ g < p


def _as_matrix(rows: list[list[int]]) -> Matrix:
    return tuple(tuple(int(round(x)) for x in r) for r in rows)


def minimal_generator_ma(matrix: Matrix, jip_octaves) -> Matrix:
    """The minimal-generator (mingen) form of a mapping: every non-period generator at its
    smallest absolute size. Starts from the canonical form, then fixes each adjacent row pair."""
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        _fix_mingen_pair(rows, i, jip_octaves)
    return _as_matrix(rows)


def equave_reduced_ma(matrix: Matrix, jip_octaves) -> Matrix:
    """The equave-reduced form: every non-period generator in ``[0, p)`` (positive, below a period)."""
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        _equave_reduce_pair(rows, i, jip_octaves)
    return _as_matrix(rows)


def positive_generator_ma(matrix: Matrix, jip_octaves) -> Matrix:
    """The positive-generator form, the "flip" variant (per the Normal Lists page): every non-period
    generator made positive by negating its row when the generator is negative — WITHOUT reducing a
    positive-but-large generator below a period. (The other variant, "shift", is a separate follow-up.)"""
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        if sizes[i + 1] < 0:
            rows[i + 1] = [-b for b in rows[i + 1]]
    return _as_matrix(rows)
