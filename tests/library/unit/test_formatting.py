from fractions import Fraction

import pytest

from rtt.library.formatting import (
    covector_to_ebk,
    format_output,
    strip_negative_zero,
    to_ebk,
    vector_to_ebk,
)
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

DUMMY = Temperament(((1, 2, 3), (0, 5, 6)), Variance.ROW)

ROW, COL = Variance.ROW, Variance.COL


class TestFormatting:
    @pytest.mark.parametrize(
        "vector, expected",
        [
            ((-4, 4, -1), "[-4 4 -1⟩"),
            ((-3, 2), "[-3 2}"),
            ((-3, 2, 0, 0), "[-3 2 0 0]"),
        ],
    )
    def test_vector_to_ebk(self, vector, expected):
        assert vector_to_ebk(vector, DUMMY) == expected

    @pytest.mark.parametrize(
        "covector, expected",
        [
            ((1, 0, -4), "⟨1 0 -4]"),
            ((7, 7), "{7 7]"),
            ((7, 7, 7, 7), "[7 7 7 7]"),
        ],
    )
    def test_covector_to_ebk(self, covector, expected):
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
    def test_to_ebk(self, temperament, expected):
        assert to_ebk(temperament) == expected

    def test_format_output_wolfram_is_identity(self):
        t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
        assert format_output(t, "wolfram") == t

    def test_format_output_ebk(self):
        t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
        assert format_output(t, "ebk") == "[⟨1 0 -4] ⟨0 1 4]}"

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("-0.000", "0.000"),
            ("-0", "0"),
            ("-0.0", "0.0"),
            ("-0.000000", "0.000000"),
            ("0.000", "0.000"),
            ("-0.001", "-0.001"),
            ("-12.000", "-12.000"),
            ("3.140", "3.140"),
        ],
    )
    def test_strip_negative_zero(self, text, expected):
        assert strip_negative_zero(text) == expected

    def test_to_ebk_preserves_exact_rationals(self):
        t = parse_temperament_data("[1/4 -1/3 0⟩")
        assert to_ebk(t) == "[1/4 -1/3 0⟩"
        assert parse_temperament_data(to_ebk(t)).matrix == ((Fraction(1, 4), Fraction(-1, 3), 0),)
        assert vector_to_ebk((Fraction(2, 1), Fraction(3, 2), 0), DUMMY) == "[2 3/2 0⟩"

    def test_format_number_drops_negative_zero(self):
        assert vector_to_ebk((-0.0004, 4.0, -1.0), DUMMY) == "[0.000 4.000 -1.000⟩"
        assert covector_to_ebk((-0.0, 1901.955, 0.0), DUMMY) == "⟨0.000 1901.955 0.000]"
