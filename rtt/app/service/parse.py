"""The parse_* readers: typed plain-text strings back to matrices, maps and states —
each the inverse of one of the text builders, returning ``None`` on malformed input so
the caller can flag the text rather than apply it."""

from __future__ import annotations

import logging
from fractions import Fraction

from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Variance

from rtt.app.service.state import TemperamentState, from_temperament_data

_log = logging.getLogger(__name__)


def _int_matrix_or_none(matrix) -> Matrix | None:
    """A rectangular all-integer matrix, or None — the validity gate for an edited
    plain-text mapping/comma-basis string (Fractions, decimals, blanks, or a ragged
    shape are rejected so the caller can flag the input rather than apply it)."""
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
    """A rectangular matrix of ints/Fractions as a grid of display strings, or None — the
    fraction-aware gate for an edited P/G plain-text string (the integer-only
    :func:`_int_matrix_or_none` rejects the ``1/4`` entries P/G carry). Floats, booleans, blanks,
    or a ragged shape are rejected so the caller can flag the input rather than apply it."""
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
    """A whitespace/comma-separated list of floats inside any EBK bracket pair
    (``{ ⟨ [ ( ) ] ⟩ }``), or None if it is empty, non-numeric, or (when ``n`` is given)
    not exactly ``n`` long. The float-tolerant core behind the cents-map parser."""
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
    """Read a cents map string back to its values — the generator tuning map
    ``{1201.699 697.564]`` or a prime tuning map ``⟨1200.000 …]`` — float-tolerant, the
    inverse of :func:`_cents_genmap` / :func:`_cents_map`. None if unparseable or (with
    ``n`` set) not exactly ``n`` values. The reader behind a typed manual generator tuning."""
    return _parse_float_list(text, n)


def parse_projection(text: str):
    """Read a map-list EBK string (e.g. ``[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩``) back to a d×d projection as a
    grid of display strings, or None if unparseable, the wrong variance (a vector, not a map), or not
    a rational matrix. The inverse of :func:`projection_ebk` — whether the matrix is actually a valid
    (idempotent) projection is the editor's call (``set_projection_matrix``)."""
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_projection rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.ROW:
        return None
    return _rational_matrix_or_none(t.matrix)


def parse_embedding(text: str, d: int, r: int):
    """Read a vector-list EBK string (e.g. ``[[1 0 0⟩[0 0 -1/4⟩]``) back to a d×r embedding as a grid
    of display strings, or None. The string's r kets parse as r rows of length d, so we TRANSPOSE
    them into the d×r grid ``set_embedding_matrix`` expects; a wrong variance (a map, not vectors) or
    a shape that isn't r kets of length d is rejected. The inverse of :func:`embedding_ebk`."""
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_embedding rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.COL:
        return None
    kets = _rational_matrix_or_none(t.matrix)  # r rows (the kets), each d-tall
    if kets is None or len(kets) != r or any(len(k) != d for k in kets):
        return None
    return tuple(tuple(kets[g][i] for g in range(r)) for i in range(d))  # transpose to d×r


def parse_prescaler_diagonal(text: str, d: int) -> tuple[float, ...] | None:
    """Read a bare prescaler 𝐿's plain text back to the diagonal it carries — the inverse
    of :func:`_prescale_vector_list` for the ``("prescaling", "primes")`` tile, the d×d
    covector matrix ``[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩``. The display shows the full
    matrix even though 𝐿 IS diagonal (off-diagonal cells pinned 0), so the parser does
    the inverse: parse the matrix via :func:`parse_temperament_data`, verify it's covariant
    and d×d, verify every off-diagonal entry is 0 (else 𝐿 wouldn't be diagonal — reject as
    malformed), and return the diagonal as a d-tuple of floats. None whenever the input
    can't be that shape, so the caller can flag the typed text without mangling the override.
    The reader behind a typed custom-prescaler EBK string (the bare prescaler tile's ptext)."""
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_prescaler_diagonal rejected %.80r: %r", text, exc)
        return None
    # the matrix is d×d, or (d+1)×d when the size factor adds the size-sensitizing row (the
    # rectangular 𝑋 = 𝑍𝐿); only the d diagonal rows are validated and read — the size row is
    # derived from the diagonal + the scheme's size factor, so any typed value there is ignored.
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
                return None  # 𝐿 is diagonal; an off-diagonal nonzero is malformed input
    return tuple(float(t.matrix[i][i]) for i in range(d))


def parse_mapping_state(text: str) -> TemperamentState | None:
    """Parse an EBK *map* string into a full state, honouring an optional domain-basis
    prefix (e.g. ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"`` -> a nonstandard temperament).
    None if unparseable, the wrong variance, or not an integer matrix. The inverse of
    the ``("mapping", "primes")`` plain text, which carries that prefix when nonstandard."""
    try:
        t = parse_temperament_data(text)
        if t.variance is not Variance.ROW or _int_matrix_or_none(t.matrix) is None:
            return None
        return from_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_mapping_state rejected %.80r: %r", text, exc)
        return None


def parse_form_matrix(text: str) -> Matrix | None:
    """Read an EBK genmap string (e.g. ``[{1 -1]{0 1]}``) back to the generator form matrix ``𝐹``'s
    integer rows, or None if unparseable, the wrong variance (a vector list, not a map), or
    non-integer. The inverse of the ``("canon", "gens")`` plain text — what the interactive 𝐹 tile
    parses a typed/edited matrix as (then :func:`mapping_from_form_matrix` re-stores the mapping)."""
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_form_matrix rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.ROW:
        return None
    return _int_matrix_or_none(t.matrix)


def parse_comma_basis(text: str) -> Matrix | None:
    """Read an EBK *vector* string (e.g. ``[4 -4 1⟩``) back to a comma basis, or
    None if unparseable, the wrong variance (a map, not a vector), or non-integer.
    The inverse of the ``("vectors", "commas")`` plain text."""
    try:
        t = parse_temperament_data(text)
    except Exception as exc:
        _log.debug("parse_comma_basis rejected %.80r: %r", text, exc)
        return None
    if t.variance is not Variance.COL:
        return None
    return _int_matrix_or_none(t.matrix)
