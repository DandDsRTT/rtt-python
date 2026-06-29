from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


class TestCommaDrafts:
    def test_add_comma_starts_a_blank_pending_draft_without_touching_the_temperament(self):
        editor = Editor()
        assert editor.pending_comma is None
        editor.add_comma()
        assert editor.pending_comma == [None, None, None]
        assert editor.state.comma_basis == ((4, -4, 1),)
        assert editor.state.r == 2
        assert editor.can_undo is False, "...and starting a draft is not an undoable edit"

    def test_add_comma_to_recombines_the_comma_basis_undoably(self):
        editor = Editor()
        editor.edit_mapping(((12, 19, 28),))
        before = editor.state.comma_basis
        editor.add_comma_to(0, 1)
        assert editor.state.comma_basis[1] == tuple(a + b for a, b in zip(before[1], before[0]))
        assert editor.state.mapping == ((12, 19, 28),)
        editor.undo()
        assert editor.state.comma_basis == before

    def test_add_comma_to_ignores_a_comma_dropped_on_itself(self):
        editor = Editor()
        editor.edit_mapping(((12, 19, 28),))
        before = editor.state.comma_basis
        steps = editor.undo_count
        editor.add_comma_to(0, 0)
        assert editor.state.comma_basis == before
        assert editor.undo_count == steps

    def test_filling_the_pending_comma_with_an_independent_comma_commits_and_reranks(self):
        editor = Editor()
        editor.add_comma()
        editor.set_pending_comma([4, -5, 1])
        assert editor.pending_comma is None
        assert editor.state.comma_basis == ((4, -4, 1), (4, -5, 1))
        assert (editor.state.r, editor.state.n) == (1, 2)
        assert editor.can_undo is True

    def test_incomplete_or_dependent_pending_comma_is_held_not_committed(self):
        editor = Editor()
        editor.add_comma()
        editor.set_pending_comma([4, None, 1])
        assert editor.pending_comma == [4, None, 1] and editor.state.r == 2
        editor.set_pending_comma([8, -8, 2])
        assert editor.pending_comma == [8, -8, 2] and editor.state.r == 2, "not a new comma -> held"

    def test_cancelling_a_pending_comma_discards_the_draft(self):
        editor = Editor()
        editor.add_comma()
        assert editor.pending_comma is not None
        editor.cancel_pending_comma()
        assert editor.pending_comma is None
        assert editor.state.comma_basis == ((4, -4, 1),), "the real comma untouched — the draft went, not it"
        assert editor.can_undo is False, "cancelling a draft is not an undoable edit"

    def test_removing_a_real_comma_drops_the_last_by_default(self):
        editor = Editor()
        editor.add_comma()
        editor.set_pending_comma([4, -5, 1])
        assert editor.pending_comma is None and len(editor.state.comma_basis) == 2
        editor.remove_comma()
        assert editor.state.comma_basis == ((4, -4, 1),)
        assert editor.state.r == 2

    def test_removing_a_comma_can_target_any_index_not_only_the_last(self):
        editor = Editor()
        editor.add_comma()
        editor.set_pending_comma([4, -5, 1])
        two = editor.state
        assert len(two.comma_basis) == 2 and two.r == 1
        editor.remove_comma(0)
        assert editor.state.n == 1 and editor.state.r == 2, "one comma un-tempered"
        assert editor.state == service.remove_comma(two, 0)
        assert editor.state != service.remove_comma(two, -1)
        editor.undo()
        assert editor.state == two

    def test_remove_comma_un_tempers_the_last_comma_to_just_intonation(self):
        editor = Editor()
        editor.remove_comma()
        assert (editor.state.d, editor.state.r, editor.state.n) == (3, 3, 0)
        assert editor.state.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        editor.undo()
        assert editor.state.comma_basis == ((4, -4, 1),)

    def test_remove_comma_is_a_noop_with_nothing_tempered(self):
        editor = Editor()
        editor.remove_comma()
        assert editor.state.n == 0
        editor.remove_comma()
        assert editor.state.n == 0 and editor.can_undo is True

    def test_first_comma_from_just_intonation_commits_no_phantom_unison(self):
        editor = Editor()
        editor.remove_comma()
        editor.add_comma()
        editor.set_pending_comma([4, -4, 1])
        assert editor.state.comma_basis == ((4, -4, 1),) and editor.state.n == 1
        editor2 = Editor()
        editor2.remove_comma()
        editor2.move_interval("targets", 0, "commas", 0)
        assert (0, 0, 0) not in editor2.state.comma_basis and editor2.state.n == 1


class TestMappingRowDrafts:
    def test_add_mapping_row_to_combines_rows_as_one_undoable_step(self):
        editor = Editor()
        commas = editor.state.comma_basis
        editor.add_mapping_row_to(0, 1)
        assert editor.state.mapping == ((1, 1, 0), (1, 2, 4))
        assert editor.state.comma_basis == commas
        editor.undo()
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))

    def test_add_mapping_row_starts_a_blank_pending_draft_row_without_touching_the_temperament(self):
        editor = Editor()
        assert editor.pending_mapping_row is None
        editor.add_mapping_row()
        assert editor.pending_mapping_row == [None, None, None]
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))
        assert (editor.state.r, editor.state.n) == (2, 1)
        assert editor.can_undo is False, "...and starting a draft is not undoable"

    def test_add_mapping_row_opens_no_draft_at_full_rank(self):
        editor = Editor()
        editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert editor.can_add_mapping_row is False
        editor.add_mapping_row()
        assert editor.pending_mapping_row is None

    def test_add_mapping_row_to_preserves_a_frozen_tuning(self):
        editor = Editor()
        editor.set_generator_tuning_text("{1200.000 700.000]")
        before = service.tuning_from_generators(editor.state.mapping, editor.effective_generator_tuning())
        editor.add_mapping_row_to(0, 1)
        assert editor.effective_generator_tuning() == (500.0, 700.0)
        after = service.tuning_from_generators(editor.state.mapping, editor.effective_generator_tuning())
        assert tuple(round(x, 6) for x in after.tuning_map) == tuple(round(x, 6) for x in before.tuning_map)

    def test_add_mapping_row_to_ignores_a_row_dropped_on_itself(self):
        editor = Editor()
        editor.add_mapping_row_to(1, 1)
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))
        assert editor.can_undo is False, "and not an undoable step"

    def test_filling_the_pending_mapping_row_with_an_independent_generator_commits_and_reranks(self):
        editor = Editor()
        editor.add_mapping_row()
        editor.set_pending_mapping_row([0, 0, 1])
        assert editor.pending_mapping_row is None
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4), (0, 0, 1))
        assert (editor.state.r, editor.state.n) == (3, 0)
        assert editor.can_undo is True
        editor.undo()
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))

    def test_incomplete_or_dependent_pending_mapping_row_is_held_not_committed(self):
        editor = Editor()
        editor.add_mapping_row()
        editor.set_pending_mapping_row([0, 0, None])
        assert editor.pending_mapping_row == [0, 0, None] and editor.state.r == 2
        editor.set_pending_mapping_row([2, 2, 0])
        assert editor.pending_mapping_row == [2, 2, 0] and editor.state.r == 2, "held, not committed"

    def test_cancel_pending_mapping_row_discards_the_draft(self):
        editor = Editor()
        editor.add_mapping_row()
        editor.set_pending_mapping_row([0, 0, None])
        editor.cancel_pending_mapping_row()
        assert editor.pending_mapping_row is None
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))
        assert editor.can_undo is False, "cancelling a never-committed draft is not undoable"

    def test_a_temperament_edit_clears_a_pending_mapping_row_draft(self):
        editor = Editor()
        editor.add_mapping_row()
        editor.edit_comma_basis(((4, -4, 1),))
        assert editor.pending_mapping_row is None

    def test_add_remove_mapping_row_change_rank_holding_dimensionality(self):
        editor = Editor()
        editor.remove_mapping_row(0)
        assert (editor.state.r, editor.state.d, editor.state.n) == (1, 3, 2)
        editor.add_mapping_row()
        assert editor.pending_mapping_row == [None, None, None], "a draft, not yet committed"
        assert (editor.state.r, editor.state.d, editor.state.n) == (1, 3, 2)
        editor.set_pending_mapping_row([1, 1, 0])
        assert editor.pending_mapping_row is None
        assert (editor.state.r, editor.state.d, editor.state.n) == (2, 3, 1)
        editor.undo()
        assert editor.state.r == 1


class TestDraftExclusivity:
    def test_opening_a_draft_discards_any_other_pending_draft(self):
        editor = Editor()
        editor.add_comma()
        assert editor.pending_comma is not None
        editor.add_interest()
        assert editor.pending_comma is None and editor.pending_interest is not None
        editor.add_held()
        assert editor.pending_interest is None and editor.pending_held is not None
        editor.add_target()
        assert editor.pending_held is None and editor.pending_target is not None
        editor.add_element()
        assert editor.pending_target is None and editor.pending_element is not None
        editor.add_comma()
        assert editor.pending_element is None and editor.pending_comma is not None

    def test_comma_and_mapping_row_drafts_cannot_coexist(self):
        editor = Editor()
        editor.state = service.from_mapping(((12, 19, 28),))
        editor.add_comma()
        editor.set_pending_comma([4, -4, None])
        editor.add_mapping_row()
        assert editor.pending_comma is None
        assert editor.pending_mapping_row is not None
        editor.set_pending_mapping_row([1, 0, None])
        editor.add_comma()
        assert editor.pending_mapping_row is None
        assert editor.pending_comma is not None

    def test_comma_and_element_drafts_cannot_coexist(self):
        editor = Editor()
        editor.state = service.from_mapping(((12, 19, 28),))
        editor.add_comma()
        editor.set_pending_comma([4, -4, None])
        editor.add_element()
        assert editor.pending_comma is None
        editor.set_pending_element("7")
        assert editor.state.d == 4

    def test_set_pending_comma_preserves_a_nonstandard_domain(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        editor.add_comma()
        editor.set_pending_comma([0, 0, 1])
        assert editor.pending_comma is None
        assert editor.state.n == 2
        assert editor.state.domain_basis == (2, 3, Fraction(13, 5))


class TestIntervalListDrafts:
    def test_add_interest_to_combines_two_intervals_of_interest_undoably(self):
        editor = Editor()
        editor.set_interest_vectors([(-1, 1, 0), (0, 0, 1)])
        editor.add_interest_to(0, 1)
        assert editor.interest_vectors == [(-1, 1, 0), (-1, 1, 1)]
        editor.undo()
        assert editor.interest_vectors == [(-1, 1, 0), (0, 0, 1)]

    def test_add_held_to_combines_two_held_intervals_undoably(self):
        editor = Editor()
        editor.set_held_vectors([(1, 0, 0), (-1, 1, 0)])
        editor.add_held_to(0, 1)
        assert editor.held_vectors == [(1, 0, 0), (0, 1, 0)]
        editor.undo()
        assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]

    def test_add_target_to_multiplies_two_targets_materializing_the_override(self):
        editor = Editor()
        editor.set_target_override_vectors([(-1, 1, 0), (-2, 0, 1)])
        editor.add_target_to(0, 1)
        assert editor.target_override == ("3/2", "15/8")
        editor.undo()
        assert editor.target_override == ("3/2", "5/4")

    def test_interval_drag_add_ignores_a_drop_on_itself(self):
        editor = Editor()
        editor.set_interest_vectors([(1, 0, 0), (0, 1, 0)])
        steps = editor.undo_count
        editor.add_interest_to(1, 1)
        assert editor.interest_vectors == [(1, 0, 0), (0, 1, 0)]
        assert editor.undo_count == steps

    def test_adding_a_target_starts_a_blank_pending_draft(self):
        editor = Editor()
        assert editor.pending_target is None
        editor.add_target()
        assert editor.pending_target == [None, None, None]
        assert editor.target_override is None, "not committed (the spec set is untouched)"
        assert editor.can_undo is False, "starting a draft is not an undoable edit"

    def test_a_partly_filled_target_draft_is_held_until_complete(self):
        editor = Editor()
        n = len(service.target_interval_set(editor.target_spec, editor.state.domain_basis))
        editor.add_target()
        editor.set_pending_target([-1, None, 0])
        assert editor.pending_target == [-1, None, 0] and editor.target_override is None
        editor.set_pending_target([-1, 1, 0])
        assert editor.pending_target is None and editor.target_override[-1] == "3/2"
        assert len(editor.target_override) == n + 1
        assert editor.can_undo is True

    def test_a_partly_filled_interest_draft_is_held_until_complete(self):
        editor = Editor()
        editor.add_interest()
        editor.set_pending_interest([-1, None, 0])
        assert editor.pending_interest == [-1, None, 0] and editor.interest_vectors == []
        editor.set_pending_interest([-1, 1, 0])
        assert editor.pending_interest is None and editor.interest_vectors == [(-1, 1, 0)]
        assert editor.can_undo is True

    def test_a_partly_filled_held_draft_is_held_until_complete(self):
        editor = Editor()
        editor.add_held()
        editor.set_pending_held([1, None, 0])
        assert editor.pending_held == [1, None, 0] and editor.held_vectors == []
        editor.set_pending_held([1, 0, 0])
        assert editor.pending_held is None and editor.held_vectors == [(1, 0, 0)]
        assert editor.can_undo is True

    def test_cancelling_a_target_draft_discards_it(self):
        editor = Editor()
        editor.add_target()
        editor.cancel_pending_target()
        assert editor.pending_target is None and editor.target_override is None
        assert editor.can_undo is False, "cancelling a draft is not an undoable edit"

    def test_interest_intervals_add_edit_remove(self):
        editor = Editor()
        assert editor.interest_vectors == []
        editor.add_interest()
        assert editor.interest_vectors == []
        assert editor.pending_interest == [None, None, None]
        editor.set_pending_interest([-1, 1, 0])
        assert editor.interest_vectors == [(-1, 1, 0)] and editor.pending_interest is None
        editor.set_interest_vectors([[-1, 1, 0], [2, 0, -1]])
        assert editor.interest_vectors == [(-1, 1, 0), (2, 0, -1)]
        editor.remove_interest(0)
        assert editor.interest_vectors == [(2, 0, -1)]

    def test_interest_intervals_changes_are_undoable(self):
        editor = Editor()
        editor.add_interest()
        assert editor.can_undo is False, "starting the blank draft is not undoable"
        editor.set_pending_interest([-1, 1, 0])
        assert editor.can_undo is True
        editor.undo()
        assert editor.interest_vectors == []

    def test_adding_an_interval_of_interest_starts_a_blank_pending_draft(self):
        editor = Editor()
        assert editor.pending_interest is None
        editor.add_interest()
        assert editor.pending_interest == [None, None, None]
        assert editor.interest_vectors == [], "not committed"
        assert editor.can_undo is False, "starting a draft is not an undoable edit"

    def test_cancelling_an_interval_of_interest_draft_discards_it(self):
        editor = Editor()
        editor.add_interest()
        editor.cancel_pending_interest()
        assert editor.pending_interest is None and editor.interest_vectors == []
        assert editor.can_undo is False, "cancelling a draft is not an undoable edit"

    def test_held_intervals_add_edit_remove(self):
        editor = Editor()
        assert editor.held_vectors == []
        editor.add_held()
        assert editor.held_vectors == []
        assert editor.pending_held == [None, None, None]
        editor.set_pending_held([1, 0, 0])
        assert editor.held_vectors == [(1, 0, 0)] and editor.pending_held is None
        editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])
        assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]
        editor.remove_held(0)
        assert editor.held_vectors == [(-1, 1, 0)]

    def test_adding_a_held_interval_starts_a_blank_pending_draft(self):
        editor = Editor()
        assert editor.pending_held is None
        editor.add_held()
        assert editor.pending_held == [None, None, None]
        assert editor.held_vectors == [], "not committed"
        assert editor.can_undo is False, "starting a draft is not an undoable edit"

    def test_cancelling_a_held_interval_draft_discards_it(self):
        editor = Editor()
        editor.add_held()
        editor.cancel_pending_held()
        assert editor.pending_held is None and editor.held_vectors == []
        assert editor.can_undo is False, "cancelling a draft is not an undoable edit"
