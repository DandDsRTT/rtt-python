from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from nicegui import background_tasks, helpers

from rtt.app import _rendering_ops, rendering_chrome
from rtt.app.render_html import (
    _freeze_container,
    _rect_in_view,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rtt.app.editor import Editor
    from rtt.app.gestures import GestureController
    from rtt.app.page_chrome import PageChrome
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.reconciler import _Reconciler

_log = logging.getLogger(__name__)

_VIRT_OVERSCAN = 600.0
_VIRT_VIEWPORT0 = (1680.0, 1050.0)
_VIRT_REVIRT_STEP = 200.0
_FILL_CHUNK = 80


def _initial_viewport() -> tuple[float, float, float, float]:
    spec = os.environ.get("RTT_VIRT_VIEWPORT", "")
    if spec:
        width, height = (float(n) for n in spec.lower().split("x"))
    else:
        width, height = _VIRT_VIEWPORT0
    return (0.0, 0.0, width, height)


class Renderer:
    def __init__(
        self,
        editor: Editor,
        reconciler: _Reconciler,
        gestures: GestureController,
        chrome: PageChrome,
        runtime: PageRuntime,
        sync_show_availability: Callable[[], None],
    ) -> None:
        self._editor = editor
        self._rec = reconciler
        self._gestures = gestures
        self._chrome = chrome
        self._runtime = runtime
        self._sync_availability = sync_show_availability
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
                prev = (
                    self._runtime.last_lay.identities
                    if self._runtime.last_lay is not None
                    else None
                )
                try:
                    await asyncio.to_thread(self._editor.layout, prev_ids=prev)
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
        _rendering_ops.apply_view_classes(self._editor, self._runtime)

    def _body_visible(self, x, y, width, height, freeze_y) -> bool:
        return _rect_in_view(x, y, width, height, freeze_y, self._viewport, _VIRT_OVERSCAN)

    def render(self):
        _rendering_ops.end_stale_gestures(self._gestures)
        with self._runtime.building_guard():
            self.apply_view_classes()
            prev = self._runtime.last_lay.identities if self._runtime.last_lay is not None else None
            cold = self._runtime.last_lay is None
            lay = self._editor.layout(prev_ids=prev, preview_remove=self._gestures.rank_remove)
            self._runtime.set_last_lay(lay)
            self._rec.pretransform = lay.pretransform
            cur_ids = frozenset(cell_box.id for cell_box in lay.cells)
            self._newborn_ids = cur_ids - self._prev_cell_ids
            freeze_x, freeze_y = lay.freeze_x, lay.freeze_y
            _rendering_ops.size_panes(self._chrome, lay, freeze_x, freeze_y)
            seen: set = set()

            _rendering_ops.render_lines(self, lay, seen)
            _rendering_ops.render_blocks(self, lay, seen)
            _rendering_ops.validate_gesture_source(self._gestures, self._rec, lay)
            amber, red = self._gestures.compute_rings(lay)
            self._last_rings = (amber, red)
            _rendering_ops.render_cells(self, lay, seen, (amber, red, cold, True))
            rendering_chrome.sync_mean_damage_tips(self._rec, self._editor)
            rendering_chrome.sync_pretransform_help(self._rec, lay.pretransform)
            rendering_chrome.sync_chrome(self, lay, freeze_y)
            self._prev_cell_ids = cur_ids
            self._virt_for = self._viewport
        # NiceGUI: run_javascript from inside a handler-driven render hits a torn-down slot context
        # under the User test harness (no live client), so this browser-only scrim teardown is skipped.
        if not helpers.is_user_simulation():
            self._runtime.page_client.run_javascript(
                "window.rttBusy && window.rttBusy.done();"
                " window.rttScheduleReveal && window.rttScheduleReveal()"
            )
        self._schedule_fill(lay)

    def _schedule_fill(self, lay) -> None:
        self._fill_gen += 1
        if helpers.is_user_simulation():
            return
        if any(cell_box.id not in self._rec.entities for cell_box in lay.cells):
            background_tasks.create(self._fill_offscreen(self._fill_gen))

    async def _fill_offscreen(self, gen) -> None:
        while self._fill_gen == gen:
            lay = self._runtime.last_lay
            if lay is None:
                return
            freeze_x, freeze_y = lay.freeze_x, lay.freeze_y
            pending = [cell_box for cell_box in lay.cells if cell_box.id not in self._rec.entities]
            if not pending:
                return
            paint = (freeze_y, False, self._last_rings)
            with self._runtime.page_client, self._runtime.building_guard():
                self._revirtualizing = True
                try:
                    for cell_box in pending[:_FILL_CHUNK]:
                        container = _freeze_container(cell_box, freeze_x, freeze_y)
                        _rendering_ops.place_cell(self, cell_box, container, paint)
                finally:
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
            with self._runtime.page_client:
                self._revirtualize()

    def _revirtualize(self) -> None:
        lay = self._runtime.last_lay
        if lay is None:
            return
        self._rec.pretransform = lay.pretransform
        with self._runtime.building_guard():
            self._revirtualizing = True
            try:
                seen: set = set()
                amber, red = self._last_rings
                _rendering_ops.render_lines(self, lay, seen)
                _rendering_ops.render_blocks(self, lay, seen)
                _rendering_ops.render_cells(self, lay, seen, (amber, red, False, False))
            finally:
                self._revirtualizing = False
        self._virt_for = self._viewport
