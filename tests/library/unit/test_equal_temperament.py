from fractions import Fraction

import pytest

from rtt.library.equal_temperament import (
    parse_wart_name,
    patent_val,
    warted_val,
    wart_name,
)


def test_patent_val_matches_known_edos():
    assert patent_val(12, (2, 3, 5)) == (12, 19, 28)
    assert patent_val(19, (2, 3, 5)) == (19, 30, 44)
    assert patent_val(31, (2, 3, 5, 7)) == (31, 49, 72, 87)
    assert patent_val(72, (2, 3, 5, 7, 11)) == (72, 114, 167, 202, 249)


def test_patent_val_over_nonstandard_basis():
    # the val maps the ELEMENT, so the 9-coordinate is round(12·log2 9) == 38, not 2·19
    assert patent_val(12, (2, 9, 5)) == (12, 38, 28)
    assert patent_val(12, (2, 3, Fraction(13, 5))) == (12, 19, 17)


def test_patent_val_rounds_halves_up():
    # 2-EDO maps 3 at 2·log2(3) = 3.17 -> 3, and an exact .5 would round up, not to even.
    # log2(2)·N is always integer; pick an element whose step count is a clean half to lock it.
    assert patent_val(2, (2,)) == (2,)
    # round-half-up vs banker's: x.5 -> x+1 (not nearest even)
    from rtt.library import equal_temperament as et

    assert et._kth_nearest_integer(2.5, 0) == 3
    assert et._kth_nearest_integer(3.5, 0) == 4


def test_warted_val_walks_outward_in_distance_order():
    # the 5-coordinate of 17-EDO is 39.47 -> patent 39; warts c, cc, ccc, cccc move it
    # to the 2nd, 3rd, 4th, 5th nearest: 40, 38, 41, 37
    assert [warted_val(17, "c" * k, (2, 3, 5))[2] for k in range(5)] == [39, 40, 38, 41, 37]
    assert warted_val(17, "c", (2, 3, 5)) == (17, 27, 40)


def test_warted_val_empty_is_patent_and_unknown_letter_is_noop():
    assert warted_val(31, "", (2, 3, 5, 7)) == patent_val(31, (2, 3, 5, 7))
    # 'z' indexes past a 3-element basis -> ignored
    assert warted_val(12, "z", (2, 3, 5)) == patent_val(12, (2, 3, 5))


def test_warted_val_letter_targets_basis_position_not_prime():
    # over 2.9.5, letter 'b' is the element 9 (position 1), not the prime 3
    patent = patent_val(12, (2, 9, 5))
    bumped = warted_val(12, "b", (2, 9, 5))
    assert bumped[1] != patent[1]
    assert bumped[0] == patent[0] and bumped[2] == patent[2]


def test_wart_name_and_parse_round_trip():
    assert wart_name(12) == "12"
    assert wart_name(17, "c") == "17c"
    assert parse_wart_name("17c") == (17, "c")
    assert parse_wart_name("12") == (12, "")
    assert parse_wart_name(" 22B ") == (22, "b")


def test_parse_wart_name_rejects_junk():
    with pytest.raises(ValueError):
        parse_wart_name("c12")
    with pytest.raises(ValueError):
        parse_wart_name("")
