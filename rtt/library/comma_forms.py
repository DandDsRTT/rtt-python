"""Alternate *comma-basis normal forms* — re-expressions of a temperament's comma basis (its
kernel), the column-vector counterpart to :mod:`rtt.library.generator_forms`.

The canonical form (:func:`rtt.library.canonicalization.canonical_ca`, the antitransposed defactored
Hermite form) is the unique identifier; these are the other named forms the guide's "Normal lists"
page ("Normal forms for commas") describes:

  - **positive-ratio:** every comma made positive *in pitch* (a comma whose ratio is below unity is
    replaced by its reciprocal — in vector form, negate that comma's whole column). The antitransposed
    Hermite form only guarantees the first nonzero entry is a positive *number*, not that the comma
    points *upward*; this is the comma analogue of the mapping's positive-generator "flip". The
    guide's example: meantone's canonical [⟨4 -4 1⟩] (80/81, downward) → positive-ratio
    [⟨-4 4 -1⟩] (81/80).
  - **minimal:** the simplest comma list that still defines the temperament — the commas rated by the
    log-product (lp) complexity ``Σ|eₚ|·log2 p``, the form shown in the wiki's per-temperament "comma
    lists". This is the *shortest basis problem* (NP-hard), so it is only *approximated*, here by an
    LLL lattice reduction under the log-product-weighted inner product. The result is made positive
    in pitch and ordered by ascending prime limit. For septimal meantone the minimal form is
    [81/80, 126/125] (vs. the canonical [81/80, 57344/59049]).

A comma's *pitch* and *complexity* are read against the just tuning map in octaves — ``log2`` of each
domain element (the primes, for a standard prime-limit domain) — passed in as ``jip_octaves``, so a
form is a pure function of the comma basis and its domain.
"""

from __future__ import annotations

import itertools

import numpy as np

from rtt.library.canonicalization import canonical_ca
from rtt.library.matrix_utils import Matrix, all_zeros


def _pitch(comma, jip_octaves) -> float:
    """The comma's size in octaves (log2 of its ratio) — negative when the ratio is below unity."""
    return sum(c * j for c, j in zip(comma, jip_octaves))


def _complexity(comma, jip_octaves) -> float:
    """The comma's log-product (lp) complexity ``log2(n·d) = Σ|eₚ|·log2 p`` — the weighted L1 size
    the minimal form minimizes."""
    return sum(abs(c) * j for c, j in zip(comma, jip_octaves))


def _prime_limit(comma) -> int:
    """The index of the highest-prime entry the comma uses (its prime-limit rank), for ordering the
    minimal form by ascending prime limit."""
    return max((i for i, c in enumerate(comma) if c), default=-1)


def _as_matrix(rows) -> Matrix:
    return tuple(tuple(int(round(x)) for x in r) for r in rows)


def positive_ratio_ca(matrix: Matrix, jip_octaves) -> Matrix:
    """The positive-ratio form of a comma basis: starting from the canonical form, flip every comma
    that points downward (ratio below unity) to its reciprocal by negating its column."""
    commas = [list(c) for c in canonical_ca(matrix)]
    for i, comma in enumerate(commas):
        if _pitch(comma, jip_octaves) < 0:
            commas[i] = [-x for x in comma]
    return _as_matrix(commas)


def _weighted_dot(u, v, w) -> float:
    """The log-product-weighted inner product ``Σ (wᵢ)²·uᵢ·vᵢ`` — the squared lp size when ``u == v``,
    so LLL reduces toward lp-short commas."""
    return sum((wi * wi) * ui * vi for ui, vi, wi in zip(u, v, w))


def _gram_schmidt(basis, w):
    """Weighted Gram–Schmidt: the orthogonalized basis ``b*`` and the coefficients ``mu[i][j]``,
    both under :func:`_weighted_dot`. The integer basis itself is untouched (floats only here)."""
    bstar: list[list[float]] = []
    mu = [[0.0] * len(basis) for _ in basis]
    for i, b in enumerate(basis):
        vec = [float(x) for x in b]
        for j in range(i):
            mu[i][j] = _weighted_dot(b, bstar[j], w) / _weighted_dot(bstar[j], bstar[j], w)
            vec = [v - mu[i][j] * s for v, s in zip(vec, bstar[j])]
        bstar.append(vec)
    return bstar, mu


def _lll_reduce(basis, w, delta: float = 0.75):
    """A small LLL lattice reduction of the integer ``basis`` rows under the log-product-weighted
    inner product — the guide's "good approximation" to the (NP-hard) shortest comma basis. All
    operations on the basis are integer unimodular row moves, so the output spans the same lattice;
    only the Gram–Schmidt orthogonality test uses the weighted floats. Recomputes the (tiny)
    Gram–Schmidt after every change — the matrices here are at most a handful of rows."""
    basis = [list(b) for b in basis]
    n = len(basis)
    bstar, mu = _gram_schmidt(basis, w)
    k = 1
    while k < n:
        for j in range(k - 1, -1, -1):                       # size-reduce bₖ against the earlier rows
            if abs(mu[k][j]) > 0.5:
                q = round(mu[k][j])
                basis[k] = [a - q * b for a, b in zip(basis[k], basis[j])]
                bstar, mu = _gram_schmidt(basis, w)
        lhs = _weighted_dot(bstar[k], bstar[k], w)
        rhs = (delta - mu[k][k - 1] ** 2) * _weighted_dot(bstar[k - 1], bstar[k - 1], w)
        if lhs >= rhs:                                        # Lovász condition met: advance
            k += 1
        else:                                                 # else swap and back up one
            basis[k], basis[k - 1] = basis[k - 1], basis[k]
            bstar, mu = _gram_schmidt(basis, w)
            k = max(k - 1, 1)
    return basis


def _positive_and_order(commas, jip_octaves):
    """Make each comma positive in pitch, then order the list by ascending prime limit (then
    complexity, then lexicographically) — the shared presentation of a minimal comma list."""
    commas = [[-x for x in c] if _pitch(c, jip_octaves) < 0 else list(c) for c in commas]
    commas.sort(key=lambda c: (_prime_limit(c), _complexity(c, jip_octaves), tuple(c)))
    return commas


def _enum_bound(rank: int, limit: int = 20000) -> int:
    """The coefficient half-range ``K`` to enumerate combinations of the LLL basis over: 2 when the
    ``(2K+1)^rank`` grid stays under ``limit``, else 1 (still finds the lp-minimum in practice, since
    LLL already delivers a near-minimal seed). Keeps the search bounded for high-codimension bases."""
    return 2 if (2 * 2 + 1) ** rank <= limit else 1


def minimal_ca(matrix: Matrix, jip_octaves) -> Matrix:
    """The minimal (lp-reduced) form of a comma basis — the simplest comma list defining the same
    temperament, the form shown in the wiki's per-temperament "comma lists".

    The shortest comma basis is NP-hard, so this approximates it: LLL-reduce (a near-minimal seed),
    then enumerate the short lattice combinations of that seed and *greedily* pick the lp-shortest
    independent comma, then the next, and so on. Greedy-by-complexity finds the true lp-minimum where
    plain LLL (which minimizes the weighted L2 size, not the log-product L1 size) does not — e.g. it
    picks septimal meantone's 126/125 over the L2-shorter 225/224. The picked basis is accepted only
    if it still spans the original lattice (same canonical form); otherwise the LLL seed is kept."""
    commas = [list(c) for c in canonical_ca(matrix)]
    if not commas or all_zeros(commas):
        return _as_matrix(commas)
    seed = _lll_reduce(commas, jip_octaves)
    rank, dim = len(seed), len(seed[0])

    # every short integer combination of the LLL seed — candidate lattice vectors to pick from
    k = _enum_bound(rank)
    candidates = []
    for coeffs in itertools.product(range(-k, k + 1), repeat=rank):
        if any(coeffs):
            vec = [sum(c * seed[r][d] for r, c in enumerate(coeffs)) for d in range(dim)]
            candidates.append(vec)
    candidates.sort(key=lambda c: _complexity(c, jip_octaves))

    # greedily take the lp-shortest commas that stay linearly independent, up to full rank
    picked: list[list[int]] = []
    for vec in candidates:
        if len(picked) == rank:
            break
        if np.linalg.matrix_rank(np.array(picked + [vec])) > len(picked):
            picked.append(vec)

    # accept the greedy basis only if it still defines the same temperament (spans the same lattice)
    chosen = picked if len(picked) == rank and canonical_ca(_as_matrix(picked)) == tuple(
        tuple(c) for c in commas) else seed
    return _as_matrix(_positive_and_order(chosen, jip_octaves))
