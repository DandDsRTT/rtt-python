from types import SimpleNamespace

from rtt.app import spreadsheet_geometry_query as query
from rtt.app.spreadsheet_constants import (
    BRACKET_W,
    COLUMN_WIDTH,
    FRAME_GAP,
    FRAME_H,
    INTERVAL_COL_GAP,
    ROW_H,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_models import RowBand


def _row(y, height=10.0, frame=2.0, symbol=3.0, caption=4.0, units=5.0, comma_picker=0.0):
    return RowBand(y=y, height=height, label="", collapsible=True, tile_h=0.0, tile_top=0.0,
                   frame=frame, symbol=symbol, caption=caption, units=units, plain_text=0.0, preset=0.0,
                   scheme_button=0.0, num_subrows=1, comma_picker=comma_picker)


def _geometry():
    return SimpleNamespace(
        rows={"mapping": _row(100.0, comma_picker=7.0), "projection": _row(200.0), "canon": _row(300.0),
              "vectors": _row(400.0), "superspace_vectors": _row(500.0), "superspace_mapping": _row(600.0),
              "superspace_projection": _row(700.0)})


class TestGeometryQuery:
    def test_row_top_functions_are_pure_over_geometry(self):
        g = _geometry()
        assert query.map_top(g, 0) == 100.0
        assert query.map_top(g, 2) == 100.0 + 2 * ROW_H
        assert query.projection_top(g, 1) == 200.0 + ROW_H
        assert query.canon_top(g, 0) == 300.0
        assert query.vector_top(g, 3) == 400.0 + 3 * ROW_H
        assert query.superspace_vector_top(g, 1) == 500.0 + ROW_H
        assert query.superspace_map_top(g, 1) == 600.0 + ROW_H
        assert query.superspace_projection_top(g, 2) == 700.0 + 2 * ROW_H

    def test_frame_and_band_y_functions_are_pure_over_geometry(self):
        g = _geometry()
        row = g.rows["mapping"]
        assert query.comma_picker_band_y(g, "mapping") == row.y + row.height + row.frame
        assert query.plain_text_band_y(g, "mapping") == (
            row.y + row.height + row.frame + row.comma_picker + row.symbol + row.caption + row.units)
        assert query.frame_top_y(g, "mapping") == row.y - FRAME_H - FRAME_GAP
        assert query.frame_brace_y(g, "mapping") == row.y + row.height + FRAME_GAP

    def test_gutter_and_coordinate_functions_are_pure_over_geometry(self):
        g = SimpleNamespace(
            primes_x=10.0, targets_x=20.0, content_x={"gens": 5.0},
            matlabel_primes_w=2.0, matlabel_superspace_primes_w=3.0, matlabel_other_w={"gens": 1.0},
            row_handle_w=4.0, etpick_w=0, group_left={"targets": (100.0, 200.0)})
        assert query.matlabel_gutter_w(g, "primes") == 2.0
        assert query.matlabel_gutter_w(g, "superspace_primes") == 3.0
        assert query.matlabel_gutter_w(g, "gens") == 1.0
        assert query.handle_gutter_w(g, "primes") == 4.0
        assert query.handle_gutter_w(g, "gens") == 0
        assert query.etpick_left_pad(g, "primes") == 0
        assert query.target_left(g, 1) == 20.0 + BRACKET_W + COLUMN_WIDTH + INTERVAL_COL_GAP
        assert query.prime_left(g, 0) == 10.0 + query.outer_gutter_w(g, "primes") + BRACKET_W
        assert query.sub_axis_x(g, "targets", 1) == 200.0 + COLUMN_WIDTH / 2

    def test_resolved_dependent_query_functions_are_pure(self):
        g = SimpleNamespace(commas_x=90.0)
        r = SimpleNamespace(unchanged=SimpleNamespace(shown=True, empty_comma_w=5.0),
                            dims=SimpleNamespace(comma_count=2, comma_count_shown=3))
        assert query.comma_value_pos(r, 1) == 1
        assert query.comma_value_pos(r, 2) == 2 + (3 - 2)
        assert query.comma_left(g, r, 0) == 90.0 + BRACKET_W + 5.0
        assert query.comma_left(g, r, 3) == 90.0 + BRACKET_W + 5.0 + 3 * COLUMN_WIDTH + V_SPLIT_GAP

    def test_openness_predicates_are_pure_over_geometry_and_collapsed(self):
        g = SimpleNamespace(column_x={"primes": 0.0, "targets": 0.0}, rows={"mapping": None},
                            declared_tiles={("mapping", "primes")})
        collapsed = frozenset({"col:targets", "row:nope", "tile:mapping:primes"})
        assert query.column_open(g, collapsed, "primes") is True
        assert query.column_open(g, collapsed, "targets") is False
        assert query.column_open(g, collapsed, "absent") is False
        assert query.row_open(g, collapsed, "mapping") is True
        assert query.tile_open(g, collapsed, "mapping", "primes") is False
        assert query.tile_open(g, frozenset(), "mapping", "primes") is True

    def test_column_identity_queries_are_pure_over_resolved(self):
        r = SimpleNamespace(
            dims=SimpleNamespace(comma_count=2, target_count=3, held_count=0, interest_count=0),
            column_ids={"targets": [(7, "a"), (8, "b"), (9, "c")], "commas": [(0, "x"), (1, "y")]},
            scalars=SimpleNamespace(comma_draft=False),
            targets=SimpleNamespace(pending=None), held=SimpleNamespace(pending=None),
            interest=SimpleNamespace(pending=None))
        assert query.column_token(r, "targets", 1) == 8
        assert query.column_token(r, "commas", 3) == "u1"
        assert query.pending_draft_idx(r, "targets") == (None, 3)
        assert query.pending_draft_idx(r, "absent") is None

    def test_unit_queries_are_pure_over_resolved(self):
        r = SimpleNamespace(
            flags=SimpleNamespace(cell_units=True),
            scalars=SimpleNamespace(weight_unit="(W)", damage_unit="¢(W)", complexity_unit="(X)"),
            labels=SimpleNamespace(domain_label="p"))
        assert query.tile_unit(r, "weight", "targets") == "(W)"
        assert query.tile_unit(r, "damage", "targets") == "¢(W)"
        assert query.tile_unit(r, "nope", "nope") == ""
        off = SimpleNamespace(flags=SimpleNamespace(cell_units=False))
        assert query.cell_unit(off, "weight", "targets") == ""
