import pytest

from rtt.dimensions import get_d, get_n, get_r
from rtt.parsing import parse_temperament_data
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

# (temperament, d, r, n) — every dimensions case from rtt-library/tests.m.
DIMENSIONS = [
    (Temperament(((0,),), ROW), 1, 0, 1),
    (Temperament(((0,),), COL), 1, 1, 0),
    (Temperament(((0, 0),), ROW), 2, 0, 2),
    (Temperament(((0, 0),), COL), 2, 2, 0),
    (Temperament(((0,), (0,)), ROW), 1, 0, 1),
    (Temperament(((0,), (0,)), COL), 1, 1, 0),
    (Temperament(((1, 0), (0, 1)), ROW), 2, 2, 0),
    (Temperament(((1, 0), (0, 1)), COL), 2, 0, 2),
    (Temperament(((1, 0, -4), (0, 1, 4)), ROW), 3, 2, 1),
    (Temperament(((4, -4, 1),), COL), 3, 2, 1),
    (Temperament(((1, 0, -4, 0), (0, 1, 4, 0)), ROW), 4, 2, 2),
    (Temperament(((4, -4, 1, 0),), COL), 4, 3, 1),
    (Temperament(((1, 1, 3), (0, 3, -1)), ROW, (2, 3, 7)), 3, 2, 1),
    (Temperament(((1200.0, 1901.955, 2386.314),), ROW), 3, 1, 2),
    (Temperament(((12, 19, 28),), ROW), 3, 1, 2),
    (Temperament(((-4, 4, -1),), COL), 3, 2, 1),
]


@pytest.mark.parametrize("t, d, r, n", DIMENSIONS)
def test_get_d(t, d, r, n):
    assert get_d(t) == d


@pytest.mark.parametrize("t, d, r, n", DIMENSIONS)
def test_get_r(t, d, r, n):
    assert get_r(t) == r


@pytest.mark.parametrize("t, d, r, n", DIMENSIONS)
def test_get_n(t, d, r, n):
    assert get_n(t) == n


@pytest.mark.parametrize(
    "ebk, d, r, n",
    [("[⟨1 0 -4] ⟨0 1 4]}", 3, 2, 1), ("[4 -4 1⟩", 3, 2, 1)],
)
def test_dimensions_through_parser(ebk, d, r, n):
    t = parse_temperament_data(ebk)
    assert (get_d(t), get_r(t), get_n(t)) == (d, r, n)
