from __future__ import annotations

from fractions import Fraction
from functools import lru_cache

import sympy as sp


@lru_cache(maxsize=64)
def get_primes(count: int) -> tuple[int, ...]:
    """The first ``count`` primes, e.g. ``get_primes(5) == (2, 3, 5, 7, 11)``."""
    return tuple(int(sp.prime(i)) for i in range(1, count + 1))


def quotient_to_pcv(quotient: Fraction | int) -> tuple[int, ...]:
    """Quotient to prime-count vector over the first N primes. Memoized: the spreadsheet
    re-factors the same target/comma/held ratios many times per build, and sympy's
    factorint is the cost."""
    return _quotient_to_pcv_cached(Fraction(quotient))


@lru_cache(maxsize=4096)
def _quotient_to_pcv_cached(q: Fraction) -> tuple[int, ...]:
    if q == 0:
        return (0,)
    exponents: dict[int, int] = {}
    for prime, power in sp.factorint(q.numerator).items():
        exponents[int(prime)] = exponents.get(int(prime), 0) + power
    for prime, power in sp.factorint(q.denominator).items():
        exponents[int(prime)] = exponents.get(int(prime), 0) - power
    exponents.pop(1, None)
    if not exponents:
        return (0,)
    primes = get_primes(int(sp.primepi(max(exponents))))
    return tuple(exponents.get(prime, 0) for prime in primes)


def pcv_to_quotient(pcv: tuple[int, ...]) -> Fraction:
    """Prime-count vector back to its quotient. Memoized (callers may pass any int
    sequence, so the key is normalized to a plain tuple first)."""
    return _pcv_to_quotient_cached(tuple(int(x) for x in pcv))


@lru_cache(maxsize=4096)
def _pcv_to_quotient_cached(pcv: tuple[int, ...]) -> Fraction:
    quotient = Fraction(1)
    for index, power in enumerate(pcv):
        quotient *= Fraction(int(sp.prime(index + 1))) ** power
    return quotient


def super_(quotient: Fraction | int) -> Fraction:
    """The "super" form of a quotient: its reciprocal if below 1, else itself."""
    q = Fraction(quotient)
    return 1 / q if q < 1 else q


def pad_vectors_with_zeros_up_to_d(
    matrix: tuple[tuple[int, ...], ...], d: int
) -> tuple[tuple[int, ...], ...]:
    """Right-pad each row with zeros up to length ``d``."""
    return tuple(tuple(row) + (0,) * (d - len(row)) for row in matrix)


def octave_reduce(quotient: Fraction | int) -> Fraction:
    """Multiply/divide by 2 until the quotient lands in the octave [1, 2)."""
    q = Fraction(quotient)
    while q >= 2:
        q /= 2
    while q < 1:
        q *= 2
    return q
