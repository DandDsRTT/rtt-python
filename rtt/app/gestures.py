from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from rtt.app import _gesture_ops
from rtt.app.page_assets import _Gesture, cb_method

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
        self.rank_remove = None
        self.rank_rendering = False
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
        self.rank_remove = None

    def compute_rings(self, layout):
        if not self._editor.settings["preview_highlighting"]:
            return frozenset(), frozenset()
        static_red = frozenset(cell_box.id for cell_box in layout.cells if cell_box.preview_remove)
        static_amber = frozenset(cell_box.id for cell_box in layout.cells if cell_box.preview_change)
        amber, red = _gesture_ops.gesture_rings(self, layout)
        pending = frozenset(cell_box.id for cell_box in layout.cells if cell_box.pending)
        return (amber | static_amber) - pending, (red | static_red) - pending

    def paint_cell(self, element_id, amber, red):
        el = self._rec.entity(element_id).el
        if el is None:
            return
        rsig = (element_id in amber, element_id in red)
        if self._rec.entity(element_id).ring_sig == rsig:
            return
        el.classes(
            add="rtt-preview-change" if element_id in amber else "",
            remove="" if element_id in amber else "rtt-preview-change",
        )
        el.classes(
            add="rtt-preview-remove" if element_id in red else "",
            remove="" if element_id in red else "rtt-preview-remove",
        )
        self._rec.entities[element_id].ring_sig = rsig

    def edit_candidate(self, apply):
        g = self.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        _gesture_ops.paint_rings(self)

    def rebase_edit_gesture(self):
        g = self.gesture
        if g is not None and g.kind == "edit":
            g.baseline = self._runtime.last_lay
            _gesture_ops.paint_rings(self)

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
            _gesture_ops.take_over_gesture(self)
        self.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        _gesture_ops.paint_rings(self)

    @cb_method
    def control_unhover(self):
        g = self.gesture
        if g is None or g.kind != "hover":
            return
        self.gesture = g.prev
        _gesture_ops.paint_rings(self)


class _GestureCombine:
    def __init__(self, gesture_controller) -> None:
        self.gesture_controller = gesture_controller

    @cb_method
    def on_cell_focus(self, cell_id):
        _gesture_ops.on_cell_focus(self.gesture_controller, cell_id)

    @cb_method
    def on_cell_blur(self, cell_id=None):
        _gesture_ops.on_cell_blur(self.gesture_controller, cell_id)

    @cb_method
    def combine_begin(self):
        _gesture_ops.combine_begin(self.gesture_controller)

    @cb_method
    def combine_preview(self, apply, target_pred=None):
        _gesture_ops.combine_preview(self.gesture_controller, apply, target_pred)

    @cb_method
    def combine_commit(self, apply):
        _gesture_ops.combine_commit(self.gesture_controller, apply)

    @cb_method
    def combine_end(self):
        _gesture_ops.combine_end(self.gesture_controller)

    @cb_method
    def rank_remove_hover(self, axis, index):
        _gesture_ops.rank_remove_hover(self.gesture_controller, axis, index)

    @cb_method
    def rank_remove_unhover(self):
        _gesture_ops.rank_remove_unhover(self.gesture_controller)


class _GestureHover:
    def __init__(self, gesture_controller) -> None:
        self.gesture_controller = gesture_controller

    @cb_method
    def on_chooser_hover(self, cell_id, detail):
        _gesture_ops.on_chooser_hover(self.gesture_controller, cell_id, detail)

    @cb_method
    def on_popup(self, cell_id, is_open):
        _gesture_ops.on_popup(self.gesture_controller, cell_id, is_open)

    @cb_method
    def gentuning_hover(self, cell_id):
        _gesture_ops.gentuning_hover(self.gesture_controller, cell_id)

    @cb_method
    def gentuning_unhover(self, cell_id):
        _gesture_ops.gentuning_unhover(self.gesture_controller, cell_id)

    @cb_method
    def on_drag_start(self, lst, index):
        _gesture_ops.on_drag_start(self.gesture_controller, lst, index)

    @cb_method
    def on_drag_enter(self, dst_list, dst_idx):
        _gesture_ops.on_drag_enter(self.gesture_controller, dst_list, dst_idx)

    @cb_method
    def on_drag_end(self):
        _gesture_ops.on_drag_end(self.gesture_controller)

    @cb_method
    def on_drop(self, dst_list, dst_idx):
        _gesture_ops.on_drop(self.gesture_controller, dst_list, dst_idx)
