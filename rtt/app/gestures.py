from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from rtt.app import _gesture_ops, _gesture_reorder
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

    def compute_rings(self, layout):
        return _gesture_ops.compute_rings(self, layout)

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
        _gesture_ops.edit_candidate(self, op)

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
