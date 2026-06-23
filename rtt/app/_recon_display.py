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



class _ReconDisplayCells:
    def __init__(self, r) -> None:
        self.r = r

    def _build_svgfill(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.r.htmls[cb.id] = ui.html("").classes("rtt-svgfill")

    def _update_ebk(self, cb: spreadsheet.CellBox) -> None:
        if self.r.ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
            self.r.htmls[cb.id].set_content(ebk_svg(cb))
            self.r.ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)

    def _update_chart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
        if self.r.chart_keys.get(cb.id) != key:
            self.r.htmls[cb.id].set_content(
                _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
            )
            self.r.chart_keys[cb.id] = key

    def _update_rangechart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
        if self.r.range_keys.get(cb.id) != key:
            self.r.htmls[cb.id].set_content(
                _range_chart(cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
            )
            self.r.range_keys[cb.id] = key

    def _build_count(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.r.math_cells[cb.id] = ui.html("").classes("rtt-count")

    def _build_symbol(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-symbol-cell")
        cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
        self.r.math_cells[cb.id] = ui.html("").classes(cls)

    @staticmethod
    def _matlabel_classes(text: str) -> str:
        return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"

    def _build_matlabel(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-matlabel-cell")
        self.r.math_cells[cb.id] = ui.html("").classes(self._matlabel_classes(cb.text))

    def _build_units(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-units-cell")
        self.r.math_cells[cb.id] = ui.html("").classes("rtt-units")

    def _update_mathcell(self, cb: spreadsheet.CellBox) -> None:
        if cb.kind == "units":
            html = _units_html(cb.text)
            if self.r.math_rendered.get(cb.id) != (html, cb.w):
                self.r.math_cells[cb.id].set_content(html)
                self.r.math_cells[cb.id].style(
                    f"font-size:{_units_font(cb.text, cb.w, _UNITS_MAX_FONT):.2f}px"
                )
                self.r.math_rendered[cb.id] = (html, cb.w)
            return
        html = _math_html(cb.text)
        font = None
        if cb.kind == "matlabel" and ":col:" in cb.id and "‖" not in cb.text and " " not in cb.text:
            w = spreadsheet_text._min_width_for_lines(cb.text, 1, _MATLABEL_FONT)
            if w > cb.w - 2:
                font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cb.w - 2) / w)
        if self.r.math_rendered.get(cb.id) != (html, font):
            self.r.math_cells[cb.id].set_content(html)
            if font is not None:
                self.r.math_cells[cb.id].style(f"font-size:{font:.2f}px")
            self.r.math_rendered[cb.id] = (html, font)
            if cb.kind == "matlabel":
                self.r.math_cells[cb.id].classes(replace=self._matlabel_classes(cb.text))
            if cb.id == "optimization:mean_damage:symbol":
                wide = "‖" in cb.text
                self.r.math_cells[cb.id].classes(
                    replace="rtt-symbol rtt-opt-1line rtt-opt-wide"
                    if wide
                    else "rtt-symbol rtt-opt-1line"
                )

    def _build_caption(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-caption-cell")
        one_line = cb.id.startswith("optimization:") and cb.id != "optimization:mean_damage:caption"
        cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
        if cb.align == "left":
            cls += " rtt-caption-left"
        self.r.captions[cb.id] = ui.html("").classes(cls)

    def _update_caption(self, cb: spreadsheet.CellBox) -> None:
        html = _underline_html(cb.text, cb.underlines)
        if self.r.caption_html.get(cb.id) != html:
            self.r.captions[cb.id].set_content(html)
            self.r.caption_html[cb.id] = html
        self.r.captions[cb.id].classes(
            add="rtt-caption-disabled" if cb.disabled else "",
            remove="" if cb.disabled else "rtt-caption-disabled",
        )

    def _build_ptextpending(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.r.htmls[cb.id] = ui.html("").classes("rtt-ptextpending")

    def _update_ptextpending(self, cb: spreadsheet.CellBox) -> None:
        ed = self.r._editor
        off = not ed.settings.get("ebk", True)

        def squared(prefix, draft, suffix, vector_based):
            if not off:
                return prefix, draft, suffix
            return (
                prefix.translate(_EBK_SQUARE),
                draft.translate(_EBK_SQUARE),
                suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
            )

        if cb.id == "ptext:mapping:primes":
            committed = service.simple_matrix_to_ebk(cb.text, False) if off else cb.text
            prefix, draft, suffix = squared(
                *service.mapping_pending_text(committed, ed.pending_mapping_row), False
            )
            self.r.htmls[cb.id].set_content(
                f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
            )
            self.r.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            return
        if cb.id == "ptext:vectors:targets":
            targets = ed.target_override or service.target_interval_set(
                ed.target_spec, ed.state.domain_basis
            )
            committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
            pending = ed.pending_target
        else:
            committed, pending = ed.state.comma_basis, ed.pending_comma
        prefix, draft, suffix = squared(*service.vector_list_pending_text(committed, pending), True)
        self.r.htmls[cb.id].set_content(f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
        self.r.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")

    def _build_mathexpr(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.r.exprs[cb.id] = ui.html("").classes("rtt-mathexpr")

    def _update_mathexpr(self, cb: spreadsheet.CellBox) -> None:
        if self.r.expr_state.get(cb.id) != (cb.text, cb.w):
            self.r.exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
            self.r.expr_state[cb.id] = (cb.text, cb.w)
