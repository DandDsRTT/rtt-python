from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from math import comb

import sympy as sp

from rtt.canonicalization import canonical_form
from rtt.dimensions import get_d, get_n, get_r
from rtt.list_utils import all_zeros_l, divide_out_gcd, leading_entry, trailing_entry
from rtt.matrix_utils import get_largest_minors_l, hnf, reverse_inner_l, rotate_180
from rtt.temperament import Temperament, Variance


@dataclass(frozen=True)
class Multivector:
    """A temperament as a multivector (wedgie): the rank-order minors
    (Plücker coordinates), the grade, the variance, and d (needed only when
    grade == 0, where d can't be inferred from the coordinate count)."""

    coords: tuple
    grade: int
    variance: Variance
    d: int | None = None


def ea_get_largest_minors_l(u: Multivector) -> tuple:
    return u.coords


def ea_get_grade(u: Multivector) -> int:
    return u.grade


def ea_get_variance(u: Multivector) -> Variance:
    return u.variance


def ea_get_d(u: Multivector) -> int:
    if is_nondecomposable(u):
        raise ValueError("nondecomposable multivector has no dimensionality")
    return _ea_get_decomposable_d(u)


def ea_get_r(u: Multivector) -> int:
    if is_nondecomposable(u):
        raise ValueError("nondecomposable multivector has no rank")
    if u.variance is Variance.ROW:
        return u.grade
    return _ea_get_decomposable_d(u) - u.grade


def ea_get_n(u: Multivector) -> int:
    if is_nondecomposable(u):
        raise ValueError("nondecomposable multivector has no nullity")
    if u.variance is Variance.COL:
        return u.grade
    return _ea_get_decomposable_d(u) - u.grade


def _ea_get_decomposable_d(u: Multivector) -> int:
    if u.d is not None:
        return u.d
    target = len(u.coords)
    d = u.grade
    while comb(d, u.grade) != target:
        d += 1
    return d


def is_nondecomposable(u: Multivector) -> bool:
    return _multivector_to_matrix_or_none(u) is None


def multivector_to_matrix(u: Multivector) -> Temperament:
    matrix = _multivector_to_matrix_or_none(u)
    if matrix is None:
        raise ValueError("nondecomposable multivector has no matrix")
    return matrix


def _multivector_to_matrix_or_none(u: Multivector) -> Temperament | None:
    if u.grade == 0:
        t = Temperament(((0,) * _ea_get_decomposable_d(u),), u.variance)
    elif u.grade == 1:
        t = Temperament((u.coords,), u.variance)
    else:
        t = _mc_to_c(u) if u.variance is Variance.COL else _mm_to_m(u)
    return None if t is None else canonical_form(t)


def _mm_to_m(u: Multivector) -> Temperament | None:
    flattened = _flattened_antisymmetric_matrix(u)
    if sp.Matrix(flattened).rank() != u.grade:
        return None
    return Temperament(hnf(flattened)[: u.grade], u.variance)


def _mc_to_c(u: Multivector) -> Temperament | None:
    flattened = reverse_inner_l(_flattened_antisymmetric_matrix(u))
    if sp.Matrix(flattened).rank() != u.grade:
        return None
    return Temperament(rotate_180(hnf(flattened)[: u.grade]), u.variance)


def _flattened_antisymmetric_matrix(u: Multivector) -> tuple:
    """The antisymmetric grade-tensor flattened to a (d^(grade-1)) x d matrix."""
    d = _ea_get_decomposable_d(u)
    index_to_coord = dict(zip(combinations(range(d), u.grade), u.coords))
    rows = [[0] * d for _ in range(d ** (u.grade - 1))]
    for full_index in product(range(d), repeat=u.grade):
        if len(set(full_index)) < u.grade:
            continue  # repeated index -> antisymmetric entry is zero
        value = _permutation_sign(full_index) * index_to_coord[tuple(sorted(full_index))]
        if value:
            row = 0
            for component in full_index[:-1]:
                row = row * d + component
            rows[row][full_index[-1]] = value
    return tuple(tuple(row) for row in rows)


def _permutation_sign(permutation: tuple) -> int:
    inversions = sum(
        1
        for i in range(len(permutation))
        for j in range(i + 1, len(permutation))
        if permutation[i] > permutation[j]
    )
    return -1 if inversions % 2 else 1


def ea_canonical_form(u: Multivector) -> Multivector:
    if all_zeros_l(u.coords):
        return u
    if is_nondecomposable(u):
        raise ValueError("nondecomposable multivector has no canonical form")
    coords = divide_out_gcd(u.coords)
    descends = (u.variance is Variance.ROW and leading_entry(coords) < 0) or (
        u.variance is Variance.COL and trailing_entry(coords) < 0
    )
    if descends:
        coords = tuple(-x for x in coords)
    d = ea_get_d(u) if u.grade == 0 else None
    return Multivector(coords, u.grade, u.variance, d)


def matrix_to_multivector(t: Temperament) -> Multivector:
    grade = get_n(t) if t.variance is Variance.COL else get_r(t)
    return ea_canonical_form(
        Multivector(get_largest_minors_l(t.matrix), grade, t.variance, get_d(t))
    )
