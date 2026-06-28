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


def build_svgfill(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cell_box.id].display.html = ui.html("").classes("rtt-svgfill")


def update_ebk(rec, cell_box: spreadsheet.CellBox) -> None:
    if rec.handles(cell_box.id).display.ebk_size != (cell_box.w, cell_box.h, cell_box.pending):
        rec.cells[cell_box.id].display.html.set_content(ebk_svg(cell_box))
        rec.cells[cell_box.id].display.ebk_size = (cell_box.w, cell_box.h, cell_box.pending)


def update_chart(rec, cell_box: spreadsheet.CellBox) -> None:
    key = (
        cell_box.w,
        cell_box.h,
        cell_box.values,
        cell_box.indicator,
        cell_box.indicator_label,
        cell_box.col_gap,
    )
    if rec.handles(cell_box.id).display.chart_key != key:
        rec.cells[cell_box.id].display.html.set_content(
            _bar_chart(
                cell_box.w,
                cell_box.h,
                cell_box.values,
                cell_box.indicator,
                cell_box.indicator_label,
                cell_box.col_gap,
            )
        )
        rec.cells[cell_box.id].display.chart_key = key


def update_rangechart(rec, cell_box: spreadsheet.CellBox) -> None:
    key = (cell_box.w, cell_box.h, cell_box.ranges, cell_box.values, cell_box.decimals)
    if rec.handles(cell_box.id).display.range_key != key:
        rec.cells[cell_box.id].display.html.set_content(
            _range_chart(
                cell_box.w, cell_box.h, cell_box.ranges, cell_box.values, cell_box.decimals
            )
        )
        rec.cells[cell_box.id].display.range_key = key


def build_count(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cell_box.id].display.math_cell = ui.html("").classes("rtt-count")


def build_symbol(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-symbol-cell")
    cls = "rtt-symbol rtt-opt-1line" if cell_box.id.startswith("optimization:") else "rtt-symbol"
    rec.cells[cell_box.id].display.math_cell = ui.html("").classes(cls)


def _matlabel_classes(text: str) -> str:
    return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"


def build_matlabel(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-matlabel-cell")
    rec.cells[cell_box.id].display.math_cell = ui.html("").classes(_matlabel_classes(cell_box.text))


def build_units(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-units-cell")
    rec.cells[cell_box.id].display.math_cell = ui.html("").classes("rtt-units")


def update_mathcell(rec, cell_box: spreadsheet.CellBox) -> None:
    if cell_box.kind == "units":
        html = _units_html(cell_box.text)
        if rec.handles(cell_box.id).display.math_rendered != (html, cell_box.w):
            rec.cells[cell_box.id].display.math_cell.set_content(html)
            rec.cells[cell_box.id].display.math_cell.style(
                f"font-size:{_units_font(cell_box.text, cell_box.w, _UNITS_MAX_FONT):.2f}px"
            )
            rec.cells[cell_box.id].display.math_rendered = (html, cell_box.w)
        return
    html = _math_html(cell_box.text)
    font = None
    if (
        cell_box.kind == "matlabel"
        and ":col:" in cell_box.id
        and "‖" not in cell_box.text
        and " " not in cell_box.text
    ):
        w = spreadsheet_text._min_width_for_lines(cell_box.text, 1, _MATLABEL_FONT)
        if w > cell_box.w - 2:
            font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cell_box.w - 2) / w)
    if rec.handles(cell_box.id).display.math_rendered != (html, font):
        rec.cells[cell_box.id].display.math_cell.set_content(html)
        if font is not None:
            rec.cells[cell_box.id].display.math_cell.style(f"font-size:{font:.2f}px")
        rec.cells[cell_box.id].display.math_rendered = (html, font)
        if cell_box.kind == "matlabel":
            rec.cells[cell_box.id].display.math_cell.classes(
                replace=_matlabel_classes(cell_box.text)
            )
        if cell_box.id == "optimization:mean_damage:symbol":
            wide = "‖" in cell_box.text
            rec.cells[cell_box.id].display.math_cell.classes(
                replace="rtt-symbol rtt-opt-1line rtt-opt-wide"
                if wide
                else "rtt-symbol rtt-opt-1line"
            )


def build_caption(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-caption-cell")
    one_line = (
        cell_box.id.startswith("optimization:")
        and cell_box.id != "optimization:mean_damage:caption"
    )
    cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
    if cell_box.align == "left":
        cls += " rtt-caption-left"
    rec.cells[cell_box.id].display.caption = ui.html("").classes(cls)


def update_caption(rec, cell_box: spreadsheet.CellBox) -> None:
    html = _underline_html(cell_box.text, cell_box.underlines)
    if rec.handles(cell_box.id).display.caption_html != html:
        rec.cells[cell_box.id].display.caption.set_content(html)
        rec.cells[cell_box.id].display.caption_html = html
    rec.cells[cell_box.id].display.caption.classes(
        add="rtt-caption-disabled" if cell_box.disabled else "",
        remove="" if cell_box.disabled else "rtt-caption-disabled",
    )


def build_plain_text_pending(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cell_box.id].display.html = ui.html("").classes("rtt-ptextpending")


def _squared(off, prefix, draft, suffix, vector_based):
    if not off:
        return prefix, draft, suffix
    return (
        prefix.translate(_EBK_SQUARE),
        draft.translate(_EBK_SQUARE),
        suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
    )


def update_plain_text_pending(rec, cell_box: spreadsheet.CellBox) -> None:
    ed = rec._editor
    off = not ed.settings.get("ebk", True)
    if cell_box.id == "ptext:mapping:primes":
        committed = service.simple_matrix_to_ebk(cell_box.text, False) if off else cell_box.text
        prefix, draft, suffix = _squared(
            off, *service.mapping_pending_text(committed, ed.pending_mapping_row), False
        )
        rec.cells[cell_box.id].display.html.set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
        )
        rec.cells[cell_box.id].display.html.style(
            f"font-size:{_plain_text_font(prefix + draft + suffix, cell_box.w)}px"
        )
        return
    if cell_box.id == "ptext:vectors:targets":
        targets = ed.target_override or service.target_interval_set(
            ed.target_spec, ed.state.domain_basis
        )
        committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
        pending = ed.pending_target
    else:
        committed, pending = ed.state.comma_basis, ed.pending_comma
    prefix, draft, suffix = _squared(
        off, *service.vector_list_pending_text(committed, pending), True
    )
    rec.cells[cell_box.id].display.html.set_content(
        f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
    )
    rec.cells[cell_box.id].display.html.style(
        f"font-size:{_plain_text_font(prefix + draft + suffix, cell_box.w)}px"
    )


def build_mathexpr(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cell_box.id].display.expr = ui.html("").classes("rtt-mathexpr")


def update_mathexpr(rec, cell_box: spreadsheet.CellBox) -> None:
    if rec.handles(cell_box.id).display.expr_state != (cell_box.text, cell_box.w):
        rec.cells[cell_box.id].display.expr.set_content(_mathexpr_html(cell_box.text, cell_box.w))
        rec.cells[cell_box.id].display.expr_state = (cell_box.text, cell_box.w)
