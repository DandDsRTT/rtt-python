"""Prime-based nonstandard-domain (trait 7) tuning (tests.m 3716-3874): re-express the
temperament over its simplest prime-only basis, optimize there, then map the generators
back to the original (nonprime) basis. For co-prime subgroups this agrees with the
nonprime-based approach; for non-co-prime ones (and the explicit barbados target set) it
genuinely differs."""

from math import inf

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import TuningSchemeSpec, optimize_generator_tuning_map

TOL = 1e-2

BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"
MACHINE = "2.9.7.11 [⟨1 3 3 4] ⟨0 1 -1 -3]}"
STARLINGTET = "2.5/3.7/3 [⟨1 1 2] ⟨0 -1 -3]}"


def test_barbados_prime_based_explicit_targets():
    # tests.m 3716-3726: targets given as vectors in 2.3.5.13; equivalently the quotients
    # {2, 5/4, 3/4, 3/5, 13/4, 13/5, 13/8, 13/3}.
    t = parse_temperament_data(BARBADOS)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals="{2/1, 5/4, 3/4, 3/5, 13/4, 13/5, 13/8, 13/3}",
        damage_weight_slope="complexityWeight",
        nonprime_basis_approach="prime-based",
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1200.370, 248.863), abs=TOL)


# Co-prime subgroups: prime-based agrees with nonprime-based (tests.m 3787-3802).
@pytest.mark.parametrize(
    "ebk, name, expected",
    [
        (MACHINE, "{2/1, 9/4, 11/7} prime-based minimax-C", (1197.268, 207.170)),
        (BARBADOS, "{3/2, 13/10, 15/13} prime-based minimax-C", (1197.437, 247.741)),
        (STARLINGTET, "{7/5, 7/6, 6/5} prime-based minimax-C", (1213.795, 315.641)),
    ],
)
def test_prime_based_target_set_names(ebk, name, expected):
    t = parse_temperament_data(ebk)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# All-interval prime-based schemes (tests.m 3817-3874).
def test_all_interval_prime_based_explicit_specs():
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals="{}",
        damage_weight_slope="simplicityWeight",
        complexity_norm_power=2,
        nonprime_basis_approach="prime-based",
    )
    t1 = parse_temperament_data("2.7/5.11 [⟨1 1 5] ⟨0 -1 -3]}")
    assert optimize_generator_tuning_map(t1, spec) == pytest.approx((1200.0558, 616.4318), abs=TOL)
    t2 = parse_temperament_data("2.9.5.21 [⟨1 0 -4 0] ⟨0 1 2 0] ⟨0 0 0 1]}")
    assert optimize_generator_tuning_map(t2, spec) == pytest.approx(
        (1201.3969, 3796.8919, 5267.2719), abs=TOL
    )


@pytest.mark.parametrize(
    "name, expected",
    [
        # co-prime: agree with nonprime-based
        ("prime-based minimax-ES", (1197.281, 213.899)),
        ("prime-based minimax-S", (1197.344, 215.749)),
        # E-copfr / E-sopfr complexities make prime-based differ from nonprime-based
        ("prime-based minimax-E-copfr-S", (1195.547, 211.194)),
        ("prime-based minimax-E-sopfr-S", (1197.440, 214.315)),
    ],
)
def test_machine_all_interval_prime_based(name, expected):
    t = parse_temperament_data(MACHINE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)
