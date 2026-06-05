"""Tuning-scheme name parsing: the systematic (and historical) scheme names and the
:class:`TuningSchemeSpec` traits they decode to. Pure string handling — no numpy, no
temperament — so the optimizer (rtt.tuning) and the web service can resolve a scheme
without pulling in the solve machinery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import inf


@dataclass(frozen=True)
class TuningSchemeSpec:
    """A tuning scheme's traits: how the optimum generator tuning is chosen.

    ``target_intervals`` is a quotient-list string (the intervals whose mistuning
    is minimized); the complexity traits describe the norm used to weight damage.
    """

    optimization_power: float  # trait 2: inf = minimax, 2 = miniRMS, 1 = miniaverage
    target_intervals: str | None = None  # trait 1
    damage_weight_slope: str = "unityWeight"  # trait 3
    complexity_norm_power: float = 1  # trait 4
    complexity_log_prime_power: float = 1  # trait 5a
    complexity_prime_power: float = 0  # trait 5b
    complexity_size_factor: float = 0  # trait 5c
    nonprime_basis_approach: str = ""  # trait 7
    held_intervals: str | None = None  # trait 0: intervals tuned exactly justly
    destretched_interval: str | None = None  # trait 6: interval rescaled to be just


_SLOPE_BY_LETTER = {
    "U": "unityWeight",
    "S": "simplicityWeight",
    "C": "complexityWeight",
}
_LETTER_BY_SLOPE = {slope: letter for letter, slope in _SLOPE_BY_LETTER.items()}

# The complexity family token each (log-prime power, prime power, size factor) triple names —
# the inverse of the prescaler/size assignments in :func:`_complexity_traits_from_name`. The
# log-product (lp) default contributes no token (it is the bare ``minimax-S``). The size-factor
# families (lils/ils) become their octave-holding forms (lols/ols) when the octave is held — see
# :func:`systematic_name`. A triple absent here is no named complexity (rendered as unnamed).
_COMPLEXITY_FAMILY = {
    (0, 0, 0): "copfr",
    (1, 0, 0): "",  # log-product (lp): the default, no token
    (0, 1, 0): "sopfr",
    (1, 0, 1): "lils",
    (0, 1, 1): "ils",
}
_OCTAVE_HOLDING_FAMILY = {"lils": "lols", "ils": "ols"}


def _complexity_traits_from_name(name: str) -> dict:
    """The complexity traits (4, 5a, 5b, 5c) and any held interval injection an interval-
    complexity name encodes, following source.m's sequential dash-delimited token overrides.

    ``E`` = Euclidean (norm power 2); ``copfr`` = unweighted, ``lopfr``/``lp``/[blank] =
    log-prime (Tenney), ``sopfr``/``prod`` = prime (Benedetti); ``ils``/``ols``/``lils``/
    ``lols``/``limit`` add the size factor (Weil-style); ``ols``/``lols``/``odd`` also hold
    the octave justly."""
    padded = "-" + name.replace(" ", "-") + "-"

    def has(token: str) -> bool:
        return f"-{token}-" in padded

    traits = {
        "complexity_norm_power": 2 if "-E" in padded else 1,
        "complexity_log_prime_power": 1,
        "complexity_prime_power": 0,
        "complexity_size_factor": 0,
    }
    held = None
    if has("copfr"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 0, 0
    if has("lopfr") or has("lp"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 1, 0
    if has("sopfr") or has("prod"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 0, 1
    if has("ils"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 0, 1
        traits["complexity_size_factor"] = 1
    if has("ols"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 0, 1
        traits["complexity_size_factor"], held = 1, "octave"
    if has("lils"):
        traits["complexity_log_prime_power"], traits["complexity_prime_power"] = 1, 0
        traits["complexity_size_factor"] = 1
    if has("limit"):
        traits["complexity_size_factor"] = 1
    if has("lols"):
        traits["complexity_size_factor"], held = 1, "octave"
    if has("odd"):
        held = "octave"
    if held is not None:
        traits["held_intervals"] = held
    return traits


def damage_name_traits(name: str) -> dict:
    """Traits a damage systematic name encodes, e.g. ``"E-copfr-S-damage"``: the slope
    (final letter) plus the complexity traits."""
    core = name.replace("-damage", "")
    return {
        "damage_weight_slope": _SLOPE_BY_LETTER[core[-1]],
        **_complexity_traits_from_name(core),
    }


def complexity_name_traits(name: str) -> tuple[dict, str | None]:
    """The complexity traits an interval-complexity systematic name encodes (e.g.
    ``"copfr-E-complexity"``) and, separately, any interval it holds justly — only the
    ``ols``/``lols`` (log-odd-limit) family hold the octave. Surfacing held on its own keeps
    it out of the trait dict, so a caller applies it explicitly rather than popping it."""
    traits = _complexity_traits_from_name(name)
    held = traits.pop("held_intervals", None)
    return traits, held


# Historical tuning-scheme names, each expressed as the equivalent systematic name.
_ORIGINAL_NAME_SCHEMES = {
    "minimax": "held-octave OLD minimax-U",
    "least squares": "held-octave OLD miniRMS-U",
    "TOP": "minimax-S",
    "TIPTOP": "minimax-S",
    "T1": "minimax-S",
    "TOP-max": "minimax-S",
    "Tenney": "minimax-S",
    "TE": "minimax-ES",
    "Tenney-Euclidean": "minimax-ES",
    "T2": "minimax-ES",
    "TOP-RMS": "minimax-ES",
    "CTE": "held-octave minimax-ES",
    "Constrained Tenney-Euclidean": "held-octave minimax-ES",
    "POTE": "destretched-octave minimax-ES",
    "POTOP": "destretched-octave minimax-S",
    "POTT": "destretched-octave minimax-S",
    "Frobenius": "minimax-E-copfr-S",
    "BOP": "minimax-sopfr-S",
    "Benedetti": "minimax-sopfr-S",
    "BE": "minimax-E-sopfr-S",
    "Benedetti-Euclidean": "minimax-E-sopfr-S",
    "Weil": "minimax-lils-S",
    "WOP": "minimax-lils-S",
    "WE": "minimax-E-lils-S",
    "Weil-Euclidean": "minimax-E-lils-S",
    "Kees": "destretched-octave minimax-lils-S",
    "KOP": "destretched-octave minimax-lils-S",
    "KE": "destretched-octave minimax-E-lils-S",
    "Kees-Euclidean": "destretched-octave minimax-E-lils-S",
    "CWE": "destretched-octave minimax-E-lils-S",
    "constrained Weil-Euclidean": "destretched-octave minimax-E-lils-S",
}


def tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec:
    """Build a spec from a systematic tuning-scheme name like ``"{2/1, ...} minimax-E-copfr-S"``:
    the ``mini{max,RMS,average}`` prefix gives the optimization power, an optional ``{...}``
    gives the target intervals, and the trailing ``U``/``S``/``C`` plus complexity tokens
    give the damage weighting. An optional ``held-<interval(s)>`` prefix names intervals
    to tune justly."""
    held = None
    held_match = re.match(r"\s*held-(\{[^}]*\}|[\w/]+)\s+(.*)", name)
    if held_match:
        held, name = held_match.group(1), held_match.group(2)
    destretched = None
    destretched_match = re.match(r"\s*destretched-(\S+)\s+(.*)", name)
    if destretched_match:
        destretched, name = destretched_match.group(1), destretched_match.group(2)
    power = _optimization_power_from_name(name)
    target_match = re.search(
        r"\{[\d/,\s]*\}|\d*-?TILT|\d*-?OLD|primes", name
    )
    target = target_match.group(0) if target_match else None
    if target is None and ("all-interval" in name or ("minimax" in name and "S" in name)):
        target = "{}"  # all-interval scheme (e.g. minimax-S = TOP, minimax-ES = TE)
    complexity_traits = _complexity_traits_from_name(name)
    held = complexity_traits.pop("held_intervals", None) or held  # odd/ols/lols hold the octave
    # trait 7: "nonprime-based" is checked first since it contains "prime-based" as a substring
    nonprime_approach = (
        "nonprime-based"
        if "nonprime-based" in name
        else "prime-based" if "prime-based" in name else ""
    )
    return TuningSchemeSpec(
        optimization_power=power,
        target_intervals=target,
        damage_weight_slope=_SLOPE_BY_LETTER[name.strip()[-1]],
        held_intervals=held,
        destretched_interval=destretched,
        nonprime_basis_approach=nonprime_approach,
        **complexity_traits,
    )


def resolve_tuning_scheme(spec: TuningSchemeSpec | str) -> TuningSchemeSpec:
    """A scheme given as a :class:`TuningSchemeSpec`, a systematic name, or a historical
    name (e.g. ``"TOP"``, ``"TE"``, ``"CTE"``) resolved to a :class:`TuningSchemeSpec`."""
    if isinstance(spec, str):
        return tuning_scheme_from_systematic_name(_ORIGINAL_NAME_SCHEMES.get(spec, spec))
    return spec


def _optimization_power_from_name(name: str) -> float:
    """The optimization power (trait 2) a systematic name encodes: ``minimax`` = ∞,
    ``miniRMS`` = 2, ``miniaverage`` = 1, ``mini-N-mean`` = N."""
    if "minimax" in name:
        return inf
    if "miniRMS" in name:
        return 2
    mean_match = re.search(r"mini-(\d+)-mean", name)
    if mean_match:
        return float(int(mean_match.group(1)))
    return 1


def systematic_name(spec: TuningSchemeSpec) -> str | None:
    """The canonical systematic name of a tuning scheme — the inverse of
    :func:`tuning_scheme_from_systematic_name`. ``None`` when the spec corresponds to no
    systematic name (a non-integer optimization power, or a complexity outside the named
    families), for which a chooser shows "-".

    The grammar mirrors the parser's reading order: ``[held-X ][destretched-X ][TARGET ]
    [nonprime ]mini{max,RMS,average,-N-mean}[complexity][SLOPE]``."""
    power = _power_word(spec.optimization_power)
    if power is None:
        return None
    complexity = _complexity_part(spec)
    if complexity is None:
        return None
    family, consumes_octave = complexity
    letter = _LETTER_BY_SLOPE[spec.damage_weight_slope]
    if family:  # a named complexity is dash-delimited from the mini-prefix and the slope
        tokens = (["E"] if spec.complexity_norm_power == 2 else []) + [family]
        core = f"{power}-" + "-".join(tokens) + f"-{letter}"
    else:  # log-product (the default): the Euclidean E (if any) glues straight to the slope
        core = f"{power}-" + ("E" if spec.complexity_norm_power == 2 else "") + letter
    return _scheme_prefix(spec, consumes_octave) + core


def _power_word(power: float) -> str | None:
    """The ``mini…`` token an optimization power renders to, or ``None`` if the power has no
    systematic name (a non-integer power other than ∞)."""
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
    """The complexity family token and whether it consumes the held octave (the lols/ols
    log-/integer-odd-limit forms), or ``None`` if the complexity is outside the named families.
    The empty token is the log-product default. Only norm powers 1 (taxicab) and 2 (Euclidean)
    are named."""
    if spec.complexity_norm_power not in (1, 2):
        return None
    family = _COMPLEXITY_FAMILY.get(
        (spec.complexity_log_prime_power, spec.complexity_prime_power, spec.complexity_size_factor)
    )
    if family is None:
        return None
    if family in _OCTAVE_HOLDING_FAMILY and spec.held_intervals == "octave":
        return _OCTAVE_HOLDING_FAMILY[family], True  # lils->lols / ils->ols, octave folded in
    return family, False


def _scheme_prefix(spec: TuningSchemeSpec, octave_held_by_complexity: bool) -> str:
    """The ``held-X destretched-X TARGET nonprime `` prefix in front of the ``mini…`` core, in
    the parser's reading order. A held octave the complexity already encodes (lols/ols) is not
    re-emitted as a ``held-`` token."""
    prefix = ""
    if spec.held_intervals and not octave_held_by_complexity:
        prefix += f"held-{spec.held_intervals} "
    if spec.destretched_interval:
        prefix += f"destretched-{spec.destretched_interval} "
    target = (spec.target_intervals or "").strip()
    if target and target != "{}":  # an all-interval ({}/empty) scheme carries no target prefix
        prefix += f"{target} "
    if spec.nonprime_basis_approach:
        prefix += f"{spec.nonprime_basis_approach} "
    return prefix
