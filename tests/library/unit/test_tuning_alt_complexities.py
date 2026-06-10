"""Alternative interval-complexity names (tests.m 3388-3697): the full complexity-name
grammar (copfr/lopfr/lp/sopfr/prod/ils/ols/lils/lols/limit/odd) and the size-factor
augmentation (Weil/lils norms), driving non-all-interval and all-interval schemes."""

import pytest

from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import optimize_generator_tuning_map

TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"


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


# tests.m 3442-3448: lols = held-octave lils (the size-factor Tenney norm with octave held).
@pytest.mark.parametrize(
    "name, expected",
    [
        ("held-octave TILT miniRMS-lils-C", (1200.000, 696.075)),
        ("TILT miniRMS-lols-C", (1200.000, 696.075)),
    ],
)
def test_lols_equals_held_octave_lils(name, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, name) == pytest.approx(expected, abs=TOL)


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
