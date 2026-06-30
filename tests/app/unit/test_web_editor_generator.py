from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor
from _editor_support import _cents_map, BARBADOS, BARBADOS_ALT


class TestGeneratorTuning:
    def test_set_generator_tuning_text_freezes_a_typed_generator_map(self):
        editor = Editor()
        assert editor.set_generator_tuning_text("{1200.000 701.955]") is True
        assert editor.effective_generator_tuning() == (1200.0, 701.955)
        assert editor.manual_tuning is True
        assert editor.can_undo is True
        assert editor.set_generator_tuning_text("{1200]") is False
        assert editor.set_generator_tuning_text("garbage") is False
        assert editor.effective_generator_tuning() == (1200.0, 701.955)

    def test_set_generator_tuning_component_overrides_one_generator(self):
        editor = Editor()
        optimum = editor.optimum_generator_tuning()
        editor.set_generator_tuning_component(1, 700.0)
        eff = editor.effective_generator_tuning()
        assert eff[1] == 700.0 and eff[0] == optimum[0]
        assert editor.manual_tuning is True and editor.can_undo is True

    def test_editing_a_generator_cell_after_a_rank_change_seeds_from_the_optimum(self):
        editor = Editor()
        editor.set_generator_tuning_component(1, 700.0)
        editor.expand()
        assert editor.state.rank == 3 and len(editor.generator_tuning) == 2
        editor.set_generator_tuning_component(2, 700.0)
        assert len(editor.generator_tuning) == 3 and editor.generator_tuning[2] == 700.0
        editor.nudge_generator_tuning_component(2, 5)
        assert len(editor.generator_tuning) == 3

    def test_flip_generator_reverses_the_mapping_row_and_keeps_the_tuning_map(self):
        editor = Editor()
        tuning_map_before = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
        row1_before, row0 = editor.state.mapping[1], editor.state.mapping[0]
        gen1_before = editor.optimum_generator_tuning()[1]
        editor.flip_generator(1)
        assert editor.state.mapping[1] == tuple(-x for x in row1_before)
        assert editor.state.mapping[0] == row0
        assert _cents_map([editor.optimum_generator_tuning()[1]]) == _cents_map([-gen1_before])
        tuning_map_after = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
        assert _cents_map(tuning_map_after) == _cents_map(tuning_map_before)
        assert editor.can_undo is True
        editor.undo()
        assert editor.state.mapping[1] == row1_before

    def test_flip_generator_with_a_frozen_tuning_negates_its_size_and_holds_the_tuning_map(self):
        editor = Editor()
        editor.set_generator_tuning_component(1, 700.0)
        eff_before = editor.effective_generator_tuning()
        t_before = service.tuning_from_generators(editor.state.mapping, eff_before).tuning_map
        editor.flip_generator(1)
        eff_after = editor.effective_generator_tuning()
        assert eff_after[1] == -700.0 and eff_after[0] == eff_before[0]
        t_after = service.tuning_from_generators(editor.state.mapping, eff_after).tuning_map
        assert _cents_map(t_after) == _cents_map(t_before)

    def test_nudge_generator_tuning_component_steps_by_a_thousandth_of_a_cent(self):
        editor = Editor()
        optimum = editor.optimum_generator_tuning()
        shown = round(optimum[1], 3)
        editor.nudge_generator_tuning_component(1, 1)
        eff = editor.effective_generator_tuning()
        assert eff[1] == round(shown + 0.001, 3)
        assert eff[0] == optimum[0]
        assert editor.manual_tuning is True
        assert editor.can_undo is True
        editor.nudge_generator_tuning_component(1, -1)
        assert editor.effective_generator_tuning()[1] == shown

    def test_consecutive_generator_nudges_coalesce_into_one_undo_step(self):
        editor = Editor()
        shown = round(editor.optimum_generator_tuning()[1], 3)
        editor.nudge_generator_tuning_component(1, 1)
        editor.nudge_generator_tuning_component(1, 1)
        editor.nudge_generator_tuning_component(1, 1)
        assert editor.effective_generator_tuning()[1] == round(shown + 0.003, 3)
        editor.undo()
        assert editor.effective_generator_tuning() is None
        assert editor.can_undo is False

    def test_nudging_a_different_generator_starts_a_new_undo_step(self):
        editor = Editor()
        optimum = editor.optimum_generator_tuning()
        editor.nudge_generator_tuning_component(0, 1)
        editor.nudge_generator_tuning_component(1, 1)
        editor.undo()
        eff = editor.effective_generator_tuning()
        assert eff[0] == round(round(optimum[0], 3) + 0.001, 3)
        assert eff[1] == optimum[1]

    def test_an_edit_between_nudges_breaks_the_coalescing(self):
        editor = Editor()
        editor.nudge_generator_tuning_component(1, 1)
        editor.set_generator_tuning_component(0, 700.0)
        a_then_typed = editor.effective_generator_tuning()
        editor.nudge_generator_tuning_component(1, 1)
        editor.undo()
        assert editor.effective_generator_tuning() == a_then_typed

    def test_override_generator_clamps_an_out_of_range_component(self):
        editor = Editor()
        editor.add_mapping_row()
        editor.set_pending_mapping_row([0, 0, 1])
        editor.set_generator_tuning_component(2, 700.0)
        editor.add_comma()
        editor.set_pending_comma([4, -4, 1])
        before = editor.generator_tuning
        editor.set_generator_tuning_component(2, 700.0)
        editor.nudge_generator_tuning_component(2, 1)
        assert editor.generator_tuning == before
        editor.layout()

    def test_optimization_is_always_on_so_a_change_retunes_immediately(self):
        editor = Editor()
        assert editor.generator_tuning is None
        assert editor.effective_generator_tuning() is None
        generators = lambda: {c.id: c.text for c in editor.layout().cells}["tuning:generator:1"]
        before = generators()
        editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")
        assert generators() != before

    def test_editor_optimum_uses_the_domain_basis_not_standard_primes(self):
        editor = Editor()
        assert editor.try_edit_mapping_text(BARBADOS)
        generators = editor.optimum_generator_tuning()
        grid = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis).generator_map
        assert _cents_map(generators) == _cents_map(grid)
        assert round(generators[0], 3) == 1199.872 and round(generators[1], 3) == 248.766, "the real optimum, not 822 ¢"

    def test_editor_optimum_honors_the_custom_prescaler(self):
        editor = Editor()
        editor.set_weight_slope("simplicity-weight")
        editor.set_custom_prescaler_entry(0, 0, 3.0)
        generators = editor.optimum_generator_tuning()
        grid = service.tuning(editor.state.mapping, editor.tuning_scheme,
                              prescaler_override=editor.custom_prescaler).generator_map
        assert _cents_map(generators) == _cents_map(grid)
        editor.set_generator_tuning_text("{%f %f]" % generators)
        assert editor.tuning_is_optimized is True


class TestSchemeNameTracking:
    def test_displayed_scheme_name_names_a_control_refined_spec(self):
        editor = Editor()
        editor.set_all_interval(True)
        editor.set_complexity_norm_power(2)
        assert service.base_scheme_name(editor.tuning_scheme) == "minimax-ES"
        assert editor.displayed_tuning_scheme_name == "minimax-ES"

    def test_displayed_scheme_name_is_none_for_an_unnameable_power(self):
        editor = Editor()
        editor.set_optimization_power(1.5)
        assert editor.displayed_tuning_scheme_name is None

    def test_displayed_tuning_scheme_name_drops_to_none_when_the_tuning_deviates(self):
        editor = Editor()
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        editor.set_generator_tuning_component(1, 700.0)
        assert editor.displayed_tuning_scheme_name is None
        fresh = Editor()
        fresh.set_optimization_power(2.0)
        assert fresh.displayed_tuning_scheme_name == "miniRMS-U"

    def test_displayed_tuning_scheme_name_keeps_the_name_when_the_tuning_still_matches(self):
        editor = Editor()
        optimum = editor.optimum_generator_tuning()
        editor.set_generator_tuning_component(1, round(optimum[1], 3))
        assert editor.effective_generator_tuning() is not None
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        editor.expand()
        assert len(editor.effective_generator_tuning()) != editor.state.rank
        assert editor.displayed_tuning_scheme_name == "minimax-U"

    def test_displayed_tuning_scheme_name_drops_to_none_when_a_held_interval_deviates_the_tuning(self):
        editor = Editor()
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        editor.set_held_vectors([(-1, 1, 0)])
        assert editor.displayed_tuning_scheme_name is None
        octave = Editor()
        octave.set_held_vectors([(1, 0, 0)])
        assert octave.displayed_tuning_scheme_name == "minimax-U"

    def test_displayed_tuning_scheme_name_keeps_the_name_under_a_typed_target_list(self):
        editor = Editor()
        editor.set_target_override_vectors([(-1, 1, 0), (-2, 0, 1)])
        assert editor.target_override == ("3/2", "5/4")
        assert editor.displayed_tuning_scheme_name == "minimax-U"

    def test_a_scheme_control_pick_tracks_the_established_scheme_name(self):
        editor = Editor()
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        editor.set_weight_slope("complexity-weight")
        assert editor.displayed_tuning_scheme_name == "minimax-C"
        editor.set_weight_slope("simplicity-weight")
        assert editor.displayed_tuning_scheme_name == "minimax-S"
        editor.set_weight_slope("unity-weight")
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        editor.set_optimization_power(2.0)
        assert editor.displayed_tuning_scheme_name == "miniRMS-U"

    def test_a_hand_edit_blanks_the_chooser_even_after_a_scheme_pick(self):
        editor = Editor()
        editor.set_weight_slope("complexity-weight")
        assert editor.displayed_tuning_scheme_name == "minimax-C"
        editor.set_generator_tuning_component(1, 700.0)
        assert editor.displayed_tuning_scheme_name is None

    def test_a_scheme_pick_clears_a_hand_edit_and_names_the_picked_scheme(self):
        editor = Editor()
        editor.set_generator_tuning_component(1, 700.0)
        assert editor.displayed_tuning_scheme_name is None
        editor.set_tuning_scheme("minimax-C")
        assert editor.manual_tuning is False
        assert editor.effective_generator_tuning() is None
        assert editor.displayed_tuning_scheme_name == "minimax-C"


class TestManualOptimized:
    def test_manual_tuning_status_travels_with_the_document(self):
        editor = Editor()
        editor.set_weight_slope("complexity-weight")
        editor.set_generator_tuning_component(1, 700.0)
        assert editor.displayed_tuning_scheme_name is None
        reloaded = Editor()
        reloaded.load(editor.serialize())
        assert reloaded.displayed_tuning_scheme_name is None
        editor.undo()
        assert editor.displayed_tuning_scheme_name == "minimax-C"

    def test_tuning_is_optimized_tracks_whether_the_grid_shows_the_optimum(self):
        editor = Editor()
        assert editor.tuning_is_optimized is True
        editor.set_generator_tuning_component(1, 700.0)
        assert editor.tuning_is_optimized is False
        editor.back_to_scheme()
        assert editor.tuning_is_optimized is True

    def test_tuning_is_optimized_holds_under_held_intervals(self):
        held = Editor()
        held.add_held()
        held.set_held_vectors([(-1, 1, 0)])
        assert held.displayed_tuning_scheme_name is None
        assert held.tuning_is_optimized is True
        held.set_generator_tuning_component(1, 700.0)
        assert held.tuning_is_optimized is False

    def test_layout_wraps_the_mean_damage_symbol_in_min_while_optimized(self):
        editor = Editor()
        editor.set_show("optimization", True)

        def mean_damage_symbol() -> str:
            return {c.id: c for c in editor.layout().cells}["optimization:mean_damage:symbol"].text

        assert mean_damage_symbol() == "min(⟪𝐝⟫ₚ)"
        editor.set_generator_tuning_component(1, 700.0)
        assert mean_damage_symbol() == "⟪𝐝⟫ₚ"

    def test_load_reoptimizes_an_old_docs_non_manual_frozen_tuning(self):
        editor = Editor()
        data = editor.serialize()
        data["generator_tuning"] = [1200.0, 696.578]
        data["manual_tuning"] = False
        old = Editor()
        old.load(data)
        assert old.generator_tuning is None
        del data["manual_tuning"]
        older = Editor()
        older.load(data)
        assert older.generator_tuning is None
        editor.set_generator_tuning_component(1, 700.0)
        manual = Editor()
        manual.load(editor.serialize())
        assert manual.generator_tuning == editor.generator_tuning
        assert manual.manual_tuning is True

    def test_choose_form_drops_a_stale_manual_tuning_to_scheme_driven(self):
        editor = Editor()
        editor.set_generator_tuning_text("{1200.000 696.578]")
        editor.canonicalize_mapping()
        assert editor.effective_generator_tuning() is None
        assert editor.manual_tuning is False
        tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
        assert all(x > 0 for x in tuning_map)

    def test_preset_pick_drops_a_stale_manual_tuning(self):
        from rtt.app import presets
        editor = Editor()
        editor.set_generator_tuning_text("{1200.000 696.578]")
        editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS["5:Meantone"])
        assert editor.effective_generator_tuning() is None and editor.manual_tuning is False

    def test_comma_drag_drops_a_stale_manual_tuning_on_a_non_canonical_mapping(self):
        editor = Editor()
        assert editor.try_edit_mapping_text("[⟨12 19 28 34] ⟨19 30 44 53]]")
        optimum = editor.optimum_generator_tuning()
        editor.set_generator_tuning_text("{%f %f]" % optimum)
        editor.add_comma_to(0, 1)
        assert editor.state.mapping == ((1, 0, -4, -13), (0, 1, 4, 10))
        assert editor.effective_generator_tuning() is None and editor.manual_tuning is False

    def test_editor_optimized_flag_and_scheme_name_are_honest_on_a_nonstandard_domain(self):
        editor = Editor()
        assert editor.try_edit_mapping_text(BARBADOS_ALT)
        assert editor.tuning_is_optimized is True
        assert editor.displayed_tuning_scheme_name == "minimax-U"
        generators = editor.optimum_generator_tuning()
        assert round(generators[0], 3) == 1199.872 and round(generators[1], 3) == 951.106

    def test_a_typed_generator_tuning_drops_a_prior_projection_pin(self):
        ed = Editor()
        ed.settings["projection"] = True
        ed.set_unchanged_basis(("2/1", "10/9"))
        assert ed.projection_basis == ("2/1", "10/9")
        ed.set_generator_tuning_text("1200 697")
        assert ed.projection_basis == ()


    BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"
    BARBADOS_ALT = "2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}"
