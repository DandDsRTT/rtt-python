from __future__ import annotations

from fractions import Fraction
from functools import lru_cache

import sympy as sp


@lru_cache(maxsize=64)
def get_primes(count: int) -> tuple[int, ...]:
    return tuple(int(sp.prime(i)) for i in range(1, count + 1))


def quotient_to_pcv(quotient: Fraction | int) -> tuple[int, ...]:
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
    return _pcv_to_quotient_cached(tuple(int(x) for x in pcv))


@lru_cache(maxsize=4096)
def _pcv_to_quotient_cached(pcv: tuple[int, ...]) -> Fraction:
    quotient = Fraction(1)
    for index, power in enumerate(pcv):
        quotient *= Fraction(int(sp.prime(index + 1))) ** power
    return quotient


def super_(quotient: Fraction | int) -> Fraction:
    q = Fraction(quotient)
    return 1 / q if q < 1 else q


def pad_vectors_with_zeros_up_to_d(
    matrix: tuple[tuple[int, ...], ...], d: int
) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) + (0,) * (d - len(row)) for row in matrix)


def equave_reduce(quotient: Fraction | int, equave: Fraction | int = 2) -> Fraction:
    q = Fraction(quotient)
    e = Fraction(equave)
    while q >= e:
        q /= e
    while q < 1:
        q *= e
    return q


def octave_reduce(quotient: Fraction | int) -> Fraction:
    return equave_reduce(quotient, 2)
