from rtt.app.editor import Editor

DEFAULT_MEANTONE = ((1, 1, 0), (0, 1, 4))
CANONICAL_MEANTONE = ((1, 0, -4), (0, 1, 4))


class TestFormSelectionUndo:
    def test_reselecting_the_same_form_is_not_an_undoable_edit(self):
        editor = Editor()
        editor.set_mapping_form("canonical")
        assert editor.state.mapping == CANONICAL_MEANTONE
        steps = editor.undo_count
        editor.set_mapping_form("canonical")
        assert editor.undo_count == steps
        assert editor.state.mapping == CANONICAL_MEANTONE
        assert editor.preferred_form.get("mapping") == "canonical"

    def test_switching_to_a_form_that_agrees_on_the_matrix_still_records_the_selection(self):
        editor = Editor()
        editor.set_mapping_form("canonical")
        steps = editor.undo_count
        editor.set_mapping_form("positive-generator")
        assert editor.state.mapping == CANONICAL_MEANTONE
        assert editor.undo_count == steps + 1
        assert editor.preferred_form.get("mapping") == "positive-generator"
        editor.undo()
        assert editor.preferred_form.get("mapping") == "canonical"
        assert editor.state.mapping == CANONICAL_MEANTONE

    def test_choosing_a_form_that_changes_the_matrix_stays_undoable(self):
        editor = Editor()
        assert editor.state.mapping == DEFAULT_MEANTONE
        steps = editor.undo_count
        editor.set_mapping_form("canonical")
        assert editor.state.mapping == CANONICAL_MEANTONE
        assert editor.undo_count == steps + 1
        editor.undo()
        assert editor.state.mapping == DEFAULT_MEANTONE

    def test_reselecting_the_same_comma_basis_form_is_not_an_undoable_edit(self):
        editor = Editor()
        editor.set_comma_basis_form("canonical")
        steps = editor.undo_count
        editor.set_comma_basis_form("canonical")
        assert editor.undo_count == steps
        assert editor.preferred_form.get("comma_basis") == "canonical"
