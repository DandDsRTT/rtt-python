from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from math import comb

import sympy as sp

from rtt.library.canonicalization import canonical_form
from rtt.library.dimensions import get_d, get_n, get_r
from rtt.library.list_utils import all_zeros_l, divide_out_gcd, leading_entry, trailing_entry
from rtt.library.matrix_utils import get_largest_minors_l, hnf, reverse_inner_l, rotate_180
from rtt.library.temperament import Temperament, Variance


@dataclass(frozen=True)
class Multivector:
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


def ea_indices(d: int, grade: int) -> tuple:
    return tuple(combinations(range(d), grade))


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
    d = _ea_get_decomposable_d(u)
    index_to_coord = dict(zip(combinations(range(d), u.grade), u.coords))
    rows = [[0] * d for _ in range(d ** (u.grade - 1))]
    for full_index in product(range(d), repeat=u.grade):
        if len(set(full_index)) < u.grade:
            continue
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
    return _decomposable_ea_canonical_form(u)


def _decomposable_ea_canonical_form(u: Multivector) -> Multivector:
    coords = divide_out_gcd(u.coords)
    descends = (u.variance is Variance.ROW and leading_entry(coords) < 0) or (
        u.variance is Variance.COL and trailing_entry(coords) < 0
    )
    if descends:
        coords = tuple(-x for x in coords)
    d = ea_get_d(u) if u.grade == 0 else None
    return Multivector(coords, u.grade, u.variance, d)


def ea_dual(u: Multivector) -> Multivector:
    if is_nondecomposable(u):
        raise ValueError("nondecomposable multivector has no dual")
    dual_variance = Variance.COL if u.variance is Variance.ROW else Variance.ROW
    d = _ea_get_decomposable_d(u)
    if u.grade == 0:
        return Multivector((1,), d, dual_variance)
    if u.grade == d:
        return Multivector((1,), 0, dual_variance, d)
    index_to_coord = dict(zip(combinations(range(d), u.grade), u.coords))
    dual_grade = d - u.grade
    dual_coords = []
    for indices in combinations(range(d), dual_grade):
        complement = tuple(x for x in range(d) if x not in indices)
        sign = _permutation_sign(complement + indices)
        dual_coords.append(sign * index_to_coord[complement])
    return _decomposable_ea_canonical_form(
        Multivector(tuple(dual_coords), dual_grade, dual_variance)
    )


def progressive_product(u1: Multivector, u2: Multivector) -> Multivector:
    if u1.variance is not u2.variance:
        raise ValueError("progressive product requires matching variance")
    d = ea_get_d(u1)
    if _ea_get_decomposable_d(u2) != d:
        raise ValueError("progressive product requires matching dimensionality")
    grade = u1.grade + u2.grade
    if grade > d:
        raise ValueError("progressive product grade exceeds dimensionality")
    coords1 = dict(zip(combinations(range(d), u1.grade), u1.coords))
    coords2 = dict(zip(combinations(range(d), u2.grade), u2.coords))
    result = []
    for indices in combinations(range(d), grade):
        total = 0
        for left in combinations(indices, u1.grade):
            right = tuple(x for x in indices if x not in left)
            total += _permutation_sign(left + right) * coords1[left] * coords2[right]
        result.append(total)
    return ea_canonical_form(Multivector(tuple(result), grade, u1.variance))


def regressive_product(u1: Multivector, u2: Multivector) -> Multivector:
    return ea_dual(progressive_product(ea_dual(u1), ea_dual(u2)))


def right_interior_product(u1: Multivector, u2: Multivector) -> Multivector:
    return ea_dual(progressive_product(ea_dual(u1), u2))


def left_interior_product(u1: Multivector, u2: Multivector) -> Multivector:
    return ea_dual(progressive_product(u1, ea_dual(u2)))


def interior_product(u1: Multivector, u2: Multivector) -> Multivector:
    if u1.grade >= u2.grade:
        return right_interior_product(u1, u2)
    return left_interior_product(u1, u2)


def ea_sum(u1: Multivector, u2: Multivector) -> Multivector:
    return _ea_addition(u1, u2, is_sum=True)


def ea_diff(u1: Multivector, u2: Multivector) -> Multivector:
    return _ea_addition(u1, u2, is_sum=False)


def _ea_addition(u1: Multivector, u2: Multivector, is_sum: bool) -> Multivector:
    first = ea_canonical_form(u1)
    second = ea_dual(u2) if u2.variance is not first.variance else ea_canonical_form(u2)
    if ea_get_r(first) != ea_get_r(second) or ea_get_d(first) != ea_get_d(second):
        raise ValueError("multivectors not addable: dimensions differ")
    if not is_sum and first == second:
        raise ValueError("cannot diff a temperament with itself")
    combined = tuple(a + b if is_sum else a - b for a, b in zip(first.coords, second.coords))
    result = Multivector(combined, first.grade, first.variance)
    if is_nondecomposable(result):
        raise ValueError("multivectors not addable")
    return ea_canonical_form(result)


def matrix_to_multivector(t: Temperament) -> Multivector:
    grade = get_n(t) if t.variance is Variance.COL else get_r(t)
    independent_rows = hnf(t.matrix)[:grade]
    return ea_canonical_form(
        Multivector(get_largest_minors_l(independent_rows), grade, t.variance, get_d(t))
    )


def u_to_tensor(u: Multivector):
    d = _ea_get_decomposable_d(u)
    index_to_coord = dict(zip(combinations(range(d), u.grade), u.coords))

    def build(prefix: tuple) -> object:
        if len(prefix) == u.grade:
            if len(set(prefix)) < u.grade:
                return 0
            return _permutation_sign(prefix) * index_to_coord[tuple(sorted(prefix))]
        return tuple(build(prefix + (axis,)) for axis in range(d))

    return build(())
