"""Pure superspace / held-basis linear algebra (chapter 9): applying a matrix to a list
of vectors, lifting domain vectors through a basis embedding, composing a lifted mapping
with that embedding, greedy independent-row reduction, completing a held basis to full
image rank, and the least-squares left-factor recovery behind the superspace projection
row. Everything here is a pure function over integer / rational matrices and vectors —
the ratio-string parsing and display conversions live in the app's service wrappers."""

from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.library.matrix_utils import Matrix, matrix_multiply, transpose


def apply_matrix_to_vectors(matrix, vectors) -> tuple:
    """``matrix · v`` for each vector — plain matrix·vector products over a list of vectors
    stored rows-as-intervals (the comma-basis storage convention), returned the same way.
    Entries may be ints, Fractions, or floats; an empty matrix maps every vector to the
    empty tuple, and no vectors yields ``()``."""
    return tuple(
        tuple(sum(row[j] * v[j] for j in range(len(row))) for row in matrix)
        for v in vectors
    )


def lift_vectors(basis_embedding: Matrix, vectors) -> tuple:
    """Each length-d vector re-expressed over the superspace primes: ``B_L · v``, i.e.
    ``v ↦ Σₑ vₑ · B_L[e]``. ``basis_embedding`` is B_L stored as d ROWS of length dL (each
    row one domain element over the superspace primes); ``vectors`` are rows-as-intervals
    of length d, and the result keeps that shape with rows dL long."""
    return apply_matrix_to_vectors(transpose(basis_embedding), vectors)


def compose_mapping_with_embedding(mapping: Matrix, basis_embedding: Matrix) -> Matrix:
    """``M_L · B_Lᵀ`` — the rL × d composite sending each domain element straight to its
    coordinates over the rL superspace generators (``basis_embedding`` stored d rows × dL,
    as in :func:`lift_vectors`). ``()`` when either factor is empty."""
    if not mapping or not basis_embedding:
        return ()
    return matrix_multiply(mapping, transpose(basis_embedding))


def greedy_independent_rows(vectors, limit: int) -> tuple:
    """The given vectors greedily reduced to an independent set: each row is kept iff it is
    linearly independent of those already kept, stopping at ``limit`` rows. Order is
    preserved (earlier rows win), and the kept rows are returned as given."""
    kept: list = []
    rows: list = []
    for vector in vectors:
        if len(kept) >= limit:
            break
        if sp.Matrix(rows + [list(vector)]).rank() == len(rows) + 1:  # independent so far
            kept.append(vector)
            rows.append(list(vector))
    return tuple(kept)


def extend_to_full_image_rank(mapping: Matrix, vectors) -> Matrix | None:
    """The given column vectors (rows-as-intervals, kept unconditionally and in order)
    extended to rL columns by greedily appending the lowest standard unit vectors whose
    image under ``mapping`` (rL × dL) extends the image of the columns so far. ``None``
    when the fill comes up short of rL (no remaining unit vector extends the image — the
    mapping's row rank is below rL). The mandatory vectors are NOT rank-checked: a full
    (length-rL) degenerate set comes back as given, for the caller's downstream inversion
    to detect."""
    rL, dL = len(mapping), len(mapping[0])
    m = sp.Matrix([list(row) for row in mapping])  # rL × dL
    image_rank = lambda cols: (m * sp.Matrix.hstack(*cols)).rank() if cols else 0
    columns = [sp.Matrix(dL, 1, list(v)) for v in vectors]  # the given vectors, mandatory
    rank = image_rank(columns)
    for j in range(dL):  # fill to rank rL with the lowest unit vectors that extend the image
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
    """The least-squares X with ``X · right_factor ≈ product``: ``product · right_factor⁺``
    via the sympy pseudoinverse (exact over rationals), as a matrix of ``Fraction`` entries.
    The pseudoinverse handles a rank-deficient ``right_factor``, where a plain right-inverse
    would not exist; when ``product`` does factor exactly the result is an exact factor."""
    x = (sp.Matrix([list(row) for row in product])
         * sp.Matrix([list(row) for row in right_factor]).pinv())
    return tuple(
        tuple(Fraction(x[i, j].p, x[i, j].q) for j in range(x.cols))
        for i in range(x.rows)
    )
