from rtt.app import editor_predicates as ep
from rtt.app import service
from rtt.app.editor import Editor
from rtt.app.editor_solve import solve_model


class TestWebEditorPredicates:
    def test_structure_predicates_are_pure_functions_of_state(self):
        standard = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert ep.can_expand(standard) is True
        assert ep.basis_is_nonstandard(standard) is False
        assert ep.can_add_mapping_row(standard) is True
        assert ep.can_remove_mapping_row(standard) is True
        nonstandard = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert ep.can_expand(nonstandard) is False
        assert ep.basis_is_nonstandard(nonstandard) is True
        rank_one = service.from_mapping([[1, 1, 0]])
        assert ep.can_remove_mapping_row(rank_one) is False

    def test_valid_domain_basis_accepts_a_standard_prime_limit(self):
        assert ep.valid_domain_basis(service.from_mapping([[1, 1, 0], [0, 1, 4]])) is True

    def test_list_vectors_reads_each_named_collection_off_the_read_model(self):
        editor = Editor()
        editor.set_held_vectors([(-1, 1, 0)])
        editor.set_interest_vectors([(2, 0, -1)])
        s = solve_model(editor)
        assert ep.list_vectors(s, "held") == [(-1, 1, 0)]
        assert ep.list_vectors(s, "interest") == [(2, 0, -1)]
        assert ep.list_vectors(s, "commas") == [tuple(v) for v in editor.state.comma_basis]

    def test_peek_vector_returns_none_out_of_bounds(self):
        assert ep.peek_vector([(1, 0)], 0) == (1, 0)
        assert ep.peek_vector([(1, 0)], 5) is None
        assert ep.peek_vector([], 0) is None

    def test_move_feasible_blocks_into_unchanged_and_allows_a_plain_move(self):
        s = solve_model(Editor())
        assert ep.move_feasible(s, "held", "unchanged", (1, 0, 0)) is False
        assert ep.move_feasible(s, "interest", "held", (1, 0, 0)) is True
