from __future__ import annotations

from nicegui import ui

from rtt.app import presets, service, spreadsheet_text
from rtt.app.page_assets import _Gesture, _hover_index, _option_key


def gesture_render(gesture_controller):
    gesture_controller.gesture_rendering = True
    try:
        gesture_controller._renderer.render()
    finally:
        gesture_controller.gesture_rendering = False


def take_over_gesture(gesture_controller):
    was = gesture_controller.end_gesture()
    if was is not None and was.reflowed:
        gesture_render(gesture_controller)


def paint_rings(gesture_controller):
    layout = gesture_controller._runtime.last_lay
    if layout is None:
        return
    amber, red = gesture_controller.compute_rings(layout)
    for cell_box in layout.cells:
        gesture_controller.paint_cell(cell_box.id, amber, red)


def gesture_rings(gesture_controller, layout):
    g = gesture_controller.gesture
    if g is None:
        return frozenset(), frozenset()
    if g.apply is not None:
        base = g.baseline if g.baseline is not None else layout
        token = gesture_controller._editor.capture_for_preview()
        try:
            g.apply()
            hyp = gesture_controller._editor.layout(prev_ids=base.identities)
            amber = spreadsheet_text.changed_cell_ids(base, hyp)
            red = spreadsheet_text.removed_cell_ids(layout, hyp)
        finally:
            gesture_controller._editor.restore_for_preview(token)
        return amber - {g.source}, red
    if g.baseline is not None:
        amber = spreadsheet_text.changed_cell_ids(g.baseline, layout) - {g.source}
        if g.target_pred is not None:
            amber |= frozenset(cell_box.id for cell_box in layout.cells if g.target_pred(cell_box))
        return amber, frozenset()
    return frozenset(), frozenset()


def cell_xy(layout, element_id):
    for c in layout.cells:
        if c.id == element_id:
            return (round(c.x), round(c.y))
    return None


def chooser_hover(gesture_controller, cell_id, apply):
    if not gesture_controller._editor.settings["preview_highlighting"]:
        return
    g = gesture_controller.gesture
    if g is not None and g.kind in ("edit", "drag"):
        return
    if g is not None and (g.kind != "chooser" or g.source != cell_id):
        take_over_gesture(gesture_controller)
    if gesture_controller.gesture is None:
        gesture_controller.gesture = _Gesture(
            kind="chooser",
            source=cell_id,
            token=gesture_controller._editor.capture_for_preview(),
            baseline=gesture_controller._runtime.last_lay,
        )
    g = gesture_controller.gesture
    gesture_controller._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gesture_controller)
    if apply is None:
        g.apply = None
        paint_rings(gesture_controller)
        return
    base = g.baseline
    apply()
    hyp = gesture_controller._editor.layout(prev_ids=base.identities if base is not None else None)
    disturbs = base is not None and (
        spreadsheet_text.removed_cell_ids(base, hyp)
        or cell_xy(base, cell_id) != cell_xy(hyp, cell_id)
    )
    if disturbs:
        gesture_controller._editor.restore_for_preview(g.token)
        g.apply = apply
        paint_rings(gesture_controller)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gesture_controller)


def chooser_unhover(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "chooser":
        return
    was = gesture_controller.end_gesture()
    if was is not None and was.reflowed:
        gesture_controller._renderer.render()
    else:
        paint_rings(gesture_controller)


def end_temperament_preview(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "temp":
        return
    was = gesture_controller.end_gesture()
    if was.reflowed:
        gesture_controller._renderer.render()
    else:
        paint_rings(gesture_controller)


def temperament_hover_preview(gesture_controller, key):
    if key not in presets.TEMPERAMENT_COMMAS:
        end_temperament_preview(gesture_controller)
        return
    g = gesture_controller.gesture
    if g is None or g.kind != "temp":
        if g is not None and g.kind in ("edit", "drag"):
            return
        gesture_controller.end_gesture()
        g = gesture_controller.gesture = _Gesture(
            kind="temp",
            token=gesture_controller._editor.capture_for_preview(),
            baseline=gesture_controller._runtime.last_lay,
        )
    gesture_controller._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gesture_controller)
    base = gesture_controller._editor.state
    gesture_controller._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
    hyp = gesture_controller._editor.state
    if (
        hyp.dimensionality < base.dimensionality
        or hyp.rank < base.rank
        or hyp.nullity < base.nullity
    ):
        gesture_controller._editor.restore_for_preview(g.token)
        g.apply = lambda: gesture_controller._editor.edit_comma_basis(
            presets.TEMPERAMENT_COMMAS[key]
        )
        paint_rings(gesture_controller)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gesture_controller)


def ensure_temp_gesture(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "temp":
        if g is not None and g.kind in ("edit", "drag"):
            return None
        gesture_controller.end_gesture()
        g = gesture_controller.gesture = _Gesture(
            kind="temp",
            token=gesture_controller._editor.capture_for_preview(),
            baseline=gesture_controller._runtime.last_lay,
        )
    gesture_controller._editor.restore_for_preview(g.token)
    if g.reflowed:
        g.reflowed = False
        g.apply = None
        gesture_render(gesture_controller)
    return g


def subpick_hover_preview(gesture_controller, cell_id, value):
    if value is None:
        end_temperament_preview(gesture_controller)
        return
    draft = cell_id in ("etpick:draft", "commapick:draft")
    index = None
    if not draft:
        index = gesture_controller._runtime.token_index(
            cell_id, "gens" if cell_id.startswith("etpick:") else "commas"
        )
        if index is None:
            end_temperament_preview(gesture_controller)
            return
    g = ensure_temp_gesture(gesture_controller)
    if g is None:
        return
    if draft:
        preview_subpick_draft(gesture_controller, cell_id, value)
    else:
        preview_subpick_pick(gesture_controller, cell_id, value, index)


def preview_subpick_draft(gesture_controller, cell_id, value) -> None:
    db = gesture_controller._editor.state.domain_basis
    g = gesture_controller.gesture
    if cell_id == "etpick:draft":
        gesture_controller._editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
    else:
        gesture_controller._editor.pending_comma = list(presets.comma_value_to_vector(value, db))
    g.apply = None
    g.reflowed = True
    gesture_render(gesture_controller)


def preview_subpick_pick(gesture_controller, cell_id, value, index) -> None:
    db = gesture_controller._editor.state.domain_basis
    g = gesture_controller.gesture
    if cell_id.startswith("etpick:"):

        def apply(i=index, v=value):
            return gesture_controller._editor.set_mapping_row(i, presets.et_value_to_val(v, db))
    else:

        def apply(c=index, v=value):
            return gesture_controller._editor.set_comma(c, presets.comma_value_to_vector(v, db))

    base = gesture_controller._editor.state
    apply()
    hyp = gesture_controller._editor.state
    if (
        hyp.dimensionality < base.dimensionality
        or hyp.rank < base.rank
        or hyp.nullity < base.nullity
    ):
        gesture_controller._editor.restore_for_preview(g.token)
        g.apply = apply
        paint_rings(gesture_controller)
    else:
        g.apply = None
        g.reflowed = True
        gesture_render(gesture_controller)


def hover_value_chooser(gesture_controller, cell_id, index) -> None:
    entry = gesture_controller._rec.handles(cell_id).chooser.select
    sel = entry[1] if isinstance(entry, tuple) else entry
    if cell_id == "preset:target":
        family = _option_key(sel, index)
        if family not in presets.TARGET_SETS:
            chooser_unhover(gesture_controller)
            return
        spec = service.target_spec(family, entry[0].value)
        chooser_hover(
            gesture_controller, cell_id, lambda: gesture_controller._editor.set_target_spec(spec)
        )
        return
    apply = gesture_controller._edits.candidate_apply(cell_id, _option_key(sel, index))
    if apply is None:
        chooser_unhover(gesture_controller)
        return
    chooser_hover(gesture_controller, cell_id, apply)


def on_cell_focus(gesture_controller, cell_id):
    take_over_gesture(gesture_controller)
    gesture_controller.gesture = _Gesture(
        kind="edit", source=cell_id, baseline=gesture_controller._runtime.last_lay
    )


def on_cell_blur(gesture_controller, cell_id=None):
    g = gesture_controller.gesture
    if g is not None and g.kind in ("edit", "wheel") and (cell_id is None or g.source == cell_id):
        gesture_controller.end_gesture()
        paint_rings(gesture_controller)


def combine_begin(gesture_controller):
    gesture_controller.end_gesture()
    gesture_controller.gesture = _Gesture(
        kind="drag",
        token=gesture_controller._editor.capture_for_preview(),
        baseline=gesture_controller._runtime.last_lay,
    )


def combine_preview(gesture_controller, apply, target_pred=None):
    g = gesture_controller.gesture
    if g is None or g.kind != "drag":
        return
    gesture_controller._editor.restore_for_preview(g.token)
    g.target_pred = target_pred if apply is not None else None
    if apply is not None:
        apply()
    gesture_render(gesture_controller)


def combine_commit(gesture_controller, apply):
    g = gesture_controller.gesture
    if g is None or g.kind != "drag":
        return
    gesture_controller.end_gesture()
    gesture_controller._edits.act(apply)


def combine_end(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "drag":
        return
    gesture_controller.end_gesture()
    gesture_controller._renderer.render()


def rank_remove_hover(gesture_controller, axis, index):
    if not gesture_controller._editor.settings["preview_highlighting"]:
        return
    if gesture_controller.gesture is not None and gesture_controller.gesture.kind in (
        "edit",
        "drag",
    ):
        return
    gesture_controller.rank_remove = (axis, index)
    gesture_controller.rank_rendering = True
    try:
        gesture_controller._renderer.render()
    finally:
        gesture_controller.rank_rendering = False


def rank_remove_unhover(gesture_controller):
    if gesture_controller.rank_remove is not None:
        gesture_controller.rank_remove = None
        gesture_controller._renderer.render()


def on_chooser_hover(gesture_controller, cell_id, detail):
    entry = gesture_controller._rec.handles(cell_id).chooser.select
    sel = entry[1] if isinstance(entry, tuple) else entry
    if not isinstance(sel, ui.select):
        return
    index = _hover_index(detail)
    if index is not None and gesture_controller._rec.handles(cell_id).popup_state == "closed":
        return
    if cell_id.startswith(("etpick:", "commapick:")):
        subpick_hover_preview(
            gesture_controller, cell_id, _option_key(sel, index) if index is not None else None
        )
        return
    if cell_id.startswith("preset:temperament"):
        temperament_hover_preview(gesture_controller, _option_key(sel, index))
        return
    if index is None or not sel.enabled:
        chooser_unhover(gesture_controller)
        return
    hover_value_chooser(gesture_controller, cell_id, index)


def on_popup(gesture_controller, cell_id, is_open):
    gesture_controller._rec.cells[cell_id].popup_state = "open" if is_open else "closed"
    if not is_open:
        on_chooser_hover(gesture_controller, cell_id, None)


def gentuning_hover(gesture_controller, cell_id):
    g = gesture_controller.gesture
    if g is not None and g.kind in ("edit", "drag", "hover"):
        return
    take_over_gesture(gesture_controller)
    gesture_controller.gesture = _Gesture(
        kind="wheel", source=cell_id, baseline=gesture_controller._runtime.last_lay
    )


def gentuning_unhover(gesture_controller, cell_id):
    g = gesture_controller.gesture
    if g is None or g.kind != "wheel" or g.source != cell_id:
        return
    gesture_controller.end_gesture()
    paint_rings(gesture_controller)


def on_drag_start(gesture_controller, lst, index):
    gesture_controller.drag_src = (lst, index)
    gesture_controller.reorder_dst = (lst, index)
    gesture_controller.end_gesture()
    gesture_controller.gesture = _Gesture(
        kind="drag",
        token=gesture_controller._editor.capture_for_preview(),
        baseline=gesture_controller._runtime.last_lay,
    )


def on_drag_enter(gesture_controller, dst_list, dst_idx):
    g = gesture_controller.gesture
    if (
        g is None
        or g.kind != "drag"
        or gesture_controller.drag_src is None
        or (dst_list, dst_idx) == gesture_controller.reorder_dst
    ):
        return
    gesture_controller.reorder_dst = (dst_list, dst_idx)
    gesture_controller._editor.restore_for_preview(g.token)
    index = dst_idx if dst_idx is not None else (1 << 30)
    gesture_controller._editor.move_interval(
        gesture_controller.drag_src[0], gesture_controller.drag_src[1], dst_list, index
    )
    gesture_render(gesture_controller)


def on_drag_end(gesture_controller):
    if gesture_controller.gesture is not None and gesture_controller.gesture.kind == "drag":
        gesture_controller.end_gesture()
        gesture_controller._renderer.render()
    gesture_controller.drag_src = None
    gesture_controller.reorder_dst = None


def on_drop(gesture_controller, dst_list, dst_idx):
    src = gesture_controller.drag_src
    gesture_controller.drag_src = None
    gesture_controller.reorder_dst = None
    had_preview = (
        gesture_controller.gesture is not None and gesture_controller.gesture.kind == "drag"
    )
    if had_preview:
        gesture_controller.end_gesture()
    if not src:
        if had_preview:
            gesture_controller._renderer.render()
        return
    index = dst_idx if dst_idx is not None else (1 << 30)
    if gesture_controller._editor.move_interval(src[0], src[1], dst_list, index) or had_preview:
        gesture_controller._renderer.render()
