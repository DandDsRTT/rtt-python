from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.library.dimensions import get_d
from rtt.library.domain_basis import get_domain_basis
from rtt.library.dual import mapping_matrix
from rtt.library.temperament import Temperament
from rtt.library.tuning import _held_vectors, resolve_target_intervals
from rtt.library.tuning_scheme_names import TuningSchemeSpec, resolve_tuning_scheme


def _is_prime_only_basis(domain_basis) -> bool:
    fractions = [Fraction(element) for element in domain_basis]
    return all(f.denominator == 1 and sp.isprime(f.numerator) for f in fractions)


def has_rational_closed_form(spec: TuningSchemeSpec, t: Temperament) -> bool:
    return (
        spec.optimization_power == 2
        and spec.damage_weight_slope == "unityWeight"
        and (spec.target_intervals is None or spec.target_intervals.strip() not in ("{}", ""))
        and spec.destretched_interval is None
        and not spec.nonprime_basis_approach
        and spec.complexity_size_factor == 0
        and _is_prime_only_basis(get_domain_basis(t))
    )


def closed_form_generator_operator(
    t: Temperament, spec: TuningSchemeSpec | str
) -> sp.Matrix | None:
    spec = resolve_tuning_scheme(spec)
    if not has_rational_closed_form(spec, t):
        return None
    try:
        return _build_generator_operator(t, spec)
    except (sp.matrices.exceptions.NonInvertibleMatrixError, ValueError):
        return None


def _integer_matrix(rows) -> sp.Matrix | None:
    rows = [[round(x) for x in row] for row in rows]
    return sp.Matrix(rows) if rows else None


def _solve_unity_operator(targets, held, mapping):
    rank, d = mapping.shape
    tempered = targets * mapping.T if targets is not None else sp.zeros(0, rank)
    if held is None:
        if targets is None or tempered.rows == 0:
            return sp.zeros(d, rank)
        return (tempered.pinv() * targets).T
    held_tempered = held * mapping.T
    held_operator = held_tempered.pinv() * held
    null_basis = held_tempered.nullspace()
    if not null_basis:
        return held_operator.T
    free_space = sp.Matrix.hstack(*null_basis)
    if tempered.rows == 0:
        free_operator = sp.zeros(free_space.cols, d)
    else:
        free_operator = (tempered * free_space).pinv() * (targets - tempered * held_operator)
    return (held_operator + free_space * free_operator).T


def _column_space_projector(determining, rank):
    null_basis = determining.nullspace()
    if not null_basis:
        return None
    free_space = sp.Matrix.hstack(*null_basis)
    return free_space * (free_space.T * free_space).inv() * free_space.T


def _build_generator_operator(t: Temperament, spec: TuningSchemeSpec) -> sp.Matrix:
    d = get_d(t)
    mapping = sp.Matrix(mapping_matrix(t))
    rank = mapping.rows
    targets = (
        None
        if spec.target_intervals is None
        else _integer_matrix(
            [v for v in _reshaped(resolve_target_intervals(spec.target_intervals, t, d), d)]
        )
    )
    held_raw = _held_vectors(spec, t, d)
    held = None if held_raw is None else _integer_matrix(_reshaped(held_raw, d))

    operator = _solve_unity_operator(targets, held, mapping)

    determining_rows = []
    if held is not None:
        determining_rows.append(held * mapping.T)
    if targets is not None and targets.rows > 0:
        determining_rows.append(targets * mapping.T)
    determining = (
        sp.Matrix.vstack(*determining_rows) if determining_rows else sp.zeros(0, rank)
    )
    projector = _column_space_projector(determining, rank)
    if projector is not None:
        just_operator = mapping.pinv()
        operator = operator + (just_operator - operator) * projector
    return operator


def _reshaped(vectors, d):
    flat = [list(v) for v in vectors]
    return [v for v in flat if len(v) == d]
