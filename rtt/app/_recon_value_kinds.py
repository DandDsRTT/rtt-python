from __future__ import annotations

import html
import math

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
    _CELL_FONT,
    _INT_WHEEL_JS,
)
from rtt.app.render_html import (
    _digit_fit_font,
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


_RADICAL_SIGN = "√"


def build_radical(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-radical")
    face = ui.element("div").classes("rtt-radical-face")
    reconciler.cells[cell.id].value.ratio_face = face
    with face:
        _radical_body(cell.text, cell.width)


def update_radical(reconciler, cell: spreadsheet.Cell) -> None:
    face = reconciler.handles(cell.id).value.ratio_face
    if face is None:
        return
    face.clear()
    with face:
        _radical_body(cell.text, cell.width)


def _radical_body(text: str, width: float) -> None:
    decimal = _collapsed_decimal(text)
    if decimal is not None:
        _fit_decimal_label(decimal, width)
    elif _RADICAL_SIGN in text:
        index, radicand = text.split(_RADICAL_SIGN, 1)
        ui.html(_radical_svg(index, radicand))
    else:
        ui.label(text).classes("rtt-radical-body")


_RADICAL_FRAC_MAX = 4


def _collapsed_decimal(text: str) -> str | None:
    if _RADICAL_SIGN in text:
        index, radicand = text.split(_RADICAL_SIGN, 1)
    else:
        index, radicand = "1", text
    num, den = radicand.split("/", 1) if "/" in radicand else (radicand, "1")
    if not num.lstrip("-").isdigit() or not den.lstrip("-").isdigit():
        return None
    if max(len(num), len(den)) <= _RADICAL_FRAC_MAX:
        return None
    return "~" + _radical_resolved_decimal(index, num, den)


def _fit_decimal_label(text: str, width: float) -> None:
    ui.label(text).classes("rtt-radical-body").style(
        f"font-size:{_digit_fit_font(len(text), width, float(_CELL_FONT))}px"
    )


def _radical_svg(index: str, radicand: str) -> str:
    if "/" in radicand:
        num, den = radicand.split("/", 1)
        return _radical_fraction_svg(index, num, den)
    return _radical_single_svg(index, radicand)


def _radical_resolved_decimal(index: str, num: str, den: str) -> str:
    try:
        value = math.exp((math.log(int(num)) - math.log(int(den))) / int(index))
        return f"{value:.3f}"
    except (ValueError, ZeroDivisionError, OverflowError):
        return f"{num}/{den}"


def _radical_single_svg(index: str, radicand: str) -> str:
    span = max(len(radicand), 1) * 9
    apex = 14
    end = apex + 3 + span
    center = apex + 3 + span / 2
    return (
        f'<svg class="rtt-radical-svg" viewBox="0 0 {end + 1} 26" height="22" '
        f'role="img" aria-label="{index} root of {radicand}">'
        f'<path d="M2,14 L5,11 L9,23 L{apex},4 L{end},4" fill="none" stroke="currentColor" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<text class="rtt-radical-index" x="8" y="9" text-anchor="middle">{index}</text>'
        f'<text class="rtt-radical-radicand" x="{center}" y="17" '
        f'text-anchor="middle" dominant-baseline="middle">{radicand}</text>'
        f"</svg>"
    )


def _radical_fraction_svg(index: str, numerator: str, denominator: str) -> str:
    column = max(len(numerator), len(denominator), 1) * 8
    apex = 15
    left = apex + 3
    end = left + column + 2
    center = left + column / 2
    return (
        f'<svg class="rtt-radical-svg rtt-radical-tall" viewBox="0 0 {end + 1} 29" height="30" '
        f'role="img" aria-label="{index} root of {numerator} over {denominator}">'
        f'<path d="M2,15 L5,12 L9,26 L{apex},3 L{end},3" fill="none" stroke="currentColor" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<text class="rtt-radical-index" x="8" y="9" text-anchor="middle">{index}</text>'
        f'<text class="rtt-radical-frac" x="{center}" y="14" text-anchor="middle">{numerator}</text>'
        f'<line x1="{left}" y1="16" x2="{end - 2}" y2="16" stroke="currentColor" stroke-width="1"/>'
        f'<text class="rtt-radical-frac" x="{center}" y="27" text-anchor="middle">{denominator}</text>'
        f"</svg>"
    )


def _build_ratio_face(reconciler, cell: spreadsheet.Cell, wrap, approx: bool) -> None:
    if cell.pending:
        wrap.classes(add="rtt-pending")
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
