import pytest

from rtt.dual import dual
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

# (input, expected dual) drawn from rtt-library/tests.m dualPrivate cases.
DUAL_CASES = [
    (Temperament(((1, 0, -4), (0, 1, 4)), ROW), Temperament(((4, -4, 1),), COL)),
    (Temperament(((0, 9, 4),), ROW), Temperament(((1, 0, 0), (0, -4, 9)), COL)),
    (Temperament(((4, -4, 1),), COL), Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
    (Temperament(((1, 0, 0), (0, -4, 9)), COL), Temperament(((0, 9, 4),), ROW)),
    (Temperament(((12, 19),), ROW), Temperament(((-19, 12),), COL)),
    (Temperament(((-19, 12),), COL), Temperament(((12, 19),), ROW)),
    # zero mapping -> every prime is a comma (identity comma basis)
    (Temperament(((0, 0, 0),), ROW), Temperament(((1, 0, 0), (0, 1, 0), (0, 0, 1)), COL)),
    # full mapping -> no commas (single zero comma)
    (Temperament(((1, 0, 0), (0, 1, 0), (0, 0, 1)), ROW), Temperament(((0, 0, 0),), COL)),
]


@pytest.mark.parametrize("temperament, expected", DUAL_CASES)
def test_dual(temperament, expected):
    assert dual(temperament) == expected
