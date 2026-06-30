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
from _spreadsheet_support import _memoized_build, _layout, _with, _title_edges, _assert_freeze_partition, _all_on


class TestFreezeAndStructure:
    def test_rows_columns_and_cells_are_present(self):
        ids = {c.id for c in _layout().cells}
        assert {"header:generators", "header:primes"} <= ids
        assert {"label:quantities", "label:mapping"} <= ids
        assert {"prime:0", "prime:1", "prime:2"} <= ids
        assert {"generator:0", "generator:1"} <= ids
        assert {"cell:mapping:0:0", "cell:mapping:1:2"} <= ids
        assert {"minus", "plus"} <= ids

    def test_freeze_seam_sits_at_the_first_value_tile(self):
        layout = _layout()
        tiles = [bl for bl in layout.blocks if bl.tint == "" and not bl.boxed]
        assert layout.freeze_y == min(bl.y for bl in tiles)
        assert layout.freeze_x == min(bl.x for bl in tiles)
        by_id = {line.id: line for line in layout.lines}
        assert by_id["trunk:primes"].start < layout.freeze_y
        assert by_id["trunk:mapping"].start < layout.freeze_x

    def test_the_first_columns_title_clears_the_frozen_corner(self):
        layout = _layout()
        height = {c.id: c for c in layout.cells}["header:quantities"]
        title_left = (height.x + height.width / 2) - spreadsheet_text._title_w(height.text) / 2
        assert title_left >= layout.freeze_x - 0.51, "not tucked under the frozen corner"

    def test_branch_controls_ride_the_frozen_bands(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        assert cells["plus"].y + cells["plus"].height <= layout.freeze_y
        assert cells["minus"].y < layout.freeze_y
        assert cells["basis_plus"].x + cells["basis_plus"].width <= layout.freeze_x
        assert cells["basis_minus"].x < layout.freeze_x

    def test_layout_reports_the_rightmost_title_overhang(self):
        layout = _layout()
        rightmost = max(c.x + c.width / 2 + spreadsheet_text._title_w(c.text) / 2
                        for c in layout.cells if c.kind == "columnheader")
        assert layout.right_overhang == rightmost - layout.width
        assert layout.right_overhang > 0

    def test_no_title_overhang_reports_zero(self):
        layout = _with(interest=False)
        rightmost = max(c.x + c.width / 2 + spreadsheet_text._title_w(c.text) / 2
                        for c in layout.cells if c.kind == "columnheader")
        assert rightmost < layout.width
        assert layout.right_overhang == 0

    def test_adjacent_column_titles_keep_a_margin(self):
        s = settings.defaults()
        s["optimization"] = True
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, targets_in_use=False)
        edges = _title_edges(layout)
        assert [k for k, _l, _r in edges][-2:] == ["held", "interest"]
        for (lk, _ll, lr), (rk, rl, _rr) in zip(edges, edges[1:]):
            assert rl - lr >= spreadsheet_constants.TITLE_MARGIN - 0.5, f"{lk}->{rk} titles only {rl - lr:.1f}px apart"

    def test_title_clearance_leaves_shielded_columns_untouched(self):
        layout = _layout()
        interest = {c.id: c for c in layout.cells}["header:interest"]
        targets = {c.id: c for c in layout.cells}["header:targets"]
        assert interest.x == targets.x + targets.width + spreadsheet_constants.GAP, "plain GAP, not widened"
        assert layout.right_overhang > 0

    def test_freeze_bands_hold_exactly_the_titles_and_toggles(self):
        _assert_freeze_partition(_layout())

    def test_freeze_bands_survive_collapsing_rows_and_columns(self):
        collapsed = {"row:tuning", "row:mapping", "column:targets", "column:primes"}
        _assert_freeze_partition(spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), collapsed=collapsed))

    def test_build_renders_a_nonstandard_domain_in_its_elements(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        cells = {c.id: c for c in spreadsheet.build(state).cells}
        assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "13/5"]
        assert cells["header:primes"].text == "domain basis\nelements"
        assert cells["generator:1"].text == "15/13"

    def test_build_threads_nonprime_approach_through_to_the_tuning(self):
        state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
        neutral = spreadsheet.build(state, tuning_scheme="TILT minimax-C")
        nonprime = spreadsheet.build(state, tuning_scheme="TILT minimax-C", nonprime_approach="nonprime-based")
        n = {c.id: c.text for c in neutral.cells}
        np_ = {c.id: c.text for c in nonprime.cells}
        assert n["tuning:generator:0"] != np_["tuning:generator:0"]
        assert n["tuning:generator:1"] != np_["tuning:generator:1"]

    def test_generator_ratios_also_head_the_generators_column_in_the_quantities_row(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["quantities_generator:0"].text == "2/1"
        assert cells["quantities_generator:1"].text == "3/2"
        assert cells["quantities_generator:0"].x == cells["tuning:generator:0"].x
        assert cells["quantities_generator:1"].x == cells["tuning:generator:1"].x
        assert cells["quantities_generator:0"].y == cells["prime:0"].y

    def test_standard_domain_header_still_reads_domain_primes(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["header:primes"].text == "domain\nprimes"
        assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "5"]

    def test_nonstandard_but_all_prime_domain_still_reads_domain_primes(self):
        arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))
        s = settings.defaults()
        s["domain_units"] = True
        cells = {c.id: c for c in spreadsheet.build(arch, s).cells}
        assert cells["header:primes"].text == "domain\nprimes"
        assert [cells[f"prime:{p}"].text for p in range(3)] == ["2", "3", "7"]
        assert cells["units_row:primes:0"].text == "/p₁", "its coordinate label is p (true primes) too, not the basis-element b"

    def test_generator_ratios_are_listed_in_the_quantities_column(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["generator:0"].text == "2/1"
        assert cells["generator:1"].text == "3/2"
        assert cells["generator:0"].x == cells["header:quantities"].x
        assert cells["generator:0"].x < cells["header:generators"].x
        assert cells["generator:0"].y == cells["cell:mapping:0:0"].y
        assert cells["generator:1"].y == cells["cell:mapping:1:0"].y

    def test_mapping_over_generators_identity_renders_with_identity_objects(self):
        cells = {c.id: c for c in _with(identity_objects=True, names=True, symbols=True,
                                        equivalences=True, plain_text_values=True).cells}
        for i in range(2):
            for k in range(2):
                assert cells[f"cell:selfmap:{i}:{k}"].text == ("1" if i == k else "0")
                assert cells[f"cell:selfmap:{i}:{k}"].kind == "mapped"
        assert cells["symbol:mapping:generators"].text == "\U0001D440G = \U0001D43C"
        assert cells["caption:mapping:generators"].text == "mapped generators"
        assert cells["bracket:selfmap:l"].text == spreadsheet_constants.GENMAP_BRACKETS[0]
        assert cells["bracket:selfmap:r"].text == spreadsheet_constants.GENMAP_BRACKETS[1]
        assert cells["ebktop:selfmap:0"].kind == "ebktop"
        assert cells["ebkbrace:selfmap:0"].kind == "ebkbrace"
        assert cells["plain_text:mapping:generators"].text == "{[1 0} [0 1}]"
        assert not any(c.startswith(("matrix_label:row:mapping:generators", "matrix_label:column:mapping:generators")) for c in cells)

    def test_mapping_over_generators_identity_gated_off_by_default(self):
        cells = {c.id for c in _layout().cells}
        assert not any(c.startswith(("cell:selfmap", "bracket:selfmap", "ebktop:selfmap",
                                     "ebkbrace:selfmap")) for c in cells)
        assert "toggle:tile:mapping:generators" not in cells

    def test_standard_identity_objects_wash_temperament_yellow(self):
        washes = {b.id for b in _with(identity_objects=True, generator_detempering=True,
                                      temperament_colorization=True).blocks}
        for key in ("vectors:primes", "mapping:generators", "mapping:detempering"):
            assert f"wash:temperament:{key}" in washes
            assert f"wash:tuning:{key}" not in washes, "not cyan"

    def test_primes_sit_above_the_mapping_columns(self):
        cells = {c.id: c for c in _layout().cells}
        for p in range(3):
            assert cells[f"prime:{p}"].x == cells[f"cell:mapping:0:{p}"].x
        assert cells["prime:0"].y < cells["cell:mapping:0:0"].y

    def test_minus_is_revealed_at_the_last_primes_branch_point_clear_of_its_input(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        minus = cells["minus"]
        assert abs((minus.x + minus.width / 2) - by_id["v:prime:2"].position) < 0.51
        assert minus.y == by_id["bus:primes:top"].position, "the zone drops from the top bus (branch point)"
        assert minus.y + minus.height <= cells["cell:mapping:0:2"].y

    def test_minus_tracks_the_new_last_prime_after_a_shrink(self):
        wide = service.expand_domain(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        wlay = spreadsheet.build(wide)
        wcells, wlines = {c.id: c for c in wlay.cells}, {line.id: line for line in wlay.lines}
        assert abs((wcells["minus"].x + wcells["minus"].width / 2) - wlines["v:prime:3"].position) < 0.51
        slay = spreadsheet.build(service.shrink_domain(wide))
        scells, slines = {c.id: c for c in slay.cells}, {line.id: line for line in slay.lines}
        assert "prime:3" not in scells
        assert abs((scells["minus"].x + scells["minus"].width / 2) - slines["v:prime:2"].position) < 0.51

    def test_a_single_prime_domain_has_no_minus_but_keeps_plus(self):
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1,),))).cells}
        assert "minus" not in cells
        assert {"plus", "prime:0"} <= cells

    def test_domain_minus_is_absent_on_a_nonstandard_subgroup(self):
        arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))
        cells = {c.id for c in spreadsheet.build(arch).cells}
        assert {"prime:0", "prime:2"} <= cells
        assert "minus" not in cells and "basis_minus" not in cells

    def test_domain_minus_shows_even_when_the_shrink_would_degenerate(self):
        augmented = service.from_comma_basis(((7, 0, -3),))
        cells = {c.id for c in spreadsheet.build(augmented).cells}
        assert {"prime:0", "prime:2"} <= cells
        assert "minus" in cells and "basis_minus" in cells

    def test_domain_plus_is_absent_on_a_nonstandard_subgroup(self):
        arch = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))
        cells = {c.id for c in spreadsheet.build(arch).cells}
        assert {"prime:0", "prime:2"} <= cells
        assert "plus" not in cells and "basis_plus" not in cells

    def test_quantities_row_pluses_ride_the_bus_stub_past_the_last_branch_point(self):
        opts = settings.defaults()
        opts["names"] = False
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), opts, interest=((-1, 1, 0),))
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        for plus_id, col, last_sub, gap in (("plus", "primes", "v:prime:2", 0),
                                            ("comma_plus", "commas", "v:comma:0", 0),
                                            ("interest_plus", "interest", "v:interest:0", spreadsheet_constants.INTERVAL_COL_GAP / 2)):
            plus, bus = cells[plus_id], by_id[f"bus:{col}:top"]
            stub = by_id[last_sub].position + spreadsheet_constants.COLUMN_WIDTH + gap
            assert abs((plus.x + plus.width / 2) - stub) < 0.51
            assert abs((plus.y + plus.height / 2) - bus.position) < 0.51
            assert abs((bus.start + bus.length) - stub) < 0.51

    def test_interval_pluses_survive_hiding_the_quantities_row(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        interval_pluses = {"comma_plus", "target_plus", "interest_plus"}
        quantities_only = {"plus", "generator_plus"}

        shown = {c.id for c in spreadsheet.build(state).cells}
        assert (interval_pluses | quantities_only) <= shown

        folded = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"}).cells}
        assert interval_pluses <= folded
        assert quantities_only.isdisjoint(folded)

        off = settings.defaults()
        off["interval_ratios"] = False
        dropped = {c.id for c in spreadsheet.build(state, off).cells}
        assert interval_pluses <= dropped
        assert quantities_only.isdisjoint(dropped)

        both_hidden = {c.id for c in spreadsheet.build(state, off, collapsed={"row:vectors"}).cells}
        assert (interval_pluses | quantities_only).isdisjoint(both_hidden)


class TestAddRemoveControls:
    def test_interval_minuses_rehome_to_the_vectors_row_when_quantities_hidden(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        shown = {c.id for c in spreadsheet.build(state).cells}
        assert {"comma_minus:0", "target_minus:0", "minus", "generator_minus"} <= shown

        folded = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"}).cells}
        assert {"comma_minus:0", "target_minus:0"} <= folded
        assert {"minus", "generator_minus"}.isdisjoint(folded)
        assert "basis_minus" in folded, "(the domain − twin already lives on the vectors row)"

        drafts = (("pending_comma", "comma_minus:pending"), ("pending_interest", "interest_minus:pending"))
        for arg, minus_id in drafts:
            cells = {c.id for c in spreadsheet.build(state, collapsed={"row:quantities"},
                                                     **{arg: [None, None, None]}).cells}
            assert minus_id in cells

        off = settings.defaults(); off["interval_ratios"] = False
        both_hidden = {c.id for c in spreadsheet.build(state, off, collapsed={"row:vectors"}).cells}
        assert {"comma_minus:0", "target_minus:0"}.isdisjoint(both_hidden)

    def test_generators_plus_and_minus_ride_the_generators_fan(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        plus, bus, last_sub = cells["generator_plus"], by_id["bus:generators:top"], by_id["v:generator:1"]
        stub = last_sub.position + spreadsheet_constants.COLUMN_WIDTH
        assert abs((plus.x + plus.width / 2) - stub) < 0.51
        assert abs((plus.y + plus.height / 2) - bus.position) < 0.51
        assert abs((bus.start + bus.length) - stub) < 0.51
        minus = cells["generator_minus"]
        assert abs((minus.x + minus.width / 2) - last_sub.position) < 0.51
        assert minus.y == bus.position, "the zone drops from the top bus"
        assert minus.y + minus.height <= cells["tuning:generator:0"].y

    def test_a_single_generator_temperament_has_no_gen_minus_but_keeps_gen_plus(self):
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}
        assert "generator_minus" not in cells
        assert {"generator_plus", "quantities_generator:0"} <= cells, "...but n>0, so a generator can still be added (un-tempering a comma)"

    def test_generators_plus_is_gated_on_a_comma_to_un_temper(self):
        assert "generator_plus" in {c.id for c in _layout().cells}, "the generators + un-tempers a comma (−n, +r, hold d), like the mapping +, so it needs a comma: # present at n>0, gone at full rank where there is nothing left to un-temper"
        ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert "generator_plus" not in {c.id for c in spreadsheet.build(ji).cells}

    def test_minus_hover_zone_clears_the_editable_quantities_cell(self):
        cells = {c.id: c for c in _layout().cells}
        k = len([c for c in cells if c.startswith("target:") and c.split(":")[1].isdigit()])
        assert k >= 2
        for j in range(k):
            zone, cell = cells[f"target_minus:{j}"], cells[f"target:{j}"]
            assert zone.y + zone.height <= cell.y + 0.51

    def test_target_list_carries_a_per_entry_minus_and_a_plus(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        k = len([c for c in cells if c.startswith("target:") and c.split(":")[1].isdigit()])
        assert k >= 2
        assert all(f"target_minus:{j}" in cells for j in range(k))
        plus, bus, last_sub = cells["target_plus"], by_id["bus:targets:top"], by_id[f"v:target:{k - 1}"]
        stub = last_sub.position + spreadsheet_constants.COLUMN_WIDTH + spreadsheet_constants.INTERVAL_COL_GAP
        assert abs((plus.x + plus.width / 2) - stub) < 0.51
        assert abs((bus.start + bus.length) - stub) < 0.51

    def test_target_list_has_no_controls_in_all_interval(self):
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), tuning_scheme="minimax-S")
        cells = {c.id for c in layout.cells}
        assert "target_plus" not in cells
        assert not any(c.startswith("target_minus:") for c in cells)

    def test_interval_columns_carry_a_drag_grip_per_column(self):
        ed = Editor()
        ed.set_held_vectors([(-1, 1, 0), (2, 0, -1)])
        ed.set_interest_vectors([(1, 1, -1)])
        cells = {c.id: c for c in spreadsheet.build(
            ed.state, _all_on(), interest=ed.interest_vectors, held_vectors=ed.held_vectors).cells}
        assert cells["grip:held:0"].kind == "columngrip" and cells["grip:held:1"].kind == "columngrip"
        assert "grip:held:2" not in cells
        assert cells["grip:held:add"].kind == "columngrip"
        assert cells["grip:interest:0"].kind == "columngrip"

    def test_a_drag_grip_rides_the_fan_band_below_the_minus(self):
        ed = Editor()
        ed.set_held_vectors([(-1, 1, 0), (2, 0, -1)])
        layout = spreadsheet.build(ed.state, _all_on(), held_vectors=ed.held_vectors)
        cells = {c.id: c for c in layout.cells}
        sub = {line.id: line for line in layout.lines}["v:held:1"].position
        grip, minus = cells["grip:held:1"], cells["held_minus:1"]
        assert abs((grip.x + grip.width / 2) - sub) < 0.51
        assert grip.y > minus.y + 0.5
        assert grip.y + grip.height <= layout.freeze_y + 0.51, "...and above the seam (in the frozen fan, not clipped)"

    def test_an_empty_interval_list_still_offers_a_gridline_drop_zone(self):
        cells = {c.id for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), _all_on()).cells}
        assert "grip:interest:0" not in cells
        assert "grip:interest:add" in cells

    def test_comma_grips_let_even_the_sole_comma_be_dragged_out(self):
        on = {**_all_on(), "projection": False}
        one = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), on).cells}
        assert "grip:commas:0" in one and "grip:commas:add" in one
        two = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),)), on).cells}
        assert "grip:commas:0" in two and "grip:commas:1" in two
        ji = {c.id for c in spreadsheet.build(service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4)))), on).cells}
        assert "grip:commas:0" not in ji

    def test_targets_have_no_drag_grips_in_all_interval(self):
        cells = {c.id for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), tuning_scheme="minimax-S").cells}
        assert not any(c.startswith("grip:targets") for c in cells)
