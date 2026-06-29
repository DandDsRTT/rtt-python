import pytest

from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning_ranges import get_generator_tuning_range

MEANTONE = Temperament(((1, 1, 0), (0, 1, 4)), Variance.ROW)


class TestTuningRanges:
    def test_diamond_tradeoff_meantone_fifth_range(self):
        ranges = get_generator_tuning_range(MEANTONE, "tradeoff")
        assert ranges[1] == pytest.approx((694.786, 701.955), abs=1e-2)

    def test_diamond_monotone_meantone_fifth_range(self):
        ranges = get_generator_tuning_range(MEANTONE, "monotone")
        assert ranges[1] == pytest.approx((685.714, 720.0), abs=1e-2)

    def test_monotone_range_is_none_when_no_monotone_tuning_exists(self):
        t = Temperament(((1, 1),), Variance.ROW)
        assert get_generator_tuning_range(t, "monotone") is None
        tradeoff = get_generator_tuning_range(t, "tradeoff")
        assert tradeoff[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)

    def test_tradeoff_range_is_none_when_the_octave_tempers_out(self):
        t = Temperament(((0, 1, 4),), Variance.ROW)
        assert get_generator_tuning_range(t, "tradeoff") is None

    def test_unknown_range_mode_is_rejected(self):
        with pytest.raises(ValueError, match="unknown mode"):
            get_generator_tuning_range(MEANTONE, "tradoff")

    def test_octave_generator_is_pinned_pure_in_both_modes(self):
        for mode in ("monotone", "tradeoff"):
            ranges = get_generator_tuning_range(MEANTONE, mode)
            assert ranges[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)
