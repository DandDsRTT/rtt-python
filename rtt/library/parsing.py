from __future__ import annotations

import re
from fractions import Fraction

from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, quotient_to_pcv
from rtt.library.temperament import Temperament, Variance

_COVARIANT_RE = re.compile(r"\[?\s*[<⟨{][^\[]*")
_ROW_VECTOR_RE = re.compile(r"[⟨{<]([\d\-+*/.,\s]*)[\]|]\s*")
_COL_VECTOR_RE = re.compile(r"[\[|]([\d\-+*/.,\s]*)[}⟩>]\s*")
_SPLIT_RE = re.compile(r"(?:\s*,\s*)|\s+")
_DOMAIN_BASIS_PREFIX_RE = re.compile(r"^([\d./]+)\s+(.*)$", re.DOTALL)


def is_covariant_ebk(ebk: str) -> bool:
    """Whether the EBK string denotes a covariant (mapping / covector) temperament."""
    return _COVARIANT_RE.fullmatch(ebk) is not None


def parse_temperament_data(data: str | Temperament) -> Temperament:
    if isinstance(data, Temperament):  # already-structured input passes through
        return data
    domain_basis = None
    prefix = _DOMAIN_BASIS_PREFIX_RE.match(data)
    if prefix:
        domain_basis = parse_domain_basis(prefix.group(1))
        data = prefix.group(2)
    if is_covariant_ebk(data):
        variance = Variance.ROW
        raw_vectors = _ROW_VECTOR_RE.findall(data)
    else:
        variance = Variance.COL
        raw_vectors = _COL_VECTOR_RE.findall(data)
    matrix = tuple(parse_ebk_vector(v) for v in raw_vectors)
    return Temperament(matrix, variance, domain_basis)


def parse_quotients(text: str) -> list[Fraction]:
    """Parse a quotient-list string like ``"{2/1, 3/2, 5/4}"`` into fractions."""
    return [Fraction(token) for token in re.findall(r"[\d/]+", text)]


def parse_quotient_list(text: str, d: int) -> tuple[tuple[int, ...], ...]:
    """Parse a quotient-list string like ``"{2/1, 3/2, 5/4}"`` into vectors (each a
    prime-count vector padded to ``d`` entries)."""
    pcvs = tuple(quotient_to_pcv(q) for q in parse_quotients(text))
    return pad_vectors_with_zeros_up_to_d(pcvs, d)


def parse_domain_basis(text: str) -> tuple:
    """Parse a dot-separated domain basis like ``2.3.7`` into ``(2, 3, 7)``."""
    return tuple(Fraction(p) if "/" in p else int(p) for p in text.split("."))


def parse_ebk_vector(text: str) -> tuple:
    """Parse one EBK vector's entries; empty entries (e.g. ``,,``) become None."""
    return tuple(_to_number(token) for token in _SPLIT_RE.split(text.strip()))


def _to_number(token: str):
    if token == "":
        return None
    if "." in token:
        return float(token)
    if "/" in token:
        return Fraction(token)
    return int(token)
