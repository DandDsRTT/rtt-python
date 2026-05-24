"""Editor view-model contract tests.

Behavioral scenarios (expand/shrink/change/undo) are covered by
test_web_integration.py; here we pin the Editor's own state-machine contract:
the initial state, undo availability, and the shrink guard.
"""

from rtt.web import service
from rtt.web.editor import INITIAL_MAPPING, Editor


def test_editor_starts_at_meantone_with_no_undo():
    editor = Editor()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.state.comma_basis == ((4, -4, 1),)
    assert editor.can_undo is False
    assert editor.can_redo is False


def test_an_edit_enables_undo():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    assert editor.can_undo is True


def test_redo_restores_an_undone_action():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    edited = editor.state.mapping
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.can_redo is True
    editor.redo()
    assert editor.state.mapping == edited
    assert editor.can_redo is False


def test_a_fresh_edit_clears_the_redo_history():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.can_redo is True
    editor.edit_mapping([[1, 1, 0], [0, 1, 5]])  # a new action invalidates redo
    assert editor.can_redo is False


def test_undo_with_empty_stack_is_a_noop():
    editor = Editor()
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING


def test_add_comma_then_remove_comma_round_trips_through_undo_state():
    editor = Editor()
    assert editor.state.comma_basis == ((4, -4, 1),)
    editor.add_comma()
    assert editor.state.comma_basis == ((4, -4, 1), (0, 0, 0))  # a blank comma to fill
    assert editor.can_undo is True  # the add is undoable
    editor.remove_comma()
    assert editor.state.comma_basis == ((4, -4, 1),)


def test_cannot_remove_the_sole_comma():
    editor = Editor()  # meantone exposes a single comma
    assert editor.can_remove_comma is False  # removing it would empty the basis
    editor.add_comma()
    assert editor.can_remove_comma is True  # ...but with two, the last can go


def test_editor_starts_with_default_tuning_scheme_and_target_spec():
    editor = Editor()
    assert editor.tuning_scheme == service.DEFAULT_TUNING_SCHEME
    assert editor.target_spec == "TILT"


def test_selecting_a_tuning_scheme_and_target_spec_updates_them():
    editor = Editor()
    editor.set_tuning_scheme("POTE")
    editor.set_target_spec("OLD")
    assert editor.tuning_scheme == "POTE"
    assert editor.target_spec == "OLD"


def test_scheme_and_target_spec_are_view_selections_outside_undo():
    # they are display/analysis choices, not temperament edits, so they neither
    # push onto the undo stack nor get reverted by undoing a temperament change
    editor = Editor()
    editor.set_tuning_scheme("CTE")
    assert editor.can_undo is False  # selecting a scheme is not an undoable edit
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.tuning_scheme == "CTE"  # undo reverts the mapping, not the scheme


def test_cannot_shrink_below_one_dimension():
    editor = Editor()
    assert editor.can_shrink is True  # starts at d=3
    editor.shrink()
    editor.shrink()
    assert editor.state.d == 1
    assert editor.can_shrink is False


def test_interest_intervals_add_edit_remove():
    editor = Editor()
    assert editor.interest_monzos == []  # starts empty
    editor.add_interest()
    assert editor.interest_monzos == [(0, 0, 0)]  # a blank 1/1 (zero monzo) at the current d
    editor.set_interest_monzos([[-1, 1, 0], [0, 0, 0]])  # edit it to 3/2 and add a second
    assert editor.interest_monzos == [(-1, 1, 0), (0, 0, 0)]
    editor.remove_interest(1)
    assert editor.interest_monzos == [(-1, 1, 0)]


def test_interest_intervals_are_view_data_outside_undo():
    # like the tuning/target selections, the interest set is curated display data,
    # not a temperament edit: editing it does not push undo, and undoing a temperament
    # change leaves it untouched
    editor = Editor()
    editor.add_interest()
    assert editor.can_undo is False  # adding an interval of interest is not undoable
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.interest_monzos == [(0, 0, 0)]  # the undo reverts the mapping, not the set
