"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.web.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

import json
import math
import os
import sys
from html import escape as _escape
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, NamedTuple
from urllib.parse import quote

from nicegui import app, helpers, ui

from rtt.web import presets
from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web import tooltips
from rtt.web.editor import Editor
from rtt.web.marks import (
    _BR_COLOR,
    _PENDING_COLOR,
    _angle_bracket,
    _angle_foot,
    _brace,
    _curly_bracket,
    _ebk_svg,
    _qbez,
    _rect,
    _ribbon,
    _square_bracket,
    _svg,
    _top_bracket,
    _vbar,
)


class _KindHandlers(NamedTuple):
    """The build + update pair for one cell kind — the unified replacement for the two
    parallel ``if/elif cb.kind`` ladders (audit #3). ``build(cb, wrap)`` creates the cell's
    child element(s) and registers their per-id handles; ``update(cb)`` refreshes the live
    element from the cell box. ``update`` is None for static kinds (built once, never refilled)."""
    build: Callable
    update: Callable | None = None


_ASSETS = Path(__file__).parent / "assets"  # CSS/JS asset files, loaded at import time

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration
_PANEL_W = 330  # px width the settings drawer opens to (the Show + example columns)
_RAIL_W = 40  # px width of the permanent left rail (hamburger + the rotated app title)
_TOOLTIP_DELAY_MS = 700  # hover delay before a tooltip appears — long enough that the dense grid's
# help waits for a deliberate rest instead of popping on every passing cursor (Quasar defaults to 0)
_STORE_KEY = "rtt_doc"  # store key holding the serialized document (survives refresh)
_STORAGE_SECRET = "dnd-rtt-app"  # signs the per-browser session cookie that keys app.storage.user
# Under NiceGUI's in-process User test simulation, app.storage.user is file-backed: writing
# it on every render both litters the tree and races the harness's teardown file-cleanup on
# Windows. The tests re-import this module per case, so a module-level dict gives the same
# survives-a-refresh persistence, isolated per test, with no file I/O. Production is unaffected.
_MEMORY_STORE: dict = {}


def _doc_store() -> dict:
    """Where the serialized document is persisted: the per-browser ``app.storage.user`` in
    production, an in-process dict under the test simulation (see :data:`_MEMORY_STORE`)."""
    return _MEMORY_STORE if helpers.is_user_simulation() else app.storage.user

_SEAM = "#999"  # the thin grey rule separating the frozen title panes from the scrolling body
_PREVIEW_COLOR = "#f5a623"  # amber ring on a cell the in-progress edit moves (the edit-preview
# highlight) — a warm "this changed" hue, kept distinct from the red _PENDING_COLOR error/alert
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
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

# Colorization wash colours, keyed by the group the layout tags a wash with
# (spreadsheet.CELL_FACTORS via _FACTOR_GROUP); a wash sits behind the grey tiles so the
# colour reads through the gaps around them. The three are the muted-channel trio — each
# dims ONE RGB channel to 0x9a — so their darken blends stay clean (tuning ⊓ temperament =
# #9acd9a, the mockup's green). cyan = tuning (the generator embedding G), khaki =
# temperament (the mapping 𝑀 / comma basis C), magenta = form (the form matrix 𝐹 — its
# wash is deferred; the palette entry feeds the greyed Show-panel swatch for now).
_TINTS = {"tuning": "#9acdcd", "temperament": "#cdcd9a", "form": "#cd9acd"}

_AUDIO_KINDS = {"speaker"}  # cells whose baked cents rebuild when the tuning changes
_AUDIO_CTRLS = {"audio_wave", "audio_mode", "audio_hold", "audio_root"}  # the per-tile bank controls


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


# the four play modes' 3×3 glyphs: 1 one-off (centre), 2 arpeggiate (bottom-left→top-right
# diagonal), 3 chord (centre column), 4 rolled chord (diagonal + the bottom-right triangle)
_MODE_FILLS = (
    frozenset({(1, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2)}),
    frozenset({(0, 1), (1, 1), (2, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2), (1, 2), (2, 1), (2, 2)}),
)
# Glyph variants the bank cycles through. Generated once in Python and shared with the JS
# (injected as rttAudio.glyphs) so the click-side redraw uses the very same markup.
_AUDIO_GLYPHS = {
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(f) for f in _MODE_FILLS],
    "lock": ['<span class="material-icons rtt-audio-glyph">lock_open</span>',
             '<span class="material-icons rtt-audio-glyph">lock</span>'],
    "root": '<span class="rtt-audio-rootglyph">1/1</span>',
}

# The Web Audio engine. Each audio tile owns independent state (waveform, play-mode, hold/loop,
# include-1/1), keyed by tile id; the bank controls cycle it and redraw their glyph client-side,
# and a speaker calls rttAudio.hit(tile, idx, [cents…]) to sound per that state — all CLIENT-side
# (no server round-trip). 1/1 (root) sounds UNDERNEATH as a drone; playing notes' speakers
# highlight. freq = 261.626·2^(¢/1200) (1/1 = middle C). Modes (0..3): one-off, arpeggiate from
# the clicked note, chord, rolled chord; hold sustains (mode 0 stacks notes) or loops (2 & 4).
_AUDIO_JS = (_ASSETS / "audio.js").read_text(encoding="utf-8")

# Frozen-pane support. The row band freezes by position:sticky (zero JS on its scroll path), but the
# column-title strip sits OUTSIDE the body scroller (so the vertical scrollbar can stop below it), so
# it can't ride the scroll via CSS — this listener translateX-syncs it to the body's horizontal
# scroll. It also reveals the seams: a frozen region is "stuck" (body scrolled under it) exactly when
# .rtt-gridbody has scrolled off zero on that axis, toggled as rtt-scrolled-x/y on .rtt-app. scroll
# doesn't bubble → capture phase, so the body's scroll events are still caught here.
_FREEZE_JS = (_ASSETS / "freeze.js").read_text(encoding="utf-8")
# delegated drag-and-drop glue for the interval-column grips / drop slots (see drag.js): arms the
# drop slots while a grip is dragging, prevents dragover default so a drop fires, and highlights
# the hovered slot — all client-side; the pick-up and drop themselves cross to Python.
_DRAG_JS = (_ASSETS / "drag.js").read_text(encoding="utf-8")


def _option_box_svg(fill: str | None) -> str:
    """A data-URI SVG of the option-box indicator: an n×n white square with a 1px #555 border
    and, when ``fill`` is given, a centred inner square (inset by the 1px border + a 2px gap) of
    that colour. Used as the BACKGROUND of every q-checkbox box and the tuning-ranges radio box,
    so the whole mark scales as ONE vector — staying square with an even border at any zoom —
    instead of separate CSS box edges (border + inset fill), which the browser snaps independently
    to the device-pixel grid, distorting the square and the gap at fractional zooms / positions."""
    n = spreadsheet.OPTION_BOX_PX
    inner = f"<rect x='3' y='3' width='{n - 6}' height='{n - 6}' fill='{fill}'/>" if fill else ""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}'>"
           f"<rect x='.5' y='.5' width='{n - 1}' height='{n - 1}' fill='#fff' stroke='#555' stroke-width='1'/>"
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


def _grip_svg() -> str:
    """A column drag-handle glyph: two columns of three dots (a ⠿ grip) in currentColor, so the
    cell's CSS colour and :hover tint it. No bordered box (unlike the ± buttons) — a dotted grip
    reads as 'grab me' rather than 'click me', and it's a thin vertical handle for the narrow slot."""
    dots = "".join(f"<circle cx='{cx}' cy='{cy}' r='0.9' fill='currentColor'/>"
                   for cx in (2, 5) for cy in (3, 8, 13))
    return f"<svg viewBox='0 0 7 16' xmlns='http://www.w3.org/2000/svg'>{dots}</svg>"


_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --rail-w:{_RAIL_W}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --pending-color:{_PENDING_COLOR}; --preview-color:{_PREVIEW_COLOR};
  --cell-border-w:{_CELL_BORDER_W}px; --cell-border:{_CELL_BORDER}; --cell-font:{_CELL_FONT}px;
  --label-w:{spreadsheet.LABEL_W}px; --header-h:{spreadsheet.HEADER_H}px; --line-w:{spreadsheet.LINE_W}px;
  --ptext-edit-h:{spreadsheet.PTEXT_EDIT_H}px; --option-box:{spreadsheet.OPTION_BOX_PX}px; --btn:{spreadsheet.BTN}px;
  --option-box-unchecked:url("{_option_box_svg(None)}");
  --option-box-checked:url("{_option_box_svg('#000')}");
  --option-box-disabled:url("{_option_box_svg('#888')}");
}}
"""

# The bulk stylesheet lives in assets/rtt.css; it references the CSS custom properties above,
# which _CSS_VARS feeds the Python-side constants (sizes, colours, the option-box SVG data URIs).
_CSS = _CSS_VARS + (_ASSETS / "rtt.css").read_text(encoding="utf-8")


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


def _mathexpr_html(text: str, width: float) -> str:
    """The stacked HTML for a math-expression cell: each newline-separated line on
    its own row, its font shrunk to fit the cell so long expressions stay in-bounds."""
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{line}</div>'
        for line in text.split("\n")
    )
    return f'<div class="rtt-mathexpr-stack">{lines}</div>'

# Every EBK mark is drawn by hand as an SVG sized to the cell. The viewBox is the
# cell's own px box (0 0 w h), so one viewBox unit == one px: a stroke we declare
# as N px renders exactly N px wide regardless of how tall/long the mark spans.
# This is the single rule that keeps the brackets and brace a constant weight —
# the rejected font glyph scaled its weight with its height, and a fixed viewBox
# stretched to the cell sheared its serifs. Square/top brackets are crisp filled
# rects; the calligraphic ⟨ and brace are filled variable-width ribbons (_ribbon).
_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar"}


def _chart_ticks(lo, hi):
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


def _bar_chart(w, h, values, indicator=None, indicator_label=""):
    """A bar chart filling its 1:1 px box: one bar per value, aligned to the value
    columns below, rising/falling from a zero baseline; gridlines mark nice ticks. When
    ``indicator`` is set (the optimization objective ⟪𝐝⟫ₚ on the damage chart), a solid
    lighter-grey line marks that minimized-damage level across the plot, broken by a
    ⟪𝐝⟫ label whose subscript is ``indicator_label`` (the scheme's Lp power ∞ / 2 / 1)."""
    axis_x, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    vals = tuple(values)
    ticks = _chart_ticks(min(vals + (0.0,)), max(vals + (0.0,)))  # 0 in range: baseline shows
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
                    f'font-size="7" fill="{_BR_COLOR}">{tv:g}</text>')
    zero_y = y_of(0)
    body.append(f'<line x1="{axis_x:.2f}" y1="{zero_y:.2f}" x2="{w:.2f}" y2="{zero_y:.2f}" '
                f'stroke="{_BR_COLOR}" stroke-width="1"/>')
    body.append(_rect(axis_x, plot_top, 0.8, plot_bot - plot_top))  # vertical y-axis
    bw = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(vals):
        cx = axis_x + i * col_w + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(_rect(cx - bw / 2, top, bw, bot - top))
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
    return _svg(w, h, "".join(body))


def _range_chart(w, h, ranges, tunings=()):
    """The generator tuning-ranges chart filling its 1:1 px box: one vertical I-beam per
    generator showing its [min, max] tuning in cents (max at the top cap, min at the
    bottom), with a shorter tick marking where the live tuning falls within that range. A
    pinned generator (min == max) draws a single flat cap; empty ``ranges`` draws a 'no
    range' placeholder. The 'tuning ranges' title is a boxtitle above the chart, not in the SVG."""
    cx0, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    if not ranges:
        return _svg(w, h, f'<text x="{w / 2:.2f}" y="{h / 2 + 2:.2f}" text-anchor="middle" '
                    f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">no range</text>')
    plot_top, plot_bot = _RANGE_PLOT_T, h - _RANGE_PLOT_B
    mid, hw = (plot_top + plot_bot) / 2, _RANGE_MARK_W / 2
    cap_half, tick_half = _RANGE_CAP_W / 2, _RANGE_CAP_W / 2 - 3  # the live-tuning tick is shorter

    def bar(cx, y, half):
        return _rect(cx - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(cx, y, v):
        return (f'<text x="{cx:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">{v:.3f}</text>')

    body = []
    for i, (lo, hi) in enumerate(ranges):
        cx = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:  # pinned (e.g. the period): one value, no range — a single cap
            body.append(bar(cx, mid, cap_half) + label(cx, mid - 4, lo))
            continue
        # a vertical stem capped at the max (top) and min (bottom), labelled at each
        body.append(_rect(cx - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(cx, plot_top, cap_half) + bar(cx, plot_bot, cap_half))
        body.append(label(cx, plot_top - 4, hi) + label(cx, plot_bot + 9, lo))
        if i < len(tunings):  # the live tuning, ticked where it falls within [min, max]
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(cx, plot_top + frac * (plot_bot - plot_top), tick_half))
    return _svg(w, h, "".join(body))


def _parse_int(text):
    """``text`` -> int, or None for blank/partial input (matching the old parseInt)."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _ratio_parts(text):
    """Split a ratio like ``"3/2"`` into ``("3", "2")``; None if it isn't a fraction."""
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text):
    """Split a cents value like ``"1899.260"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _gentuning_parts(text):
    """Split a generator-tuning cents value into ``(sign, whole, frac)`` for the genmap's
    clickable signed face: a non-negative value carries an explicit ``"+"`` (ordinarily
    assumed), a negative one a ``"−"`` with the bare magnitude; blank text (quantities off)
    carries no sign. The sign glyph is the part the user clicks to flip the generator."""
    if not text:
        return "", "", ""
    sign, body = ("−", text[1:]) if text.startswith("-") else ("+", text)
    whole, frac = _cents_parts(body)
    return sign, whole, frac


def _power_parts(text):
    """Split an optimization/norm power into a stacked face: ``∞`` carries a small ``"(max)"``
    below it (it IS the max-norm / minimax power), the way a cents value carries its decimal;
    a numeric power (``2``, ``1``) shows bare, with no annotation."""
    return (text, "(max)") if text == "∞" else (text, "")


# Per-glyph widths (in em — font-size multiples) for the .rtt-ptext face, used to estimate a
# plain-text value's width without a browser. An EBK string mixes wide digits with narrow
# punctuation and spaces, so a single average char width over-shrinks a punctuation-heavy
# value (e.g. a prescaling ket-matrix, mostly 0s, dots and spaces); summing the real glyphs
# lets each value fill its box. These are Cambria em-widths rounded up with a ~5% margin, so
# the estimate never falls short of the render and the value never spills. 0.59 (the widest
# glyph, a digit) is the fallback for any character not listed.
_PTEXT_DEFAULT_EM = 0.59
_PTEXT_GLYPH_EM = {
    **{d: 0.59 for d in "0123456789"},
    ".": 0.22, "-": 0.35, "/": 0.52, " ": 0.24,
    "[": 0.37, "]": 0.37, "{": 0.41, "}": 0.41, "⟨": 0.38, "⟩": 0.38,
}


def _ptext_units(text):
    """``text``'s width in em (font-size multiples), summed from the real per-glyph widths —
    so a punctuation-heavy value is estimated narrower than a digit-dense one of the same
    length, and each sizes to fill its box."""
    return sum(_PTEXT_GLYPH_EM.get(c, _PTEXT_DEFAULT_EM) for c in text)


def _ptext_font(text, width):
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


_DESCENDERS = "gjpqy"  # letters whose tail dips below the baseline


def _underline_html(text, spans):
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


# The "example" column of the Show panel's "specific boxes & controls" group: one illustrative
# sample per toggle, read from the mockup's Show legend. Most are a glyph or short string (the
# maps' bold-italic letters, the vectors/matrices' bold-upright ones, the plain captions); a few
# (the colorization swatch, the audio speaker, the tuning-ranges I-beam) are graphical, built in
# _example_html. The "general" group is no longer a checkbox column with samples — it is the
# clickable dummy tile, which carries its own sample content (see the _TILE_* block below) — so
# this table holds only the specific-group keys.
_EXAMPLE_TEXT: dict[str, str] = {
    "counts": "𝑑",
    "domain_quantities": "2.3.5",
    "domain_units": "p₁/",
    "temperament_boxes": "𝑀",
    "form_controls": "canonical form",
    "tuning_boxes": "T",
    "optimization": "𝑝",
    "weighting": "𝒘",
    "all_interval": "minimax-S",
    "alt_complexity": "E-lp",
    "projection": "𝑃",
    "interest": "𝐢",
    "generator_detempering": "D",
    "nonstandard_domain": "prime-based",
    "identity_objects": "𝑀ⱼ",
}


def _example_chart() -> str:
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with grey horizontal
    gridlines (the chart's tick lines) and a bar dipping below the zero line, as the mockup's
    legend shows."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            # grey horizontal tick lines at the ±5 levels (the chart's gridlines)
            '<line x1="2" y1="5" x2="64" y2="5" stroke="#bbb" stroke-width="1"/>'
            '<line x1="2" y1="29" x2="64" y2="29" stroke="#bbb" stroke-width="1"/>'
            '<line x1="2" y1="3" x2="2" y2="31" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="5" x2="6" y2="5" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="29" x2="6" y2="29" stroke="#000" stroke-width="1.4"/>'
            '<line x1="2" y1="17" x2="62" y2="17" stroke="#000" stroke-width="1"/>'
            '<rect x="16" y="17" width="22" height="6" fill="#000"/>'
            '</svg></div>')


def _example_html(key: str) -> str:
    """The example-column sample for one "specific boxes & controls" toggle, as an HTML string.
    (The "general" group is no longer a checkbox column — it is the clickable dummy tile, which
    renders its own samples; see _general_part_html.)"""
    if key in ("temperament_colorization", "tuning_colorization", "form_colorization"):
        # a swatch of the actual wash colour (one source of truth with _TINTS), stamped with
        # the fundamental matrix that drives it: 𝑀 (mapping), 𝐺 (generator embedding), 𝐹 (form)
        group = key.split("_")[0]
        letter = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}[group]
        return (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:36px;height:14px;background:{_TINTS[group]}">{_math_html(letter)}</span>')
    if key == "audio":  # a speaker glyph — the per-pitch play button the audio rows carry
        return '<span class="material-icons" style="font-size:18px;color:#444">volume_up</span>'
    if key == "tuning_ranges":  # the tuning-range I-beam (min/max generator bars)
        return ('<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
                '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
                '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
                '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>')
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


# --- the "general" Show group's dummy tile ---------------------------------------------------
# The general layers render as ONE clickable dummy value tile (the alternative to a checkbox
# column), laid out as a real tile reads: the boxed value cell on top — with its closed form and
# value INSIDE the box, the way they appear on a tile rather than as rows of their own — then the
# symbol, the name, units, the plain-text value, the presets chooser, and a chart. Each part is a
# dummy sample shown black when its layer is shown and grey when hidden; clicking it flips the
# layer in the live grid. The tile carries its OWN sample content (below); the specific group's
# example column still uses _example_html / _EXAMPLE_TEXT.
_TILE_NAME = "tile name"        # the name caption; its symbol-spelling letter (the n of "name") underlines for mnemonics
_TILE_SYMBOL = "𝒏"              # the quantity symbol — a bold-italic n, matching the underlined letter
_TILE_EQUIV = " = 𝑒G"          # the symbol's defining-equation tail (𝒏 = 𝑒G — mixed object styling: italic scalar, upright matrix)
_TILE_ROWLABEL = "𝒏₁"           # the matrix's row header (a matlabel) — rides the symbol layer, like real row labels
_TILE_MATH = "1200·log₂(3/2) ="  # math_expressions: a value's closed form; the "=" belongs to the EXPRESSION, not the value
_TILE_VALUE = "701.96"          # quantities: the bare value the form evaluates to (no "=" — that rides the expression)
_TILE_UNITS = "¢/p"             # units: the value's unit (cents per prime) — the "units: …" line AND the per-cell unit
_TILE_PTEXT = "⟨1200 1902 2786]"  # plain_text_values: the same kind of value as a one-line EBK string

_TILE_MNEMONIC_AT = _TILE_NAME.index("n")  # where the mnemonic underline falls (the symbol's letter)

# The tile's stacked lines, top to bottom, by their PRIMARY layer keys (left-to-right render
# order). The value cell additionally shows the symbol layer's row header and the units layer's
# per-cell unit (secondary appearances, added in the builder), and seats math_expressions /
# quantities INSIDE its box rather than on rows of their own. The symbol line seats the symbol +
# its equivalence tail; the name line the mnemonic letter + the rest of the name.
_GENERAL_TILE_LINES: tuple[tuple[str, ...], ...] = (
    ("gridded_values", "math_expressions", "quantities"),
    ("symbols", "equivalences"),
    ("mnemonics", "names"),
    ("units",),
    ("plain_text_values",),
    ("presets",),
    ("charts",),
)

# A tile part that renders INSIDE another's cell is inert (greyed, unclickable) until that host
# cell is shown — the dummy mirrors the grid, where the value and its closed form have nowhere to
# sit without the boxed cell. (The refinement layers — equivalences, mnemonics — are NOT here:
# they stay live and instead pull their base layer on when selected; see SUBCONTROLS / set_show.)
_TILE_HOST: dict[str, str] = {
    "quantities": "gridded_values",
    "math_expressions": "gridded_values",
}

# Per-layer font size in the tile (px), matched to the real tile constants so the dummy's
# proportions read like an actual tile: the symbol/equivalence glyph, the name caption, the row
# header (matlabel), the units line, and the per-cell unit (6px grey, like .rtt-cellunit). The
# closed form and value inside the cell are font-FITTED to the COL_W square (see the builder), so
# they aren't listed here.
_TILE_FONT = {
    "symbols": 15, "equivalences": 15, "rowlabel": spreadsheet.MATLABEL_H - 2,
    "names": spreadsheet.CAPTION_FONT, "mnemonics": spreadsheet.CAPTION_FONT,
    "units": 10, "cellunit": 6, "plain_text_values": 11,
}


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
# against the box, ~_BR_INSET≈2.5px off, exactly as the grid's per-row brackets do), enclosed by an
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
            + mark(0, 0, span, cap, _top_bracket(span, cap))
            + mark(0, _TILE_FRAME_H - cap, span, cap, _brace(span, cap))
            # INNER covector ⟨ … ] hugging the value box
            + mark(0, cy, bw, cell, _angle_bracket(bw, cell))
            + mark(cx, cy, cell, cell, '<div style="width:100%;height:100%;box-sizing:border-box;'
                                       'border:1px solid #555;background:#fff"></div>')
            + mark(cx + cell, cy, bw, cell, _square_bracket(bw, cell, "right"))
            + '</div>')


def _tile_preset_html() -> str:
    """The presets-chooser sample, styled like the app's real q-select dropdowns: a white bordered
    field showing the "(presets)" placeholder with a dropdown caret."""
    return ('<span style="display:flex;align-items:center;justify-content:space-between;'
            'gap:4px;width:100%;height:22px;box-sizing:border-box;background:#fff;border:1px solid #999;'
            'border-radius:2px;padding:0 2px 0 6px;font-size:12px;color:#000">(presets)'
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
        return _math_html(_TILE_VALUE)
    if key == "symbols":
        return _math_html(_TILE_SYMBOL)
    if key == "equivalences":
        return _math_html(_TILE_EQUIV)
    if key == "names":
        return _escape(_TILE_NAME)
    if key == "mnemonics":
        return _escape(_tile_name_pieces()[1])
    if key == "units":
        return f'<span class="rtt-units-pre">units: </span>{_units_html(_TILE_UNITS)}'
    if key == "plain_text_values":
        return _math_html(_TILE_PTEXT)
    if key == "presets":
        return _tile_preset_html()
    if key == "charts":
        return _example_chart()
    raise KeyError(key)  # every general layer must have a sample


def _demath(ch):
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


def _math_html(text):
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


def _bold_units(value):
    """A unit value with its variable symbols bold (the unit letters g/p and the
    placeholder 1, plus any subscript), leaving the units ¢ and ``oct`` and the ``/``
    separator un-bold. Bolds maximal runs of variable characters so e.g. ``g₁/`` →
    ``<b>g₁</b>/``, ``oct/p`` → ``oct/<b>p</b>``. All text HTML-escaped."""
    out, run = [], []

    def flush():
        if run:
            out.append(f"<b>{_escape(''.join(run))}</b>")
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


def _units_html(text):
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
        dots = (f"repeating-linear-gradient({sweep},#e0e0e0 0 {spreadsheet.LINE_W}px,"
                f"transparent {spreadsheet.LINE_W}px {_DOT_PITCH}px) border-box")
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:#e0e0e0; background:none"


def _select_props(min_width: float) -> str:
    """Shared Quasar props for every chooser dropdown (preset / target / form / control
    select): a compact borderless field whose open popup is at least as wide as its trigger
    (``min_width`` px) but grows to ``max-content``, so each entry shows on one line rather
    than wrapping or truncating at the trigger's width."""
    return ("dense options-dense borderless hide-bottom-space "
            "popup-content-class=rtt-select-popup "
            f"popup-content-style=min-width:{min_width}px;width:max-content")


class _GroupedSelect(ui.select):
    """A chooser whose group-divider rows are non-selectable. Each option whose value
    satisfies ``is_divider`` is handed to Quasar with ``disable=True``, so its q-item
    takes no hover highlight, can't be picked, and a click on it leaves the popup open —
    it reads purely as a section header among the selectable entries."""

    def __init__(self, options, *, is_divider, **kwargs) -> None:
        self._is_divider = is_divider
        super().__init__(options, **kwargs)

    def _update_options(self) -> None:
        # NiceGUI rebuilds the Quasar option dicts here (value/label); flag the divider
        # rows so Quasar renders them disabled. Runs on every rebuild, so it survives a
        # later set_options()/update() too.
        super()._update_options()
        for option, value in zip(self._props["options"], self._values):
            if self._is_divider(value):
                option["disable"] = True


def _set_offlist_prompt(select: ui.select, value) -> None:
    """Show a "-" prompt in a preset chooser's closed box when its current state matches
    no named entry (``value`` is None) — the temperament chooser with no matching preset, or
    the tuning chooser on a control-refined scheme with no name. It is a Quasar display-value
    placeholder, so "-" never appears as a pickable row in the open list; when a named entry
    matches, the override is cleared and Quasar shows its label."""
    if value is None:
        select.props('display-value="-"')
    else:
        select.props(remove="display-value")


class _Reconciler:
    def __init__(self, editor):
        self._editor = editor
        self._cb = None  # callbacks (act, render, on_*) wired by index() after they are defined
        self._row_drag: int | None = None  # the mapping row a drag-to-add started on (dragstart → drop)
        self._col_drag: tuple[str, int] | None = None  # the (interval group, index) a drag-to-add started on
        self.els: dict = {}  # entity id -> outer element (persists across renders)
        self.inputs: dict = {}  # mapping cell id -> q-input
        self.labels: dict = {}  # cell id -> the label whose text tracks state
        self.fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
        self.stacked_faces: dict = {}  # stacked-value cell id -> (main label, sub label): cents whole/.frac, power ∞/(max)
        self.gensign_faces: dict = {}  # generator-tuning cell id -> (sign, whole, .frac) labels: the clickable signed cents face
        self.htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
        self.ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
        self.chart_keys: dict = {}  # chart cell id -> last (w, h, values) drawn, to redraw on resize/data change
        self.range_keys: dict = {}  # range-chart cell id -> last (w, h, ranges) drawn, to redraw on resize/data change
        self.audio_keys: dict = {}  # speaker/arp/chord cell id -> last cents tuple, to rebuild its click handler on change
        self.exprs: dict = {}  # math-expression cell id -> the ui.html holding its stacked lines
        self.expr_state: dict = {}  # math-expression cell id -> last (text, w) rendered, to redraw on change
        self.kinds: dict = {}  # entity id -> the kind its element was built for (rebuild when it changes)
        self.selects: dict = {}  # preset cell id -> its q-select
        self.checks: dict = {}  # control_check cell id -> its q-checkbox (the box-𝐋 "replace diminuator")
        self.ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
        self.rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
        self.opt_buttons: dict = {}  # optimize-button cell id -> its ui.button (for the auto-lock visual)
        self.objective_tips: dict = {}  # optimization-objective cell id -> its ui.tooltip (text swaps with all-interval mode)
        self.captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
        self.caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
        self.math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
        self.math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
        self.fold_state: dict = {}  # fold-toggle cell id -> last state token (unfold_more/less), to swap its SVG on change
        self.cell_units: dict = {}  # value cell id -> the ui.html holding its per-cell unit (the units toggle)
        self.cell_unit_text: dict = {}  # ...and its last unit string, to rewrite on a units toggle / value change
        # The single source of truth for every per-id handle dict, so drop() clears an entity from ALL
        # of them. Forgetting one leaks handles to a deleted element (checks was historically omitted —
        # the box-𝐋 diminuator checkbox); a NEW per-id handle dict MUST be added here.
        self._handle_dicts = (self.els, self.inputs, self.labels, self.fracs, self.stacked_faces, self.gensign_faces, self.htmls, self.ebk_sizes, self.chart_keys, self.range_keys, self.audio_keys, self.exprs, self.expr_state, self.kinds, self.selects, self.checks, self.ptext_inputs, self.rangeopts, self.opt_buttons, self.objective_tips, self.captions, self.caption_html, self.math_cells, self.math_rendered, self.fold_state, self.cell_units, self.cell_unit_text)
        # The edit-preview highlight: while one editable cell is focused, every render rings the
        # OTHER cells whose value the in-progress edit has moved, so the user previews the ripple
        # before leaving the cell. preview_baseline is the layout captured when the cell took focus
        # (None when nothing is being edited); preview_source is that focused cell's id (never rung —
        # the user is already looking at it); preview_shown is the set currently carrying the ring,
        # so clear_preview can strip them without a re-render when focus leaves.
        self.preview_baseline = None
        self.preview_source = None
        self.preview_shown: set = set()
        # The cell-kind dispatch registry (audit #3): kind -> _KindHandlers(build[, update]).
        # Every kind is registered below; make_cell/update_cell index it directly (no fallback),
        # so an unregistered kind raises loudly rather than rendering a silent blank cell.
        self.cell_kinds: dict[str, _KindHandlers] = {}
        for _ebk_kind in _EBK_SVG_KINDS:  # bracket / ebktop / ebkbrace / ebkangle / vbar
            self.cell_kinds[_ebk_kind] = _KindHandlers(self._build_svgfill, self._update_ebk)
        self.cell_kinds["chart"] = _KindHandlers(self._build_svgfill, self._update_chart)
        self.cell_kinds["rangechart"] = _KindHandlers(self._build_svgfill, self._update_rangechart)

        self.cell_kinds["count"] = _KindHandlers(self._build_count, self._update_mathcell)
        self.cell_kinds["symbol"] = _KindHandlers(self._build_symbol, self._update_mathcell)
        self.cell_kinds["matlabel"] = _KindHandlers(self._build_matlabel, self._update_mathcell)
        self.cell_kinds["units"] = _KindHandlers(self._build_units, self._update_mathcell)
        self.cell_kinds["caption"] = _KindHandlers(self._build_caption, self._update_caption)

        self.cell_kinds["ptextpending"] = _KindHandlers(self._build_ptextpending, self._update_ptextpending)
        self.cell_kinds["mathexpr"] = _KindHandlers(self._build_mathexpr, self._update_mathexpr)

        self.cell_kinds["mapping"] = _KindHandlers(self._build_mapping, self._update_mapping)
        self.cell_kinds["commacell"] = _KindHandlers(self._build_commacell, self._update_commacell)
        self.cell_kinds["interestcell"] = _KindHandlers(self._build_interestcell, self._update_input_text)
        self.cell_kinds["heldcell"] = _KindHandlers(self._build_heldcell, self._update_input_text)
        self.cell_kinds["targetcell"] = _KindHandlers(self._build_targetcell, self._update_input_text)
        self.cell_kinds["prescalercell"] = _KindHandlers(self._build_prescalercell, self._update_prescalercell)
        self.cell_kinds["powerinput"] = _KindHandlers(self._build_powerinput, self._update_powerinput)
        self.cell_kinds["powerdisplay"] = _KindHandlers(self._build_powerdisplay, self._update_powerdisplay)
        self.cell_kinds["gentuningcell"] = _KindHandlers(self._build_gentuningcell, self._update_gentuningcell)

        self.cell_kinds["ptextedit"] = _KindHandlers(self._build_ptextedit, self._update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(self._build_genratio, self._update_ratio)
        # the editable quantities-row ratios (comma / target / held / interest): a fraction face
        # overlaid on an input, the scalar twin of the interval-vectors row's editable column cells
        self.cell_kinds["ratiocell"] = _KindHandlers(self._build_ratiocell, self._update_ratiocell)
        self.cell_kinds["commaratio"] = _KindHandlers(self._build_commaratio, self._update_ratio)
        self.cell_kinds["tval"] = _KindHandlers(self._build_tval, self._update_tval)

        self.cell_kinds["prime"] = _KindHandlers(self._build_white_label, self._update_label)
        self.cell_kinds["formcell"] = _KindHandlers(self._build_white_label, self._update_label)
        _val_builder = self._label_builder("rtt-val")
        self.cell_kinds["mapped"] = _KindHandlers(_val_builder, self._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_val_builder, self._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(self._label_builder("rtt-colheader"), self._update_label)
        self.cell_kinds["rowlabel"] = _KindHandlers(self._label_builder("rtt-rowlabel"), self._update_label)
        self.cell_kinds["ptext"] = _KindHandlers(self._label_builder("rtt-ptext"), self._update_ptext)
        self.cell_kinds["boxtitle"] = _KindHandlers(self._label_builder("rtt-boxtitle"), None)  # a static in-tile title

        self.cell_kinds["rangemode"] = _KindHandlers(self._build_rangemode, self._update_rangemode)
        self.cell_kinds["optimize"] = _KindHandlers(self._build_optimize, self._update_optimize)
        self.cell_kinds["rowtoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["coltoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["tiletoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["alltoggle"] = _KindHandlers(self._build_alltoggle, self._update_foldtoggle)

        self.cell_kinds["preset"] = _KindHandlers(self._build_preset, self._update_preset)
        self.cell_kinds["control_select"] = _KindHandlers(self._build_control_select, self._update_control_select)
        self.cell_kinds["control_check"] = _KindHandlers(self._build_control_check, self._update_control_check)
        self.cell_kinds["formchooser"] = _KindHandlers(self._build_formchooser, self._update_formchooser)

        self.cell_kinds["minus"] = _KindHandlers(self._build_minus)
        self.cell_kinds["plus"] = _KindHandlers(self._build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(self._build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(self._build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(self._build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(self._build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(self._build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(self._build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(self._build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(self._build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(self._build_comma_plus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._build_colgrip)
        self.cell_kinds["dropslot"] = _KindHandlers(self._build_dropslot)
        self.cell_kinds["speaker"] = _KindHandlers(self._build_speaker)
        for _audio_ctrl in _AUDIO_CTRLS:  # audio_wave / audio_mode / audio_hold / audio_root
            self.cell_kinds[_audio_ctrl] = _KindHandlers(self._build_audio_ctrl)

    def drop(self, eid):
        """Remove an entity's element and forget every per-id handle for it (see _handle_dicts)."""
        self.els[eid].delete()
        for d in self._handle_dicts:
            d.pop(eid, None)

    def clear_preview(self):
        """Strip every edit-preview ring (the focused cell was left). Removes the class straight from
        the rung cells rather than via a render, so the highlight clears even when leaving the cell
        triggers no re-render (most editable cells have already committed live)."""
        for eid in self.preview_shown:
            if eid in self.els:
                self.els[eid].classes(remove="rtt-preview-change")
        self.preview_shown = set()

    def make_cell(self, cb):
        # build a cell's element in the active parent (the caller opens the freeze container),
        # register it + its kind (and audio key) so render() can place and reconcile it after.
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            # every cell kind is registered (audit #3); indexing rather than .get means an
            # unregistered kind raises loudly here — drift surfaces as a crash, not a silent blank cell
            self.cell_kinds[cb.kind].build(cb, wrap)
        # explanatory hover text for the interactive controls (read-only value cells get none).
        # All wording lives in rtt.web.tooltips; a NEW cell kind must be classified there
        # (in READONLY_KINDS or with a help entry) or test_web_tooltips' completeness sweep fails.
        # The mark/data-eid ride the wrap, so the tooltip hangs off it too — one shared anchor.
        help_text = tooltips.control_help(cb.kind, cb.id)
        if help_text:
            if cb.id in tooltips.OBJECTIVE_IDS:
                # the read-only objective's help names a different quantity per mode (damage
                # ⟪𝐝⟫ₚ vs the all-interval retuning magnitude); keep the Tooltip handle so
                # render() can swap its wording in place when the mode flips, like the symbol glyph
                with wrap:
                    self.objective_tips[cb.id] = ui.tooltip(help_text)
            else:
                wrap.tooltip(help_text)
        self.els[cb.id] = wrap
        self.kinds[cb.id] = cb.kind
        # an editable text cell drives the edit-preview highlight: focusing it snapshots the grid as
        # the baseline, leaving it clears the rings. Every such cell registers its q-input in `inputs`
        # or `ptext_inputs`, so wiring here covers all of them at once (and no others — a dropdown /
        # checkbox commits instantly, with no "while editing" window to preview).
        edit_input = self.inputs.get(cb.id) or self.ptext_inputs.get(cb.id)
        if edit_input is not None:
            edit_input.on("focus", lambda _=None, cid=cb.id: self._cb.on_cell_focus(cid))
            edit_input.on("blur", lambda _=None: self._cb.on_cell_blur())
        if cb.kind in _AUDIO_KINDS:
            self.audio_keys[cb.id] = cb.values

    def update_cell(self, cb):
        # reconcile a present cell: run its registered update (value/glyph in sync) then
        # add/refresh/remove the per-cell unit overlay (the `units` toggle).
        handlers = self.cell_kinds[cb.kind]  # registered for every kind (see make_cell); raises on drift
        if handlers.update is not None:
            handlers.update(cb)
        # a flagged value (a held interval the current tuning no longer holds just) reddens its
        # whole cell — the .rtt-alert CSS paints every face inside the wrap red, clearing back to
        # black when the flag lifts. Toggled generically so any alerting cell kind picks it up.
        self.els[cb.id].classes(add="rtt-alert" if cb.alert else "",
                                remove="" if cb.alert else "rtt-alert")
        # per-cell unit (the `units` toggle): a tiny line at the bottom of the value
        # cell, the value lifted to stay centred. cb.unit is "" unless units is on, so
        # this adds/updates/removes the overlay as the toggle (or the domain) changes.
        if cb.unit:
            if cb.id not in self.cell_units:
                with self.els[cb.id]:
                    self.cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                self.els[cb.id].classes(add="rtt-cell-united")
            if self.cell_unit_text.get(cb.id) != cb.unit:
                self.cell_units[cb.id].set_content(_bold_units(cb.unit))
                self.cell_unit_text[cb.id] = cb.unit
        elif cb.id in self.cell_units:
            self.cell_units[cb.id].delete()
            self.cell_units.pop(cb.id, None)
            self.cell_unit_text.pop(cb.id, None)
            self.els[cb.id].classes(remove="rtt-cell-united")

    def _put_stacked_face(self, cid, cls, main, sub):
        """Build a stacked value face into the active cell — a big main glyph over a smaller
        sub-line (the read-only tval look) — and register the two labels so the update can
        re-sync them. Shared by the cents cells (whole part over .fraction) and the power cells
        (∞ over "(max)")."""
        with ui.element("div").classes(cls):
            m = ui.label(main).classes("rtt-stacked-main")
            s = ui.label(sub).classes("rtt-stacked-sub")
        self.stacked_faces[cid] = (m, s)

    def _sync_stacked_face(self, cid, main, sub):
        """Re-sync a stacked face's two lines in place (the cell kind is unchanged across
        renders, so its labels persist)."""
        m, s = self.stacked_faces[cid]
        m.set_text(main)
        s.set_text(sub)

    def set_cents_face(self, cid, text):
        """Sync a cents cell's stacked face: the whole part over the dot-led fraction (the
        fraction blank when the value is an integer or the cell is blanked). Shared by the
        read-only tval cells and the editable cents cells (whose face overlays their input)."""
        whole, frac = _cents_parts(text)
        self._sync_stacked_face(cid, whole, f".{frac}" if frac else "")

    def cents_face(self, cb, cls):
        """Build the stacked int-over-fraction cents face (the read-only tval look: the whole
        part big over a smaller dot-led fraction). Shared by the read-only tval cell and the
        editable cents cells — the latter pass the overlay class and lay it over their input."""
        whole, frac = _cents_parts(cb.text)
        self._put_stacked_face(cb.id, cls, whole, f".{frac}" if frac else "")

    def _ratio(self, cb, approx, overlay=False):
        """A ratio rendered as a stacked fraction (with a ~ prefix when approximate). With
        ``overlay`` the fraction is an ``rtt-cellface`` laid over an editable input (the
        ratiocell) instead of a read-only cell — it shows when the cell isn't focused."""
        parts = _ratio_parts(cb.text)
        with ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio"):
            if approx:
                ui.label("~").classes("rtt-approx")
            if parts:
                with ui.element("div").classes("rtt-frac"):
                    num = ui.label(parts[0]).classes("rtt-frac-num")
                    den = ui.label(parts[1]).classes("rtt-frac-den")
                self.fracs[cb.id] = (num, den)
            else:
                self.labels[cb.id] = ui.label(cb.text).classes("rtt-val")

    # ---- cell-kind handlers (audit #3): each kind's build + update, co-located here so a
    # built-but-not-filled drift between the two ladders becomes structurally impossible ----
    # The html-content families build an empty ui.html; the update fills it (re-drawing only
    # when the cached key changes). The EBK marks, bar chart and range chart share the build.
    def _build_svgfill(self, cb, wrap):
        self.htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in the update from the cell's px box

    def _update_ebk(self, cb):
        # the mark is drawn 1:1 to its px box, so redraw it whenever the box changes size (e.g.
        # the brace/top bracket as the domain grows) or its pending (red) state flips (a draft
        # comma's marks committing to black)
        if self.ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
            self.htmls[cb.id].set_content(_ebk_svg(cb))
            self.ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)

    def _update_chart(self, cb):
        # redraw when the box resizes OR the underlying data / indicator changes
        key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
        if self.chart_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(
                _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label))
            self.chart_keys[cb.id] = key

    def _update_rangechart(self, cb):
        # redraw when the box resizes OR the ranges/live tuning change (mapping/mode edit)
        key = (cb.w, cb.h, cb.ranges, cb.values)
        if self.range_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values))
            self.range_keys[cb.id] = key

    def _build_count(self, cb, wrap):
        self.math_cells[cb.id] = ui.html("").classes("rtt-count")  # a scalar "symbol = value"; filled in update

    def _build_symbol(self, cb, wrap):
        wrap.classes("rtt-symbol-cell")
        # the optimization box's symbols (⟪𝐝⟫ₚ, 𝑝) stay on one line (ₚ never wraps off)
        cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
        self.math_cells[cb.id] = ui.html("").classes(cls)

    def _build_matlabel(self, cb, wrap):
        # routed through _math_html so its bold-italic / bold-upright glyphs draw in the same
        # styled face as the tile symbol it indexes; the complexity row's longer labels (‖L𝐜ᵢ‖q)
        # take a smaller variant to avoid colliding
        cls = "rtt-matlabel rtt-matlabel-norm" if "‖" in cb.text else "rtt-matlabel"
        wrap.classes("rtt-matlabel-cell")
        self.math_cells[cb.id] = ui.html("").classes(cls)

    def _build_units(self, cb, wrap):
        wrap.classes("rtt-units-cell")
        self.math_cells[cb.id] = ui.html("").classes("rtt-units")

    def _update_mathcell(self, cb):  # shared by symbol / count / units / matlabel
        # symbols/equivalence tails/counts and matrix row/col labels go through _math_html (styled
        # math glyphs); units use _units_html (a single-story-g sans value, serif label)
        html = _units_html(cb.text) if cb.kind == "units" else _math_html(cb.text)
        if self.math_rendered.get(cb.id) != html:  # rewrite on a toggle / value change
            self.math_cells[cb.id].set_content(html)
            self.math_rendered[cb.id] = html
            if cb.id == "optimization:objective:symbol":
                # all-interval relabels this to the wide retuning magnitude ‖𝒓𝐿⁻¹‖dual(q); shrink
                # it (rtt-opt-wide) so it stays centred over its COL_W value
                wide = "‖" in cb.text
                self.math_cells[cb.id].classes(
                    replace="rtt-symbol rtt-opt-1line rtt-opt-wide" if wide
                    else "rtt-symbol rtt-opt-1line")

    def _build_caption(self, cb, wrap):
        wrap.classes("rtt-caption-cell")
        # the optimization box's captions stay on one line (no wrap), unlike tile names; a caption
        # with align="left" reads left-justified under its control (e.g. a preset chooser's label).
        # The lone exception is the objective's own label, whose wide all-interval "retuning
        # magnitude" must wrap to two lines (its slot is too narrow to spread it on one) — it wraps
        # at the space like a tile name, while the short "power mean" still fits on a single line.
        one_line = cb.id.startswith("optimization:") and cb.id != "optimization:objective:caption"
        cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
        if cb.align == "left":
            cls += " rtt-caption-left"
        self.captions[cb.id] = ui.html("").classes(cls)

    def _update_caption(self, cb):
        html = _underline_html(cb.text, cb.underlines)
        if self.caption_html.get(cb.id) != html:  # rewrite when a mnemonic toggle adds/removes underlines
            self.captions[cb.id].set_content(html)
            self.caption_html[cb.id] = html
        # a locked control's caption greys with it (the disabled flag), so the label reads in the
        # same disabled grey as the control rather than the caption's darker default
        self.captions[cb.id].classes(add="rtt-caption-disabled" if cb.disabled else "",
                                     remove="" if cb.disabled else "rtt-caption-disabled")

    def _build_ptextpending(self, cb, wrap):
        # an editable vector-list dual mid-draft (comma basis / target list): a static two-tone
        # box (the draft is typed into the red grid cells, not here); content set in the update
        self.htmls[cb.id] = ui.html("").classes("rtt-ptextpending")

    def _update_ptextpending(self, cb):
        # the committed vectors black and the draft vector red (same red as its grid cells)
        ed = self._editor
        if cb.id == "ptext:vectors:targets":
            targets = ed.target_override or service.target_interval_set(ed.target_spec, ed.state.domain_basis)
            committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
            pending = ed.pending_target
        else:  # the comma basis
            committed, pending = ed.state.comma_basis, ed.pending_comma
        prefix, draft, suffix = service.vector_list_pending_text(committed, pending)
        self.htmls[cb.id].set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
        self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")

    def _build_mathexpr(self, cb, wrap):
        self.exprs[cb.id] = ui.html("").classes("rtt-mathexpr")  # a just value's stacked closed form; drawn in update

    def _update_mathexpr(self, cb):
        # redraw (with refit fonts) whenever the expression text or cell width changes
        if self.expr_state.get(cb.id) != (cb.text, cb.w):
            self.exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
            self.expr_state[cb.id] = (cb.text, cb.w)

    # ---- editable grid-input cells: an input registered in the inputs dict, its value mirrored
    # in the update. interestcell / heldcell / targetcell share the plain-value fill; prescalercell
    # / gentuningcell / powerinput also overlay a stacked face (cents whole/.frac, power ∞/(max)). ----
    def _build_mapping(self, cb, wrap):
        wrap.classes("rtt-cell-input")  # a per-cell unit overlays inside the input box
        self.inputs[cb.id] = ui.input(on_change=lambda e: self._cb.on_mapping_change()) \
            .props("dense borderless").classes("rtt-cellinput")

    def _update_mapping(self, cb):
        self.inputs[cb.id].value = "" if cb.blank else str(self._editor.state.mapping[cb.gen][cb.prime])

    def _build_commacell(self, cb, wrap):
        wrap.classes("rtt-cell-input")
        self.inputs[cb.id] = ui.input(on_change=lambda e: self._cb.on_comma_change()) \
            .props("dense borderless").classes("rtt-cellinput")

    def _update_commacell(self, cb):
        if cb.pending:  # the draft column: show the typed component (blank if None), red-outlined
            v = self._editor.pending_comma[cb.prime] if self._editor.pending_comma is not None else None
            self.inputs[cb.id].value = "" if v is None else str(v)
        else:
            self.inputs[cb.id].value = "" if cb.blank else str(self._editor.state.comma_basis[cb.comma][cb.prime])
        self.inputs[cb.id].classes(add="rtt-pending" if cb.pending else "",
                              remove="" if cb.pending else "rtt-pending")

    def _build_interestcell(self, cb, wrap):
        wrap.classes("rtt-cell-input")
        self.inputs[cb.id] = ui.input(on_change=lambda e: self._cb.on_interest_change()) \
            .props("dense borderless").classes("rtt-cellinput")

    def _build_heldcell(self, cb, wrap):
        wrap.classes("rtt-cell-input")
        self.inputs[cb.id] = ui.input(on_change=lambda e: self._cb.on_held_change()) \
            .props("dense borderless").classes("rtt-cellinput")

    def _build_targetcell(self, cb, wrap):
        wrap.classes("rtt-cell-input")
        self.inputs[cb.id] = ui.input(on_change=lambda e: self._cb.on_target_cells_change()) \
            .props("dense borderless").classes("rtt-cellinput")

    def _update_input_text(self, cb):  # interestcell / heldcell / targetcell: mirror cb.text
        self.inputs[cb.id].value = cb.text  # a pending draft cell carries "" / the typed component
        self.inputs[cb.id].classes(add="rtt-pending" if cb.pending else "",
                              remove="" if cb.pending else "rtt-pending")

    def _build_prescalercell(self, cb, wrap):
        # a bare prescaler 𝐿 diagonal cell, the user's editable override (off-diagonal cells stay
        # tval "0" — 𝐿 is diagonal). Each input dispatches to set_custom_prescaler_entry; the cid
        # carries the diagonal slot, so the lambda closes over it (a free cb would be the LAST
        # cell's id by the time the user types)
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_prescaler_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self.cents_face(cb, "rtt-tval rtt-cellface")  # the stacked face overlaid on the input

    def _update_prescalercell(self, cb):
        # reflect the live prescaler diagonal (the override if set, else the scheme-derived value —
        # spreadsheet.build emits the final text). Blank when quantities are off, like the other cells
        self.inputs[cb.id].value = cb.text
        self.set_cents_face(cb.id, cb.text)  # the overlaid stacked face mirrors the input

    def _build_powerinput(self, cb, wrap):
        # the optimization power 𝑝, the box-𝒄 norm power 𝑞, or its dual. The symbol label rides as
        # a separate cell below; the value carries a stacked gridded face overlaid on the editable
        # input (like a cents cell): ∞ shows a small "(max)" beneath it, a numeric power shows bare.
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_power_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self._put_stacked_face(cb.id, "rtt-tval rtt-cellface", *_power_parts(cb.text))

    def _update_powerinput(self, cb):
        # mirror the raw value into the input (shown when focused) and re-sync the overlay face
        # (shown otherwise): ∞ stacks a small "(max)" below it, a numeric power shows bare. (All-
        # interval locks 𝑝 to ∞ as a read-only powerdisplay — a different kind — so this only ever
        # runs for the live editable power and the box-𝒄 norm-power 𝑞 / dual(𝑞) fields.)
        self.inputs[cb.id].value = cb.text
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_powerdisplay(self, cb, wrap):
        # the all-interval-locked optimization power as a READ-ONLY value: the SAME stacked
        # ∞-over-"(max)" face as the editable powerinput (_power_parts, same fonts, full-cell centred
        # via rtt-cellface), but with no input — so it looks identical to the live power minus the
        # white input box. (rtt-cell-stacked is omitted: with no input there's no face to hide on
        # focus, and it keeps the per-cell-unit padding rule off a value that carries no unit.)
        self._put_stacked_face(cb.id, "rtt-tval rtt-cellface", *_power_parts(cb.text))

    def _update_powerdisplay(self, cb):
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_gentuningcell(self, cb, wrap):
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_gentuning_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self._gentuning_face(cb)  # the clickable signed cents face overlaid on the input
        # hover-and-scroll fine-adjust: each wheel notch nudges this generator by 1/1000 cent (the
        # last digit the cents face shows). The listener rides the wrap, not the input, so a scroll
        # over the overlaid signed face (a sibling of the input) still reaches it by bubbling;
        # .prevent stops the grid scrolling out from under the cursor.
        wrap.on("wheel.prevent",
                lambda e, cid=cb.id: self._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
                args=["deltaY"])

    def _update_gentuningcell(self, cb):
        text = "" if cb.blank else cb.text  # blank when quantities off
        self.inputs[cb.id].value = text
        self._set_gentuning_face(cb.id, text)  # the overlaid signed face mirrors the input

    def _gentuning_face(self, cb):
        """The generator-tuning cell's signed, clickable cents face overlaid on its input: a sign
        glyph (the otherwise-assumed "+" of a positive generator, made visible — or "−") the user
        clicks to reverse the generator (negating its mapping row in lockstep, so the tuning map
        holds), then the whole part big over a small dot-led fraction (the shared cents look). Only
        the sign takes pointer events; a click elsewhere falls through to focus the input for typing."""
        sign, whole, frac = _gentuning_parts(cb.text)
        i = int(cb.id.rsplit(":", 1)[1])
        with ui.element("div").classes("rtt-tval rtt-cellface"):
            with ui.element("div").classes("rtt-gentuning-main"):
                s = ui.label(sign).classes("rtt-gensign") \
                    .on("click", lambda _=None, i=i: self._cb.act(lambda: self._editor.flip_generator(i)))
                m = ui.label(whole).classes("rtt-stacked-main")
            sub = ui.label(f".{frac}" if frac else "").classes("rtt-stacked-sub")
        self.gensign_faces[cb.id] = (s, m, sub)

    def _set_gentuning_face(self, cid, text):
        """Re-sync a generator-tuning cell's signed face in place (the cell kind is unchanged
        across renders, so its sign/whole/fraction labels persist)."""
        sign, whole, frac = _gentuning_parts(text)
        s, m, sub = self.gensign_faces[cid]
        s.set_text(sign)
        m.set_text(whole)
        sub.set_text(f".{frac}" if frac else "")

    def _build_ptextedit(self, cb, wrap):
        # an editable dual: typing a valid EBK string drives the grid (its own ptext_inputs dict)
        self.ptext_inputs[cb.id] = ui.input(value=cb.text,
                on_change=lambda e, cid=cb.id: self._cb.on_ptext_edit(cid, e.value)) \
            .props("dense borderless").classes("rtt-ptextedit")

    def _update_ptextedit(self, cb):  # reflect the canonical string + its shrink-to-fit font
        self.ptext_inputs[cb.id].value = cb.text
        self.ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    # ---- ratio faces (a stacked fraction via _ratio) + the read-only cents (tval) face ----
    def _build_genratio(self, cb, wrap):
        self._ratio(cb, approx=True)  # a generator ratio, shown ~approximate

    def _build_commaratio(self, cb, wrap):
        self._build_ratio_or_pending(cb)

    def _build_ratio_or_pending(self, cb):
        # a read-only comma ratio heading its column — the generator-detempering D ratio, or a
        # pending comma draft's red "?" placeholder (no value until the vector is filled in). The
        # editable comma/target/held/interest ratios are ratiocells (see _build_ratiocell).
        if cb.pending:
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-val rtt-pending-q")
        else:
            self._ratio(cb, approx=False)

    def _build_ratiocell(self, cb, wrap):
        # an editable comma / target / held / interest ratio: an input (the white box + black
        # outline) carrying the same stacked fraction face as the read-only ratios, overlaid so
        # the cell reads as a fraction until clicked, then swaps to the raw "num/den" for editing.
        # It commits the WHOLE typed fraction on blur / Enter, not per keystroke — parsing "2" of a
        # "25/24" mid-edit would momentarily retune to 2/1 and fight the typing. A pending draft's
        # red "?/?" face stays put until a valid fraction fills it (or its vector cells do).
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        commit = lambda _=None, cid=cb.id: self._cb.on_ratio_change(cid)
        inp = ui.input().props("dense borderless").classes("rtt-cellinput")
        inp.on("blur", commit)
        inp.on("keydown.enter", commit)
        self.inputs[cb.id] = inp
        self._ratio(cb, approx=False, overlay=True)

    def _update_ratiocell(self, cb):
        self.inputs[cb.id].value = cb.text  # committed: the ratio; a draft pre-fills "?/?" so you edit it
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")  # red draft styling
        self._update_ratio(cb)              # the overlaid stacked face mirrors the fraction

    def _update_ratio(self, cb):  # genratio / commaratio / ratiocell: refresh the stacked fraction face
        # only the fraction form is refreshed; a plain-label ratio (no num/den) is static, as built
        if cb.id in self.fracs:
            num, den = _ratio_parts(cb.text) or (cb.text, "")
            self.fracs[cb.id][0].set_text(num)
            self.fracs[cb.id][1].set_text(den)

    def _build_tval(self, cb, wrap):
        self.cents_face(cb, "rtt-tval")  # the read-only stacked int-over-fraction cents face

    def _update_tval(self, cb):
        self.set_cents_face(cb.id, cb.text)

    # ---- plain label cells: a ui.label whose text the update keeps in sync (set_text). prime /
    # formcell sit in a white-bordered box; ptext also tracks a shrink-to-fit font; boxtitle is static ----
    def _label_builder(self, cls):  # a build that drops a classed ui.label into the cell, registered in labels
        def build(cb, wrap):
            self.labels[cb.id] = ui.label(cb.text).classes(cls)
        return build

    def _build_white_label(self, cb, wrap):  # prime / formcell: a read-only bordered cell
        with ui.element("div").classes("rtt-white"):
            self.labels[cb.id] = ui.label(cb.text)

    def _update_label(self, cb):  # prime / formcell / colheader / rowlabel / mapped / vec
        self.labels[cb.id].set_text(cb.text)

    def _update_ptext(self, cb):  # a read-only value: keep its text and shrink-to-fit font in sync
        self.labels[cb.id].set_text(cb.text)
        self.labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    # ---- interactive controls with an update: range-mode selector, optimize button, fold toggles ----
    def _build_rangemode(self, cb, wrap):
        wrap.classes("rtt-rangemode")  # two square indicators side by side (the mockup style)
        opts = {}
        for mode in ("monotone", "tradeoff"):
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                ui.label(mode).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, m=mode: self._cb.on_range_mode(m))
            opts[mode] = opt
        self.rangeopts[cb.id] = opts

    def _update_rangemode(self, cb):  # fill the live mode's square (the other's is hollow)
        for mode, opt in self.rangeopts[cb.id].items():
            (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
             else opt.classes(remove="rtt-rangeopt-on"))

    def _build_optimize(self, cb, wrap):
        # single click optimizes once (freeze at the optimum); double click toggles the auto-
        # optimize lock. A double-click also fires its two single clicks, but optimize() is
        # idempotent, so a double-click's net effect is the lock toggle.
        self.opt_buttons[cb.id] = ui.button(cb.text, on_click=lambda: self._cb.act(self._editor.optimize), color=None) \
            .props("unelevated dense no-caps").classes("rtt-optimize")
        self.opt_buttons[cb.id].on("dblclick", lambda: self._cb.act(self._editor.toggle_optimize_lock))

    def _update_optimize(self, cb):  # mark the button when its auto-optimize lock is on
        (self.opt_buttons[cb.id].classes(add="rtt-optimize-locked") if self._editor.optimize_locked
         else self.opt_buttons[cb.id].classes(remove="rtt-optimize-locked"))

    def _build_foldtoggle(self, cb, wrap):  # rowtoggle / coltoggle / tiletoggle: a clickable chevron over its band
        item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets" / "tile:mapping:primes"
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text  # the glyph swaps on collapse/expand (see _update_foldtoggle)
        wrap.on("click", lambda _=None, it=item: self._cb.on_toggle(it))

    def _build_alltoggle(self, cb, wrap):  # the master expand/collapse-all control in the node corner
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None: self._cb.on_toggle_all())

    def _update_foldtoggle(self, cb):  # swap the chevron SVG when the band folds / unfolds
        if self.fold_state.get(cb.id) != cb.text:
            self.htmls[cb.id].set_content(_control_svg(_FOLD_GLYPH[cb.text]))
            self.fold_state[cb.id] = cb.text

    # ---- chooser dropdowns + the diminuator checkbox ----
    def _target_preset_values(self):
        """The numeric limit + TILT/OLD family the target chooser shows, or ``(None, None)``
        when no named family applies — a typed/edited target list overriding it, or all-interval
        mode (every interval, so no target set scheme). Then both parts fall back to "-" (the
        select via display-value, the number via its "-" placeholder); all-interval also greys+locks
        the chooser (the cell's ``disabled`` flag, applied in :meth:`_update_preset`). A ``None``
        family is also what makes re-picking TILT/OLD a real value change the handler acts on, so the
        chooser doubles as the reset back to a named list — not a same-value no-op Quasar would swallow."""
        if self._editor.target_override is not None or service.is_all_interval(self._editor.tuning_scheme):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:  # no manual limit: show the family's domain default
            limit = service.default_target_limit(
                family, service.standard_primes(self._editor.state.d))
        return limit, family

    def _build_preset(self, cb, wrap):
        name = cb.id.split(":")[1]  # temperament / tuning / target (a copy adds a :col suffix)
        if name == "target":
            # a numeric limit override beside the TILT/OLD family select. Both fall back to "-"
            # when a typed/edited target list overrides the family (see _target_preset_values):
            # the select via display-value, the number via its "-" placeholder.
            limit, family = self._target_preset_values()
            with ui.element("div").classes("rtt-preset-target"):
                num = ui.number(value=limit, min=2,
                        on_change=lambda e: self._cb.on_target_change()) \
                    .props('dense borderless hide-bottom-space placeholder="-"').classes("rtt-preset-num")
                sel = ui.select(list(presets.TARGET_SETS), value=family,
                        on_change=lambda e: self._cb.on_target_change()) \
                    .props(_select_props(cb.w - 30)).classes("rtt-preset")  # field = cell − the 30px square (touching, no gap)
            _set_offlist_prompt(sel, family)
            self.selects[cb.id] = (num, sel)
        elif name == "temperament":
            # a normal dropdown listing only the rank/limit section dividers and their presets
            # (grouped in the open list). The chosen preset shows in the box; when none matches, a "-" prompt
            # shows there as a display-value placeholder — never a pickable row in the list.
            value = presets.identify(self._editor.state)
            sel = _GroupedSelect(presets.temperament_options(), value=value,
                    is_divider=presets.is_divider,
                    on_change=lambda e: self._cb.on_preset("temperament", e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            self.selects[cb.id] = sel
        elif name == "prescaler":
            # the predefined-prescalers chooser: log-prime always, the rest (identity / prime) gated
            # behind alt-complexities. "-" when a manual diagonal edit deviates from the named
            # prescaler (editor.displayed_prescaler_name returns None then).
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            sel = ui.select(options, value=value,
                    on_change=lambda e: self._cb.on_preset("prescaler", e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            self.selects[cb.id] = sel
        else:  # tuning — systematic scheme names, T-prefixed when targeting a list (not all-interval);
            # a control-refined scheme has no name, shown as the "-" placeholder. Alternative-
            # complexity schemes are gated behind the alt. complexity setting.
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme), self._editor.settings["alt_complexity"])
            # "-" when the displayed tuning is off the named list — a refined spec, or a manual
            # override deviating from the scheme's optimum; else the offered name
            name = self._editor.displayed_tuning_scheme_name
            scheme = name if name in options else None
            sel = ui.select(options, value=scheme,
                    on_change=lambda e: self._cb.on_preset("tuning", e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, scheme)
            self.selects[cb.id] = sel

    def _update_preset(self, cb):
        # mirror the live selection: the temperament chooser shows the matched preset (or its
        # placeholder), the target chooser splits into limit + family, the tuning chooser shows its
        # scheme. building[0] guards echoes.
        if cb.id.startswith("preset:temperament"):  # base + the comma-basis copy
            value = presets.identify(self._editor.state)
            self.selects[cb.id].value = value
            _set_offlist_prompt(self.selects[cb.id], value)
        elif cb.id == "preset:target":
            num, sel = self.selects[cb.id]
            limit, family = self._target_preset_values()  # (None, None) -> both show "-"
            num.value = limit
            sel.value = family
            _set_offlist_prompt(sel, family)
            num.set_enabled(not cb.disabled)  # all-interval greys+locks the chooser (it also shows "-")
            sel.set_enabled(not cb.disabled)
        elif cb.id == "preset:prescaler":  # the scheme's prescaler, "-" on a deviating edit; the
            # option list widens/narrows as alt-complexities flips, so refresh it too
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value)
        else:  # tuning — a refined spec or a deviating manual override shows "-"
            name = self._editor.displayed_tuning_scheme_name
            # the option LABELS T-prefix only while target-based, so recompute them as the all-
            # interval checkbox flips (set once at creation, they would otherwise go stale)
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme), self._editor.settings["alt_complexity"])
            # a name off the offered list (e.g. a finite-power miniRMS scheme — nameable, but not in
            # the lp-only list) falls back to the "-" placeholder, matching the build path
            scheme = name if name in options else None
            self.selects[cb.id].set_options(options, value=scheme)
            _set_offlist_prompt(self.selects[cb.id], scheme)

    def _build_control_select(self, cb, wrap):  # a weighting chooser (complexity / norm / weight slope)
        self.selects[cb.id] = ui.select(list(cb.values), value=cb.text or None,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")

    def _update_control_select(self, cb):  # mirror the live choice; grey it when locked (box 𝒘 all-interval)
        self.selects[cb.id].value = cb.text or None
        self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_control_check(self, cb, wrap):  # the box-𝐋 "replace diminuator" checkbox (size factor)
        self.checks[cb.id] = ui.checkbox(cb.text, value=cb.checked,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props("dense").classes("rtt-control-check")

    def _update_control_check(self, cb):  # mirror the live "replace diminuator" state
        self.checks[cb.id].value = cb.checked

    def _build_formchooser(self, cb, wrap):  # the <choose form> control: canonicalizes its matrix on select
        name = cb.id.split(":", 1)[1]  # mapping / comma_basis
        self.selects[cb.id] = ui.select({"": "choose form", "canonical": "canonical"}, value="",
                on_change=lambda e, n=name: self._cb.on_form_choose(n, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")

    def _update_formchooser(self, cb):  # a one-shot action: snap back to the placeholder
        self.selects[cb.id].value = ""

    # ---- static controls (build only, no update): the domain/comma/interest/held ± buttons,
    # the speaker, and the audio bank glyphs. Their click / JS handlers are baked at build time. ----
    def _build_minus(self, cb, wrap):  # remove the highest prime; a hover − centred on the last prime's branch point
        wrap.classes("rtt-minus-zone")  # clear of the editable cell below
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))

    def _build_plus(self, cb, wrap):  # add a prime; the always-shown + on the bus stub
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.expand))

    def _build_gen_minus(self, cb, wrap):  # drop the last generator (+n, −r); the mapping-row − reached from the column
        wrap.classes("rtt-minus-zone")  # clear of the genmap cell below
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))

    def _build_gen_plus(self, cb, wrap):  # add a generator by un-tempering a comma (−n, +r); the + on the bus stub
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_mapping_row))

    def _build_map_minus(self, cb, wrap):  # remove generator cb.gen (a mapping row); a hover − on the left bus
        wrap.classes("rtt-minus-zone")  # clear of the generator-ratio spine it drops over
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))

    def _build_map_plus(self, cb, wrap):  # add a generator (un-temper a comma); the + on the left-bus stub
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_mapping_row))

    def _build_map_drag(self, cb, wrap):  # drag generator row cb.gen onto another to ADD it into that row
        # HTML5 drag-and-drop: the source row is held server-side from dragstart through drop (the
        # index can't ride in the drop event's dataTransfer through NiceGUI's arg paths). dragover
        # must cancel its default (client-side, so it doesn't round-trip per move) to mark this a
        # valid drop target; the drop adds the dragged row into this one and re-renders.
        wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, idx=cb.gen: self._begin_row_drag(idx))
        wrap.on("dragend", lambda _=None: self._end_row_drag())
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")
        wrap.on("drop.prevent", lambda _=None, idx=cb.gen: self._drop_on_row(idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _begin_row_drag(self, idx):
        self._row_drag = idx

    def _end_row_drag(self):
        self._row_drag = None

    def _drop_on_row(self, idx):  # add the dragged generator row into the one it was dropped on
        src = self._row_drag
        if src is not None and src != idx:
            self._cb.act(lambda: self._editor.add_mapping_row_to(src, idx))

    # the interval-column drag handles (comma / target / held / interest): the column twin of the
    # mapping-row handle. Drag one interval onto another in the SAME column to ADD it in (their
    # product) — the source's (group, index) is held server-side from dragstart through drop, so
    # the drop only combines within its own column. See spreadsheet's int_drag.
    _INTERVAL_COMBINE = {
        "comma": "add_comma_to", "target": "add_target_to",
        "held": "add_held_to", "interest": "add_interest_to",
    }

    def _build_int_drag(self, cb, wrap):
        group = cb.id.split(":")[1]  # int_drag:<group>:<index>
        wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, g=group, idx=cb.comma: self._begin_col_drag(g, idx))
        wrap.on("dragend", lambda _=None: self._end_col_drag())
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")
        wrap.on("drop.prevent", lambda _=None, g=group, idx=cb.comma: self._drop_on_interval(g, idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _begin_col_drag(self, group, idx):
        self._col_drag = (group, idx)

    def _end_col_drag(self):
        self._col_drag = None

    def _drop_on_interval(self, group, idx):  # add the dragged interval into the one it was dropped on
        if self._col_drag is None:
            return
        src_group, src = self._col_drag
        if src_group != group or src == idx:  # only combine within the same interval column
            return
        combine = getattr(self._editor, self._INTERVAL_COMBINE[group])
        self._cb.act(lambda: combine(src, idx))

    def _build_basis_minus(self, cb, wrap):  # the domain − on the interval-vectors row's left bus
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))

    def _build_comma_minus(self, cb, wrap):  # drop the last comma, or cancel the pending draft
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(self._editor.remove_comma))

    def _build_comma_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_comma))

    def _build_list_minus(self, cb, wrap, cancel, remove):
        # an interval-list column's − (interest / held / target): the draft column's cancels the
        # draft, every other drops just its interval (cb.comma) — each is independently removable
        action = cancel if cb.id.endswith(":pending") else (lambda idx=cb.comma: remove(idx))
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(action))

    def _build_interest_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_interest, self._editor.remove_interest)

    def _build_interest_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_interest))

    def _build_held_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_held, self._editor.remove_held)

    def _build_held_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_held))

    def _build_target_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_target, self._editor.remove_target)

    def _build_target_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.add_target))

    def _build_colgrip(self, cb, wrap):  # a per-column drag handle on the fan (the drag source)
        _, lst, idx = cb.id.split(":")  # "grip:{list}:{idx}"
        wrap.classes("rtt-colgrip").props("draggable=true")
        wrap.on("dragstart", lambda _=None, l=lst, i=int(idx): self._cb.on_drag_start(l, i))
        wrap.on("dragend", lambda _=None: self._cb.on_drag_end())
        ui.html(_grip_svg()).classes("rtt-glyph")

    def _build_dropslot(self, cb, wrap):  # a per-gap drop target on the fan (insert-before this gap)
        # the drop fires the move; dragover.preventDefault + the dragging-state class + the hover
        # highlight are handled client-side by _DRAG_JS (no per-frame server round-trips)
        _, lst, gap = cb.id.split(":")  # "drop:{list}:{gap}"
        wrap.classes("rtt-dropslot")
        wrap.on("drop", lambda _=None, l=lst, g=int(gap): self._cb.on_drop(l, g))

    def _build_speaker(self, cb, wrap):  # play this pitch per its tile's mode (client-side engine)
        tile = cb.text  # the tile key "<row>:<group>", shared with the tile's control bank
        idx = int(cb.id.rsplit(":", 1)[1])
        pitches = ",".join(f"{float(v):.6f}" for v in cb.values)  # the whole tile (for arp/chord)
        # color=None drops Quasar's default primary (blue): the app is greyscale, leaving colour to
        # the yellow/cyan/magenta colorization. .rtt-spk + the data attrs let the engine highlight
        # this speaker while it sounds.
        ui.button(icon="volume_up", color=None) \
            .props(f'flat dense round data-audio="{tile}" data-idx="{idx}"') \
            .classes("rtt-audio-btn rtt-spk") \
            .on("click", js_handler=f"() => window.rttAudio.hit('{tile}', {idx}, [{pitches}])")

    def _build_audio_ctrl(self, cb, wrap):  # a bank control: cycles its state + glyph client-side
        tile = cb.id.split(":", 1)[1]      # "<row>:<group>"
        ctrl = cb.kind.split("_", 1)[1]     # wave | mode | hold | root
        glyph = {"wave": _AUDIO_GLYPHS["wave"][0], "mode": _AUDIO_GLYPHS["mode"][0],
                 "hold": _AUDIO_GLYPHS["lock"][0], "root": _AUDIO_GLYPHS["root"]}[ctrl]
        fn = {"wave": "cycleWave", "mode": "cycleMode",
              "hold": "toggleHold", "root": "toggleRoot"}[ctrl]
        ui.html(glyph).classes("rtt-audio-ctrl") \
            .props(f'data-audio="{tile}" data-actrl="{ctrl}"') \
            .on("click", js_handler=f"() => window.rttAudio.{fn}('{tile}')")


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    # Give every tooltip a show delay so the dense grid's hover help waits for a deliberate rest
    # rather than popping the instant the cursor crosses a control. Setting it on the Tooltip
    # element's default props covers the whole population at once — chrome, Show toggles, grid
    # controls and any future tooltip — with no per-call wiring to keep in sync. Idempotent: it
    # re-sets the same class default each page build.
    ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS}")
    # the audio rows' Web Audio engine + its glyph variants (shared markup for click redraws)
    ui.add_body_html(f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>")
    # keep the frozen title bands pinned to the scrolling grid pane (see _FREEZE_JS)
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
    # the interval-column drag-and-drop glue (see _DRAG_JS)
    ui.add_body_html(f"<script>{_DRAG_JS}</script>")
    ui.query("body").style("background:#fff")
    # trim NiceGUI's default 16px content padding to a slim margin around the whole app
    ui.query(".nicegui-content").style("padding:6px")

    # The Editor owns the whole document — temperament, view selections, the Show
    # settings (editor.settings) and the folded rows/columns/tiles (editor.collapsed) —
    # and the undo/redo history over all of it. We persist that document per browser
    # (app.storage.user) so a refresh restores exactly where the user left off; a
    # corrupt/old blob is ignored, falling back to the as-shipped defaults.
    editor = Editor()
    stored = _doc_store().get(_STORE_KEY)
    if stored:
        try:
            editor.load(stored)
        except Exception:
            pass
    rec = _Reconciler(editor)
    building = [False]
    last_lay = [None]  # the most recently built layout, so the master toggle can read its foldable bands
    refs: dict = {}

    def on_mapping_change():
        if building[0] or not editor.settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(rec.inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            return
        editor.edit_mapping(matrix)
        render()

    def on_comma_change():
        # the comma basis (the mapping's dual) is edited in the interval-vectors row,
        # which is present independent of the temperament boxes
        if building[0]:
            return
        d, nc = editor.state.d, len(editor.state.comma_basis)
        if editor.pending_comma is not None:
            # the draft column rides at index nc; hand its cells to the editor, which
            # commits (and re-ranks) once they form a valid independent comma
            if any(f"cell:comma:{p}:{nc}" not in rec.inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_comma([_parse_int(rec.inputs[f"cell:comma:{p}:{nc}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:comma:{p}:{c}" not in rec.inputs for c in range(nc) for p in range(d)):
            return  # the comma cells aren't currently shown (folded away)
        # the comma cells are the basis transposed (prime down the rows, comma across)
        basis = [[_parse_int(rec.inputs[f"cell:comma:{p}:{c}"].value) for p in range(d)] for c in range(nc)]
        if any(v is None for comma in basis for v in comma):
            return
        editor.edit_comma_basis(basis)
        render()

    def on_interest_change():
        # the intervals of interest are edited as vectors in the interval-vectors row,
        # like the comma basis; read the d-tall columns and replace the set
        if building[0]:
            return
        d, mi = editor.state.d, len(editor.interest_vectors)
        if editor.pending_interest is not None:
            # the draft column rides at index mi; hand its cells to the editor, which commits
            # (appends the interval) once every component is filled in
            if any(f"cell:interest:{p}:{mi}" not in rec.inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_interest([_parse_int(rec.inputs[f"cell:interest:{p}:{mi}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:interest:{p}:{i}" not in rec.inputs for i in range(mi) for p in range(d)):
            return  # the interest cells aren't currently shown (folded away)
        vectors = [[_parse_int(rec.inputs[f"cell:interest:{p}:{i}"].value) for p in range(d)] for i in range(mi)]
        if any(v is None for m in vectors for v in m):
            return
        editor.set_interest_vectors(vectors)
        render()

    def on_held_change():
        # the held intervals are edited as vectors in the interval-vectors row, like the
        # intervals of interest; read the d-tall columns and replace the held set
        if building[0]:
            return
        d, nh = editor.state.d, len(editor.held_vectors)
        if editor.pending_held is not None:
            # the draft column rides at index nh; commit it once every component is filled in
            if any(f"cell:held:{p}:{nh}" not in rec.inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_held([_parse_int(rec.inputs[f"cell:held:{p}:{nh}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:held:{p}:{i}" not in rec.inputs for i in range(nh) for p in range(d)):
            return  # the held cells aren't currently shown (folded away / optimization off)
        vectors = [[_parse_int(rec.inputs[f"cell:held:{p}:{i}"].value) for p in range(d)] for i in range(nh)]
        if any(v is None for m in vectors for v in m):
            return
        editor.set_held_vectors(vectors)
        render()

    def on_target_cells_change():
        # the target interval list is edited as vector columns, like the comma basis; read the
        # d-tall columns (id is cell:vec:targets:{column}:{prime}) and replace the target set
        if building[0]:
            return
        d = editor.state.d
        targets = editor.target_override or service.target_interval_set(
            editor.target_spec, editor.state.domain_basis)
        k = len(targets)
        if editor.pending_target is not None:
            # the draft column rides at index k; commit it once every component is filled in
            if any(f"cell:vec:targets:{k}:{p}" not in rec.inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_target([_parse_int(rec.inputs[f"cell:vec:targets:{k}:{p}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:vec:targets:{j}:{p}" not in rec.inputs for j in range(k) for p in range(d)):
            return  # the target cells aren't currently shown (folded away)
        vectors = [[_parse_int(rec.inputs[f"cell:vec:targets:{j}:{p}"].value) for p in range(d)] for j in range(k)]
        if any(v is None for m in vectors for v in m):
            return
        editor.set_target_override_vectors(vectors)
        render()

    def on_ratio_change(cid):
        # a quantities-row ratio cell committing on blur (comma / target / held / interest) — the
        # scalar twin of the interval-vectors row's column edit. The typed fraction parses to a
        # vector and routes through the SAME setter the vector edit uses; a ":pending" draft fills
        # that column's draft instead (like typing its vector cells). render() always runs: a valid
        # edit shows the new value, an invalid one snaps the field back — and a bad fraction also
        # toasts WHY (unparseable vs outside the prime limit). An untouched "?/?" draft or a cleared
        # cell is a silent no-op (no toast), not an error.
        if building[0] or cid not in rec.inputs:
            return
        group, idx = cid.split(":")
        raw = str(rec.inputs[cid].value).strip()
        if raw in ("", "?/?"):  # an untouched draft placeholder or a cleared cell
            render()
            return
        try:
            vector = service.interval_vector(raw, editor.state.d, editor.state.domain_basis)
        except ValueError as exc:
            ui.notify(str(exc), type="negative", position="top")
            render()  # revert the field to its current value
            return

        def replace(current, setter):  # swap the edited column in, skipping a no-op blur (no undo step)
            vectors = [list(v) for v in current]
            if vectors[int(idx)] != list(vector):
                vectors[int(idx)] = vector
                setter(vectors)

        if idx == "pending":  # fill the draft column, committing it like its vector cells do
            {"comma": editor.set_pending_comma, "interest": editor.set_pending_interest,
             "held": editor.set_pending_held, "target": editor.set_pending_target}[group](vector)
        elif group == "comma":
            replace(editor.state.comma_basis, editor.edit_comma_basis)
        elif group == "interest":
            replace(editor.interest_vectors, editor.set_interest_vectors)
        elif group == "held":
            replace(editor.held_vectors, editor.set_held_vectors)
        else:  # target
            targets = editor.target_override or service.target_interval_set(
                editor.target_spec, editor.state.domain_basis)
            replace(service.target_interval_vectors(targets, editor.state.d, editor.state.domain_basis),
                    editor.set_target_override_vectors)
        render()

    def on_power_change(cid):
        # editable power inputs share this kind. optimization:power drives the Lp optimization
        # power; control:q (the complexity norm power in box 𝒄) is styling-only for now, so we
        # accept the keystroke but don't yet wire it through to the scheme.
        if building[0] or cid not in rec.inputs:
            return
        if cid != "optimization:power":
            return  # control:q: white-box look, no behaviour yet (wiring later)
        raw = str(rec.inputs[cid].value).strip().lower()
        if raw in ("∞", "inf", "max", "minimax"):
            power = float("inf")
        else:
            try:
                power = float(raw)
            except ValueError:
                return  # leave the scheme unchanged on unparseable input
            if power <= 0:
                return
        editor.set_optimization_power(power)
        render()

    def on_gentuning_change(cid):
        # an editable generator-tuning-map cell: a valid cents number overrides that one
        # generator's tuning (a per-number manual override); an unparseable entry is ignored
        if building[0] or cid not in rec.inputs:
            return
        try:
            cents = float(str(rec.inputs[cid].value).strip())
        except ValueError:
            return
        editor.set_generator_tuning_component(int(cid.rsplit(":", 1)[1]), cents)
        render()

    def on_gentuning_wheel(cid, delta_y):
        # the genmap cell's hover-and-scroll fine-adjust: each wheel notch nudges this generator's
        # tuning by a thousandth of a cent — scroll up (deltaY < 0) raises it, down lowers it. The
        # cents face shows 3 dp, so one notch moves the last shown digit by one.
        if building[0] or not delta_y:
            return
        editor.nudge_generator_tuning_component(int(cid.rsplit(":", 1)[1]), 1 if delta_y < 0 else -1)
        render()

    def on_prescaler_change(cid):
        # a bare prescaler 𝐿 diagonal cell (cid "cell:prescaling:primes:i:i"): a valid float
        # overrides that one diagonal entry (which then drives EVERY downstream consumer — the
        # product tiles, complexity, weights, the tuning solve and its retunings/damages).
        # The first edit seeds the override from the scheme so the d-1 untouched cells keep
        # their displayed values (set_custom_prescaler_entry handles that). The bare prescaler
        # is a float diagonal (log_prime / prime / identity / typed), so parse as float — an
        # unparseable entry leaves the scheme unchanged, like the other editable cells.
        if building[0] or cid not in rec.inputs:
            return
        try:
            value = float(str(rec.inputs[cid].value).strip())
        except ValueError:
            return
        editor.set_custom_prescaler_entry(int(cid.split(":")[3]), value)
        render()

    def on_ptext_edit(cid, value):
        # the editable plain-text duals: a valid EBK string drives the grid (like
        # typing in a matrix cell); an unparseable one reddens the box and is ignored
        if building[0]:
            return
        if cid == "ptext:mapping:primes":
            ok = editor.try_edit_mapping_text(value)
        elif cid == "ptext:vectors:commas":
            ok = editor.try_edit_comma_basis_text(value)
        elif cid == "ptext:tuning:gens":  # a typed cents tuning freezes the generator tuning map
            ok = editor.set_generator_tuning_text(value)
        elif cid == "ptext:vectors:targets":  # a typed vector list overrides the target interval set
            ok = editor.set_target_override_text(value)
        elif cid == "ptext:prescaling:primes":  # a typed d×d matrix overrides the prescaler 𝐿's
            # diagonal — the alternative to per-cell edits in the same tile, and the only path
            # for typing the WHOLE diagonal at once. An invalid shape (non-diagonal, wrong size)
            # reddens the box rather than mangling 𝐿, like the mapping / comma-basis duals.
            ok = editor.set_custom_prescaler_text(value)
        else:
            return
        if ok:
            rec.ptext_inputs[cid].classes(remove="rtt-ptext-error")
            render()
        else:
            rec.ptext_inputs[cid].classes(add="rtt-ptext-error")

    def act(action):
        action()
        render()

    def on_show_toggle(key, value):
        # building[0] guards the echo when render() syncs a checkbox to the document
        # (e.g. after undo/redo/reset/select-all) rather than a real user toggle
        if building[0]:
            return
        editor.set_show(key, value)
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def on_select_all(value):
        # the settings panel's select-all/none: flip every implemented Show toggle at once
        if building[0]:
            return
        editor.set_all_show(value)
        render()

    def on_part_click(key):
        # a click on one part of the general dummy tile flips that layer's toggle (the tile is the
        # checkbox column's alternative). A value-cell part (the value, its closed form) is inert
        # until its host cell is shown — there's nowhere to draw it otherwise — so a click while
        # gridded values is off does nothing (the CSS also makes it unclickable; this guards the
        # state too). A refinement (equivalences, mnemonics) stays live and, via set_show, pulls
        # its base layer on when selected. render() then re-styles the tile and animates the grid.
        if building[0]:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not editor.settings[host]:
            return
        editor.set_show(key, not editor.settings[key])
        render()

    def on_preset(name, value):
        # the temperament chooser loads a mapping (an undoable edit); the tuning chooser
        # sets the view scheme. A re-render echo is ignored via the building guard.
        if building[0]:
            return
        if name == "temperament":
            # the divider rows are disabled and the prompt is a display-value placeholder
            # (not a row), so only a preset reaches here; load its comma basis as an
            # undoable edit, then re-render to snap the box onto the now-matching preset.
            if value in presets.TEMPERAMENT_COMMAS:
                editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
            render()
        elif name == "tuning" and value is not None:
            editor.set_tuning_scheme(value)  # the bare name, applied in the live target mode
            render()
        elif name == "prescaler" and value is not None:
            editor.set_complexity_prescaler(value)  # swaps the scheme's prescaler, clears the override
            render()

    def on_form_choose(name, value):
        # the <choose form> control: selecting "canonical" re-stores that matrix in
        # canonical form (an undoable edit). The select snaps back to its placeholder on
        # the re-render. building[0] guards the echo from that reset.
        if building[0] or value != "canonical":
            return
        if name == "mapping":
            editor.canonicalize_mapping()
        elif name == "comma_basis":
            editor.canonicalize_comma_basis()
        render()

    def on_target_change():
        # the target chooser is a numeric limit + a TILT/OLD family; compose them into
        # a spec ("9-TILT", or just "TILT" when the limit is blank). An incomplete or
        # out-of-range limit (one that resolves to no intervals) is held without
        # disturbing the grid, mirroring how a half-typed mapping cell is ignored.
        if building[0]:
            return
        num, sel = rec.selects["preset:target"]
        family = sel.value or "TILT"
        spec = f"{int(num.value)}-{family}" if num.value else family
        try:
            valid = bool(service.target_interval_set(spec, service.standard_primes(editor.state.d)))
        except Exception:
            valid = False
        if not valid:
            return
        editor.set_target_spec(spec)
        render()

    def on_control_select(cid, value):
        # the weighting choosers (box 𝒄 complexity + norm, box 𝒘 weight slope): each swaps a
        # scheme trait, re-weighting and retuning. The re-render echo is ignored via the guards.
        # (The prescaler chooser is a preset now — see on_preset.)
        if building[0] or value is None:
            return
        if cid == "control:norm":
            editor.set_complexity_euclidean(value == "Euclidean")
        elif cid == "control:slope":
            editor.set_weight_slope(value)
        elif cid == "control:complexity":
            if value == "custom":  # a display-only state (a shape off the preset list): no-op
                return
            # the dropdown presents the friendly display name ("log-product (lp)"); map it back
            # to the internal complexity key the editor takes ("lp")
            internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
            editor.set_complexity_name(internal)
        elif cid == "control:diminuator":  # the checkbox passes a bool (replace the diminuator?)
            editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":  # the target-controls checkbox: all-interval vs target-based
            editor.set_all_interval(bool(value))
        render()

    def on_range_mode(value):
        # which generator tuning range the ranges chart shows. A re-render echo (the radio
        # mirroring editor.range_mode) is ignored via the building/None guards, like the presets.
        if building[0] or value is None:
            return
        editor.set_range_mode(value)
        render()

    def on_toggle(item):  # fold/unfold one row, column, or tile ("row:tuning", "tile:mapping:primes")
        editor.toggle_collapsed(item)
        render()

    def on_toggle_all():  # the master node-corner toggle: fold the whole grid, or expand it all back
        editor.set_collapsed(spreadsheet.toggle_all_collapsed(last_lay[0], editor.collapsed))
        render()

    def on_cell_focus(cid):
        # an editable cell took focus: snapshot the on-screen grid as the preview baseline so every
        # subsequent live edit can ring exactly the cells it moves (computed against this snapshot in
        # render), until the cell is left. No render needed — nothing has changed against itself yet.
        rec.preview_baseline = last_lay[0]
        rec.preview_source = cid

    def on_cell_blur():
        # leaving the cell ends the preview: forget the baseline and strip every highlight ring
        rec.preview_baseline = None
        rec.preview_source = None
        rec.clear_preview()

    # drag-and-drop: a grip's dragstart records the column it picked up; a drop slot's drop reads it
    # and moves the interval into that gap (between/within the interval lists). The whole gesture is
    # one editor edit (one undo step). The dragging-state class + hover highlight are client-side
    # (_DRAG_JS); only the pick-up and the drop cross to Python.
    drag_src = [None]  # (list, idx) of the column being dragged, or None

    def on_drag_start(lst, idx):
        drag_src[0] = (lst, idx)

    def on_drag_end():
        drag_src[0] = None  # a cancelled / completed drag leaves no stale source

    def on_drop(dst_list, gap):
        src = drag_src[0]
        drag_src[0] = None
        if src and editor.move_interval(src[0], src[1], dst_list, gap):
            render()  # the reconciler reflows the affected lists into their new shape
    # wire the reconciler's callbacks now that the event handlers exist: the cell
    # builders fire these (a control's on_change/on_click -> an editor edit + re-render)
    rec._cb = SimpleNamespace(
        act=act,
        on_cell_blur=on_cell_blur,
        on_cell_focus=on_cell_focus,
        on_comma_change=on_comma_change,
        on_drag_start=on_drag_start,
        on_drag_end=on_drag_end,
        on_drop=on_drop,
        on_control_select=on_control_select,
        on_form_choose=on_form_choose,
        on_gentuning_change=on_gentuning_change,
        on_gentuning_wheel=on_gentuning_wheel,
        on_held_change=on_held_change,
        on_interest_change=on_interest_change,
        on_mapping_change=on_mapping_change,
        on_power_change=on_power_change,
        on_prescaler_change=on_prescaler_change,
        on_preset=on_preset,
        on_ptext_edit=on_ptext_edit,
        on_ratio_change=on_ratio_change,
        on_range_mode=on_range_mode,
        on_target_cells_change=on_target_cells_change,
        on_target_change=on_target_change,
        on_toggle=on_toggle,
        on_toggle_all=on_toggle_all,
    )


    def render():
        building[0] = True
        st = editor.state
        lay = editor.layout()
        last_lay[0] = lay
        # The body scroller holds the grid shifted up by the column strip's height (freeze_y): the
        # board content is (total_h - fy) tall, its cells/lines/blocks placed at native coords minus
        # fy, so they land where they always did with the column-title rows now lifted into the strip
        # above. The strip (its inner is full grid width, translated horizontally by _FREEZE_JS) and
        # the corner keep native coords. gridbody drops below the strip (top = _PAD + fy).
        fx, fy = lay.freeze_x, lay.freeze_y
        # the grid pane is sized to enclose the grid + the column strip, a _PAD margin on every side,
        # and the last column title's right overhang (right_overhang — the interest title renders
        # unwrapped past its narrow column, so the pane widens to show it instead of clipping). Its
        # grey backdrop then frames the gridlines all round, white beyond, rather than filling the
        # window. The top/left margin is the frozen regions' _PAD inset; the right/bottom margin is the
        # body's own scroll padding, so it survives scrolling to the end (see .rtt-gridbody). The CSS
        # caps the pane at the window, past which the body scrolls.
        grid_pane.style(f"width:{lay.width + lay.right_overhang + 2 * _PAD}px; height:{lay.height + 2 * _PAD}px")
        board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
        colhead.style(f"height:{fy}px")
        colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
        corner.style(f"width:{fx}px; height:{fy}px")
        gridbody.style(f"top:{_PAD + fy}px")
        rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
        # the settings pane's frozen header takes the same height as the grid's frozen column
        # strip, so the two frozen/scrolling seams line up across the app
        show_frozen.style(f"height:{fy}px")
        # the settings body sizes to its own content but caps at the window less the inset (12px) and
        # the frozen header (fy) above it, so a tall toggle list scrolls there instead of off-screen
        show_scroll.style(f"max-height:calc(100vh - {12 + fy}px)")
        seen = set()

        # Each gridline renders into every pane its extent reaches, so the branching stays put in
        # the frozen header / row band while the body scrolls beneath. The scrolling body holds
        # the copy shifted up by fy; a line rising above freeze_y also draws into the column strip
        # (at native y), and one reaching left of freeze_x into the sticky row band (body space) —
        # each clipped to its band by the pane's overflow:hidden, meeting the body copy
        # continuously at the seam. No gridline falls in the corner (column lines sit right of
        # freeze_x, row lines below freeze_y), so it's skipped. Copies are keyed #col / #row, each
        # added to `seen`, so the orphan sweep below drops one whose line later stops reaching it.
        def place_line(ln, suffix, parent, shift):
            eid = ln.id + suffix
            seen.add(eid)
            if eid not in rec.els:
                with parent:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    rec.els[eid] = ui.element("div").classes(cls).props(f'data-eid="{eid}"')
            rec.els[eid].style(_line_style(ln, shift))

        for ln in lay.lines:
            x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
            y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
            if x1 >= fx and y1 >= fy:
                place_line(ln, "", board, fy)              # the scrolling body
            if x1 >= fx and y0 < fy:
                place_line(ln, "#col", colhead_inner, 0)   # the frozen column strip (native y)
            if x0 < fx and y1 >= fy:
                place_line(ln, "#row", rowband, fy)        # the frozen row band (body scroll space)

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in rec.els:
                # a block is a thin-bordered box (boxed, the nested tuning-ranges frame), a
                # plain grey tile (tint ""), a colorization wash's white base (tint "base"),
                # or its coloured layer (tint = group name). Fixed for the block's lifetime,
                # so the class is chosen once.
                with board:
                    cls = ("rtt-block-boxed" if bl.boxed
                           else "rtt-washbase" if bl.tint == "base"
                           else "rtt-wash" if bl.tint else "rtt-block")
                    rec.els[bl.id] = ui.element("div").classes(cls).props(f'data-eid="{bl.id}"')
            style = f"left:{bl.x}px; top:{bl.y - fy}px; width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:  # the coloured layer (the base draws white from CSS)
                style += f"; background:{_TINTS[bl.tint]}"
            rec.els[bl.id].style(style)

        # the edit-preview highlight: while a cell is focused, ring every OTHER cell whose value this
        # render has moved against the baseline snapshotted when the cell took focus. With nothing
        # being edited (no baseline) the set is empty, so the loop below clears any lingering rings.
        preview = (spreadsheet.changed_cell_ids(rec.preview_baseline, lay) - {rec.preview_source}
                   if rec.preview_baseline is not None else frozenset())

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id in rec.els and rec.kinds[cb.id] != cb.kind:
                rec.drop(cb.id)  # a cell changed kind (e.g. cents <-> math expression): rebuild it
            if cb.kind in _AUDIO_KINDS and cb.id in rec.els and rec.audio_keys.get(cb.id) != cb.values:
                rec.drop(cb.id)  # cents changed -> rebuild so the baked-in click handler sounds the new pitch
            container = _freeze_container(cb, fx, fy)
            if cb.id not in rec.els:
                with cell_parents[container]:
                    rec.make_cell(cb)
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner
            top = cb.y - (fy if container in ("body", "row") else 0)
            rec.els[cb.id].style(f"left:{cb.x}px; top:{top}px; width:{cb.w}px; height:{cb.h}px")
            rec.update_cell(cb)
            ringed = cb.id in preview
            rec.els[cb.id].classes(add="rtt-preview-change" if ringed else "",
                                   remove="" if ringed else "rtt-preview-change")
        rec.preview_shown = set(preview)  # every rung id is a live cell (changed_cell_ids ⊆ lay.cells)

        for eid in [e for e in rec.els if e not in seen]:
            rec.drop(eid)

        # the optimization objective is read-only yet helped, and that help names a different
        # quantity per mode — the minimized damage ⟪𝐝⟫ₚ over the targets, or (all-interval) the
        # retuning magnitude. Swap its tooltip(s) to match the live scheme, the same in-place
        # relabel the symbol glyph makes; set_text only pushes when the wording actually changes.
        if rec.objective_tips:
            obj_help = tooltips.objective_help(service.is_all_interval(editor.tuning_scheme))
            for tip in rec.objective_tips.values():
                tip.set_text(obj_help)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        refs["reset"].set_enabled(editor.can_reset)
        # reflect the document's Show settings into the panel (after undo/redo/reset/
        # select-all/load). building[0] is still True, so these programmatic value writes
        # are swallowed by on_show_toggle/on_select_all rather than re-firing as edits.
        for key, box in boxes.items():
            if box.value != editor.settings[key]:
                box.value = editor.settings[key]
        # the general dummy tile: style each layer's part(s) by its live setting — black + opaque
        # when shown, grey + dimmed when hidden — so the tile both mirrors and drives the grid. A
        # value-cell part is inert (no click) until its host cell is shown (_TILE_HOST), mirroring
        # the grid where the value/closed-form need the boxed cell to sit in. Mnemonics is special:
        # it is an underline ON the name, so its COLOUR tracks the name (the layer it refines) while
        # only the underline tracks mnemonics itself — else a name-shown/mnemonic-hidden state would
        # grey just the one letter mid-word.
        for key, parts in tile_parts.items():
            shown = editor.settings["names"] if key == "mnemonics" else editor.settings[key]
            host = _TILE_HOST.get(key)
            inert = host is not None and not editor.settings[host]
            for part in parts:
                part.classes(add="rtt-part-on" if shown else "rtt-part-off",
                             remove="rtt-part-off" if shown else "rtt-part-on")
                part.classes(add="rtt-part-inert") if inert else part.classes(remove="rtt-part-inert")
                if key == "mnemonics":
                    part.classes(add="rtt-mnem-underline") if editor.settings["mnemonics"] \
                        else part.classes(remove="rtt-mnem-underline")
        # the master checkbox: checked (true / black fill) when all on, unchecked (false /
        # empty) when all off, MIXED (grey fill) when some-but-not-all are on
        states = [editor.settings[k] for k in show_settings.IMPLEMENTED]
        select_all_box.value = all(states)
        if any(states) and not all(states):
            select_all_box.classes(add="rtt-show-mixed")
        else:
            select_all_box.classes(remove="rtt-show-mixed")
        # persist the whole document so a browser refresh restores exactly this state
        _doc_store()[_STORE_KEY] = editor.serialize()
        building[0] = False

    # the corner hamburger toggles the settings drawer, which slides the app right
    drawer_open = [False]

    def toggle_drawer():
        drawer_open[0] = not drawer_open[0]
        drawer.classes(add="rtt-drawer-open") if drawer_open[0] else drawer.classes(remove="rtt-drawer-open")

    with ui.element("div").classes("rtt-shell"):
        # the rail and the settings pane share one group so the rail's grey stretches to the
        # pane's height; the app sits to the group's right
        with ui.element("div").classes("rtt-panelgroup"):
            # the left rail: the hamburger on top, the app title rotated a quarter-turn below it.
            # The rail is left of the pane, so opening the pane never moves the title.
            with ui.element("div").classes("rtt-rail"):
                ui.button(icon="menu", on_click=toggle_drawer, color=None).props("flat dense") \
                    .classes("rtt-hamburger").tooltip(tooltips.CHROME_HELP["settings"])
                ui.label("D&D's RTT app").classes("rtt-sidetitle")
            drawer = ui.element("div").classes("rtt-drawer")
            with drawer, ui.element("div").classes("rtt-drawer-inner"):
                # the frozen header: just the select-all/none master, pinned above the scrolling
                # groups (render() sizes it to the layout's freeze_y, matching the main app's frozen
                # band). Its bottom border is the frozen/scrolling seam. The show/example column
                # titles are NOT here — they describe only the specific-group checkbox column now
                # (the general group is the dummy tile), so they ride that group's head below.
                show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
                with show_frozen:
                    # the select-all/none master checkbox: one click flips every implemented Show
                    # toggle on or off. Its checked state (all on) is kept in sync by render();
                    # the not-yet-built toggles are left untouched.
                    with ui.element("div").classes("rtt-show-all"):
                        select_all_box = ui.checkbox(
                            "select all / none",
                            value=all(editor.settings[k] for k in show_settings.IMPLEMENTED),
                            on_change=lambda e: on_select_all(e.value)) \
                            .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                            .tooltip(tooltips.CHROME_HELP["select_all"])
                # the scrolling body: the toggle groups, which scroll under the frozen header when
                # the panel outgrows the window (rather than spilling off the bottom of the screen)
                boxes: dict = {}  # specific-group toggle key -> checkbox, so a sub-control row can bind to its parent
                tile_parts: dict = {}  # general-group layer key -> its clickable dummy-tile part (render() styles these)
                show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
                with show_scroll:
                    for group_name, items in show_settings.SHOW_GROUPS:
                        with ui.element("div").classes("rtt-show-group"):
                            if group_name == "general":
                                # the general layers render as ONE clickable dummy value tile rather
                                # than a checkbox column — laid out and proportioned like a real value
                                # tile. Each part is a sample of that layer, clicked directly to show/
                                # hide it; render() styles it by the live setting. A layer's PRIMARY
                                # element carries the showpart:<key> marker + hover help; some layers
                                # also surface inside the value cell (the symbol's row header, the
                                # units' per-cell unit) or split in two (the name, around its mnemonic
                                # letter) — those extra elements ride the same key's list.
                                def add_el(key, html, *, marked=False, size=None, style=""):
                                    fs = size if size is not None else _TILE_FONT.get(key)
                                    css = (f"font-size:{fs}px;" if fs else "") + style
                                    el = ui.html(html).classes("rtt-tile-part").tooltip(tooltips.SHOW_HELP[key])
                                    if key == "mnemonics":
                                        el.classes(add="rtt-tile-mnem")  # always underlined; render() colours it
                                    if marked:
                                        el.mark(f"showpart:{key}")
                                    if css:
                                        el.style(css)
                                    el.on("click", lambda k=key: on_part_click(k))
                                    tile_parts.setdefault(key, []).append(el)
                                    return el

                                def part_el(key, *, size=None, style=""):  # the layer's primary (marked) element
                                    return add_el(key, _general_part_html(key), marked=True, size=size, style=style)

                                with ui.element("div").classes("rtt-show-tile"):
                                    ui.html(_tile_fold_html()).classes("rtt-tile-fold")  # decorative fold toggle, top-left
                                    for line in _GENERAL_TILE_LINES:
                                        if "gridded_values" in line:
                                            # the value cell, like a real gridded cell: a square box (the
                                            # gridded_values frame) holding the closed form (math_expressions)
                                            # over "= value" (quantities) over the unit (rides the units layer)
                                            # — all stacked INSIDE the box, as on a real tile, the form/value
                                            # font-FITTED to the square so they don't spill. A row-header
                                            # matlabel (rides the symbol layer) sits in a left gutter; an EQUAL
                                            # empty gutter on the right keeps the boxed cell centred in the tile.
                                            gut = 20  # the row-label gutter, mirrored on the right for centring
                                            cell_x = gut + _TILE_CELL_X  # the cell's left within the container
                                            cell_y = _TILE_CELL_Y        # the cell's top within the frame (below the outer top)
                                            row_y = cell_y + (_TILE_CELL - 13) // 2  # row label centred on the cell
                                            with ui.element("div").classes("rtt-tile-line"), \
                                                    ui.element("div").style(f"position:relative;"
                                                        f"width:{gut + _TILE_FRAME_W + gut}px;height:{_TILE_FRAME_H}px"):
                                                add_el("symbols", _math_html(_TILE_ROWLABEL), size=_TILE_FONT["rowlabel"],
                                                       style=f"position:absolute;left:0;top:{row_y}px;width:{gut - 3}px;"
                                                             "height:13px;justify-content:flex-end")
                                                part_el("gridded_values", style=f"position:absolute;left:{gut}px;top:0")
                                                part_el("math_expressions", size=_fit_font(_TILE_MATH, _TILE_CELL),
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
                                                              f"width:{_TILE_CELL}px;height:9px;justify-content:center")
                                                part_el("quantities", size=_fit_font(_TILE_VALUE, _TILE_CELL),
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
                                                              f"width:{_TILE_CELL}px;height:10px;justify-content:center")
                                                add_el("units", _units_html(_TILE_UNITS), size=_TILE_FONT["cellunit"],
                                                       style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
                                                             f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:#555")
                                        elif "names" in line:
                                            # the name word, split so the mnemonic letter is its own target
                                            # while the word still reads whole: "tile " + "n" + "ame". Only
                                            # the first piece is marked, so a test click lands one toggle.
                                            before, _letter, after = _tile_name_pieces()
                                            with ui.element("div").classes("rtt-tile-line"):
                                                add_el("names", _escape(before), marked=True)
                                                part_el("mnemonics")
                                                add_el("names", _escape(after))
                                        elif "presets" in line:
                                            # the presets chooser sits in a control box (bordered, spanning the
                                            # full tile width like a real tile's control boxes); no label.
                                            with ui.element("div").classes("rtt-tile-line rtt-tile-line-wide"), \
                                                    ui.element("div").classes("rtt-tile-cbox"):
                                                part_el("presets")
                                        else:
                                            with ui.element("div").classes("rtt-tile-line"):
                                                for key in line:
                                                    part_el(key)
                                continue
                            # the specific group keeps the show | example column header (moved here from
                            # the frozen band — it describes only this checkbox column now).
                            with ui.element("div").classes("rtt-show-head"):
                                ui.label("show").classes("rtt-show-title")
                                ui.label("example").classes("rtt-show-examplehdr")
                            for key, label, _ in items:
                                row = ui.element("div").classes("rtt-show-row")
                                with row:
                                    box = ui.checkbox(label, value=editor.settings[key],
                                                      on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                                        .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                                        .tooltip(tooltips.SHOW_HELP[key])
                                    example = ui.html(_example_html(key)).classes("rtt-ex-cell")
                                    if key not in show_settings.IMPLEMENTED:
                                        box.props("disable")  # not built yet -> greyed and inert
                                        example.classes(add="rtt-ex-disabled")  # ...and its sample greys to match
                                boxes[key] = box
                                parent = show_settings.SUBCONTROLS.get(key)
                                if parent:  # indent by nesting depth (so a grandchild sits further right
                                    # than its parent) and show the row only while the parent is on. Only the
                                    # checkbox shifts within its grid column, so the example column stays aligned.
                                    box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                                    row.bind_visibility_from(boxes[parent], "value")

        grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with grid_pane:
            # the grid pane splits into frozen title regions OUTSIDE the body scroller (so the body's
            # scrollbars stop at the titles): the column-title strip (scrolls horizontally in sync via
            # _FREEZE_JS), the corner (frozen both), and the body scroller .rtt-gridbody — which holds
            # the value cells, lines and blocks (on .rtt-gridcontent) plus the sticky-left row band.
            # Sizes/positions are set in render() from the layout's freeze_x/freeze_y. Column/corner
            # cells keep native coords; body/row cells shift up by freeze_y into the body's scroll space.
            colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with colhead:
                colhead_inner = ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
            corner = ui.element("div").classes("rtt-corner").mark("corner")
            with corner:
                # the corner holds the undo/redo title tile (the app title is on the rail)
                with ui.element("div").classes("rtt-titletile").mark("titletile"):
                    with ui.element("div").classes("rtt-tile-btns"):
                        refs["undo"] = ui.button(icon="undo", on_click=lambda: act(editor.undo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("undo").tooltip(tooltips.CHROME_HELP["undo"])
                        refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("redo").tooltip(tooltips.CHROME_HELP["redo"])
                        # reset everything (settings, expand/collapse, values) to the
                        # as-shipped defaults — itself an undoable action
                        refs["reset"] = ui.button(icon="restart_alt", on_click=lambda: act(editor.reset), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("reset").tooltip(tooltips.CHROME_HELP["reset"])
            gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
            with gridbody:
                board = ui.element("div").classes("rtt-gridcontent").mark("board")
                with board, ui.element("div").classes("rtt-band"):
                    rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
            # where each cell renders: a frozen region (corner/column strip/row band) or the body board
            cell_parents = {"corner": corner, "col": colhead_inner, "row": rowband, "body": board}

    def on_key(e):
        if not (e.action.keydown and e.modifiers.ctrl):
            return
        is_z = e.key == "z" or e.key == "Z"
        if e.key == "y" or (is_z and e.modifiers.shift):
            act(editor.redo)
        elif is_z:
            act(editor.undo)

    ui.keyboard(on_key=on_key)
    render()


def _reload_excludes(worktrees: Path) -> str:
    """The uvicorn ``reload_excludes`` string: NiceGUI's default ignore globs plus the
    agent-worktrees subtree, but only when it exists. An existing directory becomes a
    watchfiles ``exclude_dir`` (every change under it is dropped by path-parent
    containment), the only way to ignore a subtree of unknown depth — uvicorn's glob
    matcher has no ``**`` and a relative dir never matches the absolute change paths. The
    path must therefore be absolute AND exist: uvicorn globs any non-dir exclude relative
    to cwd, and on Python 3.14 pathlib rejects an absolute glob pattern
    (NotImplementedError), crashing the server at startup. Absent, there's nothing to skip."""
    excludes = [".*", ".py[cod]", ".sw.*", "~*"]
    if worktrees.is_dir():
        excludes.append(str(worktrees))
    return ", ".join(excludes)


def main() -> None:
    """Launch the NiceGUI server.

    Bare ``python app.py`` is local dev: port 8137 with hot-reload (the user keeps an
    instance running there to use the app). A hosting platform — Render — sets ``PORT``,
    which switches to a production launch: bind every interface on that port, no
    file-watching reloader, and sign sessions with the secret from the environment.
    """
    hosted_port = os.environ.get("PORT")
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    elif hosted_port:
        port = int(hosted_port)
    else:
        port = 8137
    run_kwargs = dict(
        title="D&D's RTT App", favicon="https://github.com/DandDsRTT.png",
        show=False, port=port,
        storage_secret=os.environ.get("STORAGE_SECRET", _STORAGE_SECRET),
    )
    if hosted_port:
        run_kwargs.update(host="0.0.0.0", reload=False)
    else:
        worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
        run_kwargs.update(reload=True, uvicorn_reload_excludes=_reload_excludes(worktrees))
    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__"}:
    main()
