from __future__ import annotations

from fractions import Fraction

from rtt.app import editor_solve, service
from rtt.app.editor_solve import Solve
from rtt.app.service.state import TemperamentState

MOVE_LISTS = ("targets", "held", "interest", "commas", "unchanged")


def can_expand(state: TemperamentState) -> bool:
    return service.is_standard_domain(state.domain_basis)


def can_shrink(state: TemperamentState) -> bool:
    return service.can_shrink_domain(state)


def can_remove_domain_element(state: TemperamentState) -> bool:
    return service.can_remove_domain_element(state)


def can_add_mapping_row(state: TemperamentState) -> bool:
    return state.n > 0


def can_remove_mapping_row(state: TemperamentState) -> bool:
    return state.r > 1


def basis_is_nonstandard(state: TemperamentState) -> bool:
    return not service.is_standard_domain(state.domain_basis)


def valid_domain_basis(state: TemperamentState) -> bool:
    basis = state.domain_basis
    if not state.mapping or len(basis) != len(state.mapping[0]):
        return False
    try:
        elements = [Fraction(e) for e in basis]
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    if any(e <= 0 or e == 1 for e in elements):
        return False
    return service.is_independent_domain_basis(basis)


def current_targets(s: Solve) -> list[str]:
    if s.target_override is not None:
        return list(s.target_override)
    return list(service.target_interval_set(s.target_spec, s.state.domain_basis))


def list_vectors(s: Solve, name: str) -> list[tuple[int, ...]]:
    state = s.state
    if name == "targets":
        return [
            tuple(v)
            for v in service.target_interval_vectors(
                current_targets(s), state.d, state.domain_basis
            )
        ]
    if name == "held":
        return [tuple(v) for v in s.held_vectors]
    if name == "interest":
        return [tuple(v) for v in s.interest_vectors]
    if name == "unchanged":
        return list(service.unchanged_interval_basis(state, editor_solve.unchanged_ratios(s)) or ())
    return [tuple(v) for v in state.comma_basis]


def peek_vector(vectors: list[tuple[int, ...]], i: int) -> tuple[int, ...] | None:
    return vectors[i] if 0 <= i < len(vectors) else None


def move_feasible(s: Solve, src: str, dst: str, vector: tuple[int, ...]) -> bool:
    state = s.state
    if src not in MOVE_LISTS or dst not in MOVE_LISTS:
        return False
    if dst == "unchanged":
        return False
    if "targets" in (src, dst) and service.is_all_interval(s.tuning_scheme):
        return False
    if src == "commas" and state.n == 0:
        return False
    if dst == "commas":
        real_comma_basis = state.comma_basis if state.n else ()
        domain_basis = state.domain_basis if len(vector) == state.d else None
        extended = service.from_comma_basis((*real_comma_basis, tuple(vector)), domain_basis)
        if extended.n <= state.n:
            return False
    return True
