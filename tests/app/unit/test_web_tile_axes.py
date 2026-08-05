import re

from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_tile_axes import FIXED, MATRIX_TILES, REGISTRY

_ANCHOR = {
    "generators": ("cell:mapping", 0),
    "primes": ("cell:mapping", 1),
    "canonical_generators": ("cell:canonical", 0),
    "commas": ("cell:comma", 1),
    "targets": ("cell:mapped", 1),
    "held": ("cell:hmapped", 1),
    "interest": ("cell:imapped", 1),
    "detempering": ("cell:mapped_detempering", 1),
    "unchanged": ("cell:mapped_unchanged", 1),
}

_CASES = {
    "r2d3": ((1, 1, 0), (0, 1, 4)),
    "r3d3": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "r2d4": ((1, 1, 0, -1), (0, 1, 4, 10)),
    "r1d3": ((1, 1, 0),),
}


def _sizes(mapping):
    s = settings.defaults()
    for k in settings.IMPLEMENTED:
        s[k] = True
    cells = spreadsheet.build(service.from_mapping(mapping), s,
                              held_vectors=[(-1, 1, 0)], interest=((-2, 0, 1),)).cells
    sizes = {}
    for c in cells:
        m = re.match(r"^(cell:[a-z_]+(?::[a-z_]+)?):(\d+):(\d+)$", c.id)
        if m:
            pre, i, j = m.group(1), int(m.group(2)), int(m.group(3))
            r = sizes.setdefault(pre, [0, 0])
            r[0], r[1] = max(r[0], i + 1), max(r[1], j + 1)
    return sizes


def _axis_counts(sizes):
    counts = {}
    for axis, (anchor, dim) in _ANCHOR.items():
        if anchor in sizes:
            counts[axis] = sizes[anchor][dim]
    return counts


class TestTileAxisRegistry:
    def test_every_matrix_tile_matches_the_size_of_its_declared_axes(self):
        for mapping in _CASES.values():
            sizes = _sizes(mapping)
            counts = _axis_counts(sizes)
            for tile in MATRIX_TILES:
                if tile.prefix not in sizes:
                    continue
                actual_rows, actual_cols = sizes[tile.prefix]
                if tile.rows in counts:
                    assert actual_rows == counts[tile.rows], f"{tile.prefix} rows: axis {tile.rows}"
                if tile.cols in counts:
                    assert actual_cols == counts[tile.cols], f"{tile.prefix} cols: axis {tile.cols}"

    def test_the_registry_covers_every_matrix_tile_the_layout_emits(self):
        registered = {t.prefix for t in MATRIX_TILES}
        seen = set()
        for mapping in _CASES.values():
            seen |= set(_sizes(mapping))
        missing = seen - registered
        assert not missing, f"layout emits but the axis registry omits: {sorted(missing)}"

    def test_value_row_tiles_have_no_row_axis(self):
        for tile in REGISTRY:
            if tile.prefix.split(":")[0] in ("tuning", "just", "retune", "damage", "weight"):
                assert tile.rows is FIXED
