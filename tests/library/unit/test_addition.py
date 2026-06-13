import random
import time

import pytest
import sympy as sp

from rtt.library.addition import _find_modular_solution, diff_, sum_
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


# --- temperament-addition-1: sum_/diff_ are duality-consistent --------------
# The temperament sum/difference must be independent of which side of duality the
# inputs are handed in as: dual(sum_(M1, M2)) == sum_(dual M1, dual M2). The old
# per-variance negation rule ignored the Hodge permutation sign and silently
# swapped sum<->difference for some addable pairs (e.g. the schisma below).

# Curated regression pairs that USED to swap sum<->diff across duality.
DUALITY_SWAP_PAIRS = [
    # compton (Pythagorean comma) + meantone -> schisma was returned as the diff
    # on the mapping side; the sum is ((-15, 8, 1),), the diff ((23, -16, 1),).
    (Temperament(((-19, 12, 0),), COL), Temperament(((4, -4, 1),), COL)),
    # nullity-1 / rank-1 pairs that fuzzing flagged as inconsistent
    (Temperament(((2, 2, -3),), ROW), Temperament(((0, 2, -1),), ROW)),
    (Temperament(((0, 4, 3),), ROW), Temperament(((6, -1, 4),), ROW)),
    # r == n == 2 in d=4 (no g_min tie-break) that also used to swap
    (
        Temperament(((-6, -4, 1, -2), (5, 0, 1, -1)), ROW),
        Temperament(((-3, 0, -5, 5), (-2, 0, -1, 1)), ROW),
    ),
    (
        Temperament(((2, -3, 6, 2), (0, 1, -5, -4)), ROW),
        Temperament(((6, 0, 6, 3), (-6, 0, -3, 0)), ROW),
    ),
]


@pytest.mark.parametrize("op", [sum_, diff_])
@pytest.mark.parametrize("a, b", DUALITY_SWAP_PAIRS)
def test_addition_duality_consistent_regressions(op, a, b):
    assert op(a, b) == dual(op(dual(a), dual(b)))


def test_compton_meantone_sum_is_schisma_on_both_sides():
    c1, c2 = Temperament(((-19, 12, 0),), COL), Temperament(((4, -4, 1),), COL)
    m1, m2 = dual(c1), dual(c2)
    assert sum_(c1, c2) == Temperament(((-15, 8, 1),), COL)  # schisma
    assert dual(sum_(m1, m2)) == Temperament(((-15, 8, 1),), COL)
    assert diff_(c1, c2) == Temperament(((23, -16, 1),), COL)
    assert dual(diff_(m1, m2)) == Temperament(((23, -16, 1),), COL)


def _random_full_rank_rows(rng, d, r):
    while True:
        rows = tuple(tuple(rng.randint(-6, 6) for _ in range(d)) for _ in range(r))
        if sp.Matrix(rows).rank() == r:
            return rows


def test_addition_duality_consistent_fuzz():
    rng = random.Random(20240613)
    checked = 0
    for _ in range(250):
        d = rng.choice([3, 4, 5])
        r = rng.randint(1, d - 1)
        t1 = Temperament(_random_full_rank_rows(rng, d, r), ROW)
        t2 = Temperament(_random_full_rank_rows(rng, d, r), ROW)
        for op in (sum_, diff_):
            try:
                result = op(t1, t2)
            except ValueError:
                # non-addability (or self-diff) must be reported on both sides
                with pytest.raises(ValueError):
                    op(dual(t1), dual(t2))
                continue
            assert result == dual(op(dual(t1), dual(t2)))
            checked += 1
    assert checked > 100  # the fuzz actually exercised addable pairs


# --- temperament-addition-3: the result carries the inputs' domain basis ----
def test_addition_preserves_domain_basis():
    a = Temperament(((5, 8, 14),), ROW, (2, 3, 7))
    b = Temperament(((7, 11, 20),), ROW, (2, 3, 7))
    result = sum_(a, b)
    assert result.matrix == ((12, 19, 34),)
    assert result.domain_basis == (2, 3, 7)
    assert diff_(a, b).domain_basis == (2, 3, 7)
    # a nonstandard COL pair keeps its basis too
    c = Temperament(((-8, 5, 0), (-6, 2, 1)), COL, (2, 3, 7))
    d = Temperament(((-2, 0, 1), (-3, 2, 0)), COL, (2, 3, 7))
    assert sum_(c, d).domain_basis == (2, 3, 7)


# --- temperament-addition-4: addabilization defactoring is not brute force --
def test_find_modular_solution_is_bounded_and_correct():
    # A 4-vector L_dep with a sizeable modulus: the old brute force scanned
    # modulus ** 4 candidates (here ~1.5e8); the closed-form solve is instant.
    # Build base so a solution is guaranteed to exist (base == -L^T x mod modulus).
    rng = random.Random(7)
    modulus = 111
    ldb = tuple(tuple(rng.randint(-9, 9) for _ in range(6)) for _ in range(4))
    seed_multiples = [rng.randint(0, modulus - 1) for _ in range(len(ldb))]
    base = tuple(
        modulus * rng.randint(-3, 3)
        - sum(seed_multiples[i] * ldb[i][j] for i in range(len(ldb)))
        for j in range(6)
    )
    start = time.perf_counter()
    multiples = _find_modular_solution(ldb, base, modulus)
    assert time.perf_counter() - start < 5.0
    combined = [
        base[j] + sum(multiples[i] * ldb[i][j] for i in range(len(ldb)))
        for j in range(len(base))
    ]
    assert all(value % modulus == 0 for value in combined)


def test_heavy_13_limit_sum_is_fast_and_consistent():
    # monzisma (13-limit) + 123201/123200: the old modulus ** (grade-1) brute
    # force took ~16 s here; bound the whole sum_ call well under that.
    c1 = Temperament(((54, -37, 2, 0, 0, 0),), COL)
    c2 = Temperament(((-5, 6, -2, 2, -1, -1),), COL)
    start = time.perf_counter()
    comma_side = sum_(c1, c2)
    map_side = dual(sum_(dual(c1), dual(c2)))
    assert time.perf_counter() - start < 10.0
    assert comma_side == map_side
