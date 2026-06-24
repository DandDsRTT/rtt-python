from __future__ import annotations

from typing import ClassVar

from nicegui import ui

from rtt.app import (
    spreadsheet,
)


class _ReconDrag:
    _INTERVAL_COMBINE: ClassVar[dict[str, str]] = {
        "comma": "add_comma_to",
        "target": "add_target_to",
        "held": "add_held_to",
        "interest": "add_interest_to",
    }

    _GROUP_CELL_KIND: ClassVar[dict[str, str]] = {
        "comma": "commacell",
        "target": "targetcell",
        "held": "heldcell",
        "interest": "interestcell",
    }

    def __init__(self, r) -> None:
        self.r = r

    def _build_map_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
        # HTML5 DnD: a Quasar input cell is not a reliable native drop target, so the drag goes grip-to-
        # grip (a grip is both source and target, each with its own dragover preventDefault). Do NOT set
        # effectAllowed here — leaving it 'uninitialized' permits all drops; setting it 'copy' leaves it
        # 'none' and blocks every drop. dropEffect='copy' on dragover gives the + cursor.
        wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, idx=cb.gen: self._begin_row_drag(idx))
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, idx=cb.gen: self._preview_row_drop(idx))
        wrap.on("dragend", lambda _=None: self._end_row_drag())
        wrap.on("drop.prevent", lambda _=None, idx=cb.gen: self._drop_on_row(idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_row_target(self, wrap, gen: int) -> None:
        # HTML5 DnD: preventDefault on dragover makes a cell a droppable surface and dropEffect='copy'
        # gives the + cursor, so every mapping cell can accept a dragged generator row.
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, idx=gen: self._preview_row_drop(idx))
        wrap.on("drop.prevent", lambda _=None, idx=gen: self._drop_on_row(idx))

    def _begin_row_drag(self, idx: int) -> None:
        self.r._row_drag = idx
        self.r._cb.combine_begin()

    def _end_row_drag(self) -> None:
        self.r._row_drag = None
        self.r._cb.combine_end()

    def _preview_row_drop(self, idx: int) -> None:
        src = self.r._row_drag
        valid = src is not None and src != idx
        apply = (lambda: self.r._editor.add_mapping_row_to(src, idx)) if valid else None
        target = (
            (lambda cb: cb.kind == "mapping" and getattr(cb, "gen", None) == idx) if valid else None
        )
        self.r._cb.combine_preview(apply, target)

    def _drop_on_row(self, idx: int) -> None:
        src = self.r._row_drag
        self.r._row_drag = None
        if src is not None and src != idx:
            self.r._cb.combine_commit(lambda: self.r._editor.add_mapping_row_to(src, idx))
        else:
            self.r._cb.combine_end()

    def _build_int_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
        group = cb.id.split(":")[1]
        wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, g=group, idx=cb.comma: self._begin_col_drag(g, idx))
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on(
            "dragenter.prevent",
            lambda _=None, g=group, idx=cb.comma: self._preview_int_drop(g, idx),
        )
        wrap.on("dragend", lambda _=None: self._end_col_drag())
        wrap.on(
            "drop.prevent", lambda _=None, g=group, idx=cb.comma: self._drop_on_interval(g, idx)
        )
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_col_target(self, wrap, group: str, idx: int) -> None:
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: self._preview_int_drop(g, i))
        wrap.on("drop.prevent", lambda _=None, g=group, i=idx: self._drop_on_interval(g, i))

    def _int_combine(self, group: str, idx: int):
        if self.r._col_drag is None:
            return None
        src_group, src = self.r._col_drag
        if src_group != group or src == idx:
            return None
        combine = getattr(self.r._editor, self._INTERVAL_COMBINE[group])
        return lambda: combine(src, idx)

    def _begin_col_drag(self, group: str, idx: int) -> None:
        self.r._col_drag = (group, idx)
        self.r._cb.combine_begin()

    def _end_col_drag(self) -> None:
        self.r._col_drag = None
        self.r._cb.combine_end()

    def _preview_int_drop(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        kind = self._GROUP_CELL_KIND[group]
        target = (
            (lambda cb: cb.kind == kind and getattr(cb, "comma", None) == idx)
            if apply is not None
            else None
        )
        self.r._cb.combine_preview(apply, target)

    def _drop_on_interval(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        self.r._col_drag = None
        if apply is not None:
            self.r._cb.combine_commit(apply)
        else:
            self.r._cb.combine_end()
