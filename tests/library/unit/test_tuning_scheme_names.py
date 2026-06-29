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


ANNOTATION_CASES = [
    ("minimax-S", "S", "S"), ("minimax-ES", "S", "ES"),
    ("minimax-C", "C", "C"), ("minimax-EC", "C", "EC"),
    ("minimax-sopfr-S", "S", "sopfr-S"), ("minimax-E-sopfr-S", "S", "E-sopfr-S"),
    ("minimax-sopfr-S", "C", "sopfr-C"), ("minimax-E-sopfr-S", "C", "E-sopfr-C"),
    ("minimax-copfr-C", "C", "copfr-C"), ("minimax-E-copfr-S", "S", "E-copfr-S"),
    ("minimax-lils-S", "S", "lils-S"), ("minimax-lils-S", "C", "lils-C"),
    ("minimax-lols-S", "S", "lols-S"), ("minimax-E-lils-S", "C", "E-lils-C"),
]


SEMANTIC = [
    "held-2/1 minimax-U",
    "held-2 miniaverage-U",
    "minimax-E-lils-S",
    "TILT minimax-S",
]


class TestTuningSchemeNames:
    @pytest.mark.parametrize("name", CANONICAL)
    def test_canonical_name_renders_back_to_itself(self, name):
        assert systematic_name(parse(name)) == name

    @pytest.mark.parametrize("name, letter, expected", ANNOTATION_CASES)
    def test_annotation_code_is_the_systematic_core_for_a_slope_position(self, name, letter, expected):
        assert annotation_code(parse(name), letter) == expected

    @pytest.mark.parametrize("name", [n for n in CANONICAL if n.startswith("minimax-")])
    def test_annotation_code_matches_the_systematic_names_own_core(self, name):
        from rtt.library.tuning_scheme_names import _LETTER_BY_SLOPE
        spec = parse(name)
        own = annotation_code(spec, _LETTER_BY_SLOPE[spec.damage_weight_slope])
        assert name == f"minimax-{own}"

    @pytest.mark.parametrize("name", SEMANTIC)
    def test_rendered_name_parses_back_to_the_same_spec(self, name):
        spec = parse(name)
        rendered = systematic_name(spec)
        assert rendered is not None
        assert parse(rendered) == spec

    @pytest.mark.parametrize(
        "name",
        ["TOP", "TIPTOP", "TE", "CTE", "POTE", "POTOP", "BOP", "Benedetti", "Weil", "Kees",
         "Frobenius", "Tenney", "least squares", "minimax"],
    )
    def test_non_systematic_scheme_names_are_rejected(self, name):
        with pytest.raises(ValueError):
            resolve_tuning_scheme(name)

    def test_every_spec_field_survives_a_render_parse_round_trip(self):
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
            nonprime_basis_approach="prime-based",
        )
        rendered = systematic_name(spec)
        assert "prime-based " in rendered
        assert parse(rendered) == spec

    @pytest.mark.parametrize(
        "spec",
        [
            TuningSchemeSpec(optimization_power=1.5, target_intervals="{}", damage_weight_slope="simplicityWeight"),
            TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight",
                             complexity_norm_power=3),
            TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight",
                             complexity_log_prime_power=1, complexity_prime_power=1),
        ],
    )
    def test_systematic_name_is_none_for_an_unnameable_spec(self, spec):
        assert systematic_name(spec) is None

    @pytest.mark.parametrize(
        "name, expected_norm_power",
        [
            ("minimax-MS", inf),
            ("minimax-1.5-S", 1.5),
            ("minimax-3S", 3),
            ("minimax-S", 1),
            ("minimax-ES", 2),
            ("9-OLD minimax-S", 1),
            ("mini-3-mean-S", 1),
        ],
    )
    def test_norm_power_token_parsing(self, name, expected_norm_power):
        assert parse(name).complexity_norm_power == expected_norm_power
