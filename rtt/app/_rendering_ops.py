from __future__ import annotations

from nicegui import ui

from rtt.app import spreadsheet_text
from rtt.app._recon_handles import EntityHandles
from rtt.app.page_assets import _CELL_BORDER_W, _CHROME_H, _PAD, _TINTS, GRIDVALUE_KINDS
from rtt.app.render_html import _block_panes, _freeze_container, _line_style


def apply_view_classes(editor, runtime) -> None:
    # NiceGUI: render() can run off the event loop (_commit_render), where the slot stack is empty
    # and ui.query would raise "slot stack ... is empty"; entering the captured page client lets the
    # <body> query resolve there (and nests harmlessly inside the live slot on the synchronous path).
    with runtime.page_client:
        body = ui.query("body")
        body.classes(add="rtt-no-anim") if not editor.settings["animations"] else body.classes(
            remove="rtt-no-anim"
        )
        body.classes(add="rtt-no-tooltips") if not editor.settings["tooltips"] else body.classes(
            remove="rtt-no-tooltips"
        )
        body.classes(add="rtt-mapping-demos") if editor.settings["mapping_demos"] else body.classes(
            remove="rtt-mapping-demos"
        )


def size_panes(chrome, layout, freeze_x, freeze_y) -> None:
    base_width = layout.width + layout.right_overhang + 2 * _PAD
    base_height = layout.height + 2 * _PAD
    chrome.grid_pane.style(f"width:{base_width}px; height:{base_height}px")
    fit_width = layout.width + 2 * _PAD
    chrome.grid_pane.props(
        f'data-base-w="{base_width}" data-base-h="{base_height}" data-fit-w="{fit_width}"'
    )
    chrome.board.style(f"width:{layout.width}px; height:{layout.height - freeze_y}px")
    chrome.colhead.style(f"height:{freeze_y}px")
    chrome.colhead_inner.style(f"width:{layout.width}px; height:{freeze_y}px")
    chrome.corner.style(f"width:{freeze_x}px; height:{freeze_y}px")
    chrome.gridbody.style(f"top:{_PAD + freeze_y}px")
    chrome.colfill.style(f"top:{_PAD + freeze_y}px")
    chrome.colfill_inner.style(f"width:{layout.width}px; height:{layout.height}px")
    chrome.rowfill.style(f"top:{_PAD + freeze_y}px; width:{freeze_x}px")
    chrome.rowband.style(f"width:{freeze_x}px; height:{layout.height - freeze_y}px")
    chrome.show_frozen.style(f"height:{max(0, freeze_y - _CHROME_H)}px")
    chrome.show_scroll.style(f"max-height:calc(100dvh - {_PAD + freeze_y}px)")


def render_lines(r, layout, seen) -> None:
    freeze_x, freeze_y = layout.freeze_x, layout.freeze_y

    def place_line(line, suffix, parent, shift):
        element_id = line.id + suffix
        seen.add(element_id)
        if element_id not in r._rec.entities:
            with parent:
                cls = "rtt-line " + ("rtt-line-v" if line.orientation == "v" else "rtt-line-h")
                if r._revirtualizing:
                    cls += " rtt-noentry"
                r._rec.entities[element_id] = EntityHandles(
                    element=ui.element("div").classes(cls).props(f'data-eid="{element_id}"')
                )
        sty = _line_style(line, shift)
        if r._rec.entity(element_id).styled != sty:
            r._rec.entities[element_id].element.style(sty)
            r._rec.entities[element_id].styled = sty

    for line in layout.lines:
        x0, x1 = (
            (line.position, line.position)
            if line.orientation == "v"
            else (line.start, line.start + line.length)
        )
        y0, y1 = (
            (line.start, line.start + line.length)
            if line.orientation == "v"
            else (line.position, line.position)
        )
        if x1 >= freeze_x and y1 >= freeze_y:
            place_line(line, "", r._chrome.board, freeze_y)
            if line.orientation == "v" and y0 <= freeze_y and line.length > freeze_y:
                place_line(line, "#fill", r._chrome.colfill_inner, freeze_y)
        if x1 >= freeze_x and y0 < freeze_y:
            place_line(line, "#col", r._chrome.colhead_inner, 0)
        if x0 < freeze_x and y1 >= freeze_y:
            place_line(line, "#row", r._chrome.rowband, freeze_y)


def render_blocks(r, layout, seen) -> None:
    freeze_x, freeze_y = layout.freeze_x, layout.freeze_y

    def place_block(bl, pane):
        suffix = "" if pane == "body" else "#" + pane
        shift = 0 if pane in ("col", "corner") else freeze_y
        element_id = bl.id + suffix
        seen.add(element_id)
        if element_id not in r._rec.entities:
            with r._chrome.cell_parents[pane]:
                cls = (
                    "rtt-block-boxed"
                    if bl.boxed
                    else "rtt-washbase"
                    if bl.tint == "base"
                    else "rtt-wash"
                    if bl.tint
                    else "rtt-block"
                )
                if r._revirtualizing:
                    cls += " rtt-noentry"
                r._rec.entities[element_id] = EntityHandles(
                    element=ui.element("div")
                    .classes(cls)
                    .props(f'data-eid="{element_id}"')
                    .mark(element_id)
                )
        style = f"left:0; top:0; transform:translate({bl.x}px,{bl.y - shift}px); width:{bl.width}px; height:{bl.height}px"
        if bl.tint in _TINTS:
            style += f"; background:var(--wash-{bl.tint})"
        if r._rec.entity(element_id).styled != style:
            r._rec.entities[element_id].element.style(style)
            r._rec.entities[element_id].styled = style

    for bl in layout.blocks:
        for pane in _block_panes(bl, freeze_x, freeze_y):
            place_block(bl, pane)


def make_cell_if_new(r, cell_box, container, structural) -> None:
    if cell_box.id in r._rec.entities and r._rec.cells[cell_box.id].kind != cell_box.kind:
        r._rec.drop(cell_box.id)
    if cell_box.id not in r._rec.entities:
        with r._chrome.cell_parents[container]:
            r._rec.make_cell(cell_box)
        if r._revirtualizing:
            r._rec.entities[cell_box.id].element.classes(add="rtt-noentry")
        if structural and not cell_box.pending and cell_box.id in r._newborn_ids:
            r._rec.entities[cell_box.id].element.classes(add="rtt-withhold")


def update_cell_content(r, cell_box) -> None:
    csig = (
        spreadsheet_text._cell_content(cell_box),
        cell_box.width,
        cell_box.height,
        cell_box.audio,
    )
    height = r._rec.handles(cell_box.id)
    volatile = any(
        (
            height.value.input,
            height.value.den_input,
            height.value.plain_text_input,
            height.chooser.select,
            height.chooser.check,
            height.value.frac_edit,
            height.value.ratio_op,
        )
    )
    if volatile or r._rec.handles(cell_box.id).content_sig != csig:
        r._rec.update_cell(cell_box)
        r._rec.cells[cell_box.id].content_sig = csig


def place_cell(r, cell_box, container, paint) -> None:
    freeze_y, structural, rings = paint
    make_cell_if_new(r, cell_box, container, structural)
    top = cell_box.y - (freeze_y if container in ("body", "row") else 0)
    grow = _CELL_BORDER_W if cell_box.kind in GRIDVALUE_KINDS else 0
    placement = f"left:0; top:0; transform:translate({cell_box.x}px,{top}px); width:{cell_box.width + grow}px; height:{cell_box.height + grow}px"
    if r._rec.entity(cell_box.id).styled != placement:
        r._rec.entities[cell_box.id].element.style(placement)
        r._rec.entities[cell_box.id].styled = placement
    update_cell_content(r, cell_box)
    amber, red = rings
    r._gestures.paint_cell(cell_box.id, amber, red)


def render_cells(r, layout, seen, flags) -> None:
    amber, red, cold, structural = flags
    freeze_x, freeze_y = layout.freeze_x, layout.freeze_y
    paint = (freeze_y, structural and not cold, (amber, red))
    for cell_box in layout.cells:
        seen.add(cell_box.id)
        container = _freeze_container(cell_box, freeze_x, freeze_y)
        if (
            cell_box.id not in r._rec.entities
            and container == "body"
            and not cell_box.pending
            and not r._body_visible(
                cell_box.x, cell_box.y, cell_box.width, cell_box.height, freeze_y
            )
        ):
            continue
        place_cell(r, cell_box, container, paint)

    for element_id in [e for e in r._rec.entities if e not in seen]:
        r._rec.drop(element_id)


def end_stale_gestures(gestures) -> None:
    g = gestures.gesture
    if g is not None and not gestures.gesture_rendering:
        if g.kind in ("hover", "chooser", "temp", "drag"):
            gestures.end_gesture()
        else:
            g.apply = None
    if not gestures.rank_rendering:
        gestures.rank_remove = None


def validate_gesture_source(gestures, reconciler, layout) -> None:
    g = gestures.gesture
    if g is not None and g.source is not None:
        src_kind = next(
            (cell_box.kind for cell_box in layout.cells if cell_box.id == g.source), None
        )
        if src_kind is None or (
            g.source in reconciler.cells and reconciler.cells[g.source].kind != src_kind
        ):
            gestures.end_gesture()
