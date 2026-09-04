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

    def test_only_explicitly_held_slots_get_a_minus(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    held_vectors=[(1, 0, 0)], held_basis_ratios=("2/1",)).cells}
        assert cells["unchanged_minus:0"].kind == "unchanged_minus" and cells["unchanged_minus:0"].comma == 0
        assert cells["unchanged_minus:0"].x == cells["unchanged:0"].x
        assert "unchanged_minus:1" not in cells

    def test_emergent_slots_get_no_minus_since_removal_could_not_bite(self):
        s = settings.defaults()
        s["projection"] = True
        cells = {c.id for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                 held_basis_ratios=("2/1", "5/4")).cells}
        assert not any(c.startswith("unchanged_minus:") for c in cells)

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


class TestMatrixCellsShareThePlainTextEditabilityFlag:
    def test_projection_and_embedding_cells_are_editable_exactly_when_their_plain_text_is(self):
        s = settings.defaults()
        s["projection"] = s["plain_text_values"] = True
        full = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                   held_basis_ratios=("2/1", "5/4")).cells}
        assert full["plain_text:projection:primes"].kind == "plain_text_edit"
        assert all(full[f"cell:projection:{i}:{p}"].kind == "projection_cell" for i in range(3) for p in range(3))
        assert full["plain_text:vectors:generator_embedding"].kind == "plain_text_edit"
        assert all(full[f"cell:embed:{i}:{g}"].kind == "embed_cell" for i in range(3) for g in range(2))
        dashed = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s).cells}
        assert dashed["plain_text:projection:primes"].kind == "plain_text"
        assert all(dashed[f"cell:projection:{i}:{p}"].kind == "mapped" for i in range(3) for p in range(3))
        assert dashed["plain_text:vectors:generator_embedding"].kind == "plain_text"
        assert all(dashed[f"cell:embed:{i}:{g}"].kind == "mapped" for i in range(3) for g in range(2))

    def test_derived_projection_grids_stay_read_only_even_when_full(self):
        cells = {c.id: c for c in _projection_full(generator_detempering=True).cells}
        assert all(c.kind == "mapped" for i, c in cells.items() if i.startswith(("cell:projection_detempering:", "cell:projection_targets:", "cell:embed_c:")))
