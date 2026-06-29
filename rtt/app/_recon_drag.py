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


def build_map_drag(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    # HTML5 DnD: a Quasar input cell is not a reliable native drop target, so the drag goes grip-to-
    # grip (a grip is both source and target, each with its own dragover preventDefault). Do NOT set
    # effectAllowed here — leaving it 'uninitialized' permits all drops; setting it 'copy' leaves it
    # 'none' and blocks every drop. dropEffect='copy' on dragover gives the + cursor.
    wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
    wrap.on("dragstart", lambda _=None, idx=cell_box.gen: _begin_row_drag(reconciler, idx))
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent", lambda _=None, idx=cell_box.gen: _preview_row_drop(reconciler, idx)
    )
    wrap.on("dragend", lambda _=None: _end_row_drag(reconciler))
    wrap.on("drop.prevent", lambda _=None, idx=cell_box.gen: _drop_on_row(reconciler, idx))
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_row_target(reconciler, wrap, gen: int) -> None:
    # HTML5 DnD: preventDefault on dragover makes a cell a droppable surface and dropEffect='copy'
    # gives the + cursor, so every mapping cell can accept a dragged generator row.
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on("dragenter.prevent", lambda _=None, idx=gen: _preview_row_drop(reconciler, idx))
    wrap.on("drop.prevent", lambda _=None, idx=gen: _drop_on_row(reconciler, idx))


def _begin_row_drag(reconciler, idx: int) -> None:
    reconciler._row_drag = idx
    reconciler._cell_box.combine_begin()


def _end_row_drag(reconciler) -> None:
    reconciler._row_drag = None
    reconciler._cell_box.combine_end()


def _preview_row_drop(reconciler, idx: int) -> None:
    src = reconciler._row_drag
    valid = src is not None and src != idx
    apply = (lambda: reconciler._editor.add_mapping_row_to(src, idx)) if valid else None
    target = (
        (lambda cell_box: cell_box.kind == "mapping" and getattr(cell_box, "gen", None) == idx)
        if valid
        else None
    )
    reconciler._cell_box.combine_preview(apply, target)


def _drop_on_row(reconciler, idx: int) -> None:
    src = reconciler._row_drag
    reconciler._row_drag = None
    if src is not None and src != idx:
        reconciler._cell_box.combine_commit(lambda: reconciler._editor.add_mapping_row_to(src, idx))
    else:
        reconciler._cell_box.combine_end()


def build_int_drag(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    group = cell_box.id.split(":")[1]
    wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
    wrap.on(
        "dragstart", lambda _=None, g=group, idx=cell_box.comma: _begin_col_drag(reconciler, g, idx)
    )
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, g=group, idx=cell_box.comma: _preview_int_drop(reconciler, g, idx),
    )
    wrap.on("dragend", lambda _=None: _end_col_drag(reconciler))
    wrap.on(
        "drop.prevent",
        lambda _=None, g=group, idx=cell_box.comma: _drop_on_interval(reconciler, g, idx),
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_col_target(reconciler, wrap, group: str, idx: int) -> None:
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: _preview_int_drop(reconciler, g, i))
    wrap.on("drop.prevent", lambda _=None, g=group, i=idx: _drop_on_interval(reconciler, g, i))


def _int_combine(reconciler, group: str, idx: int):
    if reconciler._col_drag is None:
        return None
    src_group, src = reconciler._col_drag
    if src_group != group or src == idx:
        return None
    combine = getattr(reconciler._editor, _INTERVAL_COMBINE[group])
    return lambda: combine(src, idx)


def _begin_col_drag(reconciler, group: str, idx: int) -> None:
    reconciler._col_drag = (group, idx)
    reconciler._cell_box.combine_begin()


def _end_col_drag(reconciler) -> None:
    reconciler._col_drag = None
    reconciler._cell_box.combine_end()


def _preview_int_drop(reconciler, group: str, idx: int) -> None:
    apply = _int_combine(reconciler, group, idx)
    kind = _GROUP_CELL_KIND[group]
    target = (
        (lambda cell_box: cell_box.kind == kind and getattr(cell_box, "comma", None) == idx)
        if apply is not None
        else None
    )
    reconciler._cell_box.combine_preview(apply, target)


def _drop_on_interval(reconciler, group: str, idx: int) -> None:
    apply = _int_combine(reconciler, group, idx)
    reconciler._col_drag = None
    if apply is not None:
        reconciler._cell_box.combine_commit(apply)
    else:
        reconciler._cell_box.combine_end()
