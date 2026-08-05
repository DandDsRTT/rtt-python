from rtt.app import service, settings, spreadsheet, spreadsheet_constants
from _spreadsheet_support import _with


class TestPendingGeneratorDraft:
    @staticmethod
    def _all_on():
        s = settings.defaults()
        for key in settings.IMPLEMENTED:
            s[key] = True
        return s

    def test_the_draft_greens_the_pending_column_of_the_inverse_form_and_mapped_generator_tiles(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_generator=[None, None, None]).cells}
        assert all(cells[f"cell:inverse_form:{i}:draft"].pending and cells[f"cell:inverse_form:{i}:draft"].text == "" for i in range(2))
        assert all(cells[f"cell:selfmap:{i}:draft"].pending and cells[f"cell:selfmap:{i}:draft"].text == "" for i in range(2))
        assert cells["units_row:generators:2"].pending and not cells["units_row:generators:1"].pending
        assert abs(cells["cell:inverse_form:0:draft"].x - cells["generator:pending"].x) < 0.5
        assert abs(cells["cell:selfmap:0:draft"].x - cells["generator:pending"].x) < 0.5
        assert abs(cells["units_row:generators:2"].x - cells["generator:pending"].x) < 0.5

    def test_the_draft_also_greens_the_derived_mapping_and_canonical_rows_it_creates(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = spreadsheet.build(base, s)
        drafting = spreadsheet.build(base, s, pending_generator=[None, None, None])
        cells = {c.id: c for c in drafting.cells}
        assert all(cells[f"cell:mapping:2:{p}"].pending and cells[f"cell:mapping:2:{p}"].text == "" for p in range(3))
        assert all(cells[f"cell:canonical:2:{p}"].pending and cells[f"cell:canonical:2:{p}"].text == "" for p in range(3))
        assert cells["cell:mapped:2:0"].pending
        assert drafting.height > plain.height, "the new generator is also a new row, so the band grows like the mapping-row draft"
        assert "map_minus:pending" not in cells, "the generator ratio is entered in the generators column, so the mapping row is a derived placeholder, not an editable input"

    def test_without_a_draft_those_tiles_carry_no_pending_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ids = {c.id for c in spreadsheet.build(base, self._all_on()).cells}
        assert "cell:inverse_form:0:draft" not in ids
        assert "cell:selfmap:0:draft" not in ids
        assert "units_row:generators:2" not in ids

    def test_a_row_draft_also_greens_the_new_generators_derived_columns_and_a_canonical_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_mapping_row=[None, None, None]).cells}
        assert all(cells[f"cell:embed:{i}:draft"].pending for i in range(3))
        assert all(cells[f"cell:inverse_form:{i}:draft"].pending for i in range(2))
        assert all(cells[f"cell:selfmap:{i}:draft"].pending for i in range(2))
        assert cells["tuning:generator:pending"].pending
        assert all(cells[f"cell:canonical:2:{p}"].pending and cells[f"cell:canonical:2:{p}"].text == "" for p in range(3))


class TestPendingElementDraft:
    @staticmethod
    def _all_on():
        s = settings.defaults()
        for key in settings.IMPLEMENTED:
            s[key] = True
        return s

    def test_the_draft_grows_both_square_matrices_with_a_pending_row_and_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, self._all_on(), pending_element="7").cells}
        for prefix in ("cell:vector:primes", "cell:projection"):
            assert all(cells[f"{prefix}:{i}:draft"].pending and cells[f"{prefix}:{i}:draft"].text == "" for i in range(3))
            assert all(cells[f"{prefix}:3:{k}"].pending and cells[f"{prefix}:3:{k}"].text == "" for k in range(3))
            assert cells[f"{prefix}:3:draft"].pending and cells[f"{prefix}:3:draft"].text == ""

    def test_the_new_prime_row_gets_its_own_bracket_and_the_fit_brackets_grow(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = {c.id: c for c in spreadsheet.build(base, s).cells}
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_element="7").cells}
        assert "bracket:vector:primes:3:l" in drafting and "bracket:vector:primes:3:l" not in plain
        assert "bracket:projection:3:l" in drafting and "bracket:projection:3:l" not in plain
        for fit in ("bracket:embed:l", "bracket:vector:targets:l", "bracket:projection_targets:l"):
            assert drafting[fit].height == plain[fit].height + spreadsheet_constants.ROW_HEIGHT

    def test_the_draft_grows_the_vectors_and_projection_bands_each_by_one_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = self._all_on()
        plain = spreadsheet.build(base, s)
        drafting = spreadsheet.build(base, s, pending_element="7")
        assert drafting.height - plain.height == 2 * spreadsheet_constants.ROW_HEIGHT

    def test_without_a_draft_the_square_matrices_carry_no_pending_row_or_column(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        ids = {c.id for c in spreadsheet.build(base, self._all_on()).cells}
        assert "cell:vector:primes:3:0" not in ids and "cell:vector:primes:0:3" not in ids
        assert "cell:projection:3:0" not in ids


class TestPendingMappingRow:
    def test_a_partly_typed_pending_mapping_row_shows_its_entered_components(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[0, None, 1]).cells}
        assert cells["cell:mapping:2:0"].text == "0"
        assert cells["cell:mapping:2:1"].text == ""
        assert cells["cell:mapping:2:2"].text == "1"
        assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))

    def test_a_pending_mapping_row_grows_only_the_mapping_band_by_one_row(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = spreadsheet.build(base)
        drafting = spreadsheet.build(base, pending_mapping_row=[None, None, None])
        assert drafting.height - plain.height == spreadsheet_constants.ROW_HEIGHT

    def test_the_mapping_plain_text_becomes_a_two_tone_draft_field_while_a_row_is_pending(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["plain_text_values"] = True
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_mapping_row=[None, None, None]).cells}
        assert drafting["plain_text:mapping:primes"].kind == "plain_text_pending"
        assert drafting["plain_text:vectors:commas"].kind == "plain_text_edit"
        resting = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert resting["plain_text:mapping:primes"].kind == "plain_text_edit"

    def test_the_mapped_list_brackets_grow_to_enclose_the_draft_rows_placeholders(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = {c.id: c for c in spreadsheet.build(base).cells}
        drafting = {c.id: c for c in spreadsheet.build(base, pending_mapping_row=[None, None, None]).cells}
        for bid in ("bracket:mapped:l", "bracket:mapped_comma:l"):
            assert drafting[bid].height == plain[bid].height + spreadsheet_constants.ROW_HEIGHT
        assert drafting["cell:mapped:2:0"].pending and drafting["cell:mapped:2:0"].text == ""
        assert drafting["cell:mapped_comma:2:0"].preview_remove and not drafting["cell:mapped_comma:2:0"].pending, "...but its cell over the doomed comma is red (the draft generator un-tempers it away), enclosed all the same"

    def test_a_comma_minus_hover_fills_the_born_generator_rows_derived_cells(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("comma", 0)).cells}
        assert [cells[f"cell:mapping:2:{p}"].text for p in range(3)] == ["0", "0", "1"]
        assert all(f"cell:mapped:2:{j}" in cells and cells[f"cell:mapped:2:{j}"].text != "" for j in range(2))

    def test_a_comma_minus_hover_ambers_the_surviving_mapping_rows_as_preview_change(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("comma", 0)).cells}
        for row in (0, 1):
            for p in range(3):
                cell = cells[f"cell:mapping:{row}:{p}"]
                assert cell.preview_change and not cell.preview_remove and not cell.pending
        assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))
        assert not any(cells[f"cell:mapping:2:{p}"].preview_change for p in range(3))
        assert cells["cell:comma:0:0"].preview_remove

    def test_a_mapping_minus_hover_fills_the_born_commas_derived_cells(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, preview_remove=("row", 0)).cells}
        assert [cells[f"cell:comma:{p}:1"].text for p in range(3)] == ["0", "-4", "1"]
        assert cells["tuning:comma:draft"].text == "0.000"
        assert (cells["just:comma:draft"].text.lstrip("-")
                == cells["retune:comma:draft"].text.lstrip("-") != "0.000")
        assert cells["cell:mapped_comma:1:1"].text == "0"
        assert cells["cell:mapped_comma:0:1"].preview_remove

    def test_a_mapping_minus_hover_fills_the_born_commas_projection_and_complexity_rows(self):
        s = settings.defaults(); s["weighting"], s["projection"] = True, True
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        cells = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S", preview_remove=("row", 0)).cells}
        assert cells["cell:scaling:draft"].text == "0"
        assert [cells[f"cell:projection_vectors:{p}:draft"].text for p in range(3)] == ["0", "0", "0"]
        pre = [cells[f"cell:prescaling:commas:{i}:draft"].text for i in range(3)]
        assert pre[0] == "0" and pre != ["", "", ""], "filled, not blank"
        assert cells["complexity:comma:draft"].text not in ("", "<MISSING>")
        assert cells["complexity:comma:draft"].pending
        assert all(cells[f"cell:prescaling:commas:{i}:draft"].pending for i in range(3))

    def test_a_comma_minus_hover_in_projection_births_an_unchanged_interval(self):
        s = settings.defaults(); s["projection"] = True
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plain = {c.id: c for c in spreadsheet.build(base, s).cells}
        hovered = {c.id: c for c in spreadsheet.build(base, s, preview_remove=("comma", 0)).cells}
        base_nu = sum(1 for i in plain if i.startswith("cell:unchanged:0:"))
        hov_nu = sum(1 for i in hovered if i.startswith("cell:unchanged:0:"))
        assert hov_nu == base_nu + 1
        born = hov_nu - 1
        assert [hovered[f"cell:unchanged:{p}:{born}"].text for p in range(3)] == ["0", "0", "1"]
        assert all(hovered[f"cell:unchanged:{p}:{born}"].pending for p in range(3))
        assert not any(hovered[f"cell:unchanged:{p}:0"].pending for p in range(3))
