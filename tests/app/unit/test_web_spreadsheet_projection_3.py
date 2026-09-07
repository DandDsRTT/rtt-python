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


class TestEmbeddingColumnSizesMeasureTheEmbedding:
    def _cells(self, **extra):
        s = settings.defaults()
        s.update(projection=True, generator_detempering=True, plain_text_values=True, **extra)
        return {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                   held_basis_ratios=("2/1", "5/4")).cells}

    def test_the_just_and_retuning_sizes_are_taken_over_Gs_columns_not_Ds(self):
        cells = self._cells()
        assert cells["cell:embed:2:1"].text == "1/4", "G's second column is the fourth root of 5"
        assert cells["just:generator_embedding:1"].text == "696.578", "𝒋G is the just size of that root, not 𝒋D's 701.955"
        assert cells["retune:generator_embedding:1"].text == "0.000", "G's columns are held, so 𝒓G vanishes — 𝒓D would read -4.391"
        assert cells["just:generator:1"].text == "701.955", "the detempering column still measures D"

    def test_the_tempered_size_over_G_is_the_generator_tuning_map(self):
        cells = self._cells()
        assert [cells[f"tuning:generator_embedding:{g}"].text for g in range(2)] == \
               [cells[f"tuning:generator:{g}"].text for g in range(2)], "𝒕G = 𝒈𝑀G = 𝒈"

    def test_the_sizes_dash_with_the_embedding_they_measure(self):
        s = settings.defaults()
        s.update(projection=True, generator_detempering=True, plain_text_values=True)
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s).cells}
        assert cells["cell:embed:0:0"].text == "—"
        for key in ("tuning", "just", "retune"):
            assert all(cells[f"{key}:generator_embedding:{g}"].text == "—" for g in range(2))
            assert "—" in cells[f"plain_text:{key}:generator_embedding"].text

    def test_the_plain_text_band_reads_the_same_sizes_as_the_grid(self):
        cells = self._cells()
        for key in ("tuning", "just", "retune"):
            grid = [cells[f"{key}:generator_embedding:{g}"].text for g in range(2)]
            assert all(v in cells[f"plain_text:{key}:generator_embedding"].text for v in grid)
