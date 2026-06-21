from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.library.matrix_utils import Matrix, matrix_multiply, transpose


def apply_matrix_to_vectors(matrix, vectors) -> tuple:
    return tuple(
        tuple(sum(row[j] * v[j] for j in range(len(row))) for row in matrix) for v in vectors
    )


def lift_vectors(basis_embedding: Matrix, vectors) -> tuple:
    return apply_matrix_to_vectors(transpose(basis_embedding), vectors)


def compose_mapping_with_embedding(mapping: Matrix, basis_embedding: Matrix) -> Matrix:
    if not mapping or not basis_embedding:
        return ()
    return matrix_multiply(mapping, transpose(basis_embedding))


def greedy_independent_rows(vectors, limit: int) -> tuple:
    kept: list = []
    rows: list = []
    for vector in vectors:
        if len(kept) >= limit:
            break
        if sp.Matrix(rows + [list(vector)]).rank() == len(rows) + 1:
            kept.append(vector)
            rows.append(list(vector))
    return tuple(kept)


def extend_to_full_image_rank(mapping: Matrix, vectors) -> Matrix | None:
    rL, dL = len(mapping), len(mapping[0])
    m = sp.Matrix([list(row) for row in mapping])
    image_rank = lambda cols: (m * sp.Matrix.hstack(*cols)).rank() if cols else 0
    columns = [sp.Matrix(dL, 1, list(v)) for v in vectors]
    rank = image_rank(columns)
    for j in range(dL):
        if len(columns) >= rL:
            break
        e = sp.Matrix(dL, 1, [1 if k == j else 0 for k in range(dL)])
        if image_rank(columns + [e]) > rank:
            columns.append(e)
            rank += 1
    if len(columns) != rL:
        return None
    return tuple(tuple(int(c[k]) for k in range(dL)) for c in columns)


def least_squares_left_factor(product, right_factor) -> tuple:
    x = (
        sp.Matrix([list(row) for row in product])
        * sp.Matrix([list(row) for row in right_factor]).pinv()
    )
    return tuple(
        tuple(Fraction(x[i, j].p, x[i, j].q) for j in range(x.cols)) for i in range(x.rows)
    )
