from rtt.web.editor import INITIAL_MAPPING, Editor


def test_editor_starts_at_meantone_with_no_undo():
    editor = Editor()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.state.comma_basis == ((4, -4, 1),)
    assert editor.can_undo is False


def test_edit_mapping_recomputes_and_enables_undo():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
    assert editor.can_undo is True


def test_undo_restores_previous_state():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.can_undo is False


def test_edit_comma_basis_recomputes_mapping():
    editor = Editor()
    editor.edit_comma_basis([[-4, 4, -1]])
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))


def test_expand_then_undo_round_trips_dimension():
    editor = Editor()
    editor.expand()
    assert editor.state.d == 4
    editor.undo()
    assert editor.state.d == 3


def test_shrink_then_undo_round_trips_dimension():
    editor = Editor()
    editor.shrink()
    assert editor.state.d == 2
    editor.undo()
    assert editor.state.d == 3


def test_undo_with_empty_stack_is_a_noop():
    editor = Editor()
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING


def test_cannot_shrink_below_one_dimension():
    editor = Editor()
    assert editor.can_shrink is True  # starts at d=3
    editor.shrink()
    editor.shrink()
    assert editor.state.d == 1
    assert editor.can_shrink is False
