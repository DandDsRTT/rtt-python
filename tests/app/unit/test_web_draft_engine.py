import collections

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

_GENERATOR_FAMILY = (GENERATORS, CANONICAL_GENERATORS, DETEMPERING, UNCHANGED)


def _all_on():
    s = settings.defaults()
    for k in settings.IMPLEMENTED:
        s[k] = True
    return s


def _committed():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    return spreadsheet.build(base, _all_on(), held_vectors=[(-1, 1, 0)], interest=((-2, 0, 1),)).cells


def _draft(**inputs):
    base = service.from_mapping(((1, 1, 0, -1), (0, 1, 4, 10)))
    return spreadsheet.build(base, _all_on(), held_vectors=[(-1, 1, 0)],
                             interest=((-2, 0, 1),), **inputs).cells


def _green_prefixes(cells):
    out = set()
    for c in cells:
        if c.pending and c.id.startswith("cell:"):
            out.add(":".join(c.id.split(":")[:-2]))
    return out


def _present_prefixes(cells):
    return {":".join(c.id.split(":")[:-2]) for c in cells
            if not c.pending and c.id.startswith("cell:")}


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


class TestDraftIntegrationCoverage:
    _CASES = (
        ("generator", _GENERATOR_FAMILY, dict(pending_generator=(0, 0, 1, 0))),
        ("mapping_row", _GENERATOR_FAMILY, dict(pending_mapping_row=(0, 0, 1, 0))),
        ("element", (PRIMES,), dict(pending_element="5")),
        ("comma", (COMMAS,), dict(pending_comma="81/80")),
        ("target", (TARGETS,), dict(pending_target=[None, None, None, None])),
        ("held", (HELD,), dict(pending_held=[None, None, None, None])),
        ("interest", (INTEREST,), dict(pending_interest=[None, None, None, None])),
    )

    def test_every_tile_on_a_grown_axis_shows_green_for_each_add_draft(self):
        for label, axes, inputs in self._CASES:
            cells = _draft(**inputs)
            green = _green_prefixes(cells)
            present = _present_prefixes(cells)
            expected = {t.prefix for t in REGISTRY
                        if any(a in (t.rows, t.cols) for a in axes) and t.prefix in present}
            missing = expected - green
            assert not missing, f"{label} draft misses greens on {sorted(missing)}"

    def test_no_two_grid_cells_share_a_position_during_a_draft(self):
        for label, _axes, inputs in self._CASES:
            cells = _draft(**inputs)
            pos = collections.defaultdict(list)
            for c in cells:
                if c.id.startswith("cell:"):
                    pos[(round(c.x, 1), round(c.y, 1))].append(c.id)
            collisions = {k: v for k, v in pos.items() if len(v) > 1}
            assert not collisions, f"{label} draft overlaps cells: {collisions}"
