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
from rtt.app.layout import CellBox, Layout
from rtt.app.spreadsheet_decorations import _tile_groups
from rtt.app.spreadsheet_geometry import plain_text_band
from _spreadsheet_support import _memoized_build, _layout, _with, _with_interest, _INTEREST, _with_held, _target_count


class TestMathExpressions:
    def test_math_expressions_render_the_just_tuning_primes_as_logs(self):
        cells = {c.id: c for c in _with(math_expressions=True).cells}
        assert cells["just:prime:0"].kind == "mathexpr"
        assert cells["just:prime:0"].text == "1200 · log₂2\n= 1200.000"
        assert cells["just:prime:1"].text == "1200 · log₂3\n= 1901.955"
        assert cells["just:prime:2"].text == "1200 · log₂5\n= 2786.314"

    def test_math_expressions_render_the_just_target_sizes_as_logs(self):
        cells = {c.id: c for c in _with(math_expressions=True).cells}
        assert cells["just:target:1"].text == "1200 · log₂3\n= 1901.955"
        assert cells["just:target:2"].text == "1200 · log₂(3/2)\n= 701.955"

    def test_math_expressions_render_the_just_comma_sizes_as_logs(self):
        cells = {c.id: c for c in _with(math_expressions=True).cells}
        assert cells["just:comma:0"].kind == "mathexpr"
        assert cells["just:comma:0"].text == "1200 · log₂(80/81)\n= -21.506"

    def test_math_expressions_show_the_comma_error_as_a_log(self):
        cells = {c.id: c for c in _with(math_expressions=True).cells}
        assert cells["retune:comma:0"].text == "1200 · log₂(81/80)\n= 21.506"

    def test_math_expressions_leave_the_no_closed_form_cells_and_tiles_untouched(self):
        off = {c.id: c for c in _with().cells}
        on_lay = _with(math_expressions=True)
        on = {c.id: c for c in on_lay.cells}
        for cell_id in ("tuning:prime:1", "tuning:comma:0", "tuning:target:0",
                    "retune:prime:1", "damage:target:0"):
            assert on[cell_id].kind == "tuningvalue"
            assert on[cell_id].text == off[cell_id].text
        assert {"bracket:tuning:map:l", "caption:tuning:primes"} <= set(on)
        assert "block:tuning:primes" in {b.id for b in on_lay.blocks}

    def test_math_expressions_without_quantities_show_only_the_expression(self):
        cells = {c.id: c for c in _with(math_expressions=True, quantities=False).cells}
        assert cells["just:prime:1"].text == "1200 · log₂3"

    def test_math_expressions_render_rms_generators_as_prime_power_logs(self):
        cells = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True).cells}
        assert cells["tuning:gen:0"].kind == "mathexpr"
        assert cells["tuning:gen:0"].text == "1200 · log₂(2^(17/33)·3^(16/33)·5^(-4/33))\n= 1202.607"
        assert cells["tuning:gen:1"].text == "1200 · log₂(2^(-1/33)·3^(1/33)·5^(8/33))\n= 696.741"

    def test_math_expressions_render_rms_tempered_primes_as_prime_power_logs(self):
        cells = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True).cells}
        assert cells["tuning:prime:0"].kind == "mathexpr"
        assert cells["tuning:prime:0"].text == "1200 · log₂(2^(17/33)·3^(16/33)·5^(-4/33))\n= 1202.607"
        assert cells["tuning:prime:2"].text == "1200 · log₂(2^(-4/33)·3^(4/33)·5^(32/33))\n= 2786.965"

    def test_math_expressions_closed_form_value_equals_the_plain_cents(self):
        off = {c.id: c for c in _with(scheme="miniRMS-U").cells}
        on = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True).cells}
        for cell_id in ("tuning:gen:0", "tuning:gen:1", "tuning:prime:0", "tuning:prime:1", "tuning:prime:2"):
            assert on[cell_id].kind == "mathexpr"
            assert on[cell_id].text.endswith("= " + off[cell_id].text)

    def test_math_expressions_held_octave_rms_shows_the_octave_pure(self):
        cells = {c.id: c for c in _with(scheme="held-octave miniRMS-U", math_expressions=True).cells}
        assert cells["tuning:prime:0"].text == "1200 · log₂2\n= 1200.000"

    def test_math_expressions_skip_minimax_optimum_no_closed_form(self):
        off = {c.id: c for c in _with(scheme="minimax-S").cells}
        on = {c.id: c for c in _with(scheme="minimax-S", math_expressions=True).cells}
        for cell_id in ("tuning:gen:0", "tuning:gen:1", "tuning:prime:0", "tuning:prime:1"):
            assert on[cell_id].kind != "mathexpr"
            assert on[cell_id].text == off[cell_id].text

    def test_math_expressions_skip_weighted_rms_optimum_irrational(self):
        off = {c.id: c for c in _with(scheme="miniRMS-S").cells}
        on = {c.id: c for c in _with(scheme="miniRMS-S", math_expressions=True).cells}
        for cell_id in ("tuning:gen:0", "tuning:prime:0"):
            assert on[cell_id].kind != "mathexpr"
            assert on[cell_id].text == off[cell_id].text

    def test_math_expressions_show_exact_zero_as_bare_zero(self):
        cells = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True).cells}
        assert cells["tuning:comma:0"].kind == "mathexpr"
        assert cells["tuning:comma:0"].text == "0"

    def test_math_expressions_render_rms_retuning_map_as_prime_power_logs(self):
        off = {c.id: c for c in _with(scheme="miniRMS-U").cells}
        on = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True).cells}
        assert on["retune:prime:0"].kind == "mathexpr"
        assert on["retune:prime:0"].text == "1200 · log₂(2^(-16/33)·3^(16/33)·5^(-4/33))\n= " + off["retune:prime:0"].text
        assert on["retune:comma:0"].text == "1200 · log₂(81/80)\n= 21.506", "a tempered-out comma's error keeps the readable inverted-ratio form, not prime powers"

    def test_math_expressions_render_rms_canonical_generators_as_logs(self):
        off = {c.id: c for c in _with(scheme="miniRMS-U", form_tiles=True).cells}
        on = {c.id: c for c in _with(scheme="miniRMS-U", math_expressions=True, form_tiles=True).cells}
        for cell_id in ("tuning:cangen:0", "tuning:cangen:1"):
            assert on[cell_id].kind == "mathexpr"
            assert on[cell_id].text.endswith("= " + off[cell_id].text)

    def test_math_expressions_render_superspace_rms_tuning_as_logs(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        s.update(nonstandard_domain=True, math_expressions=True)
        off = {c.id: c for c in spreadsheet.build(state, {**s, "math_expressions": False}, tuning_scheme="miniRMS-U").cells}
        on = {c.id: c for c in spreadsheet.build(state, s, tuning_scheme="miniRMS-U").cells}
        for cell_id in ("tuning:superspace_prime:0", "tuning:superspace_generator:0", "retune:superspace_prime:1"):
            assert on[cell_id].kind == "mathexpr"
            assert "log₂" in on[cell_id].text
            assert on[cell_id].text.endswith("= " + off[cell_id].text)
        mini = {c.id: c for c in spreadsheet.build(state, s, tuning_scheme="minimax-S").cells}
        assert mini["tuning:superspace_prime:0"].kind == "tuningvalue"

    def test_math_expressions_skip_manual_generator_override(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "math_expressions": True},
            tuning_scheme="miniRMS-U", generator_tuning=(1200.0, 700.0),
        )
        cells = {c.id: c for c in layout.cells}
        assert cells["tuning:gen:0"].kind != "mathexpr"
        assert cells["tuning:gen:1"].text == "700.000"

    def test_math_expressions_is_an_interactive_toggle(self):
        assert "math_expressions" in settings.IMPLEMENTED, "it now builds content, so the panel must offer it live rather than greyed out"

    def test_math_expressions_render_the_prescaler_diagonal_as_logs(self):
        cells = {c.id: c for c in _with("minimax-S", weighting=True, math_expressions=True).cells}
        assert cells["cell:prescaling:primes:0:0"].kind == "prescalercell"
        assert cells["cell:prescaling:primes:0:0"].text == "1"
        assert cells["cell:prescaling:primes:1:1"].text == "1.585"
        assert cells["cell:prescaling:primes:2:2"].text == "2.322"
        assert cells["cell:prescaling:primes:0:1"].kind == "tuningvalue"
        assert cells["cell:prescaling:primes:0:1"].text == "0"

    def test_math_expressions_render_the_prescaled_comma_basis_as_logs(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, math_expressions=True).cells}
        assert cells["cell:prescaling:commas:0:0"].text == "4 · log₂2\n= 4"
        assert cells["cell:prescaling:commas:1:0"].text == "-4 · log₂3\n= -6.340"
        assert cells["cell:prescaling:commas:2:0"].text == "log₂5\n= 2.322"

    def test_math_expressions_without_quantities_show_only_the_prescaler_expression(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, math_expressions=True, quantities=False).cells}
        assert cells["cell:prescaling:primes:1:1"].kind == "prescalercell"
        assert cells["cell:prescaling:primes:1:1"].text == ""
        assert cells["cell:prescaling:primes:1:1"].blank is True
        assert cells["cell:prescaling:commas:1:0"].text == "-4 · log₂3"

    def test_math_expressions_under_prime_prescaler_drop_the_log(self):
        scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "prime")
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                                {**settings.defaults(), "weighting": True, "alt_complexity": True,
                                 "math_expressions": True},
                                tuning_scheme=scheme)
        cells = {c.id: c for c in layout.cells}
        assert cells["cell:prescaling:primes:0:0"].kind == "prescalercell", "the diagonal: each prime is the plain value (prescalercell, not mathexpr)"
        assert cells["cell:prescaling:primes:0:0"].text == "2"
        assert cells["cell:prescaling:primes:1:1"].text == "3"
        assert cells["cell:prescaling:primes:2:2"].text == "5"
        assert cells["cell:prescaling:commas:0:0"].text == "4 · 2\n= 8"
        assert cells["cell:prescaling:commas:1:0"].text == "-4 · 3\n= -12"

    def test_math_expressions_under_identity_prescaler_emit_no_closed_form(self):
        scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "identity")
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                                {**settings.defaults(), "weighting": True, "alt_complexity": True,
                                 "math_expressions": True},
                                tuning_scheme=scheme)
        cells = {c.id: c for c in layout.cells}
        assert cells["cell:prescaling:primes:1:1"].kind == "prescalercell"
        assert cells["cell:prescaling:primes:1:1"].text == "1"
        assert cells["cell:prescaling:commas:0:0"].kind == "tuningvalue"
        assert cells["cell:prescaling:commas:0:0"].text == "4"

    def test_bare_prescaler_diagonal_is_editable_prescalercell_kind(self):
        cells = {c.id: c for c in _with("minimax-S", weighting=True).cells}
        for i in range(3):
            assert cells[f"cell:prescaling:primes:{i}:{i}"].kind == "prescalercell"
        for i in range(3):
            for c in range(3):
                if i == c:
                    continue
                assert cells[f"cell:prescaling:primes:{i}:{c}"].kind == "tuningvalue"
                assert cells[f"cell:prescaling:primes:{i}:{c}"].text == "0"

    def test_bare_prescaler_diagonal_carries_its_prime_index(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        for i in range(3):
            assert cells[f"cell:prescaling:primes:{i}:{i}"].prime == i

    def test_custom_prescaler_override_drives_the_bare_prescaler_diagonal_text(self):
        s = settings.defaults() | {"weighting": True, "alt_complexity": True}
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                tuning_scheme="TILT minimax-S",
                                custom_prescaler=(2.5, 7.5, 11.0))
        cells = {c.id: c for c in layout.cells}
        assert cells["cell:prescaling:primes:0:0"].text == "2.500"
        assert cells["cell:prescaling:primes:1:1"].text == "7.500"
        assert cells["cell:prescaling:primes:2:2"].text == "11"

    def test_custom_prescaler_override_flows_into_the_product_tiles(self):
        s = settings.defaults() | {"weighting": True, "alt_complexity": True}
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                tuning_scheme="TILT minimax-S",
                                custom_prescaler=(1.0, 1.0, 2.0))
        cells = {c.id: c for c in layout.cells}
        assert cells["cell:prescaling:commas:0:0"].text == "4"
        assert cells["cell:prescaling:commas:1:0"].text == "-4"
        assert cells["cell:prescaling:commas:2:0"].text == "2"

    def test_custom_prescaler_override_drives_the_complexity_row(self):
        s = settings.defaults() | {"weighting": True}
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                tuning_scheme="TILT minimax-S",
                                custom_prescaler=(1.0, 1.0, 1.0))
        cells = {c.id: c for c in layout.cells}
        assert cells["complexity:comma:0"].text == "9.000"


class TestCountsRow:
    def test_custom_prescaler_override_drives_the_weight_row(self):
        s = settings.defaults() | {"weighting": True}
        scheme = f"TILT {service.DEFAULT_TUNING_SCHEME}"
        default = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, tuning_scheme=scheme)
        override = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                      tuning_scheme=scheme, custom_prescaler=(1.0, 1.0, 1.0))
        d_weights = [c.text for c in default.cells if c.id.startswith("weight:target:")]
        o_weights = [c.text for c in override.cells if c.id.startswith("weight:target:")]
        assert d_weights and o_weights and len(d_weights) == len(o_weights)
        assert d_weights != o_weights

    def test_counts_on_adds_a_top_row_of_per_column_cardinalities(self):
        cells = {c.id: c for c in _with(counts=True).cells}
        assert cells["count:gens"].text == "\U0001D45F = 2"
        assert cells["count:primes"].text == "\U0001D451 = 3"
        assert cells["count:commas"].text == "\U0001D45B = 1"
        assert cells["count:targets"].text == "\U0001D458 = 8"

    def test_counts_row_counts_the_generator_detempering_column_too(self):
        cells = {c.id: c for c in _with(counts=True, names=True, generator_detempering=True).cells}
        assert cells["count:detempering"].text == "\U0001D45F = 2"
        assert cells["count:detempering"].text == cells["count:gens"].text
        assert cells["caption:counts:detempering"].text == "rank", "the same name as the generators count, not a new one"
        assert "count:detempering" not in {c.id for c in _with(counts=True).cells}

    def test_counts_row_sits_at_the_top_aligned_over_its_columns(self):
        cells = {c.id: c for c in _with(counts=True).cells}
        assert cells["count:primes"].y < cells["prime:0"].y
        assert cells["count:targets"].y < cells["target:0"].y
        for column_key in ("gens", "primes", "targets"):
            assert cells[f"count:{column_key}"].x == cells[f"header:{column_key}"].x
            assert cells[f"count:{column_key}"].width == cells[f"header:{column_key}"].width

    def test_counts_present_keeps_the_column_fan_out_immediately_after_the_toggle(self):
        layout = _with(counts=True)
        by_id = {line.id: line for line in layout.lines}
        cells = {c.id: c for c in layout.cells}
        fan = by_id["bus:primes:top"].position
        count = cells["count:primes"]
        assert fan < count.y
        v0 = by_id["v:prime:0"]
        assert v0.start == fan
        assert v0.start < count.y and v0.start + v0.length > count.y + count.height
        trunk = by_id["trunk:primes"]
        assert trunk.start + trunk.length == fan
        assert fan == {line.id: line for line in _with(counts=False).lines}["bus:primes:top"].position

    def test_counts_on_by_default_shows_the_counts_row(self):
        cells = {c.id for c in _layout().cells}
        assert "label:counts" in cells
        assert any(c.startswith("count:") for c in cells)

    def test_count_names_caption_each_count_only_when_names_is_on(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        def captioned(names):
            s = settings.defaults()
            s["counts"], s["names"] = True, names
            return {c.id: c for c in spreadsheet.build(base, s).cells}

        on = captioned(names=True)
        assert on["caption:counts:gens"].text == "rank"
        assert on["caption:counts:primes"].text == "dimensionality"
        assert on["caption:counts:commas"].text == "nullity"
        assert on["caption:counts:targets"].text == "target interval count"
        assert on["caption:counts:primes"].y > on["count:primes"].y
        off = captioned(names=False)
        assert not any(c.startswith("caption:counts:") for c in off)
        assert {"count:gens", "count:primes", "count:targets"} <= set(off)

    def test_counts_row_collapses_like_any_other_keeping_its_label_and_gridline(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["counts"] = True
        full = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert "toggle:row:counts" in full
        layout = spreadsheet.build(base, s, collapsed={"row:counts"})
        cells = {c.id: c for c in layout.cells}
        assert not any(c.startswith("count:") for c in cells)
        assert "label:counts" in cells
        assert {line.id for line in layout.lines} >= {"h:counts"}

    def test_counts_track_the_live_domain_after_an_expand(self):
        expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        s = settings.defaults()
        s["counts"] = True
        cells = {c.id: c for c in spreadsheet.build(expanded, s).cells}
        assert cells["count:primes"].text == "\U0001D451 = 4"
        assert cells["count:gens"].text == "\U0001D45F = 3"

    def test_every_count_sits_on_its_own_grey_panel(self):
        layout = _with(counts=True)
        blocks = {b.id: b for b in layout.blocks}
        counts = [c.id for c in layout.cells if c.id.startswith("count:")]
        assert counts
        for cell_id in counts:
            column_key = cell_id.split(":", 1)[1]
            panel = blocks.get(f"block:counts:{column_key}")
            assert panel is not None, f"{cell_id} has no backing panel"
            assert panel.width > 0 and panel.height > 0

    def test_other_intervals_of_interest_column_is_present_right_of_targets(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["header:interest"].text == "other intervals\nof interest"
        assert "toggle:col:interest" in cells
        assert cells["header:interest"].x > cells["header:targets"].x

    def test_empty_interest_columns_footprint_hugs_its_content_the_title_overhangs(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["header:interest"].width == 2 * spreadsheet_constants.BRACKET_WIDTH
        assert cells["header:interest"].width < spreadsheet_text._title_w("other intervals\nof interest")

    def test_empty_interest_column_is_just_a_header_and_axis(self):
        layout = _layout()
        cids = {c.id for c in layout.cells}
        assert not any(c.startswith(("interest:", "cell:imapped:")) for c in cids)
        assert not any(c.startswith(("tuning:interest:", "just:interest:", "retune:interest:")) for c in cids)
        assert not any("imapped" in c for c in cids)
        assert "caption:mapping:interest" not in cids
        lids = {line.id for line in layout.lines}
        assert {"trunk:interest", "foot:interest"} <= lids
        assert "v:interest:0" not in lids and "bus:interest:top" not in lids


    _INTEREST = ((-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1))

    def test_populated_interest_renders_ratios_mapped_and_sizes_minus_damage(self):
        cells = {c.id: c for c in _with_interest(_INTEREST).cells}
        assert cells["interest:0"].text == "3/2" and cells["interest:3"].text == "8/5"
        assert cells["cell:imapped:0:0"].text == "0" and cells["cell:imapped:1:0"].text == "1"
        assert cells["cell:imapped:1:3"].text == "-4"
        assert {"tuning:interest:0", "just:interest:0", "retune:interest:3"} <= set(cells)
        assert cells["just:interest:0"].text == "701.955"
        assert not any(c.startswith("damage:interest") for c in cells), "...but NO damage row: these are not optimization targets"

    def test_populated_interest_renders_plain_text_for_all_its_value_tiles(self):
        s = settings.defaults()
        s["plain_text_values"] = True
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s, interest=_INTEREST).cells}
        assert cells["plain_text:vectors:interest"].text == "[-1 1 0⟩ [-3 2 0⟩ [1 -2 1⟩ [3 0 -1⟩"
        assert cells["plain_text:mapping:interest"].text == "[0 1} [-1 2} [-1 2} [3 -4}"
        assert {"plain_text:tuning:interest", "plain_text:just:interest", "plain_text:retune:interest"} <= set(cells)
        assert cells["plain_text:just:interest"].text == "701.955 203.910 182.404 813.686"

    def test_decimals_off_rounds_every_value_to_the_nearest_integer(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        on = {c.id: c for c in spreadsheet.build(base, settings.defaults(), interest=_INTEREST).cells}
        assert on["just:interest:0"].text == "701.955"

        s = {**settings.defaults(), "plain_text_values": True, "decimals": False}
        off = {c.id: c for c in spreadsheet.build(base, s, interest=_INTEREST).cells}
        assert off["just:interest:0"].text == "702"
        assert "." not in off["just:interest:0"].text
        assert off["plain_text:just:interest"].text == "702 204 182 814", "the plain-text EBK string rounds in lockstep, so the grid and the inline notation still match"

    def test_interest_intervals_are_editable_vectors_like_the_comma_basis(self):
        cells = {c.id: c for c in _with_interest(_INTEREST).cells}
        assert cells["cell:interest:0:0"].text == "-1"
        assert cells["cell:interest:1:0"].text == "1" and cells["cell:interest:2:0"].text == "0"
        assert cells["cell:interest:2:2"].text == "1"
        assert cells["cell:interest:0:0"].kind == "interestcell", "editable, not a static 'vector'"
        assert {"ebktop:vector:interest:0", "ebkangle:vector:interest:0",
                "ebktop:vector:interest:1", "ebkangle:vector:interest:1"} <= set(cells)
        assert "bracket:vector:interest:l" not in cells and "bracket:vector:interest:r" not in cells
        assert not any(c.startswith("sep:vector:interest:") for c in cells)

    def test_interest_vector_cells_are_separated_boxes_not_a_contiguous_grid(self):
        cells = {c.id: c for c in _with_interest(_INTEREST).cells}
        c0, c1 = cells["cell:interest:0:0"], cells["cell:interest:0:1"]
        m0 = cells["cell:imapped:0:0"]
        assert c0.width == m0.width == spreadsheet_constants.COLUMN_WIDTH
        assert c1.x - (c0.x + c0.width) == spreadsheet_constants.INTERVAL_COL_GAP / 2
        assert c0.x == m0.x

    def test_interest_has_add_and_per_interval_remove_controls(self):
        cells = {c.id: c for c in _with_interest(_INTEREST).cells}
        assert "interest_plus" in cells
        assert {"interest_minus:0", "interest_minus:1", "interest_minus:2", "interest_minus:3"} <= set(cells)

    def test_empty_but_open_interest_still_offers_the_add_control(self):
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), interest=()).cells}
        assert "interest_plus" in cells
        assert not any(c.startswith("interest_minus:") for c in cells)

    def test_adding_an_interval_of_interest_opens_a_blank_green_draft_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, interest=(), pending_interest=[None, None, None]).cells}
        assert cells["interest:pending"].text == "?/?" and cells["interest:pending"].pending
        assert all(cells[f"cell:interest:{p}:0"].text == "" and cells[f"cell:interest:{p}:0"].pending
                   for p in range(3))
        assert cells["tuning:interest:draft"].pending and cells["tuning:interest:draft"].text == "", "adding the FIRST interval lights every row the column crosses: the derived rows get blank # green placeholders at the draft column too, so it reads green top-to-bottom (not just the ket)"
        assert cells["cell:imapped:0:draft"].pending
        assert cells["interest_plus"].x > cells["interest:pending"].x
        assert "interest_minus:pending" in cells

    def test_a_partly_typed_interest_draft_shows_its_entered_components(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, interest=(), pending_interest=[-1, None, 0]).cells}
        assert cells["cell:interest:0:0"].text == "-1"
        assert cells["cell:interest:1:0"].text == ""
        assert cells["cell:interest:2:0"].text == "0"
        assert all(cells[f"cell:interest:{p}:0"].pending for p in range(3))

    def test_a_pending_interest_draft_rides_right_of_the_committed_intervals(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(
            base, interest=((-1, 1, 0),), pending_interest=[None, None, None]).cells}
        assert not cells["cell:interest:0:0"].pending
        assert cells["cell:interest:0:1"].pending and cells["cell:interest:0:1"].text == ""
        assert cells["interest:pending"].x > cells["interest:0"].x
        assert cells["ebkangle:vector:interest:1"].pending
        assert not cells["ebkangle:vector:interest:0"].pending

    def test_adding_a_held_interval_opens_a_blank_green_draft_column(self):
        cells = {c.id: c for c in _with_held((), pending_held=[None, None, None]).cells}
        assert cells["held:pending"].text == "?/?" and cells["held:pending"].pending
        assert all(cells[f"cell:held:{p}:0"].text == "" and cells[f"cell:held:{p}:0"].pending
                   for p in range(3))
        assert cells["tuning:held:draft"].pending and cells["tuning:held:draft"].text == ""
        assert cells["cell:hmapped:0:draft"].pending
        assert cells["held_plus"].x > cells["held:pending"].x
        assert "held_minus:pending" in cells
        assert cells["count:held"].text == "ℎ = 0", "the draft is not a committed held interval"

    def test_a_partly_typed_held_draft_shows_its_entered_components(self):
        cells = {c.id: c for c in _with_held((), pending_held=[1, None, 0]).cells}
        assert cells["cell:held:0:0"].text == "1"
        assert cells["cell:held:1:0"].text == ""
        assert cells["cell:held:2:0"].text == "0"
        assert all(cells[f"cell:held:{p}:0"].pending for p in range(3))

    def test_a_pending_held_draft_rides_right_of_the_committed_held_intervals(self):
        cells = {c.id: c for c in _with_held(((1, 0, 0),), pending_held=[None, None, None]).cells}
        assert not cells["cell:held:0:0"].pending
        assert cells["cell:held:0:1"].pending and cells["cell:held:0:1"].text == ""
        assert cells["held:pending"].x > cells["held:0"].x
        assert cells["ebkangle:vector:held:1"].pending
        assert not cells["ebkangle:vector:held:0"].pending

    def test_adding_a_target_opens_a_blank_green_draft_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        k = _target_count()
        cells = {c.id: c for c in spreadsheet.build(base, pending_target=[None, None, None]).cells}
        assert cells["target:pending"].text == "?/?" and cells["target:pending"].pending
        assert all(cells[f"cell:vector:targets:{k}:{p}"].text == "" and cells[f"cell:vector:targets:{k}:{p}"].pending
                   for p in range(3))
        assert cells["target:pending"].x > cells[f"target:{k - 1}"].x
        assert cells["target_plus"].x > cells["target:pending"].x
        assert "target_minus:pending" in cells

    def test_a_partly_typed_target_draft_shows_its_entered_components(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        k = _target_count()
        cells = {c.id: c for c in spreadsheet.build(base, pending_target=[-1, 1, None]).cells}
        assert cells[f"cell:vector:targets:{k}:0"].text == "-1"
        assert cells[f"cell:vector:targets:{k}:1"].text == "1"
        assert cells[f"cell:vector:targets:{k}:2"].text == ""
        assert all(cells[f"cell:vector:targets:{k}:{p}"].pending for p in range(3))


class TestPendingTargetDraft:
    def test_a_pending_target_draft_is_suppressed_in_all_interval_mode(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id for c in spreadsheet.build(base, tuning_scheme="minimax-S", pending_target=[None, None, None]).cells}
        assert "target:pending" not in cells
        assert not any(c.startswith("target_minus:pending") for c in cells)
