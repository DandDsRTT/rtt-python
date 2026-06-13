"""Projection / embedding / unchanged-interval math: the rational tempering projection
P = GM, its generator embedding G, the held-interval basis that pins them, and the
dash-aware unchanged half U of the consolidated V = C|U column."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import sympy as sp

from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.temperament import Temperament, Variance

from rtt.app.service.core import (
    IntervalSizes,
    Tuning,
    _vectors_to_ratios,
    comma_ratios,
    interval_complexities,
    interval_sizes,
    interval_vector,
    mapped_commas,
)
from rtt.app.service.state import TemperamentState

_log = logging.getLogger(__name__)


def held_basis_vectors(state: TemperamentState, held_ratios) -> tuple:
    """The tuning's held interval basis as up to ``r`` INDEPENDENT domain vectors: the held
    intervals (the scheme's structural held plus the held column) parsed to vectors and reduced
    to a basis — dependent, out-of-domain, and beyond-rank entries are dropped. These are the
    KNOWN unchanged intervals of the tuning; a tuning holding fewer than ``r`` of them leaves the
    rest of the projection undetermined (see :func:`unchanged_interval_basis`). The order of
    ``held_ratios`` is preserved (the held column reads left to right)."""
    vectors: list = []
    rows: list = []
    for ratio in held_ratios:
        if len(vectors) >= state.r:
            break
        try:
            vector = interval_vector(ratio, state.d, state.domain_basis)
        except ValueError:
            continue
        if sp.Matrix(rows + [list(vector)]).rank() == len(rows) + 1:  # independent of those so far
            vectors.append(vector)
            rows.append(list(vector))
    return tuple(vectors)


def _all_primes_held(state: TemperamentState) -> tuple:
    """The ``d`` standard unit vectors — the held basis for the trivial temperament (``n = 0``),
    where nothing is tempered so every prime is unchanged and ``P = I``."""
    return tuple(tuple(1 if k == j else 0 for k in range(state.d)) for j in range(state.d))


def _projection_temperaments(state: TemperamentState, held_vectors):
    """The ``(mapping, held)`` :class:`Temperament` pair both ``P = GM`` and ``G`` are built from
    for a FULL-RANK held basis (``len == r``), or ``None`` when it can't be formed (an empty /
    over-full domain, or a basis that isn't full rank). Convention-free: held intervals are
    columns (COL)."""
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d or len(held_vectors) != r:
        return None
    mapping_t = Temperament(state.mapping, Variance.ROW, state.domain_basis)
    held_t = Temperament(held_vectors, Variance.COL, state.domain_basis)
    return mapping_t, held_t


def _held_for_projection(state: TemperamentState, held_ratios):
    """The held basis that pins ``P``/``G``: every prime for the trivial temperament (``n = 0``,
    JI), else the tuning's held interval basis from ``held_ratios``."""
    return _all_primes_held(state) if state.n == 0 else held_basis_vectors(state, held_ratios)


def _matrix_strings(matrix):
    """A rational matrix as a grid of display strings (``"1"``, ``"0"``, ``"1/4"``, ``"-1/3"``)."""
    return tuple(tuple(str(entry) for entry in row) for row in matrix)


def tuning_projection(state: TemperamentState, held_ratios=()):
    """The rational tempering projection ``P = GM`` as a ``d×d`` grid of display strings (``"1"``,
    ``"0"``, ``"1/4"`` …), or ``None`` when the tuning is NOT a full rational projection — its
    held basis isn't full rank ``r`` (it holds fewer than ``r`` rational intervals, so ``P`` is
    undetermined and the caller dashes it out) or is degenerate (a singular hold like pajara's
    ``{2/1, 7/5}``). ``held_ratios`` is the tuning's held interval basis (the scheme's structural
    held plus the held column) as ratio strings; the trivial temperament (``n = 0``) is JI, so
    ``P = I``. ``P`` sends each just prime to its tempered size (``j·P = t``), idempotent with the
    commas in its kernel."""
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return _matrix_strings(get_tempering_projection(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("tuning_projection dashed: %r", exc)
        return None


def tuning_embedding(state: TemperamentState, held_ratios=()):
    """The rational generator embedding ``G = H·(M·H)⁻¹`` as a ``d×r`` grid of display strings —
    its columns are the held tuning's generators as fractional prime vectors (the octave
    ``[1 0 0]`` and, for quarter-comma meantone, ``5^(1/4) = [0 0 1/4]``). ``held_ratios`` matches
    :func:`tuning_projection`, so ``P = GM`` stays in sync; ``None`` whenever ``P`` is (the held
    basis isn't full rank, or is degenerate), and the caller dashes the embedding box."""
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return _matrix_strings(get_generator_embedding(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("tuning_embedding dashed: %r", exc)
        return None


def projection_matrix_rationals(state: TemperamentState, held_ratios=()):
    """The rational tempering projection ``P = GM`` as the ``d×d`` matrix of ``Fraction`` entries —
    the numeric source behind :func:`tuning_projection`'s display strings, for multiplying vector
    sets through ``P`` (the projected lists P·D / P·H / P·T / P·interest). ``None`` in lockstep with
    :func:`tuning_projection` (an under-held / degenerate tuning is no rational projection)."""
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return get_tempering_projection(*inputs)
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("projection_matrix_rationals dashed: %r", exc)
        return None


def project_vectors(p_matrix, vectors):
    """Each ``d``-tall column vector ``v`` projected through ``P`` (``P·v``). Returns a tuple of
    ``d``-tall vectors (one per input column), or ``()`` when there is no projection (``p_matrix``
    is ``None`` — the caller dashes the tile) or no vectors. Plain matrix·vector products, reused
    by the spreadsheet's projection-row tiles and the matching plain-text bands."""
    if p_matrix is None or not vectors:
        return ()
    d = len(p_matrix)
    return tuple(
        tuple(sum(p_matrix[i][j] * v[j] for j in range(d)) for i in range(d))
        for v in vectors
    )


def _integer_columns(vectors):
    """sympy rational column vectors → primitive integer tuples (rows-as-intervals, like a comma
    basis): clear each to its lowest-terms integer form."""
    from math import gcd
    from functools import reduce
    out = []
    for v in vectors:
        entries = [sp.Rational(x) for x in v]
        lcm_d = 1
        for e in entries:
            lcm_d = lcm_d * int(e.q) // gcd(lcm_d, int(e.q))
        ints = [int(e * lcm_d) for e in entries]
        g = reduce(gcd, [abs(i) for i in ints], 0) or 1
        out.append(tuple(i // g for i in ints))
    return out


def unchanged_basis_from_projection(state: TemperamentState, projection):
    """The unchanged interval basis ``U`` recovered from a hand-edited projection matrix ``P`` (a
    ``d×d`` grid of fraction strings) — its eigenvalue-1 eigenvectors ``nullspace(P − I)`` as
    primitive integer interval vectors. ``None`` when the edit isn't a valid rational tempering
    projection of THIS temperament: not idempotent (``P² ≠ P``), the commas not in its kernel
    (``P·c ≠ 0``), or the wrong rank. The inverse of :func:`tuning_projection`, for the editable P."""
    try:
        d, r = state.d, state.r
        P = sp.Matrix([[sp.Rational(x) for x in row] for row in projection])
        if P.shape != (d, d) or P * P != P:  # must be idempotent
            return None
        for comma in state.comma_basis:  # the commas must vanish (be in the kernel)
            if P * sp.Matrix(comma) != sp.zeros(d, 1):
                return None
        U = _integer_columns((P - sp.eye(d)).nullspace())
        return tuple(U) if len(U) == r else None
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("unchanged_basis_from_projection dashed: %r", exc)
        return None


def unchanged_basis_from_embedding(state: TemperamentState, embedding):
    """The unchanged interval basis ``U`` recovered from a hand-edited generator embedding ``G`` (a
    ``d×r`` grid of fraction strings) — the integer basis of its column space (the generators span
    the held subspace). ``None`` when ``G`` isn't a valid embedding of this temperament: ``M·G ≠ I``
    (its generators don't map to themselves) or the wrong rank. The inverse of :func:`tuning_embedding`."""
    try:
        d, r = state.d, state.r
        G = sp.Matrix([[sp.Rational(x) for x in row] for row in embedding])
        M = sp.Matrix([list(row) for row in state.mapping])
        if G.shape != (d, r) or M * G != sp.eye(r):  # the generators must map to the identity
            return None
        U = _integer_columns(G.columnspace())
        return tuple(U) if len(U) == r else None
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("unchanged_basis_from_embedding dashed: %r", exc)
        return None


def unchanged_interval_basis(state: TemperamentState, held_ratios=()):
    """The unchanged interval basis ``U`` as exactly ``r`` columns: the tuning's held intervals
    (``h`` known, rational vectors, stored rows-as-intervals like the comma basis) padded to rank
    ``r`` with ``None`` — a DASHED column — for each direction the optimization leaves irrational.
    A tuning holding fewer than ``r`` rational intervals is not a full rational projection there,
    so those columns are unknown. Together with the comma basis ``C`` it forms ``V = C | U`` (the
    commas have eigenvalue 0, the unchanged 1). The trivial temperament (``n = 0``, JI) tempers
    nothing, so every prime is unchanged — ``U`` is all ``d`` primes with no dashes. ``held_ratios``
    is the tuning's held interval basis (scheme held + held column). ``None`` only on a degenerate
    domain (``d ≤ 0`` / ``r`` out of range)."""
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d:
        return None
    if state.n == 0:  # JI: every prime is unchanged (P = I), no irrational free directions
        return _all_primes_held(state)
    held = held_basis_vectors(state, held_ratios)
    return held + (None,) * (r - len(held))


def unchanged_interval_ratios(state: TemperamentState, held_ratios=()) -> tuple | None:
    """Each KNOWN unchanged interval as a ratio string (the unchanged-basis analogue of
    :func:`comma_ratios`) — the ``h`` held intervals; a DASHED (``None``) column has no ratio and
    is dropped here, so this can be shorter than ``r`` (use :func:`unchanged_interval_basis` for
    the full ``r``-column shape with dashes). ``None`` only when the basis can't be formed."""
    basis = unchanged_interval_basis(state, held_ratios)
    if basis is None:
        return None
    known = tuple(vector for vector in basis if vector is not None)
    return _vectors_to_ratios(known, state.domain_basis)


@dataclass(frozen=True)
class UnchangedData:
    """The unchanged half U of the consolidated V = C|U column, computed ONE way and shared by
    the grid and the plain text (so the two views can't diverge). Every field runs over the ``r``
    unchanged sub-columns, with ``None`` in the slots the under-held tuning leaves DASHED:
    ``basis`` the U vectors, ``ratios`` their ratio strings, ``mapped`` the M·U generator-coordinate
    rows (one per mapping row), ``sizes`` their tempered/just/error/damage cents, ``complexities``."""

    basis: tuple          # r entries: a domain vector, or None (dashed)
    ratios: tuple         # r entries: ratio string, or None
    mapped: tuple         # len(mapping) rows, each r entries (M·U), or None
    sizes: IntervalSizes  # each list r entries, with None for dashed
    complexities: tuple   # r entries, or None


def unchanged_interval_data(state: TemperamentState, held_ratios, tun: Tuning, scheme,
                            domain_basis=None, prescaler_override=None) -> UnchangedData | None:
    """Assemble the dash-aware unchanged half U of V — its vectors, ratios, mapped images, sizes
    and complexities — from the tuning's held basis. The derived twins are computed over the KNOWN
    columns only, then scattered back to the ``r`` positions (``None`` for each dashed column), so
    the grid's value tiles and the plain text both read one geometry. ``None`` when U can't form."""
    basis = unchanged_interval_basis(state, held_ratios)
    if basis is None:
        return None
    nu = len(basis)
    known = tuple(v for v in basis if v is not None)
    kidx = [j for j, v in enumerate(basis) if v is not None]

    def scatter(per_known):
        out = [None] * nu
        for pos, j in enumerate(kidx):
            out[j] = per_known[pos]
        return tuple(out)

    ratios = comma_ratios(known, domain_basis) if known else ()
    mapped = mapped_commas(state.mapping, known) if known else ()  # M·U over the known columns
    mapped_rows = tuple(scatter(mapped[i] if known else ()) for i in range(len(state.mapping)))
    sizes = interval_sizes(tun, ratios, domain_basis)
    sized = IntervalSizes(scatter(sizes.tempered), scatter(sizes.just),
                          scatter(sizes.errors), scatter(sizes.damage))
    comps = (interval_complexities(state.mapping, scheme, ratios,
                                   prescaler_override=prescaler_override, domain_basis=domain_basis)
             if known else ())
    return UnchangedData(basis, scatter(ratios), mapped_rows, sized, scatter(comps))


def unchanged_ratios_of_tuning(state: TemperamentState, retuning_map, candidate_ratios, tol=1e-6):
    """The ratio strings of the intervals the DISPLAYED tuning actually holds unchanged — its
    rational unchanged interval basis, read straight off the tuning rather than off the held
    column. An interval ``i`` is unchanged exactly when its damage is zero, i.e. the per-prime
    retuning map (tempered − just sizes) dotted with ``i`` is ``0``; genuine holds land at ``0``
    to floating-point precision while everything else is whole cents away, so the check is a clean
    threshold with no integer-relation guessing. We only TEST ``candidate_ratios`` (the held column
    first — so an interval the user deliberately holds is the representative chosen for its unchanged
    direction — then the temperament's established-projection bases, for clean representatives like
    ``5/4`` over ``5/2`` on the directions the optimizer holds on its own, then the target interval
    set), so a basis of the unchanged subspace is always among them, ORDERED so the held intervals
    win. Returns up to ``r`` independent ratios (fewer ⇒ the tuning isn't a full rational projection,
    and the caller dashes the rest); JI (``n = 0``) holds every prime."""
    d, r = state.d, state.r
    if d <= 0 or not 0 < r <= d:
        return ()
    if state.n == 0:  # JI: nothing is tempered, so every prime is unchanged
        return _vectors_to_ratios(_all_primes_held(state), state.domain_basis)
    rows, ratios = [], []
    for ratio in candidate_ratios:
        try:
            vector = interval_vector(ratio, d, state.domain_basis)
        except (ValueError, KeyError, IndexError):
            continue  # a candidate outside this domain (e.g. a 7-limit target on a 5-limit) — skip
        if abs(sum(retuning_map[p] * vector[p] for p in range(d))) >= tol:
            continue  # nonzero damage: the tuning changes this interval, so it isn't unchanged
        if sp.Matrix(rows + [list(vector)]).rank() == len(rows) + 1:  # independent of those found
            rows.append(list(vector))
            ratios.append(ratio)
            if len(ratios) == r:
                break
    return tuple(ratios)
