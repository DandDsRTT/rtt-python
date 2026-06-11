"""The sole seam between the web UI and the RTT library.

Everything the front end needs is expressed here in plain tuples/ints/strings so
the UI never imports library types directly. A :class:`TemperamentState` bundles
a temperament's mapping and its dual comma basis (kept in sync) plus dimensions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from functools import reduce
from math import lcm

import sympy as sp

from rtt.library.canonicalization import canonical_ca, canonical_ma
from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.dimensions import get_d, get_n, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.dual import dual
from rtt.library.formatting import strip_negative_zero, to_ebk
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.math_utils import get_primes, pcv_to_quotient, quotient_to_pcv
from rtt.library.matrix_utils import Matrix, matrix_multiply
from rtt.library.parsing import parse_quotient_list, parse_temperament_data
from rtt.library.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    damage_weights,
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity,
    get_complexity_prescaler,
    get_dual_power,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_ranges import get_generator_tuning_range as _get_generator_tuning_range


def get_generator_tuning_range(t, mode):
    """The generator tuning range for the I-beam range chart, or ``None`` when the range solver
    can't measure this basis. The odd-limit diamond it works over isn't defined for every
    nonstandard subgroup — a mixed basis like ``2.3.5.13/5`` (where 5 and 13/5 share the prime 5)
    yields 0-width diamond vectors and the projection through the mapping fails. The range is a
    chart-only nicety with no bearing on the tuning itself, so a basis it can't measure simply
    shows no range — the same ``None`` the superspace tuning already uses for its (range-less) maps."""
    try:
        return _get_generator_tuning_range(t, mode)
    except (ValueError, IndexError):
        return None
from rtt.library.tuning_scheme_names import (
    TuningSchemeSpec,
    annotation_code,
    complexity_name_traits,
    resolve_tuning_scheme,
    systematic_name,
)

DEFAULT_TUNING_SCHEME = "minimax-S"  # the canonical all-interval scheme — the compute/helper
# default (where a complete self-contained scheme is wanted) and the all-interval form the chooser
# anchors on. NOT the as-shipped document scheme (see DEFAULT_DOCUMENT_SCHEME).
DEFAULT_TARGET_SPEC = "TILT"  # the default target interval set family (tracks the domain)
# The as-shipped document scheme the editor and a fresh build start from: target-based (the
# default TILT family) and UNITY-weighted. All-interval schemes are simplicity-weighted by
# construction, but the target-based default is plain unity weight (minimax-U, not minimax-S).
DEFAULT_DOCUMENT_SCHEME = f"{DEFAULT_TARGET_SPEC} minimax-U"


@dataclass(frozen=True)
class Tuning:
    """The temperament-level tuning — prime maps and generator ranges, independent
    of any interval set."""

    generator_map: tuple[float, ...]  # cents, over the generators
    tuning_map: tuple[float, ...]  # cents, over the domain primes
    just_map: tuple[float, ...]  # cents, over the domain primes
    retuning_map: tuple[float, ...]  # tempered - just, over the primes
    monotone_generator_range: tuple[tuple[float, float], ...] | None  # per generator; None if none exists
    tradeoff_generator_range: tuple[tuple[float, float], ...] | None  # (low, high) cents/gen; None if octave tempers out


@dataclass(frozen=True)
class IntervalSizes:
    """An interval set's sizes under a tuning; each list runs over the intervals.

    Used for every interval column (targets, commas, other intervals of interest):
    project the set once through the shared prime maps rather than recomputing the
    optimization per set."""

    tempered: tuple[float, ...]  # cents
    just: tuple[float, ...]  # cents
    errors: tuple[float, ...]  # tempered - just
    damage: tuple[float, ...]  # 𝐝 = |error|·weight (|error| when no weights passed: unity)


@dataclass(frozen=True)
class TemperamentState:
    mapping: Matrix
    comma_basis: Matrix
    d: int
    r: int
    n: int
    domain_basis: tuple  # the d basis elements (ints / Fractions); standard primes by default


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


def _is_matrix(x) -> bool:
    """Whether a complexity-pretransformer override is a full d×d matrix (a sequence of rows) rather
    than a flat diagonal d-tuple — the editable square's non-diagonal form. Plain-Python (no numpy,
    keeping this module's tuple-only surface): a matrix's first entry is itself a sequence."""
    return bool(x) and isinstance(x[0], (tuple, list))


def _state(mapping: Matrix, comma_basis: Matrix, domain_basis=None) -> TemperamentState:
    m = Temperament(mapping, Variance.ROW, domain_basis)
    return TemperamentState(
        mapping, comma_basis, get_d(m), get_r(m), get_n(m), tuple(get_domain_basis(m))
    )


def from_mapping(mapping, domain_basis=None) -> TemperamentState:
    """State whose source of truth is ``mapping``; comma basis is its dual.

    ``domain_basis`` (a tuple of basis elements, possibly nonprime) names a
    nonstandard domain; ``None`` is the standard prime limit."""
    mapping = _to_matrix(mapping)
    comma_basis = dual(Temperament(mapping, Variance.ROW, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def from_comma_basis(comma_basis, domain_basis=None) -> TemperamentState:
    """State whose source of truth is ``comma_basis``; mapping is its dual."""
    comma_basis = _to_matrix(comma_basis)
    mapping = dual(Temperament(comma_basis, Variance.COL, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def from_temperament_data(ebk: str) -> TemperamentState:
    """State parsed from an EBK string, honouring an optional domain-basis prefix
    (e.g. ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"``). A map string is taken as the mapping,
    a vector string as the comma basis; the dual is computed as usual."""
    t = parse_temperament_data(ebk)
    if t.variance is Variance.ROW:
        return from_mapping(t.matrix, t.domain_basis)
    return from_comma_basis(t.matrix, t.domain_basis)


def mapping_ebk(state: TemperamentState) -> str:
    """The temperament's mapping as an EBK string — the editable dual the grid shows and
    the form persistence stores. A nonstandard domain prefixes its basis (e.g.
    ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"``) so the string parses back to the same
    temperament via :func:`parse_mapping_state`."""
    ebk = to_ebk(Temperament(state.mapping, Variance.ROW, state.domain_basis))
    if not is_standard_prime_limit_domain_basis(state.domain_basis):
        ebk = ".".join(str(e) for e in state.domain_basis) + " " + ebk
    return ebk


def standard_primes(d: int) -> tuple[int, ...]:
    """The first ``d`` primes — the standard prime-limit domain basis (header labels)."""
    return get_primes(d)


def is_standard_domain(domain_basis) -> bool:
    """Whether a domain basis is a standard prime limit (the first d primes) — so the
    prime-walking domain ± controls apply, as opposed to a nonstandard subgroup."""
    return is_standard_prime_limit_domain_basis(tuple(domain_basis))


def domain_has_nonprimes(domain_basis) -> bool:
    """Whether the domain basis contains any nonprime element (a composite integer or a
    Fraction with a denominator > 1, like ``13/5``) — the gate for the nonprime-basis-approach
    mode radio, which is only meaningful when there is a nonprime to embed differently. Finer
    than :func:`is_standard_domain`: a reordered prime limit (``3.2.5``) still has the
    prime-only structure, so this returns False where ``is_standard_domain`` does."""
    for element in domain_basis:
        fraction = Fraction(element)
        if fraction.denominator != 1 or not sp.isprime(fraction.numerator):
            return True
    return False


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


def is_proper_temperament(mapping) -> bool:
    """Whether ``mapping`` is a proper temperament: its rows are independent (full row rank — not a
    dependent or zero row), and every domain element is reached by some generator (no all-zero
    column — an element mapped to nothing is tempered to a unison, a degenerate temperament).
    Improper mappings break the detempering identity (M·Dᵀ = I) and don't round-trip, so the editor
    rejects an edit that would produce one."""
    rows = _to_matrix(mapping)
    if not rows or not rows[0]:
        return False
    if get_r(Temperament(rows, Variance.ROW)) < len(rows):  # a dependent / zero row
        return False
    return all(any(row[p] for row in rows) for p in range(len(rows[0])))  # every element reached


def target_interval_set(spec: str, domain_basis) -> tuple[str, ...]:
    """Resolve a target interval set spec against a domain basis, as ratio strings.

    ``spec`` selects the family — a truncated integer-limit triangle (``"TILT"`` /
    ``"N-TILT"``) or an odd-limit diamond (``"OLD"`` / ``"N-OLD"``). With no explicit
    limit the set tracks the domain. ``"TILT"`` is the as-shipped default.
    """
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    if is_standard_prime_limit_domain_basis(domain):
        # a limit raised past the domain's prime limit reaches intervals needing a prime the domain
        # lacks (e.g. 7/4 over a 5-limit) — drop them, matching the optimizer (resolve_target_intervals)
        quotients = tuple(q for q in quotients if len(quotient_to_pcv(q)) <= len(domain))
    else:
        # a nonstandard subgroup can't voice every interval the prime-limit triangle spans
        # (e.g. 5/4 over 2.3.13/5, where 5 isn't reachable) — keep only those it contains
        quotients = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain)
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


def element_ratio(element) -> str:
    """A domain element as a ``"num/den"`` ratio: a prime ``p`` → ``"p/1"``, a nonprime
    element (a Fraction like ``13/5``) → ``"13/5"`` — the operand its just log₂ is taken over."""
    fraction = Fraction(element)
    return f"{fraction.numerator}/{fraction.denominator}"


def default_target_limit(family: str, domain_basis) -> int:
    """The limit a bare TILT/OLD family resolves to for this domain — the number the
    target chooser shows when no manual limit is set (so it never reads as 'auto')."""
    domain = tuple(domain_basis)
    return default_old_limit(domain) if "OLD" in family else default_tilt_limit(domain)


def target_limit_problem(family: str | None, limit_value) -> str | None:
    """Classify a target-limit chooser entry against its family, returning an error key, or
    ``None`` when the value is acceptable:

      - ``"whole"`` — the value isn't a whole number (a decimal, or unparseable text).
      - ``"odd"``   — an even limit for the odd-limit diamond (``OLD``), which is odd by construction;
        the truncated integer-limit triangle (``TILT``) takes any whole number.

    A blank or zero value reads as "no manual limit" (the family tracks the domain default),
    matching the chooser handler that treats a falsy entry as the bare family. A ``None`` family
    (a typed override / all-interval chooser) has no parity rule, so only the whole-number check
    applies."""
    if not limit_value:  # None / "" / 0 -> no manual limit (the bare family)
        return None
    try:
        number = float(limit_value)
    except (TypeError, ValueError):
        return "whole"
    if number != int(number):
        return "whole"
    if "OLD" in (family or "") and int(number) % 2 == 0:
        return "odd"
    return None


def _vectors_to_ratios(vectors, domain_basis=None) -> tuple[str, ...]:
    """Each vector as a ``"num/den"`` ratio string (the shared rendering for generators
    and commas). A vector's components are exponents on the domain basis: the standard
    primes (``pcv_to_quotient``) or, for a nonstandard basis, its (nonprime) elements —
    so a comma over ``2.3.13/5`` multiplies those out (676/675), not the primes (100/27)."""
    standard = domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis)
    elements = None if standard else tuple(Fraction(e) for e in domain_basis)
    ratios = []
    for vector in vectors:
        if standard:
            quotient = pcv_to_quotient(vector)  # exponents on the standard primes
        else:
            quotient = Fraction(1)
            for element, exponent in zip(elements, vector):
                quotient *= element**exponent
        ratios.append(f"{quotient.numerator}/{quotient.denominator}")
    return tuple(ratios)


def generators(mapping, domain_basis=None) -> tuple[str, ...]:
    """Each generator as an approximate ratio string, e.g. ``('2/1', '2/3')``. The
    detempering's vectors are over the domain basis, so a nonstandard one multiplies out
    its (nonprime) elements rather than reading the vector over primes."""
    m = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return _vectors_to_ratios(get_generator_detempering(m).matrix, domain_basis)


def generator_detempering(mapping) -> Matrix:
    """The generator detempering ``D``: one JI interval per generator that tempers to it
    (the mapping's right-inverse), as ``r`` vectors over the ``d`` primes. The vector form
    of :func:`generators` — for 5-limit meantone, the octave and fifth ``((1,0,0),(-1,1,0))``."""
    m = Temperament(_to_matrix(mapping), Variance.ROW)
    return _to_matrix(get_generator_detempering(m).matrix)


def comma_ratios(comma_basis, domain_basis=None) -> tuple[str, ...]:
    """Each comma in the basis as a ratio string, e.g. ``('80/81',)`` — the
    comma-column analogue of :func:`generators`. Rendered as-is (the canonical
    dual's sign), so the syntonic comma reads ``80/81`` (a descending interval).
    Over a nonstandard ``domain_basis`` the vector is multiplied out over its elements."""
    return _vectors_to_ratios(comma_basis, domain_basis)


def _vectors(ratios, d) -> tuple:
    """Parse a ratio list into vectors over the first ``d`` primes (``()`` if empty)."""
    return parse_quotient_list("{" + ", ".join(ratios) + "}", d)


def _interval_vectors(ratios, domain_basis, d) -> tuple:
    """Each ratio as a vector over the domain basis: parsed over the first ``d`` primes for a
    standard basis, or expressed over the (possibly nonprime) elements for a nonstandard one
    (so e.g. ``13/5`` keeps its 13 over ``2.3.13/5`` instead of being truncated to the d primes)."""
    if domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis):
        return _vectors(ratios, d)
    return express_quotients_in_domain_basis(tuple(Fraction(r) for r in ratios), tuple(domain_basis))


def _over(prime_map, vector):
    """Project a vector through a prime map (their dot product)."""
    return sum(prime_map[p] * vector[p] for p in range(len(prime_map)))


def _map_through(mapping, vectors) -> Matrix:
    """Map each vector through ``M`` — columns of vectors taken to generator coords."""
    d = len(mapping[0])
    return tuple(
        tuple(sum(mapping[i][p] * vector[p] for p in range(d)) for vector in vectors)
        for i in range(len(mapping))
    )


def mapped_intervals(mapping, ratios, domain_basis=None) -> Matrix:
    """A ratio-string interval set mapped through ``M`` — the intervals in generator
    coords (r x m). Works for any such set (targets or other intervals of interest);
    the empty set yields one empty generator row per mapping row, keeping the shape.
    Over a nonstandard ``domain_basis`` each ratio is expressed in that basis first."""
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _interval_vectors(ratios, domain_basis, len(mapping[0])))


def mapped_commas(mapping, comma_basis) -> Matrix:
    """Each comma mapped through ``M`` — the comma basis in generator coords (r x nc).
    Every comma the temperament tempers out maps to zero: it vanishes."""
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _to_matrix(comma_basis))


def canonical_mapping(mapping) -> Matrix:
    """The canonical form of ``M`` — defactored, then Hermite Normal Form — as shown
    in the ``canonical mapping`` form box. May differ from the stored matrix (which the
    user can enter in any equivalent form)."""
    return _to_matrix(canonical_ma(_to_matrix(mapping)))


def canonical_comma_basis(comma_basis) -> Matrix:
    """The canonical form of a comma basis (the comma-column analogue of
    :func:`canonical_mapping`) — for the comma-basis box's ``<choose form>`` control."""
    return _to_matrix(canonical_ca(_to_matrix(comma_basis)))


def held_basis_vectors(state: TemperamentState, held_ratios) -> tuple:
    """The tuning's held-interval basis as up to ``r`` INDEPENDENT domain vectors: the held
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
    JI), else the tuning's held-interval basis from ``held_ratios``."""
    return _all_primes_held(state) if state.n == 0 else held_basis_vectors(state, held_ratios)


def _matrix_strings(matrix):
    """A rational matrix as a grid of display strings (``"1"``, ``"0"``, ``"1/4"``, ``"-1/3"``)."""
    return tuple(tuple(str(entry) for entry in row) for row in matrix)


def tuning_projection(state: TemperamentState, held_ratios=()):
    """The rational tempering projection ``P = GM`` as a ``d×d`` grid of display strings (``"1"``,
    ``"0"``, ``"1/4"`` …), or ``None`` when the tuning is NOT a full rational projection — its
    held basis isn't full rank ``r`` (it holds fewer than ``r`` rational intervals, so ``P`` is
    undetermined and the caller dashes it out) or is degenerate (a singular hold like pajara's
    ``{2/1, 7/5}``). ``held_ratios`` is the tuning's held-interval basis (the scheme's structural
    held plus the held column) as ratio strings; the trivial temperament (``n = 0``) is JI, so
    ``P = I``. ``P`` sends each just prime to its tempered size (``j·P = t``), idempotent with the
    commas in its kernel."""
    try:
        inputs = _projection_temperaments(state, _held_for_projection(state, held_ratios))
        if inputs is None:
            return None
        return _matrix_strings(get_tempering_projection(*inputs))
    except (ArithmeticError, ValueError, IndexError, TypeError):
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
    except (ArithmeticError, ValueError, IndexError, TypeError):
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
    except (ArithmeticError, ValueError, IndexError, TypeError):
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
    except (ArithmeticError, ValueError, IndexError, TypeError, AttributeError):
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
    """The held-interval basis that pins ``P_L``, as ``rL`` independent ``dL``-tall vectors over the
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
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None


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
    """The unchanged-interval basis ``U`` recovered from a hand-edited projection matrix ``P`` (a
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
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None


def unchanged_basis_from_embedding(state: TemperamentState, embedding):
    """The unchanged-interval basis ``U`` recovered from a hand-edited generator embedding ``G`` (a
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
    except (ArithmeticError, ValueError, IndexError, TypeError):
        return None


def unchanged_interval_basis(state: TemperamentState, held_ratios=()):
    """The unchanged-interval basis ``U`` as exactly ``r`` columns: the tuning's held intervals
    (``h`` known, rational vectors, stored rows-as-intervals like the comma basis) padded to rank
    ``r`` with ``None`` — a DASHED column — for each direction the optimization leaves irrational.
    A tuning holding fewer than ``r`` rational intervals is not a full rational projection there,
    so those columns are unknown. Together with the comma basis ``C`` it forms ``V = C | U`` (the
    commas have eigenvalue 0, the unchanged 1). The trivial temperament (``n = 0``, JI) tempers
    nothing, so every prime is unchanged — ``U`` is all ``d`` primes with no dashes. ``held_ratios``
    is the tuning's held-interval basis (scheme held + held column). ``None`` only on a degenerate
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
    rational unchanged-interval basis, read straight off the tuning rather than off the held
    column. An interval ``i`` is unchanged exactly when its damage is zero, i.e. the per-prime
    retuning map (tempered − just sizes) dotted with ``i`` is ``0``; genuine holds land at ``0``
    to floating-point precision while everything else is whole cents away, so the check is a clean
    threshold with no integer-relation guessing. We only TEST ``candidate_ratios`` (the
    temperament's established-projection bases first — for clean representatives like ``5/4`` over
    ``5/2`` — then the target-interval set, then the held column), so a basis of the unchanged
    subspace is always among them. Returns up to ``r`` independent ratios (fewer ⇒ the tuning isn't
    a full rational projection, and the caller dashes the rest); JI (``n = 0``) holds every prime."""
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


def form_matrix(mapping) -> Matrix:
    """The generator form matrix ``F``: the unimodular r×r change of generator basis with
    ``F·M = canonical(M)``. Computed as ``F = canonical(M)·Dᵀ`` where ``D`` is the
    generator detempering (its rows the generators as vectors), since ``M·Dᵀ = I``."""
    m = _to_matrix(mapping)
    canon = canonical_ma(m)
    detemper = get_generator_detempering(Temperament(m, Variance.ROW)).matrix
    return tuple(
        tuple(sum(canon[i][p] * detemper[j][p] for p in range(len(m[0])))
              for j in range(len(detemper)))
        for i in range(len(canon))
    )


def target_interval_vectors(ratios, d: int, domain_basis=None) -> Matrix:
    """Each target interval as a vector — its interval-vector form over the d domain
    elements (expressed in the basis when it is nonstandard)."""
    return tuple(tuple(int(x) for x in vector) for vector in _interval_vectors(ratios, domain_basis, d))


def _domain_label(d: int, domain_basis=None) -> str:
    """The domain as a dotted basis string (``"2.3.5"`` / ``"2.3.13/5"``) for error messages."""
    standard = domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis)
    return ".".join(str(e) for e in (standard_primes(d) if standard else domain_basis))


def interval_vector(ratio: str, d: int, domain_basis=None) -> tuple[int, ...]:
    """Parse one ratio string (e.g. ``"80/81"``) into its interval vector over the d domain
    elements — the inverse of :func:`comma_ratios`, for the editable quantities-row ratio cells.
    Raises :class:`ValueError` with a user-facing message (the cell shows it as a toast) when the
    text isn't a single positive quotient (unparseable or non-positive) or carries a prime beyond
    the d-element domain (out of limit) — the two failure modes read differently."""
    text = str(ratio).strip()
    try:
        target = Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f'"{text}" is not a valid ratio.')
    if target <= 0:
        raise ValueError(f'"{text}" is not a positive ratio.')
    vectors = _interval_vectors((text,), domain_basis, d)
    vector = tuple(int(x) for x in vectors[0]) if len(vectors) == 1 and len(vectors[0]) == d else ()
    # a prime past the domain leaves an over-long vector; a within-limit interval outside a
    # nonstandard subgroup parses to one that no longer reproduces the ratio — both are out of limit
    if not vector or Fraction(_vectors_to_ratios((vector,), domain_basis)[0]) != target:
        raise ValueError(f'"{text}" is outside the {_domain_label(d, domain_basis)} domain.')
    return vector


def tuning(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    domain_basis=None,
    nonprime_approach: str = "",
    held=(),
    prescaler_override=None,
    targets=None,
) -> Tuning:
    """The temperament's maps and generator ranges (cents) under ``scheme`` — no
    interval set. Over a nonstandard ``domain_basis`` the maps run over its (possibly
    nonprime) elements; ``nonprime_approach`` ("" neutral, "nonprime-based",
    "prime-based") picks how the optimization treats a nonprime basis (trait 7).
    ``held`` is the user's held interval constraints (ratio strings from the held column):
    the optimization holds each exactly just, on top of any the scheme itself holds.

    ``prescaler_override`` (a d-tuple) drives the complexity-prescaler diagonal directly,
    overriding the scheme's log-prime / prime / identity diagonal — the bare prescaler
    tile's hand-edited values flow through here into the damage-weighted optimum.

    ``targets`` (ratio strings) is a typed explicit target interval list overriding the
    scheme's named TILT/OLD set, so the optimum minimizes damage over THOSE intervals —
    changing the target list retunes. An all-interval scheme keeps its empty set (every
    interval, by duality) and ignores the list."""
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    if targets and (spec.target_intervals or "").strip() not in ("{}", ""):
        spec = replace(spec, target_intervals="{" + ", ".join(targets) + "}")
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if held:  # fold the user's held intervals into the scheme's own (its bare tokens, brace-free)
        own = (spec.held_intervals or "").strip().strip("{}").strip()
        parts = ([own] if own else []) + [r for r in held]
        spec = replace(spec, held_intervals="{" + ", ".join(parts) + "}")
    tempered = optimize_tuning_map(t, spec, prescaler_override=prescaler_override)
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=optimize_generator_tuning_map(t, spec, prescaler_override=prescaler_override),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def tuning_from_generators(mapping, generators, domain_basis=None) -> Tuning:
    """The Tuning produced by a manually-set generator tuning (cents per generator):
    ``tuning_map = generators · mapping``, rather than the scheme's optimum. Backs a manual
    generator-tuning override (a typed/nudged/projection-picked tuning). Just map and
    generator ranges are temperament properties, computed as for the optimum."""
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, generators))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=tuple(generators),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def optimization_power(scheme: str = DEFAULT_TUNING_SCHEME) -> float:
    """The optimization power ``p`` the tuning scheme minimizes: the order of the Lp
    norm taken over the damages — ∞ for a minimax scheme, 2 for least-squares
    (miniRMS), 1 for miniaverage."""
    return resolve_tuning_scheme(scheme).optimization_power


def held_intervals(scheme: str = DEFAULT_TUNING_SCHEME, d: int = 3) -> tuple[str, ...]:
    """The intervals the scheme tunes exactly justly (trait 0), as ratio strings — the
    optimization's held interval constraints. The canonical minimax-S holds nothing;
    a held-octave scheme (e.g. held-octave minimax-ES) holds ``2/1``. ``"octave"`` reads as the prime 2."""
    held = resolve_tuning_scheme(scheme).held_intervals
    if not held:
        return ()
    return _vectors_to_ratios(parse_quotient_list(held.replace("octave", "2"), d))


def interval_sizes(tun: Tuning, ratios, domain_basis=None, weights=None) -> IntervalSizes:
    """Project an interval set through ``tun`` — its tempered/just sizes, error, damage.
    Over a nonstandard ``domain_basis`` each ratio is expressed in that basis (matching the
    basis ``tun`` runs over).

    ``weights`` (a per-interval list aligned to ``ratios``, e.g. the scheme's damage weights
    from :func:`interval_weights`) scales each |error| into the scheme-weighted damage
    ``𝐝 = |𝐞|·W`` — the displayed damage list and the minimized mean damage the optimizer
    actually targets. Default ``None`` is unity weight (``|error|×1 = |error|``)."""
    vectors = _interval_vectors(ratios, domain_basis, len(tun.tuning_map))
    tempered = tuple(_over(tun.tuning_map, m) for m in vectors)
    just = tuple(_over(tun.just_map, m) for m in vectors)
    errors = tuple(t_ - j for t_, j in zip(tempered, just))
    if weights is None:
        damage = tuple(abs(e) for e in errors)
    else:
        damage = tuple(abs(e) * w for e, w in zip(errors, weights))
    return IntervalSizes(tempered, just, errors, damage)


def _temperament_spec_vectors(mapping, scheme, ratios, domain_basis=None):
    """The (Temperament, resolved spec, vectors-over-the-domain) triple the complexity and
    weight projections share — both norm a set of vectors through the scheme's complexity.
    Over a nonstandard ``domain_basis`` the temperament and the vectors run over its
    (possibly nonprime) elements, mirroring :func:`interval_sizes` — so e.g. ``13/5`` over
    ``2.3.13/5`` keeps its basis vector instead of truncating to the d primes."""
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return t, resolve_tuning_scheme(scheme), _interval_vectors(ratios, domain_basis, get_d(t))


def interval_complexities(
    mapping, scheme: str = DEFAULT_TUNING_SCHEME, ratios=(), prescaler_override=None,
    domain_basis=None,
) -> tuple[float, ...]:
    """Each interval's complexity under ``scheme``'s complexity norm — the (pre-transformed)
    norm of its vector (log-prime by default). Independent of the damage slope, which
    only decides how complexity becomes a weight.

    ``prescaler_override`` (a d-tuple) replaces the trait-derived diagonal — the seam the
    bare prescaler tile rides into the complexity row. Over a nonstandard ``domain_basis``
    each ratio is expressed in that basis (so a nonprime target keeps its full vector)."""
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        get_complexity(
            m, t, spec.complexity_norm_power, spec.complexity_log_prime_power,
            spec.complexity_prime_power, spec.complexity_size_factor, spec.nonprime_basis_approach,
            prescaler_override=prescaler_override,
        )
        for m in vectors
    )


def interval_weights(
    mapping, scheme: str = DEFAULT_TUNING_SCHEME, ratios=(), prescaler_override=None,
    domain_basis=None,
) -> tuple[float, ...]:
    """Each interval's damage weight under ``scheme``: 1 (unity weight), its complexity,
    or 1/complexity, picked by the scheme's damage-weight slope.

    ``prescaler_override`` (a d-tuple) flows into each per-target complexity via
    :func:`damage_weights`, so a hand-edited diagonal reaches the weights row. Over a
    nonstandard ``domain_basis`` each ratio is expressed in that basis, like the complexity
    row, so a nonprime target's weight derives from its full domain-basis vector."""
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        float(w) for w in damage_weights(vectors, t, spec, prescaler_override=prescaler_override)
    )


def damage_weight_slope(scheme: str = DEFAULT_TUNING_SCHEME) -> str:
    """The scheme's damage-weight slope — ``"unityWeight"``, ``"complexityWeight"`` or
    ``"simplicityWeight"`` — i.e. whether each weight is 1, its complexity, or 1/complexity."""
    return resolve_tuning_scheme(scheme).damage_weight_slope


# The three predefined complexity prescalers the alt.-complexity control offers, as the
# (log-prime power, prime power) traits each sets — identity (count), log-prime, prime (sopfr).
PRESCALERS = {"identity": (0, 0), "log-prime": (1, 0), "prime": (0, 1)}

# The damage-weight slopes the weight box's chooser offers, mapping each display name to the
# spec's slope trait (trait 3): whether each weight is the complexity, 1, or 1/complexity.
WEIGHT_SLOPES = {
    "complexity-weight": "complexityWeight",
    "unity-weight": "unityWeight",
    "simplicity-weight": "simplicityWeight",
}

# the order the weight variants are offered (per complexity family) in the scheme chooser:
# simplicity, unity, complexity — the slope running from 1/𝒄 through 1 to 𝒄
_WEIGHT_VARIANT_ORDER = ("simplicity-weight", "unity-weight", "complexity-weight")

# The predefined complexities the master chooser in box 𝒄 offers, each mapping its display
# name to the systematic interval-complexity token whose traits it sets (prescaler + size
# factor + norm power). It is the master that overrides the box 𝐋 prescaler and box 𝒄 norm:
# copfr (count), lp (log-product), sopfr, lils (log-integer-limit),
# lols (log-odd-limit), and the Euclidean (q=2) variant of each. lols/lols-E also hold
# the octave just (the only ones that touch trait 0); see :func:`scheme_with_complexity`.
COMPLEXITY_NAMES = {
    "copfr": "copfr",
    "lp": "lp",
    "sopfr": "sopfr",
    "lils": "lils",
    "lols": "lols",
    "copfr-E": "E-copfr",
    "lp-E": "E-lp",
    "sopfr-E": "E-sopfr",
    "lils-E": "E-lils",
    "lols-E": "E-lols",
}

# Friendly display names the master-complexity dropdown shows — abbreviation first, then the
# expansion in parens (the D&D guide's monster table form, inverted so the abbreviation reads
# as the primary token). The Euclidean variants stay short, naming the base by its abbreviation
# ("Euclideanized lp", not "Euclideanized log-product"). The chooser stores the short internal
# key (the COMPLEXITY_NAMES key) but presents these on the dropdown.
COMPLEXITY_DISPLAYS = {
    "copfr": "copfr (count-of-prime-factors-with-repetition)",
    "lp": "lp (log-product)",
    "sopfr": "sopfr (sum-of-prime-factors-with-repetition)",
    "lils": "lils (log-integer-limit-squared)",
    "lols": "lols (log-odd-limit-squared)",
    "copfr-E": "E-copfr (Euclideanized copfr)",
    "lp-E": "E-lp (Euclideanized lp)",
    "sopfr-E": "E-sopfr (Euclideanized sopfr)",
    "lils-E": "E-lils (Euclideanized lils)",
    "lols-E": "E-lols (Euclideanized lols)",
}


def scheme_with_prescaler(scheme, prescaler: str):
    """``scheme`` with its complexity prescaler DIAGONAL swapped to ``prescaler`` (one of
    :data:`PRESCALERS`) — the top d×d of the pretransformer 𝑋. Keeps everything else, INCLUDING
    the size factor (the size-sensitizing 𝑍 row): the diagonal 𝐷 and 𝑍 are independent axes, so
    choosing a prescaler must not clear "replace diminuator". Returns a resolved spec (which the
    service/layout accept anywhere a scheme name is taken)."""
    log_prime_power, prime_power = PRESCALERS[prescaler]
    return replace(
        resolve_tuning_scheme(scheme),
        complexity_log_prime_power=log_prime_power,
        complexity_prime_power=prime_power,
    )


def scheme_with_complexity_norm_power(scheme, power: float):
    """``scheme`` with its interval-complexity norm power q set to ``power`` — the editable q field
    in box 𝒄, deciding which Lq norm of each prescaled vector 𝑋·v the complexity takes (1 = taxicab,
    2 = Euclidean, ∞ = Chebyshev). Keeps everything else. Returns a resolved spec."""
    return replace(resolve_tuning_scheme(scheme), complexity_norm_power=float(power))


def complexity_norm_power(scheme) -> float:
    """The interval-complexity norm power q (trait 4) the scheme currently uses."""
    return resolve_tuning_scheme(scheme).complexity_norm_power


def dual_norm_power(scheme) -> float:
    """The dual of the complexity norm power, dual(q) = q/(q−1) (∞ for q=1, 1 for q=∞) — shown
    beside q in box 𝒄; the norm the all-interval dual-norm inequality minimaxes under."""
    return get_dual_power(complexity_norm_power(scheme))


def scheme_with_power(scheme, power: float):
    """``scheme`` with its optimization power set to ``power`` — the editable 𝑝 field in the
    optimization box (∞ minimax, 2 miniRMS, 1 miniaverage) — keeping everything else. Returns
    a resolved spec (accepted anywhere a scheme name is)."""
    return replace(resolve_tuning_scheme(scheme), optimization_power=float(power))


def is_euclidean(scheme) -> bool:
    """Whether ``scheme`` uses the Euclidean (q=2) complexity norm rather than taxicab (q=1)."""
    return resolve_tuning_scheme(scheme).complexity_norm_power == 2


def weight_annotation(scheme=DEFAULT_TUNING_SCHEME) -> str:
    """The damage/weight unit's annotation code — the parenthetical the guide's dB(A)-style
    annotated units use (ch.10 "Annotated units"): the weight-slope letter ``"U"`` (unity),
    ``"C"`` (complexity) or ``"S"`` (simplicity), gaining an ``"E"`` prefix at a Euclidean (q=2)
    norm and the alternative-complexity family when it isn't the log-product default — e.g.
    ``"S"``, ``"ES"``, ``"sopfr-S"``, ``"E-sopfr-S"``. Damage renders ``¢(<code>)``, the weight
    ``(<code>)``. Unity weight applies no complexity, so it is always just ``"U"``."""
    spec = resolve_tuning_scheme(scheme)
    if spec.damage_weight_slope == "unityWeight":
        return "U"
    letter = "C" if spec.damage_weight_slope == "complexityWeight" else "S"
    return annotation_code(spec, letter)


def complexity_annotation(scheme=DEFAULT_TUNING_SCHEME) -> str:
    """The complexity quantity's annotation code — its slope-free family+norm token, always in
    the ``"C"`` (complexity) position: ``"C"`` / ``"EC"`` for the log-product default,
    ``"sopfr-C"`` / ``"E-sopfr-C"`` for a named family (guide ch.10). Unlike the weight,
    complexity carries no slope — only the family and Euclideanization vary it."""
    return annotation_code(resolve_tuning_scheme(scheme), "C")


def is_all_interval(scheme) -> bool:
    """Whether ``scheme`` is an all-interval tuning scheme — its target set is the empty
    quotient list ``{}`` (every interval, by duality). The canonical minimax-S is."""
    targets = resolve_tuning_scheme(scheme).target_intervals
    return targets is not None and targets.strip() in ("{}", "")


def displayed_targets(state, scheme=DEFAULT_TUNING_SCHEME, target_spec=DEFAULT_TARGET_SPEC,
                      target_override=None) -> tuple[str, ...]:
    """The target interval list as actually displayed, resolved in one place so the grid and the
    plain text can't diverge: a typed ``target_override``, else the named/``TILT`` set — but an
    all-interval scheme auto-replaces it with Tₚ = 𝐈, the domain basis itself (every interval, by
    duality, is its own prime-based proxy), overriding even a typed override."""
    db = state.domain_basis
    if is_all_interval(scheme):
        return tuple(element_ratio(e) for e in db)
    return target_override if target_override is not None else target_interval_set(target_spec, db)


def base_scheme_name(scheme) -> str | None:
    """The bare systematic scheme name — the all-interval form the chooser lists, with any
    target-set prefix dropped (the prefix marks a target-based scheme; stripping it gives the base
    the chooser shows, T-prefixed in its label). Works on a name string or a control-refined spec
    alike, via the renderer. ``None`` when the scheme has no systematic name (an unnameable
    optimization power or complexity). Forcing the target set to all-interval and rendering drops
    the prefix structurally, so an embedded target (``held-octave TILT minimax-ES``) is stripped
    too — where a leading-only text strip would miss it."""
    return systematic_name(replace(resolve_tuning_scheme(scheme), target_intervals="{}"))


def scheme_with_targets(scheme, target_intervals: str):
    """``scheme`` with its target set replaced — ``"{}"`` for all-interval (every interval, by
    duality) or a target family/list spec (e.g. ``"TILT"``) for a target-based scheme — keeping
    every other trait. The target-controls all-interval checkbox flips between the two. Returns a
    resolved spec (accepted anywhere a scheme name is)."""
    return replace(resolve_tuning_scheme(scheme), target_intervals=target_intervals)


def scheme_with_weight_slope(scheme, slope: str):
    """``scheme`` with its damage-weight slope swapped to ``slope`` (a :data:`WEIGHT_SLOPES`
    key) — the weight box's chooser — keeping the complexity and optimization power. Returns a
    resolved spec; the renderer names it back when a chooser needs a label."""
    return replace(resolve_tuning_scheme(scheme), damage_weight_slope=WEIGHT_SLOPES[slope])


def weight_slope_variants(name: str, weighting: bool) -> tuple[str, ...]:
    """``name``'s weight-slope variants as systematic names — its slope swapped to each offered slope
    and rendered back. With ``weighting`` on the established-tuning-scheme chooser lists all three per
    complexity family (simplicity / unity / complexity, T minimax-S / -U / -C) so a weight slope is
    pickable by name, staying in sync with the box-𝒘 weight chooser (both set the same scheme trait).
    With ``weighting`` off there is no box-𝒘 chooser and the weight is unity by construction, so the
    simplicity/complexity slopes aren't reachable — only the unity variant (T minimax-U) is offered."""
    slopes = _WEIGHT_VARIANT_ORDER if weighting else ("unity-weight",)
    return tuple(systematic_name(scheme_with_weight_slope(name, slope)) for slope in slopes)


def weight_slope_of(scheme) -> str:
    """Which of :data:`WEIGHT_SLOPES` ``scheme`` currently uses (by its damage-weight slope)
    — so the control can show the live selection."""
    slope = resolve_tuning_scheme(scheme).damage_weight_slope
    for name, internal in WEIGHT_SLOPES.items():
        if internal == slope:
            return name
    raise ValueError(f"unknown damage weight slope: {slope!r}")


def scheme_with_complexity(scheme, name: str):
    """``scheme`` with its whole complexity shape set to the predefined complexity ``name``
    (a :data:`COMPLEXITY_NAMES` key) — the master chooser in box 𝒄, which overrides the box 𝐋
    prescaler and box 𝒄 norm. lols/lols-E hold the octave just (log-odd-limit); every other
    name clears the held octave, since the held interval is the complexity's own (trait 0).
    Keeps the optimization power and damage slope. Returns a resolved spec."""
    traits, held = complexity_name_traits(COMPLEXITY_NAMES[name])  # only lols/ols hold an interval
    return replace(resolve_tuning_scheme(scheme), held_intervals=held, **traits)  # non-lols clears it


def _complexity_signature(spec) -> tuple:
    """The traits that distinguish the predefined complexities: norm power, prescaler powers,
    size factor, and whether the octave is held (lols vs lils). Two schemes share a complexity
    name iff they share this signature."""
    return (
        spec.complexity_norm_power, spec.complexity_log_prime_power,
        spec.complexity_prime_power, spec.complexity_size_factor,
        spec.held_intervals == "octave",
    )


def complexity_name_of(scheme) -> str:
    """Which of :data:`COMPLEXITY_NAMES` ``scheme`` currently matches — so the master chooser
    can show the live selection — or ``"custom"`` when the complexity shape (set by the box 𝐋
    prescaler / box 𝒄 norm / diminuator controls) is no named preset."""
    sig = _complexity_signature(resolve_tuning_scheme(scheme))
    for name in COMPLEXITY_NAMES:
        if _complexity_signature(scheme_with_complexity(scheme, name)) == sig:
            return name
    return "custom"


def scheme_with_diminuator(scheme, replaced: bool):
    """``scheme`` with its size factor (trait 5c) set — the box 𝐋 "replace diminuator" checkbox.
    Replacing the diminuator (the lesser of a ratio's num/den) with the numinator (the greater)
    is the integer-limit "shear" that turns lp into lils (and copfr/sopfr into their limit forms).
    Keeps everything else. Returns a resolved spec."""
    return replace(resolve_tuning_scheme(scheme), complexity_size_factor=1 if replaced else 0)


def diminuator_replaced(scheme) -> bool:
    """Whether ``scheme`` replaces the diminuator (carries the size factor) — so the box 𝐋
    checkbox can show the live state. False for log-product (lp), True for log-integer-limit (lils)."""
    return resolve_tuning_scheme(scheme).complexity_size_factor != 0


def complexity_size_factor(scheme) -> float:
    """The complexity size factor (trait 5c) ``scheme`` carries — 0 for lp / copfr / sopfr, 1 for
    the integer/odd-limit (lils / lols) family. A nonzero factor is what makes the complexity
    pretransformer 𝑋 rectangular: the guide composes the diagonal log-prime matrix 𝐿 with a
    '''size-sensitizing matrix''' 𝑍 (𝑋 = 𝑍𝐿), appending one extra row, the size-weighted
    ``size_factor·𝐿`` (the log-prime row). The grid reads this to size the prescaling matrix's
    extra row; the value form (:func:`diminuator_replaced`) reads the same trait as a yes/no."""
    return resolve_tuning_scheme(scheme).complexity_size_factor


def prescaler_of(scheme) -> str:
    """Which of :data:`PRESCALERS` ``scheme`` currently uses (by its complexity traits) —
    so the control can show the live selection. Defaults to ``"log-prime"``."""
    spec = resolve_tuning_scheme(scheme)
    traits = (1 if spec.complexity_log_prime_power else 0, 1 if spec.complexity_prime_power else 0)
    for name, t in PRESCALERS.items():
        if t == traits:
            return name
    return "log-prime"


def scheme_to_json(scheme):
    """A tuning scheme as a JSON-safe value, for persistence: the resolved spec's fields as a
    dict. The infinite optimization power (minimax) is encoded as the string ``"inf"`` because
    the JSON layer writes a raw float infinity as null. The inverse is :func:`scheme_from_json`."""
    data = asdict(resolve_tuning_scheme(scheme))
    if data["optimization_power"] == float("inf"):
        data["optimization_power"] = "inf"
    return data


def scheme_from_json(data):
    """Rebuild a tuning scheme spec from :func:`scheme_to_json`'s output (or a legacy saved name
    string), decoding the ``"inf"`` optimization-power sentinel back to a float. Always returns a
    :class:`TuningSchemeSpec`, so a loaded document carries the canonical (spec) representation."""
    if isinstance(data, str):
        return resolve_tuning_scheme(data)  # a legacy saved name -> its spec
    data = dict(data)
    if data.get("optimization_power") == "inf":
        data["optimization_power"] = float("inf")
    return TuningSchemeSpec(**data)


def complexity_prescaler(
    mapping, scheme: str = DEFAULT_TUNING_SCHEME, override=None,
) -> tuple[float, ...]:
    """The diagonal of the complexity prescaler L — each domain prime's pre-norm weight
    (log2(prime) for the default log-prime norm). The L matrix is diag of this.

    ``override`` lets the bare prescaler tile's editable cells short-circuit the scheme's
    computed diagonal: a d-tuple typed in there REPLACES the log-prime/prime/identity
    diagonal everywhere it flows — the matrix display, the 𝐿·basis products, complexity,
    weights, and the tuning solve. ``None`` (the default) keeps today's behavior. The override
    is a d-tuple diagonal, or — once alt-complexity makes the whole square editable — a full d×d
    matrix (a non-diagonal pretransformer); a matrix is returned as rows of floats, a diagonal flat."""
    if override is not None:
        if _is_matrix(override):
            return tuple(tuple(float(x) for x in row) for row in override)
        return tuple(float(x) for x in override)
    t = Temperament(_to_matrix(mapping), Variance.ROW)
    spec = resolve_tuning_scheme(scheme)
    return tuple(
        get_complexity_prescaler(
            t, spec.complexity_log_prime_power, spec.complexity_prime_power, spec.nonprime_basis_approach
        )
    )


def displayed_prescaler_name(mapping, scheme=DEFAULT_TUNING_SCHEME, custom_prescaler=None) -> str | None:
    """The named prescaler (:data:`PRESCALERS`) the displayed L diagonal realises, or ``None`` —
    for which the prescaler chooser shows "-". ``None`` when a ``custom_prescaler`` override
    deviates from the scheme's computed diagonal (the user hand-edited the bare prescaler tile),
    so the shown diagonal no longer matches a named prescaler. An override equal to the scheme's
    own diagonal keeps the scheme's name, mirroring ``Editor.displayed_tuning_scheme_name``.

    The match is at DISPLAY precision (:func:`prescale_text`): a cell shows its value rounded, and
    editing stores that shown value, so a round-trip — deviate a cell, then type the shown value
    back — leaves a diagonal differing from the full-precision scheme diagonal only by rounding.
    Comparing what's shown lets that read as "no deviation" (the chooser and the grid's 𝑋 = 𝐿
    awareness recover), where a bit-exact compare would wrongly keep showing "-"."""
    if custom_prescaler is not None:
        if _is_matrix(custom_prescaler):
            return None  # a non-diagonal pretransformer has no named (diagonal) prescaler form
        computed = complexity_prescaler(mapping, scheme)
        shown = tuple(float(x) for x in custom_prescaler)
        if len(shown) != len(computed) or any(
                prescale_text(a) != prescale_text(b) for a, b in zip(shown, computed)):
            return None
    return prescaler_of(scheme)


def plain_text_values(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
    target_spec: str = DEFAULT_TARGET_SPEC,
    held=(),
    interest=(),
    generator_tuning=None,
    target_override=None,
    nonprime_approach: str = "",
    superspace: bool = False,
    superspace_generator_override=None,
    consolidate_v: bool = False,
    held_basis_ratios=(),
    custom_prescaler=None,
) -> dict[tuple[str, str], str]:
    """Each value group's natural plain-text form, keyed by its ``(row, column)``
    tile (the same vocabulary the spreadsheet layout uses). The grid and this text
    show the same numbers two ways — the EBK string is the inline notation. ``held``
    (the held interval vectors), ``interest`` (the other-intervals-of-interest vectors),
    ``generator_tuning`` (a frozen manual tuning), ``target_override`` (a typed explicit
    target list), ``nonprime_approach`` (the nonprime-basis optimization trait) and
    ``custom_prescaler`` (the bare prescaler tile's hand-edited diagonal / matrix override)
    are threaded into the same tuning/weights/complexity/prescaling the grid builds, so the
    two views can't diverge."""
    db = state.domain_basis
    targets = displayed_targets(state, scheme, target_spec, target_override)  # all-interval-aware, like the grid
    # the REAL comma basis: empty at full rank (n = 0), where state.comma_basis is just the trivial
    # zero comma — the grid shows no comma column there, so the plain text must show no comma vector
    # either (not a phantom [0 0 0⟩). Everything comma-side below reads this, like the grid's self.nc.
    comma_basis = state.comma_basis if state.n else ()
    commas = comma_ratios(comma_basis, db)
    mapped = mapped_intervals(state.mapping, targets, db)
    mapped_comma = mapped_commas(state.mapping, comma_basis)
    target_vectors = target_interval_vectors(targets, state.d, db)
    held_ratios = comma_ratios(held, db) if held else ()
    # match the grid's tuning exactly: a manual generator-tuning override
    # drives the maps directly; otherwise the scheme's optimum holding the held intervals just
    if generator_tuning is not None and len(generator_tuning) == len(state.mapping):
        tun = tuning_from_generators(state.mapping, generator_tuning, db)
    else:  # a typed target-list override retunes the optimum, matching the grid's own tuning —
        # over the SAME nonprime approach + custom prescaler the grid threads (else the tuning rows
        # diverge from the grid's optimum under a hand-edited prescaler or a nonprime domain)
        tun = tuning(state.mapping, scheme, db, nonprime_approach, held=held_ratios,
                     prescaler_override=custom_prescaler, targets=target_override)
    # the target damage row is the scheme-weighted 𝐝 = |𝐞|·W (the same weights the weight row
    # shows and the optimizer minimizes), so the displayed damage tracks the unity/complexity/
    # simplicity slope rather than staying plain |error|. The custom prescaler rides into the
    # weights too (the grid passes it to interval_weights), so a hand-edited diagonal reweights here.
    target_damage_weights = interval_weights(state.mapping, scheme, targets, domain_basis=db,
                                             prescaler_override=custom_prescaler)
    target_sizes = interval_sizes(tun, targets, db, weights=target_damage_weights)
    comma_sizes = interval_sizes(tun, commas, db)  # comma sizes, like the grid's commas column
    detemper_ratios = generators(state.mapping, db)  # the detempering as ratios (= service.generators)
    detemper_sizes = interval_sizes(tun, detemper_ratios, db)  # tempered = the genmap, plus just/error
    detemper_vectors = generator_detempering(state.mapping)  # D's vectors, for the prescaling matrix
    # the weighting region: complexity (a covector over the primes, lists elsewhere), the
    # per-target weight list, and the prescaling matrices (L applied to each vector set, as
    # ket lists). Complexity over the primes is the complexity of each domain basis element
    # (over the domain basis, like the grid) — NOT the standard primes, so a nonprime element
    # prime-factors correctly (13/5 reads log₂(13·5), not log₂5 over a domain that has no 5).
    prime_ratios = tuple(element_ratio(e) for e in db)
    # the bare prescaler 𝑋 (its diagonal, or a hand-entered non-diagonal matrix override) — the
    # SAME override the grid threads into every prescaling/complexity/weight/tuning calculation.
    prescaler = complexity_prescaler(state.mapping, scheme, override=custom_prescaler)
    prescaler_is_matrix = bool(prescaler) and isinstance(prescaler[0], (tuple, list))
    size_factor = complexity_size_factor(scheme)  # nonzero ⇒ the rectangular 𝑋 = 𝑍𝐿 (size row)

    def _prescaled(vectors):
        # the prescaled vector 𝑋·v: a diagonal pretransformer multiplies element-wise (𝐿ᵢvᵢ); a
        # non-diagonal one (the editable square's matrix override) is a matrix-vector product — the
        # same split the grid takes (spreadsheet.py's prescaling loop)
        if prescaler_is_matrix:
            return tuple(tuple(sum(prescaler[i][k] * v[k] for k in range(state.d)) for i in range(state.d))
                         for v in vectors)
        return tuple(tuple(prescaler[i] * v[i] for i in range(state.d)) for v in vectors)

    def _sized(cols):
        """Append the size component sf·Σ(𝐿ⱼ·vⱼ) (= sf·sum of the prescaled column) to each
        prescaled COLUMN, growing a 𝐿·basis product into the rectangular 𝑍𝐿 form when the size
        factor is on — the guide's size-sensitizing row. A no-op for the square (lp) case."""
        if not size_factor:
            return cols
        return tuple(col + (size_factor * sum(col),) for col in cols)

    # the bare prescaler 𝑋 as its d matrix ROWS: a diagonal 𝐿 broadcast to [0…𝐿ᵢ…0] rows; a
    # hand-entered non-diagonal pretransformer its own rows — matching the grid's 2D placement,
    # where cell (i, c) = 𝑋[i][c] (the diagonal case renders identically either way).
    if prescaler_is_matrix:
        bare_rows = [tuple(prescaler[i]) for i in range(state.d)]
    else:
        bare_rows = [tuple(prescaler[i] if k == i else 0 for k in range(state.d)) for i in range(state.d)]
    # the bare prescaler is a covector STACK, so the size factor appends one extra ROW — the
    # size-sensitizing covector sf·𝐋 (each entry sf·Σᵢ𝑋ᵢⱼ, the column sum — sf·𝐿ⱼ for a diagonal),
    # keeping the row length d — rather than extending each column the way the products do. This
    # 𝑋 = 𝑍𝐿 size row is the only growth the weighting region shows; the all-interval simplicity
    # weight stays a per-target list (its 𝒘 = 𝒄⁻¹ form lives in the grid tile's symbol, not here).
    bare_size_row = ((tuple(size_factor * sum(col) for col in zip(*bare_rows)),) if size_factor else ())
    weight_text = _cents_list(target_damage_weights)
    tp_text = _ket_list(target_vectors, "⟩")
    bare_x_text = _prescale_vector_list(bare_rows + list(bare_size_row), col="⟨]", outer="[⟩")
    complexity_text = _cents_list(interval_complexities(state.mapping, scheme, targets, domain_basis=db,
                                                        prescaler_override=custom_prescaler))
    damage_text = _cents_list(target_sizes.damage)
    # the unchanged half U of the consolidated V = C|U column (projection on): assembled the SAME way
    # the grid does — service.unchanged_interval_data, over the same custom prescaler — so the inline
    # plain text matches the grid cell-for-cell, em-dashes and all, where the under-held tuning leaves
    # a direction irrational. Off (or n = 0), the u_* lists stay empty and every V tile reads as C alone.
    udata = unchanged_interval_data(state, held_basis_ratios, tun, scheme, db,
                                    custom_prescaler) if consolidate_v else None
    if udata is not None:
        nrow = len(state.mapping)
        u_basis = list(udata.basis)  # P·𝐮 = 𝐮, so this also serves the projected list P·V's unchanged half
        u_mapped_cols = [None if udata.basis[j] is None else tuple(udata.mapped[i][j] for i in range(nrow))
                         for j in range(len(udata.basis))]
        u_prescaled = [None if u is None else _sized(_prescaled((u,)))[0]
                       for u in udata.basis]
        u_tempered, u_just, u_errors = list(udata.sizes.tempered), list(udata.sizes.just), list(udata.sizes.errors)
        u_comps = list(udata.complexities)
        u_scaling = [_DASH if v is None else "1" for v in udata.basis]  # λ = 1 (held) / — (dashed)
    else:
        u_basis = u_mapped_cols = u_prescaled = u_tempered = u_just = u_errors = u_comps = u_scaling = []
    # Keyed by the tile each value group occupies. The interval-vectors row holds the
    # vector lists (close ⟩); the mapping row holds the mapping (a list of maps, close ])
    # and the mapped lists (generator-coordinate vectors, close }). The editable duals
    # are the mapping (mapping/primes) and the comma basis (vectors/commas). The
    # quantities row's only plain text is the domain-primes basis ("2.3.5"), keyed here; its
    # interval-ratio columns (commas/targets/held/detempering) carry none — their gridded
    # ratio is already the formatted value. The generators (mapping/quantities) carry none either.
    values = {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        # the consolidated V = C|U column shows BOTH halves in every tile: the comma side C then the
        # unchanged side U (em-dashed where the tuning leaves a direction irrational). Off projection
        # the u_* lists are empty, so each tile falls back to the bare comma side exactly as before.
        ("vectors", "commas"): _ket_list(list(comma_basis) + u_basis, "⟩"),
        # the projected unrotated vector list P·V: P·𝐜 = 𝟎 (the commas vanish), P·𝐮 = 𝐮 (held), so it
        # is the zero comma columns followed by the unchanged vectors themselves — prime-count (⟩)
        ("projection", "commas"): _ket_list([(0,) * state.d for _ in commas] + u_basis, "⟩"),
        # the scaling factors λ = diag(λ): 0 per comma (vanished), 1 per (known) unchanged, — if dashed
        ("scaling_factors", "commas"): "[" + " ".join(["0"] * len(commas) + u_scaling) + "]",
        ("vectors", "targets"): tp_text,  # Tₚ — the target identity
        ("mapping", "primes"): mapping_ebk(state),
        ("mapping", "commas"): _ket_list(list(zip(*mapped_comma)) + u_mapped_cols, "}"),
        ("mapping", "targets"): _ket_list(zip(*mapped), "}"),
        ("tuning", "gens"): _cents_genmap(tun.generator_map),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(list(comma_sizes.tempered) + u_tempered),
        # the detempering's tempered sizes ARE the generator tuning map (𝒕D = 𝒈), shown
        # genmap-style ({ ]); its just and retuning sizes are ordinary cents lists
        ("tuning", "detempering"): _cents_genmap(detemper_sizes.tempered),
        ("tuning", "targets"): _cents_list(target_sizes.tempered),
        ("just", "primes"): _cents_map(tun.just_map),
        ("just", "commas"): _cents_list(list(comma_sizes.just) + u_just),
        ("just", "detempering"): _cents_list(detemper_sizes.just),
        ("just", "targets"): _cents_list(target_sizes.just),
        ("retune", "primes"): _cents_map(tun.retuning_map),
        ("retune", "commas"): _cents_list(list(comma_sizes.errors) + u_errors),
        ("retune", "detempering"): _cents_list(detemper_sizes.errors),
        ("retune", "targets"): _cents_list(target_sizes.errors),
        ("damage", "targets"): damage_text,
        # the bare prescaler 𝐿 is the asymmetric exception of the prescaling row: it reads
        # as a covector stack like the mapping — per-row ⟨ … ] (angle open + square close)
        # inside outer [ … ⟩ (square open + ket close). Every 𝐿·basis product (𝐿C/𝐿D/𝐿H/𝐿T)
        # is instead a matrix of prescaled VECTORS — per-column ket [ … ⟩ inside symmetric
        # outer [ … ] — so the bare prescaler reads as the matrix itself rather than a
        # product with another basis.
        ("prescaling", "primes"): bare_x_text,  # the bare 𝑋 — gains its 𝑍𝐿 size ROW under the size factor
        ("prescaling", "commas"): _prescale_vector_list(list(_sized(_prescaled(comma_basis))) + u_prescaled),
        ("prescaling", "detempering"): _prescale_vector_list(_sized(_prescaled(detemper_vectors))),
        ("prescaling", "targets"): _prescale_vector_list(_sized(_prescaled(target_vectors))),
        ("complexity", "primes"): _cents_map(interval_complexities(state.mapping, scheme, prime_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        ("complexity", "commas"): _cents_list(list(interval_complexities(state.mapping, scheme, commas, domain_basis=db, prescaler_override=custom_prescaler)) + u_comps),
        ("complexity", "detempering"): _cents_list(interval_complexities(state.mapping, scheme, detemper_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        ("complexity", "targets"): complexity_text,
        ("weight", "targets"): weight_text,
    }
    # the held interval column mirrors the comma column: the basis as a vector list, mapped
    # into generator coords, then the held-just sizes/errors and complexity. Added only when
    # the user has held intervals (an empty set declares no held tiles, like the commas).
    if held:
        held_sizes = interval_sizes(tun, held_ratios, db)
        held_mapped = mapped_intervals(state.mapping, held_ratios, db)
        values.update({
            ("vectors", "held"): _ket_list(held, "⟩"),
            ("mapping", "held"): _ket_list(zip(*held_mapped), "}"),
            ("tuning", "held"): _cents_list(held_sizes.tempered),
            ("just", "held"): _cents_list(held_sizes.just),
            ("retune", "held"): _cents_list(held_sizes.errors),
            ("prescaling", "held"): _prescale_vector_list(_sized(_prescaled(held))),
            ("complexity", "held"): _cents_list(interval_complexities(state.mapping, scheme, held_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        })
    # the other-intervals-of-interest column is a loose collection, not a basis, so every
    # row is unwrapped (wrap=False): its vectors and mapped images stand alone (each its own
    # ket, space-separated, no outer [ … ]), unlike the comma/target/held matrices; the size
    # rows drop their [ … ] too, and prescaling lists each prescaled vector as its own parens.
    if interest:
        interest_ratios = comma_ratios(interest, db)
        interest_mapped = mapped_intervals(state.mapping, interest_ratios, db)
        interest_sizes = interval_sizes(tun, interest_ratios, db)
        values.update({
            ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
            ("mapping", "interest"): _ket_list(zip(*interest_mapped), "}", wrap=False),
            ("tuning", "interest"): _cents_list(interest_sizes.tempered, wrap=False),
            ("just", "interest"): _cents_list(interest_sizes.just, wrap=False),
            ("retune", "interest"): _cents_list(interest_sizes.errors, wrap=False),
            ("prescaling", "interest"): _prescale_vector_list(_sized(_prescaled(interest)), outer=""),
            ("complexity", "interest"): _cents_list(interval_complexities(state.mapping, scheme, interest_ratios, domain_basis=db, prescaler_override=custom_prescaler), wrap=False),
        })
    # the projection P and generator embedding G plain-text bands (the editable duals — the only edit
    # path now that the gridded cells are read-only). Computed from the SAME held basis the grid's
    # P/G cells use, so band and grid agree cell-for-cell, dashed in lockstep when the tuning isn't a
    # full rational projection. Only when projection is on (consolidate_v), like the grid.
    if consolidate_v:
        values[("projection", "primes")] = projection_ebk(tuning_projection(state, held_basis_ratios), state.d)
        values[("projection", "gens")] = embedding_ebk(tuning_embedding(state, held_basis_ratios), state.d, len(state.mapping))
        # the projected vector lists' read-only EBK bands (P·D / P·T / P·H / P·interest), the projection-
        # row counterparts of the interval-vectors row's strings. P·D = the embedding G takes the curly
        # { … ] (generator-coordinate columns, like G); P·T / P·H the plain [ … ]; P·interest stands
        # alone (no outer wrap). Dashed in lockstep with P when the tuning isn't a rational projection.
        p_rat = projection_matrix_rationals(state, held_basis_ratios)

        def _proj_cols(vectors):
            cols = project_vectors(p_rat, vectors)
            return list(cols) if cols else [tuple(_DASH for _ in range(state.d)) for _ in vectors]

        values[("projection", "detempering")] = "{" + _ket_list(_proj_cols(detemper_vectors), "⟩", wrap=False) + "]"
        values[("projection", "targets")] = _ket_list(_proj_cols(target_vectors), "⟩")
        if held:
            values[("projection", "held")] = _ket_list(_proj_cols(held), "⟩")
        if interest:
            values[("projection", "interest")] = _ket_list(_proj_cols(interest), "⟩", wrap=False)
    # the chapter-9 nonstandard-domain superspace region: B_L (the basis-embedding matrix
    # as a list of dL-tall kets, one per domain element), M_L (the temperament's mapping
    # over the superspace primes — a covector stack like M), M_jL (the dL × dL identity),
    # and the cyan tuning maps 𝒈ₗ / 𝒕ₗ / 𝒋ₗ / 𝒓ₗ (covectors over the superspace primes,
    # respectively the generators for 𝒈ₗ). Same bracket conventions as the existing tiles
    # they parallel — _ket_list for B_L's vector columns, _cents_map for the covector maps,
    # _cents_genmap for the genmap 𝒈ₗ — so each new EBK string reads consistently with its
    # non-superspace cousin (per the rendered mockup, which kept the existing brackets).
    if superspace:
        db = state.domain_basis
        ml = superspace_mapping(state)
        ss_primes = superspace_primes(db)
        mjl = superspace_just_mapping(ss_primes)
        mlgl = superspace_self_map(state)
        msl = mapping_to_superspace_generators(state)
        bl = basis_in_superspace(db)
        ss_tun = superspace_tuning(state, scheme, nonprime_approach,
                                   generator_override=superspace_generator_override)

        def _covector_stack(rows):  # mapping-style: each row ⟨ … ], outer [ … }
            return "[" + "".join("⟨" + " ".join(str(x) for x in r) + "]" for r in rows) + "}"

        # the lifted interval lists (B_L · each column) over the superspace primes, and the
        # mapped versions (M_s→L · each column) over the superspace generators
        C_L = lift_vectors_to_superspace(db, state.comma_basis)
        T_L = lift_vectors_to_superspace(db, target_vectors)
        I_L = lift_vectors_to_superspace(db, interest)
        mapped_C = map_vectors_into_superspace_generators(state, state.comma_basis)
        mapped_T = map_vectors_into_superspace_generators(state, target_vectors)
        mapped_I = map_vectors_into_superspace_generators(state, interest)
        values.update({
            # B_L (basis change matrix): the mockup wraps it ⟨ … ] (distinct from the plain
            # [ … ] lifted lists), its columns the domain-element kets [ … ⟩.
            ("ss_vectors", "primes"): "⟨" + _ket_list(bl, "⟩", wrap=False) + "]",
            ("ss_vectors", "ssprimes"): _covector_stack(mjl),       # M_jL = I
            ("ss_vectors", "commas"): _ket_list(C_L, "⟩"),          # C_L
            ("ss_vectors", "targets"): _ket_list(T_L, "⟩"),         # T_L
            ("ss_vectors", "interest"): _ket_list(I_L, "⟩", wrap=False),
            ("ss_mapping", "ssprimes"): _covector_stack(ml),        # M_L
            ("ss_mapping", "primes"): _covector_stack(msl),         # M_s→L
            ("ss_mapping", "ssgens"): _ket_list(mlgl, "}"),         # M_LgL = I (gen coords)
            ("ss_mapping", "commas"): _ket_list(mapped_C, "}"),     # mapped commas (→ 0)
            ("ss_mapping", "targets"): _ket_list(mapped_T, "}"),    # Y_L
            ("ss_mapping", "interest"): _ket_list(mapped_I, "}", wrap=False),
            ("ss_just_mapping", "ssprimes"): _covector_stack(mjl),
            ("tuning", "ssgens"): _cents_genmap(ss_tun.generator_map),
            ("tuning", "ssprimes"): _cents_map(ss_tun.tuning_map),
            ("just", "ssprimes"): _cents_map(ss_tun.just_map),
            ("retune", "ssprimes"): _cents_map(ss_tun.retuning_map),
        })
        # the superspace projection P_L = G_L·M_L's EBK band — the plain-text twin of its grid, a
        # covector stack closing with the angle ⟩ (the b/b operator, framed like the on-domain P).
        # Only when the projection toggle is on (consolidate_v), like the on-domain P band below, and
        # built from the SAME held basis so the two views agree; projection_ebk dashes a None matrix.
        if consolidate_v:
            values[("ss_projection", "ssprimes")] = projection_ebk(
                superspace_tuning_projection(state, held_basis_ratios), len(ss_primes))
        # the chapter-9 prescaler SHIFT (the plain-text twin of the gridded cells): the bare 𝐿
        # moves into the ss-primes column — the dL×dL log-prime diagonal over the TRUE primes, a
        # covector stack [ ⟨…] ⟨…] ⟩ that stays EDITABLE — while the domain-primes tile becomes the
        # 𝐿·B_Ls product, the prescaled subspace basis elements: a READ-ONLY matrix of d prescaled
        # kets [ … ⟩ (NOT the bare prescaler's covector stack — that backwards EBK was the bug). The
        # complexity row mirrors it: the prime complexity map ‖𝐿[i]‖ moves to ss-primes; the domain-
        # primes complexity becomes the subspace basis element map (prime-factored over the domain).
        ss_prescaler = superspace_complexity_prescaler(state, scheme)
        dL = len(ss_primes)
        ss_units = tuple(tuple(1 if i == p else 0 for i in range(dL)) for p in range(dL))

        def _prescaled_ss(vectors):  # element-wise 𝐿ᵢvᵢ over the dL superspace primes
            return tuple(tuple(ss_prescaler[i] * v[i] for i in range(dL)) for v in vectors)

        ss_bare_size = ((tuple(size_factor * w for w in ss_prescaler),) if size_factor else ())
        elem_ratios = tuple(element_ratio(e) for e in db)
        values.update({
            ("prescaling", "ssprimes"): _prescale_vector_list(_prescaled_ss(ss_units) + ss_bare_size, col="⟨]", outer="[⟩"),
            # 𝐿·B_Ls is the prescaled basis-change matrix, so it follows B_L's wrap: outer ⟨ … ]
            # around the per-column kets [ … ⟩ (matching ss_vectors/primes, not the plain products)
            ("prescaling", "primes"): _prescale_vector_list(_sized(_prescaled_ss(bl)), col="[⟩", outer="⟨]"),
            ("complexity", "ssprimes"): _cents_map(ss_prescaler),
            ("complexity", "primes"): _cents_map(interval_complexities(state.mapping, scheme, elem_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        })
    return values


_DASH = "—"  # an em-dash column/value: an unknown the under-held tuning doesn't pin (matches the grid)


def _ket_list(vectors, close: str, wrap: bool = True) -> str:
    """A list of column vectors: ``[[1 0 0⟩ [0 1 0⟩]`` for vectors (close ``⟩``),
    ``[[1 0} [0 1}]`` for generator-coordinate vectors (close ``}``). The outer ``[ ]``
    wraps the whole list (a matrix presentation, even a single vector); ``wrap=False``
    drops it for the intervals-of-interest column, whose intervals stand alone. A ``None``
    column is a DASHED unchanged vector — all em-dashes, width matched to the known columns."""
    vectors = list(vectors)
    dim = next((len(v) for v in vectors if v is not None), 0)
    def _ket(v):
        comps = [_DASH] * dim if v is None else [str(x) for x in v]
        return "[" + " ".join(comps) + close
    kets = " ".join(_ket(v) for v in vectors)
    return f"[{kets}]" if wrap else kets


def projection_ebk(matrix, d: int) -> str:
    """The rational tempering projection P as a map-list EBK string — a covector stack like the
    mapping (each row a map ``⟨ … ]``), but closing with the prime-coordinate ket ``⟩`` since P is
    p/p: ``[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩``. ``matrix`` is the d×d grid of display strings from
    :func:`tuning_projection`; ``None`` (not a full rational projection) dashes every entry to match
    the dashed grid. The editable dual the projection-primes plain text shows (parsed by
    :func:`parse_projection`)."""
    grid = matrix if matrix is not None else tuple((_DASH,) * d for _ in range(d))
    return "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in grid) + "⟩"


def embedding_ebk(matrix, d: int, r: int) -> str:
    """The rational generator embedding G as a vector-list EBK string — its r held generators as
    prime-count ket columns inside an outer ``{ … ]`` (curly open, square close — generator-coordinate
    columns): ``{[1 0 0⟩ [0 0 1/4⟩]``. ``matrix`` is the d×r grid of display strings from
    :func:`tuning_embedding`; ``None`` dashes every entry. The editable dual the projection-gens plain
    text shows (parsed by :func:`parse_embedding`)."""
    grid = matrix if matrix is not None else tuple((_DASH,) * r for _ in range(d))  # d×r
    return "{" + _ket_list(list(zip(*grid)), "⟩", wrap=False) + "]"  # transpose to the r ket columns


def _prescale_vector_list(vectors, col: str = "[⟩", outer: str = "[]") -> str:
    """A list of complexity-prescaler matrix columns — for the weighting prescaling matrices
    (the prescaled vectors 𝐿·v). A 𝐿·basis product is a matrix of prescaled VECTORS, so each
    column is a ket ``[ … ⟩`` (square open + angle close — the default ``col``); the OUTER
    wrap then differs by tile family:

      * 𝐿·basis products  — ``col="[⟩"``, ``outer="[]"`` (kets inside a symmetric square).
      * Interest tile     — ``col="[⟩"``, ``outer=""``  (standalone kets, no wrap).
      * Bare prescaler 𝐿  — ``col="⟨]"``, ``outer="[⟩"`` (the asymmetric exception: it reads
        as a covector stack like the mapping — per-row ⟨ … ] inside outer [ … ⟩, mirroring
        the mapping's ``[ … }`` but with the angle ⟩ instead of the curly }).

    Each value is formatted with prescale_text, so the string shows exactly the grid's
    numbers (whole numbers bare, else 3-dp) rather than a denser all-3-dp form."""
    vectors = list(vectors)
    dim = next((len(v) for v in vectors if v is not None), 0)  # a dashed (None) column is all em-dashes
    def _col(v):
        body = " ".join([_DASH] * dim if v is None else [prescale_text(x) for x in v])
        return col[0] + body + col[1]
    cols = " ".join(_col(v) for v in vectors)
    if not outer:
        return cols
    return f"{outer[0]}{cols}{outer[1]}"


def vector_list_pending_text(committed_vectors, pending) -> tuple[str, str, str]:
    """Split a wrapped vector-list plain text for the two-tone draft display: the committed
    vectors and the wrapping ``[ … ]`` stay black, the in-progress draft vector greens.
    Shared by the comma basis and the target interval list (both wrapped ket lists). Returns
    ``(black_prefix, green_draft_ket, black_suffix)``. The draft ket shows the entered components
    only (``None`` blanks omitted): ``[4, None, 1] -> "[4 1⟩"``."""
    committed = _ket_list(committed_vectors, "⟩")  # e.g. "[[4 -4 1⟩]" — drop its close ] to reopen
    draft = "[" + " ".join(str(x) for x in pending if x is not None) + "⟩"
    return committed[:-1] + " ", draft, "]"


def mapping_pending_text(committed_ebk, pending) -> tuple[str, str, str]:
    """Split the wrapped mapping plain text for the two-tone draft display while a generator ROW is
    being added: the committed maps and the wrapping ``[ … }`` stay black, the in-progress draft map
    greens. The ROW mirror of :func:`vector_list_pending_text`. ``committed_ebk`` is the mapping's
    plain text (e.g. ``"[⟨1 1 0] ⟨0 1 4]}"``, possibly domain-prefixed), which always closes with the
    generator-coordinate ``}``. Returns ``(black_prefix, green_draft_map, black_suffix)``; the draft
    map shows the entered components only (``None`` blanks omitted): ``[0, None, 1] -> "⟨0 1]"``."""
    draft = "⟨" + " ".join(str(x) for x in pending if x is not None) + "]"
    return committed_ebk[:-1] + " ", draft, "}"


def cents(value) -> str:
    """A cents quantity at the 3-dp the grid and plain-text views share, so the two displays
    always agree. ``None`` (a dashed value — e.g. the size of an unknown unchanged interval the
    tuning doesn't pin) renders as an em-dash."""
    if value is None:
        return "—"
    return strip_negative_zero(f"{value:.3f}")


def prescale_text(value: float) -> str:
    """A complexity-prescaler matrix entry as BOTH the grid cell and the plain-text view
    render it: a whole number bare (the mostly-0 off-diagonal, and the log₂2 = 1 of an
    identity prescaler), else the 3-dp cents value (log₂3 = 1.585) — keeping the mostly-zero
    matrix clean. One formatter for both views, so the prescaling grid and its EBK string
    can't disagree."""
    return str(int(value)) if value == int(value) else cents(value)


def _cents_map(values) -> str:
    """A tuning covector over the primes: ``⟨1200.000 1901.955 …]``."""
    return "⟨" + " ".join(cents(v) for v in values) + "]"


def _cents_list(values, wrap: bool = True) -> str:
    """A tuning list over the targets: ``[1200.000 1901.955 …]``. ``wrap=False`` drops the
    enclosing ``[ ]`` for the intervals-of-interest column, whose values stand bare."""
    body = " ".join(_DASH if v is None else cents(v) for v in values)  # None → a dashed (unknown) entry
    return f"[{body}]" if wrap else body


def _cents_genmap(values) -> str:
    """The generator tuning map: ``{1201.699 697.564]`` — curly open, square close,
    per the mockup (distinct from the primes' covector ``⟨ … ]``)."""
    return "{" + " ".join(cents(v) for v in values) + "]"


def _int_matrix_or_none(matrix) -> Matrix | None:
    """A rectangular all-integer matrix, or None — the validity gate for an edited
    plain-text mapping/comma-basis string (Fractions, decimals, blanks, or a ragged
    shape are rejected so the caller can flag the input rather than apply it)."""
    if not matrix or not all(matrix):
        return None
    width = len(matrix[0])
    rows = []
    for row in matrix:
        if len(row) != width:
            return None
        if any(isinstance(x, bool) or not isinstance(x, int) for x in row):
            return None
        rows.append(tuple(row))
    return tuple(rows)


def _rational_matrix_or_none(matrix):
    """A rectangular matrix of ints/Fractions as a grid of display strings, or None — the
    fraction-aware gate for an edited P/G plain-text string (the integer-only
    :func:`_int_matrix_or_none` rejects the ``1/4`` entries P/G carry). Floats, booleans, blanks,
    or a ragged shape are rejected so the caller can flag the input rather than apply it."""
    if not matrix or not all(matrix):
        return None
    width = len(matrix[0])
    rows = []
    for row in matrix:
        if len(row) != width:
            return None
        if any(isinstance(x, bool) or not isinstance(x, (int, Fraction)) for x in row):
            return None
        rows.append(tuple(str(x) for x in row))
    return tuple(rows)


def _parse_float_list(text: str, n: int | None = None) -> tuple[float, ...] | None:
    """A whitespace/comma-separated list of floats inside any EBK bracket pair
    (``{ ⟨ [ ( ) ] ⟩ }``), or None if it is empty, non-numeric, or (when ``n`` is given)
    not exactly ``n`` long. The float-tolerant core behind the cents-map parser."""
    tokens = text.strip().strip("{}⟨⟩[]()").replace(",", " ").split()
    if not tokens:
        return None
    try:
        values = tuple(float(t) for t in tokens)
    except ValueError:
        return None
    if n is not None and len(values) != n:
        return None
    return values


def parse_cents_map(text: str, n: int | None = None) -> tuple[float, ...] | None:
    """Read a cents map string back to its values — the generator tuning map
    ``{1201.699 697.564]`` or a prime tuning map ``⟨1200.000 …]`` — float-tolerant, the
    inverse of :func:`_cents_genmap` / :func:`_cents_map`. None if unparseable or (with
    ``n`` set) not exactly ``n`` values. The reader behind a typed manual generator tuning."""
    return _parse_float_list(text, n)


def parse_mapping(text: str) -> Matrix | None:
    """Read an EBK *map* string (e.g. ``[⟨1 1 0] ⟨0 1 4]}``) back to a mapping
    matrix, or None if it is unparseable, the wrong variance (a vector, not a map),
    or not an integer matrix. The inverse of the ``("mapping", "primes")`` plain text."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.ROW:
        return None
    return _int_matrix_or_none(t.matrix)


def parse_projection(text: str):
    """Read a map-list EBK string (e.g. ``[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩``) back to a d×d projection as a
    grid of display strings, or None if unparseable, the wrong variance (a vector, not a map), or not
    a rational matrix. The inverse of :func:`projection_ebk` — whether the matrix is actually a valid
    (idempotent) projection is the editor's call (``set_projection_matrix``)."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.ROW:
        return None
    return _rational_matrix_or_none(t.matrix)


def parse_embedding(text: str, d: int, r: int):
    """Read a vector-list EBK string (e.g. ``[[1 0 0⟩[0 0 -1/4⟩]``) back to a d×r embedding as a grid
    of display strings, or None. The string's r kets parse as r rows of length d, so we TRANSPOSE
    them into the d×r grid ``set_embedding_matrix`` expects; a wrong variance (a map, not vectors) or
    a shape that isn't r kets of length d is rejected. The inverse of :func:`embedding_ebk`."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.COL:
        return None
    kets = _rational_matrix_or_none(t.matrix)  # r rows (the kets), each d-tall
    if kets is None or len(kets) != r or any(len(k) != d for k in kets):
        return None
    return tuple(tuple(kets[g][i] for g in range(r)) for i in range(d))  # transpose to d×r


def parse_prescaler_diagonal(text: str, d: int) -> tuple[float, ...] | None:
    """Read a bare prescaler 𝐿's plain text back to the diagonal it carries — the inverse
    of :func:`_prescale_vector_list` for the ``("prescaling", "primes")`` tile, the d×d
    covector matrix ``[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩``. The display shows the full
    matrix even though 𝐿 IS diagonal (off-diagonal cells pinned 0), so the parser does
    the inverse: parse the matrix via :func:`parse_temperament_data`, verify it's covariant
    and d×d, verify every off-diagonal entry is 0 (else 𝐿 wouldn't be diagonal — reject as
    malformed), and return the diagonal as a d-tuple of floats. None whenever the input
    can't be that shape, so the caller can flag the typed text without mangling the override.
    The reader behind a typed custom-prescaler EBK string (the bare prescaler tile's ptext)."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    # the matrix is d×d, or (d+1)×d when the size factor adds the size-sensitizing row (the
    # rectangular 𝑋 = 𝑍𝐿); only the d diagonal rows are validated and read — the size row is
    # derived from the diagonal + the scheme's size factor, so any typed value there is ignored.
    if t.variance is not Variance.ROW or len(t.matrix) not in (d, d + 1):
        return None
    for i in range(d):
        row = t.matrix[i]
        if len(row) != d:
            return None
        for j, value in enumerate(row):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            if i != j and value != 0:
                return None  # 𝐿 is diagonal; an off-diagonal nonzero is malformed input
    return tuple(float(t.matrix[i][i]) for i in range(d))


def parse_mapping_state(text: str) -> TemperamentState | None:
    """Parse an EBK *map* string into a full state, honouring an optional domain-basis
    prefix (e.g. ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"`` -> a nonstandard temperament).
    None if unparseable, the wrong variance, or not an integer matrix. The inverse of
    the ``("mapping", "primes")`` plain text, which carries that prefix when nonstandard."""
    try:
        t = parse_temperament_data(text)
        if t.variance is not Variance.ROW or _int_matrix_or_none(t.matrix) is None:
            return None
        return from_temperament_data(text)
    except Exception:
        return None


def parse_comma_basis(text: str) -> Matrix | None:
    """Read an EBK *vector* string (e.g. ``[4 -4 1⟩``) back to a comma basis, or
    None if unparseable, the wrong variance (a map, not a vector), or non-integer.
    The inverse of the ``("vectors", "commas")`` plain text."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.COL:
        return None
    return _int_matrix_or_none(t.matrix)


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim the last component off each comma, then re-dual.
    Trimming can collapse commas that were independent into dependent ones over the smaller domain —
    leaving more comma vectors than the new nullity, which would violate d = r + n and show phantom
    comma columns. So keep only a maximal independent subset (each comma that still raises the
    nullity), preserving the surviving commas' values; an emptied set is full rank — just intonation
    over the smaller domain."""
    independent: list[tuple[int, ...]] = []
    for comma in (c[:-1] for c in state.comma_basis):
        trial = independent + [comma]
        if from_comma_basis(tuple(trial)).n == len(trial):  # this comma adds a new nullity dimension
            independent.append(comma)
    if not independent:
        return just_intonation(standard_primes(state.d - 1))  # nothing tempered survives the trim
    return from_comma_basis(tuple(independent))


def can_shrink_domain(state: TemperamentState) -> bool:
    """Whether the domain − applies to ``state``: a standard prime limit (the prime-walk control
    doesn't fit a nonstandard subgroup) with a prime to spare (a domain keeps at least one prime).
    Dropping the top prime may leave a lower prime tempered to a unison — a degenerate result — but
    that is allowed, just as tempering one out via the comma + is; such states render and tune. The
    single source of truth for both the editor's shrink guard and the renderer's decision to show
    the − (so the button appears exactly when a click would shrink)."""
    return is_standard_domain(state.domain_basis) and state.d > 1


def just_intonation(domain_basis) -> TemperamentState:
    """The untempered temperament over a domain — nothing tempered out, every basis element its
    own generator (the identity mapping), so nullity 0. The endpoint both the comma − (removing the
    last comma) and the mapping + (un-tempering it) arrive at. Built from the identity mapping
    rather than by dualizing an empty comma basis, which can't recover the dimension d — and which
    keeps a nonstandard domain that re-dualing would lose."""
    d = len(domain_basis)
    identity = tuple(tuple(int(row == col) for col in range(d)) for row in range(d))
    return from_mapping(identity, domain_basis)


def remove_comma(state: TemperamentState, index: int = -1) -> TemperamentState:
    """Drop comma ``index`` (the last by default) from the basis, then re-dual — raising
    rank as nullity falls (the temperament tempers out one fewer comma). An arbitrary index
    is the comma-space twin of :func:`remove_mapping_row`, reached by dragging a comma column
    out of the basis (un-tempering it). Adding a comma is the Editor's job (it stages a
    pending draft and commits it once valid), not a service primitive, since an arbitrary
    blank comma would be dependent and re-rank nothing. Removing the SOLE comma un-tempers
    everything — just intonation over the domain (see :func:`just_intonation`)."""
    basis = state.comma_basis
    i = index % len(basis)  # normalize, so the -1 default drops the last comma
    remaining = basis[:i] + basis[i + 1:]
    return from_comma_basis(remaining) if remaining else just_intonation(state.domain_basis)


def remove_mapping_row(state: TemperamentState, i: int) -> TemperamentState:
    """Drop mapping row ``i`` (a generator), keeping the remaining rows as-is and
    re-dualing the comma basis: rank falls, nullity rises, dimensionality held
    (−r, +n). The row-space dual of :func:`remove_comma` (which drops a comma to
    raise rank). Callers guard against removing the sole row. Adding a mapping row
    is the comma-space :func:`remove_comma` reached from the mapping (+r, −n)."""
    kept = state.mapping[:i] + state.mapping[i + 1:]
    return from_mapping(kept)


def add_mapping_row(state: TemperamentState) -> TemperamentState:
    """Add a generator by un-tempering a comma — the row-space face of :func:`remove_comma`:
    dropping the last comma and re-dualing IS adding a generator (+r, −n, dimensionality held).
    Re-dualing (rather than splicing the comma in as a raw row) keeps the generators simple: a raw
    comma row detempers to an astronomically complex ratio. Un-tempering the LAST comma leaves
    just intonation over the d primes. Callers guard on there being a comma (nullity > 0)."""
    return remove_comma(state)  # drop the last comma — the same primitive, viewed from the mapping


# ── domain basis element editing (chapter-9 nonstandard-domain input) ────────────────────────
# When the nonstandard-domain box is on the domain elements are typeable: an element can be
# relabelled in place (a basis relabel that leaves the mapping coordinates untouched) and a new
# element can be added (held just — its own new generator). Both demand the basis stay
# multiplicatively INDEPENDENT, or it names fewer than d directions and d = r + n breaks.

def _as_basis_element(value):
    """Normalize a domain basis element to the storage convention: a bare ``int`` when it is
    integral (a prime/integer like ``7``), else a ``Fraction`` (a nonprime like ``13/5``)."""
    fraction = Fraction(value)
    return fraction.numerator if fraction.denominator == 1 else fraction


def parse_domain_element(text):
    """Parse a typed domain basis element — a positive rational ``≠ 1`` such as ``"7"`` or
    ``"13/5"``. Returns the normalized element (int / Fraction) or ``None`` if it is not a valid
    positive rational (blank, non-numeric, ``≤ 0``, or the unison ``1``, which spans nothing)."""
    try:
        fraction = Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        return None
    if fraction <= 0 or fraction == 1:
        return None
    return _as_basis_element(fraction)


def is_independent_domain_basis(domain_basis) -> bool:
    """Whether the basis elements are multiplicatively independent — no element is a product of
    integer powers of the others, so the d elements really span a d-dimensional domain. A
    dependent basis (e.g. ``2.3.9``, where ``9 = 3²``) is degenerate: it names fewer than d
    independent directions, breaking ``d = r + n``. Tested by the rank of the elements' vectors over
    their simplest prime-only superspace (rank == d iff independent)."""
    elements = tuple(Fraction(e) for e in domain_basis)
    if not elements:
        return False
    superspace = get_simplest_prime_only_basis(tuple(domain_basis))
    vectors = express_quotients_in_domain_basis(elements, superspace)
    return sp.Matrix(vectors).rank() == len(elements)


def can_set_domain_element(state: TemperamentState, index: int, element) -> bool:
    """Whether relabelling basis element ``index`` to ``element`` yields a valid domain — a positive
    rational ``≠ 1`` that leaves the whole basis multiplicatively independent."""
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    trial = state.domain_basis[:index] + (_as_basis_element(parsed),) + state.domain_basis[index + 1:]
    return is_independent_domain_basis(trial)


def set_domain_element(state: TemperamentState, index: int, element) -> TemperamentState:
    """Relabel basis element ``index`` to ``element`` — a pure basis relabel: the mapping
    coordinates are unchanged, they now read over the new element. Callers guard with
    :func:`can_set_domain_element`."""
    new_basis = state.domain_basis[:index] + (_as_basis_element(element),) + state.domain_basis[index + 1:]
    return from_mapping(state.mapping, new_basis)


def can_add_domain_element(state: TemperamentState, element) -> bool:
    """Whether ``element`` can be added to the domain — a positive rational ``≠ 1`` independent of
    the existing basis (a dependent addition would name no new direction)."""
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    return is_independent_domain_basis(tuple(state.domain_basis) + (_as_basis_element(parsed),))


def add_domain_element(state: TemperamentState, element) -> TemperamentState:
    """Enlarge the domain by one basis element, held just: the element becomes its OWN new
    generator (a unit row), tuned pure, while every existing generator keeps its columns and gains a
    0 over the new element. ``d → d+1``, ``r → r+1``, nullity preserved (``n = d − r``) — the
    superspace 'extra prime held just' construction in the domain-enlarging direction. Callers guard
    with :func:`can_add_domain_element`."""
    new_basis = tuple(state.domain_basis) + (_as_basis_element(element),)
    extended = tuple(tuple(row) + (0,) for row in state.mapping)       # existing gens, 0 over the new element
    new_generator = tuple(0 for _ in range(state.d)) + (1,)            # the new element's own pure generator
    return from_mapping(extended + (new_generator,), new_basis)


def can_remove_domain_element(state: TemperamentState) -> bool:
    """Whether a domain basis element can be removed: a domain keeps at least one element, so the
    only bar is ``d == 1``. Unlike :func:`can_shrink_domain` (the standard prime-walk −, which is
    confined to a standard limit and only drops the TOP prime), this gates the nonstandard-domain
    per-element −, which removes ANY element of ANY basis — removing an element from a
    multiplicatively independent basis always leaves an independent one, so no further check."""
    return state.d > 1


def remove_domain_element(state: TemperamentState, index: int) -> TemperamentState:
    """Drop basis element ``index`` from the domain: trim its component off each comma and off the
    basis, then re-dual over the reduced basis. The arbitrary-index, nonstandard-aware generalization
    of :func:`shrink_domain` (which always drops the last component, re-dualing to a standard limit).
    As there, trimming can collapse independent commas into dependent ones, so keep only a maximal
    independent subset (each comma that still raises the nullity over the reduced basis); an emptied
    set is just intonation over the smaller domain. Inverts :func:`add_domain_element` for the element
    it just added (whose comma column is all-zero, so trimming it recovers the prior state). Callers
    guard with :func:`can_remove_domain_element`."""
    i = index % state.d
    new_basis = state.domain_basis[:i] + state.domain_basis[i + 1:]
    independent: list[tuple[int, ...]] = []
    for comma in (c[:i] + c[i + 1:] for c in state.comma_basis):
        trial = independent + [comma]
        if from_comma_basis(tuple(trial), new_basis).n == len(trial):  # raises the nullity over the reduced basis
            independent.append(comma)
    if not independent:
        return just_intonation(new_basis)  # nothing tempered survives the trim
    return from_comma_basis(tuple(independent), new_basis)


def add_mapping_row_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    """Add generator row ``source`` into row ``target`` (the row dropped onto): ``target``'s
    mapping row becomes ``row[target] + row[source]``. A unimodular row operation, so the
    temperament (its comma basis, rank and nullity) is untouched — only the generator basis
    changes, re-expressing the same tuning over a different generating set. The dragged
    generator's ratio shifts (e.g. the octave dropped onto the fifth becomes a fourth) while the
    target's stays put; callers transform any frozen generator tuning to hold the sound. Callers
    guard ``source != target`` (adding a row to itself would double it, enfactoring the mapping)."""
    rows = [list(row) for row in state.mapping]
    rows[target] = [t + s for t, s in zip(rows[target], rows[source])]
    return from_mapping(rows, state.domain_basis)


def add_comma_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    """Add comma ``source`` into comma ``target`` (the comma dropped onto): ``target``'s vector
    becomes ``comma[target] + comma[source]``. The dual of :func:`add_mapping_row_to` — a
    unimodular column operation on the comma basis, so the temperament (its mapping, rank and
    nullity) is untouched; only which intervals name the nullspace changes. The mapping is the
    comma basis's dual and is unaffected, so unlike the row op no tuning transform is needed.
    Callers guard ``source != target`` (adding a comma to itself would double it)."""
    commas = [list(comma) for comma in state.comma_basis]
    commas[target] = [t + s for t, s in zip(commas[target], commas[source])]
    return from_comma_basis(commas, state.domain_basis)
