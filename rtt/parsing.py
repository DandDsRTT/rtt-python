from __future__ import annotations

import re

from rtt.temperament import Temperament, Variance

_COVARIANT_RE = re.compile(r"^\[?\s*[<⟨{]")
_ROW_VECTOR_RE = re.compile(r"[⟨{<]([\d\-+*/.,\s]*)[\]|]\s*")
_COL_VECTOR_RE = re.compile(r"[\[|]([\d\-+*/.,\s]*)[}⟩>]\s*")
_SPLIT_RE = re.compile(r"(?:\s*,\s*)|\s+")


def parse_temperament_data(data: str) -> Temperament:
    if _COVARIANT_RE.match(data):
        variance = Variance.ROW
        raw_vectors = _ROW_VECTOR_RE.findall(data)
    else:
        variance = Variance.COL
        raw_vectors = _COL_VECTOR_RE.findall(data)
    matrix = tuple(_parse_ebk_vector(v) for v in raw_vectors)
    return Temperament(matrix, variance)


def _parse_ebk_vector(s: str) -> tuple[int, ...]:
    return tuple(int(token) for token in _SPLIT_RE.split(s.strip()) if token)
