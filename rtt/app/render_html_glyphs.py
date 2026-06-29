from __future__ import annotations

import math
from html import escape as _escape
from urllib.parse import quote

from rtt.app import spreadsheet_constants
from rtt.app.marks import BR_COLOR, rect, svg
from rtt.library.formatting import strip_negative_zero

_CHART_PAD_T = 9
_CHART_PAD_B = 2
_CHART_BAR_FRAC = 0.5
_CHART_GRID = "#bbbbbb"
_CHART_INDICATOR = "#888888"
_RANGE_CAP_W = 14
_RANGE_MARK_W = 1.6
_RANGE_PLOT_T = 11
_RANGE_PLOT_B = 12
_RANGE_FONT = 7


def _wave_svg(kind: str) -> str:
    paths = {
        "sine": "M1,6 Q3,1 5.5,6 T11,6",
        "square": "M1,9 V3 H6 V9 H11 V3",
        "triangle": "M1,9 L3.5,3 L6,9 L8.5,3 L11,9",
        "sawtooth": "M1,9 L6,3 L6,9 L11,3 L11,9",
    }
    return (
        f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph"><path d="{paths[kind]}" '
        f'fill="none" stroke="currentColor" stroke-width="1.1"/></svg>'
    )


def _mode_svg(filled) -> str:
    rects = [
        f'<rect x="{1 + c * 3.7:.1f}" y="{1 + r * 3.7:.1f}" width="2.6" height="2.6" '
        f'fill="{"currentColor" if (r, c) in filled else "none"}" stroke="currentColor" '
        f'stroke-width="0.5"/>'
        for r in range(3)
        for c in range(3)
    ]
    return f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph">{"".join(rects)}</svg>'


def _option_box_svg(fill: str | None, *, box: str = "#fff", border: str = "#555") -> str:
    n = spreadsheet_constants.OPTION_BOX_PX
    inner = f"<rect x='3' y='3' width='{n - 6}' height='{n - 6}' fill='{fill}'/>" if fill else ""
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}'>"
        f"<rect x='.5' y='.5' width='{n - 1}' height='{n - 1}' "
        f"fill='{box}' stroke='{border}' stroke-width='1'/>"
        f"{inner}</svg>"
    )
    return "data:image/svg+xml," + quote(svg)


_CONTROL_GLYPHS = {
    "plus": "M6 3V9M3 6H9",
    "minus": "M3 6H9",
    "expand": "M3.5 4.7L6 2.6L8.5 4.7M3.5 7.3L6 9.4L8.5 7.3",
    "collapse": "M3.5 2.6L6 4.7L8.5 2.6M3.5 9.4L6 7.3L8.5 9.4",
    "reduce": "M6 2.8L6 8.6M3.8 6.2L6 8.8L8.2 6.2",
    "reciprocate": "M6 3L6 9M4.2 4.6L6 3L7.8 4.6M4.2 7.4L6 9L7.8 7.4",
}
_FOLD_GLYPH = {"unfold_more": "expand", "unfold_less": "collapse"}


def _control_svg(glyph: str) -> str:
    return (
        f"<svg viewBox='0 0 12 12' xmlns='http://www.w3.org/2000/svg'>"
        f"<rect x='.5' y='.5' width='11' height='11' fill='#fff' stroke='#bbb' stroke-width='1'/>"
        f"<path d='{_CONTROL_GLYPHS[glyph]}' fill='none' stroke='currentColor' stroke-width='1.2'"
        f" stroke-linecap='round' stroke-linejoin='round'/></svg>"
    )


def _chart_ticks(lo: float, hi: float) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo, lo + 1.0]
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag)
    start = math.floor(lo / step) * step
    stop = (math.floor(hi / step) + 1) * step
    count = round((stop - start) / step)
    ticks = [round(start + i * step, 6) for i in range(count + 1)]
    if len(ticks) < 2 or ticks[-1] == ticks[0]:
        return [ticks[0], ticks[0] + 1.0]
    return ticks


def _bar_chart(w: float, h: float, values, indicator=None, indicator_label="", col_gap=0) -> str:
    axis_x, col_w = spreadsheet_constants.BRACKET_W, spreadsheet_constants.COL_W
    pitch = col_w + col_gap
    values = tuple(values)
    present = tuple(v for v in values if v is not None)
    ticks = _chart_ticks(min((*present, 0.0)), max((*present, 0.0)))
    axis_lo, axis_hi = ticks[0], ticks[-1]
    plot_top, plot_bot = _CHART_PAD_T, h - _CHART_PAD_B
    span = axis_hi - axis_lo

    def y_of(v):
        return plot_top + (axis_hi - v) / span * (plot_bot - plot_top)

    body = []
    for tv in ticks:
        ty = y_of(tv)
        body.append(
            f'<line x1="{axis_x:.2f}" y1="{ty:.2f}" x2="{w:.2f}" y2="{ty:.2f}" '
            f'stroke="{_CHART_GRID}" stroke-width="0.5"/>'
        )
        body.append(
            f'<text x="{axis_x - 2:.2f}" y="{ty + 2.4:.2f}" text-anchor="end" '
            f'font-size="7" fill="{BR_COLOR}">{tv:g}</text>'
        )
    zero_y = y_of(0)
    body.append(
        f'<line x1="{axis_x:.2f}" y1="{zero_y:.2f}" x2="{w:.2f}" y2="{zero_y:.2f}" '
        f'stroke="{BR_COLOR}" stroke-width="1"/>'
    )
    body.append(rect(axis_x, plot_top, 0.8, plot_bot - plot_top))
    bar_width = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(values):
        if v is None:
            continue
        center_x = axis_x + i * pitch + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(rect(center_x - bar_width / 2, top, bar_width, bot - top))
    body.extend(_bar_chart_indicator(w, axis_x, y_of, indicator, indicator_label))
    return svg(w, h, "".join(body))


def _bar_chart_indicator(w, axis_x, y_of, indicator, indicator_label) -> list[str]:
    if indicator is None:
        return []
    iy = y_of(indicator)
    lbl_font, sub_font, stub = 9, 6, 8
    lbl_w = 3 * lbl_font * 0.62 + len(indicator_label) * sub_font * 0.62 + 3
    lx = axis_x + stub
    sub = (
        f'<tspan font-size="{sub_font}" dy="2">{_escape(indicator_label)}</tspan>'
        if indicator_label
        else ""
    )
    return [
        f'<line x1="{axis_x:.2f}" y1="{iy:.2f}" x2="{lx - 2:.2f}" y2="{iy:.2f}" '
        f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>',
        f'<line x1="{lx + lbl_w + 2:.2f}" y1="{iy:.2f}" x2="{w:.2f}" y2="{iy:.2f}" '
        f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>',
        f'<text x="{lx:.2f}" y="{iy + lbl_font * 0.34:.2f}" font-size="{lbl_font}" '
        f'fill="{_CHART_INDICATOR}"><tspan>⟪</tspan>'
        f'<tspan font-weight="bold">d</tspan><tspan>⟫</tspan>{sub}</text>',
    ]


def _range_chart(w: float, h: float, ranges, tunings=(), decimals: bool = True) -> str:
    cx0, col_w = spreadsheet_constants.BRACKET_W, spreadsheet_constants.COL_W
    if not ranges:
        return svg(
            w,
            h,
            f'<text x="{w / 2:.2f}" y="{h / 2 + 2:.2f}" text-anchor="middle" '
            f'font-size="{_RANGE_FONT}" fill="{BR_COLOR}">no range</text>',
        )
    plot_top, plot_bot = _RANGE_PLOT_T, h - _RANGE_PLOT_B
    mid, hw = (plot_top + plot_bot) / 2, _RANGE_MARK_W / 2
    cap_half, tick_half = _RANGE_CAP_W / 2, _RANGE_CAP_W / 2 - 3

    def bar(center_x, y, half):
        return rect(center_x - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(center_x, y, v):
        shown = strip_negative_zero(f"{v:.{3 if decimals else 0}f}")
        return (
            f'<text x="{center_x:.2f}" y="{y:.2f}" text-anchor="middle" '
            f'font-size="{_RANGE_FONT}" fill="{BR_COLOR}">{shown}</text>'
        )

    body = []
    for i, (lo, hi) in enumerate(ranges):
        center_x = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:
            body.append(bar(center_x, mid, cap_half) + label(center_x, mid - 4, lo))
            continue
        body.append(rect(center_x - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(center_x, plot_top, cap_half) + bar(center_x, plot_bot, cap_half))
        body.append(label(center_x, plot_top - 4, hi) + label(center_x, plot_bot + 9, lo))
        if i < len(tunings):
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(center_x, plot_top + frac * (plot_bot - plot_top), tick_half))
    return svg(w, h, "".join(body))


def _example_chart() -> str:
    return (
        '<div style="position:relative;width:84px;height:34px">'
        '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
        '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
        '<svg width="66" height="34" viewBox="0 0 66 34" '
        'style="position:absolute;left:16px;top:0">'
        f'<line x1="2" y1="5" x2="64" y2="5" stroke="{_CHART_GRID}" stroke-width="1"/>'
        f'<line x1="2" y1="29" x2="64" y2="29" stroke="{_CHART_GRID}" stroke-width="1"/>'
        f'<line x1="2" y1="3" x2="2" y2="31" stroke="{BR_COLOR}" stroke-width="1.4"/>'
        f'<line x1="0" y1="5" x2="6" y2="5" stroke="{BR_COLOR}" stroke-width="1.4"/>'
        f'<line x1="0" y1="29" x2="6" y2="29" stroke="{BR_COLOR}" stroke-width="1.4"/>'
        f'<line x1="2" y1="17" x2="62" y2="17" stroke="{BR_COLOR}" stroke-width="1"/>'
        f'<rect x="16" y="17" width="22" height="6" fill="{BR_COLOR}"/>'
        "</svg></div>"
    )
