from __future__ import annotations

from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    spreadsheet_text,
)
from rtt.app.marks import (
    ebk_svg,
)
from rtt.app.page_assets import (
    _EBK_SQUARE,
    _MATRIX_LABEL_FONT,
    _MATRIX_LABEL_MIN_FONT,
    _TRANSPOSE_MARK,
    _UNITS_MAX_FONT,
)
from rtt.app.render_html import (
    _bar_chart,
    _math_expression_html,
    _math_html,
    _plain_text_font,
    _range_chart,
    _run_html,
    _underline_html,
    _units_font,
    _units_html,
)


def _pending_html(prefix: str, draft: str, suffix: str) -> str:
    return (
        f"{_run_html(prefix)}"
        f"<span class='rtt-pending-q'>{_run_html(draft)}</span>"
        f"{_run_html(suffix)}"
    )


def build_svgfill(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].display.html = ui.html("").classes("rtt-svgfill")


def update_ebk(reconciler, cell: spreadsheet.Cell) -> None:
    if reconciler.handles(cell.id).display.ebk_size != (
        cell.width,
        cell.height,
        cell.pending,
    ):
        reconciler.cells[cell.id].display.html.set_content(ebk_svg(cell))
        reconciler.cells[cell.id].display.ebk_size = (
            cell.width,
            cell.height,
            cell.pending,
        )


def update_chart(reconciler, cell: spreadsheet.Cell) -> None:
    key = (
        cell.width,
        cell.height,
        cell.values,
        cell.indicator,
        cell.indicator_label,
        cell.column_gap,
    )
    if reconciler.handles(cell.id).display.chart_key != key:
        reconciler.cells[cell.id].display.html.set_content(
            _bar_chart(
                cell.width,
                cell.height,
                cell.values,
                cell.indicator,
                cell.indicator_label,
                cell.column_gap,
            )
        )
        reconciler.cells[cell.id].display.chart_key = key


def update_rangechart(reconciler, cell: spreadsheet.Cell) -> None:
    key = (cell.width, cell.height, cell.ranges, cell.values, cell.decimals)
    if reconciler.handles(cell.id).display.range_key != key:
        reconciler.cells[cell.id].display.html.set_content(
            _range_chart(cell.width, cell.height, cell.ranges, cell.values, cell.decimals)
        )
        reconciler.cells[cell.id].display.range_key = key


def build_count(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].display.math_cell = ui.html("").classes("rtt-count")


def build_symbol(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-symbol-cell")
    cls = (
        "rtt-symbol rtt-optimization-1line" if cell.id.startswith("optimization:") else "rtt-symbol"
    )
    reconciler.cells[cell.id].display.math_cell = ui.html("").classes(cls)


def _matrix_label_classes(text: str) -> str:
    return (
        "rtt-matrix-label rtt-matrix-label-norm"
        if ("‖" in text or " " in text)
        else "rtt-matrix-label"
    )


def build_matrix_label(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-matrix-label-cell")
    reconciler.cells[cell.id].display.math_cell = ui.html("").classes(
        _matrix_label_classes(cell.text)
    )


def build_units(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-units-cell")
    reconciler.cells[cell.id].display.math_cell = ui.html("").classes("rtt-units")


def update_mathcell(reconciler, cell: spreadsheet.Cell) -> None:
    if cell.kind == "units":
        html = _units_html(cell.text)
        if reconciler.handles(cell.id).display.math_rendered != (html, cell.width):
            reconciler.cells[cell.id].display.math_cell.set_content(html)
            reconciler.cells[cell.id].display.math_cell.style(
                f"font-size:{_units_font(cell.text, cell.width, _UNITS_MAX_FONT):.2f}px"
            )
            reconciler.cells[cell.id].display.math_rendered = (html, cell.width)
        return
    html = _math_html(cell.text)
    font = None
    if (
        cell.kind == "matrix_label"
        and ":column:" in cell.id
        and "‖" not in cell.text
        and " " not in cell.text
    ):
        width = spreadsheet_text._min_width_for_lines(cell.text, 1, _MATRIX_LABEL_FONT)
        if width > cell.width - 2:
            font = max(_MATRIX_LABEL_MIN_FONT, _MATRIX_LABEL_FONT * (cell.width - 2) / width)
    if reconciler.handles(cell.id).display.math_rendered != (html, font):
        reconciler.cells[cell.id].display.math_cell.set_content(html)
        if font is not None:
            reconciler.cells[cell.id].display.math_cell.style(f"font-size:{font:.2f}px")
        reconciler.cells[cell.id].display.math_rendered = (html, font)
        if cell.kind == "matrix_label":
            reconciler.cells[cell.id].display.math_cell.classes(
                replace=_matrix_label_classes(cell.text)
            )
        if cell.id == "optimization:mean_damage:symbol":
            wide = "‖" in cell.text
            reconciler.cells[cell.id].display.math_cell.classes(
                replace="rtt-symbol rtt-optimization-1line rtt-optimization-wide"
                if wide
                else "rtt-symbol rtt-optimization-1line"
            )


def build_caption(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-caption-cell")
    one_line = cell.id.startswith("optimization:") and cell.id != "optimization:mean_damage:caption"
    cls = "rtt-caption rtt-optimization-1line" if one_line else "rtt-caption"
    if cell.align == "left":
        cls += " rtt-caption-left"
    reconciler.cells[cell.id].display.caption = ui.html("").classes(cls)


def update_caption(reconciler, cell: spreadsheet.Cell) -> None:
    html = _underline_html(cell.text, cell.underlines)
    if reconciler.handles(cell.id).display.caption_html != html:
        reconciler.cells[cell.id].display.caption.set_content(html)
        reconciler.cells[cell.id].display.caption_html = html
    reconciler.cells[cell.id].display.caption.classes(
        add="rtt-caption-disabled" if cell.disabled else "",
        remove="" if cell.disabled else "rtt-caption-disabled",
    )


def build_plain_text_pending(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].display.html = ui.html("").classes("rtt-plain-text-pending")


def _squared(off, prefix, draft, suffix, vector_based):
    if not off:
        return prefix, draft, suffix
    return (
        prefix.translate(_EBK_SQUARE),
        draft.translate(_EBK_SQUARE),
        suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
    )


def update_plain_text_pending(reconciler, cell: spreadsheet.Cell) -> None:
    ed = reconciler._editor
    off = not ed.settings.get("ebk", True)
    if cell.id == "plain_text:mapping:primes":
        committed = service.simple_matrix_to_ebk(cell.text, False) if off else cell.text
        prefix, draft, suffix = _squared(
            off, *service.mapping_pending_text(committed, ed.pending_mapping_row), False
        )
        reconciler.cells[cell.id].display.html.set_content(_pending_html(prefix, draft, suffix))
        reconciler.cells[cell.id].display.html.style(
            f"font-size:{_plain_text_font(prefix + draft + suffix, cell.width)}px"
        )
        return
    if cell.id == "plain_text:vectors:targets":
        targets = ed.target_override or service.target_interval_set(
            ed.target_spec, ed.state.domain_basis
        )
        committed = service.target_interval_vectors(
            targets, ed.state.dimensionality, ed.state.domain_basis
        )
        pending = ed.pending_target
    else:
        committed, pending = ed.state.comma_basis, ed.pending_comma
    prefix, draft, suffix = _squared(
        off, *service.vector_list_pending_text(committed, pending), True
    )
    reconciler.cells[cell.id].display.html.set_content(_pending_html(prefix, draft, suffix))
    reconciler.cells[cell.id].display.html.style(
        f"font-size:{_plain_text_font(prefix + draft + suffix, cell.width)}px"
    )


def build_math_expression(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].display.expr = ui.html("").classes("rtt-math-expression")


def update_math_expression(reconciler, cell: spreadsheet.Cell) -> None:
    if reconciler.handles(cell.id).display.expr_state != (cell.text, cell.width):
        reconciler.cells[cell.id].display.expr.set_content(
            _math_expression_html(cell.text, cell.width)
        )
        reconciler.cells[cell.id].display.expr_state = (cell.text, cell.width)
