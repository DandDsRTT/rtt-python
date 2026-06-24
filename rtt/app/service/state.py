from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from rtt.app.service import outcome
from rtt.app.service.core import (
    is_standard_domain,
    standard_primes,
)
from rtt.app.service.core_intervals import transform_ratio
from rtt.app.service.core_vectors import _to_matrix
from rtt.app.service.outcome import Outcome
from rtt.library.dimensions import get_d, get_n, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance


@dataclass(frozen=True)
class TemperamentState:
    mapping: Matrix
    comma_basis: Matrix
    d: int
    r: int
    n: int
    domain_basis: tuple


def _state(mapping: Matrix, comma_basis: Matrix, domain_basis=None) -> TemperamentState:
    m = Temperament(mapping, Variance.ROW, domain_basis)
    return TemperamentState(
        mapping, comma_basis, get_d(m), get_r(m), get_n(m), tuple(get_domain_basis(m))
    )


def from_mapping(mapping, domain_basis=None) -> TemperamentState:
    mapping = _to_matrix(mapping)
    comma_basis = dual(Temperament(mapping, Variance.ROW, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def from_comma_basis(comma_basis, domain_basis=None) -> TemperamentState:
    comma_basis = _to_matrix(comma_basis)
    mapping = dual(Temperament(comma_basis, Variance.COL, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def standardize_to_prime_limit(domain_basis, comma_ratios) -> TemperamentState:
    touched_primes = get_simplest_prime_only_basis(domain_basis)
    num_primes = int(sp.primepi(touched_primes[-1])) if touched_primes else len(tuple(domain_basis))
    standard = standard_primes(num_primes)
    commas = express_quotients_in_domain_basis(comma_ratios, standard)
    return from_comma_basis(commas, standard)


def from_temperament_data(ebk: str) -> TemperamentState:
    t = parse_temperament_data(ebk)
    if t.variance is Variance.ROW:
        return from_mapping(t.matrix, t.domain_basis)
    return from_comma_basis(t.matrix, t.domain_basis)


def mapping_ebk(state: TemperamentState) -> str:
    ebk = to_ebk(Temperament(state.mapping, Variance.ROW, state.domain_basis))
    if not is_standard_prime_limit_domain_basis(state.domain_basis):
        ebk = ".".join(str(e) for e in state.domain_basis) + " " + ebk
    return ebk


def expand_domain(state: TemperamentState) -> TemperamentState:
    expanded = tuple((*comma, 0) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    independent: list[tuple[int, ...]] = []
    for comma in (c[:-1] for c in state.comma_basis):
        trial = [*independent, comma]
        raises_the_nullity = from_comma_basis(tuple(trial)).n == len(trial)
        if raises_the_nullity:
            independent.append(comma)
    if not independent:
        return just_intonation(standard_primes(state.d - 1))
    return from_comma_basis(tuple(independent))


def can_shrink_domain(state: TemperamentState) -> bool:
    return is_standard_domain(state.domain_basis) and state.d > 1


def just_intonation(domain_basis) -> TemperamentState:
    d = len(domain_basis)
    identity = tuple(tuple(int(row == col) for col in range(d)) for row in range(d))
    return from_mapping(identity, domain_basis)


def remove_comma(state: TemperamentState, index: int = -1) -> TemperamentState:
    basis = state.comma_basis
    i = index % len(basis)
    remaining = basis[:i] + basis[i + 1 :]
    return (
        from_comma_basis(remaining, state.domain_basis)
        if remaining
        else just_intonation(state.domain_basis)
    )


def remove_mapping_row(state: TemperamentState, i: int) -> TemperamentState:
    kept = state.mapping[:i] + state.mapping[i + 1 :]
    return from_mapping(kept, state.domain_basis)


def add_mapping_row(state: TemperamentState) -> TemperamentState:
    return remove_comma(state)


def _as_basis_element(value):
    fraction = Fraction(value)
    return fraction.numerator if fraction.denominator == 1 else fraction


def parse_domain_element(text):
    try:
        fraction = Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        return None
    if fraction <= 0 or fraction == 1:
        return None
    return _as_basis_element(fraction)


def is_independent_domain_basis(domain_basis) -> bool:
    elements = tuple(Fraction(e) for e in domain_basis)
    if not elements:
        return False
    superspace = get_simplest_prime_only_basis(tuple(domain_basis))
    vectors = express_quotients_in_domain_basis(elements, superspace)
    return sp.Matrix(vectors).rank() == len(elements)


def can_set_domain_element(state: TemperamentState, index: int, element) -> bool:
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    trial = (
        *state.domain_basis[:index],
        _as_basis_element(parsed),
        *state.domain_basis[index + 1 :],
    )
    return is_independent_domain_basis(trial)


def set_domain_element(state: TemperamentState, index: int, element) -> TemperamentState:
    new_basis = (
        *state.domain_basis[:index],
        _as_basis_element(element),
        *state.domain_basis[index + 1 :],
    )
    return from_mapping(state.mapping, new_basis)


def _not_a_basis_element(raw: str) -> Outcome:
    return outcome.reject(f"“{raw}” is not a valid basis element (≠ 1)")


def resolve_domain_element_transform(
    state: TemperamentState, index: int, current_text: str, op: str
) -> Outcome:
    new_raw = transform_ratio(current_text, op, state.domain_basis)
    if new_raw is None:
        return outcome.IGNORE
    parsed = parse_domain_element(new_raw)
    if parsed is None:
        return _not_a_basis_element(new_raw)
    if not can_set_domain_element(state, index, parsed):
        return outcome.reject(f"{new_raw} would make the basis dependent")
    return outcome.accept(new_raw)


def resolve_domain_element_edit(state: TemperamentState, tok: str, raw: str) -> Outcome:
    if raw in ("", "?/?"):
        return outcome.RERENDER
    parsed = parse_domain_element(raw)
    if parsed is None:
        return outcome.reject(f"“{raw}” is not a positive rational basis element (≠ 1)")
    if tok == "pending":
        return _resolve_pending_domain_element(state, parsed, raw)
    return _resolve_existing_domain_element(state, int(tok), parsed, raw)


def _resolve_pending_domain_element(state: TemperamentState, parsed, raw: str) -> Outcome:
    if not can_add_domain_element(state, parsed):
        return outcome.reject(f"{raw} isn’t independent of the existing basis")
    return outcome.accept(raw)


def _resolve_existing_domain_element(
    state: TemperamentState, index: int, parsed, raw: str
) -> Outcome:
    if parsed == state.domain_basis[index]:
        return outcome.IGNORE
    if not can_set_domain_element(state, index, parsed):
        return outcome.reject(f"{raw} would make the basis dependent")
    return outcome.accept(raw)


def can_add_domain_element(state: TemperamentState, element) -> bool:
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    return is_independent_domain_basis((*tuple(state.domain_basis), _as_basis_element(parsed)))


def add_domain_element(state: TemperamentState, element) -> TemperamentState:
    new_basis = (*tuple(state.domain_basis), _as_basis_element(element))
    extended = tuple((*tuple(row), 0) for row in state.mapping)
    new_generator = (*tuple(0 for _ in range(state.d)), 1)
    return from_mapping((*extended, new_generator), new_basis)


def can_remove_domain_element(state: TemperamentState) -> bool:
    return state.d > 1


def remove_domain_element(state: TemperamentState, index: int) -> TemperamentState:
    i = index % state.d
    new_basis = state.domain_basis[:i] + state.domain_basis[i + 1 :]
    independent: list[tuple[int, ...]] = []
    for comma in (c[:i] + c[i + 1 :] for c in state.comma_basis):
        trial = [*independent, comma]
        raises_the_nullity = from_comma_basis(tuple(trial), new_basis).n == len(trial)
        if raises_the_nullity:
            independent.append(comma)
    if not independent:
        return just_intonation(new_basis)
    return from_comma_basis(tuple(independent), new_basis)


def add_mapping_row_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    rows = [list(row) for row in state.mapping]
    rows[target] = [t + s for t, s in zip(rows[target], rows[source], strict=False)]
    return from_mapping(rows, state.domain_basis)


def add_comma_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    commas = [list(comma) for comma in state.comma_basis]
    commas[target] = [t + s for t, s in zip(commas[target], commas[source], strict=False)]
    return from_comma_basis(commas, state.domain_basis)
