"""Editor view-model contract tests.

Behavioral scenarios (expand/shrink/change/undo) are covered by
test_web_integration.py; here we pin the Editor's own state-machine contract:
the initial state, undo availability, and the shrink guard.
"""

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


def test_cannot_shrink_below_one_dimension():
    editor = Editor()
    assert editor.can_shrink is True  # starts at d=3
    editor.shrink()
    editor.shrink()
    assert editor.state.d == 1
    assert editor.can_shrink is False
