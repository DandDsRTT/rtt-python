import math

from rtt.app.editor_state import (
    INITIAL_MAPPING,
    initial_doc,
    prescaler_is_solvable,
    weights_are_solvable,
)


class TestWebEditorState:
    def test_diagonal_prescaler_is_solvable_when_every_entry_is_positive_and_finite(self):
        assert prescaler_is_solvable((1.0, 2.0, 3.0))

    def test_diagonal_prescaler_is_unsolvable_with_a_nonpositive_entry(self):
        assert not prescaler_is_solvable((1.0, 0.0, 3.0))
        assert not prescaler_is_solvable((1.0, -2.0, 3.0))

    def test_diagonal_prescaler_is_unsolvable_with_a_nonfinite_entry(self):
        assert not prescaler_is_solvable((1.0, math.inf, 3.0))

    def test_empty_prescaler_is_unsolvable(self):
        assert not prescaler_is_solvable(())
        assert not prescaler_is_solvable(None)

    def test_matrix_prescaler_requires_a_positive_diagonal_but_allows_zero_offdiagonal(self):
        assert prescaler_is_solvable(((1.0, 0.0), (0.0, 2.0)))
        assert not prescaler_is_solvable(((0.0, 0.0), (0.0, 2.0)))

    def test_matrix_prescaler_is_unsolvable_with_a_nonfinite_offdiagonal(self):
        assert not prescaler_is_solvable(((1.0, math.inf), (0.0, 2.0)))

    def test_weights_are_solvable_only_when_all_positive_and_finite(self):
        assert weights_are_solvable((1.0, 2.0))
        assert not weights_are_solvable((1.0, 0.0))
        assert not weights_are_solvable((1.0, -1.0))
        assert not weights_are_solvable((1.0, math.nan))
        assert not weights_are_solvable(())

    def test_initial_doc_is_a_cached_singleton(self):
        assert initial_doc() is initial_doc()

    def test_initial_doc_carries_the_initial_mapping(self):
        assert initial_doc().state.mapping == INITIAL_MAPPING
