from fractions import Fraction

from rtt.app import presets, service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor
from _editor_support import _mapping_form_cell, _comma_form_cell


class TestUndoRedo:
    def test_editor_starts_at_meantone_with_no_undo(self):
        editor = Editor()
        assert editor.state.mapping == INITIAL_MAPPING
        assert editor.state.comma_basis == ((4, -4, 1),)
        assert editor.can_undo is False
        assert editor.can_redo is False

    def test_editor_starts_with_default_tuning_scheme_and_target_spec(self):
        editor = Editor()
        assert editor.tuning_scheme == service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME)
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        assert service.is_all_interval(editor.tuning_scheme) is False
        assert editor.target_spec == "TILT"

    def test_an_edit_enables_undo(self):
        editor = Editor()
        editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
        assert editor.can_undo is True

    def test_redo_restores_an_undone_action(self):
        editor = Editor()
        editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
        edited = editor.state.mapping
        editor.undo()
        assert editor.state.mapping == INITIAL_MAPPING
        assert editor.can_redo is True
        editor.redo()
        assert editor.state.mapping == edited
        assert editor.can_redo is False

    def test_a_fresh_edit_clears_the_redo_history(self):
        editor = Editor()
        editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
        editor.undo()
        assert editor.can_redo is True
        editor.edit_mapping([[1, 1, 0], [0, 1, 5]])
        assert editor.can_redo is False

    def test_undo_with_empty_stack_is_a_noop(self):
        editor = Editor()
        editor.undo()
        assert editor.state.mapping == INITIAL_MAPPING


class TestMatrixEdits:
    def test_canonicalize_mapping_restores_canonical_form_undoably(self):
        editor = Editor()
        editor.canonicalize_mapping()
        assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
        editor.undo()
        assert editor.state.mapping == INITIAL_MAPPING

    def test_canonicalize_comma_basis_restores_canonical_form_undoably(self):
        editor = Editor()
        editor.edit_comma_basis([[-8, 8, -2]])
        editor.canonicalize_comma_basis()
        assert editor.state.comma_basis == ((4, -4, 1),)
        editor.undo()
        assert editor.state.comma_basis == ((-8, 8, -2),)

    def test_edit_form_matrix_restores_the_mapping_in_the_typed_generating_set_undoably(self):
        editor = Editor()
        canonical, commas = service.canonical_mapping(editor.state.mapping), editor.state.comma_basis
        assert editor.edit_form_matrix(((1, 2), (0, 1))) is True
        assert editor.state.mapping == ((1, 2, 4), (0, 1, 4))
        assert service.canonical_mapping(editor.state.mapping) == canonical
        assert editor.state.comma_basis == commas
        assert service.form_matrix(editor.state.mapping) == ((1, 2), (0, 1))
        editor.undo()
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))

    def test_edit_form_matrix_rejects_a_non_unimodular_matrix(self):
        editor = Editor()
        before = editor.state
        assert editor.edit_form_matrix(((2, 0), (0, 1))) is False, "det 2 — not unimodular"
        assert editor.state is before and editor.can_undo is False
        assert editor.try_edit_form_matrix_text("[{2 0]{0 1]}") is False
        assert editor.try_edit_form_matrix_text("garble") is False
        assert editor.state is before

    def test_set_mapping_row_replaces_a_row_verbatim_and_is_undoable(self):
        editor = Editor()
        assert editor.set_mapping_row(0, (12, 19, 28)) is True
        assert editor.state.mapping[0] == (12, 19, 28), "stored verbatim, not canonicalized"
        assert editor.state.mapping[1] == (0, 1, 4)
        assert (editor.state.rank, editor.state.nullity) == (2, 1)
        assert editor.can_undo is True
        editor.undo()
        assert editor.state.mapping == INITIAL_MAPPING

    def test_set_mapping_row_rejects_a_dependent_row(self):
        editor = Editor()
        assert editor.set_mapping_row(1, (2, 2, 0)) is False
        assert editor.state.mapping == INITIAL_MAPPING
        assert editor.can_undo is False

    def test_set_mapping_row_preserves_a_nonstandard_domain(self):
        editor = Editor()
        editor.edit_comma_basis([(6, -1, -1)], (2, 9, 7))
        val = presets.et_value_to_val("12", (2, 9, 7))
        assert editor.set_mapping_row(0, val) is True
        assert editor.state.domain_basis == (2, 9, 7)

    def test_set_comma_replaces_a_column_verbatim_and_is_undoable(self):
        editor = Editor()
        vector = presets.comma_value_to_vector("128/125", (2, 3, 5))
        assert editor.set_comma(0, vector) is True
        assert editor.state.comma_basis[0] == tuple(vector)
        assert editor.state.nullity == 1
        assert editor.can_undo is True
        editor.undo()
        assert editor.state.comma_basis == ((4, -4, 1),)

    def test_set_comma_rejects_a_dependent_comma(self):
        editor = Editor()
        editor.edit_comma_basis([[-4, 4, -1, 0], [1, 2, -3, 1]])
        assert editor.state.nullity == 2
        assert editor.set_comma(1, (-8, 8, -2, 0)) is False
        assert editor.state.comma_basis == ((-4, 4, -1, 0), (1, 2, -3, 1))
        assert editor.state.nullity == 2

    def test_set_comma_preserves_a_nonstandard_domain(self):
        editor = Editor()
        editor.edit_comma_basis([(6, -1, -1)], (2, 9, 7))
        assert editor.state.domain_basis == (2, 9, 7)
        vector = presets.comma_value_to_vector("531441/524288", (2, 9, 7))
        assert editor.set_comma(0, vector) is True
        assert editor.state.domain_basis == (2, 9, 7), "not silently reset to standard primes"

    def test_editing_to_a_degenerate_temperament_is_rejected(self):
        editor = Editor()
        before = editor.state.mapping
        assert editor.try_edit_mapping_text("[⟨1 2] ⟨0 0]}") is False
        assert editor.state.mapping == before
        assert editor.try_edit_comma_basis_text("[1 0 0⟩") is False
        assert editor.state.mapping == before

    def test_mapping_row_guards(self):
        editor = Editor()
        editor.edit_mapping(((1, 0, 0),))
        assert editor.can_remove_mapping_row is False
        assert editor.can_add_mapping_row is True, "...nullity>0, a comma to un-temper"
        editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert editor.can_add_mapping_row is False, "nothing tempered to un-temper"


class TestForms:
    def test_set_mapping_form_restores_the_mapping_in_each_generator_form_undoably(self):
        editor = Editor()
        editor.set_mapping_form("canonical")
        assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
        editor.set_mapping_form("mingen")
        assert editor.state.mapping == ((1, 2, 4), (0, -1, -4))
        editor.set_mapping_form("equave-reduced")
        assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))
        editor.undo()
        assert editor.state.mapping == ((1, 2, 4), (0, -1, -4))

    def test_set_mapping_form_positive_generator_flip_and_shift_differ(self):
        editor = Editor()
        editor.edit_mapping([[1, 6, 8], [0, 7, 9]])
        editor.set_mapping_form("positive-generator")
        assert editor.state.mapping == ((1, 6, 8), (0, -7, -9))
        editor.set_mapping_form("positive-generator-shift")
        assert editor.state.mapping == ((1, -1, -1), (0, 7, 9))
        editor.undo()
        assert editor.state.mapping == ((1, 6, 8), (0, -7, -9))

    def test_set_comma_basis_form_restores_the_comma_basis_in_each_normal_form_undoably(self):
        editor = Editor()
        assert editor.state.comma_basis == ((4, -4, 1),)
        editor.set_comma_basis_form("positive-ratio")
        assert editor.state.comma_basis == ((-4, 4, -1),)
        assert service.identify_comma_basis_form(editor.state.comma_basis) == "positive-ratio"
        editor.set_comma_basis_form("minimal")
        assert editor.state.comma_basis == ((-4, 4, -1),)
        editor.set_comma_basis_form("canonical")
        assert editor.state.comma_basis == ((4, -4, 1),)
        editor.undo()
        assert editor.state.comma_basis == ((-4, 4, -1),)

    def test_set_comma_basis_form_minimal_simplifies_septimal_meantone(self):
        editor = Editor()
        editor.edit_comma_basis([[4, -4, 1, 0], [13, -10, 0, 1]])
        editor.set_comma_basis_form("minimal")
        assert editor.state.comma_basis == ((-4, 4, -1, 0), (1, 2, -3, 1))

    def test_mapping_chooser_shows_the_picked_form_even_when_forms_coincide(self):
        editor = Editor()
        editor.edit_mapping([[1, 6, 8], [0, 7, 9]])
        editor.set_mapping_form("positive-generator-shift")
        assert editor.state.mapping == ((1, -1, -1), (0, 7, 9))
        assert _mapping_form_cell(editor) == "positive-generator-shift", "the cell carries the resolved form KEY (the dropdown maps it to its 'positive-generator # (shift)' label for display); stickiness means it stays on shift, not the coinciding mingen"

    def test_chooser_shows_the_picked_form_even_when_forms_coincide(self):
        editor = Editor()
        editor.set_comma_basis_form("positive-ratio")
        assert _comma_form_cell(editor) == "positive-ratio"
        editor.set_comma_basis_form("minimal")
        assert _comma_form_cell(editor) == "minimal"
        editor.edit_comma_basis([[4, -4, 1]])
        assert _comma_form_cell(editor) == "canonical"
        editor.edit_comma_basis([[-4, 4, -1]])
        assert _comma_form_cell(editor) == "minimal"

    def test_chooser_form_pick_survives_undo_and_redo(self):
        editor = Editor()
        editor.set_comma_basis_form("positive-ratio")
        editor.set_comma_basis_form("minimal")
        editor.set_comma_basis_form("canonical")
        assert _comma_form_cell(editor) == "canonical"
        editor.undo()
        assert _comma_form_cell(editor) == "minimal"
        editor.undo()
        assert _comma_form_cell(editor) == "positive-ratio"
        editor.redo()
        assert _comma_form_cell(editor) == "minimal"


class TestTryEditText:
    def test_try_edit_form_matrix_text_parses_and_applies(self):
        editor = Editor()
        assert editor.try_edit_form_matrix_text("[{1 2]{0 1]}") is True
        assert editor.state.mapping == ((1, 2, 4), (0, 1, 4))

    def test_try_edit_mapping_text_applies_a_valid_ebk_map(self):
        editor = Editor()
        assert editor.try_edit_mapping_text("[⟨1 0 0] ⟨0 1 0] ⟨0 0 1]}") is True
        assert editor.state.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def test_try_edit_mapping_text_loads_a_nonstandard_domain_from_its_prefix(self):
        editor = Editor()
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        assert editor.state.domain_basis == (2, 3, Fraction(13, 5))
        assert editor.state.mapping == ((1, 2, 2), (0, -2, -3))
        assert editor.can_undo is True

    def test_try_edit_mapping_text_rejects_bad_input_without_changing_state(self):
        editor = Editor()
        before = editor.state.mapping
        assert editor.try_edit_mapping_text("garbage") is False
        assert editor.try_edit_mapping_text("[1 0 0⟩") is False, "a vector, not a map"
        assert editor.try_edit_mapping_text("⟨1 1.5 0]") is False
        assert editor.state.mapping == before
        assert editor.can_undo is False

    def test_try_edit_comma_basis_text_applies_a_valid_ebk_vector(self):
        editor = Editor()
        assert editor.try_edit_comma_basis_text("[4 -4 1⟩") is True
        assert editor.state.comma_basis == ((4, -4, 1),)

    def test_try_edit_comma_basis_text_rejects_bad_input_without_changing_state(self):
        editor = Editor()
        before = editor.state.comma_basis
        assert editor.try_edit_comma_basis_text("nonsense") is False
        assert editor.try_edit_comma_basis_text("⟨1 0 0]") is False, "a map, not a vector"
        assert editor.state.comma_basis == before

    def test_try_edit_comma_basis_text_preserves_a_nonstandard_domain(self):
        editor = Editor()
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        assert editor.try_edit_comma_basis_text("[2 -3 2⟩") is True
        assert editor.state.domain_basis == (2, 3, Fraction(13, 5))

    def test_try_edit_projection_text_retunes_or_rejects(self):
        ed = Editor()
        assert ed.try_edit_projection_text("[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩") is True
        assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
        assert ed.try_edit_projection_text("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩") is False
        assert ed.try_edit_projection_text("not a matrix") is False
        assert ed.try_edit_projection_text("[[1 0 0⟩[0 1 0⟩[0 0 1⟩]") is False, "a vector list, not a map"
        assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]

    def test_try_edit_embedding_text_retunes_or_rejects(self):
        ed = Editor()
        assert ed.try_edit_embedding_text("{[1 0 0⟩[1/3 -1/3 1/3⟩]") is True
        assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
        assert ed.try_edit_embedding_text("{[0 0 0⟩[0 0 1/4⟩]") is False
        assert ed.try_edit_embedding_text("[⟨1 1 0]⟨0 1 4]}") is False, "a map, not a vector list"

    def test_try_edit_projection_text_is_undoable(self):
        ed = Editor()
        assert ed.try_edit_projection_text("[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩") is True
        assert ed.manual_tuning is True
        ed.undo()
        assert ed.manual_tuning is False
        assert ed.displayed_projection_scheme_name == "1/4-comma"

    def test_try_edit_mapping_text_rejects_malformed_domain_prefixes(self):
        for bad in ("0.5 [⟨1 0] ⟨0 1]]",
                    "1.3 [⟨1 0] ⟨0 1]]",
                    "2.4 [⟨1 0] ⟨0 1]]",
                    "2.3.7 [⟨1 0] ⟨0 1]]"):
            editor = Editor()
            before = editor.state.mapping
            assert editor.try_edit_mapping_text(bad) is False
            assert editor.state.mapping == before
        assert Editor().try_edit_mapping_text("2.3.7 [⟨1 1 3] ⟨0 3 -1]}") is True
