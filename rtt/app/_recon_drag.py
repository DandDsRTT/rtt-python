from __future__ import annotations

from nicegui import ui

from rtt.app import (
    spreadsheet,
)

_INTERVAL_COMBINE: dict[str, str] = {
    "comma": "add_comma_to",
    "target": "add_target_to",
    "held": "add_held_to",
    "interest": "add_interest_to",
}

_GROUP_CELL_KIND: dict[str, str] = {
    "comma": "commacell",
    "target": "targetcell",
    "held": "heldcell",
    "interest": "interestcell",
}


def build_map_drag(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    # HTML5 DnD: a Quasar input cell is not a reliable native drop target, so the drag goes grip-to-
    # grip (a grip is both source and target, each with its own dragover preventDefault). Do NOT set
    # effectAllowed here — leaving it 'uninitialized' permits all drops; setting it 'copy' leaves it
    # 'none' and blocks every drop. dropEffect='copy' on dragover gives the + cursor.
    wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
    wrap.on("dragstart", lambda _=None, idx=cell_box.gen: _begin_row_drag(rec, idx))
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on("dragenter.prevent", lambda _=None, idx=cell_box.gen: _preview_row_drop(rec, idx))
    wrap.on("dragend", lambda _=None: _end_row_drag(rec))
    wrap.on("drop.prevent", lambda _=None, idx=cell_box.gen: _drop_on_row(rec, idx))
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_row_target(rec, wrap, gen: int) -> None:
    # HTML5 DnD: preventDefault on dragover makes a cell a droppable surface and dropEffect='copy'
    # gives the + cursor, so every mapping cell can accept a dragged generator row.
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on("dragenter.prevent", lambda _=None, idx=gen: _preview_row_drop(rec, idx))
    wrap.on("drop.prevent", lambda _=None, idx=gen: _drop_on_row(rec, idx))


def _begin_row_drag(rec, idx: int) -> None:
    rec._row_drag = idx
    rec._cb.combine_begin()


def _end_row_drag(rec) -> None:
    rec._row_drag = None
    rec._cb.combine_end()


def _preview_row_drop(rec, idx: int) -> None:
    src = rec._row_drag
    valid = src is not None and src != idx
    apply = (lambda: rec._editor.add_mapping_row_to(src, idx)) if valid else None
    target = (
        (lambda cell_box: cell_box.kind == "mapping" and getattr(cell_box, "gen", None) == idx)
        if valid
        else None
    )
    rec._cb.combine_preview(apply, target)


def _drop_on_row(rec, idx: int) -> None:
    src = rec._row_drag
    rec._row_drag = None
    if src is not None and src != idx:
        rec._cb.combine_commit(lambda: rec._editor.add_mapping_row_to(src, idx))
    else:
        rec._cb.combine_end()


def build_int_drag(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    group = cell_box.id.split(":")[1]
    wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
    wrap.on("dragstart", lambda _=None, g=group, idx=cell_box.comma: _begin_col_drag(rec, g, idx))
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, g=group, idx=cell_box.comma: _preview_int_drop(rec, g, idx),
    )
    wrap.on("dragend", lambda _=None: _end_col_drag(rec))
    wrap.on(
        "drop.prevent", lambda _=None, g=group, idx=cell_box.comma: _drop_on_interval(rec, g, idx)
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_col_target(rec, wrap, group: str, idx: int) -> None:
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: _preview_int_drop(rec, g, i))
    wrap.on("drop.prevent", lambda _=None, g=group, i=idx: _drop_on_interval(rec, g, i))


def _int_combine(rec, group: str, idx: int):
    if rec._col_drag is None:
        return None
    src_group, src = rec._col_drag
    if src_group != group or src == idx:
        return None
    combine = getattr(rec._editor, _INTERVAL_COMBINE[group])
    return lambda: combine(src, idx)


def _begin_col_drag(rec, group: str, idx: int) -> None:
    rec._col_drag = (group, idx)
    rec._cb.combine_begin()


def _end_col_drag(rec) -> None:
    rec._col_drag = None
    rec._cb.combine_end()


def _preview_int_drop(rec, group: str, idx: int) -> None:
    apply = _int_combine(rec, group, idx)
    kind = _GROUP_CELL_KIND[group]
    target = (
        (lambda cell_box: cell_box.kind == kind and getattr(cell_box, "comma", None) == idx)
        if apply is not None
        else None
    )
    rec._cb.combine_preview(apply, target)


def _drop_on_interval(rec, group: str, idx: int) -> None:
    apply = _int_combine(rec, group, idx)
    rec._col_drag = None
    if apply is not None:
        rec._cb.combine_commit(apply)
    else:
        rec._cb.combine_end()
