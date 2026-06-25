from types import SimpleNamespace

from rtt.app import spreadsheet_geometry_query as query
from rtt.app.spreadsheet_constants import FRAME_GAP, FRAME_H, ROW_H
from rtt.app.spreadsheet_models import RowBand


def _row(y, h=10.0, frame=2.0, sym=3.0, cap=4.0, units=5.0):
    return RowBand(y=y, h=h, label="", collapsible=True, tile_h=0.0, tile_top=0.0,
                   frame=frame, sym=sym, cap=cap, units=units, ptext=0.0, pre=0.0,
                   schemebtn=0.0, nsub=1)


def _geometry():
    return SimpleNamespace(
        rows={"mapping": _row(100.0), "projection": _row(200.0), "canon": _row(300.0),
              "vectors": _row(400.0), "ss_vectors": _row(500.0), "ss_mapping": _row(600.0),
              "ss_projection": _row(700.0)},
        row_cpick={"mapping": 7.0})


def test_row_top_functions_are_pure_over_geometry():
    g = _geometry()
    assert query.map_top(g, 0) == 100.0
    assert query.map_top(g, 2) == 100.0 + 2 * ROW_H
    assert query.proj_top(g, 1) == 200.0 + ROW_H
    assert query.canon_top(g, 0) == 300.0
    assert query.vec_top(g, 3) == 400.0 + 3 * ROW_H
    assert query.ss_vec_top(g, 1) == 500.0 + ROW_H
    assert query.ss_map_top(g, 1) == 600.0 + ROW_H
    assert query.ss_proj_top(g, 2) == 700.0 + 2 * ROW_H


def test_frame_and_band_y_functions_are_pure_over_geometry():
    g = _geometry()
    row = g.rows["mapping"]
    assert query.cpick_band_y(g, "mapping") == row.y + row.h + row.frame
    assert query.ptext_band_y(g, "mapping") == (
        row.y + row.h + row.frame + g.row_cpick["mapping"] + row.sym + row.cap + row.units)
    assert query.frame_top_y(g, "mapping") == row.y - FRAME_H - FRAME_GAP
    assert query.frame_brace_y(g, "mapping") == row.y + row.h + FRAME_GAP
