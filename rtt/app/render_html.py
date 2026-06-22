from __future__ import annotations

import math
from html import escape as _escape
from urllib.parse import quote

from rtt.app import grid_tables, service, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.marks import (
    BR_COLOR,
    angle_bracket,
    brace,
    rect,
    square_bracket,
    svg,
    top_bracket,
)
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


def _freeze_container(cb, fx: float, fy: float) -> str:
    if cb.x < fx and cb.y < fy:
        return "corner"
    if cb.y < fy:
        return "col"
    if cb.x < fx:
        return "row"
    return "body"


def _block_panes(bl, fx: float, fy: float) -> tuple[str, ...]:
    panes = ["body"]
    if bl.y < fy:
        panes.append("col")
    if bl.x < fx:
        panes.append("row")
    if bl.x < fx and bl.y < fy:
        panes.append("corner")
    return tuple(panes)


_EXPR_MAX_FONT = 9.0
_EXPR_MIN_FONT = 3.5
_EXPR_CHAR_W = 0.5


def _fit_font(
    line: str,
    width: float,
    max_font: float = _EXPR_MAX_FONT,
    min_font: float = _EXPR_MIN_FONT,
    char_w: float = _EXPR_CHAR_W,
) -> float:
    if not line:
        return max_font
    fit = (width - 2) / (len(line) * char_w)
    return max(min_font, min(max_font, fit))


_LOG2 = "log₂"


def _elide_expr_line(line: str, width: float) -> str:
    max_chars = (width - 2) / (_EXPR_MIN_FONT * _EXPR_CHAR_W)
    if len(line) <= max_chars:
        return line
    cut = line.rfind(_LOG2)
    if cut < 0:
        return line
    head, operand = line[: cut + len(_LOG2)], line[cut + len(_LOG2) :]
    return head + ("(…/…)" if "/" in operand else "…")


def _mathexpr_html(text: str, width: float) -> str:
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{line}</div>'
        for line in (_elide_expr_line(raw, width) for raw in text.split("\n"))
    )
    return f'<div class="rtt-mathexpr-stack">{lines}</div>'


def _units_font(text: str, width: float, max_font: float) -> float:
    return _fit_font(text, width, max_font=max_font)


def _chart_ticks(lo: float, hi: float) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo, lo + 1.0]
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag)
    start = math.floor(lo / step) * step
    stop = (math.floor(hi / step) + 1) * step
    count = int(round((stop - start) / step))
    ticks = [round(start + i * step, 6) for i in range(count + 1)]
    if len(ticks) < 2 or ticks[-1] == ticks[0]:
        return [ticks[0], ticks[0] + 1.0]
    return ticks


def _bar_chart(w: float, h: float, values, indicator=None, indicator_label="") -> str:
    axis_x, col_w = spreadsheet_constants.BRACKET_W, spreadsheet_constants.COL_W
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
    bw = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(values):
        if v is None:
            continue
        cx = axis_x + i * col_w + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(rect(cx - bw / 2, top, bw, bot - top))
    if indicator is not None:
        iy = y_of(indicator)
        lbl_font, sub_font, stub = 9, 6, 8
        lbl_w = 3 * lbl_font * 0.62 + len(indicator_label) * sub_font * 0.62 + 3
        lx = axis_x + stub
        body.append(
            f'<line x1="{axis_x:.2f}" y1="{iy:.2f}" x2="{lx - 2:.2f}" y2="{iy:.2f}" '
            f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>'
        )
        body.append(
            f'<line x1="{lx + lbl_w + 2:.2f}" y1="{iy:.2f}" x2="{w:.2f}" y2="{iy:.2f}" '
            f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>'
        )
        sub = (
            f'<tspan font-size="{sub_font}" dy="2">{_escape(indicator_label)}</tspan>'
            if indicator_label
            else ""
        )
        body.append(
            f'<text x="{lx:.2f}" y="{iy + lbl_font * 0.34:.2f}" font-size="{lbl_font}" '
            f'fill="{_CHART_INDICATOR}"><tspan>⟪</tspan>'
            f'<tspan font-weight="bold">d</tspan><tspan>⟫</tspan>{sub}</text>'
        )
    return svg(w, h, "".join(body))


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

    def bar(cx, y, half):
        return rect(cx - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(cx, y, v):
        shown = strip_negative_zero(f"{v:.{3 if decimals else 0}f}")
        return (
            f'<text x="{cx:.2f}" y="{y:.2f}" text-anchor="middle" '
            f'font-size="{_RANGE_FONT}" fill="{BR_COLOR}">{shown}</text>'
        )

    body = []
    for i, (lo, hi) in enumerate(ranges):
        cx = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:
            body.append(bar(cx, mid, cap_half) + label(cx, mid - 4, lo))
            continue
        body.append(rect(cx - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(cx, plot_top, cap_half) + bar(cx, plot_bot, cap_half))
        body.append(label(cx, plot_top - 4, hi) + label(cx, plot_bot + 9, lo))
        if i < len(tunings):
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(cx, plot_top + frac * (plot_bot - plot_top), tick_half))
    return svg(w, h, "".join(body))


def _parse_int(text: str) -> int | None:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _wheel_step(value, delta_y, step=1) -> str:
    text = str(value).strip()
    try:
        cur = float(text.replace("∞", "inf"))
    except ValueError:
        cur = 0.0
    if not math.isfinite(cur):
        return text
    new = cur + (step if delta_y < 0 else -step)
    if isinstance(step, int):
        return str(int(new)) if new == int(new) else str(new)
    decimals = max(0, -math.floor(math.log10(step)))
    return strip_negative_zero(f"{round(new, decimals):.{decimals}f}")


def _limit_text(limit) -> str | None:
    return None if limit is None else str(limit)


def _ratio_parts(text) -> tuple[str, str] | None:
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text) -> tuple[str, str]:
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _approach_visible(editor) -> bool:
    return service.domain_has_nonprimes(editor.state.domain_basis)


def _gentuning_parts(text: str) -> tuple[str, str, str]:
    if not text:
        return "", "", ""
    sign, body = ("−", text[1:]) if text.startswith("-") else ("+", text)
    whole, frac = _cents_parts(body)
    return sign, whole, frac


def _power_parts(text) -> tuple[str, str]:
    return (text, "(max)") if text == "∞" else (text, "")


# Per-glyph widths (in em — font-size multiples) for the .rtt-ptext face, used to estimate a
# plain-text value's width without a browser. An EBK string mixes wide digits with narrow
# punctuation and spaces, so a single average char width over-shrinks a punctuation-heavy
# value (e.g. a prescaling ket-matrix, mostly 0s, dots and spaces); summing the real glyphs
# lets each value fill its box. These are conservative upper-bound em-widths (originally Cambria,
# rounded up with a ~5% margin) — the self-hosted STIX Two Text body face (see app.py) is narrower
# still (its digit is ~0.50 em vs the 0.59 here), so the estimate stays safely above the real
# render and a value never spills; it just sizes a touch conservatively. 0.59 (a digit, the widest
# common EBK glyph) is the fallback for any character not listed.
_PTEXT_DEFAULT_EM = 0.59
_PTEXT_GLYPH_EM = {
    **dict.fromkeys("0123456789", 0.59),
    ".": 0.25,
    "-": 0.35,
    "/": 0.52,
    " ": 0.24,
    "[": 0.37,
    "]": 0.37,
    "{": 0.41,
    "}": 0.41,
    "⟨": 0.38,
    "⟩": 0.38,
    "⟪": 0.58,
    "⟫": 0.58,
    "—": 1.0,
}


def _ptext_units(text: str) -> float:
    return sum(_PTEXT_GLYPH_EM.get(c, _PTEXT_DEFAULT_EM) for c in text)


def _ptext_font(text: str, width: float) -> float:
    units = _ptext_units(text)
    fit = (width - 2) / units if units else spreadsheet_constants.PTEXT_MAX_FONT
    return int(min(spreadsheet_constants.PTEXT_MAX_FONT, fit) * 10) / 10


_RATIO_MAX_FONT = 13.0
_RATIO_DIGIT_EM = _PTEXT_GLYPH_EM["0"]
_RATIO_PAD = 6.0


def _digit_fit_font(longest, width: float, max_font: float) -> float:
    if not longest:
        return max_font
    fit = (width - _RATIO_PAD) / (longest * _RATIO_DIGIT_EM)
    return int(min(max_font, fit) * 10) / 10


def _ratio_font(num, den, width: float) -> float:
    return _digit_fit_font(max(len(num), len(den)), width, _RATIO_MAX_FONT)


_DESCENDERS = "gjpqy"


def _underline_html(text: str, spans) -> str:
    out, i = [], 0
    for start, length in sorted(spans):
        seg = text[start : start + length]
        tag = '<u class="rtt-desc">' if any(c in _DESCENDERS for c in seg) else "<u>"
        out.append(_escape(text[i:start]) + tag + _escape(seg) + "</u>")
        i = start + length
    out.append(_escape(text[i:]))
    return "".join(out)


_EXAMPLE_TEXT: dict[str, str] = {
    "counts": "𝑑",
    "interval_ratios": "2.3.5",
    "interval_vectors": "[−4 4 −1⟩",
    "ebk": "⟨1 0 -4]",
    "domain_units": "p₁/",
    "temperament_tiles": "𝑀",
    "form": "𝑀" + grid_tables.SUBSCRIPT_C,
    "form_controls": "canonical form",
    "form_tiles": "𝐹",
    "tuning_tiles": "T",
    "optimization": "𝑝",
    "weighting": "𝒘",
    "all_interval": "minimax-S",
    "alt_complexity": "E-lp",
    "custom_weights": "1.5",
    "projection": "𝑃",
    "interest": "𝐢",
    "generator_detempering": "D",
    "nonstandard_domain": "Bₗ",
    "identity_objects": "𝑀ⱼ",
}


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


_EXAMPLE_HTML = {
    "animations": (
        '<span style="position:relative;display:inline-block;width:34px;height:16px">'
        '<span style="position:absolute;left:0;top:1px;width:13px;height:13px;'
        'border:1px solid #999;background:#fff;opacity:0.35"></span>'
        '<span style="position:absolute;left:11px;top:1px;width:13px;height:13px;'
        'border:1px solid #555;background:#fff"></span>'
        '<span class="material-icons" style="position:absolute;right:-3px;top:1px;'
        'font-size:13px;color:#777">east</span></span>'
    ),
    "preview_highlighting": (
        '<span style="display:inline-flex;align-items:center;justify-content:center;'
        "width:22px;height:16px;background:#fff;"
        "box-shadow:inset 0 0 0 2px var(--preview-color);"
        'color:var(--preview-text-color);font-size:10px">3</span>'
    ),
    "tooltips": (
        '<span style="position:relative;display:inline-block;background:#444;color:#fff;'
        'font-size:9px;line-height:1;padding:3px 5px;border-radius:3px">help'
        '<span style="position:absolute;left:6px;bottom:-3px;width:0;height:0;'
        "border-left:3px solid transparent;border-right:3px solid transparent;"
        'border-top:3px solid #444"></span></span>'
    ),
    "tuning_ranges": (
        '<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
        '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
        '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
        '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>'
    ),
}

_COLORIZATION_LETTER = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}


def _colorization_example_html(key: str) -> str:
    group = key.split("_", maxsplit=1)[0]
    letter = _COLORIZATION_LETTER[group]
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:36px;height:14px;background:var(--wash-{group})">{_math_html(letter)}</span>'
    )


def _example_html(key: str) -> str:
    if key in show_settings.GROUPING_PARENTS:
        return ""
    if key in _EXAMPLE_HTML:
        return _EXAMPLE_HTML[key]
    if key.split("_", maxsplit=1)[0] in _COLORIZATION_LETTER and key.endswith("_colorization"):
        return _colorization_example_html(key)
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


_TILE_NAME = "tile name"
_TILE_SYMBOL = "𝒏"
_TILE_ROWLABEL = "𝒏₁"
_TILE_EQUIV = " = 𝑒G"
_TILE_MATH = "1200·log₂(3/2) ="
_TILE_VALUE = "701.955"
_TILE_UNITS = "¢/p"
_TILE_PTEXT = "⟨1200 1902 2786]"

_TILE_MNEMONIC_AT = _TILE_NAME.index("n")


def _tile_name_pieces() -> tuple[str, str, str]:
    i = _TILE_MNEMONIC_AT
    return _TILE_NAME[:i], _TILE_NAME[i], _TILE_NAME[i + 1 :]


def _tile_fold_html() -> str:
    return _control_svg(_FOLD_GLYPH["unfold_less"])


_TILE_CELL = spreadsheet_constants.COL_W
_TILE_BR_W = 9
_TILE_ENCLOSE = 5
_TILE_CAP = 5
_TILE_FRAME_W = _TILE_BR_W + _TILE_CELL + _TILE_BR_W
_TILE_FRAME_H = _TILE_CAP + _TILE_ENCLOSE + _TILE_CELL + _TILE_ENCLOSE + _TILE_CAP
_TILE_CELL_X = _TILE_BR_W
_TILE_CELL_Y = _TILE_CAP + _TILE_ENCLOSE


def _tile_grid_frame_html() -> str:
    def mark(x, y, w, h, inner):
        return (
            f'<div style="position:absolute;left:{x}px;top:{y}px;'
            f'width:{w}px;height:{h}px">{inner}</div>'
        )

    cell, cap, bw, cx, cy = _TILE_CELL, _TILE_CAP, _TILE_BR_W, _TILE_CELL_X, _TILE_CELL_Y
    span = _TILE_FRAME_W
    return (
        f'<div style="position:relative;width:{_TILE_FRAME_W}px;height:{_TILE_FRAME_H}px">'
        + mark(0, 0, span, cap, top_bracket(span, cap))
        + mark(0, _TILE_FRAME_H - cap, span, cap, brace(span, cap))
        + mark(0, cy, bw, cell, angle_bracket(bw, cell))
        + mark(
            cx,
            cy,
            cell,
            cell,
            '<div style="width:100%;height:100%;box-sizing:border-box;'
            'border:1px solid #555;background:#fff"></div>',
        )
        + mark(cx + cell, cy, bw, cell, square_bracket(bw, cell, "right"))
        + "</div>"
    )


def _tile_preset_html() -> str:
    return (
        '<span style="display:flex;align-items:center;justify-content:space-between;'
        "gap:4px;width:100%;height:22px;box-sizing:border-box;background:#fff;border:1px solid "
        "#999;"
        'border-radius:2px;padding:0 2px 0 6px;font-size:13px;color:#000">(presets)'
        '<span class="material-icons" '
        'style="font-size:16px;color:#555">arrow_drop_down</span></span>'
    )


_GENERAL_PART_BUILDERS = {
    "gridded_values": lambda: _tile_grid_frame_html(),
    "math_expressions": lambda: _math_html(_TILE_MATH),
    "quantities": lambda: f'<span class="rtt-stacked-main">{_cents_parts(_TILE_VALUE)[0]}</span>',
    "decimals": lambda: f'<span class="rtt-stacked-sub">.{_cents_parts(_TILE_VALUE)[1]}</span>',
    "symbols": lambda: _math_html(_TILE_SYMBOL),
    "header_symbols": lambda: _math_html(_TILE_ROWLABEL),
    "equivalences": lambda: _math_html(_TILE_EQUIV),
    "names": lambda: _escape(_TILE_NAME),
    "mnemonics": lambda: _escape(_tile_name_pieces()[1]),
    "units": lambda: f'<span class="rtt-units-pre">units: </span>{_units_html(_TILE_UNITS)}',
    "cell_units": lambda: _units_html(_TILE_UNITS),
    "plain_text_values": lambda: _math_html(_TILE_PTEXT),
    "presets": lambda: _tile_preset_html(),
    "charts": lambda: _example_chart(),
    "drag_to_combine": lambda: (
        '<span class="material-icons" style="color:#444">drag_indicator</span>'
    ),
}


def _general_part_html(key: str) -> str:
    if key not in _GENERAL_PART_BUILDERS:
        raise KeyError(key)
    return _GENERAL_PART_BUILDERS[key]()


_MATH_ALPHABET_RANGES = (
    (0x1D7CE, 0x1D7D7, "0", True, False),
    (0x1D400, 0x1D419, "A", True, False),
    (0x1D41A, 0x1D433, "a", True, False),
    (0x1D434, 0x1D44D, "A", False, True),
    (0x1D44E, 0x1D467, "a", False, True),
    (0x1D468, 0x1D481, "A", True, True),
    (0x1D482, 0x1D49B, "a", True, True),
)


def _demath(ch: str) -> tuple[str, bool, bool] | None:
    cp = ord(ch)
    for lo, hi, base, bold, italic in _MATH_ALPHABET_RANGES:
        if lo <= cp <= hi:
            return chr(ord(base) + cp - lo), bold, italic
    return None


def _math_html(text: str) -> str:
    out = []
    for ch in text:
        if ch == grid_tables.NORM_SUB_OPEN:
            out.append('<sub style="font-style:italic">')
            continue
        if ch == grid_tables.NORM_SUB_CLOSE:
            out.append("</sub>")
            continue
        if ch == grid_tables.SUB_OPEN:
            out.append("<sub>")
            continue
        if ch == grid_tables.SUB_CLOSE:
            out.append("</sub>")
            continue
        styled = _demath(ch)
        if styled is None:
            out.append(_escape(ch))
            continue
        base, bold, italic = styled
        css = (["font-weight:700"] if bold else []) + (["font-style:italic"] if italic else [])
        out.append(f'<span style="{";".join(css)}">{_escape(base)}</span>')
    return "".join(out)


_UNIT_PLAIN = ("oct", "¢", "/", " ")


_SUB_TAGS = {
    grid_tables.SUB_OPEN: "<sub>",
    grid_tables.SUB_CLOSE: "</sub>",
    grid_tables.NORM_SUB_OPEN: '<sub style="font-style:italic">',
    grid_tables.NORM_SUB_CLOSE: "</sub>",
}


def _run_html(s: str) -> str:
    return "".join(_SUB_TAGS.get(ch) or _escape(ch) for ch in s)


def _bold_units(value) -> str:
    out, run = [], []

    def flush():
        if run:
            out.append(f"<b>{_run_html(''.join(run))}</b>")
            run.clear()

    i = 0
    while i < len(value):
        plain = next((t for t in _UNIT_PLAIN if value.startswith(t, i)), None)
        if plain is not None:
            flush()
            out.append(_escape(plain))
            i += len(plain)
        else:
            run.append(value[i])
            i += 1
    flush()
    return "".join(out)


def _units_html(text: str) -> str:
    prefix = "units: "
    if text.startswith(prefix):
        return f'<span class="rtt-units-pre">{prefix}</span>{_bold_units(text[len(prefix) :])}'
    return _bold_units(text)


# spacing of the dots on a folded band's gridline: a LINE_W-long dot every _DOT_PITCH px.
# CSS `border-style:dotted` packs dots ~one border-width apart (≈2*LINE_W period) and gives
# no control; painting them ourselves lets us space them out — here ≈twice as sparse.
_DOT_PITCH = 8


def _line_style(ln, y_shift: float = 0) -> str:
    half = spreadsheet_constants.LINE_W / 2
    if ln.orientation == "v":
        pos, edge, sweep = (
            f"left:0; top:0; transform:translate({ln.pos - half}px,{ln.start - y_shift}px); "
            f"height:{ln.length}px",
            "left",
            "to bottom",
        )
    else:
        pos, edge, sweep = (
            f"left:0; top:0; transform:translate({ln.start}px,{ln.pos - half - y_shift}px); "
            f"width:{ln.length}px",
            "top",
            "to right",
        )
    if ln.dotted:
        dots = (
            f"repeating-linear-gradient({sweep},var(--c-gridline) 0 {spreadsheet_constants.LINE_W}px,"
            f"transparent {spreadsheet_constants.LINE_W}px {_DOT_PITCH}px) border-box"
        )
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:var(--c-gridline); background:none"


def _select_props(min_width: float) -> str:
    return (
        "dense options-dense borderless hide-bottom-space "
        "popup-content-class=rtt-select-popup "
        f"popup-content-style=min-width:{min_width}px;width:max-content"
    )
