from __future__ import annotations

from nicegui import ui

from rtt.app import presets, service, spreadsheet_text
from rtt.app.page_assets import _Gesture, _hover_index, _option_key


def gesture_render(gc):
    gc.gesture_rendering = True
    try:
        gc._renderer.render()
    finally:
        gc.gesture_rendering = False


def take_over_gesture(gc):
    was = gc.end_gesture()
    if was is not None and was.reflowed:
        gesture_render(gc)


def paint_rings(gc):
    lay = gc._runtime.last_lay
    if lay is None:
        return
    amber, red = gc.compute_rings(lay)
    for cb in lay.cells:
        gc.paint_cell(cb.id, amber, red)


def gesture_rings(gc, lay):
    g = gc.gesture
    if g is None:
        return frozenset(), frozenset()
    if g.apply is not None:
        base = g.baseline if g.baseline is not None else lay
        token = gc._editor.capture_for_preview()
        try:
            g.apply()
            hyp = gc._editor.layout(prev_ids=base.identities)
            amber = spreadsheet_text.changed_cell_ids(base, hyp)
            red = spreadsheet_text.removed_cell_ids(lay, hyp)
        finally:
            gc._editor.restore_for_preview(token)
        return amber - {g.source}, red
    if g.baseline is not None:
        amber = spreadsheet_text.changed_cell_ids(g.baseline, lay) - {g.source}
        if g.target_pred is not None:
            amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
        return amber, frozenset()
    return frozenset(), frozenset()


def cell_xy(lay, eid):
    for c in lay.cells:
        if c.id == eid:
            return (round(c.x), round(c.y))
    return None


def chooser_hover(gc, cid, apply):
    if not gc._editor.settings["preview_highlighting"]:
        return
    g = gc.gesture
    if g is not None and g.kind in ("edit", "drag"):
        return
    if g is not None and (g.kind != "chooser" or g.source != cid):
        take_over_gesture(gc)
    if gc.gesture is None:
        gc.gesture = _Gesture(
            kind="chooser",
            source=cid,
            token=gc._editor.capture_for_preview(),
            baseline=gc._runtime.last_lay,
        )
    g = gc.gesture
    gc._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gc)
    if apply is None:
        g.apply = None
        paint_rings(gc)
        return
    base = g.baseline
    apply()
    hyp = gc._editor.layout(prev_ids=base.identities if base is not None else None)
    disturbs = base is not None and (
        spreadsheet_text.removed_cell_ids(base, hyp) or cell_xy(base, cid) != cell_xy(hyp, cid)
    )
    if disturbs:
        gc._editor.restore_for_preview(g.token)
        g.apply = apply
        paint_rings(gc)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gc)


def chooser_unhover(gc):
    g = gc.gesture
    if g is None or g.kind != "chooser":
        return
    was = gc.end_gesture()
    if was is not None and was.reflowed:
        gc._renderer.render()
    else:
        paint_rings(gc)


def end_temperament_preview(gc):
    g = gc.gesture
    if g is None or g.kind != "temp":
        return
    was = gc.end_gesture()
    if was.reflowed:
        gc._renderer.render()
    else:
        paint_rings(gc)


def temperament_hover_preview(gc, key):
    if key not in presets.TEMPERAMENT_COMMAS:
        end_temperament_preview(gc)
        return
    g = gc.gesture
    if g is None or g.kind != "temp":
        if g is not None and g.kind in ("edit", "drag"):
            return
        gc.end_gesture()
        g = gc.gesture = _Gesture(
            kind="temp", token=gc._editor.capture_for_preview(), baseline=gc._runtime.last_lay
        )
    gc._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gc)
    base = gc._editor.state
    gc._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
    hyp = gc._editor.state
    if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
        gc._editor.restore_for_preview(g.token)
        g.apply = lambda: gc._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        paint_rings(gc)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gc)


def ensure_temp_gesture(gc):
    g = gc.gesture
    if g is None or g.kind != "temp":
        if g is not None and g.kind in ("edit", "drag"):
            return None
        gc.end_gesture()
        g = gc.gesture = _Gesture(
            kind="temp", token=gc._editor.capture_for_preview(), baseline=gc._runtime.last_lay
        )
    gc._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gc)
    return g


def subpick_hover_preview(gc, cid, value):
    if value is None:
        end_temperament_preview(gc)
        return
    draft = cid in ("etpick:draft", "commapick:draft")
    idx = None
    if not draft:
        idx = gc._runtime.token_index(cid, "gens" if cid.startswith("etpick:") else "commas")
        if idx is None:
            end_temperament_preview(gc)
            return
    g = ensure_temp_gesture(gc)
    if g is None:
        return
    if draft:
        preview_subpick_draft(gc, cid, value)
    else:
        preview_subpick_pick(gc, cid, value, idx)


def preview_subpick_draft(gc, cid, value) -> None:
    db = gc._editor.state.domain_basis
    g = gc.gesture
    if cid == "etpick:draft":
        gc._editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
    else:
        gc._editor.pending_comma = list(presets.comma_value_to_vector(value, db))
    g.apply = None
    g.reflowed = True
    gesture_render(gc)


def preview_subpick_pick(gc, cid, value, idx) -> None:
    db = gc._editor.state.domain_basis
    g = gc.gesture
    if cid.startswith("etpick:"):

        def apply(i=idx, v=value):
            return gc._editor.set_mapping_row(i, presets.et_value_to_val(v, db))
    else:

        def apply(c=idx, v=value):
            return gc._editor.set_comma(c, presets.comma_value_to_vector(v, db))

    base = gc._editor.state
    apply()
    hyp = gc._editor.state
    if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
        gc._editor.restore_for_preview(g.token)
        g.apply = apply
        paint_rings(gc)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gc)


def hover_value_chooser(gc, cid, index) -> None:
    entry = gc._rec.handles(cid).chooser.select
    sel = entry[1] if isinstance(entry, tuple) else entry
    if cid == "preset:target":
        family = _option_key(sel, index)
        if family not in presets.TARGET_SETS:
            chooser_unhover(gc)
            return
        spec = service.target_spec(family, entry[0].value)
        chooser_hover(gc, cid, lambda: gc._editor.set_target_spec(spec))
        return
    apply = gc._edits.candidate_apply(cid, _option_key(sel, index))
    if apply is None:
        chooser_unhover(gc)
        return
    chooser_hover(gc, cid, apply)


def on_cell_focus(gc, cid):
    take_over_gesture(gc)
    gc.gesture = _Gesture(kind="edit", source=cid, baseline=gc._runtime.last_lay)


def on_cell_blur(gc, cid=None):
    g = gc.gesture
    if g is not None and g.kind in ("edit", "wheel") and (cid is None or g.source == cid):
        gc.end_gesture()
        paint_rings(gc)


def combine_begin(gc):
    gc.end_gesture()
    gc.gesture = _Gesture(
        kind="drag", token=gc._editor.capture_for_preview(), baseline=gc._runtime.last_lay
    )


def combine_preview(gc, apply, target_pred=None):
    g = gc.gesture
    if g is None or g.kind != "drag":
        return
    gc._editor.restore_for_preview(g.token)
    g.target_pred = target_pred if apply is not None else None
    if apply is not None:
        apply()
    gesture_render(gc)


def combine_commit(gc, apply):
    g = gc.gesture
    if g is None or g.kind != "drag":
        return
    gc.end_gesture()
    gc._edits.act(apply)


def combine_end(gc):
    g = gc.gesture
    if g is None or g.kind != "drag":
        return
    gc.end_gesture()
    gc._renderer.render()


def rank_remove_hover(gc, axis, idx):
    if not gc._editor.settings["preview_highlighting"]:
        return
    if gc.gesture is not None and gc.gesture.kind in ("edit", "drag"):
        return
    gc.rank_remove = (axis, idx)
    gc.rank_rendering = True
    try:
        gc._renderer.render()
    finally:
        gc.rank_rendering = False


def rank_remove_unhover(gc):
    if gc.rank_remove is not None:
        gc.rank_remove = None
        gc._renderer.render()


def on_chooser_hover(gc, cid, detail):
    entry = gc._rec.handles(cid).chooser.select
    sel = entry[1] if isinstance(entry, tuple) else entry
    if not isinstance(sel, ui.select):
        return
    index = _hover_index(detail)
    if index is not None and gc._rec.handles(cid).popup_state == "closed":
        return
    if cid.startswith(("etpick:", "commapick:")):
        subpick_hover_preview(gc, cid, _option_key(sel, index) if index is not None else None)
        return
    if cid.startswith("preset:temperament"):
        temperament_hover_preview(gc, _option_key(sel, index))
        return
    if index is None or not sel.enabled:
        chooser_unhover(gc)
        return
    hover_value_chooser(gc, cid, index)


def on_popup(gc, cid, is_open):
    gc._rec.cells[cid].popup_state = "open" if is_open else "closed"
    if not is_open:
        on_chooser_hover(gc, cid, None)


def gentuning_hover(gc, cid):
    g = gc.gesture
    if g is not None and g.kind in ("edit", "drag", "hover"):
        return
    take_over_gesture(gc)
    gc.gesture = _Gesture(kind="wheel", source=cid, baseline=gc._runtime.last_lay)


def gentuning_unhover(gc, cid):
    g = gc.gesture
    if g is None or g.kind != "wheel" or g.source != cid:
        return
    gc.end_gesture()
    paint_rings(gc)


def on_drag_start(gc, lst, idx):
    gc.drag_src = (lst, idx)
    gc.reorder_dst = (lst, idx)
    gc.end_gesture()
    gc.gesture = _Gesture(
        kind="drag", token=gc._editor.capture_for_preview(), baseline=gc._runtime.last_lay
    )


def on_drag_enter(gc, dst_list, dst_idx):
    g = gc.gesture
    if (
        g is None
        or g.kind != "drag"
        or gc.drag_src is None
        or (dst_list, dst_idx) == gc.reorder_dst
    ):
        return
    gc.reorder_dst = (dst_list, dst_idx)
    gc._editor.restore_for_preview(g.token)
    idx = dst_idx if dst_idx is not None else (1 << 30)
    gc._editor.move_interval(gc.drag_src[0], gc.drag_src[1], dst_list, idx)
    gesture_render(gc)


def on_drag_end(gc):
    if gc.gesture is not None and gc.gesture.kind == "drag":
        gc.end_gesture()
        gc._renderer.render()
    gc.drag_src = None
    gc.reorder_dst = None


def on_drop(gc, dst_list, dst_idx):
    src = gc.drag_src
    gc.drag_src = None
    gc.reorder_dst = None
    had_preview = gc.gesture is not None and gc.gesture.kind == "drag"
    if had_preview:
        gc.end_gesture()
    if not src:
        if had_preview:
            gc._renderer.render()
        return
    idx = dst_idx if dst_idx is not None else (1 << 30)
    if gc._editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
        gc._renderer.render()
