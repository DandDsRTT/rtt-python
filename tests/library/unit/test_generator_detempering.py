from rtt.library.formatting import to_ebk
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL


class TestGeneratorDetempering:
    def test_generator_detempering_mapping(self):
        t = Temperament(((1, 1, 0), (0, 1, 4)), ROW)
        assert get_generator_detempering(t) == Temperament(((1, 0, 0), (-1, 1, 0)), COL)

    def test_generator_detempering_comma_basis(self):
        t = Temperament(((4, -4, 1),), COL)
        assert get_generator_detempering(t) == Temperament(((1, 0, 0), (0, 1, 0)), COL)

    def test_generator_detempering_through_ebk(self):
        t = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
        assert to_ebk(get_generator_detempering(t)) == "[[1 0 0⟩ [-1 1 0⟩]"
