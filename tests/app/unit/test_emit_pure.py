from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_emit_mapping import emit_mapping, emit_projection_band
from rtt.app.spreadsheet_emit_matrix import (
    emit_column_plus_controls,
    emit_counts_row,
    emit_headers,
    emit_quantities_row,
    emit_rehomed_minus_controls,
    emit_units,
)
from rtt.app.spreadsheet_emit_model import EmitResult, build_context
from rtt.app.spreadsheet_emit_vectors import emit_vectors


def _maximized_builder():
    return spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def test_emit_vectors_is_a_pure_function_over_resolved_geometry_ctx():
    builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())
    result = emit_vectors(builder.resolved, builder.geometry, build_context(builder))
    assert isinstance(result, EmitResult)
    ids = {c.id for c in result.cells}
    assert "basis:0" in ids
    assert any(c.id.startswith("cell:vec:detempering") for c in result.cells)
    # every cell it emits also appears in the full build (it owns the vectors band)
    full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert ids <= full


def test_emit_vectors_emits_nothing_when_the_vectors_row_is_hidden():
    s = settings.defaults()
    s["interval_vectors"] = False
    builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)
    result = emit_vectors(builder.resolved, builder.geometry, build_context(builder))
    assert result.cells == ()


def test_emit_mapping_is_a_pure_function_over_resolved_geometry_ctx():
    builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on())
    result = emit_mapping(builder.resolved, builder.geometry, build_context(builder))
    assert isinstance(result, EmitResult)
    ids = {c.id for c in result.cells}
    assert "gen:0" in ids
    full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert ids <= full


def test_emit_matrix_bands_are_pure_functions():
    builder = _maximized_builder()
    ctx = build_context(builder)
    headers = {c.id for c in emit_headers(builder.resolved, builder.geometry, ctx).cells}
    counts = {c.id for c in emit_counts_row(builder.resolved, builder.geometry, ctx).cells}
    units = {c.id for c in emit_units(builder.resolved, builder.geometry, ctx).cells}
    assert "header:primes" in headers and "toggle:all" in headers
    assert "count:primes" in counts
    assert any(i.startswith(("urow:", "ucol:")) for i in units)
    full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert (headers | counts | units) <= full


def test_emit_quantities_row_is_a_pure_function():
    builder = _maximized_builder()
    result = emit_quantities_row(builder.resolved, builder.geometry, build_context(builder))
    ids = {c.id for c in result.cells}
    assert "qgen:0" in ids and "prime:0" in ids
    full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert ids <= full


def test_emit_column_plus_and_rehomed_are_pure_functions():
    builder = _maximized_builder()
    ctx = build_context(builder)
    plus = emit_column_plus_controls(builder.resolved, builder.geometry)
    rehomed = emit_rehomed_minus_controls(builder.resolved, builder.geometry, ctx)
    assert isinstance(plus, EmitResult) and isinstance(rehomed, EmitResult)
    assert "gen_plus" in {c.id for c in plus.cells}
    # rehomed minus controls only emit when the quantities row is collapsed and vectors open
    assert rehomed.cells == ()


def test_emit_projection_band_is_a_pure_function():
    s = _all_on()
    builder = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                       held_basis_ratios=("2/1", "5/4"))
    result = emit_projection_band(builder.resolved, builder.geometry, build_context(builder))
    ids = {c.id for c in result.cells}
    assert any(i.startswith("cell:proj:") for i in ids)
    full = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                            held_basis_ratios=("2/1", "5/4")).cells}
    assert ids <= full
