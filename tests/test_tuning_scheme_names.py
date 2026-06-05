"""Round-trip tests for the systematic-name parser and its inverse renderer.

The renderer (:func:`systematic_name`) must be the inverse of the parser
(:func:`tuning_scheme_from_systematic_name`): rendering a spec to a name and parsing it
back must recover the same spec, and a canonical name must render back to itself."""

from dataclasses import replace
from math import inf

import pytest

from rtt.tuning_scheme_names import (
    TuningSchemeSpec,
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


# Non-canonical / synonym / historical forms: the rendered name need not equal the input
# string, but parsing the rendered name must recover the same spec (semantic round-trip).
SEMANTIC = [
    "held-2/1 minimax-U",          # held synonym for the octave
    "held-2 miniaverage-U",
    "minimax-E-lils-S",
    "TILT minimax-S",              # target-based simplicity
    "TOP", "Tenney", "minimax",    # historical names (resolve to systematic specs)
]


@pytest.mark.parametrize("name", SEMANTIC)
def test_rendered_name_parses_back_to_the_same_spec(name):
    spec = parse(name) if name not in ("TOP", "Tenney", "minimax") else _resolve(name)
    rendered = systematic_name(spec)
    assert rendered is not None
    assert parse(rendered) == spec


def _resolve(name):
    from rtt.tuning_scheme_names import resolve_tuning_scheme
    return resolve_tuning_scheme(name)


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
