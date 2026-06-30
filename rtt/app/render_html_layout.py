from __future__ import annotations

from rtt.app import spreadsheet_constants


def _freeze_container(cell_box, freeze_x: float, freeze_y: float) -> str:
    if cell_box.x < freeze_x and cell_box.y < freeze_y:
        return "corner"
    if cell_box.y < freeze_y:
        return "col"
    if cell_box.x < freeze_x:
        return "row"
    return "body"


def _block_panes(bl, freeze_x: float, freeze_y: float) -> tuple[str, ...]:
    panes = ["body"]
    if bl.y < freeze_y:
        panes.append("col")
    if bl.x < freeze_x:
        panes.append("row")
    if bl.x < freeze_x and bl.y < freeze_y:
        panes.append("corner")
    return tuple(panes)


def _rect_in_view(x, y, width, height, freeze_y, view, overscan) -> bool:
    if view is None:
        return True
    left, top, vw, vh = view
    by = y - freeze_y
    return (
        x < left + vw + overscan
        and x + width > left - overscan
        and by < top + vh + overscan
        and by + height > top - overscan
    )


# CSS `border-style:dotted` packs dots ~one border-width apart and gives no spacing control, so the
# folded-band gridline dots are painted manually at this pitch instead.
_DOT_PITCH = 8


def _line_style(line, y_shift: float = 0) -> str:
    half = spreadsheet_constants.LINE_WIDTH / 2
    if line.orientation == "v":
        pos, edge, sweep = (
            f"left:0; top:0; transform:translate({line.pos - half}px,{line.start - y_shift}px); "
            f"height:{line.length}px",
            "left",
            "to bottom",
        )
    else:
        pos, edge, sweep = (
            f"left:0; top:0; transform:translate({line.start}px,{line.pos - half - y_shift}px); "
            f"width:{line.length}px",
            "top",
            "to right",
        )
    if line.dotted:
        dots = (
            f"repeating-linear-gradient({sweep},var(--c-gridline) 0 {spreadsheet_constants.LINE_WIDTH}px,"
            f"transparent {spreadsheet_constants.LINE_WIDTH}px {_DOT_PITCH}px) border-box"
        )
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:var(--c-gridline); background:none"


def _select_props(min_width: float) -> str:
    return (
        "dense options-dense borderless hide-bottom-space "
        "popup-content-class=rtt-select-popup "
        f"popup-content-style=min-width:{min_width}px;width:max-content"
    )
