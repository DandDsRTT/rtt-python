import math

BR_COLOR = "#1a1a1a"
PENDING_COLOR = "#2e9e3f"
_BR_BAR = 2
_BR_SERIF_T = 0.9
BR_SERIF_L = 6
BR_INSET = 2.5
_BR_ANGLE_THICK = 1.1
_BR_ANGLE_THIN = 0.45
_BEZIER_SAMPLES = 10
_FOOT_BEZIER_SAMPLES = 8


def svg(width, height, body):
    return (
        f'<svg width="100%" height="100%" viewBox="0 0 {width:.2f} {height:.2f}" '
        f'aria-hidden="true" preserveAspectRatio="none" '
        f'style="display:block;overflow:visible">{body}</svg>'
    )


def rect(x, y, width, height):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="{BR_COLOR}"/>'


def ribbon(pts):
    edge_a, edge_b = [], []
    n = len(pts)
    for i in range(n):
        x, y, hw = pts[i]
        px, py = pts[i - 1][:2] if i else pts[i][:2]
        nx, ny = pts[i + 1][:2] if i < n - 1 else pts[i][:2]
        tx, ty = nx - px, ny - py
        length = math.hypot(tx, ty) or 1.0
        ox, oy = -ty / length * hw, tx / length * hw
        edge_a.append((x + ox, y + oy))
        edge_b.append((x - ox, y - oy))
    outline = edge_a + edge_b[::-1]
    return (
        '<path fill="'
        + BR_COLOR
        + '" d="M'
        + " ".join(f"{x:.2f},{y:.2f}" for x, y in outline)
        + ' Z"/>'
    )


def _qbez(p0, control, p1, w0, w1, n, *, skip_first=False):
    out = []
    for i in range(n + 1):
        if skip_first and i == 0:
            continue
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * control[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * control[1] + t * t * p1[1]
        out.append((x, y, w0 + (w1 - w0) * t))
    return out


def square_bracket(width, height, side):
    if side == "left":
        x_in = width - BR_INSET
        x_out = x_in - BR_SERIF_L
        bar_x = x_out
    else:
        x_out = BR_INSET
        bar_x = x_out + BR_SERIF_L - _BR_BAR
    return svg(
        width,
        height,
        rect(bar_x, 0, _BR_BAR, height)
        + rect(x_out, 0, BR_SERIF_L, _BR_SERIF_T)
        + rect(x_out, height - _BR_SERIF_T, BR_SERIF_L, _BR_SERIF_T),
    )


def top_bracket(width, height):
    return svg(
        width,
        height,
        rect(0, 0, width, _BR_BAR)
        + rect(0, 0, _BR_SERIF_T, BR_SERIF_L)
        + rect(width - _BR_SERIF_T, 0, _BR_SERIF_T, BR_SERIF_L),
    )


def angle_bracket(width, height):
    bx1 = width - BR_INSET
    bx0 = bx1 - BR_SERIF_L
    center_y = height / 2
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.4
    top, vertex, bot = (tx, 0.2), (vx, center_y), (tx, height - 0.2)
    n = _BEZIER_SAMPLES
    pts = [
        (
            top[0] + (vertex[0] - top[0]) * i / n,
            top[1] + (vertex[1] - top[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n,
        )
        for i in range(n + 1)
    ]
    pts += [
        (
            vertex[0] + (bot[0] - vertex[0]) * i / n,
            vertex[1] + (bot[1] - vertex[1]) * i / n,
            _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n,
        )
        for i in range(1, n + 1)
    ]
    return svg(width, height, ribbon(pts))


def curved_angle_foot(width, height):
    center_x = width / 2
    ty, vy = 0.85, height - 0.5 - _BR_ANGLE_THICK
    thick, thin = _BR_ANGLE_THICK, _BR_ANGLE_THIN
    n = _FOOT_BEZIER_SAMPLES
    pts = _qbez((0.8, ty), (center_x, ty), (center_x, vy), thin, thick, n)
    pts += _qbez((center_x, vy), (center_x, ty), (width - 0.8, ty), thick, thin, n, skip_first=True)
    return svg(width, height, ribbon(pts))


def curved_angle_bracket(width, height):
    bx1 = width - BR_INSET
    bx0 = bx1 - BR_SERIF_L
    center_y = height / 2
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.4
    thick, thin = _BR_ANGLE_THICK, _BR_ANGLE_THIN
    n = _BEZIER_SAMPLES
    pts = _qbez((tx, 0.2), (tx, center_y), (vx, center_y), thin, thick, n)
    pts += _qbez((vx, center_y), (tx, center_y), (tx, height - 0.2), thick, thin, n, skip_first=True)
    return svg(width, height, ribbon(pts))


def angle_foot(width, height):
    center_x = width / 2
    ty, vy = 0.85, height - 0.5 - _BR_ANGLE_THICK
    left, vertex, right = (0.8, ty), (center_x, vy), (width - 0.8, ty)
    n = _FOOT_BEZIER_SAMPLES
    pts = [
        (
            left[0] + (vertex[0] - left[0]) * i / n,
            left[1] + (vertex[1] - left[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n,
        )
        for i in range(n + 1)
    ]
    pts += [
        (
            vertex[0] + (right[0] - vertex[0]) * i / n,
            vertex[1] + (right[1] - vertex[1]) * i / n,
            _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n,
        )
        for i in range(1, n + 1)
    ]
    return svg(width, height, ribbon(pts))


def vbar(width, height):
    return svg(width, height, rect((width - _BR_BAR) / 2, 0, _BR_BAR, height))


def _hbar(width, height):
    return svg(width, height, rect(0, (height - _BR_BAR) / 2, width, _BR_BAR))


def ebk_svg(cell):
    if cell.kind == "bracket":
        if cell.text == "⟨":
            svg = angle_bracket(cell.width, cell.height)
        elif cell.text == "⧼":
            svg = curved_angle_bracket(cell.width, cell.height)
        else:
            svg = square_bracket(cell.width, cell.height, "left" if cell.text == "[" else "right")
    elif cell.kind == "ebktop":
        svg = top_bracket(cell.width, cell.height)
    elif cell.kind == "ebkcurve":
        svg = curved_angle_foot(cell.width, cell.height)
    elif cell.kind == "ebkangle":
        svg = angle_foot(cell.width, cell.height)
    elif cell.kind == "hbar":
        svg = _hbar(cell.width, cell.height)
    else:
        svg = vbar(cell.width, cell.height)
    return svg.replace(BR_COLOR, PENDING_COLOR) if cell.pending else svg
