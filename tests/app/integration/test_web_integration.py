"""Integration tests mirroring the original rtt-app ``spec/integration.test.tsx``.

The original rendered the React app and drove DOM events against a *mocked*
Wolfram API. Here the same user scenarios run through the Editor (service + undo
state), and the expected duals are the library's real canonical values — which
differ in sign from the original's hand-written mocks (e.g. the syntonic comma is
``[4 -4 1⟩`` here vs ``[-4 4 -1⟩`` there). Same scenarios, real arithmetic.
"""

from rtt.app import service
from rtt.app.render_html import _parse_int
from rtt.app.editor import INITIAL_MAPPING, Editor


def _domain(editor):
    return list(service.standard_primes(editor.state.dimensionality))


def _mapping(editor):
    return [list(row) for row in editor.state.mapping]


def _comma_basis(editor):
    return [list(comma) for comma in editor.state.comma_basis]


class TestWebIntegration:
    def test_expanding_grows_the_domain(self):
        editor = Editor()
        assert _domain(editor) == [2, 3, 5]
        editor.expand()
        assert _domain(editor) == [2, 3, 5, 7]

    def test_expanding_grows_the_mapping(self):
        editor = Editor()
        assert _mapping(editor) == [[1, 1, 0], [0, 1, 4]]
        editor.expand()
        assert _mapping(editor) == [[1, 0, -4, 0], [0, 1, 4, 0], [0, 0, 0, 1]]

    def test_expanding_grows_the_comma_basis(self):
        editor = Editor()
        assert _comma_basis(editor) == [[4, -4, 1]]
        editor.expand()
        assert _comma_basis(editor) == [[4, -4, 1, 0]]

    def test_shrinking_shrinks_the_domain(self):
        editor = Editor()
        assert _domain(editor) == [2, 3, 5]
        editor.shrink()
        assert _domain(editor) == [2, 3]

    def test_shrinking_shrinks_the_mapping(self):
        editor = Editor()
        editor.shrink()
        assert _mapping(editor) == [[1, 1]]

    def test_shrinking_shrinks_the_comma_basis(self):
        editor = Editor()
        editor.shrink()
        assert _comma_basis(editor) == [[4, -4]]

    def test_shrinking_to_a_degenerate_state_shows_no_phantom_comma_columns(self):
        editor = Editor()
        editor.edit_mapping(((12, 19, 28),))
        editor.shrink()
        editor.shrink()
        assert editor.state.dimensionality == editor.state.rank + editor.state.nullity
        cols = [c.id for c in editor.layout().cells
                if c.id.startswith("comma:") and not c.id.endswith(":pending")]
        assert len(cols) == editor.state.nullity == 1

    def test_changing_the_mapping_updates_the_comma_basis(self):
        editor = Editor()
        assert _comma_basis(editor) == [[4, -4, 1]]
        editor.edit_mapping([[1, 1, 0], [0, 1, 5]])
        assert _comma_basis(editor) == [[5, -5, 1]]

    def test_changing_the_comma_basis_updates_the_mapping(self):
        editor = Editor()
        assert _mapping(editor) == [[1, 1, 0], [0, 1, 4]]
        editor.edit_comma_basis([[4, -5, 1]])
        assert _mapping(editor) == [[1, 0, -4], [0, 1, 5]]

    def test_undo_reverts_the_latest_mapping_change(self):
        editor = Editor()
        original = [list(row) for row in INITIAL_MAPPING]
        editor.edit_mapping([[1, 1, 0], [0, 1, 5]])
        assert _mapping(editor) != original
        editor.undo()
        assert _mapping(editor) == original

    def test_undo_reverts_the_latest_comma_basis_change(self):
        editor = Editor()
        original = _comma_basis(editor)
        editor.edit_comma_basis([[4, -5, 1]])
        assert _comma_basis(editor) != original
        editor.undo()
        assert _comma_basis(editor) == original

    def test_removing_the_last_comma_reaches_just_intonation_and_renders(self):
        editor = Editor()
        editor.remove_comma()
        assert _mapping(editor) == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        assert editor.state.nullity == 0
        ids = {c.id for c in editor.layout().cells}
        assert "comma_plus" in ids and not any(c.startswith("comma_minus") for c in ids)
        assert "comma:0" not in ids and "cell:comma:0:0" not in ids
        editor.undo()
        assert _comma_basis(editor) == [[4, -4, 1]]

    def test_basis_is_nonstandard_tracks_the_domain(self):
        editor = Editor()
        assert editor.basis_is_nonstandard is False
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        assert editor.basis_is_nonstandard is True

    def test_exit_nonstandard_domain_standardizes_to_the_simplest_prime_limit(self):
        editor = Editor()
        editor.set_show("nonstandard_domain", True)
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        commas_before = service.comma_ratios(editor.state.comma_basis, editor.state.domain_basis)
        editor.exit_nonstandard_domain()
        assert editor.state.domain_basis == (2, 3, 5, 7, 11, 13)
        assert editor.basis_is_nonstandard is False
        assert editor.settings["nonstandard_domain"] is False
        assert service.comma_ratios(editor.state.comma_basis, editor.state.domain_basis) == commas_before
        editor.undo()
        assert editor.basis_is_nonstandard is True
        assert editor.settings["nonstandard_domain"] is True

    def test_exit_nonstandard_domain_is_a_noop_on_a_standard_basis(self):
        editor = Editor()
        assert editor.basis_is_nonstandard is False
        editor.exit_nonstandard_domain()
        assert editor.can_undo is False, "nothing happened, so nothing to undo"

    def test_select_none_standardizes_a_nonstandard_basis_like_the_direct_toggle(self):
        editor = Editor()
        editor.set_show("nonstandard_domain", True)
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        editor.set_all_show(False)
        assert editor.settings["nonstandard_domain"] is False
        assert editor.basis_is_nonstandard is False

    def test_select_none_turns_nonstandard_domain_off_on_a_standard_basis(self):
        editor = Editor()
        editor.set_show("nonstandard_domain", True)
        assert editor.basis_is_nonstandard is False
        editor.set_all_show(False)
        assert editor.settings["nonstandard_domain"] is False

    def test_disable_hidden_settings_turns_off_layers_past_the_chapter(self):
        editor = Editor()
        editor.set_show("weighting", True)
        editor.set_show("nonstandard_domain", True)
        editor.set_show("counts", True)
        undo_depth = editor.undo_count
        editor.disable_hidden_settings(2)
        assert editor.settings["weighting"] is False
        assert editor.settings["nonstandard_domain"] is False
        assert editor.settings["counts"] is True
        assert editor.undo_count == undo_depth, "a view prune, not an undoable edit"

    def test_set_all_show_only_flips_the_keys_it_is_given(self):
        editor = Editor()
        editor.set_all_show(False)
        editor.set_all_show(True, ["names"])
        assert editor.settings["names"] is True
        assert editor.settings["symbols"] is False

    def test_a_temporarily_invalid_cell_value_does_not_recompute(self):
        assert _parse_int("-") is None, "While typing, a lone '-' is not a number: the UI parses it to None and skips # the recompute (no crash). A complete value like '-3' parses to drive an edit"
        assert _parse_int("-3") == -3
