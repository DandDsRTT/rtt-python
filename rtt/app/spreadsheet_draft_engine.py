from __future__ import annotations

import collections

from rtt.app.layout import Cell
from rtt.app.spreadsheet_constants import COLUMN_WIDTH, ROW_HEIGHT
from rtt.app.spreadsheet_tile_axes import (
    CANONICAL_GENERATORS,
    COMMAS,
    DETEMPERING,
    FIXED,
    GENERATORS,
    HELD,
    INTEREST,
    PRIMES,
    REGISTRY,
    TARGETS,
    UNCHANGED,
)

_COLKEY = "draft"

_GENERATOR_AXES = (GENERATORS, CANONICAL_GENERATORS, DETEMPERING, UNCHANGED)


def drafted_axes(resolved):
    scalars = resolved.scalars
    row_add = scalars.row_draft and not resolved.ghosts.row
    axes = []
    if scalars.generator_draft or row_add:
        axes.extend(_GENERATOR_AXES)
    if scalars.element_draft:
        axes.append(PRIMES)
    if scalars.comma_draft and resolved.commas.pending is not None:
        axes.append(COMMAS)
    if resolved.targets.pending is not None:
        axes.append(TARGETS)
    if resolved.held.pending is not None:
        axes.append(HELD)
    if resolved.interest.pending is not None:
        axes.append(INTEREST)
    return tuple(axes)


def _split(cell_id):
    parts = cell_id.split(":")
    if len(parts) < 3:
        return None
    prefix, rowkey, colkey = ":".join(parts[:-2]), parts[-2], parts[-1]
    if not (rowkey.isdigit() and colkey.isdigit()):
        return None
    return prefix, int(rowkey), int(colkey)


def _index(committed_cells):
    tiles = {t.prefix: t for t in REGISTRY}
    grids = collections.defaultdict(dict)
    for cell in committed_cells:
        if cell.pending:
            continue
        split = _split(cell.id)
        if split is None:
            continue
        prefix, i, j = split
        if prefix in tiles:
            grids[prefix][(i, j)] = cell
    return tiles, grids


def _step_along(grid, index_pos):
    for (i, j), c in grid.items():
        nxt = (i + 1, j) if index_pos == 0 else (i, j + 1)
        if nxt in grid:
            o = grid[nxt]
            if abs(o.x - c.x) >= abs(o.y - c.y):
                return (COLUMN_WIDTH, 0.0)
            return (0.0, ROW_HEIGHT)
    return None


def _orientation(grid):
    i_step = _step_along(grid, 0)
    j_step = _step_along(grid, 1)
    if i_step is None and j_step is None:
        return (0.0, ROW_HEIGHT), (COLUMN_WIDTH, 0.0)
    if i_step is None:
        i_step = (COLUMN_WIDTH, 0.0) if j_step == (0.0, ROW_HEIGHT) else (0.0, ROW_HEIGHT)
    if j_step is None:
        j_step = (COLUMN_WIDTH, 0.0) if i_step == (0.0, ROW_HEIGHT) else (0.0, ROW_HEIGHT)
    return i_step, j_step


def _cell(prefix, i, j, base, step, pending):
    colkey = _COLKEY if isinstance(j, str) else j
    return Cell(f"{prefix}:{i}:{colkey}", base.x + step[0], base.y + step[1],
                COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", pending=pending)


def growth_cells(committed_cells, axis, *, pending=True):
    tiles, grids = _index(committed_cells)
    out = []
    for prefix, grid in grids.items():
        tile = tiles[prefix]
        grows_i = tile.rows == axis and tile.rows is not FIXED
        grows_j = tile.cols == axis and tile.cols is not FIXED
        if not (grows_i or grows_j):
            continue
        i_step, j_step = _orientation(grid)
        max_i = max(i for i, _ in grid)
        max_j = max(j for _, j in grid)
        new_i = max_i + 1
        if grows_i:
            for j in sorted({j for _, j in grid}):
                if (max_i, j) in grid:
                    out.append(_cell(prefix, new_i, j, grid[(max_i, j)], i_step, pending))
        if grows_j:
            for i in sorted({i for i, _ in grid}):
                if (i, max_j) in grid:
                    out.append(_cell(prefix, i, _COLKEY, grid[(i, max_j)], j_step, pending))
        if grows_i and grows_j and (max_i, max_j) in grid:
            corner_base = grid[(max_i, max_j)]
            out.append(Cell(f"{prefix}:{new_i}:{_COLKEY}",
                            corner_base.x + i_step[0] + j_step[0],
                            corner_base.y + i_step[1] + j_step[1],
                            COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", pending=pending))
    return out


def touched_tiles(committed_cells, axis):
    tiles, grids = _index(committed_cells)
    return {prefix for prefix, _ in grids.items()
            if tiles[prefix].rows == axis or tiles[prefix].cols == axis}


def _pos(cell):
    return (round(cell.x, 1), round(cell.y, 1))


def _is_blank_placeholder(cell):
    return (cell.pending and cell.text == "" and cell.kind == "mapped"
            and cell.id.startswith("cell:"))


def apply_draft_engine(resolved, cells):
    axes = drafted_axes(resolved)
    if not axes:
        return cells
    engine = {}
    for axis in axes:
        for cell in growth_cells(cells, axis):
            engine.setdefault(_pos(cell), cell)
    kept = [c for c in cells
            if not (_is_blank_placeholder(c) and _pos(c) in engine)]
    kept_positions = {_pos(c) for c in kept}
    kept_ids = {c.id for c in kept}
    added = [cell for pos, cell in engine.items()
             if pos not in kept_positions and cell.id not in kept_ids]
    return kept + added
