from fractions import Fraction

from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.matrix_utils import matrix_multiply
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

MEANTONE = Temperament(((1, 1, 0), (0, 1, 4)), ROW)


def test_quarter_comma_meantone_projection_holds_2_and_5():
    """5-limit meantone, holding 2/1 and 5/1 justly, is quarter-comma: the
    projection sends each just prime to its tempered size, with the fifth flat
    by 1/4 comma (the 1/4 on prime 3's image)."""
    held = Temperament(((1, 0, 0), (0, 0, 1)), COL)  # 2/1 and 5/1
    assert get_tempering_projection(MEANTONE, held) == (
        (1, 1, 0),
        (0, 0, 0),
        (0, Fraction(1, 4), 1),
    )


def test_quarter_comma_meantone_embedding_generator_is_quarter_root_of_5():
    """The embedding's generators (its columns) are the octave 2/1 and the
    fractional vector 5^(1/4) — quarter-comma meantone's defining fifth."""
    held = Temperament(((1, 0, 0), (0, 0, 1)), COL)  # 2/1 and 5/1
    assert get_generator_embedding(MEANTONE, held) == (
        (1, 0),
        (0, 0),
        (0, Fraction(1, 4)),
    )


def test_holding_2_and_3_reproduces_the_integer_generator_detempering():
    """Holding the first r primes instead recovers the integer (Smith-form)
    detempering's projection — which holds 2 & 3 and tempers 5, the wrong
    primes for the canonical embedding."""
    held = Temperament(((1, 0, 0), (0, 1, 0)), COL)  # 2/1 and 3/1
    assert get_tempering_projection(MEANTONE, held) == (
        (1, 0, -4),
        (0, 1, 4),
        (0, 0, 0),
    )


def test_projection_is_idempotent():
    """P is a projection: applying it twice is the same as applying it once."""
    held = Temperament(((1, 0, 0), (0, 0, 1)), COL)
    p = get_tempering_projection(MEANTONE, held)
    assert matrix_multiply(p, p) == p
