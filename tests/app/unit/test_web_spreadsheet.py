import pickle

import pytest

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import Editor
from rtt.app.layout import CellBox, Layout


@pytest.fixture(autouse=True, scope="module")
def _memoized_build():
    """Cache byte-identical spreadsheet.build calls for this module. Measured: ~465 of this
    file's ~857 builds repeat a prior (args, kwargs) exactly — ~34s of pure waste per run.
    Layout and its parts are frozen dataclasses and no test mutates a returned layout, so
    handing repeat calls the same object is behavior-preserving. In-file (not a tests/app
    conftest) deliberately: the render tests re-import rtt.* and must not see a stale patch."""
    real = spreadsheet.build
    cache: dict = {}

    def cached(*args, **kwargs):
        try:
            key = pickle.dumps((args, sorted(kwargs.items())), protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            return real(*args, **kwargs)  # unpicklable arguments: just build
        if key not in cache:
            cache[key] = real(*args, **kwargs)
        return cache[key]

    spreadsheet.build = cached
    try:
        yield
    finally:
        spreadsheet.build = real


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


def _proj_build(held_basis_ratios=(), **overrides):
    # a meantone build with the projection box on and a given held interval basis — () leaves the
    # tuning under-held (P/G/U dashed), a full rational basis like ("2/1", "5/4") completes it.
    s = settings.defaults()
    s["projection"] = True
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_basis_ratios=held_basis_ratios)


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


def _title_edges(lay):
    # each column header's (key, title-left, title-right) for its unwrapped title centred on its
    # gridline, left to right
    return [(c.id.split("header:", 1)[1],
             c.x + c.w / 2 - spreadsheet._title_w(c.text) / 2,
             c.x + c.w / 2 + spreadsheet._title_w(c.text) / 2)
            for c in sorted((c for c in lay.cells if c.kind == "colheader"), key=lambda c: c.x)]


def test_adjacent_column_titles_keep_a_margin():
    # Titles render unwrapped and centred on their gridline, overhanging a content-hugged column.
    # When two narrow columns sit side by side, the gap between them widens so the two overhangs
    # always stay >= TITLE_MARGIN apart — a long title (the "other intervals of interest" header)
    # can never overspill into its neighbour's title. The worst case is the empty held intervals
    # column right beside the empty interest column, with the wide target intervals column that
    # normally shields interest hidden: before the fix interest's title started 54px LEFT of where
    # held's title ended (the "o" of "other" left of the "s" of held's "intervals").
    s = settings.defaults()
    s["optimization"] = True  # show the (narrow) held intervals column, immediately left of interest
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, targets_in_use=False)
    edges = _title_edges(lay)
    assert [k for k, _l, _r in edges][-2:] == ["held", "interest"]  # the colliding pair, now adjacent
    for (lk, _ll, lr), (rk, rl, _rr) in zip(edges, edges[1:]):
        assert rl - lr >= spreadsheet.TITLE_MARGIN - 0.5, f"{lk}->{rk} titles only {rl - lr:.1f}px apart"


def test_title_clearance_leaves_shielded_columns_untouched():
    # The gap only widens on an ACTUAL title collision: where a column's neighbour is wide (its
    # title well inside its footprint) the clearance term goes slack and the gap stays GAP, so the
    # common layouts are unchanged. In the default view the wide target intervals column sits left
    # of interest, so interest keeps its plain GAP and narrow footprint (and still overhangs the
    # grid's right edge — right_overhang > 0).
    lay = _layout()
    interest = {c.id: c for c in lay.cells}["header:interest"]
    targets = {c.id: c for c in lay.cells}["header:targets"]
    assert interest.x == targets.x + targets.w + spreadsheet.GAP  # plain GAP, not widened
    assert lay.right_overhang > 0  # interest's title still overhangs the right edge (pane widens to show it)


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
    # a nonprime element (13/5) flips the header to the guide's term, keeping the "domain" prefix
    assert cells["header:primes"].text == "domain basis\nelements"
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


def test_nonstandard_but_all_prime_domain_still_reads_domain_primes():
    # 2.3.7 (archytas) is a nonstandard subgroup but every element is a genuine prime, so the
    # header stays "domain primes" — the "basis elements" wording is reserved for a basis that
    # actually carries a NONPRIME (e.g. 2.9.5, 2.3.13/5), not merely a non-contiguous prime set
    arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))  # 2.3.7
    s = settings.defaults()
    s["domain_units"] = True  # so the coordinate-label row renders
    cells = {c.id: c for c in spreadsheet.build(arch, s).cells}
    assert cells["header:primes"].text == "domain\nprimes"
    assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "7"]
    # its coordinate label is p (true primes) too, not the basis-element b
    assert cells["urow:primes:0"].text == "/p₁"


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


def test_mapping_over_generators_identity_renders_with_identity_objects():
    # 𝑀𝐺 = 𝐼: the mapping over its own generators is the r × r identity (the embedding) — an
    # identity object shown when identity_objects is on. A COLUMN-first vector list { … ] (each
    # generator a ket [ … } in gen coords), the on-domain twin of the superspace M_LGL; no
    # matlabels (like M_LGL, per the mockup).
    cells = {c.id: c for c in _with(identity_objects=True, names=True, symbols=True,
                                    equivalences=True, plain_text_values=True).cells}
    for i in range(2):  # r = 2
        for k in range(2):
            assert cells[f"cell:selfmap:{i}:{k}"].text == ("1" if i == k else "0")
            assert cells[f"cell:selfmap:{i}:{k}"].kind == "mapped"
    assert cells["symbol:mapping:gens"].text == "\U0001D440G = \U0001D43C"  # 𝑀G = 𝐼
    assert cells["caption:mapping:gens"].text == "mapped generators"  # projection off (base caption)
    # cols-first: an outer { … ] wrap, with per-column ket marks [ … } (NOT per-row covectors)
    assert cells["bracket:selfmap:l"].text == spreadsheet.GENMAP_BRACKETS[0]  # {
    assert cells["bracket:selfmap:r"].text == spreadsheet.GENMAP_BRACKETS[1]  # ]
    assert cells["ebktop:selfmap:0"].kind == "ebktop"
    assert cells["ebkbrace:selfmap:0"].kind == "ebkbrace"  # the ket's } foot
    assert cells["ptext:mapping:gens"].text == "{[1 0} [0 1}]"
    assert not any(c.startswith(("matlabel:row:mapping:gens", "matlabel:col:mapping:gens")) for c in cells)


def test_mapping_over_generators_identity_gated_off_by_default():
    # off by default (identity_objects is in IMPLEMENTED but ships off): the generators column
    # carries no tile at the mapping row — no cells, brackets, framing marks or fold toggle.
    cells = {c.id for c in _layout().cells}
    assert not any(c.startswith(("cell:selfmap", "bracket:selfmap", "ebktop:selfmap",
                                 "ebkbrace:selfmap")) for c in cells)
    assert "toggle:tile:mapping:gens" not in cells


def test_standard_identity_objects_wash_temperament_yellow():
    # the three identity tiles ride the mapping row / primes column, so under colorization they
    # wash YELLOW (temperament) like their siblings — NOT colourless. Guards the CELL_FACTORS
    # entries (𝑀ⱼ over P, 𝑀𝐺 over the generator basis B, 𝑀D over the neutral D — all 𝑀-family).
    washes = {b.id for b in _with(identity_objects=True, generator_detempering=True,
                                  temperament_colorization=True).blocks}
    for key in ("vectors:primes", "mapping:gens", "mapping:detempering"):
        assert f"wash:temperament:{key}" in washes
        assert f"wash:tuning:{key}" not in washes  # not cyan


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
    # dropping to 2.3.5 moves it to prime 2 — the − shows at each (a standard limit with d > 1).
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


def test_domain_minus_shows_even_when_the_shrink_would_degenerate():
    # augmented tempers out 128/125; dropping prime 5 leaves prime 2 tempered to a unison (a
    # degenerate result) — but that is allowed, just as tempering one out via the comma + is, so the
    # − shows. Only a nonstandard subgroup or d == 1 withholds it (not a would-be degenerate result).
    augmented = service.from_comma_basis(((7, 0, -3),))  # 2.3.5, mapping shrinks to ((0, 1),)
    cells = {c.id for c in spreadsheet.build(augmented).cells}
    assert {"prime:0", "prime:2"} <= cells
    assert "minus" in cells and "basis_minus" in cells  # the − is offered on both axes


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


def test_interval_pluses_survive_hiding_the_quantities_row():
    # the interval columns' + ride the shared column fan above the grid, NOT the quantities row, so
    # they stay addable straight from the interval-vectors row when the quantities row is hidden —
    # either folded (its row toggle) or dropped by the domain-quantities setting. Clicking + then
    # drops the cursor into the new column's first vector cell (see app.add_interval). The
    # domain/generator + (plus, gen_plus) DO answer to the quantities row: their draft is a ratio /
    # element header, with no editable vectors-row twin to fall back to.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    interval_pluses = {"comma_plus", "target_plus", "interest_plus"}
    quantities_only = {"plus", "gen_plus"}

    shown = {c.id for c in spreadsheet.build(state).cells}
    assert (interval_pluses | quantities_only) <= shown  # both kinds present with the row shown

    folded = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"}).cells}
    assert interval_pluses <= folded                     # interval + survive the fold...
    assert quantities_only.isdisjoint(folded)            # ...the domain/generator + fold away with it

    off = settings.defaults()
    off["interval_ratios"] = False                     # the setting drops the row from the layout
    dropped = {c.id for c in spreadsheet.build(state, off).cells}
    assert interval_pluses <= dropped
    assert quantities_only.isdisjoint(dropped)

    # with BOTH interval rows hidden there is nowhere to place or focus a draft, so every + goes
    both_hidden = {c.id for c in spreadsheet.build(state, off, collapsed={"row:vectors"}).cells}
    assert (interval_pluses | quantities_only).isdisjoint(both_hidden)


def test_interval_minuses_rehome_to_the_vectors_row_when_quantities_hidden():
    # the twin of the + fix: the interval columns' − (each column's removal, and a draft's cancel)
    # ride the quantities row when it shows, but re-home onto the interval-vectors row when it is
    # hidden, so a column — or an accidental draft — stays removable there. The domain/generator −
    # (the domain shrink "minus", "gen_minus") do NOT re-home: their twins basis_minus (vectors row)
    # and map_minus (mapping row) already offer those removals where the quantities row is gone.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    shown = {c.id for c in spreadsheet.build(state).cells}
    assert {"comma_minus:0", "target_minus:0", "minus", "gen_minus"} <= shown  # all there with the row shown

    folded = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"}).cells}
    assert {"comma_minus:0", "target_minus:0"} <= folded   # the interval − re-home onto the vectors row...
    assert {"minus", "gen_minus"}.isdisjoint(folded)     # ...the domain/generator − do not
    assert "basis_minus" in folded                       # (the domain − twin already lives on the vectors row)

    # a draft opened while the quantities row is hidden still carries its cancel − there
    drafts = (("pending_comma", "comma_minus:pending"), ("pending_interest", "interest_minus:pending"))
    for arg, minus_id in drafts:
        cells = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"},
                                                 **{arg: [None, None, None]}).cells}
        assert minus_id in cells

    # both interval rows hidden → nothing to remove from, so the re-homed − go too
    off = settings.defaults(); off["interval_ratios"] = False
    both_hidden = {c.id for c in spreadsheet.build(state, off, collapsed={"row:vectors"}).cells}
    assert {"comma_minus:0", "target_minus:0"}.isdisjoint(both_hidden)


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
    # offers its gridline "add" zone (dropping an interval in tempers it out). Projection is held
    # off: its consolidated V = C|U view freezes the comma count controls (see the projection
    # tests), so dragging commas around is a structurally-editable, projection-off concern.
    on = {**_all_on(), "projection": False}
    one = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), on).cells}
    assert "grip:commas:0" in one and "grip:commas:add" in one  # the lone comma grips too
    two = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),)), on).cells}  # r=1, n=2
    assert "grip:commas:0" in two and "grip:commas:1" in two
    ji = {c.id for c in spreadsheet.build(service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4)))), on).cells}
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


def test_mid_list_removal_keeps_every_survivors_token():
    # removing entry 0 (any non-last entry) leaves the survivors' tokens untouched — its own token
    # simply vanishes, so the remove-preview diff blames the REMOVED column/row, not whichever one
    # slides into its slot (the reported hover-the-first-comma's-minus-reds-the-last bug)
    a, b, c = "81/80", "128/125", "64/63"
    prev = spreadsheet.assign_column_tokens(None, [a, b, c])   # tokens 0,1,2
    removed = spreadsheet.assign_column_tokens(prev, [b, c])   # drop the FIRST entry
    assert _tokens(removed) == [1, 2]                          # survivors keep their ids; 0 is gone


def test_basis_groups_claim_freed_slots_positionally_on_a_resolve():
    # a BASIS group (claim_unmatched=True: the mapping rows, the commas) can be rewritten wholesale
    # by a re-solve — a rank drop recombines every row, so nothing content-matches. The unmatched
    # new rows claim the freed tokens in order: the diff reads "row 0's values moved (amber), the
    # surplus last row goes (red)" — not every row removed-plus-recreated (which would paint the
    # whole matrix red and ring nothing as moved).
    r0, r1 = (1, 1, 0), (0, 1, 4)
    prev = spreadsheet.assign_column_tokens(None, [r0, r1])    # rank 2: tokens 0,1
    dropped = spreadsheet.assign_column_tokens(prev, [(12, 19, 28)], claim_unmatched=True)
    assert _tokens(dropped) == [0]                             # the survivor claims slot 0; 1 is the red row
    # but a survivor-verbatim removal still matches by content first: removing row 0 keeps row 1's id
    removed = spreadsheet.assign_column_tokens(prev, [r1], claim_unmatched=True)
    assert _tokens(removed) == [1]                             # row 0's id vanishes with it → row 0 reds


def test_interval_sets_never_relabel_a_dropped_column_as_a_new_one():
    # the independent interval SETS (targets/held/interest) leave claim_unmatched off: a brand-new
    # ratio is genuinely new, never "the same column as" a dropped one — so a family switch reds the
    # dropped ratios (still on screen) and the new ones arrive with fresh ids (off-screen, no ring)
    prev = spreadsheet.assign_column_tokens(None, ["3/2", "6/5", "5/4"])  # tokens 0,1,2
    switched = spreadsheet.assign_column_tokens(prev, ["3/2", "7/4"])     # 3/2 survives; 6/5+5/4 drop; 7/4 new
    assert _tokens(switched) == [0, 3]                         # 7/4 is FRESH (3), not relabelled 1 or 2


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
    # tuning-derived cells (tempered sizes, errors, charts, plain-text re-lists) shift by sub-cent
    # solver noise / re-list on reorder, so they're expected to "change" — filter them out
    return cid.startswith(("chart:", "ptext:", "tuning:", "retune:", "rangechart:"))


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
    # grip and the − — stay INDEX-keyed: each is bound to a SLOT, not a column. So a
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
    assert c2["cell:held:0:2"].x == slot_x[0]                    # but the value column DID glide to the front


def test_reordering_interest_rekeys_its_column_cells():
    interest = [(1, 1, -1), (-1, 1, 0), (2, 0, -1)]  # 6/5, 3/2, 9/8-ish
    lay1 = spreadsheet.build(_held_state(), _all_on(), interest=interest)
    lay2 = spreadsheet.build(_held_state(), _all_on(),
                             interest=[interest[2], interest[0], interest[1]], prev_ids=lay1.identities)
    moved = {cid for cid in spreadsheet.changed_cell_ids(lay1, lay2) if not _reorder_volatile(cid)}
    assert moved == set(), f"interest cells re-filled in place instead of gliding: {sorted(moved)}"


def test_reordering_targets_rekeys_its_column_cells():
    # targets carry the optimization mean damage, so the damage row shifts by solver noise on reorder
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
    # the generator-detempering D stays a read-only ratio (its vectors row is read-only too)
    assert cells["detempering:0"].kind == "commaratio"
    # the domain elements are editable (elementcell) ONLY with the nonstandard-domain box on — that
    # box is what makes the basis typeable; with it off they are read-only domain primes
    assert cells["prime:0"].kind == "elementcell"  # nonstandard_domain is among the toggles set on above
    off = settings.defaults()  # nonstandard_domain off
    off_cells = {c.id: c for c in spreadsheet.build(ed.state, off).cells}
    assert off_cells["prime:0"].kind == "prime"


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


def test_adjacent_tiles_keep_a_roomy_minimum_gap():
    # the minimum whitespace between two grey tiles is GAP - 2*PAD — wide enough that the
    # 2px-thick gridlines threading the gap keep their room
    blocks = {b.id: b for b in _layout().blocks}
    top, bot = blocks["block:tuning:targets"], blocks["block:just:targets"]
    assert (top.x, top.w) == (bot.x, bot.w)  # the same column, stacked vertically
    assert bot.y - (top.y + top.h) == spreadsheet.GAP - 2 * spreadsheet.PAD  # the visible gap between the two tiles


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
    # an "interval ratios" column header, leftmost of the data columns (before generators)
    assert cells["header:quantities"].text == "interval ratios"
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


def test_tuning_tiles_off_removes_the_tuning_rows_and_the_target_intervals_column():
    off = {c.id for c in _with(tuning_tiles=False).cells}
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
    assert {"minus", "plus", "comma_minus:0", "comma_plus", "gen_minus", "gen_plus",
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
    # the domain/comma ± controls and the tile structure carry no value, so they're untouched
    assert {"plus", "minus", "comma_plus", "label:mapping", "header:primes", "toggle:row:mapping"} <= set(off)
    # the quantities ROW headers + spine COLUMN now blank too (their boxes stay, numbers cleared)
    for cid in ("prime:0", "comma:0", "target:0"):
        assert cid in off and not on[cid].blank and off[cid].blank and off[cid].text == ""


def test_general_quantities_off_blanks_the_quantities_row_col_and_unrotated_vectors():
    # general quantities-off blanks the numbers of EVERY value cell -- including the three regions
    # that used to leak: the quantities ROW (domain primes / nonstandard elements / interval-ratio
    # headers), the quantities COLUMN / spine (the domain basis), and the unrotated vector list's
    # editable unchanged cells. Superspace mirrors the main block with the same kinds, so its
    # quantities blank too. Boxes/EBK marks stay (the gentle behavior) -- only the numbers clear.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    full = settings.defaults() | {k: True for k in settings.IMPLEMENTED}
    on = {c.id: c for c in spreadsheet.build(state, {**full, "quantities": True}).cells}
    off = {c.id: c for c in spreadsheet.build(state, {**full, "quantities": False}).cells}
    regions = (
        "prime:0", "prime:2",              # quantities row: a domain prime + a nonstandard element (13/5)
        "comma:0", "target:0",             # quantities row: interval-ratio headers
        "basis:0", "basis:2",              # quantities spine column: the domain basis
        "qgen:0",                          # quantities row: a generator ratio
        "ssqprime:0", "ssqgen:0",          # superspace mirror: its primes + generator ratios
    )
    for cid in regions:
        assert cid in on and on[cid].text and not on[cid].blank  # carries a value when on
        assert off[cid].blank and off[cid].text == ""            # box kept, number cleared when off
    # the structure stays (this is quantities-off, not gridded-off): the spine cell's box survives
    assert "basis:0" in off and any(c.startswith("bracket:") for c in off)


def test_gridded_values_off_also_empties_the_math_expression_cells():
    # math expressions swap the just row's cents for "log₂…" cells (kind mathexpr);
    # gridded values off empties the tiles, so those go too (like the cents they
    # replace). General quantities, by contrast, only trims their "= value" tail
    # (see test_math_expressions_without_quantities_show_only_the_expression).
    on = {c.id for c in _with(math_expressions=True).cells}
    off = {c.id for c in _with(math_expressions=True, gridded_values=False).cells}
    assert any(c.startswith("just:") for c in on)  # shown when gridded values is on
    assert not any(c.startswith("just:") for c in off)  # gone when it is off


def test_interval_ratios_off_removes_the_interval_ratios_row_and_column():
    on, off = _with(), _with(interval_ratios=False)
    on_ids, off_ids = {c.id for c in on.cells}, {c.id for c in off.cells}
    assert {"label:quantities", "prime:0", "header:quantities"} <= on_ids  # present by default
    # the interval-ratios ROW (band key still "quantities") -- its label, the domain-prime /
    # target-ratio headers in it, the domain ± controls riding it, and its gridline -- is gone
    assert "label:quantities" not in off_ids
    assert not any(c.startswith(("prime:", "target:")) for c in off_ids)
    assert {"minus", "plus"}.isdisjoint(off_ids)
    assert "h:quantities" not in {ln.id for ln in off.lines}
    # the interval-ratios spine COLUMN goes with it: its header and its vertical gridline
    assert "header:quantities" not in off_ids
    assert "trunk:quantities" not in {ln.id for ln in off.lines}
    # the body values (mapping matrix, tuning rows) are untouched
    assert {"cell:mapping:0:0", "tuning:target:0"} <= off_ids


def test_temperament_tiles_off_removes_the_mapping_row_and_domain_columns():
    off = {c.id: c for c in _with(temperament_tiles=False).cells}
    on = {c.id: c for c in _with().cells}
    # the mapping quantities (matrix, mapped list, generator ratios) are gone
    assert "label:mapping" not in off
    assert not any(c.startswith(("cell:mapping:", "cell:mapped:", "gen:")) for c in off)
    # the interval-vectors row owns its own toggle now (interval_vectors), so it does NOT go with
    # the temperament tiles: it stays, still showing the target vectors over the surviving targets
    # column. Only the cells in the now-gone temperament columns (the comma vectors) vanish.
    assert "label:vectors" in off
    assert "cell:vec:targets:0:0" in off
    # the whole domain-primes column goes with it: its header, the prime headers,
    # and every row's prime-side cells -- including the tuning maps over primes
    assert "header:primes" not in off
    assert not any(c.startswith(("prime:", "tuning:prime:", "just:prime:", "retune:prime:")) for c in off)
    # the commas column belongs to the temperament too, so it goes as well: header,
    # comma headers, the comma basis (its vectors), and the comma-size cells across the tuning rows
    assert "header:commas" not in off
    assert not any(c.startswith(("comma:", "cell:comma:", "tuning:comma:", "just:comma:",
                                 "retune:comma:")) for c in off)
    assert {"comma_plus", "comma_minus:0"}.isdisjoint(off)
    # tuning over the targets survives and rises into the freed space (the mapping row vacated)
    assert "tuning:target:0" in off
    assert off["tuning:target:0"].y < on["tuning:target:0"].y


def test_interval_vectors_off_removes_the_interval_vectors_row_only():
    off = {c.id: c for c in _with(interval_vectors=False).cells}
    on = {c.id: c for c in _with().cells}
    # the interval-vectors row -- its label and every interval-as-vector cell (targets, commas,
    # intervals of interest) -- is gone, since the row now answers to its own toggle
    assert "label:vectors" not in off
    assert not any(c.startswith(("cell:vec:", "cell:comma:", "cell:interest:", "cell:held:"))
                   for c in off)
    # ...but the temperament tiles are untouched: the mapping row, the domain columns, and the
    # interval-ratios row (comma ratios / prime ratios) all stay
    assert {"label:mapping", "cell:mapping:0:0", "header:primes", "header:commas",
            "label:quantities"} <= set(off)
    # the mapping row rises into the space the vectors row vacated
    assert off["label:mapping"].y < on["label:mapping"].y


def test_interval_vectors_row_reserves_no_phantom_picker_band_when_commas_column_hidden():
    # the comma-picker band rides the interval-vectors row's head, but its picker cells only emit
    # when the commas COLUMN is open (tile_open("vectors","commas")). Now the vectors row can show
    # while the commas column is hidden (it answers to interval_vectors, the commas column to
    # temperament_tiles), the band must NOT reserve empty space below the comma matrix.
    s = settings.defaults()
    s["temperament_tiles"], s["interval_vectors"], s["presets"] = False, True, True
    meantone = service.from_mapping(((1, 1, 0), (0, 1, 4)))          # nc = 1 (a comma in state)
    full = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))   # nc = 0 (no comma)
    with_comma = {b.id: b for b in spreadsheet.build(meantone, s).blocks}
    no_comma = {b.id: b for b in spreadsheet.build(full, s).blocks}
    # with the commas column hidden, the comma in state must not grow the vectors row: its spine
    # tile is the same height as the no-comma build (which reserves no band either way)
    assert with_comma["block:vec:quantities"].h == no_comma["block:vec:quantities"].h
    # and there are genuinely no picker cells to back a band (the commas column is gone)
    assert not any(c.id.startswith("commapick") for c in spreadsheet.build(meantone, s).cells)


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
    # "interval ratios" (floored wider so its title clears the frozen corner) keeps that floored width
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
    # the "form tiles" toggle adds a "canonical mapping" row whose primes tile holds M in
    # canonical form (defactored + HNF) — for ((1,1,0),(0,1,4)) that is
    # ((1,0,-4),(0,1,4)), distinct from the stored matrix in the mapping row
    cells = {c.id: c for c in _with(form_tiles=True).cells}
    assert cells["cell:canon:0:0"].text == "1"
    assert cells["cell:canon:0:2"].text == "-4"
    assert cells["cell:canon:1:1"].text == "1"
    assert cells["cell:canon:1:2"].text == "4"
    # off by default the row adds nothing
    assert not any(c.id.startswith("cell:canon:") for c in _layout().cells)


def test_canonical_mapping_row_is_framed_like_the_mapping_above_it():
    cells = {c.id: c for c in _with(form_tiles=True).cells}
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


def test_form_box_shows_the_inverse_form_matrix_over_the_gens():
    cells = {c.id: c for c in _with(form_tiles=True).cells}
    # the canon row's gens tile is 𝐹⁻¹ (𝑀_C = 𝐹⁻¹𝑀, g_C/g) — read-only; the EDITABLE 𝐹 (𝑀 = 𝐹𝑀_C)
    # rides the mapping row's canonical-generators column instead. For ((1,1,0),(0,1,4)), 𝐹⁻¹ = ((1,-1),(0,1))
    assert cells["cell:form:0:0"].text == "1" and cells["cell:form:0:1"].text == "-1"
    assert cells["cell:form:1:0"].text == "0" and cells["cell:form:1:1"].text == "1"
    assert cells["cell:form:0:0"].kind == "mapped"  # read-only (the inverse is derived)
    assert cells["caption:canon:gens"].text == "inverse generator form matrix"
    # framed { … ] per row (the generator-map brackets) plus an enclosing top bracket/brace
    assert cells["bracket:form:map:0:l"].text == "{" and cells["bracket:form:map:0:r"].text == "]"
    assert "ebktop:form" in cells and "ebkbrace:form" in cells
    # the form box adds nothing while the toggle is off
    assert not any(c.id.startswith("cell:form:") for c in _layout().cells)


def test_canonical_generators_column_sits_between_units_and_generators():
    # the form layer surfaces a "canonical generators" column (the mockup), between the units
    # spine and the generators column, gated on the canonical-mapping row (show_canon)
    cells = {c.id: c for c in _with(form_tiles=True).cells}
    assert cells["header:canongens"].text == "canonical\ngenerators"
    # right of the quantities spine, left of the generators column (the mockup ordering)
    assert cells["header:quantities"].x < cells["header:canongens"].x < cells["header:gens"].x
    # and immediately right of the units spine when that column is shown
    with_units = {c.id: c for c in _with(form_tiles=True, domain_units=True).cells}
    assert with_units["header:units"].x < with_units["header:canongens"].x < with_units["header:gens"].x
    # the column is absent without the form tiles
    assert not any(c.id == "header:canongens" for c in _layout().cells)


def test_canonical_generators_render_as_a_ratio_list_over_the_column_and_in_the_spine():
    # the canonical generators (g_C) head their column over the quantities row (the dual of the
    # generators column's qgen list) AND label the canon rows in the spine — for ((1,1,0),(0,1,4))
    # the canonical generators are 2/1, 3/1 (vs the stored equave-reduced 2/1, 3/2)
    cells = {c.id: c for c in _with(form_tiles=True).cells}
    assert cells["cangen:0"].text == "2/1" and cells["cangen:1"].text == "3/1"
    assert cells["cangen:0"].kind == "genratio"
    # the spine twin (the canonical generators labelling the canon rows, like gens label the mapping)
    assert cells["canon:gen:0"].text == "2/1" and cells["canon:gen:1"].text == "3/1"
    assert cells["canon:gen:0"].x == cells["header:quantities"].x  # in the quantities spine column
    # the horizontal ratios sit in the canonical-generators column, over the quantities row
    assert cells["cangen:0"].x == cells["header:canongens"].x + spreadsheet.BRACKET_W
    assert cells["cangen:0"].y < cells["canon:gen:0"].y  # the column header above the canon-row spine


def test_form_matrices_canceling_out_is_an_identity_tile_in_the_canonical_generators_column():
    # 𝐹⁻¹𝐹 = 𝐼 (rc×rc identity) renders in the canon row's canonical-generators column, gated on
    # the identity_objects toggle (like 𝑀𝐺 = 𝐼), framed { … ] per row with an enclosing bracket/brace
    cells = {c.id: c for c in _with(form_tiles=True, identity_objects=True).cells}
    assert cells["cell:fcancel:0:0"].text == "1" and cells["cell:fcancel:0:1"].text == "0"
    assert cells["cell:fcancel:1:0"].text == "0" and cells["cell:fcancel:1:1"].text == "1"
    assert cells["bracket:fcancel:map:0:l"].text == "{" and cells["bracket:fcancel:map:0:r"].text == "]"
    assert "ebktop:fcancel" in cells and "ebkbrace:fcancel" in cells
    assert cells["caption:canon:canongens"].text == "form matrices canceling out"
    # it sits in the canonical-generators column (left of the generators column's F)
    assert cells["cell:fcancel:0:0"].x == cells["cangen:0"].x
    assert cells["cell:fcancel:0:0"].x < cells["cell:form:0:0"].x
    # gated on identity_objects: form tiles alone shows the column + its ratios but not 𝐹⁻¹𝐹
    form_only = {c.id for c in _with(form_tiles=True).cells}
    assert "cangen:0" in form_only and "cell:fcancel:0:0" not in form_only


def test_form_box_symbols_and_units_match_the_canonical_notation():
    from rtt.app.grid_tables import SUBSCRIPT_C
    gc = f"g{SUBSCRIPT_C}"
    cells = {c.id: c for c in _with(form_tiles=True, identity_objects=True,
                                    symbols=True, equivalences=True, header_symbols=True,
                                    units=True, domain_units=True).cells}
    # the big symbols: 𝑀_C (canonical mapping), 𝐹⁻¹ (inverse form matrix, over the gens column),
    # 𝐹 (the form matrix itself, over the canonical-generators column), 𝐹⁻¹𝐹 = 𝐼 (canceling out)
    assert cells["symbol:canon:primes"].text == f"𝑀{SUBSCRIPT_C}"
    assert cells["symbol:canon:gens"].text == "𝐹⁻¹"
    assert cells["symbol:mapping:canongens"].text == "𝐹"
    assert cells["symbol:canon:canongens"].text == "𝐹⁻¹𝐹 = 𝐼"
    # the canonical mapping's rows carry 𝒎_C row labels in the primes gutter (like 𝒎 on the mapping)
    assert cells["matlabel:row:canon:primes:0"].text == f"𝒎{SUBSCRIPT_C}₁"
    # the per-box "units:" lines: g_C/p, g_C/g, g_C/g_C
    assert cells["units:canon:primes"].text == f"units: {gc}/p"
    assert cells["units:canon:gens"].text == f"units: {gc}/g"
    assert cells["units:canon:canongens"].text == f"units: {gc}/{gc}"
    # the units row/column coordinate labels (the spine g_Cᵢ/ and the column's /g_Cᵢ)
    assert cells["ucol:canon:0"].text == f"{gc}₁/"
    assert cells["urow:canongens:0"].text == f"/{gc}₁"


def test_rank_count_merges_across_the_canonical_generators_and_generators_columns():
    # the mockup draws ONE "rank / r = 2" tile spanning both the canonical-generators and the
    # generators columns (the rank is the shared cardinality of both generator bases)
    cells = {c.id: c for c in _with(form_tiles=True).cells}
    rank, hcan, hgen = cells["count:gens"], cells["header:canongens"], cells["header:gens"]
    assert rank.text.endswith(" = 2")  # the rank r = 2 (math-italic r glyph + " = 2")
    assert rank.x <= hcan.x and rank.x + rank.w >= hgen.x  # the cell spans both column headers
    assert cells["caption:counts:gens"].text == "rank"
    assert "count:canongens" not in cells  # no separate canonical-generators count — it's merged
    plain = {c.id: c for c in _layout().cells}  # hugs the generators column alone without the form layer
    assert plain["count:gens"].x == plain["header:gens"].x


def test_form_matrix_row_labels_get_a_balanced_matlabel_gutter():
    # the form matrix 𝐹's 𝒇 row labels (its own tile, the mapping row's canonical-generators column)
    # must reserve the same balanced gutter the mapping's 𝒎 labels do — in a gutter LEFT of the EBK,
    # not crammed against it. (The gutter generalizes to ANY column carrying per-row matrix labels.)
    cells = {c.id: c for c in _with(form_tiles=True, header_symbols=True).cells}
    flabel, fbracket = cells["matlabel:row:mapping:canongens:0"], cells["bracket:finv:map:0:l"]
    assert flabel.text == "𝒇₁"
    assert flabel.x + flabel.w <= fbracket.x  # the label sits left of (or up to) the { bracket, not over it
    assert flabel.w > 0 and fbracket.x - flabel.x >= flabel.w  # a real gutter, ≥ the label's own width


def test_canonical_generators_column_builds_finv_embedding_and_tuning_tiles():
    from rtt.app.grid_tables import SUBSCRIPT_C
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"),
                                          form_tiles=True, symbols=True, header_symbols=True).cells}
    # 𝐹 (generator form matrix) over the mapping row: M = F·M_C, so F = ((1,1),(0,1)) (cell id is the
    # historical "cell:finv" from before the 𝐹/𝐹⁻¹ swap)
    assert cells["cell:finv:0:0"].text == "1" and cells["cell:finv:0:1"].text == "1"
    assert cells["cell:finv:1:0"].text == "0" and cells["cell:finv:1:1"].text == "1"
    assert cells["symbol:mapping:canongens"].text == "𝐹"
    assert "bracket:finv:map:0:l" in cells
    # G_C (canonical generator embedding) = G·F⁻¹ — for quarter-comma meantone [[1 1],[0 0],[0 1/4]]:
    # column 0 the octave [1 0 0⟩, column 1 the canonical fifth [1 0 1/4⟩ (cell ids are :row:col)
    assert cells["cell:embed_c:0:0"].text == "1" and cells["cell:embed_c:0:1"].text == "1"
    assert cells["cell:embed_c:2:1"].text == "1/4"
    assert cells["symbol:projection:canongens"].text == f"G{SUBSCRIPT_C}"
    # 𝒈_C (canonical generator tuning map) = 𝒈·F⁻¹ — the octave and the canonical (~3/1) fifth
    assert cells["tuning:cangen:0"].text.startswith("1200")
    assert cells["tuning:cangen:1"].text.startswith("1896")
    assert cells["symbol:tuning:canongens"].text == f"𝒈{SUBSCRIPT_C}"
    # the three tiles are absent without the form layer / projection
    assert not any(c.id.startswith(("cell:finv:", "cell:embed_c:")) for c in _layout().cells)


def test_canonical_generators_column_tiles_carry_plain_text_matching_their_grids():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), form_tiles=True, plain_text_values=True).cells}
    # the three new tiles' EBK strings read in the same brackets as their grids (the lockstep guard
    # enforces this globally; here we pin the exact strings): 𝐹 a covector stack, G_C a vector list,
    # 𝒈_C a cents genmap
    assert cells["ptext:mapping:canongens"].text == "[{1 1] {0 1]}"          # 𝐹 (𝑀 = 𝐹𝑀_C)
    assert cells["ptext:projection:canongens"].text == "{[1 0 0⟩ [1 0 1/4⟩]"  # G_C
    assert cells["ptext:tuning:canongens"].text.startswith("{1200")          # 𝒈_C


def test_canonical_embedding_and_tuning_tiles_carry_their_column_index_headers():
    from rtt.app.grid_tables import SUBSCRIPT_C
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), form_tiles=True, header_symbols=True).cells}
    # G_C / 𝒈_C head each canonical-generator column with its index (𝐠_Cᵢ / 𝒈_Cᵢ), like G / 𝒈 do
    assert cells["matlabel:col:projection:canongens:0"].text == f"𝐠{SUBSCRIPT_C}₁"
    assert cells["matlabel:col:projection:canongens:1"].text == f"𝐠{SUBSCRIPT_C}₂"
    assert cells["matlabel:col:tuning:canongens:0"].text == f"𝒈{SUBSCRIPT_C}₁"
    assert cells["matlabel:col:tuning:canongens:1"].text == f"𝒈{SUBSCRIPT_C}₂"


def test_generator_form_matrix_is_interactive():
    # the 𝐹 tile (mapping row × canonical generators) is editable — its gridded cells AND its
    # plain-text band — so the user can re-store the mapping in any generating set, in sync with
    # <choose form>. Its read-only inverse 𝐹⁻¹ (canon row × gens) is NOT editable.
    cells = {c.id: c for c in _with(form_tiles=True, plain_text_values=True).cells}
    assert cells["cell:finv:0:0"].kind == "formcell"            # 𝐹: routed to the editable gridvalue component
    assert cells["ptext:mapping:canongens"].kind == "ptextedit"  # 𝐹's editable plain-text input
    assert cells["cell:form:0:0"].kind == "mapped"              # 𝐹⁻¹: read-only
    assert cells["ptext:canon:gens"].kind == "ptext"           # 𝐹⁻¹'s plain text is read-only
    from rtt.app.grid_tables import EDITABLE_PTEXT
    assert ("mapping", "canongens") in EDITABLE_PTEXT and ("canon", "gens") not in EDITABLE_PTEXT


def test_form_controls_adds_a_choose_form_chooser_to_the_mapping_and_comma_basis_boxes():
    cells = {c.id: c for c in _with(form_controls=True).cells}
    # a "<choose form>" chooser rides in the mapping box and the comma-basis box
    assert cells["formchooser:mapping"].kind == "formchooser"
    assert cells["formchooser:comma_basis"].kind == "formchooser"
    # form CONTROLS (the dropdowns) does NOT reveal the canonical-mapping row / 𝐹 matrix — those
    # belong to "form tiles" (greyed for now); the dropdowns appear without the boxes
    assert not any(c.id.startswith(("cell:canon:", "cell:form:")) for c in cells.values())
    # each over its box's column (mapping over the primes, comma basis over the commas), seated
    # one BOX_INNER inside its tile-spanning box's left edge
    inset = spreadsheet.BOX_INNER
    assert cells["formchooser:mapping"].x == cells["header:primes"].x + inset
    assert cells["formchooser:comma_basis"].x == cells["header:commas"].x + inset
    # seated below the tile's value rows, never over the matrix
    assert cells["formchooser:mapping"].y > cells["cell:mapping:1:0"].y
    # the control adds nothing while form_controls is off
    assert not any(c.id.startswith("formchooser:") for c in _layout().cells)


def test_form_chooser_is_stateful_showing_the_mappings_current_form():
    # the <choose form> dropdown shows the mapping's CURRENT generator form selected (its cell
    # carries that form key). The default meantone ((1,1,0),(0,1,4)) is the equave-reduced form.
    cells = {c.id: c for c in _with(form_controls=True).cells}
    assert cells["formchooser:mapping"].text == "equave-reduced"
    # a mapping stored in canonical form reads "canonical"
    canon = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 0, -4), (0, 1, 4))),
        {**settings.defaults(), "form_controls": True}).cells}
    assert canon["formchooser:mapping"].text == "canonical"
    # the comma-basis chooser is stateful too: the default meantone's comma basis [⟨4 -4 1⟩] is the
    # canonical (antitransposed defactored Hermite) form, so its cell reads "canonical"
    assert cells["formchooser:comma_basis"].text == "canonical"


def test_mapped_list_rules_its_vector_columns_apart_clear_of_the_marks():
    cells = {c.id: c for c in _layout().cells}
    # the mapped target interval list separates its vector columns with vertical
    # bars, and the per-column top/bottom marks are inset so they never touch one
    assert "sep:mapped:1" in cells  # a bar between columns 0 and 1
    sep = cells["sep:mapped:1"]
    top0, brace0 = cells["ebktop:mapped:0"], cells["ebkbrace:mapped:0"]
    assert top0.w < spreadsheet.COL_W and brace0.w < spreadsheet.COL_W  # inset, not full column
    assert top0.x + top0.w < sep.x  # the mark stops short of the bar to its right
    # the rules span the matrix's full framed height and OVERHANG the per-column top/bottom
    # marks by FRAME_OVERHANG at each end — exactly like the outer [ ] wrap (and mirroring how
    # the mapping's spanning bracket overhangs its per-row ⟨ ] in x) — so every vertical rule
    # of the matrix clears the marks rather than stopping flush with (or short of) them
    outer = cells["bracket:mapped:l"]
    over = spreadsheet.FRAME_OVERHANG
    assert sep.y == outer.y == top0.y - over            # top: overhang above the top marks
    assert sep.y + sep.h == outer.y + outer.h == brace0.y + brace0.h + over  # below the bottom marks


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
    lay = _with(presets=True)
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    assert {"preset:temperament", "preset:tuning", "preset:target"} <= set(cells)
    inset = spreadsheet.BOX_INNER  # the dropdown sits one inner-pad inside its tile-spanning box
    # the temperament chooser sits under the mapping matrix, one inner pad into its tile-spanning box
    # (which spans the primes column — NOT keyed off the header, which now centres over the matrix
    # once the ET-picker right gutter is balanced by an equal left pad)
    temp, matrix = cells["preset:temperament"], cells["cell:mapping:0:0"]
    box = blocks["block:preset:temperament"]
    assert temp.y > matrix.y and temp.x == box.x + inset
    assert box.x <= matrix.x and matrix.x + matrix.w <= box.x + box.w  # the box spans the matrix's column
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
    s["presets"], s["temperament_tiles"] = True, False
    cells = {c.id for c in spreadsheet.build(base, s).cells}
    # the temperament + tuning choosers ride the domain-primes column (under the mapping matrix /
    # tuning map), so hiding the temperament takes each away with that column
    assert "preset:temperament" not in cells
    assert "preset:tuning" not in cells
    # but the target chooser rides the interval-vectors row's target tile, which now owns its own
    # toggle (interval_vectors) rather than the temperament's -- so it stays with the temperament hidden
    assert "preset:target" in cells


def test_target_preset_chooser_follows_the_interval_vectors_row():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["presets"], s["interval_vectors"] = True, False
    cells = {c.id for c in spreadsheet.build(base, s).cells}
    # the target chooser rides the (interval-vectors, targets) tile, so hiding that row takes it
    assert "preset:target" not in cells
    # ...while the temperament / tuning choosers (domain-primes column) are unaffected
    assert {"preset:temperament", "preset:tuning"} <= cells


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
                             ("preset:target", "target interval set scheme", "block:vec:targets")):
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
    # the <choose form> dropdowns DON'T get their own boxes (the user's rule): with presets on they
    # ride INSIDE the temperament chooser's box, below its dropdown + caption, each with a "form" label
    for fcid, tbox in (("formchooser:mapping", "block:preset:temperament"),
                       ("formchooser:comma_basis", "block:preset:temperament:commas")):
        assert f"block:{fcid}" not in boxes              # no separate box for the form chooser
        ctrl, box = cells[fcid], boxes[tbox]
        assert box.y <= ctrl.y and box.y + box.h >= ctrl.y + ctrl.h  # enclosed by the temperament box
        tdrop = cells[tbox.removeprefix("block:")]       # the temperament dropdown it sits under
        assert ctrl.y > tdrop.y                          # below the main chooser
        flbl = cells[f"{fcid}:label"]
        assert flbl.kind == "caption" and flbl.text == "form" and flbl.align == "left" and flbl.y > ctrl.y


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
                      ("block:preset:target", "block:vec:targets")):
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


def test_every_open_value_tile_has_a_plain_text_string():
    # The invariant that keeps the two views in lockstep: EVERY open value tile (a tile that renders
    # gridded numbers) carries a matching plain-text EBK band. A grid tile added without a service/text
    # entry shows numbers up top and a blank band below — the bug the generator-detempering and
    # superspace-projection columns hit. This sweeps the WHOLE surface with every Show toggle on so a
    # newly-added tile that forgets its plain text fails here, rather than slipping through to the user.
    from rtt.app.grid_tables import PTEXT_ROWS, SPINE_COLUMNS
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True  # every Show toggle on, to open the maximum set of tiles
    # a nonstandard-domain temperament (lights the chapter-9 superspace block) with held + interest +
    # projection, so the detempering / held / superspace / projection columns are all in play at once
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    assert b.show_superspace and b.show_ptext  # the config really did light the superspace + plain text
    value_rows = PTEXT_ROWS - {"quantities"}  # the quantities row's only band is the "2.3.5" primes string
    missing = [(r, c) for (r, c) in sorted(b.declared_tiles)
               if r in value_rows and c not in SPINE_COLUMNS and b.tile_open(r, c)
               and (r, c) not in b.ptext_strings]
    assert not missing, f"open value tiles with no plain-text band: {missing}"


def test_every_row_that_produces_plain_text_reserves_its_band():
    # the CONVERSE of the lockstep guard above, and the invariant the canonical-mapping row broke: a row
    # that PRODUCES a plain-text EBK string must RESERVE band height for it, or the text spills past the
    # bottom of the tile into the row below. ptext_band() is now CONTENT-FIRST — it reserves iff the row
    # appears in ptext_strings — so this asserts the real reservation (height > 0), not a proxy set
    # membership. Sweeping every Show toggle on (which surfaces the canon row via form_tiles) catches any
    # such row generically, before it reaches the user.
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    assert b.show_ptext and b.show_canon  # the config really did light the plain text + the canon row
    rows_with_text = {r for (r, _c) in b.ptext_strings}
    spill = sorted(r for r in rows_with_text if b.ptext_band(r, folded=False) <= 0)
    assert not spill, f"rows produce plain text but reserve no band (it will spill past the tile): {spill}"


def test_every_in_tile_band_reserves_for_what_it_emits():
    # The GENERALIZED tile-holds-its-content guard (chip task_75d713e3): a tile must reserve a band for
    # EVERY band whose content it emits, or that content spills past the tile. Each in-tile band pairs a
    # CONTENT source (what gets drawn) with a RESERVATION set/predicate (what the height pass reserves);
    # the canon-row spill was these two disagreeing for the plain-text band. This sweeps every Show toggle
    # on over a rich nonstandard-domain temperament and asserts, for every band, that the set of rows
    # EMITTING content is contained in the set of rows RESERVING it — so a future row that emits into a
    # band but is forgotten in its reservation set fails here, for ANY band, not just plain text.
    from rtt.app.grid_tables import (SYMBOLED_ROWS, UNITED_ROWS, CAPTIONED_ROWS,
                                     COL_LABELED_ROWS, SYMBOLS, UNITS)
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    # (band name, rows that EMIT its content, rows that RESERVE its height). The emit side reads the
    # LIVE per-render content where one exists (col_labels/effective_captions/ptext_strings are rebuilt
    # each render — exactly where drift hides), and the static content table otherwise.
    bands = {
        "plain text":   ({r for (r, _c) in b.ptext_strings},
                         {r for (r, _c) in b.ptext_strings if b.ptext_band(r, folded=False) > 0}),
        "symbol":       ({r for (r, _c) in SYMBOLS}, set(SYMBOLED_ROWS)),
        "units":        ({r for (r, _c) in UNITS}, set(UNITED_ROWS)),
        "caption":      ({r for (r, _c) in b.effective_captions}, set(CAPTIONED_ROWS)),
        "column label": ({r for (r, _c) in b.col_labels}, set(COL_LABELED_ROWS)),
    }
    spills = {name: sorted(emit - reserve) for name, (emit, reserve) in bands.items() if emit - reserve}
    assert not spills, f"rows emit a band's content but reserve no height for it (it will spill): {spills}"


def test_every_plain_text_band_shows_the_same_numbers_as_its_grid_tile():
    # The stronger half of the lockstep guard: a tile's plain-text band must show the SAME values as
    # its gridded cells — not merely exist (the test above). A band built from a different derivation
    # (the unlifted-vs-lifted / wrong-prescaler class of bug) would still have a band but disagree
    # cell-for-cell; this catches that. We compare the multiset of numeric tokens (ints, fractions,
    # decimals, em-dashes) the band emits against the multiset its grid cells carry — order-independent
    # (the band is column- or row-major by tile; bracket shape is asserted by the per-tile tests), so
    # this answers exactly "do the two views show the same numbers?". The shared DerivedQuantities makes
    # the tuning solve identical, so cents strings match to the digit.
    #
    # Two by-design view differences are normalised away first (they are NOT disagreements): the grid's
    # math-expression cells show the working AND the result ("1200 · log₂(15/13)\n= 247.741") while the
    # band shows only the result (247.741) — so for a cell carrying "=" we read only the part after it;
    # and the mapping band carries a leading domain-basis prefix ("2.3.13/5 [⟨…") the value cells don't,
    # so the band is tokenised from its first EBK bracket on.
    import re
    from rtt.app.grid_tables import PTEXT_ROWS, SPINE_COLUMNS
    TOKEN = re.compile(r"—|-?\d+\.\d+|-?\d+/\d+|-?\d+")  # decimal before fraction before int

    def cell_value(text):  # a math-expression cell shows "<working>\n= <result>"; take the result
        return text.rsplit("=", 1)[-1] if "=" in text else text

    def band_body(text):  # drop a leading domain-basis prefix ("2.3.13/5 ") before the first bracket
        i = min((text.find(ch) for ch in "[⟨{" if ch in text), default=0)
        return text[i:]

    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    lay = b.layout()
    value_rows = PTEXT_ROWS - {"quantities"}
    mismatches = []
    checked = 0
    for (rkey, ckey) in sorted(b.declared_tiles):
        if rkey not in value_rows or ckey in SPINE_COLUMNS or not b.tile_open(rkey, ckey):
            continue
        if (rkey, ckey) not in b.ptext_strings:
            continue  # the presence test owns that failure
        # the VALUE region of the tile only — the column's x-span × the row's value-area height
        # (rows[rkey].y .. +h). NOT panel_rect, which spans the whole tile stack (symbol / caption /
        # plain-text band / any overlapping control box) and would pull in the band itself and stray
        # box values. Brackets / matlabels inside the value band carry no ascii-digit tokens.
        rb, cx, cw = b.rows[rkey], b.col_x[ckey], b.col_w[ckey]
        grid_tokens = []
        for c in lay.cells:
            if (c.text and not c.id.startswith("ptext:")
                    and cx - 2 <= c.x <= cx + cw and rb.y - 2 <= c.y <= rb.y + rb.h + 2):
                grid_tokens += TOKEN.findall(cell_value(c.text))
        band_tokens = TOKEN.findall(band_body(b.ptext_strings[(rkey, ckey)]))
        if sorted(grid_tokens) != sorted(band_tokens):
            mismatches.append((rkey, ckey, sorted(band_tokens), sorted(grid_tokens)))
        checked += 1
    assert checked >= 60, f"config did not light enough value tiles ({checked})"
    assert not mismatches, "plain text disagrees with the grid:\n" + "\n".join(
        f"  {r}/{c}: band={bt} grid={gt}" for r, c, bt, gt in mismatches)


# ── the EBK BRACKET-convention lockstep guard ────────────────────────────────────────────────
# The two guards above check that the two views EXIST and show the same NUMBERS. This third one
# closes the remaining gap the same way for the bracket NOTATION: a tile declares its EBK variance
# (vector-list ⟩ / genmap-coord } / covector-stack ⟨…] / …) independently in spreadsheet.py (the
# frame + marks drawn around the grid) and in service/text.py (the plain-text band), and nothing
# forced the two to agree — a tile could read { … ] in the grid but [ … ⟩ in the band. This test
# reconstructs each view's convention and asserts they match, so a future tile (or an edit) that
# lets the two drift fails here rather than reaching the user.
_EBK_OPEN, _EBK_CLOSE = "[⟨{", "]⟩}"


def _ebk_text_convention(text):
    """The bracket convention a plain-text EBK band declares, as
    ``(structure, outer_open, outer_close, inner_open, inner_close)`` — structure ∈
    ``stack`` (covector stack), ``list`` (vector list / kets), ``row`` (single line), ``none``."""
    i = min((text.find(ch) for ch in _EBK_OPEN if ch in text), default=-1)
    if i == -1:
        return ("none", "", "", "", "")  # the quantities "2.3.5" primes string carries no EBK bracket
    s = text[i:]  # drop a leading domain-basis prefix ("2.3.13/5 ") before the first bracket
    groups, depth, start = [], 0, 0
    for j, c in enumerate(s):  # the top-level bracket groups (a no-wrap list has more than one)
        if c in _EBK_OPEN:
            if depth == 0:
                start = j
            depth += 1
        elif c in _EBK_CLOSE:
            depth -= 1
            if depth == 0:
                groups.append(s[start:j + 1])
    multi = len(groups) > 1
    g = groups[0]
    inner = g[1:-1].strip()
    if inner and inner[0] in _EBK_OPEN:  # wraps sub-items: a vector list (kets) or a covector stack
        io, depth, ic = inner[0], 0, ""
        for c in inner:  # this first sub-item's close char
            depth += c in _EBK_OPEN
            depth -= c in _EBK_CLOSE
            if depth == 0 and c in _EBK_CLOSE:
                ic = c
                break
        structure = "list" if io == "[" else "stack"
        return (structure, "", "", io, ic) if multi else (structure, g[0], g[-1], io, ic)
    if multi:  # bare standalone kets, space-separated (the intervals-of-interest column)
        return ("list", "", "", "[", g[-1])
    return ("row", g[0], g[-1], "", "")  # one bare group: a scalar list / map / genmap / lone ket


def _ebk_grid_convention(b, lay, rkey, ckey):
    """The bracket convention the GRID draws around a tile's cells, reconstructed from its frame
    bands (matrix_frame's ebktop/ebkbrace/ebkangle), per-column ket marks and bracket glyphs.
    Cell-id shape disambiguates: a per-column mark / per-row stacked bracket ends in ``:<int>``,
    a spanning matrix_frame band or an outer list wrap does not."""
    cx, cw = b.col_x[ckey], b.col_w[ckey]

    def in_tile(c):  # x-centre inside the column, and this row is the nearest row band
        if not (cx - 2 <= c.x + c.w / 2 <= cx + cw + 2):
            return False
        ccy = c.y + c.h / 2
        return min(b.rows, key=lambda k: abs(b.rows[k].y + b.rows[k].h / 2 - ccy)) == rkey

    frame_top = col_marks = False
    brace = angle = False
    outer, perrow = [], []
    for c in lay.cells:
        if not in_tile(c):
            continue
        digit = c.id.rsplit(":", 1)[-1].isdigit()
        if c.id.startswith("ebktop:"):
            col_marks |= digit  # ebktop:<name>:<c> is a per-column mark; ebktop:<bid> a frame band
            frame_top |= not digit
        elif c.id.startswith("ebkbrace:"):
            col_marks |= digit
            brace = True
        elif c.id.startswith("ebkangle:"):
            col_marks |= digit
            angle = True
        elif c.id.startswith("bracket:") and c.id.endswith(":l"):
            base = c.id[:-2]
            if base.rsplit(":", 1)[-1].isdigit():  # bracket:<bid>:<i>:l is a per-row stacked bracket
                perrow.append(c.text)
            else:  # bracket:<bid>:l is an outer (single-row or list-wrap) bracket
                r = next((x for x in lay.cells if x.id == base + ":r"), None)
                outer.append((c.text, r.text if r else "]"))
    foot = "}" if brace else "⟩" if angle else ""
    if frame_top:  # matrix_frame present ⇒ a covector / genmap stack (top bar + foot + per-row brackets)
        io = sorted(set(perrow))[0] if perrow else "⟨"
        return ("stack", "[", foot, io, "]")
    if col_marks:  # per-column ket marks ⇒ a vector list
        if outer:
            oo, oc = sorted(outer)[0]
            return ("list", oo, oc, "[", foot)
        return ("list", "", "", "[", foot)  # interest: standalone kets, no outer wrap
    if outer:  # a lone bracket pair ⇒ a single-row map / genmap / scalar list
        oo, oc = sorted(outer)[0]
        return ("row", oo, oc, "", "")
    return ("none", "", "", "", "")


def _ebk_canonical(conv):
    """Fold the one harmless ambiguity away before comparing: a single ket (a no-wrap list of one
    interval, ``[…⟩`` / ``[…}``) reads as a bare ``row`` by the close char but IS a 1-item list."""
    structure, oo, oc, io, ic = conv
    if structure == "row" and oo == "[" and oc in "⟩}":
        return ("list", "", "", "[", oc)
    return conv


def test_every_plain_text_band_uses_the_same_brackets_as_its_grid_tile():
    # The bracket-notation half of the lockstep guard (numbers are covered by the test above). The
    # grid frame (spreadsheet.py) and the plain-text band (service/text.py) each declare a tile's
    # EBK variance independently; this asserts the two declarations agree for every open value tile,
    # so the views can't read e.g. { … ] in the grid and [ … ⟩ in the band. Same all-on /
    # nonstandard-domain + held + interest + projection config the two guards above use, so the
    # whole surface (detempering / held / superspace / projection columns) is in play at once.
    from rtt.app.grid_tables import PTEXT_ROWS, SPINE_COLUMNS
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    lay = b.layout()
    value_rows = PTEXT_ROWS - {"quantities"}
    mismatches, checked = [], 0
    for (rkey, ckey) in sorted(b.declared_tiles):
        if rkey not in value_rows or ckey in SPINE_COLUMNS or not b.tile_open(rkey, ckey):
            continue
        if (rkey, ckey) not in b.ptext_strings:
            continue  # presence is the other guard's job
        text_conv = _ebk_canonical(_ebk_text_convention(b.ptext_strings[(rkey, ckey)]))
        grid_conv = _ebk_canonical(_ebk_grid_convention(b, lay, rkey, ckey))
        if text_conv != grid_conv:
            mismatches.append((rkey, ckey, text_conv, grid_conv, b.ptext_strings[(rkey, ckey)]))
        checked += 1
    assert checked >= 60, f"config did not light enough value tiles ({checked})"
    assert not mismatches, "grid and plain-text EBK brackets disagree:\n" + "\n".join(
        f"  {r}/{c}: band={t} grid={g}  ({txt!r})" for r, c, t, g, txt in mismatches)


def _ebk_table_canonical(conv):
    """Reduce an EBK_CONVENTIONS row to the 5-tuple the band parser yields: drop the (text-only)
    separator, and fold a bracket-less ``row`` to ``none`` (a bare scalar list reads as ``none``)."""
    structure, oo, oc, io, ic, _sep = conv
    if structure == "row" and not oo and not oc:
        return ("none", "", "", "", "")
    return (structure, oo, oc, io, ic)


def test_every_open_value_tile_declares_an_ebk_convention():
    # The single-source-of-truth guard: the plain-text band is now BUILT from the per-tile
    # EBK_CONVENTIONS table (service/text.render_ebk owns every bracket), and the grid frame is held
    # to it by the grid↔band guard above. This pins both views to the table: every open value tile
    # must declare a convention there, and its rendered band must match what it declared — so a new
    # tile can't ship without a convention, and can't drift from the one it names.
    from rtt.app.grid_tables import PTEXT_ROWS, SPINE_COLUMNS
    from rtt.app.service.text import ebk_convention, EBK_CONVENTIONS
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    b = spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                 held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))
    value_rows = PTEXT_ROWS - {"quantities"}
    undeclared, mismatches, checked = [], [], 0
    for (rkey, ckey) in sorted(b.declared_tiles):
        if rkey not in value_rows or ckey in SPINE_COLUMNS or not b.tile_open(rkey, ckey):
            continue
        if (rkey, ckey) not in b.ptext_strings:
            continue
        if (rkey, ckey) not in EBK_CONVENTIONS and (rkey, ckey) != ("prescaling", "primes"):
            undeclared.append((rkey, ckey))
            continue
        declared = _ebk_table_canonical(ebk_convention(rkey, ckey, superspace=b.show_superspace))
        rendered = _ebk_canonical(_ebk_text_convention(b.ptext_strings[(rkey, ckey)]))
        if declared != rendered:
            mismatches.append((rkey, ckey, declared, rendered, b.ptext_strings[(rkey, ckey)]))
        checked += 1
    assert checked >= 60, f"config did not light enough value tiles ({checked})"
    assert not undeclared, f"open value tiles with no EBK_CONVENTIONS entry: {undeclared}"
    assert not mismatches, "rendered band disagrees with its declared EBK convention:\n" + "\n".join(
        f"  {r}/{c}: declared={d} rendered={g}  ({txt!r})" for r, c, d, g, txt in mismatches)


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
    # the interval-ratios row title is forced onto two lines ("interval\nratios") so it reads as a
    # two-line title matching "interval vectors" below it, rather than sitting on one line
    assert cells["label:quantities"].text == "interval\nratios"
    assert "toggle:row:vectors" in cells  # collapsible like the other content rows
    assert cells["label:quantities"].y < cells["label:vectors"].y < cells["label:mapping"].y


def test_interval_vectors_show_targets_as_vectors():
    cells = {c.id: c for c in _layout().cells}
    # each target interval as a d-tall vector column: 2/1->[1,0,0], 3/2->[-1,1,0], 5/4->[-2,0,1]
    assert [cells[f"cell:vec:targets:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:vec:targets:2:{p}"].text for p in range(3)] == ["-1", "1", "0"]
    assert [cells[f"cell:vec:targets:6:{p}"].text for p in range(3)] == ["-2", "0", "1"]
    # the editable vector cell is inset within its COL_W slot (leaving the separator rule a gap),
    # so it shares the ratio header's column AXIS by centre, not by left edge
    v, hdr = cells["cell:vec:targets:2:0"], cells["target:2"]
    assert v.x + v.w / 2 == hdr.x + hdr.w / 2  # column centred on its target axis
    # the d components stack downward, one ROW_H apart
    assert cells["cell:vec:targets:0:1"].y - cells["cell:vec:targets:0:0"].y == spreadsheet.ROW_H


def test_interval_vectors_domain_primes_identity_renders_with_identity_objects():
    # 𝑀ⱼ = 𝐼: the domain primes as vectors over themselves form the d × d identity (the p/p JI
    # mapping) — an identity object shown when identity_objects is on. A covector stack ⟨ … ] over
    # the primes column, each row labelled 𝒎ⱼᵢ, closing with the angle ⟩ (an operator, like P) —
    # the on-domain twin of the superspace M_jL.
    J = spreadsheet.SUB_OPEN + "j" + spreadsheet.SUB_CLOSE  # <sub>j</sub> (a tight j, not raw U+2C7C)
    cells = {c.id: c for c in _with(identity_objects=True, names=True, symbols=True,
                                    header_symbols=True, equivalences=True,
                                    plain_text_values=True).cells}
    for i in range(3):  # d = 3
        for k in range(3):
            assert cells[f"cell:vec:primes:{i}:{k}"].text == ("1" if i == k else "0")
            assert cells[f"cell:vec:primes:{i}:{k}"].kind == "mapped"
    assert cells["symbol:vectors:primes"].text == f"\U0001D440{J} = \U0001D43C"  # 𝑀ⱼ = 𝐼
    assert cells["caption:vectors:primes"].text == "JI mapping"
    assert cells["matlabel:row:vectors:primes:0"].text == f"\U0001D48E{J}₁"  # 𝒎ⱼ₁
    assert cells["ebktop:vec:primes"].kind == "ebktop"
    assert cells["ebkangle:vec:primes"].kind == "ebkangle"  # the outer ⟩ foot (operator, not the } of M)
    assert cells["bracket:vec:primes:0:l"].text == spreadsheet.MAP_BRACKETS[0]
    assert cells["ptext:vectors:primes"].text == "[⟨1 0 0]⟨0 1 0]⟨0 0 1]⟩"


def test_interval_vectors_domain_primes_identity_gated_off_by_default():
    # off by default: the primes column carries NOTHING at the interval-vectors row — no cells,
    # ket marks, the enclosing bracket, fold toggle or caption.
    cells = {c.id for c in _with(names=True).cells}
    assert not any(c.startswith(("cell:vec:primes", "ebktop:vec:primes",
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
                            {**settings.defaults(), "symbols": True, "header_symbols": True, "drag_to_combine": True})
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
                            {**settings.defaults(), "symbols": True, "header_symbols": True, "drag_to_combine": True},
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


def test_the_size_sensitizing_row_is_labelled_z_not_a_fourth_prime():
    # the bottom (size-sensitizing) row of 𝑋 = 𝑍𝐿 is labelled 𝒛 (the size-sensitizing matrix 𝑍's row
    # variable, §10), NOT 𝒍₄ / 𝒙₄ — it isn't a fourth prime. The d real prime rows keep their 𝒍ᵢ.
    lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, header_symbols=True).cells}
    assert lils["matlabel:row:prescaling:primes:0"].text == "𝒍₁"
    assert lils["matlabel:row:prescaling:primes:2"].text == "𝒍₃"
    assert lils["matlabel:row:prescaling:primes:3"].text == "𝒛"  # the size row — not 𝒍₄
    # a square (no size factor) prescaler has only the d prime rows, all 𝒍ᵢ (no 𝒛 row)
    lp = {c.id: c for c in _with("minimax-S", weighting=True, symbols=True, header_symbols=True).cells}
    assert lp["matlabel:row:prescaling:primes:2"].text == "𝒍₃"
    assert "matlabel:row:prescaling:primes:3" not in lp


def test_size_factor_composes_the_size_sensitizing_matrix_with_each_base_prescaler():
    # "replace diminuator" (the size factor) composes the size-sensitizing matrix 𝑍 with the base
    # prescaler — 𝑋 = 𝑍𝐿 (log-prime), 𝑋 = 𝑍 (identity: 𝑍𝐼 vaporizes), 𝑋 = 𝑍·diag(𝒑) (prime; the ·
    # keeps "𝑍diag" from reading as one word) — per the guide's ch8 table, and the NAME spells it out.
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))

    def labels(scheme):
        s = settings.defaults()
        s.update(weighting=True, symbols=True, equivalences=True, names=True, alt_complexity=True)
        cells = {c.id: c for c in spreadsheet.build(st, s, tuning_scheme=scheme).cells}
        return cells["symbol:prescaling:primes"].text, cells["caption:prescaling:primes"].text

    identity = service.scheme_with_diminuator(service.scheme_with_complexity("minimax-S", "copfr"), True)
    prime = service.scheme_with_diminuator(service.scheme_with_complexity("minimax-S", "sopfr"), True)
    assert labels("minimax-lils-S") == (
        "𝑋 = 𝑍𝐿", "complexity pretransformer = size-sensitizing matrix × log-prime matrix")
    assert labels(identity) == (
        "𝑋 = 𝑍", "complexity pretransformer = size-sensitizing matrix")
    assert labels(prime) == (
        "𝑋 = 𝑍·diag(𝒑)", "complexity pretransformer = size-sensitizing matrix × diagonal matrix of primes")
    # without the size factor the base prescaler stands alone (existing behavior, unchanged)
    s = settings.defaults()
    s.update(weighting=True, symbols=True, equivalences=True, names=True)
    lp = {c.id: c for c in spreadsheet.build(st, s, tuning_scheme="minimax-S").cells}
    assert lp["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
    assert lp["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"


def test_the_size_factor_drops_the_diag_complexity_equivalence():
    # the lils complexity is ‖𝑍𝐿·i‖ (the size row doubles each prime), NOT diag(𝐿) — so the size factor
    # drops the "𝒄 = diag(𝐿)" closed form, leaving the bare 𝒄 (a plain diagonal lp prescaler keeps it).
    lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, equivalences=True).cells}
    assert lils["symbol:complexity:targets"].text == "𝒄"            # no " = diag(𝐿)"
    lp = {c.id: c for c in _with("minimax-S", weighting=True, symbols=True, equivalences=True).cells}
    assert lp["symbol:complexity:targets"].text == "𝒄 = diag(𝐿)"    # the plain diagonal keeps it


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
    # editable prescalercell — the user types overrides here), 0 off it (a plain tuning value since
    # 𝐿 is diagonal, no point editing what's pinned to zero).
    assert on["cell:prescaling:primes:0:0"].kind == "prescalercell"
    assert on["cell:prescaling:primes:0:0"].text == "1"               # log2(2) = 1, shown bare
    assert on["cell:prescaling:primes:1:1"].text == service.cents(pre[1])  # log2(3) = 1.585
    assert on["cell:prescaling:primes:2:2"].text == service.cents(pre[2])  # log2(5) = 2.322
    assert on["cell:prescaling:primes:0:1"].kind == "tuningvalue"             # off-diagonal stays tuning value
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
    # lils grows row d (= 3): every entry is sf·𝐿_c = the log-prime, a derived (non-editable) tuning value
    for c in range(3):
        assert lils[f"cell:prescaling:primes:3:{c}"].text == service.prescale_text(pre[c])
        assert lils[f"cell:prescaling:primes:3:{c}"].kind == "tuningvalue"
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
    lils_sym = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, symbols=True, header_symbols=True).cells}
    pre = service.complexity_prescaler(mapping, "TILT minimax-S")
    comma = service.from_mapping(mapping).comma_basis[0]      # the syntonic comma vector
    # the comma product tile 𝑋C grows the size row: sf·Σ(𝐿ⱼ·commaⱼ) = sf · the comma's log size
    expected = service.prescale_text(sum(pre[j] * comma[j] for j in range(3)))
    assert lils["cell:prescaling:commas:3:0"].text == expected
    assert lils["cell:prescaling:commas:3:0"].kind == "tuningvalue"
    # the bare matrix's size row carries the 𝒛 row label (the size-sensitizing row, not a 4th prime 𝒍₄)
    assert lils_sym["matlabel:row:prescaling:primes:3"].text == "𝒛"


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
    # size-sensitized form), not 𝑋 = 𝐿 (the square diagonal); and the NAME spells the composition out
    # (here on the all-interval-OFF TILT scheme — the rectangular 𝑍𝐿 with no phantom column).
    lils = {c.id: c for c in _with(scheme="TILT minimax-lils-S", weighting=True,
                                   symbols=True, names=True, equivalences=True).cells}
    assert lils["symbol:prescaling:primes"].text == "𝑋 = 𝑍𝐿"
    # the size factor also renames "prescaler" → "pretransformer" (the guide's term for rectangular 𝑋)
    assert lils["caption:prescaling:primes"].text == "complexity pretransformer = size-sensitizing matrix × log-prime matrix"
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
    s = {**settings.defaults(), "symbols": True, "header_symbols": True, "weighting": True,
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
    # WITHOUT alt complexity, only the diagonal is editable; the off-diagonal stays a 0 tuning value
    off = {c.id: c for c in spreadsheet.build(
        base, {**settings.defaults(), "weighting": True, "alt_complexity": False},
        tuning_scheme="TILT minimax-S").cells}
    assert off["cell:prescaling:primes:1:1"].kind == "prescalercell"
    assert off["cell:prescaling:primes:0:1"].kind == "tuningvalue"


def test_custom_prescaler_diagonal_keeps_the_generic_symbol():
    # typing a custom prescaler diagonal makes it no longer THE log-prime matrix, so the symbol
    # stays the generic 𝑋 everywhere (no 𝐿 promotion, no "= log-prime matrix") — the typed
    # diagonal speaks for itself, so the bare tile prints no equivalence.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "symbols": True, "header_symbols": True, "equivalences": True,
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
        assert cell.kind == "tuningvalue"
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
    # slope picks the letter — U (unity) / C (complexity) / S (simplicity) — an Euclidean (q=2)
    # complexity norm prefixes E, and a named alternative complexity slots its family in. Damage
    # is the ¢-prefixed weighted-cents form, the weight the bare parenthetical, the complexity its
    # own slope-free code (the "C" position). All three renderings agree: the per-box "units:"
    # line, the per-cell unit, and the units-column spine.
    # (scheme, damage, weight, complexity); complexity is None when its row is hidden (unity weight).
    cases = [
        ("TILT minimax-U", "¢(U)", "(U)", None),       # unity-weight: no complexity, the row is hidden
        ("TILT minimax-C", "¢(C)", "(C)", "(C)"),      # complexity-weight, taxicab
        ("TILT minimax-S", "¢(S)", "(S)", "(C)"),      # simplicity-weight, taxicab
        ("TILT minimax-EC", "¢(EC)", "(EC)", "(EC)"),  # complexity-weight, Euclidean
        ("TILT minimax-ES", "¢(ES)", "(ES)", "(EC)"),  # simplicity-weight, Euclidean: weight (ES), complexity (EC)
        # alternative complexities slot the family in (E prefixes the family, not the slope):
        ("TILT minimax-sopfr-S", "¢(sopfr-S)", "(sopfr-S)", "(sopfr-C)"),            # sopfr, taxicab
        ("TILT minimax-E-sopfr-S", "¢(E-sopfr-S)", "(E-sopfr-S)", "(E-sopfr-C)"),    # sopfr, Euclidean
        ("TILT minimax-copfr-C", "¢(copfr-C)", "(copfr-C)", "(copfr-C)"),            # copfr, complexity-weight
        ("TILT minimax-lils-S", "¢(lils-S)", "(lils-S)", "(lils-C)"),                # lils (size factor)
    ]
    for scheme, damage, weight, complexity in cases:
        cells = {c.id: c for c in _with(scheme, weighting=True, units=True, cell_units=True, domain_units=True).cells}
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
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, symbols=True, header_symbols=True).cells}  # non-unity slope reveals the prescaling row
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
    # exists only while weighting is on; the temperament tiles own the primes column it sits in.
    off = {c.id for c in _with("TILT minimax-S", weighting=True, presets=False).cells}  # non-unity slope reveals the prescaling tile
    lay = _with("TILT minimax-S", weighting=True, presets=True)
    on = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    assert "preset:prescaler" not in off  # no chooser unless presets is on
    sel = on["preset:prescaler"]
    # with alt. complexity off there is only one prescaler (log-prime), so the chooser has no real
    # choice: it renders as a DISABLED dropdown (greyed), not an interactive one
    assert sel.kind == "preset"
    assert sel.disabled is True
    assert sel.text == "log-prime"  # the default scheme's prescaler
    # it rides below the prescaling matrix, one inner pad into its tile-spanning box, which spans the
    # primes column (NOT keyed off the header — that now centres over the matrix once the ET-picker
    # right gutter is balanced by an equal left pad)
    pre = on["cell:prescaling:primes:2:2"]
    box = blocks["block:preset:prescaler"]
    assert sel.y > pre.y
    assert sel.x == box.x + spreadsheet.BOX_INNER  # one inner pad into the box
    assert box.x <= pre.x and pre.x + pre.w <= box.x + box.w  # the box spans the prescaler's column
    # gone without the prescaling tile (weighting off) or its column (temperament tiles off)
    assert "preset:prescaler" not in {c.id for c in _with(weighting=False, presets=True).cells}
    assert "preset:prescaler" not in {
        c.id for c in _with(weighting=True, presets=True, temperament_tiles=False).cells}


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
    # and the box never grows by dropping the dropdown. Whether the targets column actually narrows
    # depends on cell size: at COL_W the column is wide enough to contain box 𝒄 either way, so its
    # width is column-floored — the released dropdown reservation shows in 𝑞's leftward shift above.
    off_box = {b.id: b for b in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
    on_box = {b.id: b for b in spreadsheet.build(base, {**s, "presets": True}, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
    assert off_box.w <= on_box.w


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


def test_gridded_values_off_hides_the_nonstandard_domain_element_cells_and_controls():
    # With the nonstandard-domain box ON the domain basis is editable, so its quantities-row /
    # spine cells render as elementcell/elementratio (not the read-only "prime") and carry per-
    # element ± controls (element_minus/element_plus, not the plain minus/plus walk). Those kinds
    # were overlooked in GRIDDED_KINDS, so gridded-off used to leave them floating while the rest
    # of the row/column collapsed. They must now collapse with everything else. The projection P/G
    # grids (read-only "mapped" cells, cell:proj:*/cell:embed:*) ride along to confirm gridded-off
    # still hides them too — they were already gridded, this guards against regressing that.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # genuinely nonstandard (13/5)
    s = {**settings.defaults(), "nonstandard_domain": True, "projection": True}
    on = {c.id: c for c in spreadsheet.build(state, {**s, "gridded_values": True}).cells}
    off = {c.id for c in spreadsheet.build(state, {**s, "gridded_values": False}).cells}
    # sanity: the scenario really builds the editable domain cells (a prime as elementcell, the
    # 13/5 element as a stacked elementratio), the per-element controls, and the P/G grids
    assert on["prime:0"].kind == "elementcell" and on["prime:2"].kind == "elementratio"
    assert on["basis:0"].kind == "elementcell" and on["basis_plus"].kind == "element_plus"
    domain_value_ids = {"prime:0", "prime:1", "prime:2", "basis:0", "basis:1", "basis:2"}
    domain_control_ids = {"element_minus:0", "element_minus:1", "element_minus:2",
                          "element_minus:basis:0", "element_minus:basis:1", "element_minus:basis:2",
                          "element_plus", "basis_plus"}
    proj_grid_ids = {c for c in on if c.startswith(("cell:proj:", "cell:embed:"))}
    assert proj_grid_ids and all(on[c].kind == "mapped" for c in proj_grid_ids)
    assert domain_value_ids <= on.keys() and domain_control_ids <= on.keys()
    # gridded off: every one of those is gone (only captions/tile boxes/plain-text survive)
    assert not (domain_value_ids & off)
    assert not (domain_control_ids & off)
    assert not (proj_grid_ids & off)


def test_gridded_values_off_hides_the_editable_unchanged_basis_cells():
    # The editable unchanged basis U (the U half of the consolidated V = C|U view, rendered as
    # "unchangedcell" when the tuning is a full rational projection — meantone fully held by 2/1
    # and 5/4) was also missing from GRIDDED_KINDS, so it leaked when gridded-off. (The read-only
    # dashed form "vec" was already filtered; only the editable kind was overlooked.) It must hide.
    mt = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "projection": True}
    on = {c.id: c for c in spreadsheet.build(mt, {**s, "gridded_values": True}, held_basis_ratios=("2/1", "5/4")).cells}
    off = {c.id for c in spreadsheet.build(mt, {**s, "gridded_values": False}, held_basis_ratios=("2/1", "5/4")).cells}
    unchanged_ids = {c for c in on if c.startswith("cell:unchanged:")}
    assert unchanged_ids and all(on[c].kind == "unchangedcell" for c in unchanged_ids)  # really editable here
    assert not (unchanged_ids & off)  # gridded off collapses them with the comma cells beside them


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


def test_all_interval_removes_the_superspace_target_lifts_too():
    # the chapter-9 superspace rows were added AFTER the collapse above, so they must register with
    # it too: over Tₚ = I the target lifts re-express their domain-prime tiles — the target vectors
    # T_L → B_L (the (ss_vectors, primes) tile) and the mapped targets Y_L → M_s→L (the
    # (ss_mapping, primes) tile) — so both drop, leaving the target column wiped from the mapping row
    # down to the complexity row with no stray superspace tiles floating in the gap. Their
    # non-duplicate prime-column counterparts (B_L, M_s→L) survive.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # BARBADOS: dL = 4 superspace
    def blocks(scheme):
        s = settings.defaults()
        s["nonstandard_domain"], s["weighting"] = True, True  # show the superspace; reveal prescaling/complexity
        return {b.id for b in spreadsheet.build(state, s, tuning_scheme=scheme).blocks}
    based, allint = blocks("TILT minimax-S"), blocks("minimax-S")
    for bid in ("block:ss_vectors:targets", "block:ss_mapping:targets"):
        assert bid in based, bid       # the superspace target lifts show when target-based
        assert bid not in allint, bid  # and drop (panel and all) when all-interval
    assert {"block:ss_vectors:primes", "block:ss_mapping:primes"} <= allint  # B_L / M_s→L survive


def test_all_interval_relabels_the_optimization_mean_damage():
    # the optimization mean damage ⟪𝐝⟫ₚ is the minimized total damage; all-interval it relabels to the
    # retuning magnitude over the retuning map 𝒓𝐿⁻¹ at the dual norm power. The DISPLAYED VALUE is the
    # dual-power MEAN (_power_mean, ÷d — see test_..._aggregates_at_the_dual_norm_power below), so the
    # symbol must wear the double-angle power-MEAN brackets ⟪…⟫ — NOT the single-bar NORM ‖…‖, which
    # omits the /d and reads √d too large for that value (and for the damage chart's ⟪𝐝⟫ line). The
    # dual(q) subscript is PLAIN (SUB_*) so "dual" stays upright and only the math-italic 𝑞 slants.
    based = {c.id: c for c in _with(scheme="TILT minimax-S", optimization=True).cells}
    assert based["optimization:mean_damage:symbol"].text == "⟪𝐝⟫ₚ"
    allint = {c.id: c for c in _with(scheme="minimax-S", optimization=True).cells}
    expected = "⟪𝒓𝐿⁻¹⟫" + spreadsheet.SUB_OPEN + "dual(𝑞)" + spreadsheet.SUB_CLOSE
    assert allint["optimization:mean_damage:symbol"].text == expected
    # the symbol denotes the SAME quantity as the value it labels: a power-MEAN (double-angle), not a
    # norm (single bars). Guards the off-by-√d mean/norm confusion (tuning-core-6).
    assert "⟪" in expected and "⟫" in expected and "‖" not in expected


def test_optimization_mean_damage_carries_a_label_caption():
    # the mean damage gains a caption under its symbol, mirroring the power's "optimization power":
    # target-based it is the Lp "power mean" of the target damages; all-interval that quantity is
    # the "retuning magnitude" (the ⟪𝒓𝐿⁻¹⟫ relabel). The wide all-interval label does not fit on
    # one line in the min-width box, so it wraps to two lines (centred under the value cell, like
    # the q/dual captions) and the box reserves the extra caption line.
    based = _with(scheme="TILT minimax-S", optimization=True)
    allint = _with(scheme="minimax-S", optimization=True)
    on_based = {c.id: c for c in based.cells}
    on_allint = {c.id: c for c in allint.cells}
    assert on_based["optimization:mean_damage:caption"].text == "power mean"
    assert on_allint["optimization:mean_damage:caption"].text == "retuning magnitude"
    # it sits below the symbol and stays centred on the mean damage value cell (the power's stack)
    cap = on_based["optimization:mean_damage:caption"]
    mean_damage = on_based["optimization:mean_damage"]
    sym = on_based["optimization:mean_damage:symbol"]
    assert cap.y > sym.y
    assert abs((cap.x + cap.w / 2) - (mean_damage.x + mean_damage.w / 2)) < 0.5
    # target-based the short label is one line; all-interval the wide label reserves two, so the
    # box (and thus the damage tile) grows by exactly that extra line
    assert on_based["optimization:mean_damage:caption"].h == spreadsheet.CAPTION_LINE
    assert on_allint["optimization:mean_damage:caption"].h == 2 * spreadsheet.CAPTION_LINE
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


def test_optimized_tuning_wraps_the_mean_damage_symbol_in_min():
    # mockup: "make ⟪𝐝⟫ₚ into min(⟪𝐝⟫ₚ)". When the displayed tuning sits at the scheme's optimum,
    # the mean damage value IS the minimized one, so its symbol wraps in min(...); a deviating (hand-
    # edited) tuning shows the bare symbol — the displayed value is no longer the minimum.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True

    def symbol(scheme, optimized):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
        return cells["optimization:mean_damage:symbol"].text

    assert symbol("TILT minimax-S", True) == "min(⟪𝐝⟫ₚ)"
    assert symbol("TILT minimax-S", False) == "⟪𝐝⟫ₚ"
    # all-interval: the retuning-magnitude relabel (double-angle power-MEAN ⟪…⟫, not a norm) wraps in
    # min() the same way
    inner = "⟪𝒓𝐿⁻¹⟫" + spreadsheet.SUB_OPEN + "dual(𝑞)" + spreadsheet.SUB_CLOSE
    assert symbol("minimax-S", True) == "min(" + inner + ")"
    assert symbol("minimax-S", False) == inner


def test_minimized_mean_damage_prefixes_its_label_with_minimized():
    # when the displayed tuning is optimized (the symbol wraps in min()), the value shown IS the
    # minimized mean damage, so its label is prefixed "minimized": "minimized power mean", or
    # "minimized retuning magnitude" all-interval. A deviating tuning drops the prefix. The extra
    # word wraps to its own line, so the caption band — and the box — reserves it.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True

    def cap(scheme, optimized):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=optimized).cells}
        return cells["optimization:mean_damage:caption"]

    assert cap("TILT minimax-S", True).text == "minimized power mean"
    assert cap("TILT minimax-S", False).text == "power mean"
    assert cap("minimax-S", True).text == "minimized retuning magnitude"
    assert cap("minimax-S", False).text == "retuning magnitude"
    # the reserved caption band grows by the wrapped "minimized" line
    assert cap("TILT minimax-S", True).h == 2 * spreadsheet.CAPTION_LINE   # "minimized" / "power mean"
    assert cap("TILT minimax-S", False).h == spreadsheet.CAPTION_LINE      # "power mean"
    assert cap("minimax-S", True).h == 3 * spreadsheet.CAPTION_LINE         # + "retuning" / "magnitude"
    assert cap("minimax-S", False).h == 2 * spreadsheet.CAPTION_LINE


def test_all_interval_mean_damage_aggregates_at_the_dual_norm_power_not_infinity():
    # the all-interval mean damage is computed at the DUAL of the complexity norm power — the power the
    # optimizer actually minimized at (it minimaxes over every interval, which by duality is an
    # optimization over the primes at dual(𝑞)) — NOT the ∞ the 𝑝 cell shows. For a Euclidean (ES)
    # scheme dual(𝑞)=2, so the mean damage is the RMS of the per-prime weighted damages, not their max:
    # the value must equal tuning.get_tuning_map_mean_damage, the optimizer's own minimized quantity.
    import pytest
    from rtt.library import tuning
    from rtt.library.parsing import parse_temperament_data

    s = settings.defaults()
    s["optimization"] = True
    base = service.from_mapping(((1, 0, -4), (0, 1, 4)))  # meantone
    t = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")

    def mean_damage(scheme):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=True).cells}
        return float(cells["optimization:mean_damage"].text)

    # minimax-ES: per-prime weighted damages [1.397, 2.214, 0.811]; the bug showed their MAX
    # (2.214 — the ∞ aggregate), the fix shows their RMS (1.582 — the dual(𝑞)=2 aggregate)
    es = mean_damage("minimax-ES")
    assert es == pytest.approx(1.582, abs=1e-3)   # the dual-power mean (RMS)
    assert es != pytest.approx(2.214, abs=1e-2)   # NOT the max (the pre-fix bug)
    assert es == pytest.approx(
        tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-ES"), "minimax-ES"),
        abs=1e-3)  # equals the optimizer's own minimized mean damage
    # minimax-S: 𝑞=1 so dual(𝑞)=∞ — there the mean damage IS a max, so the value is unchanged
    # by the fix (this is why the bug hid behind the default scheme)
    ss = mean_damage("minimax-S")
    assert ss == pytest.approx(1.699, abs=1e-3)
    assert ss == pytest.approx(
        tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-S"), "minimax-S"),
        abs=1e-3)
    # held-octave minimax-ES (CTE): the Euclidean fix carries to the held-octave all-interval form too
    assert mean_damage("held-octave minimax-ES") == pytest.approx(
        tuning.get_tuning_map_mean_damage(
            t, tuning.optimize_tuning_map(t, "held-octave minimax-ES"), "held-octave minimax-ES"),
        abs=1e-3)


def test_all_interval_mean_damage_power_label_tracks_the_dual_norm_power():
    # the mean damage is aggregated at dual(𝑞), so the damage chart's indicator (the same minimized
    # value, drawn as a horizontal line) and its power label track dual(𝑞): "2" for a Euclidean (ES)
    # scheme, "∞" for taxicab (-S, dual(𝑞)=∞). The 𝑝 cell stays ∞ either way — that is the power over
    # intervals, not the over-primes aggregation power the mean damage and chart use.
    s = settings.defaults()
    s["optimization"] = True
    s["charts"] = True
    base = service.from_mapping(((1, 0, -4), (0, 1, 4)))

    def chart(scheme):
        cells = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme=scheme, tuning_optimized=True).cells}
        return cells["chart:damage:targets"], cells["optimization:power"]

    es_chart, es_power = chart("minimax-ES")
    assert es_chart.indicator_label == "2"      # dual(𝑞) for q=2
    assert es_power.text == "∞"                  # the 𝑝 cell stays ∞ (power over intervals)
    s_chart, s_power = chart("minimax-S")
    assert s_chart.indicator_label == "∞"        # dual(𝑞) for q=1
    assert s_power.text == "∞"


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
    # then — just the bare 𝒄. The weight stays a LIST: the concrete diag(𝐿)⁻¹ form is gone too, leaving
    # the generic 𝒘 = 𝒄⁻¹ symbol with per-column wₙ = cₙ⁻¹ headers (referencing each complexity column).
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s.update(weighting=True, alt_complexity=True, symbols=True, header_symbols=True, equivalences=True)
    square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))  # an off-diagonal pretransformer
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                             custom_prescaler=square).cells}
    assert on["symbol:complexity:targets"].text == "𝒄"       # NOT "𝒄 = diag(𝑋)"
    assert on["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"    # the generic reciprocal, not a matrix inverse
    assert on["matlabel:col:weight:targets:0"].text == "w₁ = c₁⁻¹"  # reciprocal of the complexity column


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
    # the all-interval Show toggle reveals the in-grid box-𝐓 checkbox (a two-step process); its
    # content is built, so the Show panel offers it live (interactive), not greyed out as a stub
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
    # read-only VALUE (a tuning value like the mean damage) — not a greyed control — so its "optimization power"
    # caption stays the normal value colour in both modes, matching the mean damage's caption beside it.
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
        c.id for c in _with(weighting=True, alt_complexity=True, temperament_tiles=False).cells
    }


def test_alt_complexity_is_implemented_now_that_its_controls_are_built():
    # alt. complexity is un-shelved: its built controls (the box-𝐋 diminuator checkbox, box-𝒄's
    # predefined-complexity options, the alternative-complexity prescalers + tuning schemes) are
    # ready, so it rides in IMPLEMENTED as a live, interactive Show toggle rather than a greyed stub.
    assert "alt_complexity" in settings.IMPLEMENTED


def test_weighting_subcontrols_are_registered_under_weighting():
    # all-interval (the all-interval mode), alternative complexity (controls in boxes 𝐋 and 𝒄) and
    # custom weights (the editable 𝒘 row) are the three sub-controls of weighting, so the panel
    # indents them and shows them only while weighting is on
    keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
    assert {"all_interval", "alt_complexity", "custom_weights"} <= keys
    assert settings.SUBCONTROLS["all_interval"] == "weighting"
    assert settings.SUBCONTROLS["alt_complexity"] == "weighting"
    assert settings.SUBCONTROLS["custom_weights"] == "weighting"


def test_subcontrol_nesting_depth_drives_panel_indentation():
    # the panel indents each row by its nesting depth, so a child sits further right than its
    # parent. The "tuning" grouping parent (depth 0) holds the two modes' shared base (tuning
    # boxes) plus the two modes — "optimization" (Mode A) and "projection" (Mode B) — at depth 1.
    # "optimization" parents the optimize sub-axes (weighting, tuning ranges) at depth 2, and
    # weighting's three refinements (all-interval, alt. complexity, custom weights) at depth 3.
    assert settings.depth_of("tuning") == 0          # the pure grouping parent is top-level
    assert settings.depth_of("tuning_tiles") == 1
    assert settings.depth_of("optimization") == 1    # Mode A, a direct child of the tuning group
    assert settings.depth_of("projection") == 1      # Mode B, optimization's peer
    assert settings.depth_of("tuning_colorization") == 1
    assert settings.depth_of("weighting") == 2       # now nested under optimization
    assert settings.depth_of("tuning_ranges") == 2
    assert settings.depth_of("all_interval") == 3    # weighting's refinements, one deeper
    assert settings.depth_of("alt_complexity") == 3
    assert settings.depth_of("custom_weights") == 3
    assert settings.depth_of("temperament") == 0     # the other grouping parents are top-level too
    assert settings.depth_of("temperament_tiles") == 1
    assert settings.depth_of("temperament_colorization") == 1  # now level with the boxes, not under them
    assert settings.depth_of("mnemonics") == 1       # untouched by the regroup (still under names)


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


def test_custom_weights_make_the_weight_row_editable():
    # custom-weight mode (target-based, plain-value view): the per-target 𝒘 cells become editable
    # weightcells (overriding the slope), and the slope chooser greys (the typed weights supersede it)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True, "custom_weights": True}
    lay = spreadsheet.build(base, s, custom_weights=(1.0, 2.0, 3.0))
    weight_cells = [c for c in lay.cells if c.id.startswith("weight:target:")]
    assert weight_cells and all(c.kind == "weightcell" for c in weight_cells)
    assert next(c for c in lay.cells if c.id == "control:slope").disabled


def test_custom_weights_stay_read_only_in_all_interval_and_math_views():
    # all-interval has structural per-prime weights (no per-target ones) and the math-expr view
    # renders closed forms — so neither makes the weight cells editable even with an override present
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    ai = {**settings.defaults(), "weighting": True, "custom_weights": True}
    lay = spreadsheet.build(base, ai, tuning_scheme="minimax-S", custom_weights=(1.0, 2.0, 3.0))
    assert all(c.kind != "weightcell" for c in lay.cells if c.id.startswith("weight:target:"))
    m = {**settings.defaults(), "weighting": True, "custom_weights": True, "math_expressions": True}
    lay = spreadsheet.build(base, m, custom_weights=(1.0, 2.0, 3.0))
    assert all(c.kind != "weightcell" for c in lay.cells if c.id.startswith("weight:target:"))


def test_custom_weights_show_the_overridden_values_in_the_weight_row():
    # the displayed 𝒘 row IS the override (same values that drive the solve) — sized to the live
    # target count (a length mismatch would fall back to the slope, as the library guards)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "weighting": True, "custom_weights": True}
    n = len([c for c in spreadsheet.build(base, s).cells if c.id.startswith("weight:target:")])
    override = tuple(1.0 + 0.5 * i for i in range(n))
    lay = spreadsheet.build(base, s, custom_weights=override)
    texts = [c.text for c in lay.cells if c.id.startswith("weight:target:")]
    assert texts == [service.cents(w) for w in override]


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
    # the caption band is its wrapped lines plus BAND_GAP (the in-tile breathing room)
    assert cap.h == spreadsheet._wrap_lines(name, cap.w) * spreadsheet.CAPTION_LINE + spreadsheet.BAND_GAP
    assert cap.h <= spreadsheet.MAX_CAPTION_LINES * spreadsheet.CAPTION_LINE + spreadsheet.BAND_GAP
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
    assert short.h == tall.h == spreadsheet._wrap_lines(tall.text, tall.w) * spreadsheet.CAPTION_LINE + spreadsheet.BAND_GAP
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


def test_each_comma_carries_its_own_minus_on_its_branch_point():
    lay = _layout()  # meantone exposes a single comma
    one, by1 = {c.id: c for c in lay.cells}, {ln.id: ln for ln in lay.lines}
    assert "comma_minus:0" in one  # the SOLE comma is removable now (un-tempers to just intonation)
    cm = one["comma_minus:0"]  # centred on the lone comma's branch point, dropping from the top bus
    assert abs((cm.x + cm.w / 2) - by1["v:comma:0"].pos) < 0.51
    assert cm.y == by1["bus:commas:top"].pos
    two = service.from_comma_basis([[4, -4, 1], [4, -5, 1]])  # two real commas: EACH carries its own −
    tlay = spreadsheet.build(two)
    cells, by2 = {c.id: c for c in tlay.cells}, {ln.id: ln for ln in tlay.lines}
    assert {"comma_minus:0", "comma_minus:1"} <= set(cells)  # any comma removable, not just the last
    assert abs((cells["comma_minus:0"].x + cells["comma_minus:0"].w / 2) - by2["v:comma:0"].pos) < 0.51
    assert abs((cells["comma_minus:1"].x + cells["comma_minus:1"].w / 2) - by2["v:comma:1"].pos) < 0.51
    ji = service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # full rank, n=0
    assert not any(c.startswith("comma_minus") for c in {c.id for c in spreadsheet.build(ji).cells})  # nothing to remove


def test_adding_a_comma_starts_a_pending_draft_column_that_does_not_re_rank():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma, mapping r=2
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    assert cells["comma:0"].text == "80/81"  # the real comma stays
    # a draft column rides to its right: an editable "?/?" ratio and blank, green-flagged vector cells
    assert cells["comma:pending"].text == "?/?" and cells["comma:pending"].pending
    assert cells["comma:pending"].x > cells["comma:0"].x
    assert cells["cell:comma:0:1"].text == "" and cells["cell:comma:0:1"].pending
    # the mapping is untouched (the draft is not yet a real comma): still 2 rows, no 3rd
    assert "cell:mapping:1:0" in cells and "cell:mapping:2:0" not in cells
    # the draft has no size cells (undefined until valid)
    assert "tuning:comma:1" not in cells
    # the draft column carries its own − on its branch point (to cancel it); the real comma keeps its
    by_id = {ln.id: ln for ln in spreadsheet.build(base, pending_comma=[None, None, None]).lines}
    assert "comma_minus:0" in cells  # the real comma stays independently removable
    assert abs((cells["comma_minus:pending"].x + cells["comma_minus:pending"].w / 2) - by_id["v:comma:1"].pos) < 0.51


def test_a_partly_typed_pending_comma_shows_its_entered_components():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[4, None, 1]).cells}
    assert cells["cell:comma:0:1"].text == "4"   # typed
    assert cells["cell:comma:1:1"].text == ""    # still blank
    assert cells["cell:comma:2:1"].text == "1"
    assert all(cells[f"cell:comma:{p}:1"].pending for p in range(3))


def test_the_pending_comma_columns_ket_marks_are_flagged_for_green():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma + a pending draft (col 1)
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    # the draft column's EBK ket marks render green (like its cells); the real comma's don't
    assert cells["ebktop:vec:commas:1"].pending and cells["ebkangle:vec:commas:1"].pending
    assert not cells["ebktop:vec:commas:0"].pending


def test_the_pending_comma_greens_the_advanced_prescaling_matrix_draft_column():
    # the advanced complexity-prescaling matrix was the last tuning-family row leaving its draft
    # column blank-white while a comma was pending; it now emits a blank green placeholder stacked
    # over every prescaled sub-row, so the draft reads green top-to-bottom through it too.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    alt = settings.defaults(); alt["weighting"] = True; alt["alt_complexity"] = True
    cells = {c.id: c for c in spreadsheet.build(  # a non-unity slope reveals the prescaling matrix
        base, alt, tuning_scheme="TILT minimax-S", pending_comma=[None, None, None]).cells}
    draft = [k for k in cells if k.startswith("cell:prescaling:commas:") and k.endswith(":draft")]
    assert draft, "the prescaling matrix emits a comma-draft placeholder column"
    assert all(cells[k].pending and cells[k].text == "" for k in draft)  # blank, green-flagged
    assert abs(cells[draft[0]].x - cells["tuning:comma:draft"].x) < 0.5  # same draft column as above
    resting = {c.id: c for c in spreadsheet.build(base, alt, tuning_scheme="TILT minimax-S").cells}
    assert not any(k.startswith("cell:prescaling:") and k.endswith(":draft") for k in resting)


def test_the_comma_basis_plain_text_becomes_a_two_tone_draft_box_while_pending():
    # while a comma is pending the comma-basis plain text can't be a single-colour input
    # (it must show the committed commas black and the draft vector green), so it flips to a
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


def test_adding_a_mapping_row_starts_a_pending_draft_row_that_does_not_re_rank():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone, r=2
    cells = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[None, None, None]).cells}
    # the two committed generator rows stay; a draft row rides ONE ROW_H below them (at index r=2)
    assert "cell:mapping:1:0" in cells and not cells["cell:mapping:1:0"].pending
    assert cells["cell:mapping:2:0"].text == "" and cells["cell:mapping:2:0"].pending  # blank, green-flagged
    assert cells["cell:mapping:2:0"].y - cells["cell:mapping:1:0"].y == spreadsheet.ROW_H
    assert "cell:mapping:3:0" not in cells  # exactly one draft row
    # a "?" generator ratio on the spine, the draft's own ⟨ … ] map brackets, and a − to cancel it
    assert cells["gen:pending"].text == "?" and cells["gen:pending"].pending
    assert cells["bracket:map:pending:l"].pending and cells["bracket:map:pending:r"].pending  # green, like the cells
    assert cells["map_minus:pending"].pending
    # the temperament is untouched: the genmap / canonical mapping stay at the committed rank (no 3rd
    # generator ratio). The derived mapped tiles DO get a blank green placeholder at the draft row, so
    # the whole row reads green across the band (the row mirror of a draft column reading green down).
    assert "gen:2" not in cells
    assert cells["cell:mapped:2:0"].pending and cells["cell:mapped:2:0"].text == ""


def test_a_partly_typed_pending_mapping_row_shows_its_entered_components():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[0, None, 1]).cells}
    assert cells["cell:mapping:2:0"].text == "0"   # typed
    assert cells["cell:mapping:2:1"].text == ""    # still blank
    assert cells["cell:mapping:2:2"].text == "1"
    assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))


def test_a_pending_mapping_row_grows_only_the_mapping_band_by_one_row():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # r=2
    plain = spreadsheet.build(base)
    drafting = spreadsheet.build(base, pending_mapping_row=[None, None, None])
    # the draft adds exactly one ROW_H to the grid (the extra mapping row) — no other band changes
    assert drafting.height - plain.height == spreadsheet.ROW_H


def test_the_mapping_plain_text_becomes_a_two_tone_draft_box_while_a_row_is_pending():
    # the ROW mirror of test_the_comma_basis_plain_text_...: while a generator row is pending, the
    # mapping's editable plain-text box flips to a static two-tone "ptextpending" box (committed maps
    # black, draft map green — a single-colour input can't do that); the comma basis keeps its
    # editable box, and once there's no draft the mapping returns to an editable box.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["plain_text_values"] = True
    drafting = {c.id: c for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
    assert drafting["ptext:mapping:primes"].kind == "ptextpending"
    assert drafting["ptext:vectors:commas"].kind == "ptextedit"  # the comma basis is untouched
    resting = {c.id: c for c in spreadsheet.build(base, s).cells}
    assert resting["ptext:mapping:primes"].kind == "ptextedit"  # no draft -> editable again


def test_the_mapped_list_brackets_grow_to_enclose_the_draft_rows_placeholders():
    # the spanning derived [ ]s (M·targets, M·commas) grow with the band so they enclose the draft
    # row's blank green placeholders at the band floor — mirroring the comma draft, whose mapped_comma
    # [ ] grows over nc_shown to enclose its draft-COLUMN placeholder. The placeholders read green
    # (their value is undefined until the row commits), so the draft row greens across — EXCEPT where
    # it crosses the comma the new generator un-tempers: adding a row drops a comma (the rank-duality
    # preview reds that comma's column), and red overrides green at the crossing.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # r=2, n=1 (one comma — the doomed one)
    plain = {c.id: c for c in spreadsheet.build(base).cells}
    drafting = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[None, None, None]).cells}
    # the spanning [ ] wrap encloses the value rows AND the framing bands it spans (see
    # bracket's fit branch), plus a FRAME_OVERHANG past the marks at each end, so its height is
    # r·ROW_H plus that constant frame allowance...
    frame = ((spreadsheet.FRAME_H + spreadsheet.FRAME_GAP) + (spreadsheet.FRAME_GAP + spreadsheet.BRACE_H)
             + 2 * spreadsheet.FRAME_OVERHANG)
    for bid in ("bracket:mapped:l", "bracket:mapped_comma:l"):
        assert plain[bid].h == 2 * spreadsheet.ROW_H + frame        # committed: r rows
        # ...and grows by exactly one ROW_H when the draft row joins, enclosing its placeholder
        assert drafting[bid].h == plain[bid].h + spreadsheet.ROW_H  # draft: r_shown rows
    # the draft row's mapped-target cell is a blank green placeholder the grown bracket now encloses
    assert drafting["cell:mapped:2:0"].pending and drafting["cell:mapped:2:0"].text == ""
    # ...but its cell over the doomed comma is red (the draft generator un-tempers it away), enclosed all the same
    assert drafting["cell:mapped_comma:2:0"].preview_remove and not drafting["cell:mapped_comma:2:0"].pending


def test_a_comma_minus_hover_fills_the_born_generator_rows_derived_cells():
    # the − hover op is known, so the green ghost row is a COMPLETE generator row, not a blank
    # placeholder: its prime coords AND its mapped image of every interval are computed (the new
    # generator born from un-tempering the comma). Dropping meantone's syntonic comma → JI, whose
    # third generator is prime 5 (⟨0 0 1]); its target images are that prime's exponents.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone r=2; ghost row rides at token 2
    cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("comma", 0)).cells}
    assert [cells[f"cell:mapping:2:{p}"].text for p in range(3)] == ["0", "0", "1"]
    assert all(f"cell:mapped:2:{j}" in cells and cells[f"cell:mapped:2:{j}"].text != "" for j in range(2))


def test_a_mapping_minus_hover_fills_the_born_commas_derived_cells():
    # the dual: the green ghost comma column is a COMPLETE comma column — its vector, and down the
    # mapping band M[surviving row]·newborn = 0 (the rank-reduced mapping tempers it out), and its
    # tuning sizes: it vanishes in the new temperament, so tempered 0, just its just size, error −just.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone; ghost comma rides at token 1
    cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("row", 0)).cells}
    assert [cells[f"cell:comma:{p}:1"].text for p in range(3)] == ["0", "-4", "1"]
    assert cells["tuning:comma:draft"].text == "0.000"                       # vanishes → tempered 0
    assert (cells["just:comma:draft"].text.lstrip("-")                       # error = −just (equal magnitude)
            == cells["retune:comma:draft"].text.lstrip("-") != "0.000")
    assert cells["cell:mapped_comma:1:1"].text == "0"                        # surviving row tempers it out
    assert cells["cell:mapped_comma:0:1"].preview_remove                     # the removed row reds over its cell


def test_a_mapping_minus_hover_fills_the_born_commas_projection_and_complexity_rows():
    # the born comma column reads green top-to-bottom: the projection-half rows (scaling factors λ and
    # P·comma) show the vanished-comma values 0, and the complexity-prescaling matrix + complexity norm
    # show the born comma's own 𝐿·comma and ‖𝐿·comma‖q — not the blank placeholders a real draft leaves.
    s = settings.defaults(); s["weighting"], s["projection"] = True, True
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone; minimax-S → the complexity rows show
    cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S", preview_remove=("row", 0)).cells}
    assert cells["cell:scaling:draft"].text == "0"                           # λ = 0 (a vanished comma)
    assert [cells[f"cell:proj_v:{p}:draft"].text for p in range(3)] == ["0", "0", "0"]  # P·comma = 0
    # the prescaled born-comma vector 𝐿·comma matches what the committed comma columns compute
    pre = [cells[f"cell:prescaling:commas:{i}:draft"].text for i in range(3)]
    assert pre[0] == "0" and pre != ["", "", ""]                             # filled, not blank
    assert cells["complexity:comma:draft"].text not in ("", "<MISSING>")     # its own ‖𝐿·comma‖q
    assert cells["complexity:comma:draft"].pending                           # ...tinted green
    assert all(cells[f"cell:prescaling:commas:{i}:draft"].pending for i in range(3))


def test_a_comma_minus_hover_in_projection_births_an_unchanged_interval():
    # in projection (V = C|U, #unchanged = rank) a comma − raises the rank, so the U half grows: a held
    # interval is BORN with its computed value, tinted green, the dual of the doomed-U a mapping − reds.
    s = settings.defaults(); s["projection"] = True
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone r=2 → 2 unchanged columns
    plain = {c.id: c for c in spreadsheet.build(base, s).cells}
    hovered = {c.id: c for c in spreadsheet.build(base, s, preview_remove=("comma", 0)).cells}
    base_nu = sum(1 for i in plain if i.startswith("cell:unchanged:0:"))
    hov_nu = sum(1 for i in hovered if i.startswith("cell:unchanged:0:"))
    assert hov_nu == base_nu + 1                                             # the U half grew by one
    born = hov_nu - 1
    assert [hovered[f"cell:unchanged:{p}:{born}"].text for p in range(3)] == ["0", "0", "1"]  # computed (prime 5)
    assert all(hovered[f"cell:unchanged:{p}:{born}"].pending for p in range(3))                # ...green
    assert not any(hovered[f"cell:unchanged:{p}:0"].pending for p in range(3))                 # an existing one isn't


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
        assert on[cid].kind == "tuningvalue"  # untouched: still the plain cents cell...
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
    assert cells["cell:prescaling:primes:0:1"].kind == "tuningvalue"  # off-diagonal stays plain
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
    # prescaling cell stays as its plain tuning value. The bare prescaler 𝐿's diagonal is an
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
    assert cells["cell:prescaling:commas:0:0"].kind == "tuningvalue"
    assert cells["cell:prescaling:commas:0:0"].text == "4"


def test_bare_prescaler_diagonal_is_editable_prescalercell_kind():
    # the bare prescaler 𝐿 tile is the editable surface where the user types overrides
    # for the prescaler's diagonal — so each diagonal cell (i == c) is a prescalercell
    # kind (mirroring commacell/interestcell/heldcell, the other editable matrix cells).
    # The OFF-diagonal cells stay tuning value "0" — they're pinned at zero because 𝐿 is diagonal.
    cells = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}  # non-unity slope reveals the prescaling row
    # diagonal cells are prescalercell
    for i in range(3):
        assert cells[f"cell:prescaling:primes:{i}:{i}"].kind == "prescalercell"
    # off-diagonal cells stay plain tuning value "0"
    for i in range(3):
        for c in range(3):
            if i == c:
                continue
            assert cells[f"cell:prescaling:primes:{i}:{c}"].kind == "tuningvalue"
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


def test_counts_on_by_default_shows_the_counts_row():
    # counts ships ON now (a default-on toggle), so the default build shows the counts row + cells
    cells = {c.id for c in _layout().cells}
    assert "label:counts" in cells
    assert any(c.startswith("count:") for c in cells)


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


def test_decimals_off_rounds_every_value_to_the_nearest_integer():
    # the Show panel's "decimals" toggle (off) rounds every displayed cents value — grid cells AND
    # the plain-text EBK strings — to the nearest integer, so the two views still agree. It is a
    # DISPLAY setting: the underlying tuning is untouched, so the same build with decimals ON still
    # shows the full 3-dp reading.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    on = {c.id: c for c in spreadsheet.build(base, settings.defaults(), interest=_INTEREST).cells}
    assert on["just:interest:0"].text == "701.955"  # decimals on (default): full 3-dp

    s = {**settings.defaults(), "plain_text_values": True, "decimals": False}
    off = {c.id: c for c in spreadsheet.build(base, s, interest=_INTEREST).cells}
    assert off["just:interest:0"].text == "702"     # 701.955 → 702, rounded, no decimal point
    assert "." not in off["just:interest:0"].text
    # the plain-text EBK string rounds in lockstep, so the grid and the inline notation still match
    assert off["ptext:just:interest"].text == "702 204 182 814"


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


def test_adding_an_interval_of_interest_opens_a_blank_green_draft_column():
    # mirrors the pending comma: + opens a blank, green-outlined draft column (an editable "?/?"
    # ratio header over empty vector cells) the user fills in — not a pre-filled 1/1
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    cells = {c.id: c for c in spreadsheet.build(base, interest=(), pending_interest=[None, None, None]).cells}
    assert cells["interest:pending"].text == "?/?" and cells["interest:pending"].pending
    assert all(cells[f"cell:interest:{p}:0"].text == "" and cells[f"cell:interest:{p}:0"].pending
               for p in range(3))
    # adding the FIRST interval lights every row the column crosses: the derived rows get blank
    # green placeholders at the draft column too, so it reads green top-to-bottom (not just the ket)
    assert cells["tuning:interest:draft"].pending and cells["tuning:interest:draft"].text == ""
    assert cells["cell:imapped:0:draft"].pending  # the mapped-list draft slot
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
    # the draft column's ket marks render green (like its cells); the real interval's don't
    assert cells["ebkangle:vec:interest:1"].pending
    assert not cells["ebkangle:vec:interest:0"].pending


def _with_held(held_vectors, pending_held=None):
    s = settings.defaults()
    s["optimization"], s["counts"] = True, True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_vectors=held_vectors, pending_held=pending_held)


def test_adding_a_held_interval_opens_a_blank_green_draft_column():
    # the held intervals column gets the same pending-draft behaviour as the commas/interest
    cells = {c.id: c for c in _with_held((), pending_held=[None, None, None]).cells}
    assert cells["held:pending"].text == "?/?" and cells["held:pending"].pending
    assert all(cells[f"cell:held:{p}:0"].text == "" and cells[f"cell:held:{p}:0"].pending
               for p in range(3))
    # the derived rows green the draft column too now (blank placeholders), like the interest draft
    assert cells["tuning:held:draft"].pending and cells["tuning:held:draft"].text == ""
    assert cells["cell:hmapped:0:draft"].pending
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


def test_adding_a_target_opens_a_blank_green_draft_column():
    # the target intervals list gets the same pending-draft behaviour as the commas
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    k = _target_count()
    cells = {c.id: c for c in spreadsheet.build(base, pending_target=[None, None, None]).cells}
    assert cells["target:pending"].text == "?/?" and cells["target:pending"].pending
    # the draft rides at index k (right of the committed targets), blank and green
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
    # target is pending it flips to a static two-tone box (committed black, draft green); with no
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
    for mi in range(3):  # a handful of intervals: at COL_W the content stays narrower than the title
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
    # with names off, the lone symbol sits below the (unframed) tuning row, cleared off the
    # values by BAND_GAP (the in-tile breathing room) — like the gap below the symbol to the name
    assert sym_only["symbol:tuning:primes"].y == sym_only["tuning:prime:0"].y + spreadsheet.ROW_H + spreadsheet.BAND_GAP
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
    # the form layer's own grid mark — the subscript C — rides the main rows only when the mapping IS
    # canonical (the default is the equave-reduced form), and its canon row/column gate on form_tiles.
    # So sweep `form` over the CANONICAL mapping, where flipping it adds/removes the subscript; every
    # other toggle keeps the default base. (form_tiles itself surfaces the canon row over either base.)
    base_for = {"form": service.from_mapping(((1, 0, -4), (0, 1, 4)))}

    def snapshot(s, key_base=base):
        # capture both cells and blocks: most toggles add/move cells, but colorization
        # is expressed purely through blocks (the colour washes), so a cells-only
        # snapshot would call it a no-op. Build under a non-unity slope so the slope-gated
        # weighting machinery (prescaling/complexity rows + box 𝐋's controls) is visible —
        # otherwise flipping alt_complexity changes nothing under the unity default.
        lay = spreadsheet.build(key_base, s, tuning_scheme="TILT minimax-S")
        return (
            # c.unit is in the tuple so cell_units (which adds/removes the per-value unit beneath a
            # cell without changing the cell's id/geometry/text) registers as a real layout change
            frozenset((c.id, c.x, c.y, c.w, c.h, c.kind, c.text, c.unit, c.underlines) for c in lay.cells),
            frozenset((b.id, b.x, b.y, b.w, b.h, b.tint) for b in lay.blocks),
        )

    # a few toggles only refine a layer that isn't their hierarchy parent, so their effect is
    # invisible until that layer is shown — like the slope above, this is a visibility condition,
    # not a sub-control link. The form layer subscripts the canonical-form objects, so it only
    # shows once the symbols layer is on; the form colorization washes the canonical-mapping row +
    # canon-gens column, so it only shows once form_tiles surfaces them. (identity_objects needs no
    # such rider: its standard-domain tiles 𝑀ⱼ / 𝑀𝐺 show over the base temperament directly.)
    rides_on = {"form": "symbols", "form_colorization": "form_tiles"}

    def with_parents_on(key):
        # a sub-control only takes effect while its parent chain is on (e.g. alt. complexity
        # needs weighting, which needs tuning tiles), so enable that chain before flipping it
        s = settings.defaults()
        for parent in settings.ancestors_of(key):
            s[parent] = True
        if key in rides_on:
            s[rides_on[key]] = True
        return s

    # custom-weights drives the grid through a doc FIELD (custom_weights), not the settings dict the
    # build reads — flipping just the flag is a build no-op, like a grouping parent. (all-interval is
    # NOT here: its Show toggle reveals the in-grid checkbox, which IS a settings-driven layout change.
    # Its mode effect — Tₚ=I etc. — is keyed off the scheme and covered by the all-interval tests.)
    MODE_TOGGLES = {"custom_weights"}
    # the `interface` behaviours gate app-wide FEEL, not grid content: animations and tooltips ride a
    # <body> class (CSS), and preview highlighting is gated in the renderer's hover/ring path — none is
    # read by spreadsheet.build, so flipping one is a build no-op the same way a mode toggle is.
    BEHAVIOUR_TOGGLES = {"animations", "preview_highlighting", "tooltips"}
    for key in settings.IMPLEMENTED:
        if key in settings.GROUPING_PARENTS or key in MODE_TOGGLES or key in BEHAVIOUR_TOGGLES:
            continue
        kb = base_for.get(key, base)
        on, off = with_parents_on(key), with_parents_on(key)
        on[key], off[key] = True, False
        assert snapshot(on, kb) != snapshot(off, kb), f"{key} is marked implemented but changes nothing"


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


def test_header_symbols_label_each_matrix_row_or_column_with_a_subscripted_glyph():
    # Header symbols (a toggle independent of the in-tile name symbol below the cells) label
    # each individual row/column of the matrix with a subscripted version of that name, per
    # the maximized mockup. A covector stack labels its ROWS at the left of each row's ⟨
    # bracket; every other multi-value tile labels its COLUMNS above each cell.
    on = {c.id: c for c in _with(header_symbols=True, names=True).cells}
    off = {c.id: c for c in _with(header_symbols=False).cells}

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

    # Header symbols off drops every label (independent of the in-tile symbol/equivalence cells)
    assert not any(c.startswith("matlabel:") for c in off)


def test_in_tile_symbols_and_header_symbols_toggle_independently():
    # the in-tile big symbol (𝒕, above the caption) and the matrix row/column header labels
    # (matlabels 𝒎ᵢ / 𝐜ᵢ) are now SEPARATE toggles — either renders without the other.
    sym_only = {c.id for c in _with(symbols=True, header_symbols=False).cells}
    hdr_only = {c.id for c in _with(symbols=False, header_symbols=True).cells}
    # symbols on, header symbols off: the in-tile symbol renders, but NO row/col header labels
    assert "symbol:tuning:primes" in sym_only
    assert not any(c.startswith("matlabel:") for c in sym_only)
    # header symbols on, symbols off: the matlabels render, but NO in-tile big symbol
    assert any(c.startswith("matlabel:") for c in hdr_only)
    assert not any(c.startswith("symbol:") for c in hdr_only)


def test_matrix_labels_index_match_their_matrix_size():
    # Each label set covers exactly its matrix's rows/columns — r=2 row labels for the
    # mapping, d=3 column labels for the tuning map, k=4 for the target list — so the
    # i-suffix on the ids tracks the live matrix and a relabel adds/drops in lockstep
    on = {c.id for c in _with(header_symbols=True).cells}
    assert {f"matlabel:row:mapping:primes:{i}" for i in range(2)} <= on
    assert "matlabel:row:mapping:primes:2" not in on   # only r=2 rows
    assert {f"matlabel:col:vectors:targets:{j}" for j in range(8)} <= on
    assert "matlabel:col:vectors:targets:8" not in on  # only k=8 targets in the default set
    assert {f"matlabel:col:tuning:primes:{p}" for p in range(3)} <= on
    assert "matlabel:col:tuning:primes:3" not in on    # only d=3 primes


def test_matrix_labels_only_emit_where_the_tile_is_open():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["header_symbols"] = True
    # the mapping row collapsed: its row labels vanish with the rest of its content,
    # while the interval-vectors row's column labels are unaffected
    cells = {c.id for c in spreadsheet.build(base, s, collapsed={"row:mapping"}).cells}
    assert not any(c.startswith("matlabel:row:mapping:") for c in cells)
    assert "matlabel:col:vectors:commas:0" in cells


def test_matrix_labels_sit_above_or_left_of_the_cells_they_label():
    on = {c.id: c for c in _with(header_symbols=True).cells}
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
        {**settings.defaults(), "header_symbols": True},
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
        # the matrix's topmost frame element is the outer [ ]'s overhang top, which reaches
        # FRAME_OVERHANG above the per-column ebktop marks — so the label is centred against THAT,
        # not the marks (which now sit FRAME_OVERHANG lower, inside the wrap).
        bracket_top = on[f"bracket:{frame_id}:l"].y
        tile_top = blocks[tile_block_id].y + spreadsheet.PAD  # logical top (panel overhangs by PAD)
        # the label sits INSIDE the tile (at or below tile_top), not above it in the GAP
        assert label.y >= tile_top - 1, \
            f"{label_id} (y={label.y}) must sit inside tile (top={tile_top}), not in the gap"
        # the label sits ABOVE the bracket (with the bracket clear below it)
        assert label.y + label.h <= bracket_top, \
            f"{label_id} bottom y={label.y + label.h} must be at/above bracket y={bracket_top}"
        # equidistance: distance from tile_top to label-top ≈ distance from label-bottom
        # to bracket-top (within 1px tolerance for int rounding)
        dist_above = label.y - tile_top
        dist_below = bracket_top - (label.y + label.h)
        assert abs(dist_above - dist_below) <= 1, \
            f"{label_id}: dist_above={dist_above}, dist_below={dist_below} should be ~equal"


def test_col_labels_sit_above_the_top_frame_in_framed_rows():
    # In a framed row (interval vectors, mapping, prescaling), the col labels (𝐜ᵢ, 𝐲ᵢ,
    # …) MUST sit above the matrix's top bracket ─┐ — the labels name the columns the
    # bracket spans, so they read like a header over the matrix, not as decoration
    # squeezed into the bracket gutter.
    on = {c.id: c for c in _with(header_symbols=True).cells}
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
    on = {c.id: c for c in _with(header_symbols=True).cells}
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
    # header symbols on adds the 𝒎ᵢ / 𝒙ᵢ row-label gutter on the LEFT of the domain-primes matrix.
    # With no counterpart it shoves the matrix right-of-centre in its grey tile, so we mirror
    # it with an equal empty gutter on the RIGHT. The matrix's per-row ⟨ … ⟩ brackets then sit
    # centred in the primes tile (block:mapping), with a full label width of room each side.
    lay = _with(header_symbols=True)
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
    s["header_symbols"] = True
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
    # the target interval complexity list 𝒄 names its column cells cₙ; with the equivalences
    # layer each header gains its defining equation cₙ = ‖𝐿𝐭ₙ‖q (the q-norm of the prescaled
    # target vector), mirroring the tile big-symbols' "= …" tails. The prescaler glyph follows
    # the X→L rule (𝐿 for the log-prime matrix). All-interval (Tₚ = I) replaces the per-target
    # vector 𝐭ₙ with the n-th prime — the n-th column 𝐿[n] — so each header IS the domain prime
    # complexity map's per-column ‖𝐿[n]‖q. Without equivalences only the bare cₙ shows.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    q = spreadsheet.NORM_SUB_OPEN + "q" + spreadsheet.NORM_SUB_CLOSE
    s = {**settings.defaults(), "header_symbols": True, "weighting": True, "equivalences": True}
    # non-unity slope reveals the complexity row (the prescaler is the log-prime matrix)
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
    assert on["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝐿𝐭₁‖{q}"
    assert on["matlabel:col:complexity:targets:7"].text == f"c₈ = ‖𝐿𝐭₈‖{q}"
    # all-interval: the per-target 𝐭ₙ becomes the n-th prime column 𝐿[n] (a per-column VECTOR norm,
    # matching the domain prime complexity map) — NOT the whole matrix's ‖𝐿‖q
    allint = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S").cells}
    assert allint["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝐿[1]‖{q}"
    assert allint["matlabel:col:complexity:targets:2"].text == f"c₃ = ‖𝐿[3]‖{q}"
    # exactly the domain prime complexity map's per-column headers, bar the cₙ name
    assert allint["matlabel:col:complexity:primes:0"].text == f"‖𝐿[1]‖{q}"
    # equivalences off → just the bare named symbol cₙ
    off = {c.id: c for c in spreadsheet.build(
        base, {**settings.defaults(), "header_symbols": True, "weighting": True},
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
    s["header_symbols"] = True
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
    on = {c.id: c for c in _with("TILT minimax-S", units=True, cell_units=True, weighting=True).cells}  # non-unity slope reveals the prescaling/complexity rows
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


def test_per_box_units_line_and_cell_units_toggle_independently():
    # the per-box "units: …" line (below each caption) and the per-value unit beneath each gridded
    # cell are now SEPARATE toggles — either renders without the other.
    line_only = {c.id: c for c in _with(units=True, cell_units=False).cells}
    cell_only = {c.id: c for c in _with(units=False, cell_units=True).cells}
    # units on, cell units off: the per-box "units:" line renders, but no value carries a per-cell unit
    assert "units:tuning:primes" in line_only
    assert all(not c.unit for c in line_only.values())
    # cell units on, units off: each value carries its per-cell unit, but no per-box "units:" line shows
    assert cell_only["tuning:prime:0"].unit == "¢/p₁"
    assert not any(cid.startswith("units:") for cid in cell_only)


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
    s["cell_units"] = True
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
    # columns: the mean damage ⟪𝐝⟫ₚ and the editable power 𝑝 (optimization is always on, so
    # there is no optimize button to trigger it).
    lay = _with(optimization=True)
    on = {c.id: c for c in lay.cells}
    assert on["optimization:title"].text == "optimization"
    # the mean damage: a cents value over the symbol ⟪𝐝⟫ₚ (double-angle brackets, power subscript)
    assert on["optimization:mean_damage"].kind == "tuningvalue"
    assert on["optimization:mean_damage:symbol"].text == "⟪𝐝⟫ₚ"
    # the power: 𝑝 over its symbol and the "optimization power" caption. With alt. complexity off (the
    # default here) it is read-only — a powerdisplay (its editability is covered separately).
    assert on["optimization:power"].kind == "powerdisplay"
    assert on["optimization:power"].text == "∞"                     # ...showing the current Lp order
    assert on["optimization:power:symbol"].text == "𝑝"
    assert on["optimization:power:caption"].text == "optimization power"
    # the box sits below the damage values, in the target intervals column
    assert on["optimization:title"].y > on["damage:target:0"].y
    assert on["optimization:title"].x == on["header:targets"].x
    # ...and there is no separate optimization row
    assert "label:optimization" not in on
    assert "h:optimization" not in {ln.id for ln in lay.lines}


def test_optimization_power_field_reflects_the_current_scheme():
    # the power field shows the *current* scheme's Lp order: ∞ for minimax, 2 for miniRMS
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    ls = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="held-octave OLD miniRMS-U").cells}
    assert ls["optimization:power"].text == "2"  # miniRMS ⇒ p = 2


def test_optimization_needs_its_parent_tuning_tiles():
    # optimization is a sub-control of tuning tiles: with the tuning region hidden
    # there is nothing to annotate, so the box stays away even when toggled on
    cells = {c.id for c in _with(optimization=True, tuning_tiles=False).cells}
    assert "optimization:power" not in cells
    assert "optimization:title" not in cells


def test_optimization_box_lays_out_mean_damage_and_power():
    lay = _with(optimization=True)
    on = {c.id: c for c in lay.cells}
    box = {b.id: b for b in lay.blocks}["block:optimization:box"]
    # the two controls sit on one row, left to right: mean damage | power
    assert on["optimization:mean_damage"].x < on["optimization:power"].x
    assert on["optimization:mean_damage"].y == on["optimization:power"].y
    # within each column the value/control sits above its symbol/label
    assert on["optimization:mean_damage"].y < on["optimization:mean_damage:symbol"].y
    assert (on["optimization:power"].y < on["optimization:power:symbol"].y
            < on["optimization:power:caption"].y)
    # the min-damage and the power are ordinary gridded cells (COL_W wide); their contents are
    # centred like any other value cell (not stretched/left-justified within the control)
    assert on["optimization:mean_damage"].w == spreadsheet.COL_W
    assert on["optimization:power"].w == spreadsheet.COL_W
    # the controls DISTRIBUTE across the full-width box (no longer packed left): the mean damage is a
    # COLUMN hugging the left edge — its symbol and caption span the column width and its COL_W value
    # cell is centred within it, so a wide min()-wrapped symbol overflows evenly and stays inside the
    # box. The power sits centered in the gap between the column and the box's right inner edge.
    mean_damage_col_x = box.x + spreadsheet.OPT_PAD_L
    assert on["optimization:mean_damage:symbol"].x == mean_damage_col_x
    assert on["optimization:mean_damage:symbol"].w == spreadsheet.OPT_MEAN_DAMAGE_W
    assert on["optimization:mean_damage:caption"].x == mean_damage_col_x
    assert on["optimization:mean_damage"].x == mean_damage_col_x + (spreadsheet.OPT_MEAN_DAMAGE_W - spreadsheet.COL_W) / 2
    mean_damage_r = mean_damage_col_x + spreadsheet.OPT_MEAN_DAMAGE_W  # the mean damage column's right edge
    box_inner_r = box.x + box.w - spreadsheet.OPT_PAD_R               # the box's right inner edge
    # power centered in the gap to the column's right: its COL_W value cell straddles the midpoint
    assert on["optimization:power"].x == (mean_damage_r + box_inner_r) / 2 - spreadsheet.COL_W / 2
    cap = on["optimization:power:caption"]
    assert cap.x > mean_damage_r and cap.x + cap.w < box.x + box.w  # ...and its caption clears both sides
    # the box is floored wide enough to seat the spread-out controls
    assert box.w >= spreadsheet.OPT_BOX_MIN_W
    # the caption occupies a single line (so "optimization power" sits right under 𝑝, not a
    # two-line band that floats it lower)
    assert on["optimization:power:caption"].h == spreadsheet.CAPTION_LINE
    # the title sits inside the box (below its top border) with a gap before the controls
    assert on["optimization:title"].y > box.y
    assert on["optimization:mean_damage"].y > on["optimization:title"].y + on["optimization:title"].h
    # optimization is always on — no optimize button, and no lock hint beneath it
    ids = {c.id for c in lay.cells}
    assert "optimization:button" not in ids
    assert "optimization:button:hint" not in ids
    assert not any(c.id.startswith("optimization:") for c in _with(optimization=False).cells)


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
    assert box.w >= spreadsheet.OPT_BOX_MIN_W  # wide enough to seat mean damage | power | button
    assert box.w == blk["block:damage:targets"].w - 2 * spreadsheet.PAD  # still fills its tile


def test_a_manual_generator_tuning_drives_the_displayed_maps():
    # a manual generator-tuning override drives the tuning maps directly, not the scheme
    # optimum: a pure octave + pure fifth tunes prime 3 (= g0 + g1) to exactly the just fifth
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
    # retunes the generator map itself — not just the displayed target columns: targeting only
    # 2/1 + 3/2 under minimax-U pulls the fifth toward just.
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


def test_editable_target_vector_cells_clear_the_column_separator():
    # the target list is a matrix drawn WITH separator rules between its interval columns
    # (unlike the loose interest collection). But its vector cells are editable inputs whose
    # opaque box, sitting flush at the slot boundary, would paint over the thin rule. So the
    # editable target cells are inset within their COL_W slot — like the interest kets — leaving
    # a gap the separator shows through, while staying centred so the per-column marks/axis align.
    cells = {c.id: c for c in _layout().cells}
    c0, c1 = cells["cell:vec:targets:0:0"], cells["cell:vec:targets:1:0"]
    sep = cells["sep:vec:targets:1"]            # the rule between target intervals 0 and 1
    full = cells["cell:mapped:0:0"]             # the mapped image spans the full COL_W slot
    assert c0.w < full.w                        # the input box is inset (narrower than the slot)
    assert c0.x + c0.w / 2 == full.x + full.w / 2   # ...but centred on the same slot
    # the rule lies entirely in the gap between the two input boxes — neither covers it
    assert c0.x + c0.w <= sep.x                 # cell 0 ends at/before the rule's left edge
    assert sep.x + sep.w <= c1.x                # cell 1 starts at/after the rule's right edge


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
    # mean damage ⟪𝐝⟫ₚ: max damage for the default minimax) to the damage chart
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
    # a miniRMS scheme subscripts it with 2
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"], s["charts"] = True, True
    rms = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="held-octave OLD miniRMS-U").cells}
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
    # vectors / mapping / sizes / complexity tiles, it gets the units-row label and the
    # complexity-prescaling matrix
    on = _held("TILT minimax-S", weighting=True, domain_units=True)  # non-unity slope opens the prescaling row
    assert "cell:prescaling:held:0:0" in on     # the complexity-prescaling matrix over the held interval
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


def test_mapped_generator_detempering_renders_with_identity_objects():
    # 𝑀D = 𝐼 (the detempering is M's right-inverse): the r × r identity = M·D in generator coords —
    # an identity object shown with identity_objects AND the detempering column on. A COLUMN-first
    # vector list { … ] (each detempering a ket [ … }), its columns headed 𝑀𝐝ᵢ.
    cells = {c.id: c for c in _with(identity_objects=True, generator_detempering=True, names=True,
                                    symbols=True, header_symbols=True, equivalences=True,
                                    plain_text_values=True).cells}
    for i in range(2):  # r = 2
        for k in range(2):
            assert cells[f"cell:mapped_detempering:{i}:{k}"].text == ("1" if i == k else "0")
            assert cells[f"cell:mapped_detempering:{i}:{k}"].kind == "mapped"
    assert cells["symbol:mapping:detempering"].text == "\U0001D440D = \U0001D43C"  # 𝑀D = 𝐼
    assert cells["caption:mapping:detempering"].text == "mapped generator detempering"
    assert cells["matlabel:col:mapping:detempering:0"].text == "\U0001D440\U0001D41D₁"  # 𝑀𝐝₁
    # cols-first: outer { … ] wrap + per-column ket marks [ … } (NOT a per-row covector frame)
    assert cells["bracket:mapped_detempering:l"].text == spreadsheet.GENMAP_BRACKETS[0]  # {
    assert cells["ebktop:mapped_detempering:0"].kind == "ebktop"
    assert cells["ebkbrace:mapped_detempering:0"].kind == "ebkbrace"  # the ket's } foot
    assert cells["ptext:mapping:detempering"].text == "{[1 0} [0 1}]"


def test_mapped_generator_detempering_gated_off_by_default():
    # 𝑀D = 𝐼 is an identity object, so even with the detempering column on it carries NOTHING
    # without identity_objects: no cells, framing kets, bracket, fold toggle, caption, symbol or
    # plain text.
    cells = {c.id for c in _with(generator_detempering=True, names=True, symbols=True,
                                 equivalences=True, plain_text_values=True).cells}
    assert not any("mapped_detempering" in c for c in cells)
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
    assert cells["caption:tuning:detempering"].text == "(retempered) generator tuning map"
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
         "weighting": True, "form_tiles": True},  # form_tiles reveals the canonical-mapping row
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
    s["optimization"] = True  # reveal the held intervals column (a tuning-box sub-control)
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
    # the rows hidden by default follow the same content rule when revealed: the canonical-mapping row is
    # a temperament + form REGION, but form_colorization is OFF here, so only its temperament half washes
    # — its 𝑀_C tile reads yellow (the magenta form layer is gated away; with it on the tile would be RED
    # — see test_form_colorization_washes_the_canon_row_and_column). The prescaler 𝑋 is cyan, so the prescaling
    # and complexity rows carry it everywhere; a column that also bears a yellow object (the
    # domain primes P or the comma basis C) greens, while the cyan target list 𝑋T stays cyan.
    s = settings.defaults()
    s["temperament_colorization"] = True
    s["tuning_colorization"] = True
    s["form_tiles"] = True   # reveal the canonical-mapping row
    s["weighting"] = True       # reveal the prescaling + complexity rows (a tuning-boxes sub-control)
    s["optimization"] = True    # reveal the held column
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            tuning_scheme="TILT minimax-S",  # non-unity slope reveals the slope-gated prescaling/complexity rows
                            interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))
    cells = {c.id: c for c in lay.cells}
    Y, C, G, N = {"temperament"}, {"tuning"}, {"temperament", "tuning"}, set()
    at = lambda cid: _color_at(lay, *_mid(cells, cid))
    assert at("cell:canon:0:0") == Y                       # 𝑀_C over the yellow domain basis P (form layer off)
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


def test_form_colorization_washes_the_canon_row_and_column():
    # step 5: the colour BANDS — the canonical-mapping ROW + canonical-generators COLUMN are a temperament
    # + form region (red); the projection + tuning ROWS are a tuning region (cyan). Every tile inherits its
    # row/column bands (tile_groups, no per-tile entry) and the darken-blend composes them: red alone, red +
    # the cyan target/held columns = white, the projection row's cyan + the yellow primes/gens basis = green.
    s = settings.defaults()
    s.update(form_tiles=True, form_colorization=True, temperament_colorization=True, tuning_colorization=True,
             generator_detempering=True, optimization=True, projection=True, identity_objects=True)
    b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), settings=s,
                                 interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),), held_basis_ratios=("2/1", "5/4"))
    b.layout()
    tg = b.tile_groups
    RED, WHITE, GREEN = {"form", "temperament"}, {"form", "temperament", "tuning"}, {"temperament", "tuning"}
    # the canon ROW + canon-gens COLUMN: red, going white where they cross a cyan column / row
    assert tg("canon", "primes") == RED and tg("canon", "gens") == RED and tg("canon", "detempering") == RED
    assert tg("canon", "targets") == WHITE and tg("canon", "held") == WHITE      # cyan target / held columns
    assert tg("mapping", "canongens") == RED                                     # 𝐹⁻¹ (a non-cyan row)
    assert tg("projection", "canongens") == WHITE and tg("tuning", "canongens") == WHITE  # the cyan rows
    # the PROJECTION row: cyan, green over its yellow primes / generators columns
    assert tg("projection", "primes") == GREEN and tg("projection", "gens") == GREEN
    assert tg("projection", "detempering") == {"tuning"} and tg("projection", "targets") == {"tuning"}
    # the MAIN mapping row is untouched — temperament yellow, never the form region
    assert tg("mapping", "primes") == {"temperament"}
    # the THREE-way (white) intersection RENDERS as the bare white base — no colour band, so it reads
    # white (lighter than the board), not the muddy darken-grey three colour bands would give.
    cells = {c.id: c for c in b.cells}
    yc = cells["cell:canon_mapped:0:0"]   # Y_C, a white tile
    x, y = yc.x + yc.w / 2, yc.y + yc.h / 2
    over = lambda pred: any(pred(bl) and bl.x <= x <= bl.x + bl.w and bl.y <= y <= bl.y + bl.h for bl in b.blocks)
    assert over(lambda bl: bl.id.startswith("washbase:"))                    # a white base IS laid
    assert not over(lambda bl: bl.tint in ("temperament", "tuning", "form"))  # but NO colour band → white
    # the counts "rank" tile spans both generator columns but splits: yellow generators | red canon-gens
    rank = cells["count:gens"]
    gx, cgx = cells["cell:form:0:0"].x + 5, cells["cell:fcancel:0:0"].x + 5
    in_band = lambda bx, tint: any(bl.tint == tint and bl.x <= bx <= bl.x + bl.w
                                   and bl.y <= rank.y + rank.h / 2 <= bl.y + bl.h for bl in b.blocks)
    assert in_band(gx, "temperament") and not in_band(gx, "form")   # generators half: yellow
    assert in_band(cgx, "temperament") and in_band(cgx, "form")     # canon-gens half: red


def test_form_colorization_is_a_layer_the_other_colorizations_compose_with():
    # the colorizations stack like coloured FILTERS (darken blend): each {group}_colorization lays its
    # colour and they compose, so the SAME tile reads different colours by which layers are on. The
    # canonical generator tuning map (tuning row × canon-gens column) is the witness: with only tuning on
    # it is its row's cyan; add temperament → green; add form → white. No per-tile colour was set — it
    # inherits its row's cyan band and the canon-gens region, and the filters do the rest.
    def active(**toggles):  # the wash groups actually painted: tile_groups filtered by the live toggles
        s = settings.defaults()
        s.update(form=True, form_tiles=True, projection=True, **toggles)
        b = spreadsheet._GridBuilder(service.from_mapping(((1, 1, 0), (0, 1, 4))), settings=s,
                                     held_basis_ratios=("2/1", "5/4"))
        b.layout()
        return {g for g in b.tile_groups("tuning", "canongens") if s.get(f"{g}_colorization")}
    assert active(tuning_colorization=True) == {"tuning"}                                     # cyan
    assert active(tuning_colorization=True, temperament_colorization=True) == {"tuning", "temperament"}  # green
    assert active(tuning_colorization=True, temperament_colorization=True,
                  form_colorization=True) == {"tuning", "temperament", "form"}                # white (base-only render)


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


def _spine_colormap():
    # everything that reveals the two spine rows (counts, units) and the two spine columns
    # (quantities, units), plus the detempering column and the weighting rows, so every
    # spine intersection the continuity rule colours is present to probe
    s = settings.defaults()
    s["tuning_colorization"] = s["temperament_colorization"] = True
    s["counts"] = s["domain_units"] = s["interval_ratios"] = True
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


# --- per-cell audio (click an interval cell to hear it) ----------------------
# Audio is triggered by clicking the interval cells themselves (a hover speaker icon), not by
# dedicated audio rows. Each playable cell carries an `audio = (tile, idx, cents)` tuple: `cents`
# is the pitch it sounds, and `tile`+`idx` group a row's cells so the bank's arp/chord modes sweep
# the whole tile from the clicked note. The JI representations (ratios/vectors/primes) sound the
# JUST size; the tuning row sounds the TEMPERED size; the genmap sounds the generators.


def test_comma_ratio_cell_is_click_to_play_with_its_just_size():
    cells = {c.id: c for c in _layout().cells}
    cb = cells["comma:0"]
    assert cb.audio is not None
    tile, idx, cents = cb.audio
    assert (tile, idx) == ("quantities:commas", 0)
    # the meantone comma 81/80 is ~21.506¢ JUST (it is tempered to ~0¢) — so a magnitude of ~21.5
    # confirms the ratio sounds the JUST size, not the tempered one (sign is the comma's stored
    # orientation, the same value the old audio rows sounded)
    assert abs(abs(cents) - 21.506) < 0.01


def test_prime_cell_plays_its_size_but_a_generator_ratio_does_not():
    cells = {c.id: c for c in _layout().cells}
    p = cells["prime:1"]  # the prime 3
    assert p.audio is not None
    tile, idx, cents = p.audio
    assert (tile, idx) == ("quantities:primes", 1)
    assert abs(cents - 1901.955) < 0.01  # 3/1 sounds 1901.955¢ (its JUST size)
    # generators have no JUST size, so the generator-ratio cells stay silent (not click-to-play)
    assert cells["qgen:0"].audio is None


def test_tuning_sounds_tempered_just_sounds_just_and_retuning_errors_are_silent():
    cells = {c.id: c for c in _layout().cells}
    # the SAME comma sounds ~0¢ from the tuning row (meantone tempers 81/80 out) and ~21.5¢ from
    # the just row — so the two rows demonstrably sound the tempered vs the just size
    tuned = cells["tuning:comma:0"]
    assert tuned.audio is not None and tuned.audio[0] == "tuning:commas"
    assert abs(tuned.audio[2]) < 0.01
    just = cells["just:comma:0"]
    assert just.audio is not None and just.audio[0] == "just:commas"
    assert abs(abs(just.audio[2]) - 21.506) < 0.01
    # the retuning-error row is not a pitch — none of its cells play
    assert all(c.audio is None for c in cells.values() if c.id.startswith("retune:"))


def test_genmap_cell_sounds_the_generators_tuned_size():
    cells = {c.id: c for c in _layout().cells}
    g = cells["tuning:gen:0"]
    assert g.audio is not None
    tile, idx, cents = g.audio
    assert (tile, idx) == ("tuning:gens", 0)
    assert abs(cents) > 100                                  # a real generator pitch, not silence
    assert abs(cents - float(cells["tuning:gen:0"].text)) < 0.6  # matches the displayed tuned size


def test_every_interval_ratio_and_vector_is_click_to_play():
    # commas were covered above; the targets / held / intervals-of-interest / detempering ratios
    # AND their vector columns are click-to-play too, each sounding its JUST size. A vector column's
    # every component cell carries the column's pitch (keyed to the interval, not the prime row).
    base = {c.id: c for c in _layout().cells}
    tr = next(c for c in base.values() if c.id.startswith("target:") and c.id != "target:pending")
    assert tr.audio and tr.audio[0] == "quantities:targets"
    tv = next(c for c in base.values() if c.id.startswith("cell:vec:targets:"))
    assert tv.audio and tv.audio[0] == "vectors:targets"
    assert base["cell:comma:0:0"].audio and base["cell:comma:0:0"].audio[0] == "vectors:commas"
    interest = {c.id: c for c in _with_interest([(-2, 0, 1)]).cells}  # 5/4 = 2⁻²·5
    ir = next(c for c in interest.values() if c.id.startswith("interest:") and c.id != "interest:pending")
    assert ir.audio and ir.audio[0] == "quantities:interest"
    iv = next(c for c in interest.values() if c.id.startswith("cell:interest:"))
    assert iv.audio and iv.audio[0] == "vectors:interest"
    held = _held()
    hr = next(c for c in held.values() if c.id.startswith("held:") and c.id != "held:pending")
    assert hr.audio and hr.audio[0] == "quantities:held"
    hv = next(c for c in held.values() if c.id.startswith("cell:held:"))
    assert hv.audio and hv.audio[0] == "vectors:held"
    det = {c.id: c for c in _with(generator_detempering=True).cells}
    assert det["detempering:0"].audio and det["detempering:0"].audio[0] == "quantities:detempering"
    dv = next(c for c in det.values() if c.id.startswith("cell:vec:detempering:"))
    assert dv.audio and dv.audio[0] == "vectors:detempering"


def test_form_layer_is_a_live_parent_with_three_live_subcontrols():
    # the form layer is a live top-level toggle (it adds the canonical-form subscript C — so unlike
    # the pure grouping parents temperament/tuning it is NOT in GROUPING_PARENTS). All THREE of its
    # sub-controls are live: "form_controls" (the <choose form> dropdowns), "form_tiles" (the
    # canonical-mapping row + canonical-generators column) and "form_colorization" (the magenta wash).
    keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
    assert {"form", "form_controls", "form_tiles", "form_colorization"} <= keys
    assert settings.defaults()["form"] is False and "form" in settings.IMPLEMENTED  # live parent
    assert "form" not in settings.GROUPING_PARENTS  # it carries a real layer, unlike temperament/tuning
    for child in ("form_controls", "form_tiles", "form_colorization"):
        assert settings.SUBCONTROLS[child] == "form"            # grouped under the form parent
        assert settings.defaults()[child] is False              # default off
        assert child in settings.IMPLEMENTED                    # all three live now (steps 2, 4, 5)
    # the parent precedes its children in the group (the panel requires it for indentation)
    specific = [k for k, *_ in dict(settings.SHOW_GROUPS)["specific tiles & controls"]]
    assert specific.index("form") < min(specific.index(c)
                                        for c in ("form_controls", "form_tiles", "form_colorization"))


_CANON_MEANTONE = ((1, 0, -4), (0, 1, 4))  # meantone's canonical (defactored Hermite) form


def _canon_cells(**overrides):
    # build over a CANONICAL mapping, so the form layer's subscript C rides the MAIN rows (it marks
    # the canonical form — on a non-canonical mapping the main rows stay bare; see step 3c below)
    s = settings.defaults()
    s.update(overrides)
    held = s.pop("_held_vectors", None)
    ratios = s.pop("_held_basis_ratios", None)
    kw = {}
    if held is not None:
        kw["held_vectors"] = held
    if ratios is not None:
        kw["held_basis_ratios"] = ratios
    return {c.id: c for c in spreadsheet.build(service.from_mapping(_CANON_MEANTONE), s, **kw).cells}


def test_form_layer_subscripts_the_canonical_form_objects_in_symbols():
    # over a CANONICAL mapping, the "form" layer marks the canonical form with a subscript C after
    # the leading glyph of every generator-basis object — the mapping 𝑀 and its products (mapped
    # comma basis 𝑀C, mapped target list Y), the generator tuning map 𝒈, and the projection's
    # generator embedding G. The form-INVARIANT objects (the prime tuning map 𝒕, the comma basis C)
    # stay bare. The subscript is the SUBSCRIPT_C sentinel — distinct from the upright comma-basis C.
    C = spreadsheet.SUBSCRIPT_C
    on = _canon_cells(symbols=True, form=True)
    off = _canon_cells(symbols=True)
    assert on["symbol:mapping:primes"].text == f"𝑀{C}"
    assert on["symbol:mapping:commas"].text == f"𝑀{C}C"   # 𝑀_C then the upright comma basis C
    assert on["symbol:mapping:targets"].text == f"Y{C}"
    assert on["symbol:tuning:gens"].text == f"𝒈{C}"
    # the projection's generator embedding G (only present when projection is on)
    proj = _canon_cells(symbols=True, projection=True, form=True)
    assert proj["symbol:projection:gens"].text == f"G{C}"
    # form-invariant objects stay bare, and nothing is subscripted without the layer
    assert on["symbol:tuning:primes"].text == "𝒕"          # the prime tuning map is form-invariant
    assert on["symbol:vectors:commas"].text == "C"         # the comma basis itself
    assert off["symbol:mapping:primes"].text == "𝑀"        # no subscript when the form layer is off


def test_form_layer_subscripts_the_canonical_form_objects_in_equivalences():
    # the subscript reaches inside the defining equations too: 𝒕 = 𝒈C𝑀C, Y = 𝑀C T, and the
    # projection's P = GC𝑀C — but 𝒕 (the form-invariant result) keeps its bare head.
    C = spreadsheet.SUBSCRIPT_C
    on = _canon_cells(symbols=True, equivalences=True, projection=True, form=True)
    assert on["symbol:tuning:primes"].text == f"𝒕 = 𝒈{C}𝑀{C}"      # 𝒕 bare, 𝒈/𝑀 subscripted
    assert on["symbol:mapping:targets"].text == f"Y{C} = 𝑀{C}T"
    assert on["symbol:projection:gens"].text == f"G{C} = U(𝑀{C}U)⁻¹"


def test_form_layer_subscripts_the_matrix_header_labels():
    # "everywhere" includes the matrix row/column header labels (matlabels), not just the tile
    # symbols: the mapping's row covectors 𝒎ᵢ → 𝒎_Cᵢ, the mapped products' leading 𝑀 — 𝑀𝐜ᵢ (mapped
    # comma basis) and 𝑀𝐡ᵢ (mapped held basis) — the mapped target columns 𝐲ᵢ, the generator tuning
    # map 𝒈ᵢ, and the projection embedding's 𝐠ᵢ all gain the subscript. Form-invariant labels (the
    # prime tuning map's 𝒕𝐜ᵢ, the comma basis 𝐜ᵢ) stay bare. Over a CANONICAL mapping (subscript on main).
    C, s1 = spreadsheet.SUBSCRIPT_C, spreadsheet._sub(1)
    on = _canon_cells(symbols=True, header_symbols=True, form=True)
    assert on["matlabel:row:mapping:primes:0"].text == f"𝒎{C}{s1}"   # the mapping covector rows
    assert on["matlabel:col:mapping:commas:0"].text == f"𝑀{C}𝐜{s1}"  # mapped comma basis
    assert on["matlabel:col:mapping:targets:0"].text == f"𝐲{C}{s1}"  # mapped target list Y
    assert on["matlabel:col:tuning:gens:0"].text == f"𝒈{C}{s1}"      # generator tuning map
    # form-invariant header labels stay bare
    assert on["matlabel:col:tuning:commas:0"].text == f"𝒕𝐜{s1}"      # the prime tuning map's 𝒕𝐜
    assert on["matlabel:col:vectors:commas:0"].text == f"𝐜{s1}"      # the comma basis itself
    # the mapped HELD interval basis (𝑀𝐡) — over a build with a held interval column
    held = _canon_cells(symbols=True, header_symbols=True, form=True, optimization=True,
                        _held_vectors=[(-1, 1, 0)])
    assert held["matlabel:col:mapping:held:0"].text == f"𝑀{C}𝐡{s1}"
    # under unchanged the mapped comma column reads the mapped unrotated vector list 𝑀𝐯, and the
    # projection embedding's generator columns are 𝐠 — both subscripted, over a projection build
    proj = _canon_cells(symbols=True, header_symbols=True, form=True, projection=True,
                        _held_basis_ratios=("2/1", "5/4"))
    assert proj["matlabel:col:mapping:commas:0"].text.startswith(f"𝑀{C}𝐯")  # unrotated vector list 𝑀𝐯
    assert proj["matlabel:col:projection:gens:0"].text == f"𝐠{C}{s1}"


def test_form_subscript_is_two_faced_and_the_canon_row_needs_a_noncanonical_form():
    # the subscript C marks the canonical form: on a NON-canonical mapping (the default equave-reduced
    # meantone) the main rows stay BARE; on a canonical one the subscript rides them. The canonical-
    # mapping row + 𝐹 (which display the canonical form) need BOTH the form-tiles toggle AND a
    # non-canonical stored form — over a canonical 𝑀 they would just duplicate the main rows, so they hide.
    C = spreadsheet.SUBSCRIPT_C
    noncanon = {c.id: c for c in _with(symbols=True, form=True).cells}     # default = equave-reduced
    assert noncanon["symbol:mapping:primes"].text == "𝑀"                  # bare: not the canonical form
    assert not any(cid.startswith("cell:canon:") for cid in noncanon)     # canon row gated off (no form_tiles)
    canon = _canon_cells(symbols=True, form=True)                          # canonical mapping, no form_tiles
    assert canon["symbol:mapping:primes"].text == f"𝑀{C}"                 # subscript on the main rows
    assert not any(cid.startswith("cell:canon:") for cid in canon)        # no canon row without form_tiles
    # turning form_tiles on surfaces the canonical-mapping row — but ONLY over a non-canonical form
    tiles = {c.id: c for c in _with(symbols=True, form=True, form_tiles=True).cells}
    assert any(cid.startswith("cell:canon:") for cid in tiles)
    # over a CANONICAL mapping the form box has nothing non-trivial to show (𝑀 = 𝑀_C, 𝐹 = 𝐼): the
    # canonical-mapping row AND the canonical-generators column both stay hidden even with form_tiles on
    canon_tiles = _canon_cells(symbols=True, form=True, form_tiles=True)
    assert not any(cid.startswith("cell:canon:") for cid in canon_tiles)       # no canonical-mapping row
    assert not any(cid.startswith("cell:finv:") for cid in canon_tiles)        # no editable 𝐹 tile
    assert not any(":canongens" in cid for cid in canon_tiles)                 # no canonical-generators column


def test_form_box_shows_the_mapping_decomposition_equivalence_only_when_noncanonical():
    # with the form box up, the mapping tile's symbol line gains the decomposition 𝑀 = 𝐹𝑀_C — but
    # only while 𝑀 ≠ 𝑀_C (a non-trivial 𝐹). The default meantone ((1,1,0),(0,1,4)) is equave-reduced,
    # so 𝐹 ≠ 𝐼 and the tail shows; over the canonical mapping it would be trivially 𝐼·𝑀_C, suppressed.
    C = spreadsheet.SUBSCRIPT_C
    on = {c.id: c for c in _with(symbols=True, equivalences=True, form_tiles=True).cells}
    assert on["symbol:mapping:primes"].text == f"𝑀 = 𝐹𝑀{C}"   # bare 𝑀 head (non-canonical) + the 𝐹𝑀_C tail
    # over a CANONICAL mapping (form box still up) the decomposition is trivial (𝐹 = 𝐼) — no tail
    canon = _canon_cells(symbols=True, equivalences=True, form=True, form_tiles=True)
    assert canon["symbol:mapping:primes"].text == f"𝑀{C}"     # subscript head, NO " = 𝐹𝑀_C" tail
    # the tail needs the form box: without form_tiles the canon row is gone and the tail can't appear
    off = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
    assert off["symbol:mapping:primes"].text == "𝑀"           # no decomposition without the form box


def test_form_subscript_covers_the_whole_mapping_row_including_new_tiles():
    # the subscript-C applies by ROW, not per tile, so every mapped product in the mapping row —
    # including the identity-object tiles 𝑀G (mapped generators) and 𝑀D (mapped generator
    # detemperings) — inherits 𝑀 → 𝑀_C with no per-tile registration. Over a canonical mapping.
    C, s1 = spreadsheet.SUBSCRIPT_C, spreadsheet._sub(1)
    on = _canon_cells(symbols=True, header_symbols=True, form=True,
                     generator_detempering=True, identity_objects=True)
    assert on["symbol:mapping:gens"].text == f"𝑀{C}G"          # mapped generators 𝑀G → 𝑀_CG
    assert on["symbol:mapping:detempering"].text == f"𝑀{C}D"   # mapped generator detempering 𝑀D → 𝑀_CD
    assert on["matlabel:col:mapping:detempering:0"].text == f"𝑀{C}𝐝{s1}"  # and its column header


def test_canonical_mapping_row_carries_its_own_symbols_and_row_headers():
    # the canonical-mapping row (surfaced when a non-canonical form is active) has its own symbols +
    # row headers: the canonical mapping 𝑀_C over the primes (subscript baked — it IS the canonical
    # form) and the INVERSE generator form matrix 𝐹⁻¹ over the gens column (𝑀_C = 𝐹⁻¹𝑀). The generator
    # form matrix 𝐹 itself (𝑀 = 𝐹𝑀_C), with its 𝒇 row labels, rides the mapping row's canongens column.
    C, s1 = spreadsheet.SUBSCRIPT_C, spreadsheet._sub(1)
    on = {c.id: c for c in _with(symbols=True, header_symbols=True, form=True, form_tiles=True).cells}  # form_tiles → canon surfaces
    assert on["symbol:canon:primes"].text == f"𝑀{C}"               # the canonical mapping
    assert on["symbol:canon:gens"].text == "𝐹⁻¹"                   # the inverse generator form matrix
    assert on["symbol:mapping:canongens"].text == "𝐹"             # the generator form matrix itself
    assert on["matlabel:row:canon:primes:0"].text == f"𝒎{C}{s1}"   # 𝑀_C's covector rows 𝒎_Cᵢ
    assert on["matlabel:row:mapping:canongens:0"].text == f"𝒇{s1}"  # 𝐹's rows 𝒇ᵢ


def test_canonical_mapping_row_renders_its_mapped_product_tiles():
    # the canonical-mapping row carries 𝑀_C's mapped lists — the canonical-form twins of the
    # mapping row's read-only M·X tiles, over the rc canonical rows: 𝑀_C·D = 𝐹 (the generator form
    # matrix), 𝑀_C·C = 𝑂 (the comma basis vanishes), and 𝑀_C·H / 𝑀_C·interest. Built over the app
    # default (a NON-canonical fifth form), so 𝑀_C genuinely differs from the stored mapping 𝑀.
    M = ((1, 1, 0), (0, 1, 4))
    Mc = service.canonical_mapping(M)                 # ((1, 0, -4), (0, 1, 4))
    F = service.form_matrix(M)                        # 𝑀_C·D = 𝐹
    held = [(-1, 1, 0)]                               # one held interval (3/2)
    interest = ((1, -2, 1),)                          # one interval of interest
    s = settings.defaults()
    s.update(form=True, form_tiles=True, generator_detempering=True, optimization=True)
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(M), s, held_vectors=held, interest=interest).cells}
    rc, r = len(Mc), len(M)
    # the canonical mapping 𝑀_C itself (differs from the stored fifth-form 𝑀)
    assert [[cells[f"cell:canon:{i}:{p}"].text for p in range(3)] for i in range(rc)] == \
        [[str(x) for x in row] for row in Mc]
    # 𝑀_C·D = 𝐹
    assert [[cells[f"cell:canon_detempering:{i}:{c}"].text for c in range(r)] for i in range(rc)] == \
        [[str(x) for x in row] for row in F]
    # 𝑀_C·C = 𝑂 — the lone comma maps to a zero column
    assert all(cells[f"cell:canon_mapped_comma:{i}:0"].text == "0" for i in range(rc))
    # 𝑀_C·H and 𝑀_C·interest — 𝑀_C applied to each column vector
    mc_dot = lambda v: [str(sum(Mc[i][p] * v[p] for p in range(3))) for i in range(rc)]
    assert [cells[f"cell:canon_hmapped:{i}:0"].text for i in range(rc)] == mc_dot(held[0])
    assert [cells[f"cell:canon_imapped:{i}:0"].text for i in range(rc)] == mc_dot(interest[0])


def test_canonical_mapping_row_tile_symbols_units_and_equivalences():
    # full parity for the mapped tiles: 𝑀_C-baked symbols + their defining equations, the canonical-
    # generator units g_C (g_C/p for 𝑀_C, g_C/g for 𝐹, plain g_C for the mapped lists), and the
    # 𝑀_C-baked column headers (𝑀_C𝐝 / 𝑀_C𝐜 / 𝐲_C / 𝑀_C𝐡).
    C, s1 = spreadsheet.SUBSCRIPT_C, spreadsheet._sub(1)
    s = settings.defaults()
    s.update(form=True, form_tiles=True, symbols=True, equivalences=True, units=True, header_symbols=True,
             generator_detempering=True, optimization=True)
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s, held_vectors=[(-1, 1, 0)]).cells}
    assert cells["symbol:canon:detempering"].text == f"𝑀{C}D = 𝐹"
    assert cells["symbol:canon:commas"].text == f"𝑀{C}C = 𝑂"
    assert cells["symbol:canon:targets"].text == f"Y{C} = 𝑀{C}T"
    assert cells["symbol:canon:held"].text == f"𝑀{C}H"
    assert cells["units:canon:primes"].text == f"units: g{C}/p"
    assert cells["units:canon:gens"].text == f"units: g{C}/g"
    assert cells["units:canon:detempering"].text == f"units: g{C}"
    assert cells["units:canon:targets"].text == f"units: g{C}"
    assert cells["matlabel:col:canon:detempering:0"].text == f"𝑀{C}𝐝{s1}"
    assert cells["matlabel:col:canon:commas:0"].text == f"𝑀{C}𝐜{s1}"
    assert cells["matlabel:col:canon:targets:0"].text == f"𝐲{C}{s1}"
    assert cells["matlabel:col:canon:held:0"].text == f"𝑀{C}𝐡{s1}"


def test_canonical_mapping_row_commas_symbol_keeps_subscript_under_unchanged():
    # under the V = C|U consolidation (projection on) the mapped-comma tile reads the mapped
    # UNROTATED vector list: the comma-basis C swaps to V, but the canonical subscript's own "C"
    # sentinel must survive the swap — 𝑀_C C → 𝑀_C V, never 𝑀_V V (the bug this guards).
    C = spreadsheet.SUBSCRIPT_C
    s = settings.defaults()
    s.update(form=True, form_tiles=True, symbols=True, header_symbols=True, projection=True, optimization=True)
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
        held_basis_ratios=("2/1", "5/4")).cells}
    # the "= 𝑂" equivalence drops under V (the column is no longer the bare vanishing comma basis),
    # for both rows; what matters here is the subscript-C surviving the comma C → V swap
    assert cells["symbol:canon:commas"].text == f"𝑀{C}V"           # subscript-C survives, comma C → V
    assert cells["symbol:mapping:commas"].text == "𝑀V"             # the main (non-canonical) row swaps, no subscript
    assert cells["matlabel:col:canon:commas:0"].text.startswith(f"𝑀{C}𝐯")  # the bold 𝐜 → 𝐯 in the header too


def test_canonical_mapping_row_carries_plain_text():
    # the canon row's EBK strings mirror the mapping row's notation with the canonical values: 𝑀_C a
    # covector stack (⟨ … ] rows, brace close), 𝐹 / 𝐹⁻¹𝐹 = 𝐼 genmap covector stacks, and the mapped
    # lists ket-lists (generator coords). The whole row must carry plain text (the gap this guards).
    s = settings.defaults()
    s.update(form=True, form_tiles=True, plain_text_values=True, ebk=True,
             generator_detempering=True, identity_objects=True, optimization=True)
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
        held_vectors=[(-1, 1, 0)], interest=((1, -2, 1),)).cells}
    assert cells["ptext:canon:primes"].text == "[⟨1 0 -4] ⟨0 1 4]}"   # 𝑀_C
    assert cells["ptext:canon:gens"].text == "[{1 -1] {0 1]}"          # 𝐹
    assert cells["ptext:canon:canongens"].text == "[{1 0] {0 1]}"      # 𝐹⁻¹𝐹 = 𝐼
    assert cells["ptext:canon:detempering"].text == "{[1 0} [-1 1}]"   # 𝑀_C·D = 𝐹 (a vector list)
    assert cells["ptext:canon:commas"].text == "[[0 0}]"               # 𝑀_C·C vanishes to 𝑂
    assert cells["ptext:canon:held"].text == "[[-1 1}]"                # 𝑀_C·H
    assert cells["ptext:canon:interest"].text == "[-3 2}"              # 𝑀_C·interest (stands alone)


def test_interest_is_a_top_level_toggle_after_the_tuning_tiles_group():
    # "other intervals of interest" is a standalone grey column (not part of the cyan
    # tuning region), so it owns a top-level toggle: built (implemented), default on, and
    # NOT a sub-control of the tuning group. It sits just after that group (whose last
    # member is colorization) and before generator detempering, mirroring the grid where
    # the interest column lands just right of the target intervals.
    items = dict(settings.SHOW_GROUPS)["specific tiles & controls"]
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


def test_interest_column_follows_its_own_toggle_not_tuning_tiles():
    # the interest column used to ride the tuning tiles toggle; now it has its own. Turning
    # tuning tiles off drops the cyan tuning columns but leaves the interest column standing.
    off_tuning = {c.id for c in _with(tuning_tiles=False).cells}
    assert "header:targets" not in off_tuning  # the tuning column goes...
    assert "header:interest" in off_tuning      # ...the interest column stays
    # and its own toggle hides it — header, axis and content — even when populated
    s = settings.defaults(); s["interest"] = False
    off_interest = {c.id for c in spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), s, interest=_INTEREST).cells}
    assert "header:interest" not in off_interest
    assert not any(c.startswith(("interest:", "cell:interest:", "cell:imapped:")) for c in off_interest)


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


def test_show_flags_gate_sub_controls_under_their_parent():
    # _resolve_show_flags (build's phase-1) ANDs each nested toggle with its parent: optimization /
    # weighting nest under tuning_tiles, alt_complexity under weighting, mnemonics under names. So a
    # sub-control can't render while its region is hidden, whatever its own toggle says.
    s = settings.defaults()
    s.update(tuning_tiles=False, optimization=True, weighting=True, alt_complexity=True,
             names=False, mnemonics=True)
    f = spreadsheet._resolve_show_flags(s, frozenset())
    assert not (f.optimization or f.weighting or f.alt_complexity)  # all gated off by tuning_tiles
    assert not f.mnemonics                                          # gated off by names
    s.update(tuning_tiles=True, names=True)  # parents on -> sub-controls follow their own toggle
    f = spreadsheet._resolve_show_flags(s, frozenset())
    assert f.optimization and f.weighting and f.alt_complexity and f.mnemonics


def test_show_flags_box_choosers_gate_on_the_collapsed_state():
    # the box-𝐋 / box-𝒄 in-tile choosers (lbox/cbox) show only while their column + row + tile are
    # open; collapsing any of them hides the chooser even with every toggle on.
    s = settings.defaults()
    s.update(tuning_tiles=True, weighting=True, alt_complexity=True, temperament_tiles=True)
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
    return CellBox(id=cid, x=0, y=0, w=10, h=10, kind="tuningvalue", text=text, **kw)


def test_changed_cell_ids_is_empty_for_an_unchanged_layout():
    lay = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    assert spreadsheet.changed_cell_ids(lay, lay) == frozenset()


def test_changed_cell_ids_flags_a_cell_whose_text_changed():
    old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
    new = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "9"))
    assert spreadsheet.changed_cell_ids(old, new) == frozenset({"b"})


def test_changed_cell_ids_ignores_a_cell_that_only_moved():
    # a cell shifted because a neighbour widened — same text, new box — has not changed value
    old = _diff_layout(CellBox("a", 0, 0, 10, 10, "tuningvalue", text="1"))
    new = _diff_layout(CellBox("a", 99, 50, 20, 20, "tuningvalue", text="1"))
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
    # a cell can flip a content FLAG (e.g. blank, when "quantities" off empties it) while its text is
    # unchanged; the signature must compare content flags, not text alone, so the highlight catches it
    old = _diff_layout(_diff_cell("a", "701.955"))
    new = _diff_layout(_diff_cell("a", "701.955", blank=True))
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
        CellBox("comma_minus:0", 0, 0, 10, 10, "comma_minus"),  # a - control
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
        _diff_cell("value", "2"),                                 # a value cell -> rings red when gone
        CellBox("ebkangle:vec:commas:1", 0, 0, 10, 10, "ebkangle"),  # marks / controls deleted with it
        CellBox("sep:targets:1", 0, 0, 10, 10, "vbar"),
        CellBox("grip:commas:1", 0, 0, 10, 10, "colgrip"),
        CellBox("comma_minus:1", 0, 0, 10, 10, "comma_minus"),
    )
    new = _diff_layout(_diff_cell("survivor", "1"), _diff_cell("added", "9"))
    assert spreadsheet.removed_cell_ids(old, new) == frozenset({"value"})


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


def _barbados_ss_identity(**overrides):
    # BARBADOS superspace WITH the identity objects shown — the JI mapping M_jL = I
    # (ss_vectors × ssprimes) and M_L over its own generators (ss_mapping × ssgens). Both gate
    # on the identity_objects setting (default off), so tests verifying their rendering opt in
    # here. See test_superspace_identity_objects_gate_on_identity_objects for the default-off gate.
    return _barbados_ss(identity_objects=True, **overrides)


def test_every_derived_matrix_row_greens_its_draft_column():
    # Adding an interval opens a DRAFT column that must read green top-to-bottom across EVERY value
    # row the column crosses — INCLUDING when it's the first interval of its kind (nothing committed
    # yet). Two bugs broke this: held/interest declared their derived rows only once an interval had
    # committed (so a first draft left ~9 rows blank), and the units row never emitted a draft cell
    # for any list. This guards both: under the maxed config (superspace + complexity weighting) the
    # FIRST held and FIRST interest draft green every value row of their column (units included), and
    # so do the target and comma drafts. BARBADOS lights the superspace block; minimax-ES (an all-
    # interval, complexity-weighted scheme) lights the prescaling / complexity rows.
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True  # every show toggle on, to maximise the rows in play
    barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    VALUE_ROWS = ("quantities", "vectors", "units", "mapping", "tuning", "just", "retune",
                  "prescaling", "complexity", "projection", "scaling_factors",
                  "ss_vectors", "ss_mapping", "ss_projection")
    STRUCTURAL = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "matlabel", "colgrip", "int_drag"}

    def assert_draft_greened(b, lst, committed, minimum):
        # every DECLARED value-row tile of `lst`'s column must hold a cell (value OR unit) at the
        # draft column — one slot past the `committed` sub-columns. A blank there is exactly the bug.
        lay = b.layout()
        left = {"held": b.held_left, "interest": b.interest_left,
                "targets": b.target_left, "commas": b.comma_left}[lst]
        dx = left(committed)
        checked = 0
        for rkey in VALUE_ROWS:
            if rkey not in b.rows or (rkey, lst) not in b.declared_tiles:
                continue
            top, h = b.rows[rkey].tile_top, b.rows[rkey].tile_h
            hit = any(abs(c.x - dx) < 7 and top - 1 <= c.y <= top + h + 1 and c.kind not in STRUCTURAL
                      for c in lay.cells)
            assert hit, f"first {lst} draft: row {rkey!r} is blank at the draft column (the bug)"
            checked += 1
        assert checked >= minimum, f"{lst}: only {checked} rows checked (config not fully lit?)"

    # the FIRST held and FIRST interest interval (nothing committed) — the exact reported failure
    b = spreadsheet._GridBuilder(barb, s, tuning_scheme="minimax-ES",
                                 held_vectors=(), pending_held=[None, None, None],
                                 interest=(), pending_interest=[None, None, None])
    assert b.show_superspace and "prescaling" in b.rows and "complexity" in b.rows
    assert_draft_greened(b, "held", 0, minimum=10)
    assert_draft_greened(b, "interest", 0, minimum=10)

    # the target and comma drafts green every value row too (the units row included — its draft cell
    # was also missing for targets). A target-based scheme so a target draft is allowed.
    b2 = spreadsheet._GridBuilder(barb, s,
                                  target_override=["3/2", "5/4"], pending_target=[None, None, None],
                                  pending_comma=[None, None, None])
    assert ("units", "targets") in b2.declared_tiles  # the units tile the targets draft must fill
    assert_draft_greened(b2, "targets", b2.k, minimum=6)
    assert_draft_greened(b2, "commas", b2.nc, minimum=6)


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


def test_nonstandard_domain_superspace_columns_head_their_quantities():
    # the superspace columns carry the same quantities-row headers as gens / primes: the
    # rL superspace generators as ~ratios (the detempering of M_L) and the dL superspace
    # primes, the column-header duals of the spine basis index. For BARBADOS over 2.3.13/5
    # the superspace is 2.3.5.13 (dL = 4) and M_L has rL = 3 generators.
    cells = {c.id: c for c in _barbados_ss().cells}
    assert [cells[f"ssqprime:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
    assert [cells[f"ssqgen:{g}"].text for g in range(3)] == ["2/1", "26/3", "130/3"]
    # the generators read ~approximate (genratio), the primes as white labels (prime)
    assert cells["ssqgen:0"].kind == "genratio"
    assert cells["ssqprime:0"].kind == "prime"
    # each header sits over its column's tuning cells (the 𝒈L / 𝒕L map below it), on the
    # quantities row (aligned with the gens/primes headers)
    assert cells["ssqgen:0"].x == cells["tuning:ssgen:0"].x
    assert cells["ssqprime:0"].x == cells["tuning:ssprime:0"].x
    assert cells["ssqgen:0"].y == cells["prime:0"].y == cells["ssqprime:0"].y


def test_nonstandard_domain_superspace_quantities_are_derived_read_only():
    # the superspace basis is derived from the domain, not user-edited, so its quantity
    # headers carry none of the ± controls the editable gens / primes columns ride
    cells = {c.id for c in _barbados_ss().cells}
    assert "ssqgen:0" in cells and "ssqprime:0" in cells
    # no superspace counterparts of gen_plus / gen_minus / plus / minus
    assert not any(c.startswith(("ssqgen_plus", "ssqgen_minus", "ssqprime_plus", "ssqprime_minus")) for c in cells)


def test_nonstandard_domain_off_omits_the_superspace_quantities():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()  # nonstandard_domain off
    cells = {c.id for c in spreadsheet.build(state, s).cells}
    assert "ssqgen:0" not in cells
    assert "ssqprime:0" not in cells


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
    assert cells["count:ssgens"].text == "\U0001D45FL = 3"   # 𝑟L
    assert cells["count:ssprimes"].text == "\U0001D451L = 4"  # 𝑑L


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
    # targets}, the real M_L mapping at ss_mapping × ssprimes, the four ssgens/ssprimes
    # tuning-family tiles) has a backing grey panel — the same machinery the rest of the
    # grid uses. M_L over its own generators (ss_mapping × ssgens) is an identity object, gated
    # on identity_objects (see test_superspace_identity_objects_gate_on_identity_objects).
    lay = _barbados_ss()
    blocks = {b.id for b in lay.blocks}
    expected = {
        "block:ss_vectors:quantities", "block:ss_vectors:primes",
        "block:ss_vectors:commas", "block:ss_vectors:targets",
        "block:ss_mapping:ssprimes",
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
        "toggle:tile:ss_mapping:ssprimes",
        "toggle:tile:tuning:ssgens", "toggle:tile:tuning:ssprimes",
        "toggle:tile:just:ssprimes", "toggle:tile:retune:ssprimes",
    }
    assert expected <= cells


def test_superspace_columns_get_their_fold_toggles_in_the_header_band():
    # the ssgens / ssprimes columns are collapsible like every other content column
    cells = {c.id for c in _barbados_ss().cells}
    assert {"toggle:col:ssgens", "toggle:col:ssprimes"} <= cells


def _barbados_proj(held_basis_ratios=("2", "13/5"), **overrides):
    # BARBADOS superspace with the projection box on and a full held basis ({2/1, 13/5} pins P_L);
    # held_basis_ratios=() leaves it under-held (P_L dashed), like _proj_build for the on-domain row.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    s["projection"] = True
    s.update(overrides)
    return spreadsheet.build(state, s, held_basis_ratios=held_basis_ratios)


def test_superspace_projection_row_renders_PL_over_the_superspace_primes():
    # the projection toggle adds a third superspace row band — the superspace projection P_L = G_L·M_L,
    # a dL × dL covector stack over the superspace primes (the chapter-9 analogue of the on-domain P).
    # It seats just below the superspace mapping and above the on-domain projection row.
    cells = {c.id: c for c in _barbados_proj().cells}
    assert cells["label:ss_projection"].text == "superspace\nprojection"
    # dL = 4 rows tall (one covector per superspace prime)
    assert cells["label:ss_projection"].h == 4 * spreadsheet.ROW_H
    # ordered: ss_mapping < ss_projection < projection
    assert cells["label:ss_mapping"].y < cells["label:ss_projection"].y < cells["label:projection"].y
    # the full 4 × 4 P_L grid renders over the ssprimes column
    assert {f"cell:ss_projection:ssprimes:{i}:{j}" for i in range(4) for j in range(4)} <= set(cells)
    # P_L for BARBADOS held by {2/1, 13/5}: [[1,2/3,0,0],[0,0,0,0],[0,-2/3,1,0],[0,2/3,0,1]]
    assert cells["cell:ss_projection:ssprimes:0:0"].text == "1"
    assert cells["cell:ss_projection:ssprimes:0:1"].text == "2/3"
    assert cells["cell:ss_projection:ssprimes:2:2"].text == "1"
    assert cells["cell:ss_projection:ssprimes:3:1"].text == "2/3"
    # the cells share the ssprimes column x with the superspace mapping M_L above
    assert cells["cell:ss_projection:ssprimes:0:0"].x == cells["cell:ss_mapping:ssprimes:0:0"].x


def test_superspace_projection_row_renders_the_embedding_and_projected_lists():
    # the superspace projection row carries the full tile set, paralleling the on-domain projection row:
    # the embedding G_L (ssgens), P_L·B_Ls (primes), P_L·V (commas/V), P_L·T_L (targets) — each P_L applied
    # to that column's lifted vectors. BARBADOS over 2.3.13/5 (dL=4, rL=3, d=3) held by {2/1, 13/5}.
    cells = {c.id: c for c in _barbados_proj().cells}
    # G_L the embedding, dL × rL = 4 × 3 (a vector list over the superspace generators)
    assert {f"cell:ss_embed:{i}:{g}" for i in range(4) for g in range(3)} <= set(cells)
    assert cells["cell:ss_embed:0:0"].text == "1" and cells["cell:ss_embed:0:1"].text == "1/3"
    # P_L·B_Ls the projected subspace basis, dL-tall over the d = 3 domain-element columns
    assert {f"cell:ss_proj_bls:{e}:{p}" for e in range(3) for p in range(4)} <= set(cells)
    assert cells["cell:ss_proj_bls:0:0"].text == "1"     # P_L·2/1 = 2/1 (held)
    assert cells["cell:ss_proj_bls:1:0"].text == "2/3"   # P_L·3 is tempered
    # P_L·V over the consolidated V = C|U column: the comma half vanishes (0), the unchanged half is held
    assert {f"cell:ss_proj_v:{p}:0" for p in range(4)} <= set(cells)
    assert [cells[f"cell:ss_proj_v:{p}:0"].text for p in range(4)] == ["0", "0", "0", "0"]  # P_L·comma = 0
    # P_L·T_L the projected target list, dL-tall over the targets, not dashed (a full rational projection)
    assert any(c.startswith("cell:ss_proj_pt:") for c in cells)
    assert cells["cell:ss_proj_pt:0:0"].text != spreadsheet.DASH
    # the tiles carry their mockup captions
    assert cells["caption:ss_projection:ssgens"].text == "superspace generator embedding"
    assert cells["caption:ss_projection:primes"].text == "superspace projected subspace basis elements"


def test_superspace_projection_detempering_tile_renders_when_shown():
    # P_L·D_L (the projected lifted domain detempering, dL × r) rides the generator-detempering column,
    # the chapter-9 analogue of the on-domain P·D — shown only when that column is on, dashed-aware.
    cells = {c.id: c for c in _barbados_proj(generator_detempering=True).cells}
    assert {f"cell:ss_proj_pd:{i}:{p}" for i in range(2) for p in range(4)} <= set(cells)  # dL × r = 4 × 2
    assert cells["cell:ss_proj_pd:0:0"].text != spreadsheet.DASH  # a full rational projection, not dashed
    assert cells["caption:ss_projection:detempering"].text == "projected generator detempering in superspace"
    # absent when the generator-detempering column is off (parity with the on-domain P·D)
    off = {c.id for c in _barbados_proj().cells}
    assert not any(c.startswith("cell:ss_proj_pd:") for c in off)


def test_superspace_projection_extra_tiles_dash_when_under_held():
    # every projected tile dashes in lockstep with P_L when the tuning isn't a full rational projection
    cells = {c.id: c for c in _barbados_proj(held_basis_ratios=()).cells}
    assert cells["cell:ss_embed:0:0"].text == spreadsheet.DASH       # G_L dashed
    assert cells["cell:ss_proj_bls:0:0"].text == spreadsheet.DASH    # P_L·B_Ls dashed


def test_superspace_projection_extra_tiles_absent_without_projection():
    # additive-only: the embedding / projected-list tiles need the projection toggle, like P_L itself
    cells = {c.id for c in _barbados_ss().cells}  # projection off
    assert not any(c.startswith(("cell:ss_embed:", "cell:ss_proj_bls:", "cell:ss_proj_v:",
                                 "cell:ss_proj_pt:", "cell:ss_proj_pd:")) for c in cells)


def test_superspace_projection_row_dashes_when_under_held():
    # under-held (P_L undetermined, service returns None): every cell an em-dash — in lockstep with
    # the on-domain projection P, never asserting a projection the optimum doesn't have.
    cells = {c.id: c for c in _barbados_proj(held_basis_ratios=()).cells}
    assert cells["cell:ss_projection:ssprimes:0:0"].text == spreadsheet.DASH
    assert cells["cell:ss_projection:ssprimes:3:3"].text == spreadsheet.DASH


def test_superspace_projection_row_absent_without_the_projection_toggle():
    # additive-only: the superspace mapping shows (nonstandard domain on) but P_L needs the projection
    # toggle too — off, it leaves no trace
    cells = {c.id for c in _barbados_ss().cells}  # projection off
    assert "label:ss_mapping" in cells  # the superspace block is up
    assert "label:ss_projection" not in cells
    assert not any(c.startswith("cell:ss_projection:") for c in cells)


def test_superspace_projection_row_absent_on_a_standard_domain():
    # a standard prime domain has no superspace, so no P_L even with the projection box on — only
    # the on-domain P renders
    cells = {c.id for c in _proj_build(("2", "5/4")).cells}  # meantone, projection on, standard domain
    assert "cell:proj:0:0" in cells  # the on-domain projection P is there
    assert "label:ss_projection" not in cells
    assert not any(c.startswith("cell:ss_projection:") for c in cells)


def test_superspace_projection_quantities_spine_lists_the_superspace_primes():
    # the superspace projection's quantities spine lists the dL superspace primes (the mockup's
    # α, β, γ … are placeholders for them), one per row — exactly like the superspace interval-
    # vectors spine above it. For BARBADOS over 2.3.13/5 the superspace is 2.3.5.13.
    cells = {c.id: c for c in _barbados_proj().cells}
    assert [cells[f"ss_proj_basis:{p}"].text for p in range(4)] == ["2", "3", "5", "13"]
    # the same superspace primes the ss_vectors spine shows (both rows are indexed by them)
    assert [cells[f"ss_proj_basis:{p}"].text for p in range(4)] == [cells[f"ss_basis:{p}"].text for p in range(4)]
    # spine-centred in the quantities column, sharing its x with the superspace mapping spine above
    assert cells["ss_proj_basis:0"].x == cells["ss_basis:0"].x
    assert cells["ss_proj_basis:0"].w == spreadsheet.COL_W


def test_superspace_projection_units_column_reads_superspace_prime():
    # P_L = G_L·M_L is a superspace-prime → superspace-prime operator (dL × dL), so its units column
    # reads pᵢ/ down the dL rows — true primes, exactly like the M_jL / B_L rows above it, NEVER the
    # on-domain basis element b. The units COLUMN rides the domain_units toggle.
    cells = {c.id: c for c in _barbados_proj(domain_units=True).cells}
    assert cells["ucol:ss_projection:0"].text == "p₁/"
    assert cells["ucol:ss_projection:3"].text == "p₄/"


def test_superspace_projection_row_carries_the_full_projected_tile_set():
    # the row is the chapter-9 analogue of the WHOLE on-domain projection row: not just the P_L matrix
    # but the embedding G_L and P_L applied to every column's lifted vectors — P_L·B_Ls / P_L·D_L /
    # P_L·V / P_L·T_L (the superspace twins of G / P·D / P·V / P·T).
    cells = {c.id: c for c in _barbados_proj(generator_detempering=True).cells}
    assert {f"cell:ss_embed:{i}:{g}" for i in range(4) for g in range(3)} <= set(cells)        # G_L (dL × rL)
    assert {f"cell:ss_proj_bls:{e}:{p}" for e in range(3) for p in range(4)} <= set(cells)      # P_L·B_Ls (d × dL)
    assert {f"cell:ss_proj_pd:{i}:{p}" for i in range(2) for p in range(4)} <= set(cells)        # P_L·D_L (r × dL)
    assert "cell:ss_proj_pt:0:0" in cells                                                         # P_L·T_L
    # P_L·V over the consolidated V = C|U column: the comma half vanishes (every entry zero)
    assert all(cells[f"cell:ss_proj_v:{p}:0"].text == "0" for p in range(4))


def test_superspace_projection_embedding_G_L_matches_the_service():
    # G_L = the dL × rL superspace generator embedding (the embedding factor of P_L = G_L·M_L); the
    # grid cells read it cell-for-cell, over the superspace-generators column
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    gl = service.superspace_tuning_embedding(state, ("2", "13/5"))
    cells = {c.id: c for c in _barbados_proj().cells}
    assert [[cells[f"cell:ss_embed:{i}:{g}"].text for g in range(3)] for i in range(4)] == [list(r) for r in gl]


def test_superspace_projection_projected_basis_matches_P_L_times_B_L():
    # P_L·B_Ls projects each domain basis element (a superspace vector — the columns of B_L) through P_L
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pl = service.superspace_projection_matrix_rationals(state, ("2", "13/5"))
    expected = service.project_vectors(pl, service.basis_in_superspace(state.domain_basis))
    cells = {c.id: c for c in _barbados_proj().cells}
    assert [[cells[f"cell:ss_proj_bls:{e}:{p}"].text for p in range(4)] for e in range(3)] \
        == [[str(x) for x in v] for v in expected]


def test_superspace_projection_extra_tiles_carry_captions_symbols_and_units():
    cells = {c.id: c for c in _barbados_proj(generator_detempering=True, names=True, symbols=True, units=True).cells}
    assert cells["caption:ss_projection:ssgens"].text == "superspace generator embedding"
    assert cells["caption:ss_projection:primes"].text == "superspace projected subspace basis elements"
    assert cells["caption:ss_projection:detempering"].text == "projected generator detempering in superspace"
    assert cells["caption:ss_projection:targets"].text == "projected target interval list in superspace"
    # the commas tile reads as the consolidated V (unrotated vector list) under the projection view
    assert cells["caption:ss_projection:commas"].text == "projected unrotated vector list in superspace"
    assert cells["symbol:ss_projection:ssgens"].text == "GL"                  # G_L
    assert cells["symbol:ss_projection:primes"].text == spreadsheet.SYMBOLS[("ss_projection", "primes")]  # P_L B_L (no trailing s)
    assert cells["units:ss_projection:ssgens"].text == "units: p/gL"            # G_L: superspace prime per superspace gen
    assert cells["units:ss_projection:primes"].text == "units: p/b"
    assert cells["units:ss_projection:detempering"].text == "units: p"


def test_superspace_projection_extra_tiles_dash_when_under_held():
    # the whole row dashes in lockstep with P_L when the tuning isn't a full rational projection
    cells = {c.id: c for c in _barbados_proj(held_basis_ratios=(), generator_detempering=True).cells}
    assert cells["cell:ss_embed:0:0"].text == spreadsheet.DASH        # G_L
    assert cells["cell:ss_proj_bls:0:0"].text == spreadsheet.DASH     # P_L·B_Ls
    assert cells["cell:ss_proj_pd:0:0"].text == spreadsheet.DASH      # P_L·D_L
    assert cells["cell:ss_proj_pt:0:0"].text == spreadsheet.DASH      # P_L·T_L


def test_superspace_projection_extra_tiles_absent_without_projection():
    # additive-only: with the projection toggle off, none of the projected tiles leave a trace
    cells = {c.id for c in _barbados_ss(generator_detempering=True).cells}  # projection off
    assert not any(c.startswith(("cell:ss_embed:", "cell:ss_proj_bls:", "cell:ss_proj_pd:",
                                 "cell:ss_proj_v:", "cell:ss_proj_pt:", "cell:ss_proj_ph:",
                                 "cell:ss_proj_pi:")) for c in cells)


def test_superspace_projection_emits_a_plain_text_band():
    # plain_text_values on: P_L gets its own EBK string band under the tile, like M_L / M_jL / B_L and
    # the on-domain P — P_L was the sole matrix row missing one (PTEXT_ROWS + plain_text_values parity).
    cells = {c.id for c in _barbados_proj(plain_text_values=True).cells}
    assert "ptext:ss_projection:ssprimes" in cells
    # absent without the projection toggle: the superspace mapping's band shows, P_L's does not
    off = {c.id for c in _barbados_ss(plain_text_values=True).cells}  # projection off
    assert "ptext:ss_mapping:ssprimes" in off
    assert "ptext:ss_projection:ssprimes" not in off


def test_superspace_projection_every_tile_emits_a_plain_text_band():
    # parity with the on-domain projection row: EVERY tile carries a plain-text EBK band when
    # plain_text_values is on — not just P_L, but the embedding G_L and each projected list.
    cells = {c.id for c in _barbados_proj(plain_text_values=True, generator_detempering=True).cells}
    for col in ["ssgens", "ssprimes", "primes", "detempering", "commas", "targets"]:
        assert f"ptext:ss_projection:{col}" in cells, col


def test_superspace_projection_caption_symbol_and_units_when_named():
    # names + symbols + units on: the tile carries the "superspace projection" caption, the in-tile
    # 𝒑Lᵢ covector row labels, the p/p units line, and the P_L = G_L M_L symbol/equivalence
    cells = {c.id: c for c in _barbados_proj(names=True, symbols=True, header_symbols=True, units=True).cells}
    assert cells["caption:ss_projection:ssprimes"].text == "superspace projection"
    assert "matlabel:row:ss_projection:ssprimes:0" in cells  # 𝒑L₁ row label
    # the units line under the tile reads p/p (a superspace-prime operator, like M_jL above it)
    assert cells["units:ss_projection:ssprimes"].text == "units: p/p"


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
    assert cells["symbol:ss_mapping:ssprimes"].text == "\U0001D440L"  # 𝑀L


def test_B_L_tile_has_a_caption_and_symbol():
    # the basis-embedding tile (each domain element as a superspace vector) gets a caption
    # + an upright bold B with subscript L (parallel to C for the comma basis, T for the
    # target list — upright capitals naming an interval basis)
    cells = {c.id: c for c in _barbados_ss(names=True, symbols=True).cells}
    assert cells["caption:ss_vectors:primes"].text == "basis change matrix"
    assert cells["symbol:ss_vectors:primes"].text == "BL"


def test_B_L_units_line_reads_superspace_prime_over_domain_element():
    # B_L's units line is in output/input order: a superspace prime (p) per domain element (b) —
    # p/b — matching the rest of the p-coordinate ss_vectors row (M_jL p/p, C_L/T_L/H_L p) and the
    # gL/b of its M_s→L sibling (the superspace coordinate leads), NOT the reversed b/p.
    cells = {c.id: c for c in _barbados_ss(units=True).cells}
    assert cells["units:ss_vectors:primes"].text == "units: p/b"
    # M_jL = I lives wholly in the superspace (the dL×dL identity over superspace primes), so it
    # reads p/p — like the on-domain M_j = I, NEVER the on-domain basis element b (the tile is gated
    # on identity_objects, so opt in via _barbados_ss_identity)
    id_cells = {c.id: c for c in _barbados_ss_identity(units=True).cells}
    assert id_cells["units:ss_vectors:ssprimes"].text == "units: p/p"


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


def test_standard_domain_with_toggle_on_shows_no_superspace_but_enables_editing():
    # checking the nonstandard-domain toggle over a STILL-standard prime limit must not reveal
    # the superspace columns/rows (the superspace would merely clone the domain — nothing to
    # show yet). The one thing it changes: the domain basis becomes editable. The header stays
    # "domain primes" (no nonprime yet) and the superspace appears later, once one is entered.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5 meantone — standard prime limit
    s = settings.defaults() | {"nonstandard_domain": True, "counts": True}
    lay = spreadsheet.build(state, s)
    cells = {c.id: c for c in lay.cells}
    ids = {c.id for c in lay.cells} | {b.id for b in lay.blocks} | {ln.id for ln in lay.lines}
    # no superspace trace: no columns, rows, counts, spine, or cells keyed by the ss prefixes
    assert not any(tok in i for i in ids
                   for tok in ("ssgens", "ssprimes", "ss_vectors", "ss_mapping", "ss_basis",
                               "ssgen", "ssprime"))
    # the toggle DID make the basis editable — but with no nonprime the header keeps "domain primes"
    assert cells["prime:0"].kind == "elementcell"
    assert cells["header:primes"].text == "domain\nprimes"


def test_nonstandard_all_prime_subgroup_with_toggle_on_shows_no_superspace():
    # the subtlety: being nonstandard isn't enough — a subgroup that is still ALL PRIMES (e.g.
    # 2.5.7, which merely skips 3) has no nonprime element to embed, so neither the superspace
    # columns/rows nor the matching damage-tile approach radio appear. Only a basis carrying a
    # nonprime (2.3.13/5) triggers them. The toggle's editability still applies; the header stays
    # "domain primes" (every element IS a prime), NOT "domain basis elements" — that waits on a nonprime.
    state = service.from_temperament_data("2.5.7 [⟨1 0 0] ⟨0 1 1]}")
    assert not service.domain_has_nonprimes(state.domain_basis)  # all-prime, but...
    assert not service.is_standard_domain(state.domain_basis)    # ...still a nonstandard subgroup
    s = settings.defaults() | {"nonstandard_domain": True}
    lay = spreadsheet.build(state, s)
    cells = {c.id: c for c in lay.cells}
    ids = {c.id for c in lay.cells} | {b.id for b in lay.blocks} | {ln.id for ln in lay.lines}
    assert not any(tok in i for i in ids
                   for tok in ("ssgens", "ssprimes", "ss_vectors", "ss_mapping", "ss_basis",
                               "ssgen", "ssprime"))
    assert cells["prime:0"].kind == "elementcell"
    assert cells["header:primes"].text == "domain\nprimes"  # all-prime ⇒ still "domain primes"


def test_nonprime_based_approach_collapses_the_entire_superspace():
    # the nonprime-based approach honors the basis as-is and never converts to the prime
    # superspace, so the WHOLE superspace block — both columns and both rows (embedding B_L and
    # mapping M_L) plus the superspace tuning maps — collapses. Only neutral / prime-based show
    # it. The approach radio itself stays (gated only on the nonprime element) so it can be
    # switched back; see test_build_threads_nonprime_approach_through_to_the_tuning.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"nonstandard_domain": True}
    lay = spreadsheet.build(state, s, nonprime_approach="nonprime-based")
    ids = {c.id for c in lay.cells} | {b.id for b in lay.blocks} | {ln.id for ln in lay.lines}
    assert not any(tok in i for i in ids
                   for tok in ("ssgens", "ssprimes", "ss_vectors", "ss_mapping", "ss_basis",
                               "ssgen", "ssprime"))


def _barbados_prescaling(approach="", nonstandard=True):
    # BARBADOS with a complexity-weighted scheme (so the prescaling + complexity rows show) and the
    # nonstandard-domain toggle. TILT minimax-C weights damage by complexity → both rows present.
    # symbols/captions/equivalences ON: the superspace shift relocates the bare prescaler's row
    # labels and "𝑋 = 𝐿" equivalence into ss-primes, so these layers must resolve there without
    # KeyError (they once did, on the hardcoded (prescaling, primes) row_top / equivalence keys).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"nonstandard_domain": nonstandard, "weighting": True,
                               "symbols": True, "header_symbols": True, "captions": True, "equivalences": True,
                               "plain_text_values": True, "presets": True}
    return spreadsheet.build(state, s, tuning_scheme="TILT minimax-C", nonprime_approach=approach)


def test_superspace_prescaler_interactivity_and_controls_shift_to_ss_primes():
    # Under the shift the bare prescaler's INTERACTIVITY + controls move to ss-primes, while the
    # domain-primes 𝐿·B_Ls product becomes a read-only matrix with its own row headers.
    cells = {c.id: c for c in _barbados_prescaling().cells}
    # the bare prescaler's plain text stays editable — now in ss-primes; the 𝐿·B_Ls plain text is
    # read-only, and reads ⟨[…⟩ …] (a matrix of kets like B_L), NOT the backwards bare-prescaler stack
    assert cells["ptext:prescaling:ssprimes"].kind == "ptextedit"
    assert cells["ptext:prescaling:primes"].kind == "ptext"
    assert cells["ptext:prescaling:primes"].text.startswith("⟨[") and cells["ptext:prescaling:primes"].text.endswith("]")
    # 𝐿·B_Ls is a matrix of kets, so it takes COLUMN headers (one per domain element, like B_L),
    # NOT the bare prescaler's row headers; the bare prescaler (ss-primes) keeps its dL row headers
    assert sum(1 for i in cells if i.startswith("matlabel:row:prescaling:primes:")) == 0
    assert sum(1 for i in cells if i.startswith("matlabel:col:prescaling:primes:")) == 3
    assert sum(1 for i in cells if i.startswith("matlabel:row:prescaling:ssprimes:")) == 4
    # the predefined-prescalers chooser follows the bare prescaler into the ss-primes column
    assert "preset:prescaler" in cells
    assert abs(cells["preset:prescaler"].x - cells["header:ssprimes"].x) < abs(cells["preset:prescaler"].x - cells["header:primes"].x)


def test_superspace_shifts_the_complexity_prescaler_into_the_ss_primes_column():
    # The chapter-9 prescaler shift: once the superspace primes column appears (neutral / prime-
    # based over a nonprime domain), the bare complexity prescaler moves one column LEFT into
    # ss-primes as the "(superspace) complexity prescaler" (the dL log-prime diagonal over the TRUE
    # primes), and the domain-primes tile becomes "complexity prescaled subspace basis elements"
    # (𝐿·B_Ls). The same in the next row: the prime complexity map moves to ss-primes, the domain-
    # primes complexity becomes the subspace basis element complexity map.
    cells = {c.id: c for c in _barbados_prescaling().cells}
    # the bare prescaler's "= log-prime matrix" NAME (equivalences on) lands on the ss-primes tile —
    # NOT on the domain-primes 𝐿·B_Ls product (a product prints no "= …")
    assert cells["caption:prescaling:ssprimes"].text == "(superspace) complexity prescaler = log-prime matrix"
    assert cells["caption:prescaling:primes"].text == "complexity prescaled subspace basis elements"
    assert cells["caption:complexity:ssprimes"].text == "domain prime complexity map"
    assert cells["caption:complexity:primes"].text == "subspace basis element complexity map"
    # the prescaling matrices lift to dL = 4 rows (the superspace primes 2.3.5.13), not d = 3: the
    # bare ss-primes prescaler is dL×dL, so its 4th diagonal entry (row 3, col 3) exists and is
    # log-prime over the TRUE primes — log₂13 ≈ 3.700, the new prime 13 disentangled from 13/5.
    assert "cell:prescaling:ssprimes:3:3" in cells
    assert abs(float(cells["cell:prescaling:ssprimes:3:3"].text) - 3.7004) < 0.01  # log₂13
    # the lifted domain-primes tile 𝐿·B_Ls is dL-tall too (4 rows over the d = 3 domain elements)
    assert "cell:prescaling:primes:3:0" in cells
    # the displayed complexities ARE ‖𝐿·(B_L·v)‖ — the corrected get_complexity. The subspace basis
    # element complexity of 13/5 prime-factors to log₂(13·5) = 6.022 (NOT log₂5 = 2.322, the
    # out-of-limit 13 dropped — the bug fixed by passing domain_basis); the ss-primes prime
    # complexity map is log-prime over the true primes, so the 3rd entry is log₂5 = 2.322.
    assert cells["complexity:prime:2"].text == "6.022"     # 13/5 subspace basis element
    assert cells["complexity:ssprime:2"].text == "2.322"   # the true prime 5


def test_superspace_prescaler_shift_only_for_neutral_and_prime_based():
    # nonprime-based keeps the atomic domain prescaler (it doesn't prime-factor), so NO ss-primes
    # prescaling/complexity tiles and the domain-primes tile keeps its plain "complexity prescaler"
    # name. A standard domain (toggle off) likewise shows no shift.
    for approach in ("nonprime-based",):
        cells = {c.id: c for c in _barbados_prescaling(approach=approach).cells}
        assert not any(cid.startswith("cell:prescaling:ssprimes:") for cid in cells)
        # the domain-primes tile keeps the plain bare-prescaler name (it stays the bare 𝐿 here),
        # NOT the shifted "complexity prescaled subspace basis elements" product caption
        assert cells["caption:prescaling:primes"].text.startswith("complexity prescaler")
    off = {c.id: c for c in _barbados_prescaling(nonstandard=False).cells}
    assert not any(cid.startswith("cell:prescaling:ssprimes:") for cid in off)
    assert off["caption:prescaling:primes"].text.startswith("complexity prescaler")


def test_prime_based_shifts_generator_editing_to_superspace():
    # In the prime-based approach the optimization solves the superspace generators 𝒈L and projects
    # them to 𝒈, so 𝒈L (ssgens) is the EDITABLE generator map and 𝒈 (gens) is its READ-ONLY
    # projection — editing + the tuning chooser move there. Neutral optimizes in the domain, so it
    # keeps editing on 𝒈 (only prime-based shifts; the prescaler/complexity shift, by contrast,
    # happens for both — complexity is superspace for both, but only prime-based OPTIMIZES there).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"nonstandard_domain": True, "plain_text_values": True, "presets": True}
    prime = {c.id: c for c in spreadsheet.build(state, s, nonprime_approach="prime-based").cells}
    assert {prime[i].kind for i in prime if i.startswith("tuning:gen:")} == {"tuningvalue"}      # 𝒈 read-only
    assert {prime[i].kind for i in prime if i.startswith("tuning:ssgen:")} == {"gentuningcell"}  # 𝒈L editable
    assert prime["ptext:tuning:gens"].kind == "ptext"
    assert prime["ptext:tuning:ssgens"].kind == "ptextedit"
    assert "preset:tuning:ssgens" in prime  # the tuning-scheme chooser copy follows to 𝒈L
    # neutral: no generator shift — 𝒈 stays editable, 𝒈L read-only
    neutral = {c.id: c for c in spreadsheet.build(state, s, nonprime_approach="").cells}
    assert {neutral[i].kind for i in neutral if i.startswith("tuning:gen:")} == {"gentuningcell"}
    assert {neutral[i].kind for i in neutral if i.startswith("tuning:ssgen:")} == {"tuningvalue"}


def test_approach_radio_band_only_for_a_nonprime_domain():
    # the nonstandard-domain approach radio gets a reserved band above the optimization box — a bold
    # boxtitle plus lay.approach_box (the x/y/w/h app.py positions refs["approach"] over) — only
    # when the basis carries a nonprime element, the same gate as the superspace. (Before this it
    # was parked in the frozen corner, clipped and invisible.)
    on = settings.defaults() | {"nonstandard_domain": True}
    nonprime = spreadsheet.build(service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"), on)
    assert nonprime.approach_box is not None
    title = {c.id: c for c in nonprime.cells}["optimization:approach:title"]
    assert title.kind == "boxtitle" and title.text == "nonstandard domain approach"
    # a standard prime limit: no nonprime → no band, no title
    std = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), on)
    assert std.approach_box is None
    assert "optimization:approach:title" not in {c.id for c in std.cells}
    # a nonstandard but all-prime subgroup (2.5.7): still no band — it needs a nonprime
    sub = spreadsheet.build(service.from_temperament_data("2.5.7 [⟨1 0 0] ⟨0 1 1]}"), on)
    assert sub.approach_box is None


# ---------------------------------------------------------------------------
# Phase 4E.1 — B_L (basis embedding) cells in (ss_vectors, primes). The new
# tile renders each domain element as a dL-tall ket of integer vector
# coefficients over the superspace primes; the cells share the existing
# prime-column gridlines with the vectors row above and the ss_vectors band's
# spine basis index to the left.
# ---------------------------------------------------------------------------


def test_B_L_emits_one_cell_per_superspace_prime_row_and_domain_element_col():
    # the basis-embedding matrix B_L lives in (ss_vectors, primes) — each domain element is
    # one COLUMN (over the d domain primes column axis) of dL components, each component the
    # integer vector coefficient over the superspace primes (rows). For BARBADOS over
    # 2.3.13/5 with superspace (2, 3, 5, 13):
    #   element 2  (col 0): (1, 0, 0, 0)   — 2 is the first superspace prime
    #   element 3  (col 1): (0, 1, 0, 0)   — 3 is the second
    #   element 13/5 (col 2): (0, 0, -1, 1) — −1 in the 5-row, +1 in the 13-row
    cells = {c.id: c for c in _barbados_ss().cells}
    expected_by_element = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
    for elem_idx, vector in enumerate(expected_by_element):
        for ss_prime_idx, value in enumerate(vector):
            assert cells[f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}"].text == str(value)


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


def test_B_L_absent_over_a_standard_prime_domain():
    # a standard prime-limit domain IS its own superspace (B_L would be the identity), so the
    # embedding tile has nothing to add — the superspace stays hidden even with the toggle on.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("cell:ss_vectors:primes:") for cid in cids)


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
        for ss_prime_idx, value in enumerate(row):
            assert cells[f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}"].text == str(value)


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


def test_M_L_absent_over_a_standard_prime_domain():
    # a standard prime-limit domain IS its own superspace (M_L would just be M), so the
    # superspace mapping tile stays hidden even with the toggle on.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith("cell:ss_mapping:ssprimes:") for cid in cids)


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
    cells = {c.id: c for c in _barbados_ss(symbols=True, header_symbols=True).cells}
    for i in range(3):  # rL=3 rows
        sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
        assert cells[f"matlabel:row:ss_mapping:ssprimes:{i}"].text == f"\U0001D48EL{sub_i}"


# ---------------------------------------------------------------------------
# Phase 4E.3 — M_jL = I, the superspace JI mapping: a tile in the superspace-
# interval-vectors row at its ssprimes column (ss_vectors × ssprimes). Each superspace
# prime is its own basis element, so M_jL is the dL × dL identity; it reuses the
# matrix-frame pattern (per-row ⟨ … ] + outer ebktop / ebkbrace).
# ---------------------------------------------------------------------------


def test_M_jL_emits_a_cell_per_ss_prime_row_and_ss_prime_col_as_identity():
    # M_jL = I: each prime is its own basis element. Read-only "mapped" cells (a
    # derived display, same kind the canonical-form row and the mapped-target tiles
    # use — not the editable "mapping" kind, since the user can't edit identity).
    cells = {c.id: c for c in _barbados_ss_identity().cells}
    for i in range(4):  # dL = 4
        for j in range(4):
            expected = "1" if i == j else "0"
            assert cells[f"cell:ss_vectors:ssprimes:{i}:{j}"].text == expected
            assert cells[f"cell:ss_vectors:ssprimes:{i}:{j}"].kind == "mapped"


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
    cells = {c.id: c for c in _barbados_ss_identity().cells}
    for i in range(4):  # dL=4 covector rows
        assert cells[f"bracket:ss_vec_jmap:{i}:l"].text == spreadsheet.MAP_BRACKETS[0]
        assert cells[f"bracket:ss_vec_jmap:{i}:r"].text == spreadsheet.MAP_BRACKETS[1]
    assert "ebktop:ss_vec_jmap" in cells
    assert "ebkangle:ss_vec_jmap" in cells


def test_M_jL_tile_carries_caption_and_symbol():
    # caption: "superspace JI mapping", symbol: 𝑀ⱼₗ — math-italic M + subscript j + ₗ
    # (parallel to M_L's 𝑀ₗ). With ALPHABET subscripts we use j (U+2C7C is the latin j sub)
    cells = {c.id: c for c in _barbados_ss_identity(names=True, symbols=True).cells}
    assert cells["caption:ss_vectors:ssprimes"].text == "superspace JI mapping"
    # 𝑀 = U+1D440. Subscript j = U+2C7C. Subscript L = U+2097.
    assert cells["symbol:ss_vectors:ssprimes"].text == "\U0001D440jL"


def test_M_jL_tile_row_labels_each_covector():
    # each row labelled 𝒎ⱼₗᵢ — math-italic 𝒎 + subscript j (U+2C7C) + ₗ + index
    cells = {c.id: c for c in _barbados_ss_identity(symbols=True, header_symbols=True).cells}
    for i in range(4):  # dL=4 rows
        sub_i = str(i + 1).translate(_SUBSCRIPT_DIGITS)
        assert cells[f"matlabel:row:ss_vectors:ssprimes:{i}"].text == f"\U0001D48EjL{sub_i}"


def test_M_jL_tile_carries_identity_equivalence():
    # equivalences on adds " = 𝐼" after the 𝑀ⱼₗ symbol — the trivial-identity equation
    cells = {c.id: c for c in _barbados_ss_identity(symbols=True, equivalences=True).cells}
    sym = cells["symbol:ss_vectors:ssprimes"].text
    assert sym == "\U0001D440jL = \U0001D43C"  # "𝑀jL = 𝐼" — math-italic I = U+1D43C


def test_superspace_identity_objects_gate_on_identity_objects():
    # the two built superspace identity objects gate on identity_objects: the JI mapping
    # M_jL = I (ss_vectors × ssprimes) and M_L over its own generators (ss_mapping × ssgens).
    # With the superspace on but identity_objects off (the default) neither renders, while the
    # real B_L (ss_vectors × primes) and M_L (ss_mapping × ssprimes) are unaffected. There is no
    # separate JI-mapping row band — M_jL = I is a tile inside the superspace-interval-vectors row.
    lay = _barbados_ss(symbols=True)  # superspace on, identity_objects off
    cids = {c.id for c in lay.cells}
    bids = {b.id for b in lay.blocks}
    assert not any(c.startswith("cell:ss_vectors:ssprimes:") for c in cids)
    assert not any(c.startswith("cell:ss_mapping:ssgens:") for c in cids)
    assert "block:ss_vectors:ssprimes" not in bids
    assert "block:ss_mapping:ssgens" not in bids
    # the real B_L / M_L in the same rows render regardless of the gate
    assert any(c.startswith("cell:ss_vectors:primes:") for c in cids)
    assert any(c.startswith("cell:ss_mapping:ssprimes:") for c in cids)
    # identity_objects on brings both identity objects back
    on = {c.id for c in _barbados_ss_identity(symbols=True).cells}
    assert {"cell:ss_vectors:ssprimes:0:0", "cell:ss_mapping:ssgens:0:0"} <= on


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
    # "tuningvalue" (matches the existing 𝒈 cells), text formatted at the grid's 3-dp.
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
    assert cells["symbol:tuning:ssgens"].text == "\U0001D488L"
    assert cells["symbol:tuning:ssprimes"].text == "\U0001D495L"
    assert cells["symbol:just:ssprimes"].text == "\U0001D48BL"
    assert cells["symbol:retune:ssprimes"].text == "\U0001D493L"


def test_superspace_tuning_row_equivalences():
    # equivalences on appends the defining equation: 𝒕ₗ = 𝒈ₗ𝑀ₗ; 𝒓ₗ = 𝒕ₗ − 𝒋ₗ.
    # 𝒈ₗ and 𝒋ₗ are primary, no continuation.
    cells = {c.id: c for c in _barbados_ss(symbols=True, equivalences=True).cells}
    # 𝒕ₗ = 𝒈ₗ𝑀ₗ
    assert cells["symbol:tuning:ssprimes"].text == "\U0001D495L = \U0001D488L\U0001D440L"
    # 𝒓ₗ = 𝒕ₗ − 𝒋ₗ
    assert cells["symbol:retune:ssprimes"].text == "\U0001D493L = \U0001D495L − \U0001D48BL"


def test_superspace_tuning_rows_absent_over_a_standard_prime_domain():
    # over a standard prime domain the superspace IS the domain (𝒈ₗ = 𝒈, 𝒕ₗ = 𝒕 …), so the
    # superspace tuning cells add nothing — they stay hidden even with the toggle on.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults() | {"nonstandard_domain": True}
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(cid.startswith(pfx) for cid in cids
                   for pfx in ("tuning:ssgen", "tuning:ssprime", "just:ssprime", "retune:ssprime"))


# ---------------------------------------------------------------------------
# Plain-text values for the new superspace tiles. The EBK strings under each
# new tile (when the plain_text_values toggle is on) read the same numbers
# the grid renders — service.plain_text_values is the single seam.
# ---------------------------------------------------------------------------


def test_B_L_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    # B_L for BARBADOS over 2.3.13/5 → ((1,0,0,0), (0,1,0,0), (0,0,-1,1)). The basis change
    # matrix wraps its domain-element kets in an OUTER ⟨ … ] (the mockup's distinct bracket,
    # setting it apart from the plain [ … ] lifted lists C_L / T_L)
    assert cells["ptext:ss_vectors:primes"].text == "⟨[1 0 0 0⟩ [0 1 0 0⟩ [0 0 -1 1⟩]"


def test_M_L_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    # the mapping-style stack "[⟨…]⟨…]⟨…]}" — same shape the existing M's plain-text uses
    ml = service.superspace_mapping(_barbados_state())
    expected = "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in ml) + "}"
    assert cells["ptext:ss_mapping:ssprimes"].text == expected


def test_M_jL_tile_has_a_plain_text_string():
    cells = {c.id: c for c in _barbados_ss_identity(plain_text_values=True).cells}
    # the dL × dL identity — a covector stack closing with the angle ⟩ (the b/b JI mapping is an
    # operator, like P_L), NOT the mapping's }
    assert cells["ptext:ss_vectors:ssprimes"].text == (
        "[⟨1 0 0 0]⟨0 1 0 0]⟨0 0 1 0]⟨0 0 0 1]⟩")


def test_cyan_superspace_tuning_tiles_have_plain_text_strings():
    cells = {c.id: c for c in _barbados_ss(plain_text_values=True).cells}
    tun = _barbados_superspace_tuning()
    # 𝒈ₗ — genmap shape "{ … ]"
    expected_g = "{" + " ".join(service.cents(v) for v in tun.generator_map) + "]"
    assert cells["ptext:tuning:ssgens"].text == expected_g
    # 𝒕ₗ / 𝒋ₗ / 𝒓ₗ — map shape "⟨ … ]"
    for row_key, values in (("tuning", tun.tuning_map), ("just", tun.just_map),
                            ("retune", tun.retuning_map)):
        expected = "⟨" + " ".join(service.cents(v) for v in values) + "]"
        assert cells[f"ptext:{row_key}:ssprimes"].text == expected


def test_superspace_plain_text_off_when_nonstandard_domain_off():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"plain_text_values": True}  # nonstandard_domain off
    cids = {c.id for c in spreadsheet.build(state, s).cells}
    for new in ("ptext:ss_vectors:primes", "ptext:ss_mapping:ssprimes",
                "ptext:ss_vectors:ssprimes", "ptext:tuning:ssgens",
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
    for frag in ("cell:ss_vectors:primes:", "cell:ss_mapping:ssprimes:",
                 "ssgenmap", ":ssprimes:l", ":ssprimes:r"):
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
    cells = {c.id: c for c in _barbados_ss_identity().cells}
    for i in range(4):  # dL=4 rows
        assert cells[f"bracket:ss_vec_jmap:{i}:l"].text == "⟨"
        assert cells[f"bracket:ss_vec_jmap:{i}:r"].text == "]"


def test_superspace_t_L_j_L_r_L_brackets_reuse_MAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    for key in ("tuning", "just", "retune"):
        assert cells[f"bracket:{key}:ssprimes:l"].text == "⟨"
        assert cells[f"bracket:{key}:ssprimes:r"].text == "]"


def test_superspace_g_L_brackets_reuse_GENMAP_BRACKETS():
    cells = {c.id: c for c in _barbados_ss().cells}
    assert cells["bracket:tuning:ssgenmap:l"].text == "{"
    assert cells["bracket:tuning:ssgenmap:r"].text == "]"


def test_superspace_M_L_and_M_jL_outer_frame_uses_ebktop_with_brace_or_angle():
    # both M_L and M_jL frame with a spanning ebktop. M_L is the rL × dL mapping, so it closes with
    # the curly } (ebkbrace), like the on-domain M. M_jL = I is the p/p JI mapping — an operator,
    # so it closes with the angle ⟩ (ebkangle), like the projection P_L.
    cells = {c.id: c for c in _barbados_ss_identity().cells}
    assert cells["ebktop:ss_mapping"].kind == "ebktop"
    assert cells["ebkbrace:ss_mapping"].kind == "ebkbrace"   # M_L: mapping → curly }
    assert cells["ebktop:ss_vec_jmap"].kind == "ebktop"
    assert cells["ebkangle:ss_vec_jmap"].kind == "ebkangle"  # M_jL: operator → angle ⟩


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


def test_math_expressions_off_keeps_j_L_cells_as_plain_tuning_value():
    # math expressions OFF: the just/ssprimes cells stay as plain "tuningvalue" cents cells, no
    # closed-form prefix. (The math toggle is independent of the other display flags.)
    cells = {c.id: c for c in _barbados_ss(math_expressions=False).cells}
    assert cells["just:ssprime:0"].kind == "tuningvalue"


def test_chart_band_renders_over_the_retune_r_L_tile_when_charts_is_on():
    # retune ∈ CHARTED_ROWS, so its tuning_value_row records (retune, ssprimes) in chart_tiles,
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


def test_per_cell_units_subscript_p_on_the_superspace_tuning_cells():
    # the cyan tuning row's ssprimes cells carry "¢/p" units — the superspace runs over TRUE
    # primes p (it is prime-only by construction), NOT the on-domain basis element b, even when
    # the domain is nonstandard. With units on, each cell's unit subscripts the prime index —
    # ¢/p₁, ¢/p₂, … — and the on-domain p → b swap does NOT reach these tiles.
    cells = {c.id: c for c in _barbados_ss(units=True, cell_units=True).cells}
    assert cells["tuning:ssprime:0"].unit == "¢/p₁"
    assert cells["tuning:ssprime:1"].unit == "¢/p₂"
    assert cells["just:ssprime:0"].unit == "¢/p₁"
    assert cells["retune:ssprime:0"].unit == "¢/p₁"


def test_per_cell_units_subscript_gL_on_the_g_L_cells():
    # 𝒈ₗ over the ssgens column carries "¢/gL" units (one cents-per-superspace-generator entry),
    # subscripted by the generator index — ¢/gL₁, ¢/gL₂, … (gL, distinct from the on-domain g)
    cells = {c.id: c for c in _barbados_ss(units=True, cell_units=True).cells}
    assert cells["tuning:ssgen:0"].unit == "¢/gL₁"
    assert cells["tuning:ssgen:1"].unit == "¢/gL₂"


def test_per_cell_units_on_the_M_L_cells_carry_gL_over_p():
    # M_L (superspace mapping) is superspace-generators-per-superspace-prime (gL/p), one entry
    # per (superspace generator, superspace prime). The subscripts follow row × column —
    # gL₁/p₁, gL₁/p₂, … like the on-domain mapping cells take g₁/p₁ etc.
    cells = {c.id: c for c in _barbados_ss(units=True, cell_units=True).cells}
    assert cells["cell:ss_mapping:ssprimes:0:0"].unit == "gL₁/p₁"
    assert cells["cell:ss_mapping:ssprimes:0:1"].unit == "gL₁/p₂"
    assert cells["cell:ss_mapping:ssprimes:1:0"].unit == "gL₂/p₁"


def test_superspace_units_row_labels_columns_gL_and_p():
    # the domain_units row labels each superspace column's coordinate at the top: /gLᵢ over the
    # superspace generators, /pᵢ over the superspace primes (true primes p, NOT the on-domain b)
    cells = {c.id: c for c in _barbados_ss(domain_units=True).cells}
    assert [cells[f"urow:ssgens:{g}"].text for g in range(3)] == ["/gL₁", "/gL₂", "/gL₃"]
    assert [cells[f"urow:ssprimes:{p}"].text for p in range(4)] == ["/p₁", "/p₂", "/p₃", "/p₄"]


def test_superspace_units_column_labels_rows_p_and_gL():
    # the domain_units column labels each superspace row's coordinate down the spine: B_L's
    # components are superspace primes (pᵢ/), M_L's rows are superspace generators (gLᵢ/)
    cells = {c.id: c for c in _barbados_ss(domain_units=True).cells}
    assert [cells[f"ucol:ss_vectors:{p}"].text for p in range(4)] == ["p₁/", "p₂/", "p₃/", "p₄/"]
    assert [cells[f"ucol:ss_mapping:{i}"].text for i in range(3)] == ["gL₁/", "gL₂/", "gL₃/"]


def test_superspace_keeps_p_while_the_nonstandard_domain_swaps_to_b():
    # the crux of p vs b: over a nonstandard domain the on-domain coordinate swaps p → b
    # (basis element), but the superspace — prime-only by construction — keeps p (true primes).
    # The two coexist in one grid: the domain column reads /b, the superspace column reads /p.
    cells = {c.id: c for c in _barbados_ss(domain_units=True, units=True, cell_units=True).cells}
    # on-domain: basis-element b (the 2.3.13/5 domain has a nonprime element)
    assert cells["urow:primes:0"].text == "/b₁"
    assert cells["ucol:vectors:0"].text == "b₁/"
    assert cells["tuning:prime:0"].unit == "¢/b₁"
    # superspace: true prime p, unaffected by the domain swap
    assert cells["urow:ssprimes:0"].text == "/p₁"
    assert cells["ucol:ss_vectors:0"].text == "p₁/"
    assert cells["tuning:ssprime:0"].unit == "¢/p₁"


def test_superspace_units_off_without_domain_units():
    # the superspace units ride the domain_units toggle like the rest — off, no urow/ucol cells
    cells = {c.id for c in _barbados_ss().cells}  # domain_units off
    assert not any(c.startswith(("urow:ssgens", "urow:ssprimes", "ucol:ss_")) for c in cells)


def test_superspace_L_marker_is_a_capital_subscript():
    # the superspace "L" subscript is a real CAPITAL L wrapped in the <sub> sentinels (rendered
    # <sub>L</sub> by app), not the lowercase ₗ — consistently across counts, symbols and units.
    L = spreadsheet.SUBSCRIPT_L
    assert L == spreadsheet.SUB_OPEN + "L" + spreadsheet.SUB_CLOSE  # capital L, subscript-wrapped
    cells = {c.id: c for c in _barbados_ss(counts=True, symbols=True, domain_units=True).cells}
    assert cells["count:ssgens"].text == f"\U0001D45F{L} = 3"        # 𝑟ʟ = 3 (not 𝑟ₗ)
    assert cells["symbol:tuning:ssgens"].text == f"\U0001D488{L}"    # 𝒈ʟ
    assert cells["urow:ssgens:0"].text == f"/g{L}₁"            # /gʟ₁


def test_superspace_mapping_row_labels_clear_the_bracket_and_cells():
    # M_L's row labels (𝒎ʟᵢ) seat in a reserved gutter LEFT of each row's ⟨ bracket and first
    # cell — the ssprimes column now reserves the same MATLABEL_W gutter the primes column does,
    # so the labels no longer collide with the EBK or the matrix (the issue-2 fix)
    cells = {c.id: c for c in _barbados_ss(symbols=True, header_symbols=True).cells}
    label = cells["matlabel:row:ss_mapping:ssprimes:0"]
    bracket = cells["bracket:ss_map:0:l"]
    cell0 = cells["cell:ss_mapping:ssprimes:0:0"]
    assert label.x + label.w <= bracket.x        # label ends at/before the ⟨ starts
    assert bracket.x + bracket.w <= cell0.x      # ⟨ ends at/before the first cell


def test_superspace_matrix_plain_text_stays_within_its_tile():
    # the M_L / M_jL / B_L plain-text EBK strings reserve band height (PTEXT_ROWS), so they sit
    # inside the tile instead of spilling into the row below (the issue-2 plain-text fix)
    cells = {c.id: c for c in _barbados_ss(symbols=True, plain_text_values=True, identity_objects=True).cells}
    ptext = cells["ptext:ss_mapping:ssprimes"]
    next_label = cells["label:tuning"]
    assert ptext.y + ptext.h <= next_label.y     # the plain text clears the next row's band


def test_nonstandard_domain_uses_b_throughout_the_basis_column_not_just_units():
    # over a nonstandard domain the on-domain p → b swap reaches the TILE-level "units:" line
    # too (not merely the units row/column + per-cell units) — the whole basis-elements column
    # reads b consistently. The superspace tiles keep p (true primes).
    cells = {c.id: c for c in _barbados_ss(names=True, units=True).cells}
    assert cells["units:mapping:primes"].text == "units: g/b"        # 𝑔/𝑝 → 𝑔/𝒃
    assert cells["units:tuning:primes"].text == "units: ¢/b"
    # the superspace mapping's tile-level unit is unchanged (gʟ/p, true primes)
    assert cells["units:ss_mapping:ssprimes"].text == f"units: g{spreadsheet.SUBSCRIPT_L}/p"


def test_superspace_tuning_tiles_get_subcolumn_headers():
    # the superspace tuning-family covectors head each column with 𝒈ʟᵢ / 𝒕ʟᵢ / 𝒋ʟᵢ / 𝒓ʟᵢ
    # (the issue-4 fix — they were missing while the on-domain 𝒕ᵢ etc. had them). M_L / M_jL
    # head their ROWS (𝒎ʟᵢ) instead, like the on-domain mapping, so they carry no col header.
    L = spreadsheet.SUBSCRIPT_L
    cells = {c.id: c for c in _barbados_ss(symbols=True, header_symbols=True).cells}
    assert cells["matlabel:col:tuning:ssgens:0"].text == f"\U0001D488{L}₁"   # 𝒈ʟ₁
    assert cells["matlabel:col:tuning:ssprimes:0"].text == f"\U0001D495{L}₁"  # 𝒕ʟ₁
    assert cells["matlabel:col:just:ssprimes:1"].text == f"\U0001D48B{L}₂"    # 𝒋ʟ₂
    assert cells["matlabel:col:retune:ssprimes:0"].text == f"\U0001D493{L}₁"  # 𝒓ʟ₁


def test_superspace_block_is_a_cyan_region_green_at_temperament_columns():
    # the chapter-9 superspace block reads as a CYAN (tuning) region, turning GREEN ONLY where it
    # crosses a yellow temperament COLUMN — the domain-basis elements (B_L / M_s→L) and the commas
    # (C_L). Its own ssgens/ssprimes columns (the superspace bases, M_L), the tuning maps
    # (𝒈ₗ/𝒕ₗ/𝒋ₗ/𝒓ₗ), the JI mapping M_jₗ and the spine all stay pure cyan. (A deliberate region
    # tint, NOT the per-object factor scheme — see tile_groups.)
    lay = _barbados_ss(tuning_colorization=True, temperament_colorization=True,
                       counts=True, identity_objects=True)
    cells = {c.id: c for c in lay.cells}
    cyan, green = {"tuning"}, {"tuning", "temperament"}
    # pure cyan: the superspace bases/headers, the M_L mapping, the tuning maps, the JI mapping, the spine
    assert _color_at(lay, *_mid(cells, "ssqgen:0")) == cyan                # superspace generators (ssgens col)
    assert _color_at(lay, *_mid(cells, "ssqprime:0")) == cyan             # superspace primes (ssprimes col)
    assert _color_at(lay, *_mid(cells, "cell:ss_mapping:ssprimes:0:0")) == cyan  # M_L (ssprimes col)
    assert _color_at(lay, *_mid(cells, "tuning:ssgen:0")) == cyan          # 𝒈ₗ
    assert _color_at(lay, *_mid(cells, "tuning:ssprime:0")) == cyan        # 𝒕ₗ
    assert _color_at(lay, *_mid(cells, "just:ssprime:0")) == cyan          # 𝒋ₗ
    assert _color_at(lay, *_mid(cells, "cell:ss_vectors:ssprimes:0:0")) == cyan  # M_jₗ
    assert _color_at(lay, *_mid(cells, "count:ssprimes")) == cyan          # the spine
    # green ONLY where a yellow temperament column crosses: the domain-elements & commas columns
    assert _color_at(lay, *_mid(cells, "cell:ss_vectors:primes:0:0")) == green    # B_L (domain elements)
    assert _color_at(lay, *_mid(cells, "cell:ss_vectors:commas:0:0")) == green    # C_L (commas)
    assert _color_at(lay, *_mid(cells, "cell:ss_mapping:primes:0:0")) == green    # M_s→L (domain elements)


def test_size_factor_all_interval_weight_is_a_list_mirroring_the_complexity_row():
    # all-interval + size factor (lils): the simplicity weight has no concrete diagonal closed form, but
    # it still renders as a per-target LIST (with its bar chart) — and it's labelled as the reciprocal of
    # the complexity row, exactly as the complexity row drops diag(𝐿) for a bare 𝒄. So the weight drops
    # the concrete diag(𝐿)⁻¹ for the generic 𝒘 = 𝒄⁻¹, with per-column headers wₙ = cₙ⁻¹ — just the
    # reciprocal of that column's complexity cₙ (the norm detail stays on the 𝒄 tile's own cₙ = ‖𝐿[n]‖q
    # header, not repeated). NOT the matrix 𝑆ₚ / ⊕ 1 — that's the (d+1)×(d+1) form a list can't be.
    lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, charts=True,
                                   symbols=True, header_symbols=True, equivalences=True, names=True).cells}
    assert "weight:target:0" in lils and "chart:weight:targets" in lils   # a single-row list, with its chart
    assert "cell:weight:targets:1:0" not in lils and "bar:weight" not in lils  # NOT a matrix, no size bar
    assert lils["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"
    assert lils["caption:weight:targets"].text == "target interval weight list"
    assert lils["matlabel:col:weight:targets:0"].text == "w₁ = c₁⁻¹"
    assert lils["matlabel:col:weight:targets:2"].text == "w₃ = c₃⁻¹"
    # symbols only (no equivalences) → the bare glyph 𝒘 and the bare per-column wₙ
    bare = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, header_symbols=True).cells}
    assert bare["symbol:weight:targets"].text == "𝒘"
    assert bare["matlabel:col:weight:targets:0"].text == "w₁"
    # a plain all-interval diagonal weight (no size factor) keeps the concrete 𝒘 = diag(𝐿)⁻¹ + bare wₙ
    lp = {c.id: c for c in _with("minimax-S", weighting=True, charts=True, symbols=True, header_symbols=True, equivalences=True).cells}
    assert lp["symbol:weight:targets"].text == "𝒘 = diag(𝐿)⁻¹" and lp["matlabel:col:weight:targets:0"].text == "w₁"
    assert "weight:target:0" in lp and "cell:weight:targets:1:0" not in lp


def test_a_non_diagonal_pretransformer_all_interval_weight_is_a_reciprocal_list():
    # editing the pretransformer square off-diagonal (a non-diagonal 𝑋, no size factor) also costs the
    # per-prime weight list its diagonal closed form — but the weight still renders as a per-target LIST,
    # carrying the generic reciprocal symbol 𝒘 = 𝒄⁻¹ and per-column headers wₙ = cₙ⁻¹ (not a matrix); the
    # norm detail (‖𝑋[n]‖q) lives on the complexity tile, not here.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s.update(weighting=True, charts=True, symbols=True, header_symbols=True, equivalences=True)
    square = ((1.0, 0.0, 0.0), (0.3, 1.0, 0.0), (0.0, 0.0, 1.0))  # an off-diagonal editable square
    on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S",
                                             custom_prescaler=square).cells}
    assert "weight:target:0" in on and "chart:weight:targets" in on       # a list, with its chart
    assert "cell:weight:targets:1:0" not in on and "bar:weight" not in on  # NOT a matrix
    assert on["symbol:weight:targets"].text == "𝒘 = 𝒄⁻¹"                 # the generic reciprocal, no matrix inverse
    assert on["matlabel:col:weight:targets:0"].text == "w₁ = c₁⁻¹"       # references the complexity column, not the norm
    # the complexity tile keeps the per-column norm detail
    assert on["matlabel:col:complexity:targets:0"].text == f"c₁ = ‖𝑋[1]‖{spreadsheet.NORM_SUB_OPEN}q{spreadsheet.NORM_SUB_CLOSE}"


def test_a_matrix_row_carries_a_unit_on_every_subrow_not_just_the_first():
    # GENERIC: a row-tile's units span its actual cell-row count (row_nsub), so a matrix-valued row
    # (the pretransformer 𝑋 = 𝑍𝐿, grown by its size row) gets a unit on EVERY subrow — not just the
    # first. Multi-row tiles index the id by subrow; single-row tiles keep the bare id.
    lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, domain_units=True).cells}
    units = [lils[f"ucol:prescaling:{i}"].text for i in range(4)]  # d=3 prime rows + the size row
    assert len(set(units)) == 1 and units[0].endswith("/")        # one identical unit per subrow
    assert "ucol:prescaling" not in lils                          # multi-row → indexed, no bare id
    # a single-row tile (the weight list) keeps the bare id — generic, not snowflaked
    assert "ucol:weight" in lils and "ucol:weight:0" not in lils


def test_read_only_target_vectors_stay_full_width():
    # the all-interval Tₚ = 𝐈 list is read-only ("vec"), not editable: its cells stay full COL_W (the
    # inset is an editable-input affordance only — see KET_INSET on the editable comma / interest kets).
    cells = {c.id: c for c in _with(scheme="minimax-lils-S").cells}
    real = cells["cell:vec:targets:0:0"]
    assert real.kind == "vec"            # read-only (not the editable targetcell)
    assert real.w == spreadsheet.COL_W   # full width, no inset
# ── chapter-9 domain basis elements become editable with the nonstandard-domain box ──────────

def _nonstd_on(state):
    return settings.defaults() | {"nonstandard_domain": True}


def test_domain_elements_are_editable_elementcells_with_the_box_on():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    on = {c.id: c for c in spreadsheet.build(state, _nonstd_on(state)).cells}
    # an integer prime shows as a plain number (elementcell); a nonprime renders as a stacked
    # fraction face (elementratio — a horizontal bar, denominator below), like every other ratio
    assert on["prime:0"].kind == "elementcell" and on["prime:0"].text == "2"
    assert on["prime:2"].kind == "elementratio" and on["prime:2"].text == "13/5"
    # the box off: the same elements are read-only domain primes
    off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
    assert off["prime:0"].kind == "prime"
    assert off["prime:2"].kind == "prime"


def test_domain_header_flips_to_basis_elements_only_with_a_nonprime():
    # the header reads "domain basis elements" only when the box is on AND the basis carries a
    # nonprime. Over a standard prime limit the box-on header stays "domain primes" (just
    # editable now); a nonprime basis (2.3.13/5) with the box on flips it.
    std = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # standard 2.3.5
    on = {c.id: c for c in spreadsheet.build(std, _nonstd_on(std)).cells}
    assert on["header:primes"].text == "domain\nprimes"
    off = {c.id: c for c in spreadsheet.build(std, settings.defaults()).cells}
    assert off["header:primes"].text == "domain\nprimes"
    nonprime = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    on_np = {c.id: c for c in spreadsheet.build(nonprime, _nonstd_on(nonprime)).cells}
    assert on_np["header:primes"].text == "domain basis\nelements"


def test_basis_spine_is_editable_with_the_box_on():
    # the interval-vectors spine becomes interactive too — the vertical twin of the editable
    # quantities-row element cells: typing a rational relabels that basis element (holding its
    # mapping coordinates) through the SAME on_element_change. An integer prime is a plain
    # elementcell, a nonprime a stacked-fraction elementratio; off, both are read-only "prime".
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    on = {c.id: c for c in spreadsheet.build(state, _nonstd_on(state)).cells}
    assert on["basis:0"].kind == "elementcell" and on["basis:0"].text == "2"
    assert on["basis:2"].kind == "elementratio" and on["basis:2"].text == "13/5"
    off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
    assert off["basis:0"].kind == "prime" and off["basis:2"].kind == "prime"


def test_domain_plus_is_element_draft_with_the_box_on():
    # the + opens a typed draft, not a prime walk — on BOTH axes: the quantities-row primes +
    # (id "element_plus" / "plus") and the interval-vectors spine + (id "basis_plus", whose KIND
    # flips element_plus ↔ plus), so each adds held-just rather than resetting to a prime limit.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # standard 2.3.5
    on = {c.id: c for c in spreadsheet.build(state, settings.defaults() | {"nonstandard_domain": True}).cells}
    assert "element_plus" in on and "plus" not in on  # the column + opens a typed draft, not a prime walk
    assert on["basis_plus"].kind == "element_plus"     # ...and so does the spine + (its kind, the id stays basis_plus)
    off = {c.id: c for c in spreadsheet.build(state, settings.defaults()).cells}
    assert "plus" in off and "element_plus" not in off  # box off: the column + walks to the next prime
    assert off["basis_plus"].kind == "plus"             # ...and so does the spine +


def test_box_off_walk_minus_gives_way_to_a_per_element_minus_with_the_box_on():
    # box OFF: a single walk − (basis_minus / minus → shrink) over the highest prime only, on both
    # axes. box ON: that one walk − gives way to a per-element − over EVERY element (each removing
    # just that element via remove_domain_element), on both axes — the fix for the domain − that
    # previously vanished entirely with the box on.
    augmented = service.from_comma_basis(((7, 0, -3),))  # 2.3.5 (d=3), a shrinkable standard limit
    off = {c.id for c in spreadsheet.build(augmented).cells}
    assert "basis_minus" in off and "minus" in off  # box off: the single walk − on both axes
    assert not any(i.startswith("element_minus") for i in off)  # ...and no per-element −
    on = {c.id: c for c in spreadsheet.build(augmented, _nonstd_on(augmented)).cells}
    assert "basis_minus" not in on and "minus" not in on  # box on: no walk − on either axis
    qty = {f"element_minus:{p}" for p in range(augmented.d)}        # a − over each quantities header
    spine = {f"element_minus:basis:{p}" for p in range(augmented.d)}  # ...and each spine row
    assert qty <= set(on) and spine <= set(on)
    assert all(on[f"element_minus:{p}"].prime == p for p in range(augmented.d))  # each carries its index


def test_per_element_domain_minus_is_withheld_at_the_last_element():
    # a domain keeps at least one element, so with d == 1 there is nothing to remove — no − on
    # either axis even with the box on (never shown inert, like the walk − at d == 1).
    sole = service.from_mapping(((1,),))  # d == 1
    on = {c.id for c in spreadsheet.build(sole, _nonstd_on(sole)).cells}
    assert not any(i.startswith("element_minus") for i in on)
    assert "minus" not in on and "basis_minus" not in on


def test_pending_element_renders_drafts_on_both_axes():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"nonstandard_domain": True}
    cells = {c.id: c for c in spreadsheet.build(state, s, pending_element="").cells}
    # the quantities-row ratio draft AND the interval-vectors spine draft, two views of one
    # pending element — each a "?/?" placeholder committing through the SAME on_element_change
    for draft_id, minus_id in (("prime:pending", "element_minus:pending"),
                               ("basis:pending", "element_minus:basis:pending")):
        draft = cells[draft_id]
        assert draft.kind == "elementratio" and draft.pending and draft.text == "?/?"
        assert minus_id in cells  # its − cancels the draft (the ":pending" id steers it to remove_element)
    # the spine draft sits one ROW_H below the basis stack, past which the spine + has dropped
    assert cells["basis:pending"].y == cells["basis:2"].y + spreadsheet.ROW_H
    assert cells["basis_plus"].y > cells["basis:pending"].y  # the + rides the stub below the draft
    # a partially-typed draft shows the raw text on both axes
    typed = {c.id: c for c in spreadsheet.build(state, s, pending_element="9").cells}
    assert typed["prime:pending"].text == "9" and typed["basis:pending"].text == "9"


# --- the projection box (a tuning-boxes sub-control; the rational P = GM) ---


def test_projection_off_by_default_shows_no_projection_box():
    cells = {c.id for c in _layout().cells}  # default build: projection off
    assert "label:projection" not in cells
    assert not any(c.startswith("cell:proj:") for c in cells)


def test_projection_is_an_interactive_toggle():
    # it builds content now, so the panel offers it live rather than greyed out
    assert "projection" in settings.IMPLEMENTED


def test_projection_on_adds_a_dxd_matrix_between_mapping_and_tuning():
    cells = {c.id: c for c in _with(projection=True).cells}
    assert cells["label:projection"].text == "projection"
    # a d×d matrix of read-only cells (d=3 here), on the shared domain-prime axes
    for i in range(3):
        for p in range(3):
            cell = cells[f"cell:proj:{i}:{p}"]
            assert cell.kind == "mapped"  # read-only computed value, like the mapped lists
            assert cell.x == cells[f"cell:mapping:0:{p}"].x  # the same prime columns
    # its own band, between the mapping and the tuning rows (per the mockup)
    assert cells["label:mapping"].y < cells["label:projection"].y < cells["label:tuning"].y
    # square grid cells stacked one ROW_H apart, like the other matrices
    c00 = cells["cell:proj:0:0"]
    assert c00.w == c00.h == spreadsheet.ROW_H
    assert cells["cell:proj:1:0"].y == c00.y + spreadsheet.ROW_H


def test_projection_box_is_dashed_until_the_tuning_is_a_rational_projection():
    # the corrected model: the default tuning holds nothing rational, so P is TOTALLY DASHED
    # (every cell an em-dash) — NOT a fabricated quarter-comma it doesn't actually realise.
    dashed = {c.id: c for c in _proj_build().cells}
    assert all(dashed[f"cell:proj:{i}:{p}"].text == "—" for i in range(3) for p in range(3))


def test_projection_box_shows_the_real_quarter_comma_when_fully_held():
    # holding a full rational basis {2/1, 5/4} pins quarter-comma meantone: the fifth flat by 1/4
    # comma (the 1/4 on prime 3's image). Reproduces the mockup exactly.
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}
    expected = (("1", "1", "0"), ("0", "0", "0"), ("0", "1/4", "1"))
    for i in range(3):
        for p in range(3):
            assert cells[f"cell:proj:{i}:{p}"].text == expected[i][p]


def test_projection_box_is_framed_like_a_matrix_of_maps():
    cells = {c.id: c for c in _with(projection=True).cells}
    # each of the d rows is a map: ⟨ … ] brackets, like the mapping rows
    assert cells["bracket:proj:0:l"].text == "⟨" and cells["bracket:proj:0:r"].text == "]"
    assert {"bracket:proj:1:l", "bracket:proj:2:l"} <= set(cells)  # d=3 rows
    # and the whole matrix is enclosed by a spanning top bracket + bottom ANGLE close ⟩ (P is p/p, so
    # its outer closes with the prime-coordinate ket ⟩, matching its plain text [⟨…]…⟩ — not the
    # mapping's generator-coordinate })
    assert "ebktop:proj" in cells and "ebkangle:proj" in cells and "ebkbrace:proj" not in cells
    top, brace = cells["ebktop:proj"], cells["ebkangle:proj"]
    first, last = cells["cell:proj:0:0"], cells["cell:proj:2:0"]
    assert top.y + top.h <= first.y       # the top bracket sits above the matrix
    assert brace.y >= last.y + last.h     # the angle close sits below it


def test_projection_row_fans_a_gridline_per_subrow():
    lines = {ln.id for ln in _with(projection=True).lines}
    # a d-tall matrix row fans into one rule per cell-row (like the mapping / vectors)
    assert {"h:projection:0", "h:projection:1", "h:projection:2"} <= lines


def test_projection_hides_with_its_parent_tuning_tiles():
    # projection is a sub-control of tuning tiles, so turning the parent off takes the
    # projection box with it (even when projection itself is on)
    cells = {c.id for c in _with(projection=True, tuning_tiles=False).cells}
    assert "label:projection" not in cells
    assert not any(c.startswith("cell:proj:") for c in cells)


def test_projection_on_adds_the_generator_embedding_G_beside_P():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}  # quarter-comma: a full rational hold
    # G shares the projection band (the d prime rows) but lives in the r generator columns:
    # a d×r matrix of read-only "mapped" cells (d=3, r=2 here) — edited only via the plain-text band,
    # since 𝑀𝐺 = 𝐼 couples every entry
    for i in range(3):
        for g in range(2):
            cell = cells[f"cell:embed:{i}:{g}"]
            assert cell.kind == "mapped"                  # read-only (a single entry can't be a valid edit)
            assert cell.x == cells[f"tuning:gen:{g}"].x   # the same generator columns as 𝒈
            assert cell.y == cells[f"cell:proj:{i}:0"].y  # the same prime rows as P
    # quarter-comma's embedding G: the octave and 5^(1/4)
    expected = (("1", "0"), ("0", "0"), ("0", "1/4"))
    for i in range(3):
        for g in range(2):
            assert cells[f"cell:embed:{i}:{g}"].text == expected[i][g]
    # under-held (the default), G dashes out in lockstep with P
    dashed = {c.id: c for c in _proj_build().cells}
    assert all(dashed[f"cell:embed:{i}:{g}"].text == "—" for i in range(3) for g in range(2))


def test_projection_p_and_g_carry_full_chrome_and_editable_plain_text():
    # P and G are at chrome parity with the mapping: symbols 𝑃/𝐺 (+ equivalence), the p/p and p/g
    # units, P's covector rows labelled 𝒑ᵢ and G's columns 𝐠ᵢ, and an EDITABLE plain-text band each —
    # the only edit path now the gridded cells are read-only "mapped".
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), symbols=True, header_symbols=True, units=True,
                                          equivalences=True, plain_text_values=True).cells}
    assert cells["symbol:projection:primes"].text.startswith("𝑃") and "= G𝑀" in cells["symbol:projection:primes"].text
    assert cells["symbol:projection:gens"].text.startswith("G")   # upright G (a basis), not italic 𝐺
    assert cells["units:projection:primes"].text == "units: p/p"
    assert cells["units:projection:gens"].text == "units: p/g"
    assert cells["matlabel:row:projection:primes:0"].text == "𝒑₁"   # P's covector rows
    assert cells["matlabel:col:projection:gens:0"].text == "𝐠₁"     # G's vector columns
    # the gridded cells are read-only; editing is via the plain-text bands (kind "ptextedit")
    assert cells["cell:proj:0:0"].kind == "mapped" and cells["cell:embed:0:0"].kind == "mapped"
    assert cells["ptext:projection:primes"].kind == "ptextedit"
    assert cells["ptext:projection:gens"].kind == "ptextedit"
    assert cells["ptext:projection:primes"].text == "[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩"
    assert cells["ptext:projection:gens"].text == "{[1 0 0⟩ [0 0 1/4⟩]"


def test_projection_plain_text_bands_dash_when_under_held():
    # under-held (the default), P/G aren't a full rational projection, so the bands dash in lockstep
    # with the grid cells
    cells = {c.id: c for c in _proj_build(plain_text_values=True).cells}
    assert cells["ptext:projection:primes"].text == "[⟨— — —]⟨— — —]⟨— — —]⟩"
    assert cells["ptext:projection:gens"].text == "{[— — —⟩ [— — —⟩]"


def _proj_full(**overrides):
    # a quarter-comma (fully held) projection build with extra build kwargs (held_vectors, interest)
    s = settings.defaults()
    s["projection"] = True
    kwargs = {k: overrides.pop(k) for k in ("held_vectors", "interest") if k in overrides}
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_basis_ratios=("2/1", "5/4"), **kwargs)


def test_projection_quantities_spine_lists_the_domain_primes():
    # the projection row's quantities column labels its prime-indexed rows with the domain basis
    # (2, 3, 5), like the interval-vectors basis spine — read-only (the whole projection row is derived)
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}
    assert [cells[f"proj_basis:{p}"].text for p in range(3)] == ["2", "3", "5"]
    assert cells["proj_basis:0"].kind == "prime"                  # read-only
    assert cells["proj_basis:0"].y == cells["cell:proj:0:0"].y    # aligned with P's top prime row
    assert cells["proj_basis:0"].x == cells["basis:0"].x          # same quantities spine as the vectors row


def test_projection_units_spine_labels_each_row_as_a_prime_coordinate():
    # P is a p/p operator, so the units column reads pᵢ/ down the projection row, like the vectors row
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), domain_units=True).cells}
    assert [cells[f"ucol:projection:{p}"].text for p in range(3)] == ["p₁/", "p₂/", "p₃/"]
    assert cells["ucol:projection:0"].y == cells["cell:proj:0:0"].y


def test_projection_detempering_tile_shows_P_times_D():
    # the projected generator detempering P·D over the detempering column: d-tall ket columns, one per
    # generator. P·D = the embedding G (P·D = GMD = G, since M·D = I): quarter-comma's columns are the
    # octave [1 0 0] and 5^(1/4) = [0 0 1/4]. Read-only "mapped" cells, like P/G.
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), generator_detempering=True).cells}
    expected = (("1", "0", "0"), ("0", "0", "1/4"))
    for i in range(2):  # r = 2 generators
        for p in range(3):
            cell = cells[f"cell:proj_pd:{i}:{p}"]
            assert cell.text == expected[i][p]
            assert cell.kind == "mapped"
            assert cell.x == cells[f"cell:vec:detempering:{i}:{p}"].x  # the detempering column
            assert cell.y == cells[f"cell:proj:{p}:0"].y               # the projection row's prime rows


def test_projection_targets_tile_shows_P_times_T():
    # P·T over the targets column: each default target (the 5-limit diamond) projected to its tempered
    # vector — the 8 columns of the mockup's PT tile (e.g. 3/2 → 5^(1/4) = [0 0 1/4], 6/5 → [2 0 -3/4])
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}
    expected = (("1", "0", "0"), ("1", "0", "1/4"), ("0", "0", "1/4"), ("1", "0", "-1/4"),
                ("-1", "0", "1"), ("-1", "0", "3/4"), ("-2", "0", "1"), ("2", "0", "-3/4"))
    for j, col in enumerate(expected):
        for p in range(3):
            cell = cells[f"cell:proj_pt:{j}:{p}"]
            vec = cells[f"cell:vec:targets:{j}:{p}"]
            assert cell.text == col[p]
            assert cell.kind == "mapped"
            assert cell.x + cell.w / 2 == vec.x + vec.w / 2  # column-centred on the targets column
            assert cell.y == cells[f"cell:proj:{p}:0"].y     # the projection row's prime rows


def test_projection_held_tile_shows_P_times_H_equals_H():
    # P·H = H: the held intervals are P's eigenvalue-1 directions, unchanged by the projection
    cells = {c.id: c for c in _proj_full(optimization=True,
                                         held_vectors=[(1, 0, 0), (-2, 0, 1)]).cells}
    expected = (("1", "0", "0"), ("-2", "0", "1"))
    for i in range(2):
        for p in range(3):
            assert cells[f"cell:proj_ph:{i}:{p}"].text == expected[i][p]
            assert cells[f"cell:proj_ph:{i}:{p}"].kind == "mapped"


def test_projection_interest_tile_shows_P_times_interest():
    # P·interest over the loose interest kets: 3/2 → [0 0 1/4], 6/5 → [2 0 -3/4]
    cells = {c.id: c for c in _proj_full(interest=[(-1, 1, 0), (1, 1, -1)]).cells}
    expected = (("0", "0", "1/4"), ("2", "0", "-3/4"))
    for i in range(2):
        for p in range(3):
            assert cells[f"cell:proj_pi:{i}:{p}"].text == expected[i][p]
            assert cells[f"cell:proj_pi:{i}:{p}"].kind == "mapped"


def test_projection_column_tiles_dash_when_under_held():
    # under-held (no rational projection), every projected tile dashes in lockstep with P
    cells = {c.id: c for c in _proj_build(generator_detempering=True).cells}
    assert all(cells[f"cell:proj_pd:{i}:{p}"].text == "—" for i in range(2) for p in range(3))
    assert all(cells[f"cell:proj_pt:{j}:{p}"].text == "—" for j in range(3) for p in range(3))


def test_projection_column_tiles_carry_full_chrome():
    # captions, symbols, units and per-column labels at parity with the vectors-row tiles they project
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), generator_detempering=True,
                                          symbols=True, header_symbols=True, units=True, equivalences=True).cells}
    assert cells["caption:projection:detempering"].text == "projected generator detempering"
    assert cells["caption:projection:targets"].text == "projected target interval list"
    assert cells["symbol:projection:detempering"].text == "𝑃D"
    assert cells["symbol:projection:targets"].text == "𝑃T"
    assert cells["units:projection:detempering"].text == "units: p"
    assert cells["units:projection:targets"].text == "units: p"
    assert cells["matlabel:col:projection:detempering:0"].text == "𝑃𝐝₁"
    assert cells["matlabel:col:projection:targets:0"].text == "𝑃𝐭₁"


def test_projection_held_tile_carries_the_equals_H_equivalence():
    # PH = H: the held tile's symbol gains the "= H" equivalence (the held intervals are unchanged)
    cells = {c.id: c for c in _proj_full(optimization=True, held_vectors=[(1, 0, 0), (-2, 0, 1)],
                                         symbols=True, header_symbols=True, equivalences=True).cells}
    assert cells["caption:projection:held"].text == "projected held interval basis"
    assert cells["symbol:projection:held"].text == "𝑃H = H"
    assert cells["matlabel:col:projection:held:0"].text == "𝑃𝐡₁"


def test_projection_interest_tile_caption_and_label():
    # interest carries a caption + per-column label but NO big symbol (a loose collection, like the vectors row)
    cells = {c.id: c for c in _proj_full(interest=[(-1, 1, 0), (1, 1, -1)], symbols=True, header_symbols=True).cells}
    assert cells["caption:projection:interest"].text == "projected intervals"
    assert cells["matlabel:col:projection:interest:0"].text == "𝑃𝐢₁"
    assert "symbol:projection:interest" not in cells


def test_projection_column_tiles_carry_plain_text_bands():
    # the EBK strings under each projected tile: P·D the embedding form { … ], P·T a ket list [ … ]
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), generator_detempering=True,
                                          plain_text_values=True).cells}
    assert cells["ptext:projection:detempering"].text == "{[1 0 0⟩ [0 0 1/4⟩]"
    assert cells["ptext:projection:targets"].text == (
        "[[1 0 0⟩ [1 0 1/4⟩ [0 0 1/4⟩ [1 0 -1/4⟩ [-1 0 1⟩ [-1 0 3/4⟩ [-2 0 1⟩ [2 0 -3/4⟩]")


def test_projection_column_tiles_use_their_vectors_row_brackets():
    # P·D takes the embedding's { … ] (genmap), P·T a list [ … ]; their per-column ket marks ride the
    # projection row's frame band, like the matrix tiles' marks
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), generator_detempering=True).cells}
    assert cells["bracket:proj_pd:l"].text == "{" and cells["bracket:proj_pd:r"].text == "]"
    assert cells["bracket:proj_pt:l"].text == "[" and cells["bracket:proj_pt:r"].text == "]"
    assert "ebkangle:proj_pd:0" in cells and "ebkangle:proj_pt:0" in cells  # per-column ket feet


def _proj_superspace(**overrides):
    # BARBADOS over the nonstandard domain 2.3.13/5 with projection + the superspace columns on,
    # holding {2/1, 3/1} (a full rational projection)
    st = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s.update(projection=True, nonstandard_domain=True)
    s.update(overrides)
    return spreadsheet.build(st, s, held_basis_ratios=("2/1", "3/1"))


def test_projection_superspace_tiles_fill_the_gap_between_G_and_P():
    # the missing tiles: G_L→s (d×rL vector list, ssgens) and P_L→s (d×dL covector stack, ssprimes),
    # between G (gens) and P (primes) in the projection row — so the row reads G, G_L→s, P_L→s, P
    cells = {c.id: c for c in _proj_superspace().cells}
    assert [cells[f"cell:embed_sl:0:{g}"].text for g in range(3)] == ["1", "0", "0"]      # G_L→s row 0
    assert [cells[f"cell:embed_sl:1:{g}"].text for g in range(3)] == ["0", "1/2", "0"]    # G_L→s row 1
    assert [cells[f"cell:proj_sl:0:{p}"].text for p in range(4)] == ["1", "0", "0", "-1"]  # P_L→s row 0
    assert [cells[f"cell:proj_sl:1:{p}"].text for p in range(4)] == ["0", "1", "0", "3/2"]  # P_L→s row 1
    assert cells["cell:embed_sl:0:0"].kind == "mapped" and cells["cell:proj_sl:0:0"].kind == "mapped"
    assert cells["cell:embed_sl:0:0"].y == cells["cell:proj:0:0"].y  # the projection row's prime rows
    # left→right order: G < G_L→s < P_L→s < P
    assert (cells["cell:embed:0:0"].x < cells["cell:embed_sl:0:0"].x
            < cells["cell:proj_sl:0:0"].x < cells["cell:proj:0:0"].x)


def test_projection_superspace_tiles_carry_chrome():
    from rtt.app.grid_tables import SUBSCRIPT_L
    cells = {c.id: c for c in _proj_superspace(symbols=True, header_symbols=True, equivalences=True, units=True).cells}
    assert cells["caption:projection:ssgens"].text == "embedding from superspace generators to subspace elements"
    assert cells["caption:projection:ssprimes"].text == "projection from superspace to subspace"
    assert cells["symbol:projection:ssgens"].text == f"G{SUBSCRIPT_L}→ₛ"
    assert cells["symbol:projection:ssprimes"].text == f"𝑃{SUBSCRIPT_L}→ₛ = G{SUBSCRIPT_L}→ₛ𝑀{SUBSCRIPT_L}"
    assert cells["units:projection:ssgens"].text == f"units: b/g{SUBSCRIPT_L}"
    assert cells["units:projection:ssprimes"].text == "units: b/p"
    assert cells["matlabel:col:projection:ssgens:0"].text == f"𝐠{SUBSCRIPT_L}→ₛ₁"     # G_L→s columns
    assert cells["matlabel:row:projection:ssprimes:0"].text == f"𝒑{SUBSCRIPT_L}→ₛ₁"   # P_L→s covector rows
    # G_L→s the genmap { … ] (a vector list, like G); P_L→s a covector stack ⟨ … ] per row (like P)
    assert cells["bracket:embed_sl:l"].text == "{" and cells["bracket:embed_sl:r"].text == "]"
    assert cells["bracket:proj_sl:0:l"].text == "⟨" and cells["bracket:proj_sl:0:r"].text == "]"


def test_projection_superspace_tiles_dash_when_under_held():
    # under-held (no rational projection), G_L→s / P_L→s dash in lockstep with P/G
    st = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s.update(projection=True, nonstandard_domain=True)
    cells = {c.id: c for c in spreadsheet.build(st, s).cells}  # no held_basis_ratios → under-held
    assert all(cells[f"cell:embed_sl:{i}:{g}"].text == "—" for i in range(3) for g in range(3))
    assert all(cells[f"cell:proj_sl:{i}:{p}"].text == "—" for i in range(3) for p in range(4))


def test_projection_row_comes_after_the_superspace_rows():
    # per the mockup the projection row (P, G_L→s, P_L→s) sits BELOW the superspace interval-vectors
    # (B_L) and superspace mapping (M_L) rows, not above them
    cells = {c.id: c for c in _proj_superspace().cells}
    proj_y = cells["cell:proj:0:0"].y
    assert proj_y > cells["cell:ss_vectors:primes:0:0"].y    # below B_L
    assert proj_y > cells["cell:ss_mapping:ssprimes:0:0"].y  # below M_L


def test_projection_targets_tile_tracks_the_targets_column():
    # the projection P·T tile is gated like the other targets tiles, so it is never absent while the
    # interval-vectors targets tile renders an empty [] (the reported inconsistent state): both the
    # populated list and an empty-but-open one keep the two tiles in lockstep
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s.update(projection=True)
    for kw in ({}, {"target_override": ()}):  # a populated target list, then an empty-but-open one
        ids = {c.id for c in spreadsheet.build(st, s, held_basis_ratios=("2/1", "5/4"), **kw).cells}
        assert ("bracket:vec:targets:l" in ids) == ("bracket:proj_pt:l" in ids)


def test_projection_symbol_floor_widens_the_tile_so_the_equivalence_never_wraps():
    # P's equivalence (𝑃 = G𝑀 = V·diag(𝝀)V⁻¹) is wider than the bare 3-column matrix, so the column
    # widens (the _symbol_floor) to fit it on ONE line — the symbol/equivalence must never wrap. The
    # matrix then centres in the widened column.
    from rtt.app.spreadsheet import _min_width_for_lines, SYMBOL_FONT
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), symbols=True, equivalences=True, names=True).cells}
    sym = cells["symbol:projection:primes"]
    assert sym.w >= _min_width_for_lines(sym.text, 1, SYMBOL_FONT)   # the cell is wide enough — no wrap
    left = cells["cell:proj:0:0"].x - sym.x                          # margin from the column edge to the matrix
    right = (sym.x + sym.w) - (cells["cell:proj:0:2"].x + cells["cell:proj:0:2"].w)
    assert abs(left - right) <= 1                                    # the matrix is centred in the widened column


def test_return_to_scheme_button_is_boxed_above_the_dropdown_with_presets():
    # the ✕ "return to scheme" row rides INSIDE the established-projection chooser's box, ABOVE the
    # dropdown (not in a separate control box). Assert the ✕ cell sits above the preset dropdown and
    # both are enclosed by the same chooser box block.
    lay = _with(projection=True, presets=True)
    cells = {c.id: c for c in lay.cells}
    sq, dropdown = cells["scheme:primes"], cells["preset:projection"]
    assert sq.y < dropdown.y  # ✕ row above the dropdown
    box = next(b for b in lay.blocks if b.id == "block:preset:projection")
    for cell in (sq, dropdown):
        assert box.x <= cell.x and cell.y >= box.y and cell.y < box.y + box.h  # both inside the box


def test_return_to_scheme_button_keeps_its_own_box_without_presets():
    # with presets OFF there is no chooser dropdown, but the ✕ + label must still be boxed (a real
    # bug once dropped the box because it was built after the control-region flush). Assert the
    # block:scheme:primes box exists and encloses the ✕ square.
    lay = _with(projection=True, presets=False)
    cells = {c.id: c for c in lay.cells}
    sq = cells["scheme:primes"]
    box = next((b for b in lay.blocks if b.id == "block:scheme:primes"), None)
    assert box is not None and getattr(box, "boxed", False)
    assert box.x <= sq.x and box.y <= sq.y and sq.x + sq.w <= box.x + box.w and sq.y + sq.h <= box.y + box.h


def test_generator_embedding_is_a_vector_list_of_generator_kets():
    cells = {c.id: c for c in _with(projection=True).cells}
    assert cells["caption:projection:gens"].text == "generator embedding"
    # G is a VECTOR LIST (matching its plain text {[…⟩…]): an outer { … ] (curly open, square close)
    # around r prime-count ket [ … ⟩ columns — NOT a per-row covector stack
    assert cells["bracket:embed:l"].text == "{" and cells["bracket:embed:r"].text == "]"  # outer { … ]
    assert {"ebktop:embed:0", "ebkangle:embed:0", "ebktop:embed:1", "ebkangle:embed:1"} <= set(cells)  # r=2 ket columns
    assert "bracket:embed:0:l" not in cells and "ebkbrace:embed" not in cells  # no old per-row covector frame


def test_generator_embedding_hides_when_projection_is_off():
    assert not any(c.id.startswith("cell:embed:") for c in _layout().cells)


def test_presets_on_adds_the_established_projection_and_embedding_choosers():
    cells = {c.id: c for c in _with(projection=True, presets=True).cells}
    assert cells["preset:projection"].kind == "preset"        # established projection, under P
    assert cells["preset:projection:gens"].kind == "preset"   # established embedding, under G
    # their field labels (one selection, two views, since P = GM)
    assert cells["block:preset:projection:label"].text == "established projection"
    assert cells["block:preset:projection:gens:label"].text == "established embedding"


def test_established_projection_choosers_need_both_presets_and_the_projection_box():
    assert not any(c.id.startswith("preset:projection") for c in _with(presets=True).cells)     # projection off
    assert not any(c.id.startswith("preset:projection") for c in _with(projection=True).cells)  # presets off


# --- the projection view's V = C|U consolidation + the scaling-factors row ---
# When projection is on, the commas column and the unchanged interval basis U =
# nullspace(P − I) consolidate into one "unrotated vector basis" column V = C|U, and a
# "scaling factors" row (the eigenvalue list λ = diag(λ), 0 per comma, 1 per unchanged)
# rides over it. (The mockup only draws V in the first row by its author's own admission —
# a blue note licenses generalizing the merger to every tile.)


def test_projection_adds_a_scaling_factors_row_over_v():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}  # a full rational hold completes U
    assert cells["label:scaling_factors"].text == "scaling factors"
    # λ = diag(λ): 0 per comma (vanished), 1 per unchanged interval (held). Meantone fully held
    # has n=1 comma + u=2 unchanged → [0, 1, 1] over the three V sub-columns. The comma half is
    # identity-keyed (token == index until a removal); the U half rides its own u{j} namespace.
    assert [cells[i].text for i in ("cell:scaling:0", "cell:scaling:u0", "cell:scaling:u1")] == ["0", "1", "1"]
    # it rides between the header rows and the interval-vectors row (per the mockup)
    assert cells["label:scaling_factors"].y < cells["label:vectors"].y
    # a one-ROW_H scalar list, on the same V sub-axes as the vectors below it
    s0 = cells["cell:scaling:0"]
    assert s0.h == spreadsheet.ROW_H
    assert s0.x == cells["cell:comma:0:0"].x


def test_projection_consolidates_commas_and_unchanged_into_v():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}  # a full rational hold completes U
    # V = C|U: the editable comma vectors C stay, the unchanged basis U appends — also editable now
    # (a full rational projection), retyping it retunes
    assert cells["cell:comma:0:0"].kind == "commacell"   # C stays editable
    u_first = cells["cell:unchanged:0:0"]
    assert u_first.kind == "unchangedcell"               # U is editable when it's a full projection
    # the unchanged half U is pushed right of the comma half by the extra C|U gap (so the divider
    # clears the cells); within U the columns stay one COL_W apart
    assert u_first.x == cells["cell:comma:0:0"].x + spreadsheet.COL_W + spreadsheet.V_SPLIT_GAP
    assert cells["cell:unchanged:0:1"].x == u_first.x + spreadsheet.COL_W
    # U is the held basis as entered — u₁ = 2/1 = (1,0,0), u₂ = 5/4 = (-2,0,1)
    assert [cells[f"cell:unchanged:{p}:0"].text for p in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["-2", "0", "1"]


def test_projection_dashes_the_unchanged_columns_when_under_held():
    # default (under-held): both unchanged columns are dashed — every U cell an em-dash
    cells = {c.id: c for c in _proj_build().cells}
    assert all(cells[f"cell:unchanged:{p}:{j}"].text == "—" for p in range(3) for j in range(2))


def test_projection_on_a_nonstandard_domain_lifts_dashes_cleanly():
    # regression: projection + a genuinely nonstandard domain (2.3.13/5) lifts the V = C|U column
    # into the chapter-9 superspace; a DASHED (under-held) unchanged column has no vector to lift,
    # so it must stay dashed rather than crash the superspace lift.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["projection"] = True
    s["nonstandard_domain"] = True
    cells = {c.id: c for c in spreadsheet.build(state, s).cells}  # must not raise
    unchanged = [c for c in cells if c.startswith("cell:unchanged:")]
    assert unchanged and all(cells[c].text == "—" for c in unchanged)


def test_projection_mapping_row_spans_v_mapping_the_unchanged_intervals():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}  # quarter-comma: full hold
    # M·C = 0 (the comma vanishes) stays; M·U appends — the unchanged intervals' generator coords.
    assert cells["cell:mapped_comma:0:0"].text == "0"
    assert cells["cell:mapped_unchanged:0:0"].text == "1"   # M·(2/1) = ⟨1 0] (the period)
    assert cells["cell:mapped_unchanged:1:1"].text == "4"   # M·(5/4): gen-row 1 = four fifths
    assert cells["cell:mapped_unchanged:0:0"].x == cells["cell:unchanged:0:0"].x


def test_projection_row_spans_v_with_the_projected_unrotated_vector_list():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}  # quarter-comma: a full rational hold
    # P·V over the V column: P·comma = 0 (the eigenvalue-0 direction vanishes), P·unchanged = the
    # unchanged interval itself (eigenvalue 1). V col 0 = comma (identity-keyed), the unchanged
    # u₁=2/1, u₂=5/4 ride their own u{j} namespace.
    assert [cells[f"cell:proj_v:{p}:0"].text for p in range(3)] == ["0", "0", "0"]    # P·c₁ = 𝟎
    assert [cells[f"cell:proj_v:{p}:u0"].text for p in range(3)] == ["1", "0", "0"]   # P·u₁ = 2/1
    assert [cells[f"cell:proj_v:{p}:u1"].text for p in range(3)] == ["-2", "0", "1"]  # P·u₂ = 5/4
    # it rides the projection row band (same y as P over the primes) on the V sub-axes
    assert cells["cell:proj_v:0:0"].y == cells["cell:proj:0:0"].y
    assert cells["cell:proj_v:0:u0"].x == cells["cell:unchanged:0:0"].x  # V col 1 = first unchanged col
    assert cells["caption:projection:commas"].text == "projected unrotated vector list"


def test_projection_size_rows_span_v():
    cells = {c.id: c for c in _with(projection=True).cells}
    # tuning / just / retuning size lists run over all d = n+u columns of V — the comma half
    # identity-keyed, the unchanged half on its own u{j} namespace
    for key in ("tuning", "just", "retune"):
        assert {f"{key}:comma:0", f"{key}:comma:u0", f"{key}:comma:u1"} <= set(cells)
        # the unchanged size cells sit on the U sub-axes (right of the comma sizes)
        assert cells[f"{key}:comma:u1"].x == cells["cell:unchanged:0:1"].x


def test_projection_v_column_has_one_c_u_divider_per_tile_and_no_stray_separators():
    cells = {c.id: c for c in _with(projection=True).cells}
    # one vertical bar centred in the C|U gap (left of the first unchanged column) down each V tile
    bar = cells["vsplit:vectors"]
    assert bar.x == cells["cell:unchanged:0:0"].x - spreadsheet.V_SPLIT_GAP / 2 - spreadsheet.SEP_W / 2
    assert {"vsplit:scaling_factors", "vsplit:mapping", "vsplit:tuning"} <= set(cells)
    assert "vsplit:counts" not in cells  # the counts tile (two scalar tallies, not a matrix) gets none
    # the mapped unrotated vector list (M·V) draws NO inter-entry separator rules (the stray-
    # separator bug is fixed); the lone C|U bar is its only divider
    assert not any(c.startswith("sep:mapped_comma:") for c in cells)


def test_projection_v_column_divider_is_set_for_the_whole_column():
    # the C|U bar is a property of the COLUMN, not a hand-kept row list: every consolidating tile
    # gets it — derived from the emitted U cells, so a new consolidating row can't silently miss it.
    cells = {c.id: c for c in _with(projection=True).cells}
    assert {"vsplit:quantities", "vsplit:vectors", "vsplit:scaling_factors",
            "vsplit:projection", "vsplit:mapping", "vsplit:tuning"} <= set(cells)
    assert "vsplit:counts" not in cells  # the lone exclusion: two scalar tallies, no rule between them


def test_superspace_unrotated_vector_lists_consolidate_v_and_get_the_divider():
    # the superspace twins of the interval-vectors / mapping rows are renamed to "unrotated vector
    # list in superspace [generators]" over the V column, so they must render the unchanged half U
    # too (B_L·U and M_s→L·U), not just the comma half — and then carry the same lone C|U divider.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["projection"] = s["nonstandard_domain"] = True
    cells = {c.id: c for c in spreadsheet.build(state, s, held_basis_ratios=("2/1", "3/1")).cells}
    # the lifted unchanged half: 2/1 → [1,0,0,0], 3/1 → [0,1,0,0] over the superspace primes (2,3,5,13)
    assert [cells[f"cell:ss_vectors:commas:{p}:u0"].text for p in range(4)] == ["1", "0", "0", "0"]
    assert [cells[f"cell:ss_vectors:commas:{p}:u1"].text for p in range(4)] == ["0", "1", "0", "0"]
    # the unchanged half mapped into the superspace generators (M_s→L·u) renders too
    assert any(cid.startswith("cell:ss_mapping:commas:") and ":u0" in cid for cid in cells)
    # both tiles now carry the divider, in the same C|U gap as the rest of the column
    assert cells["vsplit:ss_vectors"].x == cells["vsplit:vectors"].x
    assert cells["vsplit:ss_mapping"].x == cells["vsplit:vectors"].x
    # the U half sits right of the divider, the comma half left of it (the bar genuinely splits the tile)
    assert cells["cell:ss_vectors:commas:0:0"].x < cells["vsplit:ss_vectors"].x < cells["cell:ss_vectors:commas:0:u0"].x


def test_mapped_comma_basis_has_no_stray_separators_off_projection():
    # the long-standing bug: a 2+-comma mapped basis drew dividing rules between its entries
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}  # r=1, n=2 commas
    assert any(c.startswith("cell:mapped_comma:") for c in cells)  # the tile renders
    assert not any(c.startswith("sep:mapped_comma:") for c in cells)  # …but with no separators


def test_projection_v_column_fans_one_gridline_per_subcolumn():
    lines = {ln.id for ln in _with(projection=True).lines}
    assert {"v:comma:0", "v:comma:1", "v:comma:2"} <= lines  # n+u = 3 sub-axes


def test_projection_keeps_the_comma_add_remove_controls():
    cells = {c.id: c for c in _with(projection=True).cells}
    # commas stay addable/removable in the consolidated V view (adding one shrinks U by a column);
    # the + rides the rightmost comma's branch point — no free stub past it, U holds the next slots —
    # and each comma carries its own − hover zone. No +/− on the unchanged half.
    assert "comma_plus" in cells and "comma_minus:0" in cells
    assert cells["comma_plus"].x < cells["cell:unchanged:0:0"].x   # the + sits left of U
    # the + rides the C|U gap — the visual "next comma" slot between the comma half and U — kept clear
    # of BOTH the − (on the lone comma's branch point) and U's first reorder grip, so it doesn't sit on
    # U's gridline and occlude grip:unchanged:0 (layout-invariants-2)
    assert abs(cells["comma_plus"].x - (cells["cell:comma:0:0"].x + spreadsheet.COL_W + spreadsheet.V_SPLIT_GAP / 2 - spreadsheet.BTN / 2)) < 0.51
    # and a COL_W clear of the − hover zone on the lone comma (so the + is actually clickable)
    assert cells["comma_plus"].x - cells["comma_minus:0"].x >= spreadsheet.COL_W - spreadsheet.BTN


def test_projection_at_full_rank_shows_the_complete_unchanged_basis():
    # removing the LAST comma → just intonation (n = 0): nothing is tempered, so P = I and the column
    # is the FULL unchanged basis — all d primes, no comma half — NOT a wiped-out empty column.
    s = settings.defaults()
    s["projection"] = True
    cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
    assert not any(c.startswith("cell:comma:") for c in cells)   # no commas (C empty)
    assert [[cells[f"cell:unchanged:{p}:{j}"].text for p in range(3)] for j in range(3)] == \
        [["1", "0", "0"], ["0", "1", "0"], ["0", "0", "1"]]      # U = all d primes
    assert [cells[f"cell:scaling:u{j}"].text for j in range(3)] == ["1", "1", "1"]  # every prime unchanged (nc=0: all of V is U)
    assert "comma_plus" in cells           # …and a + to add a first comma back
    assert not any(c.startswith("comma_minus") for c in cells)  # nothing to remove
    # no comma half, so no C|U divider and no wasted gap — U starts at the column's left and runs flush
    assert not any(c.startswith("vsplit:") for c in cells)
    assert cells["cell:unchanged:0:1"].x - cells["cell:unchanged:0:0"].x == spreadsheet.COL_W


def test_projection_at_full_rank_keeps_the_nullity_count_in_a_readable_stub():
    # at n = 0 the comma half is empty, but the counts tile must still show "n = 0" and its "nullity"
    # caption on ONE line — so a comma-half STUB is reserved to the LEFT of the EBK bracket, wide
    # enough for the word. The unchanged half (and the bracket) sit to its right, flush to U.
    s = settings.defaults()
    s["projection"] = True
    s["counts"] = True
    cells = {c.id: c for c in spreadsheet.build(
        service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
    n_count = cells["count:commas"]              # the n = 0 tally still renders (not dropped)
    assert n_count.text.endswith("= 0")
    cap = cells["caption:counts:commas"]         # …and "nullity" fits on a single line in the stub
    assert cap.text == "nullity"
    assert spreadsheet._wrap_lines("nullity", cap.w) == 1
    # the stub sits LEFT of the bracket; the unchanged count + first U cell sit to its right
    assert n_count.x == cap.x < cells["bracket:vec:commas:l"].x <= cells["cell:unchanged:0:0"].x
    assert cells["count:commas:u"].x == cells["cell:unchanged:0:0"].x   # u tally over U
    # the bracket still hugs U on both sides — the stub is OUTSIDE the matrix (no gap inside the EBK)
    assert cells["bracket:vec:commas:l"].x + spreadsheet.BRACKET_W == cells["cell:unchanged:0:0"].x


def test_projection_pending_comma_reddens_the_unchanged_interval_it_will_delete():
    # adding a comma drops the rank by one, deleting an unchanged interval — preview that interval with
    # the app's STANDARD remove highlight (CellBox.preview_remove → rtt-preview-remove), across its
    # WHOLE column (every value tile, not a smattering, not just a couple of tiles), while the draft
    # is open.
    s = settings.defaults()
    s["projection"] = True
    s["counts"] = True
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None])
    cells = {c.id: c for c in lay.cells}
    nu = sum(1 for i in cells if i.startswith("cell:unchanged:0:"))
    assert nu >= 2
    last = nu - 1   # the doomed U column's index — its V-band cells ride the u{j} namespace
    # the doomed column reddens across EVERY value tile: vectors, the ratio, mapping, all three size
    # rows, P·V and the scaling factor — one consistent preview, the whole column
    doomed_ids = ([f"cell:unchanged:{p}:{last}" for p in range(3)] + [f"unchanged:{last}"]
                  + [f"cell:mapped_unchanged:{i}:{last}" for i in range(2)]
                  + [f"tuning:comma:u{last}", f"just:comma:u{last}", f"retune:comma:u{last}"]
                  + [f"cell:proj_v:{p}:u{last}" for p in range(3)] + [f"cell:scaling:u{last}"])
    assert all(cells[cid].preview_remove for cid in doomed_ids), \
        [cid for cid in doomed_ids if not cells[cid].preview_remove]
    # the earlier U column, the unchanged count/caption, and the drag grip are NOT reddened
    assert not any(cells[f"cell:unchanged:{p}:0"].preview_remove for p in range(3))
    assert not cells["count:commas:u"].preview_remove
    assert not cells[f"grip:unchanged:{last}"].preview_remove
    # with NO draft open, nothing is doomed
    plain = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                              held_basis_ratios=("2/1", "5/4"))
    assert not any(c.preview_remove for c in plain.cells)


def test_unchanged_columns_have_cross_list_drag_grips():
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), drag_to_combine=True).cells}
    # each KNOWN unchanged interval gets a drag grip — a cross-list drag SOURCE (drop it on another
    # list to copy it there), on its own U sub-axis, like the comma/target/held/interest columns
    assert cells["grip:unchanged:0"].kind == "colgrip"
    assert cells["grip:unchanged:1"].kind == "colgrip"
    assert cells["grip:unchanged:0"].x == cells["cell:unchanged:0:0"].x   # rides the first U column
    assert cells["grip:unchanged:1"].x == cells["cell:unchanged:0:1"].x
    # no drop-into-U "add" zone — U is derived, nothing is dropped INTO it (see editor.move_interval)
    assert "grip:unchanged:add" not in cells


def test_projection_pending_comma_pushes_the_unchanged_half_past_the_draft():
    # adding a comma opens a pending draft column at index nc; the unchanged half U must sit PAST it
    # (and past the C|U gap), so the draft and U never overlap
    s = settings.defaults()
    s["projection"] = True
    lay = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                            held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None])
    cells = {c.id: c for c in lay.cells}
    draft = cells["cell:comma:0:1"]            # the draft column rides at nc = 1
    u_first = cells["cell:unchanged:0:0"]      # the first unchanged column
    assert u_first.x > draft.x + spreadsheet.COL_W   # U is past the draft (with the gap between)


def test_projection_v_column_counts_both_nullity_and_unchanged():
    cells = {c.id: c for c in _with(projection=True, counts=True).cells}
    # the consolidated V = C|U carries two counts: the nullity n over the comma half and the
    # unchanged interval count u over the unchanged half (meantone: n=1, u=2)
    assert cells["count:commas"].text.endswith("= 1")        # n = 1 (nullity)
    assert cells["count:commas:u"].text.endswith("= 2")      # u = 2 (unchanged intervals)
    # the u-count sits over the unchanged sub-columns, right of the n-count
    assert cells["count:commas:u"].x == cells["cell:unchanged:0:0"].x
    assert cells["count:commas"].x < cells["count:commas:u"].x
    # each half is NAMED too, the name centred over the same area as its tally
    assert cells["caption:counts:commas"].text == "nullity"
    assert cells["caption:counts:commas:u"].text == "unchanged interval count"
    assert (cells["caption:counts:commas"].x, cells["caption:counts:commas"].w) == (cells["count:commas"].x, cells["count:commas"].w)
    assert (cells["caption:counts:commas:u"].x, cells["caption:counts:commas:u"].w) == (cells["count:commas:u"].x, cells["count:commas:u"].w)


def test_projected_unrotated_vector_list_tile_is_complete():
    # the P·V tile carries the full complement like every other V-column tile: a symbol, a units
    # line, and a plain-text EBK string (not just the gridded cells)
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), symbols=True, units=True, plain_text_values=True).cells}
    assert cells["symbol:projection:commas"].text == "𝑃V"      # P·V (= V·diag(λ)); italic 𝑃 operator
    assert cells["units:projection:commas"].text == "units: p"  # prime-count vectors, like V
    # the plain text shows the WHOLE column V = C|U: P·𝐜 = 𝟎 (commas vanish) then P·𝐮 = 𝐮 (held)
    assert cells["ptext:projection:commas"].text == "[[0 0 0⟩ [1 0 0⟩ [-2 0 1⟩]"


def test_consolidated_v_column_reads_green():
    # V = C|U mixes the comma half (temperament/yellow) with the unchanged/held half (tuning/cyan),
    # so the whole column reads GREEN — every tile carries BOTH washes when both colorizations are on
    blocks = {b.id for b in _proj_build(("2/1", "5/4"),
                                        temperament_colorization=True, tuning_colorization=True).blocks}
    for r in ("vectors", "mapping", "scaling_factors", "projection", "tuning", "just", "retune"):
        assert f"wash:temperament:{r}:commas" in blocks, r   # yellow (the comma half C)
        assert f"wash:tuning:{r}:commas" in blocks, r        # cyan (the unchanged half U) → green
    # off projection the comma column is its plain temperament yellow — no tuning wash (regression)
    off = {b.id for b in _with(temperament_colorization=True, tuning_colorization=True).blocks}
    assert "wash:temperament:vectors:commas" in off and "wash:tuning:vectors:commas" not in off


def test_v_column_plain_text_shows_both_the_comma_and_unchanged_halves():
    # the inline plain text matches the grid for the WHOLE consolidated V = C|U — not just C. Every
    # value tile appends the unchanged half U (here 2/1, 5/4 under a full rational hold).
    cells = {c.id: c for c in _proj_build(("2/1", "5/4"), plain_text_values=True, weighting=True).cells}
    assert cells["ptext:vectors:commas"].text == "[[4 -4 1⟩ [1 0 0⟩ [-2 0 1⟩]"   # C | U vectors
    assert cells["ptext:mapping:commas"].text == "[[0 0} [1 0} [-2 4}]"           # M·C=0 | M·U
    assert cells["ptext:tuning:commas"].text == "[0.000 1200.000 386.314]"        # comma | unchanged sizes
    assert cells["ptext:scaling_factors:commas"].text == "[0 1 1]"                # λ over C|U
    # under-held, the unchanged half dashes out in the plain text exactly as in the grid
    dashed = {c.id: c for c in _proj_build(plain_text_values=True).cells}
    assert dashed["ptext:vectors:commas"].text == "[[4 -4 1⟩ [— — —⟩ [— — —⟩]"
    assert dashed["ptext:tuning:commas"].text == "[0.000 — —]"
    # OFF projection the column is just C again (no consolidation, no U) — regression guard
    off = {c.id: c for c in _with(plain_text_values=True).cells}
    assert off["ptext:vectors:commas"].text == "[[4 -4 1⟩]"


def test_no_scaling_factors_or_unchanged_columns_without_projection():
    cells = {c.id for c in _layout().cells}  # projection off (default)
    assert "label:scaling_factors" not in cells
    assert not any(c.startswith("cell:scaling:") for c in cells)
    assert not any(c.startswith("cell:unchanged:") for c in cells)


def test_v_consolidation_needs_the_commas_column_present():
    # V = C|U lives in the commas column; with the temperament tiles off that column is gone,
    # so projection-on adds no consolidation and no (empty) scaling-factors row
    cells = {c.id for c in _with(projection=True, temperament_tiles=False).cells}
    assert "label:scaling_factors" not in cells
    assert not any(c.startswith(("cell:scaling:", "cell:unchanged:")) for c in cells)


def test_projection_relabels_the_whole_column_as_the_unrotated_vector_list():
    # the consolidated column is the unrotated vector list V = C|U — the column TITLE and EVERY
    # tile's name/symbol read V / "unrotated vector list", not C / "comma basis" (the "(made to
    # vanish!)" note drops too: only the comma half of V vanishes, which the λ = 0 row marks)
    named = {c.id: c for c in _with(projection=True).cells}
    assert named["header:commas"].text == "unrotated\nvector list"            # the column title
    assert named["caption:vectors:commas"].text == "unrotated vector list"
    assert named["caption:mapping:commas"].text == "mapped unrotated vector list"
    # where the rename would double "list" ("…vector list interval size list") the first is dropped
    assert named["caption:tuning:commas"].text == "tempered unrotated vector interval size list"
    assert named["caption:just:commas"].text == "(just) unrotated vector interval size list"
    symd = {c.id: c for c in _with(projection=True, symbols=True, equivalences=True).cells}
    assert symd["symbol:vectors:commas"].text == "V = C|U"
    assert symd["symbol:mapping:commas"].text == "𝑀V"   # C → V; the "= 𝑂" vanish-equivalence dropped
    assert symd["symbol:tuning:commas"].text == "𝒕V"
    # off projection it stays the plain comma basis C
    plain = {c.id: c for c in _with(symbols=True).cells}
    assert plain["header:commas"].text == "commas"
    assert plain["caption:vectors:commas"].text == "comma basis"
    assert plain["symbol:vectors:commas"].text == "C"


def test_projection_v_column_labels_are_v_and_lambda():
    cells = {c.id: c for c in _with(projection=True, symbols=True, header_symbols=True).cells}
    # the C|U split is the vertical bar, so every V sub-column is labelled 𝐯ᵢ (not a 𝐜/𝐮 split)
    assert [cells[f"matlabel:col:vectors:commas:{i}"].text for i in range(3)] == ["𝐯₁", "𝐯₂", "𝐯₃"]
    assert cells["matlabel:col:mapping:commas:2"].text == "𝑀𝐯₃"   # the mapping over V: 𝑀𝐯ᵢ
    # the scaling-factors row: bold-italic 𝝀 tile symbol, italic 𝜆ᵢ per-column scalar headers
    assert cells["symbol:scaling_factors:commas"].text == "𝝀"
    assert [cells[f"matlabel:col:scaling_factors:commas:{i}"].text for i in range(3)] == ["𝜆₁", "𝜆₂", "𝜆₃"]


def test_projection_prescaling_and_complexity_rows_span_v():
    # with complexity weighting on, the prescaling (𝐿·v) and complexity (‖𝐿·v‖) rows run over
    # V = C|U too — the unchanged intervals get prescaled / normed exactly like the commas
    cells = {c.id: c for c in _with("minimax-S", projection=True, weighting=True).cells}
    # prescaling: a d-tall 𝐿·v matrix per V sub-column; the two unchanged columns ride the
    # u{j} namespace (nc=1 here), so row 0 of each appears
    assert {"cell:prescaling:commas:0:u0", "cell:prescaling:commas:0:u1"} <= set(cells)
    # complexity: the list 𝒄 = ‖𝐿·v‖ over all d V sub-columns
    assert {"complexity:comma:0", "complexity:comma:u0", "complexity:comma:u1"} <= set(cells)
    # the unchanged complexity sits on its V sub-axis (aligned with its vector column)
    assert cells["complexity:comma:u1"].x == cells["cell:unchanged:0:1"].x


def test_v_column_unchanged_basis_follows_the_held_basis():
    # U is the held basis, so the held intervals / established-projection chooser drive the V = C|U
    # column: holding {2/1, 5/4} (quarter-comma) vs {2/1, 6/5} (third-comma) changes the second
    # unchanged column from 5/4 to 6/5.
    quarter = {c.id: c for c in _proj_build(("2/1", "5/4")).cells}
    third = {c.id: c for c in _proj_build(("2/1", "6/5")).cells}
    assert [quarter[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["-2", "0", "1"]  # 5/4
    assert [third[f"cell:unchanged:{p}:1"].text for p in range(3)] == ["1", "1", "-1"]     # 6/5


def _assert_ptext_cells_match(lay, pt):
    # every rendered ptext band cell carries exactly the string the direct derivation gives
    ptext_cells = [c for c in lay.cells if c.id.startswith("ptext:")]
    assert len(ptext_cells) >= 8  # the band is actually on, so the loop below isn't vacuous
    for c in ptext_cells:
        _, rkey, ckey = c.id.split(":")
        assert c.text == pt[(rkey, ckey)], c.id


def test_ptext_band_matches_a_direct_derivation_under_a_custom_prescaler():
    # the band is built FROM the grid's DerivedQuantities bundle; a direct (self-deriving)
    # plain_text_values call over the same document must produce identical strings. The
    # custom prescaler is one of the knobs that historically diverged the two views.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(state, {**settings.defaults(), "plain_text_values": True},
                            custom_prescaler=(1.0, 2.0, 3.0))
    pt = service.plain_text_values(state, service.DEFAULT_DOCUMENT_SCHEME,
                                   custom_prescaler=(1.0, 2.0, 3.0))
    _assert_ptext_cells_match(lay, pt)


def test_ptext_band_matches_a_direct_derivation_under_a_manual_generator_tuning():
    # a frozen manual tuning takes the bundle's tun straight from the grid's
    # tuning_from_generators result — same strings as a direct self-deriving call
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    lay = spreadsheet.build(state, {**settings.defaults(), "plain_text_values": True},
                            generator_tuning=(1201.7, 697.6))
    pt = service.plain_text_values(state, service.DEFAULT_DOCUMENT_SCHEME,
                                   generator_tuning=(1201.7, 697.6))
    _assert_ptext_cells_match(lay, pt)


def test_ptext_band_matches_a_direct_derivation_over_the_superspace():
    # the chapter-9 block rides the bundle's memoized superspace_tun (the grid's one solve);
    # the direct call solves it itself — both must give the same ss tile strings
    lay = _barbados_ss(plain_text_values=True)
    pt = service.plain_text_values(_barbados_state(), service.DEFAULT_DOCUMENT_SCHEME,
                                   superspace=True)
    _assert_ptext_cells_match(lay, pt)


# --- Audit fixes: draft-column holes, V-column label alignment, grip occlusion, mean-damage symbol ---


def test_projection_row_grows_a_draft_column_for_target_held_interest_drafts():
    # projection-4 / render-fiddle-7: a pending target/held/interest draft gets a blank GREEN
    # placeholder in the projection row's P·T / P·H / P·interest tile, so the draft column reads green
    # top-to-bottom (like P·V's comma draft and the mapped/tuning rows) instead of a hole.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "projection": True, "optimization": True}
    k = _target_count()
    pt = {c.id: c for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
    assert all(pt[f"cell:proj_pt:draft:{p}"].pending and pt[f"cell:proj_pt:draft:{p}"].text == "" for p in range(3))
    assert pt["cell:proj_pt:draft:0"].x == pt[f"cell:proj_pt:{k - 1}:0"].x + spreadsheet.COL_W  # one slot past committed P·T
    ph = {c.id: c for c in spreadsheet.build(base, s, pending_held=[None, None, None]).cells}
    assert all(ph[f"cell:proj_ph:draft:{p}"].pending and ph[f"cell:proj_ph:draft:{p}"].text == "" for p in range(3))
    pi = {c.id: c for c in spreadsheet.build(base, s, interest=((1, 1, -1),), pending_interest=[None, None, None]).cells}
    assert all(pi[f"cell:proj_pi:draft:{p}"].pending and pi[f"cell:proj_pi:draft:{p}"].text == "" for p in range(3))
    # no draft → no draft column in the projection row (regression guard)
    none = {c.id for c in spreadsheet.build(base, s, interest=((1, 1, -1),)).cells}
    assert not any(i.startswith(("cell:proj_pt:draft", "cell:proj_ph:draft", "cell:proj_pi:draft")) for i in none)


def test_scaling_factors_grows_a_green_draft_column_for_a_pending_comma():
    # layout-invariants-3: the λ scaling-factors row gets a blank GREEN placeholder at the pending
    # comma's draft slot (which comma_value_pos skips for the U half), so λ reads green top-to-bottom.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "projection": True}
    c = {cb.id: cb for cb in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None]).cells}
    assert c["cell:scaling:draft"].pending and c["cell:scaling:draft"].text == ""
    assert c["cell:scaling:draft"].x == c["cell:proj_v:0:draft"].x   # aligned with the projection row's comma draft
    assert "cell:scaling:draft" not in {cb.id for cb in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}


def test_superspace_lifted_lists_grow_draft_columns_for_interval_drafts():
    # layout-invariants-3: on a nonstandard domain the lifted ss_vectors / ss_mapping tiles get a blank
    # GREEN placeholder for a pending interval draft, like the on-domain vectors/mapping rows — not a
    # hole inside their list brackets.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # barbados: dL = 4, rL = 3
    s = {**settings.defaults(), "nonstandard_domain": True}
    ss = {c.id: c for c in spreadsheet.build(state, s, pending_target=[None, None, None]).cells}
    vrows = sum(1 for i in ss if i.startswith("cell:ss_vectors:targets:") and i.endswith(":0"))  # dL committed rows
    mrows = sum(1 for i in ss if i.startswith("cell:ss_mapping:targets:") and i.endswith(":0"))   # rL committed rows
    assert vrows and mrows
    assert all(ss[f"cell:ss_vectors:targets:{p}:draft"].pending and ss[f"cell:ss_vectors:targets:{p}:draft"].text == "" for p in range(vrows))
    assert all(ss[f"cell:ss_mapping:targets:{g}:draft"].pending and ss[f"cell:ss_mapping:targets:{g}:draft"].text == "" for g in range(mrows))
    # a pending comma fills the lifted comma tiles too
    ssc = {c.id: c for c in spreadsheet.build(state, s, pending_comma=[None, None, None]).cells}
    assert ssc["cell:ss_vectors:commas:0:draft"].pending and ssc["cell:ss_mapping:commas:0:draft"].pending
    # no draft → no placeholder (regression guard)
    plain = {c.id for c in spreadsheet.build(state, s).cells}
    assert not any(i.startswith("cell:ss_vectors:targets") and i.endswith("draft") for i in plain)


def test_v_column_labels_track_their_cells_during_a_pending_comma():
    # layout-invariants-1 / projection-5 / render-fiddle-8: with a pending comma the consolidated V's
    # U-half value cells shift right past the draft slot (comma_value_pos); the column labels must
    # follow — else every U label sits a slot LEFT (over the draft) and the last U column is unlabelled.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "projection": True, "header_symbols": True}  # header_symbols drives matlabel
    c = {cb.id: cb for cb in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4"), pending_comma=[None, None, None]).cells}
    # meantone, projection on: 1 comma + draft + 2 U → labels 0,1,2 (nc + nu = 3); the draft is unlabelled
    assert c["matlabel:col:vectors:commas:0"].x == c["cell:comma:0:0"].x        # 𝐯₁ over the comma
    assert c["matlabel:col:vectors:commas:1"].x == c["cell:unchanged:0:0"].x    # 𝐯₂ over U col 0 (NOT the draft)
    assert c["matlabel:col:vectors:commas:2"].x == c["cell:unchanged:0:1"].x    # 𝐯₃ over the LAST U col (now labelled)
    assert "matlabel:col:vectors:commas:3" not in c                            # exactly nc + nu labels
    assert c["matlabel:col:vectors:commas:1"].x != c["cell:comma:0:1"].x        # no label over the draft column
    assert c["matlabel:col:projection:commas:1"].x == c["cell:proj_v:0:u0"].x  # the whole V band tracks together
    # off-draft this is a no-op: labels sit on their plain columns (regression guard)
    rest = {cb.id: cb for cb in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}
    assert rest["matlabel:col:vectors:commas:1"].x == rest["cell:unchanged:0:0"].x


def test_comma_add_drop_zone_does_not_occlude_the_unchanged_grips():
    # layout-invariants-2: the comma list's "add" drop zone (grip:commas:add) overlapped U's reorder
    # grips — 14px under V = C|U, EXACTLY coincident at full rank (where the comma drop target was then
    # dead). It now rides the C|U gap (or the nullity stub at full rank), narrowed to that stub, clear of
    # U's grips on their own sub-axes. (End-to-end drag behaviour should be re-checked in a real browser.)
    def overlap(a, b):
        return max(a.x, b.x) < min(a.x + a.w, b.x + b.w) - 0.01
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "projection": True, "drag_to_combine": True}
    # n ≥ 1 (meantone, projection on, U held rational): add zone in the gap, left of U's first grip
    on = {c.id: c for c in spreadsheet.build(base, s, held_basis_ratios=("2/1", "5/4")).cells}
    assert not overlap(on["grip:commas:add"], on["grip:unchanged:0"])
    assert on["grip:commas:add"].x + on["grip:commas:add"].w <= on["grip:unchanged:0"].x + 0.51
    # full rank (n = 0): the add zone rides the reserved nullity stub, NOT U's first sub-axis where it
    # used to coincide EXACTLY with grip:unchanged:0
    full = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
    assert not overlap(full["grip:commas:add"], full["grip:unchanged:0"])
    assert full["grip:commas:add"].x + full["grip:commas:add"].w <= full["grip:unchanged:0"].x + 0.51
    assert full["comma_plus"].x < full["cell:unchanged:0:0"].x  # the + sits in the stub, left of U


def test_units_row_draft_columns_match_across_the_interval_lists():
    # layout-invariants-4: the units row's /1 (and the units column's gₙ/) over a pending draft column
    # was emitted for the comma draft but not the target/held/interest drafts or the mapping-row draft.
    # Now the *_shown counts include the draft, so every draft column reads complete.
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "domain_units": True, "optimization": True}
    k = _target_count()
    ut = {c.id for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
    assert f"urow:targets:{k}" in ut                       # the target draft column carries /1
    ui = {c.id for c in spreadsheet.build(base, s, interest=((1, 1, -1),), pending_interest=[None, None, None]).cells}
    assert "urow:interest:1" in ui                          # interest draft (1 committed + draft)
    uh = {c.id for c in spreadsheet.build(base, s, held_vectors=((-1, 1, 0),), pending_held=[None, None, None]).cells}
    assert "urow:held:1" in uh                              # held draft (1 committed + draft)
    um = {c.id for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
    assert "ucol:mapping:2" in um                           # the pending mapping-row's gₙ/ label (r = 2 → draft row 2)
    rest = {c.id for c in spreadsheet.build(base, s).cells}  # no draft → no extra labels (regression guard)
    assert f"urow:targets:{k}" not in rest and "ucol:mapping:2" not in rest


def test_all_interval_mean_damage_value_and_symbol_denote_the_same_quantity():
    # tuning-core-6 / all-interval-alt-complexity-5: the displayed value is the dual-power MEAN (RMS for
    # ES — see test_..._aggregates_at_the_dual_norm_power), so its symbol must be the double-angle
    # power-MEAN ⟪…⟫, NOT a single-bar NORM ‖…‖. The norm = sqrt(SUM of squares) is √d larger than the
    # mean = sqrt(sum/d); labelling the mean with a norm symbol read √d too large (minimax-ES meantone: the
    # value 1.582 under a symbol naming the 2.741 norm).
    import math
    from rtt.library import tuning
    from rtt.library.parsing import parse_temperament_data
    base = service.from_mapping(((1, 0, -4), (0, 1, 4)))  # meantone, d = 3
    t = parse_temperament_data("[⟨1 0 -4] ⟨0 1 4]}")
    cells = {c.id: c for c in spreadsheet.build(base, {**settings.defaults(), "optimization": True},
                                                tuning_scheme="minimax-ES").cells}
    sym = cells["optimization:mean_damage:symbol"].text
    assert "⟪" in sym and "⟫" in sym and "‖" not in sym       # double-angle MEAN brackets, not a norm
    val = float(cells["optimization:mean_damage"].text)
    mean = tuning.get_tuning_map_mean_damage(t, tuning.optimize_tuning_map(t, "minimax-ES"), "minimax-ES")
    assert val == pytest.approx(mean, abs=1e-3)               # the value IS that mean (matches the ⟪…⟫ symbol)
    norm = val * math.sqrt(3)                                 # the single-bar NORM the OLD symbol named is √d larger
    assert norm == pytest.approx(2.741, abs=1e-2) and abs(val - norm) > 1.0  # value is the mean, NOT the norm


# --- per-sub-row ET picker / per-sub-column comma picker placement ---------------------


def test_etpick_rides_the_right_gutter_of_each_mapping_row():
    cells = {c.id: c for c in _with(presets=True).cells}
    for i in range(2):  # meantone, rank 2
        ep = cells[f"etpick:{i}"]
        assert ep.kind == "etpick" and ep.gen == i
        assert ep.w == spreadsheet.COL_W and ep.h == spreadsheet.ROW_H
        assert ep.y == cells[f"cell:mapping:{i}:0"].y   # the picker shares the row
        # it sits to the RIGHT of the row, clearing the closing ] bracket (the analogue of the
        # comma picker below each column; the crowded left — handles, 𝒎ᵢ labels — stays clear)
        close_bracket = cells[f"bracket:map:{i}:r"]
        assert ep.x >= close_bracket.x + close_bracket.w
    # gone without presets
    off = {c.id: c for c in _with(presets=False).cells}
    assert not any(k.startswith("etpick:") for k in off)


def test_et_picker_keeps_the_mapping_matrix_centred_in_its_tile():
    # the per-row ET pickers ride the primes column's RIGHT gutter (past the ]). That gutter REUSES
    # the empty space that already balanced the left furniture (drag handles + 𝒎ᵢ row labels): the
    # left is padded only enough to keep the two gutters EQUAL, so the matrix stays horizontally
    # centred in its tile rather than being shoved left with a dead band on the right (the bug this
    # guards). Exercised in the user's config — handles + row headers + pickers all on.
    lay = _with(presets=True, drag_to_combine=True, header_symbols=True)
    cells = {c.id: c for c in lay.cells}
    tile = {b.id: b for b in lay.blocks}["block:primes"]  # the mapping·primes grey panel (spans the column)
    lb, rb = cells["bracket:map:0:l"], cells["bracket:map:0:r"]
    m_left, m_right = lb.x, rb.x + rb.w                   # the EBK matrix span (⟨ … ])
    assert abs((m_left - tile.x) - ((tile.x + tile.w) - m_right)) < 0.51  # equal gutters → centred
    # the picker fills that right gutter, past the ], reaching the tile edge — no dead band beyond it
    ep = cells["etpick:0"]
    assert ep.x >= m_right
    assert abs((ep.x + ep.w) - (tile.x + tile.w - spreadsheet.PAD)) < 0.51
    # the left furniture sits in the matching left gutter: the handle outside the row label, the
    # label butting up against the matrix's opening ⟨
    handle, label = cells["map_drag:0"], cells["matlabel:row:mapping:primes:0"]
    assert tile.x <= handle.x and handle.x + handle.w <= label.x
    assert abs((label.x + label.w) - m_left) < 0.51


def test_commapick_rides_below_each_real_comma_column():
    cells = {c.id: c for c in _with(presets=True).cells}
    cp = cells["commapick:0"]  # meantone has one comma
    assert cp.kind == "commapick" and cp.comma == 0
    assert cp.w == spreadsheet.COL_W and cp.h == spreadsheet.ROW_H
    column_cell = next(c for cid, c in cells.items()
                       if cid.startswith("cell:comma:0:") and c.comma == 0)
    assert cp.x == column_cell.x   # aligned under its column
    assert cp.y > column_cell.y    # below the matrix (and its ⟩ foot)
    assert not any(c.id.startswith("commapick:") for c in _with(presets=False).cells)


def test_a_full_rank_temperament_has_no_comma_pickers():
    # no commas -> no comma column -> no per-column pickers, and no reserved band
    full = spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))),
                             {**settings.defaults(), "presets": True})
    assert not any(c.id.startswith("commapick:") for c in full.cells)
    assert any(c.id.startswith("etpick:") for c in full.cells)  # but still one ET picker per row


def test_green_draft_row_and_column_get_their_own_pickers():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = {**settings.defaults(), "presets": True}
    # a pending comma draft gets a commapick under its (green) column
    cc = {c.id: c for c in spreadsheet.build(base, s, pending_comma=[None, None, None]).cells}
    assert "commapick:draft" in cc and cc["commapick:draft"].pending
    draft_col = next(c for cid, c in cc.items() if cid.startswith("cell:comma:0:") and c.pending)
    assert cc["commapick:draft"].x == draft_col.x   # aligned under the draft column
    # a pending mapping row gets its own ET picker, to the right like the committed rows
    mc = {c.id: c for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
    assert "etpick:draft" in mc and mc["etpick:draft"].pending
    assert mc["etpick:draft"].x == mc["etpick:0"].x   # same right gutter as the committed rows
    # adding the FIRST comma to a full-rank temperament still reserves the band + draft picker
    full = spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))),
                             s, pending_comma=[None, None, None])
    assert any(c.id == "commapick:draft" for c in full.cells)
