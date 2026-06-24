from __future__ import annotations

from nicegui import ui

from rtt.app import (
    spreadsheet,
)
from rtt.app.render_html import (
    _control_svg,
)


class _ReconButtons:
    def __init__(self, r) -> None:
        self.r = r

    def _build_minus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click", lambda _=None: self.r._cb.act(self.r._editor.shrink)
        )
        self._choose._preview_control(wrap, self.r._editor.shrink)

    def _build_plus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn").on(
            "click", lambda _=None: self.r._cb.act(self.r._editor.expand)
        )
        self._choose._preview_control(wrap, self.r._editor.expand)

    def _build_gen_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click",
            lambda _=None, idx=cb.gen: self.r._cb.act(
                lambda: self.r._editor.remove_mapping_row(idx)
            ),
        )
        self._choose._preview_rank_remove(wrap, "row", cb.gen)

    def _build_gen_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping").on(
            "click",
            lambda _=None: self.r._cb.add_interval(self.r._editor.add_mapping_row, "mapping"),
        )

    def _build_map_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        if cb.pending:
            ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
                "click", lambda _=None: self.r._cb.act(self.r._editor.cancel_pending_mapping_row)
            )
            return
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
            "click",
            lambda _=None, idx=cb.gen: self.r._cb.act(
                lambda: self.r._editor.remove_mapping_row(idx)
            ),
        )
        self._choose._preview_rank_remove(wrap, "row", cb.gen)

    def _build_map_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping").on(
            "click",
            lambda _=None: self.r._cb.add_interval(self.r._editor.add_mapping_row, "mapping"),
        )

    def _build_basis_minus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
            "click", lambda _=None: self.r._cb.act(self.r._editor.shrink)
        )
        self._choose._preview_control(wrap, self.r._editor.shrink)

    def _build_comma_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb,
            wrap,
            self.r._editor.cancel_pending_comma,
            self.r._editor.remove_comma,
            rank_axis="comma",
        )

    def _build_comma_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-comma").on(
            "click", lambda _=None: self.r._cb.add_interval(self.r._editor.add_comma, "comma")
        )

    def _build_element_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-element").on(
            "click", lambda _=None: self.r._cb.add_interval(self.r._editor.add_element, "element")
        )

    def _build_element_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        action = (
            self.r._editor.remove_element
            if cb.id.endswith(":pending")
            else (lambda idx=cb.prime: self.r._editor.remove_domain_element(idx))
        )
        btn = "rtt-minus-btn-v" if ":basis" in cb.id else "rtt-minus-btn"
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes(f"rtt-glyph {btn}").on(
            "click", lambda _=None: self.r._cb.act(action)
        )
        self._choose._preview_control(wrap, action)

    def _build_list_minus(
        self, cb: spreadsheet.CellBox, wrap, cancel, remove, rank_axis: str | None = None
    ) -> None:
        pending = cb.id.endswith(":pending")
        action = cancel if pending else (lambda idx=cb.comma: remove(idx))
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click", lambda _=None: self.r._cb.act(action)
        )
        if rank_axis is not None and not pending:
            self._choose._preview_rank_remove(wrap, rank_axis, cb.comma)
        else:
            self._choose._preview_control(wrap, action)

    def _build_interest_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb, wrap, self.r._editor.cancel_pending_interest, self.r._editor.remove_interest
        )

    def _build_interest_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-interest").on(
            "click", lambda _=None: self.r._cb.add_interval(self.r._editor.add_interest, "interest")
        )

    def _build_held_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb, wrap, self.r._editor.cancel_pending_held, self.r._editor.remove_held
        )

    def _build_held_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-held").on(
            "click", lambda _=None: self.r._cb.add_interval(self.r._editor.add_held, "held")
        )

    def _build_target_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb, wrap, self.r._editor.cancel_pending_target, self.r._editor.remove_target
        )

    def _build_target_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-target").on(
            "click", lambda _=None: self.r._cb.add_interval(self.r._editor.add_target, "target")
        )

    def _build_colgrip(self, cb: spreadsheet.CellBox, wrap) -> None:
        # drag one column's grip onto another to MOVE/reorder it; the per-list "grip:{list}:add" zone
        # is drop-only — the append / into-empty-list target on the stub gridline, so dropping into a
        # list is always "drop on the gridline" (no separate header/+ target). Mirrors the proven
        # drag-to-combine handle EXACTLY (which the user confirmed works), so it relies on no global
        # drag.js / dragging-class: a grip is BOTH source AND drop target, with a per-element dragover
        # preventDefault (client-side, so it doesn't round-trip per move) marking it a valid target.
        # The dragged column's (list, idx) is held server-side from dragstart through drop.
        _, lst, tail = cb.id.split(":")
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")
        if tail == "add":
            wrap.classes("rtt-colgrip rtt-coldrop")
            wrap.on(
                "dragenter.prevent", lambda _=None, which=lst: self.r._cb.on_drag_enter(which, None)
            )
            wrap.on("drop.prevent", lambda _=None, which=lst: self.r._cb.on_drop(which, None))
            return
        idx = cb.comma
        wrap.classes("rtt-drag-handle rtt-colgrip").props("draggable=true")
        wrap.on("dragstart", lambda _=None, which=lst, i=idx: self.r._cb.on_drag_start(which, i))
        wrap.on(
            "dragenter.prevent", lambda _=None, which=lst, i=idx: self.r._cb.on_drag_enter(which, i)
        )
        wrap.on("dragend", lambda _=None: self.r._cb.on_drag_end())
        wrap.on("drop.prevent", lambda _=None, which=lst, i=idx: self.r._cb.on_drop(which, i))
        ui.icon("drag_indicator").classes("rtt-grip")
