from __future__ import annotations

import math
import re
from fractions import Fraction


def _exact_steps(n: int, domain_basis: tuple) -> list[float]:
    """How many of N's equal steps each domain element spans, before rounding:
    ``N · log2(element)`` for each element. Elements are ints or Fractions, possibly
    nonprime (9, 13/5); the log is taken over the element itself, so over 2.9.5 the
    9-coordinate is ``N · log2 9`` (not twice the 3-coordinate)."""
    return [n * math.log2(float(Fraction(e))) for e in domain_basis]


def _kth_nearest_integer(x: float, k: int) -> int:
    """The ``(k+1)``-th closest integer to ``x`` (``k == 0`` is the nearest — the patent
    rounding). Integers are ordered by distance to ``x``, so this walks outward in the
    asymmetric order the fractional part dictates: for ``x = 39.47`` the sequence
    k = 0,1,2,… is 39, 40, 38, 41, 37, … (rounds down first, then alternates). This is the
    wart adjustment: one wart = second-nearest, two = third-nearest, and so on."""
    nearest = math.floor(x + 0.5)
    if k == 0:
        return nearest
    window = range(math.floor(x) - (k + 1), math.ceil(x) + (k + 1) + 1)
    by_distance = sorted(window, key=lambda m: (abs(m - x), m))
    return by_distance[k]


def patent_val(n: int, domain_basis: tuple) -> tuple[int, ...]:
    """The patent (best-rounding) val of the N-tone equal temperament over ``domain_basis``:
    each element is mapped to the nearest whole number of steps, ``round(N · log2(element))``.
    E.g. ``patent_val(12, (2, 3, 5)) == (12, 19, 28)``; over the nonstandard 2.9.5 basis the
    9-coordinate is ``round(12 · log2 9) == 38``. Rounds halves up (the microtonal convention),
    not to even. The result has one component per basis element."""
    return tuple(math.floor(x + 0.5) for x in _exact_steps(n, domain_basis))


def warted_val(n: int, warts: str, domain_basis: tuple) -> tuple[int, ...]:
    """The patent val of N adjusted by its wart letters. A wart letter names a domain-basis
    POSITION (``a`` → element 0, ``b`` → element 1, …, NOT a fixed prime), and each repeat of
    a letter pushes that coordinate one integer further from its exact step count, in the
    distance order :func:`_kth_nearest_integer` defines. ``warts == ""`` is the patent val.
    Letters past the basis length are ignored. E.g. ``warted_val(17, "c", (2, 3, 5)) ==
    (17, 27, 40)`` (the 5-coordinate moves off the patent 39 to its second-nearest 40)."""
    exact = _exact_steps(n, domain_basis)
    counts: dict[int, int] = {}
    for letter in warts.lower():
        i = ord(letter) - ord("a")
        if 0 <= i < len(exact):
            counts[i] = counts.get(i, 0) + 1
    return tuple(
        _kth_nearest_integer(x, counts.get(i, 0)) for i, x in enumerate(exact)
    )


def wart_name(n: int, warts: str = "") -> str:
    """The wart-notation label/value for an ET: a bare ``"N"`` for the patent val, else the
    count followed by its warts (e.g. ``"17c"``)."""
    return f"{n}{warts}"


def parse_wart_name(value: str) -> tuple[int, str]:
    """Split a wart name back into its ``(N, warts)`` parts — the inverse of
    :func:`wart_name`, for turning a chosen dropdown value into a val via :func:`warted_val`.
    ``"17c" -> (17, "c")``, ``"12" -> (12, "")``."""
    match = re.fullmatch(r"(\d+)([a-z]*)", value.strip().lower())
    if not match:
        raise ValueError(f'"{value}" is not a valid wart name.')
    return int(match.group(1)), match.group(2)


def _wart_string(n: int, val: tuple[int, ...], domain_basis: tuple) -> str:
    """The position-based wart string for which ``warted_val(n, warts, domain_basis) == val``:
    for each coordinate, how many integers off the patent rounding ``val`` lands, spelled as that
    coordinate's letter (a/b/c/…) repeated that many times. The inverse of :func:`warted_val`
    restricted to one ``n``. The equave coordinate is ``n`` itself, so it never warts."""
    letters = []
    for i, (x, vi) in enumerate(zip(_exact_steps(n, domain_basis), val)):
        k = 0
        while _kth_nearest_integer(x, k) != vi:
            k += 1
        letters.append(chr(ord("a") + i) * k)
    return "".join(letters)


def uniform_maps(domain_basis: tuple, max_n: int) -> list[tuple[int, str, tuple[int, ...]]]:
    """Every uniform map (generalized patent val / GPV) of every EDO from 1 to ``max_n`` over
    ``domain_basis``, in continuum order (EDO ascending, and within an EDO by ascending step
    size). A uniform map is the JIP ``⟨log2(e) for e in domain_basis]`` scaled by some positive
    real and rounded; an EDO's maps are exactly those whose multiplier lies in ``[n-0.5, n+0.5)``
    (so it has finitely many at a given prime limit, the patent val — ``warts == ""`` — among
    them). Each is returned as ``(n, warts, val)`` with ``n == val[0]`` the equave's step count
    and ``warted_val(n, warts, domain_basis) == val``.

    Found by walking the GPV sequence: from the all-zero map, repeatedly bump the coordinate whose
    rounding flips next (smallest ``(val[i] + 0.5) / log2(basis[i])``), emitting each map until the
    equave passes ``max_n``."""
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
