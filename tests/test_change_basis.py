from fractions import Fraction as F

import pytest

from rtt.change_basis import change_domain_basis
from rtt.formatting import to_ebk
from rtt.parsing import parse_domain_basis, parse_temperament_data
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

VALID = [
    # mapping restricted to a subspace
    (
        Temperament(((22, 35, 51, 76),), ROW, (2, 3, 5, 11)),
        (2, 9, 11),
        Temperament(((11, 35, 38),), ROW, (2, 9, 11)),
    ),
    (
        Temperament(((1, 0, -4), (0, 1, 4)), ROW),
        (2, 3, 5),
        Temperament(((1, 0, -4), (0, 1, 4)), ROW),
    ),
    # comma basis embedded into a superspace
    (
        Temperament(((0, 1, 0), (0, -2, 1)), COL, (2, F(9, 7), F(5, 3))),
        (2, 3, 5, 7),
        Temperament(((0, -1, 1, 0), (0, -2, 0, 1)), COL),
    ),
    (Temperament(((1,),), COL, (81,)), (9,), Temperament(((1,),), COL, (9,))),
    (Temperament(((4, -4, 1),), COL), (2, 3, 5), Temperament(((4, -4, 1),), COL)),
]

ERRORS = [
    (Temperament(((12, 19, 28),), ROW), (2, 3, 5, 7)),  # can't expand a mapping
    (Temperament(((4, -4, 1),), COL), (2, 9, 7)),  # not a superspace
    (Temperament(((1,),), COL, (27,)), (9,)),  # 27 not a subgroup of 9
]


@pytest.mark.parametrize("temperament, target, expected", VALID)
def test_change_domain_basis(temperament, target, expected):
    assert change_domain_basis(temperament, target) == expected


@pytest.mark.parametrize("temperament, target", ERRORS)
def test_change_domain_basis_errors(temperament, target):
    with pytest.raises(ValueError):
        change_domain_basis(temperament, target)


@pytest.mark.parametrize(
    "ebk, target, expected",
    [
        ("[4 -4 1⟩", "2.3.5.7", "[4 -4 1 0⟩"),
        ("[⟨1 0 -4] ⟨0 1 4]}", "2.3", "[⟨1 0] ⟨0 1]⟩"),
    ],
)
def test_change_domain_basis_through_ebk(ebk, target, expected):
    result = change_domain_basis(
        parse_temperament_data(ebk), parse_domain_basis(target)
    )
    assert to_ebk(result) == expected
