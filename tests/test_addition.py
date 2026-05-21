import pytest

from rtt.addition import diff_, sum_
from rtt.dual import dual
from rtt.formatting import to_ebk
from rtt.parsing import parse_temperament_data
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

MEANTONE_M = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
MEANTONE_C = Temperament(((4, -4, 1),), COL)
PORCUPINE_C = Temperament(((1, -5, 3),), COL)
ET7_M = Temperament(((7, 11, 16),), ROW)
ET5_M = Temperament(((5, 8, 12),), ROW)
ET12_M = Temperament(((12, 19, 28, 34),), ROW)


# Grade-1 (single comma / single map): a sign-aligned vector add/subtract.
@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (MEANTONE_C, PORCUPINE_C, sum_, Temperament(((5, -9, 4),), COL)),
        (MEANTONE_C, PORCUPINE_C, diff_, Temperament(((-3, -1, 2),), COL)),
        (ET7_M, ET5_M, sum_, Temperament(((12, 19, 28),), ROW)),
        (ET7_M, ET5_M, diff_, Temperament(((2, 3, 4),), ROW)),
    ],
)
def test_grade_one_addition(a, b, op, expected):
    assert op(a, b) == expected


@pytest.mark.parametrize(
    "ebk_a, ebk_b, op, expected",
    [
        ("[4 -4 1⟩", "[1 -5 3⟩", sum_, "[5 -9 4⟩"),
        ("[4 -4 1⟩", "[1 -5 3⟩", diff_, "[-3 -1 2⟩"),
    ],
)
def test_addition_through_ebk(ebk_a, ebk_b, op, expected):
    result = op(parse_temperament_data(ebk_a), parse_temperament_data(ebk_b))
    assert to_ebk(result) == expected


PORCUPINE_M = Temperament(((1, 2, 3), (0, 3, 5)), ROW)
ET19_M = Temperament(((19, 30, 44, 53),), ROW)
AUGMENTED_M = Temperament(((3, 0, 7), (0, 1, 0)), ROW)
DIMINISHED_M = Temperament(((4, 0, 3), (0, 1, 1)), ROW)


# Grade >= 2 (linearly dependent): needs the addabilization defactoring.
@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (MEANTONE_M, PORCUPINE_M, sum_, Temperament(((1, 1, 1), (0, 4, 9)), ROW)),
        (MEANTONE_M, PORCUPINE_M, diff_, Temperament(((1, 1, 2), (0, 2, 1)), ROW)),
        (dual(ET7_M), dual(ET5_M), sum_, Temperament(((-19, 12, 0), (-15, 8, 1)), COL)),
        (dual(ET7_M), dual(ET5_M), diff_, Temperament(((-3, 2, 0), (-2, 0, 1)), COL)),
        (ET12_M, ET19_M, sum_, Temperament(((31, 49, 72, 87),), ROW)),
        (ET12_M, ET19_M, diff_, Temperament(((7, 11, 16, 19),), ROW)),
        (
            dual(ET12_M),
            dual(ET19_M),
            sum_,
            Temperament(((-49, 31, 0, 0), (-45, 27, 1, 0), (-36, 21, 0, 1)), COL),
        ),
        (
            dual(ET12_M),
            dual(ET19_M),
            diff_,
            Temperament(((-11, 7, 0, 0), (-7, 3, 1, 0), (-9, 4, 0, 1)), COL),
        ),
        (AUGMENTED_M, DIMINISHED_M, sum_, Temperament(((1, 1, 2), (0, 7, 4)), ROW)),
        (AUGMENTED_M, DIMINISHED_M, diff_, Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
    ],
)
def test_linearly_dependent_addition(a, b, op, expected):
    assert op(a, b) == expected


@pytest.mark.parametrize("t", [MEANTONE_M, MEANTONE_C, ET7_M, dual(ET7_M)])
def test_self_sum_returns_self(t):
    assert sum_(t, t) == t


@pytest.mark.parametrize("t", [MEANTONE_M, MEANTONE_C, ET7_M, dual(ET7_M)])
def test_self_diff_errors(t):
    with pytest.raises(ValueError):
        diff_(t, t)


SEPTIMAL_MEANTONE_M = Temperament(((1, 0, -4, -13), (0, 1, 4, 10)), ROW)
SEPTIMAL_BLACKWOOD_M = Temperament(((5, 8, 0, 14), (0, 0, 1, 0)), ROW)
LIN_DEP_1 = Temperament(((1, 1, 0, 30, -19), (0, 0, 1, 6, -4), (0, 0, 0, 41, -27)), ROW)
LIN_DEP_2 = Temperament(((2, 0, 19, 45, 16), (0, 1, 19, 55, 18), (0, 0, 24, 70, 23)), ROW)

ERROR_PAIRS = [
    (SEPTIMAL_MEANTONE_M, SEPTIMAL_BLACKWOOD_M),  # not addable
    (dual(SEPTIMAL_MEANTONE_M), dual(SEPTIMAL_BLACKWOOD_M)),
    (ET7_M, MEANTONE_M),  # mismatched rank
    (dual(ET7_M), MEANTONE_C),
    (ET7_M, ET12_M),  # mismatched dimensionality
    (dual(ET7_M), dual(ET12_M)),
    (LIN_DEP_1, LIN_DEP_2),  # linearly dependent but not addable
]


@pytest.mark.parametrize("op", [sum_, diff_])
@pytest.mark.parametrize("a, b", ERROR_PAIRS)
def test_addition_errors(op, a, b):
    with pytest.raises(ValueError):
        op(a, b)
