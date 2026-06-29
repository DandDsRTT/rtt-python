from __future__ import annotations

import logging
from dataclasses import replace
from fractions import Fraction
from functools import lru_cache

from rtt.app.service.core import DEFAULT_TUNING_SCHEME, Tuning
from rtt.app.service.core_closed_form import ClosedFormTuning, closed_form_from_temperament
from rtt.app.service.core_vectors import _to_matrix, _vectors_to_ratios
from rtt.app.service.projection import (
    _held_for_projection,
    _matrix_strings,
    projection_matrix_rationals,
)
from rtt.app.service.state import TemperamentState
from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    get_simplest_prime_only_basis,
)
from rtt.library.dual import dual
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.matrix_utils import Matrix, matrix_multiply
from rtt.library.superspace import (
    apply_matrix_to_vectors,
    compose_mapping_with_embedding,
    extend_to_full_image_rank,
    least_squares_left_factor,
    lift_vectors,
)
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity_prescaler,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_scheme_names import resolve_tuning_scheme

_log = logging.getLogger(__name__)


def superspace_primes(domain_basis) -> tuple[int, ...]:
    return get_simplest_prime_only_basis(tuple(domain_basis))


def superspace_dimension(domain_basis) -> int:
    return len(superspace_primes(domain_basis))


def basis_in_superspace(domain_basis) -> Matrix:
    superspace = superspace_primes(domain_basis)
    elements = tuple(Fraction(e) for e in domain_basis)
    return tuple(
        tuple(int(x) for x in v) for v in express_quotients_in_domain_basis(elements, superspace)
    )


def superspace_mapping(state: TemperamentState) -> Matrix:
    superspace = superspace_primes(state.domain_basis)
    comma_t = Temperament(state.comma_basis, Variance.COL, state.domain_basis)
    embedded = change_domain_basis_for_c(comma_t, superspace)
    return _to_matrix(dual(embedded).matrix)


def superspace_rank(state: TemperamentState) -> int:
    return len(superspace_mapping(state))


def superspace_generators(state: TemperamentState) -> tuple[str, ...]:
    superspace = superspace_primes(state.domain_basis)
    m = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    return _vectors_to_ratios(get_generator_detempering(m).matrix, superspace)


def superspace_just_mapping(primes) -> Matrix:
    dl = len(tuple(primes))
    return tuple(tuple(1 if i == j else 0 for j in range(dl)) for i in range(dl))


def lift_vectors_to_superspace(domain_basis, vectors) -> Matrix:
    return lift_vectors(basis_in_superspace(domain_basis), vectors)


def superspace_complexity_prescaler(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
) -> tuple[float, ...]:
    superspace = superspace_primes(state.domain_basis)
    t = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    spec = resolve_tuning_scheme(scheme)
    return tuple(get_complexity_prescaler(t, replace(spec.complexity, nonprime_basis_approach="")))


def mapping_to_superspace_generators(state: TemperamentState) -> Matrix:
    return compose_mapping_with_embedding(
        superspace_mapping(state), basis_in_superspace(state.domain_basis)
    )


def map_vectors_into_superspace_generators(state: TemperamentState, vectors) -> Matrix:
    return apply_matrix_to_vectors(mapping_to_superspace_generators(state), vectors)


def superspace_self_map(state: TemperamentState) -> Matrix:
    rl = superspace_rank(state)
    return tuple(tuple(1 if i == j else 0 for j in range(rl)) for i in range(rl))


def superspace_tuning(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
    nonprime_approach: str = "",
    generator_override=None,
) -> Tuning:
    superspace = superspace_primes(state.domain_basis)
    ml = superspace_mapping(state)
    t = Temperament(ml, Variance.ROW, superspace)
    spec = resolve_tuning_scheme(scheme)
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if generator_override is not None:
        generator_map = tuple(float(g) for g in generator_override)
        tempered = tuple(float(x) for x in tuning_map_from_generators(t, generator_map))
    else:
        generator_map = optimize_generator_tuning_map(t, spec)
        tempered = optimize_tuning_map(t, spec)
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=generator_map,
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just, strict=False)),
        monotone_generator_range=None,
        tradeoff_generator_range=None,
    )


def closed_form_superspace_tuning(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
) -> ClosedFormTuning | None:
    return _cached_closed_form_superspace_tuning(
        _to_matrix(superspace_mapping(state)), superspace_primes(state.domain_basis), scheme
    )


@lru_cache(maxsize=256)
def _cached_closed_form_superspace_tuning(ml, superspace, scheme) -> ClosedFormTuning | None:
    t = Temperament(ml, Variance.ROW, superspace)
    return closed_form_from_temperament(t, resolve_tuning_scheme(scheme))


def project_superspace_generators_to_domain(
    state: TemperamentState, superspace_generators
) -> tuple[float, ...]:
    superspace = superspace_primes(state.domain_basis)
    ml_t = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    superspace_tuning_map = tuning_map_from_generators(
        ml_t, tuple(float(g) for g in superspace_generators)
    )
    bl = basis_in_superspace(state.domain_basis)
    domain_tuning_map = apply_matrix_to_vectors(bl, (superspace_tuning_map,))[0]
    domain_t = Temperament(_to_matrix(state.mapping), Variance.ROW, state.domain_basis)
    return tuple(
        float(g) for g in generator_tuning_map_from_t_and_tuning_map(domain_t, domain_tuning_map)
    )


def superspace_generator_embedding(state: TemperamentState, held_ratios=()):
    p_rat = projection_matrix_rationals(state, held_ratios)
    if p_rat is None:
        return None
    msl = mapping_to_superspace_generators(state)
    if not msl:
        return None
    try:
        return least_squares_left_factor(p_rat, msl)
    except (ArithmeticError, ValueError, IndexError, TypeError, AttributeError) as exc:
        _log.debug("superspace_generator_embedding dashed: %r", exc)
        return None


def superspace_prime_projection(state: TemperamentState, held_ratios=()):
    g = superspace_generator_embedding(state, held_ratios)
    if g is None:
        return None
    return matrix_multiply(g, superspace_mapping(state))


def superspace_generator_embedding_display(state: TemperamentState, held_ratios=()):
    g = superspace_generator_embedding(state, held_ratios)
    return _matrix_strings(g) if g is not None else None


def superspace_prime_projection_display(state: TemperamentState, held_ratios=()):
    p = superspace_prime_projection(state, held_ratios)
    return _matrix_strings(p) if p is not None else None


def _superspace_held_basis(state: TemperamentState, held_ratios, ml):
    domain_held = _held_for_projection(state, held_ratios)
    if len(domain_held) != state.rank:
        return None
    lifted = lift_vectors_to_superspace(state.domain_basis, domain_held)
    return extend_to_full_image_rank(ml, lifted)


def _superspace_projection_temperaments(state: TemperamentState, held_ratios):
    ml = _to_matrix(superspace_mapping(state))
    if not ml:
        return None
    held_L = _superspace_held_basis(state, held_ratios, ml)
    if held_L is None:
        return None
    superspace = superspace_primes(state.domain_basis)
    return (
        Temperament(ml, Variance.ROW, superspace),
        Temperament(held_L, Variance.COL, superspace),
    )


def superspace_tuning_projection(state: TemperamentState, held_ratios=()):
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return _matrix_strings(get_tempering_projection(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("superspace_tuning_projection dashed: %r", exc)
        return None


def superspace_projection_matrix_rationals(state: TemperamentState, held_ratios=()):
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return get_tempering_projection(*inputs)
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None


def superspace_tuning_embedding(state: TemperamentState, held_ratios=()):
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return _matrix_strings(get_generator_embedding(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None
