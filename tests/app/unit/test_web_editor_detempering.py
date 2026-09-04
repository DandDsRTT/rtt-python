from types import SimpleNamespace

from rtt.app import service, settings, spreadsheet
from rtt.app.editing import EditController
from rtt.app.editor import Editor
from rtt.app.spreadsheet_constants import DASH

MEANTONE_DETEMPERING = ((1, 0, 0), (-1, 1, 0))
FORTY_OVER_TWENTY_SEVEN = (3, -3, 1)
TWO_HUNDRED_FORTY_THREE_OVER_ONE_SIXTY = (-5, 5, -1)


def _shown(editor):
    editor.settings.update(generator_detempering=True, interval_vectors=True, presets=True)
    return {c.id: c for c in editor.layout().cells}


def _typed_into(editor, typed):
    reconciler = SimpleNamespace(
        cell_value=lambda _cell_id: typed,
        handles=lambda _cell_id: SimpleNamespace(value=SimpleNamespace(input=typed)),
    )
    return EditController(editor, reconciler, SimpleNamespace(),
                          SimpleNamespace(render=lambda: None, request_render=lambda after=None: None),
                          SimpleNamespace(building=False))


class TestDetemperingChoice:
    def test_the_detempering_defaults_to_the_computed_one(self):
        editor = Editor()
        assert editor.custom_detempering is None
        assert editor.detempering == MEANTONE_DETEMPERING

    def test_choosing_a_preimage_of_the_generator_replaces_that_column(self):
        editor = Editor()
        assert editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN) is True
        assert editor.detempering == ((1, 0, 0), FORTY_OVER_TWENTY_SEVEN)
        assert editor.custom_detempering == ((1, 0, 0), FORTY_OVER_TWENTY_SEVEN)

    def test_an_interval_mapping_to_two_generators_is_refused(self):
        editor = Editor()
        assert editor.set_detempering_generator(1, (0, 1, 0)) is False
        assert editor.detempering == MEANTONE_DETEMPERING
        assert editor.can_undo is False

    def test_an_interval_mapping_to_the_other_generator_is_refused(self):
        editor = Editor()
        assert editor.set_detempering_generator(1, (1, 0, 0)) is False
        assert editor.custom_detempering is None

    def test_rechoosing_the_computed_vector_drops_the_override(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        assert editor.set_detempering_generator(1, (-1, 1, 0)) is True
        assert editor.custom_detempering is None
        assert editor.detempering == MEANTONE_DETEMPERING

    def test_choosing_the_vector_already_shown_changes_nothing(self):
        editor = Editor()
        assert editor.set_detempering_generator(1, (-1, 1, 0)) is False
        assert editor.can_undo is False

    def test_the_choice_is_undoable(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        editor.undo()
        assert editor.detempering == MEANTONE_DETEMPERING

    def test_editing_the_mapping_drops_the_choice(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        editor.edit_mapping(((1, 0, -4), (0, 1, 4)))
        assert editor.custom_detempering is None

    def test_the_choice_survives_a_setting_toggle(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        editor.set_show("generator_detempering", True)
        assert editor.custom_detempering == ((1, 0, 0), FORTY_OVER_TWENTY_SEVEN)


class TestDetemperingCycle:
    def test_cycling_advances_to_the_next_most_complex_preimage(self):
        editor = Editor()
        editor.cycle_detempering_generator(1)
        assert editor.detempering[1] == FORTY_OVER_TWENTY_SEVEN
        editor.cycle_detempering_generator(1)
        assert editor.detempering[1] == TWO_HUNDRED_FORTY_THREE_OVER_ONE_SIXTY

    def test_cycling_leaves_the_other_generators_alone(self):
        editor = Editor()
        editor.cycle_detempering_generator(1)
        assert editor.detempering[0] == (1, 0, 0)

    def test_every_cycled_vector_still_maps_to_one_of_its_generator(self):
        editor = Editor()
        for _ in range(5):
            editor.cycle_detempering_generator(0)
            assert service.detempers_the_generator(editor.state.mapping, 0, editor.detempering[0])

    def test_cycling_wraps_around_to_the_simplest_preimage(self):
        editor = Editor()
        simplest = editor.detempering[1]
        seen = set()
        for _ in range(24):
            editor.cycle_detempering_generator(1)
            seen.add(editor.detempering[1])
            if editor.detempering[1] == simplest:
                break
        assert editor.detempering[1] == simplest
        assert len(seen) > 1

    def test_cycling_a_generator_the_temperament_no_longer_has_does_nothing(self):
        editor = Editor()
        editor.cycle_detempering_generator(2)
        assert editor.custom_detempering is None

    def test_just_intonation_has_nothing_to_cycle_through(self):
        editor = Editor()
        editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert editor.can_cycle_detempering is False
        editor.cycle_detempering_generator(0)
        assert editor.custom_detempering is None


class TestDetemperingEditOutcome:
    def test_a_preimage_is_accepted(self):
        editor = Editor()
        out = service.resolve_detempering_edit(editor.state, 1, "40/27")
        assert out.effect is service.Effect.ACCEPT
        assert out.value == FORTY_OVER_TWENTY_SEVEN

    def test_a_non_preimage_is_rejected_naming_its_generator(self):
        editor = Editor()
        out = service.resolve_detempering_edit(editor.state, 1, "3/1")
        assert out.effect is service.Effect.REJECT
        assert "\U0001d454₂" in out.message

    def test_an_unparseable_ratio_is_rejected(self):
        editor = Editor()
        assert service.resolve_detempering_edit(editor.state, 0, "garbage").effect is service.Effect.REJECT


class TestDetemperingCellEdit:
    def test_typing_a_preimage_into_the_cell_chooses_it(self):
        editor = Editor()
        _typed_into(editor, "40/27").vectors.on_ratio_change("detempering:1")
        assert editor.detempering[1] == FORTY_OVER_TWENTY_SEVEN

    def test_typing_the_same_ratio_back_leaves_the_detempering_alone(self):
        editor = Editor()
        _typed_into(editor, "3/2").vectors.on_ratio_change("detempering:1")
        assert editor.detempering == MEANTONE_DETEMPERING
        assert editor.can_undo is False


class TestDetemperingSerialization:
    def test_serialize_load_round_trips_a_chosen_detempering(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        restored = Editor()
        restored.load(editor.serialize())
        assert restored.custom_detempering == ((1, 0, 0), FORTY_OVER_TWENTY_SEVEN)

    def test_a_detempering_that_does_not_detemper_the_mapping_is_dropped(self):
        editor = Editor()
        data = editor.serialize()
        data["custom_detempering"] = [[1, 0, 0], [0, 1, 0]]
        restored = Editor()
        restored.load(data)
        assert restored.custom_detempering is None

    def test_a_detempering_of_the_wrong_shape_is_dropped(self):
        editor = Editor()
        data = editor.serialize()
        data["custom_detempering"] = [[1, 0, 0]]
        restored = Editor()
        restored.load(data)
        assert restored.custom_detempering is None


class TestDetemperingGrid:
    def test_the_quantities_row_shows_the_chosen_interval(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        cells = _shown(editor)
        assert cells["detempering:1"].text == "40/27"
        assert [cells[f"cell:vector:detempering:1:{p}"].text for p in range(3)] == ["3", "-3", "1"]

    def test_the_generators_column_names_the_chosen_interval_too(self):
        editor = Editor()
        editor.set_detempering_generator(1, FORTY_OVER_TWENTY_SEVEN)
        assert _shown(editor)["detempering:1"].text == "40/27"

    def test_a_cycle_button_sits_under_each_generator_column(self):
        cells = _shown(Editor())
        assert cells["detempering_cycle:0"].kind == "detempering_cycle"
        assert cells["detempering_cycle:1"].generator == 1
        assert cells["detempering_cycle:0"].x < cells["detempering_cycle:1"].x

    def test_the_cycle_buttons_share_the_comma_pickers_band(self):
        cells = _shown(Editor())
        assert cells["commapick:0"].y <= cells["detempering_cycle:0"].y < cells["commapick:0"].y + cells["commapick:0"].height

    def test_just_intonation_offers_no_cycle_button(self):
        editor = Editor()
        editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert not any(c.startswith("detempering_cycle:") for c in _shown(editor))

    def test_the_detempering_merges_into_the_leftmost_generators_column(self):
        editor = Editor()
        editor.set_interest_vectors([(1, 1, -1)])
        s = settings.defaults()
        s["generator_detempering"] = True
        s["interest"] = True
        cells = {c.id: c for c in spreadsheet.build(editor.state, s, interest=editor.interest_vectors).cells}
        assert cells["header:generators"].x < cells["header:primes"].x < cells["header:interest"].x
        assert "cell:vector:detempering:0:0" in cells

    def test_the_editable_generator_ratios_carry_an_approx_token_when_detempering_is_on(self):
        cells = _shown(Editor())
        assert cells["detempering:0"].approx and cells["detempering:0"].kind == "ratio_cell"
        off = {c.id: c for c in spreadsheet.build(Editor().state, settings.defaults()).cells}
        assert not off["quantities_generator:0"].approx


class TestGeneratorEmbeddingColumn:
    def _embedding(self):
        editor = Editor()
        editor.settings.update(projection=True, identity_objects=True, presets=True)
        return {c.id: c for c in editor.layout().cells}

    def test_the_embedding_sizes_render_as_radicals_beside_their_column(self):
        cells = self._embedding()
        assert cells["generator_embedding:0"].kind == "radical"
        assert cells["generator_embedding:0"].text == "2"
        assert cells["generator_embedding:1"].text == "4√5", "quarter-comma meantone's fifth is the fourth root of five"

    def test_the_embedding_column_labels_each_generator_in_its_units_row(self):
        editor = Editor()
        editor.settings.update(projection=True, app_units=True, tile_units=True)
        cells = {c.id: c for c in editor.layout().cells}
        assert [cells[f"units_row:generator_embedding:{i}"].text for i in range(2)] == ["/g₁", "/g₂"]

    def test_the_embedding_sizes_dash_when_the_tuning_is_not_a_rational_projection(self):
        editor = Editor()
        editor.set_generator_tuning_component(1, 700.0)
        editor.settings.update(projection=True, presets=True)
        cells = {c.id: c for c in editor.layout().cells}
        assert cells["generator_embedding:0"].text == DASH

    def test_the_embedding_column_is_absent_without_projection(self):
        editor = Editor()
        editor.settings.update(identity_objects=True)
        ids = {c.id for c in editor.layout().cells}
        assert not any(c.startswith("generator_embedding:") for c in ids)
        assert "header:generator_embedding" not in ids
