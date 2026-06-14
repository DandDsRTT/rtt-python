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
    positive-but-large generator below a period. The other variant, "shift", is
    :func:`positive_generator_shift_ma`."""
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        if sizes[i + 1] < 0:
            rows[i + 1] = [-b for b in rows[i + 1]]
    return _as_matrix(rows)


def _fx_generator_sizes_octaves(rows: list[list[int]], jip_octaves) -> np.ndarray:
    """Flora Canou's "fast approximate" (FX) generator map, in OCTAVES — the tuning her Temperament
    Evaluator uses for the positive-generator forms. The mapping must be canonical/HNF: for each row
    take its pivot column (its first nonzero entry), invert the r×r submatrix of those pivot columns,
    and read the generator sizes off the just map (``J[cols] · inv(M[:, cols])``). It "short-circuits
    optimization" — a property of how the temperament splits intervals — and is what the (c−p)-shear
    test in :func:`positive_generator_shift_ma` is defined against, so shift uses it rather than the
    weighted pseudoinverse the other forms size with."""
    m = np.array(rows, dtype=float)
    jip = np.array(jip_octaves, dtype=float)
    cols = [next(j for j, v in enumerate(r) if v != 0) for r in rows]  # each row's pivot column
    return jip[cols] @ np.linalg.inv(m[:, cols])


def positive_generator_shift_ma(matrix: Matrix, jip_octaves) -> Matrix:
    """The positive-generator form, the "shift" variant (per the Normal Lists page): every non-period
    generator made positive by period-SHIFTING a negative generator (adding whole periods into its
    row's period) rather than negating it — EXCEPT when the generator is ``(c − p)``-sheared, where
    ``c`` is the cot (generators to reach the prime, the row's pivot value) and ``p`` is the ploid
    (periods per equave, the period row's leading entry), in which case it falls back to the "flip"
    routine. This is the form most temperament mappings on the wiki are given in; it is often more
    musically useful, since the prime harmonics then land on positive generator counts.

    This mirrors Flora Canou's Temperament Evaluator ``form("shift")``: the sign test and the shear
    are computed against the FX tuning (:func:`_fx_generator_sizes_octaves`), once, up front."""
    rows = [list(r) for r in canonical_ma(matrix)]
    gen = _fx_generator_sizes_octaves(rows, jip_octaves)
    jip = np.array(jip_octaves, dtype=float)
    ploid = rows[0][0]                                              # periods per equave
    for i in range(1, len(rows)):
        if gen[i] >= 0:                                            # already positive: leave it
            continue
        cot = next(b for b in rows[i] if b != 0)                  # generators to reach this prime
        # shear: periods added to the equave-reduced prime to reach the generator stack, mod cot
        whole_periods_in_gen = int(cot * gen[i] // gen[0])
        whole_periods_in_prime = int((jip[i] % jip[0]) // gen[0])
        shear = (whole_periods_in_gen - whole_periods_in_prime) % cot
        if shear == cot - ploid:                                   # (c − p)-sheared → flip
            rows[i] = [-b for b in rows[i]]
        else:                                                      # otherwise shift by whole periods
            k = int(gen[i] // gen[0])
            rows[0] = [a + b * k for a, b in zip(rows[0], rows[i])]
    return _as_matrix(rows)
