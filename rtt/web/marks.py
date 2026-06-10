"""EBK mark SVGs — the bracket/brace/rule glyphs that frame the spreadsheet's value
matrices. Each is one SVG whose viewBox maps 1:1 to the cell's px box (see :func:`_svg`),
so a stroke specified as N px is exactly N px tall AND wide at any span — no scaling, so a
1-row and a many-row bracket read at the exact same weight. Pure string builders, shared by
the renderer (app.py) so the page module doesn't carry the geometry."""

import math

_BR_COLOR = "#1a1a1a"
_PENDING_COLOR = "#e53935"  # red for a pending comma's draft cells, brackets and "?"
_BR_BAR = 2  # main bar / vector-rule / square-bracket bar thickness (px)
_BR_SERIF_T = 0.9  # square + top bracket serif thickness — a thin foot, well under the bar
_BR_SERIF_L = 6  # square + top bracket serif length (how far the foot reaches) — also
# the shared footprint width every value bracket (square AND angle) draws within
_BR_INSET = 2.5  # gap from a bracket's open side to the value cells it hugs
# The ⟨ and the brace are filled ribbons of varying width (see _ribbon): a calligraphic
# pen lays a LONG stroke down THICK and a SHORT one THIN. The thin ends stay delicate so
# the thick/thin taper reads clearly.
_BR_ANGLE_THICK = 1.1  # ⟨ half-width at the vertex (heavier)
_BR_ANGLE_THIN = 0.45  # ⟨ half-width at the open tips (much lighter) — a pronounced taper
_BR_BRACE_THICK = 1.15  # brace arm half-width: the long horizontal stroke is thick
_BR_BRACE_THIN = 0.4  # brace end-serif half-width: the short upturn is thin
_BR_BRACE_CUSP = 0.2  # brace central-cusp half-width: the short dip is a near point


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


def _hbar(w, h):
    """A horizontal rule — the size-sensitizing matrix's \\hline, separating 𝑋 = 𝑍𝐿's bottom size row
    from its top square (the mirror of the vertical size bar in the inverse 𝑊 = 𝑋⁻)."""
    return _svg(w, h, _rect(0, (h - _BR_BAR) / 2, w, _BR_BAR))


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
    elif cb.kind == "hbar":
        svg = _hbar(cb.w, cb.h)
    else:
        svg = _vbar(cb.w, cb.h)  # "vbar"
    return svg.replace(_BR_COLOR, _PENDING_COLOR) if cb.pending else svg
