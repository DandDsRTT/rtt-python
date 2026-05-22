from rtt.web import layout


def _meantone():
    return layout.build_layout(3, 2, 1, (2, 3, 5))


def test_lines_are_first_class_one_per_axis():
    lines = _meantone().lines
    vids = {ln.id for ln in lines if ln.orientation == "v"}
    hids = {ln.id for ln in lines if ln.orientation == "h"}
    assert vids == {"v:prime:0", "v:prime:1", "v:prime:2", "v:comma:0"}
    assert hids == {"h:header", "h:prime:0", "h:prime:1", "h:prime:2", "h:gen:0", "h:gen:1"}


def test_cells_have_stable_semantic_ids():
    ids = {c.id for c in _meantone().cells}
    assert {"cell:prime:0", "cell:prime:2"} <= ids
    assert {"cell:mapping:0:0", "cell:mapping:1:2"} <= ids
    assert {"cell:comma:0:0", "cell:comma:0:2"} <= ids
    assert {"minus", "plus", "label:mapping", "label:comma basis"} <= ids


def test_blocks_are_the_four_panels():
    assert {b.id for b in _meantone().blocks} == {
        "block:controls", "block:header", "block:mapping", "block:comma"
    }


def test_axes_are_arranged_as_the_staircase():
    lines = _meantone().lines
    prime_x = sorted(ln.pos for ln in lines if ln.id.startswith("v:prime:"))
    comma_x = next(ln.pos for ln in lines if ln.id == "v:comma:0")
    header_y = next(ln.pos for ln in lines if ln.id == "h:header")
    coeff_y = [ln.pos for ln in lines if ln.id.startswith("h:prime:")]
    gen_y = [ln.pos for ln in lines if ln.id.startswith("h:gen:")]
    assert prime_x == sorted(prime_x) and len(prime_x) == 3  # prime columns left-to-right
    assert comma_x > max(prime_x)  # comma basis to the right
    assert header_y < min(coeff_y)  # header above the shared-axis rows
    assert max(coeff_y) < min(gen_y)  # mapping below them


def test_axis_ids_are_stable_across_expand():
    # the animation foundation: expanding the domain keeps existing axes' ids and
    # only adds the new prime/generator, so the renderer can animate rather than rebuild.
    before = {ln.id for ln in layout.build_layout(3, 2, 1, (2, 3, 5)).lines}
    after = {ln.id for ln in layout.build_layout(4, 3, 1, (2, 3, 5, 7)).lines}
    assert before <= after  # every prior axis survives by id
    assert "v:prime:3" in after and "h:gen:2" in after  # the added prime / generator
    assert "v:prime:3" not in before
