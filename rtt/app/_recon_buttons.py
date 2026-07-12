from __future__ import annotations

from nicegui import ui

from rtt.app import (
    spreadsheet,
)
from rtt.app._recon_hover import (
    preview_control,
    preview_rank_remove,
)
from rtt.app.render_html import (
    _control_svg,
)


def build_canonicalize_button(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    canonicalize = reconciler._editor.canonicalize_domain_basis
    button = ui.button(
        cell.text,
        on_click=lambda: reconciler._callbacks.act(canonicalize),
        color=None,
    )
    button.props("unelevated dense no-caps flat").classes("rtt-canonicalize-button rtt-acts")
    reconciler.cells[cell.id].chooser.canonicalize_button = button
    preview_control(reconciler, button, canonicalize)
    update_canonicalize_button(reconciler, cell)


def update_canonicalize_button(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].chooser.canonicalize_button.set_enabled(not cell.disabled)


_INERT_FLANKING_GAPS_JS = """(e) => {
  const grip = e.currentTarget;
  const col = grip.classList.contains('rtt-column-grip');
  const cls = col ? 'rtt-col-gap' : 'rtt-row-gap';
  const rect = grip.getBoundingClientRect();
  const mid = col ? rect.left + rect.width / 2 : rect.top + rect.height / 2;
  let before = null, after = null, db = Infinity, da = Infinity;
  document.querySelectorAll('.' + cls).forEach((gap) => {
    const gr = gap.getBoundingClientRect();
    const gc = col ? gr.left + gr.width / 2 : gr.top + gr.height / 2;
    if (gc <= mid && mid - gc < db) { db = mid - gc; before = gap; }
    if (gc >= mid && gc - mid < da) { da = gc - mid; after = gap; }
  });
  if (before) before.classList.add('rtt-gap-inert');
  if (after) after.classList.add('rtt-gap-inert');
}"""

_CLEAR_INERT_GAPS_JS = (
    "() => document.querySelectorAll('.rtt-gap-inert')"
    ".forEach((gap) => gap.classList.remove('rtt-gap-inert'))"
)


def build_minus(reconciler, _callbacks: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click", lambda _=None: reconciler._callbacks.act(reconciler._editor.shrink)
    )
    preview_control(reconciler, wrap, reconciler._editor.shrink)


def build_plus(reconciler, _callbacks: spreadsheet.Cell, wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button").on(
        "click", lambda _=None: reconciler._callbacks.act(reconciler._editor.expand)
    )
    preview_control(reconciler, wrap, reconciler._editor.expand)


def build_generator_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click",
        lambda _=None, index=cell.generator: reconciler._callbacks.act(
            lambda: reconciler._editor.remove_mapping_row(index)
        ),
    )
    preview_rank_remove(reconciler, wrap, "row", cell.generator)


def build_generator_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-mapping").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(
            reconciler._editor.add_mapping_row, "mapping"
        ),
    )


def build_map_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    if cell.pending:
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
            "click",
            lambda _=None: reconciler._callbacks.act(reconciler._editor.cancel_pending_mapping_row),
        )
        return
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
        "click",
        lambda _=None, index=cell.generator: reconciler._callbacks.act(
            lambda: reconciler._editor.remove_mapping_row(index)
        ),
    )
    preview_rank_remove(reconciler, wrap, "row", cell.generator)


def build_map_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-mapping").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(
            reconciler._editor.add_mapping_row, "mapping"
        ),
    )


def build_basis_minus(reconciler, _callbacks: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button-v").on(
        "click", lambda _=None: reconciler._callbacks.act(reconciler._editor.shrink)
    )
    preview_control(reconciler, wrap, reconciler._editor.shrink)


def build_comma_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell,
        wrap,
        reconciler._editor.cancel_pending_comma,
        reconciler._editor.remove_comma,
        rank_axis="comma",
    )


def build_comma_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-comma").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(reconciler._editor.add_comma, "comma"),
    )


def build_element_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-element").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(
            reconciler._editor.add_element, "element"
        ),
    )


def build_element_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    action = (
        reconciler._editor.remove_element
        if cell.id.endswith(":pending")
        else (lambda index=cell.prime: reconciler._editor.remove_domain_element(index))
    )
    button = "rtt-minus-button-v" if ":basis" in cell.id else "rtt-minus-button"
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes(f"rtt-glyph {button}").on(
        "click", lambda _=None: reconciler._callbacks.act(action)
    )
    preview_control(reconciler, wrap, action)


def _build_list_minus(
    reconciler, cell: spreadsheet.Cell, wrap, cancel, remove, rank_axis=None
) -> None:
    pending = cell.id.endswith(":pending")
    action = cancel if pending else (lambda index=cell.comma: remove(index))
    wrap.classes("rtt-minus-zone")
    ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-button").on(
        "click", lambda _=None: reconciler._callbacks.act(action)
    )
    if rank_axis is not None and not pending:
        preview_rank_remove(reconciler, wrap, rank_axis, cell.comma)
    else:
        preview_control(reconciler, wrap, action)


def build_interest_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell,
        wrap,
        reconciler._editor.cancel_pending_interest,
        reconciler._editor.remove_interest,
    )


def build_interest_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-interest").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(
            reconciler._editor.add_interest, "interest"
        ),
    )


def build_held_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell,
        wrap,
        reconciler._editor.cancel_pending_held,
        reconciler._editor.remove_held,
    )


def build_held_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-held").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(reconciler._editor.add_held, "held"),
    )


def build_target_minus(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_list_minus(
        reconciler,
        cell,
        wrap,
        reconciler._editor.cancel_pending_target,
        reconciler._editor.remove_target,
    )


def build_target_plus(reconciler, _callbacks: spreadsheet.Cell, _wrap) -> None:
    ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fan-button rtt-hk-target").on(
        "click",
        lambda _=None: reconciler._callbacks.add_interval(reconciler._editor.add_target, "target"),
    )


def build_subcolumngrip(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    # HTML5 DnD: an element is only a valid drop target if it preventDefaults dragover, so each grip
    # is both drag source and drop target with its own client-side dragover preventDefault.
    _, lst, tail = cell.id.split(":")
    wrap.on("dragover", js_handler="(e) => e.preventDefault()")
    if tail == "add":
        wrap.classes("rtt-subcolumn-grip rtt-subcolumn-drop")
        wrap.on(
            "dragenter.prevent",
            lambda _=None, which=lst: reconciler._callbacks.on_drag_enter(which, None),
        )
        wrap.on(
            "drop.prevent", lambda _=None, which=lst: reconciler._callbacks.on_drop(which, None)
        )
        return
    index = cell.comma
    wrap.classes("rtt-drag-handle rtt-subcolumn-grip").props("draggable=true")
    wrap.on(
        "dragstart",
        lambda _=None, which=lst, i=index: reconciler._callbacks.on_drag_start(which, i),
    )
    wrap.on(
        "dragenter.prevent",
        lambda _=None, which=lst, i=index: reconciler._callbacks.on_drag_enter(which, i),
    )
    wrap.on("dragend", lambda _=None: reconciler._callbacks.on_drag_end())
    wrap.on(
        "drop.prevent", lambda _=None, which=lst, i=index: reconciler._callbacks.on_drop(which, i)
    )
    ui.icon("drag_indicator").classes("rtt-grip")


def _build_bandgrip(reconciler, cell: spreadsheet.Cell, wrap, axis: str, css: str) -> None:
    key = cell.id.split(":", 1)[1]
    wrap.classes(f"rtt-drag-handle {css}").props("draggable=true")
    wrap.on("dragstart", lambda _=None, k=key: reconciler._callbacks.on_band_drag_start(axis, k))
    wrap.on("dragstart", js_handler=_INERT_FLANKING_GAPS_JS)
    wrap.on("dragend", js_handler=_CLEAR_INERT_GAPS_JS)
    wrap.on("dragend", lambda _=None: reconciler._callbacks.on_band_drag_end())
    ui.icon("drag_indicator").classes("rtt-grip")


def _build_bandgap(reconciler, cell: spreadsheet.Cell, wrap, axis: str, css: str) -> None:
    # HTML5 DnD: an element is only a drop target if it preventDefaults dragover, so each gap arms its
    # own client-side dragover preventDefault. The before-key rides the cell id (empty tail = the end).
    before_key = cell.id.split(":", 1)[1]
    wrap.classes(css)
    wrap.on("dragover", js_handler="(e) => e.preventDefault()")
    wrap.on(
        "drop.prevent",
        lambda _=None, k=before_key: reconciler._callbacks.on_band_drop(axis, k),
    )


def build_columngrip(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_bandgrip(reconciler, cell, wrap, "column", "rtt-column-grip")


def build_rowgrip(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_bandgrip(reconciler, cell, wrap, "row", "rtt-row-grip")


def build_colgap(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_bandgap(reconciler, cell, wrap, "column", "rtt-band-gap rtt-col-gap")


def build_rowgap(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_bandgap(reconciler, cell, wrap, "row", "rtt-band-gap rtt-row-gap")
