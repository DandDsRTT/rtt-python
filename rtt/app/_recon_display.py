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
    _MATLABEL_FONT,
    _MATLABEL_MIN_FONT,
    _TRANSPOSE_MARK,
    _UNITS_MAX_FONT,
)
from rtt.app.render_html import (
    _bar_chart,
    _math_html,
    _mathexpr_html,
    _plain_text_font,
    _range_chart,
    _underline_html,
    _units_font,
    _units_html,
)


def build_svgfill(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    reconciler.cells[cell_box.id].display.html = ui.html("").classes("rtt-svgfill")


def update_ebk(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if reconciler.handles(cell_box.id).display.ebk_size != (
        cell_box.width,
        cell_box.height,
        cell_box.pending,
    ):
        reconciler.cells[cell_box.id].display.html.set_content(ebk_svg(cell_box))
        reconciler.cells[cell_box.id].display.ebk_size = (
            cell_box.width,
            cell_box.height,
            cell_box.pending,
        )


def update_chart(reconciler, cell_box: spreadsheet.CellBox) -> None:
    key = (
        cell_box.width,
        cell_box.height,
        cell_box.values,
        cell_box.indicator,
        cell_box.indicator_label,
        cell_box.column_gap,
    )
    if reconciler.handles(cell_box.id).display.chart_key != key:
        reconciler.cells[cell_box.id].display.html.set_content(
            _bar_chart(
                cell_box.width,
                cell_box.height,
                cell_box.values,
                cell_box.indicator,
                cell_box.indicator_label,
                cell_box.column_gap,
            )
        )
        reconciler.cells[cell_box.id].display.chart_key = key


def update_rangechart(reconciler, cell_box: spreadsheet.CellBox) -> None:
    key = (cell_box.width, cell_box.height, cell_box.ranges, cell_box.values, cell_box.decimals)
    if reconciler.handles(cell_box.id).display.range_key != key:
        reconciler.cells[cell_box.id].display.html.set_content(
            _range_chart(
                cell_box.width, cell_box.height, cell_box.ranges, cell_box.values, cell_box.decimals
            )
        )
        reconciler.cells[cell_box.id].display.range_key = key


def build_count(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    reconciler.cells[cell_box.id].display.math_cell = ui.html("").classes("rtt-count")


def build_symbol(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-symbol-cell")
    cls = "rtt-symbol rtt-opt-1line" if cell_box.id.startswith("optimization:") else "rtt-symbol"
    reconciler.cells[cell_box.id].display.math_cell = ui.html("").classes(cls)


def _matlabel_classes(text: str) -> str:
    return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"


def build_matlabel(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-matlabel-cell")
    reconciler.cells[cell_box.id].display.math_cell = ui.html("").classes(
        _matlabel_classes(cell_box.text)
    )


def build_units(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-units-cell")
    reconciler.cells[cell_box.id].display.math_cell = ui.html("").classes("rtt-units")


def update_mathcell(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if cell_box.kind == "units":
        html = _units_html(cell_box.text)
        if reconciler.handles(cell_box.id).display.math_rendered != (html, cell_box.width):
            reconciler.cells[cell_box.id].display.math_cell.set_content(html)
            reconciler.cells[cell_box.id].display.math_cell.style(
                f"font-size:{_units_font(cell_box.text, cell_box.width, _UNITS_MAX_FONT):.2f}px"
            )
            reconciler.cells[cell_box.id].display.math_rendered = (html, cell_box.width)
        return
    html = _math_html(cell_box.text)
    font = None
    if (
        cell_box.kind == "matlabel"
        and ":col:" in cell_box.id
        and "‖" not in cell_box.text
        and " " not in cell_box.text
    ):
        width = spreadsheet_text._min_width_for_lines(cell_box.text, 1, _MATLABEL_FONT)
        if width > cell_box.width - 2:
            font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cell_box.width - 2) / width)
    if reconciler.handles(cell_box.id).display.math_rendered != (html, font):
        reconciler.cells[cell_box.id].display.math_cell.set_content(html)
        if font is not None:
            reconciler.cells[cell_box.id].display.math_cell.style(f"font-size:{font:.2f}px")
        reconciler.cells[cell_box.id].display.math_rendered = (html, font)
        if cell_box.kind == "matlabel":
            reconciler.cells[cell_box.id].display.math_cell.classes(
                replace=_matlabel_classes(cell_box.text)
            )
        if cell_box.id == "optimization:mean_damage:symbol":
            wide = "‖" in cell_box.text
            reconciler.cells[cell_box.id].display.math_cell.classes(
                replace="rtt-symbol rtt-opt-1line rtt-opt-wide"
                if wide
                else "rtt-symbol rtt-opt-1line"
            )


def build_caption(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-caption-cell")
    one_line = (
        cell_box.id.startswith("optimization:")
        and cell_box.id != "optimization:mean_damage:caption"
    )
    cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
    if cell_box.align == "left":
        cls += " rtt-caption-left"
    reconciler.cells[cell_box.id].display.caption = ui.html("").classes(cls)


def update_caption(reconciler, cell_box: spreadsheet.CellBox) -> None:
    html = _underline_html(cell_box.text, cell_box.underlines)
    if reconciler.handles(cell_box.id).display.caption_html != html:
        reconciler.cells[cell_box.id].display.caption.set_content(html)
        reconciler.cells[cell_box.id].display.caption_html = html
    reconciler.cells[cell_box.id].display.caption.classes(
        add="rtt-caption-disabled" if cell_box.disabled else "",
        remove="" if cell_box.disabled else "rtt-caption-disabled",
    )


def build_plain_text_pending(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    reconciler.cells[cell_box.id].display.html = ui.html("").classes("rtt-plain-text-pending")


def _squared(off, prefix, draft, suffix, vector_based):
    if not off:
        return prefix, draft, suffix
    return (
        prefix.translate(_EBK_SQUARE),
        draft.translate(_EBK_SQUARE),
        suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
    )


def update_plain_text_pending(reconciler, cell_box: spreadsheet.CellBox) -> None:
    ed = reconciler._editor
    off = not ed.settings.get("ebk", True)
    if cell_box.id == "plain_text:mapping:primes":
        committed = service.simple_matrix_to_ebk(cell_box.text, False) if off else cell_box.text
        prefix, draft, suffix = _squared(
            off, *service.mapping_pending_text(committed, ed.pending_mapping_row), False
        )
        reconciler.cells[cell_box.id].display.html.set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
        )
        reconciler.cells[cell_box.id].display.html.style(
            f"font-size:{_plain_text_font(prefix + draft + suffix, cell_box.width)}px"
        )
        return
    if cell_box.id == "plain_text:vectors:targets":
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
    reconciler.cells[cell_box.id].display.html.set_content(
        f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
    )
    reconciler.cells[cell_box.id].display.html.style(
        f"font-size:{_plain_text_font(prefix + draft + suffix, cell_box.width)}px"
    )


def build_mathexpr(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    reconciler.cells[cell_box.id].display.expr = ui.html("").classes("rtt-mathexpr")


def update_mathexpr(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if reconciler.handles(cell_box.id).display.expr_state != (cell_box.text, cell_box.width):
        reconciler.cells[cell_box.id].display.expr.set_content(
            _mathexpr_html(cell_box.text, cell_box.width)
        )
        reconciler.cells[cell_box.id].display.expr_state = (cell_box.text, cell_box.width)
