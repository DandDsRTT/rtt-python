from rtt.web import service, settings, spreadsheet


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


def _with(**overrides):
    s = settings.defaults()
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)


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
    # ...and a fold toggle, like every other column
    assert "toggle:col:quantities" in cells


def test_generators_column_gridline_spans_the_full_height():
    by_id = {ln.id: ln for ln in _layout().lines}
    gens, quant = by_id["trunk:gens"], by_id["trunk:quantities"]
    # the generators gridline runs the full grid height like the quantities spine,
    # rather than stopping at the mapping band partway down
    assert gens.start == quant.start
    assert gens.length == quant.length


def test_interval_vectors_row_has_a_horizontal_gridline():
    lay = _layout()
    by_id = {ln.id: ln for ln in lay.lines}
    cells = {c.id: c for c in lay.cells}
    assert "h:vectors" in by_id  # the interval-vectors row gets a gridline like the rest
    line, vrow = by_id["h:vectors"], cells["label:vectors"]
    assert vrow.y <= line.pos <= vrow.y + vrow.h  # centred on the vectors row band
    assert line.start + line.length >= cells["header:targets"].x  # across the data columns


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
    # interval-vectors monzos
    assert not any(c.startswith(("prime:", "target:", "gen:", "cell:mapping:",
                                 "cell:mapped:", "cell:vec:", "comma:", "cell:comma:",
                                 "tuning:", "just:", "retune:", "damage:"))
                   for c in ids)
    # no EBK marks (brackets, top brackets, braces, monzo rules) and no domain/comma controls
    assert not any(c.startswith(("bracket:", "ebktop:", "ebkbrace:", "sep:")) for c in ids)
    assert {"minus", "plus", "comma_minus", "comma_plus"}.isdisjoint(ids)
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


def test_a_collapsed_multiline_title_strip_fits_its_widest_line():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    interest = {c.id: c for c in spreadsheet.build(base, collapsed={"col:interest"}).cells}["header:interest"]
    # the title keeps its full (explicitly "\n"-broken) text and folds to a strip sized to
    # its widest line, so a three-word title stacks instead of forcing a ~226px one-line ribbon
    assert interest.text == "other intervals\nof interest"
    assert interest.w == len("other intervals") * 8 + 10  # the widest line, not all 27 chars
    assert interest.w < len("other intervals of interest") * 8 + 10  # far narrower than one line


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
    # the mapped target interval list separates its monzo columns with vertical
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


def test_preselects_off_shows_no_chooser_dropdowns():
    cells = {c.id for c in _with(preselects=False).cells}
    assert not any(c.startswith("preselect:") for c in cells)


def test_preselects_on_adds_the_three_chooser_dropdowns_under_their_tiles():
    cells = {c.id: c for c in _with(preselects=True).cells}
    assert {"preselect:temperament", "preselect:tuning", "preselect:target"} <= set(cells)
    # the temperament chooser sits under the mapping matrix, aligned to its column
    temp, matrix = cells["preselect:temperament"], cells["cell:mapping:0:0"]
    assert temp.y > matrix.y and temp.x == cells["header:primes"].x
    # the target chooser sits under the target interval list (quantities row)
    assert cells["preselect:target"].x == cells["header:targets"].x


def test_tuning_and_target_choosers_show_the_live_selection_temperament_is_a_placeholder():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["preselects"] = True
    cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="POTE", target_spec="OLD").cells}
    assert cells["preselect:tuning"].text == "POTE"  # reflects the active scheme
    assert cells["preselect:target"].text == "OLD"  # reflects the active set
    assert cells["preselect:temperament"].text == ""  # a chooser placeholder, not a live value


def test_preselect_choosers_follow_their_columns_when_temperament_is_hidden():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["preselects"], s["temperament_boxes"] = True, False
    cells = {c.id for c in spreadsheet.build(base, s).cells}
    # the temperament and tuning choosers both ride the domain-primes column (under
    # the mapping matrix / tuning map), which temperament_boxes owns -- so hiding the
    # temperament takes both choosers with the column
    assert "preselect:temperament" not in cells
    assert "preselect:tuning" not in cells
    # the target chooser rides the tuning-owned target intervals column, so it stays
    assert "preselect:target" in cells


def test_preselect_dropdown_clears_the_row_below_it():
    cells = {c.id: c for c in _with(preselects=True).cells}
    drop, next_row = cells["preselect:tuning"], cells["label:just"]
    assert drop.y + drop.h <= next_row.y  # the reserved band keeps it off the next row


def test_target_chooser_is_wider_to_seat_its_numeric_override():
    # the target chooser carries a numeric limit field beside the TILT/OLD select,
    # so it reserves more width than the single-control tuning chooser
    cells = {c.id: c for c in _with(preselects=True).cells}
    assert cells["preselect:target"].w > cells["preselect:tuning"].w


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
    assert pote["tuning:prime:0"] == "1200.000"


def test_plain_text_values_adds_a_string_band_under_each_tile():
    on = {c.id: c for c in _with(plain_text_values=True).cells}
    off = {c.id for c in _with(plain_text_values=False).cells}
    assert not any(c.startswith("ptext:") for c in off)  # off by default
    # each value group gets its natural plain-text form (from the service seam)
    assert on["ptext:mapping:primes"].text == "[⟨1 1 0] ⟨0 1 4]}"
    assert on["ptext:mapping:targets"].text.startswith("[[1 0}")  # generator-coord vectors (close })
    assert on["ptext:vectors:commas"].text == "[[4 -4 1⟩]"  # comma basis: monzo list, outer [ ]
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


def test_only_the_editable_duals_render_as_input_plain_text():
    cells = {c.id: c for c in _with(plain_text_values=True).cells}
    # the mapping and the comma basis — the grid's two editable duals — are inputs
    assert cells["ptext:mapping:primes"].kind == "ptextedit"
    assert cells["ptext:vectors:commas"].kind == "ptextedit"
    # every other plain-text value is read-only display text, not an editable box
    for cid in ("ptext:mapping:targets", "ptext:mapping:commas", "ptext:tuning:primes",
                "ptext:quantities:primes", "ptext:damage:targets"):
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


# --- the interval-vectors row (each column's intervals as monzos) ---

def test_interval_vectors_row_sits_between_quantities_and_mapping():
    cells = {c.id: c for c in _layout().cells}
    assert cells["label:vectors"].text == "interval vectors"
    assert "toggle:row:vectors" in cells  # collapsible like the other content rows
    assert cells["label:quantities"].y < cells["label:vectors"].y < cells["label:mapping"].y


def test_interval_vectors_show_targets_as_monzos():
    cells = {c.id: c for c in _layout().cells}
    # each target interval as a d-tall monzo column: 2/1->[1,0,0], 3/2->[-1,1,0], 5/4->[-2,0,1]
    assert [cells[f"cell:vec:targets:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
    assert [cells[f"cell:vec:targets:2:{p}"].text for p in range(3)] == ["-1", "1", "0"]
    assert [cells[f"cell:vec:targets:6:{p}"].text for p in range(3)] == ["-2", "0", "1"]
    assert cells["cell:vec:targets:2:0"].x == cells["target:2"].x  # column on its target axis
    # the d components stack downward, one ROW_H apart
    assert cells["cell:vec:targets:0:1"].y - cells["cell:vec:targets:0:0"].y == spreadsheet.ROW_H


def test_interval_vectors_domain_primes_identity_is_deferred_to_identity_objects():
    # the domain primes as monzos over themselves are the d x d identity — an
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


def test_interval_vectors_basis_has_vertical_domain_controls():
    cells = {c.id: c for c in _layout().cells}
    # the domain controls of the quantities row, oriented vertically: a + below the
    # stack to add a prime, a − on the highest (bottom) prime to remove one
    plus, minus, top, bot = cells["basis_plus"], cells["basis_minus"], cells["basis:0"], cells["basis:2"]
    assert plus.y >= bot.y + bot.h  # + sits below the whole stack, clear of the last box (no overlap)
    assert abs((plus.x + plus.w / 2) - (top.x + top.w / 2)) < 1  # centred under the basis column
    assert minus.y <= bot.y + spreadsheet.ROW_H and minus.y + minus.h > bot.y  # − rides the highest prime


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


def test_comma_basis_renders_as_raw_monzos_in_the_interval_vectors_row():
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
    # just and error sizes, but damage is a target-interval quantity only.
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


def test_comma_basis_is_framed_as_a_monzo_list_spanning_its_d_tall_height():
    cells = {c.id: c for c in _layout().cells}
    # the comma basis (in the interval-vectors row) is a list of monzos: an enclosing
    # [ ] plus per-column ket marks
    assert cells["bracket:vec:commas:l"].text == "[" and cells["bracket:vec:commas:r"].text == "]"
    assert "ebktop:vec:commas:0" in cells and "ebkangle:vec:commas:0" in cells
    cb = cells["bracket:vec:commas:l"]
    # the enclosing bracket spans the full d=3 tall basis
    assert cb.y <= cells["cell:comma:0:0"].y
    assert cb.y + cb.h >= cells["cell:comma:2:0"].y + cells["cell:comma:2:0"].h


def test_untempered_monzo_columns_get_angle_feet_while_mapped_lists_keep_braces():
    cells = {c.id: c for c in _layout().cells}
    # the interval-vectors row holds RAW (untempered) monzos — each column is a ket,
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
    # so its cell borders already divide the columns; also drawing the monzo
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
    assert spreadsheet._wrap_lines("tempered comma size list", 62) >= 3


def test_a_long_caption_grows_its_tile_rather_than_spilling():
    cells = {c.id: c for c in _with(names=True).cells}
    cap = cells["caption:tuning:commas"]  # "tempered comma size list" on a ~62px column
    # the caption gets a line per wrapped line (not one fixed line), so the name
    # stays within its column instead of overflowing it
    assert cap.h == spreadsheet._wrap_lines("tempered comma size list", cap.w) * spreadsheet.CAPTION_LINE
    assert cap.h >= 3 * spreadsheet.CAPTION_LINE  # at least three lines tall here
    # it stays as wide as its (one-comma) column and sits below the value cell
    assert cap.w == cells["header:commas"].w
    assert cap.y >= cells["tuning:comma:0"].y + spreadsheet.ROW_H


def test_comma_columns_get_in_tile_captions_consistent_with_the_targets():
    on = {c.id: c for c in _with(names=True).cells}
    off = {c.id: c for c in _with(names=False).cells}
    # the raw comma basis is captioned in the interval-vectors row; the mapping row
    # shows it mapped (vanishing), captioned to parallel the mapped target list
    assert on["caption:vectors:commas"].text == "comma basis"
    assert on["caption:mapping:commas"].text == "mapped comma list"
    # comma captions mirror the target captions, swapping "target interval" for "comma"
    # (damage is the exception — a target-only row, with no comma tile to caption)
    assert on["caption:tuning:commas"].text == "tempered comma size list"
    assert on["caption:just:commas"].text == "(just) comma size list"
    assert on["caption:retune:commas"].text == "comma error list"
    assert "caption:damage:commas" not in on
    assert not any(c.startswith("caption:") and c.endswith(":commas") for c in off)


def test_interval_vectors_tiles_are_captioned_by_what_each_column_holds():
    on = {c.id: c for c in _with(names=True).cells}
    assert on["caption:vectors:commas"].text == "comma basis"  # the raw monzos (the dual)
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
    assert cells["comma_minus"].x == cells["comma:1"].x  # rides the last comma column
    assert cells["comma_minus"].y < cells["comma:1"].y  # revealed above its header


def test_adding_a_comma_starts_a_pending_draft_column_that_does_not_re_rank():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 1 real comma, mapping r=2
    cells = {c.id: c for c in spreadsheet.build(base, pending_comma=[None, None, None]).cells}
    assert cells["comma:0"].text == "80/81"  # the real comma stays
    # a draft column rides to its right: a "?" quantity and blank, red-flagged monzo cells
    assert cells["comma:pending"].text == "?" and cells["comma:pending"].pending
    assert cells["comma:pending"].x > cells["comma:0"].x
    assert cells["cell:comma:0:1"].text == "" and cells["cell:comma:0:1"].pending
    # the mapping is untouched (the draft is not yet a real comma): still 2 rows, no 3rd
    assert "cell:mapping:1:0" in cells and "cell:mapping:2:0" not in cells
    # the draft has no size cells (undefined until valid)
    assert "tuning:comma:1" not in cells
    # the − rides the draft column (to cancel it)
    assert cells["comma_minus"].x == cells["comma:pending"].x


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


def test_counts_on_adds_a_top_row_of_per_column_cardinalities():
    cells = {c.id: c for c in _with(counts=True).cells}
    # the counts row reports each present column's set cardinality, with the
    # variable as a mathematical-italic letter (matching the Show panel's example)
    assert cells["count:gens"].text == "\U0001D45F = 2"  # 𝑟 rank: two generators
    assert cells["count:primes"].text == "\U0001D451 = 3"  # 𝑑 dimensionality: 2.3.5
    assert cells["count:commas"].text == "\U0001D45B = 1"  # 𝑛 nullity: one comma (syntonic)
    assert cells["count:targets"].text == "\U0001D458 = 8"  # 𝑘 target interval count: the 6-TILT is 8


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


def test_empty_interest_column_takes_its_titles_wrapped_strip_width():
    # an empty interest column has no cells to set its width, so it adopts its title's
    # strip width — the widest line of its two-line header (the narrow header strip the
    # mockup shows) rather than a bare bracket-gutter stub the long title would overflow
    cells = {c.id: c for c in _layout().cells}  # default build => interest empty
    assert cells["header:interest"].w == len("other intervals") * 8 + 10


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


# the user enters intervals of interest as monzos (like the comma basis); these are
# 3/2, 9/8, 10/9, 8/5 over the 2.3.5 domain, used across the populated-interest tests
_INTEREST = ((-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1))


def test_populated_interest_renders_ratios_mapped_and_sizes_minus_damage():
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    # quantities row: the ratio derived from each entered monzo
    assert cells["interest:0"].text == "3/2" and cells["interest:3"].text == "8/5"
    # mapping row: each interval mapped to generator coords (M . i), like the targets
    assert cells["cell:imapped:0:0"].text == "0" and cells["cell:imapped:1:0"].text == "1"  # 3/2 -> [0,1]
    assert cells["cell:imapped:1:3"].text == "-4"  # 8/5 -> [3,-4]
    # tempered / just / retuning size rows
    assert {"tuning:interest:0", "just:interest:0", "retune:interest:3"} <= set(cells)
    assert cells["just:interest:0"].text == "701.955"  # 3/2 just is a pure fifth
    # ...but NO damage row: these are not optimization targets
    assert not any(c.startswith("damage:interest") for c in cells)


def test_interest_intervals_are_editable_monzo_vectors_like_the_comma_basis():
    # in the interval-vectors row each interval is an editable d-tall monzo column
    # (kind "interestcell", the comma-basis editing affordance), prime exponents down
    cells = {c.id: c for c in _with_interest(_INTEREST).cells}
    assert cells["cell:interest:0:0"].text == "-1"  # 3/2 = [-1 1 0>: prime-2 exponent
    assert cells["cell:interest:1:0"].text == "1" and cells["cell:interest:2:0"].text == "0"
    assert cells["cell:interest:2:2"].text == "1"  # 10/9 = [1 -2 1>: prime-5 exponent
    assert cells["cell:interest:0:0"].kind == "interestcell"  # editable, not a static "vec"
    # marked as a ket list in the vectors row, like the comma basis and targets
    assert cells["bracket:vec:interest:l"].text == "[" and "ebktop:vec:interest:0" in cells
    assert "sep:vec:interest:1" in cells  # a rule between the monzo columns


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


def test_adding_intervals_of_interest_neither_shrinks_the_header_nor_reflows_the_board():
    # regression: the long title floats the interest HEADER out to its two-line strip
    # width; the few-interval value cells must not shrink that header (which would
    # rewrap the title onto a third line), and — because the captions wrap within that
    # header width, not the content — the board height must not change as intervals are
    # added (an interest set is curated display data, not a layout dimension)
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    builds = [spreadsheet.build(base, collapsed=frozenset(), interest=[(0, 0, 0)] * n) for n in range(5)]
    widths = [{c.id: c for c in lay.cells}["header:interest"].w for lay in builds]
    heights = [lay.height for lay in builds]
    assert widths == sorted(widths)  # monotonic: adding an interval never narrows the header
    assert min(widths) == widths[0]  # ...and never dips below the empty (title-strip) width
    assert len(set(heights)) == 1  # the board height is unaffected by the interval count


def test_interest_tiles_hug_their_content_not_the_title_strip():
    # the grey tiles and value cells hug the few narrow intervals — no empty padding out
    # to the wide title. Only the header (and the captions under it) float to the title
    # width and overhang to the right, since interest is the rightmost column.
    lay = _with_interest(_INTEREST[:1])  # a single interval
    cells = {c.id: c for c in lay.cells}
    blocks = {b.id: b for b in lay.blocks}
    content_w = 2 * spreadsheet.BRACKET_W + 1 * spreadsheet.COL_W  # the two gutters + one cell
    assert blocks["block:interest"].w == content_w + 2 * spreadsheet.PAD  # tile hugs content...
    assert cells["header:interest"].w > blocks["block:interest"].w  # ...while the header floats wider
    assert cells["header:interest"].w == len("other intervals") * 8 + 10  # to its title-strip width


def test_populated_interest_mapped_list_is_bracketed_and_ruled_like_targets():
    cells = {c.id: c for c in _with_interest(_INTEREST[:2]).cells}
    assert cells["bracket:imapped:l"].text == "[" and cells["bracket:imapped:r"].text == "]"
    assert {"ebktop:imapped:0", "ebkbrace:imapped:0", "ebktop:imapped:1"} <= set(cells)
    assert "sep:imapped:1" in cells  # a rule between the two monzo columns
    # the tempered/just/retuning rows get plain list brackets too
    assert cells["bracket:tuning:ilist:l"].text == "[" and cells["bracket:retune:ilist:r"].text == "]"


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


def test_interest_captions_mirror_targets_without_damage_when_named():
    cells = {c.id: c for c in _with_interest(_INTEREST[:1]).cells}  # names default on
    assert cells["caption:vectors:interest"].text == "interval of interest list"
    assert cells["caption:mapping:interest"].text == "mapped interval list"
    assert cells["caption:tuning:interest"].text == "tempered interval size list"
    assert "caption:damage:interest" not in cells


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


def test_symbols_toggles_in_tile_symbol_glyphs_above_the_names():
    on = {c.id: c for c in _with(symbols=True, names=True).cells}
    off = {c.id: c for c in _with(symbols=False).cells}
    # styling per the convention: the mapping 𝑀 is math-italic; the interval
    # lists/bases (Y, comma basis C, target list T) are upright non-bold; the maps
    # are bold-italic; the size-lists bold-upright
    assert on["symbol:mapping:primes"].text == "𝑀"  # mapping matrix (italic)
    assert on["symbol:mapping:targets"].text == "Y"  # mapped target list (upright)
    assert on["symbol:vectors:targets"].text == "T"  # target-interval list (upright)
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
    assert on["symbol:mapping:commas"].text == "𝑀C"   # mapped comma list
    assert on["symbol:tuning:commas"].text == "𝒕C"    # tempered comma sizes
    assert on["symbol:just:commas"].text == "𝒋C"      # just comma sizes
    assert on["symbol:retune:commas"].text == "𝒓C"    # comma errors
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
    # a toggle is "implemented" (live, not greyed, in the Show panel) iff it has
    # built content — flipping any IMPLEMENTED key from its default must visibly
    # change the grid (cells added/removed/moved or their text/kind changed)
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

    default_snap = snapshot(settings.defaults())
    for key in settings.IMPLEMENTED:
        s = settings.defaults()
        s[key] = not s[key]
        assert snapshot(s) != default_snap, f"{key} is marked implemented but changes nothing"


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


def test_optimization_on_shows_the_power_below_the_damage_row():
    on = {c.id: c for c in _with(optimization=True).cells}
    # the optimization power p of the current tuning (TOP, a minimax scheme => ∞),
    # rendered like a count: the math-italic symbol, " = ", and its value
    assert on["optimization:power"].text == "\U0001D45D = ∞"  # 𝑝 = ∞
    # it rides the target-intervals column (the tuning's own column) ...
    assert on["optimization:power"].x == on["header:targets"].x
    assert on["optimization:power"].w == on["header:targets"].w
    # ... in a new row at the bottom of the tuning boxes, below the damage row
    assert on["optimization:power"].y > on["damage:target:0"].y
    assert "label:optimization" in on


def test_optimization_power_reflects_the_current_tuning_scheme():
    # the surfaced power is the *current* tuning's, not a constant: a least-squares
    # (miniRMS) scheme reads p = 2 where the default minimax TOP reads p = ∞
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    ls = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="least squares").cells}
    assert ls["optimization:power"].text == "\U0001D45D = 2"  # 𝑝 = 2


def test_optimization_needs_its_parent_tuning_boxes():
    # optimization is a sub-control of tuning boxes: with the tuning region hidden
    # there is nothing to annotate, so the power row stays away even when toggled on
    cells = {c.id for c in _with(optimization=True, tuning_boxes=False).cells}
    assert "optimization:power" not in cells
    assert "label:optimization" not in cells


def test_optimization_power_sits_on_a_grey_panel():
    # like every value tile, the power rides a grey panel (never a bare floating number)
    lay = _with(optimization=True)
    panel = {b.id: b for b in lay.blocks}.get("block:optimization")
    assert panel is not None
    assert panel.w > 0 and panel.h > 0


def test_optimization_row_collapses_keeping_its_label_and_gridline():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    full = {c.id for c in spreadsheet.build(base, s).cells}
    assert "toggle:row:optimization" in full  # collapsible: it has a fold toggle
    lay = spreadsheet.build(base, s, collapsed={"row:optimization"})
    cells = {c.id for c in lay.cells}
    assert "optimization:power" not in cells  # the value folds away
    assert "label:optimization" in cells  # ...the label survives as a strip
    assert {ln.id for ln in lay.lines} >= {"h:optimization"}  # ...leaving a gridline


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


def test_generator_tuning_map_tile_shows_the_generator_map_cents_in_the_default_view():
    # the generator tuning map (the tuning row over the generators) is a default-view
    # tile, like the tuning map over the primes — present without any toggle
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    tun = service.tuning(st.mapping)
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
    assert on["ptext:tuning:gens"].text == service.plain_text_values(st)[("tuning", "gens")]
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
    assert sel.text == "monotone"  # the live mode (default), so the renderer can preselect it
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


def test_tuning_colorization_washes_every_tuning_row():
    # a full-width colour band backs each tuning/just/retuning/damage row (the mockup's
    # cyan box group): one wash + white base per row, spanning the whole row background
    ids = {b.id for b in _with(tuning_colorization=True).blocks}
    assert {"wash:tuning", "wash:just", "wash:retune", "wash:damage"} <= ids
    assert {"washbase:tuning", "washbase:just", "washbase:retune", "washbase:damage"} <= ids


def test_a_wash_is_a_full_width_band_over_a_white_base_below_the_grey_tiles():
    blocks = {b.id: b for b in _with(tuning_colorization=True).blocks}
    wash, base = blocks["wash:tuning"], blocks["washbase:tuning"]
    assert wash.tint == "tuning"  # the colour layer (renderer → CSS colour, drawn darken)
    assert base.tint == "base"  # the white base it darkens over, so groups combine to green
    assert (base.x, base.y, base.w, base.h) == (wash.x, wash.y, wash.w, wash.h)  # coincident
    assert blocks["block:tuning:targets"].tint == ""  # grey tiles aren't tinted — they float on the band
    # the band runs the full column width (over the primes tile AND the targets tile,
    # not just one column) and overhangs the row vertically
    left, right = blocks["block:tuning:primes"], blocks["block:tuning:targets"]
    assert wash.x < left.x and wash.x + wash.w > right.x + right.w
    assert wash.y < left.y and wash.y + wash.h > left.y + left.h


def test_colorization_off_means_no_wash_and_only_tuning_rows_wash_when_on():
    assert not any(b.id.startswith(("wash:", "washbase:")) for b in _layout().blocks)  # off by default
    # with it on, only the tuning quantity rows wash; the temperament/vector/quantity
    # rows stay plain (their own colorization is a separate, still-stubbed toggle)
    rows = {b.id.split(":")[1] for b in _with(tuning_colorization=True).blocks
            if b.id.startswith("wash:")}
    assert rows == {"tuning", "just", "retune", "damage"}


def test_a_folded_tuning_row_shrinks_its_wash_to_the_collapsed_strip():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["tuning_colorization"] = True
    open_h = {b.id: b for b in spreadsheet.build(base, s).blocks}["wash:tuning"].h
    folded = {b.id: b for b in spreadsheet.build(base, s, collapsed={"row:tuning"}).blocks}
    # the band tracks its row: collapsing the row shrinks the band to the strip (and its
    # white base with it), so no full-height cyan strip is left behind
    assert folded["wash:tuning"].h < open_h
    assert folded["washbase:tuning"].h == folded["wash:tuning"].h


def test_mapped_comma_basis_vanishes_and_the_damage_weight_is_bold_italic():
    on = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
    # the mapped comma basis is exactly the zero matrix
    assert on["symbol:mapping:commas"].text == "𝑀C = 𝑂"
    # the damage weight w is bold-italic (matching the maps), not bold-upright
    assert on["symbol:damage:targets"].text == "𝐝 = |𝐞|diag(𝒘)"


def test_temperament_colorization_washes_the_temperament_columns():
    # temperament is a COLUMN group (the mockup washes the domain primes / generators /
    # commas columns yellow, full height): one full-height wash + white base per column
    ids = {b.id for b in _with(temperament_colorization=True).blocks}
    assert {"wash:col:gens", "wash:col:primes", "wash:col:commas"} <= ids
    assert {"washbase:col:gens", "washbase:col:primes", "washbase:col:commas"} <= ids


def test_a_temperament_column_wash_is_a_full_height_band_over_a_white_base():
    lay = _with(temperament_colorization=True)
    blocks = {b.id: b for b in lay.blocks}
    cells = {c.id: c for c in lay.cells}
    wash, base = blocks["wash:col:primes"], blocks["washbase:col:primes"]
    assert wash.tint == "temperament"  # the colour layer (renderer → khaki, drawn darken)
    assert base.tint == "base"  # the white base it darkens over
    assert (base.x, base.y, base.w, base.h) == (wash.x, wash.y, wash.w, wash.h)  # coincident
    # the band runs the full row height (above the topmost tile, below the bottommost)
    tiles = [b for b in lay.blocks if b.id.startswith("block:")]
    assert wash.y <= min(t.y for t in tiles) and wash.y + wash.h >= max(t.y + t.h for t in tiles)
    # but only the primes column's width — it brackets the primes header, and is
    # narrower than the whole grid (a column band, not a full-width row band)
    hp = cells["header:primes"]
    assert wash.x <= hp.x and wash.x + wash.w >= hp.x + hp.w
    assert wash.w < max(t.x + t.w for t in tiles) - min(t.x for t in tiles)


def test_tuning_rows_and_temperament_columns_cross_to_blend_green():
    # both on: a cyan tuning ROW band and a yellow temperament COLUMN band overlap at the
    # tuning-map-over-primes cell, where the renderer's darken blends them to the mockup's
    # green. Assert the two bands' rectangles actually intersect (the colour is a CSS blend).
    blocks = {b.id: b for b in _with(tuning_colorization=True, temperament_colorization=True).blocks}
    row, col = blocks["wash:tuning"], blocks["wash:col:primes"]
    assert row.x < col.x + col.w and col.x < row.x + row.w  # x ranges overlap
    assert row.y < col.y + col.h and col.y < row.y + row.h  # y ranges overlap


def test_temperament_colorization_off_by_default_and_scoped_to_its_columns():
    assert not any(b.id.startswith(("wash:col:", "washbase:col:")) for b in _layout().blocks)
    cols = {b.id.split(":")[2] for b in _with(temperament_colorization=True).blocks
            if b.id.startswith("wash:col:")}
    assert cols == {"gens", "primes", "commas"}
