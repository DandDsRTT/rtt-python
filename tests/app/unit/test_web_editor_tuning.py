from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


class TestTuningSchemes:
    def test_selecting_a_tuning_scheme_and_target_spec_updates_them(self):
        editor = Editor()
        editor.set_tuning_scheme("destretched-octave minimax-ES")
        editor.set_target_spec("OLD")
        assert service.base_scheme_name(editor.tuning_scheme) == "destretched-octave minimax-ES"
        assert editor.target_spec == "OLD"
        assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == "OLD"

    def test_scheme_and_target_spec_changes_are_undoable(self):
        editor = Editor()
        editor.set_tuning_scheme("held-octave minimax-ES")
        assert editor.can_undo is True
        editor.set_target_spec("OLD")
        editor.undo()
        assert editor.target_spec == "TILT"
        editor.undo()
        assert service.base_scheme_name(editor.tuning_scheme) \
            == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)
        editor.redo()
        assert service.base_scheme_name(editor.tuning_scheme) == "held-octave minimax-ES"

    def test_set_tuning_scheme_preserves_the_target_mode(self):
        editor = Editor()
        editor.set_tuning_scheme("minimax-ES")
        assert not service.is_all_interval(editor.tuning_scheme)
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-ES"
        assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
        editor.set_all_interval(True)
        editor.set_tuning_scheme("minimax-S")
        assert service.is_all_interval(editor.tuning_scheme)
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-S"

    def test_a_held_octave_scheme_holds_the_octave_in_target_mode(self):
        editor = Editor()
        editor.set_tuning_scheme("held-octave minimax-ES")
        spec = service.resolve_tuning_scheme(editor.tuning_scheme)
        assert spec.held_intervals == "octave"
        assert spec.target_intervals == editor.target_spec, "...and it is target-based, not all-interval"
        tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis)
        assert abs(tuning_map.tuning_map[0] - 1200.0) < 1e-6

    def test_set_weight_slope_swaps_the_damage_weight_slope(self):
        editor = Editor()
        assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
        flat = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                                 tuning_scheme=editor.tuning_scheme)
        assert all(c.text == "1.000" for c in flat.cells if c.id.startswith("weight:target:"))
        editor.set_weight_slope("simplicity-weight")
        assert service.weight_slope_of(editor.tuning_scheme) == "simplicity-weight"
        lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                                tuning_scheme=editor.tuning_scheme)
        weights = [c.text for c in lay.cells if c.id.startswith("weight:target:")]
        assert weights and not all(w == "1.000" for w in weights)

    def test_the_weighting_choosers_are_undoable_like_every_other_change(self):
        editor = Editor()
        editor.set_weight_slope("simplicity-weight")
        assert editor.can_undo is True
        editor.undo()
        assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
        editor.set_complexity_name("sopfr")
        editor.undo()
        assert service.complexity_name_of(editor.tuning_scheme) == "lp"
        editor.set_diminuator_replaced(True)
        editor.undo()
        assert service.diminuator_replaced(editor.tuning_scheme) is False

    def test_set_complexity_prescaler_swaps_the_weighting_prescaler_into_the_layout(self):
        editor = Editor()
        assert service.prescaler_of(editor.tuning_scheme) == "log-prime"
        editor.set_complexity_prescaler("prime")
        assert service.prescaler_of(editor.tuning_scheme) == "prime"
        editor.set_weight_slope("simplicity-weight")
        lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True, "alt_complexity": True},
                                tuning_scheme=editor.tuning_scheme)
        on = {c.id: c.text for c in lay.cells}
        assert on["cell:prescaling:primes:0:0"] == "2"
        assert on["cell:prescaling:primes:1:1"] == "3"
        assert on["cell:prescaling:primes:2:2"] == "5"

    def test_set_complexity_norm_power_sets_the_complexity_norm(self):
        editor = Editor()
        assert service.complexity_norm_power(editor.tuning_scheme) == 1
        editor.set_complexity_norm_power(2)
        assert service.complexity_norm_power(editor.tuning_scheme) == 2
        editor.set_complexity_norm_power(3)
        assert service.complexity_norm_power(editor.tuning_scheme) == 3

    def test_set_complexity_name_sets_the_whole_complexity_shape(self):
        editor = Editor()
        assert service.complexity_name_of(editor.tuning_scheme) == "lp"
        editor.set_complexity_name("sopfr")
        assert service.complexity_name_of(editor.tuning_scheme) == "sopfr"
        assert service.prescaler_of(editor.tuning_scheme) == "prime"
        editor.set_complexity_name("lols")
        assert service.held_intervals(editor.tuning_scheme) == ("2/1",)

    def test_set_diminuator_replaced_toggles_the_size_factor(self):
        editor = Editor()
        assert service.diminuator_replaced(editor.tuning_scheme) is False
        editor.set_diminuator_replaced(True)
        assert service.diminuator_replaced(editor.tuning_scheme) is True
        editor.set_diminuator_replaced(False)
        assert service.diminuator_replaced(editor.tuning_scheme) is False

    def test_picking_a_scheme_retunes_immediately(self):
        editor = Editor()
        gens = lambda: {c.id: c.text for c in editor.layout().cells}["tuning:gen:1"]
        before = gens()
        editor.set_tuning_scheme("minimax-S")
        assert gens() != before
        assert editor.effective_generator_tuning() is None
        assert editor.displayed_tuning_scheme_name == "minimax-S"

    def test_picking_a_preset_prescaler_clears_the_custom_override(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(1, 1, 9.9)
        editor.set_complexity_prescaler("prime")
        assert editor.custom_prescaler is None
        assert service.prescaler_of(editor.tuning_scheme) == "prime"

    def test_picking_a_predefined_complexity_clears_the_custom_override(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(0, 0, 3.3)
        editor.set_complexity_name("sopfr")
        assert editor.custom_prescaler is None
        assert service.prescaler_of(editor.tuning_scheme) == "prime"


class TestCustomWeighting:
    def test_custom_prescaler_starts_unset_and_is_a_diagonal_d_tuple(self):
        editor = Editor()
        assert editor.custom_prescaler is None

    def test_custom_prescaler_edits_are_undoable(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(1, 1, 7.5)
        assert editor.can_undo is True
        editor.undo()
        assert editor.custom_prescaler is None
        editor.redo()
        assert editor.custom_prescaler is not None and editor.custom_prescaler[1] == 7.5

    def test_set_custom_prescaler_entry_seeds_then_edits_one_diagonal_cell(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(1, 1, 7.5)
        seed = service.complexity_prescaler(editor.state.mapping, service.DEFAULT_TUNING_SCHEME)
        assert editor.custom_prescaler == (seed[0], 7.5, seed[2])
        editor.set_custom_prescaler_entry(2, 2, 11.0)
        assert editor.custom_prescaler == (seed[0], 7.5, 11.0)

    def test_set_custom_prescaler_entry_promotes_to_a_matrix_on_an_off_diagonal_edit(self):
        editor = Editor()
        seed = service.complexity_prescaler(editor.state.mapping, service.DEFAULT_TUNING_SCHEME)
        editor.set_custom_prescaler_entry(0, 1, 0.5)
        M = editor.custom_prescaler
        assert isinstance(M[0], tuple)
        assert M[0][1] == 0.5
        assert (M[0][0], M[1][1], M[2][2]) == (seed[0], seed[1], seed[2])
        assert M[2][0] == 0.0
        editor.set_custom_prescaler_entry(2, 2, 9.0)
        assert isinstance(editor.custom_prescaler[0], tuple) and editor.custom_prescaler[2][2] == 9.0

    def test_set_custom_prescaler_text_holds_a_typed_diagonal(self):
        editor = Editor()
        ok = editor.set_custom_prescaler_text("[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩")
        assert ok is True
        assert editor.custom_prescaler == (1.0, 4.0, 2.322)
        editor.undo()
        assert editor.custom_prescaler is None
        editor.redo()
        assert editor.custom_prescaler == (1.0, 4.0, 2.322)

    def test_set_custom_prescaler_text_rejects_unparseable_or_malformed_input(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(1, 1, 7.5)
        before = editor.custom_prescaler
        undo_steps_before = editor.can_undo
        assert editor.set_custom_prescaler_text("garbage") is False
        assert editor.custom_prescaler == before
        assert editor.set_custom_prescaler_text("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩") is False, "an off-diagonal nonzero is malformed (𝐿 is diagonal), so it too is rejected"
        assert editor.custom_prescaler == before
        assert editor.set_custom_prescaler_text("[⟨1 0] ⟨0 2]⟩") is False
        assert editor.custom_prescaler == before
        assert editor.can_undo == undo_steps_before

    def test_set_custom_weight_entry_seeds_then_edits_one_slot(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        seeded = editor.custom_weights
        editor.set_custom_weight_entry(1, 4.0)
        assert editor.custom_weights[1] == 4.0
        assert editor.custom_weights[0] == seeded[0]
        editor.set_custom_weight_entry(0, 9.0)
        assert editor.custom_weights[0] == 9.0
        assert editor.custom_weights[1] == 4.0

    def test_custom_weights_starts_off_and_the_toggle_drives_it(self):
        editor = Editor()
        assert editor.custom_weights is None
        assert editor.settings["custom_weights"] is False
        n = len(editor.current_targets())
        editor.set_show("custom_weights", True)
        assert editor.custom_weights is not None and len(editor.custom_weights) == n
        assert editor.settings["custom_weights"] is True
        for key in ("weighting", "optimization", "tuning"):
            assert editor.settings[key] is True
        editor.set_show("custom_weights", False)
        assert editor.custom_weights is None
        assert editor.settings["custom_weights"] is False

    def test_custom_weights_toggle_is_one_undoable_step(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        editor.undo()
        assert editor.custom_weights is None and editor.settings["custom_weights"] is False
        editor.redo()
        assert editor.custom_weights is not None and editor.settings["custom_weights"] is True

    def test_custom_weights_is_checkable_while_all_interval_is_on(self):
        editor = Editor()
        editor.set_all_interval(True)
        editor.set_show("custom_weights", True)
        assert editor.settings["custom_weights"] is True
        assert editor.custom_weights is None
        editor.set_all_interval(False)
        assert editor.custom_weights is not None

    def test_custom_weights_round_trip_and_resync_the_toggle(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        editor.set_custom_weight_entry(0, 7.0)
        restored = Editor()
        restored.load(editor.serialize())
        assert restored.custom_weights == editor.custom_weights
        assert restored.settings["custom_weights"] is True

    def test_picking_a_named_slope_clears_custom_weights(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        editor.set_weight_slope("complexity-weight")
        assert editor.custom_weights is None and editor.settings["custom_weights"] is False

    def test_a_complexity_or_prescaler_pick_clears_custom_weights(self):
        for action in ("complexity", "prescaler"):
            editor = Editor()
            editor.set_show("custom_weights", True)
            if action == "complexity":
                editor.set_complexity_name("sopfr")
            else:
                editor.set_complexity_prescaler("prime")
            assert editor.custom_weights is None, action
            assert editor.settings["custom_weights"] is False, action

    def test_a_target_change_re_seeds_custom_weights_keeping_the_setting(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        n_before = len(editor.custom_weights)
        editor.remove_target(0)
        assert editor.settings["custom_weights"] is True
        assert editor.custom_weights is not None and len(editor.custom_weights) == n_before - 1

    def test_a_domain_change_re_seeds_custom_weights_keeping_the_setting(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        editor.expand()
        assert editor.settings["custom_weights"] is True
        assert editor.custom_weights is not None

    def test_round_trip_prescaler_edit_returns_to_the_scheme_name(self):
        editor = Editor()
        shown = float(service.prescale_text(
            service.complexity_prescaler(editor.state.mapping, editor.tuning_scheme)[1]))
        editor.set_custom_prescaler_entry(1, 1, 9.9)
        assert editor.displayed_prescaler_name is None
        editor.set_custom_prescaler_entry(1, 1, shown)
        assert editor.displayed_prescaler_name == "log-prime"

    def test_displayed_prescaler_name_tracks_the_scheme_and_falls_back_on_a_manual_edit(self):
        editor = Editor()
        assert editor.displayed_prescaler_name == "log-prime"
        editor.set_custom_prescaler_entry(1, 1, 9.9)
        assert editor.displayed_prescaler_name is None
        editor.undo()
        assert editor.displayed_prescaler_name == "log-prime"

    def test_load_round_trips_a_matrix_pretransformer_override(self):
        import json

        editor = Editor()
        editor.set_custom_prescaler_entry(0, 1, 0.5)
        e2 = Editor()
        e2.load(editor.serialize())
        assert e2.custom_prescaler == editor.custom_prescaler
        assert isinstance(e2.custom_prescaler[0], tuple)
        e3 = Editor()
        e3.load(json.loads(json.dumps(editor.serialize())))
        assert e3.custom_prescaler == editor.custom_prescaler

    def test_load_drops_a_crash_inducing_prescaler_and_still_renders(self):
        editor = Editor()
        editor.set_weight_slope("simplicity-weight")
        doc = editor.serialize()
        doc["custom_prescaler"] = [0.0, 1.585, 2.322]
        editor.load(doc)
        assert editor.custom_prescaler is None, "the crash-inducing prescaler was dropped"
        editor.layout()

        editor2 = Editor()
        editor2.set_weight_slope("simplicity-weight")
        doc2 = editor2.serialize()
        doc2["custom_prescaler"] = [float("inf"), 1.585, 2.322]
        editor2.load(doc2)
        assert editor2.custom_prescaler is None
        editor2.layout()

    def test_load_drops_a_bad_custom_weights_value(self):
        editor = Editor()
        data = editor.serialize()
        data["custom_weights"] = [1.0, -2.0, 0.0]
        editor.load(data)
        assert editor.custom_weights is None and editor.settings["custom_weights"] is False

    def test_load_keeps_a_valid_custom_prescaler(self):
        editor = Editor()
        editor.set_custom_prescaler_entry(1, 1, 7.5)
        saved = editor.custom_prescaler
        e2 = Editor()
        e2.load(editor.serialize())
        assert e2.custom_prescaler == saved


class TestAllIntervalMode:
    def test_turning_off_alt_complexity_resets_the_tuning_to_basic_minimax_lp(self):
        editor = Editor()
        editor.set_show("alt_complexity", True)
        editor.set_complexity_norm_power(2)
        editor.set_optimization_power(2)
        editor.set_show("alt_complexity", False)
        assert service.optimization_power(editor.tuning_scheme) == float("inf")
        assert service.complexity_norm_power(editor.tuning_scheme) == 1
        assert service.complexity_name_of(editor.tuning_scheme) == "lp"
        assert editor.custom_prescaler is None
        editor.undo()
        assert editor.settings["alt_complexity"] is True
        assert service.optimization_power(editor.tuning_scheme) == 2
        assert service.complexity_norm_power(editor.tuning_scheme) == 2

    def test_turning_off_all_interval_show_exits_all_interval_mode(self):
        editor = Editor()
        editor.set_show("all_interval", True)
        editor.set_all_interval(True)
        assert service.is_all_interval(editor.tuning_scheme) is True
        editor.set_show("all_interval", False)
        assert editor.settings["all_interval"] is False
        assert service.is_all_interval(editor.tuning_scheme) is False
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U"
        editor.undo()
        assert editor.settings["all_interval"] is True
        assert service.is_all_interval(editor.tuning_scheme) is True

    def test_deselecting_weighting_also_resets_alt_complexity_to_basic(self):
        editor = Editor()
        editor.set_show("alt_complexity", True)
        editor.set_optimization_power(2)
        editor.set_show("weighting", False)
        assert editor.settings["alt_complexity"] is False
        assert service.optimization_power(editor.tuning_scheme) == float("inf")

    def test_deselecting_weighting_also_exits_all_interval_mode(self):
        editor = Editor()
        editor.set_show("all_interval", True)
        editor.set_all_interval(True)
        editor.set_show("weighting", False)
        assert editor.settings["all_interval"] is False
        assert service.is_all_interval(editor.tuning_scheme) is False

    def test_set_all_interval_toggles_the_scheme_target_set(self):
        editor = Editor()
        assert service.is_all_interval(editor.tuning_scheme) is False
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U", "check the scheme's identity directly by name (base_scheme_name); displayed_tuning_scheme_name # tracks it too (the always-on optimization realises a picked scheme at once, so the name follows)"
        assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
        editor.set_all_interval(True)
        assert service.is_all_interval(editor.tuning_scheme) is True
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-S", "an all-interval scheme is simplicity-weighted by construction, so the toggle forces it"
        assert service.weight_slope_of(editor.tuning_scheme) == "simplicity-weight"
        editor.set_all_interval(False)
        assert service.is_all_interval(editor.tuning_scheme) is False
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U"
        assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
        editor.undo()
        assert service.is_all_interval(editor.tuning_scheme) is True

    def test_all_interval_clears_the_override_but_keeps_the_custom_weights_setting(self):
        editor = Editor()
        editor.set_show("custom_weights", True)
        assert editor.custom_weights is not None
        editor.set_all_interval(True)
        assert editor.custom_weights is None
        assert editor.settings["custom_weights"] is True
        editor.set_all_interval(False)
        assert editor.custom_weights is not None
        assert editor.settings["custom_weights"] is True

    def test_all_interval_toggle_off_keeps_a_destretched_modifier(self):
        editor = Editor()
        editor.set_all_interval(True)
        editor.set_tuning_scheme("destretched-octave minimax-ES")
        editor.set_all_interval(False)
        spec = service.resolve_tuning_scheme(editor.tuning_scheme)
        assert spec.destretched_interval == "octave"
        assert not service.is_all_interval(editor.tuning_scheme)
        assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
        assert service.base_scheme_name(editor.tuning_scheme) == "destretched-octave minimax-EU"
