from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_emit_mapping import emit_mapping
from rtt.app.spreadsheet_emit_model import EmitResult, build_context
from rtt.app.spreadsheet_emit_vectors import emit_vectors


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
