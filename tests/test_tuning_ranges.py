import pytest

from rtt.temperament import Temperament, Variance
from rtt.tuning_ranges import get_generator_tuning_range

MEANTONE = Temperament(((1, 1, 0), (0, 1, 4)), Variance.ROW)


def test_diamond_tradeoff_meantone_fifth_range():
    # Octave held pure pins the period generator; the fifth generator ranges
    # over the diamond-tradeoff tunings, from pure-6/5 (694.786) at the low end
    # up to pure-3/2 (701.955) at the high end.
    ranges = get_generator_tuning_range(MEANTONE, "tradeoff")
    assert ranges[1] == pytest.approx((694.786, 701.955), abs=1e-2)


def test_diamond_monotone_meantone_fifth_range():
    # The fifth keeps the diamond intervals in their JI order across a wider span
    # than the tradeoff range: the whole 5edo (685.714) to 7edo (720.0) corridor.
    ranges = get_generator_tuning_range(MEANTONE, "monotone")
    assert ranges[1] == pytest.approx((685.714, 720.0), abs=1e-2)


def test_octave_generator_is_pinned_pure_in_both_modes():
    # The normalization holds 2/1 pure, so the period (octave) generator collapses
    # to a single point at 1200 cents in either mode -- only the fifth has a range.
    for mode in ("monotone", "tradeoff"):
        ranges = get_generator_tuning_range(MEANTONE, mode)
        assert ranges[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)
