import math

BR_COLOR = "#1a1a1a"
PENDING_COLOR = "#2e9e3f"
_BR_BAR = 2
_BR_SERIF_T = 0.9
BR_SERIF_L = 6
BR_INSET = 2.5
_BR_ANGLE_THICK = 1.1
_BR_ANGLE_THIN = 0.45
_BR_BRACE_THICK = 1.15
_BR_BRACE_THIN = 0.4
_BR_BRACE_CUSP = 0.2
_BR_BRACE_END = 2.0
_BR_BRACE_SERIF = 3.2
_BR_BRACE_CUSP_DX = 5.5
_BEZIER_SAMPLES = 10
_FOOT_BEZIER_SAMPLES = 8


def svg(width, height, body):
    return (
        f'<svg width="100%" height="100%" viewBox="0 0 {width:.2f} {height:.2f}" '
        f'preserveAspectRatio="none" style="display:block;overflow:visible">{body}</svg>'
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


def brace(width, height):
    center_x = width / 2
    end_x, serif_dx, cusp_dx = _BR_BRACE_END, _BR_BRACE_SERIF, _BR_BRACE_CUSP_DX
    span = end_x + serif_dx + cusp_dx + 1.0
    if span > center_x:
        s = center_x / span
        end_x, serif_dx, cusp_dx = end_x * s, serif_dx * s, cusp_dx * s
    arm_y = height / 2
    reach = height / 2 - 0.5
    tip_y, cusp_y = arm_y - reach, arm_y + reach - 0.3
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = _BEZIER_SAMPLES
    pts = _qbez((end_x, tip_y), (end_x, arm_y), (end_x + serif_dx, arm_y), thin, thick, n)
    pts.append((center_x - cusp_dx, arm_y, thick))
    pts += _qbez(
        (center_x - cusp_dx, arm_y),
        (center_x, arm_y),
        (center_x, cusp_y),
        thick,
        cusp,
        n,
        skip_first=True,
    )
    pts += _qbez(
        (center_x, cusp_y),
        (center_x, arm_y),
        (center_x + cusp_dx, arm_y),
        cusp,
        thick,
        n,
        skip_first=True,
    )
    pts.append((width - end_x - serif_dx, arm_y, thick))
    pts += _qbez(
        (width - end_x - serif_dx, arm_y),
        (width - end_x, arm_y),
        (width - end_x, tip_y),
        thick,
        thin,
        n,
        skip_first=True,
    )
    return svg(width, height, ribbon(pts))


def curly_bracket(width, height):
    center_y = height / 2
    end_y, serif_dy, cusp_dy = _BR_BRACE_END, _BR_BRACE_SERIF, _BR_BRACE_CUSP_DX
    span = end_y + serif_dy + cusp_dy + 1.0
    if span > center_y:
        s = center_y / span
        end_y, serif_dy, cusp_dy = end_y * s, serif_dy * s, cusp_dy * s
    tip_x = width - BR_INSET
    cusp_x = tip_x - BR_SERIF_L
    arm_x = (tip_x + cusp_x) / 2
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = _BEZIER_SAMPLES
    pts = _qbez((tip_x, end_y), (arm_x, end_y), (arm_x, end_y + serif_dy), thin, thick, n)
    pts.append((arm_x, center_y - cusp_dy, thick))
    pts += _qbez(
        (arm_x, center_y - cusp_dy),
        (arm_x, center_y),
        (cusp_x, center_y),
        thick,
        cusp,
        n,
        skip_first=True,
    )
    pts += _qbez(
        (cusp_x, center_y),
        (arm_x, center_y),
        (arm_x, center_y + cusp_dy),
        cusp,
        thick,
        n,
        skip_first=True,
    )
    pts.append((arm_x, height - end_y - serif_dy, thick))
    pts += _qbez(
        (arm_x, height - end_y - serif_dy),
        (arm_x, height - end_y),
        (tip_x, height - end_y),
        thick,
        thin,
        n,
        skip_first=True,
    )
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


def ebk_svg(cell_box):
    if cell_box.kind == "bracket":
        if cell_box.text == "⟨":
            svg = angle_bracket(cell_box.width, cell_box.height)
        elif cell_box.text == "{":
            svg = curly_bracket(cell_box.width, cell_box.height)
        else:
            svg = square_bracket(
                cell_box.width, cell_box.height, "left" if cell_box.text == "[" else "right"
            )
    elif cell_box.kind == "ebktop":
        svg = top_bracket(cell_box.width, cell_box.height)
    elif cell_box.kind == "ebkbrace":
        svg = brace(cell_box.width, cell_box.height)
    elif cell_box.kind == "ebkangle":
        svg = angle_foot(cell_box.width, cell_box.height)
    elif cell_box.kind == "hbar":
        svg = _hbar(cell_box.width, cell_box.height)
    else:
        svg = vbar(cell_box.width, cell_box.height)
    return svg.replace(BR_COLOR, PENDING_COLOR) if cell_box.pending else svg
