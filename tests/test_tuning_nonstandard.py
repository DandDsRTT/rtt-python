"""Nonstandard-domain (trait 7) tuning schemes (tests.m 3698-3874): temperaments over
subgroups like 2.3.13/5, with the "nonprime-based" approach (treat each basis element as
a prime) or the neutral default. Targets are filtered to the subgroup and expressed as
vectors in the (nonprime) basis. Prime-based cases live in test_tuning_nonstandard_prime.py."""

from math import inf

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import TuningSchemeSpec, optimize_generator_tuning_map

TOL = 1e-2  # the library states these to 3-4 decimals; a couple of references are coarser

BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"
ARTICLE_EXAMPLE = "2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]"
MACHINE = "2.9.7.11 [⟨1 3 3 4] ⟨0 1 -1 -3]}"
STARLINGTET = "2.5/3.7/3 [⟨1 1 2] ⟨0 -1 -3]}"


def test_barbados_nonprime_explicit_targets():
    # tests.m 3703-3713: targets given as vectors in 2.3.13/5; equivalently the quotients
    # {2, 3, 13/5, 3/2, 13/10, 15/13}.
    t = parse_temperament_data(BARBADOS)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals="{2/1, 3/1, 13/5, 3/2, 13/10, 15/13}",
        damage_weight_slope="complexityWeight",
        nonprime_basis_approach="nonprime-based",
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1198.919, 248.212), abs=TOL)


@pytest.mark.parametrize(
    "nonprime_basis_approach, expected",
    [("", (1194.291, 135.186)), ("nonprime-based", (1192.399, 133.768))],
)
def test_article_example_tilt(nonprime_basis_approach, expected):
    # tests.m 3733-3762: a 2.7/3.11/3 example over the default TILT, neutral vs nonprime-based.
    t = parse_temperament_data(ARTICLE_EXAMPLE)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals="TILT",
        damage_weight_slope="complexityWeight",
        nonprime_basis_approach=nonprime_basis_approach,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Co-prime subgroups: prime-based and nonprime-based agree, so only the nonprime-based name
# is exercised here (the prime-based twins live in the prime-based test module). tests.m 3787-3802.
@pytest.mark.parametrize(
    "ebk, name, expected",
    [
        (MACHINE, "{2/1, 9/4, 11/7} nonprime-based minimax-C", (1197.268, 207.170)),
        (BARBADOS, "{3/2, 13/10, 15/13} nonprime-based minimax-C", (1197.437, 247.741)),
        (STARLINGTET, "{7/5, 7/6, 6/5} nonprime-based minimax-C", (1213.795, 315.641)),
    ],
)
def test_nonprime_based_target_set_names(ebk, name, expected):
    t = parse_temperament_data(ebk)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# All-interval nonprime-based schemes (tests.m 3817-3874).
def test_all_interval_nonprime_based_explicit_specs():
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals="{}",
        damage_weight_slope="simplicityWeight",
        complexity_norm_power=2,
        nonprime_basis_approach="nonprime-based",
    )
    t1 = parse_temperament_data("2.7/5.11 [⟨1 1 5] ⟨0 -1 -3]}")
    assert optimize_generator_tuning_map(t1, spec) == pytest.approx((1200.4181, 617.7581), abs=TOL)
    t2 = parse_temperament_data("2.9.5.21 [⟨1 0 -4 0] ⟨0 1 2 0] ⟨0 0 0 1]}")
    assert optimize_generator_tuning_map(t2, spec) == pytest.approx(
        (1201.3969, 3796.8919, 5270.7809), abs=TOL
    )


@pytest.mark.parametrize(
    "name, expected",
    [
        ("nonprime-based minimax-ES", (1197.281, 213.899)),
        ("nonprime-based minimax-S", (1197.344, 215.749)),
        ("nonprime-based minimax-E-copfr-S", (1196.398, 212.537)),
        ("nonprime-based minimax-E-sopfr-S", (1197.766, 215.083)),
    ],
)
def test_machine_all_interval_nonprime_based(name, expected):
    t = parse_temperament_data(MACHINE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)
