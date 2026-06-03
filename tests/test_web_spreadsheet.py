from rtt.web import service, settings, spreadsheet
from rtt.web.editor import Editor


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


def _with(scheme=None, **overrides):
    # scheme=None uses build's (target-based, all-interval-OFF) default; pass an all-interval
    # name like "minimax-S" to exercise all-interval rendering (dual(q), the primes target column)
    s = settings.defaults()
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, tuning_scheme=scheme)


def _with_interest(interest, collapsed=None):
    return spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), collapsed=collapsed, interest=interest
    )


def test_rows_columns_and_cells_are_present():
    ids = {c.id for c in _layout().cells}
    assert {"header:gens", "header:primes"} <= ids  # column headers
    assert {"label:quantities", "label:mapping"} <= ids  # row labels
    assert {"prime:0", "prime:1", "prime:2"} <= ids  # the domain primes
    assert {"gen:0", "gen:1"} <= ids  # generator ratios
    assert {"cell:mapping:0:0", "cell:mapping:1:2"} <= ids  # the mapping matrix
    assert {"minus", "plus"} <= ids  # domain controls


def test_freeze_boundaries_sit_at_the_title_band_edges():
    # the layout publishes where the frozen title bands end: freeze_y is the bottom
    # of the column-title + column-toggle band, freeze_x the right of the row-title +
    # row-toggle band. The renderer pins everything within those bands and scrolls the
    # rest under them, so these must land exactly on the band edges.
    lay = _layout()
    # land on the ACTUAL band edges (the extent of the title/toggle cells), not a re-derived
    # production formula that would mirror any bug in it
    assert lay.freeze_y == max(c.y + c.h for c in lay.cells if c.kind in {"colheader", "coltoggle"})
    assert lay.freeze_x == max(c.x + c.w for c in lay.cells if c.kind in {"rowlabel", "rowtoggle"})
    # and every content cell clears both bands, so the bands precede the scrolling content
    titles = {"colheader", "coltoggle", "rowlabel", "rowtoggle", "alltoggle"}
    assert all(c.y >= lay.freeze_y and c.x >= lay.freeze_x for c in lay.cells if c.kind not in titles)


def test_layout_reports_the_rightmost_title_overhang():
    # column titles render unwrapped and centred on their gridline, so one wider than its
    # (content-hugging) column overhangs it. The last column's title spills past the grid's
    # right edge: the empty "other intervals of interest" column is narrow, but its long title
    # reaches well beyond total_w. The layout publishes that overhang so the renderer can widen
    # the grey pane to SHOW the title rather than clip its trailing "…ls" (the clip the
    # hug-to-content panes introduced). Titles never overhang the bottom, so only the right is
    # reported.
    lay = _layout()
    rightmost = max(c.x + c.w / 2 + spreadsheet._title_w(c.text) / 2
                    for c in lay.cells if c.kind == "colheader")
    assert lay.right_overhang == rightmost - lay.width  # the interest title's reach past total_w
    assert lay.right_overhang > 0  # it really does overhang (else there'd be nothing to fix)


def test_no_title_overhang_reports_zero():
    # when the rightmost title fits within the grid (nothing spills past the footprint's right
    # edge), the layout reports no overhang and the pane carries only its plain margin — the
    # clamp keeps a fitting title from reporting a NEGATIVE overhang that would shrink the pane
    # below the grid. Hiding the long-titled interest column leaves "target intervals" last,
    # whose title sits well within total_w.
    lay = _with(interest=False)
    rightmost = max(c.x + c.w / 2 + spreadsheet._title_w(c.text) / 2
                    for c in lay.cells if c.kind == "colheader")
    assert rightmost < lay.width  # no title reaches past the grid's right edge
    assert lay.right_overhang == 0


def _assert_freeze_partition(lay):
    # the frozen bands partition the board: column titles + their toggles lie wholly
    # above freeze_y, row titles + their toggles wholly left of freeze_x, the master
    # toggle in the corner of both. Every other cell — and every grey tile / wash —
    # clears both bands, so the renderer's occlusion curtains never mask live content.
    top, left = {"colheader", "coltoggle"}, {"rowlabel", "rowtoggle"}
    for cb in lay.cells:
        if cb.kind in top:
            assert cb.y + cb.h <= lay.freeze_y
        elif cb.kind in left:
            assert cb.x + cb.w <= lay.freeze_x
        elif cb.kind == "alltoggle":
            assert cb.y + cb.h <= lay.freeze_y and cb.x + cb.w <= lay.freeze_x
        else:
            assert cb.x >= lay.freeze_x and cb.y >= lay.freeze_y
    for bl in lay.blocks:
        assert bl.x >= lay.freeze_x and bl.y >= lay.freeze_y


def test_freeze_bands_hold_exactly_the_titles_and_toggles():
    _assert_freeze_partition(_layout())


def test_freeze_bands_survive_collapsing_rows_and_columns():
    # collapsing folds rows/columns to a STRIP but keeps their title + toggle in the
    # band; the partition must still hold so the frozen panes stay correct when folded.
    collapsed = {"row:tuning", "row:mapping", "col:targets", "col:primes"}
    _assert_freeze_partition(spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), collapsed=collapsed))


def test_build_renders_a_nonstandard_domain_in_its_elements():
    # a loaded 2.3.13/5 temperament shows its (nonprime) elements in the grid, renames
    # the domain header, and reads its quantities over the basis — not the 2,3,5 the grid
    # would otherwise default to
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    cells = {c.id: c for c in spreadsheet.build(state).cells}
    assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "13/5"]
    assert cells["header:primes"].text == "basis\nelements"  # the guide's term for the columns
    assert cells["gen:1"].text == "15/13"  # the Barbados generator, read over the basis


def test_generator_ratios_also_head_the_generators_column_in_the_quantities_row():
    # the generators column gets the same quantities-row header treatment as the domain
    # primes: each generator's ratio heads its sub-column (horizontally), the dual of the
    # spine list that labels the mapping rows (gen:i). The mockup's "~2/1 ~2/3".
    cells = {c.id: c for c in _layout().cells}
    assert cells["qgen:0"].text == "2/1"
    assert cells["qgen:1"].text == "3/2"
    # in the generators column (aligned with the genmap cells), on the quantities row
    assert cells["qgen:0"].x == cells["tuning:gen:0"].x
    assert cells["qgen:1"].x == cells["tuning:gen:1"].x
    assert cells["qgen:0"].y == cells["prime:0"].y  # the quantities row


def test_standard_domain_header_still_reads_domain_primes():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:primes"].text == "domain\nprimes"
    assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "5"]


def test_generator_ratios_are_listed_in_the_quantities_column():
    cells = {c.id: c for c in _layout().cells}
    assert cells["gen:0"].text == "2/1"
    assert cells["gen:1"].text == "3/2"
    # listed vertically in the quantities spine column (left of the generators
    # column), aligned with the mapping rows they label
    assert cells["gen:0"].x == cells["header:quantities"].x
    assert cells["gen:0"].x < cells["header:gens"].x
    assert cells["gen:0"].y == cells["cell:mapping:0:0"].y
    assert cells["gen:1"].y == cells["cell:mapping:1:0"].y


def test_mapping_over_generators_identity_is_deferred_to_identity_objects():
    # M over its own generators is the identity — an "identity object" the grid
    # won't show until the identity_objects setting is built. Until then the
    # generators column carries no tile at the mapping row (no cells, brackets,
    # framing marks or fold toggle).
    cells = {c.id for c in _layout().cells}
    assert not any(c.startswith(("cell:selfmap", "bracket:selfmap")) for c in cells)
    assert {"ebktop:gens", "ebkbrace:gens", "toggle:tile:mapping:gens"}.isdisjoint(cells)


def test_primes_sit_above_the_mapping_columns():
    cells = {c.id: c for c in _layout().cells}
    for p in range(3):
        assert cells[f"prime:{p}"].x == cells[f"cell:mapping:0:{p}"].x  # same column
    assert cells["prime:0"].y < cells["cell:mapping:0:0"].y  # quantities row above mapping


def test_minus_is_revealed_at_the_last_primes_branch_point_clear_of_its_input():
    # only the highest prime can be dropped (service.shrink_domain trims the last), so its
    # hover-minus rides that prime's branch point — the top-bus split, up at the fan-out,
    # centred on the sub-axis — never over the editable mapping cell below (which would
    # block editing). Its zone drops from the branch point over the header as the hover target.
    lay = _layout()
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    minus = cells["minus"]
    assert abs((minus.x + minus.w / 2) - by_id["v:prime:2"].pos) < 0.51  # centred on the last sub-axis
    assert minus.y == by_id["bus:primes:top"].pos  # the zone drops from the top bus (branch point)
    assert minus.y + minus.h <= cells["cell:mapping:0:2"].y  # ...and clear of the editable input below


def test_minus_tracks_the_new_last_prime_after_a_shrink():
    shrunk = service.shrink_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # d=2
    lay = spreadsheet.build(shrunk)
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    assert "prime:2" not in cells  # only primes 0 and 1 remain
    # the minus follows to the new last column's branch point
    assert abs((cells["minus"].x + cells["minus"].w / 2) - by_id["v:prime:1"].pos) < 0.51


def test_a_single_prime_domain_has_no_minus_but_keeps_plus():
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1,),))).cells}
    assert "minus" not in cells  # nothing is removable when d == 1
    assert {"plus", "prime:0"} <= cells  # ...but you can still expand


def test_quantities_row_pluses_ride_the_bus_stub_past_the_last_branch_point():
    # the domain/comma/interest + rides its column's fan stub — one COL_W past the last branch
    # point (the slot where the next element would branch), centred on the top bus — and the bus
    # stretches out to reach it. The horizontal echo of the interval-vectors basis +.
    opts = settings.defaults()
    opts["names"] = False
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), opts, interest=((-1, 1, 0),))
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    for plus_id, col, last_sub in (("plus", "primes", "v:prime:2"),
                                   ("comma_plus", "commas", "v:comma:0"),
                                   ("interest_plus", "interest", "v:interest:0")):
        plus, bus = cells[plus_id], by_id[f"bus:{col}:top"]
        stub = by_id[last_sub].pos + spreadsheet.COL_W  # one slot past the last sub-axis
        assert abs((plus.x + plus.w / 2) - stub) < 0.51     # the + centres on the stub
        assert abs((plus.y + plus.h / 2) - bus.pos) < 0.51  # ...up on the top bus
        assert abs((bus.start + bus.length) - stub) < 0.51  # and the bus reaches it


def test_generators_plus_and_minus_ride_the_generators_fan():
    # the generators ± rides the generators column's fan, like the domain ±: the + on the
    # stub one COL_W past the last generator's branch point (the bus stretched to reach it),
    # the hover − on that last branch point, up at the fan-out and clear of the cell below.
    lay = _layout()  # meantone, r = 2
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    plus, bus, last_sub = cells["gen_plus"], by_id["bus:gens:top"], by_id["v:gen:1"]
    stub = last_sub.pos + spreadsheet.COL_W
    assert abs((plus.x + plus.w / 2) - stub) < 0.51      # the + centres on the stub
    assert abs((plus.y + plus.h / 2) - bus.pos) < 0.51   # ...up on the top bus
    assert abs((bus.start + bus.length) - stub) < 0.51   # and the bus reaches it
    minus = cells["gen_minus"]
    assert abs((minus.x + minus.w / 2) - last_sub.pos) < 0.51  # − on the last generator's branch point
    assert minus.y == bus.pos                                  # the zone drops from the top bus
    assert minus.y + minus.h <= cells["tuning:gen:0"].y        # ...clear of the genmap cell below


def test_a_single_generator_temperament_has_no_gen_minus_but_keeps_gen_plus():
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}
    assert "gen_minus" not in cells  # nothing to remove at rank 1
    assert {"gen_plus", "qgen:0"} <= cells  # ...but you can still add a generator


def test_target_list_carries_a_per_entry_minus_and_a_plus():
    # the target interval list gets the same ± as the intervals of interest: a − over each
    # target (any one removable) and a + on the column stub to add one.
    lay = _layout()  # default TILT targets
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    k = len([c for c in cells if c.startswith("target:") and c.split(":")[1].isdigit()])
    assert k >= 2
    assert all(f"target_minus:{j}" in cells for j in range(k))  # a − per target
    # the + rides the stub one COL_W past the last target's branch point, bus stretched to reach it
    plus, bus, last_sub = cells["target_plus"], by_id["bus:targets:top"], by_id[f"v:target:{k - 1}"]
    stub = last_sub.pos + spreadsheet.COL_W
    assert abs((plus.x + plus.w / 2) - stub) < 0.51
    assert abs((bus.start + bus.length) - stub) < 0.51


def test_target_list_has_no_controls_in_all_interval():
    # all-interval auto-generates the target list (Tₚ = I), so it carries no ± to curate
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), tuning_scheme="minimax-S")
    cells = {c.id for c in lay.cells}
    assert "target_plus" not in cells
    assert not any(c.startswith("target_minus:") for c in cells)


def test_target_intervals_column_with_mapped_list():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:targets"].text == "target\nintervals"
    # each target maps through M ([[1,1,0],[0,1,4]]) into the mapped-list column below it
    assert cells["target:0"].text == "2/1"
    assert cells["cell:mapped:0:0"].text == "1" and cells["cell:mapped:1:0"].text == "0"  # 2/1 -> 1 octave
    assert cells["target:6"].text == "5/4"
    assert cells["cell:mapped:1:6"].text == "4"  # 5/4 -> 4 generators of the fifth


def test_target_columns_default_to_the_domains_tilt():
    cells = {c.id: c for c in _layout().cells}  # 5-limit meantone, domain 2.3.5
    texts = [cells[f"target:{j}"].text for j in range(8)]
    assert texts == ["2/1", "3/1", "3/2", "4/3", "5/2", "5/3", "5/4", "6/5"]  # the 6-TILT


def test_target_set_tracks_the_domain():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # domain 2.3.5

    def targets(state):
        return {c.text for c in spreadsheet.build(state).cells if c.id.startswith("target:")}

    three = targets(service.shrink_domain(base))  # drop prime 5 -> 2.3
    five = targets(base)  # 2.3.5
    seven = targets(service.expand_domain(base))  # add prime 7 -> 2.3.5.7
    assert three < five < seven  # the default target set shrinks/grows with the domain


def test_mapping_cells_form_a_square_touching_grid():
    cells = {c.id: c for c in _layout().cells}
    c00 = cells["cell:mapping:0:0"]
    # each cell is square, so the matrix reads as a grid of squares (mockup z_map2)
    assert c00.w == c00.h == spreadsheet.ROW_H
    # consecutive cells in a row/column abut exactly — shared borders, no gaps
    assert cells["cell:mapping:0:1"].x == c00.x + c00.w
    assert cells["cell:mapping:0:2"].x == c00.x + 2 * c00.w
    assert cells["cell:mapping:1:0"].y == c00.y + c00.h
    # the mapped target interval list sits on the same square columns
    m00 = cells["cell:mapped:0:0"]
    assert m00.w == m00.h == spreadsheet.ROW_H
    assert cells["cell:mapped:0:1"].x == m00.x + m00.w


def test_tuning_rows_over_primes_and_targets():
    cells = {c.id: c for c in _layout().cells}
    assert cells["label:tuning"].text == "tuning"
    assert cells["label:just"].text == "just tuning"
    assert cells["label:damage"].text == "damage"
    assert {"tuning:prime:0", "tuning:target:0", "just:prime:0", "retune:target:0", "damage:target:0"} <= set(cells)
    assert cells["just:prime:0"].text == "1200.000"  # just octave is pure
    # tuning rows sit on the same shared prime columns as the mapping
    assert cells["tuning:prime:2"].x == cells["cell:mapping:0:2"].x


def test_shared_axes_and_branching():
    lay = _layout()
    ids = {ln.id for ln in lay.lines}
    assert {"v:prime:0", "v:prime:1", "v:prime:2"} <= ids  # per-prime axes
    assert {"v:target:0", "v:target:1", "v:target:2", "v:target:3"} <= ids
    assert {"h:mapping:0", "h:mapping:1", "h:tuning", "h:just", "h:retune", "h:damage"} <= ids
    # each column fans out from a top bus and back in to a bottom bus + foot
    assert {"trunk:primes", "trunk:targets", "trunk:gens"} <= ids
    assert {"bus:primes:top", "bus:primes:bot", "foot:primes"} <= ids
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    assert by_id["bus:primes:top"].pos < cells["prime:0"].y  # top fan-out is ABOVE quantities
    assert by_id["v:prime:0"].start == by_id["bus:primes:top"].pos  # verticals start at the top bus
    assert by_id["bus:primes:bot"].pos > by_id["bus:primes:top"].pos  # ...and rejoin at the bottom
    # the per-generator mapping lines fan back in on the right to a foot
    assert {"vbar:mapping:left", "vbar:mapping:right", "foot:mapping"} <= ids


def test_convergence_buses_keep_solid_corners_and_the_top_bus_reaches_the_plus():
    # both buses fan from half a line-width before the first sub-line, so the near (fan-out)
    # corner stays solid at LINE_W. The BOTTOM bus rejoins half past the last sub-line (its far
    # corner solid too). The TOP bus instead stretches on past the last sub-line to the + stub —
    # the branching bar reaching the add-control. (At 1px the shortfall was invisible; at 2px the
    # far corner dropped a square.)
    lay = _layout()  # 2.3.5 -> primes fan to 3 columns
    by = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    half = spreadsheet.LINE_W / 2
    v0, vlast = by["v:prime:0"], by["v:prime:2"]
    assert by["bus:primes:top"].start == v0.pos - half  # both fan out from half before the first...
    assert by["bus:primes:bot"].start == v0.pos - half
    assert by["bus:primes:bot"].start + by["bus:primes:bot"].length == vlast.pos + half  # bot rejoins half past
    top, plus = by["bus:primes:top"], cells["plus"]
    assert top.start + top.length == plus.x + plus.w / 2  # the top bus reaches the + stub
    assert top.start + top.length > vlast.pos + half      # ...extending past the last sub-line


def test_mapping_rejoin_bars_span_the_full_generator_fan():
    # the RIGHT vertical bar closing the mapping rows reaches half a line-width past the outer
    # generator rows, like the column buses, so the far rejoin corner stays solid. The LEFT bar
    # shares that top but stretches further DOWN to the mapping-row + stub (the row mirror of the
    # basis +), so it only matches the fan at its top end (its reach to the + is tested separately).
    by = {ln.id: ln for ln in _layout().lines}  # rank-2 -> 2 generator rows
    half = spreadsheet.LINE_W / 2
    g0, glast = by["h:mapping:0"], by["h:mapping:1"]
    right = by["vbar:mapping:right"]
    assert right.start == g0.pos - half and right.start + right.length == glast.pos + half
    left = by["vbar:mapping:left"]
    assert left.start == g0.pos - half  # same top edge
    assert left.start + left.length > glast.pos + half  # ...but extends past the fan to the +


def test_adjacent_tiles_keep_a_twelve_px_minimum_gap():
    # the minimum whitespace between two grey tiles is GAP - 2*PAD; the design doubles it
    # from 6px to 12px so the (now 2px-thick) gridlines threading the gap keep their room
    blocks = {b.id: b for b in _layout().blocks}
    top, bot = blocks["block:tuning:targets"], blocks["block:just:targets"]
    assert (top.x, top.w) == (bot.x, bot.w)  # the same column, stacked vertically
    assert bot.y - (top.y + top.h) == 12  # the visible gap between the two tiles


def test_quantities_spine_row_has_a_horizontal_gridline():
    lay = _layout()
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    assert "h:quantities" in by_id  # the spine row gets a gridline like the tuning rows
    line, prime = by_id["h:quantities"], cells["prime:0"]
    assert abs(line.pos - (prime.y + prime.h / 2)) < 0.51  # centred on the quantities row
    assert line.start < prime.x  # runs in from the left, across the data columns
    assert line.start + line.length >= cells["target:3"].x


def test_axis_ids_are_stable_across_expand():
    before = {ln.id for ln in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4)))).lines}
    expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
    after = {ln.id for ln in spreadsheet.build(expanded).lines}
    assert before <= after  # existing prime/generator axes survive by id
    assert "v:prime:3" in after and "v:prime:3" not in before  # the added prime


def test_quantities_spine_column_is_present_with_a_vertical_gridline():
    lay = _layout()
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    # a "quantities" column header, leftmost of the data columns (before generators)
    assert cells["header:quantities"].text == "quantities"
    assert cells["header:quantities"].x < cells["header:gens"].x
    # ...carrying a single vertical gridline down the grid (the column spine)
    assert "trunk:quantities" in by_id
    spine, header = by_id["trunk:quantities"], cells["header:quantities"]
    assert abs(spine.pos - (header.x + header.w / 2)) < 0.51  # centred on the column
    assert spine.start < cells["prime:0"].y  # starts above the quantities row
    assert spine.start + spine.length >= cells["label:damage"].y  # runs past the last row
    # ...and a fold toggle, like every other column
    assert "toggle:col:quantities" in cells


def test_spine_columns_hug_their_col_w_content_not_the_long_title():
    # the quantities and units spine columns each carry only a single COL_W-wide index per
    # row (the domain basis square / generator ratio; the per-row unit label), so their
    # footprint hugs that COL_W content. The long "quantities"/"units" titles are wider than
    # the column and overhang it (rendered without wrapping) rather than setting its width.
    cells = {c.id: c for c in _with(domain_units=True).cells}
    assert cells["header:quantities"].w == spreadsheet.COL_W
    assert cells["header:units"].w == spreadsheet.COL_W
    assert cells["header:quantities"].w < spreadsheet._title_w("quantities")
    assert cells["header:units"].w < spreadsheet._title_w("units")


def test_generators_column_fans_into_per_generator_axes():
    # the generators column carries r side-by-side cells (the genmap, the per-generator
    # units, the form matrix), so it fans into one vertical rule per generator -- exactly
    # like the domain primes column fans per prime -- rather than a single spine down its
    # centre. (It used to be pinned as a full-height spine; the fan matches the mockup.)
    lay = _layout()  # rank 2 -> two generators
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    ids = set(by_id)
    assert {"v:gen:0", "v:gen:1"} <= ids  # one axis per generator
    assert {"trunk:gens", "bus:gens:top", "bus:gens:bot", "foot:gens"} <= ids
    # each per-generator axis runs through the centre of its generator-tuning-map cell
    for i in (0, 1):
        cell = cells[f"tuning:gen:{i}"]
        assert abs(by_id[f"v:gen:{i}"].pos - (cell.x + cell.w / 2)) < 0.51
    # the trunk is now just the short fan stem above the data, not a full-height spine
    assert by_id["trunk:gens"].length < by_id["trunk:quantities"].length


def test_interval_vectors_row_fans_into_per_component_axes():
    # the interval-vectors matrix is d prime-components tall, so its row fans into one
    # horizontal rule per component -- the horizontal mirror of the domain-primes column
    # fanning per prime -- rather than a single spine across the band (which is what it was).
    lay = _layout()  # 2.3.5 -> d = 3 components
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    ids = set(by_id)
    assert {"h:vectors:0", "h:vectors:1", "h:vectors:2"} <= ids  # one rule per component
    assert {"trunk:vectors", "foot:vectors", "vbar:vectors:left", "vbar:vectors:right"} <= ids
    assert "h:vectors" not in ids  # no single spine: it fans like the mapping
    vrow = cells["label:vectors"]
    rules = [by_id[f"h:vectors:{i}"].pos for i in range(3)]
    assert rules == sorted(rules)  # top-to-bottom in component order
    for pos in rules:
        assert vrow.y <= pos <= vrow.y + vrow.h  # each within the vectors row band
    assert by_id["h:vectors:0"].start + by_id["h:vectors:0"].length >= cells["header:targets"].x


def test_tuning_boxes_off_removes_the_tuning_rows_and_the_target_intervals_column():
    off = {c.id for c in _with(tuning_boxes=False).cells}
    # the tuning-family rows are gone
    assert not any(c.split(":")[0] in {"tuning", "just", "retune", "damage"} for c in off)
    assert {"label:tuning", "label:just", "label:retune", "label:damage"}.isdisjoint(off)
    # the target intervals column goes with them: its header, the target headers,
    # and the mapped target interval list that lived in it
    assert "header:targets" not in off
    assert not any(c.startswith(("target:", "cell:mapped:")) for c in off)
    # the mapping over the domain primes (temperament still on) survives
    assert "cell:mapping:0:0" in off


def test_gridded_values_off_empties_the_tiles_but_keeps_the_structure():
    lay = _with(gridded_values=False)
    ids = {c.id for c in lay.cells}
    # no value numbers anywhere: header primes/ratios, matrix, mapped list, cents,
    # interval-vector cells
    assert not any(c.startswith(("prime:", "target:", "gen:", "cell:mapping:",
                                 "cell:mapped:", "cell:vec:", "comma:", "cell:comma:",
                                 "tuning:", "just:", "retune:", "damage:"))
                   for c in ids)
    # no EBK marks (brackets, top brackets, braces, vector rules) and no domain/comma controls
    assert not any(c.startswith(("bracket:", "ebktop:", "ebkbrace:", "sep:")) for c in ids)
    assert {"minus", "plus", "comma_minus", "comma_plus", "gen_minus", "gen_plus",
            "map_minus:0", "map_plus", "target_minus:0", "target_plus"}.isdisjoint(ids)  # every fan ± control goes too
    # ...but the tiles stand empty save their fold toggles and name captions, and
    # the labels, headers and gridlines remain so the empty grid still reads
    assert {"label:mapping", "header:primes", "header:targets", "toggle:row:mapping",
            "caption:mapping:primes"} <= ids
    assert any(b.id == "block:mapping" for b in lay.blocks)  # the grey tiles persist
    assert any(ln.id == "v:prime:0" for ln in lay.lines)  # as do the gridlines


def test_general_quantities_off_blanks_the_body_numbers_keeping_boxes_and_brackets():
    on = {c.id: c for c in _with().cells}
    off = {c.id: c for c in _with(quantities=False).cells}
    # the body value cells are still present -- their boxes stay -- but emptied of
    # their numbers (blank flag set, text cleared). Unlike gridded values off, which
    # removes them outright.
    body = ("cell:mapping:0:0", "cell:mapped:0:0", "cell:comma:0:0", "tuning:prime:0", "gen:0")
    for cid in body:
        assert cid in off and not on[cid].blank  # present in both; carries its value when on
        assert off[cid].blank and off[cid].text == ""  # kept (box stays) but blanked when off
    # the text-bearing cells held a real number when on (matrix/comma inputs read state)
    assert on["cell:mapped:0:0"].text and on["gen:0"].text and on["tuning:prime:0"].text
    # the EBK marks framing them stay (this is the whole difference from gridded off)
    assert any(c.startswith("bracket:") for c in off)
    assert "ebktop:primes" in off and "ebkbrace:primes" in off
    # quantities-row headers and the domain/comma controls are untouched
    assert {"prime:0", "comma:0", "target:0", "plus", "minus", "comma_plus"} <= set(off)
    assert {"label:mapping", "header:primes", "toggle:row:mapping"} <= set(off)


def test_gridded_values_off_also_empties_the_math_expression_cells():
    # math expressions swap the just row's cents for "log₂…" cells (kind mathexpr);
    # gridded values off empties the tiles, so those go too (like the cents they
    # replace). General quantities, by contrast, only trims their "= value" tail
    # (see test_math_expressions_without_quantities_show_only_the_expression).
    on = {c.id for c in _with(math_expressions=True).cells}
    off = {c.id for c in _with(math_expressions=True, gridded_values=False).cells}
    assert any(c.startswith("just:") for c in on)  # shown when gridded values is on
    assert not any(c.startswith("just:") for c in off)  # gone when it is off


def test_specific_quantities_off_removes_the_quantities_row_and_column():
    on, off = _with(), _with(domain_quantities=False)
    on_ids, off_ids = {c.id for c in on.cells}, {c.id for c in off.cells}
    assert {"label:quantities", "prime:0", "header:quantities"} <= on_ids  # present by default
    # the quantities ROW -- its label, the domain-prime / target-ratio headers in
    # it, the domain ± controls riding it, and its gridline -- is gone
    assert "label:quantities" not in off_ids
    assert not any(c.startswith(("prime:", "target:")) for c in off_ids)
    assert {"minus", "plus"}.isdisjoint(off_ids)
    assert "h:quantities" not in {ln.id for ln in off.lines}
    # the quantities spine COLUMN goes with it: its header and its vertical gridline
    assert "header:quantities" not in off_ids
    assert "trunk:quantities" not in {ln.id for ln in off.lines}
    # the body quantities (mapping matrix, tuning rows) are untouched
    assert {"cell:mapping:0:0", "tuning:target:0"} <= off_ids


def test_temperament_boxes_off_removes_the_mapping_and_vectors_rows_and_domain_columns():
    off = {c.id: c for c in _with(temperament_boxes=False).cells}
    on = {c.id: c for c in _with().cells}
    # the mapping quantities (matrix, mapped list, generator ratios) are gone
    assert "label:mapping" not in off
    assert not any(c.startswith(("cell:mapping:", "cell:mapped:", "gen:")) for c in off)
    # the interval-vectors row is the temperament's too -- its vectors are read over the
    # domain basis -- so it goes with the domain rather than lingering as a lone row when
    # every specific box is off (it owned no toggle before, so it was the sole survivor)
    assert "label:vectors" not in off
    assert not any(c.startswith("cell:vec:") for c in off)
    # the whole domain-primes column goes with it: its header, the prime headers,
    # and every row's prime-side cells -- including the tuning maps over primes
    assert "header:primes" not in off
    assert not any(c.startswith(("prime:", "tuning:prime:", "just:prime:", "retune:prime:")) for c in off)
    # the commas column belongs to the temperament too, so it goes as well: header,
    # comma headers, the comma basis, and the comma-size cells across the tuning rows
    assert "header:commas" not in off
    assert not any(c.startswith(("comma:", "cell:comma:", "tuning:comma:", "just:comma:",
                                 "retune:comma:")) for c in off)
    assert {"comma_plus", "comma_minus"}.isdisjoint(off)
    # tuning over the targets survives and rises into the freed space
    assert "tuning:target:0" in off
    assert off["tuning:target:0"].y < on["tuning:target:0"].y


def test_every_row_including_quantities_has_a_fold_toggle():
    cells = {c.id: c for c in _layout().cells}
    for key in ("quantities", "vectors", "mapping", "tuning", "just", "retune", "damage"):
        assert f"toggle:row:{key}" in cells  # every row gets the [x]/expand control
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


def test_collapsed_column_keeps_its_title_at_a_width_that_fits_it():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    coll = {c.id: c for c in spreadsheet.build(base, collapsed={"col:targets"}).cells}["header:targets"]
    full = {c.id: c for c in spreadsheet.build(base).cells}["header:targets"]
    assert coll.text == "target\nintervals"  # the title stays put (not blanked, not rotated)
    assert spreadsheet.STRIP < coll.w < full.w  # folded narrower, but wide enough to read the title


def test_collapsed_column_gridline_stays_centred_in_its_fold_node():
    # Folding a column shrinks its footprint to the title strip; its gridline must follow,
    # staying centred in the fold toggle (the node) and under the title -- not stranded at the
    # centre of where the OPEN cells used to sit. (commas drifted 2px right; targets, with more
    # cells, drifted 95px -- the gridline sat well outside the collapsed strip.)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    for key in ("commas", "targets"):
        lay = spreadsheet.build(base, collapsed={f"col:{key}"})
        trunk = {ln.id: ln for ln in lay.lines}[f"trunk:{key}"]
        cells = {c.id: c for c in lay.cells}
        toggle, header = cells[f"toggle:col:{key}"], cells[f"header:{key}"]
        assert abs(trunk.pos - (toggle.x + toggle.w / 2)) < 0.51, key  # centred in the node
        assert abs(trunk.pos - (header.x + header.w / 2)) < 0.51, key  # and under the title


def test_a_collapsed_multiline_title_strip_fits_its_widest_line():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    # a populated interest column (open wider than its title) folds to its title strip: sized
    # to the widest "\n"-broken line, so a three-word title stacks instead of a ~226px ribbon
    interest = {c.id: c for c in spreadsheet.build(
        base, collapsed={"col:interest"}, interest=[(0, 0, 0)] * 5).cells}["header:interest"]
    assert interest.text == "other intervals\nof interest"
    assert interest.w == len("other intervals") * 8 + 10  # the widest line, not all 27 chars
    assert interest.w < len("other intervals of interest") * 8 + 10  # far narrower than one line


def test_collapsing_a_spine_column_never_widens_it():
    # a spine (quantities/units) is one COL_W wide open — narrower than its long title, which
    # overhangs it. Collapsing it must NOT balloon it out to the title's strip width: collapsing
    # a column should never make it wider. It stays a COL_W strip with the title still overhanging.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults(); s["domain_units"] = True
    opened = {c.id: c for c in spreadsheet.build(base, s).cells}
    collapsed = {c.id: c for c in spreadsheet.build(base, s, collapsed={"col:quantities", "col:units"}).cells}
    for key in ("quantities", "units"):
        assert collapsed[f"header:{key}"].w <= opened[f"header:{key}"].w  # collapse never widens
        assert collapsed[f"header:{key}"].w == spreadsheet.COL_W  # ...stays a single-COL_W strip


def test_a_rows_nested_control_grows_every_tile_in_that_row_uniformly():
    # A nested in-tile control (the generator tuning-ranges chart, box 𝐋's prescaler chooser,
    # box 𝒄's norm chooser) extends its OWNING tile downward. The grid stays uniform: every
    # sibling tile in that row grows to the same height, so the row is one band rather than
    # one tall tile beside short ones.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    ranges = settings.defaults(); ranges["tuning_ranges"] = True
    on = {b.id: b for b in spreadsheet.build(base, ranges).blocks}
    gens = on["block:tuning:gens"].h  # the tile carrying the ranges chart
    for sib in ("block:tuning:primes", "block:tuning:commas", "block:tuning:targets"):
        assert on[sib].h == gens, sib  # chart-less siblings match the charted tile
    off = {b.id: b for b in spreadsheet.build(base).blocks}
    assert gens > off["block:tuning:primes"].h  # the chart reserves real height (not zeroed away)

    alt = settings.defaults(); alt["weighting"] = True; alt["alt_complexity"] = True
    aon = {b.id: b for b in spreadsheet.build(base, alt).blocks}
    presc = aon["block:prescaling:primes"].h  # box 𝐋 extends the prescaling row's primes tile
    for sib in ("block:prescaling:commas", "block:prescaling:targets"):
        assert aon[sib].h == presc, sib
    comp = aon["block:complexity:targets"].h  # box 𝒄 extends the complexity row's targets tile
    for sib in ("block:complexity:primes", "block:complexity:commas"):
        assert aon[sib].h == comp, sib


def test_collapsing_a_column_does_not_shrink_its_rows_caption_band():
    # the row's caption band is sized to its tallest caption, but it must NOT depend on which
    # columns are open: collapsing a column (hiding its caption) must not drop the band and
    # shrink the row's other tiles. The "generator tuning map" caption wraps to two lines in the
    # narrow gens column while the sibling tuning captions fit one line, so with the commas
    # column also collapsed the gens caption is the band's sole two-liner — exactly the case
    # where the old code shrank the prime/target tiles on collapsing generators.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    without_gens = {b.id: b for b in spreadsheet.build(base, s, collapsed={"col:commas"}).blocks}
    with_gens = {b.id: b for b in spreadsheet.build(base, s, collapsed={"col:commas", "col:gens"}).blocks}
    for sib in ("block:tuning:primes", "block:tuning:targets"):
        assert with_gens[sib].h == without_gens[sib].h, f"{sib} shrank when the gens column collapsed"


def test_collapsing_a_row_folds_its_panel_away_and_leaves_a_gridline():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base, collapsed={"row:tuning"})
    blocks = {b.id: b for b in lay.blocks}
    lines = {ln.id for ln in lay.lines}
    assert "block:tuning:primes" in blocks  # the panel persists so the renderer can animate it...
    assert blocks["block:tuning:primes"].h == 0  # ...folding to nothing (no leftover grey tile)
    assert "h:tuning" in lines  # leaving a single gridline through the folded row


def test_collapsing_a_column_folds_its_panels_away_and_converges_the_lines():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base, collapsed={"col:primes"})
    blocks = {b.id: b for b in lay.blocks}
    by_id = {ln.id: ln for ln in lay.lines}
    assert blocks["block:mapping"].w == 0  # the primes-column panels fold to nothing
    # the per-prime verticals converge onto one x (so they read as a single line)
    assert by_id["v:prime:0"].pos == by_id["v:prime:1"].pos == by_id["v:prime:2"].pos
    assert by_id["bus:primes:top"].length == 0  # ...and the buses shrink to nothing


def test_a_collapsed_bands_gridline_is_dotted_while_open_bands_stay_solid():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base, collapsed={"row:tuning", "col:primes"})
    by_id = {ln.id: ln for ln in lay.lines}
    # a collapsed row's lone rule, and every converged vertical of a collapsed
    # column (its trunk + the per-element lines), read as a dotted placeholder
    assert by_id["h:tuning"].dotted
    assert by_id["trunk:primes"].dotted
    assert by_id["v:prime:0"].dotted
    # open bands keep their solid rules
    assert not by_id["h:quantities"].dotted
    assert not by_id["trunk:gens"].dotted


def test_a_collapsed_fanned_mapping_row_dots_its_converged_rules():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    by_id = {ln.id: ln for ln in spreadsheet.build(base, collapsed={"row:mapping"}).lines}
    assert by_id["trunk:mapping"].dotted and by_id["h:mapping:0"].dotted


def test_the_mapping_matrix_is_framed_top_and_bottom():
    cells = {c.id: c for c in _layout().cells}
    # the mapping matrix gets a spanning top bracket and bottom curly brace
    assert "ebktop:primes" in cells and "ebkbrace:primes" in cells
    top, brace = cells["ebktop:primes"], cells["ebkbrace:primes"]
    first, last = cells["cell:mapping:0:0"], cells["cell:mapping:1:0"]
    # the framing bands stand off the matrix by a gap, so the top bracket and
    # bottom brace never butt up against the per-row ⟨ … ] brackets (which would
    # read as one tall curly shape on the left edge)
    assert top.y + top.h < first.y  # top bracket sits fully above row 0, clear of it
    assert brace.y > last.y + last.h  # brace sits fully below the last row, clear of it
    # the mapped list is marked per target column
    assert {"ebktop:mapped:0", "ebkbrace:mapped:0"} <= set(cells)


def test_form_box_shows_the_canonical_mapping_over_the_primes():
    # the "form" toggle adds a "canonical mapping" row whose primes tile holds M in
    # canonical form (defactored + HNF) — for ((1,1,0),(0,1,4)) that is
    # ((1,0,-4),(0,1,4)), distinct from the stored matrix in the mapping row
    cells = {c.id: c for c in _with(form_controls=True).cells}
    assert cells["cell:canon:0:0"].text == "1"
    assert cells["cell:canon:0:2"].text == "-4"
    assert cells["cell:canon:1:1"].text == "1"
    assert cells["cell:canon:1:2"].text == "4"
    # off by default the row adds nothing
    assert not any(c.id.startswith("cell:canon:") for c in _layout().cells)


def test_canonical_mapping_row_is_framed_like_the_mapping_above_it():
    cells = {c.id: c for c in _with(form_controls=True).cells}
    # a stack of maps (⟨ … ] per row), enclosed by its own top bracket + bottom brace
    assert cells["bracket:canon:map:0:l"].text == "⟨" and cells["bracket:canon:map:0:r"].text == "]"
    assert "ebktop:canon" in cells and "ebkbrace:canon" in cells
    assert cells["ebktop:canon"].y < cells["cell:canon:0:0"].y    # top bracket above row 0
    assert cells["ebkbrace:canon"].y > cells["cell:canon:1:0"].y  # brace below the last row
    # captioned, and seated between the interval-vectors and mapping matrices
    assert cells["caption:canon:primes"].text == "canonical mapping"
    assert cells["basis:0"].y < cells["cell:canon:0:0"].y < cells["cell:mapping:0:0"].y
    # the mapping keeps its own frame (the canonical frame doesn't steal its ids)
    assert "ebktop:primes" in cells and cells["ebktop:primes"].y > cells["cell:canon:1:0"].y


def test_form_box_shows_the_generator_form_matrix_over_the_gens():
    cells = {c.id: c for c in _with(form_controls=True).cells}
    # F (generator form matrix, r×r) renders in the canon row's gens column as a
    # bordered grid: for ((1,1,0),(0,1,4)), F = ((1,-1),(0,1))
    assert cells["cell:form:0:0"].text == "1" and cells["cell:form:0:1"].text == "-1"
    assert cells["cell:form:1:0"].text == "0" and cells["cell:form:1:1"].text == "1"
    assert cells["cell:form:0:0"].kind == "formcell"  # a read-only bordered cell
    # framed { … ] per row (the generator-map brackets) plus an enclosing top bracket/brace
    assert cells["bracket:form:map:0:l"].text == "{" and cells["bracket:form:map:0:r"].text == "]"
    assert "ebktop:form" in cells and "ebkbrace:form" in cells
    # the form box adds nothing while the toggle is off
    assert not any(c.id.startswith("cell:form:") for c in _layout().cells)


def test_form_controls_adds_a_choose_form_chooser_to_the_mapping_and_comma_basis_boxes():
    cells = {c.id: c for c in _with(form_controls=True).cells}
    # a "<choose form>" chooser rides in the mapping box and the comma-basis box
    assert cells["formchooser:mapping"].kind == "formchooser"
    assert cells["formchooser:comma_basis"].kind == "formchooser"
    # each over its box's column (mapping over the primes, comma basis over the commas), seated
    # one BOX_INNER inside its tile-spanning box's left edge
    inset = spreadsheet.BOX_INNER
    assert cells["formchooser:mapping"].x == cells["header:primes"].x + inset
    assert cells["formchooser:comma_basis"].x == cells["header:commas"].x + inset
    # seated below the tile's value rows, never over the matrix
    assert cells["formchooser:mapping"].y > cells["cell:mapping:1:0"].y
    # the control adds nothing while form_controls is off
    assert not any(c.id.startswith("formchooser:") for c in _layout().cells)


def test_mapped_list_rules_its_vector_columns_apart_clear_of_the_marks():
    cells = {c.id: c for c in _layout().cells}
    # the mapped target interval list separates its vector columns with vertical
    # bars, and the per-column top/bottom marks are inset so they never touch one
    assert "sep:mapped:1" in cells  # a bar between columns 0 and 1
    sep, first = cells["sep:mapped:1"], cells["cell:mapped:0:0"]
    top0, brace0 = cells["ebktop:mapped:0"], cells["ebkbrace:mapped:0"]
    assert top0.w < spreadsheet.COL_W and brace0.w < spreadsheet.COL_W  # inset, not full column
    assert top0.x + top0.w < sep.x  # the mark stops short of the bar to its right
    assert sep.y == first.y and sep.h == cells["cell:mapped:1:0"].y + cells["cell:mapped:1:0"].h - first.y


def test_maps_get_angle_brackets_and_lists_get_square_brackets():
    cells = {c.id: c for c in _layout().cells}
    # each mapping row is a map: ⟨ … ] (one bracket pair per generator)
    assert cells["bracket:map:0:l"].text == "⟨" and cells["bracket:map:0:r"].text == "]"
    assert "bracket:map:1:l" in cells
    # tuning/just/retuning maps are maps too
    assert cells["bracket:tuning:map:l"].text == "⟨" and cells["bracket:tuning:map:r"].text == "]"
    # the target-side lists are plain: [ … ]
    assert cells["bracket:mapped:l"].text == "[" and cells["bracket:mapped:r"].text == "]"
    assert cells["bracket:damage:l"].text == "[" and cells["bracket:damage:r"].text == "]"
    # brackets sit just outside the value cells (left of the first, right of the last)
    assert cells["bracket:map:0:l"].x < cells["cell:mapping:0:0"].x < cells["bracket:map:0:r"].x


def test_per_row_brackets_are_short_and_centred_leaving_a_gap_between_rows():
    cells = {c.id: c for c in _layout().cells}
    l0, l1 = cells["bracket:map:0:l"], cells["bracket:map:1:l"]
    row0 = cells["cell:mapping:0:0"]
    # each per-row bracket is much shorter than the ROW_H row it sits in...
    assert l0.h < spreadsheet.ROW_H
    assert l0.h == l1.h
    # ...and centred within its row
    assert abs((l0.y + l0.h / 2) - (row0.y + row0.h / 2)) < 0.51
    # so neighbouring rows' brackets keep a clear gap >= 75% of a bracket's height
    gap = l1.y - (l0.y + l0.h)
    assert gap >= 0.75 * l0.h


def test_mapped_list_outer_bracket_still_spans_the_whole_matrix():
    cells = {c.id: c for c in _layout().cells}
    b = cells["bracket:mapped:l"]
    first, last = cells["cell:mapped:0:0"], cells["cell:mapped:1:0"]
    # the enclosing [ ] is the tall exception: it spans both mapping rows
    assert b.h > spreadsheet.ROW_H
    assert b.y <= first.y and b.y + b.h >= last.y + last.h


def test_the_row_fold_node_clears_the_first_content_tile():
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))))
    node = {c.id: c for c in lay.cells}["toggle:row:mapping"]
    gens_block = {b.id: b for b in lay.blocks}["block:gens"]
    assert node.x + node.w <= gens_block.x  # the node does not collide with the tile


def test_each_content_tile_has_a_top_left_fold_toggle():
    cells = {c.id: c for c in _layout().cells}
    # every (row, column) content tile carries its own fold control, in addition
    # to the per-row and per-column ones
    for rkey, ckey in (("quantities", "primes"), ("quantities", "targets"),
                       ("mapping", "primes"), ("mapping", "targets"),
                       ("tuning", "primes"), ("tuning", "targets"), ("damage", "targets")):
        assert f"toggle:tile:{rkey}:{ckey}" in cells
    # it sits in the tile's top-left corner: above and left of the tile's content
    node = cells["toggle:tile:mapping:primes"]
    first = cells["cell:mapping:0:0"]
    assert node.x < first.x and node.y < first.y


def test_tile_toggle_sits_clear_of_the_tile_content_and_panel_edges():
    lay = _layout()
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    # framed tile: the toggle is fully above the matrix's top framing band, so it
    # never overlaps the bracket or the cells
    tog, top = cells["toggle:tile:mapping:primes"], cells["ebktop:primes"]
    assert tog.y + tog.h <= top.y
    # single-row tile: it clears the value row too
    tt, v = cells["toggle:tile:tuning:primes"], cells["tuning:prime:0"]
    assert tt.y + tt.h <= v.y
    # and it floats inset inside its grey panel, never flush against an edge
    panel = blocks["block:mapping"]
    assert panel.x < tog.x and panel.y < tog.y
    assert tog.x + tog.w < panel.x + panel.w


def test_collapsing_a_tile_hides_its_content_keeps_its_toggle_and_folds_its_panel():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base, collapsed={"tile:mapping:primes"})
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    # the matrix, its row brackets, and its top/bottom framing bands all vanish
    assert not any(c.startswith("cell:mapping:") for c in cells)
    assert not any(c.startswith("bracket:map:") for c in cells)
    assert "ebktop:primes" not in cells and "ebkbrace:primes" not in cells
    # ...the panel folds to a zero-size point so the renderer animates it away...
    assert blocks["block:mapping"].w == 0 and blocks["block:mapping"].h == 0
    # ...but the toggle stays so the tile can be re-expanded
    assert "toggle:tile:mapping:primes" in cells


def test_collapsing_a_tile_leaves_its_siblings_and_the_grid_geometry_intact():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    full = spreadsheet.build(base)
    coll = spreadsheet.build(base, collapsed={"tile:mapping:primes"})
    fc = {c.id: c for c in full.cells}
    cc = {c.id: c for c in coll.cells}
    # a sibling tile sharing the mapping row is untouched, and nothing reflows
    assert "cell:mapped:0:0" in cc
    assert cc["cell:mapped:0:0"].x == fc["cell:mapped:0:0"].x
    assert coll.width == full.width and coll.height == full.height
    # the shared prime axes still run through the now-empty intersection
    assert {ln.id for ln in coll.lines} == {ln.id for ln in full.lines}


def test_tile_toggle_glyph_flips_between_collapse_and_expand():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    open_ = {c.id: c for c in spreadsheet.build(base).cells}["toggle:tile:mapping:primes"]
    shut = {c.id: c for c in spreadsheet.build(base, collapsed={"tile:mapping:primes"}).cells}["toggle:tile:mapping:primes"]
    assert open_.text == "unfold_less"  # an open tile offers to fold in
    assert shut.text == "unfold_more"  # a folded tile offers to expand out


def test_collapsing_a_whole_band_removes_its_per_tile_toggles():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    # a folded row/column subsumes its tiles into the strip, so their corner
    # toggles must not survive as orphaned boxes floating on the gridline
    row_off = {c.id for c in spreadsheet.build(base, collapsed={"row:tuning"}).cells}
    assert not any(c.startswith("toggle:tile:tuning:") for c in row_off)
    col_off = {c.id for c in spreadsheet.build(base, collapsed={"col:primes"}).cells}
    assert not any(c.endswith(":primes") and c.startswith("toggle:tile:") for c in col_off)


def test_master_toggle_sits_in_the_top_left_node_corner():
    cells = {c.id: c for c in _layout().cells}
    master = cells["toggle:all"]
    # it shares the row toggles' x (the node column) and the column toggles' y (the
    # node row), so it lands in the corner where the two toggle lines converge
    assert master.x == cells["toggle:row:mapping"].x
    assert master.y == cells["toggle:col:primes"].y
    # and it is the top-left of the cross: above every row toggle, left of every column one
    assert master.y < cells["toggle:row:mapping"].y
    assert master.x < cells["toggle:col:primes"].x


def _foldable(layout):
    return {c.id.split("toggle:", 1)[1] for c in layout.cells
            if c.kind in ("rowtoggle", "coltoggle")}


def test_master_toggle_glyph_reflects_whether_the_whole_grid_is_collapsed():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    open_grid = {c.id: c for c in spreadsheet.build(base).cells}["toggle:all"]
    assert open_grid.text == "unfold_less"  # something's open -> offer collapse-all
    every = _foldable(spreadsheet.build(base))
    shut_grid = {c.id: c for c in spreadsheet.build(base, collapsed=every).cells}["toggle:all"]
    assert shut_grid.text == "unfold_more"  # all folded -> offer expand-all


def test_toggle_all_collapses_every_band_when_any_is_open():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base)  # fully open
    after = spreadsheet.toggle_all_collapsed(lay, set())
    assert after == _foldable(lay)  # exactly every present row & column, nothing more
    assert {"row:mapping", "col:primes", "col:targets"} <= after


def test_toggle_all_expands_everything_when_fully_collapsed():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base)
    every = _foldable(lay)
    # already fully folded (with a stray individually-folded tile too) -> expand clears it all
    assert spreadsheet.toggle_all_collapsed(lay, every | {"tile:mapping:primes"}) == set()


def test_collapsing_all_folds_the_whole_grid_down_to_its_strips():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    full = spreadsheet.build(base)
    shut = spreadsheet.build(base, collapsed=spreadsheet.toggle_all_collapsed(full, set()))
    # no content survives: every value group has folded into its row/column strip
    assert not any(c.id.startswith(("cell:", "tuning:", "just:", "retune:", "damage:", "prime:"))
                   for c in shut.cells)
    assert shut.width < full.width and shut.height < full.height  # the board shrinks to the strips
    # labels, headers and the master toggle persist so the grid can be re-expanded
    assert {c.id for c in shut.cells} >= {"label:mapping", "header:primes", "toggle:all"}


def test_presets_off_shows_no_chooser_dropdowns():
    cells = {c.id for c in _with(presets=False).cells}
    assert not any(c.startswith("preset:") for c in cells)


def test_presets_on_adds_the_three_chooser_dropdowns_under_their_tiles():
    cells = {c.id: c for c in _with(presets=True).cells}
    assert {"preset:temperament", "preset:tuning", "preset:target"} <= set(cells)
    inset = spreadsheet.BOX_INNER  # the dropdown sits one inner-pad inside its tile-spanning box
    # the temperament chooser sits under the mapping matrix, in its column
    temp, matrix = cells["preset:temperament"], cells["cell:mapping:0:0"]
    assert temp.y > matrix.y and temp.x == cells["header:primes"].x + inset
    # the target chooser sits under the target interval list, in its column
    assert cells["preset:target"].x == cells["header:targets"].x + inset


def test_tuning_and_target_choosers_show_the_live_selection_temperament_is_a_placeholder():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="destretched-octave minimax-ES", target_spec="OLD").cells}
    assert cells["preset:tuning"].text == "destretched-octave minimax-ES"  # reflects the active scheme
    assert cells["preset:target"].text == "OLD"  # reflects the active set
    assert cells["preset:temperament"].text == ""  # a chooser placeholder, not a live value


def test_preset_choosers_follow_their_tiles_when_temperament_is_hidden():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["temperament_boxes"] = True, False
    cells = {c.id for c in spreadsheet.build(base, s).cells}
    # every chooser rides a temperament-owned tile: the temperament + tuning choosers the
    # domain-primes column (under the mapping matrix / tuning map), the target chooser the
    # interval-vectors row (the target interval list tile) -- so hiding the temperament
    # takes each chooser away with its tile
    assert "preset:temperament" not in cells
    assert "preset:tuning" not in cells
    assert "preset:target" not in cells


def test_preset_dropdown_clears_the_row_below_it():
    cells = {c.id: c for c in _with(presets=True).cells}
    drop, next_row = cells["preset:tuning"], cells["label:just"]
    assert drop.y + drop.h <= next_row.y  # the reserved band keeps it off the next row


def test_preset_chooser_sits_below_the_plain_text_band():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["plain_text_values"] = True, True
    cells = {c.id: c for c in spreadsheet.build(base, s).cells}
    chooser, ptext = cells["preset:tuning"], cells["ptext:tuning:primes"]
    assert chooser.y >= ptext.y + ptext.h  # the chooser rides beneath the plain-text box


def test_target_chooser_is_wider_to_seat_its_numeric_override():
    # the target chooser carries a numeric limit field beside the TILT/OLD select,
    # so it reserves more width than the single-control tuning chooser
    cells = {c.id: c for c in _with(presets=True).cells}
    assert cells["preset:target"].w > cells["preset:tuning"].w


def test_tuning_and_temperament_dropdowns_are_copied_into_more_tiles():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    lay = spreadsheet.build(base, s, tuning_scheme="destretched-octave minimax-ES")
    cells = {c.id: c for c in lay.cells}
    boxes = {b.id: b for b in lay.blocks}
    # a copy of the tuning chooser rides the generator tuning map tile (gens column),
    # mirroring the live scheme like the tuning map copy in the primes column. The dropdown seats
    # at the box's left inset (the box spans the tile, so the dropdown is one BOX_INNER off it)
    inset = spreadsheet.BOX_INNER
    gt = cells["preset:tuning:gens"]
    assert gt.x == cells["header:gens"].x + inset and gt.text == "destretched-octave minimax-ES"
    # it shares the tuning row's control band with the tuning map dropdown (primes box)
    assert boxes["block:preset:tuning:gens"].y == boxes["block:preset:tuning"].y
    # a copy of the temperament chooser rides the comma basis tile (commas column)
    ct = cells["preset:temperament:commas"]
    assert ct.x == cells["header:commas"].x + inset and ct.text == ""  # a placeholder, like the mapping copy


def test_target_preset_now_lives_in_the_target_interval_list_tile():
    # the target interval set chooser belongs to the target interval list (the vectors-row
    # targets tile), not the quantities row -- so it rides below that list's value cells
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s).cells}
    target = cells["preset:target"]
    # still under the targets column, seated one BOX_INNER inside its tile-spanning box
    assert target.x == cells["header:targets"].x + spreadsheet.BOX_INNER
    # it now sits in the interval-vectors row (the target interval list), below those cells
    assert target.y > cells["cell:vec:targets:0:0"].y
    # and below the quantities-row target ratios it used to sit under
    assert target.y > cells["target:0"].y


def test_control_dropdowns_are_boxed_within_their_tiles():
    # every dropdown rides inside a thin-bordered box that STAYS WITHIN its tile, with the
    # standard caption label UNDERNEATH the control (the dropdown-label asset, not a box title)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["form_controls"] = True, True
    lay = spreadsheet.build(base, s)
    cells = {c.id: c for c in lay.cells}
    boxes = {b.id: b for b in lay.blocks}
    for cid, label, tile in (("preset:tuning", "established tuning scheme", "block:tuning:primes"),
                             ("preset:tuning:gens", "established tuning scheme", "block:tuning:gens"),
                             ("preset:temperament", "temperament", "block:mapping"),
                             ("preset:target", "target interval set scheme", "block:vec:targets"),
                             ("formchooser:mapping", "form", "block:mapping"),
                             ("formchooser:comma_basis", "form", "block:vec:commas")):
        ctrl, box, panel = cells[cid], boxes[f"block:{cid}"], boxes[tile]
        assert box.boxed is True  # a bordered box, not a plain tile
        assert box.x <= ctrl.x and box.x + box.w >= ctrl.x + ctrl.w  # encloses the control
        assert box.y <= ctrl.y and box.y + box.h >= ctrl.y + ctrl.h
        # the box stays WITHIN its tile -- never spilling out (the reported bug)
        assert box.x >= panel.x - 0.5 and box.x + box.w <= panel.x + panel.w + 0.5
        # the standard dropdown label (a left-justified caption, the .rtt-caption-left asset)
        # hugs the dropdown's bottom edge, like the box-𝐋/𝒄/𝒘 controls -- not a box title above
        lbl = cells[f"block:{cid}:label"]
        assert lbl.kind == "caption" and lbl.text == label and lbl.align == "left" and lbl.y > ctrl.y


def test_a_long_control_label_widens_its_narrow_tile():
    # the generator tuning map (gens) column is naturally narrow (a couple of generators), too
    # narrow for the one-line "established tuning scheme" label -- so enabling presets widens
    # that tile to fit the label rather than letting it spill, keeping the label on one line
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    gens_off = {b.id: b for b in spreadsheet.build(base, settings.defaults()).blocks}["block:tuning:gens"]
    lay = spreadsheet.build(base, {**settings.defaults(), "presets": True})
    gens_on = {b.id: b for b in lay.blocks}["block:tuning:gens"]
    box = {b.id: b for b in lay.blocks}["block:preset:tuning:gens"]
    assert gens_on.w > gens_off.w  # the tile widened for the label
    assert gens_on.w >= spreadsheet._min_width_for_lines("established tuning scheme", 1)  # fits it on one line
    assert box.x >= gens_on.x and box.x + box.w <= gens_on.x + gens_on.w  # the box stays inside the widened tile


def test_chooser_boxes_span_the_full_width_of_their_tiles():
    # EVERY control box spans the full width of its tile — its border sits on the tile footprint
    # (equal insets each side, like the optimization and tuning-ranges boxes), regardless of how
    # wide the dropdown inside it is. This includes the target chooser (a narrow dropdown in a
    # wide box; the dropdown's own width is the next test's concern).
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["form_controls"] = True, True
    boxes = {b.id: b for b in spreadsheet.build(base, s).blocks}
    for cid, tile in (("block:preset:temperament", "block:mapping"),
                      ("block:preset:tuning", "block:tuning:primes"),
                      ("block:preset:tuning:gens", "block:tuning:gens"),
                      ("block:preset:target", "block:vec:targets"),
                      ("block:formchooser:mapping", "block:mapping"),
                      ("block:formchooser:comma_basis", "block:vec:commas")):
        box, panel = boxes[cid], boxes[tile]
        left, right = box.x - panel.x, (panel.x + panel.w) - (box.x + box.w)
        assert abs(left - right) < 1  # equal insets == the box spans its tile's footprint


def test_target_chooser_box_spans_its_tile_with_a_capped_dropdown_inside():
    # widening control boxes is about the BOX (frame), not the dropdown: the target chooser's box
    # spans its wide tile like every other box, while the dropdown inside keeps its natural (capped)
    # width — the numeric limit square + family select, with empty room (box 𝐓's checkbox slot) to
    # its right
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    lay = spreadsheet.build(base, s)
    box = {b.id: b for b in lay.blocks}["block:preset:target"]
    dropdown = {c.id: c for c in lay.cells}["preset:target"]
    assert dropdown.w < box.w - 30  # the dropdown stays narrow inside the wide, tile-spanning box


def test_build_honors_the_target_interval_spec():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5
    tilt = {c.text for c in spreadsheet.build(base, target_spec="TILT").cells if c.id.startswith("target:")}
    old = {c.text for c in spreadsheet.build(base, target_spec="OLD").cells if c.id.startswith("target:")}
    assert tilt != old  # the two families differ
    assert "8/5" in old and "8/5" not in tilt  # a diamond ratio absent from the triangle


def test_build_honors_the_tuning_scheme():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    top = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="minimax-S").cells}
    pote = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="destretched-octave minimax-ES").cells}
    # destretched-octave minimax-ES holds the octave pure; minimax-S stretches it — so the prime-2 tuning differs
    assert top["tuning:prime:0"] != pote["tuning:prime:0"]
    assert pote["tuning:prime:0"] == "1200.000"


def test_plain_text_values_adds_a_string_band_under_each_tile():
    on = {c.id: c for c in _with(plain_text_values=True).cells}
    off = {c.id for c in _with(plain_text_values=False).cells}
    assert not any(c.startswith("ptext:") for c in off)  # off by default
    # each value group gets its natural plain-text form (from the service seam)
    assert on["ptext:mapping:primes"].text == "[⟨1 1 0] ⟨0 1 4]}"
    assert on["ptext:mapping:targets"].text.startswith("[[1 0}")  # generator-coord vectors (close })
    assert on["ptext:vectors:commas"].text == "[[4 -4 1⟩]"  # comma basis: vector list, outer [ ]
    assert on["ptext:quantities:primes"].text == "2.3.5"
    assert on["ptext:tuning:primes"].text.startswith("⟨")  # a tuning map


def test_quantities_ratios_get_per_column_plain_text_below_each_ratio():
    cells = {c.id: c for c in _with(plain_text_values=True).cells}
    # the target ratios get one inline "n/d" per column, directly below each ratio cell
    assert cells["ptext:quantities:targets:0"].text == "2/1"
    assert cells["ptext:quantities:targets:2"].text == "3/2"
    assert cells["ptext:quantities:commas:0"].text == "80/81"
    # each sits in its own column, aligned under the ratio above it
    assert cells["ptext:quantities:targets:0"].x == cells["target:0"].x
    assert cells["ptext:quantities:targets:0"].y > cells["target:0"].y


def test_plain_text_band_sits_below_the_caption_spanning_its_column():
    cells = {c.id: c for c in _with(plain_text_values=True, names=True).cells}
    pt, cap, header = cells["ptext:mapping:primes"], cells["caption:mapping:primes"], cells["header:primes"]
    assert pt.y >= cap.y + cap.h  # the string sits below the name caption
    assert pt.x == header.x and pt.w == header.w  # and spans the column


def test_plain_text_band_grows_tiles_and_pushes_lower_rows_down():
    on = {c.id: c for c in _with(plain_text_values=True).cells}
    off = {c.id: c for c in _with(plain_text_values=False).cells}
    assert on["label:tuning"].y > off["label:tuning"].y  # the band reserves space, lifting nothing


def test_collapsing_hides_the_plain_text_band_with_the_tile():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["plain_text_values"] = True
    row_off = {c.id for c in spreadsheet.build(base, s, collapsed={"row:mapping"}).cells}
    assert not any(c.startswith("ptext:mapping:") for c in row_off)  # a folded row keeps no band
    tile_off = {c.id for c in spreadsheet.build(base, s, collapsed={"tile:mapping:primes"}).cells}
    assert "ptext:mapping:primes" not in tile_off  # a collapsed tile drops its band...
    assert "ptext:mapping:targets" in tile_off  # ...but its open sibling keeps one


def test_editable_plain_text_tiles_render_as_inputs():
    # weighting opens the prescaling row so the bare prescaler 𝐿 tile's ptext is present too
    cells = {c.id: c for c in _with(plain_text_values=True, weighting=True).cells}
    # the editable tiles render as inputs: the mapping + comma-basis duals, the generator
    # tuning map (typing a cents tuning freezes it), the target interval list (typing a
    # vector list overrides the target set), and the bare prescaler 𝐿 (typing a d×d
    # diagonal matrix overrides the complexity-prescaler diagonal)
    for cid in ("ptext:mapping:primes", "ptext:vectors:commas", "ptext:tuning:gens",
                "ptext:vectors:targets", "ptext:prescaling:primes"):
        assert cells[cid].kind == "ptextedit"
    # every computed value stays read-only display text, not an editable box
    for cid in ("ptext:mapping:targets", "ptext:mapping:commas", "ptext:tuning:primes",
                "ptext:quantities:primes", "ptext:damage:targets",
                "ptext:prescaling:commas"):  # 𝐿C is a computed product, not editable
        assert cells[cid].kind == "ptext"


def test_plain_text_values_are_a_single_line_within_their_column():
    cells = {c.id: c for c in _with(plain_text_values=True).cells}
    # every read-only value is one line tall and no wider than its column — the app
    # shrinks the font to fit, so a long tuning row never wraps or spills
    long, header = cells["ptext:tuning:targets"], cells["header:targets"]
    assert long.h == spreadsheet.PTEXT_H  # one line, even for the longest size list...
    assert long.w == header.w  # ...spanning exactly its column, never wider
    assert cells["ptext:just:targets"].h == spreadsheet.PTEXT_H
    # the editable duals are one (slightly taller) input line
    assert cells["ptext:mapping:primes"].h == spreadsheet.PTEXT_EDIT_H


def test_names_toggles_in_tile_captions_but_never_the_row_col_titles():
    on = {c.id: c for c in _with(names=True).cells}
    off = {c.id: c for c in _with(names=False).cells}
    # row labels and column headers are always present, independent of names
    assert {"label:mapping", "header:primes"} <= set(on)
    assert {"label:mapping", "header:primes"} <= set(off)
    # the in-tile quantity captions appear only when names is on
    assert on["caption:mapping:primes"].text == "(temperament) mapping"
    assert not any(c.startswith("caption:") for c in off)


# --- the interval-vectors row (each column's intervals as vectors) ---

def test_interval_vectors_row_sits_between_quantities_and_mapping():
    cells = {c.id: c for c in _layout().cells}
    assert cells["label:vectors"].text == "interval vectors"
    assert "toggle:row:vectors" in cells  # collapsible like the other content rows
    assert cells["label:quantities"].y < cells["label:vectors"].y < cells["label:mapping"].y


def test_interval_vectors_show_targets_as_vectors():
    cells = {c.id: c for c in _layout().cells}
    # each target interval as a d-tall vector column: 2/1->[1,0,0], 3/2->[-1,1,0], 5/4->[-2,0,1]
    assert [cells[f"cell:vec:targets:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:vec:targets:2:{p}"].text for p in range(3)] == ["-1", "1", "0"]
    assert [cells[f"cell:vec:targets:6:{p}"].text for p in range(3)] == ["-2", "0", "1"]
    assert cells["cell:vec:targets:2:0"].x == cells["target:2"].x  # column on its target axis
    # the d components stack downward, one ROW_H apart
    assert cells["cell:vec:targets:0:1"].y - cells["cell:vec:targets:0:0"].y == spreadsheet.ROW_H


def test_interval_vectors_domain_primes_identity_is_deferred_to_identity_objects():
    # the domain primes as vectors over themselves are the d x d identity — an
    # "identity object" the grid won't show until the identity_objects setting is
    # built (the basis is already listed down the quantities spine). Until then the
    # primes column carries NOTHING at the interval-vectors row: no cells, ket marks,
    # separators, the enclosing [ ] bracket, fold toggle or caption.
    cells = {c.id for c in _with(names=True).cells}
    assert not any(c.startswith(("cell:vec:primes", "ebktop:vec:primes",
                                 "ebkangle:vec:primes", "sep:vec:primes",
                                 "bracket:vec:primes")) for c in cells)
    assert {"toggle:tile:vectors:primes", "caption:vectors:primes"}.isdisjoint(cells)


def test_interval_vectors_quantities_tile_shows_the_domain_basis_as_row_index():
    cells = {c.id: c for c in _layout().cells}
    # the quantities spine holds the domain basis (the d primes) as the vectors row's
    # row-index, stacked vertically — dual to the generators indexing the mapping rows
    assert [cells[f"basis:{p}"].text for p in range(3)] == ["2", "3", "5"]
    # boxed COL_W squares like the domain primes, centred in the wider spine column
    assert cells["basis:0"].w == spreadsheet.COL_W == cells["prime:0"].w
    gen0 = cells["gen:0"]  # the generators span the full spine; the basis is centred in it
    assert cells["basis:0"].x + cells["basis:0"].w / 2 == gen0.x + gen0.w / 2
    assert cells["basis:0"].y == cells["cell:comma:0:0"].y  # aligned with the top component
    assert cells["basis:1"].y - cells["basis:0"].y == spreadsheet.ROW_H  # stacked down its column


def test_interval_vectors_basis_controls_ride_the_rows_left_bus():
    # the basis fans HORIZONTALLY (one sub-row per prime); its domain controls ride the row's
    # LEFT bus — out to the left of the primes, the row mirror of the columns' top-bus controls:
    # a − on the bottom prime's branch point, a + on the stub one ROW_H below the stack, with the
    # left bar stretched down to reach it.
    lay = _layout()
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    plus, minus, bot = cells["basis_plus"], cells["basis_minus"], cells["basis:2"]
    left_bus = by_id["vbar:vectors:left"]
    assert minus.x == left_bus.pos  # − zone drops from the left-bus branch point (button at its edge)
    assert abs((minus.y + minus.h / 2) - by_id["h:vectors:2"].pos) < 0.51  # ...on the bottom prime's sub-row
    assert minus.x < cells["basis:2"].x  # ...out to the LEFT of the primes
    assert abs((plus.x + plus.w / 2) - left_bus.pos) < 0.51  # + centred on the left bus
    assert plus.y >= bot.y + bot.h  # ...below the whole stack (clear of the last box)
    assert abs((left_bus.start + left_bus.length) - (plus.y + plus.h / 2)) < 0.51  # bar reaches the +


def test_mapping_row_controls_ride_the_rows_left_bus():
    # the mapping fans like the basis (one sub-row per generator); its row ± ride the row's LEFT
    # bus, out to the left of the generator-ratio spine: a − on EACH generator's branch point (any
    # row removable, −r,+n), and a + on the stub below the stack (un-temper a comma, +r,−n), with
    # the left bar stretched down to reach it.
    lay = _layout()  # meantone, r = 2, n = 1
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    left_bus = by_id["vbar:mapping:left"]
    for i in range(2):  # a − per generator (unlike the domain −, which is last-only)
        minus = cells[f"map_minus:{i}"]
        assert minus.x == left_bus.pos  # − drops from the left-bus branch point
        assert abs((minus.y + minus.h / 2) - by_id[f"h:mapping:{i}"].pos) < 0.51  # on generator i's sub-row
        assert minus.x < cells["gen:0"].x  # ...out to the LEFT of the generator-ratio spine
    plus = cells["map_plus"]
    assert abs((plus.x + plus.w / 2) - left_bus.pos) < 0.51  # + centred on the left bus
    assert plus.y >= cells["gen:1"].y + cells["gen:1"].h  # ...below the last generator row
    assert abs((left_bus.start + left_bus.length) - (plus.y + plus.h / 2)) < 0.51  # bar reaches the +


def test_mapping_row_minus_gated_on_rank_and_plus_on_nullity():
    rank1 = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}
    assert "map_plus" in rank1 and "map_minus:0" not in rank1  # n>0 so a +, but can't drop the sole row
    ji = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))).cells}
    assert "map_plus" not in ji  # full rank: nothing tempered to un-temper
    assert {"map_minus:0", "map_minus:1", "map_minus:2"} <= ji  # ...but each generator is removable


def test_grid_builds_for_an_octave_less_temperament():
    # dropping the octave generator (the mapping-row −) can leave a temperament whose octave
    # tempers out; its generator tuning-range chart loses its I-beams, but the grid must still
    # build — the tuning solve used to crash computing the now-undefined diamond-tradeoff range.
    degenerate = service.remove_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))), 0)
    lay = spreadsheet.build(degenerate)  # no IndexError
    assert any(c.id == "gen:0" for c in lay.cells)  # the rank-1 grid rendered


def test_interval_vectors_basis_minus_is_absent_when_the_domain_cannot_shrink():
    base = service.from_mapping(((1,),))  # d == 1: removing the last prime is disallowed
    cells = {c.id for c in spreadsheet.build(base).cells}
    assert "basis_plus" in cells and "basis_minus" not in cells


# --- the commas column (the comma basis, the mapping's dual) ---

def _in_commas(cid):
    return cid.startswith(("comma:", "cell:comma:")) or cid.split(":")[0:2] in (
        ["tuning", "comma"], ["just", "comma"], ["retune", "comma"])


def test_commas_column_sits_between_primes_and_targets_with_its_comma_ratios():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:commas"].text == "commas"
    assert cells["comma:0"].text == "80/81"  # the syntonic comma, as-is from the dual
    # the commas band falls between domain primes and target intervals
    assert cells["header:primes"].x < cells["header:commas"].x < cells["header:targets"].x
    assert cells["prime:2"].x < cells["comma:0"].x < cells["target:0"].x


def test_comma_basis_renders_as_raw_vectors_in_the_interval_vectors_row():
    cells = {c.id: c for c in _layout().cells}
    # the raw comma basis lives in the interval-vectors row's commas column, d-tall;
    # the syntonic comma [4, -4, 1] reads top-to-bottom (prime 2, 3, 5) down its column
    assert cells["cell:comma:0:0"].text == "4"
    assert cells["cell:comma:1:0"].text == "-4"
    assert cells["cell:comma:2:0"].text == "1"
    c00 = cells["cell:comma:0:0"]
    assert c00.w == c00.h == spreadsheet.ROW_H  # square grid cells
    assert cells["cell:comma:1:0"].y == c00.y + c00.h  # stacked down its column
    assert c00.x == cells["comma:0"].x  # on the commas axis
    assert c00.y == cells["cell:vec:targets:0:0"].y  # top-aligned across the vectors row


def test_mapping_row_commas_show_the_mapped_comma_basis_vanishing():
    cells = {c.id: c for c in _layout().cells}
    # in the mapping row the comma basis is shown MAPPED through M — it vanishes to 0,
    # the whole point of the temperament (parallel to the mapped target interval list)
    assert cells["cell:mapped_comma:0:0"].text == "0"
    assert cells["cell:mapped_comma:1:0"].text == "0"
    # r-tall (one row per generator) and aligned with the mapped target list beside it
    assert cells["cell:mapped_comma:0:0"].y == cells["cell:mapped:0:0"].y
    assert cells["cell:mapped_comma:1:0"].y == cells["cell:mapping:1:0"].y
    assert cells["cell:mapped_comma:0:0"].x == cells["comma:0"].x  # on the commas axis
    # the raw comma basis is NOT here — it sits up in the (higher) interval-vectors row
    assert cells["cell:comma:0:0"].y < cells["cell:mapped_comma:0:0"].y


def test_comma_sizes_fill_the_tuning_family_rows():
    cells = {c.id: c for c in _layout().cells}
    # the comma vanishes in the temperament: its tempered size is ~0
    assert cells["tuning:comma:0"].text == "0.000"
    # ...but it has a real just size (the syntonic comma is ~21.5 cents)
    assert cells["just:comma:0"].text == "-21.506"
    assert cells["retune:comma:0"].text == "21.506"
    # comma tuning values share the comma column with the quantities-row ratio
    assert cells["tuning:comma:0"].x == cells["comma:0"].x


def test_damage_row_has_no_commas_tile():
    # the damage row exists only over the targets (the tuning's own column) — there is
    # NO comma damage tile; it was never in the mockup. Commas still carry tempered,
    # just and error sizes, but damage is a target interval quantity only.
    lay = _with(names=True, symbols=True, plain_text_values=True, charts=True)
    cells = {c.id for c in lay.cells}
    blocks = {b.id for b in lay.blocks}
    # the target damage tile is intact (the row still exists)...
    assert "damage:target:0" in cells and "block:damage:targets" in blocks
    # ...but nothing of a comma damage tile remains
    assert not any(c.startswith("damage:comma") for c in cells)  # no value cells
    assert "caption:damage:commas" not in cells                  # no name caption
    assert "symbol:damage:commas" not in cells                   # no symbol slot
    assert {"bracket:damage:commalist:l", "bracket:damage:commalist:r"}.isdisjoint(cells)
    assert "toggle:tile:damage:commas" not in cells              # no fold toggle
    assert "ptext:damage:commas" not in cells                    # no plain-text box
    assert "block:damage:commas" not in blocks                   # no grey panel


def test_weighting_on_adds_a_weight_row_over_the_targets():
    off = {c.id for c in _with(weighting=False).cells}
    on = {c.id: c for c in _with(weighting=True).cells}
    assert "weight:target:0" not in off  # no weight row unless weighting is on
    assert "weight:target:0" in on
    # one weight value per target interval, the scheme's per-target damage weight
    # at the grid's shared precision
    targets = service.target_interval_set(
        service.DEFAULT_TARGET_SPEC, service.standard_primes(3)
    )
    weights = service.interval_weights(
        ((1, 1, 0), (0, 1, 4)), service.DEFAULT_DOCUMENT_SCHEME, targets
    )
    assert len(weights) == 8
    assert on["weight:target:0"].text == service.cents(weights[0])
    assert on["weight:target:7"].text == service.cents(weights[7])


def test_weight_row_sits_between_retuning_and_damage():
    on = {c.id: c for c in _with(weighting=True).cells}
    # the weighting region computes prescaling -> complexity -> weight -> damage,
    # so the weight row lands just above damage (and below retuning)
    assert on["retune:target:0"].y < on["weight:target:0"].y < on["damage:target:0"].y


def test_weight_row_value_list_is_bracketed_like_the_other_tuning_lists():
    cells = {c.id: c for c in _with(weighting=True).cells}
    # a [ … ] list over the targets, like damage (the weight list it scales)
    assert cells["bracket:weight:l"].text == "[" and cells["bracket:weight:r"].text == "]"
    assert cells["bracket:weight:l"].x < cells["weight:target:0"].x < cells["bracket:weight:r"].x


def test_charts_on_adds_a_weight_bar_chart_over_the_targets():
    on = {c.id: c for c in _with(weighting=True, charts=True).cells}
    off = {c.id for c in _with(weighting=True, charts=False).cells}
    assert "chart:weight:targets" not in off  # no chart cell unless charts is on
    ch = on["chart:weight:targets"]
    assert ch.kind == "chart"
    assert len(ch.values) == 8  # one bar per target interval (the weight list)
    assert all(v >= 0 for v in ch.values)  # weights are non-negative
    assert ch.y + ch.h <= on["weight:target:0"].y  # the chart sits above its values


def test_weight_row_carries_its_symbol_and_caption():
    on = {c.id: c for c in _with(weighting=True, symbols=True, names=True).cells}
    # 𝒘 (bold italic, the same glyph the damage equivalence's 𝒘 factor uses)
    assert on["symbol:weight:targets"].text == "𝒘"
    assert spreadsheet.EQUIVALENCES[("damage", "targets")].endswith("𝒘")  # same 𝒘
    assert on["caption:weight:targets"].text == "target interval weight list"


def test_weight_caption_mnemonic_underlines_its_symbol_letter():
    on = {c.id: c for c in _with(weighting=True, names=True, mnemonics=True).cells}
    cap = on["caption:weight:targets"]
    # the 'w' of "weight" is underlined (its symbol 𝒘), like damage underlines "damage"
    assert cap.underlines == ((cap.text.index("weight"), 1),)


def test_weighting_on_adds_a_complexity_row_over_every_interval_column():
    off = {c.id for c in _with(weighting=False).cells}
    on = {c.id: c for c in _with(weighting=True).cells}
    assert "complexity:target:0" not in off  # no complexity row unless weighting is on
    mapping = ((1, 1, 0), (0, 1, 4))
    scheme = service.DEFAULT_TUNING_SCHEME
    targets = service.target_interval_set(service.DEFAULT_TARGET_SPEC, service.standard_primes(3))
    tx = service.interval_complexities(mapping, scheme, targets)
    assert on["complexity:target:0"].text == service.cents(tx[0])
    assert on["complexity:target:7"].text == service.cents(tx[7])
    # the comma basis interval complexity list, over the commas column
    cx = service.interval_complexities(mapping, scheme, ("80/81",))
    assert on["complexity:comma:0"].text == service.cents(cx[0])
    # the domain prime complexity map, over the primes: the complexity of each prime
    px = service.interval_complexities(mapping, scheme, ("2/1", "3/1", "5/1"))
    assert on["complexity:prime:0"].text == service.cents(px[0])  # log2(2) = 1.000
    assert on["complexity:prime:2"].text == service.cents(px[2])  # log2(5) = 2.322


def test_complexity_row_sits_between_retuning_and_weight():
    on = {c.id: c for c in _with(weighting=True).cells}
    assert on["retune:target:0"].y < on["complexity:target:0"].y < on["weight:target:0"].y


def test_complexity_over_primes_is_a_map_the_rest_are_lists():
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True}, interest=((-3, 2, 0),),
    ).cells}
    # the domain-prime complexity is a covector ⟨ … ] (a map), like the tuning map
    assert cells["bracket:complexity:map:l"].text == "⟨" and cells["bracket:complexity:map:r"].text == "]"
    # the comma / target complexities are plain [ … ] lists
    assert cells["bracket:complexity:commalist:l"].text == "["
    assert cells["bracket:complexity:list:l"].text == "[" and cells["bracket:complexity:list:r"].text == "]"
    # ...but the interest complexity drops its bracket — the whole interest column is bare
    assert not any(c.startswith("bracket:complexity:ilist") for c in cells)
    # the interest prescaling stands alone too — per-column ket ``[ … ⟩`` marks (ebktop ⌐
    # at top + ebkangle ∨ at bottom), no outer ``[ … ]`` wrap, like the other interest-row
    # standalone-columns shapes. The comma/target/held prescaling tiles get the same
    # per-column marks plus an outer bracket frame (see
    # test_prescaling_matrices_have_outer_brackets_and_per_column_marks).
    assert {"ebktop:prescaling:interest:0", "ebkangle:prescaling:interest:0"} <= set(cells)
    assert "ebkbrace:prescaling:interest:0" not in cells  # NOT a curly close — the ket's angle foot ⟩
    assert "bracket:prescaling:interest:l" not in cells  # standalone, no outer wrap


def test_complexity_is_not_charted():
    # only retuning/weight/damage grow bar charts; complexity does not (the mockup
    # shows the chart in the weight box, not the complexity boxes)
    on = {c.id for c in _with(weighting=True, charts=True).cells}
    assert not any(c.startswith("chart:complexity") for c in on)


def test_complexity_row_carries_its_symbol_and_captions():
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True, "symbols": True, "names": True},
        interest=((-3, 2, 0),),
    ).cells}
    assert cells["symbol:complexity:targets"].text == "𝒄"  # only the target list carries the symbol
    assert cells["caption:complexity:primes"].text == "domain prime complexity map"
    assert cells["caption:complexity:commas"].text == "comma basis interval complexity list"
    assert cells["caption:complexity:targets"].text == "target interval complexity list"
    # the interest column's weighting-row captions are the mockup's descriptive names
    assert cells["caption:complexity:interest"].text == "interval complexities"
    assert cells["caption:prescaling:interest"].text == "complexity prescaled intervals"


def test_complexity_caption_mnemonic_underlines_its_symbol_letter():
    cells = {c.id: c for c in _with(weighting=True, names=True, mnemonics=True).cells}
    cap = cells["caption:complexity:targets"]
    # the 'c' of "complexity" is underlined (its symbol 𝒄)
    assert cap.underlines == ((cap.text.index("complexity"), 1),)


def test_weighting_on_adds_the_complexity_prescaling_matrix_over_the_primes():
    on = {c.id: c for c in _with(weighting=True).cells}
    off = {c.id for c in _with(weighting=False).cells}
    assert "cell:prescaling:primes:0:0" not in off  # no prescaling matrix unless weighting is on
    pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), service.DEFAULT_TUNING_SCHEME)
    # a d×d diagonal matrix over the primes: the prescaler weights on the diagonal (the
    # editable prescalercell — the user types overrides here), 0 off it (a plain tval since
    # 𝐿 is diagonal, no point editing what's pinned to zero).
    assert on["cell:prescaling:primes:0:0"].kind == "prescalercell"
    assert on["cell:prescaling:primes:0:0"].text == "1"               # log2(2) = 1, shown bare
    assert on["cell:prescaling:primes:1:1"].text == service.cents(pre[1])  # log2(3) = 1.585
    assert on["cell:prescaling:primes:2:2"].text == service.cents(pre[2])  # log2(5) = 2.322
    assert on["cell:prescaling:primes:0:1"].kind == "tval"             # off-diagonal stays tval
    assert on["cell:prescaling:primes:0:1"].text == "0"               # off-diagonal entry
    # column p sits under prime p; rows stack one ROW_H apart (a d-tall matrix)
    assert on["cell:prescaling:primes:0:0"].x == on["prime:0"].x
    assert on["cell:prescaling:primes:1:1"].x == on["prime:1"].x
    assert on["cell:prescaling:primes:1:0"].y == on["cell:prescaling:primes:0:0"].y + spreadsheet.ROW_H


def test_prescaling_tiles_carry_their_per_tile_symbols_and_equivalences():
    # the bare prescaler tile keeps the abstract symbol 𝑋 with its concrete equivalence — the
    # active prescaler IS the log-prime matrix, so "𝑋 = 𝐿". Everywhere 𝑋 further appears (the
    # product tiles) it's written with the concrete 𝐿: 𝐿C / 𝐿D / 𝐿T / 𝐿H, which print no "= …".
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        # ``optimization`` brings the held column out (held lives in the optimization layer);
        # without it the prescaling/held tile would be silently absent and that assertion
        # would skip rather than verify the symbol/equivalence wiring.
        {**settings.defaults(), "weighting": True, "optimization": True,
         "symbols": True, "equivalences": True},
        held_vectors=((-1, 1, 0),),  # 3/2 held, so the held column appears
    )
    on = {c.id: c for c in lay.cells}
    # bare prescaler tile: the abstract 𝑋 with its concrete equivalence (the symbol line is unchanged)
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
    # product tiles: the concrete 𝐿, no "= …" — they're already the matrix
    assert on["symbol:prescaling:commas"].text == "𝐿C"
    assert on["symbol:prescaling:targets"].text == "𝐿T"
    assert on["symbol:prescaling:held"].text == "𝐿H"


def test_non_log_prime_prescaler_stays_generic_X_named_in_the_equivalence():
    # when the prescaler is NOT the log-prime matrix it keeps the generic placeholder 𝑋
    # everywhere — the products read 𝑋C / 𝑋T / 𝑋H, not the concrete matrix. The concrete
    # form surfaces only in the bare tile's equivalence: 𝐼 for the identity (count) scheme.
    scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "identity")
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True, "optimization": True,
         "symbols": True, "names": True, "equivalences": True},
        tuning_scheme=scheme, held_vectors=((-1, 1, 0),),
    )
    on = {c.id: c for c in lay.cells}
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐼"   # generic symbol, concrete equivalence
    assert on["symbol:prescaling:commas"].text == "𝑋C"     # product keeps the generic 𝑋
    assert on["symbol:prescaling:targets"].text == "𝑋T"
    assert on["symbol:prescaling:held"].text == "𝑋H"
    # the NAME gains its "= log-prime matrix" equivalence ONLY when 𝑋 = 𝐿 — not here
    assert on["caption:prescaling:primes"].text == "complexity prescaler"


def test_prime_prescaler_names_diag_p_in_the_equivalence_not_the_projection_letter():
    # the prime (sopfr) prescaler is the guide's diag(𝒑), the diagonal matrix of primes —
    # NOT a bare 𝑃, which the guide reserves for the projection matrix (P = GM). It surfaces
    # in the bare tile's equivalence; the symbol itself stays the generic 𝑋 ("diag(" and the
    # prime list 𝒑 render per the guide). The product tiles keep the generic 𝑋, too.
    scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "prime")
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True, "optimization": True,
         "symbols": True, "equivalences": True},
        tuning_scheme=scheme, held_vectors=((-1, 1, 0),),
    )
    on = {c.id: c for c in lay.cells}
    assert on["symbol:prescaling:primes"].text == "𝑋 = diag(𝒑)"
    assert on["symbol:prescaling:commas"].text == "𝑋C"
    assert on["symbol:prescaling:targets"].text == "𝑋T"


def test_log_prime_prescaler_name_gains_the_equivalence():
    # when 𝑋 = 𝐿, the NAME (caption) reads "complexity prescaler = log-prime matrix" with the
    # equivalences layer on — paralleling the symbol line's OWN, UNCHANGED "𝑋 = 𝐿".
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True, "symbols": True, "names": True,
         "equivalences": True}
    on = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"  # the symbol line is unchanged
    assert on["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"
    # without the equivalences layer the name is just the plain caption
    on2 = {c.id: c for c in spreadsheet.build(base, {**s, "equivalences": False}).cells}
    assert on2["caption:prescaling:primes"].text == "complexity prescaler"


def test_prescaler_symbol_never_mixes_L_and_X_within_a_tile():
    # regression: the "complexity prescaled generator detempering" tile read 𝐿D as its big
    # symbol but 𝑋𝐝 over its columns. Under the default (log-prime) scheme the prescaler IS
    # the log-prime matrix, so BOTH must use 𝐿 — the symbol and the column headers in lockstep.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "symbols": True, "weighting": True,
         "generator_detempering": True}
    on = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert on["symbol:prescaling:detempering"].text == "𝐿D"          # the tile's big symbol
    assert on["matlabel:col:prescaling:detempering:0"].text == "𝐿𝐝₁"  # its column headers — same 𝐿


def test_custom_prescaler_diagonal_keeps_the_generic_symbol():
    # typing a custom prescaler diagonal makes it no longer THE log-prime matrix, so the symbol
    # stays the generic 𝑋 everywhere (no 𝐿 promotion, no "= log-prime matrix") — the typed
    # diagonal speaks for itself, so the bare tile prints no equivalence.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "symbols": True, "equivalences": True,
         "weighting": True, "generator_detempering": True}
    on = {c.id: c for c in spreadsheet.build(
        base, s, custom_prescaler=(1.0, 1.5, 2.0)).cells}
    assert on["symbol:prescaling:primes"].text == "𝑋"               # generic, no "= …"
    assert on["symbol:prescaling:commas"].text == "𝑋C"              # generic product
    assert on["matlabel:col:prescaling:detempering:0"].text == "𝑋𝐝₁"
    assert on["matlabel:row:prescaling:primes:0"].text == "𝒙₁"


def test_returning_the_prescaler_to_its_shown_log_prime_diagonal_restores_the_L_awareness():
    # regression: deviating 𝑋 from 𝐿 then typing the SHOWN log-prime values back must RESTORE the
    # 𝑋 = 𝐿 awareness — symbol equivalence, concrete-𝐿 products, and the name equivalence — even
    # though the stored diagonal carries the rounded shown values (build derives the awareness from
    # service.displayed_prescaler_name at display precision, not "custom_prescaler is None").
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    scheme = f"TILT {service.DEFAULT_TUNING_SCHEME}"
    shown = tuple(float(service.prescale_text(v))  # the rounded diagonal a round-trip cell edit stores
                  for v in service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), scheme))
    s = {**settings.defaults(), "weighting": True, "symbols": True, "names": True, "equivalences": True}
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme, custom_prescaler=shown).cells}
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
    assert on["symbol:prescaling:commas"].text == "𝐿C"
    assert on["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"


def test_complexity_symbol_and_mnemonic_only_on_the_target_list():
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True, "symbols": True, "names": True, "mnemonics": True},
        interest=((-3, 2, 0),),
    )
    on = {c.id: c for c in lay.cells}
    # only the target interval complexity list carries the 𝒄 symbol and its mnemonic underline
    assert on["symbol:complexity:targets"].text == "𝒄"
    assert on["caption:complexity:targets"].underlines != ()
    # the domain-prime map, comma list and interest complexity carry neither
    for col in ("primes", "commas", "interest"):
        assert f"symbol:complexity:{col}" not in on, col
        assert on[f"caption:complexity:{col}"].underlines == (), col


def test_prescaling_row_spans_commas_and_targets_with_L_scaled_vectors():
    lay = _with(weighting=True)
    on = {c.id: c for c in lay.cells}
    blocks = {b.id for b in lay.blocks}
    pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)))  # (1, 1.585, 2.322)
    _t = service.prescale_text
    # over the commas: L applied to the comma basis 80/81 = [4,-4,1], a d-tall column rendered
    # as int/frac gridded cells (its taxicab norm 4+6.34+2.322 is the comma's complexity)
    for i, comp in enumerate((4, -4, 1)):
        cell = on[f"cell:prescaling:commas:{i}:0"]
        assert cell.text == _t(pre[i] * comp)
        assert cell.kind == "tval"
    # the comma + target prescaling tiles exist with panels, and their EBK is per-column
    # ket ``[ … ⟩`` (ebktop:…:{c} + ebkangle:…:{c}) inside outer left/right ``[ … ]``
    # brackets (see test_prescaling_matrices_have_outer_brackets_and_per_column_marks for
    # the outer frame).
    assert {"block:prescaling:commas", "block:prescaling:targets"} <= blocks
    assert {"ebktop:prescaling:commas:0", "ebkangle:prescaling:commas:0",
            "ebktop:prescaling:targets:0", "ebkangle:prescaling:targets:0"} <= set(on)
    assert "cell:prescaling:targets:0:0" in on  # the target column is populated too


def test_prescaling_plain_text_shows_the_same_numbers_as_the_grid():
    # the plain-text value and the gridded cells are two views of ONE matrix, so the
    # string must read off the SAME numbers the grid shows — bare whole numbers and all
    # (the prescaler diagonal is mostly 0 and 1), never padded to "0.000"/"1.000". The bare
    # prescaler 𝐿 is a covector stack — per-row ``⟨ … ]`` inside the asymmetric outer
    # ``[ … ⟩`` (mirroring the mapping's ``[ … }`` but with the angle ⟩ instead of the curly
    # }). Every 𝐿·basis product (𝐿C / 𝐿T / 𝐿H) is a matrix of prescaled VECTORS — per-column
    # ket ``[ … ⟩`` inside the symmetric outer ``[ … ]``.
    import re
    cells = {c.id: c for c in _with(plain_text_values=True, weighting=True).cells}
    vecbr = {"primes": "⟨]", "commas": "[⟩", "targets": "[⟩"}  # per-vector bracket pair
    outer = {"primes": "[⟩", "commas": "[]", "targets": "[]"}
    for group in ("primes", "commas", "targets"):
        coords = [re.fullmatch(rf"cell:prescaling:{group}:(\d+):(\d+)", cid)
                  for cid in cells]
        coords = [(int(m.group(2)), int(m.group(1))) for m in coords if m]  # (col, row)
        ncols = max(c for c, _ in coords) + 1
        d = max(r for _, r in coords) + 1
        vo, vc = vecbr[group]
        vecs = [vo + " ".join(cells[f"cell:prescaling:{group}:{i}:{c}"].text
                              for i in range(d)) + vc
                for c in range(ncols)]
        op, cl = outer[group]
        assert cells[f"ptext:prescaling:{group}"].text == f"{op}{' '.join(vecs)}{cl}", group


def test_weighting_rows_show_their_units_line_when_units_on():
    cells = {c.id: c for c in _with(weighting=True, units=True).cells}
    # the per-box "units:" line below each caption, per the mockup
    assert cells["units:prescaling:primes"].text == "units: oct/p"   # the prescaler matrix L
    assert cells["units:prescaling:targets"].text == "units: oct"     # L applied to a vector set
    assert cells["units:complexity:primes"].text == "units: (C)/p"    # the domain-prime complexity map
    assert cells["units:complexity:targets"].text == "units: (C)"     # a complexity list
    assert cells["units:weight:targets"].text == "units: (C)"


def test_weighting_rows_have_units_column_tiles_when_domain_units_on():
    cells = {c.id: c for c in _with(weighting=True, domain_units=True).cells}
    # the units-column (spine) marginal label per weighting row, like the tuning rows' ¢/
    assert cells["ucol:prescaling:0"].text == "oct/"   # one per matrix row (d-tall)
    assert cells["ucol:complexity"].text == "(C)/"
    assert cells["ucol:weight"].text == "(C)/"


def test_weighting_rows_render_a_plain_text_box_when_plain_text_on():
    cells = {c.id for c in _with(weighting=True, plain_text_values=True).cells}
    assert {"ptext:weight:targets", "ptext:complexity:primes", "ptext:complexity:targets",
            "ptext:prescaling:primes"} <= cells


def test_prescaling_row_sits_between_retuning_and_complexity():
    on = {c.id: c for c in _with(weighting=True).cells}
    assert on["retune:prime:0"].y < on["cell:prescaling:primes:0:0"].y < on["complexity:prime:0"].y


def test_every_present_row_and_column_has_a_gridline():
    # structural guarantee (derived from the live row_y/col_x, not a hand-maintained list):
    # no present row or column can be missing its gridline — the bug that left the weighting
    # rows bare. Exercise the busiest grid (weighting + its controls + an interest column).
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True, "alt_complexity": True},
        interest=((-3, 2, 0),),
    )
    line_ids = {ln.id for ln in lay.lines}
    rows = {c.id.split("label:", 1)[1] for c in lay.cells if c.id.startswith("label:")}
    for key in rows:
        if key in spreadsheet.FRAMED_ROWS:
            assert f"h:{key}:0" in line_ids, f"matrix row {key!r} has no fanned gridline"
        else:
            assert f"h:{key}" in line_ids, f"row {key!r} has no gridline"
    cols = {c.id.split("header:", 1)[1] for c in lay.cells if c.id.startswith("header:")}
    for key in cols:
        assert f"trunk:{key}" in line_ids, f"column {key!r} has no gridline"


def test_prescaling_matrices_have_outer_brackets_and_per_column_marks():
    # The bare prescaler 𝐿 reads exactly like the mapping in plain text — outer
    # ``[ … ⟩`` over per-row ``⟨ … ]`` — so its gridded EBK uses the SAME matrix_frame +
    # per-row bracket pattern the mapping does, just with the angle ⟩ (ebkangle) at the
    # bottom-span instead of the curly } (ebkbrace).
    #
    # The 𝐿·basis product matrices (𝐿C / 𝐿D / 𝐿T / 𝐿H) are column-wise: per-column ket
    # ``[ … ⟩`` marks (top = ebktop ⌐ square open, foot = ebkangle ∨ angle close on the
    # bottom of the column) inside outer ``[ … ]`` left/right brackets.
    on = {c.id: c for c in _with(weighting=True).cells}
    # bare 𝐿: mapping-style — ebktop + ebkangle spanning the matrix top/bottom, MAP_BRACKETS
    # ⟨ … ] per row, and NO outer left/right brackets (the spans replace them)
    assert on["ebktop:prescaling"].kind == "ebktop"
    assert on["ebkangle:prescaling"].kind == "ebkangle"
    assert on["bracket:prescaling:row:0:l"].text == "⟨"
    assert on["bracket:prescaling:row:0:r"].text == "]"
    assert "bracket:prescaling:l" not in on  # no outer left/right — matrix_frame spans top/bot
    assert "bracket:prescaling:r" not in on
    assert "ebkbrace:prescaling" not in on  # NOT a curly close at bottom — angle close ⟩
    # product tiles: symmetric outer left/right [ ], per-column ket marks — square top + angle foot
    for bid in ("prescaling:commas", "prescaling:targets"):
        assert on[f"bracket:{bid}:l"].text == "[" and on[f"bracket:{bid}:r"].text == "]"
        assert on[f"ebktop:{bid}:0"].kind == "ebktop"
        assert on[f"ebkangle:{bid}:0"].kind == "ebkangle"
        assert f"ebkbrace:{bid}:0" not in on  # NOT a curly close — the ket's angle foot ⟩
    # the mapping matrix keeps its single top bracket + bottom curly brace (its mapped lists
    # ARE generator coords, so the } close is correct there)
    assert on["ebktop:primes"].kind == "ebktop" and on["ebkbrace:primes"].kind == "ebkbrace"


def test_outer_matrix_frame_hugs_the_cells_leaving_subrow_labels_outside():
    # When the primes column footprint is widened past its content — here by the box-𝐋
    # prescaler controls that alt. complexity adds beneath the prescaling matrix — the
    # spanning top/bottom frame of the mapping and complexity-prescaler matrices must
    # still hug the CELL matrix, exactly like the per-row ⟨ … ] brackets do (both via
    # content_box). Otherwise the frame drifts left over the subrow labels (𝒎ᵢ / 𝒙ᵢ),
    # swallowing them, and overhangs the cells on the right. Per the mockup the labels
    # sit OUTSIDE the frame, to its left.
    cells = {c.id: c for c in _with(weighting=True, alt_complexity=True, symbols=True).cells}
    for top_id, foot_id, label_id, left_id, right_id in (
        ("ebktop:primes", "ebkbrace:primes", "matlabel:row:mapping:primes:0",
         "bracket:map:0:l", "bracket:map:0:r"),
        ("ebktop:prescaling", "ebkangle:prescaling", "matlabel:row:prescaling:primes:0",
         "bracket:prescaling:row:0:l", "bracket:prescaling:row:0:r"),
    ):
        top, foot = cells[top_id], cells[foot_id]
        label, left, right = cells[label_id], cells[left_id], cells[right_id]
        # the subrow label sits fully to the LEFT of the outer frame (outside it)
        assert label.x + label.w <= top.x
        # the frame's left and right edges align with the per-row brackets — it hugs the
        # cell matrix, not the wider grey footprint (top and bottom spans stay in lockstep)
        assert top.x == left.x == foot.x
        assert top.x + top.w == right.x + right.w == foot.x + foot.w


def test_prescaling_matrix_carries_its_symbol_and_caption():
    cells = {c.id: c for c in _with(weighting=True, symbols=True, names=True).cells}
    # the bare prescaler matrix is the abstract symbol 𝑋 (math italic, like 𝑀); with no
    # equivalences layer the name is just the plain caption
    assert cells["symbol:prescaling:primes"].text == "𝑋"
    assert cells["caption:prescaling:primes"].text == "complexity prescaler"


def test_complexity_prescaler_caption_mnemonic_marks_the_x_in_complexity():
    cells = {c.id: c for c in _with(weighting=True, names=True, mnemonics=True).cells}
    cap = cells["caption:prescaling:primes"]
    # the prescaler's symbol 𝑋 has no word-initial X in "complexity prescaler"; unlike the
    # word-initial mnemonics, it marks the x mid-word in "compleXity"
    assert cap.text == "complexity prescaler"
    assert cap.underlines == ((cap.text.index("x"), 1),)


def test_weighting_is_implemented_now_that_its_region_builds():
    # the weighting toggle builds content (the prescaling/complexity/weight rows), so the
    # Show panel must offer it live rather than greyed out
    assert "weighting" in settings.IMPLEMENTED


def test_presets_adds_the_prescaler_chooser_under_the_prescaling_tile():
    # the prescaler is a preset (like temperament / tuning / target), gated on PRESETS —
    # not the shelved alt_complexity. It rides under the prescaling matrix tile (box 𝐋), which
    # exists only while weighting is on; the temperament boxes own the primes column it sits in.
    off = {c.id for c in _with(weighting=True, presets=False).cells}
    on = {c.id: c for c in _with(weighting=True, presets=True).cells}
    assert "preset:prescaler" not in off  # no chooser unless presets is on
    sel = on["preset:prescaler"]
    assert sel.kind == "preset"
    assert sel.text == "log-prime"  # the default scheme's prescaler
    # it rides below the prescaling matrix, seated one inner pad into the primes column (like the
    # other presets, the dropdown sits inside a tile-spanning box at BOX_INNER off the edge)
    assert sel.y > on["cell:prescaling:primes:2:2"].y
    assert sel.x == on["header:primes"].x + spreadsheet.BOX_INNER
    # gone without the prescaling tile (weighting off) or its column (temperament boxes off)
    assert "preset:prescaler" not in {c.id for c in _with(weighting=False, presets=True).cells}
    assert "preset:prescaler" not in {
        c.id for c in _with(weighting=True, presets=True, temperament_boxes=False).cells}


def test_prescaler_chooser_shows_dash_when_a_custom_diagonal_deviates():
    # like the tuning chooser, the prescaler preset falls back to "-" (empty text) when a
    # manual prescaler edit (the custom_prescaler override) deviates from the scheme's diagonal
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["weighting"] = True, True
    named = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert named["preset:prescaler"].text == "log-prime"  # the scheme's prescaler, no override
    devi = {c.id: c for c in spreadsheet.build(base, s, custom_prescaler=(1.0, 9.9, 2.322)).cells}
    assert devi["preset:prescaler"].text == ""  # off the named list -> the "-" placeholder


def test_box_c_complexity_dropdown_shows_with_weighting_lp_only_until_alt_complexity():
    # box 𝒄's predefined-complexities dropdown shows with WEIGHTING alone — it no longer waits on
    # the shelved alt_complexity. Until alt-complexities are un-shelved it offers ONLY the current
    # complexity (lp for every scheme today), so the user can't pick an unimplemented complexity;
    # turning alt_complexity on restores the full preset list (+ the inert "custom").
    on = {c.id: c for c in _with(weighting=True).cells}  # weighting on, alt_complexity OFF (shelved)
    ctrl = on["control:complexity"]
    assert ctrl.kind == "control_select"
    # the dropdown shows the friendly display name (abbreviation first, expansion in parens) —
    # for the default scheme (log-prime taxicab) that's "lp (log-product)"
    assert ctrl.text == "lp (log-product)"
    assert ctrl.values == ("lp (log-product)",)  # lp-only while alt-complexities are shelved
    # the master chooser sits below the complexity list (box 𝒄), at the targets-column left edge
    assert ctrl.y > on["complexity:target:0"].y
    assert ctrl.x == on["header:targets"].x
    # un-shelving alt_complexity restores the full preset list + custom
    full = {c.id: c for c in _with(weighting=True, alt_complexity=True).cells}
    assert full["control:complexity"].values == tuple(service.COMPLEXITY_DISPLAYS.values()) + ("custom",)


def test_box_c_lays_out_with_q_and_dual_q_norm_power_fields():
    # box 𝒄 lays its three controls left-to-right: [predefined complexities ▼] | q | dual(q),
    # each with a caption beneath. It shows with WEIGHTING alone (no alt_complexity); the q (norm
    # power) and dual(q) fields follow the optimization box's value-over-symbol-over-caption pattern
    # (the 𝑝 / "optimization power" style); the dropdown has just a caption (no symbol slot).
    # dual(q) needs an all-interval scheme.
    on = {c.id: c for c in _with(scheme="minimax-S", weighting=True, all_interval=True).cells}
    # the predefined-complexities dropdown carries its caption HUGGING its bottom (rather than
    # bottom-aligned with the q/dual captions further down the row)
    assert on["caption:complexity"].kind == "caption"
    assert on["caption:complexity"].text == "predefined complexities"
    assert on["caption:complexity"].y == on["control:complexity"].y + on["control:complexity"].h
    # the q norm-power field: an editable powerinput (white box) styled like the optimization
    # power 𝑝 — the wiring (typing a new q to drive the norm) comes later. Default taxicab => 1.
    assert on["control:q"].kind == "powerinput"
    assert on["control:q"].text == "1"
    assert on["control:q"].x > on["control:complexity"].x  # to the RIGHT of the dropdown
    assert on["control:q"].y == on["control:complexity"].y  # same row
    assert on["symbol:q"].text == "𝑞"  # math italic q, matching 𝑝 on the optimization power
    assert on["symbol:q"].y > on["control:q"].y  # symbol BELOW the value (optimization-box style)
    assert on["caption:q"].text == "interval complexity norm power"
    assert on["caption:q"].y > on["symbol:q"].y  # caption BELOW the symbol
    # the dual(q) display: the dual norm power, rendered through the SAME powerinput path as q
    # so ∞ sits at the same visual size as the q numeral (the on_power_change handler no-ops here)
    assert on["control:dual"].kind == "powerinput"
    assert on["control:dual"].text == "∞"  # the dual of taxicab (q=1) is ∞
    assert on["control:dual"].x > on["control:q"].x
    assert on["symbol:dual"].text == "dual(𝑞)"  # the math italic q sits inside the dual-of-q label
    assert on["caption:dual"].text == "dual norm power"
    # the q and dual(q) captions sit at the same y (one tidy row); the dropdown's caption hugs
    # higher up against the dropdown's bottom, so it is ABOVE that row
    assert on["caption:q"].y == on["caption:dual"].y
    assert on["caption:complexity"].y < on["caption:q"].y
    # the old taxicab/Euclidean dropdown is gone — its look is replaced by the q field (mockup)
    assert "control:norm" not in on


def test_dual_q_shows_only_when_the_scheme_is_all_interval():
    # dual(q) is gated on the all-interval CHECKBOX (is_all_interval), NOT the show-panel entry:
    # an all-interval scheme renders dual(q); a target-based scheme hides it. The q field and the
    # predefined-complexities dropdown show with WEIGHTING regardless of all-interval — only the
    # dual power is gated.
    on_all = {c.id for c in _with(scheme="minimax-S", weighting=True).cells}
    assert {"control:dual", "symbol:dual", "caption:dual"} <= on_all
    on_tilt = {c.id for c in _with(scheme="TILT minimax-S", weighting=True).cells}
    assert not ({"control:dual", "symbol:dual", "caption:dual"} & on_tilt)
    assert {"control:q", "control:complexity"} <= on_tilt  # q + dropdown show regardless of all-interval


def test_all_interval_show_entry_adds_a_checkbox_to_the_target_controls():
    # the show-panel "all-interval" entry ALONE adds an "all-interval" checkbox to the target-
    # interval-list controls (it does NOT need the target chooser / presets): an OPTION_BOX_PX
    # square over an "all-interval" caption. It reflects whether the scheme targets every interval —
    # the default scheme is target-based, so it reads UNCHECKED; an all-interval scheme reads checked.
    off = {c.id for c in _with().cells}  # entry off (default)
    assert "control:all_interval" not in off and "caption:all_interval" not in off
    on = {c.id: c for c in _with(all_interval=True).cells}  # entry on, default (target-based) scheme
    chk = on["control:all_interval"]
    assert chk.kind == "control_check"
    assert chk.text == ""  # the square only — "all-interval" is a caption beneath
    assert chk.checked is False  # all-interval OFF by default (the default scheme is target-based)
    cap = on["caption:all_interval"]
    assert cap.kind == "caption" and cap.text == "all-interval"
    assert abs((chk.x + chk.w / 2) - (cap.x + cap.w / 2)) < 1  # square centred above its caption
    assert cap.y == chk.y + chk.h  # the caption hugs the square's bottom
    # an all-interval scheme reads the box checked
    on_ai = {c.id: c for c in _with(scheme="minimax-S", all_interval=True).cells}
    assert on_ai["control:all_interval"].checked is True


def test_all_interval_removes_all_redundant_target_tiles():
    # all-interval (Tₚ = I) drops every target-column list that just re-expresses an existing column:
    # mapped 𝑀T→𝑀, prescaled 𝐿T→𝐿, and the size/error lists 𝐚→𝒕, 𝐨→𝒋, 𝐞→𝒓. Each tile goes FULLY
    # (its grey panel too — never a blank box). The kept target tiles — the prime-proxy list, the
    # complexity, weight and damage — stay.
    removed = ["block:mapped", "block:prescaling:targets", "block:tuning:targets",
               "block:just:targets", "block:retune:targets"]
    based = {b.id for b in _with(scheme="TILT minimax-S", weighting=True).blocks}  # weighting reveals prescaling/complexity/weight
    allint = {b.id for b in _with(scheme="minimax-S", weighting=True).blocks}
    for bid in removed:
        assert bid in based, bid       # present when target-based
        assert bid not in allint, bid  # fully removed (panel and all) when all-interval
    assert {"block:vec:targets", "block:complexity:targets", "block:weight:targets",
            "block:damage:targets"} <= allint  # the kept target tiles remain


def test_all_interval_relabels_the_optimization_objective():
    # the optimization objective ⟪𝐝⟫ₚ is the minimized total damage; when all-interval that quantity
    # IS the retuning magnitude ‖𝒓𝐿⁻¹‖ at the dual norm power, so the symbol relabels with dual(q)
    # as the norm subscript — a PLAIN subscript (SUB_*) so the function name "dual" stays upright and
    # only the math-italic 𝑞 slants. A target-based scheme keeps ⟪𝐝⟫ₚ.
    based = {c.id: c for c in _with(scheme="TILT minimax-S", optimization=True).cells}
    assert based["optimization:objective:symbol"].text == "⟪𝐝⟫ₚ"
    allint = {c.id: c for c in _with(scheme="minimax-S", optimization=True).cells}
    expected = "‖𝒓𝐿⁻¹‖" + spreadsheet.SUB_OPEN + "dual(𝑞)" + spreadsheet.SUB_CLOSE
    assert allint["optimization:objective:symbol"].text == expected


def test_all_interval_relabels_the_target_list_as_prime_proxy():
    # per the Guide, all-interval relabels the target list: symbol T → Tₚ, equivalence = 𝐼 (the
    # math-italic identity, per the Guide's conventions), and the lowercase name "prime proxy
    # target interval list" — no hyphen in "target interval" (this app never capitalizes names).
    # Target-based keeps T / "target interval list".
    based = {c.id: c for c in _with(scheme="TILT minimax-S", symbols=True, equivalences=True).cells}
    assert based["symbol:vectors:targets"].text == "T"  # no equivalence tail when target-based
    assert based["caption:vectors:targets"].text == "target interval list"
    allint = {c.id: c for c in _with(scheme="minimax-S", symbols=True, equivalences=True).cells}
    assert allint["symbol:vectors:targets"].text == "Tₚ = 𝐼"  # symbol + math-italic equivalence tail
    assert allint["caption:vectors:targets"].text == "prime proxy target interval list"


def test_all_interval_mnemonics_underline_the_prime_proxy_p_subscript():
    # the all-interval target list's symbol is Tₚ, so its caption "prime proxy target interval list"
    # underlines the symbol's letters: the base T marks the t of "target" (as the target-based list
    # does), and the ₚ subscript marks BOTH p's it stands for — "prime" and "proxy".
    based = {c.id: c for c in _with(scheme="TILT minimax-S", names=True, mnemonics=True).cells}
    based_cap = based["caption:vectors:targets"]
    assert based_cap.underlines == ((based_cap.text.index("target"), 1),)  # just the T's "target"
    allint = {c.id: c for c in _with(scheme="minimax-S", names=True, mnemonics=True).cells}
    cap = allint["caption:vectors:targets"]
    assert cap.text == "prime proxy target interval list"
    # the t of target plus BOTH p's (prime, proxy) — order-independent
    assert set(cap.underlines) == {(cap.text.index("target"), 1),
                                   (cap.text.index("prime"), 1),
                                   (cap.text.index("proxy"), 1)}
    assert sorted(cap.text[s:s + n] for s, n in cap.underlines) == ["p", "p", "t"]


def test_control_checkbox_cell_matches_the_one_shared_option_box_size():
    # the all-interval (and diminuator) checkbox CELL is sized to the rendered square so its
    # caption hugs it; that square is the SINGLE shared option-box size (OPTION_BOX_PX = 16),
    # identical to the settings-panel checkboxes and the tuning-ranges monotone/tradeoff boxes.
    chk = {c.id: c for c in _with(all_interval=True).cells}["control:all_interval"]
    assert chk.h == spreadsheet.OPTION_BOX_PX  # tracks the one shared option-box constant


def test_all_interval_checkbox_rides_right_of_the_target_chooser_when_shown():
    # when the target interval set scheme chooser is shown (presets on), the checkbox sits to
    # its RIGHT (the box-𝐋 checkbox-beside-dropdown layout); the chooser greys when it is checked
    on = {c.id: c for c in _with(all_interval=True, presets=True).cells}
    assert on["control:all_interval"].x > on["preset:target"].x


def test_all_interval_checkbox_sits_inside_the_target_chooser_box():
    # box 𝐓: the checkbox + its caption share the target chooser's box (to the dropdown's right),
    # so the border encloses them rather than stranding them past its right edge — and the widened
    # box still stays within the target column's tile (it never overhangs).
    lay = _with(all_interval=True, presets=True)
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    box, tile = blocks["block:preset:target"], blocks["block:vec:targets"]
    for cid in ("control:all_interval", "caption:all_interval"):
        c = cells[cid]
        assert box.x <= c.x and c.x + c.w <= box.x + box.w  # enclosed horizontally
        assert box.y <= c.y and c.y + c.h <= box.y + box.h  # enclosed vertically
    assert tile.x <= box.x and box.x + box.w <= tile.x + tile.w  # box stays within the tile


def test_all_interval_show_entry_is_live_not_a_greyed_stub():
    # it now builds content (the target-controls checkbox + the dual(q) gate), so the Show panel
    # offers it live (interactive), not greyed out as an unbuilt stub
    assert "all_interval" in settings.IMPLEMENTED


def test_alt_complexity_lays_box_l_out_with_just_the_diminuator_checkbox():
    # box 𝐋's only alt.-complexity control is now the "replace diminuator" checkbox — the prescaler
    # chooser became a preset (riding the preset band above). The square sits at the primes
    # column's left edge, over its "replace diminuator" caption; no prescaler dropdown beside it.
    off = {c.id for c in _with(weighting=True, alt_complexity=False).cells}
    on = {c.id: c for c in _with(weighting=True, alt_complexity=True).cells}
    assert "control:prescaler" not in on  # the prescaler is a preset now, not a box-𝐋 control
    assert "caption:prescaler" not in on
    assert "caption:diminuator" not in off
    cap_d = on["caption:diminuator"]
    assert cap_d.kind == "caption"
    assert cap_d.text == "replace diminuator"
    dim = on["control:diminuator"]
    # the square sits at the column's left, its caption hugging its bottom (the cell is sized to
    # the rendered square, OPTION_BOX_PX, so its bottom IS the square's bottom)
    assert dim.x == on["header:primes"].x
    assert cap_d.y == dim.y + dim.h
    # ...and is horizontally CENTRED above its caption slot (both at the column's left edge)
    assert abs((dim.x + dim.w / 2) - (cap_d.x + cap_d.w / 2)) < 1


def test_alt_complexity_adds_an_ignore_diminuator_checkbox_to_box_l():
    off = {c.id for c in _with(weighting=True, alt_complexity=False).cells}
    on = {c.id: c for c in _with(weighting=True, alt_complexity=True).cells}
    assert "control:diminuator" not in off  # no control unless alt. complexity is on
    ctrl = on["control:diminuator"]
    assert ctrl.kind == "control_check"
    assert ctrl.text == ""  # the square only — "replace diminuator" is a separate caption beneath
    assert ctrl.checked is False  # the default scheme is lp, which uses the diminuator
    # the square sits in box 𝐋 (over the primes); its row-position is covered by the layout test
    assert on["header:primes"].x <= ctrl.x


def test_weighting_captions_the_weight_slope_chooser():
    # the weight box's slope dropdown carries a "damage weight slope" caption beneath it,
    # like the optimization box's "optimization power" caption — single CAPTION_LINE band
    on = {c.id: c for c in _with(weighting=True).cells}
    assert "caption:slope" not in {c.id for c in _with(weighting=False).cells}
    cap = on["caption:slope"]
    assert cap.kind == "caption"
    assert cap.text == "damage weight slope"
    assert cap.h == spreadsheet.CAPTION_LINE
    assert cap.y > on["control:slope"].y  # sits below the chooser


def test_weighting_adds_a_weight_slope_chooser_to_the_weight_box():
    # the U/S/C chooser is core to box 𝒘, so it shows with weighting itself — not gated on the
    # (shelved) alt. complexity feature the way box 𝐋's prescaler controls are
    off = {c.id for c in _with(weighting=False).cells}
    on = {c.id: c for c in _with(weighting=True).cells}
    assert "control:slope" not in off  # no control unless weighting is on
    ctrl = on["control:slope"]
    assert ctrl.kind == "control_select"
    assert ctrl.text == "unity-weight"  # the default scheme's damage-weight slope (unity)
    assert ctrl.values == ("complexity-weight", "unity-weight", "simplicity-weight")
    # it rides below the weight list (box 𝒘), spanning the targets column
    assert ctrl.y > on["weight:target:0"].y
    assert ctrl.x == on["header:targets"].x and ctrl.w == on["header:targets"].w


def test_all_interval_omits_the_weight_slope_chooser():
    # an all-interval scheme is simplicity-weighted by construction, so its weight is not a free
    # choice — the U/S/C chooser (and its caption) are omitted, leaving the weight at simplicity
    on = {c.id for c in _with(scheme="minimax-S", weighting=True).cells}
    assert "control:slope" not in on
    assert "caption:slope" not in on


def test_box_l_diminuator_needs_weighting_and_the_primes_column():
    # the diminuator checkbox lives in box 𝐋 (the prescaling matrix over the primes), so it
    # is gone if weighting is off or the temperament (primes) boxes are hidden
    assert "control:diminuator" not in {c.id for c in _with(weighting=False, alt_complexity=True).cells}
    assert "control:diminuator" not in {
        c.id for c in _with(weighting=True, alt_complexity=True, temperament_boxes=False).cells
    }


def test_alt_complexity_is_deferred_so_its_toggle_stays_greyed():
    # alt. complexity is built, but shelved as not-ready: it is held OUT of IMPLEMENTED so the
    # Show panel greys/disables its checkbox (like projection, identity objects, …) and the
    # load path pins it to its default. Its build code and layout tests below stay intact —
    # only the live, toggleable exposure is withdrawn, ready to restore when the feature is.
    assert "alt_complexity" not in settings.IMPLEMENTED


def test_weighting_subcontrols_are_registered_under_weighting():
    # all-interval (a control in box 𝐓) and alt. complexity (controls in boxes 𝐋 and 𝒄)
    # are sub-controls of weighting, so the panel indents them and shows them only while
    # weighting is on
    keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
    assert {"all_interval", "alt_complexity"} <= keys
    assert settings.SUBCONTROLS["all_interval"] == "weighting"
    assert settings.SUBCONTROLS["alt_complexity"] == "weighting"


def test_subcontrol_nesting_depth_drives_panel_indentation():
    # the panel indents each row by its nesting depth, so a grandchild sits further right than
    # its parent rather than level with it: all-interval / alt. complexity (under weighting,
    # under tuning boxes) are depth 2 and indent twice as far as weighting (depth 1). A
    # single-level sub-control is depth 1; a top-level toggle is depth 0.
    assert settings.depth_of("tuning_boxes") == 0
    assert settings.depth_of("weighting") == 1
    assert settings.depth_of("all_interval") == 2
    assert settings.depth_of("alt_complexity") == 2
    assert settings.depth_of("mnemonics") == 1


def test_weight_equivalence_reflects_the_schemes_damage_slope():
    # the weight = complexity / 1 / 1-over-complexity by the scheme's slope, so the
    # equivalence tells the truth about the live scheme rather than a fixed headline
    def equiv(scheme):
        lay = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "symbols": True, "equivalences": True},
            tuning_scheme=scheme,
        )
        return {c.id: c for c in lay.cells}["symbol:weight:targets"].text

    assert equiv("minimax-C") == "𝒘 = 𝒄"      # complexity weight
    assert equiv("minimax-U") == "𝒘 = 𝟏"      # unity weight (document default): bold-1 all-ones vector
    assert equiv("minimax-S") == "𝒘 = 𝒄⁻¹"    # simplicity weight (the all-interval weight)


def test_damage_equivalence_names_the_weight_only_when_the_weight_row_is_shown():
    # 𝐝 = |𝐞|𝒘 (𝒘 the weight LIST, not a matrix — so 𝒘, never diag(𝒘)). The equivalence
    # names that 𝒘 factor only while the weight row is on screen; with weighting hidden it
    # drops to 𝐝 = |𝐞| rather than dangle a reference to a row the reader can't see. The
    # factor is the same whatever the slope — even the unity all-ones weight shows as 𝒘 once
    # visible (its 𝒘 = 𝟏 value lives on the weight row).
    def equiv(scheme, weighting):
        lay = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": weighting, "symbols": True, "equivalences": True},
            tuning_scheme=scheme,
        )
        return {c.id: c for c in lay.cells}["symbol:damage:targets"].text

    # weighting hidden → bare |𝐞|, regardless of the scheme's weight slope
    assert equiv("minimax-U", False) == "𝐝 = |𝐞|"
    assert equiv("minimax-S", False) == "𝐝 = |𝐞|"
    # weighting shown → the 𝒘 factor appears, even under unity weight
    assert equiv("minimax-U", True) == "𝐝 = |𝐞|𝒘"
    assert equiv("minimax-S", True) == "𝐝 = |𝐞|𝒘"


def test_commas_have_a_shared_vertical_axis_per_comma():
    ids = {ln.id for ln in _layout().lines}
    assert "v:comma:0" in ids  # one axis per comma, like the primes/targets
    assert {"trunk:commas", "bus:commas:top", "bus:commas:bot", "foot:commas"} <= ids


def test_collapsing_the_commas_column_hides_its_cells_but_keeps_the_header():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    full = spreadsheet.build(base)
    coll = spreadsheet.build(base, collapsed={"col:commas"})
    assert any(_in_commas(c.id) for c in full.cells)  # present when expanded
    cids = {c.id for c in coll.cells}
    assert not any(_in_commas(c) for c in cids)  # gone from quantities and every tuning row
    assert "header:commas" in cids  # ...but the header survives as a strip
    assert "toggle:col:commas" in cids  # with a re-expand toggle
    assert coll.width < full.width  # and the board narrows


def test_commas_column_has_panels_that_fold_away_and_converge_when_collapsed():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(base, collapsed={"col:commas"})
    blocks = {b.id: b for b in lay.blocks}
    by_id = {ln.id: ln for ln in lay.lines}
    assert blocks["block:commas"].w == 0  # the quantities-row comma panel folds away
    assert blocks["block:tuning:commas"].w == 0  # ...and each tuning row's
    assert by_id["bus:commas:top"].length == 0  # the comma axis converges to one line


def test_comma_basis_is_framed_as_a_vector_list_spanning_its_d_tall_height():
    cells = {c.id: c for c in _layout().cells}
    # the comma basis (in the interval-vectors row) is a list of vectors: an enclosing
    # [ ] plus per-column ket marks
    assert cells["bracket:vec:commas:l"].text == "[" and cells["bracket:vec:commas:r"].text == "]"
    assert "ebktop:vec:commas:0" in cells and "ebkangle:vec:commas:0" in cells
    cb = cells["bracket:vec:commas:l"]
    # the enclosing bracket spans the full d=3 tall basis
    assert cb.y <= cells["cell:comma:0:0"].y
    assert cb.y + cb.h >= cells["cell:comma:2:0"].y + cells["cell:comma:2:0"].h


def test_untempered_vector_columns_get_angle_feet_while_mapped_lists_keep_braces():
    cells = {c.id: c for c in _layout().cells}
    # the interval-vectors row holds RAW (untempered) vectors — each column is a ket,
    # so its foot is the angle ⟩ (drawn as a down-chevron), not the curly brace
    for group in ("commas", "targets"):
        assert f"ebkangle:vec:{group}:0" in cells       # the ket's angle foot
        assert f"ebkbrace:vec:{group}:0" not in cells   # never the curly brace
        assert f"ebktop:vec:{group}:0" in cells         # the square top ([) is unchanged
    # the mapped (tempered) lists in the mapping row keep the curly-brace foot
    assert "ebkbrace:mapped:0" in cells and "ebkangle:mapped:0" not in cells
    assert "ebkbrace:mapped_comma:0" in cells and "ebkangle:mapped_comma:0" not in cells


def test_comma_tuning_rows_get_list_brackets_hugging_their_values():
    cells = {c.id: c for c in _layout().cells}
    # comma sizes are a list of interval sizes, bracketed like the target sizes
    assert cells["bracket:tuning:commalist:l"].text == "[" and cells["bracket:tuning:commalist:r"].text == "]"
    # the bracket pair sits just outside the comma value cells
    l, r = cells["bracket:tuning:commalist:l"], cells["bracket:tuning:commalist:r"]
    assert l.x < cells["tuning:comma:0"].x < r.x


def test_comma_basis_grid_has_no_separator_rules_that_double_its_cell_borders():
    # the comma basis is an editable BORDERED grid (the same cell as the mapping),
    # so its cell borders already divide the columns; also drawing the vector
    # separator rules would lay a second line over each shared border (a visible
    # double). The bare-label target-list vecs keep theirs.
    two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])  # two real comma columns
    cells = {c.id for c in spreadsheet.build(two).cells}
    assert "cell:comma:0:1" in cells  # the second comma column is present...
    assert not any(c.startswith("sep:vec:commas") for c in cells)  # ...with no separator rule
    assert "sep:vec:targets:1" in cells  # the bare target-list vecs still need their separators


def test_caption_line_estimate_wraps_a_long_name_in_a_narrow_column():
    # a wide column fits the whole name on one line...
    assert spreadsheet._wrap_lines("tempered target interval size list", 272) == 1
    # ...but the narrow one-comma column forces it to several lines
    assert spreadsheet._wrap_lines("tempered comma basis interval size list (made to vanish!)", 62) >= 3


def test_a_long_caption_widens_its_tile_to_stay_within_two_lines():
    lay = _with(names=True)
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    name = "tempered comma basis interval size list (made to vanish!)"
    cap = cells["caption:tuning:commas"]
    # the name never wraps past two lines: the column is floored wide enough to hold it,
    # rather than the font shrinking or the name spilling tall down a narrow column
    assert spreadsheet._wrap_lines(name, cap.w) <= spreadsheet.MAX_CAPTION_LINES
    assert cap.h == spreadsheet._wrap_lines(name, cap.w) * spreadsheet.CAPTION_LINE
    assert cap.h <= spreadsheet.MAX_CAPTION_LINES * spreadsheet.CAPTION_LINE
    # the tile widened to make that fit: the commas column is wider than its lone value
    # cell + brackets alone would make it (a narrow one-comma content width)
    content_w = 2 * spreadsheet.BRACKET_W + spreadsheet.COL_W
    assert cells["header:commas"].w > content_w
    assert cap.w == cells["header:commas"].w  # the caption spans the (widened) column
    assert cap.y >= cells["tuning:comma:0"].y + spreadsheet.ROW_H  # below the value cell
    # the grey tile widened with it, so the caption sits within the tile, never beyond it
    panel = blocks["block:tuning:commas"]
    assert panel.x <= cap.x and cap.x + cap.w <= panel.x + panel.w


def test_a_widened_caption_tile_keeps_the_add_control_on_its_fan_stub():
    # Companion to the names-off + test: with names ON, the commas captions widen its tile past
    # its lone comma and the content re-centres in the wider tile. The + rides the fan stub
    # (cell-anchored, a slot past the re-centred comma) and the top bus reaches it — so the +
    # tracks the fan, not the tile edge, and the bar follows it.
    lay = _with(names=True)
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    narrow = {b.id: b for b in _with(names=False).blocks}
    by_id = {ln.id: ln for ln in lay.lines}
    assert blocks["block:commas"].w > narrow["block:commas"].w  # commas tile widened by its caption
    plus, bus = cells["comma_plus"], by_id["bus:commas:top"]
    stub = by_id["v:comma:0"].pos + spreadsheet.COL_W  # one slot past the (re-centred) comma
    assert abs((plus.x + plus.w / 2) - stub) < 0.51     # the + tracks the fan, not the tile edge
    assert abs((bus.start + bus.length) - stub) < 0.51  # and the bus reaches it


def test_min_width_for_lines_floors_a_column_to_keep_a_name_within_two_lines():
    # the inverse of _wrap_lines: the smallest width at which the name fits in two lines.
    # at that width the wrap fits; a narrow one-comma column would overflow it.
    for name in ("tempered comma basis interval size list (made to vanish!)",
                 "comma basis interval retuning list (made to vanish!)",
                 "(just) comma basis interval size list"):
        w = spreadsheet._min_width_for_lines(name, 2)
        assert spreadsheet._wrap_lines(name, w) <= 2
        assert spreadsheet._wrap_lines(name, 2 * spreadsheet.BRACKET_W + spreadsheet.COL_W) > 2


def test_short_captions_span_the_full_band_so_css_can_centre_them():
    # in a row mixing one- and two-line names, every caption cell is the row's full
    # caption-band height (the tallest name's), aligned at the band top — so the CSS can
    # vertically centre a short name (half a blank line above and below) against a taller
    # sibling, rather than the short name hugging the cells with all the slack below.
    cells = {c.id: c for c in _with(names=True).cells}
    short = cells["caption:tuning:primes"]  # "tuning map" — one line in its column
    tall = cells["caption:tuning:commas"]   # "tempered ... (made to vanish!)" — two lines
    assert spreadsheet._wrap_lines(short.text, short.w) == 1
    assert spreadsheet._wrap_lines(tall.text, tall.w) == 2
    assert short.h == tall.h == spreadsheet._wrap_lines(tall.text, tall.w) * spreadsheet.CAPTION_LINE
    assert short.y == tall.y  # both start at the band top; the CSS centres within the band


def test_comma_columns_get_in_tile_captions_consistent_with_the_targets():
    on = {c.id: c for c in _with(names=True).cells}
    off = {c.id: c for c in _with(names=False).cells}
    # the raw comma basis is captioned in the interval-vectors row; the mapping row
    # shows it mapped (vanishing), captioned to parallel the mapped target list
    assert on["caption:vectors:commas"].text == "comma basis"
    assert on["caption:mapping:commas"].text == "mapped comma basis (made to vanish!)"
    # comma captions mirror the target captions, swapping "target interval" for "comma
    # basis interval"; the retuning row says "retuning" (its symbol is 𝒓C) where the
    # targets' dedicated error vector 𝐞 reads "error". The rows the temperament zeroes
    # out — mapped, tempered, retuned — append "(made to vanish!)"; the just row shows
    # the comma's genuine untempered size, so it omits the note. (damage is the
    # exception — a target-only row, with no comma tile to caption)
    assert on["caption:tuning:commas"].text == "tempered comma basis interval size list (made to vanish!)"
    assert on["caption:just:commas"].text == "(just) comma basis interval size list"
    assert on["caption:retune:commas"].text == "comma basis interval retuning list (made to vanish!)"
    assert "caption:damage:commas" not in on
    assert not any(c.startswith("caption:") and c.endswith(":commas") for c in off)


def test_interval_vectors_tiles_are_captioned_by_what_each_column_holds():
    on = {c.id: c for c in _with(names=True).cells}
    assert on["caption:vectors:commas"].text == "comma basis"  # the raw vectors (the dual)
    assert on["caption:vectors:targets"].text == "target interval list"


def test_commas_column_has_an_add_comma_control():
    cells = {c.id: c for c in _layout().cells}
    assert "comma_plus" in cells  # always add-able, like the domain +
    assert cells["comma_plus"].x > cells["comma:0"].x  # in the gutter right of the basis


def test_comma_minus_rides_the_last_comma_only_when_more_than_one():
    one = {c.id for c in _layout().cells}  # meantone exposes a single comma
    assert "comma_minus" not in one  # the sole comma cannot be removed
    two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])  # two real (independent) commas
    cells = {c.id: c for c in spreadsheet.build(two).cells}
    assert "comma_minus" in cells  # ...but with two, the last is removable
    by_id = {ln.id: ln for ln in spreadsheet.build(two).lines}
    cm = cells["comma_minus"]  # centred on the last comma's branch point, dropping from the top bus
    assert abs((cm.x + cm.w / 2) - by_id["v:comma:1"].pos) < 0.51
    assert cm.y == by_id["bus:commas:top"].pos


def test_adding_a_comma_starts_a_pending_draft_column_that_does_not_re_rank():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma, mapping r=2
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    assert cells["comma:0"].text == "80/81"  # the real comma stays
    # a draft column rides to its right: a "?" quantity and blank, red-flagged vector cells
    assert cells["comma:pending"].text == "?" and cells["comma:pending"].pending
    assert cells["comma:pending"].x > cells["comma:0"].x
    assert cells["cell:comma:0:1"].text == "" and cells["cell:comma:0:1"].pending
    # the mapping is untouched (the draft is not yet a real comma): still 2 rows, no 3rd
    assert "cell:mapping:1:0" in cells and "cell:mapping:2:0" not in cells
    # the draft has no size cells (undefined until valid)
    assert "tuning:comma:1" not in cells
    # the − rides the draft column's branch point (to cancel it)
    by_id = {ln.id: ln for ln in spreadsheet.build(base, pending_comma=[None, None, None]).lines}
    assert abs((cells["comma_minus"].x + cells["comma_minus"].w / 2) - by_id["v:comma:1"].pos) < 0.51


def test_a_partly_typed_pending_comma_shows_its_entered_components():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[4, None, 1]).cells}
    assert cells["cell:comma:0:1"].text == "4"   # typed
    assert cells["cell:comma:1:1"].text == ""    # still blank
    assert cells["cell:comma:2:1"].text == "1"
    assert all(cells[f"cell:comma:{p}:1"].pending for p in range(3))


def test_the_pending_comma_columns_ket_marks_are_flagged_for_red():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma + a pending draft (col 1)
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    # the draft column's EBK ket marks render red (like its cells); the real comma's don't
    assert cells["ebktop:vec:commas:1"].pending and cells["ebkangle:vec:commas:1"].pending
    assert not cells["ebktop:vec:commas:0"].pending


def test_the_comma_basis_plain_text_becomes_a_two_tone_draft_box_while_pending():
    # while a comma is pending the comma-basis plain text can't be a single-colour input
    # (it must show the committed commas black and the draft vector red), so it flips to a
    # static two-tone "ptextpending" box; the mapping keeps its editable text box, and once
    # there's no draft the comma basis returns to an editable box too.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["plain_text_values"] = True
    drafting = {c.id: c for c in spreadsheet.build(base, s, pending_comma=[None, None, None]).cells}
    assert drafting["ptext:vectors:commas"].kind == "ptextpending"
    assert drafting["ptext:mapping:primes"].kind == "ptextedit"  # the mapping is untouched
    resting = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert resting["ptext:vectors:commas"].kind == "ptextedit"  # no draft -> editable again


# --- math expressions: the just row's exact log₂ closed forms ---

def test_math_expressions_render_the_just_tuning_primes_as_logs():
    # the just tuning map over primes is exactly 1200·log₂ of each prime, so with
    # math expressions on its cells PREFIX the (unchanged) cents value with that
    # equal expression — the "= cents" kept on a second line
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:prime:0"].kind == "mathexpr"
    assert cells["just:prime:0"].text == "1200 · log₂2\n= 1200.000"  # 1200·log₂2 == 1200
    assert cells["just:prime:1"].text == "1200 · log₂3\n= 1901.955"
    assert cells["just:prime:2"].text == "1200 · log₂5\n= 2786.314"


def test_math_expressions_render_the_just_target_sizes_as_logs():
    # the just target-size list is 1200·log₂ of each target ratio; a bare prime ratio
    # (n/1) drops its denominator, a proper ratio keeps it in parentheses
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:target:1"].text == "1200 · log₂3\n= 1901.955"  # 3/1 -> log₂3
    assert cells["just:target:2"].text == "1200 · log₂(3/2)\n= 701.955"  # 3/2 keeps the ratio


def test_math_expressions_render_the_just_comma_sizes_as_logs():
    # a comma is an interval too, so its just size is 1200·log₂ of its ratio; the
    # syntonic comma 80/81 is a hair flat of unity, hence a small negative size
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:comma:0"].kind == "mathexpr"
    assert cells["just:comma:0"].text == "1200 · log₂(80/81)\n= -21.506"


def test_math_expressions_show_the_comma_error_as_a_log():
    # a comma vanishes in the temperament (its tempered size is 0), so its retuning is
    # the negated just size — an exact log of the inverted comma (80/81 -> 81/80),
    # unlike the optimized prime/target errors
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["retune:comma:0"].text == "1200 · log₂(81/80)\n= 21.506"


def test_math_expressions_leave_the_no_closed_form_cells_and_tiles_untouched():
    # tempered tuning + the prime/target errors have no exact closed form, so math
    # expressions adds nothing there: those cells keep their plain cents value, and
    # the brackets, captions and panels of every tuning tile stay put. Math
    # expressions only PREFIXES the closed-form cells — it never removes anything.
    off = {c.id: c for c in _with().cells}
    on_lay = _with(math_expressions=True)
    on = {c.id: c for c in on_lay.cells}
    for cid in ("tuning:prime:1", "tuning:comma:0", "tuning:target:0",
                "retune:prime:1", "damage:target:0"):
        assert on[cid].kind == "tval"  # untouched: still the plain cents cell...
        assert on[cid].text == off[cid].text  # ...with the same value as math off
    # the tempered row's framing brackets, caption and grey panel all remain
    assert {"bracket:tuning:map:l", "caption:tuning:primes"} <= set(on)
    assert "block:tuning:primes" in {b.id for b in on_lay.blocks}


def test_math_expressions_without_quantities_show_only_the_expression():
    # quantities drives the "= value" second line; with it off the cell is the
    # bare expression, no decimal and no newline
    cells = {c.id: c for c in _with(math_expressions=True, quantities=False).cells}
    assert cells["just:prime:1"].text == "1200 · log₂3"


def test_math_expressions_is_an_interactive_toggle():
    # it now builds content, so the panel must offer it live rather than greyed out
    assert "math_expressions" in settings.IMPLEMENTED


def test_math_expressions_render_the_prescaler_diagonal_as_logs():
    # the bare prescaler 𝐿's diagonal is the user's editable surface (the prescalercell
    # kind, where the override is typed), so it WINS over math_expressions even with the
    # toggle on: each diagonal cell shows its plain prescaled value (the active diagonal),
    # not a closed-form expression. Math expressions still styles the off-diagonal product
    # tiles (LC, LD, LT, LH), and the diagonal's value still matches the live scheme.
    cells = {c.id: c for c in _with(weighting=True, math_expressions=True).cells}
    assert cells["cell:prescaling:primes:0:0"].kind == "prescalercell"
    assert cells["cell:prescaling:primes:0:0"].text == "1"  # log₂2 == 1, shown bare
    assert cells["cell:prescaling:primes:1:1"].text == "1.585"
    assert cells["cell:prescaling:primes:2:2"].text == "2.322"
    assert cells["cell:prescaling:primes:0:1"].kind == "tval"  # off-diagonal stays plain
    assert cells["cell:prescaling:primes:0:1"].text == "0"


def test_math_expressions_render_the_prescaled_comma_basis_as_logs():
    # 𝑋C = LC: each cell is the prime's log scaled by the comma's coefficient for that
    # prime — so the syntonic comma 80/81 (basis sign — see the just-comma test) over
    # 2.3.5 gives 4·log₂2, -4·log₂3, log₂5. A unit coefficient drops the ``1 ·`` prefix.
    cells = {c.id: c for c in _with(weighting=True, math_expressions=True).cells}
    assert cells["cell:prescaling:commas:0:0"].text == "4 · log₂2\n= 4"
    assert cells["cell:prescaling:commas:1:0"].text == "-4 · log₂3\n= -6.340"
    assert cells["cell:prescaling:commas:2:0"].text == "log₂5\n= 2.322"


def test_math_expressions_without_quantities_show_only_the_prescaler_expression():
    # quantities drives the "= value" second line for the prescaling row's product tiles too;
    # with it off, each LC/LD/LT/LH cell is just the bare closed form — no decimal, no newline,
    # like the just row's math expression in the same configuration. The bare prescaler 𝐿's
    # diagonal is an editable prescalercell (a value-bearing input box), so quantities=False
    # blanks its text alongside the other editable matrix cells (commacell/heldcell/...).
    cells = {c.id: c for c in _with(weighting=True, math_expressions=True, quantities=False).cells}
    assert cells["cell:prescaling:primes:1:1"].kind == "prescalercell"
    assert cells["cell:prescaling:primes:1:1"].text == ""  # blanked alongside other editable cells
    assert cells["cell:prescaling:primes:1:1"].blank is True
    assert cells["cell:prescaling:commas:1:0"].text == "-4 · log₂3"


def test_math_expressions_under_prime_prescaler_drop_the_log():
    # the prime prescaler (diag(𝒑)) puts each prime ITSELF on the diagonal, so the closed
    # form for the product tiles (LC/LD/LT/LH) is ``coeff · prime`` — no log₂. The bare
    # prescaler 𝐿's diagonal stays a prescalercell (the editable surface), so it shows
    # each prime as the plain value rather than a closed form.
    scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "prime")
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                            {**settings.defaults(), "weighting": True, "math_expressions": True},
                            tuning_scheme=scheme)
    cells = {c.id: c for c in lay.cells}
    # the diagonal: each prime is the plain value (prescalercell, not mathexpr)
    assert cells["cell:prescaling:primes:0:0"].kind == "prescalercell"
    assert cells["cell:prescaling:primes:0:0"].text == "2"  # prime 2
    assert cells["cell:prescaling:primes:1:1"].text == "3"  # prime 3
    assert cells["cell:prescaling:primes:2:2"].text == "5"
    # the comma column: coeff · prime (no log)
    assert cells["cell:prescaling:commas:0:0"].text == "4 · 2\n= 8"
    assert cells["cell:prescaling:commas:1:0"].text == "-4 · 3\n= -12"


def test_math_expressions_under_identity_prescaler_emit_no_closed_form():
    # the identity prescaler (𝐼) puts 1 on every diagonal slot, so the closed form
    # would just repeat the coefficient — no new information. Following the just-row
    # rule (mathexpr only where a NON-trivial closed form lives), every product-tile
    # prescaling cell stays as its plain tval. The bare prescaler 𝐿's diagonal is an
    # editable prescalercell regardless of scheme (the user types overrides here), so
    # it shows the plain value (1) too — same number, kinder kind.
    scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "identity")
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                            {**settings.defaults(), "weighting": True, "math_expressions": True},
                            tuning_scheme=scheme)
    cells = {c.id: c for c in lay.cells}
    # diagonal cell of the bare prescaler — value 1, the editable prescalercell kind
    assert cells["cell:prescaling:primes:1:1"].kind == "prescalercell"
    assert cells["cell:prescaling:primes:1:1"].text == "1"
    # comma column entry — value 4 (= coeff), no log dressing
    assert cells["cell:prescaling:commas:0:0"].kind == "tval"
    assert cells["cell:prescaling:commas:0:0"].text == "4"


def test_bare_prescaler_diagonal_is_editable_prescalercell_kind():
    # the bare prescaler 𝐿 tile is the editable surface where the user types overrides
    # for the prescaler's diagonal — so each diagonal cell (i == c) is a prescalercell
    # kind (mirroring commacell/interestcell/heldcell, the other editable matrix cells).
    # The OFF-diagonal cells stay tval "0" — they're pinned at zero because 𝐿 is diagonal.
    cells = {c.id: c for c in _with(weighting=True).cells}
    # diagonal cells are prescalercell
    for i in range(3):
        assert cells[f"cell:prescaling:primes:{i}:{i}"].kind == "prescalercell"
    # off-diagonal cells stay plain tval "0"
    for i in range(3):
        for c in range(3):
            if i == c:
                continue
            assert cells[f"cell:prescaling:primes:{i}:{c}"].kind == "tval"
            assert cells[f"cell:prescaling:primes:{i}:{c}"].text == "0"


def test_bare_prescaler_diagonal_carries_its_prime_index():
    # like the commacell/interestcell/heldcell editable kinds, each diagonal cell records
    # which diagonal slot (= which domain prime) it edits, so the app layer can dispatch
    # set_custom_prescaler_entry(i, value) on change. The off-diagonal cells stay pinned 0
    # and carry no prime index (nothing to dispatch).
    cells = {c.id: c for c in _with(weighting=True).cells}
    for i in range(3):
        assert cells[f"cell:prescaling:primes:{i}:{i}"].prime == i


def test_custom_prescaler_override_drives_the_bare_prescaler_diagonal_text():
    # a custom_prescaler override (d-tuple) typed into the bare prescaler tile flows back
    # into the diagonal cells' text — the user's edit IS what they see, rather than the
    # scheme's computed log/prime/identity diagonal.
    s = settings.defaults() | {"weighting": True}
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            custom_prescaler=(2.5, 7.5, 11.0))
    cells = {c.id: c for c in lay.cells}
    assert cells["cell:prescaling:primes:0:0"].text == "2.500"
    assert cells["cell:prescaling:primes:1:1"].text == "7.500"
    assert cells["cell:prescaling:primes:2:2"].text == "11"  # bare (no fractional part)


def test_custom_prescaler_override_flows_into_the_product_tiles():
    # 𝐿C (and 𝐿T, 𝐿D, 𝐿H) read off the same prescaler diagonal — typing an override at
    # the bare tile MUST retune every product tile that scales by 𝐿. Here the syntonic
    # comma 80/81 over 2.3.5 with diag (1, 1, 2) gives 4·1, -4·1, 1·2 = 4, -4, 2.
    s = settings.defaults() | {"weighting": True}
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            custom_prescaler=(1.0, 1.0, 2.0))
    cells = {c.id: c for c in lay.cells}
    assert cells["cell:prescaling:commas:0:0"].text == "4"
    assert cells["cell:prescaling:commas:1:0"].text == "-4"
    assert cells["cell:prescaling:commas:2:0"].text == "2"


def test_custom_prescaler_override_drives_the_complexity_row():
    # the complexity row norms each interval's prescaled vector — so a custom diagonal
    # rewrites every complexity cell. With diag (1, 1, 1) (an identity-style override
    # over 2.3.5), the comma 80/81's complexity equals its taxicab norm = 4+4+1 = 9.
    s = settings.defaults() | {"weighting": True}
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            custom_prescaler=(1.0, 1.0, 1.0))
    cells = {c.id: c for c in lay.cells}
    assert cells["complexity:comma:0"].text == "9.000"


def test_custom_prescaler_override_drives_the_weight_row():
    # the weight row reads each target's complexity (under the live prescaler) — so a custom
    # diagonal MUST rewrite the weights too. That coupling only shows when the slope isn't unity
    # (unity weight is 1 regardless of complexity), so use a simplicity-weighted scheme: every
    # weight is then 1/complexity. Spot-check by comparing the override case to the scheme's: the
    # override's weights are NOT the default's (the prescaler changed, so the complexities did too).
    s = settings.defaults() | {"weighting": True}
    scheme = f"TILT {service.DEFAULT_TUNING_SCHEME}"  # target-based simplicity weight
    default = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, tuning_scheme=scheme)
    override = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                  tuning_scheme=scheme, custom_prescaler=(1.0, 1.0, 1.0))
    d_weights = [c.text for c in default.cells if c.id.startswith("weight:target:")]
    o_weights = [c.text for c in override.cells if c.id.startswith("weight:target:")]
    assert d_weights and o_weights and len(d_weights) == len(o_weights)
    assert d_weights != o_weights  # the override genuinely changed the weights row


def test_counts_on_adds_a_top_row_of_per_column_cardinalities():
    cells = {c.id: c for c in _with(counts=True).cells}
    # the counts row reports each present column's set cardinality, with the
    # variable as a mathematical-italic letter (matching the Show panel's example)
    assert cells["count:gens"].text == "\U0001D45F = 2"  # 𝑟 rank: two generators
    assert cells["count:primes"].text == "\U0001D451 = 3"  # 𝑑 dimensionality: 2.3.5
    assert cells["count:commas"].text == "\U0001D45B = 1"  # 𝑛 nullity: one comma (syntonic)
    assert cells["count:targets"].text == "\U0001D458 = 8"  # 𝑘 target interval count: the 6-TILT is 8


def test_counts_row_counts_the_generator_detempering_column_too():
    # the generator detempering matrix holds one detempering interval per generator, so its
    # count IS the rank r — the same value AND the same name ("rank") as the generators
    # column's count. The count tile only exists while the detempering column is shown.
    cells = {c.id: c for c in _with(counts=True, names=True, generator_detempering=True).cells}
    assert cells["count:detempering"].text == "\U0001D45F = 2"  # 𝑟 rank: one detempering interval per generator
    assert cells["count:detempering"].text == cells["count:gens"].text  # tracks the rank, like the generators count
    assert cells["caption:counts:detempering"].text == "rank"  # the same name as the generators count, not a new one
    # absent when the detempering column is hidden (no column → no count tile)
    assert "count:detempering" not in {c.id for c in _with(counts=True).cells}


def test_counts_row_sits_at_the_top_aligned_over_its_columns():
    cells = {c.id: c for c in _with(counts=True).cells}
    # the counts row is the topmost data row — above the quantities (primes/targets)
    assert cells["count:primes"].y < cells["prime:0"].y
    assert cells["count:targets"].y < cells["target:0"].y
    # each count spans its column, centred over the values like the header
    for ckey in ("gens", "primes", "targets"):
        assert cells[f"count:{ckey}"].x == cells[f"header:{ckey}"].x
        assert cells[f"count:{ckey}"].w == cells[f"header:{ckey}"].w


def test_counts_present_keeps_the_column_fan_out_immediately_after_the_toggle():
    # the column fan-out sits right below the toggle (where rows fan too), NOT delayed
    # past the counts row: counts shows one cardinality per column, and the per-element
    # sub-lines now thread straight through the counts band rather than splitting below it.
    lay = _with(counts=True)
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    fan = by_id["bus:primes:top"].pos  # the y where the per-prime lines fan out
    count = cells["count:primes"]
    assert fan < count.y  # the fan-out sits ABOVE the counts row...
    # ...and the per-prime sub-lines thread straight through the counts band
    v0 = by_id["v:prime:0"]
    assert v0.start == fan
    assert v0.start < count.y and v0.start + v0.length > count.y + count.h
    # the trunk is just the short stem from the branch top down to the fan-out
    trunk = by_id["trunk:primes"]
    assert trunk.start + trunk.length == fan
    # and it matches the counts-absent fan-out position (counts no longer shifts it)
    assert fan == {ln.id: ln for ln in _with(counts=False).lines}["bus:primes:top"].pos


def test_counts_off_by_default_leaves_the_quantities_row_on_top():
    # the default build target shows no counts row; quantities stays the top row
    cells = {c.id for c in _layout().cells}
    assert "label:counts" not in cells
    assert not any(c.startswith("count:") for c in cells)


def test_count_names_caption_each_count_only_when_names_is_on():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    def captioned(names):
        s = settings.defaults()
        s["counts"], s["names"] = True, names
        return {c.id: c for c in spreadsheet.build(base, s).cells}

    on = captioned(names=True)
    assert on["caption:counts:gens"].text == "rank"
    assert on["caption:counts:primes"].text == "dimensionality"
    assert on["caption:counts:commas"].text == "nullity"
    assert on["caption:counts:targets"].text == "target interval count"
    assert on["caption:counts:primes"].y > on["count:primes"].y  # caption below the value
    off = captioned(names=False)
    assert not any(c.startswith("caption:counts:") for c in off)  # but the value cells remain
    assert {"count:gens", "count:primes", "count:targets"} <= set(off)


def test_counts_row_collapses_like_any_other_keeping_its_label_and_gridline():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["counts"] = True
    full = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert "toggle:row:counts" in full  # collapsible: it has a fold toggle
    lay = spreadsheet.build(base, s, collapsed={"row:counts"})
    cells = {c.id: c for c in lay.cells}
    assert not any(c.startswith("count:") for c in cells)  # the values fold away
    assert "label:counts" in cells  # ...the label survives as a strip
    assert {ln.id for ln in lay.lines} >= {"h:counts"}  # ...leaving a gridline through the row


def test_counts_track_the_live_domain_after_an_expand():
    expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # 2.3.5 -> 2.3.5.7
    s = settings.defaults()
    s["counts"] = True
    cells = {c.id: c for c in spreadsheet.build(expanded, s).cells}
    assert cells["count:primes"].text == "\U0001D451 = 4"  # 𝑑: the added prime grows the dimensionality
    assert cells["count:gens"].text == "\U0001D45F = 3"  # 𝑟: meantone gains an independent generator


def test_every_count_sits_on_its_own_grey_panel():
    # the counts row's panels derive from the same COUNTS source as its cells, so a
    # count can never render without a tile background behind it (the nullity bug)
    lay = _with(counts=True)
    blocks = {b.id: b for b in lay.blocks}
    counts = [c.id for c in lay.cells if c.id.startswith("count:")]
    assert counts  # the counts row is populated
    for cid in counts:
        ckey = cid.split(":", 1)[1]
        panel = blocks.get(f"block:counts:{ckey}")
        assert panel is not None, f"{cid} has no backing panel"
        assert panel.w > 0 and panel.h > 0  # a visible grey background


def test_other_intervals_of_interest_column_is_present_right_of_targets():
    cells = {c.id: c for c in _layout().cells}  # default build: interest defaults to empty
    assert cells["header:interest"].text == "other intervals\nof interest"
    assert "toggle:col:interest" in cells  # foldable like the other interval columns
    assert cells["header:interest"].x > cells["header:targets"].x  # rightmost column


def test_empty_interest_columns_footprint_hugs_its_content_the_title_overhangs():
    # the footprint hugs the column's content — for an empty interest column that is just
    # its two bracket gutters (no intervals yet). The long two-line title is wider than
    # that and overhangs the column (rendered without wrapping), rather than forcing the
    # footprint out to the title's strip width and leaving the narrow content adrift in it.
    cells = {c.id: c for c in _layout().cells}  # default build => interest empty
    assert cells["header:interest"].w == 2 * spreadsheet.BRACKET_W
    assert cells["header:interest"].w < spreadsheet._title_w("other intervals\nof interest")


def test_empty_interest_column_is_just_a_header_and_axis():
    lay = _layout()
    cids = {c.id for c in lay.cells}
    # an empty set contributes no per-interval content, marks, or captions
    assert not any(c.startswith(("interest:", "cell:imapped:")) for c in cids)
    assert not any(c.startswith(("tuning:interest:", "just:interest:", "retune:interest:")) for c in cids)
    assert not any("imapped" in c for c in cids)
    assert "caption:mapping:interest" not in cids
    # ...but the column still draws a single straight vertical axis (trunk -> foot)
    lids = {ln.id for ln in lay.lines}
    assert {"trunk:interest", "foot:interest"} <= lids
    assert "v:interest:0" not in lids and "bus:interest:top" not in lids


# the user enters intervals of interest as vectors (like the comma basis); these are
# 3/2, 9/8, 10/9, 8/5 over the 2.3.5 domain, used across the populated-interest tests
_INTEREST = ((-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1))


def test_populated_interest_renders_ratios_mapped_and_sizes_minus_damage():
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    # quantities row: the ratio derived from each entered vector
    assert cells["interest:0"].text == "3/2" and cells["interest:3"].text == "8/5"
    # mapping row: each interval mapped to generator coords (M . i), like the targets
    assert cells["cell:imapped:0:0"].text == "0" and cells["cell:imapped:1:0"].text == "1"  # 3/2 -> [0,1]
    assert cells["cell:imapped:1:3"].text == "-4"  # 8/5 -> [3,-4]
    # tempered / just / retuning size rows
    assert {"tuning:interest:0", "just:interest:0", "retune:interest:3"} <= set(cells)
    assert cells["just:interest:0"].text == "701.955"  # 3/2 just is a pure fifth
    # ...but NO damage row: these are not optimization targets
    assert not any(c.startswith("damage:interest") for c in cells)


def test_populated_interest_renders_plain_text_for_all_its_value_tiles():
    # regression: plain text was missing for the entire interest column. Every value tile
    # the default view shows should carry its band, and the vectors/mapped rows read as
    # standalone kets — no outer [ … ] wrapping (the column is a collection, not a matrix).
    s = settings.defaults()
    s["plain_text_values"] = True
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s, interest=_INTEREST).cells}
    assert cells["ptext:vectors:interest"].text == "[-1 1 0⟩ [-3 2 0⟩ [1 -2 1⟩ [3 0 -1⟩"
    assert cells["ptext:mapping:interest"].text == "[0 1} [-1 2} [-1 2} [3 -4}"
    assert {"ptext:tuning:interest", "ptext:just:interest", "ptext:retune:interest"} <= set(cells)
    # the size rows' plain text is bare numbers too — no enclosing [ … ] (the whole column)
    assert cells["ptext:just:interest"].text == "701.955 203.910 182.404 813.686"


def test_interest_intervals_are_editable_vectors_like_the_comma_basis():
    # in the interval-vectors row each interval is an editable d-tall vector column
    # (kind "interestcell", the comma-basis editing affordance), prime exponents down
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    assert cells["cell:interest:0:0"].text == "-1"  # 3/2 = [-1 1 0>: prime-2 exponent
    assert cells["cell:interest:1:0"].text == "1" and cells["cell:interest:2:0"].text == "0"
    assert cells["cell:interest:2:2"].text == "1"  # 10/9 = [1 -2 1>: prime-5 exponent
    assert cells["cell:interest:0:0"].kind == "interestcell"  # editable, not a static "vec"
    # each interval stands alone as its own ket (per-column ⟨ top + ⟩ angle foot), UNLIKE
    # the comma basis / target list: no outer [ … ] wrapping it into a matrix, and no
    # separator rules between the columns — just space (per the mockup)
    assert {"ebktop:vec:interest:0", "ebkangle:vec:interest:0",
            "ebktop:vec:interest:1", "ebkangle:vec:interest:1"} <= set(cells)
    assert "bracket:vec:interest:l" not in cells and "bracket:vec:interest:r" not in cells
    assert not any(c.startswith("sep:vec:interest:") for c in cells)


def test_interest_vector_cells_are_separated_boxes_not_a_contiguous_grid():
    # the mockup renders each interval's ket as its own bordered box with space around it,
    # not a contiguous matrix grid. So the interest vector cells are inset within their
    # COL_W column slot, leaving a horizontal gap between adjacent kets — while staying
    # centred on the slot, so the per-column marks and the column axis still line up.
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    c0, c1 = cells["cell:interest:0:0"], cells["cell:interest:0:1"]
    m0 = cells["cell:imapped:0:0"]  # the mapped cell spans the full COL_W slot
    assert c0.w < m0.w                              # the ket box is inset (narrower than the slot)
    assert c0.x + c0.w < c1.x                       # a real gap between adjacent kets
    assert c0.x + c0.w / 2 == m0.x + m0.w / 2       # ...but centred on the same slot


def test_interest_has_add_and_per_interval_remove_controls():
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    assert "interest_plus" in cells  # one + appends a blank interval
    # every interval carries its own − (unlike the domain/comma last-only −)
    assert {"interest_minus:0", "interest_minus:1", "interest_minus:2", "interest_minus:3"} <= set(cells)


def test_empty_but_open_interest_still_offers_the_add_control():
    # with no intervals yet (but the column expanded), the + must be reachable to add
    # the first one; there are no minus controls since there is nothing to remove
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), interest=()).cells}
    assert "interest_plus" in cells
    assert not any(c.startswith("interest_minus:") for c in cells)


def test_adding_intervals_of_interest_never_shrinks_the_header():
    # regression: the long title floats the interest HEADER out to its two-line strip
    # width; the few-interval value cells must not shrink that header (which would rewrap
    # the title onto a third line). The footprint hugs max(content, the caption's 2-line
    # floor), so it only ever grows as intervals are added — like every other column.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    builds = [spreadsheet.build(base, collapsed=frozenset(), interest=[(0, 0, 0)] * n) for n in range(5)]
    widths = [{c.id: c for c in lay.cells}["header:interest"].w for lay in builds]
    assert widths == sorted(widths)  # monotonic: adding an interval never narrows the header
    assert min(widths) == widths[0]  # ...and never dips below the empty (title-strip) width


def test_interest_tiles_and_footprint_hug_their_content_the_title_overhangs():
    # the column footprint hugs its content — or the modest width its captions need to wrap
    # within MAX_CAPTION_LINES, like every other column — NOT the wide title's width. The
    # two-line title overhangs the column rather than the footprint reserving its width and
    # leaving the narrow tile adrift in it.
    lay = _with_interest(_INTEREST[:1])  # a single interval
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    content_w = 2 * spreadsheet.BRACKET_W + 1 * spreadsheet.COL_W  # the two gutters + one cell
    # one interval's content is narrow, so its captions' 2-line floor sets the (still modest) width
    floor = max(spreadsheet._min_width_for_lines(spreadsheet.CAPTIONS[(rk, "interest")], spreadsheet.MAX_CAPTION_LINES)
                for rk in ("vectors", "mapping", "tuning", "just", "retune"))
    hug_w = max(content_w, floor)
    # the tile hugs that width — just its PAD overhang each side (the + rides the fan, not the tile)
    assert blocks["block:interest"].w == hug_w + 2 * spreadsheet.PAD
    # the footprint hugs content/captions (no title reservation); the wider title overhangs it
    assert cells["header:interest"].w == hug_w
    assert cells["header:interest"].w < spreadsheet._title_w("other intervals\nof interest")


def test_interest_title_overhangs_symmetrically_centred_on_the_gridline():
    # the footprint hugs the content (narrower than the two-line title) with the gridline
    # down its centre and the header box centred on it — so the wider title overflows the
    # box symmetrically (centred on the gridline), never floated to one side the way a
    # right-aligned header would. The tiles sit centred on that same gridline.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    title_w = spreadsheet._title_w("other intervals\nof interest")
    for mi in range(4):  # a handful of intervals: content stays narrower than the title
        lay = spreadsheet.build(base, collapsed=frozenset(), interest=[(0, 0, 0)] * mi)
        cells = {c.id: c for c in lay.cells}
        lines = {ln.id: ln for ln in lay.lines}
        header, trunk = cells["header:interest"], lines["trunk:interest"]
        assert header.w < title_w  # footprint hugs content, narrower than the title
        assert header.x + header.w / 2 == trunk.pos  # header centred on the gridline => title overhangs evenly
    # a single interval: the tile is narrower than the title yet centred on the gridline,
    # and the lone interval's own axis coincides with the trunk
    one = _with_interest(_INTEREST[:1])
    cells = {c.id: c for c in one.cells}
    lines = {ln.id: ln for ln in one.lines}
    block = {b.id: b for b in one.blocks}["block:interest"]
    trunk = lines["trunk:interest"]
    assert block.w < title_w  # the tile is allowed to be smaller than the title
    assert block.x + block.w / 2 == trunk.pos  # ...and is centred on the same gridline
    assert lines["v:interest:0"].pos == trunk.pos  # the single interval's axis is the trunk


def test_per_tile_fold_toggle_hugs_its_tile_corner():
    # a per-tile fold toggle is anchored to its tile's own top-left corner — for a narrow
    # column whose title overhangs (interest) as much as for an ordinary one (primes).
    lay = _with_interest(_INTEREST[:1])
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    for toggle_id, block_id in (("toggle:tile:vectors:interest", "block:vec:interest"),
                                ("toggle:tile:mapping:primes", "block:mapping")):
        toggle, tile = cells[toggle_id], blocks[block_id]
        assert toggle.x == tile.x + spreadsheet.TOGGLE_INSET  # hugs the tile's corner
        assert tile.x <= toggle.x <= tile.x + tile.w          # ...so it sits within the tile


def test_populated_interest_mapped_list_is_standalone_columns_not_a_matrix():
    # the mapped row mirrors the vectors row: each interval's generator-coord image stands
    # alone (per-column top + brace ⟩ foot), with NO outer [ … ] wrapping it into a matrix
    # and NO separator rules between columns — just space (per the mockup)
    cells = {c.id: c for c in _with_interest(_INTEREST[:2]).cells}
    assert {"ebktop:imapped:0", "ebkbrace:imapped:0",
            "ebktop:imapped:1", "ebkbrace:imapped:1"} <= set(cells)
    assert "bracket:imapped:l" not in cells and "bracket:imapped:r" not in cells
    assert not any(c.startswith("sep:imapped:") for c in cells)
    # the tempered/just/retuning size rows drop their list brackets too — the whole interest
    # column is a loose collection, not a matrix/list, so its values stand bare (per the mockup)
    assert not any(c.startswith(("bracket:tuning:ilist", "bracket:just:ilist", "bracket:retune:ilist")) for c in cells)


def test_populated_interest_has_per_interval_axes_and_panels():
    lay = _with_interest(_INTEREST[:3])
    ids = {ln.id for ln in lay.lines}
    assert {"v:interest:0", "v:interest:1", "v:interest:2"} <= ids
    assert {"trunk:interest", "bus:interest:top", "bus:interest:bot", "foot:interest"} <= ids
    blocks = {b.id for b in lay.blocks}
    assert {"block:interest", "block:imapped", "block:tuning:interest", "block:vec:interest"} <= blocks
    assert "block:damage:interest" not in blocks  # no damage tile


def test_collapsing_interest_hides_its_cells_but_keeps_the_header():
    coll = _with_interest(_INTEREST[:2], collapsed={"col:interest"})
    cids = {c.id for c in coll.cells}
    assert not any(c.startswith(("interest:", "cell:imapped:", "cell:interest:", "tuning:interest:")) for c in cids)
    assert "header:interest" in cids and "toggle:col:interest" in cids
    # targets are unaffected by the interest column folding
    assert "cell:mapped:0:0" in cids


def test_interest_captions_match_the_mockup_names():
    # the interest column's captions are the mockup's own descriptive names — distinct from
    # the targets column's "...target interval... list" phrasing. They're longer than the
    # narrow column, so (like the column title) they overhang a single line rather than
    # wrapping; the caption band counts them as one line, so adding intervals never reflows
    # the board (guarded by test_adding_intervals_of_interest_neither_shrinks_the_header...).
    cells = {c.id: c for c in _with_interest(_INTEREST[:1]).cells}  # names default on
    assert cells["caption:vectors:interest"].text == "intervals of interest"
    assert cells["caption:mapping:interest"].text == "mapped intervals"
    assert cells["caption:tuning:interest"].text == "tempered interval sizes"
    assert cells["caption:just:interest"].text == "(just) interval sizes"
    assert cells["caption:retune:interest"].text == "interval retunings"
    assert "caption:damage:interest" not in cells  # no damage row, like the column's tiles


def test_mnemonics_underline_the_symbol_letter_within_the_name_captions():
    on = {c.id: c for c in _with(names=True, mnemonics=True).cells}
    off = {c.id: c for c in _with(names=True, mnemonics=False).cells}
    cap = on["caption:mapping:primes"]
    # the caption keeps the plain name as its text...
    assert cap.text == "(temperament) mapping"
    # ...and mnemonics underlines the m of "mapping" — the symbol M — as a (start, len) span
    assert cap.underlines == ((cap.text.index("mapping"), 1),)
    # without mnemonics the caption carries no underlines
    assert off["caption:mapping:primes"].underlines == ()


def test_mnemonics_mark_each_quantitys_symbol_letter_and_skip_the_symbolless_ones():
    on = {c.id: c for c in _with(names=True, mnemonics=True).cells}

    def underlined(cid):
        c = on[cid]
        return "".join(c.text[s:s + n] for s, n in c.underlines)

    assert underlined("caption:tuning:primes") == "t"  # tuning map -> t
    assert underlined("caption:just:primes") == "j"  # just tuning map -> j
    assert underlined("caption:retune:primes") == "r"  # retuning map -> r
    assert underlined("caption:retune:targets") == "e"  # target interval error list -> e
    assert underlined("caption:damage:targets") == "d"  # target interval damage list -> d
    # size/list tiles whose symbol letter isn't a word-initial in their name stay
    # unmarked: the mapped list (Y), the tempered (𝐚) and just (𝐨) size lists
    assert on["caption:mapping:targets"].underlines == ()
    assert on["caption:tuning:targets"].underlines == ()
    assert on["caption:just:targets"].underlines == ()


def test_interval_basis_captions_underline_their_symbol_letters():
    on = {c.id: c for c in _with(names=True, mnemonics=True).cells}

    def underlined(cid):
        c = on[cid]
        return "".join(c.text[s:s + n] for s, n in c.underlines)

    # the input interval bases in the vectors row carry single-letter symbols whose
    # letter leads their caption: the comma basis C and the target interval list T
    assert underlined("caption:vectors:commas") == "c"   # comma basis -> C
    assert underlined("caption:vectors:targets") == "t"  # target interval list -> T


def test_symbols_toggles_in_tile_symbol_glyphs_above_the_names():
    on = {c.id: c for c in _with(symbols=True, names=True).cells}
    off = {c.id: c for c in _with(symbols=False).cells}
    # styling per the convention: the mapping 𝑀 is math-italic; the interval
    # lists/bases (Y, comma basis C, target list T) are upright non-bold; the maps
    # are bold-italic; the size-lists bold-upright
    assert on["symbol:mapping:primes"].text == "𝑀"  # mapping matrix (italic)
    assert on["symbol:mapping:targets"].text == "Y"  # mapped target list (upright)
    assert on["symbol:vectors:targets"].text == "T"  # target interval list (upright)
    assert on["symbol:vectors:commas"].text == "C"  # comma basis (upright)
    assert on["symbol:tuning:primes"].text == "𝒕"  # tuning map (bold-italic)
    assert on["symbol:tuning:targets"].text == "𝐚"  # tempered target sizes (bold-upright)
    assert on["symbol:damage:targets"].text == "𝐝"  # damage list (bold-upright)
    assert not any(c.startswith("symbol:") for c in off)
    # the symbol stacks directly above the name caption for the same quantity
    assert on["symbol:mapping:primes"].y < on["caption:mapping:primes"].y
    # row labels and column headers are unaffected, like names
    assert {"label:mapping", "header:primes"} <= set(on)


def test_symbol_takes_the_label_slot_and_pushes_the_name_down():
    both = {c.id: c for c in _with(symbols=True, names=True).cells}
    sym_only = {c.id: c for c in _with(symbols=True, names=False).cells}
    # with names off, the lone symbol sits immediately below the (unframed) tuning row
    assert sym_only["symbol:tuning:primes"].y == sym_only["tuning:prime:0"].y + spreadsheet.ROW_H
    assert not any(c.startswith("caption:") for c in sym_only)
    # with both on, the name sits exactly one symbol-height below the symbol
    assert both["caption:tuning:primes"].y == both["symbol:tuning:primes"].y + spreadsheet.SYMBOL_H


def test_folding_a_row_drops_its_symbols_with_the_rest_of_its_content():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["symbols"] = True
    cells = {c.id for c in spreadsheet.build(base, s, collapsed={"row:tuning"}).cells}
    assert not any(c.startswith("symbol:tuning:") for c in cells)  # the folded row sheds its symbols
    assert "symbol:just:primes" in cells  # ...while open siblings keep theirs


def test_comma_column_symbols_are_map_times_basis_products():
    on = {c.id: c for c in _with(symbols=True, names=True).cells}
    # the comma basis C lives in the interval-vectors row; the comma column has no
    # dedicated letters, so the rest are products of the maps and that basis
    assert on["symbol:vectors:commas"].text == "C"    # comma basis
    assert on["symbol:mapping:commas"].text == "𝑀C"   # mapped comma basis
    assert on["symbol:tuning:commas"].text == "𝒕C"    # tempered comma sizes
    assert on["symbol:just:commas"].text == "𝒋C"      # just comma sizes
    assert on["symbol:retune:commas"].text == "𝒓C"    # comma retunings
    # the comma symbol still aligns with the prime symbol in the same row
    assert on["symbol:tuning:commas"].y == on["symbol:tuning:primes"].y


def test_other_intervals_of_interest_column_carries_no_symbols():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["symbols"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s, interest=((-1, 1, 0),)).cells}
    # the interest column gets no symbols at all, even with the column populated
    assert not any(c.startswith("symbol:") and c.endswith(":interest") for c in cells)
    # its caption still lines up with the symboled columns (the slot stays reserved)
    assert cells["caption:tuning:interest"].y == cells["caption:tuning:primes"].y


def test_counts_row_reserves_no_symbol_slot_so_its_captions_dont_shift():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    def caps(symbols):
        s = settings.defaults()
        s["counts"], s["symbols"] = True, symbols
        return {c.id: c for c in spreadsheet.build(base, s).cells}

    on, off = caps(symbols=True), caps(symbols=False)
    # the counts row carries no symbol (its r/d/n/k ride the value cells), so turning
    # symbols on must not reserve a slot that would drift its captions down
    assert not any(c.startswith("symbol:counts:") for c in on)
    assert on["caption:counts:primes"].y == off["caption:counts:primes"].y


def test_every_implemented_toggle_actually_changes_the_layout():
    # a toggle is "implemented" (live, not greyed, in the Show panel) only if it has built
    # content — with its parent chain on, flipping the toggle must visibly change the grid
    # (cells/blocks added/removed/moved or their text/kind changed). The converse needn't
    # hold: a built feature may be shelved out of IMPLEMENTED (e.g. alt. complexity), so it
    # changes the layout yet stays greyed — hence we only sweep the IMPLEMENTED toggles here.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    def snapshot(s):
        # capture both cells and blocks: most toggles add/move cells, but colorization
        # is expressed purely through blocks (the colour washes), so a cells-only
        # snapshot would call it a no-op
        lay = spreadsheet.build(base, s)
        return (
            frozenset((c.id, c.x, c.y, c.w, c.h, c.kind, c.text, c.underlines) for c in lay.cells),
            frozenset((b.id, b.x, b.y, b.w, b.h, b.tint) for b in lay.blocks),
        )

    def with_parents_on(key):
        # a sub-control only takes effect while its parent chain is on (e.g. alt. complexity
        # needs weighting, which needs tuning boxes), so enable that chain before flipping it
        s = settings.defaults()
        parent = settings.SUBCONTROLS.get(key)
        while parent:
            s[parent] = True
            parent = settings.SUBCONTROLS.get(parent)
        return s

    for key in settings.IMPLEMENTED:
        on, off = with_parents_on(key), with_parents_on(key)
        on[key], off[key] = True, False
        assert snapshot(on) != snapshot(off), f"{key} is marked implemented but changes nothing"


def test_equivalences_extend_the_symbol_line_with_the_defining_equation():
    on = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
    sym_only = {c.id: c for c in _with(symbols=True, equivalences=False).cells}
    # equivalences appends the "= …" continuation to the symbol, in the same cell —
    # no separate equation cell. Glyphs match SYMBOLS (𝒕 = 𝒈𝑀, not faux-styled)
    assert sym_only["symbol:tuning:primes"].text == "𝒕"
    assert on["symbol:tuning:primes"].text == "𝒕 = 𝒈𝑀"
    assert on["symbol:retune:primes"].text == "𝒓 = 𝒕 − 𝒋"
    assert on["symbol:mapping:targets"].text == "Y = 𝑀T"
    assert not any(c.startswith("equivalence:") for c in on)


def test_equivalences_cover_derived_quantities_but_not_the_fundamentals():
    on = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
    extended = {c.split("symbol:", 1)[1] for c in on
                if c.startswith("symbol:") and " = " in on[c].text}
    assert extended == {
        "mapping:commas", "mapping:targets", "tuning:primes", "tuning:targets",
        "just:targets", "retune:primes", "retune:targets", "damage:targets",
    }
    # the temperament mapping and just tuning map have no buildable continuation yet
    # (theirs need the canonical-form / superspace features), so their symbol is bare
    assert on["symbol:mapping:primes"].text == "𝑀"
    assert on["symbol:just:primes"].text == "𝒋"


def test_equivalences_alone_render_the_symbol_line_only_where_there_is_an_equation():
    eq_only = {c.id: c for c in _with(names=False, symbols=False, equivalences=True).cells}
    # the equation needs its left-hand side, so equivalences renders the symbol line
    # (symbol + continuation) even with symbols and names both off...
    assert eq_only["symbol:tuning:primes"].text == "𝒕 = 𝒈𝑀"
    # ...but only where there is a continuation to show — a bare symbol is the
    # symbols feature's job, so the equation-less fundamentals stay absent
    assert "symbol:mapping:primes" not in eq_only
    assert "symbol:just:primes" not in eq_only
    assert not any(c.startswith("caption:") for c in eq_only)  # names is off here


def test_symbols_labels_each_matrix_row_or_column_with_a_subscripted_glyph():
    # Symbols on doesn't just put the matrix's name (𝑀, C, 𝒕, …) below the cells; it
    # also labels each individual row/column of the matrix with a subscripted version
    # of that name, per the maximized mockup. A covector stack labels its ROWS at the
    # left of each row's ⟨ bracket; every other multi-value tile labels its COLUMNS
    # above each cell.
    on = {c.id: c for c in _with(symbols=True, names=True).cells}
    off = {c.id: c for c in _with(symbols=False).cells}

    # The mapping matrix 𝑀 is a stack of two covector rows (one per generator), each
    # labelled 𝒎ᵢ at the left of its ⟨ — the bold-italic lowercase of 𝑀
    assert on["matlabel:row:mapping:primes:0"].text == "𝒎₁"
    assert on["matlabel:row:mapping:primes:1"].text == "𝒎₂"

    # The comma basis C is a single column vector here (one comma), labelled 𝐜₁ above
    # the cell — the bold-upright lowercase of C
    assert on["matlabel:col:vectors:commas:0"].text == "𝐜₁"
    # The target interval list T over the default 8 targets → 𝐭₁…𝐭₈
    assert on["matlabel:col:vectors:targets:0"].text == "𝐭₁"
    assert on["matlabel:col:vectors:targets:7"].text == "𝐭₈"

    # A single-row map's cells are labelled by their column index — the tuning map 𝒕
    # over d=3 primes → 𝒕₁, 𝒕₂, 𝒕₃ (the symbol IS the label letter; only the index changes)
    assert on["matlabel:col:tuning:primes:0"].text == "𝒕₁"
    assert on["matlabel:col:tuning:primes:2"].text == "𝒕₃"

    # Compound symbols keep the prefix and lowercase only the trailing vector letter:
    # 𝒕C → 𝒕𝐜ᵢ, 𝑀C → 𝑀𝐜ᵢ
    assert on["matlabel:col:tuning:commas:0"].text == "𝒕𝐜₁"
    assert on["matlabel:col:mapping:commas:0"].text == "𝑀𝐜₁"

    # The mapped target list Y is itself a list of vectors, so its column label is
    # the renamed bold-upright 𝐲 + subscript
    assert on["matlabel:col:mapping:targets:0"].text == "𝐲₁"   # Y → 𝐲
    # The six target SIZE lists hold SCALARS per cell, so each indexed label is the
    # bare PLAIN-ASCII letter (neither bold nor italic) — the bold form names the list
    # (𝐚, 𝐨, 𝐞, 𝒘, 𝐝, 𝒄); the indexed scalar is a/o/e/w/d/c. Plain ASCII passes through
    # _math_html as plain serif text, with the index subscripted via Unicode.
    assert on["matlabel:col:tuning:targets:0"].text == "a₁"    # tempered target sizes
    assert on["matlabel:col:just:targets:0"].text == "o₁"      # just target sizes
    assert on["matlabel:col:retune:targets:0"].text == "e₁"    # target retunings
    assert on["matlabel:col:damage:targets:0"].text == "d₁"    # damage list

    # Symbols off drops every label, like the symbol/equivalence cells
    assert not any(c.startswith("matlabel:") for c in off)


def test_matrix_labels_index_match_their_matrix_size():
    # Each label set covers exactly its matrix's rows/columns — r=2 row labels for the
    # mapping, d=3 column labels for the tuning map, k=4 for the target list — so the
    # i-suffix on the ids tracks the live matrix and a relabel adds/drops in lockstep
    on = {c.id for c in _with(symbols=True).cells}
    assert {f"matlabel:row:mapping:primes:{i}" for i in range(2)} <= on
    assert "matlabel:row:mapping:primes:2" not in on   # only r=2 rows
    assert {f"matlabel:col:vectors:targets:{j}" for j in range(8)} <= on
    assert "matlabel:col:vectors:targets:8" not in on  # only k=8 targets in the default set
    assert {f"matlabel:col:tuning:primes:{p}" for p in range(3)} <= on
    assert "matlabel:col:tuning:primes:3" not in on    # only d=3 primes


def test_matrix_labels_only_emit_where_the_tile_is_open():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["symbols"] = True
    # the mapping row collapsed: its row labels vanish with the rest of its content,
    # while the interval-vectors row's column labels are unaffected
    cells = {c.id for c in spreadsheet.build(base, s, collapsed={"row:mapping"}).cells}
    assert not any(c.startswith("matlabel:row:mapping:") for c in cells)
    assert "matlabel:col:vectors:commas:0" in cells


def test_matrix_labels_sit_above_or_left_of_the_cells_they_label():
    on = {c.id: c for c in _with(symbols=True).cells}
    # a column label sits directly above the cell it labels (same x, smaller y)
    assert on["matlabel:col:tuning:primes:0"].x == on["tuning:prime:0"].x
    assert on["matlabel:col:tuning:primes:0"].y < on["tuning:prime:0"].y
    # a row label sits LEFT of the row's covector ⟨ bracket (same y band as the row,
    # smaller x than the bracket — both inside the mapping/primes tile)
    assert on["matlabel:row:mapping:primes:0"].x < on["bracket:map:0:l"].x
    # the row label vertically aligns with the row's value cells
    assert (on["matlabel:row:mapping:primes:0"].y <= on["cell:mapping:0:0"].y
            <= on["matlabel:row:mapping:primes:0"].y + on["matlabel:row:mapping:primes:0"].h)


def test_col_labels_sit_inside_the_tile_centred_above_the_bracket():
    # Per Douglas: col labels sit INSIDE the tile (nothing in the gaps between tiles),
    # roughly equidistant from the tile_top and the bracket below them. matlabel
    # starts at or below the logical tile top AND ends with visible space above the
    # matrix's top bracket.
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "symbols": True},
    )
    on = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    for tile_block_id, frame_id, label_id in [
        ("block:vec:commas", "vec:commas", "matlabel:col:vectors:commas:0"),
        ("block:vec:targets", "vec:targets", "matlabel:col:vectors:targets:0"),
        ("block:mapped", "mapped", "matlabel:col:mapping:targets:0"),
        ("block:mapped_comma", "mapped_comma", "matlabel:col:mapping:commas:0"),
    ]:
        label = on[label_id]
        ebktop = on[f"ebktop:{frame_id}:0"]
        tile_top = blocks[tile_block_id].y + spreadsheet.PAD  # logical top (panel overhangs by PAD)
        # the label sits INSIDE the tile (at or below tile_top), not above it in the GAP
        assert label.y >= tile_top - 1, \
            f"{label_id} (y={label.y}) must sit inside tile (top={tile_top}), not in the gap"
        # the label sits ABOVE the bracket (with the bracket clear below it)
        assert label.y + label.h <= ebktop.y, \
            f"{label_id} bottom y={label.y + label.h} must be at/above bracket y={ebktop.y}"
        # equidistance: distance from tile_top to label-top ≈ distance from label-bottom
        # to bracket-top (within 1px tolerance for int rounding)
        dist_above = label.y - tile_top
        dist_below = ebktop.y - (label.y + label.h)
        assert abs(dist_above - dist_below) <= 1, \
            f"{label_id}: dist_above={dist_above}, dist_below={dist_below} should be ~equal"


def test_col_labels_sit_above_the_top_frame_in_framed_rows():
    # In a framed row (interval vectors, mapping, prescaling), the col labels (𝐜ᵢ, 𝐲ᵢ,
    # …) MUST sit above the matrix's top bracket ─┐ — the labels name the columns the
    # bracket spans, so they read like a header over the matrix, not as decoration
    # squeezed into the bracket gutter.
    on = {c.id: c for c in _with(symbols=True).cells}
    # mapping matrix: top bracket (ebktop:primes) sits BELOW the row labels' band, and
    # the col labels for the mapping's mapped lists sit above their own ebktop marks
    assert on["matlabel:col:mapping:targets:0"].y + on["matlabel:col:mapping:targets:0"].h \
        <= on["ebktop:mapped:0"].y
    assert on["matlabel:col:mapping:commas:0"].y + on["matlabel:col:mapping:commas:0"].h \
        <= on["ebktop:mapped_comma:0"].y
    # interval vectors row: same rule — the comma basis 𝐜ᵢ labels sit above the basis's
    # per-column ket marks (ebktop:vec:commas:*)
    assert on["matlabel:col:vectors:commas:0"].y + on["matlabel:col:vectors:commas:0"].h \
        <= on["ebktop:vec:commas:0"].y
    assert on["matlabel:col:vectors:targets:0"].y + on["matlabel:col:vectors:targets:0"].h \
        <= on["ebktop:vec:targets:0"].y


def test_mapping_top_frame_hugs_the_cells_not_the_row_label_gutter():
    # The mapping matrix's outer top bracket ─┐ and bottom curly brace span ONLY the
    # cells (left of which the per-row ⟨ sits, in turn left of which the matlabel
    # gutter sits). Without this the bracket would be a MATLABEL_W wider than the
    # matrix, visually swallowing the 𝒎ᵢ labels.
    on = {c.id: c for c in _with(symbols=True).cells}
    ebktop = on["ebktop:primes"]
    ebkbrace = on["ebkbrace:primes"]
    left_bracket = on["bracket:map:0:l"]
    right_bracket = on["bracket:map:0:r"]
    # the top/brace's LEFT edge starts at the per-row ⟨'s left edge (both flush over
    # the cells), past the row-label gutter — never at col_x[primes]
    assert ebktop.x == left_bracket.x
    assert ebkbrace.x == left_bracket.x
    # the top/brace's RIGHT edge ends at the per-row ]'s right edge
    assert ebktop.x + ebktop.w == right_bracket.x + right_bracket.w
    assert ebkbrace.x + ebkbrace.w == right_bracket.x + right_bracket.w


def test_row_labels_balance_the_primes_tile_with_an_equal_right_gutter():
    # symbols on adds the 𝒎ᵢ / 𝒙ᵢ row-label gutter on the LEFT of the domain-primes matrix.
    # With no counterpart it shoves the matrix right-of-centre in its grey tile, so we mirror
    # it with an equal empty gutter on the RIGHT. The matrix's per-row ⟨ … ⟩ brackets then sit
    # centred in the primes tile (block:mapping), with a full label width of room each side.
    lay = _with(symbols=True)
    on = {c.id: c for c in lay.cells}
    panel = {b.id: b for b in lay.blocks}["block:mapping"]
    left = on["bracket:map:0:l"].x - panel.x
    right = (panel.x + panel.w) - (on["bracket:map:0:r"].x + on["bracket:map:0:r"].w)
    assert abs(left - right) < 0.01, f"primes matrix off-centre in its tile: left={left}, right={right}"
    assert left >= spreadsheet.MATLABEL_W  # the label gutter (and its mirror) reserve real room


def test_complexity_col_labels_spell_out_the_norm_definition():
    # Complexity is the q-norm of L (the prescaler) applied to each basis vector; per
    # the mockup each cell is labelled with that closed form rather than a bare 𝒄
    # subscript. The L is math-italic, the basis letter (𝐜/𝐡/𝐝/𝐭) bold-upright, the
    # index a Unicode subscript, and the trailing q a small post-norm subscript marker.
    # The PRIMES column uses bracket-index notation L[i] (each prime's column of L),
    # not a separate vector letter — there is no bold lowercase p in this scheme.
    # The TARGETS column is the named complexity list 𝒄, so its labels stay plain "c".
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["symbols"] = True
    s["weighting"] = True              # opens the complexity row
    s["optimization"] = True           # opens the held column
    s["generator_detempering"] = True  # opens the detempering column
    on = {c.id: c for c in spreadsheet.build(
        base, s, held_vectors=((-1, 1, 0),)
    ).cells}
    # The trailing q is italic-subscripted (per the mockup) — emitted with sentinel
    # markers around it that the matlabel renderer converts to <sub><i>q</i></sub>.
    q = spreadsheet.NORM_SUB_OPEN + "q" + spreadsheet.NORM_SUB_CLOSE
    assert on["matlabel:col:complexity:primes:0"].text == f"‖𝐿[1]‖{q}"
    assert on["matlabel:col:complexity:primes:2"].text == f"‖𝐿[3]‖{q}"
    assert on["matlabel:col:complexity:commas:0"].text == f"‖𝐿𝐜₁‖{q}"
    assert on["matlabel:col:complexity:held:0"].text == f"‖𝐿𝐡₁‖{q}"
    assert on["matlabel:col:complexity:detempering:0"].text == f"‖𝐿𝐝₁‖{q}"
    # complexity over targets is the named complexity LIST 𝒄 — each cell a scalar
    # entry, so the label is plain "c" (no styling, like the other size lists)
    assert on["matlabel:col:complexity:targets:0"].text == "c₁"


def test_prescaling_matrix_row_and_col_labels():
    # The bare prescaler matrix is a covector stack like 𝑀. Its big symbol stays the abstract 𝑋,
    # but every LABEL takes the concrete glyph the matrix realises — 𝑋 = 𝐿 by default (the log-prime
    # matrix) — so the rows read 𝒍ᵢ (lowercase 𝐿, one per dimension, parallel to 𝒎ᵢ on the mapping)
    # and the products get COLUMN labels 𝐿𝐜ᵢ / 𝐿𝐡ᵢ / 𝐿𝐝ᵢ / 𝐿𝐭ᵢ — never the generic 𝒙/𝑋, which
    # would mix with the 𝐿 in the same tile.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["symbols"] = True
    s["weighting"] = True
    s["optimization"] = True
    s["generator_detempering"] = True
    on = {c.id: c for c in spreadsheet.build(
        base, s, held_vectors=((-1, 1, 0),)
    ).cells}
    # row labels: d=3 rows, one 𝒍ᵢ per dimension (the lowercase of the realised 𝐿)
    assert on["matlabel:row:prescaling:primes:0"].text == "𝒍₁"
    assert on["matlabel:row:prescaling:primes:1"].text == "𝒍₂"
    assert on["matlabel:row:prescaling:primes:2"].text == "𝒍₃"
    # col labels on the prescaled product lists: 𝐿·basis, 𝐿·detempering, 𝐿·held, 𝐿·targets
    assert on["matlabel:col:prescaling:commas:0"].text == "𝐿𝐜₁"
    assert on["matlabel:col:prescaling:held:0"].text == "𝐿𝐡₁"
    assert on["matlabel:col:prescaling:detempering:0"].text == "𝐿𝐝₁"
    assert on["matlabel:col:prescaling:targets:0"].text == "𝐿𝐭₁"


def test_units_annotate_each_box_with_its_unit_string():
    on = {c.id: c for c in _with(units=True, names=True).cells}
    off = {c.id: c for c in _with(units=False).cells}
    # the per-box units line, parallel to the symbol/caption, reads "units: <value>"
    # in plain ASCII (g/p/¢) — the view styles the value bold in a single-story-g
    # sans face, keeping "units:" in the serif body face (see app._units_html)
    assert on["units:tuning:gens"].text == "units: ¢/g"    # generator tuning map ¢/g
    assert on["units:tuning:primes"].text == "units: ¢/p"  # (prime) tuning map ¢/p
    assert on["units:mapping:primes"].text == "units: g/p"  # mapping matrix g/p
    assert on["units:mapping:targets"].text == "units: g"  # mapped target list g
    assert on["units:vectors:targets"].text == "units: p"  # target interval list p
    assert on["units:damage:targets"].text == "units: ¢"   # damage list ¢
    # nothing rendered when units is off
    assert not any(c.startswith("units:") for c in off)
    # the units line sits below the name caption for the same box
    assert on["units:tuning:primes"].y > on["caption:tuning:primes"].y


def test_units_carry_a_per_value_unit_on_each_gridded_cell():
    on = {c.id: c for c in _with(units=True, weighting=True).cells}
    off = {c.id: c for c in _with(units=False, weighting=True).cells}
    # each gridded value cell carries its coordinate-specialized unit: the tile's unit
    # with its variables subscripted by the cell's generator/prime index (the mockup's
    # g/p mapping tile reads g₁/p₁ in its top-left cell)
    assert on["cell:mapping:0:0"].unit == "g₁/p₁"
    assert on["cell:mapping:1:2"].unit == "g₂/p₃"   # generator 2 over prime 3
    assert on["tuning:prime:0"].unit == "¢/p₁"       # tuning map over primes: cents per prime
    assert on["tuning:gen:0"].unit == "¢/g₁"         # generator tuning map: cents per generator
    assert on["tuning:target:0"].unit == "¢"         # a size list: plain cents, no index
    assert on["cell:mapped:0:0"].unit == "g₁"        # mapped target list: generators (gen index)
    assert on["cell:vec:targets:0:0"].unit == "p₁"   # interval vector: prime component
    # the prescaler matrix's per-cell unit is octaves per its COLUMN's prime (oct/p), so the
    # p subscripts by the column — its diagonal reads oct/pᵢ, and an off-diagonal zero tracks
    # its column's prime, not its row (the matrix's d columns are the d domain primes)
    assert on["cell:prescaling:primes:0:0"].unit == "oct/p₁"  # diagonal: log₂2 in oct/p₁
    assert on["cell:prescaling:primes:1:1"].unit == "oct/p₂"  # diagonal: log₂3 in oct/p₂
    assert on["cell:prescaling:primes:0:1"].unit == "oct/p₂"  # off-diagonal in prime-2 column
    assert on["complexity:prime:0"].unit == "(C)/p₁"          # complexity map: (C) per prime
    # the unit is absent when units is off
    assert all(not c.unit for c in off.values())


def test_domain_units_adds_a_units_row_and_column_of_coordinate_labels():
    on = {c.id: c for c in _with(domain_units=True).cells}
    off = {c.id: c for c in _with(domain_units=False).cells}
    # the units COLUMN (a spine column right after quantities) labels each row's
    # coordinate: the interval-vectors basis in primes (pᵢ/), the mapping in
    # generators (gᵢ/), and the cents tuning rows as ¢/
    assert on["ucol:vectors:0"].text == "p₁/"   # p₁/
    assert on["ucol:vectors:2"].text == "p₃/"   # p₃/
    assert on["ucol:mapping:0"].text == "g₁/"   # g₁/
    assert on["ucol:tuning"].text == "¢/"
    assert on["ucol:damage"].text == "¢/"
    # the units ROW (a spine row right after quantities) labels each column's
    # coordinate: /gᵢ over the generators, /pᵢ over the domain primes, /1 over the
    # ratio columns (commas, targets)
    assert on["urow:gens:0"].text == "/g₁"      # /g₁
    assert on["urow:primes:0"].text == "/p₁"    # /p₁
    assert on["urow:primes:2"].text == "/p₃"    # /p₃
    assert on["urow:targets:0"].text == "/1"
    # the labels line up with the coordinates they annotate
    assert on["urow:primes:0"].x == on["prime:0"].x   # /p₁ under the first prime column
    assert on["ucol:vectors:0"].y == on["basis:0"].y  # p₁/ beside the first basis prime
    assert on["ucol:mapping:0"].y == on["gen:0"].y    # g₁/ beside the first generator
    # header + label for the new band
    assert "header:units" in on and "label:units" in on
    # none of it when the toggle is off
    assert not any(c.startswith(("ucol:", "urow:")) for c in off)
    assert "header:units" not in off and "label:units" not in off
    # geometry: the units column sits between quantities and generators; the units
    # row sits between the quantities row and the interval-vectors row
    assert on["header:quantities"].x < on["header:units"].x < on["header:gens"].x
    assert on["label:quantities"].y < on["label:units"].y < on["label:vectors"].y


def test_optimization_box_sits_at_the_bottom_of_the_damage_tile():
    # per the mockup, the optimization controls live INSIDE the target interval damage list
    # tile as a bordered, titled box — not a separate row — laid out as two value-over-label
    # columns (the objective ⟪𝐝⟫ₚ and the editable power 𝑝) with the optimize button at right.
    lay = _with(optimization=True)
    on = {c.id: c for c in lay.cells}
    assert on["optimization:title"].text == "optimization"
    # the objective: a cents value over the symbol ⟪𝐝⟫ₚ (double-angle brackets, power subscript)
    assert on["optimization:objective"].kind == "tval"
    assert on["optimization:objective:symbol"].text == "⟪𝐝⟫ₚ"
    # the power: an editable field over the symbol 𝑝 and the "optimization power" caption
    assert on["optimization:power"].kind == "powerinput"            # the power is editable
    assert on["optimization:power"].text == "∞"                     # ...showing the current Lp order
    assert on["optimization:power:symbol"].text == "𝑝"
    assert on["optimization:power:caption"].text == "optimization power"
    assert on["optimization:button"].text == "optimize"
    # the box sits below the damage values, in the target intervals column
    assert on["optimization:title"].y > on["damage:target:0"].y
    assert on["optimization:title"].x == on["header:targets"].x
    # ...and there is no separate optimization row
    assert "label:optimization" not in on
    assert "h:optimization" not in {ln.id for ln in lay.lines}


def test_optimization_hint_invites_unlock_once_the_auto_lock_is_latched():
    # the optimize button's hint reads "double-click to lock" by default; once the auto-
    # optimize lock is latched on, the next double-click UNlocks it, so the hint flips to match
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    unlocked = {c.id: c for c in spreadsheet.build(base, s).cells}
    locked = {c.id: c for c in spreadsheet.build(base, s, optimize_locked=True).cells}
    assert unlocked["optimization:button:hint"].text == "double-click to lock"
    assert locked["optimization:button:hint"].text == "double-click to unlock"


def test_optimization_power_field_reflects_the_current_scheme():
    # the power field shows the *current* scheme's Lp order: ∞ for minimax, 2 for
    # least-squares (miniRMS)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    ls = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="least squares").cells}
    assert ls["optimization:power"].text == "2"  # miniRMS ⇒ p = 2


def test_optimization_needs_its_parent_tuning_boxes():
    # optimization is a sub-control of tuning boxes: with the tuning region hidden
    # there is nothing to annotate, so the box stays away even when toggled on
    cells = {c.id for c in _with(optimization=True, tuning_boxes=False).cells}
    assert "optimization:power" not in cells
    assert "optimization:title" not in cells


def test_optimization_box_lays_out_objective_power_and_button_in_columns():
    lay = _with(optimization=True)
    on = {c.id: c for c in lay.cells}
    box = {b.id: b for b in lay.blocks}["block:optimization:box"]
    # the three controls sit on one row, left to right: objective | power | optimize button
    assert on["optimization:objective"].x < on["optimization:power"].x < on["optimization:button"].x
    assert on["optimization:objective"].y == on["optimization:power"].y == on["optimization:button"].y
    # within each column the value/control sits above its symbol/label
    assert on["optimization:objective"].y < on["optimization:objective:symbol"].y
    assert (on["optimization:power"].y < on["optimization:power:symbol"].y
            < on["optimization:power:caption"].y)
    # the min-damage and the power are ordinary gridded cells (COL_W wide); their contents are
    # centred like any other value cell (not stretched/left-justified within the control)
    assert on["optimization:objective"].w == spreadsheet.COL_W
    assert on["optimization:power"].w == spreadsheet.COL_W
    # the controls DISTRIBUTE across the full-width box (no longer packed left): the objective
    # hugs the left edge, the optimize button hugs the right edge, and the power sits centered
    # in the gap between them, so its "optimization power" caption has clear room either side
    assert on["optimization:objective"].x == box.x + spreadsheet.OPT_PAD_L
    assert (on["optimization:button"].x + on["optimization:button"].w
            == box.x + box.w - spreadsheet.OPT_PAD_R)
    obj_r = on["optimization:objective"].x + on["optimization:objective"].w
    btn_l = on["optimization:button"].x
    pow_c = on["optimization:power"].x + on["optimization:power"].w / 2
    assert abs(pow_c - (obj_r + btn_l) / 2) < 1  # power centered in the gap between the two
    cap = on["optimization:power:caption"]
    assert cap.x > obj_r and cap.x + cap.w < btn_l  # ...and its caption clears both neighbors
    # the optimize button is a normal rectangle the same height as the value boxes (the p input),
    # not a giant full-height button, with a "double-click to lock" hint beneath it
    assert on["optimization:button"].h == on["optimization:objective"].h
    assert on["optimization:button:hint"].text == "double-click to lock"
    assert on["optimization:button:hint"].y > on["optimization:button"].y
    # the captions occupy a single line (so "optimization power" sits right under 𝑝, not a
    # two-line band that floats it lower), and so does the hint
    assert on["optimization:power:caption"].h == spreadsheet.CAPTION_LINE
    assert on["optimization:button:hint"].h == spreadsheet.CAPTION_LINE
    # the title sits inside the box (below its top border) with a gap before the controls
    assert on["optimization:title"].y > box.y
    assert on["optimization:objective"].y > on["optimization:title"].y + on["optimization:title"].h
    assert "optimization:button" not in {c.id for c in _with(optimization=False).cells}


def test_optimization_box_fills_the_full_width_of_the_damage_tile():
    # the box no longer hugs its controls — it spans the entire target interval damage list
    # tile (like the tuning-ranges box spans the generator tuning map tile), giving the
    # controls room to spread out across it
    lay = _with(optimization=True)
    blk = {b.id: b for b in lay.blocks}
    box = blk["block:optimization:box"]
    panel = blk["block:damage:targets"]  # the damage tile's grey panel
    assert box.x == panel.x + spreadsheet.PAD  # the box starts at the tile's content left edge
    assert box.w == panel.w - 2 * spreadsheet.PAD  # ...and fills the tile's content width


def test_a_narrow_damage_tile_widens_to_seat_the_optimization_box():
    # a 3-limit temperament targets few intervals, so its damage tile would be narrower than
    # the optimization box's spread-out controls; turning optimization on floors the targets
    # column so the box (and thus the whole tile) is wide enough to seat them
    base = service.from_mapping(((1, 1), (0, 1)))
    s = settings.defaults()
    s["optimization"] = True
    blk = {b.id: b for b in spreadsheet.build(base, s).blocks}
    box = blk["block:optimization:box"]
    assert box.w >= spreadsheet.OPT_BOX_MIN_W  # wide enough to seat objective | power | button
    assert box.w == blk["block:damage:targets"].w - 2 * spreadsheet.PAD  # still fills its tile


def test_a_manual_generator_tuning_drives_the_displayed_maps():
    # a frozen manual generator tuning (optimize lock off) drives the tuning maps directly, not the
    # scheme optimum: a pure octave + pure fifth tunes prime 3 (= g0 + g1) to exactly the just fifth
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    manual = {c.id: c for c in spreadsheet.build(base, s, generator_tuning=(1200.0, 701.955)).cells}
    assert manual["tuning:prime:1"].text == "1901.955"          # prime 3 = g0 + g1 = the pure fifth
    # the default optimum tempers the fifth, so it differs
    auto = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert auto["tuning:prime:1"].text != "1901.955"


def test_typing_the_generator_tuning_map_drives_the_grid_through_the_editor():
    # the editable generator tuning map: a typed cents tuning, applied via the editor, drives
    # the built tuning maps just like a frozen manual tuning -- the hybrid input end to end
    editor = Editor()
    assert editor.set_generator_tuning_text("{1200.000 700.000]") is True
    cells = {c.id: c for c in spreadsheet.build(
        editor.state, editor.settings, tuning_scheme=editor.tuning_scheme,
        generator_tuning=editor.effective_generator_tuning()).cells}
    # meantone g=(1200,700): prime 2 = g0, prime 3 = g0+g1, prime 5 = 4*g1
    assert cells["tuning:prime:0"].text == "1200.000"
    assert cells["tuning:prime:1"].text == "1900.000"
    assert cells["tuning:prime:2"].text == "2800.000"


def test_generator_tuning_map_cells_are_editable_inputs():
    # each generator-tuning-map cell is an editable per-generator override, not a read-only value
    cells = {c.id: c for c in _layout().cells}
    assert cells["tuning:gen:0"].kind == "gentuningcell"
    assert cells["tuning:gen:1"].kind == "gentuningcell"


def test_a_target_override_drives_the_target_columns():
    # a typed explicit target list replaces the TILT/OLD set everywhere it flows: the ratios,
    # the vector cells, and the tempered/just/damage size lists all show exactly the two intervals
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    cells = {c.id: c for c in spreadsheet.build(base, s, target_override=("2/1", "3/2")).cells}
    assert cells["target:0"].text == "2/1" and cells["target:1"].text == "3/2"
    assert "target:2" not in cells  # exactly two columns
    assert cells["cell:vec:targets:0:0"].kind == "targetcell"  # the editable vector cells
    for row in ("tuning", "just", "damage"):  # the size lists follow the override (two columns)
        assert f"{row}:target:1" in cells and f"{row}:target:2" not in cells


def test_a_target_override_retunes_the_generator_map():
    # the grid's auto-optimized tuning minimizes over the target intervals, so a typed override
    # retunes the generator map itself — not just the displayed target columns. Same fix as the
    # optimize button: targeting only 2/1 + 3/2 under minimax-U pulls the fifth toward just.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    plain = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-U", target_spec="TILT").cells}
    overridden = {c.id: c for c in spreadsheet.build(
        base, s, tuning_scheme="TILT minimax-U", target_spec="TILT", target_override=("2/1", "3/2")).cells}
    assert overridden["tuning:gen:1"].text != plain["tuning:gen:1"].text


def test_target_interval_list_cells_and_plain_text_are_editable():
    cells = {c.id: c for c in _with(plain_text_values=True).cells}
    assert cells["ptext:vectors:targets"].kind == "ptextedit"
    assert cells["cell:vec:targets:0:0"].kind == "targetcell"


def test_typing_the_target_interval_list_drives_the_grid_through_the_editor():
    # the editable target interval list end to end: a typed vector list, applied via the editor,
    # drives the built target columns (the hybrid override)
    editor = Editor()
    assert editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩") is True
    cells = {c.id: c for c in spreadsheet.build(
        editor.state, editor.settings, tuning_scheme=editor.tuning_scheme,
        target_override=editor.target_override).cells}
    assert cells["target:0"].text == "2/1" and cells["target:1"].text == "3/2"
    assert "target:2" not in cells


def test_optimization_draws_the_minimized_damage_indicator_on_the_chart():
    # optimization adds a horizontal indicator at the minimized-damage level (the
    # objective ⟪𝐝⟫ₚ: max damage for the default minimax) to the damage chart
    on = {c.id: c for c in _with(optimization=True, charts=True).cells}
    chart = on["chart:damage:targets"]
    assert chart.indicator is not None
    assert chart.indicator == max(chart.values)  # minimax: the minimized maximum damage
    # ...and there is no indicator without optimization
    off = {c.id: c for c in _with(optimization=False, charts=True).cells}
    assert off["chart:damage:targets"].indicator is None


def test_optimization_indicator_carries_the_power_as_its_subscript_label():
    # the damage chart's minimized-damage line is labelled ⟪𝐝⟫ with the scheme's Lp order
    # as the subscript — ∞ for the default minimax — carried as the bare power so the
    # renderer can draw the (bold 𝐝, double-angle) label breaking the line.
    on = {c.id: c for c in _with(optimization=True, charts=True).cells}
    assert on["chart:damage:targets"].indicator_label == "∞"
    # a miniRMS (least-squares) scheme subscripts it with 2
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"], s["charts"] = True, True
    rms = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="least squares").cells}
    assert rms["chart:damage:targets"].indicator_label == "2"
    # ...and no label on a non-optimization chart (or with optimization off)
    off = {c.id: c for c in _with(optimization=False, charts=True).cells}
    assert off["chart:damage:targets"].indicator_label == ""


def test_optimization_box_is_a_bordered_frame_nested_in_the_damage_tile():
    # the optimization box is a thin-bordered frame (like the tuning-ranges box) nested
    # inside the damage×targets tile's grey panel, which grows to enclose it
    lay = _with(optimization=True)
    blocks = {b.id: b for b in lay.blocks}
    box = blocks["block:optimization:box"]
    assert box.boxed
    panel = blocks["block:damage:targets"]
    assert panel.y <= box.y and box.y + box.h <= panel.y + panel.h  # nested within the panel


def test_optimization_on_adds_an_addable_held_intervals_column():
    on = {c.id: c for c in _with(optimization=True).cells}
    off = {c.id for c in _with(optimization=False).cells}
    # the optimization box's held interval constraints get their own column...
    assert "header:held" in on
    assert "header:held" not in off
    # ...riding between the commas and the target intervals columns (per the mockup)
    assert on["header:commas"].x < on["header:held"].x < on["header:targets"].x
    # ...and a + to add the first held interval even when the column is empty, exactly
    # like the other-intervals-of-interest column
    assert "held_plus" in on
    assert "held_plus" not in off


def test_held_intervals_are_a_user_editable_counted_interval_list():
    # the held column is a user-edited vector list (like the intervals of interest): each
    # held interval heads its column as a derived ratio, with EDITABLE vector cells below
    # and its own − to remove it; the held count h tracks how many there are
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"], s["counts"] = True, True
    cells = {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}
    assert cells["held:0"].text == "3/2"               # the derived ratio (3/2) heads the column
    assert cells["cell:held:0:0"].kind == "heldcell"   # the vector cells are editable inputs
    assert [cells[f"cell:held:{p}:0"].text for p in range(3)] == ["-1", "1", "0"]
    assert "held_minus:0" in cells                     # each held interval is removable
    assert cells["count:held"].text == "ℎ = 1"         # h = 1 (Planck-glyph math-italic h)
    # empty by default: no held interval tiles, count h = 0
    empty = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert empty["count:held"].text == "ℎ = 0"
    assert not any(c.startswith(("held:", "cell:held:")) for c in empty)


def test_held_intervals_show_across_the_rows_like_the_other_intervals():
    # the held column is a full interval list (not just quantities + vectors): mapped through
    # M and sized across the tuning/just/retuning rows, like the other-intervals column
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}
    assert "cell:hmapped:0:0" in cells   # M·held in the mapping row
    assert "tuning:held:0" in cells      # tempered size
    assert "just:held:0" in cells        # just size
    assert "retune:held:0" in cells      # error
    # the held fifth is tuned exactly just, so its error reads ~0
    assert abs(float(cells["retune:held:0"].text)) < 1e-3


def _held(**overrides):
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    s.update(overrides)
    return {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}


def test_held_column_symbols_are_map_times_basis_products():
    on = _held(symbols=True, names=True)
    # the held interval basis H lives in the interval-vectors row; like the comma column,
    # the held column has no dedicated letters — the rest are products of the maps and H
    assert on["symbol:vectors:held"].text == "H"     # held interval basis
    assert on["symbol:mapping:held"].text == "𝑀H"    # mapped held interval basis
    assert on["symbol:tuning:held"].text == "𝒕H"     # tempered held sizes
    assert on["symbol:just:held"].text == "𝒋H"       # just held sizes
    assert on["symbol:retune:held"].text == "𝒓H"     # held retunings (errors)


def test_held_column_captions_are_full_held_interval_names():
    on = _held(names=True, weighting=True)  # weighting opens the prescaling + complexity rows
    # full descriptive names mirroring the comma column ("held interval basis" in place of
    # "comma basis"), without the comma column's "(made to vanish!)" — held intervals are held
    # just, not vanished
    assert on["caption:vectors:held"].text == "held interval basis"
    assert on["caption:mapping:held"].text == "mapped held interval basis"
    assert on["caption:tuning:held"].text == "tempered held interval basis interval size list"
    assert on["caption:just:held"].text == "(just) held interval basis interval size list"
    assert on["caption:retune:held"].text == "held interval basis interval retuning list"
    assert on["caption:prescaling:held"].text == "complexity prescaled held interval basis"
    assert on["caption:complexity:held"].text == "held interval basis interval complexity list"


def test_held_interval_basis_caption_mnemonic_underlines_its_symbol_letter():
    on = _held(names=True, mnemonics=True)
    cap = on["caption:vectors:held"]
    # the held interval basis H underlines the h of "held" (like the comma basis C -> c)
    assert cap.underlines == ((cap.text.index("held"), 1),)


def test_held_column_equivalences_show_the_held_just_identities():
    on = _held(symbols=True, equivalences=True)
    # held intervals are tuned exactly just: the tempered size equals the just size (and the
    # just size equals the tempered — the inverse identity, shown on the just row just below),
    # so the retuning error vanishes to the zero list
    assert on["symbol:tuning:held"].text == "𝒕H = 𝒋H"
    assert on["symbol:just:held"].text == "𝒋H = 𝒕H"
    assert on["symbol:retune:held"].text == "𝒓H = 𝟎"


def _held_value_cells():
    # every per-interval value cell of the held column (the ratio, its vector, the mapped
    # column, the three size rows, and the weighting rows) — the cells that, together, ARE the
    # held interval. NOT the column furniture (header, count, symbols, captions, − control).
    return ("held:0", "cell:held:0:0", "cell:hmapped:0:0", "tuning:held:0",
            "just:held:0", "retune:held:0", "cell:prescaling:held:0:0", "complexity:held:0")


def _held_with_tuning(generator_tuning):
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"], s["weighting"] = True, True  # weighting opens the prescaling + complexity rows
    return {c.id: c for c in spreadsheet.build(
        base, s, held_vectors=[(-1, 1, 0)], generator_tuning=generator_tuning).cells}


def test_unheld_held_interval_is_flagged_red_across_its_value_cells():
    # a held interval the current (frozen) generator tuning does NOT tune just is flagged for
    # red rendering across its WHOLE interval — the user has changed something so the tuning no
    # longer holds it. Here the frozen genmap (1200¢ period, 700¢ fifth) leaves the held fifth
    # 3/2 ~1.955¢ flat, so its retuning error reads nonzero.
    cells = _held_with_tuning((1200.0, 700.0))
    for cid in _held_value_cells():
        assert cells[cid].alert, cid
    # the column's furniture stays black — only the interval itself reddens
    assert not cells["header:held"].alert
    assert not cells["held_minus:0"].alert


def test_held_interval_held_to_display_precision_is_not_flagged():
    # typing the *displayed* optimum (701.955¢, the rounded value the app shows) leaves a sub-
    # milli-cent residual that still reads 0.000 — the interval is held to display precision, so
    # NOT red. The red follows the shown retuning error, never hidden float noise.
    cells = _held_with_tuning((1200.0, 701.955))
    assert cells["retune:held:0"].text in ("0.000", "-0.000")  # reads as zero error
    for cid in _held_value_cells():
        assert not cells[cid].alert, cid


def test_held_interval_actually_held_stays_black():
    # a generator tuning that tunes the held fifth exactly just (its optimum) — the happy state
    # clicking optimize restores — flags nothing; nor does the default auto-optimized path, which
    # folds the held interval into the solve so it comes out just on its own.
    exact = _held_with_tuning((1200.0, 701.9550008653873))
    for cid in _held_value_cells():
        assert not exact[cid].alert, cid
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    auto = {c.id: c for c in spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)]).cells}
    assert not auto["retune:held:0"].alert  # no frozen tuning ⇒ re-optimized to hold it ⇒ black


def test_held_column_shows_plain_text_values():
    on = _held(plain_text_values=True)
    # the held column's tiles get plain-text EBK boxes like every other value tile
    assert on["ptext:vectors:held"].text == "[[-1 1 0⟩]"   # the held basis (vector list)
    assert on["ptext:mapping:held"].text == "[[0 1}]"      # mapped into generator coords
    assert "ptext:tuning:held" in on and "ptext:just:held" in on
    # held just ⇒ the retuning error vanishes
    assert abs(float(on["ptext:retune:held"].text.strip("[]"))) < 1e-3
    # the quantities tile (the ratio heading the column) gets per-column plain text too,
    # like the commas / targets columns
    assert on["ptext:quantities:held:0"].text == "3/2"


def test_held_column_has_the_full_interval_column_tile_set():
    # the held column mirrors the intervals-of-interest column's FULL tile set: besides the
    # vectors / mapping / sizes / complexity tiles, it gets the units-row label, the complexity-
    # prescaling matrix, and the just / tempered audio rows (each gated on its own toggle)
    on = _held(weighting=True, audio=True, domain_units=True)
    assert "cell:prescaling:held:0:0" in on     # the complexity-prescaling matrix over the held interval
    assert "speaker:just_audio:held:0" in on    # the just audio row sounds the held interval
    assert "speaker:tempered_audio:held:0" in on  # the tempered audio row
    assert "urow:held:0" in on                  # the units row's /1 over the held column


def test_generator_detempering_column_holds_the_d_matrix():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["generator_detempering"] = True
    lay = spreadsheet.build(base, s)
    cells = {c.id: c for c in lay.cells}
    off = {c.id for c in _with(generator_detempering=False).cells}
    # the column appears only when toggled, riding between the domain primes and commas
    assert "header:detempering" in cells
    assert "header:detempering" not in off
    assert cells["header:primes"].x < cells["header:detempering"].x < cells["header:commas"].x
    # D for 5-limit meantone: the octave [1 0 0⟩ and the fifth [-1 1 0⟩, as vector columns
    assert [cells[f"cell:vec:detempering:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:vec:detempering:1:{p}"].text for p in range(3)] == ["-1", "1", "0"]
    # framed as a vector list (an enclosing bracket), riding its own gridline axis
    assert "bracket:vec:detempering:l" in cells
    assert "trunk:detempering" in {ln.id for ln in lay.lines}


def test_generator_detempering_vectors_tile_carries_the_D_symbol():
    # the mockup labels the D matrix with the symbol "D" above its caption, like the comma
    # basis's C and the target list's T in the same interval-vectors row
    cells = {c.id: c for c in _with(generator_detempering=True, symbols=True).cells}
    assert cells["symbol:vectors:detempering"].text == "D"
    # mnemonics underlines the d of "detempering" (its symbol D), like the comma basis C -> c
    named = {c.id: c for c in _with(generator_detempering=True, names=True, mnemonics=True).cells}
    cap = named["caption:vectors:detempering"]
    assert cap.underlines == ((cap.text.index("detempering"), 1),)


def test_generator_detempering_mapping_row_is_the_identity():
    # the mapping row over the detempering column shows M·D — each detempering generator
    # mapped back through M to its own generator coordinate, so M·D = I (D is the right-
    # inverse). Parallels the mapped comma basis (M·C = O) one column to its right.
    cells = {c.id: c for c in _with(generator_detempering=True).cells}
    assert [cells[f"cell:mapped_detempering:{i}:0"].text for i in range(2)] == ["1", "0"]
    assert [cells[f"cell:mapped_detempering:{i}:1"].text for i in range(2)] == ["0", "1"]
    # framed as a mapped list: an enclosing [ ] over the r rows, like the mapped comma basis
    assert "bracket:mapped_detempering:l" in cells
    assert cells["caption:mapping:detempering"].text == "mapped generator detempering"
    # symbols + equivalences read "𝑀D = 𝐼", the dual of the mapped comma basis's "𝑀C = 𝑂"
    eq = {c.id: c for c in _with(generator_detempering=True, symbols=True, equivalences=True).cells}
    assert eq["symbol:mapping:detempering"].text == "𝑀D = 𝐼"


def test_generator_detempering_mapping_row_plain_text():
    # the mapped detempering as a generator-coordinate ket list (} close), like the mapped
    # comma basis — M·D = I, so two unit kets
    cells = {c.id: c for c in _with(generator_detempering=True, plain_text_values=True).cells}
    assert cells["ptext:mapping:detempering"].text == "[[1 0} [0 1}]"


def test_generator_detempering_tuning_row_equals_the_genmap():
    # tempering the detempering intervals recovers the generator sizes (𝒕D = 𝒈), so the
    # detempering column's tuning row matches the generator tuning map cell-for-cell — and
    # is framed { ] like the genmap, not as a plain interval-size list
    cells = {c.id: c for c in _with(generator_detempering=True).cells}
    genmap = [cells[f"tuning:gen:{i}"].text for i in range(2)]
    assert [cells[f"tuning:detempering:{i}"].text for i in range(2)] == genmap
    assert cells["bracket:tuning:detempering:l"].text == "{"


def test_generator_detempering_size_rows_are_just_and_retuning_lists():
    cells = {c.id: c for c in _with(generator_detempering=True, units=True).cells}
    # just sizes of the octave (2/1) and fifth (3/2) detemperings: 1200 and 701.955
    assert [cells[f"just:detempering:{i}"].text for i in range(2)] == ["1200.000", "701.955"]
    # just and retune are ordinary interval-size lists ([ ]), one value per generator
    assert cells["bracket:just:detemperinglist:l"].text == "["
    assert cells["bracket:retune:detemperinglist:l"].text == "["
    assert {f"retune:detempering:{i}" for i in range(2)} <= set(cells)
    # captions per the mockup; every size row is in cents
    assert cells["caption:tuning:detempering"].text == "tempered generator detempering tuning map"
    assert cells["caption:just:detempering"].text == "(just) generator detempering interval size list"
    assert cells["caption:retune:detempering"].text == "generator detempering interval retuning list"
    for key in ("tuning", "just", "retune"):
        assert cells[f"units:{key}:detempering"].text == "units: ¢"


def test_generator_detempering_size_row_symbols():
    # 𝒕D = 𝒈 (its tempered sizes are the generator tuning map); 𝒋D / 𝒓D carry no continuation
    eq = {c.id: c for c in _with(generator_detempering=True, symbols=True, equivalences=True).cells}
    assert eq["symbol:tuning:detempering"].text == "𝒕D = 𝒈"
    assert eq["symbol:just:detempering"].text == "𝒋D"
    assert eq["symbol:retune:detempering"].text == "𝒓D"


def test_generator_detempering_size_rows_plain_text():
    cells = {c.id: c for c in _with(generator_detempering=True, plain_text_values=True).cells}
    # the tuning row is the generator tuning map, so its plain text matches the genmap's ({ ])
    assert cells["ptext:tuning:detempering"].text == cells["ptext:tuning:gens"].text
    # just/retune are ordinary cents lists ([ ]); just sizes are the octave + fifth
    assert cells["ptext:just:detempering"].text == "[1200.000 701.955]"
    assert cells["ptext:retune:detempering"].text.startswith("[")


def test_generator_detempering_quantities_row_shows_the_generator_ratios():
    # the detempering column's quantities row heads each generator with its JI ratio — the
    # octave 2/1 and the fifth 3/2 (the values the generator spine also shows), read-only
    cells = {c.id: c for c in _with(generator_detempering=True).cells}
    assert [cells[f"detempering:{i}"].text for i in range(2)] == ["2/1", "3/2"]
    # exact interval ratios (commaratio kind), like the comma / held / interest ratio headers
    assert cells["detempering:0"].kind == "commaratio"


def test_generator_detempering_quantities_plain_text():
    cells = {c.id: c for c in _with(generator_detempering=True, plain_text_values=True).cells}
    assert [cells[f"ptext:quantities:detempering:{i}"].text for i in range(2)] == ["2/1", "3/2"]


def test_generator_detempering_prescaling_row_scales_each_vector():
    # box 𝐋 applies the complexity prescaler to each detempering vector (L·D): the octave
    # [1 0 0⟩ and the fifth [-1 1 0⟩ scaled by diag(log₂2, log₂3, log₂5) = (1, 1.585, …)
    cells = {c.id: c for c in _with(generator_detempering=True, weighting=True, units=True).cells}
    assert [cells[f"cell:prescaling:detempering:{i}:0"].text for i in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:prescaling:detempering:{i}:1"].text for i in range(3)] == ["-1", "1.585", "0"]
    # framed per-column ket [ … ⟩ (ebktop/ebkangle) inside outer ``[ ]`` like every other
    # 𝐿·basis product prescaling tile, captioned + in octaves like the comma basis's
    assert "ebktop:prescaling:detempering:0" in cells
    assert cells["bracket:prescaling:detempering:l"].text == "["
    assert cells["caption:prescaling:detempering"].text == "complexity prescaled generator detempering"
    assert cells["units:prescaling:detempering"].text == "units: oct"


def test_generator_detempering_complexity_row_lists_each_complexity():
    # the complexity of each detempering interval: the octave (1.000) and the fifth (2.585,
    # = log₂2 + log₂3 under the default log-product norm), framed as an interval-size list
    cells = {c.id: c for c in _with(generator_detempering=True, weighting=True, units=True).cells}
    assert [cells[f"complexity:detempering:{i}"].text for i in range(2)] == ["1.000", "2.585"]
    assert cells["bracket:complexity:detemperinglist:l"].text == "["
    assert cells["caption:complexity:detempering"].text == "generator detempering complexity list"
    assert cells["units:complexity:detempering"].text == "units: (C)"


def test_generator_detempering_units_row_labels_each_generator():
    # the units row labels each detempering column /1 (a dimensionless ratio column), like
    # the commas and targets
    cells = {c.id: c for c in _with(generator_detempering=True, domain_units=True).cells}
    assert [cells[f"urow:detempering:{i}"].text for i in range(2)] == ["/1", "/1"]


def test_generator_detempering_audio_rows_sound_each_generator():
    # like the commas/targets, the detempering column gets audio: just_audio sounds the JI
    # sizes of its intervals, tempered_audio their tempered sizes (= the generators' sizes)
    cells = {c.id: c for c in _with(generator_detempering=True, audio=True).cells}
    assert {f"speaker:just_audio:detempering:{i}" for i in range(2)} <= set(cells)
    assert {f"speaker:tempered_audio:detempering:{i}" for i in range(2)} <= set(cells)
    # each speaker carries the whole tile's cents (for arp/chord play): the JI octave + fifth
    vals = cells["speaker:just_audio:detempering:0"].values
    assert [round(v, 3) for v in vals] == [1200.0, 701.955]


def test_generator_detempering_column_fans_without_a_centre_trunk():
    # the detempering column fans into one vertical rule per generator; it must own exactly
    # ONE trunk (its short fan stem above the data), never a second full-height one down the
    # centre between the two generator rules — that was a spurious middle gridline
    lay = _with(generator_detempering=True)
    assert sum(1 for ln in lay.lines if ln.id == "trunk:detempering") == 1
    assert sum(1 for ln in lay.lines if ln.id.startswith("v:detempering:")) == 2


def test_gridline_ids_are_unique_across_every_fan_and_spine():
    # every gridline id must be unique (the reconciling renderer keys on ids). A fanned
    # column or row — one rule per element — must NEVER also get a spine rule across its
    # centre: that duplicated id drew a spurious middle gridline (the detempering / held bug,
    # when those columns were added to the fan but not the spine loop's skip-set). Build with
    # every fanning column AND every matrix row (weighting, form controls) populated, so the
    # whole class — gens/primes/commas/targets/held/detempering columns and vectors/canon/
    # mapping/prescaling rows — is guarded structurally.
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "generator_detempering": True, "optimization": True,
         "weighting": True, "form_controls": True},
        interest=((-1, 1, 0), (2, 0, -1)),
        held_vectors=((1, 0, 0), (-1, 1, 0)),
    )
    ids = [ln.id for ln in lay.lines]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert dupes == [], f"duplicate gridline ids: {dupes}"


def test_generator_detempering_toggle_is_implemented():
    # the column is built, so its Show toggle is live (interactive, not a greyed stub)
    assert "generator_detempering" in settings.IMPLEMENTED


def test_optimization_toggle_is_implemented():
    # the power line + held intervals column are built, so the toggle is live. (Its third
    # mockup column, unchanged intervals, is deferred to the projection feature.)
    assert "optimization" in settings.IMPLEMENTED


def test_charts_on_adds_a_damage_bar_chart_over_the_targets():
    on = {c.id: c for c in _with(charts=True).cells}
    off = {c.id for c in _with(charts=False).cells}
    assert "chart:damage:targets" not in off  # no chart cell unless charts is on
    ch = on["chart:damage:targets"]
    assert ch.kind == "chart"
    # it carries the per-target damage values (one per target interval), all >= 0
    assert len(ch.values) == 8
    assert all(v >= 0 for v in ch.values)


def test_the_damage_chart_sits_above_its_values_and_reserves_row_space():
    off = {c.id: c for c in _with(charts=False).cells}
    on = {c.id: c for c in _with(charts=True).cells}
    ch, v0 = on["chart:damage:targets"], on["damage:target:0"]
    assert ch.y + ch.h <= v0.y  # the chart sits fully above the value cells, clear of them
    assert on["damage:target:0"].y > off["damage:target:0"].y  # values pushed down to make room
    # the chart spans the target columns (so its bars can align with them)
    assert ch.x <= on["target:0"].x and ch.x + ch.w >= on["target:7"].x + spreadsheet.COL_W


def test_charts_on_adds_signed_retuning_charts_over_primes_and_targets():
    on = {c.id: c for c in _with(charts=True).cells}
    cp, ct = on["chart:retune:primes"], on["chart:retune:targets"]
    assert cp.kind == ct.kind == "chart"
    assert len(cp.values) == 3  # one bar per domain prime (the retuning map)
    assert len(ct.values) == 8  # one bar per target interval (the error list)
    assert any(v < 0 for v in ct.values)  # errors are signed, so the chart straddles zero
    # each chart sits above its own value row, clear of it
    assert cp.y + cp.h <= on["retune:prime:0"].y
    assert ct.y + ct.h <= on["retune:target:0"].y


def test_every_open_tile_in_the_retuning_row_is_charted():
    # the retuning row carries a per-tile bar chart for EVERY one of its tiles, not a
    # hardcoded few: a chart tracks its tile, so any column joining the row is charted
    # automatically. Exercise every group the row can span at once.
    s = settings.defaults()
    s.update(charts=True, optimization=True, generator_detempering=True)
    on = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
        interest=((-3, 2, 0),),       # 9/8, an interval of interest (the interest column)
        held_vectors=((-1, 1, 0),),    # 3/2 held (the held column)
    ).cells}
    elem = {"primes": "prime", "commas": "comma", "targets": "target",
            "interest": "interest", "held": "held", "detempering": "detempering"}
    for group, e in elem.items():
        assert f"retune:{e}:0" in on, f"the retune {group} tile is missing"  # the tile is present
        assert on[f"chart:retune:{group}"].kind == "chart", f"the retune {group} tile is not charted"


def test_chart_bars_centre_on_their_value_gridlines():
    # each black bar centres exactly on the thin grey vertical gridline under its value
    # cell — the chart's plot area overlays the value block, not the (possibly wider /
    # gutter-offset) column footprint. _bar_chart lays bar i at chart.x + BRACKET_W +
    # i·COL_W + COL_W/2, so that must equal the per-element gridline. symbols adds the
    # primes matlabel gutter and the interest column's long title widens its footprint,
    # so both offsets are exercised.
    s = settings.defaults()
    s.update(charts=True, symbols=True, optimization=True, generator_detempering=True)
    lay = spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
        interest=((-3, 2, 0),), held_vectors=((-1, 1, 0),))
    on = {c.id: c for c in lay.cells}
    gridline = {ln.id: ln.pos for ln in lay.lines if ln.orientation == "v"}
    bw, cw = spreadsheet.BRACKET_W, spreadsheet.COL_W
    elem = {"primes": "prime", "commas": "comma", "targets": "target",
            "interest": "interest", "held": "held", "detempering": "detempering"}
    for group, e in elem.items():
        ch = on[f"chart:retune:{group}"]
        for i in range(len(ch.values)):
            bar_centre = ch.x + bw + i * cw + cw / 2
            assert bar_centre == gridline[f"v:{e}:{i}"], f"{group} bar {i} is off its gridline"


def test_generator_tuning_map_tile_shows_the_generator_map_cents_in_the_default_view():
    # the generator tuning map (the tuning row over the generators) is a default-view
    # tile, like the tuning map over the primes — present without any toggle
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    tun = service.tuning(st.mapping, service.DEFAULT_DOCUMENT_SCHEME)  # the default view's scheme
    cells = {c.id: c for c in _layout().cells}  # default settings (charts off)
    assert cells["tuning:gen:0"].text == service.cents(tun.generator_map[0])
    assert cells["tuning:gen:1"].text == service.cents(tun.generator_map[1])
    # one cents cell per generator, in the generators column, one COL_W apart
    assert cells["header:gens"].x <= cells["tuning:gen:0"].x < cells["header:primes"].x
    assert cells["tuning:gen:1"].x == cells["tuning:gen:0"].x + spreadsheet.COL_W
    assert cells["tuning:gen:0"].y == cells["tuning:prime:0"].y  # in the tuning row
    # framed { … ] (a curly open, square close) per the mockup — distinct from the
    # ⟨ … ] prime maps — and named by its caption
    assert cells["bracket:tuning:genmap:l"].text == "{" and cells["bracket:tuning:genmap:r"].text == "]"
    assert cells["caption:tuning:gens"].text == "generator tuning map"


def test_generator_tuning_map_gets_a_plain_text_value_band():
    # like every other tile, the generator tuning map shows its plain-text value when
    # plain text values is on — the { … ] curly map string from the service
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    on = {c.id: c for c in _with(plain_text_values=True).cells}
    assert "ptext:tuning:gens" in on
    assert on["ptext:tuning:gens"].text == service.plain_text_values(
        st, service.DEFAULT_DOCUMENT_SCHEME)[("tuning", "gens")]
    assert on["ptext:tuning:gens"].text.startswith("{") and on["ptext:tuning:gens"].text.endswith("]")


def test_tuning_ranges_on_adds_a_generator_tuning_range_chart_in_the_generators_column():
    # the generator tuning map tile (the generators column at the tuning row) grows a
    # ranges chart when tuning ranges is on — a maximized-only feature, so it is absent
    # by default (keeping the default view unchanged)
    on = {c.id: c for c in _with(tuning_ranges=True).cells}
    off = {c.id for c in _with(tuning_ranges=False).cells}
    assert "rangechart:tuning:gens" not in off  # no chart cell unless tuning ranges is on
    ch = on["rangechart:tuning:gens"]
    assert ch.kind == "rangechart"
    # it spans the generators column (so its per-generator I-beams align with the cells)
    assert ch.x == on["header:gens"].x and ch.w == on["header:gens"].w


def test_the_ranges_chart_answers_to_tuning_ranges_not_charts():
    # the ranges chart is the tuning-ranges box's content (mockup: "controls in box g"),
    # not the (bar-)charts toggle's: turning charts on alone must not summon it, and
    # tuning ranges drives it on its own
    charts_only = {c.id for c in _with(charts=True, tuning_ranges=False).cells}
    ranges_only = {c.id for c in _with(charts=False, tuning_ranges=True).cells}
    assert "rangechart:tuning:gens" not in charts_only
    assert "rangechart:tuning:gens" in ranges_only


def test_generator_tuning_range_chart_carries_the_monotone_ranges_by_default():
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    tun = service.tuning(st.mapping)  # ranges are interval-set-independent (the OLD diamond)
    ch = {c.id: c for c in _with(tuning_ranges=True).cells}["rangechart:tuning:gens"]
    # default mode is monotone: one (low, high) cents pair per generator
    assert ch.ranges == tun.monotone_generator_range
    assert len(ch.ranges) == 2  # rank 2: period + one free generator
    assert ch.ranges[0][0] == ch.ranges[0][1]  # the period pins to a point (octave held pure)
    assert ch.ranges[1][0] < ch.ranges[1][1]  # the fifth has a genuine [min, max] range


def test_range_mode_tradeoff_switches_the_chart_to_the_tradeoff_range():
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    tun = service.tuning(st.mapping)  # ranges are interval-set-independent (the OLD diamond)
    s = settings.defaults()
    s["tuning_ranges"] = True
    ch = {c.id: c for c in spreadsheet.build(st, s, range_mode="tradeoff").cells}["rangechart:tuning:gens"]
    assert ch.ranges == tun.tradeoff_generator_range
    assert ch.ranges != tun.monotone_generator_range  # the two modes give different ranges


def test_range_chart_draws_a_placeholder_when_no_monotone_range_exists():
    # some temperaments have no diamond-monotone tuning (the service returns None);
    # the chart still appears but carries no I-beams (empty ranges -> placeholder)
    st = service.from_mapping(((1, 0, -1), (0, 1, -1)))
    assert service.tuning(st.mapping).monotone_generator_range is None
    s = settings.defaults()
    s["tuning_ranges"] = True
    ch = {c.id: c for c in spreadsheet.build(st, s, range_mode="monotone").cells}["rangechart:tuning:gens"]
    assert ch.ranges == ()


def test_range_chart_nests_below_the_generator_map_values_inside_the_tile():
    on = {c.id: c for c in _with(tuning_ranges=True).cells}
    ch = on["rangechart:tuning:gens"]
    # the chart sits below the generator-map values (nested at the bottom of the tile),
    # not floating over them
    assert ch.y > on["tuning:gen:0"].y
    # ...and below the mapping row (whose generators-column tile is empty), so they never overlap
    mapping_bottom = on["cell:mapping:1:0"].y + spreadsheet.ROW_H
    assert ch.y >= mapping_bottom


def test_range_mode_selector_sits_below_the_chart_and_carries_the_current_mode():
    on = {c.id: c for c in _with(tuning_ranges=True).cells}
    off = {c.id for c in _with(tuning_ranges=False).cells}
    assert "rangemode:tuning:gens" not in off  # the selector rides the chart, tuning-ranges-only
    sel, ch = on["rangemode:tuning:gens"], on["rangechart:tuning:gens"]
    assert sel.kind == "rangemode"
    assert sel.text == "monotone"  # the live mode (default), so the renderer can preset it
    assert sel.x == ch.x  # in the generators column, under the chart
    assert sel.y >= ch.y + ch.h  # below the chart, clear of it


def test_generator_tuning_map_panel_encloses_its_values_chart_and_selector():
    lay = _with(tuning_ranges=True)
    cells = {c.id: c for c in lay.cells}
    pan = {b.id: b for b in lay.blocks}["block:tuning:gens"]  # the tile's OWN panel, extended
    v, ch, sel = cells["tuning:gen:0"], cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
    assert pan.x <= ch.x and pan.x + pan.w >= ch.x + ch.w  # encloses the chart horizontally
    assert pan.y <= v.y  # starts at/above the generator-map values...
    assert pan.y + pan.h >= sel.y + sel.h  # ...and extends down past the nested chart + selector
    # the panel is a normal default-view tile too (present without the chart), just shorter,
    # and there is no separate floating panel
    assert "block:tuning:gens" in {b.id for b in _with(tuning_ranges=False).blocks}
    assert "block:gentuning" not in {b.id for b in lay.blocks}


def test_tuning_ranges_box_has_a_left_aligned_boxtitle():
    # the ranges box wears the same left-aligned boxtitle as every other control box, not
    # a centred title drawn inside the chart SVG
    lay = _with(tuning_ranges=True)
    cells = {c.id: c for c in lay.cells}
    boxes = {b.id: b for b in lay.blocks}
    title = cells["rangetitle:tuning:gens"]
    assert title.kind == "boxtitle" and title.text == "tuning ranges"
    chart, sel = cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
    assert title.y < chart.y  # the title sits above the chart
    assert title.x == cells["header:gens"].x
    box = boxes["block:tuning:rangesbox"]  # the box still frames the whole thing
    assert box.y <= title.y and box.y + box.h >= sel.y + sel.h


def test_tuning_ranges_draws_a_bordered_box_around_the_chart_and_selector():
    # the mockup frames the tuning-ranges section (title + I-beams + mode selector) in a
    # thin-bordered box nested in the generator tuning map tile; the layout emits a boxed
    # Block enclosing the chart and selector
    lay = _with(tuning_ranges=True)
    boxes = {b.id: b for b in lay.blocks}
    cells = {c.id: c for c in lay.cells}
    assert "block:tuning:rangesbox" in boxes
    box = boxes["block:tuning:rangesbox"]
    assert box.boxed is True  # a bordered box, not a plain grey tile
    ch, sel = cells["rangechart:tuning:gens"], cells["rangemode:tuning:gens"]
    assert box.x <= ch.x and box.x + box.w >= ch.x + ch.w  # encloses them horizontally
    assert box.y <= ch.y and box.y + box.h >= sel.y + sel.h  # and the chart + selector vertically
    # gone when the ranges box is off
    assert "block:tuning:rangesbox" not in {b.id for b in _with(tuning_ranges=False).blocks}


def test_tuning_ranges_box_reserves_row_height_so_following_rows_clear_it():
    # the ranges box (chart + selector) nests below the generator-map values and extends
    # the tuning tile downward; that extra height must be reserved in the tuning row so the
    # just/retuning/damage rows drop below the whole box instead of it spilling across them
    lay = _with(tuning_ranges=True)
    cells = {c.id: c for c in lay.cells}
    panel = {b.id: b for b in lay.blocks}["block:tuning:gens"]  # the extended generator-tuning-map tile
    box_bottom = panel.y + panel.h
    for nxt in ("just:prime:0", "retune:prime:0", "damage:target:0"):
        assert cells[nxt].y >= box_bottom, f"{nxt} overlaps the ranges box"
    # and turning the box on must push those rows DOWN versus off (space is reserved, not stolen)
    off = {c.id: c for c in _with(tuning_ranges=False).cells}
    assert cells["just:prime:0"].y > off["just:prime:0"].y


def _color_at(lay, x, y):
    # which colorization groups' colour bands cover the point: {temperament}=yellow,
    # {tuning}=cyan, both=green (the darken blend), empty=uncoloured
    return {b.tint for b in lay.blocks if b.tint in ("temperament", "tuning")
            and b.x <= x <= b.x + b.w and b.y <= y <= b.y + b.h}


def _mid(cells, cid):
    c = cells[cid]
    return c.x + c.w / 2, c.y + c.h / 2


def _colormap_layout():
    s = settings.defaults()
    s["tuning_colorization"] = True
    s["temperament_colorization"] = True
    s["optimization"] = True  # reveal the held-intervals column (a tuning-box sub-control)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))


def test_colorization_follows_the_content_map():
    # colour by algebraic content: a tile is tinted by which fundamental objects are
    # multiplied into its quantity. Cyan (tuning): the generator embedding G / genmap 𝒈,
    # the just tuning map 𝒋, the prescaler 𝑋, the target list T, the held basis H. Yellow
    # (temperament): the mapping 𝑀, the comma basis C, the domain basis P, the generator
    # basis B. Both → green (the darken blend). (The spine label cells colour by the band
    # they head instead — see test_spine_rows_and_columns_colorize_by_their_band.)
    lay = _colormap_layout()
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    # quantities + interval-vectors rows: the domain primes P and comma basis C are yellow;
    # the target list T and the held basis H are cyan; only the other-intervals stay neutral
    assert at("comma:0") == Y                  # quantities × commas (the comma ratios are C)
    assert at("cell:comma:0:0") == Y           # interval-vectors × commas (the comma basis vectors)
    assert at("prime:0") == Y                  # quantities × primes (the domain basis, now yellow)
    assert at("qgen:0") == Y                    # quantities × generators (the generator basis B, yellow)
    assert at("target:0") == C                 # quantities × targets (T, now cyan)
    assert at("interest:0") == N               # quantities × other-intervals
    assert at("held:0") == C                   # quantities × held intervals (H, now cyan)
    assert at("basis:0") == N                  # interval-vectors × spine (the domain basis, quantities col)
    assert at("cell:vec:targets:0:0") == C     # interval-vectors × targets (the target vectors, T)
    assert at("cell:interest:0:0") == N        # interval-vectors × other-intervals
    assert at("cell:held:0:0") == C            # interval-vectors × held intervals (the H basis)
    # the generators in the spine are the generator basis — an input, carrying neither the
    # tuning map 𝒈 nor the embedding G — so by CONTENT they'd be neutral; but the quantities
    # spine column colours by its row's BAND (continuity), so the mapping row's generator
    # ratios take the mapping's temperament yellow (see test_spine_rows_and_columns_…)
    assert at("gen:0") == Y                     # mapping × spine (generator ratios, by the mapping band)
    # the mapping matrix and its mapped lists are 𝑀; mapping a cyan list (T, H) greens it
    assert at("cell:mapping:0:0") == Y          # mapping × primes (𝑀)
    assert at("cell:mapped_comma:0:0") == Y     # mapping × commas (𝑀C)
    assert at("cell:mapped:0:0") == G           # mapping × targets (𝑀T = 𝑀·T, both colours)
    assert at("cell:imapped:0:0") == Y          # mapping × other-intervals (𝑀·interest)
    assert at("cell:hmapped:0:0") == G          # mapping × held intervals (𝑀H, both colours)
    # the generators column carries the generator basis B (yellow) in every tile, like the
    # primes column carries P — so the cyan genmap 𝒈 over it reads green; 𝒕 = 𝒈𝑀 over it is
    # green too (already had G·M). the retuning row 𝒓 = 𝒕 − 𝒋 keeps the 𝒈𝑀 term's G and 𝑀
    assert at("tuning:gen:0") == G              # tuning × generators (𝒈 over the yellow generator basis B)
    for col in ("prime", "comma", "target", "interest", "held"):
        assert at(f"tuning:{col}:0") == G       # 𝒕 / 𝒕C / 𝐚 / 𝒕H = 𝒈𝑀(…)
        assert at(f"retune:{col}:0") == G       # 𝒓 / 𝒓C / 𝐞 / 𝒓H = (𝒈𝑀 − 𝒋)(…)
    # the just tuning map 𝒋 is cyan; its products green where the column also carries a
    # yellow object (primes P, commas C), stay cyan where the column is cyan (T, H)
    assert at("just:prime:0") == G              # just × primes (𝒋 over the yellow domain basis P)
    assert at("just:comma:0") == G              # just × commas (𝒋C, both colours)
    assert at("just:target:0") == C             # just × targets (𝐨 = 𝒋T, both cyan → cyan)
    assert at("just:interest:0") == C           # just × other-intervals (𝒋·interest)
    assert at("just:held:0") == C               # just × held intervals (𝒋H, both cyan → cyan)
    # the damage row rides the error chain 𝐞 = (𝒈𝑀 − 𝒋)T → green
    assert at("damage:target:0") == G           # damage × targets (𝐝 = |𝐞|𝒘)


def test_off_by_default_rows_colorize_by_content_too():
    # the rows hidden by default follow the same content rule when revealed: the canonical
    # mapping is the 𝑀 family (𝑀 = 𝐅𝑀_c → yellow). The prescaler 𝑋 is cyan, so the prescaling
    # and complexity rows carry it everywhere; a column that also bears a yellow object (the
    # domain primes P or the comma basis C) greens, while the cyan target list 𝑋T stays cyan.
    s = settings.defaults()
    s["temperament_colorization"] = True
    s["tuning_colorization"] = True
    s["form_controls"] = True   # reveal the canonical-mapping row
    s["weighting"] = True       # reveal the prescaling + complexity rows (a tuning-boxes sub-control)
    s["optimization"] = True    # reveal the held column
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    assert at("cell:canon:0:0") == Y                       # the canonical mapping (𝑀 family)
    # the prescaling row 𝑋 is cyan; the primes (P) and comma (C) columns add yellow (green);
    # T / H ride cyan-only
    assert at("cell:prescaling:primes:0:0") == G           # 𝑋 over the yellow domain basis P (green)
    assert at("cell:prescaling:commas:0:0") == G           # 𝑋C (the prescaler keeps the comma basis's C)
    assert at("cell:prescaling:targets:0:0") == C          # 𝑋T (both cyan → cyan)
    assert at("cell:prescaling:interest:0:0") == C         # 𝑋·interest (cyan)
    assert at("cell:prescaling:held:0:0") == C             # 𝑋H (both cyan → cyan)
    # complexity 𝒄 = ‖𝑋·v‖ inherits 𝑋 (cyan), greening where the basis is yellow (P or C)
    assert at("complexity:prime:0") == G                   # 𝒄 of the primes (norm of 𝑋 over the yellow P)
    assert at("complexity:comma:0") == G                   # 𝒄 of the comma basis (norm of 𝑋C)
    assert at("complexity:target:0") == C                  # 𝒄 of the targets (norm of 𝑋T)
    assert at("complexity:interest:0") == C                # 𝒄 of the other-intervals
    assert at("complexity:held:0") == C                    # 𝒄 of the held basis (norm of 𝑋H)
    # the weight 𝒘 incorporates the target complexity list (𝒘 = 𝒄 / 1 / 1∕𝒄), so it inherits
    # that list's cyan 𝑋 (and rides the cyan target column T) → cyan
    assert at("weight:target:0") == C                      # 𝒘 (built from the cyan complexity 𝒄)


def test_generator_detempering_column_colorizes_by_content():
    # the generator detempering column is NEUTRAL — like the intervals-of-interest column,
    # the basis itself (D) carries no colour, and a tile takes only the colour of the OTHER
    # objects its row multiplies in. So the basis + mapped-detempering tiles are uncoloured,
    # the mapping product 𝑀·D is yellow (the 𝑀), and the tuning/retune family stays green
    # (its 𝒈𝑀), while the just / prescaled / complexity products are CYAN (their bare 𝒋 / 𝑋).
    s = settings.defaults()
    s["tuning_colorization"] = True
    s["temperament_colorization"] = True
    s["generator_detempering"] = True  # reveal the detempering column
    s["weighting"] = True              # reveal the prescaling + complexity rows
    s["audio"] = True                  # reveal the just/tempered audio speaker tiles
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    # the detempering basis carries no colour (like the interest list); only its products colour
    assert at("detempering:0") == N                    # quantities × detempering (the detempering list, neutral)
    assert at("cell:vec:detempering:0:0") == N         # interval-vectors × detempering (the basis, neutral)
    assert at("cell:mapped_detempering:0:0") == Y      # mapping × detempering (𝑀·D → the 𝑀 yellow)
    # the tuning/retune family keeps its 𝒈𝑀 green; the bare 𝒋 / 𝑋 products are cyan-only now
    assert at("tuning:detempering:0") == G             # tuning × detempering (𝒕·D, the 𝒈𝑀 greens)
    assert at("just:detempering:0") == C               # just × detempering (𝒋·D, bare cyan 𝒋)
    assert at("retune:detempering:0") == G             # retune × detempering (𝒓·D, keeps 𝒈𝑀)
    assert at("cell:prescaling:detempering:0:0") == C  # prescaling × detempering (𝑋·D, bare cyan 𝑋)
    assert at("complexity:detempering:0") == C         # complexity × detempering (norm of 𝑋·D, cyan)
    assert at("speaker:just_audio:detempering:0") == C    # just audio × detempering (sounds 𝒋·D, cyan)
    assert at("speaker:tempered_audio:detempering:0") == G  # tempered audio × detempering (sounds 𝒕·D, green)


def _spine_colormap():
    # everything that reveals the two spine rows (counts, units) and the two spine columns
    # (quantities, units), plus the detempering column and the weighting rows, so every
    # spine intersection the continuity rule colours is present to probe
    s = settings.defaults()
    s["tuning_colorization"] = s["temperament_colorization"] = True
    s["counts"] = s["domain_units"] = s["domain_quantities"] = True
    s["weighting"] = s["optimization"] = s["generator_detempering"] = True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))


def test_spine_rows_and_columns_colorize_by_their_band():
    # the spine label cells (the counts + units ROWS, the quantities + units COLUMNS) carry
    # no algebraic quantity of their own — they head a value row or column, so they take
    # that BAND's family colour, continuing the colour through the spine so each value
    # column / row reads as one unbroken band. This is a BY-BAND rule, not the content rule:
    # the retuning spine cell is cyan (its band is a tuning row) even though the retuning
    # VALUE cells are green (𝒓 carries both groups).
    lay = _spine_colormap()
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    # counts + units ROWS take each column's family: primes / commas yellow and now the
    # generators column too; held / targets cyan; the detempering column is neutral
    for spine in ("count", "urow"):
        suffix = ":0" if spine == "urow" else ""
        assert at(f"{spine}:commas{suffix}") == Y       # the commas column is temperament (C)
        assert at(f"{spine}:primes{suffix}") == Y       # the domain primes column is temperament (P)
        assert at(f"{spine}:gens{suffix}") == Y          # the generators column is now temperament (B)
        assert at(f"{spine}:targets{suffix}") == C      # the target column is tuning (T)
        assert at(f"{spine}:held{suffix}") == C         # the held column is tuning (H)
        assert at(f"{spine}:detempering{suffix}") == N  # the detempering column is now neutral
    # quantities + units COLUMNS take each row's family: mapping yellow; tuning, just,
    # retuning, prescaling, complexity cyan. The retuning units cell is cyan despite the
    # retuning VALUE cells being green — the spine follows the band, not the content.
    assert at("gen:0") == Y                             # quantities × mapping (the generator ratios → yellow)
    assert at("ucol:mapping:0") == Y                    # units × mapping (yellow)
    assert at("ucol:tuning") == C                       # units × tuning (cyan)
    assert at("ucol:just") == C                         # units × just tuning (cyan)
    assert at("ucol:retune") == C                       # units × retuning (cyan, though 𝒓 cells are green)
    assert at("ucol:prescaling:0") == C                 # units × complexity prescaling (cyan)
    assert at("ucol:complexity") == C                   # units × complexity (cyan)


def test_washes_bridge_the_plus_column_gutters():
    # the domain primes and commas tiles carry an in-tile +, so each tile's footprint runs
    # a FRAME_GAP wider on each side than its bare content. A wash on such a column must
    # reach across that wider gutter to meet its same-coloured neighbour, or a grey strip
    # shows beside the + tile. In the mapping row the mapping 𝑀, mapped comma basis 𝑀C and
    # mapped list 𝑀T are all temperament (yellow); in the tuning row the tempered comma
    # sizes 𝒕C and target sizes 𝐚 are both green. Probe each gutter's midpoint.
    lay = _colormap_layout()
    cells = {c.id: c for c in lay.cells}
    h = lambda k: cells[f"header:{k}"]
    primes_commas = (h("primes").x + h("primes").w + h("commas").x) / 2    # 𝑀 | 𝑀C
    commas_targets = (h("commas").x + h("commas").w + h("targets").x) / 2  # 𝑀C | 𝑀T  /  𝒕C | 𝐚
    map_y = _mid(cells, "cell:mapping:0:0")[1]
    tun_y = _mid(cells, "tuning:prime:0")[1]
    assert "temperament" in _color_at(lay, primes_commas, map_y)               # 𝑀 meets 𝑀C
    assert "temperament" in _color_at(lay, commas_targets, map_y)              # 𝑀C meets 𝑀T
    assert {"temperament", "tuning"} <= _color_at(lay, commas_targets, tun_y)  # 𝒕C meets 𝐚 (green)


def test_colorization_off_by_default_and_renders_as_base_plus_darken_bands():
    assert not any(b.id.startswith(("wash:", "washbase:")) for b in _layout().blocks)  # off by default
    blocks = _with(tuning_colorization=True).blocks
    washes = {b.id.split(":", 1)[1]: b for b in blocks if b.tint == "tuning"}
    bases = {b.id.split(":", 1)[1]: b for b in blocks if b.tint == "base"}
    assert washes and set(washes) == set(bases)  # one white base per colour band
    for k, w in washes.items():
        b = bases[k]
        assert (b.x, b.y, b.w, b.h) == (w.x, w.y, w.w, w.h)  # base coincident with its colour band
    assert all(b.tint == "" for b in blocks if b.id.startswith("block:"))  # grey tiles untinted


def test_collapsing_a_tile_removes_its_colorization():
    # colour goes away with the content: a folded tile shows NO wash, rather than lingering
    # as a coloured strip behind the collapsed band. Holds whether the tile is folded on its
    # own, or via its row or column.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["tuning_colorization"] = s["temperament_colorization"] = True
    open_ids = {b.id for b in spreadsheet.build(base, s).blocks if b.tint in ("tuning", "temperament")}
    assert "wash:tuning:tuning:targets" in open_ids       # tempered target sizes 𝐚 (green → cyan layer)
    assert "wash:temperament:mapping:primes" in open_ids  # the mapping 𝑀 (yellow)
    folded = spreadsheet.build(base, s, collapsed={"row:tuning", "tile:mapping:primes"})
    folded_ids = {b.id for b in folded.blocks if b.tint in ("tuning", "temperament")}
    assert "wash:tuning:tuning:targets" not in folded_ids       # row folded → its tiles' washes vanish
    assert "wash:temperament:mapping:primes" not in folded_ids  # tile folded → its own wash vanishes
    assert "wash:temperament:vectors:commas" in folded_ids      # an untouched tile keeps its wash


def test_mapped_comma_basis_vanishes_and_the_damage_weight_is_bold_italic():
    # weighting shown so the damage equivalence names its 𝒘 weight factor (hidden it drops to
    # |𝐞|); the bold-italic 𝒘 — matching the maps, not the bold-upright list glyphs — is the check
    on = {c.id: c for c in _with(weighting=True, symbols=True, equivalences=True).cells}
    # the mapped comma basis is exactly the zero matrix
    assert on["symbol:mapping:commas"].text == "𝑀C = 𝑂"
    # the damage weight w is bold-italic (matching the maps), not bold-upright
    assert on["symbol:damage:targets"].text == "𝐝 = |𝐞|𝒘"


# --- audio rows (hear just & mapped intervals) -------------------------------

def _audio(**overrides):
    # tuning boxes default on, so the target interval column (and its audio tile) is present
    return _with(audio=True, **overrides)


def test_audio_is_a_top_level_toggle_between_counts_and_quantities():
    # audio is NOT nested under tuning boxes; it is a top-level Show toggle sitting between
    # counts and quantities, matching where its rows land in the grid
    assert "audio" not in settings.SUBCONTROLS
    keys = [k for k, *_ in dict(settings.SHOW_GROUPS)["specific boxes & controls"]]
    assert keys[keys.index("counts") + 1] == "audio"
    assert keys[keys.index("audio") + 1] == "domain_quantities"  # the "quantities" toggle
    assert settings.defaults()["audio"] is False


def test_audio_rows_depend_only_on_the_audio_toggle():
    # top-level: the rows appear whenever audio is on, independent of the tuning boxes
    assert "label:just_audio" in {c.id for c in _with(audio=True, tuning_boxes=False).cells}
    assert "label:just_audio" not in {c.id for c in _with(audio=False).cells}


def test_form_colorization_is_a_greyed_form_subcontrol():
    # form colorization completes the M/G/F colour trio alongside temperament (𝑀) and
    # tuning (G) colorization, but its content — the form matrix 𝐹 — isn't a built tile
    # yet, so it rides as a greyed stub: registered and indented under the form controls,
    # default off, and NOT implemented (no wash to paint), like the other deferred controls.
    keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
    assert "form_colorization" in keys
    assert settings.SUBCONTROLS["form_colorization"] == "form_controls"
    assert settings.defaults()["form_colorization"] is False
    assert "form_colorization" not in settings.IMPLEMENTED


def test_interest_is_a_top_level_toggle_after_the_tuning_boxes_group():
    # "other intervals of interest" is a standalone grey column (not part of the cyan
    # tuning region), so it owns a top-level toggle: built (implemented), default on, and
    # NOT a sub-control of tuning boxes. It sits just after the tuning boxes group (its
    # last sub-control, colorization) and before generator detempering, mirroring the grid
    # where the interest column lands just right of the target intervals.
    items = dict(settings.SHOW_GROUPS)["specific boxes & controls"]
    keys = [k for k, *_ in items]
    assert keys[keys.index("tuning_colorization") + 1] == "interest"
    assert keys[keys.index("interest") + 1] == "generator_detempering"
    assert "interest" not in settings.SUBCONTROLS
    assert "interest" in settings.IMPLEMENTED
    assert settings.defaults()["interest"] is True
    # its label is the column's full name, wrapped onto two lines (it won't fit the
    # panel's narrow label column on one)
    label = dict((k, lbl) for k, lbl, _d in items)["interest"]
    assert label == "other intervals\nof interest"


def test_interest_column_follows_its_own_toggle_not_tuning_boxes():
    # the interest column used to ride the tuning boxes toggle; now it has its own. Turning
    # tuning boxes off drops the cyan tuning columns but leaves the interest column standing.
    off_tuning = {c.id for c in _with(tuning_boxes=False).cells}
    assert "header:targets" not in off_tuning  # the tuning column goes...
    assert "header:interest" in off_tuning      # ...the interest column stays
    # and its own toggle hides it — header, axis and content — even when populated
    s = settings.defaults(); s["interest"] = False
    off_interest = {c.id for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s, interest=_INTEREST).cells}
    assert "header:interest" not in off_interest
    assert not any(c.startswith(("interest:", "cell:interest:", "cell:imapped:")) for c in off_interest)


def test_audio_adds_two_rows_between_counts_and_quantities():
    cells = {c.id: c for c in _audio(counts=True).cells}
    assert cells["label:just_audio"].text == "just audio"
    assert cells["label:tempered_audio"].text == "tempered audio"
    # ordered: counts, then just audio, then tempered audio, then quantities
    ys = [cells[f"label:{k}"].y for k in ("counts", "just_audio", "tempered_audio", "quantities")]
    assert ys == sorted(ys)


def test_audio_speakers_carry_the_whole_tiles_pitch_list():
    # every speaker carries its tile's full cents list (so arp/chord modes can sound the
    # whole tile); the list matches the displayed tuning (mapped) / just-tuning row sizes
    cells = {c.id: c for c in _audio().cells}
    k = len([c for c in cells if c.startswith("speaker:tempered_audio:target:")])
    spk = cells["speaker:tempered_audio:target:0"]
    assert spk.kind == "speaker"
    assert [service.cents(v) for v in spk.values] == [cells[f"tuning:target:{j}"].text for j in range(k)]
    just = cells["speaker:just_audio:target:0"]
    assert [service.cents(v) for v in just.values] == [cells[f"just:target:{j}"].text for j in range(k)]


def test_tempered_audio_sounds_generators_but_just_audio_has_no_generator_pitch():
    # the tempered row carries the generator tuning map (like the tuning row); a generator
    # has no just size, so the just-audio row has no generator speaker
    cells = {c.id: c for c in _audio().cells}
    assert service.cents(cells["speaker:tempered_audio:gen:0"].values[0]) == cells["tuning:gen:0"].text
    assert "speaker:just_audio:gen:0" not in cells


def test_audio_tiles_carry_a_control_bank_in_the_top_right():
    # each tile gets a bank of four TOGGLE-sized controls in the head strip, mirroring the
    # fold toggle (top-left): waveform, play-mode, hold/loop, include-1/1 — left to right
    cells = {c.id: c for c in _audio().cells}
    fold = cells["toggle:tile:tempered_audio:targets"]
    bank = [cells[f"{c}:tempered_audio:targets"] for c in ("wave", "mode", "hold", "root")]
    assert [b.kind for b in bank] == ["audio_wave", "audio_mode", "audio_hold", "audio_root"]
    for b in bank:
        assert (b.y, b.w, b.h) == (fold.y, fold.w, fold.h)  # TOGGLE-sized, in the head strip
        assert b.x > fold.x                                  # right of the fold toggle
    assert [b.x for b in bank] == sorted(b.x for b in bank)  # ordered left to right
    assert bank[0].y < cells["speaker:tempered_audio:target:0"].y  # above the speaker band


def test_caption_widened_commas_tile_keeps_its_controls_on_the_panel_edges():
    # Regression: the commas column's long captions ("...comma basis...(made to vanish!)")
    # widen its grey tile well past its narrow one-comma content, so the content centres
    # within the wider tile. The per-tile fold toggle (top-left) and the audio control bank
    # (top-right) must anchor to the PANEL's corners, not to that centred content — anchoring
    # to content drifts both inward by half the widening, reading as centred rather than
    # left/right-justified. The bug showed only here because commas is the one column whose
    # caption outruns its content; wide-content columns (targets) hid it (tile == content).
    cells = {c.id: c for c in _with(names=True, audio=True).cells}
    blocks = {b.id: b for b in _with(names=True, audio=True).blocks}
    narrow = {b.id: b for b in _with(names=False, audio=True).blocks}
    inset = spreadsheet.TOGGLE_INSET
    for row in ("just_audio", "tempered_audio"):
        panel = blocks[f"block:{row}:commas"]
        assert panel.w > narrow[f"block:{row}:commas"].w  # the caption really did widen it
        fold = cells[f"toggle:tile:{row}:commas"]
        root = cells[f"root:{row}:commas"]  # the rightmost control in the four-wide bank
        assert fold.x == panel.x + inset                     # fold hugs the panel's left edge
        assert root.x + root.w == panel.x + panel.w - inset  # bank hugs the panel's right edge


def _audio_colormap():
    s = settings.defaults()
    s["tuning_colorization"] = s["temperament_colorization"] = s["audio"] = True
    s["optimization"] = True  # reveal the held-intervals column (and its audio tiles)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))


def test_audio_rows_colorize_by_content_like_the_rows_they_sound():
    # the audio rows mirror the rows they sound. just audio plays the just sizes 𝒋, cyan;
    # the primes and comma columns green (the just sizes 𝒋 over the yellow domain basis P /
    # comma basis C), while the target / held columns stay cyan. tempered audio plays the
    # tempered sizes: the generator tuning map 𝒈 over the generators (cyan 𝒈 over the yellow
    # generator basis B → green), and 𝒕 = 𝒈𝑀 (G·M → green) over the value columns.
    lay = _audio_colormap()
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    assert at("speaker:just_audio:prime:0") == G           # 𝒋 over the yellow domain basis P (green)
    assert at("speaker:just_audio:comma:0") == G           # 𝒋C (cyan 𝒋 over the yellow comma basis)
    for g in ("target", "interest", "held"):
        assert at(f"speaker:just_audio:{g}:0") == C         # 𝐨 / 𝒋H: cyan 𝒋 (T/H also cyan)
    assert at("speaker:tempered_audio:gen:0") == G           # 𝒈 over the yellow generator basis B (green)
    for g in ("prime", "comma", "target", "interest", "held"):
        assert at(f"speaker:tempered_audio:{g}:0") == G       # 𝒕 / 𝒕H = 𝒈𝑀


def test_every_audio_tile_gets_its_own_bank():
    # the bank is per-tile (independent waveform/mode/hold/root), on every audio tile
    cells = {c.id for c in _audio_colormap().cells}  # has primes/commas/targets/interest + gens
    for tile in ("just_audio:primes", "just_audio:commas", "just_audio:targets", "just_audio:interest",
                 "tempered_audio:gens", "tempered_audio:primes", "tempered_audio:targets"):
        assert {f"wave:{tile}", f"mode:{tile}", f"hold:{tile}", f"root:{tile}"} <= cells


def test_show_flags_gate_sub_controls_under_their_parent():
    # _resolve_show_flags (build's phase-1) ANDs each nested toggle with its parent: optimization /
    # weighting nest under tuning_boxes, alt_complexity under weighting, mnemonics under names. So a
    # sub-control can't render while its region is hidden, whatever its own toggle says.
    s = settings.defaults()
    s.update(tuning_boxes=False, optimization=True, weighting=True, alt_complexity=True,
             names=False, mnemonics=True)
    f = spreadsheet._resolve_show_flags(s, frozenset())
    assert not (f.optimization or f.weighting or f.alt_complexity)  # all gated off by tuning_boxes
    assert not f.mnemonics                                          # gated off by names
    s.update(tuning_boxes=True, names=True)  # parents on -> sub-controls follow their own toggle
    f = spreadsheet._resolve_show_flags(s, frozenset())
    assert f.optimization and f.weighting and f.alt_complexity and f.mnemonics


def test_show_flags_box_choosers_gate_on_the_collapsed_state():
    # the box-𝐋 / box-𝒄 in-tile choosers (lbox/cbox) show only while their column + row + tile are
    # open; collapsing any of them hides the chooser even with every toggle on.
    s = settings.defaults()
    s.update(tuning_boxes=True, weighting=True, alt_complexity=True, temperament_boxes=True)
    assert spreadsheet._resolve_show_flags(s, frozenset()).lbox  # all open -> box-𝐋 chooser shows
    assert spreadsheet._resolve_show_flags(s, frozenset()).cbox  # ...and box-𝒄
    assert not spreadsheet._resolve_show_flags(s, frozenset({"row:prescaling"})).lbox  # collapsed -> hidden
    assert not spreadsheet._resolve_show_flags(s, frozenset({"row:complexity"})).cbox


def test_prescaler_labels_resolve_the_log_prime_glyph_and_gated_name():
    # _resolve_prescaler_labels (build's phase 2): the default scheme's prescaler is the log-prime
    # matrix, so products/headers carry the concrete 𝐿 (not the abstract 𝑋), and the bare tile's
    # NAME gains "= log-prime matrix" — but only with the equivalences layer on.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    p = spreadsheet._resolve_prescaler_labels(state, service.DEFAULT_DOCUMENT_SCHEME, None, show_equiv=True)
    assert p.symbol == "𝐿"  # the concrete log-prime glyph (not the abstract 𝑋)
    assert p.effective_captions[("prescaling", "primes")].endswith("= log-prime matrix")
    bare = spreadsheet._resolve_prescaler_labels(state, service.DEFAULT_DOCUMENT_SCHEME, None, show_equiv=False)
    assert "log-prime matrix" not in bare.effective_captions[("prescaling", "primes")]  # gated on equivalences


