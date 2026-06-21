from __future__ import annotations

import logging
from fractions import Fraction

from rtt.app.service.state import TemperamentState, from_temperament_data
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Variance

_log = logging.getLogger(__name__)


def _int_matrix_or_none(matrix) -> Matrix | None:
    if not matrix or not all(matrix):
        return None
    width = len(matrix[0])
    rows = []
    for row in matrix:
        if len(row) != width:
            return None
        if any(isinstance(x, bool) or not isinstance(x, int) for x in row):
            return None
        rows.append(tuple(row))
    return tuple(rows)


def _rational_matrix_or_none(matrix):
    if not matrix or not all(matrix):
        return None
    width = len(matrix[0])
    rows = []
    for row in matrix:
        if len(row) != width:
            return None
        if any(isinstance(x, bool) or not isinstance(x, (int, Fraction)) for x in row):
            return None
        rows.append(tuple(str(x) for x in row))
    return tuple(rows)


def _parse_float_list(text: str, n: int | None = None) -> tuple[float, ...] | None:
    tokens = text.strip().strip("{}⟨⟩[]()").replace(",", " ").split()
    if not tokens:
        return None
    try:
        values = tuple(float(t) for t in tokens)
    except ValueError:
        return None
    if n is not None and len(values) != n:
        return None
    return values


def parse_cents_map(text: str, n: int | None = None) -> tuple[float, ...] | None:
    return _parse_float_list(text, n)


def parse_projection(text: str):
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_projection rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.ROW:
        return None
    return _rational_matrix_or_none(t.matrix)


def parse_embedding(text: str, d: int, r: int):
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_embedding rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.COL:
        return None
    kets = _rational_matrix_or_none(t.matrix)
    if kets is None or len(kets) != r or any(len(k) != d for k in kets):
        return None
    return tuple(tuple(kets[g][i] for g in range(r)) for i in range(d))


def parse_prescaler_diagonal(text: str, d: int) -> tuple[float, ...] | None:
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_prescaler_diagonal rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.ROW or len(t.matrix) not in (d, d + 1):
        return None
    for i in range(d):
        row = t.matrix[i]
        if len(row) != d:
            return None
        for j, value in enumerate(row):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            if i != j and value != 0:
                return None
    return tuple(float(t.matrix[i][i]) for i in range(d))


def parse_mapping_state(text: str) -> TemperamentState | None:
    try:
        t = parse_temperament_data(text)
        if t.variance is not Variance.ROW or _int_matrix_or_none(t.matrix) is None:
            return None
        return from_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_mapping_state rejected %.80r: %r", text, exc)
        return None


def parse_form_matrix(text: str) -> Matrix | None:
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_form_matrix rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.ROW:
        return None
    return _int_matrix_or_none(t.matrix)


def parse_comma_basis(text: str) -> Matrix | None:
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_comma_basis rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.COL:
        return None
    return _int_matrix_or_none(t.matrix)
