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

# Viewport virtualization: only body-pane cells/lines/blocks whose geometry intersects the visible
# scroll rectangle (inflated by _VIRT_OVERSCAN on every edge) are materialized; off-screen ones are
# released by render()'s existing drop sweep and rebuilt when scrolled back. _VIRT_VIEWPORT0 is the
# assumed viewport for the cold paint, before the client has reported its real one — bounded so the
# initial paint builds only the top-left region, then a real-viewport report fills the rest. Tests run
# with no live browser (no scroll events fire), so the render harness sets RTT_VIRT_VIEWPORT to a huge
# size: the filter still runs, but admits the whole grid, keeping the element-tree assertions intact.
_VIRT_OVERSCAN = 600.0
_VIRT_VIEWPORT0 = (1680.0, 1050.0)
_VIRT_REVIRT_STEP = 200.0  # ignore scroll deltas smaller than this — the overscan already covers them
_FILL_CHUNK = 80  # off-screen cells the background fill builds per event-loop yield (keeps it snappy)


def _initial_viewport() -> tuple[float, float, float, float]:
    # the cold-paint viewport (scrollLeft, scrollTop, clientW, clientH), before the client reports its
    # real one. RTT_VIRT_VIEWPORT="WxH" overrides the assumed size — the render-test harness sets it
    # huge so the whole grid materializes; production uses the bounded default so the cold paint is
    # cheap and a real-viewport report fills the rest.
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
        # Viewport virtualization state. _viewport is the visible scroll rectangle the client last
        # reported (assumed for the cold paint until then); _virt_for is the viewport the body cells
        # were last materialized against, so a scroll within the overscan margin skips revirtualizing.
        # _newborn_ids are the cells born by the latest structural render (layout-diff) — only those
        # take the withhold→reveal entrance, never a cell merely scrolled into view. _last_rings caches
        # the rings so a scroll revirtualize repaints without re-running the (state-mutating) gesture
        # hypotheticals. _revirtualizing tags scrolled-in cells so they appear at once (no rtt-in fade).
        self._viewport = _initial_viewport()
        self._virt_for: tuple | None = None
        self._revirtualizing = False
        self._newborn_ids: frozenset[str] = frozenset()
        self._prev_cell_ids: frozenset[str] = frozenset()
        self._last_rings: tuple = (frozenset(), frozenset())
        self._fill_gen = 0  # bumped each render; a background fill bails once it no longer matches

    def request_render(self, after=None):
        # schedule an off-loop commit render; a request arriving while one is in flight collapses
        # into a single trailing rebuild (the state it lands on is the only one that matters).
        # ``after`` runs on the loop once render() has rebuilt — for the few commits with a
        # synchronous tail that reads the fresh layout (a draft column materializing then rebasing
        # its edit gesture off last_lay).
        if helpers.is_user_simulation():
            # the in-process User test harness drives clicks/edits and inspects the DOM right after,
            # with no chance for a background task to run — and there is no real socket to protect.
            # Render synchronously there: tests see the same immediate rebuild they always did, and
            # the off-loop machinery (a production websocket concern) is exercised by the live probe.
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
                    # warm the tuning memo off the loop; the result is discarded — render() below
                    # recomputes the layout, now a cache hit. (editor.layout is read-only, and the
                    # mutation that triggered this already ran synchronously in the handler.)
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
        # Two of the `interface` Show behaviours gate the whole app through a single <body> class each,
        # so one CSS rule (assets/rtt.css) handles every element: `animations` off adds rtt-no-anim
        # (which zeroes the --t transition var, so every change snaps instead of sliding/fading) and
        # `tooltips` off adds rtt-no-tooltips (which hides every .q-tooltip). Unlike dark mode these
        # live in editor.settings — toggled in the Show panel, so select-all / Reset reach them — so
        # render() re-applies them after any toggle (and on the initial build, before cells animate in).
        # The third behaviour, preview_highlighting, has no body class: it's gated in Python at the
        # preview source (compute_rings + the hover handlers) so no ring or reflow is even produced.
        # render() can run OFF the loop (the _commit_render background task — every act()-driven commit:
        # reset, undo/redo, a structural edit), where the slot stack is empty and ui.query would raise
        # "slot stack ... is empty", aborting the whole render (grid never updates, busy scrim never
        # clears). Enter the captured page client so the <body> query resolves; in the synchronous /
        # test path this just nests harmlessly inside the already-live slot.
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
            if self.page.rec.entity(eid).styled != sty:  # only restyle a line that actually moved
                self.page.rec.entities[eid].el.style(sty)
                self.page.rec.entities[eid].styled = sty

        for ln in lay.lines:
            x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
            y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
            # Gridlines, washes and boxes are NOT virtualized — there are only ~O(rows+cols) of them
            # (a few hundred), cheap to build once and keep. Virtualizing them was a mistake: their
            # eviction left the grid's lines/colour-washes blanking on scroll (the body cells are the
            # bulk and the only thing worth virtualizing). So a body line always builds.
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
            # position via transform:translate (anchored at left:0;top:0), so a wash/box that SHIFTS
            # on a reflow rides the compositor like the cells; its size (a wash growing to cover a new
            # column) stays on width/height — unavoidably a layout op, but the shift is the common case.
            style = f"left:0; top:0; transform:translate({bl.x}px,{bl.y - shift}px); width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:
                style += f"; background:var(--wash-{bl.tint})"
            if (
                self.page.rec.entity(eid).styled != style
            ):  # only restyle a block that actually moved/recoloured
                self.page.rec.entities[eid].el.style(style)
                self.page.rec.entities[eid].styled = style

        for bl in lay.blocks:
            for pane in _block_panes(bl, fx, fy):  # washes/boxes aren't virtualized (see _render_lines)
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
                self.page.rec.entities[cb.id].el.classes(add="rtt-noentry")  # scrolled-in: appear at once
            # two-step entrance: a cell BORN by a STRUCTURAL render — present in the new layout, absent
            # from the previous one (_newborn_ids) — is WITHHELD (.rtt-withhold → opacity 0) while the
            # existing cells slide to open the room, and only fades in once the reflow has SETTLED. A
            # retuning commit can render in stages (the handler's render, then the off-loop retune
            # render), so a fixed delay would reveal it mid-expansion — instead rttScheduleReveal
            # (pushed at the end of every render) debounces the reveal, firing one beat after renders
            # STOP. A cell merely SCROLLED into view is not new content (it existed, just unmaterialized
            # under virtualization), so it appears at once; so do a PENDING draft (typeable immediately)
            # and the cold first paint (no room to make yet).
            if structural and not cold and not cb.pending and cb.id in self._newborn_ids:
                self.page.rec.entities[cb.id].el.classes(add="rtt-withhold")

    def _update_cell_content(self, cb) -> None:
        # content depends on the cell's value fields AND its w/h (width-fitted faces re-fit on
        # resize), so the signature carries both; audio rides along (a retune rebakes the pitch).
        # BUT an interactive cell — one carrying an input, select, checkbox or fraction-mode box —
        # can have its DOM changed by the USER (typing) or hover JS between renders, so its cached
        # signature no longer reflects the live DOM. Such a cell is always re-asserted, so an
        # improper-commit REVERT restores the box even though its value is unchanged from the last
        # render (the bug that surfaced here). Read-only display cells — the vast majority — are
        # only the server's to change, so the cache safely skips them.
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
            seen.add(cb.id)  # a current-layout cell is VALID — never dropped; only stale cells go
            container = _freeze_container(cb, fx, fy)
            # Virtualize the body pane to keep the COLD paint cheap: BUILD a new body cell only when it
            # is on screen (visible rect + overscan); a new off-screen one is deferred to the background
            # fill (_fill_offscreen), which materializes the rest just after the first paint. An
            # ALREADY-built cell, by contrast, is always repositioned + refreshed even off-screen, so a
            # structural reflow can't strand a retained cell at a stale spot — and the change-guards make
            # an unmoved cell a no-op. Off-screen cells are never EVICTED (that re-blank on scroll-back
            # was the bug); the drop sweep below removes only cells gone from the layout. Frozen
            # corner/col/row strips and pending drafts always build.
            if (
                cb.id not in self.page.rec.entities
                and container == "body"
                and not cb.pending
                and not self._body_visible(cb.x, cb.y, cb.w, cb.h, fy)
            ):
                continue
            self._make_cell_if_new(cb, container, cold, structural)
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner. Each reconcile step (reposition,
            # refresh content, repaint rings) runs only when its own signature changed, so an
            # interaction that moves a handful of cells doesn't re-run the whole page's per-cell work.
            top = cb.y - (fy if container in ("body", "row") else 0)
            # position via transform:translate (anchored at the container origin) rather than left/top,
            # so a reflow animates on the COMPOSITOR (the .rtt-cell transition rides `transform`) instead
            # of left/top — which would re-run layout every frame for every moving cell, the jank when a
            # basis/column change shifts most of the grid at once. Size still rides width/height.
            geo = f"left:0; top:0; transform:translate({cb.x}px,{top}px); width:{cb.w}px; height:{cb.h}px"
            if self.page.rec.entity(cb.id).styled != geo:
                self.page.rec.entities[cb.id].el.style(geo)
                self.page.rec.entities[cb.id].styled = geo
            self._update_cell_content(cb)
            self.page.gestures.paint_cell(cb.id, amber, red)  # self-guards on ring_sig (no-op when unchanged)

        for eid in [e for e in self.page.rec.entities if e not in seen]:
            self.page.rec.drop(eid)

    def _end_stale_gestures(self) -> None:
        # Renders end gestures that don't render: a render arriving while a hover / chooser /
        # temp / drag gesture is live — and NOT initiated by that gesture's own handler
        # (gesture_render) — is by definition an external commit or unrelated rebuild, so the
        # gesture ends here, structurally, whatever path the commit took (act, a chooser's
        # on_change, a Show toggle, the debounced target commit...). end_gesture restores a held
        # token FIRST, so the layout below builds from the real document. The edit/wheel gestures
        # legitimately render mid-gesture (their commits) and end on blur/mouseleave instead —
        # but any doc-moving render consumes a pending edit candidate (it is stale once the doc
        # moves; the baseline diff takes over, and no hypothetical solve runs inside a commit).
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
            cold = self.page.last_lay is None  # the first render: every cell is new, so it must NOT
            #                                     stagger (no room to make yet) — the whole grid paints at once
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
        # clear the busy scrim: this render is the result the user was waiting on, so whatever the
        # client armed (see _BUSY_JS) comes down now. The message rides out with this render's DOM
        # patch, so the scrim stays up across the patch and lifts once the new grid is on screen.
        # Skipped under the User test harness, where there's no live client (and run_javascript from
        # inside a handler-driven render hits a torn-down slot context); the scrim is browser-only.
        if not helpers.is_user_simulation():
            self.page.page_client.run_javascript(
                "window.rttBusy && window.rttBusy.done();"
                " window.rttScheduleReveal && window.rttScheduleReveal()"
            )
        self._schedule_fill(lay)

    def _schedule_fill(self, lay) -> None:
        # After the cheap viewport-only paint, materialize the rest of the body OFF the critical path so
        # forward-scrolling is never blank: a background task builds the deferred off-screen cells in
        # chunks, yielding the loop between chunks. Bumping _fill_gen supersedes any fill still running
        # for an older layout. Skipped under the test harness (synchronous, and its huge viewport has
        # already built everything) and when nothing is deferred.
        self._fill_gen += 1
        if helpers.is_user_simulation():
            return
        if any(cb.id not in self.page.rec.entities for cb in lay.cells):
            background_tasks.create(self._fill_offscreen(self._fill_gen))

    async def _fill_offscreen(self, gen) -> None:
        # Build the not-yet-materialized cells a chunk at a time, yielding between chunks so scrolls,
        # edits and the heartbeat keep flowing. Only ADDS cells (skips any already built by a scroll
        # revirtualize), never drops, so it can't fight the live view; a structural render bumps
        # _fill_gen and this loop exits, the new render scheduling a fresh fill for the new layout.
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
                self._revirtualizing = True  # filled cells are existing content → appear at once
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
        # the viewport moved or resized enough that the materialized band may no longer cover it. A
        # scroll within _VIRT_REVIRT_STEP is already absorbed by the overscan, so it skips the rebuild;
        # any size change re-materializes (a resize changes which cells fit).
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
        # Give the just-scrolled-into-view region priority while the background fill is still running:
        # materialize its body cells NOW, against the CACHED layout (a scroll must never re-run the RTT
        # solve). Reuses the cached rings, since recomputing them would re-run the gesture hypotheticals
        # (which mutate and restore editor state). Newly visible cells appear at once (structural=False →
        # never withheld); nothing is evicted (re-blanking on scroll-back was the bug), so a scroll only
        # ever ADDS — the drop sweep removes only cells gone from the layout, of which a scroll has none.
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
