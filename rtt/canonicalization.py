from __future__ import annotations

import sympy as sp

from rtt.temperament import Temperament, Variance

Matrix = tuple[tuple[int, ...], ...]


def canonical_form(t: Temperament) -> Temperament:
    """Canonical form of a temperament, by its mapping or comma-basis variance."""
    canonicalize = canonical_ca if t.variance is Variance.COL else canonical_ma
    return Temperament(canonicalize(t.matrix), t.variance, t.domain_basis)


def canonical_ma(matrix: Matrix) -> Matrix:
    """Canonical form of a mapping: defactored, then Hermite Normal Form."""
    inner = matrix if _all_zeros(matrix) else _hnf(col_hermite_defactor(matrix))
    return _remove_unneeded_zero_lists(inner)


def canonical_ca(matrix: Matrix) -> Matrix:
    """Canonical form of a comma basis: canonical_ma between two 180° rotations."""
    return _rotate_180(canonical_ma(_rotate_180(matrix)))


def _rotate_180(matrix: Matrix) -> Matrix:
    return tuple(tuple(reversed(row)) for row in reversed(matrix))


def col_hermite_defactor(matrix: Matrix) -> Matrix:
    """A saturated (defactored) basis spanning the same rational row space."""
    rank = sp.Matrix(matrix).rank()
    inverse = sp.Matrix(hermite_right_unimodular(matrix)).inv().tolist()
    return tuple(tuple(int(x) for x in inverse[i]) for i in range(rank))


def hermite_right_unimodular(matrix: Matrix) -> Matrix:
    transform, _ = _hnf_with_transform(_transpose(matrix))
    return _transpose(transform)


def _hnf(matrix: Matrix) -> Matrix:
    """Row-style Hermite Normal Form (Wolfram convention)."""
    return _hnf_with_transform(matrix)[1]


def _hnf_with_transform(matrix: Matrix) -> tuple[Matrix, Matrix]:
    """Row HNF plus the unimodular transform U such that ``U @ matrix == H``.

    H is in echelon form with pivots descending left-to-right, positive pivots,
    and entries strictly above each pivot reduced into ``[0, pivot)``.
    """
    rows = [list(row) for row in matrix]
    size = len(rows)
    transform = [[int(i == j) for j in range(size)] for i in range(size)]
    if size == 0:
        return (), ()
    n_cols = len(rows[0])
    pivot_row = 0
    for col in range(n_cols):
        if pivot_row >= size:
            break
        _reduce_column_to_pivot(rows, transform, pivot_row, col)
        if rows[pivot_row][col] == 0:
            continue
        if rows[pivot_row][col] < 0:
            rows[pivot_row] = [-x for x in rows[pivot_row]]
            transform[pivot_row] = [-x for x in transform[pivot_row]]
        pivot = rows[pivot_row][col]
        for r in range(pivot_row):
            q = rows[r][col] // pivot
            if q:
                rows[r] = [a - q * b for a, b in zip(rows[r], rows[pivot_row])]
                transform[r] = [a - q * b for a, b in zip(transform[r], transform[pivot_row])]
        pivot_row += 1
    return _to_matrix(transform), _to_matrix(rows)


def _reduce_column_to_pivot(
    rows: list[list[int]], transform: list[list[int]], pivot_row: int, col: int
) -> None:
    """Euclidean-reduce ``col`` so only ``rows[pivot_row]`` is nonzero at/below it."""
    while True:
        nonzero = [r for r in range(pivot_row, len(rows)) if rows[r][col] != 0]
        if not nonzero:
            return
        smallest = min(nonzero, key=lambda r: abs(rows[r][col]))
        if smallest != pivot_row:
            rows[pivot_row], rows[smallest] = rows[smallest], rows[pivot_row]
            transform[pivot_row], transform[smallest] = transform[smallest], transform[pivot_row]
        reduced = False
        for r in range(pivot_row + 1, len(rows)):
            if rows[r][col] != 0:
                q = rows[r][col] // rows[pivot_row][col]
                rows[r] = [a - q * b for a, b in zip(rows[r], rows[pivot_row])]
                transform[r] = [a - q * b for a, b in zip(transform[r], transform[pivot_row])]
                reduced = True
        if not reduced:
            return


def _transpose(matrix: Matrix) -> Matrix:
    return tuple(zip(*matrix)) if matrix else ()


def _to_matrix(rows: list[list[int]]) -> Matrix:
    return tuple(tuple(row) for row in rows)


def _all_zeros(matrix: Matrix) -> bool:
    return all(all(x == 0 for x in row) for row in matrix)


def _remove_unneeded_zero_lists(matrix: Matrix) -> Matrix:
    if not matrix:
        return matrix
    if _all_zeros(matrix):
        return ((0,) * len(matrix[0]),)
    return tuple(row for row in matrix if any(x != 0 for x in row))
