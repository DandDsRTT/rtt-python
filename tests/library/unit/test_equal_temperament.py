from fractions import Fraction

import pytest

from rtt.library.equal_temperament import (
    parse_wart_name,
    patent_val,
    uniform_maps,
    warted_val,
    wart_name,
)


class TestEqualTemperament:
    def test_patent_val_matches_known_edos(self):
        assert patent_val(12, (2, 3, 5)) == (12, 19, 28)
        assert patent_val(19, (2, 3, 5)) == (19, 30, 44)
        assert patent_val(31, (2, 3, 5, 7)) == (31, 49, 72, 87)
        assert patent_val(72, (2, 3, 5, 7, 11)) == (72, 114, 167, 202, 249)

    def test_patent_val_over_nonstandard_basis(self):
        assert patent_val(12, (2, 9, 5)) == (12, 38, 28), "the val maps the ELEMENT, so the 9-coordinate is round(12·log2 9) == 38, not 2·19"
        assert patent_val(12, (2, 3, Fraction(13, 5))) == (12, 19, 17)

    def test_patent_val_rounds_halves_up(self):
        assert patent_val(2, (2,)) == (2,), "2-EDO maps 3 at 2·log2(3) = 3.17 -> 3, and an exact .5 would round up, not to even. # log2(2)·N is always integer; pick an element whose step count is a clean half to lock it"
        from rtt.library import equal_temperament as et

        assert et._kth_nearest_integer(2.5, 0) == 3
        assert et._kth_nearest_integer(3.5, 0) == 4

    def test_warted_val_walks_outward_in_distance_order(self):
        assert [warted_val(17, "c" * k, (2, 3, 5))[2] for k in range(5)] == [39, 40, 38, 41, 37]
        assert warted_val(17, "c", (2, 3, 5)) == (17, 27, 40)

    def test_warted_val_empty_is_patent_and_unknown_letter_is_noop(self):
        assert warted_val(31, "", (2, 3, 5, 7)) == patent_val(31, (2, 3, 5, 7))
        assert warted_val(12, "z", (2, 3, 5)) == patent_val(12, (2, 3, 5))

    def test_warted_val_letter_targets_basis_position_not_prime(self):
        patent = patent_val(12, (2, 9, 5))
        bumped = warted_val(12, "b", (2, 9, 5))
        assert bumped[1] != patent[1]
        assert bumped[0] == patent[0] and bumped[2] == patent[2]

    def test_wart_name_and_parse_round_trip(self):
        assert wart_name(12) == "12"
        assert wart_name(17, "c") == "17c"
        assert parse_wart_name("17c") == (17, "c")
        assert parse_wart_name("12") == (12, "")
        assert parse_wart_name(" 22B ") == (22, "b")

    def test_parse_wart_name_rejects_junk(self):
        with pytest.raises(ValueError):
            parse_wart_name("c12")
        with pytest.raises(ValueError):
            parse_wart_name("")

    def test_uniform_maps_enumerates_an_edos_warted_maps(self):
        maps = [(n, w, v) for n, w, v in uniform_maps((2, 3, 5), 72) if n == 17]
        assert [v for _n, _w, v in maps] == [
            (17, 26, 38), (17, 26, 39), (17, 27, 39), (17, 27, 40), (17, 28, 40), (17, 28, 41),
        ]
        assert [warts for _n, warts, _v in maps] == ["bcc", "b", "", "c", "bbc", "bbccc"]
        assert (17, "", (17, 27, 39)) in maps

    def test_uniform_maps_every_edo_offers_its_patent_val_and_round_trips(self):
        for basis in ((2, 3, 5), (2, 3, 5, 7), (2, 9, 5)):
            maps = uniform_maps(basis, 72)
            for n, warts, val in maps:
                assert warted_val(n, warts, basis) == val
            names = {wart_name(n, w) for n, w, _v in maps}
            assert len(names) == len(maps)
            assert {n for n, _w, _v in maps} == set(range(1, 73))
            for n in range(1, 73):
                assert (n, "", patent_val(n, basis)) in maps

    def test_uniform_maps_terminates_on_a_subunison_basis_element(self):
        basis = (2, Fraction(7, 11), 5)
        maps = uniform_maps(basis, 24)
        assert {n for n, _w, _v in maps} == set(range(1, 25))
        for n, warts, val in maps:
            assert warted_val(n, warts, basis) == val
        for n in range(1, 25):
            patent = patent_val(n, basis)
            assert patent[1] <= 0
            assert (n, "", patent) in maps

    def test_uniform_maps_count_grows_with_the_prime_limit(self):
        assert (len(uniform_maps((2, 3, 5), 72))
                < len(uniform_maps((2, 3, 5, 7), 72))
                < len(uniform_maps((2, 3, 5, 7, 11), 72)))
