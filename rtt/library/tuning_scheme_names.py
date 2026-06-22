from __future__ import annotations

import re
from dataclasses import dataclass
from math import inf


@dataclass(frozen=True)
class TuningSchemeSpec:
    optimization_power: float
    target_intervals: str | None = None
    damage_weight_slope: str = "unityWeight"
    complexity_norm_power: float = 1
    complexity_log_prime_power: float = 1
    complexity_prime_power: float = 0
    complexity_size_factor: float = 0
    complexity_rough: int = 0
    nonprime_basis_approach: str = ""
    held_intervals: str | None = None
    destretched_interval: str | None = None


_SLOPE_BY_LETTER = {
    "U": "unityWeight",
    "S": "simplicityWeight",
    "C": "complexityWeight",
}
_LETTER_BY_SLOPE = {slope: letter for letter, slope in _SLOPE_BY_LETTER.items()}

_COMPLEXITY_FAMILY = {
    (0, 0, 0): "copfr",
    (1, 0, 0): "",
    (0, 1, 0): "sopfr",
    (1, 0, 1): "lils",
    (0, 1, 1): "ils",
}
_OCTAVE_HOLDING_FAMILY = {"lils": "lols", "ils": "ols"}


_COMPLEXITY_TOKEN_TRAITS = {
    "copfr": {"complexity_log_prime_power": 0, "complexity_prime_power": 0},
    "lopfr": {"complexity_log_prime_power": 1, "complexity_prime_power": 0},
    "lp": {"complexity_log_prime_power": 1, "complexity_prime_power": 0},
    "sopfr": {"complexity_log_prime_power": 0, "complexity_prime_power": 1},
    "prod": {"complexity_log_prime_power": 0, "complexity_prime_power": 1},
    "ils": {
        "complexity_log_prime_power": 0,
        "complexity_prime_power": 1,
        "complexity_size_factor": 1,
    },
    "ols": {
        "complexity_log_prime_power": 0,
        "complexity_prime_power": 1,
        "complexity_size_factor": 1,
        "complexity_rough": 3,
        "held_intervals": "octave",
    },
    "lils": {
        "complexity_log_prime_power": 1,
        "complexity_prime_power": 0,
        "complexity_size_factor": 1,
    },
    "limit": {"complexity_size_factor": 1},
    "lols": {"complexity_size_factor": 1, "complexity_rough": 3, "held_intervals": "octave"},
    "odd": {"held_intervals": "octave"},
}


def _complexity_traits_from_name(name: str) -> dict:
    padded = "-" + name.replace(" ", "-") + "-"
    traits = {
        "complexity_norm_power": _norm_power_from_name(padded),
        "complexity_log_prime_power": 1,
        "complexity_prime_power": 0,
        "complexity_size_factor": 0,
        "complexity_rough": 0,
    }
    for token, overrides in _COMPLEXITY_TOKEN_TRAITS.items():
        if f"-{token}-" in padded:
            traits.update(overrides)
    return traits


def _norm_power_from_name(padded: str) -> float:
    if "-E" in padded:
        return 2
    if "-M" in padded:
        return inf
    numeric = re.search(r"-(\d+(?:\.\d+)?)-?[SCU]-?$", padded)
    return float(numeric.group(1)) if numeric else 1


def damage_name_traits(name: str) -> dict:
    core = name.replace("-damage", "")
    return {
        "damage_weight_slope": _SLOPE_BY_LETTER[core[-1]],
        **_complexity_traits_from_name(core),
    }


def complexity_name_traits(name: str) -> tuple[dict, str | None]:
    traits = _complexity_traits_from_name(name)
    held = traits.pop("held_intervals", None)
    return traits, held


def tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec:
    original = name
    held = destretched = None
    while True:
        prefix = re.match(r"\s*(held|destretched)-(\{[^}]*\}|[\w/]+)\s+(.*)", name, re.DOTALL)
        if not prefix:
            break
        if prefix.group(1) == "held":
            held = prefix.group(2)
        else:
            destretched = prefix.group(2)
        name = prefix.group(3)
    power = _optimization_power_from_name(name)
    target_match = re.search(r"\{[\d/,\s]*\}|\d*-?TILT|\d*-?OLD|primes", name)
    target = target_match.group(0) if target_match else None
    if target is None and ("all-interval" in name or name.strip().endswith("S")):
        target = "{}"
    complexity_traits = _complexity_traits_from_name(name)
    held = complexity_traits.pop("held_intervals", None) or held
    nonprime_approach = (
        "nonprime-based"
        if "nonprime-based" in name
        else "prime-based"
        if "prime-based" in name
        else ""
    )
    slope_letter = name.strip()[-1:]
    if slope_letter not in _SLOPE_BY_LETTER:
        raise ValueError(
            f"{original!r} is not a recognized systematic tuning-scheme name. A systematic "
            f"name ends in a weight-slope letter (U, S, or C), e.g. 'minimax-S', "
            f"'held-octave minimax-ES'. Non-systematic / historical / community scheme names "
            f"are not accepted."
        )
    return TuningSchemeSpec(
        optimization_power=power,
        target_intervals=target,
        damage_weight_slope=_SLOPE_BY_LETTER[slope_letter],
        held_intervals=held,
        destretched_interval=destretched,
        nonprime_basis_approach=nonprime_approach,
        **complexity_traits,
    )


def resolve_tuning_scheme(spec: TuningSchemeSpec | str) -> TuningSchemeSpec:
    if isinstance(spec, str):
        return tuning_scheme_from_systematic_name(spec)
    return spec


def _optimization_power_from_name(name: str) -> float:
    if "minimax" in name:
        return inf
    if "miniRMS" in name:
        return 2
    mean_match = re.search(r"mini-(\d+)-mean", name)
    if mean_match:
        return float(int(mean_match.group(1)))
    return 1


def _annotation_token(family: str, euclidean: bool, letter: str) -> str:
    if family:
        return "-".join((["E"] if euclidean else []) + [family, letter])
    return ("E" if euclidean else "") + letter


def systematic_name(spec: TuningSchemeSpec) -> str | None:
    power = _power_word(spec.optimization_power)
    if power is None:
        return None
    complexity = _complexity_part(spec)
    if complexity is None:
        return None
    family, consumes_octave = complexity
    letter = _LETTER_BY_SLOPE[spec.damage_weight_slope]
    core = f"{power}-" + _annotation_token(family, spec.complexity_norm_power == 2, letter)
    return _scheme_prefix(spec, consumes_octave) + core


def _power_word(power: float) -> str | None:
    if power == inf:
        return "minimax"
    if power == 2:
        return "miniRMS"
    if power == 1:
        return "miniaverage"
    if float(power).is_integer() and power > 0:
        return f"mini-{int(power)}-mean"
    return None


def _complexity_part(spec: TuningSchemeSpec) -> tuple[str, bool] | None:
    if spec.complexity_norm_power not in (1, 2):
        return None
    family = _COMPLEXITY_FAMILY.get(
        (spec.complexity_log_prime_power, spec.complexity_prime_power, spec.complexity_size_factor)
    )
    if family is None:
        return None
    if family in _OCTAVE_HOLDING_FAMILY and spec.complexity_rough:
        return _OCTAVE_HOLDING_FAMILY[family], True
    return family, False


def annotation_code(spec: TuningSchemeSpec, letter: str) -> str:
    complexity = _complexity_part(spec)
    family = complexity[0] if complexity else ""
    return _annotation_token(family, spec.complexity_norm_power == 2, letter)


def _scheme_prefix(spec: TuningSchemeSpec, octave_held_by_complexity: bool) -> str:
    prefix = ""
    if spec.held_intervals and not octave_held_by_complexity:
        prefix += f"held-{spec.held_intervals} "
    if spec.destretched_interval:
        prefix += f"destretched-{spec.destretched_interval} "
    target = (spec.target_intervals or "").strip()
    if target and target != "{}":
        prefix += f"{target} "
    if spec.nonprime_basis_approach:
        prefix += f"{spec.nonprime_basis_approach} "
    return prefix
