from __future__ import annotations

from fractions import Fraction
from itertools import combinations

import sympy as sp

from rtt.library.list_utils import divide_out_gcd

Matrix = tuple[tuple[int, ...], ...]


def inverse(x):
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
    return tuple(tuple(reversed(row)) for row in matrix)


def reverse_outer_l(matrix: Matrix) -> Matrix:
    return tuple(reversed(matrix))


def rotate_180(matrix: Matrix) -> Matrix:
    return reverse_inner_l(reverse_outer_l(matrix))


def inner_l_length(matrix: Matrix) -> int:
    return len(matrix[0])


def all_zeros(matrix: Matrix) -> bool:
    return all(x == 0 for row in matrix for x in row)


def remove_all_zero_lists(matrix: Matrix) -> Matrix:
    return tuple(row for row in matrix if any(x != 0 for x in row))


def remove_unneeded_zero_lists(matrix: Matrix) -> Matrix:
    if not matrix:
        return matrix
    if all_zeros(matrix):
        return ((0,) * len(matrix[0]),)
    return remove_all_zero_lists(matrix)


def transpose(matrix: Matrix) -> Matrix:
    return tuple(zip(*matrix, strict=False)) if matrix else ()


def matrix_multiply(a: Matrix, b: Matrix) -> Matrix:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0])))
        for i in range(len(a))
    )


def get_largest_minors_l(matrix: Matrix) -> tuple[int, ...]:
    m = sp.Matrix(matrix)
    rank = m.rank()
    row_subset = next(iter(combinations(range(m.rows), rank)))
    minors = [
        int(m.extract(list(row_subset), list(col_subset)).det())
        for col_subset in combinations(range(m.cols), rank)
    ]
    return divide_out_gcd(tuple(minors))


def hnf(matrix: Matrix) -> Matrix:
    return hnf_with_transform(matrix)[1]


def hnf_with_transform(matrix: Matrix) -> tuple[Matrix, Matrix]:
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
                rows[r] = [a - q * b for a, b in zip(rows[r], rows[pivot_row], strict=False)]
                transform[r] = [
                    a - q * b for a, b in zip(transform[r], transform[pivot_row], strict=False)
                ]
        pivot_row += 1
    return _to_matrix(transform), _to_matrix(rows)


class _SmithReduction:
    def __init__(self, matrix: Matrix):
        self.rows = [list(row) for row in matrix]
        self.row_count = len(self.rows)
        self.column_count = len(self.rows[0]) if self.rows else 0
        self.left = [[int(i == j) for j in range(self.row_count)] for i in range(self.row_count)]
        self.right = [
            [int(i == j) for j in range(self.column_count)] for i in range(self.column_count)
        ]

    def _add_row(self, target, source, q):
        r, ll = self.rows, self.left
        r[target] = [a + q * b for a, b in zip(r[target], r[source], strict=False)]
        ll[target] = [a + q * b for a, b in zip(ll[target], ll[source], strict=False)]

    def _add_col(self, target, source, q):
        for row in self.rows:
            row[target] += q * row[source]
        for row in self.right:
            row[target] += q * row[source]

    def _swap_rows(self, a, b):
        self.rows[a], self.rows[b] = self.rows[b], self.rows[a]
        self.left[a], self.left[b] = self.left[b], self.left[a]

    def _swap_cols(self, a, b):
        for row in self.rows:
            row[a], row[b] = row[b], row[a]
        for row in self.right:
            row[a], row[b] = row[b], row[a]

    def _bring_nonzero_to_corner(self, t):
        if self.rows[t][t] != 0:
            return
        spot = next(
            (i, j)
            for i in range(t, self.row_count)
            for j in range(t, self.column_count)
            if self.rows[i][j]
        )
        self._swap_rows(t, spot[0])
        self._swap_cols(t, spot[1])

    def _clear_below_pivot(self, t):
        pivot = min(
            (i for i in range(t, self.row_count) if self.rows[i][t]),
            key=lambda i: abs(self.rows[i][t]),
        )
        self._swap_rows(t, pivot)
        for i in range(t + 1, self.row_count):
            if self.rows[i][t]:
                self._add_row(i, t, -(self.rows[i][t] // self.rows[t][t]))
        return any(self.rows[i][t] for i in range(t + 1, self.row_count))

    def _clear_right_of_pivot(self, t):
        pivot = min(
            (j for j in range(t, self.column_count) if self.rows[t][j]),
            key=lambda j: abs(self.rows[t][j]),
        )
        self._swap_cols(t, pivot)
        for j in range(t + 1, self.column_count):
            if self.rows[t][j]:
                self._add_col(j, t, -(self.rows[t][j] // self.rows[t][t]))
        return any(self.rows[t][j] for j in range(t + 1, self.column_count))

    def _reduce_pivot_cross(self, t):
        while self._clear_below_pivot(t) or self._clear_right_of_pivot(t):
            pass

    def _offending_row(self, t):
        cross = (
            (i, j) for i in range(t + 1, self.row_count) for j in range(t + 1, self.column_count)
        )
        return next((i for i, j in cross if self.rows[i][j] % self.rows[t][t]), None)

    def _normalize_pivot_sign(self, t):
        if self.rows[t][t] < 0:
            self.rows[t] = [-x for x in self.rows[t]]
            self.left[t] = [-x for x in self.left[t]]

    def _all_zero_from(self, t):
        return all(
            self.rows[i][j] == 0
            for i in range(t, self.row_count)
            for j in range(t, self.column_count)
        )

    def reduce(self):
        t = 0
        while t < min(self.row_count, self.column_count):
            if self._all_zero_from(t):
                break
            self._bring_nonzero_to_corner(t)
            self._reduce_pivot_cross(t)
            offending = self._offending_row(t)
            if offending is not None:
                self._add_row(t, offending, 1)
                continue
            self._normalize_pivot_sign(t)
            t += 1
        return self


def smith_normal_form_with_transforms(matrix: Matrix) -> tuple[Matrix, Matrix, Matrix]:
    reduction = _SmithReduction(matrix).reduce()
    return _to_matrix(reduction.left), _to_matrix(reduction.rows), _to_matrix(reduction.right)


def _reduce_column_to_pivot(
    rows: list[list[int]], transform: list[list[int]], pivot_row: int, col: int
) -> None:
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
                rows[r] = [a - q * b for a, b in zip(rows[r], rows[pivot_row], strict=False)]
                transform[r] = [
                    a - q * b for a, b in zip(transform[r], transform[pivot_row], strict=False)
                ]
                reduced = True
        if not reduced:
            return


def _to_matrix(rows: list[list[int]]) -> Matrix:
    return tuple(tuple(row) for row in rows)
