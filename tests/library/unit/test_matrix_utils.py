from fractions import Fraction

import pytest

from rtt.library.matrix_utils import (
    all_zeros,
    get_largest_minors_l,
    hnf,
    inner_l_length,
    inverse,
    matrix_multiply,
    remove_all_zero_lists,
    remove_unneeded_zero_lists,
    reverse_inner_l,
    reverse_outer_l,
    rotate_180,
    smith_normal_form_with_transforms,
)


def _f(*pairs):
    return tuple(Fraction(n, d) for n, d in pairs)


class TestMatrixUtils:
    def test_inverse_matrix(self):
        assert inverse(((1, 2, 3), (4, 5, 0), (0, 0, 9))) == (
            _f((-5, 3), (2, 3), (5, 9)),
            _f((4, 3), (-1, 3), (-4, 9)),
            _f((0, 1), (0, 1), (1, 9)),
        )

    def test_inverse_vector(self):
        assert inverse((1, 2, 3)) == _f((1, 1), (1, 2), (1, 3))

    def test_inverse_scalar(self):
        assert inverse(3) == Fraction(1, 3)

    def test_reverse_inner_l(self):
        assert reverse_inner_l(((1, 0, -4), (0, 1, 4))) == ((-4, 0, 1), (4, 1, 0))

    def test_reverse_outer_l(self):
        assert reverse_outer_l(((1, 0, -4), (0, 1, 4))) == ((0, 1, 4), (1, 0, -4))

    def test_rotate_180(self):
        assert rotate_180(((1, 0, -4), (0, 1, 4))) == ((4, 1, 0), (-4, 0, 1))

    @pytest.mark.parametrize(
        "matrix, expected",
        [(((0, 0), (0, 0)), 2), (((0,), (0,)), 1), (((0, 0),), 2)],
    )
    def test_inner_l_length(self, matrix, expected):
        assert inner_l_length(matrix) == expected

    @pytest.mark.parametrize(
        "matrix, expected",
        [
            (((5, 8, 12), (7, 11, 16)), ((1, 0, -4), (0, 1, 4))),
            (((3, 0, -1), (0, 3, 5)), ((3, 0, -1), (0, 3, 5))),
            ((), ()),
        ],
    )
    def test_hnf(self, matrix, expected):
        assert hnf(matrix) == expected

    def test_get_largest_minors_l(self):
        assert get_largest_minors_l(((17, 16, -4), (4, -4, 1))) == (-4, 1, 0)

    def test_smith_normal_form_factors_a_matrix_into_left_diagonal_right(self):
        a = ((2, 0), (0, 3))
        left, diagonal, right = smith_normal_form_with_transforms(a)
        assert diagonal == ((1, 0), (-3, 6))
        assert matrix_multiply(matrix_multiply(left, a), right) == diagonal
        assert abs(diagonal[0][0]) == 1 and abs(diagonal[1][1]) == 6

    @pytest.mark.parametrize(
        "matrix, expected",
        [(((1, 0, -4), (0, 1, 4)), False), (((0, 0, 0), (0, 0, 0)), True)],
    )
    def test_all_zeros(self, matrix, expected):
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
    def test_remove_all_zero_lists(self, matrix, expected):
        assert remove_all_zero_lists(matrix) == expected

    @pytest.mark.parametrize(
        "matrix, expected",
        [
            (((1, 0, 0), (0, 0, 0), (1, 2, 3)), ((1, 0, 0), (1, 2, 3))),
            (((1, 0, 1), (0, 0, 2), (0, 0, 3)), ((1, 0, 1), (0, 0, 2), (0, 0, 3))),
            (((12, 19, 28), (24, 38, 56)), ((12, 19, 28), (24, 38, 56))),
            (((0, 0), (0, 0)), ((0, 0),)),
            ((), ()),
        ],
    )
    def test_remove_unneeded_zero_lists(self, matrix, expected):
        assert remove_unneeded_zero_lists(matrix) == expected
