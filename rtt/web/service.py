"""The sole seam between the web UI and the RTT library.

Everything the front end needs is expressed here in plain tuples/ints/strings so
the UI never imports library types directly. A :class:`TemperamentState` bundles
a temperament's mapping and its dual comma basis (kept in sync) plus dimensions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction

from rtt.canonicalization import canonical_ca, canonical_ma
from rtt.dimensions import get_d, get_n, get_r
from rtt.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    get_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.dual import dual
from rtt.formatting import to_ebk
from rtt.generator_detempering import get_generator_detempering
from rtt.math_utils import get_primes, pcv_to_quotient
from rtt.matrix_utils import Matrix
from rtt.parsing import parse_quotient_list, parse_temperament_data
from rtt.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)
from rtt.temperament import Temperament, Variance
from rtt.tuning import (
    damage_weights,
    get_complexity,
    get_complexity_prescaler,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    tuning_map_from_generators,
)
from rtt.tuning_ranges import get_generator_tuning_range
from rtt.tuning_scheme_names import (
    TuningSchemeSpec,
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
    damage: tuple[float, ...]  # |error| (unity weight)


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


def target_interval_set(spec: str, domain_basis) -> tuple[str, ...]:
    """Resolve a target interval set spec against a domain basis, as ratio strings.

    ``spec`` selects the family — a truncated integer-limit triangle (``"TILT"`` /
    ``"N-TILT"``) or an odd-limit diamond (``"OLD"`` / ``"N-OLD"``). With no explicit
    limit the set tracks the domain. ``"TILT"`` is the as-shipped default.
    """
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    if not is_standard_prime_limit_domain_basis(domain):
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


def mapped_detempering(mapping) -> Matrix:
    """The generator detempering ``D`` mapped through ``M`` — ``M·D`` in generator
    coordinates (r×r). Each detempering generator maps back to its own generator (D is
    M's right-inverse), so this is the identity: the dual of the comma basis vanishing
    (:func:`mapped_commas`), the temperament's two right/left-inverse relations side by side."""
    m = _to_matrix(mapping)
    return _map_through(m, generator_detempering(m))


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
    ``tuning_map = generators · mapping``, rather than the scheme's optimum. Used when the
    optimize lock is off and the user has frozen/edited the generator tuning. Just map and
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


def interval_sizes(tun: Tuning, ratios, domain_basis=None) -> IntervalSizes:
    """Project an interval set through ``tun`` — its tempered/just sizes, error, damage.
    Over a nonstandard ``domain_basis`` each ratio is expressed in that basis (matching the
    basis ``tun`` runs over)."""
    vectors = _interval_vectors(ratios, domain_basis, len(tun.tuning_map))
    tempered = tuple(_over(tun.tuning_map, m) for m in vectors)
    just = tuple(_over(tun.just_map, m) for m in vectors)
    errors = tuple(t_ - j for t_, j in zip(tempered, just))
    return IntervalSizes(tempered, just, errors, tuple(abs(e) for e in errors))


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

# the trailing letter each weight slope carries in a systematic scheme name (minimax-U/-S/-C) —
# the slope is always the name's final character, so a named scheme's slope is swapped by
# replacing that letter, keeping the scheme nameable rather than degrading it to an unnamed spec.
WEIGHT_SLOPE_LETTERS = {"unity-weight": "U", "simplicity-weight": "S", "complexity-weight": "C"}

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
    """``scheme`` with its complexity prescaler swapped to ``prescaler`` (one of
    :data:`PRESCALERS`), keeping its optimization power, target and damage slope. Returns a
    resolved spec (which the service/layout accept anywhere a scheme name is taken)."""
    log_prime_power, prime_power = PRESCALERS[prescaler]
    return replace(
        resolve_tuning_scheme(scheme),
        complexity_log_prime_power=log_prime_power,
        complexity_prime_power=prime_power,
        complexity_size_factor=0,
    )


def scheme_with_norm(scheme, euclidean: bool):
    """``scheme`` with its complexity norm power set to 2 (Euclidean) or 1 (taxicab) — the
    alt.-complexity control in box 𝒄 — keeping everything else. Returns a resolved spec."""
    return replace(resolve_tuning_scheme(scheme), complexity_norm_power=2.0 if euclidean else 1.0)


def scheme_with_power(scheme, power: float):
    """``scheme`` with its optimization power set to ``power`` — the editable 𝑝 field in the
    optimization box (∞ minimax, 2 miniRMS, 1 miniaverage) — keeping everything else. Returns
    a resolved spec (accepted anywhere a scheme name is)."""
    return replace(resolve_tuning_scheme(scheme), optimization_power=float(power))


def is_euclidean(scheme) -> bool:
    """Whether ``scheme`` uses the Euclidean (q=2) complexity norm rather than taxicab (q=1)."""
    return resolve_tuning_scheme(scheme).complexity_norm_power == 2


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
    key) — the weight box's chooser — keeping the complexity and optimization power. A named
    scheme keeps its name (the trailing U/S/C letter is swapped, e.g. ``minimax-S`` →
    ``minimax-U``) so the chooser can still name it; a control-refined spec stays a spec."""
    if isinstance(scheme, str):
        bare = scheme.rstrip()
        if bare and bare[-1] in "USC":  # a systematic name ends in its slope letter
            return bare[:-1] + WEIGHT_SLOPE_LETTERS[slope]
    return replace(resolve_tuning_scheme(scheme), damage_weight_slope=WEIGHT_SLOPES[slope])


def weight_slope_variants(name: str) -> tuple[str, ...]:
    """``name``'s simplicity / unity / complexity weight variants — its trailing U/S/C letter
    swapped to each slope. The established-tuning-scheme chooser lists these per complexity family
    so a weight slope is pickable by name (T minimax-S / -U / -C), staying in sync with the box-𝒘
    weight chooser (both set the same scheme trait)."""
    return tuple(scheme_with_weight_slope(name, slope) for slope in _WEIGHT_VARIANT_ORDER)


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
    """A tuning scheme as a JSON-safe value, for persistence: a bare name string, or a
    spec dict for a control-refined scheme. The infinite optimization power (minimax) is
    encoded as the string ``"inf"`` because the JSON layer writes a raw float infinity as
    null. The inverse is :func:`scheme_from_json`."""
    if isinstance(scheme, str):
        return scheme
    data = asdict(scheme)
    if data["optimization_power"] == float("inf"):
        data["optimization_power"] = "inf"
    return data


def scheme_from_json(data):
    """Rebuild a tuning scheme from :func:`scheme_to_json`'s output — a name string passes
    through; a spec dict is rehydrated into a :class:`TuningSchemeSpec`, decoding the
    ``"inf"`` optimization-power sentinel back to a float."""
    if isinstance(data, str):
        return data
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
    weights, and the tuning solve. ``None`` (the default) keeps today's behavior."""
    if override is not None:
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
) -> dict[tuple[str, str], str]:
    """Each value group's natural plain-text form, keyed by its ``(row, column)``
    tile (the same vocabulary the spreadsheet layout uses). The grid and this text
    show the same numbers two ways — the EBK string is the inline notation. ``held``
    (the held interval vectors), ``interest`` (the other-intervals-of-interest vectors),
    ``generator_tuning`` (a frozen manual tuning) and ``target_override`` (a typed explicit
    target list) are threaded into the same tuning/targets the grid builds, so the two views
    can't diverge."""
    db = state.domain_basis
    targets = displayed_targets(state, scheme, target_spec, target_override)  # all-interval-aware, like the grid
    commas = comma_ratios(state.comma_basis, db)
    mapped = mapped_intervals(state.mapping, targets, db)
    mapped_comma = mapped_commas(state.mapping, state.comma_basis)
    target_vectors = target_interval_vectors(targets, state.d, db)
    held_ratios = comma_ratios(held, db) if held else ()
    # match the grid's tuning exactly: a frozen manual generator tuning (optimize lock off)
    # drives the maps directly; otherwise the scheme's optimum holding the held intervals just
    if generator_tuning is not None and len(generator_tuning) == len(state.mapping):
        tun = tuning_from_generators(state.mapping, generator_tuning, db)
    else:  # a typed target-list override retunes the optimum, matching the grid's own tuning
        tun = tuning(state.mapping, scheme, db, held=held_ratios, targets=target_override)
    target_sizes = interval_sizes(tun, targets, db)
    comma_sizes = interval_sizes(tun, commas, db)  # comma sizes, like the grid's commas column
    detemper_ratios = generators(state.mapping, db)  # the detempering as ratios (= service.generators)
    detemper_sizes = interval_sizes(tun, detemper_ratios, db)  # tempered = the genmap, plus just/error
    detemper_vectors = generator_detempering(state.mapping)  # D's vectors, for the prescaling matrix
    # the weighting region: complexity (a covector over the primes, lists elsewhere), the
    # per-target weight list, and the prescaling matrices (L applied to each vector set, as
    # ket lists). Complexity over the primes is the complexity of each domain basis element.
    prime_ratios = tuple(f"{p}/1" for p in standard_primes(state.d))
    prescaler = complexity_prescaler(state.mapping, scheme)
    prime_units = tuple(tuple(1 if i == p else 0 for i in range(state.d)) for p in range(state.d))

    def _prescaled(vectors):
        return tuple(tuple(prescaler[i] * v[i] for i in range(state.d)) for v in vectors)
    # Keyed by the tile each value group occupies. The interval-vectors row holds the
    # vector lists (close ⟩); the mapping row holds the mapping (a list of maps, close ])
    # and the mapped lists (generator-coordinate vectors, close }). The editable duals
    # are the mapping (mapping/primes) and the comma basis (vectors/commas). The
    # quantities-row ratios get a per-column plain text in the layout, not here; the
    # generators (mapping/quantities) carry no plain-text form.
    values = {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        ("vectors", "commas"): _ket_list(state.comma_basis, "⟩"),
        ("vectors", "targets"): _ket_list(target_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(state),
        ("mapping", "commas"): _ket_list(zip(*mapped_comma), "}"),
        ("mapping", "detempering"): _ket_list(zip(*mapped_detempering(state.mapping)), "}"),
        ("mapping", "targets"): _ket_list(zip(*mapped), "}"),
        ("tuning", "gens"): _cents_genmap(tun.generator_map),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(comma_sizes.tempered),
        # the detempering's tempered sizes ARE the generator tuning map (𝒕D = 𝒈), shown
        # genmap-style ({ ]); its just and retuning sizes are ordinary cents lists
        ("tuning", "detempering"): _cents_genmap(detemper_sizes.tempered),
        ("tuning", "targets"): _cents_list(target_sizes.tempered),
        ("just", "primes"): _cents_map(tun.just_map),
        ("just", "commas"): _cents_list(comma_sizes.just),
        ("just", "detempering"): _cents_list(detemper_sizes.just),
        ("just", "targets"): _cents_list(target_sizes.just),
        ("retune", "primes"): _cents_map(tun.retuning_map),
        ("retune", "commas"): _cents_list(comma_sizes.errors),
        ("retune", "detempering"): _cents_list(detemper_sizes.errors),
        ("retune", "targets"): _cents_list(target_sizes.errors),
        ("damage", "targets"): _cents_list(target_sizes.damage),
        # the bare prescaler 𝐿 is the asymmetric exception of the prescaling row: it reads
        # as a covector stack like the mapping — per-row ⟨ … ] (angle open + square close)
        # inside outer [ … ⟩ (square open + ket close). Every 𝐿·basis product (𝐿C/𝐿D/𝐿H/𝐿T)
        # is instead a matrix of prescaled VECTORS — per-column ket [ … ⟩ inside symmetric
        # outer [ … ] — so the bare prescaler reads as the matrix itself rather than a
        # product with another basis.
        ("prescaling", "primes"): _prescale_vector_list(_prescaled(prime_units), col="⟨]", outer="[⟩"),
        ("prescaling", "commas"): _prescale_vector_list(_prescaled(state.comma_basis)),
        ("prescaling", "detempering"): _prescale_vector_list(_prescaled(detemper_vectors)),
        ("prescaling", "targets"): _prescale_vector_list(_prescaled(target_vectors)),
        ("complexity", "primes"): _cents_map(interval_complexities(state.mapping, scheme, prime_ratios)),
        ("complexity", "commas"): _cents_list(interval_complexities(state.mapping, scheme, commas, domain_basis=db)),
        ("complexity", "detempering"): _cents_list(interval_complexities(state.mapping, scheme, detemper_ratios, domain_basis=db)),
        ("complexity", "targets"): _cents_list(interval_complexities(state.mapping, scheme, targets, domain_basis=db)),
        ("weight", "targets"): _cents_list(interval_weights(state.mapping, scheme, targets, domain_basis=db)),
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
            ("prescaling", "held"): _prescale_vector_list(_prescaled(held)),
            ("complexity", "held"): _cents_list(interval_complexities(state.mapping, scheme, held_ratios, domain_basis=db)),
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
            ("prescaling", "interest"): _prescale_vector_list(_prescaled(interest), outer=""),
            ("complexity", "interest"): _cents_list(interval_complexities(state.mapping, scheme, interest_ratios, domain_basis=db), wrap=False),
        })
    return values


def _ket_list(vectors, close: str, wrap: bool = True) -> str:
    """A list of column vectors: ``[[1 0 0⟩ [0 1 0⟩]`` for vectors (close ``⟩``),
    ``[[1 0} [0 1}]`` for generator-coordinate vectors (close ``}``). The outer ``[ ]``
    wraps the whole list (a matrix presentation, even a single vector); ``wrap=False``
    drops it for the intervals-of-interest column, whose intervals stand alone."""
    kets = " ".join("[" + " ".join(str(x) for x in v) + close for v in vectors)
    return f"[{kets}]" if wrap else kets


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
    cols = " ".join(col[0] + " ".join(prescale_text(x) for x in v) + col[1] for v in vectors)
    if not outer:
        return cols
    return f"{outer[0]}{cols}{outer[1]}"


def vector_list_pending_text(committed_vectors, pending) -> tuple[str, str, str]:
    """Split a wrapped vector-list plain text for the two-tone draft display: the committed
    vectors and the wrapping ``[ … ]`` stay black, the in-progress draft vector reddens.
    Shared by the comma basis and the target interval list (both wrapped ket lists). Returns
    ``(black_prefix, red_draft_ket, black_suffix)``. The draft ket shows the entered components
    only (``None`` blanks omitted): ``[4, None, 1] -> "[4 1⟩"``."""
    committed = _ket_list(committed_vectors, "⟩")  # e.g. "[[4 -4 1⟩]" — drop its close ] to reopen
    draft = "[" + " ".join(str(x) for x in pending if x is not None) + "⟩"
    return committed[:-1] + " ", draft, "]"


def cents(value: float) -> str:
    """A cents quantity at the 3-dp the grid and plain-text views share, so the
    two displays always agree."""
    return f"{value:.3f}"


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
    body = " ".join(cents(v) for v in values)
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
    if t.variance is not Variance.ROW or len(t.matrix) != d:
        return None
    for i, row in enumerate(t.matrix):
        if len(row) != d:
            return None
        for j, val in enumerate(row):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                return None
            if i != j and val != 0:
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
    """Drop the highest prime from the domain: trim each comma, then re-dual."""
    shrunk = tuple(comma[:-1] for comma in state.comma_basis)
    return from_comma_basis(shrunk)


def remove_comma(state: TemperamentState, index: int = -1) -> TemperamentState:
    """Drop comma ``index`` (the last by default) from the basis, then re-dual — raising
    rank as nullity falls (the temperament tempers out one fewer comma). An arbitrary index
    is the comma-space twin of :func:`remove_mapping_row`, reached by dragging a comma column
    out of the basis (un-tempering it). Adding a comma is the Editor's job (it stages a
    pending draft and commits it once valid), not a service primitive, since an arbitrary
    blank comma would be dependent and re-rank nothing. Callers guard against removing the
    sole comma."""
    basis = state.comma_basis
    i = index % len(basis)  # normalize, so the -1 default drops the last comma
    return from_comma_basis(basis[:i] + basis[i + 1:])


def remove_mapping_row(state: TemperamentState, i: int) -> TemperamentState:
    """Drop mapping row ``i`` (a generator), keeping the remaining rows as-is and
    re-dualing the comma basis: rank falls, nullity rises, dimensionality held
    (−r, +n). The row-space dual of :func:`remove_comma` (which drops a comma to
    raise rank). Callers guard against removing the sole row. Adding a mapping row
    is the comma-space :func:`remove_comma` reached from the mapping (+r, −n)."""
    kept = state.mapping[:i] + state.mapping[i + 1:]
    return from_mapping(kept)


def add_mapping_row(state: TemperamentState) -> TemperamentState:
    """Add a generator by un-tempering a comma: drop a comma from the basis and re-dual to the
    canonical higher-rank mapping — rank rises, nullity falls, dimensionality held (+r, −n).
    Re-dualing (rather than splicing the comma in as a raw row) keeps the generators simple:
    a raw comma row detempers to an astronomically complex ratio. Un-tempering the LAST comma
    leaves nothing tempered — just intonation over the d primes (the identity mapping, whose
    generators are the primes themselves). Callers guard on there being a comma (nullity > 0)."""
    remaining = state.comma_basis[:-1]
    if remaining:
        return from_comma_basis(remaining)
    return from_mapping(tuple(tuple(int(i == j) for j in range(state.d)) for i in range(state.d)))


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
