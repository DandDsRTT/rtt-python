from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_draft_engine import growth_cells, touched_tiles
from rtt.app.spreadsheet_tile_axes import (
    CANONICAL_GENERATORS,
    COMMAS,
    DETEMPERING,
    GENERATORS,
    HELD,
    INTEREST,
    PRIMES,
    REGISTRY,
    TARGETS,
    UNCHANGED,
)

_AXES = (GENERATORS, PRIMES, COMMAS, TARGETS, HELD, INTEREST,
         CANONICAL_GENERATORS, DETEMPERING, UNCHANGED)


def _committed():
    s = settings.defaults()
    for k in settings.IMPLEMENTED:
        s[k] = True
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    return spreadsheet.build(base, s, held_vectors=[(-1, 1, 0)], interest=((-2, 0, 1),)).cells


class TestDraftEngineCoverage:
    def test_growth_touches_exactly_the_registered_tiles_present_for_each_axis(self):
        cells = _committed()
        present = {":".join(c.id.split(":")[:-2]) for c in cells if not c.pending}
        for axis in _AXES:
            expected = {t.prefix for t in REGISTRY
                        if (t.rows == axis or t.cols == axis) and t.prefix in present}
            assert touched_tiles(cells, axis) == expected, f"axis {axis}"

    def test_every_growth_cell_is_a_blank_green_placeholder(self):
        cells = _committed()
        for axis in _AXES:
            green = growth_cells(cells, axis)
            assert green, f"axis {axis} produced no growth"
            assert all(c.pending and c.text == "" for c in green)

    def test_a_square_tile_grows_a_row_a_col_and_the_corner(self):
        cells = _committed()
        green = {c.id for c in growth_cells(cells, GENERATORS)}
        assert "cell:selfmap:2:0" in green
        assert "cell:selfmap:0:draft" in green
        assert "cell:selfmap:2:draft" in green
