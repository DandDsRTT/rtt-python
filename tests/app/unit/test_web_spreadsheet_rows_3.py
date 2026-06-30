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
from _spreadsheet_support import _memoized_build, _layout, _with, _held, _color_at, _mid, _colormap_layout, _spine_colormap


class TestHeldColumn:
    def test_optimization_on_adds_an_addable_held_intervals_column(self):
        on = {c.id: c for c in _with(optimization=True).cells}
        off = {c.id for c in _with(optimization=False).cells}
        assert "header:held" in on
        assert "header:held" not in off
        assert on["header:commas"].x < on["header:held"].x < on["header:targets"].x
        assert "held_plus" in on
        assert "held_plus" not in off

    def test_held_intervals_are_a_user_editable_counted_interval_list(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"], s["counts"] = True, True
        cells = {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}
        assert cells["held:0"].text == "3/2"
        assert cells["cell:held:0:0"].kind == "heldcell"
        assert [cells[f"cell:held:{p}:0"].text for p in range(3)] == ["-1", "1", "0"]
        assert "held_minus:0" in cells
        assert cells["count:held"].text == "ℎ = 1"
        empty = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert empty["count:held"].text == "ℎ = 0"
        assert not any(c.startswith(("held:", "cell:held:")) for c in empty)

    def test_held_intervals_show_across_the_rows_like_the_other_intervals(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"] = True
        cells = {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}
        assert "cell:hmapped:0:0" in cells
        assert "tuning:held:0" in cells
        assert "just:held:0" in cells
        assert "retune:held:0" in cells
        assert abs(float(cells["retune:held:0"].text)) < 1e-3, "the held fifth is tuned exactly just, so its error reads ~0"

    def test_held_column_symbols_are_map_times_basis_products(self):
        on = _held(symbols=True, names=True, equivalences=False)
        assert on["symbol:vectors:held"].text == "H", "the held interval basis H lives in the interval-vectors row; like the comma column, # the held column has no dedicated letters — the rest are products of the maps and H"
        assert on["symbol:mapping:held"].text == "𝑀H"
        assert on["symbol:tuning:held"].text == "𝒕H"
        assert on["symbol:just:held"].text == "𝒋H"
        assert on["symbol:retune:held"].text == "𝒓H"

    def test_held_column_captions_are_full_held_interval_names(self):
        on = _held("TILT minimax-S", names=True, weighting=True, alt_complexity=True)
        assert on["caption:vectors:held"].text == "held interval basis", "full descriptive names mirroring the comma column ('held interval basis' in place of # 'comma basis'), without the comma column's '(made to vanish!)' — held intervals are held # just, not vanished"
        assert on["caption:mapping:held"].text == "mapped held interval basis"
        assert on["caption:tuning:held"].text == "tempered held interval basis interval size list"
        assert on["caption:just:held"].text == "(just) held interval basis interval size list"
        assert on["caption:retune:held"].text == "held interval basis interval retuning list"
        assert on["caption:prescaling:held"].text == "complexity prescaled held interval basis"
        assert on["caption:complexity:held"].text == "held interval basis interval complexity list"

    def test_held_interval_basis_caption_mnemonic_underlines_its_symbol_letter(self):
        on = _held(names=True, mnemonics=True)
        cap = on["caption:vectors:held"]
        assert cap.underlines == ((cap.text.index("held"), 1),)

    def test_held_column_equivalences_show_the_held_just_identities(self):
        on = _held(symbols=True, equivalences=True)
        assert on["symbol:tuning:held"].text == "𝒕H = 𝒋H", "held intervals are tuned exactly just: the tempered size equals the just size (and the # just size equals the tempered — the inverse identity, shown on the just row just below), # so the retuning error vanishes to the zero list"
        assert on["symbol:just:held"].text == "𝒋H = 𝒕H"
        assert on["symbol:retune:held"].text == "𝒓H = 𝟎"

    def test_held_column_shows_plain_text_values(self):
        on = _held(plain_text_values=True)
        assert on["plain_text:vectors:held"].text == "[[-1 1 0⟩]"
        assert on["plain_text:mapping:held"].text == "[[0 1}]"
        assert "plain_text:tuning:held" in on and "plain_text:just:held" in on
        assert abs(float(on["plain_text:retune:held"].text.strip("[]"))) < 1e-3
        assert "plain_text:quantities:held:0" not in on, "the quantities tile (the ratio heading the column) emits NO plain text — the gridded # ratio already is the formatted value, so a duplicate line would be redundant"

    def test_held_column_has_the_full_interval_column_tile_set(self):
        on = _held("TILT minimax-S", weighting=True, alt_complexity=True, domain_units=True)
        assert "cell:prescaling:held:0:0" in on
        assert "urow:held:0" in on

    def test_generator_detempering_column_holds_the_d_matrix(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["generator_detempering"] = True
        layout = spreadsheet.build(base, s)
        cells = {c.id: c for c in layout.cells}
        off = {c.id for c in _with(generator_detempering=False).cells}
        assert "header:detempering" in cells
        assert "header:detempering" not in off
        assert cells["header:primes"].x < cells["header:detempering"].x < cells["header:commas"].x
        assert [cells[f"cell:vector:detempering:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:vector:detempering:1:{p}"].text for p in range(3)] == ["-1", "1", "0"]
        assert "bracket:vector:detempering:l" in cells
        assert "trunk:detempering" in {line.id for line in layout.lines}

    def test_generator_detempering_vectors_tile_carries_the_D_symbol(self):
        cells = {c.id: c for c in _with(generator_detempering=True, symbols=True).cells}
        assert cells["symbol:vectors:detempering"].text == "D"
        named = {c.id: c for c in _with(generator_detempering=True, names=True, mnemonics=True).cells}
        cap = named["caption:vectors:detempering"]
        assert cap.underlines == ((cap.text.index("detempering"), 1),)

    def test_mapped_generator_detempering_renders_with_identity_objects(self):
        cells = {c.id: c for c in _with(identity_objects=True, generator_detempering=True, names=True,
                                        symbols=True, header_symbols=True, equivalences=True,
                                        plain_text_values=True).cells}
        for i in range(2):
            for k in range(2):
                assert cells[f"cell:mapped_detempering:{i}:{k}"].text == ("1" if i == k else "0")
                assert cells[f"cell:mapped_detempering:{i}:{k}"].kind == "mapped"
        assert cells["symbol:mapping:detempering"].text == "\U0001D440D = \U0001D43C"
        assert cells["caption:mapping:detempering"].text == "mapped generator detempering"
        assert cells["matlabel:col:mapping:detempering:0"].text == "\U0001D440\U0001D41D₁"
        assert cells["bracket:mapped_detempering:l"].text == spreadsheet_constants.GENMAP_BRACKETS[0]
        assert cells["ebktop:mapped_detempering:0"].kind == "ebktop"
        assert cells["ebkbrace:mapped_detempering:0"].kind == "ebkbrace"
        assert cells["plain_text:mapping:detempering"].text == "{[1 0} [0 1}]"

    def test_mapped_generator_detempering_gated_off_by_default(self):
        cells = {c.id for c in _with(generator_detempering=True, names=True, symbols=True,
                                     equivalences=True, plain_text_values=True).cells}
        assert not any("mapped_detempering" in c for c in cells)
        assert {"toggle:tile:mapping:detempering", "caption:mapping:detempering",
                "symbol:mapping:detempering", "plain_text:mapping:detempering"}.isdisjoint(cells)
        assert {"header:detempering", "cell:vector:detempering:0:0"} <= cells

    def test_generator_detempering_tuning_row_equals_the_genmap(self):
        cells = {c.id: c for c in _with(generator_detempering=True).cells}
        genmap = [cells[f"tuning:gen:{i}"].text for i in range(2)]
        assert [cells[f"tuning:detempering:{i}"].text for i in range(2)] == genmap
        assert cells["bracket:tuning:detempering:l"].text == "{"

    def test_generator_detempering_size_rows_are_just_and_retuning_lists(self):
        cells = {c.id: c for c in _with(generator_detempering=True, units=True).cells}
        assert [cells[f"just:detempering:{i}"].text for i in range(2)] == ["1200.000", "701.955"]
        assert cells["bracket:just:detemperinglist:l"].text == "["
        assert cells["bracket:retune:detemperinglist:l"].text == "["
        assert {f"retune:detempering:{i}" for i in range(2)} <= set(cells)
        assert cells["caption:tuning:detempering"].text == "(retempered) generator tuning map"
        assert cells["caption:just:detempering"].text == "(just) generator detempering interval size list"
        assert cells["caption:retune:detempering"].text == "generator detempering interval retuning list"
        for key in ("tuning", "just", "retune"):
            assert cells[f"units:{key}:detempering"].text == "units: ¢"

    def test_generator_detempering_size_row_symbols(self):
        eq = {c.id: c for c in _with(generator_detempering=True, symbols=True, equivalences=True).cells}
        assert eq["symbol:tuning:detempering"].text == "𝒕D = 𝒈"
        assert eq["symbol:just:detempering"].text == "𝒋D"
        assert eq["symbol:retune:detempering"].text == "𝒓D"

    def test_generator_detempering_size_rows_plain_text(self):
        cells = {c.id: c for c in _with(generator_detempering=True, plain_text_values=True).cells}
        assert cells["plain_text:tuning:detempering"].text == cells["plain_text:tuning:gens"].text, "the tuning row is the generator tuning map, so its plain text matches the genmap's ({ ])"
        assert cells["plain_text:just:detempering"].text == "[1200.000 701.955]"
        assert cells["plain_text:retune:detempering"].text.startswith("[")

    def test_generator_detempering_quantities_row_shows_the_generator_ratios(self):
        cells = {c.id: c for c in _with(generator_detempering=True).cells}
        assert [cells[f"detempering:{i}"].text for i in range(2)] == ["2/1", "3/2"]
        assert cells["detempering:0"].kind == "commaratio"

    def test_generator_detempering_quantities_emits_no_redundant_plain_text(self):
        ids = {c.id for c in _with(generator_detempering=True, plain_text_values=True).cells}
        assert not any(i.startswith("plain_text:quantities:detempering") for i in ids)

    def test_generator_detempering_prescaling_row_scales_each_vector(self):
        cells = {c.id: c for c in _with("TILT minimax-S", generator_detempering=True, weighting=True, alt_complexity=True, units=True).cells}
        assert [cells[f"cell:prescaling:detempering:{i}:0"].text for i in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:prescaling:detempering:{i}:1"].text for i in range(3)] == ["-1", "1.585", "0"]
        assert "ebktop:prescaling:detempering:0" in cells
        assert cells["bracket:prescaling:detempering:l"].text == "["
        assert cells["caption:prescaling:detempering"].text == "complexity prescaled generator detempering"
        assert cells["units:prescaling:detempering"].text == "units: oct"

    def test_generator_detempering_complexity_row_lists_each_complexity(self):
        cells = {c.id: c for c in _with("TILT minimax-S", generator_detempering=True, weighting=True, units=True).cells}
        assert [cells[f"complexity:detempering:{i}"].text for i in range(2)] == ["1.000", "2.585"]
        assert cells["bracket:complexity:detemperinglist:l"].text == "["
        assert cells["caption:complexity:detempering"].text == "generator detempering complexity list"
        assert cells["units:complexity:detempering"].text == "units: (C)"

    def test_generator_detempering_units_row_labels_each_generator(self):
        cells = {c.id: c for c in _with(generator_detempering=True, domain_units=True).cells}
        assert [cells[f"urow:detempering:{i}"].text for i in range(2)] == ["/1", "/1"]

    def test_generator_detempering_column_fans_without_a_centre_trunk(self):
        layout = _with(generator_detempering=True)
        assert sum(1 for line in layout.lines if line.id == "trunk:detempering") == 1
        assert sum(1 for line in layout.lines if line.id.startswith("v:detempering:")) == 2

    def test_gridline_ids_are_unique_across_every_fan_and_spine(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "generator_detempering": True, "optimization": True,
             "weighting": True, "form_tiles": True},
            interest=((-1, 1, 0), (2, 0, -1)),
            held_vectors=((1, 0, 0), (-1, 1, 0)),
        )
        ids = [line.id for line in layout.lines]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        assert dupes == [], f"duplicate gridline ids: {dupes}"

    def test_generator_detempering_toggle_is_implemented(self):
        assert "generator_detempering" in settings.IMPLEMENTED, "the column is built, so its Show toggle is live (interactive, not a greyed stub)"

    def test_optimization_toggle_is_implemented(self):
        assert "optimization" in settings.IMPLEMENTED, "the power line + held intervals column are built, so the toggle is live. (Its third # mockup column, unchanged intervals, is deferred to the projection feature.)"

    def test_charts_on_adds_a_damage_bar_chart_over_the_targets(self):
        on = {c.id: c for c in _with(charts=True).cells}
        off = {c.id for c in _with(charts=False).cells}
        assert "chart:damage:targets" not in off
        ch = on["chart:damage:targets"]
        assert ch.kind == "chart"
        assert len(ch.values) == 8
        assert all(v >= 0 for v in ch.values)

    def test_the_damage_chart_sits_above_its_values_and_reserves_row_space(self):
        off = {c.id: c for c in _with(charts=False).cells}
        on = {c.id: c for c in _with(charts=True).cells}
        ch, v0 = on["chart:damage:targets"], on["damage:target:0"]
        assert ch.y + ch.height <= v0.y
        assert on["damage:target:0"].y > off["damage:target:0"].y
        assert ch.x <= on["target:0"].x and ch.x + ch.width >= on["target:7"].x + spreadsheet_constants.COL_W, "the chart spans the target columns (so its bars can align with them)"


class TestRetuningChartsAndGenMap:
    def test_charts_on_adds_signed_retuning_charts_over_primes_and_targets(self):
        on = {c.id: c for c in _with(charts=True).cells}
        cp, ct = on["chart:retune:primes"], on["chart:retune:targets"]
        assert cp.kind == ct.kind == "chart"
        assert len(cp.values) == 3
        assert len(ct.values) == 8
        assert any(v < 0 for v in ct.values), "errors are signed, so the chart straddles zero"
        assert cp.y + cp.height <= on["retune:prime:0"].y
        assert ct.y + ct.height <= on["retune:target:0"].y

    def test_every_open_tile_in_the_retuning_row_is_charted(self):
        s = settings.defaults()
        s.update(charts=True, optimization=True, generator_detempering=True)
        on = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
            interest=((-3, 2, 0),),
            held_vectors=((-1, 1, 0),),
        ).cells}
        elem = {"primes": "prime", "commas": "comma", "targets": "target",
                "interest": "interest", "held": "held", "detempering": "detempering"}
        for group, e in elem.items():
            assert f"retune:{e}:0" in on, f"the retune {group} tile is missing"
            assert on[f"chart:retune:{group}"].kind == "chart", f"the retune {group} tile is not charted"

    def test_chart_bars_centre_on_their_value_gridlines(self):
        s = settings.defaults()
        s.update(charts=True, symbols=True, optimization=True, generator_detempering=True)
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
            interest=((-3, 2, 0),), held_vectors=((-1, 1, 0),))
        on = {c.id: c for c in layout.cells}
        gridline = {line.id: line.pos for line in layout.lines if line.orientation == "v"}
        bw, cw = spreadsheet_constants.BRACKET_W, spreadsheet_constants.COL_W
        elem = {"primes": "prime", "commas": "comma", "targets": "target",
                "interest": "interest", "held": "held", "detempering": "detempering"}
        for group, e in elem.items():
            ch = on[f"chart:retune:{group}"]
            for i in range(len(ch.values)):
                bar_centre = ch.x + bw + i * (cw + ch.col_gap) + cw / 2
                assert bar_centre == gridline[f"v:{e}:{i}"], f"{group} bar {i} is off its gridline"

    def test_generator_tuning_map_tile_shows_the_generator_map_cents_in_the_default_view(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        tuning_map = service.tuning(st.mapping, service.DEFAULT_DOCUMENT_SCHEME)
        cells = {c.id: c for c in _layout().cells}
        assert cells["tuning:gen:0"].text == service.cents(tuning_map.generator_map[0])
        assert cells["tuning:gen:1"].text == service.cents(tuning_map.generator_map[1])
        assert cells["header:gens"].x <= cells["tuning:gen:0"].x < cells["header:primes"].x
        assert cells["tuning:gen:1"].x == cells["tuning:gen:0"].x + spreadsheet_constants.COL_W
        assert cells["tuning:gen:0"].y == cells["tuning:prime:0"].y
        assert cells["bracket:tuning:genmap:l"].text == "{" and cells["bracket:tuning:genmap:r"].text == "]"
        assert cells["caption:tuning:gens"].text == "generator tuning map"

    def test_generator_tuning_map_gets_a_plain_text_value_band(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        on = {c.id: c for c in _with(plain_text_values=True).cells}
        assert "plain_text:tuning:gens" in on
        assert on["plain_text:tuning:gens"].text == service.plain_text_values(
            st, service.DEFAULT_DOCUMENT_SCHEME)[("tuning", "gens")]
        assert on["plain_text:tuning:gens"].text.startswith("{") and on["plain_text:tuning:gens"].text.endswith("]")

    def test_tuning_ranges_on_adds_a_generator_tuning_range_chart_in_the_generators_column(self):
        on = {c.id: c for c in _with(tuning_ranges=True).cells}
        off = {c.id for c in _with(tuning_ranges=False).cells}
        assert "rangechart:tuning:gens" not in off
        ch = on["rangechart:tuning:gens"]
        assert ch.kind == "rangechart"
        assert ch.x == on["header:gens"].x and ch.width == on["header:gens"].width, "it spans the generators column (so its per-generator I-beams align with the cells)"

    def test_generator_range_chart_carries_the_decimals_toggle(self):
        on = {c.id: c for c in _with(tuning_ranges=True).cells}["rangechart:tuning:gens"]
        off = {c.id: c for c in _with(tuning_ranges=True, decimals=False).cells}["rangechart:tuning:gens"]
        assert on.decimals is True
        assert off.decimals is False

    def test_the_ranges_chart_answers_to_tuning_ranges_not_charts(self):
        charts_only = {c.id for c in _with(charts=True, tuning_ranges=False).cells}
        ranges_only = {c.id for c in _with(charts=False, tuning_ranges=True).cells}
        assert "rangechart:tuning:gens" not in charts_only
        assert "rangechart:tuning:gens" in ranges_only

    def test_generator_tuning_range_chart_carries_the_monotone_ranges_by_default(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        tuning_map = service.tuning(st.mapping)
        ch = {c.id: c for c in _with(tuning_ranges=True).cells}["rangechart:tuning:gens"]
        assert ch.ranges == tuning_map.monotone_generator_range
        assert len(ch.ranges) == 2
        assert ch.ranges[0][0] == ch.ranges[0][1]
        assert ch.ranges[1][0] < ch.ranges[1][1]

    def test_range_mode_tradeoff_switches_the_chart_to_the_tradeoff_range(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        tuning_map = service.tuning(st.mapping)
        s = settings.defaults()
        s["tuning_ranges"] = True
        ch = {c.id: c for c in spreadsheet.build(st, s, range_mode="tradeoff").cells}["rangechart:tuning:gens"]
        assert ch.ranges == tuning_map.tradeoff_generator_range
        assert ch.ranges != tuning_map.monotone_generator_range

    def test_range_chart_draws_a_placeholder_when_no_monotone_range_exists(self):
        st = service.from_mapping(((1, 0, -1), (0, 1, -1)))
        assert service.tuning(st.mapping).monotone_generator_range is None
        s = settings.defaults()
        s["tuning_ranges"] = True
        ch = {c.id: c for c in spreadsheet.build(st, s, range_mode="monotone").cells}["rangechart:tuning:gens"]
        assert ch.ranges == ()

    def test_range_chart_nests_below_the_generator_map_values_inside_the_tile(self):
        on = {c.id: c for c in _with(tuning_ranges=True).cells}
        ch = on["rangechart:tuning:gens"]
        assert ch.y > on["tuning:gen:0"].y, "the chart sits below the generator-map values (nested at the bottom of the tile), # not floating over them"
        mapping_bottom = on["cell:mapping:1:0"].y + spreadsheet_constants.ROW_H
        assert ch.y >= mapping_bottom

    def test_range_mode_selector_sits_below_the_chart_and_carries_the_current_mode(self):
        on = {c.id: c for c in _with(tuning_ranges=True).cells}
        off = {c.id for c in _with(tuning_ranges=False).cells}
        assert "rangemode:tuning:gens" not in off
        selection, ch = on["rangemode:tuning:gens"], on["rangechart:tuning:gens"]
        assert selection.kind == "rangemode"
        assert selection.text == "monotone", "the live mode (default), so the renderer can preset it"
        assert selection.x == ch.x
        assert selection.y >= ch.y + ch.height

    def test_generator_tuning_map_panel_encloses_its_values_chart_and_selector(self):
        layout = _with(tuning_ranges=True)
        cells = {c.id: c for c in layout.cells}
        pan = {b.id: b for b in layout.blocks}["block:tuning:gens"]
        v, ch, selection = cells["tuning:gen:0"], cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
        assert pan.x <= ch.x and pan.x + pan.width >= ch.x + ch.width
        assert pan.y <= v.y
        assert pan.y + pan.height >= selection.y + selection.height
        assert "block:tuning:gens" in {b.id for b in _with(tuning_ranges=False).blocks}
        assert "block:gentuning" not in {b.id for b in layout.blocks}

    def test_tuning_ranges_box_has_a_left_aligned_boxtitle(self):
        layout = _with(tuning_ranges=True)
        cells = {c.id: c for c in layout.cells}
        boxes = {b.id: b for b in layout.blocks}
        title = cells["rangetitle:tuning:gens"]
        assert title.kind == "boxtitle" and title.text == "tuning ranges"
        chart, selection = cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
        assert title.y < chart.y
        assert title.x == cells["header:gens"].x
        box = boxes["block:tuning:rangesbox"]
        assert box.y <= title.y and box.y + box.height >= selection.y + selection.height

    def test_tuning_ranges_draws_a_bordered_box_around_the_chart_and_selector(self):
        layout = _with(tuning_ranges=True)
        boxes = {b.id: b for b in layout.blocks}
        cells = {c.id: c for c in layout.cells}
        assert "block:tuning:rangesbox" in boxes
        box = boxes["block:tuning:rangesbox"]
        assert box.boxed is True, "a bordered box, not a plain grey tile"
        ch, selection = cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
        assert box.x <= ch.x and box.x + box.width >= ch.x + ch.width
        assert box.y <= ch.y and box.y + box.height >= selection.y + selection.height
        assert "block:tuning:rangesbox" not in {b.id for b in _with(tuning_ranges=False).blocks}

    def test_tuning_ranges_box_reserves_row_height_so_following_rows_clear_it(self):
        layout = _with(tuning_ranges=True)
        cells = {c.id: c for c in layout.cells}
        panel = {b.id: b for b in layout.blocks}["block:tuning:gens"]
        box_bottom = panel.y + panel.height
        for nxt in ("just:prime:0", "retune:prime:0", "damage:target:0"):
            assert cells[nxt].y >= box_bottom, f"{nxt} overlaps the ranges box"
        off = {c.id: c for c in _with(tuning_ranges=False).cells}
        assert cells["just:prime:0"].y > off["just:prime:0"].y

    def test_colorization_follows_the_content_map(self):
        layout = _colormap_layout()
        cells = {c.id: c for c in layout.cells}
        Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
        at = lambda cell_id: _color_at(layout, *_mid(cells, cell_id))
        assert at("comma:0") == Y
        assert at("cell:comma:0:0") == Y
        assert at("prime:0") == Y
        assert at("qgen:0") == Y
        assert at("target:0") == C
        assert at("interest:0") == N
        assert at("held:0") == C
        assert at("basis:0") == N
        assert at("cell:vector:targets:0:0") == C
        assert at("cell:interest:0:0") == N
        assert at("cell:held:0:0") == C
        assert at("gen:0") == Y, "the generators in the spine are the generator basis — an input, carrying neither the # tuning map 𝒈 nor the embedding G — so by CONTENT they'd be neutral; but the quantities # spine column colours by its row's BAND (continuity), so the mapping row's generator # ratios take the mapping's temperament yellow (see test_spine_rows_and_columns_…)"
        assert at("cell:mapping:0:0") == Y
        assert at("cell:mapped_comma:0:0") == Y
        assert at("cell:mapped:0:0") == G
        assert at("cell:imapped:0:0") == Y
        assert at("cell:hmapped:0:0") == G
        assert at("tuning:gen:0") == G, "the generators column carries the generator basis B (yellow) in every tile, like the # primes column carries P — so the cyan genmap 𝒈 over it reads green; 𝒕 = 𝒈𝑀 over it is # green too (already had G·M). the retuning row 𝒓 = 𝒕 − 𝒋 keeps the 𝒈𝑀 term's G and 𝑀"
        for col in ("prime", "comma", "target", "interest", "held"):
            assert at(f"tuning:{col}:0") == G
            assert at(f"retune:{col}:0") == G
        assert at("just:prime:0") == G, "the just tuning map 𝒋 is cyan; its products green where the column also carries a # yellow object (primes P, commas C), stay cyan where the column is cyan (T, H)"
        assert at("just:comma:0") == G
        assert at("just:target:0") == C
        assert at("just:interest:0") == C
        assert at("just:held:0") == C
        assert at("damage:target:0") == G

    def test_off_by_default_rows_colorize_by_content_too(self):
        s = settings.defaults()
        s["temperament_colorization"] = True
        s["tuning_colorization"] = True
        s["form_tiles"] = True
        s["weighting"] = True
        s["alt_complexity"] = True
        s["optimization"] = True
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                tuning_scheme="TILT minimax-S",
                                interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))
        cells = {c.id: c for c in layout.cells}
        Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
        at = lambda cell_id: _color_at(layout, *_mid(cells, cell_id))
        assert at("cell:canon:0:0") == Y
        assert at("cell:prescaling:primes:0:0") == G
        assert at("cell:prescaling:commas:0:0") == G
        assert at("cell:prescaling:targets:0:0") == C
        assert at("cell:prescaling:interest:0:0") == C
        assert at("cell:prescaling:held:0:0") == C
        assert at("complexity:prime:0") == G
        assert at("complexity:comma:0") == G
        assert at("complexity:target:0") == C
        assert at("complexity:interest:0") == C
        assert at("complexity:held:0") == C
        assert at("weight:target:0") == C, "the weight 𝒘 incorporates the target complexity list (𝒘 = 𝒄 / 1 / 1∕𝒄), so it inherits # that list's cyan 𝑋 (and rides the cyan target column T) → cyan"

    def test_form_colorization_washes_the_canon_row_and_column(self):
        s = settings.defaults()
        s.update(form_tiles=True, form_colorization=True, temperament_colorization=True, tuning_colorization=True,
                 generator_detempering=True, optimization=True, projection=True, identity_objects=True)
        b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), settings=s,
                                     interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),), held_basis_ratios=("2/1", "5/4"))
        layout = b.layout()
        tg = partial(_tile_groups, b.resolved)
        RED, WHITE, GREEN = {"form", "temperament"}, {"form", "temperament", "tuning"}, {"temperament", "tuning"}
        assert tg("canon", "primes") == RED and tg("canon", "gens") == RED and tg("canon", "detempering") == RED
        assert tg("canon", "targets") == WHITE and tg("canon", "held") == WHITE
        assert tg("mapping", "canongens") == RED
        assert tg("projection", "canongens") == WHITE and tg("tuning", "canongens") == WHITE
        assert tg("projection", "primes") == GREEN and tg("projection", "gens") == GREEN
        assert tg("projection", "detempering") == {"tuning"} and tg("projection", "targets") == {"tuning"}
        assert tg("mapping", "primes") == {"temperament"}
        cells = {c.id: c for c in layout.cells}
        yc = cells["cell:canon_mapped:0:0"]
        x, y = yc.x + yc.width / 2, yc.y + yc.height / 2
        over = lambda pred: any(pred(bl) and bl.x <= x <= bl.x + bl.width and bl.y <= y <= bl.y + bl.height for bl in layout.blocks)
        assert over(lambda bl: bl.id.startswith("washbase:"))
        assert not over(lambda bl: bl.tint in ("temperament", "tuning", "form"))
        rank = cells["count:gens"]
        gx, cgx = cells["cell:form:0:0"].x + 5, cells["cell:fcancel:0:0"].x + 5
        in_band = lambda bx, tint: any(bl.tint == tint and bl.x <= bx <= bl.x + bl.width
                                       and bl.y <= rank.y + rank.height / 2 <= bl.y + bl.height for bl in layout.blocks)
        assert in_band(gx, "temperament") and not in_band(gx, "form")
        assert in_band(cgx, "temperament") and in_band(cgx, "form")

    def test_form_colorization_is_a_layer_the_other_colorizations_compose_with(self):
        def active(**toggles):
            s = settings.defaults()
            s.update(form=True, form_tiles=True, projection=True, **toggles)
            b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), settings=s,
                                         held_basis_ratios=("2/1", "5/4"))
            b.layout()
            return {g for g in _tile_groups(b.resolved, "tuning", "canongens") if s.get(f"{g}_colorization")}
        assert active(tuning_colorization=True) == {"tuning"}
        assert active(tuning_colorization=True, temperament_colorization=True) == {"tuning", "temperament"}
        assert active(tuning_colorization=True, temperament_colorization=True,
                      form_colorization=True) == {"tuning", "temperament", "form"}

    def test_generator_detempering_column_colorizes_by_content(self):
        s = settings.defaults()
        s["tuning_colorization"] = True
        s["temperament_colorization"] = True
        s["generator_detempering"] = True
        s["weighting"] = True
        s["alt_complexity"] = True
        s["audio"] = True
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                tuning_scheme="TILT minimax-S")
        cells = {c.id: c for c in layout.cells}
        Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
        at = lambda cell_id: _color_at(layout, *_mid(cells, cell_id))
        assert at("detempering:0") == N
        assert at("cell:vector:detempering:0:0") == N
        assert at("tuning:detempering:0") == G
        assert at("just:detempering:0") == C
        assert at("retune:detempering:0") == G
        assert at("cell:prescaling:detempering:0:0") == C
        assert at("complexity:detempering:0") == C

    def test_spine_rows_and_columns_colorize_by_their_band(self):
        layout = _spine_colormap()
        cells = {c.id: c for c in layout.cells}
        Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
        at = lambda cell_id: _color_at(layout, *_mid(cells, cell_id))
        for spine in ("count", "urow"):
            suffix = ":0" if spine == "urow" else ""
            assert at(f"{spine}:commas{suffix}") == Y
            assert at(f"{spine}:primes{suffix}") == Y
            assert at(f"{spine}:gens{suffix}") == Y
            assert at(f"{spine}:targets{suffix}") == C
            assert at(f"{spine}:held{suffix}") == C
            assert at(f"{spine}:detempering{suffix}") == N
        assert at("gen:0") == Y, "quantities + units COLUMNS take each row's family: mapping yellow; tuning, just, # retuning, prescaling, complexity cyan. The retuning units cell is cyan despite the # retuning VALUE cells being green — the spine follows the band, not the content"
        assert at("ucol:mapping:0") == Y
        assert at("ucol:tuning") == C
        assert at("ucol:just") == C
        assert at("ucol:retune") == C
        assert at("ucol:prescaling:0") == C
        assert at("ucol:complexity") == C

    def test_washes_bridge_the_plus_column_gutters(self):
        layout = _colormap_layout()
        cells = {c.id: c for c in layout.cells}
        height = lambda k: cells[f"header:{k}"]
        primes_commas = (height("primes").x + height("primes").width + height("commas").x) / 2
        commas_targets = (height("commas").x + height("commas").width + height("targets").x) / 2
        map_y = _mid(cells, "cell:mapping:0:0")[1]
        tun_y = _mid(cells, "tuning:prime:0")[1]
        assert "temperament" in _color_at(layout, primes_commas, map_y)
        assert "temperament" in _color_at(layout, commas_targets, map_y)
        assert {"temperament", "tuning"} <= _color_at(layout, commas_targets, tun_y)

    def test_colorization_off_by_default_and_renders_as_base_plus_darken_bands(self):
        assert not any(b.id.startswith(("wash:", "washbase:")) for b in _layout().blocks)
        blocks = _with(tuning_colorization=True).blocks
        washes = {b.id.split(":", 1)[1]: b for b in blocks if b.tint == "tuning"}
        bases = {b.id.split(":", 1)[1]: b for b in blocks if b.tint == "base"}
        assert washes and set(washes) == set(bases)
        for k, width in washes.items():
            b = bases[k]
            assert (b.x, b.y, b.width, b.height) == (width.x, width.y, width.width, width.height)
        assert all(b.tint == "" for b in blocks if b.id.startswith("block:"))

    def test_collapsing_a_tile_removes_its_colorization(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["tuning_colorization"] = s["temperament_colorization"] = True
        open_ids = {b.id for b in spreadsheet.build(base, s).blocks if b.tint in ("tuning", "temperament")}
        assert "wash:tuning:tuning:targets" in open_ids
        assert "wash:temperament:mapping:primes" in open_ids
        folded = spreadsheet.build(base, s, collapsed={"row:tuning", "tile:mapping:primes"})
        folded_ids = {b.id for b in folded.blocks if b.tint in ("tuning", "temperament")}
        assert "wash:tuning:tuning:targets" not in folded_ids
        assert "wash:temperament:mapping:primes" not in folded_ids
        assert "wash:temperament:vectors:commas" in folded_ids

    def test_mapped_comma_basis_vanishes_and_the_damage_weight_is_bold_italic(self):
        on = {c.id: c for c in _with(weighting=True, symbols=True, equivalences=True).cells}
        assert on["symbol:mapping:commas"].text == "𝑀C = O"
        assert on["symbol:damage:targets"].text == "𝐝 = |𝐞|𝒘", "the damage weight w is bold-italic (matching the maps), not bold-upright"
