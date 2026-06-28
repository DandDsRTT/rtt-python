from __future__ import annotations

from rtt.app import spreadsheet_constants


def _freeze_container(cell_box, fx: float, fy: float) -> str:
    if cell_box.x < fx and cell_box.y < fy:
        return "corner"
    if cell_box.y < fy:
        return "col"
    if cell_box.x < fx:
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


def _rect_in_view(x, y, w, h, fy, view, overscan) -> bool:
    if view is None:
        return True
    left, top, vw, vh = view
    by = y - fy
    return (
        x < left + vw + overscan
        and x + w > left - overscan
        and by < top + vh + overscan
        and by + h > top - overscan
    )


# CSS `border-style:dotted` packs dots ~one border-width apart and gives no spacing control, so the
# folded-band gridline dots are painted manually at this pitch instead.
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
