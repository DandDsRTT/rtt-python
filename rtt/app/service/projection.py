from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache, reduce
from math import gcd

import sympy as sp

from rtt.app.service.core import (
    IntervalSizes,
    Tuning,
    _vectors_to_ratios,
    comma_ratios,
    interval_complexities,
    interval_sizes,
    interval_vector,
    mapped_commas,
)
from rtt.app.service.core_forms import inverse_form_matrix
from rtt.app.service.state import TemperamentState
from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.superspace import apply_matrix_to_vectors, greedy_independent_rows
from rtt.library.temperament import Temperament, Variance

_log = logging.getLogger(__name__)


def held_basis_vectors(state: TemperamentState, held_ratios) -> tuple:
    vectors: list = []
    for ratio in held_ratios:
        try:
            vectors.append(interval_vector(ratio, state.d, state.domain_basis))
        except ValueError:
            continue
    return greedy_independent_rows(vectors, state.r)


def _all_primes_held(state: TemperamentState) -> tuple:
    return tuple(tuple(1 if k == j else 0 for k in range(state.d)) for j in range(state.d))


def _projection_temperaments(state: TemperamentState, held_vectors):
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d or len(held_vectors) != r:
        return None
    mapping_t = Temperament(state.mapping, Variance.ROW, state.domain_basis)
    held_t = Temperament(held_vectors, Variance.COL, state.domain_basis)
    return mapping_t, held_t


def _held_for_projection(state: TemperamentState, held_ratios):
    return _all_primes_held(state) if state.n == 0 else held_basis_vectors(state, held_ratios)


def _matrix_strings(matrix):
    return tuple(tuple(str(entry) for entry in row) for row in matrix)


@lru_cache(maxsize=512)
def tuning_projection(state: TemperamentState, held_ratios=()):
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return _matrix_strings(get_tempering_projection(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("tuning_projection dashed: %r", exc)
        return None


def tuning_embedding(state: TemperamentState, held_ratios=()):
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return _matrix_strings(get_generator_embedding(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("tuning_embedding dashed: %r", exc)
        return None


def canonical_generator_embedding(state: TemperamentState, held_ratios=()):
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        g = get_generator_embedding(*inputs)
        f_inv = inverse_form_matrix(state.mapping)
        r, rc = len(f_inv), len(f_inv[0]) if f_inv else 0
        gc = tuple(
            tuple(sum(g[i][k] * f_inv[k][j] for k in range(r)) for j in range(rc))
            for i in range(len(g))
        )
        return _matrix_strings(gc)
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("canonical_generator_embedding dashed: %r", exc)
        return None


def projection_matrix_rationals(state: TemperamentState, held_ratios=()):
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return get_tempering_projection(*inputs)
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("projection_matrix_rationals dashed: %r", exc)
        return None


def project_vectors(p_matrix, vectors):
    if p_matrix is None:
        return ()
    return apply_matrix_to_vectors(p_matrix, vectors)


def _integer_columns(vectors):
    out = []
    for v in vectors:
        entries = [sp.Rational(x) for x in v]
        lcm_d = 1
        for e in entries:
            lcm_d = lcm_d * int(e.q) // gcd(lcm_d, int(e.q))
        ints = [int(e * lcm_d) for e in entries]
        g = reduce(gcd, [abs(i) for i in ints], 0) or 1
        out.append(tuple(i // g for i in ints))
    return out


def unchanged_basis_from_projection(state: TemperamentState, projection):
    try:
        d, r = state.d, state.r
        P = sp.Matrix([[sp.Rational(x) for x in row] for row in projection])
        if P.shape != (d, d) or P * P != P:
            return None
        for comma in state.comma_basis:
            if P * sp.Matrix(comma) != sp.zeros(d, 1):
                return None
        U = _integer_columns((P - sp.eye(d)).nullspace())
        return tuple(U) if len(U) == r else None
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("unchanged_basis_from_projection dashed: %r", exc)
        return None


def unchanged_basis_from_embedding(state: TemperamentState, embedding):
    try:
        d, r = state.d, state.r
        G = sp.Matrix([[sp.Rational(x) for x in row] for row in embedding])
        M = sp.Matrix([list(row) for row in state.mapping])
        if G.shape != (d, r) or sp.eye(r) != M * G:
            return None
        U = _integer_columns(G.columnspace())
        return tuple(U) if len(U) == r else None
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("unchanged_basis_from_embedding dashed: %r", exc)
        return None


def unchanged_interval_basis(state: TemperamentState, held_ratios=()):
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d:
        return None
    if state.n == 0:
        return _all_primes_held(state)
    held = held_basis_vectors(state, held_ratios)
    return held + (None,) * (r - len(held))


def unchanged_interval_ratios(state: TemperamentState, held_ratios=()) -> tuple | None:
    basis = unchanged_interval_basis(state, held_ratios)
    if basis is None:
        return None
    known = tuple(vector for vector in basis if vector is not None)
    return _vectors_to_ratios(known, state.domain_basis)


@dataclass(frozen=True)
class UnchangedData:
    basis: tuple
    ratios: tuple
    mapped: tuple
    sizes: IntervalSizes
    complexities: tuple


def unchanged_interval_data(
    state: TemperamentState,
    held_ratios,
    tun: Tuning,
    scheme,
    domain_basis=None,
    prescaler_override=None,
) -> UnchangedData | None:
    basis = unchanged_interval_basis(state, held_ratios)
    if basis is None:
        return None
    nu = len(basis)
    known = tuple(v for v in basis if v is not None)
    kidx = [j for j, v in enumerate(basis) if v is not None]

    def scatter(per_known):
        out = [None] * nu
        for pos, j in enumerate(kidx):
            out[j] = per_known[pos]
        return tuple(out)

    ratios = comma_ratios(known, domain_basis) if known else ()
    mapped = mapped_commas(state.mapping, known) if known else ()
    mapped_rows = tuple(scatter(mapped[i] if known else ()) for i in range(len(state.mapping)))
    sizes = interval_sizes(tun, ratios, domain_basis)
    sized = IntervalSizes(
        scatter(sizes.tempered), scatter(sizes.just), scatter(sizes.errors), scatter(sizes.damage)
    )
    comps = (
        interval_complexities(
            state.mapping,
            scheme,
            ratios,
            prescaler_override=prescaler_override,
            domain_basis=domain_basis,
        )
        if known
        else ()
    )
    return UnchangedData(basis, scatter(ratios), mapped_rows, sized, scatter(comps))


def unchanged_ratios_of_tuning(state: TemperamentState, retuning_map, candidate_ratios, tol=1e-6):
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d:
        return ()
    if state.n == 0:
        return _vectors_to_ratios(_all_primes_held(state), state.domain_basis)
    rows, ratios = [], []
    for ratio in candidate_ratios:
        try:
            vector = interval_vector(ratio, d, state.domain_basis)
        except (ValueError, KeyError, IndexError):
            continue
        damage = abs(sum(retuning_map[p] * vector[p] for p in range(d)))
        if damage >= tol:
            continue
        is_independent_of_those_found = sp.Matrix([*rows, list(vector)]).rank() == len(rows) + 1
        if is_independent_of_those_found:
            rows.append(list(vector))
            ratios.append(ratio)
            if len(ratios) == r:
                break
    return tuple(ratios)
