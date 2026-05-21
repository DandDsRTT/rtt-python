"""Alternative interval-complexity names (tests.m 3388-3697): the full complexity-name
grammar (copfr/lopfr/lp/sopfr/prod/ils/ols/lils/lols/limit/odd) and the size-factor
augmentation (Weil/lils norms), driving non-all-interval and all-interval schemes."""

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import optimize_generator_tuning_map

TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"


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
