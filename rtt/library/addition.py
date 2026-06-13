from __future__ import annotations

import sympy as sp
from sympy.matrices.normalforms import smith_normal_decomp

from rtt.library.canonicalization import canonical_form
from rtt.library.dimensions import get_d, get_n, get_r
from rtt.library.domain_basis import get_domain_basis
from rtt.library.dual import dual
from rtt.library.list_utils import divide_out_gcd, leading_entry, trailing_entry
from rtt.library.matrix_utils import get_largest_minors_l, hnf, remove_all_zero_lists, transpose
from rtt.library.merging import comma_merge, map_merge
from rtt.library.temperament import Temperament, Variance


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
    # The temperament sum/difference is duality-independent, but the per-input
    # negation check (largest-minors orientation of the explicit-L_dep form) is
    # not: the Hodge dual carries a permutation sign the check ignores, so for
    # some addable pairs the two duality sides disagree about which input is
    # "negated" and silently swap sum<->difference. Pin the computation to one
    # canonical side (the guide's g_min single-vector side, COL on a tie) and
    # dualize the result back, so dual(sum_(M1, M2)) == sum_(dual M1, dual M2).
    output_variance = t1.variance
    compute_variance = _canonical_addition_variance(t1)
    if t1.variance is not compute_variance:
        t1, t2 = dual(t1), dual(t2)
    ldb = _get_linear_dependence_basis(t1, t2)  # raises if not addable
    v1 = _linear_independence_basis_vector(t1, ldb)
    v2 = _linear_independence_basis_vector(t2, ldb)
    combined = tuple(a + b if is_sum else a - b for a, b in zip(v1, v2))
    result = canonical_form(
        Temperament(tuple(ldb) + (combined,), t1.variance, t1.domain_basis)
    )
    return result if result.variance is output_variance else dual(result)


def _canonical_addition_variance(t: Temperament) -> Variance:
    """The duality side the addition is computed on: the smaller-grade (g_min)
    side, which for g_min == 1 is the guide's single-vector side; ties (r == n)
    resolve to the comma (COL) side."""
    return Variance.ROW if get_r(t) < get_n(t) else Variance.COL


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
    """Integer multiples ``x`` of the L_dep vectors such that, component-wise,
    ``base + sum_i x_i * ldb_i`` is divisible by ``modulus``.

    Solved exactly from the Smith normal form of the integer system
    ``A x + modulus * y = -base`` (``A`` holds the L_dep vectors as its columns),
    so the cost is a single matrix decomposition no matter how large the modulus.
    This is the guide's "eliminate the greatest factor piecemeal" prescription in
    closed form; it replaces a brute force over ``modulus ** len(ldb)`` candidates
    that grew without bound (tens of seconds, then effectively a hang, on ordinary
    13-limit rank-5 sums)."""
    k = len(ldb)
    if modulus <= 1 or k == 0:
        return (0,) * k
    width = len(base)
    a_rows = transpose(ldb)  # a_rows[j][i] == ldb[i][j]
    system = sp.Matrix(
        [
            list(a_rows[j]) + [modulus if col == j else 0 for col in range(width)]
            for j in range(width)
        ]
    )
    # left @ system @ right == diagonal (Smith normal form), left/right unimodular,
    # so system @ z == target  <=>  diagonal @ (right^-1 @ z) == left @ target.
    diagonal, left, right = smith_normal_decomp(system, domain=sp.ZZ)
    image = left * sp.Matrix([[-value] for value in base])
    n_cols = k + width
    reduced = [0] * n_cols
    for i in range(width):
        pivot = int(diagonal[i, i])
        value = int(image[i, 0])
        if pivot == 0:
            if value != 0:
                raise _no_modular_solution()
        elif value % pivot:
            raise _no_modular_solution()
        else:
            reduced[i] = value // pivot
    solution = right * sp.Matrix([[value] for value in reduced])
    return tuple(int(solution[i, 0]) for i in range(k))


def _no_modular_solution() -> ValueError:
    return ValueError("no modular solution found for addabilization defactoring")


def _is_negative(a: tuple, is_contravariant: bool) -> bool:
    largest_minors = get_largest_minors_l(a)
    entry = trailing_entry if is_contravariant else leading_entry
    return entry(largest_minors) < 0
