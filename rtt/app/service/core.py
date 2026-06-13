"""Shared service primitives: the facade's tuple-first vocabulary.

The :class:`Tuning` / :class:`IntervalSizes` bundles, the tuple<->matrix/ratio/vector
converters every sibling shares, the temperament-level computations (tuning, sizes,
complexities, weights), and the cents/prescale display formatters (defined here, at the
bottom of the import graph, so both the scheme helpers and the plain-text builders can
share them without a schemes<->text cycle)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.library.canonicalization import canonical_ca, canonical_ma
from rtt.library.dimensions import get_d, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.formatting import strip_negative_zero
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.math_utils import get_primes, pcv_to_quotient, quotient_to_pcv
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_quotient_list
from rtt.library.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    damage_weights,
    get_complexity,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_ranges import get_generator_tuning_range as _get_generator_tuning_range
from rtt.library.tuning_scheme_names import resolve_tuning_scheme


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


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


def _hashable(value):
    """A hashable (tuple-frozen) copy of an optional sequence argument, for memoization
    keys: handles a flat sequence (a domain basis, a target list, a prescaler diagonal)
    and a nested one (a full prescaler matrix); ``None`` passes through."""
    if value is None:
        return None
    return tuple(tuple(row) if isinstance(row, (tuple, list)) else row for row in value)


def _is_matrix(x) -> bool:
    """Whether a complexity-pretransformer override is a full d×d matrix (a sequence of rows) rather
    than a flat diagonal d-tuple — the editable square's non-diagonal form. Plain-Python (no numpy,
    keeping this module's tuple-only surface): a matrix's first entry is itself a sequence."""
    return bool(x) and isinstance(x[0], (tuple, list))


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
    interval, by duality) and ignores the list.

    Memoized on the (frozen) arguments: the optimization is a pure function of them, and
    one page render asks for the same tuning several times (the grid build plus the
    editor's displayed-scheme / unchanged-interval reads) — as does every render after,
    until the document actually moves. The solves run once per distinct document state."""
    return _cached_tuning(_to_matrix(mapping), scheme, _hashable(domain_basis),
                          nonprime_approach, tuple(held), _hashable(prescaler_override),
                          _hashable(targets))


@lru_cache(maxsize=256)
def _cached_tuning(mapping, scheme, domain_basis, nonprime_approach, held,
                   prescaler_override, targets) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    if targets and (spec.target_intervals or "").strip() not in ("{}", ""):
        spec = replace(spec, target_intervals="{" + ", ".join(targets) + "}")
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if held:  # fold the user's held intervals into the scheme's own (its bare tokens, brace-free)
        own = (spec.held_intervals or "").strip().strip("{}").strip()
        parts = ([own] if own else []) + [r for r in held]
        spec = replace(spec, held_intervals="{" + ", ".join(parts) + "}")
    # one solve serves both maps: the tuning map IS the generators applied to the mapping
    # (optimize_tuning_map re-runs the identical optimization just to take that product)
    gmap = optimize_generator_tuning_map(t, spec, prescaler_override=prescaler_override)
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, gmap))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=gmap,
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
    generator ranges are temperament properties, computed as for the optimum.
    Memoized like :func:`tuning` (the ranges are the expensive part here)."""
    return _cached_tuning_from_generators(
        _to_matrix(mapping), tuple(float(g) for g in generators), _hashable(domain_basis))


@lru_cache(maxsize=256)
def _cached_tuning_from_generators(mapping, generators, domain_basis) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
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
