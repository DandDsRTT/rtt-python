from __future__ import annotations

from dataclasses import asdict, replace

from rtt.app.service.core import (
    DEFAULT_TARGET_SPEC,
    DEFAULT_TUNING_SCHEME,
    _is_matrix,
    _to_matrix,
    _vectors_to_ratios,
    element_ratio,
    prescale_text,
)
from rtt.app.service.core_targets import target_interval_set
from rtt.library.parsing import parse_quotient_list
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import get_complexity_prescaler, get_dual_power
from rtt.library.tuning_scheme_names import (
    TuningSchemeSpec,
    annotation_code,
    complexity_name_traits,
    resolve_tuning_scheme,
    systematic_name,
)


def optimization_power(scheme: str = DEFAULT_TUNING_SCHEME) -> float:
    return resolve_tuning_scheme(scheme).optimization_power


def held_intervals(scheme: str = DEFAULT_TUNING_SCHEME, d: int = 3) -> tuple[str, ...]:
    held = resolve_tuning_scheme(scheme).held_intervals
    if not held:
        return ()
    return _vectors_to_ratios(parse_quotient_list(held.replace("octave", "2"), d))


def damage_weight_slope(scheme: str = DEFAULT_TUNING_SCHEME) -> str:
    return resolve_tuning_scheme(scheme).damage_weight_slope


PRESCALERS = {"identity": (0, 0), "log-prime": (1, 0), "prime": (0, 1)}

WEIGHT_SLOPES = {
    "complexity-weight": "complexityWeight",
    "unity-weight": "unityWeight",
    "simplicity-weight": "simplicityWeight",
}

_WEIGHT_VARIANT_ORDER = ("simplicity-weight", "unity-weight", "complexity-weight")

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
    log_prime_power, prime_power = PRESCALERS[prescaler]
    return replace(
        resolve_tuning_scheme(scheme),
        complexity_log_prime_power=log_prime_power,
        complexity_prime_power=prime_power,
    )


def scheme_with_complexity_norm_power(scheme, power: float):
    return replace(resolve_tuning_scheme(scheme), complexity_norm_power=float(power))


def complexity_norm_power(scheme) -> float:
    return resolve_tuning_scheme(scheme).complexity_norm_power


def dual_norm_power(scheme) -> float:
    return get_dual_power(complexity_norm_power(scheme))


def scheme_with_power(scheme, power: float):
    return replace(resolve_tuning_scheme(scheme), optimization_power=float(power))


def is_euclidean(scheme) -> bool:
    return resolve_tuning_scheme(scheme).complexity_norm_power == 2


def weight_annotation(scheme=DEFAULT_TUNING_SCHEME) -> str:
    spec = resolve_tuning_scheme(scheme)
    if spec.damage_weight_slope == "unityWeight":
        return "U"
    letter = "C" if spec.damage_weight_slope == "complexityWeight" else "S"
    return annotation_code(spec, letter)


def complexity_annotation(scheme=DEFAULT_TUNING_SCHEME) -> str:
    return annotation_code(resolve_tuning_scheme(scheme), "C")


def is_all_interval(scheme) -> bool:
    targets = resolve_tuning_scheme(scheme).target_intervals
    return targets is not None and targets.strip() in ("{}", "")


def displayed_targets(
    state, scheme=DEFAULT_TUNING_SCHEME, target_spec=DEFAULT_TARGET_SPEC, target_override=None
) -> tuple[str, ...]:
    db = state.domain_basis
    if is_all_interval(scheme):
        return tuple(element_ratio(e) for e in db)
    return target_override if target_override is not None else target_interval_set(target_spec, db)


def base_scheme_name(scheme) -> str | None:
    return systematic_name(replace(resolve_tuning_scheme(scheme), target_intervals="{}"))


def scheme_with_targets(scheme, target_intervals: str):
    return replace(resolve_tuning_scheme(scheme), target_intervals=target_intervals)


def scheme_with_weight_slope(scheme, slope: str):
    return replace(resolve_tuning_scheme(scheme), damage_weight_slope=WEIGHT_SLOPES[slope])


def weight_slope_variants(name: str, weighting: bool) -> tuple[str, ...]:
    slopes = _WEIGHT_VARIANT_ORDER if weighting else ("unity-weight",)
    return tuple(systematic_name(scheme_with_weight_slope(name, slope)) for slope in slopes)


def weight_slope_of(scheme) -> str:
    slope = resolve_tuning_scheme(scheme).damage_weight_slope
    for name, internal in WEIGHT_SLOPES.items():
        if internal == slope:
            return name
    raise ValueError(f"unknown damage weight slope: {slope!r}")


def scheme_with_complexity(scheme, name: str):
    spec = resolve_tuning_scheme(scheme)
    traits, held = complexity_name_traits(COMPLEXITY_NAMES[name])
    if held is None:
        held = None if spec.complexity_rough else spec.held_intervals
    return replace(spec, held_intervals=held, **traits)


def _complexity_signature(spec) -> tuple:
    return (
        spec.complexity_norm_power,
        spec.complexity_log_prime_power,
        spec.complexity_prime_power,
        spec.complexity_size_factor,
        bool(spec.complexity_rough),
    )


def complexity_name_of(scheme) -> str:
    sig = _complexity_signature(resolve_tuning_scheme(scheme))
    for name in COMPLEXITY_NAMES:
        if _complexity_signature(scheme_with_complexity(scheme, name)) == sig:
            return name
    return "custom"


def scheme_with_diminuator(scheme, replaced: bool):
    return replace(resolve_tuning_scheme(scheme), complexity_size_factor=1 if replaced else 0)


def diminuator_replaced(scheme) -> bool:
    return resolve_tuning_scheme(scheme).complexity_size_factor != 0


def complexity_size_factor(scheme) -> float:
    return resolve_tuning_scheme(scheme).complexity_size_factor


def prescaler_of(scheme) -> str:
    spec = resolve_tuning_scheme(scheme)
    traits = (1 if spec.complexity_log_prime_power else 0, 1 if spec.complexity_prime_power else 0)
    for name, t in PRESCALERS.items():
        if t == traits:
            return name
    return "log-prime"


def scheme_to_json(scheme):
    data = asdict(resolve_tuning_scheme(scheme))
    if data["optimization_power"] == float("inf"):
        data["optimization_power"] = "inf"
    return data


def scheme_from_json(data):
    if isinstance(data, str):
        return resolve_tuning_scheme(data)
    data = dict(data)
    if data.get("optimization_power") == "inf":
        data["optimization_power"] = float("inf")
    return TuningSchemeSpec(**data)


def complexity_prescaler(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    override=None,
    domain_basis=None,
    nonprime_approach: str = "",
) -> tuple[float, ...]:
    if override is not None:
        if _is_matrix(override):
            return tuple(tuple(float(x) for x in row) for row in override)
        return tuple(float(x) for x in override)
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    return tuple(
        get_complexity_prescaler(
            t,
            replace(
                spec.complexity,
                nonprime_basis_approach=nonprime_approach or spec.nonprime_basis_approach,
            ),
        )
    )


def displayed_prescaler_name(
    mapping,
    scheme=DEFAULT_TUNING_SCHEME,
    custom_prescaler=None,
    domain_basis=None,
    nonprime_approach: str = "",
) -> str | None:
    if custom_prescaler is not None:
        if _is_matrix(custom_prescaler):
            return None
        computed = complexity_prescaler(
            mapping, scheme, domain_basis=domain_basis, nonprime_approach=nonprime_approach
        )
        shown = tuple(float(x) for x in custom_prescaler)
        if len(shown) != len(computed) or any(
            prescale_text(a) != prescale_text(b) for a, b in zip(shown, computed, strict=False)
        ):
            return None
    return prescaler_of(scheme)
