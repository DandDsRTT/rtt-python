import pytest

from rtt.app import editor_codec, service, settings, spreadsheet, spreadsheet_layout, tooltips
from rtt.app.editor import Editor
from rtt.app.editor_settings_ops import reordered_before
from rtt.app.grid_tables import NATURAL_COLUMN_KEYS, NATURAL_ROW_KEYS
from rtt.app.spreadsheet_constants import GRIP_BAND, TRUNK_GRIP_BAND

_MEANTONE = ((1, 1, 0), (0, 1, 4))


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def _layout(over=None, **inputs):
    return spreadsheet.build(service.from_mapping(_MEANTONE), {**_all_on(), **(over or {})}, **inputs)


def _grips(layout, kind):
    return {c.id.split(":", 1)[1]: c for c in layout.cells if c.kind == kind}


def _kinds(layout):
    return {c.kind for c in layout.cells}


def _order_before(natural_keys, src, before):
    return reordered_before(natural_keys, natural_keys, src, before)


class TestBandGripsRideTheTrunks:
    def test_reorder_grips_defaults_on_and_gates_the_whole_row_and_column_grips(self):
        assert settings.defaults()["reorder_grips"] is True
        assert {"rowgrip", "columngrip"} <= _kinds(_layout(settings.defaults()))
        assert not ({"rowgrip", "columngrip"} & _kinds(_layout({"reorder_grips": False})))

    def test_every_shown_row_and_column_carries_exactly_one_band_grip(self):
        layout = _layout()
        labels = {c.id.split(":", 1)[1] for c in layout.cells if c.kind == "row_label"}
        headers = {c.id.split(":", 1)[1] for c in layout.cells if c.kind == "column_header"}
        assert set(_grips(layout, "rowgrip")) == labels
        assert set(_grips(layout, "columngrip")) == headers

    def test_a_collapsed_row_or_column_keeps_its_grip_so_it_can_still_be_moved(self):
        layout = _layout(collapsed=frozenset({"row:mapping", "column:primes"}))
        assert "mapping" in _grips(layout, "rowgrip")
        assert "primes" in _grips(layout, "columngrip")

    def test_each_column_grip_rides_its_own_columns_trunk_gridline(self):
        layout = _layout()
        trunks = {line.id: line for line in layout.lines if line.orientation == "v"}
        for key, grip in _grips(layout, "columngrip").items():
            trunk = trunks[f"trunk:{key}"]
            assert trunk.position == pytest.approx(grip.x + grip.width / 2)
            assert trunk.start <= grip.y and grip.y + grip.height <= trunk.start + trunk.length

    def test_each_row_grip_rides_its_own_rows_trunk_gridline(self):
        layout = _layout()
        rules = [line for line in layout.lines if line.orientation == "h"]
        for key, grip in _grips(layout, "rowgrip").items():
            trunk = next(line for line in rules if line.id in (f"trunk:{key}", f"h:{key}"))
            assert trunk.position == pytest.approx(grip.y + grip.height / 2)
            assert trunk.start <= grip.x and grip.x + grip.width <= trunk.start + trunk.length

    def test_the_trunks_reserve_a_grip_band_that_the_frozen_seams_absorb(self):
        layout = _layout()
        assert TRUNK_GRIP_BAND >= GRIP_BAND
        for grip in _grips(layout, "columngrip").values():
            assert grip.y + grip.height <= layout.freeze_y
        for grip in _grips(layout, "rowgrip").values():
            assert grip.x + grip.width <= layout.freeze_x

    def test_each_band_grip_offers_hover_help_naming_the_gesture(self):
        assert "column" in tooltips.control_help("columngrip", "columngrip:commas")
        assert "row" in tooltips.control_help("rowgrip", "rowgrip:mapping")

    def test_the_generator_subcolumn_grip_help_names_reordering_generators(self):
        generators = tooltips.control_help("subcolumngrip", "grip:generators:0")
        intervals = tooltips.control_help("subcolumngrip", "grip:commas:0")
        assert "generator" in generators and "reorder" in generators
        assert generators != intervals

    def test_no_band_grip_collides_with_its_fold_toggle(self):
        layout = _layout()
        cells = {c.id: c for c in layout.cells}
        for key, grip in _grips(layout, "columngrip").items():
            assert cells[f"toggle:column:{key}"].y + cells[f"toggle:column:{key}"].height <= grip.y
        for key, grip in _grips(layout, "rowgrip").items():
            assert cells[f"toggle:row:{key}"].x + cells[f"toggle:row:{key}"].width <= grip.x


def _subrow_grips(layout):
    return {c.generator: c for c in layout.cells if c.kind == "subrowgrip"}


def _generator_cells(layout):
    return {c.generator: c for c in layout.cells
            if c.kind == "generator_ratio" and not getattr(c, "pending", False)}


class TestSubrowGripsRideEachSubrowGridline:
    def test_reorder_grips_gates_the_subrow_grips(self):
        assert "subrowgrip" in _kinds(_layout())
        assert "subrowgrip" not in _kinds(_layout({"reorder_grips": False}))

    def test_the_mapping_band_carries_one_subrow_grip_per_generator(self):
        assert set(_grips(_layout(), "subrowgrip")) == {"generators:0", "generators:1"}

    def test_each_subrow_grip_rides_its_own_generator_rows_gridline(self):
        layout = _layout()
        gens = _generator_cells(layout)
        for i, grip in _subrow_grips(layout).items():
            assert grip.y == gens[i].y

    def test_each_subrow_grip_sits_on_the_frozen_side_of_the_row_header(self):
        layout = _layout()
        gens = _generator_cells(layout)
        for i, grip in _subrow_grips(layout).items():
            assert grip.x + grip.width <= layout.freeze_x
            assert grip.x + grip.width <= gens[i].x

    def test_a_subrow_grip_stands_taller_than_wide_like_a_row_handle(self):
        for grip in _subrow_grips(_layout()).values():
            assert grip.height > grip.width

    def test_a_rank_one_temperament_shows_no_subrow_grips(self):
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0),)), _all_on())
        assert not _subrow_grips(layout)

    def test_a_collapsed_mapping_band_drops_its_subrow_grips(self):
        layout = _layout(collapsed=frozenset({"row:mapping"}))
        assert not _subrow_grips(layout)

    def test_hiding_the_generator_ratio_tile_keeps_the_subrow_grips(self):
        layout = _layout(collapsed=frozenset({"tile:mapping:quantities"}))
        assert set(_grips(layout, "subrowgrip")) == {"generators:0", "generators:1"}

    def test_the_subrow_grip_help_names_reordering_generators(self):
        help_text = tooltips.control_help("subrowgrip", "subrowgrip:generators:0")
        assert "generator" in help_text and "reorder" in help_text


def _nonstandard_layout(over=None):
    return spreadsheet.build(service.from_mapping(_MEANTONE),
                             {**_all_on(), "nonstandard_domain": True, **(over or {})},
                             tuning_scheme="minimax-S")


def _prime_subrow_grips(layout):
    return [c for c in layout.cells
            if c.kind == "element_reorder" and c.id.count(":") == 2]


def _prime_grip_bands(layout):
    return {c.id.split(":")[1] for c in _prime_subrow_grips(layout)}


class TestPrimeSubrowGripsRideTheElementBands:
    def test_vectors_projection_and_prescaling_each_carry_a_grip_per_element(self):
        layout = _nonstandard_layout()
        assert _prime_grip_bands(layout) == {"vectors", "projection", "prescaling"}
        for band in ("vectors", "projection", "prescaling"):
            band_grips = [c for c in _prime_subrow_grips(layout) if c.id.split(":")[1] == band]
            assert {c.prime for c in band_grips} == {0, 1, 2}

    def test_a_standard_prime_limit_domain_shows_no_prime_subrow_grips(self):
        assert not _prime_subrow_grips(spreadsheet.build(service.from_mapping(_MEANTONE), settings.defaults()))

    def test_prime_subrow_grips_gate_on_reorder_grips(self):
        assert not _prime_subrow_grips(_nonstandard_layout({"reorder_grips": False}))

    def test_each_prime_subrow_grip_sits_on_the_frozen_side_of_the_row_header(self):
        layout = _nonstandard_layout()
        for grip in _prime_subrow_grips(layout):
            assert grip.x + grip.width <= layout.freeze_x

    def test_each_prime_subrow_grip_rides_its_bands_element_gridline(self):
        layout = _nonstandard_layout()
        vecs = {c.prime: c for c in layout.cells if c.kind in ("element_ratio", "element_cell")}
        for grip in (c for c in _prime_subrow_grips(layout) if c.id.split(":")[1] == "vectors"):
            assert grip.y == vecs[grip.prime].y

    def test_a_prime_subrow_grip_stands_taller_than_wide_like_a_row_handle(self):
        grips = _prime_subrow_grips(_nonstandard_layout())
        assert grips and all(c.height > c.width for c in grips)


class TestBandOrderDrivesTheLayout:
    def test_a_band_key_missing_from_the_natural_order_fails_the_build(self):
        with pytest.raises(KeyError):
            spreadsheet_layout._in_band_order((("unlisted", 1, True),), NATURAL_ROW_KEYS, ())

    def test_every_shown_band_key_is_declared_in_the_natural_order(self):
        layout = _layout()
        rows = {c.id.split(":", 1)[1] for c in layout.cells if c.kind == "row_label"}
        columns = {c.id.split(":", 1)[1] for c in layout.cells if c.kind == "column_header"}
        assert rows <= set(NATURAL_ROW_KEYS) and columns <= set(NATURAL_COLUMN_KEYS)

    def test_an_empty_order_lays_the_bands_out_in_their_natural_sequence(self):
        assert spreadsheet_layout.ordered_keys(NATURAL_ROW_KEYS, ()) == NATURAL_ROW_KEYS

    def test_an_order_missing_a_key_parks_that_key_after_the_ones_it_names(self):
        order = tuple(k for k in NATURAL_ROW_KEYS if k != "counts")
        assert spreadsheet_layout.ordered_keys(NATURAL_ROW_KEYS, order) == (*order, "counts")

    def test_moving_a_column_reorders_the_columns_left_to_right(self):
        natural = {c.id.split(":", 1)[1]: c.x for c in _layout().cells if c.kind == "column_header"}
        assert natural["primes"] < natural["commas"]
        moved = _order_before(NATURAL_COLUMN_KEYS, "commas", "primes")
        xs = {c.id.split(":", 1)[1]: c.x for c in _layout(column_order=moved).cells if c.kind == "column_header"}
        assert xs["commas"] < xs["primes"]
        assert xs["generators"] < xs["commas"]

    def test_moving_a_row_reorders_the_rows_top_to_bottom(self):
        natural = {c.id.split(":", 1)[1]: c.y for c in _layout().cells if c.kind == "row_label"}
        assert natural["vectors"] < natural["mapping"]
        moved = _order_before(NATURAL_ROW_KEYS, "mapping", "vectors")
        ys = {c.id.split(":", 1)[1]: c.y for c in _layout(row_order=moved).cells if c.kind == "row_label"}
        assert ys["mapping"] < ys["vectors"]


class TestBandReorderCommands:
    def test_moving_a_row_onto_another_lands_it_in_that_rows_slot(self):
        editor = Editor()
        assert editor.move_row("mapping", "vectors") is True
        assert editor.row_order.index("mapping") < editor.row_order.index("vectors")

    def test_moving_a_column_onto_another_lands_it_in_that_columns_slot(self):
        editor = Editor()
        assert editor.move_column("commas", "primes") is True
        assert editor.column_order.index("commas") < editor.column_order.index("primes")

    def test_dropping_a_band_on_itself_changes_nothing(self):
        editor = Editor()
        assert editor.move_row("mapping", "mapping") is False
        assert editor.move_column("commas", "commas") is False
        assert editor.row_order == () and editor.column_order == ()

    def test_dropping_a_band_on_an_unknown_key_changes_nothing(self):
        editor = Editor()
        assert editor.move_row("mapping", "commas") is False
        assert editor.row_order == ()

    def test_a_band_move_is_undoable(self):
        editor = Editor()
        editor.move_column("commas", "primes")
        moved = editor.column_order
        editor.undo()
        assert editor.column_order == () and moved != ()
        editor.redo()
        assert editor.column_order == moved

    def test_a_move_seats_the_band_immediately_before_its_target(self):
        editor = Editor()
        editor.move_row("mapping", "counts")
        assert editor.row_order[:2] == ("mapping", "counts")

    def test_a_none_target_appends_the_band_to_the_end(self):
        editor = Editor()
        editor.move_column("commas", None)
        assert editor.column_order[-1] == "commas"

    def test_moving_a_band_twice_composes_from_the_order_already_chosen(self):
        editor = Editor()
        editor.move_row("mapping", "counts")
        editor.move_row("damage", "counts")
        assert editor.row_order[:3] == ("mapping", "damage", "counts")


class TestBandOrderPersistence:
    def test_the_band_orders_round_trip_through_the_shared_document(self):
        editor = Editor()
        editor.move_row("mapping", "vectors")
        editor.move_column("commas", "primes")
        restored = editor_codec.load(editor_codec.serialize(editor))
        assert restored.grid_view.row_order == editor.row_order
        assert restored.grid_view.column_order == editor.column_order

    def test_a_natural_order_stays_empty_across_the_round_trip(self):
        view = editor_codec.load(editor_codec.serialize(Editor())).grid_view
        assert view.row_order == () and view.column_order == ()

    def test_an_order_naming_unknown_keys_lays_out_the_bands_it_does_know(self):
        assert spreadsheet_layout.ordered_keys(NATURAL_ROW_KEYS, ("mapping", "bogus")) == (
            "mapping", *(k for k in NATURAL_ROW_KEYS if k != "mapping"))

    def test_a_repeated_key_is_honoured_once_at_its_first_mention(self):
        order = ("mapping", "counts", "mapping")
        assert spreadsheet_layout.ordered_keys(NATURAL_ROW_KEYS, order)[:2] == ("mapping", "counts")

    def test_a_shared_url_carrying_junk_band_orders_still_builds(self):
        layout = _layout(row_order=("bogus", "mapping"), column_order=("bogus",))
        assert {c.kind for c in layout.cells} >= {"row_label", "column_header"}
