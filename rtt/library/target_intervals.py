from __future__ import annotations

import re
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.library.math_utils import octave_reduce

MIN_SIZE = Fraction(15, 13)
MAX_SIZE = Fraction(13, 4)


@lru_cache(maxsize=64)
def get_tilt(integer_limit: int) -> tuple[Fraction, ...]:
    diamond = _dedup(
        Fraction(numerator, denominator)
        for numerator in range(2, integer_limit + 1)
        for denominator in range(1, numerator)
    )
    max_complexity = integer_limit * 13
    return tuple(
        q
        for q in diamond
        if MIN_SIZE <= q <= MAX_SIZE
        and q.numerator * q.denominator <= max_complexity
    )


@lru_cache(maxsize=64)
def get_old(odd_limit: int) -> tuple[Fraction, ...]:
    odds = range(1, odd_limit + 1, 2)
    quotients = _dedup(
        Fraction(numerator, denominator) for numerator in odds for denominator in odds
    )
    reduced = _dedup(octave_reduce(q) for q in quotients if q != 1)
    return (Fraction(2), *reduced)


def get_otonal_chord(harmonics: tuple[int, ...]) -> tuple[Fraction, ...]:
    return _dedup(
        Fraction(harmonics[higher], harmonics[lower])
        for lower in range(len(harmonics))
        for higher in range(lower + 1, len(harmonics))
    )


def default_tilt_limit(domain_basis: tuple) -> int:
    greatest = max(Fraction(q).numerator for q in domain_basis)
    return int(sp.nextprime(greatest)) - 1


def default_old_limit(domain_basis: tuple) -> int:
    greatest = max(_odd_part(Fraction(q).numerator) for q in domain_basis)
    return int(sp.nextprime(greatest)) - 2


def process_tilt(target_spec: str, domain_basis: tuple) -> tuple[Fraction, ...]:
    spec = target_spec.replace("truncated integer limit triangle", "TILT")
    match = re.search(r"(\d*)-?TILT", spec)
    given = match.group(1) if match else ""
    return get_tilt(int(given) if given else default_tilt_limit(domain_basis))


def process_old(target_spec: str, domain_basis: tuple) -> tuple[Fraction, ...]:
    spec = target_spec.replace("odd limit diamond", "OLD")
    match = re.search(r"(\d*)-?OLD", spec)
    given = match.group(1) if match else ""
    return get_old(int(given) if given else default_old_limit(domain_basis))


def _odd_part(n: int) -> int:
    while n % 2 == 0:
        n //= 2
    return n


def _dedup(values) -> tuple:
    return tuple(dict.fromkeys(values))
