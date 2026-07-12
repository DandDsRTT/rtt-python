from __future__ import annotations

from dataclasses import replace

from nicegui import ui

from rtt.app import presets, preview_engine, service
from rtt.app._gesture_render import gesture_render
from rtt.app.grid_tables import RINGABLE_KINDS
from rtt.app.page_assets import _Gesture, _hover_index, _option_key
from rtt.app.preview_engine import HYBRID, NO_RINGS, PAINT, REFLOW
from rtt.app.spreadsheet_text import (
    added_cell_ids,
    moved_cell_ids,
    value_changed_cell_ids,
)


def take_over_gesture(gesture_controller):
    was = gesture_controller.end_gesture()
    if was is not None and was.reflowed:
        gesture_render(gesture_controller)


def paint_rings(gesture_controller):
    layout = gesture_controller._runtime.last_lay
    if layout is None:
        return
    green, amber, red = gesture_controller.compute_rings(layout)
    for cell in layout.cells:
        gesture_controller.paint_cell(cell.id, green, amber, red)


def _live_rings(gesture, layout):
    green = added_cell_ids(gesture.baseline, layout)
    amber = (
        value_changed_cell_ids(gesture.baseline, layout) | moved_cell_ids(gesture.baseline, layout)
    ) - green
    if gesture.target_pred is not None:
        amber |= frozenset(cell.id for cell in layout.cells if gesture.target_pred(cell))
    return green - {gesture.source}, amber - {gesture.source}, frozenset()


def gesture_rings(gesture_controller, layout):
    g = gesture_controller.gesture
    if g is None:
        return NO_RINGS
    if g.plan is not None:
        plan = g.plan
        if plan.mode == REFLOW and g.reflowed:
            green = plan.added
            amber = (plan.changed | plan.moved) - green
            return green - {g.source}, amber - {g.source}, frozenset()
        red = plan.removed
        if plan.mode == HYBRID and g.baseline is not None:
            red = red | preview_engine.hybrid_orphan_ids(layout, g.baseline)
        return frozenset(), plan.changed - {g.source}, red - {g.source}
    if g.baseline is not None:
        return _live_rings(g, layout)
    return NO_RINGS


def compute_rings(gesture_controller, layout):
    if not gesture_controller._editor.settings["preview_highlighting"]:
        return NO_RINGS
    green, amber, red = gesture_rings(gesture_controller, layout)
    comma_draft, row_draft = preview_engine.draft_flags(gesture_controller._editor)
    draft_amber, draft_red = preview_engine.open_draft_rings(
        layout, RINGABLE_KINDS, comma_draft=comma_draft, row_draft=row_draft
    )
    pending = frozenset(cell.id for cell in layout.cells if cell.pending)
    red = (red - pending) | draft_red
    amber = ((amber | draft_amber) - pending) - red
    green = ((green - pending) - red) - amber
    return green, amber, red


def plan_action(gesture_controller, op, source_id, current):
    editor = gesture_controller._editor
    future = preview_engine.compute_future(editor, op, current)
    return preview_engine.plan_preview(
        current, future, source_id, preview_engine.occupied_axes(editor)
    )


def plan_structural_action(gesture_controller, op, current):
    editor = gesture_controller._editor
    future = preview_engine.compute_future(editor, op, current)
    return preview_engine.plan_structural(current, future, preview_engine.occupied_axes(editor))


def edit_candidate(gesture_controller, op):
    g = gesture_controller.gesture
    if g is None or g.kind != "edit":
        return
    g.op = op
    if op is not None and g.baseline is not None:
        future = preview_engine.compute_future(gesture_controller._editor, op, g.baseline)
        g.plan = preview_engine.plan_edit(g.baseline, gesture_controller._runtime.last_lay, future)
    else:
        g.plan = None
    paint_rings(gesture_controller)


def start_planned_preview(gesture_controller, gesture, plan) -> None:
    gesture.plan = plan
    if plan.mode == REFLOW:
        if gesture.token is None:
            gesture.token = gesture_controller._editor.capture_for_preview()
        gesture.op()
        gesture.reflowed = True
        gesture_render(gesture_controller, prebuilt=plan.future)
    elif plan.mode == HYBRID:
        hybrid = preview_engine.build_hybrid(gesture_controller._editor, gesture.baseline, plan)
        gesture_render(gesture_controller, prebuilt=hybrid)
    else:
        paint_rings(gesture_controller)


def end_planned_preview(gesture_controller) -> None:
    was = gesture_controller.end_gesture()
    if was is None:
        return
    if was.reflowed or (was.plan is not None and was.plan.mode == HYBRID):
        gesture_controller._renderer.render(
            prebuilt=was.baseline if was.baseline is not None else None
        )
    else:
        paint_rings(gesture_controller)


def control_hover(gesture_controller, op, source_id=None, allow_reflow=False):
    if not gesture_controller._editor.settings["preview_highlighting"]:
        return
    g = gesture_controller.gesture
    if g is not None and g.kind in ("edit", "drag"):
        return
    previous = None
    if g is not None and g.kind == "wheel":
        previous = g
    elif g is not None:
        take_over_gesture(gesture_controller)
    gesture = _Gesture(
        kind="hover",
        source=source_id,
        op=op,
        baseline=gesture_controller._runtime.last_lay,
        previous=previous,
    )
    gesture_controller.gesture = gesture
    plan = plan_action(gesture_controller, op, source_id, gesture.baseline)
    if plan.mode != PAINT and not allow_reflow:
        plan = replace(plan, mode=PAINT)
    start_planned_preview(gesture_controller, gesture, plan)


def control_unhover(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "hover":
        return
    previous = g.previous
    if g.reflowed or (g.plan is not None and g.plan.mode == HYBRID):
        end_planned_preview(gesture_controller)
        gesture_controller.gesture = previous
        if previous is not None:
            paint_rings(gesture_controller)
    else:
        gesture_controller.end_gesture()
        gesture_controller.gesture = previous
        paint_rings(gesture_controller)


def _option_kind(cell_id: str) -> str:
    return (
        "temp" if cell_id.startswith(("preset:temperament", "etpick:", "commapick:")) else "chooser"
    )


def ensure_option_gesture(gesture_controller, cell_id):
    kind = _option_kind(cell_id)
    g = gesture_controller.gesture
    if g is not None and (g.kind != kind or g.source != cell_id):
        if g.kind in ("edit", "drag"):
            return None
        take_over_gesture(gesture_controller)
        g = None
    if g is None:
        g = gesture_controller.gesture = _Gesture(
            kind=kind,
            source=cell_id,
            token=gesture_controller._editor.capture_for_preview(),
            baseline=gesture_controller._runtime.last_lay,
        )
    return g


def option_preview(gesture_controller, cell_id, op, op_value):
    g = ensure_option_gesture(gesture_controller, cell_id)
    if g is None:
        return
    gesture_controller._editor.restore_for_preview(g.token)
    was_showing = g.reflowed or (g.plan is not None and g.plan.mode == HYBRID)
    g.reflowed = False
    g.op, g.op_value, g.plan = op, op_value, None
    if op is None:
        if was_showing:
            gesture_render(
                gesture_controller, prebuilt=g.baseline if g.baseline is not None else None
            )
        else:
            paint_rings(gesture_controller)
        return
    plan = (
        plan_structural_action(gesture_controller, op, g.baseline)
        if g.kind == "temp"
        else plan_action(gesture_controller, op, cell_id, g.baseline)
    )
    if plan.mode == PAINT and was_showing:
        gesture_render(gesture_controller, prebuilt=g.baseline if g.baseline is not None else None)
        g.plan = plan
        paint_rings(gesture_controller)
        return
    start_planned_preview(gesture_controller, g, plan)


def end_option_preview(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind not in ("chooser", "temp"):
        return
    end_planned_preview(gesture_controller)


def chooser_unhover(gesture_controller):
    g = gesture_controller.gesture
    if g is None or g.kind != "chooser":
        return
    end_planned_preview(gesture_controller)


def temperament_hover_preview(gesture_controller, cell_id, key):
    if key not in presets.TEMPERAMENT_COMMAS:
        end_option_preview(gesture_controller)
        return
    option_preview(
        gesture_controller,
        cell_id,
        lambda: gesture_controller._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key]),
        key,
    )


def _subpick_draft_op(editor, cell_id, value):
    if cell_id == "etpick:draft":

        def op(v=value):
            editor.pending_mapping_row = list(presets.et_value_to_val(v, editor.state.domain_basis))
    else:

        def op(v=value):
            editor.pending_comma = list(presets.comma_value_to_vector(v, editor.state.domain_basis))

    return op


def _subpick_pick_op(editor, cell_id, value, index):
    if cell_id.startswith("etpick:"):
        return lambda i=index, v=value: editor.set_mapping_row(
            i, presets.et_value_to_val(v, editor.state.domain_basis)
        )
    return lambda c=index, v=value: editor.set_comma(
        c, presets.comma_value_to_vector(v, editor.state.domain_basis)
    )


def subpick_hover_preview(gesture_controller, cell_id, value):
    if value is None:
        end_option_preview(gesture_controller)
        return
    editor = gesture_controller._editor
    if cell_id in ("etpick:draft", "commapick:draft"):
        op = _subpick_draft_op(editor, cell_id, value)
    else:
        index = gesture_controller._runtime.token_index(
            cell_id, "generators" if cell_id.startswith("etpick:") else "commas"
        )
        if index is None:
            end_option_preview(gesture_controller)
            return
        op = _subpick_pick_op(editor, cell_id, value, index)
    option_preview(gesture_controller, cell_id, op, value)


def hover_value_chooser(gesture_controller, cell_id, index) -> None:
    handles = gesture_controller._rec.handles(cell_id)
    radio = handles.chooser.radio
    if radio is not None:
        value = radio[0][index]
    else:
        entry = handles.chooser.select
        selection = entry[1] if isinstance(entry, tuple) else entry
        if cell_id == "preset:target":
            family = _option_key(selection, index)
            if family not in presets.TARGET_SETS:
                chooser_unhover(gesture_controller)
                return
            spec = service.target_spec(family, entry[0].value)
            option_preview(
                gesture_controller,
                cell_id,
                lambda: gesture_controller._editor.set_target_spec(spec),
                family,
            )
            return
        value = _option_key(selection, index)
    apply = gesture_controller._edits.candidate_apply(cell_id, value)
    if apply is None:
        chooser_unhover(gesture_controller)
        return
    option_preview(gesture_controller, cell_id, apply, value)


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


def on_chooser_hover(gesture_controller, cell_id, detail):
    handles = gesture_controller._rec.handles(cell_id)
    radio = handles.chooser.radio
    if radio is not None:
        index = _hover_index(detail)
        if index is None or radio[1] or not 0 <= index < len(radio[0]):
            chooser_unhover(gesture_controller)
        else:
            hover_value_chooser(gesture_controller, cell_id, index)
        return
    entry = handles.chooser.select
    selection = entry[1] if isinstance(entry, tuple) else entry
    if not isinstance(selection, ui.select):
        return
    index = _hover_index(detail)
    if index is not None and handles.popup_state == "closed":
        return
    if cell_id.startswith(("etpick:", "commapick:")):
        subpick_hover_preview(
            gesture_controller,
            cell_id,
            _option_key(selection, index) if index is not None else None,
        )
        return
    if cell_id.startswith("preset:temperament"):
        temperament_hover_preview(gesture_controller, cell_id, _option_key(selection, index))
        return
    if index is None or not selection.enabled:
        chooser_unhover(gesture_controller)
        return
    hover_value_chooser(gesture_controller, cell_id, index)


def on_popup(gesture_controller, cell_id, is_open):
    gesture_controller._rec.cells[cell_id].popup_state = "open" if is_open else "closed"
    if not is_open:
        on_chooser_hover(gesture_controller, cell_id, None)


def generator_tuning_hover(gesture_controller, cell_id):
    g = gesture_controller.gesture
    if g is not None and g.kind in ("edit", "drag", "hover"):
        return
    take_over_gesture(gesture_controller)
    gesture_controller.gesture = _Gesture(
        kind="wheel", source=cell_id, baseline=gesture_controller._runtime.last_lay
    )


def generator_tuning_unhover(gesture_controller, cell_id):
    g = gesture_controller.gesture
    if g is None or g.kind != "wheel" or g.source != cell_id:
        return
    gesture_controller.end_gesture()
    paint_rings(gesture_controller)
