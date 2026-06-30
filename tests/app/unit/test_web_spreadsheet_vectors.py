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
from _spreadsheet_support import _memoized_build, _layout, _drag_layout, _with


class TestIntervalVectorsRow:
    def test_interval_vectors_row_sits_between_quantities_and_mapping(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["label:vectors"].text == "interval vectors"
        assert cells["label:quantities"].text == "interval\nratios", "the interval-ratios row title is forced onto two lines ('interval\\nratios') so it reads as a # two-line title matching 'interval vectors' below it, rather than sitting on one line"
        assert "toggle:row:vectors" in cells
        assert cells["label:quantities"].y < cells["label:vectors"].y < cells["label:mapping"].y

    def test_interval_vectors_show_targets_as_vectors(self):
        cells = {c.id: c for c in _layout().cells}
        assert [cells[f"cell:vector:targets:0:{p}"].text for p in range(3)] == ["1", "0", "0"]
        assert [cells[f"cell:vector:targets:2:{p}"].text for p in range(3)] == ["-1", "1", "0"]
        assert [cells[f"cell:vector:targets:6:{p}"].text for p in range(3)] == ["-2", "0", "1"]
        v, hdr = cells["cell:vector:targets:2:0"], cells["target:2"]
        assert v.x + v.width / 2 == hdr.x + hdr.width / 2
        assert cells["cell:vector:targets:0:1"].y - cells["cell:vector:targets:0:0"].y == spreadsheet_constants.ROW_H

    def test_interval_vectors_domain_primes_identity_renders_with_identity_objects(self):
        J = grid_tables.SUB_OPEN + "j" + grid_tables.SUB_CLOSE
        cells = {c.id: c for c in _with(identity_objects=True, names=True, symbols=True,
                                        header_symbols=True, equivalences=True,
                                        plain_text_values=True).cells}
        for i in range(3):
            for k in range(3):
                assert cells[f"cell:vector:primes:{i}:{k}"].text == ("1" if i == k else "0")
                assert cells[f"cell:vector:primes:{i}:{k}"].kind == "mapped"
        assert cells["symbol:vectors:primes"].text == f"\U0001D440{J} = \U0001D43C"
        assert cells["caption:vectors:primes"].text == "JI mapping"
        assert cells["matlabel:row:vectors:primes:0"].text == f"\U0001D48E{J}₁"
        assert cells["ebktop:vector:primes"].kind == "ebktop"
        assert cells["ebkangle:vector:primes"].kind == "ebkangle", "the outer ⟩ foot (operator, not the } of M)"
        assert cells["bracket:vector:primes:0:l"].text == spreadsheet_constants.MAP_BRACKETS[0]
        assert cells["plain_text:vectors:primes"].text == "[⟨1 0 0]⟨0 1 0]⟨0 0 1]⟩"

    def test_interval_vectors_domain_primes_identity_gated_off_by_default(self):
        cells = {c.id for c in _with(names=True).cells}
        assert not any(c.startswith(("cell:vector:primes", "ebktop:vector:primes",
                                     "bracket:vector:primes")) for c in cells)
        assert {"toggle:tile:vectors:primes", "caption:vectors:primes"}.isdisjoint(cells)

    def test_interval_vectors_quantities_tile_shows_the_domain_basis_as_row_index(self):
        cells = {c.id: c for c in _layout().cells}
        assert [cells[f"basis:{p}"].text for p in range(3)] == ["2", "3", "5"]
        assert cells["basis:0"].width == spreadsheet_constants.COL_W == cells["prime:0"].width
        gen0 = cells["gen:0"]
        assert cells["basis:0"].x + cells["basis:0"].width / 2 == gen0.x + gen0.width / 2
        assert cells["basis:0"].y == cells["cell:comma:0:0"].y
        assert cells["basis:1"].y - cells["basis:0"].y == spreadsheet_constants.ROW_H

    def test_interval_vectors_basis_controls_ride_the_rows_left_bus(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        plus, minus, bot = cells["basis_plus"], cells["basis_minus"], cells["basis:2"]
        left_bus = by_id["vbar:vectors:left"]
        assert minus.x == left_bus.pos, "− zone drops from the left-bus branch point (button at its edge)"
        assert abs((minus.y + minus.height / 2) - by_id["h:vectors:2"].pos) < 0.51
        assert minus.x < cells["basis:2"].x
        assert abs((plus.x + plus.width / 2) - left_bus.pos) < 0.51
        assert plus.y >= bot.y + bot.height
        assert abs((left_bus.start + left_bus.length) - (plus.y + plus.height / 2)) < 0.51

    def test_mapping_row_controls_ride_the_rows_left_bus(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        left_bus = by_id["vbar:mapping:left"]
        for i in range(2):
            minus = cells[f"map_minus:{i}"]
            assert minus.x == left_bus.pos, "− drops from the left-bus branch point"
            assert abs((minus.y + minus.height / 2) - by_id[f"h:mapping:{i}"].pos) < 0.51
            assert minus.x < cells["gen:0"].x
        plus = cells["map_plus"]
        assert abs((plus.x + plus.width / 2) - left_bus.pos) < 0.51
        assert plus.y >= cells["gen:1"].y + cells["gen:1"].height
        assert abs((left_bus.start + left_bus.length) - (plus.y + plus.height / 2)) < 0.51

    def test_mapping_row_minus_gated_on_rank_and_plus_on_nullity(self):
        rank1 = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0),))).cells}
        assert "map_plus" in rank1 and "map_minus:0" not in rank1, "n>0 so a +, but can't drop the sole row"
        ji = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))).cells}
        assert "map_plus" not in ji, "full rank: nothing tempered to un-temper"
        assert {"map_minus:0", "map_minus:1", "map_minus:2"} <= ji

    def test_a_rank_one_mapping_still_fans_to_connect_its_plus(self):
        layout = spreadsheet.build(service.from_mapping(((12, 19, 28),)))
        cells = {c.id: c for c in layout.cells}
        by_id = {line.id: line for line in layout.lines}
        assert "h:mapping:0" in by_id and "h:mapping" not in by_id, "the fanned sub-rule, not the flat spine"
        left_bus, plus = by_id["vbar:mapping:left"], cells["map_plus"]
        assert abs((plus.x + plus.width / 2) - left_bus.pos) < 0.51
        assert abs((left_bus.start + left_bus.length) - (plus.y + plus.height / 2)) < 0.51
        assert abs((plus.x + plus.width / 2) - (cells["basis_plus"].x + cells["basis_plus"].width / 2)) < 0.51, "...and the + sits as close to the spine as the always-fanned basis +, not a FAN further out"

    def test_drag_handles_are_gated_on_the_drag_to_combine_toggle(self):
        off = {c.id for c in _layout().cells}
        assert not any(c.startswith(("map_drag:", "int_drag:")) for c in off)
        on = {c.id for c in _drag_layout().cells}
        assert "map_drag:0" in on
        assert any(c.startswith("int_drag:target:") for c in on)

    def test_mapping_row_drag_handles_sit_left_of_the_row_labels(self):
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))),
                                {**settings.defaults(), "symbols": True, "header_symbols": True, "drag_to_combine": True})
        cells = {c.id: c for c in layout.cells}
        for i in range(2):
            handle = cells[f"map_drag:{i}"]
            label = cells[f"matlabel:row:mapping:primes:{i}"]
            assert handle.gen == i
            assert handle.y == cells[f"cell:mapping:{i}:0"].y
            assert handle.x + handle.width <= label.x
            assert label.x + label.width <= cells[f"cell:mapping:{i}:0"].x
            assert handle.x > cells[f"map_minus:{i}"].x

    def test_mapping_row_drag_handles_need_two_rows(self):
        rank1 = {c.id for c in _drag_layout(((1, 0, 0),)).cells}
        assert not any(c.startswith("map_drag:") for c in rank1)
        assert {"map_drag:0", "map_drag:1"} <= {c.id for c in _drag_layout().cells}

    def test_interval_drag_handles_sit_above_the_column_labels_in_the_vectors_row(self):
        layout = spreadsheet.build(service.from_mapping(((12, 19, 28),)),
                                {**settings.defaults(), "symbols": True, "header_symbols": True, "drag_to_combine": True},
                                interest=((-1, 1, 0), (0, 0, 1)))
        cells = {c.id: c for c in layout.cells}
        for i in range(2):
            handle = cells[f"int_drag:comma:{i}"]
            label = cells[f"matlabel:col:vectors:commas:{i}"]
            vector0 = cells[f"cell:comma:0:{i}"]
            assert handle.comma == i and handle.x == label.x
            assert handle.y + handle.height <= label.y
            assert label.y < vector0.y
        assert cells["int_drag:interest:0"].y + spreadsheet_constants.ROW_HANDLE_W <= cells["cell:interest:0:0"].y
        assert "int_drag:target:0" in cells

    def test_interval_drag_handles_need_two_entries_and_skip_all_interval_targets(self):
        one_comma = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id for c in _drag_layout(((1, 1, 0), (0, 1, 4))).cells}
        assert not any(c.startswith("int_drag:comma") for c in cells)
        ai = {c.id for c in spreadsheet.build(one_comma, settings.defaults(), tuning_scheme="minimax-S").cells}
        assert not any(c.startswith("int_drag:target") for c in ai)

    def test_full_rank_temperament_shows_an_empty_commas_column(self):
        ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        cells = {c.id for c in spreadsheet.build(ji).cells}
        assert not any(c.startswith(("comma:", "cell:comma:")) for c in cells)
        assert "comma_plus" in cells

    def test_grid_builds_for_an_octave_less_temperament(self):
        degenerate = service.remove_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))), 0)
        layout = spreadsheet.build(degenerate)
        assert any(c.id == "gen:0" for c in layout.cells)

    def test_interval_vectors_basis_minus_is_absent_when_the_domain_cannot_shrink(self):
        base = service.from_mapping(((1,),))
        cells = {c.id for c in spreadsheet.build(base).cells}
        assert "basis_plus" in cells and "basis_minus" not in cells
