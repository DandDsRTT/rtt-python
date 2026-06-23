from __future__ import annotations

from rtt.app import spreadsheet_constants


def _freeze_container(cb, fx: float, fy: float) -> str:
    if cb.x < fx and cb.y < fy:
        return "corner"
    if cb.y < fy:
        return "col"
    if cb.x < fx:
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
    # whether a grid rect's body-pane placement intersects the visible scroll rectangle (inflated by
    # overscan). view is the gridbody's (scrollLeft, scrollTop, clientW, clientH) in its own scrolled
    # coordinates; a body item sits at board-local (x, y - fy), the same frame the scroll metrics use.
    # view is None before the client reports its viewport (and whenever virtualization is off), meaning
    # "materialize everything". A zero-width/height edge (a gridline) still tests correctly: x..x and
    # the overscan band give it a one-axis interval.
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


# spacing of the dots on a folded band's gridline: a LINE_W-long dot every _DOT_PITCH px.
# CSS `border-style:dotted` packs dots ~one border-width apart (≈2*LINE_W period) and gives
# no control; painting them ourselves lets us space them out — here ≈twice as sparse.
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
