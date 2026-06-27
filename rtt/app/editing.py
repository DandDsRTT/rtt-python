from __future__ import annotations

from typing import TYPE_CHECKING

from rtt.app import _editing_controls
from rtt.app._editing_tuning import _TuningEdits
from rtt.app._editing_vectors import _VectorEdits
from rtt.app.page_assets import cb_method

if TYPE_CHECKING:
    from rtt.app.editor import Editor
    from rtt.app.gestures import GestureController
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.reconciler import _Reconciler
    from rtt.app.rendering import Renderer


class EditController:
    def __init__(
        self,
        editor: Editor,
        rec: _Reconciler,
        gestures: GestureController,
        renderer: Renderer,
        runtime: PageRuntime,
    ) -> None:
        self._editor = editor
        self._rec = rec
        self._gestures = gestures
        self._renderer = renderer
        self._runtime = runtime
        self.vectors = _VectorEdits(self)
        self.tuning = _TuningEdits(self)
        self.controls = _ControlEdits(self)

    def _build_edit_specs(self) -> None:
        _editing_controls.build_edit_specs(self)

    def _build_vector_list_specs(self) -> None:
        _editing_controls.build_vector_list_specs(self)

    def _apply_outcome(self, out, commit, preview=False) -> None:
        _editing_controls.apply_outcome(self, out, commit, preview)

    @cb_method
    def act(self, action):
        _editing_controls.act(self._gestures, self._renderer, action)

    def on_show_toggle(self, key, value):
        _editing_controls.on_show_toggle(self, key, value)

    def on_select_all(self, value, keys):
        _editing_controls.on_select_all(self._editor, self._renderer, self._runtime, value, keys)

    def on_part_click(self, key):
        _editing_controls.on_part_click(self._editor, self._renderer, self._runtime, key)

    @cb_method
    def on_target_change(self):
        _editing_controls.on_target_change(self)

    def candidate_apply(self, cid, value):
        return _editing_controls.candidate_apply(self, cid, value)


class _ControlEdits:
    def __init__(self, e) -> None:
        self.e = e

    @cb_method
    def add_interval(self, action, group):
        _editing_controls.add_interval(self.e, action, group)

    @cb_method
    def on_preset(self, cid, value):
        _editing_controls.on_preset(self.e, cid, value)

    @cb_method
    def on_subpick(self, cid, value):
        _editing_controls.on_subpick(self.e, cid, value)

    @cb_method
    def on_form_choose(self, cid, value):
        _editing_controls.on_form_choose(self.e, cid, value)

    @cb_method
    def on_control_select(self, cid, value):
        _editing_controls.on_control_select(self.e, cid, value)

    @cb_method
    def on_range_mode(self, value):
        _editing_controls.on_range_mode(self.e, value)

    @cb_method
    def on_toggle(self, item):
        _editing_controls.on_toggle(self.e, item)

    @cb_method
    def on_toggle_all(self):
        _editing_controls.on_toggle_all(self.e)
