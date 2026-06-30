from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_brackets import emit_brackets, emit_ebk_frames_and_marks
from rtt.app.spreadsheet_closed_form import _closed_form, closed_form_operand
from rtt.app.spreadsheet_controls import emit_controls, emit_tile_toggles, transform_cells
from rtt.app.spreadsheet_decorations import emit_decorations
from rtt.app.spreadsheet_emit_mapping import emit_canonical_band, emit_mapping, emit_projection_band
from rtt.app.spreadsheet_emit_matrix import (
    emit_column_plus_controls,
    emit_counts_row,
    emit_headers,
    emit_quantities_row,
    emit_rehomed_minus_controls,
    emit_units,
)
from rtt.app.spreadsheet_emit_model import EmitResult, build_context
from rtt.app.spreadsheet_emit_prescaling import emit_prescaling_band
from rtt.app.spreadsheet_emit_tuning import emit_tuning
from rtt.app.spreadsheet_emit_vectors import (
    emit_identity_objects,
    emit_superspace_rows,
    emit_vectors,
)


def _inputs(builder):
    return builder.resolved, builder.geometry, build_context(builder)


def _maximized_builder():
    return spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def _all_bool_on():
    s = settings.defaults()
    for key, value in list(s.items()):
        if isinstance(value, bool):
            s[key] = True
    return s


def _superspace_builder():
    return spreadsheet._GridBuilder(
        service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), _all_bool_on(),
        tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),),
    )


def _math_builder():
    s = {**settings.defaults(), "math_expressions": True}
    return spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)


class TestEmitPure:
    def test_emit_vectors_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_vectors(*_inputs(_maximized_builder()))
        assert isinstance(result, EmitResult)
        ids = {c.id for c in result.cells}
        assert "basis:0" in ids
        assert any(c.id.startswith("cell:vector:detempering") for c in result.cells)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_vectors_emits_nothing_when_the_vectors_row_is_hidden(self):
        s = settings.defaults()
        s["interval_vectors"] = False
        builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)
        result = emit_vectors(*_inputs(builder))
        assert result.cells == ()

    def test_emit_mapping_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_mapping(*_inputs(_maximized_builder()))
        assert isinstance(result, EmitResult)
        ids = {c.id for c in result.cells}
        assert "generator:0" in ids
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_matrix_bands_are_pure_functions(self):
        resolved, geometry, context = _inputs(_maximized_builder())
        headers = {c.id for c in emit_headers(resolved, geometry, context).cells}
        counts = {c.id for c in emit_counts_row(resolved, geometry, context).cells}
        units = {c.id for c in emit_units(resolved, geometry, context).cells}
        assert "header:primes" in headers and "toggle:all" in headers
        assert "count:primes" in counts
        assert any(i.startswith(("units_row:", "units_column:")) for i in units)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert (headers | counts | units) <= full

    def test_emit_quantities_row_is_a_pure_function(self):
        result = emit_quantities_row(*_inputs(_maximized_builder()))
        ids = {c.id for c in result.cells}
        assert "quantities_generator:0" in ids and "prime:0" in ids
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_column_plus_and_rehomed_are_pure_functions(self):
        resolved, geometry, context = _inputs(_maximized_builder())
        plus = emit_column_plus_controls(resolved, geometry)
        rehomed = emit_rehomed_minus_controls(resolved, geometry, context)
        assert isinstance(plus, EmitResult) and isinstance(rehomed, EmitResult)
        assert "generator_plus" in {c.id for c in plus.cells}
        assert rehomed.cells == ()

    def test_emit_projection_band_is_a_pure_function(self):
        s = _all_on()
        builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                           held_basis_ratios=("2/1", "5/4"))
        result = emit_projection_band(*_inputs(builder))
        ids = {c.id for c in result.cells}
        assert any(i.startswith("cell:projection:") for i in ids)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                held_basis_ratios=("2/1", "5/4")).cells}
        assert ids <= full

    def test_emit_superspace_rows_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_superspace_rows(*_inputs(_superspace_builder()))
        ids = {c.id for c in result.cells}
        assert "superspace_basis:0" in ids
        assert any(i.startswith("cell:superspace_mapping:superspace_primes:") for i in ids)
        full = {c.id for c in spreadsheet.build(
            service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), _all_bool_on(),
            tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),)).cells}
        assert ids <= full

    def test_projection_basis_uses_the_stacked_ratio_kind_for_a_nonstandard_element(self):
        result = emit_projection_band(*_inputs(_superspace_builder()))
        ratio = next(c for c in result.cells if c.id.startswith("projection_basis:") and "/" in c.text)
        assert ratio.kind == "commaratio"

    def test_no_basis_cell_renders_a_ratio_as_inline_plain_text(self):
        builds = [
            spreadsheet.build(
                service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), _all_bool_on(),
                tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),)),
            spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on(),
                              held_basis_ratios=("2/1", "5/4")),
        ]
        inline_ratios = [c for build in builds for c in build.cells if c.kind == "prime" and "/" in c.text]
        assert inline_ratios == []

    def test_emit_identity_objects_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_identity_objects(*_inputs(_maximized_builder()))
        ids = {c.id for c in result.cells}
        assert any(i.startswith("cell:vector:primes:") for i in ids)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_brackets_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_brackets(*_inputs(_maximized_builder()))
        ids = {c.id for c in result.cells}
        assert any(i.startswith("bracket:") for i in ids)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_ebk_frames_and_marks_reads_the_accumulator_for_v_split_bars(self):
        resolved, geometry, context = _inputs(_maximized_builder())
        full_layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())
        accum = list(full_layout.cells)
        result = emit_ebk_frames_and_marks(resolved, geometry, context, accum)
        assert isinstance(result, EmitResult)
        ids = {c.id for c in result.cells}
        full = {c.id for c in full_layout.cells}
        assert ids <= full

    def test_emit_tuning_is_a_pure_function_returning_cells_boxes_and_extra(self):
        result = emit_tuning(*_inputs(_maximized_builder()))
        assert isinstance(result, EmitResult)
        ids = {c.id for c in result.cells}
        assert any(i.startswith("tuning:") for i in ids)
        assert set(result.extra) == {"tuning_ranges_box", "optimization_box", "approach_frame", "approach_box"}
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_transform_cells_marks_the_dual_axis_preview_on_a_row_removal(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("row", 0)).cells}
        assert cells["cell:mapped_comma:0:1"].preview_remove
        assert transform_cells((), *_inputs(spreadsheet._GridBuilder(base))) == ()

    def test_emit_controls_is_a_pure_function_returning_cells_and_blocks(self):
        resolved, geometry, context = _inputs(_maximized_builder())
        result = emit_controls(resolved, geometry, context)
        assert isinstance(result, EmitResult)
        cell_ids = {c.id for c in result.cells}
        assert any(i.startswith("preset:") for i in cell_ids)
        full = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())
        assert cell_ids <= {c.id for c in full.cells}
        assert {b.id for b in result.blocks} <= {b.id for b in full.blocks}

    def test_emit_tile_toggles_is_a_pure_function_over_geometry_ctx(self):
        _resolved, geometry, context = _inputs(_maximized_builder())
        result = emit_tile_toggles(geometry, context)
        ids = {c.id for c in result.cells}
        assert any(i.startswith("toggle:tile:") for i in ids)
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert ids <= full

    def test_emit_decorations_is_a_pure_function_returning_cells_lines_and_blocks(self):
        resolved, geometry, context = _inputs(_maximized_builder())
        tuning = emit_tuning(resolved, geometry, context)
        result = emit_decorations(resolved, geometry, context, tuning.region_boxes,
                                  tuning.extra["tuning_ranges_box"], tuning.extra["optimization_box"], tuning.extra["approach_frame"])
        assert isinstance(result, EmitResult)
        assert result.lines and result.blocks
        cell_ids = {c.id for c in result.cells}
        assert any(i.startswith("matrix_label:") for i in cell_ids)
        full = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())
        assert cell_ids <= {c.id for c in full.cells}
        assert {b.id for b in result.blocks} <= {b.id for b in full.blocks}
        assert {line.id for line in result.lines} <= {line.id for line in full.lines}

    def test_emit_prescaling_band_is_a_pure_function_over_resolved_geometry_ctx(self):
        result = emit_prescaling_band(*_inputs(_superspace_builder()))
        ids = {c.id for c in result.cells}
        assert any(i.startswith("cell:prescaling:") for i in ids)
        full = {c.id for c in spreadsheet.build(
            service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), _all_bool_on(),
            tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),)).cells}
        assert ids <= full

    def test_closed_form_operand_is_a_pure_function_over_resolved_geometry_ctx(self):
        builder = _math_builder()
        resolved, geometry, context = _inputs(builder)
        operand = closed_form_operand(resolved, geometry, context, "just", "primes", 0)
        assert operand is not None
        assert closed_form_operand(resolved, geometry, build_context(builder), "just", "primes", 0) == operand

    def test_closed_form_drops_the_redundant_self_cache(self):
        builder = _math_builder()
        assert not hasattr(builder, "_closed_form_cache")
        context = build_context(builder)
        assert _closed_form(builder.resolved, context) is _closed_form(builder.resolved, context)

    def test_emit_canonical_band_is_a_pure_function(self):
        builder = spreadsheet._GridBuilder(service.from_mapping(((1, 0, -4), (0, 1, 4))), _all_on())
        result = emit_canonical_band(*_inputs(builder))
        ids = {c.id for c in result.cells}
        full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, -4), (0, 1, 4))), _all_on()).cells}
        assert ids <= full
