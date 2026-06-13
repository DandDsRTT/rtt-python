"""The chapter-9 superspace math: a nonstandard domain lifted onto its simplest
prime-only superspace — B_L, M_L, the lifted vector sets, the superspace tuning, and
the superspace projection row (P_L, G_L, G_L->s, P_L->s)."""

from __future__ import annotations

import logging
from dataclasses import replace
from fractions import Fraction

import sympy as sp

from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    get_simplest_prime_only_basis,
)
from rtt.library.dual import dual
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.matrix_utils import Matrix, matrix_multiply
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity_prescaler,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_scheme_names import resolve_tuning_scheme

from rtt.app.service.core import (
    DEFAULT_TUNING_SCHEME,
    Tuning,
    _to_matrix,
    _vectors_to_ratios,
)
from rtt.app.service.projection import (
    _held_for_projection,
    _matrix_strings,
    projection_matrix_rationals,
)
from rtt.app.service.state import TemperamentState

_log = logging.getLogger(__name__)


def superspace_primes(domain_basis) -> tuple[int, ...]:
    """The simplest prime-only basis containing the domain — the sorted unique primes that
    appear in any element's numerator or denominator. Over 2.3.13/5 (BARBADOS) the superspace
    primes are ``(2, 3, 5, 13)``: the rL × dL embedding the nonstandard-domain superspace
    region runs over. A standard / reordered prime basis passes through (sorted)."""
    return get_simplest_prime_only_basis(tuple(domain_basis))


def superspace_dimension(domain_basis) -> int:
    """The superspace's dimension dL — the number of primes the domain embeds into. Equal to
    ``len(superspace_primes(domain_basis))``; ≥ d, with equality iff the basis is already
    prime-only. For BARBADOS over 2.3.13/5: d=3 grows to dL=4 (the extra prime 13)."""
    return len(superspace_primes(domain_basis))


def basis_in_superspace(domain_basis) -> Matrix:
    """Each domain element as a vector over the superspace primes — the embedding matrix B_L
    the nonstandard-domain superspace region renders. Returned as a tuple of d ROWS of length
    dL (each row is one element), matching the comma-basis/target-vector storage convention
    in this module. The conceptual matrix is dL × d with elements as columns; transpose the
    stored value to consume it that way. For BARBADOS over 2.3.13/5 with superspace
    (2, 3, 5, 13): ``((1,0,0,0), (0,1,0,0), (0,0,-1,1))`` — 2→prime 2, 3→prime 3, 13/5→prime
    13 minus prime 5."""
    superspace = superspace_primes(domain_basis)
    elements = tuple(Fraction(e) for e in domain_basis)
    return tuple(
        tuple(int(x) for x in v)
        for v in express_quotients_in_domain_basis(elements, superspace)
    )


def superspace_mapping(state: TemperamentState) -> Matrix:
    """The temperament's mapping M_L re-expressed over its superspace primes — rL × dL,
    where rL = r + (dL − d) (nullity is preserved; the new primes contribute new generators).
    Derived by embedding the comma basis into the superspace and taking the dual: the
    public-API equivalent of the library's ``_change_to_simplest_prime_basis``. For BARBADOS
    over 2.3.13/5 it is the 3×4 integer mapping that tempers out 676/675 expressed over
    (2, 3, 5, 13)."""
    superspace = superspace_primes(state.domain_basis)
    comma_t = Temperament(state.comma_basis, Variance.COL, state.domain_basis)
    embedded = change_domain_basis_for_c(comma_t, superspace)
    return _to_matrix(dual(embedded).matrix)


def superspace_rank(state: TemperamentState) -> int:
    """rL, the rank of M_L over the superspace. Equals r + (dL − d): nullity is preserved
    by the embedding, so each extra prime adds one extra generator. For BARBADOS over
    2.3.13/5 (r=2, d=3, dL=4): rL = 3. A standard-prime temperament passes through unchanged."""
    return len(superspace_mapping(state))


def superspace_generators(state: TemperamentState) -> tuple[str, ...]:
    """Each superspace generator as an approximate ratio string — the rL generators of M_L
    over the superspace primes, the chapter-9 counterpart of :func:`generators`. Built by
    detempering the lifted mapping M_L (so the ratios are over the prime superspace, not the
    nonstandard domain). For BARBADOS over 2.3.13/5 with superspace (2, 3, 5, 13) it is the
    rL = 3 generators of the 3×4 mapping, e.g. ``('2/1', '26/3', '130/3')``."""
    superspace = superspace_primes(state.domain_basis)
    m = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    return _vectors_to_ratios(get_generator_detempering(m).matrix, superspace)


def superspace_just_mapping(primes) -> Matrix:
    """M_jL = I (dL × dL identity) — the just mapping over the superspace. Each prime in the
    superspace is its own basis element, so the just mapping is trivially the identity.
    Exposed as a named function so the layout renders it uniformly with the other superspace
    matrices. ``primes`` is the superspace prime tuple from :func:`superspace_primes`; only
    its length is read."""
    dl = len(tuple(primes))
    return tuple(tuple(1 if i == j else 0 for j in range(dl)) for i in range(dl))


def lift_vectors_to_superspace(domain_basis, vectors) -> Matrix:
    """Each domain interval vector (a length-d integer vector over the domain basis) re-expressed
    as a length-dL vector over the superspace primes — i.e. ``B_L · v`` for each. ``vectors`` is an
    iterable of length-d vectors stored rows-as-intervals (the comma basis, target vectors,
    held/interest vectors, the detempering columns); the result keeps that shape but each row is
    dL long. The lifted comma/target lists C_L / T_L the superspace block renders. For BARBADOS
    over 2.3.13/5 a vector touching the domain element 13/5 spreads across the 5 and 13 columns
    of the superspace (2, 3, 5, 13)."""
    bl = basis_in_superspace(domain_basis)  # d rows × dL: element e -> its superspace vector
    if not bl:
        return tuple(tuple() for _ in vectors)
    dL = len(bl[0])
    return tuple(
        tuple(sum(v[e] * bl[e][p] for e in range(len(bl))) for p in range(dL))
        for v in vectors
    )


def superspace_complexity_prescaler(
    state: TemperamentState, scheme: str = DEFAULT_TUNING_SCHEME,
) -> tuple[float, ...]:
    """The diagonal of the complexity prescaler over the SUPERSPACE primes — the dL pre-norm
    weights (log2 of each true prime for the default log-prime norm). This is the prescaler the
    neutral and prime-based approaches actually measure complexity with: both prime-factor, so
    complexity lives over the simplest prime-only basis, not the (possibly nonprime) domain. It
    feeds the "(superspace) complexity prescaler" tile (the bare L the prescaling row shows once
    the superspace primes column appears) AND — since the complexity of a lone prime is its own
    diagonal weight, ‖L[i]‖q = Lᵢᵢ — the "domain prime complexity map" values beneath it. The
    approach is forced neutral here: in a prime-only basis there is nothing to protect against
    factoring, so log-prime gives log2(prime) regardless. For BARBADOS over 2.3.13/5 with
    superspace (2, 3, 5, 13): ``(1.0, log2 3, log2 5, log2 13)``."""
    superspace = superspace_primes(state.domain_basis)
    t = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    spec = resolve_tuning_scheme(scheme)
    return tuple(
        get_complexity_prescaler(
            t, spec.complexity_log_prime_power, spec.complexity_prime_power, ""
        )
    )


def mapping_to_superspace_generators(state: TemperamentState) -> Matrix:
    """M_s→L = M_L · B_L — the rL × d matrix sending each domain element to its coordinates over
    the rL superspace generators (composing the basis embedding B_L, domain → superspace primes,
    with the superspace mapping M_L, superspace primes → superspace generators). The
    ``(ss_mapping, primes)`` tile: "mapping from domain intervals to superspace generators"."""
    ml = superspace_mapping(state)                 # rL × dL
    bl = basis_in_superspace(state.domain_basis)   # d × dL
    if not ml or not bl:
        return tuple()
    rL, dL, d = len(ml), len(ml[0]), len(bl)
    return tuple(
        tuple(sum(ml[g][p] * bl[e][p] for p in range(dL)) for e in range(d))
        for g in range(rL)
    )


def map_vectors_into_superspace_generators(state: TemperamentState, vectors) -> Matrix:
    """Each domain interval vector mapped to superspace-generator coordinates: ``M_s→L · v``. Mapped commas
    vanish to 0 (parallel to the on-domain mapped comma basis); mapped targets give the
    superspace-generator counts Y_L. ``vectors`` is rows-as-intervals (length d); the result is
    rows-as-intervals, each length rL."""
    msl = mapping_to_superspace_generators(state)  # rL × d
    if not msl:
        return tuple(tuple() for _ in vectors)
    rL, d = len(msl), len(msl[0])
    return tuple(
        tuple(sum(msl[g][e] * v[e] for e in range(d)) for g in range(rL))
        for v in vectors
    )


def superspace_self_map(state: TemperamentState) -> Matrix:
    """M_LgL = I (rL × rL identity) — the superspace mapping expressed over its own generators
    (each superspace generator maps to itself). The generator-space counterpart of M_jL = I."""
    rl = superspace_rank(state)
    return tuple(tuple(1 if i == j else 0 for j in range(rl)) for i in range(rl))


def superspace_tuning(
    state: TemperamentState, scheme: str = DEFAULT_TUNING_SCHEME, nonprime_approach: str = "",
    generator_override=None,
) -> Tuning:
    """The temperament's tuning over its superspace primes — the maps the nonstandard-domain
    superspace region needs (𝒈L, 𝒕L, 𝒋L, 𝒓L). Built by lifting the temperament to M_L over
    the prime superspace and running the same optimization the on-domain :func:`tuning` uses.
    Generator-tuning ranges are omitted (left as ``None``): the ranges chart isn't a superspace
    concept. ``nonprime_approach`` is accepted for signature parity with :func:`tuning` but has
    no effect — the superspace is prime-only by construction, so the optimizer ignores it.

    ``generator_override`` (an rL-tuple) freezes a MANUAL superspace generator tuning 𝒈L instead of
    optimizing — the prime-based approach's editable 𝒈L (the on-domain 𝒈's editing moves here). The
    superspace maps then read straight off it (𝒕L = 𝒈L·M_L); the on-domain maps are this 𝒈L
    projected back down (see :func:`project_superspace_generators_to_domain`)."""
    superspace = superspace_primes(state.domain_basis)
    ml = superspace_mapping(state)
    t = Temperament(ml, Variance.ROW, superspace)
    spec = resolve_tuning_scheme(scheme)
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if generator_override is not None:
        generator_map = tuple(float(g) for g in generator_override)
        tempered = tuple(float(x) for x in tuning_map_from_generators(t, generator_map))
    else:
        generator_map = optimize_generator_tuning_map(t, spec)
        tempered = optimize_tuning_map(t, spec)
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=generator_map,
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        monotone_generator_range=None,
        tradeoff_generator_range=None,
    )


def project_superspace_generators_to_domain(state: TemperamentState, ss_generators) -> tuple[float, ...]:
    """A manual superspace generator tuning 𝒈L (rL values) projected back to the original domain's
    r generators — the prime-based approach's final step (ch9 §9–10): lift 𝒈L to the superspace
    tempered map 𝒕L = 𝒈L·M_L, change basis down to the domain (𝒕 = 𝒕L·B_L), then recover the domain
    generators via the mapping's right-inverse. Feeding the result as the on-domain ``generator_tuning``
    makes every on-domain map track the edited 𝒈L, while 𝒈L itself shows the user's manual values."""
    superspace = superspace_primes(state.domain_basis)
    ml_t = Temperament(_to_matrix(superspace_mapping(state)), Variance.ROW, superspace)
    tL = tuning_map_from_generators(ml_t, tuple(float(g) for g in ss_generators))  # over superspace primes
    bl = basis_in_superspace(state.domain_basis)  # d rows × dL
    dL = len(superspace)
    t_s = tuple(sum(tL[p] * bl[e][p] for p in range(dL)) for e in range(len(bl)))  # domain tuning map
    domain_t = Temperament(_to_matrix(state.mapping), Variance.ROW, state.domain_basis)
    return tuple(float(g) for g in generator_tuning_map_from_t_and_tuning_map(domain_t, t_s))


def superspace_generator_embedding(state: TemperamentState, held_ratios=()):
    """The superspace generator embedding ``G_L→s`` (``d×rL``) — the embedding from the superspace
    generators to the subspace (domain) elements, the factor of the projection identity the mockup
    pins on P: ``P = G_L→s·M_s→L``. Since ``M_s→L`` (``rL×d``) can be rank-deficient when ``rL > r``
    (extra superspace primes add generators), it is solved as the least-squares right factor
    ``P·(M_s→L)⁺``. ``Fraction`` entries; ``None`` in lockstep with :func:`projection_matrix_rationals`
    (an under-held / degenerate tuning is no rational projection)."""
    p_rat = projection_matrix_rationals(state, held_ratios)
    if p_rat is None:
        return None
    msl = mapping_to_superspace_generators(state)
    if not msl:
        return None
    try:
        g = sp.Matrix([list(r) for r in p_rat]) * sp.Matrix([list(r) for r in msl]).pinv()
        return tuple(tuple(Fraction(g[i, j].p, g[i, j].q) for j in range(g.cols))
                     for i in range(g.rows))
    except (ArithmeticError, ValueError, IndexError, TypeError, AttributeError) as exc:
        _log.debug("superspace_generator_embedding dashed: %r", exc)
        return None


def superspace_prime_projection(state: TemperamentState, held_ratios=()):
    """The superspace-prime projection ``P_L→s`` (``d×dL``) ``= G_L→s·M_L`` — the projection from the
    superspace to the subspace, the superspace embedding of the on-domain projection (the on-domain
    ``P = P_L→s·B_Lᵀ`` is recovered by restricting to the domain subspace). ``None`` in lockstep with
    :func:`superspace_generator_embedding`."""
    g = superspace_generator_embedding(state, held_ratios)
    if g is None:
        return None
    return matrix_multiply(g, superspace_mapping(state))


def superspace_generator_embedding_display(state: TemperamentState, held_ratios=()):
    """``G_L→s`` as a grid of display strings, or ``None`` (dashed) when the tuning isn't a full
    rational projection — the projection-row tile in the superspace-generators column."""
    g = superspace_generator_embedding(state, held_ratios)
    return _matrix_strings(g) if g is not None else None


def superspace_prime_projection_display(state: TemperamentState, held_ratios=()):
    """``P_L→s`` as a grid of display strings, or ``None`` (dashed) in lockstep with ``G_L→s`` — the
    projection-row tile in the superspace-primes column."""
    p = superspace_prime_projection(state, held_ratios)
    return _matrix_strings(p) if p is not None else None


def _superspace_held_basis(state: TemperamentState, held_ratios, ml):
    """The held interval basis that pins ``P_L``, as ``rL`` independent ``dL``-tall vectors over the
    superspace primes (rows-as-intervals, the COL-variance storage convention), or ``None`` when the
    tuning isn't a full rational projection (its domain held basis isn't full rank ``r``).

    The domain held basis (every prime for the trivial ``n = 0`` temperament, else the tuning's held
    intervals) is lifted into the superspace (``B_L · held``) — ``r`` vectors spanning the held
    directions WITHIN the domain. The superspace adds ``dL − d`` dimensions OUTSIDE the domain that no
    comma touches (the commas all live in the domain), so they are held justly; the basis is filled out
    to rank ``rL`` by greedily taking the lowest superspace primes that extend ``M_L``'s image. Which
    off-domain prime is held there is a free choice the mockup pins no rule for — lowest-first mirrors
    :func:`held_basis_vectors`' greedy independence. The held intervals are kept unconditionally, so a
    tuning that tries to hold a tempered interval yields a rank-deficient ``M_L·held_L`` and dashes (the
    caller's :func:`get_tempering_projection` raises, caught as ``None``) — exactly like ``P``."""
    domain_held = _held_for_projection(state, held_ratios)
    if len(domain_held) != state.r:
        return None
    lifted = lift_vectors_to_superspace(state.domain_basis, domain_held)  # r vectors, dL tall
    rL, dL = len(ml), len(ml[0])
    m = sp.Matrix([list(row) for row in ml])  # rL × dL
    image_rank = lambda cols: (m * sp.Matrix.hstack(*cols)).rank() if cols else 0
    columns = [sp.Matrix(dL, 1, list(v)) for v in lifted]  # the held intervals, mandatory
    rank = image_rank(columns)
    for j in range(dL):  # fill to rank rL with the lowest superspace primes that extend M_L's image
        if len(columns) >= rL:
            break
        e = sp.Matrix(dL, 1, [1 if k == j else 0 for k in range(dL)])
        if image_rank(columns + [e]) > rank:
            columns.append(e)
            rank += 1
    if len(columns) != rL:
        return None
    return tuple(tuple(int(c[k]) for k in range(dL)) for c in columns)


def _superspace_projection_temperaments(state: TemperamentState, held_ratios):
    """The ``(M_L, held_L)`` :class:`Temperament` pair :func:`superspace_tuning_projection` feeds the
    convention-free :func:`get_tempering_projection`, or ``None`` when no full rational projection
    exists. ``M_L`` is the superspace mapping (ROW); ``held_L`` the lifted held basis as columns (COL)."""
    ml = _to_matrix(superspace_mapping(state))
    if not ml:
        return None
    held_L = _superspace_held_basis(state, held_ratios, ml)
    if held_L is None:
        return None
    superspace = superspace_primes(state.domain_basis)
    return (Temperament(ml, Variance.ROW, superspace),
            Temperament(held_L, Variance.COL, superspace))


def superspace_tuning_projection(state: TemperamentState, held_ratios=()):
    """The chapter-9 superspace tempering projection ``P_L = G_L·M_L`` as a ``dL × dL`` grid of display
    strings, or ``None`` when the tuning isn't a full rational projection (dashed, in lockstep with the
    on-domain :func:`tuning_projection`). The superspace analogue of ``P``: the domain projection lifted
    onto the prime superspace mapping ``M_L``, holding the same tuning's held intervals (lifted) and the
    untempered extra primes. Built with the SAME convention-free :func:`get_tempering_projection` ``P``
    uses, just over ``M_L`` and its lifted held basis. Reduces to ``P`` over a standard prime basis
    (``dL = d``); ``I_dL`` for the trivial temperament (``n = 0``)."""
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return _matrix_strings(get_tempering_projection(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError) as exc:
        _log.debug("superspace_tuning_projection dashed: %r", exc)
        return None


def superspace_projection_matrix_rationals(state: TemperamentState, held_ratios=()):
    """The superspace projection ``P_L = G_L·M_L`` as the ``dL × dL`` matrix of ``Fraction`` entries —
    the numeric source behind :func:`superspace_tuning_projection`'s display strings, for projecting the
    lifted vector sets through ``P_L`` (the row's ``P_L·B_Ls`` / ``P_L·D_L`` / ``P_L·V_L`` / … tiles).
    ``None`` in lockstep with :func:`superspace_tuning_projection`."""
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return get_tempering_projection(*inputs)
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None


def superspace_tuning_embedding(state: TemperamentState, held_ratios=()):
    """The superspace generator embedding ``G_L = H_L·(M_L·H_L)⁻¹`` as a ``dL × rL`` grid of display
    strings — its columns are the held tuning's superspace generators as fractional superspace-prime
    vectors, the embedding factor of ``P_L = G_L·M_L`` (the projection row's superspace-generators tile,
    the chapter-9 analogue of the on-domain ``G``). ``None`` (dashed) in lockstep with
    :func:`superspace_tuning_projection`."""
    try:
        inputs = _superspace_projection_temperaments(state, held_ratios)
        if inputs is None:
            return None
        return _matrix_strings(get_generator_embedding(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None
