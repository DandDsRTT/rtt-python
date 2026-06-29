from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


class TestMoveInterval:
    def test_move_interval_reorders_within_a_list_with_a_single_undo(self):
        editor = Editor()
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])
        assert editor.move_interval("held", 0, "held", 2) is True
        assert editor.held_vectors == [(-1, 1, 0), (2, 0, -1), (1, 0, 0)]
        editor.undo()
        assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0), (2, 0, -1)]

    def test_move_interval_carries_a_vector_between_two_lists(self):
        editor = Editor()
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])
        editor.set_interest_vectors([[2, 0, -1]])
        assert editor.move_interval("held", 0, "interest", 1) is True
        assert editor.held_vectors == [(-1, 1, 0)]
        assert editor.interest_vectors == [(2, 0, -1), (1, 0, 0)]
        editor.undo()
        assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]
        assert editor.interest_vectors == [(2, 0, -1)]

    def test_move_interval_into_commas_preserves_a_nonstandard_domain(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        editor.interest_vectors = [(0, 0, 1)]
        assert editor.move_interval("interest", 0, "commas", 1) is True
        assert editor.state.n == 2
        assert editor.state.domain_basis == (2, 3, Fraction(13, 5))

    def test_within_list_reorder_keeps_the_moved_columns_cell_id_for_the_glide(self):
        editor = Editor()
        editor.settings["optimization"] = True
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])
        lay1 = editor.layout()
        cells1 = {c.id: c for c in lay1.cells}
        front_x = cells1["cell:held:0:0"].x
        editor.move_interval("held", 2, "held", 0)
        cells2 = {c.id: c for c in editor.layout(prev_ids=lay1.identities).cells}
        assert "cell:held:0:2" in cells2
        assert cells2["cell:held:0:2"].x == front_x
        assert cells2["cell:held:0:2"].text == cells1["cell:held:0:2"].text

    def test_dropping_a_column_on_its_neighbour_swaps_them(self):
        editor = Editor()
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])
        assert editor.move_interval("held", 0, "held", 1) is True
        assert editor.held_vectors == [(-1, 1, 0), (1, 0, 0), (2, 0, -1)]

    def test_dropping_a_column_on_itself_is_a_no_op(self):
        editor = Editor()
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])
        assert editor.move_interval("held", 1, "held", 1) is False
        assert editor.move_interval("held", 0, "held", 0) is False
        editor.undo()
        assert editor.held_vectors == []

    def test_unchanged_interval_drags_out_as_a_copy(self):
        editor = Editor()
        u_known = editor.list_vectors("unchanged")
        assert u_known and u_known[0] is not None
        u0 = u_known[0]
        assert editor.move_interval("unchanged", 0, "interest", 0) is True
        assert tuple(editor.interest_vectors[0]) == u0
        assert editor.list_vectors("unchanged")[0] == u0, "…and U keeps it (derived — not removed)"
        assert editor.move_interval("interest", 0, "unchanged", 0) is False

    def test_move_a_target_into_held_converts_the_ratio_and_materializes_the_override(self):
        editor = Editor()
        targets = service.target_interval_set(editor.target_spec, editor.state.domain_basis)
        first = service.interval_vector(targets[0], editor.state.d, editor.state.domain_basis)
        assert editor.move_interval("targets", 0, "held", 0) is True
        assert editor.held_vectors == [first]
        assert editor.target_override is not None and len(editor.target_override) == len(targets) - 1
        assert targets[0] not in editor.target_override

    def test_move_a_held_interval_into_commas_tempers_it_out_and_reranks(self):
        editor = Editor()
        editor.set_held_vectors([[4, -5, 1]])
        editor.add_interest()
        assert editor.pending_interest is not None
        assert editor.move_interval("held", 0, "commas", 0) is True
        assert (editor.state.r, editor.state.n) == (1, 2)
        assert len(editor.state.comma_basis) == 2 and editor.held_vectors == []
        assert editor.pending_interest is None
        editor.undo()
        assert (editor.state.r, editor.state.n) == (2, 1) and editor.held_vectors == [(4, -5, 1)]

    def test_moving_a_dependent_interval_into_commas_is_rejected(self):
        editor = Editor()
        editor.set_held_vectors([[8, -8, 2]])
        before = editor.state.comma_basis
        assert editor.move_interval("held", 0, "commas", 0) is False
        assert editor.state.comma_basis == before and editor.held_vectors == [(8, -8, 2)]
        editor.undo()
        assert editor.held_vectors == []

    def test_move_a_comma_out_to_a_list_untempers_it_using_its_pre_removal_vector(self):
        editor = Editor()
        editor.edit_comma_basis([[4, -4, 1], [4, -5, 1]])
        vector = editor.state.comma_basis[-1]
        assert editor.move_interval("commas", len(editor.state.comma_basis) - 1, "interest", 0) is True
        assert (editor.state.r, editor.state.n) == (2, 1), "un-tempering it dropped the nullity"
        assert editor.interest_vectors == [vector]

    def test_dragging_out_the_sole_comma_un_tempers_it_to_just_intonation(self):
        editor = Editor()
        assert editor.move_interval("commas", 0, "held", 0) is True
        assert editor.state.n == 0
        assert editor.held_vectors == [(4, -4, 1)]

    def test_dragging_a_comma_out_is_blocked_with_nothing_tempered(self):
        editor = Editor()
        editor.remove_comma()
        assert editor.move_interval("commas", 0, "held", 0) is False
        assert editor.held_vectors == []

    def test_targets_are_inert_in_all_interval_mode(self):
        editor = Editor()
        editor.set_all_interval(True)
        assert service.is_all_interval(editor.tuning_scheme)
        editor.set_held_vectors([[1, 0, 0]])
        assert editor.move_interval("held", 0, "targets", 0) is False
        assert editor.held_vectors == [(1, 0, 0)]

    def test_reordering_targets_materializes_the_spec_into_an_override(self):
        editor = Editor()
        assert editor.target_override is None
        orig = service.target_interval_set(editor.target_spec, editor.state.domain_basis)
        assert editor.move_interval("targets", 0, "targets", len(orig)) is True
        assert editor.target_override is not None and len(editor.target_override) == len(orig)
        assert editor.target_override[-1] == orig[0] and editor.target_override[0] == orig[1]
