from __future__ import annotations

from fractions import Fraction

from rtt.library.dimensions import get_dimensionality, get_rank
from rtt.library.temperament import Temperament, Variance

_OUTPUT_ACCURACY = 3


def format_output(output: Temperament, fmt: str = "wolfram") -> Temperament | str:
    return to_ebk(output) if fmt == "ebk" else output


def to_ebk(t: Temperament) -> str:
    rows = t.matrix
    if t.variance is Variance.COL:
        if len(rows) == 1:
            return vector_to_ebk(rows[0], t)
        inner = " ".join(vector_to_ebk(row, t) for row in rows)
        opener, closer = _outer_brackets(len(rows), t, ("⟨", "]"), ("{", "]"))
    else:
        if len(rows) == 1:
            return covector_to_ebk(rows[0], t)
        inner = " ".join(covector_to_ebk(row, t) for row in rows)
        opener, closer = _outer_brackets(len(rows), t, ("[", "⟩"), ("[", "}"))
    return f"{opener}{inner}{closer}"


def _outer_brackets(
    count: int, t: Temperament, when_d: tuple[str, str], when_r: tuple[str, str]
) -> tuple[str, str]:
    if count == get_dimensionality(t):
        return when_d
    if count == get_rank(t):
        return when_r
    return ("[", "]")


def vector_to_ebk(vector: tuple, t: Temperament) -> str:
    body = " ".join(_format_number(x) for x in vector)
    n = len(vector)
    if n == get_dimensionality(t):
        return f"[{body}⟩"
    if n == get_rank(t):
        return "[" + body + "}"
    return f"[{body}]"


def covector_to_ebk(covector: tuple, t: Temperament) -> str:
    body = " ".join(_format_number(x) for x in covector)
    n = len(covector)
    if n == get_dimensionality(t):
        return f"⟨{body}]"
    if n == get_rank(t):
        return "{" + body + "]"
    return f"[{body}]"


def strip_negative_zero(text: str) -> str:
    if text.startswith("-") and not any(ch in "123456789" for ch in text):
        return text[1:]
    return text


def _format_number(entry) -> str:
    if isinstance(entry, int):
        return str(entry)
    if isinstance(entry, Fraction):
        if entry.denominator == 1:
            return str(entry.numerator)
        return f"{entry.numerator}/{entry.denominator}"
    return strip_negative_zero(f"{float(entry):.{_OUTPUT_ACCURACY}f}")
