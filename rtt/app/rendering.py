from __future__ import annotations

import asyncio
import logging
import os

from nicegui import background_tasks, helpers, ui

from rtt.app import (
    spreadsheet_text,
)
from rtt.app._recon_handles import EntityHandles
from rtt.app.page_assets import (
    _CHROME_H,
    _PAD,
    _TINTS,
)
from rtt.app.render_html import (
    _block_panes,
    _freeze_container,
    _line_style,
    _rect_in_view,
)
from rtt.app.rendering_chrome import _ChromeSyncMixin

_log = logging.getLogger(__name__)

_VIRT_OVERSCAN = 600.0
_VIRT_VIEWPORT0 = (1680.0, 1050.0)
_VIRT_REVIRT_STEP = 200.0
_FILL_CHUNK = 80


def _initial_viewport() -> tuple[float, float, float, float]:
    spec = os.environ.get("RTT_VIRT_VIEWPORT", "")
    if spec:
        w, h = (float(n) for n in spec.lower().split("x"))
    else:
        w, h = _VIRT_VIEWPORT0
    return (0.0, 0.0, w, h)


class Renderer(_ChromeSyncMixin):
    def __init__(self, page) -> None:
        self.page = page
        self.render_inflight = False
        self.render_again = False
        self.render_after = None
        self._viewport = _initial_viewport()
        self._virt_for: tuple | None = None
        self._revirtualizing = False
        self._newborn_ids: frozenset[str] = frozenset()
        self._prev_cell_ids: frozenset[str] = frozenset()
        self._last_rings: tuple = (frozenset(), frozenset())
        self._fill_gen = 0

    def request_render(self, after=None):
        if helpers.is_user_simulation():
            self.render()
            if after is not None:
                after()
            return
        if self.render_inflight:
            self.render_again = True
            self.render_after = after
            return
        background_tasks.create(self._commit_render(after))

    async def _commit_render(self, after=None):
        self.render_inflight = True
        try:
            again = True
            cont = after
            while again:
                prev = self.page.last_lay.identities if self.page.last_lay is not None else None
                try:
                    await asyncio.to_thread(self.page.editor.layout, prev_ids=prev)
                except Exception:
                    _log.exception("off-loop layout warm-up failed; rendering on the loop")
                self.render()
                if cont is not None:
                    cont()
                again = self.render_again
                self.render_again = False
                cont = self.render_after
                self.render_after = None
        finally:
            self.render_inflight = False

    def apply_view_classes(self):
        # NiceGUI: render() can run off the event loop (_commit_render), where the slot stack is empty
        # and ui.query would raise "slot stack ... is empty"; entering the captured page client lets the
        # <body> query resolve there (and nests harmlessly inside the live slot on the synchronous path).
        with self.page.page_client:
            body = ui.query("body")
            body.classes(add="rtt-no-anim") if not self.page.editor.settings[
                "animations"
            ] else body.classes(remove="rtt-no-anim")
            body.classes(add="rtt-no-tooltips") if not self.page.editor.settings[
                "tooltips"
            ] else body.classes(remove="rtt-no-tooltips")

    def _size_panes(self, lay, fx, fy) -> None:
        base_w = lay.width + lay.right_overhang + 2 * _PAD
        base_h = lay.height + 2 * _PAD
        self.page.grid_pane.style(f"width:{base_w}px; height:{base_h}px")
        fit_w = lay.width + 2 * _PAD
        self.page.grid_pane.props(f'data-base-w="{base_w}" data-base-h="{base_h}" data-fit-w="{fit_w}"')
        self.page.board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
        self.page.colhead.style(f"height:{fy}px")
        self.page.colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
        self.page.corner.style(f"width:{fx}px; height:{fy}px")
        self.page.gridbody.style(f"top:{_PAD + fy}px")
        self.page.rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
        self.page.show_frozen.style(f"height:{max(0, fy - _CHROME_H)}px")
        self.page.show_scroll.style(f"max-height:calc(100vh - {_PAD + fy}px)")

    def _render_lines(self, lay, fx, fy, seen) -> None:
        def place_line(ln, suffix, parent, shift):
            eid = ln.id + suffix
            seen.add(eid)
            if eid not in self.page.rec.entities:
                with parent:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    if self._revirtualizing:
                        cls += " rtt-noentry"
                    self.page.rec.entities[eid] = EntityHandles(
                        el=ui.element("div").classes(cls).props(f'data-eid="{eid}"')
                    )
            sty = _line_style(ln, shift)
            if self.page.rec.entity(eid).styled != sty:
                self.page.rec.entities[eid].el.style(sty)
                self.page.rec.entities[eid].styled = sty

        for ln in lay.lines:
            x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
            y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
            if x1 >= fx and y1 >= fy:
                place_line(ln, "", self.page.board, fy)
            if x1 >= fx and y0 < fy:
                place_line(ln, "#col", self.page.colhead_inner, 0)
            if x0 < fx and y1 >= fy:
                place_line(ln, "#row", self.page.rowband, fy)

    def _render_blocks(self, lay, fx, fy, seen) -> None:
        def place_block(bl, pane):
            suffix = "" if pane == "body" else "#" + pane
            shift = 0 if pane in ("col", "corner") else fy
            eid = bl.id + suffix
            seen.add(eid)
            if eid not in self.page.rec.entities:
                with self.page.cell_parents[pane]:
                    cls = (
                        "rtt-block-boxed"
                        if bl.boxed
                        else "rtt-washbase"
                        if bl.tint == "base"
                        else "rtt-wash"
                        if bl.tint
                        else "rtt-block"
                    )
                    if self._revirtualizing:
                        cls += " rtt-noentry"
                    self.page.rec.entities[eid] = EntityHandles(
                        el=ui.element("div").classes(cls).props(f'data-eid="{eid}"').mark(eid)
                    )
            style = f"left:0; top:0; transform:translate({bl.x}px,{bl.y - shift}px); width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:
                style += f"; background:var(--wash-{bl.tint})"
            if self.page.rec.entity(eid).styled != style:
                self.page.rec.entities[eid].el.style(style)
                self.page.rec.entities[eid].styled = style

        for bl in lay.blocks:
            for pane in _block_panes(bl, fx, fy):
                place_block(bl, pane)

    def _body_visible(self, x, y, w, h, fy) -> bool:
        return _rect_in_view(x, y, w, h, fy, self._viewport, _VIRT_OVERSCAN)

    def _make_cell_if_new(self, cb, container, cold, structural) -> None:
        if cb.id in self.page.rec.entities and self.page.rec.cells[cb.id].kind != cb.kind:
            self.page.rec.drop(cb.id)
        if cb.id not in self.page.rec.entities:
            with self.page.cell_parents[container]:
                self.page.rec.make_cell(cb)
            if self._revirtualizing:
                self.page.rec.entities[cb.id].el.classes(add="rtt-noentry")
            if structural and not cold and not cb.pending and cb.id in self._newborn_ids:
                self.page.rec.entities[cb.id].el.classes(add="rtt-withhold")

    def _update_cell_content(self, cb) -> None:
        csig = (spreadsheet_text._cell_content(cb), cb.w, cb.h, cb.audio)
        h = self.page.rec.handles(cb.id)
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
        if volatile or self.page.rec.handles(cb.id).content_sig != csig:
            self.page.rec.update_cell(cb)
            self.page.rec.cells[cb.id].content_sig = csig

    def _render_cells(self, lay, fx, fy, seen, amber, red, cold, structural) -> None:
        for cb in lay.cells:
            seen.add(cb.id)
            container = _freeze_container(cb, fx, fy)
            if (
                cb.id not in self.page.rec.entities
                and container == "body"
                and not cb.pending
                and not self._body_visible(cb.x, cb.y, cb.w, cb.h, fy)
            ):
                continue
            self._make_cell_if_new(cb, container, cold, structural)
            top = cb.y - (fy if container in ("body", "row") else 0)
            geo = f"left:0; top:0; transform:translate({cb.x}px,{top}px); width:{cb.w}px; height:{cb.h}px"
            if self.page.rec.entity(cb.id).styled != geo:
                self.page.rec.entities[cb.id].el.style(geo)
                self.page.rec.entities[cb.id].styled = geo
            self._update_cell_content(cb)
            self.page.gestures.paint_cell(cb.id, amber, red)

        for eid in [e for e in self.page.rec.entities if e not in seen]:
            self.page.rec.drop(eid)

    def _end_stale_gestures(self) -> None:
        g = self.page.gestures.gesture
        if g is not None and not self.page.gestures.gesture_rendering:
            if g.kind in ("hover", "chooser", "temp", "drag"):
                self.page.gestures.end_gesture()
            else:
                g.apply = None
        if not self.page.gestures.rank_rendering:
            self.page.gestures.rank_remove = None

    def _validate_gesture_source(self, lay) -> None:
        g = self.page.gestures.gesture
        if g is not None and g.source is not None:
            src_kind = next((cb.kind for cb in lay.cells if cb.id == g.source), None)
            if src_kind is None or (
                g.source in self.page.rec.cells and self.page.rec.cells[g.source].kind != src_kind
            ):
                self.page.gestures.end_gesture()

    def render(self):
        self._end_stale_gestures()
        self.page.building = True
        try:
            self.apply_view_classes()
            prev = self.page.last_lay.identities if self.page.last_lay is not None else None
            cold = self.page.last_lay is None
            lay = self.page.editor.layout(prev_ids=prev, preview_remove=self.page.gestures.rank_remove)
            self.page.last_lay = lay
            self.page.rec.pretransform = lay.pretransform
            cur_ids = frozenset(cb.id for cb in lay.cells)
            self._newborn_ids = cur_ids - self._prev_cell_ids
            fx, fy = lay.freeze_x, lay.freeze_y
            self._size_panes(lay, fx, fy)
            seen = set()

            self._render_lines(lay, fx, fy, seen)
            self._render_blocks(lay, fx, fy, seen)
            self._validate_gesture_source(lay)
            amber, red = self.page.gestures.compute_rings(lay)
            self._last_rings = (amber, red)
            self._render_cells(lay, fx, fy, seen, amber, red, cold, structural=True)
            self._sync_mean_damage_tips()
            self._sync_pretransform_help(lay.pretransform)
            self._sync_chrome(lay, fy)
            self._prev_cell_ids = cur_ids
            self._virt_for = self._viewport
        finally:
            self.page.building = False
        # NiceGUI: run_javascript from inside a handler-driven render hits a torn-down slot context
        # under the User test harness (no live client), so this browser-only scrim teardown is skipped.
        if not helpers.is_user_simulation():
            self.page.page_client.run_javascript(
                "window.rttBusy && window.rttBusy.done();"
                " window.rttScheduleReveal && window.rttScheduleReveal()"
            )
        self._schedule_fill(lay)

    def _schedule_fill(self, lay) -> None:
        self._fill_gen += 1
        if helpers.is_user_simulation():
            return
        if any(cb.id not in self.page.rec.entities for cb in lay.cells):
            background_tasks.create(self._fill_offscreen(self._fill_gen))

    async def _fill_offscreen(self, gen) -> None:
        while self._fill_gen == gen:
            lay = self.page.last_lay
            if lay is None:
                return
            fx, fy = lay.freeze_x, lay.freeze_y
            pending = [cb for cb in lay.cells if cb.id not in self.page.rec.entities]
            if not pending:
                return
            amber, red = self._last_rings
            with self.page.page_client:
                self.page.building = True
                self._revirtualizing = True
                try:
                    for cb in pending[:_FILL_CHUNK]:
                        container = _freeze_container(cb, fx, fy)
                        self._make_cell_if_new(cb, container, cold=False, structural=False)
                        top = cb.y - (fy if container in ("body", "row") else 0)
                        geo = (
                            f"left:0; top:0; transform:translate({cb.x}px,{top}px); "
                            f"width:{cb.w}px; height:{cb.h}px"
                        )
                        self.page.rec.entities[cb.id].el.style(geo)
                        self.page.rec.entities[cb.id].styled = geo
                        self._update_cell_content(cb)
                        self.page.gestures.paint_cell(cb.id, amber, red)
                finally:
                    self.page.building = False
                    self._revirtualizing = False
            await asyncio.sleep(0)

    def _scrolled_past_overscan(self, vp, ref) -> bool:
        return (
            abs(vp[0] - ref[0]) >= _VIRT_REVIRT_STEP
            or abs(vp[1] - ref[1]) >= _VIRT_REVIRT_STEP
            or vp[2] != ref[2]
            or vp[3] != ref[3]
        )

    def _on_viewport(self, e) -> None:
        a = e.args
        try:
            vp = (float(a["l"]), float(a["t"]), float(a["w"]), float(a["h"]))
        except (KeyError, TypeError, ValueError):
            return
        self._viewport = vp
        if self._virt_for is None or self._scrolled_past_overscan(vp, self._virt_for):
            with self.page.page_client:
                self._revirtualize()

    def _revirtualize(self) -> None:
        lay = self.page.last_lay
        if lay is None:
            return
        self.page.rec.pretransform = lay.pretransform
        self.page.building = True
        self._revirtualizing = True
        try:
            fx, fy = lay.freeze_x, lay.freeze_y
            seen: set = set()
            amber, red = self._last_rings
            self._render_lines(lay, fx, fy, seen)
            self._render_blocks(lay, fx, fy, seen)
            self._render_cells(lay, fx, fy, seen, amber, red, cold=False, structural=False)
        finally:
            self.page.building = False
            self._revirtualizing = False
        self._virt_for = self._viewport
