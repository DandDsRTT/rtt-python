"""The sole seam between the web UI and the RTT library.

Everything the front end needs is expressed here in plain tuples/ints/strings so
the UI never imports library types directly. A :class:`TemperamentState` bundles
a temperament's mapping and its dual comma basis (kept in sync) plus dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass

from rtt.dimensions import get_d, get_n, get_r
from rtt.dual import dual
from rtt.math_utils import get_primes
from rtt.temperament import Temperament, Variance

Matrix = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class TemperamentState:
    mapping: Matrix
    comma_basis: Matrix
    d: int
    r: int
    n: int


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


def _state(mapping: Matrix, comma_basis: Matrix) -> TemperamentState:
    m = Temperament(mapping, Variance.ROW)
    return TemperamentState(mapping, comma_basis, get_d(m), get_r(m), get_n(m))


def from_mapping(mapping) -> TemperamentState:
    """State whose source of truth is ``mapping``; comma basis is its dual."""
    mapping = _to_matrix(mapping)
    comma_basis = dual(Temperament(mapping, Variance.ROW)).matrix
    return _state(mapping, comma_basis)


def from_comma_basis(comma_basis) -> TemperamentState:
    """State whose source of truth is ``comma_basis``; mapping is its dual."""
    comma_basis = _to_matrix(comma_basis)
    mapping = dual(Temperament(comma_basis, Variance.COL)).matrix
    return _state(mapping, comma_basis)


def standard_primes(d: int) -> tuple[int, ...]:
    """The first ``d`` primes — the standard prime-limit domain basis (header labels)."""
    return get_primes(d)


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim each comma, then re-dual."""
    shrunk = tuple(comma[:-1] for comma in state.comma_basis)
    return from_comma_basis(shrunk)
