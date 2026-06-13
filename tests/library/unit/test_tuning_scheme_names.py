"""Round-trip tests for the systematic-name parser and its inverse renderer.

The renderer (:func:`systematic_name`) must be the inverse of the parser
(:func:`tuning_scheme_from_systematic_name`): rendering a spec to a name and parsing it
back must recover the same spec, and a canonical name must render back to itself."""

from dataclasses import replace
from math import inf

import pytest

from rtt.library.tuning_scheme_names import (
    TuningSchemeSpec,
    annotation_code,
    resolve_tuning_scheme,
    systematic_name,
    tuning_scheme_from_systematic_name as parse,
)

# Canonical names — the exact strings the renderer is expected to emit. Each must satisfy
# render(parse(name)) == name (the rounded-trip is the identity on canonical forms).
CANONICAL = [
    "minimax-S", "minimax-U", "minimax-C",
    "miniRMS-U", "miniaverage-S",
    "minimax-ES", "minimax-EU", "minimax-EC",
    "minimax-copfr-S", "minimax-E-copfr-S",
    "minimax-sopfr-S", "minimax-E-sopfr-S",
    "minimax-lils-S", "minimax-E-lils-S",
    "minimax-lols-S", "minimax-E-lols-S",
    "mini-3-mean-S",
    "held-octave minimax-ES",
    "destretched-octave minimax-ES",
    "TILT minimax-U", "9-OLD minimax-S", "6-TILT minimax-C",
    "held-octave TILT minimax-ES",
    "{2/1, 3/2} minimax-U",
]


@pytest.mark.parametrize("name", CANONICAL)
def test_canonical_name_renders_back_to_itself(name):
    assert systematic_name(parse(name)) == name


# annotation_code(spec, letter) is the complexity+slope token the guide parenthesizes as an
# annotated unit (ch.10) — the systematic name's core after the mini-power word, with the slope
# position set to `letter`. The log-product default glues E to the slope (ES); a named family
# dash-delimits it (E-sopfr-S). The complexity quantity reuses the same family with letter "C".
ANNOTATION_CASES = [
    ("minimax-S", "S", "S"), ("minimax-ES", "S", "ES"),
    ("minimax-C", "C", "C"), ("minimax-EC", "C", "EC"),
    ("minimax-sopfr-S", "S", "sopfr-S"), ("minimax-E-sopfr-S", "S", "E-sopfr-S"),
    ("minimax-sopfr-S", "C", "sopfr-C"), ("minimax-E-sopfr-S", "C", "E-sopfr-C"),
    ("minimax-copfr-C", "C", "copfr-C"), ("minimax-E-copfr-S", "S", "E-copfr-S"),
    ("minimax-lils-S", "S", "lils-S"), ("minimax-lils-S", "C", "lils-C"),
    ("minimax-lols-S", "S", "lols-S"), ("minimax-E-lils-S", "C", "E-lils-C"),
]


@pytest.mark.parametrize("name, letter, expected", ANNOTATION_CASES)
def test_annotation_code_is_the_systematic_core_for_a_slope_position(name, letter, expected):
    assert annotation_code(parse(name), letter) == expected


@pytest.mark.parametrize("name", [n for n in CANONICAL if n.startswith("minimax-")])
def test_annotation_code_matches_the_systematic_names_own_core(name):
    # for a scheme's OWN slope, the token is exactly the systematic name minus the "minimax-"
    # prefix — so the annotation and the scheme name stay in lockstep.
    from rtt.library.tuning_scheme_names import _LETTER_BY_SLOPE
    spec = parse(name)
    own = annotation_code(spec, _LETTER_BY_SLOPE[spec.damage_weight_slope])
    assert name == f"minimax-{own}"


# Non-canonical / synonym forms: the rendered name need not equal the input string, but parsing
# the rendered name must recover the same spec (semantic round-trip).
SEMANTIC = [
    "held-2/1 minimax-U",          # held synonym for the octave
    "held-2 miniaverage-U",
    "minimax-E-lils-S",
    "TILT minimax-S",              # target-based simplicity
]


@pytest.mark.parametrize("name", SEMANTIC)
def test_rendered_name_parses_back_to_the_same_spec(name):
    spec = parse(name)
    rendered = systematic_name(spec)
    assert rendered is not None
    assert parse(rendered) == spec


# Only systematic names resolve. Non-systematic / historical / community scheme names (TE, TOP,
# CTE, POTE, BOP, Weil, Kees, "least squares", Tenney, …) are banned in this codebase and must
# raise a clear error rather than silently resolving to some spec.
@pytest.mark.parametrize(
    "name",
    ["TOP", "TIPTOP", "TE", "CTE", "POTE", "POTOP", "BOP", "Benedetti", "Weil", "Kees",
     "Frobenius", "Tenney", "least squares", "minimax"],
)
def test_non_systematic_scheme_names_are_rejected(name):
    with pytest.raises(ValueError):
        resolve_tuning_scheme(name)


def test_every_spec_field_survives_a_render_parse_round_trip():
    spec = TuningSchemeSpec(
        optimization_power=2,
        target_intervals="9-OLD",
        damage_weight_slope="complexityWeight",
        complexity_norm_power=2,
        complexity_log_prime_power=0,
        complexity_prime_power=1,
        complexity_size_factor=0,
        held_intervals="octave",
        destretched_interval=None,
    )
    rendered = systematic_name(spec)
    assert parse(rendered) == spec


@pytest.mark.parametrize(
    "spec",
    [
        # a non-integer optimization power has no systematic name
        TuningSchemeSpec(optimization_power=1.5, target_intervals="{}", damage_weight_slope="simplicityWeight"),
        # a complexity norm power other than 1 or 2 is unnamed
        TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight",
                         complexity_norm_power=3),
        # a prescaler that is neither pure log-prime, pure prime, nor pure count is unnamed
        TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight",
                         complexity_log_prime_power=1, complexity_prime_power=1),
    ],
)
def test_systematic_name_is_none_for_an_unnameable_spec(spec):
    assert systematic_name(spec) is None


# all-interval-alt-complexity-16: the complexity norm power must read the maxized ``M`` (q = ∞)
# and explicit numeric tokens — not silently default to q = 1, resolving a different scheme's spec.
@pytest.mark.parametrize(
    "name, expected_norm_power",
    [
        ("minimax-MS", inf),       # maxized: q = ∞ (a real scheme; was silently read as minimax-S)
        ("minimax-1.5-S", 1.5),    # explicit numeric norm power
        ("minimax-3S", 3),         # explicit numeric norm power, glued
        ("minimax-S", 1),          # plain taxicab default — unchanged
        ("minimax-ES", 2),         # Euclidean — unchanged
        ("9-OLD minimax-S", 1),    # the target-limit 9 is NOT mistaken for a norm power
        ("mini-3-mean-S", 1),      # the optimization-power 3 is NOT mistaken for a norm power
    ],
)
def test_norm_power_token_parsing(name, expected_norm_power):
    assert parse(name).complexity_norm_power == expected_norm_power
