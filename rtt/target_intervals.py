from __future__ import annotations

from fractions import Fraction

from rtt.math_utils import octave_reduce

MIN_SIZE = Fraction(15, 13)
MAX_SIZE = Fraction(13, 4)


def get_tilt(integer_limit: int) -> tuple[Fraction, ...]:
    """Truncated integer-limit triangle: the reduced quotients ``n/d`` with ``1 < n/d``
    and ``n <= integer_limit`` that fall within ``[15/13, 13/4]`` and whose ``n*d`` does
    not exceed ``13 * integer_limit``."""
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


def get_old(odd_limit: int) -> tuple[Fraction, ...]:
    """Odd-limit diamond: every octave-reduced reduced quotient among odd/odd ratios
    (excluding 1/1), with 2/1 prepended (Partch's tonality diamond, 2/1 for 1/1)."""
    odds = range(1, odd_limit + 1, 2)
    quotients = _dedup(
        Fraction(numerator, denominator) for numerator in odds for denominator in odds
    )
    reduced = _dedup(octave_reduce(q) for q in quotients if q != 1)
    return (Fraction(2), *reduced)


def get_otonal_chord(harmonics: tuple[int, ...]) -> tuple[Fraction, ...]:
    """The intervals between each pair of harmonics (each later harmonic over an earlier one)."""
    return _dedup(
        Fraction(harmonics[higher], harmonics[lower])
        for lower in range(len(harmonics))
        for higher in range(lower + 1, len(harmonics))
    )


def _dedup(values) -> tuple:
    """Deduplicate, preserving first-seen order."""
    return tuple(dict.fromkeys(values))
