from __future__ import annotations

import itertools

import numpy as np

from rtt.library.canonicalization import canonical_ca
from rtt.library.matrix_utils import Matrix, all_zeros


def _pitch(comma, jip_octaves) -> float:
    return sum(c * j for c, j in zip(comma, jip_octaves, strict=False))


def _complexity(comma, jip_octaves) -> float:
    return sum(abs(c) * j for c, j in zip(comma, jip_octaves, strict=False))


def _prime_limit(comma) -> int:
    return max((i for i, c in enumerate(comma) if c), default=-1)


def _as_matrix(rows) -> Matrix:
    return tuple(tuple(int(round(x)) for x in r) for r in rows)


def positive_ratio_ca(matrix: Matrix, jip_octaves) -> Matrix:
    commas = [list(c) for c in canonical_ca(matrix)]
    for i, comma in enumerate(commas):
        if _pitch(comma, jip_octaves) < 0:
            commas[i] = [-x for x in comma]
    return _as_matrix(commas)


def _weighted_dot(u, v, w) -> float:
    return sum((wi * wi) * ui * vi for ui, vi, wi in zip(u, v, w, strict=False))


def _gram_schmidt(basis, w):
    bstar: list[list[float]] = []
    mu = [[0.0] * len(basis) for _ in basis]
    for i, b in enumerate(basis):
        vec = [float(x) for x in b]
        for j in range(i):
            mu[i][j] = _weighted_dot(b, bstar[j], w) / _weighted_dot(bstar[j], bstar[j], w)
            vec = [v - mu[i][j] * s for v, s in zip(vec, bstar[j], strict=False)]
        bstar.append(vec)
    return bstar, mu


def _lll_reduce(basis, w, delta: float = 0.75):
    basis = [list(b) for b in basis]
    n = len(basis)
    bstar, mu = _gram_schmidt(basis, w)
    k = 1
    while k < n:
        for j in range(k - 1, -1, -1):
            if abs(mu[k][j]) > 0.5:
                q = round(mu[k][j])
                basis[k] = [a - q * b for a, b in zip(basis[k], basis[j], strict=False)]
                bstar, mu = _gram_schmidt(basis, w)
        lhs = _weighted_dot(bstar[k], bstar[k], w)
        rhs = (delta - mu[k][k - 1] ** 2) * _weighted_dot(bstar[k - 1], bstar[k - 1], w)
        if lhs >= rhs:
            k += 1
        else:
            basis[k], basis[k - 1] = basis[k - 1], basis[k]
            bstar, mu = _gram_schmidt(basis, w)
            k = max(k - 1, 1)
    return basis


def _positive_and_order(commas, jip_octaves):
    commas = [[-x for x in c] if _pitch(c, jip_octaves) < 0 else list(c) for c in commas]
    commas.sort(key=lambda c: (_prime_limit(c), _complexity(c, jip_octaves), tuple(c)))
    return commas


def _enum_bound(rank: int, limit: int = 20000) -> int:
    return 2 if (2 * 2 + 1) ** rank <= limit else 1


def minimal_ca(matrix: Matrix, jip_octaves) -> Matrix:
    commas = [list(c) for c in canonical_ca(matrix)]
    if not commas or all_zeros(commas):
        return _as_matrix(commas)
    seed = _lll_reduce(commas, jip_octaves)
    rank, dim = len(seed), len(seed[0])

    k = _enum_bound(rank)
    candidates = []
    for coeffs in itertools.product(range(-k, k + 1), repeat=rank):
        if any(coeffs):
            vec = [sum(c * seed[r][d] for r, c in enumerate(coeffs)) for d in range(dim)]
            candidates.append(vec)
    candidates.sort(key=lambda c: _complexity(c, jip_octaves))

    picked: list[list[int]] = []
    for vec in candidates:
        if len(picked) == rank:
            break
        if np.linalg.matrix_rank(np.array([*picked, vec])) > len(picked):
            picked.append(vec)

    chosen = (
        picked
        if len(picked) == rank
        and canonical_ca(_as_matrix(picked)) == tuple(tuple(c) for c in commas)
        else seed
    )
    return _as_matrix(_positive_and_order(chosen, jip_octaves))
