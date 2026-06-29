from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


class TestShowToggles:
    def test_symbols_toggle_gates_the_control_label_symbols(self):
        editor = Editor()
        editor.set_show("optimization", True)
        editor.set_show("weighting", True)
        editor.set_weight_slope("complexity-weight")

        def ids() -> set[str]:
            return {c.id for c in editor.layout().cells}

        symbol_ids = {"optimization:power:symbol", "optimization:mean_damage:symbol", "symbol:q"}
        caption_ids = {"optimization:power:caption", "optimization:mean_damage:caption", "caption:q"}

        on = ids()
        assert symbol_ids <= on
        assert caption_ids <= on

        editor.set_show("symbols", False)
        off = ids()
        assert symbol_ids.isdisjoint(off)
        assert caption_ids <= off

    def test_hiding_control_symbols_collapses_the_symbol_band(self):
        editor = Editor()
        editor.set_show("optimization", True)

        def caption_top() -> float:
            return {c.id: c for c in editor.layout().cells}["optimization:power:caption"].y

        with_symbols = caption_top()
        editor.set_show("symbols", False)
        assert caption_top() < with_symbols

    def test_show_settings_start_at_defaults_and_changes_are_undoable(self):
        editor = Editor()
        assert editor.settings == settings.defaults()
        editor.set_show("charts", True)
        assert editor.settings["charts"] is True
        assert editor.can_undo is True
        editor.undo()
        assert editor.settings["charts"] is False
        editor.redo()
        assert editor.settings["charts"] is True

    def test_select_all_then_none_over_implemented_toggles(self):
        editor = Editor()
        editor.set_all_show(True)
        assert all(editor.settings[k] for k in settings.IMPLEMENTED)
        editor.set_all_show(False)
        assert not any(editor.settings[k] for k in settings.IMPLEMENTED)
        editor.undo()
        assert all(editor.settings[k] for k in settings.IMPLEMENTED)

    def test_deselecting_a_parent_also_deselects_its_subcontrols(self):
        editor = Editor()
        editor.set_show("temperament_colorization", True)
        assert editor.settings["temperament_colorization"] is True
        editor.set_show("temperament", False)
        assert editor.settings["temperament_tiles"] is False
        assert editor.settings["temperament_colorization"] is False

    def test_deselecting_a_parent_cascades_through_nested_subcontrols(self):
        editor = Editor()
        for key in ("weighting", "all_interval", "alt_complexity", "custom_weights",
                    "tuning_ranges", "optimization"):
            editor.set_show(key, True)
        editor.set_show("tuning", False)
        for key in ("tuning", "tuning_tiles", "weighting", "all_interval", "alt_complexity",
                    "custom_weights", "tuning_ranges", "optimization", "projection",
                    "tuning_colorization"):
            assert editor.settings[key] is False

    def test_deselecting_optimization_cascades_the_optimize_subaxes(self):
        editor = Editor()
        for key in ("weighting", "all_interval", "alt_complexity", "custom_weights", "tuning_ranges"):
            editor.set_show(key, True)
        editor.set_show("projection", True)
        editor.set_show("optimization", False)
        for key in ("optimization", "weighting", "all_interval", "alt_complexity",
                    "custom_weights", "tuning_ranges"):
            assert editor.settings[key] is False, key
        assert editor.settings["tuning"] is True
        assert editor.settings["projection"] is True

    def test_the_subcontrol_cascade_is_one_undoable_action(self):
        editor = Editor()
        editor.set_show("temperament_colorization", True)
        editor.set_show("temperament", False)
        assert editor.settings["temperament_colorization"] is False
        editor.undo()
        assert editor.settings["temperament"] is True
        assert editor.settings["temperament_tiles"] is True
        assert editor.settings["temperament_colorization"] is True

    def test_selecting_a_parent_does_not_force_its_subcontrols_on(self):
        editor = Editor()
        editor.set_show("temperament", False)
        editor.set_show("temperament", True)
        assert editor.settings["temperament_tiles"] is False
        assert editor.settings["temperament_colorization"] is False

    def test_selecting_a_subcontrol_pulls_its_parent_on(self):
        editor = Editor()
        editor.set_show("symbols", False)
        assert editor.settings["symbols"] is False, "off so the pull-on below is observable"
        assert editor.settings["equivalences"] is False
        editor.set_show("equivalences", True)
        assert editor.settings["equivalences"] is True
        assert editor.settings["symbols"] is True
        editor.set_show("names", False)
        editor.set_show("mnemonics", True)
        assert editor.settings["names"] is True

    def test_selecting_a_nested_subcontrol_pulls_its_whole_parent_chain_on(self):
        editor = Editor()
        editor.set_show("tuning", False)
        assert editor.settings["weighting"] is False
        editor.set_show("all_interval", True)
        for key in ("all_interval", "weighting", "optimization", "tuning"):
            assert editor.settings[key] is True
        assert editor.settings["tuning_tiles"] is False, "a sibling, not pulled on by all-interval"

    def test_grouping_parents_flatten_their_box_toggles_former_children(self):
        assert settings.SUBCONTROLS["temperament_colorization"] == "temperament", "the regroup is a flatten, not an extra nesting level: what used to be a direct child of a # box toggle is now a direct child of the GROUP, level with the box toggle (a sibling), not # buried under it. So 'temperament colorization' answers to 'temperament' (not to # 'temperament tiles'), and the whole tuning column answers to 'tuning' (not 'tuning tiles')"
        assert settings.SUBCONTROLS["temperament_tiles"] == "temperament"
        for key in ("tuning_tiles", "optimization", "projection", "tuning_colorization"):
            assert settings.SUBCONTROLS[key] == "tuning", key
        assert settings.SUBCONTROLS["weighting"] == "optimization"
        assert settings.SUBCONTROLS["tuning_ranges"] == "optimization"
        assert settings.SUBCONTROLS["all_interval"] == "weighting"
        assert settings.SUBCONTROLS["alt_complexity"] == "weighting"
        assert settings.SUBCONTROLS["custom_weights"] == "weighting"
        editor = Editor()
        editor.set_show("optimization", True)
        editor.set_show("tuning_tiles", False)
        assert editor.settings["optimization"] is True

    def test_form_is_a_live_layer_not_a_pure_grouping_parent(self):
        assert settings.DEFAULTS["form"] is False, "'form' heads the form group like temperament/tuning, but unlike those pure grouping parents # it carries a real grid layer (the canonical-form subscript C), so it is LIVE (in IMPLEMENTED) # and NOT in GROUPING_PARENTS. It defaults OFF (the subscript is opt-in, and its group starts # collapsed), and being implemented its saved value is honoured rather than pinned"
        assert "form" in settings.IMPLEMENTED
        assert "form" not in settings.GROUPING_PARENTS
        assert {"temperament", "tuning"} <= settings.GROUPING_PARENTS
        assert settings.from_persisted({"form": True})["form"] is True

    def test_expand_collapse_state_is_owned_and_undoable(self):
        editor = Editor()
        assert editor.collapsed == set()
        editor.toggle_collapsed("col:commas")
        assert "col:commas" in editor.collapsed
        assert editor.can_undo is True
        editor.undo()
        assert "col:commas" not in editor.collapsed
        editor.set_collapsed({"row:tuning"})
        assert editor.collapsed == {"row:tuning"}
        editor.undo()
        assert editor.collapsed == set()

    def test_reset_restores_every_default_as_one_undoable_action(self):
        editor = Editor()
        assert editor.can_reset is False
        editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
        editor.set_tuning_scheme("held-octave minimax-ES")
        editor.set_show("charts", True)
        editor.toggle_collapsed("col:commas")
        assert editor.can_reset is True
        editor.reset()
        assert editor.state.mapping == INITIAL_MAPPING
        assert service.base_scheme_name(editor.tuning_scheme) \
            == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)
        assert service.is_all_interval(editor.tuning_scheme) is False
        assert editor.settings == settings.defaults()
        assert editor.collapsed == set()
        assert editor.can_reset is False
        editor.undo()
        assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
        assert service.base_scheme_name(editor.tuning_scheme) == "held-octave minimax-ES"
        assert editor.settings["charts"] is True
        assert "col:commas" in editor.collapsed


class TestSerialization:
    def test_serialize_load_round_trips_the_whole_document(self):
        editor = Editor()
        editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
        editor.set_tuning_scheme("destretched-octave minimax-ES")
        editor.set_target_spec("9-OLD")
        editor.set_interest_vectors([[-1, 1, 0]])
        editor.set_held_vectors([[1, 0, 0]])
        editor.set_range_mode("tradeoff")
        editor.set_show("charts", True)
        editor.toggle_collapsed("col:commas")
        data = editor.serialize()

        restored = Editor()
        restored.load(data)
        assert restored.state.mapping == ((1, 0, -4), (0, 1, 4))
        restored_spec = service.resolve_tuning_scheme(restored.tuning_scheme)
        assert restored_spec == service.resolve_tuning_scheme(editor.tuning_scheme)
        assert service.base_scheme_name(restored.tuning_scheme) == "destretched-octave minimax-ES"
        assert restored_spec.target_intervals == "9-OLD"
        assert restored.target_spec == "9-OLD"
        assert restored.interest_vectors == [(-1, 1, 0)]
        assert restored.held_vectors == [(1, 0, 0)]
        assert restored.range_mode == "tradeoff"
        assert restored.settings["charts"] is True
        assert "col:commas" in restored.collapsed
        assert restored.can_undo is False, "a load is a fresh start, not an undoable step"

    def test_serialize_load_round_trips_a_finite_power_spec(self):
        editor = Editor()
        editor.set_optimization_power(2.0)
        restored = Editor()
        restored.load(editor.serialize())
        assert service.optimization_power(restored.tuning_scheme) == 2.0

    def test_serialize_load_round_trips_a_nonstandard_domain(self):
        editor = Editor()
        editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        restored = Editor()
        restored.load(editor.serialize())
        assert restored.state.domain_basis == (2, 3, Fraction(13, 5))
        assert restored.state.mapping == ((1, 2, 2), (0, -2, -3))

    def test_serialize_survives_the_json_layer_with_an_infinite_optimization_power(self):
        import json

        editor = Editor()
        editor.set_optimization_power(float("inf"))
        data = editor.serialize()
        assert data["tuning_scheme"]["optimization_power"] == "inf"
        json.loads(json.dumps(data))
        restored = Editor()
        restored.load(data)
        assert service.optimization_power(restored.tuning_scheme) == float("inf")

    def test_load_tolerates_a_state_saved_before_a_setting_existed(self):
        editor = Editor()
        data = editor.serialize()
        del data["settings"]["charts"]
        restored = Editor()
        restored.load(data)
        assert restored.settings["charts"] is settings.defaults()["charts"]

    def test_load_pins_a_shelved_toggle_to_its_default(self, monkeypatch):
        key = "form_colorization"
        monkeypatch.setattr(settings, "IMPLEMENTED", settings.IMPLEMENTED - {key})
        editor = Editor()
        data = editor.serialize()
        data["settings"][key] = not settings.DEFAULTS[key]
        restored = Editor()
        restored.load(data)
        assert restored.settings[key] is settings.DEFAULTS[key]

    def test_load_falls_back_when_the_core_fields_are_missing(self):
        editor = Editor()
        base = editor.serialize()

        no_scheme = dict(base)
        del no_scheme["tuning_scheme"]
        restored = Editor()
        restored.load(no_scheme)
        assert service.base_scheme_name(restored.tuning_scheme) \
            == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)

        both_missing = dict(base)
        del both_missing["mapping_ebk"]
        del both_missing["tuning_scheme"]
        Editor().load(both_missing)
