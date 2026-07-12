from __future__ import annotations

from rtt.app._gesture_render import gesture_render
from rtt.app.page_assets import _Gesture

_INTERVALS = "intervals"
_BAND_MOVE = {"row": "move_row", "column": "move_column"}
_APPEND = 1 << 30


def _move(gesture_controller, source, destination) -> bool:
    family, target = destination
    if family == _INTERVALS:
        (src_list, src_idx), (dst_list, dst_idx) = source[1], target
        return gesture_controller._editor.move_interval(
            src_list, src_idx, dst_list, _APPEND if dst_idx is None else dst_idx
        )
    return getattr(gesture_controller._editor, _BAND_MOVE[family])(source[1], target)


def _begin_drag(gesture_controller, source) -> None:
    gesture_controller.drag_src = source
    gesture_controller.reorder_dst = source
    gesture_controller.end_gesture()
    gesture_controller.gesture = _Gesture(
        kind="drag",
        token=gesture_controller._editor.capture_for_preview(),
        baseline=gesture_controller._runtime.last_lay,
    )


def _dragging_from(gesture_controller, family):
    g = gesture_controller.gesture
    source = gesture_controller.drag_src
    if g is None or g.kind != "drag" or source is None or source[0] != family:
        return None
    return source


def _preview_drag(gesture_controller, family, destination) -> None:
    source = _dragging_from(gesture_controller, family)
    if source is None or destination == gesture_controller.reorder_dst:
        return
    gesture_controller.reorder_dst = destination
    gesture_controller._editor.restore_for_preview(gesture_controller.gesture.token)
    _move(gesture_controller, source, destination)
    gesture_render(gesture_controller)


def _end_drag(gesture_controller) -> None:
    if gesture_controller.gesture is not None and gesture_controller.gesture.kind == "drag":
        gesture_controller.end_gesture()
        gesture_controller._renderer.render()
    gesture_controller.drag_src = None
    gesture_controller.reorder_dst = None


def _commit_drag(gesture_controller, family, destination) -> None:
    source = _dragging_from(gesture_controller, family)
    had_preview = (
        gesture_controller.gesture is not None and gesture_controller.gesture.kind == "drag"
    )
    gesture_controller.drag_src = None
    gesture_controller.reorder_dst = None
    if had_preview:
        gesture_controller.end_gesture()
    moved = source is not None and _move(gesture_controller, source, destination)
    if moved or had_preview:
        gesture_controller._renderer.render()


def on_drag_start(gesture_controller, lst, index):
    _begin_drag(gesture_controller, (_INTERVALS, (lst, index)))


def on_drag_enter(gesture_controller, dst_list, dst_idx):
    _preview_drag(gesture_controller, _INTERVALS, (_INTERVALS, (dst_list, dst_idx)))


def on_drag_end(gesture_controller):
    _end_drag(gesture_controller)


def on_drop(gesture_controller, dst_list, dst_idx):
    _commit_drag(gesture_controller, _INTERVALS, (_INTERVALS, (dst_list, dst_idx)))


def on_band_drag_start(gesture_controller, axis, key):
    _begin_drag(gesture_controller, (axis, key))


def on_band_drag_end(gesture_controller):
    _end_drag(gesture_controller)


def on_band_drop(gesture_controller, axis, before_key):
    _commit_drag(gesture_controller, axis, (axis, before_key or None))
