"""The sole seam between the web UI and the RTT library.

Everything the front end needs is expressed here in plain tuples/ints/strings so
the UI never imports library types directly. A :class:`TemperamentState` bundles
a temperament's mapping and its dual comma basis (kept in sync) plus dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass

from rtt.dimensions import get_d, get_n, get_r
from rtt.dual import dual
from rtt.generator_detempering import get_generator_detempering
from rtt.math_utils import get_primes, pcv_to_quotient
from rtt.parsing import parse_quotient_list
from rtt.target_intervals import process_tilt
from rtt.temperament import Temperament, Variance
from rtt.tuning import (
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
)

Matrix = tuple[tuple[int, ...], ...]

DEFAULT_TUNING_SCHEME = "TOP"


@dataclass(frozen=True)
class Tuning:
    generator_map: tuple[float, ...]  # cents, over the generators
    tuning_map: tuple[float, ...]  # cents, over the domain primes
    just_map: tuple[float, ...]  # cents, over the domain primes
    retuning_map: tuple[float, ...]  # tempered - just, over the primes
    tempered_targets: tuple[float, ...]  # cents, over the target intervals
    just_targets: tuple[float, ...]  # cents, over the target intervals
    target_errors: tuple[float, ...]  # tempered - just, over the targets
    target_damage: tuple[float, ...]  # |error| (unity weight), over the targets


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


def default_target_intervals(domain_basis) -> tuple[str, ...]:
    """The default target-interval set for a domain basis — its TILT — as ratio strings."""
    quotients = process_tilt("TILT", tuple(domain_basis))
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


def generators(mapping) -> tuple[str, ...]:
    """Each generator as an approximate ratio string, e.g. ``('2/1', '2/3')``."""
    m = Temperament(_to_matrix(mapping), Variance.ROW)
    ratios = []
    for monzo in get_generator_detempering(m).matrix:
        quotient = pcv_to_quotient(monzo)
        ratios.append(f"{quotient.numerator}/{quotient.denominator}")
    return tuple(ratios)


def mapped_target_intervals(mapping, ratios) -> Matrix:
    """Each target interval mapped through ``M`` — the targets in generator coords (r x k)."""
    mapping = _to_matrix(mapping)
    d = len(mapping[0])
    monzos = parse_quotient_list("{" + ", ".join(ratios) + "}", d)
    return tuple(
        tuple(sum(mapping[i][p] * monzo[p] for p in range(d)) for monzo in monzos)
        for i in range(len(mapping))
    )


def tuning(mapping, ratios, scheme: str = DEFAULT_TUNING_SCHEME) -> Tuning:
    """All tuning-row values (cents) for the temperament under ``scheme``."""
    t = Temperament(_to_matrix(mapping), Variance.ROW)
    d = get_d(t)
    tempered = optimize_tuning_map(t, scheme)
    just = get_just_tuning_map(t)
    monzos = parse_quotient_list("{" + ", ".join(ratios) + "}", d)

    def over(prime_map, monzo):
        return sum(prime_map[p] * monzo[p] for p in range(d))

    tempered_targets = tuple(over(tempered, m) for m in monzos)
    just_targets = tuple(over(just, m) for m in monzos)
    errors = tuple(t_ - j for t_, j in zip(tempered_targets, just_targets))
    return Tuning(
        generator_map=optimize_generator_tuning_map(t, scheme),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        tempered_targets=tempered_targets,
        just_targets=just_targets,
        target_errors=errors,
        target_damage=tuple(abs(e) for e in errors),
    )


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim each comma, then re-dual."""
    shrunk = tuple(comma[:-1] for comma in state.comma_basis)
    return from_comma_basis(shrunk)
