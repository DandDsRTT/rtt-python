from rtt.formatting import to_ebk
from rtt.generator_detempering import get_generator_detempering
from rtt.parsing import parse_temperament_data
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL


def test_generator_detempering_mapping():
    t = Temperament(((1, 1, 0), (0, 1, 4)), ROW)
    assert get_generator_detempering(t) == Temperament(((1, 0, 0), (-1, 1, 0)), COL)


def test_generator_detempering_comma_basis():
    t = Temperament(((4, -4, 1),), COL)
    assert get_generator_detempering(t) == Temperament(((1, 0, 0), (0, 1, 0)), COL)


def test_generator_detempering_through_ebk():
    t = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
    assert to_ebk(get_generator_detempering(t)) == "[[1 0 0⟩ [-1 1 0⟩]"
