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
    "comma": "comma_cell",
    "target": "target_cell",
    "held": "held_cell",
    "interest": "interest_cell",
}


def build_map_drag(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    # HTML5 DnD: a Quasar input cell is not a reliable native drop target, so the drag goes grip-to-
    # grip (a grip is both source and target, each with its own dragover preventDefault). Do NOT set
    # effectAllowed here — leaving it 'uninitialized' permits all drops; setting it 'copy' leaves it
    # 'none' and blocks every drop. dropEffect='copy' on dragover gives the + cursor.
    wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
    wrap.on(
        "dragstart", lambda _=None, index=cell_box.generator: _begin_row_drag(reconciler, index)
    )
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, index=cell_box.generator: _preview_row_drop(reconciler, index),
    )
    wrap.on("dragend", lambda _=None: _end_row_drag(reconciler))
    wrap.on(
        "drop.prevent", lambda _=None, index=cell_box.generator: _drop_on_row(reconciler, index)
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_row_target(reconciler, wrap, generator: int) -> None:
    # HTML5 DnD: preventDefault on dragover makes a cell a droppable surface and dropEffect='copy'
    # gives the + cursor, so every mapping cell can accept a dragged generator row.
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent", lambda _=None, index=generator: _preview_row_drop(reconciler, index)
    )
    wrap.on("drop.prevent", lambda _=None, index=generator: _drop_on_row(reconciler, index))


def _begin_row_drag(reconciler, index: int) -> None:
    reconciler._row_drag = index
    reconciler._cell_box.combine_begin()


def _end_row_drag(reconciler) -> None:
    reconciler._row_drag = None
    reconciler._cell_box.combine_end()


def _preview_row_drop(reconciler, index: int) -> None:
    source = reconciler._row_drag
    valid = source is not None and source != index
    apply = (lambda: reconciler._editor.add_mapping_row_to(source, index)) if valid else None
    target = (
        (
            lambda cell_box: (
                cell_box.kind == "mapping" and getattr(cell_box, "generator", None) == index
            )
        )
        if valid
        else None
    )
    reconciler._cell_box.combine_preview(apply, target)


def _drop_on_row(reconciler, index: int) -> None:
    source = reconciler._row_drag
    reconciler._row_drag = None
    if source is not None and source != index:
        reconciler._cell_box.combine_commit(
            lambda: reconciler._editor.add_mapping_row_to(source, index)
        )
    else:
        reconciler._cell_box.combine_end()


def build_int_drag(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    group = cell_box.id.split(":")[1]
    wrap.classes("rtt-drag-handle rtt-column-handle").props("draggable=true")
    wrap.on(
        "dragstart",
        lambda _=None, g=group, index=cell_box.comma: _begin_col_drag(reconciler, g, index),
    )
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, g=group, index=cell_box.comma: _preview_int_drop(reconciler, g, index),
    )
    wrap.on("dragend", lambda _=None: _end_col_drag(reconciler))
    wrap.on(
        "drop.prevent",
        lambda _=None, g=group, index=cell_box.comma: _drop_on_interval(reconciler, g, index),
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def arm_col_target(reconciler, wrap, group: str, index: int) -> None:
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent", lambda _=None, g=group, i=index: _preview_int_drop(reconciler, g, i)
    )
    wrap.on("drop.prevent", lambda _=None, g=group, i=index: _drop_on_interval(reconciler, g, i))


def _int_combine(reconciler, group: str, index: int):
    if reconciler._col_drag is None:
        return None
    src_group, source = reconciler._col_drag
    if src_group != group or source == index:
        return None
    combine = getattr(reconciler._editor, _INTERVAL_COMBINE[group])
    return lambda: combine(source, index)


def _begin_col_drag(reconciler, group: str, index: int) -> None:
    reconciler._col_drag = (group, index)
    reconciler._cell_box.combine_begin()


def _end_col_drag(reconciler) -> None:
    reconciler._col_drag = None
    reconciler._cell_box.combine_end()


def _preview_int_drop(reconciler, group: str, index: int) -> None:
    apply = _int_combine(reconciler, group, index)
    kind = _GROUP_CELL_KIND[group]
    target = (
        (lambda cell_box: cell_box.kind == kind and getattr(cell_box, "comma", None) == index)
        if apply is not None
        else None
    )
    reconciler._cell_box.combine_preview(apply, target)


def _drop_on_interval(reconciler, group: str, index: int) -> None:
    apply = _int_combine(reconciler, group, index)
    reconciler._col_drag = None
    if apply is not None:
        reconciler._cell_box.combine_commit(apply)
    else:
        reconciler._cell_box.combine_end()
