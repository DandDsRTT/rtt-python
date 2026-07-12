import json

import pytest

from rtt.app.service.pump import comma_pump_moves, pump_payload
from _spreadsheet_support import _layout, _projection_build

_J5 = (1200.0, 1901.955, 2786.3137)
_T5 = (1200.0, 1896.578, 2786.312)
_J7 = (1200.0, 1901.955, 2786.3137, 3368.8259)


def _sums(moves, d):
    return [sum(m[i] for m in moves) for i in range(d)]


class TestCommaPumpMoves:
    def test_moves_sum_to_the_negated_comma_exactly(self):
        for comma, jmap in (([-4, 4, -1], _J5), ([11, -4, -2], _J5), ([1, -5, 3], _J5), ([6, -2, 0, -1], _J7)):
            moves = comma_pump_moves(comma, jmap)
            assert moves, comma
            assert _sums(moves, len(comma)) == [-x for x in comma], comma

    def test_meantone_pump_is_the_classic_descending_fourths_progression(self):
        assert comma_pump_moves([-4, 4, -1], _J5) == ((2, -1, 0), (1, -1, 0), (2, -1, 0), (1, -1, 0), (-2, 0, 1))

    def test_every_landing_stays_within_half_an_equave_of_home(self):
        for comma in ([-4, 4, -1], [11, -4, -2], [1, -5, 3], [-15, 8, 1]):
            landing = 0.0
            for move in comma_pump_moves(comma, _J5):
                landing += sum(x * j for x, j in zip(move, _J5))
                assert abs(landing) <= 600.0 + 25.0, (comma, landing)

    def test_zero_or_degenerate_commas_produce_no_moves(self):
        assert comma_pump_moves([0, 0, 0], _J5) == ()
        assert comma_pump_moves([], ()) == ()
        assert comma_pump_moves([-4, 4, -1], (1200.0, 1901.955)) == ()
        assert comma_pump_moves([-4, 4, -1], (0.0, 1901.955, 2786.3137)) == ()

    def test_equave_only_comma_closes_with_pure_equave_moves(self):
        assert comma_pump_moves([3, 0, 0], _J5) == ((-1, 0, 0), (-1, 0, 0), (-1, 0, 0))


class TestPumpPayload:
    def test_payload_roots_follow_the_moves_in_both_tunings(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert d["ji"] == pytest.approx([0.0, 498.045, -203.91, 294.135, -407.82], abs=1e-3)
        assert d["t"] == pytest.approx([0.0, 503.422, -193.156, 310.266, -386.312], abs=1e-3)

    def test_tempered_drift_closes_to_zero_while_just_drifts_by_the_comma(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert abs(d["dt"]) < 1e-9, "the comma is tempered out, so one full cycle returns home to float precision"
        assert abs(d["dji"] - -21.5063) < 0.001, "in JI each cycle drifts flat by the comma"

    def test_payload_carries_both_equave_sizes_for_chord_voicing(self):
        stretched = (1201.0, 1898.0, -4 * 1201.0 + 4 * 1898.0)
        d = json.loads(pump_payload([-4, 4, -1], _J5, stretched))
        assert d["eji"] == 1200.0 and d["et"] == 1201.0
        assert abs(d["dt"]) < 1e-9, "closure holds for any generator tuning, octave-stretched included"

    def test_degenerate_payloads_are_empty(self):
        assert pump_payload([0, 0, 0], _J5, _T5) == ""
        assert pump_payload([-4, 4, -1], _J5, (1200.0, 1896.578)) == ""


class TestPumpStamping:
    def test_comma_column_cells_carry_the_pump_payload(self):
        cells = {c.id: c for c in _layout().cells}
        ratio = cells["comma:0"]
        assert ratio.pump, "the quantities-column comma ratio cell offers the pump"
        d = json.loads(ratio.pump)
        assert set(d) == {"ji", "t", "dji", "dt", "eji", "et"}
        assert len(d["ji"]) == len(d["t"]) == 5
        assert abs(d["dt"]) < 1e-6 and abs(abs(d["dji"]) - 21.5063) < 0.001
        vector_pumps = [c.pump for c in cells.values() if c.kind == "comma_cell"]
        assert vector_pumps and all(p == ratio.pump for p in vector_pumps), "every cell of the comma's column shares one payload"

    def test_noncomma_and_unchanged_columns_carry_no_pump(self):
        layout = _layout()
        assert all(not c.pump for c in layout.cells if c.kind in ("prime", "target_cell", "held_cell", "unchanged_cell", "generator_ratio"))
        assert all(not c.pump for c in layout.cells if c.audio is not None and not c.audio[0].endswith(":commas")), "only the commas tiles' columns offer a pump"
        assert any(c.pump for c in layout.cells if c.kind == "mapped" and c.audio is not None and c.audio[0] == "mapped:commas"), "the mapping row's slice of the comma's column offers it too"
        unchanged = [c for c in _projection_build(("3/2",)).cells if c.audio is not None and c.audio[0].endswith(":commas") and c.audio[1] >= 1]
        assert unchanged and all(not c.pump for c in unchanged), "unchanged-interval columns share the commas tile but are not pumpable"

    def test_pump_tempered_roots_reflect_the_temperament_not_ji(self):
        cells = {c.id: c for c in _layout().cells}
        d = json.loads(cells["comma:0"].pump)
        assert d["t"] != d["ji"], "meantone retunes the pump's roots away from their just sizes"
