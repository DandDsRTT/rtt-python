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


def size_panes(chrome, lay, fx, fy) -> None:
    base_w = lay.width + lay.right_overhang + 2 * _PAD
    base_h = lay.height + 2 * _PAD
    chrome.grid_pane.style(f"width:{base_w}px; height:{base_h}px")
    fit_w = lay.width + 2 * _PAD
    chrome.grid_pane.props(f'data-base-w="{base_w}" data-base-h="{base_h}" data-fit-w="{fit_w}"')
    chrome.board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
    chrome.colhead.style(f"height:{fy}px")
    chrome.colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
    chrome.corner.style(f"width:{fx}px; height:{fy}px")
    chrome.gridbody.style(f"top:{_PAD + fy}px")
    chrome.colfill.style(f"top:{_PAD + fy}px")
    chrome.colfill_inner.style(f"width:{lay.width}px; height:{lay.height}px")
    chrome.rowfill.style(f"top:{_PAD + fy}px; width:{fx}px")
    chrome.rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
    chrome.show_frozen.style(f"height:{max(0, fy - _CHROME_H)}px")
    chrome.show_scroll.style(f"max-height:calc(100dvh - {_PAD + fy}px)")


def render_lines(r, lay, seen) -> None:
    fx, fy = lay.freeze_x, lay.freeze_y

    def place_line(ln, suffix, parent, shift):
        eid = ln.id + suffix
        seen.add(eid)
        if eid not in r._rec.entities:
            with parent:
                cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                if r._revirtualizing:
                    cls += " rtt-noentry"
                r._rec.entities[eid] = EntityHandles(
                    el=ui.element("div").classes(cls).props(f'data-eid="{eid}"')
                )
        sty = _line_style(ln, shift)
        if r._rec.entity(eid).styled != sty:
            r._rec.entities[eid].el.style(sty)
            r._rec.entities[eid].styled = sty

    for ln in lay.lines:
        x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
        y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
        if x1 >= fx and y1 >= fy:
            place_line(ln, "", r._chrome.board, fy)
            if ln.orientation == "v" and y0 <= fy and ln.length > fy:
                place_line(ln, "#fill", r._chrome.colfill_inner, fy)
        if x1 >= fx and y0 < fy:
            place_line(ln, "#col", r._chrome.colhead_inner, 0)
        if x0 < fx and y1 >= fy:
            place_line(ln, "#row", r._chrome.rowband, fy)


def render_blocks(r, lay, seen) -> None:
    fx, fy = lay.freeze_x, lay.freeze_y

    def place_block(bl, pane):
        suffix = "" if pane == "body" else "#" + pane
        shift = 0 if pane in ("col", "corner") else fy
        eid = bl.id + suffix
        seen.add(eid)
        if eid not in r._rec.entities:
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
                r._rec.entities[eid] = EntityHandles(
                    el=ui.element("div").classes(cls).props(f'data-eid="{eid}"').mark(eid)
                )
        style = f"left:0; top:0; transform:translate({bl.x}px,{bl.y - shift}px); width:{bl.w}px; height:{bl.h}px"
        if bl.tint in _TINTS:
            style += f"; background:var(--wash-{bl.tint})"
        if r._rec.entity(eid).styled != style:
            r._rec.entities[eid].el.style(style)
            r._rec.entities[eid].styled = style

    for bl in lay.blocks:
        for pane in _block_panes(bl, fx, fy):
            place_block(bl, pane)


def make_cell_if_new(r, cb, container, structural) -> None:
    if cb.id in r._rec.entities and r._rec.cells[cb.id].kind != cb.kind:
        r._rec.drop(cb.id)
    if cb.id not in r._rec.entities:
        with r._chrome.cell_parents[container]:
            r._rec.make_cell(cb)
        if r._revirtualizing:
            r._rec.entities[cb.id].el.classes(add="rtt-noentry")
        if structural and not cb.pending and cb.id in r._newborn_ids:
            r._rec.entities[cb.id].el.classes(add="rtt-withhold")


def update_cell_content(r, cb) -> None:
    csig = (spreadsheet_text._cell_content(cb), cb.w, cb.h, cb.audio)
    h = r._rec.handles(cb.id)
    volatile = any(
        (
            h.value.input,
            h.value.den_input,
            h.value.ptext_input,
            h.chooser.select,
            h.chooser.check,
            h.value.frac_edit,
            h.value.ratio_op,
        )
    )
    if volatile or r._rec.handles(cb.id).content_sig != csig:
        r._rec.update_cell(cb)
        r._rec.cells[cb.id].content_sig = csig


def place_cell(r, cb, container, paint) -> None:
    fy, structural, rings = paint
    make_cell_if_new(r, cb, container, structural)
    top = cb.y - (fy if container in ("body", "row") else 0)
    grow = _CELL_BORDER_W if cb.kind in GRIDVALUE_KINDS else 0
    geo = f"left:0; top:0; transform:translate({cb.x}px,{top}px); width:{cb.w + grow}px; height:{cb.h + grow}px"
    if r._rec.entity(cb.id).styled != geo:
        r._rec.entities[cb.id].el.style(geo)
        r._rec.entities[cb.id].styled = geo
    update_cell_content(r, cb)
    amber, red = rings
    r._gestures.paint_cell(cb.id, amber, red)


def render_cells(r, lay, seen, flags) -> None:
    amber, red, cold, structural = flags
    fx, fy = lay.freeze_x, lay.freeze_y
    paint = (fy, structural and not cold, (amber, red))
    for cb in lay.cells:
        seen.add(cb.id)
        container = _freeze_container(cb, fx, fy)
        if (
            cb.id not in r._rec.entities
            and container == "body"
            and not cb.pending
            and not r._body_visible(cb.x, cb.y, cb.w, cb.h, fy)
        ):
            continue
        place_cell(r, cb, container, paint)

    for eid in [e for e in r._rec.entities if e not in seen]:
        r._rec.drop(eid)


def end_stale_gestures(gestures) -> None:
    g = gestures.gesture
    if g is not None and not gestures.gesture_rendering:
        if g.kind in ("hover", "chooser", "temp", "drag"):
            gestures.end_gesture()
        else:
            g.apply = None
    if not gestures.rank_rendering:
        gestures.rank_remove = None


def validate_gesture_source(gestures, rec, lay) -> None:
    g = gestures.gesture
    if g is not None and g.source is not None:
        src_kind = next((cb.kind for cb in lay.cells if cb.id == g.source), None)
        if src_kind is None or (g.source in rec.cells and rec.cells[g.source].kind != src_kind):
            gestures.end_gesture()
