import pytest

from rtt.library.addition import diff_, sum_
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

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


TETRACOT_M = Temperament(((1, 1, 1), (0, 4, 9)), ROW)
DICOT_M = Temperament(((1, 1, 2), (0, 2, 1)), ROW)
SRUTAL_M = Temperament(((2, 0, 11), (0, 1, -2)), ROW)
SEPTIMAL_MEANTONE_M2 = Temperament(((1, 0, -4, -13), (0, 1, 4, 10)), ROW)
FLATTONE_M = Temperament(((1, 0, -4, 17), (0, 1, 4, -9)), ROW)
GODZILLA_M = Temperament(((1, 0, -4, 2), (0, 2, 8, 1)), ROW)
MEANMAG_M = Temperament(((19, 30, 44, 0), (0, 0, 0, 1)), ROW)


# The full "basic examples" set + the historically-tricky regression cases
# (tests.m 1282-1440), all same-variance.
@pytest.mark.parametrize(
    "a, b, op, expected",
    [
        (AUGMENTED_M, TETRACOT_M, sum_, Temperament(((1, 6, 8), (0, 7, 9)), ROW)),
        (AUGMENTED_M, TETRACOT_M, diff_, Temperament(((1, 0, -12), (0, 1, 9)), ROW)),
        (AUGMENTED_M, DICOT_M, sum_, Temperament(((1, 0, 2), (0, 5, 1)), ROW)),
        (AUGMENTED_M, DICOT_M, diff_, Temperament(((1, 0, 4), (0, 1, -1)), ROW)),
        (AUGMENTED_M, SRUTAL_M, sum_, Temperament(((1, 2, 2), (0, 5, -4)), ROW)),
        (AUGMENTED_M, SRUTAL_M, diff_, Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
        (DIMINISHED_M, TETRACOT_M, sum_, Temperament(((1, 2, 3), (0, 8, 13)), ROW)),
        (DIMINISHED_M, TETRACOT_M, diff_, Temperament(((5, 8, 0), (0, 0, 1)), ROW)),
        (DIMINISHED_M, DICOT_M, sum_, Temperament(((1, 0, 1), (0, 6, 5)), ROW)),
        (DIMINISHED_M, DICOT_M, diff_, Temperament(((1, 0, 0), (0, 2, 3)), ROW)),
        (DIMINISHED_M, SRUTAL_M, sum_, Temperament(((3, 0, 7), (0, 1, 0)), ROW)),
        (DIMINISHED_M, SRUTAL_M, diff_, Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
        (TETRACOT_M, DICOT_M, sum_, Temperament(((1, 2, 3), (0, 3, 5)), ROW)),
        (TETRACOT_M, DICOT_M, diff_, Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
        (TETRACOT_M, SRUTAL_M, sum_, Temperament(((1, 0, 1), (0, 6, 5)), ROW)),
        (TETRACOT_M, SRUTAL_M, diff_, Temperament(((1, 0, -8), (0, 2, 13)), ROW)),
        (DICOT_M, SRUTAL_M, sum_, Temperament(((1, 2, 2), (0, 4, -3)), ROW)),
        (DICOT_M, SRUTAL_M, diff_, Temperament(((5, 8, 0), (0, 0, 1)), ROW)),
        # canonicalize-first matters (enfactored / sign)
        (
            Temperament(((-2, 4, -2),), ROW),
            Temperament(((7, 7, 0),), ROW),
            sum_,
            Temperament(((2, -1, 1),), ROW),
        ),
        (
            Temperament(((-2, 4, -2),), ROW),
            Temperament(((7, 7, 0),), ROW),
            diff_,
            Temperament(((0, 3, -1),), ROW),
        ),
        (SEPTIMAL_MEANTONE_M2, FLATTONE_M, sum_, GODZILLA_M),
        (SEPTIMAL_MEANTONE_M2, FLATTONE_M, diff_, MEANMAG_M),
        (
            Temperament(((1, 2, -1, 1), (0, 18, -2, -1)), ROW),
            Temperament(((2, 0, -2, 5), (0, 3, -1, 4)), ROW),
            sum_,
            Temperament(((1, 19, -4, 7), (0, 24, -4, 7)), ROW),
        ),
        (
            Temperament(((3, 2, 8, 2), (0, 5, 31, 10)), ROW),
            Temperament(((1, 22, 32, 0), (0, 32, 44, -1)), ROW),
            sum_,
            Temperament(((1, 32, 94, 20), (0, 47, 137, 29)), ROW),
        ),
        (
            Temperament(((5, 0, 1, 0), (-16, 1, 0, 3)), COL),
            Temperament(((4, 0, 1, 0), (-3, 1, 0, 3)), COL),
            sum_,
            Temperament(((9, 0, 2, 0), (-5, 1, 1, 3)), COL),
        ),
        (
            Temperament(((3, 8, -4, -6),), ROW),
            Temperament(((9, 2, -4, 1),), ROW),
            sum_,
            Temperament(((12, 10, -8, -5),), ROW),
        ),
        (
            Temperament(((-97, 73, 45, 16),), COL),
            Temperament(((-1, 8, 9, 3),), COL),
            sum_,
            Temperament(((-98, 81, 54, 19),), COL),
        ),
        (
            Temperament(((2, 0, 3),), COL),
            Temperament(((5, 4, 0),), COL),
            sum_,
            Temperament(((7, 4, 3),), COL),
        ),
        (
            Temperament(((2, 0, 3),), COL),
            Temperament(((5, 4, 0),), COL),
            diff_,
            Temperament(((-3, -4, 3),), COL),
        ),
        (
            Temperament(((0, 1, 4),), ROW),
            Temperament(((5, -6, -2),), ROW),
            sum_,
            Temperament(((5, -5, 2),), ROW),
        ),
        (
            Temperament(((0, 1, 4),), ROW),
            Temperament(((5, -6, -2),), ROW),
            diff_,
            Temperament(((5, -7, -6),), ROW),
        ),
        (
            Temperament(((-3, 2, 0, 0), (-2, 0, 0, 1)), COL),
            Temperament(((-3, 2, 0, 0), (-4, 1, 1, 0)), COL),
            sum_,
            Temperament(((-3, 2, 0, 0), (-6, 1, 1, 1)), COL),
        ),
        (
            Temperament(((-3, 2, 0, 0), (-2, 0, 0, 1)), COL),
            Temperament(((-3, 2, 0, 0), (-4, 1, 1, 0)), COL),
            diff_,
            Temperament(((-3, 2, 0, 0), (-1, 1, -1, 1)), COL),
        ),
        (
            Temperament(((5, -1, -4, 9, -3), (0, -7, -1, -8, -2)), ROW),
            Temperament(((5, -1, -4, 9, -3), (-5, 2, -4, -3, -9)), ROW),
            sum_,
            Temperament(((5, 7, -11, 23, -13), (0, 8, -7, 14, -10)), ROW),
        ),
        (
            Temperament(((5, -1, -4, 9, -3), (0, -7, -1, -8, -2)), ROW),
            Temperament(((5, -1, -4, 9, -3), (-5, 2, -4, -3, -9)), ROW),
            diff_,
            Temperament(((5, 5, 5, 11, 11), (0, 6, 9, 2, 14)), ROW),
        ),
        (
            Temperament(((-17, -55, 24, 34),), COL),
            Temperament(((-1, -7, 0, 2),), COL),
            sum_,
            Temperament(((-9, -31, 12, 18),), COL),
        ),
    ],
)
def test_addition_examples(a, b, op, expected):
    assert op(a, b) == expected


@pytest.mark.parametrize("t", [MEANTONE_M, MEANTONE_C, ET7_M, dual(ET7_M)])
def test_self_sum_returns_self(t):
    assert sum_(t, t) == t


@pytest.mark.parametrize("t", [MEANTONE_M, MEANTONE_C, ET7_M, dual(ET7_M)])
def test_self_diff_errors(t):
    with pytest.raises(ValueError):
        diff_(t, t)


def test_addition_mixed_variance():
    # col + row: the result takes the first input's variance
    assert sum_(Temperament(((2, 3),), COL), Temperament(((4, -7),), ROW)) == Temperament(
        ((9, 7),), COL
    )
    assert diff_(Temperament(((2, 3),), COL), Temperament(((4, -7),), ROW)) == Temperament(
        ((5, 1),), COL
    )
    # the "languisher": col + row
    a = Temperament(((23, -14, 3, 0), (9, -5, 1, 1)), COL)
    b = Temperament(((1, 7, 3, -1), (0, 25, 14, -1)), ROW)
    assert sum_(a, b) == Temperament(((23, -14, 14, 0), (9, -5, 5, 1)), COL)


def test_addition_is_variance_consistent():
    a, b = SEPTIMAL_MEANTONE_M2, FLATTONE_M
    assert sum_(a, b) == GODZILLA_M
    assert sum_(dual(a), b) == dual(GODZILLA_M)
    assert sum_(a, dual(b)) == GODZILLA_M
    assert sum_(dual(a), dual(b)) == dual(GODZILLA_M)


SEPTIMAL_MEANTONE_M = Temperament(((1, 0, -4, -13), (0, 1, 4, 10)), ROW)
SEPTIMAL_BLACKWOOD_M = Temperament(((5, 8, 0, 14), (0, 0, 1, 0)), ROW)
LIN_DEP_1 = Temperament(((1, 1, 0, 30, -19), (0, 0, 1, 6, -4), (0, 0, 0, 41, -27)), ROW)
LIN_DEP_2 = Temperament(((2, 0, 19, 45, 16), (0, 1, 19, 55, 18), (0, 0, 24, 70, 23)), ROW)
BIG_RANDOM_1 = Temperament(
    ((-89, -46, 61, 0, 0), (-85, -44, 59, 1, 0), (-39, -21, 26, 0, 1)), COL
)
BIG_RANDOM_2 = Temperament(((-16, -9, 1, 0, 0), (10, 4, 0, 1, 0), (16, 8, 0, 0, 1)), COL)

ERROR_PAIRS = [
    (SEPTIMAL_MEANTONE_M, SEPTIMAL_BLACKWOOD_M),  # not addable
    (dual(SEPTIMAL_MEANTONE_M), dual(SEPTIMAL_BLACKWOOD_M)),
    (ET7_M, MEANTONE_M),  # mismatched rank
    (dual(ET7_M), MEANTONE_C),
    (ET7_M, ET12_M),  # mismatched dimensionality
    (dual(ET7_M), dual(ET12_M)),
    (LIN_DEP_1, LIN_DEP_2),  # linearly dependent but not addable
    (BIG_RANDOM_1, BIG_RANDOM_2),  # "big random" — not addable
    # mismatched domain bases
    (
        Temperament(((1, 0, -4), (0, 1, 4)), ROW),
        Temperament(((1, 1, 3), (0, 3, -1)), ROW, (2, 3, 7)),
    ),
]


@pytest.mark.parametrize("op", [sum_, diff_])
@pytest.mark.parametrize("a, b", ERROR_PAIRS)
def test_addition_errors(op, a, b):
    with pytest.raises(ValueError):
        op(a, b)
