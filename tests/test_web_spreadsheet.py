from rtt.web import service, settings, spreadsheet


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


def _with(**overrides):
    s = settings.defaults()
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)


def test_rows_columns_and_cells_are_present():
    ids = {c.id for c in _layout().cells}
    assert {"header:gens", "header:primes"} <= ids  # column headers
    assert {"label:quantities", "label:mapping"} <= ids  # row labels
    assert {"prime:0", "prime:1", "prime:2"} <= ids  # the domain primes
    assert {"gen:0", "gen:1"} <= ids  # generator ratios
    assert {"cell:mapping:0:0", "cell:mapping:1:2"} <= ids  # the mapping matrix
    assert {"minus", "plus"} <= ids  # domain controls


def test_generator_ratios_are_shown_beside_the_mapping_rows():
    cells = {c.id: c for c in _layout().cells}
    assert cells["gen:0"].text == "2/1"
    assert cells["gen:1"].text == "3/2"
    # aligned vertically with the mapping rows they label
    assert cells["gen:0"].y == cells["cell:mapping:0:0"].y
    assert cells["gen:1"].y == cells["cell:mapping:1:0"].y


def test_primes_sit_above_the_mapping_columns():
    cells = {c.id: c for c in _layout().cells}
    for p in range(3):
        assert cells[f"prime:{p}"].x == cells[f"cell:mapping:0:{p}"].x  # same column
    assert cells["prime:0"].y < cells["cell:mapping:0:0"].y  # quantities row above mapping


def test_target_intervals_column_with_mapped_list():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:targets"].text == "target-intervals"
    assert cells["target:0"].text == "2/1" and cells["target:2"].text == "5/4"
    # the mapped target-interval list (M . target monzo) for [[1,1,0],[0,1,4]]
    assert cells["cell:mapped:0:0"].text == "1"
    assert cells["cell:mapped:1:2"].text == "4"  # 5/4 -> 4 generators of the fifth


def test_tuning_rows_over_primes_and_targets():
    cells = {c.id: c for c in _layout().cells}
    assert cells["label:tuning"].text == "tuning"
    assert cells["label:just"].text == "just tuning"
    assert cells["label:damage"].text == "damage"
    assert {"tuning:prime:0", "tuning:target:0", "just:prime:0", "retune:target:0", "damage:target:0"} <= set(cells)
    assert cells["just:prime:0"].text == "1200.00"  # just octave is pure
    # tuning rows sit on the same shared prime columns as the mapping
    assert cells["tuning:prime:2"].x == cells["cell:mapping:0:2"].x


def test_shared_axes_and_branching():
    lay = _layout()
    ids = {ln.id for ln in lay.lines}
    assert {"v:prime:0", "v:prime:1", "v:prime:2"} <= ids  # per-prime axes
    assert {"v:target:0", "v:target:1", "v:target:2", "v:target:3"} <= ids
    assert {"h:gen:0", "h:gen:1", "h:tuning", "h:just", "h:retune", "h:damage"} <= ids
    # each column header branches: a trunk down to a bus that fans into the verticals
    assert {"trunk:primes", "trunk:targets", "trunk:gens", "bus:primes", "bus:targets"} <= ids
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    assert by_id["bus:primes"].pos < cells["prime:0"].y  # fan-out is ABOVE quantities
    assert by_id["v:prime:0"].start == by_id["bus:primes"].pos  # verticals start at the fan-out


def test_axis_ids_are_stable_across_expand():
    before = {ln.id for ln in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4)))).lines}
    expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
    after = {ln.id for ln in spreadsheet.build(expanded).lines}
    assert before <= after  # existing prime/generator axes survive by id
    assert "v:prime:3" in after and "v:prime:3" not in before  # the added prime


def test_tuning_boxes_off_hides_the_tuning_rows():
    cells = {c.id for c in _with(tuning_boxes=False).cells}
    assert not any(c.split(":")[0] in {"tuning", "just", "retune", "damage"} for c in cells)
    assert {"label:tuning", "label:just", "label:retune", "label:damage"}.isdisjoint(cells)


def test_temperament_boxes_off_hides_mapping_and_lifts_tuning():
    off = {c.id: c for c in _with(temperament_boxes=False).cells}
    on = {c.id: c for c in _with().cells}
    assert "label:mapping" not in off
    assert not any(c.startswith(("cell:mapping:", "cell:mapped:", "gen:")) for c in off)
    assert off["tuning:prime:0"].y < on["tuning:prime:0"].y  # tuning rises into the freed space


def test_each_collapsible_row_has_a_toggle_but_quantities_does_not():
    cells = {c.id: c for c in _layout().cells}
    for key in ("mapping", "tuning", "just", "retune", "damage"):
        assert f"toggle:row:{key}" in cells  # the [x]/expand control
    assert "toggle:row:quantities" not in cells  # the spine row is not collapsible
    assert cells["toggle:row:tuning"].x < cells["tuning:prime:0"].x  # sits left of the content


def test_a_collapsed_rows_toggle_still_renders_so_it_can_reexpand():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
    assert "toggle:row:tuning" in cells  # the affordance survives collapse


def test_collapsing_a_row_hides_its_content_but_keeps_the_label():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    full = {c.id: c for c in spreadsheet.build(base).cells}
    coll = {c.id: c for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
    assert not any(c.startswith("tuning:") for c in coll)  # the tuning content is gone
    assert "label:tuning" in coll  # ...but its label remains as a re-expandable strip
    assert coll["label:tuning"].h < full["label:tuning"].h  # shrunk to a thin strip
    assert coll["label:just"].y < full["label:just"].y  # rows below lift into the freed space


def _in_targets(cid):
    return (cid.startswith(("target:", "cell:mapped:", "damage:target:"))
            or cid.startswith(("tuning:target:", "just:target:", "retune:target:")))


def test_collapsing_the_targets_column_hides_its_cells_across_every_row():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    full = spreadsheet.build(base)
    coll = spreadsheet.build(base, collapsed={"col:targets"})
    cids = {c.id for c in coll.cells}
    assert not any(_in_targets(c) for c in cids)  # gone from quantities, mapped, and every tuning row
    assert "header:targets" in cids  # ...but the header survives as a strip
    assert "toggle:col:targets" in cids  # with a re-expand toggle
    assert coll.width < full.width  # and the board narrows


def test_collapsing_the_domain_primes_column_hides_the_mapping_matrix():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cids = {c.id for c in spreadsheet.build(base, collapsed={"col:primes"}).cells}
    assert not any(c.startswith(("prime:", "cell:mapping:")) for c in cids)
    assert not any(c.startswith(("tuning:prime:", "just:prime:", "retune:prime:")) for c in cids)
    assert "header:primes" in cids  # header strip stays
    assert "cell:mapped:0:0" in cids  # the target columns are unaffected


def test_names_off_hides_labels_and_headers_and_collapses_their_space():
    off = {c.id: c for c in _with(names=False).cells}
    on = {c.id: c for c in _with().cells}
    assert not any(c.startswith(("label:", "header:")) for c in off)
    assert off["prime:0"].x < on["prime:0"].x  # the label gutter collapses, content shifts left
    assert off["prime:0"].y < on["prime:0"].y  # the header band collapses, content rises
