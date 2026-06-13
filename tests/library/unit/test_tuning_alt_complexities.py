"""Alternative interval-complexity names (tests.m 3388-3697): the full complexity-name
grammar (copfr/lopfr/lp/sopfr/prod/ils/ols/lils/lols/limit/odd) and the size-factor
augmentation (Weil/lils norms), driving non-all-interval and all-interval schemes."""

from dataclasses import replace
from fractions import Fraction

import pytest

from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, quotient_to_pcv
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import get_complexity, optimize_generator_tuning_map
from rtt.library.tuning_scheme_names import resolve_tuning_scheme

TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"


# all-interval-alt-complexity-4: lols-C is lils-C with the prime-2 entry dropped (rough(·,3)). It
# was wrongly computing the lils value (2/1 → 1.0 instead of 0). Values are in D&D's halved
# convention (alt-complexities O15: lols-C(10/9) = 6.340 / 2 = 3.170).
@pytest.mark.parametrize(
    "ratio, expected",
    [("2/1", 0.0), ("4/3", 1.585), ("6/5", 2.322), ("10/9", 3.170), ("3/2", 1.585)],
)
def test_lols_complexity_drops_the_prime_2_entry(ratio, expected):
    t = parse_temperament_data(MEANTONE)
    spec = resolve_tuning_scheme("minimax-lols-S")
    pcv = pad_vectors_with_zeros_up_to_d((quotient_to_pcv(Fraction(ratio)),), 3)[0]
    complexity = get_complexity(
        pcv, t, spec.complexity_norm_power, spec.complexity_log_prime_power,
        spec.complexity_prime_power, spec.complexity_size_factor, spec.nonprime_basis_approach,
        complexity_rough=spec.complexity_rough,
    )
    assert complexity == pytest.approx(expected, abs=TOL)


# all-interval-alt-complexity-15: an all-interval size-factor scheme with a NON-log prescaler must
# use that prescaler's diagonal in the phantom-prime size row (not a hard-coded log2(p)), so the
# minimax attains its own complexity's true optimum. sopfr (prime) prescaler + size factor on
# meantone: (1203.309, 698.646) (sup-damage 1.654), not the old log-row tuning (1200.860, 697.154).
def test_all_interval_size_factor_uses_the_scheme_prescaler_diagonal():
    t = parse_temperament_data(MEANTONE)
    spec = replace(resolve_tuning_scheme("minimax-sopfr-S"), complexity_size_factor=1)
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1203.309, 698.646), abs=0.05)


# The lils family (log prescaler) is the case where the old log2(p) row was already correct — it
# must be unchanged by the prescaler-diagonal generalization (the Weil meantone optimum).
def test_all_interval_lils_size_factor_unchanged():
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, "minimax-lils-S") == pytest.approx(
        (1200.000, 696.578), abs=TOL
    )


# tests.m 3392-3419: meantone over TILT, miniRMS, complexity-weighted, no size factor.
# copfr (unweighted), lopfr (Tenney, the default), sopfr (Benedetti), each plain and
# Euclidean (E), plain and odd (octave held justly).
NO_SIZE_FACTOR_NAMES = [
    ("TILT miniRMS-copfr-C", (1200.813, 696.570)),
    ("TILT miniRMS-lopfr-C", (1201.489, 696.662)),
    ("TILT miniRMS-sopfr-C", (1201.507, 696.668)),
    ("TILT miniRMS-E-copfr-C", (1200.522, 696.591)),
    ("TILT miniRMS-E-lopfr-C", (1201.535, 696.760)),
    ("TILT miniRMS-E-sopfr-C", (1201.503, 696.732)),
    ("TILT miniRMS-odd-copfr-C", (1200.000, 696.182)),
    ("TILT miniRMS-odd-lopfr-C", (1200.000, 695.972)),
    ("TILT miniRMS-odd-sopfr-C", (1200.000, 695.974)),
    ("TILT miniRMS-odd-E-copfr-C", (1200.000, 696.350)),
    ("TILT miniRMS-odd-E-lopfr-C", (1200.000, 696.089)),
    ("TILT miniRMS-odd-E-sopfr-C", (1200.000, 696.078)),
]


@pytest.mark.parametrize("name, expected", NO_SIZE_FACTOR_NAMES)
def test_no_size_factor_complexity_names(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# tests.m 3402-3429: the same TILT/miniRMS/C cases with the size factor (the "-limit-"
# token augments the norm with the interval's size). Odd variants hold the octave justly.
SIZE_FACTOR_NAMES = [
    ("TILT miniRMS-copfr-limit-C", (1201.168, 696.797)),
    ("TILT miniRMS-lopfr-limit-C", (1202.087, 696.955)),
    ("TILT miniRMS-sopfr-limit-C", (1201.830, 696.851)),
    ("TILT miniRMS-E-copfr-limit-C", (1201.024, 696.834)),
    ("TILT miniRMS-E-lopfr-limit-C", (1202.009, 696.981)),
    ("TILT miniRMS-E-sopfr-limit-C", (1201.898, 696.913)),
    ("TILT miniRMS-odd-copfr-limit-C", (1200.000, 696.209)),
    ("TILT miniRMS-odd-lopfr-limit-C", (1200.000, 696.075)),
    ("TILT miniRMS-odd-sopfr-limit-C", (1200.000, 696.093)),
    ("TILT miniRMS-odd-E-copfr-limit-C", (1200.000, 696.354)),
    ("TILT miniRMS-odd-E-lopfr-limit-C", (1200.000, 696.144)),
    ("TILT miniRMS-odd-E-sopfr-limit-C", (1200.000, 696.126)),
]


@pytest.mark.parametrize("name, expected", SIZE_FACTOR_NAMES)
def test_size_factor_complexity_names(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# lols ≡ held-octave lils only as a SCHEME (the all-interval equivalence). As a complexity
# FUNCTION, lols-C roughs out the 2's (alt-complexities O15 / MUST-GET-RIGHT 7), so in a
# complexity-WEIGHTED TARGET scheme the lols weights differ from the (un-roughed) lils weights —
# the two tunings diverge. (Was wrongly asserted equal, both 696.075, before the rough fix.)
@pytest.mark.parametrize(
    "name, expected",
    [
        ("held-octave TILT miniRMS-lils-C", (1200.000, 696.075)),  # un-roughed lils weights
        ("TILT miniRMS-lols-C", (1200.000, 696.097)),              # roughed (2-less) lols weights
    ],
)
def test_lols_target_mode_roughs_out_the_twos(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# But the all-interval SCHEME equivalence still holds exactly (rough is cleared on the over-primes
# weights there): minimax-lols-S == held-octave minimax-lils-S.
def test_lols_scheme_equals_held_octave_lils_scheme():
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, "minimax-lols-S") == pytest.approx(
        optimize_generator_tuning_map(t, "held-octave minimax-lils-S"), abs=TOL
    )


# tests.m 3631-3647: lils vs non-lils over an explicit (non-all-interval) target, across
# the four optimization powers (max / sum / sos / sop), simplicity-weighted.
@pytest.mark.parametrize(
    "name, expected",
    [
        (f"{SIX_TILT} minimax-lils-S", (1201.191, 697.405)),
        (f"{SIX_TILT} miniaverage-lils-S", (1200.000, 696.578)),
        (f"{SIX_TILT} miniRMS-lils-S", (1201.648, 697.183)),
        (f"{SIX_TILT} mini-3-mean-lils-S", (1201.621, 697.326)),
        (f"{SIX_TILT} minimax-S", (1201.699, 697.564)),
        (f"{SIX_TILT} miniaverage-S", (1200.000, 696.578)),
        (f"{SIX_TILT} miniRMS-S", (1201.617, 697.379)),
        (f"{SIX_TILT} mini-3-mean-S", (1201.603, 697.601)),
    ],
)
def test_lils_vs_non_lils_over_explicit_target(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


# tests.m 3432-3457: synonym tokens. lp = lopfr = [blank] (Tenney); prod = sopfr.
@pytest.mark.parametrize(
    "name, expected",
    [
        ("TILT miniRMS-lopfr-C", (1201.489, 696.662)),
        ("TILT miniRMS-lp-C", (1201.489, 696.662)),
        ("TILT miniRMS-C", (1201.489, 696.662)),
        ("TILT miniRMS-prod-C", (1201.507, 696.668)),
        ("TILT miniRMS-sopfr-C", (1201.507, 696.668)),
    ],
)
def test_complexity_name_synonyms(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)
