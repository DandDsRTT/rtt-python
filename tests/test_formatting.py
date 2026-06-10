import pytest

from rtt.formatting import covector_to_ebk, format_output, to_ebk, vector_to_ebk
from rtt.temperament import Temperament, Variance

DUMMY = Temperament(((1, 2, 3), (0, 5, 6)), Variance.ROW)  # d = 3, r = 2

ROW, COL = Variance.ROW, Variance.COL


@pytest.mark.parametrize(
    "vector, expected",
    [
        ((-4, 4, -1), "[-4 4 -1⟩"),  # length == d
        ((-3, 2), "[-3 2}"),  # length == r
        ((-3, 2, 0, 0), "[-3 2 0 0]"),  # neither
    ],
)
def test_vector_to_ebk(vector, expected):
    assert vector_to_ebk(vector, DUMMY) == expected


@pytest.mark.parametrize(
    "covector, expected",
    [
        ((1, 0, -4), "⟨1 0 -4]"),  # length == d
        ((7, 7), "{7 7]"),  # length == r
        ((7, 7, 7, 7), "[7 7 7 7]"),  # neither
    ],
)
def test_covector_to_ebk(covector, expected):
    assert covector_to_ebk(covector, DUMMY) == expected


@pytest.mark.parametrize(
    "temperament, expected",
    [
        (Temperament(((1200.0, 1901.955, 2786.314),), ROW), "⟨1200.000 1901.955 2786.314]"),
        (Temperament(((1, 0, -4), (0, 1, 4)), ROW), "[⟨1 0 -4] ⟨0 1 4]}"),
        (Temperament(((1, -5, 3),), COL), "[1 -5 3⟩"),
        (Temperament(((-4, 4, -1), (7, 0, -3)), COL), "[[-4 4 -1⟩ [7 0 -3⟩]"),
        (Temperament(((4,), (5,)), ROW), "[⟨4] ⟨5]]"),
        (Temperament(((4,), (5,)), COL), "[[4⟩ [5⟩]"),
    ],
)
def test_to_ebk(temperament, expected):
    assert to_ebk(temperament) == expected


def test_format_output_wolfram_is_identity():
    t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
    assert format_output(t, "wolfram") == t


def test_format_output_ebk():
    t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
    assert format_output(t, "ebk") == "[⟨1 0 -4] ⟨0 1 4]}"
