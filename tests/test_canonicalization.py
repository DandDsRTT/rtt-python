import pytest

from rtt.canonicalization import canonical_ca, canonical_form, canonical_ma
from rtt.parsing import parse_temperament_data
from rtt.temperament import Temperament, Variance

# Saturated mappings: plain HNF already yields the canonical form
# (cases drawn from rtt-library/tests.m canonicalFormPrivate / canonicalMa).
SATURATED_MA = [
    (((1, 1, 0), (0, 1, 4)), ((1, 0, -4), (0, 1, 4))),
    (((12, 19, 28),), ((12, 19, 28),)),
    (((12, 0, 0), (19, 0, 0)), ((1, 0, 0),)),
    (((7, 11, 16), (22, 35, 51)), ((1, 2, 3), (0, 3, 5))),
    (((12, 19, 28), (0, 0, 0)), ((12, 19, 28),)),
    (((0, 0, 0), (0, 0, 0)), ((0, 0, 0),)),
]


# Enfactored mappings: the row lattice is not saturated, so defactoring
# (not just HNF) is required to reach the canonical form.
ENFACTORED_MA = [
    (((3, 0, -1), (0, 3, 5)), ((1, 2, 3), (0, 3, 5))),
    (((6, 5, -4), (4, -4, 1)), ((2, 1, -1), (0, 2, -1))),
    (((12, 19, 28), (26, 43, 60)), ((1, 8, 0), (0, 11, -4))),
    (((17, 16, -4), (4, -4, 1)), ((1, 0, 0), (0, 4, -1))),
]


@pytest.mark.parametrize("matrix, expected", SATURATED_MA)
def test_canonical_ma_saturated(matrix, expected):
    assert canonical_ma(matrix) == expected


@pytest.mark.parametrize("matrix, expected", ENFACTORED_MA)
def test_canonical_ma_enfactored(matrix, expected):
    assert canonical_ma(matrix) == expected


# Comma bases canonicalize via the "antitranspose sandwich" (rotate180 either side).
CANONICAL_CA = [
    (((-4, 4, -1),), ((4, -4, 1),)),
    (
        ((8, 2, 9, 8), (2, 9, -4, -8), (3, 1, -9, -2)),
        ((370, 327, 0, 0), (150, 133, 1, 0), (127, 110, 0, 2)),
    ),
]


@pytest.mark.parametrize("matrix, expected", CANONICAL_CA)
def test_canonical_ca(matrix, expected):
    assert canonical_ca(matrix) == expected


def test_canonical_form_mapping():
    t = Temperament(((5, 8, 12), (7, 11, 16)), Variance.ROW)
    assert canonical_form(t) == Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)


def test_canonical_form_comma_basis():
    t = Temperament(((-8, 8, -2),), Variance.COL)
    assert canonical_form(t) == Temperament(((4, -4, 1),), Variance.COL)


def test_canonical_form_matches_parsed_ebk():
    # someMeantoneM canonicalizes to meantoneM (rtt-library/tests.m:481)
    some = parse_temperament_data("[⟨5 8 12] ⟨7 11 16]}")
    assert canonical_form(some) == parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")
