import pytest

from rtt.matrix_utils import (
    all_zeros,
    get_largest_minors_l,
    hnf,
    inner_l_length,
    remove_all_zero_lists,
    remove_unneeded_zero_lists,
    reverse_inner_l,
    reverse_outer_l,
    rotate_180,
)


def test_reverse_inner_l():
    assert reverse_inner_l(((1, 0, -4), (0, 1, 4))) == ((-4, 0, 1), (4, 1, 0))


def test_reverse_outer_l():
    assert reverse_outer_l(((1, 0, -4), (0, 1, 4))) == ((0, 1, 4), (1, 0, -4))


def test_rotate_180():
    assert rotate_180(((1, 0, -4), (0, 1, 4))) == ((4, 1, 0), (-4, 0, 1))


@pytest.mark.parametrize(
    "matrix, expected",
    [(((0, 0), (0, 0)), 2), (((0,), (0,)), 1), (((0, 0),), 2)],
)
def test_inner_l_length(matrix, expected):
    assert inner_l_length(matrix) == expected


@pytest.mark.parametrize(
    "matrix, expected",
    [
        (((5, 8, 12), (7, 11, 16)), ((1, 0, -4), (0, 1, 4))),
        (((3, 0, -1), (0, 3, 5)), ((3, 0, -1), (0, 3, 5))),
    ],
)
def test_hnf(matrix, expected):
    assert hnf(matrix) == expected


def test_get_largest_minors_l():
    assert get_largest_minors_l(((17, 16, -4), (4, -4, 1))) == (-4, 1, 0)


@pytest.mark.parametrize(
    "matrix, expected",
    [(((1, 0, -4), (0, 1, 4)), False), (((0, 0, 0), (0, 0, 0)), True)],
)
def test_all_zeros(matrix, expected):
    assert all_zeros(matrix) == expected


@pytest.mark.parametrize(
    "matrix, expected",
    [
        (((1, 0, 0), (0, 0, 0), (1, 2, 3)), ((1, 0, 0), (1, 2, 3))),
        (((1, 0, 1), (0, 0, 2), (0, 0, 3)), ((1, 0, 1), (0, 0, 2), (0, 0, 3))),
        (((12, 19, 28), (24, 38, 56)), ((12, 19, 28), (24, 38, 56))),
        (((0, 0), (0, 0)), ()),
    ],
)
def test_remove_all_zero_lists(matrix, expected):
    assert remove_all_zero_lists(matrix) == expected


@pytest.mark.parametrize(
    "matrix, expected",
    [
        (((1, 0, 0), (0, 0, 0), (1, 2, 3)), ((1, 0, 0), (1, 2, 3))),
        (((1, 0, 1), (0, 0, 2), (0, 0, 3)), ((1, 0, 1), (0, 0, 2), (0, 0, 3))),
        (((12, 19, 28), (24, 38, 56)), ((12, 19, 28), (24, 38, 56))),
        (((0, 0), (0, 0)), ((0, 0),)),
    ],
)
def test_remove_unneeded_zero_lists(matrix, expected):
    assert remove_unneeded_zero_lists(matrix) == expected
