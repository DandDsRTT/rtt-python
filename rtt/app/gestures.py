from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from rtt.app import _gesture_ops, _gesture_reorder, preview_engine
from rtt.app.grid_tables import RINGABLE_KINDS
from rtt.app.page_assets import callback_method

if TYPE_CHECKING:
    from rtt.app.editing import EditController
    from rtt.app.editor import Editor
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.reconciler import _Reconciler
    from rtt.app.rendering import Renderer


class GestureController:
    def __init__(self, editor: Editor, runtime: PageRuntime) -> None:
        self._editor = editor
        self._runtime = runtime
        self._rec: _Reconciler | None = None
        self._renderer: Renderer | None = None
        self._edits: EditController | None = None
        self.gesture = None
        self.gesture_rendering = False
        self.drag_src = None
        self.reorder_dst = None

    @cached_property
    def combine(self):
        return _GestureCombine(self)

    @cached_property
    def hover(self):
        return _GestureHover(self)

    def bind(self, reconciler: _Reconciler, renderer: Renderer, edits: EditController) -> None:
        self._rec = reconciler
        self._renderer = renderer
        self._edits = edits

    def end_gesture(self):
        g, self.gesture = self.gesture, None
        if g is not None and g.token is not None:
            self._editor.restore_for_preview(g.token)
        return g

    def end_chooser_gesture(self):
        if self.gesture is not None and self.gesture.kind == "chooser":
            self.end_gesture()

    def end_commit_gestures(self):
        if self.gesture is not None and self.gesture.kind in ("hover", "chooser", "temp", "drag"):
            self.end_gesture()

    def occupied_axes(self) -> frozenset:
        occupied = set()
        if self._editor.pending_mapping_row is not None:
            occupied.add("generators")
        if self._editor.pending_comma is not None:
            occupied.add("commas")
        return frozenset(occupied)

    def plan_action(self, op, source_id=None, baseline=None):
        current = baseline if baseline is not None else self._runtime.last_lay
        future = preview_engine.compute_future(self._editor, op, current)
        return preview_engine.plan_preview(current, future, source_id, self.occupied_axes())

    def active_ghost_axes(self) -> tuple:
        g = self.gesture
        if g is not None and g.plan is not None and g.plan.mode == preview_engine.HYBRID:
            return g.plan.ghost_axes
        return ()

    def transform_layout(self, layout):
        g = self.gesture
        if g is not None and g.plan is not None and g.plan.mode == preview_engine.HYBRID:
            return preview_engine.graft_ghost_values(layout, g.baseline, g.plan.future)
        return layout

    def consume_prebuilt(self, op):
        g = self.gesture
        if (
            g is not None
            and g.kind in ("hover", "chooser", "temp")
            and g.plan is not None
            and g.op is op
        ):
            return g.plan.future
        return None

    def consume_prebuilt_choice(self, cell_id, value):
        g = self.gesture
        if (
            g is not None
            and g.kind in ("chooser", "temp")
            and g.plan is not None
            and g.source == cell_id
            and g.op_value == value
        ):
            return g.plan.future
        return None

    def compute_rings(self, layout):
        if not self._editor.settings["preview_highlighting"]:
            return preview_engine.NO_RINGS
        green, amber, red = _gesture_ops.gesture_rings(self, layout)
        draft_amber, draft_red = preview_engine.open_draft_rings(
            layout,
            RINGABLE_KINDS,
            comma_draft=self._editor.pending_comma is not None,
            row_draft=self._editor.pending_mapping_row is not None,
        )
        amber, red = amber | draft_amber, red | draft_red
        pending = frozenset(cell.id for cell in layout.cells if cell.pending)
        red -= pending
        amber -= red | pending
        green -= red | amber | pending
        return green, amber, red

    def paint_cell(self, element_id, green, amber, red):
        element = self._rec.entity(element_id).element
        if element is None:
            return
        ring_sig = (element_id in green, element_id in amber, element_id in red)
        if self._rec.entity(element_id).ring_sig == ring_sig:
            return
        for on, cls in zip(
            ring_sig, ("rtt-preview-add", "rtt-preview-change", "rtt-preview-remove"), strict=True
        ):
            element.classes(add=cls if on else "", remove="" if on else cls)
        self._rec.entities[element_id].ring_sig = ring_sig

    def edit_candidate(self, op):
        g = self.gesture
        if g is None or g.kind != "edit":
            return
        g.op = op
        g.plan = (
            self.plan_action(op, g.source, baseline=g.baseline)
            if op is not None and g.baseline is not None
            else None
        )
        _gesture_ops.paint_rings(self)

    def rebase_edit_gesture(self):
        g = self.gesture
        if g is not None and g.kind == "edit":
            g.baseline = self._runtime.last_lay
            g.plan = None
            _gesture_ops.paint_rings(self)

    @callback_method
    def control_hover(self, op, source_id=None, allow_reflow=False):
        _gesture_ops.control_hover(self, op, source_id, allow_reflow)

    @callback_method
    def control_unhover(self):
        _gesture_ops.control_unhover(self)


class _GestureCombine:
    def __init__(self, gesture_controller) -> None:
        self.gesture_controller = gesture_controller

    @callback_method
    def on_cell_focus(self, cell_id):
        _gesture_ops.on_cell_focus(self.gesture_controller, cell_id)

    @callback_method
    def on_cell_blur(self, cell_id=None):
        _gesture_ops.on_cell_blur(self.gesture_controller, cell_id)

    @callback_method
    def combine_begin(self):
        _gesture_ops.combine_begin(self.gesture_controller)

    @callback_method
    def combine_preview(self, apply, target_pred=None):
        _gesture_ops.combine_preview(self.gesture_controller, apply, target_pred)

    @callback_method
    def combine_commit(self, apply):
        _gesture_ops.combine_commit(self.gesture_controller, apply)

    @callback_method
    def combine_end(self):
        _gesture_ops.combine_end(self.gesture_controller)


class _GestureHover:
    def __init__(self, gesture_controller) -> None:
        self.gesture_controller = gesture_controller

    @callback_method
    def on_chooser_hover(self, cell_id, detail):
        _gesture_ops.on_chooser_hover(self.gesture_controller, cell_id, detail)

    @callback_method
    def on_popup(self, cell_id, is_open):
        _gesture_ops.on_popup(self.gesture_controller, cell_id, is_open)

    @callback_method
    def generator_tuning_hover(self, cell_id):
        _gesture_ops.generator_tuning_hover(self.gesture_controller, cell_id)

    @callback_method
    def generator_tuning_unhover(self, cell_id):
        _gesture_ops.generator_tuning_unhover(self.gesture_controller, cell_id)

    @callback_method
    def on_drag_start(self, lst, index):
        _gesture_reorder.on_drag_start(self.gesture_controller, lst, index)

    @callback_method
    def on_drag_enter(self, dst_list, dst_idx):
        _gesture_reorder.on_drag_enter(self.gesture_controller, dst_list, dst_idx)

    @callback_method
    def on_drag_end(self):
        _gesture_reorder.on_drag_end(self.gesture_controller)

    @callback_method
    def on_drop(self, dst_list, dst_idx):
        _gesture_reorder.on_drop(self.gesture_controller, dst_list, dst_idx)

    @callback_method
    def on_band_drag_start(self, axis, key):
        _gesture_reorder.on_band_drag_start(self.gesture_controller, axis, key)

    @callback_method
    def on_band_drag_end(self):
        _gesture_reorder.on_band_drag_end(self.gesture_controller)

    @callback_method
    def on_band_drop(self, axis, before_key):
        _gesture_reorder.on_band_drop(self.gesture_controller, axis, before_key)
