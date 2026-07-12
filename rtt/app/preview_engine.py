from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rtt.app.spreadsheet_constants import COLUMN_WIDTH
from rtt.app.spreadsheet_text import (
    added_cell_ids,
    moved_cell_ids,
    removed_cell_ids,
    value_changed_cell_ids,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rtt.app.layout import Layout

PAINT = "paint"
REFLOW = "reflow"
HYBRID = "hybrid"

GHOST_SLOT_AXES = ("generators", "commas", "unchanged")

NO_RINGS = (frozenset(), frozenset(), frozenset())

_COLUMN_KINDS_EXEMPT = frozenset({"count", "name", "label", "subcolumngrip"})


@dataclass(frozen=True)
class PreviewPlan:
    mode: str
    added: frozenset
    changed: frozenset
    removed: frozenset
    moved: frozenset
    ghost_axes: tuple
    future: Layout


def compute_future(editor, op: Callable, baseline: Layout) -> Layout:
    token = editor.capture_for_preview()
    try:
        op()
        return editor.layout(previous_ids=baseline.identities)
    finally:
        editor.restore_for_preview(token)


def _position(layout: Layout, cell_id: str) -> tuple | None:
    for cell in layout.cells:
        if cell.id == cell_id:
            return (round(cell.x), round(cell.y))
    return None


def source_stable(current: Layout, future: Layout, source_id: str | None) -> bool:
    if source_id is None:
        return True
    return _position(current, source_id) == _position(future, source_id)


def ghost_axes_between(current: Layout, future: Layout, occupied: frozenset = frozenset()) -> tuple:
    if current.axis_counts is None or future.axis_counts is None:
        return ()
    return tuple(
        axis
        for axis in GHOST_SLOT_AXES
        if axis not in occupied
        and future.axis_counts.get(axis, 0) - current.axis_counts.get(axis, 0) == 1
    )


def plan_preview(
    current: Layout,
    future: Layout,
    source_id: str | None = None,
    occupied_axes: frozenset = frozenset(),
) -> PreviewPlan:
    added = added_cell_ids(current, future)
    changed = value_changed_cell_ids(current, future)
    removed = removed_cell_ids(current, future)
    moved = moved_cell_ids(current, future)
    if not removed and source_stable(current, future, source_id):
        return PreviewPlan(REFLOW, added, changed, removed, moved, (), future)
    ghosts = ghost_axes_between(current, future, occupied_axes) if added else ()
    mode = HYBRID if ghosts else PAINT
    return PreviewPlan(mode, added, changed, removed, moved, ghosts, future)


def _slot_aliases(cell_id: str, tokens: tuple) -> tuple:
    aliases = []
    for token in tokens:
        marker = str(token)
        parts = cell_id.split(":")
        for stand_in in ("pending", "draft"):
            if stand_in in parts:
                aliases.append(":".join(marker if part == stand_in else part for part in parts))
    return tuple(aliases)


def _new_tokens(current: Layout, future: Layout) -> tuple:
    if current.identities is None or future.identities is None:
        return ()
    fresh = []
    for axis, entries in future.identities.items():
        before = {token for token, _ in current.identities.get(axis, ())}
        fresh.extend(token for token, _ in entries if token not in before)
    return tuple(dict.fromkeys(fresh))


def graft_ghost_values(hybrid: Layout, current: Layout, future: Layout) -> Layout:
    future_cells = {cell.id: cell for cell in future.cells}
    tokens = _new_tokens(current, future)
    grafted = []
    dirty = False
    for cell in hybrid.cells:
        if cell.pending:
            donor = future_cells.get(cell.id)
            if donor is None:
                for alias in _slot_aliases(cell.id, tokens):
                    donor = future_cells.get(alias)
                    if donor is not None:
                        break
            if donor is not None and donor.text != cell.text:
                grafted.append(replace(cell, text=donor.text))
                dirty = True
                continue
        grafted.append(cell)
    if not dirty:
        return hybrid
    return replace(hybrid, cells=tuple(grafted))


def _column_positions(layout: Layout, prefix: str) -> tuple:
    xs = sorted(
        {cell.x for cell in layout.cells if cell.id.startswith(prefix) and not cell.pending}
    )
    return tuple(xs)


def _cells_in_columns(layout: Layout, ringable, xs: frozenset) -> frozenset:
    return frozenset(
        cell.id
        for cell in layout.cells
        if cell.x in xs
        and cell.width == COLUMN_WIDTH
        and cell.kind in ringable
        and cell.kind not in _COLUMN_KINDS_EXEMPT
        and not cell.pending
    )


def _cells_in_generator_rows(layout: Layout, ringable, rows: frozenset) -> frozenset:
    return frozenset(
        cell.id
        for cell in layout.cells
        if cell.generator in rows and cell.kind in ringable and not cell.pending
    )


def open_draft_rings(layout: Layout, ringable, comma_draft: bool, row_draft: bool) -> tuple:
    amber: frozenset = frozenset()
    red: frozenset = frozenset()
    counts = layout.axis_counts or {}
    if comma_draft and counts.get("generators", 0):
        rank = counts["generators"]
        red |= _cells_in_generator_rows(layout, ringable, frozenset({rank - 1}))
        amber |= _cells_in_generator_rows(layout, ringable, frozenset(range(rank - 1)))
        unchanged_xs = _column_positions(layout, "cell:mapped_unchanged:")
        if unchanged_xs:
            red |= _cells_in_columns(layout, ringable, frozenset({unchanged_xs[-1]}))
    if row_draft and counts.get("commas", 0):
        comma_xs = _column_positions(layout, "cell:mapped_comma:")
        if comma_xs:
            red |= _cells_in_columns(layout, ringable, frozenset({comma_xs[-1]}))
            amber |= _cells_in_columns(layout, ringable, frozenset(comma_xs[:-1]))
    return amber - red, red
