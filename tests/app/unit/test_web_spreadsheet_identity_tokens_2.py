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
from _spreadsheet_support import _memoized_build, _layout, _with, _projection_build, _maximized_superspace_builder, _foldable, _EBK_OPEN, _EBK_CLOSE, _ebk_text_convention, _ebk_grid_convention, _ebk_canonical, _ebk_table_canonical


class TestCanonicalGenerators:
    def test_canonical_generators_render_as_a_ratio_list_over_the_column_and_in_the_spine(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        assert cells["cangen:0"].text == "2/1" and cells["cangen:1"].text == "3/1"
        assert cells["cangen:0"].kind == "genratio"
        assert cells["canon:gen:0"].text == "2/1" and cells["canon:gen:1"].text == "3/1"
        assert cells["canon:gen:0"].x == cells["header:quantities"].x
        assert cells["cangen:0"].x == cells["header:canongens"].x + spreadsheet_constants.BRACKET_W
        assert cells["cangen:0"].y < cells["canon:gen:0"].y

    def test_form_matrices_canceling_out_is_an_identity_tile_in_the_canonical_generators_column(self):
        cells = {c.id: c for c in _with(form_tiles=True, identity_objects=True).cells}
        assert cells["cell:fcancel:0:0"].text == "1" and cells["cell:fcancel:0:1"].text == "0"
        assert cells["cell:fcancel:1:0"].text == "0" and cells["cell:fcancel:1:1"].text == "1"
        assert cells["bracket:fcancel:map:0:l"].text == "{" and cells["bracket:fcancel:map:0:r"].text == "]"
        assert "ebktop:fcancel" in cells and "ebkbrace:fcancel" in cells
        assert cells["caption:canon:canongens"].text == "form matrices canceling out"
        assert cells["cell:fcancel:0:0"].x == cells["cangen:0"].x
        assert cells["cell:fcancel:0:0"].x < cells["cell:form:0:0"].x
        form_only = {c.id for c in _with(form_tiles=True).cells}
        assert "cangen:0" in form_only and "cell:fcancel:0:0" not in form_only

    def test_form_box_symbols_and_units_match_the_canonical_notation(self):
        from rtt.app.grid_tables import SUBSCRIPT_C
        gc = f"g{SUBSCRIPT_C}"
        cells = {c.id: c for c in _with(form_tiles=True, identity_objects=True,
                                        symbols=True, equivalences=True, header_symbols=True,
                                        units=True, domain_units=True).cells}
        assert cells["symbol:canon:primes"].text == f"𝑀{SUBSCRIPT_C}"
        assert cells["symbol:canon:gens"].text == "𝐹⁻¹"
        assert cells["symbol:mapping:canongens"].text == "𝐹"
        assert cells["symbol:canon:canongens"].text == "𝐹⁻¹𝐹 = 𝐼"
        assert cells["matlabel:row:canon:primes:0"].text == f"𝒎{SUBSCRIPT_C}₁"
        assert cells["units:canon:primes"].text == f"units: {gc}/p"
        assert cells["units:canon:gens"].text == f"units: {gc}/g"
        assert cells["units:canon:canongens"].text == f"units: {gc}/{gc}"
        assert cells["ucol:canon:0"].text == f"{gc}₁/"
        assert cells["urow:canongens:0"].text == f"/{gc}₁"

    def test_rank_count_merges_across_the_canonical_generators_and_generators_columns(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        rank, hcan, hgen = cells["count:gens"], cells["header:canongens"], cells["header:gens"]
        assert rank.text.endswith(" = 2")
        assert rank.x <= hcan.x and rank.x + rank.w >= hgen.x
        assert cells["caption:counts:gens"].text == "rank"
        assert "count:canongens" not in cells
        plain = {c.id: c for c in _layout().cells}
        assert plain["count:gens"].x == plain["header:gens"].x

    def test_form_matrix_row_labels_get_a_balanced_matlabel_gutter(self):
        cells = {c.id: c for c in _with(form_tiles=True, header_symbols=True).cells}
        flabel, fbracket = cells["matlabel:row:mapping:canongens:0"], cells["bracket:finv:map:0:l"]
        assert flabel.text == "𝒇₁"
        assert flabel.x + flabel.w <= fbracket.x, "the label sits left of (or up to) the { bracket, not over it"
        assert flabel.w > 0 and fbracket.x - flabel.x >= flabel.w

    def test_canonical_generators_column_builds_finv_embedding_and_tuning_tiles(self):
        from rtt.app.grid_tables import SUBSCRIPT_C
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"),
                                              form_tiles=True, symbols=True, header_symbols=True).cells}
        assert cells["cell:finv:0:0"].text == "1" and cells["cell:finv:0:1"].text == "1", "𝐹 (generator form matrix) over the mapping row: M = F·M_C, so F = ((1,1),(0,1)) (cell id is the # historical 'cell:finv' from before the 𝐹/𝐹⁻¹ swap)"
        assert cells["cell:finv:1:0"].text == "0" and cells["cell:finv:1:1"].text == "1"
        assert cells["symbol:mapping:canongens"].text == "𝐹"
        assert "bracket:finv:map:0:l" in cells
        assert cells["cell:embed_c:0:0"].text == "1" and cells["cell:embed_c:0:1"].text == "1"
        assert cells["cell:embed_c:2:1"].text == "1/4"
        assert cells["symbol:projection:canongens"].text == f"G{SUBSCRIPT_C}"
        assert cells["tuning:cangen:0"].text.startswith("1200")
        assert cells["tuning:cangen:1"].text.startswith("1896")
        assert cells["symbol:tuning:canongens"].text == f"𝒈{SUBSCRIPT_C}"
        assert not any(c.id.startswith(("cell:finv:", "cell:embed_c:")) for c in _layout().cells)

    def test_canonical_generators_column_tiles_carry_plain_text_matching_their_grids(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), form_tiles=True, plain_text_values=True).cells}
        assert cells["plain_text:mapping:canongens"].text == "[{1 1] {0 1]}"
        assert cells["plain_text:projection:canongens"].text == "{[1 0 0⟩ [1 0 1/4⟩]"
        assert cells["plain_text:tuning:canongens"].text.startswith("{1200")

    def test_canonical_embedding_and_tuning_tiles_carry_their_column_index_headers(self):
        from rtt.app.grid_tables import SUBSCRIPT_C
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), form_tiles=True, header_symbols=True).cells}
        assert cells["matlabel:col:projection:canongens:0"].text == f"𝐠{SUBSCRIPT_C}₁"
        assert cells["matlabel:col:projection:canongens:1"].text == f"𝐠{SUBSCRIPT_C}₂"
        assert cells["matlabel:col:tuning:canongens:0"].text == f"𝒈{SUBSCRIPT_C}₁"
        assert cells["matlabel:col:tuning:canongens:1"].text == f"𝒈{SUBSCRIPT_C}₂"

    def test_generator_form_matrix_is_interactive(self):
        cells = {c.id: c for c in _with(form_tiles=True, plain_text_values=True).cells}
        assert cells["cell:finv:0:0"].kind == "formcell", "𝐹: routed to the editable gridvalue component"
        assert cells["plain_text:mapping:canongens"].kind == "plain_text_edit"
        assert cells["cell:form:0:0"].kind == "mapped"
        assert cells["plain_text:canon:gens"].kind == "plain_text"
        from rtt.app.grid_tables import EDITABLE_PLAIN_TEXT
        assert ("mapping", "canongens") in EDITABLE_PLAIN_TEXT and ("canon", "gens") not in EDITABLE_PLAIN_TEXT

    def test_form_controls_adds_a_choose_form_chooser_to_the_mapping_and_comma_basis_boxes(self):
        cells = {c.id: c for c in _with(form_controls=True).cells}
        assert cells["formchooser:mapping"].kind == "formchooser"
        assert cells["formchooser:comma_basis"].kind == "formchooser"
        assert not any(c.id.startswith(("cell:canon:", "cell:form:")) for c in cells.values()), "form CONTROLS (the dropdowns) does NOT reveal the canonical-mapping row / 𝐹 matrix — those # belong to 'form tiles' (greyed for now); the dropdowns appear without the boxes"
        inset = spreadsheet_constants.BOX_INNER
        assert cells["formchooser:mapping"].x == cells["header:primes"].x + inset
        assert cells["formchooser:comma_basis"].x == cells["header:commas"].x + inset
        assert cells["formchooser:mapping"].y > cells["cell:mapping:1:0"].y
        assert not any(c.id.startswith("formchooser:") for c in _layout().cells)

    def test_form_chooser_is_stateful_showing_the_mappings_current_form(self):
        cells = {c.id: c for c in _with(form_controls=True).cells}
        assert cells["formchooser:mapping"].text == "equave-reduced"
        canon = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 0, -4), (0, 1, 4))),
            {**settings.defaults(), "form_controls": True}).cells}
        assert canon["formchooser:mapping"].text == "canonical"
        assert cells["formchooser:comma_basis"].text == "canonical", "the comma-basis chooser is stateful too: the default meantone's comma basis [⟨4 -4 1⟩] is the # canonical (antitransposed defactored Hermite) form, so its cell reads 'canonical'"

    def test_mapped_list_rules_its_vector_columns_apart_clear_of_the_marks(self):
        cells = {c.id: c for c in _layout().cells}
        assert "sep:mapped:1" in cells, "the mapped target interval list separates its vector columns with vertical # bars, and the per-column top/bottom marks are inset so they never touch one"
        sep = cells["sep:mapped:1"]
        top0, brace0 = cells["ebktop:mapped:0"], cells["ebkbrace:mapped:0"]
        assert top0.w < spreadsheet_constants.COL_W and brace0.w < spreadsheet_constants.COL_W, "inset, not full column"
        assert top0.x + top0.w < sep.x
        outer = cells["bracket:mapped:l"]
        over = spreadsheet_constants.FRAME_OVERHANG
        assert sep.y == outer.y == top0.y - over
        assert sep.y + sep.h == outer.y + outer.h == brace0.y + brace0.h + over

    def test_maps_get_angle_brackets_and_lists_get_square_brackets(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["bracket:map:0:l"].text == "⟨" and cells["bracket:map:0:r"].text == "]"
        assert "bracket:map:1:l" in cells
        assert cells["bracket:tuning:map:l"].text == "⟨" and cells["bracket:tuning:map:r"].text == "]"
        assert cells["bracket:mapped:l"].text == "[" and cells["bracket:mapped:r"].text == "]"
        assert cells["bracket:damage:l"].text == "[" and cells["bracket:damage:r"].text == "]"
        assert cells["bracket:map:0:l"].x < cells["cell:mapping:0:0"].x < cells["bracket:map:0:r"].x

    def test_per_row_brackets_are_short_and_centred_leaving_a_gap_between_rows(self):
        cells = {c.id: c for c in _layout().cells}
        l0, l1 = cells["bracket:map:0:l"], cells["bracket:map:1:l"]
        row0 = cells["cell:mapping:0:0"]
        assert l0.h < spreadsheet_constants.ROW_H
        assert l0.h == l1.h
        assert abs((l0.y + l0.h / 2) - (row0.y + row0.h / 2)) < 0.51
        gap = l1.y - (l0.y + l0.h)
        assert gap >= 0.75 * l0.h

    def test_mapped_list_outer_bracket_still_spans_the_whole_matrix(self):
        cells = {c.id: c for c in _layout().cells}
        b = cells["bracket:mapped:l"]
        first, last = cells["cell:mapped:0:0"], cells["cell:mapped:1:0"]
        assert b.h > spreadsheet_constants.ROW_H
        assert b.y <= first.y and b.y + b.h >= last.y + last.h

    def test_the_row_fold_node_clears_the_first_content_tile(self):
        lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        node = {c.id: c for c in lay.cells}["toggle:row:mapping"]
        gens_block = {b.id: b for b in lay.blocks}["block:gens"]
        assert node.x + node.w <= gens_block.x, "the node does not collide with the tile"

    def test_each_content_tile_has_a_top_left_fold_toggle(self):
        cells = {c.id: c for c in _layout().cells}
        for row_key, column_key in (("quantities", "primes"), ("quantities", "targets"),
                           ("mapping", "primes"), ("mapping", "targets"),
                           ("tuning", "primes"), ("tuning", "targets"), ("damage", "targets")):
            assert f"toggle:tile:{row_key}:{column_key}" in cells
        node = cells["toggle:tile:mapping:primes"]
        first = cells["cell:mapping:0:0"]
        assert node.x < first.x and node.y < first.y

    def test_tile_toggle_sits_clear_of_the_tile_content_and_panel_edges(self):
        lay = _layout()
        cells = {c.id: c for c in lay.cells}
        blocks = {b.id: b for b in lay.blocks}
        tog, top = cells["toggle:tile:mapping:primes"], cells["ebktop:primes"]
        assert tog.y + tog.h <= top.y
        tt, v = cells["toggle:tile:tuning:primes"], cells["tuning:prime:0"]
        assert tt.y + tt.h <= v.y
        panel = blocks["block:mapping"]
        assert panel.x < tog.x and panel.y < tog.y
        assert tog.x + tog.w < panel.x + panel.w

    def test_collapsing_a_tile_hides_its_content_keeps_its_toggle_and_folds_its_panel(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base, collapsed={"tile:mapping:primes"})
        cells = {c.id: c for c in lay.cells}
        blocks = {b.id: b for b in lay.blocks}
        assert not any(c.startswith("cell:mapping:") for c in cells)
        assert not any(c.startswith("bracket:map:") for c in cells)
        assert "ebktop:primes" not in cells and "ebkbrace:primes" not in cells
        assert blocks["block:mapping"].w == 0 and blocks["block:mapping"].h == 0, "...the panel folds to a zero-size point so the renderer animates it away"
        assert "toggle:tile:mapping:primes" in cells, "...but the toggle stays so the tile can be re-expanded"

    def test_collapsing_a_tile_leaves_its_siblings_and_the_grid_geometry_intact(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = spreadsheet.build(base)
        coll = spreadsheet.build(base, collapsed={"tile:mapping:primes"})
        fc = {c.id: c for c in full.cells}
        cc = {c.id: c for c in coll.cells}
        assert "cell:mapped:0:0" in cc
        assert cc["cell:mapped:0:0"].x == fc["cell:mapped:0:0"].x
        assert coll.width == full.width and coll.height == full.height
        assert {ln.id for ln in coll.lines} == {ln.id for ln in full.lines}

    def test_tile_toggle_glyph_flips_between_collapse_and_expand(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        open_ = {c.id: c for c in spreadsheet.build(base).cells}["toggle:tile:mapping:primes"]
        shut = {c.id: c for c in spreadsheet.build(base, collapsed={"tile:mapping:primes"}).cells}["toggle:tile:mapping:primes"]
        assert open_.text == "unfold_less"
        assert shut.text == "unfold_more"

    def test_collapsing_a_whole_band_removes_its_per_tile_toggles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        row_off = {c.id for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
        assert not any(c.startswith("toggle:tile:tuning:") for c in row_off)
        col_off = {c.id for c in spreadsheet.build(base, collapsed={"col:primes"}).cells}
        assert not any(c.endswith(":primes") and c.startswith("toggle:tile:") for c in col_off)

    def test_master_toggle_sits_in_the_top_left_node_corner(self):
        cells = {c.id: c for c in _layout().cells}
        master = cells["toggle:all"]
        assert master.x == cells["toggle:row:mapping"].x, "it shares the row toggles' x (the node column) and the column toggles' y (the # node row), so it lands in the corner where the two toggle lines converge"
        assert master.y == cells["toggle:col:primes"].y
        assert master.y < cells["toggle:row:mapping"].y
        assert master.x < cells["toggle:col:primes"].x

    def test_master_toggle_glyph_reflects_whether_the_whole_grid_is_collapsed(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        open_grid = {c.id: c for c in spreadsheet.build(base).cells}["toggle:all"]
        assert open_grid.text == "unfold_less"
        every = _foldable(spreadsheet.build(base))
        shut_grid = {c.id: c for c in spreadsheet.build(base, collapsed=every).cells}["toggle:all"]
        assert shut_grid.text == "unfold_more"

    def test_toggle_all_collapses_every_band_when_any_is_open(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base)
        after = spreadsheet_text.toggle_all_collapsed(lay, set())
        assert after == _foldable(lay)
        assert {"row:mapping", "col:primes", "col:targets"} <= after

    def test_toggle_all_expands_everything_when_fully_collapsed(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base)
        every = _foldable(lay)
        assert spreadsheet_text.toggle_all_collapsed(lay, every | {"tile:mapping:primes"}) == set()

    def test_collapsing_all_folds_the_whole_grid_down_to_its_strips(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = spreadsheet.build(base)
        shut = spreadsheet.build(base, collapsed=spreadsheet_text.toggle_all_collapsed(full, set()))
        assert not any(c.id.startswith(("cell:", "tuning:", "just:", "retune:", "damage:", "prime:"))
                       for c in shut.cells)
        assert shut.width < full.width and shut.height < full.height
        assert {c.id for c in shut.cells} >= {"label:mapping", "header:primes", "toggle:all"}, "labels, headers and the master toggle persist so the grid can be re-expanded"

    def test_presets_off_shows_no_chooser_dropdowns(self):
        cells = {c.id for c in _with(presets=False).cells}
        assert not any(c.startswith("preset:") for c in cells)


class TestPlainText:
    def test_presets_on_adds_the_three_chooser_dropdowns_under_their_tiles(self):
        lay = _with(presets=True)
        cells = {c.id: c for c in lay.cells}
        blocks = {b.id: b for b in lay.blocks}
        assert {"preset:temperament", "preset:tuning", "preset:target"} <= set(cells)
        inset = spreadsheet_constants.BOX_INNER
        temp, matrix = cells["preset:temperament"], cells["cell:mapping:0:0"]
        box = blocks["block:preset:temperament"]
        assert temp.y > matrix.y and temp.x == box.x + inset
        assert box.x <= matrix.x and matrix.x + matrix.w <= box.x + box.w
        assert cells["preset:target"].x == cells["header:targets"].x + inset

    def test_single_option_tuning_chooser_is_a_disabled_dropdown(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        lay = spreadsheet.build(base, s, displayed_tuning_name="minimax-U")
        cells = {c.id: c for c in lay.cells}
        assert cells["preset:tuning"].kind == "preset"
        assert cells["preset:tuning"].disabled is True
        assert "block:preset:tuning" in {b.id for b in lay.blocks}
        assert cells["block:preset:tuning:label"].disabled is True

    def test_off_list_tuning_chooser_stays_an_interactive_dropdown(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        lay = spreadsheet.build(base, s, displayed_tuning_name=None)
        cell = {c.id: c for c in lay.cells}["preset:tuning"]
        assert cell.kind == "preset" and cell.disabled is False
        assert "block:preset:tuning" in {b.id for b in lay.blocks}

    def test_weighting_keeps_the_tuning_chooser_an_enabled_dropdown(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["weighting"] = True, True
        lay = spreadsheet.build(base, s, displayed_tuning_name="minimax-U")
        cell = {c.id: c for c in lay.cells}["preset:tuning"]
        assert cell.kind == "preset" and cell.disabled is False
        assert "block:preset:tuning" in {b.id for b in lay.blocks}

    def test_tuning_and_target_choosers_show_the_live_selection_temperament_is_a_placeholder(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="destretched-octave minimax-ES", target_spec="OLD").cells}
        assert cells["preset:tuning"].text == "destretched-octave minimax-ES"
        assert cells["preset:target"].text == "OLD"
        assert cells["preset:temperament"].text == "", "a chooser placeholder, not a live value"

    def test_preset_choosers_follow_their_tiles_when_temperament_is_hidden(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["temperament_tiles"] = True, False
        cells = {c.id for c in spreadsheet.build(base, s).cells}
        assert "preset:temperament" not in cells, "the temperament + tuning choosers ride the domain-primes column (under the mapping matrix / # tuning map), so hiding the temperament takes each away with that column"
        assert "preset:tuning" not in cells
        assert "preset:target" in cells, "but the target chooser rides the interval-vectors row's target tile, which now owns its own # toggle (interval_vectors) rather than the temperament's -- so it stays with the temperament hidden"

    def test_target_preset_chooser_follows_the_interval_vectors_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["interval_vectors"] = True, False
        cells = {c.id for c in spreadsheet.build(base, s).cells}
        assert "preset:target" not in cells, "the target chooser rides the (interval-vectors, targets) tile, so hiding that row takes it"
        assert {"preset:temperament", "preset:tuning"} <= cells

    def test_preset_dropdown_clears_the_row_below_it(self):
        cells = {c.id: c for c in _with(presets=True).cells}
        drop, next_row = cells["preset:tuning"], cells["label:just"]
        assert drop.y + drop.h <= next_row.y

    def test_preset_chooser_sits_below_the_plain_text_band(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["plain_text_values"] = True, True
        cells = {c.id: c for c in spreadsheet.build(base, s).cells}
        chooser, plain_text = cells["preset:tuning"], cells["plain_text:tuning:primes"]
        assert chooser.y >= plain_text.y + plain_text.h

    def test_target_chooser_is_wider_to_seat_its_numeric_override(self):
        cells = {c.id: c for c in _with(presets=True).cells}
        assert cells["preset:target"].w > cells["preset:tuning"].w

    def test_tuning_and_temperament_dropdowns_are_copied_into_more_tiles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        lay = spreadsheet.build(base, s, tuning_scheme="destretched-octave minimax-ES")
        cells = {c.id: c for c in lay.cells}
        boxes = {b.id: b for b in lay.blocks}
        inset = spreadsheet_constants.BOX_INNER
        gt = cells["preset:tuning:gens"]
        assert gt.x == cells["header:gens"].x + inset and gt.text == "destretched-octave minimax-ES"
        assert boxes["block:preset:tuning:gens"].y == boxes["block:preset:tuning"].y
        ct = cells["preset:temperament:commas"]
        assert ct.x == cells["header:commas"].x + inset and ct.text == ""

    def test_target_preset_now_lives_in_the_target_interval_list_tile(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        cells = {c.id: c for c in spreadsheet.build(base, s).cells}
        target = cells["preset:target"]
        assert target.x == cells["header:targets"].x + spreadsheet_constants.BOX_INNER
        assert target.y > cells["cell:vector:targets:0:0"].y
        assert target.y > cells["target:0"].y

    def test_control_dropdowns_are_boxed_within_their_tiles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["form_controls"] = True, True
        lay = spreadsheet.build(base, s)
        cells = {c.id: c for c in lay.cells}
        boxes = {b.id: b for b in lay.blocks}
        for cid, label, tile in (("preset:tuning", "established tuning scheme", "block:tuning:primes"),
                                 ("preset:tuning:gens", "established tuning scheme", "block:tuning:gens"),
                                 ("preset:temperament", "temperament", "block:mapping"),
                                 ("preset:target", "target interval set scheme", "block:vector:targets")):
            ctrl, box, panel = cells[cid], boxes[f"block:{cid}"], boxes[tile]
            assert box.boxed is True, "a bordered box, not a plain tile"
            assert box.x <= ctrl.x and box.x + box.w >= ctrl.x + ctrl.w
            assert box.y <= ctrl.y and box.y + box.h >= ctrl.y + ctrl.h
            assert box.x >= panel.x - 0.5 and box.x + box.w <= panel.x + panel.w + 0.5, "the box stays WITHIN its tile -- never spilling out (the reported bug)"
            lbl = cells[f"block:{cid}:label"]
            assert lbl.kind == "caption" and lbl.text == label and lbl.align == "left" and lbl.y > ctrl.y
        for fcid, tbox in (("formchooser:mapping", "block:preset:temperament"),
                           ("formchooser:comma_basis", "block:preset:temperament:commas")):
            assert f"block:{fcid}" not in boxes
            ctrl, box = cells[fcid], boxes[tbox]
            assert box.y <= ctrl.y and box.y + box.h >= ctrl.y + ctrl.h
            tdrop = cells[tbox.removeprefix("block:")]
            assert ctrl.y > tdrop.y
            flbl = cells[f"{fcid}:label"]
            assert flbl.kind == "caption" and flbl.text == "form" and flbl.align == "left" and flbl.y > ctrl.y

    def test_a_long_control_label_widens_its_narrow_tile(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        gens_off = {b.id: b for b in spreadsheet.build(base, settings.defaults()).blocks}["block:tuning:gens"]
        lay = spreadsheet.build(base, {**settings.defaults(), "presets": True})
        gens_on = {b.id: b for b in lay.blocks}["block:tuning:gens"]
        box = {b.id: b for b in lay.blocks}["block:preset:tuning:gens"]
        assert gens_on.w > gens_off.w
        assert gens_on.w >= spreadsheet_text._min_width_for_lines("established tuning scheme", 1)
        assert box.x >= gens_on.x and box.x + box.w <= gens_on.x + gens_on.w

    def test_chooser_boxes_span_the_full_width_of_their_tiles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["form_controls"] = True, True
        boxes = {b.id: b for b in spreadsheet.build(base, s).blocks}
        for cid, tile in (("block:preset:temperament", "block:mapping"),
                          ("block:preset:tuning", "block:tuning:primes"),
                          ("block:preset:tuning:gens", "block:tuning:gens"),
                          ("block:preset:target", "block:vector:targets")):
            box, panel = boxes[cid], boxes[tile]
            left, right = box.x - panel.x, (panel.x + panel.w) - (box.x + box.w)
            assert abs(left - right) < 1

    def test_target_chooser_box_spans_its_tile_with_a_capped_dropdown_inside(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"] = True
        lay = spreadsheet.build(base, s)
        box = {b.id: b for b in lay.blocks}["block:preset:target"]
        dropdown = {c.id: c for c in lay.cells}["preset:target"]
        assert dropdown.w < box.w - 30

    def test_build_honors_the_target_interval_spec(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        tilt = {c.text for c in spreadsheet.build(base, target_spec="TILT").cells if c.id.startswith("target:")}
        old = {c.text for c in spreadsheet.build(base, target_spec="OLD").cells if c.id.startswith("target:")}
        assert tilt != old
        assert "8/5" in old and "8/5" not in tilt

    def test_build_honors_the_tuning_scheme(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        top = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="minimax-S").cells}
        pote = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="destretched-octave minimax-ES").cells}
        assert top["tuning:prime:0"] != pote["tuning:prime:0"], "destretched-octave minimax-ES holds the octave pure; minimax-S stretches it — so the prime-2 tuning differs"
        assert pote["tuning:prime:0"] == "1200.000"

    def test_plain_text_values_adds_a_string_band_under_each_tile(self):
        on = {c.id: c for c in _with(plain_text_values=True).cells}
        off = {c.id for c in _with(plain_text_values=False).cells}
        assert not any(c.startswith("plain_text:") for c in off)
        assert on["plain_text:mapping:primes"].text == "[⟨1 1 0] ⟨0 1 4]}"
        assert on["plain_text:mapping:targets"].text.startswith("[[1 0}")
        assert on["plain_text:vectors:commas"].text == "[[4 -4 1⟩]"
        assert on["plain_text:quantities:primes"].text == "2.3.5"
        assert on["plain_text:tuning:primes"].text.startswith("⟨")

    def test_every_open_value_tile_has_a_plain_text_string(self):
        from rtt.app.grid_tables import PLAIN_TEXT_ROWS, SPINE_COLUMNS
        b = _maximized_superspace_builder()
        assert b.resolved.flags.superspace and b.resolved.flags.plain_text_values
        value_rows = PLAIN_TEXT_ROWS - {"quantities"}
        missing = [(r, c) for (r, c) in sorted(b.geometry.declared_tiles)
                   if r in value_rows and c not in SPINE_COLUMNS and query.tile_open(b.geometry, b.inputs.collapsed, r, c)
                   and (r, c) not in b.geometry.plain_text_strings]
        assert not missing, f"open value tiles with no plain-text band: {missing}"

    def test_every_row_that_produces_plain_text_reserves_its_band(self):
        b = _maximized_superspace_builder()
        assert b.resolved.flags.plain_text_values and b.resolved.flags.canon
        rows_with_text = {r for (r, _c) in b.geometry.plain_text_strings}
        spill = sorted(r for r in rows_with_text if plain_text_band(b.geometry, r, folded=False) <= 0)
        assert not spill, f"rows produce plain text but reserve no band (it will spill past the tile): {spill}"

    def test_every_in_tile_band_reserves_for_what_it_emits(self):
        from rtt.app.grid_tables import BANDS, SYMBOLS, UNITS
        b = _maximized_superspace_builder()
        bands = {
            "plain text":   ({r for (r, _c) in b.geometry.plain_text_strings},
                             {r for (r, _c) in b.geometry.plain_text_strings if plain_text_band(b.geometry, r, folded=False) > 0}),
            "symbol":       ({r for (r, _c) in SYMBOLS}, set(BANDS["symbol"].rows)),
            "units":        ({r for (r, _c) in UNITS}, set(BANDS["units"].rows)),
            "caption":      ({r for (r, _c) in b.resolved.labels.captions}, set(BANDS["caption"].rows)),
            "column label": ({r for (r, _c) in b.resolved.labels.col_labels}, set(BANDS["col_label"].rows)),
        }
        spills = {name: sorted(emit - reserve) for name, (emit, reserve) in bands.items() if emit - reserve}
        assert not spills, f"rows emit a band's content but reserve no height for it (it will spill): {spills}"

    def test_frame_and_chart_bands_reserve_height_for_what_they_emit(self):
        b = _maximized_superspace_builder()
        lay = b.layout()
        frame_ys = {round(c.y, 3) for c in lay.cells if c.kind in {"ebktop", "ebkbrace", "ebkangle"}}
        frame_emit = {r for r in b.geometry.rows if round(query.frame_top_y(b.geometry, r), 3) in frame_ys
                      or round(query.frame_brace_y(b.geometry, r), 3) in frame_ys}
        frame_spill = sorted(r for r in frame_emit if b.geometry.rows[r].frame <= 0)
        assert not frame_spill, f"rows draw an EBK matrix frame but reserve no frame band (it will spill): {frame_spill}"
        chart_emit = {c.id.split(":")[1] for c in lay.cells if c.id.startswith("chart:")}
        chart_spill = sorted(r for r in chart_emit if b.geometry.rows[r].chart_top is None)
        assert not chart_spill, f"rows draw a bar chart but reserve no chart band (it will spill): {chart_spill}"

    def test_every_plain_text_band_shows_the_same_numbers_as_its_grid_tile(self):
        import re

        from rtt.app.grid_tables import PLAIN_TEXT_ROWS, SPINE_COLUMNS
        TOKEN = re.compile(r"—|-?\d+\.\d+|-?\d+/\d+|-?\d+")

        def cell_value(text):
            return text.rsplit("=", 1)[-1] if "=" in text else text

        def band_body(text):
            i = min((text.find(ch) for ch in "[⟨{" if ch in text), default=0)
            return text[i:]

        b = _maximized_superspace_builder()
        lay = b.layout()
        value_rows = PLAIN_TEXT_ROWS - {"quantities"}
        mismatches = []
        checked = 0
        for (row_key, column_key) in sorted(b.geometry.declared_tiles):
            if row_key not in value_rows or column_key in SPINE_COLUMNS or not query.tile_open(b.geometry, b.inputs.collapsed, row_key, column_key):
                continue
            if (row_key, column_key) not in b.geometry.plain_text_strings:
                continue
            rb, cx, cw = b.geometry.rows[row_key], b.geometry.col_x[column_key], b.geometry.col_w[column_key]
            grid_tokens = []
            for c in lay.cells:
                if (c.text and not c.id.startswith("plain_text:")
                        and cx - 2 <= c.x <= cx + cw and rb.y - 2 <= c.y <= rb.y + rb.h + 2):
                    grid_tokens += TOKEN.findall(cell_value(c.text))
            band_tokens = TOKEN.findall(band_body(b.geometry.plain_text_strings[(row_key, column_key)]))
            if sorted(grid_tokens) != sorted(band_tokens):
                mismatches.append((row_key, column_key, sorted(band_tokens), sorted(grid_tokens)))
            checked += 1
        assert checked >= 60, f"config did not light enough value tiles ({checked})"
        assert not mismatches, "plain text disagrees with the grid:\n" + "\n".join(
            f"  {r}/{c}: band={bt} grid={gt}" for r, c, bt, gt in mismatches)


    _EBK_OPEN, _EBK_CLOSE = "[⟨{", "]⟩}"

    def test_every_plain_text_band_uses_the_same_brackets_as_its_grid_tile(self):
        from rtt.app.grid_tables import PLAIN_TEXT_ROWS, SPINE_COLUMNS
        b = _maximized_superspace_builder()
        lay = b.layout()
        value_rows = PLAIN_TEXT_ROWS - {"quantities"}
        mismatches, checked = [], 0
        for (row_key, column_key) in sorted(b.geometry.declared_tiles):
            if row_key not in value_rows or column_key in SPINE_COLUMNS or not query.tile_open(b.geometry, b.inputs.collapsed, row_key, column_key):
                continue
            if (row_key, column_key) not in b.geometry.plain_text_strings:
                continue
            text_conv = _ebk_canonical(_ebk_text_convention(b.geometry.plain_text_strings[(row_key, column_key)]))
            grid_conv = _ebk_canonical(_ebk_grid_convention(b, lay, row_key, column_key))
            if text_conv != grid_conv:
                mismatches.append((row_key, column_key, text_conv, grid_conv, b.geometry.plain_text_strings[(row_key, column_key)]))
            checked += 1
        assert checked >= 60, f"config did not light enough value tiles ({checked})"
        assert not mismatches, "grid and plain-text EBK brackets disagree:\n" + "\n".join(
            f"  {r}/{c}: band={t} grid={g}  ({txt!r})" for r, c, t, g, txt in mismatches)

    def test_every_open_value_tile_declares_an_ebk_convention(self):
        from rtt.app.grid_tables import PLAIN_TEXT_ROWS, SPINE_COLUMNS
        from rtt.app.service.text_conventions import EBK_CONVENTIONS, ebk_convention
        b = _maximized_superspace_builder()
        value_rows = PLAIN_TEXT_ROWS - {"quantities"}
        undeclared, mismatches, checked = [], [], 0
        for (row_key, column_key) in sorted(b.geometry.declared_tiles):
            if row_key not in value_rows or column_key in SPINE_COLUMNS or not query.tile_open(b.geometry, b.inputs.collapsed, row_key, column_key):
                continue
            if (row_key, column_key) not in b.geometry.plain_text_strings:
                continue
            if (row_key, column_key) not in EBK_CONVENTIONS and (row_key, column_key) != ("prescaling", "primes"):
                undeclared.append((row_key, column_key))
                continue
            declared = _ebk_table_canonical(ebk_convention(row_key, column_key, superspace=b.resolved.flags.superspace))
            rendered = _ebk_canonical(_ebk_text_convention(b.geometry.plain_text_strings[(row_key, column_key)]))
            if declared != rendered:
                mismatches.append((row_key, column_key, declared, rendered, b.geometry.plain_text_strings[(row_key, column_key)]))
            checked += 1
        assert checked >= 60, f"config did not light enough value tiles ({checked})"
        assert not undeclared, f"open value tiles with no EBK_CONVENTIONS entry: {undeclared}"
        assert not mismatches, "rendered band disagrees with its declared EBK convention:\n" + "\n".join(
            f"  {r}/{c}: declared={d} rendered={g}  ({txt!r})" for r, c, d, g, txt in mismatches)

    def test_quantities_interval_ratios_emit_no_redundant_plain_text(self):
        ids = {c.id for c in _with(plain_text_values=True).cells}
        assert not any(i.startswith("plain_text:quantities:commas") for i in ids), "the quantities row's interval-ratio columns (commas, targets, held, …) already show the # formatted 'n/d' in the gridded cell, so they emit NO duplicate plain-text line below it"
        assert not any(i.startswith("plain_text:quantities:targets") for i in ids)
        assert "plain_text:quantities:primes" in ids, "the domain-primes column keeps its plain text — '2.3.5' is the compact prime-limit # notation, not a copy of the gridded '2 3 5' cells"

    def test_plain_text_band_sits_below_the_caption_spanning_its_column(self):
        cells = {c.id: c for c in _with(plain_text_values=True, names=True).cells}
        pt, cap, header = cells["plain_text:mapping:primes"], cells["caption:mapping:primes"], cells["header:primes"]
        assert pt.y >= cap.y + cap.h
        assert pt.x == header.x and pt.w == header.w


class TestPlainText2:
    def test_plain_text_band_grows_tiles_and_pushes_lower_rows_down(self):
        on = {c.id: c for c in _with(plain_text_values=True).cells}
        off = {c.id: c for c in _with(plain_text_values=False).cells}
        assert on["label:tuning"].y > off["label:tuning"].y

    def test_collapsing_hides_the_plain_text_band_with_the_tile(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["plain_text_values"] = True
        row_off = {c.id for c in spreadsheet.build(base, s, collapsed={"row:mapping"}).cells}
        assert not any(c.startswith("plain_text:mapping:") for c in row_off)
        tile_off = {c.id for c in spreadsheet.build(base, s, collapsed={"tile:mapping:primes"}).cells}
        assert "plain_text:mapping:primes" not in tile_off, "a collapsed tile drops its band"
        assert "plain_text:mapping:targets" in tile_off

    def test_editable_plain_text_tiles_render_as_inputs(self):
        cells = {c.id: c for c in _with("TILT minimax-S", plain_text_values=True, weighting=True, alt_complexity=True).cells}
        for cid in ("plain_text:mapping:primes", "plain_text:vectors:commas", "plain_text:tuning:gens",
                    "plain_text:vectors:targets", "plain_text:prescaling:primes"):
            assert cells[cid].kind == "plain_text_edit"
        for cid in ("plain_text:mapping:targets", "plain_text:mapping:commas", "plain_text:tuning:primes",
                    "plain_text:quantities:primes", "plain_text:damage:targets",
                    "plain_text:prescaling:commas"):
            assert cells[cid].kind == "plain_text"

    def test_plain_text_values_are_a_single_line_within_their_column(self):
        cells = {c.id: c for c in _with(plain_text_values=True).cells}
        long, header = cells["plain_text:tuning:targets"], cells["header:targets"]
        assert long.h == spreadsheet_constants.PLAIN_TEXT_H
        assert long.w == header.w
        assert cells["plain_text:just:targets"].h == spreadsheet_constants.PLAIN_TEXT_H
        assert cells["plain_text:mapping:primes"].h == spreadsheet_constants.PLAIN_TEXT_EDIT_H

    def test_names_toggles_in_tile_captions_but_never_the_row_col_titles(self):
        on = {c.id: c for c in _with(names=True).cells}
        off = {c.id: c for c in _with(names=False).cells}
        assert {"label:mapping", "header:primes"} <= set(on)
        assert {"label:mapping", "header:primes"} <= set(off)
        assert on["caption:mapping:primes"].text == "(temperament) mapping"
        assert not any(c.startswith("caption:") for c in off)
