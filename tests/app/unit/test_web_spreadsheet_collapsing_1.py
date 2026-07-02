from rtt.app import service, settings, spreadsheet, spreadsheet_constants
from _spreadsheet_support import _memoized_build, _layout, _in_targets


class TestCollapsingRowsAndColumns:
    def test_every_row_including_quantities_has_a_fold_toggle(self):
        cells = {c.id: c for c in _layout().cells}
        for key in ("quantities", "vectors", "mapping", "tuning", "just", "retune", "damage"):
            assert f"toggle:row:{key}" in cells
        assert cells["toggle:row:tuning"].x < cells["tuning:prime:0"].x

    def test_a_collapsed_rows_toggle_still_renders_so_it_can_reexpand(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
        assert "toggle:row:tuning" in cells

    def test_collapsing_a_row_hides_its_content_but_keeps_the_label(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = {c.id: c for c in spreadsheet.build(base).cells}
        coll = {c.id: c for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
        assert not any(c.startswith("tuning:") for c in coll)
        assert "label:tuning" in coll
        assert coll["label:tuning"].height < full["label:tuning"].height
        assert coll["label:just"].y < full["label:just"].y

    def test_collapsing_the_targets_column_hides_its_cells_across_every_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = spreadsheet.build(base)
        coll = spreadsheet.build(base, collapsed={"column:targets"})
        cids = {c.id for c in coll.cells}
        assert not any(_in_targets(c) for c in cids)
        assert "header:targets" in cids
        assert "toggle:column:targets" in cids
        assert coll.width < full.width

    def test_collapsing_the_domain_primes_column_hides_the_mapping_matrix(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cids = {c.id for c in spreadsheet.build(base, collapsed={"column:primes"}).cells}
        assert not any(c.startswith(("prime:", "cell:mapping:")) for c in cids)
        assert not any(
            c.startswith(("tuning:prime:", "just:prime:", "retune:prime:")) for c in cids
        )
        assert "header:primes" in cids
        assert "cell:mapped:0:0" in cids

    def test_collapsed_column_keeps_its_title_at_a_width_that_fits_it(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        coll = {c.id: c for c in spreadsheet.build(base, collapsed={"column:targets"}).cells}[
            "header:targets"
        ]
        full = {c.id: c for c in spreadsheet.build(base).cells}["header:targets"]
        assert coll.text == "target\nintervals", "the title stays put (not blanked, not rotated)"
        assert spreadsheet_constants.STRIP < coll.width < full.width

    def test_collapsed_column_gridline_stays_centred_in_its_fold_node(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        for key in ("commas", "targets"):
            layout = spreadsheet.build(base, collapsed={f"column:{key}"})
            trunk = {line.id: line for line in layout.lines}[f"trunk:{key}"]
            cells = {c.id: c for c in layout.cells}
            toggle, header = cells[f"toggle:column:{key}"], cells[f"header:{key}"]
            assert abs(trunk.position - (toggle.x + toggle.width / 2)) < 0.51, key
            assert abs(trunk.position - (header.x + header.width / 2)) < 0.51, key

    def test_a_collapsed_multiline_title_strip_fits_its_widest_line(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        interest = {
            c.id: c
            for c in spreadsheet.build(
                base, collapsed={"column:interest"}, interest=[(0, 0, 0)] * 5
            ).cells
        }["header:interest"]
        assert interest.text == "other intervals\nof interest"
        assert interest.width == len("other intervals") * 8 + 10, (
            "the widest line, not all 27 chars"
        )
        assert interest.width < len("other intervals of interest") * 8 + 10

    def test_collapsing_a_spine_column_never_widens_it(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["app_units"] = True
        s["tile_units"] = True
        opened = {c.id: c for c in spreadsheet.build(base, s).cells}
        collapsed = {
            c.id: c
            for c in spreadsheet.build(
                base, s, collapsed={"column:quantities", "column:units"}
            ).cells
        }
        for key in ("quantities", "units"):
            assert collapsed[f"header:{key}"].width <= opened[f"header:{key}"].width
        assert collapsed["header:units"].width == spreadsheet_constants.COLUMN_WIDTH

    def test_a_rows_nested_control_grows_every_tile_in_that_row_uniformly(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ranges = settings.defaults()
        ranges["tuning_ranges"] = True
        on = {b.id: b for b in spreadsheet.build(base, ranges).blocks}
        generators = on["block:tuning:generators"].height
        for sib in ("block:tuning:primes", "block:tuning:commas", "block:tuning:targets"):
            assert on[sib].height == generators, sib
        off = {b.id: b for b in spreadsheet.build(base).blocks}
        assert generators > off["block:tuning:primes"].height

        alt = settings.defaults()
        alt["weighting"] = True
        alt["alt_complexity"] = True
        aon = {b.id: b for b in spreadsheet.build(base, alt, tuning_scheme="TILT minimax-S").blocks}
        presc = aon["block:prescaling:primes"].height
        for sib in ("block:prescaling:commas", "block:prescaling:targets"):
            assert aon[sib].height == presc, sib
        comp = aon["block:complexity:targets"].height
        for sib in ("block:complexity:primes", "block:complexity:commas"):
            assert aon[sib].height == comp, sib

    def test_collapsing_a_column_does_not_shrink_its_rows_caption_band(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        without_generators = {
            b.id: b for b in spreadsheet.build(base, s, collapsed={"column:commas"}).blocks
        }
        with_generators = {
            b.id: b
            for b in spreadsheet.build(
                base, s, collapsed={"column:commas", "column:generators"}
            ).blocks
        }
        for sib in ("block:tuning:primes", "block:tuning:targets"):
            assert with_generators[sib].height == without_generators[sib].height, (
                f"{sib} shrank when the generators column collapsed"
            )

    def test_collapsing_a_row_folds_its_panel_away_and_leaves_a_gridline(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(base, collapsed={"row:tuning"})
        blocks = {b.id: b for b in layout.blocks}
        lines = {line.id for line in layout.lines}
        assert "block:tuning:primes" in blocks, "the panel persists so the renderer can animate it"
        assert blocks["block:tuning:primes"].height == 0
        assert "h:tuning" in lines

    def test_collapsing_a_column_folds_its_panels_away_and_converges_the_lines(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(base, collapsed={"column:primes"})
        blocks = {b.id: b for b in layout.blocks}
        by_id = {line.id: line for line in layout.lines}
        assert blocks["block:mapping"].width == 0
        assert (
            by_id["v:prime:0"].position
            == by_id["v:prime:1"].position
            == by_id["v:prime:2"].position
        ), "the per-prime verticals converge onto one x (so they read as a single line)"
        assert by_id["bus:primes:top"].length == 0

    def test_a_collapsed_bands_gridline_is_dotted_while_open_bands_stay_solid(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        layout = spreadsheet.build(base, collapsed={"row:tuning", "column:primes"})
        by_id = {line.id: line for line in layout.lines}
        assert by_id["h:tuning"].dotted
        assert by_id["trunk:primes"].dotted
        assert by_id["v:prime:0"].dotted
        assert not by_id["h:quantities"].dotted
        assert not by_id["trunk:generators"].dotted

    def test_a_collapsed_fanned_mapping_row_dots_its_converged_rules(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        by_id = {line.id: line for line in spreadsheet.build(base, collapsed={"row:mapping"}).lines}
        assert by_id["trunk:mapping"].dotted and by_id["h:mapping:0"].dotted
