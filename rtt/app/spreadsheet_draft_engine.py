from __future__ import annotations

import collections

from rtt.app.layout import Cell
from rtt.app.spreadsheet_constants import COLUMN_WIDTH, ROW_HEIGHT
from rtt.app.spreadsheet_tile_axes import FIXED, REGISTRY

_ROWKEY = "draft"
_COLKEY = "draft"


def _split(cell_id):
    parts = cell_id.split(":")
    if len(parts) < 3:
        return None
    return ":".join(parts[:-2]), parts[-2], parts[-1]


class _TileCells:
    def __init__(self):
        self.by_row = collections.OrderedDict()
        self.by_col = collections.OrderedDict()
        self.cells = []

    def add(self, rowkey, colkey, cell):
        self.cells.append(cell)
        self.by_row.setdefault(rowkey, cell)
        self.by_col.setdefault(colkey, cell)


def _index(committed_cells):
    tiles = {t.prefix: t for t in REGISTRY}
    grouped = collections.defaultdict(_TileCells)
    for cell in committed_cells:
        if cell.pending:
            continue
        split = _split(cell.id)
        if split is None:
            continue
        prefix, rowkey, colkey = split
        if prefix in tiles:
            grouped[prefix].add(rowkey, colkey, cell)
    return tiles, grouped


def _new_row(prefix, group, pending):
    ys = [c.y for c in group.cells]
    new_y = max(ys) + ROW_HEIGHT
    out = []
    for colkey, sample in group.by_col.items():
        out.append(Cell(f"{prefix}:{_ROWKEY}:{colkey}", sample.x, new_y, COLUMN_WIDTH,
                        ROW_HEIGHT, "mapped", text="", pending=pending))
    return out


def _new_col(prefix, group, pending):
    xs = [c.x for c in group.cells]
    new_x = max(xs) + COLUMN_WIDTH
    out = []
    for rowkey, sample in group.by_row.items():
        out.append(Cell(f"{prefix}:{rowkey}:{_COLKEY}", new_x, sample.y, COLUMN_WIDTH,
                        ROW_HEIGHT, "mapped", text="", pending=pending))
    return out


def growth_cells(committed_cells, axis, *, pending=True):
    tiles, grouped = _index(committed_cells)
    out = []
    for prefix, group in grouped.items():
        tile = tiles[prefix]
        if tile.rows == axis and tile.rows is not FIXED:
            out.extend(_new_row(prefix, group, pending))
        if tile.cols == axis and tile.cols is not FIXED:
            out.extend(_new_col(prefix, group, pending))
        if tile.rows == axis and tile.cols == axis and tile.rows is not FIXED:
            xs = [c.x for c in group.cells]
            ys = [c.y for c in group.cells]
            out.append(Cell(f"{prefix}:{_ROWKEY}:{_COLKEY}", max(xs) + COLUMN_WIDTH,
                            max(ys) + ROW_HEIGHT, COLUMN_WIDTH, ROW_HEIGHT, "mapped",
                            text="", pending=pending))
    return out


def touched_tiles(committed_cells, axis):
    tiles, grouped = _index(committed_cells)
    return {prefix for prefix, _ in grouped.items()
            if tiles[prefix].rows == axis or tiles[prefix].cols == axis}
