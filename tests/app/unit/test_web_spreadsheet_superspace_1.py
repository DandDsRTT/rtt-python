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
from _spreadsheet_support import _memoized_build, _projection_build, _barbados_superspace, _barbados_superspace_identity, _barbados_projection, _barbados_prescaling, _SUBSCRIPT_DIGITS


class TestNonstandardDomain:
    def test_nonstandard_domain_toggle_is_implemented(self):
        assert "nonstandard_domain" in settings.IMPLEMENTED, "the superspace block (B_L / M_L / M_jL green + 𝒈L / 𝒕L / 𝒋L / 𝒓L cyan + the # mode-gated B_L·T and X_L conversion rows + EBKs + plain text + units) is built, # so the Show panel offers the toggle live rather than greyed out"

    def test_every_derived_matrix_row_greens_its_draft_column(self):
        s = settings.defaults()
        for k, v in list(s.items()):
            if isinstance(v, bool):
                s[k] = True
        barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        VALUE_ROWS = ("quantities", "vectors", "units", "mapping", "tuning", "just", "retune",
                      "prescaling", "complexity", "projection", "scaling_factors",
                      "superspace_vectors", "superspace_mapping", "superspace_projection")
        STRUCTURAL = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "matrix_label", "columngrip", "int_drag"}

        def assert_draft_greened(b, lst, committed, minimum):
            layout = b.layout()
            left = {"held": lambda i: query.held_left(b.geometry, i),
                    "interest": lambda i: query.interest_left(b.geometry, i),
                    "targets": lambda i: query.target_left(b.geometry, i),
                    "commas": lambda i: query.comma_left(b.geometry, b.resolved, i)}[lst]
            dx = left(committed)
            checked = 0
            for row_key in VALUE_ROWS:
                if row_key not in b.geometry.rows or (row_key, lst) not in b.geometry.declared_tiles:
                    continue
                top, height = b.geometry.rows[row_key].tile_top, b.geometry.rows[row_key].tile_height
                hit = any(abs(c.x - dx) < 7 and top - 1 <= c.y <= top + height + 1 and c.kind not in STRUCTURAL
                          for c in layout.cells)
                assert hit, f"first {lst} draft: row {row_key!r} is blank at the draft column (the bug)"
                checked += 1
            assert checked >= minimum, f"{lst}: only {checked} rows checked (config not fully lit?)"

        b = spreadsheet._GridBuilder(barb, s, tuning_scheme="minimax-ES",
                                     held_vectors=(), pending_held=[None, None, None],
                                     interest=(), pending_interest=[None, None, None])
        assert b.resolved.flags.superspace and "prescaling" in b.geometry.rows and "complexity" in b.geometry.rows
        assert_draft_greened(b, "held", 0, minimum=10)
        assert_draft_greened(b, "interest", 0, minimum=10)

        b2 = spreadsheet._GridBuilder(barb, s,
                                      target_override=["3/2", "5/4"], pending_target=[None, None, None],
                                      pending_comma=[None, None, None])
        assert ("units", "targets") in b2.geometry.declared_tiles, "the units tile the targets draft must fill"
        assert_draft_greened(b2, "targets", b2.resolved.dimensions.target_count, minimum=6)
        assert_draft_greened(b2, "commas", b2.resolved.dimensions.comma_count, minimum=6)

    def test_nonstandard_domain_adds_superspace_columns_between_generators_and_primes(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert cells["header:superspace_generators"].text == "superspace\ngenerators"
        assert cells["header:superspace_primes"].text == "superspace\nprimes"
        assert cells["header:generators"].x < cells["header:superspace_generators"].x < cells["header:superspace_primes"].x < cells["header:primes"].x

    def test_nonstandard_domain_superspace_columns_size_to_rL_dL(self):
        layout = _barbados_superspace(equivalences=False)
        cells = {c.id: c for c in layout.cells}
        rL, dL = 3, 4
        expected_superspace_generators_w = 2 * spreadsheet_constants.BRACKET_WIDTH + rL * spreadsheet_constants.COLUMN_WIDTH
        expected_superspace_primes_w = 2 * spreadsheet_constants.BRACKET_WIDTH + dL * spreadsheet_constants.COLUMN_WIDTH
        assert cells["header:superspace_generators"].width == expected_superspace_generators_w, "the header spans the column; the column's content footprint matches # (no caption widening here — Phase 3 declares no captioned tiles in the new columns # so the natural width drives the footprint)"
        assert cells["header:superspace_primes"].width == expected_superspace_primes_w

    def test_nonstandard_domain_off_omits_the_superspace_columns(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cells = {c.id for c in spreadsheet.build(state, s).cells}
        assert "header:superspace_generators" not in cells
        assert "header:superspace_primes" not in cells

    def test_nonstandard_domain_superspace_columns_head_their_quantities(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert [cells[f"superspace_quantity_prime:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
        assert [cells[f"superspace_quantity_generator:{g}"].text for g in range(3)] == ["2/1", "26/3", "130/3"]
        assert cells["superspace_quantity_generator:0"].kind == "generator_ratio"
        assert cells["superspace_quantity_prime:0"].kind == "commaratio"
        assert cells["superspace_quantity_generator:0"].x == cells["tuning:superspace_generator:0"].x
        assert cells["superspace_quantity_prime:0"].x == cells["tuning:superspace_prime:0"].x
        assert cells["superspace_quantity_generator:0"].y == cells["prime:0"].y == cells["superspace_quantity_prime:0"].y

    def test_nonstandard_domain_superspace_quantities_are_derived_read_only(self):
        cells = {c.id for c in _barbados_superspace().cells}
        assert "superspace_quantity_generator:0" in cells and "superspace_quantity_prime:0" in cells
        assert not any(c.startswith(("superspace_quantity_generator_plus", "superspace_quantity_generator_minus", "superspace_quantity_prime_plus", "superspace_quantity_prime_minus")) for c in cells)

    def test_nonstandard_domain_off_omits_the_superspace_quantities(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cells = {c.id for c in spreadsheet.build(state, s).cells}
        assert "superspace_quantity_generator:0" not in cells
        assert "superspace_quantity_prime:0" not in cells

    def test_nonstandard_domain_adds_superspace_rows_between_mapping_and_tuning(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert cells["label:superspace_vectors"].text == "superspace\ninterval vectors"
        assert cells["label:superspace_mapping"].text == "superspace\nmapping"
        assert cells["label:mapping"].y < cells["label:superspace_vectors"].y < cells["label:superspace_mapping"].y < cells["label:tuning"].y

    def test_nonstandard_domain_superspace_rows_size_to_dL_rL(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        dL, rL = 4, 3
        assert cells["label:superspace_vectors"].height == dL * spreadsheet_constants.ROW_HEIGHT
        assert cells["label:superspace_mapping"].height == rL * spreadsheet_constants.ROW_HEIGHT

    def test_nonstandard_domain_off_omits_the_superspace_rows(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cells = {c.id for c in spreadsheet.build(state, s).cells}
        assert "label:superspace_vectors" not in cells
        assert "label:superspace_mapping" not in cells

    def test_nonstandard_domain_adds_rL_dL_counts_when_counts_is_on(self):
        cells = {c.id: c for c in _barbados_superspace(counts=True).cells}
        assert cells["count:superspace_generators"].text == "\U0001D45FL = 3"
        assert cells["count:superspace_primes"].text == "\U0001D451L = 4"

    def test_count_panels_back_every_superspace_count_too(self):
        layout = _barbados_superspace(counts=True)
        blocks = {b.id for b in layout.blocks}
        assert "block:counts:superspace_generators" in blocks
        assert "block:counts:superspace_primes" in blocks

    def test_superspace_counts_carry_captions_when_names_is_on(self):
        cells = {c.id: c for c in _barbados_superspace(counts=True, names=True).cells}
        assert cells["caption:counts:superspace_generators"].text == "superspace rank"
        assert cells["caption:counts:superspace_primes"].text == "superspace dimensionality"

    def test_superspace_vectors_quantities_spine_lists_the_superspace_primes(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert [cells[f"superspace_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
        for p in range(3):
            assert cells[f"superspace_basis:{p}"].y < cells[f"superspace_basis:{p+1}"].y

    def test_superspace_vectors_spine_is_centred_in_the_quantities_column(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        assert cells["superspace_basis:0"].x == cells["basis:0"].x
        assert cells["superspace_basis:0"].width == cells["basis:0"].width == spreadsheet_constants.COLUMN_WIDTH

    def test_nonstandard_domain_off_omits_the_spine_basis_index(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cells = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cell_id.startswith("superspace_basis:") for cell_id in cells)

    def test_superspace_block_tiles_get_their_grey_panels(self):
        layout = _barbados_superspace()
        blocks = {b.id for b in layout.blocks}
        expected = {
            "block:superspace_vectors:quantities", "block:superspace_vectors:primes",
            "block:superspace_vectors:commas", "block:superspace_vectors:targets",
            "block:superspace_mapping:superspace_primes",
            "block:tuning:superspace_generators", "block:tuning:superspace_primes",
            "block:just:superspace_primes", "block:retune:superspace_primes",
        }
        assert expected <= blocks

    def test_superspace_block_tiles_get_per_tile_fold_toggles(self):
        cells = {c.id for c in _barbados_superspace().cells}
        expected = {
            "toggle:tile:superspace_vectors:quantities", "toggle:tile:superspace_vectors:primes",
            "toggle:tile:superspace_vectors:commas", "toggle:tile:superspace_vectors:targets",
            "toggle:tile:superspace_mapping:superspace_primes",
            "toggle:tile:tuning:superspace_generators", "toggle:tile:tuning:superspace_primes",
            "toggle:tile:just:superspace_primes", "toggle:tile:retune:superspace_primes",
        }
        assert expected <= cells

    def test_superspace_columns_get_their_fold_toggles_in_the_header_band(self):
        cells = {c.id for c in _barbados_superspace().cells}
        assert {"toggle:column:superspace_generators", "toggle:column:superspace_primes"} <= cells

    def test_superspace_projection_row_renders_PL_over_the_superspace_primes(self):
        cells = {c.id: c for c in _barbados_projection().cells}
        assert cells["label:superspace_projection"].text == "superspace\nprojection"
        assert cells["label:superspace_projection"].height == 4 * spreadsheet_constants.ROW_HEIGHT
        assert cells["label:superspace_mapping"].y < cells["label:superspace_projection"].y < cells["label:projection"].y
        assert {f"cell:superspace_projection:superspace_primes:{i}:{j}" for i in range(4) for j in range(4)} <= set(cells)
        assert cells["cell:superspace_projection:superspace_primes:0:0"].text == "1"
        assert cells["cell:superspace_projection:superspace_primes:0:1"].text == "2/3"
        assert cells["cell:superspace_projection:superspace_primes:2:2"].text == "1"
        assert cells["cell:superspace_projection:superspace_primes:3:1"].text == "2/3"
        assert cells["cell:superspace_projection:superspace_primes:0:0"].x == cells["cell:superspace_mapping:superspace_primes:0:0"].x

    def test_superspace_projection_row_renders_the_embedding_and_projected_lists(self):
        cells = {c.id: c for c in _barbados_projection().cells}
        assert {f"cell:superspace_embed:{i}:{g}" for i in range(4) for g in range(3)} <= set(cells)
        assert cells["cell:superspace_embed:0:0"].text == "1" and cells["cell:superspace_embed:0:1"].text == "1/3"
        assert {f"cell:superspace_projection_basis_lift:{e}:{p}" for e in range(3) for p in range(4)} <= set(cells)
        assert cells["cell:superspace_projection_basis_lift:0:0"].text == "1"
        assert cells["cell:superspace_projection_basis_lift:1:0"].text == "2/3"
        assert {f"cell:superspace_projection_vectors:{p}:0" for p in range(4)} <= set(cells)
        assert [cells[f"cell:superspace_projection_vectors:{p}:0"].text for p in range(4)] == ["0", "0", "0", "0"]
        assert any(c.startswith("cell:superspace_projection_targets:") for c in cells), "P_L·T_L the projected target list, dL-tall over the targets, not dashed (a full rational projection)"
        assert cells["cell:superspace_projection_targets:0:0"].text != spreadsheet_constants.DASH
        assert cells["caption:superspace_projection:superspace_generators"].text == "superspace generator embedding"
        assert cells["caption:superspace_projection:primes"].text == "superspace projected subspace basis elements"

    def test_superspace_projection_detempering_tile_renders_when_shown(self):
        cells = {c.id: c for c in _barbados_projection(generator_detempering=True).cells}
        assert {f"cell:superspace_projection_detempering:{i}:{p}" for i in range(2) for p in range(4)} <= set(cells)
        assert cells["cell:superspace_projection_detempering:0:0"].text != spreadsheet_constants.DASH, "a full rational projection, not dashed"
        assert cells["caption:superspace_projection:detempering"].text == "projected generator detempering in superspace"
        off = {c.id for c in _barbados_projection().cells}
        assert not any(c.startswith("cell:superspace_projection_detempering:") for c in off)

    def test_superspace_projection_extra_tiles_dash_when_under_held(self):
        cells = {c.id: c for c in _barbados_projection(held_basis_ratios=(), generator_detempering=True).cells}
        assert cells["cell:superspace_embed:0:0"].text == spreadsheet_constants.DASH
        assert cells["cell:superspace_projection_basis_lift:0:0"].text == spreadsheet_constants.DASH
        assert cells["cell:superspace_projection_detempering:0:0"].text == spreadsheet_constants.DASH
        assert cells["cell:superspace_projection_targets:0:0"].text == spreadsheet_constants.DASH

    def test_superspace_projection_extra_tiles_absent_without_projection(self):
        cells = {c.id for c in _barbados_superspace(generator_detempering=True).cells}
        assert not any(c.startswith(("cell:superspace_embed:", "cell:superspace_projection_basis_lift:", "cell:superspace_projection_detempering:",
                                     "cell:superspace_projection_vectors:", "cell:superspace_projection_targets:", "cell:superspace_projection_held:",
                                     "cell:superspace_projection_interest:")) for c in cells)

    def test_superspace_projection_row_dashes_when_under_held(self):
        cells = {c.id: c for c in _barbados_projection(held_basis_ratios=()).cells}
        assert cells["cell:superspace_projection:superspace_primes:0:0"].text == spreadsheet_constants.DASH
        assert cells["cell:superspace_projection:superspace_primes:3:3"].text == spreadsheet_constants.DASH

    def test_superspace_projection_row_absent_without_the_projection_toggle(self):
        cells = {c.id for c in _barbados_superspace().cells}
        assert "label:superspace_mapping" in cells
        assert "label:superspace_projection" not in cells
        assert not any(c.startswith("cell:superspace_projection:") for c in cells)

    def test_superspace_projection_row_absent_on_a_standard_domain(self):
        cells = {c.id for c in _projection_build(("2", "5/4")).cells}
        assert "cell:projection:0:0" in cells
        assert "label:superspace_projection" not in cells
        assert not any(c.startswith("cell:superspace_projection:") for c in cells)


class TestSuperspaceProjection:
    def test_superspace_projection_quantities_spine_lists_the_superspace_primes(self):
        cells = {c.id: c for c in _barbados_projection().cells}
        assert [cells[f"superspace_projection_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
        assert [cells[f"superspace_projection_basis:{p}"].text for p in range(4)] == [cells[f"superspace_basis:{p}"].text for p in range(4)]
        assert cells["superspace_projection_basis:0"].x == cells["superspace_basis:0"].x
        assert cells["superspace_projection_basis:0"].width == spreadsheet_constants.COLUMN_WIDTH

    def test_superspace_projection_units_column_reads_superspace_prime(self):
        cells = {c.id: c for c in _barbados_projection(domain_units=True).cells}
        assert cells["units_column:superspace_projection:0"].text == "p₁/"
        assert cells["units_column:superspace_projection:3"].text == "p₄/"

    def test_superspace_projection_row_carries_the_full_projected_tile_set(self):
        cells = {c.id: c for c in _barbados_projection(generator_detempering=True).cells}
        assert {f"cell:superspace_embed:{i}:{g}" for i in range(4) for g in range(3)} <= set(cells)
        assert {f"cell:superspace_projection_basis_lift:{e}:{p}" for e in range(3) for p in range(4)} <= set(cells)
        assert {f"cell:superspace_projection_detempering:{i}:{p}" for i in range(2) for p in range(4)} <= set(cells)
        assert "cell:superspace_projection_targets:0:0" in cells
        assert all(cells[f"cell:superspace_projection_vectors:{p}:0"].text == "0" for p in range(4))

    def test_superspace_projection_embedding_G_L_matches_the_service(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        gl = service.superspace_tuning_embedding(state, ("2", "13/5"))
        cells = {c.id: c for c in _barbados_projection().cells}
        assert [[cells[f"cell:superspace_embed:{i}:{g}"].text for g in range(3)] for i in range(4)] == [list(r) for r in gl]

    def test_superspace_projection_projected_basis_matches_P_L_times_B_L(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pl = service.superspace_projection_matrix_rationals(state, ("2", "13/5"))
        expected = service.project_vectors(pl, service.basis_in_superspace(state.domain_basis))
        cells = {c.id: c for c in _barbados_projection().cells}
        assert [[cells[f"cell:superspace_projection_basis_lift:{e}:{p}"].text for p in range(4)] for e in range(3)] \
            == [[str(x) for x in v] for v in expected]

    def test_superspace_projection_extra_tiles_carry_captions_symbols_and_units(self):
        cells = {c.id: c for c in _barbados_projection(generator_detempering=True, names=True, symbols=True, units=True).cells}
        assert cells["caption:superspace_projection:superspace_generators"].text == "superspace generator embedding"
        assert cells["caption:superspace_projection:primes"].text == "superspace projected subspace basis elements"
        assert cells["caption:superspace_projection:detempering"].text == "projected generator detempering in superspace"
        assert cells["caption:superspace_projection:targets"].text == "projected target interval list in superspace"
        assert cells["caption:superspace_projection:commas"].text == "projected unrotated vector list in superspace"
        assert cells["symbol:superspace_projection:superspace_generators"].text == "GL"
        assert cells["symbol:superspace_projection:primes"].text == grid_tables.SYMBOLS[("superspace_projection", "primes")]
        assert cells["units:superspace_projection:superspace_generators"].text == "units: p/gL"
        assert cells["units:superspace_projection:primes"].text == "units: p/b"
        assert cells["units:superspace_projection:detempering"].text == "units: p"

    def test_superspace_projection_emits_a_plain_text_band(self):
        cells = {c.id for c in _barbados_projection(plain_text_values=True).cells}
        assert "plain_text:superspace_projection:superspace_primes" in cells
        off = {c.id for c in _barbados_superspace(plain_text_values=True).cells}
        assert "plain_text:superspace_mapping:superspace_primes" in off
        assert "plain_text:superspace_projection:superspace_primes" not in off

    def test_superspace_projection_every_tile_emits_a_plain_text_band(self):
        cells = {c.id for c in _barbados_projection(plain_text_values=True, generator_detempering=True).cells}
        for column in ["superspace_generators", "superspace_primes", "primes", "detempering", "commas", "targets"]:
            assert f"plain_text:superspace_projection:{column}" in cells, column

    def test_superspace_projection_caption_symbol_and_units_when_named(self):
        cells = {c.id: c for c in _barbados_projection(names=True, symbols=True, header_symbols=True, units=True).cells}
        assert cells["caption:superspace_projection:superspace_primes"].text == "superspace projection"
        assert "matrix_label:row:superspace_projection:superspace_primes:0" in cells
        assert cells["units:superspace_projection:superspace_primes"].text == "units: p/p"

    def test_superspace_rows_get_their_fold_toggles_in_the_label_gutter(self):
        cells = {c.id for c in _barbados_superspace().cells}
        assert {"toggle:row:superspace_vectors", "toggle:row:superspace_mapping"} <= cells

    def test_superspace_columns_get_column_axes_fanned_into_per_cell_sub_axes(self):
        lines = {line.id for line in _barbados_superspace().lines}
        assert {"v:superspace_generator:0", "v:superspace_generator:1", "v:superspace_generator:2"} <= lines
        assert {"v:superspace_prime:0", "v:superspace_prime:1", "v:superspace_prime:2", "v:superspace_prime:3"} <= lines

    def test_superspace_rows_get_horizontal_axes(self):
        lines = {line.id for line in _barbados_superspace().lines}
        assert {"h:superspace_mapping:0", "h:superspace_mapping:1", "h:superspace_mapping:2"} <= lines
        assert {"h:superspace_vectors:0", "h:superspace_vectors:1", "h:superspace_vectors:2", "h:superspace_vectors:3"} <= lines

    def test_M_L_tile_has_a_caption_and_symbol(self):
        cells = {c.id: c for c in _barbados_superspace(names=True, symbols=True, equivalences=False).cells}
        assert cells["caption:superspace_mapping:superspace_primes"].text == "superspace mapping"
        assert cells["symbol:superspace_mapping:superspace_primes"].text == "\U0001D440L"

    def test_B_L_tile_has_a_caption_and_symbol(self):
        cells = {c.id: c for c in _barbados_superspace(names=True, symbols=True).cells}
        assert cells["caption:superspace_vectors:primes"].text == "basis change matrix"
        assert cells["symbol:superspace_vectors:primes"].text == "BL"

    def test_B_L_units_line_reads_superspace_prime_over_domain_element(self):
        cells = {c.id: c for c in _barbados_superspace(units=True).cells}
        assert cells["units:superspace_vectors:primes"].text == "units: p/b"
        id_cells = {c.id: c for c in _barbados_superspace_identity(units=True).cells}
        assert id_cells["units:superspace_vectors:superspace_primes"].text == "units: p/p"

    def test_nonstandard_domain_off_leaves_no_superspace_trace(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {"names": True, "symbols": True, "counts": True}
        layout = spreadsheet.build(state, s)
        ids = {c.id for c in layout.cells} | {b.id for b in layout.blocks} | {line.id for line in layout.lines}
        assert not any(s in i for i in ids for s in ("superspace_generators", "superspace_primes", "superspace_vectors", "superspace_mapping", "superspace_basis", "superspace_generator", "superspace_prime"))

    def test_standard_domain_with_toggle_on_shows_no_superspace_but_enables_editing(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults() | {"nonstandard_domain": True, "counts": True}
        layout = spreadsheet.build(state, s)
        cells = {c.id: c for c in layout.cells}
        ids = {c.id for c in layout.cells} | {b.id for b in layout.blocks} | {line.id for line in layout.lines}
        assert not any(token in i for i in ids
                       for token in ("superspace_generators", "superspace_primes", "superspace_vectors", "superspace_mapping", "superspace_basis",
                                   "superspace_generator", "superspace_prime"))
        assert cells["prime:0"].kind == "elementcell"
        assert cells["header:primes"].text == "domain\nprimes"

    def test_nonstandard_all_prime_subgroup_with_toggle_on_shows_no_superspace(self):
        state = service.from_temperament_data("2.5.7 [⟨1 0 0] ⟨0 1 1]}")
        assert not service.domain_has_nonprimes(state.domain_basis)
        assert not service.is_standard_domain(state.domain_basis)
        s = settings.defaults() | {"nonstandard_domain": True}
        layout = spreadsheet.build(state, s)
        cells = {c.id: c for c in layout.cells}
        ids = {c.id for c in layout.cells} | {b.id for b in layout.blocks} | {line.id for line in layout.lines}
        assert not any(token in i for i in ids
                       for token in ("superspace_generators", "superspace_primes", "superspace_vectors", "superspace_mapping", "superspace_basis",
                                   "superspace_generator", "superspace_prime"))
        assert cells["prime:0"].kind == "elementcell"
        assert cells["header:primes"].text == "domain\nprimes"

    def test_nonprime_based_approach_collapses_the_entire_superspace(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {"nonstandard_domain": True}
        layout = spreadsheet.build(state, s, nonprime_approach="nonprime-based")
        ids = {c.id for c in layout.cells} | {b.id for b in layout.blocks} | {line.id for line in layout.lines}
        assert not any(token in i for i in ids
                       for token in ("superspace_generators", "superspace_primes", "superspace_vectors", "superspace_mapping", "superspace_basis",
                                   "superspace_generator", "superspace_prime"))

    def test_superspace_prescaler_interactivity_and_controls_shift_to_superspace_primes(self):
        cells = {c.id: c for c in _barbados_prescaling().cells}
        assert cells["plain_text:prescaling:superspace_primes"].kind == "plain_text_edit", "the bare prescaler's plain text stays editable — now in superspace-primes; the 𝐿·B_Ls plain text is # read-only, and reads ⟨[…⟩ …] (a matrix of kets like B_L), NOT the backwards bare-prescaler stack"
        assert cells["plain_text:prescaling:primes"].kind == "plain_text"
        assert cells["plain_text:prescaling:primes"].text.startswith("⟨[") and cells["plain_text:prescaling:primes"].text.endswith("]")
        assert sum(1 for i in cells if i.startswith("matrix_label:row:prescaling:primes:")) == 0, "𝐿·B_Ls is a matrix of kets, so it takes COLUMN headers (one per domain element, like B_L), # NOT the bare prescaler's row headers; the bare prescaler (superspace-primes) keeps its dL row headers"
        assert sum(1 for i in cells if i.startswith("matrix_label:column:prescaling:primes:")) == 3
        assert sum(1 for i in cells if i.startswith("matrix_label:row:prescaling:superspace_primes:")) == 4
        assert "preset:prescaler" in cells
        assert abs(cells["preset:prescaler"].x - cells["header:superspace_primes"].x) < abs(cells["preset:prescaler"].x - cells["header:primes"].x)

    def test_superspace_shifts_the_complexity_prescaler_into_the_superspace_primes_column(self):
        cells = {c.id: c for c in _barbados_prescaling().cells}
        assert cells["caption:prescaling:superspace_primes"].text == "(superspace) complexity prescaler = log-prime matrix", "the bare prescaler's '= log-prime matrix' NAME (equivalences on) lands on the superspace-primes tile — # NOT on the domain-primes 𝐿·B_Ls product (a product prints no '= …')"
        assert cells["caption:prescaling:primes"].text == "complexity prescaled subspace basis elements"
        assert cells["caption:complexity:superspace_primes"].text == "domain prime complexity map"
        assert cells["caption:complexity:primes"].text == "subspace basis element complexity map"
        assert "cell:prescaling:superspace_primes:3:3" in cells, "the prescaling matrices lift to dL = 4 rows (the superspace primes 2.3.5.13), not d = 3: the # bare superspace-primes prescaler is dL×dL, so its 4th diagonal entry (row 3, col 3) exists and is # log-prime over the TRUE primes — log₂13 ≈ 3.700, the new prime 13 disentangled from 13/5"
        assert abs(float(cells["cell:prescaling:superspace_primes:3:3"].text) - 3.7004) < 0.01
        assert "cell:prescaling:primes:3:0" in cells
        assert cells["complexity:prime:2"].text == "6.022", "the displayed complexities ARE ‖𝐿·(B_L·v)‖ — the corrected get_complexity. The subspace basis # element complexity of 13/5 prime-factors to log₂(13·5) = 6.022 (NOT log₂5 = 2.322, the # out-of-limit 13 dropped — the bug fixed by passing domain_basis); the superspace-primes prime # complexity map is log-prime over the true primes, so the 3rd entry is log₂5 = 2.322"
        assert cells["complexity:superspace_prime:2"].text == "2.322"

    def test_superspace_prescaler_shift_only_for_neutral_and_prime_based(self):
        for approach in ("nonprime-based",):
            cells = {c.id: c for c in _barbados_prescaling(approach=approach).cells}
            assert not any(cell_id.startswith("cell:prescaling:superspace_primes:") for cell_id in cells)
            assert cells["caption:prescaling:primes"].text.startswith("complexity prescaler"), "the domain-primes tile keeps the plain bare-prescaler name (it stays the bare 𝐿 here), # NOT the shifted 'complexity prescaled subspace basis elements' product caption"
        off = {c.id: c for c in _barbados_prescaling(nonstandard=False).cells}
        assert not any(cell_id.startswith("cell:prescaling:superspace_primes:") for cell_id in off)
        assert off["caption:prescaling:primes"].text.startswith("complexity prescaler")

    def test_prime_based_shifts_generator_editing_to_superspace(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults() | {"nonstandard_domain": True, "plain_text_values": True, "presets": True}
        prime = {c.id: c for c in spreadsheet.build(state, s, nonprime_approach="prime-based").cells}
        assert {prime[i].kind for i in prime if i.startswith("tuning:generator:")} == {"tuningvalue"}
        assert {prime[i].kind for i in prime if i.startswith("tuning:superspace_generator:")} == {"generator_tuning_cell"}
        assert prime["plain_text:tuning:generators"].kind == "plain_text"
        assert prime["plain_text:tuning:superspace_generators"].kind == "plain_text_edit"
        assert "preset:tuning:superspace_generators" in prime
        neutral = {c.id: c for c in spreadsheet.build(state, s, nonprime_approach="").cells}
        assert {neutral[i].kind for i in neutral if i.startswith("tuning:generator:")} == {"generator_tuning_cell"}
        assert {neutral[i].kind for i in neutral if i.startswith("tuning:superspace_generator:")} == {"tuningvalue"}

    def test_approach_radio_band_only_for_a_nonprime_domain(self):
        on = settings.defaults() | {"nonstandard_domain": True}
        nonprime = spreadsheet.build(service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), on)
        assert nonprime.approach_box is not None
        title = {c.id: c for c in nonprime.cells}["optimization:approach:title"]
        assert title.kind == "boxtitle" and title.text == "nonstandard domain approach"
        std = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), on)
        assert std.approach_box is None
        assert "optimization:approach:title" not in {c.id for c in std.cells}
        sub = spreadsheet.build(service.from_temperament_data("2.5.7 [⟨1 0 0] ⟨0 1 1]}"), on)
        assert sub.approach_box is None

    def test_B_L_emits_one_cell_per_superspace_prime_row_and_domain_element_col(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        expected_by_element = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
        for elem_idx, vector in enumerate(expected_by_element):
            for superspace_prime_idx, value in enumerate(vector):
                assert cells[f"cell:superspace_vectors:primes:{superspace_prime_idx}:{elem_idx}"].text == str(value)

    def test_B_L_cells_ride_the_existing_prime_gridlines_and_superspace_vector_rows(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for elem_idx in range(3):
            for superspace_prime_idx in range(4):
                bl = cells[f"cell:superspace_vectors:primes:{superspace_prime_idx}:{elem_idx}"]
                assert bl.x == cells[f"cell:mapping:0:{elem_idx}"].x
                assert bl.y == cells[f"superspace_basis:{superspace_prime_idx}"].y

    def test_B_L_off_omits_the_cells(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cell_id.startswith("cell:superspace_vectors:primes:") for cell_id in cids)

    def test_B_L_absent_over_a_standard_prime_domain(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults() | {"nonstandard_domain": True}
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cell_id.startswith("cell:superspace_vectors:primes:") for cell_id in cids)


    _SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


class TestMLTile:
    def test_M_L_emits_one_cell_per_superspace_generator_row_and_superspace_prime_col(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        ml = service.superspace_mapping(
            service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"))
        for generator_idx, row in enumerate(ml):
            for superspace_prime_idx, value in enumerate(row):
                assert cells[f"cell:superspace_mapping:superspace_primes:{generator_idx}:{superspace_prime_idx}"].text == str(value)

    def test_M_L_cells_ride_the_superspace_primes_gridlines_and_superspace_mapping_rows(self):
        cells = {c.id: c for c in _barbados_superspace().cells}
        for generator_idx in range(3):
            for superspace_prime_idx in range(4):
                cell = cells[f"cell:superspace_mapping:superspace_primes:{generator_idx}:{superspace_prime_idx}"]
                assert cell.x == cells[f"cell:superspace_mapping:superspace_primes:0:{superspace_prime_idx}"].x
                assert cell.y == cells[f"cell:superspace_mapping:superspace_primes:{generator_idx}:0"].y

    def test_M_L_off_omits_the_cells(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        cids = {c.id for c in spreadsheet.build(state, s).cells}
        assert not any(cell_id.startswith("cell:superspace_mapping:superspace_primes:") for cell_id in cids)
