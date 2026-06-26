from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nicegui import ui

from rtt.app import presets, service, spreadsheet_text
from rtt.app.page_assets import _Gesture, _hover_index, _option_key, cb_method

if TYPE_CHECKING:
    from rtt.app.editing import EditController
    from rtt.app.editor import Editor
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.reconciler import _Reconciler
    from rtt.app.rendering import Renderer

_log = logging.getLogger(__name__)


class GestureController:
    def __init__(self, editor: Editor, runtime: PageRuntime) -> None:
        self._editor = editor
        self._runtime = runtime
        self._rec: _Reconciler = None
        self._renderer: Renderer = None
        self._edits: EditController = None
        self.gesture = None
        self.gesture_rendering = False
        self.rank_remove = None
        self.rank_rendering = False
        self.drag_src = None
        self.reorder_dst = None

    def bind(self, rec: _Reconciler, renderer: Renderer, edits: EditController) -> None:
        self._rec = rec
        self._renderer = renderer
        self._edits = edits

    def gesture_render(self):
        self.gesture_rendering = True
        try:
            self._renderer.render()
        finally:
            self.gesture_rendering = False

    def end_gesture(self):
        g, self.gesture = self.gesture, None
        if g is not None and g.token is not None:
            self._editor.restore_for_preview(g.token)
        return g

    def end_chooser_gesture(self):
        if self.gesture is not None and self.gesture.kind == "chooser":
            self.end_gesture()

    def compute_rings(self, lay):
        if not self._editor.settings["preview_highlighting"]:
            return frozenset(), frozenset()
        static_red = frozenset(cb.id for cb in lay.cells if cb.preview_remove)
        static_amber = frozenset(cb.id for cb in lay.cells if cb.preview_change)
        amber, red = self._gesture_rings(lay)
        pending = frozenset(cb.id for cb in lay.cells if cb.pending)
        return (amber | static_amber) - pending, (red | static_red) - pending

    def _gesture_rings(self, lay):
        g = self.gesture
        if g is None:
            return frozenset(), frozenset()
        if g.apply is not None:
            base = g.baseline if g.baseline is not None else lay
            token = self._editor.capture_for_preview()
            try:
                g.apply()
                hyp = self._editor.layout(prev_ids=base.identities)
                amber = spreadsheet_text.changed_cell_ids(base, hyp)
                red = spreadsheet_text.removed_cell_ids(lay, hyp)
            finally:
                self._editor.restore_for_preview(token)
            return amber - {g.source}, red
        if g.baseline is not None:
            amber = spreadsheet_text.changed_cell_ids(g.baseline, lay) - {g.source}
            if g.target_pred is not None:
                amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
            return amber, frozenset()
        return frozenset(), frozenset()

    def paint_cell(self, eid, amber, red):
        el = self._rec.entity(eid).el
        if el is None:
            return
        rsig = (eid in amber, eid in red)
        if self._rec.entity(eid).ring_sig == rsig:
            return
        el.classes(
            add="rtt-preview-change" if eid in amber else "",
            remove="" if eid in amber else "rtt-preview-change",
        )
        el.classes(
            add="rtt-preview-remove" if eid in red else "",
            remove="" if eid in red else "rtt-preview-remove",
        )
        self._rec.entities[eid].ring_sig = rsig

    def paint_rings(self):
        lay = self._runtime.last_lay
        if lay is None:
            return
        amber, red = self.compute_rings(lay)
        for cb in lay.cells:
            self.paint_cell(cb.id, amber, red)

    def take_over_gesture(self):
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self.gesture_render()

    def edit_candidate(self, apply):
        g = self.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        self.paint_rings()

    def rebase_edit_gesture(self):
        g = self.gesture
        if g is not None and g.kind == "edit":
            g.baseline = self._runtime.last_lay
            self.paint_rings()

    def end_commit_gestures(self):
        if self.gesture is not None and self.gesture.kind in (
            "hover",
            "chooser",
            "temp",
            "drag",
        ):
            self.end_gesture()
        self.rank_remove = None

    @cb_method
    def on_cell_focus(self, cid):
        self.take_over_gesture()
        self.gesture = _Gesture(kind="edit", source=cid, baseline=self._runtime.last_lay)

    @cb_method
    def on_cell_blur(self, cid=None):
        g = self.gesture
        if g is not None and g.kind in ("edit", "wheel") and (cid is None or g.source == cid):
            self.end_gesture()
            self.paint_rings()

    @cb_method
    def combine_begin(self):
        self.end_gesture()
        self.gesture = _Gesture(
            kind="drag", token=self._editor.capture_for_preview(), baseline=self._runtime.last_lay
        )

    @cb_method
    def combine_preview(self, apply, target_pred=None):
        g = self.gesture
        if g is None or g.kind != "drag":
            return
        self._editor.restore_for_preview(g.token)
        g.target_pred = target_pred if apply is not None else None
        if apply is not None:
            apply()
        self.gesture_render()

    @cb_method
    def combine_commit(self, apply):
        g = self.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self._edits.act(apply)

    @cb_method
    def combine_end(self):
        g = self.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self._renderer.render()

    @cb_method
    def control_hover(self, apply):
        if not self._editor.settings["preview_highlighting"]:
            return
        g = self.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        prev = None
        if g is not None and g.kind == "wheel":
            prev = g
        elif g is not None:
            self.take_over_gesture()
        self.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        self.paint_rings()

    @cb_method
    def control_unhover(self):
        g = self.gesture
        if g is None or g.kind != "hover":
            return
        self.gesture = g.prev
        self.paint_rings()

    @cb_method
    def rank_remove_hover(self, axis, idx):
        if not self._editor.settings["preview_highlighting"]:
            return
        if self.gesture is not None and self.gesture.kind in ("edit", "drag"):
            return
        self.rank_remove = (axis, idx)
        self.rank_rendering = True
        try:
            self._renderer.render()
        finally:
            self.rank_rendering = False

    @cb_method
    def rank_remove_unhover(self):
        if self.rank_remove is not None:
            self.rank_remove = None
            self._renderer.render()

    def _cell_xy(self, lay, eid):
        for c in lay.cells:
            if c.id == eid:
                return (round(c.x), round(c.y))
        return None

    def chooser_hover(self, cid, apply):
        if not self._editor.settings["preview_highlighting"]:
            return
        g = self.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        if g is not None and (g.kind != "chooser" or g.source != cid):
            self.take_over_gesture()
        if self.gesture is None:
            self.gesture = _Gesture(
                kind="chooser",
                source=cid,
                token=self._editor.capture_for_preview(),
                baseline=self._runtime.last_lay,
            )
        g = self.gesture
        self._editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        if apply is None:
            g.apply = None
            self.paint_rings()
            return
        base = g.baseline
        apply()
        hyp = self._editor.layout(prev_ids=base.identities if base is not None else None)
        disturbs = base is not None and (
            spreadsheet_text.removed_cell_ids(base, hyp)
            or self._cell_xy(base, cid) != self._cell_xy(hyp, cid)
        )
        if disturbs:
            self._editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def chooser_unhover(self):
        g = self.gesture
        if g is None or g.kind != "chooser":
            return
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self._renderer.render()
        else:
            self.paint_rings()

    def _end_temperament_preview(self):
        g = self.gesture
        if g is None or g.kind != "temp":
            return
        was = self.end_gesture()
        if was.reflowed:
            self._renderer.render()
        else:
            self.paint_rings()

    def _temperament_hover_preview(self, key):
        if key not in presets.TEMPERAMENT_COMMAS:
            self._end_temperament_preview()
            return
        g = self.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return
            self.end_gesture()
            g = self.gesture = _Gesture(
                kind="temp", token=self._editor.capture_for_preview(), baseline=self._runtime.last_lay
            )
        self._editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        base = self._editor.state
        self._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        hyp = self._editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self._editor.restore_for_preview(g.token)
            g.apply = lambda: self._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def _ensure_temp_gesture(self):
        g = self.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return None
            self.end_gesture()
            g = self.gesture = _Gesture(
                kind="temp", token=self._editor.capture_for_preview(), baseline=self._runtime.last_lay
            )
        self._editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        return g

    def _subpick_hover_preview(self, cid, value):
        if value is None:
            self._end_temperament_preview()
            return
        db = self._editor.state.domain_basis
        draft = cid in ("etpick:draft", "commapick:draft")
        idx = None
        if not draft:
            idx = self._runtime.token_index(cid, "gens" if cid.startswith("etpick:") else "commas")
            if idx is None:
                self._end_temperament_preview()
                return
        g = self._ensure_temp_gesture()
        if g is None:
            return
        if draft:
            self._preview_subpick_draft(cid, value, db, g)
        else:
            self._preview_subpick_pick(cid, value, db, idx, g)

    def _preview_subpick_draft(self, cid, value, db, g) -> None:
        if cid == "etpick:draft":
            self._editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
        else:
            self._editor.pending_comma = list(presets.comma_value_to_vector(value, db))
        g.apply = None
        g.reflowed = True
        self.gesture_render()

    def _preview_subpick_pick(self, cid, value, db, idx, g) -> None:
        if cid.startswith("etpick:"):

            def apply(i=idx, v=value):
                return self._editor.set_mapping_row(i, presets.et_value_to_val(v, db))
        else:

            def apply(c=idx, v=value):
                return self._editor.set_comma(c, presets.comma_value_to_vector(v, db))

        base = self._editor.state
        apply()
        hyp = self._editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self._editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    @cb_method
    def on_chooser_hover(self, cid, detail):
        entry = self._rec.handles(cid).chooser.select
        sel = entry[1] if isinstance(entry, tuple) else entry
        if not isinstance(sel, ui.select):
            return
        index = _hover_index(detail)
        if index is not None and self._rec.handles(cid).popup_state == "closed":
            return
        if cid.startswith(("etpick:", "commapick:")):
            self._subpick_hover_preview(cid, _option_key(sel, index) if index is not None else None)
            return
        if cid.startswith("preset:temperament"):
            self._temperament_hover_preview(_option_key(sel, index))
            return
        if index is None or not sel.enabled:
            self.chooser_unhover()
            return
        self._hover_value_chooser(cid, sel, index, entry)

    def _hover_value_chooser(self, cid, sel, index, entry) -> None:
        if cid == "preset:target":
            family = _option_key(sel, index)
            if family not in presets.TARGET_SETS:
                self.chooser_unhover()
                return
            spec = service.target_spec(family, entry[0].value)
            self.chooser_hover(cid, lambda: self._editor.set_target_spec(spec))
            return
        apply = self._edits.candidate_apply(cid, _option_key(sel, index))
        if apply is None:
            self.chooser_unhover()
            return
        self.chooser_hover(cid, apply)

    @cb_method
    def on_popup(self, cid, is_open):
        self._rec.cells[cid].popup_state = "open" if is_open else "closed"
        if not is_open:
            self.on_chooser_hover(cid, None)

    @cb_method
    def gentuning_hover(self, cid):
        g = self.gesture
        if g is not None and g.kind in ("edit", "drag", "hover"):
            return
        self.take_over_gesture()
        self.gesture = _Gesture(kind="wheel", source=cid, baseline=self._runtime.last_lay)

    @cb_method
    def gentuning_unhover(self, cid):
        g = self.gesture
        if g is None or g.kind != "wheel" or g.source != cid:
            return
        self.end_gesture()
        self.paint_rings()

    @cb_method
    def on_drag_start(self, lst, idx):
        self.drag_src = (lst, idx)
        self.reorder_dst = (lst, idx)
        self.end_gesture()
        self.gesture = _Gesture(
            kind="drag", token=self._editor.capture_for_preview(), baseline=self._runtime.last_lay
        )

    @cb_method
    def on_drag_enter(self, dst_list, dst_idx):
        g = self.gesture
        if (
            g is None
            or g.kind != "drag"
            or self.drag_src is None
            or (dst_list, dst_idx) == self.reorder_dst
        ):
            return
        self.reorder_dst = (dst_list, dst_idx)
        self._editor.restore_for_preview(g.token)
        idx = dst_idx if dst_idx is not None else (1 << 30)
        self._editor.move_interval(self.drag_src[0], self.drag_src[1], dst_list, idx)
        self.gesture_render()

    @cb_method
    def on_drag_end(self):
        if self.gesture is not None and self.gesture.kind == "drag":
            self.end_gesture()
            self._renderer.render()
        self.drag_src = None
        self.reorder_dst = None

    @cb_method
    def on_drop(self, dst_list, dst_idx):
        src = self.drag_src
        self.drag_src = None
        self.reorder_dst = None
        had_preview = self.gesture is not None and self.gesture.kind == "drag"
        if had_preview:
            self.end_gesture()
        if not src:
            if had_preview:
                self._renderer.render()
            return
        idx = dst_idx if dst_idx is not None else (1 << 30)
        if self._editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
            self._renderer.render()
