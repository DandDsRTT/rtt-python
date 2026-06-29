from __future__ import annotations

from nicegui import ui

from rtt.app import (
    spreadsheet,
)
from rtt.app._recon_choosers import (
    preview_control,
    preview_rank_remove,
)
from rtt.app.render_html import (
    _control_svg,
)


def build_minus(reconciler, _cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click", lambda _=None: reconciler._cell_box.act(reconciler._editor.shrink)
    )
    preview_control(reconciler, wrap, reconciler._editor.shrink)


def build_plus(reconciler, _cell_box: spreadsheet.CellBox, wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button").on(
        "click", lambda _=None: reconciler._cell_box.act(reconciler._editor.expand)
    )
    preview_control(reconciler, wrap, reconciler._editor.expand)


def build_gen_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click",
        lambda _=None, idx=cell_box.gen: reconciler._cell_box.act(
            lambda: reconciler._editor.remove_mapping_row(idx)
        ),
    )
    preview_rank_remove(reconciler, wrap, "row", cell_box.gen)


def build_gen_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-mapping").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(
            reconciler._editor.add_mapping_row, "mapping"
        ),
    )


def build_map_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    if cell_box.pending:
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
            "click",
            lambda _=None: reconciler._cell_box.act(reconciler._editor.cancel_pending_mapping_row),
        )
        return
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
        "click",
        lambda _=None, idx=cell_box.gen: reconciler._cell_box.act(
            lambda: reconciler._editor.remove_mapping_row(idx)
        ),
    )
    preview_rank_remove(reconciler, wrap, "row", cell_box.gen)


def build_map_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-mapping").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(
            reconciler._editor.add_mapping_row, "mapping"
        ),
    )


def build_basis_minus(reconciler, _cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
        "click", lambda _=None: reconciler._cell_box.act(reconciler._editor.shrink)
    )
    preview_control(reconciler, wrap, reconciler._editor.shrink)


def build_comma_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell_box,
        wrap,
        reconciler._editor.cancel_pending_comma,
        reconciler._editor.remove_comma,
        rank_axis="comma",
    )


def build_comma_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-comma").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(reconciler._editor.add_comma, "comma"),
    )


def build_element_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-element").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(reconciler._editor.add_element, "element"),
    )


def build_element_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    action = (
        reconciler._editor.remove_element
        if cell_box.id.endswith(":pending")
        else (lambda idx=cell_box.prime: reconciler._editor.remove_domain_element(idx))
    )
    button = "rtt-minus-button-v" if ":basis" in cell_box.id else "rtt-minus-button"
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes(f"rtt-glyph {button}").on(
        "click", lambda _=None: reconciler._cell_box.act(action)
    )
    preview_control(reconciler, wrap, action)


def _build_list_minus(
    reconciler, cell_box: spreadsheet.CellBox, wrap, cancel, remove, rank_axis=None
) -> None:
    pending = cell_box.id.endswith(":pending")
    action = cancel if pending else (lambda idx=cell_box.comma: remove(idx))
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click", lambda _=None: reconciler._cell_box.act(action)
    )
    if rank_axis is not None and not pending:
        preview_rank_remove(reconciler, wrap, rank_axis, cell_box.comma)
    else:
        preview_control(reconciler, wrap, action)


def build_interest_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell_box,
        wrap,
        reconciler._editor.cancel_pending_interest,
        reconciler._editor.remove_interest,
    )


def build_interest_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-interest").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(
            reconciler._editor.add_interest, "interest"
        ),
    )


def build_held_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell_box,
        wrap,
        reconciler._editor.cancel_pending_held,
        reconciler._editor.remove_held,
    )


def build_held_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-held").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(reconciler._editor.add_held, "held"),
    )


def build_target_minus(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell_box,
        wrap,
        reconciler._editor.cancel_pending_target,
        reconciler._editor.remove_target,
    )


def build_target_plus(reconciler, _cell_box: spreadsheet.CellBox, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-target").on(
        "click",
        lambda _=None: reconciler._cell_box.add_interval(reconciler._editor.add_target, "target"),
    )


def build_colgrip(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    # HTML5 DnD: an element is only a valid drop target if it preventDefaults dragover, so each grip
    # is both drag source and drop target with its own client-side dragover preventDefault.
    _, lst, tail = cell_box.id.split(":")
    wrap.on("dragover", js_handler="(e) => e.preventDefault()")
    if tail == "add":
        wrap.classes("rtt-colgrip rtt-coldrop")
        wrap.on(
            "dragenter.prevent",
            lambda _=None, which=lst: reconciler._cell_box.on_drag_enter(which, None),
        )
        wrap.on("drop.prevent", lambda _=None, which=lst: reconciler._cell_box.on_drop(which, None))
        return
    idx = cell_box.comma
    wrap.classes("rtt-drag-handle rtt-colgrip").props("draggable=true")
    wrap.on(
        "dragstart", lambda _=None, which=lst, i=idx: reconciler._cell_box.on_drag_start(which, i)
    )
    wrap.on(
        "dragenter.prevent",
        lambda _=None, which=lst, i=idx: reconciler._cell_box.on_drag_enter(which, i),
    )
    wrap.on("dragend", lambda _=None: reconciler._cell_box.on_drag_end())
    wrap.on("drop.prevent", lambda _=None, which=lst, i=idx: reconciler._cell_box.on_drop(which, i))
    ui.icon("drag_indicator").classes("rtt-grip")
