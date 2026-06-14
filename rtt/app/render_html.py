"""Pure string/number builders for the RTT spreadsheet front end.

HTML / SVG / text / font-fit / chart builders extracted from :mod:`rtt.app.app`
(audit Phase 2, cluster C). Every function here is pure — it touches no NiceGUI
``ui.`` element, no ``app.storage`` / ``background_tasks``, and no app.py state — so
``app.py`` imports them back and every ``app.<name>`` reference keeps working. This
module must NOT import :mod:`rtt.app.app` (it would cycle)."""

from __future__ import annotations

import math
from html import escape as _escape
from urllib.parse import quote

from rtt.library.formatting import strip_negative_zero
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app.marks import (
    BR_COLOR,
    angle_bracket,
    brace,
    rect,
    square_bracket,
    svg,
    top_bracket,
)


# A per-tile bar chart (damage, retuning) is drawn in the same 1:1 SVG box as the EBK
# marks: a left y-axis with nice-stepped gridlines, a darker zero baseline, and one bar
# per value column aligned to the cells below. Bars rise from the zero line for positive
# values and drop from it for negative, so an all-positive chart (damage) reads from the
# bottom and a signed one (retuning) reads from a centred zero.
_CHART_PAD_T = 9  # top padding (room for the top gridline's label)
_CHART_PAD_B = 2  # bottom padding
_CHART_BAR_FRAC = 0.5  # bar width as a fraction of the column it sits in
_CHART_GRID = "#bbbbbb"  # light gridline / tick colour
_CHART_INDICATOR = "#888888"  # the minimized-damage indicator line (a solid lighter grey, labelled)
# The generator tuning-ranges chart: per-generator vertical I-beam range markers drawn
# in the same 1:1 SVG box as the EBK marks. A ranged generator is a stem with a cap at
# top (max cents) and bottom (min), labelled at the caps; a pinned generator (the period,
# octave held pure, so min == max) collapses to a single flat cap with one value.
_RANGE_CAP_W = 14  # I-beam cap width (px); the live-tuning tick is a shorter bar
_RANGE_MARK_W = 1.6  # I-beam stem + cap thickness (px) — constant at any height (1:1 viewBox)
_RANGE_PLOT_T = 11  # plot-area top (room for the top-cap label; the title is now a boxtitle above the chart)
_RANGE_PLOT_B = 12  # plot-area bottom margin (room for the bottom-cap label)
_RANGE_FONT = 7  # cents-label / placeholder font size

def _wave_svg(kind: str) -> str:
    """A small waveform glyph (sine/square/triangle/sawtooth) for the bank's waveform control."""
    paths = {"sine": "M1,6 Q3,1 5.5,6 T11,6", "square": "M1,9 V3 H6 V9 H11 V3",
             "triangle": "M1,9 L3.5,3 L6,9 L8.5,3 L11,9", "sawtooth": "M1,9 L6,3 L6,9 L11,3 L11,9"}
    return (f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph"><path d="{paths[kind]}" '
            f'fill="none" stroke="currentColor" stroke-width="1.1"/></svg>')


def _mode_svg(filled) -> str:
    """A 3×3 grid glyph with the given (row, col) cells filled — the play-mode control."""
    rects = [f'<rect x="{1 + c * 3.7:.1f}" y="{1 + r * 3.7:.1f}" width="2.6" height="2.6" '
             f'fill="{"currentColor" if (r, c) in filled else "none"}" stroke="currentColor" '
             f'stroke-width="0.5"/>' for r in range(3) for c in range(3)]
    return f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph">{"".join(rects)}</svg>'


def _option_box_svg(fill: str | None, *, box: str = "#fff", border: str = "#555") -> str:
    """A data-URI SVG of the option-box indicator: an n×n ``box``-filled square with a 1px
    ``border`` and, when ``fill`` is given, a centred inner square (inset by the 1px border + a
    2px gap) of that colour. Used as the BACKGROUND of every q-checkbox box and the tuning-ranges
    radio box, so the whole mark scales as ONE vector — staying square with an even border at any
    zoom — instead of separate CSS box edges (border + inset fill), which the browser snaps
    independently to the device-pixel grid, distorting the square and the gap at fractional zooms.
    ``box``/``border`` default to the light theme; dark mode rebakes them (see _CSS_DARK_VARS)."""
    n = spreadsheet.OPTION_BOX_PX
    inner = f"<rect x='3' y='3' width='{n - 6}' height='{n - 6}' fill='{fill}'/>" if fill else ""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}'>"
           f"<rect x='.5' y='.5' width='{n - 1}' height='{n - 1}' fill='{box}' stroke='{border}' stroke-width='1'/>"
           f"{inner}</svg>")
    return "data:image/svg+xml," + quote(svg)


# the fan controls' glyphs, stroked centred in a 12-unit box: the +/− add/remove rules and the
# fold toggles' outward (expand) / inward (collapse) double-chevrons. Drawn in currentColor so the
# element's CSS colour (and :hover) tints them.
_CONTROL_GLYPHS = {
    "plus":     "M6 3V9M3 6H9",
    "minus":    "M3 6H9",
    "expand":   "M3.5 4.7L6 2.6L8.5 4.7M3.5 7.3L6 9.4L8.5 7.3",   # ∧ over ∨ — chevrons point OUT
    "collapse": "M3.5 2.6L6 4.7L8.5 2.6M3.5 9.4L6 7.3L8.5 9.4",   # ∨ over ∧ — chevrons point IN
}
# a fold toggle's state token (spreadsheet._fold_glyph) -> its chevron glyph: a collapsed band
# offers to expand out, an open one to collapse in.
_FOLD_GLYPH = {"unfold_more": "expand", "unfold_less": "collapse"}


def _control_svg(glyph: str) -> str:
    """An inline SVG for a fan control — the +/− add/remove buttons and the fold toggles: a white
    #bbb-bordered square with a centred glyph (a + or − rule, or the expand/collapse double-chevron)
    stroked in currentColor, so the element's CSS colour (and :hover) tints the glyph while the
    white box stays put against the grey fan. One coherent vector like the option-box checkbox, so
    box and glyph stay square and centred at ANY zoom — unlike a font glyph or a CSS-bordered button,
    whose edges the browser snaps to the device-pixel grid independently and drifts off-centre."""
    return (f"<svg viewBox='0 0 12 12' xmlns='http://www.w3.org/2000/svg'>"
            f"<rect x='.5' y='.5' width='11' height='11' fill='#fff' stroke='#bbb' stroke-width='1'/>"
            f"<path d='{_CONTROL_GLYPHS[glyph]}' fill='none' stroke='currentColor' stroke-width='1.2'"
            f" stroke-linecap='round' stroke-linejoin='round'/></svg>")


# Which sticky band a cell renders into — decided by WHERE its top-left corner falls, not by
# its kind. The column titles + fold toggles AND the column branching (each column's trunk +
# fan-out bus and the ± controls riding it) sit above freeze_y, so they ride the column strip
# (sticky to the window top); the row titles/toggles AND the row branching (each matrix row's
# trunk + left bus and its ± controls) sit left of freeze_x, so they ride the row band (sticky
# to the left); the master toggle, in the corner of both, rides the corner. Everything past both
# seams — the value cells and their grey tiles — scrolls on the body board. Routing by position
# (rather than a hand-kept kind→band map) lets the column + and the basis + — which share the
# kind "plus" but freeze in DIFFERENT bands — each land correctly, and a new control freezes for
# free.
def _freeze_container(cb, fx: float, fy: float) -> str:
    if cb.x < fx and cb.y < fy:
        return "corner"
    if cb.y < fy:
        return "col"
    if cb.x < fx:
        return "row"
    return "body"

# Which panes a BLOCK renders into. Unlike a cell — small enough that its top-left corner picks one
# band — a colorization wash overhangs its tile by WASH_PAD-PAD (so adjacent washes meet across the
# gap), so the top-row / left-column washes spill PAST the freeze seam. A wash rendered only into the
# body is then shaved at those edges: the column strip clips the spill above freeze_y (the body
# scroller stops at the seam) and the row band paints over the spill left of freeze_x. So a wash, like
# a gridline crossing the seam, renders into the body PLUS every frozen pane its rect reaches — each
# copy clipped to its pane, meeting the body copy continuously so the colour fills the inter-title gap
# at the top/left edges too. Grey tiles and bordered boxes sit inside both seams, so they get "body"
# alone and stay single-pane. The frozen copies hide once the body scrolls on that axis (see rtt.css).
def _block_panes(bl, fx: float, fy: float) -> tuple[str, ...]:
    panes = ["body"]
    if bl.y < fy:
        panes.append("col")
    if bl.x < fx:
        panes.append("row")
    if bl.x < fx and bl.y < fy:
        panes.append("corner")
    return tuple(panes)

# A math-expression cell stacks 1–2 lines ("1200 · log₂(3/2)" over "= 701.96") in a
# narrow value square, so each line's font is scaled down to fit the cell width.
_EXPR_MAX_FONT = 9.0  # px — short lines (a bare prime map) sit at the comfortable size
_EXPR_MIN_FONT = 3.5  # px — the floor for the longest target-ratio expressions
_EXPR_CHAR_W = 0.5  # a glyph's width as a fraction of font size (serif average), for the fit


def _fit_font(line: str, width: float, max_font: float = _EXPR_MAX_FONT,
              min_font: float = _EXPR_MIN_FONT, char_w: float = _EXPR_CHAR_W) -> float:
    """Largest font (capped at ``max_font``, floored at ``min_font``) at which ``line``
    fits ``width`` px on one line. Shared by the math-expression cells and the
    plain-text value boxes (which pass their own bounds)."""
    if not line:
        return max_font
    fit = (width - 2) / (len(line) * char_w)
    return max(min_font, min(max_font, fit))


# The log₂ operand is the one part of an expression that can grow without bound: a target or
# comma can be an astronomically large ratio (hundreds of digits), so a literal "1200 · log₂(N/D)"
# would streak clear across the page. When even the minimum font can't fit the line in its cell we
# elide that operand — the cents value on the second line still gives the exact size, so nothing the
# cell actually conveys is lost. (The "1200 ·" prefix, the value line, and the small prime operands
# of the prescaler are all short, so only a giant ratio is ever touched.)
_LOG2 = "log₂"  # the operand follows this literal — must match spreadsheet._math_expr's


def _elide_expr_line(line: str, width: float) -> str:
    """``line`` with its log₂ operand elided iff the line can't fit ``width`` px even at the
    minimum font: a ratio operand collapses to ``(…/…)``, a bare-integer one to ``…``. Lines that
    already fit — and the short value / prescaler lines, which carry no over-long log₂ — pass
    through unchanged. Keeps a huge target or comma ratio from spilling its cell across the page."""
    max_chars = (width - 2) / (_EXPR_MIN_FONT * _EXPR_CHAR_W)  # glyphs that fit at the floor
    if len(line) <= max_chars:
        return line
    cut = line.rfind(_LOG2)
    if cut < 0:
        return line  # no operand to elide (a value line) — already in-bounds in practice
    head, operand = line[:cut + len(_LOG2)], line[cut + len(_LOG2):]
    return head + ("(…/…)" if "/" in operand else "…")


def _mathexpr_html(text: str, width: float) -> str:
    """The stacked HTML for a math-expression cell: each newline-separated line on its own row,
    its log₂ operand elided if it would overflow even at the minimum font, then its font shrunk
    to fit the cell so the expression always stays in-bounds."""
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{line}</div>'
        for line in (_elide_expr_line(raw, width) for raw in text.split("\n"))
    )
    return f'<div class="rtt-mathexpr-stack">{lines}</div>'


def _units_font(text: str, width: float, max_font: float) -> float:
    """Font (px) at which a unit label fits ``width`` on one line, so a long annotated unit
    shrinks to its cell rather than spilling. Reuses the math-expression fit; the 0.5 char-width
    estimate overshoots the units sans (Corbel ≈0.42 em), so the chosen size never spills."""
    return _fit_font(text, width, max_font=max_font)

def _chart_ticks(lo: float, hi: float) -> list[float]:
    """Nice round tick values enclosing ``[lo, hi]``: rounded down to a tick at/below
    ``lo`` and up to the first tick strictly *above* ``hi`` (~4-5 steps). A chart scaled
    to span the returned ticks therefore always shows a gridline past its tallest bar."""
    span = hi - lo
    if span <= 0:
        return [lo, lo + 1.0]  # flat data (e.g. all-equal values): a unit axis around it
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag)
    stop = (math.floor(hi / step) + 1) * step  # first tick strictly above the top value
    ticks, v = [], math.floor(lo / step) * step
    while v <= stop + step * 1e-9:
        ticks.append(round(v, 6))
        v += step
    if ticks[-1] == ticks[0]:  # a sub-precision span (floating-point dust ~1e-13, e.g. a
        return [ticks[0], ticks[0] + 1.0]  # "made to vanish" retuning) rounded to one value:
    return ticks                           # numerically flat, so scale it flat as for span<=0


def _bar_chart(w: float, h: float, values, indicator=None, indicator_label="") -> str:
    """A bar chart filling its 1:1 px box: one bar per value, aligned to the value
    columns below, rising/falling from a zero baseline; gridlines mark nice ticks. When
    ``indicator`` is set (the optimization mean damage ⟪𝐝⟫ₚ on the damage chart), a solid
    lighter-grey line marks that minimized-damage level across the plot, broken by a
    ⟪𝐝⟫ label whose subscript is ``indicator_label`` (the scheme's Lp power ∞ / 2 / 1)."""
    axis_x, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    values = tuple(values)
    present = tuple(v for v in values if v is not None)  # a DASHED (None) cell — an unknown size the
    # under-held tuning doesn't pin (a dashed unchanged column of V) — gets no bar and no axis weight
    ticks = _chart_ticks(min(present + (0.0,)), max(present + (0.0,)))  # 0 in range: baseline shows
    axis_lo, axis_hi = ticks[0], ticks[-1]  # the axis spans the ticks, so the top one clears the bars
    plot_top, plot_bot = _CHART_PAD_T, h - _CHART_PAD_B
    span = axis_hi - axis_lo

    def y_of(v):
        return plot_top + (axis_hi - v) / span * (plot_bot - plot_top)

    body = []
    for tv in ticks:
        ty = y_of(tv)
        body.append(f'<line x1="{axis_x:.2f}" y1="{ty:.2f}" x2="{w:.2f}" y2="{ty:.2f}" '
                    f'stroke="{_CHART_GRID}" stroke-width="0.5"/>')
        body.append(f'<text x="{axis_x - 2:.2f}" y="{ty + 2.4:.2f}" text-anchor="end" '
                    f'font-size="7" fill="{BR_COLOR}">{tv:g}</text>')
    zero_y = y_of(0)
    body.append(f'<line x1="{axis_x:.2f}" y1="{zero_y:.2f}" x2="{w:.2f}" y2="{zero_y:.2f}" '
                f'stroke="{BR_COLOR}" stroke-width="1"/>')
    body.append(rect(axis_x, plot_top, 0.8, plot_bot - plot_top))  # vertical y-axis
    bw = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(values):
        if v is None:  # a dashed cell has no bar
            continue
        cx = axis_x + i * col_w + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(rect(cx - bw / 2, top, bw, bot - top))
    if indicator is not None:  # the minimized-damage level: a solid lighter-grey line BROKEN
        # by its ⟪𝐝⟫ label (a short stub from the axis, then the label in a gap, then the
        # rest of the rule), the scheme's Lp power as the label's subscript
        iy = y_of(indicator)
        lbl_font, sub_font, stub = 9, 6, 8
        # estimate the label's width so the rule gaps just around it (⟪𝐝⟫ + the subscript)
        lbl_w = 3 * lbl_font * 0.62 + len(indicator_label) * sub_font * 0.62 + 3
        lx = axis_x + stub
        body.append(f'<line x1="{axis_x:.2f}" y1="{iy:.2f}" x2="{lx - 2:.2f}" y2="{iy:.2f}" '
                    f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>')
        body.append(f'<line x1="{lx + lbl_w + 2:.2f}" y1="{iy:.2f}" x2="{w:.2f}" y2="{iy:.2f}" '
                    f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>')
        sub = (f'<tspan font-size="{sub_font}" dy="2">{_escape(indicator_label)}</tspan>'
               if indicator_label else "")
        body.append(f'<text x="{lx:.2f}" y="{iy + lbl_font * 0.34:.2f}" font-size="{lbl_font}" '
                    f'fill="{_CHART_INDICATOR}"><tspan>⟪</tspan>'
                    f'<tspan font-weight="bold">d</tspan><tspan>⟫</tspan>{sub}</text>')
    return svg(w, h, "".join(body))


def _range_chart(w: float, h: float, ranges, tunings=(), decimals: bool = True) -> str:
    """The generator tuning-ranges chart filling its 1:1 px box: one vertical I-beam per
    generator showing its [min, max] tuning in cents (max at the top cap, min at the
    bottom), with a shorter tick marking where the live tuning falls within that range. A
    pinned generator (min == max) draws a single flat cap; empty ``ranges`` draws a 'no
    range' placeholder. The 'tuning ranges' title is a boxtitle above the chart, not in the SVG."""
    cx0, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    if not ranges:
        return svg(w, h, f'<text x="{w / 2:.2f}" y="{h / 2 + 2:.2f}" text-anchor="middle" '
                    f'font-size="{_RANGE_FONT}" fill="{BR_COLOR}">no range</text>')
    plot_top, plot_bot = _RANGE_PLOT_T, h - _RANGE_PLOT_B
    mid, hw = (plot_top + plot_bot) / 2, _RANGE_MARK_W / 2
    cap_half, tick_half = _RANGE_CAP_W / 2, _RANGE_CAP_W / 2 - 3  # the live-tuning tick is shorter

    def bar(cx, y, half):
        return rect(cx - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(cx, y, v):
        shown = strip_negative_zero(f"{v:.{3 if decimals else 0}f}")  # decimals off → integer cents
        return (f'<text x="{cx:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'font-size="{_RANGE_FONT}" fill="{BR_COLOR}">{shown}</text>')

    body = []
    for i, (lo, hi) in enumerate(ranges):
        cx = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:  # pinned (e.g. the period): one value, no range — a single cap
            body.append(bar(cx, mid, cap_half) + label(cx, mid - 4, lo))
            continue
        # a vertical stem capped at the max (top) and min (bottom), labelled at each
        body.append(rect(cx - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(cx, plot_top, cap_half) + bar(cx, plot_bot, cap_half))
        body.append(label(cx, plot_top - 4, hi) + label(cx, plot_bot + 9, lo))
        if i < len(tunings):  # the live tuning, ticked where it falls within [min, max]
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(cx, plot_top + frac * (plot_bot - plot_top), tick_half))
    return svg(w, h, "".join(body))


def _parse_int(text: str) -> int | None:
    """``text`` -> int, or None for blank/partial input (matching the old parseInt)."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _wheel_step(value, delta_y, step=1) -> str:
    """One wheel notch on a numeric input's text value: scroll up (``delta_y`` < 0) adds ``step``,
    down subtracts it. A blank/partial value starts from 0; ``∞`` (the max-norm power) is left
    unchanged — a wheel can't reach it, you type it. An int ``step`` formats a bare integer
    (``2`` → ``3``); a fractional one keeps its own decimal precision (``0.001``: ``1.585`` →
    ``1.586``), so the stepped text reads like the cell already does. The one step shared by every
    gridded numeric input (and the target-limit square)."""
    text = str(value).strip()
    try:
        cur = float(text.replace("∞", "inf"))
    except ValueError:
        cur = 0.0  # blank / partial component starts from 0
    if not math.isfinite(cur):
        return text  # ∞ / inf: leave it; the wheel can't step the max-norm power
    new = cur + (step if delta_y < 0 else -step)
    if isinstance(step, int):
        return str(int(new)) if new == int(new) else str(new)
    decimals = max(0, -math.floor(math.log10(step)))
    return strip_negative_zero(f"{round(new, decimals):.{decimals}f}")


def _limit_text(limit) -> str | None:
    """The target-limit field's text for a resolved limit: the number as a string, or None
    (the "-" placeholder) when there is no limit to show (a typed override / all-interval)."""
    return None if limit is None else str(limit)


def _ratio_parts(text) -> tuple[str, str] | None:
    """Split a ratio like ``"3/2"`` into ``("3", "2")``; None if it isn't a fraction."""
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text) -> tuple[str, str]:
    """Split a cents value like ``"1899.260"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _approach_visible(editor) -> bool:
    """Whether the chapter-9 nonstandard-domain-approach radio (prime-based / nonprime-based /
    neutral) should render — True iff the loaded domain basis carries any element that isn't a
    prime int (e.g. 13/5 in 2.3.13/5). On a pure-prime basis the trait is meaningless, so the
    radio stays hidden, mirroring the maximized mockup's blue-text gating."""
    return service.domain_has_nonprimes(editor.state.domain_basis)


def _gentuning_parts(text: str) -> tuple[str, str, str]:
    """Split a generator-tuning cents value into ``(sign, whole, frac)`` for the genmap's
    clickable signed face: a non-negative value carries an explicit ``"+"`` (ordinarily
    assumed), a negative one a ``"−"`` with the bare magnitude; blank text (quantities off)
    carries no sign. The sign glyph is the part the user clicks to flip the generator."""
    if not text:
        return "", "", ""
    sign, body = ("−", text[1:]) if text.startswith("-") else ("+", text)
    whole, frac = _cents_parts(body)
    return sign, whole, frac


def _power_parts(text) -> tuple[str, str]:
    """Split an optimization/norm power into a stacked face: ``∞`` carries a small ``"(max)"``
    below it (it IS the max-norm / minimax power), the way a cents value carries its decimal;
    a numeric power (``2``, ``1``) shows bare, with no annotation."""
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
    **{d: 0.59 for d in "0123456789"},
    ".": 0.22, "-": 0.35, "/": 0.52, " ": 0.24,
    "[": 0.37, "]": 0.37, "{": 0.41, "}": 0.41, "⟨": 0.38, "⟩": 0.38,
}


def _ptext_units(text: str) -> float:
    """``text``'s width in em (font-size multiples), summed from the real per-glyph widths —
    so a punctuation-heavy value is estimated narrower than a digit-dense one of the same
    length, and each sizes to fill its box."""
    return sum(_PTEXT_GLYPH_EM.get(c, _PTEXT_DEFAULT_EM) for c in text)


def _ptext_font(text: str, width: float) -> float:
    """The largest font (px, capped at PTEXT_MAX_FONT) at which ``text`` fits on ONE line
    within a ``width``-px box. The plain-text contract is fit-on-one-line, so there is NO
    readability floor: a dense value (a prescaling ket-matrix at a high prime limit) keeps
    shrinking until it fits rather than spilling, and a short one grows to the cap. Width is
    estimated per glyph (_ptext_units) rather than by a uniform char width, so punctuation-
    heavy strings use the room they actually have. Truncated (not rounded) to 0.1px so the
    chosen size never rounds back up past the fit and spills."""
    units = _ptext_units(text)
    fit = (width - 2) / units if units else spreadsheet.PTEXT_MAX_FONT
    return int(min(spreadsheet.PTEXT_MAX_FONT, fit) * 10) / 10


_RATIO_MAX_FONT = 13.0  # px — the comfortable stacked-fraction size (matches .rtt-ratio in rtt.css)
_RATIO_DIGIT_EM = _PTEXT_GLYPH_EM["0"]  # a digit's width in em (the ptext estimate; fraction lines are all digits)
_RATIO_PAD = 6.0  # px — the .rtt-frac-num/.rtt-frac-den left+right padding (3px a side, the bar's overhang),
                  # fixed regardless of font, so it is reserved before the digits get the rest of the cell


def _digit_fit_font(longest, width: float, max_font: float) -> float:
    """The largest font (px, capped at ``max_font``) at which ``longest`` digits plus the fixed
    fraction-bar padding fit a ``width``-px square. Truncated (not rounded) to 0.1px so the chosen
    size never rounds back up and spills; like ``_ptext_font`` there is no readability floor — the
    cell is a hard boundary. Shared by the stacked-fraction face (capped at the comfortable ratio
    size) and the big-integer view (capped at the value-cell font)."""
    if not longest:
        return max_font
    fit = (width - _RATIO_PAD) / (longest * _RATIO_DIGIT_EM)
    return int(min(max_font, fit) * 10) / 10


def _ratio_font(num, den, width: float) -> float:
    """The largest font (px, capped at ``_RATIO_MAX_FONT``) at which a stacked fraction's longer
    line fits its ``width``-px square. A long numerator or denominator (e.g. 65536 = the target
    2/1 re-vectored to [16 0 0⟩) spills the 30px cell at the comfortable size, so the whole
    fraction shrinks to fit — num and den share the size, as a fraction should."""
    return _digit_fit_font(max(len(num), len(den)), width, _RATIO_MAX_FONT)


_DESCENDERS = "gjpqy"  # letters whose tail dips below the baseline


def _underline_html(text: str, spans) -> str:
    """``text`` with each ``(start, len)`` span wrapped in ``<u>`` — the mnemonic
    underline marking a caption's symbol letter. All text is HTML-escaped. A span
    holding a descender (g/j/p/q/y) is tagged ``rtt-desc`` so only its underline is
    dropped below the tail; the rest keep the normal snug underline."""
    out, i = [], 0
    for start, length in sorted(spans):
        seg = text[start:start + length]
        tag = '<u class="rtt-desc">' if any(c in _DESCENDERS for c in seg) else "<u>"
        out.append(_escape(text[i:start]) + tag + _escape(seg) + "</u>")
        i = start + length
    out.append(_escape(text[i:]))
    return "".join(out)


# The "example" column of the Show panel's "specific tiles & controls" group: one illustrative
# sample per toggle, read from the mockup's Show legend. Most are a glyph or short string (the
# maps' bold-italic letters, the vectors/matrices' bold-upright ones, the plain captions); a few
# (the colorization swatch, the audio speaker, the tuning-ranges I-beam) are graphical, built in
# _example_html. The "general" group is no longer a checkbox column with samples — it is the
# clickable dummy tile, which carries its own sample content (see the _TILE_* block below) — so
# this table holds only the specific-group keys.
_EXAMPLE_TEXT: dict[str, str] = {
    "counts": "𝑑",
    "interval_ratios": "2.3.5",
    "interval_vectors": "[−4 4 −1⟩",          # an interval as a column vector (monzo) — the syntonic comma 81/80
    "ebk": "⟨1 0 -4]",                        # the bra-ket notation itself (a map ⟨…]); off → the plain [1 0 -4]
    "domain_units": "p₁/",
    "temperament_tiles": "𝑀",
    "form": "𝑀" + spreadsheet.SUBSCRIPT_C,  # the canonical-form subscript this layer adds (𝑀 → 𝑀_C)
    "form_controls": "canonical form",
    "form_tiles": "𝐹",                       # the generator form matrix (the mockup's form-tiles example)
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
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with grey horizontal
    gridlines (the chart's tick lines) and a bar dipping below the zero line, as the mockup's
    legend shows. Bars + axes ride BR_COLOR and the gridlines _CHART_GRID — the same tokens the
    real chart and the EBK frame use — so the dark overlay's [fill]/[stroke] rules retint them."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            # grey horizontal tick lines at the ±5 levels (the chart's gridlines)
            f'<line x1="2" y1="5" x2="64" y2="5" stroke="{_CHART_GRID}" stroke-width="1"/>'
            f'<line x1="2" y1="29" x2="64" y2="29" stroke="{_CHART_GRID}" stroke-width="1"/>'
            f'<line x1="2" y1="3" x2="2" y2="31" stroke="{BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="0" y1="5" x2="6" y2="5" stroke="{BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="0" y1="29" x2="6" y2="29" stroke="{BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="2" y1="17" x2="62" y2="17" stroke="{BR_COLOR}" stroke-width="1"/>'
            f'<rect x="16" y="17" width="22" height="6" fill="{BR_COLOR}"/>'
            '</svg></div>')


def _example_html(key: str) -> str:
    """The example-column sample for one "specific tiles & controls" toggle, as an HTML string.
    (The "general" group is no longer a checkbox column — it is the clickable dummy tile, which
    renders its own samples; see _general_part_html.)"""
    if key in show_settings.GROUPING_PARENTS:
        return ""  # a pure grouping parent (temperament / form / tuning) — nothing of its own to illustrate
    if key in ("temperament_colorization", "tuning_colorization", "form_colorization"):
        # a swatch of the actual wash colour (one source of truth with _TINTS), stamped with
        # the fundamental matrix that drives it: 𝑀 (mapping), 𝐺 (generator embedding), 𝐹 (form)
        group = key.split("_")[0]
        letter = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}[group]
        return (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:36px;height:14px;background:var(--wash-{group})">{_math_html(letter)}</span>')
    if key == "tuning_ranges":  # the tuning-range I-beam (min/max generator bars)
        return ('<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
                '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
                '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
                '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>')
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


_TILE_NAME = "tile name"        # the name caption; its symbol-spelling letter (the n of "name") underlines for mnemonics
_TILE_SYMBOL = "𝒏"              # the quantity symbol — a bold-italic n, matching the underlined letter
_TILE_ROWLABEL = "𝒏₁"           # the matrix's row header (a matlabel) — its own header_symbols layer, like real row labels
_TILE_EQUIV = " = 𝑒G"          # the symbol's defining-equation tail (𝒏 = 𝑒G — mixed object styling: italic scalar, upright matrix)
_TILE_MATH = "1200·log₂(3/2) ="  # math_expressions: a value's closed form; the "=" belongs to the EXPRESSION, not the value
_TILE_VALUE = "701.955"         # quantities: the bare value the form evaluates to (no "=" — that rides the expression); 3 dp, the grid's cents precision
_TILE_UNITS = "¢/p"             # units: the value's unit (cents per prime) — the "units: …" line AND the per-cell unit
_TILE_PTEXT = "⟨1200 1902 2786]"  # plain_text_values: the same kind of value as a one-line EBK string

_TILE_MNEMONIC_AT = _TILE_NAME.index("n")  # where the mnemonic underline falls (the symbol's letter)

def _tile_name_pieces() -> tuple[str, str, str]:
    """The name caption split at its mnemonic letter — (before, letter, after) — so the letter
    (the mnemonics target) and the rest of the word (the names target) are separate click targets
    that still read as one word. For "tile name" with the 'n' marked: ("tile ", "n", "ame")."""
    i = _TILE_MNEMONIC_AT
    return _TILE_NAME[:i], _TILE_NAME[i], _TILE_NAME[i + 1:]


def _tile_fold_html() -> str:
    """The decorative fold toggle for the tile's top-left corner — the same boxed double-chevron
    glyph a real tile carries (open/collapse state). Inert here; it only makes the tile read as a tile."""
    return _control_svg(_FOLD_GLYPH["unfold_less"])


# The value cell's geometry (px), built to read like the real mapping tile's NESTED EBK: an INNER
# per-row covector ⟨ … ] HUGGING the COL_W×ROW_H square cell (the angle/square marks sit right
# against the box, ~BR_INSET≈2.5px off, exactly as the grid's per-row brackets do), enclosed by an
# OUTER frame — a top bracket + brace that SPAN the inner brackets and sit _TILE_ENCLOSE px above /
# below the cell. (Earlier rounds wrongly pushed the brackets far horizontally; the real app hugs.)
_TILE_CELL = spreadsheet.COL_W           # the square cell side (== ROW_H)
_TILE_BR_W = 9                            # inner ⟨ / ] bracket width — hugs the cell (no gap)
_TILE_ENCLOSE = 5                         # gap between the OUTER top/brace and the cell (the enclosing space)
_TILE_CAP = 5                             # outer top-bracket / brace height
_TILE_FRAME_W = _TILE_BR_W + _TILE_CELL + _TILE_BR_W            # the outer top/brace span ⟨ … ]
_TILE_FRAME_H = _TILE_CAP + _TILE_ENCLOSE + _TILE_CELL + _TILE_ENCLOSE + _TILE_CAP
_TILE_CELL_X = _TILE_BR_W                 # the cell's left edge within the frame (right after the inner ⟨)
_TILE_CELL_Y = _TILE_CAP + _TILE_ENCLOSE  # the cell's top edge within the frame (below the outer top)


def _tile_grid_frame_html() -> str:
    """The value cell's NESTED EBK, like the mapping tile: an inner covector ⟨ … ] hugging the
    COL_W×ROW_H white box, enclosed by an outer top bracket + brace that span the inner brackets and
    sit _TILE_ENCLOSE above / below the cell. The builder lays the closed form and value in the box."""
    def mark(x, y, w, h, inner):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">{inner}</div>'
    cell, cap, bw, cx, cy = _TILE_CELL, _TILE_CAP, _TILE_BR_W, _TILE_CELL_X, _TILE_CELL_Y
    span = _TILE_FRAME_W  # the outer top/brace run the full ⟨ … ] width
    return (f'<div style="position:relative;width:{_TILE_FRAME_W}px;height:{_TILE_FRAME_H}px">'
            # OUTER frame: top bracket + brace spanning the inner brackets, enclosing from above/below
            + mark(0, 0, span, cap, top_bracket(span, cap))
            + mark(0, _TILE_FRAME_H - cap, span, cap, brace(span, cap))
            # INNER covector ⟨ … ] hugging the value box
            + mark(0, cy, bw, cell, angle_bracket(bw, cell))
            + mark(cx, cy, cell, cell, '<div style="width:100%;height:100%;box-sizing:border-box;'
                                       'border:1px solid #555;background:#fff"></div>')
            + mark(cx + cell, cy, bw, cell, square_bracket(bw, cell, "right"))
            + '</div>')


def _tile_preset_html() -> str:
    """The presets-chooser sample, styled like the app's real q-select dropdowns: a white bordered
    field showing the "(presets)" placeholder with a dropdown caret."""
    return ('<span style="display:flex;align-items:center;justify-content:space-between;'
            'gap:4px;width:100%;height:22px;box-sizing:border-box;background:#fff;border:1px solid #999;'
            'border-radius:2px;padding:0 2px 0 6px;font-size:13px;color:#000">(presets)'
            '<span class="material-icons" style="font-size:16px;color:#555">arrow_drop_down</span></span>')


def _general_part_html(key: str) -> str:
    """The inner sample HTML for one general tile layer (every general key has one). The value
    cell's three layers split apart — gridded_values is the EBK-framed box, math_expressions the
    closed form, quantities the value (the builder stacks the form and value inside the box) — and
    the rest are a glyph, the name word, the units, the plain-text string, the presets field, or a
    chart sparkline."""
    if key == "gridded_values":
        return _tile_grid_frame_html()
    if key == "math_expressions":
        return _math_html(_TILE_MATH)
    if key == "quantities":
        # the value's whole part (the big "701"), drawn with the live grid's stacked-value main class
        # so it reads at the size a real cents cell uses. Its three-decimal fraction is the SEPARATE
        # `decimals` part stacked just beneath (so the value and its decimals are each their own click
        # target) — the builder seats the two so they read as one whole-over-.fraction cents value.
        whole, _frac = _cents_parts(_TILE_VALUE)
        return f'<span class="rtt-stacked-main">{whole}</span>'
    if key == "decimals":
        # the value's three-decimal fraction (the small ".955" beneath the whole part) — the
        # `decimals` sub-control's own click target, in the grid's stacked-value sub class. Turning
        # it off rounds every value in the app to the nearest integer (see service.cents).
        _whole, frac = _cents_parts(_TILE_VALUE)
        return f'<span class="rtt-stacked-sub">.{frac}</span>'
    if key == "symbols":
        return _math_html(_TILE_SYMBOL)
    if key == "header_symbols":  # the matrix's row/col header label (matlabel), in the cell's left gutter
        return _math_html(_TILE_ROWLABEL)
    if key == "equivalences":
        return _math_html(_TILE_EQUIV)
    if key == "names":
        return _escape(_TILE_NAME)
    if key == "mnemonics":
        return _escape(_tile_name_pieces()[1])
    if key == "units":
        return f'<span class="rtt-units-pre">units: </span>{_units_html(_TILE_UNITS)}'
    if key == "cell_units":  # the per-value unit beneath a gridded cell (no "units:" prefix)
        return _units_html(_TILE_UNITS)
    if key == "plain_text_values":
        return _math_html(_TILE_PTEXT)
    if key == "presets":
        return _tile_preset_html()
    if key == "charts":
        return _example_chart()
    if key == "drag_to_combine":  # a grip glyph — the drag handle this layer adds to rows and intervals
        return '<span class="material-icons" style="color:#444">drag_indicator</span>'
    raise KeyError(key)  # every general layer must have a sample


def _demath(ch: str) -> tuple[str, bool, bool] | None:
    """A Mathematical Alphanumeric letter (or bold digit) as ``(base, bold, italic)``,
    or None for an ordinary character. Covers the bold, italic and bold-italic letter
    blocks — the maps (bold-italic), matrices/vectors (bold-upright) and the counts'
    plain italic variables — plus the bold digits (the zero list 𝟎 the held interval
    errors vanish to); other characters pass through unstyled."""
    cp = ord(ch)
    if 0x1D7CE <= cp <= 0x1D7D7:  # bold digits 𝟎–𝟗
        return chr(ord("0") + cp - 0x1D7CE), True, False
    if 0x1D400 <= cp <= 0x1D419:  # bold capitals
        return chr(ord("A") + cp - 0x1D400), True, False
    if 0x1D41A <= cp <= 0x1D433:  # bold small
        return chr(ord("a") + cp - 0x1D41A), True, False
    if 0x1D434 <= cp <= 0x1D44D:  # italic capitals
        return chr(ord("A") + cp - 0x1D434), False, True
    if 0x1D44E <= cp <= 0x1D467:  # italic small
        return chr(ord("a") + cp - 0x1D44E), False, True
    if 0x1D468 <= cp <= 0x1D481:  # bold-italic capitals
        return chr(ord("A") + cp - 0x1D468), True, True
    if 0x1D482 <= cp <= 0x1D49B:  # bold-italic small
        return chr(ord("a") + cp - 0x1D482), True, True
    return None


def _math_html(text: str) -> str:
    """``text`` with each Mathematical Alphanumeric letter rendered as its base
    letter in a span carrying explicit CSS weight/slant — so the UI serif draws a
    correctly bold/italic glyph rather than depending on a maths font (which font
    fallback mis-rendered). Ordinary characters pass through, HTML-escaped. The
    matlabel NORM_SUB sentinels wrap a range as italic subscript (the trailing q
    on the complexity row's ‖L𝐜ᵢ‖q). Used for the quantity symbols, their
    equivalence tails, and the matrix labels."""
    out = []
    for ch in text:
        if ch == spreadsheet.NORM_SUB_OPEN:
            out.append('<sub style="font-style:italic">')
            continue
        if ch == spreadsheet.NORM_SUB_CLOSE:
            out.append('</sub>')
            continue
        if ch == spreadsheet.SUB_OPEN:  # a plain subscript: each glyph keeps its own slant
            out.append('<sub>')          # (so "dual" stays upright while the math-italic 𝑞 slants)
            continue
        if ch == spreadsheet.SUB_CLOSE:
            out.append('</sub>')
            continue
        styled = _demath(ch)
        if styled is None:
            out.append(_escape(ch))
            continue
        base, bold, italic = styled
        css = (["font-weight:700"] if bold else []) + (["font-style:italic"] if italic else [])
        out.append(f'<span style="{";".join(css)}">{_escape(base)}</span>')
    return "".join(out)


# Within a unit value these tokens stay un-bold: the units of interval size — the cent
# sign ¢ and the spelled-out "oct" (octaves) — plus the fraction slash and spaces. The
# variable symbols (g, p, b and the placeholder 1, with subscripts) are bold —
# consistently in the per-box line AND the units row/col.
_UNIT_PLAIN = ("oct", "¢", "/", " ")


_SUB_TAGS = {
    spreadsheet.SUB_OPEN: "<sub>", spreadsheet.SUB_CLOSE: "</sub>",
    spreadsheet.NORM_SUB_OPEN: '<sub style="font-style:italic">', spreadsheet.NORM_SUB_CLOSE: "</sub>",
}


def _run_html(s: str) -> str:
    # a bold-able unit run, HTML-escaped, with the subscript sentinels turned into <sub>…</sub>
    # (so the superspace marker gʟ reads as g + subscript capital L, not the raw PUA chars)
    return "".join(_SUB_TAGS.get(ch) or _escape(ch) for ch in s)


def _bold_units(value) -> str:
    """A unit value with its variable symbols bold (the unit letters g/p and the
    placeholder 1, plus any subscript), leaving the units ¢ and ``oct`` and the ``/``
    separator un-bold. Bolds maximal runs of variable characters so e.g. ``g₁/`` →
    ``<b>g₁</b>/``, ``oct/p`` → ``oct/<b>p</b>``. All text HTML-escaped."""
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
    """A unit label (kind ``units``). The value's face — a single-story-g sans — comes
    from the ``.rtt-units`` class; the variable symbols are bold (see :func:`_bold_units`).
    A per-box line (``units: g/p``) keeps its ``units:`` label in the serif body face; a
    bare domain-units coordinate label (``g₁/``, ``/p₁``, ``¢/``) is just the bolded value."""
    prefix = "units: "
    if text.startswith(prefix):
        return f'<span class="rtt-units-pre">{prefix}</span>{_bold_units(text[len(prefix):])}'
    return _bold_units(text)


# spacing of the dots on a folded band's gridline: a LINE_W-long dot every _DOT_PITCH px.
# CSS `border-style:dotted` packs dots ~one border-width apart (≈2*LINE_W period) and gives
# no control; painting them ourselves lets us space them out — here ≈twice as sparse.
_DOT_PITCH = 8


def _line_style(ln, y_shift: float = 0) -> str:
    """Absolute-position CSS for one gridline rule (a zero-size div carrying a single
    border). The border grows off one edge, so shift the box back by half the line width
    to seat the rule centred on its coordinate (its toggle-node / cell-column centre).
    ``y_shift`` lifts the rule into the body's scroll space (the frozen column strip's
    height), since every gridline lives on the scrolling board. A folded band's rule reads
    as dotted (a placeholder for the hidden content): the dots are painted as a repeating
    gradient showing through a TRANSPARENT border, so the box keeps its zero cross-size and
    the rule neither resizes nor shimmers as a band folds. The border colour + background
    are emitted here every update, so re-expanding restores the solid rule rather than
    leaving a stuck override -- v rules carry border-left, h rules border-top (per the CSS)."""
    half = spreadsheet.LINE_W / 2
    if ln.orientation == "v":
        pos, edge, sweep = f"left:{ln.pos - half}px; top:{ln.start - y_shift}px; height:{ln.length}px", "left", "to bottom"
    else:
        pos, edge, sweep = f"top:{ln.pos - half - y_shift}px; left:{ln.start}px; width:{ln.length}px", "top", "to right"
    if ln.dotted:
        # paint the dots over the border box (the box has no width of its own — just the
        # border), so the gradient fills the LINE_W-wide border strip rather than the
        # zero-width content box; the transparent border lets it show.
        dots = (f"repeating-linear-gradient({sweep},var(--c-gridline) 0 {spreadsheet.LINE_W}px,"
                f"transparent {spreadsheet.LINE_W}px {_DOT_PITCH}px) border-box")
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:var(--c-gridline); background:none"


def _select_props(min_width: float) -> str:
    """Shared Quasar props for every chooser dropdown (preset / target / form / control
    select): a compact borderless field whose open popup is at least as wide as its trigger
    (``min_width`` px) but grows to ``max-content``, so each entry shows on one line rather
    than wrapping or truncating at the trigger's width."""
    return ("dense options-dense borderless hide-bottom-space "
            "popup-content-class=rtt-select-popup "
            f"popup-content-style=min-width:{min_width}px;width:max-content")
