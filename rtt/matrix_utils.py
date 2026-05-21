from __future__ import annotations

from fractions import Fraction
from itertools import combinations

import sympy as sp

from rtt.list_utils import divide_out_gcd

Matrix = tuple[tuple[int, ...], ...]


def inverse(x):
    """Polymorphic inverse: a 2D matrix becomes its exact rational matrix inverse, a 1D
    vector its element-wise reciprocals, and a scalar its reciprocal."""
    if not isinstance(x, (list, tuple)):
        return Fraction(1) / Fraction(x)
    if x and isinstance(x[0], (list, tuple)):
        inverted = sp.Matrix([list(row) for row in x]).inv()
        return tuple(
            tuple(Fraction(int(entry.p), int(entry.q)) for entry in row)
            for row in inverted.tolist()
        )
    return tuple(Fraction(1) / Fraction(value) for value in x)


def reverse_inner_l(matrix: Matrix) -> Matrix:
    """Reverse the entries within each row."""
    return tuple(tuple(reversed(row)) for row in matrix)


def reverse_outer_l(matrix: Matrix) -> Matrix:
    """Reverse the order of the rows."""
    return tuple(reversed(matrix))


def rotate_180(matrix: Matrix) -> Matrix:
    """Rotate the matrix 180° (reverse both rows and the entries within them)."""
    return reverse_inner_l(reverse_outer_l(matrix))


def inner_l_length(matrix: Matrix) -> int:
    """The number of columns (length of each row)."""
    return len(matrix[0])


def all_zeros(matrix: Matrix) -> bool:
    return all(x == 0 for row in matrix for x in row)


def remove_all_zero_lists(matrix: Matrix) -> Matrix:
    """Drop every all-zero row (may yield an empty matrix)."""
    return tuple(row for row in matrix if any(x != 0 for x in row))


def remove_unneeded_zero_lists(matrix: Matrix) -> Matrix:
    """Drop all-zero rows, but keep a single zero row if the matrix is all zeros."""
    if not matrix:
        return matrix
    if all_zeros(matrix):
        return ((0,) * len(matrix[0]),)
    return remove_all_zero_lists(matrix)


def transpose(matrix: Matrix) -> Matrix:
    return tuple(zip(*matrix)) if matrix else ()


def matrix_multiply(a: Matrix, b: Matrix) -> Matrix:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0])))
        for i in range(len(a))
    )


def get_largest_minors_l(matrix: Matrix) -> tuple[int, ...]:
    """The rank-order minors (first row-subset, all column-subsets), gcd divided out."""
    m = sp.Matrix(matrix)
    rank = m.rank()
    row_subset = next(iter(combinations(range(m.rows), rank)))
    minors = [
        int(m.extract(list(row_subset), list(col_subset)).det())
        for col_subset in combinations(range(m.cols), rank)
    ]
    return divide_out_gcd(tuple(minors))


def hnf(matrix: Matrix) -> Matrix:
    """Row-style Hermite Normal Form (Wolfram convention)."""
    return hnf_with_transform(matrix)[1]


def hnf_with_transform(matrix: Matrix) -> tuple[Matrix, Matrix]:
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


def smith_normal_form_with_transforms(matrix: Matrix) -> tuple[Matrix, Matrix, Matrix]:
    """Smith Normal Form with the unimodular transforms U, V s.t. U @ matrix @ V == S."""
    rows = [list(row) for row in matrix]
    m = len(rows)
    n = len(rows[0]) if rows else 0
    left = [[int(i == j) for j in range(m)] for i in range(m)]
    right = [[int(i == j) for j in range(n)] for i in range(n)]

    def add_row(target, source, q):
        rows[target] = [a + q * b for a, b in zip(rows[target], rows[source])]
        left[target] = [a + q * b for a, b in zip(left[target], left[source])]

    def add_col(target, source, q):
        for row in rows:
            row[target] += q * row[source]
        for row in right:
            row[target] += q * row[source]

    def swap_rows(a, b):
        rows[a], rows[b] = rows[b], rows[a]
        left[a], left[b] = left[b], left[a]

    def swap_cols(a, b):
        for row in rows:
            row[a], row[b] = row[b], row[a]
        for row in right:
            row[a], row[b] = row[b], row[a]

    t = 0
    while t < min(m, n):
        if all(rows[i][j] == 0 for i in range(t, m) for j in range(t, n)):
            break
        if rows[t][t] == 0:  # bring some nonzero into the pivot position
            spot = next((i, j) for i in range(t, m) for j in range(t, n) if rows[i][j])
            swap_rows(t, spot[0])
            swap_cols(t, spot[1])
        while True:  # isolate (t, t) by alternating column/row reduction
            pivot = min((i for i in range(t, m) if rows[i][t]), key=lambda i: abs(rows[i][t]))
            swap_rows(t, pivot)
            for i in range(t + 1, m):
                if rows[i][t]:
                    add_row(i, t, -(rows[i][t] // rows[t][t]))
            if any(rows[i][t] for i in range(t + 1, m)):
                continue
            pivot = min((j for j in range(t, n) if rows[t][j]), key=lambda j: abs(rows[t][j]))
            swap_cols(t, pivot)
            for j in range(t + 1, n):
                if rows[t][j]:
                    add_col(j, t, -(rows[t][j] // rows[t][t]))
            if any(rows[t][j] for j in range(t + 1, n)):
                continue
            break
        offending = next(
            (
                i
                for i in range(t + 1, m)
                for j in range(t + 1, n)
                if rows[i][j] % rows[t][t]
            ),
            None,
        )
        if offending is not None:
            add_row(t, offending, 1)
            continue
        if rows[t][t] < 0:
            rows[t] = [-x for x in rows[t]]
            left[t] = [-x for x in left[t]]
        t += 1
    return _to_matrix(left), _to_matrix(rows), _to_matrix(right)


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


def _to_matrix(rows: list[list[int]]) -> Matrix:
    return tuple(tuple(row) for row in rows)
