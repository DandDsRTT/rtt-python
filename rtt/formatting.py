from __future__ import annotations

from fractions import Fraction

from rtt.dimensions import get_d, get_r
from rtt.temperament import Temperament, Variance

_OUTPUT_ACCURACY = 3


def format_output(output: Temperament, fmt: str = "wolfram") -> Temperament | str:
    """Return the structured temperament (``wolfram``) or its EBK string (``ebk``)."""
    return to_ebk(output) if fmt == "ebk" else output


def to_ebk(t: Temperament) -> str:
    """Format a whole temperament as an EBK string (the inverse of parsing)."""
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
    if count == get_d(t):
        return when_d
    if count == get_r(t):
        return when_r
    return ("[", "]")


def vector_to_ebk(vector: tuple, t: Temperament) -> str:
    """Format one vector as EBK, bracketed per its length vs d/r."""
    body = " ".join(_format_number(x) for x in vector)
    n = len(vector)
    if n == get_d(t):
        return f"[{body}⟩"
    if n == get_r(t):
        return "[" + body + "}"
    return f"[{body}]"


def covector_to_ebk(covector: tuple, t: Temperament) -> str:
    """Format one covector (map) as EBK, bracketed per its length vs d/r."""
    body = " ".join(_format_number(x) for x in covector)
    n = len(covector)
    if n == get_d(t):
        return f"⟨{body}]"
    if n == get_r(t):
        return "{" + body + "]"
    return f"[{body}]"


def _format_number(entry) -> str:
    if isinstance(entry, int):
        return str(entry)
    if isinstance(entry, Fraction) and entry.denominator == 1:
        return str(entry.numerator)
    return f"{float(entry):.{_OUTPUT_ACCURACY}f}"
