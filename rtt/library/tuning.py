from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import inf, log2

import numpy as np
from scipy.linalg import null_space

from rtt.library.dimensions import get_d
from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.dual import dual, mapping_matrix
from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, pcv_to_quotient, quotient_to_pcv
from rtt.library.parsing import parse_quotient_list, parse_quotients
from rtt.library.target_intervals import process_old, process_tilt
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning_scheme_names import TuningSchemeSpec, resolve_tuning_scheme
from rtt.library.tuning_solvers import solve_optimum


def optimize_generator_tuning_map(
    t: Temperament, spec: TuningSchemeSpec | str, prescaler_override=None,
) -> tuple[float, ...]:
    """The generator tuning map minimizing target interval damage under the scheme.

    ``spec`` may be a :class:`TuningSchemeSpec`, a systematic tuning-scheme name string,
    or a historical scheme name (e.g. ``"TOP"``, ``"TE"``, ``"CTE"``).

    ``prescaler_override`` (a d-tuple) bypasses the spec's trait-derived prescaler
    diagonal, riding through into the damage-weight complexities; ``None`` keeps the
    existing behavior."""
    spec = resolve_tuning_scheme(spec)

    # trait 7, prime-based: re-express the temperament over its simplest prime-only basis,
    # optimize there, then map the generators back to the original (nonprime) basis.
    prime_based = spec.nonprime_basis_approach == "prime-based" and not (
        is_standard_prime_limit_domain_basis(get_domain_basis(t))
    )
    solve_t = _change_to_simplest_prime_basis(t) if prime_based else t
    solve_spec = replace(spec, nonprime_basis_approach="") if prime_based else spec

    generators = _solve_generators(solve_t, solve_spec, prescaler_override=prescaler_override)
    if prime_based:
        generators = _retrieve_prime_domain_basis_generators(generators, t, solve_t)

    if spec.destretched_interval:
        mapping = np.array(mapping_matrix(t), dtype=float)
        just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)
        generators = _destretch(
            generators, spec.destretched_interval, mapping, just_tuning_map, get_d(t)
        )
    return tuple(float(g) for g in generators)


def _solve_generators(t: Temperament, spec: TuningSchemeSpec, prescaler_override=None) -> np.ndarray:
    """The optimum generators for a scheme over the temperament's own domain basis."""
    d = get_d(t)
    mapping = np.array(mapping_matrix(t), dtype=float)  # r x d
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)  # d
    if _is_all_interval(spec) and spec.complexity_size_factor != 0:
        return _optimize_augmented_all_interval(
            t, spec, mapping, just_tuning_map, d, prescaler_override=prescaler_override,
        )
    vectors, weights, power = _optimization_setup(t, spec, d, prescaler_override=prescaler_override)
    return _constrained_solve(
        mapping, just_tuning_map, vectors, weights, power, _held_vectors(spec, d)
    )


def _change_to_simplest_prime_basis(t: Temperament) -> Temperament:
    """Re-express a temperament over the simplest prime-only basis containing its subgroup,
    by embedding its comma basis into that prime superspace."""
    comma_basis = t if t.variance is Variance.COL else dual(t)
    prime_basis = get_simplest_prime_only_basis(get_domain_basis(t))
    return dual(change_domain_basis_for_c(comma_basis, prime_basis))


def _retrieve_prime_domain_basis_generators(
    generators: np.ndarray, original_t: Temperament, prime_t: Temperament
) -> np.ndarray:
    """Convert generators optimized over the prime basis back to the original (nonprime)
    basis: re-derive the prime tuning map, restrict it to the original basis elements, then
    recover the original temperament's generators from that tuning map."""
    prime_mapping = np.array(mapping_matrix(prime_t), dtype=float)
    tuning_over_primes = np.asarray(generators) @ prime_mapping
    basis_change = np.array(
        express_quotients_in_domain_basis(
            get_domain_basis(original_t), get_domain_basis(prime_t)
        ),
        dtype=float,
    )  # original-basis elements as prime-basis vectors
    tuning_over_original = tuning_over_primes @ basis_change.T
    return np.array(
        generator_tuning_map_from_t_and_tuning_map(original_t, tuple(tuning_over_original))
    )


def _is_all_interval(spec: TuningSchemeSpec) -> bool:
    """Whether the scheme targets every interval (an empty target set), which by duality
    becomes an optimization over the primes (or the size-augmented primes)."""
    return spec.target_intervals is not None and spec.target_intervals.strip() in ("{}", "")


def _constrained_solve(
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    vectors: tuple[tuple[int, ...], ...],
    weights: np.ndarray,
    power: float,
    held_vectors: np.ndarray | None,
) -> np.ndarray:
    """The generators minimizing the weighted ``power``-norm of the target damages, holding
    any ``held_vectors`` exactly justly (reparameterizing onto the held-justly subspace)."""
    targets = np.array(vectors, dtype=float).reshape(-1, mapping.shape[1])  # k x d
    tempered = (targets @ mapping.T) * weights[:, None]  # k x r
    just = (targets @ just_tuning_map) * weights  # k
    if held_vectors is None:
        return solve_optimum(tempered, just, power, mapping.shape[0])
    tempered_side = held_vectors @ mapping.T  # n_held x r
    held_generators, *_ = np.linalg.lstsq(tempered_side, held_vectors @ just_tuning_map, rcond=None)
    held_null = null_space(tempered_side)
    if held_null.shape[1] == 0:
        return held_generators  # held intervals pin the tuning
    # g = held_generators + held_null @ y, optimizing only the held-justly subspace
    free = solve_optimum(
        tempered @ held_null, just - tempered @ held_generators, power, held_null.shape[1]
    )
    return held_generators + held_null @ free


def _optimize_augmented_all_interval(
    t: Temperament,
    spec: TuningSchemeSpec,
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    d: int,
    prescaler_override=None,
) -> np.ndarray:
    """All-interval schemes with a size factor (Weil/lils family) augment the system with a
    phantom prime: an extra generator and a mapping row ``(size_factor·log2(p), -1)``, the
    phantom tuned justly to 0 and weighted 1. After solving, the phantom generator is dropped."""
    rank = mapping.shape[0]
    size_factor = spec.complexity_size_factor
    log_primes = np.array([log2(float(q)) for q in get_domain_basis(t)])

    aug_mapping = np.zeros((rank + 1, d + 1))
    aug_mapping[:rank, :d] = mapping
    aug_mapping[rank, :d] = size_factor * log_primes
    aug_mapping[rank, d] = -1.0
    aug_just = np.append(just_tuning_map, 0.0)

    primes, prime_weights, power = _optimization_setup(
        t, replace(spec, complexity_size_factor=0), d,
        prescaler_override=prescaler_override,
    )
    aug_vectors = np.eye(d + 1)
    weights = np.append(prime_weights, 1.0)  # phantom prime weighted 1

    held = _held_vectors(spec, d)
    # Each held vector's phantom component is size_factor · (log_primes · v) — its just log2 size,
    # scaled — mirroring the size-stretch row of the mapping augmentation (``size_factor·log2(p)``).
    # That makes the phantom generator's stretch cancel out of the held constraint, so the held
    # interval's real tempered size equals its just size. The octave's component is
    # size_factor · log2(2) = 1, which a bare constant 1 matched only by coincidence — silently
    # mistuning every non-octave held interval.
    aug_held = (
        None if held is None
        else np.hstack([held, size_factor * (held @ log_primes)[:, None]])
    )

    generators = _constrained_solve(aug_mapping, aug_just, aug_vectors, weights, power, aug_held)
    return generators[:rank]  # drop the phantom generator


def _destretch(
    generators: np.ndarray,
    destretched_interval: str,
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    d: int,
) -> np.ndarray:
    """Rescale the whole tuning so the destretched interval comes out exactly just."""
    interval = np.array(_parse_interval_spec(destretched_interval, d)[0], dtype=float)
    just_size = just_tuning_map @ interval
    tempered_size = (generators @ mapping) @ interval
    return generators * (just_size / tempered_size)


def _optimization_setup(
    t: Temperament, spec: TuningSchemeSpec, d: int, prescaler_override=None,
) -> tuple[tuple[tuple[int, ...], ...], np.ndarray, float]:
    """The (target vectors, per-target damage weights, optimization power) for the scheme.

    An all-interval scheme (empty target set) instead optimizes over the primes with
    simplicity weighting, at the dual of the interval-complexity norm power — minimax
    over every interval is, by duality, this optimization over the primes.

    A non-diagonal pretransformer 𝑋 (a hand-edited matrix override) generalizes that duality:
    minimax over every interval of ``|𝒓v| / ‖𝑋v‖`` equals ``‖𝒓𝑋⁻¹‖`` at the dual norm power, which
    is the unit-weighted minimax over the COLUMNS of 𝑋⁻¹ (each ``𝒓·colⱼ`` is a component of
    ``𝒓𝑋⁻¹``). For a diagonal 𝑋 those columns are ``(1/𝐿ᵢ)·eᵢ``, reproducing the per-prime path —
    so this is taken only when the override is an actual matrix, keeping the integer-prime targets
    (and their quotient labels) for every diagonal scheme."""
    if spec.target_intervals is None:
        return (), np.array([]), spec.optimization_power  # held intervals alone pin the tuning
    if spec.target_intervals.strip() in ("{}", ""):
        if prescaler_override is not None and np.ndim(prescaler_override) == 2:
            inverse_columns = np.linalg.inv(np.asarray(prescaler_override, dtype=float)).T
            return (tuple(map(tuple, inverse_columns)), np.ones(d),
                    get_dual_power(spec.complexity_norm_power))
        primes = tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
        weights = damage_weights(
            primes, t, replace(spec, damage_weight_slope="simplicityWeight"),
            prescaler_override=prescaler_override,
        )
        return primes, weights, get_dual_power(spec.complexity_norm_power)
    vectors = resolve_target_intervals(spec.target_intervals, t, d)
    return vectors, damage_weights(vectors, t, spec, prescaler_override=prescaler_override), spec.optimization_power


def optimize_tuning_map(
    t: Temperament, spec: TuningSchemeSpec | str, prescaler_override=None,
) -> tuple[float, ...]:
    """The optimum tuning map (the generators applied to the mapping) under the scheme."""
    generators = np.array(
        optimize_generator_tuning_map(t, spec, prescaler_override=prescaler_override), dtype=float,
    )
    mapping = np.array(mapping_matrix(t), dtype=float)
    return tuple(float(x) for x in generators @ mapping)


def get_tuning_map_damages(
    t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str
) -> dict:
    """Each target interval's damage under a *given* tuning map (not an optimization):
    the scheme-weighted absolute error, keyed by the interval's quotient."""
    vectors, damages, _ = _evaluate_damages(t, tuning_map, spec)
    return {pcv_to_quotient(vector): float(damage) for vector, damage in zip(vectors, damages)}


def get_generator_tuning_map_damages(
    t: Temperament, generator_tuning_map: tuple, spec: TuningSchemeSpec | str
) -> dict:
    """Each target interval's damage under a given *generator* tuning map."""
    return get_tuning_map_damages(t, tuning_map_from_generators(t, generator_tuning_map), spec)


def get_tuning_map_mean_damage(
    t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str
) -> float:
    """The scheme's mean damage of a given tuning map: the power-mean of the target damages
    at the optimization power (the max for minimax, RMS for miniRMS, and so on)."""
    _, damages, power = _evaluate_damages(t, tuning_map, spec)
    if power == inf:
        return float(np.max(damages))
    return float((np.sum(damages**power) / len(damages)) ** (1 / power))


def get_generator_tuning_map_mean_damage(
    t: Temperament, generator_tuning_map: tuple, spec: TuningSchemeSpec | str
) -> float:
    """The scheme's mean damage of a given generator tuning map."""
    return get_tuning_map_mean_damage(t, tuning_map_from_generators(t, generator_tuning_map), spec)


def tuning_map_from_generators(t: Temperament, generator_tuning_map: tuple) -> np.ndarray:
    """The tuning map a generator tuning produces: the generators applied to the mapping
    (``generators @ M``). The manual-tuning counterpart of an optimized tuning map."""
    return np.array(generator_tuning_map, dtype=float) @ np.array(mapping_matrix(t), dtype=float)


def _evaluate_damages(
    t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str
) -> tuple[tuple[tuple[int, ...], ...], np.ndarray, float]:
    """The (target vectors, per-target damages, mean power) for a given tuning map: each
    damage is the scheme's weight times the absolute mistuning of that target."""
    spec = resolve_tuning_scheme(spec)
    d = get_d(t)
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)
    vectors, weights, power = _optimization_setup(t, spec, d)
    targets = np.array(vectors, dtype=float).reshape(-1, d)
    tempered = np.array(tuning_map, dtype=float)
    damages = np.abs(targets @ tempered - targets @ just_tuning_map) * weights
    return vectors, damages, power


def resolve_target_intervals(
    target_spec: str, t: Temperament, d: int
) -> tuple[tuple[int, ...], ...]:
    """Resolve a target interval spec to vectors: an explicit ``{...}`` quotient list, a
    TILT/OLD named scheme, or ``"primes"`` (the identity).

    Intervals outside the domain are dropped — over a standard prime limit, a quotient needing a
    prime beyond the d-th (a target limit raised past the domain); over a nonstandard basis, a
    quotient outside the subgroup. Unisons are dropped too: a unison has no mistuning to optimize,
    and its zero complexity would make a simplicity weight infinite."""
    domain_basis = get_domain_basis(t)
    if target_spec == "primes":
        return tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
    if "TILT" in target_spec or "truncated integer limit triangle" in target_spec:
        quotients = process_tilt(target_spec, domain_basis)
    elif "OLD" in target_spec or "odd limit diamond" in target_spec:
        quotients = process_old(target_spec, domain_basis)
    else:
        quotients = parse_quotients(target_spec)
    if is_standard_prime_limit_domain_basis(domain_basis):
        pcvs = [v for v in (quotient_to_pcv(q) for q in quotients) if len(v) <= d]
        vectors = pad_vectors_with_zeros_up_to_d(tuple(pcvs), d)
    else:
        in_basis = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain_basis)
        vectors = express_quotients_in_domain_basis(in_basis, domain_basis)
    return tuple(v for v in vectors if any(v))  # drop the unison (an all-zero vector)


def _parse_interval_spec(text: str, d: int) -> tuple[tuple[int, ...], ...]:
    """Parse an interval-set spec (``"octave"``, ``"2"``, ``"2/1"``, ``"{2/1, 3/2}"``) into vectors."""
    return parse_quotient_list(text.replace("octave", "2"), d)


def _held_vectors(spec: TuningSchemeSpec, d: int) -> np.ndarray | None:
    """The vectors of the scheme's held intervals (tuned exactly justly), or ``None``."""
    if not spec.held_intervals:
        return None
    return np.array(_parse_interval_spec(spec.held_intervals, d), dtype=float)


def damage_weights(
    vectors: tuple[tuple[int, ...], ...],
    t: Temperament,
    spec: TuningSchemeSpec,
    prescaler_override=None,
) -> np.ndarray:
    """The per-target damage weights: 1 (unity), complexity, or 1/complexity.

    ``prescaler_override`` rides into each per-target complexity (the slope rolls off
    the same diagonal the matrix tile shows), so a custom diagonal reaches the tuning
    solve too rather than only the displayed prescaler."""
    if spec.damage_weight_slope == "unityWeight":
        return np.ones(len(vectors))
    complexities = np.array(
        [
            get_complexity(
                vector,
                t,
                spec.complexity_norm_power,
                spec.complexity_log_prime_power,
                spec.complexity_prime_power,
                spec.complexity_size_factor,
                spec.nonprime_basis_approach,
                prescaler_override=prescaler_override,
            )
            for vector in vectors
        ]
    )
    if spec.damage_weight_slope == "complexityWeight":
        return complexities
    if spec.damage_weight_slope == "simplicityWeight":
        return 1.0 / complexities
    raise ValueError(f"unknown damage weight slope: {spec.damage_weight_slope!r}")


def get_complexity_prescaler(
    t: Temperament,
    log_prime_power,  # trait 5a
    prime_power,  # trait 5b
    nonprime_basis_approach: str,  # trait 7
    override=None,
) -> list[float]:
    """The diagonal of the complexity prescaler L: each domain basis element's pre-norm
    weight, log2(prime)**a · prime**b (log-prime by default, a=1, b=0). An interval's
    complexity is a norm of L applied to its vector, so this is the matrix that defines it.

    ``override`` is a per-call escape hatch: when set, the four trait arguments are
    ignored and the override is returned verbatim. It is either a d-tuple diagonal OR a full
    d×d matrix (the editable pretransformer tile, once alt-complexity makes the whole square
    editable) — :func:`get_complexity` applies a 2-D override as a matrix-vector product. Threaded
    through the optimization and complexity / weight paths so the web app's bare pretransformer
    tile can hand-edit it without inventing a synthetic spec or monkey-patching every consumer."""
    if override is not None:
        return override
    return _prescaler_diagonal(
        get_domain_basis(t), log_prime_power, prime_power, nonprime_basis_approach
    )


def _prescaler_diagonal(
    domain_basis, log_prime_power, prime_power, nonprime_basis_approach: str
) -> list[float]:
    """The log2(prime)**a · prime**b pre-norm weight for each basis element of ``domain_basis``.
    For a nonprime element the base is its log-product complexity numerator·denominator (e.g.
    7/3 → 7·3) — UNLESS the nonprime-based approach is in force, which treats the element as an
    atom protected against factoring (7/3 → 7/3). Kept basis-parameterized (not temperament-
    parameterized) so :func:`get_complexity` can build it over a lifted prime basis."""
    diagonal = []
    for q in domain_basis:
        fraction = Fraction(q)
        base = (
            float(q)
            if nonprime_basis_approach == "nonprime-based"
            else float(fraction.numerator * fraction.denominator)
        )
        weight = 1.0
        if log_prime_power > 0:
            weight *= log2(base) ** log_prime_power
        if prime_power > 0:
            weight *= base**prime_power
        diagonal.append(weight)
    return diagonal


def get_complexity(
    pcv: tuple,
    t: Temperament,
    norm_power,  # trait 4
    log_prime_power,  # trait 5a
    prime_power,  # trait 5b
    size_factor,  # trait 5c
    nonprime_basis_approach: str,  # trait 7
    prescaler_override=None,
) -> float:
    """An interval's complexity: a (pre-transformed) norm of its vector.

    A nonzero ``size_factor`` augments the pre-transformed vector with one extra entry
    (the size-weighted sum, ``size_factor`` times the interval's log size), then divides
    the norm by ``1 + size_factor`` — the Weil/lils family of complexities.

    ``prescaler_override`` bypasses the trait-driven prescaler — a d-tuple diagonal, or a full
    d×d matrix (a non-diagonal pretransformer) the web app's editable tile rides in. A diagonal
    pre-transforms element-wise (𝐿ᵢvᵢ); a matrix as a matrix-vector product (𝑋·v).

    Over a NONPRIME basis the default (non-override) neutral path lifts the interval into the
    simplest prime-only basis (the superspace) and prescales THERE, because log-product
    complexity is defined on the prime factorization: its quotient form log2(n·d) equals the
    vector form only when the vector is the PRIME-COUNT vector. A per-basis-element diagonal
    would instead double-count a prime shared across two elements that cancels in the true
    quotient (the 3 in 7/3 and 11/3 of 2.7/3.11/3: 11/7 is log2(11·7), not log2(11·3·7·3)).
    The nonprime-based approach deliberately keeps the atomic basis (it redefines complexity);
    prime-based already arrives here over its prime superspace, so the lift is a no-op; an
    override pins the diagonal by hand; coprime and standard bases lift to themselves."""
    domain_basis = get_domain_basis(t)
    if (
        prescaler_override is None
        and nonprime_basis_approach != "nonprime-based"
        and len(pcv) == len(domain_basis)
        and not is_standard_prime_limit_domain_basis(domain_basis)
    ):
        prime_basis = get_simplest_prime_only_basis(domain_basis)
        if tuple(prime_basis) != tuple(domain_basis):  # there really is a nonprime to factor
            lift = express_quotients_in_domain_basis(domain_basis, prime_basis)  # d rows × dL
            pcv = tuple(
                sum(pcv[e] * lift[e][p] for e in range(len(lift)))
                for p in range(len(prime_basis))
            )
            domain_basis = prime_basis
    prescaler = (
        prescaler_override
        if prescaler_override is not None
        else _prescaler_diagonal(
            domain_basis, log_prime_power, prime_power, nonprime_basis_approach
        )
    )
    if np.ndim(prescaler) == 2:  # a full (non-diagonal) pretransformer matrix: 𝑋·v
        transformed = list(np.asarray(prescaler, dtype=float) @ np.asarray(pcv, dtype=float))
    else:  # a diagonal: element-wise 𝐿ᵢvᵢ. zip truncates to the shorter — a nonstandard domain's
        # prescaler can be shorter than the over-primes vector, and only the basis elements count
        transformed = [w * x for w, x in zip(prescaler, pcv)]
    if size_factor != 0:
        transformed.append(size_factor * sum(transformed))
    ord_ = np.inf if norm_power == float("inf") else norm_power
    return float(np.linalg.norm(transformed, ord_)) / (1 + size_factor)


def get_dual_power(power):
    """The Hölder-conjugate (dual) norm power: 1 <-> inf, 2 <-> 2."""
    if power == 1:
        return float("inf")
    return 1 / (1 - 1 / power)


def get_just_tuning_map(t: Temperament) -> tuple[float, ...]:
    """The just tuning map: the size in cents (1200·log2) of each basis element."""
    return tuple(1200.0 * log2(float(q)) for q in get_domain_basis(t))


def generator_tuning_map_from_t_and_tuning_map(
    t: Temperament, tuning_map: tuple
) -> tuple[float, ...]:
    """Recover the generator tuning map from a temperament and a tuning map,
    via a right-inverse of the mapping (the tuning map is generators · mapping)."""
    mapping = np.array(mapping_matrix(t), dtype=float)
    generators = np.array(tuning_map, dtype=float) @ np.linalg.pinv(mapping)
    return tuple(float(x) for x in generators)
