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
    _ptext_font,
    _range_chart,
    _underline_html,
    _units_font,
    _units_html,
)


def build_svgfill(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cb.id].display.html = ui.html("").classes("rtt-svgfill")


def update_ebk(rec, cb: spreadsheet.CellBox) -> None:
    if rec.handles(cb.id).display.ebk_size != (cb.w, cb.h, cb.pending):
        rec.cells[cb.id].display.html.set_content(ebk_svg(cb))
        rec.cells[cb.id].display.ebk_size = (cb.w, cb.h, cb.pending)


def update_chart(rec, cb: spreadsheet.CellBox) -> None:
    key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label, cb.col_gap)
    if rec.handles(cb.id).display.chart_key != key:
        rec.cells[cb.id].display.html.set_content(
            _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label, cb.col_gap)
        )
        rec.cells[cb.id].display.chart_key = key


def update_rangechart(rec, cb: spreadsheet.CellBox) -> None:
    key = (cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
    if rec.handles(cb.id).display.range_key != key:
        rec.cells[cb.id].display.html.set_content(
            _range_chart(cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
        )
        rec.cells[cb.id].display.range_key = key


def build_count(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cb.id].display.math_cell = ui.html("").classes("rtt-count")


def build_symbol(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-symbol-cell")
    cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
    rec.cells[cb.id].display.math_cell = ui.html("").classes(cls)


def _matlabel_classes(text: str) -> str:
    return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"


def build_matlabel(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-matlabel-cell")
    rec.cells[cb.id].display.math_cell = ui.html("").classes(_matlabel_classes(cb.text))


def build_units(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-units-cell")
    rec.cells[cb.id].display.math_cell = ui.html("").classes("rtt-units")


def update_mathcell(rec, cb: spreadsheet.CellBox) -> None:
    if cb.kind == "units":
        html = _units_html(cb.text)
        if rec.handles(cb.id).display.math_rendered != (html, cb.w):
            rec.cells[cb.id].display.math_cell.set_content(html)
            rec.cells[cb.id].display.math_cell.style(
                f"font-size:{_units_font(cb.text, cb.w, _UNITS_MAX_FONT):.2f}px"
            )
            rec.cells[cb.id].display.math_rendered = (html, cb.w)
        return
    html = _math_html(cb.text)
    font = None
    if cb.kind == "matlabel" and ":col:" in cb.id and "‖" not in cb.text and " " not in cb.text:
        w = spreadsheet_text._min_width_for_lines(cb.text, 1, _MATLABEL_FONT)
        if w > cb.w - 2:
            font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cb.w - 2) / w)
    if rec.handles(cb.id).display.math_rendered != (html, font):
        rec.cells[cb.id].display.math_cell.set_content(html)
        if font is not None:
            rec.cells[cb.id].display.math_cell.style(f"font-size:{font:.2f}px")
        rec.cells[cb.id].display.math_rendered = (html, font)
        if cb.kind == "matlabel":
            rec.cells[cb.id].display.math_cell.classes(replace=_matlabel_classes(cb.text))
        if cb.id == "optimization:mean_damage:symbol":
            wide = "‖" in cb.text
            rec.cells[cb.id].display.math_cell.classes(
                replace="rtt-symbol rtt-opt-1line rtt-opt-wide"
                if wide
                else "rtt-symbol rtt-opt-1line"
            )


def build_caption(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-caption-cell")
    one_line = cb.id.startswith("optimization:") and cb.id != "optimization:mean_damage:caption"
    cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
    if cb.align == "left":
        cls += " rtt-caption-left"
    rec.cells[cb.id].display.caption = ui.html("").classes(cls)


def update_caption(rec, cb: spreadsheet.CellBox) -> None:
    html = _underline_html(cb.text, cb.underlines)
    if rec.handles(cb.id).display.caption_html != html:
        rec.cells[cb.id].display.caption.set_content(html)
        rec.cells[cb.id].display.caption_html = html
    rec.cells[cb.id].display.caption.classes(
        add="rtt-caption-disabled" if cb.disabled else "",
        remove="" if cb.disabled else "rtt-caption-disabled",
    )


def build_ptextpending(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cb.id].display.html = ui.html("").classes("rtt-ptextpending")


def _squared(off, prefix, draft, suffix, vector_based):
    if not off:
        return prefix, draft, suffix
    return (
        prefix.translate(_EBK_SQUARE),
        draft.translate(_EBK_SQUARE),
        suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
    )


def update_ptextpending(rec, cb: spreadsheet.CellBox) -> None:
    ed = rec._editor
    off = not ed.settings.get("ebk", True)
    if cb.id == "ptext:mapping:primes":
        committed = service.simple_matrix_to_ebk(cb.text, False) if off else cb.text
        prefix, draft, suffix = _squared(
            off, *service.mapping_pending_text(committed, ed.pending_mapping_row), False
        )
        rec.cells[cb.id].display.html.set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
        )
        rec.cells[cb.id].display.html.style(
            f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px"
        )
        return
    if cb.id == "ptext:vectors:targets":
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
    rec.cells[cb.id].display.html.set_content(
        f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
    )
    rec.cells[cb.id].display.html.style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")


def build_mathexpr(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cb.id].display.expr = ui.html("").classes("rtt-mathexpr")


def update_mathexpr(rec, cb: spreadsheet.CellBox) -> None:
    if rec.handles(cb.id).display.expr_state != (cb.text, cb.w):
        rec.cells[cb.id].display.expr.set_content(_mathexpr_html(cb.text, cb.w))
        rec.cells[cb.id].display.expr_state = (cb.text, cb.w)
