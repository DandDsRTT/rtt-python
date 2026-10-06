from rtt.app import service, settings, spreadsheet
from rtt.app import spreadsheet_geometry as sg
from rtt.app.spreadsheet_emit_model import build_context


def _builder(collapsed=frozenset(), **overrides):
    s = {**settings.defaults(), **overrides}
    b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, collapsed=set(collapsed))
    b.layout()
    return b


class TestColumnFloorsIgnoreFoldedTiles:
    def test_a_folded_rows_symbol_no_longer_floors_its_column(self):
        b = _builder()
        opened = sg.symbol_floor(b.geometry, b.resolved, frozenset(), "targets")
        assert sg.symbol_floor(b.geometry, b.resolved, frozenset({"row:retune"}), "targets") < opened
        assert sg.symbol_floor(b.geometry, b.resolved, frozenset({"tile:retune:targets"}), "targets") < opened

    def test_a_folded_counts_tile_no_longer_floors_its_column(self):
        b = _builder()
        assert sg.count_floor(b.resolved, frozenset(), "targets") > 0
        assert sg.count_floor(b.resolved, frozenset({"row:counts"}), "targets") == 0
        assert sg.count_floor(b.resolved, frozenset({"tile:counts:targets"}), "targets") == 0

    def test_a_folded_rows_preset_label_no_longer_floors_its_column(self):
        b = _builder(presets=True)
        context = build_context(b)
        opened = sg.control_floor(b.resolved, context, frozenset(), "targets")
        assert sg.control_floor(b.resolved, context, frozenset({"row:vectors"}), "targets") < opened
        assert sg.control_floor(b.resolved, context, frozenset({"tile:vectors:targets"}), "targets") < opened


class TestRowBandsIgnoreFoldedTiles:
    def test_collapsing_a_column_never_heightens_a_row(self):
        opened = _builder(presets=True, projection=True).geometry.rows
        for column_key in _builder(presets=True, projection=True).geometry.column_x:
            folded = _builder({f"column:{column_key}"}, presets=True, projection=True)
            for row_key, band in folded.geometry.rows.items():
                assert band.tile_height <= opened[row_key].tile_height, (column_key, row_key)

    def test_a_rows_plain_text_band_closes_when_its_only_plain_text_tile_folds(self):
        assert _builder(plain_text_values=True).geometry.rows["damage"].plain_text > 0
        for collapsed in ({"column:targets"}, {"tile:damage:targets"}):
            assert _builder(collapsed, plain_text_values=True).geometry.rows["damage"].plain_text == 0, collapsed
