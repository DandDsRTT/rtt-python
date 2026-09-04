from __future__ import annotations

import html

from nicegui import ui

from rtt.app import (
    spreadsheet,
)
from rtt.app._recon_value import (
    _build_decimal,
    _put_stacked_face,
    _ratio,
    _ratio_body,
    _set_pending_class,
    _sync_stacked_face,
    _update_decimal,
    cents_face,
    set_cents_face,
)
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
)
from rtt.app.render_html import (
    _plain_text_font,
    _power_parts,
)


def build_prescaler_cell(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_decimal(
        reconciler,
        cell,
        wrap,
        lambda _e=None, cell_id=cell.id: reconciler._callbacks.on_prescaler_change(cell_id),
    )


def update_prescaler_cell(reconciler, cell: spreadsheet.Cell) -> None:
    _update_decimal(reconciler, cell, cell.text)


def build_weight_cell(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_decimal(
        reconciler,
        cell,
        wrap,
        lambda _e=None, cell_id=cell.id: reconciler._callbacks.on_weight_change(cell_id),
    )


def update_weight_cell(reconciler, cell: spreadsheet.Cell) -> None:
    _update_decimal(reconciler, cell, cell.text)


def build_power_input(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-cell-input rtt-cell-stacked")
    reconciler.cells[cell.id].value.input = (
        ui.input(
            on_change=lambda _e, cell_id=cell.id: reconciler._callbacks.on_power_change(cell_id)
        )
        .props("dense borderless")
        .classes("rtt-cell-input-field")
    )
    _put_stacked_face(
        reconciler,
        cell.id,
        "rtt-tuning-value rtt-cell-face",
        *_power_parts(cell.text),
        cell.width,
    )


def update_power_input(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].value.input.value = cell.text
    _sync_stacked_face(reconciler, cell.id, *_power_parts(cell.text))


def build_power_display(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    _put_stacked_face(
        reconciler,
        cell.id,
        "rtt-tuning-value rtt-cell-face",
        *_power_parts(cell.text),
        cell.width,
    )


def update_power_display(reconciler, cell: spreadsheet.Cell) -> None:
    _sync_stacked_face(reconciler, cell.id, *_power_parts(cell.text))


def build_generator_tuning_cell(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    i = int(cell.id.rsplit(":", 1)[1])
    _build_decimal(
        reconciler,
        cell,
        wrap,
        lambda _e=None, cell_id=cell.id: reconciler._callbacks.on_generator_tuning_change(cell_id),
        generator_index=i,
    )
    wrap.on(
        "wheel",
        lambda e, cell_id=cell.id: reconciler._callbacks.on_generator_tuning_wheel(
            cell_id, e.args.get("deltaY")
        ),
        args=["deltaY"],
        js_handler=_INT_WHEEL_JS,
    )
    wrap.on(
        "mouseenter",
        lambda _=None, cell_id=cell.id: reconciler._callbacks.generator_tuning_hover(cell_id),
    )
    wrap.on(
        "mouseleave",
        lambda _=None, cell_id=cell.id: reconciler._callbacks.generator_tuning_unhover(cell_id),
    )


def update_generator_tuning_cell(reconciler, cell: spreadsheet.Cell) -> None:
    _update_decimal(reconciler, cell, "" if cell.blank else cell.text, signed=True)


def build_plain_text_edit(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    if cell.id.startswith("plain_text:projection:"):
        inp = ui.input(value=cell.text).props("dense borderless").classes("rtt-plain-text-edit")
        inp.on(
            "blur",
            lambda _e=None, cell_id=cell.id: reconciler._callbacks.on_plain_text_edit(
                cell_id, reconciler.cells[cell_id].value.plain_text_input.value
            ),
        )
    else:
        inp = (
            ui.input(
                value=cell.text,
                on_change=lambda e, cell_id=cell.id: reconciler._callbacks.on_plain_text_edit(
                    cell_id, e.value
                ),
            )
            .props("dense borderless")
            .classes("rtt-plain-text-edit")
        )
    reconciler.cells[cell.id].value.plain_text_input = inp


def update_plain_text_edit(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].value.plain_text_input.value = cell.text
    reconciler.cells[cell.id].value.plain_text_input.style(
        f"font-size:{_plain_text_font(cell.text, cell.width)}px"
    )


def build_generator_ratio(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_ratio_face(reconciler, cell, wrap, approx=True)


def build_comma_ratio(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    _build_ratio_face(reconciler, cell, wrap, approx=False)


def build_mapped(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    _ratio(reconciler, cell, approx=False)


def _build_ratio_face(reconciler, cell: spreadsheet.Cell, wrap, approx: bool) -> None:
    if cell.pending:
        wrap.classes(add="rtt-pending")
    if cell.pending and cell.text in ("?", "?/?", ""):
        reconciler.cells[cell.id].value.label = ui.label(cell.text).classes(
            "rtt-value rtt-pending-q"
        )
    else:
        _ratio(reconciler, cell, approx=approx)


def update_ratio(reconciler, cell: spreadsheet.Cell) -> None:
    _set_pending_class(reconciler.entities[cell.id].element, cell.pending)
    face = reconciler.handles(cell.id).value.ratio_face
    if face is None:
        return
    face.clear()
    reconciler.cells[cell.id].value.frac = None
    reconciler.cells[cell.id].value.label = None
    with face:
        _ratio_body(reconciler, cell, approx=(cell.kind == "generator_ratio"))


def build_tuning_value(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    cents_face(reconciler, cell, "rtt-tuning-value")


def update_tuning_value(reconciler, cell: spreadsheet.Cell) -> None:
    set_cents_face(reconciler, cell.id, cell.text)
    _set_pending_class(reconciler.entities[cell.id].element, cell.pending)


def column_header_html(text: str) -> str:
    return '<span class="rtt-header-break"> </span>'.join(
        html.escape(line) for line in text.split("\n")
    )


def build_column_header(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].value.label = ui.html(column_header_html(cell.text)).classes(
        "rtt-column-header"
    )


def update_column_header(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].value.label.set_content(column_header_html(cell.text))
    _set_pending_class(reconciler.entities[cell.id].element, cell.pending)


def label_builder(cls: str):
    def build(reconciler, cell, _wrap):
        reconciler.cells[cell.id].value.label = ui.label(cell.text).classes(cls)

    return build


def update_label(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].value.label.set_text(cell.text)
    _set_pending_class(reconciler.entities[cell.id].element, cell.pending)


def update_plain_text(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].value.label.set_text(cell.text)
    reconciler.cells[cell.id].value.label.style(
        f"font-size:{_plain_text_font(cell.text, cell.width)}px"
    )
