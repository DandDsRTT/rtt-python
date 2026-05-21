from __future__ import annotations

from itertools import product

import sympy as sp

from rtt.canonicalization import canonical_form
from rtt.dimensions import get_d, get_n, get_r
from rtt.domain_basis import get_domain_basis
from rtt.dual import dual
from rtt.list_utils import divide_out_gcd, leading_entry, trailing_entry
from rtt.matrix_utils import get_largest_minors_l, hnf, remove_all_zero_lists, transpose
from rtt.merging import comma_merge, map_merge
from rtt.temperament import Temperament, Variance


def sum_(t1: Temperament, t2: Temperament) -> Temperament:
    """The temperament sum: combine two addable temperaments (adding their
    differing basis vector)."""
    first, second = _prepare(t1, t2)
    if first == second:
        return first
    return _addition(first, second, is_sum=True)


def diff_(t1: Temperament, t2: Temperament) -> Temperament:
    """The temperament difference (subtracting the differing basis vector)."""
    first, second = _prepare(t1, t2)
    if first == second:
        raise ValueError("cannot diff a temperament with itself")
    return _addition(first, second, is_sum=False)


def _prepare(t1: Temperament, t2: Temperament) -> tuple[Temperament, Temperament]:
    first = canonical_form(t1)
    second = canonical_form(t2) if t1.variance is t2.variance else dual(t2)
    return first, second


def _addition(t1: Temperament, t2: Temperament, is_sum: bool) -> Temperament:
    if _dimensions_mismatch(t1, t2) or get_domain_basis(t1) != get_domain_basis(t2):
        raise ValueError("temperaments not addable: dimensions or bases differ")
    ldb = _get_linear_dependence_basis(t1, t2)  # raises if not addable
    v1 = _linear_independence_basis_vector(t1, ldb)
    v2 = _linear_independence_basis_vector(t2, ldb)
    combined = tuple(a + b if is_sum else a - b for a, b in zip(v1, v2))
    return canonical_form(Temperament(tuple(ldb) + (combined,), t1.variance))


def _dimensions_mismatch(t1: Temperament, t2: Temperament) -> bool:
    return get_r(t1) != get_r(t2) or get_d(t1) != get_d(t2)


def _get_grade(t: Temperament) -> int:
    return get_n(t) if t.variance is Variance.COL else get_r(t)


def _get_linear_dependence_basis(t1: Temperament, t2: Temperament) -> tuple:
    merged = map_merge(t1, t2) if t1.variance is Variance.COL else comma_merge(t1, t2)
    ldb = remove_all_zero_lists(dual(merged).matrix)
    if len(ldb) != _get_grade(t1) - 1:
        raise ValueError("temperaments not addable")
    return ldb


def _linear_independence_basis_vector(t: Temperament, ldb: tuple) -> tuple:
    a = _addabilization_defactor(t, ldb)
    vector = a[-1]
    if _is_negative(a, t.variance is Variance.COL):
        vector = tuple(-x for x in vector)
    return vector


def _addabilization_defactor(t: Temperament, ldb: tuple) -> tuple:
    grade = _get_grade(t)
    initial = _initial_explicit_ldb_form(t, ldb, grade)
    if len(ldb) > 0:  # linearly dependent: defactor against the shared basis
        return _defactor_with_nonempty_ldb(t, ldb, grade, initial)
    return initial


def _initial_explicit_ldb_form(t: Temperament, ldb: tuple, grade: int) -> tuple:
    result = list(ldb)
    for candidate in t.matrix:
        if len(result) < grade and sp.Matrix(list(ldb) + [candidate]).rank() > len(ldb):
            result.append(candidate)
    return tuple(result[:grade])


def _defactor_with_nonempty_ldb(t, ldb, grade, initial):
    # Adjust the last (linear-independence) vector by an integer combination of
    # the shared basis so it becomes divisible by the enfactoring, then defactor.
    # Any valid modular solution gives the same canonical result.
    base = initial[-1]
    enfactoring = abs(_get_greatest_factor(initial))
    multiples = _find_modular_solution(ldb, base, enfactoring)
    combination = (
        sum(multiples[i] * ldb[i][j] for i in range(len(ldb))) for j in range(len(base))
    )
    new_last = divide_out_gcd(tuple(b + c for b, c in zip(base, combination)))
    return tuple(initial[:-1]) + (new_last,)


def _get_greatest_factor(a: tuple) -> int:
    rank = sp.Matrix(a).rank()
    square = transpose(hnf(transpose(a))[:rank])
    return int(sp.Matrix(square).det())


def _find_modular_solution(ldb: tuple, base: tuple, modulus: int) -> tuple:
    if modulus <= 1:
        return (0,) * len(ldb)
    for candidate in product(range(modulus), repeat=len(ldb)):
        if all(
            (base[j] + sum(candidate[i] * ldb[i][j] for i in range(len(ldb)))) % modulus == 0
            for j in range(len(base))
        ):
            return candidate
    raise ValueError("no modular solution found for addabilization defactoring")


def _is_negative(a: tuple, is_contravariant: bool) -> bool:
    largest_minors = get_largest_minors_l(a)
    entry = trailing_entry if is_contravariant else leading_entry
    return entry(largest_minors) < 0
