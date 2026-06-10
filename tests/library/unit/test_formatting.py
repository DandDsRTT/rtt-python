import pytest

from rtt.library.formatting import (
    covector_to_ebk,
    format_output,
    strip_negative_zero,
    to_ebk,
    vector_to_ebk,
)
from rtt.library.temperament import Temperament, Variance

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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("-0.000", "0.000"),  # the reported bug: a zero shown with a sign
        ("-0", "0"),
        ("-0.0", "0.0"),
        ("-0.000000", "0.000000"),  # any precision
        ("0.000", "0.000"),  # already unsigned — untouched
        ("-0.001", "-0.001"),  # a real nonzero negative keeps its sign
        ("-12.000", "-12.000"),
        ("3.140", "3.140"),
    ],
)
def test_strip_negative_zero(text, expected):
    assert strip_negative_zero(text) == expected


def test_format_number_drops_negative_zero():
    # a float that rounds to all-zero digits formats without the sign (negative zero is meaningless)
    assert vector_to_ebk((-0.0004, 4.0, -1.0), DUMMY) == "[0.000 4.000 -1.000⟩"
    assert covector_to_ebk((-0.0, 1901.955, 0.0), DUMMY) == "⟨0.000 1901.955 0.000]"
