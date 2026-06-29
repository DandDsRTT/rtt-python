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
from _spreadsheet_support import _memoized_build, _with, _color_at, _mid, _barbados_superspace, _barbados_superspace_identity, _SUBSCRIPT_DIGITS, _barbados_state, _barbados_superspace_tuning, _nonstd_on


class TestSuperspaceTuning:
    def test_M_L_absent_over_a_standard_prime_domain(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults() | {"nonstandard_domain": True}
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cid.startswith("cell:superspace_mapping:superspace_primes:") for cid in cids)

    def test_M_L_tile_carries_per_row_map_brackets_and_a_matrix_frame(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i in range(3):
            assert cells[f"bracket:superspace_map:{i}:l"].text == spreadsheet_constants.MAP_BRACKETS[0]
            assert cells[f"bracket:superspace_map:{i}:r"].text == spreadsheet_constants.MAP_BRACKETS[1]
        assert "ebktop:superspace_mapping" in cells
        assert "ebkbrace:superspace_mapping" in cells

    def test_M_L_tile_row_labels_each_covector(self):
        cells = {c.id: c for c in _barbados_superspace(symbols=True, header_symbols=True).cells}
        for i in range(3):
            sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
            assert cells[f"matlabel:row:superspace_mapping:superspace_primes:{i}"].text == f"\U0001D48EL{sub_i}"

    def test_M_jL_emits_a_cell_per_superspace_prime_row_and_superspace_prime_col_as_identity(self):
        cells = {c.id: c for c in _barbados_superspace_identity().cells}
        for i in range(4):
            for j in range(4):
                expected = "1" if i == j else "0"
                assert cells[f"cell:superspace_vectors:superspace_primes:{i}:{j}"].text == expected
                assert cells[f"cell:superspace_vectors:superspace_primes:{i}:{j}"].kind == "mapped"

    def test_M_L_and_M_jL_cells_are_read_only_mapped_kind(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for gen_idx in range(3):
            for superspace_prime_idx in range(4):
                assert cells[f"cell:superspace_mapping:superspace_primes:{gen_idx}:{superspace_prime_idx}"].kind == "mapped"

    def test_M_jL_tile_has_brackets_and_matrix_frame(self):
        cells = {c.id: c for c in _barbados_superspace_identity().cells}
        for i in range(4):
            assert cells[f"bracket:superspace_vector_ji_map:{i}:l"].text == spreadsheet_constants.MAP_BRACKETS[0]
            assert cells[f"bracket:superspace_vector_ji_map:{i}:r"].text == spreadsheet_constants.MAP_BRACKETS[1]
        assert "ebktop:superspace_vector_ji_map" in cells
        assert "ebkangle:superspace_vector_ji_map" in cells

    def test_M_jL_tile_carries_caption_and_symbol(self):
        cells = {c.id: c for c in _barbados_superspace_identity(names=True, symbols=True, equivalences=False).cells}
        assert cells["caption:superspace_vectors:superspace_primes"].text == "superspace JI mapping"
        assert cells["symbol:superspace_vectors:superspace_primes"].text == "\U0001D440jL"

    def test_M_jL_tile_row_labels_each_covector(self):
        cells = {c.id: c for c in _barbados_superspace_identity(symbols=True, header_symbols=True).cells}
        for i in range(4):
            sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
            assert cells[f"matlabel:row:superspace_vectors:superspace_primes:{i}"].text == f"\U0001D48EjL{sub_i}"

    def test_M_jL_tile_carries_identity_equivalence(self):
        cells = {c.id: c for c in _barbados_superspace_identity(symbols=True, equivalences=True).cells}
        sym = cells["symbol:superspace_vectors:superspace_primes"].text
        assert sym == "\U0001D440jL = \U0001D43C"

    def test_superspace_identity_objects_gate_on_identity_objects(self):
        lay = _barbados_superspace(symbols=True)
        cids = {c.id for c in lay.cells}
        bids = {b.id for b in lay.blocks}
        assert not any(c.startswith("cell:superspace_vectors:superspace_primes:") for c in cids)
        assert not any(c.startswith("cell:superspace_mapping:superspace_generators:") for c in cids)
        assert "block:superspace_vectors:superspace_primes" not in bids
        assert "block:superspace_mapping:superspace_generators" not in bids
        assert any(c.startswith("cell:superspace_vectors:primes:") for c in cids)
        assert any(c.startswith("cell:superspace_mapping:superspace_primes:") for c in cids)
        on = {c.id for c in _barbados_superspace_identity(symbols=True).cells}
        assert {"cell:superspace_vectors:superspace_primes:0:0", "cell:superspace_mapping:superspace_generators:0:0"} <= on

    def test_superspace_tuning_emits_g_L_cells_over_the_superspace_generators_column(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i, v in enumerate(_barbados_superspace_tuning().generator_map):
            assert cells[f"tuning:superspace_generator:{i}"].text == service.cents(v)

    def test_superspace_tuning_emits_t_L_cells_over_the_superspace_primes_column(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i, v in enumerate(_barbados_superspace_tuning().tuning_map):
            assert cells[f"tuning:superspace_prime:{i}"].text == service.cents(v)

    def test_superspace_just_emits_j_L_cells_over_the_superspace_primes_column(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i, v in enumerate(_barbados_superspace_tuning().just_map):
            assert cells[f"just:superspace_prime:{i}"].text == service.cents(v)

    def test_superspace_retune_emits_r_L_cells_over_the_superspace_primes_column(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i, v in enumerate(_barbados_superspace_tuning().retuning_map):
            assert cells[f"retune:superspace_prime:{i}"].text == service.cents(v)

    def test_superspace_tuning_row_off_omits_the_cells(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cid.startswith("tuning:superspace_generator:") for cid in cids)
        assert not any(cid.startswith("tuning:superspace_prime:") for cid in cids)
        assert not any(cid.startswith("just:superspace_prime:") for cid in cids)
        assert not any(cid.startswith("retune:superspace_prime:") for cid in cids)

    def test_superspace_tuning_tiles_carry_their_brackets(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert cells["bracket:tuning:superspace_generator_map:l"].text == spreadsheet_constants.GENMAP_BRACKETS[0]
        assert cells["bracket:tuning:superspace_generator_map:r"].text == spreadsheet_constants.GENMAP_BRACKETS[1]
        for key in ("tuning", "just", "retune"):
            assert cells[f"bracket:{key}:superspace_primes:l"].text == spreadsheet_constants.MAP_BRACKETS[0]
            assert cells[f"bracket:{key}:superspace_primes:r"].text == spreadsheet_constants.MAP_BRACKETS[1]

    def test_superspace_tuning_row_captions_and_symbols(self):
        cells = {c.id: c for c in _barbados_superspace(names=True, symbols=True, equivalences=False).cells}
        assert cells["caption:tuning:superspace_generators"].text == "superspace generator tuning map"
        assert cells["caption:tuning:superspace_primes"].text == "superspace tuning map"
        assert cells["caption:just:superspace_primes"].text == "superspace just tuning map"
        assert cells["caption:retune:superspace_primes"].text == "superspace retuning map"
        assert cells["symbol:tuning:superspace_generators"].text == "\U0001D488L"
        assert cells["symbol:tuning:superspace_primes"].text == "\U0001D495L"
        assert cells["symbol:just:superspace_primes"].text == "\U0001D48BL"
        assert cells["symbol:retune:superspace_primes"].text == "\U0001D493L"

    def test_superspace_tuning_row_equivalences(self):
        cells = {c.id: c for c in _barbados_superspace(symbols=True, equivalences=True).cells}
        assert cells["symbol:tuning:superspace_primes"].text == "\U0001D495L = \U0001D488L\U0001D440L"
        assert cells["symbol:retune:superspace_primes"].text == "\U0001D493L = \U0001D495L − \U0001D48BL"

    def test_superspace_tuning_rows_absent_over_a_standard_prime_domain(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults() | {"nonstandard_domain": True}
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cid.startswith(pfx) for cid in cids
                       for pfx in ("tuning:superspace_generator", "tuning:superspace_prime", "just:superspace_prime", "retune:superspace_prime"))

    def test_B_L_tile_has_a_plain_text_string(self):
        cells = {c.id: c for c in _barbados_superspace(plain_text_values=True).cells}
        assert cells["plain_text:superspace_vectors:primes"].text == "⟨[1 0 0 0⟩ [0 1 0 0⟩ [0 0 -1 1⟩]"

    def test_M_L_tile_has_a_plain_text_string(self):
        cells = {c.id: c for c in _barbados_superspace(plain_text_values=True).cells}
        ml = service.superspace_mapping(_barbados_state())
        expected = "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in ml) + "}"
        assert cells["plain_text:superspace_mapping:superspace_primes"].text == expected

    def test_M_jL_tile_has_a_plain_text_string(self):
        cells = {c.id: c for c in _barbados_superspace_identity(plain_text_values=True).cells}
        assert cells["plain_text:superspace_vectors:superspace_primes"].text == (
            "[⟨1 0 0 0]⟨0 1 0 0]⟨0 0 1 0]⟨0 0 0 1]⟩")

    def test_cyan_superspace_tuning_tiles_have_plain_text_strings(self):
        cells = {c.id: c for c in _barbados_superspace(plain_text_values=True).cells}
        tuning_map = _barbados_superspace_tuning()
        expected_g = "{" + " ".join(service.cents(v) for v in tuning_map.generator_map) + "]"
        assert cells["plain_text:tuning:superspace_generators"].text == expected_g
        for row_key, values in (("tuning", tuning_map.tuning_map), ("just", tuning_map.just_map),
                                ("retune", tuning_map.retuning_map)):
            expected = "⟨" + " ".join(service.cents(v) for v in values) + "]"
            assert cells[f"plain_text:{row_key}:superspace_primes"].text == expected

    def test_superspace_plain_text_off_when_nonstandard_domain_off(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {"plain_text_values": True}
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        for new in ("plain_text:superspace_vectors:primes", "plain_text:superspace_mapping:superspace_primes",
                    "plain_text:superspace_vectors:superspace_primes", "plain_text:tuning:superspace_generators",
                    "plain_text:tuning:superspace_primes", "plain_text:just:superspace_primes", "plain_text:retune:superspace_primes"):
            assert new not in cids

    def test_phase4_additive_only_against_baseline_with_all_show_toggles(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {
            "names": True, "symbols": True, "counts": True, "plain_text_values": True,
            "equivalences": True, "units": True, "presets": True,
        }
        lay = spreadsheet.build(state, s)
        ids = ({c.id for c in lay.cells} | {b.id for b in lay.blocks}
               | {ln.id for ln in lay.lines})
        for frag in ("cell:superspace_vectors:primes:", "cell:superspace_mapping:superspace_primes:",
                     "superspace_generator_map", ":superspace_primes:l", ":superspace_primes:r"):
            assert not any(frag in i for i in ids), f"leaked id matching {frag!r}"

    def test_superspace_M_L_per_row_brackets_reuse_MAP_BRACKETS(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for i in range(3):
            assert cells[f"bracket:superspace_map:{i}:l"].text == "⟨"
            assert cells[f"bracket:superspace_map:{i}:r"].text == "]"

    def test_superspace_M_jL_per_row_brackets_reuse_MAP_BRACKETS(self):
        cells = {c.id: c for c in _barbados_superspace_identity().cells}
        for i in range(4):
            assert cells[f"bracket:superspace_vector_ji_map:{i}:l"].text == "⟨"
            assert cells[f"bracket:superspace_vector_ji_map:{i}:r"].text == "]"

    def test_superspace_t_L_j_L_r_L_brackets_reuse_MAP_BRACKETS(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for key in ("tuning", "just", "retune"):
            assert cells[f"bracket:{key}:superspace_primes:l"].text == "⟨"
            assert cells[f"bracket:{key}:superspace_primes:r"].text == "]"


class TestPerCell:
    def test_superspace_g_L_brackets_reuse_GENMAP_BRACKETS(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert cells["bracket:tuning:superspace_generator_map:l"].text == "{"
        assert cells["bracket:tuning:superspace_generator_map:r"].text == "]"

    def test_superspace_M_L_and_M_jL_outer_frame_uses_ebktop_with_brace_or_angle(self):
        cells = {c.id: c for c in _barbados_superspace_identity().cells}
        assert cells["ebktop:superspace_mapping"].kind == "ebktop"
        assert cells["ebkbrace:superspace_mapping"].kind == "ebkbrace"
        assert cells["ebktop:superspace_vector_ji_map"].kind == "ebktop"
        assert cells["ebkangle:superspace_vector_ji_map"].kind == "ebkangle"

    def test_existing_bracket_constants_are_unchanged_by_superspace(self):
        assert spreadsheet_constants.MAP_BRACKETS == ("⟨", "]")
        assert spreadsheet_constants.LIST_BRACKETS == ("[", "]")
        assert spreadsheet_constants.GENMAP_BRACKETS == ("{", "]")

    def test_math_expressions_render_j_L_cells_as_log_of_superspace_primes(self):
        cells = {c.id: c for c in _barbados_superspace(math_expressions=True).cells}
        assert cells["just:superspace_prime:0"].kind == "mathexpr"
        assert cells["just:superspace_prime:0"].text == "1200 · log₂2\n= 1200.000"
        assert cells["just:superspace_prime:1"].text == "1200 · log₂3\n= 1901.955"
        assert cells["just:superspace_prime:2"].text == "1200 · log₂5\n= 2786.314"
        assert cells["just:superspace_prime:3"].text.startswith("1200 · log₂13\n= ")

    def test_math_expressions_off_keeps_j_L_cells_as_plain_tuning_value(self):
        cells = {c.id: c for c in _barbados_superspace(math_expressions=False).cells}
        assert cells["just:superspace_prime:0"].kind == "tuningvalue"

    def test_chart_band_renders_over_the_retune_r_L_tile_when_charts_is_on(self):
        cells = {c.id: c for c in _barbados_superspace(charts=True).cells}
        chart = cells["chart:retune:superspace_primes"]
        assert chart.kind == "chart"
        expected_vals = tuple(_barbados_superspace_tuning().retuning_map)
        assert chart.values == expected_vals

    def test_chart_band_omitted_from_r_L_when_charts_is_off(self):
        cells = {c.id for c in _barbados_superspace(charts=False).cells}
        assert "chart:retune:superspace_primes" not in cells

    def test_per_cell_units_subscript_p_on_the_superspace_tuning_cells(self):
        cells = {c.id: c for c in _barbados_superspace(units=True, cell_units=True).cells}
        assert cells["tuning:superspace_prime:0"].unit == "¢/p₁"
        assert cells["tuning:superspace_prime:1"].unit == "¢/p₂"
        assert cells["just:superspace_prime:0"].unit == "¢/p₁"
        assert cells["retune:superspace_prime:0"].unit == "¢/p₁"

    def test_per_cell_units_subscript_gL_on_the_g_L_cells(self):
        cells = {c.id: c for c in _barbados_superspace(units=True, cell_units=True).cells}
        assert cells["tuning:superspace_generator:0"].unit == "¢/gL₁"
        assert cells["tuning:superspace_generator:1"].unit == "¢/gL₂"

    def test_per_cell_units_on_the_M_L_cells_carry_gL_over_p(self):
        cells = {c.id: c for c in _barbados_superspace(units=True, cell_units=True).cells}
        assert cells["cell:superspace_mapping:superspace_primes:0:0"].unit == "gL₁/p₁"
        assert cells["cell:superspace_mapping:superspace_primes:0:1"].unit == "gL₁/p₂"
        assert cells["cell:superspace_mapping:superspace_primes:1:0"].unit == "gL₂/p₁"

    def test_superspace_units_row_labels_columns_gL_and_p(self):
        cells = {c.id: c for c in _barbados_superspace(domain_units=True).cells}
        assert [cells[f"urow:superspace_generators:{g}"].text for g in range(3)] == ["/gL₁", "/gL₂", "/gL₃"]
        assert [cells[f"urow:superspace_primes:{p}"].text for p in range(4)] == ["/p₁", "/p₂", "/p₃", "/p₄"]

    def test_superspace_units_column_labels_rows_p_and_gL(self):
        cells = {c.id: c for c in _barbados_superspace(domain_units=True).cells}
        assert [cells[f"ucol:superspace_vectors:{p}"].text for p in range(4)] == ["p₁/", "p₂/", "p₃/", "p₄/"]
        assert [cells[f"ucol:superspace_mapping:{i}"].text for i in range(3)] == ["gL₁/", "gL₂/", "gL₃/"]

    def test_superspace_keeps_p_while_the_nonstandard_domain_swaps_to_b(self):
        cells = {c.id: c for c in _barbados_superspace(domain_units=True, units=True, cell_units=True).cells}
        assert cells["urow:primes:0"].text == "/b₁"
        assert cells["ucol:vectors:0"].text == "b₁/"
        assert cells["tuning:prime:0"].unit == "¢/b₁"
        assert cells["urow:superspace_primes:0"].text == "/p₁"
        assert cells["ucol:superspace_vectors:0"].text == "p₁/"
        assert cells["tuning:superspace_prime:0"].unit == "¢/p₁"

    def test_superspace_units_off_without_domain_units(self):
        cells = {c.id for c in _barbados_superspace().cells}
        assert not any(c.startswith(("urow:superspace_generators", "urow:superspace_primes", "ucol:superspace_")) for c in cells)

    def test_superspace_L_marker_is_a_capital_subscript(self):
        L = grid_tables.SUBSCRIPT_L
        assert L == grid_tables.SUB_OPEN + "L" + grid_tables.SUB_CLOSE
        cells = {c.id: c for c in _barbados_superspace(counts=True, symbols=True, domain_units=True).cells}
        assert cells["count:superspace_generators"].text == f"\U0001D45F{L} = 3"
        assert cells["symbol:tuning:superspace_generators"].text == f"\U0001D488{L}"
        assert cells["urow:superspace_generators:0"].text == f"/g{L}₁"

    def test_superspace_mapping_row_labels_clear_the_bracket_and_cells(self):
        cells = {c.id: c for c in _barbados_superspace(symbols=True, header_symbols=True).cells}
        label = cells["matlabel:row:superspace_mapping:superspace_primes:0"]
        bracket = cells["bracket:superspace_map:0:l"]
        cell0 = cells["cell:superspace_mapping:superspace_primes:0:0"]
        assert label.x + label.w <= bracket.x
        assert bracket.x + bracket.w <= cell0.x

    def test_superspace_matrix_plain_text_stays_within_its_tile(self):
        cells = {c.id: c for c in _barbados_superspace(symbols=True, plain_text_values=True, identity_objects=True).cells}
        plain_text = cells["plain_text:superspace_mapping:superspace_primes"]
        next_label = cells["label:tuning"]
        assert plain_text.y + plain_text.h <= next_label.y

    def test_nonstandard_domain_uses_b_throughout_the_basis_column_not_just_units(self):
        cells = {c.id: c for c in _barbados_superspace(names=True, units=True).cells}
        assert cells["units:mapping:primes"].text == "units: g/b"
        assert cells["units:tuning:primes"].text == "units: ¢/b"
        assert cells["units:superspace_mapping:superspace_primes"].text == f"units: g{grid_tables.SUBSCRIPT_L}/p"

    def test_superspace_tuning_tiles_get_subcolumn_headers(self):
        L = grid_tables.SUBSCRIPT_L
        cells = {c.id: c for c in _barbados_superspace(symbols=True, header_symbols=True).cells}
        assert cells["matlabel:col:tuning:superspace_generators:0"].text == f"\U0001D488{L}₁"
        assert cells["matlabel:col:tuning:superspace_primes:0"].text == f"\U0001D495{L}₁"
        assert cells["matlabel:col:just:superspace_primes:1"].text == f"\U0001D48B{L}₂"
        assert cells["matlabel:col:retune:superspace_primes:0"].text == f"\U0001D493{L}₁"

    def test_superspace_block_is_a_cyan_region_green_at_temperament_columns(self):
        lay = _barbados_superspace(tuning_colorization=True, temperament_colorization=True,
                           counts=True, identity_objects=True)
        cells = {c.id: c for c in lay.cells}
        cyan, green = {"tuning"}, {"tuning", "temperament"}
        assert _color_at(lay, *_mid(cells, "superspace_quantity_generator:0")) == cyan
        assert _color_at(lay, *_mid(cells, "superspace_quantity_prime:0")) == cyan
        assert _color_at(lay, *_mid(cells, "cell:superspace_mapping:superspace_primes:0:0")) == cyan
        assert _color_at(lay, *_mid(cells, "tuning:superspace_generator:0")) == cyan
        assert _color_at(lay, *_mid(cells, "tuning:superspace_prime:0")) == cyan
        assert _color_at(lay, *_mid(cells, "just:superspace_prime:0")) == cyan
        assert _color_at(lay, *_mid(cells, "cell:superspace_vectors:superspace_primes:0:0")) == cyan
        assert _color_at(lay, *_mid(cells, "count:superspace_primes")) == cyan
        assert _color_at(lay, *_mid(cells, "cell:superspace_vectors:primes:0:0")) == green
        assert _color_at(lay, *_mid(cells, "cell:superspace_vectors:commas:0:0")) == green
        assert _color_at(lay, *_mid(cells, "cell:superspace_mapping:primes:0:0")) == green

    def test_size_factor_all_interval_weight_is_a_list_mirroring_the_complexity_row(self):
        lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, charts=True,
                                       symbols=True, header_symbols=True, equivalences=True, names=True).cells}
        assert "weight:target:0" in lils and "chart:weight:targets" in lils
        assert "cell:weight:targets:1:0" not in lils and "bar:weight" not in lils, "NOT a matrix, no size bar"
        assert lils["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"
        assert lils["caption:weight:targets"].text == "target interval weight list"
        assert lils["matlabel:col:weight:targets:0"].text == "w₁ = c₁⁻¹"
        assert lils["matlabel:col:weight:targets:2"].text == "w₃ = c₃⁻¹"
        bare = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, header_symbols=True, equivalences=False).cells}
        assert bare["symbol:weight:targets"].text == "𝒘"
        assert bare["matlabel:col:weight:targets:0"].text == "w₁"
        lp = {c.id: c for c in _with("minimax-S", weighting=True, charts=True, symbols=True, header_symbols=True, equivalences=True).cells}
        assert lp["symbol:weight:targets"].text == "𝒘 = diag(𝐿)⁻¹" and lp["matlabel:col:weight:targets:0"].text == "w₁"
        assert "weight:target:0" in lp and "cell:weight:targets:1:0" not in lp

    def test_a_non_diagonal_pretransformer_all_interval_weight_is_a_reciprocal_list(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s.update(weighting=True, charts=True, symbols=True, header_symbols=True, equivalences=True)
        square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                                 custom_prescaler=square).cells}
        assert "weight:target:0" in on and "chart:weight:targets" in on
        assert "cell:weight:targets:1:0" not in on and "bar:weight" not in on, "NOT a matrix"
        assert on["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"
        assert on["matlabel:col:weight:targets:0"].text == "w₁ = c₁⁻¹", "references the complexity column, not the norm"
        assert on["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝑋[1]‖{grid_tables.NORM_SUB_OPEN}q{grid_tables.NORM_SUB_CLOSE}"

    def test_a_matrix_row_carries_a_unit_on_every_subrow_not_just_the_first(self):
        lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, domain_units=True).cells}
        units = [lils[f"ucol:prescaling:{i}"].text for i in range(4)]
        assert len(set(units)) == 1 and units[0].endswith("/")
        assert "ucol:prescaling" not in lils
        assert "ucol:weight" in lils and "ucol:weight:0" not in lils, "a single-row tile (the weight list) keeps the bare id — generic, not snowflaked"

    def test_read_only_target_vectors_stay_full_width(self):
        cells = {c.id: c for c in _with(scheme="minimax-lils-S").cells}
        real = cells["cell:vector:targets:0:0"]
        assert real.kind == "vector"
        assert real.w == spreadsheet_constants.COL_W

    def test_domain_elements_are_editable_elementcells_with_the_box_on(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        on = {c.id: c for c in spreadsheet.build(state, _nonstd_on(state)).cells}
        assert on["prime:0"].kind == "elementcell" and on["prime:0"].text == "2"
        assert on["prime:2"].kind == "elementratio" and on["prime:2"].text == "13/5"
        off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
        assert off["prime:0"].kind == "prime"
        assert off["prime:2"].kind == "prime"

    def test_domain_header_flips_to_basis_elements_only_with_a_nonprime(self):
        std = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        on = {c.id: c for c in spreadsheet.build(std, _nonstd_on(std)).cells}
        assert on["header:primes"].text == "domain\nprimes"
        off = {c.id: c for c in spreadsheet.build(std, settings.defaults()).cells}
        assert off["header:primes"].text == "domain\nprimes"
        nonprime = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        on_np = {c.id: c for c in spreadsheet.build(nonprime, _nonstd_on(nonprime)).cells}
        assert on_np["header:primes"].text == "domain basis\nelements"

    def test_basis_spine_is_editable_with_the_box_on(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        on = {c.id: c for c in spreadsheet.build(state, _nonstd_on(state)).cells}
        assert on["basis:0"].kind == "elementcell" and on["basis:0"].text == "2"
        assert on["basis:2"].kind == "elementratio" and on["basis:2"].text == "13/5"
        off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
        assert off["basis:0"].kind == "prime" and off["basis:2"].kind == "prime"

    def test_domain_plus_is_element_draft_with_the_box_on(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        on = {c.id: c for c in spreadsheet.build(state, settings.defaults() | {"nonstandard_domain": True}).cells}
        assert "element_plus" in on and "plus" not in on, "the column + opens a typed draft, not a prime walk"
        assert on["basis_plus"].kind == "element_plus", "...and so does the spine + (its kind, the id stays basis_plus)"
        off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
        assert "plus" in off and "element_plus" not in off
        assert off["basis_plus"].kind == "plus", "...and so does the spine +"


class TestBoxOff:
    def test_box_off_walk_minus_gives_way_to_a_per_element_minus_with_the_box_on(self):
        augmented = service.from_comma_basis(((7, 0, -3),))
        off = {c.id for c in spreadsheet.build(augmented).cells}
        assert "basis_minus" in off and "minus" in off
        assert not any(i.startswith("element_minus") for i in off)
        on = {c.id: c for c in spreadsheet.build(augmented, _nonstd_on(augmented)).cells}
        assert "basis_minus" not in on and "minus" not in on
        qty = {f"element_minus:{p}" for p in range(augmented.d)}
        spine = {f"element_minus:basis:{p}" for p in range(augmented.d)}
        assert qty <= set(on) and spine <= set(on)
        assert all(on[f"element_minus:{p}"].prime == p for p in range(augmented.d))

    def test_per_element_domain_minus_is_withheld_at_the_last_element(self):
        sole = service.from_mapping(((1,),))
        on = {c.id for c in spreadsheet.build(sole, _nonstd_on(sole)).cells}
        assert not any(i.startswith("element_minus") for i in on)
        assert "minus" not in on and "basis_minus" not in on

    def test_pending_element_renders_drafts_on_both_axes(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {"nonstandard_domain": True}
        cells = {c.id: c for c in spreadsheet.build(state, s, pending_element="").cells}
        for draft_id, minus_id in (("prime:pending", "element_minus:pending"),
                                   ("basis:pending", "element_minus:basis:pending")):
            draft = cells[draft_id]
            assert draft.kind == "elementratio" and draft.pending and draft.text == "?/?"
            assert minus_id in cells
        assert cells["basis:pending"].y == cells["basis:2"].y + spreadsheet_constants.ROW_H
        assert cells["basis_plus"].y > cells["basis:pending"].y
        typed = {c.id: c for c in spreadsheet.build(state, s, pending_element="9").cells}
        assert typed["prime:pending"].text == "9" and typed["basis:pending"].text == "9"
