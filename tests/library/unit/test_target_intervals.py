"""Target interval set schemes (tests.m 4008-4035). The library's testTargetSetScheme
compares order-agnostically, so these assert set equality."""

from fractions import Fraction

import pytest

from rtt.library.domain_basis import filter_target_intervals_for_nonstandard_domain_basis
from rtt.library.target_intervals import get_old, get_otonal_chord, get_tilt, process_old, process_tilt


def _set(*pairs):
    return {Fraction(n, d) for n, d in pairs}


# getTilt is monotonic in the integer limit, so each set extends the previous.
_TILT = {4: _set((2, 1), (3, 1), (3, 2), (4, 3))}
_TILT[6] = _TILT[4] | _set((5, 2), (5, 3), (5, 4), (6, 5))
_TILT[8] = _TILT[6] | _set((7, 3), (7, 4), (7, 5), (7, 6), (8, 3), (8, 5))
_TILT[10] = _TILT[8] | _set((9, 4), (9, 5), (9, 7), (10, 7))
_TILT[12] = _TILT[10] | _set(
    (11, 4), (11, 5), (11, 6), (11, 7), (11, 8), (11, 9), (12, 5), (12, 7)
)
_TILT[14] = _TILT[12] | _set(
    (13, 4), (13, 5), (13, 6), (13, 7), (13, 8), (13, 9), (13, 10), (13, 11),
    (14, 5), (14, 9), (14, 11),
)
_TILT[16] = _TILT[14] | _set(
    (15, 7), (15, 8), (15, 11), (15, 13), (16, 5), (16, 7), (16, 9), (16, 11), (16, 13)
)
_TILT[18] = _TILT[16] | _set(
    (17, 6), (17, 7), (17, 8), (17, 9), (17, 10), (17, 11), (17, 12), (17, 13),
    (18, 7), (18, 11), (18, 13),
)


@pytest.mark.parametrize("integer_limit", sorted(_TILT))
def test_get_tilt(integer_limit):
    assert set(get_tilt(integer_limit)) == _TILT[integer_limit]


_OLD = {3: _set((2, 1), (3, 2), (4, 3))}
_OLD[5] = _OLD[3] | _set((5, 4), (8, 5), (5, 3), (6, 5))
_OLD[7] = _OLD[5] | _set((7, 4), (8, 7), (7, 6), (12, 7), (7, 5), (10, 7))
_OLD[9] = _OLD[7] | _set((9, 8), (16, 9), (9, 5), (10, 9), (9, 7), (14, 9))


@pytest.mark.parametrize("odd_limit", sorted(_OLD))
def test_get_old(odd_limit):
    assert set(get_old(odd_limit)) == _OLD[odd_limit]


OTONAL_CHORDS = [
    ((4, 5), _set((5, 4))),
    ((4, 5, 6), _set((5, 4), (3, 2), (6, 5))),
    ((4, 5, 6, 7), _set((5, 4), (3, 2), (7, 4), (6, 5), (7, 5), (7, 6))),
    ((8, 11, 13, 15), _set((11, 8), (13, 8), (15, 8), (13, 11), (15, 11), (15, 13))),
]


@pytest.mark.parametrize("harmonics, expected", OTONAL_CHORDS)
def test_get_otonal_chord(harmonics, expected):
    assert set(get_otonal_chord(harmonics)) == expected


# Default integer/odd limit picked from the domain basis (tests.m 3885-3914): with no explicit
# limit, TILT/OLD pick the integer/odd just below the next prime past the basis's greatest part.
@pytest.mark.parametrize(
    "domain_basis, default_limit",
    [
        ((2, 3, 5), "6-TILT"),
        ((2, 3, 5, 7), "10-TILT"),
        ((2, 9, 21), "22-TILT"),
        ((2, 3, Fraction(13, 5)), "16-TILT"),
        ((2, 3, Fraction(5, 13)), "16-TILT"),
        ((2, Fraction(5, 7)), "10-TILT"),
    ],
)
def test_process_tilt_default_limit_reads_the_greatest_part_numerator_or_denominator(
    domain_basis, default_limit
):
    assert process_tilt("TILT", domain_basis) == process_tilt(default_limit, domain_basis)


@pytest.mark.parametrize(
    "domain_basis, default_limit",
    [
        ((2, 3, 5), "5-OLD"),
        ((2, 3, 5, 7), "9-OLD"),
        ((2, 9, 21), "21-OLD"),
        ((2, 3, Fraction(13, 5)), "15-OLD"),
        ((2, 3, Fraction(5, 13)), "15-OLD"),
        ((2, Fraction(5, 7)), "9-OLD"),
    ],
)
def test_process_old_default_limit_reads_the_greatest_part_numerator_or_denominator(
    domain_basis, default_limit
):
    assert process_old("OLD", domain_basis) == process_old(default_limit, domain_basis)


@pytest.mark.parametrize(
    "process, family, domain_basis",
    [
        (process_tilt, "TILT", (2, 3, Fraction(5, 13))),
        (process_old, "OLD", (2, 3, Fraction(5, 13))),
        (process_tilt, "TILT", (2, Fraction(5, 7))),
        (process_old, "OLD", (2, Fraction(5, 7))),
    ],
)
def test_default_limit_keeps_a_nonempty_target_set_when_a_denominator_holds_the_greatest_part(
    process, family, domain_basis
):
    quotients = process(family, domain_basis)
    filtered = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain_basis)
    assert filtered, f"{family} default limit left no targets for {domain_basis}"


# Filtering a target set to a nonstandard subgroup (tests.m 4109-4112): over the basis 4.3.5,
# 2/1 is dropped (2 is not a power of 4); over 2.3.7, the 5-bearing intervals are dropped.
FILTER_CASES = [
    (get_old(5), (4, 3, 5), {(4, 3), (5, 4), (5, 3)}),
    (get_old(9), (2, 3, 7),
     {(2, 1), (4, 3), (8, 7), (16, 9), (3, 2), (12, 7), (7, 4), (7, 6), (14, 9), (9, 8), (9, 7)}),
    (get_tilt(6), (4, 3, 5), {(3, 1), (4, 3), (5, 3), (5, 4)}),
    (get_tilt(8), (2, 3, 7),
     {(2, 1), (3, 1), (3, 2), (4, 3), (7, 3), (7, 4), (7, 6), (8, 3)}),
]


@pytest.mark.parametrize("quotients, domain_basis, expected", FILTER_CASES)
def test_filter_target_intervals_for_nonstandard_domain_basis(quotients, domain_basis, expected):
    filtered = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain_basis)
    assert set(filtered) == {Fraction(n, d) for n, d in expected}
