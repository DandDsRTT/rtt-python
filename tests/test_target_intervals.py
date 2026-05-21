"""Target-interval set schemes (tests.m 4008-4035). The library's testTargetSetScheme
compares order-agnostically, so these assert set equality."""

from fractions import Fraction

import pytest

from rtt.target_intervals import get_old, get_otonal_chord, get_tilt


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
