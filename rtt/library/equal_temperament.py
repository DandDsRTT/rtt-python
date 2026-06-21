from __future__ import annotations

import math
import re
from fractions import Fraction


def _exact_steps(n: int, domain_basis: tuple) -> list[float]:
    return [n * math.log2(float(Fraction(e))) for e in domain_basis]


def _kth_nearest_integer(x: float, k: int) -> int:
    nearest = math.floor(x + 0.5)
    if k == 0:
        return nearest
    window = range(math.floor(x) - (k + 1), math.ceil(x) + (k + 1) + 1)
    by_distance = sorted(window, key=lambda m: (abs(m - x), m))
    return by_distance[k]


def patent_val(n: int, domain_basis: tuple) -> tuple[int, ...]:
    return tuple(math.floor(x + 0.5) for x in _exact_steps(n, domain_basis))


def warted_val(n: int, warts: str, domain_basis: tuple) -> tuple[int, ...]:
    exact = _exact_steps(n, domain_basis)
    counts: dict[int, int] = {}
    for letter in warts.lower():
        i = ord(letter) - ord("a")
        if 0 <= i < len(exact):
            counts[i] = counts.get(i, 0) + 1
    return tuple(_kth_nearest_integer(x, counts.get(i, 0)) for i, x in enumerate(exact))


def wart_name(n: int, warts: str = "") -> str:
    return f"{n}{warts}"


def parse_wart_name(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([a-z]*)", value.strip().lower())
    if not match:
        raise ValueError(f'"{value}" is not a valid wart name.')
    return int(match.group(1)), match.group(2)


def _wart_string(n: int, val: tuple[int, ...], domain_basis: tuple) -> str:
    letters = []
    for i, (x, vi) in enumerate(zip(_exact_steps(n, domain_basis), val, strict=False)):
        k = 0
        while _kth_nearest_integer(x, k) != vi:
            k += 1
        letters.append(chr(ord("a") + i) * k)
    return "".join(letters)


def uniform_maps(domain_basis: tuple, max_n: int) -> list[tuple[int, str, tuple[int, ...]]]:
    logs = [math.log2(float(Fraction(e))) for e in domain_basis]
    val = [0] * len(domain_basis)
    out: list[tuple[int, str, tuple[int, ...]]] = []
    while True:
        i = min(range(len(val)), key=lambda j: (val[j] + 0.5) / logs[j])
        val[i] += 1
        n = val[0]
        if n > max_n:
            return out
        if n >= 1:
            frozen = tuple(val)
            out.append((n, _wart_string(n, frozen, domain_basis), frozen))
