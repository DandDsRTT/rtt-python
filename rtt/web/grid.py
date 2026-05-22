"""Lays out the temperament editor on the original app's coordinate grid.

The mapping, prime header and comma basis share a prime axis: the header sits
above the mapping columns, an empty d x d square holds the crossing axis, and
the comma basis hangs to its right. Each content block is an #e0e0e0 padded
rectangle; blocks are separated by #c0c0c0 margins; and #e0e0e0 grid lines
extend every gridded row and column across the empty/margin regions, drawing
the coordinate grid. This generator returns the cells (position, CSS class,
content, grid-line flags) so the NiceGUI layer can render them verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    css: str  # original style class: square-input, square-box, box-name, blank,
    # corner/vertical/horizontal-padding, corner/vertical/horizontal-margin,
    # empty-box-element, empty
    kind: str = ""  # "", prime, minus, plus, mapping, comma, name
    text: str = ""  # prime number or label
    gen: int = -1  # generator index (mapping cell)
    prime: int = -1  # prime index (mapping/comma cell)
    comma: int = -1  # comma index (comma cell)
    colspan: int = 1
    hline: bool = False
    vline: bool = False


_CELL_PX = 30  # a content cell (square-input / square-box)
_GAP_PX = 10  # a padding / margin track
_NAME_PX = 16  # a box-name (label) row


def track_sizes(cells: list[Cell]) -> tuple[list[int], list[int]]:
    """Explicit, uniform column widths and row heights for the grid.

    Content tracks are ``_CELL_PX`` wide/tall, padding/margin tracks ``_GAP_PX``;
    fixed tracks keep every column and row aligned so the centered grid lines
    line up (auto/min-content sizing left them ragged)."""
    col_w: dict[int, int] = {}
    row_h: dict[int, int] = {}
    for c in cells:
        if c.css in ("square-input", "square-box"):
            for k in range(c.colspan):
                col_w[c.col + k] = _CELL_PX
            row_h[c.row] = _CELL_PX
        elif c.css == "box-name":
            row_h.setdefault(c.row, _NAME_PX)
    max_col = max(c.col + c.colspan - 1 for c in cells)
    max_row = max(c.row for c in cells)
    cols = [col_w.get(i, _GAP_PX) for i in range(1, max_col + 1)]
    rows = [row_h.get(i, _GAP_PX) for i in range(1, max_row + 1)]
    return cols, rows


def _band(content_subs: list[str]) -> list[str]:
    """Wrap a band's content sub-tracks with the padding ring and trailing margin."""
    return ["pad", *content_subs, "pad", "margin"]


def _gridded_index(subs: list[str], pos: int) -> int:
    """Among ``subs``, the 0-based index of the gridded track at ``pos`` (else -1)."""
    if subs[pos] != "gridded":
        return -1
    return sum(1 for s in subs[:pos] if s == "gridded")


def build(d: int, rank: int, n: int, primes: tuple[int, ...]) -> list[Cell]:
    row_bands = {
        "rae": _band(["main"]),
        "header": _band(["gridded", "text"]),
        "intervals": _band(["gridded"] * d + ["name", "plus"]),
        "mapping": _band(["gridded"] * rank + ["name", "plus"]),
    }
    col_bands = {
        "primes": _band(["gridded"] * d + ["plus"]),
        "commas": _band(["gridded"] * n + ["plus"]),
    }
    row_order = ["rae", "header", "intervals", "mapping"]
    col_order = ["primes", "commas"]

    row_base, col_base = {}, {}
    pos = 1
    for name in row_order:
        row_base[name] = pos
        pos += len(row_bands[name])
    pos = 1
    for name in col_order:
        col_base[name] = pos
        pos += len(col_bands[name])

    # which (row band, col band) regions hold content, and which renderer to use
    content = {
        ("rae", "primes"): "rae",
        ("header", "primes"): "header",
        ("intervals", "commas"): "comma",
        ("mapping", "primes"): "mapping",
    }

    cells: list[Cell] = []
    for rb in row_order:
        rsubs = row_bands[rb]
        for cb in col_order:
            csubs = col_bands[cb]
            component = content.get((rb, cb))
            for ri, rtype in enumerate(rsubs):
                for ci, ctype in enumerate(csubs):
                    row, col = row_base[rb] + ri, col_base[cb] + ci
                    g_row = _gridded_index(rsubs, ri)
                    g_col = _gridded_index(csubs, ci)
                    cell = (
                        _content_cell(component, rtype, ctype, g_row, g_col, row, col, d, n, primes)
                        if component
                        else _empty_cell(rtype, ctype, row, col)
                    )
                    if cell is not None:
                        cells.append(cell)
    return cells


def _content_cell(component, rtype, ctype, g_row, g_col, row, col, d, n, primes):
    if rtype == "margin":
        css = "corner-margin" if ctype == "margin" else "vertical-margin"
        return Cell(row, col, css, vline=(ctype == "gridded"))
    if rtype == "pad":
        if ctype == "margin":
            return Cell(row, col, "horizontal-margin")
        return Cell(row, col, "corner-padding" if ctype == "pad" else "vertical-padding")
    if ctype == "pad":
        return Cell(row, col, "horizontal-padding")
    if ctype == "margin":
        return Cell(row, col, "horizontal-margin", hline=(rtype == "gridded"))
    return _interactive_cell(component, rtype, ctype, g_row, g_col, row, col, d, n, primes)


def _interactive_cell(component, rtype, ctype, g_row, g_col, row, col, d, n, primes):
    gridded = rtype == "gridded" and g_col >= 0
    if component == "header":
        if gridded:
            return Cell(row, col, "square-input", "prime", text=str(primes[g_col]))
        return Cell(row, col, "blank")
    if component == "mapping":
        if gridded:
            return Cell(row, col, "square-input", "mapping", gen=g_row, prime=g_col)
        if rtype == "name" and g_col == 0:
            return Cell(row, col, "box-name", "name", text="mapping", colspan=d)
        if rtype == "name" and g_col > 0:
            return None  # covered by the spanning box-name
        return Cell(row, col, "blank")
    if component == "comma":
        if gridded:
            return Cell(row, col, "square-input", "comma", comma=g_col, prime=g_row)
        if rtype == "name" and g_col == 0:
            return Cell(row, col, "box-name", "name", text="comma basis", colspan=n)
        if rtype == "name" and g_col > 0:
            return None
        return Cell(row, col, "blank")
    if component == "rae":  # the - / + domain controls
        if g_col == d - 1:
            return Cell(row, col, "square-box", "minus")
        if ctype == "plus":
            return Cell(row, col, "square-box", "plus")
        return Cell(row, col, "blank")
    return Cell(row, col, "blank")


def _empty_cell(rtype, ctype, row, col):
    if rtype in ("pad", "margin"):
        if ctype == "margin":
            return Cell(row, col, "corner-margin" if rtype == "margin" else "horizontal-margin")
        if ctype == "pad":
            return Cell(row, col, "corner-margin")
        return Cell(row, col, "vertical-margin", vline=(ctype == "gridded"))
    if ctype in ("pad", "margin"):
        return Cell(row, col, "horizontal-margin", hline=(rtype == "gridded"))
    hline, vline = rtype == "gridded", ctype == "gridded"
    if hline or vline:
        return Cell(row, col, "empty-box-element", hline=hline, vline=vline)
    return Cell(row, col, "empty")
