import pytest

from rtt.dimensions import get_d, get_n, get_r
from rtt.parsing import parse_temperament_data

MEANTONE_M = "[⟨1 0 -4] ⟨0 1 4]}"
MEANTONE_C = "[4 -4 1⟩"


@pytest.mark.parametrize("ebk, expected", [(MEANTONE_M, 3), (MEANTONE_C, 3)])
def test_get_d(ebk, expected):
    assert get_d(parse_temperament_data(ebk)) == expected


@pytest.mark.parametrize("ebk, expected", [(MEANTONE_M, 2), (MEANTONE_C, 2)])
def test_get_r(ebk, expected):
    assert get_r(parse_temperament_data(ebk)) == expected


@pytest.mark.parametrize("ebk, expected", [(MEANTONE_M, 1), (MEANTONE_C, 1)])
def test_get_n(ebk, expected):
    assert get_n(parse_temperament_data(ebk)) == expected
