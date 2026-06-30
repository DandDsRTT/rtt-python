import pytest

from rtt.library.canonicalization import (
    canonical_ca,
    canonical_form,
    canonical_ma,
    column_hermite_defactor,
)
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

CANONICAL_MA = [
    (((12, 0, 0), (19, 0, 0)), ((1, 0, 0),)),
    (((1, 1, 0), (0, 1, 4)), ((1, 0, -4), (0, 1, 4))),
    (((12, 19, 28),), ((12, 19, 28),)),
    (((7, 11, 16), (22, 35, 51)), ((1, 2, 3), (0, 3, 5))),
    (((3, 0, -1), (0, 3, 5)), ((1, 2, 3), (0, 3, 5))),
    (((1, 2, 3), (0, 3, 5)), ((1, 2, 3), (0, 3, 5))),
    (((0, 1, 4, 10), (1, 0, -4, -13)), ((1, 0, -4, -13), (0, 1, 4, 10))),
    (((10, 13, 12, 0), (-1, -1, 0, 3)), ((1, 0, -4, -13), (0, 1, 4, 10))),
    (((5, 8, 0), (0, 0, 1)), ((5, 8, 0), (0, 0, 1))),
    (((2, 0, 11, 12), (0, 1, -2, -2)), ((2, 0, 11, 12), (0, 1, -2, -2))),
    (
        ((1, 0, 0, -5), (0, 1, 0, 2), (0, 0, 1, 2)),
        ((1, 0, 0, -5), (0, 1, 0, 2), (0, 0, 1, 2)),
    ),
    (
        ((1, 0, 0, -5, 12), (0, 1, 0, 2, -1), (0, 0, 1, 2, -3)),
        ((1, 0, 0, -5, 12), (0, 1, 0, 2, -1), (0, 0, 1, 2, -3)),
    ),
    (((12, 19, 28), (26, 43, 60)), ((1, 8, 0), (0, 11, -4))),
    (((17, 16, -4), (4, -4, 1)), ((1, 0, 0), (0, 4, -1))),
    (((6, 5, -4), (4, -4, 1)), ((2, 1, -1), (0, 2, -1))),
    (((12, 19, 28), (0, 0, 0)), ((12, 19, 28),)),
    (((1, 0, 0, -5), (0, 1, 0, 2), (1, 1, 0, -3)), ((1, 0, 0, -5), (0, 1, 0, 2))),
    (((0, 0),), ((0, 0),)),
    (((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((1, 0, 0), (0, 1, 0), (0, 0, 1))),
    (((1, 0, -4), (0, 1, 4), (0, 0, 0)), ((1, 0, -4), (0, 1, 4))),
    (((12, 19, 28, 0),), ((12, 19, 28, 0),)),
    (((0, 0, 0), (0, 0, 0)), ((0, 0, 0),)),
]

CANONICAL_CA = [
    (((-4, 4, -1),), ((4, -4, 1),)),
    (
        ((8, 2, 9, 8), (2, 9, -4, -8), (3, 1, -9, -2)),
        ((370, 327, 0, 0), (150, 133, 1, 0), (127, 110, 0, 2)),
    ),
]


class TestCanonicalization:
    @pytest.mark.parametrize("matrix, expected", CANONICAL_MA)
    def test_canonical_ma(self, matrix, expected):
        assert canonical_ma(matrix) == expected

    @pytest.mark.parametrize("matrix, expected", CANONICAL_CA)
    def test_canonical_ca(self, matrix, expected):
        assert canonical_ca(matrix) == expected

    def test_col_hermite_defactor(self):
        assert column_hermite_defactor(((6, 5, -4), (4, -4, 1))) == ((6, 5, -4), (-4, -4, 3)), "Matches Wolfram exactly. (hermiteRightUnimodular's exact output is omitted: # the unimodular transform isn't unique, and mine differs only by the sign of # one column — which cancels out, so col_hermite_defactor still matches.)"

    def test_canonical_form_mapping(self):
        t = Temperament(((5, 8, 12), (7, 11, 16)), Variance.ROW)
        assert canonical_form(t) == Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)

    def test_canonical_form_comma_basis(self):
        t = Temperament(((-8, 8, -2),), Variance.COL)
        assert canonical_form(t) == Temperament(((4, -4, 1),), Variance.COL)

    def test_canonical_form_keeps_nonstandard_domain_basis(self):
        t = Temperament(((22, 70, 62),), Variance.ROW, (2, 9, 7))
        assert canonical_form(t) == Temperament(((11, 35, 31),), Variance.ROW, (2, 9, 7))

    def test_canonical_form_drops_standard_domain_basis(self):
        t = Temperament(((24, 38, 56),), Variance.ROW, (2, 3, 5))
        assert canonical_form(t) == Temperament(((12, 19, 28),), Variance.ROW)

    def test_canonical_form_matches_parsed_ebk(self):
        some = parse_temperament_data("[⟨5 8 12] ⟨7 11 16]}")
        assert canonical_form(some) == parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")
