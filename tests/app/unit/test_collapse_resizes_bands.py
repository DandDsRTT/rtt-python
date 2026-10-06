from rtt.app import service, settings, spreadsheet
from rtt.app import spreadsheet_geometry as sg
from rtt.app.spreadsheet_emit_model import build_context


def _builder(collapsed=frozenset(), tuning_scheme=None, **overrides):
    s = {**settings.defaults(), **overrides}
    b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, collapsed=set(collapsed),
                                 tuning_scheme=tuning_scheme)
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


    def test_a_folded_mapping_tile_releases_the_et_picker_and_drag_handle_gutters(self):
        for overrides in ({"presets": True}, {"drag_to_combine": True}):
            opened = _builder(**overrides).geometry.column_width["primes"]
            for collapsed in ({"row:mapping"}, {"tile:mapping:primes"}):
                assert _builder(collapsed, **overrides).geometry.column_width["primes"] < opened, (overrides, collapsed)


    def test_folding_every_row_labeled_in_a_column_releases_its_label_gutters(self):
        for column_key, overrides in (("primes", {"header_symbols": True}),
                                      ("canonical_generators", {"header_symbols": True, "form_tiles": True})):
            opened = _builder(**overrides).geometry.column_width[column_key]
            for collapsed in ({"row:mapping"}, {f"tile:mapping:{column_key}"}):
                assert _builder(collapsed, **overrides).geometry.column_width[column_key] < opened, (column_key, collapsed)


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

    def test_a_row_whose_every_tile_is_folded_reserves_no_symbol_name_units_or_chart_room(self):
        opened = _builder(charts=True, tile_units=True).geometry.rows["damage"]
        assert opened.symbol and opened.text and opened.units and opened.chart_top is not None
        for collapsed in ({"column:targets"}, {"tile:damage:targets"}):
            band = _builder(collapsed, charts=True, tile_units=True).geometry.rows["damage"]
            assert (band.symbol, band.text, band.units, band.chart_top) == (0, 0, 0, None), collapsed

    def test_plain_text_for_a_column_off_the_grid_holds_no_plain_text_band_open(self):
        opened = _builder(plain_text_values=True).geometry
        assert ("just", "canonical_generators") in opened.plain_text_strings and "canonical_generators" not in opened.column_x
        folded = _builder({f"column:{c}" for c in opened.column_x}, plain_text_values=True)
        assert folded.geometry.rows["just"].plain_text == 0

    def test_the_superspace_prescaling_panel_folds_with_its_own_superspace_primes_tile(self):
        def panel_shown(collapsed):
            s = {**settings.defaults(), "nonstandard_domain": True, "projection": True, "weighting": True, "alt_complexity": True}
            b = spreadsheet._GridBuilder(service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5)), s,
                                         collapsed=set(collapsed), tuning_scheme="TILT minimax-S")
            b.layout()
            assert b.resolved.flags.superspace
            return b.geometry.prescaling_panel_control
        assert panel_shown(()) and panel_shown({"column:primes"}) and panel_shown({"tile:prescaling:primes"})
        assert not panel_shown({"tile:prescaling:superspace_primes"})
        assert not panel_shown({"column:superspace_primes"})

    def test_the_prescaling_and_complexity_panels_fold_with_their_rows_and_tiles(self):
        def controls(collapsed):
            g = _builder(collapsed, "TILT minimax-S", weighting=True, alt_complexity=True).geometry
            return g.prescaling_panel_control, g.complexity_panel_control
        assert controls(()) == (True, True)
        assert controls({"row:prescaling", "row:complexity"}) == (False, False)
        assert controls({"tile:prescaling:primes", "tile:complexity:targets"}) == (False, False)
        assert controls({"column:primes", "column:targets"}) == (False, False)
