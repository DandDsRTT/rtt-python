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
from _spreadsheet_support import _memoized_build, _layout, _with, _projection_build, _target_count, _barbados_superspace, _barbados_state, _assert_plain_text_cells_match


class TestProjectionVColumn:
    def test_projection_dashes_the_unchanged_columns_when_under_held(self):
        cells = {c.id: c for c in _projection_build().cells}
        assert all(cells[f"cell:unchanged:{p}:{j}"].text == "—" for p in range(3) for j in range(2))

    def test_projection_on_a_nonstandard_domain_lifts_dashes_cleanly(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        s["projection"] = True
        s["nonstandard_domain"] = True
        cells = {c.id: c for c in spreadsheet.build(state, s).cells}
        unchanged = [c for c in cells if c.startswith("cell:unchanged:")]
        assert unchanged and all(cells[c].text == "—" for c in unchanged)

    def test_projection_mapping_row_spans_v_mapping_the_unchanged_intervals(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        assert cells["cell:mapped_comma:0:0"].text == "0"
        assert cells["cell:mapped_unchanged:0:0"].text == "1"
        assert cells["cell:mapped_unchanged:1:1"].text == "4"
        assert cells["cell:mapped_unchanged:0:0"].x == cells["cell:unchanged:0:0"].x

    def test_projection_row_spans_v_with_the_projected_unrotated_vector_list(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        assert [cells[f"cell:projection_vectors:{p}:0"].text for p in range(3)] == ["0", "0", "0"]
        assert [cells[f"cell:projection_vectors:{p}:u0"].text for p in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:projection_vectors:{p}:u1"].text for p in range(3)] == ["-2", "0", "1"]
        assert cells["cell:projection_vectors:0:0"].y == cells["cell:projection:0:0"].y
        assert cells["cell:projection_vectors:0:u0"].x == cells["cell:unchanged:0:0"].x
        assert cells["caption:projection:commas"].text == "projected unrotated vector list"

    def test_projection_size_rows_span_v(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        for key in ("tuning", "just", "retune"):
            assert {f"{key}:comma:0", f"{key}:comma:u0", f"{key}:comma:u1"} <= set(cells)
            assert cells[f"{key}:comma:u1"].x == cells["cell:unchanged:0:1"].x

    def test_projection_v_column_has_one_c_u_divider_per_tile_and_no_stray_separators(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        bar = cells["vsplit:vectors"]
        assert bar.x == cells["cell:unchanged:0:0"].x - spreadsheet_constants.V_SPLIT_GAP / 2 - spreadsheet_constants.SEP_WIDTH / 2
        assert {"vsplit:scaling_factors", "vsplit:mapping", "vsplit:tuning"} <= set(cells)
        assert "vsplit:counts" not in cells, "the counts tile (two scalar tallies, not a matrix) gets none"
        assert not any(c.startswith("sep:mapped_comma:") for c in cells), "the mapped unrotated vector list (M·V) draws NO inter-entry separator rules (the stray- # separator bug is fixed); the lone C|U bar is its only divider"

    def test_projection_v_column_divider_is_set_for_the_whole_column(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        assert {"vsplit:quantities", "vsplit:vectors", "vsplit:scaling_factors",
                "vsplit:projection", "vsplit:mapping", "vsplit:tuning"} <= set(cells)
        assert "vsplit:counts" not in cells

    def test_superspace_unrotated_vector_lists_consolidate_v_and_get_the_divider(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        s["projection"] = s["nonstandard_domain"] = True
        cells = {c.id: c for c in spreadsheet.build(state, s, held_basis_ratios=("2/1", "3/1")).cells}
        assert [cells[f"cell:superspace_vectors:commas:{p}:u0"].text for p in range(4)] == ["1", "0", "0", "0"]
        assert [cells[f"cell:superspace_vectors:commas:{p}:u1"].text for p in range(4)] == ["0", "1", "0", "0"]
        assert any(cell_id.startswith("cell:superspace_mapping:commas:") and ":u0" in cell_id for cell_id in cells)
        assert cells["vsplit:superspace_vectors"].x == cells["vsplit:vectors"].x
        assert cells["vsplit:superspace_mapping"].x == cells["vsplit:vectors"].x
        assert cells["cell:superspace_vectors:commas:0:0"].x < cells["vsplit:superspace_vectors"].x < cells["cell:superspace_vectors:commas:0:u0"].x

    def test_mapped_comma_basis_has_no_stray_separators_off_projection(self):
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}
        assert any(c.startswith("cell:mapped_comma:") for c in cells)
        assert not any(c.startswith("sep:mapped_comma:") for c in cells)

    def test_projection_v_column_fans_one_gridline_per_subcolumn(self):
        lines = {line.id for line in _with(projection=True).lines}
        assert {"v:comma:0", "v:comma:1", "v:comma:2"} <= lines

    def test_projection_keeps_the_comma_add_remove_controls(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        assert "comma_plus" in cells and "comma_minus:0" in cells
        assert cells["comma_plus"].x < cells["cell:unchanged:0:0"].x
        assert abs(cells["comma_plus"].x - (cells["cell:comma:0:0"].x + spreadsheet_constants.COLUMN_WIDTH + spreadsheet_constants.V_SPLIT_GAP / 2 - spreadsheet_constants.BUTTON / 2)) < 0.51, "the + rides the C|U gap — the visual 'next comma' slot between the comma half and U — kept clear # of BOTH the − (on the lone comma's branch point) and U's first reorder grip, so it doesn't sit on # U's gridline and occlude grip:unchanged:0 (layout-invariants-2)"
        assert cells["comma_plus"].x - cells["comma_minus:0"].x >= spreadsheet_constants.COLUMN_WIDTH - spreadsheet_constants.BUTTON, "and a COL_W clear of the − hover zone on the lone comma (so the + is actually clickable)"

    def test_projection_at_full_rank_shows_the_complete_unchanged_basis(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
        assert not any(c.startswith("cell:comma:") for c in cells)
        assert [[cells[f"cell:unchanged:{p}:{j}"].text for p in range(3)] for j in range(3)] == \
            [["1", "0", "0"], ["0", "1", "0"], ["0", "0", "1"]]
        assert [cells[f"cell:scaling:u{j}"].text for j in range(3)] == ["1", "1", "1"]
        assert "comma_plus" in cells
        assert not any(c.startswith("comma_minus") for c in cells)
        assert not any(c.startswith("vsplit:") for c in cells), "no comma half, so no C|U divider and no wasted gap — U starts at the column's left and runs flush"
        assert cells["cell:unchanged:0:1"].x - cells["cell:unchanged:0:0"].x == spreadsheet_constants.COLUMN_WIDTH

    def test_projection_at_full_rank_keeps_the_nullity_count_in_a_readable_stub(self):
        s = settings.defaults()
        s["projection"] = True
        s["counts"] = True
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
        n_count = cells["count:commas"]
        assert n_count.text.endswith("= 0")
        cap = cells["caption:counts:commas"]
        assert cap.text == "nullity"
        assert spreadsheet_text._wrap_lines("nullity", cap.width) == 1
        assert n_count.x == cap.x < cells["bracket:vector:commas:l"].x <= cells["cell:unchanged:0:0"].x
        assert cells["count:commas:u"].x == cells["cell:unchanged:0:0"].x
        assert cells["bracket:vector:commas:l"].x + spreadsheet_constants.BRACKET_WIDTH == cells["cell:unchanged:0:0"].x

    def test_projection_pending_comma_reddens_the_unchanged_interval_it_will_delete(self):
        s = settings.defaults()
        s["projection"] = True
        s["counts"] = True
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None])
        cells = {c.id: c for c in layout.cells}
        nu = sum(1 for i in cells if i.startswith("cell:unchanged:0:"))
        assert nu >= 2
        last = nu - 1
        doomed_ids = ([f"cell:unchanged:{p}:{last}" for p in range(3)] + [f"unchanged:{last}"]
                      + [f"cell:mapped_unchanged:{i}:{last}" for i in range(2)]
                      + [f"tuning:comma:u{last}", f"just:comma:u{last}", f"retune:comma:u{last}"]
                      + [f"cell:projection_vectors:{p}:u{last}" for p in range(3)] + [f"cell:scaling:u{last}"])
        assert all(cells[cell_id].preview_remove for cell_id in doomed_ids), \
            [cell_id for cell_id in doomed_ids if not cells[cell_id].preview_remove]
        assert not any(cells[f"cell:unchanged:{p}:0"].preview_remove for p in range(3)), "the earlier U column, the unchanged count/caption, and the drag grip are NOT reddened"
        assert not cells["count:commas:u"].preview_remove
        assert not cells[f"grip:unchanged:{last}"].preview_remove
        plain = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                  held_basis_ratios=("2/1", "5/4"))
        assert not any(c.preview_remove for c in plain.cells)

    def test_unchanged_columns_have_cross_list_drag_grips(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), drag_to_combine=True).cells}
        assert cells["grip:unchanged:0"].kind == "columngrip"
        assert cells["grip:unchanged:1"].kind == "columngrip"
        assert cells["grip:unchanged:0"].x == cells["cell:unchanged:0:0"].x
        assert cells["grip:unchanged:1"].x == cells["cell:unchanged:0:1"].x
        assert "grip:unchanged:add" not in cells

    def test_projection_pending_comma_pushes_the_unchanged_half_past_the_draft(self):
        s = settings.defaults()
        s["projection"] = True
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None])
        cells = {c.id: c for c in layout.cells}
        draft = cells["cell:comma:0:1"]
        u_first = cells["cell:unchanged:0:0"]
        assert u_first.x > draft.x + spreadsheet_constants.COLUMN_WIDTH

    def test_projection_v_column_counts_both_nullity_and_unchanged(self):
        cells = {c.id: c for c in _with(projection=True, counts=True).cells}
        assert cells["count:commas"].text.endswith("= 1")
        assert cells["count:commas:u"].text.endswith("= 2")
        assert cells["count:commas:u"].x == cells["cell:unchanged:0:0"].x
        assert cells["count:commas"].x < cells["count:commas:u"].x
        assert cells["caption:counts:commas"].text == "nullity"
        assert cells["caption:counts:commas:u"].text == "unchanged interval count"
        assert (cells["caption:counts:commas"].x, cells["caption:counts:commas"].width) == (cells["count:commas"].x, cells["count:commas"].width)
        assert (cells["caption:counts:commas:u"].x, cells["caption:counts:commas:u"].width) == (cells["count:commas:u"].x, cells["count:commas:u"].width)

    def test_projected_unrotated_vector_list_tile_is_complete(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), symbols=True, units=True, plain_text_values=True).cells}
        assert cells["symbol:projection:commas"].text == "𝑃V"
        assert cells["units:projection:commas"].text == "units: p"
        assert cells["plain_text:projection:commas"].text == "[[0 0 0⟩ [1 0 0⟩ [-2 0 1⟩]"

    def test_consolidated_v_column_reads_green(self):
        blocks = {b.id for b in _projection_build(("2/1", "5/4"),
                                            temperament_colorization=True, tuning_colorization=True).blocks}
        for r in ("vectors", "mapping", "scaling_factors", "projection", "tuning", "just", "retune"):
            assert f"wash:temperament:{r}:commas" in blocks, r
            assert f"wash:tuning:{r}:commas" in blocks, r
        off = {b.id for b in _with(temperament_colorization=True, tuning_colorization=True).blocks}
        assert "wash:temperament:vectors:commas" in off and "wash:tuning:vectors:commas" not in off

    def test_v_column_plain_text_shows_both_the_comma_and_unchanged_halves(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), plain_text_values=True, weighting=True).cells}
        assert cells["plain_text:vectors:commas"].text == "[[4 -4 1⟩ [1 0 0⟩ [-2 0 1⟩]"
        assert cells["plain_text:mapping:commas"].text == "[[0 0} [1 0} [-2 4}]"
        assert cells["plain_text:tuning:commas"].text == "[0.000 1200.000 386.314]"
        assert cells["plain_text:scaling_factors:commas"].text == "[0 1 1]"
        dashed = {c.id: c for c in _projection_build(plain_text_values=True).cells}
        assert dashed["plain_text:vectors:commas"].text == "[[4 -4 1⟩ [— — —⟩ [— — —⟩]"
        assert dashed["plain_text:tuning:commas"].text == "[0.000 — —]"
        off = {c.id: c for c in _with(plain_text_values=True).cells}
        assert off["plain_text:vectors:commas"].text == "[[4 -4 1⟩]"

    def test_no_scaling_factors_or_unchanged_columns_without_projection(self):
        cells = {c.id for c in _layout().cells}
        assert "label:scaling_factors" not in cells
        assert not any(c.startswith("cell:scaling:") for c in cells)
        assert not any(c.startswith("cell:unchanged:") for c in cells)

    def test_v_consolidation_needs_the_commas_column_present(self):
        cells = {c.id for c in _with(projection=True, temperament_tiles=False).cells}
        assert "label:scaling_factors" not in cells
        assert not any(c.startswith(("cell:scaling:", "cell:unchanged:")) for c in cells)

    def test_projection_relabels_the_whole_column_as_the_unrotated_vector_list(self):
        named = {c.id: c for c in _with(projection=True).cells}
        assert named["header:commas"].text == "unrotated\nvector list"
        assert named["caption:vectors:commas"].text == "unrotated vector list = comma basis | unchanged interval basis"
        assert named["caption:mapping:commas"].text == "mapped unrotated vector list"
        assert named["caption:tuning:commas"].text == "tempered unrotated vector interval size list"
        assert named["caption:just:commas"].text == "(just) unrotated vector interval size list"
        symd = {c.id: c for c in _with(projection=True, symbols=True, equivalences=True).cells}
        assert symd["symbol:vectors:commas"].text == "V = C|U"
        assert symd["symbol:mapping:commas"].text == "𝑀V"
        assert symd["symbol:tuning:commas"].text == "𝒕V"
        plain = {c.id: c for c in _with(symbols=True).cells}
        assert plain["header:commas"].text == "commas"
        assert plain["caption:vectors:commas"].text == "comma basis"
        assert plain["symbol:vectors:commas"].text == "C"

    def test_projection_v_column_labels_are_v_and_lambda(self):
        cells = {c.id: c for c in _with(projection=True, symbols=True, header_symbols=True).cells}
        assert [cells[f"matrix_label:column:vectors:commas:{i}"].text for i in range(3)] == ["𝐯₁", "𝐯₂", "𝐯₃"], "the C|U split is the vertical bar, so every V sub-column is labelled 𝐯ᵢ (not a 𝐜/𝐮 split)"
        assert cells["matrix_label:column:mapping:commas:2"].text == "𝑀𝐯₃"
        assert cells["symbol:scaling_factors:commas"].text == "𝝀"
        assert [cells[f"matrix_label:column:scaling_factors:commas:{i}"].text for i in range(3)] == ["𝜆₁", "𝜆₂", "𝜆₃"]

    def test_projection_prescaling_and_complexity_rows_span_v(self):
        cells = {c.id: c for c in _with("minimax-S", projection=True, weighting=True).cells}
        assert {"cell:prescaling:commas:0:u0", "cell:prescaling:commas:0:u1"} <= set(cells), "prescaling: a d-tall 𝐿·v matrix per V sub-column; the two unchanged columns ride the # u{j} namespace (nc=1 here), so row 0 of each appears"
        assert {"complexity:comma:0", "complexity:comma:u0", "complexity:comma:u1"} <= set(cells)
        assert cells["complexity:comma:u1"].x == cells["cell:unchanged:0:1"].x

    def test_v_column_unchanged_basis_follows_the_held_basis(self):
        quarter = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        third = {c.id: c for c in _projection_build(("2/1", "6/5")).cells}
        assert [quarter[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["-2", "0", "1"]
        assert [third[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["1", "1", "-1"]

    def test_plain_text_band_matches_a_direct_derivation_under_a_custom_prescaler(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(state, {**settings.defaults(), "plain_text_values": True},
                                custom_prescaler=(1.0, 2.0, 3.0))
        pt = service.plain_text_values(state, service.DEFAULT_DOCUMENT_SCHEME,
                                       custom_prescaler=(1.0, 2.0, 3.0))
        _assert_plain_text_cells_match(layout, pt)

    def test_plain_text_band_matches_a_direct_derivation_under_a_manual_generator_tuning(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(state, {**settings.defaults(), "plain_text_values": True},
                                generator_tuning=(1201.7, 697.6))
        pt = service.plain_text_values(state, service.DEFAULT_DOCUMENT_SCHEME,
                                       generator_tuning=(1201.7, 697.6))
        _assert_plain_text_cells_match(layout, pt)


class TestProjectionDrafts:
    def test_plain_text_band_matches_a_direct_derivation_over_the_superspace(self):
        layout = _barbados_superspace(plain_text_values=True)
        pt = service.plain_text_values(_barbados_state(), service.DEFAULT_DOCUMENT_SCHEME,
                                       superspace=True)
        _assert_plain_text_cells_match(layout, pt)

    def test_projection_row_grows_a_draft_column_for_target_held_interest_drafts(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "projection": True, "optimization": True}
        k = _target_count()
        pt = {c.id: c for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
        assert all(pt[f"cell:projection_targets:draft:{p}"].pending and pt[f"cell:projection_targets:draft:{p}"].text == "" for p in range(3))
        assert pt["cell:projection_targets:draft:0"].x == pt[f"cell:projection_targets:{k - 1}:0"].x + spreadsheet_constants.COLUMN_WIDTH + spreadsheet_constants.INTERVAL_COL_GAP
        ph = {c.id: c for c in spreadsheet.build(base, s, pending_held=[None, None, None]).cells}
        assert all(ph[f"cell:projection_held:draft:{p}"].pending and ph[f"cell:projection_held:draft:{p}"].text == "" for p in range(3))
        pi = {c.id: c for c in spreadsheet.build(base, s, interest=((1, 1, -1),), pending_interest=[None, None, None]).cells}
        assert all(pi[f"cell:projection_interest:draft:{p}"].pending and pi[f"cell:projection_interest:draft:{p}"].text == "" for p in range(3))
        none = {c.id for c in spreadsheet.build(base, s, interest=((1, 1, -1),)).cells}
        assert not any(i.startswith(("cell:projection_targets:draft", "cell:projection_held:draft", "cell:projection_interest:draft")) for i in none)

    def test_scaling_factors_grows_a_green_draft_column_for_a_pending_comma(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "projection": True}
        c = {cell_box.id: cell_box for cell_box in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None]).cells}
        assert c["cell:scaling:draft"].pending and c["cell:scaling:draft"].text == ""
        assert c["cell:scaling:draft"].x == c["cell:projection_vectors:0:draft"].x
        assert "cell:scaling:draft" not in {cell_box.id for cell_box in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}

    def test_superspace_lifted_lists_grow_draft_columns_for_interval_drafts(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = {**settings.defaults(), "nonstandard_domain": True}
        superspace = {c.id: c for c in spreadsheet.build(state, s, pending_target=[None, None, None]).cells}
        vrows = sum(1 for i in superspace if i.startswith("cell:superspace_vectors:targets:") and i.endswith(":0"))
        mrows = sum(1 for i in superspace if i.startswith("cell:superspace_mapping:targets:") and i.endswith(":0"))
        assert vrows and mrows
        assert all(superspace[f"cell:superspace_vectors:targets:{p}:draft"].pending and superspace[f"cell:superspace_vectors:targets:{p}:draft"].text == "" for p in range(vrows))
        assert all(superspace[f"cell:superspace_mapping:targets:{g}:draft"].pending and superspace[f"cell:superspace_mapping:targets:{g}:draft"].text == "" for g in range(mrows))
        superspace_context = {c.id: c for c in spreadsheet.build(state, s, pending_comma=[None, None, None]).cells}
        assert superspace_context["cell:superspace_vectors:commas:0:draft"].pending and superspace_context["cell:superspace_mapping:commas:0:draft"].pending
        plain = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(i.startswith("cell:superspace_vectors:targets") and i.endswith("draft") for i in plain)

    def test_v_column_labels_track_their_cells_during_a_pending_comma(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "projection": True, "header_symbols": True}
        c = {cell_box.id: cell_box for cell_box in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None]).cells}
        assert c["matrix_label:column:vectors:commas:0"].x == c["cell:comma:0:0"].x
        assert c["matrix_label:column:vectors:commas:1"].x == c["cell:unchanged:0:0"].x
        assert c["matrix_label:column:vectors:commas:2"].x == c["cell:unchanged:0:1"].x
        assert "matrix_label:column:vectors:commas:3" not in c
        assert c["matrix_label:column:vectors:commas:1"].x != c["cell:comma:0:1"].x
        assert c["matrix_label:column:projection:commas:1"].x == c["cell:projection_vectors:0:u0"].x
        rest = {cell_box.id: cell_box for cell_box in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}
        assert rest["matrix_label:column:vectors:commas:1"].x == rest["cell:unchanged:0:0"].x

    def test_comma_add_drop_zone_does_not_occlude_the_unchanged_grips(self):
        def overlap(a, b):
            return max(a.x, b.x) < min(a.x + a.width, b.x + b.width) - 0.01
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "projection": True, "drag_to_combine": True}
        on = {c.id: c for c in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}
        assert not overlap(on["grip:commas:add"], on["grip:unchanged:0"])
        assert on["grip:commas:add"].x + on["grip:commas:add"].width <= on["grip:unchanged:0"].x + 0.51
        full = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
        assert not overlap(full["grip:commas:add"], full["grip:unchanged:0"])
        assert full["grip:commas:add"].x + full["grip:commas:add"].width <= full["grip:unchanged:0"].x + 0.51
        assert full["comma_plus"].x < full["cell:unchanged:0:0"].x

    def test_units_row_draft_columns_match_across_the_interval_lists(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "domain_units": True, "optimization": True}
        k = _target_count()
        ut = {c.id for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
        assert f"units_row:targets:{k}" in ut
        ui = {c.id for c in spreadsheet.build(base, s, interest=((1, 1, -1),), pending_interest=[None, None, None]).cells}
        assert "units_row:interest:1" in ui
        uh = {c.id for c in spreadsheet.build(base, s, held_vectors=((-1, 1, 0),), pending_held=[None, None, None]).cells}
        assert "units_row:held:1" in uh
        um = {c.id for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
        assert "units_column:mapping:2" in um
        rest = {c.id for c in spreadsheet.build(base, s).cells}
        assert f"units_row:targets:{k}" not in rest and "units_column:mapping:2" not in rest

    def test_all_interval_mean_damage_value_and_symbol_denote_the_same_quantity(self):
        import math

        from rtt.library import tuning
        from rtt.library.parsing import parse_temperament_data
        base = service.from_mapping(((1, 0, -4), (0, 1, 4)))
        t = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")
        cells = {c.id: c for c in spreadsheet.build(base, {**settings.defaults(), "optimization": True},
                                                    tuning_scheme="minimax-ES").cells}
        sym = cells["optimization:mean_damage:symbol"].text
        assert "⟪" in sym and "⟫" in sym and "‖" not in sym, "double-angle MEAN brackets, not a norm"
        val = float(cells["optimization:mean_damage"].text)
        mean = tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-ES"), "minimax-ES")
        assert val == pytest.approx(mean, abs=1e-3)
        norm = val * math.sqrt(3)
        assert norm == pytest.approx(2.741, abs=1e-2) and abs(val - norm) > 1.0, "value is the mean, NOT the norm"
