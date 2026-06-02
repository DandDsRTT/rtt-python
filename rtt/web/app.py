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
import sys
from html import escape as _escape
from pathlib import Path
from urllib.parse import quote

from nicegui import app, helpers, ui

from rtt.web import presets
from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web import tooltips
from rtt.web.editor import Editor

_ASSETS = Path(__file__).parent / "assets"  # CSS/JS asset files, loaded at import time

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration
_PANEL_W = 330  # px width the settings drawer opens to (the Show + example columns)
_RAIL_W = 40  # px width of the permanent left rail (hamburger + the rotated app title)
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

# One weight and colour for every EBK bracket, brace and vector rule. Each mark is
# drawn as an SVG whose viewBox maps 1:1 to the cell's px size (see _svg), so a
# stroke specified as N px is exactly N px tall AND wide at any span — no scaling.
_BR_COLOR = "#1a1a1a"
_PENDING_COLOR = "#e53935"  # red for a pending comma's draft cells, brackets and "?"
_SEAM = "#999"  # the thin grey rule separating the frozen title panes from the scrolling body
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
_BR_BAR = 2  # main bar / vector-rule / square-bracket bar thickness (px)
_BR_SERIF_T = 0.9  # square + top bracket serif thickness — a thin foot, well under the bar
_BR_SERIF_L = 6  # square + top bracket serif length (how far the foot reaches) — also
# the shared footprint width every value bracket (square AND angle) draws within
_BR_INSET = 2.5  # gap from a bracket's open side to the value cells it hugs
# The ⟨ and the brace are filled ribbons of varying width (see _ribbon): a
# calligraphic pen lays a LONG stroke down THICK and a SHORT one THIN. The thin
# ends are kept delicate so the thick/thin taper reads clearly.
_BR_ANGLE_THICK = 1.1  # ⟨ half-width at the vertex (heavier)
_BR_ANGLE_THIN = 0.45  # ⟨ half-width at the open tips (much lighter) — a pronounced taper
_BR_BRACE_THICK = 1.15  # brace arm half-width: the long horizontal stroke is thick
_BR_BRACE_THIN = 0.4  # brace end-serif half-width: the short upturn is thin
_BR_BRACE_CUSP = 0.2  # brace central-cusp half-width: the short dip is a near point
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


_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --rail-w:{_RAIL_W}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --pending-color:{_PENDING_COLOR};
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


_LABEL_KINDS = {"prime", "formcell", "colheader", "rowlabel", "mapped", "vec",
                "rowtoggle", "coltoggle", "tiletoggle", "alltoggle"}  # "ptext" has its own font-sync branch

# Which sticky band each title/toggle kind renders into; every other cell goes to the body
# board. The column titles + their fold toggles ride the column band (sticky to the window top);
# the row titles + toggles the row band (sticky to the left); the master toggle (and the undo/
# redo title tile) the corner band (sticky to both). Per-tile toggles aren't frozen.
_FREEZE_CONTAINER = {"colheader": "col", "coltoggle": "col",
                     "rowlabel": "row", "rowtoggle": "row",
                     "alltoggle": "corner"}

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


def _svg(w, h, body):
    return (f'<svg width="100%" height="100%" viewBox="0 0 {w:.2f} {h:.2f}" '
            f'preserveAspectRatio="none" style="display:block;overflow:visible">{body}</svg>')


def _rect(x, y, w, h):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{_BR_COLOR}"/>'


def _ribbon(pts):
    """One filled path tracing a variable-width stroke down a centreline. ``pts``
    is a list of ``(x, y, half_width)``; the outline runs up one offset edge and
    back down the other. A long run can be laid thick and a short turn thin, and
    the centreline may double back (the brace cusp, the ⟨ vertex) — the offsets
    meet at a clean point there, and any inner overlap fills solid (nonzero)."""
    edge_a, edge_b = [], []
    n = len(pts)
    for i in range(n):
        x, y, hw = pts[i]
        px, py = pts[i - 1][:2] if i else pts[i][:2]
        nx, ny = pts[i + 1][:2] if i < n - 1 else pts[i][:2]
        tx, ty = nx - px, ny - py
        length = math.hypot(tx, ty) or 1.0
        ox, oy = -ty / length * hw, tx / length * hw  # normal * half-width
        edge_a.append((x + ox, y + oy))
        edge_b.append((x - ox, y - oy))
    outline = edge_a + edge_b[::-1]
    return ('<path fill="' + _BR_COLOR + '" d="M'
            + ' '.join(f'{x:.2f},{y:.2f}' for x, y in outline) + ' Z"/>')


def _qbez(p0, ctrl, p1, w0, w1, n, *, skip_first=False):
    """Sample a quadratic Bézier from ``p0`` to ``p1`` into ``(x, y, half_width)``
    centreline points, the width lerped ``w0``->``w1`` along it."""
    out = []
    for i in range(n + 1):
        if skip_first and i == 0:
            continue
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * p1[1]
        out.append((x, y, w0 + (w1 - w0) * t))
    return out


def _square_bracket(w, h, side):
    """``[`` or ``]`` as a bar + two perpendicular feet, hugging the value cells
    (open side ``_BR_INSET`` from them). Constant weight at 1 row or many."""
    if side == "left":  # bar on the left, feet reaching right toward the cells
        x_in = w - _BR_INSET
        x_out = x_in - _BR_SERIF_L
        bar_x = x_out
    else:  # "right": bar on the right, feet reaching left toward the cells
        x_out = _BR_INSET
        bar_x = x_out + _BR_SERIF_L - _BR_BAR
    return _svg(w, h,
        _rect(bar_x, 0, _BR_BAR, h)
        + _rect(x_out, 0, _BR_SERIF_L, _BR_SERIF_T)
        + _rect(x_out, h - _BR_SERIF_T, _BR_SERIF_L, _BR_SERIF_T))


def _top_bracket(w, h):
    """The matrix's spanning top bracket: a bar across the top with a down-foot at
    each end. Same weights as the square brackets, so the frame reads as one font."""
    return _svg(w, h,
        _rect(0, 0, w, _BR_BAR)
        + _rect(0, 0, _BR_SERIF_T, _BR_SERIF_L)
        + _rect(w - _BR_SERIF_T, 0, _BR_SERIF_T, _BR_SERIF_L))


def _angle_bracket(w, h):
    """``⟨`` drawn within the SAME oblong footprint as the square brackets — a
    serif-length wide and the full cell height — so every value bracket shares one
    rectangle. A filled ribbon, subtly heavier at the vertex than the open tips.
    The centreline insets (vertex by the thick half-width, tips by the thin one)
    land the ribbon's outer edge on that footprint, vertex hugging the far side."""
    bx1 = w - _BR_INSET  # open tips, nearest the value cells
    bx0 = bx1 - _BR_SERIF_L  # vertex, at the far edge — width matches the square's reach
    cy = h / 2
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.4
    top, vertex, bot = (tx, 0.2), (vx, cy), (tx, h - 0.2)
    n = 10
    pts = [(top[0] + (vertex[0] - top[0]) * i / n, top[1] + (vertex[1] - top[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (bot[0] - vertex[0]) * i / n, vertex[1] + (bot[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _brace(w, h):
    """The matrix's bottom curly brace as ONE variable-width ribbon computed from
    the width: long horizontal arms (THICK) sweeping from upturned end-serifs
    (THIN) into a central downward cusp (a THIN near-point). The main (arm) stroke
    runs through the vertical CENTRE of the box, with the end-serifs rising and the
    cusp dipping by the SAME amount, so the brace is balanced about its main stroke
    (not top-heavy). Its depth (the short bounding dimension) matches the value
    brackets' footprint. On a wide span the curls keep a fixed shape and only the
    arm grows; on a narrow span (the per-column braces) the curls shrink together
    so a short arm always survives. One outline, so no seams or overshoot."""
    cx = w / 2
    end_x, serif_dx, cusp_dx = 2.0, 3.2, 5.5
    span = end_x + serif_dx + cusp_dx + 1.0  # the curls plus a reserved minimal arm
    if span > cx:  # too narrow to fit full curls — shrink them together to fit
        s = cx / span
        end_x, serif_dx, cusp_dx = end_x * s, serif_dx * s, cusp_dx * s
    arm_y = h / 2  # the main stroke runs through the box's vertical centre...
    reach = h / 2 - 0.5  # ...with the serifs rising this far above it. The cusp
    # centreline stops a touch short because its pointed tip's fill overshoots
    # downward, so this lands the cusp's fill symmetric to the serif tips — i.e.
    # the arm ends up at the bounding box's exact centre, not above it.
    tip_y, cusp_y = arm_y - reach, arm_y + reach - 0.3
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((end_x, tip_y), (end_x, arm_y), (end_x + serif_dx, arm_y), thin, thick, n)
    pts.append((cx - cusp_dx, arm_y, thick))
    pts += _qbez((cx - cusp_dx, arm_y), (cx, arm_y), (cx, cusp_y), thick, cusp, n, skip_first=True)
    pts += _qbez((cx, cusp_y), (cx, arm_y), (cx + cusp_dx, arm_y), cusp, thick, n, skip_first=True)
    pts.append((w - end_x - serif_dx, arm_y, thick))
    pts += _qbez((w - end_x - serif_dx, arm_y), (w - end_x, arm_y), (w - end_x, tip_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _curly_bracket(w, h):
    """A left curly brace ``{`` for the generator tuning map's frame (it reads ``{ … ]`` —
    curly open, square close — per the mockup). The matrix brace (:func:`_brace`) turned a
    quarter-turn: ONE variable-width ribbon with a vertical spine, the two ends curling
    toward the value cells (thin tips) and a central cusp poking to the far edge (a thin
    near-point). Shares the value brackets' oblong footprint, so the cusp sits where a ``⟨``
    vertex would. The curls keep a fixed shape; only the spine grows with the cell height."""
    cy = h / 2
    end_y, serif_dy, cusp_dy = 2.0, 3.2, 5.5
    span = end_y + serif_dy + cusp_dy + 1.0  # the curls plus a reserved minimal spine
    if span > cy:  # too short to fit full curls — shrink them together to fit
        s = cy / span
        end_y, serif_dy, cusp_dy = end_y * s, serif_dy * s, cusp_dy * s
    tip_x = w - _BR_INSET  # the end-tips curl in toward the value cells
    cusp_x = tip_x - _BR_SERIF_L  # the cusp pokes to the far edge (width matches the ⟨ reach)
    arm_x = (tip_x + cusp_x) / 2  # the spine runs midway between
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((tip_x, end_y), (arm_x, end_y), (arm_x, end_y + serif_dy), thin, thick, n)
    pts.append((arm_x, cy - cusp_dy, thick))
    pts += _qbez((arm_x, cy - cusp_dy), (arm_x, cy), (cusp_x, cy), thick, cusp, n, skip_first=True)
    pts += _qbez((cusp_x, cy), (arm_x, cy), (arm_x, cy + cusp_dy), cusp, thick, n, skip_first=True)
    pts.append((arm_x, h - end_y - serif_dy, thick))
    pts += _qbez((arm_x, h - end_y - serif_dy), (arm_x, h - end_y), (tip_x, h - end_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _angle_foot(w, h):
    """The ket's ``⟩`` turned a quarter-turn to close a raw (untempered) vector column:
    a shallow downward chevron from the top corners to a centre vertex, the calligraphic
    weight of the ⟨ angle bracket (heavier at the vertex than the open tips). A vector
    thus reads ``[ … ⟩`` down its column — square top, angle foot — telling it apart
    from a tempered column, which closes with the curly brace (:func:`_brace`)."""
    cx = w / 2
    # the vertex's outer (thick) edge must land inside the box, not poke past it, so
    # the chevron's footprint matches the other marks' shared short dimension — hence
    # the vertex centreline sits a thick-half-width-plus-margin up from the bottom
    ty, vy = 0.85, h - 0.5 - _BR_ANGLE_THICK
    left, vertex, right = (0.8, ty), (cx, vy), (w - 0.8, ty)
    n = 8
    pts = [(left[0] + (vertex[0] - left[0]) * i / n, left[1] + (vertex[1] - left[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (right[0] - vertex[0]) * i / n, vertex[1] + (right[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _vbar(w, h):
    """A vertical rule between the mapped list's vector columns, the bar's weight."""
    return _svg(w, h, _rect((w - _BR_BAR) / 2, 0, _BR_BAR, h))


def _ebk_svg(cb):
    """The SVG for one EBK cell, generated from its current px box (cb.w, cb.h). A
    pending comma's marks are recoloured red to match its draft cells."""
    if cb.kind == "bracket":
        if cb.text == "⟨":
            svg = _angle_bracket(cb.w, cb.h)
        elif cb.text == "{":
            svg = _curly_bracket(cb.w, cb.h)
        else:
            svg = _square_bracket(cb.w, cb.h, "left" if cb.text == "[" else "right")
    elif cb.kind == "ebktop":
        svg = _top_bracket(cb.w, cb.h)
    elif cb.kind == "ebkbrace":
        svg = _brace(cb.w, cb.h)
    elif cb.kind == "ebkangle":
        svg = _angle_foot(cb.w, cb.h)
    else:
        svg = _vbar(cb.w, cb.h)  # "vbar"
    return svg.replace(_BR_COLOR, _PENDING_COLOR) if cb.pending else svg


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


# The "example" column of the Show panel: one illustrative sample per toggle, read
# from the mockup's Show legend. Most are a glyph or short string (the maps' bold-
# italic letters, the vectors/matrices' bold-upright ones, the plain captions); the
# few graphical samples (the gridded EBK mark, the chart, the preselect chooser) are
# built below from the same primitives the grid uses.
_EXAMPLE_TEXT: dict[str, str] = {
    "names": "tuning map",
    "symbols": "𝒕",
    "equivalences": "𝒕 = 𝒈𝑀",
    "plain_text_values": "[ ⟨12 19 24] }",
    "units": "𝐩",
    "math_expressions": "log₂3",
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


def _example_grid() -> str:
    """The gridded-values sample: the ⟨12 19 24] EBK mark (angle bracket, three
    boxed components, closing bracket) framed by the matrix top-bracket and brace —
    the same hand-drawn marks the grid uses, shrunk to a legend sample."""
    def box(x, text):
        return (f'<div style="position:absolute;left:{x}px;top:11px;width:22px;height:20px;'
                'border:1px solid #000;background:#fff;display:flex;align-items:center;'
                f'justify-content:center;font-size:11px">{text}</div>')

    def mark(x, y, w, h, svg):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">{svg}</div>'

    return ('<div style="position:relative;width:90px;height:42px">'
            + mark(11, 2, 66, 6, _top_bracket(66, 6))
            + mark(0, 11, 10, 20, _angle_bracket(10, 20))
            + box(12, "12") + box(33, "19") + box(54, "24")
            + mark(78, 11, 10, 20, _square_bracket(10, 20, "right"))
            + mark(11, 34, 66, 6, _brace(66, 6))
            + '</div>')


def _example_chart() -> str:
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with a bar
    dipping below the zero line, as the mockup's legend shows."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            '<line x1="2" y1="3" x2="2" y2="31" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="5" x2="6" y2="5" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="29" x2="6" y2="29" stroke="#000" stroke-width="1.4"/>'
            '<line x1="2" y1="17" x2="62" y2="17" stroke="#000" stroke-width="1"/>'
            '<rect x="16" y="17" width="22" height="6" fill="#000"/>'
            '</svg></div>')


def _example_preselect() -> str:
    """The preselects sample: the chooser as a bordered field with a caret box."""
    return ('<span style="display:inline-flex;align-items:stretch;font-size:10px">'
            '<span style="border:1px solid #000;border-right:none;padding:2px 6px;'
            'color:#555">&lt;choose form&gt;</span>'
            '<span style="border:1px solid #000;padding:2px 4px;display:flex;'
            'align-items:center">▼</span></span>')


def _example_html(key: str) -> str:
    """The example-column sample for one Show toggle, as an HTML string."""
    if key == "gridded_values":
        return _example_grid()
    if key == "charts":
        return _example_chart()
    if key == "preselects":
        return _example_preselect()
    if key == "mnemonics":  # the underlined mnemonic letters. Wrap in one element: the
        # example cell is a flex box, which would split the words into separate items and
        # trim the space between them — every branch here must return a single root element.
        return f'<span class="rtt-ex">{_underline_html("canonical mapping", ((0, 1), (10, 1)))}</span>'
    if key == "quantities":  # a generic quantity over its size: 1 above .585
        return ('<span style="display:inline-flex;flex-direction:column;align-items:center;'
                'line-height:1.05"><span>1</span><span style="font-size:9px">.585</span></span>')
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


# The "general" Show group, composed into a single clickable dummy tile — the panel's
# alternative to a column of checkboxes. Each line stacks one (or, for a sub-control, its
# parent + the sub-control) of the layers a real value tile carries, top to bottom roughly as
# a decorated tile reads: the symbol glyph, the name caption, the units line, then the value's
# representations and adornments. Every part is a dummy sample (reusing the example-legend
# renders) shown black when its toggle is on and grey when off; clicking it flips the toggle in
# the live grid. Keys within a line are in left-to-right render order, so a sub-control sits next
# to its parent exactly where it reads: equivalences as the "= 𝒈M" tail AFTER the symbol 𝒕, the
# mnemonic letter BEFORE the rest of the name (it underlines the name's leading symbol letter).
_GENERAL_TILE_LINES: tuple[tuple[str, ...], ...] = (
    ("symbols", "equivalences"),
    ("mnemonics", "names"),
    ("units",),
    ("gridded_values",),
    ("plain_text_values",),
    ("math_expressions",),
    ("quantities",),
    ("charts",),
    ("preselects",),
)

# The symbols layer's sample is the bare covector 𝒕; the equivalences layer extends it to the
# defining equation 𝒕 = 𝒈M (the example-legend text). The dummy tile makes each its own click
# target, so the equivalence part is just that equation's tail (everything after the symbol).
_EQUIV_TAIL = _EXAMPLE_TEXT["equivalences"][len(_EXAMPLE_TEXT["symbols"]):]

# The name caption sample, split so the mnemonic letter — the one the mnemonics underline marks,
# here the 't' that spells the symbol 𝒕 — is its own click target, distinct from the rest of the
# name word (the names target). Re-joined they are exactly the names sample.
_NAME_LETTER, _NAME_REST = _EXAMPLE_TEXT["names"][:1], _EXAMPLE_TEXT["names"][1:]


def _general_part_html(key: str) -> str:
    """The dummy sample for one part of the general tile. Symbols and equivalences split the
    'symbols' equation 𝒕 = 𝒈M into the bare covector and its '= 𝒈M' tail; mnemonics and names
    split the name word into its leading symbol letter and the rest — each half a click target.
    Every other layer reuses its example-legend render, so the tile and the legend stay one
    source of truth."""
    if key == "symbols":
        return _math_html(_EXAMPLE_TEXT["symbols"])
    if key == "equivalences":
        return _math_html(_EQUIV_TAIL)
    if key == "mnemonics":
        return _escape(_NAME_LETTER)
    if key == "names":
        return _escape(_NAME_REST)
    return _example_html(key)


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
    """Shared Quasar props for every chooser dropdown (preselect / target / form / control
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
    """Show a "-" prompt in a preselect chooser's closed box when its current state matches
    no named entry (``value`` is None) — the temperament chooser with no matching preset, or
    the tuning chooser on a control-refined scheme with no name. It is a Quasar display-value
    placeholder, so "-" never appears as a pickable row in the open list; when a named entry
    matches, the override is cleared and Quasar shows its label."""
    if value is None:
        select.props('display-value="-"')
    else:
        select.props(remove="display-value")


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    # the audio rows' Web Audio engine + its glyph variants (shared markup for click redraws)
    ui.add_body_html(f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>")
    # keep the frozen title bands pinned to the scrolling grid pane (see _FREEZE_JS)
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
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
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # mapping cell id -> q-input
    labels: dict = {}  # cell id -> the label whose text tracks state
    fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
    cents: dict = {}  # cents cell id -> (whole label, fraction label), aligned on the point
    htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
    ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
    chart_keys: dict = {}  # chart cell id -> last (w, h, values) drawn, to redraw on resize/data change
    range_keys: dict = {}  # range-chart cell id -> last (w, h, ranges) drawn, to redraw on resize/data change
    audio_keys: dict = {}  # speaker/arp/chord cell id -> last cents tuple, to rebuild its click handler on change
    exprs: dict = {}  # math-expression cell id -> the ui.html holding its stacked lines
    expr_state: dict = {}  # math-expression cell id -> last (text, w) rendered, to redraw on change
    kinds: dict = {}  # entity id -> the kind its element was built for (rebuild when it changes)
    selects: dict = {}  # preselect cell id -> its q-select
    checks: dict = {}  # control_check cell id -> its q-checkbox (the box-𝐋 "replace diminuator")
    ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
    rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
    opt_buttons: dict = {}  # optimize-button cell id -> its ui.button (for the auto-lock visual)
    captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
    caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
    math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
    math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
    cell_units: dict = {}  # value cell id -> the ui.html holding its per-cell unit (the units toggle)
    cell_unit_text: dict = {}  # ...and its last unit string, to rewrite on a units toggle / value change
    building = [False]
    last_lay = [None]  # the most recently built layout, so the master toggle can read its foldable bands
    refs: dict = {}

    def drop(eid):
        """Remove an entity's element and forget every per-id handle for it."""
        els[eid].delete()
        for d in (els, inputs, labels, fracs, cents, htmls, ebk_sizes, exprs, expr_state, kinds,
                  selects, ptext_inputs, captions, caption_html, math_cells, math_rendered,
                  cell_units, cell_unit_text, chart_keys, range_keys, audio_keys, rangeopts,
                  opt_buttons):
            d.pop(eid, None)

    def set_cents_face(cid, text):
        """Sync a cents cell's stacked face: the whole part over the dot-led fraction (the
        fraction blank when the value is an integer or the cell is blanked). Shared by the
        read-only tval cells and the editable cents cells (whose face overlays their input)."""
        whole, frac = _cents_parts(text)
        cents[cid][0].set_text(whole)
        cents[cid][1].set_text(f".{frac}" if frac else "")

    def on_mapping_change():
        if building[0] or not editor.settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
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
            if any(f"cell:comma:{p}:{nc}" not in inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_comma([_parse_int(inputs[f"cell:comma:{p}:{nc}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:comma:{p}:{c}" not in inputs for c in range(nc) for p in range(d)):
            return  # the comma cells aren't currently shown (folded away)
        # the comma cells are the basis transposed (prime down the rows, comma across)
        basis = [[_parse_int(inputs[f"cell:comma:{p}:{c}"].value) for p in range(d)] for c in range(nc)]
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
        if any(f"cell:interest:{p}:{i}" not in inputs for i in range(mi) for p in range(d)):
            return  # the interest cells aren't currently shown (folded away)
        vectors = [[_parse_int(inputs[f"cell:interest:{p}:{i}"].value) for p in range(d)] for i in range(mi)]
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
        if any(f"cell:held:{p}:{i}" not in inputs for i in range(nh) for p in range(d)):
            return  # the held cells aren't currently shown (folded away / optimization off)
        vectors = [[_parse_int(inputs[f"cell:held:{p}:{i}"].value) for p in range(d)] for i in range(nh)]
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
        if any(f"cell:vec:targets:{j}:{p}" not in inputs for j in range(k) for p in range(d)):
            return  # the target cells aren't currently shown (folded away)
        vectors = [[_parse_int(inputs[f"cell:vec:targets:{j}:{p}"].value) for p in range(d)] for j in range(k)]
        if any(v is None for m in vectors for v in m):
            return
        editor.set_target_override_vectors(vectors)
        render()

    def on_power_change(cid):
        # editable power inputs share this kind. optimization:power drives the Lp optimization
        # power; control:q (the complexity norm power in box 𝒄) is styling-only for now, so we
        # accept the keystroke but don't yet wire it through to the scheme.
        if building[0] or cid not in inputs:
            return
        if cid != "optimization:power":
            return  # control:q: white-box look, no behaviour yet (wiring later)
        raw = str(inputs[cid].value).strip().lower()
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
        if building[0] or cid not in inputs:
            return
        try:
            cents = float(str(inputs[cid].value).strip())
        except ValueError:
            return
        editor.set_generator_tuning_component(int(cid.rsplit(":", 1)[1]), cents)
        render()

    def on_prescaler_change(cid):
        # a bare prescaler 𝐿 diagonal cell (cid "cell:prescaling:primes:i:i"): a valid float
        # overrides that one diagonal entry (which then drives EVERY downstream consumer — the
        # product tiles, complexity, weights, the tuning solve and its retunings/damages).
        # The first edit seeds the override from the scheme so the d-1 untouched cells keep
        # their displayed values (set_custom_prescaler_entry handles that). The bare prescaler
        # is a float diagonal (log_prime / prime / identity / typed), so parse as float — an
        # unparseable entry leaves the scheme unchanged, like the other editable cells.
        if building[0] or cid not in inputs:
            return
        try:
            value = float(str(inputs[cid].value).strip())
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
            ptext_inputs[cid].classes(remove="rtt-ptext-error")
            render()
        else:
            ptext_inputs[cid].classes(add="rtt-ptext-error")

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
        # a click on one part of the general dummy tile flips that layer's toggle (the tile is
        # the checkbox column's alternative). A sub-control is inert until its parent is shown —
        # mnemonics needs a name to underline, equivalences a symbol to expand — so a click on it
        # while the parent is off does nothing (the CSS also makes it unclickable; this guards the
        # state too). render() then re-styles the tile and animates the grid.
        if building[0]:
            return
        parent = show_settings.SUBCONTROLS.get(key)
        if parent is not None and not editor.settings[parent]:
            return
        editor.set_show(key, not editor.settings[key])
        render()

    def on_preselect(name, value):
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
        num, sel = selects["preselect:target"]
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
        # the alt.-complexity choosers (box 𝐋 prescaler, box 𝒄 complexity norm, box 𝒘 weight
        # slope): each swaps a scheme trait, re-weighting and retuning. The re-render echo is
        # ignored via the guards.
        if building[0] or value is None:
            return
        if cid == "control:prescaler":
            editor.set_complexity_prescaler(value)
        elif cid == "control:norm":
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
        # mirroring editor.range_mode) is ignored via the building/None guards, like the preselects.
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

    def _ratio(cb, approx):
        """A ratio rendered as a stacked fraction (with a ~ prefix when approximate)."""
        parts = _ratio_parts(cb.text)
        with ui.element("div").classes("rtt-ratio"):
            if approx:
                ui.label("~").classes("rtt-approx")
            if parts:
                with ui.element("div").classes("rtt-frac"):
                    num = ui.label(parts[0]).classes("rtt-frac-num")
                    den = ui.label(parts[1]).classes("rtt-frac-den")
                fracs[cb.id] = (num, den)
            else:
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")

    def _make_cell(cb):
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)

        def cents_face(cls):
            """Build the stacked int-over-fraction cents face (the read-only tval look: the
            whole part big over a smaller dot-led fraction) and register its labels so render()
            keeps them synced. Shared by the read-only tval cell and the editable cents cells —
            the latter pass the overlay class and lay it over their input."""
            whole, frac = _cents_parts(cb.text)
            with ui.element("div").classes(cls):
                w = ui.label(whole).classes("rtt-cents-int")
                f = ui.label(f".{frac}" if frac else "").classes("rtt-cents-frac")
            cents[cb.id] = (w, f)

        with wrap:
            if cb.kind == "mapping":
                wrap.classes("rtt-cell-input")  # a per-cell unit overlays inside the input box
                inputs[cb.id] = ui.input(on_change=lambda e: on_mapping_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "commacell":
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_comma_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "interestcell":  # an editable interval of interest vector component
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_interest_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "heldcell":  # an editable held interval vector component (constrains the tuning)
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_held_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "targetcell":  # an editable target interval list vector component (overrides the set)
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_target_cells_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prescalercell":  # a bare prescaler 𝐿 diagonal cell, the user's editable
                # override (off-diagonal cells stay tval "0" — 𝐿 is diagonal). Each input dispatches
                # to set_custom_prescaler_entry; the cid carries the diagonal slot, so the lambda
                # closes over it (a free cb would be the LAST cell's id by the time the user types)
                wrap.classes("rtt-cell-input rtt-cell-stacked")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_prescaler_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
                cents_face("rtt-tval rtt-cellface")  # the stacked face overlaid on the input
            elif cb.kind in ("prime", "formcell"):  # a read-only bordered cell (domain prime / form-matrix entry)
                with ui.element("div").classes("rtt-white"):
                    labels[cb.id] = ui.label(cb.text)
            elif cb.kind == "genratio":
                _ratio(cb, approx=True)
            elif cb.kind == "commaratio" and cb.pending:  # the draft comma's "?" quantity, red
                labels[cb.id] = ui.label(cb.text).classes("rtt-val rtt-pending-q")
            elif cb.kind in ("target", "commaratio"):
                _ratio(cb, approx=False)
            elif cb.kind in ("mapped", "vec"):  # plain integer values (mapped lists, vector components)
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")
            elif cb.kind == "count":  # a scalar "symbol = value" (the counts row's 𝑑 = 3 etc.)
                math_cells[cb.id] = ui.html("").classes("rtt-count")  # content set in render()
            elif cb.kind in _EBK_SVG_KINDS:  # ⟨ ] [, top bracket, brace, vector rule
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in render() from its px box
            elif cb.kind == "chart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # bar chart drawn in render()
            elif cb.kind == "rangechart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # I-beam ranges chart drawn in render()
            elif cb.kind == "rangemode":  # the monotone/tradeoff range selector under the ranges chart
                wrap.classes("rtt-rangemode")  # two square indicators side by side (the mockup style)
                opts = {}
                for mode in ("monotone", "tradeoff"):
                    opt = ui.element("div").classes("rtt-rangeopt")
                    with opt:
                        ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                        ui.label(mode).classes("rtt-rangelabel")
                    opt.on("click", lambda _=None, m=mode: on_range_mode(m))
                    opts[mode] = opt
                rangeopts[cb.id] = opts
            elif cb.kind == "symbol":
                wrap.classes("rtt-symbol-cell")
                # the optimization box's symbols (⟪𝐝⟫ₚ, 𝑝) stay on one line (ₚ never wraps off)
                cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
                math_cells[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "matlabel":  # per-row / per-column matrix label (𝒎ᵢ, 𝐜ᵢ, 𝒕ᵢ, …):
                # routed through _math_html so its bold-italic / bold-upright glyphs draw in
                # the same styled face as the tile symbol it indexes. The complexity row's
                # labels are longer (‖L𝐜ᵢ‖q) so they use a smaller variant to avoid colliding
                cls = "rtt-matlabel rtt-matlabel-norm" if "‖" in cb.text else "rtt-matlabel"
                wrap.classes("rtt-matlabel-cell")
                math_cells[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "units":  # the per-box units line and the domain-units row/col labels
                wrap.classes("rtt-units-cell")
                math_cells[cb.id] = ui.html("").classes("rtt-units")  # content set in render()
            elif cb.kind == "caption":
                wrap.classes("rtt-caption-cell")
                # the optimization box's captions stay on one line (no wrap), unlike tile names.
                # a caption with align="left" reads left-justified under its control (e.g. the
                # box-𝐋 "predefined prescalers" label sitting under the prescaler dropdown)
                cls = "rtt-caption rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-caption"
                if cb.align == "left":
                    cls += " rtt-caption-left"
                captions[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "preselect":
                name = cb.id.split(":")[1]  # temperament / tuning / target (a copy adds a :col suffix)
                if name == "target":
                    # a numeric limit override beside the TILT/OLD family select, seeded
                    # from the editor's live target family + (optional) manual limit
                    with ui.element("div").classes("rtt-preselect-target"):
                        num = ui.number(value=editor.target_limit, min=2,
                                on_change=lambda e: on_target_change()) \
                            .props("dense borderless hide-bottom-space").classes("rtt-preselect-num")
                        sel = ui.select(list(presets.TARGET_SETS), value=editor.target_family,
                                on_change=lambda e: on_target_change()) \
                            .props(_select_props(cb.w - 30)).classes("rtt-preselect")  # field = cell − the 30px square (touching, no gap)
                    selects[cb.id] = (num, sel)
                elif name == "temperament":
                    # a normal dropdown listing only the prime-limit dividers and their
                    # presets (grouped in the open list). The chosen preset shows in the
                    # box; when none matches, a "-" prompt shows there as a display-value
                    # placeholder — never a pickable row in the list.
                    value = presets.identify(editor.state)
                    sel = _GroupedSelect(presets.temperament_options(), value=value,
                            is_divider=presets.is_divider,
                            on_change=lambda e: on_preselect("temperament", e.value)) \
                        .props(_select_props(cb.w)).classes("rtt-preselect")
                    _set_offlist_prompt(sel, value)
                    selects[cb.id] = sel
                else:  # tuning — systematic scheme names, T-prefixed when targeting a list (not all-
                    # interval); a control-refined scheme has no name, shown as the "-" placeholder.
                    # Alternative-complexity schemes are gated behind the alt. complexity setting.
                    options = presets.tuning_scheme_options(
                        service.is_all_interval(editor.tuning_scheme), editor.settings["alt_complexity"])
                    # "-" when the displayed tuning is off the named list — a refined spec, or a
                    # manual override deviating from the scheme's optimum; else the offered name
                    name = editor.displayed_tuning_scheme_name
                    scheme = name if name in options else None
                    sel = ui.select(options, value=scheme,
                            on_change=lambda e: on_preselect("tuning", e.value)) \
                        .props(_select_props(cb.w)).classes("rtt-preselect")
                    _set_offlist_prompt(sel, scheme)
                    selects[cb.id] = sel
            elif cb.kind == "control_select":  # an alt.-complexity chooser (prescaler / norm / weight slope)
                selects[cb.id] = ui.select(list(cb.values), value=cb.text or None,
                        on_change=lambda e, cid=cb.id: on_control_select(cid, e.value)) \
                    .props(_select_props(cb.w)).classes("rtt-preselect")
            elif cb.kind == "control_check":  # the box-𝐋 "replace diminuator" checkbox (size factor)
                checks[cb.id] = ui.checkbox(cb.text, value=cb.checked,
                        on_change=lambda e, cid=cb.id: on_control_select(cid, e.value)) \
                    .props("dense").classes("rtt-control-check")
            elif cb.kind == "formchooser":  # the <choose form> control: canonicalizes its matrix on select
                name = cb.id.split(":", 1)[1]  # mapping / comma_basis
                selects[cb.id] = ui.select({"": "choose form", "canonical": "canonical"}, value="",
                        on_change=lambda e, n=name: on_form_choose(n, e.value)) \
                    .props(_select_props(cb.w)).classes("rtt-preselect")
            elif cb.kind == "ptext":  # a read-only value: plain wrapping text, no box
                labels[cb.id] = ui.label(cb.text).classes("rtt-ptext")
            elif cb.kind == "ptextedit":  # an editable dual: typing a valid EBK string drives the grid
                ptext_inputs[cb.id] = ui.input(value=cb.text,
                        on_change=lambda e, cid=cb.id: on_ptext_edit(cid, e.value)) \
                    .props("dense borderless").classes("rtt-ptextedit")
            elif cb.kind == "ptextpending":  # comma basis mid-draft: a static two-tone box (the
                # draft is typed into the red grid cells, not here), content set in render()
                htmls[cb.id] = ui.html("").classes("rtt-ptextpending")
            elif cb.kind == "tval":
                cents_face("rtt-tval")
            elif cb.kind == "mathexpr":  # a just value's stacked closed form, fit to the cell
                exprs[cb.id] = ui.html("").classes("rtt-mathexpr")  # content drawn in render()
            elif cb.kind == "colheader":
                labels[cb.id] = ui.label(cb.text).classes("rtt-colheader")
            elif cb.kind == "rowlabel":
                labels[cb.id] = ui.label(cb.text).classes("rtt-rowlabel")
            elif cb.kind in ("rowtoggle", "coltoggle", "tiletoggle"):
                item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets" / "tile:mapping:primes"
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None, it=item: on_toggle(it))
            elif cb.kind == "alltoggle":  # the master expand/collapse-all control in the node corner
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None: on_toggle_all())
            elif cb.kind == "minus":
                # the zone spans the removable prime's header (the hover target); the
                # button hides at its top and reveals on hover, above the header so it
                # never covers the editable mapping cell below
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "basis_minus":
                # the domain − for the vertical basis: a hover zone over the highest
                # prime revealing the − to its right, so it never covers the box
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn-v")
            elif cb.kind == "comma_minus":
                # the same hover affordance as the domain −, but on the last comma
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.remove_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "comma_plus":
                ui.button("+", on_click=lambda: act(editor.add_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "interest_minus":
                # one per interval (every interval of interest is removable); the hover
                # zone over its header reveals a − that drops just that interval
                i = int(cb.id.split(":", 1)[1])
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda _=None, idx=i: act(lambda: editor.remove_interest(idx)), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "interest_plus":
                ui.button("+", on_click=lambda: act(editor.add_interest), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "held_minus":  # one per held interval; its − drops just that one
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda _=None, idx=cb.comma: act(lambda: editor.remove_held(idx)), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "held_plus":
                ui.button("+", on_click=lambda: act(editor.add_held), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "optimize":
                # single click optimizes once (freeze at the optimum); double click toggles
                # the auto-optimize lock. A double-click also fires its two single clicks, but
                # optimize() is idempotent, so a double-click's net effect is the lock toggle.
                opt_buttons[cb.id] = ui.button(cb.text, on_click=lambda: act(editor.optimize), color=None) \
                    .props("unelevated dense no-caps").classes("rtt-btn rtt-optimize")
                opt_buttons[cb.id].on("dblclick", lambda: act(editor.toggle_optimize_lock))
            elif cb.kind == "boxtitle":  # an in-tile box title (e.g. "optimization")
                labels[cb.id] = ui.label(cb.text).classes("rtt-boxtitle")
            elif cb.kind == "powerinput":  # an editable cell-input number (the optimization power
                # 𝑝, or the box-𝒄 norm power 𝑞). The symbol label rides as a separate cell
                # below; the field itself shows only the value, in the bordered cell-input box.
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_power_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "gentuningcell":  # an editable generator-tuning-map cell (per-generator override)
                wrap.classes("rtt-cell-input rtt-cell-stacked")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_gentuning_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
                cents_face("rtt-tval rtt-cellface")  # the stacked face overlaid on the input
            elif cb.kind == "speaker":  # play this pitch per its tile's mode (client-side engine)
                tile = cb.text  # the tile key "<row>:<group>", shared with the tile's control bank
                idx = int(cb.id.rsplit(":", 1)[1])
                pitches = ",".join(f"{float(v):.6f}" for v in cb.values)  # the whole tile (for arp/chord)
                # color=None drops Quasar's default primary (blue): the app is greyscale,
                # leaving colour to the yellow/cyan/magenta colorization. .rtt-spk + the data
                # attrs let the engine highlight this speaker while it sounds.
                ui.button(icon="volume_up", color=None) \
                    .props(f'flat dense round data-audio="{tile}" data-idx="{idx}"') \
                    .classes("rtt-audio-btn rtt-spk") \
                    .on("click", js_handler=f"() => window.rttAudio.hit('{tile}', {idx}, [{pitches}])")
            elif cb.kind in _AUDIO_CTRLS:  # a bank control: cycles its state + glyph client-side
                tile = cb.id.split(":", 1)[1]      # "<row>:<group>"
                ctrl = cb.kind.split("_", 1)[1]     # wave | mode | hold | root
                glyph = {"wave": _AUDIO_GLYPHS["wave"][0], "mode": _AUDIO_GLYPHS["mode"][0],
                         "hold": _AUDIO_GLYPHS["lock"][0], "root": _AUDIO_GLYPHS["root"]}[ctrl]
                fn = {"wave": "cycleWave", "mode": "cycleMode",
                      "hold": "toggleHold", "root": "toggleRoot"}[ctrl]
                ui.html(glyph).classes("rtt-audio-ctrl") \
                    .props(f'data-audio="{tile}" data-actrl="{ctrl}"') \
                    .on("click", js_handler=f"() => window.rttAudio.{fn}('{tile}')")
        # explanatory hover text for the interactive controls (read-only value cells get none).
        # The mark/data-eid ride the wrap, so the tooltip hangs off it too — one shared anchor.
        help_text = tooltips.control_help(cb.kind, cb.id)
        if help_text:
            wrap.tooltip(help_text)
        return wrap

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

        for ln in lay.lines:
            seen.add(ln.id)
            if ln.id not in els:
                with board:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    els[ln.id] = ui.element("div").classes(cls).props(f'data-eid="{ln.id}"')
            els[ln.id].style(_line_style(ln, fy))

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in els:
                # a block is a thin-bordered box (boxed, the nested tuning-ranges frame), a
                # plain grey tile (tint ""), a colorization wash's white base (tint "base"),
                # or its coloured layer (tint = group name). Fixed for the block's lifetime,
                # so the class is chosen once.
                with board:
                    cls = ("rtt-block-boxed" if bl.boxed
                           else "rtt-washbase" if bl.tint == "base"
                           else "rtt-wash" if bl.tint else "rtt-block")
                    els[bl.id] = ui.element("div").classes(cls).props(f'data-eid="{bl.id}"')
            style = f"left:{bl.x}px; top:{bl.y - fy}px; width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:  # the coloured layer (the base draws white from CSS)
                style += f"; background:{_TINTS[bl.tint]}"
            els[bl.id].style(style)

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id in els and kinds[cb.id] != cb.kind:
                drop(cb.id)  # a cell changed kind (e.g. cents <-> math expression): rebuild it
            if cb.kind in _AUDIO_KINDS and cb.id in els and audio_keys.get(cb.id) != cb.values:
                drop(cb.id)  # cents changed -> rebuild so the baked-in click handler sounds the new pitch
            container = _FREEZE_CONTAINER.get(cb.kind, "body")
            if cb.id not in els:
                with cell_parents[container]:
                    els[cb.id] = _make_cell(cb)
                kinds[cb.id] = cb.kind
                if cb.kind in _AUDIO_KINDS:
                    audio_keys[cb.id] = cb.values
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner
            top = cb.y - (fy if container in ("body", "row") else 0)
            els[cb.id].style(f"left:{cb.x}px; top:{top}px; width:{cb.w}px; height:{cb.h}px")
            if cb.kind in _EBK_SVG_KINDS:
                # the mark is drawn 1:1 to its px box, so redraw it whenever the box
                # changes size (e.g. the brace/top bracket as the domain grows) or its
                # pending (red) state flips (a draft comma's marks committing to black)
                if ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
                    htmls[cb.id].set_content(_ebk_svg(cb))
                    ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)
            elif cb.kind == "chart":
                # redraw when the box resizes OR the underlying data / indicator changes
                key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
                if chart_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(
                        _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label))
                    chart_keys[cb.id] = key
            elif cb.kind == "rangechart":
                # redraw when the box resizes OR the ranges/live tuning change (mapping/mode edit)
                key = (cb.w, cb.h, cb.ranges, cb.values)
                if range_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values))
                    range_keys[cb.id] = key
            elif cb.kind == "rangemode":  # fill the live mode's square (the other's is hollow)
                for mode, opt in rangeopts[cb.id].items():
                    (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
                     else opt.classes(remove="rtt-rangeopt-on"))
            elif cb.kind == "optimize":  # mark the button when its auto-optimize lock is on
                (opt_buttons[cb.id].classes(add="rtt-optimize-locked") if editor.optimize_locked
                 else opt_buttons[cb.id].classes(remove="rtt-optimize-locked"))
            elif cb.kind == "powerinput":  # reflect the live optimization power (∞ / 2 / 1)
                inputs[cb.id].value = cb.text
            elif cb.kind == "gentuningcell":  # reflect the live generator tuning (blank when quantities off)
                text = "" if cb.blank else cb.text
                inputs[cb.id].value = text
                set_cents_face(cb.id, text)  # the overlaid stacked face mirrors the input
            elif cb.kind == "mapping":
                inputs[cb.id].value = "" if cb.blank else str(st.mapping[cb.gen][cb.prime])
            elif cb.kind == "commacell":
                if cb.pending:  # the draft column: show the typed component (blank if None), red-outlined
                    v = editor.pending_comma[cb.prime] if editor.pending_comma is not None else None
                    inputs[cb.id].value = "" if v is None else str(v)
                else:
                    inputs[cb.id].value = "" if cb.blank else str(st.comma_basis[cb.comma][cb.prime])
                inputs[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                      remove="" if cb.pending else "rtt-pending")
            elif cb.kind == "interestcell":
                inputs[cb.id].value = cb.text  # the normalized vector component build computed
            elif cb.kind == "heldcell":
                inputs[cb.id].value = cb.text  # the normalized held vector component build computed
            elif cb.kind == "targetcell":
                inputs[cb.id].value = cb.text  # the target vector component build computed (blank when quantities off)
            elif cb.kind == "prescalercell":  # reflect the live prescaler diagonal (the override if set,
                # else the scheme-derived value — spreadsheet.build resolves that and emits the final
                # text already). Blank when quantities are off, mirroring the other editable matrix cells
                inputs[cb.id].value = cb.text
                set_cents_face(cb.id, cb.text)  # the overlaid stacked face mirrors the input
            elif cb.kind == "ptext":  # read-only value: keep its text and shrink-to-fit font in sync
                labels[cb.id].set_text(cb.text)
                labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextedit":  # reflect the canonical string + its shrink-to-fit font
                ptext_inputs[cb.id].value = cb.text
                ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextpending":  # comma basis with a draft comma: two-tone, the
                # committed commas black and the draft vector red (same red as its grid cells)
                prefix, draft, suffix = service.comma_basis_pending_text(st.comma_basis, editor.pending_comma)
                htmls[cb.id].set_content(
                    f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
                htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            elif cb.kind == "mathexpr":
                # redraw (with refit fonts) whenever the expression text or cell width changes
                if expr_state.get(cb.id) != (cb.text, cb.w):
                    exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
                    expr_state[cb.id] = (cb.text, cb.w)
            elif cb.id in fracs:
                num, den = _ratio_parts(cb.text) or (cb.text, "")
                fracs[cb.id][0].set_text(num)
                fracs[cb.id][1].set_text(den)
            elif cb.id in cents:  # a read-only cents (tval) cell: split into the stacked face
                set_cents_face(cb.id, cb.text)
            elif cb.kind == "preselect":
                # mirror the live selection: the temperament chooser shows the matched
                # preset (or its placeholder), the target chooser splits into limit +
                # family, the tuning chooser shows its scheme. building[0] guards echoes.
                if cb.id.startswith("preselect:temperament"):  # base + the comma-basis copy
                    value = presets.identify(editor.state)
                    selects[cb.id].value = value
                    _set_offlist_prompt(selects[cb.id], value)
                elif cb.id == "preselect:target":
                    num, sel = selects[cb.id]
                    family = editor.target_family
                    # always show the number in use: the manual limit, or the domain default
                    limit = editor.target_limit
                    num.value = limit if limit is not None else \
                        service.default_target_limit(family, service.standard_primes(editor.state.d))
                    sel.value = family
                else:  # tuning — a refined spec or a deviating manual override shows "-"
                    scheme = editor.displayed_tuning_scheme_name
                    # the option LABELS T-prefix only while target-based, so recompute them as the
                    # all-interval checkbox flips (set once at creation, they would otherwise go stale)
                    options = presets.tuning_scheme_options(
                        service.is_all_interval(editor.tuning_scheme), editor.settings["alt_complexity"])
                    selects[cb.id].set_options(options, value=scheme)
                    _set_offlist_prompt(selects[cb.id], scheme)
            elif cb.kind == "control_select":  # mirror the live alt.-complexity choice
                selects[cb.id].value = cb.text or None
            elif cb.kind == "control_check":  # mirror the live "replace diminuator" state
                checks[cb.id].value = cb.checked
            elif cb.kind == "formchooser":  # a one-shot action: snap back to the placeholder
                selects[cb.id].value = ""
            elif cb.kind in ("symbol", "count", "units", "matlabel"):  # text rendered as HTML:
                # symbols/equivalence tails/counts and matrix row/col labels go through
                # _math_html (styled math glyphs); units use _units_html (a single-story-g
                # sans value, serif label)
                html = _units_html(cb.text) if cb.kind == "units" else _math_html(cb.text)
                if math_rendered.get(cb.id) != html:  # rewrite on a toggle / value change
                    math_cells[cb.id].set_content(html)
                    math_rendered[cb.id] = html
                    if cb.id == "optimization:objective:symbol":
                        # all-interval relabels this to the wide retuning magnitude ‖𝒓𝐿⁻¹‖dual(q);
                        # shrink it (rtt-opt-wide) so it stays centred over its COL_W value
                        wide = "‖" in cb.text
                        math_cells[cb.id].classes(
                            replace="rtt-symbol rtt-opt-1line rtt-opt-wide" if wide
                            else "rtt-symbol rtt-opt-1line")
            elif cb.kind == "caption":
                html = _underline_html(cb.text, cb.underlines)
                if caption_html.get(cb.id) != html:  # rewrite when a mnemonic toggle adds/removes underlines
                    captions[cb.id].set_content(html)
                    caption_html[cb.id] = html
            elif cb.kind in _LABEL_KINDS:
                labels[cb.id].set_text(cb.text)

            # per-cell unit (the `units` toggle): a tiny line at the bottom of the value
            # cell, the value lifted to stay centred. cb.unit is "" unless units is on, so
            # this adds/updates/removes the overlay as the toggle (or the domain) changes.
            if cb.unit:
                if cb.id not in cell_units:
                    with els[cb.id]:
                        cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                    els[cb.id].classes(add="rtt-cell-united")
                if cell_unit_text.get(cb.id) != cb.unit:
                    cell_units[cb.id].set_content(_bold_units(cb.unit))
                    cell_unit_text[cb.id] = cb.unit
            elif cb.id in cell_units:
                cell_units[cb.id].delete()
                cell_units.pop(cb.id, None)
                cell_unit_text.pop(cb.id, None)
                els[cb.id].classes(remove="rtt-cell-united")

        for eid in [e for e in els if e not in seen]:
            drop(eid)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        refs["reset"].set_enabled(editor.can_reset)
        # reflect the document's Show settings into the panel (after undo/redo/reset/
        # select-all/load). building[0] is still True, so these programmatic value writes
        # are swallowed by on_show_toggle/on_select_all rather than re-firing as edits.
        for key, box in boxes.items():
            if box.value != editor.settings[key]:
                box.value = editor.settings[key]
        # the general dummy tile: style each layer's part by its live setting — black + opaque
        # when shown, grey + dimmed when hidden — so the tile both mirrors and drives the grid. A
        # sub-control whose parent is hidden is inert (its click does nothing; the CSS also drops
        # its pointer events). Mnemonics is special: it is an underline ON the name, so its COLOUR
        # tracks the name (its parent) while only the underline tracks mnemonics itself — else a
        # name-shown/mnemonic-hidden state would grey just the one symbol letter mid-word.
        for key, part in tile_parts.items():
            shown = editor.settings["names"] if key == "mnemonics" else editor.settings[key]
            if shown:
                part.classes(add="rtt-part-on", remove="rtt-part-off")
            else:
                part.classes(add="rtt-part-off", remove="rtt-part-on")
            parent = show_settings.SUBCONTROLS.get(key)
            if parent is not None and not editor.settings[parent]:
                part.classes(add="rtt-part-inert")
            else:
                part.classes(remove="rtt-part-inert")
        if editor.settings["mnemonics"]:
            tile_parts["mnemonics"].classes(add="rtt-mnem-underline")
        else:
            tile_parts["mnemonics"].classes(remove="rtt-mnem-underline")
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
                # the frozen header: the select-all/none master + the show/example titles, pinned
                # above the scrolling groups (render() sizes it to the layout's freeze_y, matching
                # the main app's frozen band). Its bottom border is the frozen/scrolling seam.
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
                    with ui.element("div").classes("rtt-show-head"):
                        ui.label("show").classes("rtt-show-title")
                        ui.label("example").classes("rtt-show-examplehdr")
                # the scrolling body: the toggle groups, which scroll under the frozen header when
                # the panel outgrows the window (rather than spilling off the bottom of the screen)
                boxes: dict = {}  # specific-group toggle key -> checkbox, so a sub-control row can bind to its parent
                tile_parts: dict = {}  # general-group layer key -> its clickable dummy-tile part (render() styles these)
                show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
                with show_scroll:
                    for group_name, items in show_settings.SHOW_GROUPS:
                        with ui.element("div").classes("rtt-show-group"):
                            ui.label(group_name).classes("rtt-show-grouptitle")
                            if group_name == "general":
                                # the general layers render as ONE clickable dummy tile rather than a
                                # checkbox column: each part is a sample of that layer (reusing the
                                # example-legend renders), clicked directly to show/hide it. render()
                                # styles every part by the live setting; on_part_click flips it. Each
                                # part keeps the layer's hover help, the same text the checkbox carried.
                                # Keys per line are in render order, so a sub-control sits beside its parent.
                                with ui.element("div").classes("rtt-show-tile"):
                                    for line in _GENERAL_TILE_LINES:
                                        with ui.element("div").classes("rtt-tile-line"):
                                            for key in line:
                                                part = ui.html(_general_part_html(key)) \
                                                    .classes("rtt-tile-part").mark(f"showpart:{key}") \
                                                    .tooltip(tooltips.SHOW_HELP[key])
                                                part.on("click", lambda k=key: on_part_click(k))
                                                tile_parts[key] = part
                                continue
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
    ui.run(title="D&D's RTT App", favicon="https://github.com/DandDsRTT.png",
           reload=True, show=False, port=port, storage_secret=_STORAGE_SECRET,
           uvicorn_reload_excludes=_reload_excludes(worktrees))


if __name__ in {"__main__", "__mp_main__"}:
    main()
