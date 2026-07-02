from __future__ import annotations

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


def build_prescaler_cell(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(
        reconciler,
        cell_box,
        wrap,
        lambda _e=None, cell_id=cell_box.id: reconciler._cell_box.on_prescaler_change(cell_id),
    )


def update_prescaler_cell(reconciler, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(reconciler, cell_box, cell_box.text)


def build_weight_cell(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(
        reconciler,
        cell_box,
        wrap,
        lambda _e=None, cell_id=cell_box.id: reconciler._cell_box.on_weight_change(cell_id),
    )


def update_weight_cell(reconciler, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(reconciler, cell_box, cell_box.text)


def build_power_input(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-cell-input rtt-cell-stacked")
    reconciler.cells[cell_box.id].value.input = (
        ui.input(
            on_change=lambda _e, cell_id=cell_box.id: reconciler._cell_box.on_power_change(cell_id)
        )
        .props("dense borderless")
        .classes("rtt-cell-input-field")
    )
    _put_stacked_face(
        reconciler,
        cell_box.id,
        "rtt-tuning-value rtt-cell-face",
        *_power_parts(cell_box.text),
        cell_box.width,
    )


def update_power_input(reconciler, cell_box: spreadsheet.CellBox) -> None:
    reconciler.cells[cell_box.id].value.input.value = cell_box.text
    _sync_stacked_face(reconciler, cell_box.id, *_power_parts(cell_box.text))


def build_power_display(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    _put_stacked_face(
        reconciler,
        cell_box.id,
        "rtt-tuning-value rtt-cell-face",
        *_power_parts(cell_box.text),
        cell_box.width,
    )


def update_power_display(reconciler, cell_box: spreadsheet.CellBox) -> None:
    _sync_stacked_face(reconciler, cell_box.id, *_power_parts(cell_box.text))


def build_generator_tuning_cell(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    i = int(cell_box.id.rsplit(":", 1)[1])
    _build_decimal(
        reconciler,
        cell_box,
        wrap,
        lambda _e=None, cell_id=cell_box.id: reconciler._cell_box.on_generator_tuning_change(
            cell_id
        ),
        generator_index=i,
    )
    wrap.on(
        "wheel",
        lambda e, cell_id=cell_box.id: reconciler._cell_box.on_generator_tuning_wheel(
            cell_id, e.args.get("deltaY")
        ),
        args=["deltaY"],
        js_handler=_INT_WHEEL_JS,
    )
    wrap.on(
        "mouseenter",
        lambda _=None, cell_id=cell_box.id: reconciler._cell_box.generator_tuning_hover(cell_id),
    )
    wrap.on(
        "mouseleave",
        lambda _=None, cell_id=cell_box.id: reconciler._cell_box.generator_tuning_unhover(cell_id),
    )


def update_generator_tuning_cell(reconciler, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(reconciler, cell_box, "" if cell_box.blank else cell_box.text, signed=True)


def build_plain_text_edit(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    if cell_box.id.startswith("plain_text:projection:"):
        inp = ui.input(value=cell_box.text).props("dense borderless").classes("rtt-plain-text-edit")
        inp.on(
            "blur",
            lambda _e=None, cell_id=cell_box.id: reconciler._cell_box.on_plain_text_edit(
                cell_id, reconciler.cells[cell_id].value.plain_text_input.value
            ),
        )
    else:
        inp = (
            ui.input(
                value=cell_box.text,
                on_change=lambda e, cell_id=cell_box.id: reconciler._cell_box.on_plain_text_edit(
                    cell_id, e.value
                ),
            )
            .props("dense borderless")
            .classes("rtt-plain-text-edit")
        )
    reconciler.cells[cell_box.id].value.plain_text_input = inp


def update_plain_text_edit(reconciler, cell_box: spreadsheet.CellBox) -> None:
    reconciler.cells[cell_box.id].value.plain_text_input.value = cell_box.text
    reconciler.cells[cell_box.id].value.plain_text_input.style(
        f"font-size:{_plain_text_font(cell_box.text, cell_box.width)}px"
    )


def build_generator_ratio(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(reconciler, cell_box, wrap, approx=True)


def build_comma_ratio(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(reconciler, cell_box, wrap, approx=False)


def build_mapped(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    _ratio(reconciler, cell_box, approx=False)


def _build_ratio_face(reconciler, cell_box: spreadsheet.CellBox, wrap, approx: bool) -> None:
    if cell_box.pending:
        wrap.classes(add="rtt-pending")
    if cell_box.pending and cell_box.text in ("?", "?/?", ""):
        reconciler.cells[cell_box.id].value.label = ui.label(cell_box.text).classes(
            "rtt-value rtt-pending-q"
        )
    else:
        _ratio(reconciler, cell_box, approx=approx)


def update_ratio(reconciler, cell_box: spreadsheet.CellBox) -> None:
    _set_pending_class(reconciler.entities[cell_box.id].element, cell_box.pending)
    face = reconciler.handles(cell_box.id).value.ratio_face
    if face is None:
        return
    face.clear()
    reconciler.cells[cell_box.id].value.frac = None
    reconciler.cells[cell_box.id].value.label = None
    with face:
        _ratio_body(reconciler, cell_box, approx=(cell_box.kind == "generator_ratio"))


def build_tuning_value(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    cents_face(reconciler, cell_box, "rtt-tuning-value")


def update_tuning_value(reconciler, cell_box: spreadsheet.CellBox) -> None:
    set_cents_face(reconciler, cell_box.id, cell_box.text)
    _set_pending_class(reconciler.entities[cell_box.id].element, cell_box.pending)


def label_builder(cls: str):
    def build(reconciler, cell_box, _wrap):
        reconciler.cells[cell_box.id].value.label = ui.label(cell_box.text).classes(cls)

    return build


def update_label(reconciler, cell_box: spreadsheet.CellBox) -> None:
    reconciler.cells[cell_box.id].value.label.set_text(cell_box.text)
    _set_pending_class(reconciler.entities[cell_box.id].element, cell_box.pending)


def update_plain_text(reconciler, cell_box: spreadsheet.CellBox) -> None:
    reconciler.cells[cell_box.id].value.label.set_text(cell_box.text)
    reconciler.cells[cell_box.id].value.label.style(
        f"font-size:{_plain_text_font(cell_box.text, cell_box.width)}px"
    )
