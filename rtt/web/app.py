"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.web.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

import math

from nicegui import ui

from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.editor import Editor

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration

# One weight and colour for every EBK bracket, brace and monzo rule. Each mark is
# drawn as an SVG whose viewBox maps 1:1 to the cell's px size (see _svg), so a
# stroke specified as N px is exactly N px tall AND wide at any span — no scaling.
_BR_COLOR = "#1a1a1a"
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
_BR_BAR = 2  # main bar / monzo-rule / square-bracket bar thickness (px)
_BR_SERIF_T = 1.2  # square + top bracket serif thickness — lighter than the main bar
_BR_SERIF_L = 6  # square + top bracket serif length (how far the foot reaches) — also
# the shared footprint width every value bracket (square AND angle) draws within
_BR_INSET = 2.5  # gap from a bracket's open side to the value cells it hugs
# The ⟨ and the brace are filled ribbons of varying width (see _ribbon): a
# calligraphic pen lays a LONG stroke down THICK and a SHORT one THIN.
_BR_ANGLE_THICK = 1.05  # ⟨ half-width at the vertex (heavier)
_BR_ANGLE_THIN = 0.7  # ⟨ half-width at the open tips (lighter) — a subtle taper
_BR_BRACE_THICK = 1.15  # brace arm half-width: the long horizontal stroke is thick
_BR_BRACE_THIN = 0.55  # brace end-serif half-width: the short upturn is thin
_BR_BRACE_CUSP = 0.3  # brace central-cusp half-width: the short dip is a near point

_CSS = f"""
.rtt-title {{ font-family:'Cambria',Georgia,serif; font-size:30px; font-weight:bold;
             color:#000; margin:6px 0 8px 2px; }}
.rtt-iconbtn {{ width:30px !important; min-width:30px !important; height:30px !important;
            min-height:30px !important; padding:0 !important; box-shadow:none !important; }}
.rtt-iconbtn .q-icon {{ color:#777 !important; font-size:21px; }}
.rtt-iconbtn.q-btn--disable .q-icon {{ color:#c4c4c4 !important; }}

.rtt-scroll {{ overflow-x:auto; max-width:100%; }}
.rtt-outer {{ background:#c0c0c0; padding:{_PAD}px; width:max-content;
              font-family:'Cambria',Georgia,serif; }}
.rtt-board {{ position:relative; transition:width {_T}, height {_T}; }}
@keyframes rtt-in {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.rtt-line, .rtt-block, .rtt-cell {{ animation:rtt-in {_T} ease; }}

.rtt-line {{ position:absolute; z-index:1; opacity:1; transition:left {_T}, top {_T},
            width {_T}, height {_T}, opacity {_T}; }}
.rtt-line-v {{ border-left:1px solid #e0e0e0; width:0; }}
.rtt-line-h {{ border-top:1px solid #e0e0e0; height:0; }}
.rtt-block {{ position:absolute; z-index:2; background:#e0e0e0; opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-cell {{ position:absolute; z-index:3; display:flex; align-items:center; justify-content:center;
            opacity:1; transition:left {_T}, top {_T}, opacity {_T}; }}

.rtt-white {{ position:absolute; top:0; left:0;
             width:calc(100% + {_CELL_BORDER_W}px); height:calc(100% + {_CELL_BORDER_W}px);
             box-sizing:border-box; display:flex; align-items:center; justify-content:center;
             background:#fff; border:{_CELL_BORDER}; color:#000; font-size:{_CELL_FONT}px; }}
.rtt-colheader {{ font-size:13px; font-weight:bold; color:#000; white-space:nowrap; }}
.rtt-rowlabel {{ font-size:13px; font-weight:bold; color:#000; width:100%; text-align:right;
                padding-right:8px; }}
.rtt-val {{ font-size:{_CELL_FONT}px; color:#000; }}
.rtt-caption {{ width:100%; text-align:center; font-size:12px; color:#333; white-space:nowrap;
               font-family:'Cambria',Georgia,serif; }}
/* every EBK mark (⟨ ] [, top bracket, brace, monzo rule) is one SVG that fills
   its cell at a 1:1 viewBox, so its strokes keep a constant px weight at any span */
.rtt-svgfill {{ width:100%; height:100%; line-height:0; }}
/* captions hold off their fade-in until the tile has finished expanding */
.rtt-caption-cell {{ animation-delay:{_T}; animation-fill-mode:backwards; }}
.rtt-ratio {{ display:flex; align-items:center; justify-content:center; gap:1px;
             font-size:13px; color:#000; }}
.rtt-approx {{ font-size:13px; align-self:center; }}
.rtt-frac {{ display:inline-flex; flex-direction:column; align-items:center; line-height:1.04; }}
.rtt-frac-num {{ border-bottom:1px solid #000; padding:0 3px; }}
.rtt-frac-den {{ padding:0 3px; }}
.rtt-tval {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
            width:100%; color:#000; white-space:nowrap; line-height:1.05; }}
.rtt-cents-int {{ font-size:10px; }}
.rtt-cents-frac {{ font-size:7px; color:#000; }}
.rtt-cellinput {{ width:100% !important; height:100%; min-height:0; overflow:visible; }}
.rtt-cellinput .q-field__inner {{ overflow:visible; }}
.rtt-cellinput .q-field__control {{ position:absolute !important; top:0; left:0;
            width:calc(100% + {_CELL_BORDER_W}px) !important; height:calc(100% + {_CELL_BORDER_W}px) !important;
            max-width:none !important; min-height:0 !important;
            box-sizing:border-box; padding:0 !important; background:#fff; border:{_CELL_BORDER}; }}
.rtt-cellinput .q-field__control::before, .rtt-cellinput .q-field__control::after {{ display:none !important; }}
.rtt-cellinput .q-field__native {{ text-align:center; padding:0 !important; color:#000; font-size:{_CELL_FONT}px;
            min-height:0; font-family:'Cambria',Georgia,serif; }}
.rtt-cellinput .q-field__bottom, .rtt-cellinput .q-field__marginal {{ display:none !important; }}
/* the +/− controls are half the 26px mapping/prime cell, with that cell's border colour */
.rtt-btn {{ width:13px !important; min-width:13px !important; height:13px !important;
           min-height:13px !important; background:#fff !important; border:1px solid #c8c8c8 !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }}
/* center the glyph: Quasar's content box defaults to a tall line-height that
   overflowed the small square; pin it to the box so the flex centering can take over */
.rtt-btn .q-btn__content {{ color:#000 !important; font-size:13px; line-height:1; min-height:0;
           font-family:'Cambria',Georgia,serif; }}
/* the domain − is a hover affordance: an invisible zone over the removable prime's
   header reveals the button parked at its top (above the header, clear of inputs). The
   zone sits above the prime cells (z-index) so a column added via + can't paint over it
   and shrink the hover target down to just the button itself. */
.rtt-minus-zone {{ background:transparent; z-index:4; }}
.rtt-minus-btn {{ position:absolute !important; top:0; left:50%; transform:translateX(-50%);
           opacity:0; pointer-events:none; transition:opacity {_T}; }}
.rtt-minus-zone:hover .rtt-minus-btn {{ opacity:1; pointer-events:auto; }}

.rtt-toggle {{ width:100%; height:100%; display:flex; align-items:center; justify-content:center;
              font-size:12px !important; line-height:1; color:#666; background:#fff;
              border:1px solid #bbb; cursor:pointer; user-select:none; }}
.rtt-toggle:hover {{ background:#ececec; color:#000; }}
.rtt-show-card {{ font-family:'Cambria',Georgia,serif; background:#fff; color:#000;
                 min-width:440px; padding:14px 18px; border-radius:0; box-shadow:0 2px 12px #0003; }}
.rtt-show-title {{ font-size:22px; font-weight:bold; margin-bottom:6px; }}
.rtt-show-groups {{ gap:44px; align-items:flex-start; flex-wrap:nowrap; }}
.rtt-show-grouptitle {{ font-size:13px; font-weight:bold; color:#000;
                       margin-bottom:2px; white-space:nowrap; }}
.rtt-show-item .q-checkbox__label {{ font-family:'Cambria',Georgia,serif; font-size:13px; color:#000; }}
"""

_LABEL_KINDS = {"prime", "colheader", "rowlabel", "mapped", "rowtoggle", "coltoggle"}

# Every EBK mark is drawn by hand as an SVG sized to the cell. The viewBox is the
# cell's own px box (0 0 w h), so one viewBox unit == one px: a stroke we declare
# as N px renders exactly N px wide regardless of how tall/long the mark spans.
# This is the single rule that keeps the brackets and brace a constant weight —
# the rejected font glyph scaled its weight with its height, and a fixed viewBox
# stretched to the cell sheared its serifs. Square/top brackets are crisp filled
# rects; the calligraphic ⟨ and brace are filled variable-width ribbons (_ribbon).
_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "vbar"}


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
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.6
    top, vertex, bot = (tx, 0.4), (vx, cy), (tx, h - 0.4)
    n = 10
    pts = [(top[0] + (vertex[0] - top[0]) * i / n, top[1] + (vertex[1] - top[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (bot[0] - vertex[0]) * i / n, vertex[1] + (bot[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _brace(w, h):
    """The matrix's bottom curly brace as ONE variable-width ribbon computed from
    the width: long horizontal arms (THICK) sweeping from upturned end-serifs
    (THIN) into a central downward cusp (a THIN near-point). Its depth (the short
    bounding dimension) matches the value brackets' footprint. On a wide span the
    curls keep a fixed shape and only the arm grows; on a narrow span (the
    per-column braces) the curls shrink together so a short arm always survives.
    One outline, so no seams or overshoot."""
    cx = w / 2
    end_x, serif_dx, cusp_dx = 2.0, 3.2, 5.5
    span = end_x + serif_dx + cusp_dx + 1.0  # the curls plus a reserved minimal arm
    if span > cx:  # too narrow to fit full curls — shrink them together to fit
        s = cx / span
        end_x, serif_dx, cusp_dx = end_x * s, serif_dx * s, cusp_dx * s
    tip_y, arm_y, cusp_y = 0.12 * h, 0.34 * h, 0.95 * h
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


def _vbar(w, h):
    """A vertical rule between the mapped list's monzo columns, the bar's weight."""
    return _svg(w, h, _rect((w - _BR_BAR) / 2, 0, _BR_BAR, h))


def _ebk_svg(cb):
    """The SVG for one EBK cell, generated from its current px box (cb.w, cb.h)."""
    if cb.kind == "bracket":
        if cb.text == "⟨":
            return _angle_bracket(cb.w, cb.h)
        return _square_bracket(cb.w, cb.h, "left" if cb.text == "[" else "right")
    if cb.kind == "ebktop":
        return _top_bracket(cb.w, cb.h)
    if cb.kind == "ebkbrace":
        return _brace(cb.w, cb.h)
    return _vbar(cb.w, cb.h)  # "vbar"


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
    """Split a cents value like ``"1899.26"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    ui.query("body").style("background:#fff")

    editor = Editor()
    settings = show_settings.defaults()  # which parts of the grid are visible
    collapsed: set = set()  # ids of individually folded rows/columns ("row:tuning")
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # mapping cell id -> q-input
    labels: dict = {}  # cell id -> the label whose text tracks state
    fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
    cents: dict = {}  # cents cell id -> (whole label, fraction label), aligned on the point
    htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
    ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
    building = [False]
    refs: dict = {}

    def on_mapping_change():
        if building[0] or not settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            return
        editor.edit_mapping(matrix)
        render()

    def act(action):
        action()
        render()

    def on_show_toggle(key, value):
        settings[key] = value
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def on_toggle(item):  # fold/unfold one row or column ("row:tuning", "col:targets")
        collapsed.discard(item) if item in collapsed else collapsed.add(item)
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
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"')
        with wrap:
            if cb.kind == "mapping":
                inputs[cb.id] = ui.input(on_change=lambda e: on_mapping_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prime":
                with ui.element("div").classes("rtt-white"):
                    labels[cb.id] = ui.label(cb.text)
            elif cb.kind == "genratio":
                _ratio(cb, approx=True)
            elif cb.kind == "target":
                _ratio(cb, approx=False)
            elif cb.kind == "mapped":
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")
            elif cb.kind in _EBK_SVG_KINDS:  # ⟨ ] [, top bracket, brace, monzo rule
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in render() from its px box
            elif cb.kind == "caption":
                wrap.classes("rtt-caption-cell")
                ui.label(cb.text).classes("rtt-caption")
            elif cb.kind == "tval":
                whole, frac = _cents_parts(cb.text)
                with ui.element("div").classes("rtt-tval"):
                    w = ui.label(whole).classes("rtt-cents-int")
                    f = ui.label(f".{frac}" if frac else "").classes("rtt-cents-frac")
                cents[cb.id] = (w, f)
            elif cb.kind == "colheader":
                labels[cb.id] = ui.label(cb.text).classes("rtt-colheader")
            elif cb.kind == "rowlabel":
                labels[cb.id] = ui.label(cb.text).classes("rtt-rowlabel")
            elif cb.kind in ("rowtoggle", "coltoggle"):
                item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets"
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None, it=item: on_toggle(it))
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
        return wrap

    def render():
        building[0] = True
        st = editor.state
        lay = spreadsheet.build(st, settings, collapsed)
        board.style(f"width:{lay.width}px; height:{lay.height}px")
        seen = set()

        for ln in lay.lines:
            seen.add(ln.id)
            if ln.id not in els:
                with board:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    els[ln.id] = ui.element("div").classes(cls).props(f'data-eid="{ln.id}"')
            if ln.orientation == "v":
                els[ln.id].style(f"left:{ln.pos}px; top:{ln.start}px; height:{ln.length}px")
            else:
                els[ln.id].style(f"top:{ln.pos}px; left:{ln.start}px; width:{ln.length}px")

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in els:
                with board:
                    els[bl.id] = ui.element("div").classes("rtt-block").props(f'data-eid="{bl.id}"')
            els[bl.id].style(f"left:{bl.x}px; top:{bl.y}px; width:{bl.w}px; height:{bl.h}px")

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id not in els:
                with board:
                    els[cb.id] = _make_cell(cb)
            els[cb.id].style(f"left:{cb.x}px; top:{cb.y}px; width:{cb.w}px; height:{cb.h}px")
            if cb.kind in _EBK_SVG_KINDS:
                # the mark is drawn 1:1 to its px box, so redraw it whenever the box
                # changes size (e.g. the brace/top bracket as the domain grows)
                if ebk_sizes.get(cb.id) != (cb.w, cb.h):
                    htmls[cb.id].set_content(_ebk_svg(cb))
                    ebk_sizes[cb.id] = (cb.w, cb.h)
            elif cb.kind == "mapping":
                inputs[cb.id].value = str(st.mapping[cb.gen][cb.prime])
            elif cb.id in fracs:
                num, den = _ratio_parts(cb.text) or (cb.text, "")
                fracs[cb.id][0].set_text(num)
                fracs[cb.id][1].set_text(den)
            elif cb.id in cents:
                whole, frac = _cents_parts(cb.text)
                cents[cb.id][0].set_text(whole)
                cents[cb.id][1].set_text(f".{frac}" if frac else "")
            elif cb.kind in _LABEL_KINDS:
                labels[cb.id].set_text(cb.text)

        for eid in [e for e in els if e not in seen]:
            els[eid].delete()
            del els[eid]
            inputs.pop(eid, None)
            labels.pop(eid, None)
            fracs.pop(eid, None)
            cents.pop(eid, None)
            htmls.pop(eid, None)
            ebk_sizes.pop(eid, None)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        building[0] = False

    with ui.dialog() as show_dialog, ui.card().classes("rtt-show-card"):
        ui.label("Show").classes("rtt-show-title")
        with ui.row().classes("rtt-show-groups"):
            for group_name, items in show_settings.SHOW_GROUPS:
                with ui.column().classes("rtt-show-group"):
                    ui.label(group_name).classes("rtt-show-grouptitle")
                    for key, label, _ in items:
                        box = ui.checkbox(label, value=settings[key],
                                          on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                            .props("dense size=xs color=grey-8").classes("rtt-show-item")
                        if key not in show_settings.IMPLEMENTED:
                            box.props("disable")  # not built yet -> greyed and inert

    ui.label("RTT App").classes("rtt-title")
    with ui.row().style("gap:4px; margin-bottom:10px; align-items:center"):
        refs["undo"] = ui.button(icon="undo", on_click=lambda: act(editor.undo), color=None) \
            .props("flat dense round").classes("rtt-iconbtn")
        refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
            .props("flat dense round").classes("rtt-iconbtn")
        ui.button(icon="settings", on_click=show_dialog.open, color=None) \
            .props("flat dense round").classes("rtt-iconbtn")
    with ui.element("div").classes("rtt-scroll"):
        with ui.element("div").classes("rtt-outer"):
            board = ui.element("div").classes("rtt-board")

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


def main() -> None:
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    ui.run(title="RTT", reload=True, show=False, port=port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
