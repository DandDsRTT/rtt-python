import pytest

from rtt.temperament import Variance


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
def test_variance_from_string(text, expected):
    assert Variance.from_string(text) == expected
