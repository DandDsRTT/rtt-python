from __future__ import annotations

import logging

from nicegui import ui

from rtt.app import (
    presets,
    spreadsheet_text,
)


from rtt.app.page_assets import (
    _hover_index,
    _option_key,
    _Gesture,
)

_log = logging.getLogger(__name__)


class GestureController:
    def __init__(self, page) -> None:
        self.page = page
        self.gesture_rendering = False
        # a comma−/mapping− hover's transient rank-removal preview — None | ("comma", idx) | ("row", idx).
        # Pure view state (not a gesture, not document state): render() threads it into the build so the
        # builder reflows the dual axis (the born generator/comma ghosts green, the leaver reds, the
        # survivors amber). Set on mouseenter, cleared on mouseleave and on any committing act().
        self.rank_remove = None
        self.rank_rendering = False
        self.drag_src = None
        self.reorder_dst = None

    def gesture_render(self):
        self.gesture_rendering = True
        try:
            self.page.renderer.render()
        finally:
            self.gesture_rendering = False

    def end_gesture(self):
        g, self.page.rec.gesture = self.page.rec.gesture, None
        if g is not None and g.token is not None:
            self.page.editor.restore_for_preview(g.token)
        return g

    def end_chooser_gesture(self):
        if self.page.rec.gesture is not None and self.page.rec.gesture.kind == "chooser":
            self.end_gesture()

    def compute_rings(self, lay):
        if not self.page.editor.settings["preview_highlighting"]:
            return frozenset(), frozenset()
        static_red = frozenset(cb.id for cb in lay.cells if cb.preview_remove)
        static_amber = frozenset(cb.id for cb in lay.cells if cb.preview_change)
        amber, red = self._gesture_rings(lay)
        pending = frozenset(cb.id for cb in lay.cells if cb.pending)
        return (amber | static_amber) - pending, (red | static_red) - pending

    def _gesture_rings(self, lay):
        g = self.page.rec.gesture
        if g is None:
            return frozenset(), frozenset()
        if g.apply is not None:
            base = g.baseline if g.baseline is not None else lay
            token = self.page.editor.capture_for_preview()
            try:
                g.apply()
                hyp = self.page.editor.layout(prev_ids=base.identities)
                amber = spreadsheet_text.changed_cell_ids(base, hyp)
                red = spreadsheet_text.removed_cell_ids(lay, hyp)
            finally:
                self.page.editor.restore_for_preview(token)
            return amber - {g.source}, red
        if g.baseline is not None:
            amber = spreadsheet_text.changed_cell_ids(g.baseline, lay) - {g.source}
            if g.target_pred is not None:
                amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
            return amber, frozenset()
        return frozenset(), frozenset()

    def paint_cell(self, eid, amber, red):
        # idempotently set one cell's ring classes from the computed sets. Self-guarded on the cached
        # ring state so an unchanged cell is skipped entirely (the common case — rings move only around
        # the gesture); both render()'s sweep and paint_rings()'s hover sweep go through here, so the
        # cache stays consistent whichever path painted last. (NiceGUI's classes() is itself change-
        # detected, so even an un-guarded no-op sends nothing over the socket — this skips the Python.)
        el = self.page.rec.els.get(eid)
        if el is None:
            return  # a ring id with no DOM element (nothing on screen to mark) — skip
        rsig = (eid in amber, eid in red)
        if self.page.rec.ring_sig.get(eid) == rsig:
            return
        el.classes(
            add="rtt-preview-change" if eid in amber else "",
            remove="" if eid in amber else "rtt-preview-change",
        )
        el.classes(
            add="rtt-preview-remove" if eid in red else "",
            remove="" if eid in red else "rtt-preview-remove",
        )
        self.page.rec.ring_sig[eid] = rsig

    def paint_rings(self):
        lay = self.page.last_lay
        if lay is None:
            return
        amber, red = self.compute_rings(lay)
        for cb in lay.cells:
            self.paint_cell(cb.id, amber, red)

    def take_over_gesture(self):
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self.gesture_render()

    def _edit_candidate(self, apply):
        g = self.page.rec.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        self.paint_rings()

    def _rebase_edit_gesture(self):
        g = self.page.rec.gesture
        if g is not None and g.kind == "edit":
            g.baseline = self.page.last_lay
            self.paint_rings()

    def _end_commit_gestures(self):
        # a commit ends any hover-family gesture FIRST — its rings are previews of a click that
        # has now landed (or been superseded), and a token gesture must restore the real document
        # before the action mutates it (e.g. Ctrl+Z while a temperament hover holds a hypothetical
        # doc). The edit/wheel gestures survive their own commits and end on blur/mouseleave.
        if self.page.rec.gesture is not None and self.page.rec.gesture.kind in (
            "hover",
            "chooser",
            "temp",
            "drag",
        ):
            self.end_gesture()
        self.rank_remove = None

    def on_cell_focus(self, cid):
        self.take_over_gesture()
        self.page.rec.gesture = _Gesture(kind="edit", source=cid, baseline=self.page.last_lay)

    def on_cell_blur(self, cid=None):
        g = self.page.rec.gesture
        if g is not None and g.kind in ("edit", "wheel") and (cid is None or g.source == cid):
            self.end_gesture()
            self.paint_rings()

    def combine_begin(self):
        self.end_gesture()
        self.page.rec.gesture = _Gesture(
            kind="drag", token=self.page.editor.capture_for_preview(), baseline=self.page.last_lay
        )

    def combine_preview(self, apply, target_pred=None):
        g = self.page.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.page.editor.restore_for_preview(g.token)
        g.target_pred = target_pred if apply is not None else None
        if apply is not None:
            apply()
        self.gesture_render()

    def combine_commit(self, apply):
        g = self.page.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self.page.edits.act(apply)

    def combine_end(self):
        g = self.page.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self.page.renderer.render()

    def control_hover(self, apply):
        if not self.page.editor.settings["preview_highlighting"]:
            return
        g = self.page.rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        prev = None
        if g is not None and g.kind == "wheel":
            prev = g
        elif g is not None:
            self.take_over_gesture()
        self.page.rec.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        self.paint_rings()

    def control_unhover(self):
        g = self.page.rec.gesture
        if g is None or g.kind != "hover":
            return
        self.page.rec.gesture = g.prev
        self.paint_rings()

    def rank_remove_hover(self, axis, idx):
        if not self.page.editor.settings["preview_highlighting"]:
            return
        if self.page.rec.gesture is not None and self.page.rec.gesture.kind in ("edit", "drag"):
            return
        self.rank_remove = (axis, idx)
        self.rank_rendering = True
        try:
            self.page.renderer.render()
        finally:
            self.rank_rendering = False

    def rank_remove_unhover(self):
        if self.rank_remove is not None:
            self.rank_remove = None
            self.page.renderer.render()

    def _cell_xy(self, lay, eid):
        for c in lay.cells:
            if c.id == eid:
                return (round(c.x), round(c.y))
        return None

    def chooser_hover(self, cid, apply):
        if not self.page.editor.settings["preview_highlighting"]:
            return
        g = self.page.rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        if g is not None and (g.kind != "chooser" or g.source != cid):
            self.take_over_gesture()
        if self.page.rec.gesture is None:
            self.page.rec.gesture = _Gesture(
                kind="chooser",
                source=cid,
                token=self.page.editor.capture_for_preview(),
                baseline=self.page.last_lay,
            )
        g = self.page.rec.gesture
        self.page.editor.restore_for_preview(g.token)
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
        hyp = self.page.editor.layout(prev_ids=base.identities if base is not None else None)
        disturbs = base is not None and (
            spreadsheet_text.removed_cell_ids(base, hyp)
            or self._cell_xy(base, cid) != self._cell_xy(hyp, cid)
        )
        if disturbs:
            self.page.editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def chooser_unhover(self):
        g = self.page.rec.gesture
        if g is None or g.kind != "chooser":
            return
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self.page.renderer.render()
        else:
            self.paint_rings()

    def _end_temperament_preview(self):
        g = self.page.rec.gesture
        if g is None or g.kind != "temp":
            return
        was = self.end_gesture()
        if was.reflowed:
            self.page.renderer.render()
        else:
            self.paint_rings()

    def _temperament_hover_preview(self, key):
        if key not in presets.TEMPERAMENT_COMMAS:
            self._end_temperament_preview()
            return
        g = self.page.rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return
            self.end_gesture()
            g = self.page.rec.gesture = _Gesture(
                kind="temp", token=self.page.editor.capture_for_preview(), baseline=self.page.last_lay
            )
        self.page.editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        base = self.page.editor.state
        self.page.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        hyp = self.page.editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self.page.editor.restore_for_preview(g.token)
            g.apply = lambda: self.page.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def _ensure_temp_gesture(self):
        g = self.page.rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return None
            self.end_gesture()
            g = self.page.rec.gesture = _Gesture(
                kind="temp", token=self.page.editor.capture_for_preview(), baseline=self.page.last_lay
            )
        self.page.editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        return g

    def _subpick_hover_preview(self, cid, value):
        if value is None:
            self._end_temperament_preview()
            return
        db = self.page.editor.state.domain_basis
        draft = cid in ("etpick:draft", "commapick:draft")
        idx = None
        if not draft:
            idx = self.page._token_index(cid, "gens" if cid.startswith("etpick:") else "commas")
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
            self.page.editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
        else:
            self.page.editor.pending_comma = list(presets.comma_value_to_vector(value, db))
        g.apply = None
        g.reflowed = True
        self.gesture_render()

    def _preview_subpick_pick(self, cid, value, db, idx, g) -> None:
        if cid.startswith("etpick:"):

            def apply(i=idx, v=value):
                return self.page.editor.set_mapping_row(i, presets.et_value_to_val(v, db))
        else:

            def apply(c=idx, v=value):
                return self.page.editor.set_comma(c, presets.comma_value_to_vector(v, db))

        base = self.page.editor.state
        apply()
        hyp = self.page.editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self.page.editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def on_chooser_hover(self, cid, detail):
        # the shared option-hover preview entry for every q-select armed via _arm_option_hover: the
        # delegation fires `opthover` at the chooser's cell wrap carrying the hovered option's positional
        # index in `detail` (-1 / None on leave). Map it back to the option's key through the live
        # select, then preview applying it. Temperament + the sub-pickers route to their own sticky
        # reflow path; the rest (including the TILT/OLD family) go through chooser_hover below, which
        # reflows a value-only pick and reddens one that would remove cells.
        entry = self.page.rec.selects.get(cid)
        sel = entry[1] if isinstance(entry, tuple) else entry
        if not isinstance(sel, ui.select):
            return
        index = _hover_index(detail)
        if index is not None and self.page.rec.popup_state.get(cid) == "closed":
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
            text = (entry[0].value or "").strip()
            try:
                spec = f"{int(float(text))}-{family}" if text else family
            except ValueError:
                spec = family
            self.chooser_hover(cid, lambda: self.page.editor.set_target_spec(spec))
            return
        apply = self.page.edits._candidate_apply(cid, _option_key(sel, index))
        if apply is None:
            self.chooser_unhover()
            return
        self.chooser_hover(cid, apply)

    def on_popup(self, cid, is_open):
        # a chooser's Quasar popup opened/closed: feed the server-side gate (see on_chooser_hover)
        # and treat the close as the gesture's leave — the option the pointer was on is gone, so a
        # live chooser/temperament preview ends (ungated; only positive arms are gated).
        self.page.rec.popup_state[cid] = "open" if is_open else "closed"
        if not is_open:
            self.on_chooser_hover(cid, None)

    def gentuning_hover(self, cid):
        g = self.page.rec.gesture
        if g is not None and g.kind in ("edit", "drag", "hover"):
            return
        self.take_over_gesture()
        self.page.rec.gesture = _Gesture(kind="wheel", source=cid, baseline=self.page.last_lay)

    def gentuning_unhover(self, cid):
        g = self.page.rec.gesture
        if g is None or g.kind != "wheel" or g.source != cid:
            return
        self.end_gesture()
        self.paint_rings()

    def on_drag_start(self, lst, idx):
        self.drag_src = (lst, idx)
        self.reorder_dst = (lst, idx)
        self.end_gesture()
        self.page.rec.gesture = _Gesture(
            kind="drag", token=self.page.editor.capture_for_preview(), baseline=self.page.last_lay
        )

    def on_drag_enter(self, dst_list, dst_idx):
        g = self.page.rec.gesture
        if (
            g is None
            or g.kind != "drag"
            or self.drag_src is None
            or (dst_list, dst_idx) == self.reorder_dst
        ):
            return
        self.reorder_dst = (dst_list, dst_idx)
        self.page.editor.restore_for_preview(g.token)
        idx = dst_idx if dst_idx is not None else (1 << 30)
        self.page.editor.move_interval(self.drag_src[0], self.drag_src[1], dst_list, idx)
        self.gesture_render()

    def on_drag_end(self):
        if self.page.rec.gesture is not None and self.page.rec.gesture.kind == "drag":
            self.end_gesture()
            self.page.renderer.render()
        self.drag_src = None
        self.reorder_dst = None

    def on_drop(self, dst_list, dst_idx):
        src = self.drag_src
        self.drag_src = None
        self.reorder_dst = None
        had_preview = self.page.rec.gesture is not None and self.page.rec.gesture.kind == "drag"
        if had_preview:
            self.end_gesture()
        if not src:
            if had_preview:
                self.page.renderer.render()
            return
        idx = dst_idx if dst_idx is not None else (1 << 30)
        if self.page.editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
            self.page.renderer.render()
