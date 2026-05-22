from rtt.web import service, spreadsheet


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


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


def test_shared_axes_are_first_class_lines():
    lay = _layout()
    vids = {ln.id for ln in lay.lines if ln.orientation == "v"}
    hids = {ln.id for ln in lay.lines if ln.orientation == "h"}
    assert vids == {"v:prime:0", "v:prime:1", "v:prime:2"}
    assert hids == {"h:gen:0", "h:gen:1"}


def test_axis_ids_are_stable_across_expand():
    before = {ln.id for ln in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4)))).lines}
    expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
    after = {ln.id for ln in spreadsheet.build(expanded).lines}
    assert before <= after  # existing prime/generator axes survive by id
    assert "v:prime:3" in after and "v:prime:3" not in before  # the added prime
