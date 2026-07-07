from functools import partial

import pytest

from rtt.app import (
    grid_tables,
    service,
    settings,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_geometry_query as query,
    spreadsheet_models,
    spreadsheet_text,
)
from rtt.app.editor import Editor
from rtt.app.layout import Cell, Layout
from rtt.app.spreadsheet_decorations import _tile_groups
from rtt.app.spreadsheet_geometry import plain_text_band
from _spreadsheet_support import _memoized_build, _layout, _with, _in_commas


class TestOptimizationControls:
    def test_optimization_power_is_editable_only_with_alt_complexity(self):
        off = {c.id: c for c in _with("TILT minimax-S", optimization=True).cells}
        assert off["optimization:power"].kind == "power_display"
        assert off["optimization:power"].text == "∞"
        on = {c.id: c for c in _with("TILT minimax-S", optimization=True, weighting=True, alt_complexity=True).cells}
        assert on["optimization:power"].kind == "power_input"

    def test_all_interval_greys_and_locks_the_target_chooser(self):
        allint = {c.id: c for c in _with(scheme="minimax-S", presets=True).cells}
        assert allint["preset:target"].disabled is True
        based = {c.id: c for c in _with(scheme="TILT minimax-S", presets=True).cells}
        assert based["preset:target"].disabled is False

    def test_optimized_tuning_wraps_the_mean_damage_symbol_in_min(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"] = True

        def symbol(scheme, optimized):
            cells = {c.id: c for c in spreadsheet.build(
                base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
            return cells["optimization:mean_damage:symbol"].text

        assert symbol("TILT minimax-S", True) == "min(⟪𝐝⟫ₚ)"
        assert symbol("TILT minimax-S", False) == "⟪𝐝⟫ₚ"
        inner = "⟪𝒓𝐿⁻¹⟫" + grid_tables.SUB_OPEN + "dual(𝑞)" + grid_tables.SUB_CLOSE
        assert symbol("minimax-S", True) == "min(" + inner + ")"
        assert symbol("minimax-S", False) == inner

    def test_additional_tile_controls_gates_the_radios_and_power_controls(self):
        gated = {"control:slope", "control:q", "optimization:power", "optimization:mean_damage"}
        on = {c.id for c in _with(scheme="minimax-S", weighting=True, optimization=True).cells}
        off = {c.id for c in _with(scheme="minimax-S", weighting=True, optimization=True, tile_controls=False).cells}
        assert gated <= on
        assert not (gated & off), "'additional tile controls' off hides the slope radio and the power controls"

    def test_additional_tile_controls_gates_the_nonstandard_domain_approach_radio(self):
        st = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        on = spreadsheet.build(st, settings.defaults(), tuning_scheme="TILT minimax-S")
        off = spreadsheet.build(st, {**settings.defaults(), "tile_controls": False}, tuning_scheme="TILT minimax-S")
        assert on.approach_panel is not None
        assert off.approach_panel is None

    def test_minimized_mean_damage_prefixes_its_label_with_minimized(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"] = True

        def cap(scheme, optimized):
            cells = {c.id: c for c in spreadsheet.build(
                base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
            return cells["optimization:mean_damage:label"]

        assert cap("TILT minimax-S", True).text == "minimized power mean"
        assert cap("TILT minimax-S", False).text == "power mean"
        assert cap("minimax-S", True).text == "minimized retuning magnitude"
        assert cap("minimax-S", False).text == "retuning magnitude"
        assert cap("TILT minimax-S", True).height == 2 * spreadsheet_constants.TEXT_LINE
        assert cap("TILT minimax-S", False).height == spreadsheet_constants.TEXT_LINE
        assert cap("minimax-S", True).height == 3 * spreadsheet_constants.TEXT_LINE
        assert cap("minimax-S", False).height == 2 * spreadsheet_constants.TEXT_LINE

    def test_all_interval_mean_damage_aggregates_at_the_dual_norm_power_not_infinity(self):
        import pytest

        from rtt.library import tuning
        from rtt.library.parsing import parse_temperament_data

        s = settings.defaults()
        s["optimization"] = True
        base = service.from_mapping(((1, 0, -4), (0, 1, 4)))
        t = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")

        def mean_damage(scheme):
            cells = {c.id: c for c in spreadsheet.build(
                base, s, tuning_scheme=scheme, tuning_optimized=True).cells}
            return float(cells["optimization:mean_damage"].text)

        es = mean_damage("minimax-ES")
        assert es == pytest.approx(1.582, abs=1e-3)
        assert es != pytest.approx(2.214, abs=1e-2), "NOT the max (the pre-fix bug)"
        assert es == pytest.approx(
            tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-ES"), "minimax-ES"),
            abs=1e-3)
        superspace = mean_damage("minimax-S")
        assert superspace == pytest.approx(1.699, abs=1e-3)
        assert superspace == pytest.approx(
            tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-S"), "minimax-S"),
            abs=1e-3)
        assert mean_damage("held-octave minimax-ES") == pytest.approx(
            tuning.get_tuning_map_mean_damage(
                t, tuning.optimize_tuning_map(t, "held-octave minimax-ES"), "held-octave minimax-ES"),
            abs=1e-3)

    def test_all_interval_mean_damage_power_label_tracks_the_dual_norm_power(self):
        s = settings.defaults()
        s["optimization"] = True
        s["charts"] = True
        base = service.from_mapping(((1, 0, -4), (0, 1, 4)))

        def chart(scheme):
            cells = {c.id: c for c in spreadsheet.build(
                base, s, tuning_scheme=scheme, tuning_optimized=True).cells}
            return cells["chart:damage:targets"], cells["optimization:power"]

        es_chart, es_power = chart("minimax-ES")
        assert es_chart.indicator_label == "2"
        assert es_power.text == "∞"
        s_chart, s_power = chart("minimax-S")
        assert s_chart.indicator_label == "∞"
        assert s_power.text == "∞"

    def test_all_interval_relabels_the_target_list_as_prime_proxy(self):
        based = {c.id: c for c in _with(scheme="TILT minimax-S", symbols=True, equivalences=True).cells}
        assert based["symbol:vectors:targets"].text == "T"
        assert based["name:vectors:targets"].text == "target interval list"
        allint = {c.id: c for c in _with(scheme="minimax-S", symbols=True, equivalences=True).cells}
        assert allint["symbol:vectors:targets"].text == "Tₚ = 𝐼"
        assert allint["name:vectors:targets"].text == "prime proxy target interval list"

    def test_all_interval_mnemonics_underline_the_prime_proxy_p_subscript(self):
        based = {c.id: c for c in _with(scheme="TILT minimax-S", names=True, mnemonics=True).cells}
        based_cap = based["name:vectors:targets"]
        assert based_cap.underlines == ((based_cap.text.index("target"), 1),)
        allint = {c.id: c for c in _with(scheme="minimax-S", names=True, mnemonics=True).cells}
        cap = allint["name:vectors:targets"]
        assert cap.text == "prime proxy target interval list"
        assert set(cap.underlines) == {(cap.text.index("target"), 1),
                                       (cap.text.index("prime"), 1),
                                       (cap.text.index("proxy"), 1)}
        assert sorted(cap.text[s:s + n] for s, n in cap.underlines) == ["p", "p", "t"]

    def test_all_interval_target_list_plain_text_tracks_the_grid_identity(self):
        allint = {c.id: c for c in _with(scheme="minimax-S", plain_text_values=True).cells}
        based = {c.id: c for c in _with(scheme="TILT minimax-S", plain_text_values=True).cells}
        assert allint["plain_text:vectors:targets"].text == "[[1 0 0⟩ [0 1 0⟩ [0 0 1⟩]"
        assert allint["plain_text:vectors:targets"].text != based["plain_text:vectors:targets"].text

    def test_all_interval_relabels_the_complexity_weight_and_damage_equivalences(self):
        allint = {c.id: c for c in _with(scheme="minimax-S", symbols=True,
                                         equivalences=True, weighting=True).cells}
        assert allint["symbol:complexity:targets"].text == "𝒄 = diag(𝐿)"
        assert allint["symbol:weight:targets"].text == "𝒘 = diag(𝐿)⁻¹"
        assert allint["symbol:damage:targets"].text == "𝐝 = |𝒓|𝐿⁻¹"
        based = {c.id: c for c in _with(scheme="TILT minimax-S", symbols=True,
                                        equivalences=True, weighting=True).cells}
        assert based["symbol:complexity:targets"].text == "𝒄"
        assert based["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"
        assert based["symbol:damage:targets"].text == "𝐝 = |𝐞|𝒘"

    def test_a_non_diagonal_pretransformer_drops_the_complexity_diag_equivalence(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s.update(weighting=True, alt_complexity=True, symbols=True, header_symbols=True, equivalences=True)
        square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                                 custom_prescaler=square).cells}
        assert on["symbol:complexity:targets"].text == "𝒄", "NOT '𝒄 = diag(𝑋)'"
        assert on["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹", "the generic reciprocal, not a matrix inverse"
        assert on["matrix_label:column:weight:targets:0"].text == "w₁ = c₁⁻¹"

    def test_all_interval_show_entry_adds_a_checkbox_to_the_target_controls(self):
        off = {c.id for c in _with().cells}
        assert "control:all_interval" not in off and "label:all_interval" not in off
        on = {c.id: c for c in _with(all_interval=True).cells}
        chk = on["control:all_interval"]
        assert chk.kind == "control_check"
        assert chk.text == ""
        assert chk.checked is False
        cap = on["label:all_interval"]
        assert cap.kind == "label" and cap.text == "all-interval"
        assert abs((chk.x + chk.width / 2) - (cap.x + cap.width / 2)) < 1
        gap = (spreadsheet_constants.PRESET_HEIGHT - spreadsheet_constants.OPTION_CHECKBOX_PX) / 2
        assert cap.y == chk.y + chk.height + gap
        on_ai = {c.id: c for c in _with(scheme="minimax-S", all_interval=True).cells}
        assert on_ai["control:all_interval"].checked is True

    def test_control_checkbox_cell_matches_the_one_shared_option_checkbox_size(self):
        chk = {c.id: c for c in _with(all_interval=True).cells}["control:all_interval"]
        assert chk.height == spreadsheet_constants.OPTION_CHECKBOX_PX

    def test_all_interval_checkbox_rides_right_of_the_target_chooser_when_shown(self):
        on = {c.id: c for c in _with(all_interval=True, presets=True).cells}
        assert on["control:all_interval"].x > on["preset:target"].x

    def test_all_interval_checkbox_sits_inside_the_target_chooser_panel(self):
        layout = _with(all_interval=True, presets=True)
        cells = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        control_panel, tile = blocks["block:preset:target"], blocks["block:vector:targets"]
        for cell_id in ("control:all_interval", "label:all_interval"):
            c = cells[cell_id]
            assert control_panel.x <= c.x and c.x + c.width <= control_panel.x + control_panel.width
            assert control_panel.y <= c.y and c.y + c.height <= control_panel.y + control_panel.height
        assert tile.x <= control_panel.x and control_panel.x + control_panel.width <= tile.x + tile.width

    def test_all_interval_show_entry_is_live_not_a_greyed_stub(self):
        assert "all_interval" in settings.IMPLEMENTED, "the all-interval Show toggle reveals the in-grid control_panel-𝐓 checkbox (a two-step process); its # content is built, so the Show panel offers it live (interactive), not greyed out as a stub"

    def test_alt_complexity_lays_panel_l_out_with_just_the_diminuator_checkbox(self):
        off = {c.id for c in _with("TILT minimax-S", weighting=True, alt_complexity=False).cells}
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        assert "control:prescaler" not in on, "the prescaler is a preset now, not a panel-𝐋 control"
        assert "label:prescaler" not in on
        assert "label:diminuator" not in off
        cap_d = on["label:diminuator"]
        assert cap_d.kind == "label"
        assert cap_d.text == "replace diminuator"
        dimension = on["control:diminuator"]
        assert dimension.x == on["header:primes"].x + spreadsheet_constants.PANEL_INNER
        gap = (spreadsheet_constants.PRESET_HEIGHT - spreadsheet_constants.OPTION_CHECKBOX_PX) / 2
        assert cap_d.y == dimension.y + dimension.height + gap
        assert abs((dimension.x + dimension.width / 2) - (cap_d.x + cap_d.width / 2)) < 1

    def test_weighting_controls_each_sit_in_a_bordered_panel(self):
        layout = _with("TILT minimax-S", weighting=True, alt_complexity=True, presets=True)
        blocks = {b.id: b for b in layout.blocks}
        cells = {c.id: c for c in layout.cells}
        for panel_id, ctrl_id in (("block:preset:prescaler", "control:diminuator"),
                                ("block:complexity", "control:complexity"),
                                ("block:slope", "control:slope")):
            control_panel = blocks[panel_id]
            assert control_panel.paneled, panel_id
            control = cells[ctrl_id]
            assert control_panel.x < control.x and control.x + control.width <= control_panel.x + control_panel.width + 0.01, panel_id
            assert control_panel.y < control.y and control.y + control.height <= control_panel.y + control_panel.height + 0.01, panel_id

    def test_diminuator_rides_the_pretransformer_chooser_panel_when_presets_on(self):
        on = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                               {**settings.defaults(), "weighting": True, "alt_complexity": True, "presets": True},
                               tuning_scheme="TILT minimax-S")
        cells = {c.id: c for c in on.cells}
        blocks = {b.id for b in on.blocks}
        assert cells["control:diminuator"].x > cells["preset:prescaler"].x
        assert "block:diminuator" not in blocks
        off_blocks = {b.id for b in _with("TILT minimax-S", weighting=True, alt_complexity=True).blocks}
        assert "block:diminuator" in off_blocks

    def test_weighting_control_panels_layer_above_their_tile_panels(self):
        layout = _with("TILT minimax-S", weighting=True, alt_complexity=True)
        order = {b.id: i for i, b in enumerate(layout.blocks)}
        assert order["block:diminuator"] > order["block:prescaling:primes"]
        assert order["block:complexity"] > order["block:complexity:targets"]
        assert order["block:slope"] > order["block:weight:targets"]

    def test_alt_complexity_adds_an_ignore_diminuator_checkbox_to_panel_l(self):
        off = {c.id for c in _with("TILT minimax-S", weighting=True, alt_complexity=False).cells}
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        assert "control:diminuator" not in off
        control = on["control:diminuator"]
        assert control.kind == "control_check"
        assert control.text == ""
        assert control.checked is False
        assert on["header:primes"].x <= control.x

    def test_all_interval_greys_the_locked_target_chooser_name_but_not_the_power_value(self):
        on = {c.id: c for c in _with(scheme="minimax-S", optimization=True, presets=True).cells}
        assert on["block:preset:target:label"].disabled is True
        assert on["optimization:power:label"].disabled is False, "the power is a value: label not greyed"
        based = {c.id: c for c in _with(scheme="TILT minimax-S", optimization=True, presets=True).cells}
        assert based["block:preset:target:label"].disabled is False
        assert based["optimization:power:label"].disabled is False

    def test_panel_l_diminuator_needs_weighting_and_the_primes_column(self):
        assert "control:diminuator" not in {c.id for c in _with(weighting=False, alt_complexity=True).cells}, "the diminuator checkbox lives in panel 𝐋 (the prescaling matrix over the primes), so it # is gone if weighting is off or the temperament (primes) checkboxes are hidden"
        assert "control:diminuator" not in {
            c.id for c in _with(weighting=True, alt_complexity=True, temperament_tiles=False).cells
        }

    def test_alt_complexity_is_implemented_now_that_its_controls_are_built(self):
        assert "alt_complexity" in settings.IMPLEMENTED, "alt. complexity is un-shelved: its built controls (the panel-𝐋 diminuator checkbox, control_panel-𝒄's # established-complexity options, the alternative-complexity prescalers + tuning schemes) are # ready, so it rides in IMPLEMENTED as a live, interactive Show toggle rather than a greyed stub"

    def test_weighting_subcontrols_are_registered_under_weighting(self):
        keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
        assert {"all_interval", "alt_complexity", "custom_weights"} <= keys
        assert settings.SUBCONTROLS["all_interval"] == "weighting"
        assert settings.SUBCONTROLS["alt_complexity"] == "weighting"
        assert settings.SUBCONTROLS["custom_weights"] == "weighting"


class TestWeightSlopeControl:
    def test_weighting_names_the_weight_slope_chooser(self):
        on = {c.id: c for c in _with(weighting=True).cells}
        assert "control:slope" not in {c.id for c in _with(weighting=False).cells}
        assert on["control:slope"].label == "damage weight slope", \
            "without the custom option the three slopes ARE the whole control, so the group keeps 'slope'"

    def test_weighting_adds_a_weight_slope_chooser_to_the_weight_panel(self):
        off = {c.id for c in _with(weighting=False).cells}
        on = {c.id: c for c in _with(weighting=True).cells}
        assert "control:slope" not in off
        control = on["control:slope"]
        assert control.kind == "control_radio"
        assert control.disabled is False
        assert control.text == "unity-weight"
        assert control.values == ("complexity-weight", "unity-weight", "simplicity-weight")
        assert control.option_labels == ("complexity-weight", "unity-weight", "simplicity-weight"), \
            "without the custom option the option labels carry no redundant 'slope' suffix"
        assert control.y > on["weight:target:0"].y
        assert control.x == on["header:targets"].x + spreadsheet_constants.PANEL_INNER
        assert control.width == on["header:targets"].width - 2 * spreadsheet_constants.PANEL_INNER

    def test_custom_weights_toggle_appends_custom_and_moves_slope_onto_the_options(self):
        without = {c.id: c for c in _with(weighting=True).cells}["control:slope"]
        assert "custom" not in without.values
        assert without.label == "damage weight slope"
        with_custom = {c.id: c for c in _with(weighting=True, custom_weights=True).cells}["control:slope"]
        assert with_custom.values == ("complexity-weight", "unity-weight", "simplicity-weight", "custom")
        assert with_custom.option_labels == ("complexity-weight slope", "unity-weight slope", "simplicity-weight slope", "custom"), \
            "the toggle moves 'slope' onto the three options (custom is not a slope), so the group can host all four"
        assert with_custom.label == "damage weight"
        assert with_custom.disabled is False

    def test_the_slope_control_grows_to_hold_the_custom_option(self):
        three = {c.id: c for c in _with(weighting=True).cells}["control:slope"]
        four = {c.id: c for c in _with(weighting=True, custom_weights=True).cells}["control:slope"]
        assert four.height == spreadsheet_constants.radio_height(4)
        assert three.height == spreadsheet_constants.radio_height(3)
        assert four.height > three.height, "the panel reserves a taller band so the fourth option is not clipped"

    def test_all_interval_greys_and_locks_the_weight_slope_chooser(self):
        on = {c.id: c for c in _with(scheme="minimax-S", weighting=True).cells}
        control = on["control:slope"]
        assert control.disabled is True
        assert control.text == "simplicity-weight"
        assert control.label == "damage weight slope", "the label rides inside the radio, so it fades with the whole locked sub-panel"


class TestCustomWeightRow:
    def test_subcontrol_nesting_depth_drives_panel_indentation(self):
        assert settings.depth_of("tuning") == 0, "the panel indents each row by its nesting depth, so a child sits further right than its # parent. The 'tuning' grouping parent (depth 0) holds the two modes' shared base (tuning # checkboxes) plus the two modes — 'optimization' (Mode A) and 'projection' (Mode B) — at depth 1. # 'optimization' parents the optimize sub-axes (weighting, tuning ranges) at depth 2, and # weighting's three refinements (all-interval, alt. complexity, custom weights) at depth 3"
        assert settings.depth_of("tuning_tiles") == 1
        assert settings.depth_of("optimization") == 1
        assert settings.depth_of("projection") == 1
        assert settings.depth_of("tuning_colorization") == 1
        assert settings.depth_of("weighting") == 2
        assert settings.depth_of("tuning_ranges") == 2
        assert settings.depth_of("nonstandard_domain") == 2
        assert settings.depth_of("all_interval") == 3
        assert settings.depth_of("alt_complexity") == 3
        assert settings.depth_of("custom_weights") == 3
        assert settings.depth_of("temperament") == 0
        assert settings.depth_of("temperament_tiles") == 1
        assert settings.depth_of("temperament_colorization") == 1, "now level with the checkboxes, not under them"
        assert settings.depth_of("mnemonics") == 1

    def test_weight_equivalence_reflects_the_schemes_damage_slope(self):
        def equiv(scheme):
            layout = spreadsheet.build(
                service.from_mapping(((1, 1, 0), (0, 1, 4))),
                {**settings.defaults(), "weighting": True, "symbols": True, "equivalences": True},
                tuning_scheme=scheme,
            )
            return {c.id: c for c in layout.cells}["symbol:weight:targets"].text

        assert equiv("minimax-C") == "𝒘 = 𝒄"
        assert equiv("minimax-U") == "𝒘 = 𝟏"
        assert equiv("TILT minimax-S") == "𝒘 = 𝒄⁻¹"

    def test_damage_equivalence_names_the_weight_only_when_the_weight_row_is_shown(self):
        def equiv(scheme, weighting):
            layout = spreadsheet.build(
                service.from_mapping(((1, 1, 0), (0, 1, 4))),
                {**settings.defaults(), "weighting": weighting, "symbols": True, "equivalences": True},
                tuning_scheme=scheme,
            )
            return {c.id: c for c in layout.cells}["symbol:damage:targets"].text

        assert equiv("minimax-U", False) == "𝐝 = |𝐞|", "weighting hidden → bare |𝐞|, regardless of the scheme's weight slope (unity vs simplicity)"
        assert equiv("TILT minimax-S", False) == "𝐝 = |𝐞|"
        assert equiv("minimax-U", True) == "𝐝 = |𝐞|𝒘"
        assert equiv("TILT minimax-S", True) == "𝐝 = |𝐞|𝒘"

    def test_custom_weights_make_the_weight_row_editable(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True, "custom_weights": True}
        layout = spreadsheet.build(base, s, custom_weights=(1.0, 2.0, 3.0))
        weight_cells = [c for c in layout.cells if c.id.startswith("weight:target:")]
        assert weight_cells and all(c.kind == "weight_cell" for c in weight_cells)
        slope = next(c for c in layout.cells if c.id == "control:slope")
        assert slope.text == "custom", "the radio reads 'custom' while in custom mode"
        assert slope.disabled is False, "the slope stays live so a slope click exits custom mode"

    def test_custom_weights_stay_read_only_in_all_interval(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ai = {**settings.defaults(), "weighting": True, "custom_weights": True}
        layout = spreadsheet.build(base, ai, tuning_scheme="minimax-S", custom_weights=(1.0, 2.0, 3.0))
        assert all(c.kind != "weight_cell" for c in layout.cells if c.id.startswith("weight:target:"))

    def test_math_expressions_keep_the_weight_row_editable(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        m = {**settings.defaults(), "weighting": True, "custom_weights": True, "math_expressions": True}
        layout = spreadsheet.build(base, m, custom_weights=(1.0, 2.0, 3.0))
        weight_cells = [c for c in layout.cells if c.id.startswith("weight:target:")]
        assert weight_cells and all(c.kind == "weight_cell" for c in weight_cells)

    def test_custom_weights_show_the_overridden_values_in_the_weight_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True, "custom_weights": True}
        n = len([c for c in spreadsheet.build(base, s).cells if c.id.startswith("weight:target:")])
        override = tuple(1.0 + 0.5 * i for i in range(n))
        layout = spreadsheet.build(base, s, custom_weights=override)
        texts = [c.text for c in layout.cells if c.id.startswith("weight:target:")]
        assert texts == [service.cents(width) for width in override]

    def test_commas_have_a_shared_vertical_axis_per_comma(self):
        ids = {line.id for line in _layout().lines}
        assert "v:comma:0" in ids
        assert {"trunk:commas", "bus:commas:top", "bus:commas:bot", "foot:commas"} <= ids

    def test_collapsing_the_commas_column_hides_its_cells_but_keeps_the_header(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = spreadsheet.build(base)
        coll = spreadsheet.build(base, collapsed={"column:commas"})
        assert any(_in_commas(c.id) for c in full.cells)
        cids = {c.id for c in coll.cells}
        assert not any(_in_commas(c) for c in cids)
        assert "header:commas" in cids
        assert "toggle:column:commas" in cids
        assert coll.width < full.width

    def test_commas_column_has_panels_that_fold_away_and_converge_when_collapsed(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(base, collapsed={"column:commas"})
        blocks = {b.id: b for b in layout.blocks}
        by_id = {line.id: line for line in layout.lines}
        assert blocks["block:commas"].width == 0
        assert blocks["block:tuning:commas"].width == 0
        assert by_id["bus:commas:top"].length == 0

    def test_comma_basis_is_framed_as_a_vector_list_spanning_its_d_tall_height(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["bracket:vector:commas:l"].text == "[" and cells["bracket:vector:commas:r"].text == "]"
        assert "ebktop:vector:commas:0" in cells and "ebkangle:vector:commas:0" in cells
        cell = cells["bracket:vector:commas:l"]
        assert cell.y <= cells["cell:comma:0:0"].y
        assert cell.y + cell.height >= cells["cell:comma:2:0"].y + cells["cell:comma:2:0"].height

    def test_untempered_vector_columns_get_angle_feet_while_mapped_lists_keep_braces(self):
        cells = {c.id: c for c in _layout().cells}
        for group in ("commas", "targets"):
            assert f"ebkangle:vector:{group}:0" in cells
            assert f"ebkbrace:vector:{group}:0" not in cells
            assert f"ebktop:vector:{group}:0" in cells
        assert "ebkbrace:mapped:0" in cells and "ebkangle:mapped:0" not in cells
        assert "ebkbrace:mapped_comma:0" in cells and "ebkangle:mapped_comma:0" not in cells

    def test_comma_tuning_rows_get_list_brackets_hugging_their_values(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["bracket:tuning:commalist:l"].text == "[" and cells["bracket:tuning:commalist:r"].text == "]"
        l, r = cells["bracket:tuning:commalist:l"], cells["bracket:tuning:commalist:r"]
        assert l.x < cells["tuning:comma:0"].x < r.x

    def test_comma_basis_grid_has_no_separator_rules_that_double_its_cell_borders(self):
        two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])
        cells = {c.id for c in spreadsheet.build(two).cells}
        assert "cell:comma:0:1" in cells
        assert not any(c.startswith("sep:vector:commas") for c in cells)
        assert "sep:vector:targets:1" in cells

    def test_name_line_estimate_wraps_a_long_name_in_a_narrow_column(self):
        assert spreadsheet_text._wrap_lines("tempered target interval size list", 272) == 1
        assert spreadsheet_text._wrap_lines("tempered comma basis interval size list (made to vanish!)", 62) >= 3

    def test_a_long_name_widens_its_tile_to_stay_within_two_lines(self):
        layout = _with(names=True)
        cells = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        name = "tempered comma basis interval size list (made to vanish!)"
        cap = cells["name:tuning:commas"]
        assert spreadsheet_text._wrap_lines(name, cap.width) <= spreadsheet_constants.MAX_TEXT_LINES
        assert cap.height == spreadsheet_text._wrap_lines(name, cap.width) * spreadsheet_constants.TEXT_LINE + spreadsheet_constants.BAND_GAP
        assert cap.height <= spreadsheet_constants.MAX_TEXT_LINES * spreadsheet_constants.TEXT_LINE + spreadsheet_constants.BAND_GAP
        content_width = 2 * spreadsheet_constants.BRACKET_WIDTH + spreadsheet_constants.COLUMN_WIDTH
        assert cells["header:commas"].width > content_width
        assert cap.width == cells["header:commas"].width
        assert cap.y >= cells["tuning:comma:0"].y + spreadsheet_constants.ROW_HEIGHT
        panel = blocks["block:tuning:commas"]
        assert panel.x <= cap.x and cap.x + cap.width <= panel.x + panel.width

    def test_a_widened_name_tile_keeps_the_add_control_on_its_fan_stub(self):
        layout = _with(names=True)
        cells = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        narrow = {b.id: b for b in _with(names=False).blocks}
        by_id = {line.id: line for line in layout.lines}
        assert blocks["block:commas"].width > narrow["block:commas"].width
        plus, bus = cells["comma_plus"], by_id["bus:commas:top"]
        stub = by_id["v:comma:0"].position + spreadsheet_constants.COLUMN_WIDTH
        assert abs((plus.x + plus.width / 2) - stub) < 0.51, "the + tracks the fan, not the tile edge"
        assert abs((bus.start + bus.length) - stub) < 0.51

    def test_min_width_for_lines_floors_a_column_to_keep_a_name_within_two_lines(self):
        for name in ("tempered comma basis interval size list (made to vanish!)",
                     "comma basis interval retuning list (made to vanish!)",
                     "(just) comma basis interval size list"):
            width = spreadsheet_text._min_width_for_lines(name, 2)
            assert spreadsheet_text._wrap_lines(name, width) <= 2
            assert spreadsheet_text._wrap_lines(name, 2 * spreadsheet_constants.BRACKET_WIDTH + spreadsheet_constants.COLUMN_WIDTH) > 2

    def test_short_names_span_the_full_band_so_css_can_centre_them(self):
        cells = {c.id: c for c in _with(names=True).cells}
        short = cells["name:tuning:primes"]
        tall = cells["name:tuning:commas"]
        assert spreadsheet_text._wrap_lines(short.text, short.width) == 1
        assert spreadsheet_text._wrap_lines(tall.text, tall.width) == 2
        assert short.height == tall.height == spreadsheet_text._wrap_lines(tall.text, tall.width) * spreadsheet_constants.TEXT_LINE + spreadsheet_constants.BAND_GAP
        assert short.y == tall.y

    def test_comma_columns_get_in_tile_names_consistent_with_the_targets(self):
        on = {c.id: c for c in _with(names=True).cells}
        off = {c.id: c for c in _with(names=False).cells}
        assert on["name:vectors:commas"].text == "comma basis"
        assert on["name:mapping:commas"].text == "mapped comma basis (made to vanish!)"
        assert on["name:tuning:commas"].text == "tempered comma basis interval size list (made to vanish!)", "comma names mirror the target names, swapping 'target interval' for 'comma # basis interval'; the retuning row says 'retuning' (its symbol is 𝒓C) where the # targets' dedicated error vector 𝐞 reads 'error'. The rows the temperament zeroes # out — mapped, tempered, retuned — append '(made to vanish!)'; the just row shows # the comma's genuine untempered size, so it omits the note. (damage is the # exception — a target-only row, with no comma tile to name)"
        assert on["name:just:commas"].text == "(just) comma basis interval size list"
        assert on["name:retune:commas"].text == "comma basis interval retuning list (made to vanish!)"
        assert "name:damage:commas" not in on
        assert not any(c.startswith("name:") and c.endswith(":commas") for c in off)

    def test_interval_vectors_tiles_are_named_by_what_each_column_holds(self):
        on = {c.id: c for c in _with(names=True).cells}
        assert on["name:vectors:commas"].text == "comma basis"
        assert on["name:vectors:targets"].text == "target interval list"

    def test_commas_column_has_an_add_comma_control(self):
        cells = {c.id: c for c in _layout().cells}
        assert "comma_plus" in cells
        assert cells["comma_plus"].x > cells["comma:0"].x

    def test_each_comma_carries_its_own_minus_on_its_branch_point(self):
        layout = _layout()
        one, by1 = {c.id: c for c in layout.cells}, {line.id: line for line in layout.lines}
        assert "comma_minus:0" in one, "the SOLE comma is removable now (un-tempers to just intonation)"
        cm = one["comma_minus:0"]
        assert abs((cm.x + cm.width / 2) - by1["v:comma:0"].position) < 0.51
        assert cm.y == by1["bus:commas:top"].position
        two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])
        tlay = spreadsheet.build(two)
        cells, by2 = {c.id: c for c in tlay.cells}, {line.id: line for line in tlay.lines}
        assert {"comma_minus:0", "comma_minus:1"} <= set(cells), "any comma removable, not just the last"
        assert abs((cells["comma_minus:0"].x + cells["comma_minus:0"].width / 2) - by2["v:comma:0"].position) < 0.51
        assert abs((cells["comma_minus:1"].x + cells["comma_minus:1"].width / 2) - by2["v:comma:1"].position) < 0.51
        ji = service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        assert not any(c.startswith("comma_minus") for c in {c.id for c in spreadsheet.build(ji).cells})

    def test_adding_a_comma_starts_a_pending_draft_column_that_does_not_re_rank(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
        assert cells["comma:0"].text == "80/81"
        assert cells["comma:pending"].text == "?/?" and cells["comma:pending"].pending
        assert cells["comma:pending"].x > cells["comma:0"].x
        assert cells["cell:comma:0:1"].text == "" and cells["cell:comma:0:1"].pending
        assert "cell:mapping:1:0" in cells and "cell:mapping:2:0" not in cells, "the mapping is untouched (the draft is not yet a real comma): still 2 rows, no 3rd"
        assert "tuning:comma:1" not in cells
        by_id = {line.id: line for line in spreadsheet.build(base, pending_comma=[None, None, None]).lines}
        assert "comma_minus:0" in cells
        assert abs((cells["comma_minus:pending"].x + cells["comma_minus:pending"].width / 2) - by_id["v:comma:1"].position) < 0.51

    def test_a_partly_typed_pending_comma_shows_its_entered_components(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[4, None, 1]).cells}
        assert cells["cell:comma:0:1"].text == "4"
        assert cells["cell:comma:1:1"].text == ""
        assert cells["cell:comma:2:1"].text == "1"
        assert all(cells[f"cell:comma:{p}:1"].pending for p in range(3))

    def test_the_pending_comma_columns_ket_marks_are_flagged_for_green(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
        assert cells["ebktop:vector:commas:1"].pending and cells["ebkangle:vector:commas:1"].pending
        assert not cells["ebktop:vector:commas:0"].pending

    def test_the_pending_comma_greens_the_advanced_prescaling_matrix_draft_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        alt = settings.defaults(); alt["weighting"] = True; alt["alt_complexity"] = True
        cells = {c.id: c for c in spreadsheet.build(
            base, alt, tuning_scheme="TILT minimax-S", pending_comma=[None, None, None]).cells}
        draft = [k for k in cells if k.startswith("cell:prescaling:commas:") and k.endswith(":draft")]
        assert draft, "the prescaling matrix emits a comma-draft placeholder column"
        assert all(cells[k].pending and cells[k].text == "" for k in draft)
        assert abs(cells[draft[0]].x - cells["tuning:comma:draft"].x) < 0.5
        resting = {c.id: c for c in spreadsheet.build(base, alt, tuning_scheme="TILT minimax-S").cells}
        assert not any(k.startswith("cell:prescaling:") and k.endswith(":draft") for k in resting)

    def test_the_comma_basis_plain_text_becomes_a_two_tone_draft_field_while_pending(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["plain_text_values"] = True
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_comma=[None, None, None]).cells}
        assert drafting["plain_text:vectors:commas"].kind == "plain_text_pending"
        assert drafting["plain_text:mapping:primes"].kind == "plain_text_edit"
        resting = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert resting["plain_text:vectors:commas"].kind == "plain_text_edit"

    def test_adding_a_mapping_row_starts_a_pending_draft_row_that_does_not_re_rank(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[None, None, None]).cells}
        assert "cell:mapping:1:0" in cells and not cells["cell:mapping:1:0"].pending
        assert cells["cell:mapping:2:0"].text == "" and cells["cell:mapping:2:0"].pending
        assert cells["cell:mapping:2:0"].y - cells["cell:mapping:1:0"].y == spreadsheet_constants.ROW_HEIGHT
        assert "cell:mapping:3:0" not in cells
        assert cells["generator:pending"].text == "?" and cells["generator:pending"].pending
        assert cells["bracket:map:pending:l"].pending and cells["bracket:map:pending:r"].pending
        assert cells["map_minus:pending"].pending
        assert "generator:2" not in cells, "the temperament is untouched: the generator_map / canonical mapping stay at the committed rank (no 3rd # generator ratio). The derived mapped tiles DO get a blank green placeholder at the draft row, so # the whole row reads green across the band (the row mirror of a draft column reading green down)"
        assert cells["cell:mapped:2:0"].pending and cells["cell:mapped:2:0"].text == ""


class TestPendingGeneratorDraft:
    @staticmethod
    def _all_on():
        s = settings.defaults()
        for key in settings.IMPLEMENTED:
            s[key] = True
        return s

    def test_the_draft_greens_the_pending_column_of_the_inverse_form_and_mapped_generator_tiles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_generator=[None, None, None]).cells}
        assert all(cells[f"cell:inverse_form:{i}:draft"].pending and cells[f"cell:inverse_form:{i}:draft"].text == "" for i in range(2))
        assert all(cells[f"cell:selfmap:{i}:draft"].pending and cells[f"cell:selfmap:{i}:draft"].text == "" for i in range(2))
        assert cells["units_row:generators:2"].pending and not cells["units_row:generators:1"].pending
        assert abs(cells["cell:inverse_form:0:draft"].x - cells["generator:pending"].x) < 0.5
        assert abs(cells["cell:selfmap:0:draft"].x - cells["generator:pending"].x) < 0.5
        assert abs(cells["units_row:generators:2"].x - cells["generator:pending"].x) < 0.5

    def test_the_draft_also_greens_the_derived_mapping_and_canonical_rows_it_creates(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = spreadsheet.build(base, s)
        drafting = spreadsheet.build(base, s, pending_generator=[None, None, None])
        cells = {c.id: c for c in drafting.cells}
        assert all(cells[f"cell:mapping:2:{p}"].pending and cells[f"cell:mapping:2:{p}"].text == "" for p in range(3))
        assert all(cells[f"cell:canonical:2:{p}"].pending and cells[f"cell:canonical:2:{p}"].text == "" for p in range(3))
        assert cells["cell:mapped:2:0"].pending
        assert drafting.height > plain.height, "the new generator is also a new row, so the band grows like the mapping-row draft"
        assert "map_minus:pending" not in cells, "the generator ratio is entered in the generators column, so the mapping row is a derived placeholder, not an editable input"

    def test_without_a_draft_those_tiles_carry_no_pending_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ids = {c.id for c in spreadsheet.build(base, self._all_on()).cells}
        assert "cell:inverse_form:0:draft" not in ids
        assert "cell:selfmap:0:draft" not in ids
        assert "units_row:generators:2" not in ids

    def test_a_row_draft_also_greens_the_new_generators_derived_columns_and_a_canonical_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_mapping_row=[None, None, None]).cells}
        assert all(cells[f"cell:embed:{i}:draft"].pending for i in range(3))
        assert all(cells[f"cell:inverse_form:{i}:draft"].pending for i in range(2))
        assert all(cells[f"cell:selfmap:{i}:draft"].pending for i in range(2))
        assert cells["tuning:generator:pending"].pending
        assert all(cells[f"cell:canonical:2:{p}"].pending and cells[f"cell:canonical:2:{p}"].text == "" for p in range(3))


class TestPendingElementDraft:
    @staticmethod
    def _all_on():
        s = settings.defaults()
        for key in settings.IMPLEMENTED:
            s[key] = True
        return s

    def test_the_draft_grows_both_square_matrices_with_a_pending_row_and_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_element="7").cells}
        for prefix in ("cell:vector:primes", "cell:projection"):
            assert all(cells[f"{prefix}:{i}:3"].pending and cells[f"{prefix}:{i}:3"].text == "" for i in range(3))
            assert all(cells[f"{prefix}:3:{k}"].pending and cells[f"{prefix}:3:{k}"].text == "" for k in range(4))

    def test_the_new_prime_row_gets_its_own_bracket_and_the_fit_brackets_grow(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = {c.id: c for c in spreadsheet.build(base, s).cells}
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_element="7").cells}
        assert "bracket:vector:primes:3:l" in drafting and "bracket:vector:primes:3:l" not in plain
        assert "bracket:projection:3:l" in drafting and "bracket:projection:3:l" not in plain
        for fit in ("bracket:embed:l", "bracket:vector:targets:l", "bracket:projection_targets:l"):
            assert drafting[fit].height == plain[fit].height + spreadsheet_constants.ROW_HEIGHT

    def test_the_draft_grows_the_vectors_and_projection_bands_each_by_one_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = spreadsheet.build(base, s)
        drafting = spreadsheet.build(base, s, pending_element="7")
        assert drafting.height - plain.height == 2 * spreadsheet_constants.ROW_HEIGHT

    def test_without_a_draft_the_square_matrices_carry_no_pending_row_or_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ids = {c.id for c in spreadsheet.build(base, self._all_on()).cells}
        assert "cell:vector:primes:3:0" not in ids and "cell:vector:primes:0:3" not in ids
        assert "cell:projection:3:0" not in ids


class TestPendingMappingRow:
    def test_a_partly_typed_pending_mapping_row_shows_its_entered_components(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[0, None, 1]).cells}
        assert cells["cell:mapping:2:0"].text == "0"
        assert cells["cell:mapping:2:1"].text == ""
        assert cells["cell:mapping:2:2"].text == "1"
        assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))

    def test_a_pending_mapping_row_grows_only_the_mapping_band_by_one_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = spreadsheet.build(base)
        drafting = spreadsheet.build(base, pending_mapping_row=[None, None, None])
        assert drafting.height - plain.height == spreadsheet_constants.ROW_HEIGHT

    def test_the_mapping_plain_text_becomes_a_two_tone_draft_field_while_a_row_is_pending(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["plain_text_values"] = True
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
        assert drafting["plain_text:mapping:primes"].kind == "plain_text_pending"
        assert drafting["plain_text:vectors:commas"].kind == "plain_text_edit"
        resting = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert resting["plain_text:mapping:primes"].kind == "plain_text_edit"

    def test_the_mapped_list_brackets_grow_to_enclose_the_draft_rows_placeholders(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = {c.id: c for c in spreadsheet.build(base).cells}
        drafting = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[None, None, None]).cells}
        frame = ((spreadsheet_constants.FRAME_HEIGHT + spreadsheet_constants.FRAME_GAP) + (spreadsheet_constants.FRAME_GAP + spreadsheet_constants.BRACE_HEIGHT)
                 + 2 * spreadsheet_constants.FRAME_OVERHANG)
        for bid in ("bracket:mapped:l", "bracket:mapped_comma:l"):
            assert plain[bid].height == 2 * spreadsheet_constants.ROW_HEIGHT + frame
            assert drafting[bid].height == plain[bid].height + spreadsheet_constants.ROW_HEIGHT
        assert drafting["cell:mapped:2:0"].pending and drafting["cell:mapped:2:0"].text == ""
        assert drafting["cell:mapped_comma:2:0"].preview_remove and not drafting["cell:mapped_comma:2:0"].pending, "...but its cell over the doomed comma is red (the draft generator un-tempers it away), enclosed all the same"

    def test_a_comma_minus_hover_fills_the_born_generator_rows_derived_cells(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("comma", 0)).cells}
        assert [cells[f"cell:mapping:2:{p}"].text for p in range(3)] == ["0", "0", "1"]
        assert all(f"cell:mapped:2:{j}" in cells and cells[f"cell:mapped:2:{j}"].text != "" for j in range(2))

    def test_a_comma_minus_hover_ambers_the_surviving_mapping_rows_as_preview_change(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("comma", 0)).cells}
        for row in (0, 1):
            for p in range(3):
                cell = cells[f"cell:mapping:{row}:{p}"]
                assert cell.preview_change and not cell.preview_remove and not cell.pending
        assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))
        assert not any(cells[f"cell:mapping:2:{p}"].preview_change for p in range(3))
        assert cells["cell:comma:0:0"].preview_remove

    def test_a_mapping_minus_hover_fills_the_born_commas_derived_cells(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("row", 0)).cells}
        assert [cells[f"cell:comma:{p}:1"].text for p in range(3)] == ["0", "-4", "1"]
        assert cells["tuning:comma:draft"].text == "0.000"
        assert (cells["just:comma:draft"].text.lstrip("-")
                == cells["retune:comma:draft"].text.lstrip("-") != "0.000")
        assert cells["cell:mapped_comma:1:1"].text == "0"
        assert cells["cell:mapped_comma:0:1"].preview_remove

    def test_a_mapping_minus_hover_fills_the_born_commas_projection_and_complexity_rows(self):
        s = settings.defaults(); s["weighting"], s["projection"] = True, True
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S", preview_remove=("row", 0)).cells}
        assert cells["cell:scaling:draft"].text == "0"
        assert [cells[f"cell:projection_vectors:{p}:draft"].text for p in range(3)] == ["0", "0", "0"]
        pre = [cells[f"cell:prescaling:commas:{i}:draft"].text for i in range(3)]
        assert pre[0] == "0" and pre != ["", "", ""], "filled, not blank"
        assert cells["complexity:comma:draft"].text not in ("", "<MISSING>")
        assert cells["complexity:comma:draft"].pending
        assert all(cells[f"cell:prescaling:commas:{i}:draft"].pending for i in range(3))

    def test_a_comma_minus_hover_in_projection_births_an_unchanged_interval(self):
        s = settings.defaults(); s["projection"] = True
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = {c.id: c for c in spreadsheet.build(base, s).cells}
        hovered = {c.id: c for c in spreadsheet.build(base, s, preview_remove=("comma", 0)).cells}
        base_nu = sum(1 for i in plain if i.startswith("cell:unchanged:0:"))
        hov_nu = sum(1 for i in hovered if i.startswith("cell:unchanged:0:"))
        assert hov_nu == base_nu + 1
        born = hov_nu - 1
        assert [hovered[f"cell:unchanged:{p}:{born}"].text for p in range(3)] == ["0", "0", "1"]
        assert all(hovered[f"cell:unchanged:{p}:{born}"].pending for p in range(3))
        assert not any(hovered[f"cell:unchanged:{p}:0"].pending for p in range(3))
