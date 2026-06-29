from functools import partial

import pytest

from rtt.app import (
    grid_tables,
    service,
    settings,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_geometry_query as query,
    spreadsheet_models,
    spreadsheet_text,
)
from rtt.app.editor import Editor
from rtt.app.layout import CellBox, Layout
from rtt.app.spreadsheet_decorations import _tile_groups
from rtt.app.spreadsheet_geometry import plain_text_band
from _spreadsheet_support import _memoized_build, _layout, _with, _all_on, _tokens, _held_state, _reorder_volatile, _in_targets


class TestFreshColumn:
    def test_fresh_column_tokens_number_the_columns_by_index(self):
        pairs = spreadsheet_text.assign_column_tokens(None, [(-1, 1, 0), (2, 0, -1), (1, 1, -1)])
        assert _tokens(pairs) == [0, 1, 2]

    def test_reordered_column_keeps_its_token(self):
        a, b, c = (-1, 1, 0), (2, 0, -1), (1, 1, -1)
        prev = spreadsheet_text.assign_column_tokens(None, [a, b, c])
        moved = spreadsheet_text.assign_column_tokens(prev, [c, a, b])
        assert _tokens(moved) == [2, 0, 1]

    def test_edited_column_keeps_its_token_by_position(self):
        a, b = (-1, 1, 0), (2, 0, -1)
        prev = spreadsheet_text.assign_column_tokens(None, [a, b])
        edited = spreadsheet_text.assign_column_tokens(prev, [(-1, 2, 0), b])
        assert _tokens(edited) == [0, 1]

    def test_editing_a_column_to_a_value_already_in_the_list_keeps_its_position_token(self):
        a, b, c = (-1, 1, 0), (2, 0, -1), (1, 1, -1)
        prev = spreadsheet_text.assign_column_tokens(None, [a, b, c])
        edited = spreadsheet_text.assign_column_tokens(prev, [c, b, c])
        assert _tokens(edited) == [0, 1, 2]

    def test_duplicate_columns_get_distinct_tokens(self):
        a, b = (-1, 1, 0), (2, 0, -1)
        prev = spreadsheet_text.assign_column_tokens(None, [a, a, b])
        moved = spreadsheet_text.assign_column_tokens(prev, [a, b, a])
        assert _tokens(moved) == [0, 2, 1]
        assert len(set(_tokens(moved))) == 3

    def test_pending_token_never_collides_with_a_live_column(self):
        assert spreadsheet_text.pending_token([]) == 0, "the draft column's token is one past every committed column's, so it can't clash with a # surviving column even after a removal leaves a gap in the token sequence; an empty list's # draft is 0 (so a first pending vector cell is …:0, as the index-keyed tests expect)"
        assert spreadsheet_text.pending_token([0, 1, 2]) == 3
        assert spreadsheet_text.pending_token([2]) == 3

    def test_mid_list_removal_keeps_every_survivors_token(self):
        a, b, c = "81/80", "128/125", "64/63"
        prev = spreadsheet_text.assign_column_tokens(None, [a, b, c])
        removed = spreadsheet_text.assign_column_tokens(prev, [b, c])
        assert _tokens(removed) == [1, 2]

    def test_basis_groups_claim_freed_slots_positionally_on_a_resolve(self):
        r0, r1 = (1, 1, 0), (0, 1, 4)
        prev = spreadsheet_text.assign_column_tokens(None, [r0, r1])
        dropped = spreadsheet_text.assign_column_tokens(prev, [(12, 19, 28)], claim_unmatched=True)
        assert _tokens(dropped) == [0]
        removed = spreadsheet_text.assign_column_tokens(prev, [r1], claim_unmatched=True)
        assert _tokens(removed) == [1]

    def test_interval_sets_never_relabel_a_dropped_column_as_a_new_one(self):
        prev = spreadsheet_text.assign_column_tokens(None, ["3/2", "6/5", "5/4"])
        switched = spreadsheet_text.assign_column_tokens(prev, ["3/2", "7/4"])
        assert _tokens(switched) == [0, 3], "7/4 is FRESH (3), not relabelled 1 or 2"

    def test_build_returns_column_identities_numbered_by_index_when_fresh(self):
        held = [(-1, 1, 0), (2, 0, -1)]
        lay = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
        assert _tokens(lay.identities["held"]) == [0, 1]

    def test_reordered_held_column_keeps_its_vector_cell_id_and_glides(self):
        held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
        lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
        c1 = {c.id: c for c in lay1.cells}
        slot0_x, slot2_x = c1["cell:held:0:0"].x, c1["cell:held:0:2"].x
        assert slot0_x != slot2_x
        lay2 = spreadsheet.build(_held_state(), _all_on(),
                                 held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities)
        c2 = {c.id: c for c in lay2.cells}
        assert "cell:held:0:2" in c2
        assert c2["cell:held:0:2"].x == slot0_x
        assert c2["cell:held:0:2"].text == c1["cell:held:0:2"].text, "carrying its own content, not slot 0's"

    def test_reordering_held_rekeys_every_column_cell_not_just_the_vectors(self):
        held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
        lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
        lay2 = spreadsheet.build(_held_state(), _all_on(),
                                 held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities)
        moved = {cid for cid in spreadsheet_text.changed_cell_ids(lay1, lay2) if not _reorder_volatile(cid)}
        assert moved == set(), f"these cells re-filled in place instead of gliding: {sorted(moved)}"

    def test_reorder_keeps_controls_position_bound_while_values_glide(self):
        held = [(-1, 1, 0), (2, 0, -1), (1, 1, -1)]
        lay1 = spreadsheet.build(_held_state(), _all_on(), held_vectors=held)
        c1 = {c.id: c for c in lay1.cells}
        slot_x = [c1[f"grip:held:{i}"].x for i in range(3)]
        c2 = {c.id: c for c in spreadsheet.build(
            _held_state(), _all_on(), held_vectors=[held[2], held[0], held[1]], prev_ids=lay1.identities).cells}
        assert [c2[f"grip:held:{i}"].x for i in range(3)] == slot_x
        assert all(f"held_minus:{i}" in c2 for i in range(3))
        assert c2["cell:held:0:2"].x == slot_x[0]

    def test_reordering_interest_rekeys_its_column_cells(self):
        interest = [(1, 1, -1), (-1, 1, 0), (2, 0, -1)]
        lay1 = spreadsheet.build(_held_state(), _all_on(), interest=interest)
        lay2 = spreadsheet.build(_held_state(), _all_on(),
                                 interest=[interest[2], interest[0], interest[1]], prev_ids=lay1.identities)
        moved = {cid for cid in spreadsheet_text.changed_cell_ids(lay1, lay2) if not _reorder_volatile(cid)}
        assert moved == set(), f"interest cells re-filled in place instead of gliding: {sorted(moved)}"

    def test_reordering_targets_rekeys_its_column_cells(self):
        targets = ("2/1", "3/2", "5/4")
        lay1 = spreadsheet.build(_held_state(), _all_on(), target_override=targets)
        lay2 = spreadsheet.build(_held_state(), _all_on(),
                                 target_override=(targets[2], targets[0], targets[1]), prev_ids=lay1.identities)
        moved = {cid for cid in spreadsheet_text.changed_cell_ids(lay1, lay2)
                 if not _reorder_volatile(cid) and not cid.startswith("damage:")}
        assert moved == set(), f"target cells re-filled in place instead of gliding: {sorted(moved)}"

    def test_removing_a_column_keeps_the_survivors_identity_so_they_do_not_ring(self):
        interest = [(1, 1, -1), (-1, 1, 0), (2, 0, -1)]
        lay1 = spreadsheet.build(_held_state(), _all_on(), interest=interest)
        lay2 = spreadsheet.build(_held_state(), _all_on(), interest=interest[1:], prev_ids=lay1.identities)
        assert spreadsheet_text.changed_cell_ids(lay1, lay2) == frozenset()

    def test_editable_vector_tiles_get_editable_quantities_ratios(self):
        ed = Editor()
        ed.set_interest_vectors([(1, 1, -1)])
        ed.set_held_vectors([(-1, 1, 0)])
        s = settings.defaults()
        for key in settings.IMPLEMENTED:
            s[key] = True
        cells = {c.id: c for c in spreadsheet.build(
            ed.state, s, interest=ed.interest_vectors, held_vectors=ed.held_vectors).cells}
        assert cells["comma:0"].kind == "ratiocell"
        assert cells["target:0"].kind == "ratiocell"
        assert cells["held:0"].kind == "ratiocell"
        assert cells["interest:0"].kind == "ratiocell"
        assert cells["detempering:0"].kind == "commaratio"
        assert cells["prime:0"].kind == "elementcell"
        off = settings.defaults()
        off_cells = {c.id: c for c in spreadsheet.build(ed.state, off).cells}
        assert off_cells["prime:0"].kind == "prime"

    def test_target_intervals_column_with_mapped_list(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["header:targets"].text == "target\nintervals"
        assert cells["target:0"].text == "2/1"
        assert cells["cell:mapped:0:0"].text == "1" and cells["cell:mapped:1:0"].text == "0"
        assert cells["target:6"].text == "5/4"
        assert cells["cell:mapped:1:6"].text == "4"

    def test_target_columns_default_to_the_domains_tilt(self):
        cells = {c.id: c for c in _layout().cells}
        texts = [cells[f"target:{j}"].text for j in range(8)]
        assert texts == ["2/1", "3/1", "3/2", "4/3", "5/2", "5/3", "5/4", "6/5"]

    def test_target_set_tracks_the_domain(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        def targets(state):
            return {c.text for c in spreadsheet.build(state).cells if c.id.startswith("target:")}

        three = targets(service.shrink_domain(base))
        five = targets(base)
        seven = targets(service.expand_domain(base))
        assert three < five < seven

    def test_mapping_cells_form_a_square_touching_grid(self):
        cells = {c.id: c for c in _layout().cells}
        c00 = cells["cell:mapping:0:0"]
        assert c00.w == c00.h == spreadsheet_constants.ROW_H, "each cell is square, so the matrix reads as a grid of squares (mockup z_map2)"
        assert cells["cell:mapping:0:1"].x == c00.x + c00.w
        assert cells["cell:mapping:0:2"].x == c00.x + 2 * c00.w
        assert cells["cell:mapping:1:0"].y == c00.y + c00.h
        m00 = cells["cell:mapped:0:0"]
        assert m00.w == m00.h == spreadsheet_constants.ROW_H
        assert cells["cell:mapped:0:1"].x == m00.x + m00.w + spreadsheet_constants.INTERVAL_COL_GAP

    def test_tuning_rows_over_primes_and_targets(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["label:tuning"].text == "tuning"
        assert cells["label:just"].text == "just tuning"
        assert cells["label:damage"].text == "damage"
        assert {"tuning:prime:0", "tuning:target:0", "just:prime:0", "retune:target:0", "damage:target:0"} <= set(cells)
        assert cells["just:prime:0"].text == "1200.000"
        assert cells["tuning:prime:2"].x == cells["cell:mapping:0:2"].x

    def test_shared_axes_and_branching(self):
        lay = _layout()
        ids = {ln.id for ln in lay.lines}
        assert {"v:prime:0", "v:prime:1", "v:prime:2"} <= ids
        assert {"v:target:0", "v:target:1", "v:target:2", "v:target:3"} <= ids
        assert {"h:mapping:0", "h:mapping:1", "h:tuning", "h:just", "h:retune", "h:damage"} <= ids
        assert {"trunk:primes", "trunk:targets", "trunk:gens"} <= ids
        assert {"bus:primes:top", "bus:primes:bot", "foot:primes"} <= ids
        by_id = {ln.id: ln for ln in lay.lines}
        cells = {c.id: c for c in lay.cells}
        assert by_id["bus:primes:top"].pos < cells["prime:0"].y
        assert by_id["v:prime:0"].start == by_id["bus:primes:top"].pos
        assert by_id["bus:primes:bot"].pos > by_id["bus:primes:top"].pos
        assert {"vbar:mapping:left", "vbar:mapping:right", "foot:mapping"} <= ids

    def test_convergence_buses_keep_solid_corners_and_the_top_bus_reaches_the_plus(self):
        lay = _layout()
        by = {ln.id: ln for ln in lay.lines}
        cells = {c.id: c for c in lay.cells}
        half = spreadsheet_constants.LINE_W / 2
        v0, vlast = by["v:prime:0"], by["v:prime:2"]
        assert by["bus:primes:top"].start == v0.pos - half
        assert by["bus:primes:bot"].start == v0.pos - half
        assert by["bus:primes:bot"].start + by["bus:primes:bot"].length == vlast.pos + half
        top, plus = by["bus:primes:top"], cells["plus"]
        assert top.start + top.length == plus.x + plus.w / 2
        assert top.start + top.length > vlast.pos + half

    def test_mapping_rejoin_bars_span_the_full_generator_fan(self):
        by = {ln.id: ln for ln in _layout().lines}
        half = spreadsheet_constants.LINE_W / 2
        g0, glast = by["h:mapping:0"], by["h:mapping:1"]
        right = by["vbar:mapping:right"]
        assert right.start == g0.pos - half and right.start + right.length == glast.pos + half
        left = by["vbar:mapping:left"]
        assert left.start == g0.pos - half
        assert left.start + left.length > glast.pos + half

    def test_adjacent_tiles_keep_a_roomy_minimum_gap(self):
        blocks = {b.id: b for b in _layout().blocks}
        top, bot = blocks["block:tuning:targets"], blocks["block:just:targets"]
        assert (top.x, top.w) == (bot.x, bot.w)
        assert bot.y - (top.y + top.h) == spreadsheet_constants.GAP - 2 * spreadsheet_constants.PAD

    def test_quantities_spine_row_has_a_horizontal_gridline(self):
        lay = _layout()
        by_id = {ln.id: ln for ln in lay.lines}
        cells = {c.id: c for c in lay.cells}
        assert "h:quantities" in by_id
        line, prime = by_id["h:quantities"], cells["prime:0"]
        assert abs(line.pos - (prime.y + prime.h / 2)) < 0.51
        assert line.start < prime.x
        assert line.start + line.length >= cells["target:3"].x

    def test_axis_ids_are_stable_across_expand(self):
        before = {ln.id for ln in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4)))).lines}
        expanded = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        after = {ln.id for ln in spreadsheet.build(expanded).lines}
        assert before <= after
        assert "v:prime:3" in after and "v:prime:3" not in before


class TestIntervalVectors:
    def test_quantities_spine_column_is_present_with_a_vertical_gridline(self):
        lay = _layout()
        cells = {c.id: c for c in lay.cells}
        by_id = {ln.id: ln for ln in lay.lines}
        assert cells["header:quantities"].text == "interval ratios"
        assert cells["header:quantities"].x < cells["header:gens"].x
        assert "trunk:quantities" in by_id
        spine, header = by_id["trunk:quantities"], cells["header:quantities"]
        assert abs(spine.pos - (header.x + header.w / 2)) < 0.51
        assert spine.start < cells["prime:0"].y
        assert spine.start + spine.length >= cells["label:damage"].y
        assert "toggle:col:quantities" in cells

    def test_a_spine_hugs_col_w_and_overhangs_its_title_unless_it_is_leftmost(self):
        cells = {c.id: c for c in _with(domain_units=True).cells}
        assert cells["header:units"].w == spreadsheet_constants.COL_W
        assert cells["header:units"].w < spreadsheet_text._title_w("units")
        assert cells["header:quantities"].w > cells["header:units"].w

    def test_generators_column_fans_into_per_generator_axes(self):
        lay = _layout()
        by_id = {ln.id: ln for ln in lay.lines}
        cells = {c.id: c for c in lay.cells}
        ids = set(by_id)
        assert {"v:gen:0", "v:gen:1"} <= ids
        assert {"trunk:gens", "bus:gens:top", "bus:gens:bot", "foot:gens"} <= ids
        for i in (0, 1):
            cell = cells[f"tuning:gen:{i}"]
            assert abs(by_id[f"v:gen:{i}"].pos - (cell.x + cell.w / 2)) < 0.51
        assert by_id["trunk:gens"].length < by_id["trunk:quantities"].length, "the trunk is now just the short fan stem above the data, not a full-height spine"

    def test_interval_vectors_row_fans_into_per_component_axes(self):
        lay = _layout()
        by_id = {ln.id: ln for ln in lay.lines}
        cells = {c.id: c for c in lay.cells}
        ids = set(by_id)
        assert {"h:vectors:0", "h:vectors:1", "h:vectors:2"} <= ids
        assert {"trunk:vectors", "foot:vectors", "vbar:vectors:left", "vbar:vectors:right"} <= ids
        assert "h:vectors" not in ids
        vrow = cells["label:vectors"]
        rules = [by_id[f"h:vectors:{i}"].pos for i in range(3)]
        assert rules == sorted(rules)
        for pos in rules:
            assert vrow.y <= pos <= vrow.y + vrow.h
        assert by_id["h:vectors:0"].start + by_id["h:vectors:0"].length >= cells["header:targets"].x

    def test_tuning_tiles_off_removes_the_tuning_rows_and_the_target_intervals_column(self):
        off = {c.id for c in _with(tuning_tiles=False).cells}
        assert not any(c.split(":")[0] in {"tuning", "just", "retune", "damage"} for c in off)
        assert {"label:tuning", "label:just", "label:retune", "label:damage"}.isdisjoint(off)
        assert "header:targets" not in off
        assert not any(c.startswith(("target:", "cell:mapped:")) for c in off)
        assert "cell:mapping:0:0" in off

    def test_gridded_values_off_empties_the_tiles_but_keeps_the_structure(self):
        lay = _with(gridded_values=False)
        ids = {c.id for c in lay.cells}
        assert not any(c.startswith(("prime:", "target:", "gen:", "cell:mapping:",
                                     "cell:mapped:", "cell:vector:", "comma:", "cell:comma:",
                                     "tuning:", "just:", "retune:", "damage:"))
                       for c in ids)
        assert not any(c.startswith(("bracket:", "ebktop:", "ebkbrace:", "sep:")) for c in ids)
        assert {"minus", "plus", "comma_minus:0", "comma_plus", "gen_minus", "gen_plus",
                "map_minus:0", "map_plus", "target_minus:0", "target_plus"}.isdisjoint(ids)
        assert {"label:mapping", "header:primes", "header:targets", "toggle:row:mapping",
                "caption:mapping:primes"} <= ids
        assert any(b.id == "block:mapping" for b in lay.blocks)
        assert any(ln.id == "v:prime:0" for ln in lay.lines)

    def test_general_quantities_off_blanks_the_body_numbers_keeping_boxes_and_brackets(self):
        on = {c.id: c for c in _with().cells}
        off = {c.id: c for c in _with(quantities=False).cells}
        body = ("cell:mapping:0:0", "cell:mapped:0:0", "cell:comma:0:0", "tuning:prime:0", "gen:0")
        for cid in body:
            assert cid in off and not on[cid].blank
            assert off[cid].blank and off[cid].text == ""
        assert on["cell:mapped:0:0"].text and on["gen:0"].text and on["tuning:prime:0"].text
        assert any(c.startswith("bracket:") for c in off)
        assert "ebktop:primes" in off and "ebkbrace:primes" in off
        assert {"plus", "minus", "comma_plus", "label:mapping", "header:primes", "toggle:row:mapping"} <= set(off), "the domain/comma ± controls and the tile structure carry no value, so they're untouched"
        for cid in ("prime:0", "comma:0", "target:0"):
            assert cid in off and not on[cid].blank and off[cid].blank and off[cid].text == ""

    def test_general_quantities_off_blanks_the_quantities_row_col_and_unrotated_vectors(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        full = settings.defaults() | {k: True for k in settings.IMPLEMENTED}
        on = {c.id: c for c in spreadsheet.build(state, {**full, "quantities": True}).cells}
        off = {c.id: c for c in spreadsheet.build(state, {**full, "quantities": False}).cells}
        regions = (
            "prime:0", "prime:2",
            "comma:0", "target:0",
            "basis:0", "basis:2",
            "qgen:0",
            "superspace_quantity_prime:0", "superspace_quantity_generator:0",
        )
        for cid in regions:
            assert cid in on and on[cid].text and not on[cid].blank
            assert off[cid].blank and off[cid].text == ""
        assert "basis:0" in off and any(c.startswith("bracket:") for c in off), "the structure stays (this is quantities-off, not gridded-off): the spine cell's box survives"

    def test_gridded_values_off_also_empties_the_math_expression_cells(self):
        on = {c.id for c in _with(math_expressions=True).cells}
        off = {c.id for c in _with(math_expressions=True, gridded_values=False).cells}
        assert any(c.startswith("just:") for c in on)
        assert not any(c.startswith("just:") for c in off)

    def test_interval_ratios_off_removes_the_interval_ratios_row_and_column(self):
        on, off = _with(), _with(interval_ratios=False)
        on_ids, off_ids = {c.id for c in on.cells}, {c.id for c in off.cells}
        assert {"label:quantities", "prime:0", "header:quantities"} <= on_ids
        assert "label:quantities" not in off_ids
        assert not any(c.startswith(("prime:", "target:")) for c in off_ids)
        assert {"minus", "plus"}.isdisjoint(off_ids)
        assert "h:quantities" not in {ln.id for ln in off.lines}
        assert "header:quantities" not in off_ids
        assert "trunk:quantities" not in {ln.id for ln in off.lines}
        assert {"cell:mapping:0:0", "tuning:target:0"} <= off_ids

    def test_temperament_tiles_off_removes_the_mapping_row_and_domain_columns(self):
        off = {c.id: c for c in _with(temperament_tiles=False).cells}
        on = {c.id: c for c in _with().cells}
        assert "label:mapping" not in off
        assert not any(c.startswith(("cell:mapping:", "cell:mapped:", "gen:")) for c in off)
        assert "label:vectors" in off, "the interval-vectors row owns its own toggle now (interval_vectors), so it does NOT go with # the temperament tiles: it stays, still showing the target vectors over the surviving targets # column. Only the cells in the now-gone temperament columns (the comma vectors) vanish"
        assert "cell:vector:targets:0:0" in off
        assert "header:primes" not in off
        assert not any(c.startswith(("prime:", "tuning:prime:", "just:prime:", "retune:prime:")) for c in off)
        assert "header:commas" not in off, "the commas column belongs to the temperament too, so it goes as well: header, # comma headers, the comma basis (its vectors), and the comma-size cells across the tuning rows"
        assert not any(c.startswith(("comma:", "cell:comma:", "tuning:comma:", "just:comma:",
                                     "retune:comma:")) for c in off)
        assert {"comma_plus", "comma_minus:0"}.isdisjoint(off)
        assert "tuning:target:0" in off
        assert off["tuning:target:0"].y < on["tuning:target:0"].y

    def test_interval_vectors_off_removes_the_interval_vectors_row_only(self):
        off = {c.id: c for c in _with(interval_vectors=False).cells}
        on = {c.id: c for c in _with().cells}
        assert "label:vectors" not in off
        assert not any(c.startswith(("cell:vector:", "cell:comma:", "cell:interest:", "cell:held:"))
                       for c in off)
        assert {"label:mapping", "cell:mapping:0:0", "header:primes", "header:commas",
                "label:quantities"} <= set(off)
        assert off["label:mapping"].y < on["label:mapping"].y

    def test_interval_vectors_row_reserves_no_phantom_picker_band_when_commas_column_hidden(self):
        s = settings.defaults()
        s["temperament_tiles"], s["interval_vectors"], s["presets"] = False, True, True
        meantone = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        with_comma = {b.id: b for b in spreadsheet.build(meantone, s).blocks}
        no_comma = {b.id: b for b in spreadsheet.build(full, s).blocks}
        assert with_comma["block:vector:quantities"].h == no_comma["block:vector:quantities"].h, "with the commas column hidden, the comma in state must not grow the vectors row: its spine # tile is the same height as the no-comma build (which reserves no band either way)"
        assert not any(c.id.startswith("commapick") for c in spreadsheet.build(meantone, s).cells)

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
        assert coll["label:tuning"].h < full["label:tuning"].h
        assert coll["label:just"].y < full["label:just"].y

    def test_collapsing_the_targets_column_hides_its_cells_across_every_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        full = spreadsheet.build(base)
        coll = spreadsheet.build(base, collapsed={"col:targets"})
        cids = {c.id for c in coll.cells}
        assert not any(_in_targets(c) for c in cids)
        assert "header:targets" in cids
        assert "toggle:col:targets" in cids
        assert coll.width < full.width

    def test_collapsing_the_domain_primes_column_hides_the_mapping_matrix(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cids = {c.id for c in spreadsheet.build(base, collapsed={"col:primes"}).cells}
        assert not any(c.startswith(("prime:", "cell:mapping:")) for c in cids)
        assert not any(c.startswith(("tuning:prime:", "just:prime:", "retune:prime:")) for c in cids)
        assert "header:primes" in cids
        assert "cell:mapped:0:0" in cids

    def test_collapsed_column_keeps_its_title_at_a_width_that_fits_it(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        coll = {c.id: c for c in spreadsheet.build(base, collapsed={"col:targets"}).cells}["header:targets"]
        full = {c.id: c for c in spreadsheet.build(base).cells}["header:targets"]
        assert coll.text == "target\nintervals", "the title stays put (not blanked, not rotated)"
        assert spreadsheet_constants.STRIP < coll.w < full.w

    def test_collapsed_column_gridline_stays_centred_in_its_fold_node(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        for key in ("commas", "targets"):
            lay = spreadsheet.build(base, collapsed={f"col:{key}"})
            trunk = {ln.id: ln for ln in lay.lines}[f"trunk:{key}"]
            cells = {c.id: c for c in lay.cells}
            toggle, header = cells[f"toggle:col:{key}"], cells[f"header:{key}"]
            assert abs(trunk.pos - (toggle.x + toggle.w / 2)) < 0.51, key
            assert abs(trunk.pos - (header.x + header.w / 2)) < 0.51, key

    def test_a_collapsed_multiline_title_strip_fits_its_widest_line(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        interest = {c.id: c for c in spreadsheet.build(
            base, collapsed={"col:interest"}, interest=[(0, 0, 0)] * 5).cells}["header:interest"]
        assert interest.text == "other intervals\nof interest"
        assert interest.w == len("other intervals") * 8 + 10, "the widest line, not all 27 chars"
        assert interest.w < len("other intervals of interest") * 8 + 10

    def test_collapsing_a_spine_column_never_widens_it(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults(); s["domain_units"] = True
        opened = {c.id: c for c in spreadsheet.build(base, s).cells}
        collapsed = {c.id: c for c in spreadsheet.build(base, s, collapsed={"col:quantities", "col:units"}).cells}
        for key in ("quantities", "units"):
            assert collapsed[f"header:{key}"].w <= opened[f"header:{key}"].w
        assert collapsed["header:units"].w == spreadsheet_constants.COL_W

    def test_a_rows_nested_control_grows_every_tile_in_that_row_uniformly(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ranges = settings.defaults(); ranges["tuning_ranges"] = True
        on = {b.id: b for b in spreadsheet.build(base, ranges).blocks}
        gens = on["block:tuning:gens"].h
        for sib in ("block:tuning:primes", "block:tuning:commas", "block:tuning:targets"):
            assert on[sib].h == gens, sib
        off = {b.id: b for b in spreadsheet.build(base).blocks}
        assert gens > off["block:tuning:primes"].h

        alt = settings.defaults(); alt["weighting"] = True; alt["alt_complexity"] = True
        aon = {b.id: b for b in spreadsheet.build(base, alt, tuning_scheme="TILT minimax-S").blocks}
        presc = aon["block:prescaling:primes"].h
        for sib in ("block:prescaling:commas", "block:prescaling:targets"):
            assert aon[sib].h == presc, sib
        comp = aon["block:complexity:targets"].h
        for sib in ("block:complexity:primes", "block:complexity:commas"):
            assert aon[sib].h == comp, sib

    def test_collapsing_a_column_does_not_shrink_its_rows_caption_band(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        without_gens = {b.id: b for b in spreadsheet.build(base, s, collapsed={"col:commas"}).blocks}
        with_gens = {b.id: b for b in spreadsheet.build(base, s, collapsed={"col:commas", "col:gens"}).blocks}
        for sib in ("block:tuning:primes", "block:tuning:targets"):
            assert with_gens[sib].h == without_gens[sib].h, f"{sib} shrank when the gens column collapsed"

    def test_collapsing_a_row_folds_its_panel_away_and_leaves_a_gridline(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base, collapsed={"row:tuning"})
        blocks = {b.id: b for b in lay.blocks}
        lines = {ln.id for ln in lay.lines}
        assert "block:tuning:primes" in blocks, "the panel persists so the renderer can animate it"
        assert blocks["block:tuning:primes"].h == 0
        assert "h:tuning" in lines

    def test_collapsing_a_column_folds_its_panels_away_and_converges_the_lines(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base, collapsed={"col:primes"})
        blocks = {b.id: b for b in lay.blocks}
        by_id = {ln.id: ln for ln in lay.lines}
        assert blocks["block:mapping"].w == 0
        assert by_id["v:prime:0"].pos == by_id["v:prime:1"].pos == by_id["v:prime:2"].pos, "the per-prime verticals converge onto one x (so they read as a single line)"
        assert by_id["bus:primes:top"].length == 0

    def test_a_collapsed_bands_gridline_is_dotted_while_open_bands_stay_solid(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        lay = spreadsheet.build(base, collapsed={"row:tuning", "col:primes"})
        by_id = {ln.id: ln for ln in lay.lines}
        assert by_id["h:tuning"].dotted
        assert by_id["trunk:primes"].dotted
        assert by_id["v:prime:0"].dotted
        assert not by_id["h:quantities"].dotted
        assert not by_id["trunk:gens"].dotted

    def test_a_collapsed_fanned_mapping_row_dots_its_converged_rules(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        by_id = {ln.id: ln for ln in spreadsheet.build(base, collapsed={"row:mapping"}).lines}
        assert by_id["trunk:mapping"].dotted and by_id["h:mapping:0"].dotted


class TestFormBox:
    def test_the_mapping_matrix_is_framed_top_and_bottom(self):
        cells = {c.id: c for c in _layout().cells}
        assert "ebktop:primes" in cells and "ebkbrace:primes" in cells
        top, brace = cells["ebktop:primes"], cells["ebkbrace:primes"]
        first, last = cells["cell:mapping:0:0"], cells["cell:mapping:1:0"]
        assert top.y + top.h < first.y, "the framing bands stand off the matrix by a gap, so the top bracket and # bottom brace never butt up against the per-row ⟨ … ] brackets (which would # read as one tall curly shape on the left edge)"
        assert brace.y > last.y + last.h
        assert {"ebktop:mapped:0", "ebkbrace:mapped:0"} <= set(cells)

    def test_form_box_shows_the_canonical_mapping_over_the_primes(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        assert cells["cell:canon:0:0"].text == "1"
        assert cells["cell:canon:0:2"].text == "-4"
        assert cells["cell:canon:1:1"].text == "1"
        assert cells["cell:canon:1:2"].text == "4"
        assert not any(c.id.startswith("cell:canon:") for c in _layout().cells)

    def test_canonical_mapping_row_is_framed_like_the_mapping_above_it(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        assert cells["bracket:canon:map:0:l"].text == "⟨" and cells["bracket:canon:map:0:r"].text == "]"
        assert "ebktop:canon" in cells and "ebkbrace:canon" in cells
        assert cells["ebktop:canon"].y < cells["cell:canon:0:0"].y
        assert cells["ebkbrace:canon"].y > cells["cell:canon:1:0"].y
        assert cells["caption:canon:primes"].text == "canonical mapping"
        assert cells["basis:0"].y < cells["cell:canon:0:0"].y < cells["cell:mapping:0:0"].y
        assert "ebktop:primes" in cells and cells["ebktop:primes"].y > cells["cell:canon:1:0"].y

    def test_form_box_shows_the_inverse_form_matrix_over_the_gens(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        assert cells["cell:form:0:0"].text == "1" and cells["cell:form:0:1"].text == "-1", "the canon row's gens tile is 𝐹⁻¹ (𝑀_C = 𝐹⁻¹𝑀, g_C/g) — read-only; the EDITABLE 𝐹 (𝑀 = 𝐹𝑀_C) # rides the mapping row's canonical-generators column instead. For ((1,1,0),(0,1,4)), 𝐹⁻¹ = ((1,-1),(0,1))"
        assert cells["cell:form:1:0"].text == "0" and cells["cell:form:1:1"].text == "1"
        assert cells["cell:form:0:0"].kind == "mapped"
        assert cells["caption:canon:gens"].text == "inverse generator form matrix"
        assert cells["bracket:form:map:0:l"].text == "{" and cells["bracket:form:map:0:r"].text == "]"
        assert "ebktop:form" in cells and "ebkbrace:form" in cells
        assert not any(c.id.startswith("cell:form:") for c in _layout().cells)

    def test_canonical_generators_column_sits_between_units_and_generators(self):
        cells = {c.id: c for c in _with(form_tiles=True).cells}
        assert cells["header:canongens"].text == "canonical\ngenerators"
        assert cells["header:quantities"].x < cells["header:canongens"].x < cells["header:gens"].x
        with_units = {c.id: c for c in _with(form_tiles=True, domain_units=True).cells}
        assert with_units["header:units"].x < with_units["header:canongens"].x < with_units["header:gens"].x
        assert not any(c.id == "header:canongens" for c in _layout().cells)
