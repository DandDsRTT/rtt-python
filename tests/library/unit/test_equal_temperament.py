from fractions import Fraction

import pytest

from rtt.library.equal_temperament import (
    parse_wart_name,
    patent_val,
    uniform_maps,
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


def test_uniform_maps_enumerates_an_edos_warted_maps():
    # 17edo in the 5-limit has six uniform maps — the patent (17 27 39) and its warted neighbours,
    # in ascending-multiplier order. Both wiki examples ⟨17 27 39] and ⟨17 27 40] are among them.
    maps = [(n, w, v) for n, w, v in uniform_maps((2, 3, 5), 72) if n == 17]
    assert [v for _n, _w, v in maps] == [
        (17, 26, 38), (17, 26, 39), (17, 27, 39), (17, 27, 40), (17, 28, 40), (17, 28, 41),
    ]
    assert [warts for _n, warts, _v in maps] == ["bcc", "b", "", "c", "bbc", "bbccc"]
    # the patent val is the one with empty warts
    assert (17, "", (17, 27, 39)) in maps


def test_uniform_maps_every_edo_offers_its_patent_val_and_round_trips():
    for basis in ((2, 3, 5), (2, 3, 5, 7), (2, 9, 5)):
        maps = uniform_maps(basis, 72)
        # every map reduces to a wart name that reproduces it exactly...
        for n, warts, val in maps:
            assert warted_val(n, warts, basis) == val
        # ...the names are unique, every EDO 1..72 appears, and each offers its integer uniform map
        names = {wart_name(n, w) for n, w, _v in maps}
        assert len(names) == len(maps)
        assert {n for n, _w, _v in maps} == set(range(1, 73))
        for n in range(1, 73):
            assert (n, "", patent_val(n, basis)) in maps


def test_uniform_maps_terminates_on_a_subunison_basis_element():
    # A domain-basis element below 1/1 (a descending interval, e.g. a directly-entered 7/11) has a
    # negative log size; the sweep must select by magnitude so it still terminates, while the emitted
    # map entries carry the descending element's sign — matching the patent val and round-tripping.
    basis = (2, Fraction(7, 11), 5)
    maps = uniform_maps(basis, 24)
    assert {n for n, _w, _v in maps} == set(range(1, 25))
    for n, warts, val in maps:
        assert warted_val(n, warts, basis) == val
    for n in range(1, 25):
        patent = patent_val(n, basis)
        assert patent[1] <= 0  # the sub-unison element maps to non-ascending steps
        assert (n, "", patent) in maps


def test_uniform_maps_count_grows_with_the_prime_limit():
    # more primes -> more places to wart -> more uniform maps per EDO
    assert (len(uniform_maps((2, 3, 5), 72))
            < len(uniform_maps((2, 3, 5, 7), 72))
            < len(uniform_maps((2, 3, 5, 7, 11), 72)))
