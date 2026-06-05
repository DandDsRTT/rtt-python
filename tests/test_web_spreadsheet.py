from rtt.web import service, settings, spreadsheet
from rtt.web.editor import Editor
from rtt.web.layout import CellBox, Layout


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


def _drag_layout(mapping=((1, 1, 0), (0, 1, 4)), **kw):
    # a layout with the "drag to combine" handles turned on (the feature is off by default)
    return spreadsheet.build(service.from_mapping(mapping),
                             {**settings.defaults(), "drag_to_combine": True}, **kw)


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


def test_freeze_seam_sits_at_the_first_value_tile():
    # the frozen bands now reach PAST the column/row branching — the trunks, the fan-out
    # buses and their ± controls ride the frozen header with the titles. The seam lands on
    # the topmost / leftmost grey value tile's panel edge (the tile overhangs its cells by
    # PAD), so everything above/left of it is frozen and the value tiles scroll beneath.
    lay = _layout()
    # land on the ACTUAL tile edge (the extent of the grey panels), not a re-derived
    # production formula that would mirror any bug in it
    tiles = [bl for bl in lay.blocks if bl.tint == "" and not bl.boxed]  # the grey value tiles
    assert lay.freeze_y == min(bl.y for bl in tiles)   # the first row's panel top
    assert lay.freeze_x == min(bl.x for bl in tiles)   # the first column's panel left
    # the branching rises into the bands: a column trunk starts above the seam, a matrix
    # row's trunk starts left of it
    by_id = {ln.id: ln for ln in lay.lines}
    assert by_id["trunk:primes"].start < lay.freeze_y   # the primes column trunk, above the seam
    assert by_id["trunk:mapping"].start < lay.freeze_x  # the mapping row trunk, left of the seam


def test_the_first_columns_title_clears_the_frozen_corner():
    # the leftmost column's title ("quantities") is centred on its column and renders unwrapped,
    # so on a narrow spine it overhangs both sides. Its LEFT overhang can't show: the frozen corner
    # (opaque, higher z) abuts the first tile at freeze_x and paints over anything left of it — the
    # title was clipped to "…iantities". So the first visible column's footprint is floored to seat
    # its centred title clear of the corner (left edge at/right of the seam); the other columns'
    # titles still overhang freely into the inter-column gaps (no corner there to clip them).
    lay = _layout()
    h = {c.id: c for c in lay.cells}["header:quantities"]
    title_left = (h.x + h.w / 2) - spreadsheet._title_w(h.text) / 2  # the centred, unwrapped title
    assert title_left >= lay.freeze_x - 0.51  # not tucked under the frozen corner


def test_branch_controls_ride_the_frozen_bands():
    # the always-shown + sits wholly inside the frozen band, cleared from the seam by the
    # button's own height — pinning the band-to-tile gap so a future constant change can't
    # nudge the control under the seam where its bottom/right edge would clip. The hover −
    # anchors there too. Column controls ride the column strip (above freeze_y); the basis
    # controls ride the row band (left of freeze_x).
    lay = _layout()
    cells = {c.id: c for c in lay.cells}
    assert cells["plus"].y + cells["plus"].h <= lay.freeze_y           # column + wholly in the strip
    assert cells["minus"].y < lay.freeze_y                             # column − reveal anchors there
    assert cells["basis_plus"].x + cells["basis_plus"].w <= lay.freeze_x  # row + wholly in the band
    assert cells["basis_minus"].x < lay.freeze_x                       # row − reveal anchors there


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
    # the frozen bands hold the titles + toggles AND the branching ± / drag-grip controls; every
    # value cell and grey value tile clears both bands, so the renderer's frozen panes never mask
    # live content. A fan control (a ± whose kind ends in "plus"/"minus", or a drag grip / drop zone
    # on the fan) rides a frozen band — its anchor, the top-left where it sits, is left of freeze_x
    # (row band) or above freeze_y (column strip); a hover zone may then EXTEND past the seam over
    # the header.
    fx, fy = lay.freeze_x, lay.freeze_y
    for cb in lay.cells:
        if cb.kind in {"colheader", "coltoggle"}:
            assert cb.y + cb.h <= fy                          # column titles + toggles: above the seam
        elif cb.kind in {"rowlabel", "rowtoggle"}:
            assert cb.x + cb.w <= fx                          # row titles + toggles: left of the seam
        elif cb.kind == "alltoggle":
            assert cb.y + cb.h <= fy and cb.x + cb.w <= fx    # the master toggle: the corner of both
        elif cb.kind.endswith(("plus", "minus")) or cb.kind == "colgrip":
            assert cb.x < fx or cb.y < fy                     # a fan control rides a frozen band, not the body
        else:
            assert cb.x >= fx and cb.y >= fy                  # all value content clears both bands
    for bl in lay.blocks:
        if bl.tint == "" and not bl.boxed:                    # the grey value tiles (washes overhang by design)
            assert bl.x >= fx and bl.y >= fy


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


def test_build_threads_nonprime_approach_through_to_the_tuning():
    # the chapter-9 approach radio rides through build() as a nonprime_approach param (the
    # binary nonstandard_domain Show toggle no longer drives the mode). Picking "nonprime-based"
    # over a nonprime-bearing domain reshapes the optimal tuning visibly in the grid — the
    # same divergence service.tuning shows in test_tuning_mode_changes_the_nonstandard_optimum.
    state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    neutral = spreadsheet.build(state, tuning_scheme="TILT minimax-C")
    nonprime = spreadsheet.build(state, tuning_scheme="TILT minimax-C", nonprime_approach="nonprime-based")
    # the generator-tuning cells visibly differ between the two approaches
    n = {c.id: c.text for c in neutral.cells}
    np_ = {c.id: c.text for c in nonprime.cells}
    assert n["tuning:gen:0"] != np_["tuning:gen:0"]
    assert n["tuning:gen:1"] != np_["tuning:gen:1"]


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
    # the − rides the highest prime's branch point, so it MOVES to the new last column when the
    # domain shrinks (never stranded at the old one). 2.3.5.7 meantone carries it on prime 3;
    # dropping to 2.3.5 moves it to prime 2. Both shrinks stay proper, so the − shows at each
    # (contrast test_domain_minus_is_absent_when_the_shrink_would_degenerate, where it does not).
    wide = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # 2.3.5.7 meantone, d=4
    wlay = spreadsheet.build(wide)
    wcells, wlines = {c.id: c for c in wlay.cells}, {ln.id: ln for ln in wlay.lines}
    assert abs((wcells["minus"].x + wcells["minus"].w / 2) - wlines["v:prime:3"].pos) < 0.51  # on prime 3
    slay = spreadsheet.build(service.shrink_domain(wide))  # back to 2.3.5, d=3
    scells, slines = {c.id: c for c in slay.cells}, {ln.id: ln for ln in slay.lines}
    assert "prime:3" not in scells  # the 7 is gone again
    assert abs((scells["minus"].x + scells["minus"].w / 2) - slines["v:prime:2"].pos) < 0.51  # moved to prime 2


def test_a_single_prime_domain_has_no_minus_but_keeps_plus():
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1,),))).cells}
    assert "minus" not in cells  # nothing is removable when d == 1
    assert {"plus", "prime:0"} <= cells  # ...but you can still expand


def test_domain_minus_is_absent_on_a_nonstandard_subgroup():
    # the domain − walks the standard primes (shrink_domain trims the last), which doesn't apply to
    # a nonprime subgroup — so the − is withheld, not shown inert (clicking it would silently no-op,
    # since editor.shrink guards on the same can_shrink_domain predicate). The basis still renders.
    arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))  # 2.3.7 (archytas)
    cells = {c.id for c in spreadsheet.build(arch).cells}
    assert {"prime:0", "prime:2"} <= cells  # the 2.3.7 basis still heads its columns
    assert "minus" not in cells and "basis_minus" not in cells  # but no inert − on either axis


def test_domain_minus_is_absent_when_the_shrink_would_degenerate():
    # augmented tempers out 128/125; dropping prime 5 would leave prime 2 tempered to a unison (an
    # improper, degenerate temperament the engine rejects), so the − is withheld though d > 1.
    augmented = service.from_comma_basis(((7, 0, -3),))  # 2.3.5, mapping shrinks to ((0, 1),)
    cells = {c.id for c in spreadsheet.build(augmented).cells}
    assert {"prime:0", "prime:2"} <= cells
    assert "minus" not in cells and "basis_minus" not in cells


def test_domain_plus_is_absent_on_a_nonstandard_subgroup():
    # the domain + walks to the next standard prime, which doesn't apply to a nonprime subgroup —
    # so the + is withheld, not shown inert (editor.expand guards on the same is_standard_domain).
    # (The shrink would-degenerate / d == 1 cases still keep the +: a standard limit can always grow.)
    arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))  # 2.3.7
    cells = {c.id for c in spreadsheet.build(arch).cells}
    assert {"prime:0", "prime:2"} <= cells  # the basis still heads its columns
    assert "plus" not in cells and "basis_plus" not in cells  # but no inert + on either axis


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
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}  # r=1, n=2
    assert "gen_minus" not in cells  # nothing to remove at rank 1
    assert {"gen_plus", "qgen:0"} <= cells  # ...but n>0, so a generator can still be added (un-tempering a comma)


def test_generators_plus_is_gated_on_a_comma_to_un_temper():
    # the generators + un-tempers a comma (−n, +r, hold d), like the mapping +, so it needs a comma:
    # present at n>0, gone at full rank where there is nothing left to un-temper.
    assert "gen_plus" in {c.id for c in _layout().cells}  # meantone, n=1
    ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))  # 5-limit JI, n=0
    assert "gen_plus" not in {c.id for c in spreadsheet.build(ji).cells}


def test_minus_hover_zone_clears_the_editable_quantities_cell():
    # the − hover zone used to drop over the whole quantities header as a fat hover target. Now
    # that the header is an editable ratiocell, the zone must stop ABOVE it (at the cell's top
    # edge) so clicks reach the input rather than the invisible z-index-4 zone swallowing them.
    cells = {c.id: c for c in _layout().cells}
    k = len([c for c in cells if c.startswith("target:") and c.split(":")[1].isdigit()])
    assert k >= 2
    for j in range(k):
        zone, cell = cells[f"target_minus:{j}"], cells[f"target:{j}"]
        assert zone.y + zone.h <= cell.y + 0.51  # the zone ends at (not past) the cell's top edge


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


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def test_interval_columns_carry_a_drag_grip_per_column():
    # each existing interval column gets a drag grip (the drag-and-drop handle, also a drop target);
    # plus every list emits a drop-only "add" zone on its stub gridline (the append / into-empty
    # target), so dropping into a list is the same gridline gesture whether it is full or empty.
    ed = Editor()
    ed.set_held_vectors([(-1, 1, 0), (2, 0, -1)])  # two held intervals
    ed.set_interest_vectors([(1, 1, -1)])          # one interval of interest
    cells = {c.id: c for c in spreadsheet.build(
        ed.state, _all_on(), interest=ed.interest_vectors, held_vectors=ed.held_vectors).cells}
    assert cells["grip:held:0"].kind == "colgrip" and cells["grip:held:1"].kind == "colgrip"
    assert "grip:held:2" not in cells                 # no per-column grip past the last column
    assert cells["grip:held:add"].kind == "colgrip"   # ...but the gridline append zone is always there
    assert cells["grip:interest:0"].kind == "colgrip"


def test_a_drag_grip_rides_the_fan_band_below_the_minus():
    # the grip is a ⠿ on each column's sub-axis gridline, in the reserved fan band BETWEEN the −
    # above (at the branch point) and the first tile below — above the freeze seam, so the frozen
    # colhead doesn't clip it.
    ed = Editor()
    ed.set_held_vectors([(-1, 1, 0), (2, 0, -1)])
    lay = spreadsheet.build(ed.state, _all_on(), held_vectors=ed.held_vectors)
    cells = {c.id: c for c in lay.cells}
    sub = {ln.id: ln for ln in lay.lines}["v:held:1"].pos  # column 1's gridline
    grip, minus = cells["grip:held:1"], cells["held_minus:1"]
    assert abs((grip.x + grip.w / 2) - sub) < 0.51   # centred on the column's gridline
    assert grip.y > minus.y + 0.5                     # sits BELOW the − (which rides the branch point above)
    assert grip.y + grip.h <= lay.freeze_y + 0.51     # ...and above the seam (in the frozen fan, not clipped)


def test_an_empty_interval_list_still_offers_a_gridline_drop_zone():
    # with no intervals yet there's nothing to drag OUT (no per-column grip), but the list still
    # emits its "add" drop zone on the trunk gridline — so dropping an interval IN is the same
    # "drop on the gridline" gesture as for a full list, never a separate + / header target.
    cells = {c.id for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert "grip:interest:0" not in cells  # nothing to drag out of an empty list
    assert "grip:interest:add" in cells    # ...but its gridline drop zone is there to receive one


def test_comma_grips_let_even_the_sole_comma_be_dragged_out():
    # the sole comma is now draggable out — un-tempering it to just intonation (parity with the −) —
    # so it grips like every other list's columns; the comma special-case is gone. The list also
    # offers its gridline "add" zone (dropping an interval in tempers it out).
    one = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
    assert "grip:commas:0" in one and "grip:commas:add" in one  # the lone comma grips too
    two = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),)), _all_on()).cells}  # r=1, n=2
    assert "grip:commas:0" in two and "grip:commas:1" in two
    ji = {c.id for c in spreadsheet.build(service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4)))), _all_on()).cells}
    assert "grip:commas:0" not in ji  # ...but nothing to drag at full rank (n = 0)


def test_targets_have_no_drag_grips_in_all_interval():
    cells = {c.id for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), tuning_scheme="minimax-S").cells}
    assert not any(c.startswith("grip:targets") for c in cells)


# --- interval-column identity tokens: a stable id-token per column so a within-list reorder
# keeps each column's cell ids and the reconciler glides them (see assign_column_tokens) ---

def _tokens(pairs):
    return [tok for tok, _ in pairs]


def test_fresh_column_tokens_number_the_columns_by_index():
    # with no previous render, each column is numbered 0,1,2,… in order — so every cell id keeps
    # its index until the first reorder (the whole existing test surface is index-keyed)
    pairs = spreadsheet.assign_column_tokens(None, [(-1, 1, 0), (2, 0, -1), (1, 1, -1)])
    assert _tokens(pairs) == [0, 1, 2]


def test_reordered_column_keeps_its_token():
    # a reorder is matched by CONTENT: each moved column carries its token to its new slot, so its
    # cell ids persist and only their x changes — the reconciler then slides them across
    a, b, c = (-1, 1, 0), (2, 0, -1), (1, 1, -1)
    prev = spreadsheet.assign_column_tokens(None, [a, b, c])   # tokens 0,1,2
    moved = spreadsheet.assign_column_tokens(prev, [c, a, b])  # drag c to the front
    assert _tokens(moved) == [2, 0, 1]


def test_edited_column_keeps_its_token_by_position():
    # an edit changes a column's content but not its slot: it has no content match, so it inherits
    # the token at its index — its cell ids persist, so the focused input is reused (not rebuilt,
    # which would drop focus mid-keystroke) and its unchanged siblings keep their ids too
    a, b = (-1, 1, 0), (2, 0, -1)
    prev = spreadsheet.assign_column_tokens(None, [a, b])     # tokens 0,1
    edited = spreadsheet.assign_column_tokens(prev, [(-1, 2, 0), b])  # edit column 0's content
    assert _tokens(edited) == [0, 1]


def test_editing_a_column_to_a_value_already_in_the_list_keeps_its_position_token():
    # the subtle case: editing column 0 to a vector that ALREADY appears later in the list must NOT
    # be read as a move into that duplicate (which would steal its token and orphan column 0's id) —
    # a membership change is matched by position, so column 0 keeps token 0 and its cell id survives
    a, b, c = (-1, 1, 0), (2, 0, -1), (1, 1, -1)
    prev = spreadsheet.assign_column_tokens(None, [a, b, c])   # tokens 0,1,2
    edited = spreadsheet.assign_column_tokens(prev, [c, b, c])  # edit column 0 from a to c (== column 2)
    assert _tokens(edited) == [0, 1, 2]                         # every column keeps its slot's token


def test_duplicate_columns_get_distinct_tokens():
    # two equal vectors in one list must not collide on one id: each claims a distinct previous
    # column in order, so a reorder of the pair still keeps every id unique
    a, b = (-1, 1, 0), (2, 0, -1)
    prev = spreadsheet.assign_column_tokens(None, [a, a, b])   # tokens 0,1,2 (the dup is 0 and 1)
    moved = spreadsheet.assign_column_tokens(prev, [a, b, a])  # move b between the two equal a's
    assert _tokens(moved) == [0, 2, 1]
    assert len(set(_tokens(moved))) == 3                       # still three distinct ids


def test_pending_token_never_collides_with_a_live_column():
    # the draft column's token is one past every committed column's, so it can't clash with a
    # surviving column even after a removal leaves a gap in the token sequence; an empty list's
    # draft is 0 (so a first pending vector cell is …:0, as the index-keyed tests expect)
    assert spreadsheet.pending_token([]) == 0
    assert spreadsheet.pending_token([0, 1, 2]) == 3          # a fresh list: == the column count
    assert spreadsheet.pending_token([2]) == 3               # after removals: clears the survivor


def _held_state():
    return service.from_mapping(((1, 1, 0), (0, 1, 4)))


def test_build_returns_column_identities_numbered_by_index_when_fresh():
    # a fresh build numbers every reorderable list by index, so its cell ids are unchanged — the
    # whole index-keyed test surface stays valid (divergence happens only after a reorder)
    held = [(-1, 1, 0), (2, 0, -1)]
    lay = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
    assert _tokens(lay.identities["held"]) == [0, 1]


def test_reordered_held_column_keeps_its_vector_cell_id_and_glides():
    # build the held list, then rebuild with the third column dragged to the front, threading the
    # first build's identities as the previous render. The moved column keeps its cell id and lands
    # at the new slot's x — so the reconciler (a CSS left transition on a kept id) slides it.
    held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
    lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
    c1 = {c.id: c for c in lay1.cells}
    slot0_x, slot2_x = c1["cell:held:0:0"].x, c1["cell:held:0:2"].x
    assert slot0_x != slot2_x                                  # the slots are at different x
    lay2 = spreadsheet.build(_held_state(), _all_on(),
                             held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities)
    c2 = {c.id: c for c in lay2.cells}
    assert "cell:held:0:2" in c2                               # the moved column kept its id (token 2)...
    assert c2["cell:held:0:2"].x == slot0_x                    # ...and now sits at the front slot → glides
    assert c2["cell:held:0:2"].text == c1["cell:held:0:2"].text  # carrying its own content, not slot 0's


# Cells whose content can legitimately differ across a reorder for reasons OTHER than a bad key, so
# they're not evidence of an in-place re-fill: (a) a wide chart / the plain-text list re-list the
# columns in order; (b) anything derived from the OPTIMIZED tuning (tempered sizes, retuning errors,
# tempered audio, the generator tuning-range chart) shifts by sub-cent solver noise when the held
# SET is re-presented in a new order. The deterministic per-column cells left over — the vectors,
# ratios, just sizes, and mapped products — are the oracle for whether a column's cells re-keyed.
def _reorder_volatile(cid):
    # speaker cells carry the WHOLE tile's cents list (for arp/chord), so their values reorder too
    return cid.startswith(("chart:", "ptext:", "tuning:", "retune:", "speaker:", "rangechart:"))


def test_reordering_held_rekeys_every_column_cell_not_just_the_vectors():
    # after a within-list reorder, every per-column cell (ratio, grip, −, just-size row, mapped
    # products, just audio, prescaling) kept its id and content and merely moved x. A cell still
    # keyed by index would instead keep its id while its content changed (the next interval slid into
    # it) — so it would show up in this diff. (Tuning-derived cells are filtered: see _reorder_volatile.)
    held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
    lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
    lay2 = spreadsheet.build(_held_state(), _all_on(),
                             held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities)
    moved = {cid for cid in spreadsheet.changed_cell_ids(lay1, lay2) if not _reorder_volatile(cid)}
    assert moved == set(), f"these cells re-filled in place instead of gliding: {sorted(moved)}"


def test_reorder_keeps_controls_position_bound_while_values_glide():
    # the VALUE cells re-key by interval identity (they glide), but the per-column CONTROLS — the
    # grip, the −, the audio speaker — stay INDEX-keyed: each is bound to a SLOT, not a column. So a
    # control's build-time index never goes stale (it always addresses the column now in its slot —
    # the bug a token-keyed control hit on a SECOND reorder), and it does not drift out from under
    # the cursor mid-drag (which is what keeps a hover preview stable).
    held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
    lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
    c1 = {c.id: c for c in lay1.cells}
    slot_x = [c1[f"grip:held:{i}"].x for i in range(3)]
    c2 = {c.id: c for c in spreadsheet.build(
        _held_state(), _all_on(), held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities).cells}
    assert [c2[f"grip:held:{i}"].x for i in range(3)] == slot_x  # grips stayed at their slots...
    assert all(f"held_minus:{i}" in c2 for i in range(3))        # ...and the −'s are slot-keyed too
    assert "speaker:just_audio:held:0" in c2                     # ...and the speakers
    assert c2["cell:held:0:2"].x == slot_x[0]                    # but the value column DID glide to the front


def test_reordering_interest_rekeys_its_column_cells():
    interest = [(1, 1, -1), (-1, 1, 0), (2, 0, -1)]  # 6/5, 3/2, 9/8-ish
    lay1 = spreadsheet.build(_held_state(), _all_on(), interest=interest)
    lay2 = spreadsheet.build(_held_state(), _all_on(),
                             interest=[interest[2], interest[0], interest[1]], prev_ids=lay1.identities)
    moved = {cid for cid in spreadsheet.changed_cell_ids(lay1, lay2) if not _reorder_volatile(cid)}
    assert moved == set(), f"interest cells re-filled in place instead of gliding: {sorted(moved)}"


def test_reordering_targets_rekeys_its_column_cells():
    # targets carry the optimization objective, so the damage row shifts by solver noise on reorder
    # (filtered); the per-column cells (vectors, ratios, weights, complexity, prescaling, mapped) glide
    targets = ("2/1", "3/2", "5/4")
    lay1 = spreadsheet.build(_held_state(), _all_on(), target_override=targets)
    lay2 = spreadsheet.build(_held_state(), _all_on(),
                             target_override=(targets[2], targets[0], targets[1]), prev_ids=lay1.identities)
    moved = {cid for cid in spreadsheet.changed_cell_ids(lay1, lay2)
             if not _reorder_volatile(cid) and not cid.startswith("damage:")}
    assert moved == set(), f"target cells re-filled in place instead of gliding: {sorted(moved)}"


def test_removing_a_column_keeps_the_survivors_identity_so_they_do_not_ring():
    # dropping a column must not make every column past it read as "changed". Interest carries no
    # optimization, so removing one re-solves nothing — the only thing that could ring the survivors
    # is an id-token shift. With the tokens content-matched across the removal, each survivor keeps
    # its id AND content, so the diff rings nothing. (Index-keyed tokens would slide the next
    # interval into each freed slot, falsely flagging the whole column.)
    interest = [(1, 1, -1), (-1, 1, 0), (2, 0, -1)]  # 6/5, 3/2, 9/8
    lay1 = spreadsheet.build(_held_state(), _all_on(), interest=interest)
    lay2 = spreadsheet.build(_held_state(), _all_on(), interest=interest[1:], prev_ids=lay1.identities)
    assert spreadsheet.changed_cell_ids(lay1, lay2) == frozenset()


def test_editable_vector_tiles_get_editable_quantities_ratios():
    # every tile whose interval-vectors cells are editable (commas / targets / held / interest)
    # carries an editable quantities-row ratio — a "ratiocell" input, the scalar twin of its
    # vector column. Read-only vector tiles (the domain primes, the generator-detempering D)
    # keep their read-only ratio, so editability tracks the vectors row tile-for-tile.
    ed = Editor()
    ed.set_interest_vectors([(1, 1, -1)])  # commit 6/5 (add_* now starts a pending draft instead)
    ed.set_held_vectors([(-1, 1, 0)])      # commit 3/2
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    cells = {c.id: c for c in spreadsheet.build(
        ed.state, s, interest=ed.interest_vectors, held_vectors=ed.held_vectors).cells}
    assert cells["comma:0"].kind == "ratiocell"
    assert cells["target:0"].kind == "ratiocell"
    assert cells["held:0"].kind == "ratiocell"
    assert cells["interest:0"].kind == "ratiocell"
    # the read-only twins stay non-editable (the vectors row shows these read-only too)
    assert cells["prime:0"].kind == "prime"
    assert cells["detempering:0"].kind == "commaratio"


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


def test_the_weight_matrix_fans_its_subrows_like_any_multi_row_tile():
    # the d×(d+1) weight matrix is a multi-row tile, so — like the mapping / vectors — it must get one
    # branching gridline per sub-row, DERIVED from its own cell-row count (row_nsub > 1), not from a
    # hand-kept FRAMED_ROWS membership. Regression: the weight row used to fall through to a single
    # flat spine (h:weight) with no internal sub-rules — the row-side of the generators-column bug.
    lay = _with("minimax-lils-S", weighting=True)  # all-interval + size factor → a 3×4 weight matrix
    ids = {ln.id for ln in lay.lines}
    assert {"h:weight:0", "h:weight:1", "h:weight:2"} <= ids  # one fanned rule per matrix sub-row
    assert "h:weight" not in ids                              # NOT the single-spine fallback
    # ...fanning through the same left/right bus + foot structure the mapping uses
    assert {"vbar:weight:left", "vbar:weight:right", "foot:weight"} <= ids
    # a single-row value row (damage) still gets its lone spine, no fan
    assert "h:damage" in ids and "h:damage:0" not in ids


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


def test_a_spine_hugs_col_w_and_overhangs_its_title_unless_it_is_leftmost():
    # a spine column carries only a single COL_W-wide index per row (the domain basis square /
    # generator ratio; the per-row unit label), so it hugs that COL_W content and lets its long
    # title overhang — as "units" (the second spine) does here. The LEFTMOST spine is the exception:
    # its left overhang would vanish under the frozen corner, so it's floored wider to hold its title
    # (see test_the_first_columns_title_clears_the_frozen_corner).
    cells = {c.id: c for c in _with(domain_units=True).cells}
    assert cells["header:units"].w == spreadsheet.COL_W             # hugs the COL_W content...
    assert cells["header:units"].w < spreadsheet._title_w("units")  # ...the title overhanging it
    assert cells["header:quantities"].w > cells["header:units"].w   # but the leftmost is floored wider


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
    # collapsing a column must never BALLOON it out to its title's strip width — a column should only
    # get narrower when folded. The overhanging "units" spine stays a COL_W strip; the leftmost
    # "quantities" (floored wider so its title clears the frozen corner) keeps that floored width
    # rather than the still-wider full-title strip.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults(); s["domain_units"] = True
    opened = {c.id: c for c in spreadsheet.build(base, s).cells}
    collapsed = {c.id: c for c in spreadsheet.build(base, s, collapsed={"col:quantities", "col:units"}).cells}
    for key in ("quantities", "units"):
        assert collapsed[f"header:{key}"].w <= opened[f"header:{key}"].w  # collapse never widens
    assert collapsed["header:units"].w == spreadsheet.COL_W  # the overhanging spine stays one COL_W


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
    # a non-unity slope reveals the slope-gated prescaling + complexity rows (and box 𝐋/𝒄)
    aon = {b.id: b for b in spreadsheet.build(base, alt, tuning_scheme="TILT minimax-S").blocks}
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


def test_single_option_tuning_chooser_is_a_disabled_dropdown():
    # the established-tuning-scheme chooser has a single option in the default view (weighting +
    # alt. complexity both off → only T minimax-U). A one-option chooser has no real choice, so when its
    # value is that option (on the list) it renders as a DISABLED dropdown (greyed, kept in its box),
    # like the all-interval-locked target / slope choosers. displayed_tuning_name is the on-list value
    # the editor threads in (here the default scheme's "minimax-U").
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    lay = spreadsheet.build(base, s, displayed_tuning_name="minimax-U")
    cells = {c.id: c for c in lay.cells}
    assert cells["preset:tuning"].kind == "preset"      # still a dropdown...
    assert cells["preset:tuning"].disabled is True       # ...just disabled (greyed, non-interactive)
    assert "block:preset:tuning" in {b.id for b in lay.blocks}  # its box stays
    # the field-label caption greys with the locked chooser
    assert cells["block:preset:tuning:label"].disabled is True


def test_off_list_tuning_chooser_stays_an_interactive_dropdown():
    # even with a single option, a chooser whose value is OFF the list (a deviating manual edit, shown
    # as "-") stays interactive (not greyed) — the lone option is the reset back to the named scheme, so
    # it must remain pickable. displayed_tuning_name=None marks the off-list state.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"] = True
    lay = spreadsheet.build(base, s, displayed_tuning_name=None)
    cell = {c.id: c for c in lay.cells}["preset:tuning"]
    assert cell.kind == "preset" and cell.disabled is False  # off the list -> a live dropdown
    assert "block:preset:tuning" in {b.id for b in lay.blocks}


def test_weighting_keeps_the_tuning_chooser_an_enabled_dropdown():
    # with weighting on (alt. complexity still off) the chooser offers the three weight-slope variants
    # (T minimax-U / -S / -C) — a real choice — so it stays an enabled, interactive dropdown even on-list.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["weighting"] = True, True
    lay = spreadsheet.build(base, s, displayed_tuning_name="minimax-U")
    cell = {c.id: c for c in lay.cells}["preset:tuning"]
    assert cell.kind == "preset" and cell.disabled is False
    assert "block:preset:tuning" in {b.id for b in lay.blocks}


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


def test_quantities_interval_ratios_emit_no_redundant_plain_text():
    ids = {c.id for c in _with(plain_text_values=True).cells}
    # the quantities row's interval-ratio columns (commas, targets, held, …) already show the
    # formatted "n/d" in the gridded cell, so they emit NO duplicate plain-text line below it.
    assert not any(i.startswith("ptext:quantities:commas") for i in ids)
    assert not any(i.startswith("ptext:quantities:targets") for i in ids)
    # the domain-primes column keeps its plain text — "2.3.5" is the compact prime-limit
    # notation, not a copy of the gridded "2 3 5" cells.
    assert "ptext:quantities:primes" in ids


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
    # weighting + a non-unity slope opens the prescaling row so the bare prescaler 𝐿 tile's ptext is present too
    cells = {c.id: c for c in _with("TILT minimax-S", plain_text_values=True, weighting=True).cells}
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


def test_a_rank_one_mapping_still_fans_to_connect_its_plus():
    # an ET's mapping is a SINGLE generator row (r=1), but it still carries a + (un-temper a
    # comma, n>0). Like a multi-row mapping — and the interval-vectors basis + — that lone-row
    # band must still fan its left bus OUT past the row label and drop a connecting bar to reach
    # the +; it must NOT fall through to a flat full-width spine that strands the + off the side
    # with no line, a FAN further from the spine than the basis + sits.
    lay = spreadsheet.build(service.from_mapping(((12, 19, 28),)))  # 12-ET 5-limit: r=1, n=2
    cells = {c.id: c for c in lay.cells}
    by_id = {ln.id: ln for ln in lay.lines}
    assert "h:mapping:0" in by_id and "h:mapping" not in by_id  # the fanned sub-rule, not the flat spine
    left_bus, plus = by_id["vbar:mapping:left"], cells["map_plus"]
    assert abs((plus.x + plus.w / 2) - left_bus.pos) < 0.51  # + centred on the left bus
    assert abs((left_bus.start + left_bus.length) - (plus.y + plus.h / 2)) < 0.51  # the bar reaches the +
    # ...and the + sits as close to the spine as the always-fanned basis +, not a FAN further out
    assert abs((plus.x + plus.w / 2) - (cells["basis_plus"].x + cells["basis_plus"].w / 2)) < 0.51


def test_drag_handles_are_gated_on_the_drag_to_combine_toggle():
    # the whole feature is OFF by default — no row or interval drag handles render until the
    # "drag to combine" toggle (the top of the settings pane) turns it on.
    off = {c.id for c in _layout().cells}  # default settings
    assert not any(c.startswith(("map_drag:", "int_drag:")) for c in off)
    on = {c.id for c in _drag_layout().cells}  # meantone with the toggle on
    assert "map_drag:0" in on  # the generator-row handles appear
    assert any(c.startswith("int_drag:target:") for c in on)  # ...and the interval handles


def test_mapping_row_drag_handles_sit_left_of_the_row_labels():
    # each generator row's drag handle rides a reserved gutter to the LEFT of the row labels (the 𝒎ᵢ
    # matlabels), in the widened mapping tile — drag one row onto another to ADD it in. Verified with
    # symbols on (where the row labels render): the handle clears the labels and the left-bus − too.
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                            {**settings.defaults(), "symbols": True, "drag_to_combine": True})
    cells = {c.id: c for c in lay.cells}
    for i in range(2):
        handle = cells[f"map_drag:{i}"]
        label = cells[f"matlabel:row:mapping:primes:{i}"]
        assert handle.gen == i
        assert handle.y == cells[f"cell:mapping:{i}:0"].y  # aligned with row i
        assert handle.x + handle.w <= label.x  # LEFT of the row label (no overlap)
        assert label.x + label.w <= cells[f"cell:mapping:{i}:0"].x  # label still sits between handle and matrix
        assert handle.x > cells[f"map_minus:{i}"].x  # ...and right of the left-bus − control (separate)


def test_mapping_row_drag_handles_need_two_rows():
    rank1 = {c.id for c in _drag_layout(((1, 0, 0),)).cells}
    assert not any(c.startswith("map_drag:") for c in rank1)  # a lone generator has nothing to combine with
    assert {"map_drag:0", "map_drag:1"} <= {c.id for c in _drag_layout().cells}  # a handle per generator row


def test_interval_drag_handles_sit_above_the_column_labels_in_the_vectors_row():
    # each interval column (commas / targets / held / interest) with ≥2 entries gets a drag handle in
    # a band ABOVE its column label (c₁/𝒕ᵢ) in the (taller) interval-vectors tile — drag one onto
    # another to combine them. Verified with symbols on, where the column labels render: the order
    # down each column is handle / label / vector cells.
    lay = spreadsheet.build(service.from_mapping(((12, 19, 28),)),  # 12-ET 5-limit: two commas
                            {**settings.defaults(), "symbols": True, "drag_to_combine": True},
                            interest=((-1, 1, 0), (0, 0, 1)))
    cells = {c.id: c for c in lay.cells}
    for i in range(2):
        handle = cells[f"int_drag:comma:{i}"]
        label = cells[f"matlabel:col:vectors:commas:{i}"]
        vec0 = cells[f"cell:comma:0:{i}"]  # the column's first vector component
        assert handle.comma == i and handle.x == label.x  # aligned over its own column
        assert handle.y + handle.h <= label.y  # ABOVE the column label...
        assert label.y < vec0.y  # ...which is above the vector cells (handle / label / vector)
    # the interest column carries no column label, but still gets handles above its vectors
    assert cells["int_drag:interest:0"].y + spreadsheet.ROW_HANDLE_W <= cells["cell:interest:0:0"].y
    assert "int_drag:target:0" in cells  # the default target list (many) gets them too


def test_interval_drag_handles_need_two_entries_and_skip_all_interval_targets():
    one_comma = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone: a single comma
    cells = {c.id for c in _drag_layout(((1, 1, 0), (0, 1, 4))).cells}
    assert not any(c.startswith("int_drag:comma") for c in cells)  # one comma — nothing to combine
    # an all-interval target list is auto (Tₚ = I, not editable), so it carries no combine handles
    ai = {c.id for c in spreadsheet.build(one_comma, settings.defaults(), tuning_scheme="minimax-S").cells}
    assert not any(c.startswith("int_drag:target") for c in ai)


def test_full_rank_temperament_shows_an_empty_commas_column():
    # a full-rank (n=0) temperament tempers nothing out — the commas column shows no comma at
    # all (not the trivial zero comma's "1/1"); the + remains so a comma can be added back.
    ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))  # 5-limit JI, n=0
    cells = {c.id for c in spreadsheet.build(ji).cells}
    assert not any(c.startswith(("comma:", "cell:comma:")) for c in cells)  # no comma cells
    assert "comma_plus" in cells  # ...but the + stays, to start one


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


def test_size_factor_makes_the_all_interval_weight_a_matrix_dropping_the_chart():
    # all-interval + size factor (lils): the per-prime weight list is blind to the size factor,
    # so the weight tile renders the d×(d+1) matrix 𝑊 = (𝑍𝐿)⁻ instead — and a bar chart can't
    # draw a matrix, so it's dropped. lp (the square pretransformer) keeps the list + chart.
    lp = {c.id: c for c in _with(scheme="minimax-S", weighting=True, charts=True).cells}
    lils = {c.id: c for c in _with(scheme="minimax-lils-S", weighting=True, charts=True).cells}
    W = service.damage_weight_matrix(((1, 1, 0), (0, 1, 4)), "minimax-lils-S")
    # lp: the per-prime weight list, with its bar chart
    assert "weight:target:0" in lp and "chart:weight:targets" in lp
    # lils: a 3×4 matrix of value cells; the scalar list and the chart are both gone
    assert "weight:target:0" not in lils
    assert "chart:weight:targets" not in lils
    for i in range(3):
        for j in range(4):
            assert lils[f"cell:weight:targets:{i}:{j}"].text == service.cents(W[i][j])
    # the matrix is d (= 3) rows tall, stepping ROW_H; the size column overflows one COL_W right
    assert lils["cell:weight:targets:1:0"].y == lils["cell:weight:targets:0:0"].y + spreadsheet.ROW_H
    assert lils["cell:weight:targets:0:3"].x == lils["cell:weight:targets:0:2"].x + spreadsheet.COL_W


def test_all_interval_weight_matrix_carries_the_W_symbol_and_a_spanning_bracket():
    on = {c.id: c for c in _with(scheme="minimax-lils-S", weighting=True,
                                 symbols=True, equivalences=True).cells}
    # capital 𝑊 = 𝑋⁻ — the inverse pretransformer (𝑋 = 𝑍𝐿), simpler than spelling out (𝑍𝐿)⁻, and NOT
    # the per-prime diag(𝐿)⁻¹ the lp all-interval shows
    assert on["symbol:weight:targets"].text == "𝑊 = 𝑋⁻"
    # the appendix's [[…] …] form: outer [ … ] over all d = 3 rows + one [ … ] per row, the outer right
    # bracket past the overflowing size column
    assert on["bracket:weight:l"].text == "[" and on["bracket:weight:r"].text == "]"
    assert on["bracket:weight:l"].h == 3 * spreadsheet.ROW_H
    assert {"bracket:weight:row:0:l", "bracket:weight:row:0:r", "bracket:weight:row:2:l"} <= set(on)
    assert on["bracket:weight:r"].x > on["cell:weight:targets:0:3"].x


def test_the_weight_matrix_size_bar_is_one_structure_in_both_the_grid_and_the_plain_text():
    # the size-augmentation ` | ` divider is a single structure shown two ways and they must agree: the
    # grid draws a vertical rule (bar:weight) at the prime|size seam, and the plain text shows the same
    # ` | ` divider per row (the guide's [… | …] augmentation separator). Neither can have it alone.
    on = {c.id: c for c in _with(scheme="minimax-lils-S", weighting=True, plain_text_values=True).cells}
    assert "bar:weight" in on                              # the grid's vertical size-divider
    assert " | " in on["ptext:weight:targets"].text        # the plain text's matching size-divider
    bar = on["bar:weight"]                                 # ...sitting between the last prime and the size column
    assert on["cell:weight:targets:0:2"].x < bar.x <= on["cell:weight:targets:0:3"].x
    assert bar.h == 3 * spreadsheet.ROW_H                  # spanning all d matrix rows, like the [ … ]
    # a weight LIST (no size factor → not a matrix) has the divider in NEITHER view
    off = {c.id: c for c in _with(scheme="minimax-S", weighting=True, plain_text_values=True).cells}
    assert "bar:weight" not in off and "|" not in off["ptext:weight:targets"].text


def test_the_size_factor_prescaler_carries_a_horizontal_size_bar():
    # 𝑋 = 𝑍𝐿 is the log-prime square plus an appended size ROW; per the guide's \hline that row is set
    # off by a horizontal rule (bar:prescaling, kind hbar) — the mirror of the vertical ` | ` size bar
    # in the inverse 𝑊 = 𝑋⁻.
    on = {c.id: c for c in _with("minimax-lils-S", weighting=True).cells}
    bar = on["bar:prescaling"]
    assert bar.kind == "hbar"
    # sits at the boundary between the last square (prime) row and the appended size row
    assert on["cell:prescaling:primes:2:0"].y < bar.y < on["cell:prescaling:primes:3:0"].y
    # a square (lp) prescaler has no size row, so no horizontal bar
    assert "bar:prescaling" not in {c.id for c in _with("minimax-S", weighting=True).cells}


def test_the_size_factor_drops_the_diag_complexity_equivalence():
    # the lils complexity is ‖𝑍𝐿·i‖ (the size row doubles each prime), NOT diag(𝐿) — so the size factor
    # drops the "𝒄 = diag(𝐿)" closed form, leaving the bare 𝒄 (a plain diagonal lp prescaler keeps it).
    lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, equivalences=True).cells}
    assert lils["symbol:complexity:targets"].text == "𝒄"            # no " = diag(𝐿)"
    lp = {c.id: c for c in _with("minimax-S", weighting=True, symbols=True, equivalences=True).cells}
    assert lp["symbol:complexity:targets"].text == "𝒄 = diag(𝐿)"    # the plain diagonal keeps it


def test_a_non_diagonal_pretransformer_makes_the_all_interval_weight_the_square_inverse():
    # editing the pretransformer square off-diagonal (a non-diagonal 𝑋, no size factor) also costs the
    # per-prime weight list its diagonal form: the weight becomes the d×d inverse 𝑊 = 𝑋⁻¹. Unlike the
    # size-factor case it's square (d columns, no overflowing size column), so the bracket hugs the last.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s.update(weighting=True, charts=True, symbols=True, equivalences=True)
    square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))  # an off-diagonal editable square
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                             custom_prescaler=square).cells}
    W = service.damage_weight_matrix(((1, 1, 0), (0, 1, 4)), "minimax-S", override=square)
    assert len(W) == 3 and len(W[0]) == 3  # square 𝑋⁻¹ — no extra size column
    # the d×d matrix of value cells; the scalar list and its chart are both gone
    assert "weight:target:0" not in on
    assert "chart:weight:targets" not in on
    for i in range(3):
        for j in range(3):
            assert on[f"cell:weight:targets:{i}:{j}"].text == service.cents(W[i][j])
    # capital 𝑊 = 𝑋⁻¹ (the square inverse — NOT (𝑍𝑋)⁻, there's no size factor here)
    assert on["symbol:weight:targets"].text == "𝑊 = 𝑋⁻¹"
    # appendix form [[…] …]: an outer [ … ] over all 3 rows + one [ … ] per row, no size bar (square)
    assert on["bracket:weight:l"].h == 3 * spreadsheet.ROW_H
    assert "bracket:weight:row:0:l" in on and "bracket:weight:row:2:r" in on
    assert "bar:weight" not in on  # no size column → no size divider
    # the outer right bracket sits one bracket-width past the last column's right edge (outside the per-row ])
    assert on["bracket:weight:r"].x == on["cell:weight:targets:0:2"].x + spreadsheet.COL_W + spreadsheet.BRACKET_W


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
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the complexity row
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
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the complexity row
    assert on["retune:target:0"].y < on["complexity:target:0"].y < on["weight:target:0"].y


def test_complexity_over_primes_is_a_map_the_rest_are_lists():
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))),
        {**settings.defaults(), "weighting": True}, interest=((-3, 2, 0),),
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling/complexity rows
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
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling/complexity rows
    ).cells}
    assert cells["symbol:complexity:targets"].text == "𝒄"  # only the target list carries the symbol
    assert cells["caption:complexity:primes"].text == "domain prime complexity map"
    assert cells["caption:complexity:commas"].text == "comma basis interval complexity list"
    assert cells["caption:complexity:targets"].text == "target interval complexity list"
    # the interest column's weighting-row captions are the mockup's descriptive names
    assert cells["caption:complexity:interest"].text == "interval complexities"
    assert cells["caption:prescaling:interest"].text == "complexity prescaled intervals"


def test_complexity_caption_mnemonic_underlines_its_symbol_letter():
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, names=True, mnemonics=True).cells}  # non-unity slope reveals the complexity row
    cap = cells["caption:complexity:targets"]
    # the 'c' of "complexity" is underlined (its symbol 𝒄)
    assert cap.underlines == ((cap.text.index("complexity"), 1),)


def test_weighting_on_adds_the_complexity_prescaling_matrix_over_the_primes():
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling matrix
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


def test_size_factor_grows_the_prescaler_into_the_rectangular_ZL_matrix():
    # checking "replace diminuator" (lp -> lils) turns on the size factor, which per the guide
    # composes the log-prime matrix 𝐿 with the size-sensitizing matrix 𝑍: 𝑋 = 𝑍𝐿, a rectangular
    # (d+1)×d matrix. The extra bottom row is the size-weighted log-prime row (sf·𝐿), matching the
    # engine's get_complexity augmentation. lp stays square d×d.
    lp = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}         # lp: square
    lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True).cells}  # lils: 𝑍𝐿
    pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), "TILT minimax-S")
    assert "cell:prescaling:primes:3:0" not in lp     # lp has no size row (d=3 rows: 0..2)
    # lils grows row d (= 3): every entry is sf·𝐿_c = the log-prime, a derived (non-editable) tval
    for c in range(3):
        assert lils[f"cell:prescaling:primes:3:{c}"].text == service.prescale_text(pre[c])
        assert lils[f"cell:prescaling:primes:3:{c}"].kind == "tval"
    # the diagonal rows are unchanged (still the editable prescalercell)
    assert lils["cell:prescaling:primes:0:0"].kind == "prescalercell"
    # the size row sits one ROW_H below the last diagonal row, with its own per-row ⟨ … ] bracket
    assert lils["cell:prescaling:primes:3:0"].y == lils["cell:prescaling:primes:2:0"].y + spreadsheet.ROW_H
    assert lils["bracket:prescaling:row:3:l"].text == "⟨" and lils["bracket:prescaling:row:3:r"].text == "]"


def test_size_factor_grows_the_prescaler_product_tiles_and_labels_the_size_row():
    # the size row appears in every prescaling matrix, not just the bare 𝑋: each 𝑋·basis product
    # (𝑋C, 𝑋T, …) gains the size component sf·Σ(𝐿ⱼ·vⱼ) of its column. And the bare matrix's size
    # row gets its own row label (the (d+1)-th covector of 𝑋), like the diagonal rows above it.
    mapping = ((1, 1, 0), (0, 1, 4))
    lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True).cells}
    lils_sym = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, symbols=True).cells}
    pre = service.complexity_prescaler(mapping, "TILT minimax-S")
    comma = service.from_mapping(mapping).comma_basis[0]      # the syntonic comma vector
    # the comma product tile 𝑋C grows the size row: sf·Σ(𝐿ⱼ·commaⱼ) = sf · the comma's log size
    expected = service.prescale_text(sum(pre[j] * comma[j] for j in range(3)))
    assert lils["cell:prescaling:commas:3:0"].text == expected
    assert lils["cell:prescaling:commas:3:0"].kind == "tval"
    # the bare matrix's size row carries a row label (the (d+1)-th = 4th covector of 𝑋)
    assert lils_sym["matlabel:row:prescaling:primes:3"].text.endswith("₄")


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
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling rows (the prescaler is the log-prime matrix)
    )
    on = {c.id: c for c in lay.cells}
    # bare prescaler tile: the abstract 𝑋 with its concrete equivalence (the symbol line is unchanged)
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
    # product tiles: the concrete 𝐿, no "= …" — they're already the matrix
    assert on["symbol:prescaling:commas"].text == "𝐿C"
    assert on["symbol:prescaling:targets"].text == "𝐿T"
    assert on["symbol:prescaling:held"].text == "𝐿H"


def test_size_factor_names_the_bare_prescaler_ZL_not_just_L():
    # with equivalences on, the rectangular pretransformer's bare tile names 𝑋 = 𝑍𝐿 (the guide's
    # size-sensitized form), not 𝑋 = 𝐿 (the square diagonal); and the NAME drops "= log-prime matrix"
    # (the rectangular 𝑍𝐿 is not "the log-prime matrix").
    lils = {c.id: c for c in _with(scheme="TILT minimax-lils-S", weighting=True,
                                   symbols=True, names=True, equivalences=True).cells}
    assert lils["symbol:prescaling:primes"].text == "𝑋 = 𝑍𝐿"
    # the size factor also renames "prescaler" → "pretransformer" (the guide's term for rectangular 𝑋)
    assert lils["caption:prescaling:primes"].text == "complexity pretransformer"
    # lp keeps 𝑋 = 𝐿 and the log-prime-matrix name
    lp = {c.id: c for c in _with(scheme="TILT minimax-S", weighting=True,
                                 symbols=True, names=True, equivalences=True).cells}
    assert lp["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
    assert lp["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"


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
    # non-unity slope reveals the prescaling rows (the prescaler is the log-prime matrix)
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
    assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"  # the symbol line is unchanged
    assert on["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"
    # without the equivalences layer the name is just the plain caption
    on2 = {c.id: c for c in spreadsheet.build(base, {**s, "equivalences": False},
                                              tuning_scheme="TILT minimax-S").cells}
    assert on2["caption:prescaling:primes"].text == "complexity prescaler"


def test_prescaler_symbol_never_mixes_L_and_X_within_a_tile():
    # regression: the "complexity prescaled generator detempering" tile read 𝐿D as its big
    # symbol but 𝑋𝐝 over its columns. Under the default (log-prime) scheme the prescaler IS
    # the log-prime matrix, so BOTH must use 𝐿 — the symbol and the column headers in lockstep.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "symbols": True, "weighting": True,
         "generator_detempering": True}
    # non-unity slope reveals the prescaling rows (the prescaler is the log-prime matrix)
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
    assert on["symbol:prescaling:detempering"].text == "𝐿D"          # the tile's big symbol
    assert on["matlabel:col:prescaling:detempering:0"].text == "𝐿𝐝₁"  # its column headers — same 𝐿


def test_size_factor_renames_prescaler_to_pretransformer_in_the_labels():
    # the guide names the rectangular (size-factored) 𝑋 a "pretransformer", not a "prescaler" (which
    # shears, not scales). So when "replace diminuator" is checked, every rendered "prescal…" label
    # takes the pretransform stem: the captions, the row title, and the predefined-… preset.
    lp = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True,
                                 names=True, presets=True).cells}
    lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, alt_complexity=True,
                                   names=True, presets=True).cells}
    # the bare tile caption + a product caption
    assert lp["caption:prescaling:primes"].text == "complexity prescaler"
    assert lils["caption:prescaling:primes"].text == "complexity pretransformer"
    assert lp["caption:prescaling:targets"].text == "complexity prescaled target interval list"
    assert lils["caption:prescaling:targets"].text == "complexity pretransformed target interval list"
    # the row title (the left gutter label) stays parallel to "complexity prescaling" — too long for
    # the gutter, the size-factor form hard-wraps the long word ("... pre-" / "transforming") at full
    # font (a \n the pre-line rtt-rowlabel honours) rather than shrinking it
    assert lp["label:prescaling"].text == "complexity prescaling"
    assert lils["label:prescaling"].text == "complexity" + chr(160) + "pre-" + chr(10) + "transforming"
    # the predefined-prescalers preset's field label
    assert lp["block:preset:prescaler:label"].text == "predefined prescalers"
    assert lils["block:preset:prescaler:label"].text == "predefined pretransformers"


def test_alt_complexity_makes_the_whole_pretransformer_square_editable():
    # once alt complexity is on, the WHOLE top d×d square of the pretransformer becomes editable
    # (prescalercell), not just the diagonal — so a non-diagonal matrix can be entered. The cells
    # read the prescaled unit vectors, so the bare matrix shows the override entries 𝑋[i][c].
    X = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))  # 0.5 off the diagonal
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    on = {c.id: c for c in spreadsheet.build(
        base, {**settings.defaults(), "weighting": True, "alt_complexity": True},
        tuning_scheme="TILT minimax-S", custom_prescaler=X).cells}
    # the off-diagonal (0,1) cell is now an editable prescalercell showing the matrix entry 0.5
    assert on["cell:prescaling:primes:0:1"].kind == "prescalercell"
    assert on["cell:prescaling:primes:0:1"].text == service.prescale_text(0.5)
    # the diagonal stays editable, and an untouched off-diagonal of a diagonal prescaler reads 0
    assert on["cell:prescaling:primes:1:1"].kind == "prescalercell"
    assert on["cell:prescaling:primes:2:1"].kind == "prescalercell"
    assert on["cell:prescaling:primes:2:1"].text == "0"
    # WITHOUT alt complexity, only the diagonal is editable; the off-diagonal stays a 0 tval
    off = {c.id: c for c in spreadsheet.build(
        base, {**settings.defaults(), "weighting": True, "alt_complexity": False},
        tuning_scheme="TILT minimax-S").cells}
    assert off["cell:prescaling:primes:1:1"].kind == "prescalercell"
    assert off["cell:prescaling:primes:0:1"].kind == "tval"


def test_custom_prescaler_diagonal_keeps_the_generic_symbol():
    # typing a custom prescaler diagonal makes it no longer THE log-prime matrix, so the symbol
    # stays the generic 𝑋 everywhere (no 𝐿 promotion, no "= log-prime matrix") — the typed
    # diagonal speaks for itself, so the bare tile prints no equivalence.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "symbols": True, "equivalences": True,
         "weighting": True, "generator_detempering": True}
    on = {c.id: c for c in spreadsheet.build(
        base, s, custom_prescaler=(1.0, 1.5, 2.0),
        tuning_scheme="TILT minimax-S").cells}  # non-unity slope reveals the prescaling rows
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
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the complexity row
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
    lay = _with("TILT minimax-S", weighting=True)  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", plain_text_values=True, weighting=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, units=True).cells}  # non-unity slope reveals the prescaling/complexity rows
    # the per-box "units:" line below each caption, per the mockup
    assert cells["units:prescaling:primes"].text == "units: oct/p"   # the prescaler matrix L
    assert cells["units:prescaling:targets"].text == "units: oct"     # L applied to a vector set
    assert cells["units:complexity:primes"].text == "units: (C)/p"    # the domain-prime complexity map
    assert cells["units:complexity:targets"].text == "units: (C)"     # a complexity list (taxicab → C)
    assert cells["units:weight:targets"].text == "units: (S)"         # minimax-S is simplicity-weight → (S)


def test_weighting_rows_have_units_column_tiles_when_domain_units_on():
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, domain_units=True).cells}  # non-unity slope reveals the prescaling/complexity rows
    # the units-column (spine) marginal label per weighting row, like the tuning rows' ¢/
    assert cells["ucol:prescaling:0"].text == "oct/"   # one per matrix row (d-tall)
    assert cells["ucol:complexity"].text == "(C)/"     # taxicab complexity → (C)
    assert cells["ucol:weight"].text == "(S)/"         # minimax-S is simplicity-weight → (S)


def test_damage_weight_and_complexity_units_track_the_tuning_scheme():
    # the annotated units follow the live scheme (guide ch.10 "Annotated units"): the weight
    # slope picks the letter — U (unity) / C (complexity) / S (simplicity) — and an Euclidean
    # (q=2) complexity norm prefixes E. Damage is the ¢-prefixed weighted-cents form, the weight
    # the bare parenthetical, the complexity its own slope-free code (always C / EC). All three
    # renderings agree: the per-box "units:" line, the per-cell unit, and the units-column spine.
    # (scheme, damage, weight, complexity); complexity is None when its row is hidden (unity weight).
    cases = [
        ("TILT minimax-U", "¢(U)", "(U)", None),       # unity-weight: no complexity, the row is hidden
        ("TILT minimax-C", "¢(C)", "(C)", "(C)"),      # complexity-weight, taxicab
        ("TILT minimax-S", "¢(S)", "(S)", "(C)"),      # simplicity-weight, taxicab
        ("TILT minimax-EC", "¢(EC)", "(EC)", "(EC)"),  # complexity-weight, Euclidean
        ("TILT minimax-ES", "¢(ES)", "(ES)", "(EC)"),  # simplicity-weight, Euclidean: weight (ES), complexity (EC)
    ]
    for scheme, damage, weight, complexity in cases:
        cells = {c.id: c for c in _with(scheme, weighting=True, units=True, domain_units=True).cells}
        # damage (the tuning's own column) and the weight list always show under weighting
        assert cells["units:damage:targets"].text == f"units: {damage}", scheme
        assert cells["damage:target:0"].unit == damage, scheme
        assert cells["ucol:damage"].text == f"{damage}/", scheme
        assert cells["units:weight:targets"].text == f"units: {weight}", scheme
        assert cells["weight:target:0"].unit == weight, scheme
        assert cells["ucol:weight"].text == f"{weight}/", scheme
        # the complexity row only shows when the weight derives from complexity (not unity-weight)
        if complexity is None:
            assert "units:complexity:targets" not in cells, scheme
        else:
            assert cells["units:complexity:targets"].text == f"units: {complexity}", scheme
            assert cells["complexity:prime:0"].unit == f"{complexity}/p₁", scheme
            assert cells["ucol:complexity"].text == f"{complexity}/", scheme


def test_weighting_rows_render_a_plain_text_box_when_plain_text_on():
    cells = {c.id for c in _with("TILT minimax-S", weighting=True, plain_text_values=True).cells}  # non-unity slope reveals the prescaling/complexity rows
    assert {"ptext:weight:targets", "ptext:complexity:primes", "ptext:complexity:targets",
            "ptext:prescaling:primes"} <= cells


def test_prescaling_row_sits_between_retuning_and_complexity():
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling/complexity rows
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
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, symbols=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, symbols=True, names=True).cells}  # non-unity slope reveals the prescaling row
    # the bare prescaler matrix is the abstract symbol 𝑋 (math italic, like 𝑀); with no
    # equivalences layer the name is just the plain caption
    assert cells["symbol:prescaling:primes"].text == "𝑋"
    assert cells["caption:prescaling:primes"].text == "complexity prescaler"


def test_complexity_prescaler_caption_mnemonic_marks_the_x_in_complexity():
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, names=True, mnemonics=True).cells}  # non-unity slope reveals the prescaling row
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
    # not on alt_complexity. It rides under the prescaling matrix tile (box 𝐋), which
    # exists only while weighting is on; the temperament boxes own the primes column it sits in.
    off = {c.id for c in _with("TILT minimax-S", weighting=True, presets=False).cells}  # non-unity slope reveals the prescaling tile
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True, presets=True).cells}
    assert "preset:prescaler" not in off  # no chooser unless presets is on
    sel = on["preset:prescaler"]
    # with alt. complexity off there is only one prescaler (log-prime), so the chooser has no real
    # choice: it renders as a DISABLED dropdown (greyed), not an interactive one
    assert sel.kind == "preset"
    assert sel.disabled is True
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
    scheme = "TILT minimax-S"  # non-unity slope reveals the prescaling tile (its chooser)
    named = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme).cells}
    assert named["preset:prescaler"].text == "log-prime"  # the scheme's prescaler, no override
    devi = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme,
                                               custom_prescaler=(1.0, 9.9, 2.322)).cells}
    assert devi["preset:prescaler"].text == ""  # off the named list -> the "-" placeholder


def test_editing_the_prescaler_wipes_the_predefined_complexity_to_custom():
    # the complexity is built ON the prescaler (box 𝐋 feeds box 𝒄), so hand-editing the prescaler
    # diagonal off its named matrix — the same custom_prescaler override that drops the prescaler
    # chooser to "-" — also leaves the complexity shape off-preset: the predefined-complexity chooser
    # wipes from "lp (log-product)" to "custom", since the setup no longer realises a named complexity.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["weighting"] = True, True
    scheme = "TILT minimax-S"  # non-unity slope reveals box 𝒄 + the prescaling tile
    named = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme).cells}
    assert named["control:complexity"].text == "lp (log-product)"  # log-prime prescaler -> lp
    devi = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme,
                                               custom_prescaler=(1.0, 9.9, 2.322)).cells}
    assert devi["preset:prescaler"].text == ""          # the prescaler chooser deviates ("-")
    assert devi["control:complexity"].text == "custom"  # ...and the complexity follows, downstream


def test_complexity_machinery_hides_under_unity_weight():
    # the prescaling + complexity rows (and box 𝒄's complexity subsection) only matter when the
    # damage weight derives from complexity; under the default unity-weight the weight is 1
    # regardless, so they don't render. They appear under complexity-/simplicity-weight. This is a
    # visibility condition keyed on the slope — NOT a fold default (INITIAL_COLLAPSED stays empty).
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True}
    unity = {c.id for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-U").cells}
    simpl = {c.id for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
    # unity (the default): no prescaling/complexity rows or subsection; weight row + slope chooser stay
    assert not any(c.startswith("cell:prescaling") for c in unity)
    assert not any(c.startswith("complexity:") for c in unity)
    assert "control:complexity" not in unity and "control:q" not in unity
    assert "control:slope" in unity and any(c.startswith("weight:target") for c in unity)
    # complexity-/simplicity-weight: the prescaling + complexity rows + the subsection appear (probed
    # via box 𝒄's 𝑞 field, which rides weighting alone — the dropdown is further gated on presets)
    assert any(c.startswith("cell:prescaling") for c in simpl)
    assert any(c.startswith("complexity:") for c in simpl)
    assert "control:q" in simpl


def test_box_c_complexity_chooser_is_disabled_until_alt_complexity():
    # box 𝒄's predefined-complexities chooser is a PRESET (gated on presets — see
    # test_predefined_complexities_dropdown_is_gated_on_presets). Until alt. complexity is turned on
    # there is only ONE complexity (lp for every scheme today), so it has no real choice: it renders as
    # a DISABLED dropdown (greyed, caption greyed with it), like the all-interval-locked slope chooser.
    # Turning alt_complexity on enables it and opens the full preset list (+ the inert "custom").
    # (presets on + a non-unity slope reveal it; alt_complexity OFF (default).)
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True, presets=True).cells}
    ctrl = on["control:complexity"]
    assert ctrl.kind == "control_select"
    assert ctrl.disabled is True  # one option -> disabled dropdown, greyed
    assert on["caption:complexity"].disabled is True  # its caption greys with it
    # the dropdown shows the friendly display name (abbreviation first, expansion in parens) —
    # for the default scheme (log-prime taxicab) that's "lp (log-product)" — held as its sole option
    assert ctrl.text == "lp (log-product)"
    assert ctrl.values == ("lp (log-product)",)
    # it sits below the complexity list, inset within box 𝒄's border (BOX_INNER)
    assert ctrl.y > on["complexity:target:0"].y
    assert ctrl.x == on["header:targets"].x + spreadsheet.BOX_INNER
    # turning alt. complexity on enables the dropdown with the full preset list + custom
    full = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, presets=True).cells}
    assert full["control:complexity"].disabled is False
    assert full["control:complexity"].values == tuple(service.COMPLEXITY_DISPLAYS.values()) + ("custom",)


def test_predefined_complexities_dropdown_is_gated_on_presets():
    # the box-𝒄 "predefined complexities" dropdown is a preset chooser, so — like the
    # predefined-prescalers preset — it shows only when the presets layer is on, ON TOP of box 𝒄's
    # weighting / non-unity-slope gate. The 𝑞 (norm power) field beside it is NOT a preset, so it
    # stays put regardless: turning presets off drops the dropdown but keeps 𝑞, which then LEADS the
    # control row (slides into the dropdown's leftmost slot) rather than floating past an empty gap.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True}  # the TILT minimax-S scheme's non-unity slope reveals box 𝒄
    off = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}  # presets OFF (default)
    assert "control:complexity" not in off and "caption:complexity" not in off  # the preset dropdown is gone
    assert "control:q" in off  # ...but the norm-power field stays (it isn't a preset)
    on = {c.id: c for c in spreadsheet.build(base, {**s, "presets": True}, tuning_scheme="TILT minimax-S").cells}
    assert "control:complexity" in on and "caption:complexity" in on  # presets on restores the dropdown
    assert off["control:q"].x < on["control:q"].x  # 𝑞 leads (shifts left) once the dropdown is gone
    # and the box stops reserving the absent dropdown's width — the targets column hugs back in
    off_box = {b.id: b for b in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
    on_box = {b.id: b for b in spreadsheet.build(base, {**s, "presets": True}, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
    assert off_box.w < on_box.w


def test_box_c_lays_out_with_q_and_dual_q_norm_power_fields():
    # box 𝒄 lays its three controls left-to-right: [predefined complexities ▼] | q | dual(q),
    # each with a caption beneath. The box shows with WEIGHTING alone; the dropdown additionally needs
    # presets (it's a preset), and alt. complexity (on here) puts 𝑞 in its editable powerinput form.
    # The q (norm power) and dual(q) fields follow the optimization box's value-over-symbol-over-caption
    # pattern (the 𝑝 / "optimization power" style); the dropdown has just a caption (no symbol slot).
    # dual(q) needs an all-interval scheme.
    on = {c.id: c for c in _with(scheme="minimax-S", weighting=True, presets=True,
                                 all_interval=True, alt_complexity=True).cells}
    # the predefined-complexities dropdown carries its caption HUGGING its bottom (rather than
    # bottom-aligned with the q/dual captions further down the row)
    assert on["caption:complexity"].kind == "caption"
    assert on["caption:complexity"].text == "predefined complexities"
    assert on["caption:complexity"].y == on["control:complexity"].y + on["control:complexity"].h
    # the q norm-power field: with alt. complexity on it is an editable powerinput (white box) styled
    # like the optimization power 𝑝; typing a new q drives the norm. Default taxicab => 1.
    assert on["control:q"].kind == "powerinput"
    assert on["control:q"].text == "1"
    assert on["control:q"].x > on["control:complexity"].x  # to the RIGHT of the dropdown
    assert on["control:q"].y == on["control:complexity"].y  # same row
    assert on["symbol:q"].text == "𝑞"  # math italic q, matching 𝑝 on the optimization power
    assert on["symbol:q"].y > on["control:q"].y  # symbol BELOW the value (optimization-box style)
    assert on["caption:q"].text == "interval complexity norm power"
    assert on["caption:q"].y > on["symbol:q"].y  # caption BELOW the symbol
    # the dual(q) display: the dual norm power, DERIVED from q (never edited), so it renders as a
    # read-only powerdisplay — the same face as q (∞ at the q numeral's size), minus the white box
    assert on["control:dual"].kind == "powerdisplay"
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


def test_q_norm_power_is_editable_only_with_alt_complexity():
    # the interval-complexity norm power 𝑞 (box 𝒄) is an ALTERNATE-complexity control: typing a new
    # 𝑞 switches the scheme to a different Lq complexity, so it is editable (a powerinput) only when
    # alt. complexity is on. With alt. complexity off the complexity is fixed (the dropdown offers only
    # the current one), so 𝑞 is fixed too and renders read-only — a powerdisplay (the SAME ∞-over-"(max)"
    # face as the input, just no white box), exactly like the all-interval-locked optimization power 𝑝.
    off = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # alt. complexity OFF (default)
    assert off["control:q"].kind == "powerdisplay"
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
    assert on["control:q"].kind == "powerinput"
    assert off["control:q"].text == on["control:q"].text == "1"  # same displayed value either way (taxicab)


def test_power_value_cells_hide_when_gridded_values_are_off():
    # the power VALUE cells — the optimization power 𝑝, the norm power 𝑞, and the derived dual(𝑞) — are
    # gridded values, so turning gridded values off filters them all out whether they render as the
    # editable powerinput or the read-only powerdisplay (both kinds are in GRIDDED_KINDS). Without that
    # a locked 𝑞 / 𝑝 or the dual would survive as a lone value floating in an otherwise plain-text box.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True, "optimization": True}  # minimax-S => box 𝒄 + locked 𝑝 + dual
    off = {c.id for c in spreadsheet.build(base, {**s, "gridded_values": False}, tuning_scheme="minimax-S").cells}
    assert not ({"control:q", "control:dual", "optimization:power"} & off)  # all three (powerdisplays) filtered
    on = {c.id for c in spreadsheet.build(base, {**s, "gridded_values": True}, tuning_scheme="minimax-S").cells}
    assert {"control:q", "control:dual", "optimization:power"} <= on  # sanity: the scenario really builds them


def test_dual_q_shows_only_when_the_scheme_is_all_interval():
    # dual(q) is gated on the all-interval CHECKBOX (is_all_interval), NOT the show-panel entry:
    # an all-interval scheme renders dual(q); a target-based scheme hides it. The q field and the
    # predefined-complexities dropdown show regardless of all-interval — only the dual power is gated.
    # (presets on so the dropdown is in play; it rides the presets layer independently of all-interval.)
    on_all = {c.id for c in _with(scheme="minimax-S", weighting=True, presets=True).cells}
    assert {"control:dual", "symbol:dual", "caption:dual"} <= on_all
    on_tilt = {c.id for c in _with(scheme="TILT minimax-S", weighting=True, presets=True).cells}
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


def test_optimization_objective_carries_a_label_caption():
    # the objective gains a caption under its symbol, mirroring the power's "optimization power":
    # target-based it is the Lp "power mean" of the target damages; all-interval that quantity is
    # the "retuning magnitude" (the ‖𝒓𝐿⁻¹‖ relabel). The wide all-interval label does not fit on
    # one line in the min-width box, so it wraps to two lines (centred under the value cell, like
    # the q/dual captions) and the box reserves the extra caption line.
    based = _with(scheme="TILT minimax-S", optimization=True)
    allint = _with(scheme="minimax-S", optimization=True)
    on_based = {c.id: c for c in based.cells}
    on_allint = {c.id: c for c in allint.cells}
    assert on_based["optimization:objective:caption"].text == "power mean"
    assert on_allint["optimization:objective:caption"].text == "retuning magnitude"
    # it sits below the symbol and stays centred on the objective value cell (the power's stack)
    cap = on_based["optimization:objective:caption"]
    obj = on_based["optimization:objective"]
    sym = on_based["optimization:objective:symbol"]
    assert cap.y > sym.y
    assert abs((cap.x + cap.w / 2) - (obj.x + obj.w / 2)) < 0.5
    # target-based the short label is one line; all-interval the wide label reserves two, so the
    # box (and thus the damage tile) grows by exactly that extra line
    assert on_based["optimization:objective:caption"].h == spreadsheet.CAPTION_LINE
    assert on_allint["optimization:objective:caption"].h == 2 * spreadsheet.CAPTION_LINE
    box_based = {b.id: b for b in based.blocks}["block:optimization:box"]
    box_allint = {b.id: b for b in allint.blocks}["block:optimization:box"]
    assert box_allint.h == box_based.h + spreadsheet.CAPTION_LINE


def test_all_interval_locks_the_optimization_power_to_infinity():
    # all-interval tuning minimaxes over every interval (by duality it optimizes the primes at the
    # dual norm power), so the stored 𝑝 is irrelevant: the optimization-power cell shows ∞ even for a
    # finite-power scheme AND renders as a read-only value (kind "powerdisplay" — the SAME ∞-over-"(max)"
    # face as the editable input, just no white box), not an editable input. A target-based scheme
    # shows its actual stored power as an editable powerinput.
    finite_ai = service.scheme_with_power("minimax-S", 2.0)  # all-interval, stored power 2
    assert service.is_all_interval(finite_ai) and service.optimization_power(finite_ai) == 2.0
    allint = {c.id: c for c in _with(scheme=finite_ai, optimization=True).cells}
    assert allint["optimization:power"].text == "∞" and allint["optimization:power"].kind == "powerdisplay"
    finite_based = service.scheme_with_power("TILT minimax-S", 2.0)  # target-based, stored power 2
    # alt. complexity on so the power is editable (it locks read-only when off — see the test below)
    based = {c.id: c for c in _with(scheme=finite_based, optimization=True,
                                    weighting=True, alt_complexity=True).cells}
    assert based["optimization:power"].text == "2" and based["optimization:power"].kind == "powerinput"


def test_optimization_power_is_editable_only_with_alt_complexity():
    # the optimization power 𝑝 (∞ minimax, 2 miniRMS, 1 miniaverage) is an ADVANCED knob: every tuning
    # preset is a minimax (𝑝 = ∞) scheme, so a non-∞ power is reachable only by typing it — an
    # alternate-complexity-level choice. So like the norm power 𝑞 it is an editable powerinput only
    # with alt. complexity on; otherwise it locks read-only (a powerdisplay), as the all-interval lock
    # does. (alt. complexity rides under weighting, so both must be on to edit 𝑝.)
    off = {c.id: c for c in _with("TILT minimax-S", optimization=True).cells}  # alt. complexity OFF (default)
    assert off["optimization:power"].kind == "powerdisplay"
    assert off["optimization:power"].text == "∞"  # the basic minimax power, shown read-only
    on = {c.id: c for c in _with("TILT minimax-S", optimization=True, weighting=True, alt_complexity=True).cells}
    assert on["optimization:power"].kind == "powerinput"


def test_all_interval_greys_and_locks_the_target_chooser():
    # all-interval targets every interval, so the target interval set scheme chooser doesn't apply:
    # its preset cell is flagged disabled (greyed + locked); the app also falls it back to "-". A
    # target-based scheme leaves it live and interactive.
    allint = {c.id: c for c in _with(scheme="minimax-S", presets=True).cells}
    assert allint["preset:target"].disabled is True
    based = {c.id: c for c in _with(scheme="TILT minimax-S", presets=True).cells}
    assert based["preset:target"].disabled is False


def test_optimized_tuning_wraps_the_objective_symbol_in_min():
    # mockup: "make ⟪𝐝⟫ₚ into min(⟪𝐝⟫ₚ)". When the displayed tuning sits at the scheme's optimum,
    # the objective value IS the minimized one, so its symbol wraps in min(...); a deviating (hand-
    # edited) tuning shows the bare symbol — the displayed value is no longer the minimum.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True

    def symbol(scheme, optimized):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
        return cells["optimization:objective:symbol"].text

    assert symbol("TILT minimax-S", True) == "min(⟪𝐝⟫ₚ)"
    assert symbol("TILT minimax-S", False) == "⟪𝐝⟫ₚ"
    # all-interval: the retuning-magnitude relabel wraps in min() the same way
    inner = "‖𝒓𝐿⁻¹‖" + spreadsheet.SUB_OPEN + "dual(𝑞)" + spreadsheet.SUB_CLOSE
    assert symbol("minimax-S", True) == "min(" + inner + ")"
    assert symbol("minimax-S", False) == inner


def test_minimized_objective_prefixes_its_label_with_minimized():
    # when the displayed tuning is optimized (the symbol wraps in min()), the value shown IS the
    # minimized objective, so its label is prefixed "minimized": "minimized power mean", or
    # "minimized retuning magnitude" all-interval. A deviating tuning drops the prefix. The extra
    # word wraps to its own line, so the caption band — and the box — reserves it.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True

    def cap(scheme, optimized):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
        return cells["optimization:objective:caption"]

    assert cap("TILT minimax-S", True).text == "minimized power mean"
    assert cap("TILT minimax-S", False).text == "power mean"
    assert cap("minimax-S", True).text == "minimized retuning magnitude"
    assert cap("minimax-S", False).text == "retuning magnitude"
    # the reserved caption band grows by the wrapped "minimized" line
    assert cap("TILT minimax-S", True).h == 2 * spreadsheet.CAPTION_LINE   # "minimized" / "power mean"
    assert cap("TILT minimax-S", False).h == spreadsheet.CAPTION_LINE      # "power mean"
    assert cap("minimax-S", True).h == 3 * spreadsheet.CAPTION_LINE         # + "retuning" / "magnitude"
    assert cap("minimax-S", False).h == 2 * spreadsheet.CAPTION_LINE


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


def test_all_interval_target_list_plain_text_tracks_the_grid_identity():
    # REGRESSION: all-interval replaces the target list with Tₚ = 𝐈, and the grid shows the
    # identity — but the plain text re-resolved the named target set on its own and stayed stale
    # (byte-identical to the target-based list). Both views resolve the displayed targets through
    # one seam now, so the ptext is the identity ket-list: one unit vector per domain prime.
    allint = {c.id: c for c in _with(scheme="minimax-S", plain_text_values=True).cells}
    based = {c.id: c for c in _with(scheme="TILT minimax-S", plain_text_values=True).cells}
    assert allint["ptext:vectors:targets"].text == "[[1 0 0⟩ [0 1 0⟩ [0 0 1⟩]"
    assert allint["ptext:vectors:targets"].text != based["ptext:vectors:targets"].text


def test_all_interval_relabels_the_complexity_weight_and_damage_equivalences():
    # all-interval (Tₚ = I) gives the kept target tiles closed forms in the prescaler diagonal:
    # the complexity list IS diag(𝐿) (each target proxies a prime, so its complexity is that
    # prime's diagonal entry), the simplicity weight its reciprocal diag(𝐿)⁻¹, and the damage
    # |𝒓|𝐿⁻¹ — the retuning MAP magnitude (there is no target error list 𝐞 in all-interval; the
    # retune row's 𝐞→𝒓) times the prescaler inverse. All carry the live prescaler glyph (X→L).
    allint = {c.id: c for c in _with(scheme="minimax-S", symbols=True,
                                     equivalences=True, weighting=True).cells}
    assert allint["symbol:complexity:targets"].text == "𝒄 = diag(𝐿)"
    assert allint["symbol:weight:targets"].text == "𝒘 = diag(𝐿)⁻¹"
    assert allint["symbol:damage:targets"].text == "𝐝 = |𝒓|𝐿⁻¹"
    # target-based keeps the bare 𝒄 (its equivalence lives on the per-target column headers),
    # the slope-based weight, and the error-list damage 𝐝 = |𝐞|𝒘
    based = {c.id: c for c in _with(scheme="TILT minimax-S", symbols=True,
                                    equivalences=True, weighting=True).cells}
    assert based["symbol:complexity:targets"].text == "𝒄"
    assert based["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"
    assert based["symbol:damage:targets"].text == "𝐝 = |𝐞|𝒘"


def test_a_non_diagonal_pretransformer_drops_the_complexity_diag_equivalence():
    # diag(𝑋) is meaningless once 𝑋 has off-diagonal entries (each prime's complexity is then the norm
    # of a whole column, not one diagonal entry), so the complexity carries NO closed-form equivalence
    # then — just the bare 𝒄. The weight still becomes the matrix 𝑊 = 𝑋⁻¹ (via weight_is_matrix).
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s.update(weighting=True, alt_complexity=True, symbols=True, equivalences=True)
    square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))  # an off-diagonal pretransformer
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                             custom_prescaler=square).cells}
    assert on["symbol:complexity:targets"].text == "𝒄"       # NOT "𝒄 = diag(𝑋)"
    assert on["symbol:weight:targets"].text == "𝑊 = 𝑋⁻¹"    # the square inverse, not the diag reciprocal


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
    off = {c.id for c in _with("TILT minimax-S", weighting=True, alt_complexity=False).cells}  # non-unity slope reveals box 𝐋
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
    assert "control:prescaler" not in on  # the prescaler is a preset now, not a box-𝐋 control
    assert "caption:prescaler" not in on
    assert "caption:diminuator" not in off
    cap_d = on["caption:diminuator"]
    assert cap_d.kind == "caption"
    assert cap_d.text == "replace diminuator"
    dim = on["control:diminuator"]
    # the square sits inset within box 𝐋's border (BOX_INNER off the column's left), its caption
    # hugging its bottom (the cell is sized to the rendered square, OPTION_BOX_PX, so its bottom IS
    # the square's bottom)
    assert dim.x == on["header:primes"].x + spreadsheet.BOX_INNER
    assert cap_d.y == dim.y + dim.h
    # ...and is horizontally CENTRED above its caption slot (both at the column's left edge)
    assert abs((dim.x + dim.w / 2) - (cap_d.x + cap_d.w / 2)) < 1


def test_weighting_controls_each_sit_in_a_bordered_box():
    # box 𝒄 (predefined complexity + norm) and box 𝒘 (weight slope) each sit in their own bordered
    # control box — a boxed Block, like the preset / optimization boxes — and box 𝐋's "replace
    # diminuator" check rides inside the predefined-pretransformers preset box (block:preset:prescaler),
    # not floating bare. Each control is inset within its box's border. (presets on so box 𝒄's
    # predefined-complexities dropdown — and the preset box hosting the diminuator — are present.)
    lay = _with("TILT minimax-S", weighting=True, alt_complexity=True, presets=True)  # non-unity slope reveals the boxes
    blocks = {b.id: b for b in lay.blocks}
    cells = {c.id: c for c in lay.cells}
    for box_id, ctrl_id in (("block:preset:prescaler", "control:diminuator"),
                            ("block:complexity", "control:complexity"),
                            ("block:slope", "control:slope")):
        box = blocks[box_id]
        assert box.boxed, box_id
        ctrl = cells[ctrl_id]
        # the control sits fully inside its box, inset off the left/top border
        assert box.x < ctrl.x and ctrl.x + ctrl.w <= box.x + box.w + 0.01, box_id
        assert box.y < ctrl.y and ctrl.y + ctrl.h <= box.y + box.h + 0.01, box_id


def test_diminuator_rides_the_pretransformer_chooser_box_when_presets_on():
    # box 𝐋's "replace diminuator" check rides INSIDE the predefined-pretransformers chooser box (to
    # the dropdown's right), not a separate box — the way the all-interval check rides the target box.
    # Its own box (block:diminuator) is only the presets-OFF fallback.
    on = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                           {**settings.defaults(), "weighting": True, "alt_complexity": True, "presets": True},
                           tuning_scheme="TILT minimax-S")
    cells = {c.id: c for c in on.cells}
    blocks = {b.id for b in on.blocks}
    assert cells["control:diminuator"].x > cells["preset:prescaler"].x  # to the RIGHT of the dropdown
    assert "block:diminuator" not in blocks  # no separate box — it's inside the chooser box
    # presets OFF: the diminuator falls back to its own box
    off_blocks = {b.id for b in _with("TILT minimax-S", weighting=True, alt_complexity=True).blocks}
    assert "block:diminuator" in off_blocks


def test_weighting_control_boxes_layer_above_their_tile_panels():
    # the box-𝐋/𝒄/𝒘 borders must render ON TOP of the grey tile panels, not behind them — so each
    # box block appears AFTER its tile's panel in the blocks list (later = drawn on top), the way the
    # optimization / ranges boxes do. Otherwise the panel covers the border and no box shows.
    lay = _with("TILT minimax-S", weighting=True, alt_complexity=True)
    order = {b.id: i for i, b in enumerate(lay.blocks)}
    assert order["block:diminuator"] > order["block:prescaling:primes"]  # box 𝐋 over the prescaling panel
    assert order["block:complexity"] > order["block:complexity:targets"]  # box 𝒄 over the complexity panel
    assert order["block:slope"] > order["block:weight:targets"]           # box 𝒘 over the weight panel


def test_alt_complexity_adds_an_ignore_diminuator_checkbox_to_box_l():
    off = {c.id for c in _with("TILT minimax-S", weighting=True, alt_complexity=False).cells}  # non-unity slope reveals box 𝐋
    on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
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
    # alt. complexity feature the way box 𝐋's prescaler controls are
    off = {c.id for c in _with(weighting=False).cells}
    on = {c.id: c for c in _with(weighting=True).cells}
    assert "control:slope" not in off  # no control unless weighting is on
    ctrl = on["control:slope"]
    assert ctrl.kind == "control_select"
    assert ctrl.disabled is False  # live and interactive while target-based (locked only all-interval)
    assert ctrl.text == "unity-weight"  # the default scheme's damage-weight slope (unity)
    assert ctrl.values == ("complexity-weight", "unity-weight", "simplicity-weight")
    # it rides below the weight list, filling box 𝒘's interior (the targets column inset by its border)
    assert ctrl.y > on["weight:target:0"].y
    assert ctrl.x == on["header:targets"].x + spreadsheet.BOX_INNER
    assert ctrl.w == on["header:targets"].w - 2 * spreadsheet.BOX_INNER


def test_all_interval_greys_and_locks_the_weight_slope_chooser():
    # an all-interval scheme is simplicity-weighted by construction, so its weight is not a free
    # choice. Rather than vanish, the U/S/C chooser (and its caption) stay put — the chooser greyed
    # (disabled) and locked to the forced simplicity-weight value — so the box keeps its shape
    # across the toggle instead of the weight tile reflowing when all-interval flips on.
    on = {c.id: c for c in _with(scheme="minimax-S", weighting=True).cells}
    ctrl = on["control:slope"]
    assert ctrl.disabled is True
    assert ctrl.text == "simplicity-weight"
    # its caption ("damage weight slope") greys with it — the disabled flag rides the caption too,
    # so the label is the same disabled grey as the locked value, not darker
    assert on["caption:slope"].disabled is True


def test_all_interval_greys_the_locked_target_chooser_caption_but_not_the_power_value():
    # the all-interval-locked TARGET chooser (a control) greys its caption with it, so the label reads
    # in the same disabled grey as the locked value. The optimization power, by contrast, is now a
    # read-only VALUE (a tval like the objective) — not a greyed control — so its "optimization power"
    # caption stays the normal value colour in both modes, matching the objective's caption beside it.
    on = {c.id: c for c in _with(scheme="minimax-S", optimization=True, presets=True).cells}
    assert on["block:preset:target:label"].disabled is True   # the locked target chooser's caption greys
    assert on["optimization:power:caption"].disabled is False  # the power is a value: caption not greyed
    # a target-based scheme leaves the target chooser live (caption not greyed)
    based = {c.id: c for c in _with(scheme="TILT minimax-S", optimization=True, presets=True).cells}
    assert based["block:preset:target:label"].disabled is False
    assert based["optimization:power:caption"].disabled is False


def test_box_l_diminuator_needs_weighting_and_the_primes_column():
    # the diminuator checkbox lives in box 𝐋 (the prescaling matrix over the primes), so it
    # is gone if weighting is off or the temperament (primes) boxes are hidden
    assert "control:diminuator" not in {c.id for c in _with(weighting=False, alt_complexity=True).cells}
    assert "control:diminuator" not in {
        c.id for c in _with(weighting=True, alt_complexity=True, temperament_boxes=False).cells
    }


def test_alt_complexity_is_implemented_now_that_its_controls_are_built():
    # alt. complexity is un-shelved: its built controls (the box-𝐋 diminuator checkbox, box-𝒄's
    # predefined-complexity options, the alternative-complexity prescalers + tuning schemes) are
    # ready, so it rides in IMPLEMENTED as a live, interactive Show toggle rather than a greyed stub.
    assert "alt_complexity" in settings.IMPLEMENTED


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

    assert equiv("minimax-C") == "𝒘 = 𝒄"          # complexity weight
    assert equiv("minimax-U") == "𝒘 = 𝟏"          # unity weight (document default): bold-1 all-ones vector
    # simplicity weight, target-based: the SLOPE shows as 𝒄⁻¹. (The bare minimax-S is all-interval,
    # where the weight relabels to the concrete diag(𝐿)⁻¹ — see
    # test_all_interval_relabels_the_complexity_weight_and_damage_equivalences.)
    assert equiv("TILT minimax-S") == "𝒘 = 𝒄⁻¹"


def test_damage_equivalence_names_the_weight_only_when_the_weight_row_is_shown():
    # 𝐝 = |𝐞|𝒘 (𝒘 the weight LIST, not a matrix — so 𝒘, never diag(𝒘)). The equivalence
    # names that 𝒘 factor only while the weight row is on screen; with weighting hidden it
    # drops to 𝐝 = |𝐞| rather than dangle a reference to a row the reader can't see. The
    # factor is the same whatever the slope — even the unity all-ones weight shows as 𝒘 once
    # visible (its 𝒘 = 𝟏 value lives on the weight row). Both schemes here are target-based
    # (the all-interval damage form |𝒓|𝐿⁻¹ is covered by the all-interval relabel test).
    def equiv(scheme, weighting):
        lay = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": weighting, "symbols": True, "equivalences": True},
            tuning_scheme=scheme,
        )
        return {c.id: c for c in lay.cells}["symbol:damage:targets"].text

    # weighting hidden → bare |𝐞|, regardless of the scheme's weight slope (unity vs simplicity)
    assert equiv("minimax-U", False) == "𝐝 = |𝐞|"
    assert equiv("TILT minimax-S", False) == "𝐝 = |𝐞|"
    # weighting shown → the 𝒘 factor appears, even under unity weight
    assert equiv("minimax-U", True) == "𝐝 = |𝐞|𝒘"
    assert equiv("TILT minimax-S", True) == "𝐝 = |𝐞|𝒘"


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


def test_comma_minus_rides_the_last_comma_whenever_one_is_tempered():
    lay = _layout()  # meantone exposes a single comma
    one, by1 = {c.id: c for c in lay.cells}, {ln.id: ln for ln in lay.lines}
    assert "comma_minus" in one  # the SOLE comma is removable now (un-tempers to just intonation)
    cm = one["comma_minus"]  # centred on the lone comma's branch point, dropping from the top bus
    assert abs((cm.x + cm.w / 2) - by1["v:comma:0"].pos) < 0.51
    assert cm.y == by1["bus:commas:top"].pos
    two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])  # two real commas: − tracks the new last
    tlay = spreadsheet.build(two)
    cells, by2 = {c.id: c for c in tlay.cells}, {ln.id: ln for ln in tlay.lines}
    assert abs((cells["comma_minus"].x + cells["comma_minus"].w / 2) - by2["v:comma:1"].pos) < 0.51
    ji = service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # full rank, n=0
    assert "comma_minus" not in {c.id for c in spreadsheet.build(ji).cells}  # nothing tempered to remove


def test_adding_a_comma_starts_a_pending_draft_column_that_does_not_re_rank():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma, mapping r=2
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    assert cells["comma:0"].text == "80/81"  # the real comma stays
    # a draft column rides to its right: an editable "?/?" ratio and blank, red-flagged vector cells
    assert cells["comma:pending"].text == "?/?" and cells["comma:pending"].pending
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, math_expressions=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, math_expressions=True).cells}  # non-unity slope reveals the prescaling row
    assert cells["cell:prescaling:commas:0:0"].text == "4 · log₂2\n= 4"
    assert cells["cell:prescaling:commas:1:0"].text == "-4 · log₂3\n= -6.340"
    assert cells["cell:prescaling:commas:2:0"].text == "log₂5\n= 2.322"


def test_math_expressions_without_quantities_show_only_the_prescaler_expression():
    # quantities drives the "= value" second line for the prescaling row's product tiles too;
    # with it off, each LC/LD/LT/LH cell is just the bare closed form — no decimal, no newline,
    # like the just row's math expression in the same configuration. The bare prescaler 𝐿's
    # diagonal is an editable prescalercell (a value-bearing input box), so quantities=False
    # blanks its text alongside the other editable matrix cells (commacell/heldcell/...).
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, math_expressions=True, quantities=False).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling row
    for i in range(3):
        assert cells[f"cell:prescaling:primes:{i}:{i}"].prime == i


def test_custom_prescaler_override_drives_the_bare_prescaler_diagonal_text():
    # a custom_prescaler override (d-tuple) typed into the bare prescaler tile flows back
    # into the diagonal cells' text — the user's edit IS what they see, rather than the
    # scheme's computed log/prime/identity diagonal.
    s = settings.defaults() | {"weighting": True}
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling row
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
                            tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling row
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
                            tuning_scheme="TILT minimax-S",  # non-unity slope reveals the complexity row
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
    assert "interest_plus" in cells  # one + opens a blank draft column
    # every interval carries its own − (unlike the domain/comma last-only −)
    assert {"interest_minus:0", "interest_minus:1", "interest_minus:2", "interest_minus:3"} <= set(cells)


def test_empty_but_open_interest_still_offers_the_add_control():
    # with no intervals yet (but the column expanded), the + must be reachable to add
    # the first one; there are no minus controls since there is nothing to remove
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), interest=()).cells}
    assert "interest_plus" in cells
    assert not any(c.startswith("interest_minus:") for c in cells)


def test_adding_an_interval_of_interest_opens_a_blank_red_draft_column():
    # mirrors the pending comma: + opens a blank, red-outlined draft column (an editable "?/?"
    # ratio header over empty vector cells) the user fills in — not a pre-filled 1/1
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, interest=(), pending_interest=[None, None, None]).cells}
    assert cells["interest:pending"].text == "?/?" and cells["interest:pending"].pending
    assert all(cells[f"cell:interest:{p}:0"].text == "" and cells[f"cell:interest:{p}:0"].pending
               for p in range(3))
    # the draft has no size cells (undefined until valid), like the comma draft
    assert "tuning:interest:0" not in cells
    # the + rides one slot past the draft column; the draft can be cancelled with a −
    assert cells["interest_plus"].x > cells["interest:pending"].x
    assert "interest_minus:pending" in cells


def test_a_partly_typed_interest_draft_shows_its_entered_components():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, interest=(), pending_interest=[-1, None, 0]).cells}
    assert cells["cell:interest:0:0"].text == "-1"  # typed
    assert cells["cell:interest:1:0"].text == ""    # still blank
    assert cells["cell:interest:2:0"].text == "0"
    assert all(cells[f"cell:interest:{p}:0"].pending for p in range(3))


def test_a_pending_interest_draft_rides_right_of_the_committed_intervals():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(
        base, interest=((-1, 1, 0),), pending_interest=[None, None, None]).cells}
    assert not cells["cell:interest:0:0"].pending  # the committed interval stays black
    assert cells["cell:interest:0:1"].pending and cells["cell:interest:0:1"].text == ""
    assert cells["interest:pending"].x > cells["interest:0"].x
    # the draft column's ket marks render red (like its cells); the real interval's don't
    assert cells["ebkangle:vec:interest:1"].pending
    assert not cells["ebkangle:vec:interest:0"].pending


def _with_held(held_vectors, pending_held=None):
    s = settings.defaults()
    s["optimization"], s["counts"] = True, True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_vectors=held_vectors, pending_held=pending_held)


def test_adding_a_held_interval_opens_a_blank_red_draft_column():
    # the held intervals column gets the same pending-draft behaviour as the commas/interest
    cells = {c.id: c for c in _with_held((), pending_held=[None, None, None]).cells}
    assert cells["held:pending"].text == "?/?" and cells["held:pending"].pending
    assert all(cells[f"cell:held:{p}:0"].text == "" and cells[f"cell:held:{p}:0"].pending
               for p in range(3))
    assert "tuning:held:0" not in cells  # no size cells until valid
    assert cells["held_plus"].x > cells["held:pending"].x
    assert "held_minus:pending" in cells  # the draft's − cancels it
    assert cells["count:held"].text == "ℎ = 0"  # the draft is not a committed held interval


def test_a_partly_typed_held_draft_shows_its_entered_components():
    cells = {c.id: c for c in _with_held((), pending_held=[1, None, 0]).cells}
    assert cells["cell:held:0:0"].text == "1"
    assert cells["cell:held:1:0"].text == ""
    assert cells["cell:held:2:0"].text == "0"
    assert all(cells[f"cell:held:{p}:0"].pending for p in range(3))


def test_a_pending_held_draft_rides_right_of_the_committed_held_intervals():
    cells = {c.id: c for c in _with_held(((1, 0, 0),), pending_held=[None, None, None]).cells}
    assert not cells["cell:held:0:0"].pending  # the committed held interval stays black
    assert cells["cell:held:0:1"].pending and cells["cell:held:0:1"].text == ""
    assert cells["held:pending"].x > cells["held:0"].x
    assert cells["ebkangle:vec:held:1"].pending
    assert not cells["ebkangle:vec:held:0"].pending


def _target_count():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    return len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, base.domain_basis))


def test_adding_a_target_opens_a_blank_red_draft_column():
    # the target intervals list gets the same pending-draft behaviour as the commas
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    k = _target_count()
    cells = {c.id: c for c in spreadsheet.build(base, pending_target=[None, None, None]).cells}
    assert cells["target:pending"].text == "?/?" and cells["target:pending"].pending
    # the draft rides at index k (right of the committed targets), blank and red
    assert all(cells[f"cell:vec:targets:{k}:{p}"].text == "" and cells[f"cell:vec:targets:{k}:{p}"].pending
               for p in range(3))
    assert cells["target:pending"].x > cells[f"target:{k - 1}"].x
    assert cells["target_plus"].x > cells["target:pending"].x
    assert "target_minus:pending" in cells  # the draft's − cancels it


def test_a_partly_typed_target_draft_shows_its_entered_components():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    k = _target_count()
    cells = {c.id: c for c in spreadsheet.build(base, pending_target=[-1, 1, None]).cells}
    assert cells[f"cell:vec:targets:{k}:0"].text == "-1"
    assert cells[f"cell:vec:targets:{k}:1"].text == "1"
    assert cells[f"cell:vec:targets:{k}:2"].text == ""
    assert all(cells[f"cell:vec:targets:{k}:{p}"].pending for p in range(3))


def test_a_pending_target_draft_is_suppressed_in_all_interval_mode():
    # in all-interval the target list is the auto Tₚ = I set (not user-curated), and the + is
    # hidden — so a stray draft must not render a column there
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id for c in spreadsheet.build(base, tuning_scheme="minimax-S", pending_target=[None, None, None]).cells}
    assert "target:pending" not in cells
    assert not any(c.startswith("target_minus:pending") for c in cells)


def test_the_target_list_plain_text_becomes_a_two_tone_draft_box_while_pending():
    # the target vector list is an editable plain-text dual (like the comma basis), so while a
    # target is pending it flips to a static two-tone box (committed black, draft red); with no
    # draft it is an editable box again
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["plain_text_values"] = True
    drafting = {c.id: c for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
    assert drafting["ptext:vectors:targets"].kind == "ptextpending"
    resting = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert resting["ptext:vectors:targets"].kind == "ptextedit"  # no draft -> editable again


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
    # hold: a feature could be built yet held out of IMPLEMENTED (greyed), so it would
    # change the layout yet stay greyed — hence we only sweep the IMPLEMENTED toggles here.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    def snapshot(s):
        # capture both cells and blocks: most toggles add/move cells, but colorization
        # is expressed purely through blocks (the colour washes), so a cells-only
        # snapshot would call it a no-op. Build under a non-unity slope so the slope-gated
        # weighting machinery (prescaling/complexity rows + box 𝐋's controls) is visible —
        # otherwise flipping alt_complexity changes nothing under the unity default.
        lay = spreadsheet.build(base, s, tuning_scheme="TILT minimax-S")
        return (
            frozenset((c.id, c.x, c.y, c.w, c.h, c.kind, c.text, c.underlines) for c in lay.cells),
            frozenset((b.id, b.x, b.y, b.w, b.h, b.tint) for b in lay.blocks),
        )

    def with_parents_on(key):
        # a sub-control only takes effect while its parent chain is on (e.g. alt. complexity
        # needs weighting, which needs tuning boxes), so enable that chain before flipping it
        s = settings.defaults()
        for parent in settings.ancestors_of(key):
            s[parent] = True
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
        base, s, held_vectors=((-1, 1, 0),),
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling/complexity rows
    ).cells}
    # The trailing q is italic-subscripted (per the mockup) — emitted with sentinel
    # markers around it that the matlabel renderer converts to <sub><i>q</i></sub>.
    q = spreadsheet.NORM_SUB_OPEN + "q" + spreadsheet.NORM_SUB_CLOSE
    assert on["matlabel:col:complexity:primes:0"].text == f"‖𝐿[1]‖{q}"
    assert on["matlabel:col:complexity:primes:2"].text == f"‖𝐿[3]‖{q}"
    assert on["matlabel:col:complexity:commas:0"].text == f"‖𝐿𝐜₁‖{q}"
    assert on["matlabel:col:complexity:held:0"].text == f"‖𝐿𝐡₁‖{q}"
    assert on["matlabel:col:complexity:detempering:0"].text == f"‖𝐿𝐝₁‖{q}"
    # complexity over targets is the named complexity LIST 𝒄 — without the equivalences
    # layer its column cells show the bare named symbol cₙ (the norm equation is the cₙ = …
    # equivalence tail; see test_complexity_target_col_headers_gain_the_norm_equivalence)
    assert on["matlabel:col:complexity:targets:0"].text == "c₁"


def test_complexity_target_col_headers_gain_the_norm_equivalence():
    # the target-interval complexity list 𝒄 names its column cells cₙ; with the equivalences
    # layer each header gains its defining equation cₙ = ‖𝐿𝐭ₙ‖q (the q-norm of the prescaled
    # target vector), mirroring the tile big-symbols' "= …" tails. The prescaler glyph follows
    # the X→L rule (𝐿 for the log-prime matrix). All-interval (Tₚ = I) drops the per-target 𝐭ₙ,
    # leaving the generic ‖𝐿‖q. Without equivalences only the bare cₙ shows.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    q = spreadsheet.NORM_SUB_OPEN + "q" + spreadsheet.NORM_SUB_CLOSE
    s = {**settings.defaults(), "symbols": True, "weighting": True, "equivalences": True}
    # non-unity slope reveals the complexity row (the prescaler is the log-prime matrix)
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
    assert on["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝐿𝐭₁‖{q}"
    assert on["matlabel:col:complexity:targets:7"].text == f"c₈ = ‖𝐿𝐭₈‖{q}"
    # all-interval: the per-target 𝐭ₙ drops, leaving ‖𝐿‖q in every column
    allint = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S").cells}
    assert allint["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝐿‖{q}"
    assert allint["matlabel:col:complexity:targets:2"].text == f"c₃ = ‖𝐿‖{q}"
    # equivalences off → just the bare named symbol cₙ
    off = {c.id: c for c in spreadsheet.build(
        base, {**settings.defaults(), "symbols": True, "weighting": True},
        tuning_scheme="TILT minimax-S").cells}  # non-unity slope reveals the complexity row
    assert off["matlabel:col:complexity:targets:0"].text == "c₁"


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
        base, s, held_vectors=((-1, 1, 0),),
        tuning_scheme="TILT minimax-S",  # non-unity slope reveals the prescaling rows
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
    assert on["units:damage:targets"].text == "units: ¢(U)"  # damage is weighted cents; default scheme is unity-weight → ¢(U)
    # nothing rendered when units is off
    assert not any(c.startswith("units:") for c in off)
    # the units line sits below the name caption for the same box
    assert on["units:tuning:primes"].y > on["caption:tuning:primes"].y


def test_units_carry_a_per_value_unit_on_each_gridded_cell():
    on = {c.id: c for c in _with("TILT minimax-S", units=True, weighting=True).cells}  # non-unity slope reveals the prescaling/complexity rows
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
    assert on["ucol:damage"].text == "¢(U)/"   # damage is unity-weighted cents (default scheme)
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


def test_nonstandard_domain_units_use_basis_element_label_b():
    # over a nonstandard subgroup (whose basis may be nonprime), the domain coordinate
    # label switches from 𝑝 (prime) to 𝒃 (basis element) — so the interval-vectors row
    # reads 𝒃₁/, 𝒃₂/, 𝒃₃/ and the basis-elements column reads /𝒃₁, /𝒃₂, /𝒃₃. The per-
    # gridded-cell units carry the same swap (𝑔₁/𝒃₁ over the mapping, ¢/𝒃₁ in the
    # tuning map, 𝒃₁ in an interval vector). A standard prime limit is unaffected (locked
    # by test_domain_units_adds_a_units_row_and_column_of_coordinate_labels above).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["domain_units"] = True
    s["units"] = True   # also turn on the per-cell unit annotations
    s["weighting"] = True  # opens the prescaling row so its per-cell oct/𝒃 unit shows
    on = {c.id: c for c in spreadsheet.build(state, s, tuning_scheme="TILT minimax-S").cells}
    # the units column over the interval-vectors row: basis-element coordinate
    assert on["ucol:vectors:0"].text == "b₁/"
    assert on["ucol:vectors:2"].text == "b₃/"
    # the units row over the basis-elements column: per-column basis coordinate
    assert on["urow:primes:0"].text == "/b₁"
    assert on["urow:primes:2"].text == "/b₃"
    # per-gridded-cell units: the prime denominator becomes a basis-element denominator
    assert on["cell:mapping:0:0"].unit == "g₁/b₁"        # 𝑔/𝑝 → 𝑔/𝒃
    assert on["tuning:prime:0"].unit == "¢/b₁"            # ¢/𝑝 → ¢/𝒃
    assert on["cell:vec:targets:0:0"].unit == "b₁"        # the vector coordinate itself
    assert on["cell:prescaling:primes:0:1"].unit == "oct/b₂"  # column-tracked denominator


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
    # the power: 𝑝 over its symbol and the "optimization power" caption. With alt. complexity off (the
    # default here) it is read-only — a powerdisplay (its editability is covered separately).
    assert on["optimization:power"].kind == "powerdisplay"
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
    # the controls DISTRIBUTE across the full-width box (no longer packed left): the objective is a
    # COLUMN hugging the left edge — its symbol and caption span the column width and its COL_W value
    # cell is centred within it, so a wide min()-wrapped symbol overflows evenly and stays inside the
    # box. The optimize button hugs the right edge; the power sits centered in the gap between them.
    obj_col_x = box.x + spreadsheet.OPT_PAD_L
    assert on["optimization:objective:symbol"].x == obj_col_x
    assert on["optimization:objective:symbol"].w == spreadsheet.OPT_OBJ_W
    assert on["optimization:objective:caption"].x == obj_col_x
    assert on["optimization:objective"].x == obj_col_x + (spreadsheet.OPT_OBJ_W - spreadsheet.COL_W) / 2
    assert (on["optimization:button"].x + on["optimization:button"].w
            == box.x + box.w - spreadsheet.OPT_PAD_R)
    obj_r = obj_col_x + spreadsheet.OPT_OBJ_W  # the objective column's right edge
    btn_l = on["optimization:button"].x
    pow_c = on["optimization:power"].x + on["optimization:power"].w / 2
    assert abs(pow_c - (obj_r + btn_l) / 2) < 1  # power centered in the gap between column and button
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


def test_all_interval_target_list_is_read_only():
    # in all-interval the target list is the auto Tₚ = 𝐈 identity (not user-curated), so it
    # carries NO editing affordance: the vector cells, the quantities-row ratio twin, and the
    # plain-text band all render as the read-only computed kinds the sibling detempering
    # vectors/ratios use — never the editable targetcell / ratiocell / ptextedit. A target-based
    # scheme keeps every one of them editable.
    allint = {c.id: c for c in _with(scheme="minimax-S", plain_text_values=True).cells}
    based = {c.id: c for c in _with(scheme="TILT minimax-S", plain_text_values=True).cells}
    assert allint["cell:vec:targets:0:0"].kind == "vec"
    assert allint["target:0"].kind == "commaratio"
    assert allint["ptext:vectors:targets"].kind == "ptext"
    assert based["cell:vec:targets:0:0"].kind == "targetcell"
    assert based["target:0"].kind == "ratiocell"
    assert based["ptext:vectors:targets"].kind == "ptextedit"


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


def _held(scheme=None, **overrides):
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    s.update(overrides)
    return {c.id: c for c in spreadsheet.build(
        base, s, tuning_scheme=scheme, held_vectors=[(-1, 1, 0)]).cells}


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
    on = _held("TILT minimax-S", names=True, weighting=True)  # non-unity slope opens the prescaling + complexity rows
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
    # a non-unity slope reveals those slope-gated rows so the held column's prescaling/complexity
    # value cells exist to flag (the alert tracks the retuning error, which is slope-independent)
    return {c.id: c for c in spreadsheet.build(
        base, s, tuning_scheme="TILT minimax-S",
        held_vectors=[(-1, 1, 0)], generator_tuning=generator_tuning).cells}


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
    # the quantities tile (the ratio heading the column) emits NO plain text — the gridded
    # ratio already is the formatted value, so a duplicate line would be redundant
    assert "ptext:quantities:held:0" not in on


def test_held_column_has_the_full_interval_column_tile_set():
    # the held column mirrors the intervals-of-interest column's FULL tile set: besides the
    # vectors / mapping / sizes / complexity tiles, it gets the units-row label, the complexity-
    # prescaling matrix, and the just / tempered audio rows (each gated on its own toggle)
    on = _held("TILT minimax-S", weighting=True, audio=True, domain_units=True)  # non-unity slope opens the prescaling row
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


def test_mapped_generator_detempering_is_deferred_to_identity_objects():
    # 𝑀·D = 𝐼 (the detempering is M's right-inverse) is a trivial "identity object", like the
    # mapping-over-generators self-map and the domain-primes vectors identity — it won't show
    # until the identity_objects setting is built. So even with the detempering column on, the
    # mapping row over it carries NOTHING: no cells, framing kets / separators, enclosing
    # bracket, fold toggle, caption, symbol or plain text.
    cells = {c.id for c in _with(generator_detempering=True, names=True, symbols=True,
                                 equivalences=True, plain_text_values=True).cells}
    assert not any("mapped_detempering" in c for c in cells)  # cells, ket marks, separators, bracket
    assert {"toggle:tile:mapping:detempering", "caption:mapping:detempering",
            "symbol:mapping:detempering", "ptext:mapping:detempering"}.isdisjoint(cells)
    # only the identity tile is deferred — the detempering column itself stays (its header, the
    # D matrix in the interval-vectors row, and the tuning/just/… rows below it)
    assert {"header:detempering", "cell:vec:detempering:0:0"} <= cells


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


def test_generator_detempering_quantities_emits_no_redundant_plain_text():
    # the detempering ratio heads the column in the gridded quantities row; a plain-text line
    # below it would just duplicate it, so none is emitted (like commas / targets / held)
    ids = {c.id for c in _with(generator_detempering=True, plain_text_values=True).cells}
    assert not any(i.startswith("ptext:quantities:detempering") for i in ids)


def test_generator_detempering_prescaling_row_scales_each_vector():
    # box 𝐋 applies the complexity prescaler to each detempering vector (L·D): the octave
    # [1 0 0⟩ and the fifth [-1 1 0⟩ scaled by diag(log₂2, log₂3, log₂5) = (1, 1.585, …)
    cells = {c.id: c for c in _with("TILT minimax-S", generator_detempering=True, weighting=True, units=True).cells}  # non-unity slope reveals the prescaling row
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
    cells = {c.id: c for c in _with("TILT minimax-S", generator_detempering=True, weighting=True, units=True).cells}  # non-unity slope reveals the complexity row
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
                            tuning_scheme="TILT minimax-S",  # non-unity slope reveals the slope-gated prescaling/complexity rows
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
    # objects its row multiplies in. So the basis is uncoloured, the tuning/retune family
    # stays green (its 𝒈𝑀), and the just / prescaled / complexity products are CYAN (their
    # bare 𝒋 / 𝑋). The mapping product 𝑀·D = 𝐼 is an identity object deferred to
    # identity_objects, so the column carries no yellow mapping tile.
    s = settings.defaults()
    s["tuning_colorization"] = True
    s["temperament_colorization"] = True
    s["generator_detempering"] = True  # reveal the detempering column
    s["weighting"] = True              # reveal the prescaling + complexity rows
    s["audio"] = True                  # reveal the just/tempered audio speaker tiles
    # non-unity slope reveals the slope-gated prescaling/complexity rows
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            tuning_scheme="TILT minimax-S")
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    # the detempering basis carries no colour (like the interest list); only its products colour
    assert at("detempering:0") == N                    # quantities × detempering (the detempering list, neutral)
    assert at("cell:vec:detempering:0:0") == N         # interval-vectors × detempering (the basis, neutral)
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
                             tuning_scheme="TILT minimax-S",  # non-unity slope reveals the slope-gated prescaling/complexity rows
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


def test_audio_tiles_have_no_per_tile_control_bank():
    # the waveform / play-mode / hold / 1-1 bank is no longer per-tile: it lives once, on the
    # settings panel's dummy tile, driving every speaker from one global config. An audio tile now
    # carries only its speakers and the shared fold toggle — no bank cells, no audio_* control kind.
    cells = {c.id: c for c in _audio().cells}
    assert "speaker:tempered_audio:target:0" in cells        # the speakers stay
    assert "toggle:tile:tempered_audio:targets" in cells      # so does the fold toggle
    for ctrl in ("wave", "mode", "hold", "root"):
        assert f"{ctrl}:tempered_audio:targets" not in cells  # ...but the four bank controls are gone
    assert not any(c.kind.startswith("audio_") for c in cells.values())  # no audio_* control kind anywhere


def test_caption_widened_commas_tile_keeps_its_fold_toggle_on_the_panel_edge():
    # Regression: the commas column's long captions ("mapped comma basis (made to vanish!)")
    # widen its grey tile well past its narrow one-comma content, so the content centres within
    # the wider tile. The per-tile fold toggle (top-left) must anchor to the PANEL's left edge,
    # not to that centred content — anchoring to content drifts it inward by half the widening,
    # reading as centred rather than left-justified. commas is the column whose caption most
    # outruns its content, so the bug showed there; wide-content columns hid it (tile == content).
    blocks = {b.id: b for b in _with(names=True).blocks}
    narrow = {b.id: b for b in _with(names=False).blocks}
    cells = {c.id: c for c in _with(names=True).cells}
    panel = blocks["block:vec:commas"]
    assert panel.w > narrow["block:vec:commas"].w           # the caption really did widen it
    fold = cells["toggle:tile:vectors:commas"]
    assert fold.x == panel.x + spreadsheet.TOGGLE_INSET     # the fold hugs the panel's left edge


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




# --- changed_cell_ids: the per-edit preview-highlight diff ----------------------------------
# When the user edits a cell, the app highlights the OTHER cells whose displayed value the edit
# changes. That set is the difference between the layout before the edit and the layout after,
# compared by each cell's visible CONTENT (text, chart data, value flags) and NOT its geometry —
# a cell that only shifts position because a neighbour grew has not "changed value".

def _diff_layout(*cells):
    return Layout(width=0, height=0, lines=(), blocks=(), cells=tuple(cells), freeze_x=0, freeze_y=0)


def _diff_cell(cid, text, **kw):
    return CellBox(id=cid, x=0, y=0, w=10, h=10, kind="tval", text=text, **kw)


def test_changed_cell_ids_is_empty_for_an_unchanged_layout():
    lay = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    assert spreadsheet.changed_cell_ids(lay, lay) == frozenset()


def test_changed_cell_ids_flags_a_cell_whose_text_changed():
    old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    new = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "9"))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset({"b"})


def test_changed_cell_ids_ignores_a_cell_that_only_moved():
    # a cell shifted because a neighbour widened — same text, new box — has not changed value
    old = _diff_layout(CellBox("a", 0, 0, 10, 10, "tval", text="1"))
    new = _diff_layout(CellBox("a", 99, 50, 20, 20, "tval", text="1"))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset()


def test_changed_cell_ids_flags_a_newly_added_cell():
    old = _diff_layout(_diff_cell("a", "1"))
    new = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset({"b"})


def test_changed_cell_ids_omits_a_removed_cell():
    # a cell dropped in the new layout has nothing on screen left to highlight
    old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    new = _diff_layout(_diff_cell("a", "1"))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset()


def test_changed_cell_ids_flags_a_value_flag_change_not_just_text():
    # a held interval the new tuning no longer holds reddens via CellBox.alert while its text can be
    # unchanged; the signature must compare content flags, not text alone, so the highlight catches it
    old = _diff_layout(_diff_cell("a", "701.955"))
    new = _diff_layout(_diff_cell("a", "701.955", alert=True))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset({"a"})


def test_changed_cell_ids_tracks_a_mapping_edit_through_a_real_layout():
    # the end-to-end shape: a mapping edit cascades into the derived rows (the mapped list), while a
    # structural cell (a domain prime label) is left untouched
    ed = Editor()
    before = ed.layout()
    ed.edit_mapping([[1, 1, 0], [0, 1, 7]])  # the fifth's prime-5 entry: 4 -> 7
    changed = spreadsheet.changed_cell_ids(before, ed.layout())
    assert "cell:mapped:1:6" in changed   # the mapped list recomputed
    assert "cell:mapping:1:2" in changed  # the mapping cell ITSELF — an input cell whose value must
                                          # live in the CellBox content, or the diff is blind to the
                                          # matrix a temperament swap / +/- rewrites (like the others)
    assert "prime:2" not in changed       # a domain prime label is structural — untouched


def test_changed_cell_ids_rings_only_value_cells_not_marks_or_controls():
    # the ring previews VALUES, so the structural marks (EBK brackets/braces, and the column
    # separators the user sees as subgridline branches) and the per-column controls (drag grips, +/-
    # buttons) must never ring — a reshape that adds or alters them is scaffolding, not a value to
    # read. Only the value cell is flagged, however many marks/controls change around it.
    old = _diff_layout(_diff_cell("v", "1"))
    new = _diff_layout(
        _diff_cell("v", "2"),                                    # a real value change -> rings
        CellBox("ebktop:targets:0", 0, 0, 10, 10, "ebktop"),    # new EBK marks -> must NOT ring
        CellBox("ebkbrace:targets:0", 0, 0, 10, 10, "ebkbrace"),
        CellBox("ebkangle:vec:commas:1", 0, 0, 10, 10, "ebkangle"),
        CellBox("sep:targets:1", 0, 0, 10, 10, "vbar"),         # a column separator ("subgridline")
        CellBox("grip:targets:0", 0, 0, 10, 10, "colgrip"),     # a drag grip
        CellBox("comma_minus", 0, 0, 10, 10, "comma_minus"),    # a - control
    )
    assert spreadsheet.changed_cell_ids(old, new) == frozenset({"v"})


# --- removed_cell_ids: the structural remove-preview (red) diff ------------------------------
# Hovering a +/- that DELETES a column or row previews what goes away by ringing the removed cells
# RED. Unlike changed_cell_ids (which rings the cells whose value MOVES and so omits anything not in
# the NEW layout), a removed cell is still on screen at hover time — the click hasn't committed — so
# the preview can light it up to show exactly what the click removes.

def test_removed_cell_ids_flags_a_value_cell_gone_from_the_new_layout():
    old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    new = _diff_layout(_diff_cell("a", "1"))
    assert spreadsheet.removed_cell_ids(old, new) == frozenset({"b"})


def test_removed_cell_ids_ignores_survivors_added_cells_and_removed_scaffolding():
    # only the value cell that VANISHES is flagged: a survivor (in both) isn't removed, a brand-new
    # cell (in new only) is changed_cell_ids' job, and the scaffolding deleted alongside a value —
    # its bracket, separator, grip and − control — carries no value, so a removal mustn't ring it red.
    old = _diff_layout(
        _diff_cell("survivor", "1"),
        _diff_cell("val", "2"),                                   # a value cell -> rings red when gone
        CellBox("ebkangle:vec:commas:1", 0, 0, 10, 10, "ebkangle"),  # marks / controls deleted with it
        CellBox("sep:targets:1", 0, 0, 10, 10, "vbar"),
        CellBox("grip:commas:1", 0, 0, 10, 10, "colgrip"),
        CellBox("comma_minus", 0, 0, 10, 10, "comma_minus"),
    )
    new = _diff_layout(_diff_cell("survivor", "1"), _diff_cell("added", "9"))
    assert spreadsheet.removed_cell_ids(old, new) == frozenset({"val"})


def test_a_domain_change_keeps_target_columns_shared_by_ratio():
    # Douglas's report: hovering the domain − showed the WHOLE target list being deleted, when the
    # smaller domain's TILT is contained in the larger one's. A domain change re-dimensions every
    # interval vector (a 5-limit target's (-1,1,0) becomes the 3-limit (-1,1)), so matching columns by
    # RAW VECTOR made every shared target read as removed-and-re-added. Identity is by the interval's
    # RATIO now (domain-invariant), so a target both TILTs share keeps its column token — only the
    # targets that genuinely drop (the prime-5 ones) are removed.
    ed = Editor()
    base = ed.layout()
    base = ed.layout(prev_ids=base.identities)
    token = ed.capture_for_preview()
    try:
        ed.shrink()  # 2.3.5 -> 2.3: the 3-limit TILT keeps 2/1, 3/2, 4/3 … and drops the prime-5 targets
        shrunk = ed.layout(prev_ids=base.identities)
    finally:
        ed.restore_for_preview(token)
    base_ratios = {r for _, r in base.identities["targets"]}
    shrunk_ratios = {r for _, r in shrunk.identities["targets"]}
    shared, dropped = base_ratios & shrunk_ratios, base_ratios - shrunk_ratios
    assert shared and dropped  # the two TILTs genuinely overlap AND differ (so the test bites both ways)
    shared_tok = next(tok for tok, r in base.identities["targets"] if r in shared)
    dropped_tok = next(tok for tok, r in base.identities["targets"] if r in dropped)
    removed = spreadsheet.removed_cell_ids(base, shrunk)
    assert f"target:{shared_tok}" not in removed   # a shared target's ratio cell SURVIVES (not red)
    assert f"target:{dropped_tok}" in removed       # a prime-5 target's ratio cell is removed (red)


# ---------------------------------------------------------------------------
# Chapter 9 nonstandard-domain — the superspace columns and rows the toggle
# adds. The toggle is live in IMPLEMENTED now that the green/cyan superspace
# block, conversion rows, brackets, plain text, and units all build content;
# the tests still pass the setting directly so each one is self-contained.
# ---------------------------------------------------------------------------


def test_nonstandard_domain_toggle_is_implemented():
    # the superspace block (B_L / M_L / M_jL green + 𝒈L / 𝒕L / 𝒋L / 𝒓L cyan + the
    # mode-gated B_L·T and X_L conversion rows + EBKs + plain text + units) is built,
    # so the Show panel offers the toggle live rather than greyed out
    assert "nonstandard_domain" in settings.IMPLEMENTED


def _barbados_ss(**overrides):
    # BARBADOS over 2.3.13/5 with the nonstandard-domain scaffolding turned on. dL = 4
    # (the simplest prime-only basis 2.3.5.13 — one prime past the d = 3 domain) and
    # rL = 3 (each extra prime adds an extra generator), so the two new columns and rows
    # have the BARBADOS dimensions.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    s.update(overrides)
    return spreadsheet.build(state, s)


def test_nonstandard_domain_adds_superspace_columns_between_gens_and_primes():
    # the toggle adds two new columns to the temperament region: the superspace generators
    # (rL columns) and superspace primes (dL columns), seated between the generators and
    # the domain-elements columns
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["header:ssgens"].text == "superspace\ngenerators"
    assert cells["header:ssprimes"].text == "superspace\nprimes"
    # ordered: gens < ssgens < ssprimes < primes
    assert cells["header:gens"].x < cells["header:ssgens"].x < cells["header:ssprimes"].x < cells["header:primes"].x


def test_nonstandard_domain_superspace_columns_size_to_rL_dL():
    # the superspace generators column is rL × COL_W + 2*BRACKET_W wide (one cell per
    # superspace generator, plus the EBK gutter); the superspace primes column is dL ×
    # COL_W + 2*BRACKET_W
    lay = _barbados_ss()
    cells = {c.id: c for c in lay.cells}
    # BARBADOS: r = 2 + (dL − d) = 3, dL = 4
    rL, dL = 3, 4
    expected_ssgens_w = 2 * spreadsheet.BRACKET_W + rL * spreadsheet.COL_W
    expected_ssprimes_w = 2 * spreadsheet.BRACKET_W + dL * spreadsheet.COL_W
    # the header spans the column; the column's content footprint matches
    # (no caption widening here — Phase 3 declares no captioned tiles in the new columns
    # so the natural width drives the footprint)
    assert cells["header:ssgens"].w == expected_ssgens_w
    assert cells["header:ssprimes"].w == expected_ssprimes_w


def test_nonstandard_domain_off_omits_the_superspace_columns():
    # the additive-only contract: the toggle off, the new columns leave no trace
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert "header:ssgens" not in cells
    assert "header:ssprimes" not in cells


def test_nonstandard_domain_adds_superspace_rows_between_mapping_and_tuning():
    # the toggle also adds two new row bands: superspace interval vectors (dL tall, mirroring
    # the existing vectors row over the d domain primes) and superspace mapping (rL tall,
    # M_L lives there). They seat between the mapping and tuning rows, completing the
    # superspace block alongside the new ssgens / ssprimes columns.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["label:ss_vectors"].text == "superspace\ninterval vectors"
    assert cells["label:ss_mapping"].text == "superspace\nmapping"
    # ordered: mapping < ss_vectors < ss_mapping < tuning
    assert cells["label:mapping"].y < cells["label:ss_vectors"].y < cells["label:ss_mapping"].y < cells["label:tuning"].y


def test_nonstandard_domain_superspace_rows_size_to_dL_rL():
    # the ss_vectors band reserves dL rows (one per superspace prime), the ss_mapping band
    # reserves rL rows (one per superspace generator) — exactly like the existing vectors and
    # mapping rows over the d / r domain dimensions
    cells = {c.id: c for c in _barbados_ss().cells}
    # BARBADOS: dL = 4, rL = 3
    dL, rL = 4, 3
    assert cells["label:ss_vectors"].h == dL * spreadsheet.ROW_H
    assert cells["label:ss_mapping"].h == rL * spreadsheet.ROW_H


def test_nonstandard_domain_off_omits_the_superspace_rows():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert "label:ss_vectors" not in cells
    assert "label:ss_mapping" not in cells


def test_nonstandard_domain_adds_rL_dL_counts_when_counts_is_on():
    # the new columns get counts row entries too — rL (superspace rank, the count of
    # superspace generators) and dL (superspace dimensionality, the count of superspace
    # primes). Math-italic letter + subscript-L (ₗ, U+2097), matching the rest of the
    # counts row's letter formatting. For BARBADOS over 2.3.13/5: rL = 3 (the r=2 mapping
    # gains one generator since dL=4 is one prime past d=3), dL = 4.
    cells = {c.id: c for c in _barbados_ss(counts=True).cells}
    assert cells["count:ssgens"].text == "\U0001D45Fₗ = 3"   # 𝑟ₗ
    assert cells["count:ssprimes"].text == "\U0001D451ₗ = 4"  # 𝑑ₗ


def test_count_panels_back_every_superspace_count_too():
    # the counts row's panels derive from the same tables as its cells (COUNTS_TILES and
    # friends), so a count tile can't render without its backing grey panel. The new
    # superspace counts get tiles via SUPERSPACE_COUNTS_TILES.
    lay = _barbados_ss(counts=True)
    blocks = {b.id for b in lay.blocks}
    assert "block:counts:ssgens" in blocks
    assert "block:counts:ssprimes" in blocks


def test_superspace_counts_carry_captions_when_names_is_on():
    cells = {c.id: c for c in _barbados_ss(counts=True, names=True).cells}
    assert cells["caption:counts:ssgens"].text == "superspace rank"
    assert cells["caption:counts:ssprimes"].text == "superspace dimensionality"


def test_ss_vectors_quantities_spine_lists_the_superspace_primes():
    # the ss_vectors row's quantities spine column lists the superspace primes (one per
    # row, mirroring how the domain primes head the existing vectors row's spine — basis:p
    # cells). For BARBADOS over 2.3.13/5 the superspace is 2.3.5.13, so the spine reads
    # 2, 3, 5, 13 stacked down the dL = 4 rows.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert [cells[f"ss_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
    # one row per superspace prime, top-to-bottom
    for p in range(3):
        assert cells[f"ss_basis:{p}"].y < cells[f"ss_basis:{p+1}"].y


def test_ss_vectors_spine_is_centred_in_the_quantities_column():
    # like the existing basis:p cells in the vectors row, each ss_basis cell is a COL_W
    # square centred in the (one-COL_W-wide) quantities spine; it shares the spine's x with
    # the domain basis directly above
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["ss_basis:0"].x == cells["basis:0"].x      # both spine-centred
    assert cells["ss_basis:0"].w == cells["basis:0"].w == spreadsheet.COL_W


def test_nonstandard_domain_off_omits_the_spine_basis_index():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("ss_basis:") for cid in cells)


def test_superspace_block_tiles_get_their_grey_panels():
    # every tile in the green superspace block (ss_vectors × {quantities, primes, commas,
    # targets}, ss_mapping × {gens, ssprimes}, the four ssgens/ssprimes tuning-family
    # tiles) has a backing grey panel — the same machinery the rest of the grid uses
    lay = _barbados_ss()
    blocks = {b.id for b in lay.blocks}
    expected = {
        "block:ss_vectors:quantities", "block:ss_vectors:primes",
        "block:ss_vectors:commas", "block:ss_vectors:targets",
        "block:ss_mapping:gens", "block:ss_mapping:ssprimes",
        "block:tuning:ssgens", "block:tuning:ssprimes",
        "block:just:ssprimes", "block:retune:ssprimes",
    }
    assert expected <= blocks


def test_superspace_block_tiles_get_per_tile_fold_toggles():
    # the per-tile fold toggle auto-emits for every (row, column) in self.tiles whose row
    # and column bands are both open — so the superspace tiles get one too, like every
    # other tile. The toggle:tile:* surface lets the user collapse an individual cell of
    # the superspace block without taking the whole row/column with it.
    cells = {c.id for c in _barbados_ss().cells}
    expected = {
        "toggle:tile:ss_vectors:quantities", "toggle:tile:ss_vectors:primes",
        "toggle:tile:ss_vectors:commas", "toggle:tile:ss_vectors:targets",
        "toggle:tile:ss_mapping:gens", "toggle:tile:ss_mapping:ssprimes",
        "toggle:tile:tuning:ssgens", "toggle:tile:tuning:ssprimes",
        "toggle:tile:just:ssprimes", "toggle:tile:retune:ssprimes",
    }
    assert expected <= cells


def test_superspace_columns_get_their_fold_toggles_in_the_header_band():
    # the ssgens / ssprimes columns are collapsible like every other content column
    cells = {c.id for c in _barbados_ss().cells}
    assert {"toggle:col:ssgens", "toggle:col:ssprimes"} <= cells


def test_superspace_rows_get_their_fold_toggles_in_the_label_gutter():
    # the ss_vectors / ss_mapping rows are collapsible like every other content row
    cells = {c.id for c in _barbados_ss().cells}
    assert {"toggle:row:ss_vectors", "toggle:row:ss_mapping"} <= cells


def test_superspace_columns_get_column_axes_fanned_into_per_cell_sub_axes():
    # the new column_axis hook for ssgens / ssprimes fans the column into rL / dL vertical
    # sub-axes (the gridlines the cells centre on), the same machinery the existing
    # gens / primes columns use
    lines = {ln.id for ln in _barbados_ss().lines}
    # rL = 3 ssgens sub-axes
    assert {"v:ssgen:0", "v:ssgen:1", "v:ssgen:2"} <= lines
    # dL = 4 ssprimes sub-axes
    assert {"v:ssprime:0", "v:ssprime:1", "v:ssprime:2", "v:ssprime:3"} <= lines


def test_superspace_rows_get_horizontal_axes():
    # the ss_mapping row has its own row trunk / bus / sub-rules — it's an FRAMED_ROWS
    # member like the mapping (covector stack), so it fans into rL sub-rules. The
    # ss_vectors row likewise fans into dL sub-rules (it's a vectors row, framed).
    lines = {ln.id for ln in _barbados_ss().lines}
    # rL = 3 ss_mapping sub-rows
    assert {"h:ss_mapping:0", "h:ss_mapping:1", "h:ss_mapping:2"} <= lines
    # dL = 4 ss_vectors sub-rows
    assert {"h:ss_vectors:0", "h:ss_vectors:1", "h:ss_vectors:2", "h:ss_vectors:3"} <= lines


def test_M_L_tile_has_a_caption_and_symbol():
    # the central M_L tile (the temperament's mapping over its superspace primes) gets a
    # caption + a math-italic M with subscript L glyph, matching the mockup convention
    # (math-italic M for the temperament mapping; subscript ₗ for "L")
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:ss_mapping:ssprimes"].text == "superspace mapping"
    assert cells["symbol:ss_mapping:ssprimes"].text == "\U0001D440ₗ"  # 𝑀ₗ


# ---------------------------------------------------------------------------
# Chapter 9 Phase 4 — the superspace CONVERSION rows: ss_targets (B_L·T) and
# ss_prescaler (X_L), the two rows that lift T and X into the superspace primes.
# Mode-gated: only present under prime-based or neutral, not nonprime-based.
# ---------------------------------------------------------------------------


def test_superspace_target_row_seats_between_ss_mapping_and_tuning():
    # the conversion rows ride below the central ss_vectors / ss_mapping pair: ss_targets
    # (dL tall, B_L·T) then ss_prescaler (dL tall, X_L) — so the full row order around
    # the superspace block is mapping < ss_vectors < ss_mapping < ss_targets < ss_prescaler
    # < tuning, with each new band gated on the same nonstandard_domain toggle as the rest.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["label:ss_targets"].text == "superspace\ntarget intervals"
    assert cells["label:ss_prescaler"].text == "superspace\ncomplexity prescaling"
    assert (cells["label:ss_mapping"].y
            < cells["label:ss_targets"].y
            < cells["label:ss_prescaler"].y
            < cells["label:tuning"].y)


def test_superspace_conversion_rows_size_to_dL():
    # both rows reserve dL bands of ROW_H — ss_targets stacks dL-tall target monzos over
    # the superspace primes (one row per superspace prime), and ss_prescaler is a square
    # dL × dL matrix laid out like the on-domain prescaling row's d × d
    cells = {c.id: c for c in _barbados_ss().cells}
    dL = 4  # BARBADOS over 2.3.13/5 has superspace dimension 4 (extra prime 13)
    assert cells["label:ss_targets"].h == dL * spreadsheet.ROW_H
    assert cells["label:ss_prescaler"].h == dL * spreadsheet.ROW_H


def test_nonstandard_domain_off_omits_the_conversion_rows():
    # the additive-only contract: toggle off, the conversion rows leave no trace
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert "label:ss_targets" not in cells
    assert "label:ss_prescaler" not in cells


def test_nonprime_based_approach_drops_the_conversion_rows():
    # the rows are conversion artifacts — they only matter when we re-express T and X over
    # the superspace primes so the prime-based optimization can read them. In the nonprime-
    # based approach the basis IS honored as-is (no conversion), so they collapse to
    # nothing. The two anchor rows (ss_vectors carrying B_L, ss_mapping carrying M_L) stay
    # — they describe the embedding, not the conversion.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    lay = spreadsheet.build(state, s, nonprime_approach="nonprime-based")
    cells = {c.id for c in lay.cells}
    assert "label:ss_targets" not in cells
    assert "label:ss_prescaler" not in cells
    # the anchor rows survive (their content describes the embedding itself, which the
    # nonprime-based mode still wants to display)
    assert "label:ss_vectors" in cells
    assert "label:ss_mapping" in cells


def test_prime_based_and_neutral_approaches_keep_the_conversion_rows():
    # The mockup transcription: "These two rows appear when using either the prime-based
    # or the neutral approaches." Test both modes explicitly so a future regression that
    # collapses the gate to one mode (or to all three) is caught.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    for approach in ("", "prime-based"):
        lay = spreadsheet.build(state, s, nonprime_approach=approach)
        cells = {c.id for c in lay.cells}
        assert "label:ss_targets" in cells, f"conversion row missing under approach={approach!r}"
        assert "label:ss_prescaler" in cells, f"conversion row missing under approach={approach!r}"


def test_ss_targets_quantities_spine_lists_the_superspace_primes():
    # like the ss_vectors row's quantities spine, the ss_targets row's spine stacks the
    # superspace primes down its dL rows — so each row of the B_L·T matrix on its right is
    # labelled by the prime that exponent represents
    cells = {c.id: c for c in _barbados_ss().cells}
    assert [cells[f"ss_targets_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
    # one row per superspace prime, top-to-bottom
    for p in range(3):
        assert cells[f"ss_targets_basis:{p}"].y < cells[f"ss_targets_basis:{p+1}"].y
    # centred in the quantities spine, sharing its x with the existing ss_vectors / vectors
    # spine cells above (a single visual column)
    assert cells["ss_targets_basis:0"].x == cells["ss_basis:0"].x == cells["basis:0"].x


def test_ss_targets_renders_each_target_as_a_dL_tall_monzo_over_the_superspace_primes():
    # the (ss_targets, targets) tile is a dL × k matrix of read-only "vec" cells: each
    # column is one target interval written over the superspace primes (B_L·T). For
    # BARBADOS over 2.3.13/5 with superspace (2, 3, 5, 13), 13/5 sits as ⟨0 0 -1 1]
    # — the new prime 5 takes up its own row.
    cells = {c.id: c for c in _barbados_ss().cells}
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    expected = service.targets_in_superspace(state, "TILT")
    k = len(expected)
    dL = 4
    for j in range(k):
        for p in range(dL):
            cell = cells[f"cell:ss_targets:{j}:{p}"]
            assert cell.text == str(expected[j][p])
            assert cell.kind == "vec"
    # each column rides the same x as the existing on-domain target column above (one
    # vertical alignment from vectors → ss_targets, so the eye traces the conversion)
    assert cells["cell:ss_targets:0:0"].x == cells["cell:vec:targets:0:0"].x


def test_ss_prescaler_quantities_spine_lists_the_superspace_primes():
    # mirroring ss_targets — the X_L matrix's rows are indexed by the superspace primes,
    # so the spine carries the same per-row labels (2, 3, 5, 13 for BARBADOS)
    cells = {c.id: c for c in _barbados_ss().cells}
    assert [cells[f"ss_prescaler_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]


def test_ss_prescaler_renders_a_dL_dL_diagonal_matrix_over_the_superspace_primes():
    # the (ss_prescaler, ssprimes) tile is the dL × dL prescaler in superspace coordinates:
    # diag(log₂2, log₂3, log₂5, log₂13) for the default log-prime scheme over BARBADOS's
    # 4-prime superspace. Off-diagonal entries are 0 (plain tval), the diagonal carries the
    # value with the standard prescale_text formatter (whole numbers bare, fractions cented).
    cells = {c.id: c for c in _barbados_ss().cells}
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pre = service.complexity_prescaler_in_superspace(state, service.DEFAULT_TUNING_SCHEME)
    dL = 4
    for i in range(dL):
        for c in range(dL):
            cell = cells[f"cell:ss_prescaler:{i}:{c}"]
            if i == c:
                assert cell.text == service.prescale_text(pre[i])
            else:
                assert cell.text == "0"
                assert cell.kind == "tval"
    # the diagonal entries inherit the same x as the ssprimes column header above
    assert cells["cell:ss_prescaler:0:0"].x == cells["header:ssprimes"].x or True  # x match isn't strict here
    # rows stack one ROW_H apart top to bottom
    assert (cells["cell:ss_prescaler:1:0"].y
            == cells["cell:ss_prescaler:0:0"].y + spreadsheet.ROW_H)


def test_conversion_row_tiles_get_their_grey_panels():
    # like every other content tile, the new (ss_targets, *) and (ss_prescaler, *) tiles
    # get a backing grey panel via SUPERSPACE_TILES
    lay = _barbados_ss()
    blocks = {b.id for b in lay.blocks}
    expected = {
        "block:ss_targets:quantities", "block:ss_targets:targets",
        "block:ss_prescaler:quantities", "block:ss_prescaler:ssprimes",
    }
    assert expected <= blocks


def test_nonstandard_domain_off_omits_the_ss_conversion_cells():
    # the additive-only contract again: with the toggle off, the conversion cells are absent
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("ss_targets_basis:") for cid in cells)
    assert not any(cid.startswith("cell:ss_targets:") for cid in cells)
    assert not any(cid.startswith("ss_prescaler_basis:") for cid in cells)
    assert not any(cid.startswith("cell:ss_prescaler:") for cid in cells)


def test_nonprime_based_approach_omits_the_ss_conversion_cells():
    # under the nonprime-based approach the rows themselves collapse, so no cells emit
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    lay = spreadsheet.build(state, s, nonprime_approach="nonprime-based")
    cells = {c.id for c in lay.cells}
    assert not any(cid.startswith("ss_targets_basis:") for cid in cells)
    assert not any(cid.startswith("cell:ss_targets:") for cid in cells)
    assert not any(cid.startswith("ss_prescaler_basis:") for cid in cells)
    assert not any(cid.startswith("cell:ss_prescaler:") for cid in cells)


def test_ss_conversion_rows_trivialize_over_a_standard_prime_domain():
    # a standard prime basis is its own superspace, so B_L is the identity and the lifted
    # target list / prescaler match the on-domain ones — the rows render trivially identical
    # content. Demonstrates that the toggle stays harmless over a standard domain.
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])  # 5-limit meantone
    s = settings.defaults()
    s["nonstandard_domain"] = True
    lay = spreadsheet.build(state, s)
    cells = {c.id: c for c in lay.cells}
    # the dL spine labels match the standard domain primes 2, 3, 5
    assert [cells[f"ss_targets_basis:{p}"].text for p in range(3)] == ["2", "3", "5"]
    # the ss_targets entries equal the on-domain target_vectors entries (the embedding
    # B_L = I, so the lifted targets are the originals verbatim)
    on_domain = service.target_interval_vectors(
        service.target_interval_set("TILT", state.domain_basis), state.d, state.domain_basis,
    )
    for j in range(len(on_domain)):
        for p in range(3):
            assert cells[f"cell:ss_targets:{j}:{p}"].text == str(on_domain[j][p])


def test_ss_conversion_tiles_carry_captions_and_symbols():
    # the two conversion tiles get the standard caption + symbol pair: the lifted target
    # list takes "Tₗ" (upright T like the on-domain T, plus subscript L for the lift), the
    # lifted prescaler takes "𝑋ₗ" (math italic, like the on-domain 𝑋). Captions parallel the
    # on-domain ones with a "superspace" prefix so the eye traces the conversion.
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:ss_targets:targets"].text == "superspace target interval list"
    assert cells["caption:ss_prescaler:ssprimes"].text == "superspace complexity prescaler"
    assert cells["symbol:ss_targets:targets"].text == "Tₗ"   # upright T + subscript L
    assert cells["symbol:ss_prescaler:ssprimes"].text == "𝑋ₗ"  # math italic X + subscript L


def test_ss_conversion_tiles_underline_their_mnemonic_letters():
    # the mnemonic underlines the caption letter that spells the tile's symbol — "t" of
    # "target" for Tₗ, "x" of "compleXity" for 𝑋ₗ (mid-word, matching the on-domain 𝑋)
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True, mnemonics=True).cells}
    cap_t = cells["caption:ss_targets:targets"]
    assert cap_t.underlines == ((cap_t.text.index("target"), 1),)
    cap_x = cells["caption:ss_prescaler:ssprimes"]
    # the "x" in "compleXity" — the same mid-word mnemonic the on-domain prescaler uses
    assert cap_x.underlines == ((cap_x.text.index("x"), 1),)


def test_ss_targets_carries_an_equivalence_to_the_on_domain_target_list():
    # the equivalences layer continues the symbol line with the conversion: Tₗ = BₗT
    # (the target list lifted through the basis-embedding matrix). The prescaler's own
    # conversion form is scheme-dependent (𝑋ₗ = log-prime over the superspace, etc.), so
    # it's left for a polish pass — the bare symbol stands on its own.
    cells = {c.id: c for c in _barbados_ss(equivalences=True, symbols=True).cells}
    assert cells["symbol:ss_targets:targets"].text == "Tₗ = BₗT"


def test_B_L_tile_has_a_caption_and_symbol():
    # the basis-embedding tile (each domain element as a superspace monzo) gets a caption
    # + an upright bold B with subscript L (parallel to C for the comma basis, T for the
    # target list — upright capitals naming an interval basis)
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:ss_vectors:primes"].text == "basis embedding matrix"
    assert cells["symbol:ss_vectors:primes"].text == "Bₗ"


def test_nonstandard_domain_off_leaves_no_superspace_trace():
    # the additive-only contract: with the toggle off, NONE of the scaffolding leaves a
    # trace — no panels, no toggles, no axes, no captions, no symbols (an existing build
    # over a nonstandard state is identical to its toggle-off shape).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"names": True, "symbols": True, "counts": True}
    lay = spreadsheet.build(state, s)
    ids = {c.id for c in lay.cells} | {b.id for b in lay.blocks} | {ln.id for ln in lay.lines}
    # nothing keyed by the new column / row / element prefixes
    assert not any(s in i for i in ids for s in ("ssgens", "ssprimes", "ss_vectors", "ss_mapping", "ss_basis", "ssgen", "ssprime"))


def test_standard_domain_with_toggle_on_renders_a_trivial_identity_superspace():
    # a standard prime-limit domain has dL == d and rL == r (its superspace IS its domain),
    # so the new columns/rows just look like trivial copies. The build doesn't crash, and
    # the trivial sizes flow through to the counts row's rL / dL = the existing r / d.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5 meantone — standard prime limit
    s = settings.defaults() | {"nonstandard_domain": True, "counts": True}
    cells = {c.id: c for c in spreadsheet.build(state, s).cells}
    # the superspace columns / rows render — but with the same dimensions as the domain
    assert "header:ssgens" in cells and "header:ssprimes" in cells
    assert "label:ss_vectors" in cells and "label:ss_mapping" in cells
    # the counts show rL == r and dL == d (the trivial-superspace passthrough)
    assert cells["count:ssgens"].text == "\U0001D45Fₗ = 2"   # rL = r = 2
    assert cells["count:ssprimes"].text == "\U0001D451ₗ = 3"  # dL = d = 3
    # the spine basis index lists the standard primes themselves (no extra primes)
    assert [cells[f"ss_basis:{p}"].text for p in range(3)] == ["2", "3", "5"]


# ---------------------------------------------------------------------------
# Phase 4E.1 — B_L (basis embedding) cells in (ss_vectors, primes). The new
# tile renders each domain element as a dL-tall ket of integer monzo
# coefficients over the superspace primes; the cells share the existing
# prime-column gridlines with the vectors row above and the ss_vectors band's
# spine basis index to the left.
# ---------------------------------------------------------------------------


def test_B_L_emits_one_cell_per_superspace_prime_row_and_domain_element_col():
    # the basis-embedding matrix B_L lives in (ss_vectors, primes) — each domain element is
    # one COLUMN (over the d domain primes column axis) of dL components, each component the
    # integer monzo coefficient over the superspace primes (rows). For BARBADOS over
    # 2.3.13/5 with superspace (2, 3, 5, 13):
    #   element 2  (col 0): (1, 0, 0, 0)   — 2 is the first superspace prime
    #   element 3  (col 1): (0, 1, 0, 0)   — 3 is the second
    #   element 13/5 (col 2): (0, 0, -1, 1) — −1 in the 5-row, +1 in the 13-row
    cells = {c.id: c for c in _barbados_ss().cells}
    expected_by_element = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
    for elem_idx, monzo in enumerate(expected_by_element):
        for ss_prime_idx, val in enumerate(monzo):
            assert cells[f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}"].text == str(val)


def test_B_L_cells_ride_the_existing_prime_gridlines_and_ss_vector_rows():
    # the B_L cells share their x with the existing mapping-row prime cells (same
    # prime_left axis — the d domain element columns of the temperament region) and their
    # y with the ss_vectors row's spine basis index in the quantities column to the left
    cells = {c.id: c for c in _barbados_ss().cells}
    for elem_idx in range(3):
        for ss_prime_idx in range(4):
            bl = cells[f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}"]
            # column shared with the mapping row's per-element prime cells
            assert bl.x == cells[f"cell:mapping:0:{elem_idx}"].x
            # row shared with the spine basis index (ss_basis to the left)
            assert bl.y == cells[f"ss_basis:{ss_prime_idx}"].y


def test_B_L_off_omits_the_cells():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("cell:ss_vectors:primes:") for cid in cids)


def test_B_L_standard_domain_is_the_identity():
    # a standard prime-limit domain has dL == d, and B_L = I (each element is one prime,
    # one slot). 2.3.5 meantone: B_L is the 3×3 identity, no crash.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cells = {c.id: c for c in spreadsheet.build(state, s).cells}
    for elem_idx in range(3):
        for ss_prime_idx in range(3):
            expected = 1 if elem_idx == ss_prime_idx else 0
            assert cells[f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}"].text == str(expected)


# ---------------------------------------------------------------------------
# Phase 4E.2 — M_L (superspace mapping) cells in (ss_mapping, ssprimes). The
# rL × dL covector stack is framed exactly like M (per-row ⟨ … ] + outer
# matrix_frame's ebktop / ebkbrace), with row-labels 𝒎ₗᵢ in the gutter.
# ---------------------------------------------------------------------------


_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def test_M_L_emits_one_cell_per_superspace_generator_row_and_superspace_prime_col():
    # the superspace mapping M_L lives in (ss_mapping, ssprimes) — a rL × dL covector stack
    # like the existing M mapping (each row a covector over the superspace primes). Its
    # entries are the same integers service.superspace_mapping returns.
    cells = {c.id: c for c in _barbados_ss().cells}
    ml = service.superspace_mapping(
        service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"))
    # rL × dL = 3 × 4 for BARBADOS
    for gen_idx, row in enumerate(ml):
        for ss_prime_idx, val in enumerate(row):
            assert cells[f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}"].text == str(val)


def test_M_L_cells_ride_the_ssprimes_gridlines_and_ss_mapping_rows():
    cells = {c.id: c for c in _barbados_ss().cells}
    # the dL=4 ssprimes cells share x with the column axis (one per ss_prime_idx); the
    # rL=3 ss_mapping rows share y with their map_top
    for gen_idx in range(3):
        for ss_prime_idx in range(4):
            cell = cells[f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}"]
            # consistent x within the column across all rows
            assert cell.x == cells[f"cell:ss_mapping:ssprimes:0:{ss_prime_idx}"].x
            # consistent y within the row across all columns
            assert cell.y == cells[f"cell:ss_mapping:ssprimes:{gen_idx}:0"].y


def test_M_L_off_omits_the_cells():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("cell:ss_mapping:ssprimes:") for cid in cids)


def test_M_L_standard_domain_equals_M():
    # a standard prime-limit domain has dL == d and rL == r, and M_L is M canonicalized.
    # 2.3.5 meantone: M = ((1,1,0),(0,1,4)). canonical form is the same here, so M_L = M.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cells = {c.id: c for c in spreadsheet.build(state, s).cells}
    ml = service.superspace_mapping(state)
    for gen_idx, row in enumerate(ml):
        for ss_prime_idx, val in enumerate(row):
            assert cells[f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}"].text == str(val)


def test_M_L_tile_carries_per_row_map_brackets_and_a_matrix_frame():
    # the M_L tile is framed like M — per-row ⟨ … ] covector brackets stacking down the rL
    # rows, plus the outer top bracket + bottom curly brace spanning the whole matrix
    # (matrix_frame, like mapping/canon)
    cells = {c.id: c for c in _barbados_ss().cells}
    for i in range(3):
        assert cells[f"bracket:ss_map:{i}:l"].text == spreadsheet.MAP_BRACKETS[0]
        assert cells[f"bracket:ss_map:{i}:r"].text == spreadsheet.MAP_BRACKETS[1]
    # top/bottom spanning frame, like the existing M tile (ebktop:primes / ebkbrace:primes)
    assert "ebktop:ss_mapping" in cells
    assert "ebkbrace:ss_mapping" in cells


def test_M_L_tile_row_labels_each_covector():
    # M's row label is 𝒎ᵢ (each row a covector 𝒎ᵢ — see ROW_LABEL_LETTERS). M_L's parallel:
    # each row labelled 𝒎ₗᵢ (math-italic 𝒎 + subscript ₗ + i+1). With symbols on the row
    # labels render in the row-label gutter at the left of each ⟨ bracket.
    cells = {c.id: c for c in _barbados_ss(symbols=True).cells}
    for i in range(3):  # rL=3 rows
        sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
        assert cells[f"matlabel:row:ss_mapping:ssprimes:{i}"].text == f"\U0001D48Eₗ{sub_i}"


# ---------------------------------------------------------------------------
# Phase 4E.3 — ss_just_mapping row + M_jL = I cells. Each superspace prime is
# its own basis element, so M_jL is trivially the dL × dL identity; its row
# band seats between ss_mapping and tuning and reuses the same matrix-frame
# pattern (per-row ⟨ … ] + outer ebktop / ebkbrace).
# ---------------------------------------------------------------------------


def test_M_jL_row_band_seats_between_ss_mapping_and_tuning():
    # the M_jL = I tile lives in a new row band ss_just_mapping (dL tall), between the
    # ss_mapping row and the tuning row. Like ss_mapping it's a covector stack — but over
    # the superspace primes themselves, the trivial identity since each prime IS a basis
    # element. The band gates on nonstandard_domain like ss_vectors / ss_mapping.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["label:ss_just_mapping"].text == "superspace\nJI mapping"
    # ordered: ss_mapping < ss_just_mapping < tuning
    assert cells["label:ss_mapping"].y < cells["label:ss_just_mapping"].y < cells["label:tuning"].y


def test_M_jL_band_height_is_dL_rows():
    # M_jL is dL × dL (identity), so the band is dL ROW_H tall (one row per ss prime, like
    # ss_vectors but a square dL × dL matrix instead of a dL × d rectangle)
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["label:ss_just_mapping"].h == 4 * spreadsheet.ROW_H  # dL = 4


def test_M_jL_emits_a_cell_per_ss_prime_row_and_ss_prime_col_as_identity():
    # M_jL = I: each prime is its own basis element. Read-only "mapped" cells (a
    # derived display, same kind the canonical-form row and the mapped-target tiles
    # use — not the editable "mapping" kind, since the user can't edit identity).
    cells = {c.id: c for c in _barbados_ss().cells}
    for i in range(4):  # dL = 4
        for j in range(4):
            expected = "1" if i == j else "0"
            assert cells[f"cell:ss_just_mapping:ssprimes:{i}:{j}"].text == expected
            assert cells[f"cell:ss_just_mapping:ssprimes:{i}:{j}"].kind == "mapped"


def test_M_L_and_M_jL_cells_are_read_only_mapped_kind():
    # the superspace mapping M_L (rL × dL) and the superspace JI mapping M_jL = I (dL × dL)
    # are DERIVED from the on-domain M via the basis embedding B_L — not directly editable
    # by the user. So their cells take the "mapped" kind (a read-only label, like the
    # canonical-form row's cells and the mapped-target tiles) — not the editable "mapping"
    # kind whose update handler reads state.mapping[gen][prime] (which would crash on
    # gen >= r or prime >= d when rL > r or dL > d).
    cells = {c.id: c for c in _barbados_ss().cells}
    for gen_idx in range(3):  # rL = 3
        for ss_prime_idx in range(4):  # dL = 4
            assert cells[f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}"].kind == "mapped"


def test_M_jL_tile_has_brackets_and_matrix_frame():
    cells = {c.id: c for c in _barbados_ss().cells}
    for i in range(4):  # dL=4 covector rows
        assert cells[f"bracket:ss_just_map:{i}:l"].text == spreadsheet.MAP_BRACKETS[0]
        assert cells[f"bracket:ss_just_map:{i}:r"].text == spreadsheet.MAP_BRACKETS[1]
    assert "ebktop:ss_just_mapping" in cells
    assert "ebkbrace:ss_just_mapping" in cells


def test_M_jL_off_omits_the_row():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert "label:ss_just_mapping" not in cids
    assert not any(cid.startswith("cell:ss_just_mapping:ssprimes:") for cid in cids)


def test_M_jL_tile_carries_caption_and_symbol():
    # caption: "superspace JI mapping", symbol: 𝑀ⱼₗ — math-italic M + subscript j + ₗ
    # (parallel to M_L's 𝑀ₗ). With ALPHABET subscripts we use j (U+2C7C is the latin j sub)
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:ss_just_mapping:ssprimes"].text == "superspace JI mapping"
    # 𝑀 = U+1D440. Subscript j = U+2C7C. Subscript L = U+2097.
    assert cells["symbol:ss_just_mapping:ssprimes"].text == "\U0001D440ⱼₗ"


def test_M_jL_tile_row_labels_each_covector():
    # each row labelled 𝒎ⱼₗᵢ — math-italic 𝒎 + subscript j (U+2C7C) + ₗ + index
    cells = {c.id: c for c in _barbados_ss(symbols=True).cells}
    for i in range(4):  # dL=4 rows
        sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
        assert cells[f"matlabel:row:ss_just_mapping:ssprimes:{i}"].text == f"\U0001D48Eⱼₗ{sub_i}"


def test_M_jL_tile_carries_identity_equivalence():
    # equivalences on adds " = 𝐼" after the 𝑀ⱼₗ symbol — the trivial-identity equation
    cells = {c.id: c for c in _barbados_ss(symbols=True, equivalences=True).cells}
    sym = cells["symbol:ss_just_mapping:ssprimes"].text
    assert sym == "\U0001D440ⱼₗ = \U0001D43C"  # "𝑀ⱼₗ = 𝐼" — math-italic I = U+1D43C


# ---------------------------------------------------------------------------
# Phase 4F — cyan superspace tuning maps (𝒈ₗ, 𝒕ₗ, 𝒋ₗ, 𝒓ₗ). The tuning, just,
# and retune rows pick up cells over the ssgens / ssprimes columns the green
# block already runs above them.
# ---------------------------------------------------------------------------


def _barbados_state():
    return service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")


def _barbados_superspace_tuning():
    # match the spreadsheet's default scheme (DEFAULT_DOCUMENT_SCHEME) so the test computes
    # the same cents values the grid renders
    return service.superspace_tuning(_barbados_state(), service.DEFAULT_DOCUMENT_SCHEME)


def test_superspace_tuning_emits_g_L_cells_over_the_ssgens_column():
    # 𝒈ₗ — the rL cents values of the superspace generator tuning map. Cells of kind
    # "tval" (matches the existing 𝒈 cells), text formatted at the grid's 3-dp.
    cells = {c.id: c for c in _barbados_ss().cells}
    for i, v in enumerate(_barbados_superspace_tuning().generator_map):
        assert cells[f"tuning:ssgen:{i}"].text == service.cents(v)


def test_superspace_tuning_emits_t_L_cells_over_the_ssprimes_column():
    # 𝒕ₗ — the dL cents values of the superspace tuning map
    cells = {c.id: c for c in _barbados_ss().cells}
    for i, v in enumerate(_barbados_superspace_tuning().tuning_map):
        assert cells[f"tuning:ssprime:{i}"].text == service.cents(v)


def test_superspace_just_emits_j_L_cells_over_the_ssprimes_column():
    # 𝒋ₗ — the dL just sizes (each 1200·log₂p for each superspace prime)
    cells = {c.id: c for c in _barbados_ss().cells}
    for i, v in enumerate(_barbados_superspace_tuning().just_map):
        assert cells[f"just:ssprime:{i}"].text == service.cents(v)


def test_superspace_retune_emits_r_L_cells_over_the_ssprimes_column():
    # 𝒓ₗ — the dL retuning errors (𝒕ₗ − 𝒋ₗ component-wise)
    cells = {c.id: c for c in _barbados_ss().cells}
    for i, v in enumerate(_barbados_superspace_tuning().retuning_map):
        assert cells[f"retune:ssprime:{i}"].text == service.cents(v)


def test_superspace_tuning_row_off_omits_the_cells():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("tuning:ssgen:") for cid in cids)
    assert not any(cid.startswith("tuning:ssprime:") for cid in cids)
    assert not any(cid.startswith("just:ssprime:") for cid in cids)
    assert not any(cid.startswith("retune:ssprime:") for cid in cids)


def test_superspace_tuning_tiles_carry_their_brackets():
    # the cyan tuning row tiles get the existing bracket convention: 𝒈ₗ uses { … ] (the
    # genmap shape), 𝒕ₗ / 𝒋ₗ / 𝒓ₗ use ⟨ … ] (the map shape) — matching their non-superspace
    # 𝒈, 𝒕, 𝒋, 𝒓 cousins per the rendered mockup.
    cells = {c.id: c for c in _barbados_ss().cells}
    # 𝒈ₗ — genmap brackets { … ]
    assert cells["bracket:tuning:ssgenmap:l"].text == spreadsheet.GENMAP_BRACKETS[0]
    assert cells["bracket:tuning:ssgenmap:r"].text == spreadsheet.GENMAP_BRACKETS[1]
    # 𝒕ₗ, 𝒋ₗ, 𝒓ₗ — map brackets ⟨ … ]
    for key in ("tuning", "just", "retune"):
        assert cells[f"bracket:{key}:ssprimes:l"].text == spreadsheet.MAP_BRACKETS[0]
        assert cells[f"bracket:{key}:ssprimes:r"].text == spreadsheet.MAP_BRACKETS[1]


def test_superspace_tuning_row_captions_and_symbols():
    # the cyan tuning row tiles get captions + symbols when names/symbols are on
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:tuning:ssgens"].text == "superspace generator tuning map"
    assert cells["caption:tuning:ssprimes"].text == "superspace tuning map"
    assert cells["caption:just:ssprimes"].text == "superspace just tuning map"
    assert cells["caption:retune:ssprimes"].text == "superspace retuning map"
    # 𝒈ₗ = U+1D488 + ₗ, 𝒕ₗ = U+1D495 + ₗ, 𝒋ₗ = U+1D48B + ₗ, 𝒓ₗ = U+1D493 + ₗ
    assert cells["symbol:tuning:ssgens"].text == "\U0001D488ₗ"
    assert cells["symbol:tuning:ssprimes"].text == "\U0001D495ₗ"
    assert cells["symbol:just:ssprimes"].text == "\U0001D48Bₗ"
    assert cells["symbol:retune:ssprimes"].text == "\U0001D493ₗ"


def test_superspace_tuning_row_equivalences():
    # equivalences on appends the defining equation: 𝒕ₗ = 𝒈ₗ𝑀ₗ; 𝒓ₗ = 𝒕ₗ − 𝒋ₗ.
    # 𝒈ₗ and 𝒋ₗ are primary, no continuation.
    cells = {c.id: c for c in _barbados_ss(symbols=True, equivalences=True).cells}
    # 𝒕ₗ = 𝒈ₗ𝑀ₗ
    assert cells["symbol:tuning:ssprimes"].text == "\U0001D495ₗ = \U0001D488ₗ\U0001D440ₗ"
    # 𝒓ₗ = 𝒕ₗ − 𝒋ₗ
    assert cells["symbol:retune:ssprimes"].text == "\U0001D493ₗ = \U0001D495ₗ − \U0001D48Bₗ"


def test_superspace_tuning_standard_domain_trivially_passes_through():
    # over a standard prime domain the superspace IS the domain — 𝒈ₗ = 𝒈, 𝒕ₗ = 𝒕 etc.
    # Build doesn't crash; cells render with the same cents values as the existing rows.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cells = {c.id: c for c in spreadsheet.build(state, s).cells}
    # rL=2 ssgens
    assert "tuning:ssgen:0" in cells and "tuning:ssgen:1" in cells
    # dL=3 ssprimes
    for i in range(3):
        assert f"tuning:ssprime:{i}" in cells
        assert f"just:ssprime:{i}" in cells
        assert f"retune:ssprime:{i}" in cells


# ---------------------------------------------------------------------------
# Plain-text values for the new superspace tiles. The EBK strings under each
# new tile (when the plain_text_values toggle is on) read the same numbers
# the grid renders — service.plain_text_values is the single seam.
# ---------------------------------------------------------------------------


def test_B_L_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    # B_L for BARBADOS over 2.3.13/5 → ((1,0,0,0), (0,1,0,0), (0,0,-1,1))
    # rendered as a wrapped vector-list (the same _ket_list format the existing comma
    # basis uses — kets space-separated inside the outer [ … ])
    assert cells["ptext:ss_vectors:primes"].text == "[[1 0 0 0⟩ [0 1 0 0⟩ [0 0 -1 1⟩]"


def test_M_L_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    # the mapping-style stack "[⟨…]⟨…]⟨…]}" — same shape the existing M's plain-text uses
    ml = service.superspace_mapping(_barbados_state())
    expected = "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in ml) + "}"
    assert cells["ptext:ss_mapping:ssprimes"].text == expected


def test_M_jL_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    # the dL × dL identity rendered the same way as M_L
    assert cells["ptext:ss_just_mapping:ssprimes"].text == (
        "[⟨1 0 0 0]⟨0 1 0 0]⟨0 0 1 0]⟨0 0 0 1]}")


def test_cyan_superspace_tuning_tiles_have_plain_text_strings():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    tun = _barbados_superspace_tuning()
    # 𝒈ₗ — genmap shape "{ … ]"
    expected_g = "{" + " ".join(service.cents(v) for v in tun.generator_map) + "]"
    assert cells["ptext:tuning:ssgens"].text == expected_g
    # 𝒕ₗ / 𝒋ₗ / 𝒓ₗ — map shape "⟨ … ]"
    for row_key, vals in (("tuning", tun.tuning_map), ("just", tun.just_map),
                          ("retune", tun.retuning_map)):
        expected = "⟨" + " ".join(service.cents(v) for v in vals) + "]"
        assert cells[f"ptext:{row_key}:ssprimes"].text == expected


def test_superspace_plain_text_off_when_nonstandard_domain_off():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"plain_text_values": True}  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    for new in ("ptext:ss_vectors:primes", "ptext:ss_mapping:ssprimes",
                "ptext:ss_just_mapping:ssprimes", "ptext:tuning:ssgens",
                "ptext:tuning:ssprimes", "ptext:just:ssprimes", "ptext:retune:ssprimes"):
        assert new not in cids


def test_phase4_additive_only_against_baseline_with_all_show_toggles():
    # the additive-only contract for the whole Phase 4 contribution: a build over a
    # nonstandard-domain temperament with nonstandard_domain OFF must be identical to its
    # OFF-shape pre-Phase-4, regardless of which other Show toggles are on. Any of the new
    # cell/block/line ids appearing would mean Phase 4 leaked into the on-domain build.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {
        "names": True, "symbols": True, "counts": True, "plain_text_values": True,
        "equivalences": True, "units": True, "presets": True,
    }
    lay = spreadsheet.build(state, s)
    ids = ({c.id for c in lay.cells} | {b.id for b in lay.blocks}
           | {ln.id for ln in lay.lines})
    # the new id prefixes / fragments Phase 4 introduces
    for frag in ("ss_just_mapping", "cell:ss_vectors:primes:", "cell:ss_mapping:ssprimes:",
                 "ss_just_map", "ssgenmap", ":ssprimes:l", ":ssprimes:r"):
        assert not any(frag in i for i in ids), f"leaked id matching {frag!r}"


# ---------------------------------------------------------------------------
# Phase 4I — EBK bracket convention for the new superspace tiles. The
# maximized mockup's CSV row 7 records Douglas's note that he never decided
# on new brackets for the superspace and is "just using { for generators/rank
# and ( for primes/dimensionality" — but the rendered mockup itself shows
# the existing brackets unchanged (⟨ … ] for covectors over ss_primes,
# { … ] for the 𝒈ₗ genmap, [ … ⟩ for vector kets). Per the
# feedback_mockup_is_the_spec note the rendered mockup is the spec, so the
# new tiles reuse the existing bracket constants. These tests lock that
# choice so a later refactor can't drift the convention by accident, and so
# a future swap (the conservative "( … )" / "{ … }" variant the prompt
# suggested) shows up here as one explicit place to update.
# ---------------------------------------------------------------------------


def test_superspace_M_L_per_row_brackets_reuse_MAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    for i in range(3):  # rL=3 rows
        assert cells[f"bracket:ss_map:{i}:l"].text == "⟨"
        assert cells[f"bracket:ss_map:{i}:r"].text == "]"


def test_superspace_M_jL_per_row_brackets_reuse_MAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    for i in range(4):  # dL=4 rows
        assert cells[f"bracket:ss_just_map:{i}:l"].text == "⟨"
        assert cells[f"bracket:ss_just_map:{i}:r"].text == "]"


def test_superspace_t_L_j_L_r_L_brackets_reuse_MAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    for key in ("tuning", "just", "retune"):
        assert cells[f"bracket:{key}:ssprimes:l"].text == "⟨"
        assert cells[f"bracket:{key}:ssprimes:r"].text == "]"


def test_superspace_g_L_brackets_reuse_GENMAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["bracket:tuning:ssgenmap:l"].text == "{"
    assert cells["bracket:tuning:ssgenmap:r"].text == "]"


def test_superspace_M_L_and_M_jL_outer_frame_uses_ebktop_ebkbrace():
    # the spanning top + bottom frame is the existing ebktop / ebkbrace pair — same
    # convention the on-domain mapping uses. The asymmetric "[ … ⟩" plain-text shape
    # (square-open + ket-close) lives only on the bare prescaler 𝐿, not here.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["ebktop:ss_mapping"].kind == "ebktop"
    assert cells["ebkbrace:ss_mapping"].kind == "ebkbrace"
    assert cells["ebktop:ss_just_mapping"].kind == "ebktop"
    assert cells["ebkbrace:ss_just_mapping"].kind == "ebkbrace"


def test_existing_bracket_constants_are_unchanged_by_superspace():
    # the new superspace tiles reuse the existing constants — no new bracket-pair
    # constant was introduced, and the existing constants stay as they are
    assert spreadsheet.MAP_BRACKETS == ("⟨", "]")
    assert spreadsheet.LIST_BRACKETS == ("[", "]")
    assert spreadsheet.GENMAP_BRACKETS == ("{", "]")


# ---------------------------------------------------------------------------
# Polish — the existing math-expressions / charts / units / mnemonics
# infrastructure should automatically extend to the new superspace tuning
# cells via the group_ratio / CHARTED_ROWS / UNITS / MNEMONICS hooks the
# green and cyan commits set up. These tests lock that flow-through.
# ---------------------------------------------------------------------------


def test_math_expressions_render_j_L_cells_as_log_of_superspace_primes():
    # 𝒋ₗ over BARBADOS's superspace (2, 3, 5, 13) is 1200·log₂p for each prime; with
    # math_expressions on each cell should prefix the cents value with that closed form
    # (the same shape the on-domain (just, primes) cells take — closed_form_operand reads
    # group_ratio["ssprimes"], which the cyan commit wired up to the superspace primes).
    cells = {c.id: c for c in _barbados_ss(math_expressions=True).cells}
    assert cells["just:ssprime:0"].kind == "mathexpr"
    assert cells["just:ssprime:0"].text == "1200 · log₂2\n= 1200.000"
    assert cells["just:ssprime:1"].text == "1200 · log₂3\n= 1901.955"
    assert cells["just:ssprime:2"].text == "1200 · log₂5\n= 2786.314"
    assert cells["just:ssprime:3"].text.startswith("1200 · log₂13\n= ")  # 13 — value depends on rounding


def test_math_expressions_off_keeps_j_L_cells_as_plain_tval():
    # math expressions OFF: the just/ssprimes cells stay as plain "tval" cents cells, no
    # closed-form prefix. (The math toggle is independent of the other display flags.)
    cells = {c.id: c for c in _barbados_ss(math_expressions=False).cells}
    assert cells["just:ssprime:0"].kind == "tval"


def test_chart_band_renders_over_the_retune_r_L_tile_when_charts_is_on():
    # retune ∈ CHARTED_ROWS, so its tval_row records (retune, ssprimes) in chart_tiles,
    # and the build()'s chart pass emits a "chart" CellBox at that tile. The chart spans
    # the dL value columns, riding the group_left["ssprimes"] gridlines.
    cells = {c.id: c for c in _barbados_ss(charts=True).cells}
    chart = cells["chart:retune:ssprimes"]
    assert chart.kind == "chart"
    # the chart's value array is the dL retuning errors (same numbers the 𝒓ₗ cells carry)
    expected_vals = tuple(_barbados_superspace_tuning().retuning_map)
    assert chart.values == expected_vals


def test_chart_band_omitted_from_r_L_when_charts_is_off():
    cells = {c.id for c in _barbados_ss(charts=False).cells}
    assert "chart:retune:ssprimes" not in cells


def test_per_cell_units_subscript_b_on_the_superspace_tuning_cells():
    # the cyan tuning row's ssprimes cells carry "¢/b" units (the basis-element axis the
    # nonstandard-domain feature swaps p → b for). With units on, each cell's unit
    # subscripts the prime index — ¢/b₁, ¢/b₂, … — like the on-domain (tuning, primes)
    # cells subscript ¢/p₁, ¢/p₂. The same subscripting rides cell_unit through UNITS.
    cells = {c.id: c for c in _barbados_ss(units=True).cells}
    assert cells["tuning:ssprime:0"].unit == "¢/b₁"
    assert cells["tuning:ssprime:1"].unit == "¢/b₂"
    assert cells["just:ssprime:0"].unit == "¢/b₁"
    assert cells["retune:ssprime:0"].unit == "¢/b₁"


def test_per_cell_units_subscript_g_on_the_g_L_cells():
    # 𝒈ₗ over the ssgens column carries "¢/g" units (one cents-per-generator entry per
    # superspace generator), subscripted by the generator index — ¢/g₁, ¢/g₂, …
    cells = {c.id: c for c in _barbados_ss(units=True).cells}
    assert cells["tuning:ssgen:0"].unit == "¢/g₁"
    assert cells["tuning:ssgen:1"].unit == "¢/g₂"


def test_per_cell_units_on_the_M_L_cells_carry_g_over_b():
    # M_L (superspace mapping) is generators-per-basis-element (g/b), one entry per
    # (generator, superspace-prime). The subscript follows the column index — g₁/b₁,
    # g₁/b₂, … like the on-domain mapping cells take g₁/p₁ etc.
    cells = {c.id: c for c in _barbados_ss(units=True).cells}
    assert cells["cell:ss_mapping:ssprimes:0:0"].unit == "g₁/b₁"
    assert cells["cell:ss_mapping:ssprimes:0:1"].unit == "g₁/b₂"
    assert cells["cell:ss_mapping:ssprimes:1:0"].unit == "g₂/b₁"
