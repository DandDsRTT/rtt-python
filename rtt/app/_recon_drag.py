from __future__ import annotations

from nicegui import ui

from rtt.app import (
    spreadsheet,
)

_GROUP_CELL_KIND: dict[str, str] = {
    "comma": "comma_cell",
    "target": "target_cell",
    "held": "held_cell",
    "interest": "interest_cell",
}

_DRAG_SOURCE_SETDATA_JS = "(e) => e.dataTransfer.setData('text/plain', '')"


def arm_drag_source(wrap) -> None:
    wrap.on("dragstart", js_handler=_DRAG_SOURCE_SETDATA_JS)


def build_map_drag(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    # HTML5 DnD: a Quasar input cell is not a reliable native drop target, so the drag goes grip-to-
    # grip (a grip is both source and target, each with its own dragover preventDefault). Do NOT set
    # effectAllowed here — leaving it 'uninitialized' permits all drops; setting it 'copy' leaves it
    # 'none' and blocks every drop. dropEffect='copy' on dragover gives the + cursor.
    wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
    arm_drag_source(wrap)
    wrap.on("dragstart", lambda _=None, index=cell.generator: _begin_row_drag(reconciler, index))
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, index=cell.generator: _preview_row_drop(reconciler, index),
    )
    wrap.on("dragend", lambda _=None: _end_row_drag(reconciler))
    wrap.on("drop.prevent", lambda _=None, index=cell.generator: _drop_on_row(reconciler, index))
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
    reconciler._callbacks.combine_begin()


def _end_row_drag(reconciler) -> None:
    reconciler._row_drag = None
    reconciler._callbacks.combine_end()


def _preview_row_drop(reconciler, index: int) -> None:
    source = reconciler._row_drag
    valid = source is not None and source != index
    apply = (lambda: reconciler._editor.add_mapping_row_to(source, index)) if valid else None
    target = (
        (lambda cell: cell.kind == "mapping" and getattr(cell, "generator", None) == index)
        if valid
        else None
    )
    reconciler._callbacks.combine_preview(apply, target)


def _drop_on_row(reconciler, index: int) -> None:
    source = reconciler._row_drag
    reconciler._row_drag = None
    if source is not None and source != index:
        reconciler._callbacks.combine_commit(
            lambda: reconciler._editor.add_mapping_row_to(source, index)
        )
    else:
        reconciler._callbacks.combine_end()


def build_int_drag(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    group = cell.id.split(":")[1]
    wrap.classes("rtt-drag-handle rtt-column-handle").props("draggable=true")
    arm_drag_source(wrap)
    wrap.on(
        "dragstart",
        lambda _=None, g=group, index=cell.comma: _begin_col_drag(reconciler, g, index),
    )
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, g=group, index=cell.comma: _preview_int_drop(reconciler, g, index),
    )
    wrap.on("dragend", lambda _=None: _end_col_drag(reconciler))
    wrap.on(
        "drop.prevent",
        lambda _=None, g=group, index=cell.comma: _drop_on_interval(reconciler, g, index),
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def build_int_derived(_reconciler, _cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-derived-mark rtt-column-handle")
    ui.icon("block").classes("rtt-grip")


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
    if (src_group, source) == (group, index):
        return None
    return lambda: reconciler._editor.combine_intervals(src_group, source, group, index)


def _begin_col_drag(reconciler, group: str, index: int) -> None:
    reconciler._col_drag = (group, index)
    reconciler._callbacks.combine_begin()


def _end_col_drag(reconciler) -> None:
    reconciler._col_drag = None
    reconciler._callbacks.combine_end()


def _preview_int_drop(reconciler, group: str, index: int) -> None:
    apply = _int_combine(reconciler, group, index)
    kind = _GROUP_CELL_KIND[group]
    target = (
        (lambda cell: cell.kind == kind and getattr(cell, "comma", None) == index)
        if apply is not None
        else None
    )
    reconciler._callbacks.combine_preview(apply, target)


def _drop_on_interval(reconciler, group: str, index: int) -> None:
    apply = _int_combine(reconciler, group, index)
    reconciler._col_drag = None
    if apply is not None:
        reconciler._callbacks.combine_commit(apply)
    else:
        reconciler._callbacks.combine_end()


_ELEMENT_MOVE: dict[str, str] = {
    "combine": "add_element_to",
    "reorder": "reorder_domain_element",
}


def build_element_combine(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _wire_element_drag(reconciler, cell, wrap, "combine", "rtt-drag-handle rtt-row-handle")


def build_element_reorder(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _wire_element_drag(reconciler, cell, wrap, "reorder", "rtt-drag-handle rtt-subcolumn-grip")


def _wire_element_drag(reconciler, cell: spreadsheet.Cell, wrap, mode: str, classes: str) -> None:
    wrap.classes(classes).props("draggable=true")
    arm_drag_source(wrap)
    wrap.on("dragstart", lambda _=None, m=mode, i=cell.prime: _begin_element_drag(reconciler, m, i))
    wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
    wrap.on(
        "dragenter.prevent",
        lambda _=None, m=mode, i=cell.prime: _preview_element_drop(reconciler, m, i),
    )
    wrap.on("dragend", lambda _=None: _end_element_drag(reconciler))
    wrap.on("drop.prevent", lambda _=None, m=mode, i=cell.prime: _drop_on_element(reconciler, m, i))
    ui.icon("drag_indicator").classes("rtt-grip")


def _element_move(reconciler, mode: str, index: int):
    if reconciler._element_drag is None:
        return None
    drag_mode, source = reconciler._element_drag
    if drag_mode != mode or source == index:
        return None
    move = getattr(reconciler._editor, _ELEMENT_MOVE[mode])
    return lambda: move(source, index)


def _begin_element_drag(reconciler, mode: str, index: int) -> None:
    reconciler._element_drag = (mode, index)
    reconciler._callbacks.combine_begin()


def _end_element_drag(reconciler) -> None:
    reconciler._element_drag = None
    reconciler._callbacks.combine_end()


def _preview_element_drop(reconciler, mode: str, index: int) -> None:
    apply = _element_move(reconciler, mode, index)
    target = (
        (
            lambda cell: (
                cell.kind in ("element_cell", "element_ratio")
                and getattr(cell, "prime", None) == index
            )
        )
        if apply is not None
        else None
    )
    reconciler._callbacks.combine_preview(apply, target)


def _drop_on_element(reconciler, mode: str, index: int) -> None:
    apply = _element_move(reconciler, mode, index)
    reconciler._element_drag = None
    if apply is not None:
        reconciler._callbacks.combine_commit(apply)
    else:
        reconciler._callbacks.combine_end()
