import pytest

from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.merging import comma_merge, map_merge
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

ET5_M = Temperament(((5, 8, 12),), ROW)
ET5_C = Temperament(((-8, 5, 0), (-4, 1, 1)), COL)
ET7_M = Temperament(((7, 11, 16),), ROW)
ET7_C = Temperament(((-11, 7, 0), (-7, 3, 1)), COL)
MEANTONE_M = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
MEANTONE_C = Temperament(((4, -4, 1),), COL)
PORCUPINE_M = Temperament(((1, 2, 3), (0, 3, 5)), ROW)
PORCUPINE_C = Temperament(((1, -5, 3),), COL)

ET7D_M7 = Temperament(((7, 11, 16, 19),), ROW)
ET12_M7 = Temperament(((12, 19, 28, 34),), ROW)
ET22_M7 = Temperament(((22, 35, 51, 62),), ROW)
MARVEL = Temperament(((1, 0, 0, -5), (0, 1, 0, 2), (0, 0, 1, 2)), ROW)
MINT_C7 = Temperament(((2, 2, -1, -1),), COL)
MEANTONE_C7 = Temperament(((4, -4, 1, 0),), COL)
NEGRI_C7 = Temperament(((-14, 3, 4, 0),), COL)
ET19D_C7 = dual(Temperament(((19, 30, 44, 54),), ROW))


@pytest.mark.parametrize(
    "factors",
    [
        (ET5_M, ET7_M),
        (ET5_M, ET7_C),
        (ET5_C, ET7_M),
        (ET5_C, ET7_C),
    ],
)
def test_map_merge_to_meantone(factors):
    assert map_merge(*factors) == MEANTONE_M


@pytest.mark.parametrize(
    "factors",
    [
        (MEANTONE_C, PORCUPINE_C),
        (MEANTONE_M, PORCUPINE_C),
        (MEANTONE_C, PORCUPINE_M),
        (MEANTONE_M, PORCUPINE_M),
    ],
)
def test_comma_merge_to_et7(factors):
    assert comma_merge(*factors) == ET7_C


def test_map_merge_three_temperaments():
    assert map_merge(ET7D_M7, ET12_M7, ET22_M7) == MARVEL


def test_comma_merge_three_temperaments():
    assert comma_merge(MINT_C7, MEANTONE_C7, NEGRI_C7) == ET19D_C7


@pytest.mark.parametrize(
    "merge, inputs, expected",
    [
        (map_merge, ("⟨5 8 12]", "⟨7 11 16]"), "[⟨1 0 -4] ⟨0 1 4]}"),
        (
            map_merge,
            ("⟨7 11 16 19]", "⟨12 19 28 34]", "⟨22 35 51 62]"),
            "[⟨1 0 0 -5] ⟨0 1 0 2] ⟨0 0 1 2]}",
        ),
        (comma_merge, ("[4 -4 1⟩", "[1 -5 3⟩"), "[[-11 7 0⟩ [-7 3 1⟩]"),
        (
            comma_merge,
            ("[2 2 -1 -1⟩", "[4 -4 1 0⟩", "[-14 3 4 0⟩"),
            "[[-30 19 0 0⟩ [-26 15 1 0⟩ [-6 2 0 1⟩]",
        ),
    ],
)
def test_merge_through_ebk(merge, inputs, expected):
    result = merge(*(parse_temperament_data(s) for s in inputs))
    assert to_ebk(result) == expected


def test_map_merge_nonstandard_bases():
    t1 = Temperament(((22, 35, 51, 76),), ROW, (2, 3, 5, 11))
    t2 = Temperament(((17, 54, 48, 59),), ROW, (2, 9, 7, 11))
    assert map_merge(t1, t2) == Temperament(((1, 0, 13), (0, 1, -3)), ROW, (2, 9, 11))


def test_map_merge_mixed_variance_nonstandard():
    t1 = Temperament(((4, -4, 1),), COL)
    t2 = Temperament(((4, -2, 1, 0), (6, -3, 0, 1)), COL, (2, 9, 5, 11))
    assert map_merge(t1, t2) == Temperament(((1, 0, -4), (0, 1, 2)), ROW, (2, 9, 5))


def test_comma_merge_nonstandard_to_standard():
    t1 = Temperament(((4, -4, 1),), COL)
    t2 = Temperament(((6, -1, -1),), COL, (2, 9, 7))
    assert comma_merge(t1, t2) == Temperament(((4, -4, 1, 0), (-6, 2, 0, 1)), COL)


def test_comma_merge_nonstandard_result():
    t1 = Temperament(((5, 8, 12), (7, 11, 16)), ROW)
    t2 = Temperament(((7, 22, 16, 24), (6, 19, 14, 21)), ROW, (2, 9, 5, 11))
    assert comma_merge(t1, t2) == Temperament(
        ((4, -4, 1, 0), (6, -6, 0, 1)), COL, (2, 3, 5, 11)
    )
