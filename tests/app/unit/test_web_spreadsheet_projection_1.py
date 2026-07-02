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
from _spreadsheet_support import _memoized_build, _layout, _with, _projection_build, _projection_full, _projection_superspace


class TestProjectionBox:
    def test_projection_off_by_default_shows_no_projection_box(self):
        cells = {c.id for c in _layout().cells}
        assert "label:projection" not in cells
        assert not any(c.startswith("cell:projection:") for c in cells)

    def test_projection_is_an_interactive_toggle(self):
        assert "projection" in settings.IMPLEMENTED, "it builds content now, so the panel offers it live rather than greyed out"

    def test_projection_on_adds_a_dxd_matrix_between_mapping_and_tuning(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        assert cells["label:projection"].text == "projection"
        for i in range(3):
            for p in range(3):
                cell = cells[f"cell:projection:{i}:{p}"]
                assert cell.kind == "mapped"
                assert cell.x == cells[f"cell:mapping:0:{p}"].x
        assert cells["label:mapping"].y < cells["label:projection"].y < cells["label:tuning"].y
        c00 = cells["cell:projection:0:0"]
        assert c00.width == c00.height == spreadsheet_constants.ROW_HEIGHT
        assert cells["cell:projection:1:0"].y == c00.y + spreadsheet_constants.ROW_HEIGHT

    def test_projection_box_is_dashed_until_the_tuning_is_a_rational_projection(self):
        dashed = {c.id: c for c in _projection_build().cells}
        assert all(dashed[f"cell:projection:{i}:{p}"].text == "—" for i in range(3) for p in range(3))

    def test_projection_box_shows_the_real_quarter_comma_when_fully_held(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        expected = (("1", "1", "0"), ("0", "0", "0"), ("0", "1/4", "1"))
        for i in range(3):
            for p in range(3):
                assert cells[f"cell:projection:{i}:{p}"].text == expected[i][p]

    def test_projection_box_is_framed_like_a_matrix_of_maps(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        assert cells["bracket:projection:0:l"].text == "⟨" and cells["bracket:projection:0:r"].text == "]"
        assert {"bracket:projection:1:l", "bracket:projection:2:l"} <= set(cells)
        assert "ebktop:projection" in cells and "ebkangle:projection" in cells and "ebkbrace:projection" not in cells, "and the whole matrix is enclosed by a spanning top bracket + bottom ANGLE close ⟩ (P is p/p, so # its outer closes with the prime-coordinate ket ⟩, matching its plain text [⟨…]…⟩ — not the # mapping's generator-coordinate })"
        top, brace = cells["ebktop:projection"], cells["ebkangle:projection"]
        first, last = cells["cell:projection:0:0"], cells["cell:projection:2:0"]
        assert top.y + top.height <= first.y
        assert brace.y >= last.y + last.height

    def test_projection_row_fans_a_gridline_per_subrow(self):
        lines = {line.id for line in _with(projection=True).lines}
        assert {"h:projection:0", "h:projection:1", "h:projection:2"} <= lines

    def test_projection_hides_with_its_parent_tuning_tiles(self):
        cells = {c.id for c in _with(projection=True, tuning_tiles=False).cells}
        assert "label:projection" not in cells
        assert not any(c.startswith("cell:projection:") for c in cells)

    def test_projection_on_adds_the_generator_embedding_G_beside_P(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        for i in range(3):
            for g in range(2):
                cell = cells[f"cell:embed:{i}:{g}"]
                assert cell.kind == "mapped"
                assert cell.x == cells[f"tuning:generator:{g}"].x
                assert cell.y == cells[f"cell:projection:{i}:0"].y
        expected = (("1", "0"), ("0", "0"), ("0", "1/4"))
        for i in range(3):
            for g in range(2):
                assert cells[f"cell:embed:{i}:{g}"].text == expected[i][g]
        dashed = {c.id: c for c in _projection_build().cells}
        assert all(dashed[f"cell:embed:{i}:{g}"].text == "—" for i in range(3) for g in range(2))

    def test_projection_p_and_g_carry_full_chrome_and_editable_plain_text(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), symbols=True, header_symbols=True, tile_units=True,
                                              equivalences=True, plain_text_values=True).cells}
        assert cells["symbol:projection:primes"].text.startswith("𝑃") and "= G𝑀" in cells["symbol:projection:primes"].text
        assert cells["symbol:projection:generators"].text.startswith("G"), "upright G (a basis), not italic 𝐺"
        assert cells["units:projection:primes"].text == "units: p/p"
        assert cells["units:projection:generators"].text == "units: p/g"
        assert cells["matrix_label:row:projection:primes:0"].text == "𝒑₁"
        assert cells["matrix_label:column:projection:generators:0"].text == "𝐠₁"
        assert cells["cell:projection:0:0"].kind == "mapped" and cells["cell:embed:0:0"].kind == "mapped"
        assert cells["plain_text:projection:primes"].kind == "plain_text_edit"
        assert cells["plain_text:projection:generators"].kind == "plain_text_edit"
        assert cells["plain_text:projection:primes"].text == "[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩"
        assert cells["plain_text:projection:generators"].text == "{[1 0 0⟩ [0 0 1/4⟩]"

    def test_projection_plain_text_bands_dash_when_under_held(self):
        cells = {c.id: c for c in _projection_build(plain_text_values=True).cells}
        assert cells["plain_text:projection:primes"].text == "[⟨— — —]⟨— — —]⟨— — —]⟩"
        assert cells["plain_text:projection:generators"].text == "{[— — —⟩ [— — —⟩]"

    def test_projection_quantities_spine_lists_the_domain_primes(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        assert [cells[f"projection_basis:{p}"].text for p in range(3)] == ["2", "3", "5"]
        assert cells["projection_basis:0"].kind == "comma_ratio"
        assert cells["projection_basis:0"].y == cells["cell:projection:0:0"].y
        assert cells["projection_basis:0"].x == cells["basis:0"].x

    def test_projection_units_spine_labels_each_row_as_a_prime_coordinate(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), app_units=True, tile_units=True).cells}
        assert [cells[f"units_column:projection:{p}"].text for p in range(3)] == ["p₁/", "p₂/", "p₃/"]
        assert cells["units_column:projection:0"].y == cells["cell:projection:0:0"].y

    def test_projection_detempering_tile_shows_P_times_D(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), generator_detempering=True).cells}
        expected = (("1", "0", "0"), ("0", "0", "1/4"))
        for i in range(2):
            for p in range(3):
                cell = cells[f"cell:projection_detempering:{i}:{p}"]
                assert cell.text == expected[i][p]
                assert cell.kind == "mapped"
                assert cell.x == cells[f"cell:vector:detempering:{i}:{p}"].x
                assert cell.y == cells[f"cell:projection:{p}:0"].y

    def test_projection_targets_tile_shows_P_times_T(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        expected = (("1", "0", "0"), ("1", "0", "1/4"), ("0", "0", "1/4"), ("1", "0", "-1/4"),
                    ("-1", "0", "1"), ("-1", "0", "3/4"), ("-2", "0", "1"), ("2", "0", "-3/4"))
        for j, column in enumerate(expected):
            for p in range(3):
                cell = cells[f"cell:projection_targets:{j}:{p}"]
                vector = cells[f"cell:vector:targets:{j}:{p}"]
                assert cell.text == column[p]
                assert cell.kind == "mapped"
                assert cell.x + cell.width / 2 == vector.x + vector.width / 2
                assert cell.y == cells[f"cell:projection:{p}:0"].y

    def test_projection_held_tile_shows_P_times_H_equals_H(self):
        cells = {c.id: c for c in _projection_full(optimization=True,
                                             held_vectors=[(1, 0, 0), (-2, 0, 1)]).cells}
        expected = (("1", "0", "0"), ("-2", "0", "1"))
        for i in range(2):
            for p in range(3):
                assert cells[f"cell:projection_held:{i}:{p}"].text == expected[i][p]
                assert cells[f"cell:projection_held:{i}:{p}"].kind == "mapped"

    def test_projection_interest_tile_shows_P_times_interest(self):
        cells = {c.id: c for c in _projection_full(interest=[(-1, 1, 0), (1, 1, -1)]).cells}
        expected = (("0", "0", "1/4"), ("2", "0", "-3/4"))
        for i in range(2):
            for p in range(3):
                assert cells[f"cell:projection_interest:{i}:{p}"].text == expected[i][p]
                assert cells[f"cell:projection_interest:{i}:{p}"].kind == "mapped"

    def test_projection_column_tiles_dash_when_under_held(self):
        cells = {c.id: c for c in _projection_build(generator_detempering=True).cells}
        assert all(cells[f"cell:projection_detempering:{i}:{p}"].text == "—" for i in range(2) for p in range(3))
        assert all(cells[f"cell:projection_targets:{j}:{p}"].text == "—" for j in range(3) for p in range(3))

    def test_projection_column_tiles_carry_full_chrome(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), generator_detempering=True,
                                              symbols=True, header_symbols=True, tile_units=True, equivalences=True).cells}
        assert cells["caption:projection:detempering"].text == "projected generator detempering"
        assert cells["caption:projection:targets"].text == "projected target interval list"
        assert cells["symbol:projection:detempering"].text == "𝑃D"
        assert cells["symbol:projection:targets"].text == "𝑃T"
        assert cells["units:projection:detempering"].text == "units: p"
        assert cells["units:projection:targets"].text == "units: p"
        assert cells["matrix_label:column:projection:detempering:0"].text == "𝑃𝐝₁"
        assert cells["matrix_label:column:projection:targets:0"].text == "𝑃𝐭₁"

    def test_projection_held_tile_carries_the_equals_H_equivalence(self):
        cells = {c.id: c for c in _projection_full(optimization=True, held_vectors=[(1, 0, 0), (-2, 0, 1)],
                                             symbols=True, header_symbols=True, equivalences=True).cells}
        assert cells["caption:projection:held"].text == "projected held interval basis"
        assert cells["symbol:projection:held"].text == "𝑃H = H"
        assert cells["matrix_label:column:projection:held:0"].text == "𝑃𝐡₁"

    def test_projection_interest_tile_caption_and_label(self):
        cells = {c.id: c for c in _projection_full(interest=[(-1, 1, 0), (1, 1, -1)], symbols=True, header_symbols=True).cells}
        assert cells["caption:projection:interest"].text == "projected intervals"
        assert cells["matrix_label:column:projection:interest:0"].text == "𝑃𝐢₁"
        assert "symbol:projection:interest" not in cells

    def test_projection_column_tiles_carry_plain_text_bands(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), generator_detempering=True,
                                              plain_text_values=True).cells}
        assert cells["plain_text:projection:detempering"].text == "{[1 0 0⟩ [0 0 1/4⟩]"
        assert cells["plain_text:projection:targets"].text == (
            "[[1 0 0⟩ [1 0 1/4⟩ [0 0 1/4⟩ [1 0 -1/4⟩ [-1 0 1⟩ [-1 0 3/4⟩ [-2 0 1⟩ [2 0 -3/4⟩]")

    def test_projection_column_tiles_use_their_vectors_row_brackets(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), generator_detempering=True).cells}
        assert cells["bracket:projection_detempering:l"].text == "{" and cells["bracket:projection_detempering:r"].text == "]"
        assert cells["bracket:projection_targets:l"].text == "[" and cells["bracket:projection_targets:r"].text == "]"
        assert "ebkangle:projection_detempering:0" in cells and "ebkangle:projection_targets:0" in cells

    def test_projection_superspace_tiles_fill_the_gap_between_G_and_P(self):
        cells = {c.id: c for c in _projection_superspace().cells}
        assert [cells[f"cell:embed_sl:0:{g}"].text for g in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:embed_sl:1:{g}"].text for g in range(3)] == ["0", "1/2", "0"]
        assert [cells[f"cell:projection_superspace:0:{p}"].text for p in range(4)] == ["1", "0", "0", "-1"]
        assert [cells[f"cell:projection_superspace:1:{p}"].text for p in range(4)] == ["0", "1", "0", "3/2"]
        assert cells["cell:embed_sl:0:0"].kind == "mapped" and cells["cell:projection_superspace:0:0"].kind == "mapped"
        assert cells["cell:embed_sl:0:0"].y == cells["cell:projection:0:0"].y
        assert (cells["cell:embed:0:0"].x < cells["cell:embed_sl:0:0"].x
                < cells["cell:projection_superspace:0:0"].x < cells["cell:projection:0:0"].x)

    def test_projection_superspace_tiles_carry_chrome(self):
        from rtt.app.grid_tables import SUBSCRIPT_L
        cells = {c.id: c for c in _projection_superspace(symbols=True, header_symbols=True, equivalences=True, tile_units=True).cells}
        assert cells["caption:projection:superspace_generators"].text == "embedding from superspace generators to subspace elements"
        assert cells["caption:projection:superspace_primes"].text == "projection from superspace to subspace"
        assert cells["symbol:projection:superspace_generators"].text == f"G{SUBSCRIPT_L}→ₛ"
        assert cells["symbol:projection:superspace_primes"].text == f"𝑃{SUBSCRIPT_L}→ₛ = G{SUBSCRIPT_L}→ₛ𝑀{SUBSCRIPT_L}"
        assert cells["units:projection:superspace_generators"].text == f"units: b/g{SUBSCRIPT_L}"
        assert cells["units:projection:superspace_primes"].text == "units: b/p"
        assert cells["matrix_label:column:projection:superspace_generators:0"].text == f"𝐠{SUBSCRIPT_L}→ₛ₁"
        assert cells["matrix_label:row:projection:superspace_primes:0"].text == f"𝒑{SUBSCRIPT_L}→ₛ₁"
        assert cells["bracket:embed_sl:l"].text == "{" and cells["bracket:embed_sl:r"].text == "]"
        assert cells["bracket:projection_superspace:0:l"].text == "⟨" and cells["bracket:projection_superspace:0:r"].text == "]"

    def test_projection_superspace_tiles_dash_when_under_held(self):
        st = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        s.update(projection=True, nonstandard_domain=True)
        cells = {c.id: c for c in spreadsheet.build(st, s).cells}
        assert all(cells[f"cell:embed_sl:{i}:{g}"].text == "—" for i in range(3) for g in range(3))
        assert all(cells[f"cell:projection_superspace:{i}:{p}"].text == "—" for i in range(3) for p in range(4))

    def test_projection_row_comes_after_the_superspace_rows(self):
        cells = {c.id: c for c in _projection_superspace().cells}
        projection_y = cells["cell:projection:0:0"].y
        assert projection_y > cells["cell:superspace_vectors:primes:0:0"].y
        assert projection_y > cells["cell:superspace_mapping:superspace_primes:0:0"].y

    def test_projection_targets_tile_tracks_the_targets_column(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s.update(projection=True)
        for kw in ({}, {"target_override": ()}):
            ids = {c.id for c in spreadsheet.build(st, s, held_basis_ratios=("2/1", "5/4"), **kw).cells}
            assert ("bracket:vector:targets:l" in ids) == ("bracket:projection_targets:l" in ids)


class TestProjectionChrome:
    def test_projection_symbol_floor_widens_the_tile_so_the_equivalence_never_wraps(self):
        from rtt.app.spreadsheet_constants import SYMBOL_FONT
        from rtt.app.spreadsheet_text import _min_width_for_lines
        cells = {c.id: c for c in _projection_build(("2/1", "5/4"), symbols=True, equivalences=True, names=True).cells}
        sym = cells["symbol:projection:primes"]
        assert sym.width >= _min_width_for_lines(sym.text, 1, SYMBOL_FONT)
        left = cells["cell:projection:0:0"].x - sym.x
        right = (sym.x + sym.width) - (cells["cell:projection:0:2"].x + cells["cell:projection:0:2"].width)
        assert abs(left - right) <= 1

    def test_return_to_scheme_button_is_boxed_above_the_dropdown_with_presets(self):
        layout = _with(projection=True, presets=True)
        cells = {c.id: c for c in layout.cells}
        sq, dropdown = cells["scheme:primes"], cells["preset:projection"]
        assert sq.y < dropdown.y
        box = next(b for b in layout.blocks if b.id == "block:preset:projection")
        for cell in (sq, dropdown):
            assert box.x <= cell.x and cell.y >= box.y and cell.y < box.y + box.height

    def test_return_to_scheme_button_rides_the_projection_preset(self):
        without = {c.id: c for c in _with(projection=True, presets=False).cells}
        assert not any(c.kind == "scheme_button" for c in without.values()), \
            "the return-to-scheme button is part of the projection preset; without presets there is no standalone button"
        with_presets = {c.id: c for c in _with(projection=True, presets=True).cells}
        assert any(c.kind == "scheme_button" for c in with_presets.values()), \
            "with presets on, the return-to-scheme button appears inside the projection preset box"

    def test_generator_embedding_is_a_vector_list_of_generator_kets(self):
        cells = {c.id: c for c in _with(projection=True).cells}
        assert cells["caption:projection:generators"].text == "generator embedding"
        assert cells["bracket:embed:l"].text == "{" and cells["bracket:embed:r"].text == "]", "G is a VECTOR LIST (matching its plain text {[…⟩…]): an outer { … ] (curly open, square close) # around r prime-count ket [ … ⟩ columns — NOT a per-row covector stack"
        assert {"ebktop:embed:0", "ebkangle:embed:0", "ebktop:embed:1", "ebkangle:embed:1"} <= set(cells)
        assert "bracket:embed:0:l" not in cells and "ebkbrace:embed" not in cells

    def test_generator_embedding_hides_when_projection_is_off(self):
        assert not any(c.id.startswith("cell:embed:") for c in _layout().cells)

    def test_presets_on_adds_the_established_projection_and_embedding_choosers(self):
        cells = {c.id: c for c in _with(projection=True, presets=True).cells}
        assert cells["preset:projection"].kind == "preset"
        assert cells["preset:projection:generators"].kind == "preset"
        assert cells["block:preset:projection:label"].text == "established projection"
        assert cells["block:preset:projection:generators:label"].text == "established embedding"

    def test_established_projection_choosers_need_both_presets_and_the_projection_box(self):
        assert not any(c.id.startswith("preset:projection") for c in _with(presets=True).cells)
        assert not any(c.id.startswith("preset:projection") for c in _with(projection=True).cells)

    def test_projection_adds_a_scaling_factors_row_over_v(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        assert cells["label:scaling_factors"].text == "scaling factors"
        assert [cells[i].text for i in ("cell:scaling:0", "cell:scaling:u0", "cell:scaling:u1")] == ["0", "1", "1"]
        assert cells["label:scaling_factors"].y < cells["label:vectors"].y
        s0 = cells["cell:scaling:0"]
        assert s0.height == spreadsheet_constants.ROW_HEIGHT
        assert s0.x == cells["cell:comma:0:0"].x

    def test_projection_consolidates_commas_and_unchanged_into_v(self):
        cells = {c.id: c for c in _projection_build(("2/1", "5/4")).cells}
        assert cells["cell:comma:0:0"].kind == "comma_cell", "V = C|U: the editable comma vectors C stay, the unchanged basis U appends — also editable now # (a full rational projection), retyping it retunes"
        u_first = cells["cell:unchanged:0:0"]
        assert u_first.kind == "unchanged_cell"
        assert u_first.x == cells["cell:comma:0:0"].x + spreadsheet_constants.COLUMN_WIDTH + spreadsheet_constants.V_SPLIT_GAP, "the unchanged half U is pushed right of the comma half by the extra C|U gap (so the divider # clears the cells); within U the columns stay one COL_W apart"
        assert cells["cell:unchanged:0:1"].x == u_first.x + spreadsheet_constants.COLUMN_WIDTH
        assert [cells[f"cell:unchanged:{p}:0"].text for p in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["-2", "0", "1"]
