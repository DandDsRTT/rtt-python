from __future__ import annotations

from fractions import Fraction
from functools import reduce
from math import gcd, lcm


def divide_out_gcd(values: tuple[int, ...]) -> tuple[int, ...]:
    divisor = reduce(gcd, (abs(int(v)) for v in values), 0)
    if divisor == 0:
        return tuple(values)
    return tuple(v // divisor for v in values)


def mult_by_lcd(values: tuple) -> tuple[int, ...]:
    fractions = [Fraction(v) for v in values]
    multiplier = reduce(lcm, (f.denominator for f in fractions), 1)
    return tuple(int(f * multiplier) for f in fractions)


def leading_entry(values: tuple):
    return next(v for v in values if v != 0)


def trailing_entry(values: tuple):
    return next(v for v in reversed(values) if v != 0)


def all_zeros_l(values: tuple) -> bool:
    return all(v == 0 for v in values)
