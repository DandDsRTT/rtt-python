from fractions import Fraction

import pytest

from rtt.domain_basis import get_domain_basis_dimension
from rtt.parsing import (
    is_covariant_ebk,
    parse_domain_basis,
    parse_ebk_vector,
    parse_quotient_list,
    parse_temperament_data,
)
from rtt.temperament import Temperament, Variance

MAP = "⟨1200.000 1901.955 2786.314]"
MAPPING = "[⟨1 0 -4] ⟨0 1 4]}"
COMMA = "[1 -5 3⟩"
COMMA_BASIS = "[[-4 4 -1⟩ [7 0 -3⟩]"
WITH_OUTER_BRACKETS = "[⟨1200.000 1901.955 2786.314]]"
WITH_GT_LT_SIGNS = "[<1 0 -4] <0 1 4]>"
WITH_PUNCTUATION_COMMAS = "[1, -5, 3⟩"
WITH_LOTS_OF_SPACES = " ⟨ [ -4 4 -1 ⟩ [ 7 0 -3 ⟩ ] "

MAP_T = Temperament(((1200.0, 1901.955, 2786.314),), Variance.ROW)
MAPPING_T = Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)
COMMA_T = Temperament(((1, -5, 3),), Variance.COL)
COMMA_BASIS_T = Temperament(((-4, 4, -1), (7, 0, -3)), Variance.COL)


@pytest.mark.parametrize(
    "data, expected",
    [
        (MAP, MAP_T),
        (MAPPING, MAPPING_T),
        (COMMA, COMMA_T),
        (COMMA_BASIS, COMMA_BASIS_T),
        (WITH_OUTER_BRACKETS, MAP_T),
        (WITH_GT_LT_SIGNS, MAPPING_T),
        (WITH_PUNCTUATION_COMMAS, COMMA_T),
        (WITH_LOTS_OF_SPACES, COMMA_BASIS_T),
        (MAP_T, MAP_T),  # already-structured input passes through unchanged
        (MAPPING_T, MAPPING_T),
        (COMMA_T, COMMA_T),
        (COMMA_BASIS_T, COMMA_BASIS_T),
        ("2.3.7 [6 -2 -1⟩", Temperament(((6, -2, -1),), Variance.COL, (2, 3, 7))),
    ],
)
def test_parse_temperament_data(data, expected):
    assert parse_temperament_data(data) == expected


def test_parse_domain_basis():
    assert parse_domain_basis("2.3.7") == (2, 3, 7)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1, 3, 4", (1, 3, 4)),
        ("1,3,4", (1, 3, 4)),
        ("1 3 4", (1, 3, 4)),
        ("1  3  4", (1, 3, 4)),
        ("1 ,3 ,4", (1, 3, 4)),
        ("1 , 3 , 4", (1, 3, 4)),
        ("1 ,, 3 , 4", (1, None, 3, 4)),
    ],
)
def test_parse_ebk_vector(text, expected):
    assert parse_ebk_vector(text) == expected


@pytest.mark.parametrize(
    "ebk, expected",
    [
        (MAP, True),
        (MAPPING, True),
        (COMMA, False),
        (COMMA_BASIS, False),
        (WITH_OUTER_BRACKETS, True),
        (WITH_GT_LT_SIGNS, True),
        (WITH_PUNCTUATION_COMMAS, False),
        (WITH_LOTS_OF_SPACES, False),
    ],
)
def test_is_covariant_ebk(ebk, expected):
    assert is_covariant_ebk(ebk) == expected


# parseQuotientL (tests.m 199-204): parse a quotient (string, with synonym forms) to its
# prime monzo(s), padded to the domain basis's prime dimension. The 5-limit cases use d = 3;
# the nonstandard 2.9.7.11 basis has prime dimension 5, and 11/7 maps to its prime monzo.
@pytest.mark.parametrize(
    "text, domain_basis, expected",
    [
        ("2", (2, 3, 5), ((1, 0, 0),)),
        ("2/1", (2, 3, 5), ((1, 0, 0),)),
        ("{2}", (2, 3, 5), ((1, 0, 0),)),
        ("{2/1}", (2, 3, 5), ((1, 0, 0),)),
        ("{2/1, 3/2}", (2, 3, 5), ((1, 0, 0), (-1, 1, 0))),
        ("{11/7}", (2, 9, 7, 11), ((0, 0, 0, -1, 1),)),
    ],
)
def test_parse_quotient_list(text, domain_basis, expected):
    assert parse_quotient_list(text, get_domain_basis_dimension(domain_basis)) == expected
