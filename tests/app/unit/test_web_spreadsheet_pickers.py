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
from _spreadsheet_support import _memoized_build, _with


class TestSubPickerPlacement:
    def test_etpick_rides_the_right_gutter_of_each_mapping_row(self):
        cells = {c.id: c for c in _with(presets=True).cells}
        for i in range(2):
            ep = cells[f"etpick:{i}"]
            assert ep.kind == "etpick" and ep.gen == i
            assert ep.width == spreadsheet_constants.COLUMN_WIDTH and ep.height == spreadsheet_constants.ROW_HEIGHT
            assert ep.y == cells[f"cell:mapping:{i}:0"].y
            close_bracket = cells[f"bracket:map:{i}:r"]
            assert ep.x >= close_bracket.x + close_bracket.width
        off = {c.id: c for c in _with(presets=False).cells}
        assert not any(k.startswith("etpick:") for k in off)

    def test_et_picker_keeps_the_mapping_matrix_centred_in_its_tile(self):
        layout = _with(presets=True, drag_to_combine=True, header_symbols=True)
        cells = {c.id: c for c in layout.cells}
        tile = {b.id: b for b in layout.blocks}["block:primes"]
        lb, rb = cells["bracket:map:0:l"], cells["bracket:map:0:r"]
        m_left, m_right = lb.x, rb.x + rb.width
        assert abs((m_left - tile.x) - ((tile.x + tile.width) - m_right)) < 0.51
        ep = cells["etpick:0"]
        assert ep.x >= m_right
        assert abs((ep.x + ep.width) - (tile.x + tile.width - spreadsheet_constants.PAD)) < 0.51
        handle, label = cells["map_drag:0"], cells["matrix_label:row:mapping:primes:0"]
        assert tile.x <= handle.x and handle.x + handle.width <= label.x
        assert abs((label.x + label.width) - m_left) < 0.51

    def test_commapick_rides_below_each_real_comma_column(self):
        cells = {c.id: c for c in _with(presets=True).cells}
        cp = cells["commapick:0"]
        assert cp.kind == "commapick" and cp.comma == 0
        assert cp.width == spreadsheet_constants.COLUMN_WIDTH and cp.height == spreadsheet_constants.ROW_HEIGHT
        column_cell = next(c for cell_id, c in cells.items()
                           if cell_id.startswith("cell:comma:0:") and c.comma == 0)
        assert cp.x == column_cell.x
        assert cp.y > column_cell.y
        assert not any(c.id.startswith("commapick:") for c in _with(presets=False).cells)

    def test_a_full_rank_temperament_has_no_comma_pickers(self):
        full = spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))),
                                 {**settings.defaults(), "presets": True})
        assert not any(c.id.startswith("commapick:") for c in full.cells)
        assert any(c.id.startswith("etpick:") for c in full.cells)

    def test_green_draft_row_and_column_get_their_own_pickers(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "presets": True}
        cc = {c.id: c for c in spreadsheet.build(base, s, pending_comma=[None, None, None]).cells}
        assert "commapick:draft" in cc and cc["commapick:draft"].pending
        draft_col = next(c for cell_id, c in cc.items() if cell_id.startswith("cell:comma:0:") and c.pending)
        assert cc["commapick:draft"].x == draft_col.x
        mc = {c.id: c for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
        assert "etpick:draft" in mc and mc["etpick:draft"].pending
        assert mc["etpick:draft"].x == mc["etpick:0"].x
        full = spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))),
                                 s, pending_comma=[None, None, None])
        assert any(c.id == "commapick:draft" for c in full.cells)
