from fractions import Fraction

from rtt.parsing import parse_temperament_data
from rtt.temperament import Temperament, Variance


def test_parses_meantone_mapping():
    t = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")
    assert t == Temperament(((1, 0, -4), (0, 1, 4)), Variance.ROW)


def test_parses_meantone_comma_basis():
    t = parse_temperament_data("[4 -4 1⟩")
    assert t == Temperament(((4, -4, 1),), Variance.COL)
