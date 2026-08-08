from rtt.app import service, settings, spreadsheet
from _spreadsheet_support import _projection_full, _with_held


class TestProjectionReplacesHeldColumn:
    def test_projection_on_hides_the_held_column_everywhere(self):
        layout = _projection_full(optimization=True, held_vectors=[(1, 0, 0)])
        ids = {c.id for c in layout.cells} | {line.id for line in layout.lines}
        assert not any("held" in i for i in ids)

    def test_projection_off_keeps_the_held_column(self):
        ids = {c.id for c in _with_held([(1, 0, 0)]).cells}
        assert "held:0" in ids and "held_plus" in ids

    def test_hidden_holds_still_constrain_the_tuning(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    held_vectors=[(1, 0, 0)]).cells}
        assert cells["tuning:prime:0"].text == "1200.000"


class TestUnchangedSlotsAreTheHeldInput:
    def test_every_unchanged_slot_is_an_editable_ratio_cell(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    held_vectors=[(1, 0, 0)], held_basis_ratios=("2/1",)).cells}
        assert cells["unchanged:0"].kind == "ratio_cell" and cells["unchanged:0"].text == "2/1"
        assert cells["unchanged:1"].kind == "ratio_cell" and cells["unchanged:1"].text == "—"

    def test_filled_slots_get_a_minus_and_dashed_slots_do_not(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    held_vectors=[(1, 0, 0)], held_basis_ratios=("2/1",)).cells}
        assert cells["unchanged_minus:0"].kind == "unchanged_minus" and cells["unchanged_minus:0"].comma == 0
        assert cells["unchanged_minus:0"].x == cells["unchanged:0"].x
        assert "unchanged_minus:1" not in cells

    def test_a_ji_state_offers_no_unchanged_minus(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1))), s).cells}
        assert not any(c.startswith("unchanged_minus:") for c in cells)

    def test_a_doomed_slot_under_a_pending_comma_stays_read_only(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    pending_comma=[None, None, None]).cells}
        assert cells["unchanged:1"].kind == "comma_ratio"
