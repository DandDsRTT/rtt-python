import pytest

from rtt.library.temperament import Variance


class TestTemperament:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("row", Variance.ROW),
            ("col", Variance.COL),
            ("comma basis", Variance.COL),
            ("mapping", Variance.ROW),
            ("comma", Variance.COL),
            ("map", Variance.ROW),
            ("vector", Variance.COL),
            ("covariant", Variance.ROW),
            ("contravariant", Variance.COL),
        ],
    )
    def test_variance_from_string(self, text, expected):
        assert Variance.from_string(text) == expected

    def test_variance_from_string_rejects_an_unrecognized_word(self):
        with pytest.raises(ValueError, match="Unrecognized variance"):
            Variance.from_string("sideways")
