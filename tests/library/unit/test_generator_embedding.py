from fractions import Fraction

from rtt.library.generator_embedding import get_generator_embedding, get_tempering_projection
from rtt.library.matrix_utils import matrix_multiply
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

MEANTONE = Temperament(((1, 1, 0), (0, 1, 4)), ROW)

HELD_2_AND_5 = Temperament(((1, 0, 0), (0, 0, 1)), COL)
HELD_2_AND_3 = Temperament(((1, 0, 0), (0, 1, 0)), COL)


class TestGeneratorEmbedding:
    def test_quarter_comma_meantone_projection_holds_2_and_5(self):
        """5-limit meantone, holding 2/1 and 5/1 justly, is quarter-comma: the
        projection sends each just prime to its tempered size, with the fifth flat
        by 1/4 comma (the 1/4 on prime 3's image)."""
        assert get_tempering_projection(MEANTONE, HELD_2_AND_5) == (
            (1, 1, 0),
            (0, 0, 0),
            (0, Fraction(1, 4), 1),
        )

    def test_quarter_comma_meantone_embedding_generator_is_quarter_root_of_5(self):
        """The embedding's generators (its columns) are the octave 2/1 and the
        fractional vector 5^(1/4) — quarter-comma meantone's defining fifth."""
        assert get_generator_embedding(MEANTONE, HELD_2_AND_5) == (
            (1, 0),
            (0, 0),
            (0, Fraction(1, 4)),
        )

    def test_holding_2_and_3_reproduces_the_integer_generator_detempering(self):
        """Holding the first r primes instead recovers the integer (Smith-form)
        detempering's projection — which holds 2 & 3 and tempers 5, the wrong
        primes for the canonical embedding."""
        assert get_tempering_projection(MEANTONE, HELD_2_AND_3) == (
            (1, 0, -4),
            (0, 1, 4),
            (0, 0, 0),
        )

    def test_projection_is_idempotent(self):
        """P is a projection: applying it twice is the same as applying it once."""
        p = get_tempering_projection(MEANTONE, HELD_2_AND_5)
        assert matrix_multiply(p, p) == p
