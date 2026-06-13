from fractions import Fraction

import pytest

from rtt.library.domain_basis import get_domain_basis_dimension
from rtt.library.parsing import (
    is_covariant_ebk,
    parse_domain_basis,
    parse_ebk_vector,
    parse_quotient_list,
    parse_temperament_data,
)
from rtt.library.temperament import Temperament, Variance

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


# ebk-notation-5: a grade-≥2 multivector (wedgie) repeats its variance bracket — it is not a
# map/vector, so it must be rejected, never silently parsed as the inner single bracket.
@pytest.mark.parametrize(
    "data",
    [
        "⟨⟨1 4 4]]",  # meantone's covariant bivector
        "[[1 4 4⟩⟩",  # the contravariant multicomma
        "⟨⟨ 1 4 4 ]]",  # whitespace inside the repeated brackets
        "⟨⟨⟨1 0 0]]]",  # a trivector
    ],
)
def test_multivector_rejected(data):
    with pytest.raises(ValueError):
        parse_temperament_data(data)


# ebk-notation-6: a string mixing bras and kets at one nesting level is not valid EBK (a matrix
# is a ket of bras OR a bra of kets, never both), and arbitrary junk around the vectors is junk.
@pytest.mark.parametrize(
    "data",
    [
        "[⟨1 0 -4] [0 1 4⟩]",  # a bra and a ket at one level — don't drop the bra
        "junk [-4 4 -1⟩ junk",  # stray words around a vector
        "[-4 4 -1⟩ 5",  # a stray number outside the vectors
    ],
)
def test_mixed_variance_and_junk_rejected(data):
    with pytest.raises(ValueError):
        parse_temperament_data(data)


# ebk-notation-14: the Secor zero-run elision ', ,' stands for a dropped group of three zeros, so
# it must round-trip to the full vector; a bare ',,' (no space) is still a single blank (None).
def test_secor_zero_run_elision_expands_to_three_zeros():
    assert parse_temperament_data("[-3 0, , 1⟩").matrix == ((-3, 0, 0, 0, 0, 1),)
    # equal to the un-elided separated form
    assert parse_temperament_data("[-3 0, , 1⟩") == parse_temperament_data("[-3 0, 0 0 0, 1⟩")
    # a bare ',,' is unchanged: still a single blank entry
    assert parse_ebk_vector("1 ,, 3 , 4") == (1, None, 3, 4)


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
# prime vector(s), padded to the domain basis's prime dimension. The 5-limit cases use d = 3;
# the nonstandard 2.9.7.11 basis has prime dimension 5, and 11/7 maps to its prime vector.
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
