import pytest

from rtt.library.canonicalization import canonical_form
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL
I1 = ((1,),)
I2 = ((1, 0), (0, 1))
I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

DUAL_CASES = [
    (Temperament(((1, 0, -4), (0, 1, 4)), ROW), Temperament(((4, -4, 1),), COL)),
    (Temperament(((0, 9, 4),), ROW), Temperament(((1, 0, 0), (0, -4, 9)), COL)),
    (Temperament(((0,),), ROW), Temperament(I1, COL)),
    (Temperament(((0, 0),), ROW), Temperament(I2, COL)),
    (Temperament(((0, 0, 0),), ROW), Temperament(I3, COL)),
    (Temperament(I1, ROW), Temperament(((0,),), COL)),
    (Temperament(I2, ROW), Temperament(((0, 0),), COL)),
    (Temperament(I3, ROW), Temperament(((0, 0, 0),), COL)),
    (Temperament(((12, 19),), ROW), Temperament(((-19, 12),), COL)),
    (Temperament(((4, -4, 1),), COL), Temperament(((1, 0, -4), (0, 1, 4)), ROW)),
    (Temperament(((1, 0, 0), (0, -4, 9)), COL), Temperament(((0, 9, 4),), ROW)),
    (Temperament(((0,),), COL), Temperament(I1, ROW)),
    (Temperament(((0, 0),), COL), Temperament(I2, ROW)),
    (Temperament(((0, 0, 0),), COL), Temperament(I3, ROW)),
    (Temperament(I1, COL), Temperament(((0,),), ROW)),
    (Temperament(I2, COL), Temperament(((0, 0),), ROW)),
    (Temperament(I3, COL), Temperament(((0, 0, 0),), ROW)),
    (Temperament(((-19, 12),), COL), Temperament(((12, 19),), ROW)),
]

DUAL_PAIRS = [
    (Temperament(((1, 0, -4), (0, 1, 4)), ROW), Temperament(((4, -4, 1),), COL)),
    (Temperament(((1, 0, 0), (0, -4, 9)), ROW), Temperament(((0, 9, 4),), COL)),
    (Temperament(((0,),), ROW), Temperament(I1, COL)),
    (Temperament(((0, 0),), ROW), Temperament(I2, COL)),
    (Temperament(((0, 0, 0),), ROW), Temperament(I3, COL)),
    (Temperament(I1, ROW), Temperament(((0,),), COL)),
    (Temperament(I2, ROW), Temperament(((0, 0),), COL)),
    (Temperament(I3, ROW), Temperament(((0, 0, 0),), COL)),
    (Temperament(((12, 19),), ROW), Temperament(((-19, 12),), COL)),
]


class TestDual:
    @pytest.mark.parametrize("temperament, expected", DUAL_CASES)
    def test_dual(self, temperament, expected):
        assert dual(temperament) == expected

    @pytest.mark.parametrize("mapping, comma_basis", DUAL_PAIRS)
    def test_dual_agrees_with_canonical_form(self, mapping, comma_basis):
        assert dual(mapping) == canonical_form(comma_basis)
        assert dual(comma_basis) == canonical_form(mapping)

    def test_dual_through_parser(self):
        assert to_ebk(dual(parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}"))) == "[4 -4 1⟩"
