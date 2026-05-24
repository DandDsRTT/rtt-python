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


def test_minus_is_revealed_above_the_removable_prime_clear_of_its_input():
    # only the highest prime can be dropped (service.shrink_domain trims the last),
    # so its hover-minus rides that column — above the header, never over the
    # editable mapping cell below it (which would block editing the column).
    cells = {c.id: c for c in _layout().cells}
    minus, last_prime = cells["minus"], cells["prime:2"]
    input_below = cells["cell:mapping:0:2"]
    assert minus.x == last_prime.x  # shares the removable column
    assert minus.y < last_prime.y  # revealed above the header, not beside the block
    assert minus.y + minus.h <= input_below.y  # and clear of the editable input


def test_minus_tracks_the_new_last_prime_after_a_shrink():
    shrunk = service.shrink_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # d=2
    cells = {c.id: c for c in spreadsheet.build(shrunk).cells}
    assert "prime:2" not in cells  # only primes 0 and 1 remain
    assert cells["minus"].x == cells["prime:1"].x  # the minus follows to the new last column


def test_a_single_prime_domain_has_no_minus_but_keeps_plus():
    cells = {c.id for c in spreadsheet.build(service.from_mapping(((1,),))).cells}
    assert "minus" not in cells  # nothing is removable when d == 1
    assert {"plus", "prime:0"} <= cells  # ...but you can still expand


def test_target_intervals_column_with_mapped_list():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:targets"].text == "target-intervals"
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
    # the mapped target-interval list sits on the same square columns
    m00 = cells["cell:mapped:0:0"]
    assert m00.w == m00.h == spreadsheet.ROW_H
    assert cells["cell:mapped:0:1"].x == m00.x + m00.w


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
    # the spine column is not collapsible, mirroring the spine row
    assert "toggle:col:quantities" not in cells


def test_tuning_boxes_off_hides_the_tuning_rows():
    cells = {c.id for c in _with(tuning_boxes=False).cells}
    assert not any(c.split(":")[0] in {"tuning", "just", "retune", "damage"} for c in cells)
    assert {"label:tuning", "label:just", "label:retune", "label:damage"}.isdisjoint(cells)


def test_temperament_boxes_off_removes_mapping_and_the_domain_primes_column():
    off = {c.id: c for c in _with(temperament_boxes=False).cells}
    on = {c.id: c for c in _with().cells}
    # the mapping quantities (matrix, mapped list, generator ratios) are gone
    assert "label:mapping" not in off
    assert not any(c.startswith(("cell:mapping:", "cell:mapped:", "gen:")) for c in off)
    # the whole domain-primes column goes with it: its header, the prime headers,
    # and every row's prime-side cells -- including the tuning maps over primes
    assert "header:primes" not in off
    assert not any(c.startswith(("prime:", "tuning:prime:", "just:prime:", "retune:prime:")) for c in off)
    # tuning over the targets survives and rises into the freed space
    assert "tuning:target:0" in off
    assert off["tuning:target:0"].y < on["tuning:target:0"].y


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


def test_collapsed_column_keeps_its_title_at_a_width_that_fits_it():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    coll = {c.id: c for c in spreadsheet.build(base, collapsed={"col:targets"}).cells}["header:targets"]
    full = {c.id: c for c in spreadsheet.build(base).cells}["header:targets"]
    assert coll.text == "target-intervals"  # the title stays put (not blanked, not rotated)
    assert spreadsheet.STRIP < coll.w < full.w  # folded narrower, but wide enough to read the title


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


def test_mapped_list_rules_its_monzo_columns_apart_clear_of_the_marks():
    cells = {c.id: c for c in _layout().cells}
    # the mapped target-interval list separates its monzo columns with vertical
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
                       ("mapping", "gens"), ("mapping", "primes"), ("mapping", "targets"),
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


def test_preselects_off_shows_no_chooser_dropdowns():
    cells = {c.id for c in _with(preselects=False).cells}
    assert not any(c.startswith("preselect:") for c in cells)


def test_preselects_on_adds_the_three_chooser_dropdowns_under_their_tiles():
    cells = {c.id: c for c in _with(preselects=True).cells}
    assert {"preselect:temperament", "preselect:tuning", "preselect:target"} <= set(cells)
    # the temperament chooser sits under the mapping matrix, aligned to its column
    temp, matrix = cells["preselect:temperament"], cells["cell:mapping:0:0"]
    assert temp.y > matrix.y and temp.x == cells["header:primes"].x
    # the target chooser sits under the target-interval list (quantities row)
    assert cells["preselect:target"].x == cells["header:targets"].x


def test_tuning_and_target_choosers_show_the_live_selection_temperament_is_a_placeholder():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["preselects"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="POTE", target_spec="OLD").cells}
    assert cells["preselect:tuning"].text == "POTE"  # reflects the active scheme
    assert cells["preselect:target"].text == "OLD"  # reflects the active set
    assert cells["preselect:temperament"].text == ""  # a chooser placeholder, not a live value


def test_temperament_chooser_requires_the_mapping_tile_to_be_shown():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["preselects"], s["temperament_boxes"] = True, False
    cells = {c.id for c in spreadsheet.build(base, s).cells}
    assert "preselect:temperament" not in cells  # no mapping shown -> no temperament chooser
    assert "preselect:tuning" in cells  # the other choosers are unaffected


def test_preselect_dropdown_clears_the_row_below_it():
    cells = {c.id: c for c in _with(preselects=True).cells}
    drop, next_row = cells["preselect:tuning"], cells["label:just"]
    assert drop.y + drop.h <= next_row.y  # the reserved band keeps it off the next row


def test_build_honors_the_target_interval_spec():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5
    tilt = {c.text for c in spreadsheet.build(base, target_spec="TILT").cells if c.id.startswith("target:")}
    old = {c.text for c in spreadsheet.build(base, target_spec="OLD").cells if c.id.startswith("target:")}
    assert tilt != old  # the two families differ
    assert "8/5" in old and "8/5" not in tilt  # a diamond ratio absent from the triangle


def test_build_honors_the_tuning_scheme():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    top = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="TOP").cells}
    pote = {c.id: c.text for c in spreadsheet.build(base, tuning_scheme="POTE").cells}
    # POTE holds the octave pure; TOP stretches it — so the prime-2 tuning differs
    assert top["tuning:prime:0"] != pote["tuning:prime:0"]
    assert pote["tuning:prime:0"] == "1200.00"


def test_names_toggles_in_tile_captions_but_never_the_row_col_titles():
    on = {c.id: c for c in _with(names=True).cells}
    off = {c.id: c for c in _with(names=False).cells}
    # row labels and column headers are always present, independent of names
    assert {"label:mapping", "header:primes"} <= set(on)
    assert {"label:mapping", "header:primes"} <= set(off)
    # the in-tile quantity captions appear only when names is on
    assert on["caption:mapping:primes"].text == "(temperament) mapping"
    assert not any(c.startswith("caption:") for c in off)


# --- the commas column (the comma basis, the mapping's dual) ---

def _in_commas(cid):
    return cid.startswith(("comma:", "cell:comma:")) or cid.split(":")[0:2] in (
        ["tuning", "comma"], ["just", "comma"], ["retune", "comma"], ["damage", "comma"])


def test_commas_column_sits_between_primes_and_targets_with_its_comma_ratios():
    cells = {c.id: c for c in _layout().cells}
    assert cells["header:commas"].text == "commas"
    assert cells["comma:0"].text == "80/81"  # the syntonic comma, as-is from the dual
    # the commas band falls between domain primes and target-intervals
    assert cells["header:primes"].x < cells["header:commas"].x < cells["header:targets"].x
    assert cells["prime:2"].x < cells["comma:0"].x < cells["target:0"].x


def test_comma_basis_renders_as_vertical_monzos_in_the_mapping_row():
    cells = {c.id: c for c in _layout().cells}
    # the comma basis sits in the mapping row's commas column as d-tall monzo columns;
    # the syntonic comma [4, -4, 1] reads top-to-bottom (prime 2, 3, 5) down its column
    assert cells["cell:comma:0:0"].text == "4"
    assert cells["cell:comma:1:0"].text == "-4"
    assert cells["cell:comma:2:0"].text == "1"
    # the cells tile a square grid like the mapping matrix
    c00 = cells["cell:comma:0:0"]
    assert c00.w == c00.h == spreadsheet.ROW_H
    assert cells["cell:comma:1:0"].y == c00.y + c00.h
    # aligned in the commas column (shares the quantities-row comma's x and the matrix top)
    assert c00.x == cells["comma:0"].x
    assert c00.y == cells["cell:mapping:0:0"].y  # top-aligned with the mapping matrix


def test_expanding_commas_grows_the_mapping_band_to_fit_the_d_tall_comma_basis():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # d=3, r=2
    full = {c.id: c for c in spreadsheet.build(base).cells}
    coll = {c.id: c for c in spreadsheet.build(base, collapsed={"col:commas"}).cells}
    # the comma basis is d=3 tall while the mapping matrix is r=2 tall, so it reaches lower
    cb_bottom = full["cell:comma:2:0"].y + full["cell:comma:2:0"].h
    m_bottom = full["cell:mapping:1:0"].y + full["cell:mapping:1:0"].h
    assert cb_bottom > m_bottom
    # collapsing commas lets the band shrink back, lifting the tuning rows
    assert coll["tuning:prime:0"].y < full["tuning:prime:0"].y


def test_comma_sizes_fill_the_tuning_family_rows():
    cells = {c.id: c for c in _layout().cells}
    # the comma vanishes in the temperament: its tempered size is ~0
    assert cells["tuning:comma:0"].text == "0.00"
    # ...but it has a real just size (the syntonic comma is ~21.5 cents)
    assert cells["just:comma:0"].text == "-21.51"
    assert cells["retune:comma:0"].text == "21.51"
    assert cells["damage:comma:0"].text == "21.51"
    # comma tuning values share the comma column with the quantities-row ratio
    assert cells["tuning:comma:0"].x == cells["comma:0"].x


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
    assert blocks["block:damage:commas"].w == 0
    assert by_id["bus:commas:top"].length == 0  # the comma axis converges to one line


def test_comma_basis_is_framed_as_a_monzo_list_spanning_its_d_tall_height():
    cells = {c.id: c for c in _layout().cells}
    # the comma basis is a list of monzos: an enclosing [ ] plus per-column marks
    assert cells["bracket:comma_basis:l"].text == "[" and cells["bracket:comma_basis:r"].text == "]"
    assert "ebktop:comma_basis:0" in cells and "ebkbrace:comma_basis:0" in cells
    cb = cells["bracket:comma_basis:l"]
    # the enclosing bracket spans the full d=3 tall basis
    assert cb.y <= cells["cell:comma:0:0"].y
    assert cb.y + cb.h >= cells["cell:comma:2:0"].y + cells["cell:comma:2:0"].h


def test_each_mapping_matrix_brace_hugs_its_own_height_not_the_tallest():
    cells = {c.id: c for c in _layout().cells}
    last_map = cells["cell:mapping:1:0"]  # the maps are r=2 tall
    mbrace = cells["ebkbrace:primes"]
    # the mapping brace hugs the LAST map row (one frame gap below), rather than
    # floating at the bottom of the taller d-row comma band
    gap = mbrace.y - (last_map.y + last_map.h)
    assert 0 < gap <= spreadsheet.FRAME_GAP + 1
    # the comma basis brace, hugging its d=3 rows, sits lower than the mapping brace
    assert cells["ebkbrace:comma_basis:0"].y > mbrace.y


def test_comma_tuning_rows_get_list_brackets_hugging_their_values():
    cells = {c.id: c for c in _layout().cells}
    # comma sizes are a list of interval sizes, bracketed like the target sizes
    assert cells["bracket:tuning:commalist:l"].text == "[" and cells["bracket:tuning:commalist:r"].text == "]"
    assert cells["bracket:damage:commalist:l"].text == "["
    # the bracket pair sits just outside the comma value cells
    l, r = cells["bracket:tuning:commalist:l"], cells["bracket:tuning:commalist:r"]
    assert l.x < cells["tuning:comma:0"].x < r.x


def test_comma_columns_get_in_tile_captions_consistent_with_the_targets():
    on = {c.id: c for c in _with(names=True).cells}
    off = {c.id: c for c in _with(names=False).cells}
    # the comma basis is captioned like the mapping, and sits below its taller (d-row)
    # matrix — lower than the mapping caption hugging the r-row maps
    assert on["caption:mapping:commas"].text == "comma basis"
    assert on["caption:mapping:commas"].y > on["caption:mapping:primes"].y
    # comma captions mirror the target captions, swapping "target-interval" for "comma"
    assert on["caption:tuning:commas"].text == "tempered comma size list"
    assert on["caption:just:commas"].text == "(just) comma size list"
    assert on["caption:retune:commas"].text == "comma error list"
    assert on["caption:damage:commas"].text == "comma damage list"
    assert not any(c.startswith("caption:") and c.endswith(":commas") for c in off)


def test_commas_column_has_an_add_comma_control():
    cells = {c.id: c for c in _layout().cells}
    assert "comma_plus" in cells  # always add-able, like the domain +
    assert cells["comma_plus"].x > cells["comma:0"].x  # in the gutter right of the basis


def test_comma_minus_rides_the_last_comma_only_when_more_than_one():
    one = {c.id for c in _layout().cells}  # meantone exposes a single comma
    assert "comma_minus" not in one  # the sole comma cannot be removed
    two = service.add_comma(service.from_mapping(((1, 1, 0), (0, 1, 4))))
    cells = {c.id: c for c in spreadsheet.build(two).cells}
    assert "comma_minus" in cells  # ...but with two, the last is removable
    assert cells["comma_minus"].x == cells["comma:1"].x  # rides the last comma column
    assert cells["comma_minus"].y < cells["comma:1"].y  # revealed above its header


# --- math expressions: the just row's exact log₂ closed forms ---

def test_math_expressions_render_the_just_tuning_primes_as_logs():
    # the just tuning map over primes is exactly log2 of each prime, so with math
    # expressions on its cells show that closed form (= its octave value, since
    # quantities is also on) instead of the cents decimal
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:prime:0"].kind == "mathexpr"
    assert cells["just:prime:0"].text == "log₂2 = 1.000"  # the octave is one
    assert cells["just:prime:1"].text == "log₂3 = 1.585"  # matches the mockup legend
    assert cells["just:prime:2"].text == "log₂5 = 2.322"


def test_math_expressions_render_the_just_target_sizes_as_logs():
    # the just target-size list is log2 of each target ratio; a bare prime ratio
    # (n/1) drops its denominator, a proper ratio keeps it in parentheses
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:target:1"].text == "log₂3 = 1.585"  # 3/1 -> log₂3
    assert cells["just:target:2"].text == "log₂(3/2) = 0.585"  # 3/2 keeps the ratio


def test_math_expressions_render_the_just_comma_sizes_as_logs():
    # a comma is an interval too, so its just size is log2 of its ratio; the
    # syntonic comma 80/81 is a hair flat of unity, hence a small negative log
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    assert cells["just:comma:0"].kind == "mathexpr"
    assert cells["just:comma:0"].text == "log₂(80/81) = -0.018"


def test_math_expressions_leave_the_tempered_and_retuning_rows_as_cents():
    # only the just row has a closed form; the optimized tempered/retuning/damage
    # values stay decimal cents (the choice the legend's "all tuning rows" implies)
    cells = {c.id: c for c in _with(math_expressions=True).cells}
    for cid in ("tuning:prime:1", "retune:prime:1", "damage:target:0"):
        assert cells[cid].kind == "tval"
        assert "log" not in cells[cid].text


def test_math_expressions_without_quantities_show_only_the_expression():
    # quantities drives the "= value" tail; with it off the cell is the bare log
    cells = {c.id: c for c in _with(math_expressions=True, quantities=False).cells}
    assert cells["just:prime:1"].text == "log₂3"


def test_math_expressions_is_an_interactive_toggle():
    # it now builds content, so the panel must offer it live rather than greyed out
    assert "math_expressions" in settings.IMPLEMENTED


def test_counts_on_adds_a_top_row_of_per_column_cardinalities():
    cells = {c.id: c for c in _with(counts=True).cells}
    # the counts row reports each present column's set cardinality
    assert cells["count:gens"].text == "r = 2"  # rank: two generators
    assert cells["count:primes"].text == "d = 3"  # dimensionality: 2.3.5
    assert cells["count:commas"].text == "n = 1"  # nullity: one comma (syntonic)
    assert cells["count:targets"].text == "k = 8"  # target-interval count: the 6-TILT is 8


def test_counts_row_sits_at_the_top_aligned_over_its_columns():
    cells = {c.id: c for c in _with(counts=True).cells}
    # the counts row is the topmost data row — above the quantities (primes/targets)
    assert cells["count:primes"].y < cells["prime:0"].y
    assert cells["count:targets"].y < cells["target:0"].y
    # each count spans its column, centred over the values like the header
    for ckey in ("gens", "primes", "targets"):
        assert cells[f"count:{ckey}"].x == cells[f"header:{ckey}"].x
        assert cells[f"count:{ckey}"].w == cells[f"header:{ckey}"].w


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
    assert on["caption:counts:targets"].text == "target-interval count"
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
    assert cells["count:primes"].text == "d = 4"  # the added prime grows the dimensionality
    assert cells["count:gens"].text == "r = 3"  # ...and meantone gains an independent generator
