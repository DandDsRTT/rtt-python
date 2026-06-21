from __future__ import annotations

import math

import numpy as np
import sympy as sp

from rtt.library.canonicalization import canonical_ma
from rtt.library.matrix_utils import Matrix


def standard_jip_octaves(dimensionality: int) -> tuple[float, ...]:
    return tuple(math.log2(int(sp.prime(i + 1))) for i in range(dimensionality))


def _generator_sizes_cents(matrix: Matrix, jip_octaves) -> list[float]:
    m = np.array(matrix, dtype=float)
    jip = np.array(jip_octaves, dtype=float)
    weights = np.diag(1.0 / jip)
    weighted_g = weights @ np.linalg.pinv(m @ weights)
    return list(1200.0 * (jip @ weighted_g))


def _fix_mingen_pair(rows: list[list[int]], i: int, jip_octaves) -> None:
    while True:
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        p, g = sizes[i], sizes[i + 1]
        rp, rg = rows[i], rows[i + 1]
        if g < -p:
            rows[i] = [a - 2 * b for a, b in zip(rp, rg, strict=False)]
        elif g < -p / 2:
            rows[i] = [a - b for a, b in zip(rp, rg, strict=False)]
            return
        elif g < 0:
            rows[i + 1] = [-b for b in rg]
            return
        elif g <= p / 2:
            return
        elif g <= p:
            rows[i] = [a + b for a, b in zip(rp, rg, strict=False)]
            rows[i + 1] = [-b for b in rg]
            return
        else:
            rows[i] = [a + 2 * b for a, b in zip(rp, rg, strict=False)]
            rows[i + 1] = [-b for b in rg]


def _equave_reduce_pair(rows: list[list[int]], i: int, jip_octaves) -> None:
    for _ in range(1000):
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        p, g = sizes[i], sizes[i + 1]
        rp, rg = rows[i], rows[i + 1]
        if g >= p:
            rows[i] = [a + b for a, b in zip(rp, rg, strict=False)]
        elif g < 0:
            rows[i] = [a - b for a, b in zip(rp, rg, strict=False)]
        else:
            return


def _as_matrix(rows: list[list[int]]) -> Matrix:
    return tuple(tuple(int(round(x)) for x in r) for r in rows)


def minimal_generator_ma(matrix: Matrix, jip_octaves) -> Matrix:
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        _fix_mingen_pair(rows, i, jip_octaves)
    return _as_matrix(rows)


def equave_reduced_ma(matrix: Matrix, jip_octaves) -> Matrix:
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        _equave_reduce_pair(rows, i, jip_octaves)
    return _as_matrix(rows)


def positive_generator_ma(matrix: Matrix, jip_octaves) -> Matrix:
    rows = [list(r) for r in canonical_ma(matrix)]
    for i in range(len(rows) - 1):
        sizes = _generator_sizes_cents([tuple(r) for r in rows], jip_octaves)
        if sizes[i + 1] < 0:
            rows[i + 1] = [-b for b in rows[i + 1]]
    return _as_matrix(rows)


def _fx_generator_sizes_octaves(rows: list[list[int]], jip_octaves) -> np.ndarray:
    m = np.array(rows, dtype=float)
    jip = np.array(jip_octaves, dtype=float)
    cols = [next(j for j, v in enumerate(r) if v != 0) for r in rows]
    return jip[cols] @ np.linalg.inv(m[:, cols])


def positive_generator_shift_ma(matrix: Matrix, jip_octaves) -> Matrix:
    rows = [list(r) for r in canonical_ma(matrix)]
    gen = _fx_generator_sizes_octaves(rows, jip_octaves)
    jip = np.array(jip_octaves, dtype=float)
    ploid = rows[0][0]
    for i in range(1, len(rows)):
        if gen[i] >= 0:
            continue
        cot = next(b for b in rows[i] if b != 0)
        whole_periods_in_gen = int(cot * gen[i] // gen[0])
        whole_periods_in_prime = int((jip[i] % jip[0]) // gen[0])
        shear = (whole_periods_in_gen - whole_periods_in_prime) % cot
        if shear == cot - ploid:
            rows[i] = [-b for b in rows[i]]
        else:
            k = int(gen[i] // gen[0])
            rows[0] = [a + b * k for a, b in zip(rows[0], rows[i], strict=False)]
    return _as_matrix(rows)
