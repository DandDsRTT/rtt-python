from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


class TestTargetSpec:
    def test_a_manual_target_limit_is_weakly_held_and_reverts_when_the_domain_changes(self):
        editor = Editor()
        editor.set_target_spec("9-TILT")
        assert editor.target_spec == "9-TILT"
        editor.set_target_spec("11-OLD")
        assert editor.target_spec == "11-OLD"
        editor.expand()
        assert editor.target_spec == "OLD"

    def test_a_manual_target_limit_does_not_resurrect_when_the_domain_returns(self):
        editor = Editor()
        editor.set_target_spec("7-TILT")
        editor.edit_comma_basis([[-5, 2, 2, -1], [-10, 1, 0, 3]])
        editor.edit_comma_basis([[-4, 4, -1]])
        assert editor.target_spec == "TILT", "the 5-limit default, NOT the stale 7-TILT"

    def test_setting_a_bare_family_clears_any_manual_limit(self):
        editor = Editor()
        editor.set_target_spec("9-TILT")
        editor.set_target_spec("OLD")
        assert editor.target_spec == "OLD"

    def test_add_and_remove_target_set_a_manual_override(self):
        editor = Editor()
        assert editor.target_override is None
        n = len(service.target_interval_set(editor.target_spec, editor.state.domain_basis))
        editor.remove_target(0)
        assert editor.target_override is not None and len(editor.target_override) == n - 1
        editor.add_target()
        assert editor.pending_target == [None, None, None] and len(editor.target_override) == n - 1
        editor.set_pending_target([-1, 1, 0])
        assert len(editor.target_override) == n and editor.target_override[-1] == "3/2"
        editor.undo()
        assert len(editor.target_override) == n - 1
        editor.undo()
        assert editor.target_override is None

    def test_range_mode_starts_monotone_and_is_undoable(self):
        editor = Editor()
        assert editor.range_mode == "monotone"
        editor.set_range_mode("tradeoff")
        assert editor.range_mode == "tradeoff"
        assert editor.can_undo is True
        editor.undo()
        assert editor.range_mode == "monotone"

    def test_target_limit_beyond_the_domain_filters_out_of_domain_intervals(self):
        editor = Editor()
        editor.set_target_spec("11-OLD")
        shown = service.target_interval_set("11-OLD", editor.state.domain_basis)
        assert "7/4" not in shown and "11/8" not in shown
        assert "5/4" in shown
        editor.layout()

    def test_a_unison_target_does_not_break_simplicity_weighting(self):
        editor = Editor()
        editor.set_weight_slope("simplicity-weight")
        editor.set_target_override_vectors([[0, 0, 0], [-1, 1, 0]])
        tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis,
                             targets=editor.target_override)
        assert len(tuning_map.tuning_map) == 3 and all(v == v and abs(v) < 1e6 for v in tuning_map.tuning_map)


class TestTargetOverride:
    def test_set_target_override_text_and_vectors(self):
        editor = Editor()
        assert editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩") is True
        assert editor.target_override == ("2/1", "3/2")
        assert editor.can_undo is True
        assert editor.set_target_override_text("garbage") is False
        assert editor.target_override == ("2/1", "3/2")
        editor.set_target_override_vectors([[2, 0, 0], [0, 0, 1]])
        assert editor.target_override == ("4/1", "5/1")

    def test_choosing_a_target_spec_or_changing_domain_clears_the_target_override(self):
        editor = Editor()
        editor.set_target_override_text("[1 0 0⟩")
        assert editor.target_override is not None
        editor.set_target_spec("OLD")
        assert editor.target_override is None
        editor.set_target_override_text("[1 0 0⟩")
        editor.expand()
        assert editor.target_override is None

    def test_target_override_round_trips_serialize_and_older_docs_lack_it(self):
        editor = Editor()
        editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")
        data = editor.serialize()
        fresh = Editor()
        fresh.load(data)
        assert fresh.target_override == ("2/1", "3/2")
        del data["target_override"]
        older = Editor()
        older.load(data)
        assert older.target_override is None

    def test_the_tuning_follows_a_changed_target_interval_list(self):
        editor = Editor()
        tilt_optimum = editor.optimum_generator_tuning()
        editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")
        assert editor.optimum_generator_tuning() != tilt_optimum

    def test_no_chooser_scheme_yields_an_invalid_target_less_tuning(self):
        from rtt.app import presets

        editor = Editor()
        for all_interval in (False, True):
            editor.set_all_interval(all_interval)
            options = presets.tuning_scheme_options(
                all_interval, include_alternatives=True, weighting=True)
            for value in options:
                editor.set_tuning_scheme(value)
                spec = service.resolve_tuning_scheme(editor.tuning_scheme)
                if not service.is_all_interval(editor.tuning_scheme):
                    assert spec.target_intervals not in (None, "", "{}"), value
                tm = service.tuning(
                    editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis).tuning_map
                assert all(x == x for x in tm), value
