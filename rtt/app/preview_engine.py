from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from rtt.app import service
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

GHOST_SLOT_AXES = ("generators", "commas", "unchanged", "elements")

_ADD_GHOST_AXIS = {
    "generator_plus": "generators",
    "map_plus": "generators",
    "comma_plus": "commas",
    "plus": "elements",
    "basis_plus": "elements",
}
_ELEMENT_ADD_SOURCES = frozenset({"element_plus"})


def _source_ghosts(ghosts: tuple, source_id: str | None) -> tuple:
    if source_id in _ELEMENT_ADD_SOURCES:
        return ()
    axis = _ADD_GHOST_AXIS.get(source_id)
    if axis is not None:
        return (axis,) if axis in ghosts else ()
    return ghosts


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


def occupied_axes(editor) -> frozenset:
    occupied = set()
    if editor.pending_mapping_row is not None:
        occupied.add("generators")
    if editor.pending_comma is not None:
        occupied.add("commas")
    return frozenset(occupied)


def draft_flags(editor) -> tuple:
    return editor.pending_comma is not None, editor.pending_mapping_row is not None


_ELEMENT_REPS = ("7", "11", "13", "7/5", "5/3")


def _draft_committed(editor) -> bool:
    return (
        editor.pending_comma is None
        and editor.pending_mapping_row is None
        and editor.pending_element is None
    )


def _domain_preserved(editor, keep_dim) -> bool:
    if keep_dim is not None and editor.state.dimensionality != keep_dim:
        return False
    mapping = editor.state.mapping
    return service.is_proper_temperament(mapping) and not service.is_enfactored(mapping)


def _representative(editor, setter, candidates, keep_dim):
    for candidate in candidates:
        token = editor.capture_for_preview()
        try:
            setter(candidate)
            good = _draft_committed(editor) and _domain_preserved(editor, keep_dim)
        finally:
            editor.restore_for_preview(token)
        if good:
            return lambda value=candidate: setter(value)
    return None


_COMMA_SEEDS = ((-4, 4, -1), (7, 0, -3), (3, 4, -4), (-2, 2, -1), (2, 2, -1), (-3, 2, 1))


def _comma_candidates(dimensionality: int) -> list:
    out = []
    for seed in _COMMA_SEEDS:
        if dimensionality >= 3:
            out.append(list(seed) + [0] * (dimensionality - 3))
    for trio in itertools.combinations(range(dimensionality), 3):
        for coeffs in itertools.product((-2, -1, 1, 2), repeat=3):
            vector = [0] * dimensionality
            for index, coeff in zip(trio, coeffs, strict=True):
                vector[index] = coeff
            out.append(vector)
    for i in range(dimensionality):
        for j in range(i + 1, dimensionality):
            for a, b in ((-4, 4), (4, -4), (2, -1), (-1, 2)):
                vector = [0] * dimensionality
                vector[i], vector[j] = a, b
                out.append(vector)
    return out


def _row_candidates(dimensionality: int) -> list:
    rows = [[1 if k == i else 0 for k in range(dimensionality)] for i in range(dimensionality)]
    rows.append(list(range(1, dimensionality + 1)))
    return rows


def draft_op(editor):
    if editor.pending_element is not None:
        return _representative(editor, editor.set_pending_element, _ELEMENT_REPS, None)
    if editor.pending_mapping_row is not None:
        dimensionality = editor.state.dimensionality
        return _representative(
            editor, editor.set_pending_mapping_row, _row_candidates(dimensionality), dimensionality
        )
    if editor.pending_comma is not None:
        dimensionality = editor.state.dimensionality
        return _representative(
            editor, editor.set_pending_comma, _comma_candidates(dimensionality), dimensionality
        )
    return None


def draft_plan(editor, current: Layout):
    op = draft_op(editor)
    if op is None:
        return None
    try:
        future = compute_future(editor, op, current)
    except Exception:
        logging.exception("preview future-layout build failed; suppressing draft rings")
        return None
    return plan_structural(current, future, occupied_axes(editor))


def draft_rings(editor, current: Layout, ringable) -> tuple:
    plan = draft_plan(editor, current)
    if plan is None:
        return NO_RINGS
    kinds = {cell.id: cell.kind for cell in current.cells}
    pending = frozenset(cell.id for cell in current.cells if cell.pending)
    green = plan.added | pending
    red = frozenset(i for i in (plan.removed - green) if kinds.get(i) in ringable)
    amber = frozenset(i for i in (plan.changed - green - red) if kinds.get(i) in ringable)
    return green, amber, red


def _committing(current: Layout, future: Layout) -> bool:
    return sum(c.pending for c in future.cells) < sum(c.pending for c in current.cells)


def value_graft(
    current: Layout, plan: PreviewPlan, source_id: str | None = None, hold=""
) -> Layout:
    future_texts = {cell.id: cell.text for cell in plan.future.cells}
    future_disabled = (
        {cell.id: cell.disabled for cell in plan.future.cells}
        if _committing(current, plan.future)
        else {}
    )
    swapped = []
    dirty = False
    for cell in current.cells:
        if (
            cell.kind.endswith("plus")
            and cell.id in future_disabled
            and future_disabled[cell.id] != cell.disabled
        ):
            swapped.append(replace(cell, disabled=future_disabled[cell.id]))
            dirty = True
            continue
        if cell.id in plan.changed and cell.id != source_id and not cell.pending:
            text = future_texts.get(cell.id, cell.text)
            if text != cell.text:
                swapped.append(replace(cell, text=text))
                dirty = True
                continue
        swapped.append(cell)
    if not dirty:
        return current
    return replace(current, cells=tuple(swapped), preview_hold=hold)


def build_hybrid(editor, baseline: Layout, plan: PreviewPlan, source_id=None) -> Layout:
    hybrid = editor.layout(previous_ids=baseline.identities, ghost_axes=plan.ghost_axes)
    hybrid = anchor_to_source(hybrid, baseline, source_id)
    return value_graft(graft_ghost_values(hybrid, baseline, plan.future, plan.ghost_axes), plan)


def _position(layout: Layout, cell_id: str) -> tuple | None:
    for cell in layout.cells:
        if cell.id == cell_id:
            return (round(cell.x), round(cell.y))
    return None


def source_stable(current: Layout, future: Layout, source_id: str | None) -> bool:
    if source_id is None:
        return True
    return _position(current, source_id) == _position(future, source_id)


def _corner(layout: Layout | None, cell_id: str | None) -> tuple | None:
    if layout is None:
        return None
    for cell in layout.cells:
        if cell.id == cell_id:
            return (cell.x, cell.y)
    return None


def anchor_to_source(layout: Layout, baseline: Layout, source_id: str | None) -> Layout:
    before, after = _corner(baseline, source_id), _corner(layout, source_id)
    if before is None or after is None or before == after:
        return layout
    return replace(layout, preview_offset=(before[0] - after[0], before[1] - after[1]))


def ghost_axes_between(current: Layout, future: Layout, occupied: frozenset = frozenset()) -> tuple:
    if current.axis_counts is None or future.axis_counts is None:
        return ()
    return tuple(
        axis
        for axis in GHOST_SLOT_AXES
        if axis not in occupied
        and future.axis_counts.get(axis, 0) - current.axis_counts.get(axis, 0) == 1
    )


def _axis_shrinks(current: Layout, future: Layout) -> bool:
    if current.axis_counts is None or future.axis_counts is None:
        return False
    return any(
        future.axis_counts.get(axis, 0) < current.axis_counts.get(axis, 0)
        for axis in ("elements", "generators", "commas")
    )


def _classified(current: Layout, future: Layout, holds: bool, occupied: frozenset) -> PreviewPlan:
    added = added_cell_ids(current, future)
    changed = value_changed_cell_ids(current, future)
    removed = removed_cell_ids(current, future)
    moved = moved_cell_ids(current, future)
    if not holds:
        return PreviewPlan(REFLOW, added, changed, removed, moved, (), future)
    ghosts = ghost_axes_between(current, future, occupied) if added else ()
    mode = HYBRID if ghosts else PAINT
    return PreviewPlan(mode, added, changed, removed, moved, ghosts, future)


def plan_preview(
    current: Layout,
    future: Layout,
    source_id: str | None = None,
    occupied_axes: frozenset = frozenset(),
) -> PreviewPlan:
    holds = bool(removed_cell_ids(current, future)) or not source_stable(current, future, source_id)
    plan = _classified(current, future, holds, occupied_axes)
    ghosts = _source_ghosts(plan.ghost_axes, source_id)
    if ghosts == plan.ghost_axes:
        return plan
    return replace(plan, mode=HYBRID if ghosts else REFLOW, ghost_axes=ghosts)


def plan_structural(
    current: Layout, future: Layout, occupied_axes: frozenset = frozenset()
) -> PreviewPlan:
    return _classified(current, future, _axis_shrinks(current, future), occupied_axes)


def reflow_to_hold(
    plan: PreviewPlan,
    current: Layout,
    occupied_axes: frozenset = frozenset(),
    source_id: str | None = None,
) -> PreviewPlan:
    ghosts = ghost_axes_between(current, plan.future, occupied_axes) if plan.added else ()
    ghosts = _source_ghosts(ghosts, source_id)
    return replace(plan, mode=HYBRID if ghosts else PAINT, ghost_axes=ghosts)


def plan_edit(baseline: Layout, live: Layout, future: Layout) -> PreviewPlan:
    return PreviewPlan(
        PAINT,
        added_cell_ids(baseline, future),
        value_changed_cell_ids(baseline, future),
        removed_cell_ids(live, future),
        frozenset(),
        (),
        future,
    )


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


def _graftable(cell) -> bool:
    return cell.pending or (cell.width == COLUMN_WIDTH and cell.kind not in _COLUMN_KINDS_EXEMPT)


def _element_slot_index(current: Layout, future: Layout) -> int | None:
    if current.axis_counts is None or future.axis_counts is None:
        return None
    grown = future.axis_counts.get("elements", 0)
    if grown == current.axis_counts.get("elements", 0) + 1:
        return grown - 1
    return None


def graft_ghost_values(
    hybrid: Layout, current: Layout, future: Layout, ghost_axes: tuple = ()
) -> Layout:
    current_ids = {cell.id for cell in current.cells}
    future_cells = {cell.id: cell for cell in future.cells}
    tokens = _new_tokens(current, future)
    if "elements" in ghost_axes:
        slot = _element_slot_index(current, future)
        if slot is not None:
            tokens = (str(slot), *tokens)
    grafted = []
    dirty = False
    for cell in hybrid.cells:
        if cell.id not in current_ids and _graftable(cell):
            donor = future_cells.get(cell.id)
            if donor is None:
                for alias in _slot_aliases(cell.id, tokens):
                    donor = future_cells.get(alias)
                    if donor is not None:
                        break
            pending = donor is not None
            text = donor.text if donor is not None else cell.text
            if text != cell.text or cell.pending != pending:
                grafted.append(replace(cell, text=text, pending=pending))
                dirty = True
                continue
        grafted.append(cell)
    if not dirty:
        return hybrid
    return replace(hybrid, cells=tuple(grafted))


def hybrid_orphan_ids(layout: Layout, baseline: Layout) -> frozenset:
    baseline_ids = {cell.id for cell in baseline.cells}
    return frozenset(
        cell.id
        for cell in layout.cells
        if cell.id not in baseline_ids and not cell.pending and _graftable(cell)
    )


def _column_positions(layout: Layout, prefix: str) -> tuple:
    xs = sorted(
        {cell.x for cell in layout.cells if cell.id.startswith(prefix) and not cell.pending}
    )
    return tuple(xs)


def _cells_in_columns(layout: Layout, ringable, xs: frozenset, include_pending=False) -> frozenset:
    return frozenset(
        cell.id
        for cell in layout.cells
        if cell.x in xs
        and cell.width == COLUMN_WIDTH
        and cell.kind in ringable
        and cell.kind not in _COLUMN_KINDS_EXEMPT
        and (include_pending or not cell.pending)
    )


def _cells_in_generator_rows(
    layout: Layout, ringable, rows: frozenset, include_pending=False
) -> frozenset:
    return frozenset(
        cell.id
        for cell in layout.cells
        if cell.generator in rows
        and cell.kind in ringable
        and (include_pending or not cell.pending)
    )


def open_draft_rings(layout: Layout, ringable, comma_draft: bool, row_draft: bool) -> tuple:
    amber: frozenset = frozenset()
    red: frozenset = frozenset()
    counts = layout.axis_counts or {}
    if comma_draft and counts.get("generators", 0):
        rank = counts["generators"]
        red |= _cells_in_generator_rows(
            layout, ringable, frozenset({rank - 1}), include_pending=True
        )
        amber |= _cells_in_generator_rows(layout, ringable, frozenset(range(rank - 1)))
        unchanged_xs = _column_positions(layout, "cell:mapped_unchanged:")
        if unchanged_xs:
            red |= _cells_in_columns(
                layout, ringable, frozenset({unchanged_xs[-1]}), include_pending=True
            )
    if row_draft and counts.get("commas", 0):
        comma_xs = _column_positions(layout, "cell:mapped_comma:")
        if comma_xs:
            red |= _cells_in_columns(
                layout, ringable, frozenset({comma_xs[-1]}), include_pending=True
            )
            amber |= _cells_in_columns(layout, ringable, frozenset(comma_xs[:-1]))
    return amber - red, red
