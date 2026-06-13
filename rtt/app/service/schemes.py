"""Tuning-scheme trait helpers: read or swap one trait of a scheme spec at a time.

The PRESCALERS / WEIGHT_SLOPES / COMPLEXITY_NAMES tables the controls offer, the
scheme_with_* / *_of trait swappers and readers, the scheme JSON round-trip, and the
displayed-targets / displayed-prescaler-name resolution the grid and plain text share."""

from __future__ import annotations

from dataclasses import asdict, replace

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

from rtt.app.service.core import (
    DEFAULT_TARGET_SPEC,
    DEFAULT_TUNING_SCHEME,
    _is_matrix,
    _to_matrix,
    _vectors_to_ratios,
    element_ratio,
    prescale_text,
    target_interval_set,
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
    prescaler and box 𝒄 norm. lols/lols-E hold the octave just (log-odd-limit), so they set the
    held octave. Keeps the optimization power and damage slope. Returns a resolved spec.

    A SCHEME-level held interval (the defining held octave of ``held-octave minimax-ES``, or any
    held-X trait) survives a complexity swap — just as the destretched-octave modifier already
    does — so e.g. held-octave minimax-ES + sopfr → held-octave minimax-sopfr-S, octave still
    held. The held octave is only cleared when it was the OLD complexity's own internal fold
    (lols/ols, marked by their odd-limit rough); swapping away from such a complexity legitimately
    drops it."""
    spec = resolve_tuning_scheme(scheme)
    traits, held = complexity_name_traits(COMPLEXITY_NAMES[name])  # only lols/ols hold an interval
    if held is None:
        held = None if spec.complexity_rough else spec.held_intervals
    return replace(spec, held_intervals=held, **traits)


def _complexity_signature(spec) -> tuple:
    """The traits that distinguish the predefined complexities: norm power, prescaler powers,
    size factor, and the odd-limit rough (lols/ols vs lils/ils — the complexity's OWN held-octave
    fold). Two schemes share a complexity name iff they share this signature. The rough — a
    complexity trait — distinguishes lols from lils without folding in a scheme-level held octave:
    a held octave that is a SCHEME modifier (held-octave minimax-ES) must not change the complexity
    identity, or no named complexity would match and the chooser would read 'custom'."""
    return (
        spec.complexity_norm_power, spec.complexity_log_prime_power,
        spec.complexity_prime_power, spec.complexity_size_factor,
        bool(spec.complexity_rough),
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
    mapping, scheme: str = DEFAULT_TUNING_SCHEME, override=None, domain_basis=None,
    nonprime_approach: str = "",
) -> tuple[float, ...]:
    """The diagonal of the complexity prescaler L — each domain basis element's pre-norm weight
    (log2(element) for the default log-prime norm). The L matrix is diag of this.

    ``override`` lets the bare prescaler tile's editable cells short-circuit the scheme's
    computed diagonal: a d-tuple typed in there REPLACES the log-prime/prime/identity
    diagonal everywhere it flows — the matrix display, the 𝐿·basis products, complexity,
    weights, and the tuning solve. ``None`` (the default) keeps today's behavior. The override
    is a d-tuple diagonal, or — once alt-complexity makes the whole square editable — a full d×d
    matrix (a non-diagonal pretransformer); a matrix is returned as rows of floats, a diagonal flat.

    ``domain_basis`` (the d basis elements) and ``nonprime_approach`` (trait 7) make the diagonal
    reflect the ACTUAL domain rather than the first d standard primes: over a prime subgroup or a
    nonprime-based domain the element complexities differ (log₂7 over 2.3.7, not log₂5; log₂(13/5)
    under nonprime-based), and the diagonal must agree with the complexity row computed from the
    same scheme — and seed the right weights when a prescaler cell is edited. (nonstandard-superspace-6.)"""
    if override is not None:
        if _is_matrix(override):
            return tuple(tuple(float(x) for x in row) for row in override)
        return tuple(float(x) for x in override)
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    return tuple(
        get_complexity_prescaler(
            t, spec.complexity_log_prime_power, spec.complexity_prime_power,
            nonprime_approach or spec.nonprime_basis_approach,
        )
    )


def displayed_prescaler_name(mapping, scheme=DEFAULT_TUNING_SCHEME, custom_prescaler=None,
                             domain_basis=None, nonprime_approach: str = "") -> str | None:
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
        computed = complexity_prescaler(mapping, scheme, domain_basis=domain_basis,
                                        nonprime_approach=nonprime_approach)
        shown = tuple(float(x) for x in custom_prescaler)
        if len(shown) != len(computed) or any(
                prescale_text(a) != prescale_text(b) for a, b in zip(shown, computed)):
            return None
    return prescaler_of(scheme)
